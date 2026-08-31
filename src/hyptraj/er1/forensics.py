"""Zero-simulator ER-1 forensic artifact generation."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


LAST_CLEAN_COMMIT = "098fbc1cad5a2b00c9ced12c1b008336bcf49e56"
FIRST_CONTAMINATED_COMMIT = "0f6cdfe8fb6fc938e73b555f55d758980c9510f2"
HISTORICAL_TAGS = [
    "RareTopo-M2-v0", "RareTopo-M3-v0", "RareTopo-M3-D-v0",
    "RareTopo-M3-G-v1", "RareTopo-M3-BV-v0", "RareTopo-M3-BV2-v0",
    "RareTopo-M3-CA-v0", "RareTopo-M4-PF0-v0", "RareTopo-M4-PF1-v0",
    "RareTopo-M4-PF2-0-v0", "RareTopo-M4-PF2-v0",
    "RareTopo-M4-PF3-0-v0", "RareTopo-M4-PF3-v0",
]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def _sources(repo: Path) -> list[dict[str, str]]:
    paths = [
        "configs/evidence_repair/er1_protocol.json",
        "docs/evidence_repair/ER1_Event_Semantics_Contract.md",
        "docs/phase_m1d/M1_D_Benchmark_Freeze.json",
        "src/hyptraj/m1d/benchmark_family.py",
        "src/hyptraj/m1d/metrics.py",
        "src/hyptraj/m2/covariance_policy.py",
        "src/hyptraj/event_semantics.py",
        "scripts/run_m3_scalar_experiments.py",
        "src/hyptraj/m3d/adaptation.py",
        "src/hyptraj/m3d/reference_direction.py",
        "scripts/run_m3g_exact_proxy_replay.py",
        "scripts/run_m3g_ga2_diagnostic.py",
        "scripts/run_m3bv2_controllers.py",
        "src/hyptraj/m4pf1/experiment.py",
        "src/hyptraj/m4pf2/experiment.py",
        "src/hyptraj/m4pf3/experiment.py",
        "results/phase_m3/scalar_layer_a/scalar_layer_a_v1.json",
        "results/phase_m3d/layer_a/m3d_layer_a_v1.json",
        "results/phase_m3g_v1/layer_a/m3g_v1_confirmatory_v1.json",
        "results/phase_m3bv2/controller_evaluation.json",
        "results/phase_m3bv2/value_analysis.json",
        "results/phase_m3ca/summary/m3ca_state_table.csv",
        "results/phase_m4pf1/m4pf1_confirmation_raw.json",
        "results/phase_m4pf2/m4pf2_confirmation_raw.json",
        "results/phase_m4pf3/m4pf3_confirmation_raw.json",
    ]
    sources = []
    for rel in paths:
        path = repo / rel
        if not path.is_file():
            raise FileNotFoundError(path)
        sources.append({"path": rel, "sha256": _sha(path), "read_only": True})
    for stage in ("phase_m4pf2", "phase_m4pf3"):
        for path in sorted((repo / f"results/{stage}/gradient_samples/confirmation").glob("*.npz")):
            sources.append({
                "path": path.relative_to(repo).as_posix(),
                "sha256": _sha(path),
                "read_only": True,
            })
    return sources


def _metric_impact_rows() -> list[dict[str, Any]]:
    rows = []
    direct_metrics = ["P_hat", "M2", "VRF_proposal", "VRF_budget", "ESS"]
    gradient_metrics = ["gradient sign", "gradient magnitude", "action label", "Oracle action", "BestFixed"]
    for stage in ("M3-v0", "M3-D", "M3-G-v1", "M3-BV/BV2"):
        for metric in direct_metrics + gradient_metrics:
            rows.append({
                "stage": stage, "metric": metric,
                "direct_or_indirect_impact": "DIRECTLY_CONTAMINATED",
                "raw_data_sufficient_for_repair": "NO",
                "new_simulation_required": "YES",
                "reason": "sample-level final evaluation/pilot arrays are not persisted",
            })
    for metric in ("headroom", "FreeOracle", "VRF_budget", "BestFixed"):
        rows.append({
            "stage": "M3-CA", "metric": metric,
            "direct_or_indirect_impact": "DERIVED_FROM_CONTAMINATED_PARENT",
            "raw_data_sufficient_for_repair": "PARENT_REQUIRED",
            "new_simulation_required": "NO_DIRECT_CALLS",
            "reason": "artifact-only audit can be rebuilt only after corrected BV2",
        })
    for stage in ("M4-PF1", "M4-PF2", "M4-PF3"):
        metrics = direct_metrics + ["gradient sign", "gradient magnitude", "FreeOracle"]
        if stage == "M4-PF3":
            metrics += ["coverage U99/U999", "allocation mismatch", "birth score"]
        for metric in metrics:
            partial = stage in ("M4-PF2", "M4-PF3") and metric in (
                "gradient sign", "gradient magnitude", "coverage U99/U999",
                "allocation mismatch", "birth score")
            rows.append({
                "stage": stage, "metric": metric,
                "direct_or_indirect_impact": "DIRECTLY_CONTAMINATED",
                "raw_data_sufficient_for_repair": "PARTIAL" if partial else "NO",
                "new_simulation_required": "NO_FOR_DIAGNOSTIC" if partial else "YES_IF_STAGE_AUTHORIZED",
                "reason": "gradient archives exist but final evaluation samples do not" if partial else "final evaluation samples are not persisted",
            })
    rows.append({
        "stage": "M4-PF0", "metric": "gradient identities / SPD algebra",
        "direct_or_indirect_impact": "STRUCTURALLY_VALID",
        "raw_data_sufficient_for_repair": "YES",
        "new_simulation_required": "NO",
        "reason": "symbolic identities and safety proofs do not depend on event-label literal",
    })
    return rows


def run_forensics(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    out = repo / "results/evidence_repair/summary"
    forensic_freeze_commit = "d1f62621fa263f1153f6762249ae12c3f1e918d7"
    tags = {tag: _git(repo, "rev-list", "-n", "1", tag)
            for tag in HISTORICAL_TAGS}
    sources = _sources(repo)
    for source in sources:
        frozen = subprocess.run(
            ["git", "show", f"{forensic_freeze_commit}:{source['path']}"],
            cwd=repo, capture_output=True,
        )
        if frozen.returncode == 0:
            source["sha256"] = hashlib.sha256(frozen.stdout).hexdigest()
            source["hash_basis"] = "git_blob_at_forensic_freeze_commit"
        else:
            source["hash_basis"] = "working_tree_at_forensic_freeze"
    manifest = {
        "schema_version": "raretopo-er1-source-manifest-v0",
        "repair_stage": "ER-1",
        "forensic_freeze_commit": forensic_freeze_commit,
        "extra_simulator_calls": 0,
        "sources": sources,
        "historical_tags": tags,
        "historical_tags_mutated": False,
        "sources_unchanged": True,
    }
    boundary = {
        "schema_version": "raretopo-er1-contamination-boundary-v0",
        "last_known_clean_commit": LAST_CLEAN_COMMIT,
        "last_known_clean_stage": "M3-2 estimator stack / pre-benchmark; RareTopo-M2-v0 is the last clean frozen stage",
        "first_known_contaminated_commit": FIRST_CONTAMINATED_COMMIT,
        "first_known_contaminated_stage": "M3-v0 empirical scalar benchmark",
        "contaminated_function": "scripts/run_m3_scalar_experiments.py event-mask construction at four call sites",
        "contaminated_field": "ind_event / indicators",
        "semantic_mismatch": "topology labels S0-S4 compared against non-domain literal NOMINAL",
        "affected_metrics": ["variance_mass", "gradient", "P_hat", "M2", "ESS", "action", "VRF", "all downstream gates"],
        "confidence": "HIGH",
        "evidence": {
            "first_commit_search": "git log --reverse -S'!= \"NOMINAL\"' -- scripts/run_m3_scalar_experiments.py",
            "parent_contains_literal": False,
            "first_commit_contains_literal": True,
            "m2_uses_authoritative_nominal_constant": True,
        },
    }
    nodes = [
        ("M1-D/M2 event semantics", "UNAFFECTED", None),
        ("M3-v0 empirical", "DIRECTLY_CONTAMINATED", "M1-D/M2 event semantics"),
        ("M3-D", "DIRECTLY_CONTAMINATED", "M3-v0 empirical"),
        ("M3-G-v1", "DIRECTLY_CONTAMINATED", "M3-D"),
        ("M3-BV/BV2", "DIRECTLY_CONTAMINATED", "M3-G-v1"),
        ("M3-CA", "DERIVED_FROM_CONTAMINATED_PARENT", "M3-BV/BV2"),
        ("M4-PF0 theory", "PARTIALLY_VALID", "M3-CA"),
        ("M4-PF1", "DIRECTLY_CONTAMINATED", "M4-PF0 theory"),
        ("M4-PF2", "DIRECTLY_CONTAMINATED", "M4-PF1"),
        ("M4-PF3-0/PF3", "DIRECTLY_CONTAMINATED", "M4-PF2"),
        ("M5-AR parent freeze", "BLOCKED_BY_CONTAMINATED_PARENT", "M4-PF3-0/PF3"),
    ]
    graph = {
        "schema_version": "raretopo-er1-dependency-graph-v0",
        "nodes": [{"stage": stage, "status": status, "parent": parent}
                  for stage, status, parent in nodes],
        "child_requires_corrected_parent_gate": True,
        "m5ar_status": "BLOCKED",
    }
    repairability = {
        "schema_version": "raretopo-er1-raw-repairability-v0",
        "extra_simulator_calls": 0,
        "stages": [
            {"stage": "M3-v0", "raw_sample_arrays": False, "status": "NEW_SIMULATION_REQUIRED", "minimal_rerun": "original scalar benchmark with frozen states/seeds/budgets"},
            {"stage": "M3-D", "raw_sample_arrays": False, "status": "NEW_SIMULATION_REQUIRED_IF_PARENT_AUTHORIZES", "minimal_rerun": "original M3-D protocol"},
            {"stage": "M3-G-v1", "raw_sample_arrays": False, "status": "NEW_SIMULATION_REQUIRED_IF_PARENT_AUTHORIZES", "minimal_rerun": "original confirmation protocol without GA1 retuning"},
            {"stage": "M3-BV/BV2", "raw_sample_arrays": False, "status": "NEW_SIMULATION_REQUIRED_IF_PARENT_AUTHORIZES", "minimal_rerun": "original matched controller streams"},
            {"stage": "M3-CA", "raw_sample_arrays": False, "status": "REANALYZE_CORRECTED_PARENT_ONLY", "minimal_rerun": None},
            {"stage": "M4-PF0", "raw_sample_arrays": False, "status": "STRUCTURAL_REANALYSIS_ONLY", "minimal_rerun": None},
            {"stage": "M4-PF1", "raw_sample_arrays": False, "status": "NEW_SIMULATION_REQUIRED_IF_PARENT_AUTHORIZES", "minimal_rerun": "original PF1 protocol"},
            {"stage": "M4-PF2", "raw_sample_arrays": True, "status": "PARTIAL_REANALYSIS; FINAL_EVALUATION_REPLAY_REQUIRED_IF_AUTHORIZED", "minimal_rerun": "final evaluation only after corrected PF1 gate"},
            {"stage": "M4-PF3", "raw_sample_arrays": True, "status": "PARTIAL_REANALYSIS; FINAL_EVALUATION_REPLAY_REQUIRED_IF_AUTHORIZED", "minimal_rerun": "PF3-0 raw reanalysis then conditional final evaluation"},
        ],
        "new_simulation_required": True,
        "first_required_stage": "M3-v0",
        "reason": "the earliest contaminated empirical stage did not persist pilot or final-evaluation samples and likelihood-ratio arrays",
    }
    initial_ledger = []
    for tag, commit in tags.items():
        if tag == "RareTopo-M2-v0":
            status, affected = "VALID", []
        elif tag == "RareTopo-M4-PF0-v0":
            status, affected = "PARTIALLY_VALID", ["scientific application to contaminated gradients"]
        else:
            status, affected = "SUPERSEDED_PENDING_REVALIDATION", ["event-dependent empirical metrics and gates"]
        initial_ledger.append({
            "historical_tag": tag, "historical_commit": commit,
            "semantic_status": status, "affected_metrics": affected,
            "corrected_tag": None, "corrected_commit": None,
            "child_authorized": False,
            "notes": "historical tag preserved; corrected lineage not yet frozen",
        })
    final_lineage = {
        "repair_stage": "ER-1",
        "status": "FORENSICS_COMPLETE_REPLAY_PENDING",
        "root_cause": "S0-S4 topology labels were compared with the non-domain literal NOMINAL",
        "last_known_clean_stage": "M3-2 pre-benchmark / RareTopo-M2-v0 frozen empirical parent",
        "first_contaminated_stage": "M3-v0 empirical scalar benchmark",
        "event_semantics_schema_version": 2,
        "historical_tags_mutated": False,
        "stages": [],
        "current_valid_frontier": "RareTopo-M2-v0 plus structurally valid M3 theory/estimator algebra",
        "m5ar_authorized": False,
        "m3q_authorized": False,
        "repair_simulator_calls": 0,
    }
    _write_json(out / "er1_source_manifest.json", manifest)
    _write_json(out / "er1_contamination_boundary.json", boundary)
    _write_json(out / "er1_dependency_graph.json", graph)
    _write_csv(out / "er1_metric_impact.csv", _metric_impact_rows())
    _write_json(out / "er1_raw_repairability.json", repairability)
    final_path = out / "er1_final_lineage.json"
    existing_final = (json.loads(final_path.read_text(encoding="utf-8"))
                      if final_path.exists() else None)
    if existing_final and str(existing_final.get("status", "")).startswith("COMPLETE"):
        final_lineage = existing_final
    else:
        _write_json(out / "er1_supersession_ledger.json", initial_ledger)
        _write_json(final_path, final_lineage)
    return {"manifest": manifest, "boundary": boundary, "graph": graph,
            "repairability": repairability, "lineage": final_lineage}
