"""M1-D -- preregistered figures D1..D8 (task Sec. 39).

Reads only frozen benchmark + experiment batch artifacts; pure matplotlib
Agg.  Outputs to figures/phase_m1d/.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results" / "phase_m1d"
FREEZE = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"
OUT = REPO / "figures" / "phase_m1d"
MISSING = ("S2", "S3", "S4")
CFG_SHORT = lambda cid: cid.replace("m1d_b20260827_", "")
C_VAR, C_PROB, C_RND, C_OP, C_OV = "#1f77b4", "#d62728", "#7f7f7f", "#ff7f0e", "#2ca02c"


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _batch(path: Path):
    d = _j(path)
    rows = []
    for cb in d["records_by_config"]:
        for r in cb["records"]:
            rows.append((cb["config_id"], r))
    return d, rows


def _trials_by_method(batch_rows):
    out = defaultdict(list)
    for cid, r in batch_rows:
        out[r["method"]].append((cid, r))
    return out


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("fig ->", p.relative_to(REPO))


def main() -> int:
    fr = _j(FREEZE)
    cfgs = fr["benchmark_configs"]
    _, A = _batch(RES / "d1_selection_only" / "layer_a_one_birth_v1.json")
    _, B = _batch(RES / "d1_full_policy" / "layer_b_one_birth_v1.json")
    _, A2 = _batch(RES / "d2_two_birth" / "layer_a_two_birth_v1.json")
    _, B2 = _batch(RES / "d2_two_birth" / "layer_b_two_birth_v1.json")
    TA, TB = _trials_by_method(A), _trials_by_method(B)
    TA2, TB2 = _trials_by_method(A2), _trials_by_method(B2)

    # ---------------- Figure D1 -------------------------------------------
    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    colors = {"S2": "#1f77b4", "S3": "#ff7f0e", "S4": "#9467bd"}
    for c in cfgs:
        m = c["modes"]
        for mid in MISSING:
            x, y = m[mid]["P_ref"], m[mid]["L_ref"]
            scale = 22 * min(m[mid]["raw_count"], 1e9) ** 0  # fixed size
            ax.scatter(x, y, s=42 + 0 * scale, alpha=0.85,
                       color=colors[mid], edgecolor="k", linewidth=.4,
                       label=mid if c is cfgs[0] else None)
            off = max(y, 1e-4) * 1.25
            ax.annotate(CFG_SHORT(c["config_id"])[1:], (x, off),
                        fontsize=5.2, rotation=90, alpha=.55,
                        ha="center", va="bottom")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.axvline(0, color="0.8", lw=.6); ax.axhline(0, color="0.8", lw=.6)
    ax.set_xlabel(r"$P_k^{ref}$ (mode probability)")
    ax.set_ylabel(r"$L_k^{ref}(q_0)$ (leakage mass)")
    ax.set_title("Figure D1 — probability vs variance geometry of the "
                 "24 missing modes\n(top-right corner = estimator-critical; "
                 "labels below points = config index)", fontsize=10)
    ax.legend(title="mode", fontsize=8)
    ax.grid(alpha=.25, which="both")
    save(fig, "figure_D1_probability_vs_variance_ranking.png")

    # ---------------- Figure D2 -------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    M = len(cfgs)
    rp = np.zeros((M, 3)); rl = np.zeros((M, 3))
    for i, c in enumerate(cfgs):
        e = c["eligibility"]
        for j, mid in enumerate(MISSING):
            rp[i, j] = e["rank_P"][mid]
            rl[i, j] = e["rank_L"][mid]
    im0 = axes[0].imshow(rp, cmap="Blues_r", vmin=1, vmax=3)
    im1 = axes[1].imshow(rl, cmap="Reds_r", vmin=1, vmax=3)
    for ax_, im_, t_ in ((axes[0], im0, r"$r^P$ rank of $P^{ref}_k$"),
                         (axes[1], im1, r"$r^V$ rank of $L^{ref}_k(q_0)$")):
        ax_.set_xticks(range(3), MISSING)
        ax_.set_yticks(range(M), [CFG_SHORT(c["config_id"])
                                  for c in cfgs])
        ax_.set_title(t_, fontsize=10)
        for i in range(M):
            for j in range(3):
                v = im_.get_array()[i, j]
                ax_.text(j, i, f"{int(v)}", ha="center", va="center",
                         color="w", fontsize=9)
    inv_txt = ", ".join(f"{CFG_SHORT(c['config_id'])[1:]}:"
                        f"{len(c['eligibility']['pairwise_inversions'])}"
                        for c in cfgs)
    fig.suptitle("Figure D2 — ranking conflict heatmap (pairwise inversion "
                 f"counts per config: {inv_txt})", fontsize=10.5)
    save(fig, "figure_D2_ranking_conflict_heatmap.png")

    # ---------------- Figure D3 -------------------------------------------
    methods = ["variance_selector", "probability_selector",
               "random_selector", "oracle_P", "oracle_V"]
    cols = [C_VAR, C_PROB, C_RND, C_OP, C_OV]
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    xs = np.arange(len(methods))
    glob_acc = []
    per_cfg_acc = []
    for meth in methods:
        by_cfg = defaultdict(list)
        n_tot = n_cor = 0
        for cid, r in TA[meth]:
            ok = int(bool(r["selection_metrics"]["top1_variance_correct"]))
            by_cfg[cid].append(ok)
            n_tot += 1
            n_cor += ok
        assert n_tot == 64, (meth, n_tot)
        glob_acc.append(n_cor / n_tot)
        per_cfg_acc.append([np.mean(v) for v in by_cfg.values()])
    for x, acc_list, col in zip(xs, per_cfg_acc, cols):
        jitter = (np.random.default_rng(11).random(len(acc_list)) - .5) * .18
        ax.scatter(x * 1 + jitter, acc_list, s=16, color=col, alpha=.55,
                   zorder=2)
    ax.bar(xs, glob_acc, width=.62, color=[c + "" for c in cols],
           alpha=.78, zorder=1, edgecolor="k", linewidth=.5)
    for x, g in zip(xs, glob_acc):
        ax.text(x, g + .02, f"{g:.3f}", ha="center", fontsize=9,
                fontweight="bold")
    ax.axhline(.75, ls="--", color="crimson", lw=1.1)
    ax.text(len(methods) - .45, .762, "Gate D2 ≥ 75%", color="crimson",
            fontsize=8)
    ax.set_xticks(xs, ["Variance\nselector", "Probability\nselector",
                       "Random", "Oracle-P", "Oracle-V"], fontsize=9)
    ax.set_ylim(0, 1.06); ax.set_ylabel("Acc $V@1$ (selected $=k_V^*$)")
    ax.set_title("Figure D3 — top-1 variance-critical selection accuracy "
                 "(Layer A one-birth; bars global, dots per-config)",
                 fontsize=10)
    ax.grid(axis="y", alpha=.3)
    save(fig, "figure_D3_top1_selection_accuracy.png")

    # ---------------- helper: paired value maps ---------------------------
    def valmap(trials, metric):
        out = {}
        for cid, r in trials:
            sm, ev = r["selection_metrics"], r["evaluation"]
            v = sm.get(metric) if metric.startswith(("CVS", "CPS")) \
                else ev.get(metric)
            out[(cid, r["seed"])] = float(
                v.get(metric) if isinstance(v, dict) else v) \
                if v is not None else np.nan
        return out

    cvs_map = lambda trs: {(cid, r["seed"]):
                           r["selection_metrics"]["captured_variance_share"]
                           for cid, r in trs}
    m2_map = lambda trs: {(cid, r["seed"]): r["evaluation"]["M2_hat"]
                          for cid, r in trs}

    # ---------------- Figure D4 -------------------------------------------
    data = {m: list(cvs_map(TA[m]).values()) for m in methods}
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    bp = ax.boxplot([data[m] for m in methods], patch_artist=True,
                    medianprops=dict(color="k"))
    for patch, c in zip(bp["boxes"], cols):
        patch.set_facecolor(c); patch.set_alpha(.75)
    for x, m in zip(range(1, 6), methods):
        y = np.asarray(data[m]) * 1.0
        ax.scatter(np.full(y.size, x) +
                   np.random.default_rng(3).uniform(-.09, .09, y.size),
                   y, s=12, color="k", alpha=.35, zorder=3)
    ax.set_xticklabels(["Variance\nselector", "Probability\nselector",
                        "Random", "Oracle-P", "Oracle-V"], fontsize=9)
    ax.set_ylabel("CVS$_1$ captured variance share")
    med_ratio = np.median(list(cvs_map(TA["variance_selector"]).values()))
    ax.set_title(f"Figure D4 — captured variance share, Layer A one-birth\n"
                 f"(median CVS ratio V/P ≥ gate see audit report; oracle-V "
                 f"median = "
                 f"{np.median(data['oracle_V']):.3f})", fontsize=10)
    ax.grid(axis="y", alpha=.3)
    save(fig, "figure_D4_captured_variance_share.png")

    # ---------------- Figure D5 -------------------------------------------
    mv, mp = m2_map(TA["variance_selector"]), m2_map(TA["probability_selector"])
    keys = sorted(set(mv) & set(mp))
    vals_v = np.array([mv[k] for k in keys])
    vals_p = np.array([mp[k] for k in keys])
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=False)
    ax = axes[0]
    for i, (a, b) in enumerate(zip(vals_v, vals_p)):
        col = "#1f77b4" if a <= b else "#d62728"
        ax.plot([0, 1], [b, a], marker="o", ms=4, alpha=.45, color=col)
        ax.plot([0], [b], "o", ms=4, color="#d62728", alpha=.5)
        ax.plot([1], [a], "o", ms=4, color="#1f77b4", alpha=.5)
    ax.set_xticks([0, 1], ["Probability sel.", "Variance sel."])
    ax.set_yscale("log"); ax.set_xlim(-.28, 1.28)
    med_ratio = np.median(vals_v / vals_p)
    ax.set_title(f"M̂₂ paired slopes (median V/P = {med_ratio:.3f}; "
                 f"gate ≤ 0.90)", fontsize=10)
    ax.grid(alpha=.3)
    ax = axes[1]
    boxdat = [vals_p, vals_v]
    bp = ax.boxplot(boxdat, patch_artist=True, tick_labels=["Prob sel.",
                                                            "Var sel."])
    for patch, c in zip(bp["boxes"], ["#d62728", "#1f77b4"]):
        patch.set_facecolor(c); patch.set_alpha(.72)
    ax.set_yscale("log")
    ax.set_title("M̂₂ distributions (final q, Layer A)", fontsize=10)
    ax.grid(axis="y", alpha=.3)
    fig.suptitle("Figure D5 — second moment by selector (paired by "
                 "(config, seed))", fontsize=11)
    save(fig, "figure_D5_M2_by_selector.png")

    # ---------------- Figure D6 -------------------------------------------
    mv, mp = m2_map(TB["variance_full_policy"]), \
        m2_map(TB["probability_full_policy"])
    keys = sorted(set(mv) & set(mp))
    vv = np.array([mv[k] for k in keys]); pp = np.array([mp[k] for k in keys])
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    for a, b in zip(vv, pp):
        col = "#1f77b4" if a <= b else "#d62728"
        ax.plot([0, 1], [b, a], "-o", ms=4, alpha=.5, color=col)
    med_ratio = float(np.median(vv / pp))
    ax.annotate("", xy=(1.32, np.median(vv)),
                xytext=(1.32, np.median(pp)),
                arrowprops=dict(arrowstyle="<->", color="k"))
    ax.text(1.36, np.sqrt(np.median(vv) * np.median(pp)),
            f"median M̂₂ ratio\n{med_ratio:.3f}\n(gate ≤ 0.90)",
            fontsize=8, va="center")
    ax.set_xticks([0, 1], ["Probability full policy", "M1 variance policy"])
    ax.set_xlim(-.25, 1.95)
    ax.set_yscale("log")
    ax.set_ylabel("M̂₂(q_final)")
    ax.set_title("Figure D6 — full-policy second moment, Layer B one-birth\n"
                 "(frozen gates η-centroid+SLSQP vs π∝P̂ + P-centroid)",
                 fontsize=10)
    ax.grid(alpha=.3)
    save(fig, "figure_D6_full_policy_M2.png")

    # ---------------- Figure D7 -------------------------------------------
    reg = defaultdict(dict)
    om2 = m2_map(TA["oracle_V"]); ocvs = cvs_map(TA["oracle_V"])
    for meth in ("variance_selector", "probability_selector",
                 "random_selector", "oracle_P"):
        mm, cc = m2_map(TA[meth]), cvs_map(TA[meth])
        ks = sorted(set(mm) & set(om2))
        reg["R_M2"][meth] = float(np.median(
            [mm[k] / max(om2[k], 1e-300) - 1 for k in ks]))
        reg["R_CVS"][meth] = float(np.median(
            [1 - cc[k] / max(ocvs[k], 1e-300) for k in ks]))
    ms4 = ["variance_selector", "probability_selector", "random_selector",
           "oracle_P"]
    x = np.arange(len(ms4))
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    for ax, mk, ttl in ((axes[0], "R_CVS", "R_CVS = 1 − CVS/CVS_oracleV"),
                        (axes[1], "R_M2",
                         "R_M2 = M̂₂/M̂₂_oracleV − 1")):
        bars = ax.bar(x, [max(reg[mk][m], 0) for m in ms4],
                      color=[C_VAR, C_PROB, C_RND, C_OP], alpha=.8,
                      edgecolor="k", lw=.5)
        for xi, m in zip(x, ms4):
            ax.text(xi, reg[mk][m] + .008, f"{reg[mk][m]:.3f}",
                    ha="center", fontsize=8)
        ax.set_xticks(x, ["Variance", "Probability", "Random", "Oracle-P"],
                      fontsize=9)
        ax.set_title(ttl, fontsize=10)
        ax.grid(axis="y", alpha=.3)
    fig.suptitle("Figure D7 — selection regret vs Oracle-V "
                 "(Layer A one-birth)", fontsize=11)
    save(fig, "figure_D7_selection_regret.png")

    # ---------------- Figure D8 -------------------------------------------
    def med(trials, get):
        return float(np.median([get(r) for _, r in trials]))

    M2g = lambda r: r["evaluation"]["M2_hat"]
    CVSg = lambda r: r["selection_metrics"]["captured_variance_share"]

    cells = {}
    for tag, (t1, t2) in {"Layer A": (TA, TA2), "Layer B": (TB, TB2)}.items():
        pair = (("variance_selector", "probability_selector")
                if tag == "Layer A"
                else ("variance_full_policy", "probability_full_policy"))
        cells[tag] = {
            "var": (med(t1[pair[0]], M2g), med(t2[pair[0]], M2g)),
            "prob": (med(t1[pair[1]], M2g), med(t2[pair[1]], M2g)),
        }

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.5))
    ax = axes[0]
    b1_vals = [cells["Layer A"]["var"][0], cells["Layer A"]["prob"][0],
               cells["Layer B"]["var"][0], cells["Layer B"]["prob"][0]]
    b2_vals = [cells["Layer A"]["var"][1], cells["Layer A"]["prob"][1],
               cells["Layer B"]["var"][1], cells["Layer B"]["prob"][1]]
    xsr = np.arange(4)
    ax.bar(xsr, b1_vals, width=.62, color="#bbbbbb", edgecolor="k", lw=.5,
           label="B = 1")
    ax.scatter(xsr, b2_vals, marker="_", s=1500, linewidths=2.6,
               color="#d62728", label="B = 2")
    for x, v in zip(xsr, b1_vals):
        ax.text(x + .19, v * 1.03, f"{v:.3f}", fontsize=7, va="bottom")
    ax.set_xticks(xsr, ["Var A", "Prob A", "Var B", "Prob B"])
    ax.set_ylabel(r"median $\hat{M}_2(q_{final})$")
    ax.legend(fontsize=8)
    ax.set_title(r"M$\hat{}_2$: budget tightening B=1 → B=2"
                 "\n(grey bar = B1, red tick = B2)", fontsize=9.5)
    ax.grid(axis="y", alpha=.3)

    ax = axes[1]
    v1 = med(TA["variance_selector"], CVSg)
    p1 = med(TA["probability_selector"], CVSg)
    v2 = med(TA2["variance_selector"], CVSg)
    p2 = med(TA2["probability_selector"], CVSg)
    gaps = [v1 - p1, v2 - p2]
    bars = ax.bar(["B = 1", "B = 2"], gaps, color=["#1f77b4", "#1f77b4"],
                  alpha=.65, edgecolor="k")
    for b, v in zip(bars, gaps):
        ax.text(b.get_x() + b.get_width() / 2,
                v + (0.012 if v >= 0 else -0.024), f"{v:+.3f}",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    ax.axhline(0, color="k", lw=.7)
    ax.set_title("CVS advantage of variance selector vs birth-budget "
                 "tightness\n(shrinking gap ⇒ probability policy catches up)",
                 fontsize=9.5)
    ax.grid(axis="y", alpha=.3)
    fig.suptitle("Figure D8 — birth-budget effect (D-E ablation; Layers A/B)",
                 fontsize=11)
    save(fig, "figure_D8_birth_budget_effect.png")

    print("[figures] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
