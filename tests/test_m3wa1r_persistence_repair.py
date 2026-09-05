"""M3-WA1R persistence-repair contracts (taskbook Sec. 45) -- synthetic only."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    HASH_FIELD,
    FAULT_TAGS,
    FrozenArtifactError,
    ReplayError,
    assert_not_frozen,
    ensure_not_started,
    record_file_hash,
    run_trial_transactional,
    scientific_payload_hash,
)

OUT = ROOT / "results/phase_m3wa1r/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def mock_payload(state_id, s):
    return {"schema": "m3wa1r_reference_v1", "state_id": state_id, "seed_int": s,
            "arms": {"placeholder": True}, "note": "mock; no scientific sampling"}


def pre_hash_validate(rec):
    required = {"schema", "state_id", "arms", "note"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if HASH_FIELD in rec:
        raise ValueError("pre-hash schema must not contain a self-hash field")


def test_m3wa1r_safe_path(tmp_path):
    # a path built from the safe encoding of a logical id is accepted
    rec = run_trial_transactional("st_1::rep0", tmp_path / "rec.json",
                                  lambda: mock_payload("st_1::rep0", 3),
                                  ledger_path=tmp_path / "led.jsonl",
                                  pre_hash_validator=pre_hash_validate)
    assert rec["status"] == "COMPLETE"
    contract = load(OUT / "m3wa1r_persistence_contract.json")
    assert contract["mandatory_order"][0] == "1. safe path"
    assert contract["mandatory_order"][1] == "2. durable STARTED"
    assert contract["mandatory_order"][2] == "3. simulate"


def test_m3wa1r_started_before_simulator(tmp_path):
    observations = []

    def sim():
        observations.append(any(e.get("status") == "STARTED"
                                for e in ledger_entries(tmp_path / "led.jsonl")))
        return mock_payload("t::rep0", 7)

    rec = run_trial_transactional("t::rep0", tmp_path / "rec.json", sim,
                                  ledger_path=tmp_path / "led.jsonl",
                                  pre_hash_validator=pre_hash_validate)
    assert rec["status"] == "COMPLETE" and observations == [True]
    statuses = [e["status"] for e in ledger_entries(tmp_path / "led.jsonl")]
    assert statuses == ["STARTED", "COMPLETE"]


def test_m3wa1r_non_circular_hash_contract(tmp_path):
    rec = run_trial_transactional("h::rep0", tmp_path / "rec.json",
                                  lambda: mock_payload("h::rep0", 9),
                                  ledger_path=tmp_path / "led.jsonl",
                                  pre_hash_validator=pre_hash_validate)
    stored = json.loads((tmp_path / "rec.json").read_text(encoding="utf-8"))
    assert HASH_FIELD in stored
    # non-circular: the stored hash equals the hash of the payload minus the field
    assert scientific_payload_hash(stored) == stored[HASH_FIELD] == rec["scientific_payload_hash"]
    # and the file hash is the hash of the full serialized bytes (kept OUT of
    # the hashed payload bytes)
    assert record_file_hash(tmp_path / "rec.json") == rec["record_file_hash"]
    contract = load(OUT / "m3wa1r_hash_contract.json")
    assert "excluding the scientific_payload_hash field" in contract["scientific_payload_hash"]
    assert "never" in contract["non_circular_guarantee"]


def test_m3wa1r_schema_before_hash_contract_valid(tmp_path):
    # the pre-hash validator accepts a hash-less payload (the WA1 bug class:
    # requiring a self-hash during pre-hash validation is structurally impossible)
    payload = mock_payload("pre::rep0", 1)
    assert HASH_FIELD not in payload
    pre_hash_validate(payload)                       # must not raise
    # and the transactional runner rejects a payload that smuggles a self-hash
    def smuggle():
        p = mock_payload("pre::rep0", 1)
        p[HASH_FIELD] = "0" * 64
        return p
    rec = run_trial_transactional("pre::rep0", tmp_path / "pre.json", smuggle,
                                  ledger_path=tmp_path / "led2.jsonl",
                                  pre_hash_validator=pre_hash_validate)
    assert rec["status"] == "CONSUMED_INVALID"
    assert "self-hash" in rec["exception_message"]


def test_m3wa1r_atomic_persistence(tmp_path):
    import hashlib
    rec = run_trial_transactional("a::rep1", tmp_path / "a.json",
                                  lambda: mock_payload("a::rep1", 5),
                                  ledger_path=tmp_path / "led.jsonl",
                                  pre_hash_validator=pre_hash_validate)
    assert rec["status"] == "COMPLETE"
    assert hashlib.sha256((tmp_path / "a.json").read_bytes()).hexdigest() \
        == rec["record_file_hash"]
    assert not list(tmp_path.glob(".*.tmp.*"))
    complete = [e for e in ledger_entries(tmp_path / "led.jsonl")
                if e["status"] == "COMPLETE"]
    assert complete[0]["record_file_hash"] == rec["record_file_hash"]


def test_m3wa1r_bug_regression():
    doc = load(OUT / "m3wa1r_synthetic_bug_regression.json")
    assert doc["repaired_happy_path"]["status"] == "COMPLETE"
    assert doc["repaired_happy_path"]["non_circular_hash_verified"] is True
    assert all(doc["assertions"].values())
    assert doc["payloads"].startswith("mock only")
    # every post-START injection point yields CONSUMED_INVALID and never COMPLETE
    for inj in doc["failure_injection"]:
        if inj["fault"] == "BEFORE_START_LEDGER":
            continue
        assert inj["consumed_invalid"] == 1 and inj["complete"] == 0


def test_m3wa1r_consumed_invalid_no_replay(tmp_path):
    rec = run_trial_transactional("x::rep0", tmp_path / "x.json",
                                  lambda: mock_payload("x::rep0", 5),
                                  ledger_path=tmp_path / "led.jsonl",
                                  pre_hash_validator=pre_hash_validate,
                                  fault="AFTER_SIM_BEFORE_VALIDATE")
    assert rec["status"] == "CONSUMED_INVALID"
    with pytest.raises(ReplayError):
        ensure_not_started(tmp_path / "led.jsonl", "x::rep0")
    with pytest.raises(ReplayError):
        run_trial_transactional("x::rep0", tmp_path / "x.json",
                                lambda: mock_payload("x::rep0", 5),
                                ledger_path=tmp_path / "led.jsonl",
                                pre_hash_validator=pre_hash_validate)
    statuses = [e["status"] for e in ledger_entries(tmp_path / "led.jsonl")]
    assert statuses == ["STARTED", "CONSUMED_INVALID"]


def test_m3wa1r_frozen_overwrite_guard(tmp_path):
    existing = tmp_path / "frozen.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(FrozenArtifactError):
        assert_not_frozen(existing)
    prereg = load(OUT / "m3wa1r_prereg_hashes.json")
    with pytest.raises(FrozenArtifactError):
        assert_not_frozen(ROOT / prereg["files"][0]["path"], prereg_record=prereg)
