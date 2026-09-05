"""M3-WA1R hardened persistence -- non-circular hash contract (taskbook Sec. 9/10/23).

Repairs the exact WA1 defect: WA1's schema validator required a record
self-hash field before the frozen sequence had written it.  The WA1R
transactional order never requires a self-hash during schema validation:

    1.  safe path validation (+ no-replay / overwrite guards)
    2.  durable STARTED ledger entry
    3.  simulator  ->  canonical scientific payload WITHOUT any hash field
    4.  schema validation on the PRE-HASH schema (must not require
        scientific_payload_hash -- the WA1 bug class is structurally impossible)
    5.  compute frozen hash fields:
            scientific_payload_hash = sha256(canonical scientific payload
                                             excluding the hash field itself)
    6.  temp write of the final bytes (payload + hash field), flush, fsync
    7.  atomic rename
    8.  parent-directory fsync
    9.  verify durable final hashes:
            record_file_hash      = sha256(final serialized record bytes)
            scientific_payload_hash re-verified non-circularly from the file
    10. ledger COMPLETE carrying both hashes

Never is the final file required to contain its own full-file SHA-256 inside
the bytes being hashed.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from hyptraj.m3cf1r0.persistence import fsync_directory, ledger_append, ledger_entries
from hyptraj.m3pi1vr0.persistence import (
    PathSafetyError,
    ReplayError,
    StatePersistenceError,
    validate_safe_path,
)

__all__ = [
    "InjectedFault",
    "FAULT_TAGS",
    "scientific_payload_hash",
    "record_file_hash",
    "run_trial_transactional",
    "ensure_not_started",
    "ensure_seed_unused",
    "assert_not_frozen",
]

HASH_FIELD = "scientific_payload_hash"


class InjectedFault(RuntimeError):
    pass


FAULT_TAGS = (
    "BEFORE_START_LEDGER",
    "AFTER_START_BEFORE_SIM",
    "AFTER_SIM_BEFORE_VALIDATE",
    "AFTER_VALIDATE_BEFORE_HASH",
    "AFTER_HASH_BEFORE_TEMP",
    "AFTER_TEMP_BEFORE_FSYNC",
    "AFTER_FSYNC_BEFORE_RENAME",
    "AFTER_RENAME_BEFORE_DIRSYNC",
    "AFTER_DIRSYNC_BEFORE_VERIFY",
    "AFTER_VERIFY_BEFORE_COMPLETE",
)

FAULT_DESCRIPTIONS = {
    "BEFORE_START_LEDGER": "injected failure before the STARTED ledger entry",
    "AFTER_START_BEFORE_SIM": "injected failure after STARTED, before the simulator call",
    "AFTER_SIM_BEFORE_VALIDATE": "injected failure after the simulator, before pre-hash schema validation",
    "AFTER_VALIDATE_BEFORE_HASH": "injected failure after pre-hash validation, before hash computation (the repaired step)",
    "AFTER_HASH_BEFORE_TEMP": "injected failure after hash computation, before temp write",
    "AFTER_TEMP_BEFORE_FSYNC": "injected failure after temp write, before fsync",
    "AFTER_FSYNC_BEFORE_RENAME": "injected failure after fsync, before rename",
    "AFTER_RENAME_BEFORE_DIRSYNC": "injected failure after rename, before directory fsync",
    "AFTER_DIRSYNC_BEFORE_VERIFY": "injected failure after directory fsync, before final hash verification",
    "AFTER_VERIFY_BEFORE_COMPLETE": "injected failure after verification, before ledger COMPLETE",
}


def scientific_payload_hash(payload: dict) -> str:
    """sha256 of the canonical scientific payload excluding the hash field.

    Non-circular by construction: the hashed bytes never contain the hash
    field itself, and never the full serialized file.
    """
    body = {k: v for k, v in payload.items() if k != HASH_FIELD}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def record_file_hash(path: Path) -> str:
    """sha256 of the final serialized record bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ensure_not_started(ledger_path: str | os.PathLike, logical_id: str) -> None:
    for e in ledger_entries(Path(ledger_path)):
        if e.get("state_id") == logical_id:
            raise ReplayError(
                f"trial identity {logical_id!r} already has a ledger entry; "
                "no replay permitted (taskbook Sec. 24)")


def ensure_seed_unused(ledger_path: str | os.PathLike, seed: int) -> None:
    for e in ledger_entries(Path(ledger_path)):
        if e.get("seed") == seed:
            raise ReplayError(f"seed {seed} already consumed; no reuse permitted")


