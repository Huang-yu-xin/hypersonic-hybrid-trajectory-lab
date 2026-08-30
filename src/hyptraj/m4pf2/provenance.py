"""PF2-0 frozen-source, sample identifiability and anchor audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_SPECS = (
    ("results/phase_m4pf1/m4pf1_confirmation_raw.json", "M4-PF1",
     "aggregate gradient, update and confirmatory records"),
    ("results/phase_m4pf1/summary/m4pf1_family_summary.json", "M4-PF1",
     "PF1 verdict and lock hashes"),
    ("results/phase_m4pf1/summary/m4pf1_state_table.csv", "M4-PF1",
     "24-state PF1 summaries"),
    ("configs/phase_m4pf1/m4pf1_protocol.json", "M4-PF1",
     "PF1 proposal and gradient-construction semantics"),
    ("configs/phase_m4pf1/m4pf1_states.json", "M4-PF1",
     "PF1 state lock"),
    ("configs/phase_m4pf1/m4pf1_seeds.json", "M4-PF1",
     "PF1 seed lock"),
    ("scripts/run_m4pf1_experiment.py", "M4-PF1",
     "gradient-source and S0 anchor implementation"),
    ("docs/phase_m4pf/M4_PF1_Structured_Proposal_Audit.md", "M4-PF1",
     "PF1 final audit and claim boundary"),
    ("results/phase_m3ca/summary/m3ca_cost_attribution.json", "M3-CA",
     "absolute budget accounting anchor"),
    ("src/hyptraj/m3ca/metrics.py", "M3-CA",
     "budget VRF definitions"),
    ("configs/phase_m3bv2/m3bv2_value_benchmark.json", "M3-BV2",
     "frozen Value-Axis state definitions"),
)

TAG_BY_STAGE = {
    "M4-PF1": "RareTopo-M4-PF1-v0",
    "M3-CA": "RareTopo-M3-CA-v0",
    "M3-BV2": "RareTopo-M3-BV2-v0",
}

SAMPLE_KEYS = {
    "sample_or_whitened_coordinates": {
        "samples", "sample_coordinates", "x", "z", "whitened",
        "whitened_coordinates"},
    "second_moment_mass": {
        "variance_mass", "variance_mass_weights", "a_i", "tilted_weights"},
    "component_responsibility": {
        "responsibility", "responsibilities", "component_responsibility"},
    "sample_proposal_identity": {
        "sample_proposal_id", "proposal_identity_per_sample"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(repo: Path) -> dict:
    sources = []
    for rel, stage, role in SOURCE_SPECS:
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(f"required PF2-0 source missing: {rel}")
        sources.append({
            "path": rel,
            "sha256": sha256_file(path),
            "source_stage": stage,
            "source_tag": TAG_BY_STAGE[stage],
            "role": role,
            "proposal_anchor": (
                "PF1 base state proposal" if rel.endswith(
                    "m4pf1_confirmation_raw.json") else "not_applicable"),
            "read_only": True,
        })
    return {
        "schema_version": "raretopo-m4pf2-0-source-manifest-v0",
        "stage": "M4-PF2-0",
        "source_count": len(sources),
        "sources": sources,
        "sources_unchanged": True,
    }


def verify_manifest(repo: Path, manifest: dict) -> list[str]:
    mismatches = []
    for source in manifest["sources"]:
        path = repo / source["path"]
        if not path.is_file():
            mismatches.append(f"missing:{source['path']}")
        elif sha256_file(path) != source["sha256"]:
            mismatches.append(f"hash:{source['path']}")
    return mismatches


def _walk(value: Any, keys: set[str], numeric_arrays: list[dict],
          path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key)
            keys.add(name)
            child_path = f"{path}.{name}"
            if isinstance(child, list) and len(child) >= 100:
                vector = all(isinstance(x, (int, float)) for x in child)
                matrix = all(isinstance(row, list) and
                             all(isinstance(x, (int, float)) for x in row)
                             for row in child)
                if vector or matrix:
                    numeric_arrays.append({"key": name, "path": child_path,
                                           "length": len(child)})
            _walk(child, keys, numeric_arrays, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, keys, numeric_arrays, f"{path}[{index}]")


def identifiability_audit(raw: dict) -> dict:
    keys: set[str] = set()
    arrays: list[dict] = []
    _walk(raw, keys, arrays)
    groups = {}
    for label, accepted in SAMPLE_KEYS.items():
        matches = [item for item in arrays if item["key"] in accepted]
        groups[label] = {
            "identifiable": bool(matches),
            "numeric_sample_arrays": matches,
            "matching_key_names_any_type": sorted(keys & accepted),
        }
    identifiable = all(group["identifiable"] for group in groups.values())
    return {
        "mean_gradient_from_frozen_samples": identifiable,
        "required_groups": groups,
        "missing_groups": [name for name, group in groups.items()
                           if not group["identifiable"]],
        "aggregate_gradient_matrix_present": "gradient_matrix" in keys,
        "aggregate_matrix_does_not_identify_first_moment": True,
        "verdict_text": ("IDENTIFIABLE" if identifiable else
                         "NOT IDENTIFIABLE FROM EXISTING ARTIFACTS"),
        "reason": (None if identifiable else
                   "PF1 persisted aggregate matrix gradients and diagnostics, "
                   "but not aligned numeric sample coordinates, variance-mass "
                   "weights and component responsibilities needed for "
                   "E_nuV[r_k z_k]."),
    }


def anchor_compatibility_audit(raw: dict) -> dict:
    rows = []
    for state in raw["states"]:
        selected = state["selected_arm"]["S0"]
        source = "base"
        rows.append({
            "state_id": state["state_id"],
            "gradient_source_proposal": source,
            "pf2_anchor_proposal": selected,
            "exact_match": source == selected,
            "exact_reweighting_available": False,
            "reason": ("exact proposal identity" if source == selected else
                       "PF1 pooled gradient was constructed by state.proposal() "
                       "at base s2, while S0 FreeOracle selected a scalar "
                       f"{selected} arm; persisted sample arrays are absent"),
        })
    exact = all(row["exact_match"] for row in rows)
    return {
        "gradient_source_proposal": "PF1 base state proposal",
        "pf2_preferred_anchor": "per-state S0 FreeOracle-selected proposal",
        "state_count": len(rows),
        "exact_match_count": sum(row["exact_match"] for row in rows),
        "mismatch_count": sum(not row["exact_match"] for row in rows),
        "exact_match": exact,
        "exact_reweighting_available": False,
        "state_rows": rows,
        "verdict_text": ("ANCHOR COMPATIBLE" if exact else
                         "FRESH GRADIENT CONSTRUCTION REQUIRED"),
    }


__all__ = [
    "SOURCE_SPECS", "anchor_compatibility_audit", "build_manifest",
    "identifiability_audit", "sha256_file", "verify_manifest",
]
