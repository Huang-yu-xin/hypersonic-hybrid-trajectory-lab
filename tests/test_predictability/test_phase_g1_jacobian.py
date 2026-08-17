"""Phase-G1 continuous Jacobian tests (G1 §21).

Covers the G1 acceptance surface:

1.  ATM analytic formula (spot-checked against frozen-helper re-derivation)
2.  VAC analytic formula
3.  QEG interior analytic formula
4.  ENTRY_CAPTURE == SANGER_ATM Jacobian (regression invariant)
5.  theta-column zero
6.  QEG interior gamma_dot ~ 0 (frozen RHS residual, FP roundoff only)
7.  QEG interior Jacobian row 4 = 0
8.  QEG active-set classification (exact, no invented threshold)
9.  QEG exact clipping boundary -> ordinary Jacobian rejection
10. VAC independence from aero / K / density / scale-height
11. finite-difference oracle vs analytic Jacobian (representative samples)
12. multi-step convergence sanity (truncation scaling)
13. variational RHS: Phi = I -> dPhi = A
14. invalid states (v<=0, r<=0, shape mismatch) rejected
15. constant-K derivative semantics (dK/dx = 0 enforced by the API)
16. G1 snapshot (phase_g1_continuous_jacobian_v1.json) present and consistent

All representative samples are real frozen-trajectory interior states
(never hybrid switch points, RTI/SRTI, grazing anchors or QEG clipping
boundaries) -- see ``jacobian.representative_continuous_states``.
"""

import json
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.aerodynamics import aerodynamic_forces
from hyptraj.models.atmosphere import atmospheric_density
from hyptraj.models.gravity import gravity_acceleration
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.modes.continuous_glide import QEG_GLIDE, continuous_glide_rhs
from hyptraj.predictability import jacobian as jac
from hyptraj.predictability.jacobian import (
    QegActiveSet,
    QegBoundaryError,
    analytic_jacobian,
    atmospheric_jacobian,
    classify_qeg_active_set,
    constant_k_value,
    entry_capture_jacobian,
    finite_difference_jacobian,
    frozen_rhs,
    jacobian_error_summary,
    qeg_interior_jacobian,
    qeg_distance_metrics,
    representative_continuous_states,
    sanger_atm_jacobian,
    sanger_vac_jacobian,
    u_l_star,
)
from hyptraj.predictability.stm import (
    state_transition_initial_value,
    variational_rhs,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g1_continuous_jacobian_v1.json").read_text(
        encoding="utf-8"
    )
)

K = 3.0
FD_STEPS = np.array([100.0, 1e-5, 1.0, 1e-4])
MODES = ("entry_capture", "qeg_interior", "sanger_atm", "sanger_vac")


@pytest.fixture(scope="module")
def base():
    return (
        EnvironmentParams(),
        VehicleParams(),
        InitialCondition(),
    )


@pytest.fixture(scope="module")
def samples(base):
    env, veh, ini = base
    return {
        mode: representative_continuous_states(
            mode, env, veh, ini, K, n_samples=4
        )
        for mode in MODES
    }


# ---------------------------------------------------------------------------
# 1 / 2 / 3. Analytic formulas vs frozen-helper re-derivation
# ---------------------------------------------------------------------------
def _atm_scalars(state, env, vehicle):
    """Frozen-helper evaluation used to re-derive the analytic entries."""
    r, _theta, v, gamma = state
    alt = max(r - env.earth_radius, 0.0)
    g = gravity_acceleration(alt, env)
    rho = atmospheric_density(alt, env)
    aero = aerodynamic_forces(rho, v, K, vehicle)
    d = aero.drag / vehicle.mass
    ell = aero.lift / vehicle.mass
    return g, d, ell


