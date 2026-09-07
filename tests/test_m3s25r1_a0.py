"""M3-S25-R1-A0 tests: Arm-A rebind & execution readiness (zero sampling).

All route tests run the REAL control flow with MOCKED trials/evaluation
grids -- the real simulator is never invoked (A0 has zero simulator
calls).  The panel truth manifest stays sealed during sampling and is
unsealed ONLY after 960/960 durable COMPLETE.
"""
from __future__ import annotations

import json
import subprocess
import sys
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
# gates + truth closure
# --------------------------------------------------------------------------

def test_gate_state_per_authorization():
    """Post-A0.2-audit authorized state: TRUTH closed, ARM A YES (as
    granted), ARM B NO."""
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is True
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False
    txt = R.APPROVAL_DOC.read_text(encoding="utf-8")
    assert "M3_S25_R1_TRUTH_AUTHORIZED: NO" in txt
    assert "M3_S25_R1_ARM_A_AUTHORIZED: YES" in txt
    assert "M3_S25_R1_ARM_B_AUTHORIZED: NO" in txt
    assert "status = CLOSED / EXERCISED" in txt
    assert R.TRUTH_TERMINAL_HEAD in txt
    assert "DO NOT execute Arm B" in txt


# --------------------------------------------------------------------------
# panel truth manifest (A0 item 2)
# --------------------------------------------------------------------------

def test_panel_truth_manifest_frozen_and_bound():
    m = R.load(R.PANEL_TRUTH_MANIFEST)
    panel = R.load(R.CFG / "m3s25r1_panel.json")
    assert m["n_states"] == 120 and len(m["states"]) == 120
    assert m["panel_body_sha256"] == panel["panel_sha256"] == AA.FROZEN_PANEL_SHA
    assert m["panel_file_sha256"] == R.sha(R.CFG / "m3s25r1_panel.json")
    assert "SEALED" in m["role"] and "evaluation-only" in m["role"]
    required = {"state_id", "truth", "config_id", "source_stage", "s2", "u",
                "rank", "truth_artifact_hash"}
    assert all(required <= set(s) for s in m["states"])
    audit = R.load(R.OUT / "m3s25r1_panel_truth_manifest_audit.json")
    assert audit["PANEL_TRUTH_MANIFEST_AUDIT"] == "PASS"
    assert audit["composition"] == {"WIDEN": 30, "SHRINK": 30, "HOLD": 30,
                                    "AMBIGUOUS": 30}
    assert audit["source_mix"] == {"M3-S25-R1": 83, "M3-S2S": 37}
    assert all(s["source_stage"] == "M3-S25-R1"
               for s in m["states"] if s["truth"] == "SHRINK")
    assert sum(1 for s in m["states"] if s["truth"] == "SHRINK") == 30


# --------------------------------------------------------------------------
# Arm-A rebind contract + seeds (A0 item 3)
# --------------------------------------------------------------------------

def test_arm_a_contract_inherits_parent_contracts():
    c = R.load(R.ARM_A_CONTRACT)
    hashes = c["inherited_parent_contract_sha256"]
    assert set(hashes) == set(R.PARENT_CONTRACTS)
    for name, h in hashes.items():
        assert R.sha(R.ROOT / "configs/phase_m3s2s" / name) == h, name
    assert "gradient_decision" in c["estimator"]
    assert "unmodified" in c["estimator"]
    assert c["alpha_p"] == 0.5
    assert c["S1_threshold_frozen"] == 5.4417199447782
    assert c["trials"] == {"states": 120, "replicates": 8,
                           "samples_per_trial": 20000, "n_trials": 960,
                           "ARM_A_BUDGET": 19_200_000, "no_topup": True}
    assert c["namespace"] == "M3-S25-R1-A-GRAD"
    assert c["instrumentation"]["schema"] == "m3s2s_instr_v1"
    assert c["instrumentation"]["N_BOOTSTRAP"] == 500
    assert c["safety_gates"] == {"coverage_min": 0.75, "unsafe_max": 0.20,
                                 "wrong_max": 0.05,
                                 "ambiguous_unsafe_max": 0.25}
    assert c["verdicts"] == {"success": "M3-S25-R1-A",
                             "b_gate": "M3-S25-R1-B-GATE",
                             "failure": "M3-S25-R1-X"}
    assert "SEALED" in c["truth_manifest_rule"]
    assert R.sha_bytes(R.ARM_A_CONTRACT.read_bytes()) == R.ARM_A_CONTRACT_PIN


