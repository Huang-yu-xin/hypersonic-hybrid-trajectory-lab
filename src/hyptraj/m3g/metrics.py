"""M3-G -- calibration metrics, the preregistered selection rule and the
raretopo-m3g-v0 record schema (task Sec. 3 calibration protocol / Sec. 5).

Pure functions over STORED M3-D Layer-A records; no I/O, no simulator
calls, no oracle access inside any gate path (oracle labels enter only the
evaluation of predicted actions, exactly like the M3-D audit).
"""

from __future__ import annotations

from statistics import median

import numpy as np

from hyptraj.m2.covariance_projection import check_legality_frozen
from hyptraj.m3d.metrics import three_class_metrics

from hyptraj.m3g.gain_gate import (
    HOLD_GAIN,
    apply_gain_gate,
    final_arm_key,
)
from hyptraj.m3g.gain_proxy import DELTA_THETA_MAIN

RECORD_SCHEMA_VERSION = "raretopo-m3g-v0"

# Frozen calibration grid (task Sec. 3; NO extra thresholds allowed).
RHO_GRID = [0.0025, 0.005, 0.01, 0.02]
VARIANT_GRID = ("GA1", "GA2")


def arm_legal_at(s2: float, shift: float, dim: int = 2) -> bool:
    """Frozen legality of the arm covariance s2*exp(shift)*I (deterministic
    checker, no draws; dimension-invariant for scalar covariance)."""
    ok, _min_eig = check_legality_frozen(
        (float(s2) * float(np.exp(shift))) * np.eye(dim))
    return bool(ok)


def gate_from_stored_record(rec: dict, variant: str, rho: float) -> dict:
    """Simulate the locked gate on ONE stored M3-D Layer-A record.

    Uses only stored fields: gradient action/g_hat/g_CI (frozen outputs)
    and the base-arm evaluation M2 as the locked normaliser.  The mapped
    arm's legality is recomputed deterministically from ``base_s2``
    (frozen checker; zero simulator calls).  Never touches oracle fields.
    """
    direction = str(rec["gradient"]["action"])
    if direction not in ("WIDEN", "SHRINK"):
        return apply_gain_gate(
            direction=direction, variant=variant, rho=rho,
            g_hat=float(rec["gradient"]["g_hat"]),
            g_ci_low=float(rec["gradient"]["g_ci_low"]),
            g_ci_high=float(rec["gradient"]["g_ci_high"]),
            m2=float(rec["arms"]["hold"]["M2"]),
            delta_theta=DELTA_THETA_MAIN, arm_legal=True)
    shift = {"WIDEN": +DELTA_THETA_MAIN, "SHRINK": -DELTA_THETA_MAIN}[
        direction]
    return apply_gain_gate(
        direction=direction, variant=variant, rho=rho,
        g_hat=float(rec["gradient"]["g_hat"]),
        g_ci_low=float(rec["gradient"]["g_ci_low"]),
        g_ci_high=float(rec["gradient"]["g_ci_high"]),
        m2=float(rec["arms"]["hold"]["M2"]),
        delta_theta=DELTA_THETA_MAIN,
        arm_legal=arm_legal_at(float(rec["base_s2"]), shift))


