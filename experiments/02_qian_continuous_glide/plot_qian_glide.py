"""Phase B.5 approved Qian baseline figures (9 plots, 300 dpi).

Recomputes the approved baseline on the fly (self-contained, single
command) and writes:

    results/baseline/qian_continuous_glide/figures/
        fig01_altitude_range.png        h - R
        fig02_altitude_time.png         h - t
        fig03_velocity_time.png         v - t
        fig04_flight_path_angle_time.png  gamma - t
        fig05_dynamic_pressure_time.png q - t
        fig06_uL_time.png               u_L - t
        fig07_bank_angle_time.png       sigma - t
        fig08_literal_vs_qian_h_R.png   literal Eq.(4) vs approved Qian
        fig09_literal_vs_qian_v_t.png   literal Eq.(4) vs approved Qian

Phase markers: QEG CAPTURE / RESEARCH TERMINAL INTERFACE / GROUND.
Ground continuation rows are distinguished by line style / shading.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run_qian_glide import get_baseline_setup, OUTPUT_DIR, FIGURE_DIR
from hyptraj.simulation import integrate_qian_glide, integrate_trajectory
from hyptraj.modes import ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION

MARKERS = {
    "QEG CAPTURE": dict(color="tab:green", ls="--", lw=1.1),
    "RESEARCH TERMINAL INTERFACE": dict(color="tab:red", ls="--", lw=1.1),
    "GROUND": dict(color="k", ls=":", lw=1.1),
}


def run():
    env, vehicle, initial, control = get_baseline_setup()
    result = integrate_qian_glide(env, vehicle, initial, control)
    literal = integrate_trajectory(env, vehicle, initial, control)
    return env, result, literal


def phase_lines(ax, result):
    m = result.metrics
    ax.axvline(m["qeg_capture_time_s"], **MARKERS["QEG CAPTURE"])
    ax.axvline(m["research_terminal_time_s"], **MARKERS["RESEARCH TERMINAL INTERFACE"])
    ax.axvline(m["ground_time_s"], **MARKERS["GROUND"])
    ax.text(m["qeg_capture_time_s"], ax.get_ylim()[1], "QEG CAPTURE",
            ha="right", va="top", fontsize=7, color="tab:green", rotation=90)
    ax.text(m["research_terminal_time_s"], ax.get_ylim()[1],
            "RESEARCH TERMINAL INTERFACE", ha="right", va="top", fontsize=7,
            color="tab:red", rotation=90)
    ax.text(m["ground_time_s"], ax.get_ylim()[0], "GROUND",
            ha="right", va="bottom", fontsize=7, color="k", rotation=90)


def split(result):
    """Split arrays by mode for distinct styling of the ground continuation."""
    idx = {
        mode: np.where(np.asarray(result.mode) == mode)[0]
        for mode in (ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION)
    }
    return idx


def plot_time_series(result, env):
    idx = split(result)
    t, st = result.time, result.state
    h_km = (st[0] - env.earth_radius) / 1000.0
    R_km = result.derived["range_m"] / 1000.0
    q_kpa = result.derived["dynamic_pressure_pa"] / 1000.0
    u = result.control_history["u_L"]
    sig = result.control_history["sigma_deg"]

    series = {
        "fig02_altitude_time.png": ("Altitude [km]", h_km),
        "fig03_velocity_time.png": ("Velocity [m/s]", st[2]),
        "fig04_flight_path_angle_time.png": ("Flight-path angle [deg]",
                                              np.degrees(st[3])),
        "fig05_dynamic_pressure_time.png": ("Dynamic pressure [kPa]", q_kpa),
        "fig06_uL_time.png": ("u_L = cos(sigma)", u),
        "fig07_bank_angle_time.png": ("Bank angle sigma [deg]", sig),
    }
    for name, (ylabel, y) in series.items():
        fig, ax = plt.subplots(figsize=(8.0, 4.6))
        for mode in (ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION):
            i = idx[mode]
            style = dict(lw=1.2, color="tab:green") if mode == QEG_GLIDE else (
                dict(lw=1.2, color="tab:orange") if mode == ENTRY_CAPTURE else
                dict(lw=1.2, color="tab:blue", ls="--"))
            ax.plot(t[i], y[i], label=mode, **style)
        ax.set_xlabel("Time [s]"); ax.set_ylabel(ylabel)
        ax.set_title(f"Approved Qian baseline: {ylabel}")
        phase_lines(ax, result)
        ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
        fig.tight_layout(); fig.savefig(FIGURE_DIR / name, dpi=300)
        plt.close(fig)
        print(f"saved {name}")


def main() -> None:
    env, result, literal = run()

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    idx = split(result)
    st, t = result.state, result.time
    h_km = (st[0] - env.earth_radius) / 1000.0
    R_km = result.derived["range_m"] / 1000.0

    # 1) h-R
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for mode in (ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION):
        i = idx[mode]
        style = dict(lw=1.3, color="tab:green") if mode == QEG_GLIDE else (
            dict(lw=1.3, color="tab:orange") if mode == ENTRY_CAPTURE else
            dict(lw=1.3, color="tab:blue", ls="--"))
        ax.plot(R_km[i], h_km[i], label=mode, **style)
    m = result.metrics
    ax.plot(m["research_terminal_range_km"], m["research_terminal_altitude_km"],
            "o", color="tab:red", ms=8)
    ax.annotate("RESEARCH TERMINAL INTERFACE",
                (m["research_terminal_range_km"], m["research_terminal_altitude_km"]),
                xytext=(10, 8), textcoords="offset points", fontsize=7,
                color="tab:red")
    ax.annotate("QEG CAPTURE", (R_km[idx[ENTRY_CAPTURE][-1]], h_km[idx[ENTRY_CAPTURE][-1]]),
                xytext=(8, 8), textcoords="offset points", fontsize=7,
                color="tab:green")
    ax.set_xlabel("Ground range [km]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("Approved Qian baseline: Altitude vs Range")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "fig01_altitude_range.png", dpi=300)
    plt.close(fig)
    print("saved fig01_altitude_range.png")

    # 2-7) time series
    plot_time_series(result, env)

    # 8-9) literal vs approved Qian comparison
    l_st, l_t = literal.state, literal.time
    l_h = (l_st[0] - env.earth_radius) / 1000.0
    l_R = literal.derived["range_m"] / 1000.0

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(l_R, l_h, lw=1.2, color="tab:red", label="Literal Eq.(4) uncontrolled")
    ax.plot(R_km, h_km, lw=1.2, color="tab:blue", label="Approved Qian (dual endpoint)")
    ax.set_xlabel("Ground range [km]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("Literal Eq.(4) vs approved Qian: h - R")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "fig08_literal_vs_qian_h_R.png", dpi=300)
    plt.close(fig)
    print("saved fig08_literal_vs_qian_h_R.png")

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(l_t, l_st[2], lw=1.2, color="tab:red", label="Literal Eq.(4) uncontrolled")
    ax.plot(t, st[2], lw=1.2, color="tab:blue", label="Approved Qian (dual endpoint)")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Velocity [m/s]")
    ax.set_title("Literal Eq.(4) vs approved Qian: v - t")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "fig09_literal_vs_qian_v_t.png", dpi=300)
    plt.close(fig)
    print("saved fig09_literal_vs_qian_v_t.png")

    print(f"\n9 figures written to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
