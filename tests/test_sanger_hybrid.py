"""D1 unit tests for the Sanger hybrid-mode continuous dynamics.

Coverage (D0 spec docs/phase_d/sanger_model_spec.md, §5-6, §16-17):

TEST A -- SANGER_ATM wrapper equivalence: ``sanger_atm_rhs`` must equal the
          frozen atmospheric dynamics under u_L = 1 (and the approved Qian
          ENTRY_CAPTURE RHS) at multiple atmospheric states, proving Sanger
          ATM is NOT a second dynamics set.
TEST B -- SANGER_VAC equations: RHS matches the D0 mathematical definition,
          in particular dv/dt = -g sin(gamma) with no drag contribution.
TEST C -- SANGER_VAC sign sanity: ascending / descending physics.
TEST D -- SANGER_VAC gamma dynamics: no aerodynamic lift term.
TEST E -- ATM / VAC same-state difference: identical state definition but
          f_ATM != f_VAC, with the difference exactly the aero terms
          (the basic premise of future hybrid saltation).
TEST F -- VAC diagnostic invariants: specific mechanical energy and
          specific angular momentum formulas.
TEST G -- VAC is strictly aero-free: RHS independent of vehicle parameters.
"""

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.aerodynamics import aerodynamic_forces
from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.dynamics import atmospheric_dynamics
from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)
from hyptraj.modes.continuous_glide import (
    ENTRY_CAPTURE,
    continuous_glide_rhs,
)
from hyptraj.modes.sanger_hybrid import (
    ATMOSPHERE_BOUNDARY_M,
    MODES,
    SANGER_ATM,
    SANGER_VAC,
    sanger_atm_rhs,
    sanger_vac_rhs,
    specific_angular_momentum,
    specific_mechanical_energy,
)

K_CONTROL = ConstantKControl(3.0)

# Frozen state convention: state = [r, theta, v, gamma], h = r - R_E.
def _state(env, h_m, v_mps, gamma_deg, theta_rad=0.0):
    return np.array(
        [
            env.earth_radius + h_m,
            theta_rad,
            v_mps,
            np.deg2rad(gamma_deg),
        ],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# TEST A -- SANGER_ATM wrapper equivalence (no second dynamics set)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("h_m", [80_000.0, 60_000.0, 40_000.0])
def test_a_atm_wrapper_equals_frozen_atmospheric_dynamics(h_m):
    """sanger_atm_rhs must be bitwise-identical to the frozen RHS (u_L = 1)."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m, v_mps=6_500.0, gamma_deg=2.0, theta_rad=0.1)

    expected = atmospheric_dynamics(0.0, state, env, vehicle, K_CONTROL)
    actual = sanger_atm_rhs(0.0, state, env, vehicle, K_CONTROL)

    # The frozen atmospheric_dynamics uses the FULL lift in gamma_dot
    # (no u_L scaling), i.e. exactly the u_L = 1 / sigma = 0 semantics.
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("h_m", [80_000.0, 60_000.0, 40_000.0])
def test_a_atm_wrapper_equals_qian_entry_capture_rhs(h_m):
    """Sanger ATM must also match the approved Qian ENTRY_CAPTURE RHS."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m, v_mps=6_500.0, gamma_deg=2.0, theta_rad=0.1)

    expected = continuous_glide_rhs(
        ENTRY_CAPTURE, 0.0, state, env, vehicle, K_CONTROL)
    actual = sanger_atm_rhs(0.0, state, env, vehicle, K_CONTROL)

    np.testing.assert_array_equal(actual, expected)


def test_a_atm_full_lift_semantics():
    """u_L = 1: gamma_dot uses the full available lift (sigma = 0)."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=60_000.0, v_mps=6_500.0, gamma_deg=-3.0)

    r, _theta, v, gamma = state
    g = env.gravity_sea_level * (env.earth_radius / r) ** 2
    rho = atmospheric_density(r - env.earth_radius, env)
    aero = aerodynamic_forces(rho, v, K_CONTROL.value, vehicle)
    L = aero.lift

    expected_gamma_dot = (
        L / (vehicle.mass * v)
        + (v / r - g / v) * np.cos(gamma)
    )

    actual = sanger_atm_rhs(0.0, state, env, vehicle, K_CONTROL)
    assert actual[3] == pytest.approx(expected_gamma_dot, rel=1e-12)


# ---------------------------------------------------------------------------
# TEST B -- SANGER_VAC equations (D0 spec §6)
# ---------------------------------------------------------------------------
def test_b_vac_equations_match_definition():
    """VAC RHS must equal the D0 mathematical definition at a vacuum state."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=120_000.0, v_mps=6_500.0, gamma_deg=3.0,
                   theta_rad=0.05)

    r, _theta, v, gamma = state
    g = env.gravity_sea_level * (env.earth_radius / r) ** 2

    expected = np.array(
        [
            v * np.sin(gamma),
            v * np.cos(gamma) / r,
            -g * np.sin(gamma),
            (v / r - g / v) * np.cos(gamma),
        ],
        dtype=float,
    )

    actual = sanger_vac_rhs(0.0, state, env, vehicle)
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-15)


