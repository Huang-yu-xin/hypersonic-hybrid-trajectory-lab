"""M3-S25-R1-A1R0 tests: Replacement Arm-A preregistration (zero sampling).

Route tests run the REAL control flow with MOCKED trials/grids -- the
real simulator is never invoked.  The old Arm-A stream (terminal
M3-S25-R1-X) is retired evidence: its ledger is never resumed, its 960
seeds (including the consumed one and the 959 never-started) are fully
excluded, and the old 20k realization never enters replacement
accounting or evaluation.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s25r1 as R  # noqa: E402
from hyptraj.m3s25r1 import arm_a as AA  # noqa: E402
from hyptraj.m3s25r1 import arm_a_eval as AE  # noqa: E402


# --------------------------------------------------------------------------
# gates (item 1/8)
# --------------------------------------------------------------------------

def test_gate_state_after_a1r0():
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED") is False
    txt = R.APPROVAL_DOC.read_text(encoding="utf-8")
    assert "status = CLOSED / EXERCISED / TERMINAL-X" in txt
    assert R.TRUTH_TERMINAL_HEAD in txt
    assert "M3_S25_R1_A1R_ARM_A_AUTHORIZED: NO" in txt
    assert "M3_S25_R1_A1R_ARM_B_AUTHORIZED: NO" in txt
    # the original authorization + incident history are preserved
    assert "ARM A ONLY" in txt
    assert "M3_S25_R1_Arm_A_Incident_Report.md" in txt or \
        "incident" in txt.lower()


# --------------------------------------------------------------------------
# retired stream (item 2)
# --------------------------------------------------------------------------

def test_retired_stream_record_complete():
    r = R.load(R.A1R_RETIRED)
    assert r["old_terminal"] == "M3-S25-R1-X"
    assert len(r["units"]) == 960
    assert r["counts"] == {"total_units": 960, "consumed_invalid": 1,
                           "complete": 0, "never_started": 959}
    consumed = [u for u in r["units"]
                if u["status"] == "CONSUMED_INVALID_20K"]
    assert len(consumed) == 1
    assert consumed[0]["unit_id"] == "m3s2s_cfg_001_s2s_0.5708962241|rep0"
    assert r["consumed_unit"]["samples_consumed"] == 20000
    assert r["consumed_unit"]["unit_id"] == consumed[0]["unit_id"]
    assert consumed[0]["seed_key"] == [consumed[0]["seed"], 42424]
    assert r["old_arm_a_seed_manifest_sha256"] == R.ARM_A_SEED_MANIFEST_PIN
    assert r["old_incident_report_sha256"] == R.sha(
        R.DOC / "M3_S25_R1_Arm_A_Incident_Report.md")
    assert r["old_ledger_sha256_expected"] == R.sha(R.ARM_A_LEDGER)
    assert "no old Arm-A unit or seed may appear" in r["rule"]
    assert R.sha_bytes(R.A1R_RETIRED.read_bytes()) == R.A1R_RETIRED_PIN
    # the old ledger/artifacts are preserved verbatim
    assert R.sha_bytes(R.ARM_A_LEDGER.read_bytes()) == \
        r["old_ledger_sha256_expected"]


# --------------------------------------------------------------------------
# new seed stream (item 5) + budget (item 7)
# --------------------------------------------------------------------------

def test_new_seed_stream_fully_disjoint_from_retired():
    m = R.load(R.A1R_SEED_MANIFEST)
    retired = R.load(R.A1R_RETIRED)
    assert m["namespace"] == "M3-S25-R1-A1R-GRAD"
    assert m["n_units"] == 960 and m["n_trials"] == 960
    new_vals = set(m["planned_seeds"].values())
    old_vals = {u["seed"] for u in retired["units"]}
    assert len(new_vals) == 960 and not (new_vals & old_vals)
    assert len(new_vals) == len(set(m["planned_seeds"].values()))
    assert m["old_stream_exclusion"]["old_values_overlap"] == 0
    assert m["frozen_before_first_simulator_call"] is True
    audit = R.load(R.OUT / "m3s25r1_a1r_seed_audit.json")
    assert audit["per_stream_collisions"]["retired_old_arm_a_seeds"] == 0
    assert all(v == 0 for v in audit["per_stream_collisions"].values())
    assert R.sha_bytes(R.A1R_SEED_MANIFEST.read_bytes()) \
        == R.A1R_SEED_MANIFEST_PIN


def test_any_old_seed_in_new_stream_fails_audit():
    """If ANY of the old 960 seeds appears in the replacement stream, the
    audit hard-fails (mechanism test with a synthetic overlap)."""
    retired = R.load(R.A1R_RETIRED)
    old_seed = retired["units"][0]["seed"]
    plan = AA.arm_a_seed_plan(R.load(R.PANEL_JSON)["states"],
                              namespace=R.A1R_NAMESPACE)
    unit_id = next(iter(plan["planned_seeds"]))
    plan["planned_seeds"][unit_id] = old_seed
    with pytest.raises(RuntimeError, match="retired_old_arm_a_seeds"):
        AA.seed_collision_audit(
            plan,
            {"retired_old_arm_a_seeds": {u["seed"]
                                         for u in retired["units"]}},
            {})


def test_a1r_contract_budget_and_inheritance():
    c = R.load(R.A1R_CONTRACT)
    assert c["budget"] == {
        "n_trials": 960, "samples_per_trial": 20000,
        "replacement_planned": 19_200_000,
        "replacement_max": 19_200_000,
        "topup": 0, "substitution": 0,
        "old_invalid_stage_samples": 20_000,
        "cumulative_if_replacement_completes": 19_220_000,
        "rule": c["budget"]["rule"]}
    inh = c["scientific_inheritance"]
    assert inh["panel_body_sha256"] == AA.FROZEN_PANEL_SHA
    assert inh["panel_file_sha256"] == R.EXPECTED_PANEL_FILE_SHA
    assert inh["panel_truth_manifest_sha256"] == R.PANEL_TRUTH_MANIFEST_PIN
    assert inh["a0_rebind_contract_sha256"] == R.ARM_A_CONTRACT_PIN
    assert inh["S1_threshold_frozen"] == 5.4417199447782
    assert inh["alpha_p"] == 0.5
    assert c["corrected_instrumentation"]["code_sha256"][
        "src/hyptraj/m3s25r1/arm_a.py"] == R.sha(
        R.ROOT / "src/hyptraj/m3s25r1/arm_a.py")
    assert "stratified_bootstrap_gradient_ci" in \
        c["corrected_instrumentation"]["fix"]
    assert "MANDATORY" in c["corrected_instrumentation"]["crosscheck"]
    assert c["evaluation_protocol"]["terminal_names"] == {
        "success": "M3-S25-R1-A1R-A", "b_gate": "M3-S25-R1-A1R-B-GATE",
        "failure": "M3-S25-R1-A1R-X"}
    assert c["namespace"] == "M3-S25-R1-A1R-GRAD"
    assert R.sha_bytes(R.A1R_CONTRACT.read_bytes()) == R.A1R_CONTRACT_PIN


# --------------------------------------------------------------------------
# preflight (item 9)
# --------------------------------------------------------------------------

def test_a1r_preflight_full_checklist():
    pf = R.load(R.OUT / "m3s25r1_a1r_preflight.json")
    assert pf["PREFLIGHT_VERDICT"] == "PASS"
    assert pf["simulator_calls"] == 0 and pf["samples"] == 0
    for k in ("parent_incident_head_ancestor", "old_stage_terminal_x",
              "old_arm_a_gate_closed", "consumed_unit_retired",
              "old_seed_stream_excluded", "same_panel_and_contracts",
              "corrected_instrumentation_sha", "new_seeds_960_unique",
              "replacement_destination_empty", "reserve_untouched",
              "evaluation_truth_sealed", "a1r_arm_a_gate_no",
              "a1r_arm_b_gate_no", "zero_sampling", "truth_gate_closed",
              "old_arm_b_gate_no"):
        assert pf["checks"][k] is True, k


@pytest.fixture()
def protect_a1r_preflight_report():
    p = R.OUT / "m3s25r1_a1r_preflight.json"
    data = p.read_bytes()
    yield p
    p.write_bytes(data)


def test_a1r_preflight_cannot_flip_gates(protect_a1r_preflight_report):
    R.a1r_preflight()
    assert R.gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False


def test_old_seed_value_in_new_manifest_causes_preflight_failure(
        tmp_path, monkeypatch):
    """Any of the old 960 seeds appearing in the replacement stream
    causes a hard preflight failure (exclusion is mechanical)."""
    retired = R.load(R.A1R_RETIRED)
    old_seed = retired["units"][5]["seed"]
    m = json.loads(json.dumps(R.load(R.A1R_SEED_MANIFEST)))
    unit_id = next(iter(m["planned_seeds"]))
    m["planned_seeds"][unit_id] = old_seed
    m["units"] = [{"unit_id": u, "seed": s, "seed_key": [s, 42424],
                   "samples": 20000}
                  for u, s in m["planned_seeds"].items()]
    bad = tmp_path / "m3s25r1_a1r_seed_manifest.json"
    bad.write_text(json.dumps(m), encoding="utf-8")
    monkeypatch.setattr(R, "A1R_SEED_MANIFEST", bad)
    monkeypatch.setattr(R, "A1R_SEED_MANIFEST_PIN",
                        R.sha_bytes(bad.read_bytes()))
    with pytest.raises(RuntimeError, match="retired-seed overlap"):
        R.a1r_preflight()


# --------------------------------------------------------------------------
# mocked replacement route (item 11)
# --------------------------------------------------------------------------

def _mock_trial(monkeypatch, calls):
    def fake_arm_a_trial(st, seed_value, state_id, rep, config_id, s2,
                         contract_shas):
        calls["trials"] += 1
        rng = np.random.default_rng(seed_value % (2**31))
        record = {
            "schema": AA.TRIAL_SCHEMA, "recorded_at": None,
            "state_id": state_id, "rep_id": rep, "config_id": config_id,
            "s2": float(s2), "curvature_c": 0.5,
            "seed": int(seed_value), "namespace": R.A1R_NAMESPACE,
            "samples": AA.N_SAMPLES, "alpha_p": AA.ALPHA_P,
            "gradient": {"g_hat": float(rng.normal(0, 0.1)),
                         "g_ci_low": -0.5, "g_ci_high": 0.5,
                         "ESS_grad": 5000.0, "M2_hat": 0.01,
                         "responsibility_mass": 0.9, "D_hat": 0.02,
                         "problems": [], "s2_base": float(s2),
                         "batches": 20},
            "selected_action": "WIDEN", "S1": 1.0,
            "S1_threshold": AA.S1_THRESHOLD, "deployment": "ABSTAIN",
            "event_count": 500, "event_rate": 0.025, "valid": True,
            "estimator": "mocked", "estimator_crosscheck_exact": True,
            "instrumentation_schema": "m3s2s_instr_v1",
            "instrumentation_sha256": None,
            "contract_shas": dict(contract_shas), "z95": AA.Z95,
            "n_bootstrap": 500, "stream": "arm_a1r_gradient",
        }
        arrays = {"a_vec": rng.random(AA.N_SAMPLES),
                  "resp": rng.random(AA.N_SAMPLES),
                  "sq": rng.random(AA.N_SAMPLES),
                  "strata": rng.integers(0, 3, AA.N_SAMPLES),
                  "bootstrap_g": rng.normal(0, 0.1, 500)}
        return record, arrays

    monkeypatch.setattr(AA, "arm_a_trial", fake_arm_a_trial)


@pytest.fixture()
def a1r_route(tmp_path, monkeypatch):
    import tempfile
    calls = {"trials": 0}
    _mock_trial(monkeypatch, calls)
    monkeypatch.setattr(AE, "LOGISTIC_GRID",
                        [{"C": 1.0, "class_weight": None}])
    monkeypatch.setattr(AE, "GBDT_GRID",
                        [{"max_iter": 20, "max_leaf_nodes": 7,
                          "learning_rate": 0.1, "l2_regularization": 0,
                          "random_state": 2026}])
    root = Path(tempfile.mkdtemp(prefix="a1rt_"))
    a_dir = root / "arm_a1r"
    monkeypatch.setattr(R, "A1R_TRIALS", a_dir / "trials")
    monkeypatch.setattr(R, "A1R_LEDGER", a_dir / "trial_ledger.jsonl")
    tsum = root / "summary"
    monkeypatch.setattr(R, "A1R_EVAL", tsum / "m3s25r1_a1r_evaluation.json")
    monkeypatch.setattr(R, "SUM", tsum)
    tsum.mkdir(parents=True, exist_ok=True)
    (tsum / "m3s25r1_panel_decision.json").write_bytes(
        (R.ROOT / "results/phase_m3s25r1/summary/"
         "m3s25r1_panel_decision.json").read_bytes())
    yield {"calls": calls, "tmp": root}
    shutil.rmtree(root, ignore_errors=True)


def test_old_ledger_cannot_be_resumed():
    """The old stage stays terminal: its restart scan fails closed on the
    consumed unit (no resume, no replay) even with the (now closed) old
    gate irrelevant -- the scan precedes everything."""
    led = R.ledger_entries(R.ARM_A_LEDGER)
    assert sum(1 for e in led if e.get("status") == "CONSUMED_INVALID") == 1
    # the old-stage restart scan FAILS CLOSED on the consumed unit --
    # the old ledger cannot be resumed (this IS the no-resume proof)
    with pytest.raises(RuntimeError, match="CONSUMED_INVALID"):
        R._arm_a_restart_scan(R.load(R.PANEL_JSON)["states"])
    consumed_unit = "m3s2s_cfg_001_s2s_0.5708962241|rep0"
    with pytest.raises(RuntimeError, match="CONSUMED_INVALID"):
        AA.verify_arm_a_trial_fresh_or_verified(
            consumed_unit, R.ARM_A_TRIALS / "x" / "rep0.json",
            R.ARM_A_TRIALS / "x" / "rep0_instrumentation.npz", led,
            R.record_file_hash, R.record_file_hash)


def test_route_a1r_execute_gated_refusal(a1r_route):
    """With the A1R gate NO, the replacement execution refuses BEFORE any
    write."""
    with pytest.raises(RuntimeError,
                       match="M3_S25_R1_A1R_ARM_A_AUTHORIZED is not YES"):
        R.arm_a1r_execute()
    assert a1r_route["calls"]["trials"] == 0
    assert not R.A1R_TRIALS.exists()


def test_route_a1r_no_arm_b_execution(a1r_route, monkeypatch):
    """If any Arm-B gate were YES, the replacement execution refuses
    (no Arm-B execution exists anywhere in A1R)."""
    approval = a1r_route["tmp"] / "approval_b.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_A1R_ARM_B_AUTHORIZED: YES\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    with pytest.raises(RuntimeError, match="Arm B must remain NO"):
        R.arm_a1r_execute()
    assert a1r_route["calls"]["trials"] == 0


def test_route_a1r_execute_960_and_evaluate(a1r_route, monkeypatch):
    """Full mocked replacement route: gate YES -> 960/960 durable
    COMPLETE on the NEW ledger -> replacement 19,200,000 with the old 20k
    reported separately -> truth unseal AFTER completeness -> grouped
    evaluation -> A1R-local verdict."""
    calls = a1r_route["calls"]
    approval = a1r_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n"
                        "M3_S25_R1_A1R_ARM_A_AUTHORIZED: YES\n"
                        "M3_S25_R1_A1R_ARM_B_AUTHORIZED: NO\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    summary = R.arm_a1r_execute()
    assert calls["trials"] == 960
    assert summary["n_trials"] == 960
    assert summary["CONSUMED_INVALID"] == 0
    assert summary["replacement_samples"] == 19_200_000
    assert summary["replacement_planned"] == 19_200_000
    assert summary["old_invalid_stage_samples"] == 20_000
    assert summary["cumulative_project_samples"] == 19_220_000
    entries = R.ledger_entries(R.A1R_LEDGER)
    assert Counter(e["status"] for e in entries) == {"STARTED": 960,
                                                     "COMPLETE": 960}
    # every namespace is the NEW one; the old stream is untouched
    assert all(e.get("seed_namespace") == "M3-S25-R1-A1R-GRAD"
               for e in entries)
    old_ledger = R.ledger_entries(R.ARM_A_LEDGER)
    assert sum(1 for e in old_ledger
               if e.get("status") == "CONSUMED_INVALID") == 1
    # restart-safe: a second execute skips all 960 verified trials
    calls["trials"] = 0
    R.arm_a1r_execute()
    assert calls["trials"] == 0

    out = R.arm_a1r_evaluate()
    assert out["truth_manifest_unsealed"]["after_complete_960"] is True
    assert out["truth_manifest_unsealed"]["sha256"] == \
        R.PANEL_TRUTH_MANIFEST_PIN
    assert out["results"]["n_trials"] == 960
    assert out["verdict"]["VERDICT"] in ("M3-S25-R1-A1R-A",
                                         "M3-S25-R1-A1R-B-GATE")


def test_route_a1r_truth_sealed_until_960(a1r_route, monkeypatch):
    """The truth manifest unseals ONLY after 960/960 durable COMPLETE on
    the replacement ledger; the old 20k never counts."""
    approval = a1r_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_A1R_ARM_A_AUTHORIZED: YES\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    R.arm_a1r_execute()
    entries = R.ledger_entries(R.A1R_LEDGER)
    keep = [e for e in entries
            if not (e["status"] == "COMPLETE"
                    and e["state_id"].endswith("|rep3"))]
    with R.A1R_LEDGER.open("w", encoding="utf-8") as h:
        for e in keep:
            h.write(json.dumps(e) + "\n")
    with pytest.raises(RuntimeError, match="960/960"):
        R.arm_a1r_evaluate()


def test_route_a1r_consumed_invalid_terminates_stage(a1r_route,
                                                     monkeypatch):
    """A replacement consumed-invalid unit => M3-S25-R1-A1R-X => STOP =>
    NO REPLAY (mocked trial that dies after sampling)."""
    approval = a1r_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_A1R_ARM_A_AUTHORIZED: YES\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)

    def exploding_trial(*a, **k):
        raise RuntimeError("injected post-sampling failure")

    monkeypatch.setattr(AA, "arm_a_trial", exploding_trial)
    with pytest.raises(RuntimeError, match="M3-S25-R1-A1R-X"):
        R.arm_a1r_execute()
    led = R.ledger_entries(R.A1R_LEDGER)
    assert sum(1 for e in led if e.get("status") == "CONSUMED_INVALID") == 1
    assert sum(1 for e in led if e.get("status") == "COMPLETE") == 0


def test_route_gates_stay_no_after_all_a1r_tests():
    assert R.gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED") is False
    assert not R.gate("M3_S25_R1_TRUTH_AUTHORIZED")
    assert not R.gate("M3_S25_R1_ARM_B_AUTHORIZED")
