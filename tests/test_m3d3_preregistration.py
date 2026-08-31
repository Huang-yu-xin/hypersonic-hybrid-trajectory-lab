"""D3-1 preregistration invariants; no simulator work is invoked."""

from __future__ import annotations

import json
import subprocess

from scripts.freeze_m3d3_1_preregistration import CONFIG, SUMMARY, freeze_preregistration


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_m3d3_parent_route_and_zero_sim_preregistration():
    result = freeze_preregistration()
    assert result["extra_simulator_calls"] == 0
    assert result["route"] == "D3-1 PREREGISTRATION COMPLETE"
    assert result["stop_before_discovery"] is True


def test_m3d3_parent_lineage_and_source_manifest():
    freeze_preregistration()
    tags = set(subprocess.run(["git", "tag", "--list"], check=True, capture_output=True, text=True).stdout.split())
    assert {"RareTopo-ER1-v0", "RareTopo-M3-v2", "RareTopo-M3-D-v1"} <= tags
    d30 = _json(SUMMARY / "m3d3_d3_0_summary.json")
    manifest = _json(SUMMARY / "m3d3_1_source_manifest.json")
    assert d30["route"] == "D3-0A"
    assert d30["primary_axis"] == "s2_selected_component_covariance_scale"
    assert len(manifest["items"]) == 10
    assert all(item["read_only"] for item in manifest["items"])


def test_m3d3_log_interpolation_and_dedup_are_frozen():
    freeze_preregistration()
    candidates = _json(SUMMARY / "m3d3_candidate_states.json")
    generation = candidates["candidate_generation"]
    assert generation["interpolation_space"] == "log_s2"
    assert generation["fractions"] == [0.25, 0.5, 0.75]
    assert generation["raw_generated_candidates"] == 15
    assert generation["deduplicated_candidates"] == 14
    assert generation["distinct_configs"] == 5


def test_m3d3_firewall_classifier_seeds_and_diversity_gate():
    freeze_preregistration()
    protocol = _json(CONFIG / "m3d3_protocol.json")
    diversity = _json(CONFIG / "m3d3_diversity_gate.json")
    assert protocol["classifier_reuse"] == {"widen_reduction_threshold": -0.01, "hold_band": 0.03, "paired_support_se_multiplier": 2.0, "direction_margin": 0.05, "min_arm_ess": 20.0}
    assert protocol["discovery"]["n_per_arm"] == 100000
    assert protocol["confirmation"]["n_per_arm"] == 500000
    assert protocol["firewall"]["controller_online_trials"] == 0
    assert protocol["firewall"]["rarity_shift"] == "BLOCKED"
    assert diversity["distinct_hold_config_ids_minimum"] == 4