def test_b_vac_dvdt_has_no_drag_contribution():
    """dv/dt = -g sin(gamma) exactly; no drag term may appear."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=120_000.0, v_mps=6_500.0, gamma_deg=3.0)

    r, _theta, v, gamma = state
    g = env.gravity_sea_level * (env.earth_radius / r) ** 2

    actual = sanger_vac_rhs(0.0, state, env, vehicle)
    assert actual[2] == pytest.approx(-g * np.sin(gamma), rel=1e-12)


# ---------------------------------------------------------------------------
# TEST C -- SANGER_VAC sign sanity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("v_mps", [3_000.0, 6_500.0, 9_000.0])
def test_c_vac_ascending_physics(v_mps):
    """gamma > 0: dh/dt > 0 and (for these speeds) dv/dt < 0."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=150_000.0, v_mps=v_mps, gamma_deg=5.0)

    r_dot, _theta_dot, v_dot, _gamma_dot = sanger_vac_rhs(
        0.0, state, env, vehicle)

    assert r_dot > 0.0
    assert v_dot < 0.0  # gravity only: -g sin(gamma) < 0


@pytest.mark.parametrize("v_mps", [3_000.0, 6_500.0, 9_000.0])
def test_c_vac_descending_physics(v_mps):
    """gamma < 0: dh/dt < 0 and (for these speeds) dv/dt > 0."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=150_000.0, v_mps=v_mps, gamma_deg=-5.0)

    r_dot, _theta_dot, v_dot, _gamma_dot = sanger_vac_rhs(
        0.0, state, env, vehicle)

    assert r_dot < 0.0
    assert v_dot > 0.0  # gravity only: -g sin(gamma) > 0


def test_c_vac_zero_gamma():
    """gamma = 0: no altitude / velocity change in vacuum."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=150_000.0, v_mps=6_500.0, gamma_deg=0.0)

    r_dot, _theta_dot, v_dot, _gamma_dot = sanger_vac_rhs(
        0.0, state, env, vehicle)

    assert r_dot == pytest.approx(0.0, abs=1e-12)
    assert v_dot == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# TEST D -- SANGER_VAC gamma dynamics (no lift term)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "h_m, v_mps, gamma_deg",
    [
        (110_000.0, 5_000.0, 10.0),
        (130_000.0, 6_500.0, -8.0),
        (200_000.0, 8_000.0, 2.0),
    ],
)
def test_d_vac_gamma_dot_has_no_lift_term(h_m, v_mps, gamma_deg):
    """dgamma/dt = (v/r - g/v) cos(gamma); no L/(m v) contribution."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=h_m, v_mps=v_mps, gamma_deg=gamma_deg)

    r, _theta, v, gamma = state
    g = env.gravity_sea_level * (env.earth_radius / r) ** 2
    expected_gamma_dot = (v / r - g / v) * np.cos(gamma)

    actual = sanger_vac_rhs(0.0, state, env, vehicle)
    assert actual[3] == pytest.approx(expected_gamma_dot, rel=1e-12)


# ---------------------------------------------------------------------------
# TEST E -- ATM / VAC same-state difference (hybrid vector-field premise)
# ---------------------------------------------------------------------------
def test_e_atm_vac_same_state_differ_in_aero_terms():
    """Same state definition, but f_ATM != f_VAC exactly by the aero terms."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    state = _state(env, h_m=100_000.0, v_mps=6_500.0, gamma_deg=2.0)

    f_atm = sanger_atm_rhs(0.0, state, env, vehicle, K_CONTROL)
    f_vac = sanger_vac_rhs(0.0, state, env, vehicle)

    # Identical state definition / identical non-aero components.
    assert f_atm.shape == f_vac.shape == (4,)
    np.testing.assert_allclose(f_atm[0], f_vac[0], rtol=1e-12)  # r_dot
    np.testing.assert_allclose(f_atm[1], f_vac[1], rtol=1e-12)  # theta_dot

    # Aero contributions: dv/dt: ATM = VAC - D/m;  dgamma/dt: ATM = VAC + L/(mv).
    r, _theta, v, _gamma = state
    rho = atmospheric_density(r - env.earth_radius, env)
    aero = aerodynamic_forces(rho, v, K_CONTROL.value, vehicle)
    D, L = aero.drag, aero.lift

    assert f_atm[2] == pytest.approx(
        f_vac[2] - D / vehicle.mass, rel=1e-12)
    assert f_atm[3] == pytest.approx(
        f_vac[3] + L / (vehicle.mass * v), rel=1e-12)

    # Mode semantics differ: the aero terms are non-zero at h = 100 km.
    assert abs(f_atm[2] - f_vac[2]) > 0.0
    assert abs(f_atm[3] - f_vac[3]) > 0.0


