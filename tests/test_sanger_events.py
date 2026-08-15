"""D2 unit tests for the Sanger hybrid event primitives.

Coverage (D0 spec docs/phase_d/sanger_model_spec.md, §7-§13, §16):

TEST A -- atmosphere switching surface value (h = 90 / 100 / 110 km).
TEST B -- exit factory attributes (direction +1, terminal) + signs.
TEST C -- entry factory attributes (direction -1, terminal, same surface).
TEST D -- ATM pull-out diagnostic (gamma root, +1, nonterminal).
TEST E -- VAC apogee diagnostic (gamma root, -1, nonterminal).
TEST F -- SRTI candidate (gamma root, -1, terminal); qualification is
          explicitly deferred to the D3 state machine.
TEST G -- short-integration regression: ATM segment detects exactly one
          upward atmosphere exit near h = 100 km.
TEST H -- short-integration regression: VAC segment detects exactly one
          downward atmosphere entry near h = 100 km.
TEST I -- exact-boundary ATM restart (h = 100 km exactly, gamma < 0):
          no fake atmosphere exit at t = 0 (synthetic E0 semantics).
TEST J -- exact-boundary VAC restart (h = 100 km exactly, gamma > 0):
          no fake atmosphere entry at t = 0.
TEST K -- direction discrimination: downward crossing is not an exit,
          upward crossing is not an entry.
TEST L -- interface normal nabla G = [1, 0, 0, 0]^T in the frozen
          [r, theta, v, gamma] ordering.
TEST M -- event functions are pure observers (no state mutation).

No epsilon state perturbation is used anywhere; exact-boundary safety
comes from direction-specific events only.  Short integrations use the
frozen PRODUCTION_SOLVER_CONFIG (Phase C) to pre-validate the event
handling under production numerics.
"""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)
from hyptraj.modes.sanger_hybrid import (
    ATMOSPHERE_BOUNDARY_M,
    sanger_atm_rhs,
    sanger_vac_rhs,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_events import (
    atmosphere_interface_normal,
    atmosphere_interface_value,
    make_atmosphere_entry_event,
    make_atmosphere_exit_event,
    make_pullout_event,
    make_srti_candidate_event,
    make_vacuum_apogee_event,
)

K_CONTROL = ConstantKControl(3.0)


def _state(env, h_m, v_mps, gamma_deg, theta_rad=0.0):
    """Frozen state ordering: state = [r, theta, v, gamma], h = r - R_E."""
    return np.array(
        [
            env.earth_radius + h_m,
            theta_rad,
            v_mps,
            np.deg2rad(gamma_deg),
        ],
        dtype=float,
    )


def _integrate(rhs, state0, events, t_span=(0.0, 60.0)):
    """Short event regression harness (test-only, not a production
    trajectory integrator)."""
    cfg = PRODUCTION_SOLVER_CONFIG
    return solve_ivp(
        rhs,
        t_span,
        state0,
        method=cfg.method,
        rtol=cfg.rtol,
        atol=cfg.atol,
        max_step=cfg.max_step,
        dense_output=cfg.dense_output,
        events=events,
    )


# ---------------------------------------------------------------------------
# TEST A -- atmosphere switching surface value
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "h_m, expected_sign",
    [(90_000.0, -1), (100_000.0, 0), (110_000.0, +1)],
)
def test_a_interface_value_sign(h_m, expected_sign):
    """G_atm = h - h_atm: negative below, zero at, positive above."""
    env = EnvironmentParams()
    state = _state(env, h_m=h_m, v_mps=6_500.0, gamma_deg=0.0)

    g = atmosphere_interface_value(state, env)

    if expected_sign < 0:
        assert g < 0.0
    elif expected_sign == 0:
        assert abs(g) < 1e-9
    else:
        assert g > 0.0


def test_a_interface_value_equals_h_minus_boundary():
    """G = h - h_atm exactly, with h_atm from the frozen env field and the
    D1 constant as cross-check (no second 100 000 m literal)."""
    env = EnvironmentParams()
    for h_m in (90_000.0, 100_000.0, 110_000.0):
        state = _state(env, h_m=h_m, v_mps=6_500.0, gamma_deg=0.0)
        expected = h_m - env.atmosphere_boundary
        assert atmosphere_interface_value(state, env) == pytest.approx(
            expected, rel=1e-12)
        # D1 constant consistency (default environment).
        assert atmosphere_interface_value(state, env) == pytest.approx(
            h_m - ATMOSPHERE_BOUNDARY_M, rel=1e-12)


# ---------------------------------------------------------------------------
# TEST B -- exit factory attributes
# ---------------------------------------------------------------------------
def test_b_exit_event_attributes():
    """Exit: direction = +1 (upward crossing), terminal = True."""
    env = EnvironmentParams()
    exit_event = make_atmosphere_exit_event(env)

    assert exit_event.direction == +1
    assert exit_event.terminal is True


