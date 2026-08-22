"""H3-3A -- Set-valued variance geometry & stability pilot.

Core question
-------------
When the single-point leakage point ``x_L = argmax_A rho_L`` is unstable
under finite samples / flat landscape, is the variance geometry itself
still captured by a *stable region*?

Objects
-------
- leakage density          rho_L(x) = 1_A(x) p(x)^2 / q(x),   M_2 = int_A p^2/q
- variance-tilted measure  nu_V(dx) = rho_L(x) / M_2 dx
- variance-critical region L_eta = {x in A : rho_L(x) >= c_eta},
  c_eta chosen s.t. nu_V(L_eta) >= eta     (eta in {0.5, 0.8, 0.9}; main 0.8)
- region separation       D_eta = dist(x*, L_eta)         (x* = MPP of mode)
- region spread           R_eta = sqrt(E_nuV[||X - m_eta||^2 | X in L_eta])
- separation-to-spread    S_eta = D_eta / (R_eta + eps)
- point geometry kept      d_L = ||x* - x_L||

Set estimator (Sec. 5 of the task)
----------------------------------
Candidates are pooled samples of the mode from two proposals:
  - MC:  r = phi = N(0, I)      ->  omega_i^V ∝ rho_L/phi     = w_i
  - IS:  r = q   = N(mu, I)     ->  omega_i^V ∝ rho_L/q       = w_i^2
(``w = phi/q`` is the frozen Geometry-IS importance weight; both ratios
coincide with the continuous variance-mass weight rho_L/r up to a common
constant that cancels under normalisation.)  This distinguishes *high
leakage density* from *high sampling density* -- we never take "top 20%".

The region estimator is the highest-density region (HDR): sort by rho_L
descending, accumulate normalised variance mass, take the minimal prefix
whose mass >= eta.  All H3-2 frozen artifacts are reused read-only
(dynamics, topology evaluator, importance weights, leakage density,
synthetic boundary, deterministic seeds).  No H3-2 file is modified.

Audit
-----
Seeds: {1, 2120, 3, 4}.  Real systems: N, 4N, 16N = 128, 512, 2048 via
prefix evaluation of one iid big batch (workers <= 4).  Synthetic: frozen
sample sizes (50k MC explore + 200k IS), seed-audited only.

Gates
-----
- Gate A (synthetic B, S2): D_0.8 > 0 and separation direction aligns with
  the frozen H3-2 point separation (d_L ~= 0.775).
- Gate B (real C1): D_0.8 / R_0.8 / S_0.8 markedly more stable than d_L;
  ideal D_0.8 ~= 0 with large R_0.8 (diffuse overlapping plateau).
- Gate C: regime judgement consistent across eta in {0.5, 0.8, 0.9};
  if not, report -- never cherry-pick the favourable threshold.

Outputs
-------
results/phase_h3/h3_3a_set_valued_geometry_v1.json
results/phase_h3/fig10_b_vs_c1_region_comparison.png
results/phase_h3/fig11_dL_vs_set_geometry_stability.png
docs/phase_h/H3_3A_set_valued_variance_geometry.md

Usage
-----
    python scripts/run_h3_3a_set_valued_geometry.py --only synthetic
    python scripts/run_h3_3a_set_valued_geometry.py --only real
    python scripts/run_h3_3a_set_valued_geometry.py            # both
"""

from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.uncertainty.leakage_point_geometry import leakage_density
from hyptraj.uncertainty.topology_margin import (
    DEFAULT_MAX_TIME,
    S_A,
    run_exact_topology,
)
from hyptraj.uncertainty.variance_leakage import (
    design_point,
    importance_weights,
)

# ---- frozen H3-2 pipeline reuse (read-only) ------------------------------
import run_h3_2_adaptive_geometry_is as frozen

_antithetic = frozen._antithetic
label_linear = frozen.label_linear
label_curved = frozen.label_curved
NOMINAL = frozen.NOMINAL
SOLVER = frozen.SOLVER
N_SYNTH_MC = frozen.N_SYNTH_MC      # 50_000  (synthetic MC explore)
N_SYNTH_IS = frozen.N_SYNTH         # 200_000 (synthetic IS pass)

REPO = Path(__file__).resolve().parents[1]
MLB1_PATH = REPO / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3a_set_valued_geometry_v1.json"
FIG_DIR = REPO / "results" / "phase_h3"

# ---- audit configuration (Sec. 4 of the task) ----------------------------
SEEDS = [1, 2120, 3, 4]
ETAS = [0.5, 0.8, 0.9]
ETA_MAIN = 0.8
N_AUDIT = [128, 512, 2048]
N_BIG = 2048
WORKERS = 4                     # real dynamics: workers <= 4 (frozen rule)
EPS = 1e-8                      # S_eta denominator guard

# regime-labelling tolerances (documented; Gate C tests cross-eta stability)
TOL_D = 0.10                    # separation below this => region touches x*
TOL_S = 0.50                    # S >= this with D > TOL_D => sharp-separated
TOL_R = 0.35                    # R >= this with D <= TOL_D => diffuse plateau

