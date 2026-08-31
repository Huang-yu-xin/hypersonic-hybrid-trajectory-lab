"""M3 -- scalar Layer A counterfactual benchmark driver
(task Sec. 13-23; run order stage M3-4).

Per (config, seed), ONE locked shared stage (frozen M1-D selection + mean +
frozen SLSQP weights on the unit family; ONE 20k pilot) feeds:

    gradient estimation   importance / responsibility / ESS_grad / bootstrap CI
    CRN-matched arms      BASE | WIDEN(e^{+.20}) | SHRINK(e^{-.20})
                          Layer A fixed weights pi_C0 on every arm
    GRADIENT action path  pred = arm(decision); opposite = mirrored arm;
                          HOLD actions deploy the base arm
    M2 HDR diagnostic     frozen descriptive region object, report-only

Simulator-call honesty (task Sec. 22):
    scientific_audit_calls  = pilot_n + 3 * final_eval_n
    deployable_method_calls = pilot_n + final_eval_n
(the chosen-action evaluation reuses an already-computed diagnostic arm; the
opposite-direction scientific diagnostic is never counted toward deployable VRF).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.event_semantics import event_indicator_from_topology
from hyptraj.m1.proposal_update import LEGALITY_MIN_EIG
from hyptraj.m1d.experiments import (
    SEEDS,
    config_from_record,
    load_freeze,
    ref_views,
)
from hyptraj.m2.covariance_policy import (
    CovGaussianMixtureProposal,
    add_component_cov,
    evaluate_variant,
    run_shared_stage,
)
from hyptraj.m2.covariance_projection import check_legality_frozen
from hyptraj.m3.covariance_gradient import (
    MixtureSpec,
    component_responsibility,
)
from hyptraj.m3.direction_policy import DirectionRule, evaluation_best_direction, step_sign_for
from hyptraj.m3.gradient_estimator import (
    scalar_gradient_estimate,
    stratified_bootstrap_gradient_ci,
    variance_mass_importance,
)
from hyptraj.m3.metrics import build_trial_record

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "phase_m3"
FREEZE_JSON = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"
FREEZE_SHA = hashlib.sha256(FREEZE_JSON.read_bytes()).hexdigest()
CFG = json.loads((REPO / "configs" / "phase_m3"
                  / "m3_scalar_gradient_v0.json").read_text(encoding="utf-8"))

FROZEN_IDS = list(CFG["frozen_configs"])
PN = int(CFG["protocol_locked"]["pilot_n_per_round"])
ALPHA = float(CFG["protocol_locked"]["alpha_p"])
EVAL_N = int(CFG["protocol_locked"]["final_eval_n"])
ETA = 0.8                                    # frozen selector bandwidth (M1-D)
DELTA_THETA_MAIN = float(CFG["step_policy_locked"]["delta_theta_main"])
ESS_MIN = float(CFG["gradient_formula_locked"]["ess_grad"]["threshold"])
N_BOOT = int(CFG["bootstrap_locked"]["n_bootstrap_replicates"])
TIE_TOL = float(CFG["counterfactual_protocol_locked"]
                ["relative_tie_tolerance"])
TAGS = {"h3": CFG["parent_tags"]["h3"], "m1": CFG["parent_tags"]["m1_v0"],
        "m1d": CFG["parent_tags"]["m1d"], "m2": CFG["parent_tags"]["m2"]}
SCHEMA = CFG["outputs_locked"]["record_schema_version"]


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def _batch_meta(stage_name: str) -> dict:
    return {
        "schema_version": "raretopo-m3-batch-v0",
        "record_schema_version": SCHEMA,
        "stage": stage_name,
        "benchmark_freeze_hash": FREEZE_SHA,
        "m2_tag_commit": CFG["parent_tags"]["m2_frozen_head"],
        "git_commit": _git_head(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": {"n_pilot": PN, "alpha_p": ALPHA, "n_eval": EVAL_N,
                     "eta": ETA, "seeds": list(SEEDS),
                     "delta_theta_main": DELTA_THETA_MAIN,
                     "ess_min": ESS_MIN, "n_bootstrap": N_BOOT,
                     "tie_tol": TIE_TOL},
        "call_accounting_rule": {
            "scientific_audit_calls_per_trial": PN + 3 * EVAL_N,
            "deployable_method_calls_per_trial": PN + EVAL_N},
        "event_semantics": {
            "schema_version": 2,
            "topology_event": "label != TopologyLabel.NOMINAL",
            "estimator_indicator": "I[topology_event]",
        },
        "evidence_repair": {
            "repair_id": "ER-1",
            "run_kind": "isolated_corrected_replay",
            "historical_results_immutable": True,
        },
    }


def _save(batch: dict, rel_path: Path) -> None:
    rel_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    print(f"[saved] {rel_path.relative_to(REPO)}", flush=True)


_FREEZE_CACHE: dict[str, dict] = {}


def _freeze_records() -> dict[str, dict]:
    if not _FREEZE_CACHE:
        for r in load_freeze()["benchmark_configs"]:
            _FREEZE_CACHE[r["config_id"]] = r
    return _FREEZE_CACHE


# --------------------------------------------------------------------------- #
# trial core
# --------------------------------------------------------------------------- #
def _scaled_proposal(stage, theta_shift: float) -> CovGaussianMixtureProposal:
    """Layer A proposal with the newborn covariance scaled by e^{theta_shift}."""
    dim = stage.z.shape[1]
    sigma_new = float(np.exp(theta_shift)) * np.eye(dim)
    prop = add_component_cov(stage.q0_cov, stage.region.centroid,
                             sigma_new, mode_id=str(stage.selected_mode))
    return CovGaussianMixtureProposal(
        centers=prop.centers, weights=stage.pi_c0.copy(), covs=prop.covs,
        component_mode_ids=prop.component_mode_ids, legality_checked=True,
        min_eig_sigma_minus_halfI=prop.min_eig_sigma_minus_halfI)


def _selection_crosscheck(cid: str, seed: int, selected_mode) -> bool | None:
    try:
        arch = json.loads((REPO / "results" / "phase_m1d" / "d1_selection_only"
                           / "layer_a_one_birth_v1.json").read_text(
                               encoding="utf-8"))
        for entry in arch["records_by_config"]:
            if entry.get("config_id") != cid:
                continue
            for r in entry["records"]:
                if int(r.get("seed", -1)) == int(seed) \
                        and str(r.get("method")) == "variance_selector":
                    archived = (r.get("selected_modes") or [None])[0]
                    return bool(archived == selected_mode)
    except Exception:
        return None
    return None


def run_trial(bc, frec, cid: str, seed: int) -> dict:
    t0 = time.perf_counter()
    tags = TAGS

    def empty(reason: str) -> dict:
        rec = build_trial_record(
            tags=tags, config_id=cid, seed=int(seed), selected_mode=None,
            component_index=None, layer="fixed_weights",
            gradient={"decision": "HOLD_INVALID"},
            counterfactual={}, validity={"stop_reason": reason})
        rec["_runtime_s"] = round(time.perf_counter() - t0, 3)
        return rec

    stage = run_shared_stage(bc, int(seed), n_pilot=PN, alpha=ALPHA, eta=ETA,
                             n_eval=EVAL_N)
    if stage.stop_reason is not None or stage.selected_mode is None \
            or stage.region is None:
        return empty(stage.stop_reason or "no_selection")

    dim = stage.z.shape[1]
    prop_point = _scaled_proposal(stage, 0.0)
    k_idx = prop_point.n_components - 1
    mk = np.asarray(prop_point.centers[k_idx], dtype=float)
    sigma_k0 = np.asarray(prop_point.covs[k_idx], dtype=float)
    s2_base = float(np.trace(sigma_k0) / dim)
    pi_all = np.asarray(prop_point.weights, dtype=float)

    ind_event = event_indicator_from_topology(stage.labels).astype(float)
    a_vec = variance_mass_importance(stage.z, pi_all,
                                     np.asarray(prop_point.centers,
                                                dtype=float),
                                     list(prop_point.covs),
                                     stage.logp, stage.logr, ind_event)
    spec_point = MixtureSpec(pi_all, prop_point.centers,
                             tuple(np.asarray(c, dtype=float)
                                   for c in prop_point.covs))
    resp = component_responsibility(spec_point, stage.z, k_idx)
    sq = np.einsum("ni,ni->n", stage.z - mk[None, :], stage.z - mk[None, :])

    est = scalar_gradient_estimate(a_vec, resp, sq, s2=s2_base, dim=dim)
    est.update(stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, stage.source_strata, s2=s2_base, dim=dim,
        n_bootstrap=N_BOOT, bootstrap_seed_key=(int(seed), 424243)))

    decision = DirectionRule(ess_min=ESS_MIN).decide(
        validity_ok=bool(est["valid_pointwise"]),
        validity_reasons=tuple(est["problems"]),
        ess_grad=float(est["ESS_grad"]),
        g_ci_low=float(est["g_ci_low"]),
        g_ci_high=float(est["g_ci_high"]))
    step_sign = step_sign_for(decision, DELTA_THETA_MAIN)

    reasons: list[str] = []
    legal_gradpoint, _ = check_legality_frozen(sigma_k0)
    legal_step, _ = check_legality_frozen(
        float(np.exp(np.log(s2_base) + step_sign)) * np.eye(dim))
    if not legal_gradpoint:
        reasons.append("illegal_gradient_point_covariance")
    if not legal_step:
        reasons.append("illegal_perturbed_covariance")
    legality_ok = bool(legal_gradpoint and legal_step)

    # ---- three CRN-matched independent-eval arms ---------------------------
    arms_raw: dict[str, dict] = {}
    for tag, shift in (("base", 0.0), ("widen", +DELTA_THETA_MAIN),
                       ("shrink", -DELTA_THETA_MAIN)):
        prop_arm = _scaled_proposal(stage, shift)
        ev = evaluate_variant(stage, prop_arm, EVAL_N)
        ok_leg, _me = check_legality_frozen(prop_arm.covs[k_idx])
        from hyptraj.m1d.metrics import attach_vrfs
        rv = ref_views(frec)
        attach_vrfs(ev, p_ref=float(sum(rv["P"].values())),
                    budget_total=int(PN + EVAL_N))
        ev["L_table"] = {str(k): float(v) for k, v in ev["L_table"].items()}
        ev["mode_L"] = dict(ev["L_table"])
        ev["n"] = int(ev["n_eval"])
        arms_raw[tag] = {"evaluation": ev, "legality_passed": bool(ok_leg)}

    m2v = {t: float(v["evaluation"]["M2_hat"]) for t, v in arms_raw.items()}
    best = evaluation_best_direction(m2v["base"], m2v["widen"],
                                     m2v["shrink"], TIE_TOL)
    pred_key = ("widen" if decision == "WIDEN"
                else "shrink" if decision == "SHRINK" else "base")
    opp_key = ("shrink" if pred_key == "widen"
               else "widen" if pred_key == "shrink" else "base")

    grad_block = {
        "M2_hat": float(est["M2_hat"]),
        "responsibility_mass": float(est["mu_r_hat"]),
        "D_hat": float(est["D_hat"]),
        "g_hat": float(est["g_hat"]),
        "g_ci_low": float(est["g_ci_low"]),
        "g_ci_high": float(est["g_ci_high"]),
        "ESS_grad": float(est["ESS_grad"]),
        "decision": decision,
        "s2_base": s2_base,
        "problems": list(est["problems"]),
    }
    cf_block = {
        "delta_theta": float(DELTA_THETA_MAIN),
        "M2_base": m2v["base"], "M2_widen": m2v["widen"],
        "M2_shrink": m2v["shrink"],
        "M2_pred": m2v[pred_key], "M2_opposite": m2v[opp_key],
        "evaluation_best_direction": best,
        "pred_arm": pred_key, "opposite_arm": opp_key,
        "applied_theta_shift": float(step_sign),
    }

    region = stage.region
    hdr_trace = float(np.trace(region.cov))
    conflict = bool(decision == "WIDEN" and hdr_trace / dim < s2_base)

    evaluation_block = {
        "P_hat": arms_raw[pred_key]["evaluation"]["P_hat"],
        "VRF_proposal": arms_raw[pred_key]["evaluation"]["VRF_proposal"],
        "VRF_budget": arms_raw[pred_key]["evaluation"]["VRF_budget"],
        "VRF_budget_grad_path": arms_raw[pred_key]["evaluation"]["VRF_budget"],
        "mode_L": dict(arms_raw[pred_key]["evaluation"]["mode_L"]),
        "mode_L_base": dict(arms_raw["base"]["evaluation"]["mode_L"]),
        "mode_L_pred": dict(arms_raw[pred_key]["evaluation"]["mode_L"]),
        "n": EVAL_N,
        "scientific_audit_calls": PN + 3 * EVAL_N,
        "deployable_method_calls": PN + EVAL_N,
    }
    validity_block = {
        "selected_mode_lock": True,
        "mean_lock_dev_abs": float(stage.centroid_frozen_check),
        "crosscheck_matches_archived_m1d":
            _selection_crosscheck(cid, seed, stage.selected_mode),
        "legality_all_arms_passed":
            bool(legality_ok and all(v["legality_passed"]
                                     for v in arms_raw.values())),
        "validity_reasons": reasons,
        "legal_min_eig_frozen": float(LEGALITY_MIN_EIG),
        "pilot_rng": "[seed,101]", "eval_rng_tag": 900001,
        "bootstrap_seed_rule": "[seed,424243]",
        "component_count_fixed": int(prop_point.n_components),
    }
    rec = build_trial_record(
        tags=tags, config_id=cid, seed=int(seed),
        selected_mode=str(stage.selected_mode),
        component_index=int(k_idx), layer="fixed_weights",
        gradient=grad_block, counterfactual=cf_block,
        m2_diagnostic={
            "hdr_covariance": np.asarray(region.cov).tolist(),
            "hdr_trace": hdr_trace,
            "hdr_isotropic_scale": float(hdr_trace / dim),
            "conflict_with_gradient": conflict,
            "note": "report-only failed-M2 descriptive object (task Sec.17)",
        },
        evaluation=evaluation_block, validity=validity_block)
    rec["_arms"] = {t: {"M2_hat": v["evaluation"]["M2_hat"],
                        "P_hat": v["evaluation"]["P_hat"],
                        "var_hat": v["evaluation"]["var_hat"],
                        "VRF_proposal": v["evaluation"]["VRF_proposal"],
                        "VRF_budget": v["evaluation"]["VRF_budget"],
                        "L_table": v["evaluation"]["L_table"]}
                    for t, v in arms_raw.items()}
    rec["_weights_final"] = [float(x) for x in pi_all]
    rec["_state"] = {
        "component_mean": [float(x) for x in mk],
        "component_weight_pi_C0": float(pi_all[k_idx]),
        "base_covariance": sigma_k0.tolist(),
        "centers_all": [[float(x) for x in row]
                        for row in prop_point.centers],
        "eligible_candidates": list(stage.eligible),
    }
    rec["_runtime_s"] = round(time.perf_counter() - t0, 3)
    return rec


# --------------------------------------------------------------------------- #
# stages
# --------------------------------------------------------------------------- #
def summarize(records_by_config) -> dict:
    counts: dict[str, int] = {}
    total = 0
    cross_bad = 0
    cross_none = 0
    legality_bad = 0
    conflicts = 0
    for e in records_by_config:
        for r in e["records"]:
            d = r["gradient"].get("decision", "?")
            counts[d] = counts.get(d, 0) + 1
            total += 1
            cc = r.get("validity", {}).get("crosscheck_matches_archived_m1d")
            if cc is None:
                cross_none += 1
            elif cc is False:
                cross_bad += 1
            if r.get("validity", {}).get("legality_all_arms_passed") is False:
                legality_bad += 1
            if r.get("m2_diagnostic", {}).get("conflict_with_gradient"):
                conflicts += 1
    return {"total_trials": total, "decision_counts": counts,
            "crosscheck_false": cross_bad, "crosscheck_unavailable": cross_none,
            "legality_failures": legality_bad, "hdr_conflicts": conflicts}


# --------------------------------------------------------------------------- #
# Layer B -- frozen SLSQP refit per arm (M3-7; CANNOT rescue Layer A)
# --------------------------------------------------------------------------- #
def _layer_b_proposal(stage, theta_shift: float) -> CovGaussianMixtureProposal:
    from hyptraj.m1.mixture_weights import optimize_mixture_weights
    from hyptraj.m2.covariance_policy import component_log_densities_cov
    dim = stage.z.shape[1]
    sigma_new = float(np.exp(theta_shift)) * np.eye(dim)
    grown = add_component_cov(stage.q0_cov, stage.region.centroid,
                              sigma_new, mode_id=str(stage.selected_mode))
    indicators = event_indicator_from_topology(stage.labels).astype(float)
    logq_ji = component_log_densities_cov(stage.z, grown.centers, grown.covs)
    res = optimize_mixture_weights(logq_ji, stage.logp, stage.logr,
                                   indicators, pi0=grown.weights.copy(),
                                   floor=0.0, maxiter=500)
    if not res.success:
        raise RuntimeError(f"Layer B weight refit failed: {res.message}")
    return CovGaussianMixtureProposal(
        centers=grown.centers, weights=np.asarray(res.weights, dtype=float),
        covs=grown.covs, component_mode_ids=grown.component_mode_ids,
        legality_checked=True,
        min_eig_sigma_minus_halfI=min(
            float(grown.min_eig_sigma_minus_halfI),
            float(np.linalg.eigvalsh(symmetrized(sigma_new))[0]))), {
        "solver": "frozen SLSQP (M1)",
        "kkt_residue": float(res.kkt_residue),
        "message": str(res.message)}


def symmetrized(m):
    return 0.5 * (np.asarray(m, dtype=float)
                  + np.asarray(m, dtype=float).T)


def run_trial_layer_b(bc, frec, cid: str, seed: int) -> dict:
    """Same gradient decision machinery as Layer A; arms re-weighted by the
    frozen SLSQP core before evaluation. Weight solver metadata recorded."""
    t0 = time.perf_counter()
    stage = run_shared_stage(bc, int(seed), n_pilot=PN, alpha=ALPHA, eta=ETA,
                             n_eval=EVAL_N)

    def empty(reason: str) -> dict:
        rec = build_trial_record(
            tags=TAGS, config_id=cid, seed=int(seed), selected_mode=None,
            component_index=None, layer="shape_reweight",
            gradient={"decision": "HOLD_INVALID"},
            counterfactual={}, validity={"stop_reason": reason})
        rec["_runtime_s"] = round(time.perf_counter() - t0, 3)
        return rec

    if stage.stop_reason is not None or stage.selected_mode is None \
            or stage.region is None:
        return empty(stage.stop_reason or "no_selection")

    dim = stage.z.shape[1]
    prop_point = _scaled_proposal(stage, 0.0)
    k_idx = prop_point.n_components - 1
    mk = np.asarray(prop_point.centers[k_idx], dtype=float)
    s2_base = float(np.trace(np.asarray(prop_point.covs[k_idx])) / dim)
    pi_all = np.asarray(prop_point.weights, dtype=float)

    ind_event = event_indicator_from_topology(stage.labels).astype(float)
    a_vec = variance_mass_importance(stage.z, pi_all,
                                     np.asarray(prop_point.centers,
                                                dtype=float),
                                     list(prop_point.covs),
                                     stage.logp, stage.logr, ind_event)
    spec_point = MixtureSpec(pi_all, prop_point.centers,
                             tuple(np.asarray(c, dtype=float)
                                   for c in prop_point.covs))
    resp = component_responsibility(spec_point, stage.z, k_idx)
    sq = np.einsum("ni,ni->n", stage.z - mk[None, :], stage.z - mk[None, :])
    est = scalar_gradient_estimate(a_vec, resp, sq, s2=s2_base, dim=dim)
    est.update(stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, stage.source_strata, s2=s2_base, dim=dim,
        n_bootstrap=N_BOOT, bootstrap_seed_key=(int(seed), 424243)))
    decision = DirectionRule(ess_min=ESS_MIN).decide(
        validity_ok=bool(est["valid_pointwise"]),
        validity_reasons=tuple(est["problems"]),
        ess_grad=float(est["ESS_grad"]),
        g_ci_low=float(est["g_ci_low"]),
        g_ci_high=float(est["g_ci_high"]))

    arms_raw: dict[str, dict] = {}
    solver_infos: dict[str, dict] = {}
    for tag, shift in (("base", 0.0), ("widen", +DELTA_THETA_MAIN),
                       ("shrink", -DELTA_THETA_MAIN)):
        prop_lb, info = _layer_b_proposal(stage, shift)
        ev = evaluate_variant(stage, prop_lb, EVAL_N)
        ok_leg, _me = check_legality_frozen(prop_lb.covs[k_idx])
        from hyptraj.m1d.metrics import attach_vrfs
        rv = ref_views(frec)
        attach_vrfs(ev, p_ref=float(sum(rv["P"].values())),
                    budget_total=int(PN + EVAL_N))
        ev["L_table"] = {str(k): float(v) for k, v in ev["L_table"].items()}
        ev["mode_L"] = dict(ev["L_table"])
        ev["n"] = int(ev["n_eval"])
        arms_raw[tag] = {"evaluation": ev, "legality_passed": bool(ok_leg)}
        solver_infos[tag] = info

    m2v = {t: float(v["evaluation"]["M2_hat"]) for t, v in arms_raw.items()}
    best = evaluation_best_direction(m2v["base"], m2v["widen"],
                                     m2v["shrink"], TIE_TOL)
    pred_key = ("widen" if decision == "WIDEN"
                else "shrink" if decision == "SHRINK" else "base")
    opp_key = ("shrink" if pred_key == "widen"
               else "widen" if pred_key == "shrink" else "base")

    grad_block = {
        "M2_hat": float(est["M2_hat"]),
        "responsibility_mass": float(est["mu_r_hat"]),
        "D_hat": float(est["D_hat"]),
        "g_hat": float(est["g_hat"]),
        "g_ci_low": float(est["g_ci_low"]),
        "g_ci_high": float(est["g_ci_high"]),
        "ESS_grad": float(est["ESS_grad"]),
        "decision": decision, "s2_base": s2_base,
        "problems": list(est["problems"]),
        "note": "decision layer-A-identical; arms re-weighted (Layer B)",
    }
    cf_block = {
        "delta_theta": float(DELTA_THETA_MAIN),
        "M2_base": m2v["base"], "M2_widen": m2v["widen"],
        "M2_shrink": m2v["shrink"],
        "M2_pred": m2v[pred_key], "M2_opposite": m2v[opp_key],
        "evaluation_best_direction": best,
        "pred_arm": pred_key, "opposite_arm": opp_key,
        "applied_theta_shift": float(step_sign_for(decision,
                                                   DELTA_THETA_MAIN)),
    }
    evaluation_block = {
        "P_hat": arms_raw[pred_key]["evaluation"]["P_hat"],
        "VRF_proposal": arms_raw[pred_key]["evaluation"]["VRF_proposal"],
        "VRF_budget": arms_raw[pred_key]["evaluation"]["VRF_budget"],
        "VRF_budget_grad_path": arms_raw[pred_key]["evaluation"]["VRF_budget"],
        "mode_L": dict(arms_raw[pred_key]["evaluation"]["mode_L"]),
        "mode_L_base": dict(arms_raw["base"]["evaluation"]["mode_L"]),
        "mode_L_pred": dict(arms_raw[pred_key]["evaluation"]["mode_L"]),
        "n": EVAL_N,
        "scientific_audit_calls": PN + 3 * EVAL_N,
        "deployable_method_calls": PN + EVAL_N,
        "weight_solver_per_arm": solver_infos,
    }
    rec = build_trial_record(
        tags=TAGS, config_id=cid, seed=int(seed),
        selected_mode=str(stage.selected_mode),
        component_index=int(k_idx), layer="shape_reweight",
        gradient=grad_block, counterfactual=cf_block,
        m2_diagnostic={"hdr_covariance":
                       np.asarray(stage.region.cov).tolist(),
                       "hdr_trace": float(np.trace(stage.region.cov)),
                       "hdr_isotropic_scale":
                           float(np.trace(stage.region.cov) / dim)},
        evaluation=evaluation_block,
        validity={"selected_mode_lock": True,
                  "mean_lock_dev_abs": float(stage.centroid_frozen_check),
                  "crosscheck_matches_archived_m1d":
                      _selection_crosscheck(cid, seed, stage.selected_mode),
                  "legality_all_arms_passed":
                      bool(all(v["legality_passed"]
                               for v in arms_raw.values())),
                  "legal_min_eig_frozen": float(LEGALITY_MIN_EIG)})
    rec["_arms"] = {t: {"M2_hat": v["evaluation"]["M2_hat"]}
                    for t, v in arms_raw.items()}
    rec["_weights_final"] = [float(x) for x in
                             arms_raw[pred_key]["evaluation"].get(
                                 "_unused", pi_all)]
    rec["_runtime_s"] = round(time.perf_counter() - t0, 3)
    return rec


def run_layer_b() -> None:
    freeze = _freeze_records()
    out_records = []
    t_start = time.perf_counter()
    for cid in FROZEN_IDS:
        bc = config_from_record(freeze[cid])
        frec = freeze[cid]
        rows, t0 = [], time.perf_counter()
        for seed in SEEDS:
            rows.append(run_trial_layer_b(bc, frec, cid, seed))
        print(f"  [LB {cid}] {len(rows)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        out_records.append({"config_id": cid, "records": rows})
    batch = _batch_meta("m3_scalar_layer_B_reweight")
    batch["wall_clock_s"] = round(time.perf_counter() - t_start, 1)
    batch["summary"] = summarize(out_records)
    batch["records_by_config"] = out_records
    _save(batch, RESULTS / "scalar_layer_b" / "scalar_layer_b_v1.json")


# --------------------------------------------------------------------------- #
# Step sensitivity -- dose-response only (M3-8); MAIN stays 0.20 everywhere
# --------------------------------------------------------------------------- #
SENS_DELTAS = json.loads((REPO / "configs" / "phase_m3"
                          / "m3_step_sensitivity.json")
                         .read_text(encoding="utf-8"))["delta_theta_values"]


def run_sensitivity() -> None:
    freeze = _freeze_records()
    out_records = []
    t_start = time.perf_counter()
    for cid in FROZEN_IDS:
        bc = config_from_record(freeze[cid])
        frec = freeze[cid]
        rows, t0 = [], time.perf_counter()
        for seed in SEEDS:
            rows.append(run_trial_sensitivity(bc, frec, cid, seed))
        print(f"  [SENS {cid}] {len(rows)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        out_records.append({"config_id": cid, "records": rows})
    batch = _batch_meta("m3_step_sensitivity")
    batch["delta_theta_values"] = SENS_DELTAS
    batch["wall_clock_s"] = round(time.perf_counter() - t_start, 1)
    batch["summary"] = {"total_trials": sum(len(e["records"])
                                            for e in out_records)}
    batch["records_by_config"] = out_records
    _save(batch, RESULTS / "sensitivity" / "step_sensitivity_v1.json")


def run_trial_sensitivity(bc, frec, cid: str, seed: int) -> dict:
    """Evaluate every preregistered |delta| arm once; decisions are
    delta-INDEPENDENT (CI-sign rule happens before stepping)."""
    stage = run_shared_stage(bc, int(seed), n_pilot=PN, alpha=ALPHA, eta=ETA,
                             n_eval=EVAL_N)
    base_rec = {"config_id": cid, "seed": int(seed)}
    if stage.stop_reason is not None or stage.selected_mode is None \
            or stage.region is None:
        base_rec["stop_reason"] = stage.stop_reason or "no_selection"
        return base_rec

    dim = stage.z.shape[1]
    prop_point = _scaled_proposal(stage, 0.0)
    k_idx = prop_point.n_components - 1
    mk = np.asarray(prop_point.centers[k_idx], dtype=float)
    s2_base = float(np.trace(np.asarray(prop_point.covs[k_idx])) / dim)
    pi_all = np.asarray(prop_point.weights, dtype=float)

    ind_event = event_indicator_from_topology(stage.labels).astype(float)
    a_vec = variance_mass_importance(stage.z, pi_all,
                                     np.asarray(prop_point.centers,
                                                dtype=float),
                                     list(prop_point.covs),
                                     stage.logp, stage.logr, ind_event)
    spec_point = MixtureSpec(pi_all, prop_point.centers,
                             tuple(np.asarray(c, dtype=float)
                                   for c in prop_point.covs))
    resp = component_responsibility(spec_point, stage.z, k_idx)
    sq = np.einsum("ni,ni->n", stage.z - mk[None, :], stage.z - mk[None, :])
    est = scalar_gradient_estimate(a_vec, resp, sq, s2=s2_base, dim=dim)
    est.update(stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, stage.source_strata, s2=s2_base, dim=dim,
        n_bootstrap=N_BOOT, bootstrap_seed_key=(int(seed), 424243)))
    decision = DirectionRule(ess_min=ESS_MIN).decide(
        validity_ok=bool(est["valid_pointwise"]),
        validity_reasons=tuple(est["problems"]),
        ess_grad=float(est["ESS_grad"]),
        g_ci_low=float(est["g_ci_low"]),
        g_ci_high=float(est["g_ci_high"]))

    scales = sorted({0.0} | {+d for d in SENS_DELTAS}
                    | {-d for d in SENS_DELTAS})
    m2_at: dict[str, float] = {}
    vrf_at: dict[str, float] = {}
    from hyptraj.m1d.metrics import attach_vrfs
    rv = ref_views(frec)
    p_ref_union = float(sum(rv["P"].values()))
    for sh in scales:
        prop_arm = _scaled_proposal(stage, sh)
        ev = evaluate_variant(stage, prop_arm, EVAL_N)
        attach_vrfs(ev, p_ref=p_ref_union, budget_total=int(PN + EVAL_N))
        m2_at[f"{sh:+.2f}"] = float(ev["M2_hat"])
        vrf_at[f"{sh:+.2f}"] = float(ev["VRF_budget"])

    per_delta = {}
    for dlt in SENS_DELTAS:
        sign = step_sign_for(decision, dlt)
        pred_k = f"{(+sign):+.2f}" if sign != 0 else "+0.00"
        opp_k = ("base") if sign == 0 else (
            f"{(-sign):+.2f}")
        base_k = "+0.00"
        # widen/shrink scientific labels under THIS delta magnitude
        wk = f"{(+dlt):+.2f}"
        sk = f"{(-dlt):+.2f}"
        best_here = evaluation_best_direction(m2_at[base_k],
                                              m2_at.get(wk, m2_at[base_k]),
                                              m2_at.get(sk, m2_at[base_k]),
                                              TIE_TOL)
        per_delta[str(dlt)] = {
            "decision": decision,
            "pred_M2": m2_at.get(pred_k, m2_at[base_k]),
            "opposite_M2": m2_at.get(opp_k, m2_at[base_k]),
            "base_M2": m2_at[base_k],
            "ratio_pred_base": (m2_at.get(pred_k, m2_at[base_k])
                                / m2_at[base_k]),
            "ratio_pred_opposite": (m2_at.get(pred_k, m2_at[base_k])
                                    / m2_at.get(opp_k, m2_at[base_k])),
            "evaluation_best_direction": best_here,
            "deployable_vrf_pred": vrf_at.get(pred_k, vrf_at[base_k]),
        }
    base_rec.update({
        "schema_version": SCHEMA, "h3_tag": TAGS["h3"], "m1_tag": TAGS["m1"],
        "m1d_tag": TAGS["m1d"], "m2_tag": TAGS["m2"], "layer": "fixed_weights",
        "selected_mode": str(stage.selected_mode),
        "gradient_decision": decision,
        "g_hat": float(est["g_hat"]), "ESS_grad": float(est["ESS_grad"]),
        "per_delta_theta": per_delta,
        "arms_M2": m2_at,
        "calls": {"scientific_audit": PN + len(scales) * EVAL_N,
                  "note": "shared pilot + one eval per distinct scale"}})
    return base_rec


def run_layer_a() -> None:
    freeze = _freeze_records()
    out_records = []
    t_start = time.perf_counter()
    for cid in FROZEN_IDS:
        bc = config_from_record(freeze[cid])
        frec = freeze[cid]
        rows, t0 = [], time.perf_counter()
        for seed in SEEDS:
            rows.append(run_trial(bc, frec, cid, seed))
        print(f"  [{cid}] {len(rows)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        out_records.append({"config_id": cid, "records": rows})
    batch = _batch_meta("m3_scalar_layer_A_main")
    batch["wall_clock_s"] = round(time.perf_counter() - t_start, 1)
    batch["summary"] = summarize(out_records)
    batch["records_by_config"] = out_records
    _save(batch, RESULTS / "scalar_layer_a" / "scalar_layer_a_v1.json")


STAGES = {
    "layer_a_main": run_layer_a,
    "layer_b": run_layer_b,
    "sensitivity": run_sensitivity,
}


def main() -> int:
    global RESULTS
    ap = argparse.ArgumentParser(description="M3 scalar benchmark driver")
    ap.add_argument("--stage", choices=sorted(STAGES), required=True)
    ap.add_argument(
        "--results-root", type=Path, default=RESULTS,
        help="isolated output root (defaults to the historical phase_m3 path)",
    )
    args = ap.parse_args()
    RESULTS = args.results_root.resolve()
    STAGES[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
