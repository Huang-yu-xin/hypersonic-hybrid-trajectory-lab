"""M3-CF1R0 quarantine contracts (task §24 quarantine test list).

CF1R0 is a zero-simulator recovery stage after CF1-X.  These tests pin the
quarantine, taxonomy, retirement, and protected-confirmation invariants of
the frozen recovery artifacts.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3cf1r0/summary"
DOC = ROOT / "docs/phase_m3cf1r0"


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_m3cf1r0_parent_cf1x():
    assert j("m3cf1r0_cf1_scientific_status.json")["CF1_final_verdict"] == "CF1-X"
    assert json.loads(
        (ROOT / "results/phase_m3cf1/summary/m3cf1_final_verdict.json").read_text(encoding="utf-8")
    )["verdict"] == "CF1-X"


def test_m3cf1r0_zero_simulator():
    v = j("m3cf1r0_final_verdict.json")
    assert v["simulator_samples"] == 0
    assert v["new_reference_states"] == 0


def test_m3cf1r0_cf1_verdict_immutable():
    s = j("m3cf1r0_cf1_scientific_status.json")
    assert s["CF1_primary_structural_result"] == "UNAVAILABLE"
    # CF1's own verdict record is untouched
    parent = json.loads(
        (ROOT / "results/phase_m3cf1/summary/m3cf1_final_verdict.json").read_text(encoding="utf-8")
    )
    assert parent["status"] == "INVALID"
    assert parent["rerun_authorized"] is False


def test_m3cf1r0_no_cf1_rerun():
    s = j("m3cf1r0_cf1_scientific_status.json")
    assert s["CF1_rerun_permitted"] == "NO"
    assert s["CF1_confirmation_reusable_as_untouched"] == "NO"
    assert s["CF1_eight_configs_reusable_for_replacement_primary_evidence"] == "NO"


def test_m3cf1r0_all_cf1_configs_retired():
    r = j("m3cf1r0_retired_state_seed_manifest.json")
    assert len(r["configs_retired"]) == 8
    assert len(set(r["configs_retired"])) == 8
    q = j("m3cf1r0_cf1_quarantine_manifest.json")["items"]
    retired_ids = {i["id"] for i in q if i["id"].startswith("config:")}
    assert retired_ids == {f"config:{c}" for c in r["configs_retired"]}


def test_m3cf1r0_all_cf1_states_classified():
    q = j("m3cf1r0_cf1_quarantine_manifest.json")["items"]
    states = [i for i in q if i["id"].startswith("discovery_state:")]
    confirmations = [i for i in q if i["id"].startswith("confirmation_state:")]
    assert len(states) == 72
    assert len(confirmations) == 45
    assert all(i["status"] == "DISCOVERY_PERSISTED" for i in states)
    assert all(i["status"] == "CONFIRMATION_COMPUTED_NOT_PERSISTED" for i in confirmations)
    for i in q:
        assert set(i) >= {"id", "path", "sha256_if_available", "status", "scientific_use", "reason"}
        assert sum(1 for s in (
            "PREREG_VALID",
            "DISCOVERY_PERSISTED",
            "CONFIRMATION_PERSISTED_COMPLETE",
            "CONFIRMATION_COMPUTED_NOT_PERSISTED",
            "PARTIAL_OR_CORRUPT",
            "LOG_ONLY_OR_EPHEMERAL",
        ) if i["status"] == s) == 1


def test_m3cf1r0_all_cf1_seeds_retired():
    r = j("m3cf1r0_retired_state_seed_manifest.json")
    assert r["discovery_seeds_retired"]["namespace"] == "M3-CF1-DISCOVERY"
    assert r["confirmation_seeds_retired"]["namespace"] == "M3-CF1-CONFIRM"
    assert r["p_ref_streams_retired"]["namespace"] == "M3-CF1-PREF"
    assert r["p_ref_streams_retired"]["count"] == 8
    assert r["scientific_use"].startswith("historical diagnostics only")
    assert len(r["discovery_states_retired"]) == 72
    assert len(r["confirmation_states_consumed_invalid"]) == 45


def test_m3cf1r0_no_log_outcome_reconstruction():
    f = j("m3cf1r0_persistence_failure_forensics.json")
    assert f["outcome_reconstruction_performed"] is False
    # unprovable fields stay UNKNOWN, never guessed
    assert f["root_cause"] == "UNKNOWN"
    assert f["failing_command"].startswith("UNKNOWN")
    assert f["failing_function"].startswith("UNKNOWN")


def test_m3cf1r0_no_protected_confirmation():
    a = j("m3cf1r0_protected_confirmation_audit.json")
    assert a["UC2R_protected_confirmation_pilot_trials"] == 0
    assert a["gradient_pilot_trials"] == 0
    assert a["finite_action_probe_trials"] == 0
    assert a["threshold"] is None
    assert a["value"] == "BLOCKED"
    assert a["rarity_shift"] == "BLOCKED"
    assert a["m3_q"] == "BLOCKED"
