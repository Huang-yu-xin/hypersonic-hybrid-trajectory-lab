"""M3-S25-R1-A2R Arm-B evaluation: LOCAL-SHAPE feature family.

Runs the Arm-B evaluation on the R1 panel ONCE all 1920 side trials are
durable COMPLETE with 0 CONSUMED_INVALID and the panel truth manifest is
unsealed:

  B0 frozen S1                        (not trained; tau = 5.4417199447782)
  B1 aggregate-feature GBDT baseline  (online aggregate quantities only)
  B1_LS local-shape GBDT             (12 local-shape features from sidecar)
  B1_LS_LOG local-shape logistic     (12 local-shape features from sidecar)

Arm-B uses the LOCAL-SHAPE feature family (12 features) computed from
center/left/right sidecar gradient records.  The features capture the
local shape of the gradient landscape around each state:

  local_sign_persistence, left_sign_match, right_sign_match,
  three_point_sign_pattern, gradient_slope, left_slope, right_slope,
  slope_asymmetry, relative_gradient_slope, local_gradient_range,
  local_S1_range, g_double_prime_descriptive

outer GroupKFold(5) / inner GroupKFold(4), groups = config_id; no
test-fold threshold or delta tuning.  Arm-B success gates:

  coverage >= 0.75
  ND unsafe <= 0.20
  wrong <= 0.05
  AMBIGUOUS unsafe < 0.25

  AND relative to best Arm-A (A4_stability_margin_gbdt, frozen from A2R):
    coverage gain >= 0.03 vs A4's 0.8667
    OR: ND unsafe reduction >= 0.05 vs A4's 0.2104, with coverage >= 0.75

Terminal verdicts:
  M3-S25-R1-A2R-C  Arm-B success
  M3-S25-R1-A2R-D  valid negative
  M3-S25-R1-A2R-X  integrity invalid

B0/B1 baselines are still reported but NOT the primary comparison target.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.model_selection import GroupKFold

from hyptraj.m3ml0.evaluation import evaluate_policy
from hyptraj.m3ml0.threshold import select_threshold

from hyptraj.m3s25r1.arm_a import (
    DELTA_QUANTILES, LOGISTIC_GRID, GBDT_GRID, SEED, S1_THRESHOLD, Z95,
)

# --------------------------------------------------------------------------
# Arm-B constants
# --------------------------------------------------------------------------

N_SAMPLES = 20_000
N_STATES = 120
REPLICATES = 8
N_SIDES = 2                           # left, right
N_SIDE_TRIALS = N_STATES * REPLICATES * N_SIDES  # 1920
N_CENTER_TRIALS = N_STATES * REPLICATES           # 960

GATES = {"coverage_min": 0.75, "unsafe_max": 0.20, "wrong_max": 0.05,
         "ambiguous_unsafe_max": 0.25}

# Frozen best Arm-A comparator (A2R frozen from A2R evaluation)
A4_IDENTITY = "A4_stability_margin_gbdt"
A4_FROZEN = {
    "deployable_coverage": 0.8666666666666667,
    "nd_unsafe": 0.21041666666666667,
    "wrong_direction_rate": 0.0,
    "ambiguous_unsafe": 0.3541666666666667,
}

# Arm-B improvement criterion (relative to frozen A4)
IMPROVEMENT_VS_A4 = {
    "coverage_gain_vs_a4": 0.03,
    "unsafe_reduction_vs_a4": 0.05,
    "at_coverage_min": 0.75,
}

# --------------------------------------------------------------------------
# LOCAL-SHAPE feature family (12 features)
# --------------------------------------------------------------------------

LOCAL_SHAPE_FEATURES = [
    "local_sign_persistence",
    "left_sign_match",
    "right_sign_match",
    "three_point_sign_pattern",
    "gradient_slope",
    "left_slope",
    "right_slope",
    "slope_asymmetry",
    "relative_gradient_slope",
    "local_gradient_range",
    "local_S1_range",
    "g_double_prime_descriptive",
]

# Aggregate features for the B1 baseline (ML0 B3 frozen)
ML0_B1_FEATURES = ["S1", "g_hat", "abs_g_hat", "SE_g", "CI_width", "s2",
                   "curvature_c", "ESS_grad", "gradient_valid"]
AGGREGATE_FEATURES = ML0_B1_FEATURES

# Per-candidate feature sets
MODEL_FEATURES = {
    "B1_aggregate_gbdt_baseline": AGGREGATE_FEATURES,
    "B1_LS_local_shape_gbdt": LOCAL_SHAPE_FEATURES,
    "B1_LS_LOG_local_shape_logistic": LOCAL_SHAPE_FEATURES,
}

# A0.1 item 5: comparators (B0/B1) can never trigger M3-S25-R1-A2R-C
SUCCESS_ELIGIBLE = ("B1_LS_local_shape_gbdt",
                    "B1_LS_LOG_local_shape_logistic")


# --------------------------------------------------------------------------
# feature construction (per state x rep; local-shape from sidecar)
# --------------------------------------------------------------------------

def _extract_gradient(record: dict) -> dict:
    """Extract gradient scalars from a trial record's gradient sub-dict."""
    g = record.get("gradient", {})
    valid = bool(record.get("valid", False))
    g_hat = float(g["g_hat"]) if valid and g.get("g_hat") is not None else math.nan
    ci_high = float(g["g_ci_high"]) if valid and g.get("g_ci_high") is not None else math.nan
    ci_low = float(g["g_ci_low"]) if valid and g.get("g_ci_low") is not None else math.nan
    se_g = (ci_high - ci_low) / (2.0 * Z95) if (valid and math.isfinite(ci_high)
                                                   and math.isfinite(ci_low)
                                                   and ci_high != ci_low) else math.nan
    return {"g_hat": g_hat, "ci_high": ci_high, "ci_low": ci_low,
            "se_g": se_g, "valid": valid}


