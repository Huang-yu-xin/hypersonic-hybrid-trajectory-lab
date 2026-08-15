"""D3 unit tests for the event-driven Sanger hybrid state machine.

Coverage (D0 spec docs/phase_d/sanger_model_spec.md, §3-§17, §38):

TEST A -- synthetic E0 semantics: first event is synthetic_initial_entry,
          no real atmosphere entry at t = 0, first segment is SANGER_ATM.
TEST B -- first ATM -> VAC transition is atmosphere_exit near h = 100 km
          with gamma > 0 and exact state continuity.
TEST C -- first VAC -> ATM transition is atmosphere_entry near h = 100 km
          with gamma < 0 and exact state continuity.
TEST D -- modes strictly alternate (no ATM-ATM / VAC-VAC).
TEST E -- first atmospheric pass has a pull-out before its exit.
TEST F -- first VAC arc has an apogee with t_exit < t_apogee < t_entry
          and gamma ~ 0 (altitude NOT frozen).
TEST G -- terminal_kind == SRTI with valid pass history: mode SANGER_ATM,
          gamma ~ 0, h < h_atm, pull-out observed in the final pass, and
          no atmosphere exit in that pass before the terminal.
TEST H -- real event times strictly increasing; all segments have
          positive duration.
TEST I -- no repeated / chattering mode switches.
TEST J -- hybrid metadata: f_minus / f_plus / normal stored on every
          real ATM <-> VAC switch and equal to the D1 RHS at x_e.
TEST K -- safety guards: max_segments and max_time stop the loop with
          success = False and clear messages (no infinite loop).
TEST L -- input objects are never mutated.
TEST M -- VAC invariant smoke: for the first complete VAC arc the
          specific mechanical energy and angular momentum drift is small
          (systematic validation deferred to D6).
TEST N -- get_combined_history reconstructs a strictly increasing
          chronological trajectory without duplicated transition states.

Real event times / altitudes are reported for audit only and are NOT
frozen baseline values (D0 spec §19, §22).
"""

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes.sanger_hybrid import (
    SANGER_ATM,
    SANGER_VAC,
    sanger_atm_rhs,
    sanger_vac_rhs,
    specific_angular_momentum,
    specific_mechanical_energy,
)
from hyptraj.simulation.sanger_events import atmosphere_interface_normal
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    ATMOSPHERIC_PULLOUT,
    SRTI,
    SYNTHETIC_INITIAL_ENTRY,
    TERMINAL_MAX_SEGMENTS,
    TERMINAL_MAX_TIME,
    TERMINAL_SRTI,
    VACUUM_APOGEE,
    integrate_sanger_hybrid,
)

# NOT frozen: structural regression only (D0 spec §22).
GAMMA_NEAR_ZERO_RAD = 1e-6
ALTITUDE_TOL_M = 1.0
VAC_INVARIANT_REL_DRIFT = 1e-6


@pytest.fixture(scope="module")
def setup():
    return (
        EnvironmentParams(),
        VehicleParams(),
        InitialCondition(
            altitude=100_000.0,
            velocity=7_000.0,
            flight_path_angle_deg=-5.0,
            range_angle=0.0,
        ),
        ConstantKControl(3.0),
    )


@pytest.fixture(scope="module")
def trajectory(setup):
    env, vehicle, initial, control = setup
    return integrate_sanger_hybrid(env, vehicle, initial, control)


# ---------------------------------------------------------------------------
# TEST A -- synthetic E0
# ---------------------------------------------------------------------------
def test_a_synthetic_e0_semantics(trajectory, setup):
    env, vehicle, initial, control = setup

    assert trajectory.segments[0].mode == SANGER_ATM

    first = trajectory.events[0]
    assert first.kind == SYNTHETIC_INITIAL_ENTRY
    assert first.time == pytest.approx(0.0, abs=1e-12)
    assert first.is_synthetic is True
    assert first.mode_before is None
    assert first.mode_after == SANGER_ATM

    # No REAL atmosphere entry at t = 0.
    real_entries = [
        e for e in trajectory.events
        if e.kind == ATMOSPHERE_ENTRY and not e.is_synthetic
    ]
    assert all(e.time > 0.0 for e in real_entries)
    assert not any(
        e.kind == ATMOSPHERE_ENTRY and e.time == pytest.approx(0.0)
        for e in trajectory.events
    )


