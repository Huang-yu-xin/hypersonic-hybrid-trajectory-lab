"""M3-D metrics -- three-class classification, aggregates, regret, closure
and the raretopo-m3d-v0 record schema (task Sec. 18-21, 28, 35, 39).

Pure functions; no I/O, no oracle access, no estimator logic.
"""

from __future__ import annotations

from collections import Counter
from statistics import median

import numpy as np

CLASSES = ("WIDEN", "SHRINK", "HOLD")
RECORD_SCHEMA_VERSION = "raretopo-m3d-v0"


# --------------------------------------------------------------------------- #
# three-class classification (task Sec. 18)
# --------------------------------------------------------------------------- #
def three_class_metrics(y_true, y_pred, classes=CLASSES) -> dict:
    y_true = list(y_true)
    y_pred = list(y_pred)
    assert len(y_true) == len(y_pred) and len(y_true) > 0
    conf = {t: {p: 0 for p in classes} for t in classes}
    for t, p in zip(y_true, y_pred):
        conf[t][p] += 1
    acc = sum(conf[c][c] for c in classes) / len(y_true)
    recalls = {}
    f1s = []
    present = []
    for c in classes:
        tp = conf[c][c]
        fn = sum(conf[c][p] for p in classes if p != c)
        fp = sum(conf[t][c] for t in classes if t != c)
        denom_n = tp + fn
        recalls[c] = (tp / denom_n) if denom_n else None
        if denom_n:
            present.append(c)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / denom_n if denom_n else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    macro_f1 = float(np.mean(f1s))
    recalls_present = [recalls[c] for c in present]
    balanced_acc = (float(np.mean(recalls_present))
                    if recalls_present else float("nan"))
    return {"accuracy": acc, "recall_per_class": recalls,
            "macro_F1": macro_f1, "balanced_accuracy": balanced_acc,
            "confusion_matrix": conf}


# --------------------------------------------------------------------------- #
# statistical hierarchy (task Sec. 35): NOT-IID
# --------------------------------------------------------------------------- #
def state_seed_medians(ratios_by_state: dict) -> dict:
    return {k: float(median(v)) for k, v in ratios_by_state.items()
            if len(v) > 0}


def median_of_state_seed_medians(ratios_by_state: dict) -> float | None:
    meds = state_seed_medians(ratios_by_state)
    if not meds:
        return None
    return float(median(meds.values()))


def win_counts(grad_med: dict, rule_med: dict) -> tuple[int, int, int]:
    """Gradient wins / rule wins / ties at per-state seed-median level."""
    g = s = t = 0
    for k, gm in grad_med.items():
        rm = rule_med.get(k)
        if rm is None or gm is None or not np.isfinite(gm) \
                or not np.isfinite(rm):
            continue
        if gm < rm:
            g += 1
        elif gm > rm:
            s += 1
        else:
            t += 1
    return g, s, t


def regret_rows(records: list[dict]) -> dict:
    """R_M2 = (M2(GRADIENT)-M2(ORACLE))/M2(ORACLE); global + per-class."""
    glob, per_cls = [], {}
    for r in records:
        m = r["metrics"].get("regret_M2")
        if m is None or not np.isfinite(m):
            continue
        cls = r.get("oracle_action", "HOLD")
        glob.append(m)
        per_cls.setdefault(cls, []).append(m)
    out = {"global_median": float(median(glob)) if glob else None,
           "per_class_median": {}}
    for cls, vals in sorted(per_cls.items()):
        vals = [v for v in vals if np.isfinite(v)]
        out["per_class_median"][cls] = float(median(vals)) if vals else None
    return out


def paired_bootstrap_ci(deltas, n_boot: int = 10_000,
                        seed=(20260827,), level: float = 0.95):
    """Percentile bootstrap over supplied paired deltas (state-medians or
    trial rows as preregistered)."""
    d = np.asarray([x for x in deltas if np.isfinite(x)], dtype=float)
    if d.size == 0:
        return None, None, None
    rng = np.random.default_rng(list(seed))
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    means = d[idx].mean(axis=1)
    tail = (1 - level) / 2
    return (float(d.mean()), float(np.quantile(means, tail)),
            float(np.quantile(means, 1 - tail)))


