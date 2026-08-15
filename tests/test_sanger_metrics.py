"""D4 unit tests for the Sanger skip-cycle metrics / diagnostics.

Coverage (D0 spec docs/phase_d/sanger_model_spec.md, §12-§26):

TEST A -- synthetic fixture with one completed cycle parses to exactly 1
          completed skip (synthetic E0 as anchor).
TEST B -- two-cycle fixture parses to skip_count = 2 (synthetic fixtures
          only; NOT a frozen real-baseline number).
TEST C -- terminal incomplete pass (E1 -> P1 -> SRTI) is excluded from
          skip_count and reported separately.
TEST D -- malformed histories (missing pull-out / exit / apogee / next
          entry / wrong order) raise instead of fabricating a cycle.
TEST E -- real frozen-IC trajectory: skip_count >= 1, every completed
          cycle strictly ordered E-P-X-A-E.
TEST F -- metric identities: cycle duration = ATM + VAC duration,
          cycle range = ATM + VAC range.
TEST G -- exit / entry altitudes at the atmosphere boundary.
TEST H -- extremum events have gamma ~ 0 with distinct semantic types.
TEST I -- VAC invariant drift metrics stay at the D3-validated magnitude
          (NOT a final convergence threshold; D6 formalizes it).
TEST J -- analysis does not mutate the trajectory (pure layer).
TEST K -- range convention identical to the frozen Qian reporting.
"""

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.dynamics import derived_quantities
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.sanger_events import (
    make_atmosphere_entry_event,
    make_atmosphere_exit_event,
)
from hyptraj.simulation.sanger_metrics import (
    SangerTrajectoryMetrics,
    analyze_sanger_trajectory,
    range_from_state,
)
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    ATMOSPHERIC_PULLOUT,
    SRTI,
    SYNTHETIC_INITIAL_ENTRY,
    VACUUM_APOGEE,
    HybridEventRecord,
    integrate_sanger_hybrid,
)

# NOT frozen: structural assertions only (D0 spec §22).
GAMMA_NEAR_ZERO_RAD = 1e-6
BOUNDARY_TOL_M = 1.0
VAC_DRIFT_LIMIT = 1e-6


# ---------------------------------------------------------------------------
# Fixture helpers (synthetic event histories)
# ---------------------------------------------------------------------------
def _ev(kind, t, h_m, v_mps=6500.0, gamma_deg=0.0, theta_rad=0.1,
        is_synthetic=False, index=0):
    env = EnvironmentParams()
    return HybridEventRecord(
        index=index,
        kind=kind,
        time=t,
        state=np.array(
            [
                env.earth_radius + h_m,
                theta_rad,
                v_mps,
                np.deg2rad(gamma_deg),
            ],
            dtype=float,
        ),
        mode_before=None,
        mode_after=None,
        is_synthetic=is_synthetic,
    )


def _trajectory(events, terminal_kind="max_time"):
    env = EnvironmentParams()
    last = events[-1]
    return type(
        "FakeTraj",
        (),
        {
            "segments": (),
            "events": tuple(events),
            "terminal_kind": terminal_kind,
            "terminal_time": last.time,
            "terminal_state": last.state,
            "success": terminal_kind == SRTI,
            "message": "fixture",
        },
    )


# ---------------------------------------------------------------------------
# TEST A -- one synthetic completed cycle
# ---------------------------------------------------------------------------
def test_a_one_completed_cycle_from_synthetic_e0():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, gamma_deg=0.0, index=1),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, gamma_deg=10.0, index=2),
        _ev(VACUUM_APOGEE, 344.0, 130_000.0, gamma_deg=0.0, index=3),
        _ev(ATMOSPHERE_ENTRY, 485.0, 100_000.0, gamma_deg=-10.0, index=4),
    ]
    metrics = analyze_sanger_trajectory(_trajectory(events), EnvironmentParams())

    assert metrics.skip_count == 1
    assert len(metrics.completed_cycles) == 1
    c = metrics.completed_cycles[0]
    assert c.index == 0
    assert c.entry_is_synthetic is True
    assert c.entry_time == pytest.approx(0.0)
    assert c.pullout_time < c.exit_time < c.apogee_time < c.next_entry_time


