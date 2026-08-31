"""Run locked PF3-A discovery, confirmation, or artifact summarization."""

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
from hyptraj.m4pf3.experiment import (
    ARM_ORDER,
    build_allocation_arms,
    construct_allocation_gradient,
    load_locks,
    p11_anchor,
    proposal_identity,
    select_freeoracle,
    sha256_file,
    validate_state_lock,
)


REPO = Path(__file__).resolve().parents[1]
RESULT = REPO / "results" / "phase_m4pf3"
SUMMARY = RESULT / "summary"
SAMPLES = RESULT / "gradient_samples"
PF2_RAW_PATH = REPO / "results" / "phase_m4pf2" / "m4pf2_confirmation_raw.json"
PF2_SUMMARY_PATH = (REPO / "results" / "phase_m4pf2" / "summary"
                    / "m4pf2_family_summary.json")
PF3_0_SUMMARY = (REPO / "results" / "phase_m4pf3_0" / "summary"
                 / "m4pf3_0_diagnostic_summary.json")
PF3_0_STATES = (REPO / "results" / "phase_m4pf3_0" / "summary"
                / "m4pf3_0_state_diagnostics.csv")
POOL_PATH = (REPO / "results" / "phase_m3bv" / "reference"
             / "m3bv_candidate_pool.json")


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


def encoded(value) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))


def load_context():
    protocol, state_lock, seeds = load_locks(REPO)
    rows = validate_state_lock(REPO, state_lock)
    if sha256_file(PF2_RAW_PATH) != protocol["anchor"]["source_sha256"]:
        raise RuntimeError("PF3 P11 source changed")
    if sha256_file(PF3_0_SUMMARY) != protocol["routing"]["source_sha256"]:
        raise RuntimeError("PF3-0 route source changed")
    pf2_raw = json.loads(PF2_RAW_PATH.read_text(encoding="utf-8"))
    pf2_by_state = {row["state_id"]: row for row in pf2_raw["states"]}
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    freeze_rows = {row["config_id"]: row for row in
                   load_freeze()["benchmark_configs"]}
    benches = {cid: config_from_record(row)
               for cid, row in freeze_rows.items()}
    full_keys = sorted((row["config_id"], float(row["s2"]))
                       for row in pool["states_legal"])
    idx_of = {key: index for index, key in enumerate(full_keys)}
    return (protocol, state_lock, seeds, rows, pf2_by_state, pool,
            freeze_rows, benches, idx_of)


def assemble(row: dict, benches: dict):
    state = assemble_state(benches[row["state_key"]["config_id"]],
                           float(row["state_key"]["s2"]))
    if isinstance(state, dict) or state.state_id != row["state_id"]:
        raise RuntimeError(f"PF3 locked state assembly failed: {row['state_id']}")
    return state


def persist_sample_arrays(state_id: str, arrays: dict, identity: dict,
                          seeds: list[int], suffix: str) -> dict:
    destination = SAMPLES / suffix / f"{state_id}.npz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        samples=arrays["samples"],
        variance_mass=arrays["variance_mass"],
        responsibilities=arrays["responsibilities"],
        source_strata=arrays["source_strata"],
        proposal_identity=np.asarray(json.dumps(identity, sort_keys=True)),
        gradient_seeds=np.asarray(seeds, dtype=np.int64),
    )
    return {
        "path": destination.relative_to(REPO).as_posix(),
        "sha256": sha256_file(destination),
        "n": int(arrays["samples"].shape[0]),
        "fields": ["samples", "variance_mass", "responsibilities",
                   "source_strata", "proposal_identity", "gradient_seeds"],
    }


def evaluate_arms(arms: dict, bench_cfg, rng_keys: list[list[int]],
                  n_eval: int, n_batches: int) -> dict:
    evaluations = {arm: [] for arm in ARM_ORDER}
    for rng_key in rng_keys:
        for arm in ARM_ORDER:
            evaluations[arm].append(evaluate_proposal(
                arms[arm], bench_cfg, rng_key, int(n_eval), int(n_batches)))
    return evaluations


