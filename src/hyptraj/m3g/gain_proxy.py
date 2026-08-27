"""M3-G -- finite-step gain proxies (task Sec. 3, preregistered forms).

Predicted first-order relative gain of the FROZEN direction action:

    Delta_rel = g_hat * dtheta / M2          (dtheta = +/-delta_theta_main
                                              in the acted direction)

with the frozen step map WIDEN -> +0.20, SHRINK -> -0.20 (reused from
``hyptraj.m3.direction_policy.step_sign_for``; never re-derived here).

Operationalisation register (locked in configs/phase_m3g BEFORE online;
calibration and online use the SAME forms so the selected rho transfers):

  * M2 normaliser      : base-arm EVALUATION M2 (n_eval=100k, CRN).  The
                         D6 record schema stores only per-arm evaluation
                         M2 values, not the pilot-based M2_hat; both
                         estimate the same functional (variance mass at
                         the current covariance), so calibration and the
                         online gate normalise identically.  The pilot
                         M2_hat is recorded ONLINE as a diagnostic and the
                         audit quantifies the estimator substitution.
  * GA1 (pure magnitude): act iff |g_hat*dtheta|/M2 >= rho.
  * GA2 (conservative)  : linear propagation of the FROZEN g-CI through
                         the sign-stable factor dtheta/M2; act iff the
                         UPPER (least-favourable) end of the signed-gain
                         CI is still beyond -rho on the acted side.
                         For WIDEN  (dtheta=+0.20, g<0): upper end =
                         g_ci_high*0.20/M2 <= -rho  (|g_ci_high|*0.20/M2>=rho).
                         For SHRINK (dtheta=-0.20, g>0): upper end =
                         g_ci_low*(-0.20)/M2 <= -rho.
                         This mirrors CI-sign: act only when the WHOLE CI
                         clears the indifference band on the acted side.

``bootstrap_gain_replicates`` re-runs the FROZEN fixed-stratified
resampling (identical RNG consumption as
``stratified_bootstrap_gradient_ci``) so that per-replicate g_r and M2_r
exist for the ONLINE diagnostic CI of Delta_rel; the g quantiles reproduce
the frozen CI bitwise (guarded by test_m3g_ga2_replicate_ci_parity).
"""

from __future__ import annotations

import numpy as np

from hyptraj.m3.direction_policy import step_sign_for
from hyptraj.m3.gradient_estimator import scalar_gradient_estimate

DELTA_THETA_MAIN = 0.20           # frozen step size priced into every gate


def step_delta_theta(direction: str, delta_theta: float = DELTA_THETA_MAIN) \
        -> float:
    """Frozen step map delegate: WIDEN +dtheta, SHRINK -dtheta, else 0."""
    return float(step_sign_for(direction, delta_theta))


def signed_delta_rel(g: float, dtheta: float, m2: float) -> float:
    """``Delta_rel = g*dtheta/M2`` (signed; negative on the acted side)."""
    return float(g) * float(dtheta) / float(m2)


def ga1_magnitude(g_hat: float, dtheta: float, m2: float) -> float:
    """GA1 proxy: |g_hat*dtheta|/M2."""
    return abs(signed_delta_rel(g_hat, dtheta, m2))


def ga2_upper_end(g_ci_low: float, g_ci_high: float, dtheta: float,
                  m2: float) -> float:
    """Upper (least-favourable) end of the signed-gain CI.

    signed_gain = g*dtheta/M2 is monotone in g with the sign of dtheta:
      dtheta > 0 -> upper end uses g_ci_high
      dtheta < 0 -> upper end uses g_ci_low
    """
    dtheta = float(dtheta)
    m2 = float(m2)
    if dtheta >= 0.0:
        return float(g_ci_high) * dtheta / m2
    return float(g_ci_low) * dtheta / m2


def bootstrap_gain_replicates(
    a_full: np.ndarray,
    resp_k: np.ndarray,
    sq_radius: np.ndarray,
    source_strata: np.ndarray,
    s2: float,
    dim: int,
    dtheta: float,
    n_bootstrap: int = 500,
    bootstrap_seed_key=None,
    ci_level: float = 0.95,
) -> dict:
    """Per-replicate (g_r, M2_r, Delta_rel) over the FROZEN resampling.

    Consumes the RNG in EXACTLY the byte-identical order of the frozen
    ``stratified_bootstrap_gradient_ci`` (strata in ``np.unique`` order,
    preserved stratum sizes, per-replicate full point pipeline), so the
    g quantiles below reproduce the frozen percentile CI of g; each
    replicate additionally carries its M2_hat so a TRUE per-replicate CI
    of the signed / magnitude gain exists for the online diagnostic.
    Invalid replicates (non-finite point estimate) become NaN exactly as
    in the frozen bootstrap.
    """
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

    g_r = np.full(int(n_bootstrap), np.nan)
    m2_r = np.full(int(n_bootstrap), np.nan)
    for b in range(n_bootstrap):
        idx = np.concatenate([
            sub_idx[s][rng.integers(0, sub_idx[s].size, size=sizes[s])]
            for s in strata_ids])
        est = scalar_gradient_estimate(a_full[idx], resp[idx], sq[idx],
                                       s2=s2, dim=dim)
        if est["valid_pointwise"]:
            g_r[b] = est["g_hat"]
            m2_r[b] = est["M2_hat"]

    good = np.isfinite(g_r) & np.isfinite(m2_r) & (m2_r > 0.0)
    signed = np.full_like(g_r, np.nan)
    mag = np.full_like(g_r, np.nan)
    if np.any(good):
        signed[good] = g_r[good] * float(dtheta) / m2_r[good]
        mag[good] = np.abs(signed[good])
    tail = (1.0 - float(ci_level)) / 2.0
    g_lo, g_hi = (float(np.quantile(g_r[np.isfinite(g_r)], tail)),
                  float(np.quantile(g_r[np.isfinite(g_r)], 1 - tail))) \
        if np.isfinite(g_r).sum() >= 2 else (float("nan"), float("nan"))
    signed_good = signed[np.isfinite(signed)]
    s_lo, s_hi = (float(np.quantile(signed_good, tail)),
                  float(np.quantile(signed_good, 1 - tail))) \
        if signed_good.size >= 2 else (float("nan"), float("nan"))
    mag_good = mag[np.isfinite(mag)]
    m_lo, m_hi = (float(np.quantile(mag_good, tail)),
                  float(np.quantile(mag_good, 1 - tail))) \
        if mag_good.size >= 2 else (float("nan"), float("nan"))
    return {
        "g_replicates": g_r.tolist(),
        "M2_replicates": m2_r.tolist(),
        "delta_rel_signed_replicates": signed.tolist(),
        "delta_rel_mag_replicates": mag.tolist(),
        "n_bootstrap_requested": int(n_bootstrap),
        "n_bootstrap_valid": int(np.isfinite(g_r).sum()),
        "g_ci_low": g_lo,
        "g_ci_high": g_hi,
        "delta_rel_signed_ci_low": s_lo,
        "delta_rel_signed_ci_high": s_hi,
        "delta_rel_mag_ci_low": m_lo,
        "delta_rel_mag_ci_high": m_hi,
        "strata_sizes": {int(s): v for s, v in sizes.items()},
    }


__all__ = [
    "DELTA_THETA_MAIN", "step_delta_theta", "signed_delta_rel",
    "ga1_magnitude", "ga2_upper_end", "bootstrap_gain_replicates",
]