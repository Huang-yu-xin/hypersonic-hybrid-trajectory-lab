"""E1 tests: comparison data / alignment infrastructure.

Covers the unified ComparisonTrajectory abstraction over the frozen
Qian (ENTRY_CAPTURE + QEG_GLIDE -> RTI) and Sanger (synthetic E0 ->
SRTI) research trajectories, built on the E0.1 dense-output hook.

Test map (E1 spec):

    A  Qian adapter builds.
    B  Sanger adapter builds.
    C  Initial state equality.
    D  Environment / vehicle / K equality.
    E  Both use PRODUCTION_SOLVER_CONFIG.
    F  Qian event state continuous evaluation.
    G  Sanger event state continuous evaluation.
    H  Right-continuous mode semantics.
    I  Qian range monotonicity.
    J  Sanger range monotonicity.
    K  Qian range inversion round trip.
    L  Sanger range inversion round trip across all mode types.
    M  Time/range out-of-domain raises.
    N  Qian atmospheric exposure equals elapsed time.
    O  Sanger VAC exposure plateau.
    P  Exposure inverse UNIQUE.
    Q  Exposure inverse PLATEAU.
    R  Exposure inverse never arbitrarily selects earliest/latest.
    S  Energy helper uses frozen environment.
    T  Comparison adapter does not mutate underlying results.
    U  Ground continuation excluded.

Plus a frozen-convention consistency test for the range formula.
"""

import numpy as np
import pytest

from hyptraj.analysis import (
    AtmosphericExposureInverseStatus,
    ComparisonTrajectory,
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    verify_comparison_alignment,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.modes.continuous_glide import ENTRY_CAPTURE, GROUND_CONTINUATION, QEG_GLIDE
from hyptraj.modes.sanger_hybrid import SANGER_ATM, SANGER_VAC
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_metrics import range_from_state
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    SRTI,
)

# Production-precision consistency tolerance.
_RTOL = 1e-9
_ATOL = 1e-9

# Frozen mode labels.
QIAN_SOURCE_MODES = {ENTRY_CAPTURE, QEG_GLIDE}
SANGER_SOURCE_MODES = {SANGER_ATM, SANGER_VAC}


@pytest.fixture(scope="module")
def inputs():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    return env, vehicle, initial, control


@pytest.fixture(scope="module")
def qian(inputs):
    env, vehicle, initial, control = inputs
    return build_qian_comparison_trajectory(env, vehicle, initial, control)


@pytest.fixture(scope="module")
def sanger(inputs):
    env, vehicle, initial, control = inputs
    return build_sanger_comparison_trajectory(env, vehicle, initial, control)


# ---------------------------------------------------------------------------
# A / B. Adapters build
# ---------------------------------------------------------------------------
def test_a_qian_adapter_builds(qian):
    assert isinstance(qian, ComparisonTrajectory)
    assert qian.name == "qian"
    assert qian.terminal_kind == "RTI"
    assert qian.terminal_semantics == "QEG_FEASIBILITY_LOSS"
    assert len(qian.dense_segments) == 2


def test_b_sanger_adapter_builds(sanger):
    assert isinstance(sanger, ComparisonTrajectory)
    assert sanger.name == "sanger"
    assert sanger.terminal_kind == "SRTI"
    assert sanger.terminal_semantics == "SKIP_CAPABILITY_LOSS"
    assert len(sanger.dense_segments) == 5


# ---------------------------------------------------------------------------
# C / D / E. Alignment
# ---------------------------------------------------------------------------
def test_c_initial_state_equality(qian, sanger):
    assert np.allclose(qian.initial_state, sanger.initial_state,
                       rtol=_RTOL, atol=_ATOL)


def test_d_environment_vehicle_k_equality(qian, sanger):
    alignment = verify_comparison_alignment(qian, sanger)
    assert alignment.environment_equal
    assert alignment.vehicle_equal
    assert alignment.K_equal
    assert qian.K == 3.0 and sanger.K == 3.0


