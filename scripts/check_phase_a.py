from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)

from hyptraj.models.gravity import gravity_acceleration
from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.aerodynamics import aerodynamic_forces


env = EnvironmentParams()
vehicle = VehicleParams()

for altitude in [0.0, 50_000.0, 100_000.0]:
    g = gravity_acceleration(altitude, env)
    rho = atmospheric_density(altitude, env)

    print(
        f"h={altitude / 1000:6.1f} km | "
        f"g={g:8.5f} m/s² | "
        f"rho={rho:.6e} kg/m³"
    )


rho100 = atmospheric_density(100_000.0, env)

aero = aerodynamic_forces(
    density=rho100,
    velocity=7000.0,
    lift_to_drag_ratio=3.0,
    vehicle=vehicle,
)

print()
print("Baseline initial aerodynamic state:")
print(f"q  = {aero.dynamic_pressure:.6e} Pa")
print(f"D  = {aero.drag:.6e} N")
print(f"L  = {aero.lift:.6e} N")
print(f"L/D = {aero.lift/aero.drag:.6f}")