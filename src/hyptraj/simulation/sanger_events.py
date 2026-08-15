"""Phase D Sanger hybrid event primitives (D2).

Sanger Mathematical Specification v1.0 (docs/phase_d/sanger_model_spec.md,
§7-§13) freezes the Sanger switching geometry:

    G_atm(x) = h - h_atm = r - R_E - h_atm

with h_atm = 100 000 m.  In the frozen implementation state ordering
``state = [r, theta, v, gamma]`` (``state[0]`` is the geocentric radius
``r``, NOT the altitude ``h``), the atmosphere switching surface is
therefore implemented as

    G = state[0] - R_E - h_atm

and its gradient is ``nabla G = [1, 0, 0, 0]^T`` (D0 spec §16).  The
boundary height is read from the frozen ``EnvironmentParams`` field
``atmosphere_boundary`` (single source of truth; equals the D1 constant
``ATMOSPHERE_BOUNDARY_M`` = 100 000 m).

All event factories are PURE OBSERVERS: they never mutate the state and
never apply a reset (the D0 reset map ``x+ = x-`` is inherited naturally
by the future D3 state machine).  No epsilon state perturbation is used
to avoid t = 0 re-triggering; direction-specific events and mode-specific
event registration handle exact-boundary restarts (D0 §9 synthetic E0).

Events implemented in D2:

* atmosphere exit      ATM -> VAC,  G = h - h_atm,  direction = +1, terminal
* atmosphere entry     VAC -> ATM,  G = h - h_atm,  direction = -1, terminal
* ATM pull-out         diagnostic,  G = gamma,      direction = +1, nonterminal
* VAC apogee           diagnostic,  G = gamma,      direction = -1, nonterminal
* SRTI candidate       G = gamma, direction = -1, terminal -- a raw ATM
  downward-gamma-crossing root.  SRTI QUALIFICATION (the current
  atmospheric pass has already observed pull-out and no atmosphere exit
  occurred first) is a state-machine-history decision that belongs to
  D3; a candidate root is NOT automatically a completed SRTI.

The existing frozen ground event (``make_ground_event`` in
``simulation/events.py``, ``h = 0`` descending, terminal) is reused by
later phases; it is not re-implemented here.
"""

from typing import Callable

import numpy as np

from hyptraj.models.parameters import EnvironmentParams


def atmosphere_interface_value(
    state: np.ndarray,
    env: EnvironmentParams,
) -> float:
    """Atmosphere switching surface ``G_atm(x) = h - h_atm``.

    Implemented in the frozen state ordering as
    ``G = state[0] - R_E - env.atmosphere_boundary``, i.e. the altitude
    minus the frozen atmosphere boundary (h_atm = 100 000 m by default,
    identical to the D1 constant ``ATMOSPHERE_BOUNDARY_M``).  Pure
    diagnostic helper; never mutates ``state``.
    """
    return float(
        state[0] - env.earth_radius - env.atmosphere_boundary
    )


def atmosphere_interface_normal() -> np.ndarray:
    """Gradient of the atmosphere switching surface, ``nabla G = [1,0,0,0]^T``.

    In the frozen state ordering ``[r, theta, v, gamma]`` the surface
    ``G = r - R_E - h_atm`` depends only on ``state[0]`` (D0 spec §16,
    future hybrid-sensitivity metadata).  Saltation treatment is NOT
    implemented in Phase D.
    """
    return np.array([1.0, 0.0, 0.0, 0.0])


def make_atmosphere_exit_event(
    env: EnvironmentParams,
) -> Callable[[float, np.ndarray], float]:
    """ATM -> VAC atmosphere-exit event (D0 spec §7).

    Root ``G = h - h_atm``; ``direction = +1`` detects only the upward
    crossing (below -> above), i.e. ``dh/dt > 0`` at ``h = h_atm``;
    ``terminal = True``.  The event function does not change the state
    and does not implement the reset map.
    """

    def exit_event(t: float, state: np.ndarray, *args) -> float:
        return atmosphere_interface_value(state, env)

    exit_event.terminal = True
    exit_event.direction = +1
    return exit_event


def make_atmosphere_entry_event(
    env: EnvironmentParams,
) -> Callable[[float, np.ndarray], float]:
    """VAC -> ATM atmosphere-entry event (D0 spec §8).

    Same switching surface as the exit event, but ``direction = -1``
    detects only the downward crossing (above -> below), i.e.
    ``dh/dt < 0`` at ``h = h_atm``; ``terminal = True``.  The event
    function does not change the state and does not implement the reset
    map.
    """

    def entry_event(t: float, state: np.ndarray, *args) -> float:
        return atmosphere_interface_value(state, env)

    entry_event.terminal = True
    entry_event.direction = -1
    return entry_event


def make_pullout_event() -> Callable[[float, np.ndarray], float]:
    """ATM pull-out diagnostic event (D0 spec §10).

    Root ``G = gamma`` (``state[3]`` in the frozen ordering); direction
    ``+1`` detects ``gamma: negative -> positive``, corresponding to the
    atmospheric local minimum (``dh/dt = 0``, ``gamma = 0``).  Pull-out
    is NOT a mode transition: ``terminal = False`` (diagnostic only).
    """

    def pullout_event(t: float, state: np.ndarray, *args) -> float:
        return float(state[3])

    pullout_event.terminal = False
    pullout_event.direction = +1
    return pullout_event


def make_vacuum_apogee_event() -> Callable[[float, np.ndarray], float]:
    """VAC apogee diagnostic event (D0 spec §11).

    Root ``G = gamma`` (``state[3]``); direction ``-1`` detects
    ``gamma: positive -> negative``, corresponding to the vacuum local
    maximum altitude.  Diagnostic only: ``terminal = False``, the VAC
    mode does not change at apogee.
    """

    def apogee_event(t: float, state: np.ndarray, *args) -> float:
        return float(state[3])

    apogee_event.terminal = False
    apogee_event.direction = -1
    return apogee_event


def make_srti_candidate_event() -> Callable[[float, np.ndarray], float]:
    """ATM downward-gamma-crossing candidate for the SRTI (D0 spec §13).

    Root ``G = gamma`` (``state[3]``); direction ``-1`` detects
    ``gamma: positive -> negative`` inside the atmosphere, i.e. an
    atmospheric local apogee after the pull-out.

    IMPORTANT -- terminal root != automatically classified SRTI:

    * this primitive only locates the raw downward-gamma-crossing root;
    * SRTI QUALIFICATION -- mode == SANGER_ATM, the current atmospheric
      pass has already observed a pull-out, and no atmosphere exit
      occurred first -- depends on state-machine history and belongs to
      the D3 state machine;
    * ``terminal = True`` is recommended because in the future D3 ATM
      integration the ATM segment must stop at this candidate when it
      occurs before the next exit, and then decide SRTI qualification.

    Do NOT record every ``gamma: + -> -`` unconditionally as a formal
    SRTI.
    """

    def srti_candidate_event(t: float, state: np.ndarray, *args) -> float:
        return float(state[3])

    srti_candidate_event.terminal = True
    srti_candidate_event.direction = -1
    return srti_candidate_event
