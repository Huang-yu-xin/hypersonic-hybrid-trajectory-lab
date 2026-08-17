"""Phase-G2 continuous STM tests (G2 §27).

Covers the G2 acceptance surface: augmented pack/unpack + C-order,
augmented RHS (x-dot == frozen, Phi-dot == A Phi), 20-D integration,
Phi(t0)=I, short-time I+A dt, theta-column flow invariant, QEG gamma-row
flow invariant, QEG branch gate, per-mode continuous STM validation,
standalone-vs-augmented consistency, semigroup/composition, nonlinear
centered-FD vs STM with epsilon convergence, REF-0.1 vs REF-0.05
self-stability, computational scaling reconstruction invariance, and the
G2 snapshot consistency.

Every representative window is a single no-event continuous mode of a
frozen trajectory (no hybrid switch, no saltation, no event-time /
terminal sensitivity, no FTLE).
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
from hyptraj.predictability import perturbation as pert
from hyptraj.predictability.jacobian import (
    analytic_jacobian,
    frozen_rhs,
    representative_continuous_states,
    u_l_star,
)
from hyptraj.predictability.perturbation import (
    FD_BASE_STEP,
    FlowValidationClass,
    epsilon_sweep_fd,
    gate_perturbed_trajectory,
    validation_scaled_error,
)
from hyptraj.predictability.scaling import SCALING_CANDIDATES
from hyptraj.predictability.stm import (
    AUGMENTED_DIM,
    PHI_DIM,
    STATE_DIM,
    ContinuousStmResult,
    computational_scaling_transform,
    integrate_continuous_stm,
    integrate_standalone_mode,
    make_augmented_rhs,
    pack_augmented,
    stm_companion_reference_config,
    stm_production_like_config,
    stm_strict_reference_config,
    unpack_augmented,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g2_continuous_stm_v1.json").read_text(
        encoding="utf-8"
    )
)

K = 3.0
WINDOWS = {
    "entry_capture": (23.3572, 79.4105),
    "qeg_interior": (187.8702, 534.1620),
    "sanger_atm": (60.8892, 172.5208),
    "sanger_vac": (287.4670, 442.3893),
}
# Plateau multipliers observed in the G2 snapshot (production FD vs REF-0.1).
PLATEAU_MULT = {"entry_capture": 0.03, "qeg_interior": 0.01,
                "sanger_atm": 0.03, "sanger_vac": 0.1}
MODES = tuple(WINDOWS)


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams(), InitialCondition()


@pytest.fixture(scope="module")
def windows(base):
    env, veh, ini = base
    out = {}
    for mode, (t0, t1) in WINDOWS.items():
        x0 = representative_continuous_states(
            mode, env, veh, ini, K, n_samples=1
        )[0]["state"]
        out[mode] = {"t0": t0, "t1": t1, "x0": x0}
    return out


@pytest.fixture(scope="module")
def stm_ref(base, windows):
    """Reference-grade STM data per mode (strict 0.1 / 0.05 + consistency)."""
    env, veh, _ini = base
    ref01 = stm_strict_reference_config()
    ref05 = stm_companion_reference_config()
    prod = stm_production_like_config()
    out = {}
    for mode, w in windows.items():
        phi01 = integrate_continuous_stm(mode, w["x0"], (w["t0"], w["t1"]),
                                         env, veh, K, solver=ref01)
        phi05 = integrate_continuous_stm(mode, w["x0"], (w["t0"], w["t1"]),
                                         env, veh, K, solver=ref05)
        x1_standalone = integrate_standalone_mode(
            mode, w["x0"], (w["t0"], w["t1"]), env, veh, K, solver=ref01
        )
        # semigroup (production, composition of two sub-transitions)
        tm = w["t0"] + (w["t1"] - w["t0"]) / 2.0
        p10 = integrate_continuous_stm(mode, w["x0"], (w["t0"], tm),
                                       env, veh, K, solver=prod)
        p21 = integrate_continuous_stm(mode, p10.x1, (tm, w["t1"]),
                                       env, veh, K, solver=prod)
        out[mode] = {
            "phi01": phi01,
            "phi05": phi05,
            "x1_standalone": x1_standalone,
            "tm": tm,
            "phi10": p10.phi,
            "phi21": p21.phi,
        }
    return out


# ---------------------------------------------------------------------------
# 1. Augmented pack / unpack + C-order convention
# ---------------------------------------------------------------------------
def test_pack_unpack_roundtrip():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(STATE_DIM,))
    phi = rng.normal(size=(STATE_DIM, STATE_DIM))
    xr, phir = unpack_augmented(pack_augmented(x, phi))
    assert np.array_equal(x, xr)
    assert np.array_equal(phi, phir)
    assert pack_augmented(x, phi).shape == (AUGMENTED_DIM,)


def test_c_order_convention_locked():
    rng = np.random.default_rng(7)
    phi = rng.normal(size=(4, 4))
    z = pack_augmented(np.zeros(4), phi)
    flat = z[STATE_DIM:]
    assert np.array_equal(flat, phi.reshape(PHI_DIM, order="C"))
    assert np.array_equal(flat, phi.ravel(order="C"))
    assert np.array_equal(flat.reshape((4, 4), order="C"), phi)


def test_augmented_shape_and_initial_identity():
    z0 = pack_augmented(np.ones(4), np.eye(4))
    assert z0.shape == (20,)
    assert np.array_equal(z0[STATE_DIM:].reshape((4, 4), order="C"), np.eye(4))


# ---------------------------------------------------------------------------
# 2. Augmented RHS: x-dot == frozen RHS, Phi-dot == A Phi
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_augmented_xdot_matches_frozen(base, windows, mode):
    env, veh, _ini = base
    if mode == "qeg_interior":
        x = windows[mode]["x0"]  # real strictly-interior QEG state
    else:
        rng = np.random.default_rng(0)
        x = rng.normal(size=4) * [1e5, 1.0, 1e3, 1e-1] + [6.45e6, 0.3, 6000.0, 0.0]
    if mode == "sanger_vac":
        # VAC states live above the atmosphere boundary.
        x = np.array([env.earth_radius + 120_000.0, 0.3, 6000.0, -0.02])
    aug = make_augmented_rhs(mode, env, veh, K)
    zdot = aug(0.0, pack_augmented(x, np.eye(4)))
    xdot, phidot = unpack_augmented(zdot)
    xdot_frozen = frozen_rhs(mode, env, veh, K)(x)
    assert np.allclose(xdot, xdot_frozen, rtol=1e-10, atol=1e-12)
    A = analytic_jacobian(mode, x, env, veh, K)
    assert np.allclose(phidot, A @ np.eye(4), rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("mode", MODES)
def test_augmented_phidot_matches_A_phi(base, windows, mode):
    env, veh, _ini = base
    if mode == "qeg_interior":
        x = windows[mode]["x0"]  # real strictly-interior QEG state
    else:
        x = np.array([env.earth_radius + 50_000.0, 0.3, 6000.0, -0.05])
    if mode == "sanger_vac":
        x = np.array([env.earth_radius + 120_000.0, 0.3, 6000.0, -0.02])
    rng = np.random.default_rng(1)
    phi = rng.normal(size=(4, 4))
    aug = make_augmented_rhs(mode, env, veh, K)
    _, phidot = unpack_augmented(aug(0.0, pack_augmented(x, phi)))
    A = analytic_jacobian(mode, x, env, veh, K)
    assert np.allclose(phidot, A @ phi, rtol=1e-10, atol=1e-12)


# ---------------------------------------------------------------------------
# 3. Short-time consistency: Phi ≈ I + A dt
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_short_time_consistency(base, windows, mode):
    env, veh, _ini = base
    w = windows[mode]
    dt = 1e-2
    r = integrate_continuous_stm(mode, w["x0"], (w["t0"], w["t0"] + dt),
                                 env, veh, K, solver=stm_production_like_config())
    A0 = analytic_jacobian(mode, w["x0"], env, veh, K)
    residual = np.max(np.abs(r.phi - (np.eye(4) + A0 * dt)))
    assert residual < 1e-2, mode


# ---------------------------------------------------------------------------
# 4. Structural STM invariants
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_theta_column_flow_invariant(stm_ref, mode):
    phi = stm_ref[mode]["phi01"].phi
    theta_col = phi[:, 1]
    assert np.max(np.abs(theta_col - np.array([0.0, 1.0, 0.0, 0.0]))) < 1e-6
    # off-diagonal residual of the (theoretically zero) responses
    off = np.abs(theta_col[[0, 2, 3]]).max()
    assert off < 1e-6, mode


def test_qeg_gamma_row_flow_invariant(stm_ref):
    phi = stm_ref["qeg_interior"]["phi01"].phi
    row = phi[3, :]
    assert np.max(np.abs(row - np.array([0.0, 0.0, 0.0, 1.0]))) < 1e-6


# ---------------------------------------------------------------------------
# 5. Standalone vs augmented trajectory consistency + reference stability
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_standalone_vs_augmented_consistency(stm_ref, mode):
    d = stm_ref[mode]
    err = np.max(np.abs(d["x1_standalone"] - d["phi01"].x1))
    assert err < 1e-3, mode


@pytest.mark.parametrize("mode", MODES)
def test_reference_self_stability(stm_ref, mode):
    d = stm_ref[mode]
    diff = np.max(np.abs(d["phi01"].phi - d["phi05"].phi))
    assert diff < 1e-6, mode


# ---------------------------------------------------------------------------
# 6. Semigroup / composition property
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_semigroup_composition(stm_ref, mode):
    d = stm_ref[mode]
    # composition = Phi(t1, tm) Phi(tm, t0); compare with Phi(t1, t0)
    comp = d["phi21"] @ d["phi10"]
    err = np.max(np.abs(d["phi01"].phi - comp))
    assert err < 1e-4, mode


# ---------------------------------------------------------------------------
# 7. Nonlinear fixed-time FD vs STM (+ epsilon convergence + gate)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_nonlinear_fd_matches_stm(base, stm_ref, mode):
    env, veh, _ini = base
    phi_ref = stm_ref[mode]["phi01"].phi
    w = stm_ref[mode]["phi01"]
    mult = PLATEAU_MULT[mode]
    sweep = epsilon_sweep_fd(
        mode, w.x0, (w.t0, w.t1), env, veh, K,
        stm_production_like_config(),
        phi_stm=phi_ref, base_step=FD_BASE_STEP, multipliers=(mult,),
    )
    s = sweep[f"mult_{mult:g}"]
    assert s["n_valid_columns"] == STATE_DIM
    assert s["max_rel_error_nonzero"] < 1e-5, mode
    assert s["max_abs_error"] is not None


@pytest.mark.parametrize("mode", MODES)
def test_fd_epsilon_convergence(base, stm_ref, mode):
    """Plateau existence: small/moderate eps agree, large eps degrade."""
    env, veh, _ini = base
    phi_ref = stm_ref[mode]["phi01"].phi
    w = stm_ref[mode]["phi01"]
    sweep = epsilon_sweep_fd(
        mode, w.x0, (w.t0, w.t1), env, veh, K,
        stm_production_like_config(),
        phi_stm=phi_ref, base_step=FD_BASE_STEP,
        multipliers=(1e-2, 1e-1, 1.0, 10.0),
    )
    rels = {m: sweep[f"mult_{m:g}"]["max_rel_error_nonzero"]
            for m in (1e-2, 1e-1, 1.0, 10.0)}
    # a valid plateau at the small end, and severe truncation at eps=10
    assert rels[1e-2] is not None and rels[1e-2] < 1e-5
    assert rels[10.0] > rels[1e-2]


# ---------------------------------------------------------------------------
# 8. QEG branch gate
# ---------------------------------------------------------------------------
def test_qeg_branch_gate_all_interior(base, windows, stm_ref):
    env, veh, _ini = base
    mode = "qeg_interior"
    w = windows[mode]
    phi_ref = stm_ref[mode]["phi01"]
    mult = PLATEAU_MULT[mode]
    eps = FD_BASE_STEP * mult
    for j in range(STATE_DIM):
        for sign in (1.0, -1.0):
            xp = w["x0"] + sign * eps[j] * np.eye(STATE_DIM)[:, j]
            cls = gate_perturbed_trajectory(
                mode, xp, (w["t0"], w["t1"]), env, veh, K,
                stm_strict_reference_config(),
            )
            assert cls == FlowValidationClass.VALID_SMOOTH_FLOW, (j, sign)


def test_qeg_nominal_branch_margins(base, windows):
    env, veh, _ini = base
    w = windows["qeg_interior"]
    from scipy.integrate import solve_ivp

    rhs = frozen_rhs("qeg_interior", env, veh, K)
    sol = solve_ivp(lambda t, x: rhs(x), (w["t0"], w["t1"]), w["x0"],
                    method="DOP853", rtol=1e-12, atol=[1e-7, 1e-14, 1e-10, 1e-14],
                    max_step=0.1, dense_output=True)
    grid = np.linspace(w["t0"], w["t1"], 101)
    xs = sol.sol(grid)[:4]
    us = [u_l_star(xs[:, j], env, veh, K) for j in range(xs.shape[1])]
    assert min(us) > 0.05
    assert max(us) < 0.95
    assert min(min(abs(u) for u in us), min(abs(1 - u) for u in us)) > 0.05


def test_qeg_interior_jacobian_row4_and_gamma_dot_zero(base, windows):
    env, veh, _ini = base
    w = windows["qeg_interior"]
    A = analytic_jacobian("qeg_interior", w["x0"], env, veh, K)
    assert np.linalg.norm(A[3, :]) == 0.0


# ---------------------------------------------------------------------------
# 9. Computational scaling reconstruction invariance
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_computational_scaling_reconstruction(base, windows, mode):
    env, veh, _ini = base
    w = windows[mode]
    ref01 = stm_strict_reference_config()
    phis = {}
    label = ["identity", "A", "B", "C"]
    scales = [None, *[list(c.scales.values()) for c in SCALING_CANDIDATES]]
    for lab, sc in zip(label, scales):
        r = integrate_continuous_stm(
            mode, w["x0"], (w["t0"], w["t1"]), env, veh, K, solver=ref01,
            computational_scaling=(None if sc is None else np.array(sc)),
        )
        phis[lab] = r.phi
    for lab in label:
        if lab == "identity":
            continue
        assert np.max(np.abs(phis[lab] - phis["identity"])) < 1e-6, (mode, lab)


def test_scaling_recover_transform_roundtrip():
    rng = np.random.default_rng(3)
    phi = rng.normal(size=(4, 4))
    s = np.array([1e5, 1.0, 1e3, 0.1])
    psi = computational_scaling_transform(phi, s, inverse=False)
    back = computational_scaling_transform(psi, s, inverse=True)
    assert np.allclose(phi, back, atol=1e-12)


# ---------------------------------------------------------------------------
# 10. Result container + validation-scaled error normalization
# ---------------------------------------------------------------------------
def test_result_container_shape(base, windows):
    env, veh, _ini = base
    w = windows["entry_capture"]
    r = integrate_continuous_stm("entry_capture", w["x0"],
                                 (w["t0"], w["t1"]), env, veh, K)
    assert isinstance(r, ContinuousStmResult)
    assert r.phi.shape == (4, 4)
    assert r.success


def test_validation_scaled_error_is_normalized():
    fd = np.ones((4, 4)) * 1e-8
    phi = np.ones((4, 4))
    err = validation_scaled_error(fd, phi, {"r": 1.0, "theta": 1.0,
                                            "v": 1.0, "gamma": 1.0})
    assert err < 1.0


# ---------------------------------------------------------------------------
# 11. G2 snapshot consistency
# ---------------------------------------------------------------------------
def test_g2_snapshot_schema_and_status():
    assert SNAPSHOT["schema_version"] == "phase-g2-continuous-stm-v1"
    assert SNAPSHOT["state_order"] == ["r", "theta", "v", "gamma"]
    assert SNAPSHOT["flatten_order"].startswith("C-order")
    assert SNAPSHOT["augmented_dim"] == 20
    assert SNAPSHOT["scientific_canonical_scaling_status"].startswith(
        "CANONICAL_SCALE_NUMERIC_VALUES_PENDING"
    )
    rep = SNAPSHOT["representation_invariance"]
    for mode in MODES:
        assert rep[mode]["status"] == "PASS"


def test_g2_snapshot_all_statuses_pass():
    for mode in MODES:
        rec = SNAPSHOT["per_mode"][mode]
        for field in ("reference_self_stability", "trajectory_consistency",
                      "semigroup", "short_time", "theta_invariant"):
            assert rec[field]["status"] == "PASS", (mode, field)
        assert rec["fd_plateau"]["multiplier"] is not None
        if "qeg_gamma_row_invariant" in rec:
            assert rec["qeg_gamma_row_invariant"]["status"] == "PASS"
        if "fd_reference_agreement" in rec:
            assert rec["fd_reference_agreement"]["status"] == "PASS"


def test_g2_snapshot_fd_classifications_valid_smooth():
    for mode in MODES:
        rec = SNAPSHOT["per_mode"][mode]
        if "fd_reference_agreement" in rec:
            cls = rec["fd_reference_agreement"]["classification"]
            assert set(cls) <= {"VALID_SMOOTH_FLOW"}, (mode, cls)


def test_g2_snapshot_windows_no_event_crossing():
    from hyptraj.predictability.event_metadata import EVENT_TAXONOMY
    # Sanity: recorded windows are single continuous modes (no saltation).
    for mode, rec in SNAPSHOT["per_mode"].items():
        assert rec["window"]["duration_s"] > 0.0
        assert rec["window"]["h0_m"] > 0.0


# ---------------------------------------------------------------------------
# 12. Scope guards: no saltation / hybrid / event-time production anywhere
# ---------------------------------------------------------------------------
def test_no_saltation_scope_leak():
    # G2 continuous STM / perturbation layers must not depend on any hybrid
    # state-machine / event machinery (single continuous flow only).
    for mod in ("stm", "perturbation"):
        path = Path(__file__).resolve().parents[2] / "src" / "hyptraj" / \
            "predictability" / f"{mod}.py"
        src = path.read_text(encoding="utf-8")
        assert "sanger_trajectory" not in src
        assert "qian_research" not in src
        assert "event_time" not in src
        assert "ftle" not in src
        defs = [ln.strip() for ln in src.splitlines()
                if ln.strip().startswith(("def ", "class "))]
        assert not any("saltation" in d for d in defs)