"""D6 shared helpers for the Sanger numerical / hybrid-topology validation.

All runs reuse the D3/D4 production implementation; configuration
changes are injected ONLY through ``SolverConfig``.
"""

import json
import time
from pathlib import Path

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes.sanger_hybrid import sanger_atm_rhs
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    SRTI,
    integrate_sanger_hybrid,
)
from hyptraj.simulation.trajectory import SolverConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results" / "sanger_hybrid" / "numerical_validation"

# Reference configuration (Phase C philosophy: high-precision numerical
# reference, NOT an analytic solution).
REFERENCE_0_1 = SolverConfig(
    method="DOP853",
    rtol=1e-12,
    atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
    max_step=0.1,
    dense_output=True,
)
REFERENCE_0_05 = SolverConfig(
    method="DOP853",
    rtol=1e-12,
    atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
    max_step=0.05,
    dense_output=True,
)

# Phase C state-scaled atol coupling: atol = rtol * [1e5, 1e-2, 1e2, 1e-2]
_ATOL_SCALE = np.array([1e5, 1e-2, 1e2, 1e-2])


def scaled_atol(rtol: float) -> np.ndarray:
    """Coupled component-scaled atol for the tolerance sweep."""
    return float(rtol) * _ATOL_SCALE


def get_baseline_setup():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    return env, vehicle, initial, control


def run_case(
    solver: SolverConfig,
    max_time: float = 5000.0,
    max_segments: int = 50,
):
    """Run one Sanger trajectory + metrics with the given solver config.

    Returns ``(traj, metrics, runtime_s)``.
    """
    env, vehicle, initial, control = get_baseline_setup()
    t0 = time.perf_counter()
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control,
        solver=solver, max_time=max_time, max_segments=max_segments,
    )
    metrics = analyze_sanger_trajectory(traj, env)
    runtime = time.perf_counter() - t0
    return traj, metrics, runtime


# ---------------------------------------------------------------------------
# Topology / structural diagnostics
# ---------------------------------------------------------------------------
def topology_record(traj, metrics) -> dict:
    """Structural validity record, independent of floating-point errors."""
    real_times = [e.time for e in traj.events if not e.is_synthetic]
    switches = [
        e.kind for e in traj.events
        if e.kind in (ATMOSPHERE_EXIT, ATMOSPHERE_ENTRY)
    ]
    finite = all(
        np.all(np.isfinite(s.y)) and np.all(np.isfinite(s.state_start))
        and np.all(np.isfinite(s.state_end))
        for s in traj.segments
    )
    continuity = all(
        np.array_equal(traj.segments[i].state_start,
                       traj.segments[i - 1].state_end)
        for i in range(1, len(traj.segments))
    )
    return {
        "success": bool(traj.success),
        "terminal_kind": traj.terminal_kind,
        "skip_count": int(metrics.skip_count),
        "atm_segment_count": int(metrics.atm_segment_count),
        "vac_segment_count": int(metrics.vac_segment_count),
        "mode_sequence": [s.mode for s in traj.segments],
        "event_sequence": [e.kind for e in traj.events],
        "event_order_valid": bool(
            traj.terminal_kind == SRTI
            and traj.events[-1].kind == SRTI),
        "event_times_strictly_increasing": bool(
            all(b > a for a, b in zip(real_times, real_times[1:]))),
        "zero_duration_segments": int(
            sum(1 for s in traj.segments if s.t_end <= s.t_start)),
        "state_continuity": bool(continuity),
        "chatter": bool(not all(
            a != b for a, b in zip(switches, switches[1:]))),
        "nan_inf": bool(not finite),
    }


def topology_equal(topo: dict, ref_topo: dict) -> bool:
    """Topology identical to the reference (structure only)."""
    keys = (
        "success", "terminal_kind", "skip_count", "atm_segment_count",
        "vac_segment_count", "mode_sequence", "event_sequence",
    )
    return all(topo[k] == ref_topo[k] for k in keys)


def event_errors(traj, ref_events: list) -> dict:
    """Per-event absolute errors vs a reference event list.

    ``ref_events`` is a list of dicts with kind / time / state (the
    reference trajectory events).  Returns per-event errors for the
    common kinds plus the max-error summary.
    """
    ref_by_kind: dict[str, list] = {}
    for r in ref_events:
        ref_by_kind.setdefault(r["kind"], []).append(r)

    errors = []
    for e in traj.events:
        refs = ref_by_kind.get(e.kind)
        if not refs:
            continue
        # Same-kind events are matched chronologically.
        ref = refs.pop(0)
        errors.append({
            "kind": e.kind,
            "dt_s": abs(e.time - ref["time"]),
            "dh_m": abs(e.state[0] - ref["state"][0]),
            "dv_mps": abs(e.state[2] - ref["state"][2]),
            "dR_m": abs(e.state[1] - ref["state"][1])
            * (ref.get("earth_radius", 6_371_000.0)),
            "dgamma_rad": abs(e.state[3] - ref["state"][3]),
        })
    return {
        "per_event": errors,
        "max_dt_s": max((e["dt_s"] for e in errors), default=0.0),
        "max_dh_m": max((e["dh_m"] for e in errors), default=0.0),
        "max_dv_mps": max((e["dv_mps"] for e in errors), default=0.0),
        "max_dR_m": max((e["dR_m"] for e in errors), default=0.0),
        "max_dgamma_rad": max((e["dgamma_rad"] for e in errors),
                              default=0.0),
    }


