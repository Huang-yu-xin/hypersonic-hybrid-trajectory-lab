"""Phase-G1 continuous-mode Jacobians and numerical oracle (G1).

G1 provides ``A_m(x) = d f_m / d x`` for the frozen continuous modes:

    * Qian ``ENTRY_CAPTURE``        == ``f = atmospheric_dynamics`` (u_L = 1)
    * Sanger ``SANGER_ATM``         == the SAME frozen atmospheric RHS
    * Sanger ``SANGER_VAC``         == frozen ``sanger_vac_rhs`` (L = D = 0)
    * Qian ``QEG_GLIDE`` INTERIOR   == ``u_L = clip(L_req/L, 0, 1)`` with
      strictly interior ``u_L*`` (the smooth QEG branch, ``gamma_dot = 0``)

Hard boundaries (G0/G1 protocol): the Jacobians DIFFERENTIATE the frozen
RHS; they never re-implement physics.  No hybrid event is crossed, no
saltation is computed, no STM is propagated, no FTLE/SVD predictability
is produced (G2-G5 scope).  Control semantics: G1 freezes the constant-K
contract (``ConstantKControl`` or a plain scalar ``K`` with
``dK/dx = 0``); arbitrary state-dependent controls are rejected so that
their derivative is never silently assumed zero.

Analytic derivation (verified against the frozen source at G1 accept
time, ``docs/phase_g/g1_continuous_variational.md``):

    g   = mu / r^2,            mu = g0 R_E^2,          dg/dr = -2g/r
    rho = rho0 exp(-(r-R_E)/H),                        drho/dr = -rho/H
    d   = D/m = rho v^2 S C_D / (2m)  ->  dd/dr = -d/H,  dd/dv = 2d/v
    ell = L/m = K d             ->  dell/dr = -ell/H,  dell/dv = 2ell/v

Jacobian convention (G0 §4): columns ``[r, theta, v, gamma]``, rows
``[r_dot, theta_dot, v_dot, gamma_dot]``, ``A_ij = d f_i / d x_j``.
"""

from __future__ import annotations

import numbers
from enum import Enum

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.aerodynamics import aerodynamic_forces
from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.dynamics import required_lift
from hyptraj.models.gravity import gravity_acceleration
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes.sanger_hybrid import SANGER_ATM, SANGER_VAC

STATE_DIM = 4
COLUMNS = ("r", "theta", "v", "gamma")
ROWS = ("r_dot", "theta_dot", "v_dot", "gamma_dot")


# ---------------------------------------------------------------------------
# Constant-K derivative semantics (G0 §5, G1 §10)
# ---------------------------------------------------------------------------
def constant_k_value(control_or_k):
    """Resolve a frozen constant ``K`` from ``ConstantKControl`` or a scalar.

    G1 accepts ONLY the constant-K contract: ``dK/dx = 0`` is exact for
    ``ConstantKControl``.  Any other object (e.g. an arbitrary callable)
    raises ``TypeError`` -- the G1 analytic Jacobians must never silently
    assume a state-dependent control has zero derivative.
    """
    if isinstance(control_or_k, ConstantKControl):
        return control_or_k.value
    if isinstance(control_or_k, numbers.Real):
        value = float(control_or_k)
        if value <= 0.0:
            raise ValueError("K must be positive.")
        return value
    raise TypeError(
        "G1 analytic Jacobians accept only ConstantKControl or a scalar K "
        "(constant-K contract, dK/dx = 0).  Got "
        f"{type(control_or_k).__name__}."
    )


# ---------------------------------------------------------------------------
# Shared atmospheric evaluation (mirrors the FROZEN atmospheric_dynamics)
# ---------------------------------------------------------------------------
def atmospheric_quantities(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
) -> tuple[float, float, float, float]:
    """Return ``(g, rho, d, ell)`` evaluated exactly like the frozen RHS.

    ``g`` from ``gravity_acceleration``, ``rho`` from
    ``atmospheric_density`` (with the frozen ``max(altitude, 0)`` clamp
    for the atmosphere channel), ``d = D/m`` and ``ell = L/m`` from the
    frozen ``aerodynamic_forces``.  Reusing the frozen helpers guarantees
    the Jacobian tracks the frozen physics semantics.
    """
    state = np.asarray(state, dtype=float)
    if state.shape != (STATE_DIM,):
        raise ValueError(
            f"state must be shape ({STATE_DIM},); got {state.shape}."
        )
    r, _theta, v, _gamma = state
    if v <= 0.0:
        raise ValueError("Velocity must remain positive.")
    if r <= 0.0:
        raise ValueError("Geocentric radius must remain positive.")
    altitude = r - env.earth_radius
    alt_atm = max(altitude, 0.0)
    g = gravity_acceleration(alt_atm, env)
    rho = atmospheric_density(alt_atm, env)
    aero = aerodynamic_forces(density=rho, velocity=v,
                              lift_to_drag_ratio=k, vehicle=vehicle)
    return g, rho, aero.drag / vehicle.mass, aero.lift / vehicle.mass


