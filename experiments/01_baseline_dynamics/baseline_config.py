"""Shared configuration of the Phase B literal Eq.(4) baseline experiment.

All paths are derived from this file's location, so the experiment is
reproducible regardless of the current working directory.

The literal Eq.(4) uncontrolled solution is retained permanently as the
diagnostic / reference baseline (see docs/model_audit/phase_b5_*.md).
"""

from pathlib import Path

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "results" / "baseline" / "literal_eq4_uncontrolled"
FIGURE_DIR = OUTPUT_DIR / "figures"

# Benchmark sanity ranges from the problem statement.
# These are NOT regression tolerances.
REFERENCE_RANGE_KM = (6000.0, 8500.0)
REFERENCE_FLIGHT_TIME_S = (1200.0, 1800.0)
REFERENCE_TERMINAL_VELOCITY_MPS = (800.0, 1500.0)


def get_baseline_setup():
    """Environment, vehicle, initial condition and control of the baseline."""
    env = EnvironmentParams()
    vehicle = VehicleParams()

    initial = InitialCondition(
        altitude=100_000.0,     # h0 = 100 km
        velocity=7_000.0,       # v0 = 7000 m/s
        flight_path_angle_deg=-5.0,  # gamma0 = -5 deg
        range_angle=0.0,        # theta0 = 0
    )

    control = ConstantKControl(3.0)  # K = 3.0

    return env, vehicle, initial, control
