"""M3-G-v1 -- record schema (raretopo-m3g-v1) and parity helpers.

The frozen ``gradient`` block stays byte-identical to the M3-D record
schema (bitwise-parity guard); the gain layer adds the v1 gate block and
the pilot M2_hat diagnostic.  No oracle / reference fields enter any
online API (structural tests enforce it).
"""

from __future__ import annotations

RECORD_SCHEMA_VERSION = "raretopo-m3g-v1"
ARM_KEYS = ("hold", "widen", "shrink", "gradient", "oracle", "gate")
ACTION_ENUM = ("WIDEN", "SHRINK", "HOLD_UNCERTAIN", "HOLD_LOW_ESS",
               "HOLD_INVALID")


def build_m3g_v1_trial_record(*, config_id: str, state_id: str, seed: int,
                              base_s2: float, oracle_action: str,
                              oracle_direction_margin: float,
                              gradient_block: dict, gain_block: dict,
                              arms_block: dict, metrics_block: dict,
                              validity_block: dict | None = None) -> dict:
    """raretopo-m3g-v1 online record (mirrors the v0 shape)."""
    return {
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
            "M2_hat_pilot": float(gradient_block["M2_hat_pilot"]),
        },
        "gain": dict(gain_block),
        "arms": {k: {"M2": float(arm["M2"]),
                     "mode_L": {str(a): float(b)
                                for a, b in arm["mode_L"].items()}}
                 for k, arm in arms_block.items() if k in ARM_KEYS},
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


def validate_m3g_v1_trial_record(rec: dict) -> bool:
    if rec.get("schema_version") != RECORD_SCHEMA_VERSION:
        return False
    if set(rec.get("arms", {}).keys()) != set(ARM_KEYS):
        return False
    if rec.get("oracle_action") not in ("WIDEN", "SHRINK", "HOLD"):
        return False
    g = rec.get("gain", {})
    if g.get("variant") != "GA1":
        return False
    if g.get("final_action") not in ("WIDEN", "SHRINK", "HOLD"):
        return False
    if g.get("direction_before_gain") not in ACTION_ENUM:
        return False
    if abs(float(g.get("rho", -1.0)) - 0.02) > 1e-12:
        return False
    grad = rec.get("gradient", {})
    if grad.get("action") not in ACTION_ENUM:
        return False
    if not isinstance(grad.get("M2_hat_pilot"), (int, float)):
        return False
    from hyptraj.m3d.metrics import identity_closure_ok
    for k in ARM_KEYS:
        a = rec["arms"][k]
        if not isinstance(a.get("M2"), (int, float)):
            return False
        if identity_closure_ok(a.get("mode_L", {}), a.get("M2"),
                               rel_tol=1e-6) is False:
            return False
    need = {"config_id", "state_id", "seed", "base_s2"}
    if not need.issubset(rec.keys()):
        return False
    return True


__all__ = ["RECORD_SCHEMA_VERSION", "ARM_KEYS", "ACTION_ENUM",
           "build_m3g_v1_trial_record", "validate_m3g_v1_trial_record"]