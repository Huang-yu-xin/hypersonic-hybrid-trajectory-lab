"""Regression test for the APPROVED Qian continuous-glide baseline.

Dual-endpoint architecture (Phase B.5, DECISION: FREEZE-DUAL-ENDPOINT-QIAN):

    ENTRY_CAPTURE -> (gamma=0, +1) -> QEG_GLIDE -> (u_L* = 1, +1)
        -> RESEARCH TERMINAL INTERFACE -> GROUND_CONTINUATION (u_L=1) -> h=0

Frozen numerical values were produced by the human-confirmed production
run (DOP853, rtol=1e-8, component-scaled atol, max_step=10 s; ICs h0=100 km,
v0=7000 m/s, gamma0=-5 deg, theta0=0, K=3.0) and match the Phase B.5-B1
exploratory results exactly.  Tolerance rtol=1e-4 leaves headroom over the
solver convergence level while catching any genuine regression.

The problem-statement Table-2 ranges remain EXTERNAL comparison values only
and are not used as pass criteria here.
"""

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation import integrate_qian_glide, run_sanity_checks
from hyptraj.modes import ENTRY_CAPTURE, GROUND_CONTINUATION, QEG_GLIDE

# Frozen numerical values (human-confirmed).
REF_T_CAPTURE_S = 93.42878532241744
REF_H_CAPTURE_M = 46040.885721446946
REF_V_CAPTURE_MPS = 6810.795567490336
REF_T_RTI_S = 723.0379655300067
REF_H_RTI_M = 46040.88572144508
REF_V_RTI_MPS = 3192.533183816297
REF_R_RTI_KM = 3490.6983377576657
REF_T_GROUND_S = 2017.9599016252153
REF_R_GROUND_KM = 5363.623047671502
REF_V_GROUND_MPS = 159.92237966934928

RTOL = 1e-4


def _run():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    return integrate_qian_glide(env, vehicle, initial, control)


def test_all_three_modes_present_and_ordered():
    result = _run()

    modes = np.asarray(result.mode)
    assert modes[0] == ENTRY_CAPTURE
    assert modes[-1] == GROUND_CONTINUATION
    assert set(modes) == {ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION}
    # ordered: ENTRY_CAPTURE -> QEG_GLIDE -> GROUND_CONTINUATION
    assert np.all(np.diff(np.where(modes == QEG_GLIDE)[0]) == 1)


def test_capture_event_invariants():
    result = _run()

    cap = result.events["capture_event"]
    assert cap["g_capture"] == "gamma"
    assert cap["direction"] == 1
    assert cap["terminal"] is True
    assert cap["hybrid_switch"] is True


def test_research_terminal_interface_metadata():
    result = _run()

    assert result.metadata["research_terminal_reason"] == "qeg_feasibility_loss"
    assert result.metadata["qeg_feasibility_condition"] == "u_L_star <= 1"
    assert result.metadata["capture_event_is_hybrid_switch"] is True
    rts = result.metadata["research_terminal_state"]
    assert rts["u_L_RTI"] == pytest.approx(1.0, abs=1e-9)
    assert rts["L_RTI"] == pytest.approx(rts["L_req_RTI"], rel=1e-6)


def test_no_post_initial_atmospheric_exit():
    result = _run()

    h = result.derived["altitude_m"]
    assert np.all(h[1:] <= 100_000.0 + 1e-3)


def test_control_bounds_and_semantics():
    result = _run()

    u = result.control_history["u_L"]
    assert np.all(u >= 0.0) and np.all(u <= 1.0)
    # K_aero stays the aerodynamic L/D = 3; K_eff = K_aero * u_L
    assert np.allclose(result.control_history["K_aero"], 3.0)
    assert np.allclose(result.control_history["K_eff"], 3.0 * u)
    # u_L = 1 on ENTRY_CAPTURE and GROUND_CONTINUATION
    modes = np.asarray(result.mode)
    assert np.all(u[modes == ENTRY_CAPTURE] == 1.0)
    assert np.all(u[modes == GROUND_CONTINUATION] == 1.0)


def test_state_continuity_and_finiteness():
    result = _run()

    assert np.all(np.isfinite(result.state))
    assert all(np.all(np.isfinite(v)) for v in result.derived.values())


def test_ground_event_and_sanity():
    result = _run()

    assert result.events["ground_detected"] is True
    assert result.metrics["ground_event_altitude_residual_m"] < 1e-3
    sanity = run_sanity_checks(result)
    assert all(sanity.values()), sanity


def test_capture_regression():
    result = _run()

    assert result.metrics["qeg_capture_time_s"] == pytest.approx(
        REF_T_CAPTURE_S, rel=RTOL)
    cap = result.events["capture_event"]["state"]
    assert cap[0] - 6_371_000.0 == pytest.approx(REF_H_CAPTURE_M, rel=RTOL)
    assert cap[2] == pytest.approx(REF_V_CAPTURE_MPS, rel=RTOL)


def test_rti_regression():
    result = _run()

    m = result.metrics
    assert m["research_terminal_time_s"] == pytest.approx(REF_T_RTI_S, rel=RTOL)
    assert m["research_terminal_altitude_km"] * 1000.0 == pytest.approx(
        REF_H_RTI_M, rel=RTOL)
    assert m["research_terminal_velocity_mps"] == pytest.approx(
        REF_V_RTI_MPS, rel=RTOL)
    assert m["research_terminal_range_km"] == pytest.approx(
        REF_R_RTI_KM, rel=RTOL)


def test_ground_continuation_regression():
    result = _run()

    m = result.metrics
    assert m["ground_time_s"] == pytest.approx(REF_T_GROUND_S, rel=RTOL)
    assert m["ground_range_km"] == pytest.approx(REF_R_GROUND_KM, rel=RTOL)
    assert m["ground_velocity_mps"] == pytest.approx(REF_V_GROUND_MPS, rel=RTOL)


def test_research_and_ground_metric_schema():
    result = _run()

    research_keys = {
        "research_terminal_time_s", "research_terminal_range_km",
        "research_terminal_altitude_km", "research_terminal_velocity_mps",
        "research_terminal_gamma_deg", "research_terminal_energy_jpkg",
    }
    ground_keys = {
        "ground_time_s", "ground_range_km",
        "ground_velocity_mps", "ground_gamma_deg",
    }
    assert research_keys <= set(result.metrics)
    assert ground_keys <= set(result.metrics)
    for k in ("qeg_capture_time_s", "qeg_duration_s", "qeg_range_gain_km",
              "max_bank_angle_deg", "median_bank_angle_deg"):
        assert k in result.metrics
