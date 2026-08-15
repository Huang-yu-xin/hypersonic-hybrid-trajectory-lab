"""E0.1 tests: opt-in dense-output access amendment.

The frozen integrators already compute solver dense interpolants
(``dense_output=True``); the E0.1 collector hook exposes them without
re-integrating, re-fitting, or changing any default behavior.

Coverage (E0.1 acceptance):

    A  Qian default behavior unchanged
    B  Sanger default behavior unchanged
    C  Qian dense stages captured
    D  Sanger dense segments captured
    E  Qian dense endpoints == exact stage/event states
    F  Sanger dense endpoints == exact switching/event states
    G  dense access does not mutate result
    H  dense access does not modify solver config
    I  no extra integration calls
    J  dense runtime object not in canonical serialization
"""

import dataclasses
import json
from unittest import mock

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes import ENTRY_CAPTURE, GROUND_CONTINUATION, QEG_GLIDE
from hyptraj.modes.sanger_hybrid import SANGER_ATM, SANGER_VAC
from hyptraj.simulation import (
    DEFAULT_SOLVER_CONFIG,
    integrate_qian_glide,
)
from hyptraj.simulation.dense_output import (
    DenseOutputCollector,
    DenseSolutionSegment,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import (
    SRTI,
    SYNTHETIC_INITIAL_ENTRY,
    integrate_sanger_hybrid,
)

# Frozen Qian regression values (same human-confirmed production run as
# tests/test_models/test_qian_continuous_glide.py).
REF_T_CAPTURE_S = 93.42878532241744
REF_T_RTI_S = 723.0379655300067
REF_R_RTI_KM = 3490.6983377576657
REF_T_GROUND_S = 2017.9599016252153

RTOL = 1e-4

# Tight consistency tolerance at solver-precision level.
_STATE_RTOL = 1e-9
_STATE_ATOL = 1e-10


def _inputs():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    return env, vehicle, initial, control


def _qian_state0(env, initial):
    return np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ],
        dtype=float,
    )


def _assert_results_exactly_equal(a, b):
    """Bit-level equality of two canonical results (same integration)."""
    assert np.array_equal(a.time, b.time)
    assert np.array_equal(a.state, b.state)
    assert set(a.derived) == set(b.derived)
    for key in a.derived:
        assert np.array_equal(a.derived[key], b.derived[key])
    assert a.metrics == b.metrics
    assert a.events == b.events
    assert a.metadata == b.metadata
    assert np.array_equal(a.mode, b.mode)
    assert a.control_history.keys() == b.control_history.keys()
    for key in a.control_history:
        assert np.array_equal(a.control_history[key], b.control_history[key])


# ---------------------------------------------------------------------------
# A. Qian default behavior unchanged
# ---------------------------------------------------------------------------
def test_a_qian_default_behavior_unchanged():
    env, vehicle, initial, control = _inputs()
    result = integrate_qian_glide(env, vehicle, initial, control)

    # Frozen regression values (historical DEFAULT_SOLVER_CONFIG path).
    assert result.metrics["qeg_capture_time_s"] == pytest.approx(
        REF_T_CAPTURE_S, rel=RTOL
    )
    assert result.metrics["research_terminal_time_s"] == pytest.approx(
        REF_T_RTI_S, rel=RTOL
    )
    assert result.metrics["research_terminal_range_km"] == pytest.approx(
        REF_R_RTI_KM, rel=RTOL
    )
    assert result.metrics["ground_time_s"] == pytest.approx(
        REF_T_GROUND_S, rel=RTOL
    )
    assert result.metadata["research_terminal_reason"] == "qeg_feasibility_loss"
    assert set(result.events) >= {
        "capture_event",
        "research_terminal_interface",
        "ground_detected",
    }
    # Passing the default explicitly is identical to omitting it.
    result_default = integrate_qian_glide(
        env, vehicle, initial, control, solver=DEFAULT_SOLVER_CONFIG
    )
    _assert_results_exactly_equal(result, result_default)


