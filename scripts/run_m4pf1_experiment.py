"""Run the preregistered M4-PF1 discovery or confirmatory experiment."""

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
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m4pf1.experiment import (
    attach_vrf,
    build_structured_proposal,
    estimate_pooled_gradient,
    evaluate_proposal,
    freeoracle_candidate,
    load_locks,
    sha256_file,
    validate_state_lock,
)

REPO = Path(__file__).resolve().parents[1]
RESULT = REPO / "results" / "phase_m4pf1"
SUMMARY = RESULT / "summary"
POOL_PATH = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_candidate_pool.json"
STABILITY_PATH = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
M3CA_PATH = REPO / "results" / "phase_m3ca" / "summary" / \
    "m3ca_cost_attribution.json"


def median(values) -> float:
    return float(statistics.median(float(x) for x in values))


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def proposal_probability(prop, bench_cfg, rng_key: list[int], n: int) -> dict:
    return evaluate_proposal(prop, bench_cfg, rng_key, int(n), 10)


def load_context():
    protocol, state_lock, seeds = load_locks(REPO)
    rows = validate_state_lock(REPO, state_lock)
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    stability = json.loads(STABILITY_PATH.read_text(encoding="utf-8"))
    freeze_rows = {row["config_id"]: row for row in
                   load_freeze()["benchmark_configs"]}
    bench = {cid: config_from_record(row) for cid, row in freeze_rows.items()}
    full_keys = sorted((row["config_id"], float(row["s2"]))
                       for row in pool["states_legal"])
    idx_of = {key: idx for idx, key in enumerate(full_keys)}
    return protocol, state_lock, seeds, rows, pool, stability, freeze_rows, bench, idx_of


def assemble(row: dict, bench: dict):
    state = assemble_state(bench[row["state_key"]["config_id"]],
                           float(row["state_key"]["s2"]))
    if isinstance(state, dict):
        raise RuntimeError(f"locked PF1 state failed assembly: {row['state_id']}")
    if state.state_id != row["state_id"]:
        raise RuntimeError(f"state id mismatch: {row['state_id']}")
    return state


def state_gradient_and_proposals(state, gradient_seeds: list[int],
                                 n_gradient: int, protocol: dict):
    gradient = estimate_pooled_gradient(
        state, gradient_seeds, n_gradient,
        protocol["gradient_construction"]["pilot_source_mix_alpha"])
    proposals = {"base": state.proposal()}
    updates = {}
    for family, rank in (("S1", 1), ("S2", 2)):
        proposals[family], updates[family] = build_structured_proposal(
            state, np.asarray(gradient["gradient_matrix"]), rank,
            protocol["update"])
    return gradient, proposals, updates


def run_discovery() -> int:
    protocol, _state_lock, seeds, rows, _pool, _stability, _freeze, bench, idx_of = \
        load_context()
    wanted = set(protocol["discovery"]["state_ids"])
    chosen = [row for row in rows if row["state_id"] in wanted]
    if len(chosen) != len(wanted):
        raise RuntimeError("discovery state lock is not resolvable")
    records = []
    all_valid = True
    for row in chosen:
        state = assemble(row, bench)
        gradient, proposals, updates = state_gradient_and_proposals(
            state, seeds["discovery"]["gradient_seeds"],
            int(protocol["discovery"]["gradient_samples_per_seed"]), protocol)
        idx = idx_of[(state.config_id, state.s2)]
        evaluations = {}
        for family in ("S1", "S2"):
            evaluations[family] = []
            for replicate in seeds["discovery"]["evaluation_replicate_ids"]:
                rng_key = [740001 + idx, 20000 + int(replicate)]
                evaluations[family].append(evaluate_proposal(
                    proposals[family], state.bench_cfg, rng_key,
                    int(protocol["discovery"]["evaluation_samples_per_replicate"]),
                    2))
        valid = bool(all(update["valid"] for update in updates.values()) and
                     all(rec["nonfinite_weights"] == 0
                         for family in evaluations.values() for rec in family))
        all_valid = all_valid and valid
        records.append({
            "state_id": state.state_id,
            "class": row["class"],
            "gradient_matrix": np.asarray(gradient["gradient_matrix"]).tolist(),
            "spectral": {key: (value.tolist() if isinstance(value, np.ndarray)
                                else value)
                         for key, value in gradient["spectral"].items()},
            "updates": {family: {
                key: (value.tolist() if isinstance(value, np.ndarray) else value)
                for key, value in update.items()}
                        for family, update in updates.items()},
            "evaluations": evaluations,
            "valid": valid,
        })
    output = {
        "schema_version": "raretopo-m4pf1-discovery-v0",
        "stage": "PF1-D",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_head(),
        "protocol_may_change": False,
        "records": records,
        "pass": bool(all_valid),
    }
    RESULT.mkdir(parents=True, exist_ok=True)
    (RESULT / "m4pf1_discovery.json").write_text(
        json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"stage": "PF1-D", "states": len(records),
                      "pass": all_valid}, indent=2))
    return 0 if all_valid else 4


