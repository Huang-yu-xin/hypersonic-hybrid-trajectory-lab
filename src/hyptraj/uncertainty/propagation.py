"""Phase-H1 fixed-topology linear uncertainty propagation.

H1 for the first time connects the two accepted chains:

    Phase-G frozen derivatives  (Phi_H, eta, J)
        +
    Phase-H uncertainty geometry (X0 = xbar0 + delta X0, P0 = Cov delta X0)
        ->
    linear propagated uncertainty

This module provides the fixed-topology, first-order LINEAR algebra only:
fixed-time covariance kernel, terminal-time / terminal-state / cross
covariance kernels, per-alpha response coefficients, covariance spectrum
(rank / nullity / raw-eigenvalue classification) and physical marginal
standard deviations.  It is a pure linear-algebra / validation / metrics
module:

* it NEVER integrates a trajectory, runs ``solve_ivp``, generates random
  numbers, or classifies topology from simulation (H1 §39);
* Phase-G derivative acquisition (reading the frozen G4/G5 artifacts) is
  the responsibility of the generator / caller (``scripts/
  run_phase_h1_linear_uncertainty.py``), NOT this module (H1 §39, §43);
* all frozen H0 protocol algebra helpers are REUSED (``protocol.py``), so
  H1 does not keep a second implementation of the covariance formulas
  (H1 §40).

H1 scientific framing (immutable):

* canonical input ``Z0 ~ N(0, alpha^2 R)`` with ``R = I`` canonical, so
  ``tilde P0 = alpha^2 I`` (H0 §12; H1 §8);
* ``alpha`` stays SYMBOLIC (``ALPHA_STATUS = PENDING_NUMERICAL_AUDIT``).
  Every quantity is reported as a PER-ALPHA RESPONSE COEFFICIENT
  (``..._per_alpha`` or ``..._per_alpha2``), never as a concrete finite-
  alpha uncertainty realization (H1 §9, §11, §36);
* fixed-time kernel ``K_x(T) = tilde Phi_H R tilde Phi_H^T`` (canonical:
  ``tilde Phi_H tilde Phi_H^T``), so ``sqrt(lambda_max(K_x)) ==
  sigma_max(tilde Phi_H) == G5 canonical-A sigma_max`` (H1 §14 strong G5
  closure); principal output directions match the G5 left singular
  vectors up to sign (H1 §15);
* numerical rank uses the FROZEN Phase-G rank convention
  ``sigma_max * max(m, n) * eps_machine`` (G5 §16) applied to the root
  spectrum ``sqrt(lambda_i(K))``, so structural rank loss (Qian
  post-Capture ``rank = 3``; Qian RTI terminal ``rank(J) = 2``; Sanger
  SRTI terminal ``rank(J) = 3``) is reproduced exactly (H1 §16, §30);
* tiny negative kernel eigenvalues within the H0 covariance PSD tolerance
  are ROUND_OFF_ZERO: the RAW eigenvalue and its classification are kept,
  no ``abs(eigenvalues)`` repair, the negative is treated as 0 only when
  taking a square root; a MATERIAL negative eigenvalue is an H1 FAIL
  (H1 §17).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from hyptraj.uncertainty.protocol import (
    COVARIANCE_PSD_ABS_TOL,
    COVARIANCE_PSD_REL_TOL,
    COVARIANCE_SHAPE,
    STATE_DIM,
    STATE_ORDER_TUPLE,
    canonical_scale_matrix,
    covariance_principal_directions,
    linear_fixed_time_covariance,
    scaled_to_physical_covariance,
    terminal_cross_covariance,
    terminal_state_covariance,
    terminal_time_variance,
    validate_covariance,
)

# ---------------------------------------------------------------------------
# Input guards (H1 §41, §42)
# ---------------------------------------------------------------------------
def require_linear_map(phi, *, name: str = "matrix") -> np.ndarray:
    """Guard: a ``(4, 4)`` finite linear map (Phi_H, J)."""
    P = np.asarray(phi, dtype=float)
    if P.ndim != 2 or P.shape != COVARIANCE_SHAPE:
        raise ValueError(f"{name} must have shape (4, 4).")
    if not np.all(np.isfinite(P)):
        raise ValueError(f"{name} must be finite.")
    return P


def require_gradient(eta, *, name: str = "eta") -> np.ndarray:
    """Guard: a ``(4,)`` finite terminal-time gradient (eta)."""
    v = np.asarray(eta, dtype=float).reshape(-1)
    if v.shape != (STATE_DIM,):
        raise ValueError(f"{name} must have shape (4,).")
    if not np.all(np.isfinite(v)):
        raise ValueError(f"{name} must be finite.")
    return v


def require_correlation_matrix(
    R,
    *,
    require_correlation: bool = False,
    diag_tol: float = 1e-6,
) -> np.ndarray:
    """Guard: ``R`` is a ``(4, 4)`` finite symmetric PSD matrix.

    With ``require_correlation=True`` the matrix is additionally required
    to be a proper CORRELATION matrix (unit diagonal), matching the naming
    contract of H1 §42.  A generic PSD matrix without unit diagonal must
    be named "scaled covariance geometry", not "correlation matrix" --
    H1 does not silently treat an arbitrary PSD matrix as a correlation
    matrix.
    """
    R = np.asarray(R, dtype=float)
    if R.ndim != 2 or R.shape != COVARIANCE_SHAPE:
        raise ValueError(f"correlation matrix R must have shape (4, 4).")
    if not np.all(np.isfinite(R)):
        raise ValueError("correlation matrix R must be finite.")
    result = validate_covariance(R)
    if not result.valid:
        raise ValueError(
            f"correlation matrix R is not a valid PSD covariance: {result.reasons}"
        )
    if require_correlation:
        diag_dev = float(np.max(np.abs(np.diag(R) - 1.0)))
        if diag_dev > diag_tol:
            raise ValueError(
                "R is named 'correlation matrix' but diag(R) != 1 "
                f"(max |diag-1| = {diag_dev:.3e}); use "
                "'scaled covariance geometry' for a generic PSD input."
            )
    return R


def _as_psd_kernel(K: np.ndarray, name: str = "kernel") -> np.ndarray:
    """Symmetrize a theoretically-PSD product ``A R A^T`` for eigensolvers.

    ``A R A^T`` is PSD in exact arithmetic; only bit-level asymmetry from
    the matrix product is possible, and eigvalsh/eigh are called on an
    explicit symmetrization (classification-only, never an abs() repair).
    """
    return 0.5 * (np.asarray(K, dtype=float) + np.asarray(K, dtype=float).T)


# ---------------------------------------------------------------------------
# Fixed-time kernels (H1 §10, §16)
# ---------------------------------------------------------------------------
def fixed_time_alpha_kernel(
    phi_scaled: np.ndarray,
    R=None,
    *,
    require_correlation: bool = False,
) -> np.ndarray:
    """Normalized fixed-time response kernel ``K_x = tilde Phi_H R tilde Phi_H^T``.

    ``R`` defaults to the canonical identity (``tilde P0 = alpha^2 I``).
    This is NOT a covariance for any finite alpha -- it is the normalized
    covariance-response kernel per ``alpha^2`` (H1 §10, §11):
    ``tilde P(T) = alpha^2 K_x(T)``.
    """
    Phi = require_linear_map(phi_scaled, name="tilde Phi_H")
    if R is None:
        R = np.eye(STATE_DIM)
    R = require_correlation_matrix(R, require_correlation=require_correlation)
    return Phi @ R @ Phi.T


def fixed_time_covariance(phi: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    """``P(T) = Phi_H P0 Phi_H^T`` (frozen H0 convention, H1 §0).

    Thin wrapper over the frozen H0 algebra helper so H1 keeps a single
    implementation of the covariance propagation formula.
    """
    Phi = require_linear_map(phi, name="Phi_H")
    P = np.asarray(covariance, dtype=float)
    result = validate_covariance(P)
    if not result.valid:
        raise ValueError(f"P0 is not a valid covariance: {result.reasons}")
    return linear_fixed_time_covariance(Phi, P)


def physical_covariance_coefficient(
    kernel: np.ndarray, scales: Mapping[str, float] | None = None
) -> np.ndarray:
    """Physical per-alpha-squared covariance coefficient ``P / alpha^2 = S K S^T``.

    ``P(T) = alpha^2 S_A K_x S_A^T`` (H1 §18).  Reuses the frozen H0
    scaling conversion algebra (``scaled_to_physical_covariance``).
    """
    K = _as_psd_kernel(kernel, name="K_x")
    if scales is None:
        return scaled_to_physical_covariance(K)
    S = np.diag([float(scales[k]) for k in STATE_ORDER_TUPLE])
    return S @ K @ S.T


def physical_marginal_std_per_alpha(
    kernel: np.ndarray, scales: Mapping[str, float] | None = None
) -> np.ndarray:
    """Physical per-unit-alpha marginal standard deviations.

    ``sigma_{x_i} / alpha = s_i * sqrt((K_x)_ii)`` (H1 §18) in canonical
    units [r=m, theta=rad, v=m/s, gamma=rad].  A roundoff-negative
    diagonal element is treated as 0 (no abs repair).
    """
    K = _as_psd_kernel(kernel, name="K_x")
    if scales is None:
        scales = {"r": 1e5, "theta": 1.0, "v": 7e3, "gamma": 0.1}
    out = []
    for i, key in enumerate(STATE_ORDER_TUPLE):
        si = float(scales[key])
        diag = float(K[i, i])
        out.append(si * np.sqrt(diag if diag > 0.0 else 0.0))
    return np.asarray(out, dtype=float)


# ---------------------------------------------------------------------------
# Terminal kernels (H1 §26-§31)
# ---------------------------------------------------------------------------
def terminal_alpha_kernels(
    j_scaled: np.ndarray,
    eta_scaled: np.ndarray,
    R=None,
    *,
    require_correlation: bool = False,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Terminal per-alpha-squared kernels.

    Returns ``(K_T, sigma_t^2/alpha^2, Cov(Z_T, t_T)/alpha^2)`` with
    (H1 §26, §29, §31):

    * ``K_T = tilde J_T R tilde J_T^T``        (terminal-state kernel);
    * ``sigma_t^2 / alpha^2 = eta_scaled R eta_scaled^T``
      where ``eta_scaled = eta S_A`` (seconds per dimensionless input);
    * ``Cov(Z_T, t_T) / alpha^2 = tilde J_T R eta_scaled^T``  (shape (4,),
      units seconds, because the scaled state is dimensionless).
    """
    Jb = require_linear_map(j_scaled, name="tilde J_T")
    etab = require_gradient(eta_scaled, name="eta_scaled")
    if R is None:
        R = np.eye(STATE_DIM)
    R = require_correlation_matrix(R, require_correlation=require_correlation)
    K_T = terminal_state_covariance(Jb, R)                     # Jb R Jb^T
    t_var_per_a2 = float(terminal_time_variance(etab, R))      # etab R etab^T
    cross_per_a2 = terminal_cross_covariance(Jb, R, etab)      # Jb R etab^T (4,)
    return np.asarray(K_T, dtype=float), t_var_per_a2, np.asarray(cross_per_a2)


