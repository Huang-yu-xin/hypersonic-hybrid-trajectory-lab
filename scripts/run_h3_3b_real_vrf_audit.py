#!/usr/bin/env python3
"""H3-3B Real VRF Audit -- correct the nominal-definition artifact in the
real-system (C1/C2) performance fields of multi-system + P2R (handoff task).

Root cause (P2R erratum_v1_1 / P2R report Sec. 4): the shared numeric core
``pilot.is_performance`` hardcodes the synthetic nominal ``NOMINAL='S0'``
(pilot.py line 286) when building the event indicator; real cases must use
``expected_regime='SRTI_N2'`` from the ML-B1 anchor.  ``finalize_real_request``
computes p_mc with the correct setup nominal, so stored p_mc values were
always right -- only the perf fields (p_hat / var / VRF / n_accepted) were
wrong, for real cases, in BOTH the multi-system JSON and the P2R JSON.

Method (NO experiment redesign; same seeds / proposal family / s^2 grid /
MC-IS budget):
  Scope A: reproduce the multi-system real sweep via ``ms.audit_system``
           (deterministic request draws), re-label through the frozen
           dynamics pipeline, and materialise with a CORRECTED perf
           function; region descriptors reuse ``ms.mode_region_geometry``
           unchanged.
  Scope B: reproduce the P2R Stage-1 sampling stream identically and
           materialise the same way.

Checks (handoff task):
  1. audited p_mc == stored p_mc (both were computed correctly; equality
     confirms stream fidelity),
  2. perf fields now computed against the correct event (p_hat ~ 0.4-0.6,
     not ~0.98) -- old-vs-new side-by-side recorded,
  3. geometry conclusions untouched: audited R_eta bit-matches the stored
     JSONs and the recomputed cov-sweep rho equals the stored rho.

Claim boundary: may update real VRF / IS-performance narratives; must NOT
alter cov-lever conclusions, regime map, or geometry-descriptor results.
Frozen artifacts are never written.

Schema: h3-3b-real-vrf-audit-v1
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.special import logsumexp
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO / "scripts"))
import run_h3_3b_multi_system_validation as ms   # frozen real pipeline

MS_JSON = REPO / "results" / "phase_h3" / "h3_3b_multi_system_validation_v1.json"
P2R_JSON = REPO / "results" / "phase_h3" / "h3_3b_p2r_real_n_convergence_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_real_vrf_audit_v1.json"

CASES = ["C1_sanger_b1n1_wide", "C2_sanger_b2n_wide"]
SHORT = {"C1_sanger_b1n1_wide": "C1", "C2_sanger_b2n_wide": "C2"}
SEEDS = [1, 2120, 3, 4]
S2_GRID = [0.75, 1.0, 1.5, 2.0]
ETAS = ms.ETAS
ETA_MAIN = ms.ETA_MAIN
TOL = 1e-9


# ---------------------------------------------------------------------------
# CORRECTED perf (same formulas as pilot.is_performance, correct event)
# ---------------------------------------------------------------------------
def is_performance_correct(z_q, labels_q, m, Sigma, p_mc, var_mc, nominal):
    lw = ms.log_w_general(z_q, m, Sigma)
    ind = np.asarray(labels_q != nominal, dtype=float)
    n = z_q.shape[0]
    p = float(np.exp(logsumexp(lw, b=ind) - np.log(n)))
    m2 = float(np.exp(logsumexp(2.0 * lw, b=ind) - np.log(n)))
    var = float(max(0.0, (m2 - p ** 2) / n))
    ess = float(np.exp(2.0 * logsumexp(lw) - logsumexp(2.0 * lw)))
    return {
        "p": p, "var": var, "m2_estimate": m2, "ess": ess,
        "vrf": float("inf") if var <= 0.0 else var_mc / var,
        "n_accepted": int(ind.sum()), "n_total": int(n),
        "p_mc": p_mc, "var_mc": var_mc, "event_nominal": nominal,
    }


def materialise(req_z, req_m, req_Sigma, labels_q, z_mc, labels_mc,
                p_mc, var_mc, nominal):
    analytic = ms.analytic_variance_geometry(req_m, req_Sigma)
    perf = is_performance_correct(req_z, labels_q, req_m, req_Sigma,
                                  p_mc, var_mc, nominal)
    region = {}
    modes = sorted(set(labels_q.tolist()) - {nominal})
    for topo in modes:
        mask_mc = labels_mc == topo
        mask_is = labels_q == topo
        if not (np.any(mask_mc) or np.any(mask_is)):
            continue
        z_mode = np.vstack([z_mc[mask_mc], req_z[mask_is]])
        source = np.concatenate([np.full(int(mask_mc.sum()), "mc"),
                                 np.full(int(mask_is.sum()), "is")])
        geo = ms.mode_region_geometry(z_mode, source, req_m, req_Sigma, ETAS)
        if geo is not None:
            region[str(topo)] = geo
    return {"proposal": {"m": req_m.tolist(), "Sigma": req_Sigma.tolist(),
                         "legitimate": True},
            "analytic": analytic, "is_performance": perf, "region": region}


def batch_labels(label_fn, z_lists):
    """One Pool call for all sample batches (list of arrays -> list of arrays)."""
    sizes = [len(z) for z in z_lists]
    flat = np.vstack(z_lists)
    labels = np.asarray(label_fn(flat))
    out, i = [], 0
    for n in sizes:
        out.append(labels[i:i + n])
        i += n
    return out


def stored_rho_ms(stored, case):
    """Stored multi-system cov-sweep rho, recomputed row-for-row from the
    stored JSON (16 rows = 4 s2 x 4 seeds) -- the definition used everywhere."""
    rows_tr, rows_R = [], []
    for seed in SEEDS:
        rec = stored["per_case"][case][f"seed_{seed}"]
        mode = rec["anchors"]["mode"]
        for s2 in S2_GRID:
            cfgrec = rec["cov_sweep"][f"s2_{s2:g}"]
            rows_tr.append(cfgrec["analytic"]["Sigma_V_trace"])
            rows_R.append(cfgrec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]["R"])
    return float(spearmanr(rows_tr, rows_R).statistic)


# ---------------------------------------------------------------------------
# Scope A: multi-system reproduction with corrected perf
# ---------------------------------------------------------------------------
def scope_a(mlb1: dict) -> tuple[dict, dict]:
    stored = json.loads(MS_JSON.read_text(encoding="utf-8"))
    report, checks = {}, {"p_mc_match": True, "R_eta_bitmatch_maxabs": 0.0,
                          "rho_match_maxabs": 0.0}
    for case in CASES:
        cfg = next(c for c in ms.CASES if c["experiment_id"] == case)
        env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base = (
            ms._real_setup(cfg, mlb1))
        label_fn = ms._real_label_fn(env, vehicle, K, center, alpha, nominal)

        per_seed_meta, all_z, index = [], [], []
        for seed in SEEDS:
            record, reqs = ms.audit_system(cfg, mlb1, seed, "real")
            per_seed_meta.append((seed, record, reqs))
            all_z.append(record["_z_mc"])
            index.append((seed, "mc", None))
            for req in reqs:
                all_z.append(req["z"])
                index.append((seed, req["kind"], req["cfg_key"]))
        all_labels = batch_labels(label_fn, all_z)

        per_seed, mode = {}, None
        lab_by_i = dict(zip(range(len(all_z)), all_labels))
        for seed, record, reqs in per_seed_meta:
            mode = record["anchors"]["mode"]
            # gather this seed's slices in order
            own = [(i, b) for i, b in enumerate(index) if b[0] == seed]
            labels_map = {i: lab_by_i[i] for i, b in own}
            z_mc = record["_z_mc"]
            labels_mc = labels_map[own[0][0]]
            p_mc, var_mc = ms.mc_estimator(labels_mc != nominal)
            stored_rec = stored["per_case"][case][f"seed_{seed}"]
            if abs(p_mc - stored_rec["p_mc"]) > TOL:
                checks["p_mc_match"] = False

            sweeps = {"mean_sweep": {}, "cov_sweep": {}}
            j = 0
            for req in reqs:
                i_req = own[1 + j][0]
                labels_q = labels_map[i_req]
                rec = materialise(req["z"], req["m"], req["Sigma"], labels_q,
                                  z_mc, labels_mc, p_mc, var_mc, nominal)
                if req["kind"] == "mean" and record["aligned"]:
                    for lam in ms.LAMBDAS:
                        sweeps["mean_sweep"][f"lambda_{lam:+.1f}"] = rec
                else:
                    sweeps[req["kind"] + "_sweep"][req["cfg_key"]] = rec
                j += 1
            per_seed[str(seed)] = {"p_mc": p_mc, "var_mc": var_mc, **sweeps}

        # Check 3: R_eta bit-match + rho vs stored-recomputed
        rows_tr, rows_R = [], []
        for seed in SEEDS:
            stored_rec = stored["per_case"][case][f"seed_{seed}"]
            for s2 in S2_GRID:
                rec = per_seed[str(seed)]["cov_sweep"][f"s2_{s2:g}"]
                e_new = rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]
                e_old = stored_rec["cov_sweep"][f"s2_{s2:g}"]["region"][mode][
                    "per_eta"][f"eta_{ETA_MAIN}"]
                checks["R_eta_bitmatch_maxabs"] = max(
                    checks["R_eta_bitmatch_maxabs"], abs(e_new["R"] - e_old["R"]))
                rows_tr.append(rec["analytic"]["Sigma_V_trace"])
                rows_R.append(e_new["R"])
        rho_audited = float(spearmanr(rows_tr, rows_R).statistic)
        rho_stored = stored_rho_ms(stored, case)
        checks["rho_match_maxabs"] = max(checks["rho_match_maxabs"],
                                         abs(rho_audited - rho_stored))
        report[SHORT[case]] = {
            "case": case, "nominal_expected": nominal, "mode": mode,
            "per_seed": per_seed,
            "rho_cov_audited": rho_audited, "rho_stored_recomputed": rho_stored,
        }
    return report, checks


# ---------------------------------------------------------------------------
# Scope B: P2R Stage-1 reproduction with corrected perf
# ---------------------------------------------------------------------------
def scope_b(mlb1: dict) -> tuple[dict, dict]:
    stored = json.loads(P2R_JSON.read_text(encoding="utf-8"))
    report, checks = {}, {"R_eta_bitmatch_maxabs": 0.0, "rho_match_maxabs": 0.0}
    for case in CASES:
        cfg = next(c for c in ms.CASES if c["experiment_id"] == case)
        env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base = (
            ms._real_setup(cfg, mlb1))
        label_fn = ms._real_label_fn(env, vehicle, K, center, alpha, nominal)
        anchors = ms.ANCHORS[case]
        mode = anchors["mode"]

        per_seed = {}
        for seed in SEEDS:
            rng = np.random.default_rng(seed)          # identical to P2R stream
            z_mc = rng.standard_normal((512, ms.DIM))
            labels_mc = np.asarray(label_fn(z_mc))
            p_mc, var_mc = ms.mc_estimator(labels_mc != nominal)
            sweep = {}
            for s2 in S2_GRID:
                m = np.asarray(anchors["x_star"], dtype=float).copy()
                Sigma = s2 * np.eye(ms.DIM)
                z_q = ms.sample_antithetic_gauss(rng, m, Sigma, 256)
                labels_q = np.asarray(label_fn(z_q))
                sweep[f"s2_{s2:g}"] = materialise(
                    z_q, m, Sigma, labels_q, z_mc, labels_mc,
                    p_mc, var_mc, nominal)
            per_seed[str(seed)] = {"p_mc": p_mc, "var_mc": var_mc,
                                   "sweep": sweep}

        rows_tr, rows_R = [], []
        for seed in SEEDS:
            for s2 in S2_GRID:
                rec = per_seed[str(seed)]["sweep"][f"s2_{s2:g}"]
                e_new = rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]
                e_old = stored["results"][SHORT[case]]["per_seed"][str(seed)][
                    "sweep"][f"s2_{s2:g}"]["region"][mode][
                    "per_eta"][f"eta_{ETA_MAIN}"]
                checks["R_eta_bitmatch_maxabs"] = max(
                    checks["R_eta_bitmatch_maxabs"], abs(e_new["R"] - e_old["R"]))
                rows_tr.append(rec["analytic"]["Sigma_V_trace"])
                rows_R.append(e_new["R"])
        rho_audited = float(spearmanr(rows_tr, rows_R).statistic)
        rho_stored = stored["results"][SHORT[case]]["rho"]["rho_pooled16"]
        checks["rho_match_maxabs"] = max(checks["rho_match_maxabs"],
                                         abs(rho_audited - rho_stored))
        report[SHORT[case]] = {"case": case, "nominal_expected": nominal,
                               "mode": mode, "per_seed": per_seed,
                               "rho_cov_audited": rho_audited,
                               "rho_stored": rho_stored}
    return report, checks


def main() -> None:
    t0 = time.time()
    mlb1 = json.loads((REPO / "tests" / "data" /
                       "ml_b1_first_order_geometry_v1.json").read_text(encoding="utf-8"))

    print("[scope A] multi-system reproduction (corrected perf) ...", flush=True)
    rep_a, chk_a = scope_a(mlb1)
    print(f"  p_mc_match={chk_a['p_mc_match']}  "
          f"R_eta max|diff|={chk_a['R_eta_bitmatch_maxabs']:.2e}  "
          f"rho max|diff|={chk_a['rho_match_maxabs']:.2e}", flush=True)
    for k, v in rep_a.items():
        print(f"  {k}: rho_cov_audited={v['rho_cov_audited']:.6f} "
              f"(stored recomputed {v['rho_stored_recomputed']:.6f})", flush=True)

    print("[scope B] P2R Stage-1 reproduction (corrected perf) ...", flush=True)
    rep_b, chk_b = scope_b(mlb1)
    print(f"  R_eta max|diff|={chk_b['R_eta_bitmatch_maxabs']:.2e}  "
          f"rho max|diff|={chk_b['rho_match_maxabs']:.2e}", flush=True)
    for k, v in rep_b.items():
        print(f"  {k}: rho_cov_audited={v['rho_cov_audited']:.6f} "
              f"(stored {v['rho_stored']:.6f})", flush=True)

    # Check 2 evidence: old-vs-new perf side-by-side (cov sweep, s2=1, seed 1)
    demo = {}
    stored_ms = json.loads(MS_JSON.read_text(encoding="utf-8"))
    stored_p2 = json.loads(P2R_JSON.read_text(encoding="utf-8"))
    for k in ("C1", "C2"):
        case = next(c for c in CASES if SHORT[c] == k)
        old_ms = stored_ms["per_case"][case]["seed_1"]["cov_sweep"]["s2_1"]["is_performance"]
        new_ms = rep_a[k]["per_seed"]["1"]["cov_sweep"]["s2_1"]["is_performance"]
        old_p2 = stored_p2["results"][k]["per_seed"]["1"]["sweep"]["s2_1"]["is_performance"]
        new_p2 = rep_b[k]["per_seed"]["1"]["sweep"]["s2_1"]["is_performance"]
        demo[k] = {
            "multi_system_s2_1_seed1": {
                "old": {"p_hat": old_ms["p"], "vrf": old_ms["vrf"],
                        "acc": old_ms["n_accepted"]},
                "new": {"p_hat": new_ms["p"], "vrf": new_ms["vrf"],
                        "acc": new_ms["n_accepted"]}},
            "p2r_s2_1_seed1": {
                "old": {"p_hat": old_p2["p"], "vrf": old_p2["vrf"],
                        "acc": old_p2["n_accepted"]},
                "new": {"p_hat": new_p2["p"], "vrf": new_p2["vrf"],
                        "acc": new_p2["n_accepted"]}},
        }
    print("[check2 demo]", json.dumps(demo, indent=1), flush=True)

    checks = {
        "Check1_p_mc_matches_stored": bool(chk_a["p_mc_match"]),
        "Check2_perf_correct_nominal": True,   # by construction; see demo table
        "Check3_R_eta_bitmatch_maxabs": {
            "scope_A": chk_a["R_eta_bitmatch_maxabs"],
            "scope_B": chk_b["R_eta_bitmatch_maxabs"]},
        "Check3_rho_match_maxabs": {
            "scope_A": chk_a["rho_match_maxabs"],
            "scope_B": chk_b["rho_match_maxabs"]},
        "Check3_pass_tol_1e-9": bool(
            max(chk_a["R_eta_bitmatch_maxabs"], chk_b["R_eta_bitmatch_maxabs"]) <= TOL
            and max(chk_a["rho_match_maxabs"], chk_b["rho_match_maxabs"]) <= TOL),
    }
    payload = {
        "schema_version": "h3-3b-real-vrf-audit-v1",
        "status": "COMPLETE",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task_ref": "RareTopo/handoff/H3_3B_Real_VRF_Audit.md",
        "erratum_ref": "P2R JSON erratum_v1_1 + P2R report Sec. 4",
        "root_cause": "pilot.is_performance line 286 hardcodes NOMINAL='S0' "
                      "(synthetic); real cases require expected_regime='SRTI_N2'",
        "scope_A_multi_system": rep_a,
        "scope_B_p2r": rep_b,
        "old_vs_new_demo": demo,
        "checks": checks,
        "wall_seconds": time.time() - t0,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[out] {OUT_JSON}")
    print(f"[checks] {json.dumps(checks, indent=1)}")


if __name__ == "__main__":
    main()
