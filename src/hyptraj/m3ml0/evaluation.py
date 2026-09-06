"""M3-ML0 policy evaluation (taskbook Sec. 12).

Primary objective: maximize deployable coverage subject to
ND unsafe <= 0.20 and wrong direction <= 0.05, where the action direction
always comes from the gradient sign (ML never overrides it).

Rows are the full trial set (valid + invalid-gradient); invalid-gradient
rows deterministically map to ABSTAIN (frozen online semantics).
"""
from __future__ import annotations

import numpy as np

GATES = {"coverage_min": 0.75, "unsafe_max": 0.20, "wrong_max": 0.05}
Z95 = 1.959963984540054
S1_THRESHOLD = 5.4417199447782


def _wilson(k: int, n: int):
    if not n:
        return None
    z = Z95
    p_ = k / n
    d = 1 + z * z / n
    c = (p_ + z * z / (2 * n)) / d
    h = z * math_sqrt(p_ * (1 - p_) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def math_sqrt(x: float) -> float:
    return x ** 0.5


def evaluate_policy(rows: list[dict], deploy: list[bool]) -> dict:
    """deploy[i] == True means DEPLOY for row i (direction = gradient sign).
    Invalid-gradient rows must carry deploy=False."""
    rows = list(rows)
    deploy = np.asarray(deploy, dtype=bool)
    truth = np.array([r["truth"] for r in rows], dtype=object)
    is_dep = np.array([r["truth"] in ("WIDEN", "SHRINK") for r in rows])
    is_nd = ~is_dep
    n_dep, n_nd = int(is_dep.sum()), int(is_nd.sum())
    deployed_dep = int((deploy & is_dep).sum())
    unsafe_nd = int((deploy & is_nd).sum())
    wrong = sum(1 for r, d in zip(rows, deploy)
                if d and r["truth"] in ("WIDEN", "SHRINK")
                and (r["action_sign"] if "action_sign" in r
                     else ("WIDEN" if r["g_hat"] < 0 else "SHRINK")) != r["truth"])
    out = {
        "trials": len(rows),
        "deployable_trials": n_dep,
        "deployed": deployed_dep,
        "deployable_coverage": deployed_dep / n_dep if n_dep else 0.0,
        "coverage_ci95": _wilson(deployed_dep, n_dep),
        "nondeployable_trials": n_nd,
        "deployed_nd": unsafe_nd,
        "nd_unsafe": unsafe_nd / n_nd if n_nd else 0.0,
        "unsafe_ci95": _wilson(unsafe_nd, n_nd),
        "wrong": wrong,
        "wrong_direction_rate": wrong / n_dep if n_dep else 0.0,
        "wrong_ci95": _wilson(wrong, n_dep),
    }
    for grp in ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"):
        m = truth == grp
        d = int((deploy & m).sum())
        n = int(m.sum())
        if grp in ("WIDEN", "SHRINK"):
            out[f"truth_{grp}"] = {"trials": n, "deployed": d,
                                   "coverage": d / n if n else 0.0}
        else:
            out[f"truth_{grp}"] = {"trials": n, "deployed": d,
                                   "unsafe": d / n if n else 0.0}
    out["safety_compliant"] = bool(
        out["deployable_coverage"] >= GATES["coverage_min"]
        and out["nd_unsafe"] <= GATES["unsafe_max"]
        and out["wrong_direction_rate"] <= GATES["wrong_max"])
    return out


def s1_frozen_deploy(rows: list[dict]) -> list[bool]:
    """Frozen S1 baseline policy (B0): DEPLOY iff S1 >= tau on valid trials."""
    return [bool(r.get("gradient_valid") and r.get("S1") is not None
                 and float(r["S1"]) >= S1_THRESHOLD) for r in rows]


def classification_metrics(y_true: np.ndarray, probs: np.ndarray) -> dict:
    """Secondary ranking/calibration metrics on the scored (valid) rows."""
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    out = {}
    try:
        out["auc"] = float(roc_auc_score(y_true, probs))
    except ValueError:
        out["auc"] = None
    try:
        out["pr_auc"] = float(average_precision_score(y_true, probs))
    except ValueError:
        out["pr_auc"] = None
    out["brier"] = float(brier_score_loss(y_true, probs))
    # ECE, 10 equal-width bins
    bins = np.clip((probs * 10).astype(int), 0, 9)
    ece = 0.0
    for b in range(10):
        m = bins == b
        if m.sum():
            ece += m.mean() * abs(float(y_true[m].mean()) - float(probs[m].mean()))
    out["ece_10bin"] = float(ece)
    return out
