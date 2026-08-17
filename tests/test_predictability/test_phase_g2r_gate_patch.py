"""Phase-G2R validation-gate corrective patch tests (G2R §7-§10).

Covers the two corrective-patch contracts:

Issue 1 -- both-side gate: a centered-FD column is VALID iff BOTH the
``+epsilon`` and ``-epsilon`` trajectories are VALID_SMOOTH_FLOW; either
side invalid rejects the column (never entered into the STM error
metric), and the per-side classifications are always recorded.

Issue 2 -- MODE_WINDOW_INVALID is fully enforced: the gate observes the
FROZEN true-switch event surfaces (Qian capture, Sanger ATM exit / VAC
entry) and rejects any perturbation whose trajectory crosses one inside
the window; diagnostic events (Sanger pullout / VAC apogee) never
invalidate.  The gate is a validation observer only -- no hybrid
propagation, no reset, no RHS switching.
"""

import json
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability import perturbation as pert
from hyptraj.predictability.perturbation import (
    FD_BASE_STEP,
    FlowValidationClass,
    column_pair_class,
    epsilon_sweep_fd,
    gate_perturbed_trajectory,
    mode_window_detection_event,
)
from hyptraj.predictability.stm import (
    stm_production_like_config,
    stm_strict_reference_config,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g2_continuous_stm_v1.json").read_text(
        encoding="utf-8"
    )
)

K = 3.0
VALID = FlowValidationClass.VALID_SMOOTH_FLOW
WINVALID = FlowValidationClass.MODE_WINDOW_INVALID
AS_CHANGED = FlowValidationClass.ACTIVE_SET_CHANGED


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams(), InitialCondition()


def _qian_state_at(env, veh, ini, t, seg_index):
    """Exact frozen dense-output state of a Qian segment at time ``t``."""
    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )

    col = DenseOutputCollector()
    integrate_qian_research_trajectory(
        env, veh, ini, ConstantKControl(K), dense_output_collector=col
    )
    return np.asarray(col.segments[seg_index].solution(t), dtype=float)


def _sanger_state_at(env, veh, ini, seg_index, t):
    """Exact frozen dense-output state of a Sanger segment at time ``t``."""
    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    col = DenseOutputCollector()
    integrate_sanger_research_trajectory(
        env, veh, ini, ConstantKControl(K), dense_output_collector=col
    )
    for dseg in col.segments:
        if dseg.index == seg_index:
            return np.asarray(dseg.solution(t), dtype=float)
    raise ValueError(f"no segment {seg_index}")


# ---------------------------------------------------------------------------
# Issue 1: both-side gate / pair classification
# ---------------------------------------------------------------------------
def test_column_pair_class_logic():
    assert column_pair_class(VALID, VALID) == VALID
    assert column_pair_class(VALID, WINVALID) == FlowValidationClass.PAIR_INVALID
    assert column_pair_class(WINVALID, VALID) == FlowValidationClass.PAIR_INVALID
    assert column_pair_class(AS_CHANGED, VALID) == FlowValidationClass.PAIR_INVALID
    assert column_pair_class(WINVALID, AS_CHANGED) == FlowValidationClass.PAIR_INVALID


def test_sweep_gates_both_sides_valid(base, monkeypatch):
    """Both sides VALID_SMOOTH_FLOW -> column accepted (n_valid == 4)."""
    env, veh, ini = base
    x0 = _qian_state_at(env, veh, ini, 60.0, 0)  # entry_capture interior
    calls = []

    def fake_gate(mode, x0g, t_span, env, veh, k, solver):
        calls.append(np.asarray(x0g).copy())
        return VALID

    monkeypatch.setattr(pert, "gate_perturbed_trajectory", fake_gate)
    phi = np.zeros((4, 4))
    sweep = epsilon_sweep_fd(
        "entry_capture", x0, (60.0, 80.0), env, veh, K,
        stm_production_like_config(), phi_stm=phi,
        base_step=FD_BASE_STEP, multipliers=(1e-2,),
    )
    s = sweep["mult_0.01"]
    assert s["n_valid_columns"] == 4
    assert s["classification"] == ["VALID_SMOOTH_FLOW"] * 4
    assert s["classification_plus"] == ["VALID_SMOOTH_FLOW"] * 4
    assert s["classification_minus"] == ["VALID_SMOOTH_FLOW"] * 4
    # Gate called for BOTH + and - of every column: 2 * 4 calls.
    assert len(calls) == 8