def _rows01(state: np.ndarray, v: float, r: float, gamma: float) -> tuple:
    """Rows ``r_dot`` / ``theta_dot`` shared by all three atmospheric-family
    Jacobians (identical functional form in QEG interior and VAC)."""
    row_r = [0.0, 0.0, np.sin(gamma), v * np.cos(gamma)]
    row_theta = [
        -v * np.cos(gamma) / r**2,
        0.0,
        np.cos(gamma) / r,
        -v * np.sin(gamma) / r,
    ]
    return row_r, row_theta


def atmospheric_jacobian(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
) -> np.ndarray:
    """Analytic ``A_atm = d(f_atm)/dx`` (Qian ENTRY_CAPTURE / Sanger ATM).

    Differentiates the frozen ``atmospheric_dynamics`` under constant ``K``
    on the positive-altitude research interval ``h = r - R_E > 0``.
    """
    state = np.asarray(state, dtype=float)
    r, _theta, v, gamma = state
    k = constant_k_value(k)
    g, _rho, d, ell = atmospheric_quantities(state, env, vehicle, k)
    h = env.scale_height

    row_r, row_theta = _rows01(state, v, r, gamma)
    row_v = [
        d / h + 2.0 * g * np.sin(gamma) / r,
        0.0,
        -2.0 * d / v,
        -g * np.cos(gamma),
    ]
    row_gamma = [
        -ell / (h * v) + (-v / r**2 + 2.0 * g / (r * v)) * np.cos(gamma),
        0.0,
        ell / v**2 + (1.0 / r + g / v**2) * np.cos(gamma),
        -(v / r - g / v) * np.sin(gamma),
    ]
    return np.array([row_r, row_theta, row_v, row_gamma], dtype=float)


def entry_capture_jacobian(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
) -> np.ndarray:
    """``A`` for Qian ``ENTRY_CAPTURE`` (identical to ``atmospheric_jacobian``).

    Structural G1 invariant: under the same ``state/env/vehicle/constant-K``,
    ``ENTRY_CAPTURE`` and ``SANGER_ATM`` share the frozen atmospheric RHS,
    so their Jacobians are EXACTLY the same matrix.
    """
    return atmospheric_jacobian(state, env, vehicle, k)


def sanger_atm_jacobian(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
) -> np.ndarray:
    """``A`` for Sanger ``SANGER_ATM`` (identical to ``atmospheric_jacobian``)."""
    return atmospheric_jacobian(state, env, vehicle, k)


# ---------------------------------------------------------------------------
# QEG active-set mathematics (G0 §14 contract, G1 §7-§9)
# ---------------------------------------------------------------------------
class QegActiveSet(Enum):
    """Exact active-set classification of ``u_L* = L_req / L`` (no invented
    numerical threshold; exact comparisons on the ratios)."""

    LOWER_SATURATED = "LOWER_SATURATED"      # u_L* < 0
    INTERIOR = "INTERIOR"                    # 0 < u_L* < 1
    UPPER_SATURATED = "UPPER_SATURATED"      # u_L* > 1
    NONDIFFERENTIABLE = "NONDIFFERENTIABLE"  # u_L* == 0 or u_L* == 1


class QegBoundaryError(ValueError):
    """Raised when a smooth QEG-interior derivative is requested on a state
    that is NOT strictly interior (G1 §9: do not fake a smooth derivative
    at the ``u_L* = 0`` / ``u_L* = 1`` clipping boundaries)."""