def terminal_time_std_per_alpha(
    eta_scaled: np.ndarray, R=None, *, require_correlation: bool = False
) -> float:
    """``sigma_t / alpha = sqrt(eta_scaled R eta_scaled^T)``.

    Canonical ``R = I`` reduces to ``||eta S_A||_2`` (H1 §27) = the frozen
    G5 ``scaled_event_time_norm_seconds``.
    """
    etab = require_gradient(eta_scaled, name="eta_scaled")
    if R is None:
        R = np.eye(STATE_DIM)
    R = require_correlation_matrix(R, require_correlation=require_correlation)
    var = float(etab @ R @ etab)
    return float(np.sqrt(var)) if var >= 0.0 else float("nan")


# ---------------------------------------------------------------------------
# Covariance spectrum: raw eigenvalues / classification / frozen rank (H1 §16, §17)
# ---------------------------------------------------------------------------
# H1 numerical rank reuses the FROZEN H0 COVARIANCE rank convention
# (protocol.validate_covariance): 
#   numerical_rank = count of eigenvalues > lambda_max * max(m, n) * eps_machine
# applied to the eigenvalues of the PSD kernel K = A R A^T.
#
# This is the Phase-H-consistent choice (H1 propagates covariances, and H1
# §17 points at the H0 covariance PSD tolerance).  It coincides with the
# accepted G5 ranks on every frozen H1 case (Qian T600 3, Sanger T600/T900
# 4; Qian RTI terminal 2, Sanger SRTI terminal 3).  The stricter map-SVD
# threshold (sigma_max * max(m,n) * eps, G5) is NOT used for the kernel
# rank: the frozen snapshots store Phi_J rounded to ~8 significant digits,
# which perturbs structurally-zero singular values to ~1e-9 and would
# misreport the Qian-terminal kernel rank as 3.
def frozen_numerical_rank(K: np.ndarray) -> tuple[int, int]:
    """``(numerical_rank, nullity)`` under the frozen H0 covariance rank
    convention (count eigenvalues > lambda_max * max(m, n) * eps)."""
    K = _as_psd_kernel(K)
    lam = np.linalg.eigvalsh(K)[::-1]
    if lam.size == 0 or lam[0] <= 0.0:
        return (0, STATE_DIM)
    tol = float(lam[0] * STATE_DIM * np.finfo(float).eps)
    rank = int(np.count_nonzero(lam > tol))
    return rank, STATE_DIM - rank


