"""G7 final freeze manifest generator.

READ / HASH / SUMMARIZE / FREEZE only.

This script builds ``tests/data/phase_g_final_freeze_v1.json`` from the
ACCEPTED Phase-G scientific artifacts.  It performs NO physics: it never
integrates trajectories, solves ODEs, runs grazing families, fits slopes,
re-selects scaling, or computes SVDs.  It only:

  * reads the frozen Phase-G snapshots and the frozen machine-readable
    protocol payload;
  * computes SHA-256 hashes of the accepted scientific artifacts
    (protocol doc + G1-G6 snapshots) so that ANY future change to an
    accepted snapshot explicitly breaks the final-freeze regression;
  * summarizes the authoritative final values (fixed-time / terminal /
    grazing) directly from the snapshots;
  * writes the freeze manifest.

Reproducible: running twice in a row on the same working tree must produce
a byte-identical output (no timestamps / no self-referential SHAs).

Run from the repository root:

    python scripts/build_phase_g_final_manifest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

DATA = REPO / "tests" / "data"

# --- frozen provenance (accepted scientific chain; no self-referential SHA)
UPSTREAM_PHASE_F_COMMIT = "96253f1ef7785764d8da3156d7d614d2b244b577"
STARTING_FINAL_SCIENTIFIC_COMMIT = "d1ac723c6d0cf1ad50b4b679bbc3af8a0d889a45"
BRANCH = "feature/phase-g-predictability"

ACCEPTED_STAGE_COMMITS = {
    "G0": "9db3a35a9e4d41df55c38b5747a6ec74bfa6f015",
    "G1": "d1b3030c0988a380fcd389de7b7f10ae65185ade",
    "G2": "74453782b4a1b0c008c18cef9d94d7786598e368",
    "G2R": "a3c6dfd1339624a8e6558d6ee9b4049d8e40f733",
    "G3": "a7119c07aae8f13031e2323ea76aad9e673e4c59",
    "G4": "de17ac8508ce002d29a3fa4f02a6eeb779ad5e73",
    "G4R": "01f33a5f6a5166be7b4ccc4db3473dec994c7aa4",
    "G5": "bdc1265482dd81e19bddb4333f333ff8413c965d",
    "G5R": "7a94ed10d841a2e8faa7bbc20a46be90d185cc28",
    "G6": "3b92269a159d9b259051d0a950e52cc1647bd352",
    "G6R": "9c7e80f92d34c2d5311560cb9640aa11eaf84703",
    "G6R2": STARTING_FINAL_SCIENTIFIC_COMMIT,
}

FINAL_TAGS = ["phase-g-v1.0", "predictability-v1.0"]
TAG_TARGET_POLICY = "both tags point to the same final G7 freeze commit"

ARTIFACTS = [
    "docs/phase_g/predictability_protocol.md",
    "tests/data/phase_g1_continuous_jacobian_v1.json",
    "tests/data/phase_g2_continuous_stm_v1.json",
    "tests/data/phase_g3_transverse_saltation_v1.json",
    "tests/data/phase_g4_hybrid_stm_v1.json",
    "tests/data/phase_g5_predictability_metrics_v1.json",
    "tests/data/phase_g6_grazing_predictability_v1.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str) -> dict:
    return json.loads((REPO / name).read_text(encoding="utf-8"))


def _ro(v, nd=None):
    """Pass-through with EXACT snapshot fidelity.

    The manifest is the authoritative freeze artifact: floats (including
    tiny validation residuals like 1e-11) are kept verbatim -- rounding any
    decimal digits here would silently corrupt the accepted evidence.
    ``nd`` is accepted for signature stability but unused.
    """
    if isinstance(v, list):
        return [_ro(x, nd) for x in v]
    if isinstance(v, dict):
        return {k: _ro(x, nd) for k, x in v.items()}
    return v


# ---------------------------------------------------------------------------
# Summarizers (READ the accepted snapshots only)
# ---------------------------------------------------------------------------
def summarize_g1(d: dict) -> dict:
    out = {}
    for mode, rec in d["per_mode"].items():
        s = rec["summary"]
        out[mode] = {
            "n_samples": s["n_samples"],
            "best_max_abs_error": s["best_max_abs_error"],
            "best_max_rel_error_nonzero": s["best_max_rel_error_nonzero"],
        }
    return {
        "modes": out,
        "structural_invariants": d.get("structural_invariants", {}),
    }


def summarize_g2(d: dict) -> dict:
    out = {}
    for mode, rec in d["per_mode"].items():
        rss = rec.get("reference_self_stability", {}) or {}
        sem = rec.get("semigroup", {}) or {}
        fda = rec.get("fd_reference_agreement", {}) or {}
        out[mode] = {
            "window_s": [rec["window"]["t0"], rec["window"]["t1"]],
            "reference_self_stability": {
                "max_abs_phi_diff": _ro(rss.get("max_abs_phi_diff")),
                "max_rel_phi_diff_material": _ro(
                    rss.get("max_rel_phi_diff_material")),
                "status": rss.get("status"),
            },
            "semigroup": {
                "max_abs_error": _ro(sem.get("max_abs_error")),
                "max_rel_error_material": _ro(
                    sem.get("max_rel_error_material")),
                "status": sem.get("status"),
            },
            "fd_reference_agreement": {
                "multiplier": fda.get("multiplier"),
                "max_rel_error_nonzero": _ro(
                    fda.get("max_rel_error_nonzero")),
                "validation_scaled_error": _ro(
                    fda.get("validation_scaled_error")),
                "classifications_plus": fda.get("classification_plus"),
            },
            "theta_invariant_present": "theta_invariant" in rec,
            "qeg_gamma_row_invariant_present":
                "qeg_gamma_row_invariant" in rec,
        }
    return {
        "representation_invariance": _ro(d.get(
            "representation_invariance", {})),
        "scientific_canonical_scaling_status": d.get(
            "scientific_canonical_scaling_status"),
        "g2r": {
            "issue1_both_side_gate": d["g2r"].get("issue1_both_side_gate"),
            "issue2_mode_window_detection": d["g2r"].get(
                "issue2_mode_window_detection"),
        },
        "per_mode": out,
    }


def summarize_g3(d: dict) -> dict:
    ev = {}
    for key, rec in d["events"].items():
        fd = rec.get("event_time_plateau", {}) or {}
        sd = rec.get("saltation_plateau", {}) or {}
        ev[key] = {
            "mode_before": rec["mode_before"],
            "mode_after": rec["mode_after"],
            "time_s": rec["time"],
            "abs_denominator": rec.get("abs_denominator"),
            "event_time_fd_material_rel": _ro(fd.get("material_rel_error")),
            "saltation_fd_material_rel": _ro(sd.get("material_rel_error")),
            "reference_converged": bool(rec.get("reference_convergence", {})),
        }
    return {
        "eligible_true_switches": ev,
        "excluded_events_no_saltation": d.get(
            "excluded_events_no_saltation", []),
        "grazing_threshold_none_frozen": d.get(
            "grazing_threshold_none_frozen"),
    }


def summarize_g4(d: dict) -> dict:
    eps = {}
    for key, rec in d["endpoints"].items():
        rc = rec.get("reference_convergence", {}) or {}
        pl = rec.get("fd_plateau", {}) or {}
        rg = rec.get("reference_grade_fd", {}) or {}
        eps[key] = {
            "T_s": rec.get("T"),
            "topology_signature": rec.get("topology_signature"),
            "n_true_switches": rec.get("n_true_switches"),
            "endpoint_mode": rec.get("endpoint_mode"),
            "terminal_margin_s": rec.get("terminal_margin_s"),
            "reference_phi_material_rel": _ro(
                rc.get("phi_material_rel_diff_01_05")),
            "reference_event_time_max_diff": _ro(
                rc.get("event_time_max_diff_01_05")),
            "reference_eta_max_diff": _ro(rc.get("eta_max_diff_01_05")),
            "reference_status": rc.get("status"),
            "fd_plateau_material_rel": _ro(pl.get("material_rel_error")),
            "ref_grade_fd_material_rel": _ro(
                rg.get("material_rel_error")),
            "structural_invariants": rec.get("structural_invariants", {}),
        }
    neg = d.get("qian_no_saltation_negative_control", {}) or {}
    return {
        "endpoints": eps,
        "qian_no_saltation_negative_control": {
            "correct_hybrid_error_vs_FD": _ro(
                neg.get("correct_hybrid_error_vs_FD")),
            "naive_no_saltation_error_vs_FD": _ro(
                neg.get("naive_no_saltation_error_vs_FD")),
            "correct_gamma_row": neg.get("correct_gamma_row"),
            "naive_gamma_row": neg.get("naive_gamma_row"),
            "fd_gamma_row": neg.get("fd_gamma_row"),
        },
        "g4r": {
            key: d.get("g4r", {}).get(key)
            for key in ("endpoint_scoped_terminal", "success_false_semantics",
                        "event_multiplicity")
        },
    }


def _fixed_time_row(rec: dict) -> dict:
    return {
        "T_s": rec.get("horizon_s"),
        "topology_signature": rec.get("topology_signature"),
        "endpoint_mode": rec.get("endpoint_mode"),
        "sigma_max": _ro(rec.get("sigma_max")),
        "lambda_max": _ro(rec.get("lambda_max")),
        "numerical_rank": rec.get("numerical_rank"),
        "nullity": rec.get("nullity"),
        "condition_status": rec.get("condition_status"),
        "dominant_input_scaled": _ro(rec.get("v1_scaled")),
    }


def summarize_g5(d: dict) -> dict:
    ft = {}
    for model in ("qian", "sanger"):
        ft[model] = {k: _fixed_time_row(v)
                     for k, v in d["fixed_time_canonical"][model].items()}
    terminal = {}
    for model in ("qian", "sanger"):
        t = d["terminal"][model]
        terminal[model] = {
            "terminal": t.get("terminal"),
            "terminal_time_s": _ro(t.get("terminal_time")),
            "denominator_nTf": _ro(t.get("denominator")),
            "scaled_sigma_max": _ro(t.get("scaled_sigma_max")),
            "rank": t.get("rank"),
            "nullity": t.get("nullity"),
            "condition_status": t.get("condition_status"),
        }
    return {
        "canonical_scaling_decision": d.get("canonical_scaling_decision", {}),
        "fixed_time_canonical": ft,
        "scale_audit_T600": _ro(d.get("scale_audit", {})),
        "reference_stability": _ro(d.get("reference_stability", {})),
        "terminal": terminal,
        "native_terminal_comparison_warning": d.get(
            "native_terminal_comparison_warning"),
        "g5r_trim_convergence": _ro(
            (d.get("g5r", {}) or {}).get("qian_rti_trim_audit", {})),
    }


def summarize_g6(d: dict) -> dict:
    g6r = d.get("g6r", {}) or {}
    g6r2 = d.get("g6r2", {}) or {}
    rv = g6r.get("refined_validity_radii", {}) or {}
    radii = {}
    for k, rec in rv.items():
        radii[k] = {
            "phi_local_m": rec.get("phi_local_m"),
            "d_exit": rec.get("d_exit"),
            "r_1pct_refined": rec.get("r_1pct_refined"),
            "r_5pct_refined": rec.get("r_5pct_refined"),
            "monotone_profile": rec.get("monotone_profile"),
        }
    scaling = {}
    for br, fit in (d.get("scaling_fits", {}) or {}).items():
        scaling[br] = {
            "points_used": fit.get("points_used"),
            "H1_Phi_vs_d_slope": fit.get("H1_Phi_vs_d_slope"),
            "H1_r2": fit.get("H1_Phi_vs_d_r2"),
            "H3_pair_norm_vs_d_slope": fit.get("H3_pair_norm_vs_d_slope"),
            "H3_r2": fit.get("H3_pair_norm_vs_d_r2"),
        }
    topo = {}
    for k, rec in (d.get("topology_radii", {}) or {}).items():
        topo[k] = {
            "eps_plus_rad": rec.get("eps_gamma_plus_rad"),
            "eps_minus_rad": rec.get("eps_gamma_minus_rad"),
            "centered_radius_rad": rec.get("centered_radius_rad"),
            "plus_class": rec.get("plus_class"),
        }
    return {
        "threshold_decision": d.get("threshold_decision", {}).get("outcome"),
        "contract_audit": g6r.get("contract_audit", {}),
        "refined_validity_radii_final_G6R2": radii,
        "radii_authority": {
            "G6_coarse_grid": "HISTORICAL",
            "G6R_nonlinear_denominator": "SUPERSEDED",
            "G6R2_linear_prediction_denominator": "FINAL_AUTHORITY",
        },
        "g6r2_normalization": {
            "error_normalization": g6r2.get("error_normalization"),
            "old_error_normalization": g6r2.get("old_error_normalization"),
            "paired_fd_results_unchanged": g6r2.get(
                "paired_fd_results_unchanged"),
            "old_radii_g6r_nonlinear_denominator": _ro(g6r2.get(
                "old_radii_g6r_nonlinear_denominator", {})),
        },
        "paired_fd": {
            k: {
                "radial_plateau_pass":
                    v.get("radial_plateau", {}).get("plateau_pass"),
                "max_scaled_rel_error":
                    v.get("radial_plateau", {}).get("max_scaled_rel_error"),
                "four_column_pass":
                    v.get("four_column", {}).get("four_column_pass"),
            } for k, v in (g6r.get("paired_fd", {}) or {}).items()
        },
        "controlled_family_scaling": scaling,
        "topology_radii": topo,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DATA / "phase_g_final_freeze_v1.json"))
    args = ap.parse_args()

    from hyptraj.predictability.protocol import machine_readable_protocol

    g1, g2, g3 = (_load(n) for n in (
        "tests/data/phase_g1_continuous_jacobian_v1.json",
        "tests/data/phase_g2_continuous_stm_v1.json",
        "tests/data/phase_g3_transverse_saltation_v1.json"))
    g4, g5, g6 = (_load(n) for n in (
        "tests/data/phase_g4_hybrid_stm_v1.json",
        "tests/data/phase_g5_predictability_metrics_v1.json",
        "tests/data/phase_g6_grazing_predictability_v1.json"))
    g1s, g2s, g3s = (summarize_g1(g1), summarize_g2(g2),
                     summarize_g3(g3))
    g4s, g5s, g6s = (summarize_g4(g4), summarize_g5(g5),
                     summarize_g6(g6))

    manifest = {
        "schema_version": "phase-g-final-freeze-v1",
        "title": "Phase G final freeze manifest — finite-time local "
                 "predictability of hybrid trajectories",
        "status": "PHASE G COMPLETE / FROZEN",
        "branch": BRANCH,
        "provenance": {
            "upstream_phase_f_commit": UPSTREAM_PHASE_F_COMMIT,
            "starting_final_scientific_commit": STARTING_FINAL_SCIENTIFIC_COMMIT,
            "accepted_stage_commits": ACCEPTED_STAGE_COMMITS,
            "note": "No self-referential final G7 SHA is recorded; the real "
                    "final commit and tag targets are reported by the G7 "
                    "shell audit after freeze.",
        },
        "final_tags": {
            "names": FINAL_TAGS,
            "tag_target_policy": TAG_TARGET_POLICY,
        },
        "artifact_sha256": {
            rel: _sha256(REPO / rel) for rel in ARTIFACTS
        },
        "canonical_scaling": {
            "candidate": "A",
            "scale_values": {"r": 1e5, "theta": 1.0, "v": 7e3, "gamma": 0.1},
            "status": "CANONICAL_SCALE_NUMERIC_VALUES_FROZEN",
            "ranking_scale_sensitive": True,
            "scale_sensitivity_note": (
                "Qian-vs-Sanger sigma_max/lambda_max ordering at T=600 flips "
                "under candidate B; all scientific claims must declare scale "
                "A and report the A/B/C audit."),
        },
        "conventions": machine_readable_protocol(),
        "final_key_results": {
            "continuous_modes_validated": [
                "Qian ENTRY_CAPTURE", "Qian QEG_GLIDE (strict interior)",
                "Sanger SANGER_ATM", "Sanger SANGER_VAC"],
            "hybrid_events_eligible_true_switches": [
                "qian_capture", "sanger_atmosphere_exit",
                "sanger_atmosphere_entry"],
            "terminal_eligible": ["qian_rti (RTI)", "sanger_srti (SRTI)"],
            "fixed_time": g5s["fixed_time_canonical"],
            "scale_audit_T600": g5s["scale_audit_T600"],
            "terminal": g5s["terminal"],
            "grazing": g6s,
            "native_terminal_warning": g5s[
                "native_terminal_comparison_warning"],
        },
        "validity_radius_authority_chain": {
            "G6_coarse_grid": "HISTORICAL",
            "G6R_nonlinear_denominator": "SUPERSEDED",
            "G6R2_linear_prediction_denominator": "FINAL_AUTHORITY",
        },
        "corrective_history": {
            "G2R": "centered FD two-sided gate; continuous mode-window gate",
            "G4R": "endpoint-scoped terminal classification; success=False "
                   "semantics; event multiplicity",
            "G5R": "terminal-kind eligibility; exact-zero/nonfinite "
                   "transversality guard; RTI trim convergence",
            "G6R": "hard grazing topology contract; dual-reference lock; "
                   "refined operational radius; paired FD plateau; "
                   "four-column nonlinear validation",
            "G6R2": "ERROR / LINEAR-PREDICTION normalization restored",
            "note": "Corrective history is retained as successive validation "
                    "hardening, not hidden failures.",
        },
        "claim_boundaries": {
            "finite_time_local_only": True,
            "no_chaos_claim": True,
            "no_probabilistic_uncertainty": True,
            "no_optimization": True,
            "no_gamma0K_rescan_in_phase_g": True,
            "native_terminal_not_fair_cross_model_ranking": True,
            "no_universal_numeric_grazing_threshold": True,
            "observability_analysis_outside_scope": True,
        },
        "validation_summary": {
            "G1_continuous_jacobian": g1s,
            "G2_continuous_stm": g2s,
            "G3_transverse_saltation": g3s,
            "G4_hybrid_stm": g4s,
            "G5_metrics_terminal": g5s,
            "G6_grazing": g6s,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True),
        encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
