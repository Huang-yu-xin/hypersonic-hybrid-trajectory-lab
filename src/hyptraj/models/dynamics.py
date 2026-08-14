"""Planar atmospheric flight dynamics for the point-mass hypersonic vehicle."""

from typing import Callable

import numpy as np

from .parameters import EnvironmentParams, VehicleParams
from .gravity import gravity_acceleration
from .atmosphere import atmospheric_density
from .aerodynamics import aerodynamic_forces


def atmospheric_dynamics(
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> np.ndarray:
    """Right-hand side of the 4-D planar dynamics inside the atmosphere.

    State vector ``[r, theta, v, gamma]``:

    * ``r``      -- geocentric radius [m], ``h = r - R_e``
    * ``theta``  -- ground-range angle [rad], ground range ``R = R_e * theta``
    * ``v``      -- velocity magnitude [m/s]
    * ``gamma``  -- flight-path angle [rad]

    Equations (full atmospheric dynamics):

    .. math::

        \\dot r     &= v \\sin\\gamma \\\\
        \\dot\\theta &= \\frac{v \\cos\\gamma}{r} \\\\
        \\dot v     &= -\\frac{D}{m} - g(h)\\sin\\gamma \\\\
        \\dot\\gamma &= \\frac{L}{m v}
                       + \\left(\\frac{v}{r} - \\frac{g(h)}{v}\\right)\\cos\\gamma

    with ``g(h) = g0 (Re / (Re + h))**2``, exponential atmosphere
    ``rho(h) = rho0 exp(-h/H)`` and ``K = C_L / C_D`` taken from ``control``.

    Parameters
    ----------
    t:
        Time [s] (passed by ``solve_ivp``; currently not used by the model).
    state:
        State vector ``[r, theta, v, gamma]``.
    env:
        Environment parameters.
    vehicle:
        Vehicle parameters.
    control:
        Lift-to-drag ratio controller, called as ``control(t, state)``.

    Returns
    -------
    np.ndarray
        Time derivative of the state, shape ``(4,)``.

    Raises
    ------
    ValueError
        If ``v <= 0`` (non-physical) or ``r <= 0`` (non-physical).
    """
    r, theta, velocity, gamma = state

    altitude = r - env.earth_radius

    if velocity <= 0.0:
        raise ValueError("Velocity must remain positive.")

    if r <= 0.0:
        raise ValueError("Geocentric radius must remain positive.")

    # Numerical guard:
    # solve_ivp may temporarily evaluate the RHS slightly below h = 0
    # before locating the terminal ground event.  Only the atmosphere model
    # input is clamped; the integration state itself is never modified.
    altitude_for_atmosphere = max(altitude, 0.0)

    g = gravity_acceleration(
        altitude_for_atmosphere,
        env,
    )

    rho = atmospheric_density(
        altitude_for_atmosphere,
        env,
    )

    K = control(t, state)

    aero = aerodynamic_forces(
        density=rho,
        velocity=velocity,
        lift_to_drag_ratio=K,
        vehicle=vehicle,
    )

    D = aero.drag
    L = aero.lift

    r_dot = velocity * np.sin(gamma)

    theta_dot = (
        velocity * np.cos(gamma) / r
    )

    velocity_dot = (
        -D / vehicle.mass
        - g * np.sin(gamma)
    )

    gamma_dot = (
        L / (vehicle.mass * velocity)
        + (
            velocity / r
            - g / velocity
        ) * np.cos(gamma)
    )

    return np.array(
        [
            r_dot,
            theta_dot,
            velocity_dot,
            gamma_dot,
        ],
        dtype=float,
    )


def required_lift(
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
) -> float:
    """Lift required for ``gamma_dot = 0`` in the current longitudinal model.

    .. math::

        L_{\\mathrm{req}} = m\\left(g - \\frac{v^2}{r}\\right)\\cos\\gamma

    Used by the quasi-equilibrium glide (QEG) control, the QEG-end event
    (``L_req = L``) and the mode-specific dynamics.  Consistent with the
    equilibrium glide condition ``L cos(sigma) = m(g - v^2/r)`` of the
    entry-guidance literature (Shen & Lu 2003, eq. 7; Eggers et al. 1957).
    """
    r, _theta, v, gamma = state
    g = gravity_acceleration(r - env.earth_radius, env)
    return vehicle.mass * (g - v**2 / r) * np.cos(gamma)


def derived_quantities(
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> dict[str, float]:
    """Physical quantities derived from a single flight state.

    Used for post-processing on the uniform output grid (the RHS itself is
    :func:`atmospheric_dynamics`).  Returns the altitude, ground range,
    density, dynamic pressure, drag and lift evaluated at ``state``.
    """
    r, theta, velocity, gamma = state

    altitude = r - env.earth_radius
    altitude_for_atmosphere = max(altitude, 0.0)

    rho = atmospheric_density(altitude_for_atmosphere, env)

    K = control(t, state)

    aero = aerodynamic_forces(
        density=rho,
        velocity=velocity,
        lift_to_drag_ratio=K,
        vehicle=vehicle,
    )

    return {
        "altitude_m": float(altitude),
        "range_m": float(env.earth_radius * theta),
        "density_kgm3": float(rho),
        "dynamic_pressure_pa": float(aero.dynamic_pressure),
        "drag_n": float(aero.drag),
        "lift_n": float(aero.lift),
    }
