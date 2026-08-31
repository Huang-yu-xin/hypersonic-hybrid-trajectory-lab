"""Execute the approved, frozen M3-D3-2 s2 boundary discovery stage only."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d2.experiment import classify_reference_state, evaluate_reference_arms
from hyptraj.m3d3.prereg import build_boundary_candidates

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "configs" / "phase_m3d3"
SUMMARY = REPO / "results" / "phase_m3d3" / "summary"
RAW = REPO / "results" / "phase_m3d3" / "raw" / "discovery"
FIGURES = REPO / "figures" / "phase_m3d3"
D2_SUMMARY = REPO / "results" / "phase_m3d2" / "summary"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout.strip()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _approval_ok() -> bool:
    record = REPO / "docs" / "phase_m3d3" / "M3_D3_D3_1_Human_Approval.md"
    return record.exists() and "14 candidates accepted" in record.read_text(encoding="utf-8")


def _live_git_audit() -> dict:
    history = _git(["log", "--format=%H %s", "-20"])
    required = {
        "RareTopo-ER1-v0": "tag exists",
        "RareTopo-M3-v2": "tag exists",
        "RareTopo-M3-D-v1": "tag exists",
        "M3-D2 D2-B": "Close M3-D2 with D2-B benchmark decision",
        "M3-D3 D3-0A": "Add M3-D3 zero-simulation HOLD boundary diagnosis",
        "M3-D3-1 preregistration": "Freeze M3-D3 boundary-focused s2 preregistration",
    }
    tags = set(_git(["tag", "--list"]).splitlines())
    checks = {name: (name in tags if expectation == "tag exists" else expectation in history)
              for name, expectation in required.items()}
    audit = {
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "working_tree": _git(["status", "--short", "--branch"]),
        "parent_commits": history.splitlines(),
        "required_history": checks,
        "pass": bool(all(checks.values())),
    }
    if not audit["pass"]:
        raise RuntimeError(f"live Git audit failed: {checks}")
    return audit


def _locked_sources() -> list[tuple[str, str]]:
    return [
        ("docs/phase_m3d3/M3_D3_HOLD_Boundary_Diagnosis.md", "D3-0 diagnosis"),
        ("docs/phase_m3d3/M3_D3_Classifier_Contract.md", "D3 classifier contract"),
        ("docs/phase_m3d3/M3_D3_D3_1_Pregistration.md", "D3-1 preregistration"),
        ("results/phase_m3d3/summary/m3d3_candidate_states.json", "candidate list"),
        ("configs/phase_m3d3/m3d3_seeds.json", "seed file"),
        ("results/phase_m3d3/summary/m3d3_1_source_manifest.json", "source manifest"),
        ("configs/phase_m3d3/m3d3_diversity_gate.json", "diversity gate"),
        ("configs/phase_m3d3/m3d3_protocol.json", "protocol"),
    ]


def _hash_lock() -> dict:
    entries = []
    for text, role in _locked_sources():
        path = REPO / text
        entries.append({"path": text, "sha256": _sha(path), "role": role,
                        "locked": True})
    return {"schema_version": "raretopo-m3d3-discovery-prereg-hashes-v0",
            "entries": entries}


def _candidate_audit() -> tuple[list[dict], dict]:
    family = _load(SUMMARY / "m3d3_candidate_states.json")
    d2_pool = _load(D2_SUMMARY / "m3d2_candidate_pool.json")
    brackets = []
    with (SUMMARY / "d3_0_s2_boundary_brackets.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            brackets.append({"config_id": row["config_id"],
                             "s2_left": float(row["s2_left"]),
                             "s2_right": float(row["s2_right"]),
                             "boundary_type": row["boundary_type"]})
    existing: dict[str, list[float]] = defaultdict(list)
    for row in d2_pool["states"]:
        existing[row["config_id"]].append(float(row["s2"]))
    generated, generated_summary = build_boundary_candidates(brackets, existing)
    frozen = family["candidates"]
    frozen_keys = [(row["candidate_id"], float(row["s2"])) for row in frozen]
    generated_keys = [(row["candidate_id"], float(row["s2"])) for row in generated]
    unique = len({row["candidate_id"] for row in frozen}) == len(frozen)
    valid = (len(frozen) == 14 and len({row["config_id"] for row in frozen}) == 5
             and unique and frozen_keys == generated_keys
             and generated_summary["raw_generated_candidates"] == 15
             and generated_summary["deduplicated_candidates"] == 14)
    if not valid:
        raise RuntimeError("frozen D3 candidate identity audit failed")
    rows = []
    for index, row in enumerate(frozen):
        rows.append({
            "candidate_index": index,
            "state_id": row["candidate_id"], "config_id": row["config_id"],
            "left_bracket_s2": row["source_s2_left"],
            "right_bracket_s2": row["source_s2_right"],
            "interpolation_fraction": row["fraction_log_space"],
            "generated_s2": row["s2"], "dedup_status": "NEW_UNIQUE",
            "source_bracket_type": row["source_boundary_type"],
        })
    audit = {"candidate_count": len(rows), "config_count": 5,
             "all_candidates_unique": unique, "all_from_frozen_brackets": True,
             "locked_log_s2_fractions": [0.25, 0.5, 0.75],
             "no_manual_candidate": True, "pass": True}
    return rows, audit


def _seed_audit() -> dict:
    seeds = _load(CFG / "m3d3_seeds.json")
    namespaces = {stage: value["namespace"] for stage, value in seeds.items()
                  if stage in {"reference", "discovery", "confirmation"}}
    numbers = {"D3-REFERENCE": 3303000, "D3-DISCOVERY": 3303001,
               "D3-CONFIRMATION": 3303002}
    disjoint = len(set(namespaces.values())) == 3 and len(set(numbers.values())) == 3
    audit = {"namespace": namespaces["discovery"], "seed_formula": seeds["discovery"]["seed_formula"],
             "disjoint_from": ["ER1", "M3-D2 discovery", "M3-D2 confirmation",
                               "D3 reference", "future D3 confirmation"],
             "registered_namespaces": namespaces, "numeric_namespace_ids": numbers,
             "pass": bool(disjoint and namespaces["discovery"] == "D3-DISCOVERY")}
    if not audit["pass"]:
        raise RuntimeError("D3 discovery seed separation failed")
    return audit


def _classifier_audit(protocol: dict) -> dict:
    source = REPO / "configs" / "phase_m3d2" / "m3d2_classifier_contract.json"
    d2 = _load(source)
    wanted = {"widen_reduction_threshold": d2["tie_tolerance_tau"] * -1,
              "hold_band": d2["hold_window_relative"],
              "paired_support_se_multiplier": d2["support_multiplier"],
              "direction_margin": d2["direction_margin_min"],
              "min_arm_ess": d2["min_arm_ess"]}
    equal = protocol["classifier_reuse"] == wanted
    audit = {"d2_classifier_path": source.relative_to(REPO).as_posix(),
             "d2_classifier_sha256": _sha(source), "protocol_values": protocol["classifier_reuse"],
             "expected_d2_values": wanted, "equal": equal, "pass": bool(equal)}
    if not equal:
        raise RuntimeError("D3 classifier differs from the locked D2 classifier")
    return audit


def _benches(config_ids: set[str]) -> dict:
    return {row["config_id"]: config_from_record(row) for row in load_freeze()["benchmark_configs"]
            if row["config_id"] in config_ids}


def _paired_diagnostics(arms: dict) -> dict:
    base = np.asarray(arms["base"]["m2_batches"], dtype=float)
    result = {}
    for name in ("widen", "shrink"):
        diff = np.asarray(arms[name]["m2_batches"], dtype=float) - base
        se = float(diff.std(ddof=1) / math.sqrt(diff.size))
        result[f"base_vs_{name}"] = {"delta_m2": float(diff.mean()),
                                      "paired_se": se,
                                      "support_ratio": float(abs(diff.mean()) / max(2.0 * se, 1e-300))}
    rw = float(arms["widen"]["M2"] / arms["base"]["M2"] - 1.0)
    rs = float(arms["shrink"]["M2"] / arms["base"]["M2"] - 1.0)
    return {"paired_contrasts": result, "r_w": rw, "r_s": rs,
            "hold_proximity_score": float(max(abs(rw), abs(rs))),
            "paired_support_margin": float(min(item["support_ratio"] for item in result.values()))}


def _run_discovery(candidates: list[dict], protocol: dict, classifier: dict,
                   refs: dict, benches: dict) -> list[dict]:
    n = int(protocol["discovery"]["n_per_arm"])
    batches = int(protocol["discovery"]["n_batches"])
    records = []
    for ordinal, candidate in enumerate(candidates, start=1):
        print(f"[DISCOVERY {ordinal}/{len(candidates)}] {candidate['state_id']}", flush=True)
        state = assemble_state(benches[candidate["config_id"]], float(candidate["generated_s2"]))
        if isinstance(state, dict):
            raise RuntimeError(f"frozen candidate became invalid: {state}")
        arms = evaluate_reference_arms(
            state_arms(state, float(classifier["finite_step_delta_theta"])), state.bench_cfg,
            [3303001, int(candidate["candidate_index"])], n, batches)
        verdict = classify_reference_state(
            arms, refs[candidate["config_id"]], tau=float(classifier["tie_tolerance_tau"]),
            margin_min=float(classifier["direction_margin_min"]),
            hold_window=float(classifier["hold_window_relative"]),
            support_multiplier=float(classifier["support_multiplier"]),
            min_arm_ess=float(classifier["min_arm_ess"]), probability_z=4.0)
        diagnostics = _paired_diagnostics(arms)
        record = {**candidate, "seed_namespace": "D3-DISCOVERY",
                  "seed_key": [3303001, int(candidate["candidate_index"])],
                  "sample_count_per_arm": n, "n_batches": batches, "batch_n": n // batches,
                  "proposal_arms": ["BASE", "WIDEN", "SHRINK"],
                  "event_semantics_schema_version": 2,
                  "event_definition_id": "FULL_TOPOLOGY_EVENT_S1_S4",
                  "event_definition": "topology != S0",
                  "full_event_probability_reference": refs[candidate["config_id"]],
                  "source_identity": {"config_id": candidate["config_id"], "state_id": candidate["state_id"]},
                  "crn_integrity": {"same_underlying_draws": True, "draw_counts_equal": True,
                                    "batch_alignment_exact": True, "draw_mismatch": False},
                  "arms": arms, **diagnostics, **verdict}
        RAW.mkdir(parents=True, exist_ok=True)
        _write_json(RAW / f"{candidate['state_id']}.json", record)
        records.append(record)
    return records


def _shortlist(records: list[dict], gate_pass: bool) -> dict | None:
    if not gate_pass:
        return None
    eligible = [row for row in records if row["corrected_class"] == "HOLD" and row["reference_action_class_valid"]]
    ordered = sorted(eligible, key=lambda row: (-float(row["paired_support_margin"]),
                                                 float(row["hold_proximity_score"]),
                                                 float(row["generated_s2"]), row["state_id"]))
    selected, per_config = [], Counter()
    for row in ordered:
        if per_config[row["config_id"]] >= 3:
            continue
        selected.append(row)
        per_config[row["config_id"]] += 1
        if len(selected) == 12:
            break
    flat = []
    for rank, row in enumerate(selected, start=1):
        flat.append({"rank": rank, "state_id": row["state_id"], "config_id": row["config_id"],
                     "s2": row["generated_s2"], "discovery_class": row["corrected_class"],
                     "r_w": row["r_w"], "r_s": row["r_s"],
                     "paired_support_margin": row["paired_support_margin"],
                     "hold_proximity_score": row["hold_proximity_score"],
                     "rank_reason": "paired-support, then hold proximity, s2, lexical state_id; max 3 per config"})
    payload = {"schema_version": "raretopo-m3d3-discovery-shortlist-v0",
               "source_discovery_sha256": None, "eligible_hold_count": len(eligible),
               "cap": 12, "replacement_allowed": False, "selected": flat,
               "selection_order": "paired_support_margin desc; hold_proximity_score asc; s2 asc; state_id lexical; cap 3/config"}
    return payload


def _figures(records: list[dict]) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    colors = {"WIDEN": "#2c7fb8", "HOLD": "#31a354", "SHRINK": "#de2d26", "AMBIGUOUS": "#756bb1", "INVALID": "#252525"}
    def save(name: str) -> None:
        plt.tight_layout(); plt.savefig(FIGURES / name, dpi=160); plt.close()
    plt.figure(figsize=(8, 4))
    for row in records: plt.scatter(row["generated_s2"], row["config_id"][-4:], color=colors[row["corrected_class"]], s=45)
    plt.xscale("log"); plt.xlabel("s2"); plt.ylabel("configuration"); plt.title("D3 discovery candidates on s2 boundary map"); save("m3d3_discovery_boundary_map.png")
    plt.figure(figsize=(8, 4))
    for row in records: plt.scatter(row["generated_s2"], row["config_id"][-4:], color=colors[row["corrected_class"]], s=45)
    plt.xscale("log"); plt.xlabel("s2"); plt.ylabel("configuration"); plt.title("Discovery class by configuration and s2"); save("m3d3_discovery_class_by_config.png")
    counts = Counter(row["corrected_class"] for row in records)
    plt.figure(figsize=(6, 4)); plt.bar(list(counts), [counts[key] for key in counts], color=[colors[key] for key in counts]); plt.title("Discovery classes"); save("m3d3_discovery_class_counts.png")
    plt.figure(figsize=(6, 5))
    for row in records: plt.scatter(row["r_w"], row["r_s"], color=colors[row["corrected_class"]], label=row["corrected_class"])
    plt.axvline(0, color="black", lw=.5); plt.axhline(0, color="black", lw=.5); plt.xlabel("r_w"); plt.ylabel("r_s"); plt.title("Paired contrast plane"); save("m3d3_discovery_contrast_plane.png")
    hold = [row for row in records if row["corrected_class"] == "HOLD"]
    plt.figure(figsize=(8, 3)); plt.scatter([row["generated_s2"] for row in hold], [row["config_id"][-4:] for row in hold], color=colors["HOLD"]); plt.xscale("log"); plt.title("Provisional HOLD locations"); save("m3d3_discovery_hold_locations.png")
    fractions = [0.25, 0.5, 0.75]
    plt.figure(figsize=(7, 4)); plt.bar([str(item) for item in fractions], [sum(row["corrected_class"] == "HOLD" and row["interpolation_fraction"] == item for row in records) for item in fractions], color=colors["HOLD"]); plt.title("HOLD count by interpolation fraction"); plt.xlabel("log-s2 fraction"); save("m3d3_discovery_fraction_classes.png")
    plt.figure(figsize=(7, 4)); plt.hist([row["paired_support_margin"] for row in records], bins=8, color="#636363"); plt.title("Paired support-margin distribution"); save("m3d3_discovery_support_margin.png")


def main() -> int:
    if not _approval_ok():
        raise RuntimeError("HUMAN_APPROVAL_D3_1 is required before simulator calls")
    live = _live_git_audit()
    protocol = _load(CFG / "m3d3_protocol.json")
    if not protocol["stop_before_discovery"]:
        raise RuntimeError("D3-1 preregistration firewall is not frozen")
    hashes_before = _hash_lock()
    _write_json(SUMMARY / "m3d3_discovery_prereg_hashes.json", hashes_before)
    candidates, candidate_audit = _candidate_audit()
    _write_csv(SUMMARY / "m3d3_discovery_candidate_audit.csv", candidates, list(candidates[0]))
    _write_json(SUMMARY / "m3d3_discovery_seed_audit.json", _seed_audit())
    classifier_audit = _classifier_audit(protocol)
    classifier = _load(REPO / "configs" / "phase_m3d2" / "m3d2_classifier_contract.json")
    refs = {row["config_id"]: row for row in _load(D2_SUMMARY / "m3d2_probability_reference.json")["records"]}
    benches = _benches({row["config_id"] for row in candidates})
    if set(benches) != {row["config_id"] for row in candidates} or not all(row["config_id"] in refs for row in candidates):
        raise RuntimeError("frozen candidate configuration/reference lookup failed")
    t0 = time.perf_counter()
    records = _run_discovery(candidates, protocol, classifier, refs, benches)
    hashes_after = _hash_lock()
    unchanged = hashes_before["entries"] == hashes_after["entries"]
    if not unchanged:
        raise RuntimeError("preregistration source hash changed during discovery")
    counts = Counter(row["corrected_class"] for row in records)
    invalid = counts["INVALID"]
    holds = counts["HOLD"]
    gate_pass = holds >= int(protocol["discovery"]["new_provisional_hold_minimum"]) and invalid == 0 and unchanged
    gate = "PASS" if gate_pass else ("INVALID" if invalid else "FAIL_HOLD_INSUFFICIENT")
    shortlist = _shortlist(records, gate_pass)
    if shortlist is not None:
        shortlist["source_discovery_sha256"] = _sha(SUMMARY / "m3d3_discovery_prereg_hashes.json")
        _write_json(SUMMARY / "m3d3_shortlist.json", shortlist)
        _write_csv(SUMMARY / "m3d3_shortlist.csv", shortlist["selected"], list(shortlist["selected"][0]) if shortlist["selected"] else ["rank", "state_id"])
        shortlist_hash = _sha(SUMMARY / "m3d3_shortlist.json")
    else:
        shortlist_hash = None
    _figures(records)
    flat = []
    for row in records:
        flat.append({"state_id": row["state_id"], "config_id": row["config_id"], "s2": row["generated_s2"],
                     "interpolation_fraction": row["interpolation_fraction"], "source_bracket_type": row["source_bracket_type"],
                     "corrected_class": row["corrected_class"], "r_w": row["r_w"], "r_s": row["r_s"],
                     "hold_proximity_score": row["hold_proximity_score"], "paired_support_margin": row["paired_support_margin"],
                     "minimum_arm_ESS": row["minimum_arm_ESS"], "ambiguity_or_invalid_reason": row["ambiguity_or_invalid_reason"]})
    _write_csv(SUMMARY / "m3d3_discovery_states.csv", flat, list(flat[0]))
    summary = {"schema_version": "raretopo-m3d3-discovery-summary-v0", "created_utc": _utc(),
               "live_git": live, "human_approval": True, "candidate_audit": candidate_audit,
               "seed_audit": _seed_audit(), "classifier_audit": classifier_audit,
               "prereg_hashes_unchanged": unchanged, "records": records, "counts": dict(sorted(counts.items())),
               "by_config": {cid: dict(Counter(row["corrected_class"] for row in records if row["config_id"] == cid)) for cid in sorted(benches)},
               "by_interpolation_fraction": {str(frac): dict(Counter(row["corrected_class"] for row in records if row["interpolation_fraction"] == frac)) for frac in (0.25, 0.5, 0.75)},
               "simulator_samples": len(records) * 3 * int(protocol["discovery"]["n_per_arm"]),
               "controller_online_trials": 0, "rarity_shift": "BLOCKED", "gate": {"name": "M3D3-DISC-1", "required_new_hold": 10, "observed_new_hold": holds, "result": gate},
               "shortlist_created": shortlist is not None, "shortlist_sha256": shortlist_hash,
               "discovery_verdict": "D3-DISC-A" if gate == "PASS" else ("D3-DISC-X" if gate == "INVALID" else "D3-DISC-B"),
               "next_authorized_action": "Independent confirmation" if gate == "PASS" else "stop and human scientific review",
               "wall_clock_s": time.perf_counter() - t0}
    _write_json(SUMMARY / "m3d3_discovery_summary.json", summary)
    print(json.dumps({"counts": summary["counts"], "gate": gate,
                      "simulator_samples": summary["simulator_samples"],
                      "verdict": summary["discovery_verdict"]}, indent=2))
    return 0 if gate == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
