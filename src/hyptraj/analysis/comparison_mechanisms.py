"""Phase E atmospheric-exposure and energy-mechanism analysis (E3).

Completes the frozen E0 Protocol D (Common Atmospheric Exposure, E0
§11) and adds segment-level mechanical-energy accounting plus VAC-coast
structure diagnostics that explain the E2 common-condition results.

Scope discipline (E0 §10, §12-§14, §16, E3 spec):

* ``tau_ATM`` is atmospheric-mode exposure TIME only -- it is never
  called thermal/heat exposure, never a heat load, never a TPS claim;
* ``DeltaR_atm_exposure`` is reported as a same-exposure downrange
  difference, never as a causal "VAC contribution" quantity;
* VAC range accumulation is structural accounting, never a causal
  decomposition of the total Sanger advantage;
* raw VAC energy drift keeps its true sign (no clipping);
* the formal Protocol D checkpoint requires UNIQUE exposure inverses on
  both sides; a PLATEAU yields an explicit AMBIGUOUS result with the
  plateau interval, never an arbitrary time;
* plotting curve samples are visualization-only and never drive formal
  checkpoints.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np

from hyptraj.analysis.comparison import (
    AtmosphericExposureInverseResult,
    AtmosphericExposureInverseStatus,
    ComparisonState,
    ComparisonTrajectory,
)
from hyptraj.analysis.comparison_protocols import (
    CommonRangeComparison,
    CommonTimeComparison,
    _common_initial_energy,
    _energy_loss,
)
from hyptraj.modes.sanger_hybrid import specific_mechanical_energy

# Tau-reproduction consistency tolerance (E0 §6): the exposure inverse
# must reproduce the target exposure at the returned time.
TAU_CONSISTENCY_TOL_S = 1e-6

# Telescoping tolerance for segment energy accounting: the segment
# budgets share exact boundary states, so the residual is float-level.
TELESCOPING_TOL_JPKG = 1e-3

# Default sampling density of the visualization-only energy curves.
CURVE_POINTS_PER_SEGMENT = 50


class ProtocolDStatus(Enum):
    UNIQUE = "UNIQUE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class CommonAtmosphericExposureComparison:
    """E0 Protocol D result: both states at equal cumulative exposure.

    ``tau_common = min(tau_ATM,Q(T_Q), tau_ATM,S(T_S))``.  A formal
    checkpoint requires both exposure inverses to be UNIQUE; otherwise
    ``status == AMBIGUOUS`` and the plateau interval(s) are attached
    (no earliest / latest / midpoint selection is ever made).
    """

    status: ProtocolDStatus
    common_exposure_s: float

    qian_inverse_status: AtmosphericExposureInverseStatus
    sanger_inverse_status: AtmosphericExposureInverseStatus
    qian_plateau_interval_s: tuple[float, float] | None
    sanger_plateau_interval_s: tuple[float, float] | None

    # None when AMBIGUOUS.
    qian_time_s: float | None
    sanger_time_s: float | None
    qian_state: ComparisonState | None
    sanger_state: ComparisonState | None

    elapsed_time_extension_s: float | None
    delta_range_m: float | None
    delta_altitude_m: float | None
    delta_velocity_mps: float | None
    delta_specific_energy_jpkg: float | None

    qian_energy_loss_jpkg: float | None
    sanger_energy_loss_jpkg: float | None

    qian_mode: str | None
    sanger_mode: str | None
    qian_source_mode: str | None
    sanger_source_mode: str | None

    initial_energy_jpkg: float | None


@dataclass(frozen=True)
class CheckpointExposureDiagnostic:
    """Exposure context of an E2 checkpoint (mechanism diagnostics only).

    ``delta_tau_s = tau_Q - tau_S`` (positive: Sanger accumulated less
    atmospheric-mode exposure at the checkpoint); the VAC durations
    explain ``elapsed - exposure`` on each side.
    """

    checkpoint: str
    qian_time_s: float
    sanger_time_s: float
    qian_exposure_s: float
    sanger_exposure_s: float
    delta_tau_s: float
    qian_energy_loss_jpkg: float
    sanger_energy_loss_jpkg: float
    qian_vac_duration_s: float
    sanger_vac_duration_s: float


@dataclass(frozen=True)
class SegmentEnergyBudget:
    """One segment's exact-endpoint mechanical-energy accounting."""

    trajectory_name: str
    segment_index: int
    source_mode: str
    normalized_mode: str

    t_start_s: float
    t_end_s: float
    duration_s: float

    range_start_m: float
    range_end_m: float
    delta_range_m: float

    energy_start_jpkg: float
    energy_end_jpkg: float
    raw_energy_loss_jpkg: float
    relative_energy_change: float