# --------------------------------------------------------------------------- #
# leakage-safety helpers (task Sec. 28)
# --------------------------------------------------------------------------- #
def identity_closure_ok(mode_L: dict, M2: float, rel_tol: float = 1e-9) \
        -> bool:
    s = float(sum(float(v) for v in mode_L.values()))
    m = float(M2)
    return bool(abs(s - m) <= rel_tol * max(abs(m), 1e-300))


def max_offtarget_ratio(L_base: dict, L_grad: dict,
                        selected_mode: str) -> float:
    ratios = []
    for j, lb in L_base.items():
        if j == selected_mode or float(lb) <= 0:
            continue
        lg = L_grad.get(j)
        if lg is None:
            continue
        ratios.append(float(lg) / float(lb))
    return max(ratios) if ratios else float("nan")


# --------------------------------------------------------------------------- #
# record schema (task Sec. 39)
# --------------------------------------------------------------------------- #
ACTION_ENUM = {"WIDEN", "SHRINK", "HOLD_UNCERTAIN", "HOLD_LOW_ESS",
               "HOLD_INVALID"}
ARM_KEYS = ("hold", "widen", "shrink", "gradient", "oracle")


def build_trial_record(*, config_id: str, state_id: str, seed: int,
                       base_s2: float, oracle_action: str,
                       oracle_direction_margin: float, gradient_block: dict,
                       arms_block: dict, metrics_block: dict,
                       validity_block: dict | None = None) -> dict:
    rec = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "config_id": config_id,
        "state_id": state_id,
        "seed": int(seed),
        "base_s2": float(base_s2),
        "oracle_action": oracle_action,
        "oracle_direction_margin": float(oracle_direction_margin),
        "gradient": {
            "g_hat": float(gradient_block["g_hat"]),
            "g_ci_low": float(gradient_block["g_ci_low"]),
            "g_ci_high": float(gradient_block["g_ci_high"]),
            "ESS_grad": float(gradient_block["ESS_grad"]),
            "action": gradient_block["action"],
        },
        "arms": {},
        "metrics": {
            "action_correct": bool(metrics_block["action_correct"]),
            "regret_M2": (float(metrics_block["regret_M2"])
                          if metrics_block.get("regret_M2") is not None
                          else None),
            "VRF_proposal": (float(metrics_block["VRF_proposal"])
                             if metrics_block.get("VRF_proposal") is not None
                             else None),
            "VRF_budget": (float(metrics_block["VRF_budget"])
                           if metrics_block.get("VRF_budget") is not None
                           else None),
        },
        "validity": dict(validity_block or {}),
    }
    for k in ARM_KEYS:
        arm = arms_block[k]
        rec["arms"][k] = {"M2": float(arm["M2"]),
                          "mode_L": {str(a): float(b)
                                     for a, b in arm["mode_L"].items()}}
    return rec


def validate_trial_record(rec: dict) -> bool:
    if rec.get("schema_version") != RECORD_SCHEMA_VERSION:
        return False
    if set(rec.get("arms", {}).keys()) != set(ARM_KEYS):
        return False
    if rec.get("gradient", {}).get("action") not in ACTION_ENUM:
        return False
    if rec.get("oracle_action") not in ("WIDEN", "SHRINK", "HOLD"):
        return False
    for k in ARM_KEYS:
        a = rec["arms"][k]
        if not isinstance(a.get("M2"), (int, float)):
            return False
        if identity_closure_ok(a.get("mode_L", {}),
                               a.get("M2"), rel_tol=1e-6) is False:
            return False
    need = {"config_id", "state_id", "seed", "base_s2"}
    if not need.issubset(rec.keys()):
        return False
    return True


__all__ = [
    "CLASSES", "three_class_metrics", "state_seed_medians",
    "median_of_state_seed_medians", "win_counts", "regret_rows",
    "paired_bootstrap_ci", "identity_closure_ok", "max_offtarget_ratio",
    "build_trial_record", "validate_trial_record",
]