# ---------------------------------------------------------------------------
# TEST F -- VAC diagnostic invariants (D0 spec §17)
# ---------------------------------------------------------------------------
def test_f_mechanical_energy_formula():
    """E = v^2/2 - mu/r with mu = g0 * R_E^2, consistent with the frozen MU."""
    from hyptraj.simulation.trajectory import MU

    env = EnvironmentParams()
    state = _state(env, h_m=120_000.0, v_mps=6_500.0, gamma_deg=3.0)

    r, _theta, v, _gamma = state
    mu = env.gravity_sea_level * env.earth_radius**2
    expected = 0.5 * v**2 - mu / r

    assert specific_mechanical_energy(state, env) == pytest.approx(
        expected, rel=1e-12)
    # Cross-check against the frozen hard-coded MU (default environment),
    # guarding against drift between the two definitions.
    assert specific_mechanical_energy(state, env) == pytest.approx(
        0.5 * v**2 - MU / r, rel=1e-12)
    # Gravitationally bound state: E < 0.
    assert specific_mechanical_energy(state, env) < 0.0


def test_f_angular_momentum_formula():
    """H = r * v * cos(gamma)."""
    env = EnvironmentParams()
    state = _state(env, h_m=120_000.0, v_mps=6_500.0, gamma_deg=3.0)

    r, _theta, v, gamma = state
    expected = r * v * np.cos(gamma)

    assert specific_angular_momentum(state, env) == pytest.approx(
        expected, rel=1e-12)


def test_f_invariants_do_not_modify_state():
    """Diagnostic primitives must never modify the input state."""
    env = EnvironmentParams()
    state = _state(env, h_m=120_000.0, v_mps=6_500.0, gamma_deg=3.0)
    state_before = state.copy()

    specific_mechanical_energy(state, env)
    specific_angular_momentum(state, env)

    np.testing.assert_array_equal(state, state_before)


# ---------------------------------------------------------------------------
# TEST G -- SANGER_VAC is strictly aero-free / vehicle-independent
# ---------------------------------------------------------------------------
def test_g_vac_rhs_independent_of_vehicle():
    """No aerodynamic force may enter VAC: RHS must not depend on vehicle."""
    env = EnvironmentParams()
    state = _state(env, h_m=120_000.0, v_mps=6_500.0, gamma_deg=3.0)

    vehicle_a = VehicleParams()
    vehicle_b = VehicleParams(
        mass=2_000.0, reference_area=2.0, drag_coefficient=0.5)

    np.testing.assert_array_equal(
        sanger_vac_rhs(0.0, state, env, vehicle_a),
        sanger_vac_rhs(0.0, state, env, vehicle_b),
    )


def test_g_vac_rhs_uses_gravity_and_environment():
    """VAC must retain gravity: a different Earth radius changes the RHS."""
    state = _state(EnvironmentParams(), h_m=120_000.0,
                   v_mps=6_500.0, gamma_deg=3.0)
    env_b = EnvironmentParams(earth_radius=6_400_000.0)
    vehicle = VehicleParams()

    f_a = sanger_vac_rhs(0.0, state, EnvironmentParams(), vehicle)
    f_b = sanger_vac_rhs(0.0, state, env_b, vehicle)

    assert not np.allclose(f_a, f_b)


# ---------------------------------------------------------------------------
# Mode / constant conventions
# ---------------------------------------------------------------------------
def test_modes_and_boundary_constant():
    """Mode strings and the frozen atmosphere cutoff are explicit."""
    assert MODES == (SANGER_ATM, SANGER_VAC)
    assert SANGER_ATM == "SANGER_ATM"
    assert SANGER_VAC == "SANGER_VAC"
    assert ATMOSPHERE_BOUNDARY_M == 100_000.0
    # The Sanger mode cutoff is exactly the frozen environment boundary.
    assert ATMOSPHERE_BOUNDARY_M == EnvironmentParams().atmosphere_boundary