@dataclass(frozen=True)
class CovarianceSpectrum:
    """Raw eigenvalue spectrum of a kernel + frozen classification (H1 §17)."""

    raw_eigenvalues: np.ndarray            # descending
    eigenvalue_classification: tuple[str, ...]   # per eigenvalue (descending)
    numerical_rank: int
    nullity: int


def covariance_spectrum(covariance: np.ndarray) -> CovarianceSpectrum:
    """Raw eigenvalues (descending), classification and frozen rank/nullity.

    Numerical rank uses the frozen H0 covariance rank convention
    (``frozen_numerical_rank``: count eigenvalues > lambda_max * max(m, n)
    * eps), which reproduces the accepted G5 ranks on every frozen H1 case.

    Classification (H0 covariance PSD tolerance, H1 §17):

    * ``POSITIVE``          lambda above the numerical-zero scale;
    * ``NUMERIC_ZERO``      tiny positive within the H0 PSD tolerance
                            (a structurally-zero direction whose Gram
                            eigenvalue came out slightly positive);
    * ``ZERO``              lambda == 0 exactly;
    * ``ROUND_OFF_ZERO``    tiny negative within the H0 PSD tolerance
                            (treated as 0 only when a square root is taken);
    * ``MATERIAL_NEGATIVE`` below the tolerance -> raises (H1 FAIL).

    The raw eigenvalues and their classification are always preserved in
    the snapshot; no ``abs(eigenvalues)`` repair is performed.
    """
    K = _as_psd_kernel(covariance, name="covariance")
    lam = np.linalg.eigvalsh(K)                # ascending
    lam_desc = lam[::-1]
    lam_max = float(lam_desc[0]) if lam_desc.size else 0.0
    zero_tol = max(float(COVARIANCE_PSD_ABS_TOL),
                   float(COVARIANCE_PSD_REL_TOL) * lam_max)
    classes = []
    for x in lam_desc:
        if x < -zero_tol:
            classes.append("MATERIAL_NEGATIVE")
        elif x < 0.0:
            classes.append("ROUND_OFF_ZERO")
        elif x == 0.0:
            classes.append("ZERO")
        elif x < zero_tol:
            classes.append("NUMERIC_ZERO")
        else:
            classes.append("POSITIVE")
    if "MATERIAL_NEGATIVE" in classes:
        raise ValueError(
            "H1 FAIL: kernel has a material negative eigenvalue "
            f"{float(min(lam_desc)):.3e} (below H0 PSD tolerance); "
            "no abs() repair is allowed."
        )
    rank, nullity = frozen_numerical_rank(K)
    return CovarianceSpectrum(
        raw_eigenvalues=np.asarray(lam_desc, dtype=float),
        eigenvalue_classification=tuple(classes),
        numerical_rank=rank,
        nullity=nullity,
    )


