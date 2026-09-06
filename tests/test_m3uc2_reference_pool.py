"""Invariant checks for the M3-UC2 preregistered reference pool."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3uc2/summary"
CFG = ROOT / "configs/phase_m3uc2"


def read_json(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def rows(name):
    with (OUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_m3uc2_parent_uc1e_and_zero_pilot():
    isolation = read_json("m3uc2_uc1_outcome_isolation_audit.json")
    protocol = json.loads((CFG / "m3uc2_reference_protocol.json").read_text())
    assert isolation["pass"]
    assert protocol["pilot_samples"] == 0 and protocol["threshold"] is None
    assert protocol["rarity_shift"] == protocol["m3_q"] == "BLOCKED"


def test_m3uc2_outcome_isolation_and_prior_exclusion():
    isolation = read_json("m3uc2_uc1_outcome_isolation_audit.json")
    assert not isolation["uc1_per_state_reference_file_used_by_generator"]
    assert not isolation["uc1_per_state_labels_used_by_generator"]
    assert not isolation["uc1_per_state_metrics_used_by_generator"]
    manifest = read_json("m3uc2_prior_state_exclusion_manifest.json")
    assert manifest["uc1_48_identities_included"] and manifest["count"] >= 48


def test_m3uc2_generator_strata_sources_fractions_and_capacity():
    cap = read_json("m3uc2_generator_capacity.json")
    assert cap["capacities"] == {"DW": 56, "DS": 40, "U": 50}
    assert len(cap["source_geometry"]["w_interior_cells"]) == 7
    assert len(cap["source_geometry"]["s_interior_cells"]) == 5
    assert len(cap["source_geometry"]["u_transition_brackets"]) == 5
    assert all(value >= 20 for value in cap["capacities"].values())
    fractions = json.loads((CFG / "m3uc2_fraction_libraries.json").read_text())
    assert fractions["F_DIR"] == ["1/3", "2/3", "1/4", "3/4", "2/5", "3/5", "1/5", "4/5"]
    assert fractions["F_U"] == ["1/6", "5/6", "1/10", "3/10", "7/10", "9/10", "1/12", "5/12", "7/12", "11/12"]


def test_m3uc2_exact_60_unique_and_split_before_reference():
    fresh = rows("m3uc2_fresh_states.csv")
    assert len(fresh) == 60 == len({r["state_id"] for r in fresh})
    assert Counter(r["design_stratum"] for r in fresh) == {"DW": 20, "DS": 20, "U": 20}
    assert Counter(r["split"] for r in fresh) == {"DEVELOPMENT": 30, "CONFIRMATION": 30}
    for split in ("DEVELOPMENT", "CONFIRMATION"):
        assert Counter(r["design_stratum"] for r in fresh if r["split"] == split) == {"DW": 10, "DS": 10, "U": 10}
    prereg = read_json("m3uc2_prereg_hashes.json")
    assert prereg["reference_outcomes"] == "NONE" and prereg["threshold"] is None


def test_m3uc2_reference_outputs_and_firewall_when_complete():
    result = OUT / "m3uc2_final_verdict.json"
    if not result.exists():
        return
    final = json.loads(result.read_text())
    reference = rows("m3uc2_reference_states.csv")
    assert len(reference) == 60
    assert final["development_pilot_samples"] == final["confirmation_pilot_samples"] == 0
    assert final["threshold"] is None and not final["outcome_adaptive_rebalancing"]
    assert final["rarity_shift"] == final["m3_q"] == "BLOCKED"
