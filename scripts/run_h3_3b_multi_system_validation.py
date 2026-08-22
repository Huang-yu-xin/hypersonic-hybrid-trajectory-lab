"""H3-3B -- Multi-system validation of proposal-dependent variance geometry.

Stage-2 validation: is the ``(system, q) -> nu_V^(q)`` map discovered in the
Synthetic-B pilot (rho(mu_V, m_eta)=0.99, rho(tr Sigma_V, R_eta)=0.98) valid
across systems, or is it a Synthetic-B artifact?

Systems (frozen H3-2 / H3-3A, read-only)
-----------------------------------------
A  A_synthetic_multi_mode_recovery   synthetic linear  (aligned; x* == x_L)
B  B_synthetic_curvature_beta_kappa   synthetic curved  (mismatch; d_L=0.775)
C1 C1_sanger_b1n1_wide                real Sanger B1N1 (aligned after audit)
C2 C2_sanger_b2n_wide                 real Sanger B2N  (aligned after audit)

Unified proposal protocol (per system)
--------------------------------------
Exp 1 (mean sweep):  Sigma = I;  m_lambda = (1-lambda) x* + lambda x_L,
  lambda in {-1, -0.5, 0, 0.5, 1, 1.5, 2}
  NOTE aligned systems (A, C1, C2) have x* == x_L: the mean lever is
  degenerate by construction -- recorded, shared IS batch, not hidden.
Exp 2 (cov sweep):   m = x*;  Sigma = s^2 I,  s^2 in {0.75, 1, 1.5, 2}
  (legitimacy Sigma > 1/2 I enforced; s^2 <= 0.5 recorded invalid, NOT run)

Metrics (per config): proposal (m, Sigma); analytic (Lambda, Sigma_V, mu_V);
  region (C_eta, R_eta, G_eta, D_eta; eta in {0.5, 0.8, 0.9}, main 0.8);
  IS performance (VRF, ESS, M2, variance).

Validation gates
----------------
Gate A  per system: rho(mu_V, m_eta) > 0.8 OR rho(tr Sigma_V, R_eta) > 0.8
  (at least one lever; mean lever N/A when degenerate-aligned)
Gate B  descriptors respond to proposal change across systems
Gate C  trend direction consistent from Synthetic -> Real

Outputs
-------
results/phase_h3/h3_3b_multi_system_validation_v1.json
results/phase_h3/fig15_multi_system_geometry.png
results/phase_h3/fig16_region_descriptor_stability.png
results/phase_h3/fig17_geometry_vs_vrf_multisystem.png
docs/phase_h/H3_3B_multi_system_validation_report.md

Usage
-----
    python scripts/run_h3_3b_multi_system_validation.py --only synthetic
    python scripts/run_h3_3b_multi_system_validation.py --only real
    python scripts/run_h3_3b_multi_system_validation.py            # both
"""

from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.uncertainty.topology_margin import (
    DEFAULT_MAX_TIME,
    S_A,
    run_exact_topology,
)
from hyptraj.uncertainty.variance_leakage import mc_estimator

# ---- frozen H3-2 pipeline reuse (read-only) ------------------------------
import run_h3_2_adaptive_geometry_is as frozen
import run_h3_3b_synthetic_pilot as pilot   # validated numeric core

label_linear = frozen.label_linear
label_curved = frozen.label_curved
NOMINAL = frozen.NOMINAL
SOLVER = frozen.SOLVER
N_SYNTH_MC = frozen.N_SYNTH_MC          # 50_000  (synthetic MC explore)
N_SYNTH_IS = frozen.N_SYNTH             # 200_000 (synthetic IS pass)

# validated core functions (identical to the Synthetic-B pilot)
log_w_general = pilot.log_w_general
log_rho_v = pilot.log_rho_v
sample_antithetic_gauss = pilot.sample_antithetic_gauss
analytic_variance_geometry = pilot.analytic_variance_geometry
variance_mass_weights = pilot.variance_mass_weights
mode_region_geometry = pilot.mode_region_geometry
is_performance = pilot.is_performance
_spearman = pilot._spearman
_pearson = pilot._pearson
_mean_std = pilot._mean_std

REPO = Path(__file__).resolve().parents[1]
H3_2_DATASET = REPO / "tests" / "data" / "h3_2_leakage_point_dataset_v1.json"
MLB1_PATH = REPO / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_multi_system_validation_v1.json"
FIG_DIR = REPO / "results" / "phase_h3"

