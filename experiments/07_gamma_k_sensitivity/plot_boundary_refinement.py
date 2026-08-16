"""F3 diagnostic figures -- refined grazing boundaries, margin convergence.

Reads ONLY ``results/gamma_k_sensitivity/boundary_refinement/`` and the
F2 coarse map (background).  Discrete categorical rendering; no boundary
curve fit; no interpolation.

* F3_refined_grazing_boundaries.png -- refined terminal boundary boxes
  per branch over the faded F2 coarse Sanger regime map; OPEN-edge boxes
  marked.
* F3_grazing_margin_convergence.png -- |Phi_N| vs refinement depth per
  branch (negative / positive sides, different line styles).
* F3_exit_transversality.png -- minimum newly-created exit dh/dt per
  branch.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")
FIG_DIR = OUT_DIR / "figures"
COARSE_DIR = Path("results/gamma_k_sensitivity/coarse_map")

BRANCH_COLORS = {
    "B0": "#1f77b4",
    "B1": "#2ca02c",
    "B2": "#d62728",
    "B3": "#ff7f0e",
    "B4": "#9467bd",
    "B5": "#8c564b",
    "B6": "#e377c2",
}


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _figure_boundaries() -> plt.Figure:
    coarse = _load(COARSE_DIR / "coarse_map.json")["points"]
    cells = _load(OUT_DIR / "refined_boundary_cells.json")["cells"]
    fig, ax = plt.subplots(figsize=(12, 8))
    # Faded F2 coarse sampled regime background (discrete scatter only).
    regime_color = {
        "SRTI_N0": "#e0e0e0", "SRTI_N1": "#dbe9f6",
        "SRTI_N2": "#dff0dd", "SRTI_N3": "#fbdcdb",
        "SRTI_N4": "#fde8d5", "SRTI_N5": "#e6dcf0",
    }
    for p in coarse:
        regime = p["sanger"]["sanger_regime"]
        ax.scatter(p["parameter"][1], p["parameter"][0],
                   marker="s", s=12,
                   color=regime_color.get(regime, "#f5f5f5"),
                   edgecolors="none", zorder=1)
    for c in cells:
        r = c["rectangle"]
        branch = c.get("branch")
        color = BRANCH_COLORS.get(branch, "#333333")
        open_edges = c.get("open_edges", [])
        if open_edges:
            ax.add_patch(Rectangle(
                (r["K_min"], r["gamma_min"]),
                r["K_max"] - r["K_min"], r["gamma_max"] - r["gamma_min"],
                fill=False, edgecolor="#000000", linewidth=1.4,
                linestyle="--", zorder=4))
        ax.add_patch(Rectangle(
            (r["K_min"], r["gamma_min"]),
            r["K_max"] - r["K_min"], r["gamma_max"] - r["gamma_min"],
            fill=False, edgecolor=color, linewidth=0.9, zorder=3))
    handles = [
        plt.Line2D([0], [0], color=c, linewidth=1.2, label=b)
        for b, c in BRANCH_COLORS.items()
        if any(cell.get("branch") == b for cell in cells)
    ]
    handles.append(plt.Line2D([0], [0], color="black", linewidth=1.4,
                              linestyle="--", label="OPEN edge"))
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    ax.set_xlabel("K (dimensionless)")
    ax.set_ylabel("gamma0 [deg]")
    ax.set_title("F3 REFINED GRAZING BOUNDARIES\n"
                 "terminal boundary boxes per skip-count branch "
                 "(visualization centers only; boxes are the science)")
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    return fig


def _figure_margin_convergence() -> plt.Figure:
    margin = _load(OUT_DIR / "grazing_margin_by_depth.json")
    fig, ax = plt.subplots(figsize=(10, 6))
    for branch in sorted(margin):
        depths = sorted(int(d) for d in margin[branch])
        neg = [margin[branch][str(d)]["closest_negative_phi_m"]
               for d in depths]
        pos = [margin[branch][str(d)]["closest_positive_phi_m"]
               for d in depths]
        color = BRANCH_COLORS.get(branch, "#333333")
        ax.plot(depths, [abs(v) if v is not None else None for v in neg],
                marker="o", linestyle="-", color=color,
                label=f"{branch} N-side |Phi|")
        ax.plot(depths, [abs(v) if v is not None else None for v in pos],
                marker="s", linestyle="--", color=color,
                label=f"{branch} N+1-side |Phi|")
    ax.set_yscale("log")
    ax.set_xlabel("refinement depth")
    ax.set_ylabel("|Phi_N| [m] (distance-to-grazing magnitude)")
    ax.set_title("F3 GRAZING MARGIN CONVERGENCE BY DEPTH\n"
                 "(signed Phi kept in the artifact; magnitude shown here)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    return fig


def _figure_exit_transversality() -> plt.Figure:
    cert = _load(OUT_DIR / "branch_extremal_certification.json")
    fig, ax = plt.subplots(figsize=(9, 5))
    branches = sorted(cert)
    vals = []
    for b in branches:
        n1 = cert[b].get("N1_side")
        vals.append(n1["new_exit_dhdt_mps"] if n1 else None)
    ax.bar(branches, vals, color=[BRANCH_COLORS.get(b, "#333")
                                  for b in branches])
    ax.set_xlabel("branch")
    ax.set_ylabel("min newly-created exit dh/dt [m/s]")
    ax.set_title("F3 NEW-EXIT TRANSVERSALITY AT THE CLOSEST N+1-SIDE POINT\n"
                 "(dh/dt -> 0+ near grazing; NOT a saltation magnitude)")
    ax.grid(True, axis="y", alpha=0.3)
    return fig


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for name, fn in (
        ("F3_refined_grazing_boundaries.png", _figure_boundaries),
        ("F3_grazing_margin_convergence.png", _figure_margin_convergence),
        ("F3_exit_transversality.png", _figure_exit_transversality),
    ):
        fig = fn()
        fig.savefig(FIG_DIR / name, dpi=150)
        plt.close(fig)
    print(f"Figures written to {FIG_DIR}")
    print("F3 PLOT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
