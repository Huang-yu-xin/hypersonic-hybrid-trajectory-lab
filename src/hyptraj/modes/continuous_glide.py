"""Approved Qian continuous-glide mode semantics (Phase B.5, dual-endpoint).

The approved Qian baseline is an event-driven three-mode trajectory:

    ENTRY_CAPTURE         u_L = 1, literal Eq.(4) dynamics; terminates on
                          the first upward zero crossing of gamma
                          (gamma = 0, direction = +1)  [QEG capture]
    QEG_GLIDE             u_L = clip(L_req / L, 0, 1) with
                          L_req = m (g - v^2/r) cos(gamma); terminates on
                          the first post-capture upward crossing of
                          u_L* = 1 (L_req = L)  [Research Terminal
                          Interface = QEG feasibility loss]
    GROUND_CONTINUATION   u_L = 1, literal Eq.(4) dynamics; continues
                          naturally to the ground event h = 0.

This segment is NOT a production terminal-guidance law; it exists only
for compatibility with the original problem's ground-endpoint metrics.

Control semantics:  K = L/D = 3 is the AERODYNAMIC lift-to-drag ratio;
u_L = cos(sigma) in [0, 1] is the effective longitudinal lift projection;
K_eff = K * u_L may be REPORTED but never replaces the aerodynamic K.
"""

from typing import Callable

import numpy as np

from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.dynamics import (
    atmospheric_dynamics,
    required_lift,
)
from hyptraj.models.parameters import EnvironmentParams, VehicleParams

ENTRY_CAPTURE = "ENTRY_CAPTURE"
QEG_GLIDE = "QEG_GLIDE"
GROUND_CONTINUATION = "GROUND_CONTINUATION"

MODES = (ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION)


def qeg_lift_fraction(
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> float:
    """QEG effective longitudinal lift fraction.

    ``u_L = clip(L_req / L, 0, 1)`` with ``L_req = m (g - v^2/r) cos(gamma)``
    and ``L = q S C_L``, ``C_L = K C_D``.  Within the QEG_GLIDE stage the
    unclipped ratio satisfies ``0 <= u_L_star <= 1`` by construction (the
    stage terminates at the first upward crossing of ``u_L_star = 1``).
    """
    r, _theta, v, _gamma = state
    altitude = max(r - env.earth_radius, 0.0)
    rho = atmospheric_density(altitude, env)
    K = control(t, state)
    q = 0.5 * rho * v * v
    L = q * vehicle.reference_area * K * vehicle.drag_coefficient
    req = required_lift(state, env, vehicle)

    if L <= 0.0:
        return 0.0
    return float(np.clip(req / L, 0.0, 1.0))


def continuous_glide_rhs(
    mode: str,
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> np.ndarray:
    """Right-hand side for the given Qian glide mode.

    ENTRY_CAPTURE and GROUND_CONTINUATION use the literal Eq.(4) dynamics
    (u_L = 1).  QEG_GLIDE uses Eq.(4) with the lift term in ``gamma_dot``
    scaled by ``u_L``:

    .. math::

        \\dot\\gamma = \\frac{u_L L}{m v}
                       + \\left(\\frac{v}{r} - \\frac{g}{v}\\right)\\cos\\gamma
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}; expected one of {MODES}.")

    if mode == QEG_GLIDE:
        return _qeg_glide_dynamics(t, state, env, vehicle, control)

    return atmospheric_dynamics(t, state, env, vehicle, control)


def _qeg_glide_dynamics(
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> np.ndarray:
    r, theta, v, gamma = state
    altitude = r - env.earth_radius
    altitude_for_atmosphere = max(altitude, 0.0)

    from hyptraj.models.aerodynamics import aerodynamic_forces
    from hyptraj.models.gravity import gravity_acceleration

    g = gravity_acceleration(altitude_for_atmosphere, env)
    rho = atmospheric_density(altitude_for_atmosphere, env)
    K = control(t, state)
    aero = aerodynamic_forces(
        density=rho,
        velocity=v,
        lift_to_drag_ratio=K,
        vehicle=vehicle,
    )
    D = aero.drag
    L = aero.lift
    u = qeg_lift_fraction(t, state, env, vehicle, control)

    r_dot = v * np.sin(gamma)
    theta_dot = v * np.cos(gamma) / r
    v_dot = -D / vehicle.mass - g * np.sin(gamma)
    gamma_dot = (u * L / (vehicle.mass * v)
                 + (v / r - g / v) * np.cos(gamma))

    return np.array([r_dot, theta_dot, v_dot, gamma_dot], dtype=float)
