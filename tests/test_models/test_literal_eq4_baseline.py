"""Regression test for the literal Eq.(4) uncontrolled baseline.

The reference values below were produced by the fully converged baseline
run (DOP853, rtol=1e-8, component-scaled atol, max_step=10 s) with the
problem-statement parameters and initial conditions:

    h0 = 100 km, v0 = 7000 m/s, gamma0 = -5 deg, theta0 = 0, K = 3.0

These values are the confirmed stable output of this repository and serve
to detect future regressions (RHS changes, parameter changes, solver
config changes).  The tolerance rtol=1e-4 (0.01 %) leaves several orders
of magnitude of headroom over the solver's own convergence level
(~1e-9..1e-10) so that platform / library-version differences do not
produce false alarms, while any genuine model regression is caught.

Note: this is the LITERAL Eq.(4) uncontrolled solution (skip to ~130 km).
The approved Qian continuous-glide baseline is tested separately in
test_qian_continuous_glide.py.  The problem-statement Table-2 reference
ranges (6000-8500 km / 1200-1800 s / 800-1500 m/s) are NOT reproducible
from the stated equations and parameters (verified by the 9-point
checklist, solver convergence, an independent implementation and
parameter scans); they are therefore not used here.
"""

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation import integrate_trajectory, run_sanity_checks

# Confirmed stable baseline output (reference values).
REFERENCE_FLIGHT_TIME_S = 3508.886850796115
REFERENCE_RANGE_KM = 13578.506212620006
REFERENCE_TERMINAL_VELOCITY_MPS = 159.95359846310112

# Strict-but-robust regression tolerance.
RTOL = 1e-4


def _run_baseline():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)

    return integrate_trajectory(env, vehicle, initial, control)


def test_baseline_integrates_to_ground():
    result = _run_baseline()

    assert result.metadata["integration"]["success"] is True
    assert result.events["ground_detected"] is True
    assert result.events["ground_event_altitude_residual_m"] < 1e-3


def test_baseline_flight_time_regression():
    result = _run_baseline()

    assert result.metrics["flight_time_s"] == pytest.approx(
        REFERENCE_FLIGHT_TIME_S, rel=RTOL
    )


def test_baseline_range_regression():
    result = _run_baseline()

    assert result.metrics["range_km"] == pytest.approx(
        REFERENCE_RANGE_KM, rel=RTOL
    )


def test_baseline_terminal_velocity_regression():
    result = _run_baseline()

    assert result.metrics["terminal_velocity_mps"] == pytest.approx(
        REFERENCE_TERMINAL_VELOCITY_MPS, rel=RTOL
    )


def test_baseline_metrics_are_complete():
    result = _run_baseline()

    required_keys = {
        "flight_time_s",
        "range_km",
        "terminal_velocity_mps",
        "max_altitude_km",
        "max_dynamic_pressure_pa",
        "dynamic_pressure_integral_pas",
        "ground_event_altitude_residual_m",
    }

    assert required_keys <= set(result.metrics)


def test_baseline_sanity_checks_pass():
    result = _run_baseline()

    sanity = run_sanity_checks(result)

    assert all(sanity.values()), sanity


def test_baseline_state_and_derived_are_finite():
    result = _run_baseline()

    assert np.all(np.isfinite(result.state))
    assert all(np.all(np.isfinite(v)) for v in result.derived.values())