def test_arm_a_seed_manifest_960_unique():
    m = R.load(R.ARM_A_SEED_MANIFEST)
    assert m["namespace"] == "M3-S25-R1-A-GRAD"
    assert m["n_units"] == 960 and m["n_trials"] == 960
    assert m["budget"] == 19_200_000
    assert m["frozen_before_first_simulator_call"] is True
    vals = list(m["planned_seeds"].values())
    assert len(set(vals)) == 960
    # deterministic derivation
    sid0, rep0 = next(iter(m["planned_seeds"])).split("|rep")
    assert m["planned_seeds"][f"{sid0}|rep{rep0}"] == AA.seed(
        "M3-S25-R1-A-GRAD", sid0, int(rep0))
    audit = R.load(R.OUT / "m3s25r1_arm_a_seed_audit.json")
    assert audit["units"] == 960 and audit["unique_seeds"] == 960
    assert audit["historical_collision"] == 0
    assert audit["truth_stream_collision"] == 0
    assert audit["ARM_A_SEED_AUDIT"] == "PASS"
    # no truth-stream collision (mechanical re-check)
    r1_truth = R.load(R.CFG / "m3s25r1_truth_seed_manifest.json")
    assert {tuple(u["seed_key"]) for u in m["units"]}.isdisjoint(
        {tuple(u["seed_key"]) for u in r1_truth["units"]})
    assert R.sha_bytes(R.ARM_A_SEED_MANIFEST.read_bytes()) \
        == R.ARM_A_SEED_MANIFEST_PIN


def test_panel_truth_manifest_pinned():
    assert R.sha_bytes(R.PANEL_TRUTH_MANIFEST.read_bytes()) \
        == R.PANEL_TRUTH_MANIFEST_PIN


# --------------------------------------------------------------------------
# arm_a preflight (A0 item 6)
# --------------------------------------------------------------------------

def test_arm_a_preflight_full_checklist():
    pf = R.load(R.OUT / "m3s25r1_arm_a_preflight.json")
    assert pf["PREFLIGHT_VERDICT"] == "PASS"
    assert pf["overall"].startswith("ARM-A EXECUTION-READY")
    assert pf["simulator_calls"] == 0 and pf["samples"] == 0
    assert pf["arm_a_budget"] == 19_200_000
    for k in ("parent_head_ancestor", "truth_terminal_head_ancestor",
              "truth_stage_panel_frozen", "frozen_panel_sha",
              "panel_truth_manifest", "panel_identity_120",
              "seeds_960_unique", "seed_collisions_zero",
              "reserve_18_untouched", "destination_empty", "path_length_ok",
              "disk_ok", "groupkfold_feasible",
              "inherited_contract_hashes", "arm_a_gate_no", "arm_b_gate_no",
              "truth_gate_closed"):
        assert pf["checks"][k] is True, k
    assert pf["frozen_pins"]["universe_sha256"] == R.EXPECTED_UNIVERSE_SHA


def test_arm_a_preflight_frozen_readiness_record():
    """The FROZEN pre-arm-A-authorization readiness report stays PASS
    (it was produced while the gate was NO); the live gate is now the
    authorized YES, so the preflight is NOT re-run post-authorization
    (its fail-closed gate/destination checks reflect the readiness
    round by design)."""
    pf = R.load(R.OUT / "m3s25r1_arm_a_preflight.json")
    assert pf["PREFLIGHT_VERDICT"] == "PASS"
    assert pf["checks"]["arm_a_gate_no"] is True   # readiness round
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is True
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False


# --------------------------------------------------------------------------
# restart integrity (A0 item 5)
# --------------------------------------------------------------------------

def _mk_trial(tmp_path, statuses="SC", tamper=None, with_sidecar=True):
    out = tmp_path / "out" / "rep0.json"
    side = tmp_path / "out" / "rep0_instrumentation.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    rec = {"schema": AA.TRIAL_SCHEMA, "state_id": "s0",
           "instrumentation_sha256": None}
    if with_sidecar:
        np.savez_compressed(side, a_vec=np.zeros(4), resp=np.zeros(4),
                            sq=np.zeros(4), strata=np.zeros(4, dtype=int),
                            bootstrap_g=np.zeros(3))
        rec["instrumentation_sha256"] = R.record_file_hash(side)
    out.write_text(json.dumps(rec), encoding="utf-8")
    entries = []
    if "S" in statuses:
        entries.append({"state_id": "u1", "status": "STARTED"})
    if "C" in statuses:
        entries.append({"state_id": "u1", "status": "COMPLETE",
                        "record_file_hash": R.record_file_hash(out)})
    if tamper == "record":
        # tamper AFTER the ledger hash was captured
        rec["state_id"] = "tampered"
        out.write_text(json.dumps(rec), encoding="utf-8")
    return out, side, entries


