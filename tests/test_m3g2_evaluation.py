"""G2-1/G2-2/G2-3 audit tests over the frozen M3-G2 result files."""

from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

from hyptraj.m3g2.evaluation import directional_summary, safety_summary
from hyptraj.m3g2.policy import decide_from_gradient

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3g2" / "summary"


def load(name: str) -> dict:
    return json.loads((SUMMARY / name).read_text(encoding="utf-8"))


def rows(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_m3g2_equal_replicates_and_uniform_pilot_budget():
    data = rows("m3g2_directional_trials.csv") + rows("m3g2_safety_trials.csv") + rows("m3g2_reserve_trials.csv")
    counts = {}
    for row in data:
        counts[row["state_id"]] = counts.get(row["state_id"], 0) + 1
    assert set(counts.values()) == {8}
    assert {row["pilot_sample_count"] for row in data} == {"20000"}


def test_m3g2_no_state_adaptive_sampling_and_unique_trial_seeds():
    data = rows("m3g2_directional_trials.csv") + rows("m3g2_safety_trials.csv") + rows("m3g2_reserve_trials.csv")
    assert len({(row["axis"], row["state_id"], row["replicate"]) for row in data}) == len(data)
    assert len({row["seed"] for row in data}) == len(data)


def test_m3g2_truth_not_visible_to_policy():
    params = set(inspect.signature(decide_from_gradient).parameters)
    assert not {"truth", "reference", "oracle", "state_id"} & params


def test_m3g2_wrong_direction_coverage_and_selective_accuracy_metrics():
    summary = load("m3g2_directional_summary.json")
    assert (summary["correct"], summary["wrong"], summary["abstain"]) == (128, 0, 0)
    assert summary["wrong_direction_rate"] == 0.0
    assert summary["coverage"] == 1.0
    assert summary["selective_accuracy"] == 1.0
    assert len(summary["per_state"]) == 16


def test_m3g2_safety_unsafe_metric():
    summary = load("m3g2_safety_summary.json")
    assert (summary["abstain"], summary["unsafe_deployment"], summary["trials"]) == (11, 29, 40)
    assert summary["unsafe_deployment_rate"] == 29 / 40
    assert set(summary["by_reference_status"]) == {"HOLD", "AMBIGUOUS"}


def test_m3g2_always_abstain_selective_accuracy_undefined():
    table = rows("m3g2_baseline_comparison.csv")
    abstain = next(row for row in table if row["Policy"] == "Always-Abstain")
    assert abstain["Direction coverage"] == "0.0"
    assert abstain["Selective acc"] == ""


def test_m3g2_gate_logic_and_reserve_exclusion():
    primary = load("m3g2_primary_verdict.json")
    final = load("m3g2_final_verdict.json")
    assert primary["reserve_metrics"] is None
    assert final["gate_M3G2_1"] == "PASS"
    assert final["gate_M3G2_2"] == "PASS"
    assert final["gate_M3G2_3"] == "FAIL"
    assert final["verdict"] == "G2-D"


def test_m3g2_no_posthoc_policy_change():
    hash_audit = load("m3g2_pre_run_hash_audit.json")
    prereg = load("m3g2_prereg_hashes.json")
    assert hash_audit["hashes"]["policy"] == prereg["policy"]
    assert hash_audit["hashes"]["gates"] == prereg["gates"]


def test_m3g2_output_schema():
    required = {"axis", "state_id", "truth_reference_status", "replicate", "seed",
                "pilot_sample_count", "gradient_estimate", "gradient_ci_low",
                "gradient_ci_high", "ESS", "policy_action", "abstain_reason",
                "numerical_validity", "legality_passed"}
    for name in ("m3g2_directional_trials.csv", "m3g2_safety_trials.csv", "m3g2_reserve_trials.csv"):
        assert required <= set(rows(name)[0])
    final = load("m3g2_final_verdict.json")
    assert {"directional_wrong_rate", "directional_coverage", "safety_unsafe_rate",
            "reserve_metrics", "verdict", "next_authorized_action"} <= set(final)


def test_m3g2_metric_functions_preserve_undefined_selective_accuracy():
    trial = {"truth_reference_status": "WIDEN", "outcome": "abstain", "policy_action": "ABSTAIN",
             "state_id": "x", "ESS": 30, "gradient_estimate": 0, "gradient_ci_low": -1, "gradient_ci_high": 1}
    assert directional_summary([trial])["selective_accuracy"] is None
    safety = dict(trial, truth_reference_status="HOLD")
    assert safety_summary([safety])["unsafe_deployment_rate"] == 0.0
