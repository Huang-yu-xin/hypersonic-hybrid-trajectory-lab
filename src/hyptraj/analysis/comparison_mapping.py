"""Phase-F common-condition comparison mapping over gamma0-K (F6).

F6 — Phase-E Common-Condition Comparison Surfaces
(docs/phase_f/f6_comparison_surfaces.md).

Reuses the frozen Phase-E comparison machinery unchanged
(``run_common_time_comparison`` / ``run_common_range_comparison`` /
``run_common_atmospheric_exposure_comparison``) on paired
``ComparisonTrajectory`` objects built for the 33x33 canonical centers.

Key architectural point (F6 §3–§7): the Phase-E Sanger builder calls the
frozen ``integrate_sanger_hybrid``, which cannot express the F2.1
recovered-exit trajectories over the whole parameter domain.  F6 adds a
Phase-F Sanger research comparison adapter that builds a
``ComparisonTrajectory`` from ``integrate_sanger_research_trajectory``
(the recovered exit is a normal ATM->VAC physical switch; the candidate
overshoot state never enters the comparison history).  The Phase-E
protocol implementation is NEVER modified.

Frozen semantics:
* pointwise VALUE eligibility is separate from display/interpolation
  continuity: an F3 exclusion box never erases a pointwise comparison
  value, it only blocks smooth interpolation across it (F6 §9, §25–§26);
* recovered physical centers are valid pointwise values and are all
  strict-reference audited (F6 §11);
* GRAZING_OR_UNRESOLVED / censored / failure -> NOT_AVAILABLE (F6 §10);
* limiters are DYNAMIC (QIAN / SANGER / NUMERICAL_TIE), never assumed
  constant over the domain (F6 §13, §19);
* Protocol-D AMBIGUOUS is a legitimate comparison-semantic structure:
  all formal state-difference fields stay None (F6 §17–§18);
* no native-endpoint winner surface, no comparison derivatives, no
  optimization, no STM/saltation/FTLE (F6 §63–§65).
"""

from dataclasses import dataclass

import numpy as np

