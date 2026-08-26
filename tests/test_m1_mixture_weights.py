"""M1-1 -- Fixed-component mixture-weight convexity tests.

Covers task Sec. 29.1 (density / mixture) and Sec. 29.4 (mixture-weight
objective) plus the theory claims of
``docs/phase_m1/M1_Theory_Mixture_Weight_Convexity.md``:

- unbiasedness of ``M2_hat(pi)`` for r = p (MC), r = q_{pi0} (fixed proposal,
  incl. the classical w^2 special case) and pooled mixed pilots, against
  exact references (J=1 closed form ``exp(m^2) * Phi(a+m)``; J=2 quadrature);
- analytic gradient (T1) vs constraint-respecting central finite differences
  along simplex tangent directions (the module enforces the simplex, so raw
  coordinate FD is unavailable by design);
- analytic Hessian (T2): symmetry, PSD (``v^T H v >= 0``), eig min, FD of the
  directional gradient;
- empirical convexity on a FIXED sample set (random segment midpoint checks);
- SLSQP: simplex/floor constraints kept, objective improved, KKT residue,
  init independence (theory-backed global minimum of the empirical objective);
- degenerate identical components: flatness along the simplex direction.

Nothing here modifies H3 frozen artifacts; pure numpy/scipy tests with
locally fixed debug seeds (task Sec. 19: debug runs do not enter final
statistics).
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import norm

from hyptraj.m1.mixture_weights import (
    component_log_densities,
    kkt_residue,
    m2_gradient,
    m2_hat,
    m2_hessian,
    mixture_log_density,
    optimize_mixture_weights,
    validate_weights,
)

D = 2
LOG2PISQRT = 0.5 * np.log(2.0 * np.pi)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def target_log_density(z: np.ndarray) -> np.ndarray:
    """``log p(z) = log N(z | 0, I)`` (standardized space)."""
    z = np.asarray(z, dtype=float)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def draw_from_mixture(rng: np.random.Generator, centers, pi, n: int) -> np.ndarray:
    cent = np.asarray(centers, dtype=float)
    pi = np.asarray(pi, dtype=float)
    comp = rng.choice(cent.shape[0], size=n, p=pi)
    return cent[comp] + rng.standard_normal((n, cent.shape[1]))


def make_inputs(
    z: np.ndarray, centers, pi_r, event_a: float, event_b: float | None = None
):
    """Log-inputs for samples ``z`` drawn from ``r = q_{pi_r}``."""
    logq_ji = component_log_densities(z, np.asarray(centers, dtype=float))
    logr = mixture_log_density(logq_ji, pi_r)
    logp = target_log_density(z)
    ind = (z[:, 0] <= event_a).astype(float)
    if event_b is not None:
        ind = np.maximum(ind, (z[:, 0] >= event_b).astype(float))
    return logq_ji, logp, logr, ind


# ---------------------------------------------------------------------------
# Task Sec. 29.1 -- density / mixture
# ---------------------------------------------------------------------------
class TestWeightsValidation:
    def test_sums_to_one_and_nonneg(self):
        w = validate_weights(np.array([0.3, 0.7]))
        assert np.isclose(w.sum(), 1.0)
        assert np.all(w >= 0.0)
        with pytest.raises(ValueError):
            validate_weights(np.array([0.3, 0.8]))      # sum != 1
        with pytest.raises(ValueError):
            validate_weights(np.array([1.1, -0.1]))     # negative

    def test_floor_enforced(self):
        with pytest.raises(ValueError):
            validate_weights(np.array([0.04, 0.96]), floor=0.05)

    def test_shape_checks(self):
        with pytest.raises(ValueError):
            validate_weights(np.array([[0.5, 0.5]]))    # 2-D
        with pytest.raises(ValueError):
            validate_weights(np.array([]))              # empty


class TestMixtureDensity:
    def test_component_closed_form(self):
        # d=1: log N(z|m,1) = -(z-m)^2/2 - 0.5 log(2pi)
        z = np.array([[0.5], [2.0]])
        centers = np.array([[1.0], [-0.5]])
        logq = component_log_densities(z, centers)
        expected = np.array([
            [-((0.5 - 1.0) ** 2) / 2.0 - LOG2PISQRT,
             -((0.5 + 0.5) ** 2) / 2.0 - LOG2PISQRT],
            [-((2.0 - 1.0) ** 2) / 2.0 - LOG2PISQRT,
             -((2.0 + 0.5) ** 2) / 2.0 - LOG2PISQRT],
        ])
        assert np.allclose(logq, expected)

    def test_mixture_matches_manual_sum(self):
        z = np.array([[0.3, -0.2], [1.5, 0.7]])
        centers = np.array([[-1.5, 0.0], [1.8, 0.3], [0.1, -0.4]])
        pi = np.array([0.2, 0.5, 0.3])
        logq = component_log_densities(z, centers)
        log_dens = mixture_log_density(logq, pi)
        dens = np.exp(log_dens)
        manual = np.zeros(z.shape[0])
        for j, m in enumerate(centers):
            manual += pi[j] * np.exp(component_log_densities(z, m[None, :])[:, 0])
        assert np.allclose(dens, manual, rtol=1e-12)

    def test_logsumexp_stability_under_offset(self):
        z = np.array([[0.3, -0.2]])
        centers = np.array([[-1.5, 0.0], [1.8, 0.3]])
        pi = np.array([0.4, 0.6])
        logq = component_log_densities(z, centers)
        base = mixture_log_density(logq, pi)[0]
        for c in (300.0, 800.0):
            shifted = mixture_log_density(logq + c, pi)[0]
            assert shifted == pytest.approx(base + c, rel=1e-12)
        # naive exp path overflows for large offset; logsumexp path stays finite
        naive = np.log(np.sum(np.exp(logq + np.log(pi)), axis=1))
        assert np.isfinite(naive).all()
        with np.errstate(over="ignore"):
            naive_big = np.log(np.sum(np.exp(logq + 800.0 + np.log(pi)), axis=1))
        assert np.isinf(naive_big.sum())

    def test_ordering_invariance(self):
        z = np.array([[0.3, -0.2], [1.5, 0.7], [-0.1, 0.4]])
        centers = np.array([[-1.5, 0.0], [1.8, 0.3], [0.1, -0.4]])
        pi = np.array([0.2, 0.5, 0.3])
        logq = component_log_densities(z, centers)
        perm = np.array([2, 0, 1])
        assert np.allclose(
            mixture_log_density(logq, pi),
            mixture_log_density(logq[:, perm], pi[perm]),
        )
        logr = mixture_log_density(logq, pi)
        logp = target_log_density(z)
        ind = (z[:, 0] <= 0.0).astype(float)
        assert m2_hat(logq, logp, logr, ind, pi) == pytest.approx(
            m2_hat(logq[:, perm], logp, logr, ind, pi[perm])
        )
        assert np.allclose(
            m2_gradient(logq, logp, logr, ind, pi)[perm],
            m2_gradient(logq[:, perm], logp, logr, ind, pi[perm]),
        )
        assert np.allclose(
            m2_hessian(logq, logp, logr, ind, pi)[perm][:, perm],
            m2_hessian(logq[:, perm], logp, logr, ind, pi[perm]),
        )

    def test_positive_on_required_support(self):
        # representable-but-far points: density must stay > 0 and finite
        z = np.array([[8.0, 0.0], [-8.0, 2.0]])
        centers = np.array([[-1.5, 0.0], [1.8, 0.3]])
        pi = np.array([0.5, 0.5])
        dens = np.exp(mixture_log_density(component_log_densities(z, centers), pi))
        assert np.all(np.isfinite(dens))
        assert np.all(dens > 0.0)


# ---------------------------------------------------------------------------
# Task Sec. 14.2 / 29.4 -- finite-sample objective: unbiasedness
# ---------------------------------------------------------------------------
class TestM2Unbiasedness:
    # exact references (d = 1 half-space A = {z <= a})
    @staticmethod
    def _m2_closed_form_j1(m: float, a: float) -> float:
        """J=1, q = N(m, 1), p = phi: M2 = exp(m^2) * Phi(a + m)."""
        return float(np.exp(m * m) * norm.cdf(a + m))

    @staticmethod
    def _m2_quad(centers, pi, a: float) -> float:
        """d=1 quadrature of ``int_{-inf}^a phi(z)^2 / q_pi(z) dz``."""
        centers = np.atleast_1d(np.asarray(centers, dtype=float))
        pi = np.asarray(pi, dtype=float)

        def integrand(z):
            z = np.asarray(z, dtype=float)
            log_p2 = -z * z - np.log(2.0 * np.pi)          # 2 log phi(z), d=1
            log_q = np.logaddexp.reduce(
                [np.log(w) - 0.5 * (z - m) ** 2 - 0.5 * np.log(2.0 * np.pi)
                 for m, w in zip(centers, pi)], axis=0)
            return np.exp(log_p2 - log_q)

        val, _ = quad(integrand, -np.inf, float(a), limit=400)
        return float(val)


def _batch_bias(estimates: np.ndarray, reference: float):
    sd = estimates.std(ddof=1)
    assert sd > 0.0, "degenerate batches: identical estimates"
    se = sd / np.sqrt(estimates.size)
    assert abs(estimates.mean() - reference) <= 3.0 * se, (
        f"bias {abs(estimates.mean() - reference):.6g} > 3 SE {3 * se:.6g}"
    )


def _interior(rng: np.random.Generator, k: int, margin: float = 0.05) -> np.ndarray:
    """Random interior simplex point bounded away from the boundary."""
    a = rng.dirichlet(np.ones(k) * 2.0)
    a = np.clip(a, margin, None)
    return a / a.sum()


@pytest.fixture(scope="module")
def fd_data():
    rng = np.random.default_rng(4242)
    centers = np.array([[-1.5, 0.0], [0.5, 1.0], [1.8, -0.5]])
    pi0 = np.array([0.4, 0.3, 0.3])
    z = draw_from_mixture(rng, centers, pi0, 6000)
    return make_inputs(z, centers, pi0, -1.1, event_b=2.2)


@pytest.fixture(scope="module")
def opt_data():
    rng = np.random.default_rng(4243)
    centers = np.array([[-1.5, 0.0], [0.5, 1.0], [1.8, -0.5]])
    pi0 = np.array([0.4, 0.3, 0.3])
    z = draw_from_mixture(rng, centers, pi0, 8000)
    return make_inputs(z, centers, pi0, -1.1, event_b=2.2)

    def test_quad_self_consistency(self):
        # guard: quadrature reference agrees with the J=1 closed form
        m, a = 1.0, -0.75
        assert self._m2_quad([m], [1.0], a) == pytest.approx(
            self._m2_closed_form_j1(m, a), rel=1e-6
        )

    def test_unbiased_r_equals_p_j1_closed_form(self):
        # r = p (MC source): M2_hat(pi) unbiased at the single-component case
        m, a, n, b = 1.0, -0.75, 4000, 80
        reference = self._m2_closed_form_j1(m, a)
        rng = np.random.default_rng(4242)
        ests = []
        for _ in range(b):
            z = rng.standard_normal((n, 1))
            logq = component_log_densities(z, np.array([[m]]))
            logr = target_log_density(z)          # r = p
            ind = (z[:, 0] <= a).astype(float)
            ests.append(m2_hat(logq, target_log_density(z), logr, ind, np.array([1.0])))
        _batch_bias(np.array(ests), reference)

    def test_unbiased_r_equals_q_pi0_cross_pi(self):
        # r = q_{pi0} frozen: M2_hat(pi) unbiased at pi != pi0 and at pi = pi0
        # (the latter is the classical w^2 formula)
        centers = np.array([[-1.5], [0.5]])
        pi0 = np.array([0.6, 0.4])
        a = -0.75
        for pi_test in (np.array([0.6, 0.4]), np.array([0.2, 0.8]), np.array([0.9, 0.1])):
            reference = self._m2_quad(centers.ravel(), pi_test, a)
            n, b = 4000, 60
            rng = np.random.default_rng(4242)
            ests = []
            for _ in range(b):
                z = draw_from_mixture(rng, centers, pi0, n)
                logq, logp, logr, ind = make_inputs(z, centers, pi0, a)
                ests.append(m2_hat(logq, logp, logr, ind, pi_test))
            _batch_bias(np.array(ests), reference)

    def test_mixed_pilot_pooling_unbiased(self):
        # pooled batches from DIFFERENT fixed sources r1 = p and r2 = q_{pi0}
        centers = np.array([[-1.5], [0.5]])
        pi0 = np.array([0.5, 0.5])
        pi_test = np.array([0.3, 0.7])
        a = -0.75
        reference = self._m2_quad(centers.ravel(), pi_test, a)
        n1, n2, b = 2000, 2000, 60
        rng = np.random.default_rng(4242)
        ests = []
        for _ in range(b):
            z1 = rng.standard_normal((n1, 1))                 # r = p
            z2 = draw_from_mixture(rng, centers, pi0, n2)     # r = q_{pi0}
            z = np.vstack([z1, z2])
            logq = component_log_densities(z, centers)
            logp = target_log_density(z)
            logr = np.concatenate([target_log_density(z1), mixture_log_density(
                component_log_densities(z2, centers), pi0)])
            ind = (z[:, 0] <= a).astype(float)
            ests.append(m2_hat(logq, logp, logr, ind, pi_test))
        _batch_bias(np.array(ests), reference)

    def test_no_events_raises(self):
        z = np.array([[3.0, 3.0]])          # far outside A = {z1 <= -1.1}
        centers = np.array([[-1.5, 0.0]])
        logq, logp, logr, ind = make_inputs(z, centers, np.array([1.0]), -1.1)
        assert ind.sum() == 0
        with pytest.raises(ValueError):
            m2_hat(logq, logp, logr, ind, np.array([1.0]))
        with pytest.raises(ValueError):
            m2_gradient(logq, logp, logr, ind, np.array([1.0]))
        with pytest.raises(ValueError):
            m2_hessian(logq, logp, logr, ind, np.array([1.0]))


# ---------------------------------------------------------------------------
# Task Sec. 29.4 -- analytic gradient / Hessian vs finite differences
# ---------------------------------------------------------------------------
class TestGradientAndHessianFD:
    def test_gradient_vs_directional_fd(self, fd_data):
        """Central FD along simplex tangent directions (module enforces simplex).

        Direction ``e_j - e_0``: FD of ``f`` vs analytic ``g_j - g_0``.
        """
        logq, logp, logr, ind = fd_data
        k = logq.shape[1]
        rng = np.random.default_rng(7)
        for _ in range(5):
            a = _interior(rng, k)
            g = m2_gradient(logq, logp, logr, ind, a)
            for j in range(1, k):
                d = np.zeros(k)
                d[j], d[0] = 1.0, -1.0
                h = 1e-6
                fp = m2_hat(logq, logp, logr, ind, a + h * d)
                fm = m2_hat(logq, logp, logr, ind, a - h * d)
                fd = (fp - fm) / (2.0 * h)
                assert fd == pytest.approx(g[j] - g[0], rel=1e-5, abs=1e-9)

    def test_hessian_symmetric_psd(self, fd_data):
        logq, logp, logr, ind = fd_data
        k = logq.shape[1]
        rng = np.random.default_rng(7)
        for _ in range(5):
            a = _interior(rng, k)
            H = m2_hessian(logq, logp, logr, ind, a)
            assert np.max(np.abs(H - H.T)) <= 1e-12    # symmetry
            eig = np.linalg.eigvalsh(H)
            assert eig.min() >= -1e-8                   # PSD
            for _v in range(200):
                v = rng.standard_normal(k)
                assert v @ H @ v >= -1e-10              # v^T H v >= 0 (T3, all v)

    def test_hessian_vs_fd_of_directional_gradient(self, fd_data):
        logq, logp, logr, ind = fd_data
        k = logq.shape[1]
        rng = np.random.default_rng(11)
        a = _interior(rng, k)
        H = m2_hessian(logq, logp, logr, ind, a)
        for _ in range(3):
            v = rng.standard_normal(k)
            v = v - v.mean()                            # simplex direction
            h = 1e-6
            gp = m2_gradient(logq, logp, logr, ind, a + h * v)
            gm = m2_gradient(logq, logp, logr, ind, a - h * v)
            fd = (gp - gm) / (2.0 * h)
            assert np.allclose(fd, H @ v, rtol=1e-4, atol=1e-8)

    def test_empirical_convexity_segments(self, fd_data):
        logq, logp, logr, ind = fd_data
        k = logq.shape[1]
        rng = np.random.default_rng(13)
        for _ in range(200):
            a = rng.dirichlet(np.ones(k) * 2.0)
            b = rng.dirichlet(np.ones(k) * 2.0)
            lam = rng.uniform(0.05, 0.95)
            mid = lam * a + (1.0 - lam) * b
            f_mid = m2_hat(logq, logp, logr, ind, mid)
            f_line = lam * m2_hat(logq, logp, logr, ind, a) + (
                1.0 - lam
            ) * m2_hat(logq, logp, logr, ind, b)
            assert f_mid <= f_line + 1e-9

    def test_identical_components_flat(self):
        # q1 == q2: objective constant along the simplex direction, H v = 0
        rng = np.random.default_rng(17)
        centers = np.array([[-1.5, 0.0], [-1.5, 0.0]])
        z = draw_from_mixture(rng, centers, np.array([0.5, 0.5]), 4000)
        logq, logp, logr, ind = make_inputs(z, centers, np.array([0.5, 0.5]), -1.1)
        f1 = m2_hat(logq, logp, logr, ind, np.array([0.7, 0.3]))
        f2 = m2_hat(logq, logp, logr, ind, np.array([0.3, 0.7]))
        assert f1 == pytest.approx(f2, abs=1e-12)
        H = m2_hessian(logq, logp, logr, ind, np.array([0.5, 0.5]))
        v = np.array([1.0, -1.0])
        assert abs(v @ H @ v) <= 1e-10


# ---------------------------------------------------------------------------
# Task Sec. 29.4 / 15 -- frozen SLSQP optimizer
# ---------------------------------------------------------------------------
class TestWeightOptimizer:
    def test_simplex_constraints_and_improvement(self, opt_data):
        logq, logp, logr, ind = opt_data
        pi0 = np.array([0.98, 0.01, 0.01])
        r = optimize_mixture_weights(logq, logp, logr, ind, pi0=pi0)
        assert r.success, r.message
        assert r.weights.sum() == pytest.approx(1.0, abs=1e-8)
        assert np.all(r.weights >= -1e-9)
        assert r.objective_final <= r.objective_init - 1e-8
        assert r.objective_final <= r.objective_init * 0.99  # real improvement
        assert r.kkt_residue <= 1e-6
        assert r.n_events >= 5

    def test_init_independence(self, opt_data):
        logq, logp, logr, ind = opt_data
        inits = [
            np.full(3, 1.0 / 3.0),
            np.array([0.98, 0.01, 0.01]),
            np.array([0.01, 0.98, 0.01]),
            np.array([0.33, 0.34, 0.33]),
        ]
        results = [optimize_mixture_weights(logq, logp, logr, ind, pi0=w) for w in inits]
        assert all(r.success for r in results)
        ref = results[0]
        for r in results[1:]:
            assert np.max(np.abs(r.weights - ref.weights)) <= 1e-6
            assert abs(r.objective_final - ref.objective_final) <= 1e-8

    def test_floor_honored(self, opt_data):
        logq, logp, logr, ind = opt_data
        r = optimize_mixture_weights(logq, logp, logr, ind, floor=0.05)
        assert r.success, r.message
        assert np.all(r.weights >= 0.05 - 1e-8)
        assert r.weights.sum() == pytest.approx(1.0, abs=1e-8)

    def test_no_events_optimizer_raises(self):
        logq, logp, logr, ind = make_inputs(
            np.array([[3.0, 3.0]]), np.array([[-1.5, 0.0]]), np.array([1.0]), -1.1
        )
        with pytest.raises(ValueError):
            optimize_mixture_weights(logq, logp, logr, ind)

    def test_kkt_residue_helper(self):
        # interior stationarity: constant gradient -> residue 0
        assert kkt_residue(np.array([1.0, 1.0]), np.array([0.5, 0.5])) == pytest.approx(0.0)
        # boundary: second component at floor still pushing down -> violation
        res = kkt_residue(np.array([-2.0, -5.0]), np.array([1.0, 0.0]), floor=0.0)
        assert res > 0.0
        # satisfied boundary: g[active] >= rho
        assert kkt_residue(np.array([-2.0, 1.0]), np.array([1.0, 0.0]), floor=0.0) == pytest.approx(0.0)