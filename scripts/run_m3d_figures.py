"""M3-D figures -- the eight preregistered panels (task Sec. 38)."""

from __future__ import annotations

import json
import collections
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "figures" / "phase_m3d"
LAYA = json.loads((REPO / "results/phase_m3d/layer_a/m3d_layer_a_v1.json")
                  .read_text())
GA = json.loads((REPO / "results/phase_m3d/summary/gate_audit_m3d.json")
                .read_text())
AB = REPO / "results/phase_m3d/ablations"
FREEZE = json.loads((REPO / "docs/phase_m3d/M3_D_Benchmark_Freeze.json")
                    .read_text())
LBLV2 = json.loads((REPO / "results/phase_m3d/reference/"
                    "m3d_labels_corrected_v2.json").read_text())

CLS_COLOR = {"WIDEN": "#4C72B0", "SHRINK": "#DD8452", "HOLD": "#55A868",
             "REFERENCE_AMBIGUOUS": "#bbbbbb"}


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / name
    fig.tight_layout()
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("figure:", p.name)


# ---- F1 action-state map -------------------------------------------------- #
def f1():
    lab = {k.rsplit("|", 1)[0].split("_")[-1] + "|" +
           f"{float(k.rsplit('|',1)[1]):g}": v["oracle_action"]
           for k, v in LBLV2["corrected_oracle"].items()}
    cfgs = sorted({k.split("|")[0] for k in lab})
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, c in enumerate(cfgs):
        xs, cs, ss = [], [], []
        for k, act in lab.items():
            cid, s2s = k.split("|")
            if cid != c:
                continue
            xs.append(float(s2s))
            ss.append(28)
            cs.append(CLS_COLOR.get(act, "#999"))
        ax.scatter(xs, [i] * len(xs), c=cs, s=ss, marker="o", edgecolors="k",
                   linewidths=.3)
    ax.set_yticks(range(len(cfgs)), cfgs)
    ax.set_xscale("log")
    ax.set_xlabel(r"$s^2$ of selected component (log scale)")
    ax.axvspan(2.0, 2.5, color="#fff3cd", alpha=.6, zorder=0)
    ax.text(0.62, len(cfgs) - 0.35, "original grid", fontsize=8)
    ax.text(3.0, len(cfgs) - 0.35, "AMENDMENT-1 extension", fontsize=8,
            color="#8a6d00")
    handles = [plt.Line2D([], [], marker="o", ls="", color=v, label=k)
               for k, v in CLS_COLOR.items()]
    ax.legend(handles=handles, ncol=4, fontsize=8, loc="lower right")
    ax.set_title("M3D-1  oracle action across proposal scale "
                 "(104 candidate states)")
    _save(fig, "figure_M3D_01_action_state_map.png")


# ---- F2 gradient CI vs oracle action -------------------------------------- #
def f2():
    recs = LAYA["records"]
    fig, ax = plt.subplots(figsize=(7, 4))
    order = ["WIDEN", "SHRINK", "HOLD"]
    rng = np.random.default_rng(7)
    for i, cls in enumerate(order):
        rs = [r for r in recs if r["oracle_action"] == cls]
        y = i + rng.uniform(-0.16, 0.16, size=len(rs))
        gh = np.array([r["gradient"]["g_hat"] for r in rs])
        lo = gh - np.array([r["gradient"]["g_ci_low"] for r in rs])
        hi = np.array([r["gradient"]["g_ci_high"] for r in rs]) - gh
        cols = ["#2a7" if r["metrics"]["action_correct"] else "#c44"
                for r in rs]
        ax.errorbar(gh, y, xerr=[lo, hi], fmt="none", ecolor="#888",
                    elinewidth=.6, capsize=1.2, alpha=.6)
        ax.scatter(gh, y, c=cols, s=10, alpha=.85)
    ax.set_yticks(range(3), order)
    ax.axvline(0, color="k", lw=.8, ls="--")
    ax.set_xlabel(r"$\hat g_k$  (negative => widening beneficial)")
    ax.set_title("M3D-2  gradient estimate & 95% CI vs oracle action\n"
                 "(green = deployed action correct)")
    _save(fig, "figure_M3D_02_gradient_ci_vs_oracle.png")


# ---- F3 confusion matrix --------------------------------------------------- #
def f3():
    conf = GA["gates"]["M3D_2_adaptive_action_accuracy"]["confusion_matrix"]
    classes = ["WIDEN", "SHRINK", "HOLD"]
    M = np.array([[conf[t][p] for p in classes] for t in classes])
    fig, ax = plt.subplots(figsize=(4.6, 4))
    im = ax.imshow(M, cmap="Blues")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(M[i, j]), ha="center", va="center",
                    color="white" if M[i, j] > M.max() / 2 else "black",
                    fontweight="bold")
    ax.set_xticks(range(3), classes, rotation=20)
    ax.set_yticks(range(3), classes)
    ax.set_xlabel("deployed GRADIENT action")
    ax.set_ylabel("ORACLE action")
    ax.set_title(f"M3D-3  confusion (Acc3="
                 f"{GA['gates']['M3D_2_adaptive_action_accuracy']['acc3']:.3f})")
    fig.colorbar(im, fraction=.046)
    _save(fig, "figure_M3D_03_confusion_matrix.png")