def u_l_star(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
) -> float:
    """Unclipped QEG lift ratio ``u_L* = L_req / L`` (frozen primitives).

    ``L`` is evaluated with ``aerodynamic_forces`` and ``L_req`` with the
    frozen ``required_lift`` exactly as the frozen ``qeg_lift_fraction``
    does.  Raises ``ValueError`` when ``L <= 0`` (u_L* not well-defined).
    """
    state = np.asarray(state, dtype=float)
    r, _theta, v, _gamma = state
    k = constant_k_value(k)
    if v <= 0.0:
        raise ValueError("Velocity must remain positive.")
    altitude = max(r - env.earth_radius, 0.0)
    rho = atmospheric_density(altitude, env)
    aero = aerodynamic_forces(density=rho, velocity=v,
                              lift_to_drag_ratio=k, vehicle=vehicle)
    if aero.lift <= 0.0:
        raise ValueError(
            "u_L* is not well-defined for L <= 0 (degenerate state)."
        )
    req = required_lift(state, env, vehicle)
    return float(req / aero.lift)


def classify_qeg_active_set(u_l_star_value: float) -> QegActiveSet:
    """Exact active-set classification of ``u_L*`` (G1 §7)."""
    if u_l_star_value == 0.0 or u_l_star_value == 1.0:
        return QegActiveSet.NONDIFFERENTIABLE
    if u_l_star_value < 0.0:
        return QegActiveSet.LOWER_SATURATED
    if u_l_star_value > 1.0:
        return QegActiveSet.UPPER_SATURATED
    return QegActiveSet.INTERIOR


def qeg_distance_metrics(
    u_l_star_value: float,
) -> tuple[float, float]:
    """Numerical diagnostics ``(distance_to_0, distance_to_1)``.

    ``distance_to_0 = |u_L*|``, ``distance_to_1 = |1 - u_L*|``.  These are
    diagnostics only -- they are NOT used to classify the active set
    (classification uses the exact ratio comparisons above).
    """
    return abs(u_l_star_value), abs(1.0 - u_l_star_value)


def qeg_interior_jacobian(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
) -> np.ndarray:
    """Analytic ``A_QEG_int`` for the smooth QEG interior.

    Requires a strictly interior state (``0 < u_L* < 1``); otherwise
    raises ``QegBoundaryError`` (no fake smooth derivative at the
    clipping boundaries; G1 §9).  In the interior ``u_L L = L_req`` so
    ``gamma_dot = 0`` and the Gamma row is exactly zero:
    rows r/theta/v identical to ``atmospheric_jacobian``.
    """
    state = np.asarray(state, dtype=float)
    k = constant_k_value(k)
    us = u_l_star(state, env, vehicle, k)
    if classify_qeg_active_set(us) != QegActiveSet.INTERIOR:
        raise QegBoundaryError(
            "QEG-interior Jacobian requires a strictly interior u_L* "
            f"(0 < u_L* < 1); got u_L* = {us} -> "
            f"{classify_qeg_active_set(us).value}."
        )
    r, _theta, v, gamma = state
    g, _rho, d, _ell = atmospheric_quantities(state, env, vehicle, k)
    h = env.scale_height
    row_r, row_theta = _rows01(state, v, r, gamma)
    row_v = [
        d / h + 2.0 * g * np.sin(gamma) / r,
        0.0,
        -2.0 * d / v,
        -g * np.cos(gamma),
    ]
    return np.array([row_r, row_theta, row_v, [0.0, 0.0, 0.0, 0.0]],
                    dtype=float)


# ---------------------------------------------------------------------------
# Sanger VAC (G1 §6)
# ---------------------------------------------------------------------------
def sanger_vac_jacobian(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
) -> np.ndarray:
    """Analytic ``A_vac = d(f_VAC)/dx`` for the frozen ``sanger_vac_rhs``.

    ``f_VAC`` depends only on ``g(h)`` (no rho / scale-height / K /
    aerodynamic-coefficient dependence), so neither does ``A_vac``.
    ``vehicle`` is accepted for interface symmetry with the ATM Jacobians
    and is NOT used (same contract as the frozen ``sanger_vac_rhs``).
    """
    state = np.asarray(state, dtype=float)
    if state.shape != (STATE_DIM,):
        raise ValueError(
            f"state must be shape ({STATE_DIM},); got {state.shape}."
        )
    r, _theta, v, gamma = state
    if v <= 0.0:
        raise ValueError("Velocity must remain positive.")
    if r <= 0.0:
        raise ValueError("Geocentric radius must remain positive.")
    g = gravity_acceleration(r - env.earth_radius, env)

    row_r, row_theta = _rows01(state, v, r, gamma)
    row_v = [2.0 * g * np.sin(gamma) / r, 0.0, 0.0, -g * np.cos(gamma)]
    row_gamma = [
        (-v / r**2 + 2.0 * g / (r * v)) * np.cos(gamma),
        0.0,
        (1.0 / r + g / v**2) * np.cos(gamma),
        -(v / r - g / v) * np.sin(gamma),
    ]
    return np.array([row_r, row_theta, row_v, row_gamma], dtype=float)


