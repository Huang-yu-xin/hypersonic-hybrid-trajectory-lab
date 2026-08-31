"""Regression checks for the M3-RF zero-simulator action-space review."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "phase_m3rf" / "summary"


def _json(name):
    return json.loads((SUMMARY / name).read_text(encoding="utf-8"))


def test_m3rf_parent_d3_disc_b():
    assert _json("m3rf_route_decision.json")["d3_enrichment_test"]["verdict"] == "FAIL_HOLD_INSUFFICIENT"


def test_m3rf_zero_simulator():
    assert _json("m3rf_route_decision.json")["zero_simulator"] == {"extra_simulator_calls": 0, "controller_online_trials": 0}


def test_m3rf_source_hashes():
    for item in _json("m3rf_source_manifest.json")["items"]:
        assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]


def test_m3rf_state_deduplication():
    rows = list(csv.DictReader((SUMMARY / "m3rf_corrected_state_universe.csv").open(encoding="utf-8")))
    decision = _json("m3rf_route_decision.json")["corrected_evidence"]
    assert len(rows) == len({row["state_id"] for row in rows}) == decision["unique_state_count"] == 91
    assert decision["duplicate_state_count"] == 46


def test_m3rf_classifier_unchanged():
    manifest = _json("m3rf_source_manifest.json")
    assert any(item["role"] == "frozen classifier source" for item in manifest["items"])


def test_m3rf_event_semantics_unchanged():
    manifest = _json("m3rf_source_manifest.json")
    assert any(item["role"] == "full-event semantics contract" for item in manifest["items"])


def test_m3rf_no_historical_remote_as_corrected():
    blob = (ROOT / "docs/phase_m3rf/M3_RF_Action_Space_Reformulation_Task.md").read_text(encoding="utf-8")
    assert "not corrected empirical evidence" in blob


def test_m3rf_no_third_hold_search():
    assert _json("m3rf_route_decision.json")["no_third_hold_search"] is True


def test_m3rf_rarity_shift_blocked():
    assert _json("m3rf_route_decision.json")["rarity_shift"] == "BLOCKED"


def test_m3rf_m3q_blocked():
    assert _json("m3rf_route_decision.json")["m3_q"] == "BLOCKED"


def test_m3rf_single_primary_route():
    decision = _json("m3rf_route_decision.json")
    assert decision["primary_route"] == "M3-RF-B"
    assert set(decision["route_comparison"]) == {"RFA", "RFB", "RFC", "RFD", "RFE"}


def test_m3rf_output_schema():
    names = {p.name for p in SUMMARY.iterdir()}
    assert {"m3rf_source_manifest.json", "m3rf_corrected_state_universe.csv", "m3rf_hold_ambiguity_comparison.csv", "m3rf_action_space_evidence.csv", "m3rf_route_decision.json"} <= names
