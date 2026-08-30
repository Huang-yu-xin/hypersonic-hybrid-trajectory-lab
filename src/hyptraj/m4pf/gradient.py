"""Pure matrix arithmetic for the M4-PF objective gradient.

No function in this module draws samples or knows about a trajectory/event
simulator. Finite-sample functions consume already-recorded arrays; Gaussian
helpers are closed-form deterministic algebra fixtures.
"""

from __future__ import annotations

import math

import numpy as np


def _symmetric(matrix: np.ndarray) -> np.ndarray:
    a = np.asarray(matrix, dtype=float)
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise ValueError("matrix must be square")
    return 0.5 * (a + a.T)


def _spd_eigh(matrix: np.ndarray, floor: float = 0.0) \
        -> tuple[np.ndarray, np.ndarray]:
    vals, vecs = np.linalg.eigh(_symmetric(matrix))
    if not np.all(np.isfinite(vals)) or float(vals.min()) <= float(floor):
        raise ValueError("matrix is not strictly SPD")
    return vals, vecs


def matrix_gradient_estimate(
    variance_mass: np.ndarray,
    responsibility: np.ndarray,
    whitened: np.ndarray,
) -> dict:
    """Estimate ``G=(M2/2) sum_i abar_i r_i (I-z_i z_i')``.

    ``variance_mass`` is the existing M3 per-sample ``a_i`` array,
    ``responsibility`` is ``rhat_ki`` and ``whitened`` contains rows ``z_i``.
    The normalization exactly matches ``scalar_gradient_estimate``.
    """
    a = np.asarray(variance_mass, dtype=float).reshape(-1)
    r = np.asarray(responsibility, dtype=float).reshape(-1)
    z = np.asarray(whitened, dtype=float)
    if z.ndim != 2 or z.shape[0] != a.size or r.size != a.size:
        raise ValueError("sample array lengths do not match")
    if a.size == 0:
        raise ValueError("at least one sample is required")
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(r)) and
            np.all(np.isfinite(z))):
        raise ValueError("inputs must be finite")
    if np.any(a < 0.0) or np.any(r < 0.0):
        raise ValueError("variance mass and responsibility must be nonnegative")
    mass = float(a.sum())
    if mass <= 0.0:
        raise ValueError("variance mass must be positive")
    m2 = mass / a.size
    abar = a / mass
    wr = abar * r
    mu_r = float(wr.sum())
    scatter_z = np.einsum("n,ni,nj->ij", wr, z, z)
    gradient = 0.5 * m2 * (mu_r * np.eye(z.shape[1]) - scatter_z)
    gradient = _symmetric(gradient)
    component_weights = a * r
    component_total = float(component_weights.sum())
    ess = (1.0 / float(np.sum((component_weights / component_total) ** 2))
           if component_total > 0.0 else float("nan"))
    return {
        "M2_hat": float(m2),
        "responsibility_mass": mu_r,
        "scatter_whitened": scatter_z,
        "gradient_matrix": gradient,
        "scalar_trace": float(np.trace(gradient)),
        "ESS_gradient": float(ess),
        "n": int(a.size),
    }


def directional_gradient(gradient: np.ndarray, direction: np.ndarray) -> float:
    """Frobenius directional derivative ``<G,B>_F``."""
    g = _symmetric(gradient)
    b = _symmetric(direction)
    if g.shape != b.shape:
        raise ValueError("gradient and direction shapes differ")
    return float(np.sum(g * b))


def rank_truncate(gradient: np.ndarray, rank: int) -> dict:
    """Keep eigenpairs with largest absolute eigenvalues."""
    g = _symmetric(gradient)
    if not 1 <= int(rank) <= g.shape[0]:
        raise ValueError("rank is outside [1, dimension]")
    vals, vecs = np.linalg.eigh(g)
    order = np.argsort(-np.abs(vals), kind="stable")
    ordered_vals = vals[order]
    ordered_vecs = vecs[:, order]
    use_vals = ordered_vals[:int(rank)]
    use_vecs = ordered_vecs[:, :int(rank)]
    truncated = (use_vecs * use_vals[None, :]) @ use_vecs.T
    return {
        "matrix": _symmetric(truncated),
        "eigenvalues_abs_order": ordered_vals,
        "eigenvectors_abs_order": ordered_vecs,
        "selected_eigenvalues": use_vals,
        "rank": int(rank),
    }


def cancellation_score(eigenvalues: np.ndarray, eps: float = 1e-15) -> float:
    vals = np.asarray(eigenvalues, dtype=float).reshape(-1)
    denom = float(np.abs(vals).sum())
    if denom <= eps:
        return 0.0
    raw = 1.0 - abs(float(vals.sum())) / (denom + float(eps))
    return float(np.clip(raw, 0.0, 1.0))


def spectral_diagnostics(gradient: np.ndarray, eps: float = 1e-15) -> dict:
    g = _symmetric(gradient)
    trunc = rank_truncate(g, 1)
    vals = trunc["eigenvalues_abs_order"]
    abs_vals = np.abs(vals)
    total = float(abs_vals.sum())
    trace = float(np.trace(g))
    fro = float(np.linalg.norm(g, ord="fro"))
    dim = g.shape[0]
    return {
        "eigenvalues_abs_order": vals,
        "trace": trace,
        "spectral_norm": float(abs_vals[0]),
        "frobenius_norm": fro,
        "positive_spectral_mass": float(vals[vals > 0].sum()),
        "negative_spectral_mass_abs": float(-vals[vals < 0].sum()),
        "anisotropy_score": float(fro / (abs(trace) / math.sqrt(dim) + eps)),
        "cancellation_score": cancellation_score(vals, eps=eps),
        "top1_spectral_fraction": float(abs_vals[0] / (total + eps)),
        "top2_spectral_fraction": float(abs_vals[:min(2, dim)].sum() /
                                        (total + eps)),
    }


