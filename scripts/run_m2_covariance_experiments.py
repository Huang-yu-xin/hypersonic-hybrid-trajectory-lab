"""M2 -- execution driver for preregistered stages M2-3..M2-6 (task Sec. 42).

Stages
------
main   8 frozen configs x 8 seeds: ONE locked shared stage per (config,
       seed); C0-C4 forked on identical pilot/selection/mean;
       Layer A -> results/phase_m2/layer_a_shape_only/
       Layer B -> results/phase_m2/layer_b_shape_reweight/
lambda Ablation M2-D: C4 at lambda in {0.25, 0.75}, both layers
       -> results/phase_m2/ablations/

Every constant comes from configs/phase_m2/m2_covariance_v0.json; this
script never relaxes a protocol value.  Simulator-call accounting is honest:
one 20k shared pilot per (config, seed) feeds selection, mean, covariance
and BOTH layers' weight fits -- zero additional simulator calls anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import (
    SEEDS,
    config_from_record,
    load_freeze,
    ref_views,
)
from hyptraj.m2 import covariance_policy as cp
from hyptraj.m2.metrics import (
    build_trial_record,
    covariance_change_frobenius,
    ess_band,
    principal_alignment,
)

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "phase_m2"
FREEZE_JSON = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"
FREEZE_SHA = hashlib.sha256(FREEZE_JSON.read_bytes()).hexdigest()
CFG_V0 = json.loads(
    (REPO / "configs" / "phase_m2" / "m2_covariance_v0.json").read_text(
        encoding="utf-8"))

FROZEN_IDS = list(CFG_V0["frozen_configs"])
PN = int(CFG_V0["protocol_locked"]["pilot_n_per_round"])
ALPHA = float(CFG_V0["protocol_locked"]["alpha_p"])
EVAL_N = int(CFG_V0["protocol_locked"]["final_eval_n"])
ETA = float(CFG_V0["protocol_locked"]["eta_main"])
LAMBDA_MAIN = float(CFG_V0["covariance_family_locked"]["lambda_main"])
SCHEMA = CFG_V0["outputs"]["record_schema_version"]


def _git_head() -> str:
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _batch_meta(stage: str) -> dict:
    return {
        "schema_version": "raretopo-m2-batch-v0",
        "record_schema_version": SCHEMA,
        "benchmark_freeze_hash": FREEZE_SHA,
        "config_sha256_m1d": load_freeze()["config_sha256"],
        "m1d_frozen_head": CFG_V0["parent_tags"]["m1d_frozen_head"],
        "git_commit": _git_head(),
        "timestamp_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds"),
        "protocol": {"n_pilot": PN, "alpha_p": ALPHA, "n_eval": EVAL_N,
                     "eta_main": ETA, "seeds": SEEDS,
                     "lambda_main": LAMBDA_MAIN},
        "covariance_constants": {
            "ess_v_min": cp.ESS_V_MIN,
            "eigen_floor": 0.55, "eigen_cap": 4.00,
            "legal_min_eig_frozen": 0.5,
        },
        "stage": stage,
    }


def _save(batch: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    try:
        shown = path.relative_to(REPO)
    except ValueError:
        shown = path
    print(f"[saved] {shown} "
          f"({len(batch.get('records_by_config', []))} configs)", flush=True)


def _to_list(mat) -> list:
    return np.asarray(mat, dtype=float).tolist()


def _region_block(stage) -> dict | None:
    r = stage.region
    if r is None:
        return None
    return {
        "n_region": int(r.n_region),
        "ess_v": float(r.ess_v_region),
        "centroid": _to_list(r.centroid),
        "cov_raw": _to_list(r.cov),
        "eig_raw": [float(v) for v in r.eigenvalues_raw],
        "weight_sum": float(r.weight_sum),
        "condition_raw": float(r.condition_raw),
        "eta_requested": float(r.eta_requested),
        "eta_used": float(r.eta_used),
        "ess_band": ess_band(r.ess_v_region),
        "anisotropy_A_C": float(max(r.eigenvalues_raw)
                                / (min(r.eigenvalues_raw) + 1e-12)),
    }


def _covariance_block(spec) -> dict:
    proj = spec.projection
    return {
        "lambda": None if spec.method != "C4" else float(spec.lambda_used),
        "sigma_pre": _to_list(proj.sigma_pre),
        "sigma_final": _to_list(spec.sigma_final),
        "eig_pre": [float(v) for v in proj.eigenvalues_pre],
        "eig_final": [float(v) for v in proj.eigenvalues_post],
        "clipped_low": int(proj.n_eigen_clipped_low),
        "clipped_high": int(proj.n_eigen_clipped_high),
        "projection_frobenius_norm": float(proj.projection_frobenius_norm),
        "legality_passed": bool(proj.legality_passed),
        "min_eig_final": float(proj.min_eig_final),
        "hold": bool(spec.held),
        "hold_reason": str(spec.hold_reason),
    }


def _evaluation_block(stage, prop, p_ref_union: float, budget_total: int,
                      n_eval: int) -> dict:
    from hyptraj.m1d.metrics import attach_vrfs
    ev = cp.evaluate_variant(stage, prop, n_eval)
    attach_vrfs(ev, p_ref=float(p_ref_union), budget_total=int(budget_total))
    ev["L_table"] = {str(k): float(v) for k, v in ev["L_table"].items()}
    # task Sec. 45 required key names alongside the frozen evaluator keys
    ev["n"] = int(ev["n_eval"])
    ev["mode_L"] = dict(ev["L_table"])
    return ev


def _trial_records_for_seed(bc, frec, stage, lam_extra=None):
    """Fork C0-C4 from one locked stage into full (both-layer) records."""
    rv = ref_views(frec)
    p_ref_union = float(sum(rv["P"].values()))
    budget_total = PN + EVAL_N                      # one-birth accounting

    rows = {"layer_a_shape_only": [], "layer_b_shape_reweight": []}
    ablation_rows = {"layer_a_shape_only": [], "layer_b_shape_reweight": []}
    cands = cp.build_candidates(stage.region, stage.sigma_base,
                                lambda_main=LAMBDA_MAIN)

    def finish(layer_key, spec, prop):
        _, solver_info = prop
        prop_obj = prop[0]
        ev = _evaluation_block(stage, prop_obj, p_ref_union, budget_total,
                               EVAL_N)
        rec = build_trial_record(
            benchmark_hash=FREEZE_SHA, config_id=bc.config_id,
            seed=stage.seed, layer=layer_key,
            covariance_method=spec.method,
            selected_mode=stage.selected_mode, eta=ETA, pilot_n=PN,
            alpha_p=ALPHA, region=_region_block(stage),
            covariance_block=_covariance_block(spec), evaluation=ev,
            extra_simulator_calls=0,
            validity={
                "selected_mode_lock": True, "mean_lock_dev_abs":
                    float(stage.centroid_frozen_check),
                "source_density_recorded": True,
                "eval_rng_tag": 900001,
                "weight_solver": solver_info,
                "eligible_candidates": list(stage.eligible),
                "P_hat_table": stage.P_hat_table,
                "L_hat_table": stage.L_hat_table,
                "c0_build_details": stage.c0_build_details,
                "pi_final": [float(v) for v in prop_obj.weights],
            })
        return rec

    for method in cp.COV_METHODS:
        spec = cands[method]
        # ---- Layer A -----------------------------------------------------
        pa, info_a = cp.build_variant_proposal(stage, spec, cp.LAYER_A)
        rows["layer_a_shape_only"].append(finish("shape_only", spec, (pa,
                                                                      info_a)))
        # ---- Layer B -----------------------------------------------------
        pb, info_b = cp.build_variant_proposal(stage, spec, cp.LAYER_B)
        rows["layer_b_shape_reweight"].append(finish("shape_reweight", spec,
                                                     (pb, info_b)))

    # ---- lambda sensitivity (Ablation M2-D; explanatory ONLY) ------------
    if lam_extra:
        for lam in lam_extra:
            specs_lam = cp.build_candidates(stage.region, stage.sigma_base,
                                            lambda_main=float(lam))
            spec_lam = specs_lam["C4"]
            pal, ia = cp.build_variant_proposal(stage, spec_lam, cp.LAYER_A)
            ablation_rows["layer_a_shape_only"].append(
                finish(f"shape_only_lambda_{lam:g}", spec_lam, (pal, ia)))
            pbl, ib = cp.build_variant_proposal(stage, spec_lam, cp.LAYER_B)
            ablation_rows["layer_b_shape_reweight"].append(
                finish(f"shape_reweight_lambda_{lam:g}", spec_lam, (pbl, ib)))

    diagnostics = {
        "principal_alignment_C_eta_vs_sigma": {
            m: principal_alignment(stage.region.cov, s.sigma_final)
            for m, s in cands.items()},
        "frobenius_change_vs_base": {
            m: covariance_change_frobenius(s.sigma_final, stage.sigma_base)
            for m, s in cands.items()},
    }
    return rows, ablation_rows, diagnostics


def run_main(lam_extra=None) -> None:
    recs_all = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    missing = [c for c in FROZEN_IDS if c not in recs_all]
    if missing:
        raise RuntimeError(f"frozen configs absent from freeze artifact: "
                           f"{missing}")

    batch_out = {}
    lam_dir_rows = {k: [] for k in
                    ("layer_a_shape_only", "layer_b_shape_reweight")}
    shape_diagnostics: list[dict] = []
    for cid in FROZEN_IDS:
        bc = config_from_record(recs_all[cid])
        t0 = time.perf_counter()
        la_records, lb_records = [], []
        for seed in SEEDS:
            stage = cp.run_shared_stage(bc, seed, n_pilot=PN, alpha=ALPHA,
                                        eta=ETA, n_eval=EVAL_N)
            if stage.stop_reason is not None:
                empty_rec = build_trial_record(
                    benchmark_hash=FREEZE_SHA, config_id=cid, seed=seed,
                    layer="stage_failed", covariance_method="NONE",
                    selected_mode=None, eta=ETA, pilot_n=PN, alpha_p=ALPHA,
                    region=None,
                    covariance_block={"hold": False,
                                      "legality_passed": False},
                    evaluation={"n": EVAL_N, "P_hat": None, "M2_hat": None,
                                "VRF_proposal": None, "VRF_budget": None,
                                "mode_L": {}},
                    validity={"stop_reason": stage.stop_reason})
                la_records.append(empty_rec)
                lb_records.append({**empty_rec, "layer": "stage_failed_lb"})
                continue
            rows, abl_rows, diag = _trial_records_for_seed(bc, recs_all[cid],
                                                           stage,
                                                           lam_extra=lam_extra)
            la_records.extend(rows["layer_a_shape_only"])
            lb_records.extend(rows["layer_b_shape_reweight"])
            for k in abl_rows:
                if abl_rows[k]:
                    lam_dir_rows[k].append({"config_id": cid,
                                            "records": abl_rows[k]})
            shape_diagnostics.append({"config_id": cid, "seed": int(seed),
                                      **diag})
        print(f"  [{cid}] LA={len(la_records)} LB={len(lb_records)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        batch_out.setdefault("records_by_config", []).append(
            {"config_id": cid, "records": la_records})
        batch_out[f"layer_B_{cid}"] = lb_records      # temporary transport

    # ---- persist Layer A ---------------------------------------------------
    meta = _batch_meta("m3_layer_A_shape_only")
    meta["records_by_config"] = batch_out["records_by_config"]
    _save(meta, RESULTS / "layer_a_shape_only"
          / "layer_a_shape_only_v1.json")

    # ---- persist Layer B ---------------------------------------------------
    meta_b = _batch_meta("m4_layer_B_shape_reweight")
    meta_b["records_by_config"] = [
        {"config_id": entry["config_id"],
         "records": batch_out[f"layer_B_{entry['config_id']}"]}
        for entry in batch_out["records_by_config"]]
    _save(meta_b, RESULTS / "layer_b_shape_reweight"
          / "layer_b_shape_reweight_v1.json")

    # ---- persist shape diagnostics ----------------------------------------
    (RESULTS / "summary").mkdir(parents=True, exist_ok=True)
    (RESULTS / "summary" / "shape_diagnostics_v1.json").write_text(
        json.dumps({"schema_version": SCHEMA,
                    "_meta": _batch_meta("diagnostics"),
                    "rows": shape_diagnostics}, indent=1), encoding="utf-8")
    print("[saved] results/phase_m2/summary/shape_diagnostics_v1.json",
          flush=True)

    # ---- persist lambda ablations -----------------------------------------
    if lam_extra:
        meta_la = _batch_meta("m6_ablation_lambda_layer_A")
        meta_la["records_by_config"] = lam_dir_rows["layer_a_shape_only"]
        _save(meta_la, RESULTS / "ablations"
              / "lambda_sensitivity_layer_a_v1.json")
        meta_lb = _batch_meta("m6_ablation_lambda_layer_B")
        meta_lb["records_by_config"] = lam_dir_rows["layer_b_shape_reweight"]
        _save(meta_lb, RESULTS / "ablations"
              / "lambda_sensitivity_layer_b_v1.json")


STAGES = {
    "main": lambda: run_main(lam_extra=None),
    "main_plus_lambda": lambda: run_main(
        lam_extra=json.loads((REPO / "configs" / "phase_m2"
                              / "m2_lambda_sensitivity.json")
                             .read_text(encoding="utf-8"))["lambda_values"]),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 covariance experiments")
    ap.add_argument("--stage", choices=sorted(STAGES), required=True)
    args = ap.parse_args()
    t0 = time.perf_counter()
    STAGES[args.stage]()
    print(f"[stage {args.stage}] done in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
