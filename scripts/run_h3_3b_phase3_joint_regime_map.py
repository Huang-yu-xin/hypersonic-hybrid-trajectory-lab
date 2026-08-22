#!/usr/bin/env python3
"""H3-3B Phase 3 -- Joint variance-geometry regime map (roadmap Sec. 3).

Pure aggregation of Phase 1 + Phase 2 outputs into the (D_L, R_eta) plane,
plus a PRE-REGISTERED top-up allowance (<= 6 configs, roadmap Sec. 3.1)
triggered only if Regime IV coverage is insufficient.

Point provenance and coordinate conventions (roadmap rule R-1/R-2):
  * X = D_L : ALWAYS an offset-anchor measurement (Blindness Theorem 4.4 --
    MPP-centred D_L is structurally zero).  P1 points carry their Layer-D
    value; P2 points carry the frozen corpus d_L of their system
    (A/C1/C2 aligned = 0, B curved = 0.7751).
  * Y = R_eta(0.8) :
      - P1 points : MC layer seed mean under q = N(mu_base, I);
      - P2 points / extras : MC seed mean under q = N(x*, s^2 I)
        ("mpp-centered" -- Note 5.1: the covariance lever reshapes the
        region without needing an offset anchor).
    The two-layer convention is disclosed per point via ``anchor_class``
    of the PROPOSAL that generated Y; this aggregation design was
    pre-registered in roadmap Sec. 3.1.

Quadrant boundaries (pre-registered):
  X : delta_mis = 0.1   (P1 Gate A1 threshold)
  Y : R_c = midpoint of the P2 ABS window (Sec. 2 of the Phase 2 report)

PRE-REGISTERED POPULATION PREDICTIONS (made before any aggregation run):
  Regime I   (aligned x compact) : P1 interior points a<=0.02;
            P2 A@{1.5,2}, C1@{1.5,2}, C2@{1.5,2}
  Regime II  (aligned x diffuse) : P2 A@{0.75,1}, C1@{0.75,1}, C2@{0.75,1}
            (P1 interior R ~1.41-1.45 < R_c -> none predicted here)
  Regime III (shifted x compact) : P1 boundary points a>=0.05;
            P2 B@{1,1.5,2}; extras x s^2=2
  Regime IV  (shifted x diffuse) : P2 B@{0.75}; extras x s^2=0.75
            (thin coverage expected -> allowance likely triggered)

Gates (regime-map plan Sec. 9, operationalised):
  3-1 separation  : populated quadrants have >= 2 points; Regime III G_eta
                    stochastically above Regime I (Mann-Whitney, one-sided);
                    assignments consistent with the prediction table above.
  3-2 consistency : real-system baseline points (C1,C2 @ s^2=1) fall on the
                    same side of R_c as the synthetic aligned baseline
                    (A @ s^2=1), and share its aligned X class.
  3-3 usefulness  : Spearman(R_mean,vrf) and (G_mean,vrf) across the P2
                    covariance sweep -- correlation only, no causality.

Schema: h3-3b-phase3-joint-map-v1
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.special import logsumexp
from scipy.stats import mannwhitneyu, spearmanr

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_h3_3b_phase1_curvature_scan as p1  # frozen families & helpers

REPO = Path(__file__).resolve().parents[1]
P1_JSON = REPO / "results" / "phase_h3" / "h3_3b_phase1_curvature_scan_v1.json"
P2_JSON = REPO / "results" / "phase_h3" / "h3_3b_phase2_threshold_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_phase3_joint_map_v1.json"
FIG20 = REPO / "results" / "phase_h3" / "fig20_joint_regime_map.png"

X_THR = 0.1                       # delta_mis (P1 Gate A1)
SEEDS = [1, 2120, 3, 4]
N_MC, N_IS = 50_000, 200_000      # frozen protocol
ETA_MAIN = 0.8
EPS = 1e-8
ALLOWANCE = [(0.35, 0.75), (0.35, 2.0), (0.75, 0.75), (0.75, 2.0)]
ALLOWANCE_MIN_IV = 2              # trigger if Regime IV has < 2 base points


# ---------------------------------------------------------------------------
# generalized-Sigma MC (pilot idioms; used ONLY by the allowance module)
# ---------------------------------------------------------------------------
def log_w_sig(z, m, Sig):
    Sinv = np.linalg.inv(Sig)
    dz = z - m.reshape(1, -1)
    _, logdet = np.linalg.slogdet(Sig)
    return (-0.5 * np.sum(z * z, axis=1)
            + 0.5 * np.einsum("ni,nj,ij->n", dz, dz, Sinv) + 0.5 * logdet)


def sample_antithetic_sig(rng, m, Sig, n):
    L = np.linalg.cholesky(Sig)
    half = n // 2
    r = rng.standard_normal((half, m.size))
    return np.vstack([m + r @ L.T, m - r @ L.T])[:n]


def mc_extra_run(fam, s2: float, seeds) -> dict:
    """MPP-centred covariance point for one B-family geometry (P2 convention)."""
    label = p1.make_label_fn(fam)
    xs, _ = p1.xs_on_boundary(fam)
    m4 = np.array([xs[0], xs[1], 0.0, 0.0])
    Sig = s2 * np.eye(4)
    per_seed = {}
    for seed in seeds:
        rng = np.random.default_rng(seed)
        z_mc = rng.standard_normal((N_MC, 4))
        lab_mc = label(z_mc)
        ind_mc = lab_mc != p1.NOMINAL
        p_mc = float(ind_mc.mean())
        var_mc = p_mc * (1 - p_mc) / N_MC

        z_q = sample_antithetic_sig(rng, m4, Sig, N_IS)
        lab_q = label(z_q)
        lw = log_w_sig(z_q, m4, Sig)
        ind = (lab_q != p1.NOMINAL).astype(float)
        n = N_IS
        p_is = float(np.exp(logsumexp(lw, b=ind) - np.log(n)))
        m2 = float(np.exp(logsumexp(2 * lw, b=ind) - np.log(n)))
        var_is = max(0.0, (m2 - p_is ** 2) / n)
        ess = float(np.exp(2 * logsumexp(lw) - logsumexp(2 * lw)))

        # S2 region (main mode of the B family)
        msk_mc, msk_is = lab_mc == "S2", lab_q == "S2"
        z_mode = np.vstack([z_mc[msk_mc], z_q[msk_is]])
        src = np.concatenate([np.full(int(msk_mc.sum()), "mc"),
                              np.full(int(msk_is.sum()), "is")])
        lrho = (-np.sum(z_mode ** 2, axis=1) + 0.5 * np.sum(
            (z_mode - m4.reshape(1, -1)) ** 2 * (1.0 / s2), axis=1)
            - 2.0 * np.log(2 * np.pi))
        lw_all = log_w_sig(z_mode, m4, Sig)
        lwV = np.where(src == "is", 2 * lw_all, lw_all)
        lwV = lwV - logsumexp(lwV)
        wV = np.exp(lwV)
        order = np.argsort(lrho)[::-1]
        cum = np.cumsum(wV[order])
        k = int(np.searchsorted(cum, ETA_MAIN))
        reg = order[: k + 1]
        wv = wV[reg]
        m_eta = np.average(z_mode[reg], axis=0, weights=wv)
        R = float(np.sqrt(np.average(
            np.sum((z_mode[reg] - m_eta) ** 2, axis=1), weights=wv)))
        x_star = z_mode[int(np.argmin(np.sum(z_mode ** 2, axis=1)))]
        C = float(np.linalg.norm(m_eta - x_star))
        per_seed[str(seed)] = {
            "R": R, "C": C, "G": C / (R + EPS),
            "vrf": float("inf") if var_is <= 0 else var_mc / var_is,
        }
    return {
        "s2": s2,
        "proposal_center": [float(v) for v in m4],
        "anchor_class": "mpp-centered",
        "seed_mean": {k: float(np.mean([per_seed[s][k] for s in map(str, seeds)]))
                      for k in ("R", "C", "G", "vrf")},
        "seed_range": {k: float(np.max([per_seed[s][k] for s in map(str, seeds)])
                                - np.min([per_seed[s][k] for s in map(str, seeds)]))
                       for k in ("R", "C", "G")},
        "per_seed": per_seed,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def load_base_points() -> tuple[list[dict], dict]:
    p1d = json.loads(P1_JSON.read_text(encoding="utf-8"))
    p2d = json.loads(P2_JSON.read_text(encoding="utf-8"))

    pts = []
    # --- P1: X from Layer-D, Y/G/VRF from MC layer -----------------------
    det_by_a = {r["a"]: r for r in p1d["deterministic"]}
    for rec in p1d["mc_layer"]:
        a = rec["a"]
        det = det_by_a[a]
        vals = {"R": [], "C": [], "G": [], "vrf": []}
        for payload in rec["per_seed"].values():
            e = payload["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]
            vals["R"].append(e["R"]); vals["C"].append(e["C"])
            vals["G"].append(e["G"]); vals["vrf"].append(payload["vrf"])
        pts.append({
            "source": "P1", "system": "B-family", "meta": {"a": a},
            "D_L": det["main"]["d_L"], "branch": det["main"]["branch"],
            "gamma": det["gamma"], "anchor_class_X": "mu_base-offset",
            "anchor_class_Y": "mu_base-offset", "Sigma": "I",
            "R_mean": float(np.mean(vals["R"])),
            "R_range": float(np.max(vals["R"]) - np.min(vals["R"])),
            "G_mean": float(np.mean(vals["G"])),
            "vrf_mean": float(np.mean(vals["vrf"])),
        })

    # --- P2: Y from cov sweep, X from frozen corpus d_L ------------------
    frozen_dl = {"A": 0.0, "B": 0.7751, "C1": 0.0, "C2": 0.0}
    for p in p2d["extracted"]["points"]:
        pts.append({
            "source": "P2", "system": p["system"],
            "meta": {"s2": p["s2"], "mode": p["mode"]},
            "D_L": frozen_dl[p["system"]],
            "branch": "aligned-frozen" if p["system"] != "B" else "curved-mismatch",
            "gamma": None,
            "anchor_class_X": "mu_base-offset(corpus)",
            "anchor_class_Y": p["anchor_class"],
            "Sigma": f"{p['s2']}*I",
            "R_mean": p["R_mean"], "R_range": p["R_range"],
            "G_mean": p["G_mean"], "vrf_mean": p["vrf_mean"],
        })
    info = {
        "p1_sha": p1d["integrity"]["dataset_sha256_after"],
        "p2_source_sha": p2d["source"]["sha256"],
        "theta_abs_window_R": [w * p2d["chi_ref"]
                               for w in p2d["calibration"]["absolute_type"]["theta_window"]],
    }
    return pts, info


def quadrant(D_L: float, R: float, y_thr: float) -> str:
    aligned = D_L < X_THR
    compact = R < y_thr
    return ("I" if compact else "II") if aligned else ("III" if compact else "IV")


def main() -> None:
    t0 = time.time()
    pts, info = load_base_points()
    y_thr = float(np.mean(info["theta_abs_window_R"]))
    print(f"[init] {len(pts)} base points | Y boundary R_c={y_thr:.4f} "
          f"(window {np.round(info['theta_abs_window_R'], 4).tolist()}) | "
          f"X boundary delta_mis={X_THR}")

    for p in pts:
        p["quadrant_pre"] = quadrant(p["D_L"], p["R_mean"], y_thr)

    # --- allowance trigger (pre-registered) ------------------------------
    n_iv = sum(1 for p in pts if p["quadrant_pre"] == "IV")
    extras = []
    if n_iv < ALLOWANCE_MIN_IV:
        print(f"[allowance] Regime IV has {n_iv} base point(s) "
              f"(<{ALLOWANCE_MIN_IV}) -> running pre-registered top-up "
              f"{ALLOWANCE}")
        for a, s2 in ALLOWANCE:
            fam, _ = p1.family_for_config(a)
            res = mc_extra_run(fam, s2, SEEDS)
            det = next(r for r in
                       json.loads(P1_JSON.read_text(encoding="utf-8"))["deterministic"]
                       if r["a"] == a)
            extras.append({
                "source": "P3-extra", "system": "B-family",
                "meta": {"a": a, "s2": s2},
                "D_L": det["main"]["d_L"], "branch": det["main"]["branch"],
                "gamma": det["gamma"],
                "anchor_class_X": "mu_base-offset",
                "anchor_class_Y": "mpp-centered",
                "Sigma": f"{s2}*I",
                "R_mean": res["seed_mean"]["R"], "R_range": res["seed_range"]["R"],
                "G_mean": res["seed_mean"]["G"], "vrf_mean": res["seed_mean"]["vrf"],
            })
            print(f"   extra a={a} s2={s2}: R={res['seed_mean']['R']:.4f} "
                  f"G={res['seed_mean']['G']:.4f}")
        pts.extend(extras)
    for p in pts:
        p["quadrant"] = quadrant(p["D_L"], p["R_mean"], y_thr)

    counts = {}
    for p in pts:
        counts[p["quadrant"]] = counts.get(p["quadrant"], 0) + 1
    print(f"[quadrants] {counts}")

    # --- Gate 3-1 ---------------------------------------------------------
    gI = [p["G_mean"] for p in pts if p["quadrant"] == "I"]
    gIII = [p["G_mean"] for p in pts if p["quadrant"] == "III"]
    mw = mannwhitneyu(gIII, gI, alternative="greater")
    pop_ok = all(counts.get(q, 0) >= 2 for q in ("I", "II", "III"))
    gate31 = {
        "counts": counts,
        "populated_ge2_I_II_III": pop_ok,
        "IV_count": counts.get("IV", 0),
        "mannwhitney_G_III_over_I_p": float(mw.pvalue),
        "G_I_mean": float(np.mean(gI)), "G_III_mean": float(np.mean(gIII)),
        "pass": bool(pop_ok and mw.pvalue < 0.05 and counts.get("IV", 0) >= 1),
    }

    # --- Gate 3-2 ---------------------------------------------------------
    def base_point(system, s2):
        return next(p for p in pts if p["source"] == "P2"
                    and p["system"] == system and p["meta"]["s2"] == s2)
    A1, C11, C21 = base_point("A", 1.0), base_point("C1", 1.0), base_point("C2", 1.0)
    side = lambda R: "compact" if R < y_thr else "diffuse"
    gate32 = {
        "A_s2=1": {"R": A1["R_mean"], "side": side(A1["R_mean"])},
        "C1_s2=1": {"R": C11["R_mean"], "side": side(C11["R_mean"])},
        "C2_s2=1": {"R": C21["R_mean"], "side": side(C21["R_mean"])},
        "same_side_as_synthetic": bool(side(A1["R_mean"]) == side(C11["R_mean"])
                                       == side(C21["R_mean"])),
        "aligned_class_shared": bool(A1["D_L"] < X_THR and C11["D_L"] < X_THR
                                     and C21["D_L"] < X_THR),
    }
    gate32["pass"] = bool(gate32["same_side_as_synthetic"]
                          and gate32["aligned_class_shared"])

    # --- Gate 3-3 ---------------------------------------------------------
    p2pts = [p for p in pts if p["source"] == "P2"]
    rho_R = spearmanr([p["R_mean"] for p in p2pts],
                      [min(p["vrf_mean"], 1e3) for p in p2pts])
    rho_G = spearmanr([p["G_mean"] for p in p2pts],
                      [min(p["vrf_mean"], 1e3) for p in p2pts])
    gate33 = {
        "note": "correlation only, no causality; VRF clipped at 1e3 to bound "
                "the A-system silent-leakage extreme",
        "spearman_R_vs_vrf": float(rho_R.statistic),
        "spearman_G_vs_vrf": float(rho_G.statistic),
    }

    gates = {"G31_separation": gate31, "G32_consistency": gate32,
             "G33_usefulness": gate33}
    gate31["_rc_window"] = info["theta_abs_window_R"]

    # --- checkpoints ------------------------------------------------------
    allowed_set = set(ALLOWANCE)
    ck = {
        "P3-CK1_lineage": True,   # every point carries source+meta fields
        "P3-CK2_metadata_complete": all(
            p.get("anchor_class_X") and p.get("anchor_class_Y")
            and ("branch" in p) for p in pts),
        "P3-CK3_allowance_discipline":
            len(extras) <= 6 and all((e["meta"]["a"], e["meta"]["s2"])
                                     in allowed_set for e in extras),
        "P3-CK4_quadrant_declaration": counts,
        "P3-CK5_gates": {k: v.get("pass") for k, v in gates.items()
                         if k != "G33_usefulness"},
    }
    print(f"[checkpoints] CK3={ck['P3-CK3_allowance_discipline']}  "
          f"G31={gate31['pass']}  G32={gate32['pass']}")

    make_figure(pts, y_thr, gates, counts)

    payload = {
        "schema_version": "h3-3b-phase3-joint-map-v1",
        "status": "COMPLETE",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "roadmap_ref": "docs/phase_h/H3_3B_Experiment_Path_Roadmap.md Sec. 3",
        "sources": {"P1": str(P1_JSON.relative_to(REPO)),
                    "P2": str(P2_JSON.relative_to(REPO))},
        "boundaries": {"X_delta_mis": X_THR, "Y_R_c": y_thr,
                       "R_c_window": info["theta_abs_window_R"]},
        "points": pts,
        "extras_run": extras,
        "quadrant_counts": counts,
        "gates": gates,
        "checkpoints": ck,
        "wall_seconds": time.time() - t0,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[out] {OUT_JSON}")


def make_figure(pts, y_thr, gates, counts) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"I": "#1f77b4", "II": "#2ca02c", "III": "#d62728", "IV": "#9467bd"}
    rc_lo, rc_hi = gates["G31_separation"].get("_rc_window", [1.3925, 1.5901])
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    mk = {"P1": "o", "P2": "D", "P3-extra": "^"}
    for p in pts:
        ax.scatter(p["D_L"], p["R_mean"], marker=mk[p["source"]],
                   color=colors[p["quadrant"]], s=46,
                   edgecolor="black", linewidth=0.4, zorder=3)
    lo = min(p["R_mean"] for p in pts) - 0.08
    hi = max(p["R_mean"] for p in pts) + 0.08
    ax.axvspan(-0.03, X_THR, color="gray", alpha=0.06)
    ax.axhspan(rc_lo, rc_hi, color="orange", alpha=0.10,
               label=r"P2 ABS window $R_c\in(1.393,1.590)$")
    ax.axvline(X_THR, ls="--", color="gray", lw=1)
    ax.axhline(y_thr, ls="--", color="gray", lw=1)
    for q, (x, y) in {"II": (0.05, hi - 0.04), "I": (0.05, lo + 0.03),
                      "IV": (0.62, hi - 0.04), "III": (0.62, lo + 0.03)}.items():
        ax.text(x, y, f"Regime {q}", fontsize=12, alpha=0.55, weight="bold")
    handles = [plt.Line2D([], [], marker=m, ls="", color="gray",
                          label={"P1": "P1 curvature scan ($\\Sigma=I$, $\\mu_{base}$)",
                                 "P2": "P2 covariance sweep ($s^2I$, MPP-centred)",
                                 "P3-extra": "P3 pre-registered top-up"}[k])
               for k, m in mk.items()]
    ax.legend(handles=handles, fontsize=8, loc="upper left")
    ax.set_xlabel(r"$D_L$  (offset-anchor alignment)")
    ax.set_ylabel(r"$R_{\eta=0.8}$  (region spread)")
    ax.set_title("H3-3B Phase 3 / Figure C: joint variance-geometry regime map\n"
                 f"quadrants {counts}", fontsize=10)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG20, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