# ---------------------------------------------------------------------------
# Numerical Jacobian oracle (independent of the analytic formulas)
# ---------------------------------------------------------------------------
def finite_difference_jacobian(
    rhs,
    state: np.ndarray,
    steps: np.ndarray,
    multiplier: float = 1.0,
    scheme: str = "central3",
) -> np.ndarray:
    """Independent finite-difference Jacobian oracle.

    ``rhs(state) -> f(state)`` is the FROZEN RHS evaluated at a state
    (the caller wraps e.g. ``atmospheric_dynamics``).  ``steps`` is an
    explicit component step vector (NOT a mysterious scalar epsilon);
    ``multiplier`` scales the whole step vector for step-size sweeps.

    Schemes: ``central3`` -- (f(x+h)-f(x-h)) / (2h), one-step; ``central5``
    -- standard 5-point formula (f(x-2h)-8f(x-h)+8f(x+h)-f(x+2h))/(12h).
    """
    state = np.asarray(state, dtype=float)
    if state.shape != (STATE_DIM,):
        raise ValueError(
            f"state must be shape ({STATE_DIM},); got {state.shape}."
        )
    steps = np.asarray(steps, dtype=float)
    if steps.shape != (STATE_DIM,) or not np.all(steps > 0.0):
        raise ValueError("steps must be a positive 4-vector.")
    h = steps * multiplier
    n = STATE_DIM
    fd = np.zeros((n, n), dtype=float)

    if scheme == "central3":
        for j in range(n):
            xp = state.copy()
            xm = state.copy()
            xp[j] += h[j]
            xm[j] -= h[j]
            fd[:, j] = (np.asarray(rhs(xp), dtype=float)
                        - np.asarray(rhs(xm), dtype=float)) / (2.0 * h[j])
        return fd

    if scheme == "central5":
        for j in range(n):
            x2p = state.copy()
            x1p = state.copy()
            x1m = state.copy()
            x2m = state.copy()
            x2p[j] += 2.0 * h[j]
            x1p[j] += h[j]
            x1m[j] -= h[j]
            x2m[j] -= 2.0 * h[j]
            fd[:, j] = (
                -np.asarray(rhs(x2p), dtype=float)
                + 8.0 * np.asarray(rhs(x1p), dtype=float)
                - 8.0 * np.asarray(rhs(x1m), dtype=float)
                + np.asarray(rhs(x2m), dtype=float)
            ) / (12.0 * h[j])
        return fd

    raise ValueError(f"unknown scheme {scheme!r}")


# ---------------------------------------------------------------------------
# Error accounting (dimension-aware; G1 §14)
# ---------------------------------------------------------------------------
def jacobian_error_summary(
    a_analytic: np.ndarray,
    a_fd: np.ndarray,
    nonzero_rel_tol: float = 1e-8,
) -> dict:
    """Dimension-aware analytic-vs-FD error summary (G1 §14).

    Returns structured metrics: max absolute error, max relative error on
    materially nonzero entries, per-row / per-column max absolute errors,
    the theta-column residual (``A[:, 1]``; theoretically zero), the
    analytic row/column norms, and the number of materially nonzero
    entries.  Zero entries are reported by ABSOLUTE residual only (never
    by ratio, to avoid division by a near-zero denominator).
    """
    a_analytic = np.asarray(a_analytic, dtype=float)
    a_fd = np.asarray(a_fd, dtype=float)
    diff = a_analytic - a_fd
    max_abs = float(np.max(np.abs(diff)))
    scale = float(np.max(np.abs(a_analytic))) if a_analytic.size else 0.0
    nonzero = np.abs(a_analytic) >= nonzero_rel_tol * max(scale, 1e-300)
    rel_vals = np.abs(diff[nonzero]) / np.maximum(
        np.abs(a_analytic[nonzero]), 1e-300
    )
    max_rel_nonzero = float(np.max(rel_vals)) if rel_vals.size else 0.0
    return {
        "max_abs_error": max_abs,
        "max_rel_error_nonzero": max_rel_nonzero,
        "n_materially_nonzero": int(nonzero.sum()),
        "nonzero_rel_tol": nonzero_rel_tol,
        "per_row_max_abs": [float(np.max(np.abs(diff[i])))
                            for i in range(STATE_DIM)],
        "per_col_max_abs": [float(np.max(np.abs(diff[:, j])))
                            for j in range(STATE_DIM)],
        "theta_column_residual": float(np.max(np.abs(diff[:, 1]))),
        "analytic_abs_max": float(scale),
    }