@dataclass(frozen=True)
class ModeAggregate:
    """Aggregate of all segments of one normalized mode."""

    mode: str
    duration_s: float
    range_increment_m: float
    raw_energy_loss_jpkg: float


@dataclass(frozen=True)
class TrajectoryEnergyBudget:
    """Full mechanical-energy budget of one comparison trajectory."""

    trajectory_name: str
    initial_energy_jpkg: float
    terminal_energy_jpkg: float
    total_energy_loss_jpkg: float

    atm: ModeAggregate
    vac: ModeAggregate

    segment_budgets: tuple[SegmentEnergyBudget, ...]
    telescoping_residual_jpkg: float


# ---------------------------------------------------------------------------
# VAC duration accounting (E3 §17): direct interval arithmetic over the
# normalized VAC intervals (never merely elapsed - exposure).
# ---------------------------------------------------------------------------
def _vac_intervals(trajectory: ComparisonTrajectory) -> tuple[
    tuple[float, float], ...]:
    return tuple(
        (seg.t_start, seg.t_end)
        for seg in trajectory.dense_segments
        if seg.normalized_mode == "VAC"
    )


def vac_duration_before_time(
    trajectory: ComparisonTrajectory, t: float
) -> float:
    """Cumulative VAC duration accumulated before ``t`` (exact interval
    arithmetic over the normalized VAC intervals)."""
    total = 0.0
    for (a, b) in _vac_intervals(trajectory):
        total += max(0.0, min(b, t) - max(a, trajectory.initial_time_s))
    return float(total)


def total_vac_duration(trajectory: ComparisonTrajectory) -> float:
    return vac_duration_before_time(trajectory, trajectory.terminal_time_s)


def total_vac_range(trajectory: ComparisonTrajectory) -> float:
    """Downrange accumulated while aerodynamic force is disabled (frozen
    VAC semantics).  Structural accounting only -- never a causal
    contribution to the total Sanger advantage (E3 §18)."""
    return float(sum(
        seg.state_end[1] - seg.state_start[1]
        for seg in trajectory.dense_segments
        if seg.normalized_mode == "VAC"
    ) * trajectory.environment.earth_radius)