# ---------------------------------------------------------------------------
# TEST B -- first ATM -> VAC transition
# ---------------------------------------------------------------------------
def test_b_first_transition_is_exit(trajectory, setup):
    env, vehicle, initial, control = setup

    exit_event = next(e for e in trajectory.events if e.kind == ATMOSPHERE_EXIT)
    assert trajectory.segments[0].trigger_event == ATMOSPHERE_EXIT
    assert trajectory.segments[1].mode == SANGER_VAC

    h_exit = exit_event.state[0] - env.earth_radius
    assert abs(h_exit - 100_000.0) < ALTITUDE_TOL_M
    assert exit_event.state[3] > 0.0

    # Exact state continuity: x_plus == x_minus (plain copy).
    np.testing.assert_array_equal(
        trajectory.segments[0].state_end,
        trajectory.segments[1].state_start,
    )
    np.testing.assert_array_equal(exit_event.state,
                                  trajectory.segments[1].state_start)


# ---------------------------------------------------------------------------
# TEST C -- first VAC -> ATM transition
# ---------------------------------------------------------------------------
def test_c_first_entry_transition(trajectory, setup):
    env, vehicle, initial, control = setup

    entry_event = next(
        e for e in trajectory.events if e.kind == ATMOSPHERE_ENTRY)

    h_entry = entry_event.state[0] - env.earth_radius
    assert abs(h_entry - 100_000.0) < ALTITUDE_TOL_M
    assert entry_event.state[3] < 0.0

    entry_idx = next(
        i for i, s in enumerate(trajectory.segments)
        if s.trigger_event == ATMOSPHERE_ENTRY)
    assert trajectory.segments[entry_idx].mode == SANGER_VAC
    assert trajectory.segments[entry_idx + 1].mode == SANGER_ATM

    np.testing.assert_array_equal(
        trajectory.segments[entry_idx].state_end,
        trajectory.segments[entry_idx + 1].state_start,
    )


# ---------------------------------------------------------------------------
# TEST D -- strict mode alternation
# ---------------------------------------------------------------------------
def test_d_modes_strictly_alternate(trajectory):
    modes = [s.mode for s in trajectory.segments]
    for a, b in zip(modes, modes[1:]):
        assert a != b
    assert all(m in (SANGER_ATM, SANGER_VAC) for m in modes)
    assert modes[0] == SANGER_ATM


# ---------------------------------------------------------------------------
# TEST E -- pull-out before first exit
# ---------------------------------------------------------------------------
def test_e_pullout_before_first_exit(trajectory):
    pullouts = [e for e in trajectory.events if e.kind == ATMOSPHERIC_PULLOUT]
    exits = [e for e in trajectory.events if e.kind == ATMOSPHERE_EXIT]

    assert len(pullouts) >= 1
    assert len(exits) >= 1
    assert pullouts[0].time < exits[0].time
    # Pull-out is a diagnostic: no mode change.
    assert pullouts[0].mode_before == SANGER_ATM
    assert pullouts[0].mode_after == SANGER_ATM


# ---------------------------------------------------------------------------
# TEST F -- first VAC apogee
# ---------------------------------------------------------------------------
def test_f_first_vac_arc_apogee(trajectory):
    apogees = [e for e in trajectory.events if e.kind == VACUUM_APOGEE]
    exits = [e for e in trajectory.events if e.kind == ATMOSPHERE_EXIT]
    entries = [e for e in trajectory.events if e.kind == ATMOSPHERE_ENTRY]

    assert len(apogees) >= 1
    assert exits[0].time < apogees[0].time < entries[0].time
    assert abs(apogees[0].state[3]) < GAMMA_NEAR_ZERO_RAD
    # Diagnostic: no mode change at apogee.
    assert apogees[0].mode_before == SANGER_VAC
    assert apogees[0].mode_after == SANGER_VAC


