"""M3-BV2 figures (task Sec. 28, benchmark part only).

Decision benchmark: D1 W/H/S state map, D2 reference margin/stability,
D3 config coverage.
Value benchmark:    V1 W/S reference M2 curves, V2 fixed-rule tradeoff by
class, V3 Oracle vs BestFixed unified objective, V4 opposite-class regret,
V5 Oracle headroom distribution.

(D4 confusion matrix and V6 captured headroom are controller-evaluation
figures and are intentionally NOT produced here.)

Writes PNGs under figures/phase_m3bv2/.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
DAN = REPO / "results" / "phase_m3bv2" / "decision_analysis.json"
VAN = REPO / "results" / "phase_m3bv2" / "value_analysis.json"
OUT = REPO / "figures" / "phase_m3bv2"

CLASS_COLOR = {"WIDEN": "#1f77b4", "HOLD": "#2ca02c", "SHRINK": "#d62728"}
S2_GRID = [0.65, 0.85, 1.10, 1.40, 1.80, 2.30, 3.00, 4.00, 5.00, 6.40, 8.00]


def save(fig, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {OUT.name}/{name}")


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    dan = json.loads(DAN.read_text(encoding="utf-8"))
    van = json.loads(VAN.read_text(encoding="utf-8"))
    configs = pool["frozen_configs"]

    # ---------------- D1: W/H/S state map over the (config, s2) grid ------
    sel = {}
    for fs in dan["selection"].items():
        cls, lst = fs
        for s in lst:
            sel[(s["config_id"], s["s2"])] = cls
    fig, ax = plt.subplots(figsize=(11, 4.6))
    y = np.arange(len(configs))
    for ix, cid in enumerate(configs):
        for jx, s2 in enumerate(S2_GRID):
            cls = sel.get((cid, s2))
            color = "#e8e8e8" if cls is None else CLASS_COLOR[cls]
            ax.add_patch(plt.Rectangle((jx - .5, ix - .5), 1, 1,
                                       facecolor=color, edgecolor="white"))
            ax.text(jx, ix, f"{s2:g}", ha="center", va="center", fontsize=7,
                    color="#555" if cls is None else "white")
    ax.set_xticks(range(len(S2_GRID)), [f"{s:g}" for s in S2_GRID])
    ax.set_yticks(y, [c.split("_")[-1] for c in configs])
    ax.set_xlabel("scalar s2")
    ax.set_title("D1 — Decision benchmark W/H/S state map "
                 "(8W/8H/8S selected)")
    for cls, c in CLASS_COLOR.items():
        ax.scatter([], [], color=c, label=cls)
    ax.legend(loc="upper right", ncol=3)
    save(fig, "BV2-D1_whs_state_map.png")

    # ---------------- D2: reference margin vs headline stability -----------
    fig, ax = plt.subplots(figsize=(7.4, 5))
    for fs in dan["freeze_selection"]:
        m = fs["margin_Delta_dir"]
        ax.scatter(m if m is not None else 0.0,
                   fs["stability_fraction"],
                   color=CLASS_COLOR[fs["class"]], s=70, zorder=3)
        ax.annotate(f"{fs['state_key']['config_id'].split('_')[-1]}"
                    f"@{fs['state_key']['s2']:g}",
                    (m if m is not None else 0.0, fs["stability_fraction"]),
                    fontsize=6, xytext=(4, 3),
                    textcoords="offset points", color="#333")
    ax.axhline(0.8, color="grey", ls="--", lw=1)
    ax.set_xlabel("reference direction margin  Δ_dir")
    ax.set_ylabel("headline stability fraction")
    ax.set_title("D2 — decision states: margin vs stability")
    save(fig, "BV2-D2_margin_stability.png")

    # ---------------- D3: config coverage -----------------------------------
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    classes = ("WIDEN", "HOLD", "SHRINK")
    x = np.arange(len(configs))
    w = 0.26
    for i, cls in enumerate(classes):
        counts = [dan["coverage"][cls]["per_config"].get(cid, 0)
                  for cid in configs]
        ax.bar(x + (i - 1) * w, counts, w, label=cls,
               color=CLASS_COLOR[cls])
    ax.set_xticks(x, [c.split("_")[-1] for c in configs])
    ax.axhline(2, color="grey", ls="--", lw=1)
    ax.set_ylabel("states per config")
    ax.set_title("D3 — decision benchmark config coverage "
                 "(>=4 configs/class, <=2 per config)")
    ax.legend()
    save(fig, "BV2-D3_config_coverage.png")

    # ---------------- V1: reference M2 curves (selected value states) ------
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for fs in van["freeze_selection"]:
        m2 = fs["reference_median_M2"]
        base = m2["base"]
        ws = (m2["widen"] - base) / base
        ss = (m2["shrink"] - base) / base
        ax.plot([0, 1], [ws, ss], "-o", ms=4, lw=1,
                color=CLASS_COLOR[fs["class"]], alpha=.75)
    ax.axhline(0, color="grey", lw=1)
    ax.set_xticks([0, 1], ["WIDEN arm", "SHRINK arm"])
    ax.set_ylabel("(M2 - M2(BASE)) / M2(BASE)")
    ax.set_title("V1 — value states: reference M2 of W/S arms relative "
                 "to BASE")
    for cls, c in CLASS_COLOR.items():
        ax.scatter([], [], color=c, label=cls)
    ax.legend(loc="lower right")
    save(fig, "BV2-V1_reference_m2_curves.png")

    # ---------------- V2: fixed-rule tradeoff by class ---------------------
    t = van["fixed_rule_tradeoff_V1"]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    fixeds = ["ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD"]
    x = np.arange(3)
    for i, cls in enumerate(("WIDEN", "SHRINK")):
        vals = [t["class_conditional_J"][cls][f] for f in fixeds]
        ax.bar(x + i * .3, vals, .28, label=f"{cls} class",
               color=CLASS_COLOR[cls])
    ax.set_xticks(x + .15, ["WIDEN", "SHRINK", "HOLD"])
    ax.axhline(0, color="grey", lw=1)
    ax.set_ylabel("class-conditional J(f) = median log M2(f)/M2(BASE)")
    ax.set_title("V2 — fixed-rule tradeoff by class "
                 f"(best per class: {t['best_fixed_per_class']})")
    ax.legend()
    save(fig, "BV2-V2_fixed_rule_tradeoff.png")

    # ---------------- V3: Oracle vs BestFixed unified objective ------------
    uf = van["unified_functional"]
    order = ["ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD", "ORACLE"]
    labels = ["WIDEN", "SHRINK", "HOLD", "Oracle"]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    x4 = np.arange(4)
    vals = [uf["J"][p] for p in order]
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#333333"]
    ax.bar(x4, vals, .55, color=colors)
    ax.axhline(0, color="grey", lw=1)
    ax.set_xticks(x4, labels)
    ax.set_ylabel("J(π) = median_state median_rep log M2(π)/M2(BASE)")
    ax.set_title(f"V3 — Oracle vs BestFixed (BestFixed = {uf['best_fixed']},"
                 f"\nG_Oracle = {uf['G_Oracle']:.4f} ≥ −log(0.95) = "
                 f"{uf['threshold_minus_log095']:.4f})")
    save(fig, "BV2-V3_oracle_vs_bestfixed.png")

    # ---------------- V4: opposite-class regret -----------------------------
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    rw = van["opposite_class_regret_V3"]["R_opp_W"]
    rs = van["opposite_class_regret_V3"]["R_opp_S"]
    for fs in van["freeze_selection"]:
        m2 = fs["replicate_M2"]
        n = len(m2["base"])
        if fs["class"] == "WIDEN":
            r = np.median([m2["shrink"][i] / m2["widen"][i]
                           for i in range(n)])
            ax.scatter(0, r, color=CLASS_COLOR["SHRINK"], s=70)
        else:
            r = np.median([m2["widen"][i] / m2["shrink"][i]
                           for i in range(n)])
            ax.scatter(1, r, color=CLASS_COLOR["WIDEN"], s=70)
    ax.axhline(1.05, color="grey", ls="--", lw=1)
    ax.text(0, 1.05, "threshold 1.05", fontsize=8, va="bottom",
            ha="center")
    ax.set_xticks([0, 1], ["R_opp,W  (on W states:\nM2(SHRINK)/M2(WIDEN))",
                           "R_opp,S  (on S states:\nM2(WIDEN)/M2(SHRINK))"])
    ax.set_ylim(0.8, None)
    ax.set_ylabel("paired M2 ratio (median over replicates)")
    ax.set_title(f"V4 — opposite-class regret "
                 f"(R_opp,W = {rw:.3f}, R_opp,S = {rs:.3f}; both >= 1.05)")
    save(fig, "BV2-V4_opposite_class_regret.png")

    # ---------------- V5: Oracle headroom distribution -----------------------
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    bf = uf["best_fixed"]
    b_arm = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "base"}[bf]
    ref_arm = {"WIDEN": "widen", "SHRINK": "shrink"}
    ratios = []
    for fs in van["freeze_selection"]:
        m2 = fs["replicate_M2"]
        n = len(m2["base"])
        ratios.append(np.median([m2[ref_arm[fs["class"]]][i] /
                                 m2[b_arm][i] for i in range(n)]))
    ax.hist(ratios, bins=12, color="#4472c4", edgecolor="white")
    ax.axvline(0.95, color="red", ls="--", lw=1.5)
    ax.text(0.95, ax.get_ylim()[1] * .95, "gate 0.95", color="red",
            fontsize=9, ha="right", va="top")
    ax.set_xlabel(f"per-state median-replicate M2(Oracle)/M2(BestFixed="
                  f"{bf})")
    ax.set_ylabel("state count")
    ax.set_title("V5 — Oracle headroom distribution over the 24 value "
                 "states")
    save(fig, "BV2-V5_oracle_headroom_distribution.png")

    # ---------------- D4: controller confusion matrix (Axis A) --------------
    ce = json.loads((REPO / "results" / "phase_m3bv2"
                     / "controller_evaluation.json").read_text(encoding="utf-8"))
    axis_a = ce["axis_a"]["M3-G-v1"]
    cm = axis_a["confusion_matrix"]
    classes = ["WIDEN", "HOLD", "SHRINK"]
    M = np.array([[cm[t][p] for p in classes] for t in classes])
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(M, cmap="Blues")
    ax.set_xticks(range(3), classes)
    ax.set_yticks(range(3), classes)
    ax.set_xlabel("predicted (M3-G-v1 deployed action)")
    ax.set_ylabel("frozen reference label")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{M[i, j]}\n({M[i, j] / M[i].sum():.0%})",
                    ha="center", va="center",
                    color="white" if M[i, j] > M.max() / 2 else "black")
    ax.set_title(f"D4 — M3-G-v1 decision confusion matrix (Axis A, "
                 f"{axis_a['n_decisions']} decisions)\n"
                 f"balanced accuracy {axis_a['balanced_accuracy']:.3f} · "
                 f"macro-F1 {axis_a['macro_F1']:.3f}")
    save(fig, "BV2-D4_confusion_matrix.png")

    # ---------------- V6: M3-G-v1 captured headroom (Axis B) ----------------
    ufc = ce["unified_functional"]
    order = [ufc["best_fixed"], "M3-G-v1", "ORACLE"]
    labels = [f"BestFixed\n({ufc['best_fixed']})", "M3-G-v1", "Oracle"]
    jmap = {ufc["best_fixed"]: ufc["J_BestFixed"],
            "M3-G-v1": ufc["J_M3-G-v1"],
            "ORACLE": ufc["J_Oracle"]}
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    x3 = np.arange(3)
    vals = [jmap[o] for o in order]
    colors = ["#b0b0b0", "#4472c4", "#333333"]
    ax.bar(x3, vals, .5, color=colors)
    ax.axhline(0, color="grey", lw=1)
    ax.set_xticks(x3, labels)
    ax.set_ylabel("J(π) = median_state median_rep log M2(π)/M2(BASE)")
    ax.set_title(f"V6 — M3-G-v1 captured headroom\n"
                 f"G_Oracle = {ufc['G_Oracle']:.4f} · "
                 f"G_v1 = {ufc['G_v1']:.4f} · "
                 f"Capture = {ufc['capture_v1']:.1%} "
                 f"(gate: >= 50% and J(v1) < J(BestFixed))")
    save(fig, "BV2-V6_captured_headroom.png")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())