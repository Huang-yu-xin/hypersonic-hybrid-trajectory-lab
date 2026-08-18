"""Phase-G0 predictability-protocol semantic tests (G0 §22).

Covers the G0 acceptance surface:

1.  state ordering [r, theta, v, gamma] frozen
2.  initial-state-only perturbation scope
3.  Qian capture semantics (surface=gamma, direction=+1, true hybrid
    switch, normal=[0,0,0,1])
4.  Qian RTI terminal semantics (terminal, NOT a mode switch)
5.  Sanger atmosphere interface (surface=h-h_atm, normal=[1,0,0,0])
6.  Sanger exit/entry true hybrid switches with identity reset
7.  pullout/apogee diagnostic-only (no saltation classification)
8.  SRTI research terminal (no fake post-mode)
9.  F2.1 DENSE_RECOVERED is event-resolution METADATA, still the frozen
    ATM->VAC switch (not a new mode, not a new reset)
10. frozen numerics: PRODUCTION_SOLVER_CONFIG unchanged
11. representative trajectories: F4 coordinates + expected frozen regime
    labels (small-scale protocol verification, NOT a domain re-scan)
12. grazing anchors reserved for G6 match the frozen regression snapshot
13. frozen tags / snapshots not modified (snapshots are only read)
14. saltation convention (identity-reset reduction, sign convention)
15. event-time convention (sign + first-order identity)
16. grazing policy: diagnostic quantity frozen, numeric threshold deferred
17. state-scaling convention sanity (identity / spectrum / singular-value
    non-invariance; candidates positive)
18. FTLE definition frozen (no production FTLE computed)
19. error taxonomy + topology gate vocabulary
20. claim boundaries present
21. machine-readable protocol payload is JSON-able and complete
22. taxonomy cross-checks the FROZEN event factories
23. G0 status flags: G1 NOT started, no G1 computation implemented
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis.sensitivity_trajectory import (
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
from hyptraj.predictability.event_metadata import (
    EVENT_TAXONOMY,
    EventClassification,
    all_taxonomy_rows,
    crosscheck_frozen_factories,
    event_by_name,
)
from hyptraj.predictability.protocol import (
    GRAZING_ANCHOR_PARAMETERS,
    REPRESENTATIVE_CASES,
    FORBIDDEN_CLAIMS,
    GrazingRegime,
    SCOPE_STATEMENT,
    TopologyGateResult,
    ValidationErrorCategory,
    classify_transversality,
    event_time_first_order,
    generic_saltation,
    interface_crossing_rate,
    machine_readable_protocol,
    saltation_identity_reset,
)
from hyptraj.predictability.scaling import (
    CANONICAL_SCALE_NUMERIC_STATUS,
    CANONICAL_SCALING_STATUS,
    SCALING_CANDIDATES,
    SCALING_CONVENTION_DEFINED,
    CANONICAL_SCALE_NUMERIC_VALUES_FROZEN,
    CANONICAL_SCALE_NUMERIC_VALUES_PENDING_VALIDATION,
    canonical_candidate,
    finite_time_lyapunov_exponent,
    identity_scaled_stm,
    scaled_stm,
    singular_value_non_invariance,
    spectrum_invariance,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.qian_research_trajectory import (
    TERMINAL_RTI,
    integrate_qian_research_trajectory,
)
from hyptraj.simulation.sanger_events import (
    atmosphere_interface_normal,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_research_trajectory import (
    RESOLUTION_DENSE_RECOVERED,
    SANGER_RESEARCH_EVENT_RESOLUTION_VERSION,
)
from hyptraj.simulation.sanger_trajectory import (
    SANGER_ATM,
    SANGER_VAC,
    TERMINAL_SRTI,
)
from hyptraj.simulation.trajectory import SolverConfig

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PHASE_F_SNAPSHOT = json.loads(
    (DATA_DIR / "phase_f_gamma_k_sensitivity_v1.json").read_text(
        encoding="utf-8"
    )
)


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


# ---------------------------------------------------------------------------
# 1. State ordering frozen
# ---------------------------------------------------------------------------
def test_state_ordering_frozen():
    from hyptraj.predictability.event_metadata import STATE_ORDER

    assert STATE_ORDER == ("r", "theta", "v", "gamma")
    # Frozen physics source must still declare the same ordering.
    from hyptraj.models.dynamics import atmospheric_dynamics

    assert atmospheric_dynamics.__doc__ is not None
    assert "[r, theta, v, gamma]" in atmospheric_dynamics.__doc__


def test_taxonomy_state_semantics(base):
    env, veh, ini, ctl = base
    traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    # capture / RTI event states carry the frozen ordering.
    cap = traj.capture_event.state
    rti = traj.rti_event.state
    for s in (cap, rti):
        assert s.shape == (4,)
        assert s[0] > env.earth_radius          # r ~ 6.4e6 m
        assert s[2] > 0.0                        # v
    assert cap[3] == pytest.approx(0.0, abs=1e-9)  # gamma = 0 at capture


# ---------------------------------------------------------------------------
# 2. Perturbation scope
# ---------------------------------------------------------------------------
def test_perturbation_scope_initial_state_only():
    payload = machine_readable_protocol()
    assert payload["perturbation_scope"] == "initial-state-only"
    assert payload["perturbation_vector"] == [
        "delta r_0", "delta theta_0", "delta v_0", "delta gamma_0"
    ]
    assert payload["phase_f_parameter_jacobian_distinct"] is True


# ---------------------------------------------------------------------------
# 3 / 4. Qian capture / RTI semantics
# ---------------------------------------------------------------------------
def test_qian_capture_taxonomy():
    cap = event_by_name("qian_capture")
    assert cap.surface == "g_c = gamma"
    assert cap.direction == +1
    assert cap.mode_before == "ENTRY_CAPTURE"
    assert cap.mode_after == "QEG_GLIDE"
    assert (
        cap.classification
        == EventClassification.TRUE_HYBRID_MODE_SWITCH
    )
    assert cap.saltation is True
    assert cap.reset_is_identity is True
    assert list(cap.normal) == pytest.approx([0.0, 0.0, 0.0, 1.0])


def test_qian_rti_taxonomy():
    rti = event_by_name("qian_rti")
    assert rti.surface == "L_req - L = 0"
    assert rti.direction == +1
    assert rti.mode_before == "QEG_GLIDE"
    assert rti.mode_after is None            # no post-RTI mode
    assert rti.classification == EventClassification.RESEARCH_TERMINAL
    assert rti.saltation is False
    assert rti.terminal_sensitivity is True


def test_qian_rti_is_terminal_not_mode_switch(base):
    env, veh, ini, ctl = base
    traj = integrate_qian_research_trajectory(env, veh, ini, ctl)
    assert traj.terminal_kind == TERMINAL_RTI
    assert traj.success
    assert traj.mode_sequence == (ENTRY_CAPTURE, QEG_GLIDE)
    assert classify_qian_regime(traj) == QIAN_REGIME_RTI


# ---------------------------------------------------------------------------
# 5 / 6. Sanger atmosphere interface / exit / entry
# ---------------------------------------------------------------------------
def test_sanger_interface_surface_and_normal():
    assert list(atmosphere_interface_normal()) == pytest.approx(
        [1.0, 0.0, 0.0, 0.0]
    )
    from hyptraj.simulation.sanger_events import (
        atmosphere_interface_value,
    )

    env = EnvironmentParams()
    state = np.array(
        [env.earth_radius + env.atmosphere_boundary, 0.0, 7000.0, -0.1],
        dtype=float,
    )
    assert atmosphere_interface_value(state, env) == pytest.approx(0.0)


def test_sanger_exit_entry_taxonomy():
    exit_ = event_by_name("sanger_atmosphere_exit")
    entry = event_by_name("sanger_atmosphere_entry")
    for ev in (exit_, entry):
        assert ev.surface == "G_h = h - h_atm"
        assert list(ev.normal) == pytest.approx([1.0, 0.0, 0.0, 0.0])
        assert ev.classification == EventClassification.TRUE_HYBRID_MODE_SWITCH
        assert ev.reset_is_identity is True
        assert ev.saltation is True
        assert ev.terminal_sensitivity is False
    assert exit_.direction == +1
    assert entry.direction == -1


def test_sanger_exit_entry_are_true_switches(base):
    env, veh, ini, ctl = base
    traj = _run_sanger(base)
    kinds = [e.kind for e in traj.events]
    assert "atmosphere_exit" in kinds
    assert "atmosphere_entry" in kinds
    exit_events = [e for e in traj.events if e.kind == "atmosphere_exit"]
    entry_events = [e for e in traj.events if e.kind == "atmosphere_entry"]
    for e in (*exit_events, *entry_events):
        assert e.mode_before in (SANGER_ATM, SANGER_VAC)
        assert e.mode_after in (SANGER_ATM, SANGER_VAC)
        assert e.mode_before != e.mode_after
        # f_minus / f_plus / normal metadata present (identity reset:
        # x_plus = x_minus by plain copy).
        assert e.f_minus is not None
        assert e.f_plus is not None
        assert list(e.normal) == pytest.approx([1.0, 0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# 7. pullout / apogee diagnostic only
# ---------------------------------------------------------------------------
def test_pullout_apogee_diagnostic_only():
    pull = event_by_name("sanger_atmospheric_pullout")
    apo = event_by_name("sanger_vac_apogee")
    for ev in (pull, apo):
        assert ev.classification == EventClassification.DIAGNOSTIC
        assert ev.saltation is False
        assert ev.terminal_sensitivity is False
        assert ev.mode_before == ev.mode_after   # no mode change
    assert pull.direction == +1
    assert apo.direction == -1


def test_pullout_apogee_do_not_change_mode(base):
    traj = _run_sanger(base)
    for e in traj.events:
        if e.kind in ("atmospheric_pullout", "vacuum_apogee"):
            assert e.mode_before == e.mode_after
            assert e.f_minus is None            # diagnostic: no saltation data


# ---------------------------------------------------------------------------
# 8. SRTI research terminal
# ---------------------------------------------------------------------------
def test_srti_terminal_semantics():
    srti = event_by_name("sanger_srti")
    assert srti.classification == EventClassification.RESEARCH_TERMINAL
    assert srti.mode_after is None              # no fake post-mode
    assert srti.saltation is False
    assert srti.terminal_sensitivity is True


def test_srti_terminal_kind(base):
    traj = _run_sanger(base)
    assert traj.terminal_kind == TERMINAL_SRTI
    assert traj.success


# ---------------------------------------------------------------------------
# 9. F2.1 DENSE_RECOVERED is resolution metadata, not a new mode/reset
# ---------------------------------------------------------------------------
def test_f21_dense_recovered_is_resolution_metadata():
    assert RESOLUTION_DENSE_RECOVERED == "DENSE_RECOVERED"
    # The recovered event still represents the frozen ATM -> VAC switch.
    recovered = event_by_name("sanger_atmosphere_exit")
    assert recovered.mode_before == SANGER_ATM
    assert recovered.mode_after == SANGER_VAC
    assert recovered.reset_is_identity is True


def test_f21_resolution_vocabulary():
    assert SANGER_RESEARCH_EVENT_RESOLUTION_VERSION == "v1"


# ---------------------------------------------------------------------------
# 10. Frozen numerics unchanged
# ---------------------------------------------------------------------------
def test_production_solver_config_unchanged():
    cfg = PRODUCTION_SOLVER_CONFIG
    assert isinstance(cfg, SolverConfig)
    assert cfg.method == "DOP853"
    assert cfg.rtol == 1e-9
    assert list(cfg.atol) == [1e-4, 1e-11, 1e-7, 1e-11]
    assert cfg.max_step == 20.0
    assert cfg.dense_output is True


# ---------------------------------------------------------------------------
# 11. Representative trajectories -- F4 coordinates + expected labels
# ---------------------------------------------------------------------------
_F4_EXPECTED = {
    "qian_baseline": ("Qian", -5.0, 3.0, "QIAN_RTI"),
    "sanger_baseline": ("Sanger", -5.0, 3.0, "SRTI_N2"),
    "n0_deep": ("Sanger", -1.25, 1.125, "SRTI_N0"),
    "n1_deep": ("Sanger", -4.5, 2.375, "SRTI_N1"),
    "n2_deep": ("Sanger", -8.75, 2.5, "SRTI_N2"),
    "n3_deep": ("Sanger", -8.25, 3.5, "SRTI_N3"),
    "n4_deep": ("Sanger", -7.0, 4.875, "SRTI_N4"),
    "n5_deep": ("Sanger", -8.75, 4.875, "SRTI_N5"),
}


def test_representative_case_coordinates_frozen():
    by_key = {c.key: c for c in REPRESENTATIVE_CASES}
    assert set(by_key) == set(_F4_EXPECTED)
    for key, (model, gamma0, k, regime) in _F4_EXPECTED.items():
        c = by_key[key]
        assert c.model == model
        assert c.gamma0_deg == pytest.approx(gamma0)
        assert c.K == pytest.approx(k)
        assert c.expected_regime == regime


def test_representative_topologies_small_scale_verification(base):
    """Small-scale protocol verification (G0 §15, §22): confirm the frozen
    F4 representative points still return their expected frozen topology.

    Uses the PRODUCTION research integrators + frozen classifiers -- this
    is protocol-level validation of the representative set, NOT a gamma0-K
    domain re-scan and NOT any G1 computation.
    """
    env, veh, _ini, _ctl = base

    # Qian baseline.
    q = integrate_qian_research_trajectory(
        env, veh, _ini, ConstantKControl(3.0)
    )
    assert classify_qian_regime(q) == QIAN_REGIME_RTI

    for c in REPRESENTATIVE_CASES:
        if c.model != "Sanger":
            continue
        ini = InitialCondition(
            altitude=100_000.0,
            velocity=7_000.0,
            flight_path_angle_deg=c.gamma0_deg,
            range_angle=0.0,
        )
        traj = _run_sanger_at(env, veh, ini, ConstantKControl(c.K))
        assert traj.terminal_kind == TERMINAL_SRTI, (
            f"{c.key}: expected SRTI terminal, got {traj.terminal_kind}"
        )
        metrics = analyze_sanger_trajectory(traj.trajectory, env)
        regime = classify_sanger_regime(
            traj.trajectory, skip_count=metrics.skip_count
        )
        assert regime == c.expected_regime, (
            f"{c.key} topology mismatch: expected {c.expected_regime}, "
            f"got {regime}"
        )


# ---------------------------------------------------------------------------
# 12. Grazing anchors reserved for G6
# ---------------------------------------------------------------------------
def test_grazing_anchors_match_frozen_snapshot():
    snapshot_anchors = PHASE_F_SNAPSHOT["grazing"]["extremal_anchors"]
    assert len(snapshot_anchors) == len(GRAZING_ANCHOR_PARAMETERS) == 10
    by_side = {}
    for a in snapshot_anchors:
        # JSON uses "N1_side"; protocol keeps the same vocabulary.
        by_side[(a["branch"], a["side"])] = tuple(a["parameter"])
    for branch, side, params in GRAZING_ANCHOR_PARAMETERS:
        assert by_side[(branch, side)] == pytest.approx(params), (
            f"anchor {branch}/{side} drifted from the frozen snapshot"
        )


def test_grazing_anchors_g6_reserved():
    payload = machine_readable_protocol()
    assert payload["grazing_anchors"]["count"] == 10
    assert payload["grazing_anchors"]["g6_reserved"] is True


# ---------------------------------------------------------------------------
# 13. Frozen tags / snapshots untouched (snapshots are only read here)
# ---------------------------------------------------------------------------
def test_snapshot_files_unchanged_on_disk():
    data_dir = DATA_DIR
    for name in ("qian_sanger_comparison_v1.json",
                 "phase_f_gamma_k_sensitivity_v1.json"):
        path = data_dir / name
        assert path.exists()
        raw = path.read_text(encoding="utf-8")
        json.loads(raw)      # still valid JSON (never corrupted)


def test_frozen_tags_present():
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git not available")
    import subprocess

    tags = subprocess.run(
        ["git", "tag", "--list"], capture_output=True, text=True, check=True
    ).stdout.split()
    for tag in (
        "qian-baseline-v1.0",
        "phase-b-v1.0",
        "phase-c-v1.0",
        "sanger-baseline-v1.0",
        "phase-d-v1.0",
        "phase-e-v1.0",
        "qian-sanger-comparison-v1.0",
        "phase-f-v1.0",
        "gamma-k-sensitivity-v1.0",
    ):
        assert tag in tags, f"frozen tag {tag} is missing"


def test_no_g0_final_tag_created():
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git not available")
    import subprocess

    tags = subprocess.run(
        ["git", "tag", "--list"], capture_output=True, text=True, check=True
    ).stdout.split()
    assert "phase-g-v1.0" not in tags
    assert "predictability-v1.0" not in tags


# ---------------------------------------------------------------------------
# 14. Saltation convention
# ---------------------------------------------------------------------------
def test_saltation_identity_reset_reduction():
    rng = np.random.default_rng(42)
    for _ in range(20):
        n = rng.normal(size=4)
        fm = rng.normal(size=4)
        fp = rng.normal(size=4)
        if abs(n @ fm) < 1e-6:
            continue
        general = generic_saltation(np.eye(4), fm, fp, n)
        reduced = saltation_identity_reset(fm, fp, n)
        assert np.allclose(general, reduced, atol=1e-12)


def test_saltation_sign_convention_matrix_form():
    # Xi = I + (f^+ - f^-) n^T / (n^T f^-)  -- outer product with n^T.
    rng = np.random.default_rng(7)
    n = rng.normal(size=4)
    fm = rng.normal(size=4)
    fp = rng.normal(size=4)
    denom = float(n @ fm)
    if abs(denom) < 1e-6:
        pytest.skip("degenerate denominator")
    xi = saltation_identity_reset(fm, fp, n)
    expected = np.eye(4) + np.outer(fp - fm, n) / denom
    assert np.allclose(xi, expected, atol=1e-12)


def test_saltation_grazing_denominator_guard():
    n = np.array([1.0, 0.0, 0.0, 0.0])
    fm = np.array([0.0, 1.0, 0.0, 0.0])   # n^T f^- = 0 (grazing)
    fp = np.array([0.0, 1.0, 0.0, 0.0])
    with pytest.raises(FloatingPointError):
        saltation_identity_reset(fm, fp, n)


# ---------------------------------------------------------------------------
# 15. Event-time convention
# ---------------------------------------------------------------------------
def test_event_time_sign_convention():
    # For a transverse event with n^T f^- > 0, a positive pre-event
    # perturbation along n delays/states the crossing consistently with
    # delta t_e = - (n^T dx^-)/(n^T f^-).
    n = np.array([1.0, 0.0, 0.0, 0.0])
    f_minus = np.array([50.0, 7000.0, 0.0, 0.0])   # dh/dt = 50 m/s
    dx = np.array([1.0, 0.0, 0.0, 0.0])            # 1 m too high on G
    dt = event_time_first_order(dx, f_minus, n)
    assert dt == pytest.approx(-1.0 / 50.0, abs=1e-12)


def test_event_time_first_order_consistency():
    # First-order identity: g(x_e + f_minus*dt_e + dx) ≈ g(x_e) to first
    # order with dt_e from the frozen formula.
    rng = np.random.default_rng(3)
    n = rng.normal(size=4)
    f_minus = rng.normal(size=4)
    dx = rng.normal(size=4) * 1e-6
    denom = float(n @ f_minus)
    if abs(denom) < 1e-8:
        pytest.skip("degenerate denominator")
    dt = event_time_first_order(dx, f_minus, n)
    g_lin = float(n @ (f_minus * dt + dx))
    assert g_lin == pytest.approx(0.0, abs=1e-12)


def test_event_time_grazing_guard():
    n = np.array([1.0, 0.0, 0.0, 0.0])
    f_minus = np.array([0.0, 1.0, 0.0, 0.0])
    dx = np.array([1.0, 0.0, 0.0, 0.0])
    with pytest.raises(FloatingPointError):
        event_time_first_order(dx, f_minus, n)


# ---------------------------------------------------------------------------
# 16. Grazing policy
# ---------------------------------------------------------------------------
def test_interface_crossing_rate_diagnostic():
    state = np.array([6.4e6, 0.0, 7000.0, 0.022], dtype=float)
    # n^T f^- = dh/dt = v sin(gamma)
    assert interface_crossing_rate(state) == pytest.approx(
        7000.0 * np.sin(0.022)
    )


def test_grazing_classification_requires_threshold():
    # G0 freezes classification logic but NOT the numeric threshold.
    with pytest.raises(TypeError):
        classify_transversality(5.0)


def test_grazing_classification_logic():
    assert classify_transversality(5.0, threshold=1.0) == (
        GrazingRegime.TRANSVERSE
    )
    assert classify_transversality(0.5, threshold=1.0) == (
        GrazingRegime.GRAZING_ADJACENT
    )
    assert classify_transversality(0.0, threshold=1.0) == (
        GrazingRegime.GRAZING_NONTRANSVERSE
    )
    assert classify_transversality(1.0, threshold=1.0) == (
        GrazingRegime.TRANSVERSE
    )


# ---------------------------------------------------------------------------
# 17. State-scaling convention sanity (pure algebra, no STM)
# ---------------------------------------------------------------------------
def test_scaling_candidates_positive_and_complete():
    for cand in SCALING_CANDIDATES:
        for k in ("r", "theta", "v", "gamma"):
            assert cand.scales[k] > 0.0
            assert cand.units[k] in ("m", "rad", "m/s")
    assert len(SCALING_CANDIDATES) == 3


def test_scaling_status_flags():
    # The CONVENTION was frozen at G0; the explicitly-deferred NUMERIC
    # canonical scale was resolved (frozen = Candidate A) by G5 after the
    # A/B/C audit (G5 §10) -- see test_phase_g5_metrics.py.
    assert CANONICAL_SCALING_STATUS == SCALING_CONVENTION_DEFINED
    assert CANONICAL_SCALE_NUMERIC_STATUS == (
        CANONICAL_SCALE_NUMERIC_VALUES_FROZEN
    )


def test_scaled_stm_identity_invariance():
    scales = canonical_candidate().scales
    out = identity_scaled_stm(scales)
    assert np.allclose(out, np.eye(4))


def test_scaled_stm_spectrum_invariance():
    rng = np.random.default_rng(11)
    phi = rng.normal(size=(4, 4))
    assert spectrum_invariance(phi, canonical_candidate().scales)


def test_raw_dim_singular_values_not_scale_invariant():
    # Documents why raw dimensional STM singular values are meaningless:
    # a purely off-diagonal coupling A[0,1]=1000 (mixing r-scale and
    # theta-scale) has sigma_max = 1000, but after the frozen scaling
    # S^-1 A S the entry (and its top singular value) is rescaled by
    # s_theta/s_r -- a pure unit-scaling artefact, not physics.
    a = np.zeros((4, 4))
    a[0, 1] = 1000.0
    raw, sa, sb = singular_value_non_invariance(
        a, SCALING_CANDIDATES[0].scales, SCALING_CANDIDATES[1].scales
    )
    assert raw[0] == pytest.approx(1000.0)
    # Eigenvalues are similarity-invariant (all zero here).
    scaled_a = scaled_stm(a, SCALING_CANDIDATES[0].scales)
    assert np.allclose(
        np.sort_complex(np.linalg.eigvals(scaled_a)),
        np.sort_complex(np.linalg.eigvals(a)),
    )
    # Singular values are NOT invariant under re-scaling.
    expected_A = 1000.0 * SCALING_CANDIDATES[0].scales["theta"] / (
        SCALING_CANDIDATES[0].scales["r"]
    )
    expected_B = 1000.0 * SCALING_CANDIDATES[1].scales["theta"] / (
        SCALING_CANDIDATES[1].scales["r"]
    )
    assert sa[0] == pytest.approx(expected_A)
    assert sb[0] == pytest.approx(expected_B)
    assert not np.allclose(raw, sa)
    assert not np.allclose(raw, sb)


def test_scaled_stm_formula_explicit():
    # Diagonal matrices are invariant under diagonal similarity:
    # S^-1 diag(d) S = diag(d).  The convention formula must reflect this.
    phi = np.diag([2.0, 3.0, 4.0, 5.0])
    scales = {"r": 2.0, "theta": 3.0, "v": 4.0, "gamma": 5.0}
    out = scaled_stm(phi, scales)
    assert np.allclose(out, phi)


# ---------------------------------------------------------------------------
# 18. FTLE definition frozen
# ---------------------------------------------------------------------------
def test_ftle_definition_frozen():
    # Identity map -> lambda_max = 0 for ANY positive horizon.
    scales = canonical_candidate().scales
    ident = scaled_stm(np.eye(4), scales)
    for T in (100.0, 723.037965, 1119.545984):
        assert finite_time_lyapunov_exponent(ident, T) == pytest.approx(
            0.0, abs=1e-15
        )
    # Definition form: (1/T) ln(sigma_max) for a concrete 2x dilation.
    phi2 = np.diag([2.0, 1.0, 1.0, 1.0])
    scaled = scaled_stm(phi2, canonical_candidate().scales)
    lam = finite_time_lyapunov_exponent(scaled, 10.0)
    assert lam == pytest.approx(np.log(2.0) / 10.0, abs=1e-12)


def test_ftle_horizon_guard():
    with pytest.raises(ValueError):
        finite_time_lyapunov_exponent(np.eye(4), 0.0)


# ---------------------------------------------------------------------------
# 19. Error taxonomy + topology gate
# ---------------------------------------------------------------------------
def test_error_taxonomy_vocabulary():
    values = {c.value for c in ValidationErrorCategory}
    assert {
        "PHYSICS_SEMANTICS_ERROR",
        "NUMERICAL_ERROR",
        "TOPOLOGY_CHANGE",
        "EVENT_ORDER_CHANGE",
        "GRAZING_CROSSING",
        "LINEARIZATION_BREAKDOWN",
    } <= values


def test_topology_gate_vocabulary():
    values = {g.value for g in TopologyGateResult}
    assert {
        "TOPOLOGY_PRESERVED",
        "TOPOLOGY_CHANGED",
        "EVENT_ORDER_CHANGED",
        "GRAZING_CROSSED",
        "NUMERICAL_FAILURE",
    } <= values


# ---------------------------------------------------------------------------
# 20. Claim boundaries
# ---------------------------------------------------------------------------
def test_forbidden_claims_present():
    payload = machine_readable_protocol()
    for claim in FORBIDDEN_CLAIMS:
        assert claim in payload["forbidden_claims"]
    assert "finite-time local predictability" in payload["scope_statement"]


def test_scope_boundaries():
    payload = machine_readable_protocol()
    scope = payload["scope_statement"]
    for term in ("asymptotic chaos", "global stability", "probabilistic"):
        assert term in scope


# ---------------------------------------------------------------------------
# 21. Machine-readable protocol payload
# ---------------------------------------------------------------------------
def test_protocol_payload_json_serializable():
    payload = machine_readable_protocol()
    json.dumps(payload)                     # must not raise
    assert payload["protocol_version"] == "phase-g-predictability-protocol-v1"
    assert payload["state_order"] == ["r", "theta", "v", "gamma"]
    assert len(payload["event_taxonomy"]) == 7


def test_protocol_core_fields_present():
    payload = machine_readable_protocol()
    for field in (
        "state_order",
        "state_units",
        "perturbation_scope",
        "event_taxonomy",
        "saltation_convention",
        "event_time_convention",
        "ftle_definition",
        "grazing_policy",
        "representative_cases",
        "grazing_anchors",
        "reference_solver_policy",
        "validation_categories",
        "topology_gate",
        "forbidden_claims",
        "scope_statement",
        "g0_status",
    ):
        assert field in payload


# ---------------------------------------------------------------------------
# 22. Taxonomy cross-checks the FROZEN event factories
# ---------------------------------------------------------------------------
def test_taxonomy_crosschecks_frozen_factories():
    assert crosscheck_frozen_factories() == []


def test_taxonomy_registry_lookup():
    names = {e.event for e in EVENT_TAXONOMY}
    assert names == {
        "qian_capture",
        "qian_rti",
        "sanger_atmosphere_exit",
        "sanger_atmosphere_entry",
        "sanger_atmospheric_pullout",
        "sanger_vac_apogee",
        "sanger_srti",
    }
    with pytest.raises(KeyError):
        event_by_name("does_not_exist")


# ---------------------------------------------------------------------------
# 23. G0 status flags: no G1 computation implemented
# ---------------------------------------------------------------------------
def test_g0_status_flags():
    payload = machine_readable_protocol()["g0_status"]
    assert payload["g0_complete"] is True
    assert payload["g1_started"] is False
    assert payload["continuous_jacobian_implemented"] is False
    assert payload["variational_solver_implemented"] is False
    assert payload["hybrid_stm_implemented"] is False
    assert payload["saltation_implemented"] is False
    assert payload["production_ftle_computed"] is False
    assert payload["monte_carlo_performed"] is False
    assert payload["optimization_performed"] is False


def test_placeholder_g1_modules_stay_empty():
    """Phase-stage guard (minimal G5 update).

    ``jacobian``/``stm`` were activated by G1, ``perturbation`` by G2,
    ``saltation`` by G3, ``hybrid_stm``/``hybrid_validation`` by G4, and
    ``ftle``/``metrics``/``terminal_sensitivity`` by G5.  The remaining
    G6+ placeholder module must still contain no executable logic.
    """
    import importlib.util

    for mod in ("observability",):
        spec = importlib.util.find_spec(f"hyptraj.predictability.{mod}")
        assert spec is not None, f"placeholder module {mod} missing"
        # Placeholders must contain no executable predictability logic.
        source = Path(spec.origin).read_text(encoding="utf-8")
        assert source.strip() == "", (
            f"G6+ placeholder {mod} must remain empty (activated through G5)"
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _run_sanger(base, gamma0_deg=-5.0, k=3.0):
    env, veh, _ini, _ctl = base
    ini = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=gamma0_deg,
        range_angle=0.0,
    )
    return _run_sanger_at(env, veh, ini, ConstantKControl(k))


def _run_sanger_at(env, veh, ini, control):
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    return integrate_sanger_research_trajectory(env, veh, ini, control)