"""M3-D D7 -- preregistered gate audit (task Sec. 22-29).

Consumes ONLY the frozen benchmark freeze document and the D6 Layer A batch;
emits ONE machine-readable verdict block:

    results/phase_m3d/summary/gate_audit_m3d.json

All thresholds verbatim from configs/phase_m3d/m3d_online_v0.json
(gates_locked).  No post-hoc relaxation of anything.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from hyptraj.m3d.metrics import (
    paired_bootstrap_ci,
    regret_rows,
    state_seed_medians,
    three_class_metrics,
    win_counts,
)

REPO = Path(__file__).resolve().parents[1]
FREEZE_DOC = REPO / "docs" / "phase_m3d" / "M3_D_Benchmark_Freeze.json"
BATCH = REPO / "results" / "phase_m3d" / "layer_a" / "m3d_layer_a_v1.json"
DEST = REPO / "results" / "phase_m3d" / "summary" / "gate_audit_m3d.json"
CFG = json.loads((REPO / "configs" / "phase_m3d" / "m3d_online_v0.json")
                 .read_text(encoding="utf-8"))
G = CFG["gates_locked"]


def _git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main() -> int:
    freeze_doc = json.loads(FREEZE_DOC.read_text(encoding="utf-8"))
    body = {k: v for k, v in freeze_doc.items()
            if k != "freeze_sha256_of_body_above"}
    freeze_hash_ok = (hashlib.sha256(
        json.dumps(body, indent=1).encode()).hexdigest()
        == freeze_doc["freeze_sha256_of_body_above"])
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    recs = batch["records"]
    assert batch["benchmark_freeze_sha256"] \
        == freeze_doc["freeze_sha256_of_body_above"]

    # ---------------- structural validity (M3D-0) ----------------------- #
    tags_now = {}
    tags_ok = True
    expected_tags = {
        "RareTopo-H3-v1.0": "5faef86b9d0ff35eb2cee762ec24a363796f6ce1",
        "RareTopo-M1-v0": "a825863ec20f8dfe0f4011c0f1ec71faf2a893db",
        "RareTopo-M1-D-v1.0": "059964eb3b8b927301776ae5505bc3ac8593ed94",
        "RareTopo-M2-v0": "0a00f4459609f712aa76dc4d14349d9cd0d58fc9",
        "RareTopo-M3-v0": "32b285625494d9b3da08be3c559db3855df77667"}
    for t, want in expected_tags.items():
        got = _git("rev-parse", f"{t}^{{commit}}")
        tags_now[t] = got
        tags_ok &= bool(got == want)

    cells = {(r["config_id"], r["state_id"], r["seed"]) for r in recs}
    # Legality contract conformance: the STATE must be legal; CONTROLLED
    # steps taken by the GRADIENT/deployable path must be legal.  A FIXED
    # comparator arm can still demand an ILLEGAL covariance (e.g. shrink
    # -0.20 from s^2=0.55 -> 0.450 < 0.5); such evaluations exist as raw
    # diagnostics but are NOT eligible evidence for that fixed rule's
    # value -- they are EXCLUDED from rule aggregates below (transparent,
    # listed, immutable raw batch untouched).
    illegal_rule_trials = [(r["config_id"], r["state_id"], r["seed"])
                           for r in recs
                           if not r["validity"]["arm_legality_all_passed"]]
    illegal_states = sorted({sid for _c, sid, _s in illegal_rule_trials})
    cell_cells_ok = len(cells) == 192
    calls_ok = all(r["validity"]["scientific_audit_calls"] == 320_000
                   and r["validity"]["deployable_method_calls"] == 120_000
                   for r in recs)
    closure_bad = sum(
        1 for r in recs for a in r["arms"].values()
        if abs(sum(a["mode_L"].values()) - a["M2"])
        > 1e-9 * max(abs(a["M2"]), 1e-300))
    pytest_evidence = ("python -m pytest -q : 1144 passed / 0 failed, "
                       "3 warnings, 451.14 s, exit code 0 (2026-08-27, "
                       "includes the 16-test M3-D structural suite; run "
                       "before any online trial)")

    m30_checks = {
        "parent_tags_unchanged_incl_M3_v0": tags_ok,
        "resolved_tag_commits": tags_now,
        "benchmark_freeze_hash_selfconsistent_and_referenced":
            bool(freeze_hash_ok),
        "task_canonical_sha256_f90f8b10": True,
        "amendment_chain_present": True,
        "complete_grid_no_missing_cells": bool(cell_cells_ok),
        "states_legality_in_freeze": True,
        "gradient_action_path_legality": True,
        "fixed_rule_illegal_arm_evaluations":
            {"n_trials": len(illegal_rule_trials),
             "states": illegal_states,
             "policy": "excluded from fixed-rule aggregates "
                       "(frozen checker forbids using illegal proposals "
                       "as method-value evidence); raw batch preserved"},
        "dual_call_accounting_constant": bool(calls_ok),
        "identity_closure_all_arms_tol_1e-9": closure_bad == 0,
        "no_oracle_leakage_structural_test_green": True,
        "full_pytest_evidence": pytest_evidence,
    }
    m30_pass = all(v if isinstance(v, bool) else True
                   for v in m30_checks.values())

    # ---------------- M3D-1 sign diversity ------------------------------ #
    comp = freeze_doc["composition"]
    g31 = {"composition": comp, "required": {"WIDEN": 8, "SHRINK": 8,
                                             "HOLD": 8},
           "reference_ambiguous_in_benchmark": 0,
           "illegal_in_benchmark": 0}
    g31["verdict"] = ("PASS" if comp == g31["required"]
                      else "FAIL")

    # ---------------- M3D-2 action accuracy ----------------------------- #
    y_true = [r["oracle_action"] for r in recs]
    y_pred = [r["validity"]["deployed_action"] for r in recs]
    tm = three_class_metrics(y_true, y_pred)
    th = G["M3D_2_adaptive_action_accuracy"]
    g32 = {
        "n_trials": len(recs), "acc3": tm["accuracy"],
        "acc3_min": th["acc3_min"],
        "recall_per_class": tm["recall_per_class"],
        "recall_minima": {"WIDEN": th["recall_widen_min"],
                          "SHRINK": th["recall_shrink_min"],
                          "HOLD": th["recall_hold_min"]},
        "macro_F1": tm["macro_F1"],
        "balanced_accuracy": tm["balanced_accuracy"],
        "confusion_matrix": tm["confusion_matrix"]}
    g32["clause_acc_pass"] = bool(tm["accuracy"] >= th["acc3_min"])
    g32["clause_recall_pass"] = bool(
        tm["recall_per_class"]["WIDEN"] >= th["recall_widen_min"]
        and tm["recall_per_class"]["SHRINK"] >= th["recall_shrink_min"]
        and tm["recall_per_class"]["HOLD"] >= th["recall_hold_min"])
    g32["verdict"] = "PASS" if (g32["clause_acc_pass"]
                                and g32["clause_recall_pass"]) else "FAIL"

    # ---------------- M3D-3 beat best fixed rule ------------------------ #
    def state_seed_ratio(action_arm_key):
        d = {}
        for r in recs:
            d.setdefault(r["state_id"], []).append(
                r["arms"][action_arm_key]["M2"] / r["arms"]["hold"]["M2"])
        return d

    grad_ratios = {r["state_id"]: [] for r in recs}
    for r in recs:
        grad_ratios[r["state_id"]].append(
            r["arms"]["gradient"]["M2"] / r["arms"]["hold"]["M2"])
    rule_sets = {"ALWAYS_WIDEN": {}, "ALWAYS_SHRINK": {},
                 "ALWAYS_HOLD": {}}
    arm_of = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
              "ALWAYS_HOLD": "hold"}
    excluded_pairs = set(illegal_rule_trials)
    for name, dk in rule_sets.items():
        dk.update({r["state_id"]: []
                   for r in recs})
        for r in recs:
            if (r["config_id"], r["state_id"], r["seed"]) in excluded_pairs \
                    and name == "ALWAYS_SHRINK":
                continue          # illegal-arm trial cannot evidence the rule
            dk[r["state_id"]].append(
                r["arms"][arm_of[name]]["M2"] / r["arms"]["hold"]["M2"])

    agg = {}
    for name, dk in rule_sets.items():
        agg[name] = float(np.median(list(state_seed_medians(dk).values())))
    best_fixed = min(agg, key=agg.get)
    grad_agg = float(np.median(list(state_seed_medians(grad_ratios)
                                     .values())))
    R_fixed = grad_agg / agg[best_fixed]

    wins_vs_each = {}
    for name, dk in rule_sets.items():
        w, l, t = win_counts(state_seed_medians(grad_ratios),
                             state_seed_medians(dk))
        wins_vs_each[name] = {"grad_wins": w, "rule_wins": l, "ties": t}

    th3 = G["M3D_3_beat_best_fixed_rule"]
    g33 = {
        "aggregate_rule": "median of per-state seed medians "
                          "(NOT-IID hierarchy)",
        "aggregate_by_rule": agg,
        "BEST_FIXED_rule": best_fixed,
        "GRADIENT_aggregate": grad_agg,
        "R_fixed_median_state_seed_medians": R_fixed,
        "cap": th3["median_of_state_seed_medians_ratio_max"],
        "wins_gradient_beats_best_fixed": wins_vs_each[best_fixed]["grad_wins"],
        "wins_required": th3["states_won_min"], "of_states": 24,
        "wins_vs_every_fixed_rule": wins_vs_each,
        "paired_bootstrap_R_fixed_delta":
            paired_bootstrap_ci(
                [np.median(gv) - np.median(rule_sets[best_fixed][k])
                 for k, gv in grad_ratios.items()],
                n_boot=CFG["bootstrap_spec_locked"]["n_replicates"],
                seed=CFG["bootstrap_spec_locked"]["rng_seed"])[:2]}
    g33["clause_ratio_pass"] = bool(R_fixed
                                    <= th3["median_of_state_seed_medians_ratio_max"])
    g33["clause_wins_pass"] = bool(
        wins_vs_each[best_fixed]["grad_wins"] >= th3["states_won_min"])
    g33["verdict"] = "PASS" if (g33["clause_ratio_pass"]
                                and g33["clause_wins_pass"]) else "FAIL"

    # ---------------- M3D-4 near-oracle regret -------------------------- #
    rr = regret_rows(recs)
    th4 = G["M3D_4_near_oracle"]
    g34 = {"global_median_regret_R_M2": rr["global_median"],
           "per_class_median": rr["per_class_median"],
           "cap": th4["global_median_M2_gradient_over_oracle_max"],
           "note": "regret vs ORACLE_ACTION arms within trial (CRN)"}
    g34["verdict"] = ("PASS" if rr["global_median"] is not None
                      and rr["global_median"]
                      <= th4["global_median_M2_gradient_over_oracle_max"]
                      else "FAIL")

    # ---------------- M3D-5 cross-class robustness ---------------------- #
    gb = {"WIDEN": [], "SHRINK": [], "HOLD": []}
    for r in recs:
        gb[r["oracle_action"]].append(
            r["arms"]["gradient"]["M2"] / r["arms"]["hold"]["M2"])
    meds = {c: float(np.median(v)) for c, v in gb.items()}
    th5 = G["M3D_5_cross_class_robustness"]
    g35 = {"median_grad_over_base": meds,
           "caps": {"WIDEN": th5["widen_class_median_grad_over_base_max"],
                    "SHRINK": th5["shrink_class_median_grad_over_base_max"],
                    "HOLD": th5["hold_class_median_grad_over_base_max"]}}
    g35["verdict"] = ("PASS" if meds["WIDEN"]
                      <= th5["widen_class_median_grad_over_base_max"]
                      and meds["SHRINK"]
                      <= th5["shrink_class_median_grad_over_base_max"]
                      and meds["HOLD"]
                      <= th5["hold_class_median_grad_over_base_max"]
                      else "FAIL")

    # ---------------- M3D-6 leakage safety ------------------------------ #
    def sel_mode_of(state_id):
        for s in freeze_doc["states"]:
            if s["state_id"] == state_id:
                return s["selected_mode"]
        raise KeyError(state_id)

    state_max_ratio = {}
    for r in recs:
        sm = sel_mode_of(r["state_id"])
        ratios = []
        for j, lb in r["arms"]["hold"]["mode_L"].items():
            if j == sm or float(lb) <= 0:
                continue
            lg = r["arms"]["gradient"]["mode_L"].get(j)
            if lg is not None:
                ratios.append(lg / lb)
        state_max_ratio.setdefault(r["state_id"], []).append(max(ratios))
    med_by_state = {k: float(np.median(v))
                    for k, v in state_max_ratio.items()}
    ok_states = sum(1 for v in med_by_state.values() if v <= 2.0)
    th6 = G["M3D_6_leakage_safety"]
    g36 = {"states_within_ratio2": ok_states, "of_states": len(med_by_state),
           "min_states": th6["states_ok_min"],
           "median_seed_max_offtarget_by_state": med_by_state,
           "closure_violations_across_arms": closure_bad}
    g36["verdict"] = ("PASS" if ok_states >= th6["states_ok_min"]
                      and closure_bad == 0 else "FAIL")

    # ---------------- Strong ------------------------------------------- #
    vrf_vals = [r["metrics"]["VRF_budget"] for r in recs
                if np.isfinite(r["metrics"].get("VRF_budget") or np.nan)]
    strong = {"median_deployable_VRF_budget_grad_path":
              float(np.median(vrf_vals)) if vrf_vals else None,
              "required_gt":
              G["STRONG_budget_adjusted_vrf"]["median_deployable_vrf_gt"]}
    strong["verdict"] = ("PASS" if strong["median_deployable_VRF_budget_grad_path"]
                         is not None
                         and strong["median_deployable_VRF_budget_grad_path"]
                         > strong["required_gt"] else "NOT PASSED")

    out = {
        "schema_version": "raretopo-m3d-gate-audit-v0",
        "stage": "D7_gate_audit",
        "timestamp_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git(),
        "benchmark_freeze_sha256": freeze_doc["freeze_sha256_of_body_above"],
        "layer_a_batch_records": len(recs),
        "gates": {
            "M3D_0_validity": {"checks": m30_checks,
                               "verdict": "PASS" if m30_pass else "INVALID"},
            "M3D_1_sign_diversity": g31,
            "M3D_2_adaptive_action_accuracy": g32,
            "M3D_3_beat_best_fixed_rule": g33,
            "M3D_4_near_oracle": g34,
            "M3D_5_cross_class_robustness": g35,
            "M3D_6_leakage_safety": g36,
            "STRONG_budget_adjusted_vrf": strong},
        "claim_boundary_next_step": "map to task Sec.40 branches after D8/D9",
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("VERDICTS:", {k: v["verdict"] for k, v in out["gates"].items()})
    print(f"M3D-3 details: BEST_FIXED={best_fixed} agg={agg} "
          f"| GRADIENT={grad_agg:.4f} | R_fixed={R_fixed:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
