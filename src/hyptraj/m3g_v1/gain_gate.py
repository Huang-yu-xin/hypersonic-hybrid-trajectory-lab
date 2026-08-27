"""M3-G-v1 -- GA1 exact first-order gain gate (confirmatory recovery).

Frozen candidate (task M3_G_v1_Exact_Proxy_Recovery_Task.md; locked in
configs/phase_m3g_v1 before any confirmatory run):

    variant      GA1
    rho          0.02
    delta_theta  0.20
    denominator  pilot M2_hat (mass/n from the frozen estimator pipeline)

Decision precedence (direction layer is the frozen M3-D controller,
VERBATIM; this gate never recomputes or reclassifies a direction):

    HOLD_LOW_ESS    -> HOLD_LOW_ESS    (passthrough, reason preserved)
    HOLD_UNCERTAIN  -> HOLD_UNCERTAIN  (passthrough, reason preserved)
    Delta_rel < 0.02 -> HOLD_GAIN
    else            -> EXECUTE frozen WIDEN / SHRINK

Hard floors:
  * online gate uses pilot M2_hat ONLY -- comparator-arm M2 is not a
    parameter of this module (whitelisted signature, structural test);
  * no alternate conservative variant branch, no calibration grid,
    no alternate rho;
  * legality floor inherited from M3-D audit discipline: acted arm must be
    legal under the frozen checker, else fold HOLD_INVALID;
  * no sign flip, no label-book access.
"""

from __future__ import annotations

from hyptraj.m3.direction_policy import ACTIVE_DECISIONS, step_sign_for
from hyptraj.m3g.gain_proxy import ga1_magnitude

VARIANT = "GA1"
RHO = 0.02                       # frozen threshold (config parity-test locked)
DELTA_THETA = 0.20               # frozen step size priced into the gate

EXECUTED = "EXECUTED"
HOLD_GAIN = "HOLD_GAIN"
HOLD_INVALID = "HOLD_INVALID"


def apply_gain_gate_v1(*, direction: str, g_hat: float, m2_pilot: float,
                       delta_theta: float = DELTA_THETA,
                       rho: float = RHO, arm_legal: bool = True) -> dict:
    """Apply the frozen GA1/0.02 gate to one frozen direction decision.

    Parameters
    ----------
    direction : frozen M3-D decision code (WIDEN/SHRINK/HOLD_UNCERTAIN/
                HOLD_LOW_ESS/HOLD_INVALID).
    g_hat     : frozen point gradient estimate.
    m2_pilot  : pilot M2_hat from the frozen estimator pipeline ONLY
                (evaluation-arm M2 is NOT a parameter of this gate).
    arm_legal : frozen legality verdict of the MAPPED action arm.

    Returns the v1 per-trial gain block:
        direction_before_gain / variant / rho / delta_theta /
        gain_proxy / final_action / gain_hold_reason.
    """
    dtheta = float(step_sign_for(direction, delta_theta))
    res = {
        "direction_before_gain": str(direction),
        "variant": VARIANT,
        "rho": float(rho),
        "delta_theta": dtheta,
        "gain_proxy": None,
        "final_action": "HOLD",
        "gain_hold_reason": str(direction),   # passthrough keeps raw reason
    }
    if direction not in ACTIVE_DECISIONS:
        # HOLD_LOW_ESS / HOLD_UNCERTAIN / HOLD_INVALID passthrough verbatim.
        res["gain_hold_reason"] = str(direction)
        return res

    proxy = float(ga1_magnitude(float(g_hat), dtheta, float(m2_pilot)))
    res["gain_proxy"] = proxy

    if not arm_legal:
        res["gain_hold_reason"] = HOLD_INVALID
        return res

    if proxy < float(rho):
        res["gain_hold_reason"] = HOLD_GAIN
    else:
        res["final_action"] = str(direction)
        res["gain_hold_reason"] = EXECUTED
    return res


def final_deployed(final_action: str) -> str:
    """Fold the gated action onto the three physical arm labels."""
    if final_action in ("WIDEN", "SHRINK"):
        return final_action
    return "HOLD"


def final_arm_key(final_action: str) -> str:
    """Physical arm realising the gated action (as in M3-D arm mapping)."""
    return {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}[
        final_deployed(final_action)]


__all__ = [
    "VARIANT", "RHO", "DELTA_THETA", "EXECUTED", "HOLD_GAIN", "HOLD_INVALID",
    "apply_gain_gate_v1", "final_deployed", "final_arm_key",
]