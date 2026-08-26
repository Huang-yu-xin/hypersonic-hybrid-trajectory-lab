"""M1 -- variance measure estimation tests (task Sec. 7 / 29.2 / 29.3).

Covers:

- variance-mass weight formula for r = p (MC source) and r = q (proposal
  source, incl. the classical w^2 special case) against the closed-form
  ``M2 = exp(m^2) * Phi(a + m)`` for J=1 (d=1 half-space);
- mixed-pilot pooling keeps ``r_i`` per sample (pooling must stay unbiased);
- mode decomposition consistency ``M2_hat ~= sum_k L_k_hat`` (Sec. 29.3);
- normalized variance measure is a probability vector;
- bootstrap LCB of ``omega_k^V`` is a valid lower confidence bound in a
  crafted 2-mode case (variance-dominant mode, LCB well above the gate).

Pure numpy/scipy tests with fixed debug seeds (task Sec. 19).
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from hyptraj.m1.mixture_weights import component_log_densities, mixture_log_density
from hyptraj.m1.variance_measure import (
    estimate_variance_measure,
    omega_bootstrap_lcb,
    variance_mass_weights,
)

A1 = -1.5
A2 = 1.9
M0 = -1.5          # primary mode design center (covers A1)


def _logp(z):
    z = np.asarray(z, dtype=float)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def _labels_double(z, nominal="S0"):
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], nominal, dtype=object)
    out[z[:, 0] <= A1] = "S1"
    out[z[:, 0] >= A2] = "S2"
    return out


def _m2_closed_form(m: float, a: float) -> float:
    """J=1, q = N(m, 1), p = phi: ``M2 = exp(m^2) * Phi(a + m)`` (d=1)."""
    return float(np.exp(m * m) * norm.cdf(a + m))


def _draw(rng, centers, pi, n):
    cent = np.asarray(centers, dtype=float)
    pi = np.asarray(pi, dtype=float)
    comp = rng.choice(cent.shape[0], size=n, p=pi)
    return cent[comp] + rng.standard_normal((n, cent.shape[1]))


class TestVarianceMassFormulas:
    def test_r_equals_p_mc_source(self):
        # r = p: w_tilde = 1_A p^2 / (q p) = 1_A p / q -> unbiased for M2
        rng = np.random.default_rng(4242)
        m, a, n = -1.5, -1.5, 200_000
        reference = _m2_closed_form(m, a)
        z = rng.standard_normal((n, 1))
        logq = component_log_densities(z, np.array([[m]]))
        logr = _logp(z)                     # r = p
        w = variance_mass_weights(z, np.array([[m]]), np.array([1.0]),
                                  _logp(z), logr, (z[:, 0] <= a).astype(float))
        assert np.mean(w) == pytest.approx(reference, rel=5e-2)

    def test_r_equals_q_proposal_w2_formula(self):
        # r = q: w_tilde = 1_A p^2 / q^2 (classical w^2 form); still unbiased
        rng = np.random.default_rng(4242)
        m, a, n = -1.5, -1.5, 200_000
        reference = _m2_closed_form(m, a)
        z = _draw(rng, np.array([[m]]), np.array([1.0]), n)
        centers = np.array([[m]])
        logq_ji = component_log_densities(z, centers)
        logr = mixture_log_density(logq_ji, np.array([1.0]))   # r = q
        w = variance_mass_weights(z, centers, np.array([1.0]),
                                  _logp(z), logr, (z[:, 0] <= a).astype(float))
        assert np.mean(w) == pytest.approx(reference, rel=5e-2)
        # w^2 form: p^2 / q^2 == (p/q)^2 up to float rounding
        w2 = ((np.exp(_logp(z)) / np.exp(logr)) ** 2 * (z[:, 0] <= a).astype(float))
        assert np.allclose(w, w2, rtol=1e-8)

    def test_mixed_pilot_pooling_keeps_r(self):
        # two sources pooled: r1 = p, r2 = q; r_i must be kept per sample
        rng = np.random.default_rng(4242)
        m, a = -1.5, -1.5
        reference = _m2_closed_form(m, a)
        n1, n2 = 100_000, 100_000
        z1 = rng.standard_normal((n1, 1))
        z2 = _draw(rng, np.array([[m]]), np.array([1.0]), n2)
        z = np.vstack([z1, z2])
        centers = np.array([[m]])
        logr = np.concatenate([_logp(z1), mixture_log_density(
            component_log_densities(z2, centers), np.array([1.0]))])
        w = variance_mass_weights(z, centers, np.array([1.0]),
                                  _logp(z), logr, (z[:, 0] <= a).astype(float))
        pooled = np.mean(w)
        assert pooled == pytest.approx(reference, rel=5e-2)
        # mixing ratios must NOT matter (unbiasedness per sample)
        frac1 = np.mean(w[:n1])
        frac2 = np.mean(w[n1:])
        assert frac1 == pytest.approx(reference, rel=5e-2)
        assert frac2 == pytest.approx(reference, rel=5e-2)


class TestModeDecomposition:
    def test_M2_equals_sum_Lk(self):
        # double-mode half-spaces: M2_hat ~= L_S1 + L_S2 (task Sec. 29.3)
        rng = np.random.default_rng(4243)
        z = _draw(rng, np.array([[M0]]), np.array([1.0]), 300_000)
        centers = np.array([[M0]])
        logq_ji = component_log_densities(z, centers)
        logr = mixture_log_density(logq_ji, np.array([1.0]))
        labels = _labels_double(z)
        vm = estimate_variance_measure(z, centers, np.array([1.0]),
                                       _logp(z), logr, labels, "S0")
        assert vm.n_events > 0
        assert sum(vm.L_k) == pytest.approx(vm.M2_hat, rel=1e-10)
        # variance shares sum to one
        assert sum(vm.omega_k_V) == pytest.approx(1.0, rel=1e-10)
        assert all(w >= 0.0 for w in vm.omega_k_V)
        # raw counts are NOT variance mass: S2 has few raw samples but...
        n2 = vm.n_observed[vm.mode_ids.index("S2")]
        w2 = vm.omega_k_V[vm.mode_ids.index("S2")]
        assert n2 < 0.01 * vm.n_samples        # few raw counts
        assert w2 > 0.9                          # ...yet variance-dominant

    def test_normalized_nu_hat_is_probability(self):
        rng = np.random.default_rng(4243)
        z = _draw(rng, np.array([[M0]]), np.array([1.0]), 50_000)
        centers = np.array([[M0]])
        logq_ji = component_log_densities(z, centers)
        logr = mixture_log_density(logq_ji, np.array([1.0]))
        labels = _labels_double(z)
        ind = (labels != "S0").astype(float)
        w = variance_mass_weights(z, centers, np.array([1.0]),
                                  _logp(z), logr, ind)
        w_hat = w / w.sum()
        assert np.all(w_hat >= 0.0)
        assert w_hat.sum() == pytest.approx(1.0)
        assert len(w_hat) == z.shape[0]         # def. as a sum of point masses


class TestBootstrapLCB:
    def test_lcb_valid_and_above_gate_for_dominant_mode(self):
        rng = np.random.default_rng(4244)
        z = _draw(rng, np.array([[M0]]), np.array([1.0]), 100_000)
        centers = np.array([[M0]])
        logq_ji = component_log_densities(z, centers)
        logr = mixture_log_density(logq_ji, np.array([1.0]))
        labels = _labels_double(z)
        vm = estimate_variance_measure(z, centers, np.array([1.0]),
                                       _logp(z), logr, labels, "S0")
        w2_hat = vm.omega_k_V[vm.mode_ids.index("S2")]
        assert w2_hat > 0.9
        lb, ub = omega_bootstrap_lcb(
            z, centers, np.array([1.0]), _logp(z), logr, labels, "S0",
            mode="S2", n_bootstrap=300, seed=4244,
        )
        assert 0.0 <= lb <= ub <= 1.0 + 1e-12
        assert lb <= w2_hat
        assert lb >= 0.05         # LCB clears the frozen lower-confidence gate
        # stability across bootstrap seeds (shrinkage is mild here)
        lb2, _ = omega_bootstrap_lcb(
            z, centers, np.array([1.0]), _logp(z), logr, labels, "S0",
            mode="S2", n_bootstrap=300, seed=4245,
        )
        assert abs(lb2 - lb) < 0.05