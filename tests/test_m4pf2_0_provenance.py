"""PF2-0 parent freeze, zero-call, source and anchor tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from hyptraj.m4pf2.provenance import (
    SOURCE_SPECS,
    anchor_compatibility_audit,
    identifiability_audit,
    verify_manifest,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf2_0" / "summary"
RAW = json.loads((REPO / "results" / "phase_m4pf1" /
                  "m4pf1_confirmation_raw.json").read_text(encoding="utf-8"))


def test_m4pf2_pf1_parent_freeze():
    lock = json.loads((REPO / "configs" / "phase_m4pf2_0" /
                       "m4pf2_0_analysis_lock.json").read_text(encoding="utf-8"))
    assert lock["parent_tag"] == "RareTopo-M4-PF1-v0"
    assert lock["parent_commit"] == \
        "e6885bb59a8437cd5834a3a60ccf07c9c89624fe"


def test_m4pf2_zero_simulator_calls_pf2_0():
    doc = json.loads((SUMMARY / "m4pf2_0_diagnostic.json").read_text(
        encoding="utf-8"))
    assert doc["extra_simulator_calls"] == 0


def test_m4pf2_source_hashes():
    manifest = json.loads((SUMMARY / "m4pf2_0_source_manifest.json").read_text(
        encoding="utf-8"))
    assert manifest["source_count"] == len(SOURCE_SPECS)
    assert verify_manifest(REPO, manifest) == []
    assert manifest["sources_unchanged"] is True


def test_m4pf2_mean_gradient_not_identifiable_from_aggregate():
    result = identifiability_audit(RAW)
    assert result["mean_gradient_from_frozen_samples"] is False
    assert result["aggregate_gradient_matrix_present"] is True
    assert result["verdict_text"] == \
        "NOT IDENTIFIABLE FROM EXISTING ARTIFACTS"


def test_m4pf2_anchor_compatibility():
    result = anchor_compatibility_audit(RAW)
    assert result["state_count"] == 24
    assert result["exact_match_count"] == 0
    assert result["mismatch_count"] == 24
    assert result["verdict_text"] == "FRESH GRADIENT CONSTRUCTION REQUIRED"


def test_m4pf2_anchor_table_retains_all_states():
    with (SUMMARY / "m4pf2_0_anchor_table.csv").open(
            encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 24
    assert all(row["exact_match"] == "False" for row in rows)