# ---- F4 aggregate ratios ---------------------------------------------------- #
def f4():
    d3 = GA["gates"]["M3D_3_beat_best_fixed_rule"]
    items = [("GRADIENT", d3["GRADIENT_aggregate"]),
             ("ALWAYS_WIDEN", d3["aggregate_by_rule"]["ALWAYS_WIDEN"]),
             ("ALWAYS_SHRINK", d3["aggregate_by_rule"]["ALWAYS_SHRINK"]),
             ("ALWAYS_HOLD", d3["aggregate_by_rule"]["ALWAYS_HOLD"])]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    names, vals = zip(*items)
    bars = ax.bar(names, vals,
                  color=["#444", "#DD8452", "#4C72B0", "#999"])
    ax.axhline(1.0, color="k", lw=.8)
    ax.set_ylabel("M2(rule)/M2(BASE)\nmedian of per-state seed medians")
    for b, (n, v) in zip(bars, items):
        ax.text(b.get_x() + b.get_width() / 2, v + .003, f"{v:.4f}",
                ha="center", fontsize=9)
    ax.set_ylim(min(vals) * .985, max(vals) * 1.012)
    ax.set_title("M3D-4  aggregate vs BASE (best fixed = "
                 f"{d3['BEST_FIXED_rule']}, R_fixed="
                 f"{d3['R_fixed_median_state_seed_medians']:.4f})")
    _save(fig, "figure_M3D_04_grad_vs_fixed_rules.png")


# ---- F5 regret ---------------------------------------------------------------- #
def f5():
    reg = np.array([r["metrics"]["regret_M2"] for r in LAYA["records"]])
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.hist(reg[reg <= 0.001], bins=np.linspace(-.12, 0, 13),
            label="<=0 (at-oracle)", color="#55A868")
    ax.hist(np.clip(reg[reg > 0.001], None, 0.30), bins=np.linspace(0, .3, 26),
            label=">0 positive regret", color="#c44", alpha=.85)
    ax.axvline(float(np.median(reg)), color="k", lw=1.2, ls="--",
               label=f"median={np.median(reg):.3f}")
    ax.set_xlabel(r"$R_{M2}=$ M2(GRADIENT)/M2(ORACLE)-1   (clipped at .3)")
    ax.set_ylabel("# trials")
    ax.legend(fontsize=8)
    ax.set_title("M3D-5  oracle regret distribution (192 trials)")
    _save(fig, "figure_M3D_05_regret.png")


# ---- F6 per-class performance ------------------------------------------------- #
def f6():
    der = json.loads((AB / "derived_report_tables.json").read_text())
    da = der["d_a_gradient_vs_fixed_per_class"]
    recs = LAYA["records"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=False)
    for ax, cls in zip(axes, ["WIDEN", "SHRINK", "HOLD"]):
        rs = [r for r in recs if r["oracle_action"] == cls]
        box = {
            "GRADIENT": [r["arms"]["gradient"]["M2"] / r["arms"]["hold"]["M2"]
                         for r in rs],
            "AW": [r["arms"]["widen"]["M2"] / r["arms"]["hold"]["M2"]
                   for r in rs],
            "AS": [r["arms"]["shrink"]["M2"] / r["arms"]["hold"]["M2"]
                   for r in rs],
            "AH": [1.0] * len(rs)}
        ax.boxplot(box.values(), tick_labels=box.keys(), showfliers=False)
        ax.axhline(1.0, color="k", lw=.7)
        m = da[cls]["GRADIENT"]["median_ratio_to_BASE"]
        ax.set_title(f"{cls}: grad/BASE={m:.3f}", fontsize=10)
    fig.suptitle("M3D-6  per-class performance (ratio to BASE arm)")
    _save(fig, "figure_M3D_06_per_class.png")


# ---- F7 ESS vs correctness ----------------------------------------------------- #
def f7():
    db = json.loads((AB / "derived_report_tables.json").read_text())[
        "d_b_ess_grad_stratification"]["buckets"]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    labels_b = [f"[{lo:g},{hi:g})" if hi != float('inf') else f">={lo:g}"
                for lo, hi, *_ in [(b['ess_bucket'][0], b['ess_bucket'][1],
                                    ) for b in db]]
    rates = [b["action_correct_rate"] for b in db]
    ns = [b["n_trials"] for b in db]
    ax.bar(labels_b, rates, color="#4C72B0")
    for i, (r_, n_) in enumerate(zip(rates, ns)):
        ax.text(i, r_ + .01, f"{r_:.2f}\nn={n_}", ha="center", fontsize=8)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("deployed-action-correct rate")
    ax.set_xlabel("ESS_grad bucket")
    ax.set_title("M3D-7  ESS_grad vs directional correctness")
    _save(fig, "figure_M3D_07_ess_vs_correctness.png")


# ---- F8 budget VRF --------------------------------------------------------------- #
def f8():
    vrf = np.array([r["metrics"]["VRF_budget"] for r in LAYA["records"]])
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.hist(vrf, bins=36, color="#4C72B0", alpha=.85)
    med = float(np.median(vrf))
    ax.axvline(1.0, color="k", lw=1.2, label="crude MC boundary = 1")
    ax.axvline(med, color="#c44", lw=1.4, ls="--",
               label=f"median={med:.4f}")
    ax.set_xlabel("deployable budget-adjusted VRF (GRADIENT path)")
    ax.set_ylabel("# trials")
    ax.legend(fontsize=8)
    verdict = GA["gates"]["STRONG_budget_adjusted_vrf"]["verdict"]
    ax.set_title(f"M3D-8  budget VRF — Strong gate: {verdict}")
    _save(fig, "figure_M3D_08_budget_vrf.png")


if __name__ == "__main__":
    f1(); f2(); f3(); f4(); f5(); f6(); f7(); f8()
    print("all 8 figures written")
