"""Phase-G3 transverse hybrid saltation tests (G3 §35).

Covers the G3 acceptance surface: saltation / event-time algebra and
guards, exact-zero-denominator rejection, taxonomy eligibility (Qian
Capture, Sanger exit / entry) and exclusion (RTI / SRTI / pullout /
apogee / synthetic initial entry), Qian capture active-set audit, Sanger
metadata crosschecks, structural invariants (Qian diag(1,1,1,0); Sanger
sparse shear + det=1), event-time signs, local root before/after nominal,
synchronized post-event map, multi-epsilon FD convergence, reference
self-stability, and the G3 snapshot consistency.  No grazing anchors, no
G4 scope leak.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability import saltation as S
from hyptraj.predictability.saltation import (
    HybridLocalLinearization,
    LocalEventValidationClass,
    NonTransverseEventError,
    NotHybridSwitchError,
    assert_saltation_eligible,
    event_time_gradient,
    extract_qian_capture,
    extract_sanger_switches,
    identity_reset_saltation,
    local_event_crossing_time,
    saltation_determinant_lemma,
    saltation_matrix,
    synchronized_post_event_map,
    transversality_denominator,
)
from hyptraj.predictability.stm import stm_strict_reference_config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g3_transverse_saltation_v1.json").read_text(
        encoding="utf-8"
    )
)

K = 3.0


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams(), InitialCondition()


@pytest.fixture(scope="module")
def ref():
    return stm_strict_reference_config()


@pytest.fixture(scope="module")
def capture(base, ref):
    env, veh, ini = base
    return extract_qian_capture(env, veh, ini, K, solver=ref)


@pytest.fixture(scope="module")
def switches(base, ref):
    env, veh, ini = base
    return extract_sanger_switches(env, veh, ini, K, solver=ref)


# ---------------------------------------------------------------------------
# 1. Saltation / event-time algebra + guards
# ---------------------------------------------------------------------------
def test_identity_reset_reduction():
    rng = np.random.default_rng(0)
    for _ in range(10):
        n = rng.normal(size=4)
        fm = rng.normal(size=4)
        fp = rng.normal(size=4)
        if abs(n @ fm) < 1e-12:
            continue
        assert np.allclose(
            saltation_matrix(np.eye(4), fm, fp, n),
            identity_reset_saltation(fm, fp, n),
            atol=1e-12,
        )


def test_saltation_matrix_form():
    rng = np.random.default_rng(1)
    n = rng.normal(size=4)
    fm = rng.normal(size=4)
    fp = rng.normal(size=4)
    denom = n @ fm
    xi = identity_reset_saltation(fm, fp, n)
    assert np.allclose(xi, np.eye(4) + np.outer(fp - fm, n) / denom)


def test_event_time_gradient_formula():
    n = np.array([1.0, 0.0, 0.0, 0.0])
    q = event_time_gradient(n, 50.0)
    assert np.allclose(q, -n / 50.0)
    # delta t = q @ delta x  ->  for dx=r-direction positive, dt < 0.
    assert event_time_gradient(n, 50.0)[0] == pytest.approx(-1.0 / 50.0)


def test_transversality_denominator_eval():
    fm = np.array([50.0, 1.0, 0.0, 0.0])
    n = np.array([1.0, 0.0, 0.0, 0.0])
    assert transversality_denominator(fm, n) == pytest.approx(50.0)


def test_shape_finite_guards():
    with pytest.raises(ValueError):
        identity_reset_saltation(np.zeros(3), np.zeros(4), np.zeros(4))
    with pytest.raises(ValueError):
        identity_reset_saltation(
            np.array([1.0, 0.0, 0.0, np.nan]), np.zeros(4), np.zeros(4))
    with pytest.raises(ValueError):
        saltation_matrix(np.zeros((3, 3)), np.zeros(4), np.zeros(4), np.zeros(4))


def test_exact_zero_denominator_rejected():
    # n^T f^- == 0 exactly -> NonTransverseEventError (never inf/nan).
    n = np.array([1.0, 0.0, 0.0, 0.0])
    fm = np.array([0.0, 1.0, 0.0, 0.0])
    fp = np.array([0.0, 1.0, 0.0, 0.0])
    with pytest.raises(NonTransverseEventError):
        identity_reset_saltation(fm, fp, n)
    with pytest.raises(NonTransverseEventError):
        event_time_gradient(n, 0.0)
    with pytest.raises(NonTransverseEventError):
        saltation_determinant_lemma(fm, fp, n)
    # Cleanup: no inf/nan leaks anywhere.
    assert np.isfinite(identity_reset_saltation(
        np.array([1.0, 0.0, 0.0, 1.0]), fp, np.array([1.0, 0.0, 0.0, 0.0]))).all()


# ---------------------------------------------------------------------------
# 2. Taxonomy eligibility / exclusion
# ---------------------------------------------------------------------------
def test_eligible_events():
    assert_saltation_eligible("qian_capture")
    assert_saltation_eligible("sanger_atmosphere_exit")
    assert_saltation_eligible("sanger_atmosphere_entry")


def test_excluded_events_no_saltation():
    for name in ("qian_rti", "sanger_srti", "sanger_atmospheric_pullout",
                 "sanger_vac_apogee", "synthetic_initial_entry"):
        with pytest.raises(NotHybridSwitchError):
            assert_saltation_eligible(name)


def test_local_flows_reject_non_hybrid():
    with pytest.raises(NotHybridSwitchError):
        S.local_flows_for("qian_rti", EnvironmentParams(), VehicleParams(), K)


# ---------------------------------------------------------------------------
# 3. Qian Capture audit + structure
# ---------------------------------------------------------------------------
def test_qian_capture_active_set_interior(capture):
    assert capture.metadata["capture_active_set"] == "INTERIOR"
    assert 0.0 < capture.metadata["capture_u_l_star"] < 1.0
    d0 = capture.metadata["distance_to_0"]
    d1 = capture.metadata["distance_to_1"]
    assert d0 == pytest.approx(capture.metadata["capture_u_l_star"])
    assert d1 == pytest.approx(1.0 - capture.metadata["capture_u_l_star"])


def test_qian_capture_structure_diag1110(capture):
    xi = capture.saltation_matrix
    assert np.allclose(xi, np.diag([1.0, 1.0, 1.0, 0.0]), atol=1e-12)
    assert capture.determinant == pytest.approx(0.0, abs=1e-12)
    # determinant lemma: det = n^T f^+ / n^T f^- = gamma_dot^+ / gamma_dot^-
    lemma = saltation_determinant_lemma(
        capture.f_minus, capture.f_plus, capture.normal)
    assert lemma == pytest.approx(0.0, abs=1e-12)
    assert np.linalg.det(xi) == pytest.approx(lemma, abs=1e-12)


def test_qian_capture_denominator_positive(capture):
    # direction +1 -> gamma_dot^- > 0
    assert capture.denominator > 0.0
    # q_gamma = -1/gamma_dot^- < 0 : more positive gamma -> earlier capture
    assert capture.event_time_gradient[3] < 0.0


def test_qian_capture_normal(capture):
    assert np.array_equal(capture.normal, np.array([0.0, 0.0, 0.0, 1.0]))
    assert capture.mode_before == "ENTRY_CAPTURE"
    assert capture.mode_after == "QEG_GLIDE"


# ---------------------------------------------------------------------------
# 4. Sanger event audit + structure
# ---------------------------------------------------------------------------
def test_sanger_switch_set(switches):
    kinds = [w.event_name for w in switches]
    assert kinds.count("sanger_atmosphere_exit") == 2
    assert kinds.count("sanger_atmosphere_entry") == 2


def test_sanger_metadata_crosscheck(switches):
    for w in switches:
        assert w.metadata["f_minus_metadata_abs_err"] < 1e-9
        assert w.metadata["f_plus_metadata_abs_err"] < 1e-9
        assert w.metadata["normal_metadata_match"] is True
        assert np.array_equal(w.normal, np.array([1.0, 0.0, 0.0, 0.0]))


def test_sanger_sparse_shear_structure(switches):
    for w in switches:
        xi = w.saltation_matrix
        # columns 1,2,3 are identity
        assert np.allclose(xi[:, 1], np.array([0.0, 1.0, 0.0, 0.0]), atol=1e-12)
        assert np.allclose(xi[:, 2], np.array([0.0, 0.0, 1.0, 0.0]), atol=1e-12)
        assert np.allclose(xi[:, 3], np.array([0.0, 0.0, 0.0, 1.0]), atol=1e-12)
        # r and theta rows of column 0 are identity/zero
        assert xi[0, 0] == pytest.approx(1.0, abs=1e-12)
        assert xi[1, 0] == pytest.approx(0.0, abs=1e-12)


def test_sanger_determinant_one(switches):
    for w in switches:
        assert w.determinant == pytest.approx(1.0, abs=1e-9)
        lemma = saltation_determinant_lemma(w.f_minus, w.f_plus, w.normal)
        assert lemma == pytest.approx(1.0, abs=1e-9)
        assert np.linalg.det(w.saltation_matrix) == pytest.approx(lemma, abs=1e-9)


def test_sanger_col0_signs(switches):
    for w in switches:
        # v-row positive, gamma-row negative (G3 §32) in the radial column.
        assert w.saltation_matrix[2, 0] > 0.0
        assert w.saltation_matrix[3, 0] < 0.0


def test_sanger_event_time_sign(base, ref):
    env, veh, ini = base
    sws = extract_sanger_switches(env, veh, ini, K, solver=ref)
    for w in sws:
        if w.event_name == "sanger_atmosphere_exit":
            assert w.denominator > 0.0
            assert w.event_time_gradient[0] < 0.0  # larger r -> earlier exit
        else:
            assert w.denominator < 0.0
            assert w.event_time_gradient[0] > 0.0  # larger r -> later entry
        # tangent components (theta/v/gamma) of q have analytic zero.
        for j in (1, 2, 3):
            assert abs(w.event_time_gradient[j]) < 1e-12


# ---------------------------------------------------------------------------
# 5. Local event-time root (before / after nominal)
# ---------------------------------------------------------------------------
def test_local_root_before_and_after(base, ref, capture):
    env, veh, ini = base
    rb, _ = S.local_flows_for("qian_capture", env, veh, K)
    sf = S.event_surface_for("qian_capture", env)
    # +gamma -> crossing earlier (tau < 0)
    tau_p, _, _ = local_event_crossing_time(
        rb, sf, capture.state + np.array([0, 0, 0, 1e-5]), ref)
    # -gamma -> crossing later (tau > 0)
    tau_m, _, _ = local_event_crossing_time(
        rb, sf, capture.state + np.array([0, 0, 0, -1e-5]), ref)
    assert tau_p is not None and tau_p < 0.0
    assert tau_m is not None and tau_m > 0.0
    # linear prediction: tau ~ -delta_gamma / gamma_dot^-
    assert tau_p == pytest.approx(-1e-5 / capture.denominator, rel=1e-3)


def test_local_tangent_zero(base, ref, capture):
    env, veh, ini = base
    rb, _ = S.local_flows_for("qian_capture", env, veh, K)
    sf = S.event_surface_for("qian_capture", env)
    # theta perturbation leaves gamma unchanged -> surface exactly satisfied.
    tau, _, _ = local_event_crossing_time(
        rb, sf, capture.state + np.array([0.0, 1e-5, 0.0, 0.0]), ref)
    assert tau == 0.0


# ---------------------------------------------------------------------------
# 6. Multi-epsilon FD convergence (event-time + saltation local map)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def events(base, ref):
    env, veh, ini = base
    cap = extract_qian_capture(env, veh, ini, K, solver=ref)
    sws = extract_sanger_switches(env, veh, ini, K, solver=ref)
    return [("qian_capture", cap)] + [(w.event_name, w) for w in sws]


@pytest.mark.parametrize("key,expected", [
    ("qian_capture", 1e-5),
    ("sanger_atmosphere_exit", 1e-5),
    ("sanger_atmosphere_entry", 1e-5),
])
def test_event_time_fd_convergence(base, ref, events, key, expected):
    env, veh, ini = base
    lin = next(e for n, e in events if n == key)
    rb, _ = S.local_flows_for(key, env, veh, K)
    sf = S.event_surface_for(key, env)
    sweep = S.event_time_fd_sweep(
        lin, rb, sf, env, veh, K, ref,
        multipliers=(1e-2, 1e-1, 1.0), check_qeg_interior=(key == "qian_capture"))
    for m in ("mult_0.01", "mult_0.1"):
        rec = sweep[m]
        for j in range(4):
            c = rec["columns"][f"col_{j}"]
            assert c["absolute_error"] is not None
            if c["material_relative_error"] is not None:
                assert c["material_relative_error"] < expected, (key, j, m)
            assert c["classification_plus"] == "TRANSVERSE_LOCAL_VALID"
            assert c["classification_minus"] == "TRANSVERSE_LOCAL_VALID"


@pytest.mark.parametrize("key", ["qian_capture", "sanger_atmosphere_exit",
                                 "sanger_atmosphere_entry"])
def test_saltation_local_map_fd_convergence(base, ref, events, key):
    env, veh, ini = base
    lin = next(e for n, e in events if n == key)
    rb, ra = S.local_flows_for(key, env, veh, K)
    sf = S.event_surface_for(key, env)
    sweep = S.saltation_local_map_fd_sweep(
        lin, rb, ra, sf, env, veh, K, ref,
        multipliers=(1e-2, 1e-1), check_qeg_interior=(key == "qian_capture"))
    for m in ("mult_0.01", "mult_0.1"):
        rec = sweep[m]
        for j in range(4):
            c = rec["columns"][f"col_{j}"]
            assert c["absolute_error"] is not None
            if c["material_relative_error"] is not None:
                assert c["material_relative_error"] < 1e-5, (key, j, m)
            assert c["classification_plus"] == "TRANSVERSE_LOCAL_VALID"
            assert c["classification_minus"] == "TRANSVERSE_LOCAL_VALID"


def test_synchronized_map_dm_matches_xi(base, ref, capture):
    env, veh, ini = base
    rb, ra = S.local_flows_for("qian_capture", env, veh, K)
    sf = S.event_surface_for("qian_capture", env)
    # M(0) = x_e
    y0, meta = synchronized_post_event_map(rb, ra, sf, capture.state,
                                           np.zeros(4), ref)
    assert np.allclose(y0, capture.state, atol=1e-12)
    # DM(0) col0 via centered FD (r direction)
    eps = 1.0
    yp, _ = synchronized_post_event_map(rb, ra, sf, capture.state,
                                        np.array([eps, 0.0, 0.0, 0.0]), ref)
    ym, _ = synchronized_post_event_map(rb, ra, sf, capture.state,
                                        np.array([-eps, 0.0, 0.0, 0.0]), ref)
    fd_col0 = (yp - ym) / (2.0 * eps)
    assert np.allclose(fd_col0, capture.saltation_matrix[:, 0], atol=1e-4)


# ---------------------------------------------------------------------------
# 7. Reference self-stability (REF-0.1 vs REF-0.05)
# ---------------------------------------------------------------------------
def test_reference_self_stability(base):
    env, veh, ini = base
    from hyptraj.analysis.comparison_validation import (
        REFERENCE_05_SOLVER_CONFIG, REFERENCE_SOLVER_CONFIG,
    )

    for name in ("qian_capture", "sanger_atmosphere_exit"):
        if name == "qian_capture":
            e01 = extract_qian_capture(env, veh, ini, K, solver=REFERENCE_SOLVER_CONFIG)
            e05 = extract_qian_capture(env, veh, ini, K, solver=REFERENCE_05_SOLVER_CONFIG)
        else:
            e01 = extract_sanger_switches(env, veh, ini, K, solver=REFERENCE_SOLVER_CONFIG)[0]
            e05 = extract_sanger_switches(env, veh, ini, K, solver=REFERENCE_05_SOLVER_CONFIG)[0]
        assert np.max(np.abs(e01.saltation_matrix - e05.saltation_matrix)) < 1e-6


# ---------------------------------------------------------------------------
# 8. Snapshot consistency + scope
# ---------------------------------------------------------------------------
def test_g3_snapshot_schema_and_flags():
    assert SNAPSHOT["schema_version"] == "phase-g3-transverse-saltation-v1"
    assert SNAPSHOT["state_order"] == ["r", "theta", "v", "gamma"]
    assert SNAPSHOT["grazing_anchors_excluded"] is True
    assert SNAPSHOT["grazing_threshold_none_frozen"] is True
    assert set(SNAPSHOT["eligibility"]) == set(S.SALTATION_ELIGIBLE_EVENTS)
    assert "grazing" not in SNAPSHOT  # no numeric grazing threshold frozen


def test_g3_snapshot_reference_convergence_pass():
    for name, e in SNAPSHOT["events"].items():
        assert e["reference_convergence"]["status"] == "PASS", name
        assert e["reference_convergence"]["xi_max_abs_diff_01_05"] < 1e-6


def test_g3_snapshot_structural_results():
    for name, e in SNAPSHOT["events"].items():
        xi = np.array(e["saltation_matrix"], dtype=float)
        det = e["determinant"]
        if name == "qian_capture":
            assert np.allclose(xi, np.eye(4) * [1, 1, 1, 0], atol=1e-12)
            assert det == pytest.approx(0.0, abs=1e-12)
        else:
            assert np.allclose(xi[:, 1], [0, 1, 0, 0], atol=1e-12)
            assert np.allclose(xi[:, 2], [0, 0, 1, 0], atol=1e-12)
            assert np.allclose(xi[:, 3], [0, 0, 0, 1], atol=1e-12)
            assert det == pytest.approx(1.0, abs=1e-6)


def test_g3_snapshot_acceptance_levels():
    for name, e in SNAPSHOT["events"].items():
        et = e["event_time_plateau"]["material_rel_error"]
        sl = e["saltation_plateau"]["material_rel_error"]
        assert et is not None and et < 1e-5, name
        assert sl is not None and sl < 1e-5, name


def test_no_g4_scope_leak():
    # saltation module must not chain continuous STMs or build a hybrid STM.
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "saltation.py").read_text(encoding="utf-8")
    assert "hybrid_stm" not in src
    assert "integrate_continuous_stm" not in src
    assert "variational_rhs" not in src
    # no hybrid_stm module created for G4
    assert not (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
                "predictability" / "hybrid_stm.py").exists()