def test_e_both_use_production_solver_config(qian, sanger):
    for trajectory in (qian, sanger):
        cfg = trajectory.solver_config
        assert cfg.method == PRODUCTION_SOLVER_CONFIG.method
        assert cfg.rtol == PRODUCTION_SOLVER_CONFIG.rtol
        assert np.array_equal(cfg.atol, PRODUCTION_SOLVER_CONFIG.atol)
        assert cfg.max_step == PRODUCTION_SOLVER_CONFIG.max_step
        assert cfg.dense_output is True
    alignment = verify_comparison_alignment(qian, sanger)
    assert alignment.solver_equal
    assert alignment.all_equal


# ---------------------------------------------------------------------------
# F / G. Exact-event continuous evaluation
# ---------------------------------------------------------------------------
def test_f_qian_event_state_continuous_evaluation(qian):
    # Initial point.
    initial_state = qian.state_at_time(qian.initial_time_s)
    assert np.allclose(initial_state.state_raw, qian.initial_state,
                       rtol=_RTOL, atol=_ATOL)
    # Capture event (exact event state preferred).
    cap = qian.events[0]
    assert np.allclose(qian.state_at_time(cap.time_s).state_raw, cap.state,
                       rtol=_RTOL, atol=_ATOL)
    # RTI terminal (exact event state preferred).
    rti = qian.events[1]
    assert np.allclose(qian.state_at_time(rti.time_s).state_raw, rti.state,
                       rtol=_RTOL, atol=_ATOL)
    assert np.allclose(qian.state_at_time(qian.terminal_time_s).state_raw,
                       qian.terminal_state, rtol=_RTOL, atol=_ATOL)
    # Interior points evaluate continuously (dense, not grid).
    for t in (50.0, 200.0, 500.0, 700.0):
        state = qian.state_at_time(t)
        assert np.isfinite(state.state_raw).all()
        assert state.time_s == pytest.approx(t)


def test_g_sanger_event_state_continuous_evaluation(sanger):
    exit_e = [e for e in sanger.events if e.kind == ATMOSPHERE_EXIT]
    entry_e = [e for e in sanger.events if e.kind == ATMOSPHERE_ENTRY]
    srti_e = [e for e in sanger.events if e.kind == SRTI]
    assert len(exit_e) == 2 and len(entry_e) == 2 and len(srti_e) == 1
    for e in exit_e + entry_e + srti_e:
        assert np.allclose(sanger.state_at_time(e.time_s).state_raw, e.state,
                           rtol=_RTOL, atol=_ATOL)
    assert np.allclose(
        sanger.state_at_time(sanger.terminal_time_s).state_raw,
        sanger.terminal_state, rtol=_RTOL, atol=_ATOL
    )


# ---------------------------------------------------------------------------
# H. Right-continuous mode semantics
# ---------------------------------------------------------------------------
def test_h_right_continuous_mode_semantics(qian, sanger):
    # Qian: capture is a hybrid switch -> post-transition QEG_GLIDE (ATM).
    cap_t = qian.events[0].time_s
    assert qian.mode_at_time(cap_t) == "ATM"
    assert qian.source_mode_at_time(cap_t) == QEG_GLIDE
    # Qian RTI terminal: pre-terminal physical mode QEG_GLIDE / ATM.
    assert qian.mode_at_time(qian.terminal_time_s) == "ATM"
    assert qian.source_mode_at_time(qian.terminal_time_s) == QEG_GLIDE
    # Qian initial: ENTRY_CAPTURE / ATM.
    assert qian.mode_at_time(0.0) == "ATM"
    assert qian.source_mode_at_time(0.0) == ENTRY_CAPTURE

    # Sanger exit: post-transition VAC.
    exit0 = [e for e in sanger.events if e.kind == ATMOSPHERE_EXIT][0]
    assert sanger.mode_at_time(exit0.time_s) == "VAC"
    assert sanger.source_mode_at_time(exit0.time_s) == SANGER_VAC
    # Sanger entry: post-transition ATM.
    entry0 = [e for e in sanger.events if e.kind == ATMOSPHERE_ENTRY][0]
    assert sanger.mode_at_time(entry0.time_s) == "ATM"
    assert sanger.source_mode_at_time(entry0.time_s) == SANGER_ATM
    # Sanger SRTI terminal: pre-terminal ATM.
    assert sanger.mode_at_time(sanger.terminal_time_s) == "ATM"
    assert sanger.source_mode_at_time(sanger.terminal_time_s) == SANGER_ATM
    # Just before exit is still ATM (left-continuous interior).
    assert sanger.mode_at_time(exit0.time_s - 1e-6) == "ATM"
    # Synthetic E0: ATM.
    assert sanger.mode_at_time(0.0) == "ATM"


