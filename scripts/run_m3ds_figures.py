"""M3-DS zero-simulator figures (DS-1 .. DS-8).

All panels are drawn from frozen M3-DS summary artifacts; no simulator and
no controller code is involved. DS-7 and DS-8 are schematics: they document
benchmark structure and metric definitions only, they are not fitted
policies or measured controller results.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3ds" / "summary"
FIG = REPO / "figures" / "phase_m3ds"

CLASS_COLORS = {"WIDEN": "#1b9e77", "SHRINK": "#d95f02", "HOLD": "#7570b3",
                "AMBIGUOUS": "#e7298a"}


def _csv(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _save(fig: plt.Figure, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIG / name}")


def _short(config_id: str) -> str:
    return config_id.split("_")[-1]


def ds1_candidate_universe() -> None:
    rows = _csv("m3ds_directional_candidates.csv")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for row in rows:
        ax.scatter(float(row["s2"]), _short(row["config_id"]),
                   color=CLASS_COLORS[row["class"]], s=70,
                   edgecolor="black", linewidth=0.4)
    for cls in ("WIDEN", "SHRINK"):
        ax.scatter([], [], color=CLASS_COLORS[cls], label=cls, s=70,
                   edgecolor="black", linewidth=0.4)
    ax.set_xscale("log")
    ax.set_xlabel("s2 (log scale)")
    ax.set_ylabel("configuration")
    ax.set_title("DS-1  Directional candidate universe (12 WIDEN / 10 SHRINK, "
                 "D2 independently confirmed)")
    ax.legend()
    _save(fig, "DS-1_directional_candidate_universe.png")


def ds2_selected() -> None:
    rows = _csv("m3ds_directional_candidates.csv")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for row in rows:
        selected = row["selected"] == "True"
        ax.scatter(float(row["s2"]), _short(row["config_id"]),
                   color=CLASS_COLORS[row["class"]],
                   s=110 if selected else 45,
                   marker="o" if selected else "x",
                   alpha=1.0 if selected else 0.55,
                   edgecolor="black" if selected else "none",
                   linewidth=0.6)
    ax.scatter([], [], color="gray", s=110, edgecolor="black",
               label="primary 8W/8S")
    ax.scatter([], [], color="gray", marker="x", s=45,
               label="reserve (4W/2S)")
    ax.set_xscale("log")
    ax.set_xlabel("s2 (log scale)")
    ax.set_ylabel("configuration")
    ax.set_title("DS-2  Deterministic selected directional primary (8 WIDEN / "
                 "8 SHRINK)")
    ax.legend()
    _save(fig, "DS-2_directional_selected_8w_8s.png")


def ds3_config_diversity() -> None:
    rows = [row for row in _csv("m3ds_directional_candidates.csv")
            if row["selected"] == "True"]
    configs = sorted({row["config_id"] for row in rows})
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.38
    for idx, cls in enumerate(("WIDEN", "SHRINK")):
        counts = [sum(1 for row in rows
                      if row["config_id"] == cid and row["class"] == cls)
                  for cid in configs]
        ax.bar([x + (idx - 0.5) * width for x in range(len(configs))],
               counts, width=width, color=CLASS_COLORS[cls], label=cls)
    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels([_short(cid) for cid in configs])
    ax.set_ylabel("selected states per config")
    ax.set_title("DS-3  Config diversity map (5 distinct configs per class, "
                 "gate >= 4 PASS)")
    ax.legend()
    _save(fig, "DS-3_config_diversity_map.png")


def ds4_s2_coverage() -> None:
    rows = _csv("m3ds_directional_candidates.csv")
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for level, cls in enumerate(("WIDEN", "SHRINK")):
        selected = sorted(float(row["s2"]) for row in rows
                          if row["class"] == cls and row["selected"] == "True")
        candidate = sorted(float(row["s2"]) for row in rows
                           if row["class"] == cls)
        ax.scatter(candidate, [level + 0.12] * len(candidate), marker="|",
                   s=180, color=CLASS_COLORS[cls], alpha=0.35,
                   label=f"{cls} candidates")
        ax.scatter(selected, [level - 0.12] * len(selected), marker="|",
                   s=260, color=CLASS_COLORS[cls],
                   label=f"{cls} selected")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["WIDEN", "SHRINK"])
    ax.set_xscale("log")
    ax.set_xlabel("s2 (log scale)")
    ax.set_title("DS-4  s2 coverage by direction (selected covers full "
                 "candidate span)")
    ax.legend(fontsize=8, ncol=2)
    _save(fig, "DS-4_s2_coverage_by_direction.png")


def ds5_support_margins() -> None:
    rows = _csv("m3ds_directional_candidates.csv")
    fig, ax = plt.subplots(figsize=(7, 4))
    for cls in ("WIDEN", "SHRINK"):
        sel = sorted(float(row["confirmation_support"]) for row in rows
                     if row["class"] == cls and row["selected"] == "True")
        res = sorted(float(row["confirmation_support"]) for row in rows
                     if row["class"] == cls and row["selected"] == "False")
        ax.scatter([cls] * len(sel), sel, color=CLASS_COLORS[cls], s=70,
                   label=f"{cls} selected", zorder=3)
        ax.scatter([cls] * len(res), res, color=CLASS_COLORS[cls], s=45,
                   marker="x", label=f"{cls} reserve", zorder=3)
    ax.axhline(1.0, color="black", lw=0.8, ls="--")
    ax.text(1.35, 1.02, "support = 1 reference", fontsize=8)
    ax.set_ylabel("confirmation support margin (class certainty score)")
    ax.set_title("DS-5  Confirmation support margins")
    ax.legend(fontsize=8)
    _save(fig, "DS-5_confirmation_support_margins.png")


def ds6_safety_primary() -> None:
    rows = _csv("m3ds_safety_primary.csv")
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for row in rows:
        ax.scatter(float(row["s2"]), _short(row["config_id"]),
                   color=CLASS_COLORS[row["reference_status"]], s=120,
                   marker="s", edgecolor="black", linewidth=0.5)
    for status in ("HOLD", "AMBIGUOUS"):
        ax.scatter([], [], color=CLASS_COLORS[status], marker="s", s=120,
                   edgecolor="black",
                   label=f"confirmed {status} -> safe behavior: ABSTAIN/BASE")
    ax.set_xscale("log")
    ax.set_xlabel("s2 (log scale)")
    ax.set_ylabel("configuration")
    ax.set_title("DS-6  Safety primary states (3 confirmed HOLD + 2 confirmed "
                 "AMBIGUOUS, reference status preserved)")
    ax.legend(fontsize=8)
    _save(fig, "DS-6_safety_primary_states.png")


def ds7_dual_axis_schematic() -> None:
    benchmark = json.loads((SUMMARY / "m3ds_benchmark.json")
                           .read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axis("off")

    def box(x, y, w, h, text, fc):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.02",
                                    fc=fc, ec="black", lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=7.5)

    box(0.02, 0.52, 0.44, 0.40,
        "Axis A - Directional Sign\n"
        f"primary: {len(benchmark['directional_primary']['widen'])} WIDEN"
        f" + {len(benchmark['directional_primary']['shrink'])} SHRINK\n"
        f"reserve: {len(benchmark['directional_reserve']['widen'])}W + "
        f"{len(benchmark['directional_reserve']['shrink'])}S\n"
        "(robustness only)\n"
        "ground truth: WIDEN / SHRINK",
        "#e8f4ef")
    box(0.54, 0.52, 0.44, 0.40,
        "Axis B - Abstention Safety\n"
        f"primary: {len(benchmark['safety_primary']['confirmed_hold'])} "
        "confirmed HOLD\n"
        f"+ {len(benchmark['safety_primary']['confirmed_ambiguous'])} "
        "confirmed AMBIGUOUS\n"
        "reference status preserved\n"
        "ABSTAIN = protocol, fallback BASE",
        "#f3eef7")
    box(0.24, 0.06, 0.52, 0.30,
        "M3-DS frozen benchmark\n"
        "controller_online_trials = 0\n"
        "rarity_shift = BLOCKED | M3-Q = BLOCKED\n"
        "future: context -> {WIDEN, SHRINK, ABSTAIN}",
        "#f5f5f5")
    for x in (0.24, 0.76):
        ax.add_patch(FancyArrowPatch((x, 0.52), (0.50, 0.38),
                                     arrowstyle="-|>", mutation_scale=12,
                                     lw=0.9, color="black"))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("DS-7  Dual-axis benchmark schematic (M3-DS)")
    _save(fig, "DS-7_dual_axis_benchmark_schematic.png")


def ds8_risk_coverage_schematic() -> None:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    cov = [0.2, 0.4, 0.6, 0.8, 1.0]
    low = [0.02, 0.03, 0.05, 0.08, 0.12]
    high = [0.06, 0.09, 0.13, 0.18, 0.25]
    ax.plot(cov, low, "o-", color="#1b9e77",
            label="illustrative selective policy (lower is better)")
    ax.plot(cov, high, "s--", color="#d95f02",
            label="illustrative always-deploy policy")
    ax.set_xlabel("directional coverage C_dir (fraction non-abstained)")
    ax.set_ylabel("wrong-direction risk R_wrong")
    ax.set_ylim(0, 0.3)
    ax.set_title("DS-8  Future risk-coverage metric schematic "
                 "(definition only; no policy fitted, no controller run)")
    ax.legend(fontsize=8)
    ax.text(0.02, 0.27, "M3-DS defines metrics; M3-G2 will measure them",
            fontsize=8, style="italic")
    _save(fig, "DS-8_risk_coverage_metric_schematic.png")


def main() -> int:
    ds1_candidate_universe()
    ds2_selected()
    ds3_config_diversity()
    ds4_s2_coverage()
    ds5_support_margins()
    ds6_safety_primary()
    ds7_dual_axis_schematic()
    ds8_risk_coverage_schematic()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
