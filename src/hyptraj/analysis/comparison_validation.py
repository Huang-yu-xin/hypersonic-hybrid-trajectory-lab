"""Phase E numerical / regression audit infrastructure (E6).

Executes the complete Phase E derived analysis under multiple solver
configurations -- reusing the E1-E4 analysis APIs verbatim (this module
is an audit harness, NOT a second comparison implementation) -- and
assembles:

* high-precision numerical references (REF-0.1 / REF-0.05, same
  philosophy as the Phase D D6 reference),
* a 7-case audit matrix (tolerance side: P8-20 / P9-20 / P10-20;
  max-step side: P9-10 / P9-20 / P9-40; plus the two references),
* the production-vs-reference error table (P9-20 vs REF-0.1),
* protocol limiting-identity / hybrid-topology stability records,
* the production Phase E regression snapshot (P9-20 values).

The numerical reference is a NUMERICAL reference, not an analytic
solution and not physical truth; the production snapshot remains the
official Phase E regression reference (E6 §1, §28).
"""

from dataclasses import dataclass, field

import numpy as np

from hyptraj.analysis.comparison import (
    ComparisonTrajectory,
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    verify_comparison_alignment,
)
from hyptraj.analysis.comparison_diagnostics import (
    build_structural_diagnostics,
    native_aerodynamic_maxima,
    run_native_endpoint_comparison,
    windowed_aerodynamic_maxima,
)
from hyptraj.analysis.comparison_mechanisms import (
    build_energy_budget,
    exposure_diagnostic_at_common_range,
    exposure_diagnostic_at_common_time,
    run_common_atmospheric_exposure_comparison,
    total_vac_duration,
    total_vac_range,
)
from hyptraj.analysis.comparison_protocols import (
    run_common_range_comparison,
    run_common_time_comparison,
)
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.trajectory import SolverConfig

# ---------------------------------------------------------------------------
# High-precision reference configuration (E6 §3) -- identical philosophy
# to the Phase D D6 numerical reference (DOP853, rtol=1e-12, scaled
# atol, max_step 0.1 s).  NEVER written into PRODUCTION_SOLVER_CONFIG.
# ---------------------------------------------------------------------------
REFERENCE_SOLVER_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-12,
    atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
    max_step=0.1,
    dense_output=True,
)

# Self-stability companion: same tolerances, halved max_step.
REFERENCE_05_SOLVER_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-12,
    atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
    max_step=0.05,
    dense_output=True,
)


def make_solver_config(
    rtol: float, atol: list[float], max_step: float
) -> SolverConfig:
    """Audit-matrix config factory (DOP853, dense output)."""
    return SolverConfig(
        method="DOP853",
        rtol=rtol,
        atol=np.asarray(atol, dtype=float),
        max_step=max_step,
        dense_output=True,
    )


# The 7 audit cases (E6 §6).
AUDIT_CASES = {
    "REF-0.1": REFERENCE_SOLVER_CONFIG,
    "REF-0.05": REFERENCE_05_SOLVER_CONFIG,
    "P8-20": make_solver_config(1e-8, [1e-3, 1e-10, 1e-6, 1e-10], 20.0),
    "P9-20": PRODUCTION_SOLVER_CONFIG,
    "P10-20": make_solver_config(1e-10, [1e-5, 1e-12, 1e-8, 1e-12], 20.0),
    "P9-40": make_solver_config(1e-9, [1e-4, 1e-11, 1e-7, 1e-11], 40.0),
    "P9-10": make_solver_config(1e-9, [1e-4, 1e-11, 1e-7, 1e-11], 10.0),
}


# ---------------------------------------------------------------------------
# Full-case runner (reuses E1-E4 APIs only)
# ---------------------------------------------------------------------------
@dataclass
class AuditCaseResult:
    """All Phase E derived metrics under one solver configuration."""

    case: str
    solver: dict
    qian_terminal_kind: str
    sanger_terminal_kind: str
    sanger_skip_count: int
    sanger_mode_sequence: list
    qian_source_structure: list
    common_time_limiter: str
    common_range_limiter: str
    exposure_limiter: str
    protocol_d_qian_status: str
    protocol_d_sanger_status: str
    metrics: dict = field(default_factory=dict)
    checkpoint_modes: dict = field(default_factory=dict)
    root_residuals: dict = field(default_factory=dict)


