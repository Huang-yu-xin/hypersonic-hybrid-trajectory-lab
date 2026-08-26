"""M1-D -- evaluation & metrics (task Sec. 21-23).

All functions here are OFFLINE analysis utilities operating on frozen proposals
and benchmark-design reference tables; they never feed back into any online
policy decision (firewall Sec. 41 is structural: ``hyptraj.m1d.adaptation``
accepts no reference inputs).
"""

from __future__ import annotations

import numpy as np

from hyptraj.m1.baselines import vrf_budget, vrf_proposal   # frozen formulas
from hyptraj.m1.proposal_update import MixtureProposal

MISSING = ("S2", "S3", "S4")
NOMINAL = "S0"


def eval_proposal_is(proposal: MixtureProposal, bench_cfg, seed: int,
                     n_eval: int = 100_000,
                     rng_tag: int = 900_001) -> dict:
    """Independent IS evaluation against the true u-space target.

    Returns P_hat / M2_hat / var_hat plus PER-MODE leakage L_k(q_final),
    VRF_proposal and VRF_budget (both from the frozen semantic-corrected
    definitions; MC-side probability uses the reference P_ref -- identical
    denominator across all methods on one config keeps ratios paired).
    """
    rng = np.random.default_rng([int(seed), rng_tag])
    z = proposal.sample(rng, n_eval)
    logq = proposal.log_density(z)
    labels = bench_cfg.label(z)
    ind = (labels != NOMINAL).astype(float)
    logp = bench_cfg.logp(z)
    w = np.exp(logp - logq) * ind
    p_hat = float(np.mean(w))
    m2_hat = float(np.mean(w**2))
    var_hat = max(0.0, (m2_hat - p_hat**2) / n_eval)
    return {
        "P_hat": p_hat,
        "M2_hat": m2_hat,
        "var_hat": var_hat,
        "n_eval": int(n_eval),
        "L_table": {str(mid): float(np.mean((w * (labels == mid)) ** 2))
                    for mid in sorted(set(labels.tolist()) - {NOMINAL})},
    }


def attach_vrfs(evaluation: dict, p_ref: float, budget_total: int) -> dict:
    """Fill VRF_proposal / VRF_budget using frozen definitions."""
    evaluation["VRF_proposal"] = vrf_proposal(
        p_mc=p_ref, n_eval=evaluation["n_eval"], var_hat=evaluation["var_hat"])
    evaluation["VRF_budget"] = vrf_budget(
        p_mc=p_ref, budget=int(budget_total), m2_hat=evaluation["M2_hat"],
        p_hat=evaluation["P_hat"], n_eval=evaluation["n_eval"])
    return evaluation


# ---------------------------------------------------------------------------
# selection-quality metrics (Sec. 22-23); ref tables = benchmark-design data
# ---------------------------------------------------------------------------
def captured_share(selected: list[str], refs: dict[str, float]) -> tuple[float, float]:
    """CVS/CPS numerator-denominator machinery restricted to MISSING modes."""
    tot = sum(refs[m] for m in MISSING)
    if tot <= 0:
        return 0.0, tot
    cap = sum(refs.get(m, 0.0) for m in selected if m in MISSING)
    return float(cap / tot), tot


def cvs_of(selected: list[str], L_refs: dict[str, float]) -> float:
    return captured_share(selected, L_refs)[0]


def cps_of(selected: list[str], P_refs: dict[str, float]) -> float:
    return captured_share(selected, P_refs)[0]


def regret_metrics(m2_policy: float, m2_oracle_v: float,
                   cvs_policy: float, cvs_oracle_v: float) -> dict:
    """Sec. 23 regret pair (guarding degenerate denominators)."""
    r_m2 = float(m2_policy / m2_oracle_v - 1.0) if m2_oracle_v > 0 else float("nan")
    r_cvs = float(1.0 - cvs_policy / cvs_oracle_v) if cvs_oracle_v > 0 else float("nan")
    return {"R_M2_vs_oracleV": r_m2, "R_CVS_vs_oracleV": r_cvs}


# ---------------------------------------------------------------------------
# hierarchical aggregation (Sec. 35-36)
# ---------------------------------------------------------------------------
def paired_deltas(rows_v: dict[tuple, float], rows_p: dict[tuple, float]) -> np.ndarray:
    keys = sorted(set(rows_v) & set(rows_p))
    return np.array([rows_v[k] - rows_p[k] for k in keys]), keys


def summarize(values: list[float], boots: int = 2000,
              seed: int = 20260827) -> dict:
    a = np.asarray(values, dtype=float)
    out = {
        "n": int(a.size),
        "median": float(np.median(a)) if a.size else None,
        "mean": float(np.mean(a)) if a.size else None,
        "std": float(np.std(a, ddof=1)) if a.size > 1 else 0.0,
        "min": float(np.min(a)) if a.size else None,
        "max": float(np.max(a)) if a.size else None,
    }
    if a.size >= 2:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, a.size, size=(boots, a.size))
        stats = np.median(a[idx], axis=1)          # bootstrap of the MEDIAN
        lo, hi = np.quantile(stats, [0.025, 0.975])
        out["median_ci95"] = [float(lo), float(hi)]
    return out


__all__ = [
    "eval_proposal_is", "attach_vrfs", "captured_share", "cvs_of", "cps_of",
    "regret_metrics", "paired_deltas", "summarize",
    "MISSING", "NOMINAL",
]
