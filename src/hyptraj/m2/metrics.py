"""M2 -- geometry/leakage diagnostics, paired statistics and the
machine-readable record schema (task Sec. 25-29, 38-39, 45).

All functions here are OFFLINE analysis utilities; none feeds an online
policy decision (M1-D firewall inherited).  VRF attachment stays in the
DRIVER (reference denominators are benchmark-design data).
"""

from __future__ import annotations

import numpy as np

from hyptraj.m2.variance_covariance import symmetrize_matrix

MISSING = ("S2", "S3", "S4")
NOMINAL = "S0"
SCHEMA_VERSION = "raretopo-m2-v0"
H3_TAG = "RareTopo-H3-v1.0"
M1_TAG = "RareTopo-M1-v0"
M1D_TAG = "RareTopo-M1-D-v1.0"


# ---------------------------------------------------------------------------
# shape diagnostics (task Sec. 27)
# ---------------------------------------------------------------------------
def anisotropy_ratio(cov: np.ndarray, eps: float = 1e-12) -> float:
    """``A_C = lambda_max / (lambda_min + eps)`` (Sec. 27.2)."""
    cov = symmetrize_matrix(np.asarray(cov, dtype=float))
    eig = np.linalg.eigvalsh(cov)
    return float(eig[-1] / (eig[0] + eps))


def principal_alignment(cov_a: np.ndarray, cov_b: np.ndarray) -> float:
    """|cos| between top eigenvectors of two SPD matrices (Sec. 27.3)."""
    _, va = np.linalg.eigh(symmetrize_matrix(np.asarray(cov_a, dtype=float)))
    _, vb = np.linalg.eigh(symmetrize_matrix(np.asarray(cov_b, dtype=float)))
    c = float(abs(np.dot(va[:, -1], vb[:, -1])))
    return float(min(1.0, max(0.0, c)))


def covariance_change_frobenius(sigma_new: np.ndarray,
                                sigma_base: np.ndarray) -> float:
    """``|| Sigma_new - Sigma_base ||_F`` (Sec. 27.4)."""
    return float(np.linalg.norm(np.asarray(sigma_new, dtype=float)
                                - np.asarray(sigma_base, dtype=float)))


def mahalanobis_mismatch(z: np.ndarray, region_indices: np.ndarray,
                         centroid: np.ndarray, weights_region: np.ndarray,
                         sigma: np.ndarray) -> float:
    """Variance-mass weighted ``D_eta,k(Sigma)`` diagnostic (task Sec. 28).

    Expected squared Mahalanobis distance of the region samples under
    ``sigma``, weighted by the IN-REGION normalized variance masses.
    Diagnostic ONLY -- never a success gate.
    """
    sigma = symmetrize_matrix(np.asarray(sigma, dtype=float))
    try:
        inv = np.linalg.inv(sigma)
    except np.linalg.LinAlgError:
        return float("nan")
    X = np.asarray(z, dtype=float)[region_indices] - centroid
    w = np.asarray(weights_region, dtype=float)
    sw = float(w.sum())
    if sw <= 0.0:
        return float("nan")
    quad = np.einsum("ni,ij,nj->n", X, inv, X)
    val = float(np.sum(w * quad) / sw)
    return val if np.isfinite(val) else float("nan")


