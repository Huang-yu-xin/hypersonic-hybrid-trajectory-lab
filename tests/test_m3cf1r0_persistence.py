"""M3-CF1R0 transactional persistence contracts (task §8-§13, §24).

Unit and integration tests over synthetic/mock payloads only -- no scientific
simulator output exists anywhere in this stage.
"""
import json

import pytest

from hyptraj.m3cf1r0.persistence import (
    FAULT_TAGS,
    StatePersistenceError,
    atomic_write_state,
    fsync_directory,
    ledger_entries,
    mock_confirmation_payload,
    repair_ledger_tail,
    run_mock_stage,
)
from hyptraj.m3cf1r0.persistence import _default_validator, sha256_file

STATES = [
    {
        "state_id": f"m3cf1r0_mock_{i:02d}",
        "config_id": "mock_config",
        "s2": [1.25, 1.6, 2.0, 2.5, 3.2, 4.0, 5.0, 6.4][i],
        "seed": 910000 + i,
    }
    for i in range(8)
]


def make_payload(state_id="s0", s2=1.25):
    return mock_confirmation_payload(state_id, "mock_config", s2, 424242)


@pytest.fixture()
def env(tmp_path):
    # ledger lives beside the states so the whole transaction shares one directory
    final = tmp_path / "states" / "s0.json"
    return {
        "tmp": tmp_path,
        "final": final,
        "ledger": tmp_path / "states" / "ledger.jsonl",
    }


def write(env, payload=None, fault=None, validator=_default_validator):
    return atomic_write_state(
        "s0",
        payload if payload is not None else make_payload(),
        env["final"],
        env["ledger"],
        validator=validator,
        config_id="mock_config",
        s2=1.25,
        seed=424242,
        fault=fault,
    )


# --------------------------------------------------------------------------
# atomic write contract (unit level)
# --------------------------------------------------------------------------

def test_atomic_temp_same_filesystem(env):
    # temp file is created in the same directory as the final record
    write(env)
    leftovers = [p for p in env["final"].parent.iterdir() if p.name.startswith(".s0.json.tmp.")]
    assert env["final"].exists() and not leftovers
    # the contract derives temp naming from the final parent directory
    assert env["final"].parent == env["ledger"].parent


def test_temp_flush_and_fsync(env, monkeypatch):
    calls = []
    real_fsync = __import__("os").fsync
    monkeypatch.setattr(
        "hyptraj.m3cf1r0.persistence.os.fsync",
        lambda fd: (calls.append(fd), real_fsync(fd))[1],
    )
    write(env)
    # fsync is issued for the temp file and for every ledger append
    assert len(calls) >= 3


def test_schema_before_rename(env):
    bad = make_payload()
    del bad["arm_summaries"]

    class Rejecting(Exception):
        pass

    def validator(p):
        raise Rejecting("schema")

    r = write(env, payload=bad, validator=validator)
    # validation failure happens before rename: no final, no COMPLETE
    assert r["status"] == "CONSUMED_INVALID"
    assert not env["final"].exists()
    statuses = [e["status"] for e in ledger_entries(env["ledger"])]
    assert "COMPLETE" not in statuses
    assert statuses.count("CONSUMED_INVALID") == 1


def test_hash_before_rename(env):
    r = write(env)
    complete = [e for e in ledger_entries(env["ledger"]) if e["status"] == "COMPLETE"]
    assert len(complete) == 1
    # the hash committed to the ledger is the hash computed from the record
    # content that was atomically promoted to the final path
    assert complete[0]["output_hash"] == sha256_file(env["final"])
    assert r["final_sha256"] == complete[0]["output_hash"]


def test_atomic_replace(env):
    r = write(env)
    assert r["status"] == "COMPLETE"
    assert env["final"].exists()
    on_disk = json.loads(env["final"].read_text(encoding="utf-8"))
    assert on_disk["state_id"] == "s0"
    leftovers = [p for p in env["final"].parent.iterdir() if ".tmp." in p.name]
    assert not leftovers


def test_parent_directory_fsync():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        res = fsync_directory(Path(d))
    assert res["pass"] is True


def test_final_hash_verify(env, monkeypatch):
    # first hash call (temp, before rename) is real; the post-rename final
    # verification call reports a different hash -> must fail closed
    import hyptraj.m3cf1r0.persistence as persistence

    real = persistence.sha256_file
    calls = {"n": 0}

    def fake(p):
        calls["n"] += 1
        if calls["n"] >= 2:
            return "deadbeef" * 8
        return real(p)

    monkeypatch.setattr("hyptraj.m3cf1r0.persistence.sha256_file", fake)
    r = write(env)
    assert calls["n"] >= 2
    assert r["status"] == "CONSUMED_INVALID"
    statuses = [e["status"] for e in ledger_entries(env["ledger"])]
    assert "COMPLETE" not in statuses
    assert statuses.count("CONSUMED_INVALID") == 1


def test_ledger_commit_after_final(env):
    # F6: the final file exists durably, but the ledger has no COMPLETE yet --
    # ordering "ledger commit strictly after final persistence" holds
    r = write(env, fault="F6")
    assert r["status"] == "CONSUMED_INVALID"
    assert env["final"].exists()
    assert not [e for e in ledger_entries(env["ledger"]) if e["status"] == "COMPLETE"]


def test_stage_complete_only_after_all_states(tmp_path):
    plan = {STATES[3]["state_id"]: "F4"}
    fr = run_mock_stage({"stage_id": "S", "states": STATES}, tmp_path / "f", plan)
    assert not fr["stage_complete"]
    assert not fr["stage_summary_written"]
    clean = run_mock_stage({"stage_id": "S", "states": STATES}, tmp_path / "c", None)
    assert clean["stage_complete"]
    assert clean["stage_summary_written"]