# ---- configuration ---------------------------------------------------------
SEEDS = [1, 2120, 3, 4]
ETAS = [0.5, 0.8, 0.9]
ETA_MAIN = 0.8
LAMBDAS = [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
S2_GRID = [0.75, 1.0, 1.5, 2.0]         # task: do not over-expand the search
DIM = 4
EPS = 1e-8
WORKERS = 4                             # real dynamics rule (frozen)

# real sample sizes (small-scale validation; 4-seed averages for stability;
# N=128 matches the smallest prefix of the H3-3A real audit)
N_REAL_MC = 256                 # MC explore: stable p_mc
N_REAL_IS = 128                 # IS per config: region pool = 256 + 128

# gate tolerances
GATE_A_CORR = 0.80                      # rho > 0.8 (task)
GATE_B_MIN_RANGE = 0.15                 # descriptor range threshold
GATE_C_MIN_CONSISTENT = 3               # >= 3 of 4 systems same direction

CASES = [
    {"experiment_id": "A_synthetic_multi_mode_recovery",
     "kind": "synthetic_linear", "label": "linear"},
    {"experiment_id": "B_synthetic_curvature_beta_kappa",
     "kind": "synthetic_curved", "label": "curved"},
    {"experiment_id": "C1_sanger_b1n1_wide", "kind": "real_sanger",
     "anchor": "B1_N1_side", "alpha_factor": 8.0},
    {"experiment_id": "C2_sanger_b2n_wide", "kind": "real_sanger",
     "anchor": "B2_N_side", "alpha_factor": 8.0},
]


# ---------------------------------------------------------------------------
# Frozen anchors: per-case dominant mode x*, x_L (read-only from dataset)
# ---------------------------------------------------------------------------
def _load_case_anchors() -> dict[str, dict]:
    data = json.loads(H3_2_DATASET.read_text(encoding="utf-8"))
    out: dict = {}
    for exp in data["experiments"]:
        eid = exp["experiment_id"]
        pg = exp.get("point_geometry", [])
        if not pg:
            continue
        # dominant mode = largest leak fraction (variance-dominant)
        dom = max(pg, key=lambda g: g.get("leak_fraction", 0.0))
        out[eid] = {
            "mode": dom["topology_label"],
            "x_star": np.asarray(dom["probability_design_point"], dtype=float),
            "x_L": np.asarray(dom["leakage_point"], dtype=float),
            "d_L_frozen": float(dom["distance_between_points"]),
            "leak_fraction": float(dom["leak_fraction"]),
        }
    return out


ANCHORS = _load_case_anchors()


# ---------------------------------------------------------------------------
# Real-system setup (verbatim H3-2 / H3-3A frozen branch)
# ---------------------------------------------------------------------------
def _real_setup(cfg: dict, mlb1: dict):
    env = EnvironmentParams()
    vehicle = VehicleParams()
    a = mlb1["anchors"][cfg["anchor"]]
    K = float(a["K"])
    center = np.array(
        [env.earth_radius + 100000.0, 0.0, 7000.0, np.deg2rad(a["gamma0_deg"])],
        dtype=float,
    )
    gd_ref = a["geometry_direction"]
    beta_ref = float(gd_ref["beta_local"])
    alpha_dir = np.asarray(gd_ref["alpha"], dtype=float)
    nominal = a["expected_regime"]
    alpha = cfg["alpha_factor"] * abs(beta_ref)
    beta_eff = beta_ref / alpha if alpha > 0 else 0.0
    mu_base = frozen.design_point(beta_eff, alpha_dir)
    return env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base


_GLOBALS: dict = {}


def _init_worker(env, vehicle, K, solver, max_time):
    _GLOBALS["env"] = env
    _GLOBALS["vehicle"] = vehicle
    _GLOBALS["K"] = K
    _GLOBALS["solver"] = solver
    _GLOBALS["max_time"] = max_time


def _label_one(x0):
    try:
        info, _ = run_exact_topology(
            x0, env=_GLOBALS["env"], vehicle=_GLOBALS["vehicle"],
            K=_GLOBALS["K"], solver_label=_GLOBALS["solver"],
            max_time=_GLOBALS["max_time"],
        )
        return info.regime
    except Exception:
        return NOMINAL


def _parallel_real_labels(x0_list, env, vehicle, K):
    if len(x0_list) < 8:
        return frozen._real_labels(x0_list, env, vehicle, K)
    with Pool(WORKERS, initializer=_init_worker,
              initargs=(env, vehicle, K, SOLVER, DEFAULT_MAX_TIME)) as pool:
        return np.array(pool.map(_label_one, x0_list))


# ---------------------------------------------------------------------------
# Per-proposal evaluation (identical pipeline to the Synthetic-B pilot)
# ---------------------------------------------------------------------------
def eval_proposal_full(m: np.ndarray, Sigma: np.ndarray, z_mc: np.ndarray,
                       labels_mc: np.ndarray, p_mc: float, var_mc: float,
                       label_fn, rng: np.random.Generator,
                       n_is: int | None = None) -> dict:
    """Evaluate one (m, Sigma); ``label_fn`` maps a z batch to labels."""
    analytic = analytic_variance_geometry(m, Sigma)
    if not analytic["valid"]:
        return {"proposal": {"m": m.tolist(), "Sigma": Sigma.tolist(),
                             "legitimate": False},
                "analytic": analytic,
                "is_performance": None, "region": None,
                "invalid_reason": "Sigma not > 1/2 I (Lambda not PD)"}

    n_is = n_is or N_SYNTH_IS
    z_q = sample_antithetic_gauss(rng, m, Sigma, n_is)
    labels_q = np.asarray(label_fn(z_q))
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


def _synthetic_label_fn(cfg: dict):
    fn = label_linear if cfg["kind"] == "synthetic_linear" else label_curved

    def _batch(z_batch):
        z_batch = np.asarray(z_batch)
        if z_batch.ndim == 1:
            return fn(z_batch)
        return np.array([fn(u) for u in z_batch])

    return _batch


def _real_label_fn(env, vehicle, K, center, alpha, nominal):
    def _fn(z_batch):
        x_list = [center + S_A @ (alpha * z) for z in z_batch]
        return _parallel_real_labels(x_list, env, vehicle, K)
    return _fn


def audit_system(cfg: dict, mlb1: dict, seed: int,
                 only: str) -> tuple[dict, list[dict]]:
    """Return (record, requests).

    Synthetic: record fully materialised (fast); requests empty.
    Real:      record carries setup + _z_mc; requests = [mc, *mean, *cov].
               The caller batches all requests across seeds into ONE Pool
               call per case, then materialises via finalize_real_request.
    """
    eid = cfg["experiment_id"]
    anchors = ANCHORS[eid]
    x_star, x_L = anchors["x_star"], anchors["x_L"]
    rng = np.random.default_rng(seed)

    if cfg["kind"].startswith("synthetic"):
        label_fn = _synthetic_label_fn(cfg)
        n_mc, n_is = N_SYNTH_MC, N_SYNTH_IS
        z_mc = rng.standard_normal((n_mc, DIM))
        labels_mc = np.array([label_fn(u) for u in z_mc])
        p_mc, var_mc = mc_estimator(labels_mc != NOMINAL)
        return _audit_synth(cfg, anchors, z_mc, labels_mc, p_mc, var_mc,
                            label_fn, rng, n_is, seed=seed), []

    env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base = (
        _real_setup(cfg, mlb1))
    n_mc, n_is = N_REAL_MC, N_REAL_IS
    z_mc = rng.standard_normal((n_mc, DIM))
    aligned = float(np.linalg.norm(x_L - x_star)) < 1e-6

    # mean sweep: all lambdas share one proposal when aligned
    mean_reqs: list[dict] = []
    shared = None
    for lam in LAMBDAS:
        m = (1.0 - lam) * x_star + lam * x_L
        Sigma = np.eye(DIM)
        key = f"lambda_{lam:+.1f}"
        if aligned:
            if shared is None:
                z_q = sample_antithetic_gauss(rng, m, Sigma, n_is)
                shared = {"kind": "mean", "cfg_key": key, "z": z_q,
                          "m": m, "Sigma": Sigma}
                mean_reqs.append(shared)
        else:
            z_q = sample_antithetic_gauss(rng, m, Sigma, n_is)
            mean_reqs.append({"kind": "mean", "cfg_key": key, "z": z_q,
                              "m": m, "Sigma": Sigma})

    cov_reqs: list[dict] = []
    for s2 in S2_GRID:
        m = x_star.copy()
        Sigma = s2 * np.eye(DIM)
        z_q = sample_antithetic_gauss(rng, m, Sigma, n_is)
        cov_reqs.append({"kind": "cov", "cfg_key": f"s2_{s2:g}",
                         "z": z_q, "m": m, "Sigma": Sigma})

    record = {
        "case": eid, "kind": cfg["kind"], "seed": seed,
        "anchors": {"mode": anchors["mode"],
                    "x_star": anchors["x_star"].tolist(),
                    "x_L": anchors["x_L"].tolist(),
                    "d_L_frozen": anchors["d_L_frozen"],
                    "leak_fraction": anchors["leak_fraction"]},
        "aligned": aligned,
        "n_mc": n_mc, "n_is": n_is,
        "setup": {"env": env, "vehicle": vehicle, "K": K,
                  "center": center, "alpha": alpha, "nominal": nominal},
        "_z_mc": z_mc,            # internal, excluded from JSON
    }
    requests = [
        {"z": z_mc, "kind": "mc", "cfg_key": None, "m": None, "Sigma": None},
        *mean_reqs, *cov_reqs,
    ]
    return record, requests


def _audit_synth(cfg, anchors, z_mc, labels_mc, p_mc, var_mc,
                 label_fn, rng, n_is, seed: int | None = None) -> dict:
    eid = cfg["experiment_id"]
    x_star, x_L = anchors["x_star"], anchors["x_L"]
    aligned = float(np.linalg.norm(x_L - x_star)) < 1e-6
    mean_sweep: dict = {}
    shared_rec = None
    for lam in LAMBDAS:
        m = (1.0 - lam) * x_star + lam * x_L
        Sigma = np.eye(DIM)
        key = f"lambda_{lam:+.1f}"
        if aligned:
            if shared_rec is None:
                shared_rec = eval_proposal_full(
                    m, Sigma, z_mc, labels_mc, p_mc, var_mc,
                    label_fn, rng, n_is=n_is)
            mean_sweep[key] = shared_rec
        else:
            mean_sweep[key] = eval_proposal_full(
                m, Sigma, z_mc, labels_mc, p_mc, var_mc,
                label_fn, rng, n_is=n_is)
    cov_sweep: dict = {}
    for s2 in S2_GRID:
        m = x_star.copy()
        Sigma = s2 * np.eye(DIM)
        cov_sweep[f"s2_{s2:g}"] = eval_proposal_full(
            m, Sigma, z_mc, labels_mc, p_mc, var_mc,
            label_fn, rng, n_is=n_is)
    return {
        "case": eid, "kind": cfg["kind"], "seed": seed if seed is not None else 0,
        "anchors": {"mode": anchors["mode"],
                    "x_star": anchors["x_star"].tolist(),
                    "x_L": anchors["x_L"].tolist(),
                    "d_L_frozen": anchors["d_L_frozen"],
                    "leak_fraction": anchors["leak_fraction"]},
        "aligned": aligned,
        "p_mc": p_mc, "var_mc": var_mc,
        "n_mc": z_mc.shape[0], "n_is": n_is,
        "mean_sweep": mean_sweep, "cov_sweep": cov_sweep,
    }


def finalize_real_request(record: dict, req: dict, labels_q: np.ndarray,
                          z_mc: np.ndarray, labels_mc: np.ndarray) -> None:
    """Materialise one real request into ``record`` in place."""
    if req["kind"] == "mc":
        p_mc, var_mc = mc_estimator(labels_q != record["setup"]["nominal"])
        record["p_mc"] = p_mc
        record["var_mc"] = var_mc
        record["_labels_mc"] = labels_q
        return
    m, Sigma = req["m"], req["Sigma"]
    analytic = analytic_variance_geometry(m, Sigma)
    if not analytic["valid"]:
        rec = {"proposal": {"m": m.tolist(), "Sigma": Sigma.tolist(),
                            "legitimate": False},
               "analytic": analytic, "is_performance": None, "region": None,
               "invalid_reason": "Sigma not > 1/2 I"}
    else:
        perf = is_performance(req["z"], labels_q, m, Sigma,
                              record["p_mc"], record["var_mc"])
        region: dict = {}
        nominal = record["setup"]["nominal"]
        modes = sorted(set(labels_q.tolist()) - {nominal})
        for topo in modes:
            mask_mc = labels_mc == topo
            mask_is = labels_q == topo
            if not (np.any(mask_mc) or np.any(mask_is)):
                continue
            z_mode = np.vstack([z_mc[mask_mc], req["z"][mask_is]])
            source = np.concatenate([
                np.full(int(mask_mc.sum()), "mc"),
                np.full(int(mask_is.sum()), "is"),
            ])
            geo = mode_region_geometry(z_mode, source, m, Sigma, ETAS)
            if geo is not None:
                region[str(topo)] = geo
        rec = {
            "proposal": {"m": m.tolist(), "Sigma": Sigma.tolist(),
                         "legitimate": True},
            "analytic": analytic,
            "is_performance": perf,
            "region": region,
        }
    sweep = record["mean_sweep"] if req["kind"] == "mean" \
        else record["cov_sweep"]
    if req["kind"] == "mean" and record.get("aligned"):
        # degenerate mean lever: all lambdas share the one proposal record
        for lam in LAMBDAS:
            sweep[f"lambda_{lam:+.1f}"] = rec
    else:
        sweep[req["cfg_key"]] = rec


# ---------------------------------------------------------------------------
# Analysis (Q1/Q2/Q3 + gates)
# ---------------------------------------------------------------------------
def _rows_of(per_case: dict, case: str, sweep: str,
             seeds: list[int]) -> list[tuple[float, dict]]:
    rows = []
    for s in seeds:
        rec = per_case.get(case, {}).get(f"seed_{s}", {})
        for cfg_key, r in rec.get(sweep, {}).items():
            if r and r.get("is_performance") is not None:
                rows.append((float(cfg_key.split("_")[-1]), r))
    return rows


def _coord_spearman(a_list, b_list):
    if len(a_list) != len(b_list) or len(a_list) < 3:
        return float("nan")
    A = np.asarray(a_list); B = np.asarray(b_list)
    rhos = [_spearman(A[:, j].tolist(), B[:, j].tolist())
            for j in range(A.shape[1])]
    rhos = [r for r in rhos if not np.isnan(r)]
    return float(np.mean(rhos)) if rhos else float("nan")


def _metric_list(rows, mode, key):
    return [rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"][key]
            for _, rec in rows if mode in rec.get("region", {})]


def per_system_analysis(per_case: dict, case: str) -> dict:
    """Gate A evidence per system."""
    seeds = [int(k.split("_")[1]) for k in per_case[case].keys()]
    rows_ms = _rows_of(per_case, case, "mean_sweep", seeds)
    rows_cs = _rows_of(per_case, case, "cov_sweep", seeds)
    mode = ANCHORS[case]["mode"]

    # mean lever: coord-wise Spearman(mu_V, m_eta) -- N/A if degenerate
    muVs = [np.asarray(rec["analytic"]["mu_V"]) for _, rec in rows_ms
            if rec["analytic"].get("valid")]
    mEtas = [np.asarray(rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]["m_eta"])
             for _, rec in rows_ms if mode in rec.get("region", {})]
    corr_mean = _coord_spearman(muVs, mEtas) if len(muVs) == len(mEtas) \
        else float("nan")

    # cov lever: Spearman(tr Sigma_V, R_eta)
    trV = [rec["analytic"]["Sigma_V_trace"] for _, rec in rows_cs
           if rec["analytic"].get("valid")]
    R = _metric_list(rows_cs, mode, "R")
    corr_cov = _spearman(trV, R) if len(trV) == len(R) else float("nan")

    # descriptor response ranges (Gate B evidence)
    def desc_range(sweep_rows, key):
        vals = _metric_list(sweep_rows, mode, key)
        st = _mean_std(vals)
        return {"mean": st.get("mean"), "range": st.get("range"),
                "spearman_vs_cfg": _spearman(
                    [c for c, _ in sweep_rows if mode in _.get("region", {})],
                    vals)}

    d_R_ms = desc_range(rows_ms, "R")
    d_G_ms = desc_range(rows_ms, "G")
    d_C_ms = desc_range(rows_ms, "C")
    d_R_cs = desc_range(rows_cs, "R")
    d_G_cs = desc_range(rows_cs, "G")

    gate_a_mean = bool(not np.isnan(corr_mean) and corr_mean > GATE_A_CORR)
    gate_a_cov = bool(not np.isnan(corr_cov) and corr_cov > GATE_A_CORR)
    return {
        "mode": mode,
        "aligned": ANCHORS[case]["d_L_frozen"] < 1e-6,
        "gate_a": {
            "pass": bool(gate_a_mean or gate_a_cov),
            "evidence": {
                "corr_mean_lever_muV_vs_m_eta": corr_mean,
                "corr_cov_lever_SigmaV_trace_vs_R_eta": corr_cov,
                "mean_lever_available": not np.isnan(corr_mean),
            },
        },
        "descriptors": {
            "R_eta(mean_sweep)": d_R_ms, "G_eta(mean_sweep)": d_G_ms,
            "C_eta(mean_sweep)": d_C_ms, "R_eta(cov_sweep)": d_R_cs,
            "G_eta(cov_sweep)": d_G_cs,
        },
    }


