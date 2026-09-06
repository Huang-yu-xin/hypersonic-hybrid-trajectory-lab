"""M3-CF1N stage contracts: P_ref, discovery, confirmation (taskbook §42).

Tests that require simulator-stage outputs skip cleanly until the
corresponding approval-gated stage has actually run (the stage status lives
in results/phase_m3cf1n/run_manifest.json).
"""
import csv
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "phase_m3cf1n"
OUT = RES / "summary"
CFG = ROOT / "configs" / "phase_m3cf1n"
PREF = RES / "pref"
DISC = RES / "discovery"
CONF = RES / "confirmation"
CF1_CFG = ROOT / "configs" / "phase_m3cf1"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def stage_status() -> str:
    path = RES / "run_manifest.json"
    if not path.exists():
        return "PREPARE"
    return load(path).get("stage_status", "PREPARE")


def require_stage(*statuses):
    current = stage_status()
    if current not in statuses:
        pytest.skip(f"stage gate: requires {statuses}, currently {current}")


def pref_ran() -> bool:
    return stage_status() in (
        "PREF_COMPLETE_AWAITING_DISCOVERY_EXECUTION",
        "DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL",
        "COMPLETE",
    )


def discovery_ran() -> bool:
    return stage_status() in (
        "DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL",
        "COMPLETE",
    )


# --------------------------------------------------------------------------
# P_ref (§42 P_ref list)
# --------------------------------------------------------------------------

def test_m3cf1n_new_pref_per_config():
    require_stage("PREF_COMPLETE_AWAITING_DISCOVERY_EXECUTION",
                  "DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL", "COMPLETE")
    configs = load(OUT / "m3cf1n_config_manifest.json")["config_ids"]
    records = [load(PREF / f"{cid}.json") for cid in configs]
    assert len(records) == 8
    assert {r["config_id"] for r in records} == set(configs)


def test_m3cf1n_pref_namespace_new():
    protocol = load(OUT / "m3cf1n_pref_protocol.json")
    assert protocol["namespace"] == "M3-CF1N-PREF"
    assert protocol["CF1_P_ref_reuse"] is False
    cf1_pref = load(CF1_CFG / "m3cf1_discovery_seeds.json")["p_ref_namespace"]
    assert cf1_pref == "M3-CF1-PREF" != protocol["namespace"]


def test_m3cf1n_pref_count8():
    protocol = load(OUT / "m3cf1n_pref_protocol.json")
    assert protocol["configs"] == 8
    assert len(load(OUT / "m3cf1n_pref_seeds.json")["p_ref"]) == 8


def test_m3cf1n_pref_budget():
    protocol = load(OUT / "m3cf1n_pref_protocol.json")
    assert protocol["samples_per_config"] == 500_000
    assert protocol["expected_samples"] == 4_000_000


def test_m3cf1n_pref_persistence():
    require_stage("PREF_COMPLETE_AWAITING_DISCOVERY_EXECUTION",
                  "DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL", "COMPLETE")
    audit = load(OUT / "m3cf1n_pref_persistence_audit.json")
    assert audit["complete"] == 8
    assert audit["consumed_invalid"] == 0
    assert audit["hash_failures"] == []
    summary = load(OUT / "m3cf1n_pref_summary.json")
    assert summary["total_samples"] == 4_000_000
    # ledger COMPLETE entries carry hashes that still match the records
    for entry in [e for e in load_ledger(PREF / "pref_ledger.jsonl") if e["status"] == "COMPLETE"]:
        assert sha256_of(PREF / f"{entry['state_id']}.json") == entry["output_hash"]