@pytest.mark.parametrize(
    "h_m, expected_sign",
    [(99_000.0, -1), (100_000.0, 0), (101_000.0, +1)],
)
def test_b_exit_event_signs(h_m, expected_sign):
    """G_exit signs across the boundary."""
    env = EnvironmentParams()
    exit_event = make_atmosphere_exit_event(env)
    state = _state(env, h_m=h_m, v_mps=6_500.0, gamma_deg=0.0)

    g = exit_event(0.0, state)

    if expected_sign < 0:
        assert g < 0.0
    elif expected_sign == 0:
        assert abs(g) < 1e-9
    else:
        assert g > 0.0


# ---------------------------------------------------------------------------
# TEST C -- entry factory attributes
# ---------------------------------------------------------------------------
def test_c_entry_event_attributes():
    """Entry: direction = -1 (downward crossing), terminal = True, and the
    switching surface is identical to the exit surface."""
    env = EnvironmentParams()
    entry_event = make_atmosphere_entry_event(env)
    exit_event = make_atmosphere_exit_event(env)

    assert entry_event.direction == -1
    assert entry_event.terminal is True

    for h_m in (90_000.0, 100_000.0, 110_000.0):
        state = _state(env, h_m=h_m, v_mps=6_500.0, gamma_deg=0.0)
        assert entry_event(0.0, state) == pytest.approx(
            exit_event(0.0, state), rel=1e-12)


# ---------------------------------------------------------------------------
# TEST D -- ATM pull-out diagnostic
# ---------------------------------------------------------------------------
def test_d_pullout_event_attributes():
    """Pull-out: root = gamma, direction = +1 (negative -> positive),
    diagnostic only (terminal = False)."""
    env = EnvironmentParams()
    pullout_event = make_pullout_event()

    assert pullout_event.direction == +1
    assert pullout_event.terminal is False

    for gamma_deg in (-1.0, 0.0, +1.0):
        state = _state(env, h_m=60_000.0, v_mps=6_500.0,
                       gamma_deg=gamma_deg)
        assert pullout_event(0.0, state) == pytest.approx(
            np.deg2rad(gamma_deg), rel=1e-12)


# ---------------------------------------------------------------------------
# TEST E -- VAC apogee diagnostic
# ---------------------------------------------------------------------------
def test_e_vacuum_apogee_event_attributes():
    """VAC apogee: root = gamma, direction = -1 (positive -> negative),
    diagnostic only (terminal = False)."""
    env = EnvironmentParams()
    apogee_event = make_vacuum_apogee_event()

    assert apogee_event.direction == -1
    assert apogee_event.terminal is False

    for gamma_deg in (-1.0, 0.0, +1.0):
        state = _state(env, h_m=150_000.0, v_mps=6_500.0,
                       gamma_deg=gamma_deg)
        assert apogee_event(0.0, state) == pytest.approx(
            np.deg2rad(gamma_deg), rel=1e-12)


# ---------------------------------------------------------------------------
# TEST F -- SRTI candidate
# ---------------------------------------------------------------------------
def test_f_srti_candidate_attributes():
    """SRTI candidate: root = gamma, direction = -1, terminal = True.

    The primitive locates ONLY the raw ATM downward-gamma-crossing root.
    SRTI classification (mode == SANGER_ATM, pull-out already observed in
    the current pass, no prior atmosphere exit) is a state-machine-history
    decision explicitly deferred to D3.
    """
    env = EnvironmentParams()
    candidate = make_srti_candidate_event()

    assert candidate.direction == -1
    assert candidate.terminal is True

    for gamma_deg in (-2.0, 0.0, +2.0):
        state = _state(env, h_m=60_000.0, v_mps=6_500.0,
                       gamma_deg=gamma_deg)
        assert candidate(0.0, state) == pytest.approx(
            np.deg2rad(gamma_deg), rel=1e-12)


# ---------------------------------------------------------------------------
# TEST G -- exit short-integration regression
# ---------------------------------------------------------------------------
def test_g_short_integration_detects_exactly_one_exit():
    """An ATM segment rising through h = 100 km must report exactly one
    atmosphere exit near h_atm, with gamma still positive."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state0 = _state(env, h_m=95_000.0, v_mps=6_500.0, gamma_deg=3.0)

    rhs = lambda t, y: sanger_atm_rhs(t, y, env, vehicle, K_CONTROL)
    sol = _integrate(rhs, state0, events=make_atmosphere_exit_event(env))

    assert sol.t_events[0].size == 1
    t_exit = float(sol.t_events[0][0])
    state_exit = sol.sol(t_exit)
    h_exit = state_exit[0] - env.earth_radius

    assert abs(h_exit - 100_000.0) < 1.0
    assert state_exit[3] > 0.0  # still ascending at the exit


# ---------------------------------------------------------------------------
# TEST H -- entry short-integration regression
# ---------------------------------------------------------------------------
def test_h_short_integration_detects_exactly_one_entry():
    """A VAC segment descending through h = 100 km must report exactly one
    atmosphere entry near h_atm, with gamma still negative."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state0 = _state(env, h_m=105_000.0, v_mps=6_500.0, gamma_deg=-3.0)

    rhs = lambda t, y: sanger_vac_rhs(t, y, env, vehicle)
    sol = _integrate(rhs, state0, events=make_atmosphere_entry_event(env))

    assert sol.t_events[0].size == 1
    t_entry = float(sol.t_events[0][0])
    state_entry = sol.sol(t_entry)
    h_entry = state_entry[0] - env.earth_radius

    assert abs(h_entry - 100_000.0) < 1.0
    assert state_entry[3] < 0.0  # still descending at the entry