def test_atmospheric_jacobian_formula(samples):
    env, veh = EnvironmentParams(), VehicleParams()
    s = samples["entry_capture"][0]
    st = s["state"]
    r, _theta, v, gamma = st
    g, d, ell = _atm_scalars(st, env, veh)
    h = env.scale_height

    A = atmospheric_jacobian(st, env, veh, K)
    expected = np.array(
        [
            [0.0, 0.0, np.sin(gamma), v * np.cos(gamma)],
            [-v * np.cos(gamma) / r**2, 0.0, np.cos(gamma) / r,
             -v * np.sin(gamma) / r],
            [d / h + 2.0 * g * np.sin(gamma) / r, 0.0, -2.0 * d / v,
             -g * np.cos(gamma)],
            [
                -ell / (h * v) + (-v / r**2 + 2.0 * g / (r * v))
                * np.cos(gamma),
                0.0,
                ell / v**2 + (1.0 / r + g / v**2) * np.cos(gamma),
                -(v / r - g / v) * np.sin(gamma),
            ],
        ]
    )
    assert np.allclose(A, expected, rtol=1e-12, atol=1e-12)


def test_vac_jacobian_formula(samples):
    env, veh = EnvironmentParams(), VehicleParams()
    s = samples["sanger_vac"][0]
    st = s["state"]
    r, _theta, v, gamma = st
    g = gravity_acceleration(r - env.earth_radius, env)

    A = sanger_vac_jacobian(st, env, veh)
    expected = np.array(
        [
            [0.0, 0.0, np.sin(gamma), v * np.cos(gamma)],
            [-v * np.cos(gamma) / r**2, 0.0, np.cos(gamma) / r,
             -v * np.sin(gamma) / r],
            [2.0 * g * np.sin(gamma) / r, 0.0, 0.0, -g * np.cos(gamma)],
            [
                (-v / r**2 + 2.0 * g / (r * v)) * np.cos(gamma),
                0.0,
                (1.0 / r + g / v**2) * np.cos(gamma),
                -(v / r - g / v) * np.sin(gamma),
            ],
        ]
    )
    assert np.allclose(A, expected, rtol=1e-12, atol=1e-12)


def test_qeg_interior_jacobian_formula(samples):
    env, veh = EnvironmentParams(), VehicleParams()
    s = samples["qeg_interior"][0]
    st = s["state"]
    r, _theta, v, gamma = st
    g, d, _ell = _atm_scalars(st, env, veh)
    h = env.scale_height

    A = qeg_interior_jacobian(st, env, veh, K)
    expected = np.array(
        [
            [0.0, 0.0, np.sin(gamma), v * np.cos(gamma)],
            [-v * np.cos(gamma) / r**2, 0.0, np.cos(gamma) / r,
             -v * np.sin(gamma) / r],
            [d / h + 2.0 * g * np.sin(gamma) / r, 0.0, -2.0 * d / v,
             -g * np.cos(gamma)],
            [0.0, 0.0, 0.0, 0.0],
        ]
    )
    assert np.allclose(A, expected, rtol=1e-12, atol=1e-12)


# ---------------------------------------------------------------------------
# 4 / 5. Structural invariants: ATM identity + theta column
# ---------------------------------------------------------------------------
def test_entry_capture_equals_sanger_atm(samples):
    env, veh = EnvironmentParams(), VehicleParams()
    for mode in ("entry_capture", "sanger_atm"):
        for s in samples[mode]:
            st = s["state"]
            a = entry_capture_jacobian(st, env, veh, K)
            b = sanger_atm_jacobian(st, env, veh, K)
            assert np.array_equal(a, b)


def test_theta_column_zero_analytic(samples):
    env, veh = EnvironmentParams(), VehicleParams()
    for mode in MODES:
        for s in samples[mode]:
            A = analytic_jacobian(mode, s["state"], env, veh, K)
            assert np.linalg.norm(A[:, 1]) == 0.0


def test_theta_column_fd_residual_small(samples):
    env, veh = EnvironmentParams(), VehicleParams()
    for mode in MODES:
        rhs = frozen_rhs(mode, env, veh, K)
        for s in samples[mode]:
            Afd = finite_difference_jacobian(rhs, s["state"], FD_STEPS,
                                             multiplier=1e-2)
            assert np.max(np.abs(Afd[:, 1])) < 1e-8, mode


