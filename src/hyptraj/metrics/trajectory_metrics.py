"""Trajectory-level summary metrics for the Phase B baseline."""

import numpy as np


def dynamic_pressure_integral(
    time_s: np.ndarray,
    dynamic_pressure_pa: np.ndarray,
) -> float:
    """Integral of the dynamic pressure over flight time ``int q(t) dt`` [Pa s].

    Note: this is the problem-statement *dynamic-pressure integral proxy*
    for thermal load; it is not a strict real heat-flux integral.
    """
    return float(np.trapezoid(dynamic_pressure_pa, time_s))


def compute_trajectory_metrics(
    time_s: np.ndarray,
    altitude_m: np.ndarray,
    range_m: np.ndarray,
    velocity_mps: np.ndarray,
    dynamic_pressure_pa: np.ndarray,
) -> dict[str, float]:
    """Compute the Phase B core metrics on a uniform output grid.

    Returns
    -------
    dict
        Keys: ``flight_time_s``, ``range_km``, ``terminal_velocity_mps``,
        ``max_altitude_km``, ``max_dynamic_pressure_pa`` and
        ``dynamic_pressure_integral_pas``.
    """
    return {
        "flight_time_s": float(time_s[-1]),
        "range_km": float(range_m[-1] / 1000.0),
        "terminal_velocity_mps": float(velocity_mps[-1]),
        "max_altitude_km": float(np.max(altitude_m) / 1000.0),
        "max_dynamic_pressure_pa": float(np.max(dynamic_pressure_pa)),
        "dynamic_pressure_integral_pas": dynamic_pressure_integral(
            time_s,
            dynamic_pressure_pa,
        ),
    }