def test_arm_a_restart_fresh_and_valid_complete(tmp_path):
    out = tmp_path / "o" / "rep0.json"
    side = tmp_path / "o" / "rep0_instrumentation.npz"
    assert AA.verify_arm_a_trial_fresh_or_verified(
        "u1", out, side, [], R.record_file_hash, R.record_file_hash) is None
    o, s, entries = _mk_trial(tmp_path, "SC")
    rec = AA.verify_arm_a_trial_fresh_or_verified(
        "u1", o, s, entries, R.record_file_hash, R.record_file_hash)
    assert rec["schema"] == AA.TRIAL_SCHEMA


def test_arm_a_restart_failures(tmp_path):
    o, s, entries = _mk_trial(tmp_path, "S", with_sidecar=False)
    with pytest.raises(RuntimeError, match="STARTED-only"):
        AA.verify_arm_a_trial_fresh_or_verified(
            "u1", o, s, entries, R.record_file_hash, R.record_file_hash)
    o, s, entries = _mk_trial(tmp_path, "C", with_sidecar=False)
    with pytest.raises(RuntimeError, match="COMPLETE without STARTED"):
        AA.verify_arm_a_trial_fresh_or_verified(
            "u1", o, s, entries, R.record_file_hash, R.record_file_hash)
    o, s, entries = _mk_trial(tmp_path, "SC", tamper="record")
    with pytest.raises(RuntimeError, match="record hash mismatch"):
        AA.verify_arm_a_trial_fresh_or_verified(
            "u1", o, s, entries, R.record_file_hash, R.record_file_hash)
    o, s, entries = _mk_trial(tmp_path, "SC")
    np.savez_compressed(s, a_vec=np.ones(4), resp=np.ones(4), sq=np.ones(4),
                        strata=np.ones(4, dtype=int),
                        bootstrap_g=np.ones(3))
    with pytest.raises(RuntimeError, match="sidecar hash mismatch"):
        AA.verify_arm_a_trial_fresh_or_verified(
            "u1", o, s, entries, R.record_file_hash, R.record_file_hash)
    o, s, entries = _mk_trial(tmp_path, "SC")
    s.unlink()
    with pytest.raises(RuntimeError, match="missing record or sidecar"):
        AA.verify_arm_a_trial_fresh_or_verified(
            "u1", o, s, entries, R.record_file_hash, R.record_file_hash)
    o, s, _ = _mk_trial(tmp_path, "")
    with pytest.raises(RuntimeError, match="orphan Arm-A artifact"):
        AA.verify_arm_a_trial_fresh_or_verified(
            "u1", o, s, [], R.record_file_hash, R.record_file_hash)


# --------------------------------------------------------------------------
# mocked full route (A0 item 10): execute -> sidecar durability -> unseal
# -> grouped evaluation -> synthetic verdicts.  Real simulator calls = 0.
# --------------------------------------------------------------------------

def _mock_trial(monkeypatch, calls):
    classes = ["WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"]

    def fake_arm_a_trial(st, seed_value, state_id, rep, config_id, s2,
                         contract_shas):
        calls["trials"] += 1
        rng = np.random.default_rng(seed_value)
        record = {
            "schema": AA.TRIAL_SCHEMA, "recorded_at": None,
            "state_id": state_id, "rep_id": rep, "config_id": config_id,
            "s2": float(s2), "curvature_c": 0.5,
            "seed": int(seed_value),
            "namespace": AA.ARM_A_NAMESPACE, "samples": AA.N_SAMPLES,
            "alpha_p": AA.ALPHA_P,
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
            "n_bootstrap": 500,
        }
        arrays = {"a_vec": rng.random(AA.N_SAMPLES),
                  "resp": rng.random(AA.N_SAMPLES),
                  "sq": rng.random(AA.N_SAMPLES),
                  "strata": rng.integers(0, 3, AA.N_SAMPLES),
                  "bootstrap_g": rng.normal(0, 0.1, 500)}
        return record, arrays

    monkeypatch.setattr(AA, "arm_a_trial", fake_arm_a_trial)


@pytest.fixture()
def protect_arm_a_preflight_report():
    p = R.OUT / "m3s25r1_arm_a_preflight.json"
    data = p.read_bytes()
    yield p
    p.write_bytes(data)


