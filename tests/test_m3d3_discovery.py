"""Locked M3-D3-2 discovery checks."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "phase_m3d3" / "summary"


def _json(name):
    return json.loads((SUMMARY / name).read_text(encoding="utf-8"))


def test_m3d3_discovery_candidate_count_14(): assert _json("m3d3_discovery_summary.json")["candidate_audit"]["candidate_count"] == 14
def test_m3d3_discovery_config_count_5(): assert _json("m3d3_discovery_summary.json")["candidate_audit"]["config_count"] == 5
def test_m3d3_discovery_candidate_hash_lock(): assert _json("m3d3_discovery_summary.json")["prereg_hashes_unchanged"]
def test_m3d3_discovery_seed_separation(): assert _json("m3d3_discovery_seed_audit.json")["pass"]
def test_m3d3_discovery_classifier_hash(): assert _json("m3d3_discovery_summary.json")["classifier_audit"]["pass"]
def test_m3d3_discovery_event_semantics(): assert all(row["event_definition"] == "topology != S0" for row in _json("m3d3_discovery_summary.json")["records"])
def test_m3d3_discovery_full_event_reference(): assert all(row["full_event_probability_reference"]["event_definition_id"] == "FULL_TOPOLOGY_EVENT_S1_S4" for row in _json("m3d3_discovery_summary.json")["records"])
def test_m3d3_discovery_uniform_budget(): assert {row["sample_count_per_arm"] for row in _json("m3d3_discovery_summary.json")["records"]} == {100000}
def test_m3d3_discovery_crn_alignment(): assert all(row["crn_integrity"]["batch_alignment_exact"] for row in _json("m3d3_discovery_summary.json")["records"])
def test_m3d3_discovery_no_adaptive_samples(): assert len(_json("m3d3_discovery_summary.json")["records"]) * 300000 == _json("m3d3_discovery_summary.json")["simulator_samples"]
def test_m3d3_discovery_gate(): assert _json("m3d3_discovery_summary.json")["gate"]["result"] in {"PASS", "FAIL_HOLD_INSUFFICIENT", "INVALID"}
def test_m3d3_hold_shortlist_only_hold():
    summary = _json("m3d3_discovery_summary.json")
    if summary["shortlist_created"]: assert {row["discovery_class"] for row in _json("m3d3_shortlist.json")["selected"]} <= {"HOLD"}
def test_m3d3_hold_shortlist_cap_12():
    summary = _json("m3d3_discovery_summary.json")
    if summary["shortlist_created"]: assert len(_json("m3d3_shortlist.json")["selected"]) <= 12
def test_m3d3_shortlist_deterministic():
    summary = _json("m3d3_discovery_summary.json")
    if summary["shortlist_created"]: assert _json("m3d3_shortlist.json")["source_discovery_sha256"] == hashlib.sha256((SUMMARY / "m3d3_discovery_prereg_hashes.json").read_bytes()).hexdigest()
def test_m3d3_controller_zero(): assert _json("m3d3_discovery_summary.json")["controller_online_trials"] == 0
def test_m3d3_rarity_blocked(): assert _json("m3d3_discovery_summary.json")["rarity_shift"] == "BLOCKED"
