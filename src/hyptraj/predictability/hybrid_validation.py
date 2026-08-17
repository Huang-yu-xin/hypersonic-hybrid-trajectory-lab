"""Phase-G4 independent full-hybrid nonlinear validation (G4 §20-§32).

The analytic hybrid STM (built in ``hybrid_stm``) is validated against an
INDEPENDENT path: the FROZEN research trajectory integrators
(``integrate_qian_research_trajectory`` / ``integrate_sanger_research_
trajectory``) run directly at perturbed initial states, and the
fixed-time endpoint state / true-switch times are extracted from the
exact dense output.  A centered fixed-time FD column

    D_j^NL(T) = [ x(T; x0 + eps_j e_j) - x(T; x0 - eps_j e_j) ] / (2 eps_j)

is compared against ``Phi_H(T, 0)``; a full-hybrid topology gate and the
G2R-style both-side pair gate decide which columns enter acceptance.

Global event-time gradient FD (G4 §30): matching by topology position +
event kind (never nearest-time heuristics):

    D^{t_k} ~= eta_k = q_k Phi_k^-.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability.hybrid_stm import (
    TRUE_SWITCH_KINDS,
    true_switch_events_before,
)
from hyptraj.predictability.jacobian import (
    STATE_DIM,
    classify_qeg_active_set,
    u_l_star,
)

# G2/G3-linked FD RESEARCH base step (never canonical scientific scaling).
HYBRID_FD_BASE_STEP = np.array([100.0, 1e-5, 1.0, 1e-4])
HYBRID_FD_MULTIPLIERS = (1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0, 3.0, 10.0)
QEG_GRID_SAMPLES = 41


class HybridTopologyGate(Enum):
    """Full-hybrid topology classification (G4 §24, G0 categories)."""

    TOPOLOGY_PRESERVED = "TOPOLOGY_PRESERVED"
    TOPOLOGY_CHANGED = "TOPOLOGY_CHANGED"
    EVENT_ORDER_CHANGED = "EVENT_ORDER_CHANGED"
    GRAZING_CROSSED = "GRAZING_CROSSED"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


def _initial_condition_from_state(
    x0: np.ndarray, env: EnvironmentParams,
) -> InitialCondition:
    x0 = np.asarray(x0, dtype=float)
    return InitialCondition(
        altitude=float(x0[0] - env.earth_radius),
        velocity=float(x0[2]),
        flight_path_angle_deg=float(np.rad2deg(x0[3])),
        range_angle=float(x0[1]),
    )


def run_nonlinear_hybrid(
    model: str,
    x0: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    research_solver,
):
    """Run the FROZEN research trajectory at a perturbed initial state.

    Returns ``(trajectory_result, collector)``; the collector exposes the
    exact dense-output segments for fixed-time extraction.
    """
    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    ctl = ConstantKControl(k)
    initial = _initial_condition_from_state(x0, env)
    collector = DenseOutputCollector()
    if model == "qian":
        traj = integrate_qian_research_trajectory(
            env, vehicle, initial, ctl,
            solver=research_solver, dense_output_collector=collector,
        )
    else:
        traj = integrate_sanger_research_trajectory(
            env, vehicle, initial, ctl,
            solver=research_solver, dense_output_collector=collector,
        )
    return traj, collector


def fixed_time_state(collector, t: float) -> tuple[np.ndarray, str | None]:
    """Exact fixed-time state/mode from the frozen dense output (G4 §22)."""
    for seg in collector.segments:
        if float(seg.t_start) <= float(t) <= float(seg.t_end):
            state = np.asarray(seg.solution(float(t)), dtype=float)
            return state, str(seg.mode)
    raise ValueError(f"t = {t} outside collected segments.")


def _trajectory_true_switch_times(result, t_scan: float) -> list[dict]:
    if hasattr(result, "events"):  # QianResearchTrajectory
        events = list(result.events)
    else:  # SangerResearchTrajectory wraps SangerHybridTrajectory
        events = list(result.trajectory.events)
    return true_switch_events_before(t_scan, events)


def _qeg_interior_ok(collector, capture_time: float, t_end: float,
                     env, vehicle, k, n_samples=QEG_GRID_SAMPLES) -> bool:
    """QEG active-set preservation on [capture, t_end] (G4 §32)."""
    grid = np.linspace(capture_time, t_end, n_samples)
    for t in grid:
        try:
            state, _mode = fixed_time_state(collector, t)
            us = u_l_star(state, env, vehicle, k)
        except Exception:
            return False
        if classify_qeg_active_set(us) != classify_qeg_active_set(0.5):
            return False
    return True


def _trajectory_terminal_time(result) -> float:
    """Frozen terminal time from a Qian or Sanger research result."""
    if hasattr(result, "trajectory"):
        return float(result.trajectory.terminal_time)
    return float(result.terminal_time)


def _trajectory_terminal_kind(result) -> str:
    """Frozen structured terminal kind (never parsed from message text).

    Compatible with ``QianResearchTrajectory`` (``terminal_kind`` directly)
    and ``SangerResearchTrajectory`` (``trajectory.terminal_kind``).
    """
    if hasattr(result, "trajectory"):
        return str(result.trajectory.terminal_kind)
    return str(result.terminal_kind)


# Frozen structured terminal kinds (Qian research API, F0.1 §5).
_QIAN_TERMINAL_KINDS = (
    "RTI", "GROUND_BEFORE_CAPTURE", "GROUND_AFTER_CAPTURE_BEFORE_RTI",
    "MAX_TIME", "SOLVER_FAILURE", "AMBIGUOUS_SIMULTANEOUS_EVENT",
)
# Frozen structured terminal kinds (Sanger research API, D3 / F2.1).
_SANGER_TERMINAL_KINDS = (
    "srti", "ground_before_srti", "max_time", "max_segments",
    "solver_failure", "grazing_or_unresolved_event",
)
_SOLVER_FAILURE_KINDS = frozenset({"SOLVER_FAILURE", "solver_failure"})
_GRAZING_KINDS = frozenset({"grazing_or_unresolved_event"})
_PHYSICAL_TERMINAL_KINDS = frozenset({
    "GROUND_BEFORE_CAPTURE", "GROUND_AFTER_CAPTURE_BEFORE_RTI",
    "ground_before_srti", "RTI", "srti",
})
_CENSOR_KINDS = frozenset({"MAX_TIME", "max_time", "max_segments"})
_AMBIGUOUS_KINDS = frozenset({"AMBIGUOUS_SIMULTANEOUS_EVENT"})


def _classify_terminal_before(
    result,
    t_final: float,
) -> tuple[HybridTopologyGate | None, str]:
    """Endpoint-scoped terminal classification (G4R §4).

    Returns ``(None, "")`` when the frozen terminal occurs AFTER the fixed
    endpoint (``terminal_time > T``) -- in that case the fixed-time prefix
    is unaffected and downstream checks decide the gate.  A terminal that
    occurs at or before ``T`` is routed by its STRUCTURED ``terminal_kind``:

    * solver failure            -> NUMERICAL_FAILURE
    * grazing_or_unresolved     -> GRAZING_CROSSED
    * physical terminals (RTI / SRTI / ground / ...) -> TOPOLOGY_CHANGED
    * computational censor      -> TOPOLOGY_CHANGED
    * ambiguous simultaneous    -> TOPOLOGY_CHANGED
    """
    terminal_time = _trajectory_terminal_time(result)
    if terminal_time > t_final:
        return None, ""
    kind = _trajectory_terminal_kind(result)
    if kind in _SOLVER_FAILURE_KINDS:
        return HybridTopologyGate.NUMERICAL_FAILURE, \
            "solver_failure_before_fixed_endpoint"
    if kind in _GRAZING_KINDS:
        return HybridTopologyGate.GRAZING_CROSSED, \
            "grazing_or_unresolved_before_fixed_endpoint"
    if kind in _PHYSICAL_TERMINAL_KINDS:
        return HybridTopologyGate.TOPOLOGY_CHANGED, \
            f"terminal_before_fixed_endpoint:{kind}"
    if kind in _CENSOR_KINDS:
        return HybridTopologyGate.TOPOLOGY_CHANGED, \
            "computational_censor_before_fixed_endpoint"
    if kind in _AMBIGUOUS_KINDS:
        return HybridTopologyGate.TOPOLOGY_CHANGED, \
            "ambiguous_simultaneous_event_before_fixed_endpoint"
    return HybridTopologyGate.TOPOLOGY_CHANGED, \
        f"terminal_before_fixed_endpoint:{kind}"


def classify_perturbed_topology(
    model: str,
    nominal_signature: tuple[str, ...],
    nominal_endpoint_mode: str,
    result,
    collector,
    t_final: float,
    env, vehicle, k,
    check_qeg_interior: bool,
) -> tuple[HybridTopologyGate, dict]:
    """Full-hybrid topology gate for one perturbed trajectory (G4 §24, G4R).

    G4R corrective contract:

    * ``result.success == False`` is NOT a generic numerical failure; the
      gate is ENDPOINT-SCOPED -- a terminal/failure only matters if it
      occurs at or before ``t_final``, or if the dense fixed-time state /
      topology cannot be obtained at ``t_final``;
    * ``EVENT_ORDER_CHANGED`` requires the SAME length and the SAME event
      multiset INCLUDING multiplicity (``Counter``), with a different
      chronological sequence -- a missing / extra repeated pair is
      ``TOPOLOGY_CHANGED``, never ``EVENT_ORDER_CHANGED``.

    Resolution order: no-result -> terminal-before-T -> dense endpoint
    availability -> signature / endpoint mode / event order -> QEG
    active-set -> TOPOLOGY_PRESERVED.
    """
    if result is None:
        return HybridTopologyGate.NUMERICAL_FAILURE, {
            "reason": "no_result", "terminal_time": None}

    terminal_gate, term_reason = _classify_terminal_before(result, t_final)
    if terminal_gate is not None:
        return terminal_gate, {
            "reason": term_reason,
            "terminal_time": _trajectory_terminal_time(result),
            "terminal_kind": _trajectory_terminal_kind(result),
        }

    # Terminal (if any) occurs after T: the fixed-time prefix may still be
    # a valid TOPOLOGY_PRESERVED object (endpoint-scoped semantics).
    try:
        _, endpoint_mode = fixed_time_state(collector, t_final)
    except Exception:
        return HybridTopologyGate.NUMERICAL_FAILURE, {
            "reason": "fixed_endpoint_unavailable",
            "terminal_time": _trajectory_terminal_time(result),
        }

    switches = _trajectory_true_switch_times(result, t_final)
    pert_sig = tuple(sw["kind"] for sw in switches)

    if pert_sig != nominal_signature:
        same_multiset = Counter(pert_sig) == Counter(nominal_signature)
        same_length = len(pert_sig) == len(nominal_signature)
        if same_length and same_multiset:
            return HybridTopologyGate.EVENT_ORDER_CHANGED, {
                "reason": "event_order_changed",
                "pert_signature": list(pert_sig),
                "endpoint_mode": endpoint_mode,
            }
        return HybridTopologyGate.TOPOLOGY_CHANGED, {
            "reason": "signature_changed",
            "pert_signature": list(pert_sig),
            "endpoint_mode": endpoint_mode,
        }
    if endpoint_mode != nominal_endpoint_mode:
        return HybridTopologyGate.TOPOLOGY_CHANGED, {
            "reason": "endpoint_mode_changed",
            "pert_signature": list(pert_sig),
            "endpoint_mode": endpoint_mode,
        }

    # QEG strict-interior preservation (Qian)
    if check_qeg_interior:
        capture_time = None
        for sw in switches:
            if sw["kind"] == "qian_capture":
                capture_time = sw["time"]
                break
        if capture_time is not None:
            if not _qeg_interior_ok(collector, capture_time, t_final,
                                    env, vehicle, k):
                return HybridTopologyGate.TOPOLOGY_CHANGED, {
                    "reason": "QEG_ACTIVE_SET_CHANGED",
                    "pert_signature": list(pert_sig),
                    "endpoint_mode": endpoint_mode,
                }
    return HybridTopologyGate.TOPOLOGY_PRESERVED, {
        "reason": "ok",
        "pert_signature": list(pert_sig),
        "endpoint_mode": endpoint_mode,
        "terminal_time": _trajectory_terminal_time(result),
        "terminal_kind": _trajectory_terminal_kind(result),
    }


def nonlinear_fixed_time_state(
    model: str,
    x0: np.ndarray,
    t_final: float,
    env, vehicle, k,
    research_solver,
    check_qeg_interior: bool,
    nominal_signature: tuple[str, ...],
    nominal_endpoint_mode: str,
) -> tuple[np.ndarray | None, HybridTopologyGate, dict]:
    """Independent path: nonlinear hybrid state at fixed time ``t_final``.

    Returns ``(x_at_T, classification, info)``; ``x_at_T`` is ``None``
    unless TOPOLOGY_PRESERVED (only preserved columns enter acceptance).
    """
    from hyptraj.predictability.hybrid_stm import jacobian_mode  # noqa: F401
    result, collector = run_nonlinear_hybrid(
        model, x0, env, vehicle, k, research_solver)
    gate, info = classify_perturbed_topology(
        model, nominal_signature, nominal_endpoint_mode,
        result, collector, t_final, env, vehicle, k, check_qeg_interior)
    if gate != HybridTopologyGate.TOPOLOGY_PRESERVED:
        return None, gate, info
    x_T, _mode = fixed_time_state(collector, t_final)
    info = {**info, "x_at_T": x_T,
            "switch_times": [sw["time"] for sw in
                             _trajectory_true_switch_times(result, t_final)]}
    return x_T, gate, info


def hybrid_fixed_time_fd_sweep(
    model: str,
    x0: np.ndarray,
    t_final: float,
    env, vehicle, k,
    research_solver,
    phi_hybrid: np.ndarray,
    nominal_signature: tuple[str, ...],
    nominal_endpoint_mode: str,
    check_qeg_interior: bool,
    base_step=HYBRID_FD_BASE_STEP,
    multipliers=HYBRID_FD_MULTIPLIERS,
) -> dict:
    """Per-column centered hybrid FD sweep vs the analytic hybrid STM."""
    x0 = np.asarray(x0, dtype=float)
    out = {}
    for mult in multipliers:
        eps = base_step * mult
        fd = np.zeros((STATE_DIM, STATE_DIM))
        cls_plus: list[str] = []
        cls_minus: list[str] = []
        valid_col = np.zeros(STATE_DIM, dtype=bool)
        deets = {}
        for j in range(STATE_DIM):
            e_j = np.eye(STATE_DIM)[:, j]
            xp, cp, ip_ = nonlinear_fixed_time_state(
                model, x0 + eps[j] * e_j, t_final, env, vehicle, k,
                research_solver, check_qeg_interior, nominal_signature,
                nominal_endpoint_mode)
            xm, cm, im_ = nonlinear_fixed_time_state(
                model, x0 - eps[j] * e_j, t_final, env, vehicle, k,
                research_solver, check_qeg_interior, nominal_signature,
                nominal_endpoint_mode)
            cls_plus.append(cp.value)
            cls_minus.append(cm.value)
            deets[f"col_{j}"] = {
                "plus_signature": ip_.get("pert_signature"),
                "plus_endpoint_mode": ip_.get("endpoint_mode"),
                "plus_reason": ip_.get("reason"),
                "minus_signature": im_.get("pert_signature"),
                "minus_endpoint_mode": im_.get("endpoint_mode"),
                "minus_reason": im_.get("reason"),
            }
            if cp == HybridTopologyGate.TOPOLOGY_PRESERVED and \
                    cm == HybridTopologyGate.TOPOLOGY_PRESERVED and \
                    xp is not None and xm is not None:
                fd[:, j] = (xp - xm) / (2.0 * float(eps[j]))
                valid_col[j] = True
        n_valid = int(valid_col.sum())
        diff = fd - phi_hybrid
        max_abs = float(np.max(np.abs(diff)))
        scale = float(np.max(np.abs(phi_hybrid)))
        mat = np.abs(phi_hybrid) >= 1e-8 * max(scale, 1e-300)
        rel = (float(np.max(np.abs(diff[mat]) / np.maximum(
            np.abs(phi_hybrid[mat]), 1e-300))) if mat.any() else 0.0)
        out[f"mult_{mult:g}"] = {
            "multiplier": mult,
            "n_valid_columns": n_valid,
            "classification_plus": cls_plus,
            "classification_minus": cls_minus,
            "details": deets,
            "fd_matrix": [[float(fd[i, j]) for j in range(STATE_DIM)]
                          for i in range(STATE_DIM)],
            "max_abs_error": (max_abs if n_valid == STATE_DIM else None),
            "material_rel_error": (rel if n_valid == STATE_DIM else None),
            "per_column_abs": ([float(np.max(np.abs(diff[:, j])))
                                for j in range(STATE_DIM)]
                               if n_valid == STATE_DIM else None),
        }
    return out


def global_event_time_fd(
    model: str,
    x0: np.ndarray,
    t_final: float,
    env, vehicle, k,
    research_solver,
    nominal_signature: tuple[str, ...],
    nominal_endpoint_mode: str,
    check_qeg_interior: bool,
    eta_list: list[np.ndarray],
    event_kinds: list[str],
    base_step=HYBRID_FD_BASE_STEP,
    multipliers=(1e-2, 1e-1, 1.0),
) -> dict:
    """Global event-time FD ``D^{t_k}`` vs ``eta_k = q_k Phi_k^-``.

    Matching by topology position + event kind (G4 §30); only
    topology-preserved pairs contribute.  ``eta_list`` / ``event_kinds``
    are indexed by the nominal true-switch position (the k-th true
    switch before T).
    """
    x0 = np.asarray(x0, dtype=float)
    out = {}
    for mult in multipliers:
        eps = base_step * mult
        row = {}
        for k_idx, kind in enumerate(event_kinds):
            per_col = {}
            for j in range(STATE_DIM):
                e_j = np.eye(STATE_DIM)[:, j]
                tps, cps, _ = _nonlinear_event_time(
                    model, x0, eps, j, +1.0, t_final, env, vehicle, k,
                    research_solver, nominal_signature,
                    nominal_endpoint_mode, check_qeg_interior, k_idx)
                tms, cms, _m = _nonlinear_event_time(
                    model, x0, eps, j, -1.0, t_final, env, vehicle, k,
                    research_solver, nominal_signature,
                    nominal_endpoint_mode, check_qeg_interior, k_idx)
                if tps is None or tms is None:
                    per_col[f"col_{j}"] = {"fd": None, "cls": [cps.value, cms.value]}
                    continue
                fd = (tps - tms) / (2.0 * float(eps[j]))
                eta = float(np.asarray(eta_list[k_idx])[j])
                per_col[f"col_{j}"] = {
                    "fd": fd, "eta": eta,
                    "abs_error": abs(fd - eta),
                    "material_rel_error": (abs(fd - eta) / abs(eta)
                                           if abs(eta) > 1e-12 else None),
                    "cls": [cps.value, cms.value],
                }
            row[f"switch_{k_idx}"] = per_col
        out[f"mult_{mult:g}"] = row
    return out


def _nonlinear_event_time(
    model, x0, eps, j, sign, t_final, env, vehicle, k, research_solver,
    nominal_signature, nominal_endpoint_mode, check_qeg_interior, k_idx,
):
    """Perturbed k-th true-switch time (topology-position matched)."""
    e_j = np.eye(STATE_DIM)[:, j]
    x_pert = x0 + sign * eps[j] * e_j
    result, collector = run_nonlinear_hybrid(
        model, x_pert, env, vehicle, k, research_solver)
    terminal_gate, term_reason = _classify_terminal_before(result, t_final)
    if terminal_gate is not None:
        return None, terminal_gate, {"reason": term_reason}
    try:
        _, ep_mode = fixed_time_state(collector, t_final)
    except Exception:
        return None, HybridTopologyGate.NUMERICAL_FAILURE, {
            "reason": "fixed_endpoint_unavailable"}
    switches = _trajectory_true_switch_times(result, t_final)
    pert_sig = tuple(sw["kind"] for sw in switches)
    if pert_sig != nominal_signature or ep_mode != nominal_endpoint_mode:
        return None, HybridTopologyGate.TOPOLOGY_CHANGED, {}
    if k_idx >= len(switches):
        return None, HybridTopologyGate.TOPOLOGY_CHANGED, {}
    if switches[k_idx]["kind"] != nominal_signature[k_idx]:
        return None, HybridTopologyGate.EVENT_ORDER_CHANGED, {}
    t_ev = float(switches[k_idx]["time"])
    # QEG interior preservation (Qian)
    if check_qeg_interior:
        cap_times = [sw["time"] for sw in switches if sw["kind"] == "qian_capture"]
        if cap_times:
            if not _qeg_interior_ok(collector, cap_times[-1], t_final,
                                    env, vehicle, k):
                return None, HybridTopologyGate.TOPOLOGY_CHANGED, {}
    return t_ev, HybridTopologyGate.TOPOLOGY_PRESERVED, {}