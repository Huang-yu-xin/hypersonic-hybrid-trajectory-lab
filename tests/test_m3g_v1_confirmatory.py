"""M3-G-v1 confirmatory validation -- structural + behavioral tests
(task Sec. 11-12 list).

Covers: exact GA1 formula, pilot-M2 (not eval-M2) gate, rho locked 0.02,
no calibration grid, no GA2 selection, direction parity with the frozen
M3-D controller, HOLD passthroughs, no sign flip, no oracle leakage,
confirmatory-seed disjointness, benchmark hash unchanged, legality fold,
result schema.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m3g_v1.gain_gate import (
    EXECUTED,
    HOLD_GAIN,
    RHO,
    VARIANT,
    apply_gain_gate_v1,
    final_arm_key,
    final_deployed,
)
from hyptraj.m3g_v1.metrics import (
    build_m3g_v1_trial_record,
    validate_m3g_v1_trial_record,
)
from hyptraj.m3g_v1.pipeline import v1_trial_gate

REPO = Path(__file__).resolve().parents[1]
FREEZE_JSON = REPO / "docs" / "phase_m3d" / "M3_D_Benchmark_Freeze.json"
PROTO = json.loads((REPO / "configs" / "phase_m3g_v1"
                    / "m3g_v1_protocol.json").read_text(encoding="utf-8"))
SEED_CFG = json.loads((REPO / "configs" / "phase_m3g_v1"
                       / "m3g_v1_confirmatory_seeds.json").read_text(
                           encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. exact GA1 formula + boundary
# --------------------------------------------------------------------------- #
def test_m3gv1_exact_ga1_formula():
    # Delta_rel = |g_hat*dtheta|/M2_pilot exactly
    g = apply_gain_gate_v1(direction="WIDEN", g_hat=-4.0, m2_pilot=2.0)
    assert g["gain_proxy"] == 0.4
    assert g["variant"] == "GA1"
    assert g["rho"] == 0.02
    # boundary: proxy < 0.02 -> HOLD_GAIN ; proxy == 0.02 -> EXECUTE
    g_lo = apply_gain_gate_v1(direction="SHRINK", g_hat=0.099,
                              m2_pilot=1.0)      # 0.099*0.2/1 = 0.0198
    assert g_lo["gain_proxy"] == 0.0198
    assert g_lo["final_action"] == "HOLD"
    assert g_lo["gain_hold_reason"] == HOLD_GAIN
    g_eq = apply_gain_gate_v1(direction="SHRINK", g_hat=0.10,
                              m2_pilot=1.0)      # 0.10*0.2/1 = 0.02
    assert g_eq["gain_proxy"] == pytest.approx(0.02)
    assert g_eq["final_action"] == "SHRINK"
    assert g_eq["gain_hold_reason"] == EXECUTED


def _identifiers(src: str) -> set:
    import ast
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


# --------------------------------------------------------------------------- #
# 2. gate uses pilot M2_hat, NOT evaluation M2
# --------------------------------------------------------------------------- #
def test_m3gv1_uses_pilot_m2_not_eval_m2():
    import hyptraj.m3g_v1.gain_gate as gg
    sig = inspect.signature(gg.apply_gain_gate_v1)
    allowed = {"direction", "g_hat", "m2_pilot", "delta_theta", "rho",
               "arm_legal"}
    assert set(sig.parameters.keys()) == allowed
    assert "m2_pilot" in sig.parameters
    assert "m2_eval" not in sig.parameters
    names = _identifiers(inspect.getsource(gg))
    for banned in ("ev", "m2_eval", "evaluate_variant", "arms_block",
                   "eval_proposal"):
        assert banned not in names, f"banned identifier {banned!r}"
    # behavioral: the proxy scales with the pilot denominator only
    g1 = apply_gain_gate_v1(direction="WIDEN", g_hat=-5.0, m2_pilot=50.0)
    g2 = apply_gain_gate_v1(direction="WIDEN", g_hat=-5.0, m2_pilot=5.0)
    assert g1["gain_proxy"] == 0.02 and g2["gain_proxy"] == 0.2
    assert g1["final_action"] == "WIDEN" and g2["final_action"] == "WIDEN"


# --------------------------------------------------------------------------- #
# 3. rho locked at 0.02 (code + config)
# --------------------------------------------------------------------------- #
def test_m3gv1_rho_locked_002():
    import hyptraj.m3g_v1.gain_gate as gg
    assert RHO == 0.02
    assert PROTO["candidate_locked"]["variant"] == "GA1"
    assert PROTO["candidate_locked"]["rho"] == 0.02
    # behavioral lock: proxy 0.0199999 -> HOLD; 0.02 -> EXECUTE
    g = apply_gain_gate_v1(direction="WIDEN", g_hat=-0.0999995,
                           m2_pilot=1.0)   # 0.0199999
    assert g["gain_hold_reason"] == HOLD_GAIN


# --------------------------------------------------------------------------- #
# 4. no calibration grid in the v1 package
# --------------------------------------------------------------------------- #
def test_m3gv1_no_calibration_grid():
    import hyptraj.m3g_v1.gain_gate as gg
    import hyptraj.m3g_v1.pipeline as pl
    import hyptraj.m3g_v1 as pkg
    for mod in (gg, pl):
        names = _identifiers(inspect.getsource(mod))
        for banned in ("RHO_GRID", "rho_grid", "calibration",
                       "select_candidate", "build_calibration_table"):
            assert banned not in names, f"banned {banned!r} in {mod.__name__}"
    assert "calibration" not in _identifiers(
        inspect.getsource(pkg)), "calibration imported by the v1 package"
    assert PROTO["candidate_locked"]["no_calibration_grid"] is True


# --------------------------------------------------------------------------- #
# 5. no GA2 selection
# --------------------------------------------------------------------------- #
def test_m3gv1_no_ga2_selection():
    import hyptraj.m3g_v1.gain_gate as gg
    assert "GA2" not in _identifiers(inspect.getsource(gg))
    assert PROTO["candidate_locked"]["no_ga2"] is True


# --------------------------------------------------------------------------- #
# 6. direction parity with the frozen M3-D controller
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def real_state():
    from hyptraj.m1d.experiments import config_from_record, load_freeze
    from hyptraj.m3d.benchmark_states import assemble_state
    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    cid = [c for c in freeze if c.endswith("_c000")][0]
    return assemble_state(config_from_record(freeze[cid]), 1.0)


def test_m3gv1_direction_parity(real_state):
    from hyptraj.m3d.adaptation import draw_online_pilot, gradient_decision
    st = real_state
    seed = 3031            # confirmatory seed (unseen in discovery)
    z, logp, logr, strata = draw_online_pilot(st, seed, n_pilot=4000)
    gd = gradient_decision(st, seed, z, logp, logr, strata)
    out = v1_trial_gate(st, seed, z, logp, logr, strata)
    gr = gd["gradient"]
    assert out["gain"]["direction_before_gain"] == gr["decision"]
    for f in ("g_hat", "g_ci_low", "g_ci_high", "ESS_grad"):
        assert out["parity_block"][f] == float(gr[f])
    assert out["parity_block"]["decision"] == str(gr["decision"])


# --------------------------------------------------------------------------- #
# 7. HOLD passthroughs preserve raw reason codes
# --------------------------------------------------------------------------- #
def test_m3gv1_hold_passthrough():
    for raw in ("HOLD_LOW_ESS", "HOLD_UNCERTAIN", "HOLD_INVALID"):
        g = apply_gain_gate_v1(direction=raw, g_hat=0.0, m2_pilot=1.0)
        assert g["final_action"] == "HOLD"
        assert g["gain_hold_reason"] == raw
        assert g["gain_proxy"] is None


# --------------------------------------------------------------------------- #
# 8. the gate can never flip a direction
# --------------------------------------------------------------------------- #
def test_m3gv1_gain_hold_no_sign_flip():
    rng = np.random.default_rng(5)
    for _ in range(200):
        g = float(rng.normal(0, 5))
        m2 = float(rng.uniform(0.5, 20))
        for direction in ("WIDEN", "SHRINK"):
            out = apply_gain_gate_v1(direction=direction, g_hat=g,
                                     m2_pilot=m2)
            assert out["final_action"] in (direction, "HOLD")


# --------------------------------------------------------------------------- #
# 9. no oracle leakage (structural, AST identifiers)
# --------------------------------------------------------------------------- #
def test_m3gv1_no_oracle_leakage():
    import hyptraj.m3g_v1.gain_gate as gg
    import hyptraj.m3g_v1.pipeline as pl
    for mod in (gg, pl):
        names = _identifiers(inspect.getsource(mod))
        for banned in ("oracle", "oracle_action", "direction_margin",
                       "M2_base_ref", "mode_L_base", "labels_corrected",
                       "bench_cfg"):
            assert banned not in names, \
                f"banned identifier {banned!r} in {mod.__name__}"


# --------------------------------------------------------------------------- #
# 10. confirmatory seeds locked, unseen, disjoint
# --------------------------------------------------------------------------- #
def test_m3gv1_confirmatory_seeds_disjoint():
    conf = SEED_CFG["confirmatory_seeds"]
    disc = PROTO["seed_sets"]["discovery_seeds"]
    assert len(conf) == 8
    assert len(set(conf)) == 8
    assert set(conf).isdisjoint(set(disc))
    assert SEED_CFG["disjoint"] is True
    assert SEED_CFG["locked_before_science"] is True
    assert PROTO["seed_sets"]["disjoint_required"] is True


# --------------------------------------------------------------------------- #
# 11. sealed benchmark hash unchanged
# --------------------------------------------------------------------------- #
def test_m3gv1_benchmark_hash_unchanged():
    freeze_doc = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    body = {k: v for k, v in freeze_doc.items()
            if k != "freeze_sha256_of_body_above"}
    h = hashlib.sha256(json.dumps(body, indent=1).encode()).hexdigest()
    assert h == freeze_doc["freeze_sha256_of_body_above"]
    assert (h == "b613f45dc6645c6da26ab58b5185764f14d771ca6b996"
                 "bffed88fea1f467a5f3")
    assert PROTO["benchmark"]["freeze_sha256"] == h


# --------------------------------------------------------------------------- #
# 12. legality floor (fold HOLD_INVALID, M3-D audit discipline)
# --------------------------------------------------------------------------- #
def test_m3gv1_legality():
    # s2=0.55 shrink arm: 0.55*exp(-0.2) = 0.4502 < 0.5 -> illegal
    from hyptraj.m3g.metrics import arm_legal_at
    assert arm_legal_at(0.55, -0.20) is False
    g = apply_gain_gate_v1(direction="SHRINK", g_hat=3.0, m2_pilot=1.0,
                           arm_legal=False)
    assert g["final_action"] == "HOLD"
    assert g["gain_hold_reason"] == "HOLD_INVALID"
    assert final_deployed("HOLD") == "HOLD"
    assert final_arm_key("HOLD") == "base"
    assert final_arm_key("WIDEN") == "widen"
    assert final_arm_key("SHRINK") == "shrink"


# --------------------------------------------------------------------------- #
# 13. result schema (raretopo-m3g-v1)
# --------------------------------------------------------------------------- #
def test_m3gv1_result_schema():
    def _arm(m2):
        return {"M2": float(m2), "mode_L": {"S1": m2 / 4, "S2": m2 / 4,
                                            "S3": m2 / 4, "S4": m2 / 4}}

    rec = build_m3g_v1_trial_record(
        config_id="x", state_id="y", seed=3031, base_s2=1.0,
        oracle_action="HOLD", oracle_direction_margin=0.1,
        gradient_block={"g_hat": -1.0, "g_ci_low": -2.0, "g_ci_high": -0.1,
                        "ESS_grad": 25.0, "action": "WIDEN",
                        "M2_hat_pilot": 0.5},
        gain_block={"direction_before_gain": "WIDEN", "variant": "GA1",
                    "rho": 0.02, "delta_theta": 0.2, "gain_proxy": 0.5,
                    "final_action": "WIDEN", "gain_hold_reason": "EXECUTED"},
        arms_block={k: _arm(0.5) for k in
                    ("hold", "widen", "shrink", "gradient", "oracle",
                     "gate")},
        metrics_block={"action_correct": True, "regret_M2": 0.0,
                       "VRF_proposal": 1.2, "VRF_budget": 1.1,
                       "M2_gate_over_base": 1.0, "M2_gate_over_oracle": 1.0,
                       "M2_gate_over_gradient": 1.0},
        validity_block={"raw_decision_code": "WIDEN"})
    assert validate_m3g_v1_trial_record(rec)
    bad = dict(rec)
    bad["gain"] = dict(rec["gain"], rho=0.01)
    assert not validate_m3g_v1_trial_record(bad)
    bad2 = dict(rec)
    bad2["gradient"] = dict(rec["gradient"], M2_hat_pilot=None)
    assert not validate_m3g_v1_trial_record(bad2)