# ---------------------------------------------------------------------------
# TEST G -- SRTI classification by the state machine
# ---------------------------------------------------------------------------
def test_g_terminal_is_classified_srti(trajectory, setup):
    env, vehicle, initial, control = setup

    assert trajectory.terminal_kind == TERMINAL_SRTI
    assert trajectory.success is True
    assert trajectory.segments[-1].mode == SANGER_ATM

    srti_event = trajectory.events[-1]
    assert srti_event.kind == SRTI
    assert abs(srti_event.state[3]) < GAMMA_NEAR_ZERO_RAD
    h_srti = srti_event.state[0] - env.earth_radius
    assert h_srti < env.atmosphere_boundary + ALTITUDE_TOL_M

    # Valid pass history: the final atmospheric pass observed a pull-out
    # and NO atmosphere exit before the SRTI candidate.
    final_pass_events = []
    for e in reversed(trajectory.events):
        if e.kind in (ATMOSPHERE_ENTRY, SYNTHETIC_INITIAL_ENTRY):
            break
        final_pass_events.append(e)
    final_pass_events.reverse()
    assert final_pass_events[-1].kind == SRTI
    assert any(e.kind == ATMOSPHERIC_PULLOUT for e in final_pass_events)
    assert not any(e.kind == ATMOSPHERE_EXIT for e in final_pass_events)


# ---------------------------------------------------------------------------
# TEST H -- event time monotonicity + positive segment durations
# ---------------------------------------------------------------------------
def test_h_event_times_strictly_increasing(trajectory):
    real_times = [
        e.time for e in trajectory.events if not e.is_synthetic
    ]
    assert all(
        b > a for a, b in zip(real_times, real_times[1:])
    )
    for s in trajectory.segments:
        assert s.t_end > s.t_start


# ---------------------------------------------------------------------------
# TEST I -- no chatter / repeated switches
# ---------------------------------------------------------------------------
def test_i_no_chatter(trajectory):
    switches = [
        e for e in trajectory.events
        if e.kind in (ATMOSPHERE_EXIT, ATMOSPHERE_ENTRY)
    ]
    kinds = [e.kind for e in switches]
    # Exit and entry must strictly alternate, starting with exit.
    assert kinds[0] == ATMOSPHERE_EXIT
    for a, b in zip(kinds, kinds[1:]):
        assert a != b
    # No machine-precision back-and-forth: strictly increasing switching
    # times (restated here; TEST H enforces the same globally).
    times = [e.time for e in switches]
    assert all(b > a for a, b in zip(times, times[1:]))


# ---------------------------------------------------------------------------
# TEST J -- hybrid sensitivity metadata (f_minus / f_plus / normal)
# ---------------------------------------------------------------------------
def test_j_switching_metadata_atm_to_vac(trajectory, setup):
    env, vehicle, initial, control = setup

    exit_event = next(e for e in trajectory.events if e.kind == ATMOSPHERE_EXIT)
    t_e, x_e = exit_event.time, exit_event.state

    expected_minus = sanger_atm_rhs(t_e, x_e, env, vehicle, control)
    expected_plus = sanger_vac_rhs(t_e, x_e, env, vehicle)

    np.testing.assert_array_equal(exit_event.f_minus, expected_minus)
    np.testing.assert_array_equal(exit_event.f_plus, expected_plus)
    np.testing.assert_array_equal(exit_event.normal,
                                  atmosphere_interface_normal())
    assert not np.array_equal(exit_event.f_minus, exit_event.f_plus)


