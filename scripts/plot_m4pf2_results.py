"""Render the twelve required M4-PF2 confirmatory figures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf2" / "summary"
RAW = REPO / "results" / "phase_m4pf2" / "m4pf2_confirmation_raw.json"
DEST = REPO / "figures" / "phase_m4pf2"
CELLS = ("P00", "P10", "P01", "P11")
COLORS = {"P00": "#6E7781", "P10": "#2878B5",
          "P01": "#E6A700", "P11": "#D95319"}


def csv_rows(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def add_absolute_gates(ax, axis="y"):
    method = ax.axhline if axis == "y" else ax.axvline
    method(0.1, color="#E6A700", linestyle="--", linewidth=1,
           label="material gate 0.1")
    method(1.0, color="#B22222", linestyle=":", linewidth=1.2,
           label="absolute gate 1")


def save(fig, filename: str):
    fig.tight_layout()
    fig.savefig(DEST / filename, dpi=200)
    plt.close(fig)


def state_lookup(state_rows, cell):
    return {row["state_id"]: float(row["VRF_budget"])
            for row in state_rows if row["cell"] == cell}


def absolute_scatter(state_rows, xcell, ycell, filename):
    xval, yval = state_lookup(state_rows, xcell), state_lookup(state_rows, ycell)
    fig, ax = plt.subplots(figsize=(6.4, 5.8))
    for cls, marker in (("WIDEN", "o"), ("SHRINK", "s")):
        ids = [row["state_id"] for row in state_rows
               if row["cell"] == ycell and row["action_class"] == cls]
        ax.scatter([xval[sid] for sid in ids], [yval[sid] for sid in ids],
                   marker=marker, color=COLORS[ycell], alpha=0.85, label=cls)
    lo = min(min(xval.values()), min(yval.values())) * 0.85
    ax.plot([lo, 1.2], [lo, 1.2], color="black", linewidth=1,
            label="equal VRF")
    for gate, color, style in ((0.1, "#E6A700", "--"),
                               (1.0, "#B22222", ":")):
        ax.axhline(gate, color=color, linestyle=style, linewidth=1)
        ax.axvline(gate, color=color, linestyle=style, linewidth=1)
    ax.set(xscale="log", yscale="log", xlim=(lo, 1.2), ylim=(lo, 1.2),
           xlabel=f"{xcell} statewise VRF", ylabel=f"{ycell} statewise VRF",
           title=f"PF2 statewise {xcell} vs {ycell}")
    ax.grid(True, which="both", alpha=0.2)
    ax.legend(frameon=False)
    save(fig, filename)


def ellipse(ax, covariance, center, color, label):
    cov = np.asarray(covariance, dtype=float)
    cen = np.asarray(center, dtype=float)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    angle = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    patch = Ellipse(cen, 2*np.sqrt(vals[0]), 2*np.sqrt(vals[1]),
                    angle=angle, fill=False, linewidth=2, color=color,
                    label=label)
    ax.add_patch(patch)
    ax.scatter(*cen, color=color, s=20)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    summary = json.loads((SUMMARY / "m4pf2_family_summary.json").read_text(
        encoding="utf-8"))
    family = csv_rows("m4pf2_family_summary.csv")
    state = csv_rows("m4pf2_state_table.csv")
    contrasts = csv_rows("m4pf2_factorial_contrasts.csv")
    tails = csv_rows("m4pf2_tail_diagnostics.csv")
    raw = json.loads(RAW.read_text(encoding="utf-8"))

    # PF2-1
    values = [float(next(row for row in family if row["cell"] == cell)
                    ["median_VRF"]) for cell in CELLS]
    fig, ax = plt.subplots(figsize=(7.4, 5.3))
    bars = ax.bar(CELLS, values, color=[COLORS[cell] for cell in CELLS])
    add_absolute_gates(ax)
    ax.set(yscale="log", ylabel="median absolute VRF",
           title="PF2-1  Locked 2x2 proposal-family comparison")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, value*1.04, f"{value:.5f}",
                ha="center", va="bottom")
    ax.legend(frameon=False)
    save(fig, "PF2-1_vrf_across_factorial_cells.png")

    absolute_scatter(state, "P00", "P10", "PF2-2_p00_vs_p10_statewise_vrf.png")
    absolute_scatter(state, "P01", "P11", "PF2-3_p01_vs_p11_statewise_vrf.png")

    # PF2-4
    ids = [row["state_id"] for row in state if row["cell"] == "P00"]
    fig, ax = plt.subplots(figsize=(12.0, 5.3))
    x = np.arange(len(ids))
    for cell in CELLS:
        lookup = state_lookup(state, cell)
        ax.plot(x, [lookup[sid] for sid in ids], marker="o", markersize=3,
                linewidth=1.2, color=COLORS[cell], label=cell)
    add_absolute_gates(ax)
    ax.set(yscale="log", xticks=x, xticklabels=ids,
           ylabel="absolute VRF",
           title="PF2-4  Frozen 24-state factorial comparison")
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False, ncol=3)
    save(fig, "PF2-4_24_state_log_vrf_factorial.png")

    # PF2-5 mean contrasts
    mean0 = [float(row["mean_effect_without_covariance"]) for row in contrasts]
    mean1 = [float(row["mean_effect_with_covariance"]) for row in contrasts]
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.boxplot([mean0, mean1], tick_labels=["P10/P00", "P11/P01"],
               patch_artist=True,
               boxprops={"facecolor": COLORS["P10"], "alpha": 0.55})
    ax.axhline(0, color="black", linewidth=1)
    ax.set(ylabel="statewise log VRF contrast",
           title="PF2-5  Mean main-effect contrasts")
    ax.grid(True, axis="y", alpha=0.2)
    save(fig, "PF2-5_mean_main_effects.png")

    # PF2-6 covariance contrasts
    cov0 = [float(row["covariance_effect_without_mean"]) for row in contrasts]
    cov1 = [float(row["covariance_effect_with_mean"]) for row in contrasts]
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.boxplot([cov0, cov1], tick_labels=["P01/P00", "P11/P10"],
               patch_artist=True,
               boxprops={"facecolor": COLORS["P01"], "alpha": 0.65})
    ax.axhline(0, color="black", linewidth=1)
    ax.set(ylabel="statewise log VRF contrast",
           title="PF2-6  Rank-1 covariance main-effect contrasts")
    ax.grid(True, axis="y", alpha=0.2)
    save(fig, "PF2-6_covariance_main_effects.png")

    # PF2-7
    interaction = [float(row["interaction"]) for row in contrasts]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    colors = ["#2878B5" if value >= 0 else "#D95319" for value in interaction]
    ax.bar(np.arange(24), interaction, color=colors)
    ax.axhline(0, color="black", linewidth=1)
    ax.set(xlabel="frozen state index", ylabel="interaction log contrast",
           title="PF2-7  Mean-covariance descriptive interaction")
    ax.grid(True, axis="y", alpha=0.2)
    save(fig, "PF2-7_interaction_contrast.png")

    # PF2-8
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    x = np.arange(2)
    width = 0.19
    for offset, cell in zip((-1.5, -0.5, 0.5, 1.5), CELLS):
        record = next(row for row in family if row["cell"] == cell)
        vals = [float(record["WIDEN_median_VRF"]),
                float(record["SHRINK_median_VRF"])]
        ax.bar(x+offset*width, vals, width, color=COLORS[cell], label=cell)
    add_absolute_gates(ax)
    ax.set(yscale="log", xticks=x, xticklabels=["WIDEN", "SHRINK"],
           ylabel="class median VRF",
           title="PF2-8  Class-conditional factorial comparison")
    ax.legend(frameon=False, ncol=2)
    save(fig, "PF2-8_class_conditional_vrf.png")

    # PF2-9
    p00, p10, p11 = (state_lookup(state, cell)
                     for cell in ("P00", "P10", "P11"))
    p10_rows = [row for row in state if row["cell"] == "P10"]
    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    for cls, marker in (("WIDEN", "o"), ("SHRINK", "s")):
        subset = [row for row in p10_rows if row["action_class"] == cls]
        ax.scatter([float(row["mean_gradient_norm"]) for row in subset],
                   [p11[row["state_id"]]/p00[row["state_id"]]
                    for row in subset], marker=marker, alpha=0.85, label=cls)
    ax.axhline(1, color="black", linewidth=1)
    ax.set(xlabel="dimensionless mean-gradient norm",
           ylabel="P11/P00 statewise VRF ratio",
           title="PF2-9  Joint gain versus mean-gradient magnitude")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    save(fig, "PF2-9_vrf_gain_vs_mean_gradient.png")

    # PF2-10
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.8))
    for index, cell in enumerate(CELLS):
        ess = [float(row["ESS"]) for row in tails if row["cell"] == cell]
        top = [float(row["max_normalized_weight"]) for row in tails
               if row["cell"] == cell]
        for ax, vals in zip(axes, (ess, top)):
            ax.boxplot(vals, positions=[index], widths=0.55, patch_artist=True,
                       boxprops={"facecolor": COLORS[cell], "alpha": 0.65})
    for ax in axes:
        ax.set_xticks(range(4), CELLS)
        ax.grid(True, axis="y", alpha=0.2)
    axes[0].set_ylabel("event-weight ESS")
    axes[1].set_ylabel("maximum normalized weight")
    fig.suptitle("PF2-10  Four-cell ESS and tail concentration")
    save(fig, "PF2-10_ess_tail_risk.png")

    # PF2-11
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    ax.set_xscale("log")
    ax.set_xlim(0.004, 2)
    add_absolute_gates(ax, "x")
    free = float(summary["freeoracle"]["median_VRF"])
    ax.scatter(free, 0, s=110, color=COLORS["P11"], zorder=3)
    ax.text(free*1.06, 0, f"PF2 FreeOracle {free:.5f}", va="center")
    ax.set(yticks=[], xlabel="median absolute FreeOracle VRF",
           title="PF2-11  Joint family remains below both gates")
    ax.grid(True, axis="x", which="both", alpha=0.2)
    save(fig, "PF2-11_freeoracle_efficiency_gate.png")

    # PF2-12, strongest and weakest joint gains.
    ratios = {sid: p11[sid]/p00[sid] for sid in ids}
    representative = [max(ratios, key=ratios.get), min(ratios, key=ratios.get)]
    raw_by_id = {row["state_id"]: row for row in raw["states"]}
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.7))
    for ax, sid in zip(axes, representative):
        record = raw_by_id[sid]
        k = int(record["proposal_identity"]["component_index"])
        anchor_center = record["proposal_identity"]["centers"][k]
        anchor_cov = record["proposal_identity"]["covariances"][k]
        displacement = np.asarray(record["update"]["mean"]["displacement"])
        shifted = np.asarray(anchor_center) + displacement
        cov_updated = record["update"]["covariance"]["covariance"]
        ellipse(ax, anchor_cov, anchor_center, COLORS["P00"], "P00 anchor")
        ellipse(ax, anchor_cov, shifted, COLORS["P10"], "P10 mean")
        ellipse(ax, cov_updated, anchor_center, COLORS["P01"], "P01 cov")
        ellipse(ax, cov_updated, shifted, COLORS["P11"], "P11 joint")
        points = np.vstack([anchor_center, shifted])
        radius = 1.4*max(np.sqrt(np.linalg.eigvalsh(anchor_cov).max()),
                         np.sqrt(np.linalg.eigvalsh(cov_updated).max()))
        center = points.mean(axis=0)
        ax.set(xlim=(center[0]-radius, center[0]+radius),
               ylim=(center[1]-radius, center[1]+radius), aspect="equal",
               title=f"{sid}\nP11/P00={ratios[sid]:.3f}")
        ax.grid(True, alpha=0.2)
        ax.legend(frameon=False, fontsize=7)
    fig.suptitle("PF2-12  Representative mean/covariance interventions")
    save(fig, "PF2-12_representative_joint_geometry.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