@pytest.fixture()
def arm_a_route(tmp_path, monkeypatch):
    import shutil
    import tempfile
    calls = {"trials": 0}
    _mock_trial(monkeypatch, calls)
    # tiny grids for the mocked evaluation
    monkeypatch.setattr(AE, "LOGISTIC_GRID", [{"C": 1.0, "class_weight": None}])
    monkeypatch.setattr(AE, "GBDT_GRID",
                        [{"max_iter": 20, "max_leaf_nodes": 7,
                          "learning_rate": 0.1, "l2_regularization": 0,
                          "random_state": 2026}])
    # short real filesystem root: the 220-char path gate would trip on
    # pytest's long tmp_path roots; the production tree fits (checked by
    # arm_a_preflight with the exact layout)
    root = Path(tempfile.mkdtemp(prefix="a0rt_"))
    a_dir = root / "arm_a"
    trials = a_dir / "trials"
    ledger = a_dir / "trial_ledger.jsonl"
    tsum = root / "summary"
    monkeypatch.setattr(R, "ARM_A_TRIALS", trials)
    monkeypatch.setattr(R, "ARM_A_LEDGER", ledger)
    monkeypatch.setattr(R, "ARM_A_EVAL", tsum / "m3s25r1_arm_a_evaluation.json")
    monkeypatch.setattr(R, "SUM", tsum)
    # real panel decision (PANEL-FROZEN) is read from SUM -> copy it in
    tsum.mkdir(parents=True, exist_ok=True)
    (tsum / "m3s25r1_panel_decision.json").write_bytes(
        (R.ROOT / "results/phase_m3s25r1/summary/m3s25r1_panel_decision.json")
        .read_bytes())
    yield {"calls": calls, "tmp": root}
    shutil.rmtree(root, ignore_errors=True)


def test_route_arm_a_execute_gated_refusal(arm_a_route, monkeypatch):
    """Refusal mechanism (isolated): with the ARM_A gate NO in a tmp
    approval doc and a fresh tmp destination, arm_a_execute refuses
    AFTER the restart scan and BEFORE any write."""
    approval = arm_a_route["tmp"] / "approval_no.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    with pytest.raises(RuntimeError,
                       match="M3_S25_R1_ARM_A_AUTHORIZED is not YES"):
        R.arm_a_execute()
    assert arm_a_route["calls"]["trials"] == 0
    assert not R.ARM_A_TRIALS.exists()


def test_consumed_unit_fails_closed_before_any_simulator():
    """The REAL consumed unit (incident) keeps the runtime fail-closed:
    the restart scan hits CONSUMED_INVALID BEFORE the authorization gate
    and BEFORE any simulator call, even with the authorized gate YES."""
    calls = {"trials": 0}

    def _boom(*a, **k):
        calls["trials"] += 1
        raise AssertionError("simulator reached")

    import hyptraj.m3d.adaptation as AD
    monkey = pytest.MonkeyPatch()
    monkey.setattr(AA, "arm_a_trial", _boom)
    try:
        with pytest.raises(RuntimeError, match="CONSUMED_INVALID"):
            R.arm_a_execute()
    finally:
        monkey.undo()
    assert calls["trials"] == 0
    led = R.ledger_entries(R.ARM_A_LEDGER)
    assert sum(1 for e in led if e.get("status") == "CONSUMED_INVALID") == 1
    assert sum(1 for e in led if e.get("status") == "COMPLETE") == 0


def test_route_arm_a_execute_to_960_and_evaluate(arm_a_route, monkeypatch):
    """Full mocked route: gate YES -> 960/960 durable COMPLETE with
    sidecars -> consumption 19.2M -> truth unseal AFTER completeness ->
    grouped evaluation -> verdict."""
    calls = arm_a_route["calls"]
    approval = arm_a_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: YES\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    summary = R.arm_a_execute()
    assert calls["trials"] == 960
    assert summary["n_trials"] == 960
    assert summary["CONSUMED_INVALID"] == 0
    assert summary["actual_samples"] == 19_200_000
    assert summary["planned"] == 19_200_000 and summary["topup"] == 0
    entries = R.ledger_entries(R.ARM_A_LEDGER)
    assert Counter(e["status"] for e in entries) == {"STARTED": 960,
                                                     "COMPLETE": 960}
    # sidecar durability: every record carries a verified sidecar hash
    n_side = len(list(R.ARM_A_TRIALS.rglob("*_instrumentation.npz")))
    assert n_side == 960
    rec0 = json.loads(next(R.ARM_A_TRIALS.rglob("rep0.json")).read_text(
        encoding="utf-8"))
    assert "truth" not in rec0 and "corrected_class" not in rec0

    # restart path: a second execute skips all 960 verified trials
    calls["trials"] = 0
    summary2 = R.arm_a_execute()
    assert calls["trials"] == 0 and summary2["n_trials"] == 960

    # evaluation: unseal AFTER completeness, grouped CV, verdict
    out = R.arm_a_evaluate()
    assert out["truth_manifest_unsealed"]["after_complete_960"] is True
    assert out["truth_manifest_unsealed"]["sha256"] == \
        R.PANEL_TRUTH_MANIFEST_PIN
    assert out["results"]["n_trials"] == 960
    for name in ("B0_frozen_S1", "B1_aggregate_gbdt_baseline",
                 "A1_stability_logistic", "A2_stability_gbdt",
                 "A3_stability_margin_logistic", "A4_stability_margin_gbdt"):
        assert name in out["results"]
        assert "deployable_coverage" in out["results"][name]
    verdict = out["verdict"]
    assert verdict["VERDICT"] in ("M3-S25-R1-A", "M3-S25-R1-B-GATE")
    eval_file = R.SUM / "m3s25r1_arm_a_evaluation.json"
    assert eval_file.exists()


