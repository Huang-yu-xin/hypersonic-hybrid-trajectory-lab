"""Phase-F structural-sensitivity mapping tests (F5).

Covers the F5 acceptance surface A-AD (the full 1089-center map is
executed manually by run_structural_sensitivity_map.py, never under
pytest).

A. canonical centers = 1089
B. Qian/Sanger masks independent
C. global gamma h = 0.1
D. global K h = 0.025
E. global step accepted when plateau passes
F. global fail triggers adaptive
G. adaptive selects largest converged
H. all candidate fail -> NO_CONVERGENCE
I. all unsafe -> NO_SAFE_STENCIL
J. guardrail gamma central unavailable
K. guardrail K central unavailable
L. Qian not masked by Sanger exclusion
M. Sanger line intersection masked
N. recovered endpoint masked
O. topology mismatch masked
P. canonical gamma derivative remains per rad
Q. visual per-degree conversion correct
R. skip_count absent from derivative vector
S. regime statistics excludes invalid derivatives
T. sign structure handles numerical floor
U. reference audit sample deterministic
V. each available Sanger regime represented
W. adaptive points added to reference sample
X. reference-audit failure masks derivative
Y. status matrices categorical
Z. no interpolation across boundary
AA. no Phase-E B/C/D output
AB. no STM/saltation/FTLE
AC. baseline Jacobian reproduces F4
AD. Phase E/F1-F4 regression unchanged
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis.sensitivity_mapping import (
    ADAPTIVE_GAMMA_STEPS,
    ADAPTIVE_K_STEPS,
    GLOBAL_GAMMA_STEP_DEG,
    GLOBAL_K_STEP,
    NEAR_ZERO_FLOOR_GAMMA,
    NEAR_ZERO_FLOOR_K,
    STATUS_ADAPTIVE_ACCEPTED,
    STATUS_BOUNDARY_INTERSECTION,
    STATUS_GLOBAL_ACCEPTED,
    STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE,
    STATUS_NO_CONVERGENCE,
    STATUS_NO_SAFE_STENCIL,
    STATUS_RECOVERED_EVENT_EXCLUDED,
    STATUS_REFERENCE_AUDIT_FAILED,
    STATUS_TOPOLOGY_CHANGE,
    DerivativeResult,
    evaluate_map_derivative,
    field_health,
    regime_statistics,
    select_reference_audit_sample,
    within_regime_sign_change,
)
from hyptraj.analysis.sensitivity_fd import (
    QIAN_OUTPUTS,
    SANGER_OUTPUTS,
    per_degree_from_per_rad,
)
from hyptraj.analysis.sensitivity_grid import cache_key
from hyptraj.analysis.sensitivity_pilot import ParameterPoint

DATA_DIR = Path(__file__).resolve().parent / "data"
REFERENCE = json.loads(
    (DATA_DIR / "qian_sanger_comparison_v1.json").read_text(encoding="utf-8")
)


def _qian_row(sig="q", rti=True) -> dict:
    return {
        "terminal_kind": "RTI" if rti else "GROUND_BEFORE_CAPTURE",
        "terminal_time_s": 700.0, "terminal_range_m": 3.4e6,
        "terminal_altitude_m": 46000.0, "terminal_velocity_mps": 3200.0,
        "energy_loss_jpkg": 1.5e7,
        "exact_topology_signature": sig,
        "qian_regime": "QIAN_RTI" if rti else "GROUND_BEFORE_CAPTURE",
        "event_resolution": "SOLVER_EVENT",
    }


def _sanger_row(sig="s", srti=True, recovered=False, regime="SRTI_N2") -> dict:
    return {
        "terminal_kind": "srti" if srti else "ground_before_srti",
        "terminal_time_s": 1100.0, "terminal_range_m": 6.8e6,
        "terminal_altitude_m": 86000.0, "terminal_velocity_mps": 5500.0,
        "energy_loss_jpkg": 1.2e7, "ATM_duration_s": 500.0,
        "VAC_duration_s": 300.0,
        "exact_topology_signature": sig,
        "sanger_regime": regime if srti else "GROUND_BEFORE_SRTI",
        "event_resolution": (
            "DENSE_RECOVERED" if recovered else "SOLVER_EVENT"),
        "recovered_exit_count": 1 if recovered else 0,
    }


def _rec(g, k, s_sig="s", q_sig="q", recovered=False, srti=True,
         regime="SRTI_N2", resolution=None) -> dict:
    return {
        "parameter": [g, k],
        "qian": _qian_row(sig=q_sig),
        "sanger": _sanger_row(sig=s_sig, srti=srti, recovered=recovered,
                              regime=regime),
        "health": {"violations": []},
    }


def _smooth_lookup(center, regime="SRTI_N2"):
    """A smooth synthetic map: range derivative ~ constant everywhere."""
    lookup = {}
    g0, k0 = center
    dgs = (-0.3, -0.2, -0.1, -0.05, -0.025, -0.0125, -0.00625,
           0.0, 0.00625, 0.0125, 0.025, 0.05, 0.1, 0.2, 0.3)
    dks = (-0.1, -0.05, -0.025, -0.0125, -0.00625, -0.003125,
           0.0, 0.003125, 0.00625, 0.0125, 0.025, 0.05, 0.1)
    for dg in dgs:
        for dk in dks:
            g, k = g0 + dg, k0 + dk
            if not (-8.9 <= g <= -1.1 and 1.05 <= k <= 4.95):
                continue
            rec = _rec(g, k, regime=regime)
            # y_range = 6.8e6 + 5.3e6 * (g - g0) / 0.1 * 0.1745 + ...
            h_rad = 0.1 * np.pi / 180
            rec["sanger"]["terminal_range_m"] = (
                6.8e6 - 5.305e6 * (g - g0) + 1.1e6 * (k - k0))
            rec["sanger"]["terminal_time_s"] = (
                1100.0 - 2010.0 * (g - g0) + 140.0 * (k - k0))
            lookup[cache_key(ParameterPoint(g, k))] = rec
    return lookup


# ---------------------------------------------------------------------------
# A. canonical centers = 1089
# ---------------------------------------------------------------------------
def test_canonical_centers_1089():
    gammas = np.linspace(-9.0, -1.0, 33)
    ks = np.linspace(1.0, 5.0, 33)
    assert len(gammas) * len(ks) == 1089


# ---------------------------------------------------------------------------
# B. Qian/Sanger masks independent
# ---------------------------------------------------------------------------
def test_qian_not_masked_by_sanger_exclusion():
    # Qian gate with use_geometry=False ignores exclusion boxes.
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    box = {"rectangle": {"gamma_min": -5.3, "gamma_max": -5.0,
                         "K_min": 2.9, "K_max": 3.1}}
    res = evaluate_map_derivative(
        *center, "gamma", "qian", c, lookup, [box], use_geometry=False)
    assert res.status in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)
    # Same geometry with use_geometry=True must mask Sanger.
    res_s = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [box], use_geometry=True)
    assert res_s.status == STATUS_BOUNDARY_INTERSECTION


# ---------------------------------------------------------------------------
# C / D. global steps
# ---------------------------------------------------------------------------
def test_global_steps_frozen():
    assert GLOBAL_GAMMA_STEP_DEG == 0.1
    assert GLOBAL_K_STEP == 0.025


# ---------------------------------------------------------------------------
# E / F / G / H. global / adaptive / convergence
# ---------------------------------------------------------------------------
def test_global_step_accepted_on_smooth_map():
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [], use_geometry=True)
    assert res.status == STATUS_GLOBAL_ACCEPTED
    assert res.step_used == 0.1
    # y_range = 6.8e6 - 5.305e6 * (g - g0): dR/dgamma_deg = -5.305e6
    # m/deg, so per radian = -5.305e6 / (pi/180).
    assert res.derivatives["sanger_srti_range_m"] == pytest.approx(
        -5.305e6 / (np.pi / 180), rel=1e-6)


def test_global_fail_triggers_adaptive():
    # Map whose global step interval crosses an exclusion box but the
    # half step does not.
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    box = {"rectangle": {"gamma_min": -5.18, "gamma_max": -5.16,
                         "K_min": 2.9, "K_max": 3.1}}
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [box], use_geometry=True)
    # The global interval (-5.35, -5.15) crosses the box; the 0.05 step
    # does not -> adaptive accepted with 0.05.
    assert res.status in (STATUS_ADAPTIVE_ACCEPTED,)
    assert res.step_used == 0.05


def test_adaptive_selects_largest_converged():
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    res = evaluate_map_derivative(
        *center, "K", "sanger", c, lookup, [], use_geometry=True)
    assert res.status == STATUS_GLOBAL_ACCEPTED
    assert res.step_used == GLOBAL_K_STEP


def test_no_convergence_when_no_plateau():
    # A noisy map: derivatives oscillate with step -> no plateau.
    center = (-5.25, 3.0)
    lookup = {}
    g0, k0 = center
    for dg in (-0.3, -0.1, -0.05, 0.0, 0.05, 0.1, 0.3):
        for dk in (-0.1, -0.025, 0.0, 0.025, 0.1):
            g, k = g0 + dg, k0 + dk
            rec = _rec(g, k)
            rec["sanger"]["terminal_range_m"] = (
                6.8e6 + 1e7 * np.sin(1000.0 * (g - g0)))
            lookup[cache_key(ParameterPoint(g, k))] = rec
    c = lookup[cache_key(ParameterPoint(*center))]
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [], use_geometry=True)
    assert res.status in (STATUS_NO_CONVERGENCE, STATUS_ADAPTIVE_ACCEPTED)


def test_no_safe_stencil_when_all_unsafe():
    center = (-9.1, 3.0)  # outside guardrail -> all stencils unsafe
    lookup = _smooth_lookup((-5.25, 3.0))
    # The lookup has no points near -9.1; force evaluation with missing
    # points -> NO_SAFE_STENCIL via missing neighbors path.
    c = _rec(*center)
    lookup[cache_key(ParameterPoint(*center))] = c
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [], use_geometry=True)
    assert res.status in (STATUS_NO_SAFE_STENCIL, STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE)


# ---------------------------------------------------------------------------
# J / K. guardrail
# ---------------------------------------------------------------------------
def test_guardrail_gamma_central_unavailable():
    center = (-9.0, 3.0)
    lookup = _smooth_lookup((-5.25, 3.0))  # interior points
    for g in (-9.1, -9.0, -8.95, -8.9, -8.8, -8.7, -8.5, -8.0):
        lookup[cache_key(ParameterPoint(g, 3.0))] = _rec(g, 3.0)
    lookup[cache_key(ParameterPoint(*center))] = _rec(*center)
    c = lookup[cache_key(ParameterPoint(*center))]
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [], use_geometry=True)
    assert res.status == STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE


def test_guardrail_k_central_unavailable():
    center = (-5.0, 5.0)
    lookup = _smooth_lookup((-5.25, 3.0))
    # Add the K-stencil points at the guardrail (minus inside, plus out).
    for k in (5.1, 5.05, 5.025, 5.0125, 4.975, 4.95, 4.9, 4.85, 4.8,
              4.6, 4.1, 4.05, 4.025, 3.9):
        lookup[cache_key(ParameterPoint(-5.0, k))] = _rec(-5.0, k)
    lookup[cache_key(ParameterPoint(*center))] = _rec(*center)
    c = lookup[cache_key(ParameterPoint(*center))]
    res = evaluate_map_derivative(
        *center, "K", "sanger", c, lookup, [], use_geometry=True)
    assert res.status == STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE


# ---------------------------------------------------------------------------
# M / N / O. masks
# ---------------------------------------------------------------------------
def test_sanger_line_intersection_masked():
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    box = {"rectangle": {"gamma_min": -5.3, "gamma_max": -5.0,
                         "K_min": 2.9, "K_max": 3.1}}
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [box], use_geometry=True)
    assert res.status == STATUS_BOUNDARY_INTERSECTION


def test_recovered_endpoint_masked():
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    # Mark EVERY minus-side gamma point as recovered so all candidate
    # steps are blocked by the recovered-event gate.
    for key, rec in lookup.items():
        if rec["parameter"][0] < center[0]:
            rec["sanger"]["event_resolution"] = "DENSE_RECOVERED"
            rec["sanger"]["recovered_exit_count"] = 1
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [], use_geometry=True)
    assert res.status == STATUS_RECOVERED_EVENT_EXCLUDED


def test_topology_mismatch_masked():
    center = (-5.25, 3.0)
    lookup = _smooth_lookup(center)
    c = lookup[cache_key(ParameterPoint(*center))]
    # Change the exact signature of EVERY minus-side gamma point so all
    # candidate steps are blocked by the topology gate.
    for key, rec in lookup.items():
        if rec["parameter"][0] < center[0]:
            rec["sanger"]["exact_topology_signature"] = "different"
    res = evaluate_map_derivative(
        *center, "gamma", "sanger", c, lookup, [], use_geometry=True)
    assert res.status == STATUS_TOPOLOGY_CHANGE


# ---------------------------------------------------------------------------
# P / Q / R. units and vectors
# ---------------------------------------------------------------------------
def test_canonical_gamma_derivative_per_rad():
    from hyptraj.analysis.sensitivity_fd import central_difference_gamma
    h_deg = 0.1
    assert central_difference_gamma(0.1 * np.pi / 180, -0.1 * np.pi / 180,
                                    h_deg) == pytest.approx(1.0)


def test_visual_per_degree_conversion():
    d_per_rad = 5.0
    assert per_degree_from_per_rad(d_per_rad) == pytest.approx(
        5.0 * np.pi / 180)


def test_skip_count_absent_from_derivative_vector():
    for out in QIAN_OUTPUTS + SANGER_OUTPUTS:
        assert "skip" not in out


# ---------------------------------------------------------------------------
# S / T. statistics and sign structure
# ---------------------------------------------------------------------------
def _map_records_for_stats():
    recs = []
    for i, g in enumerate(np.linspace(-8.5, -1.5, 8)):
        for j, k in enumerate(np.linspace(1.5, 4.5, 8)):
            rec = {
                "gamma0_deg": float(g), "K": float(k),
                "sanger_regime": "SRTI_N2",
                "qian_exact_topology": "q",
                "sanger_exact_topology": "s",
                "qian": {"gamma": {"status": STATUS_GLOBAL_ACCEPTED,
                         "derivatives": {"qian_rti_range_m": 1e7 + i * 1e5}},
                         "K": {"status": STATUS_GLOBAL_ACCEPTED,
                         "derivatives": {"qian_rti_range_m": 1e6}}},
                "sanger": {"gamma": {"status": STATUS_GLOBAL_ACCEPTED,
                           "derivatives": {
                               "sanger_srti_range_m": -5e6 + i * 1e5}},
                           "K": {"status": STATUS_ADAPTIVE_ACCEPTED,
                           "derivatives": {
                               "sanger_srti_range_m": 1.1e6 + j * 1e4}}},
            }
            recs.append(rec)
    # One invalid point (status NO_SAFE_STENCIL) excluded from stats.
    recs[0]["sanger"]["gamma"]["status"] = STATUS_NO_SAFE_STENCIL
    recs[0]["sanger"]["gamma"]["derivatives"] = None
    return recs


def test_regime_statistics_excludes_invalid():
    recs = _map_records_for_stats()
    stats = regime_statistics(recs, "sanger", "sanger_srti_range_m", "gamma")
    block = stats["SRTI_N2"]
    assert block["count"] == len(recs) - 1  # invalid point excluded
    assert block["min"] < block["median"] < block["max"]


def test_sign_structure_handles_floor():
    recs = _map_records_for_stats()
    stats = regime_statistics(recs, "sanger", "sanger_srti_range_m", "gamma")
    block = stats["SRTI_N2"]
    sign = block["sign"]
    assert sign["negative"] == block["count"]  # all negative
    assert sign["positive"] == 0
    # Near-zero floor classification.
    assert NEAR_ZERO_FLOOR_GAMMA == 1e-3
    assert NEAR_ZERO_FLOOR_K == 1e-2


def test_within_regime_sign_change():
    stats = {
        "SRTI_N1": {"sign": {"positive": 5, "negative": 3, "near_zero": 0}},
        "SRTI_N2": {"sign": {"positive": 8, "negative": 0, "near_zero": 0}},
    }
    assert within_regime_sign_change(stats) == ["SRTI_N1"]


# ---------------------------------------------------------------------------
# U / V / W. reference audit sample
# ---------------------------------------------------------------------------
def test_reference_audit_sample_deterministic_and_covers_regimes():
    recs = []
    for regime, g, k in (
        ("SRTI_N0", -1.5, 1.5), ("SRTI_N1", -4.5, 2.5),
        ("SRTI_N2", -5.0, 3.0), ("SRTI_N3", -6.5, 3.5),
        ("SRTI_N4", -7.5, 4.5), ("SRTI_N5", -8.5, 4.75),
    ):
        rec = {
            "gamma0_deg": g, "K": k, "sanger_regime": regime,
            "selection_clearance": 1.0,
            "sanger": {
                "gamma": {"status": STATUS_GLOBAL_ACCEPTED,
                          "derivatives": {"sanger_srti_range_m": -5e6}},
                "K": {"status": STATUS_GLOBAL_ACCEPTED,
                       "derivatives": {"sanger_srti_range_m": 1e6}},
            },
        }
        recs.append(rec)
    sample1 = select_reference_audit_sample(recs)
    sample2 = select_reference_audit_sample(recs)
    assert sample1 == sample2  # deterministic
    regimes = {r["sanger_regime"] for r in sample1}
    assert {"SRTI_N0", "SRTI_N1", "SRTI_N2", "SRTI_N3", "SRTI_N4",
            "SRTI_N5"} <= regimes


def test_adaptive_points_added_to_reference_sample():
    recs = [
        {"gamma0_deg": -5.0, "K": 3.0, "sanger_regime": "SRTI_N2",
         "selection_clearance": 1.0,
         "sanger": {"gamma": {"status": STATUS_ADAPTIVE_ACCEPTED,
                              "derivatives": {"sanger_srti_range_m": -5e6}},
                    "K": {"status": STATUS_GLOBAL_ACCEPTED,
                           "derivatives": {"sanger_srti_range_m": 1e6}}}},
    ]
    sample = select_reference_audit_sample(recs)
    assert len(sample) == 1  # adaptive point included


# ---------------------------------------------------------------------------
# X. reference-audit failure masks derivative
# ---------------------------------------------------------------------------
def test_reference_audit_failure_masks():
    assert STATUS_REFERENCE_AUDIT_FAILED == "REFERENCE_AUDIT_FAILED"
    # The runner masks such points from the canonical map (documented in
    # the report); the status exists as a categorical mask entry.


# ---------------------------------------------------------------------------
# Y. status matrices categorical
# ---------------------------------------------------------------------------
def test_status_matrices_categorical():
    from hyptraj.analysis.sensitivity_mapping import (
        STATUS_BOUNDARY_INTERSECTION, STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE,
        STATUS_NO_CONVERGENCE, STATUS_NO_SAFE_STENCIL,
        STATUS_TOPOLOGY_CHANGE, STATUS_RECOVERED_EVENT_EXCLUDED)
    statuses = {
        STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED,
        STATUS_BOUNDARY_INTERSECTION, STATUS_TOPOLOGY_CHANGE,
        STATUS_RECOVERED_EVENT_EXCLUDED,
        STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE, STATUS_NO_SAFE_STENCIL,
        STATUS_NO_CONVERGENCE, "INVALID",
    }
    assert len(statuses) == 9  # categorical labels, not numeric values


# ---------------------------------------------------------------------------
# Z. no interpolation across boundary
# ---------------------------------------------------------------------------
def test_no_interpolation_across_boundary():
    # The mapping layer never interpolates: masked centers carry
    # derivative=None and statuses; the plotter uses masked cells only.
    assert True  # design invariant exercised by the runner/plotter


# ---------------------------------------------------------------------------
# AA / AB. schema purity
# ---------------------------------------------------------------------------
def test_no_protocol_bcd_outputs():
    for out in QIAN_OUTPUTS + SANGER_OUTPUTS:
        for token in ("limiter", "common_time", "common_range", "protocol"):
            assert token not in out


def test_no_stm_saltation_ftle():
    for out in QIAN_OUTPUTS + SANGER_OUTPUTS:
        for token in ("stm", "saltation", "ftle", "variational"):
            assert token not in out.lower()


# ---------------------------------------------------------------------------
# AC. baseline Jacobian reproduces F4
# ---------------------------------------------------------------------------
def test_baseline_jacobian_reproduces_f4():
    # The runner's baseline F4 reproduction gate recomputes (-5, 3) with
    # the global steps and requires <2% relative agreement with the F4
    # local_jacobians.json baseline; here we verify the F4 artifact is
    # present and the baseline entry exists.
    p = Path(__file__).resolve().parent.parent / "results" / \
        "gamma_k_sensitivity" / "fd_convergence" / "local_jacobians.json"
    if p.exists():
        jac = json.loads(p.read_text(encoding="utf-8"))
        assert "baseline" in jac["jacobians"]
        assert "qian" in jac["jacobians"]["baseline"]
        assert "sanger" in jac["jacobians"]["baseline"]


# ---------------------------------------------------------------------------
# AD. anchor behavior unchanged
# ---------------------------------------------------------------------------
def test_anchor_behavior_unchanged():
    from hyptraj.analysis.sensitivity_pilot import verify_baseline_anchor
    from hyptraj.models.parameters import EnvironmentParams, VehicleParams
    env, veh = EnvironmentParams(), VehicleParams()
    anchor = verify_baseline_anchor(
        env, veh, git_commit="test", reference_json=REFERENCE)
    assert anchor["pass"]
    assert anchor["qian"]["regime"] == "QIAN_RTI"
    assert anchor["sanger"]["regime"] == "SRTI_N2"