def frozen_rhs(mode: str, env, vehicle, k):
    """Wrap a FROZEN RHS as ``rhs(state)`` for the FD oracle.

    Modes: ``entry_capture`` / ``sanger_atm`` -> ``atmospheric_dynamics``;
    ``qeg_interior`` -> ``continuous_glide_rhs(QEG_GLIDE, ...)``;
    ``sanger_vac`` -> ``sanger_vac_rhs``.  All controls are the frozen
    constant-K control (``ConstantKControl``).
    """
    from hyptraj.modes.continuous_glide import QEG_GLIDE, continuous_glide_rhs
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs, sanger_vac_rhs
    from hyptraj.models.dynamics import atmospheric_dynamics

    k_float = constant_k_value(k)
    ctl = ConstantKControl(k_float)

    if mode in ("entry_capture", "sanger_atm"):
        def rhs(state):
            return atmospheric_dynamics(
                0.0, np.asarray(state, dtype=float), env, vehicle, ctl
            )

    elif mode == "qeg_interior":
        def rhs(state):
            return continuous_glide_rhs(
                QEG_GLIDE, 0.0, np.asarray(state, dtype=float),
                env, vehicle, ctl,
            )

    elif mode == "sanger_vac":
        def rhs(state):
            return sanger_vac_rhs(
                0.0, np.asarray(state, dtype=float), env, vehicle
            )

    else:
        raise ValueError(f"unknown mode {mode!r}")
    return rhs


def analytic_jacobian(
    mode: str,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
) -> np.ndarray:
    """Dispatch to the analytic Jacobian for a frozen continuous mode."""
    if mode in ("entry_capture", "sanger_atm"):
        return atmospheric_jacobian(state, env, vehicle, k)
    if mode == "qeg_interior":
        return qeg_interior_jacobian(state, env, vehicle, k)
    if mode == "sanger_vac":
        return sanger_vac_jacobian(state, env, vehicle)
    raise ValueError(f"unknown mode {mode!r}")


# ---------------------------------------------------------------------------
# Representative state extraction (G1 §12 -- frozen trajectories only)
# ---------------------------------------------------------------------------
def _nearest_event_distance(
    t: float,
    boundaries: list[float],
) -> float:
    """Time distance from ``t`` to the nearest event/segment boundary [s]."""
    if not boundaries:
        return float("inf")
    return float(min(abs(t - b) for b in boundaries))


