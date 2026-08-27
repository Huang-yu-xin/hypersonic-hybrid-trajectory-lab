"""M3-G structural + behavioral tests (task Sec. 7 list; handoff Sec. 12).

Covers: frozen direction bitwise parity, GA1 formula + threshold boundary,
GA2 formula + CI replicate parity, HOLD passthroughs, no direction flip,
zero extra simulator calls, no oracle leakage, sealed benchmark immutability,
locked calibration grid, calibration constraints (0.90/0.90 eligibility) +
selection discipline, illegal-arm fold, result schema, freeze consistency.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m3.gradient_estimator import stratified_bootstrap_gradient_ci
from hyptraj.m3g.calibration import (
    BENCHMARK_FREEZE_SHA256,
    freeze_payload,
    load_calibration_batch,
    run_offline_calibration,
)
from hyptraj.m3g.gain_gate import (
    EXECUTED,
    HOLD_GAIN,
    apply_gain_gate,
    deployed_final,
    final_arm_key,
)
from hyptraj.m3g.gain_proxy import (
    DELTA_THETA_MAIN,
    bootstrap_gain_replicates,
    ga1_magnitude,
    ga2_upper_end,
    signed_delta_rel,
    step_delta_theta,
)
from hyptraj.m3g.metrics import (
    RHO_GRID,
    VARIANT_GRID,
    arm_legal_at,
    build_calibration_table,
    gate_from_stored_record,
    select_candidate,
)

REPO = Path(__file__).resolve().parents[1]
FREEZE_JSON = REPO / "docs" / "phase_m3d" / "M3_D_Benchmark_Freeze.json"


# --------------------------------------------------------------------------- #
# shared fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def stored_batch():
    return load_calibration_batch()


@pytest.fixture(scope="module")
def stored_records(stored_batch):
    return stored_batch["records"]


@pytest.fixture(scope="module")
def freeze_doc():
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. frozen M3 direction bitwise parity: the gate never recomputes direction
# --------------------------------------------------------------------------- #
def test_m3g_m3_direction_bitwise_parity(stored_records):
    # rho=0 GA1 must EXECUTE every legal active frozen decision: the gate
    # preserves the frozen direction exactly where no gating threshold bites.
    n_active_legal = n_executed = 0
    for rec in stored_records:
        raw = rec["gradient"]["action"]
        if raw not in ("WIDEN", "SHRINK"):
            continue
        g = gate_from_stored_record(rec, "GA1", 0.0)
        assert g["direction_before_gain"] == raw
        n_active_legal += 1
        if g["final_action"] == raw:
            n_executed += 1
    # the only non-executions are legality folds at the extreme-s2 arm
    assert n_active_legal >= 168
    assert n_executed >= n_active_legal - 8


def test_m3g_direction_passthrough_preserves_raw_reason(stored_records):
    for rec in stored_records:
        raw = rec["gradient"]["action"]
        if raw in ("WIDEN", "SHRINK"):
            continue
        for v in VARIANT_GRID:
            g = gate_from_stored_record(rec, v, 0.01)
            assert g["final_action"] == "HOLD"
            assert g["gain_hold_reason"] == raw


# --------------------------------------------------------------------------- #
# 2. GA1 formula + threshold boundary
# --------------------------------------------------------------------------- #
def test_m3g_ga1_formula():
    assert signed_delta_rel(-4.0, +0.20, 2.0) == -0.4
    assert ga1_magnitude(-4.0, +0.20, 2.0) == 0.4
    assert ga1_magnitude(4.0, -0.20, 2.0) == 0.4
    assert signed_delta_rel(4.0, -0.20, 2.0) == -0.4
    # frozen step map reuse
    assert step_delta_theta("WIDEN") == +DELTA_THETA_MAIN
    assert step_delta_theta("SHRINK") == -DELTA_THETA_MAIN
    assert step_delta_theta("HOLD_UNCERTAIN") == 0.0
    assert step_delta_theta("HOLD_LOW_ESS") == 0.0


def test_m3g_ga1_threshold_boundary():
    # magnitude == rho (inclusive) executes
    g = apply_gain_gate(direction="WIDEN", variant="GA1", rho=0.05,
                        g_hat=-5.0, g_ci_low=-6.0, g_ci_high=-4.0,
                        m2=20.0)      # mag = 5*0.2/20 = 0.05 == rho
    assert g["final_action"] == "WIDEN" and g["gain_hold_reason"] == EXECUTED
    # just below folds
    g2 = apply_gain_gate(direction="WIDEN", variant="GA1", rho=0.05,
                         g_hat=-4.99, g_ci_low=-6.0, g_ci_high=-4.0,
                         m2=20.0)     # mag < rho
    assert g2["final_action"] == "HOLD" and g2["gain_hold_reason"] == HOLD_GAIN


# --------------------------------------------------------------------------- #
# 3. GA2 formula (conservative signed-gain CI end) + boundary
# --------------------------------------------------------------------------- #
def test_m3g_ga2_formula():
    # WIDEN (dtheta>0): upper end = g_ci_high*0.20/M2
    assert ga2_upper_end(-6.0, -4.0, +0.20, 20.0) == -0.04
    # SHRINK (dtheta<0): upper end = g_ci_low*(-0.20)/M2  (sign-flip branch)
    assert ga2_upper_end(4.0, 6.0, -0.20, 20.0) == -0.04
    # act iff upper end <= -rho
    g = apply_gain_gate(direction="WIDEN", variant="GA2", rho=0.05,
                        g_hat=-5.0, g_ci_low=-6.0, g_ci_high=-4.0, m2=20.0)
    assert g["gain_proxy_upper_end"] == -0.04
    assert g["gain_proxy_upper_end"] > -0.05 and g["final_action"] == "HOLD"
    g2 = apply_gain_gate(direction="SHRINK", variant="GA2", rho=0.03,
                         g_hat=5.0, g_ci_low=4.0, g_ci_high=6.0, m2=20.0)
    assert g2["gain_proxy_upper_end"] == -0.04
    assert g2["final_action"] == "SHRINK" and g2["gain_hold_reason"] == EXECUTED


def test_m3g_ga2_replicate_ci_parity():
    """bootstrap_gain_replicates consumes the RNG exactly like the frozen
    CI function: g quantiles reproduce the frozen CI bitwise."""
    rng = np.random.default_rng(7)
    n = 400
    strata = np.concatenate([np.full(200, 0), np.full(120, 1),
                             np.full(80, 2)]).astype(int)
    a = rng.exponential(1.0, n) * (0.5 + 0.5 * strata)
    resp = rng.uniform(0.1, 1.0, n)
    sq = rng.uniform(0.05, 3.0, n)
    s2, dim = 1.3, 2
    frozen = stratified_bootstrap_gradient_ci(
        a, resp, sq, strata, s2=s2, dim=dim, n_bootstrap=300,
        bootstrap_seed_key=(2026, 424243))
    mine = bootstrap_gain_replicates(
        a, resp, sq, strata, s2=s2, dim=dim, dtheta=-0.20,
        n_bootstrap=300, bootstrap_seed_key=(2026, 424243))
    assert mine["g_ci_low"] == frozen["g_ci_low"]
    assert mine["g_ci_high"] == frozen["g_ci_high"]
    assert mine["n_bootstrap_valid"] == frozen["n_bootstrap_valid"]
    # per-replicate M2 positive wherever g finite
    g = np.asarray(mine["g_replicates"])
    m2 = np.asarray(mine["M2_replicates"])
    ok = np.isfinite(g)
    assert np.all(m2[ok] > 0.0)


# --------------------------------------------------------------------------- #
# 4-5. HOLD passthroughs
# --------------------------------------------------------------------------- #
def test_m3g_hold_uncertain_passthrough():
    g = apply_gain_gate(direction="HOLD_UNCERTAIN", variant="GA2", rho=0.01,
                        g_hat=0.0, g_ci_low=-1.0, g_ci_high=1.0, m2=1.0)
    assert g["final_action"] == "HOLD"
    assert g["gain_hold_reason"] == "HOLD_UNCERTAIN"
    assert g["gain_proxy_mag"] is None and g["gain_proxy_upper_end"] is None


def test_m3g_hold_low_ess_passthrough():
    g = apply_gain_gate(direction="HOLD_LOW_ESS", variant="GA1", rho=0.01,
                        g_hat=0.0, g_ci_low=None, g_ci_high=None, m2=1.0)
    assert g["final_action"] == "HOLD"
    assert g["gain_hold_reason"] == "HOLD_LOW_ESS"


# --------------------------------------------------------------------------- #
# 6. the gate can never flip a direction
# --------------------------------------------------------------------------- #
def test_m3g_gain_hold_does_not_flip_direction(stored_records):
    for rec in stored_records:
        raw = rec["gradient"]["action"]
        for v in VARIANT_GRID:
            for rho in RHO_GRID:
                g = gate_from_stored_record(rec, v, rho)
                f = g["final_action"]
                if raw in ("WIDEN", "SHRINK"):
                    assert f in (raw, "HOLD")
                else:
                    assert f == "HOLD"


# --------------------------------------------------------------------------- #
# 7. zero extra simulator calls (hard invariant)
# --------------------------------------------------------------------------- #
def test_m3g_zero_extra_simulator_calls(stored_records, monkeypatch):
    import hyptraj.m3d.adaptation as adaptation_module
    import hyptraj.m1d.metrics as m1d_metrics_module

    def _boom(*a, **k):
        raise AssertionError("simulator path called during calibration!")

    monkeypatch.setattr(adaptation_module, "draw_online_pilot", _boom)
    monkeypatch.setattr(m1d_metrics_module, "eval_proposal_is", _boom)
    out = run_offline_calibration(stored_records)
    assert out["extra_simulator_calls"] == 0
    assert out["n_trials"] == 192


def test_m3g_calibration_module_imports_no_simulators():
    src = inspect.getsource(
        __import__("hyptraj.m3g.calibration", fromlist=["x"]))
    for banned in ("draw_online_pilot", "eval_proposal_is", "evaluate_variant"):
        assert banned not in src, f"simulator entry {banned!r} in calibration"


# --------------------------------------------------------------------------- #
# 8. no oracle leakage (structural)
# --------------------------------------------------------------------------- #
def test_m3g_no_oracle_leakage():
    import hyptraj.m3g.gain_gate as gg
    import hyptraj.m3g.gain_proxy as gp
    import hyptraj.m3g.metrics as gm

    # decision layer (gate + proxy + calibration driver): oracle banned
    for mod in (gg, gp):
        src = inspect.getsource(mod)
        for banned in ("oracle", "direction_margin", "M2_base_ref",
                       "mode_L_base", "reference_direction"):
            assert banned not in src, f"forbidden {banned!r} in {mod.__name__}"
    # evaluation layer (metrics): oracle labels used ONLY to evaluate the
    # predicted actions (identical to M3-D accounting), never as gate input;
    # reference-data symbols are banned everywhere in the package
    src_m = inspect.getsource(gm)
    for banned in ("M2_base_ref", "mode_L_base", "reference_direction"):
        assert banned not in src_m, f"forbidden {banned!r} in metrics"
    assert src_m.count("rec[\"oracle_action\"]") >= 1
    # gate API surface
    sig = inspect.signature(gg.apply_gain_gate)
    allowed = {"direction", "variant", "rho", "g_hat", "g_ci_low",
               "g_ci_high", "m2", "delta_theta", "arm_legal"}
    assert set(sig.parameters.keys()) <= allowed


# --------------------------------------------------------------------------- #
# 9. sealed benchmark immutability
# --------------------------------------------------------------------------- #
def test_m3g_sealed_benchmark_immutable(freeze_doc, stored_batch):
    body = {k: v for k, v in freeze_doc.items()
            if k != "freeze_sha256_of_body_above"}
    h = hashlib.sha256(json.dumps(body, indent=1).encode()).hexdigest()
    assert h == freeze_doc["freeze_sha256_of_body_above"]
    assert h.startswith(BENCHMARK_FREEZE_SHA256[:16])
    comp = {}
    for s in freeze_doc["states"]:
        comp[s["oracle_action"]] = comp.get(s["oracle_action"], 0) + 1
    assert comp == {"WIDEN": 8, "SHRINK": 8, "HOLD": 8}
    assert stored_batch["benchmark_freeze_sha256"] == BENCHMARK_FREEZE_SHA256


# --------------------------------------------------------------------------- #
# 10. calibration grid locked
# --------------------------------------------------------------------------- #
def test_m3g_calibration_grid_locked():
    assert RHO_GRID == [0.0025, 0.005, 0.01, 0.02]
    assert VARIANT_GRID == ("GA1", "GA2")


# --------------------------------------------------------------------------- #
# 11. calibration constraints + preregistered selection discipline
# --------------------------------------------------------------------------- #
def test_m3g_calibration_constraints(stored_records):
    table = build_calibration_table(stored_records)
    # baseline row reproduces the frozen M3-D headline recalls
    base = table["baseline_M3-D"]
    assert base["recall_per_class"]["WIDEN"] == 1.0
    assert base["recall_per_class"]["SHRINK"] == 1.0
    assert base["recall_per_class"]["HOLD"] == 0.25
    assert abs(base["accuracy"] - 0.75) < 1e-12
    selected = select_candidate(table)
    sel = selected["selected"]
    if sel is not None:
        winner = table[sel["key"]]
        assert winner["recall_per_class"]["WIDEN"] >= 0.90
        assert winner["recall_per_class"]["SHRINK"] >= 0.90
        # winner maximizes accuracy among eligible
        others = [c for c in selected["candidates"] if c["eligible"]
                  and c["key"] != sel["key"]]
        for c in others:
            assert c["accuracy"] < winner["accuracy"] or (
                c["accuracy"] == winner["accuracy"]
                and (c["balanced_accuracy"], c["macro_F1"]) <= (
                    winner["balanced_accuracy"], winner["macro_F1"]))


def test_m3g_selection_excludes_ineligible():
    fake = {
        "GA1-0.005": {"variant": "GA1", "rho": 0.005,
                      "accuracy": 0.99, "balanced_accuracy": 0.9,
                      "macro_F1": 0.9, "recall_per_class":
                          {"WIDEN": 0.80, "SHRINK": 1.0, "HOLD": 0.5}},
        "GA2-0.01": {"variant": "GA2", "rho": 0.01,
                     "accuracy": 0.7, "balanced_accuracy": 0.6,
                     "macro_F1": 0.6, "recall_per_class":
                         {"WIDEN": 0.95, "SHRINK": 0.95, "HOLD": 0.4}},
        "baseline_M3-D": {"variant": "M3-D", "accuracy": 0.75},
    }
    sel = select_candidate(fake)
    # the 0.99-accuracy candidate is ineligible (WIDEN 0.80 < 0.90)
    assert sel["selected"] == {"key": "GA2-0.01", "variant": "GA2",
                               "rho": 0.01}


# --------------------------------------------------------------------------- #
# 12. illegal-arm fold (M3-D audit discipline inheritance)
# --------------------------------------------------------------------------- #
def test_m3g_illegal_arm_fold(stored_records):
    targets = [r for r in stored_records
               if abs(r["base_s2"] - 0.55) < 1e-12
               and r["gradient"]["action"] == "SHRINK"]
    if targets:                      # real folded cases
        for rec in targets:
            assert arm_legal_at(0.55, -DELTA_THETA_MAIN) is False
            g = gate_from_stored_record(rec, "GA1", 0.0)
            assert g["gain_hold_reason"] == "HOLD_INVALID"
            assert g["final_action"] == "HOLD"
    else:                            # synthetic fold case
        assert arm_legal_at(0.55, -DELTA_THETA_MAIN) is False
        assert arm_legal_at(0.55, +DELTA_THETA_MAIN) is True
        g = apply_gain_gate(direction="SHRINK", variant="GA1", rho=0.0,
                            g_hat=3.0, g_ci_low=2.0, g_ci_high=4.0, m2=0.1,
                            arm_legal=False)
        assert g["gain_hold_reason"] == "HOLD_INVALID"
        assert g["final_action"] == "HOLD"


# --------------------------------------------------------------------------- #
# 13. per-arm legality helper
# --------------------------------------------------------------------------- #
def test_m3g_arm_legality_boundary():
    # s2*exp(-0.2) >= 0.5  <=>  s2 >= 0.5*exp(0.2)
    s2_crit = 0.5 * np.exp(DELTA_THETA_MAIN)
    assert arm_legal_at(float(s2_crit) - 1e-9, -DELTA_THETA_MAIN) is False
    assert arm_legal_at(float(s2_crit) + 1e-9, -DELTA_THETA_MAIN) is True


# --------------------------------------------------------------------------- #
# 14. result schema (raretopo-m3g-v0)
# --------------------------------------------------------------------------- #
def test_m3g_result_schema():
    from hyptraj.m3g.metrics import (
        build_m3g_trial_record,
        validate_m3g_trial_record,
    )

    def _arm(m2):
        return {"M2": float(m2), "mode_L": {"S1": float(m2 / 4),
                                            "S2": float(m2 / 4),
                                            "S3": float(m2 / 4),
                                            "S4": float(m2 / 4)}}

    rec = build_m3g_trial_record(
        config_id="x", state_id="y", seed=2026, base_s2=1.0,
        oracle_action="HOLD", oracle_direction_margin=0.1,
        gradient_block={"g_hat": -1.0, "g_ci_low": -2.0, "g_ci_high": -0.1,
                        "ESS_grad": 25.0, "action": "WIDEN",
                        "M2_hat_pilot": 0.5},
        gain_block={"direction_before_gain": "WIDEN", "gain_variant": "GA1",
                    "rho": 0.01, "final_action": "WIDEN",
                    "gain_hold_reason": "EXECUTED"},
        arms_block={k: _arm(0.5) for k in
                    ("hold", "widen", "shrink", "gradient", "oracle", "gate")},
        metrics_block={"action_correct": True, "regret_M2": 0.0,
                       "VRF_proposal": 1.2, "VRF_budget": 1.1,
                       "M2_gate_over_base": 1.0, "M2_gate_over_oracle": 1.0,
                       "M2_gate_over_gradient": 1.0},
        validity_block={"raw_decision_code": "WIDEN"})
    assert validate_m3g_trial_record(rec)
    bad = dict(rec)
    bad["gain"] = dict(rec["gain"], gain_variant="GA3")
    assert not validate_m3g_trial_record(bad)
    bad2 = dict(rec)
    bad2["gradient"] = dict(rec["gradient"], action="BOGUS")
    assert not validate_m3g_trial_record(bad2)


# --------------------------------------------------------------------------- #
# 15. freeze consistency: selection reproducible from stored data
# --------------------------------------------------------------------------- #
def test_m3g_calibration_freeze_consistency(stored_records):
    cal1 = run_offline_calibration(stored_records)
    cal2 = run_offline_calibration(stored_records)
    assert cal1["selection"]["selected"] == cal2["selection"]["selected"]
    payload = freeze_payload(cal1, task_commit_sha="9720456",
                             calibration_code_commit="local")
    assert payload["extra_simulator_calls"] == 0
    assert payload["recall_min_each"] == 0.90
    assert payload["rho_grid"] == [0.0025, 0.005, 0.01, 0.02]
    if payload["selection"]["selected"] is not None:
        key = payload["selection"]["selected"]["key"]
        row = payload["candidate_results"][key]
        assert row["recall_per_class"]["WIDEN"] >= 0.90
        assert row["recall_per_class"]["SHRINK"] >= 0.90


# --------------------------------------------------------------------------- #
# 16. non-regression metric plumbing (hand-computed synthetic case)
# --------------------------------------------------------------------------- #
def test_m3g_non_regression_metrics():
    from hyptraj.m3g.metrics import candidate_metrics

    def _rec(action, oracle, s2=1.3, g_hat=-5.0, g_ci_low=-6.0,
             g_ci_high=-4.0, m2_hold=1.0, m2_widen=0.8, m2_shrink=1.2):
        return {
            "state_id": "s", "config_id": "c", "seed": 2026,
            "base_s2": s2, "gradient": {"action": action, "g_hat": g_hat,
                                        "g_ci_low": g_ci_low,
                                        "g_ci_high": g_ci_high,
                                        "ESS_grad": 50.0},
            "oracle_action": oracle,
            "validity": {"deployed_action":
                         ("HOLD" if action not in ("WIDEN", "SHRINK")
                          else action)},
            "arms": {"hold": {"M2": m2_hold},
                     "widen": {"M2": m2_widen},
                     "shrink": {"M2": m2_shrink},
                     "oracle": {"M2": 0.7}},
        }

    # 3 WIDEN trials: g_hat=-5 -> mag=5*0.2/1.0=1.0 >= rho -> EXECUTE-WIDEN
    recs = [_rec("WIDEN", "WIDEN") for _ in range(3)]
    m = candidate_metrics(recs, "GA1", 0.01)
    assert m["accuracy"] == 1.0
    assert m["recall_per_class"]["WIDEN"] == 1.0
    assert m["hold_gain_count"] == 0
    # small gain: mag = 0.005*0.2/1.0 = 0.001 < 0.01 -> HOLD_GAIN (wrong)
    recs2 = [_rec("WIDEN", "WIDEN", g_hat=-0.005)]
    m2 = candidate_metrics(recs2, "GA1", 0.01)
    assert m2["recall_per_class"]["WIDEN"] == 0.0
    assert m2["hold_gain_count"] == 1
    assert m2["action_change_count"] == 1
    assert abs(m2["median_M2_final_over_base"] - 1.0) < 1e-12


# --------------------------------------------------------------------------- #
# 17. deployed fold + final arm key helpers
# --------------------------------------------------------------------------- #
def test_m3g_deployed_fold_helpers():
    assert deployed_final("WIDEN") == "WIDEN"
    assert deployed_final("SHRINK") == "SHRINK"
    assert deployed_final("HOLD") == "HOLD"
    assert final_arm_key("WIDEN") == "widen"
    assert final_arm_key("SHRINK") == "shrink"
    assert final_arm_key("HOLD") == "hold"