from hyptraj.analysis.comparison import (
    ATM,
    VAC,
    QIAN_TERMINAL_KIND,
    QIAN_TERMINAL_SEMANTICS,
    SANGER_TERMINAL_KIND,
    SANGER_TERMINAL_SEMANTICS,
    ComparisonEvent,
    ComparisonTrajectory,
    DenseSegmentView,
    _assemble,
    _normalize_mode,
    build_qian_comparison_trajectory,
    verify_comparison_alignment,
)
from hyptraj.analysis.comparison_mechanisms import (
    ProtocolDStatus,
    run_common_atmospheric_exposure_comparison,
)
from hyptraj.analysis.comparison_protocols import (
    run_common_range_comparison,
    run_common_time_comparison,
)
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.dense_output import (
    DenseOutputCollector,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_research_trajectory import (
    integrate_sanger_research_trajectory,
)
from hyptraj.simulation.trajectory import SolverConfig

# Limiter vocabulary.
LIMITER_QIAN = "QIAN"
LIMITER_SANGER = "SANGER"
LIMITER_NUMERICAL_TIE = "NUMERICAL_TIE"

# Comparison value statuses.
VALUE_VALID = "VALID"
VALUE_NOT_AVAILABLE = "NOT_AVAILABLE"
VALUE_NOT_AVAILABLE_NONMONOTONE = "NOT_AVAILABLE_NONMONOTONE"

# Tie tolerance for limiter classification (dimension-appropriate).
TIME_TIE_TOL_S = 1e-6
RANGE_TIE_TOL_M = 1.0


def classify_limiter(q_value: float, s_value: float, tie_tol: float) -> str:
    """Dynamic limiter: the side with the smaller terminal quantity."""
    if abs(q_value - s_value) <= tie_tol:
        return LIMITER_NUMERICAL_TIE
    return LIMITER_QIAN if q_value < s_value else LIMITER_SANGER


def comparison_signature(
    qian_regime: str,
    sanger_regime: str,
    time_limiter: str,
    range_limiter: str,
    exposure_limiter: str,
    protocol_d_status: str,
) -> tuple[str, ...]:
    """Frozen F0 §34 comparison signature (core 6-tuple)."""
    return (
        qian_regime,
        sanger_regime,
        time_limiter,
        range_limiter,
        exposure_limiter,
        protocol_d_status,
    )


# ---------------------------------------------------------------------------
# Phase-F Sanger research comparison adapter (F6 §6–§7)
# ---------------------------------------------------------------------------
def build_sanger_research_comparison_trajectory(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control,
    solver_config: SolverConfig | None = None,
    dense_output_collector: DenseOutputCollector | None = None,
) -> tuple[ComparisonTrajectory, object]:
    """Build a Phase-E ``ComparisonTrajectory`` from the F2.1 research
    integrator.

    The recovered atmosphere-exit events are normal ATM->VAC switches
    (exact recovered root, x_plus = x_minus); the candidate-overshoot
    state and the erroneous post-candidate ATM tail never enter the
    comparison history (F6 §7).  Returns ``(trajectory, research_result)``
    so the caller can read the event-resolution metadata.

    The Phase-E protocol implementation is untouched.
    """
    solver = solver_config or PRODUCTION_SOLVER_CONFIG
    collector = (dense_output_collector if dense_output_collector is not None else DenseOutputCollector())
    research = integrate_sanger_research_trajectory(
        env, vehicle, initial, control,
        solver=solver,
        dense_output_collector=collector,
    )
    traj = research.trajectory  # frozen SangerHybridTrajectory container

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
    atmospheric_intervals = tuple(
        (seg.t_start, seg.t_end)
        for seg in dense_segments
        if seg.normalized_mode == ATM
    )
    comparison = _assemble(
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
        solver_config=solver,
    )
    return comparison, research


# ---------------------------------------------------------------------------
# One-center evaluation (F6 §12–§21, §29)
# ---------------------------------------------------------------------------
def evaluate_comparison_point(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control,
    git_commit: str,
    solver_config: SolverConfig | None = None,
) -> dict:
    """Full paired B/C/D evaluation at one canonical center."""
    solver = solver_config or PRODUCTION_SOLVER_CONFIG

    qian = build_qian_comparison_trajectory(
        env, vehicle, initial, control, solver_config=solver)
    sanger, research = build_sanger_research_comparison_trajectory(
        env, vehicle, initial, control, solver_config=solver)

    alignment = verify_comparison_alignment(qian, sanger)
    if not alignment.all_equal:
        raise RuntimeError(
            f"Alignment failed at gamma0={initial.flight_path_angle_deg}, "
            f"K={getattr(control, 'value', None)}.")

    # ---- Value eligibility (F6 §9–§11) -------------------------------------
    qian_ok = qian.terminal_kind == QIAN_TERMINAL_KIND
    sanger_ok = sanger.terminal_kind == SANGER_TERMINAL_KIND
    if not (qian_ok and sanger_ok):
        return {
            "comparison_value_status": VALUE_NOT_AVAILABLE,
            "qian_terminal_kind": qian.terminal_kind,
            "sanger_terminal_kind": sanger.terminal_kind,
        }

    # ---- Protocol B --------------------------------------------------------
    b = run_common_time_comparison(qian, sanger)
    time_limiter = classify_limiter(
        qian.terminal_time_s, sanger.terminal_time_s, TIME_TIE_TOL_S)

    # ---- Protocol C --------------------------------------------------------
    qian_mono = qian.is_range_monotone().is_strictly_monotone
    sanger_mono = sanger.is_range_monotone().is_strictly_monotone
    if not (qian_mono and sanger_mono):
        c_status = VALUE_NOT_AVAILABLE_NONMONOTONE
        c = None
        range_limiter = None
    else:
        try:
            c = run_common_range_comparison(qian, sanger)
            c_status = VALUE_VALID
        except ValueError:
            # Phase-E frozen float-edge guard: the range-inverse root can
            # sit an epsilon beyond the research domain at limiter
            # switching points.  The Phase-E source is never modified;
            # the point is reported NOT_AVAILABLE with a reason.
            c = None
            c_status = "NOT_AVAILABLE_FLOAT_EDGE"
        range_limiter = classify_limiter(
            qian.range_at_time(qian.terminal_time_s),
            sanger.range_at_time(sanger.terminal_time_s),
            RANGE_TIE_TOL_M)

    # ---- Protocol D --------------------------------------------------------
    try:
        d = run_common_atmospheric_exposure_comparison(qian, sanger)
        d_status = d.status.value
    except ValueError:
        d = None
        d_status = "NOT_AVAILABLE_FLOAT_EDGE"
    exposure_limiter = classify_limiter(
        _tau_of(qian), _tau_of(sanger), TIME_TIE_TOL_S)

    # ---- Comparison signature (F0 §34) -------------------------------------
    from hyptraj.analysis.sensitivity_trajectory import (
        classify_qian_regime, classify_sanger_regime)
    q_regime = classify_qian_regime(qian.terminal_kind)
    s_skip = None
    from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
    try:
        s_skip = analyze_sanger_trajectory(research, env).skip_count
    except Exception:
        s_skip = None
    s_regime = f"SRTI_N{s_skip}" if s_skip is not None else "SRTI"
    sig = comparison_signature(
        q_regime, s_regime, time_limiter,
        range_limiter or "NA", exposure_limiter, d_status)

    record = {
        "gamma0_deg": initial.flight_path_angle_deg,
        "gamma0_rad": float(np.deg2rad(initial.flight_path_angle_deg)),
        "K": getattr(control, "value", None),
        "qian_regime": q_regime,
        "sanger_regime": s_regime,
        "skip_count": s_skip,
        "qian_terminal_kind": qian.terminal_kind,
        "sanger_terminal_kind": sanger.terminal_kind,
        "sanger_event_resolution": getattr(
            research, "event_resolution", "SOLVER_EVENT"),
        "comparison_value_status": VALUE_VALID,
        "alignment_pass": bool(alignment.all_equal),
        "protocol_b": {
            "status": VALUE_VALID,
            "common_time_s": b.common_time_s,
            "time_limiter": time_limiter,
            "qian_mode": b.qian_mode,
            "sanger_mode": b.sanger_mode,
            "qian_source_mode": b.qian_source_mode,
            "sanger_source_mode": b.sanger_source_mode,
            "delta_range_m": b.delta_range_m,
            "delta_altitude_m": b.delta_altitude_m,
            "delta_velocity_mps": b.delta_velocity_mps,
            "delta_energy_jpkg": b.delta_specific_energy_jpkg,
            "qian_energy_loss_jpkg": b.qian_energy_loss_jpkg,
            "sanger_energy_loss_jpkg": b.sanger_energy_loss_jpkg,
            "initial_energy_jpkg": b.initial_energy_jpkg,
        },
        "protocol_c": (
            {
                "status": c_status,
                "common_range_m": c.common_range_m,
                "range_limiter": range_limiter,
                "qian_mode": c.qian_mode,
                "sanger_mode": c.sanger_mode,
                "qian_arrival_time_s": c.qian_arrival_time_s,
                "sanger_arrival_time_s": c.sanger_arrival_time_s,
                "time_saving_s": c.time_saving_s,
                "delta_altitude_m": c.delta_altitude_m,
                "delta_velocity_mps": c.delta_velocity_mps,
                "delta_energy_jpkg": c.delta_specific_energy_jpkg,
                "qian_range_residual_m": c.qian_range_residual_m,
                "sanger_range_residual_m": c.sanger_range_residual_m,
                "qian_energy_loss_jpkg": c.qian_energy_loss_jpkg,
                "sanger_energy_loss_jpkg": c.sanger_energy_loss_jpkg,
            }
            if c is not None else {"status": c_status}),
        "protocol_d": _protocol_d_record(d, d_status, exposure_limiter),
        "comparison_signature": list(sig),
        "checkpoint_structure": {
            "common_time_sanger_mode": b.sanger_mode,
            "common_range_sanger_mode": (
                c.sanger_mode if c is not None else None),
            "common_exposure_sanger_mode": (
                d.sanger_mode if d is not None else None),
        },
        "native_endpoint_context": {
            "qian_rti_time_s": qian.terminal_time_s,
            "qian_rti_range_m": qian.range_at_time(qian.terminal_time_s),
            "sanger_srti_time_s": sanger.terminal_time_s,
            "sanger_srti_range_m": sanger.range_at_time(
                sanger.terminal_time_s),
        },
        "provenance": {
            "git_commit": git_commit,
            "phase_e_anchor_tag": "phase-e-v1.0",
            "solver": {
                "method": solver.method,
                "rtol": solver.rtol,
                "atol": [float(a) for a in solver.atol],
                "max_step": solver.max_step,
            },
        },
    }
    return record


def _protocol_d_record(d, d_status, exposure_limiter) -> dict:
    """Serialized Protocol-D record; float-edge failures keep formal
    state-difference fields None (never 0, never fabricated)."""
    if d is None:
        return {
            "status": d_status,
            "reason": "float_edge",
            "common_exposure_s": None,
            "exposure_limiter": exposure_limiter,
            "qian_inverse_status": None,
            "sanger_inverse_status": None,
            "qian_plateau_interval_s": None,
            "sanger_plateau_interval_s": None,
            "elapsed_time_extension_s": None,
            "delta_range_m": None,
            "delta_altitude_m": None,
            "delta_velocity_mps": None,
            "delta_energy_jpkg": None,
            "qian_energy_loss_jpkg": None,
            "sanger_energy_loss_jpkg": None,
            "qian_mode": None,
            "sanger_mode": None,
        }
    return {
        "status": d_status,
        "common_exposure_s": d.common_exposure_s,
        "exposure_limiter": exposure_limiter,
        "qian_inverse_status": d.qian_inverse_status.value,
        "sanger_inverse_status": d.sanger_inverse_status.value,
        "qian_plateau_interval_s": (
            list(d.qian_plateau_interval_s)
            if d.qian_plateau_interval_s else None),
        "sanger_plateau_interval_s": (
            list(d.sanger_plateau_interval_s)
            if d.sanger_plateau_interval_s else None),
        "elapsed_time_extension_s": d.elapsed_time_extension_s,
        "delta_range_m": d.delta_range_m,
        "delta_altitude_m": d.delta_altitude_m,
        "delta_velocity_mps": d.delta_velocity_mps,
        "delta_energy_jpkg": d.delta_specific_energy_jpkg,
        "qian_energy_loss_jpkg": d.qian_energy_loss_jpkg,
        "sanger_energy_loss_jpkg": d.sanger_energy_loss_jpkg,
        "qian_mode": d.qian_mode,
        "sanger_mode": d.sanger_mode,
    }



def _tau_of(trajectory: ComparisonTrajectory) -> float:
    """Terminal cumulative atmospheric-mode exposure (F6 §19)."""
    return float(trajectory.total_atmospheric_exposure())


def display_mask_cell(
    corner_signatures: list[tuple[str, ...]],
    exclusion_cells: list[dict],
    cell_rectangle: dict,
) -> tuple[bool, list[str]]:
    """Display/interpolation continuity mask (F6 §25–§26, §49).

    A display cell is masked (no smooth fill across it) when its four
    corners carry different comparison signatures or when any F3
    exclusion box intersects the cell.  This NEVER erases the pointwise
    metric values -- it only blocks smooth interpolation across
    comparison-semantic / grazing boundaries.
    """
    reasons: list[str] = []
    if len({tuple(s) for s in corner_signatures}) > 1:
        reasons.append("COMPARISON_SIGNATURE_TRANSITION")
    for cell in exclusion_cells:
        rect = cell.get("rectangle", cell)
        if _rects_overlap(cell_rectangle, rect):
            reasons.append("F3_EXCLUSION_INTERSECTION")
            break
    return bool(reasons), reasons


def _rects_overlap(a: dict, b: dict) -> bool:
    return not (
        a["gamma_max"] <= b["gamma_min"] or b["gamma_max"] <= a["gamma_min"]
        or a["K_max"] <= b["K_min"] or b["K_max"] <= a["K_min"]
    )
