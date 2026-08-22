"""H3-3B -- Proposal-dependent variance geometry: synthetic pilot (Synthetic B).

Core question
-------------
Does changing the importance-sampling proposal ``q`` produce a *predictable*
change of the variance geometry ``nu_V^(q)``?

    (system, q) -> nu_V^(q),    q = N(m, Sigma)

Objects (H3-3B theory extension, read-only reuse of H3-2 / H3-3A)
-----------------------------------------------------------------
- variance density       rho_V(x) = 1_A(x) p(x)^2 / q(x),  p = phi = N(0, I)
- variance measure       nu_V^(q)(dx) = rho_V / int_A rho_V dx
- analytic core          Lambda = 2I - Sigma^{-1};
                         Sigma_V = Lambda^{-1},  mu_V = -Lambda^{-1} Sigma^{-1} m
                         (legitimate iff Lambda > 0  <=>  Sigma > 1/2 I)
- region geometry        C_eta = ||m_eta - x*||,  R_eta (spread),
                         G_eta = C_eta / (R_eta + eps)      (H3-3A estimator)
- IS performance         VRF, ESS, M2 estimate, estimator variance

Experiments
-----------
1. Proposal mean sweep:  Sigma = I;  m_lambda = (1-lambda) x* + lambda x_L,
   lambda in {-1, -0.5, 0, 0.5, 1, 1.5, 2}   (x*, x_L = frozen B/S2 anchors)
2. Proposal covariance sweep:  fixed m;  Sigma = s^2 I,
   s^2 in {0.6, 0.75, 1, 1.5, 2};  legitimacy Sigma > 1/2 I enforced
   (s^2 <= 0.5 would be recorded invalid, NOT run).

Scope: ONLY the H3-2 frozen Synthetic B curved case (B_synthetic_curvature_
beta_kappa).  No new real system, no failure-topology / physics change, no
H3-2 frozen artifact modified.

Frozen reuse (read-only)
------------------------
- run_h3_2_adaptive_geometry_is: label_curved, NOMINAL, N_SYNTH_MC / N_SYNTH
- tests/data/h3_2_leakage_point_dataset_v1.json: B/S2 x* and x_L anchors
- set estimator: H3-3A variance-mass weights (rho_V/r with r = sampling
  density), HDR prefix region.  Weights generalised to q = N(m, Sigma).

Research questions / gates
--------------------------
Q1  (m, Sigma) -> (mu_V, Sigma_V): analytic map reproduced by the region
    estimator (mu_V trajectory vs m_eta; Sigma_V scale vs R_eta).
Q2  C_eta / R_eta / G_eta respond systematically to proposal variation.
Q3  G_eta <-> VRF correlation / trend (report only, no causality claim).
Gate A  stable q -> nu_V map        (Q1 evidence)
Gate B  G_eta or R_eta varies systematically with proposal
Gate C  trends persist across eta in {0.5, 0.8, 0.9}

Outputs
-------
results/phase_h3/h3_3b_synthetic_pilot_v1.json
results/phase_h3/fig12_proposal_parameter_space.png
results/phase_h3/fig13_variance_geometry_trajectory.png
results/phase_h3/fig14_geometry_vs_vrf.png
docs/phase_h/H3_3B_synthetic_pilot_report.md

Usage
-----
    python scripts/run_h3_3b_synthetic_pilot.py
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.special import logsumexp

from hyptraj.uncertainty.variance_leakage import mc_estimator

# ---- frozen H3-2 pipeline reuse (read-only) ------------------------------
import run_h3_2_adaptive_geometry_is as frozen

label_curved = frozen.label_curved
NOMINAL = frozen.NOMINAL
N_MC = frozen.N_SYNTH_MC          # 50_000  (synthetic MC exploration)
N_IS = frozen.N_SYNTH             # 200_000 (synthetic IS pass)

REPO = Path(__file__).resolve().parents[1]
H3_2_DATASET = REPO / "tests" / "data" / "h3_2_leakage_point_dataset_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_synthetic_pilot_v1.json"
FIG_DIR = REPO / "results" / "phase_h3"

# ---- pilot configuration (task H3-3B) ------------------------------------
SEEDS = [1, 2120, 3, 4]           # same seed set as H3-3A
ETAS = [0.5, 0.8, 0.9]
ETA_MAIN = 0.8
LAMBDAS = [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
S2_GRID = [0.6, 0.75, 1.0, 1.5, 2.0]
DIM = 4
EPS = 1e-8

# gate tolerances (documented)
GATE_A_CORR = 0.90                # min Spearman for analytic-vs-estimated track
GATE_A_SIGMAV_CORR = 0.70         # min |corr| for Sigma_V-scale vs R_eta
GATE_B_MIN_RANGE = 0.20           # min absolute range of G_eta or R_eta
GATE_C_CORR = 0.80                # min cross-eta Spearman for trend persistence


# ---------------------------------------------------------------------------
# Frozen B/S2 anchors (read-only from the frozen dataset)
# ---------------------------------------------------------------------------
def _load_b_anchors() -> tuple[np.ndarray, np.ndarray]:
    data = json.loads(H3_2_DATASET.read_text(encoding="utf-8"))
    b = [e for e in data["experiments"]
         if e["experiment_id"] == "B_synthetic_curvature_beta_kappa"][0]
    s2 = [g for g in b["point_geometry"] if g["topology_label"] == "S2"][0]
    x_star = np.asarray(s2["probability_design_point"], dtype=float)
    x_L = np.asarray(s2["leakage_point"], dtype=float)
    return x_star, x_L


X_STAR_S2, X_L_S2 = _load_b_anchors()
FROZEN_B_S2_DL = float(np.linalg.norm(X_L_S2 - X_STAR_S2))


# ---------------------------------------------------------------------------
# Gaussian proposal helpers (q = N(m, Sigma); log-space, overflow safe)
# ---------------------------------------------------------------------------
def log_w_general(z: np.ndarray, m: np.ndarray, Sigma: np.ndarray) -> np.ndarray:
    """``log w(z) = log phi(z) - log q(z)``,  phi = N(0,I), q = N(m, Sigma).

    log w = -1/2||z||^2 + 1/2 (z-m)^T Sigma^{-1} (z-m) + 1/2 log|Sigma|
    (2pi constants cancel).  Reduces to the frozen H3-2/3A weight at Sigma=I.
    """
    z = np.asarray(z, dtype=float)
    m = np.asarray(m, dtype=float).reshape(1, -1)
    Sinv = np.linalg.inv(Sigma)
    sgn, logdet = np.linalg.slogdet(Sigma)
    dz = z - m
    quad = np.einsum("ni,nj,ij->n", dz, dz, Sinv)
    return -0.5 * np.sum(z * z, axis=1) + 0.5 * quad + 0.5 * logdet


def log_rho_v(z: np.ndarray, m: np.ndarray, Sigma: np.ndarray) -> np.ndarray:
    """``log rho_V(z) = log p(z)^2 - log q(z)`` (p^2 = phi^2, q = N(m,Sigma)).

    log rho_V = -||z||^2 + 1/2 (z-m)^T Sigma^{-1} (z-m)
                + 1/2 log|Sigma| - (d/2) log(2 pi)
    """
    z = np.asarray(z, dtype=float)
    m = np.asarray(m, dtype=float).reshape(1, -1)
    Sinv = np.linalg.inv(Sigma)
    sgn, logdet = np.linalg.slogdet(Sigma)
    dz = z - m
    quad = np.einsum("ni,nj,ij->n", dz, dz, Sinv)
    d = z.shape[1]
    return (-np.sum(z * z, axis=1) + 0.5 * quad + 0.5 * logdet
            - 0.5 * d * np.log(2.0 * np.pi))


def sample_antithetic_gauss(rng: np.random.Generator, m: np.ndarray,
                            Sigma: np.ndarray, n: int) -> np.ndarray:
    """Antithetic Gaussian sampler ``z = m +/- L r``, ``L = chol(Sigma)``.

    Mirrors the frozen ``_antithetic`` (unit Sigma) structure; reduces to
    ``mean +/- r`` when Sigma = I.  Pairs are anti-correlated (frozen rule).
    """
    m = np.asarray(m, dtype=float).reshape(1, -1)
    L = np.linalg.cholesky(Sigma)
    half = n // 2
    r = rng.standard_normal((half, m.size))
    rL = r @ L.T
    out = np.vstack([m + rL, m - rL])
    return out[:n]


def analytic_variance_geometry(m: np.ndarray, Sigma: np.ndarray) -> dict:
    """Sec. 4 closed form: Lambda = 2I - Sigma^{-1}; Sigma_V, mu_V.

    Returns ``valid=False`` when Lambda is not positive definite
    (Sigma not > 1/2 I); the object nu_V^(q) is then ill-defined.
    """
    Lambda = 2.0 * np.eye(DIM) - np.linalg.inv(Sigma)
    eig = np.linalg.eigvalsh(Lambda)
    valid = bool(float(eig.min()) > 0.0)
    out = {
        "valid": valid,
        "Lambda_min_eig": float(eig.min()),
        "Lambda": Lambda.tolist(),
    }
    if valid:
        Sinv = np.linalg.inv(Sigma)
        Sigma_V = np.linalg.inv(Lambda)
        mu_V = -Sigma_V @ Sinv @ m
        out["Sigma_V"] = Sigma_V.tolist()
        out["mu_V"] = [float(v) for v in mu_V]
        out["Sigma_V_trace"] = float(np.trace(Sigma_V))
        out["mu_V_norm"] = float(np.linalg.norm(mu_V))
    return out


# ---------------------------------------------------------------------------
# H3-3A set estimator, generalised to q = N(m, Sigma)
# ---------------------------------------------------------------------------
def variance_mass_weights(z: np.ndarray, source: np.ndarray,
                          m: np.ndarray, Sigma: np.ndarray) -> np.ndarray:
    """Normalised variance-mass weights ``omega_i^V ~ rho_V(z_i)/r(z_i)``.

    With ``w = phi/q`` (general Gaussian IS weight):
      - MC samples  (r = phi):  omega^V ~ rho_V/phi  = w
      - IS samples  (r = q):    omega^V ~ rho_V/q    = w^2
    (common constants cancel under normalisation; log-space logsumexp).
    """
    lw = log_w_general(z, m, Sigma)
    lwV = np.where(np.asarray(source) == "is", 2.0 * lw, lw)
    lwV -= logsumexp(lwV)
    wV = np.exp(lwV)
    if not np.all(np.isfinite(wV)):
        raise ValueError("degenerate variance-mass weights")
    return wV


def mode_region_geometry(z_mode: np.ndarray, source: np.ndarray,
                         m: np.ndarray, Sigma: np.ndarray,
                         eta_list: list[float]) -> dict | None:
    """Point + set-valued variance geometry for one topology mode.

    x* = argmin||z|| (probability design point, pooled set), x_L = argmax rho_V
    (leakage point, depends on the proposal).  HDR region = minimal prefix of
    rho_V-descending order accumulating >= eta of variance mass.
    """
    z_mode = np.asarray(z_mode, dtype=float)
    source = np.asarray(source)
    if z_mode.ndim != 2 or z_mode.shape[0] == 0:
        return None
    lrho = log_rho_v(z_mode, m, Sigma)
    wV = variance_mass_weights(z_mode, source, m, Sigma)

    x_star = z_mode[int(np.argmin(np.sum(z_mode ** 2, axis=1)))]
    x_L = z_mode[int(np.argmax(lrho))]
    d_L = float(np.linalg.norm(x_L - x_star))

    order = np.argsort(lrho)[::-1]
    cum = np.cumsum(wV[order])
    per_eta: dict = {}
    for eta in eta_list:
        k = int(np.searchsorted(cum, eta))
        reg = order[: k + 1]
        wv = wV[reg]
        m_eta = np.average(z_mode[reg], axis=0, weights=wv)
        R = float(np.sqrt(np.average(
            np.sum((z_mode[reg] - m_eta) ** 2, axis=1), weights=wv)))
        C = float(np.linalg.norm(m_eta - x_star))          # region center shift
        G = float(C / (R + EPS))                            # normalized mismatch
        D = float(np.min(np.linalg.norm(z_mode[reg] - x_star, axis=1)))
        S = float(D / (R + EPS))
        v1, v2 = m_eta - x_star, x_L - x_star
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        align = float(np.dot(v1, v2) / (n1 * n2)) if n1 > 0 and n2 > 0 else 0.0
        per_eta[f"eta_{eta}"] = {
            "D": D, "R": R, "S": S, "C": C, "G": G,
            "m_eta": [float(v) for v in m_eta],
            "c_eta": float(np.exp(lrho[reg[-1]])),
            "c_eta_ratio": float(np.exp(lrho[reg[-1]] - lrho.max())),
            "n_points": int(len(reg)),
            "mass": float(cum[k]),
            "align_xL": align,
        }
    return {
        "x_star": [float(v) for v in x_star],
        "x_L": [float(v) for v in x_L],
        "d_L": d_L,
        "rho_L_max": float(np.exp(lrho.max())),
        "n_pool": int(z_mode.shape[0]),
        "per_eta": per_eta,
    }


# ---------------------------------------------------------------------------
# IS performance (log-space; identical statistics to the frozen estimators)
# ---------------------------------------------------------------------------
def is_performance(z_q: np.ndarray, labels_q: np.ndarray,
                   m: np.ndarray, Sigma: np.ndarray,
                   p_mc: float, var_mc: float) -> dict:
    """Importance-sampling estimates for proposal q = N(m, Sigma).

    p = mean_q(w 1_A),  M2 = mean_q(w^2 1_A),  var = (M2 - p^2)/N,
    ESS = (sum w)^2 / sum w^2,  VRF = var_mc / var_is.
    """
    lw = log_w_general(z_q, m, Sigma)
    ind = np.asarray(labels_q != NOMINAL, dtype=float)
    n = z_q.shape[0]
    lp = logsumexp(lw, b=ind) - np.log(n)
    lm2 = logsumexp(2.0 * lw, b=ind) - np.log(n)
    p = float(np.exp(lp))
    m2 = float(np.exp(lm2))
    var = float(max(0.0, (m2 - p ** 2) / n))
    ess = float(np.exp(2.0 * logsumexp(lw) - logsumexp(2.0 * lw)))
    return {
        "p": p,
        "var": var,
        "m2_estimate": m2,
        "ess": ess,
        "vrf": float("inf") if var <= 0.0 else var_mc / var,
        "n_accepted": int(ind.sum()),
        "n_total": n,
        "p_mc": p_mc,
        "var_mc": var_mc,
    }


# ---------------------------------------------------------------------------
# Per-proposal evaluation
# ---------------------------------------------------------------------------
def eval_proposal(m: np.ndarray, Sigma: np.ndarray, z_mc: np.ndarray,
                  labels_mc: np.ndarray, p_mc: float, var_mc: float,
                  rng: np.random.Generator, seed: int) -> dict:
    """Evaluate one (m, Sigma): analytic core + IS performance + region geo."""
    analytic = analytic_variance_geometry(m, Sigma)
    if not analytic["valid"]:
        # legitimacy Sigma > 1/2 I violated: nu_V^(q) ill-defined, do NOT run
        return {"proposal": {"m": m.tolist(), "Sigma": Sigma.tolist(),
                             "legitimate": False},
                "analytic": analytic,
                "is_performance": None, "region": None,
                "invalid_reason": "Sigma not > 1/2 I (Lambda not PD)"}

    z_q = sample_antithetic_gauss(rng, m, Sigma, N_IS)
    labels_q = np.array([label_curved(u) for u in z_q])
    perf = is_performance(z_q, labels_q, m, Sigma, p_mc, var_mc)

    # pooled candidate pool per mode (MC explore + IS pass), H3-3A style
    region: dict = {}
    modes = sorted(set(labels_q.tolist()) - {NOMINAL})
    for topo in modes:
        mask_mc = labels_mc == topo
        mask_is = labels_q == topo
        if not (np.any(mask_mc) or np.any(mask_is)):
            continue
        z_mode = np.vstack([z_mc[mask_mc], z_q[mask_is]])
        source = np.concatenate([
            np.full(int(mask_mc.sum()), "mc"),
            np.full(int(mask_is.sum()), "is"),
        ])
        geo = mode_region_geometry(z_mode, source, m, Sigma, ETAS)
        if geo is not None:
            region[str(topo)] = geo

    return {
        "proposal": {"m": m.tolist(), "Sigma": Sigma.tolist(),
                     "legitimate": True},
        "analytic": analytic,
        "is_performance": perf,
        "region": region,
    }


# ---------------------------------------------------------------------------
# Aggregation / statistics helpers
# ---------------------------------------------------------------------------
def _mean_std(vals: list[float]) -> dict:
    a = np.asarray(vals, dtype=float)
    if a.size == 0:
        return {"mean": None, "std": None, "min": None, "max": None}
    return {"mean": float(a.mean()), "std": float(a.std(ddof=1)) if a.size > 1
            else 0.0, "min": float(a.min()), "max": float(a.max()),
            "range": float(a.max() - a.min())}


def _spearman(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation (ties handled by rank average)."""
    from scipy.stats import spearmanr
    if len(x) < 2 or len(set(x)) < 2 or len(set(y)) < 2:
        return float("nan")
    rho, _ = spearmanr(x, y)
    return float(rho)