def spd_log_covariance_update(
    covariance: np.ndarray,
    gradient: np.ndarray,
    eta: float,
    rank: int | None = None,
    normalize_frobenius: bool = False,
    max_abs_log_step: float | None = None,
    condition_number_ceiling: float | None = None,
) -> dict:
    """Apply ``S^(1/2) exp(-eta G_rank) S^(1/2)`` with safety guards."""
    s_vals, s_vecs = _spd_eigh(covariance)
    sqrt_s = (s_vecs * np.sqrt(s_vals)[None, :]) @ s_vecs.T
    g = _symmetric(gradient)
    if g.shape != covariance.shape:
        raise ValueError("gradient/covariance shape mismatch")
    if rank is not None:
        g = rank_truncate(g, int(rank))["matrix"]
    g_norm = float(np.linalg.norm(g, ord="fro"))
    if normalize_frobenius and g_norm > 0.0:
        g = g / g_norm
    step = -float(eta) * g
    step_vals, step_vecs = np.linalg.eigh(_symmetric(step))
    clipped = False
    if max_abs_log_step is not None:
        bound = float(max_abs_log_step)
        if bound <= 0.0:
            raise ValueError("max_abs_log_step must be positive")
        new_vals = np.clip(step_vals, -bound, bound)
        clipped = not np.array_equal(new_vals, step_vals)
        step_vals = new_vals
    exp_step = (step_vecs * np.exp(step_vals)[None, :]) @ step_vecs.T
    updated = _symmetric(sqrt_s @ exp_step @ sqrt_s)
    out_vals, _ = _spd_eigh(updated)
    condition = float(out_vals.max() / out_vals.min())
    if (condition_number_ceiling is not None and
            condition > float(condition_number_ceiling)):
        raise ValueError("updated covariance exceeds condition-number ceiling")
    return {
        "covariance": updated,
        "min_eigenvalue": float(out_vals.min()),
        "max_eigenvalue": float(out_vals.max()),
        "condition_number": condition,
        "gradient_frobenius_before_normalization": g_norm,
        "log_step_eigenvalues": step_vals,
        "log_step_clipped": clipped,
        "rank": int(rank) if rank is not None else int(g.shape[0]),
    }


def gaussian_second_moment(target_covariance: np.ndarray,
                           proposal_covariance: np.ndarray) -> float:
    """Closed-form ``integral p_T(x)^2/q_S(x) dx`` on all of R^d."""
    t = _symmetric(target_covariance)
    s = _symmetric(proposal_covariance)
    _spd_eigh(t)
    _spd_eigh(s)
    precision = 2.0 * np.linalg.inv(t) - np.linalg.inv(s)
    _spd_eigh(precision)
    sign_t, logdet_t = np.linalg.slogdet(t)
    sign_s, logdet_s = np.linalg.slogdet(s)
    sign_p, logdet_p = np.linalg.slogdet(precision)
    if min(sign_t, sign_s, sign_p) <= 0:
        raise ValueError("invalid Gaussian determinant")
    log_m2 = -logdet_t + 0.5 * logdet_s - 0.5 * logdet_p
    return float(np.exp(log_m2))


def gaussian_log_covariance_gradient(target_covariance: np.ndarray,
                                     proposal_covariance: np.ndarray) -> np.ndarray:
    """Closed-form log-covariance gradient for the Gaussian fixture."""
    t = _symmetric(target_covariance)
    s = _symmetric(proposal_covariance)
    s_vals, s_vecs = _spd_eigh(s)
    invsqrt_s = (s_vecs * (1.0 / np.sqrt(s_vals))[None, :]) @ s_vecs.T
    nu_cov = np.linalg.inv(2.0 * np.linalg.inv(t) - np.linalg.inv(s))
    whitened_scatter = invsqrt_s @ nu_cov @ invsqrt_s
    m2 = gaussian_second_moment(t, s)
    return _symmetric(0.5 * m2 * (np.eye(s.shape[0]) - whitened_scatter))


def log_covariance_directional_fd(target_covariance: np.ndarray,
                                  proposal_covariance: np.ndarray,
                                  direction: np.ndarray,
                                  epsilon: float) -> float:
    """Central FD under ``S^1/2 exp(eps B) S^1/2`` for the fixture."""
    s_vals, s_vecs = _spd_eigh(proposal_covariance)
    sqrt_s = (s_vecs * np.sqrt(s_vals)[None, :]) @ s_vecs.T
    b_vals, b_vecs = np.linalg.eigh(_symmetric(direction))

    def perturbed(sign: float) -> np.ndarray:
        exp_b = (b_vecs * np.exp(sign * float(epsilon) * b_vals)[None, :]) @ b_vecs.T
        return _symmetric(sqrt_s @ exp_b @ sqrt_s)

    up = gaussian_second_moment(target_covariance, perturbed(+1.0))
    down = gaussian_second_moment(target_covariance, perturbed(-1.0))
    return float((up - down) / (2.0 * float(epsilon)))
