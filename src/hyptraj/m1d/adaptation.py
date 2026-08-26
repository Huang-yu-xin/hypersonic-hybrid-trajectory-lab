"""M1-D -- selection-layer adaptation machinery (task Sec. 15-17, Sec. 26-32).

Layer A (Sec. 17): selection-only comparator.  Both selectors see the SAME
mixed pilot (common random numbers per (config, seed)); they differ ONLY in
the ranking signal used to pick ONE unrepresented mode.  Downstream action is
identical and reuses frozen M1-v0 primitives:

    center   = target-probability conditional centroid m_k^P
               (= E_r[w p/r-masked] / E_r[.] over the recorded mixed pilot;
                identical estimator to frozen ``center_method=
                "probability_centroid"``)                       Sec. 30
    cov      = unit I (frozen base)                                Sec. 8.3
    init wt  = ``add_component`` pi_fallback split                 Sec. 13
    weights  = frozen SLSQP M2-hat minimizer on the same pilot     Sec. 32
    eval     = independent 100k IS pass                            Sec. 21

Candidate discovery gate (Sec. 16) -- NO birth-threshold pre-filtering:
observed >= 5, topology label valid (produced by the oracle), unrepresented,
finite estimator.  The M1-v0 tau_birth gate is deliberately NOT applied here.

Firewall (Sec. 41): nothing in this module loads or receives benchmark-design
offline quantities -- no frozen reference tables, oracle orderings, or any
other artifact from the benchmark-design side ever reaches an online decision
here.  The only oracle inputs are exact topology labels produced by the
frozen label function and the recorded sampling densities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from hyptraj.m1.proposal_update import (
    MixtureProposal,
    add_component,
    eta_region_centroid,
    update_weights,
)
from hyptraj.m1.variance_measure import estimate_variance_measure

MIN_MODE_OBSERVATIONS = 5      # task Sec. 16 literal gate


# ---------------------------------------------------------------------------
# mixed pilot (identical construction to frozen run_closed_loop._draw_pilot)
# ---------------------------------------------------------------------------
def draw_mix_pilot(
    rng: np.random.Generator,
    proposal: MixtureProposal,
    logp_fn: Callable[[np.ndarray], np.ndarray],
    n: int,
    alpha: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(z, logr, source_strata)``; strata 1 = q-source, 0 = p-source.

    Draw order and sizes mirror the frozen implementation bit-for-bit
    (``n_p = int(round(n*alpha))`` target samples first, then ``n - n_p``
    proposal samples via ``prop.sample``).
    """
    n_p = int(round(n * alpha))
    n_q = n - n_p
    d = proposal.centers.shape[1]
    zp = rng.standard_normal((n_p, d))
    rp = logp_fn(zp)
    zq = proposal.sample(rng, n_q)
    rq = proposal.log_density(zq)
    z = np.vstack([zp, zq])
    logr = np.concatenate([rp, rq])
    strata = np.concatenate([np.zeros(n_p, dtype=int), np.ones(n_q, dtype=int)])
    return z, logr, strata


# ---------------------------------------------------------------------------
# online estimators (fixed-design legal; no counts-as-probability anywhere)
# ---------------------------------------------------------------------------
def p_hat_online(logp: np.ndarray, logr: np.ndarray, labels: np.ndarray,
                 mid: str) -> float:
    """``P_hat_k = (1/N) sum 1_{A_k} p/r`` -- unbiased for ANY recorded
    fixed sampling design (task Sec. 28 ban on n_k/N respected)."""
    mask = (labels == mid).astype(float)
    return float(np.mean(mask * np.exp(np.asarray(logp, dtype=float)
                                       - np.asarray(logr, dtype=float))))


def l_hat_online(z: np.ndarray, centers: np.ndarray, pi: np.ndarray,
                 logp: np.ndarray, logr: np.ndarray, labels: np.ndarray,
                 mid: str) -> float:
    """``L_hat_k = (1/N) sum_{A_k} p^2/(q_t r)`` (task Sec. 29 estimator)."""
    mask = (labels == mid).astype(float)
    return float(np.mean(mask * np.exp(2.0 * np.asarray(logp, dtype=float)
                                       - proposal_log_density(z, centers, pi)
                                       - np.asarray(logr, dtype=float))))


def proposal_log_density(z: np.ndarray, centers: np.ndarray,
                         pi: np.ndarray) -> np.ndarray:
    """Frozen mixture log density (delegated to avoid divergence)."""
    from hyptraj.m1.mixture_weights import component_log_densities, mixture_log_density
    return mixture_log_density(component_log_densities(z, centers), pi)


# ---------------------------------------------------------------------------
# candidate discovery gate (Sec. 16) and selectors (Sec. 17 / Sec. 19)
# ---------------------------------------------------------------------------
def eligible_candidates(labels: np.ndarray, nominal_topology: str,
                        component_mode_ids,
                        min_obs: int = MIN_MODE_OBSERVATIONS) -> list[str]:
    """Unrepresented modes passing the literal Sec. 16 gate, stable order."""
    out = []
    for mid in sorted(set(labels[labels != nominal_topology].tolist())):
        if mid in component_mode_ids:
            continue
        n_obs = int(np.sum(labels == mid))
        if n_obs < min_obs:
            continue
        out.append(str(mid))
    return out