def run_audit_case(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control,
    case: str,
) -> AuditCaseResult:
    """Run the complete Phase E analysis under one solver config."""
    solver_config = AUDIT_CASES[case]

    qian = build_qian_comparison_trajectory(
        env, vehicle, initial, control, solver_config=solver_config)
    sanger = build_sanger_comparison_trajectory(
        env, vehicle, initial, control, solver_config=solver_config)
    alignment = verify_comparison_alignment(qian, sanger)
    if not alignment.all_equal:
        raise RuntimeError(f"Case {case}: alignment failed.")

    # Protocol B / C / D (E2/E3 APIs).
    ct = run_common_time_comparison(qian, sanger)
    cr = run_common_range_comparison(qian, sanger)
    pd = run_common_atmospheric_exposure_comparison(qian, sanger)
    diag_time = exposure_diagnostic_at_common_time(qian, sanger, ct)
    diag_range = exposure_diagnostic_at_common_range(qian, sanger, cr)

    # Energy budgets + structural + aerodynamic (E3/E4 APIs).
    qian_budget = build_energy_budget(qian)
    sanger_budget = build_energy_budget(sanger)
    qian_struct = build_structural_diagnostics(qian)
    sanger_struct = build_structural_diagnostics(sanger)
    native = run_native_endpoint_comparison(qian, sanger)
    qian_aero = native_aerodynamic_maxima(qian)
    sanger_aero = native_aerodynamic_maxima(sanger)
    qian_ct_aero = windowed_aerodynamic_maxima(qian, ct.common_time_s)
    sanger_ct_aero = windowed_aerodynamic_maxima(sanger, ct.common_time_s)
    qian_cr_aero = windowed_aerodynamic_maxima(
        qian, cr.qian_arrival_time_s)
    sanger_cr_aero = windowed_aerodynamic_maxima(
        sanger, cr.sanger_arrival_time_s)

    # Sanger structure (events-based, frozen kinds).
    sanger_spec = sanger_struct.sanger_specific
    sanger_mode_sequence = [s.source_mode for s in sanger.dense_segments]
    qian_source_structure = [
        s.source_mode for s in qian.dense_segments
    ]

    vac_segments = [b for b in sanger_budget.segment_budgets
                    if b.normalized_mode == "VAC"]
    vac_max_rel_drift = max(abs(b.relative_energy_change)
                            for b in vac_segments) if vac_segments else 0.0

    def _limiter(q_value, s_value) -> str:
        return "qian" if q_value <= s_value else "sanger"

    metrics = {
        # Protocol B.
        "t_common": ct.common_time_s,
        "qian_R": ct.qian_state.range_m,
        "qian_h": ct.qian_state.altitude_m,
        "qian_v": ct.qian_state.velocity_mps,
        "qian_E": ct.qian_state.specific_mechanical_energy_jpkg,
        "qian_loss": ct.qian_energy_loss_jpkg,
        "sanger_R": ct.sanger_state.range_m,
        "sanger_h": ct.sanger_state.altitude_m,
        "sanger_v": ct.sanger_state.velocity_mps,
        "sanger_E": ct.sanger_state.specific_mechanical_energy_jpkg,
        "sanger_loss": ct.sanger_energy_loss_jpkg,
        "DeltaR_time": ct.delta_range_m,
        "DeltaH_time": ct.delta_altitude_m,
        "DeltaV_time": ct.delta_velocity_mps,
        "DeltaE_time": ct.delta_specific_energy_jpkg,
        # Protocol C.
        "R_common": cr.common_range_m,
        "t_Q": cr.qian_arrival_time_s,
        "t_S": cr.sanger_arrival_time_s,
        "time_saving": cr.time_saving_s,
        "DeltaH_range": cr.delta_altitude_m,
        "DeltaV_range": cr.delta_velocity_mps,
        "DeltaE_range": cr.delta_specific_energy_jpkg,
        # Protocol D.
        "tau_common": pd.common_exposure_s,
        "pd_t_Q": pd.qian_time_s,
        "pd_t_S": pd.sanger_time_s,
        "elapsed_time_extension": pd.elapsed_time_extension_s,
        "DeltaR_atm_exposure": pd.delta_range_m,
        "DeltaH_tau": pd.delta_altitude_m,
        "DeltaV_tau": pd.delta_velocity_mps,
        "DeltaE_tau": pd.delta_specific_energy_jpkg,
        # E3 mechanism.
        "qian_total_loss": qian_budget.total_energy_loss_jpkg,
        "sanger_total_loss": sanger_budget.total_energy_loss_jpkg,
        "sanger_atm_duration": sanger_budget.atm.duration_s,
        "sanger_vac_duration": total_vac_duration(sanger),
        "sanger_vac_range": total_vac_range(sanger),
        "sanger_vac_max_rel_drift": vac_max_rel_drift,
        "tau_at_common_time_qian": diag_time.qian_exposure_s,
        "tau_at_common_time_sanger": diag_time.sanger_exposure_s,
        "tau_at_common_range_qian": diag_range.qian_exposure_s,
        "tau_at_common_range_sanger": diag_range.sanger_exposure_s,
        # Structural.
        "qian_h_min": qian_struct.min_altitude.value_m,
        "qian_h_max": qian_struct.max_altitude.value_m,
        "qian_v_min": qian_struct.min_velocity_mps,
        "sanger_h_min": sanger_struct.min_altitude.value_m,
        "sanger_h_max": sanger_struct.max_altitude.value_m,
        "sanger_v_min": sanger_struct.min_velocity_mps,
        "qian_atm_fraction": qian_struct.ATM_fraction,
        "sanger_atm_fraction": sanger_struct.ATM_fraction,
        "sanger_vac_fraction": sanger_struct.VAC_fraction,
        # Aerodynamic (native window).
        "qian_q_max": qian_aero["max_q"].value,
        "sanger_q_max": sanger_aero["max_q"].value,
        "qian_aD_max": qian_aero["max_aD"].value,
        "sanger_aD_max": sanger_aero["max_aD"].value,
        "qian_q_max_time": qian_aero["max_q"].time_s,
        "sanger_q_max_time": sanger_aero["max_q"].time_s,
        "qian_q_max_alt": qian_aero["max_q"].altitude_m,
        "sanger_q_max_alt": sanger_aero["max_q"].altitude_m,
        # Common-window aerodynamic maxima.
        "ct_qian_q_max": qian_ct_aero["max_q"].value,
        "ct_sanger_q_max": sanger_ct_aero["max_q"].value,
        "cr_qian_q_max": qian_cr_aero["max_q"].value,
        "cr_sanger_q_max": sanger_cr_aero["max_q"].value,
        # Native endpoint.
        "qian_capture_time": qian.events[0].time_s,
        "qian_terminal_time": native.qian_terminal.time_s,
        "qian_terminal_range": native.qian_terminal.range_m,
        "sanger_terminal_time": native.sanger_terminal.time_s,
        "sanger_terminal_range": native.sanger_terminal.range_m,
    }

    return AuditCaseResult(
        case=case,
        solver={
            "method": solver_config.method,
            "rtol": solver_config.rtol,
            "atol": [float(a) for a in solver_config.atol],
            "max_step": solver_config.max_step,
        },
        qian_terminal_kind=qian.terminal_kind,
        sanger_terminal_kind=sanger.terminal_kind,
        sanger_skip_count=sanger_spec["skip_count"],
        sanger_mode_sequence=sanger_mode_sequence,
        qian_source_structure=qian_source_structure,
        common_time_limiter=_limiter(qian.terminal_time_s,
                                     sanger.terminal_time_s),
        common_range_limiter=_limiter(
            qian.range_at_time(qian.terminal_time_s),
            sanger.range_at_time(sanger.terminal_time_s)),
        exposure_limiter=_limiter(qian.total_atmospheric_exposure(),
                                  sanger.total_atmospheric_exposure()),
        protocol_d_qian_status=pd.qian_inverse_status.value,
        protocol_d_sanger_status=pd.sanger_inverse_status.value,
        metrics=metrics,
        checkpoint_modes={
            "common_time": {
                "qian": (ct.qian_source_mode, ct.qian_mode),
                "sanger": (ct.sanger_source_mode, ct.sanger_mode),
            },
            "common_range": {
                "qian": (cr.qian_source_mode, cr.qian_mode),
                "sanger": (cr.sanger_source_mode, cr.sanger_mode),
            },
            "protocol_d": {
                "qian": (pd.qian_source_mode, pd.qian_mode),
                "sanger": (pd.sanger_source_mode, pd.sanger_mode),
            },
        },
        root_residuals={
            "qian": cr.qian_range_residual_m,
            "sanger": cr.sanger_range_residual_m,
        },
    )


