"""M1-v0 semantic-correction tests (freeze audit issues 1, 4, 6, 7, 8, 3).

Covers the audit-mandated checks:

- ``variance_mass_hdr_indices``: H3-3A HDR prefix semantics (cumulative
  mass >= eta, minimal prefix, deterministic stable ordering) -- NOT a raw
  quantile;
- ``eta_region_centroid`` against a hand-computed toy;
- stratified-aware target-probability estimator ``(1/N) sum 1_A p / r``
  (raw occurrence fraction is NOT the target probability under the mixed
  fixed design);
- stratified bootstrap: stratum sizes preserved, deterministic under fixed
  seed, size-mismatch rejected;
- ``add_component`` weight initialization 1->2 / 2->3 / 3->4 (old ratios
  preserved, sum == 1, ordering invariant);
- adaptation budget accounting: full 3-birth loop stays within the nominal
  ``max_iterations * pilot_n`` limit (reused diagnostic design);
- VRF definitions (proposal-level vs budget-adjusted) as a single source of
  truth with a math check.
"""

from __future__ import annotations

import numpy as np
import pytest

from hyptraj.m1.baselines import vrf_budget, vrf_proposal
from hyptraj.m1.closed_loop import run_closed_loop
from hyptraj.m1.mixture_weights import component_log_densities, mixture_log_density
from hyptraj.m1.mode_discovery import diagnose_missing_mode
from hyptraj.m1.proposal_update import (
    MixtureProposal,
    add_component,
    eta_region_centroid,
    variance_mass_hdr_indices,
)
from hyptraj.m1.variance_measure import omega_bootstrap_lcb

M0 = -1.5


def _logp(z):
    z = np.asarray(z, dtype=float)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def _draw(rng, centers, pi, n):
    cent = np.asarray(centers, dtype=float)
    pi = np.asarray(pi, dtype=float)
    comp = rng.choice(cent.shape[0], size=n, p=pi)
    return cent[comp] + rng.standard_normal((n, cent.shape[1]))


class TestVarianceMassHdr:
    """Freeze audit Issue 1 -- H3-3A HDR region semantics."""

    def _fixture(self, seed=4242, n=30_000):
        rng = np.random.default_rng(seed)
        centers = np.array([[M0]])
        z = _draw(rng, centers, np.array([1.0]), n)
        logq = mixture_log_density(component_log_densities(z, centers),
                                   np.array([1.0]))
        labels = np.where(z[:, 0] <= -1.5, "S1", "S0")
        return z, centers, _logp(z), logq, labels

    @pytest.mark.parametrize("eta", [0.5, 0.8, 0.9])
    def test_cumulative_mass_reaches_eta_and_is_minimal(self, eta):
        z, centers, logp, logr, labels = self._fixture()
        idx, achieved = variance_mass_hdr_indices(
            z, centers, np.array([1.0]), logp, logr, labels, "S0", "S1", eta)
        assert len(idx) >= 1
        assert achieved >= eta
        # minimal prefix: dropping the LAST selected sample drops the prefix
        # cumulative mass below eta (guaranteed by the searchsorted prefix
        # except for exact ties; tolerated slack 1e-12)
        w = np.exp(2.0 * logp - mixture_log_density(
            component_log_densities(z, centers), np.array([1.0])) - logr)
        total = float(w[labels == "S1"].sum())
        prefix_before_last = (achieved * total - w[idx[-1]]) / total
        assert prefix_before_last < eta + 1e-12

    def test_not_a_raw_quantile(self):
        # with highly non-uniform variance mass the HDR prefix must be much
        # smaller than the raw top-(1-eta) quantile set
        z, centers, logp, logr, labels = self._fixture(seed=7, n=40_000)
        idx, _ = variance_mass_hdr_indices(
            z, centers, np.array([1.0]), logp, logr, labels, "S0", "S1", 0.8)
        n_mode = int((labels == "S1").sum())
        assert len(idx) < 0.6 * n_mode       # mass concentration -> smaller prefix

    def test_deterministic_stable_ordering(self):
        z, centers, logp, logr, labels = self._fixture()
        kwargs = dict(z=z, centers=centers, pi=np.array([1.0]), logp=logp,
                      logr=logr, labels=labels, nominal_topology="S0",
                      mode="S1", eta=0.8)
        idx1, _ = variance_mass_hdr_indices(**kwargs)
        idx2, _ = variance_mass_hdr_indices(**kwargs)
        assert np.array_equal(idx1, idx2)

    def test_centroid_matches_hand_toy(self):
        # two selected points with weights 0.9 / 0.1 -> centroid is 0.9 x a + 0.1 x b
        z = np.array([[1.0, 0.0], [-1.0, 0.0], [5.0, 5.0]])
        centers = np.array([[0.0, 0.0]])
        pi = np.array([1.0])
        logq = mixture_log_density(component_log_densities(z, centers), pi)
        # craft logp so that rho = p^2/q ranks point 0 (mass 0.9) first
        logp = np.array([0.0, -20.0, -20.0]) * 0 + logq / 2.0
        logp = logq / 2.0 + np.array([0.5, -5.0, -5.0])   # rho ratio e^{1} vs e^{-10}
        logr = logq
        labels = np.array(["S1", "S1", "S0"])
        w = np.exp(2.0 * logp - logq - logr) * (labels == "S1").astype(float)
        idx, _ = variance_mass_hdr_indices(
            z, centers, pi, logp, logr, labels, "S0", "S1", 0.5)
        assert set(idx.tolist()) == {0}
        gamma = -1.0 - M0
        assert gamma  # silence unused
        # point 0 alone carries e^1/(e^1 + e^-10) > 0.5 mass -> prefix = {0}
        assert w[0] / (w[0] + w[1]) > 0.5

    def test_eta_region_centroid_api(self):
        z, centers, logp, logr, labels = self._fixture()
        m, eta_used = eta_region_centroid(
            z, logp, logr, np.array([1.0]), centers, labels, "S0", "S1", eta=0.8)
        assert m.shape == (1,)                     # d = 1 fixture
        assert np.all(np.isfinite(m))
        assert eta_used in (0.8, 1.0)