# ---------------------------------------------------------------------------
# leakage redistribution (task Sec. 26)
# ---------------------------------------------------------------------------
def leakage_ratios(L_table_new: dict, L_table_c0: dict,
                   selected_mode: str | None) -> dict:
    """Per-mode ratios ``R_L_j = L_j(new)/L_j(C0)`` plus headline blocks.

    ``L_table_*``: {mode_id: L_hat} from the frozen evaluator (event modes
    observed at final evaluation).  Modes absent from a table are treated as
    zero leakage on that side and handled explicitly rather than silently.
    """
    modes = sorted(set(L_table_new) | set(L_table_c0))
    ratios: dict[str, float] = {}
    for mid in modes:
        l_new = float(L_table_new.get(mid, 0.0))
        l_c0 = float(L_table_c0.get(mid, 0.0))
        if l_c0 <= 0.0:
            ratios[mid] = float("inf") if l_new > 0.0 else float("nan")
        else:
            ratios[mid] = float(l_new / l_c0)

    off = [m for m in modes if m != selected_mode]
    out = {
        "R_L_table": ratios,
        "selected_mode_leakage_ratio": (
            ratios.get(str(selected_mode), float("nan"))
            if selected_mode is not None else float("nan")),
        "max_off_target_leakage_ratio": (
            max((ratios[m] for m in off), default=float("nan"))),
        "sum_off_target_leakage": float(
            sum(L_table_new.get(m, 0.0) for m in off)),
        "L_table_new": {m: float(L_table_new.get(m, 0.0)) for m in modes},
        "L_table_C0": {m: float(L_table_c0.get(m, 0.0)) for m in modes},
    }
    finite_off = [ratios[m] for m in off if np.isfinite(ratios[m])]
    if len(finite_off) < len(off):
        # inf entries mean C0 had zero off-target leakage while new method
        # does not -- that IS catastrophic redistribution by definition
        if any(ratios[m] == float("inf") for m in off):
            out["max_off_target_leakage_ratio"] = float("inf")
        elif not finite_off:
            out["max_off_target_leakage_ratio"] = float(
                max((0.0,), default=0.0))
    return out


def ess_band(ess_v: float, low: float = 20.0, high: float = 200.0) -> str:
    """Ablation M2-F stratification bands (low / medium / high ESS_V)."""
    if not np.isfinite(ess_v):
        return "invalid"
    if ess_v < low:
        return "low"
    if ess_v < high:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# probability consistency statistics (task Sec. 29)
# ---------------------------------------------------------------------------
def probability_consistency(p_hats: np.ndarray, var_hats: np.ndarray,
                            p_ref: float) -> dict:
    """Per-(config, method) consistency stats of ``P_hat`` vs frozen ref.

    Declared statistic: standardized deviations
    ``t_i = (P_hat_i - p_ref) / sqrt(var_hat_i)`` over seeds, plus their
    median.  Gate usage (median |t| <= 4 AND fewer than 7/8 same-sign
    exceedances of |t|>2) lives in the gate audit script; this function only
    produces the numbers.
    """
    p_hats = np.asarray(p_hats, dtype=float)
    var_hats = np.maximum(np.asarray(var_hats, dtype=float), 1e-300)
    t = (p_hats - float(p_ref)) / np.sqrt(var_hats)
    return {
        "t_values": [float(v) for v in t],
        "median_abs_t": float(np.median(np.abs(t))) if t.size else None,
        "frac_same_sign_gt2": _same_sign_frac(t),
    }


def _same_sign_frac(t: np.ndarray, level: float = 2.0) -> float:
    big = t[np.abs(t) > level]
    if big.size == 0:
        return 0.0
    pos = int(np.sum(big > 0))
    neg = big.size - pos
    return float(max(pos, neg) / t.size)


