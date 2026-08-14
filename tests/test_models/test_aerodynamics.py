import pytest

from hyptraj.models.aerodynamics import aerodynamic_forces
from hyptraj.models.parameters import VehicleParams


def test_zero_velocity_gives_zero_force():
    vehicle = VehicleParams()

    aero = aerodynamic_forces(
        density=1.225,
        velocity=0.0,
        lift_to_drag_ratio=3.0,
        vehicle=vehicle,
    )

    assert aero.drag == pytest.approx(0.0)
    assert aero.lift == pytest.approx(0.0)


def test_lift_drag_ratio_is_correct():
    vehicle = VehicleParams()

    aero = aerodynamic_forces(
        density=0.1,
        velocity=1000.0,
        lift_to_drag_ratio=3.0,
        vehicle=vehicle,
    )

    assert aero.lift / aero.drag == pytest.approx(3.0)


def test_force_scales_with_velocity_squared():
    vehicle = VehicleParams()

    aero1 = aerodynamic_forces(
        density=0.1,
        velocity=1000.0,
        lift_to_drag_ratio=3.0,
        vehicle=vehicle,
    )

    aero2 = aerodynamic_forces(
        density=0.1,
        velocity=2000.0,
        lift_to_drag_ratio=3.0,
        vehicle=vehicle,
    )

    assert aero2.drag / aero1.drag == pytest.approx(4.0)