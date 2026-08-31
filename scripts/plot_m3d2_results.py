"""Generate the twelve preregistered M3-D2 benchmark figures."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullLocator

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3d2" / "summary"
OUT = REPO / "figures" / "phase_m3d2"
OUT.mkdir(parents=True, exist_ok=True)

COLORS = {"WIDEN": "#2878B5", "HOLD": "#7A7A7A",
          "SHRINK": "#D95319", "AMBIGUOUS": "#E5AE38",
          "INVALID": "#000000"}
ORDER = ["WIDEN", "HOLD", "SHRINK", "AMBIGUOUS", "INVALID"]


def load(name: str):
    return json.loads((SUMMARY / name).read_text(encoding="utf-8"))


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight")
    plt.close(fig)


def state_map(records, title, name, *, failure_note=None):
    configs = sorted({row["config_id"] for row in records})
    ymap = {cid: index for index, cid in enumerate(configs)}
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for action in ORDER:
        rows = [row for row in records if row["corrected_class"] == action]
        if rows:
            ax.scatter([row["s2"] for row in rows],
                       [ymap[row["config_id"]] for row in rows], s=44,
                       color=COLORS[action], label=action, edgecolor="white",
                       linewidth=0.4)
    ax.set_xscale("log")
    ticks = [1.25, 1.6, 2, 2.5, 3.2, 4, 5, 6.4, 8]
    ax.set_xticks(ticks, ["1.25", "1.60", "2.00", "2.50", "3.20",
                          "4.00", "5.00", "6.40", "8.00"])
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_yticks(range(len(configs)), [cid.split("_")[-1] for cid in configs])
    ax.set_xlabel(r"selected-component scale $s^2$")
    ax.set_ylabel("frozen configuration")
    ax.set_title(title)
    ax.legend(ncol=4, fontsize=8, loc="best")
    if failure_note:
        ax.text(0.01, 0.02, failure_note, transform=ax.transAxes,
                color="#8B0000", fontsize=9, weight="bold")
    save(fig, name)


def main() -> None:
    discovery = load("m3d2_discovery_summary.json")["records"]
    confirmation = load("m3d2_confirmation_summary.json")["records"]
    transition = load("m3d2_class_transition.json")

    state_map(discovery, "D2-1 Corrected discovery candidate classes",
              "D2-1_candidate_class_map.png")

    fig, ax = plt.subplots(figsize=(7.3, 4.5))
    for action in ORDER:
        rows = [row for row in discovery if row["corrected_class"] == action]
        if rows:
            slope = [(row["arms"]["widen"]["M2"] -
                      row["arms"]["shrink"]["M2"]) / 0.4
                     for row in rows]
            ax.scatter([row["s2"] for row in rows], slope,
                       color=COLORS[action], label=action, alpha=0.85)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel(r"$s^2$")
    ax.set_ylabel("symmetric finite-step M2 slope")
    ax.set_title("D2-2 Corrected finite-step slope vs provisional class")
    ax.legend(ncol=3, fontsize=8)
    save(fig, "D2-2_gradient_vs_provisional_class.png")

    fig, ax = plt.subplots(figsize=(7.3, 4.5))
    data, labels = [], []
    for action in ORDER:
        vals = [row["class_certainty_score"] for row in discovery
                if row["corrected_class"] == action and
                row["class_certainty_score"] is not None]
        if vals:
            data.append(vals); labels.append(action)
    ax.boxplot(data, tick_labels=labels, showfliers=True)
    ax.set_ylabel("preregistered class-certainty score")
    ax.set_title("D2-3 Discovery certainty / ambiguity margins")
    save(fig, "D2-3_ambiguity_margin_distribution.png")

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    for action in ORDER:
        rows = [row for row in discovery if row["corrected_class"] == action]
        ax.scatter([row["candidate_index"] for row in rows],
                   [row["arms"]["base"]["P"] for row in rows],
                   color=COLORS[action], label=action, s=28)
    refs = {row["candidate_index"]: row["p_ref_full"] for row in discovery}
    ax.plot(sorted(refs), [refs[index] for index in sorted(refs)],
            color="black", lw=1.0, label="p_ref_full")
    ax.set_xlabel("fixed candidate index")
    ax.set_ylabel("full-event probability")
    ax.set_title("D2-4 Corrected S1-S4 probability by candidate")
    ax.legend(ncol=3, fontsize=8)
    save(fig, "D2-4_corrected_event_probability.png")

    def count_plot(records, title, name):
        counts = Counter(row["corrected_class"] for row in records)
        fig, ax = plt.subplots(figsize=(6.8, 4.4))
        present = [action for action in ORDER if counts[action]]
        bars = ax.bar(present, [counts[action] for action in present],
                      color=[COLORS[action] for action in present])
        ax.bar_label(bars)
        ax.axhline(8, color="black", ls="--", lw=1, label="required = 8")
        ax.set_ylabel("state count")
        ax.set_title(title)
        ax.legend()
        save(fig, name)
    count_plot(discovery, "D2-5 Discovery class counts",
               "D2-5_discovery_class_counts.png")

    state_map(discovery, "D2-6 Discovery state-space coverage",
              "D2-6_discovery_state_space_coverage.png")

    labels = ["WIDEN", "HOLD", "SHRINK", "AMBIGUOUS"]
    matrix = np.zeros((4, 4), dtype=int)
    for row in transition["transitions"]:
        if row["discovery"] in labels and row["confirmation"] in labels:
            matrix[labels.index(row["discovery"]),
                   labels.index(row["confirmation"])] = row["count"]
    fig, ax = plt.subplots(figsize=(6.0, 5.1))
    image = ax.imshow(matrix, cmap="Blues")
    for i in range(4):
        for j in range(4):
            ax.text(j, i, matrix[i, j], ha="center", va="center")
    ax.set_xticks(range(4), labels, rotation=25)
    ax.set_yticks(range(4), labels)
    ax.set_xlabel("confirmation")
    ax.set_ylabel("discovery")
    ax.set_title(f"D2-7 Class transition (agreement {transition['agreement']:.1%})")
    fig.colorbar(image, ax=ax, shrink=0.8)
    save(fig, "D2-7_discovery_confirmation_transition.png")

    count_plot(confirmation, "D2-8 Confirmed class counts",
               "D2-8_confirmed_class_counts.png")

    fig, ax = plt.subplots(figsize=(7.5, 4.7))
    for action in ORDER:
        rows = [row for row in confirmation if row["corrected_class"] == action]
        if rows:
            x = np.arange(len(rows)) + 0.04 * ORDER.index(action)
            ax.scatter(x, [row["arms"]["widen"]["M2"] /
                           row["arms"]["base"]["M2"] for row in rows],
                       marker="o", color=COLORS[action], label=f"{action}: W/B")
            ax.scatter(x, [row["arms"]["shrink"]["M2"] /
                           row["arms"]["base"]["M2"] for row in rows],
                       marker="x", color=COLORS[action], label=f"{action}: S/B")
    ax.axhline(1, color="black", lw=0.8)
    ax.set_ylabel("action M2 / BASE M2")
    ax.set_xlabel("within-class confirmed state index")
    ax.set_title("D2-9 Action M2 ratios by confirmed class")
    ax.legend(ncol=2, fontsize=7)
    save(fig, "D2-9_action_m2_ratios.png")

    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    x = np.arange(len(confirmation))
    ax.plot(x, [row["p_ref_full"] for row in confirmation],
            color="black", lw=1.2, label="p_ref_full")
    for arm, marker in (("base", "o"), ("widen", "^"), ("shrink", "v")):
        ax.scatter(x, [row["arms"][arm]["P"] for row in confirmation],
                   s=24, marker=marker, label=arm)
    ax.set_xlabel("frozen confirmation order")
    ax.set_ylabel("full-event probability")
    ax.set_title("D2-10 Arm probability estimates under the same S1-S4 event")
    ax.legend(ncol=4, fontsize=8)
    save(fig, "D2-10_probability_estimates_across_arms.png")

    state_map(confirmation,
              "D2-11 Confirmed state map — exact 8/8/8 not constructible",
              "D2-11_final_benchmark_map.png",
              failure_note="D2-B: only 3 confirmed HOLD states; no benchmark frozen")

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    data, labels = [], []
    for action in ORDER:
        vals = [row["class_certainty_score"] for row in confirmation
                if row["corrected_class"] == action and
                row["class_certainty_score"] is not None]
        if vals:
            data.append(vals); labels.append(action)
    ax.boxplot(data, tick_labels=labels, showfliers=True)
    ax.set_ylabel("confirmation class-certainty score")
    ax.set_title("D2-12 Confirmed class margins (D2-B)")
    save(fig, "D2-12_final_class_margins.png")

    print(f"saved 12 figures to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
