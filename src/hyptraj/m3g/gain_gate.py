"""M3-G -- gain-aware execution gate (task Sec. 3, preregistered floors).

The gate is strictly a SECOND layer on top of the frozen M3-D direction
decision:

    frozen direction (WIDEN / SHRINK / HOLD_*)
        -> gain-aware gate (GA1|GA2 at locked rho)
        -> EXECUTE frozen direction | HOLD_GAIN | HOLD_INVALID

It never reclassifies a direction: WIDEN may only become EXECUTED-WIDEN,
HOLD_GAIN (folded HOLD), or HOLD_INVALID (legality fold); SHRINK likewise.
HOLD_* directions pass through untouched with their raw reason preserved.

Legality floor (preregistered): an acted state must remain legal under the
frozen checker at the mapped arm; otherwise the action folds to
HOLD_INVALID exactly like the M3-D audit discipline.
"""

from __future__ import annotations

from hyptraj.m3.direction_policy import (
    ACTIVE_DECISIONS,
    HOLD_INVALID,
    WIDEN,
    SHRINK,
    step_sign_for,
)
from hyptraj.m3g.gain_proxy import DELTA_THETA_MAIN, ga1_magnitude, ga2_upper_end

GA1 = "GA1"
GA2 = "GA2"
VARIANTS = (GA1, GA2)

# Folding reasons emitted by the gate.
EXECUTED = "EXECUTED"
HOLD_GAIN = "HOLD_GAIN"           # active direction gated to HOLD
HOLD_INVALID_REASON = HOLD_INVALID  # legality fold (action arm illegal)


def apply_gain_gate(*, direction: str, variant: str, rho: float,
                    g_hat: float, g_ci_low: float, g_ci_high: float,
                    m2: float, delta_theta: float = DELTA_THETA_MAIN,
                    arm_legal: bool = True) -> dict:
    """Apply the locked gain gate to one frozen direction decision.

    Parameters
    ----------
    direction  : frozen M3-D decision code (WIDEN/SHRINK/HOLD_UNCERTAIN/
                 HOLD_LOW_ESS/HOLD_INVALID).
    variant    : "GA1" magnitude rule |Delta_rel| >= rho, or "GA2"
                 conservative signed-gain CI rule (upper end <= -rho).
    rho        : locked global gain floor (calibration grid only).
    g_hat/g_ci_low/g_ci_high : frozen estimator outputs (never recomputed).
    m2         : locked M2 normaliser (base-arm evaluation M2).
    arm_legal  : frozen legality verdict of the MAPPED action arm.

    Returns the M3-G per-trial gain block:
        direction_before_gain / gain_variant / rho / gain_proxy_mag /
        gain_proxy_upper_end / final_action / gain_hold_reason.
    """
    rho = float(rho)
    m2 = float(m2)
    dtheta = float(step_sign_for(direction, delta_theta))
    res = {
        "direction_before_gain": str(direction),
        "gain_variant": str(variant),
        "rho": rho,
        "delta_theta": dtheta,
        "gain_proxy_mag": None,
        "gain_proxy_upper_end": None,
        "final_action": "HOLD",
        "gain_hold_reason": str(direction),   # passthrough keeps raw reason
    }
    if direction not in ACTIVE_DECISIONS:
        # HOLD_* passthrough: keep HOLD, preserve the raw reason code.
        res["gain_hold_reason"] = str(direction)
        return res

    res["gain_proxy_mag"] = float(ga1_magnitude(
        float(g_hat), dtheta, m2))
    res["gain_proxy_upper_end"] = float(ga2_upper_end(
        float(g_ci_low), float(g_ci_high), dtheta, m2))

    if not arm_legal:
        # Frozen-checker legality floor: illegal mapped arm -> HOLD_INVALID.
        res["gain_hold_reason"] = HOLD_INVALID_REASON
        return res

    if variant == GA1:
        act = bool(res["gain_proxy_mag"] >= rho)
    elif variant == GA2:
        act = bool(res["gain_proxy_upper_end"] <= -rho)
    else:
        raise ValueError(f"unknown gain variant {variant!r}")

    if act:
        res["final_action"] = str(direction)
        res["gain_hold_reason"] = EXECUTED
    else:
        res["gain_hold_reason"] = HOLD_GAIN
    return res


def deployed_final(decision: str) -> str:
    """Fold the gated action onto the three physical arms
    (WIDEN/SHRINK/HOLD) with the raw reason preserved upstream."""
    if decision == WIDEN:
        return "WIDEN"
    if decision == SHRINK:
        return "SHRINK"
    return "HOLD"


def final_arm_key(final_action: str) -> str:
    """Physical arm realising the gated action (as in M3-D arm mapping)."""
    return {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "hold"}[
        deployed_final(final_action)]


__all__ = [
    "GA1", "GA2", "VARIANTS", "EXECUTED", "HOLD_GAIN", "HOLD_INVALID_REASON",
    "apply_gain_gate", "deployed_final", "final_arm_key",
]