def run_discovery() -> int:
    (protocol, _state_lock, seeds, rows, pf2, _pool, _freeze, benches,
     idx_of) = load_context()
    wanted = set(protocol["discovery"]["state_ids"])
    records, all_valid = [], True
    for row in (item for item in rows if item["state_id"] in wanted):
        state = assemble(row, benches)
        anchor = p11_anchor(pf2[state.state_id])
        allocation, arrays = construct_allocation_gradient(
            state, anchor, seeds["discovery"]["gradient_seeds"],
            protocol["discovery"]["gradient_samples_per_seed"],
            protocol["gradient_construction"]["pilot_source_mix_alpha"])
        identity = proposal_identity(state.state_id, anchor)
        sample_artifact = persist_sample_arrays(
            state.state_id, arrays, identity,
            seeds["discovery"]["gradient_seeds"], "discovery")
        arms, update = build_allocation_arms(
            anchor, allocation, protocol, arrays=arrays)
        index = idx_of[(state.config_id, state.s2)]
        rng_keys = [[950001 + index, 40000 + int(replicate)]
                    for replicate in seeds["discovery"][
                        "evaluation_replicate_ids"]]
        evaluations = evaluate_arms(
            arms, state.bench_cfg, rng_keys,
            protocol["discovery"]["evaluation_samples_per_replicate"], 2)
        finite = all(record["nonfinite_weights"] == 0
                     for values in evaluations.values() for record in values)
        support = all(record["ESS"] >= 20.0
                      for values in evaluations.values() for record in values)
        simplex = bool(np.isclose(np.sum(update["alpha_prime"]), 1.0)
                       and np.all(np.asarray(update["alpha_prime"]) > 0.0))
        valid = finite and support and simplex
        all_valid = all_valid and valid
        records.append({
            "state_id": state.state_id, "class": row["class"],
            "anchor_identity": identity, "sample_artifact": sample_artifact,
            "allocation": jsonable(allocation), "update": jsonable(update),
            "evaluations": evaluations, "finite": finite,
            "support_pass": support, "simplex_pass": simplex, "valid": valid,
        })
    output = {
        "schema_version": "raretopo-m4pf3-discovery-v0",
        "stage": "PF3-A-D", "git_commit": git_head(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "protocol_may_change": False, "records": records,
        "pass": all_valid,
    }
    RESULT.mkdir(parents=True, exist_ok=True)
    (RESULT / "m4pf3_discovery.json").write_text(
        json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"stage": "PF3-A-D", "states": len(records),
                      "pass": all_valid}, indent=2))
    return 0 if all_valid else 4


