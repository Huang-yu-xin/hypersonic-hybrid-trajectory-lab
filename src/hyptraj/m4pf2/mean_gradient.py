"""Pure arithmetic for the PF2 dimensionless proposal-mean gradient."""

from __future__ import annotations

import numpy as np


def _symmetric(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("matrix must be square")
    return 0.5 * (value + value.T)


def _spd_factors(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    value = _symmetric(matrix)
    vals, vecs = np.linalg.eigh(value)
    if not np.all(np.isfinite(vals)) or np.any(vals <= 0.0):
        raise ValueError("matrix must be strictly SPD")
    sqrt = (vecs * np.sqrt(vals)[None, :]) @ vecs.T
    invsqrt = (vecs * (1.0 / np.sqrt(vals))[None, :]) @ vecs.T
    return sqrt, invsqrt


def mean_gradient_estimate(variance_mass: np.ndarray,
                           responsibility: np.ndarray,
                           whitened: np.ndarray) -> dict:
    """Estimate ``a=sum_i abar_i r_i z_i`` using frozen M3 normalization."""
    mass = np.asarray(variance_mass, dtype=float).reshape(-1)
    resp = np.asarray(responsibility, dtype=float).reshape(-1)
    z = np.asarray(whitened, dtype=float)
    if z.ndim != 2 or z.shape[0] != mass.size or resp.size != mass.size:
        raise ValueError("sample array lengths do not match")
    if mass.size == 0:
        raise ValueError("at least one sample is required")
    if not (np.all(np.isfinite(mass)) and np.all(np.isfinite(resp)) and
            np.all(np.isfinite(z))):
        raise ValueError("inputs must be finite")
    if np.any(mass < 0.0) or np.any(resp < 0.0):
        raise ValueError("weights and responsibilities must be nonnegative")
    total = float(mass.sum())
    if total <= 0.0:
        raise ValueError("variance mass must be positive")
    a = np.einsum("n,n,ni->i", mass / total, resp, z)
    component_weight = mass * resp
    component_total = float(component_weight.sum())
    ess = (float(component_total ** 2 / np.sum(component_weight ** 2))
           if component_total > 0.0 else 0.0)
    return {
        "dimensionless_mean_gradient": a,
        "norm": float(np.linalg.norm(a)),
        "M2_hat": total / mass.size,
        "responsibility_mass": float(component_total / total),
        "ESS_mean_gradient": ess,
        "n": int(mass.size),
    }


def whitened_mean_step(covariance: np.ndarray, a: np.ndarray,
                       delta_mu: float = 0.20,
                       numerical_zero_threshold: float = 1e-12) -> dict:
    """Return ``delta_mu Sigma^(1/2) a/(||a||+0)`` or identity at zero."""
    sqrt, invsqrt = _spd_factors(covariance)
    vector = np.asarray(a, dtype=float).reshape(-1)
    if vector.size != covariance.shape[0] or not np.all(np.isfinite(vector)):
        raise ValueError("mean-gradient vector is invalid")
    norm = float(np.linalg.norm(vector))
    threshold = float(numerical_zero_threshold)
    if threshold < 0.0:
        raise ValueError("numerical_zero_threshold must be nonnegative")
    skipped = bool(norm <= threshold)
    displacement = (np.zeros_like(vector) if skipped else
                    float(delta_mu) * (sqrt @ (vector / norm)))
    mahalanobis = float(np.linalg.norm(invsqrt @ displacement))
    return {
        "displacement": displacement,
        "euclidean_norm": float(np.linalg.norm(displacement)),
        "mahalanobis_norm": mahalanobis,
        "mean_gradient_norm": norm,
        "mean_update_skipped_numerical_zero": skipped,
        "delta_mu": float(delta_mu),
        "numerical_zero_threshold": threshold,
    }


def gaussian_second_moment_with_means(target_mean: np.ndarray,
                                      target_covariance: np.ndarray,
                                      proposal_mean: np.ndarray,
                                      proposal_covariance: np.ndarray) -> float:
    """Closed-form ``integral p^2/q`` for two Gaussian densities on R^d."""
    mt = np.asarray(target_mean, dtype=float).reshape(-1)
    mq = np.asarray(proposal_mean, dtype=float).reshape(-1)
    t = _symmetric(target_covariance)
    s = _symmetric(proposal_covariance)
    if mt.size != mq.size or t.shape != s.shape or t.shape[0] != mt.size:
        raise ValueError("Gaussian dimensions do not match")
    _spd_factors(t)
    _spd_factors(s)
    ti = np.linalg.inv(t)
    si = np.linalg.inv(s)
    precision = 2.0 * ti - si
    _spd_factors(precision)
    linear = 2.0 * ti @ mt - si @ mq
    constant = -float(mt @ ti @ mt) + 0.5 * float(mq @ si @ mq)
    exponent = constant + 0.5 * float(linear @ np.linalg.solve(
        precision, linear))
    _, logdet_t = np.linalg.slogdet(t)
    _, logdet_s = np.linalg.slogdet(s)
    _, logdet_p = np.linalg.slogdet(precision)
    return float(np.exp(-logdet_t + 0.5 * logdet_s -
                        0.5 * logdet_p + exponent))


def gaussian_mean_gradient_terms(target_mean: np.ndarray,
                                 target_covariance: np.ndarray,
                                 proposal_mean: np.ndarray,
                                 proposal_covariance: np.ndarray) -> dict:
    """Exact ``M2``, tilted mean, dimensionless ``a`` and mean gradient."""
    mt = np.asarray(target_mean, dtype=float).reshape(-1)
    mq = np.asarray(proposal_mean, dtype=float).reshape(-1)
    t = _symmetric(target_covariance)
    s = _symmetric(proposal_covariance)
    _, invsqrt = _spd_factors(s)
    precision = 2.0 * np.linalg.inv(t) - np.linalg.inv(s)
    linear = 2.0 * np.linalg.inv(t) @ mt - np.linalg.inv(s) @ mq
    tilted_mean = np.linalg.solve(precision, linear)
    a = invsqrt @ (tilted_mean - mq)
    m2 = gaussian_second_moment_with_means(mt, t, mq, s)
    grad_mu = -m2 * invsqrt @ a
    return {
        "M2": m2,
        "tilted_mean": tilted_mean,
        "dimensionless_mean_gradient": a,
        "gradient_mu": grad_mu,
    }


def gaussian_mean_directional_fd(target_mean: np.ndarray,
                                 target_covariance: np.ndarray,
                                 proposal_mean: np.ndarray,
                                 proposal_covariance: np.ndarray,
                                 whitened_direction: np.ndarray,
                                 epsilon: float) -> float:
    """Central difference for ``mu +/- epsilon Sigma^(1/2) u``."""
    sqrt, _ = _spd_factors(proposal_covariance)
    mq = np.asarray(proposal_mean, dtype=float).reshape(-1)
    u = np.asarray(whitened_direction, dtype=float).reshape(-1)
    shift = float(epsilon) * (sqrt @ u)
    plus = gaussian_second_moment_with_means(
        target_mean, target_covariance, mq + shift, proposal_covariance)
    minus = gaussian_second_moment_with_means(
        target_mean, target_covariance, mq - shift, proposal_covariance)
    return float((plus - minus) / (2.0 * float(epsilon)))


__all__ = [
    "gaussian_mean_directional_fd", "gaussian_mean_gradient_terms",
    "gaussian_second_moment_with_means", "mean_gradient_estimate",
    "whitened_mean_step",
]
