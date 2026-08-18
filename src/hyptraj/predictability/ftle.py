"""Phase-G5 finite-time predictability metrics (G5 -- scaled SVD / FTLE).

G5 defines the dimensionless SCIENTIFIC predictability metrics on the
scaled hybrid STM (G0 §11 / G4 validations):

    tilde_Phi(T) = S^-1 Phi_H(T, 0) S = U Sigma V^T

with `S = diag(s_r, s_theta, s_v, s_gamma)` the declared scientific
canonical scale and:

    sigma_max(T) = sigma_1
    lambda_max(T) = (1/T) ln(sigma_1)                [1/s]

Together with the singular-value spectrum, numerical rank (standard SVD
tolerance -- NOT a physics/grazing threshold), condition status
(STRUCTURAL_SINGULAR for numerical zero sigma_min, e.g. the Qian
post-Capture rank-deficient branch), dominant input / output singular
directions (with a deterministic sign convention), scaled row / column
norms and the singular gap.

Interpretation limits: positive finite-time lambda_max means
"exponential-equivalent finite-time local amplification of the strongest
direction under the declared metric / horizon / topology branch" -- NOT
chaos, NOT an asymptotic Lyapunov exponent, NOT global instability.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from hyptraj.predictability.scaling import (
    finite_time_lyapunov_exponent as finite_time_lyapunov_exponent,
    scaled_stm,
)

STATE_DIM = 4
_MACHINE_EPS = np.finfo(float).eps


def canonicalize_svd_signs(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic SVD sign convention (G5 §14).

    For each singular pair, find the index of the largest-magnitude
    component of ``v_i`` and, if negative, flip BOTH ``u_i`` and ``v_i``
    (preserves ``tilde_Phi v_i = sigma_i u_i``).  No physical meaning is
    attached to the sign; it only stabilizes regression/snapshot output.
    """
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    if u.shape != v.shape or u.ndim != 2:
        raise ValueError("u and v must be matching 2-D arrays.")
    for i in range(u.shape[1]):
        k = int(np.argmax(np.abs(v[:, i])))
        if v[k, i] < 0.0:
            u[:, i] = -u[:, i]
            v[:, i] = -v[:, i]
    return u, v


def numerical_rank(singular_values: np.ndarray) -> int:
    """Numerical SVD rank (G5 §16).

    ``tol = sigma_max * max(m, n) * eps_machine``.  This is an SVD rank
    tolerance, deliberately NOT a physics / grazing threshold.
    """
    sv = np.asarray(singular_values, dtype=float)
    if sv.size == 0:
        return 0
    sigma_max = float(sv[0]) if sv[0] > 0.0 else 0.0
    tol = sigma_max * max(sv.size, STATE_DIM) * _MACHINE_EPS
    return int(np.count_nonzero(sv > tol))


def condition_status(singular_values: np.ndarray) -> dict:
    """Condition status policy (G5 §17).

    A numerical-zero ``sigma_min`` (e.g. the Qian post-Capture structural
    rank deficiency, ``Phi_gamma,: = 0``) is reported as
    ``STRUCTURAL_SINGULAR`` with ``condition_number = None`` -- never a
    gigantic finite value that would falsely read as instability.
    """
    sv = np.asarray(singular_values, dtype=float)
    rank = numerical_rank(sv)
    if rank < sv.size:
        return {"condition_status": "STRUCTURAL_SINGULAR",
                "condition_number": None,
                "numerical_rank": rank,
                "nullity": int(sv.size - rank)}
    sigma_min = float(sv[-1]) if sv.size else 0.0
    cond = float(sv[0] / sigma_min) if sigma_min > 0.0 else None
    return {"condition_status": "FINITE",
            "condition_number": cond,
            "numerical_rank": rank,
            "nullity": 0}


