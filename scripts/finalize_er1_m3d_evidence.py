"""Finalize M3-D deltas and probability-scale checks without simulation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from hyptraj.event_semantics import probability_scale_guard
from hyptraj.m1d.experiments import load_freeze, ref_views


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "results/evidence_repair/reanalysis/M3-D"


def historical_references() -> dict[tuple[str, float], dict]:
    result = {}
    for path in sorted((REPO / "results/phase_m3d/reference").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        candidates = list(data.get("reference_fields", {}).values())
        candidates += [value for value in data.values()
                       if isinstance(value, dict) and "state_key" in value
                       and "arms" in value]
        for value in candidates:
            key = value["state_key"]
            result[(key["config_id"], round(float(key["s2"]), 10))] = value
    return result


def main() -> int:
    freeze_path = ROOT / "m3d_corrected_reference_freeze.json"
    gate_path = ROOT / "m3d_corrected_reference_gate.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    historical = historical_references()
    config_refs = {row["config_id"]: float(sum(ref_views(row)["P"].values()))
                   for row in load_freeze()["benchmark_configs"]}
    rows = []
    scale_rows = []
    missing_reference_ratios = []
    for state in freeze["states"]:
        key = (state["config_id"], round(float(state["s2"]), 10))
        old = historical[key]
        new_arms = state["reference"]["arms"]
        old_base = old["arms"]["base"]
        new_base = new_arms["base"]
        rows.append({
            "state_id": state["state_id"],
            "legacy_class": state["legacy_oracle_action"],
            "corrected_class": state["oracle_action"],
            "legacy_P_base": old_base["P"],
            "corrected_P_base": new_base["P"],
            "absolute_P_difference": new_base["P"] - old_base["P"],
            "relative_P_difference": new_base["P"] / old_base["P"] - 1.0,
            "legacy_M2_base": old_base["M2"],
            "corrected_M2_base": new_base["M2"],
            "absolute_M2_difference": new_base["M2"] - old_base["M2"],
            "relative_M2_difference": new_base["M2"] / old_base["M2"] - 1.0,
            "scientific_consequence": "class_changed" if state["oracle_action"] != state["legacy_oracle_action"] else "class_retained",
        })
        missing_mode_reference = config_refs[state["config_id"]]
        consensus = float(np.median([arm["P"] for arm in new_arms.values()]))
        for arm_name, arm in new_arms.items():
            se = max(0.0, (arm["M2"] - arm["P"] ** 2) / 500_000) ** 0.5
            probability_scale_guard(
                arm["P"], consensus, standard_error=se,
                relative_reference_allowance=0.05,
            )
            scale_rows.append({"state_id": state["state_id"], "arm": arm_name,
                               "p_hat": arm["P"], "consensus": consensus,
                               "standard_error": se})
            missing_reference_ratios.append(arm["P"] / missing_mode_reference)
    with (ROOT / "m3d_reference_legacy_vs_corrected.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    gate["probability_scale_guard"] = {
        "definition": "within-state same-event cross-arm consensus: |P_hat-median_arm(P_hat)| <= 8*SE + 0.05*consensus",
        "event_reference_semantics": "full topology event S1-S4 for every compared arm",
        "arms_checked": len(scale_rows),
        "all_passed": True,
        "max_absolute_difference": max(abs(row["p_hat"] - row["consensus"])
                                       for row in scale_rows),
        "frozen_missing_mode_reference_compatible": False,
        "frozen_missing_mode_reference_semantics": "S2-S4 only; cannot validate full-event P_hat",
        "full_event_to_missing_mode_reference_ratio_range": [
            min(missing_reference_ratios), max(missing_reference_ratios)],
    }
    gate["m3d_online_metrics"] = {
        "P_hat": "REFERENCE_ONLY_RECOMPUTED",
        "M2": "REFERENCE_ONLY_RECOMPUTED",
        "VRF": "NOT_RUN_PARENT_REFERENCE_GATE_FAILED",
        "action_distribution": "NOT_RUN_PARENT_REFERENCE_GATE_FAILED",
    }
    gate_path.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gate["probability_scale_guard"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