# ---------------------------------------------------------------------------
# I / J. Range monotonicity
# ---------------------------------------------------------------------------
def test_i_qian_range_monotonicity(qian):
    mono = qian.is_range_monotone()
    assert mono.is_strictly_monotone
    assert mono.minimum_drange_dt > 0.0
    assert mono.minimum_velocity > 0.0
    assert mono.minimum_cos_gamma > 0.0
    assert mono.diagnostic_sample_count >= 2 * 250


def test_j_sanger_range_monotonicity(sanger):
    mono = sanger.is_range_monotone()
    assert mono.is_strictly_monotone
    assert mono.minimum_drange_dt > 0.0
    assert mono.minimum_velocity > 0.0
    assert mono.minimum_cos_gamma > 0.0
    assert mono.diagnostic_sample_count >= 5 * 250


# ---------------------------------------------------------------------------
# K / L. Range inversion round trip
# ---------------------------------------------------------------------------
def test_k_qian_range_inversion_round_trip(qian):
    mono = qian.is_range_monotone()
    assert mono.is_strictly_monotone
    interior = np.linspace(30.0, qian.terminal_time_s - 1.0, 10)
    max_dt = 0.0
    max_residual = 0.0
    for t_i in interior:
        r_i = qian.range_at_time(t_i)
        t_rec = qian.first_time_at_range(r_i)
        max_dt = max(max_dt, abs(t_rec - t_i))
        max_residual = max(max_residual,
                           abs(qian.range_at_time(t_rec) - r_i))
    assert max_dt < 1e-6
    assert max_residual < 1e-3
    # Boundary cases.
    assert qian.first_time_at_range(qian.range_at_time(0.0)) == 0.0
    assert qian.first_time_at_range(
        qian.range_at_time(qian.terminal_time_s)
    ) == qian.terminal_time_s


def test_l_sanger_range_inversion_round_trip_across_all_modes(sanger):
    mono = sanger.is_range_monotone()
    assert mono.is_strictly_monotone
    # One probe per segment interior: ATM0 VAC0 ATM1 VAC1 ATM2.
    probes = []
    for seg in sanger.dense_segments:
        probes.append(0.5 * (seg.t_start + seg.t_end))
    probes.append(sanger.terminal_time_s - 5.0)
    max_dt = 0.0
    max_residual = 0.0
    for t_i in probes:
        r_i = sanger.range_at_time(t_i)
        t_rec = sanger.first_time_at_range(r_i)
        max_dt = max(max_dt, abs(t_rec - t_i))
        max_residual = max(max_residual,
                           abs(sanger.range_at_time(t_rec) - r_i))
    assert max_dt < 1e-6
    assert max_residual < 1e-3
    assert sanger.first_time_at_range(sanger.range_at_time(0.0)) == 0.0
    assert sanger.first_time_at_range(
        sanger.range_at_time(sanger.terminal_time_s)
    ) == sanger.terminal_time_s