# ---------------------------------------------------------------------------
# TEST I -- exact-boundary ATM restart (synthetic E0, no fake exit at t = 0)
# ---------------------------------------------------------------------------
def test_i_exact_boundary_atm_restart_no_fake_exit():
    """Starting exactly at h = 100 km with gamma < 0 (synthetic E0) and only
    the exit event registered must NOT report an atmosphere exit at t = 0;
    the trajectory continues into the atmosphere (h decreases)."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state0 = _state(env, h_m=100_000.0, v_mps=6_500.0, gamma_deg=-5.0)

    rhs = lambda t, y: sanger_atm_rhs(t, y, env, vehicle, K_CONTROL)
    sol = _integrate(rhs, state0, events=make_atmosphere_exit_event(env),
                     t_span=(0.0, 30.0))

    assert sol.t_events[0].size == 0
    # The trajectory must keep moving into the atmosphere.
    assert sol.y[0, -1] - env.earth_radius < 100_000.0


# ---------------------------------------------------------------------------
# TEST J -- exact-boundary VAC restart (no fake entry at t = 0)
# ---------------------------------------------------------------------------
def test_j_exact_boundary_vac_restart_no_fake_entry():
    """Starting exactly at h = 100 km with gamma > 0 and only the entry
    event registered must NOT report an atmosphere entry at t = 0; the
    trajectory continues outward (h increases)."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state0 = _state(env, h_m=100_000.0, v_mps=6_500.0, gamma_deg=3.0)

    rhs = lambda t, y: sanger_vac_rhs(t, y, env, vehicle)
    sol = _integrate(rhs, state0, events=make_atmosphere_entry_event(env),
                     t_span=(0.0, 30.0))

    assert sol.t_events[0].size == 0
    # The trajectory must keep moving outward.
    assert sol.y[0, -1] - env.earth_radius > 100_000.0


# ---------------------------------------------------------------------------
# TEST K -- direction discrimination
# ---------------------------------------------------------------------------
def test_k_downward_crossing_is_not_an_exit():
    """Exit (direction = +1) must NOT fire on a descending crossing."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state0 = _state(env, h_m=105_000.0, v_mps=6_500.0, gamma_deg=-3.0)

    rhs = lambda t, y: sanger_vac_rhs(t, y, env, vehicle)
    sol = _integrate(rhs, state0, events=make_atmosphere_exit_event(env),
                     t_span=(0.0, 30.0))

    assert sol.t_events[0].size == 0


def test_k_upward_crossing_is_not_an_entry():
    """Entry (direction = -1) must NOT fire on an ascending crossing."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state0 = _state(env, h_m=95_000.0, v_mps=6_500.0, gamma_deg=3.0)

    rhs = lambda t, y: sanger_atm_rhs(t, y, env, vehicle, K_CONTROL)
    sol = _integrate(rhs, state0, events=make_atmosphere_entry_event(env),
                     t_span=(0.0, 30.0))

    assert sol.t_events[0].size == 0


# ---------------------------------------------------------------------------
# TEST L -- interface normal
# ---------------------------------------------------------------------------
def test_l_interface_normal():
    """nabla G = [1, 0, 0, 0]^T in the frozen [r, theta, v, gamma] ordering
    (future hybrid-sensitivity metadata; D0 spec §16)."""
    normal = atmosphere_interface_normal()
    np.testing.assert_array_equal(normal, np.array([1.0, 0.0, 0.0, 0.0]))


# ---------------------------------------------------------------------------
# TEST M -- events are pure observers (no state mutation)
# ---------------------------------------------------------------------------
def test_m_event_functions_do_not_mutate_state():
    """Event factories must never clip or alter the state (x+ = x- contract)."""
    env = EnvironmentParams()
    state = _state(env, h_m=100_000.0, v_mps=6_500.0, gamma_deg=2.0)
    state_before = state.copy()

    for factory in (
        make_atmosphere_exit_event(env),
        make_atmosphere_entry_event(env),
        make_pullout_event(),
        make_vacuum_apogee_event(),
        make_srti_candidate_event(),
    ):
        factory(0.0, state)

    np.testing.assert_array_equal(state, state_before)
