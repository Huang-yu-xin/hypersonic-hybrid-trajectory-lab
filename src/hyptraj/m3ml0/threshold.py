"""M3-ML0 safety-constrained threshold rule (taskbook Sec. 19).

On inner-CV out-of-fold predictions:
  1. enumerate unique predicted-probability midpoints (+ sentinels);
  2. keep thresholds with ND unsafe <= 0.20;
  3. maximize deployable coverage;
  4. tie-break: lower ND unsafe, lower harmful deployment, higher
     threshold, canonical numeric order;
  5. no legal threshold => ABSTAIN-ALL sentinel (a coverage failure by
     construction, never counted as success).
"""
from __future__ import annotations

import numpy as np

UNSAFE_MAX = 0.20


def _metrics_at(probs: np.ndarray, y: np.ndarray, is_nd: np.ndarray, t: float):
    deploy = probs >= t
    n_dep = int((~is_nd).sum())
    n_nd = int(is_nd.sum())
    cov = float(deploy[~is_nd].mean()) if n_dep else 0.0
    unsafe = float(deploy[is_nd].mean()) if n_nd else 0.0
    harmful = int(deploy[is_nd].sum())
    return cov, unsafe, harmful, int(deploy.sum())


def candidate_thresholds(probs: np.ndarray) -> list[float]:
    u = np.unique(probs)
    mids = [(a + b) / 2.0 for a, b in zip(u, u[1:])]
    return [float(u[0] - 1e-6)] + [float(m) for m in mids] + [float(u[-1]) + 1.0]


def select_threshold(probs: np.ndarray, y: np.ndarray, is_nd: np.ndarray):
    """Returns (threshold, diagnostics).  probs/y/is_nd cover the inner-OOF
    valid-gradient rows."""
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y, dtype=int)
    is_nd = np.asarray(is_nd, dtype=bool)
    legal = []
    for t in candidate_thresholds(probs):
        cov, unsafe, harmful, ndep = _metrics_at(probs, y, is_nd, t)
        if unsafe <= UNSAFE_MAX:
            legal.append((t, cov, unsafe, harmful, ndep))
    if not legal:
        # ABSTAIN-ALL sentinel: threshold above every achievable probability
        return float(probs.max() + 1.0), {"abstain_all": True, "n_legal": 0}
    # maximize coverage; tie-break lower unsafe, lower harmful, higher t
    best = sorted(legal, key=lambda r: (-r[1], r[2], r[3], -r[0]))[0]
    return float(best[0]), {"abstain_all": False, "n_legal": len(legal),
                            "inner_coverage": best[1],
                            "inner_unsafe": best[2],
                            "inner_harmful": best[3]}