# ---------------------------------------------------------------------------
# Event residuals and crossing directions
# ---------------------------------------------------------------------------
def event_residuals(traj, env) -> dict:
    """Event-root residuals: |h - h_atm| for ATM switching, |gamma| for
    pull-out / apogee / SRTI."""
    atm_res = []
    gamma_res = []
    for e in traj.events:
        if e.kind in (ATMOSPHERE_EXIT, ATMOSPHERE_ENTRY):
            atm_res.append(abs(e.state[0] - env.earth_radius
                               - env.atmosphere_boundary))
        elif e.kind in ("atmospheric_pullout", "vacuum_apogee", SRTI):
            gamma_res.append(abs(e.state[3]))
    return {
        "max_atmosphere_residual_m": max(atm_res, default=0.0),
        "max_gamma_residual_rad": max(gamma_res, default=0.0),
    }


def _g_value(kind: str, state: np.ndarray, env) -> float:
    if kind in (ATMOSPHERE_EXIT, ATMOSPHERE_ENTRY):
        return float(state[0] - env.earth_radius - env.atmosphere_boundary)
    return float(state[3])  # pull-out / apogee / SRTI


def crossing_directions(traj, env) -> dict:
    """Verify each event's crossing direction from the sampled segment
    grids (no state perturbation): pull-out - -> +, exit - -> +,
    apogee + -> -, entry + -> -, SRTI + -> -."""
    expected = {
        "atmospheric_pullout": (-1.0, +1.0),
        ATMOSPHERE_EXIT: (-1.0, +1.0),
        "vacuum_apogee": (+1.0, -1.0),
        ATMOSPHERE_ENTRY: (+1.0, -1.0),
        SRTI: (+1.0, -1.0),
    }
    results = {}
    for e in traj.events:
        if e.kind not in expected:
            continue
        seg = next(
            s for s in traj.segments
            if s.t_start <= e.time <= s.t_end)
        i1 = int(np.searchsorted(seg.t, e.time))
        if i1 <= 0 or i1 >= seg.t.size:
            results[e.kind] = "skipped"
            continue
        g_before = _g_value(e.kind, seg.y[:, i1 - 1], env)
        g_after = _g_value(e.kind, seg.y[:, i1], env)
        exp_before, exp_after = expected[e.kind]
        ok = (
            (exp_before < 0 and g_before < 0 or exp_before > 0
             and g_before > 0)
            and (exp_after < 0 and g_after < 0 or exp_after > 0
                 and g_after > 0)
        )
        results[e.kind] = bool(ok)
    return results


# ---------------------------------------------------------------------------
# Topological margins and transversality
# ---------------------------------------------------------------------------
def topological_margins(traj, metrics, env, vehicle, control) -> dict:
    """SRTI / second-apogee margins and crossing transversality."""
    srti = next((e for e in traj.events if e.kind == SRTI), None)
    margins = {}
    if srti is not None:
        margins["srti_altitude_margin_m"] = float(
            env.atmosphere_boundary
            - (srti.state[0] - env.earth_radius))
    apogees = [e for e in traj.events if e.kind == "vacuum_apogee"]
    if len(apogees) >= 2:
        margins["second_apogee_clearance_m"] = float(
            apogees[1].state[0] - env.earth_radius
            - env.atmosphere_boundary)
    for e in traj.events:
        if e.kind == ATMOSPHERE_EXIT:
            margins["exit_gamma_rad"] = float(e.state[3])
            margins["exit_dhdt_mps"] = float(
                e.state[2] * np.sin(e.state[3]))
        if e.kind == ATMOSPHERE_ENTRY:
            margins["entry_gamma_rad"] = float(e.state[3])
            margins["entry_dhdt_mps"] = float(
                e.state[2] * np.sin(e.state[3]))
    if srti is not None:
        margins["srti_gamma_dot_radps"] = float(
            sanger_atm_rhs(srti.time, srti.state, env, vehicle,
                           control)[3])
    return margins


def vac_invariant_drifts(metrics) -> dict:
    """Max relative VAC energy / angular-momentum drift over the
    completed cycles (diagnostic; thresholds formalized in D6)."""
    if not metrics.completed_cycles:
        return {"max_energy_relative_drift": 0.0,
                "max_momentum_relative_drift": 0.0}
    return {
        "max_energy_relative_drift": max(
            c.vacuum_energy_relative_drift
            for c in metrics.completed_cycles),
        "max_momentum_relative_drift": max(
            c.vacuum_angular_momentum_relative_drift
            for c in metrics.completed_cycles),
    }


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write("\n")


def f16(value: float) -> float:
    return float(f"{value:.16e}")
