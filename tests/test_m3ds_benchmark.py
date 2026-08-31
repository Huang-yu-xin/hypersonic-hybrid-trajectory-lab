"""Preregistered firewall, selection and freeze tests for M3-DS.

M3-DS is a zero-simulator benchmark-construction phase: these tests lock the
dual-axis benchmark (directional sign + abstention safety) against the
corrected lineage and forbid controller execution, rarity-shift and M3-Q.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from hyptraj.m3ds.selection import (
    build_directional_axis,
    safety_primary,
    select_directional,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3ds" / "summary"
D2_SUMMARY = REPO / "results" / "phase_m3d2" / "summary"

DIRECTIONAL = ("WIDEN", "SHRINK")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _d2_records() -> list[dict]:
    return _json(D2_SUMMARY / "m3d2_confirmation_summary.json")["records"]


def _benchmark() -> dict:
    return _json(SUMMARY / "m3ds_benchmark.json")


def _verdict() -> dict:
    return _json(SUMMARY / "m3ds_final_verdict.json")


def test_m3ds_parent_rf_b():
    route = _json(REPO / "results" / "phase_m3rf" / "summary"
                  / "m3rf_route_decision.json")
    assert route["primary_route"] == "M3-RF-B"
    assert route["route_comparison"]["RFB"] == "SUPPORTED"
    manifest = _json(SUMMARY / "m3ds_source_manifest.json")
    assert all(manifest["parent_audit"].values())


def test_m3ds_zero_simulator():
    manifest = _json(SUMMARY / "m3ds_source_manifest.json")
    assert manifest["zero_simulator"]["extra_simulator_calls"] == 0
    analyses = _json(SUMMARY / "m3ds_zero_sim_analyses.json")
    assert analyses["extra_simulator_calls"] == 0
    for script in ("run_m3ds_pipeline.py", "run_m3ds_figures.py"):
        source = (REPO / "scripts" / script).read_text(encoding="utf-8")
        assert "assemble_state" not in source
        assert "evaluate_reference_arms" not in source
        assert "hyptraj.m3g" not in source


def test_m3ds_source_hashes():
    manifest = _json(SUMMARY / "m3ds_source_manifest.json")
    assert len(manifest["entries"]) >= 10
    for entry in manifest["entries"]:
        path = REPO / entry["path"]
        assert path.is_file(), entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == \
            entry["sha256"], entry["path"]
        assert entry["read_only"] is True


def test_m3ds_only_d2_confirmed_directional():
    d2_confirmed = {row["state_id"] for row in _d2_records()
                    if row["corrected_class"] in DIRECTIONAL}
    assert len(d2_confirmed) == 22
    benchmark = _benchmark()
    used = (benchmark["directional_primary"]["widen"]
            + benchmark["directional_primary"]["shrink"]
            + benchmark["directional_reserve"]["widen"]
            + benchmark["directional_reserve"]["shrink"])
    assert set(used) <= d2_confirmed
    d3_ids = {row["state_id"] for row in
              csv.DictReader((REPO / "results" / "phase_m3d3" / "summary"
                              / "m3d3_discovery_states.csv")
                             .open(encoding="utf-8"))}
    assert not (set(used) & d3_ids)


def test_m3ds_exact_8w_8s():
    benchmark = _benchmark()
    assert len(benchmark["directional_primary"]["widen"]) == 8
    assert len(benchmark["directional_primary"]["shrink"]) == 8
    assert len(set(benchmark["directional_primary"]["widen"]
                   + benchmark["directional_primary"]["shrink"])) == 16


def test_m3ds_directional_diversity():
    audit = _json(SUMMARY / "m3ds_directional_selection_audit.json")
    assert audit["M3DS_DIR_1"] == "PASS"
    for cls in DIRECTIONAL:
        info = audit["classes"][cls]
        assert info["distinct_configs"] >= 4
        assert len(info["distinct_strata"]) >= 2
        assert info["diversity_gate"]["distinct_configs_pass"] is True


def test_m3ds_selection_deterministic():
    records = _d2_records()
    first = build_directional_axis(records)
    second = build_directional_axis(list(reversed(records)))
    for cls in DIRECTIONAL:
        assert [row["state_id"] for row in first["classes"][cls]["selected"]
                ] == [row["state_id"]
                      for row in second["classes"][cls]["selected"]]
    audit = _json(SUMMARY / "m3ds_directional_selection_audit.json")
    for cls in DIRECTIONAL:
        assert [row["state_id"] for row in first["classes"][cls]["selected"]
                ] == audit["classes"][cls]["selected_state_ids"]


def test_m3ds_no_future_controller_metric_in_selection():
    source = (REPO / "src" / "hyptraj" / "m3ds" / "selection.py").read_text(
        encoding="utf-8")
    forbidden = ("controller_score", "regret", "vrf", "VRF",
                 "controller_online")
    for token in forbidden:
        assert token not in source.replace("No future controller score, "
                                           "regret, or VRF", "")
    audit = _json(SUMMARY / "m3ds_directional_selection_audit.json")
    assert audit["forbidden_in_selection"] == ["future controller score",
                                               "future regret",
                                               "future VRF"]


def test_m3ds_directional_reserve_frozen():
    benchmark = _benchmark()
    reserve = benchmark["directional_reserve"]
    assert len(reserve["widen"]) == 4
    assert len(reserve["shrink"]) == 2
    assert "robustness only" in reserve["policy"]
    primary = set(benchmark["directional_primary"]["widen"]
                  + benchmark["directional_primary"]["shrink"])
    assert not (primary & set(reserve["widen"] + reserve["shrink"]))


def test_m3ds_safety_only_independently_confirmed():
    rows = _csv("m3ds_safety_primary.csv")
    assert len(rows) == 5
    assert all(row["independently_confirmed"] == "True" for row in rows)
    d2_safety = {row["state_id"] for row in _d2_records()
                 if row["corrected_class"] in ("HOLD", "AMBIGUOUS")}
    assert {row["state_id"] for row in rows} == d2_safety


def test_m3ds_abstain_not_ground_truth_label():
    benchmark = _benchmark()
    assert benchmark["abstention_semantics"]["ground_truth_class"] is False
    assert benchmark["abstention_semantics"]["protocol_behavior"] is True
    assert benchmark["abstention_semantics"]["fallback"] == "BASE"
    statuses = {row["reference_status"] for row in
                _csv("m3ds_safety_primary.csv")}
    assert statuses == {"HOLD", "AMBIGUOUS"}
    audit = _json(SUMMARY / "m3ds_directional_selection_audit.json")
    for cls in DIRECTIONAL:
        assert set(audit["classes"][cls]["selected_state_ids"])
    assert "ABSTAIN" not in json.dumps(benchmark["directional_primary"])


def test_m3ds_event_semantics_unchanged():
    benchmark = _benchmark()
    assert benchmark["event_definition_id"] == "FULL_TOPOLOGY_EVENT_S1_S4"
    assert benchmark["event_semantics_schema_version"] == 2
    records = {row["state_id"]: row for row in _d2_records()}
    ids = (benchmark["directional_primary"]["widen"]
           + benchmark["directional_primary"]["shrink"]
           + benchmark["safety_primary"]["confirmed_hold"]
           + benchmark["safety_primary"]["confirmed_ambiguous"])
    assert len(ids) == 21
    for state_id in ids:
        assert records[state_id]["event_definition_id"] == \
            "FULL_TOPOLOGY_EVENT_S1_S4"
        assert int(records[state_id]["event_semantics_schema_version"]) == 2


def test_m3ds_classifier_unchanged():
    contract_path = REPO / "configs" / "phase_m3d2" / \
        "m3d2_classifier_contract.json"
    contract = _json(contract_path)
    assert contract["retuning_allowed"] is False
    protocol = _json(REPO / "configs" / "phase_m3d2" / "m3d2_protocol.json")
    locked = protocol["preregistration_hash_locks"][
        "m3d2_classifier_contract.json"]
    assert hashlib.sha256(contract_path.read_bytes()).hexdigest() == locked


def test_m3ds_controller_zero():
    assert _benchmark()["controller_online_trials"] == 0
    assert _verdict()["controller_online_trials"] == 0
    assert _verdict()["extra_simulator_calls"] == 0


def test_m3ds_rarity_blocked():
    assert _benchmark()["rarity_shift_authorized"] is False
    assert _verdict()["rarity_shift"] == "BLOCKED"


def test_m3ds_m3q_blocked():
    assert _verdict()["m3_q"] == "BLOCKED"


def test_m3ds_output_schema():
    required = [
        "m3ds_source_manifest.json", "m3ds_directional_candidates.csv",
        "m3ds_directional_selected.csv",
        "m3ds_directional_selection_audit.json", "m3ds_safety_primary.csv",
        "m3ds_benchmark.json", "m3ds_final_verdict.json"]
    assert all((SUMMARY / name).is_file() for name in required)
    benchmark = _benchmark()
    for key in ("directional_primary", "directional_reserve",
                "safety_primary", "safety_expansion",
                "controller_online_trials", "rarity_shift_authorized"):
        assert key in benchmark
    assert benchmark["safety_expansion"] == []
    candidates = _csv("m3ds_directional_candidates.csv")
    fields = {"state_id", "class", "config_id", "s2",
              "confirmation_support", "r_w", "r_s", "selection_rank",
              "selection_reason", "selected"}
    assert fields <= set(candidates[0])
    assert len(candidates) == 22
    selected = select_directional(_d2_records(), "WIDEN")
    assert selected["selected_count"] == 8
    safety = safety_primary(_d2_records())
    assert {row["reference_status"] for row in safety} == {"HOLD",
                                                           "AMBIGUOUS"}
