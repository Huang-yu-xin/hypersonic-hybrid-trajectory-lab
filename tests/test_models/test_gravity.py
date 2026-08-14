import pytest

from hyptraj.models.gravity import gravity_acceleration
from hyptraj.models.parameters import EnvironmentParams


def test_gravity_at_sea_level():
    env = EnvironmentParams()

    g = gravity_acceleration(0.0, env)

    assert g == pytest.approx(env.gravity_sea_level)


def test_gravity_decreases_with_altitude():
    env = EnvironmentParams()

    g0 = gravity_acceleration(0.0, env)
    g50 = gravity_acceleration(50_000.0, env)
    g100 = gravity_acceleration(100_000.0, env)

    assert g0 > g50 > g100