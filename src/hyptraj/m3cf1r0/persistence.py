"""Transactional persistence contract for M3-CF1R0 (task §8, §9, §10, §11).

Contract for every future scientific state write::

    durable PRE-RUN ledger entry (STARTED)
    -> serialize canonical record to temp file (same filesystem)
    -> flush + fsync(temp)
    -> schema validate temp
    -> sha256(temp)
    -> atomic os.replace(temp, final)
    -> fsync(parent directory)
    -> verify final hash
    -> durable ledger COMPLETE entry

If calculation completes but durable canonical persistence fails, the ledger
records ``CONSUMED_INVALID`` -- never ``READY_FOR_RERUN`` in confirmatory
stages ("computed but not durably persisted != untouched").

This module is infrastructure only.  It never invokes the simulator and never
touches scientific outcomes; CF1R0 uses it exclusively with synthetic/mock
payloads.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

FAULT_TAGS = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")

FAULT_DESCRIPTIONS = {
    "F1": "before temp write",
    "F2": "during serialization",
    "F3": "after temp write before fsync",
    "F4": "after fsync before rename",
    "F5": "after rename before directory fsync",
    "F6": "after final file before ledger commit",
    "F7": "during ledger commit",
    "F8": "after ledger commit before stage summary",
}


class StatePersistenceError(RuntimeError):
    """Raised when a transactional state write fails (real or injected)."""


# --------------------------------------------------------------------------
# Durable primitives
# --------------------------------------------------------------------------

def _win32_flush_directory(path: str) -> None:
    """Flush a directory handle on Windows via FlushFileBuffers.

    os.fsync() cannot be applied to a directory descriptor on Windows
    (os.open on a directory fails with PermissionError).  The documented Win32
    equivalent is CreateFileW with FILE_FLAG_BACKUP_SEMANTICS followed by
    FlushFileBuffers.  This is a real flush request to the operating system,
    not an emulated success.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    generic_read = 0x80000000
    generic_write = 0x40000000
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    invalid_handle_value = ctypes.c_void_p(-1).value
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateFileW(
        path,
        generic_read | generic_write,
        0,
        None,
        open_existing,
        file_flag_backup_semantics,
        None,
    )
    if handle is None or handle == invalid_handle_value:
        raise OSError(ctypes.get_last_error(), "CreateFileW(directory) failed")
    try:
        if not kernel32.FlushFileBuffers(handle):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers(directory) failed")
    finally:
        kernel32.CloseHandle(handle)


