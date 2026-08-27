"""M3-D online adaptation -- VERBATIM reuse of the frozen M3-v0 controller.

Nothing in this module re-implements, retunes, or wraps-with-modification any
estimator: ``scalar_gradient_estimate`` / ``stratified_bootstrap_gradient_ci``
/ ``DirectionRule`` are the frozen M3-v0 objects (task Sec. 2 immutable list;
parity pinned by test_m3d_controller_parity_with_m3).

M3-D-specific logic is restricted to:
    * proposal-STATE construction (hyptraj.m3d.benchmark_states),
    * deployment fold of HOLD reasons onto the BASE arm,
    * arm mapping for GRADIENT and the OFFLINE ORACLE_ACTION comparator.
"""

from __future__ import annotations

import numpy as np

from hyptraj.m1.proposal_update import LEGALITY_MIN_EIG
from hyptraj.m1d.adaptation import draw_mix_pilot
from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal
from hyptraj.m2.covariance_projection import check_legality_frozen
from hyptraj.m3.covariance_gradient import (
    MixtureSpec,
    component_responsibility,
)
from hyptraj.m3.direction_policy import DirectionRule
from hyptraj.m3.gradient_estimator import (
    scalar_gradient_estimate,
    stratified_bootstrap_gradient_ci,
    variance_mass_importance,
)

ESS_MIN = 20.0            # frozen threshold (config m3d_online_v0.json)
N_BOOTSTRAP = 500
BOOTSTRAP_SEED_RULE = "[seed, 424243]"
PILOT_RNG_RULE = "[seed, 101]"


def draw_online_pilot(st, seed: int, n_pilot: int = 20_000, alpha: float = 0.5):
    """Frozen mixed-pilot semantics on the state's full mixture.

    rng=[seed,101]; frozen draw order: target-source rows first
    (standard-normal base measure), then proposal-source via prop.sample.
    Returns (z, logp, logr, source_strata).
    """
    prop = st.proposal()
    rng = np.random.default_rng([int(seed), 101])
    z, logr, strata = draw_mix_pilot(rng, prop, st.bench_cfg.logp,
                                     int(n_pilot), float(alpha))
    logp = np.asarray(st.bench_cfg.logp(z), dtype=float)
    return z, logp, np.asarray(logr, dtype=float), np.asarray(strata)


def gradient_decision(st, seed: int, z, logp, logr, source_strata) -> dict:
    """Frozen estimator + bootstrap + CI-sign rule on one (state, seed)."""
    prop = st.proposal()
    pi_all = np.asarray(prop.weights, dtype=float)
    k = st.component_index
    labels = st.bench_cfg.label(z)
    ind_event = (labels != "NOMINAL").astype(float)

    a_vec = variance_mass_importance(z, pi_all,
                                     np.asarray(prop.centers, dtype=float),
                                     list(prop.covs), logp, logr, ind_event)
    spec = MixtureSpec(pi_all, np.asarray(prop.centers, dtype=float),
                       tuple(np.asarray(c, dtype=float) for c in prop.covs))
    resp = component_responsibility(spec, z, k)
    sq = np.einsum("ni,ni->n", z - prop.centers[k][None, :],
                   z - prop.centers[k][None, :])
    est = scalar_gradient_estimate(a_vec, resp, sq, s2=st.s2, dim=st.dim)
    est.update(stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, source_strata, s2=st.s2, dim=st.dim,
        n_bootstrap=N_BOOTSTRAP,
        bootstrap_seed_key=(int(seed), 424243)))
    decision = DirectionRule(ess_min=ESS_MIN).decide(
        validity_ok=bool(est["valid_pointwise"]),
        validity_reasons=tuple(est["problems"]),
        ess_grad=float(est["ESS_grad"]),
        g_ci_low=float(est["g_ci_low"]),
        g_ci_high=float(est["g_ci_high"]))

    legality, min_eig_step = check_legality_frozen(
        float(np.exp(np.log(st.s2) + _step_sign(decision))) * np.eye(st.dim))

    return {
        "gradient": {
            "M2_hat": float(est["M2_hat"]),
            "responsibility_mass": float(est["mu_r_hat"]),
            "D_hat": float(est["D_hat"]),
            "g_hat": float(est["g_hat"]),
            "g_ci_low": float(est["g_ci_low"]),
            "g_ci_high": float(est["g_ci_high"]),
            "ESS_grad": float(est["ESS_grad"]),
            "decision": decision,
            "problems": list(est["problems"]),
            "s2_base": float(st.s2),
        },
        "legality_all_passed": bool(legality),
        "step_min_eig": float(min_eig_step),
    }


def _step_sign(decision: str) -> float:
    """Frozen step map: WIDEN +0.20, SHRINK -0.20, HOLD* 0."""
    if decision == "WIDEN":
        return 0.20
    if decision == "SHRINK":
        return -0.20
    return 0.0


DEPLOYMENT_FOLD = {"HOLD_LOW_ESS": "HOLD", "HOLD_UNCERTAIN": "HOLD",
                   "HOLD_INVALID": "HOLD", "WIDEN": "WIDEN",
                   "SHRINK": "SHRINK"}


def deployed_action(decision: str) -> str:
    """Fold every HOLD reason onto HOLD while preserving the reason code
    upstream in the record (task Sec. 15)."""
    fold = DEPLOYMENT_FOLD.get(decision)
    if fold is None:
        raise ValueError(f"unknown decision {decision!r}")
    return fold


def gradient_arm_key(decision: str) -> str:
    """Physical arm implementing the GRADIENT comparator:
    WIDEN->widen arm, SHRINK->shrink arm, any HOLD->base arm."""
    act = deployed_action(decision)
    return {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}[act]


ORACLE_ARM_KEY = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}
FIXED_RULE_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
                  "ALWAYS_HOLD": "base"}


__all__ = [
    "ESS_MIN", "draw_online_pilot", "gradient_decision",
    "deployed_action", "gradient_arm_key", "ORACLE_ARM_KEY",
    "FIXED_RULE_ARM", "BOOTSTRAP_SEED_RULE", "PILOT_RNG_RULE",
]
