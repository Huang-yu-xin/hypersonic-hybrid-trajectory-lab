"""M3-G-v1 figures (task Sec. 24): 8 figures rendered to
figures/phase_m3g_v1/ from the 192-trial confirmatory batch + gate audit.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "figures" / "phase_m3g_v1"
BATCH = json.loads((REPO / "results" / "phase_m3g_v1" / "layer_a"
                    / "m3g_v1_confirmatory_v1.json").read_text(
                        encoding="utf-8"))
AUDIT = json.loads((REPO / "results" / "phase_m3g_v1" / "summary"
                    / "gate_audit_m3g_v1.json").read_text(encoding="utf-8"))
REPLAY = json.loads((REPO / "results" / "phase_m3g" / "summary"
                     / "exact_proxy_calibration_replay.json").read_text(
                         encoding="utf-8"))

ORDER = ("WIDEN", "SHRINK", "HOLD")
CMAP = {"WIDEN": "#d62728", "SHRINK": "#1f77b4", "HOLD": "#2ca02c"}


def main() -> int:
    recs = BATCH["gated_records"]
    FIG.mkdir(parents=True, exist_ok=True)

    # ---------------- 1. v1 vs M3-D confusion matrix on new seeds --------
    def cm(pred_key):
        mat = np.zeros((3, 3), int)
        for r in recs:
            t = r["oracle_action"]
            p = (r["gain"]["final_action"] if pred_key == "gate"
                 else ("WIDEN" if r["gradient"]["action"] == "WIDEN"
                       else "SHRINK" if r["gradient"]["action"] == "SHRINK"
                       else "HOLD"))
            mat[ORDER.index(t), ORDER.index(p)] += 1
        return mat

    cm_gate, cm_m3d = cm("gate"), cm("m3d")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, mat, title in ((axes[0], cm_m3d, "M3-D baseline (same seeds)"),
                           (axes[1], cm_gate, "M3-G-v1 GA1/0.02")):
        im = ax.imshow(mat, cmap="Blues")
        ax.set_xticks(range(3), ORDER)
        ax.set_yticks(range(3), ORDER)
        ax.set_xlabel("predicted")
        ax.set_ylabel("oracle")
        ax.set_title(title)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, mat[i, j], ha="center", va="center",
                        color="white" if mat[i, j] > mat.max() / 2
                        else "black")
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("v1 confusion matrices (192 confirmatory trials, "
                 "seeds 3031..3038)")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_1_confusion_matrices.png", dpi=150)
    plt.close(fig)

    # ---------------- 2. HOLD recall: discovery vs confirmatory ----------
    rec_disc = REPLAY["table"]["GA1-0.02"]["recall_per_class"]["HOLD"]
    rec_conf = AUDIT["gates"]["V1_2_hold_recovery"]["recall_hold_v1"]
    rec_base = AUDIT["gates"]["V1_2_hold_recovery"][
        "recall_hold_m3d_same_new_seeds"]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(["M3-D\n(new seeds)", "GA1-0.02 discovery\n(in-sample)",
                   "GA1-0.02 confirmatory\n(unseen seeds)"],
                  [rec_base, rec_disc, rec_conf],
                  color=["#888888", "#cccccc", "#2ca02c"])
    ax.axhline(0.70, color="red", ls="--", lw=1, label="V1-2 floor 0.70")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("HOLD recall")
    ax.legend()
    for b, v in zip(bars, (rec_base, rec_disc, rec_conf)):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}",
                ha="center")
    ax.set_title("v1 HOLD recall: discovery candidate vs confirmatory "
                 "replication")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_2_hold_recall_replication.png", dpi=150)
    plt.close(fig)

    # ---------------- 3. GA1 proxy by oracle class (confirmatory) --------
    fig, ax = plt.subplots(figsize=(9, 5))
    data = {c: [] for c in ORDER}
    for r in recs:
        p = r["gain"]["gain_proxy"]
        if p is None or not np.isfinite(p):
            continue
        data[r["oracle_action"]].append(np.log10(p))
    for i, c in enumerate(ORDER):
        vals = np.asarray(data[c])
        if vals.size:
            ax.boxplot([vals], positions=[i], widths=0.55, patch_artist=True,
                       boxprops=dict(facecolor=CMAP[c], alpha=0.55))
            ax.scatter(np.full(vals.size, i) + 0.2 * np.random.default_rng(
                1).uniform(-1, 1, vals.size), vals, s=8, alpha=0.35,
                color=CMAP[c])
    ax.axhline(np.log10(0.02), color="black", ls="--", lw=1,
               label=r"$\rho=0.02$ (log10)")
    ax.set_xticks(range(3), ORDER)
    ax.set_xlabel("oracle class")
    ax.set_ylabel(r"$\log_{10}|\widehat{\Delta}_{rel}|$ (pilot M2_hat)")
    ax.set_title("v1 GA1 proxy by oracle class (confirmatory seeds)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_3_gain_proxy_by_class.png", dpi=150)
    plt.close(fig)

    # ---------------- 4. false-HOLD analysis -----------------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    fhw = AUDIT["diagnostics"]["false_hold_rate_on_widen"]
    fhs = AUDIT["diagnostics"]["false_hold_rate_on_shrink"]
    hg = [r for r in recs if r["gain"]["gain_hold_reason"] == "HOLD_GAIN"]
    hg_c = sum(1 for r in hg if r["oracle_action"] == "HOLD")
    ax.bar(["false-HOLD on WIDEN", "false-HOLD on SHRINK"], [fhw, fhs],
           color=["#d62728", "#1f77b4"])
    ax.set_ylabel("rate over the oracle class")
    ax.set_ylim(0, 0.25)
    ax2 = ax.twinx()
    ax2.bar(["HOLD_GAIN correct", "HOLD_GAIN wrong"],
            [hg_c, len(hg) - hg_c], color=["#2ca02c", "#cccccc"], alpha=0.6)
    ax2.set_ylabel("HOLD_GAIN trials")
    ax.set_title(f"v1 false-HOLD rates & HOLD_GAIN disposition "
                 f"(n={len(hg)}, correct={hg_c})")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_4_false_hold_analysis.png", dpi=150)
    plt.close(fig)

    # ---------------- 5. per-state M2 ratios ------------------------------
    by = {}
    for r in recs:
        s = by.setdefault(r["state_id"], {"s2": r["base_s2"], "base": [],
                                          "gate": [], "m3d": []})
        s["base"].append(float(r["arms"]["hold"]["M2"]))
        s["gate"].append(float(r["arms"]["gate"]["M2"]))
        s["m3d"].append(float(r["arms"]["gradient"]["M2"]))
    states = sorted(by)
    fig, ax = plt.subplots(figsize=(13, 5))
    x = np.arange(len(states))
    w = 0.25
    for off, key, col, lab in ((-0.5, "m3d", "#888888", "M3-D"),
                               (0.0, "gate", "#2ca02c", "M3-G-v1"),
                               (0.5, "base", "#ff7f0e", "base arm")):
        meds = [np.median(by[s][key]) for s in states]
        ax.bar(x + off * w, meds, w, label=lab, color=col)
    ax.set_xticks(x, [s.split("_s2_")[1] for s in states], rotation=90,
                  fontsize=7)
    ax.set_ylabel("M2 (per-state seed median)")
    ax.legend(fontsize=8, ncol=3)
    ax.set_title("v1 per-state M2: M3-D / v1 gate / base arm "
                 "(confirmatory seeds)")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_5_per_state_m2.png", dpi=150)
    plt.close(fig)

    # ---------------- 6. v1 vs best fixed ---------------------------------
    bf = AUDIT["gates"]["V1_5_adaptive_value"]["best_fixed_rule"]
    bf_arm = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
              "ALWAYS_HOLD": "hold"}[bf]
    ratio_by = {}
    for r in recs:
        fm = float(r["arms"][bf_arm]["M2"])
        if fm > 0:
            ratio_by.setdefault(r["state_id"], []).append(
                float(r["arms"]["gate"]["M2"]) / fm)
    states = sorted(ratio_by)
    fig, ax = plt.subplots(figsize=(13, 5))
    meds = [np.median(ratio_by[s]) for s in states]
    cols = ["#2ca02c" if m < 1.0 else "#d62728" if m > 1.0 else "#999999"
            for m in meds]
    ax.bar(np.arange(len(states)), meds, color=cols)
    ax.axhline(1.0, color="black", lw=1, ls="--", label="parity with "
               f"best fixed ({bf})")
    ax.axhline(0.95, color="red", lw=1, ls=":", label="V1-5 floor 0.95")
    ax.set_xticks(np.arange(len(states)),
                  [s.split("_s2_")[1] for s in states], rotation=90,
                  fontsize=7)
    ax.set_ylabel("per-state seed-median M2(v1)/M2(best fixed)")
    ax.legend(fontsize=8)
    ax.set_title("v1 vs globally best fixed rule per state")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_6_v1_vs_best_fixed.png", dpi=150)
    plt.close(fig)

    # ---------------- 7. v1 vs oracle regret ------------------------------
    fig, ax = plt.subplots(figsize=(8, 5.5))
    per_cls = {c: [] for c in ORDER}
    for r in recs:
        v = r["metrics"]["regret_M2"]
        if v is not None and np.isfinite(v):
            per_cls[r["oracle_action"]].append(v)
    data = [per_cls[c] for c in ORDER]
    bp = ax.boxplot(data, positions=range(3), widths=0.5,
                    patch_artist=True, showfliers=False)
    for box, c in zip(bp["boxes"], (CMAP[c] for c in ORDER)):
        box.set_facecolor(c)
        box.set_alpha(0.55)
    ax.set_xticks(range(3), ORDER)
    ax.axhline(0.0, color="black", lw=0.8)
    ax.set_ylabel("R_M2 = (M2(v1) - M2(oracle))/M2(oracle)")
    ax.set_title("v1 vs oracle regret by oracle class (confirmatory)")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_7_regret_vs_oracle.png", dpi=150)
    plt.close(fig)

    # ---------------- 8. VRF_budget with MC boundary = 1 ------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    vrf_by = {}
    for r in recs:
        v = r["metrics"]["VRF_budget"]
        if v is not None and np.isfinite(v):
            vrf_by.setdefault(r["state_id"], []).append(v)
    states = sorted(vrf_by)
    ax.boxplot([vrf_by[s] for s in states],
               positions=np.arange(len(states)), widths=0.6,
               showfliers=False, patch_artist=True,
               boxprops=dict(facecolor="#9ecae1", alpha=0.8))
    ax.axhline(1.0, color="red", ls="--", lw=1.2, label="MC boundary (VRF=1)")
    ax.set_xticks(np.arange(len(states)),
                  [s.split("_s2_")[1] for s in states], rotation=90,
                  fontsize=7)
    ax.set_ylabel("VRF_budget (v1 gate arm, deployable)")
    ax.legend(fontsize=8)
    ax.set_title("v1 VRF_budget per state with MC boundary = 1")
    fig.tight_layout()
    fig.savefig(FIG / "m3g_v1_8_vrf_budget.png", dpi=150)
    plt.close(fig)

    print(f"[saved] 8 figures under {FIG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())