"""Render the eight required M3-CA figures from generated CSV/JSON only."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3ca" / "summary"
DEST = REPO / "figures" / "phase_m3ca"

COLORS = {"WIDEN": "#2878B5", "SHRINK": "#D95319"}


def load_rows() -> list[dict]:
    with (SUMMARY / "m3ca_state_table.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    numeric = {
        "s2", "event_probability", "base_m2_median",
        "best_fixed_m2_median", "oracle_m2_median", "m3d_m2_median",
        "m3g_v1_m2_median", "base_vrf_budget_median",
        "best_fixed_vrf_budget_median", "m3d_vrf_budget_median",
        "m3g_v1_vrf_proposal_median", "m3g_v1_vrf_budget_median",
        "free_adaptation_vrf_median", "free_oracle_vrf_median",
        "pilot_fraction", "reference_base_leakage_concentration",
        "proposal_loss_to_oracle_log_m2", "oracle_headroom_state",
        "captured_headroom_state",
    }
    for row in rows:
        for key in numeric:
            row[key] = float(row[key])
        row["headroom_capture_state"] = (
            float(row["headroom_capture_state"])
            if row["headroom_capture_state"] else None)
    return rows


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(DEST / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


def reference_one(ax: plt.Axes, axis: str = "y") -> None:
    if axis == "y":
        ax.axhline(1.0, color="black", linestyle="--", linewidth=1,
                   label="VRF = 1")
    else:
        ax.axvline(1.0, color="black", linestyle="--", linewidth=1,
                   label="VRF = 1")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    summary = json.loads((SUMMARY / "m3ca_cost_attribution.json").read_text(
        encoding="utf-8"))

    # CA-1: proposal-only vs budget-adjusted VRF.
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for cls in ("WIDEN", "SHRINK"):
        sub = [r for r in rows if r["class"] == cls]
        ax.scatter([r["m3g_v1_vrf_proposal_median"] for r in sub],
                   [r["m3g_v1_vrf_budget_median"] for r in sub],
                   s=48, alpha=0.85, color=COLORS[cls], label=cls)
    ax.axhline(1, color="black", linestyle="--", linewidth=1)
    ax.axvline(1, color="black", linestyle="--", linewidth=1)
    ax.plot([0.002, 2], [0.002, 2], color="0.55", linestyle=":",
            label="no adaptation-cost gap")
    ax.set(xscale="log", yscale="log", xlabel="VRF proposal (100k eval)",
           ylabel="VRF budget (20k pilot + 100k eval)",
           title="CA-1  Proposal gain does not reach absolute efficiency")
    ax.legend(frameon=False)
    save(fig, "CA-1_vrf_proposal_vs_vrf_budget.png")

    # CA-2: efficiency ladder.
    c = summary["counterfactuals"]
    names = ["CrudeMC", "BestFixed", "FreeOracle", "M3-D", "M3-G-v1"]
    vals = [c["vrf_budget_crude_mc"], c["vrf_budget_best_fixed"],
            c["vrf_budget_free_oracle"], c["vrf_budget_m3d"],
            c["vrf_budget_m3g_v1"]]
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.bar(names, vals, color=["#777777", "#4C956C", "#F2C14E",
                               "#7B6D8D", "#D95319"])
    ax.set_yscale("log")
    reference_one(ax)
    ax.set(ylabel="Median VRF budget (log scale)",
           title="CA-2  Cost-efficiency attribution ladder")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(frameon=False)
    save(fig, "CA-2_efficiency_ladder.png")

    # CA-3: actual vs free adaptation.
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    order = sorted(rows, key=lambda r: r["m3g_v1_vrf_budget_median"])
    x = np.arange(len(order))
    actual = [r["m3g_v1_vrf_budget_median"] for r in order]
    free = [r["free_adaptation_vrf_median"] for r in order]
    for i in x:
        ax.plot([i, i], [actual[i], free[i]], color="0.75", linewidth=1)
    ax.scatter(x, actual, s=28, color="#D95319", label="deployed M3-G-v1")
    ax.scatter(x, free, s=28, color="#4C956C", label="free adaptation")
    reference_one(ax)
    ax.set_yscale("log")
    ax.set(xlabel="24 frozen states (sorted by deployed VRF)",
           ylabel="VRF budget", title="CA-3  Removing pilot cost is insufficient")
    ax.legend(frameon=False)
    save(fig, "CA-3_free_adaptation.png")

    # CA-4: primary FreeOracle comparison.
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    names = ["BestFixed", "FreeOracle", "M3-G-v1"]
    vals = [c["vrf_budget_best_fixed"], c["vrf_budget_free_oracle"],
            c["vrf_budget_m3g_v1"]]
    bars = ax.bar(names, vals, color=["#4C956C", "#F2C14E", "#D95319"])
    reference_one(ax)
    ax.set_yscale("log")
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.12,
                f"{value:.4f}", ha="center", fontsize=9)
    ax.set(ylabel="Median VRF budget (log scale)",
           title="CA-4  Even FreeOracle remains far below VRF = 1")
    ax.legend(frameon=False)
    save(fig, "CA-4_free_oracle.png")

    # CA-5: class-conditional efficiency.
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    metrics = ["BestFixed", "FreeOracle", "M3-D", "M3-G-v1", "FreeAdapt"]
    keys = ["vrf_budget_best_fixed", "vrf_budget_free_oracle",
            "vrf_budget_m3d", "vrf_budget_m3g_v1",
            "vrf_budget_free_adaptation"]
    pos = np.arange(len(metrics))
    width = 0.36
    for shift, cls in ((-width / 2, "WIDEN"), (width / 2, "SHRINK")):
        vals = [summary["class_summary"][cls][key] for key in keys]
        ax.bar(pos + shift, vals, width, label=cls, color=COLORS[cls])
    ax.set_xticks(pos, metrics, rotation=18)
    ax.set_yscale("log")
    reference_one(ax)
    ax.set(ylabel="Class median VRF budget",
           title="CA-5  WIDEN/SHRINK class-conditional efficiency")
    ax.legend(frameon=False)
    save(fig, "CA-5_class_conditional_efficiency.png")

    # CA-6: all state-level results, no filtering.
    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    order = sorted(rows, key=lambda r: r["free_oracle_vrf_median"])
    x = np.arange(len(order))
    width = 0.42
    ax.bar(x - width / 2, [r["m3g_v1_vrf_budget_median"] for r in order],
           width, color="#D95319", label="M3-G-v1")
    ax.bar(x + width / 2, [r["free_oracle_vrf_median"] for r in order],
           width, color="#F2C14E", label="FreeOracle")
    reference_one(ax)
    ax.set_yscale("log")
    ax.set_xticks(x, [r["state_id"] for r in order], rotation=75, fontsize=7)
    ax.set(ylabel="VRF budget", title="CA-6  All 24 frozen states retained")
    ax.legend(frameon=False, ncol=3)
    save(fig, "CA-6_state_level_efficiency.png")

    # CA-7: pilot fraction is fixed by protocol; show every state at x=1/6.
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for cls in ("WIDEN", "SHRINK"):
        sub = [r for r in rows if r["class"] == cls]
        ax.scatter([r["pilot_fraction"] for r in sub],
                   [r["m3g_v1_vrf_budget_median"] for r in sub],
                   s=50, alpha=0.7, color=COLORS[cls], label=cls)
    reference_one(ax)
    ax.set_yscale("log")
    ax.set(xlabel="Pilot fraction of deployable calls",
           ylabel="M3-G-v1 VRF budget",
           title="CA-7  Pilot fraction is fixed at 1/6 for every state")
    ax.text(0.03, 0.12,
            "Fixed protocol: no cross-state pilot-size variation\n"
            "Spearman correlation is not identifiable",
            transform=ax.transAxes, fontsize=8, ha="left", va="bottom",
            bbox={"facecolor": "white", "edgecolor": "0.8", "alpha": 0.9})
    ax.legend(frameon=False)
    save(fig, "CA-7_pilot_overhead.png")

    # CA-8: relative headroom capture vs absolute efficiency.
    fig, ax = plt.subplots(figsize=(7.4, 5.3))
    for cls in ("WIDEN", "SHRINK"):
        identifiable = [r for r in rows if r["class"] == cls and
                        r["headroom_capture_state"] is not None]
        zero_headroom = [r for r in rows if r["class"] == cls and
                         r["headroom_capture_state"] is None]
        if identifiable:
            ax.scatter([r["headroom_capture_state"] for r in identifiable],
                       [r["m3g_v1_vrf_budget_median"] for r in identifiable],
                       s=48, color=COLORS[cls], label=f"{cls}: identifiable")
        if zero_headroom:
            ax.scatter([0.0] * len(zero_headroom),
                       [r["m3g_v1_vrf_budget_median"] for r in zero_headroom],
                       s=48, facecolors="none", edgecolors=COLORS[cls],
                       label=f"{cls}: zero available headroom")
    ax.scatter([summary["headline_reproduction"]["capture_fraction"]],
               [c["vrf_budget_m3g_v1"]], marker="D", s=90, color="black",
               label="aggregate: 97.1% capture")
    reference_one(ax)
    ax.set_yscale("log")
    ax.set(xlabel="Adaptive headroom capture fraction",
           ylabel="Absolute VRF budget",
           title="CA-8  Near-Oracle relative capture is not absolute efficiency")
    ax.legend(frameon=False, fontsize=8)
    save(fig, "CA-8_headroom_vs_absolute_efficiency.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
