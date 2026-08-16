"""F5 plotter -- structural sensitivity core figures (5 PNGs, 300 dpi).

Reads ONLY ``results/gamma_k_sensitivity/structural_sensitivity/`` and
the F3 refined boundary cells (mask overlay).  Categorical status maps
and masked pcolormesh derivative fields; NO interpolation across
boundaries, NO fake smooth contours.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

OUT_DIR = Path("results/gamma_k_sensitivity/structural_sensitivity")
FIG_DIR = OUT_DIR / "figures"
REFINE_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")

STATUS_COLORS = {
    "GLOBAL_ACCEPTED": "#2ca02c",
    "ADAPTIVE_ACCEPTED": "#1f77b4",
    "BOUNDARY_INTERSECTION": "#d62728",
    "TOPOLOGY_CHANGE": "#ff7f0e",
    "RECOVERED_EVENT_EXCLUDED": "#9467bd",
    "GUARDRAIL_CENTRAL_UNAVAILABLE": "#7f7f7f",
    "NO_SAFE_STENCIL": "#8c564b",
    "NO_CONVERGENCE": "#e377c2",
    "INVALID": "#f0f0f0",
}

REGIME_OUTLINES = {"B0": "#555555", "B1": "#555555", "B2": "#555555",
                   "B3": "#555555", "B4": "#555555"}


def _load_map() -> list[dict]:
    return json.loads(
        (OUT_DIR / "sensitivity_map.json").read_text(encoding="utf-8")
    )["points"]


def _grid(records):
    gs = sorted({r["gamma0_deg"] for r in records})
    ks = sorted({r["K"] for r in records})
    return gs, ks


def _field_matrix(records, model, param, output):
    """masked matrix of derivative values (NaN at invalid cells)."""
    gs, ks = _grid(records)
    lookup = {(r["gamma0_deg"], r["K"]): r for r in records}
    data = np.full((len(gs), len(ks)), np.nan)
    for r in records:
        i = gs.index(r["gamma0_deg"])
        j = ks.index(r["K"])
        d = r[model][param].get("derivatives") or {}
        if r[model][param]["status"] in ("GLOBAL_ACCEPTED",
                                         "ADAPTIVE_ACCEPTED"):
            data[i, j] = d.get(output, np.nan)
    return gs, ks, data


def _status_matrix(records, model, param):
    gs, ks = _grid(records)
    lookup = {(r["gamma0_deg"], r["K"]): r for r in records}
    mat = np.full((len(gs), len(ks)), "", dtype=object)
    for r in records:
        i = gs.index(r["gamma0_deg"])
        j = ks.index(r["K"])
        mat[i, j] = r[model][param]["status"]
    return gs, ks, mat


def _draw_derivative_panel(ax, records, model, param, output, title,
                           unit_factor, unit_label, regimes_cells):
    gs, ks, data = _field_matrix(records, model, param, output)
    data_vis = data * unit_factor
    vmax = np.nanpercentile(np.abs(data_vis), 95)
    vmax = max(vmax, 1e-30)
    if np.nanmin(data_vis) < 0 < np.nanmax(data_vis):
        norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
        cmap = "RdBu_r"
    else:
        norm = None
        cmap = "viridis"
    masked = np.ma.masked_invalid(data_vis)
    im = ax.pcolormesh(ks, gs, masked, cmap=cmap, norm=norm,
                       shading="nearest")
    for cell in regimes_cells:
        r = cell["rectangle"]
        ax.plot([r["K_min"], r["K_max"], r["K_max"], r["K_min"],
                 r["K_min"]],
                [r["gamma_min"], r["gamma_min"], r["gamma_max"],
                 r["gamma_max"], r["gamma_min"]],
                color="#888888", linewidth=0.25, alpha=0.5)
    ax.set_xlabel("K")
    ax.set_ylabel("gamma0 [deg]")
    ax.set_title(f"{title}\n[{unit_label}] (canonical artifacts store "
                 "per radian / per unit K)")
    ax.invert_yaxis()
    fig = ax.figure
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label(unit_label)


def _draw_status_panel(ax, records, model, param, title):
    gs, ks, mat = _status_matrix(records, model, param)
    colors = np.full(mat.shape, np.nan)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            colors[i, j] = list(STATUS_COLORS.keys()).index(mat[i, j]) \
                if mat[i, j] in STATUS_COLORS else len(STATUS_COLORS)
    im = ax.pcolormesh(ks, gs, colors, cmap="tab20", shading="nearest",
                       vmin=0, vmax=len(STATUS_COLORS))
    ax.set_xlabel("K")
    ax.set_ylabel("gamma0 [deg]")
    ax.set_title(title)
    ax.invert_yaxis()
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=c,
                   markersize=8, label=s)
        for s, c in STATUS_COLORS.items()
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=6)


def _load_regime_cells():
    cells = json.loads(
        (REFINE_DIR / "refined_boundary_cells.json")
        .read_text(encoding="utf-8"))["cells"]
    # Downsample for the overlay (every 5th cell keeps it readable).
    return cells[::5]


def main() -> int:
    records = _load_map()
    regime_cells = _load_regime_cells()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    def _deg_factor():
        return np.pi / 180.0  # per radian -> per degree

    # F5-F1: Qian range sensitivity (km/deg, km/unitK).
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _draw_derivative_panel(
        axes[0], records, "qian", "gamma", "qian_rti_range_m",
        "Qian dR_RTI/dgamma0", 1e-3 * _deg_factor(), "km/deg",
        regime_cells)
    _draw_derivative_panel(
        axes[1], records, "qian", "K", "qian_rti_range_m",
        "Qian dR_RTI/dK", 1e-3, "km/unit K", [])
    fig.suptitle("F5-F1 Qian RTI-range local sensitivity "
                 "(fixed topology; Sanger boxes NOT a Qian mask)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG_DIR / "F5_F1_qian_range_sensitivity.png", dpi=300)
    plt.close(fig)

    # F5-F2: Sanger range sensitivity.
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _draw_derivative_panel(
        axes[0], records, "sanger", "gamma", "sanger_srti_range_m",
        "Sanger dR_SRTI/dgamma0", 1e-3 * _deg_factor(), "km/deg",
        regime_cells)
    _draw_derivative_panel(
        axes[1], records, "sanger", "K", "sanger_srti_range_m",
        "Sanger dR_SRTI/dK", 1e-3, "km/unit K", regime_cells)
    fig.suptitle("F5-F2 Sanger SRTI-range local sensitivity "
                 "(masked at grazing bands)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG_DIR / "F5_F2_sanger_range_sensitivity.png", dpi=300)
    plt.close(fig)

    # F5-F3: Sanger time sensitivity.
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _draw_derivative_panel(
        axes[0], records, "sanger", "gamma", "sanger_srti_time_s",
        "Sanger dT_SRTI/dgamma0", _deg_factor(), "s/deg", regime_cells)
    _draw_derivative_panel(
        axes[1], records, "sanger", "K", "sanger_srti_time_s",
        "Sanger dT_SRTI/dK", 1.0, "s/unit K", regime_cells)
    fig.suptitle("F5-F3 Sanger SRTI-time local sensitivity")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG_DIR / "F5_F3_sanger_time_sensitivity.png", dpi=300)
    plt.close(fig)

    # F5-F4: Sanger energy sensitivity (MJ/kg per deg / per unitK).
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _draw_derivative_panel(
        axes[0], records, "sanger", "gamma", "sanger_energy_loss_jpkg",
        "Sanger d(DeltaE)/dgamma0", 1e-6 * _deg_factor(),
        "MJ/kg per deg", regime_cells)
    _draw_derivative_panel(
        axes[1], records, "sanger", "K", "sanger_energy_loss_jpkg",
        "Sanger d(DeltaE)/dK", 1e-6, "MJ/kg per unit K", regime_cells)
    fig.suptitle("F5-F4 Sanger energy-loss local sensitivity")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG_DIR / "F5_F4_sanger_energy_sensitivity.png", dpi=300)
    plt.close(fig)

    # F5-F5: derivative availability (4 categorical panels).
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, model, param, title in (
        (axes[0, 0], "qian", "gamma", "Qian gamma availability"),
        (axes[0, 1], "qian", "K", "Qian K availability"),
        (axes[1, 0], "sanger", "gamma", "Sanger gamma availability"),
        (axes[1, 1], "sanger", "K", "Sanger K availability"),
    ):
        _draw_status_panel(ax, records, model, param, title)
    fig.suptitle("F5-F5 Derivative availability (categorical masks)")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG_DIR / "F5_F5_derivative_availability.png", dpi=300)
    plt.close(fig)

    print(f"Figures written to {FIG_DIR}")
    print("F5 PLOT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
