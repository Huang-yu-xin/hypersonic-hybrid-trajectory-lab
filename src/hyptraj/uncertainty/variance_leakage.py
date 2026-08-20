"""H3-1 -- Variance leakage driven Geometry-IS validation (analysis core).

Pure-numpy analysis layer for the RareTopo H3-1 experiment.  It consumes
per-sample data already produced by the frozen hybrid simulator (topology
labels in a standardized Gaussian design space) and implements:

- single design-point Geometry-IS baseline estimation
  (``q(u) = N(u*, I)``, ``u* = -beta_eff * alpha_dir``)
- variance leakage per topology mode
  (``leak_k = E_q[w(u)^2 1_{A_k}]``, second-moment contribution of mode k)
- coverage analysis (proposal density share vs target share per mode)
- VRF / ESS metrics and correlation analysis
  (``corr(epsilon_geo, VRF)`` vs ``corr(leak, VRF)``)

Design-space convention (standardized ``z ~ N(0, I)``):

- physical perturbation ``delta_x = S_A * (alpha * z)``
- target density ``phi(z) = N(z | 0, I)``
- Geometry-IS proposal ``q(z) = N(z | z*, I)`` with ``z* = -beta_eff * alpha_dir``
  where ``beta_eff = beta_local_ref / alpha`` and ``alpha_dir`` is the frozen
  ML-B1 whitened design direction (``u_star``).
- event ``A = {Z(x) != Z0}`` decomposed into topology modes ``A_k = {Z = k}``.

This module never imports the simulator, ML-B1, or any frozen physics: it is
a pure analysis layer (git rule: ML-B1 implementation untouched).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DEFAULT_DIM = 4


# ---------------------------------------------------------------------------
# Proposal / weights
# ---------------------------------------------------------------------------
def design_point(beta_eff: float, alpha_dir: np.ndarray) -> np.ndarray:
    """``z* = -beta_eff * alpha_dir``: geometry design point (standardized)."""
    alpha_dir = np.asarray(alpha_dir, dtype=float)
    return float(-beta_eff) * alpha_dir


def log_importance_ratio(z: np.ndarray, z_star: np.ndarray) -> np.ndarray:
    """``log w(z) = log phi(z) - log q(z)`` for phi = q = N(., I) shifted."""
    z = np.asarray(z, dtype=float)
    z_star = np.asarray(z_star, dtype=float).reshape(1, -1)
    # log phi = -||z||^2/2 - d/2 log(2pi) ; log q = -||z - z*||^2/2 - const
    return -np.einsum("ni,ni->n", z, z) / 2.0 + np.einsum(
        "ni,ni->n", z - z_star, z - z_star
    ) / 2.0


def importance_weights(z: np.ndarray, z_star: np.ndarray) -> np.ndarray:
    """``w = phi(z)/q(z)`` (log-space, overflow safe)."""
    return np.exp(log_importance_ratio(np.asarray(z, dtype=float), z_star))


def gaussian_density(z: np.ndarray, mean: np.ndarray | None = None) -> np.ndarray:
    """Standardized Gaussian density ``N(z | mean, I)`` (vectorized)."""
    z = np.asarray(z, dtype=float)
    if z.ndim == 1:
        z = z.reshape(1, -1)
    m = np.zeros_like(z) if mean is None else np.asarray(mean, dtype=float).reshape(1, -1)
    d = z.shape[1]
    sq = np.sum((z - m) ** 2, axis=1)
    return (2.0 * math.pi) ** (-d / 2.0) * np.exp(-sq / 2.0)


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------
def mc_estimator(indicators: np.ndarray) -> tuple[float, float]:
    """Naive Monte Carlo probability and variance (Bernoulli)."""
    ind = np.asarray(indicators, dtype=float)
    n = ind.size
    if n < 2:
        raise ValueError("need at least 2 samples")
    p = float(ind.mean())
    var = float(p * (1.0 - p) / n)
    return p, var


def importance_estimator(
    weights: np.ndarray, indicators: np.ndarray
) -> tuple[float, float]:
    """IS probability estimate and second-moment based variance.

    ``var = (E_q[w^2 1_A] - p^2) / N`` -- the variance driven by the total
    leakage ``sum_k leak_k = E_q[w^2 1_A]``.
    """
    w = np.asarray(weights, dtype=float)
    ind = np.asarray(indicators, dtype=float)
    n = w.size
    if n < 2:
        raise ValueError("need at least 2 samples")
    if w.shape != ind.shape:
        raise ValueError("weights and indicators must share shape")
    p = float(np.mean(w * ind))
    second_moment = float(np.mean((w * ind) ** 2))
    var = max(0.0, (second_moment - p**2) / n)
    return p, var


def effective_sample_size(weights: np.ndarray) -> float:
    """ESS = (sum w)^2 / sum w^2 (Kong 1992), normalized to 1 at uniform."""
    w = np.asarray(weights, dtype=float)
    s = float(w.sum())
    if s <= 0.0:
        return 0.0
    return float(s * s / np.sum(w * w)) if np.sum(w * w) > 0.0 else 0.0


def vrf(p_mc: float, var_mc: float, p_is: float, var_is: float) -> float:
    """Variance reduction factor ``var_MC / var_IS`` (same N)."""
    if var_is <= 0.0:
        return float("inf")
    return var_mc / var_is


def total_leakage(weights: np.ndarray, indicators: np.ndarray) -> float:
    """``sum_k leak_k = E_q[w^2 1_A]`` (drives IS variance)."""
    w = np.asarray(weights, dtype=float)
    ind = np.asarray(indicators, dtype=float)
    return float(np.mean((w * ind) ** 2))


# ---------------------------------------------------------------------------
# Mode decomposition / leakage per topology mode
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModeLeakage:
    """Variance leakage contribution of one topology mode ``A_k = {Z = k}``."""

    mode_index: int
    mode_id: str
    transition_topology: str
    transition_channel: str | None
    probability: float            # P_k = P(Z = k)  (MC marginal estimate)
    conditional_probability: float  # P(Z = k | Z != Z0)  (MC)
    mode_beta: float              # -alpha_dir^T u_bar_k (typical boundary distance)
    mode_design_point: tuple[float, ...]  # u_k* = -mode_beta * alpha_dir
    mode_direction: tuple[float, ...]     # alpha_dir (shared, v1)
    proposal_density: float       # q(u_k*) = N(u_k* | z*, I)
    leak: float                   # leak_k = (1/N) sum_{i in A_k} w_i^2
    leak_fraction: float          # leak_k / sum_j leak_j
    coverage_score: float         # Q(A_k)/Phi(A_k) = P_k^q / P_k
    n_events: int


@dataclass(frozen=True)
class ConfigResult:
    """One Geometry-IS baseline config (one anchor / alpha)."""

    config_id: str
    level: str
    anchor: str | None
    alpha: float
    nominal_topology: str
    beta_eff: float
    design_point: tuple[float, ...]
    epsilon_geo: float
    n_mc: int
    n_is: int
    p_mc: float
    p_is: float
    var_mc: float
    var_is: float
    ess: float
    vrf: float
    total_leak: float
    accepted_rare_events: int
    modes: tuple[ModeLeakage, ...] = field(default_factory=tuple)


def decompose_modes(
    z_q: np.ndarray,
    w_q: np.ndarray,
    labels_q: np.ndarray,
    nominal_topology: str,
    alpha_dir: np.ndarray,
    z_star: np.ndarray,
    p_k_mc: dict[str, float] | None = None,
    p_total_mc: float | None = None,
    transition_channel: str | None = "atmosphere_exit",
) -> list[ModeLeakage]:
    """Decompose the rare event into topology modes and compute ``leak_k``.

    ``leak_k = (1/N) sum_{i: z_i in A_k} w_i^2`` (proposal samples), the
    second-moment contribution of mode ``k`` to the IS variance.  Target
    probabilities ``P_k = P(Z = k)`` come from the MC pass (``p_k_mc``);
    proposal shares ``P_k^q`` come from the proposal pass; coverage =
    ``P_k^q / P_k``.
    """
    z_q = np.asarray(z_q, dtype=float)
    w_q = np.asarray(w_q, dtype=float)
    labels_q = np.asarray(labels_q)
    alpha_dir = np.asarray(alpha_dir, dtype=float)
    z_star = np.asarray(z_star, dtype=float)
    if z_q.shape[0] != w_q.size or z_q.shape[0] != labels_q.size:
        raise ValueError("z_q / w_q / labels_q length mismatch")
    if z_q.shape[1] != alpha_dir.size:
        raise ValueError("z_q dim mismatch with alpha_dir")

    transition = labels_q != nominal_topology
    total_leak = float(np.mean((w_q * transition) ** 2))
    mode_list = sorted(set(labels_q[transition].tolist()))
    modes_out: list[ModeLeakage] = []

    for k, topo in enumerate(mode_list):
        mask = transition & (labels_q == topo)
        n_ev = int(mask.sum())
        p_k_q = float(mask.mean())
        p_k_target = float((p_k_mc or {}).get(str(topo), float("nan")))
        p_cond = p_k_target / p_total_mc if p_total_mc and p_total_mc > 0.0 else float("nan")
        leak_k = float(np.sum(w_q[mask] ** 2) / w_q.size) if n_ev else 0.0
        frac = leak_k / total_leak if total_leak > 0.0 else 0.0
        # weighted mode center (in z space)
        sw = float(w_q[mask].sum())
        u_bar = (
            np.sum(w_q[mask, None] * z_q[mask], axis=0) / sw if sw > 0.0
            else np.zeros(z_q.shape[1])
        )
        mode_beta = float(-np.dot(alpha_dir, u_bar))
        u_k_star = design_point(mode_beta, alpha_dir)
        q_density = float(
            gaussian_density(u_k_star.reshape(1, -1), mean=z_star)[0]
        )
        coverage = p_k_q / p_k_target if p_k_target > 0.0 else float("inf")
        modes_out.append(
            ModeLeakage(
                mode_index=k,
                mode_id=f"mode{k}",
                transition_topology=str(topo),
                transition_channel=transition_channel,
                probability=p_k_target,
                conditional_probability=p_cond,
                mode_beta=float(mode_beta),
                mode_design_point=tuple(float(v) for v in u_k_star),
                mode_direction=tuple(float(v) for v in alpha_dir),
                proposal_density=q_density,
                leak=leak_k,
                leak_fraction=frac,
                coverage_score=coverage,
                n_events=n_ev,
            )
        )
    return modes_out


# ---------------------------------------------------------------------------
# Correlation analysis (Task 5)
# ---------------------------------------------------------------------------
def pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size != y.size or x.size < 2:
        return float("nan")
    xm, ym = x - x.mean(), y - y.mean()
    denom = float(np.sqrt(np.sum(xm**2) * np.sum(ym**2)))
    if denom == 0.0:
        return float("nan")
    return float(np.sum(xm * ym) / denom)


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    from scipy.stats import rankdata

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size != y.size or x.size < 2:
        return float("nan")
    return pearson(rankdata(x), rankdata(y))


def correlation_analysis(configs: list[ConfigResult]) -> dict:
    """``corr(epsilon_geo, VRF)`` and ``corr(leak, VRF)`` across configs."""
    n = len(configs)
    if n < 2:
        return {"n_configs": n, "eps_geo_vs_vrf": float("nan"), "leak_vs_vrf": float("nan")}
    eps = np.array([c.epsilon_geo for c in configs], dtype=float)
    leak = np.array([c.total_leak for c in configs], dtype=float)
    vrf = np.array([c.vrf for c in configs], dtype=float)
    return {
        "n_configs": n,
        "eps_geo_vs_vrf": pearson(eps, vrf),
        "leak_vs_vrf": pearson(leak, vrf),
        "eps_geo_vs_vrf_spearman": spearman(eps, vrf),
        "leak_vs_vrf_spearman": spearman(leak, vrf),
    }