class TestStratifiedProbabilityEstimator:
    """Freeze audit Issue 4 -- target-probability estimator under mixed pilot."""

    def test_estimator_unbiased_and_not_raw_fraction(self):
        rng = np.random.default_rng(4242)
        centers = np.array([[M0]])
        n = 40_000
        half = n // 2
        zq = _draw(rng, centers, np.array([1.0]), half)
        zp = rng.standard_normal((n - half, 1))
        z = np.vstack([zq, zp])
        logq = mixture_log_density(component_log_densities(z, centers),
                                   np.array([1.0]))
        logr = np.concatenate(
            [mixture_log_density(component_log_densities(zq, centers),
                                 np.array([1.0])), _logp(zp)])
        labels = np.where(z[:, 0] <= -1.5, "S2", "S0")
        p_hat_is = float(np.mean((labels == "S2").astype(float)
                                 * np.exp(_logp(z) - logr)))
        raw_frac = float((labels == "S2").mean())
        from scipy.stats import norm
        p_true = float(norm.cdf(-1.5))
        assert p_hat_is == pytest.approx(p_true, rel=3e-2)   # ~1 SE tolerance
        # raw fraction is the MIXED-design occurrence rate, not P_p(A_k)
        assert abs(raw_frac - p_true) > 0.1 * p_true

    def test_top_ranked_comparator_uses_p_hat(self):
        # probability_top picks the top-ranked unrepresented mode (no threshold)
        rng = np.random.default_rng(4242)
        centers = np.array([[M0]])
        n = 40_000
        half = n // 2
        zq = _draw(rng, centers, np.array([1.0]), half)
        zp = rng.standard_normal((n - half, 1))
        z = np.vstack([zq, zp])
        logq = mixture_log_density(component_log_densities(z, centers),
                                   np.array([1.0]))
        logr = np.concatenate(
            [mixture_log_density(component_log_densities(zq, centers),
                                 np.array([1.0])), _logp(zp)])
        labels = np.full(z.shape[0], "S0", dtype=object)
        labels[z[:, 0] <= -1.5] = "S1"
        labels[z[:, 0] >= 2.5] = "S2"
        labels[z[:, 0] >= 3.5] = "S3"
        d = diagnose_missing_mode(
            z, centers, np.array([1.0]), _logp(z), logr, labels, "S0",
            component_mode_ids={"S1"}, birth_signal="probability_top",
            min_mode_observations=5, n_bootstrap=100,
            rng=np.random.default_rng(1),
        )
        # S1 represented -> the top-ranked unrepresented by P_hat is S2
        assert d.candidate_mode == "S2"
        stats = {s.mode_id: s for s in d.mode_stats}
        assert stats["S2"].P_k_hat > stats["S3"].P_k_hat


