"""Phase D Sanger hybrid-mode continuous dynamics (D1).

Sanger Mathematical Specification v1.0 (docs/phase_d/sanger_model_spec.md)
frozen in D0 is the source of truth for this module.

The Sanger baseline is an unpowered longitudinal lift-supported atmospheric
skip trajectory with the hybrid structure ``SANGER_ATM <-> SANGER_VAC``:

* ``SANGER_ATM``  -- frozen atmospheric dynamics with full longitudinal
  lift, ``u_L = 1`` (``sigma = 0``, ``cos(sigma) = 1``); the vehicle does
  NOT throttle lift to maintain QEG and the trajectory is free to
  pull-up / skip;
* ``SANGER_VAC``  -- strictly zero-aero (``L = 0``, ``D = 0``) but with
  gravity and spherical-Earth curvature terms retained, so the vacuum arc
  is NOT uniform rectilinear motion.

D1 audit notes (frozen code, unchanged):

1. The frozen atmospheric RHS entry point is
   ``atmospheric_dynamics(t, state, env, vehicle, control)`` in
   ``src/hyptraj/models/dynamics.py``.  The ``control`` callback returns
   ``K = L/D`` and the full lift ``L`` enters ``gamma_dot`` unscaled --
   literal Eq.(4) dynamics, which is exactly the ``u_L = 1`` semantics.
2. ``continuous_glide_rhs`` delegates ENTRY_CAPTURE / GROUND_CONTINUATION
   to ``atmospheric_dynamics`` and only QEG_GLIDE applies the ``u_L``
   scaling internally.
3. ``u_L = 1`` is therefore realised through the existing interface by
   calling ``atmospheric_dynamics`` directly; no second dynamics set exists.
4. New code is minimised accordingly: ``sanger_atm_rhs`` is a thin mode
   wrapper over the frozen RHS; ``sanger_vac_rhs`` is the only explicit
   zero-aero specialization (it must not call the atmosphere model).
5. ``sanger_vac_rhs`` reuses the frozen gravity model
   (``gravity_acceleration``) and the frozen ``EnvironmentParams``; the
   drag / lift terms are written out as absent, not computed then zeroed.

State convention follows the frozen implementation
``state = [r, theta, v, gamma]`` with ``h = r - R_E`` (the research
notation ``x = [h, v, gamma, theta]^T`` is a mathematical reordering only;
the code ordering must never change).  All RHS return
``[dr/dt, dtheta/dt, dv/dt, dgamma/dt]``.

D1 scope: continuous vector fields + diagnostic primitives + tests only.
No events, no state machine, no baseline integration, no saltation.
"""

from typing import Callable

import numpy as np

from hyptraj.models.dynamics import atmospheric_dynamics
from hyptraj.models.gravity import gravity_acceleration
from hyptraj.models.parameters import EnvironmentParams, VehicleParams

SANGER_ATM = "SANGER_ATM"
SANGER_VAC = "SANGER_VAC"

MODES = (SANGER_ATM, SANGER_VAC)

# D0-frozen atmosphere cutoff / switching boundary (Sanger mode semantics).
# It equals EnvironmentParams.atmosphere_boundary = 100 000 m; future event
# factories (D2) should read env.atmosphere_boundary for consistency.
ATMOSPHERE_BOUNDARY_M = 100_000.0


def sanger_atm_rhs(
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> np.ndarray:
    """SANGER_ATM continuous dynamics: frozen atmospheric RHS with u_L = 1.

    The Sanger ATM control is frozen to ``u_L = 1`` (``sigma = 0``,
    ``cos(sigma) = 1``): all available lift projects onto the longitudinal
    plane.  The frozen ``atmospheric_dynamics`` uses the full lift
    ``L = q S C_L``, ``C_L = K C_D`` in ``gamma_dot`` with no ``u_L``
    scaling, so delegating to it IS the ``u_L = 1`` semantics -- this
    wrapper must never re-implement the atmosphere / aero / gravity stack.

    The aerodynamic lift-to-drag ratio ``K`` is supplied by ``control``
    (the Sanger baseline freezes ``ConstantKControl(3.0)``, D0 spec §4).
    """
    return atmospheric_dynamics(t, state, env, vehicle, control)


def sanger_vac_rhs(
    t: float,
    state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
) -> np.ndarray:
    """SANGER_VAC continuous dynamics: strictly zero-aero, gravity retained.

    For ``h > h_atm`` the vehicle is in vacuum: ``L = 0`` and ``D = 0``
    are enforced logically (the atmosphere model is NOT called, no fake
    small aerodynamic forces), while gravity and the spherical-Earth
    curvature terms remain (D0 spec §6):

    .. math::

        \\dot r     &= v \\sin\\gamma \\\\
        \\dot\\theta &= \\frac{v \\cos\\gamma}{r} \\\\
        \\dot v     &= -g \\sin\\gamma \\\\
        \\dot\\gamma &= \\left(\\frac{v}{r} - \\frac{g}{v}\\right)\\cos\\gamma

    with ``g = g(h) = g0 (R_E / r)^2`` from the frozen gravity model.
    ``vehicle`` is accepted for interface symmetry with the ATM RHS but is
    not used (no aerodynamic force exists in vacuum).
    """
    r, _theta, v, gamma = state

    if v <= 0.0:
        raise ValueError("Velocity must remain positive.")

    if r <= 0.0:
        raise ValueError("Geocentric radius must remain positive.")

    g = gravity_acceleration(r - env.earth_radius, env)

    r_dot = v * np.sin(gamma)
    theta_dot = v * np.cos(gamma) / r
    v_dot = -g * np.sin(gamma)
    gamma_dot = (v / r - g / v) * np.cos(gamma)

    return np.array([r_dot, theta_dot, v_dot, gamma_dot], dtype=float)


def specific_mechanical_energy(
    state: np.ndarray,
    env: EnvironmentParams,
) -> float:
    """Specific mechanical energy ``E = v^2 / 2 - mu / r`` [J/kg].

    D0-frozen VAC verification quantity with ``mu = g0 * R_E^2`` built from
    the frozen environment parameters.  Pure diagnostic primitive: never
    modifies ``state`` and never involves a solver.
    """
    r, _theta, v, _gamma = state
    mu = env.gravity_sea_level * env.earth_radius**2
    return float(0.5 * v**2 - mu / r)


def specific_angular_momentum(
    state: np.ndarray,
    env: EnvironmentParams,
) -> float:
    """Specific angular momentum ``H = r * v * cos(gamma)`` [m^2/s].

    D0-frozen VAC verification quantity.  Pure diagnostic primitive: never
    modifies ``state`` and never involves a solver.
    """
    r, _theta, v, gamma = state
    return float(r * v * np.cos(gamma))
