"""M3-CF2 panel contracts (taskbook §43)."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "phase_m3cf2"
OUT = RES / "summary"
CFG = ROOT / "configs" / "phase_m3cf2"
DOC = ROOT / "docs" / "phase_m3cf2"
CF1N_OUT = ROOT / "results" / "phase_m3cf1n" / "summary"
CF1_OUT = ROOT / "results" / "phase_m3cf1" / "summary"
SF2 = ROOT / "results" / "phase_m3sf2" / "summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def panel():
    return csv_rows(OUT / "m3cf2_development_panel.csv")


def group(g):
    return [p for p in panel() if p["truth_group"] == g]


# --------------------------------------------------------------------------
# Parent / source
# --------------------------------------------------------------------------

def test_m3cf2_parent_cf1na():
    assert load(CF1N_OUT / "m3cf1n_final_verdict.json")["verdict"] == "CF1N-A"
    pa = load(OUT / "m3cf2_parent_audit.json")
    assert pa["K_NEW_STABLE"] == 6 and pa["K_CURRENT_STABLE"] == 2 and pa["K_TOTAL_STABLE"] == 8


def test_m3cf2_zero_simulator():
    v = load(OUT / "m3cf2_final_verdict.json")
    assert v["simulator_samples"] == 0
    assert v["new_p_ref_samples"] == 0
    assert v["new_finite_action_reference_samples"] == 0


def test_m3cf2_cf1_remains_invalid():
    assert load(CF1_OUT / "m3cf1_final_verdict.json")["verdict"] == "CF1-X"
    assert load(OUT / "m3cf2_parent_audit.json")["CF1_remains_INVALID"] is True


def test_m3cf2_no_cf1_primary_evidence():
    policy = load(CFG / "m3cf2_source_policy.json")
    assert "CF1 invalid scientific records" in policy["forbidden_sources"]
    assert policy["CF1_used"] is False
    audit = load(OUT / "m3cf2_panel_selection_audit.json")["checks"]
    assert audit["CF1_invalid_evidence_unused"] is True


def test_m3cf2_corrected_truth_only():
    inv = csv_rows(OUT / "m3cf2_candidate_truth_inventory.csv")
    assert all(r["event_schema"] == "corrected full-event v2" for r in inv)
    assert all(r["truth"] in {"WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"} for r in inv)


def test_m3cf2_high_budget_only():
    inv = csv_rows(OUT / "m3cf2_candidate_truth_inventory.csv")
    assert all(int(r["reference_budget"]) == 1_500_000 for r in inv)


def test_m3cf2_durable_complete_only():
    inv = csv_rows(OUT / "m3cf2_candidate_truth_inventory.csv")
    assert all(r["durable_complete"] == "True" for r in inv)


def test_m3cf2_no_pilot_exposed_candidates():
    inv = csv_rows(OUT / "m3cf2_candidate_truth_inventory.csv")
    assert all(r["pilot_exposed"] == "False" for r in inv)


def test_m3cf2_no_probe_exposed_candidates():
    inv = csv_rows(OUT / "m3cf2_candidate_truth_inventory.csv")
    assert all(r["probe_exposed"] == "False" for r in inv)


# --------------------------------------------------------------------------
# Redacted selector
# --------------------------------------------------------------------------

def test_m3cf2_selection_view_allowed_columns():
    allowed = {"state_id", "source_stage", "config_id", "physical_family", "s2", "truth",
               "stable_config_flag", "source_interval_or_grid_index", "canonical_bank_order"}
    rows = csv_rows(OUT / "m3cf2_selection_view.csv")
    assert rows
    assert set(rows[0].keys()) == allowed


def test_m3cf2_forbidden_effect_fields_absent():
    forbidden = {"r_w", "r_s", "M2", "effect", "SE", "margin", "gradient", "S1", "V1", "threshold_distance"}
    rows = csv_rows(OUT / "m3cf2_selection_view.csv")
    assert not (set(rows[0].keys()) & forbidden)
    audit = load(OUT / "m3cf2_panel_selection_audit.json")["checks"]
    assert audit["forbidden_effect_fields_absent"] is True


def test_m3cf2_selection_view_hash():
    recorded = load(OUT / "m3cf2_selection_view_hash.json")
    assert recorded["sha256"] == sha(OUT / "m3cf2_selection_view.csv")
    assert recorded["forbidden_effect_fields_present"] is False


def test_m3cf2_selector_deterministic():
    contract = load(OUT / "m3cf2_selector_contract.json")
    assert contract["deterministic"] is True
    # re-derive the S group independently: median-s2 SHRINK per stable config
    view = csv_rows(OUT / "m3cf2_selection_view.csv")
    stable = {e["config_id"] for e in load(OUT / "m3cf2_stable_config_manifest.json")["stable_configs"]}
    expected_s = set()
    for cid in stable:
        cands = sorted((r for r in view if r["config_id"] == cid and r["truth"] == "SHRINK"),
                       key=lambda r: (float(r["s2"]), r["state_id"]))
        expected_s.add(cands[(len(cands) - 1) // 2]["state_id"])
    actual_s = {p["state_id"] for p in group("S")}
    assert actual_s == expected_s


def test_m3cf2_no_manual_override():
    assert load(OUT / "m3cf2_selector_contract.json")["manual_override"] == "FORBIDDEN"
    assert load(OUT / "m3cf2_panel_selection_audit.json")["checks"]["manual_override"] == "NO"


def test_m3cf2_no_gradient_selection():
    assert "gradient score" in load(OUT / "m3cf2_selector_contract.json")["forbidden_inputs"]


def test_m3cf2_no_v1_selection():
    assert "V1 score" in load(OUT / "m3cf2_selector_contract.json")["forbidden_inputs"]


# --------------------------------------------------------------------------
# SHRINK group
# --------------------------------------------------------------------------

def test_m3cf2_total_stable_configs8():
    manifest = load(OUT / "m3cf2_stable_config_manifest.json")
    assert len(manifest["stable_configs"]) == 8
    families = Counter(e["family"] for e in manifest["stable_configs"])
    assert families == {"current": 2, "replacement": 6}


def test_m3cf2_s_exact8():
    assert len(group("S")) == 8


def test_m3cf2_s_distinct_configs8():
    assert len({p["config_id"] for p in group("S")}) == 8


def test_m3cf2_s_one_per_stable_config():
    counts = Counter(p["config_id"] for p in group("S"))
    assert max(counts.values()) == 1
    stable_ids = {e["config_id"] for e in load(OUT / "m3cf2_stable_config_manifest.json")["stable_configs"]}
    assert set(counts) == stable_ids


def test_m3cf2_s_all_confirmed():
    assert all(p["truth"] == "SHRINK" for p in group("S"))


# --------------------------------------------------------------------------
# WIDEN group
# --------------------------------------------------------------------------

def test_m3cf2_w_exact8():
    assert len(group("W")) == 8


def test_m3cf2_w_configs_ge6():
    assert len({p["config_id"] for p in group("W")}) >= 6


def test_m3cf2_w_max2_per_config():
    assert max(Counter(p["config_id"] for p in group("W")).values()) <= 2


# --------------------------------------------------------------------------
# ND group
# --------------------------------------------------------------------------

def test_m3cf2_nd_exact8():
    assert len(group("ND")) == 8


def test_m3cf2_nd_truth_hold_or_amb():
    assert all(p["truth"] in {"HOLD", "AMBIGUOUS"} for p in group("ND"))


def test_m3cf2_nd_diversity_gate():
    composition = load(OUT / "m3cf2_panel_composition.json")
    assert composition["ND_configs"] >= 6 or composition["ND_source_regions"] >= 6


def test_m3cf2_nd_max2_per_config():
    assert max(Counter(p["config_id"] for p in group("ND")).values()) <= 2


# --------------------------------------------------------------------------
# Whole panel / boundaries
# --------------------------------------------------------------------------

def test_m3cf2_panel_exact24():
    assert len(panel()) == 24


def test_m3cf2_panel_exact8w8s8nd():
    counts = Counter(p["truth_group"] for p in panel())
    assert counts == {"W": 8, "S": 8, "ND": 8}


def test_m3cf2_panel_unique_state_ids():
    assert len({p["state_id"] for p in panel()}) == 24


def test_m3cf2_panel_hash():
    recorded = load(OUT / "m3cf2_development_panel_hash.json")
    assert recorded["sha256"] == sha(OUT / "m3cf2_development_panel.csv")
    assert recorded["parent_input_for"] == "M3-PI1V"


def test_m3cf2_panel_no_pilot():
    composition = load(OUT / "m3cf2_panel_composition.json")
    assert composition["pilot_exposed_selected_states"] == 0


def test_m3cf2_panel_no_probe():
    composition = load(OUT / "m3cf2_panel_composition.json")
    assert composition["probe_exposed_selected_states"] == 0


def test_m3cf2_unselected_states_protected():
    reserve = csv_rows(OUT / "m3cf2_pilot_protected_reserve_manifest.csv")
    selected = {p["state_id"] for p in panel()}
    view = {r["state_id"] for r in csv_rows(OUT / "m3cf2_selection_view.csv")}
    assert selected | {r["state_id"] for r in reserve} == view
    assert not (selected & {r["state_id"] for r in reserve})
    summary = load(OUT / "m3cf2_reserve_summary.json")
    assert summary["reserve_total"] == len(reserve)


def test_m3cf2_gradient_pilot_zero():
    assert load(OUT / "m3cf2_protected_confirmation_audit.json")["gradient_pilot_trials"] == 0


def test_m3cf2_v1_probe_zero():
    a = load(OUT / "m3cf2_protected_confirmation_audit.json")
    assert a["finite_action_probe_trials"] == 0 and a["v1_threshold"] is None


def test_m3cf2_threshold_null():
    assert load(OUT / "m3cf2_protected_confirmation_audit.json")["v1_threshold"] is None


def test_m3cf2_uc2r_protected_confirmation_zero():
    a = load(OUT / "m3cf2_protected_confirmation_audit.json")
    assert a["UC2R_protected_confirmation_pilot_trials"] == 0
    assert a["touched_by_CF2"] is False


def test_m3cf2_value_blocked():
    assert load(OUT / "m3cf2_final_verdict.json")["value"] == "BLOCKED"


def test_m3cf2_rarity_blocked():
    assert load(OUT / "m3cf2_final_verdict.json")["rarity_shift"] == "BLOCKED"


def test_m3cf2_m3q_blocked():
    assert load(OUT / "m3cf2_final_verdict.json")["m3_q"] == "BLOCKED"


def test_m3cf2_output_schema():
    required_summary = [
        "m3cf2_source_manifest.json", "m3cf2_candidate_truth_inventory.csv",
        "m3cf2_candidate_eligibility_audit.json", "m3cf2_selection_view.csv",
        "m3cf2_selection_view_hash.json", "m3cf2_stable_config_manifest.json",
        "m3cf2_selector_contract.json", "m3cf2_development_panel.csv",
        "m3cf2_development_panel_hash.json", "m3cf2_panel_composition.json",
        "m3cf2_panel_selection_audit.json", "m3cf2_pilot_protected_reserve_manifest.csv",
        "m3cf2_reserve_summary.json", "m3cf2_protected_confirmation_audit.json",
        "m3cf2_final_verdict.json",
    ]
    assert all((OUT / n).exists() for n in required_summary)
    assert all((CFG / n).exists() for n in
               ["m3cf2_source_policy.json", "m3cf2_selector.json",
                "m3cf2_diversity_gates.json", "m3cf2_pilot_protection.json"])
    assert all((DOC / n).exists() for n in
               ["M3_CF2_Task.md", "M3_CF2_Parent_Audit.md",
                "M3_CF2_Reference_Inventory_Audit.md", "M3_CF2_Redacted_Selection_Contract.md",
                "M3_CF2_Development_Panel_Selection.md", "M3_CF2_Pilot_Protection_Audit.md",
                "M3_CF2_Final_Report.md"])
    # source manifest hashes still valid
    for e in load(OUT / "m3cf2_source_manifest.json")["entries"]:
        assert sha(ROOT / e["path"]) == e["sha256"], e["path"]
