"""F4 runner -- fixed-regime local sensitivity and FD convergence.

    PHASE F — F4 FIXED-REGIME LOCAL SENSITIVITY
    FINITE-DIFFERENCE CONVERGENCE

    ORDINARY DERIVATIVES ONLY INSIDE FIXED TOPOLOGY
    NOT STM
    NOT SALTATION
    NOT FTLE
    NOT OPTIMIZATION

Per-branch multiplicity clarification, automatic representative
fixed-topology point selection, F3 boundary-exclusion-aware stencil
eligibility, production / REF-0.1 / REF-0.05 central finite-difference
convergence, production-vs-reference derivative audit, frozen
global-or-adaptive step policy, and local parameter-output Jacobians.

Artifacts (untracked): results/gamma_k_sensitivity/fd_convergence/
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from hyptraj.analysis.sensitivity_fd import (
    GAMMA_STEPS_DEG,
    GAMMA_STEPS_DEG_EXTRA,
    K_STEPS,
    K_STEPS_EXTRA,
    QIAN_JACOBIAN_SHAPE,
    QIAN_OUTPUTS,
    SANGER_JACOBIAN_SHAPE,
    SANGER_OUTPUTS,
    StencilEligibility,
    central_difference_K,
    central_difference_gamma,
    clearance_to_boxes,
    evaluate_stencil,
    in_plateau,
    largest_safe_converged_step,
    observed_order,
    per_degree_from_per_rad,
    qian_output_vector,
    sanger_output_vector,
    select_representatives,
    segment_intersects_rectangle,
    successive_differences,
)
from hyptraj.analysis.sensitivity_grid import (
    GAMMA_GUARDRAIL,
    K_GUARDRAIL,
    cache_key,
)
from hyptraj.analysis.sensitivity_pilot import (
    ParameterPoint,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
from hyptraj.controls.constant_k import ConstantKControl
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

OUT_DIR = Path("results/gamma_k_sensitivity/fd_convergence")
CACHE_PATH = OUT_DIR / "point_cache.jsonl"
REFINE_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")
COARSE_DIR = Path("results/gamma_k_sensitivity/coarse_map")
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
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _load_cache() -> dict:
    records: dict = {}
    if not CACHE_PATH.exists():
        return records
    for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        key = (rec["parameter"][0], rec["parameter"][1], rec["solver_key"])
        records[key] = rec
    return records


def _append_cache(record: dict) -> None:
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        f.flush()


def _run_point(g, k, solver, env, veh, cache, solver_key, git_commit):
    """Run one paired point with a given solver; cache-keyed."""
    key = (g, k, solver_key)
    if key in cache:
        return cache[key]
    from hyptraj.analysis.sensitivity_pilot import (
        QIAN_MAX_TIME_S, SANGER_MAX_SEGMENTS, SANGER_MAX_TIME_S)
    initial = InitialCondition(
        altitude=100_000.0, velocity=7_000.0,
        flight_path_angle_deg=g, range_angle=0.0)
    control = ConstantKControl(k)
    if solver is PRODUCTION_SOLVER_CONFIG:
        pr = run_parameter_point(
            env, veh, ParameterPoint(g, k), git_commit,
            solver=solver,
            qian_max_time=QIAN_MAX_TIME_S,
            sanger_max_time=SANGER_MAX_TIME_S,
            sanger_max_segments=SANGER_MAX_SEGMENTS,
            sanger_integrator=integrate_sanger_research_trajectory,
        )
        qian_row, sanger_row = pr.qian_row, pr.sanger_row
    else:
        # Reference runs use the frozen integrator on the same paired
        # structure (Qian research API + frozen Sanger reference).
        from hyptraj.simulation.qian_research_trajectory import (
            integrate_qian_research_trajectory)
        qian = integrate_qian_research_trajectory(
            env, veh, initial, control, solver=solver)
        sanger = integrate_sanger_hybrid(
            env, veh, initial, control, solver=solver)
        metrics = analyze_sanger_trajectory(sanger, env)
        from hyptraj.analysis.sensitivity_pilot import _qian_row, _sanger_row
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
    print("PHASE F — F4 FIXED-REGIME LOCAL SENSITIVITY")
    print("FINITE-DIFFERENCE CONVERGENCE")
    print("ORDINARY DERIVATIVES ONLY INSIDE FIXED TOPOLOGY")
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

    # ---- F2 / F3 artifacts ------------------------------------------------
    coarse = json.loads((COARSE_DIR / "coarse_map.json")
                        .read_text(encoding="utf-8"))
    coarse_records: dict = {}
    for rec in coarse["points"]:
        coarse_records[cache_key(
            ParameterPoint(rec["parameter"][0], rec["parameter"][1]))] = rec
    exclusion = json.loads(
        (REFINE_DIR / "boundary_exclusion_cells.json")
        .read_text(encoding="utf-8"))["cells"]
    refined = json.loads(
        (REFINE_DIR / "refined_boundary_cells.json")
        .read_text(encoding="utf-8"))["cells"]
    print(f"[F2] coarse points = {len(coarse_records)} | "
          f"[F3] exclusion cells = {len(exclusion)}")

    # ---- Per-branch multiplicity clarification (F4 §3) --------------------
    branch_rows: dict[str, dict] = {}
    branch_cols: dict[str, dict] = {}
    for c in refined:
        b = c.get("branch")
        if not b:
            continue
        r = c["rectangle"]
        g_key = round(r["gamma_min"], 6)
        k_key = round(r["K_min"], 6)
        branch_rows.setdefault(b, {}).setdefault(g_key, []).append(
            (r["K_min"], r["K_max"]))
        branch_cols.setdefault(b, {}).setdefault(k_key, []).append(
            (r["gamma_min"], r["gamma_max"]))

    def _clusters(intervals):
        if not intervals:
            return 0
        merged = sorted(intervals)
        n = 1
        end = merged[0][1]
        for a, b in merged[1:]:
            if a > end + 1e-12:
                n += 1
            end = max(end, b)
        return n

    multiplicity_audit = {
        "per_branch_max_row_multiplicity": {
            b: max((_clusters(v) for v in rows.values()), default=0)
            for b, rows in sorted(branch_rows.items())},
        "per_branch_max_column_multiplicity": {
            b: max((_clusters(v) for v in cols.values()), default=0)
            for b, cols in sorted(branch_cols.items())},
        "rows_with_multiplicity_gt_1": {
            b: [{"gamma0": g, "multiplicity": _clusters(v)}
                for g, v in sorted(rows.items()) if _clusters(v) > 1]
            for b, rows in sorted(branch_rows.items())},
        "columns_with_multiplicity_gt_1": {
            b: [{"K": k, "multiplicity": _clusters(v)}
                for k, v in sorted(cols.items()) if _clusters(v) > 1]
            for b, cols in sorted(branch_cols.items())},
    }
    _write_json(OUT_DIR / "multiplicity_audit.json", {
        "schema_version": "f4-multiplicity-audit-v1",
        **multiplicity_audit,
    })
    print("[multiplicity] per-branch max row / col:",
          multiplicity_audit["per_branch_max_row_multiplicity"], "/",
          multiplicity_audit["per_branch_max_column_multiplicity"])

    # ---- Representative selection (F4 §8–§9) ------------------------------
    reps = select_representatives(coarse_records, exclusion)
    print(f"[representatives] {len(reps)} selected")
    for r in reps:
        print(f"  {r['label']}: gamma0={r['gamma0_deg']} K={r['K']} "
              f"regime={r['sanger_regime']} clearance="
              f"{r['selection_clearance']:.4f}")
    _write_json(OUT_DIR / "representative_points.json", {
        "schema_version": "f4-representative-points-v1",
        "note": "selection_clearance is a computational selection "
                "diagnostic, not a scientific sensitivity metric",
        "representatives": reps,
    })

    # ---- Baseline gate ------------------------------------------------------
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    anchor = verify_baseline_anchor(env, veh, git_commit, reference)
    if not anchor["pass"]:
        print("BASELINE ANCHOR FAIL -- HARD STOP.")
        return 1
    print("Baseline anchor: PASS")

    # ---- Candidate stencils + eligibility ----------------------------------
    cache = _load_cache()
    gamma_steps = GAMMA_STEPS_DEG + GAMMA_STEPS_DEG_EXTRA
    k_steps = K_STEPS + K_STEPS_EXTRA
    prod_key = _solver_key(PRODUCTION_SOLVER_CONFIG)
    ref1_key = _solver_key(REFERENCE_SOLVER_CONFIG)
    ref05_key = _solver_key(REF_005)

    eligibility_rows: list[dict] = []
    stop_reasons: list[str] = []
    for rep in reps:
        g0, k0 = rep["gamma0_deg"], rep["K"]
        for param, steps in (("gamma", gamma_steps), ("K", k_steps)):
            for h in steps:
                if param == "gamma":
                    plus = (g0 + h, k0)
                    minus = (g0 - h, k0)
                else:
                    plus = (g0, k0 + h)
                    minus = (g0, k0 - h)
                center = (g0, k0)
                # Production points.
                c_rec = _run_point(g0, k0, PRODUCTION_SOLVER_CONFIG,
                                   env, veh, cache, prod_key, git_commit)
                p_rec = _run_point(plus[0], plus[1],
                                   PRODUCTION_SOLVER_CONFIG, env, veh,
                                   cache, prod_key, git_commit)
                m_rec = _run_point(minus[0], minus[1],
                                   PRODUCTION_SOLVER_CONFIG, env, veh,
                                   cache, prod_key, git_commit)
                q_el = evaluate_stencil(
                    c_rec, p_rec, m_rec, center, plus, minus,
                    exclusion, "qian")
                s_el = evaluate_stencil(
                    c_rec, p_rec, m_rec, center, plus, minus,
                    exclusion, "sanger")
                eligibility_rows.append({
                    "label": rep["label"],
                    "gamma0": g0, "K": k0,
                    "parameter": param, "step": h,
                    "qian_eligible": q_el.eligible,
                    "qian_reasons": list(q_el.reasons),
                    "sanger_eligible": s_el.eligible,
                    "sanger_reasons": list(s_el.reasons),
                })
    _write_json(OUT_DIR / "stencil_eligibility.json", {
        "schema_version": "f4-stencil-eligibility-v1",
        "stencils": eligibility_rows,
    })

    # ---- FD convergence sequences (production + reference) -----------------
    def _fd_sequence(rep, param, h, solver, solver_key, model):
        """Central difference D(h) for every primary output of ``model``."""
        g0, k0 = rep["gamma0_deg"], rep["K"]
        if param == "gamma":
            plus = (g0 + h, k0)
            minus = (g0 - h, k0)
            h_scale = h * np.pi / 180.0
        else:
            plus = (g0, k0 + h)
            minus = (g0, k0 - h)
            h_scale = h
        p_rec = _run_point(plus[0], plus[1], solver, env, veh, cache,
                           solver_key, git_commit)
        m_rec = _run_point(minus[0], minus[1], solver, env, veh, cache,
                           solver_key, git_commit)
        outputs = (QIAN_OUTPUTS if model == "qian" else SANGER_OUTPUTS)
        vector_of = (qian_output_vector if model == "qian"
                     else sanger_output_vector)
        yp = vector_of(p_rec[model])
        ym = vector_of(m_rec[model])
        if yp is None or ym is None:
            return None
        return {
            outputs[i]: (yp[i] - ym[i]) / (2.0 * h_scale)
            for i in range(len(outputs))
        }

    fd_convergence: dict = {}
    reference_derivatives: dict = {}
    for rep in reps:
        label = rep["label"]
        fd_convergence[label] = {"gamma": {}, "K": {}}
        reference_derivatives[label] = {"gamma": {}, "K": {}}
        for param, steps in (("gamma", gamma_steps), ("K", k_steps)):
            for model, model_name in (("qian", "Qian"), ("sanger", "Sanger")):
                seq_prod = []
                seq_ref = []
                for h in steps:
                    d_prod = _fd_sequence(rep, param, h,
                                          PRODUCTION_SOLVER_CONFIG,
                                          prod_key, model)
                    d_ref = _fd_sequence(rep, param, h,
                                         REFERENCE_SOLVER_CONFIG,
                                         ref1_key, model)
                    seq_prod.append(d_prod)
                    seq_ref.append(d_ref)
                # Reference topology gate: plus/minus must match center.
                g0, k0 = rep["gamma0_deg"], rep["K"]
                for h in steps:
                    if param == "gamma":
                        plus = (g0 + h, k0)
                        minus = (g0 - h, k0)
                    else:
                        plus = (g0, k0 + h)
                        minus = (g0, k0 - h)
                    c_ref = _run_point(g0, k0, REFERENCE_SOLVER_CONFIG,
                                       env, veh, cache, ref1_key, git_commit)
                    p_ref = _run_point(plus[0], plus[1],
                                       REFERENCE_SOLVER_CONFIG, env, veh,
                                       cache, ref1_key, git_commit)
                    m_ref = _run_point(minus[0], minus[1],
                                       REFERENCE_SOLVER_CONFIG, env, veh,
                                       cache, ref1_key, git_commit)
                    sigs = {
                        c_ref[model]["exact_topology_signature"],
                        p_ref[model]["exact_topology_signature"],
                        m_ref[model]["exact_topology_signature"],
                    }
                    if len(sigs) > 1:
                        stop_reasons.append(
                            f"REFERENCE_TOPOLOGY_MISMATCH at "
                            f"{label} {param} h={h} model={model_name}")
                fd_convergence[label][param][model_name] = {
                    "steps": list(steps),
                    "production": seq_prod,
                    "reference": seq_ref,
                }
                reference_derivatives[label][param][model_name] = {
                    "steps": list(steps),
                    "reference": seq_ref,
                }

    # ---- Reference self-stability: REF-0.05 on the smallest stable h ------
    ref_stability: dict = {}
    for rep in reps:
        label = rep["label"]
        ref_stability[label] = {}
        for param in ("gamma", "K"):
            h_finest = (gamma_steps[-1] if param == "gamma"
                        else k_steps[-1])
            for model, model_name in (("qian", "Qian"), ("sanger", "Sanger")):
                d05 = _fd_sequence(rep, param, h_finest, REF_005,
                                   ref05_key, model)
                d01 = reference_derivatives[label][param][model_name][
                    "reference"][-1]
                g0, k0 = rep["gamma0_deg"], rep["K"]
                if param == "gamma":
                    plus = (g0 + h_finest, k0)
                    minus = (g0 - h_finest, k0)
                else:
                    plus = (g0, k0 + h_finest)
                    minus = (g0, k0 - h_finest)
                c_ref = _run_point(g0, k0, REF_005, env, veh, cache,
                                   ref05_key, git_commit)
                p_ref = _run_point(plus[0], plus[1], REF_005, env, veh,
                                   cache, ref05_key, git_commit)
                m_ref = _run_point(minus[0], minus[1], REF_005, env, veh,
                                   cache, ref05_key, git_commit)
                sigs = {
                    c_ref[model]["exact_topology_signature"],
                    p_ref[model]["exact_topology_signature"],
                    m_ref[model]["exact_topology_signature"],
                }
                ref_stability[label][f"{param}_{model_name}"] = {
                    "h_finest": h_finest,
                    "ref01_derivative": d01,
                    "ref005_derivative": d05,
                    "topology_identical": len(sigs) == 1,
                }
                if d01 and d05:
                    diffs = {
                        k_: abs(d01.get(k_, 0.0) - d05.get(k_, 0.0))
                        for k_ in d01
                    }
                    ref_stability[label][f"{param}_{model_name}"][
                        "abs_diff"] = diffs
    _write_json(OUT_DIR / "reference_derivatives.json", {
        "schema_version": "f4-reference-derivatives-v1",
        "solver": "REF-0.1 (DOP853 rtol=1e-12 atol=[1e-7,1e-14,1e-10,1e-14] "
                  "max_step=0.1)",
        "reference": reference_derivatives,
        "ref005_stability": ref_stability,
    })

    # ---- Convergence + step policy ------------------------------------------
    policy_notes: list[str] = []
    policy: dict = {"gamma": {}, "K": {}}
    for rep in reps:
        label = rep["label"]
        for param, model in (("gamma", "Sanger"), ("K", "Sanger")):
            steps = gamma_steps if param == "gamma" else k_steps
            seq = fd_convergence[label][param][model]["reference"]
            # Per-output convergence over the eligible step subsequence.
            per_output: dict = {}
            for out in (SANGER_OUTPUTS if model == "Sanger"
                        else QIAN_OUTPUTS):
                vals = [d[out] if d else None for d in seq]
                finite = [v for v in vals if v is not None
                          and np.isfinite(v)]
                diffs = successive_differences(finite) if len(finite) >= 2 \
                    else []
                ref_mag = abs(finite[-1]) if finite else 0.0
                per_output[out] = {
                    "derivatives": vals,
                    "successive_diffs": diffs,
                    "observed_order": (
                        observed_order(diffs) if len(diffs) >= 2 else None),
                    "reference_magnitude": ref_mag,
                    "negligible": ref_mag < 1e-3
                    if param == "gamma" else ref_mag < 1e-2,
                    "plateau": in_plateau(diffs, ref_mag)
                    if len(diffs) >= 2 else False,
                }
            policy[param][label] = per_output
    _write_json(OUT_DIR / "fd_convergence.json", {
        "schema_version": "f4-fd-convergence-v1",
        "gamma_steps_deg": list(gamma_steps),
        "k_steps": list(k_steps),
        "convergence": fd_convergence,
        "policy_diagnostics": policy,
        "plateau_criterion": {
            "rule": "|D(h)-D(h/2)| <= 0.01 * |D_ref| for two consecutive "
                    "differences (dimension-aware relative criterion; "
                    "absolute floors are meaningless across output "
                    "dimensions)",
            "rel_tol": 0.01,
            "negligible_output_threshold": {
                "gamma_per_rad": 1e-3, "K_per_unit": 1e-2},
            "note": "documented in docs/phase_f/f4_fd_convergence.md"},
    })

    # ---- Step-policy freeze (F4 §22–§24) -----------------------------------
    # Global policy: every mandatory representative, every primary output
    # with a non-negligible reference derivative, plateau at the same h
    # (relative plateau criterion, dimension-aware).
    global_gamma = None
    global_k = None
    for h in gamma_steps:
        ok = True
        for rep in reps:
            label = rep["label"]
            for out in SANGER_OUTPUTS:
                d = fd_convergence[label]["gamma"]["Sanger"][
                    "reference"]
                idx = gamma_steps.index(h)
                if idx + 2 > len(d):
                    ok = False
                    break
                vals = [d[j][out] for j in range(idx, min(idx + 3, len(d)))
                        if d[j]]
                if len(vals) < 3:
                    ok = False
                    break
                if max(abs(v) for v in vals) < 1e-3:
                    continue  # negligible output: not a criterion
                diffs = successive_differences(vals)
                if not in_plateau(diffs, abs(vals[-1])):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            global_gamma = h
            break
    for h in k_steps:
        ok = True
        for rep in reps:
            label = rep["label"]
            for out in SANGER_OUTPUTS:
                d = fd_convergence[label]["K"]["Sanger"]["reference"]
                idx = k_steps.index(h)
                if idx + 2 > len(d):
                    ok = False
                    break
                vals = [d[j][out] for j in range(idx, min(idx + 3, len(d)))
                        if d[j]]
                if len(vals) < 3:
                    ok = False
                    break
                if max(abs(v) for v in vals) < 1e-2:
                    continue
                diffs = successive_differences(vals)
                if not in_plateau(diffs, abs(vals[-1])):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            global_k = h
            break

    step_policy = {
        "schema_version": "f4-step-policy-v1",
        "gamma_policy": "GLOBAL_STEP_POLICY" if global_gamma is not None
        else "ADAPTIVE_STEP_POLICY",
        "gamma_step_deg": global_gamma,
        "K_policy": "GLOBAL_STEP_POLICY" if global_k is not None
        else "ADAPTIVE_STEP_POLICY",
        "K_step": global_k,
        "adaptive_rule": (
            "largest-safe-converged central step per (representative, "
            "parameter): gate + relative plateau (|D(h)-D(h/2)| <= 0.01 "
            "* |D_ref| for two consecutive differences) + reference "
            "audit" if (global_gamma is None or global_k is None)
            else None),
        "notes": policy_notes,
    }
    _write_json(OUT_DIR / "step_policy.json", step_policy)
    print(f"[policy] gamma: {step_policy['gamma_policy']} "
          f"{step_policy['gamma_step_deg']}")
    print(f"[policy] K    : {step_policy['K_policy']} "
          f"{step_policy['K_step']}")

    # ---- Local Jacobians at the approved step -------------------------------
    def _approved_step(param, label):
        if param == "gamma":
            return global_gamma if global_gamma is not None else None
        return global_k if global_k is not None else None

    jacobians: dict = {}
    for rep in reps:
        label = rep["label"]
        jacobians[label] = {"qian": {}, "sanger": {}}
        for param, h in (("gamma", global_gamma), ("K", global_k)):
            if h is None:
                continue
            for model in ("qian", "sanger"):
                d = _fd_sequence(rep, param, h, PRODUCTION_SOLVER_CONFIG,
                                 prod_key, model)
                jacobians[label][model][param] = d
    _write_json(OUT_DIR / "local_jacobians.json", {
        "schema_version": "f4-local-jacobians-v1",
        "unit_notes": {
            "d/dgamma0": "per radian (canonical); per-degree = per-rad "
                         "* pi/180",
            "d/dK": "per unit K",
            "qian_shape": list(QIAN_JACOBIAN_SHAPE),
            "sanger_shape": list(SANGER_JACOBIAN_SHAPE),
        },
        "jacobians": jacobians,
    })

    # ---- Production-vs-reference audit ---------------------------------------
    prod_ref: dict = {}
    for rep in reps:
        label = rep["label"]
        prod_ref[label] = {}
        for param in ("gamma", "K"):
            steps = gamma_steps if param == "gamma" else k_steps
            prod_ref[label][param] = {}
            for model in ("Qian", "Sanger"):
                outs = (QIAN_OUTPUTS if model == "Qian" else SANGER_OUTPUTS)
                seq_p = fd_convergence[label][param][model]["production"]
                seq_r = fd_convergence[label][param][model]["reference"]
                errs = {}
                for i, out in enumerate(outs):
                    abs_errs = []
                    for dp, dr in zip(seq_p, seq_r):
                        if dp is None or dr is None:
                            continue
                        abs_errs.append(abs(dp[out] - dr[out]))
                    ref_last = seq_r[-1][out] if seq_r[-1] else None
                    errs[out] = {
                        "abs_error_range": (
                            [min(abs_errs), max(abs_errs)]
                            if abs_errs else None),
                        "reference_numerical_floor": (
                            abs(ref_last) * 0.01 if ref_last else None),
                    }
                prod_ref[label][param][model] = errs
    _write_json(OUT_DIR / "production_vs_reference.json", {
        "schema_version": "f4-production-vs-reference-v1",
        "note": "absolute errors per output dimension; near-zero "
                "derivatives are NOT reported as large relative %",
        "audit": prod_ref,
    })

    # ---- Summary -------------------------------------------------------------
    summary = {
        "schema_version": "f4-summary-v1",
        "git_commit": git_commit,
        "representatives": reps,
        "output_vectors": {
            "qian": list(QIAN_OUTPUTS),
            "sanger": list(SANGER_OUTPUTS),
        },
        "gamma_candidate_steps_deg": list(gamma_steps),
        "k_candidate_steps": list(k_steps),
        "step_policy": step_policy,
        "stencil_counts": {
            "total_candidate_stencils": len(eligibility_rows),
            "qian_eligible": sum(1 for r in eligibility_rows
                                 if r["qian_eligible"]),
            "sanger_eligible": sum(1 for r in eligibility_rows
                                   if r["sanger_eligible"]),
            "boundary_intersection_rejected": sum(
                1 for r in eligibility_rows
                if any(x.startswith("BOUNDARY_INTERSECTION")
                       for x in r["sanger_reasons"])),
            "topology_change_rejected": sum(
                1 for r in eligibility_rows
                if any(x.startswith("TOPOLOGY_CHANGE")
                       for x in r["sanger_reasons"])),
            "recovered_rejected": sum(
                1 for r in eligibility_rows
                if any(x.startswith("RECOVERED_EVENT")
                       for x in r["sanger_reasons"])),
            "guardrail_rejected": sum(
                1 for r in eligibility_rows
                if any(x.startswith("OUTSIDE_DOMAIN")
                       for x in r["sanger_reasons"])),
        },
        "multiplicity_audit": multiplicity_audit,
        "stop_gate_triggered": bool(stop_reasons),
        "stop_gate_reasons": stop_reasons,
        "ready_for_F5": not stop_reasons,
        "total_runtime_s": time.time() - t_start,
    }
    _write_json(OUT_DIR / "f4_summary.json", summary)
    _write_json(OUT_DIR / "stop_gate_report.json", {
        "schema_version": "f4-stop-gate-report-v1",
        "stop_gate_triggered": bool(stop_reasons),
        "reasons": stop_reasons,
    })

    print("\n" + "=" * 72)
    print(f"representatives      : {len(reps)}")
    print(f"stencils             : {summary['stencil_counts']}")
    print(f"step policy          : gamma={step_policy['gamma_policy']} "
          f"K={step_policy['K_policy']}")
    print(f"stop gates           : {stop_reasons}")
    print(f"ready_for_F5         : {summary['ready_for_F5']}")
    print(f"total runtime        : {summary['total_runtime_s']:.1f} s")
    print("F4 RUN: " + ("COMPLETE" if not stop_reasons else "BLOCKED"))
    return 0 if not stop_reasons else 2


if __name__ == "__main__":
    sys.exit(main())
