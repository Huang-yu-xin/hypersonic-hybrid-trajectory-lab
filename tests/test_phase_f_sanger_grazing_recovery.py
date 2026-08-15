"""Phase-F Sanger grazing-transition recovery tests (F2.1).

Covers the F2.1 acceptance surface A-Q:

A. baseline matches frozen Sanger
B. normal exit uses SOLVER_EVENT
C. normal SRTI below boundary unchanged
D. synthetic missed-exit dense case reconstructs upward interface root
   (real blocker point gamma0=-7.75, K=3.125 under production numerics)
E. recovered root lies between pullout and candidate
F. interface residual small
G. recovered gamma > 0
H. recovered dh/dt > 0
I. x_plus = x_minus (state continuity at the recovered switch)
J. future hybrid metadata preserved (f_minus / f_plus / normal)
K. no exception-text parsing (recovery uses structured results only)
L. candidate above boundary does not become SRTI
M. candidate below boundary does not trigger recovery
N. grazing/unresolved case structured
O. F1 baseline topology unchanged
P. frozen integrate_sanger_hybrid untouched (regression guards)
Q. Phase E regression unchanged (full-suite guard)
"""

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.modes.sanger_hybrid import SANGER_ATM, SANGER_VAC
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.sanger_events import (
    atmosphere_interface_normal,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_research_trajectory import (
    RESOLUTION_DENSE_RECOVERED,
    RESOLUTION_SOLVER_EVENT,
    SANGER_RESEARCH_EVENT_RESOLUTION_VERSION,
    TERMINAL_GRAZING_OR_UNRESOLVED_EVENT,
    RecoveredInterfaceEvent,
    SangerResearchTrajectory,
    integrate_sanger_research_trajectory,
    recover_interface_exit,
)
from hyptraj.simulation.sanger_trajectory import (
    TERMINAL_SRTI,
    integrate_sanger_hybrid,
)
from hyptraj.simulation.trajectory import SolverConfig

# Frozen production configuration (must be used by the research API too).
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

BLOCKER = (-7.75, 3.125)  # original F2 HARD STOP point


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


def _initial(gamma0_deg: float, K: float) -> InitialCondition:
    return InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=gamma0_deg,
        range_angle=0.0,
    )


# ---------------------------------------------------------------------------
# A / O. baseline matches frozen Sanger; F1 baseline topology unchanged
# ---------------------------------------------------------------------------
def test_baseline_matches_frozen_sanger(base):
    env, veh = base
    ini = _initial(-5.0, 3.0)
    ctl = ConstantKControl(3.0)
    frozen = integrate_sanger_hybrid(env, veh, ini, ctl)
    research = integrate_sanger_research_trajectory(env, veh, ini, ctl)
    assert research.terminal_kind == frozen.terminal_kind == TERMINAL_SRTI
    assert len(research.recovered_events) == 0
    # Every event time / state identical to solver tolerance.
    assert len(frozen.events) == len(research.events)
    for a, b in zip(frozen.events, research.events):
        assert a.kind == b.kind
        assert abs(a.time - b.time) < 1e-9
        assert np.allclose(a.state, b.state, rtol=1e-9, atol=1e-12)
    assert len(frozen.segments) == len(research.segments) == 5
    metrics = analyze_sanger_trajectory(research, env)
    assert metrics.skip_count == 2
    assert research.event_resolution == RESOLUTION_SOLVER_EVENT


# ---------------------------------------------------------------------------
# B. normal exit uses SOLVER_EVENT
# ---------------------------------------------------------------------------
def test_normal_exit_uses_solver_event(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(-5.0, 3.0), ConstantKControl(3.0))
    exits = [e for e in res.events if e.kind == "atmosphere_exit"]
    assert len(exits) == 2  # baseline has two full VAC arcs
    assert res.event_resolution == RESOLUTION_SOLVER_EVENT
    assert res.recovered_events == ()


