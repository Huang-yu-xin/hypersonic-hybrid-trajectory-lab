"""Zero-simulator UC0 provenance, replay, and diagnostic-firewall tests."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "phase_m3uc0" / "summary"

def load(name: str) -> dict: return json.loads((OUT / name).read_text(encoding="utf-8"))
def rows(name: str) -> list[dict]:
    with (OUT / name).open(encoding="utf-8") as fh: return list(csv.DictReader(fh))
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def test_m3uc0_parent_g2d():
    assert load("m3uc0_final_verdict.json")["parent_g2_verdict"] == "G2-D"

def test_m3uc0_zero_simulator():
    final = load("m3uc0_final_verdict.json"); assert final["extra_simulator_calls"] == 0 and final["new_controller_trials"] == 0

def test_m3uc0_source_hashes():
    for entry in load("m3uc0_source_manifest.json")["entries"]:
        assert entry["read_only"] is True and sha(REPO / entry["path"]) == entry["sha256"]

def test_m3uc0_trial_counts():
    data = rows("m3uc0_all_g2_trials.csv"); assert len(data) == 216
    assert sum(r["axis"] == "directional" for r in data) == 128
    assert sum(r["axis"] == "safety" for r in data) == 40
    assert sum(r["axis"] == "reserve" for r in data) == 48

def test_m3uc0_policy_replay_exact():
    audit = load("m3uc0_policy_replay_audit.json"); assert audit["exact"] and audit["agreement"] == 216

def test_m3uc0_no_raw_trial_mutation():
    manifest = load("m3uc0_source_manifest.json")
    raw = [e for e in manifest["entries"] if e["role"].endswith("raw trials")]
    assert len(raw) == 3 and all(sha(REPO / e["path"]) == e["sha256"] for e in raw)

def test_m3uc0_no_new_policy_claim_and_reserve_not_holdout():
    summary = load("m3uc0_calibration_summary.json"); assert summary["best_descriptive_tradeoff"] == "diagnostic only; not a new policy" and summary["reserve_is_not_clean_holdout"]
    assert all(r["diagnostic_only"] == "True" and r["not_confirmatory"] == "True" for r in rows("m3uc0_threshold_diagnostic.csv"))

def test_m3uc0_state_level_analysis_and_mismatch():
    state = rows("m3uc0_state_level_summary.csv"); mismatch = rows("m3uc0_gradient_finite_action_mismatch.csv")
    assert len(state) == len(mismatch) == 27
    assert {r["mismatch_type"] for r in mismatch} >= {"M1", "M2", "M3"}

def test_m3uc0_rarity_and_m3q_blocked():
    final = load("m3uc0_final_verdict.json"); assert final["rarity_shift"] == "BLOCKED" and final["m3_q"] == "BLOCKED"

def test_m3uc0_output_schema_and_uc0a_gate():
    final = load("m3uc0_final_verdict.json"); assert final["status"] == "COMPLETE" and final["verdict"] == "UC0-A"
    required = {"axis", "state_id", "reference_status", "gradient_estimate", "gradient_se", "ESS", "policy_action", "pilot_samples", "S1_gradient_z"}
    assert required <= set(rows("m3uc0_all_g2_trials.csv")[0])
    good = [r for r in rows("m3uc0_threshold_diagnostic.csv") if float(r["directional_coverage"]) >= .75 and float(r["safety_unsafe_deployment"]) <= .2]
    assert good
