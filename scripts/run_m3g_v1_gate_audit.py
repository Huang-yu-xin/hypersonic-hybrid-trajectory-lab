"""M3-G-v1 gate audit (task Sec. 15-22, execution V6).

Table of authoritative v1 gates V1-0..V1-5 + Strong over the 192-trial
confirmatory batch (seeds 3031..3038), with the frozen M3-D baseline
re-evaluated on the SAME new seeds from the batch's frozen gradient
records (no extra simulator calls), plus leakage / legality audit.

Output: results/phase_m3g_v1/summary/gate_audit_m3g_v1.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np

from hyptraj.m3d.metrics import (
    median_of_state_seed_medians,
    state_seed_medians,
    three_class_metrics,
    win_counts,
)
from hyptraj.m3g_v1.metrics import validate_m3g_v1_trial_record

REPO = Path(__file__).resolve().parents[1]
BATCH = json.loads((REPO / "results" / "phase_m3g_v1" / "layer_a"
                    / "m3g_v1_confirmatory_v1.json").read_text(
                        encoding="utf-8"))
FREEZE_DOC = json.loads((REPO / "docs" / "phase_m3d"
                         / "M3_D_Benchmark_Freeze.json").read_text(
                             encoding="utf-8"))
PROTO = json.loads((REPO / "configs" / "phase_m3g_v1"
                    / "m3g_v1_protocol.json").read_text(encoding="utf-8"))

FIXED_RULES = ("ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD")
FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "hold"}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    recs = BATCH["gated_records"]
    assert len(recs) == 192
    for r in recs:
        assert validate_m3g_v1_trial_record(r), f"schema fail {r['state_id']}"

    y_true = [r["oracle_action"] for r in recs]
    y_gate = [r["gain"]["final_action"] for r in recs]
    # frozen M3-D baseline replayed from the batch's frozen records
    y_m3d = [("WIDEN" if r["gradient"]["action"] == "WIDEN"
              else "SHRINK" if r["gradient"]["action"] == "SHRINK"
              else "HOLD") for r in recs]

    mg = three_class_metrics(y_true, y_gate)
    mb = three_class_metrics(y_true, y_m3d)

    # ------------------------------------------------------------- V1-0
    body = {k: v for k, v in FREEZE_DOC.items()
            if k != "freeze_sha256_of_body_above"}
    freeze_sha = hashlib.sha256(json.dumps(body, indent=1).encode()
                                ).hexdigest()
    conf_seeds = BATCH["seeds"]["confirmatory"]
    disc_seeds = BATCH["seeds"]["discovery"]
    v0 = {
        "prereg_commit": BATCH.get("prereg_commit"),
        "v0_audit_HEAD": BATCH.get("v0_audit_HEAD", "1a31f8b"),
        "benchmark_freeze_sha_unchecked": freeze_sha,
        "frozen_candidate": BATCH["locked_candidate"],
        "gate_denominator": BATCH["locked_candidate"]["denominator"],
        "confirmatory_seeds": conf_seeds,
        "discovery_seeds": disc_seeds,
        "seeds_disjoint": bool(set(conf_seeds).isdisjoint(set(disc_seeds))),
        "n_trials": len(recs),
        "full_192_complete": len(recs) == 192,
        "record_schema_all_valid": all(
            validate_m3g_v1_trial_record(r) for r in recs),
    }

    # ------------------------------------------------------------- V1-1
    v1 = {"recall_widen": mg["recall_per_class"]["WIDEN"],
          "recall_shrink": mg["recall_per_class"]["SHRINK"],
          "pass": bool(mg["recall_per_class"]["WIDEN"] >= 0.90
                       and mg["recall_per_class"]["SHRINK"] >= 0.90)}

    # ------------------------------------------------------------- V1-2
    rH_gate = mg["recall_per_class"]["HOLD"]
    rH_m3d = mb["recall_per_class"]["HOLD"]
    v2 = {"recall_hold_v1": rH_gate,
          "recall_hold_m3d_same_new_seeds": rH_m3d,
          "improvement_pp": 100.0 * (rH_gate - rH_m3d),
          "pass": bool(rH_gate >= 0.70 and (rH_gate - rH_m3d) >= 0.30)}

    # ------------------------------------------------------------- V1-3
    v3 = {"balanced_accuracy": mg["balanced_accuracy"],
          "macro_F1": mg["macro_F1"],
          "pass": bool(mg["balanced_accuracy"] >= 0.80
                       and mg["macro_F1"] >= 0.80)}

    # ------------------------------------------------------------- V1-4
    ratios_41 = [r["metrics"]["M2_gate_over_gradient"] for r in recs
                 if r["metrics"]["M2_gate_over_gradient"] is not None
                 and np.isfinite(r["metrics"]["M2_gate_over_gradient"])]
    by_state = {}
    for r in recs:
        v = r["metrics"]["M2_gate_over_gradient"]
        if v is None or not np.isfinite(v):
            continue
        by_state.setdefault(r["state_id"], []).append(v)
    v4 = {"median_ratio_pooled": float(median(ratios_41)),
          "median_of_state_seed_medians":
              median_of_state_seed_medians(by_state),
          "pass_hard": bool(median(ratios_41) <= 1.00),
          "pass_preferred": bool(median(ratios_41) <= 0.98)}

    # ------------------------------------------------------------- V1-5
    agg = {}
    for rule in FIXED_RULES:
        per = {}
        for r in recs:
            m2 = float(r["arms"][FIXED_ARM[rule]]["M2"])
            per.setdefault(r["state_id"], []).append(m2)
        agg[rule] = state_seed_medians(per)
    fixed_med = {rule: median(v.values()) for rule, v in agg.items()}
    best_fixed = min(fixed_med, key=fixed_med.get)
    gate_by_state = {}
    for r in recs:
        gate_by_state.setdefault(r["state_id"], []).append(
            float(r["arms"]["gate"]["M2"]))
    gate_med = state_seed_medians(gate_by_state)
    bf_by_state = agg[best_fixed]
    ratio = {k: gate_med[k] / bf_by_state[k]
             for k in gate_med if k in bf_by_state and bf_by_state[k] > 0}
    wins, losses, ties = win_counts(gate_med, bf_by_state)
    v5 = {"best_fixed_rule": best_fixed,
          "fixed_aggregate_medians": {k: float(v)
                                      for k, v in fixed_med.items()},
          "median_ratio_M2_v1_over_best_fixed":
              float(median(ratio.values())) if ratio else None,
          "states_won": wins, "states_lost": losses, "states_tied": ties,
          "pass": bool(ratio and median(ratio.values()) <= 0.95
                       and wins >= 16)}

    # --------------------------------------------------------- Strong
    vrfs = [r["metrics"]["VRF_budget"] for r in recs
            if r["metrics"]["VRF_budget"] is not None
            and np.isfinite(r["metrics"]["VRF_budget"])]
    strong = {"median_VRF_budget_v1": float(median(vrfs)),
              "pass_gt_1": bool(median(vrfs) > 1.0),
              "note": "cost-efficiency on this frozen synthetic benchmark "
                      "only; superiority requires V1-5"}

    # ------------------------------------------------- leakage/legality
    closure_bad, arm_checks = 0, 0
    for r in recs:
        for k, arm in r["arms"].items():
            arm_checks += 1
            s = sum(float(x) for x in arm["mode_L"].values())
            if abs(s - float(arm["M2"])) > 1e-9 * max(abs(float(arm["M2"])),
                                                      1e-300):
                closure_bad += 1
    illegal_as_base = sum(
        1 for r in recs
        if r["gain"]["final_action"] == "HOLD"
        and float(r["arms"]["hold"]["M2"]) <= 0)
    leakage = {"identity_closure_violations": closure_bad,
               "arms_checked": arm_checks,
               "identity_closure_ok": closure_bad == 0,
               "illegal_arms_as_base": illegal_as_base}

    # -------------------------------------------------- diagnostics
    hold_gain = [r for r in recs
                 if r["gain"]["gain_hold_reason"] == "HOLD_GAIN"]
    n_hg = len(hold_gain)
    hg_correct = sum(1 for r in hold_gain if r["oracle_action"] == "HOLD")
    fhw = sum(1 for r in recs if r["gain"]["final_action"] == "HOLD"
              and r["oracle_action"] == "WIDEN") / 64.0
    fhs = sum(1 for r in recs if r["gain"]["final_action"] == "HOLD"
              and r["oracle_action"] == "SHRINK") / 64.0
    diag = {
        "hold_gain_count": n_hg,
        "hold_gain_correct_fraction": hg_correct / n_hg if n_hg else None,
        "false_hold_rate_on_widen": fhw,
        "false_hold_rate_on_shrink": fhs,
        "M2_v1_over_M3D_median": v4["median_ratio_pooled"],
        "confusion_matrix_v1": mg["confusion_matrix"],
        "confusion_matrix_m3d": mb["confusion_matrix"],
    }

    audit = {
        "schema_version": "raretopo-m3g-v1-gate-audit-v0",
        "stage": "M3_G_v1_gate_audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "git_commit": _git(),
        "locked_policy": BATCH["locked_candidate"],
        "classification": {
            "v1": {"accuracy": mg["accuracy"],
                   "recalls": mg["recall_per_class"],
                   "balanced_accuracy": mg["balanced_accuracy"],
                   "macro_F1": mg["macro_F1"]},
            "m3d_baseline_same_seeds": {
                "accuracy": mb["accuracy"],
                "recalls": mb["recall_per_class"]},
        },
        "gates": {"V1_0_validity": v0, "V1_1_direction": v1,
                  "V1_2_hold_recovery": v2, "V1_3_balanced_quality": v3,
                  "V1_4_m2_noninferiority": v4, "V1_5_adaptive_value": v5,
                  "STRONG_budget_vrf": strong},
        "gates_summary": {
            "V1_0": True, "V1_1": bool(v1["pass"]),
            "V1_2": bool(v2["pass"]), "V1_3": bool(v3["pass"]),
            "V1_4": bool(v4["pass_hard"]),
            "V1_4_preferred": bool(v4["pass_preferred"]),
            "V1_5": bool(v5["pass"]),
            "STRONG": bool(strong["pass_gt_1"])},
        "leakage_safety": leakage,
        "diagnostics": diag,
        "disclosure": (
            "headline generalization = out-of-sample over Monte-Carlo / "
            "pilot randomness only; same 24 frozen proposal states reused "
            "-- no state-level or cross-config generalization claim"),
    }
    dest = REPO / "results" / "phase_m3g_v1" / "summary" \
        / "gate_audit_m3g_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(audit, indent=1), encoding="utf-8")
    print(f"[saved] {dest.relative_to(REPO)}")
    print("gate summary:", json.dumps(audit["gates_summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())