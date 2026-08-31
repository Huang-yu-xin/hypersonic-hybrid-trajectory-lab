"""Stage-gated M3-D2 benchmark-construction pipeline.

Subcommands are intentionally separate so discovery cannot precede the
preregistration commit and confirmation cannot precede the shortlist commit.
No controller module is imported or evaluated here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d2.experiment import (
    classify_reference_state,
    direct_full_event_reference,
    evaluate_reference_arms,
)
from hyptraj.m3d2.selection import (
    TARGET_CLASSES,
    build_final_benchmark,
    build_shortlist,
)

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "configs" / "phase_m3d2"
SUMMARY = REPO / "results" / "phase_m3d2" / "summary"
DISCOVERY = REPO / "results" / "phase_m3d2" / "discovery"
CONFIRMATION = REPO / "results" / "phase_m3d2" / "confirmation"


def _load(name: str) -> dict:
    return json.loads((CFG / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _configs() -> dict:
    wanted = set(_load("m3d2_candidate_states.json")["frozen_config_ids"])
    return {row["config_id"]: config_from_record(row)
            for row in load_freeze()["benchmark_configs"]
            if row["config_id"] in wanted}


def _stratum(s2: float, candidate_cfg: dict) -> str:
    for name, values in candidate_cfg["strata"].items():
        if any(abs(float(value) - s2) < 1e-12 for value in values):
            return name
    raise ValueError(f"s2={s2} absent from strata")


def _candidate_rows() -> list[dict]:
    config = _load("m3d2_candidate_states.json")
    rows = []
    for cid in sorted(config["frozen_config_ids"]):
        for s2 in sorted(float(x) for x in config["s2_grid"]):
            rows.append({
                "candidate_index": len(rows),
                "config_id": cid,
                "state_id": f"{cid.split('_')[-1]}_s2_{int(round(100*s2)):05d}",
                "s2": s2,
                "candidate_stratum": _stratum(s2, config),
            })
    if len(rows) != int(config["candidate_count"]):
        raise RuntimeError("candidate count does not match preregistration")
    return rows


def build_pool() -> int:
    benches = _configs()
    legal, invalid = [], []
    t0 = time.perf_counter()
    for row in _candidate_rows():
        state = assemble_state(benches[row["config_id"]], row["s2"])
        if isinstance(state, dict):
            invalid.append({**row, **state})
            continue
        legal.append({
            **row,
            "selected_mode": state.selected_mode,
            "component_index": state.component_index,
            "component_mean": [float(x) for x in state.component_mean],
            "min_eig_selected": state.min_eig_selected,
            "legality": "LEGAL",
        })
    record = {
        "schema_version": "raretopo-m3d2-candidate-pool-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "source_config": "configs/phase_m3d2/m3d2_candidate_states.json",
        "source_config_sha256": _sha(CFG / "m3d2_candidate_states.json"),
        "states": legal, "invalid_states": invalid,
        "counts": {"legal": len(legal), "invalid": len(invalid),
                   "total": len(legal) + len(invalid)},
        "assembly_simulator_samples": 8 * 20000,
        "wall_clock_s": time.perf_counter() - t0,
    }
    _write_json(SUMMARY / "m3d2_candidate_pool.json", record)
    print(json.dumps(record["counts"], indent=2))
    return 0 if len(legal) == 72 else 2


def probability_reference() -> int:
    protocol = _load("m3d2_protocol.json")
    benches = _configs()
    n = int(protocol["full_event_reference"]["n_per_config"])
    batches = int(protocol["full_event_reference"]["n_batches"])
    records = []
    t0 = time.perf_counter()
    for index, cid in enumerate(sorted(benches)):
        print(f"[PREF {index+1}/8] {cid}", flush=True)
        rec = direct_full_event_reference(benches[cid], [3202000, index],
                                          n, batches)
        records.append({"config_id": cid, **rec})
    payload = {
        "schema_version": "raretopo-m3d2-probability-reference-set-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "records": records,
        "simulator_samples": len(records) * n,
        "wall_clock_s": time.perf_counter() - t0,
    }
    _write_json(SUMMARY / "m3d2_probability_reference.json", payload)
    _write_csv(SUMMARY / "m3d2_probability_reference.csv", records,
               ["config_id", "p_ref_full", "p_ref_full_SE",
                "p_ref_full_CI", "sample_count", "seed_key",
                "sampling_law", "event_definition_id",
                "event_semantics_schema_version"])
    return 0


def _characterize(stage: str) -> int:
    if stage not in {"discovery", "confirmation"}:
        raise ValueError(stage)
    protocol = _load("m3d2_protocol.json")
    classifier = _load("m3d2_classifier_contract.json")
    refs_payload = json.loads((SUMMARY / "m3d2_probability_reference.json")
                              .read_text(encoding="utf-8"))
    refs = {row["config_id"]: row for row in refs_payload["records"]}
    pool = json.loads((SUMMARY / "m3d2_candidate_pool.json")
                      .read_text(encoding="utf-8"))
    pool_map = {row["state_id"]: row for row in pool["states"]}
    if stage == "discovery":
        candidates = pool["states"]
        seed_namespace = 3202001
        outdir = DISCOVERY
    else:
        shortlist = json.loads((SUMMARY / "m3d2_shortlist.json")
                               .read_text(encoding="utf-8"))
        candidates = [pool_map[state_id]
                      for action in TARGET_CLASSES
                      for state_id in shortlist["selected_state_ids"][action]]
        seed_namespace = 3202002
        outdir = CONFIRMATION
    n = int(protocol[stage]["n_per_arm"])
    batches = int(protocol[stage]["n_batches"])
    benches = _configs()
    records = []
    t0 = time.perf_counter()
    for ordinal, candidate in enumerate(candidates, start=1):
        state_id = candidate["state_id"]
        print(f"[{stage.upper()} {ordinal}/{len(candidates)}] {state_id}",
              flush=True)
        state = assemble_state(benches[candidate["config_id"]],
                               float(candidate["s2"]))
        if isinstance(state, dict):
            raise RuntimeError(f"frozen legal candidate became invalid: {state}")
        arms = evaluate_reference_arms(
            state_arms(state, classifier["finite_step_delta_theta"]),
            state.bench_cfg,
            [seed_namespace, int(candidate["candidate_index"])], n, batches)
        verdict = classify_reference_state(
            arms, refs[candidate["config_id"]],
            tau=float(classifier["tie_tolerance_tau"]),
            margin_min=float(classifier["direction_margin_min"]),
            hold_window=float(classifier["hold_window_relative"]),
            support_multiplier=float(classifier["support_multiplier"]),
            min_arm_ess=float(classifier["min_arm_ess"]),
            probability_z=4.0)
        record = {
            **candidate,
            "stage": stage,
            "seed_key": [seed_namespace, int(candidate["candidate_index"])],
            "sample_count_per_arm": n,
            "event_definition_id": "FULL_TOPOLOGY_EVENT_S1_S4",
            "event_semantics_schema_version": 2,
            "p_ref_full": refs[candidate["config_id"]]["p_ref_full"],
            "p_ref_full_SE": refs[candidate["config_id"]]["p_ref_full_SE"],
            "arms": arms,
            **verdict,
        }
        records.append(record)
        _write_json(outdir / f"{state_id}.json", record)
    counts = Counter(row["corrected_class"] for row in records)
    payload = {
        "schema_version": f"raretopo-m3d2-{stage}-summary-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "records": records, "counts": dict(sorted(counts.items())),
        "simulator_samples": len(records) * 3 * n,
        "wall_clock_s": time.perf_counter() - t0,
    }
    _write_json(SUMMARY / f"m3d2_{stage}_summary.json", payload)
    flat = []
    for row in records:
        flat.append({
            **{key: row[key] for key in
               ("candidate_index", "config_id", "state_id", "s2",
                "candidate_stratum", "corrected_class",
                "class_certainty_score", "probability_semantics_valid",
                "reference_action_class_valid", "minimum_arm_ESS")},
            "p_ref_full": row["p_ref_full"],
            "P_base": row["arms"]["base"]["P"],
            "P_widen": row["arms"]["widen"]["P"],
            "P_shrink": row["arms"]["shrink"]["P"],
            "M2_base": row["arms"]["base"]["M2"],
            "M2_widen": row["arms"]["widen"]["M2"],
            "M2_shrink": row["arms"]["shrink"]["M2"],
            "ambiguity_or_invalid_reason": row["ambiguity_or_invalid_reason"],
        })
    fields = list(flat[0]) if flat else []
    _write_csv(SUMMARY / f"m3d2_{stage}_summary.csv", flat, fields)
    print(json.dumps(payload["counts"], indent=2))
    return 0


def shortlist() -> int:
    payload = json.loads((SUMMARY / "m3d2_discovery_summary.json")
                         .read_text(encoding="utf-8"))
    selection = build_shortlist(payload["records"])
    selected_ids = {
        action: [row["state_id"] for row in selection[action]["selected"]]
        for action in TARGET_CLASSES
    }
    record = {
        "schema_version": "raretopo-m3d2-shortlist-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "source_discovery_sha256": _sha(SUMMARY /
                                         "m3d2_discovery_summary.json"),
        "selection": selection,
        "selected_state_ids": selected_ids,
        "confirmation_count": sum(len(ids) for ids in selected_ids.values()),
    }
    _write_json(SUMMARY / "m3d2_shortlist.json", record)
    print(json.dumps({action: len(ids)
                      for action, ids in selected_ids.items()}, indent=2))
    return 0


def class_transition() -> None:
    disc = json.loads((SUMMARY / "m3d2_discovery_summary.json")
                      .read_text(encoding="utf-8"))["records"]
    conf = json.loads((SUMMARY / "m3d2_confirmation_summary.json")
                      .read_text(encoding="utf-8"))["records"]
    dmap = {row["state_id"]: row["corrected_class"] for row in disc}
    rows = [{"state_id": row["state_id"],
             "discovery_class": dmap[row["state_id"]],
             "confirmation_class": row["corrected_class"]}
            for row in conf]
    counts = Counter((row["discovery_class"], row["confirmation_class"])
                     for row in rows)
    for row in rows:
        row["transition"] = (f"{row['discovery_class']}->"
                             f"{row['confirmation_class']}")
    _write_csv(SUMMARY / "m3d2_class_transition.csv", rows,
               ["state_id", "discovery_class", "confirmation_class",
                "transition"])
    _write_json(SUMMARY / "m3d2_class_transition.json", {
        "transitions": [{"discovery": key[0], "confirmation": key[1],
                         "count": value}
                        for key, value in sorted(counts.items())],
        "agreement": (sum(1 for row in rows
                          if row["discovery_class"] ==
                          row["confirmation_class"]) / len(rows)
                      if rows else None),
    })


def finalize() -> int:
    class_transition()
    conf_path = SUMMARY / "m3d2_confirmation_summary.json"
    records = json.loads(conf_path.read_text(encoding="utf-8"))["records"]
    decision = build_final_benchmark(records)
    selected_ids = {
        action: [row["state_id"]
                 for row in decision["classes"][action]["selected"]]
        for action in TARGET_CLASSES
    }
    selected_set = {state_id for ids in selected_ids.values()
                    for state_id in ids}
    selected = [row for row in records if row["state_id"] in selected_set]
    excluded = [row for row in records if row["state_id"] not in selected_set]
    final = {
        "schema_version": "raretopo-m3d2-final-benchmark-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "event_semantics_schema_version": 2,
        "event_definition_id": "FULL_TOPOLOGY_EVENT_S1_S4",
        "source_confirmation_sha256": _sha(conf_path),
        "composition": dict(Counter(row["corrected_class"]
                                    for row in selected)),
        "selection": decision,
        "states": selected if decision["M3D2_1"] == "PASS" else [],
        "controller_online_trials": 0,
    }
    _write_json(SUMMARY / "m3d2_final_benchmark.json", final)
    flat_fields = ["config_id", "state_id", "s2", "corrected_class",
                   "p_ref_full", "class_certainty_score",
                   "minimum_arm_ESS", "event_definition_id",
                   "event_semantics_schema_version", "seed_key",
                   "sample_count_per_arm"]
    _write_csv(SUMMARY / "m3d2_final_benchmark.csv",
               final["states"], flat_fields)
    _write_csv(SUMMARY / "m3d2_excluded_confirmed_states.csv",
               excluded, flat_fields + ["ambiguity_or_invalid_reason"])
    verdict = {
        "schema_version": "raretopo-m3d2-final-verdict-v0",
        "M3D2_1": decision["M3D2_1"],
        "final_verdict": decision["verdict"],
        "class_availability": {
            action: decision["classes"][action]["available"]
            for action in TARGET_CLASSES},
        "class_selected": {action: len(selected_ids[action])
                           for action in TARGET_CLASSES},
        "controller_online_trials": 0,
        "next_authorized_action": (
            "write a separate M3-G2/M3-G-v2 taskbook"
            if decision["verdict"] == "D2-A" else
            "separate scientific decision on state/action family; no controller trial"),
    }
    _write_json(SUMMARY / "m3d2_final_verdict.json", verdict)
    print(json.dumps(verdict, indent=2))
    return 0 if decision["M3D2_1"] == "PASS" else 3


def source_manifest() -> int:
    sources = [
        ("docs/phase_m1d/M1_D_Benchmark_Freeze.json", "RareTopo-M2-v0 parent state family"),
        ("configs/phase_m3/m3_scalar_gradient_v0.json", "corrected candidate-generation prior"),
        ("configs/phase_m3d/m3d_reference_characterization.json", "finite-step classifier source"),
        ("results/evidence_repair/reanalysis/M3-D/m3d_corrected_reference_gate.json", "corrected historical negative gate"),
        ("docs/evidence_repair/ER1_Event_Semantics_Contract.md", "schema-2 semantic contract"),
        ("docs/evidence_repair/ER1_Supersession_Ledger.md", "lineage status"),
    ]
    sources += [(path.relative_to(REPO).as_posix(), "M3-D2 preregistration")
                for path in sorted(CFG.glob("*.json"))]
    entries = []
    for path_text, role in sources:
        path = REPO / path_text
        entries.append({"path": path_text, "sha256": _sha(path),
                        "source_tag_or_commit": _git_head(),
                        "role": role, "read_only": True})
    _write_json(SUMMARY / "m3d2_source_manifest.json", {
        "schema_version": "raretopo-m3d2-source-manifest-v0",
        "created_utc": _utc(), "entries": entries})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["manifest", "build-pool", "pref",
                                          "discovery", "shortlist",
                                          "confirmation", "finalize"])
    args = parser.parse_args()
    if args.stage == "manifest":
        return source_manifest()
    if args.stage == "build-pool":
        return build_pool()
    if args.stage == "pref":
        return probability_reference()
    if args.stage == "discovery":
        return _characterize("discovery")
    if args.stage == "shortlist":
        return shortlist()
    if args.stage == "confirmation":
        return _characterize("confirmation")
    return finalize()


if __name__ == "__main__":
    raise SystemExit(main())
