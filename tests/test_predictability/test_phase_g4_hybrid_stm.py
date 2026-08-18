"""Phase-G4 hybrid STM tests (G4 §42).

Covers: hybrid factor multiplication order, empty-chain -> ordinary
continuous STM, true-switch == Xi-factor count, diagnostics / synthetic
E0 excluded, Qian / Sanger factor chains at the three fixed endpoints,
factor state-consistency + identity reset, theta global column, Qian
global gamma row == zero, no-saltation negative control, global
event-time gradient (eta = q @ Phi_minus) + nonlinear FD, hybrid split /
composition consistency, fixed-time endpoint extraction, topology
signature extraction, topology / both-side gates, terminal-before-T,
Qian active-set gate, Sanger synthetic initial-mode semantics, reference
self-stability, hybrid STM vs full nonlinear FD, multi-epsilon
convergence, computational scaling invariance, and snapshot consistency.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability import hybrid_stm as H
from hyptraj.predictability import hybrid_validation as V
from hyptraj.predictability.hybrid_validation import HybridTopologyGate
from hyptraj.predictability.scaling import SCALING_CANDIDATES
from hyptraj.predictability.stm import (
    integrate_continuous_stm,
    stm_strict_reference_config,
)
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g4_hybrid_stm_v1.json").read_text(encoding="utf-8")
)

K = 3.0
ENDPOINTS = {"qian": 600.0, "sanger_600": 600.0, "sanger_900": 900.0}


@pytest.fixture(scope="module")
def base():
    env = EnvironmentParams()
    veh = VehicleParams()
    ini = InitialCondition()
    x0 = np.array([env.earth_radius + ini.altitude, ini.range_angle,
                   ini.velocity, np.deg2rad(ini.flight_path_angle_deg)])
    return env, veh, x0


@pytest.fixture(scope="module")
def results(base):
    """REF-0.1 hybrid STM results at the three endpoints."""
    env, veh, x0 = base
    res_solver = REFERENCE_SOLVER_CONFIG
    stm_solver = stm_strict_reference_config()
    out = {}
    for tag, T in (("qian", 600.0), ("sanger_600", 600.0), ("sanger_900", 900.0)):
        model = "qian" if tag == "qian" else "sanger"
        out[tag] = H.build_hybrid_stm(model, x0, T, env, veh, K,
                                      research_solver=res_solver,
                                      stm_solver=stm_solver)
    return out


# ---------------------------------------------------------------------------
# 1. Factor algebra / multiplication order
# ---------------------------------------------------------------------------
def test_empty_chain_is_ordinary_continuous_stm(base):
    env, veh, x0 = base
    # T=50 s: before the first Sanger true switch (X0 ~ 202.96 s)
    r = H.build_hybrid_stm("sanger", x0, 50.0, env, veh, K,
                           research_solver=PRODUCTION_SOLVER_CONFIG,
                           stm_solver=stm_strict_reference_config())
    assert r.topology_signature == ()
    assert len(r.event_cumulatives) == 0
    C = integrate_continuous_stm("sanger_atm", x0, (0.0, 50.0), env, veh, K,
                                 solver=stm_strict_reference_config())
    assert np.allclose(r.phi_final, C.phi, atol=1e-8)


def test_phi_final_equals_factor_product_in_order(base, results):
    """Lock the incremental multiplication order: Phi = M_N ... M_1."""
    for tag, r in results.items():
        phi = np.eye(4)
        for f in r.factors:
            phi = f.matrix @ phi
        assert np.allclose(phi, r.phi_final, atol=1e-8), tag


def test_true_switch_count_equals_xi_count(results):
    for tag, r in results.items():
        n_xi = sum(1 for f in r.factors if f.kind == "SALTATION")
        assert n_xi == len(r.topology_signature) == len(r.event_cumulatives), tag


def test_diagnostics_and_synthetic_e0_not_factors(base, results):
    for tag, r in results.items():
        for f in r.factors:
            assert f.kind in ("CONTINUOUS", "SALTATION")
            assert f.event_name not in (
                "sanger_atmospheric_pullout", "sanger_vac_apogee",
                "synthetic_initial_entry", "qian_rti", "sanger_srti")
        # synthetic Sanger E0: no saltation factor at t=0
        if tag.startswith("sanger"):
            assert r.factors[0].kind == "CONTINUOUS"
            assert r.factors[0].t_start == 0.0
            assert r.initial_mode == "SANGER_ATM"


def test_factor_chronology_and_state_continuity(results):
    for tag, r in results.items():
        prev_end = -1.0
        for f in r.factors:
            assert f.t_start >= prev_end - 1e-12
            prev_end = f.t_end
            if f.kind == "CONTINUOUS" and "state_continuity_error" in f.metadata:
                assert f.metadata["state_continuity_error"] < 1e-6, (
                    tag, f.mode)


# ---------------------------------------------------------------------------
# 2. Structural invariants
# ---------------------------------------------------------------------------
def test_theta_global_column_invariant(results):
    for tag, r in results.items():
        col = r.phi_final[:, 1]
        assert np.max(np.abs(col - np.array([0.0, 1.0, 0.0, 0.0]))) < 1e-6, tag


def test_qian_global_gamma_row_zero(results):
    row = results["qian"].phi_final[3, :]
    assert np.max(np.abs(row - np.array([0.0, 0.0, 0.0, 0.0]))) < 1e-6


def test_endpoint_modes_and_signatures(results):
    assert results["qian"].topology_signature == ("qian_capture",)
    assert results["qian"].endpoint_mode == "QEG_GLIDE"
    assert results["sanger_600"].topology_signature == (
        "sanger_atmosphere_exit", "sanger_atmosphere_entry")
    assert results["sanger_600"].endpoint_mode == "SANGER_ATM"
    assert results["sanger_900"].topology_signature == (
        "sanger_atmosphere_exit", "sanger_atmosphere_entry",
        "sanger_atmosphere_exit", "sanger_atmosphere_entry")
    assert results["sanger_900"].endpoint_mode == "SANGER_ATM"


# ---------------------------------------------------------------------------
# 3. Global event-time gradient
# ---------------------------------------------------------------------------
def test_global_eta_formula(base, results):
    # eta_0 = q_local @ Phi_minus (first true switch cumulative record).
    for tag, r in results.items():
        first = r.event_cumulatives[0]
        assert np.allclose(first.event_time_gradient_initial,
                           first.q_local @ first.phi_minus_initial, atol=1e-10), tag
        assert np.allclose(first.phi_plus_initial,
                           first.xi @ first.phi_minus_initial, atol=1e-10), tag


@pytest.mark.parametrize("tag,T", [("qian", 600.0), ("sanger_900", 900.0)])
def test_global_event_time_nonlinear_fd(base, results, tag, T):
    env, veh, x0 = base
    model = "qian" if tag == "qian" else "sanger"
    r = results[tag]
    etas = [c.event_time_gradient_initial for c in r.event_cumulatives]
    gt = V.global_event_time_fd(
        model, x0, T, env, veh, K, PRODUCTION_SOLVER_CONFIG,
        r.topology_signature, r.endpoint_mode,
        check_qeg_interior=(model == "qian"),
        eta_list=etas, event_kinds=list(r.topology_signature),
        multipliers=(1e-1,))
    for k_idx in range(min(2, len(etas))):
        for col, c in gt["mult_0.1"][f"switch_{k_idx}"].items():
            assert c["cls"] == ["TOPOLOGY_PRESERVED", "TOPOLOGY_PRESERVED"]
            if c["fd"] is not None and c["material_rel_error"] is not None:
                assert c["material_rel_error"] < 1e-4, (tag, k_idx, col)


# ---------------------------------------------------------------------------
# 4. Hybrid STM vs full nonlinear FD (+ multi-epsilon plateau)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tag,T", [("qian", 600.0), ("sanger_600", 600.0),
                                   ("sanger_900", 900.0)])
def test_hybrid_stm_matches_nonlinear_fd(base, results, tag, T):
    env, veh, x0 = base
    model = "qian" if tag == "qian" else "sanger"
    r = results[tag]
    snap_tag = {"qian": "qian_T600", "sanger_600": "sanger_T600",
                "sanger_900": "sanger_T900"}[tag]
    mult = SNAPSHOT["endpoints"][snap_tag]["fd_plateau"]["multiplier"]
    s = V.hybrid_fixed_time_fd_sweep(
        model, x0, T, env, veh, K, PRODUCTION_SOLVER_CONFIG,
        r.phi_final, r.topology_signature, r.endpoint_mode,
        check_qeg_interior=(model == "qian"), multipliers=(mult,))
    rec = s[f"mult_{mult:g}"]
    assert rec["n_valid_columns"] == 4, tag
    assert rec["material_rel_error"] < 1e-5, tag
    assert set(rec["classification_plus"]) == {"TOPOLOGY_PRESERVED"}
    assert set(rec["classification_minus"]) == {"TOPOLOGY_PRESERVED"}


@pytest.mark.parametrize("tag,T", [("qian", 600.0), ("sanger_900", 900.0)])
def test_fd_plateau_convergence(base, results, tag, T):
    env, veh, x0 = base
    model = "qian" if tag == "qian" else "sanger"
    r = results[tag]
    s = V.hybrid_fixed_time_fd_sweep(
        model, x0, T, env, veh, K, PRODUCTION_SOLVER_CONFIG,
        r.phi_final, r.topology_signature, r.endpoint_mode,
        check_qeg_interior=(model == "qian"),
        multipliers=(1e-2, 1e-1, 1.0, 10.0))
    rels = {m: s[f"mult_{m:g}"]["material_rel_error"] for m in (1e-2, 1e-1, 1.0, 10.0)}
    # convergent at small/moderate eps; truncation/nonlinear regime at eps=10
    assert rels[1e-2] is not None and rels[1e-2] < 1e-4, tag
    assert rels[10.0] > rels[1e-1], tag


# ---------------------------------------------------------------------------
# 5. Qian no-saltation negative control
# ---------------------------------------------------------------------------
def test_qian_no_saltation_negative_control(base):
    env, veh, x0 = base
    res_solver = REFERENCE_SOLVER_CONFIG
    stm_solver = stm_strict_reference_config()
    correct, naive = H.qian_no_saltation_negative_control(
        x0, 600.0, env, veh, K,
        research_solver=res_solver, stm_solver=stm_solver)
    s = V.hybrid_fixed_time_fd_sweep(
        "qian", x0, 600.0, env, veh, K, REFERENCE_SOLVER_CONFIG,
        correct, ("qian_capture",), "QEG_GLIDE", check_qeg_interior=True,
        multipliers=(1e-1,))["mult_0.1"]
    fd = np.array(s["fd_matrix"])
    mat = np.abs(correct) >= 1e-8 * np.max(np.abs(correct))
    rel_correct = float(np.max(np.abs(fd - correct)[mat]) /
                        np.max(np.abs(correct[mat])))
    mat_n = np.abs(naive) >= 1e-8 * np.max(np.abs(naive))
    rel_naive = float(np.max(np.abs(fd - naive)[mat_n]) /
                      np.max(np.abs(naive[mat_n])))
    # correct hybrid STM agrees with the nonlinear FD (material rel); the
    # naive no-saltation chain fails hard on the gamma structure.
    assert rel_correct < 1e-5
    assert rel_naive > rel_correct * 1000
    assert np.max(np.abs(correct[3, :])) < 1e-6
    assert abs(correct[3, 3]) < 1e-6
    assert abs(naive[3, 3]) > 1e-3


# ---------------------------------------------------------------------------
# 6. Hybrid split / composition consistency (G4 §18)
# ---------------------------------------------------------------------------
def test_hybrid_split_composition_sanger(base):
    env, veh, x0 = base
    res_solver = REFERENCE_SOLVER_CONFIG
    stm_solver = stm_strict_reference_config()
    T = 900.0
    t_a = 60.0
    left = H.build_hybrid_stm("sanger", x0, T, env, veh, K,
                              research_solver=res_solver, stm_solver=stm_solver)
    # events + x(t_a) from the frozen trajectory
    result, collector = V.run_nonlinear_hybrid(
        "sanger", x0, env, veh, K, res_solver)
    events = list(result.trajectory.events)
    x_ta, _ = V.fixed_time_state(collector, t_a)
    tail = H.build_split_tail(
        "sanger", t_a, x_ta, "SANGER_ATM", T, events, env, veh, K,
        stm_solver=stm_solver)
    head = integrate_continuous_stm("sanger_atm", x0, (0.0, t_a), env, veh, K,
                                    solver=stm_solver).phi
    assert np.max(np.abs(left.phi_final - tail @ head)) < 1e-4


def test_hybrid_split_composition_qian(base):
    env, veh, x0 = base
    res_solver = REFERENCE_SOLVER_CONFIG
    stm_solver = stm_strict_reference_config()
    T = 600.0
    t_a = 60.0
    left = H.build_hybrid_stm("qian", x0, T, env, veh, K,
                              research_solver=res_solver, stm_solver=stm_solver)
    result, collector = V.run_nonlinear_hybrid("qian", x0, env, veh, K,
                                               res_solver)
    events = list(result.events)
    x_ta, _ = V.fixed_time_state(collector, t_a)
    tail = H.build_split_tail(
        "qian", t_a, x_ta, "ENTRY_CAPTURE", T, events, env, veh, K,
        stm_solver=stm_solver)
    head = integrate_continuous_stm("entry_capture", x0, (0.0, t_a), env, veh, K,
                                    solver=stm_solver).phi
    assert np.max(np.abs(left.phi_final - tail @ head)) < 1e-4


# ---------------------------------------------------------------------------
# 7. Topology gate classifications (synthetic)
# ---------------------------------------------------------------------------
def _fake_ok_result(terminal_time, terminal_kind, events):
    traj = SimpleNamespace(terminal_time=terminal_time,
                           terminal_kind=terminal_kind,
                           events=events)
    result = SimpleNamespace(trajectory=traj, events=events)
    return result


def _fake_collector(mode):
    seg = SimpleNamespace(t_start=0.0, t_end=1e9, mode=mode,
                          solution=lambda t: np.ones(4))
    return SimpleNamespace(segments=(seg,))


def test_topology_gate_terminal_before_t():
    env = EnvironmentParams(); veh = VehicleParams()
    result = _fake_ok_result(100.0, "rti", [])
    gate, info = V.classify_perturbed_topology(
        "qian", ("qian_capture",), "QEG_GLIDE", result,
        _fake_collector("QEG_GLIDE"), 600.0, env, veh, 3.0,
        check_qeg_interior=False)
    assert gate == HybridTopologyGate.TOPOLOGY_CHANGED
    assert info["reason"].startswith("terminal_before_fixed_endpoint")


def test_topology_gate_signature_changed():
    env = EnvironmentParams(); veh = VehicleParams()
    sw = SimpleNamespace(kind="atmosphere_exit", index=0, time=100.0,
                         state=np.ones(4))
    result = _fake_ok_result(1e9, "srti", [sw])
    gate, info = V.classify_perturbed_topology(
        "sanger", ("sanger_atmosphere_exit", "sanger_atmosphere_entry"),
        "SANGER_ATM", result, _fake_collector("SANGER_ATM"), 600.0,
        env, veh, 3.0, check_qeg_interior=False)
    assert gate == HybridTopologyGate.TOPOLOGY_CHANGED


def test_topology_gate_order_changed():
    env = EnvironmentParams(); veh = VehicleParams()
    sw1 = SimpleNamespace(kind="atmosphere_entry", index=1, time=100.0,
                          state=np.ones(4))
    sw2 = SimpleNamespace(kind="atmosphere_exit", index=2, time=200.0,
                          state=np.ones(4))
    result = _fake_ok_result(1e9, "srti", [sw1, sw2])
    gate, _ = V.classify_perturbed_topology(
        "sanger", ("sanger_atmosphere_exit", "sanger_atmosphere_entry"),
        "SANGER_ATM", result, _fake_collector("SANGER_ATM"), 600.0,
        env, veh, 3.0, check_qeg_interior=False)
    assert gate == HybridTopologyGate.EVENT_ORDER_CHANGED


def test_topology_gate_preserved():
    env = EnvironmentParams(); veh = VehicleParams()
    sw = SimpleNamespace(kind="atmosphere_exit", index=0, time=100.0,
                         state=np.ones(4))
    result = _fake_ok_result(1e9, "srti", [sw])
    # endpoint mode extracted from the collector is SANGER_ATM
    gate, _ = V.classify_perturbed_topology(
        "sanger", ("sanger_atmosphere_exit",), "SANGER_ATM", result,
        _fake_collector("SANGER_ATM"), 300.0, env, veh, 3.0,
        check_qeg_interior=False)
    assert gate == HybridTopologyGate.TOPOLOGY_PRESERVED


# ---------------------------------------------------------------------------
# 8. Fixed-time endpoint extraction
# ---------------------------------------------------------------------------
def test_fixed_time_endpoint_extraction(base):
    env, veh, x0 = base
    result, collector = V.run_nonlinear_hybrid(
        "sanger", x0, env, veh, K, PRODUCTION_SOLVER_CONFIG)
    for T in (600.0, 900.0):
        state, mode = V.fixed_time_state(collector, T)
        assert state.shape == (4,)
        assert mode == "SANGER_ATM"


# ---------------------------------------------------------------------------
# 9. Reference self-stability + scaling invariance (snapshot)
# ---------------------------------------------------------------------------
def test_snapshot_schema_and_flags():
    assert SNAPSHOT["schema_version"] == "phase-g4-hybrid-stm-v1"
    assert SNAPSHOT["state_order"] == ["r", "theta", "v", "gamma"]
    assert SNAPSHOT["grazing_anchors_excluded"] is True
    assert SNAPSHOT["grazing_threshold_none_frozen"] is True
    assert SNAPSHOT["scientific_canonical_scaling_status"].startswith(
        "CANONICAL_SCALE_NUMERIC_VALUES_PENDING")
    init = SNAPSHOT["initial_discrete_mode_semantics"]
    assert init["qian_initial_mode"] == "ENTRY_CAPTURE"
    assert init["sanger_initial_mode"] == "SANGER_ATM"
    assert init["sanger_synthetic_initial_entry_saltation"] is False


def test_snapshot_reference_self_stability_pass():
    for tag, e in SNAPSHOT["endpoints"].items():
        assert e["reference_convergence"]["status"] == "PASS", tag
        assert e["reference_convergence"]["phi_material_rel_diff_01_05"] < 1e-5


def test_snapshot_fd_and_refgrade_pass():
    for tag, e in SNAPSHOT["endpoints"].items():
        assert e["fd_plateau"]["material_rel_error"] < 1e-5, tag
        assert e["reference_grade_fd"]["material_rel_error"] < 1e-5, tag
        assert set(e["reference_grade_fd"]["classification_plus"]) == {
            "TOPOLOGY_PRESERVED"}
        assert set(e["reference_grade_fd"]["classification_minus"]) == {
            "TOPOLOGY_PRESERVED"}


def test_snapshot_invariants_and_negative_control():
    for tag in ("qian_T600", "sanger_T600", "sanger_T900"):
        iv = SNAPSHOT["endpoints"][tag]["structural_invariants"]
        assert iv["theta_residual"] < 1e-9
    qi = SNAPSHOT["endpoints"]["qian_T600"]["structural_invariants"]
    assert max(abs(v) for v in qi["qian_gamma_row"]) < 1e-9
    nc = SNAPSHOT["qian_no_saltation_negative_control"]
    assert nc["correct_hybrid_error_vs_FD"] < 1e-3
    assert nc["naive_no_saltation_error_vs_FD"] > nc["correct_hybrid_error_vs_FD"] * 100


def test_snapshot_scaling_invariance_pass():
    for tag, e in SNAPSHOT["computational_scaling_audit"].items():
        assert e["status"] == "PASS", tag


# ---------------------------------------------------------------------------
# 10. Scope guards: no G5/G6 leak
# ---------------------------------------------------------------------------
def test_no_g5_g6_scope_leak():
    """G4 layers must not perform G5 metrics / G6 grazing analysis.

    ``ftle``/``metrics``/``terminal_sensitivity`` were activated by G5
    (their content is guarded by ``test_phase_g5_*.py``); only the G6+
    placeholder ``observability`` stays empty here.
    """
    src_root = Path(__file__).resolve().parents[2] / "src" / "hyptraj" / "predictability"
    for mod in ("hybrid_stm", "hybrid_validation"):
        src = (src_root / f"{mod}.py").read_text(encoding="utf-8")
        for token in ("ftle", "singular_value", "sigma_max", "lyap"):
            assert token not in src, (mod, token)
    # G5 owns the metrics layer; G6+ placeholder still empty.
    assert (src_root / "observability.py").read_text(encoding="utf-8").strip() == ""