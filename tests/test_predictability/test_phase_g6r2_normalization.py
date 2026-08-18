"""Phase-G6R2 linearization-error NORMALIZATION contract tests (G6R2 §5,
§17).

Guards the FROZEN Phase-G protocol definition of the paired-map relative
linearization error

    E = ||S^-1 (Delta_NL - Delta_LIN)|| / max(||S^-1 Delta_LIN||, floor)

i.e. ``ERROR / LINEAR PREDICTION`` -- NOT ``ERROR / NONLINEAR INCREMENT``.
A synthetic test distinguishes the two normalizations on paper; the scalar
/ 4-vector examples prove the implementation returns the protocol value
and the real 1%/5% radii are re-verified on the regenerated snapshot with
the protocol-correct normalization (paired FD results unchanged).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.predictability import grazing as G
from hyptraj.models.parameters import EnvironmentParams, VehicleParams

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAP = json.loads((DATA_DIR / "phase_g6_grazing_predictability_v1.json")
                  .read_text(encoding="utf-8"))
G6R = SNAP["g6r"]
G6R2 = SNAP["g6r2"]

_ONES = np.ones(4, dtype=float)


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


# ---------------------------------------------------------------------------
# 1. Synthetic denominator contract (protocol ERROR/LINEAR-PREDICTION)
# ---------------------------------------------------------------------------
def test_synthetic_denominator_is_linear_prediction():
    # linear prediction norm = 1.0, nonlinear increment norm = 1.1,
    # error norm = 0.1  ->  protocol E = 0.1 / 1.0 = 0.1
    lin = np.array([1.0, 0.0, 0.0, 0.0])
    err = np.array([0.1, 0.0, 0.0, 0.0])
    nl = lin + err  # norm 1.1
    assert np.isclose(np.linalg.norm(nl), 1.1)
    assert np.isclose(np.linalg.norm(err), 0.1)
    E = G.scaled_linearization_error(nl, lin, _ONES)
    assert E == pytest.approx(0.1)  # 0.1 / 1.0
    # the WRONG nonlinear-normalized value is 0.1/1.1 ~ 0.090909...
    assert not np.isclose(E, 0.1 / 1.1, atol=1e-6)
    assert abs(E - 0.1 / 1.1) > 1e-3


def test_exact_linear_map_is_exact_zero():
    lin = np.array([2.0, -1.0, 0.5, 3.0])
    E = G.scaled_linearization_error(lin, lin, _ONES)
    assert E == pytest.approx(0.0, abs=0.0)


def test_plus_minus_normalization_symmetry():
    # symmetric one-sided probes share the same linear-prediction
    # denominator  ||S^-1 (±eps p)||  -> E_plus == E_minus for the same
    # error term
    p = np.array([1.0, 2.0, 0.0, 1.0])
    eps = 1e-3
    err = np.array([0.0, 0.1 * eps ** 2, 0.0, 0.05 * eps ** 2])
    lin_plus = eps * p
    lin_minus = -eps * p
    nl_plus = lin_plus + err
    nl_minus = lin_minus + err
    Ep = G.scaled_linearization_error(nl_plus, lin_plus, _ONES)
    Em = G.scaled_linearization_error(nl_minus, lin_minus, _ONES)
    assert Ep == pytest.approx(Em)
    # minus-side linear-prediction norm equals the plus-side norm
    assert np.linalg.norm(lin_plus) == pytest.approx(
        np.linalg.norm(lin_minus))


def test_second_order_perturbation_is_O_epsilon():
    # Delta_NL = Delta_LIN + c eps^2 u  ->  E = (c||u||/||p||) eps = O(eps)
    p = np.array([1.0, 0.0, 0.0, 0.0])
    u = np.array([0.0, 1.0, 0.0, 0.0])
    c = 1.0
    ratios = []
    for eps in (1e-4, 1e-3, 1e-2):
        lin = eps * p
        nl = lin + c * eps ** 2 * u
        E = G.scaled_linearization_error(nl, lin, _ONES)
        ratios.append(E / eps)
    # E/epsilon is the O(1) coefficient c*||u||/||p|| = 1
    assert max(ratios) - min(ratios) < 1e-6
    assert abs(ratios[0] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# 2. Production-code guard: denominator is NOT the nonlinear increment
# ---------------------------------------------------------------------------
def test_production_uses_linear_prediction_denominator():
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "grazing.py").read_text(encoding="utf-8")
    # the protocol helper must be what _elin_probe uses
    assert "scaled_linearization_error" in src
    # the old nonlinear-increment denominator must be gone from _elin_probe
    assert "np.linalg.norm((Mp - M0) / svec)" not in src
    assert "np.linalg.norm((Mm - M0) / svec)" not in src


def test_epsilon_floor_is_numerical_guard_only():
    # G6R2 §4: floor is a 0/0 numerical guard, NOT a physics/validity
    # threshold; G6 threshold policy unchanged
    assert G6R2["epsilon_floor_role"] == (
        "numerical normalization guard only (0/0); NOT a grazing / "
        "validity / physics threshold; G6 threshold policy unchanged.")
    assert G6R2["epsilon_floor"] == 1e-15
    assert SNAP["threshold_decision"]["outcome"] == \
        "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED"


# ---------------------------------------------------------------------------
# 3. Snapshot G6R2 provenance + recomputed radii
# ---------------------------------------------------------------------------
def test_g6r2_block_schema():
    assert G6R2["schema_version"] == "phase-g6r2-linearization-normalization-v1"
    assert G6R2["error_normalization"] == "ERROR_OVER_LINEAR_PREDICTION"
    assert G6R2["old_error_normalization"] == "ERROR_OVER_NONLINEAR_INCREMENT"
    assert G6R2["paired_fd_results_unchanged"] is True
    assert G6R2["threshold_decision_reaudited"] is True
    assert G6R["linearization_error_denominator"] == \
        "canonical_scaled_linear_prediction_norm"
    # old G6R (nonlinear-denominator) values are preserved verbatim
    old = G6R2["old_radii_g6r_nonlinear_denominator"]
    assert set(old.keys()) == {"B0_a1", "B0_a0.5", "B3_a1", "B4_a1"}
    # previously-committed G6R refined values for B0 a1:
    assert old["B0_a1"]["r_1pct_refined"] == pytest.approx(0.0403744, abs=1e-4)
    assert old["B0_a1"]["r_5pct_refined"] == pytest.approx(0.193707, abs=1e-4)


def test_recomputed_radii_classification_and_range():
    rv = G6R["refined_validity_radii"]
    for key, rec in rv.items():
        assert rec["monotone_profile"] is True
        for tau in ("r_1pct_refined", "r_5pct_refined"):
            rr = rec[tau]
            assert rr["classification"] == "MONOTONE_REFINED_RADIUS"
            assert rr["lower_pass_beta"] < rr["refined_beta"] < (
                rr["upper_fail_beta"])
            assert rr["refined_radius_m"] == pytest.approx(
                rr["refined_beta"] * rec["phi_local_m"])
        assert 0.03 < rec["r_1pct_refined"]["radius_over_phi"] < 0.1
        assert 0.1 < rec["r_5pct_refined"]["radius_over_phi"] < 0.2


def test_protocol_correct_coefficients_scale_free():
    rv = G6R["refined_validity_radii"]
    r1 = [rec["r_1pct_refined"]["radius_over_phi"] for rec in rv.values()]
    r5 = [rec["r_5pct_refined"]["radius_over_phi"] for rec in rv.values()]
    assert max(r1) - min(r1) < 0.01
    assert max(r5) - min(r5) < 0.02
    # protocol-correct coefficients sit slightly BELOW the old G6R ones
    for key, rec in rv.items():
        old_r1 = G6R2["old_radii_g6r_nonlinear_denominator"][key][
            "r_1pct_refined"]
        old_r5 = G6R2["old_radii_g6r_nonlinear_denominator"][key][
            "r_5pct_refined"]
        assert rec["r_1pct_refined"]["radius_over_phi"] < old_r1
        assert rec["r_5pct_refined"]["radius_over_phi"] < old_r5


# ---------------------------------------------------------------------------
# 4. Real radius recomputation (live, non-self-fulfilling for one case)
# ---------------------------------------------------------------------------
def test_live_recompute_matches_protocol_snapshot(base):
    """Live recompute of B0 a=1 refined radius with the protocol-correct
    normalization must reproduce the committed snapshot coefficient."""
    env, veh = base
    from hyptraj.analysis.comparison_validation import (
        REFERENCE_05_SOLVER_CONFIG,
        REFERENCE_SOLVER_CONFIG,
    )
    from hyptraj.predictability.stm import stm_strict_reference_config
    anchors = G.load_frozen_grazing_anchors()
    cfg = stm_strict_reference_config()
    a = next(x for x in anchors if x.branch == "B0" and x.side == "N1_side")
    exc = G.extract_branch_excursion(a, env, veh, REFERENCE_SOLVER_CONFIG)
    rr = G.refined_operational_radius(
        exc.exit_state, env, veh, a.K, cfg, exc.vac_duration_s,
        float(exc.clearance_m), taus=(0.01, 0.05))
    snap = G6R["refined_validity_radii"]["B0_a1"]
    assert rr["radii"]["r_1pct"]["radius_over_phi"] == pytest.approx(
        snap["r_1pct_refined"]["radius_over_phi"], abs=1e-4)
    assert rr["radii"]["r_5pct"]["radius_over_phi"] == pytest.approx(
        snap["r_5pct_refined"]["radius_over_phi"], abs=1e-4)


# ---------------------------------------------------------------------------
# 5. Paired FD preservation (G6R2 §6)
# ---------------------------------------------------------------------------
def test_paired_fd_unchanged_in_snapshot():
    for br in ("B0", "B4"):
        pl = G6R["paired_fd"][br]["radial_plateau"]
        fc = G6R["paired_fd"][br]["four_column"]
        assert pl["plateau_pass"] is True
        assert fc["four_column_pass"] is True
        assert pl["max_scaled_rel_error"] < 1e-2


def test_frozen_g6_sections_untouched():
    # G6 coarse historical grid table + frozen G6 content stay verbatim
    assert "g6" not in SNAP  # no such key; history lives in validity_radii
    rv = SNAP["validity_radii"]["B0_a1"]
    assert rv["r_1pct_over_phi"] == 0.03  # frozen G6 grid sample preserved
    assert rv["r_5pct_over_phi"] == 0.1
