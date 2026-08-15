"""D6 lightweight numerical-validation regression tests.

Kept intentionally light (the full sweeps live in
experiments/05_sanger_numerical_validation/):

A. production topology equals the frozen D5 baseline topology;
B. production and a tight configuration give the same skip_count;
C. both terminal kinds are SRTI;
D. event sequences equal;
E. key event errors are below the loose-but-meaningful D5 bounds.

The tight configuration is the D6 numerical reference (DOP853,
rtol=1e-12, atol=[1e-7,1e-14,1e-10,1e-14], max_step=0.1 s) — a
numerical reference, not an analytic solution.
"""

import json
from pathlib import Path

import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import SRTI, integrate_sanger_hybrid
from hyptraj.simulation.trajectory import SolverConfig

REFERENCE_PATH = Path(__file__).parent / "data" / "sanger_baseline_v1.json"

# D5 tolerance policy (docs/phase_d/sanger_baseline.md §11).
TOL_TIME_S = 1e-3
TOL_ALTITUDE_M = 1.0
TOL_VELOCITY_MPS = 1e-2
TOL_RANGE_M = 10.0

TIGHT_SOLVER = SolverConfig(
    method="DOP853",
    rtol=1e-12,
    atol=PRODUCTION_SOLVER_CONFIG.atol * 1e-3,
    max_step=0.1,
    dense_output=True,
)


@pytest.fixture(scope="module")
def baseline_reference():
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def runs():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    out = {}
    for name, solver in (
        ("production", PRODUCTION_SOLVER_CONFIG),
        ("tight", TIGHT_SOLVER),
    ):
        traj = integrate_sanger_hybrid(env, vehicle, initial, control,
                                       solver=solver)
        out[name] = (traj, analyze_sanger_trajectory(traj, env))
    return env, out


# ---------------------------------------------------------------------------
def test_a_production_topology_matches_frozen_baseline(runs,
                                                       baseline_reference):
    env, out = runs
    traj, metrics = out["production"]
    ref = baseline_reference

    assert traj.terminal_kind == SRTI
    assert traj.success is True
    assert metrics.skip_count == ref["completed_skip_count"]
    assert [s.mode for s in traj.segments] == ref["mode_sequence"]
    assert [e.kind for e in traj.events] == ref["event_sequence"]


def test_b_same_skip_count_production_vs_tight(runs):
    env, out = runs
    _, m_prod = out["production"]
    _, m_tight = out["tight"]
    assert m_prod.skip_count == m_tight.skip_count


def test_c_both_terminal_kind_srti(runs):
    env, out = runs
    for name in ("production", "tight"):
        traj, _ = out[name]
        assert traj.terminal_kind == SRTI


def test_d_event_sequences_equal(runs):
    env, out = runs
    seq_prod = [e.kind for e in out["production"][0].events]
    seq_tight = [e.kind for e in out["tight"][0].events]
    assert seq_prod == seq_tight


def test_e_key_event_errors_below_bounds(runs):
    """Production vs tight: every common event within the D5 bounds."""
    env, out = runs
    traj_prod, _ = out["production"]
    traj_tight, _ = out["tight"]

    refs = {}
    for e in traj_tight.events:
        refs.setdefault(e.kind, []).append(e)

    for e in traj_prod.events:
        ref = refs[e.kind].pop(0)
        assert abs(e.time - ref.time) <= TOL_TIME_S
        assert abs(e.state[0] - ref.state[0]) <= TOL_ALTITUDE_M
        assert abs(e.state[2] - ref.state[2]) <= TOL_VELOCITY_MPS
        assert abs(env.earth_radius * (e.state[1] - ref.state[1])
                   ) <= TOL_RANGE_M