def _local_shape_features(center_rec: dict, left_rec: dict,
                          right_rec: dict) -> dict:
    """Compute 12 local-shape features from center/left/right gradient records.

    These capture the local shape of the gradient landscape around each
    state by comparing the center trial's gradient with the left and right
    side trials' gradients.

    All inputs are truth-free (derived only from durable trial records
    and sidecars)."""
    c = _extract_gradient(center_rec)
    l = _extract_gradient(left_rec)
    r = _extract_gradient(right_rec)

    gc, gl, gr = c["g_hat"], l["g_hat"], r["g_hat"]
    g_valid_c, g_valid_l, g_valid_r = c["valid"], l["valid"], r["valid"]
    se_c, se_l, se_r = c["se_g"], l["se_g"], r["se_g"]

    # S1 values for S1-range computation
    s1_c = float(center_rec["S1"]) if (center_rec.get("S1") is not None
                                       and g_valid_c) else math.nan
    s1_l = float(left_rec["S1"]) if (left_rec.get("S1") is not None
                                     and g_valid_l) else math.nan
    s1_r = float(right_rec["S1"]) if (right_rec.get("S1") is not None
                                      and g_valid_r) else math.nan

    row = {}

    # --- sign features ---
    # local_sign_persistence: fraction of center/left/right that share the
    # center's sign (NaN if center is NaN)
    if math.isfinite(gc):
        center_sign = 1 if gc > 0 else (-1 if gc < 0 else 0)
        signs = [center_sign]
        if g_valid_l and math.isfinite(gl):
            signs.append(1 if gl > 0 else (-1 if gl < 0 else 0))
        if g_valid_r and math.isfinite(gr):
            signs.append(1 if gr > 0 else (-1 if gr < 0 else 0))
        n_match = sum(1 for s in signs if s == center_sign and center_sign != 0)
        row["local_sign_persistence"] = n_match / max(len(signs), 1)
    else:
        row["local_sign_persistence"] = math.nan

    # left_sign_match: binary 1.0 if left sign matches center, 0.0 if not
    if math.isfinite(gc) and g_valid_l and math.isfinite(gl):
        cs = 1 if gc > 0 else (-1 if gc < 0 else 0)
        ls = 1 if gl > 0 else (-1 if gl < 0 else 0)
        row["left_sign_match"] = 1.0 if (cs == ls and cs != 0) else 0.0
    else:
        row["left_sign_match"] = math.nan

    # right_sign_match: binary 1.0 if right sign matches center, 0.0 if not
    if math.isfinite(gc) and g_valid_r and math.isfinite(gr):
        cs = 1 if gc > 0 else (-1 if gc < 0 else 0)
        rs = 1 if gr > 0 else (-1 if gr < 0 else 0)
        row["right_sign_match"] = 1.0 if (cs == rs and cs != 0) else 0.0
    else:
        row["right_sign_match"] = math.nan

    # three_point_sign_pattern: -1 (all negative) / 0 (mixed) / 1 (all positive)
    # NaN if any gradient is invalid or NaN
    vals = [gc, gl, gr]
    valids = [g_valid_c, g_valid_l, g_valid_r]
    if all(v for v in valids) and all(math.isfinite(v) for v in vals):
        sgns = [1 if v > 0 else (-1 if v < 0 else 0) for v in vals]
        if all(s == 1 for s in sgns):
            row["three_point_sign_pattern"] = 1.0
        elif all(s == -1 for s in sgns):
            row["three_point_sign_pattern"] = -1.0
        else:
            row["three_point_sign_pattern"] = 0.0
    else:
        row["three_point_sign_pattern"] = math.nan

    # --- slope features ---
    # gradient_slope: signed difference left-to-right (gr - gl)
    if (g_valid_l and g_valid_r
            and math.isfinite(gl) and math.isfinite(gr)):
        row["gradient_slope"] = gr - gl
    else:
        row["gradient_slope"] = math.nan

    # left_slope: signed difference center-to-left (gc - gl)
    if (g_valid_c and g_valid_l
            and math.isfinite(gc) and math.isfinite(gl)):
        row["left_slope"] = gc - gl
    else:
        row["left_slope"] = math.nan

    # right_slope: signed difference center-to-right (gc - gr)
    if (g_valid_c and g_valid_r
            and math.isfinite(gc) and math.isfinite(gr)):
        row["right_slope"] = gc - gr
    else:
        row["right_slope"] = math.nan

    # slope_asymmetry: |left_slope - right_slope| / (|left_slope| + |right_slope| + eps)
    ls = row.get("left_slope", math.nan)
    rs = row.get("right_slope", math.nan)
    if math.isfinite(ls) and math.isfinite(rs):
        denom = abs(ls) + abs(rs)
        row["slope_asymmetry"] = abs(ls - rs) / (denom + 1e-300)
    else:
        row["slope_asymmetry"] = math.nan

    # relative_gradient_slope: gradient_slope / (|gc| + eps)
    gs = row.get("gradient_slope", math.nan)
    if math.isfinite(gs) and math.isfinite(gc):
        row["relative_gradient_slope"] = gs / (abs(gc) + 1e-300)
    else:
        row["relative_gradient_slope"] = math.nan

    # --- range features ---
    # local_gradient_range: max(g_c, g_l, g_r) - min(g_c, g_l, g_r)
    gv = [v for v in [gc, gl, gr] if math.isfinite(v)]
    row["local_gradient_range"] = (max(gv) - min(gv)) if len(gv) >= 2 else math.nan

    # local_S1_range: max(s1_c, s1_l, s1_r) - min(...)
    sv = [v for v in [s1_c, s1_l, s1_r] if math.isfinite(v)]
    row["local_S1_range"] = (max(sv) - min(sv)) if len(sv) >= 2 else math.nan

    # g_double_prime_descriptive: second-order discrete difference at center
    # = gl + gr - 2*gc  (how much the center deviates from the linear
    # interpolation of the two neighbors)
    if (g_valid_l and g_valid_r and g_valid_c
            and math.isfinite(gl) and math.isfinite(gr)
            and math.isfinite(gc)):
        row["g_double_prime_descriptive"] = gl + gr - 2.0 * gc
    else:
        row["g_double_prime_descriptive"] = math.nan

    return row


