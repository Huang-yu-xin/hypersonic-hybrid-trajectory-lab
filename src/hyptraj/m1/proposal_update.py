"""M1 -- proposal update actions: ADD_COMPONENT and UPDATE_WEIGHTS.

v0 action family (task Sec. 10, Sec. 13, Sec. 15):

- ADD_COMPONENT: center the new component at the eta-main variance-mass
  weighted centroid of the born mode within its eta region
  ``m_eta,k = E_{nu_V}[X | X in L_eta,k]``.  v0 fixes ``eta_main = 0.8``;
  covariance stays the frozen base (unit I in standardized space,
  task Sec. 8.3).  This is an M1 algorithm choice, not claimed optimal.
- UPDATE_WEIGHTS: with component means/covariances fixed, minimize the
  finite-sample ``M2_hat(pi)`` on the simplex via the frozen SLSQP solve of
  ``m1.mixture_weights`` (convex program -- theory-backed global minimum).

Legality gate (task Sec. 9): the proposal family keeps positive densities
everywhere (Gaussian components, unit base covariance), and every proposal
records ``legality_checked`` + ``min_eig_Sigma_minus_halfI``.  For unit
covariance ``min_eig(Sigma - I/2) = 1/2 > 0`` by construction; the record is
still written so no run may silently assume legality.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.m1.mixture_weights import (
    component_log_densities,
    mixture_log_density,
    optimize_mixture_weights,
)
from hyptraj.m1.variance_measure import variance_mass_weights

LEGALITY_MIN_EIG = 0.5  # min_eig(unit_I - 0.5*I) = 0.5


@dataclass(frozen=True)
class MixtureProposal:
    """v0 Gaussian mixture proposal ``q(z) = sum_j pi_j N(z | centers_j, I)``.

    Plain data holder with legality metadata; construction is validated.
    """

    centers: np.ndarray          # (J, d)
    weights: np.ndarray          # (J,) sum to 1
    component_mode_ids: tuple[str, ...] = ()   # topology mode each component targets
    legality_checked: bool = True
    min_eig_sigma_minus_halfI: float = LEGALITY_MIN_EIG

    def __post_init__(self) -> None:
        centers = np.asarray(self.centers, dtype=float)
        w = np.asarray(self.weights, dtype=float)
        if centers.ndim != 2 or w.ndim != 1 or centers.shape[0] != w.size:
            raise ValueError("centers / weights shape mismatch")
        if np.any(w < 0) or not np.isclose(w.sum(), 1.0, atol=1e-9):
            raise ValueError("weights must be non-negative and sum to 1")
        object.__setattr__(self, "centers", centers)
        object.__setattr__(self, "weights", w)

    @property
    def n_components(self) -> int:
        return self.centers.shape[0]

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        comp = rng.choice(self.n_components, size=n, p=self.weights)
        return self.centers[comp] + rng.standard_normal((n, self.centers.shape[1]))

    def log_density(self, z: np.ndarray) -> np.ndarray:
        return mixture_log_density(component_log_densities(z, self.centers), self.weights)


def variance_mass_hdr_indices(
    z: np.ndarray,
    centers: np.ndarray,
    pi: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    labels: np.ndarray,
    nominal_topology: str,
    mode: str,
    eta: float,
) -> tuple[np.ndarray, float]:
    """H3-3A finite-sample ``L_eta``: smallest variance-mass prefix (HDR).

    Frozen H3-3A semantics (``docs/phase_h/H3_3A_set_valued_variance_geometry.md``
    Sec. 3.1-3.2): "**绝不取'前 20% 样本'**——HDR region 是按 rho_L 排序后
    累计 omega^V 质量得到的最小 prefix".

    Implementation:

    1. order mode samples by ``log rho_V = 2 log p - log q_t`` DESCENDING
       (``np.argsort(kind="stable")`` -- deterministic tie handling);
    2. cumulative normalized variance mass ``w_tilde / sum(w_tilde)`` along
       that order (``w_tilde = 1_A p^2/(q_t r)``, task Sec. 7);
    3. ``L_eta = smallest prefix with cumulative mass >= eta``.

    Returns ``(indices_into_z, cumulative_mass_achieved)``.
    """
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    w = variance_mass_weights(
        z, centers, pi, logp, logr, (labels == mode).astype(float)
    )
    logq = mixture_log_density(component_log_densities(z, centers), pi)
    log_rho = 2.0 * np.asarray(logp, dtype=float) - logq
    sub = np.flatnonzero(labels == mode)                # mode samples only
    if sub.size == 0:
        raise ValueError(f"no pilot samples for mode {mode!r}")
    order = sub[np.argsort(-log_rho[sub], kind="stable")]  # rho desc, ties stable
    cum = np.cumsum(w[order])
    total = float(cum[-1])
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError(f"zero variance mass for mode {mode!r}")
    norm = cum / total
    k = int(np.searchsorted(norm, eta, side="left")) + 1  # first prefix >= eta
    k = min(k, order.size)
    achieved = float(norm[k - 1])
    return order[:k], achieved


def variance_mass_region_centroid(
    z: np.ndarray, w_full: np.ndarray, idx: np.ndarray
) -> np.ndarray:
    """Variance-mass weighted centroid of a region (H3-3A ``m_eta``)."""
    w = np.asarray(w_full, dtype=float)[idx]
    sw = float(w.sum())
    if sw <= 0.0:
        raise ValueError("zero variance mass in region")
    return np.sum(w[:, None] * np.asarray(z, dtype=float)[idx], axis=0) / sw


def eta_region_centroid(
    z: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    pi: np.ndarray,
    centers: np.ndarray,
    labels: np.ndarray,
    nominal_topology: str,
    mode: str,
    eta: float = 0.8,
) -> tuple[np.ndarray, float]:
    """Variance-mass weighted centroid ``m_eta,k`` (task Sec. 13, frozen
    H3-3A HDR semantics).

    ``L_eta,k`` = smallest prefix of the variance-mass-sorted pilot whose
    cumulative normalized mass reaches ``eta`` (NOT a raw quantile);
    ``m_eta,k`` = variance-mass weighted centroid inside that prefix.
    Returns ``(centroid, eta_used)``.

    Engineering fallback (M1 implementation detail, stated explicitly): when
    the HDR prefix holds fewer than 2 samples (a rare born mode with a thin
    pilot), the centroid falls back to ALL mode samples (``eta_used = 1.0``).
    """
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    mask = labels == mode
    if mask.sum() == 0:
        raise ValueError(f"no pilot samples for mode {mode!r}")
    w_full = variance_mass_weights(
        z, centers, pi, logp, logr, mask.astype(float)
    )
    idx, _achieved = variance_mass_hdr_indices(
        z, centers, pi, logp, logr, labels, nominal_topology, mode, eta
    )
    eta_used = eta
    if idx.size < 2:
        idx = np.flatnonzero(mask)
        eta_used = 1.0
    return variance_mass_region_centroid(z, w_full, idx), float(eta_used)


def add_component(
    proposal: MixtureProposal,
    new_center: np.ndarray,
    mode_id: str,
    pi_fallback: float = 0.5,
) -> MixtureProposal:
    """ADD_COMPONENT: append a unit-covariance component at ``new_center``.

    Weight initialization: old weights scaled jointly by ``(1 - alpha_new)``
    and the new component gets ``alpha_new``:

        pi_j^{new} = (1 - alpha_new) pi_j^{old}  (j = 1..J),  pi_{J+1} = alpha_new

    so ``sum(pi_new) == 1`` exactly and the OLD RELATIVE WEIGHT RATIOS ARE
    PRESERVED (a naive ``(1-a)/J`` renormalization breaks them for J >= 2).
    (Weight reallocation is refined by the UPDATE_WEIGHTS step that follows;
    this initial value only sets the SLSQP starting point.)
    """
    centers = np.vstack([proposal.centers, np.asarray(new_center, dtype=float).reshape(1, -1)])
    w = (1.0 - pi_fallback) * proposal.weights
    w = np.append(w, pi_fallback)
    return MixtureProposal(
        centers=centers,
        weights=w,
        component_mode_ids=proposal.component_mode_ids + (mode_id,),
    )


def update_weights(
    proposal: MixtureProposal,
    z: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    indicators: np.ndarray,
    floor: float = 0.0,
    maxiter: int = 500,
):
    """UPDATE_WEIGHTS: freeze means/covariances, optimize ``pi`` on the simplex
    (frozen SLSQP + analytic gradient).  Returns the updated proposal.

    ``z``/``logr`` come from the frozen pilot (two-phase protocol: weights are
    optimized on samples drawn from the previous proposal, never redrawn).
    """
    logq_ji = component_log_densities(z, proposal.centers)
    res = optimize_mixture_weights(
        logq_ji, logp, logr, indicators, pi0=proposal.weights,
        floor=floor, maxiter=maxiter,
    )
    if not res.success:
        raise RuntimeError(f"weight update failed: {res.message} (action HOLD)")
    return MixtureProposal(
        centers=proposal.centers,
        weights=res.weights,
        component_mode_ids=proposal.component_mode_ids,
    ), res


__all__ = [
    "MixtureProposal",
    "eta_region_centroid",
    "add_component",
    "update_weights",
    "LEGALITY_MIN_EIG",
]