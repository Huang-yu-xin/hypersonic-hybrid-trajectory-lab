from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from hyptraj.m5ar.audit import build_manifest, verify_manifest


REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results/phase_m5ar/summary"
PROTOCOL = json.loads((REPO / "configs/phase_m5ar/m5ar_protocol.json").read_text(encoding="utf-8"))


def _json(name: str):
    return json.loads((SUMMARY / name).read_text(encoding="utf-8"))


def test_m5ar_pf3_parent_freeze():
    assert PROTOCOL["parent_tag"] == "RareTopo-M4-PF3-v0"
    resolved = subprocess.check_output(
        ["git", "rev-parse", "RareTopo-M4-PF3-v0^{}"], cwd=REPO, text=True
    ).strip()
    assert resolved == PROTOCOL["parent_commit"]
    assert _json("m5ar_pf3_parent_freeze_audit.json")["status"] == "FAIL"


def test_m5ar_zero_simulator_calls():
    verdict = _json("m5ar_routing_verdict.json")
    assert PROTOCOL["extra_simulator_calls"] == verdict["extra_simulator_calls"] == 0
    tree = ast.parse((REPO / "src/hyptraj/m5ar/audit.py").read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name and "simulation" in name for name in imports)


def test_m5ar_source_hashes():
    manifest = _json("m5ar_source_manifest.json")
    assert manifest["sources_unchanged"] is True
    assert not verify_manifest(REPO, manifest)
    assert build_manifest(REPO)["source_count"] == manifest["source_count"]


def test_m5ar_nominal_label_semantic_mismatch_is_explicit():
    audit = _json("m5ar_pf3_parent_freeze_audit.json")
    assert audit["frozen_nominal_label"] == "S0"
    assert audit["downstream_comparison_literal"] == "NOMINAL"
    assert audit["semantic_mismatch"] is True
    assert audit["gate"] == "STOP_DO_NOT_START_M5AR"


def test_m5ar_pf3_probability_record_exposes_mismatch():
    audit = _json("m5ar_pf3_parent_freeze_audit.json")
    assert 0.99 < audit["pf3_A1_probability_median"] < 1.01
    assert audit["frozen_event_probability_median"] < 0.1
    assert audit["median_probability_ratio"] > 10


def test_m5ar_variance_mass_is_not_rare_event_mass():
    audit = _json("m5ar_pf3_parent_freeze_audit.json")
    assert audit["median_true_event_share_of_stored_variance_mass"] < 0.05
    assert audit["true_event_share_range"][1] < 0.1


def test_m5ar_blocked_before_ar0_and_routing():
    verdict = _json("m5ar_routing_verdict.json")
    assert verdict["status"] == "BLOCKED"
    assert verdict["routing_performed"] is False
    assert verdict["primary_route"] is None
    assert verdict["single_primary_route"] is False
    assert verdict["m3q_status"] == "BLOCKED"


def test_m5ar_invalid_provisional_outputs_absent():
    forbidden = {
        "m5ar_local_family_ceiling.json", "m5ar_local_family_ceiling.csv",
        "m5ar_stage_ladder.csv", "m5ar_residual_gap_table.csv",
        "m5ar_representation_audit.json", "m5ar_static_architecture_audit.json",
        "m5ar_path_stage_audit.json", "m5ar_regime_audit.json",
    }
    assert not (forbidden & {path.name for path in SUMMARY.iterdir()})
    assert not (REPO / "figures/phase_m5ar").exists()


def test_m5ar_no_budget_change_and_no_m3q():
    assert "budget change" in PROTOCOL["forbidden"]
    assert "M3-Q reopening" in PROTOCOL["forbidden"]
    assert PROTOCOL["analysis_only"] is True
