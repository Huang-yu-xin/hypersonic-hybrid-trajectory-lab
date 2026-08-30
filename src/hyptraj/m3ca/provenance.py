"""Source hashing and read-only provenance checks for M3-CA."""

from __future__ import annotations

import hashlib
from pathlib import Path


SOURCE_SPECS = (
    ("results/phase_m3bv2/controller_evaluation.json", "M3-BV2",
     "controller actions, selected-arm M2/P/VRF and headline J", True),
    ("results/phase_m3bv2/value_analysis.json", "M3-BV2",
     "24-state value selection and fixed/Oracle replicate M2", False),
    ("results/phase_m3bv2/decision_analysis.json", "M3-BV2",
     "decision-axis freeze evidence", False),
    ("results/phase_m3bv2/reuse_record.json", "M3-BV2",
     "BV-v0 prior-data reuse and source identity", False),
    ("results/phase_m3bv/reference/m3bv_candidate_pool.json", "M3-BV-v0",
     "reference P, M2 and leakage fields", False),
    ("results/phase_m3bv/reference/m3bv_headline_stability.json", "M3-BV-v0",
     "100k matched replicate M2 for all fixed arms", False),
    ("docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.json", "M3-BV2",
     "decision benchmark freeze", False),
    ("docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.json", "M3-BV2",
     "value benchmark freeze", False),
    ("configs/phase_m3bv2/m3bv2_decision_benchmark.json", "M3-BV2",
     "decision benchmark configuration", False),
    ("configs/phase_m3bv2/m3bv2_value_benchmark.json", "M3-BV2",
     "value benchmark configuration", False),
    ("configs/phase_m3d/m3d_online_v0.json", "M3-D",
     "pilot/evaluation budgets and controller protocol", True),
    ("configs/phase_m3g_v1/m3g_v1_protocol.json", "M3-G-v1",
     "gain-gate protocol", True),
    ("configs/phase_m3g_v1/m3g_v1_confirmatory_seeds.json", "M3-G-v1",
     "frozen decision seed declaration", False),
    ("results/phase_m3g_v1/layer_a/m3g_v1_confirmatory_v1.json", "M3-G-v1",
     "upstream confirmatory controller record", False),
    ("results/phase_m3d/layer_a/m3d_layer_a_v1.json", "M3-D",
     "upstream raw-gradient controller record", False),
    ("docs/phase_m1d/M1_D_Benchmark_Freeze.json", "M1-D",
     "stored per-configuration event probabilities", False),
)

TAG_BY_STAGE = {
    "M3-BV2": "RareTopo-M3-BV2-v0",
    "M3-BV-v0": "RareTopo-M3-BV-v0",
    "M3-G-v1": "RareTopo-M3-G-v1",
    "M3-D": "RareTopo-M3-D-v0",
    "M1-D": "RareTopo-M1-D-v1.0",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_manifest(repo: Path) -> dict:
    sources = []
    for rel, stage, role, deployable in SOURCE_SPECS:
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(f"required M3-CA source missing: {rel}")
        sources.append({
            "path": rel,
            "sha256": sha256_file(path),
            "source_stage": stage,
            "source_commit_or_tag": TAG_BY_STAGE[stage],
            "artifact_role": role,
            "deployable_record": bool(deployable),
            "audit_only": not bool(deployable),
            "read_only": True,
        })
    return {
        "schema_version": "raretopo-m3ca-source-manifest-v0",
        "stage": "M3-CA",
        "parent_tag": "RareTopo-M3-BV2-v0",
        "source_count": len(sources),
        "sources_unchanged": True,
        "sources": sources,
    }


def verify_source_manifest(repo: Path, manifest: dict) -> list[str]:
    mismatches = []
    for source in manifest["sources"]:
        path = repo / source["path"]
        if not path.is_file():
            mismatches.append(f"missing:{source['path']}")
        elif sha256_file(path) != source["sha256"]:
            mismatches.append(f"hash:{source['path']}")
    return mismatches