# ---------------------------------------------------------------------------
# paired hierarchical statistics (task Sec. 38-39)
# ---------------------------------------------------------------------------
def paired_log_deltas(a_vals: dict[tuple, float],
                      b_vals: dict[tuple, float]) -> tuple[dict, list]:
    """log M2(a) - log M2(b) per shared (config, seed) key + summary."""
    keys = sorted(set(a_vals) & set(b_vals))
    deltas = []
    for k in keys:
        va, vb = a_vals[k], b_vals[k]
        if va > 0 and vb > 0:
            deltas.append(float(np.log(va) - np.log(vb)))
        else:
            deltas.append(float("nan"))
    arr = np.asarray(deltas, dtype=float)
    summary = {
        "n_pairs": int(arr.size),
        "n_valid": int(np.sum(np.isfinite(arr))),
        "median_delta_logM2": float(np.nanmedian(arr)) if arr.size else None,
        "mean_delta_logM2": float(np.nanmean(arr)) if arr.size else None,
        "std_delta_logM2": float(np.nanstd(arr, ddof=1))
        if np.isfinite(arr).sum() > 1 else None,
    }
    boots = None
    fin = arr[np.isfinite(arr)]
    if fin.size >= 2:
        rng = np.random.default_rng(20260827)
        idx = rng.integers(0, fin.size, size=(2000, fin.size))
        med = np.median(fin[idx], axis=1)
        lo, hi = np.quantile(med, [0.025, 0.975])
        boots = {"bootstrap_median_ci95_logM2": [float(lo), float(hi)]}
    summary.update(boots or {})
    return summary, keys


def win_counts(a_vals: dict[tuple, float], b_vals: dict[tuple, float]) -> dict:
    """Win counts of ``a`` vs ``b`` keyed by (config, seed); plus splits."""
    keys = sorted(set(a_vals) & set(b_vals))
    seed_wins = sum(1 for k in keys if a_vals[k] < b_vals[k])
    cfg_map: dict[str, list[int]] = {}
    for k in keys:
        cfg_map.setdefault(str(k[0]), []).append(int(a_vals[k] < b_vals[k]))
    cfg_wins = {c: int(np.median(v) == 1) for c, v in cfg_map.items()}
    return {
        "seed_level_wins": int(seed_wins),
        "seed_level_total": len(keys),
        "config_median_wins": cfg_wins,
        "config_median_win_count": int(sum(cfg_wins.values())),
    }


# ---------------------------------------------------------------------------
# machine-readable trial record (task Sec. 45)
# ---------------------------------------------------------------------------
def build_trial_record(*, benchmark_hash: str, config_id: str, seed: int,
                       layer: str, covariance_method: str,
                       selected_mode: str | None, eta: float,
                       pilot_n: int, alpha_p: float,
                       region: dict | None, covariance_block: dict,
                       evaluation: dict, extra_simulator_calls: int = 0,
                       validity: dict | None = None,
                       project_tags: dict | None = None) -> dict:
    """Assemble one raretopo-m2-v0 record (exact Sec. 45 key set)."""
    rec = {
        "schema_version": SCHEMA_VERSION,
        "h3_tag": H3_TAG,
        "m1_tag": M1_TAG,
        "m1d_tag": M1D_TAG,
        "benchmark_hash": benchmark_hash,
        "config_id": config_id,
        "seed": int(seed),
        "layer": layer,
        "covariance_method": covariance_method,
        "selected_mode": selected_mode,
        "eta": float(eta),
        "pilot": {"n": int(pilot_n), "alpha_p": float(alpha_p)},
        "variance_region": region or {},
        "covariance": covariance_block,
        "evaluation": evaluation,
        "cost": {"extra_simulator_calls_covariance":
                 int(extra_simulator_calls)},
        "validity": validity or {},
    }
    if project_tags:
        rec["project_tags"] = project_tags
    return rec


REQUIRED_SCHEMA_KEYS = ("schema_version", "h3_tag", "m1_tag", "m1d_tag",
                        "benchmark_hash", "config_id", "seed", "layer",
                        "covariance_method", "selected_mode", "eta", "pilot",
                        "variance_region", "covariance", "evaluation", "cost",
                        "validity")

__all__ = [
    "anisotropy_ratio", "principal_alignment", "covariance_change_frobenius",
    "mahalanobis_mismatch", "leakage_ratios", "ess_band",
    "probability_consistency", "paired_log_deltas", "win_counts",
    "build_trial_record", "REQUIRED_SCHEMA_KEYS",
    "SCHEMA_VERSION", "H3_TAG", "M1_TAG", "M1D_TAG", "MISSING", "NOMINAL",
]