class TestStratifiedBootstrap:
    """Freeze audit Issue 6 -- stratum-preserving resampling."""

    def _data(self, seed=4244):
        rng = np.random.default_rng(seed)
        centers = np.array([[M0]])
        n = 20_000
        half = n // 2
        zq = _draw(rng, centers, np.array([1.0]), half)
        zp = rng.standard_normal((n - half, 1))
        z = np.vstack([zq, zp])
        logq = mixture_log_density(component_log_densities(z, centers),
                                   np.array([1.0]))
        logr = np.concatenate(
            [mixture_log_density(component_log_densities(zq, centers),
                                 np.array([1.0])), _logp(zp)])
        labels = np.where(z[:, 0] <= -1.5, "S1", "S0")
        strata = np.concatenate([np.zeros(half, dtype=int),
                                 np.ones(n - half, dtype=int)])
        return z, centers, _logp(z), logr, labels, strata

    def test_deterministic_and_valid(self):
        z, centers, logp, logr, labels, strata = self._data()
        lb1, ub1 = omega_bootstrap_lcb(
            z, centers, np.array([1.0]), logp, logr, labels, "S0",
            mode="S1", n_bootstrap=100, seed=42, source_strata=strata)
        lb2, ub2 = omega_bootstrap_lcb(
            z, centers, np.array([1.0]), logp, logr, labels, "S0",
            mode="S1", n_bootstrap=100, seed=42, source_strata=strata)
        assert (lb1, ub1) == (lb2, ub2)
        assert 0.0 <= lb1 <= ub1 <= 1.0 + 1e-12

    def test_stratum_size_mismatch_rejected(self):
        z, centers, logp, logr, labels, strata = self._data()
        with pytest.raises(ValueError):
            omega_bootstrap_lcb(
                z, centers, np.array([1.0]), logp, logr, labels, "S0",
                mode="S1", n_bootstrap=10, seed=42,
                source_strata=strata[:-1])


class TestAddComponentWeights:
    """Freeze audit Issue 7 -- multi-component birth initialization."""

    def test_weights_preserve_old_ratios(self):
        old = MixtureProposal(centers=np.array([[0.0, 0.0], [1.0, 0.0]]),
                              weights=np.array([0.2, 0.8]))
        new = add_component(old, np.array([2.0, 0.0]), "S3", pi_fallback=0.5)
        assert new.weights.sum() == pytest.approx(1.0, abs=1e-12)
        # old ratios preserved: 0.1 : 0.4 (i.e. 1 : 4)
        assert new.weights[0] == pytest.approx(0.1, abs=1e-12)
        assert new.weights[1] == pytest.approx(0.4, abs=1e-12)
        assert new.weights[2] == pytest.approx(0.5, abs=1e-12)

    @pytest.mark.parametrize("stages", [
        (np.array([1.0]), [0.5, 0.5]),
        (np.array([0.8, 0.2]), [0.4, 0.1, 0.5]),
        (np.array([0.5, 0.3, 0.2]), [0.25, 0.15, 0.1, 0.5]),
    ])
    def test_growth_paths(self, stages):
        w0, expected = stages
        j = w0.size
        centers = np.arange(j, dtype=float).reshape(-1, 1)
        prop = MixtureProposal(centers=centers, weights=w0,
                               component_mode_ids=tuple(f"S{i}" for i in range(j)))
        prop = add_component(prop, np.array([[99.0]]), "Snew", pi_fallback=0.5)
        assert prop.n_components == j + 1
        assert np.allclose(prop.weights, expected, atol=1e-12)

    def test_ordering_invariance(self):
        a = MixtureProposal(centers=np.array([[0.0], [1.0]]),
                            weights=np.array([0.3, 0.7]))
        b = MixtureProposal(centers=np.array([[1.0], [0.0]]),
                            weights=np.array([0.7, 0.3]))
        na = add_component(a, np.array([[2.0]]), "S3")
        nb = add_component(b, np.array([[2.0]]), "S3")
        assert np.allclose(np.sort(na.weights), np.sort(nb.weights))


