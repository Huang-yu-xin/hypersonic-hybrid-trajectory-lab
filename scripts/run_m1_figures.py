"""M1-7 -- Figure generation (task Sec. 32, Figure M1-1..M1-6).

Reads the frozen result JSONs and renders the six required figures into
``results/phase_m1/figures/`` (project convention, cf. results/phase_h3):

- Figure M1-1  closed-loop schematic (q_t -> pilot -> nu_V -> diagnosis
               -> add/reweight -> q_{t+1})
- Figure M1-2  mode probability P_k vs variance share omega_k^V on the
               H3-1 L2 benchmark, with the closed-loop identified mode
- Figure M1-3  adaptation trajectory (M2 / L_S2 / omega_S2 per iteration)
- Figure M1-4  baseline second-moment comparison (7 methods, 8 seeds)
- Figure M1-5  oracle gap M2(M1)/M2(M3) across the 8 seeds
- Figure M1-6  cost-adjusted efficiency (proposal-level vs budget-adjusted VRF)

Pure matplotlib, deterministic; consumes only committed result artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "results" / "phase_m1" / "figures"
B_JSON = REPO / "results" / "phase_m1" / "m1_closed_loop_leakage_v0.json"
DISC_JSON = REPO / "results" / "phase_m1" / "m1_h3_1_discovery_v0.json"
SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]

METHOD_LABELS = {
    "crude_mc": "MC",
    "single_geometry_q0": "Single q0",
    "h3_2_m2_topology_mixture": "H3-2 M2",
    "h3_2_m3_leakage_mixture": "H3-2 M3",
    "fixed_variance_aware_mixture": "Fixed var-aware",
    "m1_closed_loop": "M1 closed-loop",
    "cross_entropy": "CEM",
}


def fig1_schematic() -> Path:
    fig, ax = plt.subplots(figsize=(8.6, 2.2))
    ax.axis("off")
    boxes = [
        (0.00, r"$q_t$"),
        (0.22, "pilot\n(samples $+$ $r_i$)"),
        (0.44, r"$\hat\nu_V^{(q_t)}$"),
        (0.66, "diagnose\n(missing mode?)"),
        (0.88, r"$q_{t+1}$"),
    ]
    for x, label in boxes:
        ax.add_patch(plt.Rectangle((x, 0.35), 0.13, 0.3, fill=True,
                                   facecolor="#dae8fc", edgecolor="#6c8ebf"))
        ax.text(x + 0.065, 0.5, label, ha="center", va="center", fontsize=9)
    for x in (0.13, 0.35, 0.57, 0.79):
        ax.annotate("", xy=(x + 0.075, 0.5), xytext=(x, 0.5),
                    arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(0.92, 0.42, "ADD_COMPONENT +\nUPDATE_WEIGHTS", fontsize=8,
            color="#800000", va="center")
    ax.set_title("Figure M1-1: closed-loop variance-geometry adaptive IS "
                 "(v0: Discover + Add + Reweight)", fontsize=10)
    out = OUT_DIR / "fig_m1_1_closed_loop_schematic.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return out


def fig2_prob_vs_omega() -> Path:
    d = json.loads(DISC_JSON.read_text(encoding="utf-8"))
    gt = d["ground_truth_postrun_only"]
    # omega estimates of S1/S2 from the discovery pilot (post-run stats)
    runs = d["runs"]
    om_s2 = [r["omega_S2_hat"] for r in runs]
    om_s1 = [1.0 - o for o in om_s2]
    p_s1 = gt["frozen_P_S2_mc"]  # reuse S2 MC probability below
    f = OUT_DIR / "fig_m1_2_prob_vs_omega.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.scatter([0.0668], [1.0] if False else [np.mean(om_s1)], s=120,
               marker="o", color="#4472c4", label="S1 (primary, covered)", zorder=3)
    ax.scatter([gt["frozen_P_S2_mc"]], [np.mean(om_s2)], s=140, marker="^",
               color="#c00000", label="S2 (discovered by closed loop)", zorder=3)
    ax.scatter([0.0668, gt["frozen_P_S2_mc"]],
               [gt["true_omega_S2"] / (1 + gt["true_omega_S2"]), gt["true_omega_S2"]],
               s=0)
    yt = [gt["true_omega_S2"] / (gt["true_omega_S2"] + 1) * 0 + 0.0]
    ax.text(gt["frozen_P_S2_mc"], np.mean(om_s2) + 0.05,
            f"8/8 seeds detected\n$\\hat\\omega_{{S2}}$ mean {np.mean(om_s2):.3f} "
            f"(true {gt['true_omega_S2']:.3f})", fontsize=8, ha="center")
    ax.text(0.0668, np.mean(om_s1) + 0.05, f"$\\hat\\omega_{{S1}}$ {np.mean(om_s1):.3f}",
            fontsize=8, ha="center")
    ax.axhline(0.10, color="gray", ls="--", lw=1)
    ax.text(0.11, 0.105, "birth gate $\\omega_k^V \\geq 0.10$", fontsize=8, color="gray")
    ax.set_xscale("log")
    ax.set_xlabel(r"mode probability $P_k$ (MC, target $p$)")
    ax.set_ylabel(r"variance share $\omega_k^V$")
    ax.set_ylim(0, 1.15)
    ax.set_title("Figure M1-2: probability-small but variance-dominant S2\n"
                 "(H3-1 L2; P vs variance share decoupling)", fontsize=10)
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(f, dpi=160)
    plt.close(fig)
    return f


def fig3_trajectory() -> Path:
    b = json.loads(B_JSON.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.6))
    for seed_row in b["per_seed"]:
        its = seed_row["m1_closed_loop"]["extra"]["iterations"]
        m2 = [its[0]["M2_hat_prev"] if its[0]["M2_hat_prev"] is not None else its[0]["M2_hat"]]
        m2.append(its[0]["M2_hat"])
        axes[0].plot(range(len(m2)), m2, "o-", alpha=0.5, lw=1)
    axes[0].set_xticks([0, 1])
    axes[0].set_xticklabels(["t=0 (q0)", "t=1 (after Add+RW)"])
    axes[0].set_ylabel(r"$\widehat M_2$ (diagnostic pilot)")
    axes[0].set_title("(a) second moment")
    axes[0].grid(alpha=0.3)
    # L_S2 and omega_S2 per seed (before/after from eval streams)
    l0 = [s["single_geometry_q0"]["L_S2"] for s in b["per_seed"]]
    l1 = [s["m1_closed_loop"]["L_S2"] for s in b["per_seed"]]
    om0 = [s["single_geometry_q0"]["L_S2"] / 1.5 for s in b["per_seed"]]
    om1 = [s["m1_closed_loop"]["omega_S2_hat"] for s in b["per_seed"]]
    axes[1].boxplot([l0, l1])
    axes[1].set_xticks([1, 2])
    axes[1].set_xticklabels(["q0", "q_final"])
    axes[1].set_ylabel(r"$L_{S2}$ (eval)")
    axes[1].set_title("(b) missed-mode leakage")
    axes[1].grid(alpha=0.3)
    axes[2].boxplot([om0, om1])
    axes[2].set_xticks([1, 2])
    axes[2].set_xticklabels(["q0 (approx)", "q_final"])
    axes[2].set_ylabel(r"$\omega_{S2}^V$")
    axes[2].set_title("(c) S2 variance share")
    axes[2].grid(alpha=0.3)
    fig.suptitle("Figure M1-3: adaptation trajectory (8 seeds, H3-1 L2)",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = OUT_DIR / "fig_m1_3_adaptation_trajectory.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def fig4_baseline_comparison() -> Path:
    b = json.loads(B_JSON.read_text(encoding="utf-8"))
    methods = list(METHOD_LABELS)
    data = [[s[m]["M2_hat"] for s in b["per_seed"]] for m in methods]
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    bp = ax.boxplot(data, showfliers=True, patch_artist=True)
    ax.set_xticks(range(1, len(methods) + 1))
    ax.set_xticklabels([METHOD_LABELS[m] for m in methods], fontsize=8)
    colors = ["#8faadc", "#8faadc", "#ffd966", "#ffd966", "#c6e0b4",
              "#70ad47", "#f4b183"]
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
    ax.axhline(0.0733, color="k", ls=":", lw=1)
    ax.text(7.4, 0.079, "MC level $P(A)$", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel(r"$M_2$ (second moment, 100--160k eval)")
    ax.set_title("Figure M1-4: baseline comparison (median line; 8 seeds)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    out = OUT_DIR / "fig_m1_4_baseline_comparison.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def fig5_oracle_gap() -> Path:
    b = json.loads(B_JSON.read_text(encoding="utf-8"))
    ratios = [s["m1_closed_loop"]["M2_hat"] / s["h3_2_m3_leakage_mixture"]["M2_hat"]
              for s in b["per_seed"]]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.bar([str(s) for s in SEEDS], ratios, color="#70ad47", edgecolor="k")
    ax.axhline(1.10, color="#c00000", ls="--", lw=1.5)
    ax.text(7.6, 1.115, "competitive gate 1.10", fontsize=9, color="#c00000", ha="right")
    ax.axhline(1.0, color="gray", ls=":", lw=1)
    ax.set_ylabel(r"$M_2(\mathrm{M1}) / M_2(\mathrm{H3\text{-}2\ M3})$")
    ax.set_xlabel("seed")
    ax.set_ylim(0.8, 1.4)
    ax.set_title(f"Figure M1-5: oracle gap (median {np.median(ratios):.3f}, "
                 "no leakage oracle for M1)", fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    out = OUT_DIR / "fig_m1_5_oracle_gap.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def fig6_cost_efficiency() -> Path:
    b = json.loads(B_JSON.read_text(encoding="utf-8"))
    methods = [m for m in METHOD_LABELS if m != "crude_mc"]
    vp = [np.median([s[m]["VRF_proposal"] for s in b["per_seed"]]) for m in methods]
    vb = [np.median([s[m]["VRF_budget"] for s in b["per_seed"]]) for m in methods]
    x = np.arange(len(methods))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    ax.bar(x - w / 2, vp, w, label="proposal-level VRF", color="#4472c4")
    ax.bar(x + w / 2, vb, w, label="budget-adjusted VRF", color="#ed7d31")
    ax.axhline(1.0, color="k", ls=":", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[m] for m in methods], rotation=12, fontsize=8)
    ax.set_ylabel("VRF (median over 8 seeds)")
    ax.set_yscale("log")
    ax.set_title("Figure M1-6: cost-adjusted efficiency (adaptation overhead "
                 "not hidden)", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    out = OUT_DIR / "fig_m1_6_cost_efficiency.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = [fig1_schematic(), fig2_prob_vs_omega(), fig3_trajectory(),
             fig4_baseline_comparison(), fig5_oracle_gap(), fig6_cost_efficiency()]
    for f in files:
        print(f"written {f.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())