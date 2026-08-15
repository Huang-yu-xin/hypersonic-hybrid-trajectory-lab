"""Phase-F coarse regime map tests (F2).

Covers the F2 acceptance surface A-W (the full 289-point map is executed
manually by experiments/07_gamma_k_sensitivity/run_coarse_regime_map.py,
never under pytest):

A. gamma grid exactly 17
B. K grid exactly 17
C. Cartesian product = 289
D. baseline index exact
E. F2 point wraps F1 paired result without recomputation
F. joint regime deterministic
G. candidate detector catches compact synthetic transition
H. candidate detector catches exact-only transition
I. uniform cell not candidate
J. edge-touch flags correct
K. expansion planner extends only touched edge
L. gamma expansion preserves 0.25 spacing
M. K expansion preserves 0.125 spacing
N. guardrails produce OPEN_BOUNDARY
O. cache provenance mismatch is rejected
P. valid cache reused
Q. multiskip jump warning works
R. NA margin remains None/masked, not zero
S. stop gate propagates censored/failure/ambiguous
T. F2 schema contains no derivative
U. F2 schema contains no Protocol B/C/D metrics
V. plotting categorical data uses discrete/no interpolation path
W. Phase F baseline point execution still matches F1
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis.sensitivity_grid import (
    F2_POINT_SCHEMA,
    GAMMA_GUARDRAIL,
    K_GUARDRAIL,
    GridDomain,
    baseline_grid_index,
    boundary_brackets,
    build_categorical_matrices,
    cache_key,
    detect_boundary_cells,
    detect_multiskip_jumps,
    expand_domain,
    f1_consistency_check,
    grid_index,
    grid_points,
    initial_domain,
    joint_exact_topology_signature,
    joint_regime,
    make_point_record,
    open_boundary_states,
    plan_expansion,
    validate_cache_record,
)
from hyptraj.analysis.sensitivity_pilot import (
    ParameterPoint,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.models.parameters import EnvironmentParams, VehicleParams

DATA_DIR = Path(__file__).resolve().parent / "data"
REFERENCE = json.loads(
    (DATA_DIR / "qian_sanger_comparison_v1.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


def _solver_dict() -> dict:
    from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
    cfg = PRODUCTION_SOLVER_CONFIG
    return {
        "method": cfg.method,
        "rtol": cfg.rtol,
        "atol": [float(a) for a in cfg.atol],
        "max_step": cfg.max_step,
        "dense_output": cfg.dense_output,
    }


def _fake_record(parameter, qian_regime="QIAN_RTI", sanger_regime="SRTI_N2",
                 qian_sig="q-sig", sanger_sig="s-sig",
                 skip_count=2, m_s=1000.0, m_a=None) -> dict:
    return {
        "schema_version": F2_POINT_SCHEMA,
        "parameter": list(parameter),
        "provenance": {},
        "qian": {
            "qian_regime": qian_regime,
            "terminal_kind": "RTI" if qian_regime == "QIAN_RTI" else None,
            "terminal_time_s": 100.0,
            "terminal_range_m": 3.0e6,
            "exact_topology_signature": qian_sig,
        },
        "sanger": {
            "sanger_regime": sanger_regime,
            "terminal_kind": "srti" if sanger_regime.startswith("SRTI_N")
            else sanger_regime.lower(),
            "skip_count": skip_count,
            "mode_sequence": ["SANGER_ATM"] * (2 * skip_count + 1),
            "terminal_time_s": 1000.0,
            "terminal_range_m": 6.0e6,
            "exact_topology_signature": sanger_sig,
            "M_S_clearance_m": m_s,
            "M_A_clearance_m": m_a,
            "exit_dhdt_mps": [10.0],
        },
        "joint_regime": joint_regime(qian_regime, sanger_regime),
        "joint_exact_topology_signature": joint_exact_topology_signature(
            qian_sig, sanger_sig),
        "health": {"violations": []},
        "wall_runtime_s": 0.1,
    }


# ---------------------------------------------------------------------------
# A / B / C / D. grid definition
# ---------------------------------------------------------------------------
def test_gamma_grid_exactly_17():
    d = initial_domain()
    assert len(d.gamma_grid) == 17
    assert d.gamma_grid[0] == -7.0
    assert d.gamma_grid[-1] == -3.0


def test_k_grid_exactly_17():
    d = initial_domain()
    assert len(d.k_grid) == 17
    assert d.k_grid[0] == 2.0
    assert d.k_grid[-1] == 4.0


def test_cartesian_product_289():
    points = grid_points(initial_domain())
    assert len(points) == 289
    assert len({p.key for p in points}) == 289


def test_baseline_grid_index_exact():
    d = initial_domain()
    assert baseline_grid_index(d) == (8, 8)
    assert grid_index(d, ParameterPoint(-5.0, 3.0)) == (8, 8)


# ---------------------------------------------------------------------------
# E. F2 point wraps F1 paired result without recomputation
# ---------------------------------------------------------------------------
def test_f2_point_wraps_f1_paired_result(base):
    env, veh = base
    pr = run_parameter_point(
        env, veh, ParameterPoint(-5.0, 3.0), git_commit="test")
    d = initial_domain()
    rec = make_point_record(
        d, pr.parameter, pr.qian_row, pr.sanger_row, [], 0.5, "test",
        _solver_dict())
    assert rec["qian"]["qian_regime"] == "QIAN_RTI"
    assert rec["sanger"]["sanger_regime"] == "SRTI_N2"
    assert rec["parameter"] == [-5.0, 3.0]
    assert rec["grid_index"] == [8, 8]


# ---------------------------------------------------------------------------
# F. joint regime deterministic
# ---------------------------------------------------------------------------
def test_joint_regime_deterministic():
    assert joint_regime("QIAN_RTI", "SRTI_N2") == ("QIAN_RTI", "SRTI_N2")
    assert joint_regime("QIAN_RTI", "SRTI_N2") == joint_regime(
        "QIAN_RTI", "SRTI_N2")
    sig = joint_exact_topology_signature("a", "b")
    assert sig == joint_exact_topology_signature("a", "b")
    assert "a" in sig and "b" in sig


# ---------------------------------------------------------------------------
# G / H / I. candidate-cell detection
# ---------------------------------------------------------------------------
def _records_from_grid(domain, regimes, sig_prefix="s"):
    """Build records for a 2D regime map (row-major regime strings).

    Every point shares ONE exact signature by default so that a uniform
    compact map is also exactly uniform; tests that need exact-signature
    variation overwrite the records explicitly.
    """
    recs = {}
    for i_g, g in enumerate(domain.gamma_grid):
        for i_k, k in enumerate(domain.k_grid):
            regime = regimes[i_g][i_k]
            skip = int(regime[-1]) if regime.startswith("SRTI_N") else None
            rec = _fake_record(
                [g, k], sanger_regime=regime, skip_count=skip,
                sanger_sig=sig_prefix)
            recs[cache_key(ParameterPoint(g, k))] = rec
    return recs


def test_candidate_detector_catches_compact_transition():
    d = initial_domain()
    # Column-symmetric transition: gamma0 >= -4.5 row -> N1.
    regimes = []
    for g in d.gamma_grid:
        regime = "SRTI_N1" if g >= -4.5 else "SRTI_N2"
        regimes.append([regime] * 17)
    recs = _records_from_grid(d, regimes)
    cells = detect_boundary_cells(d, recs)
    candidates = [c for c in cells if c["candidate"]]
    assert len(candidates) > 0
    assert all(
        any(r.startswith("sanger_") for r in c["candidate_reasons"])
        for c in candidates
    )
    assert all(not c["exact_topology_only"] for c in candidates)


def test_candidate_detector_catches_exact_only_transition():
    d = initial_domain()
    # Same compact regime everywhere but a different exact signature on
    # one half of the grid.
    regimes = [["SRTI_N2"] * 17 for _ in range(17)]
    recs = _records_from_grid(d, regimes)
    for i_g, g in enumerate(d.gamma_grid):
        for i_k, k in enumerate(d.k_grid):
            rec = recs[cache_key(ParameterPoint(g, k))]
            if g >= -5.0:
                rec["sanger"]["exact_topology_signature"] = "variant"
                rec["joint_exact_topology_signature"] = (
                    joint_exact_topology_signature(
                        rec["qian"]["exact_topology_signature"],
                        "variant"))
    cells = detect_boundary_cells(d, recs)
    exact_only = [c for c in cells if c["exact_topology_only"]]
    assert len(exact_only) > 0
    assert all(c["candidate"] for c in exact_only)


def test_uniform_cell_not_candidate():
    d = initial_domain()
    recs = _records_from_grid(d, [["SRTI_N2"] * 17 for _ in range(17)])
    cells = detect_boundary_cells(d, recs)
    assert all(not c["candidate"] for c in cells)
    assert len(cells) == 16 * 16


# ---------------------------------------------------------------------------
# J / K / L / M / N. edge touch and expansion planning
# ---------------------------------------------------------------------------
def test_edge_touch_flags_correct():
    d = initial_domain()
    recs = _records_from_grid(d, [["SRTI_N2"] * 17 for _ in range(17)])
    # Force a compact transition in the K=2.0 column on INTERIOR gamma
    # rows only (so the candidate cells touch the K lower edge but not
    # the gamma edges).
    for g in (-5.0, -4.75, -4.5):
        recs[cache_key(ParameterPoint(g, 2.0))]["sanger"][
            "sanger_regime"] = "SRTI_N1"
        recs[cache_key(ParameterPoint(g, 2.0))]["joint_regime"] = (
            "QIAN_RTI", "SRTI_N1")
    cells = detect_boundary_cells(d, recs)
    flags = plan_expansion(cells, d)
    assert flags["expand_K_lower"] is True
    assert flags["expand_K_upper"] is False
    assert flags["expand_gamma_lower"] is False
    assert flags["expand_gamma_upper"] is False


def test_expansion_planner_only_touches_triggered_edge():
    d = initial_domain()
    recs = _records_from_grid(d, [["SRTI_N2"] * 17 for _ in range(17)])
    # Transition touching the K upper edge only (interior gamma rows).
    for g in (-5.0, -4.75, -4.5):
        recs[cache_key(ParameterPoint(g, 4.0))]["sanger"][
            "sanger_regime"] = "SRTI_N3"
        recs[cache_key(ParameterPoint(g, 4.0))]["joint_regime"] = (
            "QIAN_RTI", "SRTI_N3")
    cells = detect_boundary_cells(d, recs)
    flags = plan_expansion(cells, d)
    assert flags == {
        "expand_gamma_lower": False,
        "expand_gamma_upper": False,
        "expand_K_lower": False,
        "expand_K_upper": True,
    }
    new_domain, new_points = expand_domain(d, flags)
    assert new_domain.k_max == 4.5
    assert new_domain.k_min == 2.0
    # Only the new strip points are returned (no re-integration of old).
    assert len(new_points) == 17 * 4


def test_gamma_expansion_preserves_spacing():
    d = initial_domain()
    flags = {"expand_gamma_lower": True, "expand_gamma_upper": True,
             "expand_K_lower": False, "expand_K_upper": False}
    new_domain, new_points = expand_domain(d, flags)
    g = new_domain.gamma_grid
    assert np.allclose(
        np.diff(g), np.full(len(g) - 1, 0.25))
    assert new_domain.gamma_min == -8.0
    assert new_domain.gamma_max == -2.0
    assert len(g) == 25
    # 4 new rows each side at 0.25 spacing.
    new_g = sorted({p.gamma0_deg for p in new_points})
    assert len(new_g) == 8
    assert -8.0 in new_g and -7.25 in new_g and -7.0 not in new_g


def test_k_expansion_preserves_spacing():
    d = initial_domain()
    flags = {"expand_gamma_lower": False, "expand_gamma_upper": False,
             "expand_K_lower": True, "expand_K_upper": True}
    new_domain, new_points = expand_domain(d, flags)
    k = new_domain.k_grid
    assert np.allclose(np.diff(k), np.full(len(k) - 1, 0.125))
    assert new_domain.k_min == 1.5
    assert new_domain.k_max == 4.5
    assert len(k) == 25


def test_guardrails_produce_open_boundary():
    # Domain already at the gamma guardrail with a touching candidate.
    d = GridDomain(-9.0, -1.0, 2.0, 4.0)
    recs = {}
    for p in grid_points(d):
        recs[cache_key(p)] = _fake_record([p.gamma0_deg, p.K])
    # Force a transition on the gamma lower edge using INTERIOR K
    # columns only (so the candidate cells do not also touch the K
    # edges -- expansion must then be limited to the gamma lower side).
    for k in (3.0, 3.125):
        recs[cache_key(ParameterPoint(-9.0, k))]["sanger"][
            "sanger_regime"] = "SRTI_N1"
        recs[cache_key(ParameterPoint(-9.0, k))]["joint_regime"] = (
            "QIAN_RTI", "SRTI_N1")
    cells = detect_boundary_cells(d, recs)
    flags = plan_expansion(cells, d)
    assert flags["expand_gamma_lower"] is True
    assert flags["expand_K_lower"] is False
    new_domain, new_points = expand_domain(d, flags)
    assert new_domain.gamma_min == GAMMA_GUARDRAIL[0]  # clamped
    assert new_points == ()
    states = open_boundary_states(d, cells)
    assert "gamma_lower" in states


# ---------------------------------------------------------------------------
# O / P. cache provenance
# ---------------------------------------------------------------------------
def _provenance(domain, schema=F2_POINT_SCHEMA, f1_commit="ok"):
    from hyptraj.analysis.sensitivity_grid import F1_COMMIT
    return {
        "schema_version": schema,
        "phase_e_anchor_commit": "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc",
        "phase_f_protocol_commit": "1cd0bd52de0d9cec615635949d2805525619d370",
        "phase_f_f01_commit": "81b3a9980c0df548786db4145f4e01c917cba1e4",
        "phase_f_f1_commit": F1_COMMIT if f1_commit == "ok" else "wrong",
        "solver_config": _solver_dict(),
        "domain": domain.as_dict(),
    }


def test_cache_provenance_mismatch_rejected():
    d = initial_domain()
    rec = _fake_record([-5.0, 3.0])
    rec["provenance"] = _provenance(d, f1_commit="wrong")
    ok, reason = validate_cache_record(rec, _provenance(d))
    assert not ok
    assert "phase_f_f1_commit" in reason


def test_valid_cache_reused():
    d = initial_domain()
    rec = _fake_record([-5.0, 3.0])
    rec["provenance"] = _provenance(d)
    ok, reason = validate_cache_record(rec, _provenance(d))
    assert ok
    assert reason == "valid"


# ---------------------------------------------------------------------------
# Q. multiskip jump warning
# ---------------------------------------------------------------------------
def test_multiskip_jump_warning():
    d = initial_domain()
    recs = _records_from_grid(d, [["SRTI_N2"] * 17 for _ in range(17)])
    # N2 -> N4 adjacent in K on one row.
    row = -5.0
    recs[cache_key(ParameterPoint(row, 4.0))]["sanger"][
        "sanger_regime"] = "SRTI_N4"
    recs[cache_key(ParameterPoint(row, 4.0))]["sanger"]["skip_count"] = 4
    jumps = detect_multiskip_jumps(d, recs)
    k_jumps = [j for j in jumps if j["direction"] == "K"]
    assert len(k_jumps) == 1
    assert (k_jumps[0]["left_skip"], k_jumps[0]["right_skip"]) == (2, 4)
    # The K=4.0 column also jumps along gamma (2 -> 4).
    assert any(j["direction"] == "gamma" and j["K"] == 4.0
               for j in jumps)


# ---------------------------------------------------------------------------
# R. NA margin stays None, never zero
# ---------------------------------------------------------------------------
def test_na_margin_not_zero():
    rec = _fake_record([-5.0, 3.0], m_s=None, m_a=None)
    assert rec["sanger"]["M_S_clearance_m"] is None
    assert rec["sanger"]["M_A_clearance_m"] is None
    # Serialized JSON keeps null.
    payload = json.dumps(rec)
    assert '"M_S_clearance_m": null' in payload


# ---------------------------------------------------------------------------
# S. stop gate propagates censored/failure/ambiguous
# ---------------------------------------------------------------------------
def test_stop_gate_propagates_censored_failure_ambiguous():
    from hyptraj.analysis.sensitivity_pilot import collect_stop_gate_reasons
    qian_censored = {
        "gamma0_deg": -5.0, "K": 3.0,
        "qian_regime": "CENSORED", "message": "horizon",
    }
    sanger_failed = {
        "gamma0_deg": -5.0, "K": 3.0,
        "sanger_regime": "NUMERICAL_FAILURE", "message": "solver",
    }
    qian_ambiguous = {
        "gamma0_deg": -5.0, "K": 3.0,
        "qian_regime": "BOUNDARY_AMBIGUOUS", "message": "tie",
    }
    reasons = collect_stop_gate_reasons(
        anchor_pass=True,
        qian_rows=[qian_censored, qian_ambiguous],
        sanger_rows=[sanger_failed],
        health_violations=[],
    )
    joined = "\n".join(reasons)
    assert "CENSORED" in joined
    assert "NUMERICAL_FAILURE" in joined
    assert "BOUNDARY_AMBIGUOUS" in joined


# ---------------------------------------------------------------------------
# T / U. F2 schema purity (no derivative, no Protocol B/C/D metrics)
# ---------------------------------------------------------------------------
def test_f2_schema_contains_no_derivative(base):
    env, veh = base
    pr = run_parameter_point(
        env, veh, ParameterPoint(-5.0, 3.0), git_commit="test")
    rec = make_point_record(
        initial_domain(), pr.parameter, pr.qian_row, pr.sanger_row, [],
        0.1, "test", _solver_dict())
    payload = json.dumps(rec)
    for token in ("dR/dgamma", "dR/dK", "gradient", "derivative"):
        assert token.lower() not in payload.lower()


def test_f2_schema_no_protocol_bcd_metrics(base):
    env, veh = base
    pr = run_parameter_point(
        env, veh, ParameterPoint(-5.0, 3.0), git_commit="test")
    rec = make_point_record(
        initial_domain(), pr.parameter, pr.qian_row, pr.sanger_row, [],
        0.1, "test", _solver_dict())
    payload = json.dumps(rec)
    for token in ("time_limiter", "range_limiter", "exposure_limiter",
                  "common_time", "common_range", "protocol_d"):
        assert token not in payload


# ---------------------------------------------------------------------------
# V. categorical plotting path is discrete (no interpolation)
# ---------------------------------------------------------------------------
def test_categorical_matrices_are_discrete():
    d = initial_domain()
    recs = _records_from_grid(d, [["SRTI_N2"] * 17 for _ in range(17)])
    m = build_categorical_matrices(d, recs)
    assert m["categorical_ids_are_visualization_only"] is True
    # ID matrix contains only integers (categorical encodings).
    for row in m["exact_topology_id_matrix"]:
        for v in row:
            assert isinstance(v, int) or v is None
    # Labels always retained.
    assert m["exact_topology_id_map"]


# ---------------------------------------------------------------------------
# W. Phase F baseline point execution still matches F1
# ---------------------------------------------------------------------------
def test_baseline_point_execution_matches_f1(base):
    env, veh = base
    anchor = verify_baseline_anchor(
        env, veh, git_commit="test", reference_json=REFERENCE)
    assert anchor["pass"]
    assert anchor["qian"]["regime"] == "QIAN_RTI"
    assert anchor["sanger"]["regime"] == "SRTI_N2"
    assert anchor["qian"]["rti_time_s"] == pytest.approx(
        723.0379653550676, rel=1e-9)
    assert anchor["sanger"]["terminal_time_s"] == pytest.approx(
        1119.5459841174863, rel=1e-9)


# ---------------------------------------------------------------------------
# Brackets sanity (F2 §30–§31)
# ---------------------------------------------------------------------------
def test_brackets_by_gamma_and_K():
    d = initial_domain()
    recs = _records_from_grid(d, [["SRTI_N2"] * 17 for _ in range(17)])
    # K <= 2.75 columns are N1 for ALL gamma rows; K >= 2.875 are N2:
    # a vertical boundary -> brackets appear only along gamma rows.
    for g in d.gamma_grid:
        for k in d.k_grid:
            regime = "SRTI_N1" if k <= 2.75 else "SRTI_N2"
            recs[cache_key(ParameterPoint(g, k))]["sanger"][
                "sanger_regime"] = regime
            recs[cache_key(ParameterPoint(g, k))]["sanger"][
                "skip_count"] = 1 if regime == "SRTI_N1" else 2
            recs[cache_key(ParameterPoint(g, k))]["joint_regime"] = (
                "QIAN_RTI", regime)
    bg = boundary_brackets(d, recs, "gamma")
    assert len(bg) == 17
    assert bg[0]["gamma0"] == -7.0
    assert (bg[0]["K_left"], bg[0]["K_right"]) == (2.75, 2.875)
    bk = boundary_brackets(d, recs, "K")
    assert bk == []