def candidate_metrics(records: list[dict], variant: str, rho: float) -> dict:
    """Full calibration row for one (variant, rho) on the stored batch.

    Classification is pooled over the 192 (state, seed) trials; M2 ratios
    reuse the STORED arm evaluations only.  ``oracle_action`` serves the
    evaluation of the predicted actions (identical to M3-D accounting).
    """
    y_true, y_pred, finals = [], [], []
    changes = hold_gain = hold_invalid = 0
    m2_final_over_base, m2_final_over_oracle = [], []
    oracle_correct = 0
    for rec in records:
        g = gate_from_stored_record(rec, variant, rho)
        final = g["final_action"]
        y_true.append(rec["oracle_action"])
        y_pred.append(final)
        finals.append(final)
        if final != rec["validity"]["deployed_action"]:
            changes += 1
        if g["gain_hold_reason"] == HOLD_GAIN:
            hold_gain += 1
        if g["gain_hold_reason"] == "HOLD_INVALID":
            hold_invalid += 1
        if final == rec["oracle_action"]:
            oracle_correct += 1
        final_m2 = float(rec["arms"][final_arm_key(final)]["M2"])
        base_m2 = float(rec["arms"]["hold"]["M2"])
        oracle_m2 = float(rec["arms"]["oracle"]["M2"])
        if base_m2 > 0.0:
            m2_final_over_base.append(final_m2 / base_m2)
        if oracle_m2 > 0.0:
            m2_final_over_oracle.append(final_m2 / oracle_m2)

    m = three_class_metrics(y_true, y_pred)
    return {
        "variant": variant,
        "rho": float(rho),
        "n_trials": int(len(records)),
        "accuracy": m["accuracy"],
        "recall_per_class": m["recall_per_class"],
        "balanced_accuracy": m["balanced_accuracy"],
        "macro_F1": m["macro_F1"],
        "confusion_matrix": m["confusion_matrix"],
        "action_change_count": int(changes),
        "hold_gain_count": int(hold_gain),
        "hold_invalid_count": int(hold_invalid),
        "median_M2_final_over_base": float(median(m2_final_over_base)),
        "median_M2_final_over_oracle": float(median(m2_final_over_oracle)),
        "oracle_action_agreement": float(oracle_correct / len(records)),
        "final_action_counts": {
            k: int(finals.count(k)) for k in ("WIDEN", "SHRINK", "HOLD")},
    }


def build_calibration_table(records: list[dict],
                            rhos: list[float] | None = None,
                            variants: tuple[str, ...] | None = None) -> dict:
    """(GA1 x 4 rho) + (GA2 x 4 rho) + frozen M3-D baseline row."""
    rhos = list(RHO_GRID if rhos is None else rhos)
    variants = tuple(VARIANT_GRID if variants is None else variants)
    table: dict[str, dict] = {}
    for v in variants:
        for r in rhos:
            table[f"{v}-{r}"] = candidate_metrics(records, v, r)

    y_true = [r["oracle_action"] for r in records]
    y_pred = [r["validity"]["deployed_action"] for r in records]
    m = three_class_metrics(y_true, y_pred)
    finals = y_pred
    m2over = [float(r["arms"][final_arm_key(p)]["M2"])
              / float(r["arms"]["hold"]["M2"])
              for r, p in zip(records, finals)
              if float(r["arms"]["hold"]["M2"]) > 0.0]
    m2over_o = [float(r["arms"][final_arm_key(p)]["M2"])
                / float(r["arms"]["oracle"]["M2"])
                for r, p in zip(records, finals)
                if float(r["arms"]["oracle"]["M2"]) > 0.0]
    table["baseline_M3-D"] = {
        "variant": "M3-D",
        "rho": None,
        "n_trials": int(len(records)),
        "accuracy": m["accuracy"],
        "recall_per_class": m["recall_per_class"],
        "balanced_accuracy": m["balanced_accuracy"],
        "macro_F1": m["macro_F1"],
        "confusion_matrix": m["confusion_matrix"],
        "action_change_count": 0,
        "hold_gain_count": 0,
        "hold_invalid_count": 0,
        "median_M2_final_over_base": float(median(m2over)),
        "median_M2_final_over_oracle": float(median(m2over_o)),
        "oracle_action_agreement": m["accuracy"],
        "final_action_counts": {
            k: int(finals.count(k)) for k in ("WIDEN", "SHRINK", "HOLD")},
    }
    return table