def representative_continuous_states(
    mode: str,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    k=3.0,
    n_samples: int = 4,
    min_event_distance_s: float = 2.0,
) -> list[dict]:
    """Extract true interior states of a frozen trajectory (G1 §12).

    Uses the PRODUCTION research integrators + E0.1 dense-output observer.
    Sampling rules: interior times of each continuous segment only; hybrid
    switch points, RTI, SRTI, grazing anchors, QEG clipping boundaries,
    diagnostic events (pullout / apogee) and segment endpoints are
    EXCLUDED (every sample is at least ``min_event_distance_s`` away from
    every stored event time).  Every QEG sample is verified to be
    strictly interior; every VAC sample comes from a real ``SANGER_VAC``
    segment (never a manually relabelled atmospheric state).

    Returns per-sample dicts with ``mode / time / state / source_segment /
    u_l_star / active_set / distance_to_0 / distance_to_1 /
    distance_to_nearest_event_s``.
    """
    k = constant_k_value(k)

    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    control = ConstantKControl(k)
    samples: list[dict] = []

    if mode in ("entry_capture", "qeg_interior"):
        collector = DenseOutputCollector()
        traj = integrate_qian_research_trajectory(
            env, vehicle, initial, control,
            dense_output_collector=collector,
        )
        all_event_times = [float(e.time_s) for e in traj.events]
        if mode == "entry_capture":
            seg = collector.segments[0]
            span = seg.t_end - seg.t_start
            for fraction in (0.25, 0.45, 0.65, 0.85, 0.92):
                t = seg.t_start + fraction * span
                state = np.asarray(seg.solution(t), dtype=float)
                bounds = [seg.t_start, seg.t_end] + all_event_times
                sample = _package_sample(mode, t, state, "segment0",
                                         None, bounds)
                if sample["distance_to_nearest_event_s"] < min_event_distance_s:
                    continue
                samples.append(sample)
                if len(samples) >= n_samples:
                    return samples
        else:  # qeg_interior
            seg = collector.segments[1]
            span = seg.t_end - seg.t_start
            for fraction in (0.15, 0.3, 0.5, 0.7, 0.85):
                t = seg.t_start + fraction * span
                state = np.asarray(seg.solution(t), dtype=float)
                us = u_l_star(state, env, vehicle, k)
                if classify_qeg_active_set(us) != QegActiveSet.INTERIOR:
                    continue
                d0, d1 = qeg_distance_metrics(us)
                bounds = [seg.t_start, seg.t_end] + all_event_times
                sample = _package_sample(mode, t, state, "segment1",
                                         us, bounds, d0, d1)
                if sample["distance_to_nearest_event_s"] < min_event_distance_s:
                    continue
                samples.append(sample)
                if len(samples) >= n_samples:
                    return samples
        if not samples:
            raise RuntimeError(
                f"no representative {mode} samples found (frozen "
                "trajectory topology unexpected)."
            )
        return samples

    # Sanger modes ---------------------------------------------------------
    collector = DenseOutputCollector()
    sanger = integrate_sanger_research_trajectory(
        env, vehicle, initial, control,
        dense_output_collector=collector,
    )
    all_event_times = [float(e.time) for e in sanger.events]

    for seg in sanger.segments:
        seg_mode = seg.mode
        if mode == "sanger_atm" and seg_mode != SANGER_ATM:
            continue
        if mode == "sanger_vac" and seg_mode != SANGER_VAC:
            continue
        span = seg.t_end - seg.t_start
        if span <= 0.0:
            continue
        for fraction in (0.3, 0.5, 0.7, 0.85):
            t = seg.t_start + fraction * span
            state = np.asarray(
                seg.y[:, int(fraction * (len(seg.t) - 1))], dtype=float
            )
            # Refine with the exact dense output of the same segment index
            # (the HybridSegment grid is a reconstruction; the
            # DenseSolutionSegment interpolant is the exact solver output).
            exact = None
            for dseg in collector.segments:
                if dseg.index == seg.index:
                    exact = dseg
                    break
            if exact is not None and exact.t_start <= t <= exact.t_end:
                state = np.asarray(exact.solution(t), dtype=float)
            bounds = [seg.t_start, seg.t_end] + all_event_times
            us = None
            if mode == "sanger_atm":
                # Sanger ATM is the frozen atmospheric RHS with u_L = 1; the
                # u_L* ratio is recorded purely as a diagnostic (the QEG
                # saturation semantics do not apply to the Sanger ATM branch).
                try:
                    us = u_l_star(state, env, vehicle, k)
                except ValueError:
                    us = None
            sample = _package_sample(mode, t, state, f"segment{seg.index}",
                                     us, bounds)
            if sample["distance_to_nearest_event_s"] < min_event_distance_s:
                continue
            samples.append(sample)
            if len(samples) >= n_samples:
                return samples
    if not samples:
        raise RuntimeError(
            f"no representative {mode} samples found (frozen trajectory "
            "topology unexpected)."
        )
    return samples


def _package_sample(
    mode: str,
    t: float,
    state: np.ndarray,
    source_segment: str,
    u_star: float | None,
    boundaries: list[float],
    distance_to_0: float | None = None,
    distance_to_1: float | None = None,
) -> dict:
    return {
        "mode": mode,
        "time_s": float(t),
        "state": np.asarray(state, dtype=float, copy=True),
        "source_segment": source_segment,
        "u_l_star": u_star,
        "active_set": (
            classify_qeg_active_set(u_star).value if u_star is not None
            else None
        ),
        "distance_to_0": distance_to_0,
        "distance_to_1": distance_to_1,
        "distance_to_nearest_event_s": _nearest_event_distance(
            t, boundaries
        ),
    }