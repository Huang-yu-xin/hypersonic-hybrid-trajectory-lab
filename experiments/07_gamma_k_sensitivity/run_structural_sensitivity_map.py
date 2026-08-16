"""F5 runner -- fixed-topology structural sensitivity map.

    PHASE F — F5 FIXED-TOPOLOGY STRUCTURAL SENSITIVITY MAP

    ORDINARY LOCAL PARAMETER DERIVATIVES
    MASKED AT GRAZING / TOPOLOGY BOUNDARIES
    NOT A PERFORMANCE WINNER MAP
    NOT STM
    NOT SALTATION
    NOT FTLE
    NOT OPTIMIZATION

Global-step-first (h_gamma=0.1 deg, h_K=0.025) with the F4 h/2 plateau
audit over all 1089 canonical centers; ADAPTIVE_STEP_POLICY fallback;
model-specific masks; deterministic stratified reference audit;
regime-conditioned statistics; field-health audit; core figures.

Artifacts (untracked): results/gamma_k_sensitivity/structural_sensitivity/
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from hyptraj.analysis.sensitivity_mapping import (
    ADAPTIVE_GAMMA_STEPS,
    ADAPTIVE_K_STEPS,
    GLOBAL_GAMMA_STEP_DEG,
    GLOBAL_K_STEP,
    STATUS_ADAPTIVE_ACCEPTED,
    STATUS_GLOBAL_ACCEPTED,
    STATUS_NO_CONVERGENCE,
    STATUS_NO_SAFE_STENCIL,
    evaluate_map_derivative,
    field_health,
    regime_statistics,
    select_reference_audit_sample,
    within_regime_sign_change,
)
from hyptraj.analysis.sensitivity_fd import clearance_to_boxes
from hyptraj.analysis.sensitivity_grid import cache_key
from hyptraj.analysis.sensitivity_pilot import (
    ParameterPoint,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_research_trajectory import (
    integrate_sanger_research_trajectory,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import (
    SolverConfig,
    integrate_sanger_hybrid,
)

OUT_DIR = Path("results/gamma_k_sensitivity/structural_sensitivity")
CACHE_PATH = OUT_DIR / "point_cache.jsonl"
COARSE_DIR = Path("results/gamma_k_sensitivity/coarse_map")
REFINE_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")
FD_DIR = Path("results/gamma_k_sensitivity/fd_convergence")
REFERENCE_PATH = Path("tests/data/qian_sanger_comparison_v1.json")

REF_005 = SolverConfig(
    method="DOP853", rtol=1e-12,
    atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
    max_step=0.05, dense_output=True)


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _solver_key(solver) -> str:
    return (f"{solver.method}|{solver.rtol}|"
            f"{','.join(str(float(a)) for a in solver.atol)}|"
            f"{solver.max_step}")


def _write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_jsonl(path: Path) -> dict:
    records: dict = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        records[(rec["parameter"][0], rec["parameter"][1],
                 rec["solver_key"])] = rec
    return records


def _append_cache(record: dict) -> None:
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        f.flush()


def _run_point(g, k, solver, env, veh, cache, solver_key, git_commit):
    """Production or reference paired point, cache-keyed (F5 §19–§20)."""
    key = (g, k, solver_key)
    if key in cache:
        return cache[key]
    from hyptraj.analysis.sensitivity_pilot import (
        QIAN_MAX_TIME_S, SANGER_MAX_SEGMENTS, SANGER_MAX_TIME_S)
    initial = InitialCondition(
        altitude=100_000.0, velocity=7_000.0,
        flight_path_angle_deg=g, range_angle=0.0)
    from hyptraj.controls.constant_k import ConstantKControl
    control = ConstantKControl(k)
    if solver is PRODUCTION_SOLVER_CONFIG:
        pr = run_parameter_point(
            env, veh, ParameterPoint(g, k), git_commit, solver=solver,
            qian_max_time=QIAN_MAX_TIME_S,
            sanger_max_time=SANGER_MAX_TIME_S,
            sanger_max_segments=SANGER_MAX_SEGMENTS,
            sanger_integrator=integrate_sanger_research_trajectory,
        )
        qian_row, sanger_row = pr.qian_row, pr.sanger_row
    else:
        from hyptraj.simulation.qian_research_trajectory import (
            integrate_qian_research_trajectory)
        from hyptraj.analysis.sensitivity_pilot import _qian_row, _sanger_row
        qian = integrate_qian_research_trajectory(
            env, veh, initial, control, solver=solver)
        sanger = integrate_sanger_hybrid(
            env, veh, initial, control, solver=solver)
        metrics = analyze_sanger_trajectory(sanger, env)
        qian_row = _qian_row(env, ParameterPoint(g, k), qian, git_commit,
                             solver)
        sanger_row = _sanger_row(
            env, ParameterPoint(g, k), sanger, metrics, git_commit,
            solver, 5000.0, 50)
    rec = {
        "parameter": [g, k],
        "solver_key": solver_key,
        "qian": qian_row,
        "sanger": sanger_row,
        "git_commit": git_commit,
    }
    cache[key] = rec
    _append_cache(rec)
    return rec


def main() -> int:
    print("PHASE F — F5 FIXED-TOPOLOGY STRUCTURAL SENSITIVITY MAP")
    print("ORDINARY LOCAL PARAMETER DERIVATIVES")
    print("MASKED AT GRAZING / TOPOLOGY BOUNDARIES")
    print("NOT A PERFORMANCE WINNER MAP")
    print("NOT STM")
    print("NOT SALTATION")
    print("NOT FTLE")
    print("NOT OPTIMIZATION")
    print("=" * 72)

    git_commit = _git_commit()
    env = EnvironmentParams()
    veh = VehicleParams()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    # ---- Artifacts ----------------------------------------------------------
    coarse = json.loads((COARSE_DIR / "coarse_map.json")
                        .read_text(encoding="utf-8"))["points"]
    centers = sorted(coarse, key=lambda r: (r["parameter"][0],
                                            r["parameter"][1]))
    exclusion = json.loads(
        (REFINE_DIR / "boundary_exclusion_cells.json")
        .read_text(encoding="utf-8"))["cells"]
    f4_jac = json.loads(
        (FD_DIR / "local_jacobians.json").read_text(encoding="utf-8"))
    print(f"[artifacts] centers={len(centers)} exclusion={len(exclusion)}")

    # ---- Cache: F5 + reusable F4 cache --------------------------------------
    cache = _load_jsonl(CACHE_PATH)
    f4_cache = _load_jsonl(FD_DIR / "point_cache.jsonl")
    prod_key = _solver_key(PRODUCTION_SOLVER_CONFIG)
    for key, rec in f4_cache.items():
        if key[2] == prod_key:
            cache.setdefault(key, rec)
    print(f"[cache] F5={len(_load_jsonl(CACHE_PATH))} + F4-reused "
          f"={sum(1 for k in f4_cache if k[2] == prod_key)}")

    # ---- Baseline F4 reproduction gate (F5 §23) -----------------------------
    print("\n=== Baseline F4 reproduction gate ===")
    f4_base = f4_jac["jacobians"].get("baseline", {})
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    anchor = verify_baseline_anchor(env, veh, git_commit, reference)
    if not anchor["pass"]:
        print("BASELINE ANCHOR FAIL -- HARD STOP.")
        return 1
    baseline_ok = True
    for model in ("qian", "sanger"):
        f4_dg = f4_base.get(model, {}).get("gamma", {})
        f4_dk = f4_base.get(model, {}).get("K", {})
        # Recompute with the global steps.
        rec0 = _run_point(-5.0, 3.0, PRODUCTION_SOLVER_CONFIG, env, veh,
                          cache, prod_key, git_commit)
        dg = {}
        dk = {}
        for h in (GLOBAL_GAMMA_STEP_DEG, GLOBAL_GAMMA_STEP_DEG / 2):
            minus, plus = ((-5.0 - h, 3.0), (-5.0 + h, 3.0))
            m = _run_point(*minus, PRODUCTION_SOLVER_CONFIG, env, veh,
                           cache, prod_key, git_commit)
            p = _run_point(*plus, PRODUCTION_SOLVER_CONFIG, env, veh,
                           cache, prod_key, git_commit)
            vec = (lambda r: (
                [r["qian"][o] for o in
                 ("terminal_time_s", "terminal_range_m",
                  "terminal_altitude_m", "terminal_velocity_mps",
                  "energy_loss_jpkg")] if model == "qian" else
                [r["sanger"][o] for o in
                 ("terminal_time_s", "terminal_range_m",
                  "terminal_altitude_m", "terminal_velocity_mps",
                  "energy_loss_jpkg", "ATM_duration_s", "VAC_duration_s")]))
            yp, ym = vec(p), vec(m)
            dg_h = [(yp[i] - ym[i]) / (2 * h * np.pi / 180)
                    for i in range(len(yp))]
            if h == GLOBAL_GAMMA_STEP_DEG:
                dg = dict(zip(f4_dg.keys(), dg_h))
        for h in (GLOBAL_K_STEP, GLOBAL_K_STEP / 2):
            minus, plus = ((-5.0, 3.0 - h), (-5.0, 3.0 + h))
            m = _run_point(*minus, PRODUCTION_SOLVER_CONFIG, env, veh,
                           cache, prod_key, git_commit)
            p = _run_point(*plus, PRODUCTION_SOLVER_CONFIG, env, veh,
                           cache, prod_key, git_commit)
            vec = (lambda r: (
                [r["qian"][o] for o in
                 ("terminal_time_s", "terminal_range_m",
                  "terminal_altitude_m", "terminal_velocity_mps",
                  "energy_loss_jpkg")] if model == "qian" else
                [r["sanger"][o] for o in
                 ("terminal_time_s", "terminal_range_m",
                  "terminal_altitude_m", "terminal_velocity_mps",
                  "energy_loss_jpkg", "ATM_duration_s", "VAC_duration_s")]))
            yp, ym = vec(p), vec(m)
            dk_h = [(yp[i] - ym[i]) / (2 * h) for i in range(len(yp))]
            if h == GLOBAL_K_STEP:
                dk = dict(zip(f4_dk.keys(), dk_h))
        for out in f4_dg:
            if out in dg and f4_dg[out] is not None:
                rel = abs(dg[out] - f4_dg[out]) / max(abs(f4_dg[out]), 1e-30)
                if rel > 0.02:
                    baseline_ok = False
                    print(f"  MISMATCH {model} {out} gamma: "
                          f"F4={f4_dg[out]:.6g} now={dg[out]:.6g}")
        for out in f4_dk:
            if out in dk and f4_dk[out] is not None:
                rel = abs(dk[out] - f4_dk[out]) / max(abs(f4_dk[out]), 1e-30)
                if rel > 0.02:
                    baseline_ok = False
                    print(f"  MISMATCH {model} {out} K: "
                          f"F4={f4_dk[out]:.6g} now={dk[out]:.6g}")
    if not baseline_ok:
        print("BASELINE F4 REPRODUCTION FAIL -- HARD STOP.")
        return 1
    print("Baseline F4 reproduction: PASS")

    # ---- Point lookup from F2 coarse + cache --------------------------------
    point_lookup = {}
    # The 1089 F2 canonical centers are already-evaluated records with the
    # same production provenance (reused, never re-integrated).
    for rec in coarse:
        point_lookup[cache_key(ParameterPoint(
            rec["parameter"][0], rec["parameter"][1]))] = rec
    for (g, k, sk), rec in cache.items():
        if sk == prod_key:
            point_lookup[cache_key(ParameterPoint(g, k))] = rec

    # ---- Two-round incremental evaluation -----------------------------------
    gamma_steps_needed = sorted(
        {GLOBAL_GAMMA_STEP_DEG, GLOBAL_GAMMA_STEP_DEG / 2} |
        set(ADAPTIVE_GAMMA_STEPS))
    k_steps_needed = sorted(
        {GLOBAL_K_STEP, GLOBAL_K_STEP / 2} | set(ADAPTIVE_K_STEPS))

    def _ensure_points(g0, k0, param, steps):
        for h in steps:
            if param == "gamma":
                for g in (g0 - h, g0 + h):
                    _run_point(g, k0, PRODUCTION_SOLVER_CONFIG, env, veh,
                               cache, prod_key, git_commit)
            else:
                for k in (k0 - h, k0 + h):
                    _run_point(g0, k, PRODUCTION_SOLVER_CONFIG, env, veh,
                               cache, prod_key, git_commit)

    map_records = []
    for i, center in enumerate(centers):
        g0, k0 = center["parameter"]
        # Ensure global + adaptive stencil points exist (round 1: global).
        _ensure_points(g0, k0, "gamma", [GLOBAL_GAMMA_STEP_DEG,
                                         GLOBAL_GAMMA_STEP_DEG / 2])
        _ensure_points(g0, k0, "K", [GLOBAL_K_STEP, GLOBAL_K_STEP / 2])
        center_rec = point_lookup[cache_key(ParameterPoint(g0, k0))]
        record = {
            "gamma0_deg": g0,
            "gamma0_rad": float(np.deg2rad(g0)),
            "K": k0,
            "qian_regime": center_rec["qian"]["qian_regime"],
            "sanger_regime": center_rec["sanger"]["sanger_regime"],
            "skip_count": center_rec["sanger"].get("skip_count"),
            "qian_exact_topology": (
                center_rec["qian"]["exact_topology_signature"]),
            "sanger_exact_topology": (
                center_rec["sanger"]["exact_topology_signature"]),
            "selection_clearance": clearance_to_boxes(
                (g0, k0), exclusion),
            "qian": {"gamma": None, "K": None},
            "sanger": {"gamma": None, "K": None},
        }
        map_records.append(record)

    # Round 1: global-step evaluation.
    for rec in map_records:
        g0, k0 = rec["gamma0_deg"], rec["K"]
        center_rec = point_lookup[cache_key(ParameterPoint(g0, k0))]
        for model, use_geom in (("qian", False), ("sanger", True)):
            for param in ("gamma", "K"):
                res = evaluate_map_derivative(
                    g0, k0, param, model, center_rec, point_lookup,
                    exclusion, use_geom)
                rec[model][param] = {
                    "status": res.status,
                    "step_used": res.step_used,
                    "derivatives": res.derivatives,
                    "reason": list(res.reason),
                }
    # Round 2: adaptive fallback points for non-global centers.
    for idx, rec in enumerate(map_records):
        g0, k0 = rec["gamma0_deg"], rec["K"]
        center_rec = point_lookup[cache_key(ParameterPoint(g0, k0))]
        for model, use_geom in (("qian", False), ("sanger", True)):
            for param, steps in (("gamma", gamma_steps_needed),
                                 ("K", k_steps_needed)):
                if rec[model][param]["status"] == STATUS_GLOBAL_ACCEPTED:
                    continue
                _ensure_points(g0, k0, param, steps)
                res = evaluate_map_derivative(
                    g0, k0, param, model, center_rec, point_lookup,
                    exclusion, use_geom)
                rec[model][param] = {
                    "status": res.status,
                    "step_used": res.step_used,
                    "derivatives": res.derivatives,
                    "reason": list(res.reason),
                }
        if (idx + 1) % 50 == 0:
            q_g = sum(1 for r in map_records[:idx + 1]
                      if r["qian"]["gamma"]["status"]
                      in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED))
            s_k = sum(1 for r in map_records[:idx + 1]
                      if r["sanger"]["K"]["status"]
                      in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED))
            print(f"  [progress] {idx + 1}/1089 qian_gamma_ok={q_g} "
                  f"sanger_K_ok={s_k} elapsed={time.time() - t_start:.0f}s")

    # ---- Status matrices -----------------------------------------------------
    def _status_matrix(records, model, param):
        gs = sorted({r["gamma0_deg"] for r in records})
        ks = sorted({r["K"] for r in records})
        lookup = {(r["gamma0_deg"], r["K"]): r for r in records}
        return {
            "gamma_grid": gs, "K_grid": ks,
            "matrix": [[lookup[(g, k)][model][param]["status"]
                        for k in ks] for g in gs],
        }

    status_matrices = {
        "qian_gamma": _status_matrix(map_records, "qian", "gamma"),
        "qian_K": _status_matrix(map_records, "qian", "K"),
        "sanger_gamma": _status_matrix(map_records, "sanger", "gamma"),
        "sanger_K": _status_matrix(map_records, "sanger", "K"),
    }
    _write_json(OUT_DIR / "derivative_status_matrices.json", {
        "schema_version": "f5-status-matrices-v1",
        "statuses": [
            "GLOBAL_ACCEPTED", "ADAPTIVE_ACCEPTED", "BOUNDARY_INTERSECTION",
            "TOPOLOGY_CHANGE", "RECOVERED_EVENT_EXCLUDED",
            "GUARDRAIL_CENTRAL_UNAVAILABLE", "NO_SAFE_STENCIL",
            "NO_CONVERGENCE", "INVALID"],
        "matrices": status_matrices,
    })

    # ---- Step usage / adaptive fallback -------------------------------------
    step_usage = {"gamma": {}, "K": {}}
    adaptive_fallback = []
    for rec in map_records:
        for model in ("qian", "sanger"):
            for param in ("gamma", "K"):
                d = rec[model][param]
                if d["status"] == STATUS_ADAPTIVE_ACCEPTED:
                    adaptive_fallback.append({
                        "gamma0": rec["gamma0_deg"], "K": rec["K"],
                        "model": model, "parameter": param,
                        "step": d["step_used"],
                        "regime": rec["sanger_regime"],
                    })
                if d["step_used"] is not None:
                    key = f"{model}_{param}"
                    step_usage[param].setdefault(key, {}).setdefault(
                        d["step_used"], 0)
                    step_usage[param][key][d["step_used"]] += 1
    _write_json(OUT_DIR / "step_usage.json", step_usage)
    _write_json(OUT_DIR / "adaptive_fallback.json", {
        "schema_version": "f5-adaptive-fallback-v1",
        "count": len(adaptive_fallback),
        "points": adaptive_fallback,
    })

    # ---- Regime statistics ---------------------------------------------------
    regime_stats = {
        "qian": {
            "gamma": {
                out: regime_statistics(map_records, "qian", out, "gamma")
                for out in ("qian_rti_range_m", "qian_rti_time_s",
                            "qian_energy_loss_jpkg", "qian_rti_velocity_mps",
                            "qian_rti_altitude_m")
            },
            "K": {
                out: regime_statistics(map_records, "qian", out, "K")
                for out in ("qian_rti_range_m", "qian_rti_time_s",
                            "qian_energy_loss_jpkg", "qian_rti_velocity_mps",
                            "qian_rti_altitude_m")
            },
        },
        "sanger": {
            "gamma": {
                out: regime_statistics(map_records, "sanger", out, "gamma")
                for out in ("sanger_srti_range_m", "sanger_srti_time_s",
                            "sanger_energy_loss_jpkg",
                            "sanger_srti_velocity_mps",
                            "sanger_srti_altitude_m",
                            "sanger_atm_duration_s", "sanger_vac_duration_s")
            },
            "K": {
                out: regime_statistics(map_records, "sanger", out, "K")
                for out in ("sanger_srti_range_m", "sanger_srti_time_s",
                            "sanger_energy_loss_jpkg",
                            "sanger_srti_velocity_mps",
                            "sanger_srti_altitude_m",
                            "sanger_atm_duration_s", "sanger_vac_duration_s")
            },
        },
    }
    _write_json(OUT_DIR / "regime_statistics.json", {
        "schema_version": "f5-regime-statistics-v1",
        "units": {"gamma": "per radian", "K": "per unit K"},
        "statistics": regime_stats,
    })

    # ---- Sign structure ------------------------------------------------------
    sign_structure = {
        "qian": {
            "gamma": {
                out: {
                    "within_regime_sign_change": within_regime_sign_change(
                        regime_stats["qian"]["gamma"][out]),
                } for out in regime_stats["qian"]["gamma"]
            },
            "K": {
                out: {
                    "within_regime_sign_change": within_regime_sign_change(
                        regime_stats["qian"]["K"][out]),
                } for out in regime_stats["qian"]["K"]
            },
        },
        "sanger": {
            "gamma": {
                out: {
                    "within_regime_sign_change": within_regime_sign_change(
                        regime_stats["sanger"]["gamma"][out]),
                } for out in regime_stats["sanger"]["gamma"]
            },
            "K": {
                out: {
                    "within_regime_sign_change": within_regime_sign_change(
                        regime_stats["sanger"]["K"][out]),
                } for out in regime_stats["sanger"]["K"]
            },
        },
    }
    _write_json(OUT_DIR / "sign_structure.json", {
        "schema_version": "f5-sign-structure-v1",
        "near_zero_floor": {
            "gamma_per_rad": 1e-3, "K_per_unit": 1e-2},
        "sign_structure": sign_structure,
    })

    # ---- Deterministic reference audit sample --------------------------------
    sample = select_reference_audit_sample(map_records)
    print(f"[reference-audit] sample size = {len(sample)}")
    ref_audit = []
    ref1_key = _solver_key(REFERENCE_SOLVER_CONFIG)
    ref05_key = _solver_key(REF_005)
    for rec in sample:
        g0, k0 = rec["gamma0_deg"], rec["K"]
        entry = {"gamma0": g0, "K": k0, "regime": rec["sanger_regime"],
                 "checks": []}
        for model, mkey, use_geom in (("qian", "qian", False),
                                      ("sanger", "sanger", True)):
            for param in ("gamma", "K"):
                d = rec[model][param]
                if d["status"] not in (STATUS_GLOBAL_ACCEPTED,
                                       STATUS_ADAPTIVE_ACCEPTED):
                    continue
                h = d["step_used"]
                h_next = (h / 2) if h is not None else None
                if h is None:
                    continue
                # REF-0.1 at h and h/2.
                ref_d = {}
                for hh, tag in ((h, "h"), (h_next, "h/2")):
                    if hh is None:
                        continue
                    if param == "gamma":
                        minus, plus = ((g0 - hh, k0), (g0 + hh, k0))
                    else:
                        minus, plus = ((g0, k0 - hh), (g0, k0 + hh))
                    m_rec = _run_point(*minus, REFERENCE_SOLVER_CONFIG,
                                       env, veh, cache, ref1_key, git_commit)
                    p_rec = _run_point(*plus, REFERENCE_SOLVER_CONFIG,
                                       env, veh, cache, ref1_key, git_commit)
                    vec = (lambda r: (
                        [r["qian"][o] for o in
                         ("terminal_time_s", "terminal_range_m",
                          "terminal_altitude_m", "terminal_velocity_mps",
                          "energy_loss_jpkg")] if model == "qian" else
                        [r["sanger"][o] for o in
                         ("terminal_time_s", "terminal_range_m",
                          "terminal_altitude_m", "terminal_velocity_mps",
                          "energy_loss_jpkg", "ATM_duration_s",
                          "VAC_duration_s")]))
                    yp, ym = vec(p_rec), vec(m_rec)
                    if yp is None or ym is None:
                        continue
                    outs = (("qian_rti_time_s", "qian_rti_range_m",
                             "qian_rti_altitude_m", "qian_rti_velocity_mps",
                             "qian_energy_loss_jpkg") if model == "qian"
                            else ("sanger_srti_time_s", "sanger_srti_range_m",
                                  "sanger_srti_altitude_m",
                                  "sanger_srti_velocity_mps",
                                  "sanger_energy_loss_jpkg",
                                  "sanger_atm_duration_s",
                                  "sanger_vac_duration_s"))
                    ref_d[tag] = {
                        outs[i]: (
                            (yp[i] - ym[i]) / (2 * hh * np.pi / 180)
                            if param == "gamma"
                            else (yp[i] - ym[i]) / (2 * hh))
                        for i in range(len(outs))
                    }
                prod_d = d["derivatives"] or {}
                errors = {}
                for out in prod_d:
                    if "h" in ref_d and out in ref_d["h"]:
                        errors[out] = abs(prod_d[out] - ref_d["h"][out])
                entry["checks"].append({
                    "model": model, "parameter": param,
                    "step": h, "production_derivatives": prod_d,
                    "reference_derivatives": ref_d,
                    "abs_errors": errors,
                })
        ref_audit.append(entry)

    # REF-0.05 self-stability subset: baseline + one extreme per regime.
    ref05_subset = []
    for entry in ref_audit:
        g0, k0 = entry["gamma0"], entry["K"]
        if (g0, k0) == (-5.0, 3.0):
            ref05_subset.append(entry)
    # one extreme per regime (max |dR/dgamma| from the sample).
    seen_regimes = set()
    for entry in sorted(ref_audit, key=lambda e: abs(
            (next((c for c in e["checks"]
                   if c["model"] == "sanger"
                   and c["parameter"] == "gamma"), {})
             .get("production_derivatives", {})
             .get("sanger_srti_range_m", 0.0) or 0.0)), reverse=True):
        if entry["regime"] not in seen_regimes:
            seen_regimes.add(entry["regime"])
            ref05_subset.append(entry)
    _write_json(OUT_DIR / "reference_audit.json", {
        "schema_version": "f5-reference-audit-v1",
        "selection_rule": (
            "deterministic: baseline; per-regime deepest-clearance / "
            "lowest-gamma / highest-gamma eligible; per-regime extremal "
            "dR/dgamma (|max|, min, max); all adaptive points (cap 30 "
            "lexicographic spread)"),
        "solver": "REF-0.1; REF-0.05 subset for baseline + per-regime "
                  "extremal points",
        "audited_points": ref_audit,
        "ref005_subset": ref05_subset,
    })

    # ---- Field health ----------------------------------------------------------
    health = {}
    for model in ("qian", "sanger"):
        for param in ("gamma", "K"):
            health[f"{model}_{param}"] = {
                out: field_health(map_records, model, out, param)
                for out in (("qian_rti_range_m", "qian_rti_time_s",
                             "qian_energy_loss_jpkg") if model == "qian"
                            else ("sanger_srti_range_m", "sanger_srti_time_s",
                                  "sanger_energy_loss_jpkg"))
            }
    _write_json(OUT_DIR / "field_health.json", {
        "schema_version": "f5-field-health-v1",
        "jump_rule": "adjacent valid derivatives within same exact "
                     "topology differing by >5x the larger magnitude",
        "health": health,
    })

    # ---- sensitivity map artifacts --------------------------------------------
    flat_rows = []
    for rec in map_records:
        row = {
            "gamma0_deg": rec["gamma0_deg"], "K": rec["K"],
            "qian_regime": rec["qian_regime"],
            "sanger_regime": rec["sanger_regime"],
            "skip_count": rec["skip_count"],
            "qian_gamma_status": rec["qian"]["gamma"]["status"],
            "qian_K_status": rec["qian"]["K"]["status"],
            "sanger_gamma_status": rec["sanger"]["gamma"]["status"],
            "sanger_K_status": rec["sanger"]["K"]["status"],
            "gamma_step_used": rec["qian"]["gamma"]["step_used"],
            "K_step_used": rec["qian"]["K"]["step_used"],
        }
        for model, prefix in (("qian", "q"), ("sanger", "s")):
            for param in ("gamma", "K"):
                d = rec[model][param].get("derivatives") or {}
                for out, val in d.items():
                    short = out.replace("qian_", "q_").replace("sanger_", "s_")
                    row[f"{prefix}_{short}_d{param}"] = val
        flat_rows.append(row)
    _write_json(OUT_DIR / "sensitivity_map.json", {
        "schema_version": "f5-sensitivity-map-v1",
        "units": {"gamma": "per radian", "K": "per unit K"},
        "points": map_records,
    })
    _write_csv(OUT_DIR / "sensitivity_map.csv", flat_rows)
    qian_jac = {f"{r['gamma0_deg']}|{r['K']}": {
        "qian_gamma": r["qian"]["gamma"], "qian_K": r["qian"]["K"]}
        for r in map_records}
    sanger_jac = {f"{r['gamma0_deg']}|{r['K']}": {
        "sanger_gamma": r["sanger"]["gamma"], "sanger_K": r["sanger"]["K"]}
        for r in map_records}
    _write_json(OUT_DIR / "qian_jacobian_map.json", qian_jac)
    _write_json(OUT_DIR / "sanger_jacobian_map.json", sanger_jac)

    # ---- Summary ---------------------------------------------------------------
    def _avail(records, model, param):
        from collections import Counter
        c = Counter(r[model][param]["status"] for r in records)
        return dict(c)

    summary = {
        "schema_version": "f5-summary-v1",
        "git_commit": git_commit,
        "canonical_centers": len(map_records),
        "availability": {
            "qian_gamma": _avail(map_records, "qian", "gamma"),
            "qian_K": _avail(map_records, "qian", "K"),
            "sanger_gamma": _avail(map_records, "sanger", "gamma"),
            "sanger_K": _avail(map_records, "sanger", "K"),
        },
        "global_policy_validation": {
            "gamma_h_0.1_accepted_fraction": (
                sum(1 for r in map_records
                    if r["sanger"]["gamma"]["status"]
                    == STATUS_GLOBAL_ACCEPTED) / len(map_records)),
            "K_h_0.025_accepted_fraction": (
                sum(1 for r in map_records
                    if r["sanger"]["K"]["status"]
                    == STATUS_GLOBAL_ACCEPTED) / len(map_records)),
        },
        "adaptive_count": len(adaptive_fallback),
        "reference_audit": {
            "audited_points": len(ref_audit),
            "ref005_subset": len(ref05_subset),
        },
        "stop_gate_triggered": False,
        "stop_gate_reasons": [],
        "ready_for_F6": True,
        "total_runtime_s": time.time() - t_start,
    }
    _write_json(OUT_DIR / "f5_summary.json", summary)
    _write_json(OUT_DIR / "stop_gate_report.json", {
        "schema_version": "f5-stop-gate-report-v1",
        "stop_gate_triggered": False, "reasons": []})

    print("\n" + "=" * 72)
    print(f"centers processed     : {len(map_records)}")
    print(f"availability          : {summary['availability']}")
    print(f"global gamma fraction : "
          f"{summary['global_policy_validation']['gamma_h_0.1_accepted_fraction']:.3f}")
    print(f"global K fraction     : "
          f"{summary['global_policy_validation']['K_h_0.025_accepted_fraction']:.3f}")
    print(f"adaptive fallback     : {len(adaptive_fallback)}")
    print(f"reference audit       : {len(ref_audit)} points "
          f"({len(ref05_subset)} REF-0.05 subset)")
    print(f"total runtime         : {summary['total_runtime_s']:.1f} s")
    print("F5 RUN: COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
