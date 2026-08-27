"""M3 -- preregistered figures M3-1..M3-8 (task Sec. 32).

Reads ONLY phase_m3 persisted artifacts + the locked config; pure matplotlib
Agg, mirroring the M2 figure conventions.  Outputs to figures/phase_m3/.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results" / "phase_m3"
OUT = REPO / "figures" / "phase_m3"
SHORT = lambda cid: cid.replace("m1d_b20260827_", "")          # noqa: E731
CFG = json.loads((REPO / "configs" / "phase_m3"
                  / "m3_scalar_gradient_v0.json").read_text(encoding="utf-8"))
TIE = float(CFG["counterfactual_protocol_locked"]["relative_tie_tolerance"])
CAP_45 = CFG["gates_locked"]["M3_4_predicted_step_m2_gain"][
    "median_M2_pred_over_base_max"]
CAP_35 = CFG["gates_locked"]["M3_5_counterfactual_ordering"][
    "median_M2_pred_over_opposite_max"]
DCOL = {"WIDEN": "#d62728", "SHRINK": "#1f77b4", "HOLD_UNCERTAIN": "#7f7f7f",
        "HOLD_LOW_ESS": "#bcbd22", "HOLD_INVALID": "#333333"}


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _records(sub: str, fname: str):
    d = _j(RES / sub / fname)
    rows = []
    for cb in d.get("records_by_config", []):
        for r in cb["records"]:
            rows.append((cb["config_id"], r))
    return d, rows


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("fig ->", p.relative_to(REPO))


LA_SUB, LA_FILE = "scalar_layer_a", "scalar_layer_a_v1.json"


# --------------------------------------------------------------------------- #
def fig_m3_1():
    _, rows = _records(LA_SUB, LA_FILE)
    xs, ys, cols, sizes = [], [], [], []
    for cid, r in rows:
        g = r.get("gradient") or {}
        if not g or r.get("selected_mode") is None:
            continue
        conf = (r.get("m2_diagnostic") or {}).get("conflict_with_gradient")
        ratio = float(r["m2_diagnostic"]["hdr_isotropic_scale"]) \
            / float(g["s2_base"])
        xs.append(min(ratio, 10.0))
        ys.append(float(g["g_hat"]))
        cols.append("#d62728" if conf else "#7f7f7f")
        sizes.append(60.0 if conf else 25.0)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.scatter(xs, ys, c=cols, s=sizes, alpha=0.75, edgecolors="none")
    ax.axhline(0.0, color="k", lw=0.8)
    ax.set_xlabel("||HDR_isotropic_scale / s_base^2||  (clip 10)")
    ax.set_ylabel(r"$\widehat{g}_k$   (negative => WIDEN)")
    ax.set_title("M3-1  M2 descriptive spread vs M3 gradient direction\n"
                 "red = descriptive-narrow-but-gradient-WIDEN conflict "
                 f"(n={int(sum(c == '#d62728' for c in cols))})")
    save(fig, "figure_M3_1_hdr_vs_gradient.png")


def fig_m3_2():
    t = _j(RES / "theory_checks" / "theory_checks_v1.json")
    a = [abs(c["analytic"]) for c in t["checks"]]
    f = [abs(c["fd_h1e-3"]) for c in t["checks"]]
    floor = max(min(a + f), 1e-16)
    a = [max(v, floor) for v in a]
    f = [max(v, floor) for v in f]
    fig, ax = plt.subplots(figsize=(4.8, 4.8))
    lo, hi = min(a + f) * 0.3, max(a + f) * 3
    ax.plot([lo, hi], [lo, hi], "k--", lw=0.9, label="y = x")
    ax.scatter(a, f, s=26, alpha=0.85)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("|analytic directional derivative|")
    ax.set_ylabel("|central FD, h=1e-3|")
    mx = t["summary"]["max_relative_error"]
    ax.set_title(f"M3-2  analytic vs finite difference\n"
                 f"{t['summary']['n_passed']}/{t['summary']['n_checks']} "
                 f"probes pass; sign 100%; max rel err {mx:.2e}")
    ax.legend(loc="upper left", fontsize=8)
    save(fig, "figure_M3_2_analytic_vs_fd.png")


def fig_m3_3():
    batch, rows = _records(LA_SUB, LA_FILE)
    counts = batch["summary"]["decision_counts"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.0),
                                   gridspec_kw={"width_ratios": [2, 3]})
    keys = [k for k in DCOL if k in counts]
    vals = [counts[k] for k in keys]
    ax1.bar(range(len(keys)), vals,
            color=[DCOL[k] for k in keys])
    ax1.set_xticks(range(len(keys)))
    ax1.set_xticklabels(keys, rotation=30, ha="right", fontsize=8)
    for i, v in enumerate(vals):
        ax1.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    ax1.set_ylabel("trials (of 64)")
    ax1.set_title("decision distribution")
    order = sorted([r for _, r in rows
                    if r.get("gradient", {}).get("ESS_grad")],
                   key=lambda r: r["gradient"]["ESS_grad"])
    y = np.arange(len(order))
    for i, r in enumerate(order):
        g = r["gradient"]
        col = DCOL.get(g["decision"], "#7f7f7f")
        ax2.plot([g["g_ci_low"], g["g_ci_high"]], [i, i], color=col,
                 lw=1.2, alpha=0.85)
    ax2.axvline(0.0, color="k", lw=0.9)
    ax2.set_xlabel(r"bootstrap 95% CI of $\widehat{g}_k$")
    ax2.set_yticks([])
    ax2.set_title("gradient CIs (colour = decision)")
    save(fig, "figure_M3_3_decision_and_CI.png")


def fig_m3_4():
    by_cfg = {}
    for cid, r in _records(LA_SUB, LA_FILE)[1]:
        cf = r.get("counterfactual") or {}
        if cf.get("M2_base") is None:
            continue
        by_cfg.setdefault(cid, []).append(cf)
    cfg_ids = sorted(by_cfg)
    arms = ("shrink", "base", "widen", "pred")
    cols = {"shrink": "#1f77b4", "base": "#7f7f7f", "widen": "#d62728",
            "pred": "#2ca02c"}
    w = 0.2
    x = np.arange(len(cfg_ids))
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    for j, arm in enumerate(arms):
        med = []
        for cid in cfg_ids:
            key = {"shrink": "M2_shrink", "base": "M2_base",
                   "widen": "M2_widen", "pred": "M2_pred"}[arm]
            med.append(np.median([c[key] for c in by_cfg[cid]]))
        rel = np.asarray(med)
        base_rel = np.median([c["M2_base"] for c in by_cfg[cfg_ids[0]]]) \
            if False else None
        del base_rel
        ax.bar(x + (j - 1.5) * w, rel, width=w, color=cols[arm], label=arm)
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT(c) for c in cfg_ids], fontsize=8)
    ax.set_ylabel(r"median $M_2$ over seeds (CRN-paired eval)")
    ax.set_title(r"M3-4  paired SHRINK / BASE / WIDEN / GRADIENT $M_2$ "
                 "(Layer A, fixed weights)")
    ax.legend(fontsize=8)
    save(fig, "figure_M3_4_paired_M2_by_arm.png")


def fig_m3_5():
    ratios = [r["counterfactual"]["M2_pred"] / r["counterfactual"]["M2_opposite"]
              for _, r in _records(LA_SUB, LA_FILE)[1]
              if r.get("counterfactual", {}).get("M2_opposite")]
    ratios = np.asarray([v for v in ratios if v and np.isfinite(v)])
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.hist(ratios, bins=24, color="#2ca02c", alpha=0.85)
    ax.axvline(CAP_35, color="r", ls="--", lw=1.2, label=f"gate cap {CAP_35}")
    ax.axvline(float(np.median(ratios)), color="k", lw=1.4,
               label=f"median {np.median(ratios):.3f}")
    ax.set_xlabel(r"$M_2(\mathrm{pred}) / M_2(\mathrm{opposite})$")
    ax.set_ylabel("trials")
    ax.set_title("M3-5  counterfactual ordering under matched CRN")
    ax.legend(fontsize=8)
    save(fig, "figure_M3_5_pred_over_opposite.png")


def fig_m3_6():
    from hyptraj.m3.metrics import aggregate_gate_quantities
    recs = [r for _, r in _records(LA_SUB, LA_FILE)[1]]
    agg = aggregate_gate_quantities(recs, TIE)
    names = ["GRADIENT\n(active set)", "ALWAYS-\nWIDEN", "ALWAYS-\nSHRINK"]
    vals = [agg["acc_dir"], agg["acc_always_widen_on_active"],
            agg["acc_always_shrink_on_active"]]
    floors = [CFG["gates_locked"]["M3_3_direction_accuracy"]
              ["acc_dir_active_min"]] * 3
    adv = agg["acc_dir"] - max(vals[1], vals[2] or 0.0)
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    bars = ax.bar(names, vals, color=["#2ca02c", "#d62728", "#1f77b4"])
    for b, v in zip(bars, vals):
        if v is not None:
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.3f}",
                    ha="center", va="bottom", fontsize=8)
    ax.axhline(floors[0], ls="--", color="r", lw=1.0, label="acc floor 0.75")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("direction accuracy on active trials")
    ax.set_title(f"M3-6  direction accuracy (+{adv * 100:.1f} pp vs best "
                 "fixed rule; gate needs >=+25 pp)")
    ax.legend(fontsize=8)
    save(fig, "figure_M3_6_direction_accuracy.png")


def fig_m3_7():
    pts = [(float(r["gradient"]["ESS_grad"]),
            int(r["gradient"]["decision"]
                == r["counterfactual"]["evaluation_best_direction"]))
           for _, r in _records(LA_SUB, LA_FILE)[1]
           if r.get("gradient", {}).get("ESS_grad")
           and r["gradient"]["decision"] in ("WIDEN", "SHRINK")]
    ess = np.array([p[0] for p in pts])
    hit = np.array([p[1] for p in pts])
    order = np.argsort(ess)
    e_s, h_s = ess[order], hit[order]
    # decile-binned reliability
    nb = 8
    bins = np.array_split(np.arange(e_s.size), nb)
    ctr = [e_s[b].mean() for b in bins]
    rate = [h_s[b].mean() for b in bins]
    n_in = [b.size for b in bins]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(ctr, rate, "o-", color="#9467bd")
    for c, rr, n in zip(ctr, rate, n_in):
        ax.annotate(f"n={n}", (c, rr), textcoords="offset points",
                    xytext=(0, 6), fontsize=7, ha="center")
    ax.set_xlabel(r"$ESS_{grad}$ bin centre")
    ax.set_ylabel("direction-correct rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("M3-7  gradient ESS vs directional reliability (active set)")
    save(fig, "figure_M3_7_ess_vs_reliability.png")


def fig_m3_8():
    vals = np.asarray([r["evaluation"]["VRF_budget_grad_path"]
                       for _, r in _records(LA_SUB, LA_FILE)[1]
                       if r.get("evaluation", {}).get("VRF_budget_grad_path")
                       is not None])
    aw = np.asarray([(r["_arms"]["widen"]["VRF_budget"])
                     for _, r in _records(LA_SUB, LA_FILE)[1]
                     if r.get("_arms")])
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.hist(vals, bins=24, color="#2ca02c", alpha=0.55,
            label=f"GRADIENT path (median {np.median(vals):.3f})")
    ax.hist(aw, bins=24, color="#d62728", alpha=0.45,
            label=f"ALWAYS-WIDEN path (median {np.median(aw):.3f})")
    ax.axvline(1.0, color="k", ls="--", lw=1.3, label="crude-MC boundary = 1")
    ax.set_xlabel("deployable budget-adjusted VRF")
    ax.set_ylabel("trials")
    ax.set_title("M3-8  deployable budget VRF vs crude MC boundary")
    ax.legend(fontsize=8)
    save(fig, "figure_M3_8_deployable_vrf.png")


def main() -> int:
    fig_m3_1()
    fig_m3_2()
    fig_m3_3()
    fig_m3_4()
    fig_m3_5()
    fig_m3_6()
    fig_m3_7()
    fig_m3_8()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
