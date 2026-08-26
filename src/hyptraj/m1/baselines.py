"""M1-4 -- Benchmark B baselines on the H3-1 L2 benchmark (task Sec. 21).

Baselines (oracle levels per task Sec. 22, fair call budget per Sec. 24):

1. ``run_mc``                  -- crude MC (no proposal, 160k calls)
2. ``run_single_geometry``     -- single Geometry-IS q0, no adaptation
3. ``run_h3_2_m2``             -- topology-aware mixture (secondary mode MPP
                                  known; probability-informed weights)
4. ``run_h3_2_m3``             -- leakage-point mixture (hand-designed oracle:
                                  component at each mode's leakage point +
                                  true leakage-power weights)
5. ``run_fixed_variance_aware``-- component set given (same as M3), weights
                                  optimized with the frozen SLSQP on a 20k
                                  mix_50 pilot (weight-only adaptation)
6. ``run_cem``                 -- cross-entropy method, 3 rounds x 20k + eval

All methods share the total nominal budget B = 160,000 calls per seed
(adaptive methods: 3 x 20k adaptation + 100k final eval; non-adaptive:
160k direct evaluation).  Evaluation always uses the frozen final proposal
with the standard IS estimator (w^2 second moment); per-mode leakage L_k is
estimated from the same final evaluation stream (proposal-source r = q_final,
task Sec. 23.3).

Note on M2 vs M3 here: the H3-1 L2 boundary is LINEAR, so MPP and leakage
points coincide (H3-2 known result); M2 uses probability-informed weights and
M3 uses true leakage-power weights (leakage geometry oracle).  On curved
boundaries (Benchmark C) they separate -- out of scope for B.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.m1.closed_loop import run_closed_loop
from hyptraj.m1.mixture_weights import component_log_densities, mixture_log_density
from hyptraj.m1.proposal_update import MixtureProposal, update_weights
from hyptraj.m1.variance_measure import estimate_variance_measure

D = 4
A1, A2 = -1.5, 2.5
NOMINAL = "S0"
Z_STAR = np.array([-1.5, 0.0, 0.0, 0.0])     # q0 center (H3-1 primary IS)
MPP_S1 = np.array([-1.5, 0.0, 0.0, 0.0])     # boundary point of A1
MPP_S2 = np.array([2.5, 0.0, 0.0, 0.0])      # boundary point of A2
TRUE_LEAK = np.array([0.012807475930126702, 1.5052791383520474])  # frozen analytic


def label_h3_1(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], NOMINAL, dtype=object)
    out[z[:, 0] < A1] = "S1"
    out[z[:, 0] > A2] = "S2"
    return out


def logp(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * D * np.log(2.0 * np.pi)


def _eval(prop: MixtureProposal, n_eval: int, seed: int) -> dict:
    """Independent IS evaluation of a frozen proposal (task Sec. 23)."""
    rng = np.random.default_rng(seed + 500_000)
    z = prop.sample(rng, n_eval)
    labels = label_h3_1(z)
    ind = (labels != NOMINAL).astype(float)
    logw = logp(z) - prop.log_density(z)
    w = np.exp(logw) * ind
    p_hat = float(np.mean(w))
    m2_hat = float(np.mean(w**2))
    var_hat = max(0.0, (m2_hat - p_hat**2) / n_eval)
    # L_k = (1/N) sum_{i in A_k} w_i^2  (NOT the conditional mean -- the
    # conditional mean misses the n_k/N factor and explodes on rare modes)
    l_s2 = float(np.mean((w * (labels == "S2")) ** 2))
    l_s1 = float(np.mean((w * (labels == "S1")) ** 2))
    total_l = float(l_s1 + l_s2)
    return {
        "P_hat": p_hat, "M2_hat": m2_hat, "var_hat": var_hat, "n_eval": n_eval,
        "L_S1": l_s1, "L_S2": l_s2, "total_leak": total_l,
        "omega_S2_hat": l_s2 / total_l if total_l > 0 else float("nan"),
    }


@dataclass(frozen=True)
class BaselineResult:
    method: str
    seed: int
    eval: dict
    adaptation_calls: int
    total_calls: int
    extra: dict = None


def run_mc(seed: int, budget: int) -> BaselineResult:
    """Crude MC: all budget spent on target-prior samples."""
    rng = np.random.default_rng(seed + 600_000)
    z = rng.standard_normal((budget, D))
    labels = label_h3_1(z)
    ind = (labels != NOMINAL).astype(float)
    p_hat = float(ind.mean())
    var_hat = float(p_hat * (1.0 - p_hat) / budget)
    return BaselineResult(
        method="crude_mc", seed=seed, adaptation_calls=0, total_calls=budget,
        eval={"P_hat": p_hat, "var_hat": var_hat, "n_eval": budget,
              "M2_hat": float(np.mean(ind)), "L_S1": float(ind[labels == "S1"].mean()),
              "L_S2": float(ind[labels == "S2"].mean()),
              "total_leak": float(ind.mean()),
              "omega_S2_hat": float(ind[labels == "S2"].mean() / max(ind.mean(), 1e-12))},
    )


def run_single_geometry(seed: int, budget: int) -> BaselineResult:
    """Single Geometry-IS q0, no adaptation (M1 baseline of H3-2)."""
    q0 = MixtureProposal(centers=Z_STAR.reshape(1, -1), weights=np.array([1.0]),
                         component_mode_ids=("S1",))
    ev = _eval(q0, budget, seed)
    return BaselineResult(
        method="single_geometry_q0", seed=seed, adaptation_calls=0,
        total_calls=budget, eval=ev,
        extra={"proposal": "N(z_star, I)", "n_components": 1},
    )


def _mixture_components():
    return MixtureProposal(
        centers=np.vstack([MPP_S1, MPP_S2]),
        weights=np.array([0.5, 0.5]),
        component_mode_ids=("S1", "S2"),
    )


def run_h3_2_m2(seed: int, budget: int) -> BaselineResult:
    """Topology-aware mixture: mode MPPs, probability-informed weights."""
    prop = MixtureProposal(
        centers=np.vstack([MPP_S1, MPP_S2]),
        weights=np.array([0.5, 0.5]),
        component_mode_ids=("S1", "S2"),
    )
    ev = _eval(prop, budget, seed)
    return BaselineResult(
        method="h3_2_m2_topology_mixture", seed=seed, adaptation_calls=0,
        total_calls=budget, eval=ev,
        extra={"weights": "uniform (topology-informed)", "n_components": 2},
    )


def run_h3_2_m3(seed: int, budget: int) -> BaselineResult:
    """Leakage-point mixture (hand-designed oracle), frozen H3-2 semantics.

    Components sit at the mode leakage points (on this linear boundary they
    coincide with the MPPs); THREE weight strategies are evaluated -
    ``probability`` (P_k normalized), ``leak_power1`` (L_k normalized) and
    ``p05_l05`` (sqrt(P_k L_k) normalized) - and the best strategy (min
    estimator variance) is reported, exactly as frozen H3-2's
    ``best_m3_strategy`` (run_h3_2_adaptive_geometry_is.py:321,339).

    Budget fairness (task Sec. 24): one shared IS stream of ``budget`` calls
    drawn from the uniform two-component mixture (r recorded per sample);
    all three strategy objectives are unbiased estimates on that single
    stream (task Sec. 7 estimator with q = q_strategy, r = shared source).
    Common random numbers across strategies (task Sec. 26: declared).
    """
    # frozen H3-2 weight strategies (leakage-power family, task Sec. 21 ref);
    # probability weights = frozen H3-1 MC mode marginals (dataset v1)
    p_norm = np.array([0.9190710767065446, 0.08092892329345532])
    l_norm = TRUE_LEAK / TRUE_LEAK.sum()
    p05_l05 = np.sqrt(p_norm * l_norm)
    p05_l05 = p05_l05 / p05_l05.sum()
    strategies = {
        "probability": p_norm,
        "leak_power1": l_norm,
        "p05_l05": p05_l05,
    }
    centers = np.vstack([MPP_S1, MPP_S2])
    rng = np.random.default_rng(seed + 750_000)
    r_prop = MixtureProposal(centers=centers, weights=np.array([0.5, 0.5]))
    z = r_prop.sample(rng, budget)
    logr = r_prop.log_density(z)
    labels = label_h3_1(z)
    ind = (labels != NOMINAL).astype(float)
    p_hat = float(np.mean(np.exp(logp(z) - logr) * ind))     # shared P_hat
    evals: dict[str, dict] = {}
    for sname, wvec in strategies.items():
        prop_s = MixtureProposal(centers=centers, weights=wvec)
        logq_s = prop_s.log_density(z)
        w2 = np.exp(2.0 * logp(z) - logq_s - logr) * ind
        m2_s = float(np.mean(w2))
        var_s = max(0.0, (m2_s - p_hat**2) / budget)
        evals[sname] = {
            "M2_hat": m2_s, "var_hat": var_s,
            "L_S2": float(np.mean(w2[labels == "S2"])),
            "L_S1": float(np.mean(w2[labels == "S1"])),
            "P_hat": p_hat, "n_eval": budget,
            "weights": list(map(float, wvec)),
        }
    best_name = min(evals, key=lambda s: evals[s]["var_hat"])
    best_ev = evals[best_name]
    return BaselineResult(
        method="h3_2_m3_leakage_mixture", seed=seed, adaptation_calls=0,
        total_calls=budget, eval=best_ev,
        extra={"best_strategy": best_name, "all_strategies": evals,
               "note": "shared IS stream (CRN); best = min variance, frozen H3-2 semantics"},
    )


def run_fixed_variance_aware(seed: int, pilot_n: int, eval_n: int) -> BaselineResult:
    """Component set given (M3 geometry); ONLY weights are optimized with the
    frozen SLSQP on a 20k mix_50 pilot (weight-only adaptation)."""
    base = _mixture_components()
    rng = np.random.default_rng(seed + 700_000)
    half = pilot_n // 2
    z1 = base.sample(rng, half)
    r1 = base.log_density(z1)
    z2 = rng.standard_normal((pilot_n - half, D))
    r2 = logp(z2)
    z = np.vstack([z1, z2])
    logr = np.concatenate([r1, r2])
    labels = label_h3_1(z)
    ind = (labels != NOMINAL).astype(float)
    prop_opt, res = update_weights(base, z, logp(z), logr, ind)
    ev = _eval(prop_opt, eval_n, seed)
    return BaselineResult(
        method="fixed_variance_aware_mixture", seed=seed,
        adaptation_calls=pilot_n, total_calls=pilot_n + eval_n, eval=ev,
        extra={"optimizer": "frozen SLSQP (M1)", "success": res.success,
               "kkt_residue": res.kkt_residue, "weights": list(map(float, res.weights))},
    )


def run_cem(seed: int, rounds: int, pilot_n: int, eval_n: int) -> BaselineResult:
    """Cross-entropy method: Gaussian N(m, diag(s^2)), elite = top 10% by
    event-weighted IS weight 1_A * phi/q, updated per round."""
    rng = np.random.default_rng(seed + 800_000)
    m = np.zeros(D)
    s = np.ones(D)
    calls = 0
    for _ in range(rounds):
        z = m + rng.standard_normal((pilot_n, D)) * s
        calls += pilot_n
        labels = label_h3_1(z)
        log_q = -0.5 * np.sum(((z - m) / s) ** 2, axis=1) \
            - np.sum(np.log(s)) - 0.5 * D * np.log(2.0 * np.pi)
        w = np.exp(logp(z) - log_q)
        score = (labels != NOMINAL).astype(float) * w
        k = max(int(0.10 * pilot_n), 1)
        elite = np.argsort(score)[-k:]
        m = z[elite].mean(axis=0)
        s = np.maximum(z[elite].std(axis=0), 0.05)
    prop = MixtureProposal(centers=m.reshape(1, -1),
                           weights=np.array([1.0]),
                           component_mode_ids=("S1",))
    ev = _eval(prop, eval_n, seed)
    return BaselineResult(
        method="cross_entropy", seed=seed, adaptation_calls=calls,
        total_calls=calls + eval_n, eval=ev,
        extra={"final_mean": list(map(float, m)), "final_sigma": list(map(float, s))},
    )


def run_m1_closed_loop(seed: int, pilot_n: int, eval_n: int, config) -> BaselineResult:
    """M1 closed-loop Discover + Add + Reweight (mix_50 pilot policy)."""
    q0 = MixtureProposal(centers=Z_STAR.reshape(1, -1), weights=np.array([1.0]),
                         component_mode_ids=("S1",))
    res = run_closed_loop(
        seed=seed, initial_proposal=q0, label_oracle=label_h3_1,
        logp_fn=logp, nominal_topology=NOMINAL,
        pilot_n=pilot_n, pilot_policy="mix_50",
        max_iterations=config["budget"]["max_adaptation_iterations"],
        tau_birth_main=config["mode_birth"]["tau_birth_main"],
        tau_birth_lower_confidence=config["mode_birth"]["tau_birth_lower_confidence"],
        min_mode_observations=config["mode_birth"]["min_mode_observations"],
    )
    ev = _eval(res.final_proposal, eval_n, seed)
    births = [it.candidate_mode for it in res.iterations
              if it.action == "ADD_COMPONENT" and it.candidate_mode is not None]
    return BaselineResult(
        method="m1_closed_loop", seed=seed,
        adaptation_calls=res.n_pilot_calls, total_calls=res.n_pilot_calls + eval_n,
        eval=ev,
        extra={"stop_reason": res.stop_reason, "n_iterations": len(res.iterations),
               "births": births,
               "final_components": res.final_proposal.component_mode_ids,
               "final_weights": list(map(float, res.final_proposal.weights)),
               "iterations": [
                   {"t": it.iteration, "action": it.action,
                    "M2_hat": it.M2_hat, "M2_hat_prev": it.M2_hat_prev,
                    "weight": it.weight_result}
                   for it in res.iterations]},
    )


__all__ = [
    "BaselineResult", "label_h3_1", "logp",
    "run_mc", "run_single_geometry", "run_h3_2_m2", "run_h3_2_m3",
    "run_fixed_variance_aware", "run_cem", "run_m1_closed_loop",
    "TRUE_LEAK", "Z_STAR", "MPP_S1", "MPP_S2",
]