"""M4-PF0 source-lock, identifiability and output-schema tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from hyptraj.m4pf.provenance import (
    SOURCE_SPECS,
    build_manifest,
    identifiability_audit,
    verify_manifest,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf0" / "summary"


def test_m4pf0_source_hashes():
    manifest = json.loads((SUMMARY / "m4pf0_source_manifest.json").read_text(
        encoding="utf-8"))
    assert manifest["source_count"] == len(SOURCE_SPECS)
    assert verify_manifest(REPO, manifest) == []
    assert manifest["sources_unchanged"] is True


def test_m4pf0_identifiability_audit():
    audit = identifiability_audit(REPO)
    assert audit["frozen_sample_level_matrix_reconstruction"] is False
    assert audit["verdict_text"] == "NOT IDENTIFIABLE FROM EXISTING ARTIFACTS"
    assert "g_hat" in audit["aggregate_fields_found"]
    assert audit["missing_groups"]


def test_m4pf0_state_table_retains_24_states():
    with (SUMMARY / "m4pf0_state_gradient_table.csv").open(
            encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 24
    assert all(row["identifiable"] == "false" for row in rows)
    assert all(row["reason"] for row in rows)


def test_m4pf0_schema():
    doc = json.loads((SUMMARY / "m4pf0_gradient_diagnostics.json").read_text(
        encoding="utf-8"))
    assert doc["schema_version"] == "raretopo-m4pf0-gradient-diagnostics-v0"
    assert doc["extra_simulator_calls"] == 0
    assert doc["source_lock"]["verified"] is True
    assert doc["pf0_verdict"] in {
        "GO", "GO-WITHOUT-FROZEN-RECONSTRUCTION", "NO-GO"
    }
    assert doc["pf0_verdict"] == "GO-WITHOUT-FROZEN-RECONSTRUCTION"
    assert doc["real_state_directional_diagnostics"] is None
    assert doc["real_state_figures_allowed"] is False
