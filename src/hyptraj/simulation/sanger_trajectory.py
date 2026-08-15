"""Event-driven Sanger hybrid trajectory integrator (D3).

Combines the D1 continuous vector fields (``sanger_atm_rhs`` /
``sanger_vac_rhs``) with the D2 hybrid event primitives into the formal
event-driven Sanger trajectory integrator (D0 spec
docs/phase_d/sanger_model_spec.md, §3-§15, §16).

State machine (ATM/VAC strictly alternate):

    synthetic E0
         |
         v
    SANGER_ATM
         |  atmosphere_exit (h = h_atm, upward, terminal)
         v
    SANGER_VAC
         |  atmosphere_entry (h = h_atm, downward, terminal)
         v
    SANGER_ATM
         |  ...
         |
         |  srti_candidate (gamma: + -> -) + valid pass history
         v
       SRTI        <-- research endpoint

Semantics fixed by D0/D1/D2 and reused verbatim:

* initial state is the synthetic E0 (h0 = h_atm, gamma0 < 0): integration
  starts directly in SANGER_ATM; NO t = 0 atmosphere-entry event is
  generated (recorded as ``synthetic_initial_entry``, which is NOT a
  SciPy root event and NOT a real entry);
* transitions are exactly continuous: ``x_plus = x_minus`` (plain copy,
  NO epsilon state perturbation anywhere);
* pull-out and vacuum apogee are diagnostic events (non-terminal) and
  never restart a segment;
* the D2 SRTI candidate is only a raw ``gamma: + -> -`` root; formal SRTI
  QUALIFICATION is done here by the state machine: mode == SANGER_ATM,
  the current atmospheric pass has already observed pull-out, and the
  candidate occurs before the next atmosphere exit, with event altitude
  below the atmosphere boundary (numerical tolerance for assertion only);
* hybrid-sensitivity metadata (D0 §16) is stored on every real
  ATM <-> VAC switching event: event state x_e, f_minus, f_plus, event
  normal nabla G, mode_before, mode_after.  Saltation is NOT computed;
* solver numerics are inherited from Phase C
  (``PRODUCTION_SOLVER_CONFIG``) and must not be re-defined.

Safety guards (not physical endpoints): ``max_time`` and ``max_segments``
stop the loop instead of infinite-looping on an event bug; they set
``success = False`` with a clear message.  A ground hit before SRTI is
``ground_before_srti`` (fallback safety endpoint only; the compatibility
ground continuation belongs to D5).

Out of scope in D3: skip-cycle metrics, frozen baseline numbers, Qian
comparison, sweeps, STM / saltation / FTLE.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes.sanger_hybrid import (
    SANGER_ATM,
    SANGER_VAC,
    sanger_atm_rhs,
    sanger_vac_rhs,
)
from hyptraj.simulation.events import make_ground_event
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_events import (
    atmosphere_interface_normal,
    make_atmosphere_entry_event,
    make_atmosphere_exit_event,
    make_pullout_event,
    make_srti_candidate_event,
    make_vacuum_apogee_event,
)
from hyptraj.simulation.trajectory import SolverConfig

# --- Event kinds (unified D3 vocabulary, D0 spec §38) -----------------------
SYNTHETIC_INITIAL_ENTRY = "synthetic_initial_entry"
ATMOSPHERIC_PULLOUT = "atmospheric_pullout"
ATMOSPHERE_EXIT = "atmosphere_exit"
VACUUM_APOGEE = "vacuum_apogee"
ATMOSPHERE_ENTRY = "atmosphere_entry"
SRTI = "srti"

# --- Terminal kinds -----------------------------------------------------------
TERMINAL_SRTI = SRTI
TERMINAL_GROUND_BEFORE_SRTI = "ground_before_srti"
TERMINAL_MAX_TIME = "max_time"
TERMINAL_MAX_SEGMENTS = "max_segments"
TERMINAL_SOLVER_FAILURE = "solver_failure"

# Reconstruction grid per segment: uniform dense-output samples.  This is
# a trajectory-reconstruction resolution, not a frozen research number.
SEGMENT_SAMPLES = 400

# Numerical tolerance used ONLY for the SRTI altitude assertion
# (h_event < h_atm).  Never perturbs any state.
_SRTI_ALTITUDE_ASSERT_TOL_M = 1.0


@dataclass(frozen=True)
class HybridEventRecord:
    """One event of the Sanger hybrid trajectory.

    ``f_minus`` / ``f_plus`` / ``normal`` are stored only on real
    ATM <-> VAC switching events (future hybrid-sensitivity metadata,
    D0 spec §16).  Diagnostic and terminal events store ``None``.
    """

    index: int
    kind: str
    time: float
    state: np.ndarray
    mode_before: str | None
    mode_after: str | None
    is_synthetic: bool
    f_minus: np.ndarray | None = None
    f_plus: np.ndarray | None = None
    normal: np.ndarray | None = None


@dataclass(frozen=True)
class HybridSegment:
    """One continuous integration segment (one Sanger mode).

    ``t`` / ``y`` are a uniform reconstruction grid (shape ``(N,)`` /
    ``(4, N)``) obtained from the dense output; adaptive solver nodes are
    not a valid final data sampling (project convention).
    """

    index: int
    mode: str
    t_start: float
    t_end: float
    state_start: np.ndarray
    state_end: np.ndarray
    trigger_event: str
    t: np.ndarray
    y: np.ndarray
    nfev: int
    njev: int
    nlu: int
    success: bool
    message: str
    pullout_time: float | None = None
    pullout_state: np.ndarray | None = None
    apogee_time: float | None = None
    apogee_state: np.ndarray | None = None


@dataclass(frozen=True)
class SangerHybridTrajectory:
    """Full event-driven Sanger hybrid trajectory result.

    ``success`` is True only when the research endpoint SRTI was reached;
    any safety stop (max_time / max_segments / ground_before_srti /
    solver_failure) yields ``success = False`` with a clear message.
    """

    segments: tuple[HybridSegment, ...]
    events: tuple[HybridEventRecord, ...]
    terminal_kind: str
    terminal_time: float
    terminal_state: np.ndarray
    success: bool
    message: str

    def get_combined_history(self) -> tuple[np.ndarray, np.ndarray]:
        """Concatenate all segments into one chronological ``(t, y)``.

        Deterministic de-dup policy: the first sample of every segment
        except segment 0 is dropped (it equals the previous segment's
        last sample), so no transition state appears twice.
        """
        t_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []
        for i, seg in enumerate(self.segments):
            t = seg.t
            y = seg.y
            if i > 0:
                t = t[1:]
                y = y[:, 1:]
            t_parts.append(t)
            y_parts.append(y)
        return np.concatenate(t_parts), np.concatenate(y_parts, axis=1)


def _initial_state(env: EnvironmentParams, initial: InitialCondition) -> np.ndarray:
    """Frozen state convention: state = [r, theta, v, gamma]."""
    return np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ],
        dtype=float,
    )


def _run_segment(
    rhs: Callable[[float, np.ndarray], np.ndarray],
    t_start: float,
    state: np.ndarray,
    events: list,
    solver: SolverConfig,
    t_span_end: float,
):
    return solve_ivp(
        rhs,
        (t_start, t_span_end),
        state,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=events,
    )


def _make_segment(
    index: int,
    mode: str,
    t_start: float,
    state_start: np.ndarray,
    t_end: float,
    state_end: np.ndarray,
    trigger_event: str,
    sol,
    pullout_time: float | None = None,
    pullout_state: np.ndarray | None = None,
    apogee_time: float | None = None,
    apogee_state: np.ndarray | None = None,
) -> HybridSegment:
    t_grid = np.linspace(t_start, t_end, SEGMENT_SAMPLES)
    y_grid = sol.sol(t_grid)
    return HybridSegment(
        index=index,
        mode=mode,
        t_start=t_start,
        t_end=t_end,
        state_start=state_start.copy(),
        state_end=state_end.copy(),
        trigger_event=trigger_event,
        t=t_grid,
        y=y_grid,
        nfev=int(sol.nfev),
        njev=int(sol.njev),
        nlu=int(sol.nlu),
        success=bool(sol.success),
        message=sol.message,
        pullout_time=pullout_time,
        pullout_state=pullout_state,
        apogee_time=apogee_time,
        apogee_state=apogee_state,
    )


def _append_event(events: list, record: HybridEventRecord) -> None:
    """Append an event record enforcing strict time monotonicity.

    Real (non-synthetic) event times must be strictly increasing; a
    violation (duplicate / chatter) raises instead of being silently
    de-duplicated or filtered by an epsilon.  The single synthetic E0 is
    allowed at t0.
    """
    if not record.is_synthetic and events:
        if record.time <= events[-1].time:
            raise RuntimeError(
                "Event time monotonicity violated: "
                f"{record.kind} at t={record.time:.12e} after "
                f"{events[-1].kind} at t={events[-1].time:.12e} "
                "(duplicate/chatter protection)."
            )
    events.append(record)


def integrate_sanger_hybrid(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control: Callable[[float, np.ndarray], float],
    solver: SolverConfig | None = None,
    max_time: float = 5000.0,
    max_segments: int = 50,
) -> SangerHybridTrajectory:
    """Integrate the event-driven Sanger hybrid trajectory to the SRTI.

    Starts from the synthetic E0 in SANGER_ATM (no t = 0 entry event),
    alternates SANGER_ATM / SANGER_VAC segments through the D2 atmosphere
    exit / entry events, records the pull-out and vacuum apogee
    diagnostics, and terminates at the research endpoint SRTI once an
    atmospheric pass loses its skip capability (D0 spec §13).

    ``solver`` defaults to the Phase C ``PRODUCTION_SOLVER_CONFIG``.
    ``max_time`` / ``max_segments`` are safety guards, not physical
    endpoints: triggering one stops the loop with ``success = False`` and
    a clear message.

    Raises
    ------
    RuntimeError
        If an SRTI candidate occurs without a prior pull-out in the
        current atmospheric pass (invalid state-machine history), if a
        candidate is found above the atmosphere boundary, or if event
        times violate strict monotonicity.
    """
    solver = solver or PRODUCTION_SOLVER_CONFIG

    segments: list[HybridSegment] = []
    events: list[HybridEventRecord] = []
    event_index = 0

    t_current = 0.0
    state = _initial_state(env, initial)
    mode = SANGER_ATM
    has_pullout = False  # per-atmospheric-pass pull-out history

    # Synthetic E0 (D0 spec §9): the initial state sits on the interface
    # heading down; it is NOT a SciPy root event and NOT a real entry.
    _append_event(
        events,
        HybridEventRecord(
            index=event_index,
            kind=SYNTHETIC_INITIAL_ENTRY,
            time=t_current,
            state=state.copy(),
            mode_before=None,
            mode_after=SANGER_ATM,
            is_synthetic=True,
        ),
    )
    event_index += 1

    terminal_kind: str | None = None
    terminal_time = t_current
    terminal_state = state.copy()
    message = ""

    while True:
        if len(segments) >= max_segments:
            terminal_kind = TERMINAL_MAX_SEGMENTS
            terminal_time = segments[-1].t_end
            terminal_state = segments[-1].state_end.copy()
            message = (
                f"max_segments={max_segments} reached; trajectory "
                f"truncated after segment {len(segments) - 1} (safety "
                "guard, not a physical endpoint)."
            )
            break

        if t_current >= max_time:
            terminal_kind = TERMINAL_MAX_TIME
            terminal_time = t_current
            terminal_state = state.copy()
            message = (
                f"max_time={max_time} s reached before the research "
                "endpoint (safety guard, not a physical endpoint)."
            )
            break

        if mode == SANGER_ATM:
            segment_events = [
                make_atmosphere_exit_event(env),
                make_pullout_event(),
                make_srti_candidate_event(),
                make_ground_event(env),
            ]
            sol = _run_segment(
                lambda t, y: sanger_atm_rhs(t, y, env, vehicle, control),
                t_current,
                state,
                segment_events,
                solver,
                max_time,
            )

            t_pull = sol.t_events[1]
            pullout_time = None
            pullout_state = None
            if t_pull.size > 0:
                pullout_time = float(t_pull[0])
                pullout_state = sol.sol(pullout_time).copy()
                has_pullout = True
                _append_event(
                    events,
                    HybridEventRecord(
                        index=event_index,
                        kind=ATMOSPHERIC_PULLOUT,
                        time=pullout_time,
                        state=pullout_state,
                        mode_before=SANGER_ATM,
                        mode_after=SANGER_ATM,
                        is_synthetic=False,
                    ),
                )
                event_index += 1

            t_exit = sol.t_events[0]
            t_cand = sol.t_events[2]
            t_ground = sol.t_events[3]

            if t_exit.size > 0:
                # ATM -> VAC transition (D0 spec §7, §11).
                t_e = float(t_exit[0])
                x_e = sol.sol(t_e).copy()
                f_minus = sanger_atm_rhs(t_e, x_e, env, vehicle, control)
                f_plus = sanger_vac_rhs(t_e, x_e, env, vehicle)
                _append_event(
                    events,
                    HybridEventRecord(
                        index=event_index,
                        kind=ATMOSPHERE_EXIT,
                        time=t_e,
                        state=x_e,
                        mode_before=SANGER_ATM,
                        mode_after=SANGER_VAC,
                        is_synthetic=False,
                        f_minus=f_minus,
                        f_plus=f_plus,
                        normal=atmosphere_interface_normal(),
                    ),
                )
                event_index += 1
                segments.append(
                    _make_segment(
                        len(segments), SANGER_ATM, t_current, state,
                        t_e, x_e, ATMOSPHERE_EXIT, sol,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                # x_plus = x_minus: plain copy, no epsilon perturbation.
                mode = SANGER_VAC
                state = x_e.copy()
                t_current = t_e
                has_pullout = False
                continue

            if t_cand.size > 0:
                # SRTI candidate -> formal SRTI only with valid pass
                # history (D0 spec §13; D2 docstring).
                t_e = float(t_cand[0])
                x_e = sol.sol(t_e).copy()
                h_e = float(x_e[0] - env.earth_radius)
                if h_e > env.atmosphere_boundary + _SRTI_ALTITUDE_ASSERT_TOL_M:
                    raise RuntimeError(
                        "SRTI candidate above the atmosphere boundary: "
                        f"h = {h_e:.3f} m > h_atm = "
                        f"{env.atmosphere_boundary} m."
                    )
                if not has_pullout:
                    raise RuntimeError(
                        "SRTI candidate without a prior pull-out in the "
                        "current atmospheric pass (invalid pass history); "
                        "not classified as SRTI."
                    )
                _append_event(
                    events,
                    HybridEventRecord(
                        index=event_index,
                        kind=SRTI,
                        time=t_e,
                        state=x_e,
                        mode_before=SANGER_ATM,
                        mode_after=None,
                        is_synthetic=False,
                    ),
                )
                event_index += 1
                segments.append(
                    _make_segment(
                        len(segments), SANGER_ATM, t_current, state,
                        t_e, x_e, SRTI, sol,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                terminal_kind = TERMINAL_SRTI
                terminal_time = t_e
                terminal_state = x_e.copy()
                message = (
                    "Sanger research terminal interface reached "
                    "(skip-capability loss in an atmospheric pass)."
                )
                break

            if t_ground.size > 0:
                # Ground before SRTI: fallback safety endpoint only.
                t_e = float(t_ground[0])
                x_e = sol.sol(t_e).copy()
                _append_event(
                    events,
                    HybridEventRecord(
                        index=event_index,
                        kind=TERMINAL_GROUND_BEFORE_SRTI,
                        time=t_e,
                        state=x_e,
                        mode_before=SANGER_ATM,
                        mode_after=None,
                        is_synthetic=False,
                    ),
                )
                event_index += 1
                segments.append(
                    _make_segment(
                        len(segments), SANGER_ATM, t_current, state,
                        t_e, x_e, TERMINAL_GROUND_BEFORE_SRTI, sol,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                terminal_kind = TERMINAL_GROUND_BEFORE_SRTI
                terminal_time = t_e
                terminal_state = x_e.copy()
                message = (
                    "Ground reached before the SRTI: unexpected fallback "
                    "safety endpoint; Sanger research completion NOT "
                    "satisfied."
                )
                break

            if not sol.success:
                terminal_kind = TERMINAL_SOLVER_FAILURE
                terminal_time = float(sol.t[-1])
                terminal_state = sol.y[:, -1].copy()
                message = f"Solver failure in SANGER_ATM: {sol.message}"
                segments.append(
                    _make_segment(
                        len(segments), SANGER_ATM, t_current, state,
                        terminal_time, terminal_state,
                        TERMINAL_SOLVER_FAILURE, sol,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                break

            # No event: integration reached the t_span upper limit.
            terminal_kind = TERMINAL_MAX_TIME
            terminal_time = float(sol.t[-1])
            terminal_state = sol.y[:, -1].copy()
            message = (
                f"max_time={max_time} s reached in SANGER_ATM before the "
                "research endpoint (safety guard, not a physical "
                "endpoint)."
            )
            segments.append(
                _make_segment(
                    len(segments), SANGER_ATM, t_current, state,
                    terminal_time, terminal_state, TERMINAL_MAX_TIME, sol,
                    pullout_time=pullout_time,
                    pullout_state=pullout_state,
                )
            )
            break

        # ---- SANGER_VAC -----------------------------------------------
        segment_events = [
            make_atmosphere_entry_event(env),
            make_vacuum_apogee_event(),
        ]
        sol = _run_segment(
            lambda t, y: sanger_vac_rhs(t, y, env, vehicle),
            t_current,
            state,
            segment_events,
            solver,
            max_time,
        )

        t_apogee = sol.t_events[1]
        apogee_time = None
        apogee_state = None
        if t_apogee.size > 0:
            apogee_time = float(t_apogee[0])
            apogee_state = sol.sol(apogee_time).copy()
            _append_event(
                events,
                HybridEventRecord(
                    index=event_index,
                    kind=VACUUM_APOGEE,
                    time=apogee_time,
                    state=apogee_state,
                    mode_before=SANGER_VAC,
                    mode_after=SANGER_VAC,
                    is_synthetic=False,
                ),
            )
            event_index += 1

        t_entry = sol.t_events[0]

        if t_entry.size > 0:
            # VAC -> ATM transition (D0 spec §8, §14).
            t_e = float(t_entry[0])
            x_e = sol.sol(t_e).copy()
            f_minus = sanger_vac_rhs(t_e, x_e, env, vehicle)
            f_plus = sanger_atm_rhs(t_e, x_e, env, vehicle, control)
            _append_event(
                events,
                HybridEventRecord(
                    index=event_index,
                    kind=ATMOSPHERE_ENTRY,
                    time=t_e,
                    state=x_e,
                    mode_before=SANGER_VAC,
                    mode_after=SANGER_ATM,
                    is_synthetic=False,
                    f_minus=f_minus,
                    f_plus=f_plus,
                    normal=atmosphere_interface_normal(),
                ),
            )
            event_index += 1
            segments.append(
                _make_segment(
                    len(segments), SANGER_VAC, t_current, state,
                    t_e, x_e, ATMOSPHERE_ENTRY, sol,
                    apogee_time=apogee_time,
                    apogee_state=apogee_state,
                )
            )
            # x_plus = x_minus: plain copy; start a fresh atmospheric
            # pass with empty pull-out history.
            mode = SANGER_ATM
            state = x_e.copy()
            t_current = t_e
            has_pullout = False
            continue

        if not sol.success:
            terminal_kind = TERMINAL_SOLVER_FAILURE
            terminal_time = float(sol.t[-1])
            terminal_state = sol.y[:, -1].copy()
            message = f"Solver failure in SANGER_VAC: {sol.message}"
            segments.append(
                _make_segment(
                    len(segments), SANGER_VAC, t_current, state,
                    terminal_time, terminal_state,
                    TERMINAL_SOLVER_FAILURE, sol,
                    apogee_time=apogee_time,
                    apogee_state=apogee_state,
                )
            )
            break

        terminal_kind = TERMINAL_MAX_TIME
        terminal_time = float(sol.t[-1])
        terminal_state = sol.y[:, -1].copy()
        message = (
            f"max_time={max_time} s reached in SANGER_VAC before the "
            "research endpoint (safety guard, not a physical endpoint)."
        )
        segments.append(
            _make_segment(
                len(segments), SANGER_VAC, t_current, state,
                terminal_time, terminal_state, TERMINAL_MAX_TIME, sol,
                apogee_time=apogee_time,
                apogee_state=apogee_state,
            )
        )
        break

    return SangerHybridTrajectory(
        segments=tuple(segments),
        events=tuple(events),
        terminal_kind=terminal_kind,
        terminal_time=terminal_time,
        terminal_state=terminal_state,
        success=terminal_kind == TERMINAL_SRTI,
        message=message,
    )
