import numpy as np

from .parameters import EnvironmentParams


def atmospheric_density(
    altitude: float,
    env: EnvironmentParams,
) -> float:
    """
    Baseline exponential atmosphere model.

    rho(h) = rho0 * exp(-h / H)
    """
    if altitude < 0.0:
        raise ValueError("Baseline atmosphere expects altitude >= 0.")

    return env.density_sea_level * np.exp(
        -altitude / env.scale_height
    )