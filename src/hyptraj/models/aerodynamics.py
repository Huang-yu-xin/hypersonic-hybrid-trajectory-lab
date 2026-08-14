from dataclasses import dataclass

from .parameters import VehicleParams


@dataclass(frozen=True)
class AerodynamicForces:
    dynamic_pressure: float
    lift_coefficient: float
    drag: float
    lift: float


def aerodynamic_forces(
    density: float,
    velocity: float,
    lift_to_drag_ratio: float,
    vehicle: VehicleParams,
) -> AerodynamicForces:
    if density < 0.0:
        raise ValueError("Density must be non-negative.")

    if velocity < 0.0:
        raise ValueError("Velocity magnitude must be non-negative.")

    if lift_to_drag_ratio < 0.0:
        raise ValueError("Lift-to-drag ratio must be non-negative.")

    q = 0.5 * density * velocity**2

    cd = vehicle.drag_coefficient
    cl = lift_to_drag_ratio * cd

    drag = q * vehicle.reference_area * cd
    lift = q * vehicle.reference_area * cl

    return AerodynamicForces(
        dynamic_pressure=q,
        lift_coefficient=cl,
        drag=drag,
        lift=lift,
    )