def fsync_directory(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Durably flush a directory entry; report the platform capability truthfully.

    POSIX path: ``os.open(dir, O_RDONLY)`` + ``os.fsync(fd)``.
    Windows path: CreateFileW(FILE_FLAG_BACKUP_SEMANTICS) + FlushFileBuffers.
    Success is never emulated; failures surface as ``pass: false`` with the
    real exception type and message.
    """
    p = str(path)
    posix_error: OSError | None = None
    try:
        fd = os.open(p, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {"pass": True, "method": "os.fsync(directory fd)"}
    except OSError as e:  # pragma: no cover - platform dependent
        posix_error = e
    if sys.platform == "win32":
        try:
            _win32_flush_directory(p)
            return {"pass": True, "method": "FlushFileBuffers(FILE_FLAG_BACKUP_SEMANTICS)"}
        except OSError as e:
            return {
                "pass": False,
                "method": "FlushFileBuffers(FILE_FLAG_BACKUP_SEMANTICS)",
                "exception_type": type(e).__name__,
                "exception_message": str(e),
            }
    assert posix_error is not None
    return {
        "pass": False,
        "method": "os.fsync(directory fd)",
        "exception_type": type(posix_error).__name__,
        "exception_message": str(posix_error),
    }


# --------------------------------------------------------------------------
# A2R bounded retry for parent-directory fsync (taskbook Sec. A2R §8)
# --------------------------------------------------------------------------

# Frozen deterministic backoff schedule (seconds).  The schedule is
# frozen before authorization and may not be tuned at runtime.
DIR_FSYNC_BACKOFF = (0.0, 0.01, 0.05, 0.15, 0.30)
DIR_FSYNC_MAX_ATTEMPTS = 5

# Windows transient error codes that justify a retry of the directory
# durability operation only (never the simulator).
#   32 = ERROR_SHARING_VIOLATION (antivirus / search indexer handle)
#   33 = ERROR_LOCK_VIOLATION
_WIN32_TRANSIENT_ERRNOS = (32, 33)


def _is_transient_fsync_failure(result: dict[str, Any]) -> bool:
    """True if an ``fsync_directory`` failure is worth retrying (transient
    Windows sharing/locking errors).  Non-transient failures are not
    retried (the fail-closed policy still declares CONSUMED_INVALID)."""
    if result.get("pass"):
        return False
    msg = str(result.get("exception_message", ""))
    etype = str(result.get("exception_type", ""))
    for code in _WIN32_TRANSIENT_ERRNOS:
        if f"[Errno {code}]" in msg:
            return True
    # BrokenPipeError is how Python surfaces Windows error 32 via
    # ctypes.get_last_error(); retry it as a transient sharing violation.
    if "BrokenPipeError" in etype:
        return True
    return False


def fsync_directory_bounded_retry(
        path: str | os.PathLike[str],
        max_attempts: int = DIR_FSYNC_MAX_ATTEMPTS,
        backoff: tuple[float, ...] = DIR_FSYNC_BACKOFF,
        sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Bounded retry for parent-directory fsync (A2R-only).

    Retries **ONLY** the directory durability operation on the SAME
    already-written / already-renamed artifact.  It NEVER reruns the
    simulator, regenerates the scientific payload, regenerates bootstrap
    samples, or changes any record/sidecar bytes.  After all attempts are
    exhausted, returns ``pass: False`` (=> CONSUMED_INVALID =>
    M3-S25-R1-A2R-X => STOP => NO REPLAY).

    The backoff schedule is frozen and deterministic (no randomness,
    no adaptive tuning).
    """
    _sleep = sleep_fn or time.sleep
    last_result: dict[str, Any] = {}
    for attempt in range(max_attempts):
        if attempt > 0:
            _sleep(backoff[min(attempt, len(backoff) - 1)])
        last_result = fsync_directory(path)
        if last_result.get("pass"):
            return {**last_result, "attempts": attempt + 1}
        if not _is_transient_fsync_failure(last_result):
            return {**last_result, "attempts": attempt + 1,
                    "retry_stopped": "non-transient"}
    return {**last_result, "attempts": max_attempts,
            "retry_stopped": "max_attempts_exhausted"}


def repair_ledger_tail(ledger_path: Path) -> int:
    """Drop a torn (unterminated) trailing ledger fragment before appending.

    Returns the number of bytes truncated (0 when the tail is clean).
    """
    if not ledger_path.exists():
        return 0
    raw = ledger_path.read_bytes()
    if not raw or raw.endswith(b"\n"):
        return 0
    cut = raw.rfind(b"\n") + 1
    with open(ledger_path, "r+b") as h:
        h.truncate(cut)
        h.flush()
        os.fsync(h.fileno())
    return len(raw) - cut


def ledger_append(ledger_path: Path, entry: dict[str, Any]) -> None:
    """Append one durable JSONL ledger entry (flush + fsync)."""
    repair_ledger_tail(ledger_path)
    line = json.dumps(entry, sort_keys=True) + "\n"
    with open(ledger_path, "a", encoding="utf-8") as h:
        h.write(line)
        h.flush()
        os.fsync(h.fileno())


def ledger_entries(ledger_path: Path) -> list[dict[str, Any]]:
    """Read all ledger entries; a torn tail becomes a LEDGER_TORN_ENTRY marker."""
    try:
        raw = Path(ledger_path).read_bytes()
    except FileNotFoundError:
        return []
    entries: list[dict[str, Any]] = []
    for line in raw.decode("utf-8").split("\n"):
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"status": "LEDGER_TORN_ENTRY", "raw_fragment": line})
    return entries


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Synthetic payloads (task §7)
# --------------------------------------------------------------------------

