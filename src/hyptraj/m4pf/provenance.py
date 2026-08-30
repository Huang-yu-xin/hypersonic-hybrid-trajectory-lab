"""PF0 source hashing and persisted-sample identifiability audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_SPECS = (
    ("results/phase_m3/scalar_layer_a/scalar_layer_a_v1.json", "M3",
     "scalar gradient records"),
    ("results/phase_m3/scalar_layer_b/scalar_layer_b_v1.json", "M3",
     "scalar perturbation confirmation"),
    ("results/phase_m3d/layer_a/m3d_layer_a_v1.json", "M3-D",
     "sign-diverse scalar controller records"),
    ("results/phase_m3g_v1/layer_a/m3g_v1_confirmatory_v1.json", "M3-G-v1",
     "gain-gated controller records"),
    ("results/phase_m3bv2/controller_evaluation.json", "M3-BV2",
     "Value-Axis selected-arm records"),
    ("results/phase_m3bv2/value_analysis.json", "M3-BV2",
     "frozen 24-state Value-Axis records"),
    ("results/phase_m3ca/summary/m3ca_cost_attribution.json", "M3-CA",
     "absolute-efficiency attribution"),
    ("results/phase_m3ca/summary/m3ca_state_table.csv", "M3-CA",
     "24-state efficiency table"),
    ("configs/phase_m3/m3_scalar_gradient_v0.json", "M3",
     "scalar estimator convention"),
    ("configs/phase_m3d/m3d_online_v0.json", "M3-D",
     "pilot/evaluation protocol"),
    ("docs/phase_m3ca/M3_CA_Cost_Efficiency_Attribution_Audit.md", "M3-CA",
     "parent verdict and claim boundary"),
)

TAG_BY_STAGE = {
    "M3": "RareTopo-M3-v0",
    "M3-D": "RareTopo-M3-D-v0",
    "M3-G-v1": "RareTopo-M3-G-v1",
    "M3-BV2": "RareTopo-M3-BV2-v0",
    "M3-CA": "RareTopo-M3-CA-v0",
}

SAMPLE_KEY_GROUPS = {
    "sample_or_whitened_coordinates": {"z", "samples", "sample_coordinates",
                                        "whitened", "whitened_coordinates"},
    "variance_mass_exact_inputs": {"variance_mass", "a_i", "logp", "logr",
                                   "indicators", "event_indicator"},
    "per_sample_responsibility": {"responsibility", "responsibilities",
                                  "component_responsibility"},
    "source_strata": {"source_strata", "strata"},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(repo: Path) -> dict:
    sources = []
    for rel, stage, role in SOURCE_SPECS:
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(f"required PF0 source missing: {rel}")
        sources.append({
            "path": rel,
            "sha256": sha256_file(path),
            "source_stage": stage,
            "source_tag": TAG_BY_STAGE[stage],
            "role": role,
            "read_only": True,
        })
    return {
        "schema_version": "raretopo-m4pf0-source-manifest-v0",
        "stage": "M4-PF0",
        "source_count": len(sources),
        "sources_unchanged": True,
        "sources": sources,
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


def _structural_keys(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(str(key))
            _structural_keys(child, found)
    elif isinstance(value, list):
        for child in value:
            _structural_keys(child, found)


def identifiability_audit(repo: Path) -> dict:
    json_sources = [repo / rel for rel, _, _ in SOURCE_SPECS
                    if rel.endswith(".json") and "m3ca_cost" not in rel]
    found_by_file: dict[str, list[str]] = {}
    all_keys: set[str] = set()
    for path in json_sources:
        doc = json.loads(path.read_text(encoding="utf-8"))
        keys: set[str] = set()
        _structural_keys(doc, keys)
        all_keys.update(keys)
        found_by_file[str(path.relative_to(repo)).replace("\\", "/")] = sorted(keys)

    groups = {}
    for label, accepted in SAMPLE_KEY_GROUPS.items():
        present = sorted(accepted & all_keys)
        groups[label] = {"identifiable": bool(present), "structural_keys": present}

    # Persisted aggregate fields are not substitutes for sample arrays.
    aggregate_only = sorted({"g_hat", "ESS_grad", "M2_hat",
                             "responsibility_mass"} & all_keys)
    identifiable = all(item["identifiable"] for item in groups.values())
    missing = [name for name, item in groups.items() if not item["identifiable"]]
    return {
        "frozen_sample_level_matrix_reconstruction": identifiable,
        "required_groups": groups,
        "missing_groups": missing,
        "aggregate_fields_found": aggregate_only,
        "aggregate_fields_are_insufficient": True,
        "verdict_text": ("IDENTIFIABLE" if identifiable else
                         "NOT IDENTIFIABLE FROM EXISTING ARTIFACTS"),
        "reason": (None if identifiable else
                   "Frozen JSON records retain aggregate scalar-gradient and "
                   "evaluation summaries but not the per-sample arrays needed "
                   "to form E_nuV[r_k z_k z_k^T]."),
    }