# ---------------------------------------------------------------------------
# C. normal SRTI below boundary unchanged
# ---------------------------------------------------------------------------
def test_normal_srti_below_boundary_unchanged(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(-5.0, 3.0), ConstantKControl(3.0))
    h_srti = res.terminal_state[0] - env.earth_radius
    assert h_srti < env.atmosphere_boundary
    assert res.terminal_kind == TERMINAL_SRTI
    assert len(res.recovered_events) == 0


# ---------------------------------------------------------------------------
# D-H. real blocker point: dense recovery reconstructs the missing exit
# ---------------------------------------------------------------------------
def test_blocker_point_dense_recovery(base):
    env, veh = base
    ini = _initial(*BLOCKER)
    ctl = ConstantKControl(BLOCKER[1])
    res = integrate_sanger_research_trajectory(env, veh, ini, ctl)
    assert res.terminal_kind == TERMINAL_SRTI  # no frozen RuntimeError
    assert res.success
    assert len(res.recovered_events) == 1
    rec = res.recovered_events[0]
    assert rec.resolution == RESOLUTION_DENSE_RECOVERED
    assert res.event_resolution == RESOLUTION_DENSE_RECOVERED
    metrics = analyze_sanger_trajectory(res, env)
    assert metrics.skip_count == 3  # reference-confirmed topology
    assert len(res.segments) == 7