# ---------------------------------------------------------------------------
# Result containers (H1 §38)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FixedTimeLinearUncertaintyResult:
    """One fixed-topology fixed-time linear uncertainty case (H1 §46)."""

    model: str
    horizon_s: float
    topology_signature: tuple[str, ...]
    endpoint_mode: str
    R: np.ndarray
    phi_source: str
    scaled_phi: np.ndarray
    kernel: np.ndarray                       # K_x (canonical)
    spectrum: CovarianceSpectrum
    sigma_rms_per_alpha: float
    sigma_max_per_alpha: float
    principal_directions: np.ndarray         # columns = covariance eigenvectors (desc)
    physical_marginal_std_per_alpha: np.ndarray
    # G5 fixed-time closure
    g5_sigma_max: float
    g5_sigma_crosscheck_error: float         # material relative error
    # reference 0.1 vs 0.05 stability
    kernel_ref_01: np.ndarray
    kernel_ref_05: np.ndarray
    reference_kernel_max_abs_diff: float
    reference_kernel_material_rel_diff: float
    reference_sigma_max_diff: float
    reference_sigma_rms_diff: float
    reference_principal_direction_alignment: float
    reference_rank_01: int
    reference_rank_05: int
    # production kernel vs accepted reference
    production_kernel_max_abs_diff: float
    production_kernel_material_rel_diff: float
    production_sigma_max_diff: float


