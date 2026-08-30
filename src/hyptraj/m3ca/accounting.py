"""Artifact-only M3-CA accounting, reproduction and counterfactuals."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from .metrics import budget_vrf, log_ratio, median, proposal_vrf, unified_j


NOT_IDENTIFIABLE = "NOT IDENTIFIABLE FROM EXISTING ARTIFACTS"
ARM_BY_ACTION = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}
FIXED_ARM = {
    "ALWAYS_WIDEN": "widen",
    "ALWAYS_SHRINK": "shrink",
    "ALWAYS_HOLD": "base",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def state_key(state: dict) -> str:
    sk = state["state_key"]
    return f"{sk['config_id']}|{sk['s2']}"


def event_probabilities(m1d_freeze: dict) -> dict[str, float]:
    return {
        cfg["config_id"]: float(sum(
            float(mode["P_ref"]) for mode in cfg["modes"].values()
        ))
        for cfg in m1d_freeze["benchmark_configs"]
    }


def _reference_leakage_concentration(reference_entry: dict) -> float:
    values = [float(v["L"]) for v in
              reference_entry["arms"]["base"]["L_modes"].values()]
    total = sum(values)
    return float(max(values) / total) if total > 0.0 else float("nan")


def _mode_action(actions: list[str]) -> str:
    counts = Counter(actions)
    return sorted(counts, key=lambda a: (-counts[a], a))[0]


def _safe_spearman(x: list[float], y: list[float]) -> dict[str, Any]:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return {"rho": None, "p_value": None,
                "reason": "constant or insufficient input"}
    result = spearmanr(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return {"rho": float(result.statistic), "p_value": float(result.pvalue),
            "reason": None}


def _j_rows(value_states: list[dict], controller: dict,
            policy: str) -> list[list[float]]:
    rows = []
    for state in value_states:
        key = state_key(state)
        base = state["replicate_M2"]["base"]
        if policy in FIXED_ARM:
            m2 = state["replicate_M2"][FIXED_ARM[policy]]
        elif policy == "ORACLE":
            m2 = state["replicate_M2"][ARM_BY_ACTION[state["oracle_action"]]]
        else:
            recs = controller["states"][key]["replicates"]
            arm_field = "m3d_arm" if policy == "M3-D" else "v1_arm"
            m2 = [float(r["arm_M2"][r[arm_field]]) for r in recs]
        rows.append([log_ratio(m2_i, base_i) for m2_i, base_i in zip(m2, base)])
    return rows


def reproduce_headlines(value_states: list[dict], controller: dict,
                        lock: dict) -> dict:
    policies = ["ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD",
                "ORACLE", "M3-D", "M3-G-v1"]
    j = {p: unified_j(_j_rows(value_states, controller, p)) for p in policies}
    fixed = min(FIXED_ARM, key=j.get)
    g_oracle = j[fixed] - j["ORACLE"]
    g_v1 = j[fixed] - j["M3-G-v1"]
    capture = g_v1 / g_oracle

    state_vrf = []
    parity = True
    formula_max_abs_diff = 0.0
    for state in value_states:
        key = state_key(state)
        for rec in controller["states"][key]["replicates"]:
            parity = parity and rec["m3d_arm"] == rec["v1_arm"]
            arm = rec["v1_arm"]
            stored = float(rec["arm_VRF_budget"][arm])
            state_vrf.append((key, stored))
            # p_ref is not needed here: the exact formula check is performed
            # later with the per-config reference probability.
    per_state_medians = [median(v for k2, v in state_vrf if k2 == state_key(s))
                         for s in value_states]
    vrf_median = median(per_state_medians)

    anchors = lock["headline_anchors"]
    checks = {
        "best_fixed": fixed == lock["best_fixed"],
        "J_oracle": math.isclose(j["ORACLE"], anchors["J_oracle"],
                                 rel_tol=0.0, abs_tol=1e-8),
        "J_best_fixed": math.isclose(j[fixed], anchors["J_best_fixed"],
                                     rel_tol=0.0, abs_tol=1e-8),
        "oracle_headroom": math.isclose(g_oracle, anchors["oracle_headroom"],
                                        rel_tol=0.0, abs_tol=1e-8),
        "v1_headroom": math.isclose(g_v1, anchors["v1_headroom"],
                                    rel_tol=0.0, abs_tol=1e-8),
        "capture_fraction": math.isclose(capture, anchors["capture_fraction"],
                                         rel_tol=0.0, abs_tol=1e-8),
        "vrf_budget_rounds_to_0.0084": round(vrf_median, 4) ==
                                      anchors["vrf_budget_median_rounded"],
        "value_axis_action_parity": parity,
    }
    return {
        "J": j,
        "best_fixed": fixed,
        "J_best_fixed": j[fixed],
        "J_oracle": j["ORACLE"],
        "J_m3g_v1": j["M3-G-v1"],
        "J_m3d": j["M3-D"],
        "oracle_headroom": g_oracle,
        "v1_headroom": g_v1,
        "capture_fraction": capture,
        "vrf_budget_m3g_v1_median": vrf_median,
        "value_axis_action_parity": parity,
        "formula_max_abs_diff": formula_max_abs_diff,
        "checks": checks,
        "pass": all(checks.values()),
    }


def _reference_arm_values(state: dict, pool_ref: dict, arm: str) -> tuple[list[float], float]:
    key = state_key(state)
    return ([float(v) for v in state["replicate_M2"][arm]],
            float(pool_ref[key]["arms"][arm]["P"]))


def run_attribution(repo: Path) -> dict[str, Any]:
    lock = load_json(repo / "configs/phase_m3ca/m3ca_analysis_lock.json")
    controller = load_json(repo / "results/phase_m3bv2/controller_evaluation.json")
    value = load_json(repo / "results/phase_m3bv2/value_analysis.json")
    pool = load_json(repo / "results/phase_m3bv/reference/m3bv_candidate_pool.json")
    m1d = load_json(repo / "docs/phase_m1d/M1_D_Benchmark_Freeze.json")
    value_states = value["freeze_selection"]
    pool_ref = pool["reference_fields"]
    p_refs = event_probabilities(m1d)
    headline = reproduce_headlines(value_states, controller, lock)

    if not headline["pass"]:
        return {
            "stage": "M3-CA",
            "extra_simulator_calls": 0,
            "headline_reproduction": headline,
            "counterfactuals": None,
            "verdict": {"code": "C", "label": "Accounting inconsistency",
                        "primary_reason": "headline reproduction gate failed"},
            "state_rows": [],
            "cost_ledger": [],
            "correlations": [],
        }

    state_rows = []
    ledger = []
    eval_n = int(lock["eval_n"])
    pilot_n = int(lock["pilot_n"])
    actual_budget = int(lock["deployable_budget_m3g_v1"])

    for state in value_states:
        key = state_key(state)
        config_id = state["state_key"]["config_id"]
        p_ref = p_refs[config_id]
        ctrl_state = controller["states"][key]
        recs = ctrl_state["replicates"]
        cls = state["class"]
        oracle_arm = ARM_BY_ACTION[state["oracle_action"]]
        best_arm = FIXED_ARM[headline["best_fixed"]]

        base_m2, base_p = _reference_arm_values(state, pool_ref, "base")
        widen_m2, widen_p = _reference_arm_values(state, pool_ref, "widen")
        shrink_m2, shrink_p = _reference_arm_values(state, pool_ref, "shrink")
        arm_m2 = {"base": base_m2, "widen": widen_m2, "shrink": shrink_m2}
        arm_p = {"base": base_p, "widen": widen_p, "shrink": shrink_p}

        best_vrf = [budget_vrf(p_ref, m2, arm_p[best_arm], eval_n, eval_n)
                    for m2 in arm_m2[best_arm]]
        oracle_vrf = [budget_vrf(p_ref, m2, arm_p[oracle_arm], eval_n, eval_n)
                      for m2 in arm_m2[oracle_arm]]
        base_vrf = [budget_vrf(p_ref, m2, base_p, eval_n, eval_n)
                    for m2 in base_m2]

        m3d_m2 = []
        v1_m2 = []
        m3d_actual = []
        v1_actual = []
        free_adaptation = []
        v1_proposal = []
        formula_diffs = []
        for rec in recs:
            m3d_arm = rec["m3d_arm"]
            v1_arm = rec["v1_arm"]
            m3d_m2.append(float(rec["arm_M2"][m3d_arm]))
            v1_m2.append(float(rec["arm_M2"][v1_arm]))
            m3d_actual.append(float(rec["arm_VRF_budget"][m3d_arm]))
            stored_v1 = float(rec["arm_VRF_budget"][v1_arm])
            v1_actual.append(stored_v1)
            p_hat = float(rec["arm_P_hat"][v1_arm])
            recomputed = budget_vrf(p_ref, rec["arm_M2"][v1_arm], p_hat,
                                    eval_n, actual_budget)
            formula_diffs.append(abs(recomputed - stored_v1))
            free = budget_vrf(p_ref, rec["arm_M2"][v1_arm], p_hat,
                              eval_n, eval_n)
            free_adaptation.append(free)
            v1_proposal.append(proposal_vrf(
                p_ref, rec["arm_M2"][v1_arm], p_hat, eval_n))

        state_j_bf = median(log_ratio(m, b) for m, b in
                            zip(arm_m2[best_arm], base_m2))
        state_j_oracle = median(log_ratio(m, b) for m, b in
                                zip(arm_m2[oracle_arm], base_m2))
        state_j_v1 = median(log_ratio(m, b) for m, b in zip(v1_m2, base_m2))
        available = state_j_bf - state_j_oracle
        captured = state_j_bf - state_j_v1
        capture_state = captured / available if abs(available) > 1e-12 else None

        row = {
            "state_id": ctrl_state["state_id"],
            "config_id": config_id,
            "s2": float(state["state_key"]["s2"]),
            "class": cls,
            "oracle_action": state["oracle_action"],
            "best_fixed_action": "WIDEN",
            "m3d_action_mode": _mode_action([r["m3d_action"] for r in recs]),
            "m3g_v1_action_mode": _mode_action([r["v1_action"] for r in recs]),
            "value_axis_action_parity": all(r["m3d_arm"] == r["v1_arm"] for r in recs),
            "event_probability": p_ref,
            "base_m2_median": median(base_m2),
            "best_fixed_m2_median": median(arm_m2[best_arm]),
            "oracle_m2_median": median(arm_m2[oracle_arm]),
            "m3d_m2_median": median(m3d_m2),
            "m3g_v1_m2_median": median(v1_m2),
            "base_vrf_budget_median": median(base_vrf),
            "best_fixed_vrf_budget_median": median(best_vrf),
            "m3d_vrf_budget_median": median(m3d_actual),
            "m3g_v1_vrf_proposal_median": median(v1_proposal),
            "m3g_v1_vrf_budget_median": median(v1_actual),
            "free_adaptation_vrf_median": median(free_adaptation),
            "free_oracle_vrf_median": median(oracle_vrf),
            "pilot_calls": pilot_n,
            "selected_arm_calls": eval_n,
            "deployable_calls": actual_budget,
            "pilot_fraction": pilot_n / actual_budget,
            "reference_base_leakage_concentration":
                _reference_leakage_concentration(pool_ref[key]),
            "proposal_loss_to_oracle_log_m2": state_j_v1 - state_j_oracle,
            "oracle_headroom_state": available,
            "captured_headroom_state": captured,
            "headroom_capture_state": capture_state,
            "absolute_efficiency_class":
                "EFFICIENT" if median(oracle_vrf) > 1.0 else "INEFFICIENT",
            "ess": NOT_IDENTIFIABLE,
            "pilot_m2_hat": NOT_IDENTIFIABLE,
            "vrf_fixed_arm_p_convention": "500k reference-arm P",
            "stored_vrf_formula_max_abs_diff": max(formula_diffs),
        }
        state_rows.append(row)

        method_rows = (
            ("CrudeMC", 0, 0, eval_n, eval_n, 1.0, "definition"),
            ("BASE", 0, 0, eval_n, eval_n, median(base_vrf), "frozen M2 + 500k arm P"),
            ("BestFixed", 0, 0, eval_n, eval_n, median(best_vrf), "frozen M2 + 500k arm P"),
            ("FreeOracle", 0, 0, eval_n, eval_n, median(oracle_vrf), "frozen M2 + 500k arm P"),
            ("M3-D", pilot_n, 0, eval_n, actual_budget, median(m3d_actual), "stored selected-arm record"),
            ("M3-G-v1", pilot_n, 0, eval_n, actual_budget, median(v1_actual), "stored selected-arm record"),
            ("FreeAdaptation", 0, 0, eval_n, eval_n, median(free_adaptation), "same stored M3-G-v1 action/arm"),
        )
        for method, pc, dc, sc, total, vrf, evidence in method_rows:
            ledger.append({
                "method": method, "state_id": row["state_id"],
                "pilot_cost": pc, "decision_cost": dc,
                "selected_arm_cost": sc, "deployable_cost": total,
                "audit_only_cost": 0, "total_scientific_cost": total,
                "vrf_budget_median": vrf,
                "source_artifact": "results/phase_m3bv2/controller_evaluation.json"
                    if "stored" in evidence or method in ("M3-D", "M3-G-v1")
                    else "results/phase_m3bv2/value_analysis.json",
                "probability_evidence": evidence,
            })
        ledger.append({
            "method": "AUDIT_REFERENCE_CHARACTERIZATION",
            "state_id": row["state_id"], "pilot_cost": 0,
            "decision_cost": 0, "selected_arm_cost": 0,
            "deployable_cost": 0,
            "audit_only_cost": 3 * 500000 + 3 * 8 * 100000,
            "total_scientific_cost": 3 * 500000 + 3 * 8 * 100000,
            "vrf_budget_median": None,
            "source_artifact": "m3bv candidate pool + headline stability",
            "probability_evidence": "audit only; excluded from deployed VRF",
        })

    def medcol(name: str, rows: list[dict] = state_rows) -> float:
        return median(r[name] for r in rows)

    counterfactuals = {
        "vrf_budget_crude_mc": 1.0,
        "vrf_budget_base": medcol("base_vrf_budget_median"),
        "vrf_budget_best_fixed": medcol("best_fixed_vrf_budget_median"),
        "vrf_budget_m3d": medcol("m3d_vrf_budget_median"),
        "vrf_budget_m3g_v1": medcol("m3g_v1_vrf_budget_median"),
        "vrf_budget_free_adaptation": medcol("free_adaptation_vrf_median"),
        "vrf_budget_free_oracle": medcol("free_oracle_vrf_median"),
        "free_oracle_gt_1": medcol("free_oracle_vrf_median") > 1.0,
        "pilot_fraction_median": medcol("pilot_fraction"),
    }

    correlations = []
    targets = (
        ("event_probability", "free_oracle_vrf_median"),
        ("base_m2_median", "free_oracle_vrf_median"),
        ("reference_base_leakage_concentration", "free_oracle_vrf_median"),
        ("s2", "free_oracle_vrf_median"),
        ("pilot_fraction", "m3g_v1_vrf_budget_median"),
    )
    for x_name, y_name in targets:
        stat = _safe_spearman([float(r[x_name]) for r in state_rows],
                              [float(r[y_name]) for r in state_rows])
        correlations.append({"scope": "all", "x": x_name, "y": y_name,
                             **stat})
        for cls in ("WIDEN", "SHRINK"):
            subset = [r for r in state_rows if r["class"] == cls]
            stat = _safe_spearman([float(r[x_name]) for r in subset],
                                  [float(r[y_name]) for r in subset])
            correlations.append({"scope": cls, "x": x_name, "y": y_name,
                                 **stat})

    free_oracle = counterfactuals["vrf_budget_free_oracle"]
    actual = counterfactuals["vrf_budget_m3g_v1"]
    if free_oracle <= 1.0:
        verdict = {
            "code": "A", "label": "Proposal / regime bottleneck",
            "primary_reason":
                "Median free-Oracle budget VRF is <= 1; perfect action "
                "selection cannot make the frozen scalar proposal family "
                "cost-efficient under the frozen BV2 benchmark.",
        }
    elif actual < 1.0:
        verdict = {
            "code": "B", "label": "Adaptation-overhead bottleneck",
            "primary_reason":
                "Median free-Oracle budget VRF is > 1 while deployed "
                "M3-G-v1 budget VRF remains < 1.",
        }
    else:
        verdict = {
            "code": "D", "label": "Mixed bottleneck",
            "primary_reason": "Neither the locked A nor B rule is decisive.",
        }

    classes = {}
    for cls in ("WIDEN", "SHRINK"):
        subset = [r for r in state_rows if r["class"] == cls]
        classes[cls] = {
            "n_states": len(subset),
            "vrf_budget_best_fixed": medcol("best_fixed_vrf_budget_median", subset),
            "vrf_budget_free_oracle": medcol("free_oracle_vrf_median", subset),
            "vrf_budget_m3d": medcol("m3d_vrf_budget_median", subset),
            "vrf_budget_m3g_v1": medcol("m3g_v1_vrf_budget_median", subset),
            "vrf_budget_free_adaptation": medcol("free_adaptation_vrf_median", subset),
        }

    return {
        "stage": "M3-CA",
        "extra_simulator_calls": 0,
        "headline_reproduction": headline,
        "counterfactuals": counterfactuals,
        "class_summary": classes,
        "cost_conventions": {
            "deployable": "pilot + decision simulator calls + selected arm",
            "decision_simulator_calls": 0,
            "decision_cpu_or_wall_clock_cost": NOT_IDENTIFIABLE,
            "fixed_arm_probability": "existing 500k reference-arm P",
            "reference_and_counterfactual_arms": "audit-only",
        },
        "correlations": correlations,
        "verdict": verdict,
        "claim_boundaries": [
            "within the frozen BV2 benchmark",
            "within the frozen scalar proposal family",
            "not universal adaptive superiority",
            "not real-system or wall-clock efficiency",
            "relative adaptive value is not absolute budget efficiency",
        ],
        "state_rows": state_rows,
        "cost_ledger": ledger,
    }
