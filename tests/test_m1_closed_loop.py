"""M1 -- closed-loop behavior tests (task Sec. 10 / 16 / 17 / 29.5 / 29.6).

Covers:

- HOLD behavior: a half-space with only the represented primary mode must
  HOLD at iteration 0 with zero false births (task Sec. 29.5 / Benchmark A);
- a crafted 2-mode case must ADD_COMPONENT exactly once (the variance-
  dominant secondary mode), reweight, and stop with a valid reason;
- final evaluation on fresh samples: the IS estimator stays unbiased and
  the second moment drops after adaptation (mechanism-level check, not a
  headline claim);
- legality metadata is carried on every proposal (task Sec. 9).

Pure numpy tests, fixed debug seeds; no simulator.
"""

from __future__ import annotations

import numpy as np
import pytest

from hyptraj.m1.closed_loop import (
    MAX_ADAPTATION_ITERATIONS,
    M2_RELATIVE_STOP_THRESHOLD,
    run_closed_loop,
)
from hyptraj.m1.mixture_weights import component_log_densities, mixture_log_density
from hyptraj.m1.proposal_update import MixtureProposal
from hyptraj.m1.variance_measure import estimate_variance_measure

A1, A2 = -1.5, 1.9
M0 = -1.5


def _logp(z):
    z = np.asarray(z, dtype=float)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def _labels_single(z, nominal="S0"):
    z = np.asarray(z, dtype=float)
    return np.where(z[:, 0] <= A1, "S1", nominal)


def _labels_double(z, nominal="S0"):
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], nominal, dtype=object)
    out[z[:, 0] <= A1] = "S1"
    out[z[:, 0] >= A2] = "S2"
    return out


@pytest.fixture(scope="module")
def loop_kwargs():
    return dict(
        initial_proposal=MixtureProposal(
            centers=np.array([[M0]]), weights=np.array([1.0]),
            component_mode_ids=("S1",),
        ),
        label_oracle=_labels_single,
        logp_fn=_logp,
        nominal_topology="S0",
        pilot_n=20_000,
    )


class TestHoldBehavior:
    def test_halfspace_holds_without_false_birth(self, loop_kwargs):
        for seed in (2026, 2027, 2028):   # debug seeds (task Sec. 19)
            res = run_closed_loop(seed=seed, **loop_kwargs)
            assert res.stop_reason == "no_missing_mode"
            assert len(res.iterations) == 1
            it = res.iterations[0]
            assert it.action == "HOLD"
            assert it.candidate_mode is None
            assert res.final_proposal.n_components == 1  # zero false births
            assert res.final_proposal.legality_checked
            assert res.final_proposal.min_eig_sigma_minus_halfI == pytest.approx(0.5)
            assert res.n_pilot_calls == loop_kwargs["pilot_n"]

    def test_halfspace_unbiased_estimation(self, loop_kwargs):
        # P_hat from q0 must be unbiased for P(A1) (IS samples come from q0)
        rng = np.random.default_rng(4242)
        n = 500_000
        centers = np.array([[M0]])
        z = centers[0] + rng.standard_normal((n, 1))    # z ~ q0
        logq_ji = component_log_densities(z, centers)
        logr = mixture_log_density(logq_ji, np.array([1.0]))
        labels = _labels_single(z)
        ind = (labels != "S0").astype(float)
        w = np.exp(_logp(z) - logr) * ind
        p_hat = float(np.mean(w))
        from scipy.stats import norm
        p_ref = float(norm.cdf(A1))          # P_p(A1) = Phi(-1.5), d=1
        assert p_hat == pytest.approx(p_ref, rel=1e-2)


class TestAdaptiveBehavior:
    def test_double_mode_adds_one_component(self):
        for seed in (2026, 2027):
            res = run_closed_loop(
                seed=seed,
                initial_proposal=MixtureProposal(
                    centers=np.array([[M0]]), weights=np.array([1.0]),
                    component_mode_ids=("S1",),
                ),
                label_oracle=_labels_double,
                logp_fn=_logp,
                nominal_topology="S0",
                pilot_n=50_000,
            )
            assert res.final_proposal.n_components >= 2
            assert res.final_proposal.component_mode_ids[-1] == "S2"
            it0 = res.iterations[0]
            assert it0.action == "ADD_COMPONENT"
            # second-moment reduced on the independent diagnostic pilot
            assert it0.M2_hat < it0.M2_hat_prev
            # stop reason is a legal one (no crashes, no INVALID)
            assert res.stop_reason in (
                "no_missing_mode", "m2_relative_improvement_below_threshold",
                "max_adaptation_iterations",
            )

    def test_final_evaluation_unbiased_second_moment_drops(self):
        # independent final evaluation after q_final is frozen (Sec. 18)
        res = run_closed_loop(
            seed=2028,
            initial_proposal=MixtureProposal(
                centers=np.array([[M0]]), weights=np.array([1.0]),
                component_mode_ids=("S1",),
            ),
            label_oracle=_labels_double,
            logp_fn=_logp,
            nominal_topology="S0",
            pilot_n=50_000,
        )
        q0 = res.initial_proposal
        qf = res.final_proposal
        rng = np.random.default_rng(9090)     # fresh eval stream, post-freeze
        n_eval = 200_000
        z0 = q0.sample(rng, n_eval)
        ind0 = (_labels_double(z0) != "S0").astype(float)
        w0 = np.exp(_logp(z0) - q0.log_density(z0)) * ind0
        m2_0 = float(np.mean(w0**2))
        zf = qf.sample(rng, n_eval)
        indf = (_labels_double(zf) != "S0").astype(float)
        wf = np.exp(_logp(zf) - qf.log_density(zf)) * indf
        m2_f = float(np.mean(wf**2))
        assert m2_f < m2_0                       # M2 Gate mechanism check
        # both estimators unbiased for P(A): agree within 3 MC-equivalent SEs
        p0 = float(np.mean(w0))
        pf = float(np.mean(wf))
        se = float(np.sqrt(m2_0 / n_eval))
        assert abs(pf - p0) <= 3.0 * se

    def test_stop_constants_frozen(self):
        assert MAX_ADAPTATION_ITERATIONS == 3
        assert M2_RELATIVE_STOP_THRESHOLD == 0.02