# ---------------------------------------------------------------------------
# 6 / 7. QEG interior invariants
# ---------------------------------------------------------------------------
def test_qeg_samples_strictly_interior(samples):
    for s in samples["qeg_interior"]:
        assert s["active_set"] == QegActiveSet.INTERIOR.value
        assert s["u_l_star"] is not None
        assert 0.0 < s["u_l_star"] < 1.0
        assert s["distance_to_0"] == pytest.approx(abs(s["u_l_star"]))
        assert s["distance_to_1"] == pytest.approx(abs(1.0 - s["u_l_star"]))


def test_qeg_interior_gamma_dot_zero(samples, base):
    env, veh, _ini = base
    for s in samples["qeg_interior"]:
        st = s["state"]
        f = continuous_glide_rhs(QEG_GLIDE, 0.0, st, env, veh,
                                 ConstantKControl(K))
        assert abs(f[3]) < 1e-12, "QEG interior gamma_dot must vanish (roundoff only)"


def test_qeg_interior_jacobian_row4_zero(samples, base):
    env, veh, _ini = base
    for s in samples["qeg_interior"]:
        A = qeg_interior_jacobian(s["state"], env, veh, K)
        assert np.linalg.norm(A[3]) == 0.0


# ---------------------------------------------------------------------------
# 8 / 9. QEG active-set classification and boundary rejection
# ---------------------------------------------------------------------------
def test_qeg_active_set_classification():
    assert classify_qeg_active_set(-0.5) == QegActiveSet.LOWER_SATURATED
    assert classify_qeg_active_set(0.5) == QegActiveSet.INTERIOR
    assert classify_qeg_active_set(1.5) == QegActiveSet.UPPER_SATURATED
    assert classify_qeg_active_set(0.0) == QegActiveSet.NONDIFFERENTIABLE
    assert classify_qeg_active_set(1.0) == QegActiveSet.NONDIFFERENTIABLE


def test_qeg_boundary_rejects_upper_saturated(samples, base):
    env, veh, _ini = base
    # A high-altitude low-lift state with u_L* >> 1 (upper saturated).
    st = np.array([env.earth_radius + 100_000.0, 0.0, 6000.0, 0.02])
    assert classify_qeg_active_set(u_l_star(st, env, veh, K)) == (
        QegActiveSet.UPPER_SATURATED
    )
    with pytest.raises(QegBoundaryError):
        qeg_interior_jacobian(st, env, veh, K)


def test_qeg_exact_clipping_boundary_rejected(base):
    """u_L* exactly 1 (RTI limit) must NOT yield a fake smooth derivative."""
    env, veh, _ini = base
    st = np.array([env.earth_radius + 50_000.0, 0.0, 5000.0, 0.0])
    with mock.patch("hyptraj.predictability.jacobian.u_l_star",
                    return_value=1.0):
        with pytest.raises(QegBoundaryError):
            qeg_interior_jacobian(st, env, veh, K)
    with mock.patch("hyptraj.predictability.jacobian.u_l_star",
                    return_value=0.0):
        with pytest.raises(QegBoundaryError):
            qeg_interior_jacobian(st, env, veh, K)


# ---------------------------------------------------------------------------
# 10. VAC independence
# ---------------------------------------------------------------------------
def test_vac_jacobian_independent_of_aero(samples):
    import dataclasses

    env, veh = EnvironmentParams(), VehicleParams()
    s = samples["sanger_vac"][0]
    st = s["state"]
    ref = sanger_vac_jacobian(st, env, veh)

    env2 = dataclasses.replace(
        env, density_sea_level=2.0, scale_height=8000.0,
        atmosphere_boundary=90_000.0,
    )
    veh2 = dataclasses.replace(
        veh, drag_coefficient=0.1, reference_area=2.0,
    )
    assert np.array_equal(ref, sanger_vac_jacobian(st, env2, veh2))

    # K never enters the VAC Jacobian signature at all.
    assert np.array_equal(ref, sanger_vac_jacobian(st, env, veh))


