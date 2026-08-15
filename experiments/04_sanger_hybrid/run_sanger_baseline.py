"""D5 canonical Sanger hybrid baseline runner.

Builds the canonical Sanger baseline from the frozen IC + frozen physics
+ Phase C production numerics, derives the D4 metrics, runs the SRTI ->
ground compatibility continuation and writes the standard artifacts:

    results/sanger_hybrid/baseline/
        trajectory.csv
        events.csv
        segments.csv
        skip_cycles.csv
        summary.json
        ground_continuation.csv
        ground_summary.json

Run from the project root:

    python experiments/04_sanger_hybrid/run_sanger_baseline.py

The baseline is a CANONICAL BASELINE CANDIDATE: it becomes
sanger-baseline-v1.0 only after the D6 numerical validation passes.
"""

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_compatibility import (
    integrate_sanger_ground_continuation,
)
from hyptraj.simulation.sanger_metrics import (
    altitude_from_state,
    analyze_sanger_trajectory,
    range_from_state,
    velocity_from_state,
)
from hyptraj.simulation.sanger_trajectory import integrate_sanger_hybrid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "results" / "sanger_hybrid" / "baseline"
FIGURE_DIR = OUTPUT_DIR / "figures"

BASELINE_NAME = "sanger-hybrid-baseline-v1-candidate"
SCHEMA_VERSION = "1.0"


def get_baseline_setup():
    """Frozen D0 baseline setup (identical to the comparative design)."""
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


def _git_info() -> dict[str, str]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True,
            text=True, check=True).stdout.strip()
    except Exception:
        commit, branch = "unknown", "unknown"
    return {"git_commit": commit, "branch": branch}


def _f16(value: float) -> float:
    """Round-trip a float through 16 significant digits (full precision)."""
    return float(f"{value:.16e}")


def _write_csv(path: Path, columns: dict) -> None:
    header = ",".join(columns)
    n = next(iter(columns.values())).size
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for i in range(n):
            fields = []
            for key in columns:
                v = columns[key][i]
                if isinstance(v, str):
                    fields.append(v)
                elif isinstance(v, (bool, np.bool_)):
                    fields.append("True" if v else "False")
                else:
                    fields.append(f"{float(v):.16e}")
            f.write(",".join(fields) + "\n")


def _write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write("\n")


def _combined_with_mode(traj):
    """Chronological grid with mode / segment labels.

    Uses the same deterministic de-dup policy as
    ``SangerHybridTrajectory.get_combined_history``: the first sample of
    every segment except segment 0 is dropped, so no transition state is
    duplicated.
    """
    t_parts, y_parts, mode_parts, seg_parts = [], [], [], []
    for i, s in enumerate(traj.segments):
        t, y = s.t, s.y
        if i > 0:
            t, y = t[1:], y[:, 1:]
        t_parts.append(t)
        y_parts.append(y)
        mode_parts.append(np.full(t.size, s.mode, dtype=object))
        seg_parts.append(np.full(t.size, s.index, dtype=int))
    return (
        np.concatenate(t_parts),
        np.concatenate(y_parts, axis=1),
        np.concatenate(mode_parts),
        np.concatenate(seg_parts),
    )


