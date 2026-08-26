"""M3 -- trial-record assembly (task Sec. 31 machine-readable schema) and
gate aggregation for the scalar benchmark (Sec. 23-25 metrics).

Simulator-call double accounting is recorded per trial (task Sec. 22):

    scientific_audit_calls = pilot + independent evals of BASE/WIDEN/SHRINK
    deployable_method_calls = pilot + ONE evaluation of the GRADIENT action path
"""

from __future__ import annotations

import numpy as np

SCHEMA_VERSION = "raretopo-m3-v0"


def build_trial_record(
    *,
    tags: dict,
    config_id: str,
    seed: int,
    selected_mode: str | None,
    component_index: int | None,
    layer: str,
    gradient: dict,
    counterfactual: dict,
    m2_diagnostic: dict | None = None,
    evaluation: dict | None = None,
    validity: dict | None = None,
) -> dict:
    """Assemble one schema-complete record; defaults keep STOP/failed stages
    representable without inventing numbers."""
    rec = {
        "schema_version": SCHEMA_VERSION,
        "h3_tag": tags["h3"],
        "m1_tag": tags["m1"],
        "m1d_tag": tags["m1d"],
        "m2_tag": tags["m2"],
        "config_id": config_id,
        "seed": int(seed),
        "selected_mode": selected_mode,
        "component_index": component_index,
        "layer": layer,
        "gradient": {
            "M2_hat": None, "responsibility_mass": None, "D_hat": None,
            "g_hat": None, "g_ci_low": None, "g_ci_high": None,
            "ESS_grad": None, "decision": "HOLD_INVALID",
            **(gradient or {}),
        },
        "counterfactual": {
            "delta_theta": None,
            "M2_base": None, "M2_widen": None, "M2_shrink": None,
            "M2_pred": None, "M2_opposite": None,
            "evaluation_best_direction": None,
            **(counterfactual or {}),
        },
        "m2_diagnostic": {"hdr_covariance": [], "hdr_trace": None,
                          "conflict_with_gradient": None,
                          **(m2_diagnostic or {})},
        "evaluation": {
            "P_hat": None, "VRF_proposal": None, "VRF_budget": None,
            "mode_L": {}, "n": None,
            "scientific_audit_calls": None,
            "deployable_method_calls": None,
            **(evaluation or {}),
        },
        "validity": {**(validity or {})},
    }
    return rec


def _median(v):
    v = [x for x in v if x is not None and np.isfinite(x)]
    return float(np.median(v)) if v else None


def aggregate_gate_quantities(records: list[dict],
                              tie_tol: float = 0.01) -> dict:
    """Per-benchmark aggregates feeding gates M3-2..M3-6 and Strong.

    ``records`` are Layer A main-grid records with completed counterfactuals.
    """
    n_total = len(records)
    dec = {}
    for r in records:
        d = r["gradient"]["decision"]
        dec[d] = dec.get(d, 0) + 1

    active = [r for r in records
              if r["gradient"]["decision"] in ("WIDEN", "SHRINK")]
    n_active = len(active)

    acc_hits = sum(
        1 for r in active
        if r["counterfactual"]["evaluation_best_direction"]
        == r["gradient"]["decision"])
    acc_dir = acc_hits / n_active if n_active else None

    success = [r for r in active
               if r["counterfactual"]["M2_pred"] < r["counterfactual"]["M2_base"]]
    rate_success = len(success) / n_active if n_active else None

    ratios_pred_base = [r["counterfactual"]["M2_pred"]
                        / r["counterfactual"]["M2_base"] for r in active]
    ratios_pred_opp = [r["counterfactual"]["M2_pred"]
                       / r["counterfactual"]["M2_opposite"] for r in active]

    # fixed-comparator direction accuracies on the SAME active-trial set
    def fixed_acc(direction_value_field):
        hits = 0
        for r in active:
            best = evaluation_best(
                r["counterfactual"]["M2_base"],
                r["counterfactual"]["M2_widen"],
                r["counterfactual"]["M2_shrink"], tie_tol)
            hits += int(best == direction_value_field)
        return hits / n_active if n_active else None

    acc_always_widen = fixed_acc("WIDEN")
    acc_always_shrink = fixed_acc("SHRINK")

    # M3-6 leakage redistribution per config: median over seeds of
    # max_{j != k} L_j(pred)/L_j(base)
    by_cfg: dict[str, list[float]] = {}
    for r in active:
        Lb = r["evaluation"].get("mode_L_base") or {}
        Lp = r["evaluation"].get("mode_L_pred") or {}
        kdx = str(r.get("selected_mode"))
        offs = [Lp[j] / Lb[j] for j in sorted(set(Lb) & set(Lp))
                if j != kdx and Lb.get(j, 0.0) > 0.0]
        if offs:
            by_cfg.setdefault(r["config_id"], []).append(max(offs))
    leak_per_config = {c: float(np.median(v)) for c, v in by_cfg.items()}

    # Strong gate: deployable budget-adjusted VRF of the GRADIENT action path
    vrf_budget_grad = [
        r["evaluation"]["VRF_budget_grad_path"]
        for r in records
        if r["evaluation"].get("VRF_budget_grad_path") is not None]

    ess_values = [r["gradient"]["ESS_grad"] for r in records
                  if r["gradient"]["ESS_grad"] is not None]

    return {
        "n_trials": n_total,
        "decision_counts": dec,
        "n_active": n_active,
        "active_fraction": n_active / n_total if n_total else None,
        "acc_dir": acc_dir,
        "rate_M2_pred_lt_base": rate_success,
        "median_ratio_pred_base": _median(ratios_pred_base),
        "median_ratio_pred_opposite": _median(ratios_pred_opp),
        "acc_always_widen_on_active": acc_always_widen,
        "acc_always_shrink_on_active": acc_always_shrink,
        "leakage_median_max_offtarget_by_config": leak_per_config,
        "configs_within_leak_ratio_2":
            sum(1 for v in leak_per_config.values() if v <= 2.0),
        "vrf_budget_grad_median": _median(vrf_budget_grad),
        "ess_grad_median_over_all": _median(ess_values),
    }


def evaluation_best(m2_base, m2_widen, m2_shrink, rel_tol=0.01):
    from hyptraj.m3.direction_policy import (
        WIDEN, SHRINK, evaluation_best_direction)
    del WIDEN, SHRINK
    return evaluation_best_direction(float(m2_base), float(m2_widen),
                                     float(m2_shrink), rel_tol)


__all__ = ["build_trial_record", "aggregate_gate_quantities",
           "SCHEMA_VERSION", "evaluation_best"]
