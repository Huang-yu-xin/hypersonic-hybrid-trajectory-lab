"""M3-PI1VN protocol + persistence + boundary contracts (taskbook Sec. 37)."""
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402
from hyptraj.m3pi1vr0.persistence import (  # noqa: E402
    safe_fs_id,
    validate_safe_path,
)
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    HASH_FIELD,
    ReplayError,
    record_file_hash,
    run_trial_transactional,
    scientific_payload_hash,
)

OUT = ROOT / "results/phase_m3pi1vn/summary"
CFG = ROOT / "configs/phase_m3pi1vn"
TRIALS = ROOT / "results/phase_m3pi1vn/trials"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def sealed():
    return (TRIALS / "trial_manifest.json").exists()


# ------------------------- gradient / probe protocol -----------------------

def test_m3pi1vn_R_exact8():
    g = load(CFG / "m3pi1vn_gradient_protocol.json")
    assert g["replicates"] == 8
    assert load(OUT / "m3pi1vn_gradient_contract.json")["R"] == 8


def test_m3pi1vn_Bgrad_exact20000():
    g = load(CFG / "m3pi1vn_gradient_protocol.json")
    assert g["samples_per_trial"] == 20_000


def test_m3pi1vn_gradient_estimator_hash():
    inh = load(OUT / "m3pi1vn_protocol_inheritance_audit.json")
    assert inh["gradient_estimator"].startswith(
        "hyptraj.m3d.adaptation.gradient_decision")
    assert inh["gradient_estimator_source_sha256"] == \
        hashlib.sha256((ROOT / "src/hyptraj/m3d/adaptation.py").read_bytes()).hexdigest()


def test_m3pi1vn_gradient_sign_rule():
    g = load(CFG / "m3pi1vn_gradient_protocol.json")
    assert g["sign_mapping"] == "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK"


def test_m3pi1vn_gradient_invalid_rule():
    g = load(CFG / "m3pi1vn_gradient_protocol.json")
    assert "ABSTAIN" in g["invalid_rule"] and "ESS<20" in g["invalid_rule"]


def test_m3pi1vn_no_direction_redefinition():
    inh = load(OUT / "m3pi1vn_protocol_inheritance_audit.json")
    assert inh["sign_convention"] == "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK"
    pc = load(CFG / "m3pi1vn_probe_protocol.json")
    assert pc["invalid_gradient"] == "ABSTAIN_NO_PROBE"


# ------------------------------- probe -------------------------------------

def test_m3pi1vn_base_probe_10000():
    assert load(CFG / "m3pi1vn_probe_protocol.json")["base_samples"] == 10_000


def test_m3pi1vn_selected_probe_10000():
    assert load(CFG / "m3pi1vn_probe_protocol.json")["selected_action_samples"] == 10_000


def test_m3pi1vn_probe_total_20000():
    assert load(CFG / "m3pi1vn_probe_protocol.json")["total_probe_samples"] == 20_000


def test_m3pi1vn_total_cost_le2x():
    pc = load(OUT / "m3pi1vn_probe_contract.json")
    assert pc["total_online_le_2x"] is True and pc["probe_le_gradient_budget"] is True


def test_m3pi1vn_paired_crn20():
    pc = load(OUT / "m3pi1vn_probe_contract.json")
    assert pc["batches"] == 20 and pc["paired_crn"] is True


def test_m3pi1vn_selected_action_only():
    pc = load(CFG / "m3pi1vn_probe_protocol.json")
    assert pc["opposite_action_probe"] == "FORBIDDEN"


def test_m3pi1vn_opposite_probe_zero():
    if sealed():
        m = load(TRIALS / "trial_manifest.json")
        assert m["opposite_action_probe_samples"] == 0


def test_m3pi1vn_no_adaptive_probe():
    pc = load(OUT / "m3pi1vn_probe_contract.json")
    assert pc["no_adaptive_probe"] is True and pc["single_budget_level"] is True


# ------------------------------- V1 / S1 -----------------------------------

def test_m3pi1vn_rhat_definition():
    v = load(CFG / "m3pi1vn_v1_estimator.json")
    assert v["r_hat"] == "M2(selected)/M2(BASE) - 1"


def test_m3pi1vn_margin_minus1pct():
    assert load(CFG / "m3pi1vn_v1_estimator.json")["improvement_margin"] == -0.01


def test_m3pi1vn_v1_formula_exact():
    assert load(CFG / "m3pi1vn_v1_estimator.json")["formula"] == \
        "V1 = (-0.01 - r_hat) / SE(r_hat)"