def test_route_arm_a_evaluate_requires_960_complete(arm_a_route, monkeypatch):
    """The truth manifest unseals ONLY after 960/960 durable COMPLETE."""
    approval = arm_a_route["tmp"] / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: YES\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    R.arm_a_execute()
    entries = R.ledger_entries(R.ARM_A_LEDGER)
    keep = [e for e in entries
            if not (e["status"] == "COMPLETE"
                    and e["state_id"].endswith("|rep7"))]
    with R.ARM_A_LEDGER.open("w", encoding="utf-8") as h:
        for e in keep:
            h.write(json.dumps(e) + "\n")
    with pytest.raises(RuntimeError, match="960/960"):
        R.arm_a_evaluate()


def test_verdict_semantics_synthetic():
    """A / B-GATE / X verdict logic on synthetic metrics (A0 item 10)."""
    good = {"deployable_coverage": 0.85, "nd_unsafe": 0.10,
            "wrong_direction_rate": 0.02, "ambiguous_unsafe": 0.10}
    b1_bad = {"deployable_coverage": 0.60, "nd_unsafe": 0.30,
              "wrong_direction_rate": 0.10, "ambiguous_unsafe": 0.40}
    b0_bad = {"deployable_coverage": 0.50, "nd_unsafe": 0.40,
              "wrong_direction_rate": 0.10, "ambiguous_unsafe": 0.40}
    results = {"B0_frozen_S1": b0_bad,
               "B1_aggregate_gbdt_baseline": b1_bad,
               "A1_stability_logistic": good}
    v = AE.verdict(results, 960, 0)
    assert v["VERDICT"] == "M3-S25-R1-A"
    assert v["compliant"] == ["A1_stability_logistic"]
    # no compliant candidate => B-GATE
    results2 = {"B0_frozen_S1": b0_bad, "B1_aggregate_gbdt_baseline": b1_bad,
                "A1_stability_logistic": b1_bad}
    v2 = AE.verdict(results2, 960, 0)
    assert v2["VERDICT"] == "M3-S25-R1-B-GATE"
    # integrity failure
    v3 = AE.verdict(results, 959, 1)
    assert v3["VERDICT"] == "M3-S25-R1-X"


def test_split_feasibility_on_frozen_panel():
    rows = [{"_state_id": s["state_id"], "_config_id": s["config_id"],
             "_truth": s["truth"]}
            for s in R.load(R.PANEL_TRUTH_MANIFEST)["states"]]
    feas = AE.split_feasibility(rows)
    assert feas["PASS"] is True
    assert len(feas["outer"]) == 5
    assert all(e["train_configs"] == 24 and e["test_configs"] == 6
               for e in feas["outer"])
    assert all(e["inner_GroupKFold4_feasible"] for e in feas["outer"])


def test_route_gates_match_authorization_after_all_tests():
    assert not R.gate("M3_S25_R1_TRUTH_AUTHORIZED")
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is True
    assert not R.gate("M3_S25_R1_ARM_B_AUTHORIZED")


# --------------------------------------------------------------------------
# A0.1 amendments
# --------------------------------------------------------------------------

def test_hashlock_covers_arm_a_and_ml0_chain():
    """A0.1 item 1: the scientific-code hash lock covers the Arm-A and
    ML0 evaluation chain, and every entry matches current bytes."""
    hm = R.load(R.CFG / "m3s25r1_hash_manifest.json")
    required = ["src/hyptraj/m3s25r1/arm_a.py",
                "src/hyptraj/m3s25r1/arm_a_eval.py",
                "src/hyptraj/m3ml0/evaluation.py",
                "src/hyptraj/m3ml0/threshold.py",
                "src/hyptraj/m3ml0/features.py",
                "src/hyptraj/m3ml0/models.py",
                "src/hyptraj/m3pi1vr0/persistence.py",
                "src/hyptraj/m3wa1r/persistence.py",
                "src/hyptraj/m3d/adaptation.py",
                "src/hyptraj/m3/gradient_estimator.py"]
    for path in required:
        assert hm["scientific_code_hashes"].get(path) == R.sha(R.ROOT / path), path