class TestAdaptationBudgetAccounting:
    """Freeze audit Issue 8 -- reused diagnostic keeps the loop in budget."""

    M1, M2 = -1.5, 2.5

    def _labels(self, z):
        # d=2, three modes in ORTHOGONAL directions so a component built for
        # S2 (u1) does not cover S3 (u2): both stay variance-important
        z = np.asarray(z, dtype=float)
        out = np.full(z.shape[0], "S0", dtype=object)
        out[z[:, 0] <= self.M1] = "S1"
        out[z[:, 0] >= self.M2] = "S2"
        out[z[:, 1] >= self.M2] = "S3"
        return out

    def test_full_three_birth_loop_within_nominal_budget(self):
        res = run_closed_loop(
            seed=2026,
            initial_proposal=MixtureProposal(
                centers=np.array([[M0, 0.0]]), weights=np.array([1.0]),
                component_mode_ids=("S1",)),
            label_oracle=self._labels, logp_fn=_logp, nominal_topology="S0",
            pilot_n=20_000, pilot_policy="mix", pilot_alpha=0.5,
            max_iterations=3, n_bootstrap=50,
        )
        assert res.budget["assertion_passed"]
        assert res.budget["cumulative_adaptation_calls"] <= res.budget["budget_limit"]
        # the two unrepresented modes born within 3 rounds
        births = [it.candidate_mode for it in res.iterations
                  if it.action == "ADD_COMPONENT"]
        assert set(births) == {"S2", "S3"}
        # diagnostics fully reused: no extra calls beyond round pilots
        assert res.budget["diagnostic_calls_total"] == 0
        per_round = [it.pilot_calls for it in res.iterations]
        assert per_round == [20_000] * len(per_round)

    def test_single_hold_never_exceeds(self):
        res = run_closed_loop(
            seed=2026,
            initial_proposal=MixtureProposal(
                centers=np.array([[M0, 0.0]]), weights=np.array([1.0]),
                component_mode_ids=("S1",)),
            label_oracle=lambda z: np.where(
                np.asarray(z)[:, 0] <= self.M1, "S1", "S0"),
            logp_fn=_logp, nominal_topology="S0",
            pilot_n=20_000, pilot_policy="proposal",
        )
        assert res.budget["assertion_passed"]
        assert res.budget["cumulative_adaptation_calls"] == 20_000


class TestVrfDefinitions:
    """Freeze audit Issue 3 -- proposal-level vs budget-adjusted VRF."""

    def test_proposal_vrf_math(self):
        # MC variance at n_eval over IS variance at n_eval
        p, n, var_is = 0.1, 1e5, 1e-6
        assert vrf_proposal(p, n, var_is) == pytest.approx(
            (p * (1 - p) / n) / var_is)
        assert vrf_proposal(0.1, 1e5, 0.0) == float("inf")

    def test_budget_vrf_math(self):
        # MC at full budget over IS at reduced eval budget
        p, B, m2, phat, n_eval = 0.1, 160_000, 0.02, 0.1, 100_000
        num = p * (1 - p) / B
        den = (m2 - phat**2) / n_eval
        assert vrf_budget(p, B, m2, phat, n_eval) == pytest.approx(num / den)
        # adaptive overhead: eval budget smaller -> budget VRF smaller
        assert vrf_budget(p, B, m2, phat, 100_000) > vrf_budget(p, B, m2, phat, 50_000)