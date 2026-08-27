"""M3-G -- Gain-Aware HOLD Decision (preregistered task
M3_G_Gain_Aware_HOLD_Decision_Task.md).

Layers
------
gain_proxy     finite-step gain proxies GA1 (|g*dtheta|/M2) and GA2
                (conservative signed-gain CI end), plus the frozen
                fixed-stratified per-replicate recomputation for the
                online diagnostic CI of Delta_rel
gain_gate      execution gate on top of the FROZEN M3-D direction: only
                EXECUTE vs HOLD_GAIN vs HOLD_INVALID; direction never
                reclassified; HOLD_* pass through with reason preserved
metrics        calibration rows (9-candidate table), the preregistered
                selection rule, per-state/per-class summaries
calibration    offline driver over the STORED M3-D Layer-A batch only;
                hard invariant extra_simulator_calls == 0

FIREWALL: the gate consumes ONLY frozen estimator outputs (g_hat, g-CI,
ESS, action, base-arm evaluation M2).  No reference / oracle field may
enter any gating API (structural test enforces it).
"""

from hyptraj.m3g.gain_proxy import (
    DELTA_THETA_MAIN,
    bootstrap_gain_replicates,
    ga1_magnitude,
    ga2_upper_end,
    signed_delta_rel,
    step_delta_theta,
)
from hyptraj.m3g.gain_gate import (
    GA1,
    GA2,
    VARIANTS,
    apply_gain_gate,
    deployed_final,
    final_arm_key,
)
from hyptraj.m3g.metrics import (
    RHO_GRID,
    VARIANT_GRID,
    arm_legal_at,
    build_calibration_table,
    candidate_metrics,
    gate_from_stored_record,
    per_class_summary,
    per_state_summary,
    select_candidate,
)
from hyptraj.m3g.calibration import (
    run_offline_calibration,
    load_calibration_batch,
    freeze_payload,
)

__all__ = [
    "DELTA_THETA_MAIN", "bootstrap_gain_replicates", "ga1_magnitude",
    "ga2_upper_end", "signed_delta_rel", "step_delta_theta",
    "GA1", "GA2", "VARIANTS", "apply_gain_gate", "deployed_final",
    "final_arm_key",
    "RHO_GRID", "VARIANT_GRID", "arm_legal_at", "build_calibration_table",
    "candidate_metrics", "gate_from_stored_record", "per_class_summary",
    "per_state_summary", "select_candidate",
    "run_offline_calibration", "load_calibration_batch", "freeze_payload",
]