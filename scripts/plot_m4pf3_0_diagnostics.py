"""Create the ten locked M4-PF3-0 diagnostic figures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from hyptraj.m4pf3.diagnostics import (
    _as_proposal,
    load_archive,
    mahalanobis_squared,
    normalized_variance_mass,
)


REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf3_0" / "summary"
FIGURES = REPO / "figures" / "phase_m4pf3_0"


def read_csv(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def finish(figure, name: str) -> None:
    figure.tight_layout()
    figure.savefig(FIGURES / name, dpi=190, bbox_inches="tight")
    plt.close(figure)


def setup() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "#fbfbfc",
    })


def colors(rows):
    return ["#2563eb" if row["action_class"] == "WIDEN" else "#ea580c"
            for row in rows]


def main() -> None:
    setup()
    states = read_csv("m4pf3_0_state_diagnostics.csv")
    components = read_csv("m4pf3_0_component_diagnostics.csv")
    summary = json.loads((SUMMARY / "m4pf3_0_diagnostic_summary.json").read_text(
        encoding="utf-8"))
    labels = [row["state_id"] for row in states]
    x = np.arange(len(states))

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    alpha = np.asarray([float(row["alpha"]) for row in components])
    rbar = np.asarray([float(row["r_bar"]) for row in components])
    ax.scatter(alpha, rbar, c=["#2563eb" if row["action_class"] == "WIDEN"
                              else "#ea580c" for row in components],
               alpha=0.82, edgecolor="white", linewidth=0.5)
    ax.plot([0, 1], [0, 1], "--", color="#475569", lw=1)
    ax.set(xlabel="Nominal component weight $\\alpha_k$",
           ylabel="Tilted responsibility $\\bar r_k$",
           title="PF3-0-1  Nominal allocation vs M2-tilted allocation",
           xlim=(0, 1), ylim=(0, 1))
    finish(fig, "PF3-0-1_nominal_vs_tilted_allocation.png")

    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    values = np.asarray([float(row["A_alloc"]) for row in states])
    ax.bar(x, values, color=colors(states), width=0.8)
    ax.axhline(0.10, ls="--", color="#334155", label="median gate 0.10")
    ax.axhline(0.15, ls=":", color="#7c3aed", label="state gate 0.15")
    ax.set(ylabel="$A_{alloc}$", title="PF3-0-2  Allocation mismatch by state",
           xticks=x, xticklabels=labels)
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False, ncol=2)
    finish(fig, "PF3-0-2_allocation_mismatch_by_state.png")

    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    component_x = np.arange(len(components))
    ratio = np.asarray([float(row["starvation_ratio"]) for row in components])
    ax.scatter(component_x, ratio,
               c=["#2563eb" if row["action_class"] == "WIDEN" else "#ea580c"
                  for row in components], s=24)
    ax.axhline(1.0, ls="--", color="#334155")
    ax.set_yscale("log")
    ax.set(xlabel="State-component pair", ylabel="$\\bar r_k/\\alpha_k$ (log scale)",
           title="PF3-0-3  Component starvation ratios")
    finish(fig, "PF3-0-3_component_starvation_ratios.png")

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    grid = np.linspace(0.0, 45.0, 361)
    for row in states:
        archive = load_archive(
            REPO / "results" / "phase_m4pf2" / "gradient_samples"
            / "confirmation" / f"{row['state_id']}.npz")
        _, means, covariances = _as_proposal(archive["proposal_identity"])
        distances = mahalanobis_squared(
            archive["samples"], means, covariances).min(axis=1)
        weights = normalized_variance_mass(archive["variance_mass"])
        bins = np.searchsorted(grid, distances, side="right") - 1
        bins = np.clip(bins, 0, grid.size - 1)
        hist = np.bincount(bins, weights=weights, minlength=grid.size)
        survival = 1.0 - np.cumsum(hist)
        ax.plot(grid, np.maximum(survival, 1e-7), color=(
            "#2563eb" if row["action_class"] == "WIDEN" else "#ea580c"),
            alpha=0.28, lw=0.8)
    ax.axvline(9.21034037197618, ls="--", color="#334155", label=r"$\tau_{99}$")
    ax.axvline(13.815510557964274, ls=":", color="#7c3aed", label=r"$\tau_{999}$")
    ax.set_yscale("log")
    ax.set(xlabel=r"$d_{min}^2$", ylabel="Tilted survival mass",
           title="PF3-0-4  Tilted nearest-component distance distributions")
    ax.legend(frameon=False)
    finish(fig, "PF3-0-4_tilted_dmin2_distribution.png")

    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    u99 = np.asarray([float(row["U99"]) for row in states])
    u999 = np.asarray([float(row["U999"]) for row in states])
    ax.bar(x - 0.19, u99, 0.38, label="$U_{99}$", color="#2563eb")
    ax.bar(x + 0.19, u999, 0.38, label="$U_{999}$", color="#f59e0b")
    ax.axhline(0.20, ls="--", color="#334155", label="$U_{99}$ state gate")
    ax.axhline(0.25, ls=":", color="#dc2626", label="$U_{999}$ severe gate")
    ax.set(ylabel="Tilted uncovered mass", title="PF3-0-5  Coverage gaps by state",
           xticks=x, xticklabels=labels)
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False, ncol=4, fontsize=8)
    finish(fig, "PF3-0-5_u99_u999_by_state.png")

    fig, ax = plt.subplots(figsize=(9.2, 4.5))
    top1 = np.asarray([float(row["top_1pct_uncovered_fraction"])
                       for row in states])
    top01 = np.asarray([float(row["top_0_1pct_uncovered_fraction"])
                        for row in states])
    ax.bar(x - 0.19, top1, 0.38, label="top 1%", color="#0f766e")
    ax.bar(x + 0.19, top01, 0.38, label="top 0.1%", color="#a21caf")
    ax.axhline(0.25, ls="--", color="#dc2626", label="severe 0.25")
    ax.set(ylabel="Uncovered fraction within tail",
           title="PF3-0-6  Top variance-mass support gaps",
           xticks=x, xticklabels=labels)
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False, ncol=3)
    finish(fig, "PF3-0-6_top_tail_uncovered_mass.png")

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    vrf = np.asarray([float(row["PF2_P11_VRF"]) for row in states])
    ax.scatter(values, vrf, c=colors(states), s=44, edgecolor="white")
    ax.axvline(0.10, ls="--", color="#334155")
    ax.set_yscale("log")
    ax.set(xlabel="$A_{alloc}$", ylabel="PF2 P11 VRF (log scale)",
           title="PF3-0-7  Allocation mismatch vs PF2 efficiency")
    finish(fig, "PF3-0-7_allocation_vs_pf2_vrf.png")

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.scatter(u99, vrf, c=colors(states), s=44, edgecolor="white")
    ax.axvline(0.20, ls="--", color="#334155")
    ax.set_yscale("log")
    ax.set(xlabel="$U_{99}$", ylabel="PF2 P11 VRF (log scale)",
           title="PF3-0-8  Coverage gap vs PF2 efficiency")
    finish(fig, "PF3-0-8_coverage_vs_pf2_vrf.png")

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.axis("off")
    ax.text(0.5, 0.62, "Birth candidate scoring not authorized",
            ha="center", va="center", fontsize=17, weight="bold",
            color="#334155")
    ax.text(0.5, 0.40,
            "Locked aggregate route = A (allocation)\n"
            "Coverage material gate = FALSE\n"
            "No post-hoc birth library was constructed",
            ha="center", va="center", fontsize=11)
    ax.set_title("PF3-0-9  Candidate birth-score gate", pad=12)
    finish(fig, "PF3-0-9_candidate_birth_scores_not_authorized.png")

    fig, ax = plt.subplots(figsize=(6.8, 5.4))
    ax.scatter(values, u99, c=colors(states), s=48, edgecolor="white")
    ax.axvline(0.15, ls="--", color="#7c3aed", label="allocation state gate")
    ax.axhline(0.20, ls="--", color="#0f766e", label="coverage state gate")
    ax.text(0.97, 0.95, f"Locked route: {summary['routing']['route']}",
            transform=ax.transAxes, ha="right", va="top", fontsize=13,
            weight="bold")
    ax.set(xlabel="$A_{alloc}$", ylabel="$U_{99}$",
           title="PF3-0-10  Allocation–coverage routing map")
    ax.legend(frameon=False)
    finish(fig, "PF3-0-10_routing_map.png")

    print(json.dumps({"figures": len(list(FIGURES.glob("*.png"))),
                      "route": summary["routing"]["route"]}, indent=2))


if __name__ == "__main__":
    main()