def select_candidate(table: dict, recall_min: float = 0.90) -> dict:
    """Preregistered selection rule (task Sec. 3).

    Eligible  : WIDEN recall >= 0.90 AND SHRINK recall >= 0.90 each;
                 violating candidates are ineligible (None -> STOP).
    Primary   : maximize accuracy (Acc3) among eligible candidates.
    Tie-break : balanced accuracy, then macro-F1, then smaller rho, then
                 GA1 before GA2 (deterministic; recorded in the freeze).
    """
    cands = []
    for key, row in table.items():
        if row.get("variant") == "M3-D":
            continue
        rc = row["recall_per_class"]
        eligible = (rc["WIDEN"] is not None and rc["WIDEN"] >= recall_min
                    and rc["SHRINK"] is not None
                    and rc["SHRINK"] >= recall_min)
        cands.append({
            "key": key,
            "variant": row["variant"],
            "rho": row["rho"],
            "eligible": bool(eligible),
            "accuracy": row["accuracy"],
            "balanced_accuracy": row["balanced_accuracy"],
            "macro_F1": row["macro_F1"],
            "recall_widen": rc["WIDEN"],
            "recall_shrink": rc["SHRINK"],
        })
    eligible = [c for c in cands if c["eligible"]]
    if not eligible:
        return {"selected": None, "why": "no_candidate_meets_90_90",
                "candidates": cands}
    order = sorted(eligible, key=lambda c: (
        -c["accuracy"], -c["balanced_accuracy"], -c["macro_F1"],
        c["rho"], 0 if c["variant"] == "GA1" else 1))
    best = order[0]
    return {"selected": {"key": best["key"], "variant": best["variant"],
                         "rho": best["rho"]},
            "why": "preregistered_accuracy_max",
            "winner_row": best,
            "candidates": cands}


ARM_KEYS = ("hold", "widen", "shrink", "gradient", "oracle", "gate")


def build_m3g_trial_record(*, config_id: str, state_id: str, seed: int,
                           base_s2: float, oracle_action: str,
                           oracle_direction_margin: float,
                           gradient_block: dict, gain_block: dict,
                           arms_block: dict, metrics_block: dict,
                           validity_block: dict | None = None) -> dict:
    """raretopo-m3g-v0 online record: the frozen M3-D ``gradient`` block is
    kept byte-identical (bitwise-parity guard) and the gain layer is a NEW
    block; ``arms`` adds the gated policy's mapped arm as ``gate``."""
    rec = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "config_id": config_id,
        "state_id": state_id,
        "seed": int(seed),
        "base_s2": float(base_s2),
        "oracle_action": oracle_action,
        "oracle_direction_margin": float(oracle_direction_margin),
        "gradient": {
            "g_hat": float(gradient_block["g_hat"]),
            "g_ci_low": float(gradient_block["g_ci_low"]),
            "g_ci_high": float(gradient_block["g_ci_high"]),
            "ESS_grad": float(gradient_block["ESS_grad"]),
            "action": gradient_block["action"],
            "M2_hat_pilot": (float(gradient_block["M2_hat_pilot"])
                             if gradient_block.get("M2_hat_pilot")
                             is not None else None),
        },
        "gain": dict(gain_block),
        "arms": {k: {"M2": float(arm["M2"]),
                     "mode_L": {str(a): float(b)
                                for a, b in arm["mode_L"].items()}}
                 for k, arm in arms_block.items()
                 if k in ARM_KEYS},
        "metrics": {
            "action_correct": bool(metrics_block["action_correct"]),
            "regret_M2": (float(metrics_block["regret_M2"])
                          if metrics_block.get("regret_M2") is not None
                          else None),
            "VRF_proposal": (float(metrics_block["VRF_proposal"])
                             if metrics_block.get("VRF_proposal")
                             is not None else None),
            "VRF_budget": (float(metrics_block["VRF_budget"])
                           if metrics_block.get("VRF_budget")
                           is not None else None),
            "M2_gate_over_base": (float(metrics_block["M2_gate_over_base"])
                                  if metrics_block.get("M2_gate_over_base")
                                  is not None else None),
            "M2_gate_over_oracle": (
                float(metrics_block["M2_gate_over_oracle"])
                if metrics_block.get("M2_gate_over_oracle") is not None
                else None),
            "M2_gate_over_gradient": (
                float(metrics_block["M2_gate_over_gradient"])
                if metrics_block.get("M2_gate_over_gradient") is not None
                else None),
        },
        "validity": dict(validity_block or {}),
    }
    return rec


