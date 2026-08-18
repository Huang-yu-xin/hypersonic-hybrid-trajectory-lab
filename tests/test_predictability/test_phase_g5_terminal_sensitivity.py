"""Phase-G5 terminal sensitivity tests (G5 §62-§65).

Covers: RTI analytic normal vs an independent FD oracle, SRTI normal =
[0,0,0,1], terminal denominator nonzero / sign, no-terminal-saltation,
eta / J formulas and their projection equivalence, ``n^T J = 0``
tangency, theta terminal-time / terminal-state symmetry, SRTI terminal
gamma row, terminal nonlinear FD (event-time and terminal-state) with the
both-side terminal topology gate, terminal reference convergence, native
terminal descriptive interpretation (NOT a fair ranking), and the G6
scope boundary.
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
from hyptraj.predictability.hybrid_validation import HYBRID_FD_BASE_STEP
from hyptraj.predictability.stm import stm_strict_reference_config
from hyptraj.analysis.comparison_validation import (
    REFERENCE_05_SOLVER_CONFIG,
    REFERENCE_SOLVER_CONFIG,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g5_predictability_metrics_v1.json").read_text(
        encoding="utf-8"
    ))

K = 3.0


@pytest.fixture(scope="module")
def base():
    env = EnvironmentParams()
    veh = VehicleParams()
    ini = InitialCondition()
    x0 = np.array([env.earth_radius + ini.altitude, ini.range_angle,
                   ini.velocity, np.deg2rad(ini.flight_path_angle_deg)])
    return env, veh, x0


@pytest.fixture(scope="module")
def terminals(base):
    env, veh, x0 = base
    return {
        "qian": TS.build_terminal_sensitivity(
            "qian", x0, env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
            stm_solver=stm_strict_reference_config(), scale_key="A"),
        "sanger": TS.build_terminal_sensitivity(
            "sanger", x0, env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
            stm_solver=stm_strict_reference_config(), scale_key="A"),
    }


# ---------------------------------------------------------------------------
# 1. Terminal normal (G5 §62)
# ---------------------------------------------------------------------------
def test_rti_analytic_normal_matches_fd_oracle(base):
    env, veh, _ = base
    ts = TS.build_terminal_sensitivity(
        "qian", np.array([env.earth_radius + 1e5, 0.0, 7000.0,
                          np.deg2rad(-5.0)]),
        env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
        stm_solver=stm_strict_reference_config(), scale_key="A")
    nf = TS.qian_rti_terminal_normal(ts.terminal_state, env, veh, K)
    h = np.array([1e0, 1e-7, 1e-2, 1e-5])
    ev = TS.qian_rti_event_surface_value
    fd = np.zeros(4)
    for j in range(4):
        xp = ts.terminal_state.copy()
        xm = ts.terminal_state.copy()
        xp[j] += h[j]
        xm[j] -= h[j]
        fd[j] = (ev(xp, env, veh, K) - ev(xm, env, veh, K)) / (2.0 * h[j])
    assert np.max(np.abs(nf - fd)) < 1e-5
    assert abs(nf[1]) < 1e-12  # theta component zero by symmetry


def test_srti_normal():
    assert np.array_equal(TS.srti_terminal_normal(),
                          np.array([0.0, 0.0, 0.0, 1.0]))


def test_terminal_denominator_nonzero_and_sign(terminals):
    assert abs(terminals["qian"].denominator) > 0.0
    assert abs(terminals["sanger"].denominator) > 0.0
    # SRTI: gamma_dot^- < 0 matches the frozen direction -1
    assert terminals["sanger"].denominator < 0.0


def test_no_terminal_saltation():
    # RTI / SRTI are RESEARCH_TERMINAL: no Xi factor is ever inserted.
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "terminal_sensitivity.py").read_text(
        encoding="utf-8")
    assert "identity_reset_saltation" not in src
    assert "saltation_matrix" not in src
    assert "pre_terminal_trim_time" in src


# ---------------------------------------------------------------------------
# 2. Terminal derivative formulas + invariants (G5 §63)
# ---------------------------------------------------------------------------
def test_eta_and_J_formulas(terminals):
    for ts in terminals.values():
        phi = ts.phi_preterminal
        assert np.allclose(ts.event_time_gradient_initial,
                           -ts.normal @ phi / ts.denominator, atol=1e-10)
        assert np.allclose(ts.terminal_state_jacobian,
                           phi + np.outer(ts.f_minus,
                                          ts.event_time_gradient_initial),
                           atol=1e-10)


def test_projection_formula_equivalence(terminals):
    for ts in terminals.values():
        phi = ts.phi_preterminal
        proj = (np.eye(4) - np.outer(ts.f_minus, ts.normal) / ts.denominator) @ phi
        assert np.allclose(ts.terminal_state_jacobian, proj, atol=1e-10)


def test_terminal_tangency_invariant(terminals):
    for ts in terminals.values():
        # n^T J_e = 0 (4-component row identity)
        res = np.max(np.abs(ts.normal @ ts.terminal_state_jacobian))
        assert res < 1e-6
        assert ts.terminal_surface_tangency_residual < 1e-6


def test_theta_symmetry(terminals):
    for ts in terminals.values():
        assert abs(ts.event_time_gradient_initial[1]) < 1e-8
        col = ts.terminal_state_jacobian[:, 1]
        assert np.max(np.abs(col - np.array([0., 1., 0., 0.]))) < 1e-6


def test_srti_terminal_gamma_row_zero(terminals):
    ts = terminals["sanger"]
    assert np.max(np.abs(ts.terminal_state_jacobian[3, :])) < 1e-6


def test_terminal_time_units_seconds(terminals):
    for ts in terminals.values():
        # scaled event-time norm in seconds; fractional sensitivity dimensionless
        assert ts.scaled_event_time_norm_seconds > 0.0
        assert ts.fractional_event_time_sensitivity > 0.0


# ---------------------------------------------------------------------------
# 3. Terminal nonlinear FD (G5 §64) -- production fast path
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("model", ["qian", "sanger"])
def test_terminal_fd_convergence(base, model):
    env, veh, x0 = base
    ts = TS.build_terminal_sensitivity(
        model, x0, env, veh, K, research_solver=REFERENCE_SOLVER_CONFIG,
        stm_solver=stm_strict_reference_config(), scale_key="A")
    sweep = TS.terminal_fd_sweep(
        model, x0, env, veh, K, PRODUCTION_SOLVER_CONFIG,
        ts.terminal_kind, ts.topology_signature,
        ts.event_time_gradient_initial, ts.terminal_state_jacobian,
        HYBRID_FD_BASE_STEP, (1e-2, 1e-1))
    for m in ("mult_0.01", "mult_0.1"):
        rec = sweep[m]
        for j in range(4):
            c = rec["columns"][f"col_{j}"]
            assert c["classification_plus"] == "TOPOLOGY_PRESERVED", (model, j)
            assert c["classification_minus"] == "TOPOLOGY_PRESERVED", (model, j)
            if c["event_time_material_rel_error"] is not None:
                assert c["event_time_material_rel_error"] < 1e-3, (model, j)
            # terminal-state per-column max-abs: material columns are
            # O(1e3-1e4); the theta column's theoretical-zero rows carry
            # root/solver noise (structural-zero absolute residual).
            if c["terminal_state_max_abs_error"] is not None:
                assert c["terminal_state_max_abs_error"] < 1e-1, (model, j)


# ---------------------------------------------------------------------------
# 4. Terminal reference convergence (G5 §65)
# ---------------------------------------------------------------------------
def test_terminal_reference_stability():
    for model in ("qian", "sanger"):
        v = SNAPSHOT["terminal"][model]
        assert v["reference_stability"]["status"] == "PASS", model


# ---------------------------------------------------------------------------
# 5. Snapshot + native-terminal comparison limitation (G5 §48, §70)
# ---------------------------------------------------------------------------
def test_native_terminal_descriptive_warning():
    assert SNAPSHOT["native_terminal_comparison_warning"].startswith(
        "Qian RTI and Sanger SRTI")


def test_snapshot_terminal_fields_present():
    for model in ("qian", "sanger"):
        v = SNAPSHOT["terminal"][model]
        for field in ("terminal_time", "terminal_state", "normal",
                      "denominator", "eta", "J", "tangency_residual",
                      "scaled_singular_values", "rank", "nullity",
                      "scaled_event_time_norm_seconds",
                      "fractional_event_time_sensitivity", "etaS",
                      "reference_stability"):
            assert field in v, (model, field)


def test_snapshot_terminal_results_consistent():
    # tangency residual small; no terminal saltation anywhere.
    for model in ("qian", "sanger"):
        v = SNAPSHOT["terminal"][model]
        assert v["tangency_residual"] < 1e-6
        assert abs(v["theta_t_residual"]) < 1e-8
        assert v["theta_state_col_residual"] < 1e-6


def test_no_g6_scope_leak():
    # G5 terminal layer routes the G4R grazing_or_unresolved gate vocabulary
    # (legitimate), but must NOT perform any G6 grazing analysis.
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "terminal_sensitivity.py").read_text(
        encoding="utf-8")
    for token in ("grazing_threshold", "B0", "B4", "anchor", "monte",
                  "asymptotic", "chaos"):
        assert token not in src, token
    assert "grazing_or_unresolved_event" in src  # G4R terminal gate routing
    assert "import" in src