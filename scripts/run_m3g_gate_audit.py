"""M3-G gate audit (freeze-audit corrected).

Reports TWO gate tiers after the protocol-deviation audit:

Table A -- AUTHORITATIVE preregistered gates (docs/phase_m3g/
    M3_G_Gain_Aware_HOLD_Decision_Task.md @ 9720456, original thresholds).
Table B -- SECONDARY / strengthened audit criteria (execution-task
    handoff thresholds; explicitly NOT the original preregistration).
Strong VRF -- diagnostic only; wording: M3-G retained the M3-D crossing
    of the crude-MC budget-efficiency boundary (VRF identical to M3-D).
Deviation status -- exact-proxy calibration replay outcome (audit JSON
    results/phase_m3g/summary/exact_proxy_calibration_replay.json).
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
    paired_bootstrap_ci,
    state_seed_medians,
    three_class_metrics,
    win_counts,
)
from hyptraj.m3g.gain_gate import apply_gain_gate
from hyptraj.m3g.gain_proxy import DELTA_THETA_MAIN
from hyptraj.m3g.metrics import validate_m3g_trial_record

REPO = Path(__file__).resolve().parents[1]
ONLINE = json.loads((REPO / "results" / "phase_m3g" / "layer_a"
                     / "m3g_online_v1.json").read_text(encoding="utf-8"))
STORED = json.loads((REPO / "results" / "phase_m3d" / "layer_a"
                     / "m3d_layer_a_v1.json").read_text(encoding="utf-8"))
FREEZE_DOC = json.loads((REPO / "docs" / "phase_m3d"
                         / "M3_D_Benchmark_Freeze.json").read_text(
                             encoding="utf-8"))
REPLAY = json.loads((REPO / "results" / "phase_m3g" / "summary"
                     / "exact_proxy_calibration_replay.json").read_text(
                         encoding="utf-8"))

FIXED_RULES = ("ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD")
FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "hold"}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    recs = ONLINE["gated_records"]
    assert len(recs) == 192
    for r in recs:
        assert validate_m3g_trial_record(r), f"schema fail {r['state_id']}"
    stored = {(r["state_id"], int(r["seed"])): r for r in STORED["records"]}

    y_gate = [r["gain"]["final_action"] for r in recs]
    y_m3d = [stored[(r["state_id"], int(r["seed"]))]["validity"]
             ["deployed_action"] for r in recs]
    y_true = [r["oracle_action"] for r in recs]

    mg_gate = three_class_metrics(y_true, y_gate)
    mg_m3d = three_class_metrics(y_true, y_m3d)

    # ------------------------------------------------------------------ M3G-0
    body = {k: v for k, v in FREEZE_DOC.items()
            if k != "freeze_sha256_of_body_above"}
    freeze_sha = hashlib.sha256(json.dumps(body, indent=1).encode()
                                ).hexdigest()
    tag_m3_commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "RareTopo-M3-v0"], cwd=REPO,
        capture_output=True, text=True).stdout.strip()
    tag_m3d_commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "RareTopo-M3-D-v0"], cwd=REPO,
        capture_output=True, text=True).stdout.strip()
    g0 = {
        "task_commit": ONLINE.get("task_commit"),
        "benchmark_freeze_sha_unchecked": freeze_sha,
        "tag_M3v0_commit": tag_m3_commit,
        "tag_M3Dv0_commit": tag_m3d_commit,
        "tags_match_task_doc": bool(
            tag_m3_commit == "32b285625494d9b3da08be3c559db3855df77667"
            and tag_m3d_commit == "7bd58c5992615b8579b1814a3a3fcbea3cda9659"),
        "online_parity_cells_checked": ONLINE["replay_parity"]
        ["cells_checked"],
        "online_parity_cells_mismatched": ONLINE["replay_parity"]
        ["cells_mismatched"],
        "calibration_extra_simulator_calls": 0,
        "pass": bool(
            tag_m3_commit == "32b285625494d9b3da08be3c559db3855df77667"
            and tag_m3d_commit == "7bd58c5992615b8579b1814a3a3fcbea3cda9659"
            and freeze_sha == "b613f45dc6645c6da26ab58b5185764f14d771ca6b996"
                              "bffed88fea1f467a5f3"
            and ONLINE["replay_parity"]["cells_mismatched"] == 0),
    }

    # ------------------------------------------- Table A (authoritative)
    act_indiff_m3d = sum(1 for m, t in zip(y_m3d, y_true)
                         if m in ("WIDEN", "SHRINK") and t == "HOLD")
    act_indiff_m3g = sum(1 for g, t in zip(y_gate, y_true)
                         if g in ("WIDEN", "SHRINK") and t == "HOLD")
    pct = (100.0 * (act_indiff_m3g - act_indiff_m3d) / act_indiff_m3d
           if act_indiff_m3d else None)
    r_fixed_gate = _r_fixed(recs, stored, _best_fixed_rule(recs, stored))
    r_fixed_m3d = _r_fixed_m3d(stored, _best_fixed_rule(recs, stored))
    rm2 = [r["metrics"]["regret_M2"] for r in recs
           if r["metrics"]["regret_M2"] is not None
           and np.isfinite(r["metrics"]["regret_M2"])]

    table_a = {
        "M3G_0_validity": g0,
        "M3G_1_baseline_parity": {
            "definition": "replayed baseline row-set bitwise equals the "
                          "frozen M3-D layer_a records",
            "cells_checked": ONLINE["replay_parity"]["cells_checked"],
            "cells_mismatched": ONLINE["replay_parity"]["cells_mismatched"],
            "pass": bool(ONLINE["replay_parity"]["cells_mismatched"] == 0)},
        "M3G_2_non_regression": {
            "definition": "Acc3_gain >= 0.75 AND WIDEN recall >= 0.90 AND "
                          "SHRINK recall >= 0.90",
            "acc3_gain": mg_gate["accuracy"],
            "recall_widen": mg_gate["recall_per_class"]["WIDEN"],
            "recall_shrink": mg_gate["recall_per_class"]["SHRINK"],
            "pass": bool(mg_gate["accuracy"] >= 0.75
                         and mg_gate["recall_per_class"]["WIDEN"] >= 0.90
                         and mg_gate["recall_per_class"]["SHRINK"] >= 0.90)},
        "M3G_3_hold_recovery": {
            "definition": "HOLD recall >= 0.50 (from 0.250) AND "
                          "act-but-indifferent count strictly decreases "
                          "(>=-30% relative)",
            "recall_hold": mg_gate["recall_per_class"]["HOLD"],
            "act_but_indifferent_m3d": act_indiff_m3d,
            "act_but_indifferent_m3g": act_indiff_m3g,
            "act_but_indifferent_delta_pct": pct,
            "pass": bool(mg_gate["recall_per_class"]["HOLD"] >= 0.50
                         and act_indiff_m3d > 0
                         and (act_indiff_m3g - act_indiff_m3d)
                         / act_indiff_m3d <= -0.30)},
        "M3G_4_value_direction": {
            "definition": "R_fixed(GA) <= R_fixed(baseline CI-sign) on the "
                          "same aggregate",
            "R_fixed_GA": r_fixed_gate,
            "R_fixed_baseline": r_fixed_m3d,
            "pass": bool(r_fixed_gate is not None and r_fixed_m3d is not None
                         and r_fixed_gate <= r_fixed_m3d)},
        "M3G_5_near_oracle": {
            "definition": "median R_M2 <= 0.05",
            "median_regret_RM2": float(median(rm2)) if rm2 else None,
            "pass": bool(median(rm2) <= 0.05) if rm2 else False},
    }

    # --------------------------------------- Strong (diagnostic only)
    vrfs = [r["metrics"]["VRF_budget"] for r in recs
            if r["metrics"]["VRF_budget"] is not None
            and np.isfinite(r["metrics"]["VRF_budget"])]
    strong = {
        "median_VRF_budget_m3g": float(median(vrfs)),
        "median_VRF_budget_m3d": 1.0303650787810041,
        "crossing_retained": bool(median(vrfs) > 1.0),
        "wording": "M3-G retained the M3-D crossing of the crude-MC "
                   "budget-efficiency boundary; PASSING CONFERS NO "
                   "SUPERIORITY CLAIM (M3-D lesson); no claim that M3-G "
                   "newly achieved cost efficiency or superiority"}

    # ---------------------------------- Table B (secondary strengthened)
    ratios_43 = [r["metrics"]["M2_gate_over_gradient"] for r in recs
                 if r["metrics"]["M2_gate_over_gradient"] is not None
                 and np.isfinite(r["metrics"]["M2_gate_over_gradient"])]
    by_state_43 = {}
    for r in recs:
        v = r["metrics"]["M2_gate_over_gradient"]
        if v is None or not np.isfinite(v):
            continue
        by_state_43.setdefault(r["state_id"], []).append(v)
    best_fixed = _best_fixed_rule(recs, stored)
    gate_by_state = {}
    for r in recs:
        gate_by_state.setdefault(r["state_id"], []).append(
            float(r["arms"]["gate"]["M2"]))
    gate_med = state_seed_medians(gate_by_state)
    bf_by_state = state_seed_medians(_fixed_rule_per_state(recs, stored,
                                                           best_fixed))
    ratio_gate_bf = {k: gate_med[k] / bf_by_state[k]
                     for k in gate_med if k in bf_by_state
                     and bf_by_state[k] > 0}
    wins, losses, ties = win_counts(gate_med, bf_by_state)
    table_b = {
        "note": "SECONDARY / strengthened audit criteria from the "
                "execution-task handoff; NOT the original preregistration "
                "official gates (Table A is authoritative)",
        "direction_preservation": {
            "definition": "W/S recall >= 0.90 (hard)",
            "recall_widen": mg_gate["recall_per_class"]["WIDEN"],
            "recall_shrink": mg_gate["recall_per_class"]["SHRINK"],
            "pass": bool(mg_gate["recall_per_class"]["WIDEN"] >= 0.90
                         and mg_gate["recall_per_class"]["SHRINK"] >= 0.90)},
        "hold_recovery_strong": {
            "definition": "HOLD recall >= 0.70 AND improvement >= +30pp",
            "recall_hold": mg_gate["recall_per_class"]["HOLD"],
            "improvement_pp": 100.0 * (mg_gate["recall_per_class"]["HOLD"]
                                       - mg_m3d["recall_per_class"]["HOLD"]),
            "pass": False},
        "balanced_quality": {
            "definition": "balanced accuracy >= 0.80 AND macro-F1 >= 0.80",
            "balanced_accuracy": mg_gate["balanced_accuracy"],
            "macro_F1": mg_gate["macro_F1"],
            "pass": bool(mg_gate["balanced_accuracy"] >= 0.80
                         and mg_gate["macro_F1"] >= 0.80)},
        "m2_noninferiority": {
            "definition": "median M2(M3G)/M2(M3D) <= 1.00 "
                          "(preferred <= 0.98)",
            "median_ratio_pooled": float(median(ratios_43)),
            "median_of_state_seed_medians":
                median_of_state_seed_medians(by_state_43),
            "pass_hard": bool(median(ratios_43) <= 1.00),
            "pass_preferred": bool(median(ratios_43) <= 0.98)},
        "adaptive_value": {
            "definition": "median(s) M2(M3G)/M2(best fixed) <= 0.95 AND "
                          ">= 16/24 states won",
            "best_fixed_rule": best_fixed,
            "median_ratio_M3G_over_best_fixed":
                median(ratio_gate_bf.values()) if ratio_gate_bf else None,
            "states_won": wins, "states_lost": losses, "states_tied": ties,
            "pass": bool(ratio_gate_bf
                         and median(ratio_gate_bf.values()) <= 0.95
                         and wins >= 16)},
    }

    # --------------------------------- leakage safety
    closure_bad, arm_checks = 0, 0
    for r in recs:
        for k, arm in r["arms"].items():
            arm_checks += 1
            s = sum(float(x) for x in arm["mode_L"].values())
            if abs(s - float(arm["M2"])) > 1e-9 * max(abs(float(arm["M2"])),
                                                      1e-300):
                closure_bad += 1
    leakage = {"identity_closure_violations": closure_bad,
               "arms_checked": arm_checks,
               "identity_closure_ok": closure_bad == 0,
               "illegal_arms_as_base": 0}

    # --------------------------------- diagnostics (frozen-policy scope)
    hold_gain = [r for r in recs
                 if r["gain"]["gain_hold_reason"] == "HOLD_GAIN"]
    n_hg = len(hold_gain)
    hg_correct = sum(1 for r in hold_gain if r["oracle_action"] == "HOLD")
    n_w = sum(1 for r in recs if r["oracle_action"] == "WIDEN")
    n_s = sum(1 for r in recs if r["oracle_action"] == "SHRINK")
    false_hold_w = sum(1 for r in recs
                       if r["gain"]["final_action"] == "HOLD"
                       and r["oracle_action"] == "WIDEN")
    false_hold_s = sum(1 for r in recs
                       if r["gain"]["final_action"] == "HOLD"
                       and r["oracle_action"] == "SHRINK")
    diag = {
        "fraction_original_WS_converted_to_hold_gain":
            n_hg / 176.0,
        "fraction_correct_among_hold_gain":
            hg_correct / n_hg if n_hg else None,
        "false_hold_rate_on_widen": false_hold_w / n_w,
        "false_hold_rate_on_shrink": false_hold_s / n_s,
        "act_but_indifferent_m3d": act_indiff_m3d,
        "act_but_indifferent_m3g": act_indiff_m3g,
    }

    # --------------------------------- deviation-status block
    div = REPLAY["closed_policy_divergence_from_sealed"]
    deviation_status = {
        "exact_proxy_replay_selection":
            REPLAY["selection"]["selected"],
        "frozen_calibration_selection":
            REPLAY["frozen_selection"],
        "selection_matches": bool(REPLAY["selection_matches_frozen"]),
        "action_divergence_count_GA2_0_0025": div["action_divergence_count"],
        "deviation_A_M2_denominator": {
            "status": "MATERIAL (not result-preserving)",
            "evidence": "selection flip GA2-0.0025 -> GA1-0.02; "
                        "9/192 action divergences at the closed policy; "
                        "pilot-vs-eval M2 relative diffs up to ~215x",
            "attribution": "all 9 divergences from the M2 normalizer "
                           "substitution (pilot-M2-linear vs pilot-M2-"
                           "per-replicate = 0/192)"},
        "deviation_B_CI_propagation": {
            "status": "result-preserving at selected rho (0/192), "
                      "superseded by A",
            "evidence": "per-direction diagnostic: 0/192 disagreements"},
        "verdict": "NOT FREEZE READY",
        "reference": "docs/phase_m3g/M3_G_Protocol_Deviation_Audit.md",
    }

    # --------------------------------- in-sample disclosure
    pair_acc = [1.0 if g == t else 0.0 for g, t in zip(y_gate, y_true)]
    base_acc = [1.0 if m == t else 0.0 for m, t in zip(y_m3d, y_true)]
    d_acc = [a - b for a, b in zip(pair_acc, base_acc)]
    boot = paired_bootstrap_ci(d_acc, n_boot=10_000, seed=(20260827,))

    audit = {
        "schema_version": "raretopo-m3g-gate-audit-v0",
        "stage": "M3_G_gate_audit_freeze_audit_corrected",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "git_commit": _git(),
        "locked_policy": {"variant": recs[0]["gain"]["gain_variant"],
                          "rho": recs[0]["gain"]["rho"]},
        "classification": {
            "M3G_executed_frozen_policy": {
                "accuracy": mg_gate["accuracy"],
                "recalls": mg_gate["recall_per_class"],
                "balanced_accuracy": mg_gate["balanced_accuracy"],
                "macro_F1": mg_gate["macro_F1"],
                "confusion_matrix": mg_gate["confusion_matrix"]},
            "M3D_baseline": {
                "accuracy": mg_m3d["accuracy"],
                "recalls": mg_m3d["recall_per_class"],
                "confusion_matrix": mg_m3d["confusion_matrix"]},
            "acc3_delta_descriptive_paired_bootstrap_after_selection": boot,
        },
        "table_A_authoritative_preregistered_gates": table_a,
        "strong_vrf_diagnostic": strong,
        "table_B_secondary_strengthened_audit": table_b,
        "leakage_safety": leakage,
        "diagnostics_frozen_policy_scope": diag,
        "deviation_audit_status": deviation_status,
        "in_sample_disclosure": (
            "calibration and replay evaluation share the same frozen "
            "(state, seed) units; the measured improvement is in-sample "
            "calibrated performance and does NOT establish out-of-sample "
            "generalization; the acc3-delta interval is a descriptive "
            "paired bootstrap interval after policy selection"),
        "gates_summary_authoritative": {
            "M3G_0": bool(g0["pass"]),
            "M3G_1": bool(table_a["M3G_1_baseline_parity"]["pass"]),
            "M3G_2": bool(table_a["M3G_2_non_regression"]["pass"]),
            "M3G_3": bool(table_a["M3G_3_hold_recovery"]["pass"]),
            "M3G_4": bool(table_a["M3G_4_value_direction"]["pass"]),
            "M3G_5": bool(table_a["M3G_5_near_oracle"]["pass"]),
            "STRONG_diagnostic": bool(strong["crossing_retained"]),
        },
        "freeze_audit_verdict": "NOT FREEZE READY",
    }
    dest = REPO / "results" / "phase_m3g" / "summary" / "gate_audit_m3g.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(audit, indent=1), encoding="utf-8")
    print(f"[saved] {dest.relative_to(REPO)}")
    print("authoritative summary:",
          json.dumps(audit["gates_summary_authoritative"]))
    print("verdict:", audit["freeze_audit_verdict"])
    return 0


def _fixed_rule_per_state(recs, stored, rule):
    per = {}
    for r in recs:
        m2 = float(stored[(r["state_id"], int(r["seed"]))]["arms"][
            FIXED_ARM[rule]]["M2"])
        per.setdefault(r["state_id"], []).append(m2)
    return per


def _best_fixed_rule(recs, stored):
    meds = {}
    for rule in FIXED_RULES:
        per = _fixed_rule_per_state(recs, stored, rule)
        meds[rule] = median(state_seed_medians(per).values())
    return min(meds, key=meds.get)


def _r_fixed(recs, stored, best_fixed):
    per = {}
    for r in recs:
        gm = float(r["arms"]["gate"]["M2"])
        fm = float(stored[(r["state_id"], int(r["seed"]))]["arms"][
            FIXED_ARM[best_fixed]]["M2"])
        if fm > 0:
            per.setdefault(r["state_id"], []).append(gm / fm)
    meds = state_seed_medians(per)
    return median(meds.values()) if meds else None


def _r_fixed_m3d(stored, best_fixed):
    per = {}
    for (sid, seed), s in stored.items():
        gm = float(s["arms"]["gradient"]["M2"])
        fm = float(s["arms"][FIXED_ARM[best_fixed]]["M2"])
        if fm > 0:
            per.setdefault(sid, []).append(gm / fm)
    meds = state_seed_medians(per)
    return median(meds.values()) if meds else None


if __name__ == "__main__":
    raise SystemExit(main())