# ---------------------------------------------------------------------------
# M. Out-of-domain raises
# ---------------------------------------------------------------------------
def test_m_out_of_domain_raises(qian, sanger):
    for trajectory in (qian, sanger):
        with pytest.raises(ValueError):
            trajectory.state_at_time(trajectory.initial_time_s - 1.0)
        with pytest.raises(ValueError):
            trajectory.state_at_time(trajectory.terminal_time_s + 1.0)
        with pytest.raises(ValueError):
            trajectory.mode_at_time(trajectory.terminal_time_s + 1.0)
        with pytest.raises(ValueError):
            trajectory.atmospheric_exposure_at_time(
                trajectory.terminal_time_s + 1.0
            )
        with pytest.raises(ValueError):
            trajectory.first_time_at_range(
                trajectory.range_at_time(trajectory.terminal_time_s) + 1.0
            )
        with pytest.raises(ValueError):
            trajectory.time_at_atmospheric_exposure(
                trajectory.total_atmospheric_exposure() + 1.0
            )


# ---------------------------------------------------------------------------
# N / O. Atmospheric exposure
# ---------------------------------------------------------------------------
def test_n_qian_atmospheric_exposure_equals_elapsed_time(qian):
    # The whole Qian research domain is atmospheric: tau(t) == t - t0.
    for t in np.linspace(0.0, qian.terminal_time_s, 12):
        assert abs(qian.atmospheric_exposure_at_time(t) - t) < 1e-9
    assert abs(qian.total_atmospheric_exposure()
               - qian.terminal_time_s) < 1e-9
    assert qian.atmospheric_exposure_at_time(0.0) == 0.0


def test_o_sanger_vac_exposure_plateau(sanger):
    # For every VAC segment, exposure is constant while range grows.
    for seg in sanger.dense_segments:
        if seg.normalized_mode != "VAC":
            continue
        t1 = seg.t_start + 5.0
        t2 = seg.t_end - 5.0
        assert sanger.atmospheric_exposure_at_time(t1) == pytest.approx(
            sanger.atmospheric_exposure_at_time(t2), abs=1e-12
        )
        assert sanger.range_at_time(t2) > sanger.range_at_time(t1)
    # Structural invariants.
    tau_end = sanger.total_atmospheric_exposure()
    assert tau_end < sanger.terminal_time_s  # VAC arcs subtract exposure
    assert tau_end > 0.0
    assert sanger.atmospheric_exposure_at_time(0.0) == 0.0


# ---------------------------------------------------------------------------
# P / Q / R. Exposure inverse
# ---------------------------------------------------------------------------
def test_p_exposure_inverse_unique(qian, sanger):
    for trajectory in (qian, sanger):
        result = trajectory.time_at_atmospheric_exposure(30.0)
        assert result.status == AtmosphericExposureInverseStatus.UNIQUE
        assert result.time_s == pytest.approx(30.0, abs=1e-9)
        assert result.plateau_start_s is None
        assert result.plateau_end_s is None


def test_q_exposure_inverse_plateau(sanger):
    # Exposure value at the end of ATM0 is a VAC0 plateau.
    vac0 = [s for s in sanger.dense_segments
            if s.normalized_mode == "VAC"][0]
    plateau_tau = sanger.atmospheric_exposure_at_time(vac0.t_start)
    result = sanger.time_at_atmospheric_exposure(plateau_tau)
    assert result.status == AtmosphericExposureInverseStatus.PLATEAU
    assert result.time_s is None
    assert result.plateau_start_s == pytest.approx(vac0.t_start, abs=1e-9)
    assert result.plateau_end_s == pytest.approx(vac0.t_end, abs=1e-9)


