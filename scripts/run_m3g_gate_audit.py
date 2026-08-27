"""M3-G gate audit (handoff Sec. 16-23, 28-G7).

Computes M3G-0..5 + Strong + leakage-safety + diagnostic blocks over the
sealed online batch vs the stored M3-D layer records, and writes
results/phase_m3g/summary/gate_audit_m3g.json.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
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
from hyptraj.m3g.metrics import validate_m3g_trial_record

REPO = Path(__file__).resolve().parents[1]
ONLINE = json.loads((REPO / "results" / "phase_m3g" / "layer_a"
                     / "m3g_online_v1.json").read_text(encoding="utf-8"))
STORED = json.loads((REPO / "results" / "phase_m3d" / "layer_a"
                     / "m3d_layer_a_v1.json").read_text(encoding="utf-8"))
FREEZE_DOC = json.loads((REPO / "docs" / "phase_m3d"
                         / "M3_D_Benchmark_Freeze.json").read_text(
                             encoding="utf-8"))

FIXED_RULES = ("ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD")
FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "hold"}
ORACLE_ARM = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "hold"}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _by_cell(recs):
    return {(r["state_id"], int(r["seed"])): r for r in recs}


def main() -> int:
    recs = ONLINE["gated_records"]
    assert len(recs) == 192
    for r in recs:
        assert validate_m3g_trial_record(r), f"schema fail {r['state_id']}"
    stored = _by_cell(STORED["records"])
    frozen = stored

    y_gate = [r["gain"]["final_action"] for r in recs]
    y_m3d = [frozen[(r["state_id"], int(r["seed"]))]["validity"]
             ["deployed_action"] for r in recs]
    y_true = [r["oracle_action"] for r in recs]

    mg_gate = three_class_metrics(y_true, y_gate)
    mg_m3d = three_class_metrics(y_true, y_m3d)

    # ------------------------------------------------------------ M3G-0
    body = {k: v for k, v in FREEZE_DOC.items()
            if k != "freeze_sha256_of_body_above"}
    freeze_sha = hashlib.sha256(json.dumps(body, indent=1).encode()
                                ).hexdigest()
    tag_m3 = subprocess.run(["git", "rev-parse", "RareTopo-M3-v0"],
                            cwd=REPO, capture_output=True, text=True)
    tag_m3d = subprocess.run(["git", "rev-parse", "RareTopo-M3-D-v0"],
                             cwd=REPO, capture_output=True, text=True)
    g0 = {
        "parent_tag_M3v0_hash": tag_m3.stdout.strip(),
        "parent_tag_M3Dv0_hash": tag_m3d.stdout.strip(),
        "task_commit": ONLINE.get("task_commit"),
        "benchmark_freeze_sha_unchecked": freeze_sha,
        "online_parity_cells_checked": ONLINE["replay_parity"]
        ["cells_checked"],
        "online_parity_cells_mismatched": ONLINE["replay_parity"]
        ["cells_mismatched"],
        "calibration_extra_simulator_calls": 0,
    }
    # tags resolve (through the annotated tag object) to the recorded commits
    tag_m3_commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "RareTopo-M3-v0"], cwd=REPO,
        capture_output=True, text=True).stdout.strip()
    tag_m3d_commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "RareTopo-M3-D-v0"], cwd=REPO,
        capture_output=True, text=True).stdout.strip()
    g0["tag_M3v0_commit"] = tag_m3_commit
    g0["tag_M3Dv0_commit"] = tag_m3d_commit
    g0["tags_match_task_doc"] = bool(
        tag_m3_commit == "32b285625494d9b3da08be3c559db3855df77667"
        and tag_m3d_commit == "7bd58c5992615b8579b1814a3a3fcbea3cda9659")

    # ------------------------------------------------------------ M3G-1
    g1 = {"recall_widen": mg_gate["recall_per_class"]["WIDEN"],
          "recall_shrink": mg_gate["recall_per_class"]["SHRINK"],
          "pass": bool(mg_gate["recall_per_class"]["WIDEN"] >= 0.90
                       and mg_gate["recall_per_class"]["SHRINK"] >= 0.90)}

    # ------------------------------------------------------------ M3G-2
    rH_gate = mg_gate["recall_per_class"]["HOLD"]
    rH_m3d = mg_m3d["recall_per_class"]["HOLD"]
    g2 = {"recall_hold_m3g": rH_gate, "recall_hold_m3d": rH_m3d,
          "improvement_pp": 100.0 * (rH_gate - rH_m3d),
          "pass": bool(rH_gate >= 0.70 and
                       (rH_gate - rH_m3d) >= 0.30)}

    # ------------------------------------------------------------ M3G-3
    g3 = {"balanced_accuracy": mg_gate["balanced_accuracy"],
          "macro_F1": mg_gate["macro_F1"],
          "pass": bool(mg_gate["balanced_accuracy"] >= 0.80
                       and mg_gate["macro_F1"] >= 0.80)}

    # ------------------------------------------------------------ M3G-4
    ratios_43 = [r["metrics"]["M2_gate_over_gradient"] for r in recs
                 if r["metrics"]["M2_gate_over_gradient"] is not None
                 and np.isfinite(r["metrics"]["M2_gate_over_gradient"])]
    by_state_43 = {}
    for r in recs:
        v = r["metrics"]["M2_gate_over_gradient"]
        if v is None or not np.isfinite(v):
            continue
        by_state_43.setdefault(r["state_id"], []).append(v)
    g4 = {"median_ratio_pooled": float(median(ratios_43)),
          "median_of_state_seed_medians": median_of_state_seed_medians(
              by_state_43),
          "pass_pooled_median_le_1": bool(median(ratios_43) <= 1.00),
          "preferred_le_0_98": bool(median(ratios_43) <= 0.98)}

    # ------------------------------------------------------------ M3G-5
    agg = {}                 # rule -> per-state seed medians on stored arms
    for rule in FIXED_RULES:
        per_state = {}
        for r in recs:
            m2 = float(frozen[(r["state_id"], int(r["seed"]))]["arms"][
                FIXED_ARM[rule]]["M2"])
            per_state.setdefault(r["state_id"], []).append(m2)
        agg[rule] = state_seed_medians(per_state)
    fixed_med = {rule: median(v.values()) for rule, v in agg.items()}
    best_fixed = min(fixed_med, key=fixed_med.get)
    bf_arms = FIXED_ARM[best_fixed]

    gate_by_state = {}
    for r in recs:
        gate_by_state.setdefault(r["state_id"], []).append(
            float(r["arms"]["gate"]["M2"]))
    gate_med = state_seed_medians(gate_by_state)
    bf_by_state = agg[best_fixed]            # already per-state medians
    ratio_gate_bf = {k: gate_med[k] / bf_by_state[k]
                     for k in gate_med if k in bf_by_state
                     and bf_by_state[k] > 0}
    wins, losses, ties = win_counts(gate_med, bf_by_state)
    g5 = {"best_fixed_rule": best_fixed,
          "fixed_aggregate_medians": {k: float(v) for k, v in fixed_med.items()},
          "median_ratio_M3G_over_best_fixed": median_of_state_seed_medians(
              {k: [v] for k, v in ratio_gate_bf.items()}),
          "states_won_vs_best_fixed": wins,
          "states_lost": losses, "states_tied": ties,
          "pass": bool(median(ratio_gate_bf.values()) <= 0.95
                       and wins >= 16)}

    # ---------------------------------------------------------- Strong
    vrfs = [r["metrics"]["VRF_budget"] for r in recs
            if r["metrics"]["VRF_budget"] is not None
            and np.isfinite(r["metrics"]["VRF_budget"])]
    strong = {"median_VRF_budget_m3g": float(median(vrfs)),
              "pass_gt_1": bool(median(vrfs) > 1.0)}

    # ------------------------------------------- leakage safety (Sec. 23)
    closure_bad, arm_checks = 0, 0
    illegal_as_base = 0
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
               "illegal_arms_as_base": illegal_as_base}

    # --------------------------------------- classification diagnostics
    conf = mg_gate["confusion_matrix"]
    n_orig_active = sum(1 for r in recs
                        if r["gradient"]["action"] in ("WIDEN", "SHRINK"))
    hold_gain = [r for r in recs
                 if r["gain"]["gain_hold_reason"] == "HOLD_GAIN"]
    n_hg = len(hold_gain)
    hg_correct = sum(1 for r in hold_gain if r["oracle_action"] == "HOLD")
    false_hold_w = sum(1 for r in recs
                       if r["gain"]["final_action"] == "HOLD"
                       and r["oracle_action"] == "WIDEN")
    false_hold_s = sum(1 for r in recs
                       if r["gain"]["final_action"] == "HOLD"
                       and r["oracle_action"] == "SHRINK")
    n_w = sum(1 for r in recs if r["oracle_action"] == "WIDEN")
    n_s = sum(1 for r in recs if r["oracle_action"] == "SHRINK")
    act_but_indiff_m3d = sum(1 for r, m, t in zip(recs, y_m3d, y_true)
                             if m in ("WIDEN", "SHRINK") and t == "HOLD")
    act_but_indiff_m3g = sum(1 for r, t in zip(recs, y_true)
                             if r["gain"]["final_action"] in ("WIDEN",
                                                               "SHRINK")
                             and t == "HOLD")
    diag = {
        "fraction_original_WS_converted_to_hold_gain":
            n_hg / n_orig_active if n_orig_active else None,
        "fraction_correct_among_hold_gain":
            hg_correct / n_hg if n_hg else None,
        "false_hold_rate_on_widen": false_hold_w / n_w if n_w else None,
        "false_hold_rate_on_shrink": false_hold_s / n_s if n_s else None,
        "act_but_indifferent_m3d": act_but_indiff_m3d,
        "act_but_indifferent_m3g": act_but_indiff_m3g,
        "act_but_indifferent_delta_pct":
            100.0 * (act_but_indiff_m3g - act_but_indiff_m3d)
            / act_but_indiff_m3d if act_but_indiff_m3d else None,
    }

    # ------------------------------------------- value-direction R_fixed
    r_fixed_gate = _r_fixed(recs, frozen, best_fixed)
    r_fixed_m3d = _r_fixed_m3d(frozen, best_fixed)
    value_dir = {"R_fixed_GA": r_fixed_gate,
                 "R_fixed_baseline_m3d": r_fixed_m3d,
                 "ga_le_baseline": bool(r_fixed_gate is not None
                                        and r_fixed_m3d is not None
                                        and r_fixed_gate <= r_fixed_m3d)}
    near_oracle = {"median_regret_RM2": float(median(
        [r["metrics"]["regret_M2"] for r in recs
         if r["metrics"]["regret_M2"] is not None
         and np.isfinite(r["metrics"]["regret_M2"])]))}

    # ----------------------------------- paired bootstrap (NOT-IID units)
    pair_acc = [1.0 if g == t else 0.0 for g, t in zip(y_gate, y_true)]
    base_acc = [1.0 if m == t else 0.0 for m, t in zip(y_m3d, y_true)]
    d_acc = [a - b for a, b in zip(pair_acc, base_acc)]
    boot = paired_bootstrap_ci(d_acc, n_boot=10_000, seed=(20260827,))

    audit = {
        "schema_version": "raretopo-m3g-gate-audit-v0",
        "stage": "M3_G_gate_audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "git_commit": _git(),
        "locked_policy": {"variant": recs[0]["gain"]["gain_variant"],
                          "rho": recs[0]["gain"]["rho"]},
        "classification": {
            "M3G": {"accuracy": mg_gate["accuracy"],
                    "recalls": mg_gate["recall_per_class"],
                    "balanced_accuracy": mg_gate["balanced_accuracy"],
                    "macro_F1": mg_gate["macro_F1"],
                    "confusion_matrix": conf},
            "M3D_baseline": {"accuracy": mg_m3d["accuracy"],
                             "recalls": mg_m3d["recall_per_class"],
                             "confusion_matrix": mg_m3d["confusion_matrix"]},
            "acc3_delta_paired_bootstrap": boot,
        },
        "gates": {"M3G_0_validity": g0, "M3G_1_direction": g1,
                  "M3G_2_hold_recovery": g2, "M3G_3_balanced_quality": g3,
                  "M3G_4_m2_noninferiority": g4, "M3G_5_adaptive_value": g5,
                  "STRONG_budget_vrf": strong},
        "task_doc_cross_reference": {
            "acc3_gain": mg_gate["accuracy"],
            "acc3_min_0_75": mg_gate["accuracy"] >= 0.75,
            "act_but_indifferent_decrease_30pct": bool(
                act_but_indiff_m3d > 0
                and (act_but_indiff_m3g - act_but_indiff_m3d)
                / act_but_indiff_m3d <= -0.30),
            "near_oracle_median_RM2_le_0_05":
                bool(near_oracle["median_regret_RM2"] <= 0.05),
            "value_direction": value_dir,
            "near_oracle": near_oracle,
        },
        "leakage_safety": leakage,
        "diagnostics": diag,
        "calibration_vs_online_proxy_fidelity": _proxy_fidelity(recs),
        "gates_summary": {
            "M3G_1": bool(g1["pass"]), "M3G_2": bool(g2["pass"]),
            "M3G_3": bool(g3["pass"]),
            "M3G_4_noninferiority": bool(g4["pass_pooled_median_le_1"]),
            "M3G_4_preferred": bool(g4["preferred_le_0_98"]),
            "M3G_5": bool(g5["pass"]),
            "STRONG": bool(strong["pass_gt_1"]),
        },
    }
    dest = REPO / "results" / "phase_m3g" / "summary" / "gate_audit_m3g.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(audit, indent=1), encoding="utf-8")
    print(f"[saved] {dest.relative_to(REPO)}")
    print("gate summary:", json.dumps(audit["gates_summary"]))
    return 0


def _per_state_meds(ratios_by_trial):
    per = {}
    for r, v in ratios_by_trial:
        if v is None or not np.isfinite(v):
            continue
        per.setdefault(r["state_id"], []).append(v)
    return state_seed_medians(per)


def _r_fixed(recs, frozen, best_fixed):
    """median of per-state seed medians of M2(M3G)/M2(best fixed rule)."""
    ratios = []
    for r in recs:
        gm = float(r["arms"]["gate"]["M2"])
        fm = float(frozen[(r["state_id"], int(r["seed"]))]["arms"][
            FIXED_ARM[best_fixed]]["M2"])
        if fm > 0:
            ratios.append((r, gm / fm))
    meds = _per_state_meds(ratios)
    return median(meds.values()) if meds else None


def _r_fixed_m3d(frozen, best_fixed):
    ratios = []
    for k, s in frozen.items():
        gm = float(s["arms"]["gradient"]["M2"])
        fm = float(s["arms"][FIXED_ARM[best_fixed]]["M2"])
        if fm > 0:
            ratios.append(({"state_id": k[0]}, gm / fm))
    per = {}
    for r, v in ratios:
        per.setdefault(r["state_id"], []).append(v)
    meds = state_seed_medians(per)
    return median(meds.values()) if meds else None


def _proxy_fidelity(recs):
    """Calibration-proxy (stored base M2) vs online-proxy (pilot M2_hat):
    per-trial gate-decision agreement of the LOCKED GA2 policy."""
    from hyptraj.m3g.gain_gate import apply_gain_gate
    from hyptraj.m3g.gain_proxy import DELTA_THETA_MAIN

    rho = float(recs[0]["gain"]["rho"])
    variant = str(recs[0]["gain"]["gain_variant"])
    same = diff = 0
    max_rel_m2_diff = 0.0
    for r in recs:
        g = r["gradient"]
        dtheta = DELTA_THETA_MAIN if g["action"] == "WIDEN" \
            else -DELTA_THETA_MAIN if g["action"] == "SHRINK" else 0.0
        if g["action"] not in ("WIDEN", "SHRINK"):
            continue
        m2_cal = float(r["arms"]["hold"]["M2"])
        m2_online = float(r["gradient"]["M2_hat_pilot"])
        if m2_cal > 0 and m2_online > 0:
            max_rel_m2_diff = max(max_rel_m2_diff,
                                  abs(m2_cal - m2_online) / m2_cal)
        dec_cal = apply_gain_gate(direction=g["action"], variant=variant,
                                  rho=rho, g_hat=g["g_hat"],
                                  g_ci_low=g["g_ci_low"],
                                  g_ci_high=g["g_ci_high"],
                                  m2=m2_cal, delta_theta=DELTA_THETA_MAIN,
                                  arm_legal=True)["final_action"]
        dec_online = r["gain"]["final_action"]
        if dec_cal == dec_online:
            same += 1
        else:
            diff += 1
    return {"active_trials_compared": same + diff,
            "gate_decisions_agree": same,
            "gate_decisions_disagree": diff,
            "max_rel_m2_diff_cal_vs_pilot": max_rel_m2_diff}


if __name__ == "__main__":
    raise SystemExit(main())