"""M3 -- finite-sample second-moment gradient estimation on the shared M1-D
pilot (task Sec. 8-10).

Everything consumes ONLY pilot quantities (samples, their RECORDED source
density ``logr`` at draw time, target logp evaluated on those samples, and the
mixed-pilot strata).  Final-evaluation data structurally cannot enter: this
module's API has no evaluation-set argument and never calls a benchmark
object -- mirrors the M2 firewall discipline.

Formulas locked by configs/phase_m3/m3_scalar_gradient_v0.json:

    a_i      = 1_A(x_i) p(x_i)^2 / (q(x_i) r_i(x_i))       (frozen var-mass IS)
    a_bar    = a / sum(a)
    rhat_ki  = pi_k q_k(x_i)/q(x_i)                        (responsibility)
    mu_r     = sum ab*rhat ;  D = sum ab*rhat*||x-m||^2 / mu_r
    g        = (M2/2)*mu_r*(dim - D/s_k^2),   theta=log s^2
    c_i      = ab*rhat / sum(ab*rhat);  ESS_grad = 1/sum(c^2)

Bootstrap: FROZEN fixed-stratified scheme (resample WITHIN each source
stratum, preserve stratum sizes exactly -- same discipline as
hyptraj.m1.variance_measure.omega_bootstrap_lcb); 95% percentile CI of g.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.m3.covariance_gradient import (
    MixtureSpec,
    component_responsibility,
    mixture_log_density,
)


def _spec(pi, means, covs) -> MixtureSpec:
    return MixtureSpec(np.asarray(pi, float), np.asarray(means, float),
                       tuple(np.asarray(c, float) for c in covs))


def variance_mass_importance(z, spec_pi, spec_means, spec_covs,
                             logp, logr, indicators) -> np.ndarray:
    """``a_i = 1_A p^2/(q r_i)`` with general component covariances.

    Cross-checked bit-for-bit against the FROZEN unit-family implementation
    whenever every covariance is exactly I_dim (raises on mismatch).
    """
    z = np.asarray(z, dtype=float)
    logq = mixture_log_density(_spec(spec_pi, spec_means, spec_covs), z)
    a = np.exp(2.0 * np.asarray(logp, float) - logq
               - np.asarray(logr, float)) * np.asarray(indicators, float)
    if np.allclose([np.asarray(c, float) for c in spec_covs],
                   stack_identity(len(spec_covs), z.shape[1])[None],
                   rtol=1e-12, atol=0):
        from hyptraj.m1.variance_measure import variance_mass_weights
        a_frozen = variance_mass_weights(
            z, np.asarray(spec_means, float), np.asarray(spec_pi, float),
            np.asarray(logp, float), np.asarray(logr, float),
            np.asarray(indicators, float))
        if not np.allclose(a, a_frozen, rtol=1e-9, atol=1e-250):
            raise RuntimeError("unit-family importance deviates from frozen "
                               "variance_mass_weights")
    return a


def stack_identity(k: int, dim: int) -> np.ndarray:
    return np.stack([np.eye(dim)] * k)


def scalar_gradient_estimate(
    a: np.ndarray,
    resp_k: np.ndarray,
    sq_radius: np.ndarray,
    s2: float,
    dim: int,
) -> dict:
    """Point estimates ``(M2_hat, mu_r, D, g, ESS_grad, validity)`` from
    precomputed per-sample factors (task Sec. 8-9 formulas, no I/O)."""
    a = np.asarray(a, float)
    resp = np.asarray(resp_k, float)
    sq = np.asarray(sq_radius, float)
    n = a.size
    mass = float(a.sum())
    finite = bool(np.all(np.isfinite(a)) and np.all(np.isfinite(resp))
                  and np.all(np.isfinite(sq)))
    problems: list[str] = []
    if not finite:
        problems.append("non_finite_inputs")
    if not (mass > 0.0):
        problems.append("zero_variance_mass_sum_a")

    m2 = mass / n                      # M2_hat = (1/N) * sum a      (task Sec. 8)
    ar = a * resp
    total_ar = float(ar.sum())         # mu_r = sum_i ab_i rhat_i    (task Sec. 8)
    if total_ar <= 0.0 or not np.isfinite(total_ar):
        problems.append("zero_responsibility_mass_mu_r")
    ab = a / mass if mass > 0 else np.full(n, np.nan)
    c = ar / total_ar if total_ar > 0 else np.full(n, np.nan)
    ess = float(1.0 / np.sum(c ** 2)) if (total_ar > 0 and
                                          np.all(np.isfinite(c))) else float("nan")
    # NOTE: responsibility_mass is taken over NORMALISED weights,
    # mu_r = sum_i ab_i rhat_i with sum(ab) == 1 -- no extra 1/N, no raw
    # unnormalised sum; both mistakes corrupt D_hat/g_hat scaling (caught by
    # sanity-S3 before any benchmark run could consume them).
    mu_r = float(total_ar / mass) if (total_ar > 0 and mass > 0) \
        else float("nan")
    if mu_r is not None and np.isfinite(mu_r) and mu_r > 0:
        d_hat = float((ab * resp * sq).sum() / mu_r)
    else:
        d_hat = float("nan")
    g = float(m2 / 2.0 * mu_r * (dim - d_hat / s2)) \
        if (np.isfinite(mu_r) and np.isfinite(d_hat)) else float("nan")
    if not np.isfinite(g):
        problems.append("non_finite_g")
    return {
        "M2_hat": m2,
        "mu_r_hat": mu_r,
        "D_hat": d_hat,
        "g_hat": g,
        "ESS_grad": ess,
        "n": int(n),
        "valid_pointwise": len(problems) == 0,
        "problems": problems,
    }


def stratified_bootstrap_gradient_ci(
    a_full: np.ndarray,
    resp_k: np.ndarray,
    sq_radius: np.ndarray,
    source_strata: np.ndarray,
    s2: float,
    dim: int,
    n_bootstrap: int = 500,
    bootstrap_seed_key: tuple[int, int] | None = None,
    ci_level: float = 0.95,
) -> dict:
    """Frozen fixed-stratified bootstrap CI for ``g`` (task Sec. 10).

    Each replicate resamples WITHIN each source stratum at preserved size,
    recomputes the FULL point pipeline (mass normalisation included) and the
    percentiles of the replicate distribution become the CI.  Responsibilities
    and squared radii are functions of the fixed sample points, hence reused;
    everything derived from the weights is recomputed per replicate."""
    a_full = np.asarray(a_full, float)
    resp = np.asarray(resp_k, float)
    sq = np.asarray(sq_radius, float)
    strata = np.asarray(source_strata).astype(int)
    n = a_full.size
    if strata.size != n:
        raise ValueError("source_strata length mismatch")
    rng = np.random.default_rng(list(bootstrap_seed_key)
                                if bootstrap_seed_key is not None
                                else [2026, 424243])

    strata_ids = np.unique(strata)
    sub_idx = {s: np.flatnonzero(strata == s) for s in strata_ids}
    sizes = {s: int(v.size) for s, v in sub_idx.items()}

    reps = np.empty(int(n_bootstrap))
    ok = 0
    for b in range(reps.size):
        idx = np.concatenate([
            sub_idx[s][rng.integers(0, sub_idx[s].size, size=sizes[s])]
            for s in strata_ids])
        est = scalar_gradient_estimate(a_full[idx], resp[idx], sq[idx],
                                       s2=s2, dim=dim)
        reps[b] = est["g_hat"] if est["valid_pointwise"] else np.nan
        ok += int(est["valid_pointwise"])
    good = reps[np.isfinite(reps)]
    tail = (1.0 - ci_level) / 2.0
    lo, hi = (float(np.quantile(good, tail)), float(np.quantile(good, 1 - tail))) \
        if good.size >= 2 else (float("nan"), float("nan"))
    return {
        "g_ci_low": lo, "g_ci_high": hi,
        "n_bootstrap_requested": int(n_bootstrap),
        "n_bootstrap_valid": int(good.size),
        "strata_sizes": {int(s): v for s, v in sizes.items()},
    }


__all__ = [
    "variance_mass_importance", "scalar_gradient_estimate",
    "stratified_bootstrap_gradient_ci", "MixtureSpec",
    "component_responsibility",
]
