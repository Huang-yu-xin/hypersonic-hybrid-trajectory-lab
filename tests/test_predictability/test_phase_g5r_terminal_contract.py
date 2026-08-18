"""Phase-G5R terminal sensitivity contract & RTI trim corrective tests.

G5R fixes three terminal-sensitivity infrastructure contracts (G5 PASS
WITH MINOR FIX -> G5R):

Issue 1 -- ``build_terminal_sensitivity`` now VERIFIES the actual frozen
``terminal_kind`` equals the expected research terminal (Qian ``RTI``,
Sanger ``srti``) before computing any eta / J / terminal-SVD
(``TerminalSensitivityEligibilityError``); invalid model strings are
rejected explicitly.

Issue 2 -- the terminal event-time algebra now has an exact-zero /
nonfinite transversality denominator guard (``NonTransverseTerminalError``);
only exact-zero / nonfinite are rejected -- a small FINITE denominator is
NEVER threshold-rejected here (G6 owns the near-grazing validity domain).

Issue 3 -- the Qian RTI strict-interior trim ``u_L* <= 1 - u_eps`` is
exposed (keyword-only ``qian_trim_u_eps``), validated ``0 < u_eps < 1``
finite, and backed by an explicit convergence audit
(``qian_rti_trim_audit``) demonstrating ``Phi(t_eps,0) -> Phi^-_RTI`` as
``u_eps -> 0`` below the G5 terminal-sensitivity error budget.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability import terminal_sensitivity as TS
from hyptraj.predictability.stm import stm_strict_reference_config
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g5_predictability_metrics_v1.json").read_text(
        encoding="utf-8"
    ))

K = 3.0
E = TS.TerminalSensitivityEligibilityError
NTE = TS.NonTransverseTerminalError


@pytest.fixture(scope="module")
def base():
    env = EnvironmentParams()
    veh = VehicleParams()
    ini = InitialCondition()
    x0 = np.array([env.earth_radius + ini.altitude, ini.range_angle,
                   ini.velocity, np.deg2rad(ini.flight_path_angle_deg)])
    return env, veh, x0


# ---------------------------------------------------------------------------
# 1. Terminal-kind eligibility contract (G5R §17)
# ---------------------------------------------------------------------------
def test_expected_terminals_accepted():
    TS.check_terminal_eligibility("qian", "RTI", 723.0)
    TS.check_terminal_eligibility("sanger", "srti", 1119.0)


@pytest.mark.parametrize("model,kind", [
    ("qian", "GROUND_BEFORE_CAPTURE"),
    ("qian", "GROUND_AFTER_CAPTURE_BEFORE_RTI"),
    ("qian", "MAX_TIME"),
    ("qian", "SOLVER_FAILURE"),
    ("qian", "AMBIGUOUS_SIMULTANEOUS_EVENT"),
    ("sanger", "ground_before_srti"),
    ("sanger", "max_time"),
    ("sanger", "max_segments"),
    ("sanger", "solver_failure"),
    ("sanger", "grazing_or_unresolved_event"),
])
def test_wrong_terminal_kind_rejected(model, kind):
    with pytest.raises(E):
        TS.check_terminal_eligibility(model, kind, 300.0)


def test_invalid_model_rejected():
    for bad in ("foo", "qain", "sanger2", ""):
        with pytest.raises(ValueError):
            TS.check_terminal_eligibility(bad, "RTI", 300.0)


def test_build_terminal_sensitivity_valid_terminals(base):
    env, veh, x0 = base
    res = REFERENCE_SOLVER_CONFIG
    stm = stm_strict_reference_config()
    ts_q = TS.build_terminal_sensitivity(
        "qian", x0, env, veh, K, research_solver=res, stm_solver=stm,
        scale_key="A")
    assert ts_q.terminal_kind == "RTI"
    ts_s = TS.build_terminal_sensitivity(
        "sanger", x0, env, veh, K, research_solver=res, stm_solver=stm,
        scale_key="A")
    assert ts_s.terminal_kind == "srti"


def test_build_terminal_sensitivity_invalid_model(base):
    env, veh, x0 = base
    with pytest.raises(ValueError):
        TS.build_terminal_sensitivity(
            "foo", x0, env, veh, K,
            research_solver=REFERENCE_SOLVER_CONFIG,
            stm_solver=stm_strict_reference_config(), scale_key="A")


# ---------------------------------------------------------------------------
# 2. Transversality denominator guard (G5R §18)
# ---------------------------------------------------------------------------
def test_finite_denominators_accepted():
    assert TS.validate_terminal_transversality(16.318) == 16.318
    assert TS.validate_terminal_transversality(-8.72e-4) == -8.72e-4
    # small FINITE denominator is NOT threshold-rejected (no grazing
    # threshold; G6 owns validity).
    assert TS.validate_terminal_transversality(1e-12) == 1e-12


@pytest.mark.parametrize("bad", [0.0, float("nan"), float("inf"),
                                 float("-inf")])
def test_exact_zero_nonfinite_rejected(bad):
    with pytest.raises(NTE):
        TS.validate_terminal_transversality(bad)


def test_terminal_event_time_gradient_formula_and_guard():
    n = np.array([1.0, 0.0, 0.0, 0.0])
    phi = np.eye(4)
    f = np.array([50.0, 0.0, 0.0, 0.0])
    eta = TS.terminal_event_time_gradient(n, phi, f)
    assert np.allclose(eta, -n @ phi / 50.0)
    # exact-zero denominator
    f_zero = np.array([0.0, 1.0, 0.0, 0.0])
    with pytest.raises(NTE):
        TS.terminal_event_time_gradient(n, phi, f_zero)
    # shape guards
    with pytest.raises(ValueError):
        TS.terminal_event_time_gradient(n, np.zeros((3, 3)), f)


def test_no_grazing_threshold_frozen():
    # the guard rejects only exact-zero/nonfinite; no small-threshold.
    assert TS.validate_terminal_transversality(1e-12) > 0


# ---------------------------------------------------------------------------
# 3. Qian RTI trim convergence (G5R §19)
# ---------------------------------------------------------------------------
def test_qian_trim_u_eps_validation(base):
    env, veh, x0 = base
    for bad in (0.0, -1e-9, 1.0, 1.5, float("nan")):
        with pytest.raises(ValueError):
            TS.build_terminal_sensitivity(
                "qian", x0, env, veh, K,
                research_solver=REFERENCE_SOLVER_CONFIG,
                stm_solver=stm_strict_reference_config(), scale_key="A",
                qian_trim_u_eps=bad)


def test_trim_convergence_audit_generated(base):
    env, veh, x0 = base
    aud = TS.qian_rti_trim_audit(
        x0, env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
        stm_solver=stm_strict_reference_config(), scale_key="A")
    assert aud["default_u_eps"] == 1e-9
    assert set(aud["u_eps_list"]) == {1e-6, 1e-7, 1e-8, 1e-9, 1e-10}
    # convergence below the G5 terminal-sensitivity error budget
    assert aud["converged_below_reference_budget"] is True
    assert aud["consecutive_phi_material_rel_1e-8_vs_1e-9"] < 1e-8
    # monotone decreasing trim dt as u_eps shrinks
    dts = [aud["per_u_eps"][u]["t_rti_minus_trim"] for u in aud["u_eps_list"]]
    assert all(dts[i] >= dts[i + 1] for i in range(len(dts) - 1))


def test_smaller_u_eps_trim_closer_to_rti(base):
    env, veh, x0 = base
    aud = TS.qian_rti_trim_audit(
        x0, env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
        stm_solver=stm_strict_reference_config(), scale_key="A",
        u_eps_list=(1e-6, 1e-9))
    dt6 = aud["per_u_eps"][1e-6]["t_rti_minus_trim"]
    dt9 = aud["per_u_eps"][1e-9]["t_rti_minus_trim"]
    assert dt9 < dt6


def test_trim_state_strict_interior(base):
    env, veh, x0 = base
    aud = TS.qian_rti_trim_audit(
        x0, env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
        stm_solver=stm_strict_reference_config(), scale_key="A")
    # each trim time is strictly interior (u_L* <= 1 - u_eps by construction);
    # sanity: terminal RTI retained.
    assert aud["terminal_time"] > aud["per_u_eps"][1e-9]["trim_time"]


# ---------------------------------------------------------------------------
# 4. Snapshot g5r metadata + G5 result preservation
# ---------------------------------------------------------------------------
def test_snapshot_g5r_metadata():
    g5r = SNAPSHOT["g5r"]
    assert g5r["terminal_kind_guard"] is True
    assert g5r["exact_zero_transversality_guard"] is True
    assert g5r["small_denominator_threshold_frozen"] is False
    assert g5r["qian_rti_trim_convergence_audited"] is True
    assert g5r["default_qian_trim_u_eps"] == 1e-9


def test_snapshot_qian_trim_audit_present():
    qian = SNAPSHOT["terminal"]["qian"]
    audit = qian["rti_trim_audit"]
    assert audit["converged_below_reference_budget"] is True
    assert audit["default_u_eps"] == 1e-9
    # per_u_eps keys are the stringified u_eps ("1e-06", ...).
    expected = {f"{u:g}" for u in (1e-6, 1e-7, 1e-8, 1e-9, 1e-10)}
    assert expected <= set(audit["per_u_eps"])
    assert audit["per_u_eps"]["1e-09"]["phi_material_rel_vs_default"] == 0.0


def test_snapshot_terminal_results_retained():
    # G5R must preserve the terminal sensitivity results.
    for m in ("qian", "sanger"):
        v = SNAPSHOT["terminal"][m]
        assert v["reference_stability"]["status"] == "PASS"
        assert v["tangency_residual"] < 1e-6
        assert set(v["fd_classifications"]["plus"]) == {"TOPOLOGY_PRESERVED"}
        assert set(v["fd_classifications"]["minus"]) == {"TOPOLOGY_PRESERVED"}


def test_snapshot_canonical_scale_unchanged():
    assert SNAPSHOT["canonical_scaling_decision"]["canonical_key"] == "A"
    assert SNAPSHOT["canonical_scaling_decision"]["decision"] == "FROZEN"


def test_no_g6_scope_leak():
    # G5R only tightens the terminal contract; no G6 grazing analysis.
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "terminal_sensitivity.py").read_text(
        encoding="utf-8")
    for token in ("grazing_threshold", "B0", "B4", "anchor", "monte",
                  "asymptotic", "chaos"):
        assert token not in src, token
    assert "validate_terminal_transversality" in src
    assert "check_terminal_eligibility" in src