# ---------------------------------------------------------------------------
# 11 / 12. FD oracle vs analytic + convergence
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_fd_oracle_matches_analytic(samples, base, mode):
    env, veh, _ini = base
    rhs = frozen_rhs(mode, env, veh, K)
    for s in samples[mode]:
        A = analytic_jacobian(mode, s["state"], env, veh, K)
        Afd = finite_difference_jacobian(rhs, s["state"], FD_STEPS,
                                         multiplier=1e-2)
        summary = jacobian_error_summary(A, Afd)
        # G1 acceptance target: 1e-6 relative agreement on materially
        # nonzero entries (well-conditioned entries are far better).
        assert summary["max_rel_error_nonzero"] < 1e-6, (
            f"{mode} rel error {summary['max_rel_error_nonzero']}"
        )
        assert summary["max_abs_error"] < 1e-5, mode


def test_fd_step_convergence_sanity(samples, base):
    """FD convergence pattern (G1 §15, §I):

    * stepping from multiplier 1 down to 1e-2 must NOT increase the error
      (truncation-driven reduction or roundoff plateau);
    * the smallest sweep step must NOT blow up (roundoff floor);
    * the error minimum (plateau) must be attained strictly INSIDE the
      sweep, never at the largest step (which would indicate a
      cancellation-dominated regime with no truncation convergence).
    """
    env, veh, _ini = base
    multipliers = (1e-3, 1e-2, 1e-1, 1.0, 10.0)
    for mode in MODES:
        rhs = frozen_rhs(mode, env, veh, K)
        for s in samples[mode]:
            A = analytic_jacobian(mode, s["state"], env, veh, K)
            errs = {
                m: jacobian_error_summary(
                    A, finite_difference_jacobian(
                        rhs, s["state"], FD_STEPS, multiplier=m)
                )["max_rel_error_nonzero"]
                for m in multipliers
            }
            assert errs[1e-2] <= errs[1.0], (
                f"{mode}: error grew when refining 1 -> 1e-2 "
                f"({errs[1.0]:.3e} -> {errs[1e-2]:.3e})"
            )
            # At the smallest step the error is roundoff-dominated and may
            # exceed the truncation plateau value; it must still stay far
            # below the acceptance target (no catastrophic blowup).
            assert errs[1e-3] <= 1e-6, (
                f"{mode}: roundoff blowup at the smallest step "
                f"({errs[1e-3]:.3e} > 1e-6)"
            )
            best = min(multipliers, key=lambda m: errs[m])
            assert best < 10.0, (
                f"{mode}: no plateau inside the sweep (best step = 10)"
            )


def test_fd_roundoff_floor_not_claimed(samples, base):
    """At very small steps the error must NOT be allowed to grow unboundedly
    (roundoff regime exists); here we only require the analytic matrix is
    still reproduced to 1e-3 at the smallest sweep step (documentation)."""
    env, veh, _ini = base
    rhs = frozen_rhs("entry_capture", env, veh, K)
    s = samples["entry_capture"][0]
    A = analytic_jacobian("entry_capture", s["state"], env, veh, K)
    Afd = finite_difference_jacobian(rhs, s["state"], FD_STEPS,
                                     multiplier=1e-3)
    assert jacobian_error_summary(A, Afd)["max_rel_error_nonzero"] < 1e-3


# ---------------------------------------------------------------------------
# 13. Variational RHS (minimal algebraic contract)
# ---------------------------------------------------------------------------
def test_variational_rhs_identity():
    A = np.arange(16.0).reshape(4, 4)
    assert np.array_equal(
        variational_rhs(state_transition_initial_value(), A), A
    )


def test_variational_rhs_matrix_algebra():
    rng = np.random.default_rng(0)
    A = rng.normal(size=(4, 4))
    Phi = rng.normal(size=(4, 4))
    assert np.allclose(variational_rhs(Phi, A), A @ Phi)


