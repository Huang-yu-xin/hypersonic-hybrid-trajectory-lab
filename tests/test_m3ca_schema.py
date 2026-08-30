"""M3-CA output completeness and schema tests."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3ca" / "summary"


def rows() -> list[dict]:
    with (SUMMARY / "m3ca_state_table.csv").open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_m3ca_state_count():
    assert len(rows()) == 24


def test_m3ca_class_split():
    assert Counter(row["class"] for row in rows()) == {
        "WIDEN": 12, "SHRINK": 12
    }


def test_m3ca_all_states_retained():
    state_rows = rows()
    value = json.loads((REPO / "results" / "phase_m3bv2" /
                        "value_analysis.json").read_text(encoding="utf-8"))
    expected = {(s["state_key"]["config_id"], str(s["state_key"]["s2"]))
                for s in value["freeze_selection"]}
    actual = {(s["config_id"], str(float(s["s2"]))) for s in state_rows}
    assert actual == {(cid, str(float(s2))) for cid, s2 in expected}


def test_m3ca_schema():
    summary = json.loads((SUMMARY / "m3ca_cost_attribution.json").read_text(
        encoding="utf-8"))
    assert summary["stage"] == "M3-CA"
    assert summary["extra_simulator_calls"] == 0
    assert summary["source_lock"]["verified"] is True
    assert summary["headline_reproduction"]["pass"] is True
    assert summary["verdict"]["code"] in {"A", "B", "C", "D"}
    required = {
        "state_id", "config_id", "s2", "class", "oracle_action",
        "base_m2_median", "best_fixed_m2_median", "oracle_m2_median",
        "m3d_m2_median", "m3g_v1_m2_median",
        "m3g_v1_vrf_budget_median", "free_adaptation_vrf_median",
        "free_oracle_vrf_median", "pilot_fraction",
        "absolute_efficiency_class",
    }
    assert required <= set(rows()[0])


def test_m3ca_vrf_reference_line_consistency():
    summary = json.loads((SUMMARY / "m3ca_cost_attribution.json").read_text(
        encoding="utf-8"))
    assert summary["counterfactuals"]["vrf_budget_crude_mc"] == 1.0
    assert all(float(row["free_oracle_vrf_median"]) < 1.0 for row in rows())
