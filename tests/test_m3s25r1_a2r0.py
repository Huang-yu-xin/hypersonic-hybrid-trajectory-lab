"""M3-S25-R1-A2R0 tests: Inherited-269 Completion Preregistration (zero sampling).

Route tests run the REAL control flow with MOCKED trials -- the real
simulator is never invoked.  The 269 durable COMPLETE A1R records are
inherited (hash-pinned in place, never copied).  The 691 missing slots
(including the 1 CONSUMED_INVALID unit) get entirely new A2R seeds.
The old A1R 960-seed stream is fully retired.  The bounded fsync retry
retries ONLY the directory durability operation, never the simulator.
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
from hyptraj.m3cf1r0.persistence import (  # noqa: E402
    fsync_directory, fsync_directory_bounded_retry,
    _is_transient_fsync_failure)
from hyptraj.m3wa1r.persistence import run_trial_transactional  # noqa: E402


# --------------------------------------------------------------------------
# §11 gates
# --------------------------------------------------------------------------

def test_gate_state_after_a2r0():
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A2R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A2R_ARM_B_AUTHORIZED") is False
    txt = R.APPROVAL_DOC.read_text(encoding="utf-8")
    assert "M3_S25_R1_A2R_ARM_A_AUTHORIZED: NO" in txt
    assert "M3_S25_R1_A2R_ARM_B_AUTHORIZED: NO" in txt


# --------------------------------------------------------------------------
# §2 inheritance manifest
# --------------------------------------------------------------------------

def test_inheritance_manifest_269_complete():
    m = R.load(R.A2R_INHERITANCE)
    assert m["inherited_count"] == 269
    assert m["missing_count"] == 691
    assert m["total_effective_trials"] == 960
    assert len(m["inherited_units"]) == 269
    assert len(m["missing_slots"]) == 691
    # ALL-269-or-none
    inherited_ids = {u["unit_id"] for u in m["inherited_units"]}
    missing_set = set(m["missing_slots"])
    assert not (inherited_ids & missing_set)
    assert len(inherited_ids | missing_set) == 960
    # each inherited unit has full provenance
    for u in m["inherited_units"]:
        assert u["unit_id"]
        assert u["state_id"]
        assert u["rep"] is not None
        assert u["config_id"]
        assert u["a1r_seed"] > 0
        assert u["a1r_seed_key"] == [u["a1r_seed"], 42424]
        assert u["namespace"] == "M3-S25-R1-A1R-GRAD"
        assert u["record_path"]
        assert u["record_file_sha256"]
        assert u["scientific_payload_sha256"]
        assert u["sidecar_path"]
        assert u["sidecar_sha256"]
        assert u["complete_ledger_evidence"]["status"] == "COMPLETE"
        assert u["inherited_from"] == "M3-S25-R1-A1R"
    # SHA pin
    assert R.sha_bytes(R.A2R_INHERITANCE.read_bytes()) == R.A2R_INHERITANCE_PIN


def test_invalid_unit_excluded():
    """§3: the CONSUMED_INVALID unit is permanently excluded."""
    m = R.load(R.A2R_INHERITANCE)
    assert m["invalid_unit"]["unit_id"] == "c020_s25r1_3.8634000847|rep5"
    assert m["invalid_unit"]["unit_id"] in set(m["missing_slots"])
    assert m["invalid_unit"]["unit_id"] not in {
        u["unit_id"] for u in m["inherited_units"]}
    assert "EXCLUDED" in m["invalid_unit"]["status"]


def test_no_truth_labels_in_manifest():
    """§2: no truth labels may enter the inheritance manifest."""
    m = R.load(R.A2R_INHERITANCE)
    for u in m["inherited_units"]:
        assert "confirmed_truth" not in u
        assert "corrected_class" not in u
        assert "truth" not in u or u.get("inherited_from") == "M3-S25-R1-A1R"
    assert m.get("no_truth_labels") is True


def test_inherited_records_hash_pinned_in_place():
    """§2: inherited records are referenced and hash-pinned, not copied."""
    m = R.load(R.A2R_INHERITANCE)
    for u in m["inherited_units"]:
        rec_path = R.ROOT / u["record_path"]
        assert rec_path.exists(), f"missing inherited record: {rec_path}"
        side_path = R.ROOT / u["sidecar_path"]
        assert side_path.exists(), f"missing inherited sidecar: {side_path}"
        # record file SHA matches
        assert R.record_file_hash(rec_path) == u["record_file_sha256"]
        # sidecar SHA matches
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        assert rec.get("instrumentation_sha256") == u["sidecar_sha256"]


# --------------------------------------------------------------------------
# §5 retired stream + new seeds
# --------------------------------------------------------------------------

def test_retired_stream_960_seeds():
    r = R.load(R.A2R_RETIRED)
    assert r["old_terminal"] == "M3-S25-R1-A1R-X"
    assert r["old_terminal_head"] == R.A2R_A1R_TERMINAL_HEAD
    assert len(r["units"]) == 960
    assert r["counts"] == {"total_units": 960, "inherited_complete": 269,
                           "consumed_invalid": 1, "never_started": 690}
    inherited = [u for u in r["units"]
                if u["status"] == "INHERITED_COMPLETE_PROVENANCE_ONLY"]
    assert len(inherited) == 269
    assert R.sha_bytes(R.A2R_RETIRED.read_bytes()) == R.A2R_RETIRED_PIN


def test_new_seeds_691_unique_and_disjoint():
    m = R.load(R.A2R_SEED_MANIFEST)
    assert m["namespace"] == "M3-S25-R1-A2R-GRAD"
    assert m["n_units"] == 691
    new_vals = set(m["planned_seeds"].values())
    assert len(new_vals) == 691 and len(new_vals) == len(m["planned_seeds"])
    # zero overlap with retired A1R seeds
    retired = R.load(R.A2R_RETIRED)
    old_vals = {u["seed"] for u in retired["units"]}
    assert not (new_vals & old_vals)
    # zero overlap with old Arm-A seeds
    old_arm_a = R.load(R.A1R_RETIRED)
    arm_a_vals = {u["seed"] for u in old_arm_a["units"]}
    assert not (new_vals & arm_a_vals)
    audit = R.load(R.OUT / "m3s25r1_a2r_seed_audit.json")
    assert audit["unique_seeds"] == 691
    assert all(v == 0 for v in audit["per_stream_collisions"].values())
    assert R.sha_bytes(R.A2R_SEED_MANIFEST.read_bytes()) == R.A2R_SEED_MANIFEST_PIN


# --------------------------------------------------------------------------
# §6-7 contract + budget
# --------------------------------------------------------------------------

def test_a2r_contract_budget_and_inheritance():
    c = R.load(R.A2R_CONTRACT)
    b = c["budget"]
    assert b["inherited_trials"] == 269
    assert b["new_trials"] == 691
    assert b["total_effective_trials"] == 960
    assert b["inherited_samples"] == 5_380_000
    assert b["new_planned"] == 13_820_000
    assert b["new_max"] == 13_820_000
    assert b["effective_final_dataset"] == 19_200_000
    assert b["topup"] == 0 and b["substitution"] == 0
    assert b["old_arm_a_invalid_samples"] == 20_000
    assert b["a1r_invalid_samples"] == 20_000
    assert b["cumulative_if_a2r_completes"] == 19_240_000
    inh = c["scientific_inheritance"]
    assert inh["panel_body_sha256"] == AA.FROZEN_PANEL_SHA
    assert inh["panel_file_sha256"] == R.EXPECTED_PANEL_FILE_SHA
    assert inh["panel_truth_manifest_sha256"] == R.PANEL_TRUTH_MANIFEST_PIN
    assert inh["S1_threshold_frozen"] == 5.4417199447782
    assert c["namespace"] == "M3-S25-R1-A2R-GRAD"
    assert c["evaluation_protocol"]["terminal_names"] == {
        "success": "M3-S25-R1-A2R-A",
        "b_gate": "M3-S25-R1-A2R-B-GATE",
        "failure": "M3-S25-R1-A2R-X"}
    assert c["corrected_instrumentation"]["bounded_dir_fsync_retry"]["max_attempts"] == 5
    assert R.sha_bytes(R.A2R_CONTRACT.read_bytes()) == R.A2R_CONTRACT_PIN


# --------------------------------------------------------------------------
# §12 preflight
# --------------------------------------------------------------------------

def test_a2r_preflight_full_checklist():
    pf = R.load(R.OUT / "m3s25r1_a2r_preflight.json")
    assert pf["PREFLIGHT_VERDICT"] == "PASS"
    assert pf["simulator_calls"] == 0 and pf["samples"] == 0
    for k in ("a1r_terminal_head_ancestor", "a1r_terminal_269_complete",
              "a1r_terminal_1_consumed_invalid",
              "a1r_terminal_690_never_started",
              "a1r_arm_a_gate_closed", "a2r_arm_a_gate_no",
              "a2r_arm_b_gate_no", "truth_gate_closed",
              "old_arm_a_gate_closed", "arm_b_gate_no",
              "frozen_inputs_verified", "inheritance_269",
              "inheritance_691_missing", "inheritance_all_269_or_none",
              "invalid_unit_excluded", "no_truth_labels_in_manifest",
              "old_a1r_seed_stream_excluded", "new_seeds_691_unique",
              "same_panel_and_contracts", "corrected_instrumentation_sha",
              "a2r_destination_empty", "evaluation_truth_sealed",
              "zero_sampling"):
        assert pf["checks"][k] is True, k


@pytest.fixture()
def protect_a2r_preflight_report():
    p = R.OUT / "m3s25r1_a2r_preflight.json"
    data = p.read_bytes()
    yield p
    p.write_bytes(data)


def test_a2r_preflight_cannot_flip_gates(protect_a2r_preflight_report):
    R.a2r_preflight()
    assert R.gate("M3_S25_R1_A2R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A2R_ARM_B_AUTHORIZED") is False


# --------------------------------------------------------------------------
# §8 bounded fsync retry (never reruns the simulator)
# --------------------------------------------------------------------------

def test_transient_fsync_failure_detection():
    """Only Windows sharing/locking errors are retried."""
    assert _is_transient_fsync_failure({
        "pass": False, "exception_type": "BrokenPipeError",
        "exception_message": "[Errno 32] CreateFileW(directory) failed"})
    assert _is_transient_fsync_failure({
        "pass": False, "exception_type": "OSError",
        "exception_message": "[Errno 33] LockViolation"})
    assert not _is_transient_fsync_failure({
        "pass": False, "exception_type": "OSError",
        "exception_message": "[Errno 13] Permission denied"})
    assert not _is_transient_fsync_failure({"pass": True})


def test_bounded_retry_succeeds_after_transient_failures():
    """Several fsync failures followed by success: the retry function
    eventually succeeds without the caller giving up."""
    calls = {"n": 0}

    def flaky_fsync(path):
        calls["n"] += 1
        if calls["n"] < 3:
            return {"pass": False, "method": "test",
                    "exception_type": "BrokenPipeError",
                    "exception_message": "[Errno 32] sharing violation"}
        return {"pass": True, "method": "test"}

    import hyptraj.m3cf1r0.persistence as P
    orig = P.fsync_directory
    try:
        P.fsync_directory = flaky_fsync
        sleeps = []
        result = fsync_directory_bounded_retry(
            "/tmp", sleep_fn=lambda d: sleeps.append(d))
        assert result["pass"] is True
        assert result["attempts"] == 3
        assert len(sleeps) == 2  # backoff before attempts 1 and 2
    finally:
        P.fsync_directory = orig


def test_bounded_retry_exhausted_returns_failure():
    """All attempts fail => pass: False (=> CONSUMED_INVALID => STOP)."""
    def always_fail(path):
        return {"pass": False, "method": "test",
                "exception_type": "BrokenPipeError",
                "exception_message": "[Errno 32] sharing violation"}

    import hyptraj.m3cf1r0.persistence as P
    orig = P.fsync_directory
    try:
        P.fsync_directory = always_fail
        result = fsync_directory_bounded_retry(
            "/tmp", sleep_fn=lambda d: None)
        assert result["pass"] is False
        assert result["attempts"] == 5
        assert result["retry_stopped"] == "max_attempts_exhausted"
    finally:
        P.fsync_directory = orig


def test_fsync_retry_never_reruns_simulator(tmp_path):
    """The bounded retry retries ONLY the directory durability operation;
    the simulator (compute function) is called exactly ONCE even when
    the fsync fails multiple times.  The retry wraps fsync_directory; the
    caller (run_trial_transactional) sees only the final pass/fail."""
    sim_calls = {"n": 0}
    raw_fsync_calls = {"n": 0}

    def compute():
        sim_calls["n"] += 1
        return {"schema": AA.TRIAL_SCHEMA, "value": 42}

    def validate(payload):
        pass  # accept anything

    import hyptraj.m3cf1r0.persistence as P
    orig = P.fsync_directory

    def flaky_raw_fsync(path):
        raw_fsync_calls["n"] += 1
        if raw_fsync_calls["n"] < 4:
            return {"pass": False, "method": "test",
                    "exception_type": "BrokenPipeError",
                    "exception_message": "[Errno 32] sharing"}
        return {"pass": True, "method": "test"}

    try:
        P.fsync_directory = flaky_raw_fsync
        # the bounded retry wraps the (now-flaky) fsync_directory
        dir_fsync_fn = fsync_directory_bounded_retry
        rec_path = tmp_path / "rec.json"
        ledger = tmp_path / "ledger.jsonl"
        result = run_trial_transactional(
            "test_unit", rec_path, compute,
            ledger_path=ledger, pre_hash_validator=validate,
            dir_fsync_fn=dir_fsync_fn)
        assert result["status"] == "COMPLETE"
        assert sim_calls["n"] == 1  # simulator called EXACTLY ONCE
        assert raw_fsync_calls["n"] >= 4  # raw fsync retried
    finally:
        P.fsync_directory = orig


# --------------------------------------------------------------------------
# §12 mocked execute + evaluate route
# --------------------------------------------------------------------------

def _mock_trial(monkeypatch, calls):
    def fake_arm_a_trial(st, seed_value, state_id, rep, config_id, s2,
                         contract_shas, namespace=R.A2R_NAMESPACE):
        calls["trials"] += 1
        rng = np.random.default_rng(seed_value % (2**31))
        record = {
            "schema": AA.TRIAL_SCHEMA, "recorded_at": None,
            "state_id": state_id, "rep_id": rep, "config_id": config_id,
            "s2": float(s2), "curvature_c": 0.5,
            "seed": int(seed_value), "namespace": R.A2R_NAMESPACE,
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
            "n_bootstrap": 500, "stream": "arm_a2r_gradient",
        }
        arrays = {"a_vec": rng.random(AA.N_SAMPLES),
                  "resp": rng.random(AA.N_SAMPLES),
                  "sq": rng.random(AA.N_SAMPLES),
                  "strata": rng.integers(0, 3, AA.N_SAMPLES),
                  "bootstrap_g": rng.normal(0, 0.1, 500)}
        return record, arrays

    monkeypatch.setattr(AA, "arm_a_trial", fake_arm_a_trial)


@pytest.fixture()
def a2r_route(tmp_path, monkeypatch):
    calls = {"trials": 0}
    _mock_trial(monkeypatch, calls)
    monkeypatch.setattr(AE, "LOGISTIC_GRID",
                        [{"C": 1.0, "class_weight": None}])
    monkeypatch.setattr(AE, "GBDT_GRID",
                        [{"max_iter": 20, "max_leaf_nodes": 7,
                          "learning_rate": 0.1, "l2_regularization": 0,
                          "random_state": 2026}])
    root = Path(tempfile.mkdtemp(prefix="a2rt_"))
    a_dir = root / "arm_a2r"
    monkeypatch.setattr(R, "A2R_TRIALS", a_dir / "trials")
    monkeypatch.setattr(R, "A2R_LEDGER", a_dir / "trial_ledger.jsonl")
    tsum = root / "summary"
    monkeypatch.setattr(R, "A2R_EVAL", tsum / "m3s25r1_a2r_evaluation.json")
    monkeypatch.setattr(R, "SUM", tsum)
    tsum.mkdir(parents=True, exist_ok=True)
    (tsum / "m3s25r1_panel_decision.json").write_bytes(
        (R.ROOT / "results/phase_m3s25r1/summary/"
         "m3s25r1_panel_decision.json").read_bytes())
    yield {"calls": calls, "tmp": root}
    shutil.rmtree(root, ignore_errors=True)


def test_route_a2r_execute_gated_refusal(a2r_route):
    """With the A2R gate NO, execution refuses BEFORE any write."""
    with pytest.raises(RuntimeError,
                       match="M3_S25_R1_A2R_ARM_A_AUTHORIZED is not YES"):
        R.arm_a2r_execute()
    assert a2r_route["calls"]["trials"] == 0
    assert not R.A2R_TRIALS.exists()


def test_route_a2r_no_arm_b_execution(a2r_route, monkeypatch):
    approval = a2r_route["tmp"] / "approval_b.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_A2R_ARM_B_AUTHORIZED: YES\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    with pytest.raises(RuntimeError, match="Arm B must remain NO"):
        R.arm_a2r_execute()
    assert a2r_route["calls"]["trials"] == 0


def test_route_a2r_execute_691_and_evaluate(a2r_route, monkeypatch):
    """Full mocked route: gate YES -> 691/691 new durable COMPLETE + 269
    inherited = 960 effective -> truth unseal -> A2R-local verdict."""
    calls = a2r_route["calls"]
    approval = a2r_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n"
                        "M3_S25_R1_A1R_ARM_A_AUTHORIZED: NO\n"
                        "M3_S25_R1_A1R_ARM_B_AUTHORIZED: NO\n"
                        "M3_S25_R1_A2R_ARM_A_AUTHORIZED: YES\n"
                        "M3_S25_R1_A2R_ARM_B_AUTHORIZED: NO\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    summary = R.arm_a2r_execute()
    assert calls["trials"] == 691  # only the 691 new slots
    assert summary["inherited_trials"] == 269
    assert summary["new_trials"] == 691
    assert summary["new_CONSUMED_INVALID"] == 0
    assert summary["effective_trials"] == 960
    assert summary["effective_samples"] == 19_200_000
    assert summary["new_samples"] == 13_820_000
    assert summary["inherited_samples"] == 5_380_000
    assert summary["cumulative_project_samples"] == 19_240_000
    entries = R.ledger_entries(R.A2R_LEDGER)
    assert Counter(e["status"] for e in entries) == {"STARTED": 691,
                                                     "COMPLETE": 691}
    assert all(e.get("seed_namespace") == "M3-S25-R1-A2R-GRAD"
               for e in entries)
    # restart-safe: a second execute skips all 691 verified trials
    calls["trials"] = 0
    R.arm_a2r_execute()
    assert calls["trials"] == 0

    out = R.arm_a2r_evaluate()
    assert out["truth_manifest_unsealed"]["after_complete_960"] is True
    assert out["truth_manifest_unsealed"]["sha256"] == \
        R.PANEL_TRUTH_MANIFEST_PIN
    assert out["results"]["n_trials"] == 960
    assert out["verdict"]["VERDICT"] in ("M3-S25-R1-A2R-A",
                                         "M3-S25-R1-A2R-B-GATE")


def test_route_a2r_truth_sealed_until_960(a2r_route, monkeypatch):
    """Truth unseals ONLY after 269 inherited + 691 new = 960 effective."""
    approval = a2r_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_A2R_ARM_A_AUTHORIZED: YES\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    R.arm_a2r_execute()
    entries = R.ledger_entries(R.A2R_LEDGER)
    keep = [e for e in entries
            if not (e["status"] == "COMPLETE"
                    and e["state_id"].endswith("|rep3"))]
    with R.A2R_LEDGER.open("w", encoding="utf-8") as h:
        for e in keep:
            h.write(json.dumps(e) + "\n")
    with pytest.raises(RuntimeError, match="691"):
        R.arm_a2r_evaluate()


def test_route_a2r_consumed_invalid_terminates(a2r_route, monkeypatch):
    """A2R CONSUMED_INVALID => M3-S25-R1-A2R-X => STOP => NO REPLAY."""
    approval = a2r_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_A2R_ARM_A_AUTHORIZED: YES\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)

    def exploding_trial(*a, **k):
        raise RuntimeError("injected post-sampling failure")

    monkeypatch.setattr(AA, "arm_a_trial", exploding_trial)
    with pytest.raises(RuntimeError, match="M3-S25-R1-A2R-X"):
        R.arm_a2r_execute()
    led = R.ledger_entries(R.A2R_LEDGER)
    assert sum(1 for e in led if e.get("status") == "CONSUMED_INVALID") == 1
    assert sum(1 for e in led if e.get("status") == "COMPLETE") == 0


def test_route_gates_stay_no_after_all_a2r_tests():
    assert R.gate("M3_S25_R1_A2R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A2R_ARM_B_AUTHORIZED") is False
    assert not R.gate("M3_S25_R1_TRUTH_AUTHORIZED")
    assert not R.gate("M3_S25_R1_ARM_B_AUTHORIZED")
