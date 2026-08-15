"""D4 skip-cycle metrics / trajectory diagnostics (pure analysis layer).

Derives research metrics from an existing ``SangerHybridTrajectory``
(D3) without re-integrating anything:

    trajectory -> metrics

The completed skip cycle follows the D0 definition
(docs/phase_d/sanger_model_spec.md, §12):

    E_i -> P_i -> X_i -> A_i -> E_{i+1}

with E = atmosphere entry (the synthetic initial entry is allowed as the
E0 anchor), P = atmospheric pull-out, X = atmosphere exit, A = vacuum
apogee, E_{i+1} = next atmosphere entry.  ``skip_count`` is the number
of COMPLETED ``E_i -> E_{i+1}`` cycles; a terminal incomplete
atmospheric pass (E -> P -> SRTI) is reported separately and NEVER
counts as a skip.

The parser is strict: the chronological event history must satisfy the
E-P-X-A-E ordering; malformed histories (missing pull-out / exit /
apogee / next entry, wrong order, duplicate diagnostic) raise a
meaningful ``RuntimeError`` instead of silently fabricating a cycle.

Conventions reused from the frozen project:

* range: ``R = R_E * theta`` (identical to the Qian reporting
  convention in ``simulation/trajectory.py`` / ``models/dynamics.py``);
* altitude: ``h = r - R_E``;
* specific mechanical energy ``E`` and angular momentum ``H``: D1
  diagnostic primitives (``modes/sanger_hybrid.py``).

This layer never mutates the trajectory, never calls ``solve_ivp``, and
freezes no baseline numbers.
"""

from dataclasses import dataclass

import numpy as np

from hyptraj.models.parameters import EnvironmentParams
from hyptraj.modes.sanger_hybrid import (
    SANGER_ATM,
    SANGER_VAC,
    specific_angular_momentum,
    specific_mechanical_energy,
)
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    ATMOSPHERIC_PULLOUT,
    SRTI,
    SYNTHETIC_INITIAL_ENTRY,
    TERMINAL_GROUND_BEFORE_SRTI,
    TERMINAL_SRTI,
    VACUUM_APOGEE,
    SangerHybridTrajectory,
)

# Ratio-stability floors for the relative-drift denominators only; the
# raw quantities are never altered.
_ENERGY_FLOOR_JPKG = 1.0
_MOMENTUM_FLOOR_M2S = 1.0


# ---------------------------------------------------------------------------
# Frozen-convention helpers
# ---------------------------------------------------------------------------
def range_from_state(
    state: np.ndarray,
    env: EnvironmentParams,
) -> float:
    """Ground range from the frozen Qian convention ``R = R_E * theta``."""
    return float(env.earth_radius * state[1])


def altitude_from_state(
    state: np.ndarray,
    env: EnvironmentParams,
) -> float:
    """Altitude ``h = r - R_E`` (state[0] is the geocentric radius)."""
    return float(state[0] - env.earth_radius)


def velocity_from_state(state: np.ndarray) -> float:
    """Velocity magnitude ``v`` (state[2])."""
    return float(state[2])


# ---------------------------------------------------------------------------
# Per-cycle metrics
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SkipCycleMetrics:
    """Metrics of one COMPLETED skip cycle E -> P -> X -> A -> E'.

    All event quantities come from the D3 exact event states (the
    pull-out minimum and the vacuum apogee are never estimated from the
    sampled reconstruction grid).
    """

    index: int
    entry_is_synthetic: bool

    entry_time: float
    pullout_time: float
    exit_time: float
    apogee_time: float
    next_entry_time: float

    entry_state: np.ndarray
    pullout_state: np.ndarray
    exit_state: np.ndarray
    apogee_state: np.ndarray
    next_entry_state: np.ndarray

    entry_altitude_m: float
    pullout_altitude_m: float
    exit_altitude_m: float
    apogee_altitude_m: float
    next_entry_altitude_m: float

    entry_velocity_mps: float
    pullout_velocity_mps: float
    exit_velocity_mps: float
    apogee_velocity_mps: float
    next_entry_velocity_mps: float

    atmospheric_duration_s: float
    vacuum_duration_s: float
    cycle_duration_s: float

    atmospheric_range_m: float
    vacuum_range_m: float
    cycle_range_m: float

    atmospheric_speed_loss_mps: float
    atmospheric_energy_loss_jpkg: float

    vacuum_energy_drift_jpkg: float
    vacuum_energy_relative_drift: float
    vacuum_angular_momentum_drift: float
    vacuum_angular_momentum_relative_drift: float