# ---------------------------------------------------------------------------
# B. Sanger default behavior unchanged
# ---------------------------------------------------------------------------
def test_b_sanger_default_behavior_unchanged():
    env, vehicle, initial, control = _inputs()
    traj = integrate_sanger_hybrid(env, vehicle, initial, control)
    metrics = analyze_sanger_trajectory(traj, env)

    assert traj.terminal_kind == SRTI
    assert traj.success is True
    assert metrics.skip_count == 2
    assert [s.mode for s in traj.segments] == [
        SANGER_ATM, SANGER_VAC, SANGER_ATM, SANGER_VAC, SANGER_ATM,
    ]
    assert traj.events[0].kind == SYNTHETIC_INITIAL_ENTRY
    assert traj.events[-1].kind == SRTI


# ---------------------------------------------------------------------------
# C. Qian dense stages captured
# ---------------------------------------------------------------------------
def test_c_qian_dense_stages_captured():
    env, vehicle, initial, control = _inputs()
    collector = DenseOutputCollector()
    result = integrate_qian_glide(
        env, vehicle, initial, control,
        solver=PRODUCTION_SOLVER_CONFIG,
        dense_output_collector=collector,
    )

    assert len(collector) == 3
    segments = collector.segments
    assert [s.index for s in segments] == [0, 1, 2]
    assert [s.name for s in segments] == [
        ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION,
    ]
    assert [s.mode for s in segments] == [
        ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION,
    ]

    t_capture = result.events["capture_event"]["time_s"]
    t_rti = result.events["research_terminal_interface"]["time_s"]
    t_ground = result.events["ground_time_s"]
    assert segments[0].t_start == pytest.approx(0.0)
    assert segments[0].t_end == pytest.approx(t_capture)
    assert segments[1].t_start == pytest.approx(t_capture)
    assert segments[1].t_end == pytest.approx(t_rti)
    assert segments[2].t_start == pytest.approx(t_rti)
    assert segments[2].t_end == pytest.approx(t_ground)

    # Dense callable evaluates to shape (4,) scalar / (4, N) array.
    assert segments[1].solution(t_rti).shape == (4,)
    assert segments[1].solution(
        np.linspace(0.0, t_rti, 5)
    ).shape == (4, 5)


# ---------------------------------------------------------------------------
# D. Sanger dense segments captured
# ---------------------------------------------------------------------------
def test_d_sanger_dense_segments_captured():
    env, vehicle, initial, control = _inputs()
    collector = DenseOutputCollector()
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control,
        dense_output_collector=collector,
    )

    assert len(collector) == len(traj.segments)
    for dense, seg in zip(collector.segments, traj.segments):
        assert dense.index == seg.index
        assert dense.name == seg.mode
        assert dense.mode == seg.mode
        assert dense.t_start == pytest.approx(seg.t_start)
        assert dense.t_end == pytest.approx(seg.t_end)
        assert dense.solution(seg.t_end).shape == (4,)


# ---------------------------------------------------------------------------
# E. Qian dense endpoints == exact stage/event states
# ---------------------------------------------------------------------------
def test_e_qian_dense_endpoints_match_exact_states():
    env, vehicle, initial, control = _inputs()
    collector = DenseOutputCollector()
    result = integrate_qian_glide(
        env, vehicle, initial, control,
        solver=PRODUCTION_SOLVER_CONFIG,
        dense_output_collector=collector,
    )
    segments = collector.segments

    # ENTRY_CAPTURE: dense(t=0) == initial state.
    assert np.allclose(
        segments[0].solution(0.0),
        _qian_state0(env, initial),
        rtol=_STATE_RTOL, atol=_STATE_ATOL,
    )
    # ENTRY_CAPTURE: dense(t_capture) == exact capture event state.
    cap = result.events["capture_event"]
    assert np.allclose(
        segments[0].solution(cap["time_s"]), cap["state"],
        rtol=_STATE_RTOL, atol=_STATE_ATOL,
    )
    # QEG_GLIDE: dense(t_capture) == same capture state (continuity).
    assert np.allclose(
        segments[1].solution(cap["time_s"]), cap["state"],
        rtol=_STATE_RTOL, atol=_STATE_ATOL,
    )
    # QEG_GLIDE: dense(t_rti) == exact RTI state.
    rti = result.events["research_terminal_interface"]
    assert np.allclose(
        segments[1].solution(rti["time_s"]), rti["state"],
        rtol=_STATE_RTOL, atol=_STATE_ATOL,
    )
    # GROUND_CONTINUATION: dense(t_ground) reaches h = 0 within solver
    # event-localization precision.
    ground_alt = float(segments[2].solution(result.events["ground_time_s"])[0]
                       - env.earth_radius)
    assert abs(ground_alt) < 1e-3


