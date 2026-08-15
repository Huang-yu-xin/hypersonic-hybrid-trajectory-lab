"""Phase E comparison data / alignment infrastructure (E1).

Maps the frozen Qian research trajectory (ENTRY_CAPTURE + QEG_GLIDE to
RTI) and the frozen Sanger research trajectory (synthetic E0 ... SRTI)
onto one continuous comparison API, per the E0 protocol
(docs/phase_e/comparison_protocol.md) and its E0.1 amendment.

Design contract (E0 §10, §17, E0.1):

* continuous evaluation uses the REAL solver dense interpolants exposed
  by the E0.1 ``DenseOutputCollector`` -- no sampled-grid checkpoints,
  no nearest CSV row, no re-integration, no monkeypatch;
* exact event states are preferred at event times;
* the internal state ordering stays the frozen ``[r, theta, v, gamma]``;
  ``ComparisonState`` is a read-only analysis view;
* the range convention is the frozen ``R = R_E * theta`` and the
  specific mechanical energy is ``E = v^2/2 - mu/r`` with ``mu`` derived
  from the frozen environment (thin delegation to the frozen helpers);
* the hybrid mode convention is right-continuous: at a switching event
  time ``t_e``, ``mode_at_time(t_e)`` returns the post-transition mode
  (Qian capture: ATM / QEG_GLIDE; Sanger exit: VAC; Sanger entry: ATM);
  at the terminal event the pre-terminal physical mode is returned
  (Qian RTI: ATM; Sanger SRTI: ATM);
* downrange monotonicity is validated from the dense dynamics before any
  common-range inversion is allowed;
* cumulative atmospheric exposure is exact piecewise interval arithmetic
  (``I_ATM = 1`` on ATM, ``0`` on VAC), and the exposure inverse handles
  the Sanger VAC plateaus explicitly (never selects an arbitrary time).

This layer never calls ``solve_ivp``, never mutates frozen results, and
produces no formal Phase-E comparison numbers.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy.optimize import brentq

from hyptraj.modes.continuous_glide import ENTRY_CAPTURE, QEG_GLIDE
from hyptraj.modes.sanger_hybrid import (
    SANGER_ATM,
    SANGER_VAC,
    specific_mechanical_energy,
)
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.dense_output import DenseOutputCollector
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_trajectory import (
    SRTI,
    SYNTHETIC_INITIAL_ENTRY,
    integrate_sanger_hybrid,
)
from hyptraj.simulation.trajectory import (
    SolverConfig,
    TrajectoryResult,
    integrate_qian_glide,
)

# ---------------------------------------------------------------------------
# Frozen-semantic constants
# ---------------------------------------------------------------------------
ATM = "ATM"
VAC = "VAC"

QIAN_TERMINAL_KIND = "RTI"
QIAN_TERMINAL_SEMANTICS = "QEG_FEASIBILITY_LOSS"
SANGER_TERMINAL_KIND = "SRTI"
SANGER_TERMINAL_SEMANTICS = "SKIP_CAPABILITY_LOSS"

# Event-time equality tolerance: exact float equality is tried first
# (event times stored in the trajectory ARE the floats of the dense
# segment boundaries / event records); a query is snapped to an event
# only within this very tight window, so a genuine interior point is
# never absorbed into an event state.  The scale is commensurate with
# float64 event-localization arithmetic on ~1e3 s timescales (ulp
# ~1e-13 s) and far below any physical or reporting timescale.
EVENT_TIME_TOL_S = 1e-9

# Same scale for plateau exposure-value equality: cumulative exposures
# are sums of a few float64 durations (~5 terms), so equality at the
# 1e-9 s level can never absorb a genuinely UNIQUE exposure, which maps
# to a distinct interior time.
EXPOSURE_TOL_S = 1e-9

# Range-inversion root-finding policy: clearly tighter than the later
# Phase-E reporting precision (km / s) while not pretending to exceed
# the underlying DOP853 accuracy by many orders of magnitude.
ROOT_XTOL_S = 1e-10
ROOT_RTOL = 1e-12

# Dense validation mesh per segment for the monotonicity diagnostic.
# This is ONLY a derivative-sign validation mesh (E0 §16); it never
# serves as a formal comparison checkpoint.
MONOTONICITY_MESH_POINTS = 250


@dataclass(frozen=True)
class ComparisonState:
    """Read-only continuous state view of one comparison trajectory.

    ``state_raw`` is a private copy of the frozen ``[r, theta, v, gamma]``
    state (mutating it cannot affect the underlying trajectory), and
    every scalar field is derived from that copy.
    """

    time_s: float
    state_raw: np.ndarray
    trajectory_name: str
    mode: str
    source_mode: str

    @property
    def radius_m(self) -> float:
        return float(self.state_raw[0])

    @property
    def altitude_m(self) -> float:
        return float(self.state_raw[0] - self._earth_radius)

    @property
    def theta_rad(self) -> float:
        return float(self.state_raw[1])

    @property
    def range_m(self) -> float:
        return float(self._earth_radius * self.state_raw[1])

    @property
    def velocity_mps(self) -> float:
        return float(self.state_raw[2])

    @property
    def gamma_rad(self) -> float:
        return float(self.state_raw[3])

    @property
    def specific_mechanical_energy_jpkg(self) -> float:
        return specific_mechanical_energy(self.state_raw, self._environment)

    _environment: EnvironmentParams = field(repr=False, compare=False)
    _earth_radius: float = field(repr=False, compare=False)


@dataclass(frozen=True)
class ComparisonEvent:
    """Light event record of a comparison trajectory (exact states)."""

    kind: str
    time_s: float
    source_mode_before: str | None
    source_mode_after: str | None
    state: np.ndarray


@dataclass(frozen=True)
class DenseSegmentView:
    """One continuous segment of the comparison trajectory.

    ``dense_solution`` is the true solver dense interpolant produced by
    the frozen integrator (E0.1); ``state_start`` / ``state_end`` are the
    exact stored event states at the boundaries.
    """

    index: int
    name: str
    source_mode: str
    normalized_mode: str
    t_start: float
    t_end: float
    dense_solution: object
    state_start: np.ndarray
    state_end: np.ndarray


@dataclass(frozen=True)
class RangeMonotonicityResult:
    """Structured downrange-monotonicity diagnostic (E0 §16).

    The minimum of ``dR/dt = R_E * v * cos(gamma) / r`` is evaluated on a
    dense validation mesh per segment from the REAL dense solutions.
    """

    is_strictly_monotone: bool
    minimum_drange_dt: float
    minimum_cos_gamma: float
    minimum_velocity: float
    diagnostic_sample_count: int


class AtmosphericExposureInverseStatus(Enum):
    UNIQUE = "UNIQUE"
    PLATEAU = "PLATEAU"


@dataclass(frozen=True)
class AtmosphericExposureInverseResult:
    """Result of the atmospheric-exposure inverse (E0 §23-§25).

    ``time_s`` is set only for ``UNIQUE``; ``plateau_start_s`` /
    ``plateau_end_s`` are set only for ``PLATEAU``.  No arbitrary
    earliest / latest / midpoint selection is ever performed.
    """

    status: AtmosphericExposureInverseStatus
    tau_s: float
    time_s: float | None = None
    plateau_start_s: float | None = None
    plateau_end_s: float | None = None


@dataclass(frozen=True)
class AlignmentResult:
    """Structural equality of the two realized comparison trajectories."""

    initial_state_equal: bool
    environment_equal: bool
    vehicle_equal: bool
    K_equal: bool
    solver_equal: bool

    @property
    def all_equal(self) -> bool:
        return all(
            [
                self.initial_state_equal,
                self.environment_equal,
                self.vehicle_equal,
                self.K_equal,
                self.solver_equal,
            ]
        )


@dataclass(frozen=True)
class ComparisonTrajectory:
    """Unified continuous comparison trajectory (E1, source of truth).

    Maps either frozen research trajectory onto the same API.  The
    research domain is ``[initial_time_s, terminal_time_s]``; the ground
    compatibility continuation NEVER enters it.
    """

    name: str
    initial_time_s: float
    terminal_time_s: float
    terminal_kind: str
    terminal_semantics: str
    initial_state: np.ndarray
    terminal_state: np.ndarray
    dense_segments: tuple[DenseSegmentView, ...]
    events: tuple[ComparisonEvent, ...]
    atmospheric_intervals: tuple[tuple[float, float], ...]
    environment: EnvironmentParams
    vehicle: VehicleParams
    K: float | None
    solver_config: SolverConfig

    _event_lookup: dict[float, tuple[np.ndarray, str]] = field(
        repr=False, compare=False
    )
    _monotonicity: RangeMonotonicityResult | None = field(
        repr=False, compare=False, default=None
    )

    # -- continuous state / mode evaluation -------------------------------

    def state_at_time(self, t: float) -> ComparisonState:
        """Continuous state at ``t`` from the REAL solver dense output.

        ``t`` must lie in ``[initial_time_s, terminal_time_s]``; outside
        raises ``ValueError`` (no extrapolation, no compatibility ground
        tail).  Exact stored event times return the exact event state;
        interior times are evaluated on the containing segment's dense
        interpolant.  The mode is right-continuous (post-transition at
        switching events; pre-terminal physical mode at the terminal).
        """
        self._check_time_in_domain(t)

        # 1) Exact event-time preference (tight tolerance, see
        #    EVENT_TIME_TOL_S policy).
        entry = self._event_lookup.get(t)
        if entry is None:
            for t_e, candidate in self._event_lookup.items():
                if abs(t - t_e) <= EVENT_TIME_TOL_S:
                    entry = candidate
                    break
        if entry is not None:
            state, source_mode = entry
            return self._wrap_state(t, state, source_mode)

        # 2) Interior: containing segment (right-continuous: [t_s, t_e)).
        seg = self._segment_at(t)
        state = np.asarray(seg.dense_solution(t), dtype=float)
        return self._wrap_state(t, state, seg.source_mode)

    def mode_at_time(self, t: float) -> str:
        """Normalized mode (``ATM`` / ``VAC``), right-continuous."""
        self._check_time_in_domain(t)
        if t >= self.terminal_time_s:
            return self.dense_segments[-1].normalized_mode
        return self._segment_at(t).normalized_mode

    def source_mode_at_time(self, t: float) -> str:
        """Original frozen mode label at ``t`` (right-continuous)."""
        self._check_time_in_domain(t)
        if t >= self.terminal_time_s:
            return self.dense_segments[-1].source_mode
        return self._segment_at(t).source_mode

    def range_at_time(self, t: float) -> float:
        """Ground range ``R = R_E * theta`` at ``t`` (frozen convention)."""
        return self.state_at_time(t).range_m

    def specific_energy_at_time(self, t: float) -> float:
        """Specific mechanical energy ``E = v^2/2 - mu/r`` at ``t``.

        Thin delegation to the frozen helper; ``mu`` comes from the
        frozen environment parameters (no duplicated constants).
        """
        return self.state_at_time(t).specific_mechanical_energy_jpkg

    # -- downrange monotonicity -------------------------------------------

    def is_range_monotone(self) -> RangeMonotonicityResult:
        """Validate downrange monotonicity from the dense dynamics.

        Evaluates ``dR/dt = R_E * v * cos(gamma) / r`` on a dense
        validation mesh per segment (validation only, never a formal
        checkpoint) and combines it with the analytical positivity of
        ``v`` / ``cos(gamma)`` implied by the frozen dynamics.
        """
        if self._monotonicity is not None:
            return self._monotonicity

        r_e = self.environment.earth_radius
        min_dr = np.inf
        min_cos = np.inf
        min_v = np.inf
        n_samples = 0
        for seg in self.dense_segments:
            t_mesh = np.linspace(seg.t_start, seg.t_end,
                                 MONOTONICITY_MESH_POINTS)
            states = np.asarray(seg.dense_solution(t_mesh), dtype=float)
            r = states[0]
            v = states[2]
            cos_g = np.cos(states[3])
            dr_dt = r_e * v * cos_g / r
            min_dr = min(min_dr, float(np.min(dr_dt)))
            min_cos = min(min_cos, float(np.min(cos_g)))
            min_v = min(min_v, float(np.min(v)))
            n_samples += t_mesh.size

        result = RangeMonotonicityResult(
            is_strictly_monotone=min_dr > 0.0,
            minimum_drange_dt=min_dr,
            minimum_cos_gamma=min_cos,
            minimum_velocity=min_v,
            diagnostic_sample_count=n_samples,
        )
        # Frozen dataclass: store via object.__setattr__.
        object.__setattr__(self, "_monotonicity", result)
        return result

    # -- common-range inversion -------------------------------------------

    def first_time_at_range(self, r_target: float) -> float:
        """First ``t`` with ``range_at_time(t) == r_target`` (E0 §17).

        Requires downrange monotonicity to PASS.  The target must lie in
        ``[R(initial_time_s), R(terminal_time_s)]``; the bracketing
        segment is located first, then ``brentq`` solves on that segment
        only (never a blind root over the whole trajectory).
        """
        mono = self.is_range_monotone()
        if not mono.is_strictly_monotone:
            raise RuntimeError(
                "Common-range inversion disabled: downrange is not "
                f"strictly monotone (min dR/dt = "
                f"{mono.minimum_drange_dt:.6e} m/s)."
            )

        r0 = self.range_at_time(self.initial_time_s)
        r_t = self.range_at_time(self.terminal_time_s)
        if r_target < r0 or r_target > r_t:
            raise ValueError(
                f"r_target={r_target:.6e} m outside the research range "
                f"[{r0:.6e}, {r_t:.6e}] m."
            )
        if r_target <= r0:
            return self.initial_time_s
        if r_target >= r_t:
            return self.terminal_time_s

        # Locate the unique bracketing segment (range is increasing).
        seg = None
        for candidate in self.dense_segments:
            if self.range_at_time(candidate.t_end) >= r_target:
                seg = candidate
                break
        if seg is None:
            raise RuntimeError("No bracketing segment found (internal).")

        return float(
            brentq(
                lambda t: self.range_at_time(t) - r_target,
                seg.t_start,
                seg.t_end,
                xtol=ROOT_XTOL_S,
                rtol=ROOT_RTOL,
            )
        )

    # -- cumulative atmospheric exposure ----------------------------------

    def atmospheric_exposure_at_time(self, t: float) -> float:
        """Cumulative atmospheric exposure ``tau_ATM(t)`` (E0 §11, §20).

        Exact piecewise interval arithmetic over
        ``atmospheric_intervals``: no quadrature, no integration error.
        """
        self._check_time_in_domain(t)
        return self._exposure_at(t)

    def total_atmospheric_exposure(self) -> float:
        """``tau_ATM(terminal_time_s)`` (never hard-coded)."""
        return self._exposure_at(self.terminal_time_s)

    def time_at_atmospheric_exposure(self, tau: float) -> AtmosphericExposureInverseResult:
        """Inverse of ``tau_ATM`` with explicit non-uniqueness handling.

        A target inside an ATM interval maps UNIQUE (slope 1, piecewise
        arithmetic -- no root solver); a target exactly equal to the
        exposure value of a VAC plateau returns PLATEAU with the full
        interval.  No earliest / latest / midpoint selection is made.
        """
        total = self.total_atmospheric_exposure()
        if tau < 0.0 or tau > total:
            raise ValueError(
                f"tau={tau:.6e} s outside [0, {total:.6e}] s "
                "(research atmospheric exposure)."
            )
        if abs(tau) <= EXPOSURE_TOL_S:
            return AtmosphericExposureInverseResult(
                status=AtmosphericExposureInverseStatus.UNIQUE,
                tau_s=tau,
                time_s=self.initial_time_s,
            )

        # Plateau candidates: a VAC gap between two ATM intervals (or
        # after the last interval) holds its exposure constant.
        for (a, b) in self._interval_gaps():
            plateau_tau = self._exposure_at(a)
            if abs(tau - plateau_tau) <= EXPOSURE_TOL_S:
                return AtmosphericExposureInverseResult(
                    status=AtmosphericExposureInverseStatus.PLATEAU,
                    tau_s=tau,
                    plateau_start_s=a,
                    plateau_end_s=b,
                )

        # UNIQUE: locate the ATM interval whose exposure range contains
        # the target; within it exposure grows with slope 1.
        c = 0.0
        for (a, b) in self.atmospheric_intervals:
            duration = b - a
            if tau <= c + duration:
                return AtmosphericExposureInverseResult(
                    status=AtmosphericExposureInverseStatus.UNIQUE,
                    tau_s=tau,
                    time_s=a + (tau - c),
                )
            c += duration

        raise RuntimeError("Exposure inverse fell through (internal).")

    # -- internal helpers ---------------------------------------------------

    def _check_time_in_domain(self, t: float) -> None:
        if t < self.initial_time_s or t > self.terminal_time_s:
            raise ValueError(
                f"t={t:.6e} s outside the research domain "
                f"[{self.initial_time_s:.6e}, {self.terminal_time_s:.6e}] s; "
                "no extrapolation and no compatibility ground tail."
            )

    def _segment_at(self, t: float) -> DenseSegmentView:
        for seg in self.dense_segments:
            if seg.t_start <= t < seg.t_end:
                return seg
        # t == terminal_time handled by the caller; fall back defensively.
        return self.dense_segments[-1]

    def _wrap_state(self, t: float, state, source_mode: str) -> ComparisonState:
        return ComparisonState(
            time_s=t,
            state_raw=np.asarray(state, dtype=float).copy(),
            trajectory_name=self.name,
            mode=_normalize_mode(source_mode),
            source_mode=source_mode,
            _environment=self.environment,
            _earth_radius=self.environment.earth_radius,
        )

    def _exposure_at(self, t: float) -> float:
        tau = 0.0
        for (a, b) in self.atmospheric_intervals:
            tau += max(0.0, min(b, t) - max(a, self.initial_time_s))
        return float(tau)

    def _interval_gaps(self):
        """Consecutive (gap_start, gap_end) pairs between ATM intervals."""
        gaps = []
        for (a, b), (c, d) in zip(self.atmospheric_intervals,
                                  self.atmospheric_intervals[1:]):
            if b < c:
                gaps.append((b, c))
        return gaps


# ---------------------------------------------------------------------------
# Normalized-mode mapping (E0 §9, §11)
# ---------------------------------------------------------------------------
_SOURCE_TO_NORMALIZED = {
    ENTRY_CAPTURE: ATM,
    QEG_GLIDE: ATM,
    SANGER_ATM: ATM,
    SANGER_VAC: VAC,
}


def _normalize_mode(source_mode: str) -> str:
    return _SOURCE_TO_NORMALIZED[source_mode]


# ---------------------------------------------------------------------------
# Frozen-convention helpers
# ---------------------------------------------------------------------------
def _solver_configs_equal(a: SolverConfig, b: SolverConfig) -> bool:
    if (a.method, a.rtol, a.max_step, a.t_span, a.dense_output,
            a.output_points) != (b.method, b.rtol, b.max_step, b.t_span,
                                 b.dense_output, b.output_points):
        return False
    return bool(np.array_equal(a.atol, b.atol))


# ---------------------------------------------------------------------------
# Builders (adapters over the frozen integrators + E0.1 collector)
# ---------------------------------------------------------------------------
def build_qian_comparison_trajectory(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control,
    solver_config: SolverConfig | None = None,
) -> ComparisonTrajectory:
    """Qian Phase-E comparison realization.

    Runs the frozen ``integrate_qian_glide`` with an E0.1
    ``DenseOutputCollector``.  ``solver_config`` defaults to
    ``PRODUCTION_SOLVER_CONFIG`` (E6 audit may override it with a
    high-precision reference config; the default path is bit-identical
    to the pre-E6 behavior).  The primary research domain is ``[t0,
    RTI]`` (ENTRY_CAPTURE + QEG_GLIDE); the GROUND_CONTINUATION dense
    stage collected by the hook is excluded from the comparison
    trajectory.
    """
    solver_config = solver_config or PRODUCTION_SOLVER_CONFIG
    collector = DenseOutputCollector()
    result: TrajectoryResult = integrate_qian_glide(
        env, vehicle, initial, control,
        solver=solver_config,
        dense_output_collector=collector,
    )

    research_stages = [
        seg for seg in collector.segments
        if seg.mode in (ENTRY_CAPTURE, QEG_GLIDE)
    ]
    if len(research_stages) != 2:
        raise RuntimeError(
            "Qian comparison realization: expected 2 research dense "
            f"stages (ENTRY_CAPTURE, QEG_GLIDE), got {len(research_stages)}."
        )

    t0 = 0.0
    t_capture = result.events["capture_event"]["time_s"]
    t_rti = result.events["research_terminal_interface"]["time_s"]
    state_capture = np.asarray(
        result.events["capture_event"]["state"], dtype=float
    ).copy()
    state_rti = np.asarray(
        result.events["research_terminal_interface"]["state"], dtype=float
    ).copy()

    initial_state = np.asarray(
        research_stages[0].solution(t0), dtype=float
    ).copy()

    dense_segments = (
        DenseSegmentView(
            index=0,
            name=ENTRY_CAPTURE,
            source_mode=ENTRY_CAPTURE,
            normalized_mode=ATM,
            t_start=t0,
            t_end=t_capture,
            dense_solution=research_stages[0].solution,
            state_start=initial_state.copy(),
            state_end=state_capture.copy(),
        ),
        DenseSegmentView(
            index=1,
            name=QEG_GLIDE,
            source_mode=QEG_GLIDE,
            normalized_mode=ATM,
            t_start=t_capture,
            t_end=t_rti,
            dense_solution=research_stages[1].solution,
            state_start=state_capture.copy(),
            state_end=state_rti.copy(),
        ),
    )

    events = (
        ComparisonEvent(
            kind="capture",
            time_s=t_capture,
            source_mode_before=ENTRY_CAPTURE,
            source_mode_after=QEG_GLIDE,
            state=state_capture.copy(),
        ),
        ComparisonEvent(
            kind=QIAN_TERMINAL_KIND,
            time_s=t_rti,
            source_mode_before=QEG_GLIDE,
            source_mode_after=None,
            state=state_rti.copy(),
        ),
    )

    # Both research stages are atmospheric -> one merged ATM interval.
    atmospheric_intervals = ((t0, t_rti),)

    return _assemble(
        name="qian",
        initial_time_s=t0,
        terminal_time_s=t_rti,
        terminal_kind=QIAN_TERMINAL_KIND,
        terminal_semantics=QIAN_TERMINAL_SEMANTICS,
        initial_state=initial_state,
        terminal_state=state_rti,
        dense_segments=dense_segments,
        events=events,
        atmospheric_intervals=atmospheric_intervals,
        env=env,
        vehicle=vehicle,
        control=control,
        solver_config=solver_config,
    )


def build_sanger_comparison_trajectory(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control,
    solver_config: SolverConfig | None = None,
) -> ComparisonTrajectory:
    """Sanger Phase-E comparison realization.

    Runs the frozen ``integrate_sanger_hybrid`` with an E0.1
    ``DenseOutputCollector``.  ``solver_config`` defaults to
    ``PRODUCTION_SOLVER_CONFIG`` (E6 audit may override it with a
    high-precision reference config; the default path is bit-identical
    to the pre-E6 behavior).  The research domain is the full hybrid
    trajectory from the synthetic E0 to SRTI; the ground compatibility
    continuation is not part of this integrator at all.
    """
    solver_config = solver_config or PRODUCTION_SOLVER_CONFIG
    collector = DenseOutputCollector()
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control,
        solver=solver_config,
        dense_output_collector=collector,
    )
    if not traj.success:
        raise RuntimeError(
            "Sanger comparison realization did not reach SRTI: "
            f"terminal_kind={traj.terminal_kind} ({traj.message})."
        )
    if len(collector) != len(traj.segments):
        raise RuntimeError(
            "Sanger comparison realization: dense segment count "
            f"{len(collector)} != trajectory segment count "
            f"{len(traj.segments)}."
        )

    dense_segments = tuple(
        DenseSegmentView(
            index=seg.index,
            name=seg.mode,
            source_mode=seg.mode,
            normalized_mode=_normalize_mode(seg.mode),
            t_start=seg.t_start,
            t_end=seg.t_end,
            dense_solution=dense.solution,
            state_start=seg.state_start.copy(),
            state_end=seg.state_end.copy(),
        )
        for dense, seg in zip(collector.segments, traj.segments)
    )

    events = tuple(
        ComparisonEvent(
            kind=e.kind,
            time_s=e.time,
            source_mode_before=e.mode_before,
            source_mode_after=e.mode_after,
            state=e.state.copy(),
        )
        for e in traj.events
    )

    # One ATM exposure interval per SANGER_ATM segment (adjacent ATM
    # segments would merge, but the frozen topology has no such pair).
    atmospheric_intervals = tuple(
        (seg.t_start, seg.t_end)
        for seg in dense_segments
        if seg.normalized_mode == ATM
    )

    return _assemble(
        name="sanger",
        initial_time_s=traj.events[0].time,
        terminal_time_s=traj.terminal_time,
        terminal_kind=SANGER_TERMINAL_KIND,
        terminal_semantics=SANGER_TERMINAL_SEMANTICS,
        initial_state=dense_segments[0].state_start.copy(),
        terminal_state=traj.terminal_state.copy(),
        dense_segments=dense_segments,
        events=events,
        atmospheric_intervals=atmospheric_intervals,
        env=env,
        vehicle=vehicle,
        control=control,
        solver_config=solver_config,
    )


def _assemble(
    name: str,
    initial_time_s: float,
    terminal_time_s: float,
    terminal_kind: str,
    terminal_semantics: str,
    initial_state: np.ndarray,
    terminal_state: np.ndarray,
    dense_segments: tuple[DenseSegmentView, ...],
    events: tuple[ComparisonEvent, ...],
    atmospheric_intervals: tuple[tuple[float, float], ...],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control,
    solver_config: SolverConfig | None = None,
) -> ComparisonTrajectory:
    """Assemble a ComparisonTrajectory with its exact event lookup.

    The lookup maps each event time to the state returned at that time:
    post-transition state semantics for switching events and the
    pre-terminal physical state at the terminal event.
    """
    event_lookup: dict[float, tuple[np.ndarray, str]] = {}
    for e in events:
        if e.source_mode_after is not None:
            event_lookup[e.time_s] = (e.state, e.source_mode_after)
        elif e.source_mode_before is not None:
            event_lookup[e.time_s] = (e.state, e.source_mode_before)

    return ComparisonTrajectory(
        name=name,
        initial_time_s=initial_time_s,
        terminal_time_s=terminal_time_s,
        terminal_kind=terminal_kind,
        terminal_semantics=terminal_semantics,
        initial_state=initial_state,
        terminal_state=terminal_state,
        dense_segments=dense_segments,
        events=events,
        atmospheric_intervals=atmospheric_intervals,
        environment=env,
        vehicle=vehicle,
        K=getattr(control, "value", None),
        solver_config=solver_config or PRODUCTION_SOLVER_CONFIG,
        _event_lookup=event_lookup,
    )


# ---------------------------------------------------------------------------
# Alignment verification (E1 §9)
# ---------------------------------------------------------------------------
def verify_comparison_alignment(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
) -> AlignmentResult:
    """Structural equality check of the two realized trajectories."""
    return AlignmentResult(
        initial_state_equal=bool(
            np.allclose(qian.initial_state, sanger.initial_state,
                        rtol=1e-9, atol=1e-9)
        ),
        environment_equal=qian.environment == sanger.environment,
        vehicle_equal=qian.vehicle == sanger.vehicle,
        K_equal=qian.K == sanger.K,
        solver_equal=_solver_configs_equal(qian.solver_config,
                                           sanger.solver_config),
    )