@dataclass(frozen=True)
class TerminalLinearUncertaintyResult:
    """One native-terminal linear uncertainty case (H1 §48)."""

    model: str
    terminal_kind: str
    terminal_time: float
    R: np.ndarray
    eta: np.ndarray
    eta_scaled: np.ndarray
    J: np.ndarray
    J_scaled: np.ndarray
    terminal_state_kernel: np.ndarray        # K_T
    spectrum: CovarianceSpectrum
    terminal_sigma_rms_per_alpha: float
    terminal_sigma_max_per_alpha: float
    terminal_time_std_per_alpha: float       # sigma_t / alpha
    scaled_state_time_cross_cov_per_alpha2: np.ndarray   # (4,)
    scaled_state_time_correlation: np.ndarray            # (4,), NaN where undefined
    physical_marginal_std_per_alpha: np.ndarray
    # G5 terminal closure
    g5_eta_norm: float
    g5_eta_crosscheck_error: float
    g5_scaled_sigma_max: float
    g5_terminal_sigma_crosscheck_error: float
    g5_rank: int
    rank_matches_g5: bool
    reference_status: str


# ---------------------------------------------------------------------------
# Case assemblers (H1 §43, §46, §48) -- pure algebra over caller matrices
# ---------------------------------------------------------------------------
def _material_rel(a: np.ndarray, b: np.ndarray) -> float:
    diff = float(np.max(np.abs(a - b)))
    denom = max(float(np.max(np.abs(a))), float(np.max(np.abs(b))), 1e-300)
    return float(diff / denom)


def _max_eigenvalue(K: np.ndarray) -> float:
    ev = np.linalg.eigvalsh(_as_psd_kernel(K))
    return float(np.max(ev)) if ev.size else 0.0


