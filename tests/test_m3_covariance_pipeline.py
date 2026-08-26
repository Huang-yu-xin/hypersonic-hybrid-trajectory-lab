"""M3 -- preregistered unit tests (task Sec. 29, all fifteen names).

Fast, deterministic; every quadrature probe uses a small-but-verified node
count.  These tests pin:
    analytic gradient identities (matrix + isotropic),
    responsibility algebra,
    estimator formulas incl. the mu_r normalisation regression,
    bootstrap strata discipline,
    ESS floor wiring,
    WIDEN/SHRINK/HOLD decision precedence,
    fixed-weight Layer A lock,
    counterfactual CRN structure,
    estimator isolation from final-evaluation machinery,
    machine-readable record schema.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from hyptraj.m1.proposal_update import MixtureProposal          # noqa: E402
from hyptraj.m3 import covariance_gradient as cg               # noqa: E402
from hyptraj.m3 import direction_policy as dp                  # noqa: E402
from hyptraj.m3 import metrics as m3m                          # noqa: E402
from hyptraj.m2.covariance_policy import (                     # noqa: E402
    CovGaussianMixtureProposal, add_component_cov, proposal_from_frozen,
)
from hyptraj.m3.gradient_estimator import (                    # noqa: E402
    scalar_gradient_estimate, stratified_bootstrap_gradient_ci,
    variance_mass_importance,
)

H_FD = 1e-3


# --------------------------------------------------------------------------- #
# shared small fixtures
# --------------------------------------------------------------------------- #
def _toy_single(reach=9.0, n=160):
    """p = N([1,0], diag(1.44,.64)); q0 single unit comp; A half-space."""
    p_spec = cg.MixtureSpec(np.array([1.0]), np.array([[1.0, 0.0]]),
                            (np.diag([1.44, 0.64]),))
    lp = lambda zz: cg.mixture_log_density(p_spec, zz)  # noqa: E731

    def reg(zz):
        return zz[:, 0] >= 0.4

    spec = cg.MixtureSpec(np.array([1.0]), np.zeros((1, 2)), (np.eye(2),))
    return spec, lp, reg, reach, n


# --------------------------------------------------------------------------- #
# 1 -- Gaussian log-density covariance derivative
# --------------------------------------------------------------------------- #
def test_m3_gaussian_covariance_loggrad():
    rng = np.random.default_rng(11)
    sig = np.array([[0.8, 0.15], [0.15, 1.30]])
    m = np.array([0.4, -0.7])
    pts = rng.normal(size=(6, 2))

    def logpdf(x, s):
        inv = np.linalg.inv(s)
        dlt = x - m
        q = np.einsum("ni,ij,nj->n", dlt, inv, dlt)
        return -0.5 * (2 * np.log(2 * np.pi) + np.linalg.slogdet(s)[1]) \
            - 0.5 * q

    grad = -0.5 * (np.linalg.inv(sig)[None] - _batch_outer_inv(pts - m,
                                                              np.linalg.inv(sig)))
    for i in range(pts.shape[0]):
        for (a, b) in ((0, 0), (0, 1), (1, 1)):
            E = np.zeros((2, 2))
            E[a, b] = E[b, a] = 1.0
            fd = (logpdf(pts[i:i + 1], sig + H_FD * E)
                  - logpdf(pts[i:i + 1], sig - H_FD * E)) / (2 * H_FD)
            ana = float(np.sum(grad[i] * E))
            assert abs(fd[0] - ana) <= 5e-3 * max(abs(ana), 1e-9)

    # classic identity: contracting with Sigma reproduces the quadratic score
    delta = (pts - m)
    quad = np.einsum("ni,ij,nj->n", delta, np.linalg.inv(sig), delta)
    contraction = float(np.sum(
        (-0.5 * (np.linalg.inv(sig)
                 - np.linalg.inv(sig) @ _outer(delta[0], delta[0])
                 @ np.linalg.inv(sig))) * sig))
    assert abs(contraction - (-1.0 + 0.5 * quad[0])) < 1e-10


def _outer(a, b):
    return np.outer(a, b)


def _batch_outer_inv(dlt, inv):
    out = np.empty((dlt.shape[0], dlt.shape[1], dlt.shape[1]))
    for i in range(dlt.shape[0]):
        out[i] = inv @ _outer(dlt[i], dlt[i]) @ inv
    return out


# --------------------------------------------------------------------------- #
# 2 -- responsibility identity
# --------------------------------------------------------------------------- #
def test_m3_mixture_responsibility():
    spec = cg.MixtureSpec(np.array([0.30, 0.70]),
                          np.array([[-1.0, 0.2], [1.0, -0.2]]),
                          (np.eye(2), 0.64 * np.eye(2)))
    xs = np.linspace(-4, 4, 23)
    grid = np.stack(np.meshgrid(xs, xs, indexing="ij"), axis=-1).reshape(-1, 2)
    r0 = cg.component_responsibility(spec, grid, 0)
    r1 = cg.component_responsibility(spec, grid, 1)
    assert np.all(r0 >= 0) and np.all(r0 <= 1)
    assert np.max(np.abs(r0 + r1 - 1.0)) < 1e-12
    logq = cg.mixture_log_density(spec, grid)
    from hyptraj.m3.gradient_estimator import component_responsibility as cr
    del cr
    # ratio form pi_k q_k / q matches the stable implementation
    diff = grid - spec.means[1]
    inv = np.linalg.inv(spec.covs[1])
    _, ld = np.linalg.slogdet(spec.covs[1])
    logq1 = np.log(spec.pi[1]) - 0.5 * (2 * np.log(2 * np.pi) + ld) \
        - 0.5 * np.einsum("ni,ij,nj->n", diff, inv, diff)
    r_direct = np.exp(logq1 - logq)
    assert np.allclose(r_direct, r1, rtol=1e-12)


# --------------------------------------------------------------------------- #
# 3 -- matrix gradient vs finite differences (toy)
# --------------------------------------------------------------------------- #
def test_m3_matrix_gradient_toy():
    spec, lp, reg, reach, n = _toy_single()
    mom = cg.variance_measure_moments(spec, 0, lp, reg, reach, n_per_axis=n)
    s0 = spec.covs[0]
    floor = 1e-9 * max(1.0, float(np.max(np.abs(mom.grad_matrix))))
    for name, E in _sym_dirs().items():
        fd = cg.directional_finite_difference(lp, reg, spec, 0, s0, E,
                                              H_FD, reach, n_per_axis=n)
        ana = float(np.sum(mom.grad_matrix * E))
        if max(abs(fd), abs(ana)) <= floor:
            continue
        assert np.sign(fd) == np.sign(ana)
        assert abs(fd - ana) <= 5e-3 * max(abs(ana), floor)


def _sym_dirs():
    return {
        "isotropic": np.eye(2) / np.sqrt(2.0),
        "e00": np.eye(2),
        "e11": np.array([[0.0, 0.0], [0.0, 1.0]]),
        "offdiag_sym": np.array([[0.0, 0.5], [0.5, 0.0]]) / np.linalg.norm(
            np.array([[0.0, 0.5], [0.5, 0.0]])),
    }


# --------------------------------------------------------------------------- #
# 4 -- isotropic derivative vs theta-path finite differences
# --------------------------------------------------------------------------- #
def test_m3_isotropic_gradient_toy():
    spec, lp, reg, reach, n = _toy_single()
    s2 = 1.21
    spec_iso = cg.with_component_covariance(spec, 0, s2 * np.eye(2))
    mom = cg.variance_measure_moments(spec_iso, 0, lp, reg, reach,
                                      n_per_axis=n)
    up = cg.m2_of_sigma(lp, reg, spec, 0, s2 * np.exp(H_FD) * np.eye(2),
                        reach, n_per_axis=n)
    dn = cg.m2_of_sigma(lp, reg, spec, 0, s2 * np.exp(-H_FD) * np.eye(2),
                        reach, n_per_axis=n)
    fd = (up - dn) / (2 * H_FD)
    assert np.sign(fd) == np.sign(mom.g_isotropic)
    assert abs(fd - mom.g_isotropic) <= 5e-3 * abs(mom.g_isotropic)


# --------------------------------------------------------------------------- #
# 5 -- finite-difference helpers + exactness anchor
# --------------------------------------------------------------------------- #
def test_m3_gradient_finite_difference():
    assert cg.safe_relative_error(1.0, 1.001) == pytest.approx(0.001)
    # tiny denominators are guarded only by the caller-level structural-zero
    # floor; against a 1e-30 floor a 1e-12 offset legitimately explodes,
    # while the mirrored direction (analytic 1e-12 vs fd 0) reads as full
    # relative disagreement of exactly 1.0
    assert cg.safe_relative_error(0.0, 1e-12) > 1e15
    assert cg.safe_relative_error(1e-12, 0.0) == pytest.approx(1.0)
    # identity anchor: p == q single standard Gaussian full plane -> M2 == 1
    p_spec = cg.MixtureSpec(np.array([1.0]), np.zeros((1, 2)), (np.eye(2),))
    lp = lambda zz: cg.mixture_log_density(p_spec, zz)   # noqa: E731
    spec = cg.MixtureSpec(np.array([1.0]), np.zeros((1, 2)), (np.eye(2),))
    reg_full = lambda zz: np.ones(zz.shape[0], dtype=bool)  # noqa: E731
    mom = cg.variance_measure_moments(spec, 0, lp, reg_full, 8.0, 160)
    assert abs(mom.M2 - 1.0) < 1e-7
    assert np.max(np.abs(mom.grad_matrix)) < 1e-6
    assert abs(mom.g_isotropic) < 1e-6


# --------------------------------------------------------------------------- #
# 6 -- stratified-pilot scalar estimator (incl. frozen-family cross-check)
# --------------------------------------------------------------------------- #
def _synthetic_pilot(seed=2026, n=4000, alpha=0.5, s2=1.21):
    p_spec = cg.MixtureSpec(np.array([1.0]), np.array([[1.6, 0.0]]),
                            (np.diag([1.0, 1.0]),))
    lp = lambda zz: cg.mixture_log_density(p_spec, zz)  # noqa: E731

    def reg(zz):
        return zz[:, 0] >= 0.8

    spec = cg.MixtureSpec(np.array([1.0]), np.zeros((1, 2)),
                          (float(s2) * np.eye(2),))
    rng = np.random.default_rng([seed, 101])
    n_p = int(round(n * alpha))
    n_q = n - n_p
    zp = rng.standard_normal((n_p, 2))
    eps = rng.standard_normal((n_q, 2))
    zq = spec.means[0][None, :] + eps @ np.linalg.cholesky(
        float(s2) * np.eye(2)).T
    z = np.vstack([zp, zq])
    logr = np.concatenate([lp(zp), cg.mixture_log_density(spec, zq)])
    strata = np.concatenate([np.zeros(n_p, int), np.ones(n_q, int)])
    return spec, lp, reg, z, logr, strata


def test_m3_stratified_gradient_estimator():
    s2 = 1.21
    spec, lp, reg, z, logr, strata = _synthetic_pilot(s2=s2)
    logp = np.asarray(lp(z))
    ind = reg(z).astype(float)
    a = variance_mass_importance(z, spec.pi, spec.means, list(spec.covs),
                                 logp, logr, ind)
    resp = cg.component_responsibility(spec, z, 0)
    sq = np.einsum("ni,ni->n", z - spec.means[0], z - spec.means[0])
    est = scalar_gradient_estimate(a, resp, sq, s2=s2, dim=2)
    assert est["valid_pointwise"]
    assert 0.0 < est["mu_r_hat"] <= 1.0 + 1e-12      # ab-normalised mass
    truth = cg.pooled_design_moments(spec, 0, lp, reg, 12.0, alpha=0.5)
    assert np.sign(est["g_hat"]) == np.sign(truth["g_isotropic"])
    # frozen cross-check on the all-unit family: estimator importance values
    # must match hyptraj.m1.variance_mass_weights bit-for-bit-ish there.
    spec_unit = cg.MixtureSpec(spec.pi.copy(), spec.means.copy(), (np.eye(2),))
    a_u = variance_mass_importance(z, spec_unit.pi, spec_unit.means,
                                   [np.eye(2)], logp, logr, ind)
    from hyptraj.m1.variance_measure import variance_mass_weights
    a_frozen = variance_mass_weights(z, spec_unit.means, spec_unit.pi,
                                     logp, logr, ind)
    assert np.allclose(a_u, a_frozen, rtol=1e-9, atol=1e-250)


# --------------------------------------------------------------------------- #
# 7 -- stratified bootstrap CI discipline
# --------------------------------------------------------------------------- #
def test_m3_gradient_bootstrap():
    s2 = 1.21
    spec, lp, reg, z, logr, strata = _synthetic_pilot(seed=2027, s2=s2)
    logp = np.asarray(lp(z))
    ind = reg(z).astype(float)
    a = variance_mass_importance(z, spec.pi, spec.means, list(spec.covs),
                                 logp, logr, ind)
    resp = cg.component_responsibility(spec, z, 0)
    sq = np.einsum("ni,ni->n", z - spec.means[0], z - spec.means[0])
    ci = stratified_bootstrap_gradient_ci(
        a, resp, sq, strata, s2=s2, dim=2, n_bootstrap=120,
        bootstrap_seed_key=(2027, 424243))
    assert ci["g_ci_low"] <= ci["g_ci_high"]
    assert ci["strata_sizes"] == {0: int((strata == 0).sum()),
                                  1: int((strata == 1).sum())}
    boot_again = stratified_bootstrap_gradient_ci(
        a, resp, sq, strata, s2=s2, dim=2, n_bootstrap=120,
        bootstrap_seed_key=(2027, 424243))
    assert boot_again["g_ci_low"] == ci["g_ci_low"]
    assert boot_again["g_ci_high"] == ci["g_ci_high"]


# --------------------------------------------------------------------------- #
# 8 -- gradient ESS extremes + threshold wiring
# --------------------------------------------------------------------------- #
def test_m3_gradient_ess():
    n = 500
    a = np.ones(n)
    sq = np.full(n, 2.0)
    resp_uniform = np.full(n, 0.5)
    est_uniform = scalar_gradient_estimate(a, resp_uniform, sq, s2=1.0, dim=2)
    assert est_uniform["ESS_grad"] > 0.99 * n
    resp_spike = np.zeros(n); resp_spike[3] = 1.0
    est_spike = scalar_gradient_estimate(a, resp_spike, sq, s2=1.0, dim=2)
    assert est_spike["ESS_grad"] < 1.5
    rule = dp.DirectionRule(ess_min=20.0)
    assert rule.decide(validity_ok=True, ess_grad=19.999,
                       g_ci_low=-5, g_ci_high=-1) == dp.HOLD_LOW_ESS
    assert rule.decide(validity_ok=True, ess_grad=20.0001,
                       g_ci_low=-5, g_ci_high=-1) == dp.WIDEN


# --------------------------------------------------------------------------- #
# 9/10/11 -- direction rules
# --------------------------------------------------------------------------- #
def test_m3_direction_rule_widen():
    rule = dp.DirectionRule()
    assert rule.decide(validity_ok=True, ess_grad=100, g_ci_low=-3.0,
                       g_ci_high=-0.2) == dp.WIDEN
    assert dp.step_sign_for(dp.WIDEN, 0.20) == +0.20


def test_m3_direction_rule_shrink():
    rule = dp.DirectionRule()
    assert rule.decide(validity_ok=True, ess_grad=100, g_ci_low=0.05,
                       g_ci_high=2.5) == dp.SHRINK
    assert dp.step_sign_for(dp.SHRINK, 0.20) == -0.20


def test_m3_direction_rule_hold():
    rule = dp.DirectionRule()
    # precedence: INVALID beats everything, LOW_ESS beats the CI rule
    assert rule.decide(validity_ok=False, ess_grad=1e6, g_ci_low=-9,
                       g_ci_high=-1) == dp.HOLD_INVALID
    assert rule.decide(validity_ok=True, ess_grad=5, g_ci_low=-9,
                       g_ci_high=-1) == dp.HOLD_LOW_ESS
    # CI containing zero -> uncertain regardless of point sign
    assert rule.decide(validity_ok=True, ess_grad=50, g_ci_low=-1.0,
                       g_ci_high=2.0) == dp.HOLD_UNCERTAIN
    assert dp.step_sign_for(dp.HOLD_UNCERTAIN, 0.20) == 0.0
    assert dp.step_sign_for(dp.HOLD_LOW_ESS, 0.20) == 0.0
    assert dp.step_sign_for(dp.HOLD_INVALID, 0.20) == 0.0
    # evaluation-best direction semantics
    assert dp.evaluation_best_direction(2.0, 1.90, 2.5, 0.01) == "WIDEN"
    assert dp.evaluation_best_direction(2.0, 2.0, 1.97, 0.01) == "SHRINK"
    assert dp.evaluation_best_direction(2.0, 1.995, 2.0, 0.01) == "HOLD"


# --------------------------------------------------------------------------- #
# 12 -- fixed-weight Layer A construction lock
# --------------------------------------------------------------------------- #
def test_m3_fixed_weight_layer():
    base_frozen = MixtureProposal(centers=np.array([[0.0, 0.0], [2.0, 0.0]]),
                                  weights=np.array([0.6, 0.4]),
                                  component_mode_ids=("NOMINAL", "M1"))
    prop = proposal_from_frozen(base_frozen, dim=2)
    sigma_new = 1.44 * np.eye(2)
    grown = add_component_cov(prop, center=np.array([1.0, -1.0]),
                              sigma_new=sigma_new, mode_id="M2",
                              pi_fallback=0.5)
    assert grown.n_components == 3
    assert np.allclose(grown.weights,
                       np.array([0.3, 0.2, 0.5]))       # joint (1-a)+a split
    assert np.allclose(grown.covs[0], np.eye(2))
    assert np.allclose(grown.covs[1], np.eye(2))
    assert np.allclose(grown.covs[2], sigma_new)
    assert np.allclose(grown.centers[:2], base_frozen.centers)
    assert grown.component_mode_ids[-1] == "M2"
    # legality metadata re-recorded through the FROZEN constant discipline
    assert grown.min_eig_sigma_minus_halfI >= (
        min(prop.min_eig_sigma_minus_halfI,
            float(np.linalg.eigvalsh(sigma_new)[0]) - 0.5) - 1e-15)


# --------------------------------------------------------------------------- #
# 13 -- counterfactual CRN stream alignment
# --------------------------------------------------------------------------- #
def test_m3_counterfactual_crn():
    centers = np.array([[0.0, 0.0], [2.0, 1.0]])
    weights = np.array([0.55, 0.45])
    cov_base = np.eye(2)
    arms = {}
    for tag, scale in (("base", 1.0), ("widen", float(np.exp(+0.20))),
                       ("shrink", float(np.exp(-0.20)))):
        prop = CovGaussianMixtureProposal(
            centers=centers, weights=weights,
            covs=(scale * cov_base, cov_base))
        rng = np.random.default_rng([2026, 900_001])
        arms[tag] = prop.sample(rng, 40)
        # independent extraction of the SAME underlying streams, then a
        # PER-SELECTED-COMPONENT transform replicating the sampling contract
        rng2 = np.random.default_rng([2026, 900_001])
        comp = rng2.choice(2, size=40, p=weights)
        eps = rng2.standard_normal((40, 2))
        chols = [np.linalg.cholesky(scale * cov_base), np.eye(2)]
        tf = np.einsum("njk,nk->nj", np.stack([chols[c] for c in comp]), eps)
        manual = centers[comp] + tf
        assert np.allclose(arms[tag], manual, atol=1e-13)
    # all three arms consume identical generator streams by construction;
    # their outputs differ ONLY through the selected component's scaling.
    assert not np.allclose(arms["base"], arms["widen"])
    assert not np.allclose(arms["base"], arms["shrink"])


# --------------------------------------------------------------------------- #
# 14 -- estimator isolation from final-evaluation machinery
# --------------------------------------------------------------------------- #
def test_m3_no_final_eval_leakage():
    # structural: estimation entry points take NO evaluation-set/rng argument
    # and no benchmark object at all -- pilot arrays are the entire universe.
    for fn in (scalar_gradient_estimate, stratified_bootstrap_gradient_ci):
        params = set(inspect.signature(fn).parameters)
        assert not ({"rng", "eval", "bench_cfg", "proposal"} & params), fn
    # pipeline separation constants locked apart (driver-level contract)
    cfg = json.loads((REPO / "configs" / "phase_m3"
                      / "m3_scalar_gradient_v0.json").read_text(encoding="utf-8"))
    pilot_tag = 101      # default_rng([seed, 101]) frozen pilot key
    eval_tag = int(cfg["protocol_locked"]["eval_rng_tag"])         # 900001
    boot_rule = cfg["bootstrap_locked"]["bootstrap_seed_rule"]
    assert eval_tag != pilot_tag
    assert "424243" in boot_rule and "101" not in boot_rule.replace("[seed,", "")


# --------------------------------------------------------------------------- #
# 15 -- machine-readable schema
# --------------------------------------------------------------------------- #
def _tags():
    return {"h3": "RareTopo-H3-v1.0", "m1": "RareTopo-M1-v0",
            "m1d": "RareTopo-M1-D-v1.0", "m2": "RareTopo-M2-v0"}


def _fake_record(hit: bool, active: bool = True):
    dec = "WIDEN" if active else "HOLD_UNCERTAIN"
    best = "WIDEN" if hit else "SHRINK"
    rec = m3m.build_trial_record(
        tags=_tags(), config_id="c000", seed=2026, selected_mode="Sx",
        component_index=2, layer="fixed_weights",
        gradient={"M2_hat": 10.0, "responsibility_mass": 0.4, "D_hat": 2.6,
                  "g_hat": -1.2, "g_ci_low": -2.0, "g_ci_high": -0.5,
                  "ESS_grad": 88.0, "decision": dec},
        counterfactual={"delta_theta": 0.20, "M2_base": 10.0,
                        "M2_widen": 8.0, "M2_shrink": 12.0,
                        "M2_pred": 8.0, "M2_opposite": 12.0,
                        "evaluation_best_direction":
                            best if active else "HOLD"},
        m2_diagnostic={"hdr_covariance": [[1, 0], [0, 1]], "hdr_trace": 2.0},
        evaluation={"P_hat": 0.5, "VRF_proposal": 3.2, "VRF_budget": 1.1,
                    "mode_L": {"M1": 1.0, "M2": 0.5},
                    "mode_L_base": {"M1": 1.0}, "mode_L_pred": {"M1": 1.4},
                    "n": 100000, "scientific_audit_calls": 320000,
                    "deployable_method_calls": 120000},
        validity={"selected_mode_lock": True})
    return rec


def test_m3_result_schema():
    required_top = ["schema_version", "h3_tag", "m1_tag", "m1d_tag", "m2_tag",
                    "config_id", "seed", "selected_mode", "component_index",
                    "layer", "gradient", "counterfactual", "m2_diagnostic",
                    "evaluation", "validity"]
    grad_keys = ["M2_hat", "responsibility_mass", "D_hat", "g_hat",
                 "g_ci_low", "g_ci_high", "ESS_grad", "decision"]
    cf_keys = ["delta_theta", "M2_base", "M2_widen", "M2_shrink",
               "M2_pred", "M2_opposite", "evaluation_best_direction"]
    ev_keys = ["P_hat", "VRF_proposal", "VRF_budget", "mode_L"]

    hit = _fake_record(True)
    miss = _fake_record(False, active=False)
    for rec in (hit, miss):
        for k in required_top:
            assert k in rec, f"missing top-level {k}"
        for k in grad_keys:
            assert k in rec["gradient"], f"missing gradient.{k}"
        for k in cf_keys:
            assert k in rec["counterfactual"], f"missing counterfactual.{k}"
        for k in ev_keys:
            assert k in rec["evaluation"], f"missing evaluation.{k}"
        assert rec["schema_version"] == "raretopo-m3-v0"
        assert rec["layer"] == "fixed_weights"
        assert rec["gradient"]["decision"] in dp.DECISIONS

    agg = m3m.aggregate_gate_quantities([hit, miss])
    assert agg["n_trials"] == 2
    assert agg["n_active"] == 1
    assert agg["acc_dir"] == pytest.approx(1.0)     # the only active is correct
    assert agg["rate_M2_pred_lt_base"] == pytest.approx(1.0)
    assert agg["median_ratio_pred_opposite"] == pytest.approx(8.0 / 12.0)
    assert agg["configs_within_leak_ratio_2"] >= 0