# ---------------------------------------------------------------------------
# F. Sanger dense endpoints == exact switching/event states
# ---------------------------------------------------------------------------
def test_f_sanger_dense_endpoints_match_exact_states():
    env, vehicle, initial, control = _inputs()
    collector = DenseOutputCollector()
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control,
        dense_output_collector=collector,
    )

    # Every segment boundary equals the stored exact event state.
    for dense, seg in zip(collector.segments, traj.segments):
        assert np.allclose(
            dense.solution(seg.t_start), seg.state_start,
            rtol=_STATE_RTOL, atol=_STATE_ATOL,
        )
        assert np.allclose(
            dense.solution(seg.t_end), seg.state_end,
            rtol=_STATE_RTOL, atol=_STATE_ATOL,
        )

    # Terminal pass: dense(t_srti) == exact SRTI state.
    srti = [e for e in traj.events if e.kind == SRTI][0]
    assert np.allclose(
        collector.segments[-1].solution(srti.time), srti.state,
        rtol=_STATE_RTOL, atol=_STATE_ATOL,
    )
    assert np.allclose(
        collector.segments[-1].solution(srti.time), traj.terminal_state,
        rtol=_STATE_RTOL, atol=_STATE_ATOL,
    )

    # Atmosphere exit / entry switching states agree across the two
    # adjacent segments (x_minus = x_plus).
    for dense_prev, dense_next in zip(collector.segments[:-1],
                                      collector.segments[1:]):
        t_switch = dense_prev.t_end
        assert np.allclose(
            dense_prev.solution(t_switch), dense_next.solution(t_switch),
            rtol=_STATE_RTOL, atol=_STATE_ATOL,
        )


# ---------------------------------------------------------------------------
# G. dense access does not mutate result
# ---------------------------------------------------------------------------
def test_g_dense_access_does_not_mutate_result():
    env, vehicle, initial, control = _inputs()

    base = integrate_qian_glide(
        env, vehicle, initial, control, solver=PRODUCTION_SOLVER_CONFIG,
    )
    collector = DenseOutputCollector()
    observed = integrate_qian_glide(
        env, vehicle, initial, control, solver=PRODUCTION_SOLVER_CONFIG,
        dense_output_collector=collector,
    )
    _assert_results_exactly_equal(base, observed)

    base_traj = integrate_sanger_hybrid(env, vehicle, initial, control)
    s_collector = DenseOutputCollector()
    obs_traj = integrate_sanger_hybrid(
        env, vehicle, initial, control, dense_output_collector=s_collector,
    )
    assert [s.mode for s in base_traj.segments] == [
        s.mode for s in obs_traj.segments
    ]
    for a, b in zip(base_traj.segments, obs_traj.segments):
        assert np.array_equal(a.t, b.t)
        assert np.array_equal(a.y, b.y)
    assert base_traj.terminal_time == obs_traj.terminal_time
    assert np.array_equal(base_traj.terminal_state, obs_traj.terminal_state)
    assert len(base_traj.events) == len(obs_traj.events)
    for a, b in zip(base_traj.events, obs_traj.events):
        assert a.kind == b.kind and a.time == b.time
        assert np.array_equal(a.state, b.state)


# ---------------------------------------------------------------------------
# H. dense access does not modify solver config
# ---------------------------------------------------------------------------
def _assert_config_unchanged(before: dict, after: dict) -> None:
    """Exact config comparison (atol is an array, not scalar equality)."""
    assert after.keys() == before.keys()
    for key in before:
        if isinstance(before[key], np.ndarray):
            assert np.array_equal(after[key], before[key])
        else:
            assert after[key] == before[key]