def test_sweep_rejects_plus_invalid_minus_valid(base, monkeypatch):
    """plus=MODE_WINDOW_INVALID, minus=VALID -> column rejected."""
    env, veh, ini = base
    x0 = _qian_state_at(env, veh, ini, 60.0, 0)
    mult = 1e-2
    e0 = np.zeros(4)
    e0[0] = 1.0
    plus0 = x0 + FD_BASE_STEP[0] * mult * e0
    minus0 = x0 - FD_BASE_STEP[0] * mult * e0

    def fake_gate(mode, x0g, t_span, env, veh, k, solver):
        if np.allclose(np.asarray(x0g), plus0, rtol=0.0, atol=1e-9):
            return WINVALID
        return VALID

    monkeypatch.setattr(pert, "gate_perturbed_trajectory", fake_gate)
    phi = np.zeros((4, 4))
    sweep = epsilon_sweep_fd(
        "entry_capture", x0, (60.0, 80.0), env, veh, K,
        stm_production_like_config(), phi_stm=phi,
        base_step=FD_BASE_STEP, multipliers=(mult,),
    )
    s = sweep["mult_0.01"]
    assert s["classification_plus"][0] == "MODE_WINDOW_INVALID"
    assert s["classification_minus"][0] == "VALID_SMOOTH_FLOW"
    assert s["classification"][0] == "PAIR_INVALID"
    assert s["n_valid_columns"] == 3  # r column rejected only


def test_sweep_rejects_minus_invalid_plus_valid(base, monkeypatch):
    """plus=VALID, minus=MODE_WINDOW_INVALID -> column rejected (key regression)."""
    env, veh, ini = base
    x0 = _qian_state_at(env, veh, ini, 60.0, 0)
    mult = 1e-2
    e0 = np.zeros(4)
    e0[0] = 1.0
    plus0 = x0 + FD_BASE_STEP[0] * mult * e0
    minus0 = x0 - FD_BASE_STEP[0] * mult * e0

    def fake_gate(mode, x0g, t_span, env, veh, k, solver):
        if np.allclose(np.asarray(x0g), minus0, rtol=0.0, atol=1e-9):
            return WINVALID
        return VALID

    monkeypatch.setattr(pert, "gate_perturbed_trajectory", fake_gate)
    phi = np.zeros((4, 4))
    sweep = epsilon_sweep_fd(
        "entry_capture", x0, (60.0, 80.0), env, veh, K,
        stm_production_like_config(), phi_stm=phi,
        base_step=FD_BASE_STEP, multipliers=(mult,),
    )
    s = sweep["mult_0.01"]
    assert s["classification_plus"][0] == "VALID_SMOOTH_FLOW"
    assert s["classification_minus"][0] == "MODE_WINDOW_INVALID"
    assert s["classification"][0] == "PAIR_INVALID"
    assert s["n_valid_columns"] == 3  # r column rejected because MINUS invalid


def test_sweep_rejects_qeg_one_side_active_set(base, monkeypatch):
    """QEG: plus interior, minus ACTIVE_SET_CHANGED -> column rejected.

    The per-side record keeps the failing side and reason.
    """
    env, veh, ini = base
    mode = "qeg_interior"
    # Real interior QEG state (G2 window start).
    from hyptraj.predictability.jacobian import representative_continuous_states

    x0 = representative_continuous_states(
        mode, env, veh, ini, K, n_samples=1
    )[0]["state"]
    mult = 1e-2
    e0 = np.zeros(4)
    e0[0] = 1.0
    plus0 = x0 + FD_BASE_STEP[0] * mult * e0
    minus0 = x0 - FD_BASE_STEP[0] * mult * e0

    def fake_gate(mode, x0g, t_span, env, veh, k, solver):
        if np.allclose(np.asarray(x0g), minus0, rtol=0.0, atol=1e-9):
            return AS_CHANGED
        return VALID  # plus side (and all other columns) interior

    monkeypatch.setattr(pert, "gate_perturbed_trajectory", fake_gate)
    phi = np.zeros((4, 4))
    sweep = epsilon_sweep_fd(
        mode, x0, (187.87, 534.16), env, veh, K,
        stm_strict_reference_config(), phi_stm=phi,
        base_step=FD_BASE_STEP, multipliers=(mult,),
    )
    s = sweep["mult_0.01"]
    assert s["classification_plus"][0] == "VALID_SMOOTH_FLOW"
    assert s["classification_minus"][0] == "ACTIVE_SET_CHANGED"
    assert s["classification"][0] == "PAIR_INVALID"
    assert s["n_valid_columns"] == 3


# ---------------------------------------------------------------------------
# Issue 2: MODE_WINDOW_INVALID real detection (integration)
# ---------------------------------------------------------------------------
def test_entry_capture_crossing_detected(base):
    env, veh, ini = base
    x60 = _qian_state_at(env, veh, ini, 60.0, 0)
    cfg = stm_production_like_config()
    # capture onset at ~93.4 s in the reference; window (60,100) crosses it
    cls = gate_perturbed_trajectory("entry_capture", x60, (60.0, 100.0),
                                    env, veh, K, cfg)
    assert cls == WINVALID
    # window fully before capture stays valid
    cls2 = gate_perturbed_trajectory("entry_capture", x60, (60.0, 80.0),
                                     env, veh, K, cfg)
    assert cls2 == VALID