def validate_m3g_trial_record(rec: dict) -> bool:
    if rec.get("schema_version") != RECORD_SCHEMA_VERSION:
        return False
    if set(rec.get("arms", {}).keys()) != set(ARM_KEYS):
        return False
    if rec.get("oracle_action") not in ("WIDEN", "SHRINK", "HOLD"):
        return False
    if rec.get("gradient", {}).get("action") not in (
            "WIDEN", "SHRINK", "HOLD_UNCERTAIN", "HOLD_LOW_ESS",
            "HOLD_INVALID"):
        return False
    g = rec.get("gain", {})
    if g.get("gain_variant") not in ("GA1", "GA2"):
        return False
    if g.get("final_action") not in ("WIDEN", "SHRINK", "HOLD"):
        return False
    if g.get("direction_before_gain") not in (
            "WIDEN", "SHRINK", "HOLD_UNCERTAIN", "HOLD_LOW_ESS",
            "HOLD_INVALID"):
        return False
    for k in ARM_KEYS:
        a = rec["arms"][k]
        if not isinstance(a.get("M2"), (int, float)):
            return False
        from hyptraj.m3d.metrics import identity_closure_ok
        if identity_closure_ok(a.get("mode_L", {}), a.get("M2"),
                               rel_tol=1e-6) is False:
            return False
    need = {"config_id", "state_id", "seed", "base_s2"}
    if not need.issubset(rec.keys()):
        return False
    return True


def per_state_summary(records: list[dict], variant: str,
                      rho: float) -> dict:
    """Per-state (24 rows) calibration summary under one locked policy."""
    by_state: dict[str, dict] = {}
    for rec in records:
        sid = rec["state_id"]
        g = gate_from_stored_record(rec, variant, rho)
        row = by_state.setdefault(sid, {
            "state_id": sid, "config_id": rec["config_id"],
            "s2": rec["base_s2"], "oracle": rec["oracle_action"],
            "n_trials": 0, "final": [], "hold_gain": 0})
        row["n_trials"] += 1
        row["final"].append(g["final_action"])
        row["hold_gain"] += int(g["gain_hold_reason"] == HOLD_GAIN)
    out = []
    for sid, row in sorted(by_state.items()):
        row["final_counts"] = {k: row["final"].count(k)
                               for k in ("WIDEN", "SHRINK", "HOLD")}
        row["n_correct"] = sum(1 for f in row["final"]
                               if f == row["oracle"])
        row.pop("final")
        out.append(row)
    return out


def per_class_summary(records: list[dict], variant: str, rho: float) -> dict:
    """Per-class calibration summary (recall, HOLD_GAIN rate, M2 medians)."""
    y_true = [r["oracle_action"] for r in records]
    finals = [gate_from_stored_record(r, variant, rho)["final_action"]
              for r in records]
    m = three_class_metrics(y_true, finals)
    out = {}
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        idx = [i for i, t in enumerate(y_true) if t == cls]
        n_hg = sum(1 for i in idx if
                   gate_from_stored_record(records[i], variant, rho)[
                       "gain_hold_reason"] == HOLD_GAIN)
        out[cls] = {
            "n": len(idx),
            "recall": m["recall_per_class"][cls],
            "hold_gain_fraction": (n_hg / len(idx)) if idx else None,
        }
    return {"confusion": m["confusion_matrix"], "per_class": out}


__all__ = [
    "RECORD_SCHEMA_VERSION", "RHO_GRID", "VARIANT_GRID", "ARM_KEYS",
    "arm_legal_at", "gate_from_stored_record", "candidate_metrics",
    "build_calibration_table", "select_candidate", "per_state_summary",
    "per_class_summary", "build_m3g_trial_record",
    "validate_m3g_trial_record",
]