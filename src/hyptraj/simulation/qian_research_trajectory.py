"""Phase-F Qian research-terminal integration API (F0.1 amendment).

F0.1 — Qian Regime-Classification Access Amendment
(docs/phase_f/sensitivity_protocol.md, F0.1 section).

The frozen production entry point ``integrate_qian_glide`` raises
``RuntimeError`` when a stage fails OR its terminating event is missing
(two different causes share one exception path), so the public API cannot
distinguish ``GROUND_BEFORE_CAPTURE`` / ``GROUND_AFTER_CAPTURE_BEFORE_RTI`` /
horizon censor / numerical failure.  This module adds a strictly
classification-oriented, backward-compatible research-terminal integrator
that returns a structured result.

Hard constraints (F0.1):

* no second Qian dynamics set -- every RHS / event / control / solver
  constant is the frozen one:
    - ``atmospheric_dynamics`` (models/dynamics.py)
    - ``continuous_glide_rhs``, ``QEG_GLIDE`` (modes/continuous_glide.py)
    - ``make_capture_event``, ``make_qeg_end_event``, ``make_ground_event``
      (simulation/events.py, frozen terminal/direction semantics kept)
    - ``PRODUCTION_SOLVER_CONFIG`` (simulation/numerics.py)
    - ``DenseOutputCollector`` / ``DenseSolutionSegment`` (E0.1 observer)
* ``integrate_qian_glide`` is NOT modified: signature, historical output
  and RuntimeError behavior stay untouched (Phase B-E regression depends
  on it).
* terminal classification never parses RuntimeError / SciPy message text;
  the terminal reason comes from the structured result only.

Stage-level event policy (F0.1 §8–§11): each stage listens to its frozen
terminal event AND the frozen ground event simultaneously; the earlier
exact event time wins by explicit comparison (never by event-list
position).  If both roots fall within ``simultaneous_tol_s`` the terminal
kind is ``AMBIGUOUS_SIMULTANEOUS_EVENT`` (no arbitrary assignment to one
side).  A horizon stop without any event is ``MAX_TIME`` (computational
censor), never a physical no-event regime.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.modes.continuous_glide import (
    ENTRY_CAPTURE,
    QEG_GLIDE,
    continuous_glide_rhs,
)
from hyptraj.models.dynamics import atmospheric_dynamics
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.dense_output import (
    DenseOutputCollector,
    DenseSolutionSegment,
)
from hyptraj.simulation.events import (
    make_capture_event,
    make_ground_event,
    make_qeg_end_event,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.trajectory import SolverConfig

# ---------------------------------------------------------------------------
# Terminal kinds (F0.1 frozen vocabulary)
# ---------------------------------------------------------------------------
TERMINAL_RTI = "RTI"
TERMINAL_GROUND_BEFORE_CAPTURE = "GROUND_BEFORE_CAPTURE"
TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI = "GROUND_AFTER_CAPTURE_BEFORE_RTI"
TERMINAL_MAX_TIME = "MAX_TIME"
TERMINAL_SOLVER_FAILURE = "SOLVER_FAILURE"
TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT = "AMBIGUOUS_SIMULTANEOUS_EVENT"

TERMINAL_KINDS = (
    TERMINAL_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    TERMINAL_MAX_TIME,
    TERMINAL_SOLVER_FAILURE,
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
)

# Default integration horizon.  Compatible with the production Qian t_span
# upper bound ((0, 5000) in SolverConfig): the research API must not extend
# the horizon arbitrarily for the pilot (F0.1 §12).
DEFAULT_MAX_TIME_S = 5000.0

# Strict tie tolerance for near-simultaneous terminal events (F0.1 §10).
# Event roots are located from the dense output at solver tolerance; any
# two terminal events closer than this are reported as
# AMBIGUOUS_SIMULTANEOUS_EVENT instead of being assigned arbitrarily.
SIMULTANEOUS_EVENT_TOL_S = 1e-6


@dataclass(frozen=True)
class QianResearchEvent:
    """One exactly-localized terminal / switching event (F0.1 §6, §8–§9).

    ``state`` is the exact event state from the solver dense output
    (``sol.sol(t_event)``), never a sampled-grid approximation.
    """

    kind: str          # "capture" | "rti" | "ground"
    stage: str         # ENTRY_CAPTURE | QEG_GLIDE
    time_s: float
    state: np.ndarray


@dataclass(frozen=True)
class QianResearchTrajectory:
    """Structured Qian research-terminal result (F0.1 §6).

    ``success`` is True only when the research endpoint RTI was reached.
    ``success = False`` does NOT mean numerical failure: the physical
    terminal kinds (``GROUND_*``) and the horizon censor (``MAX_TIME``)
    are also ``success = False`` -- the Phase-F regime classifier must
    key on ``terminal_kind``, never on ``success`` alone.
    """

    success: bool
    terminal_kind: str
    terminal_time: float
    terminal_state: np.ndarray
    message: str
    segments: tuple[DenseSolutionSegment, ...]
    events: tuple[QianResearchEvent, ...]
    capture_event: QianResearchEvent | None
    rti_event: QianResearchEvent | None
    ground_event: QianResearchEvent | None
    mode_sequence: tuple[str, ...]
    initial_state: np.ndarray
    solver_config: SolverConfig
    max_time_s: float
    initial_conditions: dict[str, float]


# ---------------------------------------------------------------------------
# Stage helpers (frozen event factories / RHS only)
# ---------------------------------------------------------------------------
def _initial_state(env: EnvironmentParams, initial: InitialCondition) -> np.ndarray:
    """Frozen state convention: state = [r, theta, v, gamma] (radians)."""
    return np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ],
        dtype=float,
    )


def _run_stage(
    rhs: Callable[[float, np.ndarray], np.ndarray],
    t_start: float,
    state0: np.ndarray,
    events: list,
    solver: SolverConfig,
    t_end: float,
):
    """One ``solve_ivp`` call with the frozen numerical configuration."""
    return solve_ivp(
        rhs,
        (t_start, t_end),
        state0,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=events,
    )


def _first_root(sol, index: int) -> float | None:
    """Earliest root of the ``index``-th event, or None if never triggered."""
    if sol.t_events is None or len(sol.t_events) <= index:
        return None
    t_ev = sol.t_events[index]
    return float(t_ev[0]) if t_ev.size > 0 else None


def _earlier_event(
    t_a: float | None,
    t_b: float | None,
    tol_s: float,
) -> tuple[str | None, float | None]:
    """Explicit event-time comparison with a strict tie policy (F0.1 §10–§11).

    Returns ``(winner, time)`` with ``winner`` in ``{"a", "b", "tie"}`` or
    ``(None, None)`` when neither event triggered.  The comparison is made
    on exact event times only; event-list position never carries physical
    priority.
    """
    if t_a is None and t_b is None:
        return None, None
    if t_a is None:
        return "b", t_b
    if t_b is None:
        return "a", t_a
    if abs(t_a - t_b) <= tol_s:
        return "tie", min(t_a, t_b)
    return ("a", t_a) if t_a < t_b else ("b", t_b)


def _record_segment(
    collector: DenseOutputCollector,
    index: int,
    mode: str,
    t_start: float,
    t_end: float,
    sol,
) -> None:
    """Expose the already-computed dense interpolant (E0.1 observer)."""
    collector.add(
        DenseSolutionSegment(
            index=index,
            name=mode,
            mode=mode,
            t_start=t_start,
            t_end=t_end,
            solution=sol.sol,
        )
    )


def _assemble(
    success: bool,
    terminal_kind: str,
    terminal_time: float,
    terminal_state: np.ndarray,
    message: str,
    collector: DenseOutputCollector,
    events: list[QianResearchEvent],
    initial_state: np.ndarray,
    solver: SolverConfig,
    max_time: float,
    initial: InitialCondition,
    control,
    mode_sequence: tuple[str, ...],
) -> QianResearchTrajectory:
    capture = next((e for e in events if e.kind == "capture"), None)
    rti = next((e for e in events if e.kind == "rti"), None)
    ground = next((e for e in events if e.kind == "ground"), None)
    return QianResearchTrajectory(
        success=success,
        terminal_kind=terminal_kind,
        terminal_time=terminal_time,
        terminal_state=np.asarray(terminal_state, dtype=float).copy(),
        message=message,
        segments=collector.segments,
        events=tuple(events),
        capture_event=capture,
        rti_event=rti,
        ground_event=ground,
        mode_sequence=mode_sequence,
        initial_state=initial_state.copy(),
        solver_config=solver,
        max_time_s=max_time,
        initial_conditions={
            "h0_m": initial.altitude,
            "v0_mps": initial.velocity,
            "gamma0_deg": initial.flight_path_angle_deg,
            "theta0_rad": initial.range_angle,
            "K": getattr(control, "value", None),
        },
    )


def integrate_qian_research_trajectory(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control: Callable[[float, np.ndarray], float],
    solver: SolverConfig | None = None,
    dense_output_collector: DenseOutputCollector | None = None,
    max_time: float = DEFAULT_MAX_TIME_S,
    simultaneous_tol_s: float = SIMULTANEOUS_EVENT_TOL_S,
) -> QianResearchTrajectory:
    """Integrate the frozen Qian glide and classify its research terminal.

    The frozen three-mode semantics (ENTRY_CAPTURE -> QEG_GLIDE ->
    GROUND_CONTINUATION) and every RHS / event / solver constant are
    reused unchanged; only the *observability* is extended:

    * Stage ENTRY_CAPTURE listens to the frozen capture event AND the
      frozen ground event; ground first -> ``GROUND_BEFORE_CAPTURE``.
    * Stage QEG_GLIDE listens to the frozen QEG feasibility-loss (RTI)
      event AND the frozen ground event; ground first ->
      ``GROUND_AFTER_CAPTURE_BEFORE_RTI``.
    * No event within ``max_time`` -> ``MAX_TIME`` (computational censor).
    * Solver failure -> ``SOLVER_FAILURE``.
    * Both terminal events within ``simultaneous_tol_s`` ->
      ``AMBIGUOUS_SIMULTANEOUS_EVENT`` (never assigned arbitrarily).

    ``integrate_qian_glide`` and all Phase B-E behavior are untouched.
    ``ValueError`` from invalid inputs (e.g. ``K <= 0``) is NOT swallowed:
    the sweep layer catches it and classifies ``INVALID_INPUT``.

    Parameters
    ----------
    max_time:
        Explicit integration horizon [s]; horizon termination is
        classified ``MAX_TIME``, never as a physical no-event regime.
    simultaneous_tol_s:
        Strict tie tolerance for near-simultaneous terminal events.
    """
    solver = solver or PRODUCTION_SOLVER_CONFIG
    collector = dense_output_collector or DenseOutputCollector()

    state0 = _initial_state(env, initial)
    events: list[QianResearchEvent] = []
    segments_done: list[str] = []

    # ---- Stage 0: ENTRY_CAPTURE ------------------------------------------
    sol0 = _run_stage(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        0.0,
        state0,
        [make_capture_event(), make_ground_event(env)],
        solver,
        max_time,
    )

    if not sol0.success:
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_SOLVER_FAILURE,
            terminal_time=float(sol0.t[-1]),
            terminal_state=sol0.y[:, -1],
            message=f"Solver failure in stage {ENTRY_CAPTURE} "
                    f"({sol0.message}).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(),
        )

    t_cap = _first_root(sol0, 0)
    t_gnd0 = _first_root(sol0, 1)
    winner, t_e = _earlier_event(t_cap, t_gnd0, simultaneous_tol_s)

    if winner is None:
        # Horizon reached in ENTRY_CAPTURE with no event: computational
        # censor, NOT a physical no-RTI regime.
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_MAX_TIME,
            terminal_time=float(sol0.t[-1]),
            terminal_state=sol0.y[:, -1],
            message=f"No terminal event within max_time = {max_time} s "
                    f"(stage {ENTRY_CAPTURE}; computational censor).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(),
        )

    if winner == "tie":
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
            terminal_time=t_e,
            terminal_state=sol0.sol(t_e),
            message=f"Simultaneous capture / ground events within "
                    f"{simultaneous_tol_s} s at t = {t_e:.6f} s "
                    f"(stage {ENTRY_CAPTURE}).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(),
        )

    if winner == "b":
        # Ground before capture: physical terminal, capture never reached.
        state_gnd0 = sol0.sol(t_gnd0)
        _record_segment(collector, 0, ENTRY_CAPTURE, 0.0, t_gnd0, sol0)
        events.append(
            QianResearchEvent(
                kind="ground",
                stage=ENTRY_CAPTURE,
                time_s=t_gnd0,
                state=state_gnd0.copy(),
            )
        )
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_GROUND_BEFORE_CAPTURE,
            terminal_time=t_gnd0,
            terminal_state=state_gnd0,
            message=f"Ground reached before capture at t = {t_gnd0:.6f} s "
                    f"(physical terminal).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(ENTRY_CAPTURE,),
        )

    # Capture first: exact capture state from the dense output.
    state_cap = sol0.sol(t_cap)
    _record_segment(collector, 0, ENTRY_CAPTURE, 0.0, t_cap, sol0)
    events.append(
        QianResearchEvent(
            kind="capture",
            stage=ENTRY_CAPTURE,
            time_s=t_cap,
            state=state_cap.copy(),
        )
    )

    # ---- Stage 1: QEG_GLIDE ----------------------------------------------
    sol1 = _run_stage(
        lambda t, y: continuous_glide_rhs(QEG_GLIDE, t, y, env, vehicle, control),
        t_cap,
        state_cap,
        [make_qeg_end_event(env, vehicle, control), make_ground_event(env)],
        solver,
        max_time,
    )

    if not sol1.success:
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_SOLVER_FAILURE,
            terminal_time=float(sol1.t[-1]),
            terminal_state=sol1.y[:, -1],
            message=f"Solver failure in stage {QEG_GLIDE} "
                    f"({sol1.message}).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(ENTRY_CAPTURE,),
        )

    t_rti = _first_root(sol1, 0)
    t_gnd1 = _first_root(sol1, 1)
    winner, t_e = _earlier_event(t_rti, t_gnd1, simultaneous_tol_s)

    if winner is None:
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_MAX_TIME,
            terminal_time=float(sol1.t[-1]),
            terminal_state=sol1.y[:, -1],
            message=f"No terminal event within max_time = {max_time} s "
                    f"(stage {QEG_GLIDE}; computational censor).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(ENTRY_CAPTURE,),
        )

    if winner == "tie":
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
            terminal_time=t_e,
            terminal_state=sol1.sol(t_e),
            message=f"Simultaneous RTI / ground events within "
                    f"{simultaneous_tol_s} s at t = {t_e:.6f} s "
                    f"(stage {QEG_GLIDE}).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(ENTRY_CAPTURE,),
        )

    if winner == "b":
        # Ground after capture, before the RTI: physical terminal.
        state_gnd1 = sol1.sol(t_gnd1)
        _record_segment(collector, 1, QEG_GLIDE, t_cap, t_gnd1, sol1)
        events.append(
            QianResearchEvent(
                kind="ground",
                stage=QEG_GLIDE,
                time_s=t_gnd1,
                state=state_gnd1.copy(),
            )
        )
        return _assemble(
            success=False,
            terminal_kind=TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
            terminal_time=t_gnd1,
            terminal_state=state_gnd1,
            message=f"Ground reached after capture before RTI at "
                    f"t = {t_gnd1:.6f} s (physical terminal).",
            collector=collector,
            events=events,
            initial_state=state0,
            solver=solver,
            max_time=max_time,
            initial=initial,
            control=control,
            mode_sequence=(ENTRY_CAPTURE, QEG_GLIDE),
        )

    # RTI first: research success (QEG feasibility loss).
    state_rti = sol1.sol(t_rti)
    _record_segment(collector, 1, QEG_GLIDE, t_cap, t_rti, sol1)
    events.append(
        QianResearchEvent(
            kind="rti",
            stage=QEG_GLIDE,
            time_s=t_rti,
            state=state_rti.copy(),
        )
    )
    return _assemble(
        success=True,
        terminal_kind=TERMINAL_RTI,
        terminal_time=t_rti,
        terminal_state=state_rti,
        message=f"Research success: RTI (QEG feasibility loss) at "
                f"t = {t_rti:.6f} s.",
        collector=collector,
        events=events,
        initial_state=state0,
        solver=solver,
        max_time=max_time,
        initial=initial,
        control=control,
        mode_sequence=(ENTRY_CAPTURE, QEG_GLIDE),
    )
