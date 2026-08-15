"""Phase-F single-parameter pilot infrastructure (F1).

Frozen grids, parameter-point representation, paired one-point execution,
compact / exact topology signatures, transition-interval detection and
baseline-anchor verification for the F1 gamma0 / K one-dimensional
slices.  All execution reuses the F0.1 structured APIs:

* Qian:  ``integrate_qian_research_trajectory`` + ``classify_qian_regime``
* Sanger: ``integrate_sanger_hybrid`` + ``analyze_sanger_trajectory`` +
  ``classify_sanger_regime``

F1 policy (frozen in docs/phase_f/sensitivity_protocol.md):

* no finite-difference derivatives (F4 only);
* no Phase-E Protocol B/C/D surfaces (F6 only);
* no optimization / uncertainty / STM / saltation / FTLE;
* ``NA`` fields are serialized as ``null``, never as numeric zero;
* unexpected programming exceptions propagate (never swallowed);
* stop gates are reported, never silently repaired.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from hyptraj.analysis.sensitivity_trajectory import (
    QIAN_REGIME_BOUNDARY_AMBIGUOUS,
    QIAN_REGIME_CENSORED,
    QIAN_REGIME_INVALID_INPUT,
    QIAN_REGIME_NUMERICAL_FAILURE,
    QIAN_REGIME_RTI,
    SANGER_REGIME_INVALID_INPUT,
    classify_qian_regime,
    classify_sanger_regime,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes.continuous_glide import ENTRY_CAPTURE, QEG_GLIDE
from hyptraj.modes.sanger_hybrid import (
    SANGER_ATM,
    SANGER_VAC,
    specific_mechanical_energy,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.qian_research_trajectory import (
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE,
    TERMINAL_MAX_TIME,
    TERMINAL_RTI,
    TERMINAL_SOLVER_FAILURE,
    integrate_qian_research_trajectory,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import (
    TERMINAL_GROUND_BEFORE_SRTI,
    TERMINAL_MAX_SEGMENTS,
    TERMINAL_MAX_TIME as SANGER_TERMINAL_MAX_TIME,
    TERMINAL_SOLVER_FAILURE as SANGER_TERMINAL_SOLVER_FAILURE,
    TERMINAL_SRTI,
    integrate_sanger_hybrid,
)
from hyptraj.simulation.trajectory import SolverConfig

# ---------------------------------------------------------------------------
# F0-frozen F1 grids (deterministic, no float accumulation; baseline
# (-5.0, 3.0) appears exactly in both slices and is deduplicated once).
# ---------------------------------------------------------------------------
GAMMA_SLICE_DEG: tuple[float, ...] = tuple(
    float(x) for x in np.linspace(-7.0, -3.0, 17)
)  # step 0.25 deg
K_SLICE: tuple[float, ...] = tuple(
    float(x) for x in np.linspace(2.0, 4.0, 17)
)  # step 0.125

ANCHOR_GAMMA0_DEG = -5.0
ANCHOR_K = 3.0

QIAN_MAX_TIME_S = 5000.0
SANGER_MAX_TIME_S = 5000.0
SANGER_MAX_SEGMENTS = 50

# Frozen provenance anchors (F0 / F0.1 protocol commits; never recomputed
# from the moving HEAD).
PHASE_E_ANCHOR_TAG = "phase-e-v1.0"
PHASE_E_ANCHOR_COMMIT = "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc"
F0_PROTOCOL_COMMIT = "1cd0bd52de0d9cec615635949d2805525619d370"
F01_COMMIT = "81b3a9980c0df548786db4145f4e01c917cba1e4"

SCHEMA_VERSION = "f1-pilot-row-v1"


@dataclass(frozen=True)
class ParameterPoint:
    """One controlled parameter point ``p = (gamma0, K)`` (F0 §4)."""

    gamma0_deg: float
    K: float

    @property
    def gamma0_rad(self) -> float:
        return float(np.deg2rad(self.gamma0_deg))

    @property
    def key(self) -> tuple[float, float]:
        """Canonical cache / dedup key (exact frozen grid values)."""
        return (self.gamma0_deg, self.K)


def gamma_slice_points() -> tuple[ParameterPoint, ...]:
    """17-point gamma slice at K = 3.0 (F0 §7)."""
    return tuple(
        ParameterPoint(gamma0_deg=g, K=ANCHOR_K) for g in GAMMA_SLICE_DEG
    )


def k_slice_points() -> tuple[ParameterPoint, ...]:
    """17-point K slice at gamma0 = -5.0 deg (F0 §7)."""
    return tuple(
        ParameterPoint(gamma0_deg=ANCHOR_GAMMA0_DEG, K=k) for k in K_SLICE
    )


def all_unique_points() -> tuple[ParameterPoint, ...]:
    """Ordered union of both slices with the baseline deduplicated (33)."""
    seen: dict[tuple[float, float], ParameterPoint] = {}
    for p in (*gamma_slice_points(), *k_slice_points()):
        seen[p.key] = p
    return tuple(seen.values())


# ---------------------------------------------------------------------------
# Topology signatures (F1 §12, §14)
# ---------------------------------------------------------------------------
def qian_topology_signature(
    terminal_kind: str,
    mode_sequence: tuple[str, ...],
    event_kinds: tuple[str, ...],
) -> str:
    """Stable serializable exact topology signature (no event times)."""
    return (
        f"terminal={terminal_kind};"
        f"modes={' > '.join(mode_sequence)};"
        f"events={' > '.join(event_kinds)}"
    )


def sanger_topology_signature(
    terminal_kind: str,
    mode_sequence: tuple[str, ...],
    event_kinds: tuple[str, ...],
) -> str:
    """Stable serializable Sanger exact topology signature.

    Retains the synthetic E0 and all canonical event kinds (pullout / exit /
    apogee / entry / SRTI), so SRTI_N1 / SRTI_N2 / SRTI_N3 and any
    same-skip-count topology anomaly are distinguishable.
    """
    return (
        f"terminal={terminal_kind};"
        f"modes={' > '.join(mode_sequence)};"
        f"events={' > '.join(event_kinds)}"
    )


# ---------------------------------------------------------------------------
# One-point paired execution
# ---------------------------------------------------------------------------
def _energy(state: np.ndarray, env: EnvironmentParams) -> float:
    """Specific mechanical energy via the frozen helper (never duplicated)."""
    return float(specific_mechanical_energy(state, env))


def _qian_row(
    env: EnvironmentParams,
    point: ParameterPoint,
    result,
    git_commit: str,
    solver: SolverConfig,
) -> dict:
    """Qian row schema (F1 §11; NA -> None)."""
    terminal = result.terminal_state
    event_kinds = tuple(e.kind for e in result.events)
    initial_energy = _energy(result.initial_state, env)
    terminal_energy = _energy(terminal, env)

    capture = result.capture_event
    rti = result.rti_event
    ground = result.ground_event

    row: dict = {
        "schema_version": SCHEMA_VERSION,
        "git_commit": git_commit,
        "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
        "phase_e_anchor_commit": PHASE_E_ANCHOR_COMMIT,
        "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
        "phase_f_f01_commit": F01_COMMIT,
        "solver_config": {
            "method": solver.method,
            "rtol": solver.rtol,
            "atol": [float(a) for a in solver.atol],
            "max_step": solver.max_step,
            "dense_output": solver.dense_output,
        },
        "max_time_s": result.max_time_s,
        "model": "qian",
        "gamma0_deg": point.gamma0_deg,
        "gamma0_rad": point.gamma0_rad,
        "K": point.K,
        "qian_regime": classify_qian_regime(result),
        "terminal_kind": result.terminal_kind,
        "success": result.success,
        "mode_sequence": list(result.mode_sequence),
        "event_sequence": list(event_kinds),
        "exact_topology_signature": qian_topology_signature(
            result.terminal_kind, result.mode_sequence, event_kinds
        ),
        "terminal_time_s": float(result.terminal_time),
        "terminal_range_m": float(env.earth_radius * terminal[1]),
        "terminal_altitude_m": float(terminal[0] - env.earth_radius),
        "terminal_velocity_mps": float(terminal[2]),
        "initial_energy_jpkg": initial_energy,
        "terminal_energy_jpkg": terminal_energy,
        "energy_loss_jpkg": initial_energy - terminal_energy,
        "message": result.message,
    }

    # Optional event fields: None when the event does not exist (never 0).
    if capture is not None:
        row.update(
            {
                "capture_exists": True,
                "capture_time_s": float(capture.time_s),
                "capture_altitude_m": float(capture.state[0] - env.earth_radius),
                "capture_velocity_mps": float(capture.state[2]),
            }
        )
    else:
        row.update(
            {
                "capture_exists": False,
                "capture_time_s": None,
                "capture_altitude_m": None,
                "capture_velocity_mps": None,
            }
        )

    if rti is not None:
        row.update(
            {
                "rti_time_s": float(rti.time_s),
                "rti_range_m": float(env.earth_radius * rti.state[1]),
                "rti_altitude_m": float(rti.state[0] - env.earth_radius),
                "rti_velocity_mps": float(rti.state[2]),
                "qeg_duration_s": (
                    float(rti.time_s - capture.time_s)
                    if capture is not None
                    else None
                ),
            }
        )
    else:
        row.update(
            {
                "rti_time_s": None,
                "rti_range_m": None,
                "rti_altitude_m": None,
                "rti_velocity_mps": None,
                "qeg_duration_s": None,
            }
        )

    # Ground event presence is recorded as a boolean fact (F1 §22 physical
    # terminals are legitimate observations, not failures).
    row["ground_event_detected"] = ground is not None
    return row


def _sanger_row(
    env: EnvironmentParams,
    point: ParameterPoint,
    trajectory,
    metrics,
    git_commit: str,
    solver: SolverConfig,
    max_time: float,
    max_segments: int,
) -> dict:
    """Sanger row schema (F1 §13; NA -> None)."""
    terminal = trajectory.terminal_state
    event_kinds = tuple(e.kind for e in trajectory.events)
    mode_sequence = tuple(s.mode for s in trajectory.segments)
    initial_state = (
        trajectory.segments[0].state_start if trajectory.segments else None
    )
    initial_energy = (
        _energy(initial_state, env) if initial_state is not None else None
    )
    terminal_energy = _energy(terminal, env)

    row: dict = {
        "schema_version": SCHEMA_VERSION,
        "git_commit": git_commit,
        "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
        "phase_e_anchor_commit": PHASE_E_ANCHOR_COMMIT,
        "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
        "phase_f_f01_commit": F01_COMMIT,
        "solver_config": {
            "method": solver.method,
            "rtol": solver.rtol,
            "atol": [float(a) for a in solver.atol],
            "max_step": solver.max_step,
            "dense_output": solver.dense_output,
        },
        "max_time_s": max_time,
        "max_segments": max_segments,
        "model": "sanger",
        "gamma0_deg": point.gamma0_deg,
        "gamma0_rad": point.gamma0_rad,
        "K": point.K,
        "sanger_regime": classify_sanger_regime(
            trajectory, metrics.skip_count
        ),
        "terminal_kind": trajectory.terminal_kind,
        "success": trajectory.success,
        "skip_count": int(metrics.skip_count),
        "mode_sequence": list(mode_sequence),
        "event_sequence": list(event_kinds),
        "exact_topology_signature": sanger_topology_signature(
            trajectory.terminal_kind, mode_sequence, event_kinds
        ),
        "terminal_time_s": float(trajectory.terminal_time),
        "terminal_range_m": float(env.earth_radius * terminal[1]),
        "terminal_altitude_m": float(terminal[0] - env.earth_radius),
        "terminal_velocity_mps": float(terminal[2]),
        "initial_energy_jpkg": initial_energy,
        "terminal_energy_jpkg": terminal_energy,
        "energy_loss_jpkg": (
            initial_energy - terminal_energy
            if initial_energy is not None else None
        ),
        "ATM_duration_s": float(metrics.total_atmospheric_time_s),
        "VAC_duration_s": float(metrics.total_vacuum_time_s),
        "max_altitude_m": float(metrics.maximum_altitude_m),
        "vac_arc_count": int(metrics.vac_segment_count),
        "message": trajectory.message,
    }
    row.update(_sanger_margins(env, trajectory))
    return row


def _sanger_margins(env: EnvironmentParams, trajectory) -> dict:
    """Topology margins from exact event states only (F1 §15).

    Implemented (no duplicated dynamics, no re-integration):
    * ``M_A`` -- per-VAC-apogee clearance ``h_apogee - h_atm``;
    * ``M_S`` -- terminal SRTI clearance ``h_atm - h_SRTI`` (SRTI only);
    * ``exit_dhdt`` -- ``v * sin(gamma)`` at each atmosphere-exit event
      (kinematic definition of ``dh/dt``, single scalar from the state).

    Not implemented in F1 (would require re-writing frozen equations):
    SRTI ``gamma_dot`` transversality -> ``None``.
    """
    h_atm = env.atmosphere_boundary
    m_a: list[float] = []
    exit_dhdt: list[float] = []
    for e in trajectory.events:
        if e.kind == "vacuum_apogee":
            m_a.append(float(e.state[0] - env.earth_radius - h_atm))
        elif e.kind == "atmosphere_exit":
            v = float(e.state[2])
            gamma = float(e.state[3])
            exit_dhdt.append(float(v * np.sin(gamma)))

    m_s = None
    if trajectory.terminal_kind == TERMINAL_SRTI:
        m_s = float(
            h_atm - (trajectory.terminal_state[0] - env.earth_radius)
        )

    return {
        "M_A_clearance_m": m_a,
        "M_S_clearance_m": m_s,
        "exit_dhdt_mps": exit_dhdt,
        "SRTI_transversality_gamma_dot": None,  # F1 does not re-derive it
    }


@dataclass(frozen=True)
class PairedPointResult:
    """One paired (Qian, Sanger) point: serialized rows + raw results.

    ``qian_result`` / ``sanger_trajectory`` are None only for classified
    INVALID_INPUT rows; they are kept for the event-health audit and are
    never serialized (F1 §17.5 metadata is reconstructed from rows).
    """

    parameter: ParameterPoint
    qian_row: dict
    sanger_row: dict
    qian_result: object | None
    sanger_trajectory: object | None


def run_parameter_point(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    point: ParameterPoint,
    git_commit: str,
    solver: SolverConfig = PRODUCTION_SOLVER_CONFIG,
    qian_max_time: float = QIAN_MAX_TIME_S,
    sanger_max_time: float = SANGER_MAX_TIME_S,
    sanger_max_segments: int = SANGER_MAX_SEGMENTS,
) -> PairedPointResult:
    """Run one paired (Qian, Sanger) point; returns rows + raw results.

    A fresh ``InitialCondition`` (only ``flight_path_angle_deg`` changed)
    and a fresh ``ConstantKControl`` are created per point; the baseline
    objects are never mutated.  ``ValueError`` (invalid input) is caught
    and classified per model; any other exception propagates.
    """
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=point.gamma0_deg,
        range_angle=0.0,
    )
    control = ConstantKControl(point.K)

    # ---- Qian -------------------------------------------------------------
    qian_raw: object | None = None
    try:
        qian = integrate_qian_research_trajectory(
            env,
            vehicle,
            initial,
            control,
            solver=solver,
            max_time=qian_max_time,
        )
        qian_raw = qian
        qian_row = _qian_row(env, point, qian, git_commit, solver)
    except ValueError as exc:
        qian_row = {
            "schema_version": SCHEMA_VERSION,
            "git_commit": git_commit,
            "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
            "phase_e_anchor_commit": PHASE_E_ANCHOR_COMMIT,
            "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
            "phase_f_f01_commit": F01_COMMIT,
            "solver_config": None,
            "max_time_s": qian_max_time,
            "model": "qian",
            "gamma0_deg": point.gamma0_deg,
            "gamma0_rad": point.gamma0_rad,
            "K": point.K,
            "qian_regime": QIAN_REGIME_INVALID_INPUT,
            "terminal_kind": None,
            "success": False,
            "mode_sequence": [],
            "event_sequence": [],
            "exact_topology_signature": None,
            "terminal_time_s": None,
            "terminal_range_m": None,
            "terminal_altitude_m": None,
            "terminal_velocity_mps": None,
            "initial_energy_jpkg": None,
            "terminal_energy_jpkg": None,
            "energy_loss_jpkg": None,
            "capture_exists": False,
            "capture_time_s": None,
            "capture_altitude_m": None,
            "capture_velocity_mps": None,
            "rti_time_s": None,
            "rti_range_m": None,
            "rti_altitude_m": None,
            "rti_velocity_mps": None,
            "qeg_duration_s": None,
            "ground_event_detected": False,
            "message": f"INVALID_INPUT: {exc}",
        }

    # ---- Sanger -----------------------------------------------------------
    sanger_raw: object | None = None
    try:
        sanger = integrate_sanger_hybrid(
            env,
            vehicle,
            initial,
            control,
            solver=solver,
            max_time=sanger_max_time,
            max_segments=sanger_max_segments,
        )
        sanger_raw = sanger
        metrics = analyze_sanger_trajectory(sanger, env)
        sanger_row = _sanger_row(
            env,
            point,
            sanger,
            metrics,
            git_commit,
            solver,
            sanger_max_time,
            sanger_max_segments,
        )
    except ValueError as exc:
        sanger_row = {
            "schema_version": SCHEMA_VERSION,
            "git_commit": git_commit,
            "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
            "phase_e_anchor_commit": PHASE_E_ANCHOR_COMMIT,
            "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
            "phase_f_f01_commit": F01_COMMIT,
            "solver_config": None,
            "max_time_s": sanger_max_time,
            "max_segments": sanger_max_segments,
            "model": "sanger",
            "gamma0_deg": point.gamma0_deg,
            "gamma0_rad": point.gamma0_rad,
            "K": point.K,
            "sanger_regime": SANGER_REGIME_INVALID_INPUT,
            "terminal_kind": None,
            "success": False,
            "skip_count": None,
            "mode_sequence": [],
            "event_sequence": [],
            "exact_topology_signature": None,
            "terminal_time_s": None,
            "terminal_range_m": None,
            "terminal_altitude_m": None,
            "terminal_velocity_mps": None,
            "initial_energy_jpkg": None,
            "terminal_energy_jpkg": None,
            "energy_loss_jpkg": None,
            "ATM_duration_s": None,
            "VAC_duration_s": None,
            "max_altitude_m": None,
            "vac_arc_count": None,
            "message": f"INVALID_INPUT: {exc}",
        }

    return PairedPointResult(
        parameter=point,
        qian_row=qian_row,
        sanger_row=sanger_row,
        qian_result=qian_raw,
        sanger_trajectory=sanger_raw,
    )


# ---------------------------------------------------------------------------
# Baseline anchor HARD GATE (F1 §8)
# ---------------------------------------------------------------------------
def verify_baseline_anchor(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    git_commit: str,
    reference_json: dict,
    solver: SolverConfig = PRODUCTION_SOLVER_CONFIG,
    rel_tol: float = 1e-9,
) -> dict:
    """Verify p0 = (-5 deg, 3) against the Phase E frozen reference.

    Compares the structured Qian / Sanger research results with
    ``tests/data/qian_sanger_comparison_v1.json`` within the Phase E
    regression tolerance.  Any mismatch FAILS the whole F1 pilot.
    """
    point = ParameterPoint(gamma0_deg=ANCHOR_GAMMA0_DEG, K=ANCHOR_K)
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=ANCHOR_GAMMA0_DEG,
        range_angle=0.0,
    )
    control = ConstantKControl(ANCHOR_K)

    qian = integrate_qian_research_trajectory(
        env, vehicle, initial, control, solver=solver
    )
    sanger = integrate_sanger_hybrid(
        env, vehicle, initial, control, solver=solver
    )
    sanger_metrics = analyze_sanger_trajectory(sanger, env)

    pv = reference_json["production_values"]
    sem = reference_json["semantic_fields"]

    checks: dict[str, tuple[bool, str]] = {}

    def _check(name: str, ok: bool, detail: str) -> None:
        checks[name] = (bool(ok), detail)

    # Qian
    _check(
        "qian_regime",
        classify_qian_regime(qian) == QIAN_REGIME_RTI,
        f"regime={classify_qian_regime(qian)}",
    )
    q_cap = qian.capture_event.time_s if qian.capture_event else None
    _check(
        "qian_capture_time",
        q_cap is not None
        and abs(q_cap - pv["qian_capture_time"])
        <= rel_tol * abs(pv["qian_capture_time"]),
        f"capture={q_cap}",
    )
    _check(
        "qian_rti_time",
        abs(qian.terminal_time - pv["qian_terminal_time"])
        <= rel_tol * abs(pv["qian_terminal_time"]),
        f"rti={qian.terminal_time}",
    )
    q_range = env.earth_radius * qian.terminal_state[1]
    _check(
        "qian_rti_range",
        abs(q_range - pv["qian_terminal_range"])
        <= rel_tol * abs(pv["qian_terminal_range"]),
        f"range={q_range}",
    )
    _check(
        "qian_mode_sequence",
        tuple(qian.mode_sequence) == tuple(sem["qian_source_structure"]),
        f"modes={tuple(qian.mode_sequence)}",
    )

    # Sanger
    s_regime = classify_sanger_regime(sanger, sanger_metrics.skip_count)
    _check("sanger_regime", s_regime == "SRTI_N2", f"regime={s_regime}")
    _check(
        "sanger_terminal_time",
        abs(sanger.terminal_time - pv["sanger_terminal_time"])
        <= rel_tol * abs(pv["sanger_terminal_time"]),
        f"terminal={sanger.terminal_time}",
    )
    s_range = env.earth_radius * sanger.terminal_state[1]
    _check(
        "sanger_terminal_range",
        abs(s_range - pv["sanger_terminal_range"])
        <= rel_tol * abs(pv["sanger_terminal_range"]),
        f"range={s_range}",
    )
    _check(
        "sanger_skip_count",
        sanger_metrics.skip_count == sem["sanger_skip_count"],
        f"skip={sanger_metrics.skip_count}",
    )
    _check(
        "sanger_mode_sequence",
        tuple(s.mode for s in sanger.segments)
        == tuple(sem["sanger_mode_sequence"]),
        f"modes={tuple(s.mode for s in sanger.segments)}",
    )

    passed = all(ok for ok, _ in checks.values())
    return {
        "pass": passed,
        "point": {"gamma0_deg": ANCHOR_GAMMA0_DEG, "K": ANCHOR_K},
        "qian": {
            "regime": classify_qian_regime(qian),
            "capture_time_s": q_cap,
            "rti_time_s": qian.terminal_time,
            "rti_range_m": q_range,
            "mode_sequence": list(qian.mode_sequence),
        },
        "sanger": {
            "regime": s_regime,
            "terminal_time_s": sanger.terminal_time,
            "terminal_range_m": s_range,
            "skip_count": int(sanger_metrics.skip_count),
            "mode_sequence": [s.mode for s in sanger.segments],
        },
        "checks": {name: {"pass": ok, "detail": d} for name, (ok, d) in checks.items()},
    }


# ---------------------------------------------------------------------------
# Transition-interval detection (F1 §17–§18)
# ---------------------------------------------------------------------------
def detect_transition_intervals(
    ordered: list[PairedPointResult],
    parameter_name: str,
) -> tuple[list[dict], list[dict]]:
    """Scan an ordered slice for regime / topology transitions.

    Returns ``(compact_transitions, exact_topology_only_transitions)``.
    A compact transition fires when either model's compact regime changes;
    an exact-topology-only transition fires when the compact regimes are
    identical but an exact topology signature changed.
    """

    def _value(p: PairedPointResult) -> float:
        return (
            p.parameter.gamma0_deg
            if parameter_name == "gamma0"
            else p.parameter.K
        )

    compact: list[dict] = []
    exact_only: list[dict] = []

    def _qian_regime(r: PairedPointResult) -> str:
        return r.qian_row["qian_regime"]

    def _sanger_regime(r: PairedPointResult) -> str:
        return r.sanger_row["sanger_regime"]

    def _qian_sig(r: PairedPointResult) -> str:
        return r.qian_row["exact_topology_signature"]

    def _sanger_sig(r: PairedPointResult) -> str:
        return r.sanger_row["exact_topology_signature"]

    for left, right in zip(ordered, ordered[1:]):
        compact_changed = (
            _qian_regime(left) != _qian_regime(right)
            or _sanger_regime(left) != _sanger_regime(right)
        )
        exact_changed = (
            _qian_sig(left) != _qian_sig(right)
            or _sanger_sig(left) != _sanger_sig(right)
        )
        interval = {
            "parameter": parameter_name,
            "left_value": _value(left),
            "right_value": _value(right),
            "left_qian_regime": _qian_regime(left),
            "right_qian_regime": _qian_regime(right),
            "left_sanger_regime": _sanger_regime(left),
            "right_sanger_regime": _sanger_regime(right),
        }
        if compact_changed:
            compact.append({**interval, "transition_type": "compact"})
        elif exact_changed:
            exact_only.append(
                {**interval, "transition_type": "exact-topology-only"}
            )
    return compact, exact_only


# ---------------------------------------------------------------------------
# Event-health audit (F1 §25) -- operates on the RAW trajectory results
# ---------------------------------------------------------------------------
def audit_point_health(
    point: ParameterPoint,
    qian_result,
    sanger_trajectory,
) -> list[str]:
    """Return event-health violations for one paired point ([] = healthy).

    Checks strict time monotonicity of event times, zero/negative segment
    durations and NaN/Inf terminal states.  Sanger event times are already
    guaranteed strictly increasing by the frozen ``_append_event`` guard;
    this audit re-verifies defensively and catches chatter / duplicate
    roots / zero-duration segments in the serialized pilot.
    """
    violations: list[str] = []
    label = f"gamma0={point.gamma0_deg}, K={point.K}"

    qian_times = [e.time_s for e in qian_result.events]
    if any(
        b <= a for a, b in zip(qian_times, qian_times[1:])
    ):
        violations.append(f"Qian {label}: event times not strictly "
                          f"increasing: {qian_times}")
    for seg in qian_result.segments:
        if seg.t_end <= seg.t_start:
            violations.append(f"Qian {label}: zero/negative segment "
                              f"duration [{seg.t_start}, {seg.t_end}]")
    if not np.all(np.isfinite(qian_result.terminal_state)):
        violations.append(f"Qian {label}: NaN/Inf in terminal state")

    sanger_times = [e.time for e in sanger_trajectory.events]
    if any(
        b <= a for a, b in zip(sanger_times, sanger_times[1:])
    ):
        violations.append(f"Sanger {label}: event times not strictly "
                          f"increasing: {sanger_times}")
    for seg in sanger_trajectory.segments:
        if seg.t_end <= seg.t_start:
            violations.append(f"Sanger {label}: zero/negative segment "
                              f"duration [{seg.t_start}, {seg.t_end}]")
    if not np.all(np.isfinite(sanger_trajectory.terminal_state)):
        violations.append(f"Sanger {label}: NaN/Inf in terminal state")

    return violations


# ---------------------------------------------------------------------------
# Stop-gate collection (F1 §23) -- pure function shared by runner + tests
# ---------------------------------------------------------------------------
def collect_stop_gate_reasons(
    anchor_pass: bool,
    qian_rows: list[dict],
    sanger_rows: list[dict],
    health_violations: list[str],
) -> list[str]:
    """Return all F1 stop-gate reasons ([] = no stop gate triggered).

    F1 §23 gates: baseline anchor mismatch, NUMERICAL_FAILURE, unexpected
    INVALID_INPUT, CENSORED under the production horizon, event chatter /
    invalid ordering / zero-duration segments, NaN/Inf, unknown terminal
    kind (classifier KeyError) and real BOUNDARY_AMBIGUOUS points.
    """
    reasons: list[str] = []
    if not anchor_pass:
        reasons.append("baseline anchor mismatch")

    for r in qian_rows:
        g, k = r["gamma0_deg"], r["K"]
        regime = r["qian_regime"]
        if regime == QIAN_REGIME_NUMERICAL_FAILURE:
            reasons.append(f"Qian NUMERICAL_FAILURE at gamma0={g}, K={k}: "
                           f"{r['message']}")
        elif regime == QIAN_REGIME_CENSORED:
            reasons.append(f"Qian CENSORED at gamma0={g}, K={k}: "
                           f"{r['message']}")
        elif regime == QIAN_REGIME_INVALID_INPUT:
            reasons.append(f"Qian INVALID_INPUT at gamma0={g}, K={k}: "
                           f"{r['message']}")
        elif regime == QIAN_REGIME_BOUNDARY_AMBIGUOUS:
            reasons.append(f"Qian BOUNDARY_AMBIGUOUS at gamma0={g}, K={k}: "
                           f"{r['message']}")

    for r in sanger_rows:
        g, k = r["gamma0_deg"], r["K"]
        regime = r["sanger_regime"]
        if regime == "NUMERICAL_FAILURE":
            reasons.append(f"Sanger NUMERICAL_FAILURE at gamma0={g}, K={k}: "
                           f"{r['message']}")
        elif regime == "CENSORED":
            reasons.append(f"Sanger CENSORED at gamma0={g}, K={k}: "
                           f"{r['message']}")
        elif regime == "INVALID_INPUT":
            reasons.append(f"Sanger INVALID_INPUT at gamma0={g}, K={k}: "
                           f"{r['message']}")

    reasons.extend(f"event-health: {v}" for v in health_violations)
    return reasons
