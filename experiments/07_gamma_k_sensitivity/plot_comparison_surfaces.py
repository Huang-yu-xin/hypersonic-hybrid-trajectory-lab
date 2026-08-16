"""F6 plotter -- comparison surface core figures (5 PNGs, 300 dpi).

Reads ONLY ``results/gamma_k_sensitivity/comparison_surfaces/`` and the
F3 refined boundary cells (overlay).  Masked pcolormesh; no interpolation
across comparison signatures / grazing boxes.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

OUT_DIR = Path("results/gamma_k_sensitivity/comparison_surfaces")
FIG_DIR = OUT_DIR / "figures"
REFINE_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")

LIMITER_COLORS = {"QIAN": "#1f77b4", "SANGER": "#d62728",
                  "NUMERICAL_TIE": "#9467bd", None: "#f0f0f0"}
D_COLORS = {"UNIQUE": "#2ca02c", "AMBIGUOUS": "#ff7f0e",
            "NOT_AVAILABLE": "#7f7f7f"}


def _load_map() -> list[dict]:
    return json.loads(
        (OUT_DIR / "comparison_map.json").read_text(encoding="utf-8")
    )["points"]


def _grid(records):
    gs = sorted({r["gamma0_deg"] for r in records})
    ks = sorted({r["K"] for r in records})
    return gs, ks


def _metric_matrix(records, proto, metric, amb_marker=False):
    gs, ks = _grid(records)
    lookup = {(r["gamma0_deg"], r["K"]): r for r in records}
    data = np.full((len(gs), len(ks)), np.nan)
    for r in records:
        i, j = gs.index(r["gamma0_deg"]), ks.index(r["K"])
        val = r.get(proto, {}).get(metric)
        if val is not None:
            data[i, j] = val
    return gs, ks, data


def _cat_matrix(records, field_fn):
    gs, ks = _grid(records)
    lookup = {(r["gamma0_deg"], r["K"]): r for r in records}
    mat = [[None] * len(ks) for _ in range(len(gs))]
    for r in records:
        mat[gs.index(r["gamma0_deg"])][ks.index(r["K"])] = field_fn(r)
    return gs, ks, mat


def _draw_metric(ax, records, proto, metric, title, unit_factor, unit,
                 regimes_cells):
    gs, ks, data = _metric_matrix(records, proto, metric)
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
    ax.set_title(title)
    ax.invert_yaxis()
    fig = ax.figure
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label(unit)


def _draw_cat(ax, records, field_fn, colors, title):
    gs, ks, mat = _cat_matrix(records, field_fn)
    mat = np.asarray(mat, dtype=object)
    lut = {v: i for i, v in enumerate(colors)}
    data = np.full(mat.shape, np.nan)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            data[i, j] = lut.get(mat[i][j], len(colors))
    im = ax.pcolormesh(ks, gs, data, cmap="tab20", shading="nearest",
                       vmin=0, vmax=len(colors))
    ax.set_xlabel("K")
    ax.set_ylabel("gamma0 [deg]")
    ax.set_title(title)
    ax.invert_yaxis()
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=c,
                   markersize=8, label=k)
        for k, c in colors.items() if k is not None
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=6)


def _load_regime_cells():
    cells = json.loads(
        (REFINE_DIR / "refined_boundary_cells.json")
        .read_text(encoding="utf-8"))["cells"]
    return cells[::5]


def main() -> int:
    records = _load_map()
    regime_cells = _load_regime_cells()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # F6-F1: common-time DeltaR [km].
    fig, ax = plt.subplots(figsize=(9, 6))
    _draw_metric(ax, records, "protocol_b", "delta_range_m",
                 "F6-F1 DeltaR_time = R_S - R_Q (common time)",
                 1e-3, "km", regime_cells)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "F6_F1_common_time_delta_range.png", dpi=300)
    plt.close(fig)

    # F6-F2: common-range time saving [s].
    fig, ax = plt.subplots(figsize=(9, 6))
    _draw_metric(ax, records, "protocol_c", "time_saving_s",
                 "F6-F2 time_saving = t_Q - t_S (common range)",
                 1.0, "s", regime_cells)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "F6_F2_common_range_time_saving.png", dpi=300)
    plt.close(fig)

    # F6-F3: common-exposure DeltaR [km] with AMBIGUOUS hatch marker.
    gs, ks, data = _metric_matrix(records, "protocol_d", "delta_range_m")
    fig, ax = plt.subplots(figsize=(9, 6))
    _draw_metric(ax, records, "protocol_d", "delta_range_m",
                 "F6-F3 DeltaR_atm_exposure (common exposure; AMBIGUOUS "
                 "masked)", 1e-3, "km", regime_cells)
    # AMBIGUOUS cells: categorical X markers on top.
    for r in records:
        if r.get("protocol_d", {}).get("status") == "AMBIGUOUS":
            ax.scatter(r["K"], r["gamma0_deg"], marker="x", s=20,
                       color="#333333", zorder=5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "F6_F3_common_exposure_delta_range.png", dpi=300)
    plt.close(fig)

    # F6-F4: energy (3 panels).
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    _draw_metric(axes[0], records, "protocol_b", "delta_energy_jpkg",
                 "DeltaE_time", 1e-6, "MJ/kg", regime_cells)
    _draw_metric(axes[1], records, "protocol_c", "delta_energy_jpkg",
                 "DeltaE_range", 1e-6, "MJ/kg", regime_cells)
    _draw_metric(axes[2], records, "protocol_d", "delta_energy_jpkg",
                 "DeltaE_tau (UNIQUE only)", 1e-6, "MJ/kg", regime_cells)
    fig.suptitle("F6-F4 Common-condition energy differences")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG_DIR / "F6_F4_common_condition_energy.png", dpi=300)
    plt.close(fig)

    # F6-F5: comparison semantics (4 categorical panels).
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    _draw_cat(axes[0, 0], records,
              lambda r: r["protocol_b"]["time_limiter"],
              LIMITER_COLORS, "time limiter")
    _draw_cat(axes[0, 1], records,
              lambda r: r["protocol_c"].get("range_limiter"),
              LIMITER_COLORS, "range limiter")
    _draw_cat(axes[1, 0], records,
              lambda r: r["protocol_d"]["exposure_limiter"],
              LIMITER_COLORS, "exposure limiter")
    _draw_cat(axes[1, 1], records,
              lambda r: r.get("protocol_d", {}).get(
                  "status", "NOT_AVAILABLE"),
              D_COLORS, "Protocol D status")
    fig.suptitle("F6-F5 Comparison semantics over gamma0-K")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG_DIR / "F6_F5_comparison_semantics.png", dpi=300)
    plt.close(fig)

    print(f"Figures written to {FIG_DIR}")
    print("F6 PLOT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
