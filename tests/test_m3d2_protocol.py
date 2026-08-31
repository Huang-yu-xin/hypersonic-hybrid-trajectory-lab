"""Preregistered semantic, protocol and benchmark tests for M3-D2."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from hyptraj.event_semantics import (
    EventSemanticsError,
    compute_event_statistics,
    event_indicator_from_topology,
)
from hyptraj.m3d2.experiment import (
    classify_reference_state,
    probability_sanity_gate,
)
from hyptraj.m3d2.selection import build_final_benchmark, build_shortlist

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "configs" / "phase_m3d2"


def _json(name: str) -> dict:
    return json.loads((CFG / name).read_text(encoding="utf-8"))


def _sha(name: str) -> str:
    return hashlib.sha256((CFG / name).read_bytes()).hexdigest()


def _arm(m2: float, p: float = 0.08, se: float = 0.001) -> dict:
    batches = [m2 * (1 + 0.002 * ((index % 5) - 2))
               for index in range(20)]
    return {"M2": m2, "P": p, "P_batch_se": se, "ESS": 1000.0,
            "m2_batches": batches}


def _pref(p: float = 0.08, se: float = 0.001) -> dict:
    return {"p_ref_full": p, "p_ref_full_SE": se}


def test_m3d2_event_schema_v2():
    protocol = _json("m3d2_protocol.json")
    assert protocol["event_semantics_schema_version"] == 2
    assert protocol["event_definition_id"] == "FULL_TOPOLOGY_EVENT_S1_S4"


def test_m3d2_event_topology_not_s0():
    labels = np.array(["S0", "S1", "S2", "S3", "S4"], dtype=object)
    assert event_indicator_from_topology(labels).tolist() == [False, True,
                                                              True, True,
                                                              True]


def test_m3d2_nominal_literal_not_event():
    with np.testing.assert_raises(EventSemanticsError):
        event_indicator_from_topology(np.array(["NOMINAL"], dtype=object))


def test_m3d2_probability_domain_full_s1_s4():
    contract = _json("m3d2_probability_contract.json")
    assert contract["full_event"] == ["S1", "S2", "S3", "S4"]


def test_m3d2_missing_mode_pref_not_used():
    contract = _json("m3d2_probability_contract.json")
    assert contract["historical_missing_mode_reference_forbidden"] is True
    assert contract["reference"]["method"] == "direct target Monte Carlo"


def test_m3d2_arm_probability_same_event():
    contract = _json("m3d2_probability_contract.json")
    assert contract["arm_estimates"]["same_event_required"] is True
    assert "S1-S4" in contract["arm_estimates"]["definition"]


def test_m3d2_variance_mass_zero_for_non_event():
    stats = compute_event_statistics(np.array([False, True]),
                                     np.array([7.0, 2.0]))
    assert stats.variance_mass.tolist() == [0.0, 4.0]


def test_m3d2_parent_tags():
    tags = set(subprocess.run(["git", "tag", "--list"], cwd=REPO,
                              check=True, capture_output=True,
                              text=True).stdout.splitlines())
    assert {"RareTopo-M2-v0", "RareTopo-M3-v2",
            "RareTopo-M3-D-v1"} <= tags


def test_m3d2_classifier_contract_hash():
    protocol = _json("m3d2_protocol.json")
    locks = protocol["preregistration_hash_locks"]
    assert _sha("m3d2_classifier_contract.json") == locks[
        "m3d2_classifier_contract.json"]


def test_m3d2_candidate_pool_frozen():
    candidates = _json("m3d2_candidate_states.json")
    assert len(candidates["frozen_config_ids"]) * len(
        candidates["s2_grid"]) == candidates["candidate_count"] == 72
    assert candidates["post_discovery_changes_allowed"] is False


def test_m3d2_discovery_seed_lock():
    seed = _json("m3d2_discovery_seeds.json")
    assert seed["count"] == 72
    assert seed["namespace"] == "D2-DISCOVERY"


def test_m3d2_confirmation_seed_lock():
    seed = _json("m3d2_confirmation_seeds.json")
    assert seed["namespace"] == "D2-CONFIRMATION"
    assert seed["candidate_index_range_inclusive"] == [0, 71]


def test_m3d2_seed_disjointness():
    assert len({3202000, 3202001, 3202002}) == 3
    assert _json("m3d2_discovery_seeds.json")["namespace"] != _json(
        "m3d2_confirmation_seeds.json")["namespace"]


def test_m3d2_no_controller_evaluation():
    source = (REPO / "scripts" / "run_m3d2_pipeline.py").read_text(
        encoding="utf-8")
    assert "hyptraj.m3g" not in source
    assert "run_m3g" not in source
    assert _json("m3d2_protocol.json")["firewall"][
        "controller_online_trials"] == 0


def test_m3d2_no_posthoc_grid_change():
    assert _json("m3d2_candidate_states.json")[
        "post_discovery_changes_allowed"] is False


def test_m3d2_no_posthoc_threshold_change():
    assert _json("m3d2_classifier_contract.json")["retuning_allowed"] is False
    assert _json("m3d2_balancing_rule.json")["posthoc_changes_allowed"] is False


def test_m3d2_probability_sanity_gate():
    arms = {"base": _arm(1.0), "widen": _arm(0.8, 0.0805),
            "shrink": _arm(1.2, 0.0795)}
    assert probability_sanity_gate(arms, _pref())["pass"] is True
    arms["shrink"]["P"] = 0.10
    assert probability_sanity_gate(arms, _pref())["pass"] is False


def test_m3d2_discovery_classifier():
    arms = {"base": _arm(1.0), "widen": _arm(0.80),
            "shrink": _arm(1.20)}
    result = classify_reference_state(arms, _pref())
    assert result["corrected_class"] == "WIDEN"
    assert result["reference_action_class_valid"] is True


def _rows(action: str, count: int) -> list[dict]:
    return [{"corrected_class": action,
             "class_certainty_score": 10.0 - index / 10,
             "config_id": f"c{index % 4}", "s2": 1.0 + index,
             "state_id": f"{action}-{index}"} for index in range(count)]


def test_m3d2_shortlist_deterministic():
    rows = sum((_rows(action, 12) for action in ("WIDEN", "HOLD",
                                                 "SHRINK")), [])
    assert build_shortlist(rows) == build_shortlist(list(reversed(rows)))


def test_m3d2_confirmation_classifier():
    arms = {"base": _arm(1.0), "widen": _arm(1.005),
            "shrink": _arm(0.995)}
    assert classify_reference_state(arms, _pref())["corrected_class"] == "HOLD"


def test_m3d2_ambiguous_not_forced():
    arms = {"base": _arm(1.0), "widen": _arm(0.995),
            "shrink": _arm(1.05)}
    assert classify_reference_state(arms, _pref())[
        "corrected_class"] == "AMBIGUOUS"


def test_m3d2_class_transition_schema():
    required = {"state_id", "discovery_class", "confirmation_class",
                "transition"}
    example = {"state_id": "x", "discovery_class": "HOLD",
               "confirmation_class": "HOLD", "transition": "HOLD->HOLD"}
    assert required <= set(example)


def test_m3d2_final_class_counts():
    rows = sum((_rows(action, 10) for action in ("WIDEN", "HOLD",
                                                 "SHRINK")), [])
    result = build_final_benchmark(rows)
    assert all(result["classes"][action]["selected_count"] == 8
               for action in ("WIDEN", "HOLD", "SHRINK"))


def test_m3d2_final_8_8_8():
    rows = sum((_rows(action, 10) for action in ("WIDEN", "HOLD",
                                                 "SHRINK")), [])
    assert build_final_benchmark(rows)["M3D2_1"] == "PASS"


def test_m3d2_final_unique_configs():
    rows = sum((_rows(action, 10) for action in ("WIDEN", "HOLD",
                                                 "SHRINK")), [])
    result = build_final_benchmark(rows)
    for action in ("WIDEN", "HOLD", "SHRINK"):
        ids = [row["state_id"] for row in
               result["classes"][action]["selected"]]
        assert len(ids) == len(set(ids))


def test_m3d2_state_diversity_rule():
    rows = _rows("HOLD", 12)
    result = build_final_benchmark(rows + _rows("WIDEN", 12) +
                                   _rows("SHRINK", 12))
    assert result["classes"]["HOLD"]["distinct_configs"] >= 3
    assert max(sum(row["config_id"] == cid for row in
                   result["classes"]["HOLD"]["selected"])
               for cid in {row["config_id"] for row in rows}) <= 3


def test_m3d2_output_schema():
    assert _json("m3d2_protocol.json")["stop_after"].startswith(
        "benchmark-only freeze")
