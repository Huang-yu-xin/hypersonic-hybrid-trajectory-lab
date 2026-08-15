"""E5 plotting -- core Phase E comparison figures (visualization only).

Reads ONLY the validated E2-E4 analysis artifacts under
``results/qian_sanger_comparison/``; never re-integrates a trajectory
(no solve_ivp, no builder calls).  Visualization curves come from the
E3 visualization-only curve CSVs; every formal checkpoint marker
(RTI / SRTI / common-time / common-range / Protocol D) is read from the
exact result JSON files -- never from a nearest CSV row.

Outputs (300 dpi PNG) to ``results/qian_sanger_comparison/figures/``:

    E5_F1_trajectory_geometry.png       altitude vs downrange / time
    E5_F2_state_energy_retention.png    velocity & energy-loss vs time
    E5_F3_range_energy_mechanism.png    energy-loss vs downrange
    E5_F4_atmospheric_exposure.png      cumulative tau_ATM vs time
    E5_F5_dynamic_pressure.png          q vs time

plus a human-review contact sheet (not a paper figure).

Unit policy (E0 §19): km / s / km/s / MJ/kg / kPa everywhere; exact
checkpoint values are converted with the same helpers as the curves.
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.parameters import EnvironmentParams

ROOT = Path("results/qian_sanger_comparison")
FIG_DIR = ROOT / "figures"

# Frozen environment for the visualization-only q curve (E5 §22): the
# frozen atmosphere API needs the frozen parameters; no physics is
# re-implemented and no trajectory is integrated.
_FROZEN_ENV = EnvironmentParams()

# ---------------------------------------------------------------------------
# Figure-wide style (E5 §5)
# ---------------------------------------------------------------------------
QIAN_COLOR = "#1f77b4"       # Qian: solid blue
SANGER_COLOR = "#ff7f0e"     # Sanger ATM: solid orange
SANGER_VAC_COLOR = "#fdae6b"  # Sanger VAC: dashed light orange
INTERFACE_COLOR = "#666666"
FONT_SIZE = 10.5
LABEL_SIZE = 12
LEGEND_SIZE = 9.5
DPI = 300

# Consistent checkpoint marker classes (E5 §7, §15, §36).
RTI_MARKER = dict(marker="*", s=140, color=QIAN_COLOR,
                  edgecolors="black", linewidths=0.6, zorder=6)
SRTI_MARKER = dict(marker="*", s=140, color=SANGER_COLOR,
                   edgecolors="black", linewidths=0.6, zorder=6)
CT_MARKER = dict(marker="o", s=55, facecolors="none",
                 edgecolors=QIAN_COLOR, linewidths=1.4, zorder=5)
CR_MARKER = dict(marker="s", s=45, facecolors="none",
                 edgecolors=SANGER_COLOR, linewidths=1.4, zorder=5)
PD_MARKER = dict(marker="^", s=60, facecolors="none",
                 edgecolors=SANGER_COLOR, linewidths=1.4, zorder=5)

# ---------------------------------------------------------------------------
# Unit conversion helpers (single source; markers and curves share them)
# ---------------------------------------------------------------------------
def _km(m: float) -> float:
    return m / 1000.0


def _kmps(mps: float) -> float:
    return mps / 1000.0


def _mj(jpkg: float) -> float:
    return jpkg / 1e6


# ---------------------------------------------------------------------------
# Artifact loading (E5 §2, §36)
# ---------------------------------------------------------------------------
def load_json(relative: str) -> dict:
    path = ROOT / relative
    if not path.exists():
        raise FileNotFoundError(
            f"Missing artifact {path}; run the E2/E3/E4 runners first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_curve_csv(relative: str) -> dict:
    path = ROOT / relative
    if not path.exists():
        raise FileNotFoundError(
            f"Missing artifact {path}; run the E3 mechanism runner first."
        )
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    numeric = {k: np.asarray([float(r[k]) for r in rows], dtype=float)
               for k in rows[0]
               if k not in ("normalized_mode", "source_mode")}
    numeric["normalized_mode"] = [r["normalized_mode"] for r in rows]
    numeric["source_mode"] = [r["source_mode"] for r in rows]
    return numeric


def split_by_mode(curve: dict) -> tuple[dict, dict]:
    """Split a curve into ATM and VAC parts (VAC visual semantics)."""
    mask = np.asarray([m == "ATM" for m in curve["normalized_mode"]])
    vac_mask = ~mask

    def _select(flags):
        out = {}
        for key, value in curve.items():
            if isinstance(value, np.ndarray):
                out[key] = value[flags]
            elif key == "normalized_mode":
                out[key] = [m for m, take in zip(value, flags) if take]
            else:
                out[key] = value
        return out

    return _select(mask), _select(vac_mask)


def vac_intervals() -> list[tuple[float, float]]:
    """Exact VAC intervals from the E3 energy budget (segment endpoints)."""
    budgets = load_json("mechanism/energy_budget.json")
    intervals = []
    for seg in budgets["sanger"]["segment_budgets"]:
        if seg["normalized_mode"] == "VAC":
            intervals.append((seg["t_start_s"], seg["t_end_s"]))
    return intervals


# ---------------------------------------------------------------------------
# Exact checkpoint markers (E5 §36: from JSON, never from curve CSVs)
# ---------------------------------------------------------------------------
def marker_states() -> dict:
    """All formal checkpoint states with exact values, keyed by name."""
    common = load_json("common_conditions/summary.json")
    mechanism = load_json("mechanism/mechanism_summary.json")
    diagnostics = load_json("diagnostics/diagnostics_summary.json")
    pd_artifact = load_json("mechanism/common_atmospheric_exposure.json")

    ct = common["common_time"]
    cr = common["common_range"]
    ne = diagnostics["native_endpoint"]

    return {
        "qian_rti": {
            "time_s": ne["qian_terminal"]["time_s"],
            "range_m": ne["qian_terminal"]["range_m"],
            "altitude_m": ne["qian_terminal"]["altitude_m"],
            "velocity_mps": ne["qian_terminal"]["velocity_mps"],
            "energy_loss_jpkg": ne["qian_terminal"]["energy_loss_jpkg"],
        },
        "sanger_srti": {
            "time_s": ne["sanger_terminal"]["time_s"],
            "range_m": ne["sanger_terminal"]["range_m"],
            "altitude_m": ne["sanger_terminal"]["altitude_m"],
            "velocity_mps": ne["sanger_terminal"]["velocity_mps"],
            "energy_loss_jpkg": ne["sanger_terminal"]["energy_loss_jpkg"],
        },
        "common_time_qian": {
            "time_s": ct["qian_state"]["time_s"],
            "range_m": ct["qian_state"]["range_m"],
            "altitude_m": ct["qian_state"]["altitude_m"],
            "velocity_mps": ct["qian_state"]["velocity_mps"],
            "energy_loss_jpkg": ct["qian_energy_loss_jpkg"],
        },
        "common_time_sanger": {
            "time_s": ct["sanger_state"]["time_s"],
            "range_m": ct["sanger_state"]["range_m"],
            "altitude_m": ct["sanger_state"]["altitude_m"],
            "velocity_mps": ct["sanger_state"]["velocity_mps"],
            "energy_loss_jpkg": ct["sanger_energy_loss_jpkg"],
        },
        "common_range_qian": {
            "time_s": cr["qian_state"]["time_s"],
            "range_m": cr["qian_state"]["range_m"],
            "altitude_m": cr["qian_state"]["altitude_m"],
            "velocity_mps": cr["qian_state"]["velocity_mps"],
            "energy_loss_jpkg": cr["qian_energy_loss_jpkg"],
        },
        "common_range_sanger": {
            "time_s": cr["sanger_state"]["time_s"],
            "range_m": cr["sanger_state"]["range_m"],
            "altitude_m": cr["sanger_state"]["altitude_m"],
            "velocity_mps": cr["sanger_state"]["velocity_mps"],
            "energy_loss_jpkg": cr["sanger_energy_loss_jpkg"],
        },
        # Protocol D states come from the exact common-exposure artifact.
        "protocol_d_qian": {
            "time_s": pd_artifact["qian_state"]["time_s"],
            "range_m": pd_artifact["qian_state"]["range_m"],
            "altitude_m": pd_artifact["qian_state"]["altitude_m"],
            "velocity_mps": pd_artifact["qian_state"]["velocity_mps"],
            "energy_loss_jpkg": pd_artifact["qian_energy_loss_jpkg"],
        },
        "protocol_d_sanger": {
            "time_s": pd_artifact["sanger_state"]["time_s"],
            "range_m": pd_artifact["sanger_state"]["range_m"],
            "altitude_m": pd_artifact["sanger_state"]["altitude_m"],
            "velocity_mps": pd_artifact["sanger_state"]["velocity_mps"],
            "energy_loss_jpkg": pd_artifact["sanger_energy_loss_jpkg"],
        },
    }


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------
def _plot_trajectory_lines(ax, qian_curve, sanger_atm, sanger_vac,
                           x_key, x_conv, y_key, y_conv):
    ax.plot(x_conv(qian_curve[x_key]), y_conv(qian_curve[y_key]),
            color=QIAN_COLOR, lw=1.6, label="Qian (continuous glide)")
    ax.plot(x_conv(sanger_atm[x_key]), y_conv(sanger_atm[y_key]),
            color=SANGER_COLOR, lw=1.6, label="Sanger ATM")
    ax.plot(x_conv(sanger_vac[x_key]), y_conv(sanger_vac[y_key]),
            color=SANGER_VAC_COLOR, lw=1.6, ls="--",
            label="Sanger VAC coast")


def _interface_line(ax, x_lim):
    ax.axhline(100.0, color=INTERFACE_COLOR, ls=":", lw=1.0, alpha=0.9)
    ax.text(x_lim[1] * 0.985, 102.5, "100 km interface",
            ha="right", va="bottom", fontsize=8.5,
            color=INTERFACE_COLOR)


def _style_axes(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, fontsize=LABEL_SIZE)
    ax.set_ylabel(ylabel, fontsize=LABEL_SIZE)
    ax.tick_params(labelsize=FONT_SIZE)
    ax.grid(True, alpha=0.3, lw=0.5)


def _vac_shading(ax, x_max, alpha=0.10):
    for (a, b) in vac_intervals():
        ax.axvspan(a, min(b, x_max), color=SANGER_COLOR, alpha=alpha,
                   lw=0)


def _finalize(fig, fname, caption_note=""):
    fig.tight_layout()
    path = FIG_DIR / fname
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure E1 -- trajectory geometry
# ---------------------------------------------------------------------------
def figure_e1(qian_curve, sanger_curve, states) -> Path:
    sanger_atm, sanger_vac = split_by_mode(sanger_curve)
    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(7.2, 7.8), sharex=False)

    # Panel A: altitude vs downrange.
    _plot_trajectory_lines(ax_a, qian_curve, sanger_atm, sanger_vac,
                           "range_m", _km, "altitude_m", _km)
    _interface_line(ax_a, [0, _km(7000_000.0)])
    ax_a.scatter([_km(states["qian_rti"]["range_m"])],
                 [_km(states["qian_rti"]["altitude_m"])],
                 label="Qian RTI", **RTI_MARKER)
    ax_a.scatter([_km(states["sanger_srti"]["range_m"])],
                 [_km(states["sanger_srti"]["altitude_m"])],
                 label="Sanger SRTI", **SRTI_MARKER)
    ax_a.scatter([_km(states["common_time_qian"]["range_m"]),
                  _km(states["common_time_sanger"]["range_m"])],
                 [_km(states["common_time_qian"]["altitude_m"]),
                  _km(states["common_time_sanger"]["altitude_m"])],
                 label="Common-time checkpoint", **CT_MARKER)
    ax_a.scatter([_km(states["common_range_sanger"]["range_m"])],
                 [_km(states["common_range_sanger"]["altitude_m"])],
                 label="Common-range checkpoint", **CR_MARKER)
    ax_a.annotate("Qian RTI",
                  (_km(states["qian_rti"]["range_m"]),
                   _km(states["qian_rti"]["altitude_m"])),
                  textcoords="offset points", xytext=(8, 6),
                  fontsize=8.5, color=QIAN_COLOR)
    ax_a.annotate("Sanger SRTI",
                  (_km(states["sanger_srti"]["range_m"]),
                   _km(states["sanger_srti"]["altitude_m"])),
                  textcoords="offset points", xytext=(8, 6),
                  fontsize=8.5, color=SANGER_COLOR)
    _style_axes(ax_a, "Downrange [km]", "Altitude [km]")

    # Panel B: altitude vs elapsed time.
    _plot_trajectory_lines(ax_b, qian_curve, sanger_atm, sanger_vac,
                           "time_s", lambda x: x, "altitude_m", _km)
    _interface_line(ax_b, [0, 1200.0])
    _vac_shading(ax_b, 1200.0)
    t_common = states["common_time_sanger"]["time_s"]
    ax_b.axvline(t_common, color=QIAN_COLOR, ls="--", lw=1.0, alpha=0.7)
    ax_b.text(t_common + 6, 108.0, "Common-time checkpoint",
              fontsize=8.5, color=QIAN_COLOR, rotation=90,
              va="bottom", ha="left")
    ax_b.scatter([states["common_time_qian"]["time_s"],
                  states["common_time_sanger"]["time_s"]],
                 [_km(states["common_time_qian"]["altitude_m"]),
                  _km(states["common_time_sanger"]["altitude_m"])],
                 **CT_MARKER)
    ax_b.scatter([states["common_range_sanger"]["time_s"]],
                 [_km(states["common_range_sanger"]["altitude_m"])],
                 label="Common-range (Sanger)", **CR_MARKER)
    ax_b.scatter([states["qian_rti"]["time_s"]],
                 [_km(states["qian_rti"]["altitude_m"])], **RTI_MARKER)
    ax_b.scatter([states["sanger_srti"]["time_s"]],
                 [_km(states["sanger_srti"]["altitude_m"])], **SRTI_MARKER)
    ax_b.annotate("Qian RTI",
                  (states["qian_rti"]["time_s"],
                   _km(states["qian_rti"]["altitude_m"])),
                  textcoords="offset points", xytext=(8, 6),
                  fontsize=8.5, color=QIAN_COLOR)
    ax_b.annotate("Sanger SRTI",
                  (states["sanger_srti"]["time_s"],
                   _km(states["sanger_srti"]["altitude_m"])),
                  textcoords="offset points", xytext=(-70, 6),
                  fontsize=8.5, color=SANGER_COLOR)
    _style_axes(ax_b, "Elapsed time [s]", "Altitude [km]")

    handles, labels = ax_a.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3,
               fontsize=LEGEND_SIZE, framealpha=0.9)
    fig.subplots_adjust(top=0.92)
    return _finalize(fig, "E5_F1_trajectory_geometry.png")


# ---------------------------------------------------------------------------
# Figure E2 -- state and energy retention
# ---------------------------------------------------------------------------
def figure_e2(qian_curve, sanger_curve, states) -> Path:
    sanger_atm, sanger_vac = split_by_mode(sanger_curve)
    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(7.2, 7.8), sharex=True)

    # Panel A: velocity vs time.
    ax_a.plot(qian_curve["time_s"], _kmps(qian_curve["velocity_mps"]),
              color=QIAN_COLOR, lw=1.6, label="Qian")
    ax_a.plot(sanger_atm["time_s"], _kmps(sanger_atm["velocity_mps"]),
              color=SANGER_COLOR, lw=1.6, label="Sanger ATM")
    ax_a.plot(sanger_vac["time_s"], _kmps(sanger_vac["velocity_mps"]),
              color=SANGER_VAC_COLOR, lw=1.6, ls="--",
              label="Sanger VAC coast")
    _vac_shading(ax_a, 1200.0)
    t_common = states["common_time_sanger"]["time_s"]
    ax_a.axvline(t_common, color=QIAN_COLOR, ls="--", lw=1.0, alpha=0.7)
    ax_a.scatter([states["common_time_qian"]["time_s"],
                  states["common_time_sanger"]["time_s"]],
                 [_kmps(states["common_time_qian"]["velocity_mps"]),
                  _kmps(states["common_time_sanger"]["velocity_mps"])],
                 label="Common-time checkpoint", **CT_MARKER)
    ax_a.scatter([states["qian_rti"]["time_s"]],
                 [_kmps(states["qian_rti"]["velocity_mps"])], **RTI_MARKER)
    ax_a.scatter([states["sanger_srti"]["time_s"]],
                 [_kmps(states["sanger_srti"]["velocity_mps"])],
                 **SRTI_MARKER)
    _style_axes(ax_a, "", "Velocity [km/s]")

    # Panel B: specific mechanical-energy loss vs time.
    ax_b.plot(qian_curve["time_s"], _mj(qian_curve["energy_loss_jpkg"]),
              color=QIAN_COLOR, lw=1.6, label="Qian")
    ax_b.plot(sanger_atm["time_s"], _mj(sanger_atm["energy_loss_jpkg"]),
              color=SANGER_COLOR, lw=1.6, label="Sanger ATM")
    ax_b.plot(sanger_vac["time_s"], _mj(sanger_vac["energy_loss_jpkg"]),
              color=SANGER_VAC_COLOR, lw=1.6, ls="--",
              label="Sanger VAC coast")
    _vac_shading(ax_b, 1200.0)
    ax_b.axvline(t_common, color=QIAN_COLOR, ls="--", lw=1.0, alpha=0.7)
    ax_b.scatter([states["common_time_qian"]["time_s"],
                  states["common_time_sanger"]["time_s"]],
                 [_mj(states["common_time_qian"]["energy_loss_jpkg"]),
                  _mj(states["common_time_sanger"]["energy_loss_jpkg"])],
                 **CT_MARKER)
    ax_b.scatter([states["qian_rti"]["time_s"]],
                 [_mj(states["qian_rti"]["energy_loss_jpkg"])],
                 **RTI_MARKER)
    ax_b.scatter([states["sanger_srti"]["time_s"]],
                 [_mj(states["sanger_srti"]["energy_loss_jpkg"])],
                 **SRTI_MARKER)
    ax_b.text(t_common + 8, 0.35, "Common-time checkpoint",
              fontsize=8.5, color=QIAN_COLOR, rotation=90,
              va="bottom", ha="left")
    _style_axes(ax_b, "Elapsed time [s]",
                "Specific mechanical-energy loss [MJ/kg]")

    handles, labels = ax_a.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3,
               fontsize=LEGEND_SIZE, framealpha=0.9)
    fig.subplots_adjust(top=0.92)
    return _finalize(fig, "E5_F2_state_energy_retention.png")


# ---------------------------------------------------------------------------
# Figure E3 -- range-energy mechanism
# ---------------------------------------------------------------------------
def figure_e3(qian_curve, sanger_curve, states) -> Path:
    sanger_atm, sanger_vac = split_by_mode(sanger_curve)
    fig, ax = plt.subplots(figsize=(7.4, 5.6))

    ax.plot(_km(qian_curve["range_m"]), _mj(qian_curve["energy_loss_jpkg"]),
            color=QIAN_COLOR, lw=1.6, label="Qian (continuous glide)")
    ax.plot(_km(sanger_atm["range_m"]), _mj(sanger_atm["energy_loss_jpkg"]),
            color=SANGER_COLOR, lw=1.6, label="Sanger ATM")
    ax.plot(_km(sanger_vac["range_m"]), _mj(sanger_vac["energy_loss_jpkg"]),
            color=SANGER_VAC_COLOR, lw=1.6, ls="--",
            label="Sanger VAC coast")

    # Three checkpoint classes (E5 §15).
    ax.scatter([_km(states["common_time_qian"]["range_m"]),
                _km(states["common_time_sanger"]["range_m"])],
               [_mj(states["common_time_qian"]["energy_loss_jpkg"]),
                _mj(states["common_time_sanger"]["energy_loss_jpkg"])],
               label="Common-time", **CT_MARKER)
    ax.scatter([_km(states["common_range_qian"]["range_m"]),
                _km(states["common_range_sanger"]["range_m"])],
               [_mj(states["common_range_qian"]["energy_loss_jpkg"]),
                _mj(states["common_range_sanger"]["energy_loss_jpkg"])],
               label="Common-range", **CR_MARKER)
    ax.scatter([_km(states["protocol_d_qian"]["range_m"]),
                _km(states["protocol_d_sanger"]["range_m"])],
               [_mj(states["protocol_d_qian"]["energy_loss_jpkg"]),
                _mj(states["protocol_d_sanger"]["energy_loss_jpkg"])],
               label="Protocol D (common exposure)", **PD_MARKER)
    ax.scatter([_km(states["qian_rti"]["range_m"])],
               [_mj(states["qian_rti"]["energy_loss_jpkg"])],
               label="Qian RTI", **RTI_MARKER)
    ax.scatter([_km(states["sanger_srti"]["range_m"])],
               [_mj(states["sanger_srti"]["energy_loss_jpkg"])],
               label="Sanger SRTI", **SRTI_MARKER)

    # VAC plateau annotations (only when the figure is not crowded).
    for i, (a, b) in enumerate(vac_intervals()):
        t_mid = 0.5 * (a + b)
        r_mid = np.interp(t_mid, sanger_curve["time_s"],
                          sanger_curve["range_m"])
        e_mid = np.interp(t_mid, sanger_curve["time_s"],
                          sanger_curve["energy_loss_jpkg"])
        ax.annotate(f"VAC {i + 1}", (_km(r_mid), _mj(e_mid)),
                    textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8, color=SANGER_VAC_COLOR)

    _style_axes(ax, "Downrange [km]",
                "Specific mechanical-energy loss [MJ/kg]")
    ax.legend(fontsize=LEGEND_SIZE, framealpha=0.9, ncol=2, loc="lower right")
    return _finalize(fig, "E5_F3_range_energy_mechanism.png")


# ---------------------------------------------------------------------------
# Figure E4 -- cumulative atmospheric exposure (exact piecewise)
# ---------------------------------------------------------------------------
def figure_e4(states, mechanism_summary, budgets) -> Path:
    fig, ax = plt.subplots(figsize=(7.4, 5.6))

    # Qian: tau = t on the whole research domain (exact piecewise).
    t_q = states["qian_rti"]["time_s"]
    ax.plot([0.0, t_q], [0.0, t_q], color=QIAN_COLOR, lw=1.6,
            label="Qian (ATM throughout)")

    # Sanger: exact piecewise vertices (E5 §18: d tau/dt = 1 in ATM,
    # 0 in VAC), built from the exact segment budgets -- never by
    # numerical integration of sampled points.
    segments = budgets["sanger"]["segment_budgets"]
    t_pts = [0.0]
    tau_pts = [0.0]
    tau = 0.0
    for seg in segments:
        if seg["normalized_mode"] == "ATM":
            tau += seg["duration_s"]
            t_pts.append(seg["t_end_s"])
            tau_pts.append(tau)
        else:  # VAC plateau: time advances, tau stays constant.
            t_pts.append(seg["t_end_s"])
            tau_pts.append(tau)
    ax.plot(t_pts, tau_pts, color=SANGER_COLOR, lw=1.6,
            label="Sanger (VAC plateaus)")

    # Protocol D: same cumulative exposure, different elapsed times.
    tau_common = mechanism_summary["protocol_d"]["tau_common"]
    ax.axhline(tau_common, color=INTERFACE_COLOR, ls=":", lw=1.2, alpha=0.9)
    ax.scatter([states["protocol_d_qian"]["time_s"]],
               [tau_common], label="Protocol D -- Qian", **RTI_MARKER)
    ax.scatter([states["protocol_d_sanger"]["time_s"]],
               [tau_common], label="Protocol D -- Sanger", **PD_MARKER)
    ax.annotate("tau_common", (states["protocol_d_qian"]["time_s"],
                               tau_common),
                textcoords="offset points", xytext=(0, 8), ha="center",
                fontsize=8.5, color=INTERFACE_COLOR)

    # E2 common-time exposure context (E3 diagnostic, exact).
    diag = mechanism_summary["e2_mechanism_diagnostics"]["common_time"]
    ax.scatter([diag["qian_time_s"]], [diag["qian_exposure_s"]],
               label="Common-time checkpoint", **CT_MARKER)
    ax.scatter([diag["sanger_time_s"]], [diag["sanger_exposure_s"]],
               **CT_MARKER)
    ax.annotate("Same tau_ATM,\nlonger elapsed time",
                (states["protocol_d_qian"]["time_s"] + 25,
                 tau_common - 40),
                fontsize=8.5, color=INTERFACE_COLOR)

    _style_axes(ax, "Elapsed time [s]",
                "Cumulative atmospheric-mode exposure [s]")
    ax.set_xlim(0, 1250)
    ax.set_ylim(0, 820)
    ax.legend(fontsize=LEGEND_SIZE, framealpha=0.9, loc="lower right")
    return _finalize(fig, "E5_F4_atmospheric_exposure.png")


# ---------------------------------------------------------------------------
# Figure E5 -- dynamic pressure (visualization-only q curve)
# ---------------------------------------------------------------------------
def figure_e5(qian_curve, sanger_curve, states, aero_artifact) -> Path:
    # q is computed with the frozen atmosphere API only (E5 §22):
    # q = 0.5 * rho(h) * v^2, with VAC identically zero per the frozen
    # hybrid diagnostic semantics.  This is visualization data for an
    # already validated quantity, not a new metric.
    def q_curve(curve):
        rho = np.asarray([
            atmospheric_density(h, _FROZEN_ENV) if m == "ATM" else 0.0
            for h, m in zip(curve["altitude_m"], curve["normalized_mode"])
        ])
        return 0.5 * rho * curve["velocity_mps"] ** 2 / 1000.0  # kPa

    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    sanger_atm, sanger_vac = split_by_mode(sanger_curve)

    ax.plot(qian_curve["time_s"], q_curve(qian_curve),
            color=QIAN_COLOR, lw=1.6, label="Qian")
    ax.plot(sanger_atm["time_s"], q_curve(sanger_atm),
            color=SANGER_COLOR, lw=1.6, label="Sanger ATM")
    ax.plot(sanger_vac["time_s"], q_curve(sanger_vac),
            color=SANGER_VAC_COLOR, lw=1.6, ls="--",
            label="Sanger VAC (q = 0)")
    _vac_shading(ax, 1250.0)

    t_common = states["common_time_sanger"]["time_s"]
    ax.axvline(t_common, color=QIAN_COLOR, ls="--", lw=1.0, alpha=0.7)
    inst = aero_artifact["instantaneous_checkpoints"]["common_time"]
    ax.scatter([inst["qian"]["time_s"]], [inst["qian"]["dynamic_pressure_pa"]
                                          / 1000.0],
               label="Common-time checkpoint (exact)", **CT_MARKER)
    ax.scatter([inst["sanger"]["time_s"]], [inst["sanger"]
                                            ["dynamic_pressure_pa"] / 1000.0],
               **CT_MARKER)
    ax.text(t_common + 8, 55.0, "Common-time checkpoint",
            fontsize=8.5, color=QIAN_COLOR, rotation=90,
            va="bottom", ha="left")

    _style_axes(ax, "Elapsed time [s]", "Dynamic pressure [kPa]")
    ax.set_ylim(0, 70)
    ax.legend(fontsize=LEGEND_SIZE, framealpha=0.9, loc="upper right")
    return _finalize(fig, "E5_F5_dynamic_pressure.png")


# ---------------------------------------------------------------------------
# Contact sheet (human review only, not a paper figure)
# ---------------------------------------------------------------------------
def make_contact_sheet(fig_names: list[str]) -> Path:
    fig, axes = plt.subplots(3, 2, figsize=(13, 17))
    axes = axes.ravel()
    for ax, name in zip(axes, fig_names):
        img = plt.imread(FIG_DIR / name)
        ax.imshow(img)
        ax.set_title(name.replace("E5_F", "Figure E").replace(".png", ""),
                     fontsize=11)
        ax.axis("off")
    for ax in axes[len(fig_names):]:
        ax.axis("off")
    fig.tight_layout()
    path = FIG_DIR / "phase_e_core_figures_contact_sheet.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Programmatic PNG audit (E5 §37)
# ---------------------------------------------------------------------------
def audit_pngs(fig_names: list[str]) -> None:
    print("Programmatic PNG audit:")
    for name in fig_names:
        path = FIG_DIR / name
        if not path.exists():
            raise RuntimeError(f"Figure missing: {path}")
        size = path.stat().st_size
        img = plt.imread(path)
        print(f"  {name:<45} {img.shape[1]}x{img.shape[0]} px  "
              f"{size / 1024:.1f} KiB  loadable=yes")
        if img.size == 0 or size < 10_000:
            raise RuntimeError(f"Figure suspiciously small/empty: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
CORE_FIGURES = [
    "E5_F1_trajectory_geometry.png",
    "E5_F2_state_energy_retention.png",
    "E5_F3_range_energy_mechanism.png",
    "E5_F4_atmospheric_exposure.png",
    "E5_F5_dynamic_pressure.png",
]


def main() -> int:
    print("E5 PHASE E CORE FIGURES -- VISUALIZATION ONLY")
    print("=" * 72)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    qian_curve = load_curve_csv("mechanism/qian_energy_curve.csv")
    sanger_curve = load_curve_csv("mechanism/sanger_energy_curve.csv")
    states = marker_states()
    mechanism_summary = load_json("mechanism/mechanism_summary.json")
    budgets = load_json("mechanism/energy_budget.json")
    aero = load_json("diagnostics/aerodynamic_diagnostics.json")

    figure_e1(qian_curve, sanger_curve, states)
    print("Figure E1 saved")
    figure_e2(qian_curve, sanger_curve, states)
    print("Figure E2 saved")
    figure_e3(qian_curve, sanger_curve, states)
    print("Figure E3 saved")
    figure_e4(states, mechanism_summary, budgets)
    print("Figure E4 saved")
    figure_e5(qian_curve, sanger_curve, states, aero)
    print("Figure E5 saved")

    make_contact_sheet(CORE_FIGURES)
    print("Contact sheet saved")

    audit_pngs(CORE_FIGURES + ["phase_e_core_figures_contact_sheet.png"])
    print("E5 PLOT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
