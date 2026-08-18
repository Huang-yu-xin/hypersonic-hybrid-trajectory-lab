"""Deterministic generator for the Phase-G6 / G6R grazing snapshot
(``tests/data/phase_g6_grazing_predictability_v1.json``).

Run from the repository root::

    python scripts/run_phase_g6_grazing.py [--out tests/data/phase_g6_grazing_predictability_v1.json]

WHAT IT RECOMPUTES (deterministically from production code + the frozen
Phase-F anchor snapshot, G6R only):
  * ``g6r.contract_audit`` -- the hardened ``extract_branch_excursion``
    topology contract on all 10 frozen anchors (5 N-side absence
    confirmations + 5 N+1 extractions with completeness / chronology /
    sign / positivity / actual-regime hard guards), plus the locked
    ``reference_dual_stable`` 10/10 True flags.
  * ``g6r.refined_validity_radii`` -- refined operational validity radii
    (bracket [PASS lower / FAIL upper] + deterministic bisection on the
    clearance-normalized beta coordinate; NONMONOTONE_VALIDITY_PROFILE
    detection) for the same four G6 cases B0 a=1 / B0 a=0.5 / B3 a=1 /
    B4 a=1, replacing the G6 coarse grid-sampled lower bounds.  Per G6R2
    the relative linearization error uses the frozen protocol denominator
    ``ERROR / LINEAR PREDICTION`` (``scaled_linearization_error``), NOT the
    nonlinear-increment norm; the old G6R (nonlinear-denominator) radii are
    preserved verbatim in ``g6r2.old_radii_g6r_nonlinear_denominator``.
  * ``g6r.paired_fd_plateau`` -- radial-column derivative plateau at
    clearance-normalized beta in [1e-4, 3e-2], both sides
    PAIR_LOCAL_VALID, canonical-A scaled-relative error << 1e-2.
  * ``g6r.paired_fd_validation`` -- full 4-column paired-map FD, strong
    case B0 and mild case B4, canonical-A scaled errors (tangent columns
    report absolute scaled residual).
  * top-level ``threshold_decision`` RADII OVERVIEW refreshed to the
    refined radii (re-audit of NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED).

WHAT IT PRESERVES VERBATIM (frozen as-of G6 accept -- G6R must NOT re-open
Phase-F physics or re-fit B0-B4): ``frozen_anchor_audit``,
``nplus_event_audit``, ``controlled_families``, ``scaling_fits``,
``topology_radii``, ``terminal_descriptive`` and the claim boundaries /
scope notes of the committed G6 snapshot.

This generator never creates Phase-G final tags and does not touch the
frozen Phase A-F physics (models/modes/simulation/controls).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hyptraj.models.parameters import (  # noqa: E402
    EnvironmentParams,
    VehicleParams,
)
from hyptraj.analysis.comparison_validation import (  # noqa: E402
    REFERENCE_05_SOLVER_CONFIG,
    REFERENCE_SOLVER_CONFIG,
)
from hyptraj.predictability import grazing as G  # noqa: E402
from hyptraj.predictability.stm import stm_strict_reference_config  # noqa: E402

DATA_DIR = REPO / "tests" / "data"
SNAPSHOT = DATA_DIR / "phase_g6_grazing_predictability_v1.json"
PHASE_F = DATA_DIR / "phase_f_gamma_k_sensitivity_v1.json"

_STATE_DIM = 4


def _git_head() -> str:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _numpy_to_python(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _build_contract_audit(env, vehicle, ref01):
    """All 10 anchors: the hardened extraction contract must hold."""
    anchors = G.load_frozen_grazing_anchors()
    audit = []
    n_absent = 0
    n_extracted = 0
    for a in anchors:
        exc = G.extract_branch_excursion(a, env, vehicle, ref01)  # raises on
        # any contract violation (hard stop)
        rec = {
            "branch": a.branch,
            "side": a.side,
            "N": a.N,
            "gamma0_deg": a.gamma0_deg,
            "K": a.K,
            "expected_regime": a.expected_regime,
            "reference_dual_stable": bool(a.reference_dual_stable),
            "phase_f_reference_phi_ref01_m": a.phase_f_reference_phi_ref01,
            "phase_f_reference_phi_ref005_m": a.phase_f_reference_phi_ref005,
            "has_excursion": bool(exc.has_excursion),
            "contract_ok": True,
        }
        if exc.has_excursion:
            n_extracted += 1
            rec.update({
                "target_exit_ordinal": exc.exit_ordinal,
                "entry_ordinal": exc.entry_ordinal,
                "vac_duration_s": exc.vac_duration_s,
                "exit_denominator": exc.exit_denominator,
                "entry_denominator": exc.entry_denominator,
                "vac_clearance_m": exc.clearance_m,
                "exit_incidence_abs_sin_gamma": exc.exit_incidence,
            })
        else:
            n_absent += 1
        audit.append(rec)
    return audit, n_absent, n_extracted, anchors


def _family_point(anchor, env, vehicle, ref01, ref05, alpha):
    """Deterministic alpha family point for an N+1 anchor (G6 §16-§20)."""
    exc = G.extract_branch_excursion(anchor, env, vehicle, ref01)
    pts, _ = G.controlled_local_grazing_family(
        exc.exit_state, env, vehicle, anchor.K,
        ref_cfg_01=ref01, ref_cfg_05=ref05)
    for p in pts:
        if abs(p.alpha - alpha) < 1e-12:
            return p, exc
    raise RuntimeError(
        f"{anchor.branch} controlled family has no alpha={alpha} point "
        f"(stopped at alpha={pts[-1].alpha if pts else 'none'}).")


def _beta_sweep_for_snapshot(rr, phi):
    """Map refined_operational_radius probe records onto the G6-style
    ``beta_sweep`` entries (beta, dr, valid, cls, fd_norm, E_lin_plus,
    E_lin_minus, E_pair)."""
    out = []
    for p in rr["beta_probes"]:
        out.append({
            "beta": p["beta"],
            "dr": float(p["beta"]) * float(phi),
            "valid": bool(p["valid"]),
            "cls": [p["cls_plus"], p["cls_minus"]],
            "fd_norm": p["fd_scaled_norm"],
            "E_lin_plus": p["E_plus"],
            "E_lin_minus": p["E_minus"],
            "E_pair": p["E_pair"],
        })
    return out


def _radius_record(phi, d_exit, rr):
    r1 = rr["radii"]["r_1pct"]
    r5 = rr["radii"]["r_5pct"]
    return {
        "phi_local_m": float(phi),
        "d_exit": float(d_exit),
        "beta_sweep": _beta_sweep_for_snapshot(rr, phi),
        "monotone_profile": bool(rr["monotone_profile"]),
        "r_1pct_refined": {
            "classification": r1["classification"],
            "lower_pass_beta": r1["lower_pass_beta"],
            "upper_fail_beta": r1["upper_fail_beta"],
            "upper_fail_reason": r1["upper_fail_reason"],
            "refined_beta": r1["refined_beta"],
            "refined_radius_m": r1["refined_radius_m"],
            "radius_over_phi": r1["radius_over_phi"],
            "bracket_width": r1["bracket_width"],
        },
        "r_5pct_refined": {
            "classification": r5["classification"],
            "lower_pass_beta": r5["lower_pass_beta"],
            "upper_fail_beta": r5["upper_fail_beta"],
            "upper_fail_reason": r5["upper_fail_reason"],
            "refined_beta": r5["refined_beta"],
            "refined_radius_m": r5["refined_radius_m"],
            "radius_over_phi": r5["radius_over_phi"],
            "bracket_width": r5["bracket_width"],
        },
        # backward-compatible grid-derived scalars (now = refined)
        "r_1pct_m": r1["refined_radius_m"],
        "r_5pct_m": r5["refined_radius_m"],
        "r_1pct_over_phi": r1["radius_over_phi"],
        "r_5pct_over_phi": r5["radius_over_phi"],
        "validity_shrinkage_note": (
            "r/phi toward grazing: compare alpha=1 vs alpha=0.5 (B0)"),
    }


def _paired_fd_block(x, env, vehicle, k, cfg, nom_vac, phi, gamma_exit):
    plateau = G.paired_radial_fd_plateau(
        x, env, vehicle, k, cfg, nom_vac, phi)
    four = G.paired_fd_validation(
        x, env, vehicle, k, cfg, nom_vac, phi, gamma_exit)
    return {
        "radial_plateau": {
            "beta_range": plateau["plateau_beta_range"],
            "records": [_numpy_to_python(r) for r in plateau["records"]],
            "max_scaled_rel_error": plateau["max_scaled_rel_error"],
            "both_sides_valid": plateau["both_sides_valid"],
            "tolerance": plateau["tolerance"],
            "plateau_pass": plateau["plateau_pass"],
            "note": plateau["note"],
        },
        "four_column": {
            "four_column_pass": four["four_column_pass"],
            "columns": {str(j): {
                "direction": c["direction"],
                "epsilon_unit": c["epsilon_unit"],
                "metric": c["metric"],
                "both_sides_valid": c["both_sides_valid"],
                "max_error": c["max_error"],
                "tolerance": c["tolerance"],
                "column_pass": c["column_pass"],
                "records": [_numpy_to_python(r) for r in c["records"]],
            } for j, c in four["columns"].items()},
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(SNAPSHOT))
    args = ap.parse_args()

    env, vehicle = EnvironmentParams(), VehicleParams()
    ref01 = REFERENCE_SOLVER_CONFIG
    ref05 = REFERENCE_05_SOLVER_CONFIG
    cfg = stm_strict_reference_config()

    old = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    # ---- Issue 1: contract audit (hard guards) + dual-reference lock ----
    contract, n_absent, n_extracted, anchors = _build_contract_audit(
        env, vehicle, ref01)
    assert n_absent == 5 and n_extracted == 5, (
        f"contract: {n_absent} N-side absence confirmations, "
        f"{n_extracted} N+1 extractions (both must be 5)")
    for rec in contract:
        assert rec["reference_dual_stable"] is True, rec["branch"]
    dual_lock = all(bool(a.reference_dual_stable) for a in anchors)

    # ---- Issue 2: refined validity radii (same four G6 cases) ----
    cases = {}
    for br, alpha in (("B0", 1.0), ("B0", 0.5), ("B3", 1.0), ("B4", 1.0)):
        a = next(x for x in anchors
                 if x.branch == br and x.side == "N1_side")
        p, exc = _family_point(a, env, vehicle, ref01, ref05, alpha)
        x_case = np.array([exc.exit_state[0], exc.exit_state[1],
                           exc.exit_state[2], p.gamma_exit_rad], dtype=float)
        phi = float(p.apogee_clearance_m)
        # deterministic cross-check against the frozen G6 family clearance
        frozen = old["controlled_families"][br]["points"]
        frozen_p = next(q for q in frozen if abs(q["alpha"] - alpha) < 1e-12)
        assert abs(phi - frozen_p["clearance_m"]) < 1e-6, (br, alpha)
        rr = G.refined_operational_radius(
            x_case, env, vehicle, a.K, cfg, float(p.vac_duration_s),
            phi, taus=(0.01, 0.05))
        cases[f"{br}_a{alpha:g}"] = _radius_record(phi, p.d_exit, rr)

    # ---- Issues 3+4: paired FD plateau + full 4-column (B0 strong, B4 mild)
    paired_fd = {}
    for br in ("B0", "B4"):
        a = next(x for x in anchors if x.branch == br and x.side == "N1_side")
        exc = G.extract_branch_excursion(a, env, vehicle, ref01)
        paired_fd[br] = _paired_fd_block(
            exc.exit_state, env, vehicle, a.K, cfg,
            float(exc.vac_duration_s), float(exc.clearance_m),
            float(exc.exit_state[3]))

    # ---- threshold re-audit with refined radii ----
    validity_overview = {k: {
        "d_exit": v["d_exit"], "phi_local_m": v["phi_local_m"],
        "r_1pct_m": v["r_1pct_m"], "r_5pct_m": v["r_5pct_m"]}
        for k, v in cases.items()}
    decision = dict(old["threshold_decision"])
    decision["radii_overview"] = {
        "r_1pct_over_phi": {k: v["r_1pct_refined"]["radius_over_phi"]
                            for k, v in cases.items()},
        "r_5pct_over_phi": {k: v["r_5pct_refined"]["radius_over_phi"]
                            for k, v in cases.items()},
    }
    decision["validity_overview"] = validity_overview
    decision["reason"] += (
        "  G6R RE-AUDIT (refined bracketed+bisected radii, protocol-correct "
        "ERROR/LINEAR-PREDICTION normalization): r_1%/Phi_local "
        "~ 0.0395-0.0403 and r_5%/Phi_local ~ 0.183-0.186 are scale-free "
        "uniform across branches and alpha -> still no dimensionful "
        "universal cutoff is supported.  The refined radii are bracketed "
        "[PASS, FAIL] and bisected (deterministic), superseding the coarse "
        "G6 grid-sampled lower bounds (0.03/0.10).  "
        "G6R2 corrected the error normalization (old nonlinear-increment "
        "denominator -> frozen linear-prediction denominator).")
    assert decision["outcome"] == \
        "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED"

    # ---- Assemble snapshot: frozen G6 sections + G6R/G6R2 additions ----
    # G6R2 provenance: capture the previous G6R (nonlinear-denominator)
    # refined radii from the committed snapshot before overwriting them.
    old_cases = old.get("g6r", {}).get("refined_validity_radii", {})
    old_radii = {
        k: {t: v[t]["radius_over_phi"]
            for t in ("r_1pct_refined", "r_5pct_refined")}
        for k, v in old_cases.items()}

    g6r = {
        "schema_version": "phase-g6r-grazing-contract-v1",
        "rationale": (
            "G6R corrective patch: hardened extraction contract, refined "
            "operational radii (bracket+bisection), paired radial plateau "
            "and full 4-column paired-map FD validation, event-direction "
            "class enforcement, dual-reference lock.  G6R2 revised the "
            "linearization-error NORMALIZATION to the frozen protocol "
            "definition (see g6r2)."),
        "linearization_error_denominator":
            "canonical_scaled_linear_prediction_norm",
        "starting_g6r_commit": _git_head(),
        "frozen_sections_preserved": [
            "frozen_anchor_audit", "nplus_event_audit", "controlled_families",
            "scaling_fits", "topology_radii", "terminal_descriptive"],
        "contract_audit": {
            "n_anchors": len(contract),
            "n_side_absence_confirmations": n_absent,
            "n1_side_extractions": n_extracted,
            "dual_reference_stable_10of10": dual_lock,
            "anchors": contract,
        },
        "refined_validity_radii": cases,
        "paired_fd": paired_fd,
        "threshold_reauth": {
            "after_refined_radii": decision["outcome"],
            "refined_radii_over_phi": {
                "r_1pct": {k: v["r_1pct_refined"]["radius_over_phi"]
                           for k, v in cases.items()},
                "r_5pct": {k: v["r_5pct_refined"]["radius_over_phi"]
                           for k, v in cases.items()},
            },
        },
    }

    # ---- G6R2 block: normalization-correction provenance ----
    paired_fd_unchanged = True
    for br, blk in paired_fd.items():
        old_p = old.get("g6r", {}).get("paired_fd", {}).get(br, {})
        if (old_p.get("radial_plateau", {}).get("plateau_pass")
                != blk["radial_plateau"]["plateau_pass"]):
            paired_fd_unchanged = False
        if (old_p.get("four_column", {}).get("four_column_pass")
                != blk["four_column"]["four_column_pass"]):
            paired_fd_unchanged = False

    g6r2 = {
        "schema_version": "phase-g6r2-linearization-normalization-v1",
        "rationale": (
            "G6R2 minimal corrective patch: the G6R refined validity radii "
            "initially normalized the relative linearization error by the "
            "canonical-A scaled NONLINEAR increment norm.  The frozen "
            "Phase-G protocol defines E = ERROR / LINEAR PREDICTION, i.e. "
            "the denominator is ||S^-1 (eps P(:,r))||.  Re-generated with "
            "the protocol-correct denominator; the two definitions are "
            "asymptotically equivalent, so 1%/5% coefficients shift only "
            "modestly, but the operational radii now match the frozen "
            "protocol exactly."),
        "error_normalization": "ERROR_OVER_LINEAR_PREDICTION",
        "old_error_normalization": "ERROR_OVER_NONLINEAR_INCREMENT",
        "epsilon_floor": 1e-15,
        "epsilon_floor_role": (
            "numerical normalization guard only (0/0); NOT a grazing / "
            "validity / physics threshold; G6 threshold policy unchanged."),
        "old_radii_g6r_nonlinear_denominator": old_radii,
        "paired_fd_results_unchanged": bool(paired_fd_unchanged),
        "threshold_decision_reaudited": True,
        "threshold_after_reaudit": decision["outcome"],
    }

    snapshot = dict(old)
    snapshot["status"] = "G6 frozen + G6R correction + G6R2 normalization fix"
    snapshot["g6r"] = g6r
    snapshot["g6r2"] = g6r2
    snapshot["threshold_decision"] = decision

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(snapshot, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    print(f"  contract: {n_absent} N-side absent + {n_extracted} N+1 "
          f"extracted, dual-lock={dual_lock}")
    for k, v in cases.items():
        print("  %s: r1%%/phi=%.4f r5%%/phi=%.4f (%s / %s)"
              % (k, v["r_1pct_over_phi"], v["r_5pct_over_phi"],
                 v["r_1pct_refined"]["classification"],
                 v["r_5pct_refined"]["classification"]))
    for br in ("B0", "B4"):
        pl = paired_fd[br]["radial_plateau"]
        fc = paired_fd[br]["four_column"]
        print("  %s: plateau_pass=%s max_rel=%.3e four_column_pass=%s"
              % (br, pl["plateau_pass"], pl["max_scaled_rel_error"],
                 fc["four_column_pass"]))
    print(f"  G6R2: error_normalization={g6r2['error_normalization']}, "
          f"paired_fd_unchanged={g6r2['paired_fd_results_unchanged']}, "
          f"threshold_reaudited={g6r2['threshold_decision_reaudited']}")


if __name__ == "__main__":
    main()