def mock_confirmation_payload(
    state_id: str,
    config_id: str,
    s2: float,
    seed: int,
    *,
    reference_label_placeholder: str = "SYNTHETIC",
) -> dict[str, Any]:
    """Build a synthetic confirmation record (placeholder fields only).

    Contains no real scientific simulator output.
    """
    return {
        "state_id": state_id,
        "config_id": config_id,
        "s2": s2,
        "seed": seed,
        "arm_summaries": {
            "base": {"placeholder": True},
            "widen": {"placeholder": True},
            "shrink": {"placeholder": True},
        },
        "paired_statistics": {"placeholder": True},
        "reference_label_placeholder": reference_label_placeholder,
        "metadata_hashes": {"payload_schema": "m3cf1r0-synthetic-v1"},
    }


# --------------------------------------------------------------------------
# Transactional state write (task §8/§10)
# --------------------------------------------------------------------------

def atomic_write_state(
    state_id: str,
    payload: dict[str, Any],
    final_path: Path,
    ledger_path: Path,
    *,
    validator: Callable[[dict[str, Any]], None],
    config_id: str = "",
    s2: float | None = None,
    protocol_hash: str = "",
    seed_namespace: str = "",
    seed: int | None = None,
    fault: str | None = None,
    run_uuid: str | None = None,
    clock: Callable[[], str] | None = None,
    ledger_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one state record under the full transactional contract.

    ``fault`` names an injection point in ``FAULT_TAGS`` used by the
    failure-injection matrix; every other failure path is identical to a real
    failure.  ``ledger_extra`` carries optional static context (e.g.
    grid_index, P_ref_hash) merged into both ledger entries.  Returns a
    deterministic classification dict.
    """
    final_path = Path(final_path)
    ledger_path = Path(ledger_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    run_uuid = run_uuid or uuid.uuid4().hex
    now = clock or (lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    temp_path = final_path.parent / f".{state_id}.json.tmp.{run_uuid}"
    extra = dict(ledger_extra or {})

    def fail(tag: str) -> None:
        if fault == tag:
            raise StatePersistenceError(f"injected failure {tag}: {FAULT_DESCRIPTIONS[tag]}")

    start_ts = now()
    ledger_append(
        ledger_path,
        {
            "state_id": state_id,
            "config_id": config_id,
            "s2": s2,
            "protocol_hash": protocol_hash,
            "seed_namespace": seed_namespace,
            "seed": seed,
            "expected_output_path": str(final_path),
            "status": "STARTED",
            "start_timestamp": start_ts,
            "started_at": start_ts,
            **extra,
        },
    )
    try:
        fail("F1")

        def serialize() -> bytes:
            fail("F2")
            return json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")

        raw = serialize()
        with open(temp_path, "wb") as h:
            h.write(raw)
            h.flush()
            fail("F3")
            os.fsync(h.fileno())
        validator(json.loads(temp_path.read_text(encoding="utf-8")))
        digest = sha256_file(temp_path)
        fail("F4")
        os.replace(temp_path, final_path)
        fail("F5")
        dir_sync = fsync_directory(final_path.parent)
        if not dir_sync["pass"]:
            raise StatePersistenceError(
                f"parent directory fsync unavailable: {dir_sync.get('exception_type')}"
            )
        if sha256_file(final_path) != digest:
            raise StatePersistenceError("final hash mismatch after replace")
        fail("F6")

        def commit_ledger_complete() -> None:
            fail("F7")
            finish_ts = now()
            ledger_append(
                ledger_path,
                {
                    "state_id": state_id,
                    "status": "COMPLETE",
                    "output_hash": digest,
                    "finish_timestamp": finish_ts,
                    "completed_at": finish_ts,
                    "final_sha256": digest,
                    **extra,
                },
            )

        commit_ledger_complete()
        # F8 ("after ledger commit before stage summary") is a STAGE-level
        # fault handled by run_mock_stage; the state transaction itself is
        # fully committed here and must remain COMPLETE.
        return {
            "state_id": state_id,
            "status": "COMPLETE",
            "final_exists": final_path.exists(),
            "final_sha256": digest,
            "temp_leftover": temp_path.exists(),
            "directory_fsync": dir_sync,
        }
    except Exception as exc:
        ledger_append(
            ledger_path,
            {
                "state_id": state_id,
                "status": "CONSUMED_INVALID",
                "reason": f"{type(exc).__name__}: {exc}",
                "finish_timestamp": now(),
            },
        )
        return {
            "state_id": state_id,
            "status": "CONSUMED_INVALID",
            "final_exists": final_path.exists(),
            "final_sha256": sha256_file(final_path) if final_path.exists() else None,
            "temp_leftover": temp_path.exists(),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }


def _default_validator(payload: dict[str, Any]) -> None:
    required = {
        "state_id",
        "config_id",
        "s2",
        "seed",
        "arm_summaries",
        "paired_statistics",
        "reference_label_placeholder",
        "metadata_hashes",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"schema validation failed; missing fields: {sorted(missing)}")
    if payload["state_id"] == "":
        raise ValueError("schema validation failed; empty state_id")


# --------------------------------------------------------------------------
# Mock stage runner (task §12: 8-state synthetic end-to-end dry run)
# --------------------------------------------------------------------------

def run_mock_stage(
    spec: dict[str, Any],
    out_dir: Path,
    fault_plan: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    """Run a synthetic multi-state stage through the full persistence system.

    ``spec`` provides ``stage_id`` and ``states`` (each with ``state_id``,
    ``config_id``, ``s2``, ``seed``).  The runner writes a durable run
    manifest, per-state transactional records under ``out_dir``, a write-ahead
    ledger, and a stage completion summary only when every required state
    record is durably complete.  ``fault_plan`` maps state_id -> fault tag
    (or a single tag applied to all states).

    No scientific simulator sampling occurs anywhere in this function.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "ledger.jsonl"
    manifest_path = out_dir / "run_manifest.json"
    stage_id = spec["stage_id"]
    states = spec["states"]
    run_uuid = uuid.uuid4().hex

    manifest = {
        "stage_id": stage_id,
        "synthetic": True,
        "simulator_samples": 0,
        "run_uuid": run_uuid,
        "states": [
            {
                "state_id": s["state_id"],
                "config_id": s["config_id"],
                "s2": s["s2"],
                "seed": s["seed"],
                "expected_output_path": str(out_dir / f"{s['state_id']}.json"),
            }
            for s in states
        ],
    }
    with open(manifest_path, "wb") as h:
        h.write(json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8"))
        h.flush()
        os.fsync(h.fileno())

    if fault_plan is None:
        faults: dict[str, str] = {}
    elif isinstance(fault_plan, str):
        faults = {s["state_id"]: fault_plan for s in states}
    else:
        faults = dict(fault_plan)

    results = []
    stage_fault_applied: str | None = None
    for s in states:
        payload = mock_confirmation_payload(s["state_id"], s["config_id"], s["s2"], s["seed"])
        state_fault = faults.get(s["state_id"])
        if state_fault == "F8":
            # F8 is a stage-level fault: every state transaction commits
            # normally, but the stage summary is never written.
            stage_fault_applied = "F8"
            state_fault = None
        res = atomic_write_state(
            s["state_id"],
            payload,
            out_dir / f"{s['state_id']}.json",
            ledger_path,
            validator=_default_validator,
            config_id=s["config_id"],
            s2=s["s2"],
            protocol_hash=s.get("protocol_hash", "SYNTHETIC-PROTOCOL"),
            seed_namespace=s.get("seed_namespace", "SYNTHETIC"),
            seed=s["seed"],
            fault=state_fault,
            run_uuid=run_uuid,
        )
        results.append(res)

    all_complete = all(r["status"] == "COMPLETE" for r in results) and stage_fault_applied is None
    stage_summary_path = out_dir / "stage_summary.json"
    stage_summary = {
        "stage_id": stage_id,
        "synthetic": True,
        "states_total": len(states),
        "states_complete": sum(r["status"] == "COMPLETE" for r in results),
        "stage_complete": all_complete,
    }
    if all_complete:
        with open(stage_summary_path, "wb") as h:
            h.write(json.dumps(stage_summary, sort_keys=True, indent=2).encode("utf-8"))
            h.flush()
            os.fsync(h.fileno())

    return {
        "stage_id": stage_id,
        "results": results,
        "stage_complete": all_complete,
        "stage_fault": stage_fault_applied,
        "stage_summary_written": stage_summary_path.exists(),
        "ledger_path": str(ledger_path),
        "manifest_path": str(manifest_path),
    }
