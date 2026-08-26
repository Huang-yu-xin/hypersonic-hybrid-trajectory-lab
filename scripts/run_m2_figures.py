"""M2 -- preregistered figures M2-1..M2-8 (task Sec. 47).

Reads only phase_m2 result/summary artifacts (+ the frozen benchmark for the
M2-1 pilot overlay); pure matplotlib Agg.  Outputs to figures/phase_m2/.
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
RES = REPO / "results" / "phase_m2"
OUT = REPO / "figures" / "phase_m2"
SHORT = lambda cid: cid.replace("m1d_b20260827_", "")          # noqa: E731
METHODS = ("C0", "C1", "C2", "C3", "C4")
MCOL = {"C0": "#7f7f7f", "C1": "#9467bd", "C2": "#8c564b",
        "C3": "#e377c2", "C4": "#d62728"}
CFG_V0 = json.loads((REPO / "configs" / "phase_m2"
                     / "m2_covariance_v0.json").read_text(encoding="utf-8"))
CFGS = CFG_V0["frozen_configs"]


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _batch(sub: str, fname: str):
    d = _j(RES / sub / fname)
    rows = []
    for cb in d["records_by_config"]:
        for r in cb["records"]:
            rows.append((cb["config_id"], r))
    return d, rows


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print("fig ->", p.relative_to(REPO))


def draw_ellipse(ax, mean, cov, color, label=None):
    from matplotlib.patches import Ellipse
    cov = np.asarray(cov, dtype=float)
    try:
        evals, evecs = np.linalg.eigh(0.5 * (cov + cov.T))
    except np.linalg.LinAlgError:
        return
    order = np.argsort(evals)[::-1]
    evals = evals[order]
    evecs = evecs[:, order]
    ang = np.degrees(np.arctan2(evecs[1, 0], evecs[0, 0]))
    e = Ellipse(xy=list(map(float, mean)),
                width=2 * np.sqrt(max(evals[0], 1e-6)),
                height=2 * np.sqrt(max(evals[1], 1e-6)),
                angle=float(ang), fill=False, color=color, lw=2, alpha=0.55,
                label=label)
    ax.add_patch(e)


def config_median_ratio(rows, method_a: str, method_b: str,
                        value_key: str = "M2_hat"):
    """{config_short: median_seed(M_a)/median_seed(M_b)} plus flat lists."""
    by_cfg_a: dict[str, list] = defaultdict(list)
    by_cfg_b: dict[str, list] = defaultdict(list)
    for cid, r in rows:
        if not r["evaluation"].get(value_key):
            continue
        m = r["covariance_method"]
        if m == method_a:
            by_cfg_a[cid].append(r["evaluation"][value_key])
        elif m == method_b:
            by_cfg_b[cid].append(r["evaluation"][value_key])
    ratios, out = {}, {}
    for cid in CFGS:
        if by_cfg_a.get(cid) and by_cfg_b.get(cid):
            ma = float(np.median(by_cfg_a[cid]))
            mb = float(np.median(by_cfg_b[cid]))
            out[SHORT(cid)] = {"a": ma, "b": mb}
            ratios[cid] = ma / mb if mb else float("nan")
    return ratios, out


def main() -> int:
    _, rows_la = _batch("layer_a_shape_only", "layer_a_shape_only_v1.json")
    _, rows_lb = _batch("layer_b_shape_reweight",
                        "layer_b_shape_reweight_v1.json")
    diag_rows = _j(RES / "summary" / "shape_diagnostics_v1.json")["rows"]
    audit = _j(RES / "summary" / "gate_audit.json")

    active_la = [(c, r) for c, r in rows_la if not r["covariance"]["hold"]]
    print(f"non-HOLD Layer A trials: {len(active_la)}/{len(rows_la)}")

    # ---- Figure M2-1: variance region + covariance ellipses --------------
    from hyptraj.m1d.adaptation import draw_mix_pilot
    from hyptraj.m1d.experiments import config_from_record, load_freeze
    frecs = {x["config_id"]: x for x in load_freeze()["benchmark_configs"]}

    candidates = sorted(
        ((c, r) for c, r in rows_la if not r["covariance"]["hold"]),
        key=lambda cr: -cr[1]["variance_region"]["ess_v"])
    n_panels = min(3, max(1, len(candidates)))
    fig, axes = plt.subplots(1, n_panels, figsize=(4.4 * n_panels + 1, 4.3))
    axes = np.atleast_1d(axes)
    seen_cfgs = set()
    panel = 0
    for cid, rec in candidates:
        if cid in seen_cfgs or panel >= n_panels:
            continue
        seen_cfgs.add(cid)
        bc = config_from_record(frecs[cid])
        seed = int(rec["seed"])
        rng = np.random.default_rng([seed, 101])
        z, logr_, _st = draw_mix_pilot(rng, bc.initial_proposal(), bc.logp,
                                       20000, 0.5)
        labels = bc.label(z)
        logp = bc.logp(z)
        q0 = bc.initial_proposal()
        wv = np.exp(2.0 * logp - q0.log_density(z) - logr_)
        sub_idx = np.flatnonzero(labels == str(rec["selected_mode"]))
        pick = sub_idx[np.argsort(-wv[sub_idx])[:300]]

        ax = axes[panel]
        ax.scatter(z[pick, 0], z[pick, 1],
                   s=4 + 60 * wv[pick] / max(wv[pick].max(), 1e-300),
                   alpha=0.45, color="#1f77b4")
        cen = np.asarray(rec["variance_region"]["centroid"])
        base = np.eye(2)
        draw_ellipse(ax, cen, base, "#444444",
                     "$\\Sigma_{\\mathrm{base}}$")
        draw_ellipse(ax, cen, np.asarray(rec["variance_region"]["cov_raw"]),
                     "#1f77b4", "$C_{\\eta}$ raw")
        draw_ellipse(ax, cen,
                     np.asarray(rec["covariance"]["sigma_final"]),
                     "#d62728", "$\\Sigma$ C4 final")
        ax.scatter([cen[0]], [cen[1]], marker="+", color="black", s=70)
        ess = rec["variance_region"]["ess_v"]
        ax.set_title(f"{SHORT(cid)} s{seed} k={rec['selected_mode']}\n"
                     f"ESS_V={ess:.1f}", fontsize=9)
        panel += 1
    axes[0].legend(loc="upper left", fontsize=7)
    save(fig, "figure_M2_1_variance_region_and_covariance_ellipse.png")

    # ---- Figure M2-2: eigenvalues / anisotropy ---------------------------
    eigs = [np.asarray(r["variance_region"]["eig_raw"], dtype=float)
            for _, r in rows_la if len(r["variance_region"]["eig_raw"]) == 2]
    lmin = np.array([e[-1] for e in eigs])
    lmax = np.array([e[1] for e in eigs]) * 0          # placeholder no-op
    lmax = np.array([e[1] for e in eigs])
    aniso = lmax / (lmin + 1e-12)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.scatter(lmin, lmax, s=14, alpha=0.65, color="#1f77b4")
    lim_hi = float(np.percentile(lmax, 99)) * 1.1 or 1.0
    lim_lo = float(np.percentile(lmin, 99)) * 1.1 or 1.0
    a1.plot([0, min(lim_lo, lim_hi)], [0, min(lim_lo, lim_hi)], "--", lw=1,
            color="#aaaaaa")
    a1.set_xlim(0, lim_lo)
    a1.set_ylim(0, lim_hi)
    a1.set_xlabel("$\\lambda_{\\min}(C_{\\eta})$ raw")
    a1.set_ylabel("$\\lambda_{\\max}(C_{\\eta})$ raw")
    a1.set_title(f"C_eta region eigenvalues ({len(eigs)} trials)")
    a2.hist(np.clip(aniso, 0, 50), bins=40, color="#ff7f0e")
    a2.axvline(float(np.median(aniso)), color="black", lw=1,
               label=f"median {np.median(aniso):.2f}")
    a2.set_xlabel("$A_C=\\lambda_{\\max}/(\\lambda_{\\min}+\\epsilon)$ "
                  "(clipped at 50)")
    a2.legend()
    save(fig, "figure_M2_2_eigenvalue_anisotropy_summary.png")

    # ---- Figure M2-3: M2_hat across C0-C4 --------------------------------
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 7.6), sharex=True)

    def grouped(rows, ax, title):
        xs = np.arange(len(CFGS))
        width = 0.16
        for i, m in enumerate(METHODS):
            vals = []
            for cid in CFGS:
                vs = [r["evaluation"]["M2_hat"] for c, r in rows
                      if c == cid and r["covariance_method"] == m
                      and r["evaluation"].get("M2_hat")]
                vals.append(float(np.median(vs)) if vs else np.nan)
            ax.bar(xs + (i - 2) * width, vals, width=width, color=MCOL[m],
                   label=m)
        ax.set_xticks(xs)
        ax.set_xticklabels([SHORT(c) for c in CFGS], rotation=45,
                           ha="right")
        ax.set_ylabel("median $\\widehat M_2(q)$")
        ax.set_title(title, fontsize=10)

    grouped(rows_la, a1, "Layer A -- shape-only ($\\pi=\\pi_{C0}$ shared)")
    grouped(rows_lb, a2, "Layer B -- shape + frozen SLSQP reweight")
    a2.legend(ncol=5, loc="upper right", fontsize=9)
    save(fig, "figure_M2_3_M2_across_C0_C4.png")

    # ---- Figure M2-4: C4/C0 ratio, both layers ---------------------------
    thr = audit["gates"]["M2_2_core_second_moment"]["threshold_median_ratio_le"]
    fig, axes2 = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, rows, title in ((axes2[0], rows_la, "Layer A (shape-only)"),
                            (axes2[1], rows_lb,
                             "Layer B (+ frozen reweight)")):
        ratios, _pairs = config_median_ratio(rows, "C4", "C0")
        keys = [SHORT(c) for c in CFGS]
        vals = [ratios.get(k, np.nan) for k in keys]
        ax.bar(range(len(keys)), vals, color="#2ca02c", alpha=0.85)
        ax.axhline(1.0, color="black", lw=1)
        ax.axhline(thr, color="#d62728", ls="--", lw=1,
                   label=f"Gate M2-2 threshold {thr}")
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels(keys, rotation=45, ha="right")
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8)
    axes2[0].set_ylabel("median-seed $\\widehat M_2$(C4)/C0 per config")
    g23 = audit["gates"]["M2_3_shape_only"]
    fig.suptitle(f"Layer A global median ratio = "
                 f"{g23['observed']:.4f}  "
                 f"(Gate M2-3: {g23['verdict']})", fontsize=10)
    save(fig, "figure_M2_4_shape_only_vs_reweight.png")

    # ---- Figure M2-5: leakage redistribution -----------------------------
    g24 = audit["gates"]["M2_4_no_leakage_redistribution"]
    off_med = g24["config_median_max_off_target_RL"]
    sel_med = g24["selected_mode_ratio_config_medians"]
    fig, ax = plt.subplots(figsize=(10, 4))
    xs = np.arange(len(CFGS))
    ax.bar(xs - 0.18, [min(off_med.get(c, np.nan), 5.0) for c in CFGS],
           width=0.36, color="#ff7f0e",
           label="median $\\max_{j\\neq sel} R_{L,j}$")
    ax.bar(xs + 0.18, [sel_med.get(c, np.nan) for c in CFGS], width=0.36,
           color="#1f77b4", label="selected-mode $R_L$ median")
    ax.axhline(2.0, color="#d62728", ls="--", lw=1,
               label="catastrophic threshold 2.0")
    ax.set_xticks(xs)
    ax.set_xticklabels([SHORT(c) for c in CFGS], rotation=45, ha="right")
    ax.set_ylabel("leakage ratio C4/C0 (Layer B)")
    ax.legend(fontsize=8)
    save(fig, "figure_M2_5_leakage_redistribution.png")

    # ---- Figure M2-6: budget VRF with MC boundary ------------------------
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))

    def vrf_by_config(ax, title):
        xs = np.arange(len(CFGS))
        width = 0.16
        for i, m in enumerate(METHODS):
            vals = [float(np.median(
                [r["evaluation"]["VRF_budget"] for c, r in rows_lb
                 if c == cid and r["covariance_method"] == m]))
                for cid in CFGS]
            ax.bar(xs + (i - 2) * width, vals, width=width, color=MCOL[m],
                   label=m)
        ax.axhline(1.0, color="black", ls=":", lw=1.2, label="MC boundary = 1")
        ax.set_xticks(xs)
        ax.set_xticklabels([SHORT(c) for c in CFGS], rotation=45, ha="right")
        ax.set_ylabel("median VRF$_{budget}$")
        ax.set_title(title, fontsize=10)

    vrf_by_config(a1, "Layer B VRF_budget per config")
    med = [float(np.median([r["evaluation"]["VRF_budget"] for _, r in rows_lb
                            if r["covariance_method"] == m]))
           for m in METHODS]
    a2.bar(list(METHODS), med, color=[MCOL[m] for m in METHODS])
    a2.axhline(1.0, color="black", ls=":", lw=1.2)
    for i, v in enumerate(med):
        a2.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    a2.set_ylim(0, max(med + [1.0]) * 1.3)
    a2.set_title("Global medians (Layer B)", fontsize=10)
    g25 = audit["gates"]["M2_5_relative_budget_efficiency"]
    strong = audit["gates"]["STRONG_absolute_efficiency"]
    a2.text(0.02, 0.96,
            f"M2-5: {g25['verdict']}; Strong gate: {strong['verdict']}",
            transform=a2.transAxes, va="top", fontsize=8, color="#333333")
    save(fig, "figure_M2_6_budget_vrf.png")

    # ---- Figure M2-7: ESS vs covariance gain -----------------------------
    lb_map = {(c, int(r["seed"]), r["covariance_method"]): r
              for c, r in rows_lb}
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    n_held = n_act = 0
    for (c, s, m), r4 in lb_map.items():
        if m != "C4":
            continue
        r0 = lb_map.get((c, s, "C0"))
        if not r0 or not r0["evaluation"].get("M2_hat"):
            continue
        ess = float(r4["variance_region"]["ess_v"])
        gain = r4["evaluation"]["M2_hat"] / r0["evaluation"]["M2_hat"]
        held = bool(r4["covariance"]["hold"])
        n_held += held
        n_act += (not held)
        ax.scatter(ess, gain, s=26, marker="x" if held else "o",
                   color="#d62728" if held else "#2ca02c", alpha=0.85)
    ax.axhline(1.0, color="black", lw=1)
    ax.axvline(20.0, color="#888888", ls="--", lw=1, label="ESS threshold 20")
    ax.set_xscale("log")
    ax.set_xlabel("ESS$_V$ region (log scale)")
    ax.set_ylabel("paired $\\widehat M_2$(C4)/$\\widehat M_2$(C0)")
    handles = [plt.Line2D([], [], marker="o", ls="", color="#2ca02c",
                          label=f"active C4 (n={n_act})"),
               plt.Line2D([], [], marker="x", ls="", color="#d62728",
                          label=f"HOLD => C0 (n={n_held})"),
               plt.Line2D([], [], ls="--", color="#888888",
                          label="ESS = 20")]
    ax.legend(handles=handles, fontsize=8)
    btab = audit["summary_tables"]["ablation_F_ess_band_gain_layer_B_C4"]
    band_txt = "; ".join(
        f"{b}: n={v['n_trials']}, med={v['median_ratio']}"
        for b, v in sorted(btab.items()) if v.get("n_trials"))
    ax.set_title(f"Ablation F -- ESS bands (Layer B): {band_txt}", fontsize=8)
    save(fig, "figure_M2_7_ess_vs_covariance_gain.png")

    # ---- Figure M2-8: lambda sensitivity ---------------------------------
    lam_summary = audit["summary_tables"]["lambda_sensitivity"]

    def lam_med(layer_prefix: str, lam: float):
        entry = next((v for k, v in lam_summary.items()
                      if k.startswith(f"{layer_prefix}@λ={lam:g}")), None)
        return entry["median_of_config_medians"] if entry else None

    lams = (0.25, 0.75)
    main_obs_A = audit["gates"]["M2_3_shape_only"]["observed"]
    main_obs_B = audit["gates"]["M2_2_core_second_moment"]["observed"]
    xs_a = [lam_med("layer_A", l) for l in lams]
    xs_b = [lam_med("layer_B", l) for l in lams]

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.plot([0.25, 0.50, 0.75],
            [xs_a[0], main_obs_A, xs_a[1]], "o-", color="#1f77b4",
            label="Layer A")
    ax.plot([0.25, 0.50, 0.75],
            [xs_b[0], main_obs_B, xs_b[1]], "s-", color="#d62728",
            label="Layer B")
    ax.axhline(1.0, color="black", lw=1)
    ax.set_xlabel("shrinkage λ")
    ax.set_ylabel("median of per-config median $\\widehat M_2$(C4λ)/C0")
    ax.set_xticks([0.25, 0.50, 0.75])
    ax.set_xticklabels(["0.25", "0.50 (main)", "0.75"])
    ax.legend()
    save(fig, "figure_M2_8_lambda_sensitivity.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