def compute_fixed_time_case(
    *,
    model: str,
    horizon_s: float,
    topology_signature: Sequence[str],
    endpoint_mode: str,
    phi_ref_01: np.ndarray,
    phi_ref_05: np.ndarray,
    phi_production: np.ndarray,
    R=None,
    scales: Mapping[str, float] | None = None,
    g5_sigma_max: float | None = None,
) -> FixedTimeLinearUncertaintyResult:
    """Assemble one fixed-time case from caller-supplied frozen Phi matrices.

    The generator feeds the accepted G4 ``phi_ref_01 / phi_ref_05 /
    phi_production`` matrices; this assembler scales them with the frozen
    canonical ``S_A``, builds the kernels, and computes every per-alpha
    response coefficient plus the G5 / reference / production cross-checks.
    """
    if scales is None:
        S = canonical_scale_matrix()
        S_inv = np.linalg.inv(S)
    else:
        S = np.diag([float(scales[k]) for k in STATE_ORDER_TUPLE])
        S_inv = np.linalg.inv(S)
    if R is None:
        R = np.eye(STATE_DIM)
    R = require_correlation_matrix(R, require_correlation=False)

    Phi01 = require_linear_map(phi_ref_01, name="phi_ref_01")
    Phi05 = require_linear_map(phi_ref_05, name="phi_ref_05")
    Phi_p = require_linear_map(phi_production, name="phi_production")

    scaled_phi = S_inv @ Phi01 @ S
    scaled_phi_05 = S_inv @ Phi05 @ S
    scaled_phi_prod = S_inv @ Phi_p @ S
    K01 = fixed_time_alpha_kernel(scaled_phi, R)
    K05 = fixed_time_alpha_kernel(scaled_phi_05, R)
    K_prod = fixed_time_alpha_kernel(scaled_phi_prod, R)

    spectrum = covariance_spectrum(K01)
    sigma_max_a = float(np.sqrt(_max_eigenvalue(K01)))
    sigma_rms_a = float(np.sqrt(np.trace(K01)))
    directions = covariance_principal_directions(K01)
    margins = physical_marginal_std_per_alpha(K01, scales=scales)

    if g5_sigma_max is None:
        g5 = float("nan")
        g5_err = float("nan")
    else:
        g5 = float(g5_sigma_max)
        g5_err = abs(sigma_max_a - g5) / g5 if g5 != 0 else float("nan")

    ref_max_diff = float(np.max(np.abs(K01 - K05)))
    ref_mat = _material_rel(K01, K05)
    s01 = float(np.sqrt(_max_eigenvalue(K01)))
    s05 = float(np.sqrt(_max_eigenvalue(K05)))
    ref_align = abs(
        covariance_principal_directions(K01)[:, 0]
        @ covariance_principal_directions(K05)[:, 0]
    )
    rank01, _ = frozen_numerical_rank(K01)
    rank05, _ = frozen_numerical_rank(K05)

    prod_max_diff = float(np.max(np.abs(K_prod - K01)))
    prod_mat = _material_rel(K_prod, K01)
    s_prod = float(np.sqrt(_max_eigenvalue(K_prod)))

    return FixedTimeLinearUncertaintyResult(
        model=model, horizon_s=float(horizon_s),
        topology_signature=tuple(topology_signature),
        endpoint_mode=endpoint_mode,
        R=np.asarray(R, dtype=float), phi_source="phase_g4_hybrid_stm_v1",
        scaled_phi=np.asarray(scaled_phi, dtype=float),
        kernel=np.asarray(K01, dtype=float), spectrum=spectrum,
        sigma_rms_per_alpha=float(sigma_rms_a),
        sigma_max_per_alpha=float(sigma_max_a),
        principal_directions=np.asarray(directions, dtype=float),
        physical_marginal_std_per_alpha=np.asarray(margins, dtype=float),
        g5_sigma_max=float(g5), g5_sigma_crosscheck_error=float(g5_err),
        kernel_ref_01=np.asarray(K01, dtype=float),
        kernel_ref_05=np.asarray(K05, dtype=float),
        reference_kernel_max_abs_diff=float(ref_max_diff),
        reference_kernel_material_rel_diff=float(ref_mat),
        reference_sigma_max_diff=float(abs(s01 - s05)),
        reference_sigma_rms_diff=float(
            abs(np.sqrt(np.trace(K01)) - np.sqrt(np.trace(K05)))),
        reference_principal_direction_alignment=float(ref_align),
        reference_rank_01=int(rank01), reference_rank_05=int(rank05),
        production_kernel_max_abs_diff=float(prod_max_diff),
        production_kernel_material_rel_diff=float(prod_mat),
        production_sigma_max_diff=float(abs(s_prod - s01)),
    )