# ---------------------------------------------------------------------------
# Protocol D -- common atmospheric exposure (E0 §11, E3 §4-§7)
# ---------------------------------------------------------------------------
def run_common_atmospheric_exposure_comparison(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
) -> CommonAtmosphericExposureComparison:
    """Protocol D: compare both trajectories at equal cumulative
    atmospheric-mode exposure.

    ``tau_common = min(tau_ATM,Q(T_Q), tau_ATM,S(T_S))`` from the real
    trajectories.  Both exposure inverses must be UNIQUE for a formal
    checkpoint; otherwise the result is AMBIGUOUS with the plateau
    interval(s) attached.
    """
    tau_common = min(
        qian.total_atmospheric_exposure(),
        sanger.total_atmospheric_exposure(),
    )

    q_inv = qian.time_at_atmospheric_exposure(tau_common)
    s_inv = sanger.time_at_atmospheric_exposure(tau_common)

    q_plateau = (
        (q_inv.plateau_start_s, q_inv.plateau_end_s)
        if q_inv.status == AtmosphericExposureInverseStatus.PLATEAU
        else None
    )
    s_plateau = (
        (s_inv.plateau_start_s, s_inv.plateau_end_s)
        if s_inv.status == AtmosphericExposureInverseStatus.PLATEAU
        else None
    )

    if (q_inv.status != AtmosphericExposureInverseStatus.UNIQUE
            or s_inv.status != AtmosphericExposureInverseStatus.UNIQUE):
        return CommonAtmosphericExposureComparison(
            status=ProtocolDStatus.AMBIGUOUS,
            common_exposure_s=float(tau_common),
            qian_inverse_status=q_inv.status,
            sanger_inverse_status=s_inv.status,
            qian_plateau_interval_s=q_plateau,
            sanger_plateau_interval_s=s_plateau,
            qian_time_s=None,
            sanger_time_s=None,
            qian_state=None,
            sanger_state=None,
            elapsed_time_extension_s=None,
            delta_range_m=None,
            delta_altitude_m=None,
            delta_velocity_mps=None,
            delta_specific_energy_jpkg=None,
            qian_energy_loss_jpkg=None,
            sanger_energy_loss_jpkg=None,
            qian_mode=None,
            sanger_mode=None,
            qian_source_mode=None,
            sanger_source_mode=None,
            initial_energy_jpkg=None,
        )

    t_q = q_inv.time_s
    t_s = s_inv.time_s
    qian_state = qian.state_at_time(t_q)
    sanger_state = sanger.state_at_time(t_s)

    # Consistency: the inverses must reproduce the target exposure
    # (never trusted blindly, E3 §6).
    tau_q = qian.atmospheric_exposure_at_time(t_q)
    tau_s = sanger.atmospheric_exposure_at_time(t_s)
    if (abs(tau_q - tau_common) > TAU_CONSISTENCY_TOL_S
            or abs(tau_s - tau_common) > TAU_CONSISTENCY_TOL_S):
        raise RuntimeError(
            "Protocol D exposure consistency violated: "
            f"tau_Q(t_Q)={tau_q:.9e} s, tau_S(t_S)={tau_s:.9e} s vs "
            f"tau_common={tau_common:.9e} s."
        )

    e0 = _common_initial_energy(qian, sanger)

    return CommonAtmosphericExposureComparison(
        status=ProtocolDStatus.UNIQUE,
        common_exposure_s=float(tau_common),
        qian_inverse_status=q_inv.status,
        sanger_inverse_status=s_inv.status,
        qian_plateau_interval_s=None,
        sanger_plateau_interval_s=None,
        qian_time_s=float(t_q),
        sanger_time_s=float(t_s),
        qian_state=qian_state,
        sanger_state=sanger_state,
        # E0 §11 / E3 §5 sign conventions.
        elapsed_time_extension_s=float(t_s - t_q),
        delta_range_m=float(sanger_state.range_m - qian_state.range_m),
        delta_altitude_m=float(sanger_state.altitude_m - qian_state.altitude_m),
        delta_velocity_mps=float(
            sanger_state.velocity_mps - qian_state.velocity_mps
        ),
        delta_specific_energy_jpkg=float(
            sanger_state.specific_mechanical_energy_jpkg
            - qian_state.specific_mechanical_energy_jpkg
        ),
        qian_energy_loss_jpkg=_energy_loss(e0, qian_state),
        sanger_energy_loss_jpkg=_energy_loss(e0, sanger_state),
        qian_mode=qian_state.mode,
        sanger_mode=sanger_state.mode,
        qian_source_mode=qian_state.source_mode,
        sanger_source_mode=sanger_state.source_mode,
        initial_energy_jpkg=e0,
    )