# ---------------------------------------------------------------------------
# TEST B -- two completed cycles (synthetic fixture semantics)
# ---------------------------------------------------------------------------
def test_b_two_completed_cycles():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, index=1),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, index=2),
        _ev(VACUUM_APOGEE, 344.0, 130_000.0, index=3),
        _ev(ATMOSPHERE_ENTRY, 485.0, 100_000.0, index=4),
        _ev(ATMOSPHERIC_PULLOUT, 596.0, 45_000.0, index=5),
        _ev(ATMOSPHERE_EXIT, 748.0, 100_000.0, index=6),
        _ev(VACUUM_APOGEE, 781.0, 102_000.0, index=7),
        _ev(ATMOSPHERE_ENTRY, 815.0, 100_000.0, index=8),
    ]
    metrics = analyze_sanger_trajectory(_trajectory(events), EnvironmentParams())

    assert metrics.skip_count == 2
    assert len(metrics.completed_cycles) == 2
    assert metrics.completed_cycles[0].entry_is_synthetic is True
    assert metrics.completed_cycles[1].entry_is_synthetic is False
    assert (
        metrics.completed_cycles[0].next_entry_time
        == metrics.completed_cycles[1].entry_time
    )


# ---------------------------------------------------------------------------
# TEST C -- terminal incomplete pass is not a skip
# ---------------------------------------------------------------------------
def test_c_terminal_incomplete_pass_excluded():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, index=1),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, index=2),
        _ev(VACUUM_APOGEE, 344.0, 130_000.0, index=3),
        _ev(ATMOSPHERE_ENTRY, 485.0, 100_000.0, index=4),
        _ev(ATMOSPHERIC_PULLOUT, 596.0, 45_000.0, index=5),
        _ev(SRTI, 1119.0, 86_000.0, gamma_deg=0.0, index=6),
    ]
    metrics = analyze_sanger_trajectory(
        _trajectory(events, terminal_kind=SRTI), EnvironmentParams())

    assert metrics.skip_count == 1
    assert len(metrics.completed_cycles) == 1

    p = metrics.terminal_incomplete_pass
    assert p is not None
    assert p.entry_time == pytest.approx(485.0)
    assert p.pullout_time == pytest.approx(596.0)
    assert p.srti_time == pytest.approx(1119.0)
    assert p.completed_exit is False
    assert p.srti_altitude_m == pytest.approx(86_000.0)
    # The P1 -> SRTI leg was NOT counted as a second skip.
    assert p.atmospheric_duration_s == pytest.approx(1119.0 - 485.0)


# ---------------------------------------------------------------------------
# TEST D -- malformed histories rejected
# ---------------------------------------------------------------------------
def test_d_missing_pullout_rejected():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, index=1),
    ]
    with pytest.raises(RuntimeError, match="pull-out"):
        analyze_sanger_trajectory(_trajectory(events), EnvironmentParams())


def test_d_missing_exit_rejected():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, index=1),
        _ev(VACUUM_APOGEE, 344.0, 130_000.0, index=2),
        _ev(ATMOSPHERE_ENTRY, 485.0, 100_000.0, index=3),
    ]
    with pytest.raises(RuntimeError, match="apogee before atmosphere exit"):
        analyze_sanger_trajectory(_trajectory(events), EnvironmentParams())


def test_d_missing_apogee_rejected():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, index=1),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, index=2),
        _ev(ATMOSPHERE_ENTRY, 485.0, 100_000.0, index=3),
    ]
    with pytest.raises(RuntimeError, match="vacuum apogee"):
        analyze_sanger_trajectory(_trajectory(events), EnvironmentParams())


def test_d_missing_next_entry_rejected():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, index=1),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, index=2),
        _ev(VACUUM_APOGEE, 344.0, 130_000.0, index=3),
        _ev(SRTI, 1119.0, 86_000.0, index=4),
    ]
    with pytest.raises(RuntimeError, match="after atmosphere exit"):
        analyze_sanger_trajectory(_trajectory(events, terminal_kind=SRTI),
                                  EnvironmentParams())


def test_d_wrong_event_order_rejected():
    events = [
        _ev(SYNTHETIC_INITIAL_ENTRY, 0.0, 100_000.0, is_synthetic=True, index=0),
        _ev(ATMOSPHERIC_PULLOUT, 93.0, 46_000.0, index=1),
        _ev(VACUUM_APOGEE, 344.0, 130_000.0, index=2),
        _ev(ATMOSPHERE_EXIT, 203.0, 100_000.0, index=3),
        _ev(ATMOSPHERE_ENTRY, 485.0, 100_000.0, index=4),
    ]
    with pytest.raises(RuntimeError, match="apogee before atmosphere exit"):
        analyze_sanger_trajectory(_trajectory(events), EnvironmentParams())


# ---------------------------------------------------------------------------
# Real-trajectory tests (frozen IC, NOT frozen numbers)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_metrics():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    traj = integrate_sanger_hybrid(env, vehicle, initial, control)
    return analyze_sanger_trajectory(traj, env), traj, env


