"""ER-1 corrected reference replay for the frozen 24-state M3-D benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d.reference_direction import BATCHES_REF, crn_batched_eval, label_state


REPO = Path(__file__).resolve().parents[1]
LEGACY_FREEZE = REPO / "docs/phase_m3d/M3_D_Benchmark_Freeze.json"
OUT = REPO / "results/evidence_repair/reanalysis/M3-D"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_seed_map() -> dict[tuple[str, float], list[int]]:
    result: dict[tuple[str, float], list[int]] = {}
    for path in sorted((REPO / "results/phase_m3d/reference").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        candidates = list(data.get("reference_fields", {}).values())
        candidates += [value for value in data.values()
                       if isinstance(value, dict) and "state_rng_key" in value]
        for value in candidates:
            key = value.get("state_key")
            if key and "state_rng_key" in value:
                result[(key["config_id"], round(float(key["s2"]), 10))] = list(value["state_rng_key"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-ref", type=int, default=500_000)
    args = parser.parse_args()
    legacy = json.loads(LEGACY_FREEZE.read_text(encoding="utf-8"))
    benchmarks = {row["config_id"]: config_from_record(row)
                  for row in load_freeze()["benchmark_configs"]}
    seeds = _reference_seed_map()
    rows = []
    corrected_states = []
    counts = {"WIDEN": 0, "SHRINK": 0, "HOLD": 0,
              "REFERENCE_AMBIGUOUS": 0}
    for index, old in enumerate(legacy["states"], start=1):
        key = (old["config_id"], round(float(old["s2"]), 10))
        if key not in seeds:
            raise RuntimeError(f"missing frozen reference seed for {key}")
        bench = benchmarks[old["config_id"]]
        state = assemble_state(bench, float(old["s2"]))
        if isinstance(state, dict):
            raise RuntimeError(f"frozen state became illegal: {key}: {state}")
        refs = crn_batched_eval(state_arms(state, 0.20), bench, seeds[key],
                                args.n_ref, BATCHES_REF)
        oracle = label_state(refs, refs, tau=0.01)
        action = oracle["oracle_action"]
        counts[action] += 1
        updated = dict(old)
        updated["legacy_oracle_action"] = old["oracle_action"]
        updated["oracle_action"] = action
        updated["direction_margin_Delta_dir"] = oracle["direction_margin_Delta_dir"]
        updated["reference"] = {
            "n_ref_per_arm": args.n_ref,
            "n_batches": BATCHES_REF,
            "state_rng_key": seeds[key],
            "arms": refs,
            "oracle": oracle,
        }
        corrected_states.append(updated)
        old_ref = old["reference"]
        rows.append({
            "state_id": old["state_id"],
            "legacy_class": old["oracle_action"],
            "corrected_class": action,
            "legacy_P_base": "",
            "corrected_P_base": refs["base"]["P"],
            "legacy_M2_base": old_ref["M2_base_ref"],
            "corrected_M2_base": refs["base"]["M2"],
            "absolute_M2_difference": refs["base"]["M2"] - old_ref["M2_base_ref"],
            "relative_M2_difference": refs["base"]["M2"] / old_ref["M2_base_ref"] - 1.0,
            "scientific_consequence": "class_changed" if action != old["oracle_action"] else "class_retained",
        })
        print(f"[{index:02d}/24] {old['state_id']} {old['oracle_action']} -> {action}", flush=True)

    freeze = dict(legacy)
    freeze["schema_version"] = "raretopo-er1-m3d-benchmark-freeze-v1"
    freeze["event_semantics_schema_version"] = 2
    freeze["event_definition_id"] = "topology-label-non-nominal-v1"
    freeze["event_predicate_source"] = "hyptraj.event_semantics.event_indicator_from_topology"
    freeze["legacy_source_path"] = LEGACY_FREEZE.relative_to(REPO).as_posix()
    freeze["legacy_source_sha256"] = _sha(LEGACY_FREEZE)
    freeze["repair_commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
        capture_output=True, text=True).stdout.strip()
    freeze["repair_parent_tag"] = "RareTopo-M3-v1"
    freeze["created_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    freeze["states"] = corrected_states
    freeze["composition"] = counts
    freeze["repair_simulator_calls"] = 24 * 3 * args.n_ref
    freeze["seed_reuse_status"] = "EXACT"
    freeze["draw_order_status"] = "EXACT"
    freeze["probability_semantics_manifest"] = {
        "proposal_arm": "base/shrink/widen",
        "source_stratum": "not applicable to reference-arm draws",
        "p_hat_definition": "mean(I[topology != S0] * p/q)",
        "m2_definition": "mean((I[topology != S0] * p/q)^2)",
        "variance_mass_definition": "per-sample squared event contribution",
        "likelihood_ratio_definition": "p/q_arm",
        "schema_version": 2,
    }
    freeze.pop("freeze_sha256_of_body_above", None)
    body = json.dumps(freeze, indent=1)
    freeze["freeze_sha256_of_body_above"] = hashlib.sha256(body.encode()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    freeze_path = OUT / "m3d_corrected_reference_freeze.json"
    freeze_path.write_text(json.dumps(freeze, indent=1) + "\n", encoding="utf-8")
    with (OUT / "m3d_reference_legacy_vs_corrected.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    gate_pass = counts == {"WIDEN": 8, "SHRINK": 8, "HOLD": 8,
                           "REFERENCE_AMBIGUOUS": 0}
    gate = {
        "schema_version": "raretopo-er1-m3d-reference-gate-v1",
        "event_semantics_schema_version": 2,
        "legacy_source_path": LEGACY_FREEZE.relative_to(REPO).as_posix(),
        "legacy_source_sha256": _sha(LEGACY_FREEZE),
        "corrected_freeze_path": freeze_path.relative_to(REPO).as_posix(),
        "corrected_freeze_sha256": _sha(freeze_path),
        "observed_composition": counts,
        "required_composition": {"WIDEN": 8, "SHRINK": 8, "HOLD": 8,
                                 "REFERENCE_AMBIGUOUS": 0},
        "gate": "PASS" if gate_pass else "FAIL",
        "online_child_authorized": gate_pass,
        "stop_old_lineage": not gate_pass,
        "repair_simulator_calls": 24 * 3 * args.n_ref,
        "original_frozen_sample_count_per_arm": 500_000,
        "repair_sample_count_per_arm": args.n_ref,
        "seed_reuse_status": "EXACT",
        "draw_order_status": "EXACT",
    }
    (OUT / "m3d_corrected_reference_gate.json").write_text(
        json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gate, indent=2))
    return 0 if gate_pass else 3


if __name__ == "__main__":
    raise SystemExit(main())