def test_panel_file_sha_enforced_at_runtime(tmp_path, monkeypatch):
    """A0.1 item 2: the frozen panel FILE sha is enforced even when the
    stored panel_sha256 field is unchanged.  Tamper an s2 field in a copy
    => arm_a_execute hard-fails BEFORE STARTED / simulator (isolated tmp
    ledger so the tamper refusal is observed before the consumed-unit
    scan)."""
    calls = {"trials": 0}
    _mock_trial(monkeypatch, calls)
    panel = json.loads((R.CFG / "m3s25r1_panel.json").read_text("utf-8"))
    tampered = json.loads(json.dumps(panel))
    tampered["states"][0]["s2"] = tampered["states"][0]["s2"] + 0.001
    assert tampered["panel_sha256"] == panel["panel_sha256"]  # field kept
    bad = tmp_path / "m3s25r1_panel.json"
    bad.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(R, "PANEL_JSON", bad)
    with pytest.raises(RuntimeError, match="panel FILE sha drift"):
        R.arm_a_execute()
    assert calls["trials"] == 0


def test_sidecar_transactional_fault_injection(tmp_path):
    """A0.1 item 3: injected failures before/after sidecar fsync/rename
    and after verify => no false COMPLETE (no record, no COMPLETE entry)."""
    from hyptraj.m3s25r1.arm_a import (InjectedSidecarFault, N_SAMPLES,
                                       write_sidecar_transactional)
    from hyptraj.m3wa1r.persistence import run_trial_transactional
    arrays = {"a_vec": np.zeros(N_SAMPLES), "resp": np.zeros(N_SAMPLES),
              "sq": np.zeros(N_SAMPLES), "strata": np.zeros(N_SAMPLES, int),
              "bootstrap_g": np.zeros(500)}
    for tag in ("SIDECAR_BEFORE_FSYNC", "SIDECAR_AFTER_FSYNC_BEFORE_RENAME",
                "SIDECAR_AFTER_VERIFY"):
        trial_dir = tmp_path / tag
        trial_dir.mkdir(parents=True, exist_ok=True)
        side = trial_dir / "rep0_instrumentation.npz"
        rec = trial_dir / "rep0.json"
        ledger = trial_dir / "ledger.jsonl"

        def compute(tag=tag, side=side, arrays=arrays):
            sha = write_sidecar_transactional(side, arrays, fault=tag)
            return {"schema": AA.TRIAL_SCHEMA,
                    "instrumentation_sha256": sha}

        result = run_trial_transactional(
            f"unit|{tag}", rec, compute, ledger_path=ledger,
            pre_hash_validator=lambda r: None)
        assert result["status"] == "CONSUMED_INVALID", tag
        assert not rec.exists(), tag
        assert not any(e.get("status") == "COMPLETE"
                       for e in R.ledger_entries(ledger)), tag
    # clean write: durable sidecar + verified sha
    side = tmp_path / "ok" / "rep0_instrumentation.npz"
    sha = write_sidecar_transactional(side, arrays)
    assert sha == R.record_file_hash(side)
    assert side.exists() and not any(
        p.name.startswith(".") for p in side.parent.iterdir())


def test_b1_comparator_is_ml0_b3_exact():
    """A0.1 item 4: B1 uses the EXACT ML0 F0_FULL feature set and the
    frozen ML0 HistGradientBoosting grid; the ML0 feature-contract and
    model-grid SHAs are recorded in the rebind contract."""
    ml0_features = R.ROOT / "src/hyptraj/m3ml0/features.py"
    text = ml0_features.read_text(encoding="utf-8")
    assert 'B3_FEATURES = F0_FULL' in text
    assert ('F0_FULL = ["S1", "g_hat", "abs_g_hat", "SE_g", "CI_width", '
            '"s2",\n           "curvature_c", "ESS_grad", "gradient_valid"]'
            in text)
    assert AE.ML0_B1_FEATURES == ["S1", "g_hat", "abs_g_hat", "SE_g",
                                  "CI_width", "s2", "curvature_c",
                                  "ESS_grad", "gradient_valid"]
    assert AE.MODEL_FEATURES["B1_aggregate_gbdt_baseline"] == \
        AE.ML0_B1_FEATURES
    c = R.load(R.ARM_A_CONTRACT)
    assert c["b1_comparator"]["features"] == AE.ML0_B1_FEATURES
    assert c["b1_comparator"]["grid"] == AA.GBDT_GRID
    assert c["b1_comparator"]["ml0_feature_contract_sha256"] == \
        R.sha(ml0_features)
    assert c["b1_comparator"]["ml0_model_grid_sha256"] == \
        R.sha(R.ROOT / "src/hyptraj/m3ml0/models.py")
    assert "curvature_c" in c["b1_comparator"]["curvature_c_route"]


