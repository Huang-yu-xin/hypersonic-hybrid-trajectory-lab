#!/usr/bin/env python3
"""H3-3B P2R -- real-system sample-size convergence check (task addendum).

Stage 1 (frozen): C1/C2 x s^2 in {0.75,1,1.5,2} x 4 seeds at the doubled
audit level (N_MC, N_IS) = (512, 256); primary endpoint is the covariance
lever correlation rho(tr Sigma_V, R_eta=0.8) versus the multi-system
baseline recomputed from the frozen JSON with the SAME formula.

Reuses the multi-system real pipeline by import (env/vehicle/anchors/
S_A-transform/parallel exact-topology labels).  No frozen artifact is
modified; the source JSON is only read for the baseline.

Schema: h3-3b-p2r-real-n-convergence-v1
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_h3_3b_multi_system_validation as ms   # frozen real pipeline

SRC_JSON = REPO / "results" / "phase_h3" / "h3_3b_multi_system_validation_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_p2r_real_n_convergence_v1.json"

CASES = ["C1_sanger_b1n1_wide", "C2_sanger_b2n_wide"]
SHORT = {"C1_sanger_b1n1_wide": "C1", "C2_sanger_b2n_wide": "C2"}
S2_GRID = [0.75, 1.0, 1.5, 2.0]
SEEDS = [1, 2120, 3, 4]
N_MC_NEW, N_IS_NEW = 512, 256                    # Stage-1 doubled audit level
GATE_TOL = 0.03


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Baseline: recompute rho at (256,128) from the frozen JSON, same formula
# ---------------------------------------------------------------------------
def baseline_rho() -> dict:
    data = json.loads(SRC_JSON.read_text(encoding="utf-8"))
    out = {}
    for case in CASES:
        rows_tr, rows_R = [], []
        per_seed = {s: [] for s in SEEDS}
        for sk in [f"seed_{s}" for s in SEEDS]:
            rec = data["per_case"][case][sk]
            mode = rec["anchors"]["mode"]
            trs, Rs = [], []
            for s2 in S2_GRID:
                cfgrec = rec["cov_sweep"][f"s2_{s2:g}"]
                e = cfgrec["region"][mode]["per_eta"]["eta_0.8"]
                tr = cfgrec["analytic"]["Sigma_V_trace"]
                rows_tr.append(tr); rows_R.append(e["R"])
                trs.append(tr); Rs.append(e["R"])
            per_seed[int(rec["seed"])] = float(spearmanr(trs, Rs).statistic)
        out[SHORT[case]] = {
            "rho_pooled16": float(spearmanr(rows_tr, rows_R).statistic),
            "rho_per_seed_mean": float(np.mean(list(per_seed.values()))),
            "per_seed": per_seed,
        }
    return out


# ---------------------------------------------------------------------------
# Stage-1 run
# ---------------------------------------------------------------------------
def run_case(case: str, mlb1: dict) -> dict:
    cfg = next(c for c in ms.CASES if c["experiment_id"] == case)
    env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base = (
        ms._real_setup(cfg, mlb1))
    label_fn = ms._real_label_fn(env, vehicle, K, center, alpha, nominal)
    anchors = ms.ANCHORS[case]
    mode = anchors["mode"]

    per_seed = {}
    for seed in SEEDS:
        t0 = time.time()
        rng = np.random.default_rng(seed)
        z_mc = rng.standard_normal((N_MC_NEW, ms.DIM))
        labels_mc = np.asarray(label_fn(z_mc))
        ind_mc = labels_mc != ms.NOMINAL
        p_mc = float(ind_mc.mean())
        var_mc = p_mc * (1 - p_mc) / N_MC_NEW

        sweep = {}
        for s2 in S2_GRID:
            m = np.asarray(anchors["x_star"], dtype=float).copy()
            Sigma = s2 * np.eye(ms.DIM)
            z_q = ms.sample_antithetic_gauss(rng, m, Sigma, N_IS_NEW)
            labels_q = np.asarray(label_fn(z_q))
            analytic = ms.analytic_variance_geometry(m, Sigma)
            if not analytic["valid"]:
                raise RuntimeError(f"illegitimate proposal s2={s2}")
            perf = ms.is_performance(z_q, labels_q, m, Sigma, p_mc, var_mc)
            msk_mc, msk_is = labels_mc == mode, labels_q == mode
            z_mode = np.vstack([z_mc[msk_mc], z_q[msk_is]])
            src = np.concatenate([np.full(int(msk_mc.sum()), "mc"),
                                  np.full(int(msk_is.sum()), "is")])
            geo = ms.mode_region_geometry(z_mode, src, m, Sigma, ms.ETAS)
            sweep[f"s2_{s2:g}"] = {
                "analytic": analytic,
                "is_performance": perf,
                "region": {mode: geo},
            }
        per_seed[str(seed)] = {
            "p_mc": p_mc, "var_mc": var_mc, "sweep": sweep,
            "wall_seconds": time.time() - t0,
        }
        print(f"  [{case} seed={seed}] done in {time.time()-t0:.0f}s "
              f"(p_mc={p_mc:.4f})")
    return {"case": case, "mode": mode, "per_seed": per_seed}


def rho_of(case_rec: dict) -> dict:
    rows_tr, rows_R = [], []
    per_seed = {}
    for sk, rec in case_rec["per_seed"].items():
        trs, Rs = [], []
        for s2 in S2_GRID:
            cfgrec = rec["sweep"][f"s2_{s2:g}"]
            e = cfgrec["region"][case_rec["mode"]]["per_eta"][f"eta_{ETA_MAIN_STR}"]
            tr = cfgrec["analytic"]["Sigma_V_trace"]
            rows_tr.append(tr); rows_R.append(e["R"]); trs.append(tr); Rs.append(e["R"])
        per_seed[sk] = float(spearmanr(trs, Rs).statistic)
    return {"rho_pooled16": float(spearmanr(rows_tr, rows_R).statistic),
            "rho_per_seed_mean": float(np.mean(list(per_seed.values()))),
            "per_seed": per_seed}


ETA_MAIN_STR = "0.8"


def main() -> None:
    t0 = time.time()
    mlb1 = json.loads((REPO / "tests" / "data" /
                       "ml_b1_first_order_geometry_v1.json").read_text(encoding="utf-8"))
    base = baseline_rho()
    print("=== baseline (recomputed @256/128, same formula) ===")
    for k, v in base.items():
        print(f"  {k}: pooled={v['rho_pooled16']:.4f} "
              f"per-seed-mean={v['rho_per_seed_mean']:.4f}")

    results = {}
    for case in CASES:
        print(f"[run] {case} @ (512,256)")
        rec = run_case(case, mlb1)
        rec["rho"] = rho_of(rec)
        results[SHORT[case]] = rec
        print(f"  rho pooled={rec['rho']['rho_pooled16']:.4f} "
              f"per-seed-mean={rec['rho']['rho_per_seed_mean']:.4f}")

    # gates
    gates = {}
    for k in ("C1", "C2"):
        new = results[k]["rho"]["rho_pooled16"]
        old = base[k]["rho_pooled16"]
        gates[k] = {
            "baseline_rho": old, "new_rho": new, "delta": new - old,
            "no_degradation_pass": bool(new >= old - GATE_TOL),
        }

    # R_eta seed-range comparison vs baseline level
    for k in ("C1", "C2"):
        case = next(c for c in CASES if SHORT[c] == k)
        rngs_new, rngs_old = [], []
        rec_new = results[k]
        for sk, rec in rec_new["per_seed"].items():
            Rs = [rec["sweep"][f"s2_{s2:g}"]["region"][rec_new["mode"]]
                  ["per_eta"]["eta_0.8"]["R"] for s2 in S2_GRID]
            rngs_new.append(max(Rs) - min(Rs))
        data = json.loads(SRC_JSON.read_text(encoding="utf-8"))
        for sk in [f"seed_{s}" for s in SEEDS]:
            r0 = data["per_case"][case][sk]
            mode = r0["anchors"]["mode"]
            Rs = [r0["cov_sweep"][f"s2_{s2:g}"]["region"][mode]
                  ["per_eta"]["eta_0.8"]["R"] for s2 in S2_GRID]
            rngs_old.append(max(Rs) - min(Rs))
        gates[k]["R_eta_within_seed_range_new_mean"] = float(np.mean(rngs_new))
        gates[k]["R_eta_within_seed_range_baseline_mean"] = float(np.mean(rngs_old))

    payload = {
        "schema_version": "h3-3b-p2r-real-n-convergence-v1",
        "status": "COMPLETE",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task_ref": "docs/phase_h/H3_3B_P2R_RealN_Convergence_Task.md",
        "stage": 1,
        "level": {"N_MC": N_MC_NEW, "N_IS": N_IS_NEW},
        "s2_grid": S2_GRID, "seeds": SEEDS,
        "gate_tolerance": GATE_TOL,
        "baseline_recomputed": base,
        "results": results,
        "gates": gates,
        "wall_seconds": time.time() - t0,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[out] {OUT_JSON}")
    for k, g in gates.items():
        print(f"[gate] {k}: rho {g['baseline_rho']:.4f} -> {g['new_rho']:.4f} "
              f"(delta {g['delta']:+.4f}) pass={g['no_degradation_pass']}")


if __name__ == "__main__":
    main()