def scaled_svd(phi: np.ndarray, scales: Mapping[str, float]):
    """``S^-1 Phi S`` + deterministic SVD ``(U, Sigma, V)``.

    ``Sigma`` is a 4-vector sorted descending; ``V`` columns are the
    (canonicalized) right singular vectors (scaled input directions) and
    ``U`` columns the left singular vectors (scaled output directions).
    """
    scaled = scaled_stm(phi, scales)
    u, sigma, vt = np.linalg.svd(scaled)
    u, v = canonicalize_svd_signs(u, vt.T)
    return scaled, u, sigma, v


def finite_time_metrics(
    phi: np.ndarray,
    scales: Mapping[str, float],
    horizon_s: float,
    state_order=("r", "theta", "v", "gamma"),
) -> dict:
    """Full fixed-time predictability metric set on the SCALED STM.

    Reuses the G0 convention (``scaled_stm`` /
    ``finite_time_lyapunov_exponent``); never uses raw dimensional
    singular values for scientific claims (those are returned separately
    under an explicit ANTI-EXAMPLE tag).
    """
    phi = np.asarray(phi, dtype=float)
    scaled, u, sigma, v = scaled_svd(phi, scales)
    sigma_max = float(sigma[0])
    lambda_max = finite_time_lyapunov_exponent(scaled, float(horizon_s))
    rank = numerical_rank(sigma)
    cond = condition_status(sigma)
    v1 = v[:, 0]
    u1 = u[:, 0]
    s_vec = np.array([float(scales[k]) for k in state_order])
    physical_v1 = s_vec * v1  # unit canonical-scaled perturbation in physical units
    gap = float(sigma[0] / sigma[1]) if len(sigma) > 1 else None
    col_norms = [float(np.linalg.norm(scaled[:, j])) for j in range(STATE_DIM)]
    row_norms = [float(np.linalg.norm(scaled[i, :])) for i in range(STATE_DIM)]
    recon_err = float(np.max(np.abs(u @ np.diag(sigma) @ v.T - scaled)))
    raw = np.linalg.svd(phi, compute_uv=False)
    return {
        "phi_scaled": scaled,
        "singular_values": list(sigma),
        "sigma_max": sigma_max,
        "lambda_max": lambda_max,
        "numerical_rank": rank,
        "nullity": int(STATE_DIM - rank),
        "condition_status": cond["condition_status"],
        "condition_number": cond["condition_number"],
        "dominant_input_direction_scaled": list(v1),
        "dominant_output_direction_scaled": list(u1),
        "dominant_input_direction_physical": list(physical_v1),
        "scaled_column_norms": col_norms,
        "scaled_row_norms": row_norms,
        "singular_gap_1_2": gap,
        "svd_reconstruction_error": recon_err,
        "raw_dimensional_singular_values_ANTI_EXAMPLE": list(raw),
    }


def unit_conversion_scaling_invariance(
    phi_x: np.ndarray,
    scales: Mapping[str, float],
    d_diag: np.ndarray,
) -> bool:
    """Unit-system invariance of the scaled scientific STM (G5 §11).

    For a positive diagonal unit-conversion matrix ``D``::

        y = D^-1 x      Phi_y = D^-1 Phi_x D     S_y = D^-1 S_x
        => S_y^-1 Phi_y S_y == S_x^-1 Phi_x S_x   (numerically)

    This proves the scaled scientific STM is invariant to a consistent
    change of physical units (e.g. m -> km, m/s -> km/s, rad unchanged).
    """
    phi_x = np.asarray(phi_x, dtype=float)
    d = np.asarray(d_diag, dtype=float)
    if d.shape != (STATE_DIM,) or not np.all(d > 0.0):
        raise ValueError("d_diag must be a positive 4-vector.")
    S_x = np.array([float(scales[k]) for k in ("r", "theta", "v", "gamma")])
    D = np.diag(d)
    D_inv = np.diag(1.0 / d)
    phi_y = D_inv @ phi_x @ D
    S_y = D_inv @ S_x
    return np.allclose(
        scaled_stm(phi_y, dict(zip(("r", "theta", "v", "gamma"), S_y))),
        scaled_stm(phi_x, scales),
        atol=1e-12,
    )