def test_only_a_models_can_trigger_success():
    """A0.1 item 5: B0/B1 are comparators only.  If only B1 is
    compliant/improved but A1-A4 are not, the verdict remains
    M3-S25-R1-B-GATE (synthetic regression for exactly this case)."""
    def m(cov, uns, wrong, amb):
        return {"deployable_coverage": cov, "nd_unsafe": uns,
                "wrong_direction_rate": wrong, "ambiguous_unsafe": amb}
    b0 = m(0.50, 0.40, 0.10, 0.40)
    # B1: fully compliant AND improved over B0 -- yet B0/B1 can never
    # trigger M3-S25-R1-A
    b1 = m(0.90, 0.05, 0.01, 0.10)
    a_bad = m(0.60, 0.30, 0.08, 0.30)
    results = {"B0_frozen_S1": b0, "B1_aggregate_gbdt_baseline": b1,
               "A1_stability_logistic": a_bad, "A2_stability_gbdt": a_bad,
               "A3_stability_margin_logistic": a_bad,
               "A4_stability_margin_gbdt": a_bad}
    v = AE.verdict(results, 960, 0)
    assert v["VERDICT"] == "M3-S25-R1-B-GATE"
    # and an eligible A-model triggers success under the same comparators
    results2 = dict(results)
    results2["A2_stability_gbdt"] = m(0.90, 0.05, 0.01, 0.10)
    v2 = AE.verdict(results2, 960, 0)
    assert v2["VERDICT"] == "M3-S25-R1-A"
    assert "A2_stability_gbdt" in v2["compliant"]
    assert "B1_aggregate_gbdt_baseline" not in v2["compliant"]


def test_seed_audit_explicit_pools():
    """A0.1 item 6: explicit 960 conditions, type-consistent pools, and
    per-stream zero-collision proof; the 960-unit manifest stays
    byte-identical."""
    plan = AA.arm_a_seed_plan(
        R.load(R.PANEL_JSON)["states"])
    pools = {"m3s2s_arm_a": set(range(1, 100)), "r1_truth": {12345}}
    truth_keys = {"m3s2s_truth": {(1, 42424)}}
    audit = AA.seed_collision_audit(plan, pools, truth_keys)
    assert audit["units"] == 960 and audit["unique_seeds"] == 960
    assert audit["per_stream_collisions"] == {
        "m3s2s_arm_a": 0, "r1_truth": 0, "m3s2s_truth": 0}
    assert audit["ARM_A_SEED_AUDIT"] == "PASS"
    # duplicate values must fail the EXPLICIT conditions
    bad = {"namespace": "x", "units": plan["units"][:1] * 2,
           "n_trials": 960, "budget": 1,
           "planned_seeds": {"a|rep0": 7, "b|rep0": 7}}
    with pytest.raises(RuntimeError, match="not 960 unique values"):
        AA.seed_collision_audit(bad, pools, truth_keys)
    # frozen manifest unchanged (values untouched by the audit rework)
    assert R.sha_bytes(R.ARM_A_SEED_MANIFEST.read_bytes())         == R.ARM_A_SEED_MANIFEST_PIN


def test_secondary_metrics_contract():
    """A0.1 item 7: OOF probabilities are preserved; ROC-AUC / PR-AUC /
    Brier / ECE are reported on scored OOF rows and never affect the
    primary verdict."""
    from hyptraj.m3s25r1.arm_a_eval import secondary_metrics
    rows = [{"_truth": "WIDEN" if i % 2 == 0 else "HOLD"} for i in range(50)]
    oof_prob = {i: 0.5 + 0.4 * ((-1) ** (i % 2)) * 0.5 for i in range(50)}
    m = secondary_metrics(oof_prob, rows)
    assert m["n_scored"] == 50
    assert 0.0 <= m["roc_auc"] <= 1.0 and 0.0 <= m["pr_auc"] <= 1.0
    assert 0.0 <= m["brier"] <= 1.0 and 0.0 <= m["ece"] <= 1.0
    # verdict never reads the secondary metrics
    import inspect
    src = inspect.getsource(AE.verdict)
    assert "secondary" not in src and "roc_auc" not in src


# --------------------------------------------------------------------------
# A0.2 micro-amendment
# --------------------------------------------------------------------------