def main() -> None:
    env, vehicle, initial, control = get_baseline_setup()

    traj = integrate_sanger_hybrid(env, vehicle, initial, control)
    metrics = analyze_sanger_trajectory(traj, env)

    if not traj.success or traj.terminal_kind != "srti":
        raise RuntimeError(
            "Canonical baseline must reach the SRTI; got "
            f"terminal_kind={traj.terminal_kind!r} (success={traj.success})."
        )

    # ---- compatibility ground continuation (does not touch research) ----
    ground = integrate_sanger_ground_continuation(
        traj.terminal_state, traj.terminal_time, env, vehicle, control)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    # ---- trajectory.csv --------------------------------------------------
    t, y, mode, seg_idx = _combined_with_mode(traj)
    traj_cols = {
        "time_s": t,
        "radius_m": y[0],
        "altitude_m": y[0] - env.earth_radius,
        "theta_rad": y[1],
        "range_m": env.earth_radius * y[1],
        "velocity_mps": y[2],
        "gamma_rad": y[3],
        "gamma_deg": np.degrees(y[3]),
        "mode": mode,
        "segment_index": seg_idx,
    }
    _write_csv(OUTPUT_DIR / "trajectory.csv", traj_cols)

    # ---- events.csv ------------------------------------------------------
    ev_cols = {
        "event_index": np.array([e.index for e in traj.events]),
        "event_kind": np.array([e.kind for e in traj.events], dtype=object),
        "time_s": np.array([e.time for e in traj.events]),
        "altitude_m": np.array(
            [altitude_from_state(e.state, env) for e in traj.events]),
        "range_m": np.array(
            [range_from_state(e.state, env) for e in traj.events]),
        "velocity_mps": np.array(
            [velocity_from_state(e.state) for e in traj.events]),
        "gamma_rad": np.array([e.state[3] for e in traj.events]),
        "gamma_deg": np.array(
            [np.degrees(e.state[3]) for e in traj.events]),
        "mode_before": np.array(
            [e.mode_before if e.mode_before else "" for e in traj.events],
            dtype=object),
        "mode_after": np.array(
            [e.mode_after if e.mode_after else "" for e in traj.events],
            dtype=object),
        "is_synthetic": np.array([e.is_synthetic for e in traj.events]),
    }
    _write_csv(OUTPUT_DIR / "events.csv", ev_cols)

    # ---- segments.csv ----------------------------------------------------
    seg_cols = {
        "segment_index": np.array([s.index for s in traj.segments]),
        "mode": np.array([s.mode for s in traj.segments], dtype=object),
        "t_start_s": np.array([s.t_start for s in traj.segments]),
        "t_end_s": np.array([s.t_end for s in traj.segments]),
        "duration_s": np.array(
            [s.t_end - s.t_start for s in traj.segments]),
        "start_altitude_m": np.array(
            [s.state_start[0] - env.earth_radius for s in traj.segments]),
        "end_altitude_m": np.array(
            [s.state_end[0] - env.earth_radius for s in traj.segments]),
        "start_velocity_mps": np.array(
            [s.state_start[2] for s in traj.segments]),
        "end_velocity_mps": np.array(
            [s.state_end[2] for s in traj.segments]),
        "nfev": np.array([s.nfev for s in traj.segments]),
        "njev": np.array([s.njev for s in traj.segments]),
        "nlu": np.array([s.nlu for s in traj.segments]),
        "success": np.array([s.success for s in traj.segments]),
        "trigger_event": np.array(
            [s.trigger_event for s in traj.segments], dtype=object),
    }
    _write_csv(OUTPUT_DIR / "segments.csv", seg_cols)

    # ---- skip_cycles.csv -------------------------------------------------
    cyc = metrics.completed_cycles
    cyc_cols = {
        "cycle_index": np.array([c.index for c in cyc]),
        "entry_is_synthetic": np.array(
            [c.entry_is_synthetic for c in cyc]),
        "entry_time_s": np.array([c.entry_time for c in cyc]),
        "pullout_time_s": np.array([c.pullout_time for c in cyc]),
        "exit_time_s": np.array([c.exit_time for c in cyc]),
        "apogee_time_s": np.array([c.apogee_time for c in cyc]),
        "next_entry_time_s": np.array([c.next_entry_time for c in cyc]),
        "pullout_altitude_m": np.array(
            [c.pullout_altitude_m for c in cyc]),
        "apogee_altitude_m": np.array([c.apogee_altitude_m for c in cyc]),
        "entry_velocity_mps": np.array([c.entry_velocity_mps for c in cyc]),
        "exit_velocity_mps": np.array([c.exit_velocity_mps for c in cyc]),
        "next_entry_velocity_mps": np.array(
            [c.next_entry_velocity_mps for c in cyc]),
        "atmospheric_duration_s": np.array(
            [c.atmospheric_duration_s for c in cyc]),
        "vacuum_duration_s": np.array([c.vacuum_duration_s for c in cyc]),
        "cycle_duration_s": np.array([c.cycle_duration_s for c in cyc]),
        "atmospheric_range_m": np.array(
            [c.atmospheric_range_m for c in cyc]),
        "vacuum_range_m": np.array([c.vacuum_range_m for c in cyc]),
        "cycle_range_m": np.array([c.cycle_range_m for c in cyc]),
        "atmospheric_speed_loss_mps": np.array(
            [c.atmospheric_speed_loss_mps for c in cyc]),
        "atmospheric_energy_loss_jpkg": np.array(
            [c.atmospheric_energy_loss_jpkg for c in cyc]),
        "vacuum_energy_drift_jpkg": np.array(
            [c.vacuum_energy_drift_jpkg for c in cyc]),
        "vacuum_energy_relative_drift": np.array(
            [c.vacuum_energy_relative_drift for c in cyc]),
        "vacuum_angular_momentum_drift": np.array(
            [c.vacuum_angular_momentum_drift for c in cyc]),
        "vacuum_angular_momentum_relative_drift": np.array(
            [c.vacuum_angular_momentum_relative_drift for c in cyc]),
    }
    _write_csv(OUTPUT_DIR / "skip_cycles.csv", cyc_cols)

    # ---- summary.json ----------------------------------------------------
    events_meta = []
    for e in traj.events:
        rec = {
            "index": e.index,
            "kind": e.kind,
            "time_s": _f16(e.time),
            "state": [_f16(x) for x in e.state],
            "mode_before": e.mode_before,
            "mode_after": e.mode_after,
            "is_synthetic": e.is_synthetic,
        }
        if e.f_minus is not None:
            rec["f_minus"] = [_f16(x) for x in e.f_minus]
        if e.f_plus is not None:
            rec["f_plus"] = [_f16(x) for x in e.f_plus]
        if e.normal is not None:
            rec["normal"] = [_f16(x) for x in e.normal]
        events_meta.append(rec)

    p = metrics.terminal_incomplete_pass
    summary = {
        "schema_version": SCHEMA_VERSION,
        "baseline_name": BASELINE_NAME,
        **_git_info(),
        "physical_configuration": {
            "initial_conditions": {
                "h0_m": initial.altitude,
                "v0_mps": initial.velocity,
                "gamma0_deg": initial.flight_path_angle_deg,
                "theta0_rad": initial.range_angle,
            },
            "environment": {
                "earth_radius_m": env.earth_radius,
                "gravity_sea_level_mps2": env.gravity_sea_level,
                "density_sea_level_kgm3": env.density_sea_level,
                "scale_height_m": env.scale_height,
                "atmosphere_boundary_m": env.atmosphere_boundary,
            },
            "vehicle": {
                "mass_kg": vehicle.mass,
                "reference_area_m2": vehicle.reference_area,
                "drag_coefficient": vehicle.drag_coefficient,
            },
            "K_aero": control.value,
            "ATM_control": "u_L = 1 (sigma = 0)",
            "VAC_semantics": "L = 0, D = 0; gravity and curvature retained",
        },
        "numerical_configuration": {
            "method": PRODUCTION_SOLVER_CONFIG.method,
            "rtol": PRODUCTION_SOLVER_CONFIG.rtol,
            "atol": [float(a) for a in PRODUCTION_SOLVER_CONFIG.atol],
            "max_step": PRODUCTION_SOLVER_CONFIG.max_step,
            "dense_output": PRODUCTION_SOLVER_CONFIG.dense_output,
        },
        "research_endpoint": "SRTI (Sanger Skip-Capability-Loss Interface)",
        "hybrid_structure": {
            "mode_sequence": [s.mode for s in traj.segments],
            "event_sequence": [e.kind for e in traj.events],
            "atm_segment_count": metrics.atm_segment_count,
            "vac_segment_count": metrics.vac_segment_count,
            "completed_skip_count": metrics.skip_count,
        },
        "global_metrics": {
            "research_flight_time_s": _f16(metrics.research_flight_time_s),
            "research_range_m": _f16(metrics.research_range_m),
            "maximum_altitude_m": _f16(metrics.maximum_altitude_m),
            "maximum_altitude_time_s": _f16(
                metrics.maximum_altitude_time_s),
        },
        "SRTI": {
            "time_s": _f16(metrics.terminal_time_s),
            "altitude_m": _f16(metrics.terminal_altitude_m),
            "range_m": _f16(
                range_from_state(traj.terminal_state, env)),
            "velocity_mps": _f16(metrics.terminal_velocity_mps),
            "gamma_rad": _f16(traj.terminal_state[3]),
            "gamma_deg": _f16(float(np.degrees(traj.terminal_state[3]))),
        },
        "completed_cycles": [
            {
                "cycle_index": c.index,
                "entry_is_synthetic": c.entry_is_synthetic,
                "entry_time_s": _f16(c.entry_time),
                "pullout_time_s": _f16(c.pullout_time),
                "exit_time_s": _f16(c.exit_time),
                "apogee_time_s": _f16(c.apogee_time),
                "next_entry_time_s": _f16(c.next_entry_time),
                "entry_altitude_m": _f16(c.entry_altitude_m),
                "pullout_altitude_m": _f16(c.pullout_altitude_m),
                "exit_altitude_m": _f16(c.exit_altitude_m),
                "apogee_altitude_m": _f16(c.apogee_altitude_m),
                "next_entry_altitude_m": _f16(c.next_entry_altitude_m),
                "entry_velocity_mps": _f16(c.entry_velocity_mps),
                "pullout_velocity_mps": _f16(c.pullout_velocity_mps),
                "exit_velocity_mps": _f16(c.exit_velocity_mps),
                "apogee_velocity_mps": _f16(c.apogee_velocity_mps),
                "next_entry_velocity_mps": _f16(c.next_entry_velocity_mps),
                "atmospheric_duration_s": _f16(c.atmospheric_duration_s),
                "vacuum_duration_s": _f16(c.vacuum_duration_s),
                "cycle_duration_s": _f16(c.cycle_duration_s),
                "atmospheric_range_m": _f16(c.atmospheric_range_m),
                "vacuum_range_m": _f16(c.vacuum_range_m),
                "cycle_range_m": _f16(c.cycle_range_m),
                "atmospheric_speed_loss_mps": _f16(
                    c.atmospheric_speed_loss_mps),
                "atmospheric_energy_loss_jpkg": _f16(
                    c.atmospheric_energy_loss_jpkg),
                "vacuum_energy_drift_jpkg": _f16(
                    c.vacuum_energy_drift_jpkg),
                "vacuum_energy_relative_drift": _f16(
                    c.vacuum_energy_relative_drift),
                "vacuum_angular_momentum_drift": _f16(
                    c.vacuum_angular_momentum_drift),
                "vacuum_angular_momentum_relative_drift": _f16(
                    c.vacuum_angular_momentum_relative_drift),
            }
            for c in cyc
        ],
        "terminal_incomplete_pass": (
            None
            if p is None
            else {
                "entry_time_s": _f16(p.entry_time),
                "pullout_time_s": (
                    None if p.pullout_time is None
                    else _f16(p.pullout_time)),
                "srti_time_s": _f16(p.srti_time),
                "entry_velocity_mps": _f16(p.entry_velocity_mps),
                "pullout_velocity_mps": (
                    None if p.pullout_velocity_mps is None
                    else _f16(p.pullout_velocity_mps)),
                "srti_velocity_mps": _f16(p.srti_velocity_mps),
                "pullout_altitude_m": (
                    None if p.pullout_altitude_m is None
                    else _f16(p.pullout_altitude_m)),
                "srti_altitude_m": _f16(p.srti_altitude_m),
                "atmospheric_duration_s": _f16(p.atmospheric_duration_s),
                "range_increment_m": _f16(p.range_increment_m),
                "mechanical_energy_loss_jpkg": _f16(
                    p.mechanical_energy_loss_jpkg),
                "completed_exit": p.completed_exit,
            }
        ),
        "solver_totals": {
            "nfev": sum(s.nfev for s in traj.segments),
            "njev": sum(s.njev for s in traj.segments),
            "nlu": sum(s.nlu for s in traj.segments),
        },
        "events": events_meta,
        "acceptance": {
            "terminal_kind_is_srti": traj.terminal_kind == "srti",
            "research_success": bool(traj.success),
            "skip_count_matches_cycles": (
                metrics.skip_count == len(metrics.completed_cycles)),
            "mode_sequence_alternates": all(
                a.mode != b.mode
                for a, b in zip(traj.segments, traj.segments[1:])),
            "event_times_strictly_increasing": all(
                b > a for a, b in zip(
                    [e.time for e in traj.events if not e.is_synthetic],
                    [e.time for e in traj.events if not e.is_synthetic][1:],
                )
            ),
            "state_continuity_exact": all(
                np.array_equal(traj.segments[i].state_start,
                               traj.segments[i - 1].state_end)
                for i in range(1, len(traj.segments))
            ),
            "ground_continuation_compatibility_only": True,
        },
        "reproducibility": {
            "python_version": sys.version.split()[0],
            "numpy_version": np.__version__,
            "scipy_version": __import__("scipy").__version__,
            "matplotlib_version": __import__("matplotlib").__version__,
            "timestamp_utc": _dt.datetime.now(
                _dt.timezone.utc).isoformat(),
        },
    }
    _write_json(OUTPUT_DIR / "summary.json", summary)

    # ---- ground continuation ---------------------------------------------
    gc_cols = {
        "time_s": ground.time,
        "radius_m": ground.state[0],
        "altitude_m": ground.state[0] - env.earth_radius,
        "range_m": env.earth_radius * ground.state[1],
        "velocity_mps": ground.state[2],
        "gamma_rad": ground.state[3],
        "gamma_deg": np.degrees(ground.state[3]),
    }
    _write_csv(OUTPUT_DIR / "ground_continuation.csv", gc_cols)

    gs = {
        "schema_version": SCHEMA_VERSION,
        "start": "SRTI",
        "compatibility_only": True,
        "start_time_s": _f16(traj.terminal_time),
        "start_state": [_f16(x) for x in traj.terminal_state],
        "ground_time_s": _f16(ground.ground_time_s),
        "ground_range_m": _f16(
            range_from_state(ground.ground_state, env)),
        "ground_velocity_mps": _f16(
            velocity_from_state(ground.ground_state)),
        "ground_gamma_rad": _f16(ground.ground_state[3]),
        "ground_gamma_deg": _f16(
            float(np.degrees(ground.ground_state[3]))),
        "duration_from_srti_s": _f16(
            ground.ground_time_s - traj.terminal_time),
        "range_after_srti_m": _f16(
            range_from_state(ground.ground_state, env)
            - range_from_state(traj.terminal_state, env)),
        "solver": {
            "nfev": ground.nfev,
            "njev": ground.njev,
            "nlu": ground.nlu,
        },
        "note": (
            "Compatibility / visualization continuation ONLY. All Phase D "
            "high-speed research metrics stop at the SRTI."
        ),
    }
    _write_json(OUTPUT_DIR / "ground_summary.json", gs)

    # ---- console summary ---------------------------------------------------
    print(f"===== Sanger Hybrid Baseline — {BASELINE_NAME} =====")
    print(f"Terminal kind      : {traj.terminal_kind} (success={traj.success})")
    print(f"Skip count         : {metrics.skip_count}")
    print(f"Mode sequence      : {' -> '.join(s.mode for s in traj.segments)}")
    print(
        f"Research endpoint  : SRTI  t={metrics.terminal_time_s:.4f} s, "
        f"h={metrics.terminal_altitude_m:.3f} m, "
        f"v={metrics.terminal_velocity_mps:.4f} m/s"
    )
    print(
        f"Ground compatibility: t={ground.ground_time_s:.4f} s, "
        f"R={range_from_state(ground.ground_state, env) / 1000.0:.3f} km, "
        f"v={velocity_from_state(ground.ground_state):.4f} m/s"
    )
    print(f"Artifacts written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
