"""H3-2 -- Leakage-aware adaptive Geometry-IS design (analysis core).

Extends the H3-1 leakage analysis with an adaptive mixture proposal:

- Stage A: leakage-aware topology mode discovery
  (``leak_k = (1/N) sum_i w_i^2 1(Z_i = k)``, ``leak_fraction_k``,
  ``coverage_score`` -- reuses ``variance_leakage.decompose_modes``).
- Stage B: adaptive mixture Geometry-IS
  ``q_mix(u) = sum_k pi_k q_k(u)``, ``q_k = N(u_k*, I)``,
  ``u_k* = -beta_k alpha_k`` (mode design points from discovery; ML-B1
  frozen geometry reused, never modified).
- Stage C: validation -- single design-point baseline vs mixture:
  P-hat / variance / VRF / leakage reduction / per-mode coverage & ESS.

Weight strategies compared: ``pi_k = P_k`` (probability), ``1/K``
(uniform), ``propto sqrt(L_k)`` (leakage-aware), and
``propto P_k^0.5 L_k^0.5`` (geometric mean).

Design space: standardized ``z ~ N(0, I)``, ``delta_x = S_A (alpha_p z)``
(identical to H3-1).  Pure-numpy/scipy analysis layer -- never imports
the simulator or ML-B1 internals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.uncertainty.variance_leakage import (
    decompose_modes,
    design_point,
    importance_estimator,
    mc_estimator,
    pearson,
    spearman,
)

DEFAULT_DIM = 4


# ---------------------------------------------------------------------------
# Gaussian mixture proposal (isotropic covariance, v1)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GaussianMixture:
    """Mixture ``q_mix(u) = sum_k pi_k N(u | u_k*, I)`` (v1, unit covariance)."""

    design_points: np.ndarray          # (K, d)
    weights: np.ndarray                # (K,) sum to 1

    def __post_init__(self) -> None:
        dp = np.asarray(self.design_points, dtype=float)
        w = np.asarray(self.weights, dtype=float)
        if dp.ndim != 2:
            raise ValueError(f"design_points must be 2-D; got {dp.ndim}-D")
        if dp.shape[0] != w.size:
            raise ValueError("design_points / weights count mismatch")
        if w.ndim != 1 or np.any(w < 0) or not np.isclose(w.sum(), 1.0, atol=1e-9):
            raise ValueError("weights must be non-negative and sum to 1")
        object.__setattr__(self, "design_points", dp)
        object.__setattr__(self, "weights", w)

    @property
    def n_components(self) -> int:
        return self.design_points.shape[0]

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        """Sample ``n`` points from the mixture (component-first)."""
        d = self.design_points.shape[1]
        comp = rng.choice(self.n_components, size=n, p=self.weights)
        r = rng.standard_normal((n, d))
        return self.design_points[comp] + r

    def log_density(self, z: np.ndarray) -> np.ndarray:
        """``log q_mix(z)`` (log-sum-exp, overflow safe)."""
        z = np.asarray(z, dtype=float)
        if z.ndim == 1:
            z = z.reshape(1, -1)
        d = z.shape[1]
        sq = np.sum(
            (z[:, None, :] - self.design_points[None, :, :]) ** 2, axis=2
        )  # (N, K)
        logk = -sq / 2.0 - (d / 2.0) * np.log(2.0 * np.pi)
        logw = np.log(self.weights)[None, :]
        return np.log(np.sum(np.exp(logk + logw), axis=1))

    def density(self, z: np.ndarray) -> np.ndarray:
        return np.exp(self.log_density(z))


def gaussian_phi(z: np.ndarray) -> np.ndarray:
    """Standard normal target density ``phi(z) = N(z | 0, I)``."""
    z = np.asarray(z, dtype=float)
    if z.ndim == 1:
        z = z.reshape(1, -1)
    d = z.shape[1]
    return (2.0 * np.pi) ** (-d / 2.0) * np.exp(-np.sum(z**2, axis=1) / 2.0)


def mixture_importance_weights(z: np.ndarray, mix: GaussianMixture) -> np.ndarray:
    """``w = phi(z) / q_mix(z)`` (log-space, overflow safe)."""
    z = np.asarray(z, dtype=float)
    if z.ndim == 1:
        z = z.reshape(1, -1)
    d = z.shape[1]
    log_phi = -np.sum(z**2, axis=1) / 2.0 - (d / 2.0) * np.log(2.0 * np.pi)
    return np.exp(log_phi - mix.log_density(z))


# ---------------------------------------------------------------------------
# Stage A -- leakage-aware mode discovery (uses H3-1 decomposition)
# ---------------------------------------------------------------------------
def discover_modes(
    z_q: np.ndarray,
    w_q: np.ndarray,
    labels_q: np.ndarray,
    nominal_topology: str,
    alpha_dir: np.ndarray,
    z_star: np.ndarray,
    p_k_mc: dict[str, float] | None = None,
    p_total_mc: float | None = None,
    transition_channel: str | None = "atmosphere_exit",
    min_events: int = 0,
):
    """Discover topology modes and their leakage (Stage A).

    Wraps ``variance_leakage.decompose_modes`` and filters modes with
    ``n_events < min_events`` (too few proposal samples to trust).
    """
    modes = decompose_modes(
        z_q, w_q, labels_q, nominal_topology, alpha_dir, z_star,
        p_k_mc=p_k_mc, p_total_mc=p_total_mc,
        transition_channel=transition_channel,
    )
    return [m for m in modes if m.n_events >= min_events]


def mixture_from_modes(modes, weights: np.ndarray, dim: int = DEFAULT_DIM) -> GaussianMixture:
    """Build the mixture proposal from discovered mode design points."""
    if not modes:
        raise ValueError("no modes to build a mixture from")
    dps = np.array([m.mode_design_point for m in modes], dtype=float)
    if dps.ndim == 1:
        dps = dps.reshape(1, -1)
    w = np.asarray(weights, dtype=float)
    if w.size != dps.shape[0]:
        raise ValueError("weights / modes count mismatch")
    w = w / w.sum()
    return GaussianMixture(design_points=dps, weights=w)


# ---------------------------------------------------------------------------
# Weight strategies (Stage B)
# ---------------------------------------------------------------------------
def weight_strategies(p_k: np.ndarray, leak_k: np.ndarray) -> dict[str, np.ndarray]:
    """Proposal weight strategies for the mixture components.

    ``p_k``: mode probabilities ``P_k = P(Z = k)``; ``leak_k``: mode leak.
    Returns normalized weight vectors keyed by strategy name.
    """
    p_k = np.asarray(p_k, dtype=float)
    leak_k = np.asarray(leak_k, dtype=float)
    k = p_k.size
    if k == 0:
        return {}
    out: dict[str, np.ndarray] = {}

    def norm(w: np.ndarray) -> np.ndarray:
        s = float(w.sum())
        return w / s if s > 0 else np.full(k, 1.0 / k)

    out["probability"] = norm(p_k)
    out["uniform"] = np.full(k, 1.0 / k)
    out["leak_power1"] = norm(leak_k)
    out["sqrt_leak"] = norm(np.sqrt(np.maximum(leak_k, 0.0)))
    out["p05_l05"] = norm(np.sqrt(np.maximum(p_k, 0.0) * np.maximum(leak_k, 0.0)))
    return out


def leakage_power_weights(leak_k: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """``pi_k propto L_k^alpha`` (leakage-aware, parameterized)."""
    leak_k = np.asarray(leak_k, dtype=float)
    w = np.maximum(leak_k, 0.0) ** alpha
    s = float(w.sum())
    return w / s if s > 0 else np.full(leak_k.size, 1.0 / leak_k.size)


def hybrid_power_weights(
    p_k: np.ndarray, leak_k: np.ndarray, gamma: float = 0.5
) -> np.ndarray:
    """``pi_k propto P_k^gamma L_k^(1-gamma)`` (hybrid, parameterized)."""
    p_k = np.asarray(p_k, dtype=float)
    leak_k = np.asarray(leak_k, dtype=float)
    w = np.maximum(p_k, 0.0) ** gamma * np.maximum(leak_k, 0.0) ** (1.0 - gamma)
    s = float(w.sum())
    return w / s if s > 0 else np.full(p_k.size, 1.0 / p_k.size)


def per_mode_ess(
    z_q: np.ndarray, w_q: np.ndarray, labels_q: np.ndarray, nominal_topology: str
) -> dict[str, float]:
    """Effective sample size restricted to each topology mode."""
    labels_q = np.asarray(labels_q)
    w_q = np.asarray(w_q, dtype=float)
    out: dict[str, float] = {}
    for k in sorted(set(labels_q.tolist())):
        if k == nominal_topology:
            continue
        mask = labels_q == k
        w = w_q[mask]
        s = float(w.sum())
        out[str(k)] = float(s * s / np.sum(w * w)) if np.sum(w * w) > 0 else 0.0
    return out


def leakage_reduction_ratio(single_total: float, adaptive_total: float) -> float:
    """``sum_k L_k^adaptive / sum_k L_k^single`` (< 1 means leakage reduced)."""
    if single_total <= 0.0:
        return float("nan")
    return adaptive_total / single_total


def mixture_vrf(
    p_mc: float, var_mc: float, p_mix: float, var_mix: float
) -> float:
    """VRF of the mixture estimator vs MC (same N)."""
    if var_mix <= 0.0:
        return float("inf")
    return var_mc / var_mix


__all__ = [
    "GaussianMixture",
    "gaussian_phi",
    "mixture_importance_weights",
    "discover_modes",
    "mixture_from_modes",
    "weight_strategies",
    "leakage_power_weights",
    "hybrid_power_weights",
    "per_mode_ess",
    "leakage_reduction_ratio",
    "mixture_vrf",
]
