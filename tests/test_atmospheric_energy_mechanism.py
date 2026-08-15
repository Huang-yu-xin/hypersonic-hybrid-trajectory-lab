"""E3 tests: atmospheric exposure and energy mechanism analysis.

Covers the frozen E0 Protocol D (common atmospheric exposure), the E2
checkpoint exposure diagnostics, segment-level mechanical-energy
accounting, and the Sanger VAC-coast structure.

    A  tau_common uses min terminal exposure.
    B  Protocol D requires UNIQUE inverse.
    C  PLATEAU inverse cannot silently produce checkpoint.
    D  Protocol D states reproduce tau_common.
    E  DeltaR_atm_exposure sign convention correct.
    F  elapsed-time extension sign convention correct.
    G  same-time exposure diagnostic uses E2 t_common.
    H  same-range diagnostic uses E2 arrival times.
    I  Qian elapsed minus exposure ~= 0.
    J  Sanger elapsed minus exposure = VAC duration before checkpoint.
    K  segment energy losses telescope to total loss.
    L  Qian VAC aggregate exactly absent.
    M  Sanger VAC delta_range positive.
    N  Sanger VAC mechanical energy conserved numerically.
    O  raw VAC energy drift is not clipped.
    P  plotting curve samples do not drive formal checkpoints.
    Q  all outputs finite.
    R  analysis does not mutate ComparisonTrajectory/E2 results.
"""

from unittest import mock

import numpy as np
import pytest

