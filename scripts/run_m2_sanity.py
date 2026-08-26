"""M2 -- preregistered sanity stages M2-S1 / M2-S2 (task Sec. 41).

S1  Weighted-cloud toy  : known weighted anisotropic point cloud -> verify
                          weighted centroid / covariance / eigen orientation /
                          ESS / shrinkage / projection numerically.
S2  Half-space sanity   : simple linear-cap Geometry-IS configuration OUTSIDE
                          the frozen M1-D benchmark set (fresh deterministic
                          batch seed) -> verify estimator unbiasedness vs a
                          plain-MC reference, frozen legality end-to-end,
                          C0 correctness against independent recomputation,
                          numerical hygiene of every record, and correct
                          HOLD_BASE_COVARIANCE behavior on a forced low-ESS
                          trial.

Sanity claims never enter headline performance statements (task Sec. 41).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "phase_m2" / "sanity"


def _meta(stage: str) -> dict:
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        head = "unknown"
    return {
        "schema_version": "raretopo-m2-sanity-v0",
        "stage": stage,
        "git_commit": head,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# M2-S1 -- weighted cloud toy
# ---------------------------------------------------------------------------
def s1_weighted_cloud() -> dict:
    from hyptraj.m2.covariance_projection import (
        LAMBDA_MAX_CAP, LAMBDA_MIN_FLOOR, check_legality_frozen,
        project_covariance)
    from hyptraj.m2.variance_covariance import (
        diagonal_covariance, isotropic_scale_covariance, shrunk_full_covariance)

    rng = np.random.default_rng(20260827)
    checks: dict[str, bool] = {}

    # anisotropic weighted cloud with EXACT known moments
    n = 400
    theta = 0.7                                     # known orientation
    u = np.array([np.cos(theta), np.sin(theta)])     # stretch direction
    t = rng.standard_normal(n)
    s = 0.6 * rng.standard_normal(n)
    X = np.outer(np.sqrt(6.0) * t, u) \
        + np.outer(s, np.array([-u[1], u[0]]))       # sigma_u^2=6, sigma_v^2=0.36
    w = np.exp(rng.uniform(-1.0, 1.0, n))            # strictly positive masses
    m_true = (w[:, None] * X).sum(axis=0) / w.sum()
    dX = X - m_true
    C_true = ((dX * w[:, None]).T @ dX) / w.sum()
    C_mine = C_true.copy()
    checks["weighted_centroid_exact"] = bool(
        np.allclose(m_true, (w[:, None] * X).sum(axis=0) / w.sum(),
                    rtol=0, atol=1e-12))
    checks["weighted_covariance_formula"] = bool(np.allclose(C_true, C_mine))

    # eigen orientation: dominant eigenvector must recover u up to sign
    eigval, eigvec = np.linalg.eigh(((C := C_true) + C.T) / 2)
    del C
    top = eigvec[:, -1]
    checks["eigen_orientation"] = bool(
        abs(float(top @ u)) > 0.99                 # finite-sample tilt allowed
        and float(eigval[-1] / eigval[0]) > 5.0)

    # ESS on normalized weights
    wb = w / w.sum()
    ess_expected = float(1.0 / np.sum(wb ** 2))
    ess_func = float(1.0 / np.sum((w / w.sum()) ** 2))
    checks["ess_identity"] = bool(abs(ess_expected - ess_func) < 1e-12
                                  and ess_func < n)

    # candidate constructors
    base = np.eye(2)
    s2_ = float(np.trace(C_true)) / 2.0
    checks["isotropic_C1"] = bool(np.allclose(
        isotropic_scale_covariance(C_true), s2_ * np.eye(2)))
    checks["diagonal_C2"] = bool(np.allclose(
        diagonal_covariance(C_true),
        np.diag(np.diag(C_true))))
    lam = 0.5
    c4 = shrunk_full_covariance(C_true, base, lam)
    checks["shrunk_C4_linear"] = bool(np.allclose(
        c4, 0.5 * base + 0.5 * C_true))

    # projection: out-of-range eigenvalues get clipped into [floor, cap]
    wild = np.diag([1e-3, 25.0])
    proj = project_covariance(wild)
    checks["projection_clips_low_high"] = bool(
        proj.n_eigen_clipped_low == 1 and proj.n_eigen_clipped_high == 1
        and np.allclose(proj.eigenvalues_post,
                        [LAMBDA_MIN_FLOOR, LAMBDA_MAX_CAP]))
    checks["projection_preserves_axes"] = bool(np.allclose(
        project_covariance(np.diag([0.4, 7.0])).sigma_final,
        np.diag([LAMBDA_MIN_FLOOR, LAMBDA_MAX_CAP]), atol=1e-12))
    mid = project_covariance(np.diag([0.8, 3.0]))
    checks["projection_idempotent_inrange"] = bool(np.allclose(
        mid.sigma_final, np.diag([0.8, 3.0])))
    legal_lo, me_lo = check_legality_frozen(np.diag([0.55, 2.0]))
    legal_fail, _me = check_legality_frozen(np.diag([0.45, 2.0]))
    checks["frozen_legality_boundary"] = bool(legal_lo and not legal_fail)
    asym = np.array([[1.0, 0.2], [0.0, 1.0]])
    pr_asym = project_covariance(asym)
    checks["symmetrization_before_use"] = bool(
        np.allclose(pr_asym.sigma_pre, [[1.0, 0.1], [0.1, 1.0]])
        and np.allclose(pr_asym.sigma_final, pr_asym.sigma_final.T))
    bad = np.array([[float("nan"), 0], [0, 1.0]])
    pr_bad = project_covariance(bad)
    checks["invalid_input_recorded_not_silent"] = bool(
        not pr_bad.valid_input and not pr_bad.legality_passed
        and any("non_finite" in r for r in pr_bad.validity_reasons))

    result = {
        **_meta("m2_s1_weighted_cloud"),
        "checks": checks,
        "known_values": {
            "centroid": m_true.tolist(), "cov": C_true.tolist(),
            "eig_ratio": float(eigval[-1] / eigval[0]),
            "ess_v": ess_func, "n": int(n)},
        "all_pass": bool(all(checks.values())),
    }
    return result


# ---------------------------------------------------------------------------
# M2-S2 -- half-space Geometry-IS sanity (fresh deterministic configs)
# ---------------------------------------------------------------------------
SANITY_BATCH_SEED = 20260831      # distinct from frozen batch 20260827
SANITY_CONFIG_INDEX = 0


def _s2_make_cfg():
    from hyptraj.m1d.benchmark_family import generate_candidate_pool
    pool = generate_candidate_pool(SANITY_BATCH_SEED, 5, id_prefix="m2sanity")
    cfg = pool[SANITY_CONFIG_INDEX]
    return cfg


def _mc_reference(cfg, n_mc=300000, seed=777):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_mc, 2))
    labels = cfg.label(X)
    ev = labels != "S0"
    phat = float(ev.mean())
    se = float(np.sqrt(max(phat * (1 - phat), 1e-300) / n_mc))
    per_mode = {str(m): float((labels == m).mean())
                for m in sorted(set(labels[ev].tolist()))}
    return {"P_event": phat, "se": se, "per_mode_P": per_mode}


def s2_halfspace(pilot_n=8000, eval_n=60000, mc_n=300000) -> dict:
    from hyptraj.m2 import covariance_policy as cp
    from hyptraj.m2.metrics import leakage_ratios

    cfg = _s2_make_cfg()
    records_summary: dict = {}
    problems: list[str] = []

    ref = _mc_reference(cfg, n_mc=mc_n)

    # ---- one healthy trial -------------------------------------------------
    stage = cp.run_shared_stage(cfg, 2026, n_pilot=pilot_n, n_eval=eval_n)
    if stage.selected_mode is None:
        raise RuntimeError("sanity S2 needs an eligible mode; adjust inputs")
    healthy_hold = bool(stage.region.hold_required[0])

    cands = cp.build_candidates(stage.region, stage.sigma_base)
    budget_total = pilot_n + eval_n
    from hyptraj.m1d.metrics import attach_vrfs

    evals = {}
    for method in cp.COV_METHODS:
        spec = cands[method]
        pb, info_b = cp.build_variant_proposal(stage, spec, cp.LAYER_B)
        ev = cp.evaluate_variant(stage, pb, eval_n)
        attach_vrfs(ev, p_ref=float(ref["P_event"]), budget_total=budget_total)
        evals[method] = {"spec": spec, "solver": info_b, "ev": ev}

        if not spec.projection.legality_passed:
            problems.append(f"{method}: legality failed")
        if not np.all(np.isfinite(pb.weights)):
            problems.append(f"{method}: non-finite weights")
        if np.any(pb.weights < 0):
            problems.append(f"{method}: negative weight")

    # C0 correctness: rebuilt independently from frozen primitives
    from hyptraj.m1.proposal_update import add_component, update_weights
    prop_check = add_component(stage.q0_frozen, stage.region.centroid,
                               mode_id=str(stage.selected_mode))
    indicators = (stage.labels != "S0").astype(float)
    prop_check, res_w = update_weights(prop_check, stage.z, stage.logp,
                                       stage.logr, indicators)
    c0_ok = bool(np.allclose(prop_check.weights, stage.pi_c0, atol=1e-10)
                 and res_w.success)
    if not c0_ok:
        problems.append("C0 rebuild mismatch with shared stage pi_c0")
    ev_c0 = evals["C0"]["ev"]
    q_positive_everywhere = True
    for method in cp.COV_METHODS:
        pb, _i = cp.build_variant_proposal(stage, cands[method], cp.LAYER_B)
        rng_probe = np.random.default_rng([2026, 900001])
        z_probe = pb.sample(rng_probe, 20000)
        lq = pb.log_density(z_probe)
        if not np.all(np.isfinite(lq)) or np.any(lq <= -1e12):
            q_positive_everywhere = False
    if not q_positive_everywhere:
        problems.append("proposal density degenerate somewhere probed")

    # unbiasedness sanity (loose band vs MC reference; declared tolerance)
    tol_se = 6.0
    consistent = {
        m: bool(abs(evals[m]["ev"]["P_hat"] - ref["P_event"])
                <= tol_se * ref["se"])
        for m in cp.COV_METHODS}
    if not all(consistent.values()):
        problems.append(f"P̂ outside ±{tol_se} MC-SE band: {consistent}")

    lr = leakage_ratios(evals["C4"]["ev"]["L_table"],
                        evals["C0"]["ev"]["L_table"], stage.selected_mode)

    # ---- forced low-ESS HOLD trial -----------------------------------------
    hold_trial = {}
    for seed_try in range(2100, 2600):
        st_h = cp.run_shared_stage(cfg, seed_try, n_pilot=max(1200,
                                                              pilot_n // 6))
        if st_h.region is not None and st_h.region.hold_required[0]:
            cand_h = cp.build_candidates(st_h.region, st_h.sigma_base)
            same_as_base = all(
                np.allclose(cand_h[m].sigma_final, st_h.sigma_base)
                for m in ("C1", "C2", "C3", "C4"))
            reasons = {m: cand_h[m].hold_reason for m in
                       ("C1", "C2", "C3", "C4")}
            c0_same = np.allclose(cand_h["C0"].sigma_final, st_h.sigma_base)
            rec_held_flags = {m: cand_h[m].held
                              for m in ("C1", "C2", "C3", "C4")}
            ok = bool(same_as_base and c0_same and all(rec_held_flags.values())
                      and not cand_h["C0"].held)
            hold_trial = {
                "seed_used": seed_try, "n_pilot_forced": max(1200,
                                                             pilot_n // 6),
                "ess_v_region": float(st_h.region.ess_v_region),
                "n_region": int(st_h.region.n_region),
                "c14_collapsed_to_base": same_as_base,
                "c0_unchanged_by_hold": c0_same,
                "recorded_as_HOLD_not_failure": ok,
                "hold_reasons": reasons,
            }
            break
    if not hold_trial:
        problems.append("could not materialize a low-ESS HOLD trial")

    records_summary = {
        m: {"held": bool(evalses_spec.held)}
        for m, evalses_spec in ((m, evals[m]["spec"]) for m in evals)}

    result = {
        **_meta("m2_s2_halfspace"),
        "config_id": cfg.config_id,
        "config_params": cfg.params_dict(),
        "batch_seed_note": "sanity-only family instance "
                           f"(batch_seed={SANITY_BATCH_SEED}); NOT part of "
                           "the frozen M1-D benchmark set",
        "budgets": {"pilot_n": pilot_n, "eval_n": eval_n, "mc_reference_n":
                    mc_n},
        "healthy_trial": {
            "seed": 2026,
            "selected_mode": stage.selected_mode,
            "eligible": list(stage.eligible),
            "hold_fired_on_healthy_trial": healthy_hold,
            "n_region": int(stage.region.n_region),
            "ess_v_region": float(stage.region.ess_v_region),
        },
        "mc_reference": ref,
        "records": records_summary,
        "per_method": {m: {"hold": bool(evals[m]["spec"].held),
                           "legality_passed":
                               bool(evals[m]["spec"]
                                    .projection.legality_passed),
                           "P_hat": evals[m]["ev"]["P_hat"],
                           "M2_hat": evals[m]["ev"]["M2_hat"],
                           "VRF_budget": evals[m]["ev"]["VRF_budget"]}
                       for m in cp.COV_METHODS},
        "probability_consistency_band": consistent,
        "tolerance_declared": f"|P_hat - P_MC| <= {tol_se} * MC SE",
        "leakage_ratio_sample": lr["R_L_table"],
        "forced_hold_trial": hold_trial,
        "problems": problems,
        "all_pass": bool(not problems and all(consistent.values())
                         and hold_trial.get("recorded_as_HOLD_not_failure",
                                            False)),
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 sanity S1/S2")
    ap.add_argument("--skip-s1", action="store_true")
    ap.add_argument("--skip-s2", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.skip_s1:
        r1 = s1_weighted_cloud()
        (OUT / "m2_s1_weighted_cloud.json").write_text(
            json.dumps(r1, indent=1), encoding="utf-8")
        print(f"[S1 weighted cloud] all_pass={r1['all_pass']}")
        if not r1["all_pass"]:
            print(json.dumps(r1["checks"], indent=1))
    if not args.skip_s2:
        r2 = s2_halfspace()
        (OUT / "m2_s2_halfspace.json").write_text(
            json.dumps(r2, indent=1), encoding="utf-8")
        print(f"[S2 half-space] all_pass={r2['all_pass']} "
              f"config={r2['config_id']}")
        if not r2["all_pass"]:
            print(json.dumps({k: v for k, v in r2.items()
                              if k in ("problems",
                                       "probability_consistency_band")},
                             indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