CASES = [
    {"experiment_id": "A_synthetic_multi_mode_recovery",
     "kind": "synthetic_linear"},
    {"experiment_id": "B_synthetic_curvature_beta_kappa",
     "kind": "synthetic_curved"},
    {"experiment_id": "C1_sanger_b1n1_wide", "kind": "real_sanger",
     "anchor": "B1_N1_side", "alpha_factor": 8.0},
    {"experiment_id": "C2_sanger_b2n_wide", "kind": "real_sanger",
     "anchor": "B2_N_side", "alpha_factor": 8.0},
]

FROZEN_B_SEP = 0.7751          # H3-2 frozen point separation for B S2


# ---------------------------------------------------------------------------
# Set-valued geometry estimator
# ---------------------------------------------------------------------------
def variance_mass_weights(z: np.ndarray, source: np.ndarray,
                          mu_base: np.ndarray) -> np.ndarray:
    """Normalised variance-mass weights ``omega_i^V ~ rho_L(z_i)/r(z_i)``.

    ``rho_L = phi^2/q`` with ``phi = N(0, I)``, ``q = N(mu_base, I)`` and
    importance weight ``w = phi/q``:
      - MC samples  (r = phi):  omega^V ~ rho_L/phi  = w
      - IS samples  (r = q):    omega^V ~ rho_L/q    = w^2
    (the same common constant appears in both cases and cancels).
    """
    w = importance_weights(z, mu_base)
    wV_raw = np.where(source == "is", w * w, w)
    s = float(wV_raw.sum())
    if s <= 0.0 or not np.isfinite(s):
        raise ValueError("degenerate variance-mass weights")
    return wV_raw / s


def mode_set_geometry(z_mode: np.ndarray, source: np.ndarray,
                      mu_base: np.ndarray, eta_list: list[float],
                      return_pool: bool = False
                      ) -> dict | None | tuple[dict | None, dict]:
    """Point + set-valued geometry for one topology mode (pooled samples).

    With ``return_pool=True`` also returns the raw pool (z, source codes,
    rho, variance mass, eta-main region mask) for diagnostics/figures.
    """
    z_mode = np.asarray(z_mode, dtype=float)
    source = np.asarray(source)
    if z_mode.ndim != 2 or z_mode.shape[0] == 0:
        return (None, {}) if return_pool else None
    rho = leakage_density(z_mode, mu_base)
    wV = variance_mass_weights(z_mode, source, mu_base)

    # point geometry (same pooled set => self-consistent with region)
    x_star = z_mode[int(np.argmin(np.sum(z_mode ** 2, axis=1)))]
    x_L = z_mode[int(np.argmax(rho))]
    d_L = float(np.linalg.norm(x_L - x_star))

    # HDR region: sort by rho_L desc, accumulate variance mass
    order = np.argsort(rho)[::-1]
    cum = np.cumsum(wV[order])
    per_eta: dict = {}
    for eta in eta_list:
        k = int(np.searchsorted(cum, eta))          # first idx with mass >= eta
        reg = order[: k + 1]
        wv = wV[reg]
        m = np.average(z_mode[reg], axis=0, weights=wv)
        R = float(np.sqrt(np.average(
            np.sum((z_mode[reg] - m) ** 2, axis=1), weights=wv)))
        D = float(np.min(np.linalg.norm(z_mode[reg] - x_star, axis=1)))
        S = float(D / (R + EPS))
        # direction consistency vs the point estimator x_L
        v1 = m - x_star
        v2 = x_L - x_star
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        align = float(np.dot(v1, v2) / (n1 * n2)) if n1 > 0.0 and n2 > 0.0 else 0.0
        per_eta[f"eta_{eta}"] = {
            "D": D, "R": R, "S": S,
            "m_eta": [float(v) for v in m],
            "c_eta": float(rho[reg[-1]]),
            "c_eta_ratio": float(rho[reg[-1]] / rho.max()) if rho.max() > 0 else 0.0,
            "n_points": int(len(reg)),
            "mass": float(cum[k]),
            "align_xL": align,
        }
    result = {
        "x_star": [float(v) for v in x_star],
        "x_L": [float(v) for v in x_L],
        "d_L": d_L,
        "rho_L_max": float(rho.max()),
        "n_pool": int(z_mode.shape[0]),
        "per_eta": per_eta,
    }
    if return_pool:
        reg_main = order[: int(np.searchsorted(cum, ETA_MAIN)) + 1]
        mask = np.zeros(z_mode.shape[0], dtype=bool)
        mask[reg_main] = True
        pool = {
            "z": z_mode.astype(np.float32),
            "source": (source == "is").astype(np.int8),
            "rho": rho.astype(np.float32),
            "wV": wV.astype(np.float32),
            "region_main": mask.astype(np.int8),
        }
        return result, pool
    return result