# ---------------------------------------------------------------------------
# Cross-phase independent reference checks (E6 §4)
# ---------------------------------------------------------------------------
def cross_phase_qian_check(
    ref_case: AuditCaseResult, phase_c_reference: dict
) -> dict:
    """Qian REF-0.1 vs the Phase C numerical reference (same config)."""
    m = ref_case.metrics
    return {
        "capture_time_diff_s": abs(
            m["qian_capture_time"] - phase_c_reference["capture_time_s"]),
        "rti_time_diff_s": abs(
            m["qian_terminal_time"] - phase_c_reference["rti_time_s"]),
        "rti_range_diff_m": abs(
            m["qian_terminal_range"] - phase_c_reference["rti_range_m"]),
    }


def cross_phase_sanger_check(
    ref_case: AuditCaseResult, phase_d_reference: dict
) -> dict:
    """Sanger REF-0.1 vs the Phase D D6 reference."""
    m = ref_case.metrics
    return {
        "srti_time_diff_s": abs(
            m["sanger_terminal_time"] - phase_d_reference["research_time_s"]),
        "srti_range_diff_m": abs(
            m["sanger_terminal_range"]
            - phase_d_reference["research_range_m"]),
        "max_altitude_diff_m": abs(
            m["sanger_h_max"] - phase_d_reference["max_altitude_m"]),
        "topology_equal": (
            ref_case.sanger_terminal_kind == "SRTI"
            and ref_case.sanger_skip_count
            == phase_d_reference["skip_count"]
            and ref_case.sanger_mode_sequence
            == phase_d_reference["mode_sequence"]
        ),
    }
