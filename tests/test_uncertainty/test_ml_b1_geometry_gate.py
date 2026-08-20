"""ML-B1 -- First-Order Geometry Gate tests (brief §25).

Live smoke tests run on the shortest reference-certified anchors
(``B0_N_side`` / ``B1_N_side`` / ``B1_N1_side``) with the frozen REF-0.1
solver so the suite stays fast; the full gate is produced by
``scripts/run_ml_b1_geometry_gate.py`` and locked by the snapshot
regression test at the end of this module.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.predictability.grazing import load_frozen_grazing_anchors
from hyptraj.uncertainty.topology_margin import (
    CHANNEL_ATMOSPHERE_EXIT,
    DEFAULT_P0,
    MarginClassification,
    analytic_margin_gradient,
    evaluate_topology_margin,
    geometry_direction,
    gradient_error_metrics,
    run_exact_topology,
    scaled_fd_margin_gradient,
    _p0_cholesky,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"


def _x0(env: EnvironmentParams, gamma0_deg: float) -> np.ndarray:
    return np.array(
        [
            env.earth_radius + 100000.0,
            0.0,
            7000.0,
            np.deg2rad(gamma0_deg),
        ],
        dtype=float,
    )


@pytest.fixture(scope="module")
def env() -> EnvironmentParams:
    return EnvironmentParams()


@pytest.fixture(scope="module")
def vehicle() -> VehicleParams:
    return VehicleParams()


@pytest.fixture(scope="module")
def anchors():
    return {f"{a.branch}_{a.side}": a for a in load_frozen_grazing_anchors()}


@pytest.fixture(scope="module")
def b0_n(env, anchors):
    a = anchors["B0_N_side"]
    return _x0(env, a.gamma0_deg), a.K, 0


def _evaluate(x0, K, branch_index, env, vehicle, solver_label="REF-0.1", **kw):
    return evaluate_topology_margin(
        x0,
        K=K,
        branch_index=branch_index,
        env=env,
        vehicle=vehicle,
        channel=CHANNEL_ATMOSPHERE_EXIT,
        solver_label=solver_label,
        max_time=1500.0,
        **kw,
    )


# ---------------------------------------------------------------------------
# M1 nominal margin
# ---------------------------------------------------------------------------
class TestNominalMargin:
    def test_b_finite(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        assert rec.classification == MarginClassification.VALID_MARGIN
        assert np.isfinite(rec.b)
        assert rec.b > 0  # N side

    def test_t_star_finite_and_extremum(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        assert rec.t_star is not None and np.isfinite(rec.t_star)
        # critical extremum: dG/dt = v sin(gamma) ~ 0
        assert abs(rec.guard_derivative) < 1e-3

    def test_critical_branch_and_prior_topology(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        assert rec.critical_mode == "SANGER_ATM"
        assert rec.critical_segment_id == 0
        assert rec.exact_regime == "SRTI_N0"
        # prior chart empty for B0 (first pass starts at t = 0)
        assert rec.prior_switch_signature == ()

    def test_critical_switch_not_executed(self, env, vehicle, anchors):
        # B1 N1_side (SRTI_N2): the critical pass is the 2nd atmospheric
        # segment (id 2), which really ends at the critical atmosphere_exit.
        # The prior part (segments 0-1) executed one full excursion (2 true
        # switches); the virtual continuation must NOT execute the critical
        # exit, which is why b < 0 (transition side) with the prior
        # signature preserved.
        a = anchors["B1_N1_side"]
        x0 = _x0(env, a.gamma0_deg)
        rec = _evaluate(x0, a.K, 1, env, vehicle)
        assert rec.classification == MarginClassification.VALID_MARGIN
        assert rec.prior_switch_signature == (
            "sanger_atmosphere_exit",
            "sanger_atmosphere_entry",
        )
        assert rec.critical_segment_id == 2
        assert rec.critical_trigger == "atmosphere_exit"
        assert rec.b < 0

    def test_guard_value_matches_phase_f(self, env, vehicle, anchors):
        # B1 N_side: |b| must agree with the Phase-F certified clearance
        # (b = -phi_F for the atmosphere-exit channel).
        a = anchors["B1_N_side"]
        x0 = _x0(env, a.gamma0_deg)
        rec = _evaluate(x0, a.K, 1, env, vehicle)
        assert rec.b > 0
        assert abs(rec.b - abs(a.phase_f_reference_phi_m)) < 0.05


# ---------------------------------------------------------------------------
# M2 orientation
# ---------------------------------------------------------------------------
class TestOrientation:
    def test_known_nominal_side_positive(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        assert rec.b > 0

    def test_known_transition_side_negative(self, env, vehicle, anchors):
        a = anchors["B1_N1_side"]
        x0 = _x0(env, a.gamma0_deg)
        rec = _evaluate(x0, a.K, 1, env, vehicle)
        assert rec.b < 0

    def test_n_star_is_oriented(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        assert np.allclose(rec.n_star, [-1.0, 0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# M3 repeatability / M4 reference
# ---------------------------------------------------------------------------
class TestRepeatabilityAndReference:
    def test_deterministic_repeatability(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        r1 = _evaluate(x0, K, bi, env, vehicle)
        r2 = _evaluate(x0, K, bi, env, vehicle)
        assert r1.b == pytest.approx(r2.b, rel=1e-12)
        assert r1.t_star == pytest.approx(r2.t_star, rel=1e-12)
        assert np.allclose(r1.x_star, r2.x_star, atol=1e-9)

    def test_ref_0_1_vs_ref_0_05_stable(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        r1 = _evaluate(x0, K, bi, env, vehicle, solver_label="REF-0.1")
        r2 = _evaluate(x0, K, bi, env, vehicle, solver_label="REF-0.05")
        assert r1.classification == r2.classification == MarginClassification.VALID_MARGIN
        assert abs(r1.b - r2.b) < 1e-3
        assert abs(r1.t_star - r2.t_star) < 1e-2


# ---------------------------------------------------------------------------
# Prior-chart guard
# ---------------------------------------------------------------------------
class TestPriorChartGuard:
    def test_regime_change_classified(self, env, vehicle, anchors):
        # B1 N_side pushed along +v_geom (towards the boundary) must flip
        # into SRTI_N2 and be classified instead of returning a margin.
        a = anchors["B1_N_side"]
        x0 = _x0(env, a.gamma0_deg)
        rec = _evaluate(x0, a.K, 1, env, vehicle)
        assert rec.classification == MarginClassification.VALID_MARGIN
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        g = geometry_direction(grad.a_raw, b0=rec.b)
        step = 3.0 * g.beta_local
        pushed = _evaluate(
            x0 + step * g.v_geom, a.K, 1, env, vehicle,
            expected_regime=rec.exact_regime,
            expected_switch_signature=rec.prior_switch_signature,
        )
        assert pushed.classification in (
            MarginClassification.PRIOR_TOPOLOGY_CHANGED,
            MarginClassification.PRIOR_EVENT_ORDER_CHANGED,
        )


# ---------------------------------------------------------------------------
# Analytic gradient (brief §14)
# ---------------------------------------------------------------------------
class TestAnalyticGradient:
    def test_shapes_and_formula(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        assert grad.phi_star.shape == (4, 4)
        assert grad.n_star.shape == (4,)
        assert np.allclose(grad.a_raw, grad.phi_star.T @ grad.n_star)
        # theta symmetry: a[1] ~ 0
        assert abs(grad.a_raw[1]) < 1e-6

    def test_no_critical_grazing_saltation(self, env, vehicle, anchors):
        # B1 N1_side prior has exactly 2 true switches; the critical exit
        # saltation must NOT appear among the prior denominators.
        a = anchors["B1_N1_side"]
        x0 = _x0(env, a.gamma0_deg)
        rec = _evaluate(x0, a.K, 1, env, vehicle)
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        assert len(grad.prior_saltation_denominators) == 2
        assert grad.critical_saltation_excluded

    def test_theta_phi_column_near_zero(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        # d b / d theta0 = 0 by theta-translation symmetry of the Sanger
        # dynamics (theta does not enter r/v/gamma equations).
        assert abs(grad.a_raw[1]) < 1e-6


# ---------------------------------------------------------------------------
# Scaled FD pair gate + analytic-vs-FD (brief §15-§19, light version)
# ---------------------------------------------------------------------------
class TestFdGate:
    # Same-side FD window: the extremal anchors sit at |b| ~ 0.1 m, so a
    # scaled step must stay below ~1e-6 for the margin not to cross the
    # boundary (brief §18 pair gate).  eps = 1e-7 is inside the validated
    # window for B0/B1 N-side anchors.
    FD_EPS = 1e-7

    def test_pair_gate_all_columns(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        fd = scaled_fd_margin_gradient(
            rec, self.FD_EPS, env=env, vehicle=vehicle,
            expected_regime=rec.exact_regime,
            expected_switch_signature=rec.prior_switch_signature,
        )
        assert fd.all_columns_valid
        for col in fd.columns:
            assert col.valid_pair

    def test_analytic_vs_fd_agreement(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        fd = scaled_fd_margin_gradient(
            rec, self.FD_EPS, env=env, vehicle=vehicle,
            expected_regime=rec.exact_regime,
            expected_switch_signature=rec.prior_switch_signature,
        )
        metrics = gradient_error_metrics(grad.a_scaled, fd.gradient)
        assert metrics["cosine_similarity"] > 0.999
        assert metrics["normalized_l2_error"] < 1e-2

    def test_theta_fd_column_noise_level(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        fd = scaled_fd_margin_gradient(
            rec, self.FD_EPS, env=env, vehicle=vehicle,
            expected_regime=rec.exact_regime,
            expected_switch_signature=rec.prior_switch_signature,
        )
        assert abs(fd.columns[1].derivative) < 1e-2


# ---------------------------------------------------------------------------
# Geometry direction (brief §20) + boundary approach (brief §21)
# ---------------------------------------------------------------------------
class TestGeometryDirection:
    def test_algebra_identity(self, env, vehicle, b0_n):
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        g = geometry_direction(grad.a_raw, b0=rec.b)
        assert np.allclose(
            grad.a_raw @ g.v_geom,
            -g.sqrt_aT_P0_a,
            atol=1e-6 * g.sqrt_aT_P0_a,
        )
        assert np.linalg.norm(g.alpha) == pytest.approx(1.0, abs=1e-9)

    def test_tangent_first_order_derivative_near_zero(self, env, vehicle, b0_n):
        # A whitened tangent direction (alpha^T v = 0) has zero first-order
        # margin derivative: a^T (L0 v_u) ~ 0 (algebraic, machine-precision).
        x0, K, bi = b0_n
        rec = _evaluate(x0, K, bi, env, vehicle)
        grad = analytic_margin_gradient(rec, env=env, vehicle=vehicle)
        g = geometry_direction(grad.a_raw, b0=rec.b)
        rng = np.random.default_rng(5)
        v_u = rng.standard_normal(4)
        v_u = v_u - np.dot(v_u, g.alpha) * g.alpha
        v_u = v_u / (np.linalg.norm(v_u) + 1e-300)
        l0 = _p0_cholesky(DEFAULT_P0)
        v_phys = l0 @ v_u
        # first-order directional derivative ~ 0
        assert abs(grad.a_raw @ v_phys) < 1e-4 * grad.sqrt_aT_P0_a
        # while the geometry direction has the maximal first-order decrease
        assert abs(grad.a_raw @ g.v_geom - (-grad.sqrt_aT_P0_a)) < 1e-6 * grad.sqrt_aT_P0_a


# ---------------------------------------------------------------------------
# Regression: snapshot (if present) + H0/H1/H2 protocol import intact
# ---------------------------------------------------------------------------
class TestSnapshotRegression:
    def test_snapshot_schema(self):
        if not SNAPSHOT_PATH.exists():
            pytest.skip("ML-B1 snapshot not generated yet")
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        assert data["schema_version"] == "ml-b1-first-order-geometry-v1"
        assert "B1_N_side" in data["anchors"]
        anchor = data["anchors"]["B1_N_side"]
        assert anchor["nominal"]["classification"] == "VALID_MARGIN"
        assert anchor["acceptance"]["orientation"] == "PASS"


class TestProtocolIntact:
    def test_h0_h1_h2_modules_importable(self):
        from hyptraj.uncertainty import propagation, protocol, sampling  # noqa: F401

        assert protocol.PHASE_H0_DONE
        assert not protocol.TOPOLOGY_PROBABILITY_COMPUTED
