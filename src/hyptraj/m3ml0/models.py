"""M3-ML0 model hierarchy and grouped nested-CV engine (taskbook Sec. 9-12).

B0  frozen S1                       (not trained; tau = 5.4417199447782)
B1  LogisticRegression(S1)          learned calibration of S1 only
B2  L2 Logistic on F0 core          interpretable S2
B3  HistGradientBoostingClassifier  small preregistered grid
B4  MLP                             NOT_AUTHORIZED (48 independent states < 100)

Hyperparameters and deploy thresholds are selected ONLY on inner grouped CV
within each outer-train set; outer-test rows are scored exactly once.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from hyptraj.m3ml0.features import MODEL_FEATURES
from hyptraj.m3ml0.splits import grouped_inner_folds
from hyptraj.m3ml0.threshold import select_threshold

SEED = 2026

LOGISTIC_GRID = [{"C": c, "class_weight": w}
                 for c in (0.1, 1.0, 10.0) for w in (None, "balanced")]
GBDT_GRID = [{"max_iter": mi, "max_leaf_nodes": ln, "learning_rate": lr,
              "l2_regularization": l2, "random_state": SEED}
             for mi in (50, 100) for ln in (7, 15)
             for lr in (0.03, 0.1) for l2 in (0, 1)]

GRIDS = {"B1_logistic_s1": LOGISTIC_GRID,
         "B2_s2_logistic": LOGISTIC_GRID,
         "B3_gbdt": GBDT_GRID}


def make_model(name: str, hyper: dict):
    feats = MODEL_FEATURES[name]
    if name.startswith("B3"):
        return HistGradientBoostingClassifier(**hyper)
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, solver="lbfgs",
                                   random_state=SEED, **hyper)),
    ])


def mlp_authorized(n_states: int) -> bool:
    return n_states >= 100


def _fit_predict(name, hyper, feats, X_tr, y_tr, X_te):
    m = make_model(name, hyper)
    X_tr = np.asarray(X_tr, dtype=float)
    X_te = np.asarray(X_te, dtype=float)
    if name.startswith("B3"):
        # HistGBDT accepts NaN natively; other rows are NaN-free by
        # construction except S1/SE fields on... valid rows only -> no NaN
        m.fit(X_tr, y_tr)
        return m.predict_proba(X_te)[:, 1]
    ok_tr = ~np.isnan(X_tr).any(axis=1)
    ok_te = ~np.isnan(X_te).any(axis=1)
    if ok_tr.sum() == 0:
        return np.full(len(X_te), np.nan)
    m.fit(X_tr[ok_tr], np.asarray(y_tr)[ok_tr])
    out = np.full(len(X_te), np.nan)
    out[ok_te] = m.predict_proba(X_te[ok_te])[:, 1]
    return out


def nested_cv_eval(name: str, rows: list[dict], outer_folds) -> dict:
    """Grouped nested-CV: returns OOF deploy decisions + diagnostics.

    rows: canonical trial rows (with features attached in 'fr').
    Invalid-gradient rows are never scored and always ABSTAIN.
    """
    feats = MODEL_FEATURES[name]
    n = len(rows)
    oof_deploy = [False] * n
    oof_prob: dict[int, float] = {}
    selection_log = []
    valid_idx = [i for i, r in enumerate(rows) if r["gradient_valid"]]
    y_all = np.array([int(rows[i]["label_deploy"]) for i in valid_idx])
    X_all = np.asarray([rows[i]["_X"][name] for i in valid_idx], dtype=float)

    for k, (tr, te) in enumerate(outer_folds):
        tr_v = [i for i in tr if rows[i]["gradient_valid"]]
        te_v = [i for i in te if rows[i]["gradient_valid"]]
        X_tr = np.asarray([rows[i]["_X"][name] for i in tr_v], dtype=float)
        y_tr = np.array([int(rows[i]["label_deploy"]) for i in tr_v])
        # ---- inner grouped CV: hyperparameter + threshold selection ------
        inner = grouped_inner_folds(rows, tr_v, n_splits=4)
        best = None
        for hyper in GRIDS[name]:
            probs = np.full(len(tr_v), np.nan)
            for itr, ite in inner:
                p = _fit_predict(name, hyper, feats,
                                 X_all[[valid_idx.index(i) for i in itr]],
                                 y_all[[valid_idx.index(i) for i in itr]],
                                 X_all[[valid_idx.index(i) for i in ite]])
                for j, i in enumerate(ite):
                    probs[tr_v.index(i)] = p[j]
            scored = ~np.isnan(probs)
            y_in = np.array([int(rows[i]["label_deploy"]) for i in tr_v])
            nd_in = np.array([rows[i]["truth"] in ("HOLD", "AMBIGUOUS")
                              for i in tr_v])
            t, diag = select_threshold(probs[scored], y_in[scored], nd_in[scored])
            cov, unsafe, harmful, ndep = _inner_metrics(probs[scored],
                                                        y_in[scored],
                                                        nd_in[scored], t)
            key = (-cov, unsafe, harmful, -t)
            if best is None or key < best["key"]:
                best = {"key": key, "hyper": hyper, "threshold": t,
                        "inner_coverage": cov, "inner_unsafe": unsafe,
                        "inner_harmful": harmful, "abstain_all": diag["abstain_all"]}
        selection_log.append({"outer_fold": k, **best})
        # ---- refit on full outer-train, score outer-test exactly once ----
        X_te = np.asarray([rows[i]["_X"][name] for i in te_v], dtype=float)
        y_te = np.array([int(rows[i]["label_deploy"]) for i in te_v])
        probs_te = _fit_predict(name, best["hyper"], feats, X_tr, y_tr, X_te)
        t = best["threshold"]
        for j, i in enumerate(te_v):
            if not np.isnan(probs_te[j]):
                oof_prob[i] = float(probs_te[j])
                oof_deploy[i] = bool(probs_te[j] >= t)
    return {"oof_deploy": oof_deploy, "oof_prob": oof_prob,
            "selection_log": selection_log}


def _inner_metrics(probs, y, is_nd, t):
    deploy = probs >= t
    n_dep = int((~is_nd).sum())
    n_nd = int(is_nd.sum())
    cov = float(deploy[~is_nd].mean()) if n_dep else 0.0
    unsafe = float(deploy[is_nd].mean()) if n_nd else 0.0
    return cov, unsafe, int(deploy[is_nd].sum()), int(deploy.sum())
