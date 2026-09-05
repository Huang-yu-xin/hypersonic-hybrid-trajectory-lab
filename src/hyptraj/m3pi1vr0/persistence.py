"""M3-PI1VR0 hardened transactional persistence (incident-repaired contract).

Repairs the two defects that invalidated M3-PI1V (PI1V-X):

1. Filesystem safety -- logical trial ids may contain characters (e.g. ``::``)
   that are illegal in Windows temporary filenames.  ``safe_fs_id`` provides a
   canonical, reversible, Windows-safe encoding; the logical scientific id is
   unchanged inside the record body and only the filesystem path is encoded.

2. Sequencing -- the frozen 12-step contract is enforced structurally: the
   simulator callable is never invoked before the durable STARTED ledger entry
   (step 2).  Failure-injection hooks cover every inter-step gap for synthetic
   verification; a real failure appends CONSUMED_INVALID and the stage must
   abort (no replay of the same state/rep or the same exact seed).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from hyptraj.m3cf1r0.persistence import (
    fsync_directory,
    ledger_append,
    ledger_entries,
)

__all__ = [
    "PathSafetyError",
    "FrozenArtifactError",
    "ReplayError",
    "FAULT_TAGS",
    "safe_fs_id",
    "decode_fs_id",
    "validate_safe_path",
    "assert_not_frozen",
    "ensure_not_started",
    "ensure_seed_unused",
    "run_trial_transactional",
    "trial_sha256",
]

SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz"
                       "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL",
                    *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10))}
MAX_SAFE_LEN = 200
ESCAPE_RE = re.compile(r"_x([0-9a-f]{2})")


def _esc_char(c: str) -> str:
    return c if c in SAFE_CHARS else f"_x{ord(c):02x}"


def safe_fs_id(logical: str) -> str:
    """Canonical, reversible, Windows-safe encoding of a logical trial id.

    Single pass: every character outside ``[A-Za-z0-9.-]`` -- including ``_``
    itself -- is escaped as ``_xHH`` (lowercase hex).  Because a literal ``_``
    never survives, every ``_x`` in the output is a genuine escape, so
    decoding is unambiguous.  Reserved Windows device names and unsafe
    leading/trailing characters are handled by escaping the first character.
    The same logical id always maps to the same safe filename.
    """
    if not logical:
        raise PathSafetyError("empty logical id")
    out = "".join(_esc_char(c) for c in logical)
    stem = out.split(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED or out[0] == "." or out[-1] in ". ":
        # force-escape the first character (even a safe one) so the encoded
        # name can no longer collide with a reserved device name or an
        # unsafe leading/trailing character
        out = f"_x{ord(out[0]):02x}" + out[1:]
    if len(out) > MAX_SAFE_LEN:
        raise PathSafetyError(f"encoded id exceeds {MAX_SAFE_LEN} characters")
    return out


class PathSafetyError(ValueError):
    """A logical id cannot be encoded to a filesystem-safe canonical path."""


class FrozenArtifactError(RuntimeError):
    """A hash-locked preregistration artifact must not be overwritten."""


class ReplayError(RuntimeError):
    """A CONSUMED_INVALID trial (or its exact seed) may never be re-run."""

    # rule text pinned by the PI1VR0 taskbook (Sec. 8)
    RULE = ("if trial becomes CONSUMED_INVALID: same stage cannot rerun same "
            "state/rep; same exact seed cannot be reused; stage verdict must "
            "remain INVALID; deterministic replay does not override this rule")


FAULT_TAGS = (
    "BEFORE_START_LEDGER",
    "AFTER_START_BEFORE_SIM",
    "AFTER_SIM_BEFORE_TEMP",
    "AFTER_TEMP_BEFORE_FSYNC",
    "AFTER_FSYNC_BEFORE_VALIDATE",
    "AFTER_VALIDATE_BEFORE_RENAME",
    "AFTER_RENAME_BEFORE_DIRSYNC",
    "AFTER_DIRSYNC_BEFORE_COMPLETE",
)

FAULT_DESCRIPTIONS = {
    "BEFORE_START_LEDGER": "injected failure before the STARTED ledger entry",
    "AFTER_START_BEFORE_SIM": "injected failure after STARTED, before the simulator call",
    "AFTER_SIM_BEFORE_TEMP": "injected failure after the simulator, before temp write",
    "AFTER_TEMP_BEFORE_FSYNC": "injected failure after temp write, before fsync",
    "AFTER_FSYNC_BEFORE_VALIDATE": "injected failure after fsync, before schema validation",
    "AFTER_VALIDATE_BEFORE_RENAME": "injected failure after validation, before rename",
    "AFTER_RENAME_BEFORE_DIRSYNC": "injected failure after rename, before directory fsync",
    "AFTER_DIRSYNC_BEFORE_COMPLETE": "injected failure after dir fsync, before ledger COMPLETE",
}


def decode_fs_id(encoded: str) -> str:
    """Exact inverse of :func:`safe_fs_id`."""
    return ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), encoded)


def validate_safe_path(logical_id: str, final_path: str | os.PathLike) -> str:
    """Step 1 of the contract: validate the filesystem-safe trial id and path.

    The encoded logical id must be canonical and reversible; every path
    component (except a Windows drive root such as ``C:\\``) must be free of
    characters illegal on Windows.  Returns the encoded logical id.
    """
    encoded = safe_fs_id(logical_id)
    if decode_fs_id(encoded) != logical_id:
        raise PathSafetyError(f"encoding is not reversible for {logical_id!r}")
    if ":" in encoded:
        raise PathSafetyError(f"encoded id still contains ':': {encoded!r}")
    drive_re = re.compile(r"^[A-Za-z]:[\\/]?$")
    for part in Path(final_path).parts:
        if drive_re.match(part):
            continue
        if "::" in part or ":" in part or any(c in part for c in '*?"<>|'):
            raise PathSafetyError(f"illegal path component: {part!r}")
        if part in ("", ".."):
            raise PathSafetyError(f"illegal path component: {part!r}")
    return encoded


def assert_not_frozen(final_path: str | os.PathLike,
                      prereg_record: dict | None = None) -> None:
    """Frozen-artifact overwrite guard (taskbook Sec. 10).

    Refuses when the target file already exists, or when a preregistration
    hash record lists the path as hash-locked.  A new version requires a new
    stage or a versioned filename.
    """
    p = Path(final_path)
    if p.exists():
        raise FrozenArtifactError(
            f"refusing to overwrite existing frozen artifact: {p}")
    if prereg_record:
        rel = p.as_posix()
        for entry in prereg_record.get("files", []):
            ep = str(entry.get("path", ""))
            if ep and (ep == rel or rel.endswith("/" + ep)):
                raise FrozenArtifactError(
                    f"refusing to overwrite hash-locked prereg artifact: {ep}")


def ensure_not_started(ledger_path: str | os.PathLike, logical_id: str) -> None:
    """No-replay rule: the same state/rep identity may never re-start."""
    for e in ledger_entries(Path(ledger_path)):
        if e.get("state_id") == logical_id:
            raise ReplayError(
                f"trial identity {logical_id!r} already has a ledger entry; "
                f"no replay permitted. {ReplayError.RULE}")


def ensure_seed_unused(ledger_path: str | os.PathLike, seed: int) -> None:
    """No-replay rule: the same exact seed may never be reused."""
    for e in ledger_entries(Path(ledger_path)):
        if e.get("seed") == seed:
            raise ReplayError(
                f"seed {seed} is already consumed by a ledger entry; "
                f"no reuse permitted. {ReplayError.RULE}")


def trial_sha256(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "record_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def run_trial_transactional(
    logical_id: str,
    final_path: str | os.PathLike,
    run_simulator: Callable[[], dict],
    *,
    ledger_path: str | os.PathLike,
    validator: Callable[[dict], None],
    base_entry: dict[str, Any] | None = None,
    fault: str | None = None,
    run_uuid: str | None = None,
    clock: Callable[[], str] | None = None,
) -> dict:
    """Execute one trial under the frozen 12-step PI1VR0 contract.

    Order (taskbook Sec. 7): 1 validate safe id/path -> 2 durable STARTED ->
    3 simulator -> 4 temp serialization -> 5 flush -> 6 fsync(temp) ->
    7 schema validation -> 8 sha256 -> 9 atomic rename -> 10 parent-dir fsync
    -> 11 verify final hash -> 12 durable COMPLETE.  The simulator is never
    invoked before step 2.

    ``fault`` injects a failure at a named inter-step gap (synthetic
    verification only; real failures traverse the identical path).  Any
    failure appends a durable CONSUMED_INVALID entry; the returned
    classification carries ``status`` and the stage runner must abort (no
    replay of this state/rep or seed in the same stage).
    """
    final_path = Path(final_path)
    ledger_path = Path(ledger_path)
    now = clock or (lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    run_uuid = run_uuid or uuid.uuid4().hex
    extra = dict(base_entry or {})

    def fail(tag: str) -> None:
        if fault == tag:
            raise InjectedFault(f"injected failure {tag}: {FAULT_DESCRIPTIONS[tag]}")

    if fault and fault not in FAULT_TAGS:
        raise ValueError(f"unknown fault tag {fault!r}")

    # -- step 1: validate filesystem-safe trial id/path, and enforce the
    # no-replay rule: an identity with any prior ledger entry (COMPLETE or
    # CONSUMED_INVALID) may never be started again in the same stage --------
    encoded = validate_safe_path(logical_id, final_path)
    ensure_not_started(ledger_path, logical_id)
    if fault == "BEFORE_START_LEDGER":
        raise InjectedFault(FAULT_DESCRIPTIONS["BEFORE_START_LEDGER"])
    if final_path.exists():
        raise ReplayError(f"final record already exists for {logical_id!r}; "
                          f"no replay permitted")

    # -- step 2: durable STARTED ledger entry (BEFORE any simulator call) ----
    ledger_append(ledger_path, {"state_id": logical_id,
                                "safe_fs_id": encoded,
                                "expected_output_path": final_path.as_posix(),
                                "status": "STARTED",
                                "start_timestamp": now(), **extra})
    temp_path = final_path.parent / f".{encoded}.json.tmp.{run_uuid}"
    try:
        fail("AFTER_START_BEFORE_SIM")
        # -- step 3: scientific simulator (only ever reached after STARTED) --
        payload = run_simulator()
        fail("AFTER_SIM_BEFORE_TEMP")
        # -- steps 4-6: serialize, flush, fsync ------------------------------
        final_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
        with open(temp_path, "wb") as h:
            h.write(raw)
            h.flush()
            fail("AFTER_TEMP_BEFORE_FSYNC")
            os.fsync(h.fileno())
        fail("AFTER_FSYNC_BEFORE_VALIDATE")
        # -- step 7: schema validation ---------------------------------------
        validator(json.loads(temp_path.read_text(encoding="utf-8")))
        fail("AFTER_VALIDATE_BEFORE_RENAME")
        # -- step 8: sha256 ---------------------------------------------------
        digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()
        # -- step 9: atomic rename -------------------------------------------
        os.replace(temp_path, final_path)
        fail("AFTER_RENAME_BEFORE_DIRSYNC")
        # -- step 10: parent-directory fsync ---------------------------------
        dir_sync = fsync_directory(final_path.parent)
        if not dir_sync["pass"]:
            raise StatePersistenceError(
                f"parent directory fsync unavailable: {dir_sync}")
        # -- step 11: verify final hash --------------------------------------
        if hashlib.sha256(final_path.read_bytes()).hexdigest() != digest:
            raise StatePersistenceError("final hash mismatch after rename")
        fail("AFTER_DIRSYNC_BEFORE_COMPLETE")
        # -- step 12: durable COMPLETE ---------------------------------------
        ledger_append(ledger_path, {"state_id": logical_id,
                                    "status": "COMPLETE",
                                    "expected_output_path": final_path.as_posix(),
                                    "output_hash": digest,
                                    "final_sha256": digest,
                                    "finish_timestamp": now(), **extra})
        return {"logical_id": logical_id, "status": "COMPLETE",
                "final_exists": final_path.exists(), "final_sha256": digest,
                "temp_leftover": temp_path.exists()}
    except Exception as exc:
        ledger_append(ledger_path, {"state_id": logical_id,
                                    "status": "CONSUMED_INVALID",
                                    "reason": f"{type(exc).__name__}: {exc}",
                                    "finish_timestamp": now()})
        return {"logical_id": logical_id, "status": "CONSUMED_INVALID",
                "final_exists": final_path.exists(),
                "final_sha256": (hashlib.sha256(final_path.read_bytes()).hexdigest()
                                 if final_path.exists() else None),
                "temp_leftover": temp_path.exists(),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)}


class InjectedFault(RuntimeError):
    pass


class StatePersistenceError(RuntimeError):
    pass
