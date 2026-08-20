"""H3-2 -- Variance-optimal leakage-point geometry (analysis core).

Central scientific update of H3-2: probability geometry and variance
geometry are different objects.

For a rare event ``A`` under target ``phi`` and proposal ``q``:

- probability design point (MPP, most probable point):

  ``x* = argmin_{x in A} ||x||``          (controls P_f)

- leakage point (variance geometry):

  ``x_L = argmax_{x in A} rho_L(x)``,
  ``rho_L(x) = phi(x)^2 / q(x)``          (controls M_2 = int_A phi^2/q)

For Gaussian ``phi = N(0, I)``, ``q = N(mu, I)``:

``log rho_L(x) = -||x||^2 + ||x - mu||^2/2
               = -||x + mu||^2/2 + ||mu||^2/2``

hence ``x_L = argmin_{x in A} ||x + mu||`` -- the point of A nearest to
``-mu``.  For a linear boundary with ``mu`` along the boundary normal the
two points coincide; for curved boundaries (``beta*kappa > 1``) they
differ.  This module implements both points, their distance, leakage
density evaluation, and coverage scoring.  Pure numpy -- never imports
the simulator or ML-B1 internals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PointGeometry:
    """Probability- vs variance-geometry for one topology mode."""

    mode_id: str
    topology_label: str
    probability_design_point: tuple[float, ...]   # x* (MPP)
    leakage_point: tuple[float, ...]              # x_L
    distance_between_points: float                # ||x_L - x*||
    leakage_density: float                        # rho_L(x_L)
    mpp_density: float                            # rho_L(x*)
    coverage_score: float                         # Q(A_k)/Phi(A_k)


def log_leakage_density(z: np.ndarray, mu: np.ndarray) -> np.ndarray:
    """``log rho_L(z) = log phi(z)^2 - log q(z)`` (q = N(mu, I))."""
    z = np.asarray(z, dtype=float)
    mu = np.asarray(mu, dtype=float).reshape(1, -1) if mu.ndim == 1 else mu
    # log phi^2 = -||z||^2 - d log(2pi) ; log q = -||z-mu||^2/2 - d/2 log(2pi)
    # log rho_L = -||z||^2 + ||z-mu||^2/2 - (d/2) log(2pi)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) + np.sum((z - mu) ** 2, axis=1) / 2.0 - (
        d / 2.0
    ) * np.log(2.0 * np.pi)


def leakage_density(z: np.ndarray, mu: np.ndarray) -> np.ndarray:
    """``rho_L(z) = phi(z)^2 / q(z)``."""
    return np.exp(log_leakage_density(z, mu))


def mpp(points: np.ndarray) -> np.ndarray:
    """Probability design point: point of the set with minimal norm."""
    points = np.asarray(points, dtype=float)
    norms = np.sum(points**2, axis=1)
    return points[int(np.argmin(norms))]


def leakage_point(points: np.ndarray, mu: np.ndarray) -> np.ndarray:
    """Leakage point: point of the set maximizing ``rho_L``.

    For Gaussian q = N(mu, I) this equals ``argmin ||x + mu||`` over the
    set (monotone transform of ``rho_L``), which is numerically safer.
    """
    points = np.asarray(points, dtype=float)
    mu = np.asarray(mu, dtype=float)
    dist = np.sum((points + mu) ** 2, axis=1)
    return points[int(np.argmin(dist))]


def point_geometry(
    points: np.ndarray,
    mu: np.ndarray,
    mode_id: str,
    topology_label: str,
    coverage_score: float,
) -> PointGeometry:
    """Compute both geometries for one mode's point set."""
    x_star = mpp(points)
    x_L = leakage_point(points, mu)
    rho = leakage_density(points, mu)
    return PointGeometry(
        mode_id=mode_id,
        topology_label=topology_label,
        probability_design_point=tuple(float(v) for v in x_star),
        leakage_point=tuple(float(v) for v in x_L),
        distance_between_points=float(np.linalg.norm(x_L - x_star)),
        leakage_density=float(rho[int(np.argmax(rho))]),
        mpp_density=float(rho[int(np.argmin(np.sum(points**2, axis=1)))]),
        coverage_score=float(coverage_score),
    )


def mode_point_set(
    z: np.ndarray, labels: np.ndarray, mode: str, nominal_topology: str
) -> np.ndarray:
    """Points of ``z`` whose topology label equals ``mode`` (empty-safe)."""
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    mask = labels == mode
    if not np.any(mask):
        return np.empty((0, z.shape[1]), dtype=float)
    return z[mask]


__all__ = [
    "PointGeometry",
    "log_leakage_density",
    "leakage_density",
    "mpp",
    "leakage_point",
    "point_geometry",
    "mode_point_set",
]
