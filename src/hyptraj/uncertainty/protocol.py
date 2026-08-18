"""Phase-H0 uncertainty / risk protocol freeze (H0 -- metadata/convention).

MACHINE-READABLE SINGLE SOURCE OF TRUTH for the Phase-H topology-aware
uncertainty & risk protocol  (``docs/phase_h/h0_uncertainty_risk_protocol.md``
is the human-readable companion).  H0 freezes SEMANTICS and CONVENTIONS
ONLY -- exactly as Phase-G0 did for predictability:

* the random-variable convention ``X0 = xbar0 + delta X0`` with
  ``E[delta X0] = 0`` and ``P0 = Cov[delta X0]`` (mean / covariance /
  full-distribution kept distinct: same covariance != same law);
* initial-state-only random-variable scope (``delta r0, delta theta0,
  delta v0, delta gamma0``); K / vehicle / atmosphere / Earth / control
  remain NON-random in H1-style studies;
* the covariance validity contract (shape (4,4), finite, symmetric,
  positive-semidefinite; explicit numerical tolerance; NO silent
  ``abs(eigenvalues)`` repair);
* the canonical-A covariance normalization (``Z0 = S_A^-1 delta X0``,
  ``tilde P = S_A^-1 P S_A^-T``) inherited from frozen Phase G;
* the synthetic research uncertainty family ``Z0 ~ N(0, alpha^2 R)``
  with ``R = I`` canonical and ``alpha`` status PENDING_NUMERICAL_AUDIT;
* the frozen linear uncertainty formulas (fixed-time covariance,
  terminal-time variance, terminal-state covariance, cross covariance);
* the topology random variable ``Z = T(X0)`` and transition probability
  ``p_topo = P(Z != Z0)`` (never inferred from distance / FTLE /
  ``|n^T f|`` / ``Phi_local``);
* mixture semantics (``p_k, mu_k, P_k`` and the law of total covariance);
* grazing validity inheritance (G6R2 radius ratios) as linearization
  validity diagnostics -- NEVER probability thresholds;
* the Monte-Carlo RNG / sequential sample-count / Wilson-interval /
  common-random-numbers / nonphysical-sample protocols (RULE freeze only);
* the statistical-error and sample-classification taxonomies;
* risk taxonomy (statistical research-model risks ONLY; no interception /
  survival / optimization);
* claim boundaries and H0 status flags.

Hard boundaries honoured by this module (H0 §0): NO Monte-Carlo run, NO
production covariance propagation, NO topology probability, NO uncertainty
maps, NO gamma0-K re-scan, NO optimization, NO new physics / atmosphere /
aerodynamics / trajectories, NO new Phase-G STM / saltation / grazing work.
The only arithmetic below implements the frozen CONVENTION *formulas* as
pure algebra on caller-supplied matrices (so the H0 semantic tests reason
about the documented convention instead of drifting to local notation) --
none of it integrates a trajectory or touches a real Phase-G derivative.

Consumption rule: Phase H consumes the frozen Phase-G derivatives; it does
NOT redefine them.  Frozen state ordering / canonical scale / numerical
rank policy / representative cases are imported from the Phase-G metadata
modules rather than copied.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

import numpy as np

from hyptraj.predictability.event_metadata import STATE_ORDER
from hyptraj.predictability.protocol import (
    GRAZING_ANCHOR_PARAMETERS,
    REPRESENTATIVE_CASES,
)
from hyptraj.predictability.scaling import (
    CANONICAL_SCALE_NUMERIC_VALUES_FROZEN,
    PREFERRED_CANONICAL_CANDIDATE,
    canonical_candidate,
)

# ---------------------------------------------------------------------------
# Status flags (H0 §0, §58) -- production engines are NOT started in H0/H0R.
# ---------------------------------------------------------------------------
# H0 was accepted by human review and locked by the H0R lifecycle patch:
# the protocol freeze is COMPLETE / ACCEPTED (phase_h0_done = true), while
# H1 and every production engine remain NOT started (all flags false).
PHASE_H0_DONE = True
H1_STARTED = False
PRODUCTION_COVARIANCE_PROPAGATION_COMPUTED = False
MONTE_CARLO_PERFORMED = False
TOPOLOGY_PROBABILITY_COMPUTED = False
UNCERTAINTY_MAP_GENERATED = False
GAMMA0_K_RE_SCANNED = False
OPTIMIZATION_PERFORMED = False

# ---------------------------------------------------------------------------
# Upstream frozen provenance (H0 §0; §57 upstream-freeze test)
# ---------------------------------------------------------------------------
PHASE_G_TAG = "phase-g-v1.0"
PHASE_G_COMMIT = "6fb75c4a5f7b6460a5c9503c99fe2b2b2c96854c"
PREDICTABILITY_TAG = "predictability-v1.0"
PHASE_F_TAG = "phase-f-v1.0"
PHASE_F_COMMIT = "96253f1ef7785764d8da3156d7d614d2b244b577"
GAMMA_K_SENSITIVITY_TAG = "gamma-k-sensitivity-v1.0"

# ---------------------------------------------------------------------------
# Frozen state convention (H0 §6, §54) -- consumed from Phase-G metadata.
# ---------------------------------------------------------------------------
STATE_DIM = 4
#: Frozen Phase-G implementation state ordering ``[r, theta, v, gamma]``
#: (m, rad, m/s, rad).  Never to be re-ordered by Phase-H notation.
STATE_ORDER_TUPLE: tuple[str, ...] = tuple(STATE_ORDER)
assert STATE_ORDER_TUPLE == ("r", "theta", "v", "gamma")
STATE_UNITS: Mapping[str, str] = {
    "r": "m", "theta": "rad", "v": "m/s", "gamma": "rad",
}
STATE_IDX_R, STATE_IDX_THETA, STATE_IDX_V, STATE_IDX_GAMMA = 0, 1, 2, 3

# ---------------------------------------------------------------------------
# Random-variable convention (H0 §6, §7)
# ---------------------------------------------------------------------------
# X0 = xbar0 + delta X0,  E[delta X0] = 0,  P0 = Cov[delta X0].
# The notation ``X0 ~ (xbar0, P0)`` does NOT require Gaussianness:
# mean / covariance / full distribution are kept distinct.
RANDOM_VARIABLE_NOTE = (
    "X0 = xbar0 + delta X0 with E[delta X0] = 0 and P0 = Cov[delta X0]. "
    "X0 ~ (xbar0, P0) does NOT imply Gaussian; the same covariance does "
    "not determine the probability distribution."
)
RANDOMIZED_QUANTITIES: tuple[str, ...] = (
    "delta r_0", "delta theta_0", "delta v_0", "delta gamma_0",
)
NON_RANDOMIZED_QUANTITIES: tuple[str, ...] = (
    "K", "mass", "C_D", "reference area", "atmospheric density",
    "scale height", "Earth parameters", "control law",
)
RANDOMIZATION_SCOPE = "initial-state-only"
# Phase-F sensitivity is a PARAMETER-space response d y / d gamma0 over the
# gamma0-K domain; Phase-H delta Gamma_0 is a RANDOM INITIAL-STATE
# component around one nominal.  They must never be conflated (H0 §8).
PHASE_F_PARAMETER_RESPONSE_DISTINCT_FROM_PHASE_H_RANDOM_STATE = True

# ---------------------------------------------------------------------------
# Canonical scaling (H0 §10, §11) -- inherited from frozen Phase-G (Candidate A)
# ---------------------------------------------------------------------------
CANONICAL_SCALE_KEY = PREFERRED_CANONICAL_CANDIDATE
CANONICAL_SCALE_STATUS = CANONICAL_SCALE_NUMERIC_VALUES_FROZEN


def canonical_scale() -> Mapping[str, float]:
    """Frozen canonical-A scale dict ``{r, theta, v, gamma}`` (H0 §10)."""
    return dict(canonical_candidate().scales)


def canonical_scale_matrix() -> np.ndarray:
    """Diagonal canonical-A matrix ``S_A = diag(1e5, 1, 7e3, 0.1)``."""
    return np.asarray(canonical_candidate().matrix, dtype=float)


# Z0 = S_A^-1 delta X0 and tilde P = S_A^-1 P S_A^-T (H0 §10).
SCALED_STATE_NOTE = "Z0 = S_A^-1 delta X0  (dimensionless perturbation)"
SCALED_COVARIANCE_NOTE = "tilde P = S_A^-1 P S_A^-T  (dimensionless covariance)"

# ---------------------------------------------------------------------------
# Distribution kinds (H0 §15) -- Gaussian is NOT the only allowed law.
# ---------------------------------------------------------------------------
class UncertaintyDistributionKind(Enum):
    """Frozen distribution-kind vocabulary (H0 §15).

    ``GAUSSIAN``, ``BOUNDED_ELLIPSOIDAL``, ``DETERMINISTIC_SIGMA_POINTS``
    and ``CUSTOM_SAMPLES`` are all permitted first-order families; whether
    H1/H2 implement every kind is a later decision.  H0 does not write the
    Gaussian assumption as a physical law.
    """

    GAUSSIAN = "GAUSSIAN"
    BOUNDED_ELLIPSOIDAL = "BOUNDED_ELLIPSOIDAL"
    DETERMINISTIC_SIGMA_POINTS = "DETERMINISTIC_SIGMA_POINTS"
    CUSTOM_SAMPLES = "CUSTOM_SAMPLES"


# ---------------------------------------------------------------------------
# Synthetic research family (H0 §12-§14)
# ---------------------------------------------------------------------------
# Z0 ~ N(0, alpha^2 R),  P0 = S_A (alpha^2 R) S_A^T,  R = I canonical.
SYNTHETIC_FAMILY_LABEL = "Z0 ~ N(0, alpha^2 R)"
CANONICAL_CORRELATION_MATRIX = "R = I  (canonical-A dimensionless geometry)"
# alpha is a SYNTHETIC dimensionless research amplitude -- NOT a real
# sensor accuracy / manufacturing tolerance / flight dispersion / world
# probability calibration (H0 §13).  Numeric alpha levels are DEFERRED to
# the H1/H2 pilot convergence / validity audit.
ALPHA_STATUS = "PENDING_NUMERICAL_AUDIT"
ALPHA_ROLE_NOTE = (
    "alpha = synthetic dimensionless research uncertainty amplitude only; "
    "no real-world magnitude or probability calibration is frozen at H0."
)

# ---------------------------------------------------------------------------
# Covariance validity contract (H0 §9)
# ---------------------------------------------------------------------------
# P0 must be (4,4), finite, symmetric, positive-semidefinite.  A tiny
# negative eigenvalue caused by roundoff is permitted under an explicit
# numerical tolerance; silently applying abs(eigenvalues) or arbitrarily
# "fixing" a covariance is FORBIDDEN.  A materially non-PSD input is
# INVALID_COVARIANCE.
COVARIANCE_SHAPE = (4, 4)
COVARIANCE_SYMMETRY_REL_TOL = 1e-8      # relative to max |entry|
COVARIANCE_PSD_REL_TOL = 1e-10          # relative to max eigenvalue
COVARIANCE_PSD_ABS_TOL = 1e-12          # absolute floor for near-zero lambda


@dataclass(frozen=True)
class CovarianceValidationResult:
    """Outcome of :func:`validate_covariance` (H0 §9)."""

    valid: bool
    status: str                 # "VALID_PSD" | "INVALID_COVARIANCE"
    min_eigenvalue: float
    max_eigenvalue: float
    numerical_rank: int         # frozen SVD-style rank (G5 §16)
    symmetry_residual: float
    reasons: tuple[str, ...]    # non-empty iff invalid


def _invalid_covariance(
    *reasons: str,
    min_eig: float = float("nan"),
    max_eig: float = float("nan"),
    rank: int = 0,
    sym_resid: float = float("nan"),
) -> CovarianceValidationResult:
    return CovarianceValidationResult(
        valid=False, status="INVALID_COVARIANCE",
        min_eigenvalue=min_eig, max_eigenvalue=max_eig,
        numerical_rank=rank, symmetry_residual=sym_resid,
        reasons=tuple(reasons),
    )


def validate_covariance(
    covariance,
    *,
    symmetry_rel_tol: float = COVARIANCE_SYMMETRY_REL_TOL,
    psd_rel_tol: float = COVARIANCE_PSD_REL_TOL,
    psd_abs_tol: float = COVARIANCE_PSD_ABS_TOL,
) -> CovarianceValidationResult:
    """Frozen covariance validity check (H0 §9).

    Accepts a (4,4) finite, symmetric, positive-semidefinite matrix.  A
    tiny negative eigenvalue within ``max(psd_abs_tol, psd_rel_tol *
    lambda_max)`` is treated as roundoff and accepted; everything outside
    the tolerance is ``INVALID_COVARIANCE``.  Absorbing the eigenvalue
    spectrum is never performed.
    """
    try:
        P = np.asarray(covariance, dtype=float)
    except (TypeError, ValueError):
        return _invalid_covariance("NOT_A_MATRIX")
    if P.ndim != 2 or P.shape != COVARIANCE_SHAPE:
        return _invalid_covariance("WRONG_SHAPE")
    if not np.all(np.isfinite(P)):
        if bool(np.isnan(P).any()):
            return _invalid_covariance("NONFINITE_NaN")
        return _invalid_covariance("NONFINITE_Inf")
    max_abs = float(np.max(np.abs(P))) if P.size else 0.0
    sym_resid = float(np.max(np.abs(P - P.T)))
    if sym_resid > symmetry_rel_tol * max_abs:
        return _invalid_covariance("NON_SYMMETRIC", sym_resid=sym_resid)
    eigvals = np.linalg.eigvalsh(0.5 * (P + P.T))
    lam_max = float(np.max(eigvals)) if eigvals.size else 0.0
    lam_min = float(np.min(eigvals)) if eigvals.size else 0.0
    neg_tol = max(float(psd_abs_tol), float(psd_rel_tol) * lam_max)
    if lam_min < -neg_tol:
        return _invalid_covariance(
            "MATERIALLY_NON_PSD", min_eig=lam_min, max_eig=lam_max,
            sym_resid=sym_resid)
    # Frozen numerical-rank convention (Phase-G G5 §16): count eigenvalue
    # magnitudes above sigma_max * max(m, n) * eps (for a symmetric PSD
    # matrix the sorted eigenvalues play the role of the singular values).
    rank_tol = lam_max * STATE_DIM * np.finfo(float).eps
    rank = int(np.count_nonzero(eigvals > rank_tol))
    return CovarianceValidationResult(
        valid=True, status="VALID_PSD",
        min_eigenvalue=lam_min, max_eigenvalue=lam_max,
        numerical_rank=rank, symmetry_residual=sym_resid, reasons=(),
    )


# ---------------------------------------------------------------------------
# Scaling conversion (H0 §10) -- pure algebra on caller-supplied matrices
# ---------------------------------------------------------------------------
def _scale_matrix(scales: Mapping[str, float] | None) -> np.ndarray:
    """Diagonal scale matrix from a ``{r, theta, v, gamma}`` mapping, or the
    frozen canonical-A matrix when no explicit scales are supplied."""
    if scales is None:
        return canonical_scale_matrix()
    return np.diag([float(scales[k]) for k in ("r", "theta", "v", "gamma")])


def physical_to_scaled_covariance(
    covariance,
    scales: Mapping[str, float] | None = None,
) -> np.ndarray:
    """``tilde P = S^-1 P S^-T`` with ``S`` the canonical-A matrix (H0 §10)."""
    P = np.asarray(covariance, dtype=float)
    S = _scale_matrix(scales)
    S_inv = np.linalg.inv(S)
    return S_inv @ P @ S_inv.T


def scaled_to_physical_covariance(
    covariance_scaled,
    scales: Mapping[str, float] | None = None,
) -> np.ndarray:
    """``P = S tilde P S^T`` -- exact inverse of the mapping above."""
    P_tilde = np.asarray(covariance_scaled, dtype=float)
    S = _scale_matrix(scales)
    return S @ P_tilde @ S.T


def synthetic_alpha_covariance(
    alpha: float,
    correlation: np.ndarray | None = None,
    scales: Mapping[str, float] | None = None,
) -> np.ndarray:
    """Synthetic research covariance ``P0 = S_A (alpha^2 R) S_A^T`` (H0 §12).

    ``R`` defaults to the canonical identity (``tilde P0 = alpha^2 I``).
    Correlations are user / research inputs and carry NO physical-claim
    meaning (H0 §14).  Pure convention algebra; no sample is generated.
    """
    alpha = float(alpha)
    R = np.eye(STATE_DIM) if correlation is None else np.asarray(
        correlation, dtype=float)
    if R.shape != COVARIANCE_SHAPE:
        raise ValueError(f"correlation matrix must be {COVARIANCE_SHAPE}.")
    S = _scale_matrix(scales)
    return S @ ((alpha ** 2) * R) @ S.T


# ---------------------------------------------------------------------------
# Frozen linear uncertainty formulas (H0 §16, §19, §20) -- pure algebra
# ---------------------------------------------------------------------------
def linear_fixed_time_covariance(
    phi: np.ndarray, covariance: np.ndarray,
) -> np.ndarray:
    """``P(T) = Phi_H(T, 0) P0 Phi_H(T, 0)^T`` (H0 §16).

    Takes matrices as arguments -- it NEVER integrates a trajectory.  This
    is the frozen CONVENTION formula, exercised by the H0 semantic tests
    on synthetic matrices; H1 builds production results on top of it.
    """
    return np.asarray(phi, dtype=float) @ np.asarray(covariance, dtype=float) \
        @ np.asarray(phi, dtype=float).T


def scaled_linear_fixed_time_covariance(
    phi_scaled: np.ndarray, covariance_scaled: np.ndarray,
) -> np.ndarray:
    """``tilde P(T) = tilde Phi_H tilde P0 tilde Phi_H^T`` (H0 §16, scaled)."""
    return np.asarray(phi_scaled, dtype=float) \
        @ np.asarray(covariance_scaled, dtype=float) \
        @ np.asarray(phi_scaled, dtype=float).T


def terminal_time_variance(
    terminal_time_gradient: np.ndarray, covariance: np.ndarray,
) -> float:
    """``sigma_tT^2 = eta_T P0 eta_T^T`` (H0 §19) as a scalar variance."""
    eta = np.asarray(terminal_time_gradient, dtype=float).reshape(-1)
    P = np.asarray(covariance, dtype=float)
    return float(eta @ P @ eta)


def terminal_state_covariance(
    terminal_state_jacobian: np.ndarray, covariance: np.ndarray,
) -> np.ndarray:
    """``P_T = J_T P0 J_T^T`` (H0 §20)."""
    J = np.asarray(terminal_state_jacobian, dtype=float)
    return J @ np.asarray(covariance, dtype=float) @ J.T


def terminal_cross_covariance(
    terminal_state_jacobian: np.ndarray,
    covariance: np.ndarray,
    terminal_time_gradient: np.ndarray,
) -> np.ndarray:
    """``Cov(X_T, t_T) = J_T P0 eta_T^T`` (H0 §20)."""
    J = np.asarray(terminal_state_jacobian, dtype=float)
    eta = np.asarray(terminal_time_gradient, dtype=float).reshape(-1)
    return J @ np.asarray(covariance, dtype=float) @ eta


# ---------------------------------------------------------------------------
# Fixed-time uncertainty metrics (H0 §18) -- DESCRIPTIVE, not probabilities
# ---------------------------------------------------------------------------
def covariance_rms_spread(covariance_scaled: np.ndarray) -> float:
    """``sigma_RMS = sqrt(tr(tilde P))`` (H0 §18, scaled) -- descriptive."""
    P = np.asarray(covariance_scaled, dtype=float)
    return float(np.sqrt(np.trace(P)))


def covariance_sigma_max(covariance_scaled: np.ndarray) -> float:
    """``sigma_max = sqrt(lambda_max(tilde P))`` (H0 §18, scaled).

    Largest PRINCIPAL standard deviation of the scaled covariance; a
    DESCRIPTIVE dispersion metric, never a risk probability.
    """
    P = np.asarray(covariance_scaled, dtype=float)
    eigvals = np.linalg.eigvalsh(0.5 * (P + P.T))
    lam_max = float(np.max(eigvals))
    return float(np.sqrt(lam_max)) if lam_max >= 0.0 else float("nan")


def covariance_principal_directions(covariance_scaled: np.ndarray) -> np.ndarray:
    """Eigenvectors of ``tilde P`` (H0 §18); columns = principal directions."""
    P = np.asarray(covariance_scaled, dtype=float)
    eigvals, eigvecs = np.linalg.eigh(0.5 * (P + P.T))
    order = np.argsort(eigvals)[::-1]
    return np.asarray(eigvecs[:, order], dtype=float)


# ---------------------------------------------------------------------------
# Uncertainty-to-margin diagnostic ratios (H0 §30, §31) -- qualitative classes
# ---------------------------------------------------------------------------
def linearization_validity_ratio(
    characteristic_std: float, validity_radius: float,
) -> float:
    """``rho_lin = characteristic uncertainty amplitude / linearization
    radius`` (H0 §30).

    Qualitative protocol classes only (``rho << 1``: local; ``rho ~ 1``:
    nonlinear validation essential; ``rho > 1``: single first-order
    approximation not globally trusted).  No numerical cutoff is frozen.
    """
    return float(characteristic_std) / float(validity_radius)


def topology_margin_ratio(
    standard_deviation: float, topology_radius: float,
) -> float:
    """``rho_topo,j = sigma_j / epsilon_topo,j`` (H0 §31).

    Compares the input uncertainty cloud against the distance to a
    topology boundary.  ``rho_topo`` is NOT a topology-change probability:
    the real probability depends on distribution shape, correlation,
    boundary geometry and nonlinearity.
    """
    return float(standard_deviation) / float(topology_radius)


# ---------------------------------------------------------------------------
# Topology random variable (H0 §23-§25, §32)
# ---------------------------------------------------------------------------
# Discrete topology random variable Z = T(X0); platform probabilities
# p_k = P(Z = k) MUST come from an explicitly defined input distribution
# (possibly post nonlinear topology classification), never from "distance
# to boundary" alone.
TOPOLOGY_RANDOM_VARIABLE_LABEL = "Z = T(X0)"
TOPOLOGY_TRANSITION_PROBABILITY_DEFINITION = (
    "p_topo = P(Z != Z0); each p_k = P(Z = k) must come from an explicitly "
    "defined input distribution (by nonlinear sampling / a validated "
    "probabilistic approximation).  Distance / FTLE / |n^T f| / Phi_local "
    "alone never define a probability (H0 §24, §25, §45)."
)
NO_UNIVERSAL_NUMERIC_GRAZING_THRESHOLD_SUPPORTED = True


class SampleClassification(Enum):
    """H0 per-sample topology / linearization classification (H0 §23).

    Only TOPOLOGY_PRESERVED samples may enter a single nominal linear
    covariance's nonlinear validation population.
    """

    TOPOLOGY_PRESERVED = "TOPOLOGY_PRESERVED"
    TOPOLOGY_CHANGED = "TOPOLOGY_CHANGED"
    EVENT_ORDER_CHANGED = "EVENT_ORDER_CHANGED"
    TERMINAL_KIND_CHANGED = "TERMINAL_KIND_CHANGED"
    GRAZING_CROSSED = "GRAZING_CROSSED"
    LINEARIZATION_INVALID = "LINEARIZATION_INVALID"
    NONPHYSICAL_STATE = "NONPHYSICAL_STATE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


# ---------------------------------------------------------------------------
# Risk taxonomy (H0 §44) -- statistical research-model risks ONLY
# ---------------------------------------------------------------------------
class RiskMetricKind(Enum):
    """Frozen research "risk" vocabulary (H0 §44).

    These are statistical properties of the research model; they are NEVER
    automatically interpreted as vehicle survival / interception / mission
    success / target effects.
    """

    TOPOLOGY_TRANSITION_RISK = "TOPOLOGY_TRANSITION_RISK"
    LINEARIZATION_BREAKDOWN_RISK = "LINEARIZATION_BREAKDOWN_RISK"
    TERMINAL_KIND_CHANGE_RISK = "TERMINAL_KIND_CHANGE_RISK"
    STATE_DISPERSION = "STATE_DISPERSION"
    TERMINAL_TIME_DISPERSION = "TERMINAL_TIME_DISPERSION"
    NUMERICAL_FAILURE_RATE = "NUMERICAL_FAILURE_RATE"


RISK_SCOPE_NOTE = (
    "Phase-H 'risk' = statistical risk of the research model only: "
    "topology-transition / linearization-breakdown / terminal-kind-change / "
    "state dispersion / terminal-time dispersion / numerical-failure rate. "
    "NOT vehicle survival, interception, penetration, target-hit or mission "
    "success, and NOT optimization."
)

# ---------------------------------------------------------------------------
# Statistical error taxonomy (H0 §46) -- aligns with the Phase-G taxonomy
# ---------------------------------------------------------------------------
class StatisticalErrorCategory(Enum):
    """H0 statistical outcome / error taxonomy (H0 §46)."""

    VALID_FIXED_TOPOLOGY_SAMPLE = "VALID_FIXED_TOPOLOGY_SAMPLE"
    TOPOLOGY_CHANGED = "TOPOLOGY_CHANGED"
    EVENT_ORDER_CHANGED = "EVENT_ORDER_CHANGED"
    TERMINAL_KIND_CHANGED = "TERMINAL_KIND_CHANGED"
    LINEARIZATION_DOMAIN_EXCEEDED = "LINEARIZATION_DOMAIN_EXCEEDED"
    NONPHYSICAL_SAMPLE = "NONPHYSICAL_SAMPLE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    INVALID_COVARIANCE = "INVALID_COVARIANCE"
    INVALID_DISTRIBUTION = "INVALID_DISTRIBUTION"
    INSUFFICIENT_MONTE_CARLO_CONVERGENCE = (
        "INSUFFICIENT_MONTE_CARLO_CONVERGENCE"
    )


# ---------------------------------------------------------------------------
# Mixture semantics (H0 §26-§28, §27 law of total covariance)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MixedComponent:
    """One topology-conditioned component ``(p_k, mu_k, P_k)`` (H0 §26)."""

    probability: float
    mean: np.ndarray
    covariance: np.ndarray


MIXTURE_NOTE = (
    "Regime A (P(Z = Z0) ~ 1, linearization valid): single covariance "
    "P(T) = Phi_H P0 Phi_H^T suffices.  Regime B (P(Z != Z0) materially "
    "nonzero): report p_k, mu_k, P_k and distinguish within-topology "
    "covariance from between-topology separation.  Terminal mixtures with "
    "different terminal kinds must be conditioned by terminal kind or "
    "compared at a common fixed time (H0 §28); incompatible semantics are "
    "never blindly mixed."
)


def mixture_total_covariance(
    components: Iterable[MixedComponent],
) -> tuple[np.ndarray, np.ndarray]:
    """Law of total covariance (H0 §27):

    ``mu = sum_k p_k mu_k`` and
    ``P = sum_k p_k [P_k + (mu_k - mu)(mu_k - mu)^T]``.
    """
    comps = list(components)
    if not comps:
        raise ValueError("mixture needs at least one component.")
    mu = np.zeros(STATE_DIM, dtype=float)
    for c in comps:
        mu = mu + c.probability * np.asarray(c.mean, dtype=float)
    P = np.zeros((STATE_DIM, STATE_DIM), dtype=float)
    for c in comps:
        mu_k = np.asarray(c.mean, dtype=float)
        diff = mu_k - mu
        P = P + c.probability * (
            np.asarray(c.covariance, dtype=float) + np.outer(diff, diff))
    return np.asarray(mu, dtype=float), np.asarray(P, dtype=float)


# ---------------------------------------------------------------------------
# Monte-Carlo future protocol (H0 §33-§38, §47-§50) -- RULE freeze only
# ---------------------------------------------------------------------------
MONTE_CARLO_RNG_POLICY: Mapping[str, object] = {
    "generator": "numpy.random.Generator (via numpy.random.default_rng)",
    "global_implicit_state": "FORBIDDEN (no global np.random state)",
    "reproducibility_seed": 2026,
    "seed_role": "REPRODUCIBILITY seed only; NOT a physical parameter",
}
# The repository has no unified global seed convention: Phase-G tests use
# per-call numpy.random.default_rng(...) with local seeds.  H0 therefore
# freezes a dedicated reproducibility seed for future Monte-Carlo runs.
SEQUENTIAL_SAMPLE_SIZES: tuple[int, ...] = (256, 512, 1024, 2048, 4096)
SAMPLE_COUNT_POLICY_NOTE = (
    "Sample counts follow sequential convergence (256, 512, 1024, ...) on "
    "sample mean / sample covariance / topology probabilities / "
    "terminal-time moments; a bare N = 10000 is never frozen without "
    "statistical evidence (H0 §34)."
)
MC_CONVERGENCE_METRICS: tuple[str, ...] = (
    "sample_mean", "sample_covariance", "topology_probabilities",
    "terminal_time_moments",
)
PROBABILITY_CI_POLICY: Mapping[str, object] = {
    "method": "binomial Wilson interval",
    "confidence": 0.95,
    "normal_approximation_note": (
        "p +/- z sqrt(...) normal approximation avoided, especially near "
        "p ~ 0 or p ~ 1 (H0 §35)."
    ),
}
PAIRED_COMMON_RANDOM_NUMBERS = True
COMMON_RANDOM_NUMBERS_NOTE = (
    "Qian/Sanger fair paired comparison reuses one standardized sample "
    "mapped to the same delta x0 in both models (H0 §49)."
)
NONPHYSICAL_SAMPLE_POLICY = (
    "Gaussian tails are unbounded: a sample producing r <= R_E, v <= 0 or "
    "another invalid initial state is CLASSIFIED (NONPHYSICAL_SAMPLE) and "
    "never silently clipped / repaired; protocol A (record the fraction) is "
    "preferred unless the amplitude is obviously excessive (H0 §47, §48)."
)
SAMPLING_AND_CLASSIFICATION_SEPARATE = (
    "sampling generates delta x0 only; propagation/classification decides "
    "topology / validity.  Sampling code never clips, projects, reroutes or "
    "repairs samples (H0 §47)."
)
SIGMA_POINT_CHECK_NOTE = (
    "+/- principal-axis sigma points (delta x_i = +- L e_i, L L^T = P0) are "
    "a deterministic sanity check BEFORE Monte Carlo -- they are not a "
    "Monte-Carlo run (H0 §50)."
)


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple:
    """95% Wilson score interval for ``p_hat = k / n`` (H0 §35).

    Preferred over the normal approximation near p ~ 0 / 1.  Returns
    ``(lower, upper)`` clipped to ``[0, 1]``.
    """
    if n <= 0:
        raise ValueError("n must be a positive integer.")
    if not (0 <= k <= n):
        raise ValueError("k must satisfy 0 <= k <= n.")
    z = float(z)
    # Degenerate Wilson limits (k = 0 / k = n): the score interval is
    #  [0, z^2/(n+z^2)] and [n/(n+z^2), 1] respectively -- exact endpoints.
    if k == 0:
        return (0.0, float(z * z / (n + z * z)))
    if k == n:
        return (float(n / (n + z * z)), 1.0)
    p_hat = k / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = z * np.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n)) / denom
    return (float(max(0.0, center - half)), float(min(1.0, center + half)))


# ---------------------------------------------------------------------------
# Grazing validity inheritance (H0 §29-§32)
# ---------------------------------------------------------------------------
# Frozen Phase-G G6R2 result (docs/phase_g/phase_g_final_report.md,
# FINAL_AUTHORITY): r1% ~ 0.040 Phi_local and r5% ~ 0.185 Phi_local on the
# radial clearance-normalized local grazing families -- ONLY for the tested
# controlled families.  Phase H consumes these as LOCAL LINEARIZATION
# VALIDITY DIAGNOSTICS; they are never probability thresholds.
G6R2_VALIDITY_RADIUS_OVER_PHI: Mapping[str, float] = {
    "r_1pct_over_phi": 0.040,
    "r_5pct_over_phi": 0.185,
}
GRAZING_VALIDITY_INHERITANCE_NOTE = (
    "G6R2: r_1% ~ 0.040 Phi_local and r_5% ~ 0.185 Phi_local near "
    "n^T f^- = v sin(gamma) -> 0, valid only for the tested controlled "
    "grazing families.  They are local linearization-validity diagnostics "
    "(rho_lin inputs), never probability / risk thresholds; no universal "
    "numeric grazing threshold is supported (H0 §29, §32, §45)."
)

# ---------------------------------------------------------------------------
# Representative hierarchy (H0 §41, §42) -- reuse frozen Phase-G cases only
# ---------------------------------------------------------------------------
DEFAULT_FAIR_HORIZON_S = 600.0
# Common-time / cross-model fair-comparison convention (G5; H0 §39, §40):
# same nominal initial state, same elapsed time, same input probability
# law (or same declared dimensionless covariance), same canonical-A
# scaling, same sampling law and sample protocol.
FAIR_COMPARISON_NOTE = (
    "Qian vs Sanger fixed-time uncertainty: same nominal initial state, "
    "same elapsed time (default T = 600 s, per G5), same physical P0 or "
    "same declared tilde P0, same canonical-A scaling, same law, same "
    "sample protocol.  Native RTI/SRTI endpoint dispersion are DESCRIPTIVE "
    "and never a fair cross-model ranking (H0 §21, §39)."
)


def representative_cases() -> tuple[dict, ...]:
    """Frozen H-case hierarchy reused from the Phase-G set (H0 §41)."""
    out = []
    for c in REPRESENTATIVE_CASES:
        out.append({
            "key": c.key, "model": c.model,
            "gamma0_deg": c.gamma0_deg, "K": c.K,
            "expected_regime": c.expected_regime, "purpose": c.purpose,
        })
    # grazing anchors (B0..B4, 10 dual-reference extremal anchors)
    anchors = []
    for branch, side, param in GRAZING_ANCHOR_PARAMETERS:
        anchors.append({
            "branch": branch, "side": side,
            "parameter": [float(param[0]), float(param[1])],
        })
    return tuple(out), tuple(anchors)


# ---------------------------------------------------------------------------
# Claim boundaries & scope (H0 §44, §59, §60)
# ---------------------------------------------------------------------------
FORBIDDEN_CLAIMS = (
    "FTLE = probability",
    "sigma_max = risk probability",
    "distance to grazing = topology-change probability",
    "covariance alone = complete hybrid uncertainty",
    "Gaussian output assumption across a topology change",
    "native RTI/SRTI terminal uncertainty = fair cross-model comparison",
    "small variance = robust",
    "large variance = unsafe",
    "Monte-Carlo sample fraction without a CI = certified probability",
    "synthetic uncertainty = real-world calibrated uncertainty",
)
SCOPE_STATEMENT = (
    "Phase H first version studies model-prediction uncertainty around a "
    "nominal initial state: initial-state uncertainty propagation, "
    "terminal-time uncertainty, terminal-state uncertainty, hybrid "
    "topology-transition probability, linearization validity and "
    "branch-conditioned mixture statistics.  It does NOT study "
    "interception geometry, survival / evasion probability, defense "
    "penetration, target-hit probability, weapon effectiveness, "
    "engagement optimization or adversarial interception analysis."
)

# ---------------------------------------------------------------------------
# Representative future phase roadmap (H0 §55, §56)
# ---------------------------------------------------------------------------
PHASE_H_ROADMAP = (
    ("H0", "uncertainty / risk protocol freeze", "COMPLETE (this stage)"),
    ("H1", "fixed-topology linear uncertainty: P(T) = Phi P0 Phi^T, "
           "terminal-time variance, terminal-state covariance, rank / "
           "eigenspectrum", "future"),
    ("H2", "nonlinear Monte-Carlo validation (Qian/Sanger baseline T600 + "
           "deep fixed-topology Sanger cases)", "future"),
    ("H3", "grazing / topology-transition risk (B0-B4 topology probability)",
           "future"),
    ("H4", "topology-conditioned mixture uncertainty (within-topology "
           "covariance + between-topology separation)", "future"),
    ("H5", "cross-model common-time uncertainty synthesis", "future"),
    ("H6", "final audit / regression / manifest / freeze / tags", "future"),
)


# ---------------------------------------------------------------------------
# Machine-readable protocol payload (H0 §51, §54)
# ---------------------------------------------------------------------------
def machine_readable_protocol() -> dict:
    """Single JSON-able protocol snapshot (H0 §54 acceptance surface)."""
    cases, anchors = representative_cases()
    return {
        "protocol_version": "phase-h-uncertainty-risk-protocol-v1",
        "schema_version": "phase-h-uncertainty-risk-protocol-v1",
        "upstream": {
            "phase_g_tag": PHASE_G_TAG,
            "phase_g_commit": PHASE_G_COMMIT,
            "phase_f_commit": PHASE_F_COMMIT,
            "phase_f_tag": PHASE_F_TAG,
            "upstream_consumed": (
                "Phase H consumes frozen Phase-G derivatives; it does not "
                "redefine them."
            ),
        },
        "h0_status": {
            "phase_h0_done": PHASE_H0_DONE,
            "h1_started": H1_STARTED,
            "production_covariance_propagation_computed": (
                PRODUCTION_COVARIANCE_PROPAGATION_COMPUTED
            ),
            "monte_carlo_performed": MONTE_CARLO_PERFORMED,
            "topology_probability_computed": TOPOLOGY_PROBABILITY_COMPUTED,
            "uncertainty_map_generated": UNCERTAINTY_MAP_GENERATED,
            "gamma0_k_rescanned": GAMMA0_K_RE_SCANNED,
            "optimization_performed": OPTIMIZATION_PERFORMED,
        },
        "state_order": list(STATE_ORDER_TUPLE),
        "state_units": dict(STATE_UNITS),
        "random_variable_scope": {
            "convention": RANDOM_VARIABLE_NOTE,
            "randomized": list(RANDOMIZED_QUANTITIES),
            "not_randomized": list(NON_RANDOMIZED_QUANTITIES),
            "phase_f_parameter_response_distinct": (
                PHASE_F_PARAMETER_RESPONSE_DISTINCT_FROM_PHASE_H_RANDOM_STATE
            ),
        },
        "covariance_convention": {
            "shape": list(COVARIANCE_SHAPE),
            "required": ["finite", "symmetric", "positive-semidefinite"],
            "roundoff_tolerance": {
                "symmetry_relative": COVARIANCE_SYMMETRY_REL_TOL,
                "psd_relative": COVARIANCE_PSD_REL_TOL,
                "psd_absolute": COVARIANCE_PSD_ABS_TOL,
            },
            "repair_policy": (
                "silent abs(eigenvalues) or arbitrary repair FORBIDDEN; "
                "materially non-PSD = INVALID_COVARIANCE"
            ),
        },
        "canonical_scale": {
            "candidate": CANONICAL_SCALE_KEY,
            "status": CANONICAL_SCALE_STATUS,
            "values": {
                "r": float(canonical_scale()["r"]),
                "theta": float(canonical_scale()["theta"]),
                "v": float(canonical_scale()["v"]),
                "gamma": float(canonical_scale()["gamma"]),
            },
        },
        "scaled_covariance_convention": {
            "state_note": SCALED_STATE_NOTE,
            "covariance_note": SCALED_COVARIANCE_NOTE,
            "comparison_policy": (
                "uncertainty comparison is meaningful only after the input "
                "distribution / covariance geometry is specified (G5 "
                "scaling-geometry caveat inherited, H0 §11)."
            ),
        },
        "synthetic_distribution_family": {
            "label": SYNTHETIC_FAMILY_LABEL,
            "canonical_correlation": CANONICAL_CORRELATION_MATRIX,
            "alpha_status": ALPHA_STATUS,
            "alpha_role": ALPHA_ROLE_NOTE,
            "distribution_kinds": [k.value for k in UncertaintyDistributionKind],
        },
        "linear_fixed_time_formula": (
            "P(T) = Phi_H(T,0) P0 Phi_H(T,0)^T ; scaled tilde P(T) = "
            "tilde Phi_H tilde P0 tilde Phi_H^T"
        ),
        "terminal_time_variance_formula": (
            "sigma_tT^2 = eta_T P0 eta_T^T  (same terminal branch / kind, "
            "topology preserved)"
        ),
        "terminal_state_covariance_formula": "P_T = J_T P0 J_T^T",
        "terminal_cross_covariance_formula": (
            "Cov(X_T, t_T) = J_T P0 eta_T^T"
        ),
        "terminal_native_semantics": (
            "Qian RTI != Sanger SRTI; native terminal uncertainty is "
            "DESCRIPTIVE, never a fair performance comparison (H0 §21)."
        ),
        "topology_random_variable": {
            "label": TOPOLOGY_RANDOM_VARIABLE_LABEL,
            "definition": TOPOLOGY_TRANSITION_PROBABILITY_DEFINITION,
            "sample_classification": [s.value for s in SampleClassification],
            "no_universal_threshold": (
                NO_UNIVERSAL_NUMERIC_GRAZING_THRESHOLD_SUPPORTED
            ),
        },
        "mixture_semantics": {
            "note": MIXTURE_NOTE,
            "components": ["p_k", "mu_k", "P_k"],
            "law_of_total_covariance": (
                "mu = sum_k p_k mu_k ; P = sum_k p_k [P_k + "
                "(mu_k - mu)(mu_k - mu)^T]"
            ),
            "incompatible_terminals": (
                "different terminal kinds are never blindly mixed; "
                "condition by terminal kind or use a common fixed-time "
                "endpoint"
            ),
        },
        "grazing_validity_inheritance": {
            "g6r2_radius_over_phi": dict(G6R2_VALIDITY_RADIUS_OVER_PHI),
            "note": GRAZING_VALIDITY_INHERITANCE_NOTE,
            "rho_lin": "rho_lin = characteristic uncertainty / validated "
                       "linearization radius (no frozen cutoff)",
            "rho_topo": "rho_topo,j = sigma_j / epsilon_topo,j (not a "
                        "probability)",
        },
        "monte_carlo_rng_policy": dict(MONTE_CARLO_RNG_POLICY),
        "sample_count_convergence_policy": {
            "sequential_sizes": list(SEQUENTIAL_SAMPLE_SIZES),
            "convergence_metrics": list(MC_CONVERGENCE_METRICS),
            "note": SAMPLE_COUNT_POLICY_NOTE,
        },
        "probability_ci_policy": dict(PROBABILITY_CI_POLICY),
        "misc_protocol": {
            "paired_common_random_numbers": PAIRED_COMMON_RANDOM_NUMBERS,
            "common_random_numbers_note": COMMON_RANDOM_NUMBERS_NOTE,
            "nonphysical_sample_policy": NONPHYSICAL_SAMPLE_POLICY,
            "sampling_classification_separate": (
                SAMPLING_AND_CLASSIFICATION_SEPARATE
            ),
            "sigma_point_check_note": SIGMA_POINT_CHECK_NOTE,
        },
        "statistical_error_taxonomy": [
            e.value for e in StatisticalErrorCategory
        ],
        "risk_taxonomy": {
            "metrics": [r.value for r in RiskMetricKind],
            "scope_note": RISK_SCOPE_NOTE,
        },
        "representative_cases": {
            "h1_h2_fixed_topology": [
                {"key": "qian_baseline", "gamma0_deg": -5.0, "K": 3.0},
                {"key": "sanger_baseline", "gamma0_deg": -5.0, "K": 3.0,
                 "regime": "SRTI_N2"},
            ],
            "deep_sanger_topology": [
                "n0_deep", "n1_deep", "n2_deep", "n3_deep", "n4_deep",
                "n5_deep",
            ],
            "grazing_anchors": {
                "count": len(anchors),
                "branches": ["B0", "B1", "B2", "B3", "B4"],
                "parameters": [dict(a) for a in anchors],
            },
            "reuse_note": (
                "all representative cases reused from the frozen Phase-G / "
                "Phase-F sets; no re-selection in H0 (H0 §41, §42)."
            ),
        },
        "fair_comparison_convention": {
            "default_horizon_s": DEFAULT_FAIR_HORIZON_S,
            "note": FAIR_COMPARISON_NOTE,
            "canonical_input": (
                "tilde P0 = alpha^2 I is a research comparison convention, "
                "not a real flight distribution (H0 §40)."
            ),
        },
        "risk_boundary": {
            "active_module": "src/hyptraj/uncertainty/",
            "inactive_placeholders": [
                "src/hyptraj/risk/interception_geometry.py",
                "src/hyptraj/risk/survival.py",
            ],
            "scope_statement": SCOPE_STATEMENT,
        },
        "claim_boundaries": list(FORBIDDEN_CLAIMS),
        "future_phase_roadmap": [
            {"phase": p, "content": c, "status": s}
            for p, c, s in PHASE_H_ROADMAP
        ],
    }


def validate_protocol() -> None:
    """Drift guard: re-freeze the canonical scale / state order invariants."""
    assert tuple(STATE_ORDER) == STATE_ORDER_TUPLE
    sc = canonical_scale()
    assert abs(sc["r"] - 1e5) < 1e-9
    assert abs(sc["theta"] - 1.0) < 1e-12
    assert abs(sc["v"] - 7e3) < 1e-9
    assert abs(sc["gamma"] - 0.1) < 1e-12