def selector_pick(signal: str, cand_ids: list[str], labels: np.ndarray,
                  z: np.ndarray, centers: np.ndarray, pi: np.ndarray,
                  logp: np.ndarray, logr: np.ndarray) -> tuple[str | None, dict]:
    """Pick ONE candidate by the declared signal; returns (mode, diagnostics).

    ``signal='probability'`` -> argmax P_hat_k           (Sec. 17.1)
    ``signal='variance'``    -> argmax L_hat_k           (Sec. 17.2)
    """
    p_tab = {m: p_hat_online(logp, logr, labels, m) for m in cand_ids}
    l_tab = {m: l_hat_online(z, centers, pi, logp, logr, labels, m)
             for m in cand_ids}
    if not cand_ids:
        return None, {"P_hat_table": {}, "L_hat_table": {}}
    key = {"probability": lambda m: p_tab[m],
           "variance": lambda m: l_tab[m]}[signal]
    pick = max(cand_ids, key=key)
    return pick, {"P_hat_table": p_tab, "L_hat_table": l_tab}


def oracle_pick(order_by_refs: list[str], cand_ids: list[str]) -> str | None:
    """Benchmark-design ORACLE selection restricted to eligible candidates.

    ``order_by_refs`` comes from the offline freeze artifact and MUST be
    provided by the DRIVER layer only (never by hyptraj.m1d.adaptation).
    """
    for mid in order_by_refs:
        if mid in cand_ids:
            return mid
    return None


def random_pick(cand_ids: list[str], rng: np.random.Generator) -> str | None:
    return str(rng.choice(cand_ids)) if cand_ids else None


# ---------------------------------------------------------------------------
# common downstream action (Sec. 17.3 / Sec. 30) + optional variants for
# ablations D-C / D-D -- one shared builder keeps every cell auditable
# ---------------------------------------------------------------------------
def probability_conditional_centroid(z: np.ndarray, logp: np.ndarray,
                                     logr: np.ndarray, labels: np.ndarray,
                                     mid: str) -> tuple[np.ndarray, int]:
    """``m_k^P`` Sec. 30: ratio of masked p/r expectations over the pilot."""
    mask = (labels == mid).astype(float)
    wp = mask * np.exp(np.asarray(logp, dtype=float) - np.asarray(logr, dtype=float))
    tot = float(wp.sum())
    if tot <= 0.0:
        raise ValueError(f"zero probability mass for mode {mid!r}")
    return (wp[:, None] * z).sum(axis=0) / tot, int(mask.sum())


def variance_hdr_centroid(z, logp, logr, pi, centers, labels, nominal, mid,
                          eta: float = 0.8) -> tuple[np.ndarray, float]:
    """Frozen H3-corrected variance-mass HDR centroid (Sec. 31; unchanged)."""
    return eta_region_centroid(np.asarray(z), np.asarray(logp),
                               np.asarray(logr), np.asarray(pi),
                               np.asarray(centers), labels, nominal,
                               mode=mid, eta=eta)


def build_final_proposal(
    base: MixtureProposal,
    z: np.ndarray, logp: np.ndarray, logr: np.ndarray, labels: np.ndarray,
    nominal: str, selected_mode: str,
    center_rule: str = "probability",       # 'probability' | 'variance_hdr'
    weight_rule: str = "m2_opt",            # 'm2_opt' (frozen SLSQP) |
                                            # 'probability' (pi propto P_hat)
    eta_main: float = 0.8,
):
    """Common downstream action; returns (proposal, details dict).

    Identical behavior across selectors is structurally guaranteed: ONLY the
    ``selected_mode`` string enters from the selection stage.
    """
    indicators = (labels != nominal).astype(float)
    if center_rule == "probability":
        cvec, n_used = probability_conditional_centroid(z, logp, logr,
                                                        labels, selected_mode)
    elif center_rule == "variance_hdr":
        cvec, eta_used = variance_hdr_centroid(z, logp, logr, base.weights,
                                               base.centers, labels, nominal,
                                               selected_mode, eta=eta_main)
        n_used = int((labels == selected_mode).sum())
    else:
        raise ValueError(center_rule)

    prop = add_component(base, cvec, mode_id=selected_mode)

    if weight_rule == "m2_opt":
        prop, res = update_weights(prop, z, logp, logr, indicators)
        details = {
            "solver": "frozen SLSQP (M1)", "success": bool(res.success),
            "message": res.message, "kkt_residue": res.kkt_residue,
            "n_iter": res.n_iter, "weights": list(map(float, res.weights)),
            "center_rule": center_rule, "center_n_obs": n_used,
        }
    elif weight_rule == "probability":
        p_hats = []
        for mid in prop.component_mode_ids:
            mask = (labels == mid).astype(float)
            p_hats.append(float(np.mean(
                mask * np.exp(np.asarray(logp, dtype=float) - logr))))
        p_hats = np.maximum(np.asarray(p_hats, dtype=float), 1e-12)
        p_hats = p_hats / p_hats.sum()
        prop = MixtureProposal(centers=prop.centers, weights=p_hats,
                               component_mode_ids=prop.component_mode_ids)
        details = {"solver": "pi_propto_P_hat", "success": True,
                   "message": "probability_weights",
                   "weights": list(map(float, p_hats)),
                   "center_rule": center_rule, "center_n_obs": n_used}
    else:
        raise ValueError(weight_rule)
    return prop, details


__all__ = [
    "draw_mix_pilot", "p_hat_online", "l_hat_online",
    "eligible_candidates", "selector_pick", "oracle_pick", "random_pick",
    "probability_conditional_centroid", "variance_hdr_centroid",
    "build_final_proposal", "MIN_MODE_OBSERVATIONS",
]