def _jsonable_gradient(gradient: dict) -> dict:
    return {
        key: (value.tolist() if isinstance(value, np.ndarray) else value)
        for key, value in gradient.items()
        if key != "spectral"
    } | {"spectral": {
        key: (value.tolist() if isinstance(value, np.ndarray) else value)
        for key, value in gradient["spectral"].items()}}


def _efficiency_class(vrf: float) -> str:
    if vrf > 1.0:
        return "ABSOLUTE_EFFICIENT"
    if vrf > 0.1:
        return "MATERIAL_BELOW_ONE"
    return "BELOW_0.1"


def run_confirmation() -> int:
    (protocol, state_lock, seeds, rows, pool, stability, freeze_rows, bench,
     idx_of) = load_context()
    confirmation = protocol["confirmation"]
    update_lock = protocol["update"]
    m3ca = json.loads(M3CA_PATH.read_text(encoding="utf-8"))
    p_refs = {cid: float(sum(ref_views(row)["P"].values()))
              for cid, row in freeze_rows.items()}
    raw_states = []
    scalar_max_abs = 0.0
    numerical_valid = True
    started = time.perf_counter()

    for ordinal, row in enumerate(rows, 1):
        state = assemble(row, bench)
        key = f"{state.config_id}|{state.s2}"
        idx = idx_of[(state.config_id, state.s2)]
        gradient, structured, updates = state_gradient_and_proposals(
            state, seeds["confirmation"]["gradient_seeds"],
            int(protocol["gradient_construction"]["samples_per_seed"]), protocol)
        scalar = state_arms(state, float(update_lock["eta"]))
        proposals = {"base": scalar["base"], "widen": scalar["widen"],
                     "shrink": scalar["shrink"],
                     "S1_structured": structured["S1"],
                     "S2_structured": structured["S2"]}

        probability = {
            "base": float(pool["reference_fields"][key]["arms"]["base"]["P"]),
            "widen": float(pool["reference_fields"][key]["arms"]["widen"]["P"]),
            "shrink": float(pool["reference_fields"][key]["arms"]["shrink"]["P"]),
        }
        probability_records = {}
        for family, code in (("S1", 1), ("S2", 2)):
            arm = f"{family}_structured"
            rec = proposal_probability(
                proposals[arm], state.bench_cfg, [810001 + idx, code],
                int(confirmation["structured_probability_characterization_n"]))
            probability[arm] = float(rec["P_hat"])
            probability_records[family] = rec

        evaluations = {name: [] for name in proposals}
        frozen_reps = stability["entries"][key]["replicates"]
        for replicate in seeds["confirmation"]["evaluation_replicate_ids"]:
            rng_key = [701001 + idx, 10000 + int(replicate)]
            for name, proposal in proposals.items():
                rec = evaluate_proposal(
                    proposal, state.bench_cfg, rng_key,
                    int(confirmation["evaluation_n_per_replicate"]),
                    int(confirmation["evaluation_batches"]))
                evaluations[name].append(rec)
            for arm in ("base", "widen", "shrink"):
                frozen = float(frozen_reps[int(replicate) - 1]["M2"][arm])
                scalar_max_abs = max(
                    scalar_max_abs, abs(evaluations[arm][-1]["M2"] - frozen))

        s0_selected = {"WIDEN": "widen", "SHRINK": "shrink",
                       "HOLD": "base"}[row["oracle_action"]]
        selected = {
            "S0": s0_selected,
            "S1": freeoracle_candidate(
                {"base": evaluations["base"],
                 "structured": evaluations["S1_structured"]},
                {"base": probability["base"],
                 "structured": probability["S1_structured"]}),
            "S2": freeoracle_candidate(
                {"base": evaluations["base"],
                 "structured": evaluations["S2_structured"]},
                {"base": probability["base"],
                 "structured": probability["S2_structured"]}),
        }
        selected_arm = {
            "S0": selected["S0"],
            "S1": "base" if selected["S1"] == "base" else "S1_structured",
            "S2": "base" if selected["S2"] == "base" else "S2_structured",
        }
        family_vrf = {}
        for family, arm in selected_arm.items():
            family_vrf[family] = attach_vrf(
                evaluations[arm], p_refs[state.config_id], probability[arm],
                int(confirmation["selected_arm_deployable_budget"]))

        state_valid = bool(all(update["valid"] for update in updates.values()) and
                           all(rec["nonfinite_weights"] == 0
                               for arm in evaluations.values() for rec in arm))
        numerical_valid = numerical_valid and state_valid
        raw_states.append({
            "state_id": state.state_id,
            "state_key": row["state_key"],
            "class": row["class"],
            "oracle_action": row["oracle_action"],
            "full_grid_index": idx,
            "p_ref": p_refs[state.config_id],
            "gradient": _jsonable_gradient(gradient),
            "updates": {family: {
                key2: (value.tolist() if isinstance(value, np.ndarray) else value)
                for key2, value in update.items()}
                        for family, update in updates.items()},
            "probability": probability,
            "probability_records": probability_records,
            "evaluations": evaluations,
            "selected_arm": selected_arm,
            "family_vrf": family_vrf,
            "valid": state_valid,
        })
        print(f"[PF1-C {ordinal:02d}/24] {state.state_id} "
              f"selected={selected_arm} elapsed={time.perf_counter()-started:.0f}s",
              flush=True)

    scalar_reproduction = bool(scalar_max_abs <= 5.1e-9)
    protocol_hashes = {
        name: sha256_file(REPO / "configs" / "phase_m4pf1" / name)
        for name in ("m4pf1_protocol.json", "m4pf1_states.json",
                     "m4pf1_seeds.json")}
    raw = {
        "schema_version": "raretopo-m4pf1-confirmation-raw-v0",
        "stage": "PF1-C",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_head(),
        "protocol_hashes": protocol_hashes,
        "state_source_hash_verified": True,
        "states": raw_states,
        "scalar_replay_max_abs_m2_error": scalar_max_abs,
        "scalar_reproduction_pass": scalar_reproduction,
        "numerical_safety_pass": numerical_valid,
    }
    RESULT.mkdir(parents=True, exist_ok=True)
    (RESULT / "m4pf1_confirmation_raw.json").write_text(
        json.dumps(raw, indent=1, allow_nan=False), encoding="utf-8")
    summarize(raw, protocol, m3ca, state_lock)
    print(json.dumps({
        "states": len(raw_states),
        "scalar_replay_max_abs_m2_error": scalar_max_abs,
        "scalar_reproduction_pass": scalar_reproduction,
        "numerical_safety_pass": numerical_valid,
    }, indent=2))
    return 0 if scalar_reproduction and numerical_valid else 5