def test_h_dense_access_does_not_modify_solver_config():
    env, vehicle, initial, control = _inputs()

    prod_before = dataclasses.asdict(PRODUCTION_SOLVER_CONFIG)
    default_before = dataclasses.asdict(DEFAULT_SOLVER_CONFIG)

    integrate_qian_glide(
        env, vehicle, initial, control, solver=PRODUCTION_SOLVER_CONFIG,
        dense_output_collector=DenseOutputCollector(),
    )
    integrate_qian_glide(
        env, vehicle, initial, control,
        dense_output_collector=DenseOutputCollector(),
    )
    integrate_sanger_hybrid(
        env, vehicle, initial, control,
        dense_output_collector=DenseOutputCollector(),
    )

    _assert_config_unchanged(prod_before,
                             dataclasses.asdict(PRODUCTION_SOLVER_CONFIG))
    _assert_config_unchanged(default_before,
                             dataclasses.asdict(DEFAULT_SOLVER_CONFIG))


# ---------------------------------------------------------------------------
# I. no extra integration calls
# ---------------------------------------------------------------------------
def test_i_no_extra_integration_calls():
    env, vehicle, initial, control = _inputs()
    import hyptraj.simulation.sanger_trajectory as sanger_mod
    import hyptraj.simulation.trajectory as traj_mod

    def _count(module, fn):
        calls = [0]
        real = getattr(module, fn)

        def counting(*args, **kwargs):
            calls[0] += 1
            return real(*args, **kwargs)

        return calls, counting

    qian_calls, qian_counter = _count(traj_mod, "solve_ivp")
    with mock.patch.object(traj_mod, "solve_ivp", side_effect=qian_counter):
        integrate_qian_glide(env, vehicle, initial, control)
        assert qian_calls[0] == 3  # ENTRY_CAPTURE, QEG_GLIDE, GROUND
        integrate_qian_glide(
            env, vehicle, initial, control,
            dense_output_collector=DenseOutputCollector(),
        )
        assert qian_calls[0] == 6  # collector adds NO integration calls

    sanger_calls, sanger_counter = _count(sanger_mod, "solve_ivp")
    with mock.patch.object(sanger_mod, "solve_ivp",
                           side_effect=sanger_counter):
        traj = integrate_sanger_hybrid(env, vehicle, initial, control)
        n_segments = len(traj.segments)
        assert sanger_calls[0] == n_segments  # one call per segment
        integrate_sanger_hybrid(
            env, vehicle, initial, control,
            dense_output_collector=DenseOutputCollector(),
        )
        assert sanger_calls[0] == 2 * n_segments  # still one per segment


# ---------------------------------------------------------------------------
# J. dense runtime object not in canonical serialization
# ---------------------------------------------------------------------------
def test_j_dense_not_in_canonical_serialization():
    env, vehicle, initial, control = _inputs()

    # Result containers carry no dense field (frozen schemas untouched).
    result = integrate_qian_glide(
        env, vehicle, initial, control, solver=PRODUCTION_SOLVER_CONFIG,
        dense_output_collector=DenseOutputCollector(),
    )
    traj = integrate_sanger_hybrid(
        env, vehicle, initial, control,
        dense_output_collector=DenseOutputCollector(),
    )
    assert "dense" not in [f.name for f in dataclasses.fields(result)]
    assert "dense" not in [f.name for f in dataclasses.fields(traj)]
    assert "dense" not in [f.name for f in dataclasses.fields(traj.segments[0])]

    # Canonical results serialize cleanly to JSON (plain data only).
    json.dumps(dataclasses.asdict(result), default=lambda o: o.tolist())
    json.dumps(dataclasses.asdict(traj), default=lambda o: o.tolist())

    # DenseSolutionSegment is runtime-only: its dense callable can never
    # be serialized into a canonical artifact.
    collector = DenseOutputCollector()
    integrate_qian_glide(
        env, vehicle, initial, control, solver=PRODUCTION_SOLVER_CONFIG,
        dense_output_collector=collector,
    )
    with pytest.raises(TypeError):
        json.dumps({"solution": collector.segments[0].solution})