def run_confirmation() -> int:
    (protocol, state_lock, seeds, rows, pf2, _pool, freeze_rows, benches,
     idx_of) = load_context()
    confirmation = protocol["confirmation"]
    p_refs = {cid: float(sum(ref_views(row)["P"].values()))
              for cid, row in freeze_rows.items()}
    raw_states, all_valid = [], True
    started = time.perf_counter()
    for ordinal, row in enumerate(rows, 1):
        state = assemble(row, benches)
        pf2_state = pf2[state.state_id]
        anchor = p11_anchor(pf2_state)
        identity = proposal_identity(state.state_id, anchor)
        allocation, arrays = construct_allocation_gradient(
            state, anchor, seeds["confirmation"]["gradient_seeds"],
            protocol["gradient_construction"]["samples_per_seed"],
            protocol["gradient_construction"]["pilot_source_mix_alpha"])
        sample_artifact = persist_sample_arrays(
            state.state_id, arrays, identity,
            seeds["confirmation"]["gradient_seeds"], "confirmation")
        arms, update = build_allocation_arms(
            anchor, allocation, protocol, arrays=arrays)
        index = idx_of[(state.config_id, state.s2)]
        probability = {"A0": float(pf2_state["probability"]["P11"])}
        probability_record = evaluate_proposal(
            arms["A1"], state.bench_cfg, [1010001 + index, 1],
            confirmation["new_A1_probability_characterization_n"], 10)
        probability["A1"] = float(probability_record["P_hat"])
        rng_keys = [[1001001 + index, 50000 + int(replicate)]
                    for replicate in seeds["confirmation"][
                        "evaluation_replicate_ids"]]
        evaluations = evaluate_arms(
            arms, state.bench_cfg, rng_keys,
            confirmation["evaluation_n_per_arm_replicate"],
            confirmation["evaluation_batches"])
        selected = select_freeoracle(evaluations, probability)
        arm_vrf = {
            arm: [budget_vrf(
                p_refs[state.config_id], record["M2"], probability[arm],
                int(record["n_eval"]),
                confirmation["deployable_selected_arm_budget"])
                for record in evaluations[arm]]
            for arm in ARM_ORDER
        }
        finite = all(record["nonfinite_weights"] == 0
                     for values in evaluations.values() for record in values)
        support = all(record["ESS"] >= 20.0
                      for values in evaluations.values() for record in values)
        simplex = bool(np.isclose(np.sum(update["alpha_prime"]), 1.0)
                       and np.all(np.asarray(update["alpha_prime"]) > 0.0))
        valid = finite and support and simplex
        all_valid = all_valid and valid
        raw_states.append({
            "state_id": state.state_id, "state_key": row["state_key"],
            "class": row["class"], "full_grid_index": index,
            "p_ref": p_refs[state.config_id],
            "anchor_identity": identity, "sample_artifact": sample_artifact,
            "allocation": jsonable(allocation), "update": jsonable(update),
            "probability": probability,
            "A1_probability_record": probability_record,
            "evaluations": evaluations, "arm_vrf": arm_vrf,
            "freeoracle_selected_arm": selected,
            "finite": finite, "support_pass": support,
            "simplex_pass": simplex, "valid": valid,
        })
        print(f"[PF3-A {ordinal:02d}/24] {state.state_id} selected={selected} "
              f"TV={update['TV_alpha_prime_alpha']:.4f} "
              f"elapsed={time.perf_counter()-started:.0f}s", flush=True)
    raw = {
        "schema_version": "raretopo-m4pf3-confirmation-raw-v0",
        "stage": "M4-PF3-A", "git_commit": git_head(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "protocol_hashes": {
            name: sha256_file(REPO / "configs" / "phase_m4pf3" / name)
            for name in ("m4pf3_protocol.json", "m4pf3_states.json",
                         "m4pf3_seeds.json")},
        "state_source_hash": state_lock["source_sha256"],
        "route_source_hash": protocol["routing"]["source_sha256"],
        "numerical_safety_pass": all_valid,
        "states": raw_states,
    }
    RESULT.mkdir(parents=True, exist_ok=True)
    (RESULT / "m4pf3_confirmation_raw.json").write_text(
        json.dumps(raw, indent=1, allow_nan=False), encoding="utf-8")
    summarize(raw, protocol)
    print(json.dumps({"states": len(raw_states),
                      "numerical_safety_pass": all_valid}, indent=2))
    return 0 if all_valid else 5


def arm_summary(state_rows: list[dict], arm: str) -> dict:
    rows = [row for row in state_rows if row["arm"] == arm]
    vrf = [row["VRF_budget"] for row in rows]
    return {
        "arm": arm,
        "allocation_on": arm == "A1",
        "state_count": len(rows),
        "median_VRF": median(vrf),
        "fraction_states_gt_0_1": sum(value > 0.1 for value in vrf) / len(vrf),
        "fraction_states_gt_1": sum(value > 1.0 for value in vrf) / len(vrf),
        "worst_state_VRF": min(vrf),
        "WIDEN_median_VRF": median(
            row["VRF_budget"] for row in rows if row["action_class"] == "WIDEN"),
        "SHRINK_median_VRF": median(
            row["VRF_budget"] for row in rows if row["action_class"] == "SHRINK"),
        "all_valid": all(row["valid"] for row in rows),
    }


def summarize(raw: dict, protocol: dict) -> None:
    confirmation = protocol["confirmation"]
    state_rows, component_rows, coverage_rows, diagnostic_rows = [], [], [], []
    tail_rows, ledger = [], []
    pf3_0 = {row["state_id"]: row for row in csv.DictReader(
        PF3_0_STATES.open(encoding="utf-8"))}
    for state in raw["states"]:
        update = state["update"]
        post = update["post_update_diagnostics"]
        alloc0 = state["allocation"]
        alloc1 = post["allocation_after"]
        coverage0 = post["coverage_A0"]
        coverage1 = post["coverage_A1_reweighted"]
        for arm in ARM_ORDER:
            records = state["evaluations"][arm]
            vrfs = state["arm_vrf"][arm]
            state_rows.append({
                "state_id": state["state_id"],
                "config_id": state["state_key"]["config_id"],
                "s2": state["state_key"]["s2"],
                "action_class": state["class"], "arm": arm,
                "allocation_on": arm == "A1",
                "alpha_before_json": encoded(update["alpha"]),
                "alpha_after_json": encoded(update["alpha_prime"]),
                "allocation_direction_norm": update["direction_norm"],
                "logit_step_norm": update["delta_beta_norm"] if arm == "A1" else 0.0,
                "TV_alpha_prime_alpha": update["TV_alpha_prime_alpha"] if arm == "A1" else 0.0,
                "KL_alpha_prime_alpha": update["KL_alpha_prime_alpha"] if arm == "A1" else 0.0,
                "selected_by_freeoracle": arm == state["freeoracle_selected_arm"],
                "M2": median(record["M2"] for record in records),
                "VRF_proposal": median(vrfs), "VRF_budget": median(vrfs),
                "ESS": median(record["ESS"] for record in records),
                "max_normalized_weight": median(
                    record["max_normalized_weight"] for record in records),
                "top_1pct_weight_mass": median(
                    record["top_1pct_weight_mass"] for record in records),
                "top_0_1pct_weight_mass": median(
                    record["top_0_1pct_weight_mass"] for record in records),
                "nonfinite_weight_count": sum(
                    record["nonfinite_weights"] for record in records),
                "underflow_count": sum(
                    record["event_weight_underflow_count"] for record in records),
                "support_loss_count": sum(record["ESS"] < 20.0
                                          for record in records),
                "fallback_count": int(not state["valid"]),
                "valid": state["valid"],
            })
            for replicate, (record, vrf) in enumerate(zip(records, vrfs), 1):
                tail_rows.append({
                    "state_id": state["state_id"], "arm": arm,
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
        for k, (alpha0, r0, alpha1, r1) in enumerate(zip(
                alloc0["alpha"], alloc0["r_bar"], update["alpha_prime"],
                alloc1["r_bar"])):
            component_rows.append({
                "state_id": state["state_id"], "action_class": state["class"],
                "component_index": k, "alpha_A0": alpha0,
                "r_bar_A0": r0,
                "starvation_ratio_A0": r0 / (alpha0 + 1e-15),
                "allocation_direction": alloc0["descent_direction"][k],
                "alpha_A1": alpha1, "r_bar_A1_reweighted": r1,
                "starvation_ratio_A1_reweighted": r1 / (alpha1 + 1e-15),
                "alpha_change": alpha1 - alpha0,
                "TV_state": update["TV_alpha_prime_alpha"],
                "KL_state": update["KL_alpha_prime_alpha"],
            })
        coverage_rows.append({
            "state_id": state["state_id"], "action_class": state["class"],
            "U99_A0": coverage0["U99"],
            "U99_A1_reweighted": coverage1["U99"],
            "U999_A0": coverage0["U999"],
            "U999_A1_reweighted": coverage1["U999"],
            "top_1pct_uncovered_A0":
                coverage0["top_1pct"]["uncovered_fraction_within_tail"],
            "top_1pct_uncovered_A1_reweighted":
                coverage1["top_1pct"]["uncovered_fraction_within_tail"],
            "M2_reweighted_log_ratio": post["M2_reweighted_log_ratio"],
        })
        source = pf3_0[state["state_id"]]
        diagnostic_rows.append({
            "state_id": state["state_id"], "action_class": state["class"],
            "PF3_0_S0_A_alloc": source["A_alloc"],
            "PF3_0_S0_U99": source["U99"],
            "P11_A_alloc": alloc0["A_alloc"],
            "P11_A1_reweighted_A_alloc": alloc1["A_alloc"],
            "P11_U99": coverage0["U99"],
            "A1_reweighted_U99": coverage1["U99"],
            "TV_alpha_prime_alpha": update["TV_alpha_prime_alpha"],
            "KL_alpha_prime_alpha": update["KL_alpha_prime_alpha"],
            "freeoracle_selected_arm": state["freeoracle_selected_arm"],
            "paired_median_log_VRF_A1_A0": median(
                math.log(a1 / a0) for a0, a1 in zip(
                    state["arm_vrf"]["A0"], state["arm_vrf"]["A1"])),
        })
        ledger.extend([
            {"record_type": "counterfactual_deployable",
             "state_id": state["state_id"],
             "arm": state["freeoracle_selected_arm"],
             "deployable_cost": confirmation["deployable_selected_arm_budget"],
             "audit_only_cost": 0,
             "cost_semantics": "FreeOracle selected final arm only"},
            {"record_type": "AUDIT_FRESH_P11_GRADIENT",
             "state_id": state["state_id"], "arm": "SHARED",
             "deployable_cost": 0,
             "audit_only_cost": protocol["gradient_construction"][
                 "pooled_samples_per_state"],
             "cost_semantics": "actual construction excluded from FreeOracle"},
            {"record_type": "AUDIT_A1_PROBABILITY",
             "state_id": state["state_id"], "arm": "A1",
             "deployable_cost": 0,
             "audit_only_cost": confirmation[
                 "new_A1_probability_characterization_n"],
             "cost_semantics": "actual probability characterization"},
            {"record_type": "AUDIT_TWO_ARM_EVALUATION",
             "state_id": state["state_id"], "arm": "SHARED",
             "deployable_cost": 0,
             "audit_only_cost": len(ARM_ORDER)
                 * confirmation["evaluation_replicates"]
                 * confirmation["evaluation_n_per_arm_replicate"],
             "cost_semantics": "actual two-arm confirmatory search"},
        ])
    discovery_cost = len(protocol["discovery"]["state_ids"]) * (
        protocol["discovery"]["gradient_seed_count"]
        * protocol["discovery"]["gradient_samples_per_seed"]
        + len(ARM_ORDER) * protocol["discovery"]["evaluation_replicates"]
        * protocol["discovery"]["evaluation_samples_per_replicate"])
    ledger.append({
        "record_type": "AUDIT_DISCOVERY", "state_id": "PF3-A-D",
        "arm": "SHARED", "deployable_cost": 0,
        "audit_only_cost": discovery_cost,
        "cost_semantics": "two-state implementation safety discovery"})

    arms = [arm_summary(state_rows, arm) for arm in ARM_ORDER]
    by_arm = {row["arm"]: row for row in arms}
    selected_vrf = []
    for state in raw["states"]:
        selected_vrf.append(median(
            state["arm_vrf"][state["freeoracle_selected_arm"]]))
    selected_counts = Counter(state["freeoracle_selected_arm"]
                              for state in raw["states"])
    paired_logs = [row["paired_median_log_VRF_A1_A0"]
                   for row in diagnostic_rows]
    neutral = 0.009950330853168092
    freeoracle_median = median(selected_vrf)
    allocation_essential = bool(
        selected_counts.get("A1", 0) > 0
        and freeoracle_median > by_arm["A0"]["median_VRF"])
    pf2_summary = json.loads(PF2_SUMMARY_PATH.read_text(encoding="utf-8"))
    pf2_p11 = next(row["median_VRF"] for row in pf2_summary["cells"]
                   if row["cell"] == "P11")
    reproduction_difference = abs(
        by_arm["A0"]["median_VRF"] - pf2_p11) / pf2_p11
    valid = bool(raw["numerical_safety_pass"] and reproduction_difference <=
                 protocol["baseline_reproduction"][
                     "median_vrf_relative_tolerance_vs_pf2_P11"])
    verdict = ("PF3-E" if not valid else
               "PF3-A" if freeoracle_median > 1.0 and allocation_essential else
               "PF3-C" if freeoracle_median > 0.1 else "PF3-D")
    confirmation_cost = sum(int(row["audit_only_cost"]) for row in ledger
                            if row["record_type"] != "AUDIT_DISCOVERY")
    summary = {
        "schema_version": "raretopo-m4pf3-family-summary-v0",
        "stage": "M4-PF3-A", "route": "A", "state_count": 24,
        "class_counts": {"WIDEN": 12, "SHRINK": 12},
        "arms": arms,
        "freeoracle": {
            "median_VRF": freeoracle_median,
            "fraction_states_gt_0_1": sum(v > 0.1 for v in selected_vrf) / 24,
            "fraction_states_gt_1": sum(v > 1.0 for v in selected_vrf) / 24,
            "worst_state_VRF": min(selected_vrf),
            "selected_arm_counts": dict(selected_counts),
        },
        "mechanism": {
            "median_log_VRF_A1_A0": median(paired_logs),
            "states_improves": sum(value > neutral for value in paired_logs),
            "states_worsens": sum(value < -neutral for value in paired_logs),
            "states_neutral": sum(abs(value) <= neutral for value in paired_logs),
            "allocation_essential_for_breakthrough": allocation_essential,
            "median_TV": median(row["TV_alpha_prime_alpha"]
                                for row in diagnostic_rows),
            "median_KL": median(row["KL_alpha_prime_alpha"]
                                for row in diagnostic_rows),
            "median_P11_A_alloc": median(float(row["P11_A_alloc"])
                                         for row in diagnostic_rows),
            "median_A1_reweighted_A_alloc": median(
                float(row["P11_A1_reweighted_A_alloc"])
                for row in diagnostic_rows),
        },
        "coverage": {
            "median_U99_A0": median(row["U99_A0"] for row in coverage_rows),
            "median_U99_A1_reweighted": median(
                row["U99_A1_reweighted"] for row in coverage_rows),
            "median_U999_A0": median(row["U999_A0"] for row in coverage_rows),
            "median_U999_A1_reweighted": median(
                row["U999_A1_reweighted"] for row in coverage_rows),
        },
        "A0_reproduction": {
            "pf2_P11": pf2_p11,
            "pf3_A0": by_arm["A0"]["median_VRF"],
            "relative_difference": reproduction_difference,
            "relative_tolerance": protocol["baseline_reproduction"][
                "median_vrf_relative_tolerance_vs_pf2_P11"],
            "pass": reproduction_difference <= protocol[
                "baseline_reproduction"][
                    "median_vrf_relative_tolerance_vs_pf2_P11"],
        },
        "numerical_safety_pass": raw["numerical_safety_pass"],
        "primary_gate_gt_1": freeoracle_median > 1.0,
        "material_gate_gt_0_1": freeoracle_median > 0.1,
        "verdict": verdict,
        "protocol_hashes": raw["protocol_hashes"],
        "cost_accounting": {
            "deployable_selected_arm_budget": confirmation[
                "deployable_selected_arm_budget"],
            "confirmation_audit_only_samples": confirmation_cost,
            "discovery_audit_only_samples": discovery_cost,
            "total_actual_pf3_samples": confirmation_cost + discovery_cost,
        },
        "claim_boundary": (
            "locked one-step P11-anchor two-arm FreeOracle feasibility; "
            "not deployable allocation control"),
    }
    SUMMARY.mkdir(parents=True, exist_ok=True)
    write_csv(SUMMARY / "m4pf3_family_summary.csv", arms)
    write_csv(SUMMARY / "m4pf3_state_results.csv", state_rows)
    write_csv(SUMMARY / "m4pf3_tail_diagnostics.csv", tail_rows)
    write_csv(SUMMARY / "m4pf3_cost_ledger.csv", ledger)
    write_csv(SUMMARY / "m4pf3_state_diagnostics.csv", diagnostic_rows)
    write_csv(SUMMARY / "m4pf3_component_allocation.csv", component_rows)
    write_csv(SUMMARY / "m4pf3_coverage_diagnostics.csv", coverage_rows)
    write_csv(SUMMARY / "m4pf3_birth_candidates.csv", [{
        "route": "A", "birth_authorized": False,
        "candidate_count": 0,
        "reason": "PF3-0 aggregate coverage-material gate false",
    }])
    (SUMMARY / "m4pf3_family_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_final_source_manifest(raw)


def write_final_source_manifest(raw: dict) -> None:
    sources = []
    fixed = [
        "configs/phase_m4pf3/m4pf3_protocol.json",
        "configs/phase_m4pf3/m4pf3_states.json",
        "configs/phase_m4pf3/m4pf3_seeds.json",
        "results/phase_m4pf3_0/summary/m4pf3_0_diagnostic_summary.json",
        "results/phase_m4pf2/m4pf2_confirmation_raw.json",
        "results/phase_m4pf3/m4pf3_discovery.json",
        "results/phase_m4pf3/m4pf3_confirmation_raw.json",
    ]
    for path in fixed:
        sources.append({"path": path, "sha256": sha256_file(REPO / path),
                        "read_only_after_confirmation": True})
    for state in raw["states"]:
        artifact = state["sample_artifact"]
        sources.append({
            "path": artifact["path"], "sha256": artifact["sha256"],
            "state_id": state["state_id"], "role": "fresh P11 arrays",
            "read_only_after_confirmation": True,
        })
    manifest = {
        "schema_version": "raretopo-m4pf3-source-manifest-v0",
        "source_count": len(sources), "sources": sources,
    }
    (SUMMARY / "m4pf3_source_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("discovery", "confirmation",
                                             "summarize"), required=True)
    args = parser.parse_args()
    if args.stage == "discovery":
        return run_discovery()
    if args.stage == "confirmation":
        return run_confirmation()
    protocol, _, _ = load_locks(REPO)
    raw = json.loads((RESULT / "m4pf3_confirmation_raw.json").read_text(
        encoding="utf-8"))
    summarize(raw, protocol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