# ---------------------------------------------------------------------------
# E2 checkpoint exposure diagnostics (E3 §8-§9): mechanism context for
# the common-time and common-range checkpoints.
# ---------------------------------------------------------------------------
def exposure_diagnostic_at_common_time(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
    common_time: CommonTimeComparison,
) -> CheckpointExposureDiagnostic:
    """Exposure context of the E2 common-time checkpoint (E3 §8)."""
    t_common = common_time.common_time_s
    tau_q = qian.atmospheric_exposure_at_time(t_common)
    tau_s = sanger.atmospheric_exposure_at_time(t_common)
    e0 = _common_initial_energy(qian, sanger)
    return CheckpointExposureDiagnostic(
        checkpoint="common_time",
        qian_time_s=t_common,
        sanger_time_s=t_common,
        qian_exposure_s=tau_q,
        sanger_exposure_s=tau_s,
        # E3 §8: positive -> Sanger accumulated less exposure.
        delta_tau_s=float(tau_q - tau_s),
        qian_energy_loss_jpkg=_energy_loss(e0, common_time.qian_state),
        sanger_energy_loss_jpkg=_energy_loss(e0, common_time.sanger_state),
        qian_vac_duration_s=vac_duration_before_time(qian, t_common),
        sanger_vac_duration_s=vac_duration_before_time(sanger, t_common),
    )


def exposure_diagnostic_at_common_range(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
    common_range: CommonRangeComparison,
) -> CheckpointExposureDiagnostic:
    """Exposure context of the E2 common-range checkpoint (E3 §9)."""
    t_q = common_range.qian_arrival_time_s
    t_s = common_range.sanger_arrival_time_s
    tau_q = qian.atmospheric_exposure_at_time(t_q)
    tau_s = sanger.atmospheric_exposure_at_time(t_s)
    e0 = _common_initial_energy(qian, sanger)
    return CheckpointExposureDiagnostic(
        checkpoint="common_range",
        qian_time_s=t_q,
        sanger_time_s=t_s,
        qian_exposure_s=tau_q,
        sanger_exposure_s=tau_s,
        # E3 §9: positive -> Sanger reached the same downrange after
        # less atmospheric-mode exposure.
        delta_tau_s=float(tau_q - tau_s),
        qian_energy_loss_jpkg=_energy_loss(e0, common_range.qian_state),
        sanger_energy_loss_jpkg=_energy_loss(e0, common_range.sanger_state),
        qian_vac_duration_s=vac_duration_before_time(qian, t_q),
        sanger_vac_duration_s=vac_duration_before_time(sanger, t_s),
    )


# ---------------------------------------------------------------------------
# Segment-level energy accounting (E3 §11-§16)
# ---------------------------------------------------------------------------
def build_energy_budget(trajectory: ComparisonTrajectory) -> TrajectoryEnergyBudget:
    """Exact-endpoint segment energy budget of one comparison trajectory.

    ``raw_energy_loss = E_start - E_end`` keeps its true sign (no
    clipping); VAC segments are expected to conserve mechanical energy
    only to numerical precision.
    """
    env = trajectory.environment
    segments: list[SegmentEnergyBudget] = []
    for seg in trajectory.dense_segments:
        e_start = specific_mechanical_energy(seg.state_start, env)
        e_end = specific_mechanical_energy(seg.state_end, env)
        raw_loss = e_start - e_end
        segments.append(
            SegmentEnergyBudget(
                trajectory_name=trajectory.name,
                segment_index=seg.index,
                source_mode=seg.source_mode,
                normalized_mode=seg.normalized_mode,
                t_start_s=seg.t_start,
                t_end_s=seg.t_end,
                duration_s=seg.t_end - seg.t_start,
                range_start_m=env.earth_radius * seg.state_start[1],
                range_end_m=env.earth_radius * seg.state_end[1],
                delta_range_m=env.earth_radius
                * (seg.state_end[1] - seg.state_start[1]),
                energy_start_jpkg=e_start,
                energy_end_jpkg=e_end,
                raw_energy_loss_jpkg=raw_loss,
                relative_energy_change=raw_loss / abs(e_start),
            )
        )

    def _aggregate(mode: str) -> ModeAggregate:
        subset = [s for s in segments if s.normalized_mode == mode]
        return ModeAggregate(
            mode=mode,
            duration_s=sum(s.duration_s for s in subset),
            range_increment_m=sum(s.delta_range_m for s in subset),
            raw_energy_loss_jpkg=sum(s.raw_energy_loss_jpkg for s in subset),
        )

    initial_energy = specific_mechanical_energy(
        trajectory.initial_state, env
    )
    terminal_energy = specific_mechanical_energy(
        trajectory.terminal_state, env
    )
    total_loss = initial_energy - terminal_energy
    telescoping = sum(s.raw_energy_loss_jpkg for s in segments) - total_loss

    return TrajectoryEnergyBudget(
        trajectory_name=trajectory.name,
        initial_energy_jpkg=initial_energy,
        terminal_energy_jpkg=terminal_energy,
        total_energy_loss_jpkg=total_loss,
        atm=_aggregate("ATM"),
        vac=_aggregate("VAC"),
        segment_budgets=tuple(segments),
        telescoping_residual_jpkg=telescoping,
    )


