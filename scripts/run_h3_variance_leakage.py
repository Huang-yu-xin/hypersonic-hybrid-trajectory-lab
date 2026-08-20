"""H3-1 -- Variance leakage driven Geometry-IS validation (deterministic).

Builds the H3-1 benchmark:

- L0 smooth synthetic (analytic half-space, no simulator)
- L1/L2/L3 real Sanger hybrid configs (frozen anchors x alpha factors):
  MC pass + single design-point Geometry-IS pass (N = 256 each, antithetic),
  topology mode decomposition, variance leakage, coverage, VRF, and a small
  margin batch for the config-level ``epsilon_geo``.

Outputs:
- tests/data/h3_variance_leakage_dataset_v1.json
- results/phase_h3/fig1_*.png .. fig4_*.png

Frozen-code reuse (read-only): run_exact_topology, evaluate_topology_margin,
ML-B1 snapshot geometry.  Nothing is modified.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.uncertainty.topology_margin import (
    CHANNEL_ATMOSPHERE_EXIT,
    DEFAULT_MAX_TIME,
    S_A,
    MarginClassification,
    evaluate_topology_margin,
    run_exact_topology,
)
from hyptraj.uncertainty.variance_leakage import (
    ConfigResult,
    ModeLeakage,
    correlation_analysis,
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
DATASET_OUT = REPO / "tests" / "data" / "h3_variance_leakage_dataset_v1.json"
FIG_DIR = REPO / "results" / "phase_h3"
MLB1_PATH = REPO / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"

SEED = 2026
N_PAIRS = 128          # antithetic pairs -> 2 * N_PAIRS samples per estimator
N_GEO = 16             # margin batch for the config-level epsilon_geo
SOLVER = "REF-0.1"
NOMINAL = "nominal"
STATUS_VOCAB = ("COMPLETE", "MAX_TIME_TERMINATED", "NONPHYSICAL", "FAILED")

CONFIGS = [
    {"config_id": "L0_smooth_synthetic", "level": "L0", "anchor": None, "synthetic_kind": "single"},
    {"config_id": "L1_B0_N_side", "level": "L1", "anchor": "B0_N_side", "alpha_factor": 2.0},
    {"config_id": "L2_synthetic_multi_mode", "level": "L2", "anchor": None, "synthetic_kind": "multi_mode"},
    {"config_id": "L2_B1_N1_side", "level": "L2", "anchor": "B1_N1_side", "alpha_factor": 3.0},
    {"config_id": "L2_B2_N_side", "level": "L2", "anchor": "B2_N_side", "alpha_factor": 4.0},
    {"config_id": "L3_B2_N1_side", "level": "L3", "anchor": "B2_N1_side", "alpha_factor": 2.0},
]


def _antithetic_gaussian(rng: np.random.Generator, mean: np.ndarray, n: int) -> np.ndarray:
    """``n`` antithetic samples around ``mean`` (n must be even)."""
    mean = np.asarray(mean, dtype=float)
    d = mean.size
    half = n // 2
    r = rng.standard_normal((half, d))
    return np.vstack([mean + r, mean - r])


def _topology_series(
    x0_list: list[np.ndarray], env, vehicle, K: float,
) -> tuple[list[str], list[str], list[str], int]:
    """Exact topology labels / statuses / terminal states for a batch."""
    labels: list[str] = []
    statuses: list[str] = []
    terminals: list[str] = []
    failures = 0
    for x0 in x0_list:
        try:
            info, traj = run_exact_topology(
                x0, env=env, vehicle=vehicle, K=K,
                solver_label=SOLVER, max_time=DEFAULT_MAX_TIME,
            )
            labels.append(info.regime)
            statuses.append("COMPLETE" if info.success else "MAX_TIME_TERMINATED")
            terminals.append(info.terminal_kind)
        except Exception:
            failures += 1
            labels.append(NOMINAL)  # unclassified -> treated as non-event
            statuses.append("FAILED")
            terminals.append("solver_failure")
    return labels, statuses, terminals, failures


def _mode_dict(m: ModeLeakage) -> dict:
    return {
        "mode_id": m.mode_id,
        "mode_index": m.mode_index,
        "transition_topology": m.transition_topology,
        "transition_channel": m.transition_channel,
        "mode_probability": m.probability,
        "conditional_probability": m.conditional_probability,
        "mode_beta": m.mode_beta,
        "mode_design_point": list(m.mode_design_point),
        "mode_direction": list(m.mode_direction),
        "proposal_density": m.proposal_density,
        "leak_k": m.leak,
        "leak_fraction": m.leak_fraction,
        "coverage_score": m.coverage_score,
        "n_events": m.n_events,
    }


def _config_dict(c: ConfigResult) -> dict:
    d = {
        "config_id": c.config_id,
        "level": c.level,
        "anchor": c.anchor,
        "alpha": c.alpha,
        "nominal_topology": c.nominal_topology,
        "beta_eff": c.beta_eff,
        "design_point": list(c.design_point),
        "epsilon_geo": c.epsilon_geo,
        "n_mc": c.n_mc,
        "n_is": c.n_is,
        "p_mc": c.p_mc,
        "p_is": c.p_is,
        "var_mc": c.var_mc,
        "var_is": c.var_is,
        "ess": c.ess,
        "vrf": c.vrf,
        "total_leak": c.total_leak,
        "accepted_rare_events": c.accepted_rare_events,
        "modes": [_mode_dict(m) for m in c.modes],
    }
    if hasattr(c, "analytic_leak"):
        d["analytic_leak"] = c.analytic_leak
    if hasattr(c, "analytic_leak_s1"):
        d["analytic_leak_s1"] = c.analytic_leak_s1
    if hasattr(c, "analytic_leak_s2"):
        d["analytic_leak_s2"] = c.analytic_leak_s2
    return d


def run_synthetic_l0() -> ConfigResult:
    """L0: analytic half-space in z-space (dim 4, beta_eff = 2.0).

    Z(z) = S1 iff z[0] < -2, else S0 (linear boundary -> epsilon_geo = 0).
    Proposal q = N(z*, I), z* = (2, 0, 0, 0); theory: leak < phi-mode, VRF high.
    """
    from scipy.integrate import quad

    d = 4
    beta_eff = 2.0
    alpha_dir = np.zeros(d)
    alpha_dir[0] = 1.0
    z_star = design_point(beta_eff, alpha_dir)
    rng = np.random.default_rng(SEED)

    def label_of(z: np.ndarray) -> str:
        return "S1" if z[0] < -beta_eff else "S0"

    z_mc = _antithetic_gaussian(rng, np.zeros(d), 2 * N_PAIRS)
    labels_mc = np.array([label_of(z) for z in z_mc])
    z_is = _antithetic_gaussian(rng, z_star, 2 * N_PAIRS)
    w_is = importance_weights(z_is, z_star)
    labels_is = np.array([label_of(z) for z in z_is])
    indicators = labels_is != "S0"

    p_mc, var_mc = mc_estimator(labels_mc != "S0")
    p_is, var_is = importance_estimator(w_is, indicators)
    ess = effective_sample_size(w_is)
    vrf_val = vrf(p_mc, var_mc, p_is, var_is)
    leak = total_leakage(w_is, indicators)
    p_k_mc = {"S1": float((labels_mc != "S0").mean())}
    modes = decompose_modes(
        z_is, w_is, labels_is, "S0", alpha_dir, z_star,
        p_k_mc=p_k_mc, p_total_mc=float((labels_mc != "S0").mean()),
        transition_channel=None,
    )
    # analytic leak (1D quadrature; other dims integrate to 1)
    analytic_leak, _ = quad(
        lambda v: (2 * np.pi) ** -0.5 * np.exp(-(v * v) + (v + beta_eff) ** 2 / 2.0),
        -np.inf, -beta_eff,
    )
    # attach the analytic value as an extra field on the serialized record
    result = ConfigResult(
        config_id="L0_smooth_synthetic",
        level="L0",
        anchor=None,
        alpha=1.0,
        nominal_topology="S0",
        beta_eff=beta_eff,
        design_point=tuple(float(v) for v in z_star),
        epsilon_geo=0.0,
        n_mc=z_mc.shape[0],
        n_is=z_is.shape[0],
        p_mc=p_mc,
        p_is=p_is,
        var_mc=var_mc,
        var_is=var_is,
        ess=ess,
        vrf=vrf_val,
        total_leak=leak,
        accepted_rare_events=int(indicators.sum()),
        modes=tuple(modes),
    )
    result.__dict__["analytic_leak"] = analytic_leak
    return result


def run_synthetic_multi_mode() -> ConfigResult:
    """L2 synthetic multi-mode: two topology modes, proposal covers one.

    A1 = {u1 < -1.5} (near, P = Phi(-1.5) ~ 0.067), A2 = {u1 > 2.5}
    (far, P = Phi(-2.5) ~ 0.0062); proposal q = N(z*, I) with z* = -1.5 e1
    covers A1 only.  A2 has small probability but huge weight -> dominant
    analytic leak (demonstrates "rare probability, large variance
    contribution").  No simulator: exact analytic leak via quadrature.
    """
    from scipy.integrate import quad

    d = 4
    beta_eff = 1.5
    alpha_dir = np.zeros(d)
    alpha_dir[0] = 1.0
    z_star = design_point(beta_eff, alpha_dir)
    n_mc = 20_000
    n_is = 200_000
    rng = np.random.default_rng(SEED + 77)

    def label_of(u: np.ndarray) -> str:
        u1 = u[0]
        if u1 < -1.5:
            return "S1"
        if u1 > 2.5:
            return "S2"
        return "S0"

    z_mc = rng.standard_normal((n_mc, d))
    labels_mc = np.array([label_of(u) for u in z_mc])
    p_mc, var_mc = mc_estimator(labels_mc != "S0")

    z_is = _antithetic_gaussian(rng, z_star, n_is)
    labels_is = np.array([label_of(u) for u in z_is])
    w_is = importance_weights(z_is, z_star)
    indicators = labels_is != "S0"
    p_is, var_is = importance_estimator(w_is, indicators)
    ess = effective_sample_size(w_is)
    vrf_val = vrf(p_mc, var_mc, p_is, var_is)
    leak = total_leakage(w_is, indicators)

    unique_mc = sorted(set(labels_mc.tolist()))
    p_k_mc = {t: float((labels_mc == t).mean()) for t in unique_mc}
    p_total_mc = float((labels_mc != "S0").mean())
    modes = decompose_modes(
        z_is, w_is, labels_is, "S0", alpha_dir, z_star,
        p_k_mc=p_k_mc, p_total_mc=p_total_mc, transition_channel=None,
    )

    def integrand(u: float) -> float:
        # (2pi)^-1/2 * exp(-u^2 + (u - z*)^2/2)  (other dims integrate to 1)
        return (2.0 * np.pi) ** -0.5 * np.exp(
            -(u * u) / 2.0 - u * z_star[0] + z_star[0] ** 2 / 2.0
        )

    analytic_a1, _ = quad(integrand, -np.inf, -1.5)
    analytic_a2, _ = quad(integrand, 2.5, np.inf)

    result = ConfigResult(
        config_id="L2_synthetic_multi_mode",
        level="L2",
        anchor=None,
        alpha=1.0,
        nominal_topology="S0",
        beta_eff=beta_eff,
        design_point=tuple(float(v) for v in z_star),
        epsilon_geo=0.0,
        n_mc=n_mc,
        n_is=n_is,
        p_mc=p_mc,
        p_is=p_is,
        var_mc=var_mc,
        var_is=var_is,
        ess=ess,
        vrf=vrf_val,
        total_leak=leak,
        accepted_rare_events=int(indicators.sum()),
        modes=tuple(modes),
    )
    result.__dict__["analytic_leak_s1"] = analytic_a1
    result.__dict__["analytic_leak_s2"] = analytic_a2
    return result


def run_simulator_config(cfg: dict, mlb1: dict) -> ConfigResult:
    env = EnvironmentParams()
    vehicle = VehicleParams()
    name = cfg["anchor"]
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
    b_ref = float(a["nominal"]["b"])
    a_ref = np.asarray(a["analytic_gradient"]["a_raw"], dtype=float)
    nominal_regime = a["expected_regime"]

    alpha = cfg["alpha_factor"] * abs(beta_ref)
    beta_eff = beta_ref / alpha          # standardized boundary distance (signed)
    z_star = design_point(beta_eff, alpha_dir)
    rng = np.random.default_rng(SEED + 1000 + CONFIGS.index(cfg))

    # ---- MC pass (target N(0,I)) ----------------------------------------
    z_mc = _antithetic_gaussian(rng, np.zeros(4), 2 * N_PAIRS)
    x_mc = [center + S_A @ (alpha * z) for z in z_mc]
    labels_mc, status_mc, term_mc, fail_mc = _topology_series(x_mc, env, vehicle, K)
    labels_mc = np.array(labels_mc)
    p_mc, var_mc = mc_estimator(labels_mc != nominal_regime)

    # ---- IS pass (proposal N(z*, I)) -------------------------------------
    z_is = _antithetic_gaussian(rng, z_star, 2 * N_PAIRS)
    x_is = [center + S_A @ (alpha * z) for z in z_is]
    labels_is, status_is, term_is, fail_is = _topology_series(x_is, env, vehicle, K)
    labels_is = np.array(labels_is)
    w_is = importance_weights(z_is, z_star)
    indicators = labels_is != nominal_regime
    p_is, var_is = importance_estimator(w_is, indicators)
    ess = effective_sample_size(w_is)
    vrf_val = vrf(p_mc, var_mc, p_is, var_is)
    leak = total_leakage(w_is, indicators)

    # ---- mode decomposition (MC marginals for P_k) ------------------------
    unique_mc = sorted(set(labels_mc.tolist()))
    p_k_mc = {t: float((labels_mc == t).mean()) for t in unique_mc}
    p_total_mc = float((labels_mc != nominal_regime).mean())
    modes = decompose_modes(
        z_is, w_is, labels_is, nominal_regime, alpha_dir, z_star,
        p_k_mc=p_k_mc, p_total_mc=p_total_mc,
        transition_channel="atmosphere_exit",
    )

    # ---- margin batch: config-level epsilon_geo ---------------------------
    eps_vals: list[float] = []
    for z in z_mc[:N_GEO]:
        x = center + S_A @ (alpha * z)
        mrec = evaluate_topology_margin(
            x, K=K, branch_index=branch, env=env, vehicle=vehicle,
            channel=CHANNEL_ATMOSPHERE_EXIT, solver_label=SOLVER,
            max_time=DEFAULT_MAX_TIME,
            expected_regime=None, expected_switch_signature=None,
            check_prior_topology=False,
        )
        if mrec.classification != MarginClassification.VALID_MARGIN:
            continue
        lin = b_ref + float(a_ref @ (S_A @ (alpha * z)))
        eps_vals.append(abs(float(mrec.b) - lin))
    eps_geo = float(np.median(eps_vals)) if eps_vals else float("nan")

    return ConfigResult(
        config_id=cfg["config_id"],
        level=cfg["level"],
        anchor=name,
        alpha=alpha,
        nominal_topology=nominal_regime,
        beta_eff=beta_eff,
        design_point=tuple(float(v) for v in z_star),
        epsilon_geo=eps_geo,
        n_mc=len(labels_mc),
        n_is=len(labels_is),
        p_mc=p_mc,
        p_is=p_is,
        var_mc=var_mc,
        var_is=var_is,
        ess=ess,
        vrf=vrf_val,
        total_leak=leak,
        accepted_rare_events=int(indicators.sum()),
        modes=tuple(modes),
    )


def make_figures(configs: list[ConfigResult], out_dir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    # Figure 1: P_k vs leak_k (log scale)
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for c in configs:
        if not c.modes:
            continue
        x = [max(m.probability, 1e-12) for m in c.modes]
        y = [max(m.leak, 1e-12) for m in c.modes]
        ax.scatter(x, y, label=c.config_id, s=60, edgecolor="k", linewidth=0.5)
        for m, xx, yy in zip(c.modes, x, y):
            ax.annotate(
                m.transition_topology, (xx, yy),
                textcoords="offset points", xytext=(4, 4), fontsize=7,
            )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$P_k$ (mode probability)")
    ax.set_ylabel(r"$\mathrm{leak}_k$")
    ax.set_title("Fig 1: topology mode probability vs variance leakage")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    f = out_dir / "fig1_topology_prob_vs_leakage.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))

    # Figure 2: epsilon_geo vs VRF
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for c in configs:
        ax.scatter(max(c.epsilon_geo, 1e-12), max(c.vrf, 1e-12), s=70,
                   edgecolor="k", linewidth=0.5)
        ax.annotate(c.config_id, (max(c.epsilon_geo, 1e-12), max(c.vrf, 1e-12)),
                    textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$\varepsilon_{\mathrm{geo}}$ (config median)")
    ax.set_ylabel("VRF")
    ax.set_title("Fig 2: geometry error vs variance reduction")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    f = out_dir / "fig2_epsilon_geo_vs_vrf.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))

    # Figure 3: secondary-mode leak_fraction vs VRF degradation
    fig, ax = plt.subplots(figsize=(6.5, 5))
    frac = []
    for c in configs:
        sec = [m.leak_fraction for m in c.modes[1:]] if len(c.modes) > 1 else []
        frac.append(sum(sec) if sec else 0.0)
    for c, fx in zip(configs, frac):
        x = max(fx, 1e-9)
        ax.scatter(x, max(c.vrf, 1e-12), s=70, edgecolor="k", linewidth=0.5)
        ax.annotate(c.config_id, (x, max(c.vrf, 1e-12)),
                    textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"secondary-mode $\mathrm{leak}_{\mathrm{frac}}$")
    ax.set_ylabel("VRF")
    ax.set_title("Fig 3: leakage fraction vs VRF degradation")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    f = out_dir / "fig3_leak_fraction_vs_vrf.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))

    # Figure 4: topology coverage map (configs x modes heatmap)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    mode_ids = sorted({m.transition_topology for c in configs for m in c.modes})
    cov = np.full((len(configs), len(mode_ids)), np.nan)
    for i, c in enumerate(configs):
        for m in c.modes:
            if m.transition_topology in mode_ids:
                v = m.coverage_score
                cov[i, mode_ids.index(m.transition_topology)] = (
                    10.0 if (v == float("inf") or v != v) else v
                )
    im = ax.imshow(cov, aspect="auto", cmap="coolwarm", vmin=0, vmax=3)
    ax.set_xticks(range(len(mode_ids)), mode_ids, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(configs)), [c.config_id for c in configs], fontsize=8)
    ax.set_title("Fig 4: proposal coverage map (Q(A_k)/Phi(A_k))")
    fig.colorbar(im, ax=ax, label="coverage score")
    fig.tight_layout()
    f = out_dir / "fig4_topology_coverage_map.png"
    fig.savefig(f, dpi=160)
    plt.close(fig)
    files.append(str(f.relative_to(REPO)))
    return files


def _config_from_dict(d: dict) -> ConfigResult:
    """Rebuild a ConfigResult from its serialized dict (used by --resume)."""
    modes = tuple(
        ModeLeakage(
            mode_index=m["mode_index"],
            mode_id=m["mode_id"],
            transition_topology=m["transition_topology"],
            transition_channel=m["transition_channel"],
            probability=m["mode_probability"],
            conditional_probability=m["conditional_probability"],
            mode_beta=m["mode_beta"],
            mode_design_point=tuple(m["mode_design_point"]),
            mode_direction=tuple(m["mode_direction"]),
            proposal_density=m["proposal_density"],
            leak=m["leak_k"],
            leak_fraction=m["leak_fraction"],
            coverage_score=m["coverage_score"],
            n_events=m["n_events"],
        )
        for m in d["modes"]
    )
    result = ConfigResult(
        config_id=d["config_id"],
        level=d["level"],
        anchor=d["anchor"],
        alpha=d["alpha"],
        nominal_topology=d["nominal_topology"],
        beta_eff=d["beta_eff"],
        design_point=tuple(d["design_point"]),
        epsilon_geo=d["epsilon_geo"],
        n_mc=d["n_mc"],
        n_is=d["n_is"],
        p_mc=d["p_mc"],
        p_is=d["p_is"],
        var_mc=d["var_mc"],
        var_is=d["var_is"],
        ess=d["ess"],
        vrf=d["vrf"],
        total_leak=d["total_leak"],
        accepted_rare_events=d["accepted_rare_events"],
        modes=modes,
    )
    for key in ("analytic_leak", "analytic_leak_s1", "analytic_leak_s2"):
        if key in d:
            result.__dict__[key] = d[key]
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="H3-1 variance leakage benchmark")
    parser.add_argument(
        "--resume", action="store_true",
        help="reuse configs already present in the dataset; recompute missing "
             "ones and regenerate figures",
    )
    args = parser.parse_args()

    t0 = time.perf_counter()
    mlb1 = json.loads(MLB1_PATH.read_text(encoding="utf-8"))

    existing: dict[str, ConfigResult] = {}
    if args.resume and DATASET_OUT.exists():
        prev = json.loads(DATASET_OUT.read_text(encoding="utf-8"))
        for c in prev["configs"]:
            existing[c["config_id"]] = _config_from_dict(c)

    configs: list[ConfigResult] = []
    for cfg in CONFIGS:
        if cfg["config_id"] in existing:
            configs.append(existing[cfg["config_id"]])
            print(f"[{cfg['config_id']}] reused", flush=True)
            continue
        print(f"[{cfg['config_id']}] start", flush=True)
        if cfg["anchor"] is None and cfg.get("synthetic_kind") == "multi_mode":
            c = run_synthetic_multi_mode()
        elif cfg["anchor"] is None:
            c = run_synthetic_l0()
        else:
            c = run_simulator_config(cfg, mlb1)
        configs.append(c)
        print(
            f"  done: P_mc={c.p_mc:.4f} P_is={c.p_is:.4f} VRF={c.vrf:.2f} "
            f"ESS={c.ess:.1f} leak={c.total_leak:.3e} eps={c.epsilon_geo:.3e} "
            f"modes={[m.transition_topology for m in c.modes]} "
            f"[{time.perf_counter()-t0:.0f}s]",
            flush=True,
        )

    corr = correlation_analysis(configs)
    n_modes = sum(len(c.modes) for c in configs)
    secondary_leak = [
        sum(m.leak_fraction for m in c.modes[1:]) if len(c.modes) > 1 else 0.0
        for c in configs
    ]
    dataset = {
        "schema_version": "h3-variance-leakage-dataset-v1",
        "status": "GENERATED",
        "freeze_stage": "H3-1",
        "date": "2026-08-20",
        "h3_schema": "h3-sample-schema-v1",
        "ml_b1_snapshot": "ml-b1-first-order-geometry-v1",
        "seed": SEED,
        "n_pairs": N_PAIRS,
        "n_samples_per_estimator": 2 * N_PAIRS,
        "design_space": "standardized z ~ N(0, I); delta_x = S_A (alpha z); q(z) = N(z*, I), z* = -beta_eff * alpha_dir",
        "configs": [_config_dict(c) for c in configs],
        "correlations": corr,
        "summary": {
            "n_configs": len(configs),
            "n_modes": n_modes,
            "secondary_leak_fractions": secondary_leak,
            "levels": [c.level for c in configs],
        },
    }
    DATASET_OUT.write_text(
        json.dumps(dataset, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fig_files = make_figures(configs, FIG_DIR)
    print("\n=== CORRELATIONS ===")
    print(json.dumps(corr, indent=1))
    print(f"\nfigures: {fig_files}")
    print(f"total wall time: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