def summarize(raw: dict, protocol: dict, m3ca: dict, state_lock: dict) -> None:
    state_rows = []
    tail_rows = []
    ledger = []
    confirmation = protocol["confirmation"]
    ranks = {"S0": 0, "S1": 1, "S2": 2}
    for state in raw["states"]:
        s0_m2 = median(state["evaluations"][state["selected_arm"]["S0"]][i]["M2"]
                       for i in range(int(confirmation["evaluation_replicates"])))
        spectral = state["gradient"]["spectral"]
        for family in ("S0", "S1", "S2"):
            arm = state["selected_arm"][family]
            records = state["evaluations"][arm]
            vrfs = state["family_vrf"][family]
            update = state["updates"].get(family)
            row = {
                "state_id": state["state_id"],
                "config_id": state["state_key"]["config_id"],
                "s2": state["state_key"]["s2"],
                "action_class": state["class"],
                "family": family,
                "rank": ranks[family],
                "eta": 0.0 if family == "S0" else protocol["update"]["eta"],
                "selected_arm": arm,
                "M2": median(rec["M2"] for rec in records),
                "VRF_proposal": median(vrfs),
                "VRF_budget": median(vrfs),
                "ESS": median(rec["ESS"] for rec in records),
                "condition_number": 1.0 if family == "S0" else
                    update["condition_number"],
                "max_abs_gradient_eigenvalue": max(
                    abs(x) for x in spectral["eigenvalues_abs_order"]),
                "top1_spectral_fraction": spectral["top1_spectral_fraction"],
                "top2_spectral_fraction": spectral["top2_spectral_fraction"],
                "anisotropy_score": spectral["anisotropy_score"],
                "cancellation_score": spectral["cancellation_score"],
                "freeoracle_selected": True,
                "efficiency_class": _efficiency_class(median(vrfs)),
                "M2_ratio_vs_S0": median(rec["M2"] for rec in records) / s0_m2,
                "valid": state["valid"],
            }
            state_rows.append(row)
            for replicate, (rec, vrf) in enumerate(zip(records, vrfs), 1):
                tail_rows.append({
                    "state_id": state["state_id"], "family": family,
                    "selected_arm": arm, "replicate": replicate,
                    "VRF_budget": vrf, "M2": rec["M2"],
                    "ESS": rec["ESS"],
                    "max_normalized_weight": rec["max_normalized_weight"],
                    "top_1pct_weight_mass": rec["top_1pct_weight_mass"],
                    "top_0_1pct_weight_mass": rec["top_0_1pct_weight_mass"],
                    "nonfinite_weights": rec["nonfinite_weights"],
                    "event_weight_underflow_count":
                        rec["event_weight_underflow_count"],
                })
            ledger.append({
                "state_id": state["state_id"], "family": family,
                "pilot_cost": 0, "decision_cost": 0,
                "selected_arm_cost":
                    confirmation["selected_arm_deployable_budget"],
                "deployable_cost":
                    confirmation["selected_arm_deployable_budget"],
                "audit_only_gradient_cost":
                    protocol["gradient_construction"]["pooled_sample_count_per_state"]
                    if family in ("S1", "S2") else 0,
                "audit_only_probability_cost":
                    confirmation["structured_probability_characterization_n"]
                    if family in ("S1", "S2") else 0,
                "audit_only_unselected_eval_cost":
                    confirmation["evaluation_n_per_replicate"] *
                    confirmation["evaluation_replicates"],
                "cost_semantics": "FreeOracle: only selected final arm is deployable",
            })

    family_rows = []
    for family in ("S0", "S1", "S2"):
        subset = [row for row in state_rows if row["family"] == family]
        values = [float(row["VRF_budget"]) for row in subset]
        family_rows.append({
            "family": family,
            "rank": ranks[family],
            "state_count": len(subset),
            "median_FreeOracle_VRF": median(values),
            "fraction_states_gt_0_1": sum(v > 0.1 for v in values) / len(values),
            "fraction_states_gt_1": sum(v > 1.0 for v in values) / len(values),
            "median_log_VRF": median(math.log(v) for v in values),
            "worst_state_VRF": min(values),
            "WIDEN_median_VRF": median(
                row["VRF_budget"] for row in subset
                if row["action_class"] == "WIDEN"),
            "SHRINK_median_VRF": median(
                row["VRF_budget"] for row in subset
                if row["action_class"] == "SHRINK"),
            "states_selected_structured": sum(
                "structured" in row["selected_arm"] for row in subset),
            "states_worsened_vs_S0": sum(
                row["M2_ratio_vs_S0"] > 1.0 + 1e-12 for row in subset),
            "all_valid": all(row["valid"] for row in subset),
        })

    by_family = {row["family"]: row for row in family_rows}
    scalar_anchor = float(m3ca["counterfactuals"]["vrf_budget_free_oracle"])
    scalar_diff = abs(by_family["S0"]["median_FreeOracle_VRF"] - scalar_anchor)
    scalar_anchor_pass = bool(scalar_diff <= 1e-12)
    structured = max((by_family["S1"], by_family["S2"]),
                     key=lambda row: row["median_FreeOracle_VRF"])
    valid = bool(raw["scalar_reproduction_pass"] and
                 raw["numerical_safety_pass"] and scalar_anchor_pass and
                 len(state_rows) == 72)
    best = float(structured["median_FreeOracle_VRF"])
    if not valid:
        verdict = "PF1-D"
    elif best > 1.0:
        verdict = "PF1-A"
    elif best > 0.1:
        verdict = "PF1-B"
    else:
        verdict = "PF1-C"
    summary = {
        "schema_version": "raretopo-m4pf1-family-summary-v0",
        "stage": "M4-PF1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "families": family_rows,
        "best_structured_family": structured["family"],
        "best_structured_median_FreeOracle_VRF": best,
        "scalar_anchor": scalar_anchor,
        "scalar_observed": by_family["S0"]["median_FreeOracle_VRF"],
        "scalar_anchor_absolute_difference": scalar_diff,
        "scalar_anchor_pass": scalar_anchor_pass,
        "scalar_replay_max_abs_m2_error": raw["scalar_replay_max_abs_m2_error"],
        "numerical_safety_pass": raw["numerical_safety_pass"],
        "state_count": len(raw["states"]),
        "class_counts": dict(Counter(state["class"] for state in raw["states"])),
        "primary_gate_gt_1": bool(best > 1.0),
        "secondary_gate_gt_0_1": bool(best > 0.1),
        "verdict": verdict,
        "protocol_hashes": raw["protocol_hashes"],
        "state_source_hash": state_lock["source_sha256"],
        "claim_boundary": "FreeOracle proposal-family feasibility; not deployable controller efficiency",
    }
    SUMMARY.mkdir(parents=True, exist_ok=True)
    (SUMMARY / "m4pf1_family_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    write_csv(SUMMARY / "m4pf1_family_summary.csv", family_rows)
    write_csv(SUMMARY / "m4pf1_state_table.csv", state_rows)
    write_csv(SUMMARY / "m4pf1_tail_diagnostics.csv", tail_rows)
    write_csv(SUMMARY / "m4pf1_cost_ledger.csv", ledger)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("discovery", "confirmation"),
                        required=True)
    args = parser.parse_args()
    return run_discovery() if args.stage == "discovery" else run_confirmation()


if __name__ == "__main__":
    raise SystemExit(main())
