"""Create the twelve route-aware M4-PF3 result figures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from hyptraj.m4pf3.diagnostics import gaussian_log_density


REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf3" / "summary"
FIGURES = REPO / "figures" / "phase_m4pf3"


def rows(name):
    with (SUMMARY / name).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def finish(fig, name):
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=190, bbox_inches="tight")
    plt.close(fig)


def unavailable(number, title, detail, filename):
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.axis("off")
    ax.text(0.5, 0.61, title, ha="center", va="center", fontsize=17,
            weight="bold", color="#334155")
    ax.text(0.5, 0.39, detail, ha="center", va="center", fontsize=11)
    ax.set_title(f"PF3-{number}  Route-aware protocol gate", pad=12)
    finish(fig, filename)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False,
                         "figure.facecolor": "white",
                         "axes.facecolor": "#fbfbfc"})
    summary = json.loads((SUMMARY / "m4pf3_family_summary.json").read_text(
        encoding="utf-8"))
    state_results = rows("m4pf3_state_results.csv")
    diagnostic = rows("m4pf3_state_diagnostics.csv")
    components = rows("m4pf3_component_allocation.csv")
    coverage = rows("m4pf3_coverage_diagnostics.csv")
    tail = rows("m4pf3_tail_diagnostics.csv")
    by_state = {}
    for row in state_results:
        by_state.setdefault(row["state_id"], {})[row["arm"]] = row
    labels = sorted(by_state)
    a0 = np.asarray([float(by_state[s]["A0"]["VRF_budget"]) for s in labels])
    a1 = np.asarray([float(by_state[s]["A1"]["VRF_budget"]) for s in labels])
    chosen = np.maximum(a0, a1)
    action = [by_state[s]["A0"]["action_class"] for s in labels]
    color = ["#2563eb" if value == "WIDEN" else "#ea580c" for value in action]

    fig, ax = plt.subplots(figsize=(6.8, 5.1))
    x = np.arange(3)
    vals = [summary["arms"][0]["median_VRF"],
            summary["arms"][1]["median_VRF"],
            summary["freeoracle"]["median_VRF"]]
    ax.bar(x, vals, color=["#64748b", "#7c3aed", "#0f766e"], width=0.65)
    ax.axhline(0.1, ls="--", color="#f59e0b", label="material gate 0.1")
    ax.axhline(1.0, ls=":", color="#dc2626", label="absolute gate 1")
    ax.set_yscale("log")
    ax.set(xticks=x, xticklabels=["A0 P11", "A1 allocation", "FreeOracle"],
           ylabel="Median VRF (log scale)",
           title="PF3-1  FreeOracle VRF by authorized arm")
    ax.legend(frameon=False)
    finish(fig, "PF3-1_freeoracle_vrf_by_arm.png")

    fig, ax = plt.subplots(figsize=(6.3, 5.3))
    ax.scatter(a0, a1, c=color, s=48, edgecolor="white")
    lo, hi = min(a0.min(), a1.min()) * 0.95, max(a0.max(), a1.max()) * 1.05
    ax.plot([lo, hi], [lo, hi], "--", color="#475569")
    ax.set(xlabel="A0 anchor VRF", ylabel="A1 allocation VRF",
           title="PF3-2  Anchor vs allocation, statewise", xlim=(lo, hi),
           ylim=(lo, hi))
    finish(fig, "PF3-2_anchor_vs_allocation_statewise.png")

    unavailable(3, "Birth arm not authorized",
                "PF3-0 locked Route A\nNo birth proposal was evaluated",
                "PF3-3_anchor_vs_birth_not_authorized.png")
    unavailable(4, "Allocation × birth factorial not authorized",
                "Route C condition was false before confirmation\n"
                "The confirmatory family contains A0 and A1 only",
                "PF3-4_factorial_not_authorized.png")

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    c1 = [row for row in components if row["component_index"] == "1"]
    cx = np.arange(len(c1))
    before = np.asarray([float(row["alpha_A0"]) for row in c1])
    after = np.asarray([float(row["alpha_A1"]) for row in c1])
    for i, (left, right) in enumerate(zip(before, after)):
        ax.plot([i, i], [left, right], color="#94a3b8", lw=1.2)
    ax.scatter(cx, before, color="#64748b", label="A0", s=28)
    ax.scatter(cx, after, color="#7c3aed", label="A1", s=28)
    ax.set(xticks=cx, xticklabels=[row["state_id"] for row in c1],
           ylabel="Component-1 mixture weight",
           title="PF3-5  Locked component-weight changes")
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False)
    finish(fig, "PF3-5_component_weight_changes.png")

    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.4))
    for ax, key0, key1, title in (
        (axes[0], "U99_A0", "U99_A1_reweighted", "$U_{99}$"),
        (axes[1], "U999_A0", "U999_A1_reweighted", "$U_{999}$")):
        before_c = np.asarray([float(row[key0]) for row in coverage])
        after_c = np.asarray([float(row[key1]) for row in coverage])
        ax.scatter(before_c, after_c, c=color, s=40, edgecolor="white")
        limit = max(before_c.max(), after_c.max(), 1e-6) * 1.05
        ax.plot([0, limit], [0, limit], "--", color="#475569")
        ax.set(xlabel=f"A0 {title}", ylabel=f"A1 reweighted {title}",
               xlim=(-0.01 * limit, limit), ylim=(-0.01 * limit, limit))
    fig.suptitle("PF3-6  Coverage metric before vs after allocation")
    finish(fig, "PF3-6_coverage_before_after.png")

    fig, ax = plt.subplots(figsize=(6.3, 5.2))
    top0 = np.asarray([float(row["top_1pct_uncovered_A0"])
                       for row in coverage])
    top1 = np.asarray([float(row["top_1pct_uncovered_A1_reweighted"])
                       for row in coverage])
    ax.scatter(top0, top1, c=color, s=45, edgecolor="white")
    limit = max(top0.max(), top1.max(), 1e-6) * 1.05
    ax.plot([0, limit], [0, limit], "--", color="#475569")
    ax.set(xlabel="A0 top-1% uncovered fraction",
           ylabel="A1 reweighted top-1% uncovered fraction",
           title="PF3-7  Top-tail support metric before vs after")
    finish(fig, "PF3-7_top_tail_before_after.png")

    gain = np.log(a1 / a0)
    p11_alloc = np.asarray([float(row["P11_A_alloc"]) for row in diagnostic])
    p11_u99 = np.asarray([float(row["P11_U99"]) for row in diagnostic])
    fig, ax = plt.subplots(figsize=(6.3, 5.0))
    ax.scatter(p11_alloc, gain, c=color, s=46, edgecolor="white")
    ax.axhline(0, ls="--", color="#475569")
    ax.set(xlabel="Fresh P11 $A_{alloc}$", ylabel="log(VRF A1/A0)",
           title="PF3-8  Allocation gain vs mismatch")
    finish(fig, "PF3-8_gain_vs_allocation_mismatch.png")

    fig, ax = plt.subplots(figsize=(6.3, 5.0))
    ax.scatter(p11_u99, gain, c=color, s=46, edgecolor="white")
    ax.axhline(0, ls="--", color="#475569")
    ax.set(xlabel="Fresh P11 $U_{99}$", ylabel="log(VRF A1/A0)",
           title="PF3-9  Allocation gain vs coverage gap")
    finish(fig, "PF3-9_gain_vs_coverage_gap.png")

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.5))
    ess = [[float(row["ESS"]) for row in tail if row["arm"] == arm]
           for arm in ("A0", "A1")]
    maxw = [[float(row["max_normalized_weight"]) for row in tail
             if row["arm"] == arm] for arm in ("A0", "A1")]
    axes[0].boxplot(ess, tick_labels=["A0", "A1"], showfliers=False)
    axes[0].set(ylabel="ESS", title="ESS")
    axes[1].boxplot(maxw, tick_labels=["A0", "A1"], showfliers=False)
    axes[1].set(ylabel="Maximum normalized weight", title="Tail concentration")
    fig.suptitle("PF3-10  ESS and tail safety")
    finish(fig, "PF3-10_ess_tail_safety.png")

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    sx = np.arange(len(labels))
    ax.bar(sx, chosen, color=color, width=0.8)
    ax.axhline(0.1, ls="--", color="#f59e0b", label="material 0.1")
    ax.axhline(1.0, ls=":", color="#dc2626", label="absolute 1")
    ax.set_yscale("log")
    ax.set(xticks=sx, xticklabels=labels, ylabel="FreeOracle VRF (log scale)",
           title="PF3-11  Absolute-efficiency gates")
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False)
    finish(fig, "PF3-11_absolute_efficiency_gates.png")

    representative = labels[int(np.argmax(gain))]
    raw = json.loads((REPO / "results/phase_m4pf3/m4pf3_confirmation_raw.json").read_text(
        encoding="utf-8"))
    record = next(row for row in raw["states"] if row["state_id"] == representative)
    identity = record["anchor_identity"]
    means = np.asarray(identity["centers"], dtype=float)
    covs = tuple(np.asarray(c, dtype=float) for c in identity["covariances"])
    weights = [np.asarray(record["update"]["alpha"]),
               np.asarray(record["update"]["alpha_prime"])]
    span = np.vstack([means - 3.2, means + 3.2])
    gx = np.linspace(span[:, 0].min(), span[:, 0].max(), 180)
    gy = np.linspace(span[:, 1].min(), span[:, 1].max(), 180)
    xx, yy = np.meshgrid(gx, gy)
    points = np.column_stack([xx.ravel(), yy.ravel()])
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.5), sharex=True, sharey=True)
    for ax, w, title in zip(axes, weights, ("A0 P11", "A1 reallocated")):
        density = sum(w[k] * np.exp(gaussian_log_density(
            points, means[k], covs[k])) for k in range(len(w)))
        ax.contourf(xx, yy, density.reshape(xx.shape), levels=16, cmap="Blues")
        ax.scatter(means[:, 0], means[:, 1], s=300 * w + 30,
                   c=["#f59e0b", "#7c3aed"], edgecolor="white")
        for k, value in enumerate(w):
            ax.text(means[k, 0], means[k, 1], f"  {value:.3f}", va="bottom")
        ax.set(title=title, xlabel="$z_1$", ylabel="$z_2$")
    fig.suptitle(f"PF3-12  Representative allocation geometry: {representative}")
    finish(fig, "PF3-12_representative_allocation_geometry.png")

    print(json.dumps({"figures": len(list(FIGURES.glob("*.png"))),
                      "representative_state": representative,
                      "verdict": summary["verdict"]}, indent=2))


if __name__ == "__main__":
    main()