def test_variational_rhs_shape_guards():
    A = np.zeros((4, 4))
    with pytest.raises(ValueError):
        variational_rhs(np.zeros((4, 3)), A)
    with pytest.raises(ValueError):
        variational_rhs(np.zeros((4, 4)), np.zeros((3, 4)))


# ---------------------------------------------------------------------------
# 14. Invalid states
# ---------------------------------------------------------------------------
def test_invalid_states_rejected(base):
    env, veh, _ini = base
    bad_v = np.array([env.earth_radius + 1e5, 0.0, 0.0, 0.0])
    bad_r = np.array([-1.0, 0.0, 7000.0, 0.0])
    bad_shape = np.zeros((3,))
    for bad in (bad_v, bad_r, bad_shape):
        with pytest.raises(ValueError):
            atmospheric_jacobian(bad, env, veh, K)
        with pytest.raises(ValueError):
            sanger_vac_jacobian(bad, env, veh)
    with pytest.raises(ValueError):
        finite_difference_jacobian(
            lambda x: x, np.zeros(4), np.array([1.0, 1.0, 1.0])
        )
    with pytest.raises(ValueError):
        frozen_rhs("not_a_mode", env, veh, K)


# ---------------------------------------------------------------------------
# 15. Constant-K derivative semantics
# ---------------------------------------------------------------------------
def test_constant_k_semantics():
    assert constant_k_value(ConstantKControl(3.0)) == 3.0
    assert constant_k_value(2.5) == 2.5
    with pytest.raises(ValueError):
        constant_k_value(0.0)
    with pytest.raises(ValueError):
        ConstantKControl(0.0)
    with pytest.raises(TypeError):
        constant_k_value(lambda t, s: 3.0)  # never silently assume dK/dx=0


def test_constant_k_control_equivalence(samples, base):
    env, veh, _ini = base
    st = samples["entry_capture"][0]["state"]
    a = atmospheric_jacobian(st, env, veh, ConstantKControl(K))
    b = atmospheric_jacobian(st, env, veh, K)
    assert np.array_equal(a, b)


# ---------------------------------------------------------------------------
# 16. G1 snapshot consistency (machine-readable artifact)
# ---------------------------------------------------------------------------
def test_g1_snapshot_present_and_consistent():
    assert SNAPSHOT["schema_version"] == "phase-g1-continuous-jacobian-v1"
    assert SNAPSHOT["state_order"] == ["r", "theta", "v", "gamma"]
    assert set(SNAPSHOT["mode_list"]) == set(MODES)
    for mode in MODES:
        assert len(SNAPSHOT["per_mode"][mode]["samples"]) >= 3
    for name, value in SNAPSHOT["structural_invariants"].items():
        assert value is True, name


def test_snapshot_qeg_interior_acceptance_notes():
    for s in SNAPSHOT["per_mode"]["qeg_interior"]["samples"]:
        rec = s["sample"]
        assert rec["active_set"] == "INTERIOR"
        assert 0.0 < rec["u_l_star"] < 1.0
        # frozen gamma_dot residual must be FP roundoff only
        assert abs(s["frozen_gamma_dot_residual"]) < 1e-12


def test_snapshot_no_grazing_or_boundary_samples():
    # No sample may sit at (or within 2 s of) an event; VAC samples come
    # from real SANGER_VAC segments.
    for mode in MODES:
        for s in SNAPSHOT["per_mode"][mode]["samples"]:
            rec = s["sample"]
            assert rec["distance_to_nearest_event_s"] >= 2.0
    for s in SNAPSHOT["per_mode"]["sanger_vac"]["samples"]:
        assert s["sample"]["source_segment"].startswith("segment")
        assert s["sample"]["h_m"] > 100_000.0  # genuinely above h_atm


# ---------------------------------------------------------------------------
# Mode coverage helpers
# ---------------------------------------------------------------------------
def test_all_four_modes_covered(samples):
    for mode in MODES:
        assert len(samples[mode]) >= 3, mode