def _boot_stats(bootstrap_g: np.ndarray) -> dict:
    """Bootstrap stability statistics (same as arm_a_eval)."""
    g = np.asarray(bootstrap_g, dtype=float)
    good = g[np.isfinite(g)]
    if good.size < 2:
        raise RuntimeError("M3-S25-R1-A2R-X: sidecar bootstrap_g too sparse")
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
    """Influence concentration statistics (same as arm_a_eval)."""
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


def aggregate_feature_row(record: dict, sidecar_arrays: dict) -> dict:
    """Per-trial aggregate feature row (B1 baseline) from the durable
    record + sidecar (both truth-free).  Same as arm_a_eval.feature_row."""
    g = record["gradient"]
    boot = _boot_stats(np.asarray(sidecar_arrays["bootstrap_g"]))
    infl = _influence_stats(np.asarray(sidecar_arrays["a_vec"]))
    se_g = (float(g["g_ci_high"]) - float(g["g_ci_low"])) / (2.0 * Z95)
    ess = float(g["ESS_grad"])
    event_count = int(record["event_count"])
    med = boot["boot_median"]
    row = dict(boot)
    row.update(infl)
    valid = bool(record["valid"])
    s1v = (float(record["S1"]) if valid and record.get("S1") is not None
           else math.nan)
    gh = float(g["g_hat"]) if valid else math.nan
    ciw = (float(g["g_ci_high"]) - float(g["g_ci_low"])
           if valid else math.nan)
    row.update({
        "g_hat_minus_boot_median": float(g["g_hat"]) - med,
        "abs_g_hat_minus_boot_median": abs(float(g["g_hat"]) - med),
        "relative_robust_discrepancy":
            abs(float(g["g_hat"]) - med) / max(abs(med), 1e-300),
        "g_hat": gh,
        "abs_g_hat": abs(gh) if valid else math.nan,
        "SE_g": float(se_g),
        "CI_width": ciw,
        "curvature_c": float(record["curvature_c"]),
        "gradient_valid": 1.0 if valid else 0.0,
        "ESS_grad": ess,
        "ESS_per_event": (ess / event_count) if event_count else 0.0,
        "ESS_fraction": ess / N_SAMPLES,
        "event_count": float(event_count),
        "event_rate": float(record["event_rate"]),
        "s2": float(record["s2"]),
        "S1": s1v,
        "_abs_g_hat": abs(float(g["g_hat"])),
        "_gradient_valid": valid,
        "_action_sign": record.get("selected_action"),
        "_s1": record.get("S1"),
        "_config_id": record["config_id"],
        "_state_id": record["state_id"],
        "_rep_id": record["rep_id"],
    })
    return row


