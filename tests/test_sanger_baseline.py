"""D5 canonical Sanger baseline regression tests.

The canonical baseline is produced by the frozen IC + frozen physics +
Phase C production numerics (results/sanger_hybrid/baseline).  The
tracked regression reference tests/data/sanger_baseline_v1.json was
generated from the canonical run at 16 significant digits.

Tolerance policy (documented in docs/phase_d/sanger_baseline.md):

    event time          abs <= 1e-3 s
    altitude            abs <= 1 m
    velocity            abs <= 1e-2 m/s
    range               abs <= 10 m
    gamma at extremum   abs <= 1e-6 rad
    integers/sequences  exact equality

The reference is a NUMERICAL baseline candidate, not an analytic truth.
The VAC invariant 1e-16 drifts are diagnostics and are deliberately NOT
frozen as regression constants (D6 defines their thresholds).

TEST A -- canonical structure matches the reference (sequences exact).
TEST B -- per-event regression (time / altitude / velocity / range).
TEST C -- per-cycle regression (durations, ranges, extremum altitudes).
TEST D -- global regression (research time / range / max altitude / SRTI).
TEST E -- structural validity independent of the JSON constants.
TEST F -- SRTI -> ground compatibility continuation.
TEST G -- compatibility continuation does not alter research metrics.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.sanger_compatibility import (
    integrate_sanger_ground_continuation,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    SRTI,
    integrate_sanger_hybrid,
)

REFERENCE_PATH = Path(__file__).parent / "data" / "sanger_baseline_v1.json"

# Tolerance policy (D5, documented).
TOL_TIME_S = 1e-3
TOL_ALTITUDE_M = 1.0
TOL_VELOCITY_MPS = 1e-2
TOL_RANGE_M = 10.0
TOL_GAMMA_RAD = 1e-6


@pytest.fixture(scope="module")
def reference():
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def canonical():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    traj = integrate_sanger_hybrid(env, vehicle, initial, control)
    metrics = analyze_sanger_trajectory(traj, env)
    return traj, metrics, env, vehicle, control


# ---------------------------------------------------------------------------
# TEST A -- canonical structure
# ---------------------------------------------------------------------------
def test_a_canonical_structure(reference, canonical):
    traj, metrics, env, vehicle, control = canonical

    assert traj.terminal_kind == SRTI
    assert traj.success is True
    assert metrics.skip_count == reference["completed_skip_count"]
    assert [s.mode for s in traj.segments] == reference["mode_sequence"]
    assert [e.kind for e in traj.events] == reference["event_sequence"]


# ---------------------------------------------------------------------------
# TEST B -- per-event regression
# ---------------------------------------------------------------------------
def test_b_event_regression(reference, canonical):
    traj, metrics, env, vehicle, control = canonical

    assert len(traj.events) == len(reference["events"])
    for e, ref in zip(traj.events, reference["events"]):
        assert e.kind == ref["kind"]
        assert abs(e.time - ref["time_s"]) <= TOL_TIME_S
        h = e.state[0] - env.earth_radius
        rng = env.earth_radius * e.state[1]
        assert abs(h - ref["altitude_m"]) <= TOL_ALTITUDE_M
        assert abs(e.state[2] - ref["velocity_mps"]) <= TOL_VELOCITY_MPS
        assert abs(rng - ref["range_m"]) <= TOL_RANGE_M
        assert abs(e.state[3] - ref["gamma_rad"]) <= TOL_GAMMA_RAD


# ---------------------------------------------------------------------------
# TEST C -- per-cycle regression
# ---------------------------------------------------------------------------
def test_c_cycle_regression(reference, canonical):
    traj, metrics, env, vehicle, control = canonical

    assert len(metrics.completed_cycles) == len(reference["cycles"])
    for c, ref in zip(metrics.completed_cycles, reference["cycles"]):
        assert abs(c.atmospheric_duration_s
                   - ref["atmospheric_duration_s"]) <= TOL_TIME_S
        assert abs(c.vacuum_duration_s - ref["vacuum_duration_s"]) <= TOL_TIME_S
        assert abs(c.atmospheric_range_m
                   - ref["atmospheric_range_m"]) <= TOL_RANGE_M
        assert abs(c.vacuum_range_m - ref["vacuum_range_m"]) <= TOL_RANGE_M
        assert abs(c.pullout_altitude_m
                   - ref["pullout_altitude_m"]) <= TOL_ALTITUDE_M
        assert abs(c.apogee_altitude_m
                   - ref["apogee_altitude_m"]) <= TOL_ALTITUDE_M


# ---------------------------------------------------------------------------
# TEST D -- global regression
# ---------------------------------------------------------------------------
def test_d_global_regression(reference, canonical):
    traj, metrics, env, vehicle, control = canonical

    assert abs(metrics.research_flight_time_s
               - reference["global"]["research_time_s"]) <= TOL_TIME_S
    assert abs(metrics.research_range_m
               - reference["global"]["research_range_m"]) <= TOL_RANGE_M
    assert abs(metrics.maximum_altitude_m
               - reference["global"]["max_altitude_m"]) <= TOL_ALTITUDE_M

    srti_ref = reference["srti"]
    assert abs(traj.terminal_time - srti_ref["time_s"]) <= TOL_TIME_S
    assert abs(traj.terminal_state[0] - env.earth_radius
               - srti_ref["altitude_m"]) <= TOL_ALTITUDE_M
    assert abs(traj.terminal_state[2]
               - srti_ref["velocity_mps"]) <= TOL_VELOCITY_MPS
    assert abs(env.earth_radius * traj.terminal_state[1]
               - srti_ref["range_m"]) <= TOL_RANGE_M


# ---------------------------------------------------------------------------
# TEST E -- structural validity (independent of the JSON constants)
# ---------------------------------------------------------------------------
def test_e_structural_validity(canonical):
    traj, metrics, env, vehicle, control = canonical

    # Event times strictly increasing; segments positive duration.
    real_times = [e.time for e in traj.events if not e.is_synthetic]
    assert all(b > a for a, b in zip(real_times, real_times[1:]))
    assert all(s.t_end > s.t_start for s in traj.segments)

    # ATM/VAC strict alternation.
    modes = [s.mode for s in traj.segments]
    assert all(a != b for a, b in zip(modes, modes[1:]))

    # Exact state continuity at every transition.
    for i in range(1, len(traj.segments)):
        np.testing.assert_array_equal(
            traj.segments[i].state_start, traj.segments[i - 1].state_end)

    # Completed cycles strictly ordered E-P-X-A-E.
    for c in metrics.completed_cycles:
        assert (c.entry_time < c.pullout_time < c.exit_time
                < c.apogee_time < c.next_entry_time)

    # Terminal incomplete pass is not counted as a skip.
    p = metrics.terminal_incomplete_pass
    assert p is not None
    assert p.completed_exit is False
    assert p.srti_time > p.entry_time
    assert metrics.skip_count == len(metrics.completed_cycles)

    # The final pass contains no atmosphere exit before the SRTI.
    final_pass = []
    for e in reversed(traj.events):
        if e.kind in (ATMOSPHERE_ENTRY, "synthetic_initial_entry"):
            break
        final_pass.append(e)
    assert not any(e.kind == ATMOSPHERE_EXIT for e in final_pass)


# ---------------------------------------------------------------------------
# TEST F -- ground compatibility continuation
# ---------------------------------------------------------------------------
def test_f_ground_continuation(canonical):
    traj, metrics, env, vehicle, control = canonical

    srti_state = traj.terminal_state.copy()
    srti_state_before = srti_state.copy()

    ground = integrate_sanger_ground_continuation(
        srti_state, traj.terminal_time, env, vehicle, control)

    # Input SRTI state never mutated.
    np.testing.assert_array_equal(srti_state, srti_state_before)

    assert ground.success is True
    assert ground.ground_time_s > traj.terminal_time
    h_ground = ground.ground_state[0] - env.earth_radius
    assert abs(h_ground) < 1.0  # ground event: h ~ 0
    assert ground.ground_state[2] > 0.0
    assert ground.nfev > 0


# ---------------------------------------------------------------------------
# TEST G -- research metrics independence from the compatibility tail
# ---------------------------------------------------------------------------
def test_g_research_metrics_independent_of_continuation(canonical):
    traj, metrics, env, vehicle, control = canonical

    before = metrics
    # Run the compatibility continuation (must not touch the trajectory).
    integrate_sanger_ground_continuation(
        traj.terminal_state, traj.terminal_time, env, vehicle, control)
    after = analyze_sanger_trajectory(traj, env)

    assert after.skip_count == before.skip_count
    assert after.research_flight_time_s == before.research_flight_time_s
    assert after.research_range_m == before.research_range_m
    assert after.maximum_altitude_m == before.maximum_altitude_m
    assert after.terminal_time_s == before.terminal_time_s
    assert after.terminal_altitude_m == before.terminal_altitude_m
    assert after.terminal_kind == SRTI
    assert after.terminal_incomplete_pass is not None
