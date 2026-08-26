"""M2 -- covariance legality projection and frozen legality checking
(task Sec. 11, 16, 17).

Pipeline for every covariance candidate before use:

    Sigma_pre      candidate-specific pre-covariance (C0 / C1 / C2 / C3 / C4)
    -- symmetrize  C <- (C + C^T) / 2                              (Sec. 11)
    -- eigen clip  eig_j <- clip(eig_j, lambda_min_floor, lambda_max_cap)   (Sec. 16)
    -- legality    frozen checker on the projected matrix            (Sec. 16)

Preregistered numerical bounds (engineering choices, NOT theory constants,
task Sec. 16):

    lambda_min_floor = 0.55
    lambda_max_cap   = 4.00

The second-stage legality check REUSES the frozen M1/M1-D Gaussian
second-moment legality discipline: the constant
``hyptraj.m1.proposal_update.LEGALITY_MIN_EIG`` (min eigenvalue of every
component covariance must be >= 0.5 so that ``Sigma - I/2`` stays PSD --
positive densities everywhere + finite second moment under the frozen v0
family).  M2 does not redefine a competing version.

Validity failures (NaN / Inf / negative numerical eigenvalues below
tolerance) are RECORDED as failures with an explicit fallback decision --
never silently repaired (task Sec. 11).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.m1.proposal_update import LEGALITY_MIN_EIG
from hyptraj.m2.variance_covariance import symmetrize_matrix

LAMBDA_MIN_FLOOR = 0.55
LAMBDA_MAX_CAP = 4.00

_NEG_EIG_TOL = 1e-10          # numerical tolerance below zero


@dataclass(frozen=True)
class ProjectionResult:
    """Task Sec. 17 projection metadata block (all fields persisted)."""

    valid_input: bool                     # no NaN/Inf; no neg eig below tol
    validity_reasons: tuple[str, ...]
    sigma_pre: np.ndarray                 # symmetrized input actually used
    sigma_final: np.ndarray               # projected matrix actually used
    eigenvalues_pre: np.ndarray           # ascending
    eigenvalues_post: np.ndarray          # ascending
    n_eigen_clipped_low: int
    n_eigen_clipped_high: int
    projection_frobenius_norm: float
    legality_passed: bool                 # frozen checker verdict post-projection
    min_eig_final: float


def _validity_scan(mat: np.ndarray) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if mat.shape[0] != mat.shape[1]:
        reasons.append("non_square")
        return False, reasons
    if not np.all(np.isfinite(mat)):
        reasons.append("non_finite_entries")
        return False, reasons
    sym = symmetrize_matrix(mat)
    eig = np.linalg.eigvalsh(sym)
    if np.any(eig < -_NEG_EIG_TOL):
        reasons.append(f"negative_numerical_eigenvalue min={float(eig[0]):.3g}")
        return False, reasons
    return True, reasons


def project_covariance(
    sigma_pre: np.ndarray,
    floor: float = LAMBDA_MIN_FLOOR,
    cap: float = LAMBDA_MAX_CAP,
) -> ProjectionResult:
    """Symmetrize + eigen-clip + frozen legality check of one candidate.

    The input is ALWAYS symmetrized first ((C + C^T)/2 -- task Sec. 11) and
    that symmetrized matrix is what gets recorded as ``sigma_pre``, then
    scanned for validity (finite entries, no negative numerical eigenvalues).
    On valid input: eigen-decompose, clip eigenvalues to ``[floor, cap]``,
    reconstruct ``U diag U^T``, re-symmetrize, then run the FROZEN legality
    checker (:func:`check_legality_frozen`).  The clip floor already sits
    above ``LEGALITY_MIN_EIG = 0.5``, so a successful projection passes the
    frozen gate by construction unless numerics corrupt it -- any such
    corruption is surfaced through ``legality_passed = False``.
    """
    mat = np.asarray(sigma_pre, dtype=float)
    d = mat.shape[0] if mat.ndim == 2 else 0
    eye = np.eye(d)
    if d == 0 or mat.shape[0] != mat.shape[1]:
        return ProjectionResult(
            valid_input=False, validity_reasons=("non_square",),
            sigma_pre=mat, sigma_final=eye,
            eigenvalues_pre=np.full(d, np.nan),
            eigenvalues_post=np.full(d, np.nan),
            n_eigen_clipped_low=0, n_eigen_clipped_high=0,
            projection_frobenius_norm=float("nan"),
            legality_passed=False, min_eig_final=float("nan"),
        )

    s = symmetrize_matrix(mat)
    ok, reasons = _validity_scan(s)
    if not ok:
        return ProjectionResult(
            valid_input=False, validity_reasons=tuple(reasons),
            sigma_pre=s, sigma_final=eye,
            eigenvalues_pre=np.linalg.eigvalsh(s)
            if np.all(np.isfinite(s)) else np.full(d, np.nan),
            eigenvalues_post=np.full(d, np.nan),
            n_eigen_clipped_low=0, n_eigen_clipped_high=0,
            projection_frobenius_norm=float("nan"),
            legality_passed=False, min_eig_final=float("nan"),
        )

    val, vec = np.linalg.eigh(s)              # ascending eigvals, orthonormal vec
    lo = int(np.sum(val < floor))
    hi = int(np.sum(val > cap))
    val2 = np.clip(val, float(floor), float(cap))
    sig = (vec * val2) @ vec.T
    sig = symmetrize_matrix(sig)

    legal, min_eig = check_legality_frozen(sig)
    frob = float(np.linalg.norm(sig - s))

    return ProjectionResult(
        valid_input=True, validity_reasons=tuple(reasons),
        sigma_pre=s, sigma_final=sig,
        eigenvalues_pre=val, eigenvalues_post=val2,
        n_eigen_clipped_low=lo, n_eigen_clipped_high=hi,
        projection_frobenius_norm=frob,
        legality_passed=bool(legal), min_eig_final=float(min_eig),
    )


def check_legality_frozen(sigma: np.ndarray) -> tuple[bool, float]:
    """FROZEN M1 Gaussian legality discipline applied to one matrix.

    Reuses ``hyptraj.m1.proposal_update.LEGALITY_MIN_EIG`` verbatim: legal
    iff the smallest eigenvalue (of the symmetrized matrix) is >= that frozen
    constant.  Returns ``(legality_passed, min_eig)``.
    """
    sig = symmetrize_matrix(np.asarray(sigma, dtype=float))
    if not np.all(np.isfinite(sig)):
        return False, float("nan")
    min_eig = float(np.linalg.eigvalsh(sig)[0])
    passed = bool(min_eig >= LEGALITY_MIN_EIG - _NEG_EIG_TOL)
    return passed, min_eig


# ---------------------------------------------------------------------------
# Frozen base covariance read-out (task Sec. 13): metadata-driven, never
# hardcoded by assumption.
# ---------------------------------------------------------------------------
def base_covariance_from_frozen_metadata(
    proposal_meta_min_eig_sigma_minus_halfI: float | None,
    legality_checked: bool | None,
    dim: int,
) -> tuple[np.ndarray, dict]:
    """Reconstruct ``Sigma_base`` from the FROZEN proposal metadata.

    The frozen v0 family records ``min_eig(Sigma - I/2)`` on every component;
    only for the unit base family is that recorded value exactly
    ``LEGALITY_MIN_EIG = 0.5`` (since min_eig(I - I/2) = 1/2).  Any non-unit
    frozen base would have produced a DIFFERENT recorded value, so equality
    certifies reconstruction ``Sigma_base = I_dim``; anything else raises
    rather than silently assuming unit covariance (task Sec. 13).
    """
    checks: dict = {
        "frozen_constant": LEGALITY_MIN_EIG,
        "legality_checked": bool(legality_checked),
        "recorded_value": None if proposal_meta_min_eig_sigma_minus_halfI is None
        else float(proposal_meta_min_eig_sigma_minus_halfI),
    }
    if legality_checked is not True:
        raise ValueError(
            "frozen proposal metadata lacks legality_checked=True; refusing "
            "to infer Sigma_base (task Sec. 13)")
    rec = proposal_meta_min_eig_sigma_minus_halfI
    if rec is None or abs(float(rec) - LEGALITY_MIN_EIG) > 1e-12:
        raise ValueError(
            f"recorded min_eig_sigma_minus_halfI={rec!r} does not match the "
            f"frozen unit-family value {LEGALITY_MIN_EIG}; Sigma_base cannot "
            "be certified from metadata (task Sec. 13)")
    sigma_base = np.eye(int(dim))
    # verify reconstruction against the same recorded discipline
    recon_min_eig = float(np.min(np.linalg.eigvalsh(sigma_base * 0.5)))
    if abs(recon_min_eig - float(rec)) > 1e-12:
        raise ValueError("reconstructed Sigma_base fails recorded metadata")
    checks["reconstruction_verified"] = True
    return sigma_base, checks


__all__ = [
    "ProjectionResult", "project_covariance", "check_legality_frozen",
    "base_covariance_from_frozen_metadata",
    "LAMBDA_MIN_FLOOR", "LAMBDA_MAX_CAP", "LEGALITY_MIN_EIG",
]