def regime_label(g: dict, d_L: float) -> str:
    """Regime label for one eta row (documented tolerances above).

    The label encodes the H3-3A question directly: does the variance-
    critical region *reproduce* the point-estimator separation?
      - d_L ~ 0  &  D ~ 0        -> aligned (compact or diffuse by R)
      - d_L > 0  &  D > 0.5 d_L  -> sharp-separated (region follows point)
      - d_L > 0  &  D <= 0.5 d_L -> overlap-diffuse (region overlaps the
                                    MPP despite point separation)
    """
    D, R = g["D"], g["R"]
    if d_L <= TOL_D and D <= TOL_D:
        return "aligned-diffuse" if R >= TOL_R else "aligned-compact"
    if d_L > TOL_D:
        if D > 0.5 * d_L:
            return "sharp-separated"
        return "overlap-diffuse"
    return "region-separated"       # d_L ~ 0 but D > 0 (unusual)


# ---------------------------------------------------------------------------
# Synthetic branch (frozen sample sizes; seed audit only)
# ---------------------------------------------------------------------------
def audit_synthetic(cfg: dict, seed: int, keep_pool: bool = False) -> dict:
    label_fn = label_linear if cfg["kind"] == "synthetic_linear" else label_curved
    rng = np.random.default_rng(seed)
    d = 4
    mu_base = np.array([-1.5, 0.0, 0.0, 0.0])       # frozen ML-B1-style design pt
    nominal = NOMINAL

    z_mc = rng.standard_normal((N_SYNTH_MC, d))
    labels_mc = np.array([label_fn(u) for u in z_mc])
    z_is = _antithetic(rng, mu_base, N_SYNTH_IS)
    labels_is = np.array([label_fn(u) for u in z_is])

    p_mc = float((labels_mc != nominal).mean())
    modes = sorted(set(np.concatenate([labels_mc, labels_is])) - {nominal})
    per_mode: dict = {}
    pools: dict = {}
    for topo in modes:
        mask_mc = labels_mc == topo
        mask_is = labels_is == topo
        z_mode = np.vstack([z_mc[mask_mc], z_is[mask_is]])
        source = np.concatenate([
            np.full(int(mask_mc.sum()), "mc"),
            np.full(int(mask_is.sum()), "is"),
        ])
        geo = mode_set_geometry(z_mode, source, mu_base, ETAS,
                                return_pool=keep_pool)
        if keep_pool:
            geo, pool = geo
            if pool["z"].shape[0] > 0:
                pools[str(topo)] = pool
        if geo is not None:
            per_mode[str(topo)] = geo
    rec = {
        "seed": seed,
        "p_mc": p_mc,
        "n_mc": N_SYNTH_MC,
        "n_is": N_SYNTH_IS,
        "per_mode": per_mode,
    }
    if keep_pool:
        rec["_pool"] = pools
    return rec


# ---------------------------------------------------------------------------
# Real branch (parallel exact topology; prefix N audit; workers <= 4)
# ---------------------------------------------------------------------------
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


def parallel_real_labels(x0_list, env, vehicle, K, workers=WORKERS):
    """Labels via the frozen solver, parallelised (workers <= 4 rule)."""
    if workers <= 1 or len(x0_list) < 8:
        return frozen._real_labels(x0_list, env, vehicle, K)
    with Pool(workers, initializer=_init_worker,
              initargs=(env, vehicle, K, SOLVER, DEFAULT_MAX_TIME)) as pool:
        return np.array(pool.map(_label_one, x0_list))


def _real_setup(cfg: dict, mlb1: dict):
    """Frozen C1/C2 branch setup (verbatim from the H3-2 generator)."""
    env = EnvironmentParams()
    vehicle = VehicleParams()
    name = cfg["anchor"]
    a = mlb1["anchors"][name]
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
    beta_eff = beta_ref / alpha
    mu_base = design_point(beta_eff, alpha_dir)
    return env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base


def audit_real(cfg: dict, mlb1: dict, seed: int,
               keep_pool: bool = False) -> dict:
    """One big iid batch per seed; prefixes give N, 4N, 16N (Sec. 4)."""
    env, vehicle, K, center, alpha_dir, nominal, alpha, mu_base = _real_setup(
        cfg, mlb1
    )
    rng = np.random.default_rng(seed)
    z_mc = rng.standard_normal((N_BIG, 4))
    z_is = _antithetic(rng, mu_base, N_BIG)

    x_mc = [center + S_A @ (alpha * z) for z in z_mc]
    x_is = [center + S_A @ (alpha * z) for z in z_is]
    labels_mc = parallel_real_labels(x_mc, env, vehicle, K)
    labels_is = parallel_real_labels(x_is, env, vehicle, K)

    rows: dict = {}
    pools: dict = {}
    for N in N_AUDIT:
        zm, lm = z_mc[:N], labels_mc[:N]
        zi, li = z_is[:N], labels_is[:N]
        p_mc = float((lm != nominal).mean())
        modes = sorted(set(np.concatenate([lm, li])) - {nominal})
        per_mode: dict = {}
        for topo in modes:
            mask_mc = lm == topo
            mask_is = li == topo
            z_mode = np.vstack([zm[mask_mc], zi[mask_is]])
            source = np.concatenate([
                np.full(int(mask_mc.sum()), "mc"),
                np.full(int(mask_is.sum()), "is"),
            ])
            geo = mode_set_geometry(z_mode, source, mu_base, ETAS,
                                    return_pool=keep_pool and N == N_BIG)
            if keep_pool and N == N_BIG:
                geo, pool = geo
                if pool["z"].shape[0] > 0:
                    pools[str(topo)] = pool
            if geo is not None:
                per_mode[str(topo)] = geo
        rows[f"N{N}"] = {"N": N, "p_mc": p_mc, "per_mode": per_mode}
    rec = {"seed": seed, "rows": rows}
    if keep_pool:
        rec["_pool"] = pools
    return rec