# ---------------------------------------------------------------------------
# Visualization-only curve data (E3 §23-§24): R vs energy-loss samples.
# These samples NEVER drive Protocol B/C/D checkpoints; they exist only
# for the future E5 figures.
# ---------------------------------------------------------------------------
def energy_curve_samples(
    trajectory: ComparisonTrajectory,
    points_per_segment: int = CURVE_POINTS_PER_SEGMENT,
) -> dict[str, np.ndarray]:
    """Sampled curve data per dense segment for visualization only.

    Segment boundaries are de-duplicated (x_minus = x_plus, one state
    per switch time), exact stored boundary states are preferred, and
    the mode label follows the E1 right-continuous convention.
    """
    e0 = trajectory.specific_energy_at_time(trajectory.initial_time_s)
    env = trajectory.environment

    times: list[float] = []
    ranges: list[float] = []
    altitudes: list[float] = []
    velocities: list[float] = []
    energies: list[float] = []
    energy_losses: list[float] = []
    modes: list[str] = []
    source_modes: list[str] = []
    segment_indices: list[int] = []

    n = len(trajectory.dense_segments)
    for i, seg in enumerate(trajectory.dense_segments):
        t_grid = np.linspace(seg.t_start, seg.t_end, points_per_segment)
        keep_last = (i == n - 1)  # terminal row keeps the exact state
        for j, t in enumerate(t_grid):
            if j == points_per_segment - 1 and not keep_last:
                continue  # switch point de-duplicated (emitted by the
                # next segment with its right-continuous mode label)
            if j == 0:
                state = seg.state_start  # exact stored state
            elif j == points_per_segment - 1:
                state = seg.state_end  # exact stored state
            else:
                state = np.asarray(seg.dense_solution(t), dtype=float)
            e = specific_mechanical_energy(state, env)
            times.append(float(t))
            ranges.append(float(env.earth_radius * state[1]))
            altitudes.append(float(state[0] - env.earth_radius))
            velocities.append(float(state[2]))
            energies.append(float(e))
            energy_losses.append(float(e0 - e))
            modes.append(seg.normalized_mode)
            source_modes.append(seg.source_mode)
            segment_indices.append(seg.index)

    return {
        "time_s": np.asarray(times),
        "range_m": np.asarray(ranges),
        "altitude_m": np.asarray(altitudes),
        "velocity_mps": np.asarray(velocities),
        "specific_energy_jpkg": np.asarray(energies),
        "energy_loss_jpkg": np.asarray(energy_losses),
        "normalized_mode": np.asarray(modes, dtype=object),
        "source_mode": np.asarray(source_modes, dtype=object),
        "segment_index": np.asarray(segment_indices, dtype=int),
    }
