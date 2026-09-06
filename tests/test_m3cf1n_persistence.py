"""M3-CF1N hardened persistence contracts (taskbook §3, §10, §24, §42).

Synthetic payloads only; exercises the CF1N firewall on top of the frozen
CF1R0 transactional contract.
"""
import json

import pytest

from hyptraj.m3cf1n.persistence import (
    PREF_VALIDATOR,
    StatePersistenceError,
    ledger_statuses,
    scientific_write,
    stage_persistence_audit,
    verify_stage_complete,
)
from hyptraj.m3cf1r0.persistence import ledger_entries, sha256_file


def pref_payload(state_id="pcfg", s2_seed=424242):
    return {
        "record_type": "M3CF1N-PREF",
        "config_id": state_id,
        "namespace": "M3-CF1N-PREF",
        "seed_key": [s2_seed, 991],
        "sample_count": 500_000,
        "n_batches": 20,
        "p_ref_full": 0.01,
        "p_ref_full_SE": 0.0001,
        "p_ref_full_CI": [0.0098, 0.0102],
        "p_batches": [0.01] * 20,
        "topology_counts": {"S0": 495000, "S1": 5000},
        "event_semantics_schema_version": 2,
        "protocol_hash": "SYNTH",
    }


def write(env, payload=None, fault=None, validator=PREF_VALIDATOR, state_id="pcfg"):
    from hyptraj.m3cf1r0.persistence import atomic_write_state

    func = scientific_write if fault != "__direct__" else atomic_write_state
    return func(
        state_id,
        payload if payload is not None else pref_payload(state_id),
        env["final"],
        env["ledger"],
        validator=validator,
        config_id=state_id,
        protocol_hash="SYNTH",
        seed_namespace="M3-CF1N-PREF",
        seed=424242,
        fault=None if fault == "__direct__" else fault,
    )


@pytest.fixture()
def env(tmp_path):
    return {
        "tmp": tmp_path,
        "final": tmp_path / "records" / "pcfg.json",
        "ledger": tmp_path / "records" / "ledger.jsonl",
    }


def test_m3cf1n_write_ahead_ledger_before_sim(env):
    write(env)
    entries = ledger_entries(env["ledger"])
    statuses = [e["status"] for e in entries]
    # the durable STARTED entry precedes any COMPLETE entry
    assert statuses.index("STARTED") < statuses.index("COMPLETE")
    started = [e for e in entries if e["status"] == "STARTED"][0]
    assert started["seed_namespace"] == "M3-CF1N-PREF"
    assert started["expected_output_path"] == str(env["final"])


def test_m3cf1n_temp_same_filesystem(env):
    write(env)
    leftovers = [p for p in env["final"].parent.iterdir() if ".tmp." in p.name]
    assert env["final"].exists() and not leftovers


def test_m3cf1n_flush_fsync(env, monkeypatch):
    import os

    calls = []
    real = os.fsync
    monkeypatch.setattr(
        "hyptraj.m3cf1r0.persistence.os.fsync",
        lambda fd: (calls.append(fd), real(fd))[1],
    )
    write(env)
    assert len(calls) >= 3  # temp file + ledger appends


def test_m3cf1n_schema_before_commit(env):
    bad = pref_payload()
    del bad["p_ref_full"]

    def rejecting(_payload):
        raise ValueError("schema")

    r = write(env, payload=bad, validator=rejecting)
    assert r["status"] == "CONSUMED_INVALID"
    assert not env["final"].exists()
    assert "COMPLETE" not in [e["status"] for e in ledger_entries(env["ledger"])]


def test_m3cf1n_hash_before_commit(env):
    r = write(env)
    complete = [e for e in ledger_entries(env["ledger"]) if e["status"] == "COMPLETE"]
    assert len(complete) == 1
    assert complete[0]["output_hash"] == sha256_file(env["final"])
    assert r["final_sha256"] == complete[0]["output_hash"]


def test_m3cf1n_atomic_replace(env):
    write(env)
    on_disk = json.loads(env["final"].read_text(encoding="utf-8"))
    assert on_disk["config_id"] == "pcfg"
    assert not [p for p in env["final"].parent.iterdir() if ".tmp." in p.name]


def test_m3cf1n_parent_directory_fsync():
    import tempfile
    from pathlib import Path

    from hyptraj.m3cf1r0.persistence import fsync_directory

    with tempfile.TemporaryDirectory() as d:
        assert fsync_directory(Path(d))["pass"] is True


def test_m3cf1n_final_hash_verify(env, monkeypatch):
    import hyptraj.m3cf1r0.persistence as persistence

    real = persistence.sha256_file
    calls = {"n": 0}

    def fake(p):
        calls["n"] += 1
        return real(p) if calls["n"] < 2 else "deadbeef" * 8

    monkeypatch.setattr("hyptraj.m3cf1r0.persistence.sha256_file", fake)
    r = write(env)
    assert r["status"] == "CONSUMED_INVALID"
    assert "COMPLETE" not in [e["status"] for e in ledger_entries(env["ledger"])]


def test_m3cf1n_ledger_complete_after_hash(env):
    # COMPLETE entry carries the verified final hash and follows the final file
    r = write(env)
    assert r["status"] == "COMPLETE"
    entry = [e for e in ledger_entries(env["ledger"]) if e["status"] == "COMPLETE"][0]
    assert entry["output_hash"] == sha256_file(env["final"])


def test_m3cf1n_no_overwrite_complete(env):
    write(env)
    with pytest.raises(StatePersistenceError, match="overwrite"):
        write(env)


def test_m3cf1n_stage_complete_requires_all_records(env):
    write(env, state_id="pcfg")
    # a second expected record was never written
    audit = stage_persistence_audit(env["final"].parent, env["ledger"], ["pcfg", "pcfg2"])
    with pytest.raises(StatePersistenceError, match="incomplete"):
        verify_stage_complete(["pcfg", "pcfg2"], audit)
    ok = stage_persistence_audit(env["final"].parent, env["ledger"], ["pcfg"])
    verify_stage_complete(["pcfg"], ok)


def test_m3cf1n_consumed_invalid_on_failure(env):
    r = write(env, fault="F4")
    assert r["status"] == "CONSUMED_INVALID"
    assert ledger_statuses(env["ledger"])["pcfg"] == ["STARTED", "CONSUMED_INVALID"]


def test_m3cf1n_no_rerun_consumed_invalid(env):
    write(env, fault="F4")
    with pytest.raises(StatePersistenceError, match="CONSUMED_INVALID"):
        write(env)


def test_m3cf1n_no_log_reconstruction(env):
    # canonical records carry canonical hashes only; no stdout/stderr/log-file
    # fields exist anywhere in the schema
    write(env)
    payload = json.loads(env["final"].read_text(encoding="utf-8"))
    assert not any("stdout" in k or "stderr" in k for k in payload)
    assert payload["protocol_hash"] == "SYNTH"