def _pearson(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return float("nan")
    a, b = np.asarray(x, float), np.asarray(y, float)
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


# ---------------------------------------------------------------------------
# Research-question analysis
# ---------------------------------------------------------------------------
def _rows_of(per_seed: dict, sweep: str) -> list[tuple[float, dict]]:
    """All (config_value, per-seed record) pairs of one sweep."""
    rows = []
    for seed_rec in per_seed.values():
        for cfg_key, rec in seed_rec[sweep].items():
            if rec.get("is_performance") is not None:
                rows.append((float(cfg_key.split("_")[-1]), rec))
    return rows


def analyze_q1_q2_q3(per_seed: dict, mean_lam: list[float],
                     mean_s2: list[float]) -> dict:
    """Q1 analytic-vs-estimated geometry; Q2 descriptor sensitivity;
    Q3 G_eta <-> VRF correlation (trend only)."""

    def metric_list(rows, mode, key):
        return [rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"][key]
                for _, rec in rows if mode in rec.get("region", {})]

    def muV_list(rows):
        return [np.asarray(rec["analytic"]["mu_V"])
                for _, rec in rows if rec["analytic"].get("valid")]

    def mEta_list(rows):
        return [np.asarray(rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["m_eta"])
                for _, rec in rows if "S2" in rec.get("region", {})]

    def coord_spearman(a_list, b_list):
        """Per-coordinate Spearman between two list-of-vector sets, averaged."""
        if len(a_list) != len(b_list) or len(a_list) < 3:
            return float("nan")
        A = np.asarray(a_list); B = np.asarray(b_list)
        rhos = [_spearman(A[:, j].tolist(), B[:, j].tolist())
                for j in range(A.shape[1])]
        rhos = [r for r in rhos if not np.isnan(r)]
        return float(np.mean(rhos)) if rhos else float("nan")

    def signal_noise_ratio(rows, mode, key):
        """std of config-mean (signal) / mean of within-config std (noise)."""
        cfg_map: dict[float, list[float]] = {}
        for ckey, rec in rows:
            if mode not in rec.get("region", {}):
                continue
            v = rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"][key]
            cfg_map.setdefault(ckey, []).append(v)
        if len(cfg_map) < 2:
            return None
        sig = float(np.std([np.mean(v) for v in cfg_map.values()]))
        noise = float(np.mean([np.std(v) for v in cfg_map.values()]))
        return float(sig / max(noise, 1e-12)) if noise > 0 else None

    # ---- Q1: (m, Sigma) -> (mu_V, Sigma_V) -------------------------------
    q1: dict = {}
    for sweep, cfg_list in (("mean_sweep", mean_lam), ("cov_sweep", mean_s2)):
        rows = _rows_of(per_seed, sweep)
        muVs = muV_list(rows)
        mEtas = mEta_list(rows)
        corr_coord = coord_spearman(muVs, mEtas)
        R_est = metric_list(rows, "S2", "R")
        trV = [rec["analytic"]["Sigma_V_trace"]
               for _, rec in rows if rec["analytic"].get("valid")]
        corr_trV_R = _spearman(trV, R_est) if len(trV) == len(R_est) else float("nan")
        q1[sweep] = {
            "n_configs": len(rows),
            "spearman_coord_muV_vs_m_eta": corr_coord,
            "spearman_SigmaV_trace_vs_R_eta": corr_trV_R,
            "signal_noise_ratio_m_eta_x": signal_noise_ratio(rows, "S2", "C"),
            "m_eta_track": {
                "d_muV_mEta_mean": float(np.mean([
                    np.linalg.norm(a - b) for a, b in zip(muVs, mEtas)])) if muVs else None,
            },
        }
    # pool both sweeps for an overall (m,Sigma) -> nu_V tracking statement
    all_rows = (_rows_of(per_seed, "mean_sweep")
                + _rows_of(per_seed, "cov_sweep"))
    q1["pooled_n"] = len(all_rows)
    q1["pooled_spearman_coord_muV_vs_m_eta"] = coord_spearman(
        muV_list(all_rows), mEta_list(all_rows))
    q1["pooled_spearman_SigmaV_trace_vs_R_eta"] = _spearman(
        [rec["analytic"]["Sigma_V_trace"] for _, rec in all_rows
         if rec["analytic"].get("valid")],
        metric_list(all_rows, "S2", "R"))

    # ---- Q2: region descriptors vs proposal variation --------------------
    q2: dict = {}
    for sweep, cfg_list in (("mean_sweep", mean_lam), ("cov_sweep", mean_s2)):
        rows = _rows_of(per_seed, sweep)
        for mode in ("S1", "S2"):
            cfgs = [c for c, rec in rows if mode in rec.get("region", {})]
            R = metric_list(rows, mode, "R")
            G = metric_list(rows, mode, "G")
            C = metric_list(rows, mode, "C")
            q2.setdefault(sweep, {})[mode] = {
                "R": _mean_std(R), "G": _mean_std(G), "C": _mean_std(C),
                "spearman_R_vs_config": _spearman(cfgs, R),
                "spearman_G_vs_config": _spearman(cfgs, G),
                "spearman_C_vs_config": _spearman(cfgs, C),
            }
    return {"q1": q1, "q2": q2, "q3": analyze_q3(per_seed)}


def analyze_q3(per_seed: dict) -> dict:
    """Q3: G_eta <-> VRF and R_eta <-> VRF correlation (trend, not causal)."""
    rows = (_rows_of(per_seed, "mean_sweep")
            + _rows_of(per_seed, "cov_sweep"))
    G, R, C, VRF = [], [], [], []
    for _, rec in rows:
        region = rec.get("region", {})
        perf = rec.get("is_performance")
        if "S2" not in region or perf is None or not np.isfinite(perf["vrf"]):
            continue
        eg = region["S2"]["per_eta"][f"eta_{ETA_MAIN}"]
        G.append(eg["G"]); R.append(eg["R"]); C.append(eg["C"])
        VRF.append(perf["vrf"])
    return {
        "n_points": len(VRF),
        "pearson_G_vs_VRF": _pearson(G, VRF),
        "spearman_G_vs_VRF": _spearman(G, VRF),
        "pearson_R_vs_VRF": _pearson(R, VRF),
        "spearman_R_vs_VRF": _spearman(R, VRF),
        "pearson_C_vs_VRF": _pearson(C, VRF),
        "spearman_C_vs_VRF": _spearman(C, VRF),
    }


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
def eval_gates(per_seed: dict) -> dict:
    rows_ms = _rows_of(per_seed, "mean_sweep")
    rows_cs = _rows_of(per_seed, "cov_sweep")

    def coord_spearman(a_list, b_list):
        if len(a_list) != len(b_list) or len(a_list) < 3:
            return float("nan")
        A = np.asarray(a_list); B = np.asarray(b_list)
        rhos = [_spearman(A[:, j].tolist(), B[:, j].tolist())
                for j in range(A.shape[1])]
        rhos = [r for r in rhos if not np.isnan(r)]
        return float(np.mean(rhos)) if rhos else float("nan")

    # ---- Gate A: stable q -> nu_V map (Q1 evidence) -----------------------
    # mean sweep: mu_V = -m (Sigma = I); the region centroid m_eta should
    # track mu_V coordinate-wise despite truncation (A shifts both, but the
    # *movement* is deterministic).  cov sweep: tr(Sigma_V) vs R_eta.
    muVs_ms = [np.asarray(rec["analytic"]["mu_V"])
               for _, rec in rows_ms if rec["analytic"].get("valid")]
    mEta_ms = [np.asarray(rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["m_eta"])
               for _, rec in rows_ms if "S2" in rec.get("region", {})]
    corr_a1 = coord_spearman(muVs_ms, mEta_ms)
    trV_cs = [rec["analytic"]["Sigma_V_trace"]
              for _, rec in rows_cs if rec["analytic"].get("valid")]
    R_cs = [rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["R"]
            for _, rec in rows_cs if "S2" in rec.get("region", {})]
    corr_a2 = _spearman(trV_cs, R_cs) if len(trV_cs) == len(R_cs) else float("nan")
    gate_a = {
        "pass": bool((corr_a1 >= GATE_A_CORR or np.isnan(corr_a1)) and
                     abs(corr_a2) >= GATE_A_SIGMAV_CORR),
        "evidence": {
            "spearman_coord_muV_vs_m_eta(mean_sweep)": corr_a1,
            "spearman_SigmaV_trace_vs_R_eta(cov_sweep)": corr_a2,
            "muV_mEta_mean_distance(mean_sweep)": (
                float(np.mean([np.linalg.norm(a - b)
                               for a, b in zip(muVs_ms, mEta_ms)]))
                if muVs_ms else None),
            "R_eta_range(cov_sweep)": _mean_std(R_cs).get("range"),
        },
    }

    # ---- Gate B: G_eta or R_eta varies systematically ----------------------
    R_ms = [rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["R"]
            for _, rec in rows_ms if "S2" in rec.get("region", {})]
    G_ms = [rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["G"]
            for _, rec in rows_ms if "S2" in rec.get("region", {})]
    R_cs = [rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["R"]
            for _, rec in rows_cs if "S2" in rec.get("region", {})]
    G_cs = [rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]["G"]
            for _, rec in rows_cs if "S2" in rec.get("region", {})]
    ranges = {
        "R_eta_range(mean_sweep)": _mean_std(R_ms).get("range"),
        "G_eta_range(mean_sweep)": _mean_std(G_ms).get("range"),
        "R_eta_range(cov_sweep)": _mean_std(R_cs).get("range"),
        "G_eta_range(cov_sweep)": _mean_std(G_cs).get("range"),
    }
    gate_b = {
        "pass": bool(max(v for v in ranges.values() if v is not None)
                     >= GATE_B_MIN_RANGE),
        "evidence": ranges,
    }

    # ---- Gate C: trends persist across eta in {0.5, 0.8, 0.9} -------------
    def cross_eta_corrs(rows, metric):
        out = {}
        for e1, e2 in ((0.5, 0.8), (0.8, 0.9), (0.5, 0.9)):
            v1 = [rec["region"]["S2"]["per_eta"][f"eta_{e1}"][metric]
                  for _, rec in rows if "S2" in rec.get("region", {})]
            v2 = [rec["region"]["S2"]["per_eta"][f"eta_{e2}"][metric]
                  for _, rec in rows if "S2" in rec.get("region", {})]
            out[f"{e1}_vs_{e2}"] = _spearman(v1, v2)
        return out

    all_rows = rows_ms + rows_cs
    cross = {m: cross_eta_corrs(all_rows, m) for m in ("C", "R", "G")}
    vals = [v for m in cross.values() for v in m.values()
            if v is not None and not np.isnan(v)]
    gate_c = {
        "pass": bool(vals and min(vals) >= GATE_C_CORR),
        "evidence": {"cross_eta_spearman": cross,
                     "min_cross_eta_spearman": min(vals) if vals else None},
    }
    return {"gate_a": gate_a, "gate_b": gate_b, "gate_c": gate_c}


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------
def build_dataset(per_seed: dict, analysis: dict, gates: dict,
                  wall_s: float) -> dict:
    return {
        "schema_version": "h3-3b-synthetic-pilot-v1",
        "status": "GENERATED",
        "stage": "H3-3B",
        "date": "2026-08-21",
        "scope": "Synthetic B curved case only (frozen H3-2, read-only)",
        "frozen_reuse": {
            "h3_2_dataset": "tests/data/h3_2_leakage_point_dataset_v1.json",
            "label_function": "run_h3_2_adaptive_geometry_is.label_curved",
            "seed_scheme": "fixed seeds {1, 2120, 3, 4}",
            "sample_sizes": {"mc": N_MC, "is": N_IS},
        },
        "config": {
            "etas": ETAS,
            "eta_main": ETA_MAIN,
            "lambdas": LAMBDAS,
            "s2_grid": S2_GRID,
            "legitimacy_rule": "Sigma > 1/2 I (Lambda = 2I - Sigma^-1 > 0); "
                               "s^2 <= 0.5 recorded invalid, not run",
            "eps": EPS,
            "gate_tolerances": {"GATE_A_CORR": GATE_A_CORR,
                                "GATE_A_SIGMAV_CORR": GATE_A_SIGMAV_CORR,
                                "GATE_B_MIN_RANGE": GATE_B_MIN_RANGE,
                                "GATE_C_CORR": GATE_C_CORR},
        },
        "anchors": {
            "x_star_S2": [float(v) for v in X_STAR_S2],
            "x_L_S2": [float(v) for v in X_L_S2],
            "frozen_dL_S2": FROZEN_B_S2_DL,
        },
        "per_seed": per_seed,
        "analysis": analysis,
        "gates": gates,
        "total_wall_seconds": round(wall_s, 1),
    }


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def make_figures(per_seed: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    # pooled rows across seeds for stable figures
    rows_ms = _rows_of(per_seed, "mean_sweep")
    rows_cs = _rows_of(per_seed, "cov_sweep")

    def m_of(rec):
        return np.asarray(rec["proposal"]["m"])

    def muV_of(rec):
        return np.asarray(rec["analytic"]["mu_V"]) if rec["analytic"]["valid"] \
            else np.zeros(2)

    # ---- Fig 1: proposal parameter space ---------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    ax = axes[0]
    ms = [m_of(rec) for _, rec in rows_ms]
    lam = [c for c, _ in rows_ms]
    for (mi, li) in zip(ms, lam):
        ax.plot(mi[0], mi[1], "o", ms=7)
        ax.annotate(f"$\\lambda$={li:+.1f}", (mi[0], mi[1]),
                    textcoords="offset points", xytext=(6, 5), fontsize=7)
    if ms:
        ax.plot([m[0] for m in ms], [m[1] for m in ms], "-", color="0.5",
                lw=0.8, alpha=0.6, label="m_λ trajectory")
    ax.plot(X_STAR_S2[0], X_STAR_S2[1], "*", color="k", ms=15,
            label=r"$x^*$ (S2 MPP)")
    ax.plot(X_L_S2[0], X_L_S2[1], "P", color="crimson", ms=13,
            label=r"$x_L$ (S2 leakage)")
    ax.set_title("Fig 1a — mean sweep:  $m_\\lambda=(1-\\lambda)x^*+\\lambda x_L$, "
                 "$\\Sigma=I$", fontsize=10)
    ax.set_xlabel("$z_1$"); ax.set_ylabel("$z_2$")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
    ax.set_xlim(-3.5, 4.0); ax.set_ylim(-2.0, 3.5)

    ax = axes[1]
    ms = [m_of(rec) for _, rec in rows_cs]
    for (mi, s2) in zip(ms, [c for c, _ in rows_cs]):
        ax.plot(mi[0], mi[1], "s", ms=8, color="#1f77b4")
        e = Ellipse((mi[0], mi[1]), 2 * np.sqrt(s2), 2 * np.sqrt(s2),
                    fill=False, edgecolor="#1f77b4", alpha=0.55,
                    linestyle="--")
        ax.add_patch(e)
        ax.annotate(f"$s^2$={s2:g}", (mi[0] + 0.12, mi[1] + 0.12),
                    fontsize=7, color="#1f77b4")
    ax.plot(X_STAR_S2[0], X_STAR_S2[1], "*", color="k", ms=15,
            label=r"$x^*$ (S2 MPP)")
    ax.plot(X_L_S2[0], X_L_S2[1], "P", color="crimson", ms=13,
            label=r"$x_L$ (S2 leakage)")
    ax.set_title("Fig 1b — covariance sweep:  fixed $m=x^*$,  "
                 "$\\Sigma=s^2 I$ (dashed = 1$\\sigma$)", fontsize=10)
    ax.set_xlabel("$z_1$"); ax.set_ylabel("$z_2$")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
    ax.set_xlim(-1.5, 4.0); ax.set_ylim(-1.5, 3.0)
    fig.tight_layout()
    f1 = FIG_DIR / "fig12_proposal_parameter_space.png"
    fig.savefig(f1, dpi=160); plt.close(fig); files.append(str(f1.relative_to(REPO)))

    # ---- Fig 2: variance geometry trajectory ------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    for ax, (rows, title, tag) in zip(
            axes,
            [(rows_ms, "mean sweep ($\\Sigma=I$)", "a"),
             (rows_cs, "covariance sweep ($m=x^*$)", "b")]):
        for _, rec in rows:
            if "S2" not in rec.get("region", {}):
                continue
            muV = muV_of(rec)
            eg = rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]
            m_eta = np.asarray(eg["m_eta"])
            ax.plot(muV[0], muV[1], "x", color="#1f77b4", ms=9)
            ax.plot(m_eta[0], m_eta[1], "o", color="#ff7f0e", ms=7)
            th = np.linspace(0, 2 * np.pi, 80)
            ax.plot(m_eta[0] + eg["R"] * np.cos(th),
                    m_eta[1] + eg["R"] * np.sin(th),
                    color="#ff7f0e", ls=":", lw=1.0, alpha=0.6)
        # connect trajectory in config order
        mus = np.array([muV_of(rec) for _, rec in rows
                        if rec["analytic"]["valid"]])
        mes = np.array([np.asarray(rec["region"]["S2"]["per_eta"]
                       [f"eta_{ETA_MAIN}"]["m_eta"])
                       for _, rec in rows if "S2" in rec.get("region", {})])
        if len(mus):
            ax.plot(mus[:, 0], mus[:, 1], "--", color="#1f77b4", lw=1.4,
                    alpha=0.8, label="$\\mu_V$ trajectory")
        if len(mes):
            ax.plot(mes[:, 0], mes[:, 1], "-", color="#ff7f0e", lw=1.4,
                    alpha=0.9, label=r"$m_\eta$ (region centroid)")
        ax.plot(X_STAR_S2[0], X_STAR_S2[1], "*", color="k", ms=15,
                label=r"$x^*$")
        ax.plot(X_L_S2[0], X_L_S2[1], "P", color="crimson", ms=13,
                label=r"$x_L$")
        ax.set_title(f"Fig 2{tag} — variance geometry trajectory ({title})",
                     fontsize=10)
        ax.set_xlabel("$z_1$"); ax.set_ylabel("$z_2$")
        ax.legend(fontsize=7, loc="best"); ax.grid(True, alpha=0.3)
    fig.tight_layout()
    f2 = FIG_DIR / "fig13_variance_geometry_trajectory.png"
    fig.savefig(f2, dpi=160); plt.close(fig); files.append(str(f2.relative_to(REPO)))

    # ---- Fig 3: geometry metrics vs VRF -----------------------------------
    rows_all = rows_ms + rows_cs
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8))
    G_ms_all, R_ms_all, C_ms_all, VRF_ms = [], [], [], []
    G_cs_all, R_cs_all, C_cs_all, VRF_cs = [], [], [], []
    tag_ms, tag_cs = [], []
    for r_, rec in rows_ms:
        if "S2" not in rec.get("region", {}) or rec.get("is_performance") is None:
            continue
        eg = rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]
        G_ms_all.append(eg["G"]); R_ms_all.append(eg["R"]); C_ms_all.append(eg["C"])
        VRF_ms.append(rec["is_performance"]["vrf"]); tag_ms.append(r_)
    for r_, rec in rows_cs:
        if "S2" not in rec.get("region", {}) or rec.get("is_performance") is None:
            continue
        eg = rec["region"]["S2"]["per_eta"][f"eta_{ETA_MAIN}"]
        G_cs_all.append(eg["G"]); R_cs_all.append(eg["R"]); C_cs_all.append(eg["C"])
        VRF_cs.append(rec["is_performance"]["vrf"]); tag_cs.append(r_)
    for ax, (vals_ms, vals_cs, name) in zip(
            axes,
            ((C_ms_all, C_cs_all, "$C_\\eta$"),
             (R_ms_all, R_cs_all, "$R_\\eta$"),
             (G_ms_all, G_cs_all, "$G_\\eta$"))):
        ax.scatter(VRF_ms, vals_ms, s=46, marker="o", color="#1f77b4",
                   alpha=0.85, label="mean sweep" if name == "$C_\\eta$" else None)
        ax.scatter(VRF_cs, vals_cs, s=52, marker="^", color="#d62728",
                   alpha=0.85, label="cov sweep" if name == "$C_\\eta$" else None)
        for vrf, v, t in zip(VRF_ms, vals_ms, tag_ms):
            ax.annotate(f"{t:g}", (vrf, v), textcoords="offset points",
                        xytext=(4, 4), fontsize=6, alpha=0.7, color="#1f77b4")
        for vrf, v, t in zip(VRF_cs, vals_cs, tag_cs):
            ax.annotate(f"$s^2$={t:g}", (vrf, v), textcoords="offset points",
                        xytext=(4, 4), fontsize=6, alpha=0.7, color="#d62728")
        all_x = VRF_ms + VRF_cs; all_y = vals_ms + vals_cs
        rho = _spearman(all_x, all_y)
        pr = _pearson(all_x, all_y)
        ax.set_xscale("log")
        ax.set_xlabel("VRF (log scale)")
        ax.set_ylabel(name)
        rho_cs = _spearman(VRF_cs, vals_cs) if len(VRF_cs) > 2 else float("nan")
        ax.set_title(f"{name} vs VRF  (pooled: Spearman={rho:.2f}, "
                     f"Pearson={pr:.2f})\n"
                     f"cov-sweep-only Spearman={rho_cs:.2f}",
                     fontsize=9)
        ax.grid(True, alpha=0.3)
        if name == "$C_\\eta$":
            ax.legend(fontsize=8, loc="best")
    fig.suptitle("Fig 3 — geometry descriptors vs IS performance "
                 "(trend only, no causality claim)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    f3 = FIG_DIR / "fig14_geometry_vs_vrf.png"
    fig.savefig(f3, dpi=160); plt.close(fig); files.append(str(f3.relative_to(REPO)))
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="H3-3B synthetic pilot")
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS)
    args = parser.parse_args()
    t0 = time.perf_counter()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    per_seed: dict = {}
    for seed in args.seeds:
        rng = np.random.default_rng(seed)
        # frozen MC exploration (proposal-independent; shared by all configs)
        z_mc = rng.standard_normal((N_MC, DIM))
        labels_mc = np.array([label_curved(u) for u in z_mc])
        p_mc, var_mc = mc_estimator(labels_mc != NOMINAL)

        mean_sweep: dict = {}
        for lam in LAMBDAS:
            m = (1.0 - lam) * X_STAR_S2 + lam * X_L_S2
            Sigma = np.eye(DIM)
            mean_sweep[f"lambda_{lam:+.1f}"] = eval_proposal(
                m, Sigma, z_mc, labels_mc, p_mc, var_mc, rng, seed)
        cov_sweep: dict = {}
        for s2 in S2_GRID:
            m = X_STAR_S2.copy()          # fixed mean = x* (probability design pt)
            Sigma = s2 * np.eye(DIM)
            cov_sweep[f"s2_{s2:g}"] = eval_proposal(
                m, Sigma, z_mc, labels_mc, p_mc, var_mc, rng, seed)
        per_seed[f"seed_{seed}"] = {
            "p_mc": p_mc, "var_mc": var_mc,
            "mean_sweep": mean_sweep, "cov_sweep": cov_sweep,
        }
        line = " | ".join(
            f"{c}:VRF={rec['is_performance']['vrf']:.2f}" if rec.get(
                "is_performance") else f"{c}:invalid"
            for c, rec in mean_sweep.items())
        print(f"[seed {seed}] p_mc={p_mc:.4f}  {line}", flush=True)

    analysis = analyze_q1_q2_q3(per_seed, LAMBDAS, S2_GRID)
    gates = eval_gates(per_seed)
    dataset = build_dataset(per_seed, analysis, gates, time.perf_counter() - t0)
    OUT_JSON.write_text(
        json.dumps(dataset, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fig_files = make_figures(per_seed)

    print("\n=== ANALYSIS ===")
    print(json.dumps(analysis, indent=1, ensure_ascii=False))
    print("\n=== GATES ===")
    print(json.dumps(gates, indent=1, ensure_ascii=False))
    print(f"\nfigures: {fig_files}")
    print(f"total wall time: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
