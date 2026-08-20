"""H3-1 -- Variance leakage driven Geometry-IS validation tests.

Covers (Task 8 "Tests"):

- analysis-core unit tests (proposal, weights, estimators, ESS, VRF,
  leakage decomposition, coverage, correlations) with analytic references
  on a synthetic half-space -- no simulator involved
- L0 smooth-synthetic closure (analytic vs estimated leak, VRF > 1)
- dataset regression + mode-level schema extension fields
  (mode_id / mode_probability / mode_beta / mode_design_point /
  mode_direction / proposal_density / leak_k / leak_fraction /
  coverage_score) against ``tests/data/h3_variance_leakage_dataset_v1.json``

Nothing here modifies ML-B1, frozen physics, H2/H2R code, or the
Geometry-IS theorem implementation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad

from hyptraj.uncertainty.variance_leakage import (
    decompose_modes,
    design_point,
    effective_sample_size,
    importance_estimator,
    importance_weights,
    mc_estimator,
    pearson,
    spearman,
    total_leakage,
    vrf,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "tests" / "data" / "h3_variance_leakage_dataset_v1.json"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Analysis-core unit tests (analytic half-space reference, dim = 1)
# ---------------------------------------------------------------------------
BETA = 2.0
P_TRUE = 0.02275013194817921          # Phi(-2)
N_REF = 100_000


def _w1d(v: np.ndarray, beta: float = BETA) -> np.ndarray:
    """phi/q for q = N(-beta, 1): log w = beta*v + beta^2/2 (dim 1)."""
    return np.exp(beta * np.asarray(v, dtype=float) + beta * beta / 2.0)


def _var_is_analytic(beta: float = BETA) -> float:
    # var_IS = (E_q[w^2 1_A] - P^2) / N with N = 1 (per-sample variance)
    second, _ = quad(
        lambda v: _w1d(v, beta) ** 2
        * (2 * np.pi) ** -0.5 * np.exp(-(v + beta) ** 2 / 2.0),
        -np.inf, -beta,
    )
    return second - P_TRUE**2


class TestProposal:
    def test_design_point_formula(self):
        alpha = np.array([0.0, 1.0, 0.0, 0.0])
        z_star = design_point(BETA, alpha)
        assert np.allclose(z_star, [0.0, -BETA, 0.0, 0.0])

    def test_importance_weights_analytic_1d(self):
        v = np.linspace(-6.0, 4.0, 7)
        z = np.stack([v, np.zeros_like(v)], axis=1)
        z_star = design_point(BETA, np.array([1.0, 0.0]))
        w = importance_weights(z, z_star)
        assert np.allclose(w, _w1d(v), rtol=1e-10)

    def test_weights_positive_and_finite(self):
        rng = np.random.default_rng(0)
        z = rng.standard_normal((500, 4))
        w = importance_weights(z, design_point(2.0, np.array([1.0, 0, 0, 0])))
        assert np.all(w > 0) and np.all(np.isfinite(w))


class TestEstimators:
    def test_mc_estimator_matches_bernoulli(self):
        rng = np.random.default_rng(1)
        ind = rng.random(10_000) < P_TRUE
        p, var = mc_estimator(ind)
        assert p == pytest.approx(P_TRUE, abs=0.01)
        assert var == pytest.approx(p * (1 - p) / ind.size, rel=1e-6)

    def test_importance_estimator_analytic_1d(self):
        rng = np.random.default_rng(2)
        v = rng.normal(-BETA, 1.0, size=N_REF)   # q = N(-beta, 1)
        ind = v < -BETA
        w = _w1d(v)
        p, var = importance_estimator(w, ind)
        assert p == pytest.approx(P_TRUE, abs=2e-3)
        assert var == pytest.approx(_var_is_analytic() / N_REF, rel=0.1)

    def test_vrf_definition(self):
        assert vrf(0.1, 1e-4, 0.1, 1e-5) == pytest.approx(10.0)
        assert np.isinf(vrf(0.1, 1e-4, 0.1, 0.0))

    def test_ess_uniform_weights(self):
        assert effective_sample_size(np.ones(64)) == pytest.approx(64.0)
        w = np.array([1.0, 1.0, 0.0, 0.0])
        assert effective_sample_size(w) == pytest.approx(2.0)


class TestLeakageDecomposition:
    def test_leak_sums_to_total(self):
        rng = np.random.default_rng(3)
        z = rng.standard_normal((4000, 2))
        z_star = design_point(1.5, np.array([1.0, 0.0]))
        z = z_star + z                      # proposal samples
        w = importance_weights(z, z_star)
        # two modes: A1 = {u0 < -1.5}, A2 = {u0 < -2.5, u1 > 1.0}
        labels = np.where((z[:, 0] < -2.5) & (z[:, 1] > 1.0), "T2",
                          np.where(z[:, 0] < -1.5, "T1", "NOM"))
        modes = decompose_modes(
            z, w, labels, "NOM", np.array([1.0, 0.0]), z_star,
            p_k_mc={"T1": 0.01, "T2": 0.001}, p_total_mc=0.011,
            transition_channel="atmosphere_exit",
        )
        assert len(modes) == 2
        assert sum(m.leak for m in modes) == pytest.approx(
            total_leakage(w, labels != "NOM"), rel=1e-9
        )
        assert sum(m.leak_fraction for m in modes) == pytest.approx(1.0, rel=1e-9)
        for m in modes:
            assert m.leak >= 0.0
            assert m.mode_beta > 0.0
            assert len(m.mode_design_point) == 2
            assert m.coverage_score > 0.0
            assert m.transition_channel == "atmosphere_exit"

    def test_secondary_mode_can_dominate_leak(self):
        # Hand-crafted weights (w formula covered by the analytic test):
        # moderate w in the near mode T1, huge w in the far mode T2 ->
        # the low-probability mode carries the dominant leak.
        rng = np.random.default_rng(4)
        z = rng.standard_normal((8000, 2)) * 2.0
        labels = np.where(
            z[:, 0] < -5.0, "T2",
            np.where(z[:, 0] < -1.5, "T1", "NOM"),
        )
        w = np.ones(z.shape[0])
        w[z[:, 0] < -1.5] = 2.0
        w[z[:, 0] < -5.0] = 80.0
        z_star = np.zeros(2)
        modes = decompose_modes(
            z, w, labels, "NOM", np.array([1.0, 0.0]), z_star,
            p_k_mc={"T1": 0.3, "T2": 1e-4}, p_total_mc=0.3001,
            transition_channel="atmosphere_exit",
        )
        by_top = {m.transition_topology: m for m in modes}
        assert len(by_top) == 2
        assert by_top["T2"].leak > by_top["T1"].leak
        assert by_top["T2"].leak_fraction > 0.5
        assert by_top["T2"].probability < by_top["T1"].probability
        assert by_top["T2"].n_events >= 1
        assert by_top["T2"].coverage_score > 0.0


class TestCorrelation:
    def test_pearson_known(self):
        assert pearson(np.array([1.0, 2, 3]), np.array([2.0, 4, 6])) == pytest.approx(1.0)
        assert pearson(np.array([1.0, 2, 3]), np.array([6.0, 4, 2])) == pytest.approx(-1.0)

    def test_spearman_known(self):
        assert spearman(np.array([1.0, 2, 3, 4]), np.array([1.0, 2, 3, 4])) == pytest.approx(1.0)
        assert spearman(np.array([1.0, 2, 3, 4]), np.array([4.0, 3, 2, 1])) == pytest.approx(-1.0)

    def test_correlation_nan_for_singleton(self):
        assert np.isnan(pearson(np.array([1.0]), np.array([2.0])))


# ---------------------------------------------------------------------------
# L0 smooth-synthetic closure (no simulator)
# ---------------------------------------------------------------------------
class TestL0Synthetic:
    @pytest.fixture(scope="class")
    def l0(self):
        from run_h3_variance_leakage import run_synthetic_l0

        return run_synthetic_l0()

    def test_geometry_error_zero(self, l0):
        assert l0.epsilon_geo == pytest.approx(0.0)

    def test_single_mode(self, l0):
        assert len(l0.modes) == 1
        assert l0.modes[0].transition_topology == "S1"

    def test_probability_close_to_theory(self, l0):
        assert l0.p_mc == pytest.approx(P_TRUE, abs=0.02)
        assert l0.p_is == pytest.approx(P_TRUE, abs=0.02)

    def test_vrf_high(self, l0):
        assert l0.vrf > 5.0

    def test_leak_matches_analytic(self, l0):
        assert l0.total_leak == pytest.approx(l0.analytic_leak, rel=0.15)

    def test_mode_fields_present(self, l0):
        m = l0.modes[0]
        assert m.mode_design_point[0] == pytest.approx(-l0.beta_eff, abs=0.5)
        assert m.proposal_density > 0.0


# ---------------------------------------------------------------------------
# Dataset regression + schema extension (mode-level fields)
# ---------------------------------------------------------------------------
class TestDatasetRegression:
    MODE_FIELDS = (
        "mode_id", "mode_probability", "mode_beta", "mode_design_point",
        "mode_direction", "proposal_density", "leak_k", "leak_fraction",
        "coverage_score",
    )

    @pytest.fixture(scope="class")
    def dataset(self):
        if not DATASET_PATH.exists():
            pytest.skip("H3-1 leakage dataset not generated yet")
        return json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    def test_manifest(self, dataset):
        assert dataset["schema_version"] == "h3-variance-leakage-dataset-v1"
        assert dataset["h3_schema"] == "h3-sample-schema-v1"
        assert dataset["ml_b1_snapshot"] == "ml-b1-first-order-geometry-v1"
        assert dataset["n_samples_per_estimator"] == dataset["n_pairs"] * 2

    def test_levels_covered(self, dataset):
        levels = {c["level"] for c in dataset["configs"]}
        assert levels >= {"L0", "L1", "L2", "L3"}
        assert dataset["summary"]["n_configs"] == len(dataset["configs"]) >= 4

    def test_mode_schema_fields_present(self, dataset):
        n_modes = 0
        for c in dataset["configs"]:
            for m in c["modes"]:
                n_modes += 1
                for f in self.MODE_FIELDS:
                    assert f in m, f"mode missing {f} in {c['config_id']}"
                assert m["mode_probability"] >= 0.0
                assert m["leak_k"] >= 0.0
                assert 0.0 <= m["leak_fraction"] <= 1.0 + 1e-9
                assert len(m["mode_design_point"]) == 4
                assert len(m["mode_direction"]) == 4
        assert n_modes >= 3
        assert dataset["summary"]["n_modes"] == n_modes

    def test_geometry_is_baseline_fields(self, dataset):
        for c in dataset["configs"]:
            for f in ("p_mc", "p_is", "var_mc", "var_is", "ess", "vrf",
                      "total_leak", "accepted_rare_events", "design_point",
                      "epsilon_geo", "beta_eff"):
                assert f in c, f"{c['config_id']} missing {f}"

    def test_vrf_consistency(self, dataset):
        for c in dataset["configs"]:
            if c["var_is"] > 0:
                assert c["vrf"] == pytest.approx(c["var_mc"] / c["var_is"], rel=1e-6)

    def test_leak_fractions_normalized(self, dataset):
        for c in dataset["configs"]:
            if c["modes"]:
                assert sum(m["leak_fraction"] for m in c["modes"]) == pytest.approx(1.0, rel=1e-6)

    def test_l0_present_with_analytic_leak(self, dataset):
        l0 = next(c for c in dataset["configs"] if c["level"] == "L0")
        assert "analytic_leak" in l0
        assert l0["total_leak"] == pytest.approx(l0["analytic_leak"], rel=0.15)
        assert l0["vrf"] > 5.0

    def test_correlations_reported(self, dataset):
        corr = dataset["correlations"]
        assert corr["n_configs"] == len(dataset["configs"])
        for key in ("eps_geo_vs_vrf", "leak_vs_vrf"):
            assert key in corr and corr[key] == corr[key]  # not NaN

    def test_locked_counts(self, dataset):
        assert dataset["summary"]["n_configs"] == LOCKED_N_CONFIGS
        assert dataset["summary"]["n_modes"] == LOCKED_N_MODES


class TestProtocolIntact:
    def test_h3_not_started_flags(self):
        from hyptraj.uncertainty import protocol

        assert protocol.PHASE_H0_DONE
        assert not protocol.TOPOLOGY_PROBABILITY_COMPUTED


# Locked regression values (from the deterministic artifact, seed 2026).
LOCKED_N_CONFIGS = 6
LOCKED_N_MODES = 7
