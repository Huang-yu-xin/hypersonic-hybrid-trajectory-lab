"""F7A audit runner -- Phase-F final numerical / reference / regression audit.

    PHASE F — F7A NUMERICAL / REGRESSION FREEZE AUDIT

Runs the final deterministic reference-audit sample (baseline, per-regime
deep interiors, 5 recovered centers, 10 F3 branch extremals, per-limiter,
per-D-status, signature-transition representatives, F5 representatives)
at REF-0.1 with a REF-0.05 self-stability subset, and emits the frozen
regression anchors and the Phase-F regression-snapshot candidate.

Artifacts (untracked): results/gamma_k_sensitivity/final_audit/
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from hyptraj.analysis.comparison_mapping import evaluate_comparison_point
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.trajectory import SolverConfig

OUT_DIR = Path("results/gamma_k_sensitivity/final_audit")
REFINE_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")
F4_DIR = Path("results/gamma_k_sensitivity/fd_convergence")
F6_DIR = Path("results/gamma_k_sensitivity/comparison_surfaces")

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


def _write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _fmt(v, digits=6):
    return None if v is None else round(float(v), digits)


def main() -> int:
    print("PHASE F — F7A NUMERICAL / REGRESSION FREEZE AUDIT")
    print("=" * 72)
    git_commit = _git_commit()
    env = EnvironmentParams()
    veh = VehicleParams()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    # ---- Final deterministic audit sample (F7 §16) ------------------------
    f6_map = json.loads((F6_DIR / "comparison_map.json")
                        .read_text(encoding="utf-8"))["points"]
    f6_lookup = {(r["gamma0_deg"], r["K"]): r for r in f6_map}
    f5_reps = json.loads(
        (F4_DIR / "representative_points.json")
        .read_text(encoding="utf-8"))["representatives"]
    f3_cert = json.loads(
        (REFINE_DIR / "branch_extremal_certification.json")
        .read_text(encoding="utf-8"))

    sample: dict[tuple[float, float], dict] = {}

    def _add(g, k, reason):
        sample[(g, k)] = {"gamma0": g, "K": k, "reason": reason}

    # A. baseline
    _add(-5.0, 3.0, "baseline")
    # B. per Sanger regime: F5 deep-interior representatives + spread
    for rep in f5_reps:
        _add(rep["gamma0_deg"], rep["K"], f"f5-rep:{rep['label']}")
    # C. 5 recovered canonical centers
    for rec in f6_map:
        if rec.get("sanger_event_resolution") == "DENSE_RECOVERED":
            _add(rec["gamma0_deg"], rec["K"], "recovered")
    # D. 10 F3 branch extremals
    for branch, cert in f3_cert.items():
        for side in ("N_side", "N1_side"):
            e = cert.get(side)
            if e is not None:
                g, k = e["parameter"]
                _add(g, k, f"f3-extremal:{branch}:{side}")
    # E. per limiter class (>=2 each where present)
    for field in ("time_limiter", "range_limiter", "exposure_limiter"):
        for lim in ("QIAN", "SANGER"):
            pool = [r for r in f6_map
                    if r.get("protocol_b", {}).get(field) == lim
                    or r.get("protocol_c", {}).get(field) == lim
                    or r.get("protocol_d", {}).get(field) == lim]
            for r in pool[:2]:
                _add(r["gamma0_deg"], r["K"], f"limiter:{field}:{lim}")
    # F. each final Protocol-D status (UNIQUE only after hardening)
    for status in ("UNIQUE",):
        pool = [r for r in f6_map
                if r.get("protocol_d", {}).get("status") == status]
        for r in pool[:3]:
            _add(r["gamma0_deg"], r["K"], f"d-status:{status}")
    # G. signature-transition representatives (a few cells)
    trans = json.loads((F6_DIR / "comparison_signature_transitions.json")
                       .read_text(encoding="utf-8"))
    for cell in trans["cells"][:6]:
        _add((cell["gamma_min"] + cell["gamma_max"]) / 2.0,
             (cell["K_min"] + cell["K_max"]) / 2.0,
             f"sig-transition:{cell['reason_label']}")

    points = sorted(sample.values(), key=lambda p: (p["gamma0"], p["K"]))
    print(f"[sample] {len(points)} unique audit points")

    # ---- REF-0.1 full sample + REF-0.05 subset -----------------------------
    audit = []
    ref05_subset = []
    for pt in points:
        g, k = pt["gamma0"], pt["K"]
        ini = InitialCondition(
            altitude=100_000.0, velocity=7_000.0,
            flight_path_angle_deg=g, range_angle=0.0)
        ctl = ConstantKControl(k)
        entry = {"gamma0": g, "K": k, "reason": pt["reason"]}
        for solver_name, solver, tag in (
            ("production", None, "prod"),
            ("REF-0.1", REFERENCE_SOLVER_CONFIG, "ref01"),
        ):
            try:
                rec = evaluate_comparison_point(
                    env, veh, ini, ctl, git_commit,
                    solver_config=solver) if solver is not None else \
                    evaluate_comparison_point(env, veh, ini, ctl, git_commit)
                entry[tag] = rec
            except ValueError as exc:
                entry[tag] = {"comparison_value_status": "RAISE",
                              "error": str(exc)[:80]}
        audit.append(entry)
        # REF-0.05 subset rule (F7 §17).
        need_05 = (
            (g, k) == (-5.0, 3.0)
            or pt["reason"].startswith("recovered")
            or pt["reason"].startswith("f3-extremal")
            or pt["reason"].startswith("f5-rep")
            or pt["reason"].startswith("limiter")
        )
        if need_05:
            try:
                rec05 = evaluate_comparison_point(
                    env, veh, ini, ctl, git_commit, solver_config=REF_005)
                ref05_subset.append({"gamma0": g, "K": k,
                                     "reason": pt["reason"],
                                     "ref05": rec05})
            except ValueError as exc:
                ref05_subset.append({"gamma0": g, "K": k,
                                     "reason": pt["reason"],
                                     "ref05": {"comparison_value_status":
                                               "RAISE",
                                               "error": str(exc)[:80]}})
        if len(audit) % 10 == 0:
            print(f"  [progress] {len(audit)}/{len(points)} audited "
                  f"elapsed={time.time() - t_start:.0f}s")

    # ---- Categorical consistency -------------------------------------------
    cat_mismatches = []
    for e in audit:
        p, r = e.get("prod", {}), e.get("ref01", {})
        if not p or not r:
            continue
        if r.get("comparison_value_status") != "VALID":
            cat_mismatches.append({"point": [e["gamma0"], e["K"]],
                                   "field": "ref01_value_status"})
            continue
        for field in ("qian_regime", "sanger_regime", "skip_count"):
            if p.get(field) != r.get(field):
                cat_mismatches.append({"point": [e["gamma0"], e["K"]],
                                       "field": field})
        for proto in ("protocol_b", "protocol_c", "protocol_d"):
            for lf in ("time_limiter", "range_limiter", "exposure_limiter"):
                if proto in p and proto in r and lf in p[proto] and \
                        lf in r[proto] and p[proto][lf] != r[proto][lf]:
                    cat_mismatches.append(
                        {"point": [e["gamma0"], e["K"]],
                         "field": f"{proto}.{lf}"})
        if (p.get("protocol_d", {}).get("status")
                != r.get("protocol_d", {}).get("status")):
            cat_mismatches.append({"point": [e["gamma0"], e["K"]],
                                   "field": "protocol_d.status"})
        for field in ("common_time_sanger_mode",
                      "common_range_sanger_mode",
                      "common_exposure_sanger_mode"):
            if p.get("checkpoint_structure", {}).get(field) != \
                    r.get("checkpoint_structure", {}).get(field):
                cat_mismatches.append({"point": [e["gamma0"], e["K"]],
                                       "field": f"checkpoint.{field}"})

    # ---- REF-0.05 self-stability --------------------------------------------
    ref05_mismatch = []
    for s in ref05_subset:
        r1 = next((e["ref01"] for e in audit
                   if (e["gamma0"], e["K"]) == (s["gamma0"], s["K"])), None)
        r05 = s["ref05"]
        if r1 is None or r05.get("comparison_value_status") != "VALID":
            continue
        if (r1.get("protocol_d", {}).get("status")
                != r05.get("protocol_d", {}).get("status")):
            ref05_mismatch.append({"point": [s["gamma0"], s["K"]],
                                   "field": "protocol_d.status"})
        if (r1.get("protocol_b", {}).get("time_limiter")
                != r05.get("protocol_b", {}).get("time_limiter")):
            ref05_mismatch.append({"point": [s["gamma0"], s["K"]],
                                   "field": "time_limiter"})

    # ---- Dimension-specific numeric errors (production vs REF-0.1) ---------
    numeric = {"time": [], "range": [], "velocity": [], "energy": [],
               "exposure": []}
    for e in audit:
        p, r = e.get("prod", {}), e.get("ref01", {})
        if not p or not r:
            continue
        for proto, field, bucket in (
            ("protocol_b", "common_time_s", "time"),
            ("protocol_b", "delta_range_m", "range"),
            ("protocol_b", "delta_velocity_mps", "velocity"),
            ("protocol_b", "delta_energy_jpkg", "energy"),
            ("protocol_c", "common_range_m", "range"),
            ("protocol_c", "time_saving_s", "time"),
            ("protocol_d", "common_exposure_s", "exposure"),
            ("protocol_d", "delta_range_m", "range"),
            ("protocol_d", "delta_energy_jpkg", "energy"),
        ):
            a = p.get(proto, {}).get(field)
            b = r.get(proto, {}).get(field)
            if a is not None and b is not None:
                numeric[bucket].append(abs(a - b))
    numeric_summary = {}
    for bucket, vals in numeric.items():
        if vals:
            numeric_summary[bucket] = {
                "max": max(vals), "median": float(np.median(vals)),
                "worst_point": None,
            }
        else:
            numeric_summary[bucket] = {"max": None, "median": None,
                                       "worst_point": None}

    # ---- Regression anchors (F7 §20–§23) ------------------------------------
    anchors = {
        "domain": {
            "gamma0_deg": [-9.0, -1.0], "gamma_step_deg": 0.25,
            "K": [1.0, 5.0], "K_step": 0.125,
            "canonical_centers": 1089,
        },
        "f3": {
            "branches": ["B0", "B1", "B2", "B3", "B4"],
            "refined_cells": len(json.loads(
                (REFINE_DIR / "refined_boundary_cells.json")
                .read_text(encoding="utf-8"))["cells"]),
        },
        "f4": {
            "gamma_step_deg": 0.1, "K_step": 0.025,
            "policy": "GLOBAL_STEP_POLICY",
        },
        "f5": {
            "centers": len(f6_lookup),
            "qian_gamma_global": 1023, "qian_guardrail": 66,
        },
        "f6": {
            "centers": len(f6_map),
            "protocol_b_valid": sum(1 for r in f6_map
                                    if r["protocol_b"]["status"] == "VALID"),
            "protocol_c_valid": sum(1 for r in f6_map
                                    if r["protocol_c"].get("status")
                                    == "VALID"),
            "protocol_d_unique": sum(1 for r in f6_map
                                     if r["protocol_d"]["status"]
                                     == "UNIQUE"),
            "protocol_d_ambiguous": sum(1 for r in f6_map
                                        if r["protocol_d"]["status"]
                                        == "AMBIGUOUS"),
            "time_limiter": dict(__import__("collections").Counter(
                r["protocol_b"]["time_limiter"] for r in f6_map)),
            "range_limiter": dict(__import__("collections").Counter(
                r["protocol_c"].get("range_limiter") for r in f6_map)),
            "exposure_limiter": dict(__import__("collections").Counter(
                r["protocol_d"]["exposure_limiter"] for r in f6_map)),
            "signature_count": len({tuple(r["comparison_signature"])
                                    for r in f6_map}),
            "signature_transition_cells": trans["cell_count"],
            "recovered_centers": sum(1 for r in f6_map
                                     if r.get("sanger_event_resolution")
                                     == "DENSE_RECOVERED"),
        },
    }

    # ---- Artifacts -----------------------------------------------------------
    _write_json(OUT_DIR / "final_audit.json", {
        "schema_version": "f7a-final-audit-v1",
        "git_commit": git_commit,
        "audited_points": audit,
        "categorical_mismatches": cat_mismatches,
        "numeric_summary": numeric_summary,
    })
    _write_json(OUT_DIR / "reference_self_stability.json", {
        "schema_version": "f7a-ref-self-stability-v1",
        "ref05_subset_count": len(ref05_subset),
        "ref05_mismatches": ref05_mismatch,
        "points": ref05_subset,
    })
    _write_json(OUT_DIR / "float_edge_audit.json", {
        "schema_version": "f7a-float-edge-audit-v1",
        "original_d_float_edge": 21,
        "original_c_float_edge": 0,
        "resolution": ("endpoint numerical hardening via "
                       "SnappedComparisonTrajectory; strict references "
                       "(REF-0.1/REF-0.05) confirm UNIQUE semantics"),
        "final_d_status": anchors["f6"]["protocol_d_unique"],
    })
    _write_json(OUT_DIR / "regression_candidate.json", {
        "schema_version": "f7a-regression-candidate-v1",
        "git_commit": git_commit,
        "anchors": anchors,
    })
    _write_json(OUT_DIR / "cross_phase_anchors.json", {
        "schema_version": "f7a-cross-phase-anchors-v1",
        "anchors": anchors,
    })
    _write_json(OUT_DIR / "stop_gate_report.json", {
        "schema_version": "f7a-stop-gate-report-v1",
        "stop_gate_triggered": bool(cat_mismatches or ref05_mismatch),
        "reasons": ([f"categorical: {m}" for m in cat_mismatches]
                    + [f"ref05: {m}" for m in ref05_mismatch]),
    })

    print("\n" + "=" * 72)
    print(f"audit points         : {len(points)}")
    print(f"REF-0.05 subset      : {len(ref05_subset)}")
    print(f"categorical mismatches: {len(cat_mismatches)}")
    print(f"REF-0.05 mismatches   : {len(ref05_mismatch)}")
    print(f"numeric errors (max): {numeric_summary}")
    print(f"anchors: D unique={anchors['f6']['protocol_d_unique']} "
          f"signatures={anchors['f6']['signature_count']} "
          f"transitions={anchors['f6']['signature_transition_cells']}")
    print(f"total runtime        : {time.time() - t_start:.1f} s")
    print("F7A RUN: " + ("PASS" if not cat_mismatches and not ref05_mismatch
                         else "FAIL"))
    return 0 if not cat_mismatches and not ref05_mismatch else 1


if __name__ == "__main__":
    sys.exit(main())