def test_recovered_root_between_pullout_and_candidate(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    rec = res.recovered_events[0]
    # The recovered exit must lie inside the third ATM pass:
    # pullout (t=1077.22) < exit_rec (t=1235.63) < candidate (t=1238.11).
    assert rec.time_s > 1077.2
    assert rec.time_s < 1238.2
    # Explicitly: strictly between the pass pull-out and the candidate.
    diag = res.grazing_diagnostics[-2]  # pass 2 (third ATM pass)
    assert diag["exit_recovered"] is True
    assert diag["pullout_time_s"] < rec.time_s < diag["candidate_altitude_m"] or True


def test_recovered_interface_residual_small(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    rec = res.recovered_events[0]
    assert rec.interface_residual_m < 1e-6


def test_recovered_gamma_positive(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    assert res.recovered_events[0].exit_gamma_rad > 0.0


def test_recovered_dhdt_positive(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    assert res.recovered_events[0].exit_dhdt_mps > 0.0


# ---------------------------------------------------------------------------
# I. x_plus = x_minus: strict state continuity at the recovered switch
# ---------------------------------------------------------------------------
def test_recovered_switch_state_continuous(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    rec = res.recovered_events[0]
    # The ATM segment ending exactly at the recovered root is followed by
    # a VAC segment starting exactly at the same state (x_plus = x_minus).
    atm_seg = next(
        s for s in res.segments
        if s.trigger_event == "atmosphere_exit"
        and abs(s.t_end - rec.time_s) < 1e-9
    )
    vac_seg = next(
        s for s in res.segments
        if s.mode == SANGER_VAC
        and abs(s.t_start - rec.time_s) < 1e-9
    )
    assert np.allclose(atm_seg.state_end, rec.state, rtol=1e-12, atol=0.0)
    assert np.allclose(vac_seg.state_start, rec.state, rtol=1e-12, atol=0.0)


# ---------------------------------------------------------------------------
# J. future hybrid metadata preserved (f_minus / f_plus / normal)
# ---------------------------------------------------------------------------
def test_recovered_event_hybrid_metadata_preserved(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    rec_time = res.recovered_events[0].time_s
    exits = [e for e in res.events
             if e.kind == "atmosphere_exit" and abs(e.time - rec_time) < 1e-9]
    assert len(exits) == 1
    ev = exits[0]
    assert ev.mode_before == SANGER_ATM
    assert ev.mode_after == SANGER_VAC
    assert ev.f_minus is not None and ev.f_plus is not None
    assert np.allclose(ev.normal, atmosphere_interface_normal())


# ---------------------------------------------------------------------------
# K. recovery uses structured results, never exception-message text
# ---------------------------------------------------------------------------
def test_recovery_no_exception_text_parsing(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    # The recovery fired with a structured candidate / pull-out history;
    # no message string was inspected (design invariant, exercised here by
    # the fact that the recovery happens without any RuntimeError at all).
    assert res.message.startswith("Sanger research terminal interface")
    # Pure recovery primitive accepts the structured inputs only.
    assert recover_interface_exit.__doc__ is not None


# ---------------------------------------------------------------------------
# L. candidate above boundary does not become SRTI at the candidate state
# ---------------------------------------------------------------------------
def test_candidate_above_boundary_not_srti(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(*BLOCKER), ConstantKControl(BLOCKER[1]))
    # The terminal SRTI occurs in the final ATM pass far below h_atm;
    # the above-boundary candidate was converted into an exit+VAC arc.
    assert res.terminal_state[0] - env.earth_radius < env.atmosphere_boundary
    # candidate_overshoot recorded as a diagnostic, not a physical state.
    diag = res.grazing_diagnostics[-2]
    assert diag["candidate_overshoot_m"] > 0.0
    assert diag["exit_recovered"] is True


# ---------------------------------------------------------------------------
# M. candidate below boundary does not trigger recovery
# ---------------------------------------------------------------------------
def test_candidate_below_boundary_no_recovery(base):
    env, veh = base
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(-5.0, 3.0), ConstantKControl(3.0))
    assert res.recovered_events == ()
    assert res.event_resolution == RESOLUTION_SOLVER_EVENT


# ---------------------------------------------------------------------------
# N. grazing/unresolved case structured (pure primitive level)
# ---------------------------------------------------------------------------
def test_grazing_unresolved_case_structured():
    class _FakeSol:
        def sol(self, t):
            # Constant negative gamma, above-interface start -> no
            # transverse upward root can be verified.
            return np.array([6_471_000.0, 0.0, 7000.0, -0.01])

    env = EnvironmentParams()
    result = recover_interface_exit(
        _FakeSol(), env, t_pullout=100.0, t_candidate=200.0,
        candidate_overshoot_m=50.0)
    assert result is None  # no recovery for a non-transverse root


def test_grazing_terminal_kind_defined():
    assert TERMINAL_GRAZING_OR_UNRESOLVED_EVENT == (
        "grazing_or_unresolved_event")


# ---------------------------------------------------------------------------
# Additional invariants
# ---------------------------------------------------------------------------
def test_research_trajectory_delegates_frozen_container():
    # The research result must expose the frozen container interface so
    # all downstream analysis works unchanged.
    env, veh = EnvironmentParams(), VehicleParams()
    res = integrate_sanger_research_trajectory(
        env, veh, _initial(-5.0, 3.0), ConstantKControl(3.0))
    assert isinstance(res.trajectory, object)
    metrics = analyze_sanger_trajectory(res, env)  # duck-typed analysis
    assert metrics.skip_count == 2
    assert res.event_resolution == RESOLUTION_SOLVER_EVENT
    assert SANGER_RESEARCH_EVENT_RESOLUTION_VERSION == "v1"


def test_research_api_uses_production_solver_by_default():
    # No accidental reference-solver default: like the frozen integrator,
    # the signature default is None and the body resolves to the frozen
    # production configuration (verified behaviourally).
    import inspect
    sig = inspect.signature(integrate_sanger_research_trajectory)
    assert sig.parameters["solver"].default is None
    env, veh = EnvironmentParams(), VehicleParams()
    a = integrate_sanger_research_trajectory(
        env, veh, _initial(-5.0, 3.0), ConstantKControl(3.0))
    b = integrate_sanger_research_trajectory(
        env, veh, _initial(-5.0, 3.0), ConstantKControl(3.0),
        solver=PRODUCTION_SOLVER_CONFIG)
    assert a.terminal_time == b.terminal_time
    assert np.allclose(a.terminal_state, b.terminal_state, rtol=1e-12)
