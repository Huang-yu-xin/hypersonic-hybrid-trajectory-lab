"""D5 SRTI -> ground compatibility continuation (compatibility only).

D0 spec docs/phase_d/sanger_model_spec.md, §14: the research endpoint of
the Sanger baseline is the SRTI; the ground endpoint exists ONLY for
compatibility / visualization / legacy full-trajectory output.

This module integrates the frozen atmospheric dynamics
(``sanger_atm_rhs``, i.e. SANGER_ATM with u_L = 1) from the SRTI state
to the ground event h = 0 (the frozen ``make_ground_event``).  It is a
separate, independent continuation:

* it is NOT part of the D3 research state machine and does not modify it;
* it never adds skips, never changes the SRTI, the completed cycles, the
  research time or the research range;
* all Phase D high-speed research metrics stop at the SRTI.

The input SRTI state is never mutated.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)
from hyptraj.modes.sanger_hybrid import sanger_atm_rhs
from hyptraj.simulation.events import make_ground_event
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.trajectory import SolverConfig

# Upper bound of the continuation time span measured from the SRTI
# (safety guard for the compatibility leg only; not a research number).
_CONTINUATION_SPAN_S = 10_000.0

# Uniform output grid for the continuation (plotting/visualization only).
_OUTPUT_POINTS = 800


@dataclass(frozen=True)
class GroundContinuationResult:
    """Result of the SRTI -> ground compatibility leg.

    ``time`` / ``state`` are a uniform grid on ``[srti_time, ground_time]``
    reconstructed from the dense output.
    """

    time: np.ndarray
    state: np.ndarray
    ground_time_s: float
    ground_state: np.ndarray
    nfev: int
    njev: int
    nlu: int
    success: bool
    message: str


def integrate_sanger_ground_continuation(
    srti_state: np.ndarray,
    srti_time: float,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
    solver: SolverConfig | None = None,
) -> GroundContinuationResult:
    """Continue the Sanger trajectory from the SRTI to the ground (h = 0).

    Uses ``sanger_atm_rhs`` (SANGER_ATM, u_L = 1) with the frozen
    ``make_ground_event`` (terminal, descending crossing) and the Phase C
    production numerics by default.

    The input ``srti_state`` is never mutated.

    Raises
    ------
    RuntimeError
        If the ground event is not detected within the continuation span.
    """
    solver = solver or PRODUCTION_SOLVER_CONFIG

    state0 = np.asarray(srti_state, dtype=float)
    if state0.shape != (4,):
        raise ValueError("srti_state must have shape (4,).")

    ground_event = make_ground_event(env)
    sol = solve_ivp(
        lambda t, y: sanger_atm_rhs(t, y, env, vehicle, control),
        (srti_time, srti_time + _CONTINUATION_SPAN_S),
        state0,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=ground_event,
    )

    if not sol.success or sol.t_events[0].size == 0:
        raise RuntimeError(
            "Ground event not detected in the SRTI -> ground "
            f"continuation ({sol.message})."
        )

    ground_time = float(sol.t_events[0][0])
    ground_state = sol.sol(ground_time)

    time_grid = np.linspace(srti_time, ground_time, _OUTPUT_POINTS)
    state_grid = sol.sol(time_grid)

    return GroundContinuationResult(
        time=time_grid,
        state=state_grid,
        ground_time_s=ground_time,
        ground_state=ground_state,
        nfev=int(sol.nfev),
        njev=int(sol.njev),
        nlu=int(sol.nlu),
        success=bool(sol.success),
        message=sol.message,
    )
