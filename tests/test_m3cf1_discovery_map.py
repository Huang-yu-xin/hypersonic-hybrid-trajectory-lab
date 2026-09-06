"""Regression contracts for the M3-CF1 frozen discovery-map stage."""

import csv
import hashlib
import json
from pathlib import Path

from hyptraj.m3cf1.workflow import classify_support, discovery_eligible_configs, final_verdict


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phase_m3cf1" / "summary"
CFG = ROOT / "configs" / "phase_m3cf1"
DOC = ROOT / "docs" / "phase_m3cf1"
CF0_OUT = ROOT / "results" / "phase_m3cf0" / "summary"


def j(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(name: str):
    with (OUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _labels(config_id: str, labels: list[str]):
    return [{"config_id": config_id, "grid_index": index, "confirmed_label": label} for index, label in enumerate(labels, 1)]


def test_m3cf1_parent_cf0a():
    assert j(CF0_OUT / "m3cf0_final_verdict.json")["verdict"] == "CF0-A"


def test_m3cf1_exact8_new_configs():
    manifest = j(OUT / "m3cf1_new_config_manifest.json")
    assert manifest["count"] == 8
    assert manifest["config_ids"] == [f"cf0_new_{index:03d}" for index in range(8)]


def test_m3cf1_configs_match_cf0_hash():
    manifest = j(OUT / "m3cf1_new_config_manifest.json")
    source = ROOT / manifest["source_csv"]
    assert manifest["source_sha256"] == _sha(source)


def test_m3cf1_exact9_s2_values():
    assert j(CFG / "m3cf1_common_s2_grid.json")["values"] == [1.25, 1.6, 2.0, 2.5, 3.2, 4.0, 5.0, 6.4, 8.0]


def test_m3cf1_grid_matches_cf0_hash():
    grid = j(CFG / "m3cf1_common_s2_grid.json")
    assert grid["source_sha256"] == _sha(ROOT / grid["source_artifact"])


def test_m3cf1_exact72_discovery_states():
    states = rows("m3cf1_discovery_states.csv")
    assert len(states) == 72
    assert len({row["state_id"] for row in states}) == 72


def test_m3cf1_discovery_budget_100k():
    protocol = j(CFG / "m3cf1_discovery_protocol.json")
    assert protocol["samples_per_arm"] == 100_000 and protocol["paired_crn_batches"] == 20


def test_m3cf1_confirmation_budget_500k():
    protocol = j(CFG / "m3cf1_confirmation_protocol.json")
    assert protocol["samples_per_arm"] == 500_000 and protocol["paired_crn_batches"] == 20


def test_m3cf1_discovery_confirm_seed_disjoint():
    discovery = j(CFG / "m3cf1_discovery_seeds.json")["finite_action"]
    confirmation = j(CFG / "m3cf1_confirmation_seeds.json")["finite_action"]
    assert {tuple(item["seed_key"]) for item in discovery}.isdisjoint({tuple(item["seed_key"]) for item in confirmation})


def test_m3cf1_no_adaptive_grid():
    protocol = j(CFG / "m3cf1_discovery_protocol.json")
    assert not protocol["adaptive_refinement"] and j(CFG / "m3cf1_common_s2_grid.json")["frozen"]


def test_m3cf1_no_config_replacement():
    assert not j(OUT / "m3cf1_new_config_manifest.json")["manual_edits_permitted"]


def test_m3cf1_discovery_all72():
    states = rows("m3cf1_discovery_states.csv")
    assert {row["grid_index"] for row in states} == {str(index) for index in range(1, 10)}
    assert all(sum(row["config_id"] == config_id for row in states) == 9 for config_id in {row["config_id"] for row in states})


def test_m3cf1_discovery_uniform_budget():
    protocol = j(CFG / "m3cf1_discovery_protocol.json")
    assert protocol["finite_action_samples"] == 72 * 3 * 100_000


def test_m3cf1_event_semantics_v2():
    protocol = j(CFG / "m3cf1_discovery_protocol.json")
    assert protocol["event_semantics_schema_version"] == 2
    assert protocol["event"] == "topology != S0" and protocol["min_arm_ess"] == 20


def test_m3cf1_adjacent_eligibility_rule():
    result = discovery_eligible_configs([
        {"config_id": "a", "grid_index": 1, "provisional_label": "PROV_SHRINK"},
        {"config_id": "a", "grid_index": 2, "provisional_label": "PROV_SHRINK"},
        {"config_id": "a", "grid_index": 3, "provisional_label": "PROV_HOLD"},
    ])
    assert result["a"]["eligible"] and result["a"]["adjacent_prov_shrink_pairs"] == [{"left_grid_index": 1, "right_grid_index": 2}]


def test_m3cf1_all_eligible_configs_selected():
    result = discovery_eligible_configs([
        {"config_id": "a", "grid_index": 1, "provisional_label": "PROV_SHRINK"},
        {"config_id": "a", "grid_index": 2, "provisional_label": "PROV_SHRINK"},
        {"config_id": "b", "grid_index": 1, "provisional_label": "PROV_HOLD"},
    ])
    assert [key for key, value in result.items() if value["eligible"]] == ["a"]


def test_m3cf1_no_effect_ranking():
    assert ">=2 adjacent PROV_SHRINK" in j(CFG / "m3cf1_gates.json")["discovery_eligibility"]


def test_m3cf1_confirm_only_eligible_configs():
    assert j(CFG / "m3cf1_confirmation_protocol.json")["confirm_all_nine_frozen_states_per_eligible_config"]


def test_m3cf1_confirm_all9_grid_states_per_eligible_config():
    confirmation = j(CFG / "m3cf1_confirmation_protocol.json")
    assert confirmation["finite_action_samples_per_eligible_config"] == 9 * 3 * 500_000


def test_m3cf1_confirm_no_new_states():
    assert j(CFG / "m3cf1_confirmation_protocol.json")["no_new_states"]


def test_m3cf1_new_stable_rule_adjacent2():
    classified = classify_support(_labels("a", ["HOLD", "SHRINK", "SHRINK", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD"]))
    assert classified["a"]["classification"] == "NEW_STABLE_S"


def test_m3cf1_new_fragile_rule():
    classified = classify_support(_labels("a", ["HOLD", "SHRINK", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD"]))
    assert classified["a"]["classification"] == "NEW_FRAGILE_S"


def test_m3cf1_new_vanished_rule():
    classified = classify_support(_labels("a", ["HOLD"] * 9))
    assert classified["a"]["classification"] == "NEW_VANISHED_S"


def test_m3cf1_target_two_new_stable():
    result = final_verdict(invalid=False, eligible_count=2, classifications=[{"classification": "NEW_STABLE_S"}, {"classification": "NEW_STABLE_S"}])
    assert result["verdict"] == "CF1-A" and result["primary_target_pass"]


def test_m3cf1_no_diversity_relaxation():
    gates = j(CFG / "m3cf1_gates.json")
    assert gates["primary_target"] == "K_NEW_STABLE >= 2"


def test_m3cf1_no_pilot():
    protected = j(OUT / "m3cf1_protected_confirmation_audit.json")
    assert protected["protected_confirmation_pilot_trials"] == 0


def test_m3cf1_no_probe():
    assert j(CFG / "m3cf1_gates.json")["forbidden"]["finite_action_probe"]


def test_m3cf1_threshold_null():
    assert j(CFG / "m3cf1_gates.json")["forbidden"]["threshold_selection"]


def test_m3cf1_protected_confirmation_zero():
    protected = j(OUT / "m3cf1_protected_confirmation_audit.json")
    assert protected["confirmation_is_not_started"] and not protected["state_specific_protected_information_used"]


def test_m3cf1_value_blocked():
    assert j(CFG / "m3cf1_gates.json")["forbidden"]["value"] == "BLOCKED"


def test_m3cf1_rarity_blocked():
    assert j(CFG / "m3cf1_gates.json")["forbidden"]["rarity_shift"] == "BLOCKED"


def test_m3cf1_m3q_blocked():
    assert j(CFG / "m3cf1_gates.json")["forbidden"]["m3_q"] == "BLOCKED"


def test_m3cf1_output_schema():
    required = [
        OUT / "m3cf1_source_manifest.json", OUT / "m3cf1_new_config_manifest.json",
        CFG / "m3cf1_common_s2_grid.json", OUT / "m3cf1_discovery_states.csv",
        CFG / "m3cf1_discovery_protocol.json", CFG / "m3cf1_discovery_seeds.json",
        CFG / "m3cf1_confirmation_protocol.json", CFG / "m3cf1_confirmation_seeds.json",
        CFG / "m3cf1_gates.json", OUT / "m3cf1_prereg_hashes.json",
        OUT / "m3cf1_protected_confirmation_audit.json",
    ]
    docs = [
        "M3_CF1_Task.md", "M3_CF1_Parent_Audit.md", "M3_CF1_Discovery_Pregistration.md",
        "M3_CF1_Human_Discovery_Approval.md", "M3_CF1_Discovery_Audit.md",
        "M3_CF1_Confirmation_Eligibility.md", "M3_CF1_Human_Confirmation_Approval.md",
        "M3_CF1_Confirmation_Audit.md", "M3_CF1_Final_Report.md",
    ]
    assert all(path.exists() for path in required)
    assert all((DOC / name).exists() for name in docs)
