"""Phase B baseline experiment: Qian continuous-glide reference trajectory.

Integrates the full atmospheric 4-D dynamics from
h0=100 km, v0=7000 m/s, gamma0=-5 deg, theta0=0 with K=3.0 (ConstantKControl)
until the terminal ground event, then writes the standardized artifacts:

    results/baseline/qian_k3_gamma5/
        trajectory.csv
        metrics.json
        metadata.json

Run from the project root:

    python experiments/01_baseline_dynamics/run_qian_baseline.py
"""

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

import baseline_config as cfg
from hyptraj.simulation import integrate_trajectory, run_sanity_checks


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
    columns = {
        "time_s": result.time,
        "r_m": result.state[0],
        "altitude_m": result.derived["altitude_m"],
        "theta_rad": result.state[1],
        "range_m": result.derived["range_m"],
        "velocity_mps": result.state[2],
        "gamma_rad": result.state[3],
        "gamma_deg": np.rad2deg(result.state[3]),
        "density_kgm3": result.derived["density_kgm3"],
        "dynamic_pressure_pa": result.derived["dynamic_pressure_pa"],
        "drag_n": result.derived["drag_n"],
        "lift_n": result.derived["lift_n"],
    }

    header = ",".join(columns)
    data = np.column_stack([columns[key] for key in columns])

    np.savetxt(path, data, delimiter=",", header=header, comments="", fmt="%.10e")


def _write_metrics(result, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.metrics, f, indent=2)
        f.write("\n")


def _write_metadata(result, path: Path) -> None:
    metadata = dict(result.metadata)

    metadata["reproducibility"] = {
        "git_commit": _git_commit(),
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "scipy_version": __import__("scipy").__version__,
        "matplotlib_version": __import__("matplotlib").__version__,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")


def _check_reference_range(name: str, value: float, lo: float, hi: float) -> bool:
    ok = lo <= value <= hi
    print(
        f"  [{name:>4s}] {value:12.3f}   reference {lo:8.0f} - {hi:8.0f}  "
        f"{'PASS' if ok else 'FAIL'}"
    )
    return ok


def main() -> None:
    env, vehicle, initial, control = cfg.get_baseline_setup()

    result = integrate_trajectory(env, vehicle, initial, control)

    metrics = result.metrics
    metadata = result.metadata

    print("===== Literal Eq.(4) Uncontrolled Baseline =====")
    print(f"Flight time               : {metrics['flight_time_s']:.3f} s")
    print(f"Range                     : {metrics['range_km']:.3f} km")
    print(f"Terminal velocity         : {metrics['terminal_velocity_mps']:.3f} m/s")
    print(f"Max altitude              : {metrics['max_altitude_km']:.3f} km")
    print(f"Max dynamic pressure      : {metrics['max_dynamic_pressure_pa']:.3f} Pa")
    print(f"Dynamic pressure integral : {metrics['dynamic_pressure_integral_pas']:.6e} Pa.s")
    print(f"Ground-event altitude residual : {metrics['ground_event_altitude_residual_m']:.6e} m")
    print(f"nfev                      : {metadata['integration']['nfev']}")

    print("\nBenchmark sanity ranges (problem-statement reference, not regression):")
    ok_time = _check_reference_range(
        "t_f", metrics["flight_time_s"], *cfg.REFERENCE_FLIGHT_TIME_S
    )
    ok_range = _check_reference_range(
        "R_f", metrics["range_km"], *cfg.REFERENCE_RANGE_KM
    )
    ok_vel = _check_reference_range(
        "v_f", metrics["terminal_velocity_mps"], *cfg.REFERENCE_TERMINAL_VELOCITY_MPS
    )

    print("\nSanity checks:")
    sanity = run_sanity_checks(result)
    for name, passed in sanity.items():
        print(f"  [{name:>32s}] {'PASS' if passed else 'FAIL'}")
    if not all(sanity.values()):
        raise RuntimeError("Sanity checks failed.")

    if not (ok_time and ok_range and ok_vel):
        print(
            "\nWARNING: benchmark results outside the problem-statement reference "
            "ranges.\nThe RHS has been verified against the problem equations "
            "(units, r = Re + h, R = Re*theta, CL = K*CD, force signs, v/r term,\n"
            "gravity model, dynamic-pressure/force formulas, ground event) and "
            "the integration is converged;\nper project policy the physics is NOT "
            "tuned to fit the reference ranges."
        )

    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _write_trajectory_csv(result, cfg.OUTPUT_DIR / "trajectory.csv")
    _write_metrics(result, cfg.OUTPUT_DIR / "metrics.json")
    _write_metadata(result, cfg.OUTPUT_DIR / "metadata.json")

    print(f"\nArtifacts written to {cfg.OUTPUT_DIR}")


if __name__ == "__main__":
    main()
