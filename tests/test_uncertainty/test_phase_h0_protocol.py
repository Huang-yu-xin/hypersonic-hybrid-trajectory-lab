"""Phase-H0 uncertainty / risk protocol semantic tests.

Fast, deterministic, STATEFUL against the committed protocol manifest
``tests/data/phase_h_uncertainty_protocol_v1.json``.  Following the
Phase-G0/G7 philosophy these tests do NOT depend on git tags at runtime
(the upstream commit/tag targets are frozen constants + the committed
manifest, while the live tag targets are verified by the H0 shell audit).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.uncertainty.protocol import (
    ALPHA_ROLE_NOTE,
    ALPHA_STATUS,
    CANONICAL_SCALE_KEY,
    DEFAULT_FAIR_HORIZON_S,
    FORBIDDEN_CLAIMS,
    G6R2_VALIDITY_RADIUS_OVER_PHI,
    H1_STARTED,
    MONTE_CARLO_PERFORMED,
    MONTE_CARLO_RNG_POLICY,
    NON_RANDOMIZED_QUANTITIES,
    NO_UNIVERSAL_NUMERIC_GRAZING_THRESHOLD_SUPPORTED,
    PAIRED_COMMON_RANDOM_NUMBERS,
    PHASE_F_COMMIT,
    PHASE_F_TAG,
    PHASE_G_COMMIT,
    PHASE_G_TAG,
    PRODUCTION_COVARIANCE_PROPAGATION_COMPUTED,
    RANDOMIZED_QUANTITIES,
    SCOPE_STATEMENT,
    SEQUENTIAL_SAMPLE_SIZES,
    STATE_ORDER_TUPLE,
    SYNTHETIC_FAMILY_LABEL,
    TOPOLOGY_PROBABILITY_COMPUTED,
    TOPOLOGY_TRANSITION_PROBABILITY_DEFINITION,
    CovarianceValidationResult,
    MixedComponent,
    RiskMetricKind,
    SampleClassification,
    StatisticalErrorCategory,
    UncertaintyDistributionKind,
    canonical_scale,
    covariance_principal_directions,
    covariance_rms_spread,
    covariance_sigma_max,
    linear_fixed_time_covariance,
    machine_readable_protocol,
    mixture_total_covariance,
    physical_to_scaled_covariance,
    representative_cases,
    scaled_linear_fixed_time_covariance,
    scaled_to_physical_covariance,
    synthetic_alpha_covariance,
    terminal_cross_covariance,
    terminal_state_covariance,
    terminal_time_variance,
    validate_covariance,
    wilson_interval,
)

REPO = Path(__file__).resolve().parent.parent.parent
DATA = REPO / "tests" / "data"
MANIFEST = json.loads((DATA / "phase_h_uncertainty_protocol_v1.json")
                      .read_text(encoding="utf-8"))

_RNG = np.random.default_rng(2026)


def _psd():
    """A generic full-rank symmetric PSD covariance."""
    A = _RNG.normal(size=(4, 4))
    return A @ A.T + 1e-6 * np.eye(4)


# ---------------------------------------------------------------------------
# 1. Upstream freeze (H0 §0, §57)
# ---------------------------------------------------------------------------
def test_upstream_phase_g_freeze_recorded_exactly():
    up = MANIFEST["upstream"]
    assert up["phase_g_commit"] == PHASE_G_COMMIT == (
        "6fb75c4a5f7b6460a5c9503c99fe2b2b2c96854c")
    # recorded commit is a full 40-hex SHA (no runtime git dependency)
    assert len(PHASE_G_COMMIT) == 40
    int(PHASE_G_COMMIT, 16)
    assert up["phase_g_tag"] == PHASE_G_TAG == "phase-g-v1.0"
    assert up["phase_f_commit"] == PHASE_F_COMMIT == (
        "96253f1ef7785764d8da3156d7d614d2b244b577")
    assert up["phase_f_tag"] == PHASE_F_TAG == "phase-f-v1.0"


def test_protocol_manifest_matches_code():
    """Single source of truth: the committed JSON == machine_readable_protocol()."""
    assert MANIFEST == machine_readable_protocol()


def test_schema_version_and_h0_flags():
    assert MANIFEST["protocol_version"] == "phase-h-uncertainty-risk-protocol-v1"
    assert MANIFEST["schema_version"] == "phase-h-uncertainty-risk-protocol-v1"
    assert MANIFEST["h0_status"]["phase_h0_done"] is False
    assert MANIFEST["h0_status"]["h1_started"] is False


# ---------------------------------------------------------------------------
# 2. State order (H0 §6)
# ---------------------------------------------------------------------------
def test_state_order_frozen():
    assert STATE_ORDER_TUPLE == ("r", "theta", "v", "gamma")
    assert list(MANIFEST["state_order"]) == list(STATE_ORDER_TUPLE)
    assert MANIFEST["state_units"] == {
        "r": "m", "theta": "rad", "v": "m/s", "gamma": "rad"}


# ---------------------------------------------------------------------------
# 3. Initial-state-only scope (H0 §7, §8)
# ---------------------------------------------------------------------------
def test_initial_state_only_random_scope():
    scope = MANIFEST["random_variable_scope"]
    assert scope["randomized"] == list(RANDOMIZED_QUANTITIES) == [
        "delta r_0", "delta theta_0", "delta v_0", "delta gamma_0"]
    # K / vehicle / atmosphere / Earth / control are frozen NON-random.
    assert "K" in NON_RANDOMIZED_QUANTITIES
    assert "mass" in NON_RANDOMIZED_QUANTITIES
    assert "atmospheric density" in NON_RANDOMIZED_QUANTITIES
    assert scope["phase_f_parameter_response_distinct"] is True


# ---------------------------------------------------------------------------
# 4. Covariance validation (H0 §9)
# ---------------------------------------------------------------------------
def test_covariance_symmetric_psd_accepted():
    P = _psd()
    res = validate_covariance(P)
    assert res.valid and res.status == "VALID_PSD"
    assert not res.reasons
    assert res.numerical_rank == 4


def test_covariance_correlated_psd_accepted():
    P = np.array([[4.0, 1.2, 0.0, 0.1],
                  [1.2, 9.0, -0.5, 0.4],
                  [0.0, -0.5, 16.0, 0.7],
                  [0.1, 0.4, 0.7, 25.0]])
    res = validate_covariance(P)
    assert res.valid and res.status == "VALID_PSD"


def test_covariance_rank_deficient_psd_accepted():
    v = np.array([1.0, 2.0, 3.0, 4.0])
    P = np.outer(v, v)                 # structural rank 1 (eig = 0)
    res = validate_covariance(P)
    assert res.valid and res.status == "VALID_PSD"
    assert res.numerical_rank == 1


def test_covariance_nonsymmetric_rejected():
    P = np.eye(4)
    P[0, 1] = 2.0
    res = validate_covariance(P)
    assert not res.valid
    assert res.status == "INVALID_COVARIANCE"
    assert "NON_SYMMETRIC" in res.reasons


def test_covariance_materially_negative_eigenvalue_rejected():
    P = np.diag([1.0, -5.0, 1.0, 1.0])
    res = validate_covariance(P)
    assert not res.valid
    assert "MATERIALLY_NON_PSD" in res.reasons


def test_covariance_roundoff_negative_eigenvalue_accepted():
    # A tiny negative eigenvalue inside the documented numerical tolerance
    # is roundoff, NOT a material non-PSD (no silent abs(eigenvalues)).
    P = np.diag([1.0, 1.0, 1.0, -1e-14])
    res = validate_covariance(P)
    assert res.valid and res.status == "VALID_PSD"


def test_covariance_nan_rejected():
    P = np.eye(4)
    P[2, 2] = np.nan
    res = validate_covariance(P)
    assert not res.valid and "NONFINITE_NaN" in res.reasons


def test_covariance_inf_rejected():
    P = np.eye(4)
    P[0, 0] = np.inf
    res = validate_covariance(P)
    assert not res.valid and "NONFINITE_Inf" in res.reasons


def test_covariance_wrong_shape_rejected():
    for bad in (np.eye(3), np.eye(5), np.zeros((4,)),
                np.eye(4).tolist() + [[0, 0, 0, 0]]):
        res = validate_covariance(bad)
        assert not res.valid and "WRONG_SHAPE" in res.reasons
    assert not validate_covariance("not a matrix").valid


# ---------------------------------------------------------------------------
# 5. Scaling conversion round trip (H0 §10)
# ---------------------------------------------------------------------------
def test_canonical_scale_frozen_candidate_a():
    assert CANONICAL_SCALE_KEY == "A"
    scales = canonical_scale()
    assert scales == {"r": 1e5, "theta": 1.0, "v": 7e3, "gamma": 0.1}
    assert MANIFEST["canonical_scale"]["status"] == \
        "CANONICAL_SCALE_NUMERIC_VALUES_FROZEN"


def test_scaling_round_trip_recovers_original():
    P = _psd()
    tilde = physical_to_scaled_covariance(P)
    back = scaled_to_physical_covariance(tilde)
    assert np.allclose(back, P, atol=1e-9)


def test_scaled_covariance_dimensionless():
    P = _psd()
    tilde = physical_to_scaled_covariance(P)
    # entries are O(1)-dimensionless under canonical A
    assert float(np.max(np.abs(tilde))) < 1e3


# ---------------------------------------------------------------------------
# 6. Covariance propagation algebra (H0 §16) -- synthetic matrices only
# ---------------------------------------------------------------------------
def test_linear_fixed_time_covariance_algebra():
    Phi = _RNG.normal(size=(4, 4))
    P0 = _psd()
    expect = Phi @ P0 @ Phi.T
    assert np.allclose(linear_fixed_time_covariance(Phi, P0), expect, atol=1e-10)


def test_scaled_linear_covariance_algebra_and_row_convention():
    Phi_t = _RNG.normal(size=(4, 4))
    P0_t = _psd()
    # rows = output component, columns = initial perturbation (Phase-G STM)
    expect = Phi_t @ P0_t @ Phi_t.T
    assert np.allclose(scaled_linear_fixed_time_covariance(Phi_t, P0_t),
                       expect, atol=1e-10)
    assert expect.shape == (4, 4)


# ---------------------------------------------------------------------------
# 7. Terminal algebra (H0 §19, §20) -- synthetic matrices only
# ---------------------------------------------------------------------------
def test_terminal_time_variance_algebra():
    eta = _RNG.normal(size=4)
    P0 = _psd()
    expect = float(eta @ P0 @ eta)
    got = terminal_time_variance(eta, P0)
    assert got >= 0.0
    assert np.isclose(got, expect, atol=1e-10)


def test_terminal_state_covariance_algebra():
    J = _RNG.normal(size=(4, 4))
    P0 = _psd()
    expect = J @ P0 @ J.T
    assert np.allclose(terminal_state_covariance(J, P0), expect, atol=1e-10)


def test_terminal_cross_covariance_algebra():
    J = _RNG.normal(size=(4, 4))
    P0 = _psd()
    eta = _RNG.normal(size=4)
    expect = J @ P0 @ eta
    got = terminal_cross_covariance(J, P0, eta)
    assert got.shape == (4,)
    assert np.allclose(got, expect, atol=1e-10)


# ---------------------------------------------------------------------------
# 8. Fixed-time uncertainty metrics (H0 §18) -- DESCRIPTIVE, not probability
# ---------------------------------------------------------------------------
def test_descriptive_metrics_consistency():
    P_t = _psd()
    sm = covariance_sigma_max(P_t)
    rms = covariance_rms_spread(P_t)
    assert sm > 0.0 and rms > 0.0
    directions = covariance_principal_directions(P_t)
    assert directions.shape == (4, 4)
    # sigma_max = sqrt(lambda_max(P)) must equal the eigen-decomposition
    evals_raw, evecs_raw = np.linalg.eigh(P_t)
    assert np.isclose(sm, np.sqrt(max(evals_raw)), atol=1e-8)
    # principal directions are the eigenvalue-ordered orthonormal basis
    order = np.argsort(evals_raw)[::-1]
    assert np.allclose(np.abs(directions.T @ evecs_raw[:, order]),
                       np.eye(4), atol=1e-8)


# ---------------------------------------------------------------------------
# 9. Topology probability semantics (H0 §24, §25, §32, §45)
# ---------------------------------------------------------------------------
def test_topology_probability_requires_explicit_distribution():
    assert TOPOLOGY_TRANSITION_PROBABILITY_DEFINITION
    assert "explicitly defined input distribution" in \
        TOPOLOGY_TRANSITION_PROBABILITY_DEFINITION
    # every sample-classification label is exposed
    labels = {s.value for s in SampleClassification}
    assert {"TOPOLOGY_PRESERVED", "TOPOLOGY_CHANGED", "EVENT_ORDER_CHANGED",
            "TERMINAL_KIND_CHANGED", "GRAZING_CROSSED",
            "LINEARIZATION_INVALID", "NONPHYSICAL_STATE",
            "NUMERICAL_FAILURE"} == labels


def test_no_universal_numeric_grazing_threshold():
    assert NO_UNIVERSAL_NUMERIC_GRAZING_THRESHOLD_SUPPORTED is True
    tv = MANIFEST["topology_random_variable"]
    assert tv["no_universal_threshold"] is True


def test_probability_not_inferred_from_diagnostics():
    # H0 §45: FTLE / sigma_max / |n^T f| / Phi_local / r_1% / r_5% /
    # topology distance / rho_lin / rho_topo are NOT probabilities.
    gv = MANIFEST["grazing_validity_inheritance"]
    assert "no frozen cutoff" in gv["rho_lin"]
    assert "not a probability" in gv["rho_topo"]
    assert "never" in gv["note"] and "risk thresholds" in gv["note"]
    # the forbidden-claims list pins each misreading
    assert "FTLE = probability" in FORBIDDEN_CLAIMS
    assert "sigma_max = risk probability" in FORBIDDEN_CLAIMS
    assert "distance to grazing = topology-change probability" in FORBIDDEN_CLAIMS
    assert "synthetic uncertainty = real-world calibrated uncertainty" in \
        FORBIDDEN_CLAIMS


# ---------------------------------------------------------------------------
# 10. Mixture law (H0 §26, §27)
# ---------------------------------------------------------------------------
def test_mixture_law_of_total_covariance():
    mu1 = np.array([1.0, 1.0, 1.0, 1.0])
    mu2 = -mu1
    Pk = np.eye(4)
    comps = [MixedComponent(0.5, mu1, Pk), MixedComponent(0.5, mu2, Pk)]
    mu, P = mixture_total_covariance(comps)
    assert np.allclose(mu, 0.0, atol=1e-12)
    # P = sum p_k [P_k + (mu_k - mu)(mu_k - mu)^T]
    expect = 0.5 * (Pk + np.outer(mu1, mu1)) + 0.5 * (Pk + np.outer(mu2, mu2))
    assert np.allclose(P, expect, atol=1e-12)


def test_mixture_incompatible_terminals_not_blindly_mixed():
    note = MANIFEST["mixture_semantics"]["incompatible_terminals"]
    assert "never blindly mixed" in note


# ---------------------------------------------------------------------------
# 11. Gaussian semantics (H0 §15, §22, §48)
# ---------------------------------------------------------------------------
def test_gaussian_not_physically_calibrated_by_default():
    kinds = {k.value for k in UncertaintyDistributionKind}
    assert kinds == {"GAUSSIAN", "BOUNDED_ELLIPSOIDAL",
                     "DETERMINISTIC_SIGMA_POINTS", "CUSTOM_SAMPLES"}
    # alpha is a synthetic research amplitude, never a physical calibration
    assert ALPHA_STATUS == "PENDING_NUMERICAL_AUDIT"
    assert "no real-world" in ALPHA_ROLE_NOTE
    assert MANIFEST["synthetic_distribution_family"]["alpha_status"] == \
        ALPHA_STATUS


def test_no_arbitrary_alpha_frozen_in_manifest():
    # the manifest must not pin a concrete numeric alpha magnitude anywhere
    text = json.dumps(MANIFEST, ensure_ascii=False)
    assert ALPHA_STATUS in text
    for _lvl in (0.01, 0.05, 0.10):      # example "physical probability" levels
        assert f'"alpha": {_lvl}' not in text
        assert f'"alpha":{_lvl}' not in text


# ---------------------------------------------------------------------------
# 12. Risk boundary (H0 §44, §1)
# ---------------------------------------------------------------------------
def test_risk_taxonomy_research_model_only():
    metrics = {r.value for r in RiskMetricKind}
    assert metrics == {"TOPOLOGY_TRANSITION_RISK",
                       "LINEARIZATION_BREAKDOWN_RISK",
                       "TERMINAL_KIND_CHANGE_RISK", "STATE_DISPERSION",
                       "TERMINAL_TIME_DISPERSION", "NUMERICAL_FAILURE_RATE"}
    note = MANIFEST["risk_taxonomy"]["scope_note"]
    assert "NOT vehicle survival" in note
    # interception / survival / optimization are NOT activated
    assert "interception geometry" in SCOPE_STATEMENT
    assert "survival / evasion" in SCOPE_STATEMENT
    rb = MANIFEST["risk_boundary"]
    assert "src/hyptraj/risk/interception_geometry.py" in \
        rb["inactive_placeholders"]
    assert "src/hyptraj/risk/survival.py" in rb["inactive_placeholders"]


# ---------------------------------------------------------------------------
# 13. Statistical error taxonomy (H0 §46)
# ---------------------------------------------------------------------------
def test_statistical_error_taxonomy():
    cats = {c.value for c in StatisticalErrorCategory}
    assert "VALID_FIXED_TOPOLOGY_SAMPLE" in cats
    assert "INVALID_COVARIANCE" in cats
    assert "INVALID_DISTRIBUTION" in cats
    assert "INSUFFICIENT_MONTE_CARLO_CONVERGENCE" in cats
    # the manifest carries the same vocabulary (order is semantic, not sorted)
    assert set(MANIFEST["statistical_error_taxonomy"]) == cats


# ---------------------------------------------------------------------------
# 14. Monte-Carlo future protocol (H0 §33-§38, §49, §50) -- rule freeze only
# ---------------------------------------------------------------------------
def test_monte_carlo_rng_policy():
    assert MONTE_CARLO_RNG_POLICY["generator"] == \
        "numpy.random.Generator (via numpy.random.default_rng)"
    assert MONTE_CARLO_RNG_POLICY["global_implicit_state"].startswith("FORBIDDEN")
    assert MANIFEST["monte_carlo_rng_policy"]["reproducibility_seed"] == 2026
    assert MANIFEST["monte_carlo_rng_policy"]["seed_role"] == \
        "REPRODUCIBILITY seed only; NOT a physical parameter"


def test_sequential_sample_count_policy():
    assert tuple(SEQUENTIAL_SAMPLE_SIZES) == (256, 512, 1024, 2048, 4096)
    assert MANIFEST["sample_count_convergence_policy"][
        "sequential_sizes"] == [256, 512, 1024, 2048, 4096]
    assert "sample_mean" in MANIFEST["sample_count_convergence_policy"][
        "convergence_metrics"]


def test_wilson_interval_behaviour():
    # not a normal approximation; endpoints clipped to [0,1]
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0.0 < hi < 1.0
    lo2, hi2 = wilson_interval(10, 10)
    assert hi2 == 1.0 and 0.0 < lo2 < 1.0
    assert MANIFEST["probability_ci_policy"]["method"] == \
        "binomial Wilson interval"


def test_paired_common_random_numbers_preferred():
    assert PAIRED_COMMON_RANDOM_NUMBERS is True
    assert MANIFEST["misc_protocol"]["paired_common_random_numbers"] is True


def test_nonphysical_sample_policy_no_silent_clip():
    note = MANIFEST["misc_protocol"]["nonphysical_sample_policy"]
    assert "never silently clipped" in note


# ---------------------------------------------------------------------------
# 15. Representative hierarchy (H0 §41, §42) -- reuse frozen cases only
# ---------------------------------------------------------------------------
def test_representative_cases_reuse_frozen_set():
    cases, anchors = representative_cases()
    keys = {c["key"] for c in cases}
    assert {"qian_baseline", "sanger_baseline", "n0_deep", "n5_deep"} <= keys
    assert len(anchors) == 10
    branches = {a["branch"] for a in anchors}
    assert branches == {"B0", "B1", "B2", "B3", "B4"}
    assert DEFAULT_FAIR_HORIZON_S == 600.0
    assert MANIFEST["fair_comparison_convention"][
        "default_horizon_s"] == 600.0


# ---------------------------------------------------------------------------
# 16. H0 no-production-computation guard (H0 §0, §52, §58)
# ---------------------------------------------------------------------------
def test_h1_not_started():
    assert H1_STARTED is False
    assert PRODUCTION_COVARIANCE_PROPAGATION_COMPUTED is False
    assert MONTE_CARLO_PERFORMED is False
    assert TOPOLOGY_PROBABILITY_COMPUTED is False
    status = MANIFEST["h0_status"]
    assert status["production_covariance_propagation_computed"] is False
    assert status["monte_carlo_performed"] is False
    assert status["topology_probability_computed"] is False


def test_production_engine_placeholders_not_started():
    """sampling.py / propagation.py must remain empty production placeholders."""
    sampling_src = (REPO / "src/hyptraj/uncertainty/sampling.py").read_text(
        encoding="utf-8")
    propagation_src = (REPO / "src/hyptraj/uncertainty/propagation.py").read_text(
        encoding="utf-8")
    combined = sampling_src + propagation_src
    # no Monte-Carlo runner / no real trajectory propagation / no RNG draw
    for marker in ("solve_ivp", "def sample", "def propagate", "default_rng",
                   "normal("):
        assert marker not in combined, marker
