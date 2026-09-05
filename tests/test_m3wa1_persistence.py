"""M3-WA1 persistence contracts (taskbook Sec. 28) -- synthetic + incident."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402
from hyptraj.m3pi1vr0.persistence import (  # noqa: E402
    FrozenArtifactError,
    ReplayError,
    assert_not_frozen,
    ensure_not_started,
    run_trial_transactional,
    safe_fs_id,
    trial_sha256,
)

OUT = ROOT / "results/phase_m3wa1/summary"
REF = ROOT / "results/phase_m3wa1/reference"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_m3wa1_safe_path():
    for logical in ("cf1n_new_000_wa1_w_s2_1p788854382",
                    "a::1", "con::rep0"):
        enc = safe_fs_id(logical)
        assert ":" not in enc and "::" not in enc
    contract = load(OUT / "m3wa1_persistence_contract.json")
    assert contract["sequence"][0] == "validate safe path"
    assert contract["sequence"][1] == "durable STARTED"
    assert contract["sequence"][2] == "simulate"


def test_m3wa1_started_before_simulator(tmp_path):
    from hyptraj.m3cf1r0.persistence import ledger_entries as le
    observations = []

    def sim():
        observations.append(any(e.get("status") == "STARTED"
                                for e in le(tmp_path / "led.jsonl")))
        return {"schema": "m3wa1_reference_v1", "state_id": "x::0",
                "record_sha256": ""}

    def validate(rec):
        assert rec["schema"] == "m3wa1_reference_v1"

    rec = run_trial_transactional("x::0", tmp_path / "rec.json", sim,
                                  ledger_path=tmp_path / "led.jsonl",
                                  validator=validate, base_entry={"seed": 1})
    assert rec["status"] == "COMPLETE"
    assert observations == [True]


def test_m3wa1_atomic_persistence(tmp_path):
    def sim():
        payload = {"schema": "m3wa1_reference_v1", "state_id": "s::1", "k": 1}
        payload["record_sha256"] = trial_sha256(payload)
        return payload

    def validate(rec):
        assert trial_sha256(rec) == rec["record_sha256"]

    rec = run_trial_transactional("s::1", tmp_path / "s.json", sim,
                                  ledger_path=tmp_path / "led.jsonl",
                                  validator=validate)
    assert rec["status"] == "COMPLETE"
    assert hashlib.sha256((tmp_path / "s.json").read_bytes()).hexdigest() \
        == rec["final_sha256"]
    assert not list(tmp_path.glob(".*.tmp.*"))


def test_m3wa1_hash_verify():
    audit = load(OUT / "m3wa1_persistence_audit.json")
    assert audit["hashes"] == "FAIL"          # the incident is truthfully recorded
    forensics = load(OUT / "m3wa1_incident_forensics.json")
    assert "record_sha256" in " ".join(forensics["defect_and_fix"])
    # module-level hash verification still works on a synthetic record
    payload = {"schema": "m3wa1_reference_v1", "state_id": "h::0"}
    payload["record_sha256"] = trial_sha256(payload)
    assert trial_sha256(payload) == payload["record_sha256"]


def test_m3wa1_consumed_invalid_no_replay():
    entries = ledger_entries(REF / "reference_ledger.jsonl")
    statuses = [e["status"] for e in entries]
    assert statuses == ["STARTED", "CONSUMED_INVALID"]
    consumed_id = entries[0]["state_id"]
    forensics = load(OUT / "m3wa1_incident_forensics.json")
    assert forensics["no_replay_bookkeeping"]["consumed_trial_identity"] == consumed_id
    # the identity may never start again in this stage
    with pytest.raises(ReplayError):
        ensure_not_started(REF / "reference_ledger.jsonl", consumed_id)
    # and the script's own guard refuses any rerun of the stage
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_m3wa1 as W
    with pytest.raises(RuntimeError, match="no replay"):
        W._check_recoverable()


def test_m3wa1_no_frozen_overwrite():
    prereg = load(OUT / "m3wa1_prereg_hashes.json")
    import hashlib
    for e in prereg["files"]:
        p = ROOT / e["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]
    with pytest.raises(FrozenArtifactError):
        assert_not_frozen(ROOT / prereg["files"][0]["path"], prereg_record=prereg)
    # and the reference manifest records the sealed-invalid status
    rm = load(REF / "reference_manifest.json")
    assert rm["status"] == "INVALID_CONSUMED_INVALID"
    assert rm["scientific_use"] == "diagnostic only"