# ---------------------------------------------------------------------------
# Stability statistics
# ---------------------------------------------------------------------------
def _stats(values: list[float]) -> dict:
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "mad": float(np.median(np.abs(a - np.median(a)))),
        "range": float(a.max() - a.min()),
        "min": float(a.min()),
        "max": float(a.max()),
    }


def _collect(case_records: list[dict]) -> dict:
    """Aggregate (case, mode) metric vectors across all audit rows.

    ``case_records``: list of {seed, N (opt), per_mode} rows.
    Returns {mode: {d_L: [...], eta_0.8: {D: [...], R: [...], S: [...]}, ...}}.
    """
    out: dict = {}
    for rec in case_records:
        rows = rec["rows"] if "rows" in rec else {"single": rec}
        for row in rows.values():
            for topo, g in row.get("per_mode", {}).items():
                slot = out.setdefault(str(topo), {"d_L": [], "meta": []})
                slot["d_L"].append(g["d_L"])
                slot["meta"].append(row.get("N", rec["seed"]))
                for key, eg in g["per_eta"].items():
                    slot.setdefault(key, {"D": [], "R": [], "S": []})
                    slot[key]["D"].append(eg["D"])
                    slot[key]["R"].append(eg["R"])
                    slot[key]["S"].append(eg["S"])
    return out


