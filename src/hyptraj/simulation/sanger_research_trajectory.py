"""Phase-F Sanger research event-resolution trajectory API (F2.1 amendment).

F2.1 — Sanger Grazing-Transition / Event-Qualification Observability
Amendment (docs/phase_f/f21_sanger_grazing_amendment.md).

The frozen production ``integrate_sanger_hybrid`` raises ``RuntimeError``
when an SRTI candidate is located above the atmosphere boundary.  The F2
coarse map hit this at (gamma0=-7.75 deg, K=3.125): the production
max_step=20 s solver stepped across an extremely shallow atmosphere
excursion (third VAC arc apogee ~16.9 m above h_atm, VAC duration ~5 s),
so the upward interface root (atmosphere_exit) was never returned while
the gamma downward crossing (the VAC apogee root, captured as an SRTI
candidate) was.  High-precision reference runs (REF-0.1 / REF-0.05) are
self-stable at SRTI_N3, proving the blocker is an event-resolution
problem, not a physical ambiguity.

This module adds a Phase-F research integrator that re-orchestrates the
frozen Sanger state machine with ONE additional observability branch:

* if the frozen ATM solve returns an SRTI candidate with
  ``h_candidate > h_atm`` while the atmosphere-exit event was NOT
  returned, and the pass already has a valid pull-out below the
  atmosphere boundary, the dense interpolant of the ALREADY COMPUTED ATM
  solution is used to locate the missing upward interface root
  ``h(t) - h_atm = 0`` (brentq, exact root; never a sampled row, never
  linear interpolation, never epsilon perturbation);
* the recovered root must satisfy ``t_pullout < t_rec < t_candidate``,
  a tiny interface residual, ``gamma(t_rec) > 0`` and
  ``dh/dt = v sin(gamma) > 0`` (true transverse upward exit), otherwise
  NO recovery is performed and the terminal kind is
  ``GRAZING_OR_UNRESOLVED_EVENT``;
* a recovered exit truncates the ATM segment at the recovered root and
  switches to the frozen SANGER_VAC with ``x_plus = x_minus`` (strictly
  continuous), exactly like a normal atmosphere-exit event, plus
  ``event_resolution = "DENSE_RECOVERED"`` metadata.  No new physical
  switch is invented; the frozen dynamics / event surfaces / reset
  semantics are untouched.

Frozen constraints (F2.1):

* ``sanger_trajectory.py``, ``sanger_events.py``, ``sanger_hybrid.py``
  and ``PRODUCTION_SOLVER_CONFIG`` are NOT modified;
* every RHS / event factory / diagnostic helper is the frozen one
  (``sanger_atm_rhs``, ``sanger_vac_rhs``, ``make_atmosphere_exit_event``,
  ``make_atmosphere_entry_event``, ``make_pullout_event``,
  ``make_vacuum_apogee_event``, ``make_srti_candidate_event``,
  ``make_ground_event``, ``atmosphere_interface_value``,
  ``atmosphere_interface_normal``);
* recovery is decided from structured event results / candidate state /
  interface value / pull-out history -- NEVER from exception-message text
  (frozen RuntimeError is used only for the regression-side audit);
* ``candidate_overshoot_m = h_candidate - h_atm`` is a qualification
  probe / numerical diagnostic only, NOT a physical post-exit state;
* recovered interface events MUST be verified against the strict
  reference (REF-0.1 / REF-0.05) before entering the canonical map.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.optimize import brentq

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
from hyptraj.simulation.dense_output import (
    DenseOutputCollector,
    DenseSolutionSegment,
)
from hyptraj.simulation.events import make_ground_event
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_events import (
    atmosphere_interface_normal,
    atmosphere_interface_value,
    make_atmosphere_entry_event,
    make_atmosphere_exit_event,
    make_pullout_event,
    make_srti_candidate_event,
    make_vacuum_apogee_event,
)
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    ATMOSPHERIC_PULLOUT,
    SRTI,
    SYNTHETIC_INITIAL_ENTRY,
    TERMINAL_GROUND_BEFORE_SRTI,
    TERMINAL_MAX_SEGMENTS,
    TERMINAL_MAX_TIME,
    TERMINAL_SOLVER_FAILURE,
    TERMINAL_SRTI,
    VACUUM_APOGEE,
    HybridEventRecord,
    HybridSegment,
    SangerHybridTrajectory,
    SolverConfig,
    _append_event,
    _initial_state,
    _make_segment,
    _run_segment,
)

# ---------------------------------------------------------------------------
# Terminal kinds (F2.1 frozen additions)
# ---------------------------------------------------------------------------
TERMINAL_GRAZING_OR_UNRESOLVED_EVENT = "grazing_or_unresolved_event"

# Event-resolution vocabulary.
RESOLUTION_SOLVER_EVENT = "SOLVER_EVENT"
RESOLUTION_DENSE_RECOVERED = "DENSE_RECOVERED"

# Research event-resolution implementation version (F2 cache provenance).
SANGER_RESEARCH_EVENT_RESOLUTION_VERSION = "v1"

# Numerical tolerance for the recovered interface residual.
_RECOVERED_EXIT_RESIDUAL_TOL_M = 1e-6


@dataclass(frozen=True)
class RecoveredInterfaceEvent:
    """One dense-recovered upward interface root (F2.1 §12, §14).

    ``resolution`` is ``"DENSE_RECOVERED"`` (root located from the dense
    interpolant of the already-computed ATM solution) or
    ``"SOLVER_EVENT"`` (returned normally by ``solve_ivp``).
    """

    kind: str  # always "atmosphere_exit"
    time_s: float
    state: np.ndarray
    resolution: str
    interface_residual_m: float
    exit_gamma_rad: float
    exit_dhdt_mps: float
    candidate_overshoot_m: float | None
    mode_before: str = SANGER_ATM
    mode_after: str = SANGER_VAC


@dataclass(frozen=True)
class SangerResearchTrajectory:
    """Phase-F Sanger research trajectory (F2.1 §9).

    Wraps the FROZEN ``SangerHybridTrajectory`` container (so all frozen
    downstream analysis -- ``analyze_sanger_trajectory``,
    ``classify_sanger_regime``, F1/F2 row generation -- works unchanged)
    and adds the Phase-F observability metadata: recovered interface
    events, per-pass grazing diagnostics, production event-resolution
    metadata and the solver configuration.
    """

    trajectory: SangerHybridTrajectory
    recovered_events: tuple[RecoveredInterfaceEvent, ...]
    grazing_diagnostics: tuple[dict, ...]
    solver_config: SolverConfig
    max_time: float
    max_segments: int
    initial_conditions: dict[str, float]

    # -- delegation to the frozen container --------------------------------
    @property
    def success(self) -> bool:
        return self.trajectory.success

    @property
    def terminal_kind(self) -> str:
        return self.trajectory.terminal_kind

    @property
    def terminal_time(self) -> float:
        return self.trajectory.terminal_time

    @property
    def terminal_state(self) -> np.ndarray:
        return self.trajectory.terminal_state

    @property
    def message(self) -> str:
        return self.trajectory.message

    @property
    def segments(self) -> tuple[HybridSegment, ...]:
        return self.trajectory.segments

    @property
    def events(self) -> tuple[HybridEventRecord, ...]:
        return self.trajectory.events

    @property
    def event_resolution(self) -> str:
        """Sweep-level resolution label for this trajectory."""
        if self.terminal_kind == TERMINAL_GRAZING_OR_UNRESOLVED_EVENT:
            return "GRAZING_OR_UNRESOLVED"
        if self.recovered_events:
            return RESOLUTION_DENSE_RECOVERED
        return RESOLUTION_SOLVER_EVENT

    @property
    def initial_state(self) -> np.ndarray | None:
        if self.trajectory.segments:
            return self.trajectory.segments[0].state_start
        return None


# ---------------------------------------------------------------------------
# Pure recovery primitive (unit-testable; no solver, no physics copies)
# ---------------------------------------------------------------------------
def recover_interface_exit(
    sol,
    env: EnvironmentParams,
    t_pullout: float,
    t_candidate: float,
    candidate_overshoot_m: float,
) -> RecoveredInterfaceEvent | None:
    """Locate the missing upward interface root on ``[t_pullout, t_cand]``.

    The dense interpolant of the already-computed ATM solution is used to
    solve ``h(t) - h_atm = 0`` with ``brentq``.  The recovered root must
    satisfy (F2.1 §12):

    * ``t_pullout < t_rec < t_candidate``;
    * ``|h(t_rec) - h_atm|`` below the residual tolerance;
    * ``gamma(t_rec) > 0``  (equivalently ``dh/dt = v sin(gamma) > 0``:
      a true transverse upward exit).

    Returns ``None`` (no recovery) when any check fails -- the caller
    then reports ``GRAZING_OR_UNRESOLVED_EVENT``.
    """
    h_atm = env.atmosphere_boundary

    def g(t: float) -> float:
        state = np.asarray(sol.sol(t), dtype=float)
        return float(state[0] - env.earth_radius - h_atm)

    g_pull = g(t_pullout)
    g_cand = g(t_candidate)
    if g_pull >= 0.0 or g_cand <= 0.0:
        # Bracketing precondition broken: the candidate does not actually
        # lie above the interface relative to the pull-out.
        return None
    if not (t_pullout < t_candidate):
        return None

    try:
        t_rec = float(brentq(g, t_pullout, t_candidate, xtol=1e-12))
    except ValueError:
        return None

    if not (t_pullout < t_rec < t_candidate):
        return None

    state_rec = np.asarray(sol.sol(t_rec), dtype=float)
    residual = float(abs(state_rec[0] - env.earth_radius - h_atm))
    if residual > _RECOVERED_EXIT_RESIDUAL_TOL_M:
        return None

    gamma_rec = float(state_rec[3])
    dhdt = float(state_rec[2] * np.sin(state_rec[3]))
    if not (gamma_rec > 0.0 and dhdt > 0.0):
        return None

    return RecoveredInterfaceEvent(
        kind=ATMOSPHERE_EXIT,
        time_s=t_rec,
        state=state_rec.copy(),
        resolution=RESOLUTION_DENSE_RECOVERED,
        interface_residual_m=residual,
        exit_gamma_rad=gamma_rec,
        exit_dhdt_mps=dhdt,
        candidate_overshoot_m=candidate_overshoot_m,
        mode_before=SANGER_ATM,
        mode_after=SANGER_VAC,
    )


# ---------------------------------------------------------------------------
# Research integrator (re-orchestration of the frozen state machine)
# ---------------------------------------------------------------------------
def integrate_sanger_research_trajectory(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control: Callable[[float, np.ndarray], float],
    solver: SolverConfig | None = None,
    dense_output_collector: DenseOutputCollector | None = None,
    max_time: float = 5000.0,
    max_segments: int = 50,
) -> SangerResearchTrajectory:
    """Integrate the frozen Sanger hybrid trajectory with F2.1 recovery.

    Identical to ``integrate_sanger_hybrid`` for every trajectory whose
    SRTI candidate stays below the atmosphere boundary (no recovery).  The
    only behavioural difference: an SRTI candidate ABOVE the boundary with
    a valid pull-out history triggers dense-output interface-root
    recovery instead of the frozen ``RuntimeError`` (see module docstring
    and F2.1 §11–§14).
    """
    solver = solver or PRODUCTION_SOLVER_CONFIG
    collector = (dense_output_collector if dense_output_collector is not None else DenseOutputCollector())

    segments: list[HybridSegment] = []
    events: list[HybridEventRecord] = []
    recovered: list[RecoveredInterfaceEvent] = []
    pass_diagnostics: list[dict] = []
    event_index = 0

    t_current = 0.0
    state = _initial_state(env, initial)
    mode = SANGER_ATM
    has_pullout = False

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
    pass_index = 0

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

            # Grazing diagnostics for this ATM pass (F2.1 §19).
            cand_state = (
                np.asarray(sol.sol(float(t_cand[0])), dtype=float)
                if t_cand.size > 0 else None
            )
            diag: dict = {
                "pass_index": pass_index,
                "candidate_seen": t_cand.size > 0,
                "candidate_altitude_m": (
                    float(cand_state[0] - env.earth_radius)
                    if cand_state is not None else None
                ),
                "candidate_overshoot_m": (
                    float(cand_state[0] - env.earth_radius
                          - env.atmosphere_boundary)
                    if cand_state is not None else None
                ),
                "exit_detected_by_solver": t_exit.size > 0,
                "exit_recovered": False,
                "recovered_exit_time_s": None,
                "interface_residual_m": None,
                "exit_gamma_rad": None,
                "exit_dhdt_mps": None,
                "pullout_time_s": pullout_time,
            }

            if t_exit.size > 0:
                # Normal detected exit (F2.1 §15): use the solver event
                # as-is, never re-root-solve.
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
                        dense_output_collector=collector,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                mode = SANGER_VAC
                state = x_e.copy()
                t_current = t_e
                has_pullout = False
                pass_index += 1
                pass_diagnostics.append(diag)
                continue

            if t_cand.size > 0:
                t_c = float(t_cand[0])
                x_c = sol.sol(t_c).copy()
                h_c = float(x_c[0] - env.earth_radius)
                diag["candidate_altitude_m"] = h_c
                diag["candidate_overshoot_m"] = (
                    h_c - env.atmosphere_boundary)

                if h_c <= env.atmosphere_boundary:
                    # Candidate below the boundary: formal SRTI
                    # qualification, identical to the frozen semantics
                    # (F2.1 §16).  No recovery.
                    if not has_pullout:
                        terminal_kind = TERMINAL_GRAZING_OR_UNRESOLVED_EVENT
                        terminal_time = t_c
                        terminal_state = x_c.copy()
                        message = (
                            "SRTI candidate below the boundary without a "
                            "prior pull-out (invalid pass history); "
                            "structured as GRAZING_OR_UNRESOLVED_EVENT "
                            "instead of the frozen RuntimeError."
                        )
                        pass_diagnostics.append(diag)
                        break
                    _append_event(
                        events,
                        HybridEventRecord(
                            index=event_index,
                            kind=SRTI,
                            time=t_c,
                            state=x_c,
                            mode_before=SANGER_ATM,
                            mode_after=None,
                            is_synthetic=False,
                        ),
                    )
                    event_index += 1
                    segments.append(
                        _make_segment(
                            len(segments), SANGER_ATM, t_current, state,
                            t_c, x_c, SRTI, sol,
                            dense_output_collector=collector,
                            pullout_time=pullout_time,
                            pullout_state=pullout_state,
                        )
                    )
                    terminal_kind = TERMINAL_SRTI
                    terminal_time = t_c
                    terminal_state = x_c.copy()
                    message = (
                        "Sanger research terminal interface reached "
                        "(skip-capability loss in an atmospheric pass)."
                    )
                    pass_diagnostics.append(diag)
                    break

                # Candidate ABOVE the boundary with the exit missing:
                # F2.1 dense recovery branch.
                if not has_pullout or pullout_time is None:
                    # No valid pull-out history: cannot recover.
                    terminal_kind = TERMINAL_GRAZING_OR_UNRESOLVED_EVENT
                    terminal_time = t_c
                    terminal_state = x_c.copy()
                    message = (
                        "SRTI candidate above the atmosphere boundary "
                        "without a valid pull-out; structured as "
                        "GRAZING_OR_UNRESOLVED_EVENT."
                    )
                    pass_diagnostics.append(diag)
                    break

                rec = recover_interface_exit(
                    sol, env, pullout_time, t_c,
                    h_c - env.atmosphere_boundary,
                )
                if rec is None:
                    terminal_kind = TERMINAL_GRAZING_OR_UNRESOLVED_EVENT
                    terminal_time = t_c
                    terminal_state = x_c.copy()
                    message = (
                        "SRTI candidate above the atmosphere boundary and "
                        "no transverse recovered interface root; "
                        "structured as GRAZING_OR_UNRESOLVED_EVENT "
                        "(strict-reference decision required)."
                    )
                    pass_diagnostics.append(diag)
                    break

                # Recovered transverse upward exit (F2.1 §13–§14).
                diag["exit_recovered"] = True
                diag["recovered_exit_time_s"] = rec.time_s
                diag["interface_residual_m"] = rec.interface_residual_m
                diag["exit_gamma_rad"] = rec.exit_gamma_rad
                diag["exit_dhdt_mps"] = rec.exit_dhdt_mps
                x_rec = rec.state
                f_minus = sanger_atm_rhs(
                    rec.time_s, x_rec, env, vehicle, control)
                f_plus = sanger_vac_rhs(rec.time_s, x_rec, env, vehicle)
                _append_event(
                    events,
                    HybridEventRecord(
                        index=event_index,
                        kind=ATMOSPHERE_EXIT,
                        time=rec.time_s,
                        state=x_rec,
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
                        rec.time_s, x_rec, ATMOSPHERE_EXIT, sol,
                        dense_output_collector=collector,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                recovered.append(rec)
                # x_plus = x_minus: plain copy, strictly continuous.
                mode = SANGER_VAC
                state = x_rec.copy()
                t_current = rec.time_s
                has_pullout = False
                pass_index += 1
                pass_diagnostics.append(diag)
                continue

            if t_ground.size > 0:
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
                        dense_output_collector=collector,
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
                pass_diagnostics.append(diag)
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
                        dense_output_collector=collector,
                        pullout_time=pullout_time,
                        pullout_state=pullout_state,
                    )
                )
                pass_diagnostics.append(diag)
                break

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
                    dense_output_collector=collector,
                    pullout_time=pullout_time,
                    pullout_state=pullout_state,
                )
            )
            pass_diagnostics.append(diag)
            break

        # ---- SANGER_VAC (identical to frozen) -----------------------------
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
            t_e = float(t_entry[0])
            if t_e <= t_current:
                # Degenerate zero-duration VAC arc (grazing limit): the
                # atmosphere entry is located at (or before) the arc
                # start.  This happens after a recovered exit at the
                # tangency limit where the new skip degenerates.  The
                # frozen chatter guard would raise; instead this is
                # structured as GRAZING_OR_UNRESOLVED_EVENT so the sweep
                # can run the strict-reference decision (F2.1 §12, F3).
                terminal_kind = TERMINAL_GRAZING_OR_UNRESOLVED_EVENT
                terminal_time = t_current
                terminal_state = state.copy()
                message = (
                    "Degenerate zero-duration VAC arc after an interface "
                    "event at t = {:.6f} s (grazing limit); structured as "
                    "GRAZING_OR_UNRESOLVED_EVENT.".format(t_current)
                )
                break
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
                    dense_output_collector=collector,
                    apogee_time=apogee_time,
                    apogee_state=apogee_state,
                )
            )
            # x_plus = x_minus: plain copy; fresh atmospheric pass.
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
                    dense_output_collector=collector,
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
                dense_output_collector=collector,
                apogee_time=apogee_time,
                apogee_state=apogee_state,
            )
        )
        break

    # Assemble the frozen container (identical semantics) + F2.1 metadata.
    frozen = SangerHybridTrajectory(
        segments=tuple(segments),
        events=tuple(events),
        terminal_kind=terminal_kind,
        terminal_time=terminal_time,
        terminal_state=terminal_state.copy(),
        success=terminal_kind == TERMINAL_SRTI,
        message=message,
    )
    return SangerResearchTrajectory(
        trajectory=frozen,
        recovered_events=tuple(recovered),
        grazing_diagnostics=tuple(pass_diagnostics),
        solver_config=solver,
        max_time=max_time,
        max_segments=max_segments,
        initial_conditions={
            "h0_m": initial.altitude,
            "v0_mps": initial.velocity,
            "gamma0_deg": initial.flight_path_angle_deg,
            "theta0_rad": initial.range_angle,
            "K": getattr(control, "value", None),
        },
    )