# ---------------------------------------------------------------------------
# Terminal incomplete atmospheric pass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TerminalAtmosphericPassMetrics:
    """Diagnostics of the final atmospheric pass E -> P -> SRTI.

    NOT a completed skip cycle: it has no exit / vacuum arc / re-entry,
    so it is excluded from ``skip_count``.
    """

    entry_time: float
    pullout_time: float | None
    srti_time: float

    entry_velocity_mps: float
    pullout_velocity_mps: float | None
    srti_velocity_mps: float

    pullout_altitude_m: float | None
    srti_altitude_m: float

    atmospheric_duration_s: float
    range_increment_m: float
    mechanical_energy_loss_jpkg: float
    completed_exit: bool = False


# ---------------------------------------------------------------------------
# Global trajectory metrics
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SangerTrajectoryMetrics:
    """Global research metrics of one Sanger hybrid trajectory.

    Research trajectory only (terminates at SRTI); no ground
    compatibility metrics are included.
    """

    skip_count: int
    completed_cycles: tuple[SkipCycleMetrics, ...]

    atm_segment_count: int
    vac_segment_count: int

    total_atmospheric_time_s: float
    total_vacuum_time_s: float

    research_flight_time_s: float
    research_range_m: float

    maximum_altitude_m: float
    maximum_altitude_time_s: float

    terminal_kind: str
    terminal_time_s: float
    terminal_altitude_m: float
    terminal_velocity_mps: float

    terminal_incomplete_pass: TerminalAtmosphericPassMetrics | None


# ---------------------------------------------------------------------------
# Strict chronological cycle parser
# ---------------------------------------------------------------------------
def _parse_cycles(
    events,
    env: EnvironmentParams,
    terminal_kind: str,
) -> tuple[list[SkipCycleMetrics], dict | None]:
    """Parse the chronological event history into completed cycles.

    Returns ``(cycles, pending)`` where ``pending`` is the last (possibly
    terminal-incomplete) atmospheric pass.  Raises ``RuntimeError`` on
    any malformed history.
    """
    cycles: list[SkipCycleMetrics] = []
    pending: dict | None = None

    for e in events:
        if e.kind in (SYNTHETIC_INITIAL_ENTRY, ATMOSPHERE_ENTRY):
            if pending is not None:
                if pending["exit"] is None:
                    raise RuntimeError(
                        "Malformed event history: atmosphere entry before "
                        "the previous pass completed an atmosphere exit."
                    )
                if pending["apogee"] is None:
                    raise RuntimeError(
                        "Malformed event history: atmosphere entry before "
                        "the previous pass recorded a vacuum apogee."
                    )
                cycles.append(_build_cycle(pending, e, env, len(cycles)))
            pending = {
                "entry": e,
                "pullout": None,
                "exit": None,
                "apogee": None,
                "srti": None,
            }
        elif e.kind == ATMOSPHERIC_PULLOUT:
            if pending is None:
                raise RuntimeError(
                    "Malformed event history: pull-out without an entry "
                    "anchor."
                )
            if pending["pullout"] is not None:
                raise RuntimeError(
                    "Malformed event history: duplicate pull-out in one "
                    "atmospheric pass."
                )
            pending["pullout"] = e
        elif e.kind == ATMOSPHERE_EXIT:
            if pending is None:
                raise RuntimeError(
                    "Malformed event history: atmosphere exit without an "
                    "entry anchor."
                )
            if pending["pullout"] is None:
                raise RuntimeError(
                    "Malformed event history: atmosphere exit before "
                    "pull-out in the pass (E-P-X ordering)."
                )
            if pending["exit"] is not None:
                raise RuntimeError(
                    "Malformed event history: duplicate atmosphere exit "
                    "in one pass."
                )
            pending["exit"] = e
        elif e.kind == VACUUM_APOGEE:
            if pending is None:
                raise RuntimeError(
                    "Malformed event history: vacuum apogee without an "
                    "entry anchor."
                )
            if pending["exit"] is None:
                raise RuntimeError(
                    "Malformed event history: vacuum apogee before "
                    "atmosphere exit (X-A ordering)."
                )
            if pending["apogee"] is not None:
                raise RuntimeError(
                    "Malformed event history: duplicate vacuum apogee."
                )
            pending["apogee"] = e
        elif e.kind == SRTI:
            if pending is None or pending["entry"] is None:
                raise RuntimeError(
                    "Malformed event history: SRTI without an atmospheric "
                    "pass."
                )
            if pending["exit"] is not None:
                raise RuntimeError(
                    "Malformed event history: SRTI after atmosphere exit "
                    "without re-entry (a completed pass cannot end in "
                    "SRTI)."
                )
            if pending["pullout"] is None:
                raise RuntimeError(
                    "Malformed event history: SRTI without a pull-out in "
                    "the pass (D0 §13)."
                )
            pending["srti"] = e
            break
        elif e.kind == TERMINAL_GROUND_BEFORE_SRTI:
            if pending is None:
                raise RuntimeError(
                    "Malformed event history: ground without an "
                    "atmospheric pass."
                )
            pending["ground"] = e
            break
        else:
            raise RuntimeError(f"Unknown event kind in history: {e.kind!r}")

    if terminal_kind == TERMINAL_SRTI and (
        pending is None or pending.get("srti") is None
    ):
        raise RuntimeError(
            "Inconsistent trajectory: terminal_kind='srti' without an "
            "srti event in the history."
        )

    return cycles, pending


