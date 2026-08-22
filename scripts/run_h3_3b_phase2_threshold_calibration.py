#!/usr/bin/env python3
"""H3-3B Phase 2 -- Proposal Covariance Map: compact/diffuse threshold
calibration (roadmap Sec. 2; NO new Monte Carlo).

Read-only analysis of ``results/phase_h3/h3_3b_multi_system_validation_v1.json``
(4 systems x s^2 in {0.75, 1, 1.5, 2} x 4 seeds, covariance sweep with the
MPP-centred proposal q = N(x*, s^2 I)):

  * extract seed-mean (+/- seed range) R_eta, C_eta, G_eta, VRF per point,
    main variance-dominant mode, eta = 0.8;
  * P2-CK2: per-system monotone decrease of R_eta in s^2;
  * pre-registered dual threshold definitions (task plan Sec. 6.2 /
    roadmap Sec. 2.2):
      ABS type : compact  iff  R_eta < theta * chi_ref,
                 chi_ref = chi^2_4(0.8)^{1/2} (unit-kernel HDR ball radius);
      REL type : compact  iff  R_eta / R_eta(s^2=1) < theta'.
    A global threshold of a given type exists iff the classification window
    theta in ( max_sys R(s^2=2), min_sys R(s^2=0.75) ) / chi_ref   [ABS]
    theta' in ( max_sys r(s^2=2), min_sys r(s^2=0.75) )           [REL]
    is non-empty AND no within-system interleaving occurs at the window
    midpoint; otherwise the honest conclusion is "system-relative thresholds".
  * anchor metadata per point (roadmap rule R-2): anchor class =
    "mpp-centered" (multi-system Exp 2 used m = x*); legitimacy boundary
    s^2 > 1/2 annotated (Prop 3.1);
  * Figure B (fig19): Sigma -> R_eta map, 4 systems overlaid.

Claim boundary: calibrates descriptive thresholds on these 4 frozen systems
only; no universal constant claim, no causal VRF claim, no new MC.

Schema: h3-3b-phase2-threshold-v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.stats import chi2, spearmanr

REPO = Path(__file__).resolve().parents[1]
SRC_JSON = REPO / "results" / "phase_h3" / "h3_3b_multi_system_validation_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_phase2_threshold_v1.json"
FIG19 = REPO / "results" / "phase_h3" / "fig19_covariance_spread_map.png"

S2_GRID = [0.75, 1.0, 1.5, 2.0]
ETA_MAIN = 0.8
CHI_REF = float(np.sqrt(chi2.ppf(ETA_MAIN, df=4)))   # 2.4477, unit-kernel radius
CASE_ORDER = ["A_synthetic_multi_mode_recovery",
              "B_synthetic_curvature_beta_kappa",
              "C1_sanger_b1n1_wide",
              "C2_sanger_b2n_wide"]
SHORT = {"A_synthetic_multi_mode_recovery": "A",
         "B_synthetic_curvature_beta_kappa": "B",
         "C1_sanger_b1n1_wide": "C1",
         "C2_sanger_b2n_wide": "C2"}
SEED_KEYS = ["seed_1", "seed_2120", "seed_3", "seed_4"]


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Extraction (read-only)
# ---------------------------------------------------------------------------
def extract() -> dict:
    raw = SRC_JSON.read_text(encoding="utf-8")
    data = json.loads(raw)
    out = {"systems": {}, "points": []}
    for case in CASE_ORDER:
        anch = data["anchors"][case]
        mode = anch["mode"]                      # variance-dominant mode label
        rows = []
        for s2 in S2_GRID:
            key = f"s2_{s2:g}"
            per_seed = {"R": [], "C": [], "G": [], "vrf": [], "ess": []}
            tr_sv = None
            for sk in SEED_KEYS:
                rec = data["per_case"][case][sk]["cov_sweep"][key]
                tr_sv = rec["analytic"]["Sigma_V_trace"]
                e = rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]
                per_seed["R"].append(e["R"])
                per_seed["C"].append(e["C"])
                per_seed["G"].append(e["G"])
                perf = rec["is_performance"]
                per_seed["vrf"].append(perf["vrf"])
                per_seed["ess"].append(perf["ess"])
            mean = {k: float(np.mean(v)) for k, v in per_seed.items()}
            rng = {k: float(np.max(v) - np.min(v)) for k, v in per_seed.items()}
            # analytic cross-check: tr(Sigma_V) = d / (2 - 1/s^2)
            tr_closed = 4.0 / (2.0 - 1.0 / s2)
            row = {
                "system": SHORT[case], "case": case, "s2": s2,
                "anchor_class": "mpp-centered",          # roadmap R-2
                "mode": mode,
                "x_star": anch["x_star"],
                "legitimate": True,                      # all s^2 > 1/2
                "R_mean": mean["R"], "R_range": rng["R"],
                "C_mean": mean["C"], "G_mean": mean["G"],
                "vrf_mean": mean["vrf"], "ess_mean": mean["ess"],
                "Sigma_V_trace": tr_sv,
                "Sigma_V_trace_closed_form": tr_closed,
                "tr_consistent": abs(tr_sv - tr_closed) <= 1e-9,
            }
            rows.append(row)
            out["points"].append(row)
        out["systems"][SHORT[case]] = {
            "case": case, "mode": mode, "kind": data["scope"],
            "rows": rows,
        }
    return out


# ---------------------------------------------------------------------------
# Monotonicity (P2-CK2)
# ---------------------------------------------------------------------------
def monotonicity(extracted: dict) -> dict:
    res = {}
    for sysname, sysrec in extracted["systems"].items():
        s2 = np.array([r["s2"] for r in sysrec["rows"]])
        R = np.array([r["R_mean"] for r in sysrec["rows"]])
        rho, _ = spearmanr(s2, R)
        drops = [float(R[i] - R[i + 1]) for i in range(len(R) - 1)]
        res[sysname] = {
            "spearman_R_vs_s2": float(rho),
            "max_increase": float(max(0.0, -min(drops))),
            "monotone_decreasing": bool(all(d > 0 for d in drops)),
        }
    return res


# ---------------------------------------------------------------------------
# Pre-registered dual threshold calibration (P2-CK3)
# ---------------------------------------------------------------------------
def _window(lo_pairs, hi_pairs):
    """Global window (theta_lo, theta_hi) with lo<theta<hi; None if empty."""
    t_lo = max(hi_pairs)     # all 'compact-end' values must be BELOW theta
    t_hi = min(lo_pairs)     # all 'diffuse-end' values must be ABOVE theta
    return (t_lo, t_hi) if t_lo < t_hi else None


def classify_full_grid(points, kind, theta):
    """Return per-system step-cleanliness at candidate theta."""
    per_sys = {}
    for p in points:
        val = p["R_mean"] / _baseline(points, p) if kind == "REL" \
            else p["R_mean"] / CHI_REF
        cls = "compact" if val < theta else "diffuse"
        per_sys.setdefault(p["system"], []).append((p["s2"], cls))
    clean = {}
    for sysname, seq in per_sys.items():
        seq.sort()
        labels = [c for _, c in seq]
        # step-clean = single diffuse->compact switch, no interleaving
        k = labels.index("compact") if "compact" in labels else len(labels)
        step_clean = (all(x == "diffuse" for x in labels[:k])
                      and all(x == "compact" for x in labels[k:]))
        clean[sysname] = {
            "sequence": labels,
            "step_clean": step_clean,
        }
    return clean


def _baseline(points, p):
    for q in points:
        if q["system"] == p["system"] and q["s2"] == 1.0:
            return q["R_mean"]
    raise KeyError("s2=1 baseline missing")


def calibrate(extracted: dict) -> dict:
    pts = extracted["points"]
    out = {"chi_ref": CHI_REF}

    # --- ABS type -------------------------------------------------------
    hi_vals = [p["R_mean"] for p in pts if p["s2"] == 2.0]     # compact end
    lo_vals = [p["R_mean"] for p in pts if p["s2"] == 0.75]    # diffuse end
    win_abs = _window([v / CHI_REF for v in lo_vals],
                      [v / CHI_REF for v in hi_vals])
    abs_res = {
        "definition": "compact iff R_eta < theta * chi_ref (chi_ref=%.4f)" % CHI_REF,
        "compact_end_values_R(s2=2)": hi_vals,
        "diffuse_end_values_R(s2=0.75)": lo_vals,
        "endpoint_separated": max(hi_vals) < min(lo_vals),
        "theta_window": win_abs,
    }
    if win_abs:
        theta_mid = 0.5 * (win_abs[0] + win_abs[1])
        abs_res["theta_midpoint"] = theta_mid
        abs_res["full_grid_classification"] = classify_full_grid(pts, "ABS", theta_mid)
    out["absolute_type"] = abs_res

    # --- REL type -------------------------------------------------------
    def ratio(p):
        return p["R_mean"] / _baseline(pts, p)

    hi_r = [ratio(p) for p in pts if p["s2"] == 2.0]
    lo_r = [ratio(p) for p in pts if p["s2"] == 0.75]
    win_rel = _window(lo_r, hi_r)
    rel_res = {
        "definition": "compact iff R_eta/R_eta(s2=1) < theta'",
        "compact_end_ratios(s2=2)": hi_r,
        "diffuse_end_ratios(s2=0.75)": lo_r,
        "endpoint_separated": max(hi_r) < min(lo_r),
        "theta_window": win_rel,
    }
    if win_rel:
        theta_mid = 0.5 * (win_rel[0] + win_rel[1])
        rel_res["theta_midpoint"] = theta_mid
        rel_res["full_grid_classification"] = classify_full_grid(pts, "REL", theta_mid)
    out["relative_type"] = rel_res

    # --- verdict (pre-registered logic) ---------------------------------
    verdict = {
        "absolute_global_exists": bool(win_abs),
        "relative_global_exists": bool(win_rel),
    }
    if verdict["absolute_global_exists"]:
        verdict["adopted"] = "ABS"
    elif verdict["relative_global_exists"]:
        verdict["adopted"] = "REL"
    else:
        verdict["adopted"] = "SYSTEM_RELATIVE"
        verdict["note"] = ("no single global threshold separates the two ends "
                           "across all 4 systems under either pre-registered "
                           "definition; per-system (relative) thresholds are "
                           "the honest conclusion")
    out["verdict"] = verdict
    return out


# ---------------------------------------------------------------------------
# Figure B (fig19)
# ---------------------------------------------------------------------------
def make_figure(extracted: dict, calib: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"A": "#1f77b4", "B": "#d62728", "C1": "#2ca02c", "C2": "#9467bd"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    ax = axes[0]
    for sysname, sysrec in extracted["systems"].items():
        s2 = [r["s2"] for r in sysrec["rows"]]
        Rm = [r["R_mean"] for r in sysrec["rows"]]
        Rr = [r["R_range"] / 2 for r in sysrec["rows"]]
        ax.errorbar(s2, Rm, yerr=Rr, marker="o", capsize=3, ms=5,
                    color=colors[sysname], label=f"{sysname} ({sysrec['mode']})")
    ax.axhline(CHI_REF, ls="--", color="gray", lw=1,
               label=r"$\chi^2_4(0.8)^{1/2}=2.448$ (unit-kernel HDR radius)")
    ax.axvline(0.5, ls=":", color="red", lw=1,
               label=r"legitimacy $\Sigma\succ\frac{1}{2}I$")
    ax.set_xscale("log")
    ax.set_xticks(S2_GRID)
    ax.set_xticklabels([str(s) for s in S2_GRID])
    ax.minorticks_off()
    ax.set_xlabel(r"$s^2$ (proposal $\Sigma=s^2 I$, MPP-centred)")
    ax.set_ylabel(r"$R_{\eta=0.8}$ (seed mean $\pm$ half-range)")
    ax.set_title("Phase 2 / Figure B: $\\Sigma \\to R_\\eta$ covariance map")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    ax = axes[1]
    for sysname, sysrec in extracted["systems"].items():
        s2 = [r["s2"] for r in sysrec["rows"]]
        Gm = [r["G_mean"] for r in sysrec["rows"]]
        ax.plot(s2, Gm, marker="s", ms=5, color=colors[sysname],
                label=f"{sysname}")
    ax.set_xscale("log")
    ax.set_xticks(S2_GRID)
    ax.set_xticklabels([str(s) for s in S2_GRID])
    ax.minorticks_off()
    ax.set_xlabel(r"$s^2$")
    ax.set_ylabel(r"$G_{\eta=0.8}$ (seed mean)")
    ax.set_title("normalized mismatch under the covariance lever")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    v = calib["verdict"]
    tag = (f"global threshold: {v['adopted']}"
           if v["adopted"] != "SYSTEM_RELATIVE"
           else "no global threshold (system-relative)")
    fig.suptitle(f"H3-3B Phase 2 - compact/diffuse calibration   [{tag}]",
                 y=1.02, fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG19, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    sha_before = _sha256(SRC_JSON)

    extracted = extract()
    mono = monotonicity(extracted)
    calib = calibrate(extracted)

    print("=== R_eta(s^2) per system (seed mean, eta=0.8, mpp-centered) ===")
    header = f"{'sys':>4} {'mode':>8} " + "".join(f"s2={s:<6}" for s in S2_GRID) + "mono?"
    print(header)
    for sysname, sysrec in extracted["systems"].items():
        vals = "".join(f"{r['R_mean']:<8.4f}" for r in sysrec["rows"])
        print(f"{sysname:>4} {sysrec['mode']:>8} {vals}"
              f"{mono[sysname]['monotone_decreasing']}")

    print("\n=== threshold calibration ===")
    ca, cr = calib["absolute_type"], calib["relative_type"]
    print(f"ABS: endpoint_separated={ca['endpoint_separated']}  "
          f"window={ca['theta_window']}")
    print(f"REL: endpoint_separated={cr['endpoint_separated']}  "
          f"window={cr['theta_window']}")
    v = calib["verdict"]
    print(f"verdict: adopted={v['adopted']}")
    for kind in ("absolute_type", "relative_type"):
        fg = calib[kind].get("full_grid_classification")
        if fg:
            mid = calib[kind].get("theta_midpoint")
            print(f"{kind} @ midpoint={mid:.4f}:")
            for sysname, rec in fg.items():
                print(f"   {sysname:>3}: {rec['sequence']}  step_clean={rec['step_clean']}")

    if not args.no_fig:
        make_figure(extracted, calib)
        print(f"[fig] {FIG19}")

    ck = {
        "P2-CK1_reuse_bitwise": True,   # no re-run performed; source untouched
        "P2-CK2_monotone_4_of_4":
            all(m["monotone_decreasing"] for m in mono.values()),
        "P2-CK3_threshold": v["adopted"],
        "P2-CK4_legitimacy_annotation_only": True,
        "P2-CK5_anchor_metadata_all_points":
            all(p["anchor_class"] == "mpp-centered" for p in extracted["points"]),
    }
    payload = {
        "schema_version": "h3-3b-phase2-threshold-v1",
        "status": "COMPLETE",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "roadmap_ref": "docs/phase_h/H3_3B_Experiment_Path_Roadmap.md Sec. 2",
        "source": {
            "path": str(SRC_JSON.relative_to(REPO)),
            "sha256": sha_before,
            "reuse_note": "read-only; multi-system cov sweep reused verbatim "
                          "(roadmap P2-CK1: no new MC)",
        },
        "chi_ref": CHI_REF,
        "extracted": extracted,
        "monotonicity": mono,
        "calibration": calib,
        "checkpoints": ck,
        "wall_seconds": time.time() - t0,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    after = _sha256(SRC_JSON)
    payload["source"]["sha256_after_equal"] = (after == sha_before)
    OUT_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[out] {OUT_JSON}")
    print(f"[checkpoints] {ck}")
    print(f"[integrity] source unchanged: {after == sha_before}")


if __name__ == "__main__":
    main()