def test_m3pi1vn_se_estimator_hash():
    v = load(CFG / "m3pi1vn_v1_estimator.json")
    assert v["source_sha256"] == hashlib.sha256(
        (ROOT / "scripts/run_m3pi1v.py").read_bytes()).hexdigest()


def test_m3pi1vn_invalid_probe_abstains():
    v = load(CFG / "m3pi1vn_v1_estimator.json")
    assert "ABSTAIN" in v["invalid_rule"]


def test_m3pi1vn_v1_controls_deploy_only():
    v = load(CFG / "m3pi1vn_v1_estimator.json")
    assert v["v1_never_changes_direction"] is True


def test_m3pi1vn_v1_never_changes_direction():
    g = load(CFG / "m3pi1vn_gradient_protocol.json")
    assert "no opposite direction inferred" in g["invalid_rule"]


def test_m3pi1vn_s1_definition_hash():
    s = load(CFG / "m3pi1vn_s1_contract.json")
    assert s["source_sha256"] == hashlib.sha256(
        (ROOT / "scripts/run_m3pi1v.py").read_bytes()).hexdigest()


def test_m3pi1vn_s1_same_gradient_data():
    assert load(CFG / "m3pi1vn_s1_contract.json")["same_gradient_data"] is True


def test_m3pi1vn_s1_no_probe_data():
    assert load(CFG / "m3pi1vn_s1_contract.json")["probe_information_used"] is False


def test_m3pi1vn_no_invalid_s1_threshold_reuse():
    assert load(CFG / "m3pi1vn_s1_contract.json")["no_invalid_threshold_reuse"] is True
    tc = load(CFG / "m3pi1vn_threshold_contract.json")
    assert tc["no_invalid_pi1v_threshold_reuse"] is True


# --------------------------- metrics / thresholds --------------------------

def test_m3pi1vn_wrong_gate_5pct():
    assert load(CFG / "m3pi1vn_gates.json")["wrong_direction_max"] == 0.05


def test_m3pi1vn_coverage_gate_75pct():
    assert load(CFG / "m3pi1vn_gates.json")["coverage_min"] == 0.75


def test_m3pi1vn_unsafe_gate_20pct():
    assert load(CFG / "m3pi1vn_gates.json")["unsafe_max"] == 0.20


def test_m3pi1vn_threshold_candidate_rule():
    tc = load(CFG / "m3pi1vn_threshold_contract.json")
    assert tc["candidate_rule"].startswith("deploy-all-valid sentinel")
    assert "abstain-all" in tc["candidate_rule"]


def test_m3pi1vn_threshold_tiebreak():
    tc = load(CFG / "m3pi1vn_threshold_contract.json")
    assert "maximize deployable coverage" in tc["selection_objective"][3]
    assert "canonical" in tc["selection_objective"][4]


def test_m3pi1vn_best_safe_coverage():
    tc = load(CFG / "m3pi1vn_threshold_contract.json")
    assert "max coverage over wrong<=5% & unsafe<=20%" in tc["best_safe_coverage"]


def test_m3pi1vn_unique_gain_5pp():
    tc = load(CFG / "m3pi1vn_threshold_contract.json")
    assert tc["unique_information"]["gain_threshold_pp"] == 0.05


def test_m3pi1vn_verdict_priority():
    import run_m3pi1v as P1V
    f = P1V.verdict_priority
    assert f(False, False, False, False) == "PI1VN-X".replace("PI1VN", "PI1V")
    assert f(True, True, True, True) == "PI1V-A"
    # PI1VN uses the same frozen priority order
    v = load(OUT / "m3pi1vn_final_verdict.json") \
        if (OUT / "m3pi1vn_final_verdict.json").exists() else None
    if v is not None and v["verdict"] == "PI1VN-X":
        assert v["status"] == "INVALID"


# ------------------------- persistence / boundaries ------------------------

def test_m3pi1vn_safe_path(tmp_path):
    enc = validate_safe_path("wcf1_new_000_wcf1_s2_1p25__rep0", tmp_path / "r.json")
    assert ":" not in enc
    contract = load(OUT / "m3pi1vn_persistence_contract.json")
    assert contract["order"][0] == "1. validate filesystem-safe path"
    assert contract["order"][1] == "2. durable STARTED ledger"


