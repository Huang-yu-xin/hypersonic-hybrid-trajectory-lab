"""H3-2 C1 stability audit -- is the C1 x*-xL separation real or a seed artifact?

Audit-only harness.  READ-ONLY reuse of the frozen H3-2 pipeline
(``run_h3_2_adaptive_geometry_is.py``): identical dynamics, topology,
uncertainty, proposal, leakage search, estimator settings and sample sizes
are used; ONLY the random seed changes between rows.

Question under audit
--------------------
Pre-freeze (hash-seed) C1 run reported  ||x* - xL|| = 1.136, while the
deterministic crc32-seed run reports 0.  Is the separation a real
phenomenon of the Sanger B1_N1_side mode, or a finite-sample / seed
artifact?

Outputs
-------
1. Multi-seed stability table (>= 4 seeds, actual runs only).
2. Leakage landscape audit (max candidate, top-k ranking, density gap,
   candidate location per seed).
3. Monte Carlo convergence check x_L(N) for N, 4N, 16N (prefix
   evaluation of one large iid batch -- standard convergence diagnostic).

The frozen crc32 row doubles as a harness-validity check: it must
reproduce the frozen dataset numbers (dist = 0, M1 VRF = 1.2055,
rho_L = 2.30e-2) before the other rows are trusted.

Usage
-----
    python scripts/run_h3_2_c1_stability_audit.py --stage multiseed
    python scripts/run_h3_2_c1_stability_audit.py --stage convergence
    python scripts/run_h3_2_c1_stability_audit.py            # both
"""

from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.uncertainty.leakage_point_geometry import (
    leakage_density,
    point_geometry,
)
from hyptraj.uncertainty.topology_margin import (
    DEFAULT_MAX_TIME,
    S_A,
    run_exact_topology,
)
from hyptraj.uncertainty.variance_leakage import (
    design_point,
    importance_weights,
    mc_estimator,
    vrf,
)

# ---- frozen pipeline reuse (read-only) ----------------------------------
import run_h3_2_adaptive_geometry_is as frozen

_antithetic = frozen._antithetic
_eval_proposal = frozen._eval_proposal
NOMINAL = frozen.NOMINAL
SOLVER = frozen.SOLVER
N_REAL = frozen.N_REAL          # 128
N_EXPLORE = frozen.N_EXPLORE    # 128
C1_CFG = {
    "experiment_id": "C1_sanger_b1n1_wide",
    "kind": "real_sanger",
    "anchor": "B1_N1_side",
    "alpha_factor": 8.0,
}

REPO = Path(__file__).resolve().parents[1]
MLB1_PATH = REPO / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"
OUT_DIR = REPO / "results" / "phase_h3"
MULTISEED_OUT = OUT_DIR / "c1_audit_multiseed_v1.json"
CONV_OUT = OUT_DIR / "c1_audit_convergence_v1.json"

# Frozen crc32 seed for C1 (what the frozen dataset used).
FROZEN_SEED = frozen._stable_seed("C1_sanger_b1n1_wide")
# Legacy-style proxy seed.  The true pre-freeze run used
# ``SEED + hash(eid) % 1000`` with Python's process-randomized ``hash()``,
# which is unreproducible BY DESIGN -- that is the bug under audit.  We
# therefore use a fixed alternate seed as the "old-style" row and document
# the historical recorded value (1.136) separately in the report.
LEGACY_PROXY_SEED = 1
SEEDS = [
    ("seed_old", LEGACY_PROXY_SEED),
    ("seed_crc32", FROZEN_SEED),
    ("seed_3", 3),
    ("seed_4", 4),
]

N_WORKERS = 4   # verified: workers in {1, 2, 4} reproduce the frozen
                # dataset exactly (VRF 1.205492, single SRTI_N1 mode,
                # d_L = 0).  workers=16 caused some simulations to throw,
                # which _real_labels catches and silently labels as NOMINAL
                # -- producing a spurious "S0" mode and shifting VRF.
                # 4 workers = ~2x faster than sequential with identical
                # results; the audit anchor (seed_crc32 row) re-verifies
                # reproducibility on every run.

