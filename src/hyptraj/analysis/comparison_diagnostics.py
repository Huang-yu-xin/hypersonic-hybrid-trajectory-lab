"""Phase E native-endpoint, structural and aerodynamic diagnostics (E4).

Final Phase-E diagnostics round:

* Protocol A -- Native Endpoint Comparison (E0 §5): separately evaluates
  Qian@RTI and Sanger@SRTI as a TRAJECTORY-MODE PERSISTENCE comparison.
  RTI (QEG feasibility loss) and SRTI (skip-capability loss) have
  different feasibility semantics, so descriptive differences are never
  called gains / improvements and no native-endpoint ratio is used as a
  performance percentage (E0 §4, §5, §15, §16).
* Structural diagnostics: continuous (dense-solution refined) altitude /
  velocity extrema, ATM/VAC durations and fractions from the real
  normalized segments, plus model-specific structure retained as
  metadata (never pseudo-matched across models).
* Aerodynamic diagnostics: dynamic pressure ``q = 0.5 rho v^2`` and
  drag deceleration ``a_D = D / m``, computed ONLY through the frozen
  atmosphere / aerodynamics helpers (``atmospheric_density``,
  ``aerodynamic_forces``).  Under the frozen hybrid semantics Sanger
  VAC mode has ``L = D = 0``, so its aerodynamic diagnostic is
  uniformly ``rho_eff = 0, q = 0, D = 0, a_D = 0`` (documented, not a
  high-fidelity outer-atmosphere model).
* Three reporting windows: native research trajectory, common-time
  window ``[t0, t_common]`` (E2 Protocol B), and common-range windows
  ``[t0, t_Q/R_common]`` / ``[t0, t_S/R_common]`` (E2 Protocol C) --
  checkpoints are reused, never redefined.
* Peaks are refined continuously (dense scan + bounded
  ``minimize_scalar``) and sanity-audited; no thermal / total-g-load /
  threshold / composite-score inferences are made (E0 §13-§16, E4
  §24-§27).
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from hyptraj.analysis.comparison import (
    ComparisonState,
    ComparisonTrajectory,
)
from hyptraj.analysis.comparison_protocols import (
    CommonRangeComparison,
    CommonTimeComparison,
    _common_initial_energy,
)
from hyptraj.models.aerodynamics import aerodynamic_forces
from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.parameters import VehicleParams
from hyptraj.modes.sanger_hybrid import specific_mechanical_energy
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    VACUUM_APOGEE,
)

# Extrema-refinement policy: dense scan density and optimizer bracket.
EXTREMA_SCAN_POINTS = 256
AERO_SCAN_POINTS = 128
AERO_VERIFY_SCAN_POINTS = 512
REFINE_XATOL_S = 1e-9

# Reporting-scale agreement for the peak sanity audit (E4 §35).
PEAK_AGREEMENT_TOL = 1e-6  # relative


# ---------------------------------------------------------------------------
# Protocol A -- native endpoint comparison (E0 §5, E4 §4-§6)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NativeTerminal:
    """One research endpoint (exact terminal state)."""

    kind: str
    semantics: str
    time_s: float
    range_m: float
    altitude_m: float
    velocity_mps: float
    specific_energy_jpkg: float
    energy_loss_jpkg: float
    normalized_mode: str
    source_mode: str


@dataclass(frozen=True)
class NativeEndpointComparison:
    """Protocol A result -- mode-persistence comparison (not a ranking)."""

    qian_terminal: NativeTerminal
    sanger_terminal: NativeTerminal

    qian_duration_s: float
    sanger_duration_s: float
    qian_range_m: float
    sanger_range_m: float

    delta_duration_s: float
    delta_range_m: float
    delta_altitude_m: float
    delta_velocity_mps: float
    delta_specific_energy_jpkg: float

    semantics: str = "trajectory_mode_persistence"


def run_native_endpoint_comparison(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
) -> NativeEndpointComparison:
    """Protocol A (E0 §5): both native endpoints with exact states.

    The descriptive differences describe the states reached when each
    native research mode persists to its own terminal interface; they
    are never called range gain / performance improvement.
    """
    e0 = _common_initial_energy(qian, sanger)

    def _terminal(trajectory: ComparisonTrajectory) -> NativeTerminal:
        env = trajectory.environment
        state = trajectory.terminal_state
        energy = specific_mechanical_energy(state, env)
        return NativeTerminal(
            kind=trajectory.terminal_kind,
            semantics=trajectory.terminal_semantics,
            time_s=trajectory.terminal_time_s,
            range_m=env.earth_radius * state[1],
            altitude_m=state[0] - env.earth_radius,
            velocity_mps=state[2],
            specific_energy_jpkg=energy,
            energy_loss_jpkg=e0 - energy,
            normalized_mode=trajectory.mode_at_time(
                trajectory.terminal_time_s
            ),
            source_mode=trajectory.source_mode_at_time(
                trajectory.terminal_time_s
            ),
        )

    q_terminal = _terminal(qian)
    s_terminal = _terminal(sanger)

    return NativeEndpointComparison(
        qian_terminal=q_terminal,
        sanger_terminal=s_terminal,
        qian_duration_s=qian.terminal_time_s,
        sanger_duration_s=sanger.terminal_time_s,
        qian_range_m=q_terminal.range_m,
        sanger_range_m=s_terminal.range_m,
        delta_duration_s=s_terminal.time_s - q_terminal.time_s,
        delta_range_m=s_terminal.range_m - q_terminal.range_m,
        delta_altitude_m=s_terminal.altitude_m - q_terminal.altitude_m,
        delta_velocity_mps=s_terminal.velocity_mps - q_terminal.velocity_mps,
        delta_specific_energy_jpkg=(
            s_terminal.specific_energy_jpkg
            - q_terminal.specific_energy_jpkg
        ),
    )


# ---------------------------------------------------------------------------
# Structural diagnostics (E4 §7-§12)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AltitudeExtremum:
    value_m: float
    time_s: float
    source_mode: str


@dataclass(frozen=True)
class TrajectoryStructuralDiagnostics:
    """Structural description of one research trajectory (E4 §7)."""

    trajectory_name: str
    research_duration_s: float
    research_range_m: float

    min_altitude: AltitudeExtremum
    max_altitude: AltitudeExtremum

    min_velocity_mps: float
    min_velocity_time_s: float
    terminal_velocity_mps: float

    ATM_duration_s: float
    VAC_duration_s: float
    ATM_fraction: float
    VAC_fraction: float

    normalized_segment_count: int
    source_segment_count: int

    terminal_kind: str

    qian_specific: dict | None
    sanger_specific: dict | None


def _refine_extremum(
    trajectory: ComparisonTrajectory,
    seg,
    sign: int,
) -> tuple[float, float]:
    """Bounded continuous refinement of a per-segment altitude extremum.

    ``sign = +1`` minimizes altitude, ``sign = -1`` maximizes it.
    Returns ``(t_star, h_star)``.
    """
    t_grid = np.linspace(seg.t_start, seg.t_end, EXTREMA_SCAN_POINTS)
    states = np.asarray(seg.dense_solution(t_grid), dtype=float)
    altitudes = states[0] - trajectory.environment.earth_radius
    t0 = t_grid[int(np.argmin(sign * altitudes))]

    result = minimize_scalar(
        lambda t: sign * (seg.dense_solution(t)[0]
                          - trajectory.environment.earth_radius),
        bounds=(seg.t_start, seg.t_end),
        method="bounded",
        options={"xatol": REFINE_XATOL_S},
    )
    # The objective is ``sign * h``, so the extremum altitude is
    # ``sign * objective_value``.
    if result.success:
        return float(result.x), float(sign * result.fun)
    return float(t0), float(sign * min(sign * altitudes))


def build_structural_diagnostics(
    trajectory: ComparisonTrajectory,
) -> TrajectoryStructuralDiagnostics:
    """Structural diagnostics with continuously refined extrema."""
    env = trajectory.environment
    r_e = env.earth_radius

    # Continuous altitude extrema (never from a plotting grid).
    h_min, t_min, mode_min = np.inf, np.nan, None
    h_max, t_max, mode_max = -np.inf, np.nan, None
    for seg in trajectory.dense_segments:
        t_lo, h_lo = _refine_extremum(trajectory, seg, +1)
        t_hi, h_hi = _refine_extremum(trajectory, seg, -1)
        if h_lo < h_min:
            h_min, t_min, mode_min = h_lo, t_lo, seg.source_mode
        if h_hi > h_max:
            h_max, t_max, mode_max = h_hi, t_hi, seg.source_mode

    # Continuous minimum velocity.
    v_min, t_vmin = np.inf, np.nan
    for seg in trajectory.dense_segments:
        t_grid = np.linspace(seg.t_start, seg.t_end, EXTREMA_SCAN_POINTS)
        states = np.asarray(seg.dense_solution(t_grid), dtype=float)
        idx = int(np.argmin(states[2]))
        if states[2, idx] < v_min:
            v_min = float(states[2, idx])
            t_vmin = float(t_grid[idx])
        result = minimize_scalar(
            lambda t: seg.dense_solution(t)[2],
            bounds=(seg.t_start, seg.t_end),
            method="bounded",
            options={"xatol": REFINE_XATOL_S},
        )
        if result.success and result.fun < v_min:
            v_min = float(result.fun)
            t_vmin = float(result.x)

    atm_duration = sum(
        s.t_end - s.t_start for s in trajectory.dense_segments
        if s.normalized_mode == "ATM"
    )
    vac_duration = sum(
        s.t_end - s.t_start for s in trajectory.dense_segments
        if s.normalized_mode == "VAC"
    )
    research_duration = trajectory.terminal_time_s

    return TrajectoryStructuralDiagnostics(
        trajectory_name=trajectory.name,
        research_duration_s=research_duration,
        research_range_m=r_e * trajectory.terminal_state[1],
        min_altitude=AltitudeExtremum(h_min, t_min, mode_min),
        max_altitude=AltitudeExtremum(h_max, t_max, mode_max),
        min_velocity_mps=v_min,
        min_velocity_time_s=t_vmin,
        terminal_velocity_mps=float(trajectory.terminal_state[2]),
        ATM_duration_s=atm_duration,
        VAC_duration_s=vac_duration,
        ATM_fraction=atm_duration / research_duration,
        VAC_fraction=vac_duration / research_duration,
        normalized_segment_count=len(trajectory.dense_segments),
        source_segment_count=len({s.source_mode
                                  for s in trajectory.dense_segments}),
        terminal_kind=trajectory.terminal_kind,
        qian_specific=(
            qian_specific_structure(trajectory)
            if trajectory.name == "qian" else None
        ),
        sanger_specific=(
            sanger_specific_structure(trajectory)
            if trajectory.name == "sanger" else None
        ),
    )


def qian_specific_structure(trajectory: ComparisonTrajectory) -> dict:
    """Qian trajectory structure (metadata; no Sanger counterpart)."""
    env = trajectory.environment
    capture = next(e for e in trajectory.events if e.kind == "capture")
    rti = next(e for e in trajectory.events if e.kind == "RTI")
    return {
        "capture_time_s": capture.time_s,
        "capture_altitude_m": capture.state[0] - env.earth_radius,
        "capture_velocity_mps": capture.state[2],
        "qeg_duration_s": rti.time_s - capture.time_s,
        "rti_time_s": rti.time_s,
    }


def sanger_specific_structure(trajectory: ComparisonTrajectory) -> dict:
    """Sanger trajectory structure from the frozen event records.

    ``skip_count`` equals the number of completed atmosphere-entry
    events (each completed VAC arc ends at an entry, matching the frozen
    D4 completed-cycle count for this complete trajectory).
    """
    env = trajectory.environment
    entries = [e for e in trajectory.events
               if e.kind == ATMOSPHERE_ENTRY]
    apogees = [e for e in trajectory.events
               if e.kind == VACUUM_APOGEE]
    vac_segments = [s for s in trajectory.dense_segments
                    if s.normalized_mode == "VAC"]
    atm_segments = [s for s in trajectory.dense_segments
                    if s.normalized_mode == "ATM"]
    return {
        "skip_count": len(entries),
        "vac_arc_count": len(vac_segments),
        "vac_arc_durations_s": [s.t_end - s.t_start
                                for s in vac_segments],
        "vac_arc_ranges_m": [
            env.earth_radius * (s.state_end[1] - s.state_start[1])
            for s in vac_segments
        ],
        "vac_apogee_altitudes_m": [
            e.state[0] - env.earth_radius for e in apogees
        ],
        "atm_segment_count": len(atm_segments),
        "vac_segment_count": len(vac_segments),
    }


# ---------------------------------------------------------------------------
# Aerodynamic diagnostics (E4 §13-§23)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AerodynamicDiagnosticState:
    """Aerodynamic quantities at one continuous point (E4 §16).

    In VAC mode the effective density / q / D / a_D are all zero under
    the frozen hybrid semantics (``L = D = 0``); the raw exponential
    atmosphere extrapolation above 100 km is NOT re-enabled.
    """

    time_s: float
    range_m: float
    altitude_m: float
    velocity_mps: float

    normalized_mode: str
    source_mode: str

    density_kgpm3: float
    dynamic_pressure_pa: float
    drag_n: float
    drag_deceleration_mps2: float


def _aero_forces(
    trajectory: ComparisonTrajectory,
    state: ComparisonState,
):
    """Frozen atmosphere/aero evaluation for an ATM point (VAC -> zeros)."""
    if state.mode == "VAC":
        return 0.0, 0.0, 0.0, 0.0  # rho_eff, q, D, a_D
    rho = atmospheric_density(state.altitude_m, trajectory.environment)
    forces = aerodynamic_forces(
        rho,
        state.velocity_mps,
        trajectory.K if trajectory.K is not None else 0.0,
        trajectory.vehicle,
    )
    a_d = forces.drag / trajectory.vehicle.mass
    return rho, forces.dynamic_pressure, forces.drag, a_d


def aerodynamic_diagnostic_state(
    trajectory: ComparisonTrajectory,
    t: float,
) -> AerodynamicDiagnosticState:
    """Instantaneous aerodynamic diagnostic at ``t`` (continuous)."""
    state = trajectory.state_at_time(t)
    rho, q, drag, a_d = _aero_forces(trajectory, state)
    return AerodynamicDiagnosticState(
        time_s=state.time_s,
        range_m=state.range_m,
        altitude_m=state.altitude_m,
        velocity_mps=state.velocity_mps,
        normalized_mode=state.mode,
        source_mode=state.source_mode,
        density_kgpm3=rho,
        dynamic_pressure_pa=q,
        drag_n=drag,
        drag_deceleration_mps2=a_d,
    )


@dataclass(frozen=True)
class AerodynamicMaximum:
    """Continuously refined window maximum of an aerodynamic quantity."""

    quantity: str
    value: float
    time_s: float
    range_m: float
    altitude_m: float
    velocity_mps: float
    normalized_mode: str
    source_mode: str
    segment_index: int
    optimization_success: bool
    candidate_count: int


def _quantity_fn(trajectory: ComparisonTrajectory, quantity: str):
    if quantity == "dynamic_pressure":

        def fn(t: float) -> float:
            state = trajectory.state_at_time(t)
            rho, q, _drag, _a_d = _aero_forces(trajectory, state)
            return q

    elif quantity == "drag_deceleration":

        def fn(t: float) -> float:
            state = trajectory.state_at_time(t)
            rho, _q, _drag, a_d = _aero_forces(trajectory, state)
            return a_d

    else:
        raise ValueError(f"Unknown quantity: {quantity}")
    return fn


def _window_maximum(
    trajectory: ComparisonTrajectory,
    window_end_s: float,
    quantity: str,
    verify_scan_points: int = AERO_VERIFY_SCAN_POINTS,
) -> AerodynamicMaximum:
    """Continuously refined maximum over ``[t0, window_end_s]``.

    Only ATM segments contribute (VAC is identically zero).  A dense
    scan locates candidate neighborhoods; a bounded ``minimize_scalar``
    of the negated quantity refines the peak; segment endpoints and
    exact event states inside the window are also considered.
    """
    fn = _quantity_fn(trajectory, quantity)
    best: AerodynamicMaximum | None = None
    candidates = 0

    for seg in trajectory.dense_segments:
        if seg.normalized_mode != "ATM":
            continue
        a = max(seg.t_start, trajectory.initial_time_s)
        b = min(seg.t_end, window_end_s)
        if b - a <= 0.0:
            continue
        candidates += 1

        # Dense scan + bounded refinement.
        scan = np.linspace(a, b, AERO_SCAN_POINTS)
        states = np.asarray(seg.dense_solution(scan), dtype=float)
        values = np.asarray([fn(float(t)) for t in scan])
        t_peak = scan[int(np.argmax(values))]
        result = minimize_scalar(
            lambda t: -fn(float(t)),
            bounds=(a, b),
            method="bounded",
            options={"xatol": REFINE_XATOL_S},
        )
        candidates += 1
        if result.success:
            t_cand, v_cand = float(result.x), float(-result.fun)
        else:
            t_cand, v_cand = float(t_peak), float(np.max(values))

        # Exact event states inside the window may beat the optimizer
        # (e.g. an event sitting exactly on the peak).
        for event in trajectory.events:
            if a <= event.time_s <= b:
                t_cand2, v_cand2 = event.time_s, fn(event.time_s)
                if v_cand2 > v_cand:
                    t_cand, v_cand = t_cand2, v_cand2
                    candidates += 1

        state = trajectory.state_at_time(t_cand)
        candidate = AerodynamicMaximum(
            quantity=quantity,
            value=float(v_cand),
            time_s=float(t_cand),
            range_m=state.range_m,
            altitude_m=state.altitude_m,
            velocity_mps=state.velocity_mps,
            normalized_mode=state.mode,
            source_mode=state.source_mode,
            segment_index=seg.index,
            optimization_success=result.success,
            candidate_count=candidates,
        )
        if best is None or candidate.value > best.value:
            best = candidate

    if best is None:
        raise RuntimeError(
            f"No ATM segment inside window [0, {window_end_s}] for "
            f"{trajectory.name} ({quantity})."
        )

    # Peak sanity audit (E4 §35): an independent denser scan must agree
    # with the refined peak within reporting tolerance.  ``fn`` already
    # maps VAC to zero, so the audit grid covers the whole window.
    t_dense = np.linspace(trajectory.initial_time_s, window_end_s,
                          verify_scan_points)
    values_dense = np.asarray([fn(float(t)) for t in t_dense])
    grid_max = float(np.max(values_dense))
    if best.value < grid_max - PEAK_AGREEMENT_TOL * max(1.0, grid_max):
        raise RuntimeError(
            f"Peak audit failed for {trajectory.name} {quantity}: "
            f"refined {best.value:.6e} < dense-scan {grid_max:.6e}."
        )
    return best


def native_aerodynamic_maxima(
    trajectory: ComparisonTrajectory,
) -> dict[str, AerodynamicMaximum]:
    """Native-window maxima over the whole research trajectory."""
    return {
        "max_q": _window_maximum(trajectory, trajectory.terminal_time_s,
                                 "dynamic_pressure"),
        "max_aD": _window_maximum(trajectory, trajectory.terminal_time_s,
                                  "drag_deceleration"),
    }


def windowed_aerodynamic_maxima(
    trajectory: ComparisonTrajectory,
    window_end_s: float,
) -> dict[str, AerodynamicMaximum]:
    """Window maxima over ``[t0, window_end_s]`` (E4 §19-§22)."""
    return {
        "max_q": _window_maximum(trajectory, window_end_s,
                                 "dynamic_pressure"),
        "max_aD": _window_maximum(trajectory, window_end_s,
                                  "drag_deceleration"),
    }
