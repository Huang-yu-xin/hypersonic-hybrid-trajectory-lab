"""Evidence tests for the corrected M3-D reference-gate replay."""

import csv
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "results/evidence_repair/reanalysis/M3-D"


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_m3d_reference_gate_stops_online_replay() -> None:
    gate = _json("m3d_corrected_reference_gate.json")
    assert gate["event_semantics_schema_version"] == 2
    assert gate["observed_composition"] == {
        "WIDEN": 6, "SHRINK": 7, "HOLD": 3,
        "REFERENCE_AMBIGUOUS": 8,
    }
    assert gate["gate"] == "FAIL"
    assert gate["online_child_authorized"] is False
    assert gate["stop_old_lineage"] is True
    assert gate["probability_scale_guard"]["arms_checked"] == 72
    assert gate["probability_scale_guard"]["all_passed"] is True
    assert gate["m3d_online_metrics"]["VRF"].startswith("NOT_RUN")


def test_m3d_replay_preserves_protocol_and_provenance() -> None:
    gate = _json("m3d_corrected_reference_gate.json")
    freeze_path = REPO / gate["corrected_freeze_path"]
    assert hashlib.sha256(freeze_path.read_bytes()).hexdigest() == gate["corrected_freeze_sha256"]
    assert gate["repair_simulator_calls"] == 24 * 3 * 500_000
    assert gate["original_frozen_sample_count_per_arm"] == 500_000
    assert gate["repair_sample_count_per_arm"] == 500_000
    assert gate["seed_reuse_status"] == gate["draw_order_status"] == "EXACT"


def test_m3d_corrected_freeze_has_probability_manifest() -> None:
    freeze = _json("m3d_corrected_reference_freeze.json")
    assert freeze["event_semantics_schema_version"] == 2
    assert freeze["repair_parent_tag"] == "RareTopo-M3-v1"
    assert len(freeze["states"]) == 24
    manifest = freeze["probability_semantics_manifest"]
    assert manifest["p_hat_definition"] == "mean(I[topology != S0] * p/q)"
    assert manifest["m2_definition"] == "mean((I[topology != S0] * p/q)^2)"


def test_m3d_delta_table_covers_all_frozen_states() -> None:
    with (ROOT / "m3d_reference_legacy_vs_corrected.csv").open(
            encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 24
    assert len({row["state_id"] for row in rows}) == 24
    assert sum(row["legacy_class"] != row["corrected_class"] for row in rows) == 12
    assert all(row["legacy_P_base"] and row["corrected_P_base"] for row in rows)