def load_ledger(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Discovery (§42 discovery list)
# --------------------------------------------------------------------------

def test_m3cf1n_exact72_states():
    states = csv_rows(OUT / "m3cf1n_discovery_states.csv")
    assert len(states) == 72
    configs = load(OUT / "m3cf1n_config_manifest.json")["config_ids"]
    assert {r["config_id"] for r in states} == set(configs)
    for cid in configs:
        per_config = [r for r in states if r["config_id"] == cid]
        assert sorted(int(r["grid_index"]) for r in per_config) == list(range(1, 10))
        assert [float(r["s2"]) for r in sorted(per_config, key=lambda r: int(r["grid_index"]))] == \
            load(OUT / "m3cf1n_common_s2_grid.json")["values"]


def test_m3cf1n_discovery_budget_100k():
    assert load(OUT / "m3cf1n_discovery_protocol.json")["samples_per_arm"] == 100_000
    assert load(OUT / "m3cf1n_discovery_protocol.json")["finite_action_samples"] == 21_600_000


def test_m3cf1n_discovery_3arms():
    assert load(OUT / "m3cf1n_discovery_protocol.json")["arms"] == ["base", "widen", "shrink"]


def test_m3cf1n_discovery_crn20():
    assert load(OUT / "m3cf1n_discovery_protocol.json")["paired_crn_batches"] == 20


def test_m3cf1n_event_semantics_v2():
    protocol = load(OUT / "m3cf1n_discovery_protocol.json")
    assert protocol["event_semantics_schema_version"] == 2
    assert protocol["event"] == "topology != S0"
    assert protocol["probability_domain"] == "full-event probability"


def test_m3cf1n_classifier_thresholds_unchanged():
    cf1 = load(CF1_CFG / "m3cf1_discovery_protocol.json")
    cf1n = load(OUT / "m3cf1n_discovery_protocol.json")
    for key in ("improvement_threshold", "hold_band", "direction_margin", "min_arm_ess",
                "event", "event_semantics_schema_version", "probability_domain",
                "samples_per_arm", "paired_crn_batches", "arms"):
        assert cf1n[key] == cf1[key], key


def test_m3cf1n_discovery_seed_disjoint():
    cf1_keys = set()
    for name in ("m3cf1_discovery_seeds.json", "m3cf1_confirmation_seeds.json"):
        rec = load(CF1_CFG / name)
        for item in rec.get("finite_action", []):
            cf1_keys.add(int(item["seed_key"][0]))
        for item in rec.get("p_ref", []):
            cf1_keys.add(int(item["seed_key"][0]))
    new_keys = {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_discovery_seeds.json")["finite_action"]}
    new_keys |= {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_confirmation_seeds.json")["finite_action"]}
    new_keys |= {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_pref_seeds.json")["p_ref"]}
    assert not (new_keys & cf1_keys)


def test_m3cf1n_all72_complete_before_eligibility():
    require_stage("DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL", "COMPLETE")
    audit = load(OUT / "m3cf1n_discovery_persistence_audit.json")
    assert audit["complete"] == 72
    assert audit["consumed_invalid"] == 0
    assert audit["hash_failures"] == []
    states = csv_rows(OUT / "m3cf1n_discovery_states.csv")
    for r in states:
        assert (DISC / f"{r['state_id']}.json").exists()


def test_m3cf1n_adjacent_prov_s_rule():
    require_stage("DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL", "COMPLETE")
    eligibility = load(OUT / "m3cf1n_discovery_eligibility.json")
    for cid, rec in eligibility["by_config"].items():
        pattern = rec["provisional_pattern"]
        expected = any(
            pattern[i] == pattern[i + 1] == "PROV_SHRINK" for i in range(len(pattern) - 1)
        )
        assert rec["eligible"] == expected, cid


def test_m3cf1n_no_effect_ranking():
    assert load(OUT / "m3cf1n_discovery_protocol.json")["adaptive_refinement"] is False
    require_stage("DISCOVERY_COMPLETE_AWAITING_CONFIRMATION_APPROVAL", "COMPLETE")
    assert load(OUT / "m3cf1n_discovery_eligibility.json")["effect_size_ranking_used"] is False


def test_m3cf1n_no_grid_refinement():
    protocol = load(OUT / "m3cf1n_discovery_protocol.json")
    assert protocol["grid_refinement"] is False
    # the grid is still bit-identical to the CF0 freeze
    grid = load(OUT / "m3cf1n_common_s2_grid.json")
    assert grid["source_sha256"] == sha(ROOT / "results/phase_m3cf0/summary/m3cf0_future_s2_grid.json")
    assert grid["hash_matches_cf0"] is True


# --------------------------------------------------------------------------
# Confirmation (§42 confirmation list)
# --------------------------------------------------------------------------

def confirmation_ran() -> bool:
    manifest = RES / "run_manifest.json"
    if not manifest.exists():
        return False
    m = load(manifest)
    return m.get("stage_status") == "COMPLETE" and m.get("final_verdict") not in (
        None, "CF1N-DISC-C", "CF1N-X"
    )


def test_m3cf1n_confirm_only_eligible_configs():
    require_stage("COMPLETE")
    manifest = load(RES / "run_manifest.json")
    if manifest["final_verdict"] == "CF1N-DISC-C":
        pytest.skip("no eligible configs; confirmation correctly not run")
    eligibility = load(OUT / "m3cf1n_discovery_eligibility.json")
    confirmed_configs = {r["config_id"] for r in csv_rows(OUT / "m3cf1n_discovery_confirmation_transition.csv")}
    assert confirmed_configs == set(eligibility["eligible_config_ids"])


def test_m3cf1n_confirm_all9_states():
    require_stage("COMPLETE")
    manifest = load(RES / "run_manifest.json")
    if manifest["final_verdict"] == "CF1N-DISC-C":
        pytest.skip("no eligible configs; confirmation correctly not run")
    transition = csv_rows(OUT / "m3cf1n_discovery_confirmation_transition.csv")
    for row in transition:
        assert len(row["confirmation_pattern"].split("|")) == 9
    audit = load(OUT / "m3cf1n_confirmation_persistence_audit.json")
    assert audit["complete"] == 9 * len(transition)


def test_m3cf1n_confirmation_budget_500k():
    protocol = load(OUT / "m3cf1n_confirmation_protocol.json")
    assert protocol["samples_per_arm"] == 500_000
    assert protocol["finite_action_samples_per_eligible_config"] == 13_500_000
    assert protocol["maximum_finite_action_samples"] == 108_000_000


def test_m3cf1n_confirmation_crn20():
    assert load(OUT / "m3cf1n_confirmation_protocol.json")["paired_crn_batches"] == 20


def test_m3cf1n_confirmation_seed_disjoint():
    disc = {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_discovery_seeds.json")["finite_action"]}
    conf = {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_confirmation_seeds.json")["finite_action"]}
    pref = {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_pref_seeds.json")["p_ref"]}
    assert not (conf & disc) and not (conf & pref) and not (disc & pref)


def test_m3cf1n_no_new_confirm_states():
    protocol = load(OUT / "m3cf1n_confirmation_protocol.json")
    assert protocol["no_new_states"] is True
    assert protocol["confirm_all_nine_frozen_states_per_eligible_config"] is True
    require_stage("COMPLETE")
    manifest = load(RES / "run_manifest.json")
    if manifest["final_verdict"] == "CF1N-DISC-C":
        pytest.skip("no eligible configs; confirmation correctly not run")
    frozen_ids = {r["state_id"] for r in csv_rows(OUT / "m3cf1n_discovery_states.csv")}
    confirmed_ids = {p.stem for p in (RES / "confirmation").glob("cf1n_new_*.json")}
    # every confirmed state id must be one of the 72 frozen discovery states
    assert confirmed_ids <= frozen_ids


def test_m3cf1n_all_confirm_records_complete():
    require_stage("COMPLETE")
    manifest = load(RES / "run_manifest.json")
    if manifest["final_verdict"] == "CF1N-DISC-C":
        pytest.skip("no eligible configs; confirmation correctly not run")
    audit = load(OUT / "m3cf1n_confirmation_persistence_audit.json")
    assert audit["consumed_invalid"] == 0
    assert audit["hash_failures"] == []
    assert audit["complete"] == audit["expected"]


def test_m3cf1n_new_stable_adjacent2():
    rule = load(CFG / "m3cf1n_stability_rule.json")
    assert rule["NEW_STABLE_S"] == ">=2 adjacent high-budget confirmed SHRINK grid states"
    require_stage("COMPLETE")
    manifest = load(RES / "run_manifest.json")
    if manifest["final_verdict"] == "CF1N-DISC-C":
        pytest.skip("no eligible configs; confirmation correctly not run")
    by_config = load(OUT / "m3cf1n_confirmation_by_config.json")
    for cid, rec in by_config.items():
        if rec["final_class"] == "NEW_STABLE_S":
            assert rec["confirmed_adjacent_pairs"] >= 1 and rec["confirmed_S_count"] >= 2


def test_m3cf1n_new_fragile():
    rule = load(CFG / "m3cf1n_stability_rule.json")
    assert "no adjacent SHRINK pair" in rule["NEW_FRAGILE_S"]
    require_stage("COMPLETE")
    manifest = load(RES / "run_manifest.json")
    if manifest["final_verdict"] == "CF1N-DISC-C":
        pytest.skip("no eligible configs; confirmation correctly not run")
    by_config = load(OUT / "m3cf1n_confirmation_by_config.json")
    for cid, rec in by_config.items():
        if rec["final_class"] == "NEW_FRAGILE_S":
            assert rec["confirmed_S_count"] >= 1 and rec["confirmed_adjacent_pairs"] == 0


def test_m3cf1n_new_vanished():
    rule = load(CFG / "m3cf1n_stability_rule.json")
    assert "0 confirmed SHRINK" in rule["NEW_VANISHED_S"]


def test_m3cf1n_target_two_new_stable():
    gates = load(OUT / "m3cf1n_gates.json")
    assert gates["primary_target"] == "K_NEW_STABLE >= 2"
    require_stage("COMPLETE")
    final = load(OUT / "m3cf1n_final_verdict.json")
    assert final["K_NEW_STABLE"] >= 2 if final["verdict"] == "CF1N-A" else True


def test_m3cf1n_no_fragile_as_stable():
    rule = load(CFG / "m3cf1n_stability_rule.json")
    assert rule["FRAGILE_counts_as_STABLE"] is False
    require_stage("COMPLETE")
    final = load(OUT / "m3cf1n_final_verdict.json")
    assert final["total_stable_configs"] == 2 + final["K_NEW_STABLE"]


def test_m3cf1n_verdict_priority():
    gates = load(OUT / "m3cf1n_gates.json")
    assert gates["verdict_priority"][0] == "CF1N-X"
    assert gates["verdict_priority"][1] == "CF1N-DISC-C"
    assert gates["verdict_priority"][2] == "CF1N-A"
    require_stage("COMPLETE")
    final = load(OUT / "m3cf1n_final_verdict.json")
    assert final["verdict"] in {"CF1N-A", "CF1N-B", "CF1N-C", "CF1N-DISC-C", "CF1N-X"}
    if final["verdict"] == "CF1N-A":
        assert final["K_NEW_STABLE"] >= 2
    elif final["verdict"] == "CF1N-B":
        assert final["K_NEW_STABLE"] == 1
