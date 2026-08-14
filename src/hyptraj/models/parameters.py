from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentParams:
    earth_radius: float = 6_371_000.0      # m
    gravity_sea_level: float = 9.81        # m/s^2
    density_sea_level: float = 1.225       # kg/m^3
    scale_height: float = 7_500.0          # m
    atmosphere_boundary: float = 100_000.0 # m


@dataclass(frozen=True)
class VehicleParams:
    mass: float = 1_000.0                  # kg
    reference_area: float = 1.0            # m^2
    drag_coefficient: float = 0.2


@dataclass(frozen=True)
class InitialCondition:
    altitude: float = 100_000.0             # m
    velocity: float = 7_000.0               # m/s
    flight_path_angle_deg: float = -5.0     # deg
    range_angle: float = 0.0                # rad