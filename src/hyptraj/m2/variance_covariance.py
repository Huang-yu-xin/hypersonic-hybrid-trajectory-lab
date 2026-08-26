"""M2 -- weighted variance-region covariance estimator (task Sec. 8-12).

Estimates, inside the frozen variance-mass HDR region ``L_eta,k`` of the
SELECTED mode ``k`` on the shared M1-D pilot:

    m_eta,k = E_{nu_V}[X | X in L_eta,k]                  (frozen mean; Sec. 8)
    C_eta,k = E_{nu_V}[(X - m_eta,k)(X - m_eta,k)^T | X in L_eta,k]   (Sec. 9)

The estimator is the VARIANCE-MASS conditional second central moment -- NOT a
plain sample covariance: every region sample carries its variance-mass weight
``w_tilde_i = 1_A(x_i) p(x_i)^2 / (q_t(x_i) r_i(x_i))`` computed under the
frozen semantic-corrected fixed-stratified pooling (each pilot sample keeps
its recorded sampling density ``r_i``).  Bessel correction is deliberately
NOT applied (the target is an empirical-measure second moment, task Sec. 9).

Region semantics reuse the FROZEN H3-3A helpers verbatim
(``variance_mass_hdr_indices`` + ``variance_mass_region_centroid``), including
the documented engineering fallback (HDR prefix < 2 samples -> all mode
samples, ``eta_used = 1.0``), so the M2 centroid is bit-identical to the
frozen M1-D variance HDR centroid.

Fires walls: this module accepts no benchmark-design reference data and no
final-evaluation samples.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.m1.proposal_update import (
    variance_mass_hdr_indices,
    variance_mass_region_centroid,
)
from hyptraj.m1.variance_measure import variance_mass_weights

# preregistered thresholds (configs/phase_m2/m2_covariance_v0.json /
# task Sec. 12): min region size d + 2 and min in-region ESS for the main
# covariance adaptation to act at all; otherwise HOLD_BASE_COVARIANCE.
ESS_V_MIN = 20.0


@dataclass(frozen=True)
class VarianceRegionStats:
    """Finite-sample description of one variance HDR region (Sec. 27 fields).

    ``cov`` is the raw weighted covariance (symmetrized); projection into the
    legality family is a separate downstream step (covariance_projection).
    """

    mode_id: str
    eta_requested: float
    eta_used: float                     # mirrors frozen fallback semantics
    region_indices: np.ndarray          # indices into z
    n_region: int
    centroid: np.ndarray                # frozen-computed variance-mass mean
    cov: np.ndarray                     # weighted second central moment
    weight_sum: float
    ess_v_region: float                 # Sec. 12 in-region ESS
    eigenvalues_raw: np.ndarray         # ascending eigvals of cov
    condition_raw: float                # max/min raw eigen ratio (guarded)
    finite: bool                        # no NaN/Inf anywhere

    @property
    def hold_required(self) -> tuple[bool, str]:
        """Preregistered HOLD rule (task Sec. 12): n_region >= d+2 AND
        ESS_V_region >= 20; shortfalls are HOLD behavior, not failures."""
        d = self.cov.shape[0]
        if not self.finite:
            return True, "non_finite_covariance"
        if self.n_region < d + 2:
            return True, f"n_region {self.n_region} < d+2 ({d + 2})"
        if self.weight_sum <= 0.0 or not np.isfinite(self.weight_sum):
            return True, "zero_variance_mass_in_region"
        if self.ess_v_region < ESS_V_MIN:
            return True, f"ESS_V_region {self.ess_v_region:.3g} < 20"
        return False, ""


def estimate_variance_region(
    z: np.ndarray,
    centers: np.ndarray,
    pi: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    labels: np.ndarray,
    nominal_topology: str,
    mode: str,
    eta: float = 0.8,
) -> VarianceRegionStats:
    """Weighted covariance of the frozen HDR region of ``mode`` (Sec. 9).

    Region selection is delegated VERBATIM to the frozen helper
    ``variance_mass_hdr_indices`` (smallest cumulative-variance-mass prefix of
    the ``rho_V``-ordered mode samples reaching ``eta``; NOT a raw quantile),
    with the frozen < 2-sample fallback to all mode samples.  The centroid is
    delegated VERBATIM to the frozen ``variance_mass_region_centroid``, so it
    equals the frozen M1-D variance HDR centroid bit-for-bit (mean lock,
    task Sec. 20).

    Returns :class:`VarianceRegionStats`; raises ``ValueError`` only when the
    frozen primitives raise (mode absent from pilot / zero mass).
    """
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    mask = labels == mode
    if mask.sum() == 0:
        raise ValueError(f"no pilot samples for mode {mode!r}")

    w_full = variance_mass_weights(
        z, centers, pi, logp, logr, mask.astype(float))

    idx_hdr, _achieved = variance_mass_hdr_indices(
        z, centers, pi, logp, logr, labels, nominal_topology, mode, eta)

    eta_used = eta
    idx = idx_hdr
    if idx.size < 2:                      # frozen engineering fallback
        idx = np.flatnonzero(mask)
        eta_used = 1.0

    centroid = variance_mass_region_centroid(z, w_full, idx)

    wr = w_full[idx]
    sw = float(np.sum(wr))
    Xc = z[idx] - centroid
    if sw > 0.0:
        cov = (Xc * wr[:, None]).T @ Xc / sw
    else:                                  # degenerate mass: flagged via HOLD
        cov = np.full((z.shape[1], z.shape[1]), np.nan)
    cov = symmetrize_matrix(cov)

    # in-region ESS (Sec. 12): weights renormalized INSIDE the region
    wb = wr / sw if sw > 0.0 else wr * np.nan
    denom = float(np.sum(wb ** 2)) if sw > 0.0 else np.nan
    ess_v = float(1.0 / denom) if denom and np.isfinite(denom) \
        and denom > 0 else float("nan")

    eig = np.linalg.eigvalsh(cov)
    finite = bool(np.all(np.isfinite(cov)) and np.all(np.isfinite(wr)))
    cond = float(eig[-1] / eig[0]) if (finite and eig[0] > 0.0) \
        else float("inf" if finite else "nan")

    return VarianceRegionStats(
        mode_id=str(mode),
        eta_requested=float(eta),
        eta_used=float(eta_used),
        region_indices=np.asarray(idx, dtype=int),
        n_region=int(idx.size),
        centroid=centroid,
        cov=cov,
        weight_sum=sw,
        ess_v_region=ess_v,
        eigenvalues_raw=eig,
        condition_raw=cond,
        finite=finite,
    )


def isotropic_scale_covariance(cov: np.ndarray) -> np.ndarray:
    """C1 pre-candidate ``s_V^2 I`` with ``s_V^2 = tr(C)/d`` (task Sec. 14 C1)."""
    cov = np.asarray(cov, dtype=float)
    d = cov.shape[0]
    s2 = float(np.trace(cov)) / d
    return s2 * np.eye(d)


def diagonal_covariance(cov: np.ndarray) -> np.ndarray:
    """C2 pre-candidate ``diag(C)`` (axis-wise scale only, task Sec. 14 C2)."""
    return np.diag(np.diag(np.asarray(cov, dtype=float)))


def shrunk_full_covariance(cov: np.ndarray, sigma_base: np.ndarray,
                           lam: float) -> np.ndarray:
    """C4 pre-candidate ``(1 - lam) Sigma_base + lam C`` (task Sec. 14 C4)."""
    if not (0.0 < lam < 1.0):
        raise ValueError(f"shrinkage lambda must lie in (0,1); got {lam}")
    return (1.0 - lam) * np.asarray(sigma_base, dtype=float) \
        + lam * np.asarray(cov, dtype=float)


def symmetrize_matrix(mat: np.ndarray) -> np.ndarray:
    """Numerical symmetrization ``M <- (M + M^T)/2`` (task Sec. 11)."""
    mat = np.asarray(mat, dtype=float)
    return 0.5 * (mat + mat.T)


__all__ = [
    "VarianceRegionStats", "estimate_variance_region", "ESS_V_MIN",
    "isotropic_scale_covariance", "diagonal_covariance",
    "shrunk_full_covariance", "symmetrize_matrix",
]