def _build_cycle(
    pending: dict,
    next_entry_event,
    env: EnvironmentParams,
    index: int,
) -> SkipCycleMetrics:
    entry_e = pending["entry"]
    pull_e = pending["pullout"]
    exit_e = pending["exit"]
    apo_e = pending["apogee"]

    s_entry = entry_e.state
    s_pull = pull_e.state
    s_exit = exit_e.state
    s_apo = apo_e.state
    s_next = next_entry_event.state

    t_e = entry_e.time
    t_p = pull_e.time
    t_x = exit_e.time
    t_a = apo_e.time
    t_e2 = next_entry_event.time

    r_atm = range_from_state(s_exit, env) - range_from_state(s_entry, env)
    r_vac = range_from_state(s_next, env) - range_from_state(s_exit, env)
    r_cyc = range_from_state(s_next, env) - range_from_state(s_entry, env)

    e_entry = specific_mechanical_energy(s_entry, env)
    e_exit = specific_mechanical_energy(s_exit, env)
    e_next = specific_mechanical_energy(s_next, env)
    h_exit = specific_angular_momentum(s_exit, env)
    h_next = specific_angular_momentum(s_next, env)

    e_drift = e_next - e_exit
    h_drift = h_next - h_exit

    return SkipCycleMetrics(
        index=index,
        entry_is_synthetic=bool(entry_e.is_synthetic),
        entry_time=t_e,
        pullout_time=t_p,
        exit_time=t_x,
        apogee_time=t_a,
        next_entry_time=t_e2,
        entry_state=s_entry,
        pullout_state=s_pull,
        exit_state=s_exit,
        apogee_state=s_apo,
        next_entry_state=s_next,
        entry_altitude_m=altitude_from_state(s_entry, env),
        pullout_altitude_m=altitude_from_state(s_pull, env),
        exit_altitude_m=altitude_from_state(s_exit, env),
        apogee_altitude_m=altitude_from_state(s_apo, env),
        next_entry_altitude_m=altitude_from_state(s_next, env),
        entry_velocity_mps=velocity_from_state(s_entry),
        pullout_velocity_mps=velocity_from_state(s_pull),
        exit_velocity_mps=velocity_from_state(s_exit),
        apogee_velocity_mps=velocity_from_state(s_apo),
        next_entry_velocity_mps=velocity_from_state(s_next),
        atmospheric_duration_s=t_x - t_e,
        vacuum_duration_s=t_e2 - t_x,
        cycle_duration_s=t_e2 - t_e,
        atmospheric_range_m=r_atm,
        vacuum_range_m=r_vac,
        cycle_range_m=r_cyc,
        atmospheric_speed_loss_mps=s_entry[2] - s_exit[2],
        atmospheric_energy_loss_jpkg=e_entry - e_exit,
        vacuum_energy_drift_jpkg=e_drift,
        vacuum_energy_relative_drift=abs(e_drift) / max(
            abs(e_exit), _ENERGY_FLOOR_JPKG
        ),
        vacuum_angular_momentum_drift=h_drift,
        vacuum_angular_momentum_relative_drift=abs(h_drift) / max(
            abs(h_exit), _MOMENTUM_FLOOR_M2S
        ),
    )


