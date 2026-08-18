"""Phase-H1 fixed-topology linear uncertainty tests.

Two layers:

1.  Pure-algebra tests (§50 A-I) over DETERMINISTIC synthetic matrices --
    no RNG in production; the few synthetic matrices below are written
    explicitly as fixed constants (H1 §58).
2.  Snapshot-authoritative frozen regressions (§51-55): the committed H1
    snapshot ``tests/data/phase_h1_linear_uncertainty_v1.json`` must
    reproduce the accepted Phase-G values read from
    ``tests/data/phase_g5_predictability_metrics_v1.json`` (G5 reference
    values are read from the G5 snapshot, not from the task prompt).

Alpha is SYMBOLIC throughout: every production quantity is a per-alpha
response coefficient; no scientific alpha magnitude is chosen or frozen.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.uncertainty.propagation import (
    covariance_spectrum,
    fixed_time_alpha_kernel,
    physical_covariance_coefficient,
    physical_marginal_std_per_alpha,
    require_correlation_matrix,
    terminal_alpha_kernels,
    terminal_time_std_per_alpha,
)
from hyptraj.uncertainty.protocol import canonical_scale_matrix

REPO = Path(__file__).resolve().parent.parent.parent
DATA = REPO / "tests" / "data"
H1 = json.loads((DATA / "phase_h1_linear_uncertainty_v1.json").read_text(
    encoding="utf-8"))
G5 = json.loads((DATA / "phase_g5_predictability_metrics_v1.json").read_text(
    encoding="utf-8"))
G4 = json.loads((DATA / "phase_g4_hybrid_stm_v1.json").read_text(
    encoding="utf-8"))

S = canonical_scale_matrix()
E = np.eye(4)

# DETERMINISTIC synthetic fixtures (H1 §58: fixed matrices, no RNG).
PHI_FULL = np.array([
    [1.2, 0.3, -0.4, 0.1],
    [0.0, 0.9, 0.2, -0.3],
    [0.5, -0.1, 1.4, 0.2],
    [0.0, 0.2, 0.0, 0.7],
])
# structural rank 3 (zero bottom row = one output direction projected out).
PHI_RANK3 = np.array([
    [1.0, 0.2, -0.3, 0.1],
    [0.0, 1.0, 0.4, -0.2],
    [0.5, -0.1, 1.0, 0.3],
    [0.0, 0.0, 0.0, 0.0],
])
ETA_SYN = np.array([0.5, -0.2, 0.3, 0.1])
J_SYN = np.array([
    [0.8, 0.1, -0.2, 0.4],
    [0.0, 1.1, 0.3, -0.1],
    [0.2, -0.3, 0.9, 0.0],
    [0.0, 0.0, 0.0, 0.0],
])
R_CORR = np.array([
    [1.0, 0.3, 0.0, 0.1],
    [0.3, 1.0, -0.2, 0.0],
    [0.0, -0.2, 1.0, 0.4],
    [0.1, 0.0, 0.4, 1.0],
])


def _sym(K: np.ndarray) -> np.ndarray:
    return 0.5 * (K + K.T)


# ---------------------------------------------------------------------------
# A. Kernel algebra (H1 §50-A)
# ---------------------------------------------------------------------------
def test_kernel_algebra():
    K = fixed_time_alpha_kernel(PHI_FULL, R_CORR)
    assert K.shape == (4, 4)
    assert np.allclose(K, PHI_FULL @ R_CORR @ PHI_FULL.T, atol=1e-12)
    assert np.allclose(K, _sym(K), atol=1e-12)


def test_canonical_identity_kernel():
    K = fixed_time_alpha_kernel(PHI_FULL)
    assert np.allclose(K, PHI_FULL @ PHI_FULL.T, atol=1e-12)


# ---------------------------------------------------------------------------
# B. Alpha scaling law (H1 §50-B) -- pure algebra, no scientific alpha chosen
# ---------------------------------------------------------------------------
def test_alpha_scaling_law():
    a1, a2 = 0.3, 0.7
    K = fixed_time_alpha_kernel(PHI_FULL)
    P1 = (a1 ** 2) * K
    P2 = (a2 ** 2) * K
    # P(a2) = (a2/a1)^2 P(a1)
    assert np.allclose(P2, (a2 / a1) ** 2 * P1, atol=1e-12)
    # sigma(a2) = (a2/a1) sigma(a1)  (for any linear spread measure)
    for f in (np.trace,):
        assert np.isclose(np.sqrt(abs(f(P2))), (a2 / a1) * np.sqrt(abs(f(P1))))


# ---------------------------------------------------------------------------
# C. R=I singular-value identity  (H1 §50-C, §14)
# ---------------------------------------------------------------------------
def test_sqrt_eigenvalues_equal_singular_values():
    K = fixed_time_alpha_kernel(PHI_FULL)
    ev = np.sort(np.linalg.eigvalsh(_sym(K)))            # ascending
    sv = np.sort(np.linalg.svd(PHI_FULL, compute_uv=False))   # ascending
    assert np.allclose(np.sqrt(ev), sv, atol=1e-10)


# ---------------------------------------------------------------------------
# D. Rank-deficient identity (H1 §50-D, §17): rank-3 -> kernel rank 3,
#    tiny negative eigenvalues handled as roundoff-zero, NO abs repair.
# ---------------------------------------------------------------------------
def test_rank_deficient_kernel_rank_and_classification():
    K = fixed_time_alpha_kernel(PHI_RANK3)
    spec = covariance_spectrum(K)
    assert spec.numerical_rank == 3
    assert spec.nullity == 1
    # raw eigenvalues preserved; the structurally-zero direction is either
    # ZERO or NUMERIC_ZERO (a tiny positive/negative roundoff), never a
    # material negative (which would raise).
    assert "MATERIAL_NEGATIVE" not in spec.eigenvalue_classification
    # no abs() repair was applied: raw eigenvalues are exactly what the
    # eigendecomposition returned (recompute and compare)
    lam = np.sort(np.linalg.eigvalsh(_sym(K)))[::-1]
    assert np.allclose(spec.raw_eigenvalues, lam, atol=1e-12)
    assert spec.eigenvalue_classification[-1] in ("ZERO", "NUMERIC_ZERO",
                                                  "ROUND_OFF_ZERO")


def test_material_negative_kernel_is_failure():
    # bypass the guards: feed an indefinite matrix directly (a covariance
    # that A A^T could never produce) -> covariance_spectrum must raise.
    bad = np.diag([1.0, 1.0, 1.0, -1.0])
    try:
        covariance_spectrum(bad)
    except ValueError as e:
        assert "H1 FAIL" in str(e)
    else:
        raise AssertionError("material negative eigenvalue must raise")


# ---------------------------------------------------------------------------
# E. Principal output direction = G5 left singular vector up to sign (H1 §50-E, §15)
# ---------------------------------------------------------------------------
def test_principal_direction_equals_left_singular_vector():
    K = fixed_time_alpha_kernel(PHI_FULL)
    u1_K = np.linalg.eigh(_sym(K))[1][:, -1]
    U = np.linalg.svd(PHI_FULL, compute_uv=True)[0]
    assert abs(u1_K @ U[:, 0]) > 1 - 1e-9


# ---------------------------------------------------------------------------
# F. Physical marginal std (H1 §50-F, §18): sigma_xi/alpha = s_i sqrt(K_ii)
# ---------------------------------------------------------------------------
def test_physical_marginal_std_per_alpha():
    K = fixed_time_alpha_kernel(PHI_FULL)
    margins = physical_marginal_std_per_alpha(K)
    for i, key in enumerate(("r", "theta", "v", "gamma")):
        si = {"r": 1e5, "theta": 1.0, "v": 7e3, "gamma": 0.1}[key]
        expect = si * np.sqrt(float(K[i, i]))
        assert np.isclose(margins[i], expect, rtol=1e-12)


def test_physical_covariance_coefficient_convention():
    K = fixed_time_alpha_kernel(PHI_FULL)
    Pcoef = physical_covariance_coefficient(K)
    assert np.allclose(Pcoef, S @ K @ S.T, atol=1e-9)


# ---------------------------------------------------------------------------
# G. Terminal-time identity (H1 §50-G, §27): sigma_t/alpha = ||eta S_A||_2
# ---------------------------------------------------------------------------
def test_terminal_time_std_per_alpha_identity():
    eta_scaled = ETA_SYN @ S
    t_std = terminal_time_std_per_alpha(eta_scaled)
    assert np.isclose(t_std, np.linalg.norm(eta_scaled), rtol=1e-12)


# ---------------------------------------------------------------------------
# H. Terminal-state identity (H1 §50-H, §29): K_T = Jb Jb^T,
#    sigma_max,T/alpha = sigma_max(tilde J)
# ---------------------------------------------------------------------------
def test_terminal_state_kernel_identity():
    Jb = np.linalg.inv(S) @ J_SYN @ S
    K_T, _, _ = terminal_alpha_kernels(Jb, ETA_SYN @ S)
    assert np.allclose(K_T, Jb @ Jb.T, atol=1e-12)
    smax = np.sqrt(np.max(np.linalg.eigvalsh(_sym(K_T))))
    assert np.isclose(smax, np.max(np.linalg.svd(Jb, compute_uv=False)),
                      rtol=1e-10)


# ---------------------------------------------------------------------------
# I. Cross covariance (H1 §50-I, §31): c_zt/alpha^2 = Jb R (eta S)^T, shape (4,)
# ---------------------------------------------------------------------------
def test_terminal_cross_covariance_identity():
    Jb = np.linalg.inv(S) @ J_SYN @ S
    etab = ETA_SYN @ S
    _, _, cross = terminal_alpha_kernels(Jb, etab, R_CORR)
    assert cross.shape == (4,)
    assert np.allclose(cross, Jb @ R_CORR @ etab, atol=1e-12)


# ---------------------------------------------------------------------------
# Input guards (H1 §41, §42)
# ---------------------------------------------------------------------------
def test_input_guards():
    with pytest.raises(ValueError):
        fixed_time_alpha_kernel(np.eye(3))
    with pytest.raises(ValueError):
        fixed_time_alpha_kernel(np.eye(4) * np.nan)
    with pytest.raises(ValueError):
        require_correlation_matrix(np.diag([1.0, 1.0, 1.0, -1.0]))
    with pytest.raises(ValueError):
        require_correlation_matrix(np.diag([1.0, 2.0, 1.0, 1.0]),
                                   require_correlation=True)
    # proper correlation matrix passes
    require_correlation_matrix(R_CORR, require_correlation=True)


# ---------------------------------------------------------------------------
# Snapshot consistency: H1 snapshot derives from the accepted G4 artifacts
# ---------------------------------------------------------------------------
def test_snapshot_kernel_derives_from_g4():
    phi = np.array(G4["endpoints"]["qian_T600"]["phi_ref_01"], dtype=float)
    K_recomputed = fixed_time_alpha_kernel(np.linalg.inv(S) @ phi @ S)
    K_snapshot = np.array(H1["fixed_time"]["qian_T600"]["kernel_ref_01"])
    assert np.allclose(K_snapshot, K_recomputed, atol=1e-12)


# ---------------------------------------------------------------------------
# Frozen regressions vs the accepted G5 snapshot (§51-55).  Reference values
# are read from G5 (never the task prompt approximations).
# ---------------------------------------------------------------------------
def _assert_fixed_time_snapshot_matches_g5(case_key, model, horizon_key):
    c = H1["fixed_time"][case_key]
    g5ft = G5["fixed_time_canonical"][model][horizon_key]
    assert c["rank"] == g5ft["numerical_rank"], case_key
    assert c["nullity"] == g5ft["nullity"], case_key
    assert abs(c["sigma_max_per_alpha"] - g5ft["sigma_max"]) < 1e-6, case_key
    assert c["G5_sigma_closure"] == "PASS", case_key
    u1 = np.array(c["principal_directions"])[:, 0]
    g5u1 = np.array(g5ft["u1_scaled"], dtype=float)
    assert abs(u1 @ g5u1) > 1 - 1e-6, case_key          # up to sign
    # REF-0.1 vs REF-0.05 reference stability
    ref = c["reference_kernel_error"]
    assert ref["principal_direction_alignment"] > 1 - 1e-9, case_key
    assert ref["rank_01"] == ref["rank_05"] == c["rank"], case_key
    assert c["reference_stability_status"] == "PASS", case_key


def test_frozen_qian_t600_regression():     # H1 §51
    _assert_fixed_time_snapshot_matches_g5("qian_T600", "qian", "T600")
    c = H1["fixed_time"]["qian_T600"]
    # Qian structural rank loss inherited from Capture (H1 §16).
    assert c["rank"] == 3 and c["nullity"] == 1
    assert np.isclose(c["sigma_max_per_alpha"], 1.608209766, atol=1e-6)
    # correlation coefficient in gamma should be numerically zero (row-projected)
    assert abs(c["physical_marginal_std_per_alpha"]["gamma"]) < 1e-9


def test_frozen_sanger_t600_regression():   # H1 §52
    _assert_fixed_time_snapshot_matches_g5("sanger_T600", "sanger", "T600")
    c = H1["fixed_time"]["sanger_T600"]
    assert c["rank"] == 4 and c["nullity"] == 0
    assert np.isclose(c["sigma_max_per_alpha"], 85.87155237, atol=1e-6)


def test_frozen_sanger_t900_regression():   # H1 §53 (descriptive stress case)
    c = H1["fixed_time"]["sanger_T900"]
    assert c["descriptive_stress_case"] is True
    assert c["fair_cross_model_comparison"] is False
    _assert_fixed_time_snapshot_matches_g5("sanger_T900", "sanger", "T900")
    assert c["rank"] == 4 and c["nullity"] == 0
    assert np.isclose(c["sigma_max_per_alpha"], 22.09059150, atol=1e-6)


def _assert_terminal_snapshot_matches_g5(case_key, model, expected_kind):
    c = H1["terminal"][case_key]
    t = G5["terminal"][model]
    assert c["terminal_kind"] == expected_kind, case_key
    assert c["rank"] == t["rank"], case_key
    assert c["nullity"] == t["nullity"], case_key
    assert c["rank_matches_g5"] is True, case_key
    # tolerance 2e-5 s absorbs the G5 snapshot quantization of eta to ~8
    # significant digits (recomputed |eta S_A| vs the stored full-precision
    # norm differ at the ~1e-5 level); relative closure ~1e-8.
    assert abs(c["terminal_time_std_per_alpha"]
               - t["scaled_event_time_norm_seconds"]) < 2e-5, case_key
    assert c["G5_eta_closure"] == "PASS", case_key
    assert abs(c["terminal_sigma_max_per_alpha"]
               - t["scaled_sigma_max"]) < 1e-6, case_key
    assert c["G5_terminal_sigma_closure"] == "PASS", case_key
    assert c["reference_status"] == "PASS", case_key


def test_frozen_qian_terminal_regression(): # H1 §54 (RTI)
    _assert_terminal_snapshot_matches_g5("qian_RTI", "qian", "RTI")
    c = H1["terminal"]["qian_RTI"]
    # inherited structural rank loss of the terminal map (H1 §30)
    assert c["rank"] == 2 and c["nullity"] == 2
    assert np.isclose(c["terminal_time_std_per_alpha"], 1093.301727, atol=1e-4)


def test_frozen_sanger_terminal_regression():  # H1 §55 (SRTI)
    _assert_terminal_snapshot_matches_g5("sanger_SRTI", "sanger", "srti")
    c = H1["terminal"]["sanger_SRTI"]
    assert c["rank"] == 3 and c["nullity"] == 1
    assert np.isclose(c["terminal_time_std_per_alpha"], 3308.568119, atol=1e-4)


# ---------------------------------------------------------------------------
# Native-terminal warning (H1 §35) + claim boundaries (§49) in the snapshot
# ---------------------------------------------------------------------------
def test_native_terminal_not_fair_cross_model_ranking():
    assert H1["claim_boundaries"]["native_terminal_not_fair_cross_model_ranking"]
    assert H1["claim_boundaries"]["first_order_only"]
    assert H1["claim_boundaries"]["fixed_topology_conditioned"]
    assert H1["claim_boundaries"]["alpha_numeric_not_frozen"]
    assert H1["claim_boundaries"]["monte_carlo_not_performed"]
    assert H1["claim_boundaries"]["topology_probability_not_computed"]


def test_alpha_status_symbolic_in_snapshot():
    assert H1["alpha_status"] == "PENDING_NUMERICAL_AUDIT"
    assert H1["reporting_normalization"] == "PER_ALPHA_RESPONSE_COEFFICIENTS"
    assert H1["h2_handoff"]["alpha_not_chosen_at_h1"] is True
    # no frozen scientific alpha magnitude anywhere (only per-alpha response
    # coefficients and the symbolic family string "alpha^2" appear)
    for word in ("alpha", "per_alpha"):
        positions = json.dumps(H1).count(word)
        assert positions > 0
    assert '"alpha": 0.' not in json.dumps(H1)


# ---------------------------------------------------------------------------
# No-RNG guard on the H1 production modules / generator (H1 §58, §57)
# ---------------------------------------------------------------------------
def test_production_modules_have_no_rng():
    src = (REPO / "src/hyptraj/uncertainty/propagation.py").read_text(
        encoding="utf-8")
    gen = (REPO / "scripts/run_phase_h1_linear_uncertainty.py").read_text(
        encoding="utf-8")
    combined = src + gen
    for marker in ("np.random", "default_rng", "multivariate_normal"):
        assert marker not in combined, marker
    # propagation.py never integrates a trajectory: no ODE-solver import
    # / call (the word may appear in the docstring as a prohibition, so
    # assert on code usage, not any substring).
    for marker in ("from scipy", "import scipy", "solve_ivp("):
        assert marker not in src, marker


def test_no_topology_probability_in_snapshot():
    # H1 makes no P(topology preserved) claim (H1 §37): the only
    # "topology_probability*" fields are the claim boundary flags.
    assert H1["claim_boundaries"]["topology_probability_not_computed"] is True
    assert H1["claim_boundaries"]["monte_carlo_not_performed"] is True
    for case in H1["fixed_time"].values():
        assert "topology_probability" not in case, case["model"]
    for case in H1["terminal"].values():
        assert "topology_probability" not in case, case["model"]