def test_j_switching_metadata_vac_to_atm(trajectory, setup):
    env, vehicle, initial, control = setup

    entry_event = next(
        e for e in trajectory.events if e.kind == ATMOSPHERE_ENTRY)
    t_e, x_e = entry_event.time, entry_event.state

    expected_minus = sanger_vac_rhs(t_e, x_e, env, vehicle)
    expected_plus = sanger_atm_rhs(t_e, x_e, env, vehicle, control)

    np.testing.assert_array_equal(entry_event.f_minus, expected_minus)
    np.testing.assert_array_equal(entry_event.f_plus, expected_plus)
    np.testing.assert_array_equal(entry_event.normal,
                                  atmosphere_interface_normal())
    assert not np.array_equal(entry_event.f_minus, entry_event.f_plus)


def test_j_diagnostic_events_have_no_switching_metadata(trajectory):
    for e in trajectory.events:
        if e.kind in (ATMOSPHERIC_PULLOUT, VACUUM_APOGEE):
            assert e.f_minus is None
            assert e.f_plus is None
            assert e.normal is None


# ---------------------------------------------------------------------------
# TEST K -- safety guards
# ---------------------------------------------------------------------------
def test_k_max_segments_guard(setup):
    env, vehicle, initial, control = setup
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control, max_segments=2)

    assert traj.success is False
    assert traj.terminal_kind == TERMINAL_MAX_SEGMENTS
    assert "max_segments=2" in traj.message
    assert len(traj.segments) == 2


def test_k_max_time_guard(setup):
    env, vehicle, initial, control = setup
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control, max_time=10.0)

    assert traj.success is False
    assert traj.terminal_kind == TERMINAL_MAX_TIME
    assert "max_time=10.0" in traj.message
    assert traj.terminal_time == pytest.approx(10.0, abs=1e-9)


# ---------------------------------------------------------------------------
# TEST L -- input objects never mutated
# ---------------------------------------------------------------------------
def test_l_inputs_not_mutated(setup):
    env, vehicle, initial, control = setup
    initial_before = (
        initial.altitude, initial.velocity,
        initial.flight_path_angle_deg, initial.range_angle)

    integrate_sanger_hybrid(env, vehicle, initial, control)

    assert (
        initial.altitude, initial.velocity,
        initial.flight_path_angle_deg, initial.range_angle
    ) == initial_before


# ---------------------------------------------------------------------------
# TEST M -- VAC invariant smoke (E and H drift over the first VAC arc)
# ---------------------------------------------------------------------------
def test_m_vac_invariant_smoke(trajectory, setup):
    env, vehicle, initial, control = setup

    first_vac = next(
        s for s in trajectory.segments
        if s.mode == SANGER_VAC and s.trigger_event == ATMOSPHERE_ENTRY)

    e0 = specific_mechanical_energy(first_vac.state_start, env)
    e1 = specific_mechanical_energy(first_vac.state_end, env)
    h0 = specific_angular_momentum(first_vac.state_start, env)
    h1 = specific_angular_momentum(first_vac.state_end, env)

    assert abs((e1 - e0) / e0) < VAC_INVARIANT_REL_DRIFT
    assert abs((h1 - h0) / h0) < VAC_INVARIANT_REL_DRIFT


# ---------------------------------------------------------------------------
# TEST N -- full trajectory reconstruction
# ---------------------------------------------------------------------------
def test_n_combined_history_reconstruction(trajectory):
    t, y = trajectory.get_combined_history()

    assert y.shape[0] == 4
    assert t.shape[0] == y.shape[1]
    # Chronological and strictly increasing (no duplicated transition).
    assert np.all(np.diff(t) > 0.0)
    # Starts at the initial state and ends at the terminal state.
    np.testing.assert_allclose(
        y[:, 0],
        trajectory.segments[0].state_start,
        rtol=1e-12,
    )
    np.testing.assert_allclose(
        y[:, -1],
        trajectory.terminal_state,
        rtol=1e-12,
    )
    # Transition point appears exactly once: segment-boundary values
    # coincide with the last sample of the preceding segment.
    for i in range(1, len(trajectory.segments)):
        prev = trajectory.segments[i - 1]
        cur = trajectory.segments[i]
        np.testing.assert_allclose(cur.state_start, prev.state_end,
                                   rtol=1e-12)