def build_feature_frame(records: list[dict],
                        sidecars: list[dict],
                        side_trials: list[dict] | None = None,
                        side_sidecars: list[dict] | None = None,
                        ) -> list[dict]:
    """Build the combined feature frame.

    For center-trial-only features (aggregate/B1 baseline): pass
    ``records`` and ``sidecars`` only.

    For local-shape features (Arm-B): additionally pass ``side_trials``
    and ``side_sidecars`` (lists of 1920 side-trial records/sidecars).
    The side trials are indexed by (state_id, rep_id) to pair with the
    center trial.

    Returns one row per center trial (960 rows) with both aggregate and
    local-shape features merged.
    """
    if len(records) != len(sidecars):
        raise RuntimeError("M3-S25-R1-A2R-X: records/sidecars length mismatch")

    # Build side-trial lookup: (state_id, rep_id) -> {side: record, sidecar}
    side_lookup: dict[tuple[str, int], dict] = {}
    if side_trials is not None and side_sidecars is not None:
        if len(side_trials) != len(side_sidecars):
            raise RuntimeError(
                "M3-S25-R1-A2R-X: side_trials/side_sidecars length mismatch")
        for st, sc in zip(side_trials, side_sidecars):
            key = (st["state_id"], st["rep_id"])
            side = st.get("side")
            if side not in ("left", "right"):
                raise RuntimeError(
                    f"M3-S25-R1-A2R-X: invalid side {side!r} for "
                    f"{st['state_id']}|rep{st['rep_id']}")
            if key not in side_lookup:
                side_lookup[key] = {}
            side_lookup[key][side] = (st, sc)

    rows = []
    for rec, sc in zip(records, sidecars):
        row = aggregate_feature_row(rec, sc)
        key = (rec["state_id"], rec["rep_id"])
        if key in side_lookup and len(side_lookup[key]) == 2:
            left_rec, _ = side_lookup[key]["left"]
            right_rec, _ = side_lookup[key]["right"]
            ls = _local_shape_features(rec, left_rec, right_rec)
            row.update(ls)
            row["_has_local_shape"] = True
        else:
            # fill NaN for all local-shape features
            for feat in LOCAL_SHAPE_FEATURES:
                row[feat] = math.nan
            row["_has_local_shape"] = False
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# deterministic grouped folds (same as arm_a_eval)
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
# frozen comparison models (same as arm_a_eval)
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
                den = r.get("SE_g") or r.get("se_g") or 0.0
                out[i, j] = (r["_abs_g_hat"] - delta) / den \
                    if den else 0.0
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
    (unsealed truth manifest) and the features.  OOF probabilities are
    preserved for the frozen secondary-metrics contract (ROC-AUC / PR-AUC
    / Brier / ECE on scored OOF rows); they never affect the primary
    verdict."""
    n = len(rows)
    oof_deploy = [False] * n
    oof_prob: dict[int, float] = {}
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
                f"M3-S25-R1-A2R-X: inner CV produced no candidate for "
                f"{name}, outer fold {k}")
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
                oof_prob[i] = float(probs_te[j])
    return {"oof_deploy": oof_deploy, "oof_prob": oof_prob,
            "selection_log": selection_log}


def frozen_s1_deploy(rows: list[dict]) -> list[bool]:
    return [bool(r["_gradient_valid"] and r["_s1"] is not None
                 and float(r["_s1"]) >= S1_THRESHOLD) for r in rows]


def secondary_metrics(oof_prob: dict[int, float],
                      rows: list[dict]) -> dict:
    """Frozen secondary metrics on SCORED OOF rows (A0.1 item 7):
    ROC-AUC / PR-AUC / Brier / ECE (10 equal-width bins).  These never
    affect the primary verdict."""
    from sklearn.metrics import (average_precision_score, brier_score_loss,
                                 roc_auc_score)
    idx = sorted(oof_prob)
    if len(idx) < 2:
        return {"roc_auc": None, "pr_auc": None, "brier": None, "ece": None,
                "n_scored": len(idx)}
    p = np.asarray([oof_prob[i] for i in idx], dtype=float)
    y = np.asarray([1 if rows[i]["_truth"] in ("WIDEN", "SHRINK") else 0
                    for i in idx], dtype=int)
    out = {"n_scored": int(len(idx))}
    out["roc_auc"] = float(roc_auc_score(y, p)) if len(set(y)) == 2 else None
    out["pr_auc"] = (float(average_precision_score(y, p))
                     if len(set(y)) == 2 else None)
    out["brier"] = float(brier_score_loss(y, p))
    # ECE: 10 equal-width bins on [0, 1]
    bins = np.clip((p * 10.0).astype(int), 0, 9)
    ece = 0.0
    for b in range(10):
        m = bins == b
        if m.sum() == 0:
            continue
        ece += (m.sum() / len(p)) * abs(float(y[m].mean()) - float(p[m].mean()))
    out["ece"] = float(ece)
    return out


def policy_metrics(rows: list[dict], deploy: list[bool]) -> dict:
    """Parent policy metrics (ML0 conventions) + AMBIGUOUS-unsafe gate."""
    eval_rows = [{"truth": r["_truth"], "action_sign": r["_action_sign"],
                  "g_hat": 0.0} for r in rows]
    out = evaluate_policy(eval_rows, deploy)
    amb = [d for d, r in zip(deploy, rows) if r["_truth"] == "AMBIGUOUS"]
    out["ambiguous_unsafe"] = (float(sum(1 for d in amb if d) / len(amb))
                               if amb else 0.0)
    return out


# --------------------------------------------------------------------------
# Arm-B comparison (frozen A4 comparator)
# --------------------------------------------------------------------------

def run_comparison(records: list[dict], sidecars: list[dict],
                   truth_by_state: dict[str, str],
                   side_trials: list[dict] | None = None,
                   side_sidecars: list[dict] | None = None) -> dict:
    """The frozen Arm-B evaluation; the CALLER must enforce
    1920/1920 side trials durable COMPLETE with 0 CONSUMED_INVALID before
    unsealing the truth manifest.

    Side trials are optional for testing (when absent, local-shape
    features are NaN and local-shape candidates are not evaluable)."""
    rows = build_feature_frame(records, sidecars, side_trials, side_sidecars)
    if len(rows) != N_CENTER_TRIALS:
        raise RuntimeError(
            f"M3-S25-R1-A2R-X: comparison requires {N_CENTER_TRIALS} trials, "
            f"got {len(rows)}")
    for r in rows:
        if r["_state_id"] not in truth_by_state:
            raise RuntimeError(
                f"M3-S25-R1-A2R-X: state without sealed truth: "
                f"{r['_state_id']}")
        r["_truth"] = truth_by_state[r["_state_id"]]
    rows = _canonical_order(rows)
    results = {"n_trials": len(rows), "n_side_trials": len(side_trials)
               if side_trials is not None else 0}

    # --- B0 frozen S1 baseline ---
    dep0 = frozen_s1_deploy(rows)
    results["B0_frozen_S1"] = policy_metrics(rows, dep0)

    # --- B1 aggregate GBDT baseline (comparator, not success-eligible) ---
    cv_b1 = nested_cv_eval("B1_aggregate_gbdt_baseline", rows)
    m_b1 = policy_metrics(rows, cv_b1["oof_deploy"])
    m_b1["selection_log"] = cv_b1["selection_log"]
    m_b1["secondary"] = secondary_metrics(cv_b1["oof_prob"], rows)
    results["B1_aggregate_gbdt_baseline"] = m_b1

    # --- local-shape candidates (success-eligible) ---
    for name in ("B1_LS_local_shape_gbdt",
                 "B1_LS_LOG_local_shape_logistic"):
        has_ls = sum(1 for r in rows if r.get("_has_local_shape", False))
        if has_ls == 0:
            # no sidecar data available; report NaN metrics
            results[name] = {
                "deployable_coverage": math.nan,
                "nd_unsafe": math.nan,
                "wrong_direction_rate": math.nan,
                "ambiguous_unsafe": math.nan,
                "selection_log": [],
                "secondary": {"n_scored": 0},
                "note": "no local-shape features available",
            }
            continue
        cv = nested_cv_eval(name, rows)
        m = policy_metrics(rows, cv["oof_deploy"])
        m["selection_log"] = cv["selection_log"]
        m["secondary"] = secondary_metrics(cv["oof_prob"], rows)
        results[name] = m

    return results


def verdict(results: dict, complete: int, consumed_invalid: int,
            prefix: str = "M3-S25-R1") -> dict:
    """Frozen R1-A2R terminal verdicts.

    Arm-B success gates:
      Absolute: coverage >= 0.75, ND unsafe <= 0.20, wrong <= 0.05,
                ambiguous_unsafe < 0.25
      Relative to A4 (frozen): coverage gain >= 0.03 OR
                               ND unsafe reduction >= 0.05 with coverage >= 0.75

    Terminal verdicts:
      M3-S25-R1-A2R-C  Arm-B success
      M3-S25-R1-A2R-D  valid negative
      M3-S25-R1-A2R-X  integrity invalid
    """
    if consumed_invalid or complete != N_CENTER_TRIALS:
        return {"VERDICT": f"{prefix}-A2R-X",
                "reason": f"completeness {complete}/{N_CENTER_TRIALS}, "
                          f"consumed_invalid {consumed_invalid}"}

    compliant = {}
    for name in SUCCESS_ELIGIBLE:
        m = results.get(name)
        if m is None:
            continue
        cov = m.get("deployable_coverage")
        nd_unsafe = m.get("nd_unsafe")
        wrong = m.get("wrong_direction_rate")
        amb_unsafe = m.get("ambiguous_unsafe")
        # skip candidates with NaN metrics (no local-shape data)
        if any(v is None or (isinstance(v, float) and math.isnan(v))
               for v in (cov, nd_unsafe, wrong, amb_unsafe)):
            continue

        # Absolute gates
        ok = (cov >= GATES["coverage_min"]
              and nd_unsafe <= GATES["unsafe_max"]
              and wrong <= GATES["wrong_max"]
              and amb_unsafe < GATES["ambiguous_unsafe_max"])

        # Relative improvement vs frozen A4
        a4_cov = A4_FROZEN["deployable_coverage"]
        a4_nd = A4_FROZEN["nd_unsafe"]
        improved = (
            (cov - a4_cov) >= IMPROVEMENT_VS_A4["coverage_gain_vs_a4"]
            or (a4_nd - nd_unsafe
                >= IMPROVEMENT_VS_A4["unsafe_reduction_vs_a4"]
                and cov >= IMPROVEMENT_VS_A4["at_coverage_min"]))

        if ok and improved:
            compliant[name] = True

    if compliant:
        return {"VERDICT": f"{prefix}-A2R-C",
                "compliant": sorted(compliant),
                "note": "Arm-B local-shape success vs frozen A4 comparator"}
    return {"VERDICT": f"{prefix}-A2R-D",
            "note": "valid Arm-B completion; no compliant local-shape "
                    "candidate relative to frozen A4"}
