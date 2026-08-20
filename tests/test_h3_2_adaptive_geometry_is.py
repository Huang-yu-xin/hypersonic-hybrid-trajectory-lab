"""H3-2 -- Variance-optimal leakage-point adaptive Geometry-IS tests.

Covers:

- leakage-point geometry unit tests (MPP vs x_L: coincidence on linear
  boundaries, separation on curved boundaries; rho_L analytic reference)
- weight-strategy unit tests (leakage_power / hybrid_power)
- synthetic experiment regressions A (multi-mode recovery) and
  B (curvature stress): M1 fails, M2/M3 recover, x* != x_L on B
- dataset regression against ``tests/data/h3_2_leakage_point_dataset_v1.json``

Nothing here modifies ML-B1, H2/H2R, frozen simulator physics, or the
Geometry-IS theorem implementation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from hyptraj.uncertainty.adaptive_geometry_is import (
    hybrid_power_weights,
    leakage_power_weights,
)
from hyptraj.uncertainty.leakage_point_geometry import (
    log_leakage_density,
    mpp,
    point_geometry,
    leakage_point,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "tests" / "data" / "h3_2_leakage_point_dataset_v1.json"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Leakage-point geometry unit tests
# ---------------------------------------------------------------------------
class TestPointGeometry:
    def test_log_leakage_density_analytic(self):
        # rho_L = phi^2/q, q = N(mu, I):
        # log rho_L = -||z||^2 + ||z-mu||^2/2 - (d/2) log(2pi), d = 2
        z = np.array([[0.0, 0.0], [1.0, 0.0]])
        mu = np.array([-1.5, 0.0])
        log_rho = log_leakage_density(z, mu)
        const = np.log(2 * np.pi)          # d/2 = 1
        expected = np.array(
            [0.0 + 0.5 * 1.5**2 - const,   # z = (0,0)
             -1.0 + 0.5 * (2.5) ** 2 - const]  # z = (1,0)
        )
        assert log_rho[0] == pytest.approx(expected[0], rel=1e-9)
        assert log_rho[1] == pytest.approx(expected[1], rel=1e-9)

    def test_linear_boundary_points_coincide(self):
        # A = {u1 < -1.5}, mu = -1.5 e1: x* = x_L = -1.5 e1
        pts = np.array([[-1.5, 0.0], [-2.0, 0.0], [-3.0, 1.0], [-1.6, 0.5]])
        mu = np.array([-1.5, 0.0])
        xs, xl = mpp(pts), leakage_point(pts, mu)
        assert np.allclose(xs, xl)

    def test_curved_boundary_points_separate(self):
        # A = {u1 > 1.0 + 0.5*(u2-1.5)^2}, mu = (-1.5, 0): x* != x_L
        g1 = np.linspace(1.0, 6.0, 321)
        g2 = np.linspace(-1.0, 4.0, 251)
        G1, G2 = np.meshgrid(g1, g2)
        pts = np.stack([G1.ravel(), G2.ravel()], axis=1)
        sel = pts[:, 0] > 1.0 + 0.5 * (pts[:, 1] - 1.5) ** 2
        pts = pts[sel]
        mu = np.array([-1.5, 0.0])
        xs, xl = mpp(pts), leakage_point(pts, mu)
        assert np.linalg.norm(xl - xs) > 0.3

    def test_point_geometry_fields(self):
        pts = np.array([[-1.5, 0.0], [-2.0, 0.0], [-3.0, 1.0]])
        pg = point_geometry(pts, np.array([-1.5, 0.0]), "m0", "S1", 1.5)
        assert pg.probability_design_point == pytest.approx((-1.5, 0.0))
        assert pg.distance_between_points >= 0.0
        assert pg.leakage_density > 0.0
        assert pg.mpp_density > 0.0
        assert pg.coverage_score == pytest.approx(1.5)


class TestWeightStrategies:
    def test_leakage_power_weights(self):
        w = leakage_power_weights(np.array([0.1, 1.9]), alpha=1.0)
        assert w.sum() == pytest.approx(1.0)
        assert w[1] > w[0]
        w2 = leakage_power_weights(np.array([0.1, 1.9]), alpha=0.5)
        assert w2[1] > w2[0]

    def test_hybrid_power_weights(self):
        P = np.array([0.9, 0.1])
        L = np.array([0.01, 0.99])
        w = hybrid_power_weights(P, L, gamma=0.5)
        assert w.sum() == pytest.approx(1.0)
        assert w[1] > w[0]          # leakage still up-weights the far mode
        wg = hybrid_power_weights(P, L, gamma=1.0)  # degenerates to P
        assert wg[0] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Synthetic experiment regressions (no simulator)
# ---------------------------------------------------------------------------
class TestSyntheticExperiments:
    def _run(self, cfg):
        from run_h3_2_adaptive_geometry_is import run_experiment

        return run_experiment(cfg)

    def test_a_multi_mode_recovery(self):
        exp = self._run({"experiment_id": "A_synthetic_multi_mode_recovery",
                         "kind": "synthetic_linear"})
        assert exp["n_modes"] == 2
        assert exp["baseline_m1"]["vrf"] < 1.0                  # single fails
        assert exp["topology_mixture_m2"]["vrf"] > 1.0          # mixture recovers
        assert exp["leakage_point_m3"]["probability"]["vrf"] > 1.0
        assert exp["leakage_reduction"] < 0.1
        # linear boundary: MPP and x_L coincide
        assert exp["mpp_xl_separation"]["S1"] == pytest.approx(0.0, abs=1e-6)
        assert exp["mpp_xl_separation"]["S2"] == pytest.approx(0.0, abs=1e-6)

    def test_b_curvature_separates_geometry(self):
        exp = self._run({"experiment_id": "B_synthetic_curvature_beta_kappa",
                         "kind": "synthetic_curved"})
        assert exp["n_modes"] == 2
        assert exp["baseline_m1"]["vrf"] < 1.0                  # S2 leak dominates
        assert exp["topology_mixture_m2"]["vrf"] > 1.0
        assert exp["leakage_point_m3"]["probability"]["vrf"] > 1.0
        assert exp["leakage_reduction"] < 0.1
        # curved secondary mode: x* != x_L
        assert exp["mpp_xl_separation"]["S2"] > 0.3
        assert exp["mpp_xl_separation"]["S1"] == pytest.approx(0.0, abs=1e-6)

    def test_m3_strategies_reported(self):
        exp = self._run({"experiment_id": "A_synthetic_multi_mode_recovery",
                         "kind": "synthetic_linear"})
        assert set(exp["leakage_point_m3"]) >= {"probability", "leak_power1", "p05_l05"}
        assert exp["best_m3_strategy"] in exp["leakage_point_m3"]


# ---------------------------------------------------------------------------
# Dataset regression
# ---------------------------------------------------------------------------
class TestDatasetRegression:
    @pytest.fixture(scope="class")
    def dataset(self):
        if not DATASET_PATH.exists():
            pytest.skip("H3-2 leakage-point dataset not generated yet")
        return json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    def test_manifest(self, dataset):
        assert dataset["schema_version"] == "h3-2-leakage-point-dataset-v1"
        assert dataset["ml_b1_snapshot"] == "ml-b1-first-order-geometry-v1"

    def test_experiments_covered(self, dataset):
        ids = {e["experiment_id"] for e in dataset["experiments"]}
        assert "A_synthetic_multi_mode_recovery" in ids
        assert "B_synthetic_curvature_beta_kappa" in ids
        assert dataset["summary"]["n_experiments"] == len(dataset["experiments"]) >= 3

    def test_point_geometry_fields(self, dataset):
        for e in dataset["experiments"]:
            for g in e["point_geometry"]:
                for f in ("probability_design_point", "leakage_point",
                          "distance_between_points", "leakage_density",
                          "coverage_score", "topology_label"):
                    assert f in g, f"missing {f} in {e['experiment_id']}"

    def test_ablation_fields(self, dataset):
        for e in dataset["experiments"]:
            assert e["baseline_m1"]["vrf"] > 0
            assert e["topology_mixture_m2"]["vrf"] > 0
            assert e["leakage_point_m3"]
            assert "leakage_reduction" in e
            assert "mpp_xl_separation" in e

    def test_a_recovery_locked(self, dataset):
        a = next(e for e in dataset["experiments"]
                 if e["experiment_id"] == "A_synthetic_multi_mode_recovery")
        assert a["baseline_m1"]["vrf"] < 1.0
        assert a["topology_mixture_m2"]["vrf"] > 1.0
        assert a["leakage_point_m3"]["probability"]["vrf"] > 1.0
        assert a["leakage_reduction"] < 0.1

    def test_b_curvature_locked(self, dataset):
        b = next(e for e in dataset["experiments"]
                 if e["experiment_id"] == "B_synthetic_curvature_beta_kappa")
        assert b["baseline_m1"]["vrf"] < 1.0
        assert b["mpp_xl_separation"]["S2"] > 0.3

    def test_real_configs_present(self, dataset):
        real = [e for e in dataset["experiments"] if e["kind"] == "real_sanger"]
        if not real:
            pytest.skip("real Sanger experiments not in this snapshot")
        for e in real:
            assert e["anchor"] in ("B1_N1_side", "B2_N_side")
            assert "alpha" in e


class TestProtocolIntact:
    def test_h3_not_started_flags(self):
        from hyptraj.uncertainty import protocol

        assert protocol.PHASE_H0_DONE
        assert not protocol.TOPOLOGY_PROBABILITY_COMPUTED
