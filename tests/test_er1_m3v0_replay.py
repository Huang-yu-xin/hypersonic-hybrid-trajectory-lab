"""Corrected M3-v0 replay-gate evidence tests."""

import csv
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "results/evidence_repair/reanalysis/M3-v0"


def test_corrected_m3v0_gate_uses_locked_thresholds() -> None:
    gate = json.loads((ROOT / "summary/m3v0_corrected_gate.json").read_text())
    assert gate["event_semantics_schema_version"] == 2
    assert gate["seed_reuse_status"] == "EXACT"
    assert gate["draw_order_status"] == "EXACT"
    assert gate["repair_simulator_calls"] == 64 * 320_000
    assert gate["gates"]["M3_3_direction_accuracy"]["verdict"] == "FAIL"
    assert gate["gates"]["STRONG_budget_adjusted_vrf"]["verdict"] == "NOT PASSED"


def test_corrected_m3v0_authorizes_only_sign_diverse_benchmark() -> None:
    gate = json.loads((ROOT / "summary/m3v0_corrected_gate.json").read_text())
    assert gate["child_stage"] == "M3-D"
    assert gate["child_authorized"] is True
    assert gate["decision_counts"].get("SHRINK", 0) == 0


def test_corrected_m3v0_delta_table_complete() -> None:
    with (ROOT / "m3v0_legacy_vs_corrected.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 5
    assert {"legacy", "corrected", "scientific_consequence"} <= set(rows[0])
