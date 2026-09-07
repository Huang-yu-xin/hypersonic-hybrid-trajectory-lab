"""M3-S25-R1-A0 Arm-A evaluation (implemented BEFORE authorization).

Runs the frozen parent development comparison on the R1 panel ONCE all
960 trials are durable COMPLETE and the panel truth manifest is unsealed:

  B0 frozen S1                        (not trained; tau = 5.4417199447782)
  B1 aggregate-feature GBDT baseline  (online aggregate quantities only)
  A1 stability logistic               (bootstrap-stability + robust)
  A2 stability GBDT
  A3 stability + practical-margin logistic   (delta via inner grouped OOF)
  A4 stability + practical-margin GBDT

outer GroupKFold(5) / inner GroupKFold(4), groups = config_id; no
test-fold threshold or delta tuning.  Parent safety gates:
coverage >= 0.75, ND unsafe <= 0.20, wrong <= 0.05, AMBIGUOUS unsafe
< 0.25, plus the frozen improvement criterion (coverage gain vs the
aggregate GBDT >= 0.03, or ND-unsafe reduction vs frozen S1 >= 0.05, at
coverage >= 0.75).  Feature families are the parent M3-S2S feature
contract, computed WITHIN each trial only (no cross-replicate aggregation
into features).  Splits replicate the parent ML0 deterministic grouped
semantics: canonical order, GroupKFold over config_id, no shuffling.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.model_selection import GroupKFold

from hyptraj.m3ml0.evaluation import evaluate_policy
from hyptraj.m3ml0.threshold import select_threshold

from hyptraj.m3s25r1.arm_a import (
    DELTA_QUANTILES, GATES, IMPROVEMENT, N_SAMPLES, S1_THRESHOLD, Z95,
    LOGISTIC_GRID, GBDT_GRID, SEED,
)

BOOTSTRAP_STABILITY = ["boot_mean", "boot_median", "boot_std", "boot_MAD",
                       "boot_IQR", "boot_q05", "boot_q25", "boot_q50",
                       "boot_q75", "boot_q95", "boot_mean_minus_median",
                       "boot_sign_probability",
                       "boot_opposite_sign_probability",
                       "boot_near_zero_probability",
                       "boot_quantile_asymmetry", "boot_tail_imbalance"]
BOOTSTRAP_SECONDARY = ["boot_skewness", "boot_excess_kurtosis"]
ROBUST_VS_CLASSICAL = ["g_hat_minus_boot_median",
                       "abs_g_hat_minus_boot_median",
                       "relative_robust_discrepancy"]
INFLUENCE_CONCENTRATION = ["max_abs_influence_fraction",
                           "top_1pct_abs_influence_fraction",
                           "top_5pct_abs_influence_fraction",
                           "top_10pct_abs_influence_fraction",
                           "herfindahl_concentration",
                           "effective_contribution_count"]
EVENT_ESS = ["event_count", "event_rate", "ESS_grad", "ESS_per_event",
             "ESS_fraction"]
AGGREGATE_FEATURES = ["g_hat", "se_g", "ESS_grad", "event_rate", "s2"]
STABILITY_FEATURES = (BOOTSTRAP_STABILITY + ROBUST_VS_CLASSICAL
                      + INFLUENCE_CONCENTRATION + EVENT_ESS
                      + AGGREGATE_FEATURES)

MODEL_FEATURES = {
    "B1_aggregate_gbdt_baseline": AGGREGATE_FEATURES,
    "A1_stability_logistic": STABILITY_FEATURES,
    "A2_stability_gbdt": STABILITY_FEATURES,
    "A3_stability_margin_logistic": STABILITY_FEATURES,
    "A4_stability_margin_gbdt": STABILITY_FEATURES,
}


# --------------------------------------------------------------------------
# feature construction (per trial; truth-free inputs only)
# --------------------------------------------------------------------------

def _boot_stats(bootstrap_g: np.ndarray) -> dict:
    g = np.asarray(bootstrap_g, dtype=float)
    good = g[np.isfinite(g)]
    if good.size < 2:
        raise RuntimeError("M3-S25-R1-X: sidecar bootstrap_g too sparse")
    q05, q25, q50, q75, q95 = (float(x) for x in
                               np.quantile(good, [0.05, 0.25, 0.50, 0.75,
                                                  0.95]))
    mean = float(np.mean(good))
    median = float(np.median(good))
    std = float(np.std(good, ddof=1))
    mad = float(np.median(np.abs(good - median)))
    scale = (q95 - q05) if (q95 - q05) != 0 else 1.0
    centered = good - mean
    var = float(np.mean(centered ** 2)) or 1e-300
    skew = float(np.mean(centered ** 3) / var ** 1.5)
    kurt = float(np.mean(centered ** 4) / (var ** 2) - 3.0)
    sg = np.sign(good)
    return {
        "boot_mean": mean, "boot_median": median, "boot_std": std,
        "boot_MAD": mad, "boot_IQR": q75 - q25,
        "boot_q05": q05, "boot_q25": q25, "boot_q50": q50,
        "boot_q75": q75, "boot_q95": q95,
        "boot_mean_minus_median": mean - median,
        "boot_sign_probability": float(np.mean(sg > 0)),
        "boot_opposite_sign_probability": float(np.mean(sg < 0)),
        "boot_near_zero_probability": float(np.mean(np.abs(good) < 1e-12)),
        "boot_quantile_asymmetry": float((q95 + q05 - 2.0 * q50) / scale),
        "boot_tail_imbalance": float(((q95 - q50) - (q50 - q05)) / scale),
        "boot_skewness": skew,
        "boot_excess_kurtosis": kurt,
    }


def _influence_stats(a_vec: np.ndarray) -> dict:
    a = np.abs(np.asarray(a_vec, dtype=float))
    tot = float(a.sum())
    s = a / tot if tot > 0 else np.full(a.size, 1.0 / max(a.size, 1))
    s_sorted = np.sort(s)[::-1]
    n = s.size

    def _top(frac):
        return float(s_sorted[:max(1, int(math.ceil(frac * n)))].sum())

    hhi = float(np.sum(s ** 2))
    return {
        "max_abs_influence_fraction": float(s_sorted[0]),
        "top_1pct_abs_influence_fraction": _top(0.01),
        "top_5pct_abs_influence_fraction": _top(0.05),
        "top_10pct_abs_influence_fraction": _top(0.10),
        "herfindahl_concentration": hhi,
        "effective_contribution_count": float(1.0 / hhi) if hhi > 0 else 0.0,
    }


def feature_row(record: dict, sidecar_arrays: dict) -> dict:
    """Per-trial feature row from the durable record + sidecar (both
    truth-free)."""
    g = record["gradient"]
    boot = _boot_stats(np.asarray(sidecar_arrays["bootstrap_g"]))
    infl = _influence_stats(np.asarray(sidecar_arrays["a_vec"]))
    se_g = (float(g["g_ci_high"]) - float(g["g_ci_low"])) / (2.0 * Z95)
    ess = float(g["ESS_grad"])
    event_count = int(record["event_count"])
    med = boot["boot_median"]
    row = dict(boot)
    row.update(infl)
    row.update({
        "g_hat_minus_boot_median": float(g["g_hat"]) - med,
        "abs_g_hat_minus_boot_median": abs(float(g["g_hat"]) - med),
        "relative_robust_discrepancy":
            abs(float(g["g_hat"]) - med) / max(abs(med), 1e-300),
        "g_hat": float(g["g_hat"]),
        "se_g": float(se_g),
        "ESS_grad": ess,
        "ESS_per_event": (ess / event_count) if event_count else 0.0,
        "ESS_fraction": ess / N_SAMPLES,
        "event_count": float(event_count),
        "event_rate": float(record["event_rate"]),
        "s2": float(record["s2"]),
        "_abs_g_hat": abs(float(g["g_hat"])),
        "_gradient_valid": bool(record["valid"]),
        "_action_sign": record.get("selected_action"),
        "_s1": record.get("S1"),
        "_config_id": record["config_id"],
        "_state_id": record["state_id"],
        "_rep_id": record["rep_id"],
    })
    return row


def build_feature_frame(records: list[dict],
                        sidecars: list[dict]) -> list[dict]:
    if len(records) != len(sidecars):
        raise RuntimeError("M3-S25-R1-X: records/sidecars length mismatch")
    return [feature_row(r, s) for r, s in zip(records, sidecars)]


# --------------------------------------------------------------------------
# deterministic grouped folds (parent ML0 semantics, R1 row schema)
# --------------------------------------------------------------------------

def _canonical_order(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["_state_id"], r.get("_rep_id", 0)))


def outer_folds(rows: list[dict], n_splits: int = 5):
    X = np.zeros((len(rows), 1))
    y = np.array([1 if r["_truth"] in ("WIDEN", "SHRINK") else 0
                  for r in rows])
    groups = np.array([r["_config_id"] for r in rows])
    gkf = GroupKFold(n_splits=n_splits)
    return [(list(tr), list(te)) for tr, te in gkf.split(X, y, groups)]


def inner_folds(rows: list[dict], indices: list[int], n_splits: int = 4):
    X = np.zeros((len(indices), 1))
    y = np.array([1 if rows[i]["_truth"] in ("WIDEN", "SHRINK") else 0
                  for i in indices])
    groups = np.array([rows[i]["_config_id"] for i in indices])
    gkf = GroupKFold(n_splits=n_splits)
    return [([indices[j] for j in tr], [indices[j] for j in te])
            for tr, te in gkf.split(X, y, groups)]


def split_feasibility(rows: list[dict]) -> dict:
    """GroupKFold(5)/GroupKFold(4) class/config feasibility (preflight
    item; mechanical)."""
    rows = _canonical_order(rows)
    folds = outer_folds(rows, 5)
    report = {"outer": [], "PASS": True}
    seen_test_cfgs = set()
    for k, (tr, te) in enumerate(folds):
        tr_cfg = {rows[i]["_config_id"] for i in tr}
        te_cfg = {rows[i]["_config_id"] for i in te}
        tr_dep = sum(1 for i in tr if rows[i]["_truth"] in ("WIDEN", "SHRINK"))
        tr_nd = len(tr) - tr_dep
        te_dep = sum(1 for i in te if rows[i]["_truth"] in ("WIDEN", "SHRINK"))
        te_nd = len(te) - te_dep
        tr_classes = {rows[i]["_truth"] for i in tr}
        entry = {"outer_fold": k, "train_configs": len(tr_cfg),
                 "test_configs": len(te_cfg), "train_dep": tr_dep,
                 "train_nd": tr_nd, "test_dep": te_dep, "test_nd": te_nd,
                 "train_classes": sorted(tr_classes)}
        ok = (len(tr_cfg) >= 4 and len(tr_classes) == 4 and tr_dep > 0
              and tr_nd > 0 and te_dep > 0 and te_nd > 0
              and not (tr_cfg & te_cfg) and not (te_cfg & seen_test_cfgs))
        entry["PASS"] = ok
        report["PASS"] = report["PASS"] and ok
        report["outer"].append(entry)
        seen_test_cfgs |= te_cfg
        # inner feasibility
        inner = inner_folds(rows, tr, 4)
        inner_ok = True
        for i_tr, _ in inner:
            c = {rows[i]["_config_id"] for i in i_tr}
            d = sum(1 for i in i_tr
                    if rows[i]["_truth"] in ("WIDEN", "SHRINK"))
            if not c or d == 0 or d == len(i_tr):
                inner_ok = False
        entry["inner_GroupKFold4_feasible"] = inner_ok
        report["PASS"] = report["PASS"] and inner_ok
    return report


# --------------------------------------------------------------------------
# frozen comparison models
# --------------------------------------------------------------------------

def _make_model(kind: str, hyper: dict):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    if "gbdt" in kind:
        return HistGradientBoostingClassifier(**hyper)
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, solver="lbfgs",
                                   random_state=SEED, **hyper)),
    ])


def _fit_predict(kind: str, hyper: dict, X_tr, y_tr, X_te):
    m = _make_model(kind, hyper)
    X_tr = np.asarray(X_tr, dtype=float)
    X_te = np.asarray(X_te, dtype=float)
    ok_tr = ~np.isnan(X_tr).any(axis=1)
    ok_te = ~np.isnan(X_te).any(axis=1)
    if ok_tr.sum() == 0 or len(np.unique(np.asarray(y_tr)[ok_tr])) < 2:
        return np.full(len(X_te), np.nan)
    m.fit(X_tr[ok_tr], np.asarray(y_tr)[ok_tr])
    out = np.full(len(X_te), np.nan)
    out[ok_te] = m.predict_proba(X_te[ok_te])[:, 1]
    return out


def _row_matrix(rows: list[dict], feats: list[str],
                delta: float | None) -> np.ndarray:
    cols = feats + (["M_delta"] if delta is not None else [])
    out = np.full((len(rows), len(cols)), np.nan)
    for i, r in enumerate(rows):
        for j, f in enumerate(cols):
            if f == "M_delta":
                out[i, j] = (r["_abs_g_hat"] - delta) / r["se_g"] \
                    if r["se_g"] else 0.0
            else:
                out[i, j] = r[f]
    return out


def _grid_combos(name: str) -> list[dict]:
    """Frozen (hyper, delta) combinations; delta is an inner-OOF-selected
    hyperparameter for the margin models only (values derived from the
    outer-train distribution)."""
    hyper_grid = GBDT_GRID if "gbdt" in name else LOGISTIC_GRID
    if "margin" in name:
        return [{"hyper": h, "delta_q": q}
                for q in DELTA_QUANTILES for h in hyper_grid]
    return [{"hyper": h, "delta_q": None} for h in hyper_grid]


def nested_cv_eval(name: str, rows: list[dict]) -> dict:
    """Grouped nested CV for one trained candidate.  rows carry '_truth'
    (unsealed truth manifest) and the features."""
    n = len(rows)
    oof_deploy = [False] * n
    selection_log = []
    folds = outer_folds(_canonical_order(rows), 5)
    for k, (tr, te) in enumerate(folds):
        tr_v = [i for i in tr if rows[i]["_gradient_valid"]]
        te_v = [i for i in te if rows[i]["_gradient_valid"]]
        rows_tr = [rows[i] for i in tr_v]
        y_tr = np.array([1 if rows[i]["_truth"] in ("WIDEN", "SHRINK")
                         else 0 for i in tr_v])
        deltas = {q: float(np.quantile([r["_abs_g_hat"] for r in rows_tr], q))
                  for q in DELTA_QUANTILES}
        combos = _grid_combos(name)
        inner = inner_folds(rows, tr_v, 4)
        best = None
        for combo in combos:
            delta = None if combo["delta_q"] is None \
                else deltas[combo["delta_q"]]
            X_all = _row_matrix(rows_tr, MODEL_FEATURES[name], delta)
            probs = np.full(len(tr_v), np.nan)
            pos = {i: j for j, i in enumerate(tr_v)}
            for i_tr, i_te in inner:
                p = _fit_predict(name, combo["hyper"],
                                 X_all[[pos[i] for i in i_tr]],
                                 y_tr[[pos[i] for i in i_tr]],
                                 X_all[[pos[i] for i in i_te]])
                for j, i in enumerate(i_te):
                    probs[pos[i]] = p[j]
            scored = ~np.isnan(probs)
            if scored.sum() == 0:
                continue
            y_in = y_tr[scored]
            nd_in = np.array([rows[i]["_truth"] in ("HOLD", "AMBIGUOUS")
                              for i, s in zip(tr_v, scored) if s])
            t, diag = select_threshold(probs[scored], y_in, nd_in)
            dep = probs[scored] >= t
            n_dep = int((~nd_in).sum())
            n_nd = int(nd_in.sum())
            cov = float(dep[~nd_in].mean()) if n_dep else 0.0
            unsafe = float(dep[nd_in].mean()) if n_nd else 0.0
            key = (-cov, unsafe, -t)
            if best is None or key < best["key"]:
                best = {"key": key, "hyper": combo["hyper"],
                        "delta": delta, "delta_q": combo["delta_q"],
                        "threshold": float(t), "inner_coverage": cov,
                        "inner_unsafe": unsafe}
        if best is None:
            raise RuntimeError(
                f"M3-S25-R1-X: inner CV produced no candidate for {name}, "
                f"outer fold {k}")
        selection_log.append({"outer_fold": k, "hyper": best["hyper"],
                              "delta": best["delta"],
                              "delta_q": best["delta_q"],
                              "threshold": best["threshold"]})
        rows_te = [rows[i] for i in te_v]
        X_tr = _row_matrix(rows_tr, MODEL_FEATURES[name], best["delta"])
        X_te = _row_matrix(rows_te, MODEL_FEATURES[name], best["delta"])
        probs_te = _fit_predict(name, best["hyper"], X_tr, y_tr, X_te)
        for j, i in enumerate(te_v):
            if not np.isnan(probs_te[j]):
                oof_deploy[i] = bool(probs_te[j] >= best["threshold"])
    return {"oof_deploy": oof_deploy, "selection_log": selection_log}


def frozen_s1_deploy(rows: list[dict]) -> list[bool]:
    return [bool(r["_gradient_valid"] and r["_s1"] is not None
                 and float(r["_s1"]) >= S1_THRESHOLD) for r in rows]


def policy_metrics(rows: list[dict], deploy: list[bool]) -> dict:
    """Parent policy metrics (ML0 conventions) + AMBIGUOUS-unsafe gate."""
    eval_rows = [{"truth": r["_truth"], "action_sign": r["_action_sign"],
                  "g_hat": 0.0} for r in rows]
    # evaluate_policy derives wrongness from action_sign when present
    out = evaluate_policy(eval_rows, deploy)
    amb = [d for d, r in zip(deploy, rows) if r["_truth"] == "AMBIGUOUS"]
    out["ambiguous_unsafe"] = (float(sum(1 for d in amb if d) / len(amb))
                               if amb else 0.0)
    return out


def run_comparison(records: list[dict], sidecars: list[dict],
                   truth_by_state: dict[str, str]) -> dict:
    """The frozen parent development comparison; the CALLER must enforce
    960/960 durable COMPLETE before unsealing the truth manifest."""
    rows = build_feature_frame(records, sidecars)
    if len(rows) != 960:
        raise RuntimeError("M3-S25-R1-X: comparison requires 960 trials")
    for r in rows:
        if r["_state_id"] not in truth_by_state:
            raise RuntimeError(
                f"M3-S25-R1-X: state without sealed truth: {r['_state_id']}")
        r["_truth"] = truth_by_state[r["_state_id"]]
    rows = _canonical_order(rows)
    results = {"n_trials": len(rows)}
    dep0 = frozen_s1_deploy(rows)
    results["B0_frozen_S1"] = policy_metrics(rows, dep0)
    for name in ("B1_aggregate_gbdt_baseline", "A1_stability_logistic",
                 "A2_stability_gbdt", "A3_stability_margin_logistic",
                 "A4_stability_margin_gbdt"):
        cv = nested_cv_eval(name, rows)
        m = policy_metrics(rows, cv["oof_deploy"])
        m["selection_log"] = cv["selection_log"]
        results[name] = m
    return results


def verdict(results: dict, complete: int, consumed_invalid: int) -> dict:
    """Frozen R1-local terminal names; the scientific gate is the
    parent's."""
    if consumed_invalid or complete != 960:
        return {"VERDICT": "M3-S25-R1-X",
                "reason": f"completeness {complete}/960, consumed_invalid "
                          f"{consumed_invalid}"}
    b1 = results["B1_aggregate_gbdt_baseline"]
    b0 = results["B0_frozen_S1"]
    compliant = {}
    for name, m in results.items():
        if name == "n_trials" or name not in MODEL_FEATURES:
            continue
        ok = (m["deployable_coverage"] >= GATES["coverage_min"]
              and m["nd_unsafe"] <= GATES["unsafe_max"]
              and m["wrong_direction_rate"] <= GATES["wrong_max"]
              and m["ambiguous_unsafe"] < GATES["ambiguous_unsafe_max"])
        improved = (
            m["deployable_coverage"] - b1["deployable_coverage"]
            >= IMPROVEMENT["coverage_gain_vs_aggregate_gbdt"]
            or (b0["nd_unsafe"] - m["nd_unsafe"]
                >= IMPROVEMENT["unsafe_reduction_vs_frozen_s1"]
                and m["deployable_coverage"] >= IMPROVEMENT["at_coverage_min"]))
        if ok and improved:
            compliant[name] = True
    if compliant:
        return {"VERDICT": "M3-S25-R1-A", "compliant": sorted(compliant),
                "note": "Arm-A development success; Arm B NOT RUN"}
    return {"VERDICT": "M3-S25-R1-B-GATE",
            "note": "valid Arm-A completion but no compliant candidate; "
                    "STOP for separate Arm-B review"}
