"""F2 diagnostic figures -- coarse regime maps and topology margins.

Reads ONLY ``results/gamma_k_sensitivity/coarse_map/`` artifacts.

* F2_sanger_regime_map.png  -- discrete categorical Sanger regime map
  (x = K, y = gamma0) with real sampled positions and BOUNDARY_CANDIDATE
  cell outlines; NO continuous colormap, NO interpolation.
* F2_joint_regime_map.png   -- joint regime map (caption notes the joint
  variation source over sampled D0).
* F2_topology_margins.png   -- M_S [km] and min positive M_A [km] at the
  sampled points (NA masked, never 0).

Diagnostic figures only -- not final paper figures.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT_DIR = Path("results/gamma_k_sensitivity/coarse_map")
FIG_DIR = OUT_DIR / "figures"

SANGER_COLORS = {
    "SRTI_N0": "#7f7f7f",
    "SRTI_N1": "#aec7e8",
    "SRTI_N2": "#98df8a",
    "SRTI_N3": "#ff9896",
    "SRTI_N4": "#ffbb78",
    "SRTI_N5": "#c5b0d5",
    "GROUND_BEFORE_SRTI": "#8c564b",
    "CENSORED": "#e0e0e0",
    "NUMERICAL_FAILURE": "#d62728",
    "INVALID_INPUT": "#ff7f0e",
    "BOUNDARY_AMBIGUOUS": "#9467bd",
    "UNKNOWN": "#f0f0f0",
}

QIAN_COLORS = {
    "QIAN_RTI": "#1f77b4",
    "GROUND_BEFORE_CAPTURE": "#8c564b",
    "GROUND_AFTER_CAPTURE_BEFORE_RTI": "#d62728",
    "CENSORED": "#e0e0e0",
    "NUMERICAL_FAILURE": "#ff7f0e",
    "INVALID_INPUT": "#ffd700",
    "BOUNDARY_AMBIGUOUS": "#9467bd",
    "UNKNOWN": "#f0f0f0",
}


def _load(name: str) -> dict:
    with open(OUT_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _regime_color(regime: str, palette: dict) -> str:
    return palette.get(regime, palette["UNKNOWN"])


def _sanger_figure(matrices: dict, cells: list[dict]) -> plt.Figure:
    g_grid = matrices["gamma_grid"]
    k_grid = matrices["K_grid"]
    sanger = matrices["sanger_regime_matrix"]
    fig, ax = plt.subplots(figsize=(11, 7))
    for i_g, g in enumerate(g_grid):
        for i_k, k in enumerate(k_grid):
            regime = sanger[i_g][i_k]
            if not regime:
                continue
            ax.scatter(
                k, g, marker="s", s=64,
                color=_regime_color(regime, SANGER_COLORS),
                edgecolors="black", linewidths=0.3, zorder=3,
            )
    # Candidate cell outlines (coarse bands, NOT a fitted boundary).
    for cell in cells:
        if not cell["candidate"]:
            continue
        ax.add_patch(Rectangle(
            (cell["K_min"], cell["gamma_min"]),
            cell["K_max"] - cell["K_min"],
            cell["gamma_max"] - cell["gamma_min"],
            fill=False, edgecolor="black", linewidth=0.8, zorder=2,
        ))
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=c,
                   markersize=9, label=regime)
        for regime, c in SANGER_COLORS.items()
        if any(regime in row for row in sanger)
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8,
              title="discrete regimes (sampled points)")
    ax.set_xlabel("K (dimensionless)")
    ax.set_ylabel("gamma0 [deg]")
    ax.set_title("COARSE REGIME MAP — Sanger\n"
                 "Candidate cells for F3 refinement (outlines)")
    ax.invert_yaxis()  # more negative gamma0 at top
    ax.grid(True, alpha=0.3)
    return fig


def _joint_figure(matrices: dict, qian_uniform: bool) -> plt.Figure:
    g_grid = matrices["gamma_grid"]
    k_grid = matrices["K_grid"]
    joint = matrices["joint_regime_matrix"]
    fig, ax = plt.subplots(figsize=(11, 7))
    for i_g, g in enumerate(g_grid):
        for i_k, k in enumerate(k_grid):
            jr = joint[i_g][i_k]
            if not jr or not jr[0]:
                continue
            q_regime, s_regime = jr
            ax.scatter(
                k, g, marker="s", s=64,
                color=_regime_color(s_regime, SANGER_COLORS),
                edgecolors="black", linewidths=0.3, zorder=3,
            )
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=c,
                   markersize=9, label=f"joint=(QIAN_RTI, {regime})")
        for regime, c in SANGER_COLORS.items()
        if any(regime in row for row in joint)
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    ax.set_xlabel("K (dimensionless)")
    ax.set_ylabel("gamma0 [deg]")
    if qian_uniform:
        ax.set_title("JOINT REGIME MAP — Qian uniform QIAN_RTI over sampled "
                     "D0;\njoint variation is entirely due to Sanger")
    else:
        ax.set_title("JOINT REGIME MAP")
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    return fig


def _margins_figure(matrices: dict, records_by_point: dict) -> plt.Figure:
    g_grid = matrices["gamma_grid"]
    k_grid = matrices["K_grid"]
    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(11, 10), sharex=True)
    for ax, key, title in (
        (ax_a, "M_S_clearance_m", "A. M_S = h_atm - h_SRTI at SRTI [km]"),
        (ax_b, "M_A_clearance_m", "B. minimum positive M_A across VAC "
                                  "arcs [km]"),
    ):
        for i_g, g in enumerate(g_grid):
            for i_k, k in enumerate(k_grid):
                rec = records_by_point.get(f"{g:.6f}|{k:.6f}")
                if rec is None:
                    continue
                s = rec["sanger"]
                if key == "M_S_clearance_m":
                    v = s.get("M_S_clearance_m")
                else:
                    ma = s.get("M_A_clearance_m") or []
                    v = min(ma) if ma else None
                if v is None:
                    continue  # NA masked, never plotted as 0
                ax.scatter(k, g, marker="o", s=42,
                           c=[v / 1000.0], cmap="viridis_r",
                           edgecolors="black", linewidths=0.2, zorder=3)
        ax.set_ylabel("gamma0 [deg]")
        ax.set_title(title)
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)
    ax_b.set_xlabel("K (dimensionless)")
    fig.suptitle("F2 TOPOLOGY MARGINS — sampled points only, no "
                 "interpolation; NA masked")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def _load_records_by_point() -> dict:
    coarse = _load("coarse_map.json")["points"]
    return {
        f"{p['parameter'][0]:.6f}|{p['parameter'][1]:.6f}": p
        for p in coarse
    }


def main() -> int:
    summary = _load("coarse_map_summary.json")
    matrices = _load("regime_matrices.json")
    cells = _load("boundary_cells.json")["cells"]
    records = _load_records_by_point()

    FIG_DIR.mkdir(parents=True, exist_ok=True)

    qian_uniform = (
        len(summary["qian"]["regime_counts"]) == 1
        and "QIAN_RTI" in summary["qian"]["regime_counts"]
    )

    fig1 = _sanger_figure(matrices, cells)
    fig1.savefig(FIG_DIR / "F2_sanger_regime_map.png", dpi=150)
    plt.close(fig1)

    fig2 = _joint_figure(matrices, qian_uniform)
    fig2.savefig(FIG_DIR / "F2_joint_regime_map.png", dpi=150)
    plt.close(fig2)

    fig3 = _margins_figure(matrices, records)
    fig3.savefig(FIG_DIR / "F2_topology_margins.png", dpi=150)
    plt.close(fig3)

    print(f"Figures written to {FIG_DIR}")
    print("F2 PLOT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
