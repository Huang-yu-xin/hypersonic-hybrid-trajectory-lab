"""Phase B.5 approved Qian continuous-glide baseline (dual endpoint).

Runs the approved three-mode baseline (ENTRY_CAPTURE -> QEG_GLIDE ->
RTI -> GROUND_CONTINUATION) and writes the standardized artifacts:

    results/baseline/qian_continuous_glide/
        trajectory.csv
        metrics.json
        metadata.json

Run from the project root:

    python experiments/02_qian_continuous_glide/run_qian_glide.py
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
from hyptraj.simulation import integrate_qian_glide, run_sanity_checks

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "results" / "baseline" / "qian_continuous_glide"
FIGURE_DIR = OUTPUT_DIR / "figures"


def get_baseline_setup():
    """Approved baseline setup (identical ICs/vehicle to the literal run)."""
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


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _write_trajectory_csv(result, path: Path) -> None:
    c = result.control_history
    d = result.derived
    columns = {
        "time_s": result.time,
        "mode": result.mode,
        "r_m": result.state[0],
        "altitude_m": d["altitude_m"],
        "theta_rad": result.state[1],
        "range_m": d["range_m"],
        "velocity_mps": result.state[2],
        "gamma_rad": result.state[3],
        "gamma_deg": np.degrees(result.state[3]),
        "energy_jpkg": d["energy_jpkg"],
        "density_kgm3": d["density_kgm3"],
        "dynamic_pressure_pa": d["dynamic_pressure_pa"],
        "drag_n": d["drag_n"],
        "lift_n": d["lift_n"],
        "lift_required_n": d["lift_required_n"],
        "u_L": c["u_L"],
        "sigma_deg": c["sigma_deg"],
        "K_aero": c["K_aero"],
        "K_eff": c["K_eff"],
    }

    header = ",".join(columns)
    n = result.time.size
    mode_col = np.asarray(columns["mode"], dtype=object)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for i in range(n):
            fields = []
            for key in columns:
                if key == "mode":
                    fields.append(str(mode_col[i]))
                else:
                    fields.append(f"{columns[key][i]:.10e}")
            f.write(",".join(fields) + "\n")


def _write_json(data, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main() -> None:
    env, vehicle, initial, control = get_baseline_setup()

    result = integrate_qian_glide(env, vehicle, initial, control)

    metrics = result.metrics
    metadata = dict(result.metadata)

    metadata["reproducibility"] = {
        "git_commit": _git_commit(),
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "scipy_version": __import__("scipy").__version__,
        "matplotlib_version": __import__("matplotlib").__version__,
    }

    print("===== Approved Qian Continuous-Glide Baseline (dual endpoint) =====")
    print(f"QEG capture            : t={metrics['qeg_capture_time_s']:.3f} s")
    print(f"Research Terminal Intf : t={metrics['research_terminal_time_s']:.3f} s, "
          f"R={metrics['research_terminal_range_km']:.2f} km, "
          f"h={metrics['research_terminal_altitude_km']:.3f} km, "
          f"v={metrics['research_terminal_velocity_mps']:.3f} m/s")
    print(f"QEG duration / range   : {metrics['qeg_duration_s']:.3f} s / "
          f"{metrics['qeg_range_gain_km']:.2f} km")
    print(f"Ground continuation    : t={metrics['ground_time_s']:.3f} s, "
          f"R={metrics['ground_range_km']:.2f} km, "
          f"v={metrics['ground_velocity_mps']:.3f} m/s")
    print(f"Bank angle (QEG)       : max={metrics['max_bank_angle_deg']:.2f} deg, "
          f"median={metrics['median_bank_angle_deg']:.2f} deg")
    print(f"Ground residual        : {metrics['ground_event_altitude_residual_m']:.3e} m")

    print("\nSanity checks:")
    sanity = run_sanity_checks(result)
    for name, passed in sanity.items():
        print(f"  [{name:>32s}] {'PASS' if passed else 'FAIL'}")
    if not all(sanity.values()):
        raise RuntimeError("Sanity checks failed.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_trajectory_csv(result, OUTPUT_DIR / "trajectory.csv")
    _write_json(metrics, OUTPUT_DIR / "metrics.json")
    _write_json(metadata, OUTPUT_DIR / "metadata.json")

    print(f"\nArtifacts written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