def eval_gates(per_case: dict) -> dict:
    """Gate A (per system), Gate B (cross-system response), Gate C (trend)."""
    active = [c for c in CASES_ID if per_case.get(c, {})]
    sys_an = {c: per_system_analysis(per_case, c) for c in active}

    # Gate A
    gate_a = {"per_system": {c: sys_an[c]["gate_a"] for c in active},
              "pass": bool(active and all(
                  sys_an[c]["gate_a"]["pass"] for c in active))}

    # Gate B: each system has at least one descriptor range >= threshold
    gate_b_per_sys = {}
    for c in active:
        ds = sys_an[c]["descriptors"]
        ranges = {
            "R_ms": ds["R_eta(mean_sweep)"]["range"],
            "G_ms": ds["G_eta(mean_sweep)"]["range"],
            "C_ms": ds["C_eta(mean_sweep)"]["range"],
            "R_cs": ds["R_eta(cov_sweep)"]["range"],
            "G_cs": ds["G_eta(cov_sweep)"]["range"],
        }
        non_null = [v for v in ranges.values() if v is not None]
        ok = bool(non_null and max(non_null) >= GATE_B_MIN_RANGE)
        gate_b_per_sys[c] = {"pass": ok, "ranges": ranges}
    gate_b = {"per_system": gate_b_per_sys,
              "pass": bool(active and all(
                  v["pass"] for v in gate_b_per_sys.values()))}

    # Gate C: trend direction consistent across systems (Synthetic -> Real)
    # use cov-sweep R_eta vs s^2 direction and tr(Sigma_V) vs R_eta sign
    dir_signs: dict[str, dict] = {}
    for c in active:
        rows_cs = _rows_of(per_case, c, "cov_sweep",
                           [int(k.split("_")[1]) for k in per_case[c].keys()])
        mode = ANCHORS[c]["mode"]
        R = _metric_list(rows_cs, mode, "R")
        trV = [rec["analytic"]["Sigma_V_trace"] for _, rec in rows_cs
               if rec["analytic"].get("valid")]
        s2 = [c2 for c2, _ in rows_cs]
        rho_R_s2 = _spearman(s2, R) if len(R) >= 3 else float("nan")
        rho_trV_R = _spearman(trV, R) if len(trV) == len(R) and len(R) >= 3 \
            else float("nan")
        # R_eta should grow with s^2 (wider proposal -> larger Sigma_V)
        sign_R_s2 = 1 if (rho_R_s2 > 0.3) else (-1 if rho_R_s2 < -0.3 else 0)
        dir_signs[c] = {"spearman_R_vs_s2": rho_R_s2,
                        "spearman_trV_vs_R": rho_trV_R, "sign": sign_R_s2}
    signs = [v["sign"] for v in dir_signs.values() if v["sign"] != 0]
    n_consistent = max(signs.count(1), signs.count(-1)) if signs else 0
    gate_c = {
        "pass": bool(n_consistent >= GATE_C_MIN_CONSISTENT),
        "evidence": {
            "per_system_direction": dir_signs,
            "n_consistent": n_consistent,
            "n_directional": len(signs),
            "consistent_direction": (1 if n_consistent == signs.count(1)
                                     else -1) if signs else None,
        },
    }
    return {"gate_a": gate_a, "gate_b": gate_b, "gate_c": gate_c,
            "per_system_analysis": sys_an}