def compute_terminal_case(
    *,
    model: str,
    terminal_kind: str,
    terminal_time: float,
    eta: np.ndarray,
    J: np.ndarray,
    R=None,
    scales: Mapping[str, float] | None = None,
    g5_eta_norm: float | None = None,
    g5_scaled_sigma_max: float | None = None,
    g5_rank: int | None = None,
    reference_status: str = "PASS",
) -> TerminalLinearUncertaintyResult:
    """Assemble one native-terminal case from the frozen G5 ``(eta, J)``.

    Uses the G5R frozen terminal configuration (the G5 snapshot already
    froze ``eta`` and ``J`` at the accepted trim).  The scaled terminal
    map is ``tilde J_T = S_A^-1 J S_A`` and the scaled terminal-time
    gradient is ``eta_scaled = eta S_A`` (H1 §26).
    """
    if scales is None:
        S = canonical_scale_matrix()
        S_inv = np.linalg.inv(S)
    else:
        S = np.diag([float(scales[k]) for k in STATE_ORDER_TUPLE])
        S_inv = np.linalg.inv(S)
    if R is None:
        R = np.eye(STATE_DIM)
    R = require_correlation_matrix(R, require_correlation=False)

    eta_v = require_gradient(eta, name="eta")
    J_m = require_linear_map(J, name="J")
    J_scaled = S_inv @ J_m @ S
    eta_scaled = eta_v @ S

    K_T, t_var_per_a2, cross_per_a2 = terminal_alpha_kernels(
        J_scaled, eta_scaled, R)
    spectrum = covariance_spectrum(K_T)
    sigma_max_a = float(np.sqrt(_max_eigenvalue(K_T)))
    sigma_rms_a = float(np.sqrt(np.trace(K_T)))
    t_std_a = float(np.sqrt(t_var_per_a2))
    margins = physical_marginal_std_per_alpha(K_T, scales=scales)

    # Scaled state-time correlation (H1 §32, optional descriptive): alpha
    # cancels; components with a structural-zero state variance are NaN.
    cross_rho = np.full((STATE_DIM,), np.nan, dtype=float)
    sigma_state = np.sqrt(np.maximum(np.diag(K_T), 0.0))
    if t_std_a > 0.0:
        for i in range(STATE_DIM):
            if sigma_state[i] > 0.0:
                cross_rho[i] = float(cross_per_a2[i] / (sigma_state[i] * t_std_a))

    if g5_eta_norm is None:
        g5_eta = float("nan"); g5_eta_err = float("nan")
    else:
        g5_eta = float(g5_eta_norm)
        g5_eta_err = abs(t_std_a - g5_eta) / g5_eta if g5_eta != 0 else float("nan")
    if g5_scaled_sigma_max is None:
        g5_ssm = float("nan"); g5_ssm_err = float("nan")
    else:
        g5_ssm = float(g5_scaled_sigma_max)
        g5_ssm_err = abs(sigma_max_a - g5_ssm) / g5_ssm if g5_ssm != 0 else float("nan")
    rank, _ = spectrum.numerical_rank, spectrum.nullity
    rank_match = (g5_rank is None) or (int(rank) == int(g5_rank))

    return TerminalLinearUncertaintyResult(
        model=model, terminal_kind=terminal_kind,
        terminal_time=float(terminal_time), R=np.asarray(R, dtype=float),
        eta=np.asarray(eta_v, dtype=float),
        eta_scaled=np.asarray(eta_scaled, dtype=float),
        J=np.asarray(J_m, dtype=float),
        J_scaled=np.asarray(J_scaled, dtype=float),
        terminal_state_kernel=np.asarray(K_T, dtype=float),
        spectrum=spectrum,
        terminal_sigma_rms_per_alpha=float(sigma_rms_a),
        terminal_sigma_max_per_alpha=float(sigma_max_a),
        terminal_time_std_per_alpha=float(t_std_a),
        scaled_state_time_cross_cov_per_alpha2=np.asarray(cross_per_a2, dtype=float),
        scaled_state_time_correlation=np.asarray(cross_rho, dtype=float),
        physical_marginal_std_per_alpha=np.asarray(margins, dtype=float),
        g5_eta_norm=float(g5_eta), g5_eta_crosscheck_error=float(g5_eta_err),
        g5_scaled_sigma_max=float(g5_ssm),
        g5_terminal_sigma_crosscheck_error=float(g5_ssm_err),
        g5_rank=int(g5_rank) if g5_rank is not None else -1,
        rank_matches_g5=bool(rank_match), reference_status=reference_status,
    )
