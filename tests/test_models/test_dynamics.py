import numpy as np
import pytest

from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)

from hyptraj.models.dynamics import (
    atmospheric_dynamics,
)

from hyptraj.controls.constant_k import (
    ConstantKControl,
)


def _baseline_state(env: EnvironmentParams) -> np.ndarray:
    """h = 100 km, v = 7000 m/s, gamma = -5 deg, theta = 0."""
    return np.array(
        [
            env.earth_radius + 100_000.0,
            0.0,
            7000.0,
            np.deg2rad(-5.0),
        ]
    )


def test_atmospheric_dynamics_returns_finite_state_derivative():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    state = _baseline_state(env)

    derivative = atmospheric_dynamics(
        0.0,
        state,
        env,
        vehicle,
        control,
    )

    assert derivative.shape == (4,)
    assert np.all(np.isfinite(derivative))


def test_initial_range_rate_is_positive():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    state = _baseline_state(env)

    derivative = atmospheric_dynamics(
        0.0,
        state,
        env,
        vehicle,
        control,
    )

    theta_dot = derivative[1]

    assert theta_dot > 0.0


def test_initial_altitude_rate_is_negative():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    state = _baseline_state(env)

    derivative = atmospheric_dynamics(
        0.0,
        state,
        env,
        vehicle,
        control,
    )

    r_dot = derivative[0]

    assert r_dot < 0.0


def test_negative_velocity_is_rejected():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    state = _baseline_state(env)
    state[2] = -1.0

    with pytest.raises(ValueError):
        atmospheric_dynamics(0.0, state, env, vehicle, control)


def test_nonpositive_radius_is_rejected():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    state = _baseline_state(env)
    state[0] = 0.0

    with pytest.raises(ValueError):
        atmospheric_dynamics(0.0, state, env, vehicle, control)


def test_below_ground_evaluation_is_guarded_and_state_unchanged():
    """solve_ivp may probe RHS slightly below h=0 while root-finding the
    ground event; the atmosphere input is clamped but the integration
    state itself must never be modified."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    control = ConstantKControl(3.0)

    state = _baseline_state(env)
    state[0] = env.earth_radius - 100.0  # h = -100 m (below ground)

    state_before = state.copy()

    derivative = atmospheric_dynamics(
        0.0,
        state,
        env,
        vehicle,
        control,
    )

    assert np.all(np.isfinite(derivative))
    assert np.array_equal(state, state_before)
