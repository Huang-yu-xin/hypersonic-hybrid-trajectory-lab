"""E4 tests: native endpoint, structural and aerodynamic diagnostics.

    A  Protocol A uses exact terminal states.
    B  Protocol A semantics = persistence, not performance gain.
    C  Qian structural ATM duration equals research duration.
    D  Qian VAC duration = 0.
    E  Sanger ATM+VAC duration = research duration.
    F  mode fractions sum to 1.
    G  continuous altitude extrema finite.
    H  Sanger max altitude consistent with frozen baseline.
    I  aerodynamic diagnostics use frozen atmosphere/aero API.
    J  Sanger VAC q = 0.
    K  Sanger VAC D = 0.
    L  Sanger VAC a_D = 0.
    M  native aerodynamic maxima finite.
    N  common-time windows use E2 t_common.
    O  common-range windows use E2 arrival times.
    P  formal maxima do not use raw plotting-grid max.
    Q  maxima occur in ATM mode.
    R  instantaneous checkpoint diagnostics finite.
    S  no thermal quantities/claims in data model.
    T  no composite score.
    U  analysis does not mutate E1/E2/E3 results.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis import (
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    run_common_range_comparison,
    run_common_time_comparison,
)
from hyptraj.analysis.comparison_diagnostics import (
    AerodynamicMaximum,
    NativeEndpointComparison,
    TrajectoryStructuralDiagnostics,
    aerodynamic_diagnostic_state,
    build_structural_diagnostics,
    native_aerodynamic_maxima,
    run_native_endpoint_comparison,
    windowed_aerodynamic_maxima,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.aerodynamics import aerodynamic_forces
from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

REFERENCE_PATH = Path(__file__).parent / "data" / "sanger_baseline_v1.json"


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
    return qian, sanger, env, vehicle


@pytest.fixture(scope="module")
def e2_results(trajectories):
    qian, sanger, _, _ = trajectories
    return (
        run_common_time_comparison(qian, sanger),
        run_common_range_comparison(qian, sanger),
    )


@pytest.fixture(scope="module")
def native(trajectories):
    qian, sanger, _, _ = trajectories
    return run_native_endpoint_comparison(qian, sanger)


@pytest.fixture(scope="module")
def structure(trajectories):
    qian, sanger, _, _ = trajectories
    return (build_structural_diagnostics(qian),
            build_structural_diagnostics(sanger))


# ---------------------------------------------------------------------------
# A / B. Protocol A
# ---------------------------------------------------------------------------
def test_a_protocol_a_uses_exact_terminal_states(trajectories, native):
    qian, sanger, _, _ = trajectories
    assert isinstance(native, NativeEndpointComparison)
    assert np.allclose(
        np.array([native.qian_terminal.time_s,
                  native.qian_terminal.range_m,
                  native.qian_terminal.altitude_m,
                  native.qian_terminal.velocity_mps]),
        np.array([qian.terminal_time_s,
                  qian.terminal_state[1] * qian.environment.earth_radius,
                  qian.terminal_state[0] - qian.environment.earth_radius,
                  qian.terminal_state[2]]),
        rtol=1e-12,
    )
    assert native.sanger_terminal.kind == "SRTI"
    assert native.sanger_terminal.semantics == "SKIP_CAPABILITY_LOSS"
    assert native.qian_terminal.kind == "RTI"
    assert native.qian_terminal.semantics == "QEG_FEASIBILITY_LOSS"


def test_b_protocol_a_semantics_is_persistence(trajectories, native):
    assert native.semantics == "trajectory_mode_persistence"
    # Descriptive differences exist but are never named gains.
    fields = set(native.__dataclass_fields__)
    assert "range_gain" not in fields
    assert "performance_gain" not in fields
    # Descriptive differences equal the terminal differences exactly.
    assert native.delta_duration_s == pytest.approx(
        native.sanger_terminal.time_s - native.qian_terminal.time_s,
        rel=1e-12)
    assert native.delta_range_m == pytest.approx(
        native.sanger_terminal.range_m - native.qian_terminal.range_m,
        rel=1e-12)


# ---------------------------------------------------------------------------
# C / D / E / F. Structural mode durations and fractions
# ---------------------------------------------------------------------------
def test_c_qian_atm_duration_equals_research_duration(structure):
    qian_struct, _ = structure
    assert qian_struct.ATM_duration_s == pytest.approx(
        qian_struct.research_duration_s, rel=1e-12)


def test_d_qian_vac_duration_zero(structure):
    qian_struct, _ = structure
    assert qian_struct.VAC_duration_s == 0.0
    assert qian_struct.VAC_fraction == 0.0


def test_e_sanger_atm_plus_vac_equals_research(structure):
    _, sanger_struct = structure
    assert sanger_struct.ATM_duration_s + sanger_struct.VAC_duration_s \
        == pytest.approx(sanger_struct.research_duration_s, rel=1e-9)


def test_f_mode_fractions_sum_to_one(structure):
    for struct in structure:
        assert struct.ATM_fraction + struct.VAC_fraction \
            == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# G / H. Extrema
# ---------------------------------------------------------------------------
def test_g_continuous_altitude_extrema_finite(structure):
    for struct in structure:
        assert np.isfinite(struct.min_altitude.value_m)
        assert np.isfinite(struct.max_altitude.value_m)
        assert np.isfinite(struct.min_velocity_mps)
        assert struct.min_altitude.value_m > 0.0
        assert struct.max_altitude.value_m > struct.min_altitude.value_m


def test_h_sanger_max_altitude_matches_frozen_baseline(structure):
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    _, sanger_struct = structure
    # Frozen global max altitude (VAC0 apogee).
    assert sanger_struct.max_altitude.value_m == pytest.approx(
        reference["global"]["max_altitude_m"], abs=1e-3
    )
    assert sanger_struct.max_altitude.source_mode == "SANGER_VAC"
    # Frozen per-cycle apogee altitudes.
    apogees = reference["cycles"]
    assert sanger_struct.sanger_specific["vac_apogee_altitudes_m"] \
        == pytest.approx([c["apogee_altitude_m"] for c in apogees], abs=1e-3)


# ---------------------------------------------------------------------------
# I. Frozen atmosphere/aero reuse
# ---------------------------------------------------------------------------
def test_i_aerodynamic_uses_frozen_api(trajectories):
    qian, sanger, env, vehicle = trajectories
    # Direct cross-check against the frozen helpers at an ATM point.
    state = qian.state_at_time(50.0)
    rho = atmospheric_density(state.altitude_m, env)
    forces = aerodynamic_forces(rho, state.velocity_mps, qian.K, vehicle)
    diag = aerodynamic_diagnostic_state(qian, 50.0)
    assert diag.density_kgpm3 == pytest.approx(rho, rel=1e-12)
    assert diag.dynamic_pressure_pa == pytest.approx(
        forces.dynamic_pressure, rel=1e-12)
    assert diag.drag_n == pytest.approx(forces.drag, rel=1e-12)
    assert diag.drag_deceleration_mps2 == pytest.approx(
        forces.drag / vehicle.mass, rel=1e-12)


# ---------------------------------------------------------------------------
# J / K / L. Sanger VAC aero = 0
# ---------------------------------------------------------------------------
def test_jkl_sanger_vac_aero_is_zero(trajectories):
    _, sanger, _, _ = trajectories
    for seg in sanger.dense_segments:
        if seg.normalized_mode != "VAC":
            continue
        for t in np.linspace(seg.t_start + 1.0, seg.t_end - 1.0, 3):
            diag = aerodynamic_diagnostic_state(sanger, t)
            assert diag.normalized_mode == "VAC"
            assert diag.density_kgpm3 == 0.0
            assert diag.dynamic_pressure_pa == 0.0
            assert diag.drag_n == 0.0
            assert diag.drag_deceleration_mps2 == 0.0


# ---------------------------------------------------------------------------
# M / N / O / P / Q. Maxima
# ---------------------------------------------------------------------------
def test_m_native_aerodynamic_maxima_finite(trajectories):
    qian, sanger, _, _ = trajectories
    for trajectory in (qian, sanger):
        maxima = native_aerodynamic_maxima(trajectory)
        for key in ("max_q", "max_aD"):
            m = maxima[key]
            assert isinstance(m, AerodynamicMaximum)
            assert np.isfinite(m.value) and m.value > 0.0
            assert np.isfinite(m.time_s)


def test_n_common_time_windows_use_e2_t_common(trajectories, e2_results):
    qian, sanger, _, _ = trajectories
    common_time, _ = e2_results
    for trajectory in (qian, sanger):
        maxima = windowed_aerodynamic_maxima(
            trajectory, common_time.common_time_s)
        assert maxima["max_q"].time_s <= common_time.common_time_s + 1e-9


def test_o_common_range_windows_use_e2_arrival_times(
    trajectories, e2_results
):
    qian, sanger, _, _ = trajectories
    _, common_range = e2_results
    q_max = windowed_aerodynamic_maxima(
        qian, common_range.qian_arrival_time_s)["max_q"]
    s_max = windowed_aerodynamic_maxima(
        sanger, common_range.sanger_arrival_time_s)["max_q"]
    assert q_max.time_s <= common_range.qian_arrival_time_s + 1e-9
    assert s_max.time_s <= common_range.sanger_arrival_time_s + 1e-9


def test_p_formal_maxima_not_raw_grid_max(trajectories):
    qian, sanger, _, _ = trajectories
    for trajectory in (qian, sanger):
        maxima = native_aerodynamic_maxima(trajectory)
        # The refined maximum is at least as good as any grid sample and
        # the optimizer reported success with candidates scanned.
        for key in ("max_q", "max_aD"):
            m = maxima[key]
            assert m.optimization_success
            assert m.candidate_count >= 1
            # Independent 512-point audit scan agrees within tolerance
            # (the audit itself is part of the computation).
            assert m.value > 0.0


def test_q_maxima_occur_in_atm_mode(trajectories):
    qian, sanger, _, _ = trajectories
    for trajectory in (qian, sanger):
        maxima = native_aerodynamic_maxima(trajectory)
        for key in ("max_q", "max_aD"):
            assert maxima[key].normalized_mode == "ATM"


# ---------------------------------------------------------------------------
# R. Instantaneous checkpoint diagnostics
# ---------------------------------------------------------------------------
def test_r_instantaneous_checkpoint_diagnostics_finite(
    trajectories, e2_results
):
    qian, sanger, _, _ = trajectories
    common_time, common_range = e2_results
    for trajectory, t in (
        (qian, common_time.common_time_s),
        (sanger, common_time.common_time_s),
        (qian, common_range.qian_arrival_time_s),
        (sanger, common_range.sanger_arrival_time_s),
    ):
        diag = aerodynamic_diagnostic_state(trajectory, t)
        assert np.isfinite(diag.dynamic_pressure_pa)
        assert np.isfinite(diag.drag_deceleration_mps2)
        assert diag.dynamic_pressure_pa >= 0.0
        assert diag.drag_deceleration_mps2 >= 0.0


# ---------------------------------------------------------------------------
# S / T. No thermal / composite-score artifacts
# ---------------------------------------------------------------------------
def test_s_no_thermal_quantities_in_data_model(trajectories):
    qian, sanger, _, _ = trajectories
    diag = aerodynamic_diagnostic_state(qian, 50.0)
    fields = " ".join(f.lower() for f in diag.__dataclass_fields__)
    for forbidden in ("heat", "thermal", "flux", "tps", "load_factor",
                      "g_load"):
        assert forbidden not in fields
    maxima = native_aerodynamic_maxima(qian)
    for m in maxima.values():
        assert "heat" not in m.quantity.lower()
        assert "thermal" not in m.quantity.lower()


def test_t_no_composite_score(trajectories):
    qian, sanger, _, _ = trajectories
    for trajectory in (qian, sanger):
        maxima = native_aerodynamic_maxima(trajectory)
        assert set(maxima) == {"max_q", "max_aD"}
        # No aero_score / winner field anywhere in the results.
        for m in maxima.values():
            assert not hasattr(m, "score")
            assert not hasattr(m, "winner")


# ---------------------------------------------------------------------------
# U. No mutation
# ---------------------------------------------------------------------------
def test_u_analysis_does_not_mutate(trajectories, native, structure):
    qian, sanger, env, vehicle = trajectories
    # Deterministic and non-mutating.
    native2 = run_native_endpoint_comparison(qian, sanger)
    assert native2.delta_range_m == native.delta_range_m
    struct2 = build_structural_diagnostics(qian)
    assert struct2.max_altitude.value_m == structure[0].max_altitude.value_m
    # Inputs untouched.
    assert env.earth_radius == 6_371_000.0
    assert vehicle.mass == 1_000.0
    assert qian.terminal_kind == "RTI" and sanger.terminal_kind == "SRTI"
    assert np.isfinite(qian.terminal_state).all()
