"""M3-G figures (handoff Sec. 24): M3G-1..M3G-8 rendered to
figures/phase_m3g/ from the sealed online batch + stored M3-D records +
calibration payload.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "figures" / "phase_m3g"
ONLINE = json.loads((REPO / "results" / "phase_m3g" / "layer_a"
                     / "m3g_online_v1.json").read_text(encoding="utf-8"))
STORED = json.loads((REPO / "results" / "phase_m3d" / "layer_a"
                     / "m3d_layer_a_v1.json").read_text(encoding="utf-8"))
FREEZE = json.loads((REPO / "docs" / "phase_m3d"
                     / "M3_D_Benchmark_Freeze.json").read_text(
                         encoding="utf-8"))
CAL = json.loads((REPO / "results" / "phase_m3g" / "calibration"
                  / "m3g_calibration_v0.json").read_text(encoding="utf-8"))

CMAP = {"WIDEN": "#d62728", "SHRINK": "#1f77b4", "HOLD": "#2ca02c"}


def main() -> int:
    recs = ONLINE["gated_records"]
    stored = {r["state_id"] + f"|{r['seed']}": r for r in STORED["records"]}
    FIG.mkdir(parents=True, exist_ok=True)

    # ----------------------------- M3G-1 gain proxy by oracle class ------
    fig, ax = plt.subplots(figsize=(9, 5))
    order = ("WIDEN", "SHRINK", "HOLD")
    data = {c: [] for c in order}
    for r in recs:
        p = r["gain"]["gain_proxy_mag"]
        if p is None or not np.isfinite(p):
            continue
        data[r["oracle_action"]].append(np.log10(p))
    xt = []
    for i, c in enumerate(order):
        vals = np.asarray(data[c])
        xt.append(c)
        if vals.size:
            bp = ax.boxplot([vals], positions=[i], widths=0.55,
                            patch_artist=True,
                            boxprops=dict(facecolor=CMAP[c], alpha=0.55))
            ax.scatter(np.full(vals.size, i) + 0.22 * np.random.default_rng(
                1).uniform(-1, 1, vals.size), vals, s=8, alpha=0.35,
                color=CMAP[c])
    ax.axhline(np.log10(0.0025), color="black", ls="--", lw=1,
               label=r"$\rho=0.0025$ (log10)")
    ax.set_xticks(range(3), order)
    ax.set_xlabel("oracle class")
    ax.set_ylabel(r"$\log_{10}|\widehat{\Delta}_{rel}|$")
    ax.set_title("M3G-1  gain proxy by oracle class (online, GA2 locked)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "m3g1_gain_proxy_by_class.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-2 calibration rho sweep -----------
    fig, ax = plt.subplots(figsize=(9, 5))
    rhos = CAL["rho_grid"]
    for var in ("GA1", "GA2"):
        acc = [CAL["table"][f"{var}-{r}"]["accuracy"] for r in rhos]
        rH = [CAL["table"][f"{var}-{r}"]["recall_per_class"]["HOLD"]
              for r in rhos]
        ax.plot(rhos, acc, marker="o", label=f"{var} acc3")
        ax.plot(rhos, rH, marker="s", ls="--",
                label=f"{var} HOLD recall")
    base = CAL["table"]["baseline_M3-D"]
    ax.axhline(base["accuracy"], color="gray", ls=":", lw=1,
               label=f"baseline acc3 = {base['accuracy']:.3f}")
    ax.axhline(base["recall_per_class"]["HOLD"], color="gray", ls=":",
               lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel(r"$\rho$ (log scale)")
    ax.set_ylabel("fraction")
    ax.set_title("M3G-2  calibration rho sweep (stored Layer-A, zero sims)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "m3g2_calibration_rho_sweep.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-3 confusion matrices ---------------
    def conf_matrix(recs_source, pred_key):
        cm = np.zeros((3, 3), int)
        for r in recs_source:
            t = r["oracle_action"]
            if pred_key == "gate":
                p = r["gain"]["final_action"]
            else:
                p = r["validity"]["deployed_action"]
            cm[order.index(t), order.index(p)] += 1
        return cm

    cm_gate = conf_matrix(recs, "gate")
    cm_m3d = conf_matrix(ONLINE["gated_records"], "deployed")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, cm, title in ((axes[0], cm_m3d, "M3-D baseline"),
                          (axes[1], cm_gate, "M3-G (GA2, rho=0.0025)")):
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(3), order)
        ax.set_yticks(range(3), order)
        ax.set_xlabel("predicted")
        ax.set_ylabel("oracle")
        ax.set_title(title)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("M3G-3  confusion matrices (192 paired trials)")
    fig.tight_layout()
    fig.savefig(FIG / "m3g3_confusion_matrices.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-4 HOLD recall recovery -------------
    fig, ax = plt.subplots(figsize=(7, 5))
    rH_m3d = sum(1 for r in STORED["records"]
                 if r["validity"]["deployed_action"] == "HOLD"
                 and r["oracle_action"] == "HOLD") / 64.0
    rH_gate = sum(1 for r in recs
                  if r["gain"]["final_action"] == "HOLD"
                  and r["oracle_action"] == "HOLD") / 64.0
    bars = ax.bar(["M3-D baseline", "M3-G (GA2, 0.0025)"],
                  [rH_m3d, rH_gate], color=["#888888", "#2ca02c"])
    ax.axhline(0.70, color="red", ls="--", lw=1, label="M3G-2 floor 0.70")
    ax.set_ylim(0, 1)
    ax.set_ylabel("HOLD recall")
    ax.set_title("M3G-4  HOLD recall recovery")
    ax.legend()
    for b, v in zip(bars, (rH_m3d, rH_gate)):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}",
                ha="center")
    fig.tight_layout()
    fig.savefig(FIG / "m3g4_hold_recall_recovery.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-5 per-state M2 ----------------------
    by_state = {}
    for r in recs:
        sid = r["state_id"]
        s2 = r["base_s2"]
        row = by_state.setdefault(sid, {"s2": s2, "gate": [], "m3d": [],
                                        "best_fixed": [], "oracle": []})
        sr = stored[sid + f"|{r['seed']}"]
        row["gate"].append(float(r["arms"]["gate"]["M2"]))
        row["m3d"].append(float(sr["arms"]["gradient"]["M2"]))
        row["oracle"].append(float(sr["arms"]["oracle"]["M2"]))
        bf = min(float(sr["arms"]["widen"]["M2"]),
                 float(sr["arms"]["shrink"]["M2"]),
                 float(sr["arms"]["hold"]["M2"]))
        row["best_fixed"].append(bf)
    states = sorted(by_state)
    fig, ax = plt.subplots(figsize=(13, 5))
    x = np.arange(len(states))
    w = 0.2
    for off, key, col in ((-1.5, "m3d", "#888888"), (-0.5, "gate", "#2ca02c"),
                          (0.5, "best_fixed", "#ff7f0e"),
                          (1.5, "oracle", "black")):
        meds = [float(np.median(by_state[s][key])) for s in states]
        ax.bar(x + off * w, meds, w, label=key, color=col,
               alpha=0.85 if key != "oracle" else 1.0)
    ax.set_xticks(x, [s.split("_s2_")[1] for s in states], rotation=90,
                  fontsize=7)
    ax.set_ylabel("M2 (per-state seed median)")
    ax.legend(fontsize=8, ncol=4)
    ax.set_title("M3G-5  per-state M2: M3-D / M3-G / best fixed / oracle")
    fig.tight_layout()
    fig.savefig(FIG / "m3g5_per_state_m2.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-6 false-HOLD analysis ---------------
    fig, ax = plt.subplots(figsize=(9, 5))
    fhw = sum(1 for r in recs if r["gain"]["final_action"] == "HOLD"
              and r["oracle_action"] == "WIDEN") / 64.0
    fhs = sum(1 for r in recs if r["gain"]["final_action"] == "HOLD"
              and r["oracle_action"] == "SHRINK") / 64.0
    hg = [r for r in recs if r["gain"]["gain_hold_reason"] == "HOLD_GAIN"]
    hg_correct = sum(1 for r in hg if r["oracle_action"] == "HOLD")
    ax.bar(["false-HOLD on WIDEN", "false-HOLD on SHRINK"], [fhw, fhs],
           color=["#d62728", "#1f77b4"])
    ax.set_ylabel("rate over the oracle class")
    ax.set_ylim(0, 0.3)
    ax2 = ax.twinx()
    ax2.bar(["HOLD_GAIN correct", "HOLD_GAIN wrong"],
            [hg_correct, len(hg) - hg_correct], color=["#2ca02c", "#cccccc"],
            alpha=0.6)
    ax2.set_ylabel("HOLD_GAIN trials")
    ax.set_title(f"M3G-6  false-HOLD rates & HOLD_GAIN disposition "
                 f"(n_hg={len(hg)})")
    fig.tight_layout()
    fig.savefig(FIG / "m3g6_false_hold_analysis.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-7 proxy vs realized gain ------------
    fig, ax = plt.subplots(figsize=(8, 5.5))
    xs, ys, cols = [], [], []
    for r in recs:
        if r["gain"]["final_action"] not in ("WIDEN", "SHRINK"):
            continue
        arm = "widen" if r["gain"]["final_action"] == "WIDEN" else "shrink"
        realized = (float(r["arms"][arm]["M2"]) - float(r["arms"]["hold"]["M2"])
                    ) / float(r["arms"]["hold"]["M2"])
        xs.append(r["gain"]["gain_proxy_mag"])
        ys.append(realized)
        cols.append(CMAP[r["oracle_action"]])
    ax.scatter(np.asarray(xs), np.asarray(ys), c=cols, s=14, alpha=0.6)
    ax.set_xscale("log")
    ax.axvline(0.0025, color="black", ls="--", lw=1,
               label=r"$\rho=0.0025$")
    ax.axhline(0.0, color="gray", lw=0.8)
    hs = [plt.Line2D([0], [0], marker="o", ls="", color=CMAP[c])
          for c in order]
    ax.legend(handles=hs, labels=order, fontsize=8)
    ax.set_xlabel(r"$|\widehat{\Delta}_{rel}|$ (proxy)")
    ax.set_ylabel("realized relative M2 change of acted arm")
    ax.set_title("M3G-7  gain proxy vs realized finite-step improvement")
    fig.tight_layout()
    fig.savefig(FIG / "m3g7_proxy_vs_realized.png", dpi=150)
    plt.close(fig)

    # ----------------------------- M3G-8 VRF_budget, MC boundary 1 ---------
    fig, ax = plt.subplots(figsize=(8, 5))
    vrf_by_state = {}
    for r in recs:
        v = r["metrics"]["VRF_budget"]
        if v is not None and np.isfinite(v):
            vrf_by_state.setdefault(r["state_id"], []).append(v)
    states = sorted(vrf_by_state)
    data = [np.asarray(vrf_by_state[s]) for s in states]
    ax.boxplot(data, positions=np.arange(len(states)), widths=0.6,
               showfliers=False, patch_artist=True,
               boxprops=dict(facecolor="#9ecae1", alpha=0.8))
    ax.axhline(1.0, color="red", ls="--", lw=1.2,
               label="MC boundary (VRF=1)")
    ax.axhline(float(np.median([v for vs in data for v in vs])),
               color="black", ls=":", lw=1,
               label="global median (deployable)")
    ax.set_xticks(np.arange(len(states)),
                  [s.split("_s2_")[1] for s in states], rotation=90,
                  fontsize=7)
    ax.set_ylabel("VRF_budget (M3-G gate arm)")
    ax.legend(fontsize=8)
    ax.set_title("M3G-8  VRF_budget per state with MC boundary = 1")
    fig.tight_layout()
    fig.savefig(FIG / "m3g8_vrf_budget.png", dpi=150)
    plt.close(fig)

    print(f"[saved] 8 figures under {FIG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())