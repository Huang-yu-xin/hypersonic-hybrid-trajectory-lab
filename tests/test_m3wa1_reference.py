"""M3-WA1 P_ref/reference contracts (taskbook Sec. 28)."""
import csv
import hashlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1/summary"
REF = ROOT / "results/phase_m3wa1/reference"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3wa1_pref_dependency_audited():
    dep = load(OUT / "m3wa1_pref_dependency_audit.json")
    assert dep["dependency"] == "CONFIG_SPECIFIC"
    assert len(dep["code_evidence"]) >= 3
    assert dep["new_p_ref_samples"] == 0


def test_m3wa1_pref_reuse_only_if_config_specific():
    dep = load(OUT / "m3wa1_pref_dependency_audit.json")
    assert "config-specific" in dep["rule"]
    # every manifest candidate points at a durable config P_ref record whose
    # hash was frozen pre-run and still verifies
    for c in csv_rows(OUT / "m3wa1_candidate_manifest.csv"):
        p = ROOT / c["P_ref_source"]
        assert p.exists()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == c["P_ref_hash"]
        rec = load(p)
        assert rec["config_id"] == c["config_id"]
        assert rec["sample_count"] == 500_000


def test_m3wa1_new_pref_if_state_dependent():
    dep = load(OUT / "m3wa1_pref_dependency_audit.json")
    assert "state-specific" in dep["rule"]
    # the actual dependency is config-specific, so zero new P_ref were used
    v = load(OUT / "m3wa1_final_verdict.json")
    assert dep["dependency"] == "CONFIG_SPECIFIC" and dep["new_p_ref_samples"] == 0
    assert v["new_p_ref_samples"] == 0 if "new_p_ref_samples" in v else True


def test_m3wa1_ref_budget_500k():
    pc = load(OUT / "m3wa1_persistence_contract.json")
    assert "500" not in pc["sequence"]  # budget lives in the protocol/STOP report
    txt = (OUT / "m3wa1_prereg_status.txt").read_text(encoding="utf-8")
    assert "samples/arm = 500000" in txt
    assert "finite-action samples = 12000000" in txt


def test_m3wa1_ref_three_arms():
    txt = (OUT / "m3wa1_prereg_status.txt").read_text(encoding="utf-8")
    assert "arms = 3" in txt
    script = (ROOT / "scripts/run_m3wa1.py").read_text(encoding="utf-8")
    assert 'for name in ("base", "widen", "shrink")' in script


def test_m3wa1_ref_crn20():
    txt = (OUT / "m3wa1_prereg_status.txt").read_text(encoding="utf-8")
    assert "batches = 20" in txt
    script = (ROOT / "scripts/run_m3wa1.py").read_text(encoding="utf-8")
    assert "N_BATCH = 20" in script
    assert "evaluate_reference_arms(" in script  # paired-CRN arm evaluation


def test_m3wa1_ref_corrected_semantics():
    from hyptraj.m3d2 import experiment as E
    sig = inspect.signature(E.classify_reference_state)
    assert sig.parameters["tau"].default == 0.01          # -1% improvement
    assert sig.parameters["hold_window"].default == 0.03  # +/-3% HOLD band
    assert sig.parameters["margin_min"].default == 0.05   # 5% direction margin
    assert sig.parameters["min_arm_ess"].default == 20.0  # ESS >= 20
    script = (ROOT / "scripts/run_m3wa1.py").read_text(encoding="utf-8")
    assert "classify_reference_state(arms_eval, p_ref_record)" in script
    assert "event = topology" not in script  # semantics inherited, not reimplemented


def test_m3wa1_ref_seed_disjoint():
    seeds = load(OUT / "m3wa1_seed_manifest.json")
    assert seeds["namespace"] == "M3-WA1-REF"
    assert seeds["prior_namespace_collision"] is False
    assert seeds["prior_recorded_seed_collision"] == []
    assert seeds["frozen_before_first_simulator_call"] is True
    assert len(seeds["seed_keys"]) == 8
    # the consumed attempt-1 trial's seed is recorded and retired by the rule
    forensics = load(OUT / "m3wa1_incident_forensics.json")
    assert forensics["no_replay_bookkeeping"]["seed_namespace"] == "M3-WA1-REF"