def test_e_real_trajectory_cycles(real_metrics):
    metrics, traj, env = real_metrics

    assert metrics.skip_count >= 1
    assert len(metrics.completed_cycles) == metrics.skip_count

    for c in metrics.completed_cycles:
        assert (
            c.entry_time < c.pullout_time < c.exit_time
            < c.apogee_time < c.next_entry_time
        )
    # Completed cycles chain: E_{i+1} of cycle i anchors cycle i+1.
    for a, b in zip(metrics.completed_cycles, metrics.completed_cycles[1:]):
        assert a.next_entry_time == pytest.approx(b.entry_time, rel=1e-12)


def test_f_metric_identities(real_metrics):
    metrics, traj, env = real_metrics

    for c in metrics.completed_cycles:
        assert c.cycle_duration_s == pytest.approx(
            c.atmospheric_duration_s + c.vacuum_duration_s, rel=1e-12)
        assert c.cycle_range_m == pytest.approx(
            c.atmospheric_range_m + c.vacuum_range_m, rel=1e-12)
        assert c.atmospheric_duration_s > 0.0
        assert c.vacuum_duration_s > 0.0


def test_g_boundary_altitudes(real_metrics):
    metrics, traj, env = real_metrics

    for c in metrics.completed_cycles:
        assert abs(c.exit_altitude_m - env.atmosphere_boundary) < BOUNDARY_TOL_M
        assert (
            abs(c.next_entry_altitude_m - env.atmosphere_boundary)
            < BOUNDARY_TOL_M
        )


def test_h_extremum_gamma_and_semantics(real_metrics):
    metrics, traj, env = real_metrics

    for c in metrics.completed_cycles:
        assert abs(c.pullout_state[3]) < GAMMA_NEAR_ZERO_RAD
        assert abs(c.apogee_state[3]) < GAMMA_NEAR_ZERO_RAD
        assert c.pullout_altitude_m < env.atmosphere_boundary
        assert c.apogee_altitude_m > env.atmosphere_boundary

    # Distinct semantic types: the three extremum event kinds coexist
    # and all sit at gamma ~ 0.
    kinds = [e.kind for e in traj.events]
    for kind in (ATMOSPHERIC_PULLOUT, VACUUM_APOGEE, SRTI):
        assert kind in kinds
        e = next(e for e in traj.events if e.kind == kind)
        assert abs(e.state[3]) < GAMMA_NEAR_ZERO_RAD


def test_i_vac_invariant_drift_metrics(real_metrics):
    metrics, traj, env = real_metrics

    for c in metrics.completed_cycles:
        assert c.vacuum_energy_relative_drift < VAC_DRIFT_LIMIT
        assert c.vacuum_angular_momentum_relative_drift < VAC_DRIFT_LIMIT


def test_j_analysis_does_not_mutate_trajectory(real_metrics):
    metrics, traj, env = real_metrics

    events_before = [
        (e.kind, e.time, e.state.copy()) for e in traj.events
    ]
    segments_before = [
        (s.t.copy(), s.y.copy(), s.state_start.copy(), s.state_end.copy())
        for s in traj.segments
    ]

    analyze_sanger_trajectory(traj, env)  # run again

    for (e, before) in zip(traj.events, events_before):
        assert e.kind == before[0]
        assert e.time == before[1]
        np.testing.assert_array_equal(e.state, before[2])
    for (s, before) in zip(traj.segments, segments_before):
        np.testing.assert_array_equal(s.t, before[0])
        np.testing.assert_array_equal(s.y, before[1])
        np.testing.assert_array_equal(s.state_start, before[2])
        np.testing.assert_array_equal(s.state_end, before[3])


def test_k_range_convention_matches_qian(real_metrics):
    """D4 range must equal the frozen Qian reporting R = R_E * theta."""
    metrics, traj, env = real_metrics
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    for e in traj.events:
        r_d4 = range_from_state(e.state, env)
        r_frozen = env.earth_radius * e.state[1]
        assert r_d4 == pytest.approx(r_frozen, rel=1e-15)

    # Cross-check against the frozen derived-quantities reporting path.
    for e in traj.events:
        dq = derived_quantities(e.time, e.state, env, vehicle, control)
        assert range_from_state(e.state, env) == pytest.approx(
            dq["range_m"], rel=1e-15)


def test_l_global_metrics_present(real_metrics):
    metrics, traj, env = real_metrics

    assert metrics.atm_segment_count >= 1
    assert metrics.vac_segment_count >= 1
    assert metrics.total_atmospheric_time_s > 0.0
    assert metrics.total_vacuum_time_s > 0.0
    assert metrics.research_flight_time_s == pytest.approx(
        traj.terminal_time, rel=1e-12)
    assert metrics.research_range_m > 0.0
    assert metrics.maximum_altitude_m > env.atmosphere_boundary
    assert metrics.terminal_kind == SRTI
    assert metrics.terminal_velocity_mps > 0.0
    assert metrics.terminal_incomplete_pass is not None
