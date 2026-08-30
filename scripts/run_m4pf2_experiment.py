"""Run locked M4-PF2 discovery, confirmation, or artifact summarization."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze, ref_views
from hyptraj.m3ca.metrics import budget_vrf
from hyptraj.m3d.benchmark_states import assemble_state
from hyptraj.m4pf1.experiment import evaluate_proposal
from hyptraj.m4pf2.experiment import (
    CELL_ORDER,
    anchor_proposal,
    build_factorial_cells,
    construct_joint_gradients,
    factorial_contrasts,
    load_locks,
    select_freeoracle,
    sha256_file,
    validate_state_lock,
)

REPO = Path(__file__).resolve().parents[1]
RESULT = REPO / "results" / "phase_m4pf2"
SUMMARY = RESULT / "summary"
SAMPLES = RESULT / "gradient_samples"
PF1_RAW_PATH = REPO / "results" / "phase_m4pf1" / "m4pf1_confirmation_raw.json"
PF1_SUMMARY_PATH = REPO / "results" / "phase_m4pf1" / "summary" / \
    "m4pf1_family_summary.json"
POOL_PATH = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_candidate_pool.json"


def median(values) -> float:
    return float(statistics.median(float(value) for value in values))


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(child) for child in value]
    return value


def load_context():
    protocol, state_lock, seeds = load_locks(REPO)
    rows = validate_state_lock(REPO, state_lock)
    pf1_raw = json.loads(PF1_RAW_PATH.read_text(encoding="utf-8"))
    anchor_action = {row["state_id"]: row["selected_arm"]["S0"]
                     for row in pf1_raw["states"]}
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    freeze_rows = {row["config_id"]: row for row in
                   load_freeze()["benchmark_configs"]}
    benches = {cid: config_from_record(row)
               for cid, row in freeze_rows.items()}
    full_keys = sorted((row["config_id"], float(row["s2"]))
                       for row in pool["states_legal"])
    idx_of = {key: index for index, key in enumerate(full_keys)}
    return (protocol, state_lock, seeds, rows, anchor_action, pool,
            freeze_rows, benches, idx_of)


def assemble(row: dict, benches: dict):
    state = assemble_state(benches[row["state_key"]["config_id"]],
                           float(row["state_key"]["s2"]))
    if isinstance(state, dict) or state.state_id != row["state_id"]:
        raise RuntimeError(f"PF2 locked state assembly failed: {row['state_id']}")
    return state


def proposal_identity(state, anchor, selected_arm: str) -> dict:
    return {
        "state_id": state.state_id,
        "anchor_arm": selected_arm,
        "component_index": int(state.component_index),
        "centers": np.asarray(anchor.centers).tolist(),
        "weights": np.asarray(anchor.weights).tolist(),
        "covariances": [np.asarray(c).tolist() for c in anchor.covs],
    }


def persist_sample_arrays(state_id: str, arrays: dict, identity: dict,
                          seeds: list[int], suffix: str = "confirmation") -> dict:
    destination = SAMPLES / suffix / f"{state_id}.npz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        samples=arrays["samples"],
        variance_mass=arrays["variance_mass"],
        responsibility=arrays["responsibility"],
        whitened=arrays["whitened"],
        source_strata=arrays["source_strata"],
        proposal_identity=np.asarray(json.dumps(identity, sort_keys=True)),
        gradient_seeds=np.asarray(seeds, dtype=np.int64))
    return {
        "path": destination.relative_to(REPO).as_posix(),
        "sha256": sha256_file(destination),
        "n": int(arrays["samples"].shape[0]),
        "fields": ["samples", "variance_mass", "responsibility", "whitened",
                   "source_strata", "proposal_identity", "gradient_seeds"],
    }


def evaluate_cells(cells: dict, bench_cfg, rng_keys: list[list[int]],
                   n_eval: int, n_batches: int) -> dict:
    evaluations = {cell: [] for cell in CELL_ORDER}
    for rng_key in rng_keys:
        for cell in CELL_ORDER:
            evaluations[cell].append(evaluate_proposal(
                cells[cell], bench_cfg, rng_key, int(n_eval), int(n_batches)))
    return evaluations


def run_discovery() -> int:
    (protocol, _state_lock, seeds, rows, anchor_action, _pool, _freeze,
     benches, idx_of) = load_context()
    wanted = set(protocol["discovery"]["state_ids"])
    chosen = [row for row in rows if row["state_id"] in wanted]
    records = []
    all_valid = True
    for row in chosen:
        state = assemble(row, benches)
        arm = anchor_action[state.state_id]
        anchor = anchor_proposal(state, arm)
        gradients, arrays = construct_joint_gradients(
            state, anchor, seeds["discovery"]["gradient_seeds"],
            int(protocol["discovery"]["gradient_samples_per_seed"]),
            float(protocol["gradient_construction"]["pilot_source_mix_alpha"]))
        sample_artifact = persist_sample_arrays(
            state.state_id, arrays, proposal_identity(state, anchor, arm),
            seeds["discovery"]["gradient_seeds"], "discovery")
        cells, update = build_factorial_cells(
            state, anchor, gradients["mean"]["dimensionless_mean_gradient"],
            gradients["covariance"]["gradient_matrix"], protocol)
        index = idx_of[(state.config_id, state.s2)]
        rng_keys = [[850001 + index, 40000 + int(replicate)]
                    for replicate in seeds["discovery"][
                        "evaluation_replicate_ids"]]
        evaluations = evaluate_cells(
            cells, state.bench_cfg, rng_keys,
            int(protocol["discovery"]["evaluation_samples_per_replicate"]), 2)
        finite = all(record["nonfinite_weights"] == 0
                     for cell in evaluations.values() for record in cell)
        support = all(record["ESS"] >= 20.0
                      for cell in evaluations.values() for record in cell)
        valid = bool(update["valid"] and finite and support)
        all_valid = all_valid and valid
        records.append({
            "state_id": state.state_id, "class": row["class"],
            "anchor_arm": arm, "sample_artifact": sample_artifact,
            "gradients": jsonable(gradients), "update": jsonable(update),
            "evaluations": evaluations, "finite": finite,
            "support_pass": support, "valid": valid,
        })
    output = {
        "schema_version": "raretopo-m4pf2-discovery-v0",
        "stage": "PF2-D", "git_commit": git_head(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "protocol_may_change": False, "records": records,
        "pass": all_valid,
    }
    RESULT.mkdir(parents=True, exist_ok=True)
    (RESULT / "m4pf2_discovery.json").write_text(
        json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"stage": "PF2-D", "states": len(records),
                      "pass": all_valid}, indent=2))
    return 0 if all_valid else 4


def run_confirmation() -> int:
    (protocol, state_lock, seeds, rows, anchor_action, pool, freeze_rows,
     benches, idx_of) = load_context()
    confirmation = protocol["confirmation"]
    p_refs = {cid: float(sum(ref_views(row)["P"].values()))
              for cid, row in freeze_rows.items()}
    raw_states = []
    numerical_valid = True
    started = time.perf_counter()
    for ordinal, row in enumerate(rows, 1):
        state = assemble(row, benches)
        key = f"{state.config_id}|{state.s2}"
        index = idx_of[(state.config_id, state.s2)]
        arm = anchor_action[state.state_id]
        anchor = anchor_proposal(state, arm)
        identity = proposal_identity(state, anchor, arm)
        gradients, arrays = construct_joint_gradients(
            state, anchor, seeds["confirmation"]["gradient_seeds"],
            int(protocol["gradient_construction"]["samples_per_seed"]),
            float(protocol["gradient_construction"]["pilot_source_mix_alpha"]))
        sample_artifact = persist_sample_arrays(
            state.state_id, arrays, identity,
            seeds["confirmation"]["gradient_seeds"])
        cells, update = build_factorial_cells(
            state, anchor, gradients["mean"]["dimensionless_mean_gradient"],
            gradients["covariance"]["gradient_matrix"], protocol)

        probability = {
            "P00": float(pool["reference_fields"][key]["arms"][arm]["P"])
        }
        probability_records = {}
        for cell, code in (("P10", 10), ("P01", 1), ("P11", 11)):
            record = evaluate_proposal(
                cells[cell], state.bench_cfg, [910001 + index, code],
                int(confirmation["new_cell_probability_characterization_n"]),
                10)
            probability[cell] = float(record["P_hat"])
            probability_records[cell] = record

        rng_keys = [[901001 + index, 30000 + int(replicate)]
                    for replicate in seeds["confirmation"][
                        "evaluation_replicate_ids"]]
        evaluations = evaluate_cells(
            cells, state.bench_cfg, rng_keys,
            int(confirmation["evaluation_n_per_cell_replicate"]),
            int(confirmation["evaluation_batches"]))
        selected = select_freeoracle(evaluations, probability)
        cell_vrf = {
            cell: [budget_vrf(
                p_refs[state.config_id], record["M2"], probability[cell],
                int(record["n_eval"]),
                int(confirmation["deployable_selected_arm_budget"]))
                for record in evaluations[cell]]
            for cell in CELL_ORDER}
        finite = all(record["nonfinite_weights"] == 0
                     for cell in evaluations.values() for record in cell)
        support = all(record["ESS"] >= 20.0
                      for cell in evaluations.values() for record in cell)
        valid = bool(update["valid"] and finite and support)
        numerical_valid = numerical_valid and valid
        raw_states.append({
            "state_id": state.state_id, "state_key": row["state_key"],
            "class": row["class"], "anchor_arm": arm,
            "full_grid_index": index, "p_ref": p_refs[state.config_id],
            "proposal_identity": identity,
            "sample_artifact": sample_artifact,
            "gradients": jsonable(gradients), "update": jsonable(update),
            "probability": probability,
            "probability_records": probability_records,
            "evaluations": evaluations, "cell_vrf": cell_vrf,
            "freeoracle_selected_cell": selected, "finite": finite,
            "support_pass": support, "valid": valid,
        })
        print(f"[PF2-C {ordinal:02d}/24] {state.state_id} anchor={arm} "
              f"selected={selected} elapsed={time.perf_counter()-started:.0f}s",
              flush=True)

    raw = {
        "schema_version": "raretopo-m4pf2-confirmation-raw-v0",
        "stage": "PF2-C", "git_commit": git_head(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "protocol_hashes": {
            name: sha256_file(REPO / "configs" / "phase_m4pf2" / name)
            for name in ("m4pf2_protocol.json", "m4pf2_states.json",
                         "m4pf2_seeds.json")},
        "state_source_hash": state_lock["source_sha256"],
        "anchor_source_hash": state_lock["anchor_action_source_sha256"],
        "numerical_safety_pass": numerical_valid,
        "states": raw_states,
    }
    RESULT.mkdir(parents=True, exist_ok=True)
    (RESULT / "m4pf2_confirmation_raw.json").write_text(
        json.dumps(raw, indent=1, allow_nan=False), encoding="utf-8")
    summarize(raw, protocol)
    print(json.dumps({"states": len(raw_states),
                      "numerical_safety_pass": numerical_valid}, indent=2))
    return 0 if numerical_valid else 5


def efficiency_class(vrf: float) -> str:
    return ("ABSOLUTE_EFFICIENT" if vrf > 1.0 else
            "MATERIAL_BELOW_ONE" if vrf > 0.1 else "BELOW_0.1")


def summarize(raw: dict, protocol: dict) -> None:
    confirmation = protocol["confirmation"]
    state_rows, tail_rows, ledger = [], [], []
    for state in raw["states"]:
        mean = state["gradients"]["mean"]
        covariance = state["gradients"]["covariance"]
        update = state["update"]
        for cell in CELL_ORDER:
            records = state["evaluations"][cell]
            vrfs = state["cell_vrf"][cell]
            mean_on = protocol["cells"][cell]["mean_on"]
            cov_on = protocol["cells"][cell]["cov_rank1_on"]
            condition = (update["covariance"]["condition_number"]
                         if cov_on else 1.0)
            state_rows.append({
                "state_id": state["state_id"],
                "config_id": state["state_key"]["config_id"],
                "s2": state["state_key"]["s2"],
                "action_class": state["class"], "cell": cell,
                "mean_on": mean_on, "cov_rank1_on": cov_on,
                "mean_step": update["mean"]["mahalanobis_norm"]
                    if mean_on else 0.0,
                "mean_step_euclidean": update["mean"]["euclidean_norm"]
                    if mean_on else 0.0,
                "cov_step": protocol["covariance_update"]["eta_sigma"]
                    if cov_on else 0.0,
                "component_index": state["proposal_identity"]["component_index"],
                "mean_gradient_norm": mean["norm"],
                "cov_gradient_norm": covariance["spectral"]["frobenius_norm"],
                "selected_by_freeoracle":
                    cell == state["freeoracle_selected_cell"],
                "M2": median(record["M2"] for record in records),
                "VRF_proposal": median(vrfs),
                "VRF_budget": median(vrfs),
                "ESS": median(record["ESS"] for record in records),
                "max_normalized_weight": median(
                    record["max_normalized_weight"] for record in records),
                "top_1pct_weight_mass": median(
                    record["top_1pct_weight_mass"] for record in records),
                "top_0_1pct_weight_mass": median(
                    record["top_0_1pct_weight_mass"] for record in records),
                "condition_number": condition,
                "nonfinite_weight_count": sum(
                    record["nonfinite_weights"] for record in records),
                "underflow_count": sum(
                    record["event_weight_underflow_count"] for record in records),
                "support_loss_count": sum(record["ESS"] < 20.0
                                          for record in records),
                "fallback_count": int(not update["valid"]),
                "efficiency_class": efficiency_class(median(vrfs)),
                "valid": state["valid"],
            })
            for replicate, (record, vrf) in enumerate(zip(records, vrfs), 1):
                tail_rows.append({
                    "state_id": state["state_id"], "cell": cell,
                    "replicate": replicate, "M2": record["M2"],
                    "VRF_budget": vrf, "ESS": record["ESS"],
                    "max_normalized_weight": record["max_normalized_weight"],
                    "top_1pct_weight_mass": record["top_1pct_weight_mass"],
                    "top_0_1pct_weight_mass": record["top_0_1pct_weight_mass"],
                    "nonfinite_weights": record["nonfinite_weights"],
                    "event_weight_underflow_count":
                        record["event_weight_underflow_count"],
                    "support_loss": record["ESS"] < 20.0,
                })
        ledger.append({
            "record_type": "counterfactual_deployable",
            "state_id": state["state_id"],
            "cell": state["freeoracle_selected_cell"],
            "pilot_cost": 0, "decision_cost": 0,
            "selected_arm_cost": confirmation["deployable_selected_arm_budget"],
            "deployable_cost": confirmation["deployable_selected_arm_budget"],
            "audit_only_cost": 0,
            "cost_semantics": "FreeOracle selected final arm only",
        })
        for record_type, cost in (
            ("AUDIT_SHARED_GRADIENT",
             protocol["gradient_construction"]["pooled_samples_per_state"]),
            ("AUDIT_NEW_CELL_PROBABILITY",
             3*confirmation["new_cell_probability_characterization_n"]),
            ("AUDIT_FOUR_CELL_EVALUATION",
             4*confirmation["evaluation_n_per_cell_replicate"] *
             confirmation["evaluation_replicates"]),
        ):
            ledger.append({
                "record_type": record_type, "state_id": state["state_id"],
                "cell": "SHARED", "pilot_cost": 0, "decision_cost": 0,
                "selected_arm_cost": 0, "deployable_cost": 0,
                "audit_only_cost": int(cost),
                "cost_semantics": "actual scientific cost excluded from FreeOracle",
            })
    ledger.append({
        "record_type": "AUDIT_DISCOVERY", "state_id": "PF2-D",
        "cell": "SHARED", "pilot_cost": 0, "decision_cost": 0,
        "selected_arm_cost": 0, "deployable_cost": 0,
        "audit_only_cost": 200000,
        "cost_semantics": "two-state locked safety discovery",
    })

    cell_rows = []
    for cell in CELL_ORDER:
        subset = [row for row in state_rows if row["cell"] == cell]
        values = [float(row["VRF_budget"]) for row in subset]
        cell_rows.append({
            "cell": cell, "mean_on": protocol["cells"][cell]["mean_on"],
            "cov_rank1_on": protocol["cells"][cell]["cov_rank1_on"],
            "state_count": len(subset), "median_VRF": median(values),
            "fraction_states_gt_0_1": sum(v > 0.1 for v in values)/len(values),
            "fraction_states_gt_1": sum(v > 1 for v in values)/len(values),
            "worst_state_VRF": min(values),
            "WIDEN_median_VRF": median(row["VRF_budget"] for row in subset
                                       if row["action_class"] == "WIDEN"),
            "SHRINK_median_VRF": median(row["VRF_budget"] for row in subset
                                        if row["action_class"] == "SHRINK"),
            "all_valid": all(row["valid"] for row in subset),
        })
    by_cell = {row["cell"]: row for row in cell_rows}
    contrasts = factorial_contrasts(state_rows)
    contrast_summary = {
        field: median(row[field] for row in contrasts)
        for field in ("mean_effect_without_covariance",
                      "mean_effect_with_covariance",
                      "covariance_effect_without_mean",
                      "covariance_effect_with_mean", "interaction")}
    neutral = float(protocol["factorial_contrasts"][
        "approximately_neutral_abs_log_threshold"])
    for row in contrasts:
        for field in ("mean_effect_without_covariance",
                      "mean_effect_with_covariance"):
            value = float(row[field])
            row[f"{field}_sign"] = ("improves" if value > neutral else
                                     "worsens" if value < -neutral else
                                     "approximately_neutral")

    freeoracle_values = []
    selected_counts = Counter()
    for state in raw["states"]:
        selected = state["freeoracle_selected_cell"]
        selected_counts[selected] += 1
        freeoracle_values.append(median(state["cell_vrf"][selected]))
    freeoracle_median = median(freeoracle_values)
    pf1 = json.loads(PF1_SUMMARY_PATH.read_text(encoding="utf-8"))
    anchor = float(pf1["scalar_observed"])
    p00 = float(by_cell["P00"]["median_VRF"])
    p00_relative = abs(p00-anchor)/anchor
    p00_pass = bool(p00_relative <= protocol["p00_reproduction"][
        "median_vrf_relative_tolerance_vs_pf1_anchor"])
    valid = bool(raw["numerical_safety_pass"] and p00_pass and
                 len(state_rows) == 96)
    verdict = ("PF2-D" if not valid else "PF2-A" if freeoracle_median > 1.0
               else "PF2-B" if freeoracle_median > 0.1 else "PF2-C")
    summary = {
        "schema_version": "raretopo-m4pf2-family-summary-v0",
        "stage": "M4-PF2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "cells": cell_rows,
        "factorial_contrasts": contrast_summary,
        "freeoracle": {
            "median_VRF": freeoracle_median,
            "fraction_states_gt_0_1": sum(v > 0.1 for v in freeoracle_values)/24,
            "fraction_states_gt_1": sum(v > 1 for v in freeoracle_values)/24,
            "worst_state_VRF": min(freeoracle_values),
            "selected_cell_counts": dict(selected_counts),
        },
        "p00_reproduction": {
            "pf1_anchor": anchor, "pf2_observed": p00,
            "relative_difference": p00_relative,
            "relative_tolerance": protocol["p00_reproduction"][
                "median_vrf_relative_tolerance_vs_pf1_anchor"],
            "pass": p00_pass,
        },
        "numerical_safety_pass": raw["numerical_safety_pass"],
        "state_count": len(raw["states"]),
        "class_counts": dict(Counter(state["class"] for state in raw["states"])),
        "primary_gate_gt_1": freeoracle_median > 1.0,
        "material_gate_gt_0_1": freeoracle_median > 0.1,
        "verdict": verdict,
        "protocol_hashes": raw["protocol_hashes"],
        "state_source_hash": raw["state_source_hash"],
        "anchor_source_hash": raw["anchor_source_hash"],
        "cost_accounting": {
            "deployable_selected_arm_budget":
                confirmation["deployable_selected_arm_budget"],
            "confirmation_audit_only_samples": 122400000,
            "discovery_audit_only_samples": 200000,
            "total_actual_pf2_samples": 122600000,
        },
        "claim_boundary": "locked one-step four-cell FreeOracle feasibility; not deployable control",
    }
    SUMMARY.mkdir(parents=True, exist_ok=True)
    (SUMMARY / "m4pf2_family_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    (SUMMARY / "m4pf2_protocol_lock.json").write_text(json.dumps({
        "protocol_hashes": raw["protocol_hashes"],
        "state_source_hash": raw["state_source_hash"],
        "anchor_source_hash": raw["anchor_source_hash"],
    }, indent=2), encoding="utf-8")
    manifest_sources = []
    fixed_sources = (
        "configs/phase_m4pf2/m4pf2_protocol.json",
        "configs/phase_m4pf2/m4pf2_states.json",
        "configs/phase_m4pf2/m4pf2_seeds.json",
        "configs/phase_m3bv2/m3bv2_value_benchmark.json",
        "results/phase_m4pf1/m4pf1_confirmation_raw.json",
        "results/phase_m4pf2/m4pf2_discovery.json",
        "results/phase_m4pf2/m4pf2_confirmation_raw.json",
    )
    for rel in fixed_sources:
        path = REPO / rel
        manifest_sources.append({
            "path": rel, "sha256": sha256_file(path),
            "role": "protocol_or_parent" if "configs" in rel or "m4pf1" in rel
                    else "PF2 experiment record",
            "read_only_after_confirmation": True,
        })
    for state in raw["states"]:
        artifact = state["sample_artifact"]
        path = REPO / artifact["path"]
        actual_hash = sha256_file(path)
        if actual_hash != artifact["sha256"]:
            raise RuntimeError(f"PF2 sample artifact hash mismatch: {path}")
        manifest_sources.append({
            "path": artifact["path"], "sha256": actual_hash,
            "role": "fresh anchor sample arrays",
            "state_id": state["state_id"],
            "proposal_anchor": state["anchor_arm"],
            "read_only_after_confirmation": True,
        })
    (SUMMARY / "m4pf2_source_manifest.json").write_text(json.dumps({
        "schema_version": "raretopo-m4pf2-source-manifest-v0",
        "source_count": len(manifest_sources),
        "sources": manifest_sources,
        "sources_unchanged": True,
    }, indent=2), encoding="utf-8")
    write_csv(SUMMARY / "m4pf2_family_summary.csv", cell_rows)
    write_csv(SUMMARY / "m4pf2_state_table.csv", state_rows)
    write_csv(SUMMARY / "m4pf2_tail_diagnostics.csv", tail_rows)
    write_csv(SUMMARY / "m4pf2_cost_ledger.csv", ledger)
    write_csv(SUMMARY / "m4pf2_factorial_contrasts.csv", contrasts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("discovery", "confirmation",
                                             "summarize"), required=True)
    args = parser.parse_args()
    if args.stage == "discovery":
        return run_discovery()
    if args.stage == "confirmation":
        return run_confirmation()
    protocol, _state_lock, _seeds = load_locks(REPO)
    raw = json.loads((RESULT / "m4pf2_confirmation_raw.json").read_text(
        encoding="utf-8"))
    summarize(raw, protocol)
    print("[saved] PF2 summary tables from frozen raw confirmation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
