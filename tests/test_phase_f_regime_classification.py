"""Phase-F regime-classification tests (F0.1 amendment).

Covers the F0.1 acceptance surface A-L:

A. baseline Qian -> QIAN_RTI
B. baseline exact capture state consistent with Phase E
C. baseline exact RTI state consistent with Phase E
D. historical integrate_qian_glide unchanged
E. ground-before-capture classification path
F. ground-after-capture-before-RTI classification path
G. max-time -> CENSORED
H. solver failure -> NUMERICAL_FAILURE
I. censored != numerical failure
J. classifier never parses RuntimeError text (pure mapping)
K. Sanger baseline -> SRTI_N2 (thin Sanger classifier)
L. Phase E regression snapshot unchanged (guarded by the full suite)

Physical early-ground cases (E/F) run the REAL frozen dynamics with a
monkeypatched never-triggering counterpart event: they are classification
state-machine tests, not fabricated physics.  The solver-failure case (H)
uses a mocked solver outcome to test classification semantics only.
"""

import json
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis.sensitivity_trajectory import (
    QIAN_REGIME_BOUNDARY_AMBIGUOUS,
    QIAN_REGIME_CENSORED,
    QIAN_REGIME_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    QIAN_REGIME_GROUND_BEFORE_CAPTURE,
    QIAN_REGIME_NUMERICAL_FAILURE,
    QIAN_REGIME_RTI,
    classify_qian_regime,
    classify_sanger_regime,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.modes.continuous_glide import ENTRY_CAPTURE, QEG_GLIDE
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.qian_research_trajectory import (
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE,
    TERMINAL_MAX_TIME,
    TERMINAL_RTI,
    TERMINAL_SOLVER_FAILURE,
    integrate_qian_research_trajectory,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import (
    TERMINAL_GROUND_BEFORE_SRTI,
    TERMINAL_MAX_SEGMENTS,
    TERMINAL_MAX_TIME as SANGER_TERMINAL_MAX_TIME,
    TERMINAL_SOLVER_FAILURE as SANGER_TERMINAL_SOLVER_FAILURE,
    TERMINAL_SRTI,
    integrate_sanger_hybrid,
)
from hyptraj.simulation.trajectory import integrate_qian_glide

DATA_DIR = Path(__file__).resolve().parent / "data"
REFERENCE = json.loads(
    (DATA_DIR / "qian_sanger_comparison_v1.json").read_text(encoding="utf-8")
)
REF_PV = REFERENCE["production_values"]

ANCHOR_CAPTURE_TIME_S = REF_PV["qian_capture_time"]
ANCHOR_RTI_TIME_S = REF_PV["qian_terminal_time"]
ANCHOR_RTI_RANGE_M = REF_PV["qian_terminal_range"]


@pytest.fixture(scope="module")
def base():
    return (
        EnvironmentParams(),
        VehicleParams(),
        InitialCondition(
            altitude=100_000.0,
            velocity=7_000.0,
            flight_path_angle_deg=-5.0,
            range_angle=0.0,
        ),
        ConstantKControl(3.0),
    )


def _never_event():
    """A frozen-style event that never triggers (constant positive value)."""

    def ev(t, state, *args):
        return 1.0

    ev.terminal = True
    ev.direction = +1
    return ev


# ---------------------------------------------------------------------------
# A. baseline Qian -> QIAN_RTI
# ---------------------------------------------------------------------------
def test_baseline_qian_rti(base):
    env, veh, ini, ctl = base
    traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.terminal_kind == TERMINAL_RTI
    assert traj.success
    assert traj.mode_sequence == (ENTRY_CAPTURE, QEG_GLIDE)
    assert traj.capture_event is not None
    assert traj.rti_event is not None
    assert traj.ground_event is None
    assert classify_qian_regime(traj) == QIAN_REGIME_RTI


# ---------------------------------------------------------------------------
# B / C. baseline exact capture / RTI state consistent with Phase E
# ---------------------------------------------------------------------------
def test_baseline_capture_state_matches_phase_e(base):
    env, veh, ini, ctl = base
    traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.capture_event.time_s == pytest.approx(
        ANCHOR_CAPTURE_TIME_S, rel=1e-9
    )


def test_baseline_rti_state_matches_phase_e(base):
    env, veh, ini, ctl = base
    traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.rti_event.time_s == pytest.approx(ANCHOR_RTI_TIME_S, rel=1e-9)
    range_rti = env.earth_radius * traj.terminal_state[1]
    assert range_rti == pytest.approx(ANCHOR_RTI_RANGE_M, rel=1e-9)


# ---------------------------------------------------------------------------
# D. historical integrate_qian_glide unchanged (same production config)
# ---------------------------------------------------------------------------
def test_historical_integrate_qian_glide_unchanged(base):
    env, veh, ini, ctl = base
    hist = integrate_qian_glide(
        env, veh, ini, ctl, solver=PRODUCTION_SOLVER_CONFIG
    )
    traj = integrate_qian_research_trajectory(env, veh, ini, ctl)

    hist_cap = hist.events["capture_event"]
    hist_rti = hist.events["research_terminal_interface"]
    assert traj.capture_event.time_s == pytest.approx(
        hist_cap["time_s"], rel=1e-9
    )
    assert np.allclose(
        traj.capture_event.state, hist_cap["state"], rtol=1e-9, atol=0.0
    )
    assert traj.rti_event.time_s == pytest.approx(
        hist_rti["time_s"], rel=1e-9
    )
    assert np.allclose(
        traj.terminal_state, hist_rti["state"], rtol=1e-9, atol=0.0
    )


# ---------------------------------------------------------------------------
# E. ground-before-capture classification path (real dynamics, capture disabled)
# ---------------------------------------------------------------------------
def test_ground_before_capture_classification(base):
    env, veh, ini, ctl = base
    with mock.patch(
        "hyptraj.simulation.qian_research_trajectory.make_capture_event",
        return_value=_never_event(),
    ):
        traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.terminal_kind == TERMINAL_GROUND_BEFORE_CAPTURE
    assert not traj.success
    assert traj.ground_event is not None
    assert traj.capture_event is None
    assert traj.mode_sequence == (ENTRY_CAPTURE,)
    assert classify_qian_regime(traj) == QIAN_REGIME_GROUND_BEFORE_CAPTURE


# ---------------------------------------------------------------------------
# F. ground-after-capture-before-RTI classification path
# ---------------------------------------------------------------------------
def test_ground_after_capture_before_rti_classification(base):
    env, veh, ini, ctl = base
    with mock.patch(
        "hyptraj.simulation.qian_research_trajectory.make_qeg_end_event",
        return_value=_never_event(),
    ):
        traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.terminal_kind == TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI
    assert not traj.success
    assert traj.capture_event is not None
    assert traj.rti_event is None
    assert traj.ground_event is not None
    assert traj.mode_sequence == (ENTRY_CAPTURE, QEG_GLIDE)
    assert (
        classify_qian_regime(traj)
        == QIAN_REGIME_GROUND_AFTER_CAPTURE_BEFORE_RTI
    )


# ---------------------------------------------------------------------------
# G. max-time -> CENSORED (horizon truncation, no event)
# ---------------------------------------------------------------------------
def test_max_time_censored(base):
    env, veh, ini, ctl = base
    traj = integrate_qian_research_trajectory(
        env, veh, ini, ctl, max_time=50.0
    )
    assert traj.terminal_kind == TERMINAL_MAX_TIME
    assert not traj.success
    assert classify_qian_regime(traj) == QIAN_REGIME_CENSORED
    assert traj.terminal_time == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# H. solver failure -> NUMERICAL_FAILURE (mocked solver outcome)
# ---------------------------------------------------------------------------
def _fake_failed_solution(message="fake solver failure"):
    return SimpleNamespace(
        success=False,
        message=message,
        t=np.array([0.0, 1.0]),
        y=np.zeros((4, 2)),
        t_events=[np.array([]), np.array([])],
        sol=None,
        nfev=0,
    )


def test_solver_failure_classification(base):
    env, veh, ini, ctl = base
    with mock.patch(
        "hyptraj.simulation.qian_research_trajectory.solve_ivp",
        return_value=_fake_failed_solution(),
    ):
        traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.terminal_kind == TERMINAL_SOLVER_FAILURE
    assert not traj.success
    assert classify_qian_regime(traj) == QIAN_REGIME_NUMERICAL_FAILURE


# ---------------------------------------------------------------------------
# I. censored != numerical failure
# ---------------------------------------------------------------------------
def test_censored_and_failure_are_distinct(base):
    env, veh, ini, ctl = base
    censored = integrate_qian_research_trajectory(
        env, veh, ini, ctl, max_time=50.0
    )
    with mock.patch(
        "hyptraj.simulation.qian_research_trajectory.solve_ivp",
        return_value=_fake_failed_solution(),
    ):
        failed = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert censored.terminal_kind == TERMINAL_MAX_TIME
    assert failed.terminal_kind == TERMINAL_SOLVER_FAILURE
    assert censored.terminal_kind != failed.terminal_kind
    assert classify_qian_regime(censored) == QIAN_REGIME_CENSORED
    assert classify_qian_regime(failed) == QIAN_REGIME_NUMERICAL_FAILURE
    assert QIAN_REGIME_CENSORED != QIAN_REGIME_NUMERICAL_FAILURE


# ---------------------------------------------------------------------------
# J. classifier is a pure mapping (never parses message / exception text)
# ---------------------------------------------------------------------------
def test_classifier_pure_mapping_no_message_parsing():
    assert classify_qian_regime(TERMINAL_RTI) == QIAN_REGIME_RTI
    assert (
        classify_qian_regime(TERMINAL_GROUND_BEFORE_CAPTURE)
        == QIAN_REGIME_GROUND_BEFORE_CAPTURE
    )
    assert (
        classify_qian_regime(TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI)
        == QIAN_REGIME_GROUND_AFTER_CAPTURE_BEFORE_RTI
    )
    assert classify_qian_regime(TERMINAL_MAX_TIME) == QIAN_REGIME_CENSORED
    assert (
        classify_qian_regime(TERMINAL_SOLVER_FAILURE)
        == QIAN_REGIME_NUMERICAL_FAILURE
    )
    # Boundary-ambiguous terminal (F0.1 tie policy) has its own regime.
    assert (
        classify_qian_regime(TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT)
        == QIAN_REGIME_BOUNDARY_AMBIGUOUS
    )
    # Unknown kinds raise (programming error), never silently map to failure.
    with pytest.raises(KeyError):
        classify_qian_regime("UNKNOWN_KIND")


def test_sanger_classifier_pure_mapping():
    assert classify_sanger_regime(
        SimpleNamespace(terminal_kind=TERMINAL_SRTI), skip_count=2
    ) == "SRTI_N2"
    assert classify_sanger_regime(
        SimpleNamespace(terminal_kind=TERMINAL_GROUND_BEFORE_SRTI)
    ) == "GROUND_BEFORE_SRTI"
    assert classify_sanger_regime(
        SimpleNamespace(terminal_kind=SANGER_TERMINAL_MAX_TIME)
    ) == "CENSORED"
    assert classify_sanger_regime(
        SimpleNamespace(terminal_kind=TERMINAL_MAX_SEGMENTS)
    ) == "CENSORED"
    assert classify_sanger_regime(
        SimpleNamespace(terminal_kind=SANGER_TERMINAL_SOLVER_FAILURE)
    ) == "NUMERICAL_FAILURE"
    # SRTI without the frozen skip_count is a caller error.
    with pytest.raises(ValueError):
        classify_sanger_regime(SimpleNamespace(terminal_kind=TERMINAL_SRTI))


# ---------------------------------------------------------------------------
# Simultaneous-event tie policy (F0.1 §10)
# ---------------------------------------------------------------------------
def test_ambiguous_simultaneous_event_classification(base):
    env, veh, ini, ctl = base
    # Stage-0 fake: capture and ground roots within the tie tolerance.
    fake = SimpleNamespace(
        success=True,
        t_events=[np.array([100.0]), np.array([100.0 + 1e-9])],
        t=np.array([0.0, 100.0]),
        y=np.zeros((4, 2)),
        sol=lambda t: np.zeros((4, 1)),
        nfev=0,
    )
    with mock.patch(
        "hyptraj.simulation.qian_research_trajectory.solve_ivp",
        return_value=fake,
    ):
        traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.terminal_kind == TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT
    assert not traj.success
    assert classify_qian_regime(traj) == QIAN_REGIME_BOUNDARY_AMBIGUOUS


# ---------------------------------------------------------------------------
# K. Sanger baseline -> SRTI_N2 (thin classifier, frozen integrator)
# ---------------------------------------------------------------------------
def test_sanger_baseline_srti_n2(base):
    env, veh, ini, ctl = base
    traj = integrate_sanger_hybrid(env, veh, ini, ctl)
    metrics = analyze_sanger_trajectory(traj, env)
    assert traj.terminal_kind == TERMINAL_SRTI
    assert metrics.skip_count == 2
    assert classify_sanger_regime(traj, metrics.skip_count) == "SRTI_N2"


# ---------------------------------------------------------------------------
# INVALID_INPUT: ValueError propagates (sweep layer classifies it)
# ---------------------------------------------------------------------------
def test_invalid_input_propagates(base):
    env, veh, ini, _ctl = base
    with pytest.raises(ValueError, match="K must be positive"):
        ConstantKControl(0.0)
