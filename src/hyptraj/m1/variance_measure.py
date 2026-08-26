"""M1 -- variance measure estimation (task Sec. 7).

Estimates, from legal pilot samples with individually recorded sampling
densities ``r_i``:

- variance-mass weights ``w_tilde_i = 1_A(x_i) p(x_i)^2 / (q_t(x_i) r_i(x_i))``
- second moment ``M2_hat = (1/N) sum_i w_tilde_i``
- mode-wise leakage ``L_k_hat = (1/N) sum_{i in A_k} w_tilde_i`` and
  variance shares ``omega_k_V_hat = L_k_hat / M2_hat``
- normalized empirical variance measure
  ``nu_hat_V = sum_i w_hat_i delta_{x_i}``, ``w_hat = w_tilde / sum w_tilde``

Prohibited (task Sec. 7): treating raw sample counts as variance mass;
pooling pilots from different sources without keeping ``r_i``; estimating
``nu_V`` directly from the proposal sample density.

Pure numpy/scipy analysis layer (no simulator import).  All inputs in
log space; the ``M2_hat`` convention is identical to
``m1.mixture_weights.m2_hat`` (unbiased for any fixed sampling density).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hyptraj.m1.mixture_weights import (
    component_log_densities,
    mixture_log_density,
)


def variance_mass_weights(
    z: np.ndarray,
    centers: np.ndarray,
    pi: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    indicators: np.ndarray,
) -> np.ndarray:
    """``w_tilde_i = 1_A(x_i) p(x_i)^2 / (q_pi(x_i) r_i(x_i))`` (task Sec. 7).

    ``q_pi`` is the proposal evaluated at the CURRENT frozen weights ``pi``
    (the pilot source ``r`` must be fixed at draw time -- two-phase protocol,
    task Sec. 18).  ``z``: ``(N, d)``; ``centers``: ``(J, d)``; others ``(N,)``.
    """
    z = np.asarray(z, dtype=float)
    logp = np.asarray(logp, dtype=float).reshape(-1)
    logr = np.asarray(logr, dtype=float).reshape(-1)
    indicators = np.asarray(indicators, dtype=float).reshape(-1)
    if z.shape[0] != logp.size or logp.size != logr.size or indicators.size != logp.size:
        raise ValueError("z / logp / logr / indicators length mismatch")
    logq = mixture_log_density(component_log_densities(z, centers), pi)
    w = np.exp(2.0 * logp - logq - logr) * indicators
    return w


@dataclass(frozen=True)
class VarianceMeasure:
    """One mode-wise decomposition of the estimated variance measure."""

    M2_hat: float
    mode_ids: tuple[str, ...]
    L_k: tuple[float, ...]            # (1/N) sum_{A_k} w_tilde
    omega_k_V: tuple[float, ...]      # L_k / M2
    n_observed: tuple[int, ...]       # raw pilot counts per mode
    variance_mass_ess: float
    n_events: int
    n_samples: int

    def mode_dict(self) -> dict[str, float]:
        return {mid: float(w) for mid, w in zip(self.mode_ids, self.omega_k_V)}

    def leakage_dict(self) -> dict[str, float]:
        return {mid: float(l) for mid, l in zip(self.mode_ids, self.L_k)}


def estimate_variance_measure(
    z: np.ndarray,
    centers: np.ndarray,
    pi: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    labels: np.ndarray,
    nominal_topology: str,
) -> VarianceMeasure:
    """Estimate ``M2_hat``, per-mode ``L_k`` / ``omega_k_V`` and ESS.

    Event = any label different from the nominal topology; topology modes
    are the distinct transition labels observed in the pilot (legal
    partition check: every observed label maps to exactly one mode).
    """
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    indicators = (labels != nominal_topology).astype(float)
    w = variance_mass_weights(z, centers, pi, logp, logr, indicators)
    n = w.size
    n_events = int(np.count_nonzero(indicators))
    m2 = float(np.mean(w)) if n_events else float("nan")

    transition = labels != nominal_topology
    mode_list = sorted(set(labels[transition].tolist()))
    L_k, omega_k, counts = [], [], []
    for topo in mode_list:
        mask = transition & (labels == topo)
        lk = float(np.sum(w[mask]) / n)
        L_k.append(lk)
        omega_k.append(lk / m2 if m2 > 0.0 else float("nan"))
        counts.append(int(mask.sum()))

    ess = float("nan")
    if n_events:
        s = float(w[transition].sum())
        ess = float(s * s / np.sum(w[transition] ** 2)) if np.sum(w[transition] ** 2) > 0 else 0.0

    return VarianceMeasure(
        M2_hat=m2,
        mode_ids=tuple(str(m) for m in mode_list),
        L_k=tuple(float(x) for x in L_k),
        omega_k_V=tuple(float(x) for x in omega_k),
        n_observed=tuple(counts),
        variance_mass_ess=ess,
        n_events=n_events,
        n_samples=n,
    )


def omega_bootstrap_lcb(
    z: np.ndarray,
    centers: np.ndarray,
    pi: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    labels: np.ndarray,
    nominal_topology: str,
    mode: str,
    n_bootstrap: int = 500,
    rng: np.random.Generator | None = None,
    seed: int = 2026,
    source_strata: np.ndarray | None = None,
) -> tuple[float, float]:
    """Bootstrap 95% lower confidence bound of ``omega_k^V`` for one mode.

    Each bootstrap replicate resamples ``N`` sample indices with replacement
    and recomputes ``w_tilde``, ``M2`` and ``omega_k^V`` from the resampled
    weights.  Returns ``(LB, UB)`` (2.5% / 97.5% quantiles of the replicate
    distribution).  ``mode`` must be a label observed in the pilot.

    Stratified bootstrap (frozen fix, semantic audit Issue 6): when the pilot
    is a fixed stratified design (``source_strata`` given; 1 = q-source,
    0 = p-source), each replicate resamples WITHIN each stratum and keeps the
    stratum sizes ``N_q`` / ``N_p`` EXACTLY -- plain pooled resampling would
    destroy the design and bias the uncertainty estimate.
    """
    rng = np.random.default_rng(seed) if rng is None else rng
    z = np.asarray(z, dtype=float)
    labels = np.asarray(labels)
    n = z.shape[0]
    logq = mixture_log_density(component_log_densities(z, centers), pi)
    logw_pre = 2.0 * np.asarray(logp, dtype=float) - logq - np.asarray(logr, dtype=float)
    ind = (labels != nominal_topology).astype(float)
    is_mode = (labels == mode).astype(float)
    if ind.sum() == 0:
        raise ValueError("no event samples to bootstrap")

    if source_strata is not None:
        strata = np.asarray(source_strata).astype(int)
        if strata.size != n:
            raise ValueError("source_strata length mismatch")
        strata_ids = np.unique(strata)
        sizes = {s: int(np.sum(strata == s)) for s in strata_ids}
    else:
        strata = None
        strata_ids = [0]
        sizes = {0: n}

    reps = np.empty(n_bootstrap)
    for b in range(n_bootstrap):
        idx = []
        for s in strata_ids:
            sub = np.flatnonzero(strata == s) if strata is not None \
                else np.arange(n)
            idx.append(sub[rng.integers(0, sub.size, size=sizes[s])])
        idx = np.concatenate(idx)
        wb = np.exp(logw_pre[idx]) * ind[idx]
        mb = float(np.sum(wb) / n)
        lb_m = float(np.sum(wb * is_mode[idx]) / n)
        reps[b] = lb_m / mb if mb > 0.0 else 0.0
    lb, ub = np.quantile(reps, [0.025, 0.975])
    return float(lb), float(ub)


__all__ = [
    "variance_mass_weights",
    "estimate_variance_measure",
    "omega_bootstrap_lcb",
    "VarianceMeasure",
]