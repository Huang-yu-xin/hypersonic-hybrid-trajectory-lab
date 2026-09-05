"""M3-PI1VR0 persistence contracts (taskbook Sec. 29) -- synthetic only."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hyptraj.m3pi1vr0.persistence import (  # noqa: E402
    FAULT_TAGS,
    FrozenArtifactError,
    PathSafetyError,
    ReplayError,
    assert_not_frozen,
    decode_fs_id,
    ensure_not_started,
    ensure_seed_unused,
    run_trial_transactional,
    safe_fs_id,
)

OUT = ROOT / "results/phase_m3pi1vr0/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def mock_payload(state_id, seed):
    return {"schema": "m3pi1vr0_synthetic_v1", "state_id": state_id, "seed": seed,
            "arm_summaries": {"placeholder": True},
            "note": "mock payload; no scientific sampling"}


def validate_mock(rec):
    required = {"schema", "state_id", "seed", "arm_summaries", "note"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["state_id"].startswith("bad"):
        raise ValueError("schema validation failed; deliberately invalid record")


def read_ledger(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def test_m3pi1vr0_safe_trial_path():
    for logical in ("state::rep0", "c000_sf2_map3_s2_4p5177271546::rep0",
                    "a::1", "con_x::2", ".hidden::3", "state_1::rep7"):
        enc = safe_fs_id(logical)
        assert ":" not in enc and "::" not in enc          # no ':' in filenames
        assert decode_fs_id(enc) == logical                 # reversible
        assert safe_fs_id(logical) == enc                   # canonical/stable
    assert safe_fs_id("a::1") == safe_fs_id("a::1")
    assert "/" not in safe_fs_id("a/b::0")
    for bad in ("", "x" * 300):
        with pytest.raises(PathSafetyError):
            safe_fs_id(bad)
    # reserved Windows names are neutralized by first-char escaping
    for reserved in ("CON", "con.txt", "NUL", "COM1"):
        enc = safe_fs_id(reserved)
        assert enc.split(".")[0].upper() not in {"CON", "PRN", "AUX", "NUL",
                                                 "COM1", "LPT1"}
        assert decode_fs_id(enc) == reserved


def test_m3pi1vr0_started_before_simulator(tmp_path):
    from hyptraj.m3cf1r0.persistence import ledger_entries

    ledger = tmp_path / "ledger.jsonl"
    observations = []

    def sim():
        # the simulator must observe a durable STARTED entry for its own trial
        observations.append(any(e.get("status") == "STARTED" and
                                e.get("state_id") == "t::rep0"
                                for e in ledger_entries(ledger)))
        return mock_payload("t::rep0", 7)

    rec = run_trial_transactional("t::rep0", tmp_path / "rec.json", sim,
                                  ledger_path=ledger, validator=validate_mock,
                                  base_entry={"seed": 7})
    assert rec["status"] == "COMPLETE"
    assert observations == [True]        # the simulator saw STARTED already
    entries = read_ledger(ledger)
    statuses = [e["status"] for e in entries if e["state_id"] == "t::rep0"]
    assert statuses.index("STARTED") < statuses.index("COMPLETE")


def test_m3pi1vr0_atomic_persistence(tmp_path):
    import hashlib
    ledger = tmp_path / "ledger.jsonl"
    final = tmp_path / "rec.json"
    rec = run_trial_transactional("st_1::rep3", final,
                                  lambda: mock_payload("st_1::rep3", 11),
                                  ledger_path=ledger, validator=validate_mock,
                                  base_entry={"seed": 11})
    assert rec["status"] == "COMPLETE"
    assert final.exists()
    assert hashlib.sha256(final.read_bytes()).hexdigest() == rec["final_sha256"]
    assert not rec["temp_leftover"]
    assert not list(tmp_path.glob(".*.tmp.*"))
    complete = [e for e in read_ledger(ledger) if e["status"] == "COMPLETE"]
    assert complete and complete[0]["final_sha256"] == rec["final_sha256"]
    # the logical id is unchanged in the record body; only the path is encoded
    body = json.loads(final.read_text(encoding="utf-8"))
    assert body["state_id"] == "st_1::rep3"


def test_m3pi1vr0_consumed_invalid_no_replay(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    rec = run_trial_transactional("x::rep0", tmp_path / "x.json",
                                  lambda: mock_payload("x::rep0", 5),
                                  ledger_path=ledger, validator=validate_mock,
                                  base_entry={"seed": 5}, fault="AFTER_SIM_BEFORE_TEMP")
    assert rec["status"] == "CONSUMED_INVALID"
    entries = read_ledger(ledger)
    assert [e["status"] for e in entries] == ["STARTED", "CONSUMED_INVALID"]
    # no-replay: same identity and same exact seed are refused
    with pytest.raises(ReplayError):
        ensure_not_started(ledger, "x::rep0")
    with pytest.raises(ReplayError):
        ensure_seed_unused(ledger, 5)
    # deterministic replay does not override the rule: re-running the same
    # identity through the transactional runner is also refused
    with pytest.raises(ReplayError):
        run_trial_transactional("x::rep0", tmp_path / "x.json",
                                lambda: mock_payload("x::rep0", 5),
                                ledger_path=ledger, validator=validate_mock,
                                base_entry={"seed": 5})


def test_m3pi1vr0_frozen_artifact_rewrite_refused(tmp_path):
    existing = tmp_path / "frozen.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(FrozenArtifactError):
        assert_not_frozen(existing)
    prereg = {"files": [{"path": "locked/artifact.json", "sha256": "x"}]}
    with pytest.raises(FrozenArtifactError):
        assert_not_frozen(tmp_path / "locked/artifact.json", prereg_record=prereg)
    # a fresh, unlocked path is allowed
    assert_not_frozen(tmp_path / "other.json", prereg_record=prereg)


def test_m3pi1vr0_failure_injection(tmp_path):
    for tag in FAULT_TAGS:
        led = tmp_path / f"led_{tag}.jsonl"
        final = tmp_path / f"inj_{tag}" / "rec.json"
        if tag == "BEFORE_START_LEDGER":
            # failure before STARTED: the trial never began; nothing consumed
            with pytest.raises(Exception):
                run_trial_transactional("s::rep0", final,
                                        lambda: mock_payload("s::rep0", 1),
                                        ledger_path=led, validator=validate_mock,
                                        fault=tag)
            assert not led.exists() or all(
                e["state_id"] != "s::rep0" for e in read_ledger(led))
            continue
        rec = run_trial_transactional("s::rep0", final,
                                      lambda: mock_payload("s::rep0", 1),
                                      ledger_path=led, validator=validate_mock,
                                      fault=tag)
        assert rec["status"] == "CONSUMED_INVALID", tag
        statuses = [e["status"] for e in read_ledger(led)]
        assert statuses == ["STARTED", "CONSUMED_INVALID"], tag
        if tag in ("AFTER_RENAME_BEFORE_DIRSYNC", "AFTER_DIRSYNC_BEFORE_COMPLETE"):
            assert final.exists()       # post-rename: final exists, no COMPLETE
        else:
            assert not final.exists()


def test_m3pi1vr0_synthetic_e2e(tmp_path):
    ledger = tmp_path / "e2e.jsonl"
    d = tmp_path / "e2e"
    for i in range(8):
        lid = f"e2e_state_{i}::rep{i % 3}"
        rec = run_trial_transactional(lid, d / f"{safe_fs_id(lid)}.json",
                                      lambda l=lid, s=100 + i: mock_payload(l, s),
                                      ledger_path=ledger, validator=validate_mock,
                                      base_entry={"seed": 100 + i})
        assert rec["status"] == "COMPLETE"
    entries = read_ledger(ledger)
    complete = [e for e in entries if e["status"] == "COMPLETE"]
    assert len(complete) == 8
    for e in complete:
        assert (tmp_path / Path(e["expected_output_path"]).name).exists() or \
            Path(e["expected_output_path"]).exists()
    assert not list(d.glob(".*.tmp.*"))
    # the committed synthetic gate artifacts corroborate the same behaviors
    inj = load(OUT / "m3pi1vr0_failure_injection.json")
    assert all(inj["assertions"].values())
    assert inj["payloads"].startswith("mock only")
    e2e = load(OUT / "m3pi1vr0_synthetic_e2e.json")
    assert e2e["all_complete"] and e2e["output_hash_match"]
    assert e2e["started_before_simulator_pass"]
    assert all(e2e["no_replay_refusals"].values())
    assert all(e2e["frozen_artifact_guard_refusals"].values())
