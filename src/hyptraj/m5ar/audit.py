"""M5-AR parent-freeze gate using committed artifacts only.

The taskbook requires an immediate stop when PF3 provenance or semantics are
inconsistent.  This module therefore performs only the source lock and PF3
event-indicator audit.  It contains no simulator entry point and cannot reach
AR0--AR4 after a failed parent gate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from hyptraj.m1d.experiments import config_from_record


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def _source_spec(repo: Path) -> list[dict[str, str]]:
    fixed = [
        ("results/phase_m3ca/summary/m3ca_state_table.csv", "RareTopo-M3-CA-v0", "M3-CA state endpoint table"),
        ("results/phase_m3ca/summary/m3ca_cost_ledger.csv", "RareTopo-M3-CA-v0", "M3-CA cost ledger"),
        ("results/phase_m4pf1/summary/m4pf1_state_table.csv", "RareTopo-M4-PF1-v0", "PF1 state results"),
        ("results/phase_m4pf1/m4pf1_confirmation_raw.json", "RareTopo-M4-PF1-v0", "PF1 confirmation record"),
        ("results/phase_m4pf2/summary/m4pf2_state_table.csv", "RareTopo-M4-PF2-v0", "PF2 state results"),
        ("results/phase_m4pf2/m4pf2_confirmation_raw.json", "RareTopo-M4-PF2-v0", "PF2 confirmation record"),
        ("results/phase_m4pf2_0/summary/m4pf2_0_diagnostic.json", "RareTopo-M4-PF2-0-v0", "PF2-0 diagnostic"),
        ("results/phase_m4pf3_0/summary/m4pf3_0_state_diagnostics.csv", "RareTopo-M4-PF3-0-v0", "PF3-0 state diagnostics"),
        ("results/phase_m4pf3_0/summary/m4pf3_0_diagnostic_summary.json", "RareTopo-M4-PF3-0-v0", "PF3-0 route"),
        ("results/phase_m4pf3/summary/m4pf3_state_results.csv", "RareTopo-M4-PF3-v0", "PF3 A0/A1 state results"),
        ("results/phase_m4pf3/summary/m4pf3_family_summary.json", "RareTopo-M4-PF3-v0", "PF3 family summary"),
        ("results/phase_m4pf3/m4pf3_confirmation_raw.json", "RareTopo-M4-PF3-v0", "PF3 confirmation record"),
        ("configs/phase_m3bv2/m3bv2_value_benchmark.json", "RareTopo-M3-BV2-v0", "24-state definition"),
        ("docs/phase_m1d/M1_D_Benchmark_Freeze.json", "RareTopo-M1-D-v1.0", "event/topology freeze"),
        ("src/hyptraj/m1d/benchmark_family.py", "RareTopo-M1-D-v1.0", "event predicate"),
        ("src/hyptraj/m3d/adaptation.py", "RareTopo-M3-D-v0", "M3-D event indicator"),
        ("src/hyptraj/m3d/reference_direction.py", "RareTopo-M3-D-v0", "M3-D reference event indicator"),
        ("scripts/run_m3bv2_controllers.py", "RareTopo-M3-BV2-v0", "M3-BV2 event indicator"),
        ("scripts/run_m3_scalar_experiments.py", "RareTopo-M3-v0", "M3 event indicator"),
        ("src/hyptraj/m4pf1/experiment.py", "RareTopo-M4-PF1-v0", "PF1 event indicator"),
        ("src/hyptraj/m4pf2/experiment.py", "RareTopo-M4-PF2-v0", "PF2 event indicator"),
        ("src/hyptraj/m4pf3/experiment.py", "RareTopo-M4-PF3-v0", "PF3 event indicator"),
        ("configs/phase_m4pf1/m4pf1_protocol.json", "RareTopo-M4-PF1-v0", "PF1 protocol"),
        ("configs/phase_m4pf2/m4pf2_protocol.json", "RareTopo-M4-PF2-v0", "PF2 protocol"),
        ("configs/phase_m4pf3/m4pf3_protocol.json", "RareTopo-M4-PF3-v0", "PF3 protocol"),
    ]
    sources = [{"path": p, "source_tag": tag, "role": role}
               for p, tag, role in fixed]
    for path in sorted((repo / "results/phase_m4pf3/gradient_samples/confirmation").glob("*.npz")):
        sources.append({
            "path": path.relative_to(repo).as_posix(),
            "source_tag": "RareTopo-M4-PF3-v0",
            "role": "stored PF3 P11 samples and variance mass",
        })
    return sources


def build_manifest(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    sources = []
    for item in _source_spec(repo):
        path = repo / item["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        sources.append({**item, "sha256": sha256_file(path), "read_only": True})
    return {
        "schema_version": "raretopo-m5ar-source-manifest-v0",
        "stage": "M5-AR",
        "parent_tag": "RareTopo-M4-PF3-v0",
        "source_count": len(sources),
        "sources": sources,
        "sources_unchanged": True,
        "post_analysis_mismatches": [],
    }


def verify_manifest(repo: Path, manifest: dict[str, Any]) -> list[str]:
    repo = Path(repo).resolve()
    mismatches = []
    for source in manifest["sources"]:
        path = repo / source["path"]
        if not path.is_file():
            mismatches.append(f"missing:{source['path']}")
        elif sha256_file(path) != source["sha256"]:
            mismatches.append(f"hash:{source['path']}")
    return mismatches


def _benchmark_configs(repo: Path) -> dict[str, dict[str, Any]]:
    freeze = _read_json(repo / "docs/phase_m1d/M1_D_Benchmark_Freeze.json")
    return {record["config_id"]: record for record in freeze["benchmark_configs"]}


def audit_pf3_parent_freeze(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    configs = _benchmark_configs(repo)
    nominal_label = str(config_from_record(next(iter(configs.values()))).label(
        np.zeros((1, 2)))[0])
    inspected = [
        "src/hyptraj/m3d/adaptation.py",
        "src/hyptraj/m3d/reference_direction.py",
        "scripts/run_m3bv2_controllers.py",
        "scripts/run_m3_scalar_experiments.py",
        "src/hyptraj/m4pf1/experiment.py",
        "src/hyptraj/m4pf2/experiment.py",
        "src/hyptraj/m4pf3/experiment.py",
    ]
    affected = [rel for rel in inspected
                if '!= "NOMINAL"' in (repo / rel).read_text(encoding="utf-8")]
    raw = _read_json(repo / "results/phase_m4pf3/m4pf3_confirmation_raw.json")
    p_hat = np.array([float(state["probability"]["A1"]) for state in raw["states"]])
    p_ref = np.array([float(state["p_ref"]) for state in raw["states"]])
    config_by_state = {state["state_id"]: state["state_key"]["config_id"]
                       for state in raw["states"]}
    event_mass_share = []
    archive_dir = repo / "results/phase_m4pf3/gradient_samples/confirmation"
    for path in sorted(archive_dir.glob("*.npz")):
        with np.load(path, allow_pickle=False) as archive:
            mass = np.asarray(archive["variance_mass"], dtype=float)
            labels = config_from_record(configs[config_by_state[path.stem]]).label(
                archive["samples"])
        event_mass_share.append(float(mass[labels != nominal_label].sum() / mass.sum()))
    mismatch = nominal_label != "NOMINAL" and bool(affected)
    return {
        "schema_version": "raretopo-m5ar-pf3-parent-freeze-audit-v0",
        "status": "FAIL" if mismatch else "PASS",
        "frozen_nominal_label": nominal_label,
        "downstream_comparison_literal": "NOMINAL",
        "semantic_mismatch": mismatch,
        "affected_paths": affected,
        "pf3_A1_probability_median": float(np.median(p_hat)),
        "frozen_event_probability_median": float(np.median(p_ref)),
        "median_probability_ratio": float(np.median(p_hat / p_ref)),
        "pf3_A1_probability_range": [float(p_hat.min()), float(p_hat.max())],
        "event_probability_range": [float(p_ref.min()), float(p_ref.max())],
        "median_true_event_share_of_stored_variance_mass": float(np.median(event_mass_share)),
        "true_event_share_range": [float(min(event_mass_share)), float(max(event_mass_share))],
        "interpretation": "The frozen predicate emits S0 for nominal samples, while M3-D/PF1/PF2/PF3 compare against the literal NOMINAL. Every label is therefore treated as event, making stored P_hat approximately one and stored variance_mass predominantly nominal.",
        "gate": "STOP_DO_NOT_START_M5AR" if mismatch else "PASS_START_M5AR",
        "extra_simulator_calls": 0,
    }


def run_audit(repo: Path) -> dict[str, Any]:
    repo = Path(repo).resolve()
    out = repo / "results/phase_m5ar/summary"
    protocol = _read_json(repo / "configs/phase_m5ar/m5ar_protocol.json")
    if protocol["extra_simulator_calls"] != 0:
        raise RuntimeError("zero-simulator invariant violated")
    manifest = build_manifest(repo)
    parent = audit_pf3_parent_freeze(repo)
    mismatches = verify_manifest(repo, manifest)
    manifest["post_analysis_mismatches"] = mismatches
    manifest["sources_unchanged"] = not mismatches
    routing = {
        "schema_version": "raretopo-m5ar-routing-verdict-v0",
        "status": "BLOCKED" if parent["status"] != "PASS" else "READY_FOR_AR0",
        "primary_route": None,
        "single_primary_route": False,
        "routing_performed": False,
        "blocker": "PF3 parent freeze event-indicator semantic mismatch" if parent["status"] != "PASS" else None,
        "blocker_artifact": "results/phase_m5ar/summary/m5ar_pf3_parent_freeze_audit.json",
        "required_action": "repair and separately re-freeze the affected M3-D through PF3 evidence before restarting M5-AR" if parent["status"] != "PASS" else "start AR0",
        "extra_simulator_calls": 0,
        "sources_unchanged": not mismatches,
        "m3q_status": "BLOCKED",
        "claim_boundary": "No AR0-AR4 result or architecture route is valid because the parent evidence failed the first hard gate." if parent["status"] != "PASS" else "parent gate only",
    }
    _write_json(out / "m5ar_source_manifest.json", manifest)
    _write_json(out / "m5ar_pf3_parent_freeze_audit.json", parent)
    _write_json(out / "m5ar_routing_verdict.json", routing)
    return {"manifest": manifest, "parent": parent, "routing": routing}