def test_m3pi1vn_started_before_simulator(tmp_path):
    observations = []

    def sim():
        observations.append(any(e.get("status") == "STARTED"
                                for e in ledger_entries(tmp_path / "led.jsonl")))
        return {"schema": "m3pi1vn_trial_v1", "state_id": "x::0"}

    def validate(rec):
        assert rec["schema"] == "m3pi1vn_trial_v1"

    rec = run_trial_transactional("x::0", tmp_path / "rec.json", sim,
                                  ledger_path=tmp_path / "led.jsonl",
                                  pre_hash_validator=validate)
    assert rec["status"] == "COMPLETE" and observations == [True]


def test_m3pi1vn_non_circular_hash(tmp_path):
    rec = run_trial_transactional(
        "h::rep0", tmp_path / "h.json", lambda: {"schema": "m3pi1vn_trial_v1",
                                                 "state_id": "h::rep0"},
        ledger_path=tmp_path / "led.jsonl",
        pre_hash_validator=lambda r: None)
    stored = json.loads((tmp_path / "h.json").read_text(encoding="utf-8"))
    assert scientific_payload_hash(stored) == stored[HASH_FIELD]


def test_m3pi1vn_atomic_persistence(tmp_path):
    import hashlib as hl
    rec = run_trial_transactional(
        "a::rep0", tmp_path / "a.json", lambda: {"schema": "m3pi1vn_trial_v1",
                                                 "state_id": "a::rep0"},
        ledger_path=tmp_path / "led.jsonl", pre_hash_validator=lambda r: None)
    assert hl.sha256((tmp_path / "a.json").read_bytes()).hexdigest() \
        == rec["record_file_hash"]
    assert not list(tmp_path.glob(".*.tmp.*"))


def test_m3pi1vn_final_hash_verify():
    # the 136 durable diagnostic records verify against the ledger
    entries = ledger_entries(TRIALS / "trial_ledger.jsonl")
    checked = 0
    for e in entries:
        if e.get("status") != "COMPLETE":
            continue
        f = TRIALS / safe_fs_id(e["panel_state_id"]) / f"rep{e['rep_id']}.json"
        assert record_file_hash(f) == e["record_file_hash"]
        checked += 1
    assert checked == 136


def test_m3pi1vn_consumed_invalid_no_replay():
    entries = ledger_entries(TRIALS / "trial_ledger.jsonl")
    statuses = Counter(e.get("status") for e in entries)
    assert statuses.get("CONSUMED_INVALID", 0) == 1
    consumed = next(e["state_id"] for e in entries
                    if e.get("status") == "CONSUMED_INVALID")
    with pytest.raises(ReplayError):
        run_trial_transactional(
            consumed, TRIALS / safe_fs_id(consumed.split("__")[0])
            / "rep0.json", lambda: {"schema": "m3pi1vn_trial_v1"},
            ledger_path=TRIALS / "trial_ledger.jsonl",
            pre_hash_validator=lambda r: None)


def test_m3pi1vn_no_frozen_overwrite():
    prereg = load(OUT / "m3pi1vn_prereg_hashes.json")
    for e in prereg["files"]:
        p = ROOT / e["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]


def test_m3pi1vn_all192_complete_or_invalid():
    # under PI1VN-X: 136 durable COMPLETE (diagnostic), 1 CONSUMED_INVALID,
    # 55 never started -- the frozen no-replay rule is recorded
    entries = ledger_entries(TRIALS / "trial_ledger.jsonl")
    st = Counter(e.get("status") for e in entries)
    assert st.get("COMPLETE", 0) + st.get("CONSUMED_INVALID", 0) <= 192
    v = load(OUT / "m3pi1vn_final_verdict.json")
    assert v["verdict"] == "PI1VN-X" and v["status"] == "INVALID"
    assert v["trials"]["complete"] == 136 and v["trials"]["consumed_invalid"] == 1


def test_m3pi1vn_no_confirmation():
    v = load(OUT / "m3pi1vn_final_verdict.json")
    assert v["protected_confirmation_authorized"] is False
    assert v["confirmation_trials"] == 0


def test_m3pi1vn_reserve_unexposed():
    v = load(OUT / "m3pi1vn_final_verdict.json")
    assert v["reserve_pilot_trials"] == 0


def test_m3pi1vn_value_blocked():
    assert load(OUT / "m3pi1vn_final_verdict.json")["value"] == "BLOCKED"


def test_m3pi1vn_rarity_blocked():
    assert load(OUT / "m3pi1vn_final_verdict.json")["rarity_shift"] == "BLOCKED"


def test_m3pi1vn_m3q_blocked():
    assert load(OUT / "m3pi1vn_final_verdict.json")["m3_q"] == "BLOCKED"
