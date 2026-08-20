"""H3-2 -- Variance-optimal leakage-point adaptive Geometry-IS (deterministic).

Central hypothesis: probability design points (MPP, ``argmin ||x||``) and
variance leakage points (``x_L = argmax rho_L``, ``rho_L = phi^2/q``;
Gaussian ``x_L = argmin ||x + mu||``) are different objects.  For curved
boundaries (``beta*kappa > 1``) they separate.

Experiments:

- A. Synthetic multi-mode recovery (H3-1 failure case, linear modes)
- B. Synthetic curvature stress (curved secondary mode, beta*kappa > 1)
- C. Real hybrid (Sanger, wide alpha) -- search for x* != x_L

Stage B ablation (mandatory):

- M1 single Geometry-IS (center = x*, the global MPP / ML-B1 design point)
- M2 topology-aware mixture (each class centered at its own MPP x_k*)
- M3 leakage-point adaptive mixture (each component at x_{L,k})

Metrics: VRF / M2 (total leak) / leak_fraction / coverage / point distance.

Frozen-code reuse (read-only): run_exact_topology + ML-B1 snapshot.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.uncertainty.adaptive_geometry_is import (
    GaussianMixture,
    hybrid_power_weights,
    leakage_power_weights,
    mixture_importance_weights,
    per_mode_ess,
    weight_strategies,
)
from hyptraj.uncertainty.leakage_point_geometry import (
    leakage_density,
    mpp,
    point_geometry,
)
from hyptraj.uncertainty.topology_margin import (
    DEFAULT_MAX_TIME,
    S_A,
    run_exact_topology,
)
from hyptraj.uncertainty.variance_leakage import (
    decompose_modes,
    design_point,
    effective_sample_size,
    importance_estimator,
    importance_weights,
    mc_estimator,
    total_leakage,
    vrf,
)

REPO = Path(__file__).resolve().parents[1]
DATASET_OUT = REPO / "tests" / "data" / "h3_2_leakage_point_dataset_v1.json"
FIG_DIR = REPO / "results" / "phase_h3"
MLB1_PATH = REPO / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"

SEED = 2026
SOLVER = "REF-0.1"
NOMINAL = "S0"
N_SYNTH = 200_000          # synthetic estimator samples
N_SYNTH_MC = 50_000        # synthetic MC exploration for P_k and point sets
N_REAL = 128               # real estimator samples per pass
N_EXPLORE = 128            # real MC exploration
STRATEGY_M3 = ("probability", "leak_power1", "p05_l05")


# ---------------------------------------------------------------------------
# Synthetic label functions
# ---------------------------------------------------------------------------
def label_linear(u: np.ndarray) -> str:
    u1 = u[0]
    if u1 < -1.5:
        return "S1"
    if u1 > 2.5:
        return "S2"
    return NOMINAL


def label_curved(u: np.ndarray) -> str:
    u1, u2 = u[0], u[1]
    if u1 < -1.5:
        return "S1"
    if u1 > 1.0 + 0.5 * (u2 - 1.5) ** 2:   # curved boundary, vertex at u2 = 1.5
        return "S2"
    return NOMINAL


def _antithetic(rng, mean, n):
    mean = np.asarray(mean, dtype=float)
    half = n // 2
    r = rng.standard_normal((half, mean.size))
    return np.vstack([mean + r, mean - r])


def _real_labels(x0_list, env, vehicle, K):
    labels = []
    for x0 in x0_list:
        try:
            info, _ = run_exact_topology(
                x0, env=env, vehicle=vehicle, K=K,
                solver_label=SOLVER, max_time=DEFAULT_MAX_TIME,
            )
            labels.append(info.regime)
        except Exception:
            labels.append(NOMINAL)
    return np.array(labels)


def _eval_proposal(z_q, w_q, labels_q, nominal, alpha_dir, p_k_mc, p_total_mc, channel):
    ind = labels_q != nominal
    p, var = importance_estimator(w_q, ind)
    leak = total_leakage(w_q, ind)
    modes = decompose_modes(
        z_q, w_q, labels_q, nominal, alpha_dir, np.zeros_like(alpha_dir),
        p_k_mc=p_k_mc, p_total_mc=p_total_mc, transition_channel=channel,
    )
    return {
        "p": p, "var": var, "ess": effective_sample_size(w_q),
        "total_leak": leak, "accepted": int(ind.sum()), "modes": modes,
        "mode_ess": per_mode_ess(z_q, w_q, labels_q, nominal),
    }


# ---------------------------------------------------------------------------
# Per-experiment runner (shared synthetic/real skeleton)
# ---------------------------------------------------------------------------
def run_experiment(exp_cfg: dict, mlb1: dict | None = None) -> dict:
    eid = exp_cfg["experiment_id"]
    kind = exp_cfg["kind"]
    rng = np.random.default_rng(SEED + hash(eid) % 1000)
    d = 4

    if kind.startswith("synthetic"):
        label_fn = label_linear if kind == "synthetic_linear" else label_curved
        nominal = NOMINAL
        mu_base = np.array([-1.5, 0.0, 0.0, 0.0])   # ML-B1-style design point
        alpha_dir = np.array([1.0, 0.0, 0.0, 0.0])
        channel = None
        n_mc = N_SYNTH_MC
        n_is = N_SYNTH

        # exploration (MC) for P_k and per-mode point sets
        z_mc = rng.standard_normal((n_mc, d))
        labels_mc = np.array([label_fn(u) for u in z_mc])
        p_mc, var_mc = mc_estimator(labels_mc != nominal)
        unique = sorted(set(labels_mc.tolist()))
        p_k_mc = {t: float((labels_mc == t).mean()) for t in unique}
        p_total_mc = float((labels_mc != nominal).mean())

        # baseline single IS (M1)
        z_base = _antithetic(rng, mu_base, n_is)
        w_base = importance_weights(z_base, mu_base)
        labels_base = np.array([label_fn(u) for u in z_base])
        base = _eval_proposal(z_base, w_base, labels_base, nominal, alpha_dir,
                              p_k_mc, p_total_mc, channel)
        base_vrf = vrf(p_mc, var_mc, base["p"], base["var"])

        # per-mode point sets: dense 2D grid rejection sampling (synthetic
        # label functions depend only on u1/u2; u3 = u4 = 0)
        g1 = np.linspace(-8.0, 8.0, 481)
        g2 = np.linspace(-6.0, 9.0, 401)
        G1, G2 = np.meshgrid(g1, g2)
        grid_pts = np.stack(
            [G1.ravel(), G2.ravel(), np.zeros(G1.size), np.zeros(G1.size)], axis=1
        )
        grid_labels = np.array([label_fn(u) for u in grid_pts])
        mode_points: dict[str, np.ndarray] = {}
        for m in base["modes"]:
            topo = m.transition_topology
            sel = grid_labels == topo
            mode_points[topo] = grid_pts[sel]
    else:
        # ---- real Sanger -------------------------------------------------
        env = EnvironmentParams()
        vehicle = VehicleParams()
        name = exp_cfg["anchor"]
        a = mlb1["anchors"][name]
        branch = int(name[1])
        K = float(a["K"])
        center = np.array(
            [env.earth_radius + 100000.0, 0.0, 7000.0, np.deg2rad(a["gamma0_deg"])],
            dtype=float,
        )
        gd_ref = a["geometry_direction"]
        beta_ref = float(gd_ref["beta_local"])
        alpha_dir = np.asarray(gd_ref["alpha"], dtype=float)
        nominal = a["expected_regime"]
        alpha = exp_cfg["alpha_factor"] * abs(beta_ref)
        beta_eff = beta_ref / alpha
        mu_base = design_point(beta_eff, alpha_dir)
        channel = "atmosphere_exit"
        n_mc, n_is = N_EXPLORE, N_REAL

        z_mc = rng.standard_normal((n_mc, d))
        x_mc = [center + S_A @ (alpha * z) for z in z_mc]
        labels_mc = _real_labels(x_mc, env, vehicle, K)
        p_mc, var_mc = mc_estimator(labels_mc != nominal)
        unique = sorted(set(labels_mc.tolist()))
        p_k_mc = {t: float((labels_mc == t).mean()) for t in unique}
        p_total_mc = float((labels_mc != nominal).mean())

        z_base = _antithetic(rng, mu_base, n_is)
        x_base = [center + S_A @ (alpha * z) for z in z_base]
        labels_base = _real_labels(x_base, env, vehicle, K)
        w_base = importance_weights(z_base, mu_base)
        base = _eval_proposal(z_base, w_base, labels_base, nominal, alpha_dir,
                              p_k_mc, p_total_mc, channel)
        base_vrf = vrf(p_mc, var_mc, base["p"], base["var"])

        # per-mode point sets: MC points + baseline IS points
        mode_points = {}
        for m in base["modes"]:
            topo = m.transition_topology
            mask_mc = labels_mc == topo
            mask_is = labels_base == topo
            if np.any(mask_mc) or np.any(mask_is):
                mode_points[topo] = np.vstack(
                    [z_mc[mask_mc], z_base[mask_is]]
                )
            else:
                # silent mode: probe around its design point
                z_probe = _antithetic(rng, np.asarray(m.mode_design_point), 64)
                x_probe = [center + S_A @ (alpha * z) for z in z_probe]
                labels_probe = _real_labels(x_probe, env, vehicle, K)
                sel = labels_probe == topo
                mode_points[topo] = z_probe[sel] if np.any(sel) else z_probe
        alpha = exp_cfg["alpha_factor"] * abs(beta_ref)

    # ---- Stage A: point geometry (MPP vs x_L) per mode ------------------
    geo: list[dict] = []
    for m in base["modes"]:
        pts = mode_points.get(m.transition_topology)
        if pts is None or pts.shape[0] == 0:
            continue
        pg = point_geometry(pts, mu_base, m.mode_id, m.transition_topology,
                            m.coverage_score)
        geo.append({
            "mode_id": m.mode_id,
            "topology_label": m.transition_topology,
            "probability": m.probability,
            "leak": m.leak,
            "leak_fraction": m.leak_fraction,
            "coverage_score": m.coverage_score,
            "probability_design_point": list(pg.probability_design_point),
            "leakage_point": list(pg.leakage_point),
            "distance_between_points": pg.distance_between_points,
            "leakage_density": pg.leakage_density,
            "mpp_density": pg.mpp_density,
        })
    n_modes = len(base["modes"])

    # ---- Stage B: ablation ------------------------------------------------
    m1 = {"vrf": base_vrf, "total_leak": base["total_leak"],
          "p": base["p"], "var": base["var"], "ess": base["ess"]}

    m2: dict | None = None
    m3: dict = {}
    if n_modes >= 1:
        mpp_points = np.array([np.asarray(g["probability_design_point"]) for g in geo])
        leak_points = np.array([np.asarray(g["leakage_point"]) for g in geo])
        p_k = np.array([g["probability"] for g in geo])
        leak_k = np.array([g["leak"] for g in geo])

        # M2: topology mixture centered at each mode's MPP, weight = P_k
        w_p = p_k / p_k.sum() if p_k.sum() > 0 else np.full(n_modes, 1 / n_modes)
        mix2 = GaussianMixture(design_points=mpp_points, weights=w_p)
        z2 = mix2.sample(rng, n_is)
        if kind.startswith("synthetic"):
            labels2 = np.array([label_fn(u) for u in z2])
        else:
            x2 = [center + S_A @ (alpha * z) for z in z2]
            labels2 = _real_labels(x2, env, vehicle, K)
        w2 = mixture_importance_weights(z2, mix2)
        res2 = _eval_proposal(z2, w2, labels2, nominal, alpha_dir,
                              p_k_mc, p_total_mc, channel)
        m2 = {"vrf": vrf(p_mc, var_mc, res2["p"], res2["var"]),
              "total_leak": res2["total_leak"], "p": res2["p"],
              "var": res2["var"], "ess": res2["ess"]}

        # M3: leakage-point mixture, weight strategies
        strategies = {"probability": w_p,
                      "leak_power1": leakage_power_weights(leak_k, alpha=1.0),
                      "p05_l05": hybrid_power_weights(p_k, leak_k, gamma=0.5)}
        for sname, wts in strategies.items():
            if sname not in STRATEGY_M3 and kind.startswith("real"):
                continue
            mix3 = GaussianMixture(design_points=leak_points, weights=wts)
            z3 = mix3.sample(rng, n_is)
            if kind.startswith("synthetic"):
                labels3 = np.array([label_fn(u) for u in z3])
            else:
                x3 = [center + S_A @ (alpha * z) for z in z3]
                labels3 = _real_labels(x3, env, vehicle, K)
            w3 = mixture_importance_weights(z3, mix3)
            res3 = _eval_proposal(z3, w3, labels3, nominal, alpha_dir,
                                  p_k_mc, p_total_mc, channel)
            m3[sname] = {"vrf": vrf(p_mc, var_mc, res3["p"], res3["var"]),
                         "total_leak": res3["total_leak"], "p": res3["p"],
                         "var": res3["var"], "ess": res3["ess"]}

    best_m3 = min(m3.values(), key=lambda r: r["var"]) if m3 else None
    leak_red = (
        best_m3["total_leak"] / base["total_leak"]
        if best_m3 and base["total_leak"] > 0 else None
    )
    return {
        "experiment_id": eid,
        "kind": kind,
        "anchor": exp_cfg.get("anchor"),
        "alpha": exp_cfg.get("alpha_factor"),
        "nominal_topology": nominal,
        "p_mc": p_mc,
        "var_mc": var_mc,
        "point_geometry": geo,
        "n_modes": n_modes,
        "baseline_m1": m1,
        "topology_mixture_m2": m2,
        "leakage_point_m3": m3,
        "best_m3_strategy": min(m3, key=lambda s: m3[s]["var"]) if m3 else None,
        "leakage_reduction": leak_red,
        "mpp_xl_separation": {
            g["topology_label"]: g["distance_between_points"] for g in geo
        },
    }


def make_figures(experiments: list[dict], out_dir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    # Fig 1: probability vs variance geometry points
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for e in experiments:
        for g in e["point_geometry"]:
            xs = np.asarray(g["probability_design_point"])
            xl = np.asarray(g["leakage_point"])
            ax.plot([xs[0], xl[0]], [xs[1], xl[1]], "-o", ms=5,
                    label=f"{e['experiment_id']} {g['topology_label']}")
    ax.axhline(0, color="k", lw=0.6)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel("z1")
    ax.set_ylabel("z2")
    ax.set_title("Fig 1: probability design point (o) vs leakage point (arrowhead)")
    ax.legend(fontsize=6)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    f = out_dir / "fig6_probability_vs_variance_geometry.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))

    # Fig 2: leakage density map (Exp B, 2D slice)
    exp_b = next((e for e in experiments if "curvature" in e["experiment_id"]), None)
    if exp_b is not None:
        from hyptraj.uncertainty.leakage_point_geometry import log_leakage_density

        mu = np.array([-1.5, 0.0, 0.0, 0.0])
        g1 = np.linspace(-6, 6, 400)
        g2 = np.linspace(-4, 7, 400)
        G1, G2 = np.meshgrid(g1, g2)
        pts = np.stack([G1.ravel(), G2.ravel(), np.zeros(G1.size), np.zeros(G1.size)], axis=1)
        inA = (pts[:, 0] < -1.5) | (pts[:, 0] > 1.5 + (pts[:, 1] - 3.0) ** 2)
        rho = np.full(pts.shape[0], np.nan)
        rho[inA] = np.exp(log_leakage_density(pts[inA], mu))
        fig, ax = plt.subplots(figsize=(6.5, 5.5))
        im = ax.pcolormesh(G1, G2, rho.reshape(G1.shape), cmap="hot", shading="auto")
        for g in exp_b["point_geometry"]:
            xs = np.asarray(g["probability_design_point"])
            xl = np.asarray(g["leakage_point"])
            ax.plot(xs[0], xs[1], "o", color="w", ms=8, mec="k")
            ax.plot(xl[0], xl[1], "P", color="cyan", ms=10, mec="k")
        ax.set_xlabel("z1")
        ax.set_ylabel("z2")
        ax.set_title("Fig 2: leakage density rho_L(z) (white o = MPP, cyan P = x_L)")
        fig.colorbar(im, ax=ax, label=r"$\rho_L$")
        fig.tight_layout()
        f = out_dir / "fig7_leakage_density_map.png"
        fig.savefig(f, dpi=160)
        plt.close(fig)
        files.append(str(f.relative_to(REPO)))

    # Fig 3: VRF comparison M1 / M2 / M3
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ids = [e["experiment_id"] for e in experiments]
    x = np.arange(len(ids))
    w = 0.27
    m1 = [e["baseline_m1"]["vrf"] for e in experiments]
    m2 = [e["topology_mixture_m2"]["vrf"] if e["topology_mixture_m2"] else np.nan for e in experiments]
    m3 = [min(v["vrf"] for v in e["leakage_point_m3"].values()) if e["leakage_point_m3"] else np.nan
          for e in experiments]
    ax.bar(x - w, m1, w, label="M1 single")
    ax.bar(x, m2, w, label="M2 topology mixture")
    ax.bar(x + w, m3, w, label="M3 leakage-point adaptive")
    ax.axhline(1.0, color="k", ls="--", lw=0.8)
    ax.set_xticks(x, ids, rotation=20, fontsize=7)
    ax.set_ylabel("VRF")
    ax.set_yscale("log")
    ax.set_title("Fig 3: VRF comparison")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    f = out_dir / "fig8_vrf_comparison.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))

    # Fig 4: leakage reduction before/after
    fig, ax = plt.subplots(figsize=(7, 4.5))
    base_leak = [e["baseline_m1"]["total_leak"] for e in experiments]
    adapt_leak = [
        min(v["total_leak"] for v in e["leakage_point_m3"].values())
        if e["leakage_point_m3"] else np.nan for e in experiments
    ]
    ax.bar(x - w, base_leak, w, label="M1 single")
    ax.bar(x + w, adapt_leak, w, label="M3 leakage-point adaptive")
    ax.set_xticks(x, ids, rotation=20, fontsize=7)
    ax.set_yscale("log")
    ax.set_ylabel(r"$\sum_k L_k$")
    ax.set_title("Fig 4: total leakage before / after adaptation")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    f = out_dir / "fig9_leakage_reduction.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="H3-2 leakage-point adaptive Geometry-IS")
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument(
        "--resume", action="store_true",
        help="reuse already-completed real experiments from an existing "
             "dataset (synthetic experiments are always recomputed)",
    )
    args = parser.parse_args()
    t0 = time.perf_counter()
    mlb1 = json.loads(MLB1_PATH.read_text(encoding="utf-8"))

    existing: dict[str, dict] = {}
    if args.resume and DATASET_OUT.exists():
        prev = json.loads(DATASET_OUT.read_text(encoding="utf-8"))
        for e in prev["experiments"]:
            if e["kind"] == "real_sanger":
                existing[e["experiment_id"]] = e
        if existing:
            print(f"[resume] reusing {sorted(existing)}", flush=True)

    cfgs = [
        {"experiment_id": "A_synthetic_multi_mode_recovery", "kind": "synthetic_linear"},
        {"experiment_id": "B_synthetic_curvature_beta_kappa", "kind": "synthetic_curved"},
    ]
    if not args.synthetic_only:
        cfgs += [
            {"experiment_id": "C1_sanger_b1n1_wide", "kind": "real_sanger",
             "anchor": "B1_N1_side", "alpha_factor": 8.0},
            {"experiment_id": "C2_sanger_b2n_wide", "kind": "real_sanger",
             "anchor": "B2_N_side", "alpha_factor": 8.0},
        ]

    experiments = []
    for cfg in cfgs:
        eid = cfg["experiment_id"]
        if eid in existing:
            experiments.append(existing[eid])
            print(f"[{eid}] reused", flush=True)
            continue
        print(f"[{eid}] start", flush=True)
        exp = run_experiment(cfg, mlb1)
        experiments.append(exp)
        best = exp["best_m3_strategy"]
        print(
            f"  done: P_mc={exp['p_mc']:.4f} modes={exp['n_modes']} "
            f"M1_vrf={exp['baseline_m1']['vrf']:.2f} "
            f"M2_vrf={(exp['topology_mixture_m2'] or {}).get('vrf', float('nan')):.2f} "
            f"M3_vrf={min(v['vrf'] for v in exp['leakage_point_m3'].values()):.2f} "
            f"best={best} leak_red={exp['leakage_reduction']:.3f} "
            f"sep={exp['mpp_xl_separation']} "
            f"[{time.perf_counter()-t0:.0f}s]",
            flush=True,
        )

    summary = {
        "n_experiments": len(experiments),
        "per_experiment": {
            e["experiment_id"]: {
                "n_modes": e["n_modes"],
                "m1_vrf": round(e["baseline_m1"]["vrf"], 3),
                "m2_vrf": round(e["topology_mixture_m2"]["vrf"], 3)
                if e["topology_mixture_m2"] else None,
                "m3_vrf": {s: round(r["vrf"], 3)
                           for s, r in e["leakage_point_m3"].items()},
                "best_m3": e["best_m3_strategy"],
                "leakage_reduction": e["leakage_reduction"],
                "mpp_xl_separation": e["mpp_xl_separation"],
            }
            for e in experiments
        },
    }
    dataset = {
        "schema_version": "h3-2-leakage-point-dataset-v1",
        "status": "GENERATED",
        "freeze_stage": "H3-2",
        "date": "2026-08-20",
        "ml_b1_snapshot": "ml-b1-first-order-geometry-v1",
        "design_space": "standardized z ~ N(0, I); rho_L = phi^2/q; x_L = argmax_A rho_L",
        "experiments": experiments,
        "summary": summary,
    }
    DATASET_OUT.write_text(
        json.dumps(dataset, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fig_files = make_figures(experiments, FIG_DIR)
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=1))
    print(f"figures: {fig_files}")
    print(f"total wall time: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
