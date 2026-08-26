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
) -> np.ndarray:
    """Variance-mass weighted centroid ``m_eta,k`` (task Sec. 13).

    Computed over the born mode's samples restricted to the eta region:
    ``L_eta,k = {x in z : label = mode, log rho_V(x) >= q_eta(region)}`` where
    ``rho_V = p^2 / q_t`` and ``q_eta`` is the eta-quantile of ``log rho_V``
    within the mode.  Uses normalized variance-mass weights (task Sec. 7).
    """
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    mask = labels == mode
    if mask.sum() == 0:
        raise ValueError(f"no pilot samples for mode {mode!r}")
    logq = mixture_log_density(component_log_densities(z, centers), pi)
    log_rho = 2.0 * np.asarray(logp, dtype=float) - logq
    thr = np.quantile(log_rho[mask], eta)
    region = mask & (log_rho >= thr)
    if region.sum() < 2:
        raise ValueError(f"eta={eta} region of mode {mode!r} has < 2 samples")
    w = variance_mass_weights(z, centers, pi, logp, logr, region.astype(float))
    sw = float(w.sum())
    if sw <= 0.0:
        raise ValueError(f"zero variance mass in mode {mode!r} region")
    return np.sum(w[:, None] * z, axis=0) / sw


def add_component(
    proposal: MixtureProposal,
    new_center: np.ndarray,
    mode_id: str,
    pi_fallback: float = 0.5,
) -> MixtureProposal:
    """ADD_COMPONENT: append a unit-covariance component at ``new_center``.

    New mixture weight: v0 naive split -- half of the uniform share is moved
    to the new component when the proposal is single-component; otherwise the
    new weight starts at ``pi_fallback / J_new`` and the rest is renormalized.
    (Weight reallocation is refined by the UPDATE_WEIGHTS step that follows;
    the initial value only sets the SLSQP starting point.)
    """
    centers = np.vstack([proposal.centers, np.asarray(new_center, dtype=float).reshape(1, -1)])
    j_new = centers.shape[0]
    w = proposal.weights * (1.0 - pi_fallback) / proposal.n_components
    w = np.append(w, pi_fallback)
    w = w / w.sum()
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