CASES_ID = [c["experiment_id"] for c in CASES]


def build_dataset(per_case: dict, gates: dict, wall_s: float) -> dict:
    return {
        "schema_version": "h3-3b-multi-system-validation-v1",
        "status": "GENERATED",
        "stage": "H3-3B (multi-system validation)",
        "date": "2026-08-21",
        "scope": "4 systems: synthetic linear/curved + real Sanger B1N1/B2N",
        "frozen_reuse": {
            "h3_2_dataset": "tests/data/h3_2_leakage_point_dataset_v1.json",
            "ml_b1_snapshot": "tests/data/ml_b1_first_order_geometry_v1.json",
            "seed_scheme": "fixed seeds {1, 2120, 3, 4}",
            "real_workers": WORKERS,
        },
        "config": {
            "etas": ETAS, "eta_main": ETA_MAIN,
            "lambdas": LAMBDAS, "s2_grid": S2_GRID,
            "legitimacy_rule": "Sigma > 1/2 I; s^2 <= 0.5 invalid, not run",
            "real_sample_sizes": {"mc": N_REAL_MC, "is": N_REAL_IS},
            "gate_tolerances": {"GATE_A_CORR": GATE_A_CORR,
                                "GATE_B_MIN_RANGE": GATE_B_MIN_RANGE,
                                "GATE_C_MIN_CONSISTENT": GATE_C_MIN_CONSISTENT},
        },
        "anchors": {c: {"mode": ANCHORS[c]["mode"],
                        "x_star": ANCHORS[c]["x_star"].tolist(),
                        "x_L": ANCHORS[c]["x_L"].tolist(),
                        "d_L_frozen": ANCHORS[c]["d_L_frozen"]}
                    for c in CASES_ID},
        "per_case": per_case,
        "gates": gates,
        "total_wall_seconds": round(wall_s, 1),
    }


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def make_figures(per_case: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    labels_short = {"A_synthetic_multi_mode_recovery": "A (lin)",
                    "B_synthetic_curvature_beta_kappa": "B (curved)",
                    "C1_sanger_b1n1_wide": "C1 (real)",
                    "C2_sanger_b2n_wide": "C2 (real)"}
    colors = {"A_synthetic_multi_mode_recovery": "#1f77b4",
              "B_synthetic_curvature_beta_kappa": "#ff7f0e",
              "C1_sanger_b1n1_wide": "#2ca02c",
              "C2_sanger_b2n_wide": "#d62728"}

    # ---- Fig 15: multi-system proposal geometry comparison ---------------
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 10.2))
    for ax, c in zip(axes.ravel(), CASES_ID):
        if not per_case.get(c, {}):
            ax.text(0.5, 0.5, "not run", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(labels_short[c], fontsize=10)
            continue
        mode = ANCHORS[c]["mode"]
        seeds_c = [int(k.split("_")[1]) for k in per_case[c].keys()]
        rows_ms = _rows_of(per_case, c, "mean_sweep", seeds_c)
        rows_cs = _rows_of(per_case, c, "cov_sweep", seeds_c)
        # mean sweep: mu_V trajectory vs m_eta trajectory (z1-z2 plane)
        mus = [np.asarray(rec["analytic"]["mu_V"]) for _, rec in rows_ms
               if rec["analytic"].get("valid")]
        mes = [np.asarray(rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]["m_eta"])
               for _, rec in rows_ms if mode in rec.get("region", {})]
        x_star = np.asarray(ANCHORS[c]["x_star"])
        x_L = np.asarray(ANCHORS[c]["x_L"])
        if mus:
            M = np.asarray(mus); ax.plot(M[:, 0], M[:, 1], "--", lw=1.4,
                                         color=colors[c], alpha=0.85,
                                         label=r"$\mu_V$ (analytic)")
            ax.scatter(M[0, 0], M[0, 1], s=18, color=colors[c], alpha=0.4)
            ax.scatter(M[-1, 0], M[-1, 1], s=30, color=colors[c], alpha=0.9)
        if mes:
            Me = np.asarray(mes)
            ax.plot(Me[:, 0], Me[:, 1], "-o", lw=1.2, ms=4, color="k",
                    alpha=0.75, label=r"$m_\eta$ (region)")
        ax.plot(x_star[0], x_star[1], "*", color="k", ms=13,
                label=r"$x^*$")
        if np.linalg.norm(x_L - x_star) > 1e-3:
            ax.plot(x_L[0], x_L[1], "P", color="crimson", ms=11,
                    label=r"$x_L$")
        else:
            ax.text(0.02, 0.98, "aligned ($x^*=x_L$)", transform=ax.transAxes,
                    ha="left", va="top", fontsize=8,
                    bbox=dict(boxstyle="round", fc="white", alpha=0.8))
        ax.set_title(f"{labels_short[c]}  ({mode})", fontsize=10)
        ax.set_xlabel("$z_1$"); ax.set_ylabel("$z_2$")
        ax.legend(fontsize=7, loc="best"); ax.grid(True, alpha=0.3)
        # cov sweep annotation
        trV = [rec["analytic"]["Sigma_V_trace"] for _, rec in rows_cs
               if rec["analytic"].get("valid")]
        R = [rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]["R"]
             for _, rec in rows_cs if mode in rec.get("region", {})]
        rho = _spearman(trV, R) if len(trV) == len(R) else float("nan")
        ax.text(0.02, 0.88, f"cov: $\\rho$(tr$\\Sigma_V$,$R_\\eta$)={rho:.2f}",
                transform=ax.transAxes, ha="left", va="top", fontsize=8)
    fig.suptitle("Fig 15 — multi-system proposal geometry: analytic core vs "
                 "region estimator", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    f1 = FIG_DIR / "fig15_multi_system_geometry.png"
    fig.savefig(f1, dpi=160); plt.close(fig); files.append(str(f1.relative_to(REPO)))

    # ---- Fig 16: region descriptor stability across systems --------------
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8))
    active_cases = [c for c in CASES_ID if per_case.get(c, {})]
    xpos = np.arange(len(active_cases)) * 3.0
    for ax, (key, name) in zip(axes, (("C", "$C_\\eta$"), ("R", "$R_\\eta$"),
                                      ("G", "$G_\\eta$"))):
        for i, c in enumerate(active_cases):
            mode = ANCHORS[c]["mode"]
            seeds_c = [int(k.split("_")[1]) for k in per_case[c].keys()]
            xx = xpos[i]
            vals_ms = []
            for _, rec in _rows_of(per_case, c, "mean_sweep", seeds_c):
                if mode in rec.get("region", {}):
                    vals_ms.append(rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"][key])
            vals_cs = []
            for _, rec in _rows_of(per_case, c, "cov_sweep", seeds_c):
                if mode in rec.get("region", {}):
                    vals_cs.append(rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"][key])
            if vals_ms:
                ax.boxplot(vals_ms, positions=[xx - 0.45], widths=0.55,
                           showfliers=False, patch_artist=True,
                           boxprops=dict(facecolor=colors[c], alpha=0.55),
                           medianprops=dict(color="k", lw=0.8))
            if vals_cs:
                ax.boxplot(vals_cs, positions=[xx + 0.45], widths=0.55,
                           showfliers=False, patch_artist=True,
                           boxprops=dict(facecolor="white",
                                         edgecolor=colors[c], lw=1.2),
                           medianprops=dict(color=colors[c], lw=0.8))
        ax.set_xticks(xpos, [labels_short[c] for c in active_cases],
                      fontsize=8)
        ax.set_ylabel(name)
        ax.set_title(f"{name} — shaded: mean sweep, white: cov sweep",
                     fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
    fig.suptitle("Fig 16 — region descriptor stability across systems "
                 "(4 seeds)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    f2 = FIG_DIR / "fig16_region_descriptor_stability.png"
    fig.savefig(f2, dpi=160); plt.close(fig); files.append(str(f2.relative_to(REPO)))

    # ---- Fig 17: geometry-performance relationship -----------------------
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8))
    for ax, (key, name) in zip(axes, (("C", "$C_\\eta$"), ("R", "$R_\\eta$"),
                                      ("G", "$G_\\eta$"))):
        for c in active_cases:
            mode = ANCHORS[c]["mode"]
            seeds_c = [int(k.split("_")[1]) for k in per_case[c].keys()]
            xs, ys = [], []
            for sweep in ("mean_sweep", "cov_sweep"):
                for _, rec in _rows_of(per_case, c, sweep, seeds_c):
                    if mode not in rec.get("region", {}) or \
                            rec.get("is_performance") is None:
                        continue
                    if not np.isfinite(rec["is_performance"]["vrf"]):
                        continue
                    eg = rec["region"][mode]["per_eta"][f"eta_{ETA_MAIN}"]
                    xs.append(rec["is_performance"]["vrf"])
                    ys.append(eg[key])
            ax.scatter(xs, ys, s=30, color=colors[c], alpha=0.6,
                       label=labels_short[c])
        ax.set_xscale("log")
        ax.set_xlabel("VRF (log scale)")
        ax.set_ylabel(name)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
    fig.suptitle("Fig 17 — geometry descriptors vs IS performance across "
                 "systems (correlation only, no causality)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    f3 = FIG_DIR / "fig17_geometry_vs_vrf_multisystem.png"
    fig.savefig(f3, dpi=160); plt.close(fig); files.append(str(f3.relative_to(REPO)))
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _load_existing(per_case: dict) -> None:
    """Merge already-completed seeds from an existing result JSON (resume).

    Format mirrors build_dataset's ``per_case``: {case: {seed_N: rec}}.
    Synthetic records are kept as-is; real records too (they carry
    real_setup_summary instead of setup, so they are JSON-safe).
    """
    if not OUT_JSON.exists():
        return
    try:
        data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    except Exception:
        return
    for cid, seed_map in data.get("per_case", {}).items():
        if cid not in per_case:
            per_case[cid] = {}
        for seed_key, rec in seed_map.items():
            if seed_key not in per_case[cid]:
                per_case[cid][seed_key] = rec


def main() -> None:
    parser = argparse.ArgumentParser(description="H3-3B multi-system validation")
    parser.add_argument("--only", choices=["synthetic", "real", "all"],
                        default="all")
    args = parser.parse_args()
    t0 = time.perf_counter()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    mlb1 = json.loads(MLB1_PATH.read_text(encoding="utf-8"))

    per_case: dict = {c: {} for c in CASES_ID}
    _load_existing(per_case)
    for cfg in CASES:
        eid = cfg["experiment_id"]
        kind = cfg["kind"]
        if args.only == "real" and kind.startswith("synthetic"):
            continue
        if args.only == "synthetic" and kind == "real_sanger":
            continue

        if kind.startswith("synthetic"):
            for seed in SEEDS:
                if f"seed_{seed}" in per_case[eid]:
                    print(f"[{eid}] seed={seed} reused", flush=True)
                    continue
                t1 = time.perf_counter()
                rec, _ = audit_system(cfg, mlb1, seed, args.only)
                per_case[eid][f"seed_{seed}"] = rec
                print(f"[{eid}] seed={seed} done "
                      f"({time.perf_counter()-t1:.0f}s, p_mc={rec['p_mc']:.4f})",
                      flush=True)
        else:
            # ---- real: batch ALL requests across seeds into ONE Pool call --
            records: dict[int, dict] = {}
            all_reqs: list[tuple[int, dict]] = []   # (seed, request)
            for seed in SEEDS:
                if f"seed_{seed}" in per_case[eid]:
                    print(f"[{eid}] seed={seed} reused", flush=True)
                    continue
                rec, reqs = audit_system(cfg, mlb1, seed, args.only)
                records[seed] = rec
                rec["mean_sweep"] = {}
                rec["cov_sweep"] = {}
                for r in reqs:
                    all_reqs.append((seed, r))
            if not records:
                continue
            # concatenate z-batches, label once with 4 workers
            first_rec = records[list(records.keys())[0]]
            setup0 = first_rec["setup"]
            env0 = setup0["env"]; vehicle0 = setup0["vehicle"]
            K0 = setup0["K"]; center0 = setup0["center"]
            alpha0 = setup0["alpha"]
            offsets = []
            all_z = []
            for _, r in all_reqs:
                offsets.append((len(all_z), len(all_z) + len(r["z"])))
                all_z.append(r["z"])
            all_z = np.vstack(all_z)
            x_all = [center0 + S_A @ (alpha0 * z) for z in all_z]
            labels_all = _parallel_real_labels(x_all, env0, vehicle0, K0)
            # split back: MC requests first (set _labels_mc), then IS
            for (seed, r), (i0, i1) in zip(all_reqs, offsets):
                if r["kind"] != "mc":
                    continue
                labels_q = labels_all[i0:i1]
                rec = records[seed]
                finalize_real_request(rec, r, labels_q, None, None)
            for (seed, r), (i0, i1) in zip(all_reqs, offsets):
                if r["kind"] == "mc":
                    continue
                labels_q = labels_all[i0:i1]
                rec = records[seed]
                finalize_real_request(rec, r, labels_q, rec["_z_mc"],
                                      rec["_labels_mc"])
            for seed, rec in records.items():
                rec.pop("_z_mc", None)
                rec.pop("_labels_mc", None)
                setup = rec.pop("setup", {})
                rec["real_setup_summary"] = {
                    "K": float(setup["K"]), "alpha": float(setup["alpha"]),
                    "nominal": str(setup["nominal"]),
                    "center": [float(v) for v in setup["center"]],
                }
                per_case[eid][f"seed_{seed}"] = rec
                print(f"[{eid}] seed={seed} done "
                      f"(p_mc={rec['p_mc']:.4f}, "
                      f"mean={len(rec['mean_sweep'])}, "
                      f"cov={len(rec['cov_sweep'])})", flush=True)

    gates = eval_gates(per_case)
    dataset = build_dataset(per_case, gates, time.perf_counter() - t0)
    OUT_JSON.write_text(
        json.dumps(dataset, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fig_files = make_figures(per_case)

    print("\n=== GATES ===")
    print(json.dumps(gates["gate_a"], indent=1))
    print(json.dumps(gates["gate_b"], indent=1))
    print(json.dumps(gates["gate_c"], indent=1))
    print(f"\nfigures: {fig_files}")
    print(f"total wall time: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
