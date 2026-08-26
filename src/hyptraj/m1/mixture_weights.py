"""M1-1 -- Fixed-component mixture-weight convexity machinery.

Pure numpy/scipy analysis layer for the M1 mixture-weight theory task
(``docs/phase_m1/M1_Theory_Mixture_Weight_Convexity.md``, task Sec. 14/15/29.4).

Guarantees provided by the module:

- ``m2_hat`` is an UNBIASED finite-sample estimate of
  ``M2(pi) = int_A p(x)^2 / q_pi(x) dx`` for ANY sampling density ``r`` that is
  fixed at draw time (each sample keeps its own ``r_i``; mixed pilots may be
  pooled, see theory doc Sec. 9.1);
- ``m2_gradient`` / ``m2_hessian`` are the analytic (T1)/(T2) plug-in
  estimators (unbiased for the true derivatives for fixed ``r``);
- for a FIXED sample set the empirical objective 1/[(sum_j pi_j q_j(x_i))] is
  convex in ``pi`` (positive constant / positive affine), so the SLSQP solve
  reaches the global minimum of the empirical objective -- init independence
  is theory-backed, not numerical luck (theory doc Sec. 9.2);
- component densities are the v0 frozen family ``q_j = N(m_j, I)`` in the
  standardized ``z`` space (H3 convention; covariance adaptation deferred,
  task Sec. 8.3).

The v0 optimizer is frozen to SLSQP (task Sec. 15) with the analytic
gradient; a weight floor is supported and must be explicitly declared by the
caller (config ``mixture_weights.floor``).  Non-convergence / no-event /
non-finite objective are surfaced as failures for the caller to map to the
HOLD action (task Sec. 16) -- never silently reported as success.

This module never imports the simulator or any frozen physics (same rule as
the H3 analysis layers).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

# ---------------------------------------------------------------------------
# Weight validation (task Sec. 29.1)
# ---------------------------------------------------------------------------
def validate_weights(pi: np.ndarray, floor: float = 0.0) -> np.ndarray:
    """Validate a weight vector: 1-D, ``pi_j >= floor``, ``sum(pi) == 1``."""
    pi = np.asarray(pi, dtype=float)
    if pi.ndim != 1:
        raise ValueError(f"weights must be 1-D; got {pi.ndim}-D")
    if pi.size == 0:
        raise ValueError("weights must not be empty")
    if np.any(pi < floor - 1e-12):
        raise ValueError(f"weights below declared floor {floor}: {pi}")
    if not np.isclose(pi.sum(), 1.0, atol=1e-9):
        raise ValueError(f"weights must sum to 1; got sum={pi.sum():.12g}")
    return pi


# ---------------------------------------------------------------------------
# Mixture densities (frozen unit base covariance, standardized z-space)
# ---------------------------------------------------------------------------
def component_log_densities(z: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """``(N, K)`` matrix ``log q_j(z_i)`` with ``q_j = N(centers_j, I)``.

    ``z``: ``(N, d)`` points; ``centers``: ``(K, d)`` component means.
    """
    z = np.asarray(z, dtype=float)
    centers = np.asarray(centers, dtype=float)
    if z.ndim != 2 or centers.ndim != 2:
        raise ValueError("z and centers must be 2-D")
    if z.shape[1] != centers.shape[1]:
        raise ValueError("z dim mismatch with centers")
    d = z.shape[1]
    sq = np.sum((z[:, None, :] - centers[None, :, :]) ** 2, axis=2)  # (N, K)
    return -sq / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def mixture_log_density(logq_ji: np.ndarray, pi: np.ndarray) -> np.ndarray:
    """``(N,)`` ``log q_pi(z_i)`` via log-sum-exp (overflow safe)."""
    logq_ji = np.asarray(logq_ji, dtype=float)
    if logq_ji.ndim != 2:
        raise ValueError("logq_ji must be (N, K)")
    pi = validate_weights(pi, floor=0.0)
    if logq_ji.shape[1] != pi.size:
        raise ValueError("logq_ji / weights component count mismatch")
    # pi_j = 0 -> log -> -inf: logsumexp handles it (exp(-inf) = 0)
    with np.errstate(divide="ignore"):
        return logsumexp(logq_ji + np.log(pi)[None, :], axis=1)


# ---------------------------------------------------------------------------
# Finite-sample second-moment objective and its analytic derivatives
# ---------------------------------------------------------------------------
def _validate_inputs(logq_ji, logp, logr, indicators) -> tuple[np.ndarray, ...]:
    logq_ji = np.asarray(logq_ji, dtype=float)
    logp = np.asarray(logp, dtype=float).reshape(-1)
    logr = np.asarray(logr, dtype=float).reshape(-1)
    indicators = np.asarray(indicators, dtype=float).reshape(-1)
    n = logp.size
    if logq_ji.ndim != 2 or logq_ji.shape[0] != n:
        raise ValueError("logq_ji must be (N, K) with N = logp.size")
    if logr.size != n or indicators.size != n:
        raise ValueError("logp / logr / indicators length mismatch")
    n_events = int(np.count_nonzero(indicators))
    if n_events == 0:
        raise ValueError("no event samples: objective undefined (HOLD per task Sec. 16)")
    return logq_ji, logp, logr, indicators, n_events


def m2_hat(
    logq_ji: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    indicators: np.ndarray,
    pi: np.ndarray,
) -> float:
    """Unbiased ``M2_hat(pi) = (1/N) sum_i 1_A(x_i) p(x_i)^2 / (q_pi r_i)``.

    All quantities in log space; ``r_i`` is the declared sampling density of
    sample ``i`` and must be FIXED (independent of ``pi``) -- the two-phase
    protocol of task Sec. 18.
    """
    logq_ji, logp, logr, indicators, _ = _validate_inputs(logq_ji, logp, logr, indicators)
    logq_pi = mixture_log_density(logq_ji, pi)
    term = np.exp(2.0 * logp - logq_pi - logr)  # p^2 / (q_pi * r)
    return float(np.mean(indicators * term))


def m2_gradient(
    logq_ji: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    indicators: np.ndarray,
    pi: np.ndarray,
) -> np.ndarray:
    """Analytic gradient ``-(1/N) sum_i 1_A p^2 q_j / (q_pi^2 r_i)`` (T1)."""
    logq_ji, logp, logr, indicators, _ = _validate_inputs(logq_ji, logp, logr, indicators)
    logq_pi = mixture_log_density(logq_ji, pi)
    base = 2.0 * logp - logr - 2.0 * logq_pi             # (N,)
    g = np.exp(base[:, None] + logq_ji)                  # (N, K) p^2 q_j / (q_pi^2 r)
    return -np.mean(indicators[:, None] * g, axis=0)     # -(1/N) sum_i 1_A (...)


def m2_hessian(
    logq_ji: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    indicators: np.ndarray,
    pi: np.ndarray,
) -> np.ndarray:
    """Analytic Hessian ``2*(1/N) sum_i 1_A p^2 q_j q_l / (q_pi^3 r_i)`` (T2)."""
    logq_ji, logp, logr, indicators, _ = _validate_inputs(logq_ji, logp, logr, indicators)
    n = logq_ji.shape[0]
    logq_pi = mixture_log_density(logq_ji, pi)
    logw = 2.0 * logp - logr - 3.0 * logq_pi                 # (N,) log w_i
    a = np.exp(logw[:, None] + logq_ji) * indicators[:, None]  # (N, K) w_i q_j(x_i)
    q = np.exp(logq_ji)                                       # (N, K) q_j(x_i)
    # (a^T q)_{j,l} = sum_i w_i q_j(x_i) q_l(x_i)
    return 2.0 * (a.T @ q) / float(n)


# ---------------------------------------------------------------------------
# KKT residue (theory doc Sec. 8)
# ---------------------------------------------------------------------------
def kkt_residue(
    gradient: np.ndarray, pi: np.ndarray, floor: float = 0.0
) -> float:
    """Max violation of the simplex KKT conditions at (pi, g).

    Interior components (``pi_j > floor``) must share a common gradient value
    ``rho``; floor-active components must satisfy ``g_j >= rho``.
    """
    g = np.asarray(gradient, dtype=float)
    pi = np.asarray(pi, dtype=float)
    interior = pi > floor + 1e-10
    if np.any(interior):
        rho = float(np.mean(g[interior]))
        res = np.max(np.abs(g[interior] - rho))
        floor_active = ~interior
        if np.any(floor_active):
            res = max(res, float(np.max(np.maximum(0.0, rho - g[floor_active]))))
        return float(res)
    # all components at the floor: rho is unconstrained; use min g as rho
    rho = float(np.min(g))
    return float(np.max(np.maximum(0.0, rho - g)))


# ---------------------------------------------------------------------------
# Frozen v0 optimizer: SLSQP with analytic gradient
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WeightOptimizeResult:
    """Outcome of one mixture-weight solve (task Sec. 15 / 31)."""

    success: bool
    message: str
    weights: np.ndarray
    objective_init: float
    objective_final: float
    n_iter: int
    kkt_residue: float
    n_samples: int
    n_events: int
    gradient_norm_final: float


def optimize_mixture_weights(
    logq_ji: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    indicators: np.ndarray,
    pi0: np.ndarray | None = None,
    floor: float = 0.0,
    ftol: float = 1e-12,
    maxiter: int = 500,
) -> WeightOptimizeResult:
    """Minimize the empirical ``M2_hat(pi)`` on the simplex via SLSQP.

    ``pi0`` defaults to uniform.  The analytic gradient (T1) is passed as the
    SLSQP ``jac``.  Constraints: ``sum(pi) == 1`` (equality) and
    ``floor <= pi_j <= 1`` (bounds).  On failure (no events, non-finite
    objective, solver non-convergence) ``success=False`` -- the caller maps
    this to action HOLD (task Sec. 16).
    """
    logq_ji_arr, logp_arr, logr_arr, ind_arr, n_events = _validate_inputs(
        logq_ji, logp, logr, indicators
    )
    k = logq_ji_arr.shape[1]
    if pi0 is None:
        pi0 = np.full(k, 1.0 / k)
    pi0 = validate_weights(pi0, floor=floor)

    def _obj(pi: np.ndarray) -> float:
        return m2_hat(logq_ji_arr, logp_arr, logr_arr, ind_arr, pi)

    def _jac(pi: np.ndarray) -> np.ndarray:
        return m2_gradient(logq_ji_arr, logp_arr, logr_arr, ind_arr, pi)

    obj0 = float(_obj(pi0))
    if not np.isfinite(obj0):
        return WeightOptimizeResult(
            success=False, message="initial objective non-finite",
            weights=pi0, objective_init=obj0, objective_final=obj0,
            n_iter=0, kkt_residue=float("nan"),
            n_samples=logq_ji_arr.shape[0], n_events=n_events,
            gradient_norm_final=float("nan"),
        )

    bounds = [(floor, 1.0)] * k
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    res = minimize(
        _obj, pi0, jac=_jac, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"maxiter": maxiter, "ftol": ftol, "disp": False},
    )
    w = np.asarray(res.x, dtype=float)
    obj_final = float(_obj(w)) if res.success else float("nan")
    if res.success:
        g = m2_gradient(logq_ji_arr, logp_arr, logr_arr, ind_arr, w)
        kkt = kkt_residue(g, w, floor=floor)
        gn = float(np.linalg.norm(g))
    else:
        kkt, gn = float("nan"), float("nan")
    message = str(res.message).strip()
    return WeightOptimizeResult(
        success=bool(res.success),
        message=message or "SLSQP",
        weights=w,
        objective_init=obj0,
        objective_final=obj_final,
        n_iter=int(res.nit),
        kkt_residue=kkt,
        n_samples=logq_ji_arr.shape[0],
        n_events=n_events,
        gradient_norm_final=gn,
    )


__all__ = [
    "validate_weights",
    "component_log_densities",
    "mixture_log_density",
    "m2_hat",
    "m2_gradient",
    "m2_hessian",
    "kkt_residue",
    "optimize_mixture_weights",
    "WeightOptimizeResult",
]