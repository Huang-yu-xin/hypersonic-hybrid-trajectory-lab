"""M3-ML0 feature firewall and contract (taskbook Sec. 7).

Only information genuinely available before the deploy/abstain decision may
enter X: the trial's own online gradient statistics and pre-frozen state
metadata.  Truth/reference-derived or identity fields are forbidden.
"""
from __future__ import annotations

import math

Z95 = 1.959963984540054

# feature sets (frozen in configs/phase_m3ml0/m3ml0_feature_contract.json)
F0_CORE = ["S1", "g_hat", "SE_g", "s2", "curvature_c"]
F0_FULL = ["S1", "g_hat", "abs_g_hat", "SE_g", "CI_width", "s2",
           "curvature_c", "ESS_grad", "gradient_valid"]
F1_AVAILABLE = ["ESS_grad"]
F1_NOT_AVAILABLE = ["p_hat_grad", "batch_dispersion", "gradient_batch_variance"]

B1_FEATURES = ["S1"]
B2_FEATURES = F0_CORE
B3_FEATURES = F0_FULL

MODEL_FEATURES = {"B1_logistic_s1": B1_FEATURES,
                  "B2_s2_logistic": B2_FEATURES,
                  "B3_gbdt": B3_FEATURES}

# forbidden as model input (taskbook Sec. 7.3)
FORBIDDEN_FEATURES = [
    "truth", "label_deploy", "confirmed_label", "provisional_label", "P_ref",
    "p_ref", "r_hat", "high_budget_gain", "probe_outcome", "V1_ref",
    "state_id", "config_id", "source_stage", "panel", "panel_name",
    "is_development", "is_confirmation", "rep", "seed",
]


def se_g(g_ci_low: float, g_ci_high: float) -> float:
    return (float(g_ci_high) - float(g_ci_low)) / (2 * Z95)


def feature_row(row: dict) -> dict:
    """Compute the online feature vector for one gradient trial.

    S1/SE_g/CI_width are defined only for valid-gradient trials (the frozen
    S1 semantics); invalid-gradient rows carry NaN for those fields and are
    deterministically mapped to ABSTAIN by every policy.
    """
    s1 = row.get("S1")
    if row.get("gradient_valid") and s1 is not None:
        se = se_g(row["g_ci_low"], row["g_ci_high"])
        ciw = float(row["g_ci_high"]) - float(row["g_ci_low"])
        s1v = float(s1)
    else:
        se = ciw = s1v = math.nan
    return {
        "S1": s1v,
        "g_hat": float(row["g_hat"]) if row.get("gradient_valid") else math.nan,
        "abs_g_hat": abs(float(row["g_hat"])) if row.get("gradient_valid") else math.nan,
        "SE_g": se,
        "CI_width": ciw,
        "s2": float(row["s2"]),
        "curvature_c": float(row["curvature_c"]),
        "ESS_grad": float(row["ESS_grad"]),
        "gradient_valid": 1.0 if row.get("gradient_valid") else 0.0,
    }


def build_feature_frame(rows: list[dict], features: list[str]) -> tuple[list[list[float]], list[int], list[dict]]:
    """X (valid-gradient rows only), y, and the kept rows.

    Invalid-gradient rows are never model input (taskbook Sec. 7.1 frozen
    semantics); in policy evaluation they map deterministically to ABSTAIN.
    """
    X, y, kept = [], [], []
    for r in rows:
        if not r["gradient_valid"]:
            continue
        fr = feature_row(r)
        X.append([fr[f] for f in features])
        y.append(int(r["label_deploy"]))
        kept.append(r)
    return X, y, kept


def leakage_audit(feature_names: list[str]) -> dict:
    hit = [f for f in feature_names if f in FORBIDDEN_FEATURES]
    return {"features": feature_names, "forbidden_hits": hit,
            "PASS": not hit}