def assert_not_frozen(final_path: str | os.PathLike,
                      prereg_record: dict | None = None) -> None:
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


class FrozenArtifactError(RuntimeError):
    pass


def run_trial_transactional(
    logical_id: str,
    final_path: str | os.PathLike,
    run_simulator: Callable[[], dict],
    *,
    ledger_path: str | os.PathLike,
    pre_hash_validator: Callable[[dict], None],
    base_entry: dict[str, Any] | None = None,
    fault: str | None = None,
    run_uuid: str | None = None,
    clock: Callable[[], str] | None = None,
) -> dict:
    """Execute one trial under the frozen M3-WA1R 12-step contract (Sec. 23)."""
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

    # -- 1. safe path validation + guards -------------------------------------
    encoded = validate_safe_path(logical_id, final_path)
    ensure_not_started(ledger_path, logical_id)
    if fault == "BEFORE_START_LEDGER":
        raise InjectedFault(FAULT_DESCRIPTIONS["BEFORE_START_LEDGER"])
    if final_path.exists():
        raise ReplayError(f"final record already exists for {logical_id!r}")

    # -- 2. durable STARTED ledger (before any simulator call) ----------------
    ledger_append(ledger_path, {"state_id": logical_id, "safe_fs_id": encoded,
                                "expected_output_path": final_path.as_posix(),
                                "status": "STARTED", "start_timestamp": now(),
                                **extra})
    temp_path = final_path.parent / f".{encoded}.json.tmp.{run_uuid}"
    try:
        fail("AFTER_START_BEFORE_SIM")
        # -- 3. simulator -> canonical scientific payload (no hash field) -----
        payload = run_simulator()
        if HASH_FIELD in payload:
            raise StatePersistenceError(
                "simulator payload must not carry a self-hash field")
        fail("AFTER_SIM_BEFORE_VALIDATE")
        # -- 4. schema validation on the PRE-HASH schema ----------------------
        #     the validator never sees (and must never require) a self-hash
        pre_hash_validator(payload)
        fail("AFTER_VALIDATE_BEFORE_HASH")
        # -- 5. compute frozen hash fields (non-circular) ---------------------
        s_hash = scientific_payload_hash(payload)
        payload[HASH_FIELD] = s_hash
        fail("AFTER_HASH_BEFORE_TEMP")
        # -- 6. temp write of the final bytes, flush, fsync -------------------
        final_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
        with open(temp_path, "wb") as h:
            h.write(raw)
            h.flush()
            fail("AFTER_TEMP_BEFORE_FSYNC")
            os.fsync(h.fileno())
        fail("AFTER_FSYNC_BEFORE_RENAME")
        # -- 7. atomic rename -------------------------------------------------
        os.replace(temp_path, final_path)
        fail("AFTER_RENAME_BEFORE_DIRSYNC")
        # -- 8. parent-directory fsync ----------------------------------------
        dir_sync = fsync_directory(final_path.parent)
        if not dir_sync["pass"]:
            raise StatePersistenceError(f"parent-directory fsync unavailable: {dir_sync}")
        fail("AFTER_DIRSYNC_BEFORE_VERIFY")
        # -- 9. verify durable final hashes -----------------------------------
        f_hash = record_file_hash(final_path)
        stored = json.loads(final_path.read_text(encoding="utf-8"))
        if scientific_payload_hash(stored) != stored[HASH_FIELD] \
                or stored[HASH_FIELD] != s_hash:
            raise StatePersistenceError("scientific payload hash mismatch after rename")
        fail("AFTER_VERIFY_BEFORE_COMPLETE")
        # -- 10. ledger COMPLETE ----------------------------------------------
        ledger_append(ledger_path, {"state_id": logical_id,
                                    "status": "COMPLETE",
                                    "expected_output_path": final_path.as_posix(),
                                    "record_file_hash": f_hash,
                                    "scientific_payload_hash": s_hash,
                                    "finish_timestamp": now(), **extra})
        return {"logical_id": logical_id, "status": "COMPLETE",
                "record_file_hash": f_hash, "scientific_payload_hash": s_hash,
                "temp_leftover": temp_path.exists()}
    except Exception as exc:
        ledger_append(ledger_path, {"state_id": logical_id,
                                    "status": "CONSUMED_INVALID",
                                    "reason": f"{type(exc).__name__}: {exc}",
                                    "finish_timestamp": now()})
        return {"logical_id": logical_id, "status": "CONSUMED_INVALID",
                "final_exists": final_path.exists(),
                "temp_leftover": temp_path.exists(),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)}
