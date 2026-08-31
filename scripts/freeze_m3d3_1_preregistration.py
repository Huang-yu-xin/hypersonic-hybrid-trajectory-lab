"""Freeze the M3-D3-1 boundary-focused candidate family; no simulator calls."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from hyptraj.m3d3.prereg import build_boundary_candidates


REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results/phase_m3d3/summary"
CONFIG = REPO / "configs/phase_m3d3"
DOCS = REPO / "docs/phase_m3d3"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_commit(path: Path) -> str:
    return subprocess.run(["git", "log", "-1", "--format=%H", "--", str(path.relative_to(REPO))], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def freeze_preregistration() -> dict:
    d2_pool = _load_json(REPO / "results/phase_m3d2/summary/m3d2_candidate_pool.json")
    d2_discovery = _load_json(REPO / "results/phase_m3d2/summary/m3d2_discovery_summary.json")
    d2_confirmation = _load_json(REPO / "results/phase_m3d2/summary/m3d2_confirmation_summary.json")
    brackets_path = SUMMARY / "d3_0_s2_boundary_brackets.csv"
    with brackets_path.open(encoding="utf-8") as stream:
        brackets = list(csv.DictReader(stream))
    required_types = {"W_H_S_PATH", "W_AMBIGUOUS_S_PATH"}
    if not brackets or any(row["boundary_type"] not in required_types for row in brackets):
        raise ValueError("D3-0 boundary brackets are missing or invalid")
    existing: dict[str, list[float]] = {}
    for state in d2_pool["states"]:
        existing.setdefault(state["config_id"], []).append(float(state["s2"]))
    candidates, generation = build_boundary_candidates(brackets, existing)
    d3_0 = {
        "schema_version": "raretopo-m3d3-d3-0-summary-v0",
        "source_commit": _source_commit(SUMMARY / "d3_0_d2_state_table.csv"),
        "extra_simulator_calls": 0,
        "state_rows": 72,
        "confirmed_hold": 3,
        "detected_brackets": len(brackets),
        "primary_axis": "s2_selected_component_covariance_scale",
        "route": "D3-0A",
    }
    _write_json(SUMMARY / "m3d3_d3_0_summary.json", d3_0)
    if d3_0["route"] != "D3-0A" or d3_0["primary_axis"] != "s2_selected_component_covariance_scale":
        raise ValueError("D3-0 routing gate failed")
    source_paths = [
        "results/phase_m3d2/summary/m3d2_candidate_pool.json",
        "results/phase_m3d2/summary/m3d2_discovery_summary.json",
        "results/phase_m3d2/summary/m3d2_confirmation_summary.json",
        "results/phase_m3d2/summary/m3d2_class_transition.json",
        "results/phase_m3d3/summary/d3_0_d2_state_table.csv",
        "results/phase_m3d3/summary/d3_0_s2_boundary_brackets.csv",
        "results/phase_m3d3/summary/d3_0_confirmed_hold_signature.csv",
        "docs/phase_m3d3/M3_D3_Lost_HOLD_Audit.md",
        "results/phase_m3d3/summary/d3_0_candidate_axis_inventory.csv",
        "docs/phase_m3d3/M3_D3_Classifier_Contract.md",
    ]
    roles = ["D2 72-state pool", "D2 discovery", "D2 confirmation", "D2 class transition", "D3-0 state table", "D3-0 brackets", "D3-0 HOLD signatures", "D3-0 lost HOLD audit", "D3-0 axis inventory", "frozen D2 classifier reuse"]
    manifest = {"schema_version": "raretopo-m3d3-1-source-manifest-v0", "read_only_sources": True, "items": []}
    for rel, role in zip(source_paths, roles, strict=True):
        path = REPO / rel
        manifest["items"].append({"path": rel.replace("\\", "/"), "sha256": _sha(path), "source_commit": _source_commit(path), "read_only": True, "role": role})
    _write_json(SUMMARY / "m3d3_1_source_manifest.json", manifest)
    candidate_payload = {
        "schema_version": "raretopo-m3d3-boundary-candidate-family-v0",
        "source_d3_0_route": "D3-0A",
        "primary_axis": "s2_selected_component_covariance_scale",
        "candidate_generation": generation,
        "candidates": candidates,
        "d2_confirmed_states_included_in_final_eligible_universe": True,
        "d2_confirmed_counts": {"WIDEN": 12, "HOLD": 3, "SHRINK": 10},
        "new_confirmed_hold_minimum_for_final_count": 5,
        "extra_simulator_calls": 0,
    }
    _write_json(SUMMARY / "m3d3_candidate_states.json", candidate_payload)
    _write_csv(SUMMARY / "m3d3_candidate_states.csv", candidates)
    protocol = {
        "schema_version": "raretopo-m3d3-protocol-v0",
        "stage": "M3-D3-1 boundary-focused s2 preregistration",
        "parent": {"ER1": "RareTopo-ER1-v0", "M3D2_tip": "f031512", "D3_0_route": "D3-0A"},
        "event_semantics_schema_version": 2,
        "event_definition_id": "FULL_TOPOLOGY_EVENT_S1_S4",
        "event_predicate": "topology != S0",
        "classifier_reuse": {"widen_reduction_threshold": -0.01, "hold_band": 0.03, "paired_support_se_multiplier": 2.0, "direction_margin": 0.05, "min_arm_ess": 20.0},
        "reference": {"n_per_config": 1000000, "n_batches": 20, "shared_across_state_arms": True, "namespace": "D3-REFERENCE", "seed_formula": "SeedSequence([3303000, candidate_index])"},
        "discovery": {"n_per_arm": 100000, "n_batches": 20, "namespace": "D3-DISCOVERY", "seed_formula": "SeedSequence([3303001, candidate_index])", "gate": "M3D3-DISC-1", "new_provisional_hold_minimum": 10, "d2_confirmed_widen": 12, "d2_confirmed_shrink": 10},
        "confirmation": {"n_per_arm": 500000, "n_batches": 20, "namespace": "D3-CONFIRMATION", "seed_formula": "SeedSequence([3303002, candidate_index])", "replacement_allowed": False, "shortlist": {"HOLD": 12, "WIDEN": 0, "SHRINK": 0}},
        "firewall": {"extra_simulator_calls_so_far": 0, "controller_online_trials": 0, "rarity_shift": "BLOCKED", "posthoc_candidates_allowed": False},
        "stop_before_discovery": True,
    }
    _write_json(CONFIG / "m3d3_protocol.json", protocol)
    _write_json(CONFIG / "m3d3_candidate_family.json", candidate_payload)
    _write_json(CONFIG / "m3d3_seeds.json", {"schema_version": "raretopo-m3d3-seeds-v0", "reference": protocol["reference"], "discovery": protocol["discovery"], "confirmation": protocol["confirmation"], "disjoint_from": ["D2-PREF", "D2-DISCOVERY", "D2-CONFIRMATION", "all controller seeds"]})
    diversity = {"schema_version": "raretopo-m3d3-diversity-gate-v0", "confirmed_hold_minimum": 8, "distinct_hold_config_ids_minimum": 4, "max_selected_hold_per_config": 3, "original_strata_gate": "NOT_APPLIED: D3 interpolation points have no stable original-stratum assignment", "applies_at": "final exact 8/8/8 selection"}
    _write_json(CONFIG / "m3d3_diversity_gate.json", diversity)
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "M3_D3_D3_1_Pregistration.md").write_text(
        "# M3-D3-1 Boundary-Focused `s2` Preregistration\n\n"
        f"D3-0A source lock is complete. All {generation['bracket_count']} valid D3-0 brackets enter the log-`s2` 25/50/75% rule. This emits {generation['raw_generated_candidates']} raw points and {generation['deduplicated_candidates']} new candidates after same-config D2-point deduplication, across {generation['distinct_configs']} configs.\n\n"
        "D2 independently confirmed W/H/S states remain eligible in the final universe (12/3/10). D3 must independently confirm new states; only D3 valid HOLD candidates may enter its HOLD shortlist, capped at 12 with no replacement. Discovery is 100,000/arm in 20 CRN batches; confirmation is 500,000/arm in 20 CRN batches. The classifier and full-event probability contract are inherited exactly.\n\n"
        "M3D3-DISC-1 requires at least 10 new provisional HOLD states while the source lock retains D2's already confirmed W=12 and S=10. M3D3-1 still requires total confirmed W/H/S >=8, no invalid states, valid full-event semantics, source lock, tests, and a HOLD diversity gate of >=4 configs with no selected config contributing more than three HOLD states.\n\n"
        "This file freezes a fair boundary-sampling test only. `stop_before_discovery=true`; controller trials and rarity-shift remain blocked.\n",
        encoding="utf-8")
    return {"extra_simulator_calls": 0, **generation, "route": "D3-1 PREREGISTRATION COMPLETE", "stop_before_discovery": True}


if __name__ == "__main__":
    print(json.dumps(freeze_preregistration(), indent=2))
