"""D5 Phase D baseline figures (D7B-pre corrected rendering).

Generates the five Phase D baseline figures from the canonical
artifacts (results/sanger_hybrid/baseline/trajectory.csv and
events.csv) — the SAME canonical run, never a re-integration:

    D1_altitude_range.png   altitude vs ground range, both in km
    D2_altitude_time.png    altitude vs time, both in km / s
    D3_velocity_time.png    velocity vs time, both in km/s
    D4_gamma_time.png       flight-path angle vs time (event semantics
                            distinguished in the legend)
    D5_mode_timeline.png    ATM / VAC mode timeline

Rendering conventions (D7B-pre):

* trajectory curves and event markers use the SAME units on every axis
  (km for range/altitude, km/s for velocity, s for time);
* every event semantic contributes exactly one legend entry (deduplicated);
* no event-marker unit mixing (the previous m vs km / m/s vs km/s
  mismatch is fixed);
* no re-integration: the figures are redrawn from the canonical CSV
  artifacts only.

Run from the project root:

    python experiments/04_sanger_hybrid/plot_sanger_baseline.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT / "results" / "sanger_hybrid" / "baseline"
FIG_DIR = BASE_DIR / "figures"

DPI = 300
ATM_COLOR = "#1f77b4"
VAC_COLOR = "#2ca02c"
EVENT_STYLE = {
    "atmospheric_pullout": ("pull-out (ATM min)", "o", "#d62728"),
    "atmosphere_exit": ("atmosphere exit", "^", "#9467bd"),
    "vacuum_apogee": ("vacuum apogee", "s", "#ff7f0e"),
    "atmosphere_entry": ("atmosphere entry", "v", "#8c564b"),
    "srti": ("SRTI (research endpoint)", "*", "#000000"),
}
# Scaling from raw artifact units to the display unit of each axis.
RANGE_SCALE = 1e-3   # m -> km
ALT_SCALE = 1e-3     # m -> km
VEL_SCALE = 1e-3     # m/s -> km/s


def _load():
    t, alt, rng, v, gam, mode = [], [], [], [], [], []
    with open(BASE_DIR / "trajectory.csv", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        idx = {name: i for i, name in enumerate(header)}
        for line in f:
            p = line.strip().split(",")
            t.append(float(p[idx["time_s"]]))
            alt.append(float(p[idx["altitude_m"]]))
            rng.append(float(p[idx["range_m"]]))
            v.append(float(p[idx["velocity_mps"]]))
            gam.append(float(p[idx["gamma_deg"]]))
            mode.append(p[idx["mode"]])
    events = []
    with open(BASE_DIR / "events.csv", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        idx = {name: i for i, name in enumerate(header)}
        for line in f:
            p = line.strip().split(",")
            events.append({
                "kind": p[idx["event_kind"]],
                "time_s": float(p[idx["time_s"]]),
                "altitude_m": float(p[idx["altitude_m"]]),
                "range_m": float(p[idx["range_m"]]),
                "velocity_mps": float(p[idx["velocity_mps"]]),
                "gamma_deg": float(p[idx["gamma_deg"]]),
            })
    return (
        np.array(t), np.array(alt), np.array(rng), np.array(v),
        np.array(gam), np.array(mode, dtype=object), events,
    )


def _legend_once(ax, fontsize=7):
    """Deduplicated legend: one entry per distinct label."""
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize=fontsize,
              loc="upper right")


def _mark(ax, events, key, x_key, y_key, x_scale, y_scale):
    """Scatter one event semantic at the DISPLAY units (scaled)."""
    for e in events:
        if e["kind"] != key:
            continue
        label, marker, color = EVENT_STYLE[key]
        ax.scatter(e[x_key] * x_scale, e[y_key] * y_scale, marker=marker,
                   s=60, color=color, zorder=5, label=label)


def main() -> None:
    t, alt, rng, v, gam, mode, events = _load()
    atm_mask = mode == "SANGER_ATM"
    vac_mask = mode == "SANGER_VAC"

    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # ---- D1: altitude vs range (both km) --------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(rng[atm_mask] * RANGE_SCALE, alt[atm_mask] * ALT_SCALE,
            color=ATM_COLOR, lw=1.2, label="SANGER_ATM")
    ax.plot(rng[vac_mask] * RANGE_SCALE, alt[vac_mask] * ALT_SCALE,
            color=VAC_COLOR, lw=1.2, label="SANGER_VAC")
    for key in EVENT_STYLE:
        _mark(ax, events, key, "range_m", "altitude_m",
              RANGE_SCALE, ALT_SCALE)
    ax.axhline(100.0, color="gray", ls="--", lw=0.8,
               label="h_atm = 100 km")
    ax.set_xlabel("Ground range R [km]")
    ax.set_ylabel("Altitude h [km]")
    ax.set_title("Sanger Hybrid Baseline — Altitude vs Range")
    ax.grid(alpha=0.3)
    _legend_once(ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D1_altitude_range.png", dpi=DPI)
    plt.close(fig)

    # ---- D2: altitude vs time (km / s) -----------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(t, alt * ALT_SCALE, color=ATM_COLOR, lw=1.2,
            label="Sanger trajectory")
    ax.axhline(100.0, color="gray", ls="--", lw=0.8,
               label="h_atm = 100 km")
    for key in ("atmosphere_exit", "atmosphere_entry", "srti"):
        _mark(ax, events, key, "time_s", "altitude_m", 1.0, ALT_SCALE)
    ax.set_xlabel("Time t [s]")
    ax.set_ylabel("Altitude h [km]")
    ax.set_title("Sanger Hybrid Baseline — Altitude vs Time")
    ax.grid(alpha=0.3)
    _legend_once(ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D2_altitude_time.png", dpi=DPI)
    plt.close(fig)

    # ---- D3: velocity vs time (km/s) -------------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(t, v * VEL_SCALE, color=ATM_COLOR, lw=1.2, label="v(t)")
    for key in EVENT_STYLE:
        _mark(ax, events, key, "time_s", "velocity_mps", 1.0, VEL_SCALE)
    ax.set_xlabel("Time t [s]")
    ax.set_ylabel("Velocity v [km/s]")
    ax.set_title("Sanger Hybrid Baseline — Velocity vs Time")
    ax.grid(alpha=0.3)
    _legend_once(ax, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D3_velocity_time.png", dpi=DPI)
    plt.close(fig)

    # ---- D4: gamma vs time (deg; event semantics distinguished) ----------
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(t, gam, color=ATM_COLOR, lw=1.2, label="gamma(t)")
    ax.axhline(0.0, color="gray", lw=0.8)
    for key in ("atmospheric_pullout", "vacuum_apogee", "srti"):
        _mark(ax, events, key, "time_s", "gamma_deg", 1.0, 1.0)
    ax.set_xlabel("Time t [s]")
    ax.set_ylabel("Flight-path angle gamma [deg]")
    ax.set_title("Sanger Hybrid Baseline — Flight-Path Angle vs Time")
    ax.grid(alpha=0.3)
    _legend_once(ax, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D4_gamma_time.png", dpi=DPI)
    plt.close(fig)

    # ---- D5: mode timeline (unchanged design, minor typography) ----------
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    change_idx = np.where(mode[1:] != mode[:-1])[0]
    bounds = np.concatenate(([0], change_idx + 1, [len(t)]))
    for k in range(len(bounds) - 1):
        a = t[bounds[k]]
        b = t[bounds[k + 1] - 1]
        m = mode[bounds[k]]
        color = ATM_COLOR if m == "SANGER_ATM" else VAC_COLOR
        ax.barh(0, b - a, left=a, height=0.5, color=color,
                edgecolor="black", linewidth=0.5)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=ATM_COLOR, label="SANGER_ATM"),
        plt.Rectangle((0, 0), 1, 1, color=VAC_COLOR, label="SANGER_VAC"),
    ]
    for e in events:
        if e["kind"] == "srti":
            ax.axvline(e["time_s"], color="black", ls="--", lw=1.0)
    ax.set_xlim(0.0, t[-1] + 30.0)  # leave room for the SRTI marker
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel("Time t [s]")
    ax.set_title("Sanger Hybrid Baseline — ATM / VAC Mode Timeline")
    ax.legend(handles=handles, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D5_mode_timeline.png", dpi=DPI)
    plt.close(fig)

    # ---- report ------------------------------------------------------------
    print("Figures written (300 dpi PNG):")
    for name in (
        "D1_altitude_range.png", "D2_altitude_time.png",
        "D3_velocity_time.png", "D4_gamma_time.png",
        "D5_mode_timeline.png",
    ):
        path = FIG_DIR / name
        img = plt.imread(path)
        print(
            f"  {name:24s} {img.shape[1]}x{img.shape[0]} px  "
            f"{path.stat().st_size / 1024.0:.1f} KiB"
        )


if __name__ == "__main__":
    main()
