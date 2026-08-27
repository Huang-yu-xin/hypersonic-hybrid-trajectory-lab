"""M3-BV -- required benchmark diagnostics figures (task Sec. 20).

BV-1  W/B/S reference M2 curves over proposal scale s2
BV-2  action-class map over (config, s2)
BV-3  reference direction-margin distribution
BV-4  headline-budget action stability (selected states)
BV-5  HOLD indifference stability
BV-6  Oracle vs best-fixed per-state M2 ratio
BV-7  Oracle adaptive headroom by class
BV-8  selected 24-state class/config coverage

All inputs benchmark-only; controller runs = 0.  Outputs to
figures/phase_m3bv/ (untracked per repo policy).
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
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
ANALYSIS = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_analysis.json"
OUT = REPO / "figures" / "phase_m3bv"

C = ["#1f77b4", "#ff7f0e", "#2ca02c"]   # base / widen / shrink


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    stab = json.loads(STAB.read_text(encoding="utf-8"))
    ana = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    ref = pool["reference_fields"]
    OUT.mkdir(parents=True, exist_ok=True)

    CLS_COLOR = {"WIDEN": "#d62728", "SHRINK": "#1f77b4", "HOLD": "#2ca02c"}

    # ---- BV-1: reference M2 curves over s2 (per config, 3 arms) ----
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    s2s = pool["s2_grid_bv"]
    for cid in pool["frozen_configs"]:
        xs = [float(s2) for s2 in s2s]
        ys = {a: [] for a in ("base", "widen", "shrink")}
        for s2 in s2s:
            key = f"{cid}|{s2}"
            if key not in ref:
                continue
            for a in ys:
                ys[a].append(ref[key]["arms"][a]["M2"])
        for a, col in zip(("base", "widen", "shrink"), C):
            ax.plot(xs, ys[a], color=col, alpha=0.35 if a != "base" else 0.8,
                    lw=1.0)
    ax.set_xscale("log"); ax.set_xticks(s2s)
    ax.set_xticklabels([f"{s:g}" for s in s2s], rotation=45, fontsize=7)
    ax.set_xlabel("proposal scale $s_2$")
    ax.set_ylabel("reference $M_2$ (500k/arm)")
    ax.set_title("BV-1  reference $M_2$ over proposal scale (88 candidates)")
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV1_ref_M2_curves.png", dpi=150)
    plt.close(fig)

    # ---- BV-2: action-class map over (config, s2) ----
    fig, ax = plt.subplots(figsize=(10, 4.2))
    labels = np.full((len(pool["frozen_configs"]), len(s2s)), "", dtype=object)
    for i, cid in enumerate(pool["frozen_configs"]):
        for j, s2 in enumerate(s2s):
            key = f"{cid}|{s2}"
            if key not in ref:
                continue
            cls = ref[key]["oracle"]["oracle_action"]
            labels[i, j] = cls if cls != "REFERENCE_AMBIGUOUS" else "AMB"
            if cls in CLS_COLOR:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                           color=CLS_COLOR[cls], alpha=0.85))
    sel_by_class = ana["selection"]
    sel_keys = {(s["config_id"], s["s2"]): cls
                for cls, lst in sel_by_class.items() for s in lst}
    for i, cid in enumerate(pool["frozen_configs"]):
        for j, s2 in enumerate(s2s):
            if (cid, float(s2)) in sel_keys:
                ax.text(j, i, "S", ha="center", va="center", fontsize=8,
                        fontweight="bold", color="black")
    ax.set_xticks(range(len(s2s)))
    ax.set_xticklabels([f"{s:g}" for s in s2s], rotation=45, fontsize=8)
    ax.set_yticks(range(len(pool["frozen_configs"])))
    ax.set_yticklabels([c.split("_")[-1] for c in pool["frozen_configs"]],
                       fontsize=8)
    ax.set_xlabel("$s_2$"); ax.set_ylabel("event config")
    ax.set_title("BV-2  reference action class over (config, $s_2$)  [S = selected]")
    ax.set_xlim(-0.6, len(s2s) - 0.4); ax.set_ylim(-0.6, len(pool["frozen_configs"]) - 0.4)
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV2_class_map.png", dpi=150)
    plt.close(fig)

    # ---- BV-3: reference direction-margin distribution ----
    fig, ax = plt.subplots(figsize=(8, 5))
    cls_margins = {"WIDEN": [], "SHRINK": [], "HOLD": []}
    for key, r in ref.items():
        cl = r["oracle"]["oracle_action"]
        m = r["oracle"].get("direction_margin_Delta_dir")
        if cl in cls_margins and m is not None:
            cls_margins[cl].append(m)
    for cl, col in CLS_COLOR.items():
        xs = cls_margins[cl]
        ax.hist(xs, bins=24, alpha=0.45, color=col, label=cl + f"  (n={len(xs)})")
    ax.axvline(0.05, color="k", ls="--", lw=1, label="eligibility floor 0.05")
    ax.set_xlabel("reference direction margin $\\Delta_{dir}$")
    ax.set_ylabel("candidate count")
    ax.set_title("BV-3  reference margin distribution by class")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV3_margin_dist.png", dpi=150)
    plt.close(fig)

    # ---- BV-4: headline action stability (selected states) ----
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, cls in zip(axes, ("WIDEN", "SHRINK", "HOLD")):
        rows = []
        for s in ana["selection"][cls]:
            key = f"{s['config_id']}|{s['s2']}"
            st = stab["entries"][key]["stability"]
            if cls == "WIDEN":
                rows.append(st["fraction_widen_best"])
            elif cls == "SHRINK":
                rows.append(st["fraction_shrink_best"])
            else:
                rows.append(st["fraction_hold_indiff"])
        ax.bar(range(len(rows)), rows, color=CLS_COLOR[cls])
        ax.axhline(0.8, color="k", ls="--", lw=0.8)
        ax.set_title(f"{cls} (n={len(rows)})", fontsize=10)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("state idx (sorted)")
    axes[0].set_ylabel("fraction of 8 replicates")
    fig.suptitle("BV-4  headline-budget action stability of selected states "
                 "(floor 0.8)")
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV4_action_stability.png",
                                    dpi=150)
    plt.close(fig)

    # ---- BV-5: HOLD indifference stability (per-replicate |r| vs +-5% band) ----
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for s in ana["selection"]["HOLD"]:
        key = f"{s['config_id']}|{s['s2']}"
        reps = stab["entries"][key]["replicates"]
        for rep in reps:
            rw = abs(rep["ratios_over_base"]["widen_over_base"])
            rs = abs(rep["ratios_over_base"]["shrink_over_base"])
            ax.scatter(rw, rs, s=16, alpha=0.55,
                       color=CLS_COLOR["HOLD"])
    lim = 0.08
    ax.plot([0, lim], [0, lim], "k:", lw=0.8)
    ax.axhline(0.05, color="r", ls="--", lw=1)
    ax.axvline(0.05, color="r", ls="--", lw=1)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("|widen/base - 1| per replicate")
    ax.set_ylabel("|shrink/base - 1| per replicate")
    ax.set_title("BV-5  HOLD indifference at headline budget (red = +-5% band)")
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV5_hold_indifference.png",
                                    dpi=150)
    plt.close(fig)

    # ---- BV-6: Oracle vs best-fixed per-state M2 ratio ----
    bf = ana["oracle_audit"]["bv3"]["best_fixed_policy"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    rows = []
    for k in sorted(ana["oracle_audit"]["state_audit"]):
        sa = ana["oracle_audit"]["state_audit"][k]
        r = sa["replicate_ratios"][bf]
        rows.append((sa["class"], k, r))
    x = 0
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        for _, k, r in rows:
            if _.startswith(cls):
                ax.scatter(x, np.median(r), s=30,
                           color=CLS_COLOR[cls], zorder=3)
                ax.vlines(x, np.min(r), np.max(r),
                          color=CLS_COLOR[cls], alpha=0.4)
                x += 1
    ax.axhline(1.0, color="k", lw=1)
    ax.axhline(0.95, color="r", ls="--", lw=1,
               label="BV-3 gate 0.95")
    ax.set_xticks([])
    ax.set_ylabel("per-state median $M_2(Oracle)/M_2(BestFixed={})$".format(
        bf.replace("ALWAYS_", "")))
    ax.set_title("BV-6  Oracle vs best-fixed per-state ratio "
                 "(med + replicate range)")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV6_oracle_ratios.png",
                                    dpi=150)
    plt.close(fig)

    # ---- BV-7: Oracle headroom by class ----
    fig, ax = plt.subplots(figsize=(7, 5))
    data = {cls: [] for cls in ("WIDEN", "SHRINK", "HOLD")}
    for k in ana["oracle_audit"]["state_audit"]:
        sa = ana["oracle_audit"]["state_audit"][k]
        data[sa["class"]].append(sa["replicate_ratios"][bf])
    bp = []
    for i, cls in enumerate(("WIDEN", "SHRINK", "HOLD")):
        arr = np.asarray(data[cls], dtype=float).ravel()
        q1, med, q3 = np.percentile(arr, [25, 50, 75])
        lo, hi = float(arr.min()), float(arr.max())
        bp.append((i, lo, q1, med, q3, hi,
                   CLS_COLOR[cls]))
    for i, lo, q1, med, q3, hi, color in bp:
        ax.vlines(i, lo, hi, color=color, lw=1.2)
        ax.vlines(i, q1, q3, color=color, lw=4.0)
        ax.plot([i - 0.18, i + 0.18], [med, med], color="black", lw=1.2)
    ax.set_xticks(range(3))
    ax.set_xticklabels(("WIDEN", "SHRINK", "HOLD"))
    ax.axhline(1.0, color="k", lw=1)
    ax.axhline(0.95, color="r", ls="--", lw=1)
    ax.set_ylabel(f"$M_2(Oracle)/M_2({bf.replace('ALWAYS_','')})$ "
                  "(per replicate)")
    ax.set_title("BV-7  Oracle adaptive headroom by class (8 replicates)")
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV7_headroom_by_class.png",
                                    dpi=150)
    plt.close(fig)

    # ---- BV-8: selected 24-state class/config coverage ----
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    cmap = np.zeros((len(pool["frozen_configs"]), len(s2s)), dtype=int)
    for cls, lst in ana["selection"].items():
        ci = {"WIDEN": 1, "SHRINK": 2, "HOLD": 3}[cls]
        for s in lst:
            i = pool["frozen_configs"].index(s["config_id"])
            j = s2s.index(float(s["s2"]))
            cmap[i, j] = ci
    im = ax.imshow(cmap, cmap="tab20c", vmin=0, vmax=20)
    ax.set_xticks(range(len(s2s)))
    ax.set_xticklabels([f"{s:g}" for s in s2s], rotation=45, fontsize=8)
    ax.set_yticks(range(len(pool["frozen_configs"])))
    ax.set_yticklabels([c.split("_")[-1] for c in pool["frozen_configs"]],
                       fontsize=8)
    for i in range(cmap.shape[0]):
        for j in range(cmap.shape[1]):
            if cmap[i, j]:
                ax.text(j, i, ["", "W", "S", "H"][cmap[i, j]],
                        ha="center", va="center", color="white",
                        fontsize=9, fontweight="bold")
    ax.set_xlabel("$s_2$"); ax.set_ylabel("event config")
    ax.set_title("BV-8  selected 24 states: class x config coverage "
                 "(4/4/6 configs; <=2 per config)")
    fig.tight_layout(); fig.savefig(OUT / "m3bv_BV8_selected_coverage.png",
                                    dpi=150)
    plt.close(fig)

    print(f"[saved] 8 figures under {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())