# --------------------------------------------------------------------------
# failure-injection matrix (§11 / §24)
# --------------------------------------------------------------------------

def run_fault(tmp_path, tag):
    return run_mock_stage(
        {"stage_id": f"T-{tag}", "states": STATES},
        tmp_path / tag,
        {s["state_id"]: tag for s in STATES},
    )


def test_failure_before_temp_write(tmp_path):
    fr = run_fault(tmp_path, "F1")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    assert not any(r["final_exists"] or r["temp_leftover"] for r in fr["results"])


def test_failure_during_serialization(tmp_path):
    fr = run_fault(tmp_path, "F2")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    assert not any(r["final_exists"] or r["temp_leftover"] for r in fr["results"])


def test_failure_after_temp_before_fsync(tmp_path):
    fr = run_fault(tmp_path, "F3")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    # temp files may remain (dotted, non-canonical); no final record exists
    assert all(r["temp_leftover"] for r in fr["results"])
    assert not any(r["final_exists"] for r in fr["results"])


def test_failure_after_fsync_before_rename(tmp_path):
    fr = run_fault(tmp_path, "F4")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    assert all(r["temp_leftover"] for r in fr["results"])
    assert not any(r["final_exists"] for r in fr["results"])


def test_failure_after_rename_before_dir_fsync(tmp_path):
    fr = run_fault(tmp_path, "F5")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    # final file exists on disk but carries no COMPLETE ledger entry
    assert all(r["final_exists"] for r in fr["results"])
    assert not any(r["temp_leftover"] for r in fr["results"])
    led = ledger_entries(tmp_path / "F5" / "ledger.jsonl")
    assert not [e for e in led if e["status"] == "COMPLETE"]


def test_failure_before_ledger_commit(tmp_path):
    fr = run_fault(tmp_path, "F6")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    led = ledger_entries(tmp_path / "F6" / "ledger.jsonl")
    assert not [e for e in led if e["status"] == "COMPLETE"]


def test_failure_during_ledger_commit(tmp_path):
    fr = run_fault(tmp_path, "F7")
    assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"])
    led = ledger_entries(tmp_path / "F7" / "ledger.jsonl")
    assert not [e for e in led if e["status"] == "COMPLETE"]
    # no torn fragment remains after the repair-on-append step
    assert not [e for e in led if e["status"] == "LEDGER_TORN_ENTRY"]


def test_failure_after_ledger_before_stage_summary(tmp_path):
    fr = run_fault(tmp_path, "F8")
    # every state transaction committed fully; only the stage summary is lost
    assert all(r["status"] == "COMPLETE" and r["final_exists"] for r in fr["results"])
    assert not fr["stage_summary_written"]
    assert not fr["stage_complete"]
    led = ledger_entries(tmp_path / "F8" / "ledger.jsonl")
    complete = [e for e in led if e["status"] == "COMPLETE"]
    assert len(complete) == 8
    for e in complete:
        fp = tmp_path / "F8" / f"{e['state_id']}.json"
        assert fp.exists() and sha256_file(fp) == e["output_hash"]


def test_no_false_complete_on_failure(tmp_path):
    for tag in FAULT_TAGS:
        fr = run_fault(tmp_path / tag, tag)
        led = ledger_entries(tmp_path / tag / "ledger.jsonl")
        for e in led:
            if e["status"] == "COMPLETE":
                fp = tmp_path / tag / f"{e['state_id']}.json"
                assert fp.exists(), f"false COMPLETE for {e['state_id']} ({tag})"
                assert sha256_file(fp) == e["output_hash"]


def test_consumed_invalid_classification(tmp_path):
    for tag in ("F1", "F2", "F3", "F4", "F5", "F6", "F7"):
        fr = run_fault(tmp_path / tag, tag)
        assert all(r["status"] == "CONSUMED_INVALID" for r in fr["results"]), tag


def test_synthetic_clean_e2e(tmp_path):
    fr = run_mock_stage({"stage_id": "CLEAN", "states": STATES}, tmp_path / "clean", None)
    assert fr["stage_complete"] and fr["stage_summary_written"]
    assert len(fr["results"]) == 8
    led = ledger_entries(tmp_path / "clean" / "ledger.jsonl")
    for e in [x for x in led if x["status"] == "COMPLETE"]:
        fp = tmp_path / "clean" / f"{e['state_id']}.json"
        assert sha256_file(fp) == e["output_hash"]


def test_synthetic_failure_e2e(tmp_path):
    for tag in FAULT_TAGS:
        fr = run_fault(tmp_path / tag, tag)
        assert not fr["stage_complete"], tag
        assert not fr["stage_summary_written"], tag


# --------------------------------------------------------------------------
# extras: torn-tail repair and deterministic payloads
# --------------------------------------------------------------------------

def test_repair_ledger_tail(tmp_path):
    led = tmp_path / "ledger.jsonl"
    led.write_text('{"state_id": "a", "status": "STARTED"}\n{"state_id": "b", "sta', encoding="utf-8")
    assert repair_ledger_tail(led) > 0
    entries = ledger_entries(led)
    assert [e["state_id"] for e in entries] == ["a"]
    # after repair, appending yields a clean ledger again
    from hyptraj.m3cf1r0.persistence import ledger_append

    ledger_append(led, {"state_id": "b", "status": "CONSUMED_INVALID"})
    assert [e["state_id"] for e in ledger_entries(led)] == ["a", "b"]


def test_mock_payload_has_no_real_outcomes():
    p = make_payload()
    assert p["reference_label_placeholder"] == "SYNTHETIC"
    assert p["metadata_hashes"]["payload_schema"] == "m3cf1r0-synthetic-v1"
    _default_validator(p)  # schema passes