def stability_block(records: list[dict]) -> dict:
    """Per-case stability block: metric stats + relative MAD vs d_L."""
    collected = _collect(records)
    block: dict = {}
    for topo, slot in collected.items():
        dL = _stats(slot["d_L"])
        metrics = {"d_L": dL}
        for key in sorted(slot):
            if key == "d_L" or key == "meta":
                continue
            for mname in ("D", "R", "S"):
                st = _stats(slot[key][mname])
                metrics[f"{key}_{mname}"] = st
        # relative MAD of D vs d_L (set-valued vs point stability)
        for key in ("eta_0.5", "eta_0.8", "eta_0.9"):
            dD = metrics.get(f"{key}_D", {}).get("mad")
            dL_mad = dL.get("mad", 0.0)
            metrics[f"{key}_D_vs_dL_MAD_ratio"] = (
                float(dD / dL_mad) if dL_mad and dD is not None else None
            )
        block[str(topo)] = metrics
    return block


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
def eval_gates(records_all: dict) -> dict:
    """``records_all``: {case_id: list of row records (flat, seed x N)}."""
    gates: dict = {}

    # ---- Gate A: synthetic B, S2 -----------------------------------------
    b_rows = records_all.get("B_synthetic_curvature_beta_kappa", [])
    b_s2 = []
    for rec in b_rows:
        for topo, g in rec["per_mode"].items():
            if topo == "S2":
                b_s2.append(g)
    if not b_s2:
        gates["gate_a"] = {"pass": False, "error": "no B/S2 rows"}
    else:
        D_list = [g["per_eta"]["eta_0.8"]["D"] for g in b_s2]
        align_list = [g["per_eta"]["eta_0.8"]["align_xL"] for g in b_s2]
        dL_list = [g["d_L"] for g in b_s2]
        pass_a = all(d > 0.0 for d in D_list) and np.mean(align_list) > 0.5
        gates["gate_a"] = {
            "pass": bool(pass_a),
            "evidence": {
                "D_0.8_per_seed": D_list,
                "align_xL_per_seed": align_list,
                "d_L_per_seed": dL_list,
                "frozen_dL_reference": FROZEN_B_SEP,
                "mean_D_0.8": float(np.mean(D_list)),
                "min_D_0.8": float(np.min(D_list)),
                "mean_align_xL": float(np.mean(align_list)),
            },
        }

    # ---- Gate B: real C1 stability of D/R/S vs d_L ------------------------
    c1_rows = records_all.get("C1_sanger_b1n1_wide", [])
    c1_col = _collect(c1_rows)
    if not c1_col:
        gates["gate_b"] = {"pass": False, "error": "no C1 rows"}
    else:
        # concatenate across all modes (single-mode case)
        dL_all = [v for slot in c1_col.values() for v in slot["d_L"]]
        D_all = [v for slot in c1_col.values()
                 for v in slot["eta_0.8"]["D"]]
        R_all = [v for slot in c1_col.values()
                 for v in slot["eta_0.8"]["R"]]
        S_all = [v for slot in c1_col.values()
                 for v in slot["eta_0.8"]["S"]]
        st_dL = _stats(dL_all)
        st_D = _stats(D_all)
        st_R = _stats(R_all)
        st_S = _stats(S_all)
        pass_b = (
            st_D["mad"] <= st_dL["mad"]
            and st_D["mean"] <= 0.15
            and st_D["mad"] <= 0.15
            and st_R["mean"] >= 0.25
        )
        gates["gate_b"] = {
            "pass": bool(pass_b),
            "evidence": {
                "d_L": st_dL, "D_0.8": st_D, "R_0.8": st_R, "S_0.8": st_S,
                "MAD_ratio_D_vs_dL": (
                    float(st_D["mad"] / st_dL["mad"])
                    if st_dL["mad"] > 0 else None
                ),
            },
        }

    # ---- Gate C: cross-eta regime consistency -----------------------------
    inconsistent: list[dict] = []
    per_case_consistent: dict = {}
    for case_id, rows in records_all.items():
        bad = 0
        total = 0
        for rec in rows:
            rows_dict = rec["rows"] if "rows" in rec else {"single": rec}
            for row in rows_dict.values():
                for topo, g in row.get("per_mode", {}).items():
                    total += 1
                    labels = [regime_label(g["per_eta"][f"eta_{e}"], g["d_L"])
                              for e in ETAS]
                    if len(set(labels)) != 1:
                        bad += 1
                        inconsistent.append({
                            "case": case_id, "seed": rec["seed"],
                            "N": row.get("N"), "mode": topo,
                            "labels": labels,
                        })
        per_case_consistent[case_id] = {
            "consistent_rows": total - bad, "total_rows": total,
        }
    gates["gate_c"] = {
        "pass": bool(bad == 0),
        "evidence": {
            "per_case": per_case_consistent,
            "n_inconsistent": bad,
            "inconsistent": inconsistent[:20],
        },
    }
    return gates


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def make_figures(records_all: dict, out_dir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    cmap = "viridis"
    pools = _load_pools(out_dir / "h3_3a_region_pools_v1.npz")

    # ---- Fig 1: B vs C1 variance-critical region (eta = 0.8) --------------
    # B: seed 2120 (frozen-style row), full synthetic sizes; C1: seed 2120, N=2048
    b_rows = records_all.get("B_synthetic_curvature_beta_kappa", [])
    c1_rows = records_all.get("C1_sanger_b1n1_wide", [])
    b_rec = next((r for r in b_rows if r["seed"] == 2120), None)
    c1_rec = next((r for r in c1_rows if r["seed"] == 2120), None)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.3))
    panels = [
        ("B (synthetic curved) — S2", b_rec, "S2", None),
        ("C1 (Sanger B1N1, N=2048)", c1_rec, None, "N2048"),
    ]
    for ax, (title, rec, mode, Nkey) in zip(axes, panels):
        if rec is None:
            ax.text(0.5, 0.5, "not run", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(title, fontsize=9)
            continue
        if Nkey is None:
            g = rec["per_mode"][mode]
            pool = pools.get(f"B_synthetic_curvature_beta_kappa|{mode}")
        else:
            row = rec["rows"][Nkey]
            mode = next(iter(row["per_mode"]))
            g = row["per_mode"][mode]
            pool = pools.get(f"C1_sanger_b1n1_wide|{mode}")
        x_star = np.asarray(g["x_star"])
        x_L = np.asarray(g["x_L"])
        eg = g["per_eta"]["eta_0.8"]
        m_eta = np.asarray(eg["m_eta"])

        # point cloud coloured by leakage density, region highlighted
        if pool is not None:
            z = pool["z"][:, :2]
            rho = pool["rho"]
            reg = pool["region_main"].astype(bool)
            sc = ax.scatter(z[~reg, 0], z[~reg, 1], c=rho[~reg], s=4,
                            cmap=cmap, alpha=0.45)
            ax.scatter(z[reg, 0], z[reg, 1], s=7, facecolor="none",
                       edgecolor="k", linewidths=0.35, alpha=0.8,
                       label=f"L_0.8 ({eg['n_points']} pts)")
            fig.colorbar(sc, ax=ax, label=r"$\rho_L$", fraction=0.046,
                         pad=0.03)
        ax.axhline(0, color="0.7", lw=0.6)
        ax.axvline(0, color="0.7", lw=0.6)
        ax.plot(x_star[0], x_star[1], "o", color="white", ms=11, mec="k",
                label="x* (MPP)")
        ax.plot(x_L[0], x_L[1], "P", color="cyan", ms=12, mec="k",
                label="x_L (point argmax)")
        ax.plot(m_eta[0], m_eta[1], "X", color="magenta", ms=12, mec="k",
                label="m_η (region mean)")
        th = np.linspace(0, 2 * np.pi, 200)
        ax.plot(m_eta[0] + eg["R"] * np.cos(th),
                m_eta[1] + eg["R"] * np.sin(th),
                color="magenta", ls="--", lw=1.2, alpha=0.8,
                label=f"R_η = {eg['R']:.2f}")
        ax.annotate("", xy=(m_eta[0], m_eta[1]), xytext=(x_star[0], x_star[1]),
                    arrowprops=dict(arrowstyle="->", color="0.35", lw=1.0,
                                    alpha=0.9))
        ax.set_title(
            f"{title}\n"
            f"d_L={g['d_L']:.3f}  D_η={eg['D']:.3f}  R_η={eg['R']:.3f}  "
            f"S_η={eg['S']:.3f}  align={eg['align_xL']:.2f}\n"
            f"region pts={eg['n_points']}/{g['n_pool']}  "
            f"mass={eg['mass']:.2f}",
            fontsize=9,
        )
        ax.set_xlabel("z1")
        ax.set_ylabel("z2")
        ax.legend(fontsize=7, loc="best")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-2.5, 3.5)
        ax.set_ylim(-2.0, 3.0)
    fig.suptitle("Fig 10 — variance-critical region L_0.8: sharp peak (B) vs "
                 "diffuse plateau (C1)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    f1 = out_dir / "fig10_b_vs_c1_region_comparison.png"
    fig.savefig(f1, dpi=160)
    plt.close(fig)
    files.append(str(f1.relative_to(REPO)))

    # ---- Fig 2: seed/N stability of d_L vs D_0.8 / R_0.8 ------------------
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.0))

    # left: synthetic A/B across seeds
    ax = axes[0]
    syn_keys = [("A_synthetic_multi_mode_recovery", "S1"),
                ("A_synthetic_multi_mode_recovery", "S2"),
                ("B_synthetic_curvature_beta_kappa", "S1"),
                ("B_synthetic_curvature_beta_kappa", "S2")]
    groups = []
    for case_id, mode in syn_keys:
        rows = records_all.get(case_id, [])
        dL = [r["per_mode"][mode]["d_L"] for r in rows
              if mode in r["per_mode"]]
        D = [r["per_mode"][mode]["per_eta"]["eta_0.8"]["D"] for r in rows
             if mode in r["per_mode"]]
        R = [r["per_mode"][mode]["per_eta"]["eta_0.8"]["R"] for r in rows
             if mode in r["per_mode"]]
        groups.append((f"{case_id.split('_')[0]}\n{mode}", dL, D, R))
    xpos = np.arange(len(groups)) * 3.0
    w = 0.55
    for i, (label, dL, D, R) in enumerate(groups):
        xx = xpos[i]
        if dL:
            ax.boxplot(dL, positions=[xx - w], widths=0.5, showfliers=False)
        if D:
            ax.boxplot(D, positions=[xx], widths=0.5, showfliers=False,
                       patch_artist=True,
                       boxprops=dict(facecolor="#ffb3b3"))
        if R:
            ax.boxplot(R, positions=[xx + w], widths=0.5, showfliers=False,
                       patch_artist=True,
                       boxprops=dict(facecolor="#b3d4ff"))
    ax.set_xticks(xpos, [g[0] for g in groups], fontsize=7)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("z-distance")
    ax.set_title("Synthetic A/B across seeds (4) — box: d_L (plain), "
                 "D_0.8 (red), R_0.8 (blue)", fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # right: real C1/C2 across seeds × N (12 rows each)
    ax = axes[1]
    real_keys = [("C1_sanger_b1n1_wide", "SRTI_N1"),
                 ("C2_sanger_b2n_wide", "SRTI_N3")]
    groups2 = []
    for case_id, mode in real_keys:
        rows = records_all.get(case_id, [])
        dL, D, R = [], [], []
        for rec in rows:
            for Nkey in ("N128", "N512", "N2048"):
                pm = rec["rows"][Nkey]["per_mode"]
                if mode not in pm:
                    continue
                g = pm[mode]
                dL.append(g["d_L"])
                D.append(g["per_eta"]["eta_0.8"]["D"])
                R.append(g["per_eta"]["eta_0.8"]["R"])
        groups2.append((case_id.split("_")[0], dL, D, R))
    xpos2 = np.arange(len(groups2)) * 3.0
    for i, (label, dL, D, R) in enumerate(groups2):
        xx = xpos2[i]
        if dL:
            ax.boxplot(dL, positions=[xx - w], widths=0.55, showfliers=False)
        if D:
            ax.boxplot(D, positions=[xx], widths=0.55, showfliers=False,
                       patch_artist=True,
                       boxprops=dict(facecolor="#ffb3b3"))
        if R:
            ax.boxplot(R, positions=[xx + w], widths=0.55, showfliers=False,
                       patch_artist=True,
                       boxprops=dict(facecolor="#b3d4ff"))
        for j, (mname, vals) in enumerate(
                [("d_L", dL), ("D_0.8", D), ("R_0.8", R)]):
            mad = float(np.median(np.abs(np.asarray(vals)
                                         - np.median(vals))))
            ax.text(xx + (j - 1) * w, ax.get_ylim()[1] * 0.9,
                    f"MAD={mad:.3f}", ha="center", fontsize=6, color="0.25")
    ax.set_xticks(xpos2, [g[0] for g in groups2], fontsize=8)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("z-distance")
    ax.set_title("Real C1/C2 across 4 seeds × {128,512,2048} — "
                 "d_L vs D_0.8 / R_0.8", fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Fig 11 — point estimator (d_L) vs set-valued geometry "
                 "(D_0.8, R_0.8) stability", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    f2 = out_dir / "fig11_dL_vs_set_geometry_stability.png"
    fig.savefig(f2, dpi=160)
    plt.close(fig)
    files.append(str(f2.relative_to(REPO)))
    return files


# ---------------------------------------------------------------------------
# Assembly / persistence
# ---------------------------------------------------------------------------
def _flatten(records: dict) -> dict:
    """Records -> JSON-safe dict {case: {seed: row}}."""
    out: dict = {}
    for case_id, recs in records.items():
        case_out: dict = {}
        for rec in recs:
            if "rows" in rec:
                case_out[f"seed_{rec['seed']}"] = rec["rows"]
            else:
                case_out[f"seed_{rec['seed']}"] = {
                    "single": {"N": None, "per_mode": rec["per_mode"],
                               "p_mc": rec["p_mc"]}
                }
        out[case_id] = case_out
    return out


def build_dataset(records: dict, gates: dict, wall_s: float) -> dict:
    reg_summary: dict = {}
    for case_id, recs in records.items():
        case_reg: dict = {}
        for rec in recs:
            rows = rec["rows"] if "rows" in rec else {"single": rec}
            for row in rows.values():
                for topo, g in row.get("per_mode", {}).items():
                    labels = [regime_label(g["per_eta"][f"eta_{e}"], g["d_L"])
                              for e in ETAS]
                    n_tag = row.get("N") if "N" in row else "frozen"
                    key = f"{topo}@seed{rec['seed']}@N{n_tag}"
                    case_reg[key] = {"labels": labels,
                                     "consistent": len(set(labels)) == 1}
        reg_summary[case_id] = case_reg
    return {
        "schema_version": "h3-3a-set-valued-geometry-v1",
        "status": "GENERATED",
        "stage": "H3-3A",
        "date": "2026-08-21",
        "frozen_reuse": {
            "h3_2_dataset": "tests/data/h3_2_leakage_point_dataset_v1.json",
            "ml_b1_snapshot": "ml-b1-first-order-geometry-v1",
            "seed_scheme": "fixed seeds {1, 2120, 3, 4}",
            "real_workers": WORKERS,
        },
        "config": {
            "etas": ETAS,
            "eta_main": ETA_MAIN,
            "seeds": SEEDS,
            "N_audit_real": N_AUDIT,
            "eps": EPS,
            "tol": {"TOL_D": TOL_D, "TOL_S": TOL_S, "TOL_R": TOL_R},
            "synthetic_sample_sizes": {"mc": N_SYNTH_MC, "is": N_SYNTH_IS},
        },
        "per_case": _flatten(records),
        "stability": {cid: stability_block(recs)
                      for cid, recs in records.items()},
        "regime_summary": reg_summary,
        "gates": gates,
        "total_wall_seconds": round(wall_s, 1),
    }


def _load_existing_records(path: Path) -> dict:
    """Merge already-completed seeds from an existing result JSON.

    Format mirrors ``_flatten``'s output: {case: {seed_N: {single|N*}}}.
    Synthetic rows are reconstructed as flat recs; real rows keep their
    N-prefix dicts.  Used so that a later ``--only real`` / ``--only all``
    run does not lose the cheap synthetic records, and real trajectories
    are never re-labelled.
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    records: dict = {}
    for case_id, seed_map in data.get("per_case", {}).items():
        recs: list[dict] = []
        for seed_key, rows in seed_map.items():
            try:
                seed = int(str(seed_key).split("_")[1])
            except (IndexError, ValueError):
                continue
            if "single" in rows:
                recs.append({
                    "seed": seed,
                    "p_mc": rows["single"].get("p_mc"),
                    "n_mc": rows["single"].get("n_mc"),
                    "n_is": rows["single"].get("n_is"),
                    "per_mode": rows["single"].get("per_mode", {}),
                })
            else:
                recs.append({"seed": seed, "rows": rows})
        if recs:
            records[case_id] = recs
    return records


def _load_pools(path: Path) -> dict:
    """Load persisted main-row candidate pools {case|mode: {z,rho,wV,reg}}."""
    if not path.exists():
        return {}
    zf = np.load(path)
    pools: dict = {}
    tags = {k.rsplit("|", 1)[0] for k in zf.files if k.endswith("|z")}
    for tag in sorted(tags):
        pools[tag] = {
            "z": zf[f"{tag}|z"],
            "source": zf[f"{tag}|src"],
            "rho": zf[f"{tag}|rho"],
            "wV": zf[f"{tag}|wV"],
            "region_main": zf[f"{tag}|reg"],
        }
    return pools


def _save_pools(records: dict) -> None:
    """Persist main-row candidate pools (seed 2120) as a compact npz.

    Merges with any existing npz so a partial run never drops pools of
    other cases (synthetic pools stay when a real-only run saves).
    """
    npz_path = FIG_DIR / "h3_3a_region_pools_v1.npz"
    arrays: dict = {}
    for tag, pool in _load_pools(npz_path).items():     # keep existing
        arrays[f"{tag}|z"] = pool["z"]
        arrays[f"{tag}|src"] = pool["source"]
        arrays[f"{tag}|rho"] = pool["rho"]
        arrays[f"{tag}|wV"] = pool["wV"]
        arrays[f"{tag}|reg"] = pool["region_main"]
    for cid, recs in records.items():
        for rec in recs:
            if rec.get("seed") != 2120 or "_pool" not in rec:
                continue
            for topo, pool in rec["_pool"].items():
                tag = f"{cid}|{topo}"
                arrays[f"{tag}|z"] = pool["z"]
                arrays[f"{tag}|src"] = pool["source"]
                arrays[f"{tag}|rho"] = pool["rho"]
                arrays[f"{tag}|wV"] = pool["wV"]
                arrays[f"{tag}|reg"] = pool["region_main"]
    if arrays:
        np.savez_compressed(npz_path, **arrays)
        print(f"[pools] saved {len(arrays)} arrays to "
              f"h3_3a_region_pools_v1.npz", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="H3-3A set-valued geometry")
    parser.add_argument("--only", choices=["synthetic", "real", "all"],
                        default="all")
    args = parser.parse_args()
    t0 = time.perf_counter()
    mlb1 = json.loads(MLB1_PATH.read_text(encoding="utf-8"))
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # resume: merge already-completed seeds so a partial run never loses
    # cheap synthetic rows, and real trajectories are not re-labelled.
    records: dict = _load_existing_records(OUT_JSON)
    for cfg in CASES:
        cid = cfg["experiment_id"]
        kind = cfg["kind"]
        if args.only == "real" and kind.startswith("synthetic"):
            continue
        if args.only == "synthetic" and kind == "real_sanger":
            continue
        recs: list[dict] = list(records.get(cid, []))
        done = {r["seed"] for r in recs}
        for seed in SEEDS:
            if seed in done:
                print(f"[{cid}] seed={seed} reused", flush=True)
                continue
            t1 = time.perf_counter()
            print(f"[{cid}] seed={seed} start", flush=True)
            keep_pool = seed == 2120 and (
                kind.startswith("synthetic") or kind == "real_sanger"
            )
            if kind.startswith("synthetic"):
                rec = audit_synthetic(cfg, seed, keep_pool=keep_pool)
            else:
                rec = audit_real(cfg, mlb1, seed, keep_pool=keep_pool)
            recs.append(rec)
            # progress line
            if kind.startswith("synthetic"):
                modes = {t: g["d_L"] for t, g in rec["per_mode"].items()}
                print(f"  done: p_mc={rec['p_mc']:.4f} d_L={modes} "
                      f"[{time.perf_counter()-t1:.0f}s]", flush=True)
            else:
                line = []
                for Nkey in ("N128", "N512", "N2048"):
                    pm = rec["rows"][Nkey]["per_mode"]
                    ds = {t: round(g["d_L"], 3) for t, g in pm.items()}
                    line.append(f"{Nkey}(d_L={ds})")
                print(f"  done: {' | '.join(line)} "
                      f"[{time.perf_counter()-t1:.0f}s]", flush=True)
        records[cid] = recs
        # incremental persist
        gates_tmp = eval_gates(records)
        OUT_JSON.write_text(
            json.dumps(build_dataset(records, gates_tmp,
                                     time.perf_counter() - t0),
                       indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[{cid}] persisted ({len(recs)} seeds)", flush=True)

    gates = eval_gates(records)
    dataset = build_dataset(records, gates, time.perf_counter() - t0)
    OUT_JSON.write_text(
        json.dumps(dataset, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _save_pools(records)
    fig_files = make_figures(records, FIG_DIR)

    print("\n=== GATES ===")
    print(json.dumps(gates, indent=1, ensure_ascii=False))
    print("\n=== REGIME SUMMARY (main eta=0.8, seed 2120, N=2048/frozen) ===")
    for cid, recs in records.items():
        for rec in recs:
            if rec["seed"] != 2120:
                continue
            rows = rec["rows"] if "rows" in rec else {"single": rec}
            for row in rows.values():
                if row.get("N") not in (None, 2048):
                    continue
                for topo, g in row.get("per_mode", {}).items():
                    lab = {f"eta_{e}": regime_label(g["per_eta"][f"eta_{e}"],
                                                    g["d_L"])
                           for e in ETAS}
                    print(f"  {cid} [{topo}] {lab}")
    print(f"\nfigures: {fig_files}")
    print(f"total wall time: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
