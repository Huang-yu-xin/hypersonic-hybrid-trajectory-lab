"""Stage-gated M3-DS dual-axis benchmark-construction pipeline.

Stages are separate so the source manifest, directional selection, safety
assembly and final freeze are individually auditable commits. Every stage is
zero-simulator: it only reads frozen corrected artifacts from ER-1, M3-D-v1,
M3-D2, M3-D3 and M3-RF. No controller module is imported or evaluated here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m3ds.selection import (
    DIRECTIONAL_CLASSES,
    build_directional_axis,
    safety_primary,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3ds" / "summary"
D2_SUMMARY = REPO / "results" / "phase_m3d2" / "summary"
D3_SUMMARY = REPO / "results" / "phase_m3d3" / "summary"
RF_SUMMARY = REPO / "results" / "phase_m3rf" / "summary"

EVENT_DEFINITION_ID = "FULL_TOPOLOGY_EVENT_S1_S4"
EVENT_SEMANTICS_SCHEMA_VERSION = 2

SOURCES = [
    ("docs/evidence_repair/ER1_Event_Semantics_Contract.md",
     "ER-1 semantic contract"),
    ("docs/evidence_repair/ER1_Supersession_Ledger.md",
     "ER-1 corrected lineage status"),
    ("results/evidence_repair/reanalysis/M3-v0/summary/"
     "m3v0_corrected_gate.json",
     "M3-v2 corrected results"),
    ("results/phase_m3d/reference/m3d_labels_corrected_v2.json",
     "M3-D-v1 corrected reference records"),
    ("results/phase_m3d2/summary/m3d2_confirmation_summary.json",
     "M3-D2 confirmation states"),
    ("results/phase_m3d2/summary/m3d2_class_transition.json",
     "M3-D2 class-transition audit"),
    ("results/phase_m3d2/summary/m3d2_final_verdict.json",
     "M3-D2 final verdict (D2-B)"),
    ("results/phase_m3d3/summary/m3d3_discovery_states.csv",
     "M3-D3 discovery states"),
    ("results/phase_m3d3/summary/m3d3_discovery_summary.json",
     "M3-D3 discovery verdict (D3-DISC-B)"),
    ("results/phase_m3rf/summary/m3rf_route_decision.json",
     "M3-RF action-space decision (RF-B)"),
    ("configs/phase_m3d2/m3d2_classifier_contract.json",
     "corrected classifier contract (frozen, retuning not allowed)"),
    ("configs/phase_m3d/m3d_reference_characterization.json",
     "M3-D-v1 classifier characterization source"),
    ("src/hyptraj/m3d/reference_direction.py",
     "corrected classifier source"),
    ("docs/phase_m3ds/M3_DS_Directional_Benchmark_Task.md",
     "M3-DS preregistration taskbook"),
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def _git_tags() -> set[str]:
    out = subprocess.run(["git", "tag", "--list"], cwd=REPO, check=True,
                         capture_output=True, text=True).stdout
    return set(out.splitlines())


def _git_reachable(sha: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"],
                          cwd=REPO).returncode == 0


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


def _d2_records() -> list[dict]:
    payload = json.loads((D2_SUMMARY / "m3d2_confirmation_summary.json")
                         .read_text(encoding="utf-8"))
    return payload["records"]


def parent_audit() -> dict:
    """DS-0 parent provenance audit; STOP (raise) if lineage mismatches."""
    tags = _git_tags()
    checks = {
        "er1_tag_reachable": "RareTopo-ER1-v0" in tags,
        "m3_v2_tag_reachable": "RareTopo-M3-v2" in tags,
        "m3d_v1_tag_reachable": "RareTopo-M3-D-v1" in tags,
        "d2_d2b_close_reachable": _git_reachable("f031512"),
        "d3_discovery_reachable": _git_reachable("a568418"),
    }
    rf = json.loads((RF_SUMMARY / "m3rf_route_decision.json")
                    .read_text(encoding="utf-8"))
    d2 = json.loads((D2_SUMMARY / "m3d2_final_verdict.json")
                    .read_text(encoding="utf-8"))
    checks["m3rf_route_is_rf_b"] = rf["primary_route"] == "M3-RF-B"
    checks["d2_verdict_is_d2b"] = d2["final_verdict"] == "D2-B"
    checks["d3_discovery_verdict_is_disc_b"] = json.loads(
        (D3_SUMMARY / "m3d3_discovery_summary.json")
        .read_text(encoding="utf-8"))["discovery_verdict"] == "D3-DISC-B"
    if not all(checks.values()):
        raise RuntimeError(f"M3-DS parent audit STOP: {checks}")
    return checks


def manifest() -> int:
    checks = parent_audit()
    commit = _git_head()
    entries = []
    for path_text, role in SOURCES:
        path = REPO / path_text
        if not path.is_file():
            raise RuntimeError(f"manifest source missing: {path_text}")
        entries.append({"path": path_text, "sha256": _sha(path),
                        "commit": commit, "role": role, "read_only": True})
    _write_json(SUMMARY / "m3ds_source_manifest.json", {
        "schema_version": "raretopo-m3ds-source-manifest-v0",
        "created_utc": _utc(), "git_commit": commit,
        "parent_audit": checks,
        "zero_simulator": {"extra_simulator_calls": 0,
                           "controller_online_trials": 0},
        "entries": entries})
    print(json.dumps({"entries": len(entries), "parent_audit": checks},
                     indent=2))
    return 0


def _flat_directional(row: dict, selected_flag: bool) -> dict:
    return {
        "state_id": row["state_id"], "class": row["corrected_class"],
        "config_id": row["config_id"], "s2": float(row["s2"]),
        "candidate_stratum": row["candidate_stratum"],
        "confirmation_support": float(row["class_certainty_score"]),
        "r_w": row["r_w"], "r_s": row["r_s"],
        "selection_rank": row["selection_rank"],
        "selection_reason": row["selection_reason"],
        "selected": selected_flag,
    }


def directional() -> int:
    records = _d2_records()
    axis = build_directional_axis(records, target=8, min_distinct_configs=4)
    candidates, selected_rows = [], []
    for name in DIRECTIONAL_CLASSES:
        result = axis["classes"][name]
        for row in result["selected"]:
            flat = _flat_directional(row, True)
            candidates.append(flat)
            selected_rows.append(flat)
        for row in result["reserve"]:
            candidates.append(_flat_directional(row, False))
    fields = ["state_id", "class", "config_id", "s2", "candidate_stratum",
              "confirmation_support", "r_w", "r_s", "selection_rank",
              "selection_reason", "selected"]
    _write_csv(SUMMARY / "m3ds_directional_candidates.csv", candidates,
               fields)
    _write_csv(SUMMARY / "m3ds_directional_selected.csv", selected_rows,
               fields)
    audit = {
        "schema_version": "raretopo-m3ds-directional-selection-audit-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "source_confirmation_sha256": _sha(
            D2_SUMMARY / "m3d2_confirmation_summary.json"),
        "selection_rule": [
            "step 1: maximize distinct config coverage",
            "step 2: within config, prefer greater s2 spacing from already "
            "selected states",
            "step 3: prefer stronger independent-confirmation support margin",
            "step 4: prefer larger absolute directional effect only after "
            "diversity/support",
            "step 5: lexical state_id tie-break",
        ],
        "forbidden_in_selection": ["future controller score",
                                   "future regret", "future VRF"],
        "classes": {
            name: {
                "available": axis["classes"][name]["available"],
                "selected_count": axis["classes"][name]["selected_count"],
                "distinct_configs": axis["classes"][name]["distinct_configs"],
                "distinct_strata": axis["classes"][name]["distinct_strata"],
                "diversity_gate": axis["classes"][name]["diversity_gate"],
                "selected_state_ids": [row["state_id"] for row in
                                       axis["classes"][name]["selected"]],
                "reserve_state_ids": sorted(
                    row["state_id"]
                    for row in axis["classes"][name]["reserve"]),
            } for name in DIRECTIONAL_CLASSES},
        "invalid_directional": axis["invalid_directional"],
        "reserve_policy": ("Directional Reserve / Stress Set; future "
                           "robustness only; forbidden for controller tuning"),
        "gates": axis["gates"], "M3DS_DIR_1": axis["M3DS_DIR_1"],
    }
    _write_json(SUMMARY / "m3ds_directional_selection_audit.json", audit)
    print(json.dumps({"M3DS-DIR-1": axis["M3DS_DIR_1"],
                      "gates": axis["gates"]}, indent=2))
    return 0 if axis["M3DS_DIR_1"] == "PASS" else 3


def safety() -> int:
    records = _d2_records()
    rows = safety_primary(records)
    fields = ["state_id", "config_id", "s2", "candidate_stratum",
              "reference_status", "confirmation_support", "r_w", "r_s",
              "probability_semantics_valid", "reference_action_class_valid",
              "ambiguity_or_invalid_reason", "safe_protocol_behavior",
              "independently_confirmed"]
    _write_csv(SUMMARY / "m3ds_safety_primary.csv", rows, fields)
    print(json.dumps({"safety_primary": len(rows),
                      "statuses": dict(Counter(row["reference_status"]
                                               for row in rows))}, indent=2))
    return 0


def _classifier_contract_pass() -> bool:
    contract = json.loads(
        (REPO / "configs" / "phase_m3d2" / "m3d2_classifier_contract.json")
        .read_text(encoding="utf-8"))
    protocol = json.loads(
        (REPO / "configs" / "phase_m3d2" / "m3d2_protocol.json")
        .read_text(encoding="utf-8"))
    locked = protocol["preregistration_hash_locks"][
        "m3d2_classifier_contract.json"]
    return (contract["retuning_allowed"] is False
            and _sha(REPO / "configs" / "phase_m3d2"
                     / "m3d2_classifier_contract.json") == locked)


def freeze(full_regression: str = "PENDING",
           regression_log: str | None = None) -> int:
    manifest_payload = json.loads(
        (SUMMARY / "m3ds_source_manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((SUMMARY / "m3ds_directional_selection_audit.json")
                       .read_text(encoding="utf-8"))
    with (SUMMARY / "m3ds_safety_primary.csv").open(encoding="utf-8") as fh:
        safety_rows = list(csv.DictReader(fh))
    hold = [row for row in safety_rows if row["reference_status"] == "HOLD"]
    amb = [row for row in safety_rows
           if row["reference_status"] == "AMBIGUOUS"]

    benchmark = {
        "schema_version": "raretopo-m3ds-benchmark-v0",
        "name": "Corrected Directional-Sign Benchmark with Abstention "
                "Safety Axis",
        "short_name": "M3-DS",
        "created_utc": _utc(), "git_commit": _git_head(),
        "event_definition_id": EVENT_DEFINITION_ID,
        "event_semantics_schema_version": EVENT_SEMANTICS_SCHEMA_VERSION,
        "directional_primary": {
            "widen": audit["classes"]["WIDEN"]["selected_state_ids"],
            "shrink": audit["classes"]["SHRINK"]["selected_state_ids"],
        },
        "directional_reserve": {
            "widen": audit["classes"]["WIDEN"]["reserve_state_ids"],
            "shrink": audit["classes"]["SHRINK"]["reserve_state_ids"],
            "policy": "future robustness only; forbidden for tuning",
        },
        "safety_primary": {
            "confirmed_hold": sorted(row["state_id"] for row in hold),
            "confirmed_ambiguous": sorted(row["state_id"] for row in amb),
        },
        "safety_expansion": [],
        "abstention_semantics": {
            "ground_truth_class": False,
            "protocol_behavior": True,
            "fallback": "BASE",
        },
        "future_metrics_definitions_only": {
            "A_safe": "#ABSTAIN on safety states / N_safety",
            "U_safe": "#(W/S deployed on safety states) / N_safety",
            "R_wrong": "(#W->SHRINK + #S->WIDEN) / N_directional",
            "C_dir": "#non-abstained directional / N_directional",
            "Acc_selective": "P(correct direction | not abstained)",
        },
        "controller_online_trials": 0,
        "rarity_shift_authorized": False,
    }
    _write_json(SUMMARY / "m3ds_benchmark.json", benchmark)

    candidates = list(csv.DictReader(
        (SUMMARY / "m3ds_directional_candidates.csv").open(encoding="utf-8")))
    analyses = {
        "schema_version": "raretopo-m3ds-zero-sim-analyses-v0",
        "created_utc": _utc(),
        "directional_class_balance": {
            "confirmed": {name: audit["classes"][name]["available"]
                          for name in DIRECTIONAL_CLASSES},
            "selected": {name: audit["classes"][name]["selected_count"]
                         for name in DIRECTIONAL_CLASSES}},
        "config_diversity": {
            name: {"distinct_configs": audit["classes"][name]
                   ["distinct_configs"],
                   "distinct_strata": audit["classes"][name]
                   ["distinct_strata"]}
            for name in DIRECTIONAL_CLASSES},
        "s2_coverage": {
            name: {"selected_s2": sorted(float(row["s2"]) for row in
                                         candidates
                                         if row["class"] == name
                                         and row["selected"] == "True"),
                   "candidate_s2": sorted(float(row["s2"]) for row in
                                          candidates
                                          if row["class"] == name)}
            for name in DIRECTIONAL_CLASSES},
        "support_margin_distribution": {
            name: sorted(float(row["confirmation_support"]) for row in
                         candidates if row["class"] == name)
            for name in DIRECTIONAL_CLASSES},
        "safety_state_provenance": {
            "source": "M3-D2 independent confirmation (zero new simulation)",
            "states": [{"state_id": row["state_id"],
                        "reference_status": row["reference_status"],
                        "reason": row["ambiguity_or_invalid_reason"]}
                       for row in safety_rows]},
        "hold_vs_ambiguous_composition": dict(
            Counter(row["reference_status"] for row in safety_rows)),
        "extra_simulator_calls": 0,
    }
    _write_json(SUMMARY / "m3ds_zero_sim_analyses.json", analyses)

    source_lock = all((REPO / entry["path"]).is_file()
                      and _sha(REPO / entry["path"]) == entry["sha256"]
                      for entry in manifest_payload["entries"])
    records = _d2_records()
    record_by_id = {row["state_id"]: row for row in records}
    event_ok = all(
        record_by_id[state_id]["event_definition_id"] == EVENT_DEFINITION_ID
        and int(record_by_id[state_id]
                ["event_semantics_schema_version"]) ==
        EVENT_SEMANTICS_SCHEMA_VERSION
        for state_id in (benchmark["directional_primary"]["widen"]
                         + benchmark["directional_primary"]["shrink"]
                         + benchmark["safety_primary"]["confirmed_hold"]
                         + benchmark["safety_primary"]["confirmed_ambiguous"]))
    gates = {
        "directional_primary_widen_8":
            len(benchmark["directional_primary"]["widen"]) == 8,
        "directional_primary_shrink_8":
            len(benchmark["directional_primary"]["shrink"]) == 8,
        "directional_diversity_pass": audit["gates"]["diversity_pass"],
        "safety_primary_at_least_5": len(safety_rows) >= 5,
        "safety_all_independently_confirmed": all(
            row["independently_confirmed"] == "True" for row in safety_rows),
        "source_lock_pass": bool(source_lock),
        "event_semantics_pass": bool(event_ok),
        "classifier_contract_pass": _classifier_contract_pass(),
        "no_controller_trials": benchmark["controller_online_trials"] == 0,
        "full_regression_pass": full_regression == "PASS",
    }
    if not gates["directional_primary_widen_8"] or \
            not gates["directional_primary_shrink_8"] or \
            not gates["directional_diversity_pass"]:
        verdict = "M3DS-B"
    elif not (gates["safety_primary_at_least_5"]
              and gates["safety_all_independently_confirmed"]):
        verdict = "M3DS-C"
    elif all(gates.values()):
        verdict = "M3DS-A"
    else:
        verdict = "M3DS-C"
    payload = {
        "schema_version": "raretopo-m3ds-final-verdict-v0",
        "created_utc": _utc(), "git_commit": _git_head(),
        "gates": gates, "M3DS_1": "PASS" if all(gates.values()) else "FAIL",
        "final_verdict": verdict,
        "full_regression": {"status": full_regression,
                            "log": regression_log},
        "controller_online_trials": 0,
        "extra_simulator_calls": 0,
        "rarity_shift": "BLOCKED",
        "m3_q": "BLOCKED",
        "next_authorized_action": (
            "M3-G2 preregistration (Corrected Directional Controller with "
            "Abstention)" if verdict == "M3DS-A" else
            "DS-3 safety confirmation review" if verdict == "M3DS-C"
            else "stop controller line"),
        "tag_policy": ("create RareTopo-M3-DS-v0 only on M3DS-A"),
    }
    _write_json(SUMMARY / "m3ds_final_verdict.json", payload)
    print(json.dumps({"M3DS-1": payload["M3DS_1"],
                      "verdict": verdict, "gates": gates}, indent=2))
    return 0 if verdict == "M3DS-A" else 3


def seal() -> int:
    """Seal the freeze after a real full-regression run passes."""
    log_path = SUMMARY / "m3ds_full_regression.log"
    text = log_path.read_text(encoding="utf-8")
    if "failed" in text or "passed" not in text:
        raise RuntimeError("regression log does not show a clean pass")
    return freeze(full_regression="PASS",
                  regression_log="results/phase_m3ds/summary/"
                                 "m3ds_full_regression.log")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["manifest", "directional",
                                          "safety", "freeze", "seal"])
    args = parser.parse_args()
    if args.stage == "manifest":
        return manifest()
    if args.stage == "directional":
        return directional()
    if args.stage == "safety":
        return safety()
    if args.stage == "freeze":
        return freeze()
    return seal()


if __name__ == "__main__":
    raise SystemExit(main())
