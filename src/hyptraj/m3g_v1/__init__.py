"""M3-G-v1 -- exact-proxy recovery (confirmatory), frozen candidate
GA1 / rho=0.02 / pilot M2_hat denominator.

Modules
-------
gain_gate    v1 gate: HOLD passthrough -> HOLD_GAIN(Delta_rel<0.02) ->
             EXECUTE frozen direction; NO GA2, NO calibration grid,
             NO eval-M2 (whitelisted signature)
pipeline     frozen M3-D direction path + v1 gate (parity-guarded)
metrics      raretopo-m3g-v1 record schema

FIREWALL: no oracle / reference field and no evaluation-arm M2 may enter
any gate API; discovery seeds/results are never consumed by the v1 gate.
"""

from hyptraj.m3g_v1.gain_gate import (
    VARIANT,
    RHO,
    DELTA_THETA,
    EXECUTED,
    HOLD_GAIN,
    HOLD_INVALID,
    apply_gain_gate_v1,
    final_deployed,
    final_arm_key,
)
from hyptraj.m3g_v1.metrics import (
    RECORD_SCHEMA_VERSION,
    ARM_KEYS,
    ACTION_ENUM,
    build_m3g_v1_trial_record,
    validate_m3g_v1_trial_record,
)
from hyptraj.m3g_v1.pipeline import (
    PARITY_FIELDS,
    v1_trial_gate,
)

__all__ = [
    "VARIANT", "RHO", "DELTA_THETA", "EXECUTED", "HOLD_GAIN", "HOLD_INVALID",
    "apply_gain_gate_v1", "final_deployed", "final_arm_key",
    "RECORD_SCHEMA_VERSION", "ARM_KEYS", "ACTION_ENUM",
    "build_m3g_v1_trial_record", "validate_m3g_v1_trial_record",
    "PARITY_FIELDS", "v1_trial_gate",
]