def _build_terminal_pass(
    pending: dict,
    env: EnvironmentParams,
) -> TerminalAtmosphericPassMetrics:
    entry_e = pending["entry"]
    pull_e = pending["pullout"]
    srti_e = pending["srti"]

    s_entry = entry_e.state
    s_srti = srti_e.state

    pullout_time = pull_e.time if pull_e is not None else None
    pullout_state = pull_e.state if pull_e is not None else None
    pullout_velocity = (
        velocity_from_state(pullout_state) if pullout_state is not None
        else None
    )
    pullout_altitude = (
        altitude_from_state(pullout_state, env)
        if pullout_state is not None else None
    )

    return TerminalAtmosphericPassMetrics(
        entry_time=entry_e.time,
        pullout_time=pullout_time,
        srti_time=srti_e.time,
        entry_velocity_mps=velocity_from_state(s_entry),
        pullout_velocity_mps=pullout_velocity,
        srti_velocity_mps=velocity_from_state(s_srti),
        pullout_altitude_m=pullout_altitude,
        srti_altitude_m=altitude_from_state(s_srti, env),
        atmospheric_duration_s=srti_e.time - entry_e.time,
        range_increment_m=(
            range_from_state(s_srti, env)
            - range_from_state(s_entry, env)
        ),
        mechanical_energy_loss_jpkg=(
            specific_mechanical_energy(s_entry, env)
            - specific_mechanical_energy(s_srti, env)
        ),
        completed_exit=False,
    )


# ---------------------------------------------------------------------------
# Public analysis entry point
# ---------------------------------------------------------------------------
def analyze_sanger_trajectory(
    trajectory: SangerHybridTrajectory,
    env: EnvironmentParams,
) -> SangerTrajectoryMetrics:
    """Derive research metrics from a D3 Sanger hybrid trajectory.

    Pure analysis: never integrates, never mutates the trajectory, and
    freezes no baseline numbers.
    """
    cycles, pending = _parse_cycles(
        trajectory.events, env, trajectory.terminal_kind)

    atm_segments = [s for s in trajectory.segments if s.mode == SANGER_ATM]
    vac_segments = [s for s in trajectory.segments if s.mode == SANGER_VAC]

    total_atm_time = sum(s.t_end - s.t_start for s in atm_segments)
    total_vac_time = sum(s.t_end - s.t_start for s in vac_segments)

    # Physical-extremum-based maximum altitude (never the plotting grid).
    candidates: list[tuple[float, np.ndarray]] = []
    if trajectory.segments:
        candidates.append((0.0, trajectory.segments[0].state_start))
    for e in trajectory.events:
        if e.kind == VACUUM_APOGEE:
            candidates.append((e.time, e.state))
    if trajectory.terminal_kind == TERMINAL_SRTI:
        srti = next(
            (e for e in trajectory.events if e.kind == SRTI), None)
        if srti is not None:
            candidates.append((srti.time, srti.state))
    candidates.append((trajectory.terminal_time, trajectory.terminal_state))
    t_max, s_max = max(
        candidates, key=lambda cs: altitude_from_state(cs[1], env))

    terminal_pass = None
    if trajectory.terminal_kind == TERMINAL_SRTI and pending is not None:
        terminal_pass = _build_terminal_pass(pending, env)

    terminal_state = trajectory.terminal_state
    return SangerTrajectoryMetrics(
        skip_count=len(cycles),
        completed_cycles=tuple(cycles),
        atm_segment_count=len(atm_segments),
        vac_segment_count=len(vac_segments),
        total_atmospheric_time_s=float(total_atm_time),
        total_vacuum_time_s=float(total_vac_time),
        research_flight_time_s=trajectory.terminal_time,
        research_range_m=range_from_state(terminal_state, env),
        maximum_altitude_m=altitude_from_state(s_max, env),
        maximum_altitude_time_s=t_max,
        terminal_kind=trajectory.terminal_kind,
        terminal_time_s=trajectory.terminal_time,
        terminal_altitude_m=altitude_from_state(terminal_state, env),
        terminal_velocity_mps=velocity_from_state(terminal_state),
        terminal_incomplete_pass=terminal_pass,
    )
