"""M3-G-v1 -- online pipeline wrapper (confirmatory evaluation).

The direction estimation is the FROZEN M3-D path verbatim
(``hyptraj.m3d.adaptation.gradient_decision``); the v1 gain gate only
filters the resulting direction with the pilot-M2-normalised proxy.
``v1_trial_gate`` additionally requires the frozen direction block to be
bitwise identical to what ``gradient_decision`` returns (parity guard).
Label/reference-book fields never enter this API.
"""

from __future__ import annotations

from hyptraj.m3d.adaptation import gradient_decision
from hyptraj.m3g_v1.gain_gate import apply_gain_gate_v1

PARITY_FIELDS = ("g_hat", "g_ci_low", "g_ci_high", "ESS_grad", "decision")


def v1_trial_gate(st, seed: int, z, logp, logr, source_strata,
                  *, arm_legal: bool = True, delta_theta: float = 0.20,
                  rho: float = 0.02) -> dict:
    """Frozen direction + v1 GA1 gate; asserts direction-layer parity."""
    gd = gradient_decision(st, int(seed), z, logp, logr, source_strata)
    gr = gd["gradient"]
    gain = apply_gain_gate_v1(
        direction=str(gr["decision"]), g_hat=float(gr["g_hat"]),
        m2_pilot=float(gr["M2_hat"]), delta_theta=delta_theta, rho=rho,
        arm_legal=bool(arm_legal))
    parity = {f: (float(gr[f]) if f != "decision"
                  else str(gr["decision"])) for f in PARITY_FIELDS}
    return {"gradient": gr, "gain": gain, "parity_block": parity}


__all__ = ["PARITY_FIELDS", "v1_trial_gate"]