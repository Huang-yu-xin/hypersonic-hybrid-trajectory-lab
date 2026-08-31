"""D3-0 regression tests: artifact-only boundary diagnosis."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.run_m3d3_d3_0 import OUT, build_d3_0


def test_m3d3_parent_d2b_and_zero_simulator_diagnosis():
    result = build_d3_0()
    assert result["extra_simulator_calls"] == 0
    assert result["state_rows"] == 72
    assert result["confirmed_hold"] == 3
    assert result["route"] == "D3-0A"


def test_m3d3_boundary_outputs_are_deterministic_and_diagnostic_only():
    build_d3_0()
    rows = list(csv.DictReader((OUT / "d3_0_d2_state_table.csv").open(encoding="utf-8")))
    brackets = list(csv.DictReader((OUT / "d3_0_s2_boundary_brackets.csv").open(encoding="utf-8")))
    assert len(rows) == 72
    assert "hold_proximity_score_diagnostic_only" in rows[0]
    assert len(brackets) >= 5
    assert {row["boundary_type"] for row in brackets} >= {"W_H_S_PATH", "W_AMBIGUOUS_S_PATH"}
    assert all(Path(path).exists() for path in [
        OUT / "d3_0_confirmed_hold_signature.csv",
        OUT / "d3_0_candidate_axis_inventory.csv",
    ])
