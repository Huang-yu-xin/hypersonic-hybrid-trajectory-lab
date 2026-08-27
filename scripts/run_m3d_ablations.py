"""M3-D D8 -- required ablations (task Sec. 33) + M3-v0 replay control.

D-C  frozen step sensitivity delta in {0.10, 0.40} extra diagnostic arms,
     evaluated with the SAME frozen evaluator + CRN stream tag per trial;
     main stays 0.20 (layer_a batch untouched).
D-D  point-sign vs CI-sign diagnostic -- pure recomputation from stored
     g_hat in the Layer A batch (zero simulator calls).
D-A / D-B / D-E  derived report tables computed directly from stored data.
D-F  M3-v0 replay control on the ORIGINAL unit-scale proposal states
     (per-seed shared stages replicating the M3-v0 benchmark exactly);
     expectation: mostly WIDEN, Gradient ~= Always-Widen; NEVER enters
     headline gates (task Sec. 31).

Outputs under results/phase_m3d/ablations/.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1.proposal_update import LEGALITY_MIN_EIG
from hyptraj.m1d.experiments import (
    config_from_record,
    load_freeze,
    ref_views,
)
from hyptraj.m1d.metrics import attach_vrfs, eval_proposal_is
from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal, run_shared_stage
from hyptraj.m3.covariance_gradient import MixtureSpec, component_responsibility
from hyptraj.m3.direction_policy import DirectionRule
from hyptraj.m3.gradient_estimator import (
    scalar_gradient_estimate,
    stratified_bootstrap_gradient_ci,
    variance_mass_importance,
)
from hyptraj.m3d.benchmark_states import ANCHOR_SEED, assemble_state, state_arms
from hyptraj.m3d.metrics import three_class_metrics

REPO = Path(__file__).resolve().parents[1]
AB = REPO / "results" / "phase_m3d" / "ablations"
LAYA = REPO / "results" / "phase_m3d" / "layer_a" / "m3d_layer_a_v1.json"
FREEZE_DOC = REPO / "docs" / "phase_m3d" / "M3_D_Benchmark_Freeze.json"
PN, EVAL_N, ALPHA, ETA = 20_000, 100_000, 0.5, 0.8


def _git():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _stamp(tag, extra=None):
    base = {"schema_version": "raretopo-m3d-ablation-v0",
            "amendment_generation": "post-AMENDMENT_1", "date_utc":
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_commit": _git(), "tag": tag}
    if extra:
        base.update(extra)
    return base


# --------------------------------------------------------------------------- #
# D-C step sensitivity (extra simulator draws)
# --------------------------------------------------------------------------- #
def dc_step_sensitivity(laya_recs) -> dict:
    freeze_doc = json.loads(FREEZE_DOC.read_text(encoding="utf-8"))
    bench = {r["config_id"]: r
             for r in load_freeze()["benchmark_configs"]}
    base_lookup = {(r["state_id"], r["seed"]):
                   r["arms"]["hold"]["M2"] for r in laya_recs}
    rows = []
    t0 = time.perf_counter()
    for s_rec in freeze_doc["states"]:
        bc = config_from_record(bench[s_rec["config_id"]])
        st = assemble_state(bc, float(s_rec["s2"]))
        assert not isinstance(st, dict)
        k = st.component_index
        base_arm = state_arms(st, 0.20)["base"]
        for seed in _SEEDS:
            m2_hold = base_lookup[(s_rec["state_id"], int(seed))]
            row = {"config_id": s_rec["config_id"],
                   "state_id": s_rec["state_id"], "seed": int(seed),
                   "base_s2": float(s_rec["s2"]),
                   "M2_base_delta0": m2_hold}
            for dlt in (0.10, 0.40):
                covs = list(base_arm.covs)
                covs[k] = st.s2 * float(np.exp(+dlt)) * np.eye(st.dim)
                wid = CovGaussianMixtureProposal(
                    centers=base_arm.centers.copy(),
                    weights=base_arm.weights.copy(),
                    covs=tuple(np.asarray(c, float) for c in covs),
                    component_mode_ids=base_arm.component_mode_ids,
                    legality_checked=True,
                    min_eig_sigma_minus_halfI=0.0)
                covs[k] = st.s2 * float(np.exp(-dlt)) * np.eye(st.dim)
                shr = CovGaussianMixtureProposal(
                    centers=base_arm.centers.copy(),
                    weights=base_arm.weights.copy(),
                    covs=tuple(np.asarray(c, float) for c in covs),
                    component_mode_ids=base_arm.component_mode_ids,
                    legality_checked=True,
                    min_eig_sigma_minus_halfI=0.0)
                ew = eval_proposal_is(wid, bc, int(seed), n_eval=EVAL_N)
                esh = eval_proposal_is(shr, bc, int(seed), n_eval=EVAL_N)
                row[f"M2_widen_{dlt}"] = float(ew["M2_hat"])
                row[f"M2_shrink_{dlt}"] = float(esh["M2_hat"])
            rows.append(row)

    def dose(delta, side):
        vals = [r[f"M2_{side}_{delta}"] / r["M2_base_delta0"]
                for r in rows]
        return {"median_ratio_to_base": float(np.median(vals)),
                "mean_ratio_to_base": float(np.mean(vals))}

    return _stamp("D_C_step_sensitivity", {
        "protocol": {"extra_deltas": [0.10, 0.40],
                     "eval_n": EVAL_N, "crn": "[seed,900001]"},
        "n_rows": len(rows),
        "dose_response": {f"delta_{d}": {
            f"{s}_arm": dose(d, s)
            for s in ("widen", "shrink")} for d in (0.10, 0.40)},
        "_runtime_note": f"{time.perf_counter() - t0:.0f}s"})


_SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]


# --------------------------------------------------------------------------- #
# derived ablations (no simulator calls)
# --------------------------------------------------------------------------- #
def dd_point_sign_vs_ci(recs) -> dict:
    """Point-sign policy: WIDEN if g_hat<0, SHRINK if g_hat>0 else HOLD."""
    def fold(raw):
        return raw if raw in ("WIDEN", "SHRINK") else "HOLD"

    y_true = [r["oracle_action"] for r in recs]
    yp_point = ["WIDEN" if r["gradient"]["g_hat"] < 0 else
                "SHRINK" if r["gradient"]["g_hat"] > 0 else "HOLD"
                for r in recs]
    yp_ci = [fold(r["validity"]["raw_decision_code"]) for r in recs]
    mp = three_class_metrics(y_true, yp_point)
    mc = three_class_metrics(y_true, yp_ci)
    return _stamp("D_D_point_sign_vs_CI_sign", {
        "point_sign": {k: v for k, v in mp.items()
                       if k != "confusion_matrix"},
        "ci_sign": {k: v for k, v in mc.items()
                    if k != "confusion_matrix"},
        "conclusion_locked": "MAIN REMAINS CI-SIGN (task Sec.33 D-D)"})


def da_gradient_vs_rules_per_class(recs) -> dict:
    """Per-class medians of each rule against its own BASE arm.

    LEGAL-DENOMINATOR DISCIPLINE (freeze audit 2026-08-27): trials whose
    comparator arm fails the FROZEN legality checker (always-shrink from
    s^2=0.55 -> min-eig 0.450 < 0.5) are EXCLUDED from that rule's channel
    entirely -- they may neither count as losses, wins, ties nor baseline
    for the fixed rule.  Raw layer_a records remain untouched."""
    out = {}
    n_excluded_as = 0
    by_class = {}
    for r in recs:
        by_class.setdefault(r["oracle_action"], []).append(r)
    for cls, rs in sorted(by_class.items()):
        ratios = {"GRADIENT": [], "ALWAYS_WIDEN": [], "ALWAYS_SHRINK": [],
                  "ALWAYS_HOLD": []}
        excluded_cls = 0
        for r in rs:
            b = r["arms"]["hold"]["M2"]
            if not r["validity"]["arm_legality_all_passed"]:
                # illegal comparator arm (shrink): counts for NO channel,
                # never as tie/base/value evidence
                excluded_cls += 1
                n_excluded_as += 1
                continue
            ratios["GRADIENT"].append(r["arms"]["gradient"]["M2"] / b)
            ratios["ALWAYS_WIDEN"].append(r["arms"]["widen"]["M2"] / b)
            ratios["ALWAYS_SHRINK"].append(r["arms"]["shrink"]["M2"] / b)
            ratios["ALWAYS_HOLD"].append(1.0)
        out[cls] = {k: {"median_ratio_to_BASE": float(np.median(v)),
                        "mean_ratio_to_BASE": float(np.mean(v)),
                        "n_legal": len(v)}
                    for k, v in ratios.items()}
        out[cls]["_excluded_illegal_shrink_trials"] = excluded_cls
    return _stamp("D_A_gradient_vs_fixed_per_class", {
        "legal_denominator_policy":
            "trials failing the frozen arm-legality checker are excluded "
            "from ALL rule channels at that trial (never tie/base/win)",
        "total_illegal_trials_excluded": n_excluded_as,
        "per_class": out})


def db_ess_stratification(recs) -> dict:
    buckets = [(20, 50), (50, 100), (100, 200), (200, float("inf"))]
    out = []
    for lo, hi in buckets:
        sel = [r for r in recs if lo <= r["gradient"]["ESS_grad"] < hi]
        if not sel:
            continue
        out.append({
            "ess_bucket": [lo, hi], "n_trials": len(sel),
            "action_correct_rate":
                float(np.mean([r["metrics"]["action_correct"]
                               for r in sel]))})
    return _stamp("D_B_ESS_grad_stratification", {"buckets": out})


def de_regret_decomposition(recs) -> dict:
    worst = sorted(
        recs, key=lambda r: -(r["metrics"]["regret_M2"] or 0))[:10]
    return _stamp("D_E_oracle_regret_decomposition", {
        "top10_negative_outcomes": [
            {"state_id": r["state_id"], "seed": r["seed"],
             "oracle": r["oracle_action"], "deployed":
                 r["validity"]["deployed_action"],
             "regret_M2": round(r["metrics"]["regret_M2"], 6)}
            for r in worst]})


# --------------------------------------------------------------------------- #
# D-F M3-v0 replay control
# --------------------------------------------------------------------------- #
def df_m3v0_replay() -> dict:
    bench = {r["config_id"]: r
             for r in load_freeze()["benchmark_configs"]}
    rows = []
    t0 = time.perf_counter()
    for cid, bc_rec in sorted(bench.items()):
        bc = config_from_record(bc_rec)
        rv = ref_views(bc_rec)
        p_ref = float(sum(rv["P"].values()))
        for seed in _SEEDS:
            # EXACT M3-v0 benchmark pathway: per-(config,seed) shared stage
            stage = run_shared_stage(bc, int(seed), n_pilot=PN, alpha=ALPHA,
                                     eta=ETA, n_eval=EVAL_N)
            assert stage.stop_reason is None and stage.selected_mode
            dim = stage.z.shape[1]
            q0c = stage.q0_cov
            centers = np.vstack([q0c.centers,
                                 np.asarray(stage.region.centroid,
                                            dtype=float).reshape(1, -1)])
            w_new = np.asarray(stage.pi_c0, dtype=float)
            k = centers.shape[0] - 1

            mk_prop = CovGaussianMixtureProposal(
                centers=centers, weights=w_new,
                covs=q0c.covs + (np.eye(dim), ),
                component_mode_ids=q0c.component_mode_ids
                + (str(stage.selected_mode), ),
                legality_checked=True,
                min_eig_sigma_minus_halfI=q0c.min_eig_sigma_minus_halfI)

            labels = bc.label(stage.z)
            ind_event = (labels != "NOMINAL").astype(float)
            a_vec = variance_mass_importance(
                stage.z, w_new, centers, list(mk_prop.covs), stage.logp,
                stage.logr, ind_event)
            spec = MixtureSpec(w_new, centers,
                               tuple(np.asarray(c, float)
                                     for c in mk_prop.covs))
            resp = component_responsibility(spec, stage.z, k)
            sq = np.einsum("ni,ni->n",
                           stage.z - centers[k][None, :],
                           stage.z - centers[k][None, :])
            est = scalar_gradient_estimate(a_vec, resp, sq, s2=1.0, dim=dim)
            est.update(stratified_bootstrap_gradient_ci(
                a_vec, resp, sq, stage.source_strata, s2=1.0, dim=dim,
                n_bootstrap=500, bootstrap_seed_key=(int(seed), 424243)))
            dec = DirectionRule(ess_min=20.0).decide(
                validity_ok=bool(est["valid_pointwise"]),
                validity_reasons=tuple(est["problems"]),
                ess_grad=float(est["ESS_grad"]),
                g_ci_low=float(est["g_ci_low"]),
                g_ci_high=float(est["g_ci_high"]))
            mapped = ("WIDEN" if dec == "WIDEN"
                      else "SHRINK" if dec == "SHRINK" else "HOLD")

            props = {}
            for nm, shft in (("base", 0.0), ("widen", 0.20),
                             ("shrink", -0.20)):
                covs = list(mk_prop.covs)
                covs[k] = float(np.exp(shft)) * np.eye(dim)
                props[nm] = CovGaussianMixtureProposal(
                    centers=centers, weights=w_new,
                    covs=tuple(np.asarray(c, float) for c in covs),
                    component_mode_ids=mk_prop.component_mode_ids,
                    legality_checked=True,
                    min_eig_sigma_minus_halfI=0.0)
            aw_m2 = float(eval_proposal_is(props["widen"], bc, int(seed),
                                           EVAL_N)["M2_hat"])
            hold_m2 = float(eval_proposal_is(props["base"], bc, int(seed),
                                             EVAL_N)["M2_hat"])
            rows.append({
                "config_id": cid, "seed": int(seed),
                "selected_mode": str(stage.selected_mode),
                "decision_raw": dec, "action": mapped,
                "ess_grad": float(est["ESS_grad"]),
                "M2_always_widen": aw_m2, "M2_hold": hold_m2,
                "ratio_aw_over_hold": aw_m2 / hold_m2})
    acts = {}
    for r in rows:
        acts[r["action"]] = acts.get(r["action"], 0) + 1
    med_rw = float(np.median([r["ratio_aw_over_hold"] for r in rows]))
    return _stamp("D_F_m3v0_replay_control", {
        "protocol": "per-(config,seed) original unit-scale M3-v0 states "
                    "(run_shared_stage verbatim), 8x8",
        "n_rows": len(rows), "action_counts": acts,
        "median_M2_always_widen_over_hold": med_rw,
        "expectation_check": {
            "mostly_WIDEN": bool(acts.get("WIDEN", 0) >= 40),
            "gradient_close_to_always_widen":
                abs(1.0 - med_rw) < 0.15},
        "gate_exclusion": True,
        "rows_sample_first_8": rows[:8]})


def main() -> int:
    AB.mkdir(parents=True, exist_ok=True)
    recs = json.loads(LAYA.read_text(encoding="utf-8"))["records"]

    print("[D-C] running extra-step sensitivity draws ...", flush=True)
    dc = dc_step_sensitivity(recs)
    (AB / "d_c_step_sensitivity.json").write_text(json.dumps(dc, indent=1))

    parts = {"d_a_gradient_vs_fixed_per_class":
             da_gradient_vs_rules_per_class(recs),
             "d_b_ess_grad_stratification": db_ess_stratification(recs),
             "d_e_oracle_regret_decomposition":
             de_regret_decomposition(recs)}
    (AB / "derived_report_tables.json").write_text(
        json.dumps(parts, indent=1), encoding="utf-8")

    (AB / "d_d_point_sign_vs_ci_sign.json").write_text(
        json.dumps(dd_point_sign_vs_ci(recs), indent=1))

    print("[D-F] replaying original M3-v0 states ...", flush=True)
    df = df_m3v0_replay()
    (AB / "d_f_m3v0_replay.json").write_text(json.dumps(df, indent=1))

    dose = {}
    for dlt in ("delta_0.1", "delta_0.4"):
        dose[dlt] = dc["dose_response"][dlt]
    print(json.dumps({"replay_actions": df["action_counts"],
                      "dose_response": dose,
                      "replay_expectation_checks":
                          df["expectation_check"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
