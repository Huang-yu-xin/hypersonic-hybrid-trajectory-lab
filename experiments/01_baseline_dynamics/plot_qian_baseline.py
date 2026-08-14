"""Phase B baseline figures (5 plots, 300 dpi, matplotlib only).

Reads the standardized ``trajectory.csv`` produced by
``run_qian_baseline.py``; if it is missing, the baseline is re-integrated
on the fly so the figures can always be regenerated with one command:

    python experiments/01_baseline_dynamics/plot_qian_baseline.py
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import baseline_config as cfg
from hyptraj.simulation import integrate_trajectory

DEFAULT_FIGURES = {
    "fig01_altitude_range.png": "Altitude vs Range",
    "fig02_altitude_time.png": "Altitude vs Time",
    "fig03_velocity_time.png": "Velocity vs Time",
    "fig04_flight_path_angle_time.png": "Flight-Path Angle vs Time",
    "fig05_dynamic_pressure_time.png": "Dynamic Pressure vs Time",
}


def _load_data():
    """Load trajectory.csv, or re-integrate the baseline if it is missing."""
    csv_path = cfg.OUTPUT_DIR / "trajectory.csv"
    if csv_path.exists():
        data = np.genfromtxt(csv_path, delimiter=",", names=True)
        return data["time_s"], data, None

    env, vehicle, initial, control = cfg.get_baseline_setup()
    result = integrate_trajectory(env, vehicle, initial, control)
    return result.time, None, result


def _figure(title, xlabel, ylabel, x, y):
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot(x, y, linewidth=1.2)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle=":", linewidth=0.5)
    fig.tight_layout()
    return fig


def plot_all() -> None:
    cfg.FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    t, data, result = _load_data()
    if result is not None:
        h_km = result.derived["altitude_m"] / 1000.0
        r_km = result.derived["range_m"] / 1000.0
        v = result.state[2]
        gamma_deg = np.rad2deg(result.state[3])
        q_kpa = result.derived["dynamic_pressure_pa"] / 1000.0
    else:
        h_km = data["altitude_m"] / 1000.0
        r_km = data["range_m"] / 1000.0
        v = data["velocity_mps"]
        gamma_deg = data["gamma_deg"]
        q_kpa = data["dynamic_pressure_pa"] / 1000.0

    figures = [
        _figure("Qian Baseline: Altitude vs Range",
                "Ground range [km]", "Altitude [km]", r_km, h_km),
        _figure("Qian Baseline: Altitude vs Time",
                "Time [s]", "Altitude [km]", t, h_km),
        _figure("Qian Baseline: Velocity vs Time",
                "Time [s]", "Velocity [m/s]", t, v),
        _figure("Qian Baseline: Flight-Path Angle vs Time",
                "Time [s]", "Flight-path angle [deg]", t, gamma_deg),
        _figure("Qian Baseline: Dynamic Pressure vs Time",
                "Time [s]", "Dynamic pressure [kPa]", t, q_kpa),
    ]

    for fig, (name, _title) in zip(figures, DEFAULT_FIGURES.items()):
        path = cfg.FIGURE_DIR / name
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"saved {path}")

    print(f"{len(figures)} figures written to {cfg.FIGURE_DIR}")


if __name__ == "__main__":
    plot_all()
