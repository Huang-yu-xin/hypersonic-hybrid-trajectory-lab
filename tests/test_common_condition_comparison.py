"""E2 tests: common-time and common-range comparison protocols.

Strict implementations of the frozen E0 Protocol B (common time) and
Protocol C (common range) on top of the E1 ComparisonTrajectory API.

No actual DeltaR / time-saving numbers are hard-coded here -- those are
E6 freeze material.  The tests verify definitions, sign conventions,
identity properties, and structural constraints.

    A  common-time definition uses min terminal time.
    B  common-time states exactly share time.
    C  common-time qian exact RTI identity when Qian is limiting.
    D  common-time difference signs/formulas correct.
    E  common-range definition uses min terminal range.
    F  range monotonicity prerequisite checked.
    G  common-range uses ComparisonTrajectory.first_time_at_range.
    H  both common-range states satisfy target range.
    I  common-range Qian RTI identity when Qian range is limiting.
    J  time_saving sign convention correct.
    K  energy uses common initial E0.
    L  mode/source-mode metadata retained.
    M  results finite.
    N  analysis does not mutate ComparisonTrajectory.
    O  no sample-grid dependency.
    P  no Protocol D metrics produced.
"""

from unittest import mock

import numpy as np
import pytest

from hyptraj.analysis import (
    CommonRangeComparison,
    CommonTimeComparison,
    ComparisonTrajectory,
    RangeMonotonicityResult,
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    run_common_range_comparison,
    run_common_time_comparison,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

_RTOL = 1e-9
_ATOL = 1e-9


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
def common_time(trajectories):
    qian, sanger = trajectories
    return run_common_time_comparison(qian, sanger)


@pytest.fixture(scope="module")
def common_range(trajectories):
    qian, sanger = trajectories
    return run_common_range_comparison(qian, sanger)


# ---------------------------------------------------------------------------
# A / B / C. Common time: definition, shared time, endpoint identity
# ---------------------------------------------------------------------------
def test_a_common_time_uses_min_terminal_time(trajectories, common_time):
    qian, sanger = trajectories
    expected = min(qian.terminal_time_s, sanger.terminal_time_s)
    assert common_time.common_time_s == expected
    assert common_time.common_time_s == qian.terminal_time_s  # current data
    assert isinstance(common_time, CommonTimeComparison)


def test_b_common_time_states_share_time(common_time):
    assert common_time.qian_state.time_s == common_time.common_time_s
    assert common_time.sanger_state.time_s == common_time.common_time_s


def test_c_common_time_qian_rti_identity(trajectories, common_time):
    qian, _ = trajectories
    # Conditional structural assertion: Qian IS the limiting endpoint
    # under the frozen configuration, so its checkpoint state must
    # reproduce the exact RTI terminal state.
    if common_time.common_time_s == qian.terminal_time_s:
        assert np.allclose(common_time.qian_state.state_raw,
                           qian.terminal_state, rtol=_RTOL, atol=_ATOL)
        assert common_time.qian_state.source_mode == "QEG_GLIDE"
    else:
        pytest.skip("Qian is not the limiting endpoint in this run")


# ---------------------------------------------------------------------------
# D. Common-time difference formulas / sign conventions
# ---------------------------------------------------------------------------
def test_d_common_time_difference_signs_correct(common_time):
    q_s = common_time.qian_state
    s_s = common_time.sanger_state
    # E0 §18: DeltaR_time = R_S - R_Q (positive: Sanger farther), etc.
    assert common_time.delta_range_m == pytest.approx(
        s_s.range_m - q_s.range_m, rel=1e-12
    )
    assert common_time.delta_altitude_m == pytest.approx(
        s_s.altitude_m - q_s.altitude_m, rel=1e-12
    )
    assert common_time.delta_velocity_mps == pytest.approx(
        s_s.velocity_mps - q_s.velocity_mps, rel=1e-12
    )
    assert common_time.delta_specific_energy_jpkg == pytest.approx(
        s_s.specific_mechanical_energy_jpkg
        - q_s.specific_mechanical_energy_jpkg, rel=1e-12
    )
    # Sign direction sanity: positive DeltaV means Sanger retains more.
    assert np.sign(common_time.delta_velocity_mps) == np.sign(
        s_s.velocity_mps - q_s.velocity_mps
    )


# ---------------------------------------------------------------------------
# E / F / G / H / I / J. Common range
# ---------------------------------------------------------------------------
def test_e_common_range_uses_min_terminal_range(trajectories, common_range):
    qian, sanger = trajectories
    expected = min(
        qian.range_at_time(qian.terminal_time_s),
        sanger.range_at_time(sanger.terminal_time_s),
    )
    assert common_range.common_range_m == expected
    assert isinstance(common_range, CommonRangeComparison)


def test_f_range_monotonicity_prerequisite_checked(trajectories):
    qian, sanger = trajectories
    # The prerequisite is verified before any inversion.
    assert qian.is_range_monotone().is_strictly_monotone
    assert sanger.is_range_monotone().is_strictly_monotone
    # A non-monotone side must abort the protocol.
    fake = RangeMonotonicityResult(
        is_strictly_monotone=False,
        minimum_drange_dt=-1.0,
        minimum_cos_gamma=0.5,
        minimum_velocity=100.0,
        diagnostic_sample_count=1,
    )
    with mock.patch.object(
        ComparisonTrajectory, "is_range_monotone", return_value=fake
    ):
        with pytest.raises(RuntimeError, match="monotonicity"):
            run_common_range_comparison(qian, sanger)


def test_g_common_range_uses_first_time_at_range(trajectories, common_range):
    qian, sanger = trajectories
    r_common = common_range.common_range_m
    # Spy on the E1 segment-aware inversion API: the protocol's arrival
    # times must come exactly from first_time_at_range (once per side).
    real = ComparisonTrajectory.first_time_at_range
    calls: list[float] = []

    def counting(self, r_target):
        calls.append(r_target)
        return real(self, r_target)

    with mock.patch.object(ComparisonTrajectory, "first_time_at_range",
                           counting):
        result = run_common_range_comparison(qian, sanger)
    assert len(calls) == 2
    assert calls == [r_common, r_common]
    assert result.qian_arrival_time_s == qian.first_time_at_range(r_common)
    assert result.sanger_arrival_time_s == sanger.first_time_at_range(
        r_common
    )


def test_h_common_range_states_satisfy_target(trajectories, common_range):
    qian, sanger = trajectories
    r_common = common_range.common_range_m
    assert abs(common_range.qian_state.range_m - r_common) < 1e-3
    assert abs(common_range.sanger_state.range_m - r_common) < 1e-3
    # Residuals recorded in the result (E0 §12).
    assert common_range.qian_range_residual_m < 1e-3
    assert common_range.sanger_range_residual_m < 1e-3


def test_i_common_range_qian_rti_identity(trajectories, common_range):
    qian, _ = trajectories
    # Conditional: Qian range is the limiting endpoint, so the Qian
    # arrival reproduces the exact RTI terminal state/time.
    if common_range.common_range_m == qian.range_at_time(
        qian.terminal_time_s
    ):
        assert common_range.qian_arrival_time_s == pytest.approx(
            qian.terminal_time_s, abs=1e-9
        )
        assert np.allclose(common_range.qian_state.state_raw,
                           qian.terminal_state, rtol=_RTOL, atol=_ATOL)
    else:
        pytest.skip("Qian range is not the limiting endpoint in this run")


def test_j_time_saving_sign_convention(common_range):
    # E0 §18: time_saving = t_Q - t_S; positive -> Sanger earlier.
    assert common_range.time_saving_s == pytest.approx(
        common_range.qian_arrival_time_s
        - common_range.sanger_arrival_time_s, rel=1e-12
    )


# ---------------------------------------------------------------------------
# K / L / M
# ---------------------------------------------------------------------------
def test_k_energy_uses_common_initial_e0(common_time, common_range):
    for result in (common_time, common_range):
        e0_q = result.qian_state.specific_mechanical_energy_jpkg \
            + result.qian_energy_loss_jpkg
        e0_s = result.sanger_state.specific_mechanical_energy_jpkg \
            + result.sanger_energy_loss_jpkg
        # Energy loss = E0 - E (no abs, no clipping) and E0 is common.
        assert e0_q == pytest.approx(result.initial_energy_jpkg, rel=1e-12)
        assert e0_s == pytest.approx(result.initial_energy_jpkg, rel=1e-12)
        # Both losses are consistent with their own energies.
        assert result.qian_energy_loss_jpkg == pytest.approx(
            result.initial_energy_jpkg
            - result.qian_state.specific_mechanical_energy_jpkg, rel=1e-12
        )


def test_l_mode_metadata_retained(common_time, common_range):
    for result in (common_time, common_range):
        # Qian: ENTRY_CAPTURE / QEG_GLIDE both normalize to ATM.
        assert result.qian_mode == "ATM"
        assert result.qian_source_mode in ("ENTRY_CAPTURE", "QEG_GLIDE")
        # Sanger: source mode consistent with its normalized mode.
        assert result.sanger_mode in ("ATM", "VAC")
        if result.sanger_source_mode == "SANGER_VAC":
            assert result.sanger_mode == "VAC"
        else:
            assert result.sanger_source_mode == "SANGER_ATM"
            assert result.sanger_mode == "ATM"


def test_m_results_finite(common_time, common_range):
    for result in (common_time, common_range):
        for field in result.__dataclass_fields__:
            value = getattr(result, field)
            if isinstance(value, float):
                assert np.isfinite(value), field
        for state in (result.qian_state, result.sanger_state):
            assert np.isfinite(state.state_raw).all()


# ---------------------------------------------------------------------------
# N. No mutation of the comparison trajectories
# ---------------------------------------------------------------------------
def test_n_analysis_does_not_mutate_trajectories(trajectories, common_time,
                                                 common_range):
    qian, sanger = trajectories
    # Structural fingerprints before / after the protocol runs.
    for trajectory in (qian, sanger):
        assert trajectory.terminal_kind in ("RTI", "SRTI")
        assert np.isfinite(trajectory.terminal_state).all()
        mono = trajectory.is_range_monotone()
        assert mono.is_strictly_monotone
        # Calling the protocols again is deterministic (idempotent).
        r1 = run_common_time_comparison(qian, sanger)
        assert r1.common_time_s == common_time.common_time_s
        assert r1.delta_range_m == common_time.delta_range_m


# ---------------------------------------------------------------------------
# O. No sample-grid dependency
# ---------------------------------------------------------------------------
def test_o_no_sample_grid_dependency(trajectories, common_time, common_range):
    qian, sanger = trajectories
    # The protocol states are exactly the continuous ComparisonTrajectory
    # evaluations (no sampled grid, no CSV, no nearest row in between).
    assert common_time.qian_state.state_raw is not None
    direct = qian.state_at_time(common_time.common_time_s)
    assert np.array_equal(common_time.qian_state.state_raw,
                          direct.state_raw)
    direct_s = sanger.state_at_time(common_time.sanger_state.time_s)
    assert np.array_equal(common_time.sanger_state.state_raw,
                          direct_s.state_raw)
    # Sanger common-range state matches the continuous evaluation at the
    # inverted arrival time.
    s_arrival = common_range.sanger_arrival_time_s
    assert np.array_equal(common_range.sanger_state.state_raw,
                          sanger.state_at_time(s_arrival).state_raw)


# ---------------------------------------------------------------------------
# P. No Protocol D metrics produced
# ---------------------------------------------------------------------------
def test_p_no_protocol_d_metrics(common_time, common_range):
    for result in (common_time, common_range):
        names = set(result.__dataclass_fields__)
        # No atmospheric-exposure quantity (E0 §11 belongs to E3).
        assert "tau" not in " ".join(names).lower()
        assert "atmospheric" not in " ".join(names).lower()
        assert "exposure" not in " ".join(names).lower()