def test_r_exposure_inverse_no_arbitrary_selection(sanger, qian):
    # A PLATEAU result never fabricates a single time.
    vac1 = [s for s in sanger.dense_segments
            if s.normalized_mode == "VAC"][1]
    plateau_tau = sanger.atmospheric_exposure_at_time(vac1.t_start)
    result = sanger.time_at_atmospheric_exposure(plateau_tau)
    assert result.time_s is None
    assert (result.plateau_start_s, result.plateau_end_s) == (
        vac1.t_start, vac1.t_end
    )
    # A UNIQUE result never carries plateau fields.
    uniq = qian.time_at_atmospheric_exposure(100.0)
    assert uniq.status == AtmosphericExposureInverseStatus.UNIQUE
    assert uniq.plateau_start_s is None and uniq.plateau_end_s is None
    # No function ever returns a bare float for the inverse.
    for trajectory in (qian, sanger):
        value = trajectory.time_at_atmospheric_exposure(
            trajectory.total_atmospheric_exposure()
        )
        assert isinstance(value, object)  # structured result type
        assert value.status == AtmosphericExposureInverseStatus.UNIQUE
        assert value.time_s == pytest.approx(
            trajectory.terminal_time_s, abs=1e-9
        )


# ---------------------------------------------------------------------------
# S. Energy helper uses frozen environment
# ---------------------------------------------------------------------------
def test_s_energy_helper_uses_frozen_environment(qian, sanger, inputs):
    env, vehicle, initial, control = inputs
    from hyptraj.modes.sanger_hybrid import specific_mechanical_energy

    for trajectory in (qian, sanger):
        for t in (10.0, 300.0, trajectory.terminal_time_s):
            state = trajectory.state_at_time(t).state_raw
            assert trajectory.specific_energy_at_time(t) == pytest.approx(
                specific_mechanical_energy(state, env), rel=1e-12
            )
        # Energy decreases monotonically over the research domain.
        e0 = trajectory.specific_energy_at_time(trajectory.initial_time_s)
        e1 = trajectory.specific_energy_at_time(trajectory.terminal_time_s)
        assert e1 < e0


def test_s2_range_convention_matches_frozen_helper(qian, sanger):
    # Thin-wrapper consistency: R = R_E * theta exactly as the frozen
    # helper defines it (no r*theta, no haversine).
    for trajectory in (qian, sanger):
        for t in np.linspace(0.0, trajectory.terminal_time_s, 9):
            state = trajectory.state_at_time(t).state_raw
            assert trajectory.range_at_time(t) == pytest.approx(
                range_from_state(state, trajectory.environment), rel=1e-15
            )


# ---------------------------------------------------------------------------
# T. No mutation of underlying results / collector
# ---------------------------------------------------------------------------
def test_t_adapter_does_not_mutate(inputs, qian, sanger):
    env, vehicle, initial, control = inputs

    # The builder does not mutate the shared inputs.
    assert env.earth_radius == 6_371_000.0
    assert vehicle.mass == 1_000.0
    assert control.value == 3.0

    # Evaluation is idempotent and state_raw is a private copy.
    for trajectory in (qian, sanger):
        t = 0.5 * trajectory.terminal_time_s
        reference = trajectory.state_at_time(t).state_raw.copy()
        view = trajectory.state_at_time(t)
        view.state_raw[:] = -999.0  # mutating the view must not affect...
        fresh = trajectory.state_at_time(t)
        assert np.array_equal(fresh.state_raw, reference)  # ...the state
        assert not np.array_equal(view.state_raw, reference)


# ---------------------------------------------------------------------------
# U. Ground continuation excluded
# ---------------------------------------------------------------------------
def test_u_ground_continuation_excluded(qian, sanger):
    # Qian research domain ends at RTI, before the ground continuation.
    assert qian.terminal_kind == "RTI"
    assert GROUND_CONTINUATION not in {s.source_mode
                                       for s in qian.dense_segments}
    assert GROUND_CONTINUATION not in {
        qian.source_mode_at_time(qian.terminal_time_s)
    }
    # No event time lies in the ground-continuation stage (t > RTI).
    assert qian.terminal_time_s == max(e.time_s for e in qian.events)
    # Sanger: research domain ends at SRTI; no ground tail is present.
    assert sanger.terminal_kind == "SRTI"
    assert sanger.terminal_time_s == max(e.time_s for e in sanger.events)