def test_robust_discrepancy_formula_restored():
    """A0.2 item 1: abs_g_hat_minus_boot_median == abs(g_hat - boot_median)
    for BOTH positive and negative g_hat -- explicitly NOT
    abs(g_hat) - boot_median."""
    med = 0.30

    def make(g_hat):
        record = {
            "schema": AA.TRIAL_SCHEMA, "state_id": "s", "rep_id": 0,
            "config_id": "c", "s2": 1.0, "curvature_c": 0.5, "seed": 1,
            "gradient": {"g_hat": g_hat, "g_ci_low": g_hat - 0.1,
                         "g_ci_high": g_hat + 0.1, "ESS_grad": 5000.0,
                         "M2_hat": 0.01, "responsibility_mass": 0.9,
                         "D_hat": 0.02, "problems": [], "s2_base": 1.0,
                         "batches": 20},
            "selected_action": "WIDEN", "S1": 1.0, "deployment": "ABSTAIN",
            "event_count": 500, "event_rate": 0.025, "valid": True,
        }
        arrays = {"a_vec": np.full(10, 0.5), "resp": np.full(10, 0.5),
                  "sq": np.zeros(10), "strata": np.zeros(10, dtype=int),
                  "bootstrap_g": np.full(500, med)}
        return AE.feature_row(record, arrays)

    for g_hat in (2.0, -2.0):
        row = make(g_hat)
        expected = abs(g_hat - med)
        wrong = abs(g_hat) - med
        assert row["abs_g_hat_minus_boot_median"] == pytest.approx(expected)
        if g_hat < 0:
            # the restored formula is DISTINGUISHABLE from the broken one
            assert row["abs_g_hat_minus_boot_median"] != pytest.approx(wrong)
        # the paired (non-abs) feature remains the plain difference
        assert row["g_hat_minus_boot_median"] == pytest.approx(g_hat - med)


def test_sidecar_dir_fsync_fail_closed(tmp_path, monkeypatch):
    """A0.2 item 2: an unavailable parent-directory fsync after the
    atomic rename must yield NO COMPLETE ledger entry, NO scientific
    record, and a CONSUMED_INVALID unit (=> M3-S25-R1-X => STOP)."""
    from hyptraj.m3wa1r.persistence import run_trial_transactional

    def broken_fsync(path):
        return {"pass": False, "reason": "injected: fsync unavailable"}

    monkeypatch.setattr(AA, "fsync_directory", broken_fsync)
    trial_dir = tmp_path / "t"
    trial_dir.mkdir(parents=True, exist_ok=True)
    side = trial_dir / "rep0_instrumentation.npz"
    rec = trial_dir / "rep0.json"
    ledger = trial_dir / "ledger.jsonl"
    arrays = {"a_vec": np.zeros(4), "resp": np.zeros(4), "sq": np.zeros(4),
              "strata": np.zeros(4, dtype=int), "bootstrap_g": np.zeros(3)}

    def compute():
        sha = AA.write_sidecar_transactional(side, arrays)
        return {"schema": AA.TRIAL_SCHEMA, "instrumentation_sha256": sha}

    result = run_trial_transactional(
        "unit|dirfsync", rec, compute, ledger_path=ledger,
        pre_hash_validator=lambda r: None)
    assert result["status"] == "CONSUMED_INVALID"
    assert not rec.exists()
    entries = R.ledger_entries(ledger)
    assert not any(e.get("status") == "COMPLETE" for e in entries)
    assert any(e.get("status") == "CONSUMED_INVALID" for e in entries)
    # a healthy fsync still produces a durable, verified sidecar
    monkeypatch.undo()
    sha = AA.write_sidecar_transactional(side, arrays)
    assert sha == R.record_file_hash(side)


def test_arm_a_trial_crosscheck_passes_on_real_state():
    """A0.2 incident regression: the bit-exact crosscheck between the
    trial's instrumented pipeline and the UNMODIFIED estimator passes on
    a REAL state assembly (the first failed trial's config; a test-local
    seed -- never a frozen manifest seed).  Slow but decisive."""
    import run_m3s25r1 as R
    from hyptraj.m3d.benchmark_states import assemble_state
    s = R.load(R.PANEL_JSON)["states"][0]
    bench = R.VR.resolve_bench_config(s["config_id"])
    st = assemble_state(bench, float(s["s2"]), short_config=s["config_id"])
    record, arrays = AA.arm_a_trial(
        st, 777, s["state_id"], 0, s["config_id"], float(s["s2"]),
        {"test": "sha"})
    assert record["estimator_crosscheck_exact"] is True
    assert record["valid"] is True
    assert arrays["bootstrap_g"].shape == (500,)
    assert np.isfinite(arrays["bootstrap_g"]).sum() == 500