from hyptraj.analysis import (
    AtmosphericExposureInverseResult,
    AtmosphericExposureInverseStatus,
    ComparisonTrajectory,
    ProtocolDStatus,
    build_energy_budget,
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    energy_curve_samples,
    exposure_diagnostic_at_common_range,
    exposure_diagnostic_at_common_time,
    run_common_atmospheric_exposure_comparison,
    run_common_range_comparison,
    run_common_time_comparison,
    total_vac_duration,
    total_vac_range,
    vac_duration_before_time,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

# Numerical-invariance scales.
TAU_TOL_S = 1e-6
VAC_ENERGY_DRIFT_TOL_JPKG = 1e-3  # raw drift ~1e-8 J/kg; generous bound


@pytest.fixture(scope="module")
def trajectories():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    qian = build_qian_comparison_trajectory(env, vehicle, initial, control)
    sanger = build_sanger_comparison_trajectory(env, vehicle, initial, control)
    return qian, sanger


@pytest.fixture(scope="module")
def e2_results(trajectories):
    qian, sanger = trajectories
    return (
        run_common_time_comparison(qian, sanger),
        run_common_range_comparison(qian, sanger),
    )


@pytest.fixture(scope="module")
def protocol_d(trajectories):
    qian, sanger = trajectories
    return run_common_atmospheric_exposure_comparison(qian, sanger)


@pytest.fixture(scope="module")
def budgets(trajectories):
    qian, sanger = trajectories
    return build_energy_budget(qian), build_energy_budget(sanger)


# ---------------------------------------------------------------------------
# A / B / C. Protocol D definition and inverse requirements
# ---------------------------------------------------------------------------
def test_a_tau_common_uses_min_terminal_exposure(trajectories, protocol_d):
    qian, sanger = trajectories
    expected = min(qian.total_atmospheric_exposure(),
                   sanger.total_atmospheric_exposure())
    assert protocol_d.common_exposure_s == expected
    assert protocol_d.common_exposure_s == qian.total_atmospheric_exposure()
    assert not np.isclose(protocol_d.common_exposure_s,
                          sanger.total_atmospheric_exposure())


def test_b_protocol_d_requires_unique_inverse(protocol_d):
    assert protocol_d.status == ProtocolDStatus.UNIQUE
    assert protocol_d.qian_inverse_status == \
        AtmosphericExposureInverseStatus.UNIQUE
    assert protocol_d.sanger_inverse_status == \
        AtmosphericExposureInverseStatus.UNIQUE


def test_c_plateau_inverse_cannot_silently_produce_checkpoint(
    trajectories,
):
    qian, sanger = trajectories
    plateau = AtmosphericExposureInverseResult(
        status=AtmosphericExposureInverseStatus.PLATEAU,
        tau_s=100.0,
        plateau_start_s=50.0,
        plateau_end_s=90.0,
    )

    def fake_inverse(self, tau):
        return plateau

    with mock.patch.object(ComparisonTrajectory,
                           "time_at_atmospheric_exposure",
                           fake_inverse):
        result = run_common_atmospheric_exposure_comparison(qian, sanger)
    assert result.status == ProtocolDStatus.AMBIGUOUS
    assert result.qian_time_s is None
    assert result.sanger_time_s is None
    assert result.qian_state is None
    # The plateau interval is attached explicitly, no arbitrary time.
    assert result.qian_plateau_interval_s == (50.0, 90.0)
    assert result.sanger_plateau_interval_s == (50.0, 90.0)
    assert result.elapsed_time_extension_s is None


# ---------------------------------------------------------------------------
# D / E / F. Protocol D checkpoint consistency and sign conventions
# ---------------------------------------------------------------------------
def test_d_protocol_d_states_reproduce_tau_common(trajectories, protocol_d):
    qian, sanger = trajectories
    assert abs(qian.atmospheric_exposure_at_time(protocol_d.qian_time_s)
               - protocol_d.common_exposure_s) < TAU_TOL_S
    assert abs(sanger.atmospheric_exposure_at_time(protocol_d.sanger_time_s)
               - protocol_d.common_exposure_s) < TAU_TOL_S


def test_e_delta_r_atm_exposure_sign_convention(protocol_d):
    # E0 §11: DeltaR_atm_exposure = R_S - R_Q (positive: Sanger gained
    # more range for the same cumulative atmospheric-mode exposure).
    assert protocol_d.delta_range_m == pytest.approx(
        protocol_d.sanger_state.range_m
        - protocol_d.qian_state.range_m, rel=1e-12
    )
    assert protocol_d.delta_range_m > 0.0


def test_f_elapsed_time_extension_sign_convention(protocol_d):
    # E3 §5: elapsed_time_extension = t_S - t_Q (positive: Sanger used
    # VAC coast to gain longer elapsed flight time at equal exposure).
    assert protocol_d.elapsed_time_extension_s == pytest.approx(
        protocol_d.sanger_time_s - protocol_d.qian_time_s, rel=1e-12
    )
    assert protocol_d.elapsed_time_extension_s > 0.0


# ---------------------------------------------------------------------------
# G / H. E2 checkpoint exposure diagnostics
# ---------------------------------------------------------------------------
def test_g_same_time_diagnostic_uses_e2_t_common(trajectories, e2_results):
    qian, sanger = trajectories
    common_time, _ = e2_results
    diag = exposure_diagnostic_at_common_time(qian, sanger, common_time)
    assert diag.checkpoint == "common_time"
    assert diag.qian_time_s == common_time.common_time_s
    assert diag.sanger_time_s == common_time.common_time_s


def test_h_same_range_diagnostic_uses_e2_arrival_times(
    trajectories, e2_results
):
    qian, sanger = trajectories
    _, common_range = e2_results
    diag = exposure_diagnostic_at_common_range(qian, sanger, common_range)
    assert diag.checkpoint == "common_range"
    assert diag.qian_time_s == common_range.qian_arrival_time_s
    assert diag.sanger_time_s == common_range.sanger_arrival_time_s


# ---------------------------------------------------------------------------
# I / J. Elapsed/exposure/VAC identities
# ---------------------------------------------------------------------------
def test_i_qian_elapsed_minus_exposure_is_zero(trajectories, e2_results,
                                               protocol_d):
    qian, _ = trajectories
    common_time, common_range = e2_results
    # Qian research domain is fully ATM: elapsed - exposure ~= 0 at
    # every checkpoint.
    for t in (common_time.common_time_s,
              common_range.qian_arrival_time_s,
              protocol_d.qian_time_s):
        assert abs((t - qian.initial_time_s)
                   - qian.atmospheric_exposure_at_time(t)) < TAU_TOL_S


def test_j_sanger_elapsed_minus_exposure_equals_vac_duration(
    trajectories, e2_results, protocol_d
):
    sanger, _ = trajectories[::-1]
    common_time, common_range = e2_results
    # Same-time checkpoint: t_common inside ATM1 after VAC0.
    t_common = common_time.common_time_s
    assert abs((t_common - sanger.initial_time_s)
               - sanger.atmospheric_exposure_at_time(t_common)
               - vac_duration_before_time(sanger, t_common)) < TAU_TOL_S
    assert abs(vac_duration_before_time(sanger, t_common)
               - (sanger.dense_segments[1].t_end
                  - sanger.dense_segments[1].t_start)) < TAU_TOL_S
    # Protocol D checkpoint identity (E3 §19):
    # t_S(tau_common) - tau_common == VAC duration before the checkpoint.
    assert abs(protocol_d.sanger_time_s - protocol_d.common_exposure_s
               - vac_duration_before_time(sanger,
                                          protocol_d.sanger_time_s)
               ) < TAU_TOL_S


# ---------------------------------------------------------------------------
# K / L / M / N / O. Energy budgets
# ---------------------------------------------------------------------------
def test_k_segment_energy_losses_telescope(budgets):
    for budget in budgets:
        assert abs(budget.telescoping_residual_jpkg) < 1e-3
        assert budget.total_energy_loss_jpkg == pytest.approx(
            budget.initial_energy_jpkg - budget.terminal_energy_jpkg,
            rel=1e-12
        )
        assert budget.atm.raw_energy_loss_jpkg + \
            budget.vac.raw_energy_loss_jpkg == pytest.approx(
                budget.total_energy_loss_jpkg, abs=1e-6
            )


def test_l_qian_vac_aggregate_exactly_absent(budgets):
    qian_budget, _ = budgets
    # Qian research domain is ATM-only: the VAC aggregate is exactly
    # zero (produced by segment aggregation, not hard-coded).
    assert qian_budget.vac.duration_s == 0.0
    assert qian_budget.vac.range_increment_m == 0.0
    assert qian_budget.vac.raw_energy_loss_jpkg == 0.0
    assert all(b.normalized_mode == "ATM"
               for b in qian_budget.segment_budgets)


def test_m_sanger_vac_delta_range_positive(budgets, trajectories):
    _, sanger_budget = budgets
    _, sanger = trajectories
    assert total_vac_range(sanger) > 0.0
    for seg in sanger_budget.segment_budgets:
        if seg.normalized_mode == "VAC":
            assert seg.delta_range_m > 0.0
    assert sanger_budget.vac.range_increment_m == pytest.approx(
        total_vac_range(sanger), rel=1e-9
    )


def test_n_sanger_vac_energy_conserved_numerically(budgets):
    _, sanger_budget = budgets
    vac_segments = [b for b in sanger_budget.segment_budgets
                    if b.normalized_mode == "VAC"]
    assert len(vac_segments) == 2
    for seg in vac_segments:
        # Energy conserved to numerical precision (raw drift ~1e-8 J/kg).
        assert abs(seg.raw_energy_loss_jpkg) < VAC_ENERGY_DRIFT_TOL_JPKG
        assert abs(seg.relative_energy_change) < 1e-12


def test_o_raw_vac_energy_drift_not_clipped(budgets):
    _, sanger_budget = budgets
    vac_segments = [b for b in sanger_budget.segment_budgets
                    if b.normalized_mode == "VAC"]
    for seg in vac_segments:
        # The stored raw loss equals E_start - E_end exactly (signed,
        # never max(0, ...) and never forced to zero).
        assert seg.raw_energy_loss_jpkg == pytest.approx(
            seg.energy_start_jpkg - seg.energy_end_jpkg, rel=1e-15
        )
    # Under the frozen realization the drift is a tiny negative number;
    # it is preserved with its true sign.
    assert all(seg.raw_energy_loss_jpkg < 1e-6 for seg in vac_segments)


# ---------------------------------------------------------------------------
# P. Plotting curve samples are visualization-only
# ---------------------------------------------------------------------------
def test_p_curve_samples_do_not_drive_formal_checkpoints(
    trajectories, protocol_d
):
    qian, sanger = trajectories
    for trajectory, n_segments in ((qian, 2), (sanger, 5)):
        curve = energy_curve_samples(trajectory, points_per_segment=50)
        expected_rows = n_segments * 50 - (n_segments - 1)
        assert curve["time_s"].size == expected_rows
        # De-duplicated switch times: no repeated time rows.
        assert np.unique(curve["time_s"]).size == curve["time_s"].size
        # Exact boundary states are preferred at switches/terminal.
        last = trajectory.dense_segments[-1]
        assert np.isclose(curve["time_s"][-1], last.t_end)
        # The curve sampling is deterministic.
        again = energy_curve_samples(trajectory, points_per_segment=50)
        assert np.array_equal(curve["time_s"], again["time_s"])

    # The Sanger Protocol-D checkpoint time is an exposure-inverse root
    # (t = 1071.4 s inside ATM2), NOT a curve grid node: visualization
    # samples never feed back into formal checkpoints.  (The Qian
    # checkpoint coincides with the RTI terminal row, which is the
    # exact terminal state by design.)
    s_curve = energy_curve_samples(sanger, points_per_segment=50)
    assert not np.any(np.isclose(s_curve["time_s"],
                                 protocol_d.sanger_time_s, atol=1e-9))
    # The checkpoint states are the continuous evaluations themselves.
    assert np.allclose(qian.state_at_time(protocol_d.qian_time_s).state_raw,
                       protocol_d.qian_state.state_raw)
    assert np.allclose(sanger.state_at_time(protocol_d.sanger_time_s)
                       .state_raw, protocol_d.sanger_state.state_raw)


# ---------------------------------------------------------------------------
# Q. Finiteness
# ---------------------------------------------------------------------------
def test_q_all_outputs_finite(trajectories, e2_results, protocol_d, budgets):
    qian, sanger = trajectories
    common_time, common_range = e2_results
    for diag in (
        exposure_diagnostic_at_common_time(qian, sanger, common_time),
        exposure_diagnostic_at_common_range(qian, sanger, common_range),
    ):
        for field in diag.__dataclass_fields__:
            value = getattr(diag, field)
            if isinstance(value, float):
                assert np.isfinite(value), field
    for result in (protocol_d,):
        assert result.status == ProtocolDStatus.UNIQUE
        assert np.isfinite(result.elapsed_time_extension_s)
        assert np.isfinite(result.delta_range_m)
        for state in (result.qian_state, result.sanger_state):
            assert np.isfinite(state.state_raw).all()
    for budget in budgets:
        assert np.isfinite(budget.total_energy_loss_jpkg)
        assert np.isfinite(budget.telescoping_residual_jpkg)


# ---------------------------------------------------------------------------
# R. No mutation
# ---------------------------------------------------------------------------
def test_r_analysis_does_not_mutate(trajectories, e2_results, protocol_d,
                                    budgets):
    qian, sanger = trajectories
    common_time, common_range = e2_results
    # Re-running is deterministic and the trajectories are untouched.
    pd2 = run_common_atmospheric_exposure_comparison(qian, sanger)
    assert pd2.common_exposure_s == protocol_d.common_exposure_s
    assert pd2.delta_range_m == protocol_d.delta_range_m
    assert qian.terminal_kind == "RTI" and sanger.terminal_kind == "SRTI"
    assert np.isfinite(qian.terminal_state).all()
    assert np.isfinite(sanger.terminal_state).all()
    assert qian.total_atmospheric_exposure() > 0.0
    assert total_vac_duration(sanger) > 0.0
    assert total_vac_duration(qian) == 0.0