def test_sanger_atm_exit_crossing_detected(base):
    env, veh, ini = base
    x150 = _sanger_state_at(env, veh, ini, 0, 150.0)  # first ATM segment
    cfg = stm_production_like_config()
    # first atmosphere exit at ~202.96 s; window (150,210) crosses it
    cls = gate_perturbed_trajectory("sanger_atm", x150, (150.0, 210.0),
                                    env, veh, K, cfg)
    assert cls == WINVALID
    # window fully before exit stays valid
    cls2 = gate_perturbed_trajectory("sanger_atm", x150, (150.0, 190.0),
                                     env, veh, K, cfg)
    assert cls2 == VALID


def test_sanger_vac_entry_crossing_detected(base):
    env, veh, ini = base
    x400 = _sanger_state_at(env, veh, ini, 1, 400.0)  # first VAC segment
    cfg = stm_production_like_config()
    # atmosphere entry at ~484.64 s; window (400,500) crosses it
    cls = gate_perturbed_trajectory("sanger_vac", x400, (400.0, 500.0),
                                    env, veh, K, cfg)
    assert cls == WINVALID
    # window fully before entry stays valid
    cls2 = gate_perturbed_trajectory("sanger_vac", x400, (400.0, 460.0),
                                     env, veh, K, cfg)
    assert cls2 == VALID


def test_diagnostic_events_do_not_invalidate(base):
    """Sanger pullout (ATM) and VAC apogee are NOT true switches."""
    env, veh, ini = base
    cfg = stm_strict_reference_config()
    # QEG-none; use the G2 windows which provably contain the diagnostics:
    # ATM window (60.89, 172.52) contains the gamma=0 pullout;
    # VAC window (287.47, 442.39) contains the vacuum apogee (~343.8 s).
    from hyptraj.predictability.jacobian import representative_continuous_states

    x_atm = representative_continuous_states("sanger_atm", env, veh, ini, K,
                                             n_samples=1)[0]["state"]
    cls_atm = gate_perturbed_trajectory(
        "sanger_atm", x_atm, (60.8892, 172.5208), env, veh, K, cfg)
    assert cls_atm == VALID

    x_vac = representative_continuous_states("sanger_vac", env, veh, ini, K,
                                             n_samples=1)[0]["state"]
    cls_vac = gate_perturbed_trajectory(
        "sanger_vac", x_vac, (287.4670, 442.3893), env, veh, K, cfg)
    assert cls_vac == VALID


# ---------------------------------------------------------------------------
# Detection-helper contract
# ---------------------------------------------------------------------------
def test_mode_window_detection_event_contract():
    env = EnvironmentParams()
    cap = mode_window_detection_event("entry_capture", env)
    assert cap.direction == +1 and cap.terminal is True
    atm_exit = mode_window_detection_event("sanger_atm", env)
    assert atm_exit.direction == +1 and atm_exit.terminal is True
    vac_entry = mode_window_detection_event("sanger_vac", env)
    assert vac_entry.direction == -1 and vac_entry.terminal is True
    assert mode_window_detection_event("qeg_interior", env) is None
    with pytest.raises(ValueError):
        mode_window_detection_event("nope", env)


# ---------------------------------------------------------------------------
# Snapshot cross-media consistency (G2R §9)
# ---------------------------------------------------------------------------
def test_snapshot_per_side_fields_recorded():
    for mode in ("entry_capture", "qeg_interior", "sanger_atm", "sanger_vac"):
        rec = SNAPSHOT["per_mode"][mode]
        agree = rec["fd_reference_agreement"]
        for field in ("classification_plus", "classification_minus"):
            assert field in agree
            assert len(agree[field]) == 4
        assert agree["pair_valid"] is True
        assert set(agree["classification_plus"]) == {"VALID_SMOOTH_FLOW"}
        assert set(agree["classification_minus"]) == {"VALID_SMOOTH_FLOW"}
        # derived pair classification agrees
        assert agree["classification"] == ["VALID_SMOOTH_FLOW"] * 4
        # plateau sweep carries per-side fields too
        pl = rec["fd_plateau"]
        assert pl["classification_plus"] == ["VALID_SMOOTH_FLOW"] * 4
        assert pl["classification_minus"] == ["VALID_SMOOTH_FLOW"] * 4


def test_snapshot_g2r_issue_documented():
    assert SNAPSHOT["g2r"]["issue1_both_side_gate"].lower().startswith(
        "a centered-fd column is valid iff both"
    )
    assert "MODE_WINDOW_INVALID" in SNAPSHOT["g2r"]["issue2_mode_window_detection"]
    assert SNAPSHOT["g2r"]["per_side_fields"] == [
        "classification_plus", "classification_minus"]
    assert "PAIR_INVALID" in SNAPSHOT["validation_classes"]


def test_snapshot_qeg_perturbation_gate_both_sides():
    per = SNAPSHOT["per_mode"]["qeg_interior"]["qeg_perturbation_gate"]
    assert len(per) == 4
    for p in per:
        assert p["plus"] == "VALID_SMOOTH_FLOW"
        assert p["minus"] == "VALID_SMOOTH_FLOW"