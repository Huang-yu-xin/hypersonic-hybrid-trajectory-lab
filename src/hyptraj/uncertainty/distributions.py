"""Phase-H2 Gaussian research input-law (H2 §62).

H2 continues to use the H0 canonical synthetic research family strictly:

    Z0 = S_A^-1 delta X0 ~ N(0, alpha^2 I),      delta X0 = S_A (alpha z),   z ~ N(0, I)

with the frozen canonical scale ``S_A = diag(1e5, 1, 7e3, 0.1)``.

This module provides ONLY the law metadata and the standardized <-> physical
perturbation transform (+ validation).  It performs NO sampling (that is
``sampling.py``'s job) and NO trajectory work.

``alpha`` stays a SYNTHETIC dimensionless research amplitude
(``ALPHA_STATUS = PENDING_NUMERICAL_AUDIT``): every H2 probe value is a
NUMERICAL PROBE, not a real-world uncertainty calibration (H2 §8).
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from hyptraj.uncertainty.protocol import (
    ALPHA_STATUS,
    STATE_DIM,
    STATE_ORDER_TUPLE,
    canonical_scale,
)

LAW_LABEL = "Z0 = S_A^-1 delta X0 ~ N(0, alpha^2 I)  (canonical R = I synthetic research law)"
LAW_NOTE = (
    "delta X0 = S_A (alpha z) with z ~ N(0, I); alpha is a synthetic "
    "dimensionless research amplitude, NOT a real sensor / tolerance / "
    "flight-dispersion / world-probability calibration (H0 §13, H2 §8)."
)


def law_metadata(scales: Mapping[str, float] | None = None) -> dict:
    """Human/machine-readable description of the frozen input law."""
    return {
        "law_label": LAW_LABEL,
        "law_note": LAW_NOTE,
        "canonical_scale": {k: float(v) for k, v in canonical_scale().items()},
        "alpha_status": ALPHA_STATUS,
        "alpha_role": "synthetic dimensionless research probability-law amplitude only",
        "state_order": list(STATE_ORDER_TUPLE),
    }


def standardized_to_delta_x(
    z: np.ndarray,
    alpha: float,
    scales: Mapping[str, float] | None = None,
) -> np.ndarray:
    """``delta X0 = S_A (alpha z)`` for standardized samples ``z ~ N(0, I)``.

    ``z`` may be a single vector or any leading-axis array of vectors
    (per-row standardized samples mapped elementwise to physical
    perturbations).
    """
    z = np.asarray(z, dtype=float)
    if z.shape[-1] != STATE_DIM:
        raise ValueError(f"z must have trailing dimension 4, got {z.shape[-1]}.")
    if not np.all(np.isfinite(z)):
        raise ValueError("z must be finite (no NaN/Inf standardized sample).")
    S = np.diag([float(v) for k, v in (scales or canonical_scale()).items()])
    return float(alpha) * (np.asarray(z) @ S.T)


def delta_x_to_standardized(
    dx: np.ndarray,
    alpha: float,
    scales: Mapping[str, float] | None = None,
) -> np.ndarray:
    """``z = (1/alpha) S_A^-1 delta X0`` -- exact inverse transform.

    Only meaningful for ``alpha > 0``; used for bookkeeping / cross-checks,
    never as a sampling path.
    """
    if float(alpha) <= 0.0:
        raise ValueError("alpha must be > 0 for the inverse transform.")
    dx = np.asarray(dx, dtype=float)
    S = np.diag([float(v) for k, v in (scales or canonical_scale()).items()])
    return np.asarray(dx, dtype=float) @ np.linalg.inv(S).T / float(alpha)


def sample_initial_states(
    x0_nominal: np.ndarray,
    z: np.ndarray,
    alpha: float,
    scales: Mapping[str, float] | None = None,
) -> np.ndarray:
    """``x_{0,i} = xbar0 + S_A (alpha z_i)`` for each standardized row.

    Returns a stack shaped like ``z`` with the nominal state broadcast.
    """
    return np.asarray(x0_nominal, dtype=float) + standardized_to_delta_x(
        z, alpha, scales=scales)