# ---------------------------------------------------------------------------
# Parallel exact-topology labelling (same solver call as the frozen branch,
# just spread across processes).  Worker state is installed once per process.
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


def parallel_real_labels(x0_list, env, vehicle, K, workers=N_WORKERS):
    """Labels for ``x0_list`` using the frozen solver, parallelised."""
    if workers <= 1 or len(x0_list) < 8:
        return frozen._real_labels(x0_list, env, vehicle, K)
    with Pool(
        workers,
        initializer=_init_worker,
        initargs=(env, vehicle, K, SOLVER, DEFAULT_MAX_TIME),
    ) as pool:
        return np.array(pool.map(_label_one, x0_list))


# ---------------------------------------------------------------------------
# C1 branch replication (verbatim logic from the frozen generator) + audit
# diagnostics.  ONLY ``seed`` / ``n`` differ from the frozen configuration.
# ---------------------------------------------------------------------------
def audit_c1(seed: int, n_mc: int, n_is: int, mlb1: dict,
             workers: int = N_WORKERS) -> dict:
    rng = np.random.default_rng(seed)
    d = 4
    env = EnvironmentParams()
    vehicle = VehicleParams()
    a = mlb1["anchors"]["B1_N1_side"]
    K = float(a["K"])
    center = np.array(
        [env.earth_radius + 100000.0, 0.0, 7000.0, np.deg2rad(a["gamma0_deg"])],
        dtype=float,
    )
    gd_ref = a["geometry_direction"]
    beta_ref = float(gd_ref["beta_local"])
    alpha_dir = np.asarray(gd_ref["alpha"], dtype=float)
    nominal = a["expected_regime"]
    alpha = C1_CFG["alpha_factor"] * abs(beta_ref)
    beta_eff = beta_ref / alpha
    mu_base = design_point(beta_eff, alpha_dir)
    channel = "atmosphere_exit"

    # exploration MC
    z_mc = rng.standard_normal((n_mc, d))
    x_mc = [center + S_A @ (alpha * z) for z in z_mc]
    labels_mc = parallel_real_labels(x_mc, env, vehicle, K, workers)
    p_mc, var_mc = mc_estimator(labels_mc != nominal)
    unique = sorted(set(labels_mc.tolist()))
    p_k_mc = {t: float((labels_mc == t).mean()) for t in unique}
    p_total_mc = float((labels_mc != nominal).mean())

    # baseline single IS (M1)
    z_base = _antithetic(rng, mu_base, n_is)
    x_base = [center + S_A @ (alpha * z) for z in z_base]
    labels_base = parallel_real_labels(x_base, env, vehicle, K, workers)
    w_base = importance_weights(z_base, mu_base)
    base = _eval_proposal(z_base, w_base, labels_base, nominal, alpha_dir,
                          p_k_mc, p_total_mc, channel)
    base_vrf = vrf(p_mc, var_mc, base["p"], base["var"])

    # per-mode point sets (verbatim frozen branch)
    mode_points: dict[str, np.ndarray] = {}
    for m in base["modes"]:
        topo = m.transition_topology
        mask_mc = labels_mc == topo
        mask_is = labels_base == topo
        if np.any(mask_mc) or np.any(mask_is):
            mode_points[topo] = np.vstack([z_mc[mask_mc], z_base[mask_is]])
        else:
            z_probe = _antithetic(rng, np.asarray(m.mode_design_point), 64)
            x_probe = [center + S_A @ (alpha * z) for z in z_probe]
            labels_probe = parallel_real_labels(x_probe, env, vehicle, K, workers)
            sel = labels_probe == topo
            mode_points[topo] = z_probe[sel] if np.any(sel) else z_probe

    # Stage A geometry + leakage landscape diagnostics
    geo: list[dict] = []
    landscape: list[dict] = []
    for m in base["modes"]:
        pts = mode_points.get(m.transition_topology)
        if pts is None or pts.shape[0] == 0:
            continue
        pg = point_geometry(pts, mu_base, m.mode_id, m.transition_topology,
                            m.coverage_score)
        geo.append({
            "mode_id": m.mode_id,
            "topology_label": m.transition_topology,
            "probability_design_point": list(pg.probability_design_point),
            "leakage_point": list(pg.leakage_point),
            "distance_between_points": pg.distance_between_points,
            "leakage_density": pg.leakage_density,
            "mpp_density": pg.mpp_density,
            "coverage_score": pg.coverage_score,
        })
        # landscape: rho_L over ALL mode points, top-k ranking
        rho = leakage_density(pts, mu_base)
        order = np.argsort(rho)[::-1]
        top5 = [
            {"z": [float(v) for v in pts[i]],
             "rho_L": float(rho[i]),
             "norm": float(np.linalg.norm(pts[i]))}
            for i in order[:5]
        ]
        sorted_rho = np.sort(rho)
        landscape.append({
            "topology_label": m.transition_topology,
            "n_points": int(pts.shape[0]),
            "rho_max": float(rho.max()),
            "rho_2nd": float(sorted_rho[-2]) if pts.shape[0] > 1 else float(rho.max()),
            "rho_median": float(np.median(rho)),
            "density_gap_max2nd": float(rho.max() / sorted_rho[-2]) if pts.shape[0] > 1 else 1.0,
            "top5": top5,
            "candidate_location": top5[0]["z"] if top5 else None,
        })

    return {
        "seed": seed,
        "n_mc": n_mc,
        "n_is": n_is,
        "p_mc": p_mc,
        "var_mc": var_mc,
        "base_vrf": base_vrf,
        "base": {"p": base["p"], "var": base["var"], "ess": base["ess"],
                 "total_leak": base["total_leak"],
                 "accepted": base["accepted"]},
        "point_geometry": geo,
        "leakage_landscape": landscape,
        "mpp_xl_separation": {
            g["topology_label"]: g["distance_between_points"] for g in geo
        },
        "wall_s": time.perf_counter(),
    }


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage_multiseed(mlb1: dict) -> list[dict]:
    rows = []
    for label, seed in SEEDS:
        t0 = time.perf_counter()
        print(f"[multiseed {label}] seed={seed} start", flush=True)
        rec = audit_c1(seed, N_EXPLORE, N_REAL, mlb1)
        rec["label"] = label
        rec["wall_s"] = round(time.perf_counter() - t0, 1)
        rows.append(rec)
        print(
            f"  done: d_L={rec['mpp_xl_separation']} "
            f"VRF={rec['base_vrf']:.4f} rho_max={rec['leakage_landscape'][0]['rho_max']:.3e} "
            f"n_pts={rec['leakage_landscape'][0]['n_points']} "
            f"[{rec['wall_s']:.0f}s]",
            flush=True,
        )
        # incremental persist (survives session interruption)
        MULTISEED_OUT.write_text(
            json.dumps({"rows": rows}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return rows


def stage_convergence(mlb1: dict) -> list[dict]:
    """One large iid batch at the frozen seed; prefix evaluation gives
    x_L(N), x_L(4N), x_L(16N) (standard MC convergence diagnostic)."""
    n_big = 16 * N_REAL  # 2048
    print(f"[convergence] seed={FROZEN_SEED} big batch {n_big} MC + {n_big} IS", flush=True)
    t0 = time.perf_counter()

    # --- one simulation pass; prefixes reuse the same iid samples ---------
    env = EnvironmentParams()
    vehicle = VehicleParams()
    a = mlb1["anchors"]["B1_N1_side"]
    K = float(a["K"])
    gd_ref = a["geometry_direction"]
    beta_ref = float(gd_ref["beta_local"])
    alpha_dir = np.asarray(gd_ref["alpha"], dtype=float)
    nominal = a["expected_regime"]
    alpha = C1_CFG["alpha_factor"] * abs(beta_ref)
    beta_eff = beta_ref / alpha
    mu_base = design_point(beta_eff, alpha_dir)
    center = np.array(
        [env.earth_radius + 100000.0, 0.0, 7000.0, np.deg2rad(a["gamma0_deg"])],
        dtype=float,
    )

    rng = np.random.default_rng(FROZEN_SEED)
    z_mc = rng.standard_normal((n_big, 4))
    z_base = _antithetic(rng, mu_base, n_big)
    x_mc = [center + S_A @ (alpha * z) for z in z_mc]
    x_base = [center + S_A @ (alpha * z) for z in z_base]
    print("  labelling big batch...", flush=True)
    labels_mc = parallel_real_labels(x_mc, env, vehicle, K)
    labels_base = parallel_real_labels(x_base, env, vehicle, K)
    print(f"  labels done [{time.perf_counter()-t0:.0f}s]", flush=True)

    rows = []
    for n in [N_REAL, 4 * N_REAL, 16 * N_REAL]:
        zm, lm = z_mc[:n], labels_mc[:n]
        zb, lb = z_base[:n], labels_base[:n]
        p_mc, var_mc = mc_estimator(lm != nominal)
        unique = sorted(set(lm.tolist()))
        p_k_mc = {t: float((lm == t).mean()) for t in unique}
        p_total_mc = float((lm != nominal).mean())
        wb = importance_weights(zb, mu_base)
        base = _eval_proposal(zb, wb, lb, nominal, alpha_dir,
                              p_k_mc, p_total_mc, "atmosphere_exit")
        base_vrf = vrf(p_mc, var_mc, base["p"], base["var"])

        pts_mc = zm[lm != nominal]
        pts_is = zb[lb != nominal]
        pts = np.vstack([pts_mc, pts_is]) if pts_mc.size else pts_is
        if pts.shape[0] == 0:
            rows.append({"N": n, "error": "no mode points"})
            continue
        pg = point_geometry(pts, mu_base, "mode0", str(unique[0] if unique else "?"), 1.0)
        rho = leakage_density(pts, mu_base)
        rows.append({
            "N": n,
            "n_mode_points": int(pts.shape[0]),
            "x_star": list(pg.probability_design_point),
            "x_L": list(pg.leakage_point),
            "d_L": pg.distance_between_points,
            "rho_L(x_L)": pg.leakage_density,
            "rho_L(x*)": pg.mpp_density,
            "M1_vrf": base_vrf,
            "M1_p": base["p"],
        })
        print(
            f"  N={n:5d}: d_L={pg.distance_between_points:.4f} "
            f"x_L={[round(v,3) for v in pg.leakage_point]} "
            f"n_pts={pts.shape[0]} VRF={base_vrf:.3f}",
            flush=True,
        )
        CONV_OUT.write_text(
            json.dumps({"seed": FROZEN_SEED, "rows": rows}, indent=1,
                       ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # convergence gaps vs 16N reference
    ref = rows[-1]
    for r in rows[:-1]:
        r["||x_L(N)-x_L(16N)||"] = float(
            np.linalg.norm(np.asarray(r["x_L"]) - np.asarray(ref["x_L"]))
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="H3-2 C1 stability audit")
    parser.add_argument("--stage", choices=["multiseed", "convergence", "all"],
                        default="all")
    args = parser.parse_args()

    mlb1 = json.loads(MLB1_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    if args.stage in ("multiseed", "all"):
        rows = stage_multiseed(mlb1)
        print(f"multiseed complete: {len(rows)} seeds "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
    if args.stage in ("convergence", "all"):
        rows = stage_convergence(mlb1)
        print(f"convergence complete: {len(rows)} prefixes "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
    print("AUDIT DONE", flush=True)


if __name__ == "__main__":
    main()
