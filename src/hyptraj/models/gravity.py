from .parameters import EnvironmentParams


def gravity_acceleration(
    altitude: float,
    env: EnvironmentParams,
) -> float:
    """
    Gravitational acceleration at altitude h.

    Parameters
    ----------
    altitude:
        Altitude above sea level [m].
    env:
        Environment parameters.

    Returns
    -------
    float
        Gravitational acceleration [m/s^2].
    """
    radius = env.earth_radius + altitude

    if radius <= 0.0:
        raise ValueError("Geocentric radius must be positive.")

    return env.gravity_sea_level * (
        env.earth_radius / radius
    ) ** 2