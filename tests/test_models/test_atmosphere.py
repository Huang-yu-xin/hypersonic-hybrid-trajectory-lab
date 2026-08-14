import pytest

from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.parameters import EnvironmentParams


def test_density_at_sea_level():
    env = EnvironmentParams()

    rho = atmospheric_density(0.0, env)

    assert rho == pytest.approx(env.density_sea_level)


def test_density_decreases_with_altitude():
    env = EnvironmentParams()

    rho0 = atmospheric_density(0.0, env)
    rho50 = atmospheric_density(50_000.0, env)
    rho100 = atmospheric_density(100_000.0, env)

    assert rho0 > rho50 > rho100 > 0.0


def test_negative_altitude_is_rejected():
    env = EnvironmentParams()

    with pytest.raises(ValueError):
        atmospheric_density(-1.0, env)