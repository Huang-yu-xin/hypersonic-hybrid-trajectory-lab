"""Terminal / crossing events for trajectory integration."""

from typing import Callable

import numpy as np

from hyptraj.models.dynamics import required_lift
from hyptraj.models.parameters import EnvironmentParams, VehicleParams


def make_ground_event(
    env: EnvironmentParams,
) -> Callable[[float, np.ndarray], float]:
    """Create the terminal ground event for ``solve_ivp``.

    The event function is ``g(t, state) = r - R_e``, i.e. the altitude.
    With ``terminal=True`` the integration stops at the crossing, and with
    ``direction=-1`` only the descending crossing ``h > 0 -> h = 0`` is
    captured (the impact time is obtained by root detection, never by
    manual truncation of the last negative-altitude point).
    """

    def ground_event(t: float, state: np.ndarray, *args) -> float:
        return float(state[0] - env.earth_radius)

    ground_event.terminal = True
    ground_event.direction = -1

    return ground_event


def make_capture_event() -> Callable[[float, np.ndarray], float]:
    """QEG capture event: first upward zero crossing of the flight-path
    angle ``gamma = 0, direction = +1`` (end of the ENTRY/CAPTURE stage).

    This is a HYBRID switch: at the event the effective longitudinal lift
    fraction jumps from ``u_L = 1`` (entry) to the QEG-required value.
    Cross-capture STM/FTLE must account for the hybrid event sensitivity
    (saltation update) -- deferred to the predictability phase.
    """

    def capture_event(t: float, state: np.ndarray, *args) -> float:
        return float(state[3])

    capture_event.terminal = True
    capture_event.direction = +1
    capture_event.hybrid_switch = True

    return capture_event


def make_qeg_end_event(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control,
) -> Callable[[float, np.ndarray], float]:
    """QEG feasibility-loss (Research Terminal Interface) event: first
    post-capture upward crossing of ``u_L* = 1``, i.e. ``L_req = L``
    (``direction = +1``, terminal)."""

    def qeg_end_event(t: float, state: np.ndarray, *args) -> float:
        from hyptraj.models.atmosphere import atmospheric_density

        r, _theta, v, gamma = state
        altitude = max(r - env.earth_radius, 0.0)
        rho = atmospheric_density(altitude, env)
        K = control(t, state)
        q = 0.5 * rho * v * v
        L = q * vehicle.reference_area * K * vehicle.drag_coefficient
        req = required_lift(state, env, vehicle)
        return float(req - L)

    qeg_end_event.terminal = True
    qeg_end_event.direction = +1

    return qeg_end_event
