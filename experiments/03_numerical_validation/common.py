"""Shared Phase C numerical-validation harness.

This module deliberately imports the frozen Phase B physics, controls and event
functions.  It does not redefine the aerodynamic / atmospheric / QEG model.
Its only purpose is to expose raw solve_ivp diagnostics (nfev/njev/nlu), wall
clock cost, event states and event residuals for solver validation.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.dynamics import atmospheric_dynamics
from hyptraj.models.parameters import EnvironmentParams, InitialCondition, VehicleParams
from hyptraj.modes.continuous_glide import QEG_GLIDE, continuous_glide_rhs, qeg_lift_fraction
from hyptraj.simulation.events import make_capture_event, make_ground_event, make_qeg_end_event
from hyptraj.simulation.trajectory import SolverConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = PROJECT_ROOT / "results" / "numerical_validation"

BASE_ATOL = np.array([1e-3, 1e-10, 1e-6, 1e-10], dtype=float)

REFERENCE_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-12,
    atol=BASE_ATOL * 1e-4,
    max_step=0.1,
    dense_output=True,
)

PRODUCTION_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-9,
    atol=BASE_ATOL * 1e-1,
    max_step=20.0,
    dense_output=True,
)


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


def _stage_stats(sol) -> dict[str, Any]:
    return {
        "success": bool(sol.success),
        "message": str(sol.message),
        "nfev": int(sol.nfev),
        "njev": int(getattr(sol, "njev", 0) or 0),
        "nlu": int(getattr(sol, "nlu", 0) or 0),
    }


def run_case(config: SolverConfig) -> dict[str, Any]:
    """Run the frozen three-mode Qian baseline with one numerical config."""
    env, vehicle, initial, control = get_baseline_setup()
    state0 = np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ],
        dtype=float,
    )

    kwargs = dict(
        method=config.method,
        rtol=config.rtol,
        atol=np.asarray(config.atol, dtype=float),
        max_step=config.max_step,
        dense_output=config.dense_output,
    )

    wall0 = perf_counter()

    capture_event = make_capture_event()
    sol_cap = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        config.t_span,
        state0,
        events=[capture_event],
        **kwargs,
    )
    if (not sol_cap.success) or sol_cap.t_events[0].size != 1:
        raise RuntimeError(f"Capture integration failed: {sol_cap.message}")
    t_capture = float(sol_cap.t_events[0][0])
    x_capture = np.asarray(sol_cap.y_events[0][0], dtype=float)

    rti_event = make_qeg_end_event(env, vehicle, control)
    sol_qeg = solve_ivp(
        lambda t, y: continuous_glide_rhs(QEG_GLIDE, t, y, env, vehicle, control),
        (t_capture, config.t_span[1]),
        x_capture,
        events=[rti_event],
        **kwargs,
    )
    if (not sol_qeg.success) or sol_qeg.t_events[0].size != 1:
        raise RuntimeError(f"RTI integration failed: {sol_qeg.message}")
    t_rti = float(sol_qeg.t_events[0][0])
    x_rti = np.asarray(sol_qeg.y_events[0][0], dtype=float)

    ground_event = make_ground_event(env)
    sol_ground = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (t_rti, config.t_span[1]),
        x_rti,
        events=[ground_event],
        **kwargs,
    )
    if (not sol_ground.success) or sol_ground.t_events[0].size != 1:
        raise RuntimeError(f"Ground integration failed: {sol_ground.message}")
    t_ground = float(sol_ground.t_events[0][0])
    x_ground = np.asarray(sol_ground.y_events[0][0], dtype=float)

    wall_s = perf_counter() - wall0
    stages = {
        "entry_capture": _stage_stats(sol_cap),
        "qeg_glide": _stage_stats(sol_qeg),
        "ground_continuation": _stage_stats(sol_ground),
    }

    all_states = np.concatenate([x_capture, x_rti, x_ground])
    result = {
        "method": config.method,
        "rtol": float(config.rtol),
        "atol": [float(v) for v in np.asarray(config.atol)],
        "max_step_s": float(config.max_step),
        "dense_output": bool(config.dense_output),
        "capture_time_s": t_capture,
        "capture_altitude_m": float(x_capture[0] - env.earth_radius),
        "capture_velocity_mps": float(x_capture[2]),
        "rti_time_s": t_rti,
        "rti_altitude_m": float(x_rti[0] - env.earth_radius),
        "rti_velocity_mps": float(x_rti[2]),
        "rti_range_m": float(env.earth_radius * x_rti[1]),
        "ground_time_s": t_ground,
        "ground_range_m": float(env.earth_radius * x_ground[1]),
        "ground_velocity_mps": float(x_ground[2]),
        "ground_gamma_deg": float(np.degrees(x_ground[3])),
        "nfev": sum(s["nfev"] for s in stages.values()),
        "njev": sum(s["njev"] for s in stages.values()),
        "nlu": sum(s["nlu"] for s in stages.values()),
        "wall_s": float(wall_s),
        "event_order_ok": bool(0.0 < t_capture < t_rti < t_ground),
        "mode_durations_positive": bool(
            t_capture > 0.0 and (t_rti - t_capture) > 0.0 and (t_ground - t_rti) > 0.0
        ),
        "state_finite": bool(np.all(np.isfinite(all_states))),
        "capture_gamma_residual_rad": float(x_capture[3]),
        "rti_event_residual": float(rti_event(t_rti, x_rti)),
        "ground_event_residual_m": float(ground_event(t_ground, x_ground)),
        "qeg_u_at_capture": float(qeg_lift_fraction(t_capture, x_capture, env, vehicle, control)),
        "stages": stages,
    }
    result["hybrid_consistency_ok"] = bool(
        result["event_order_ok"]
        and result["mode_durations_positive"]
        and result["state_finite"]
        and abs(result["capture_gamma_residual_rad"]) < 1e-8
        and abs(result["rti_event_residual"]) < 1e-7
        and abs(result["ground_event_residual_m"]) < 1e-6
        and 0.0 <= result["qeg_u_at_capture"] <= 1.0
    )
    return result


ERROR_FIELDS = {
    "capture_time_s": "abs_error_capture_time_s",
    "capture_altitude_m": "abs_error_capture_altitude_m",
    "capture_velocity_mps": "abs_error_capture_velocity_mps",
    "rti_time_s": "abs_error_rti_time_s",
    "rti_altitude_m": "abs_error_rti_altitude_m",
    "rti_velocity_mps": "abs_error_rti_velocity_mps",
    "rti_range_m": "abs_error_rti_range_m",
    "ground_time_s": "abs_error_ground_time_s",
    "ground_range_m": "abs_error_ground_range_m",
    "ground_velocity_mps": "abs_error_ground_velocity_mps",
}


def add_reference_errors(case: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    out = dict(case)
    for field, error_name in ERROR_FIELDS.items():
        out[error_name] = abs(float(case[field]) - float(reference[field]))
    return out


def load_reference() -> dict[str, Any]:
    import json
    path = RESULTS_ROOT / "reference" / "reference.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Run run_reference_solution.py first."
        )
    return json.loads(path.read_text(encoding="utf-8"))["reference"]


def write_json(path: Path, obj: Any) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if not isinstance(v, (dict, list, tuple))}
