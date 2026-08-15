"""E6 runner -- Phase E numerical and regression audit.

Runs the complete Phase E derived analysis under 7 solver
configurations (REF-0.1, REF-0.05, P8-20, P9-20, P10-20, P9-40,
P9-10), computes reference self-stability, the production-vs-reference
error table, protocol limiting-identity / topology stability, and
writes the audit artifacts under
``results/qian_sanger_comparison/numerical_audit/``.

With ``--write-snapshot`` it additionally writes the TRACKED production
regression snapshot ``tests/data/qian_sanger_comparison_v1.json``
(P9-20 values only; the high-precision reference is never used as the
regression source).

    E6 NUMERICAL / REGRESSION AUDIT
    CANDIDATE -- NOT FINAL PHASE E FREEZE
"""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from hyptraj.analysis.comparison_validation import (
    AUDIT_CASES,
    REFERENCE_SOLVER_CONFIG,
    cross_phase_qian_check,
    cross_phase_sanger_check,
    run_audit_case,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

OUT_DIR = Path("results/qian_sanger_comparison/numerical_audit")
SNAPSHOT_PATH = Path("tests/data/qian_sanger_comparison_v1.json")
PHASE_C_REF = Path("results/numerical_validation/reference/reference.json")
PHASE_D_REF = Path(
    "results/sanger_hybrid/numerical_validation/reference/ref_0_1.json")


def _git_info() -> dict[str, str]:
    def _run(cmd: list[str]) -> str:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 check=True)
            return out.stdout.strip()
        except (subprocess.CalledProcessError, OSError):
            return "unknown"

    return {
        "git_commit": _run(["git", "rev-parse", "HEAD"]),
        "branch": _run(["git", "branch", "--show-current"]),
    }


def _load_phase_c_reference() -> dict:
    if not PHASE_C_REF.exists():
        raise FileNotFoundError(
            f"Phase C reference missing: {PHASE_C_REF} "
            "(run experiments/03_numerical_validation first).")
    with open(PHASE_C_REF, encoding="utf-8") as f:
        return json.load(f)["reference"]


def _load_phase_d_reference() -> dict:
    if not PHASE_D_REF.exists():
        raise FileNotFoundError(
            f"Phase D D6 reference missing: {PHASE_D_REF} "
            "(run experiments/05_sanger_numerical_validation first).")
    with open(PHASE_D_REF, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "research_time_s": data["global"]["research_time_s"],
        "research_range_m": data["global"]["research_range_m"],
        "max_altitude_m": data["global"]["max_altitude_m"],
        "skip_count": data["topology"]["skip_count"],
        "mode_sequence": data["topology"]["mode_sequence"],
    }


def _case_to_row(result) -> dict:
    row = {
        "case": result.case,
        "qian_terminal_kind": result.qian_terminal_kind,
        "sanger_terminal_kind": result.sanger_terminal_kind,
        "sanger_skip_count": result.sanger_skip_count,
        "time_limiter": result.common_time_limiter,
        "range_limiter": result.common_range_limiter,
        "exposure_limiter": result.exposure_limiter,
        "protocol_d_status": f"{result.protocol_d_qian_status}/"
                             f"{result.protocol_d_sanger_status}",
    }
    for key in ("DeltaR_time", "time_saving", "DeltaR_atm_exposure",
                "DeltaE_time", "DeltaE_range", "DeltaE_tau",
                "qian_terminal_time", "sanger_terminal_time",
                "sanger_vac_duration", "sanger_vac_range"):
        row[key] = result.metrics[key]
    return row


def _difference_table(prod: dict, ref: dict, keys) -> dict:
    out = {}
    for key in keys:
        out[key] = {
            "production": prod[key],
            "reference": ref[key],
            "absolute_error": abs(prod[key] - ref[key]),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-snapshot", action="store_true",
                        help="write tests/data/qian_sanger_comparison_v1.json"
                             " (production P9-20 values)")
    args = parser.parse_args()

    print("E6 NUMERICAL / REGRESSION AUDIT")
    print("CANDIDATE -- NOT FINAL PHASE E FREEZE")
    print("=" * 72)

    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)

    # ------------------------------------------------------------------
    # 1. Run all 7 audit cases.
    # ------------------------------------------------------------------
    results = {}
    for case in AUDIT_CASES:
        print(f"Running case {case} ...", flush=True)
        results[case] = run_audit_case(env, vehicle, initial, control, case)

    # ------------------------------------------------------------------
    # 2. Reference self-stability (REF-0.1 vs REF-0.05).
    # ------------------------------------------------------------------
    stability_keys = [
        "t_common", "DeltaR_time", "DeltaH_time", "DeltaV_time",
        "DeltaE_time", "R_common", "time_saving", "DeltaH_range",
        "DeltaV_range", "DeltaE_range", "tau_common",
        "elapsed_time_extension", "DeltaR_atm_exposure", "DeltaH_tau",
        "DeltaV_tau", "DeltaE_tau", "qian_total_loss", "sanger_total_loss",
        "sanger_vac_duration", "sanger_vac_range", "qian_h_min",
        "qian_h_max", "sanger_h_min", "sanger_h_max",
        "sanger_atm_fraction", "sanger_vac_fraction", "qian_q_max",
        "sanger_q_max", "qian_aD_max", "sanger_aD_max",
    ]
    self_stability = {}
    for key in stability_keys:
        self_stability[key] = abs(
            results["REF-0.1"].metrics[key] - results["REF-0.05"].metrics[key]
        )
    semantics_equal = all(
        results["REF-0.1"].__dict__[field]
        == results["REF-0.05"].__dict__[field]
        for field in ("qian_terminal_kind", "sanger_terminal_kind",
                      "sanger_skip_count", "sanger_mode_sequence",
                      "qian_source_structure", "common_time_limiter",
                      "common_range_limiter", "exposure_limiter",
                      "protocol_d_qian_status", "protocol_d_sanger_status")
    )
    max_stability_diff = max(self_stability.values())

    # ------------------------------------------------------------------
    # 3. Cross-phase independent reference checks (REF-0.1).
    # ------------------------------------------------------------------
    phase_c = _load_phase_c_reference()
    phase_d = _load_phase_d_reference()
    qian_cross = cross_phase_qian_check(results["REF-0.1"], phase_c)
    sanger_cross = cross_phase_sanger_check(results["REF-0.1"], phase_d)

    # ------------------------------------------------------------------
    # 4. Production vs reference (P9-20 vs REF-0.1).
    # ------------------------------------------------------------------
    prod = results["P9-20"].metrics
    ref = results["REF-0.1"].metrics
    table_keys = [
        "t_common", "qian_R", "qian_h", "qian_v", "qian_E", "qian_loss",
        "sanger_R", "sanger_h", "sanger_v", "sanger_E", "sanger_loss",
        "DeltaR_time", "DeltaV_time", "DeltaE_time",
        "R_common", "t_Q", "t_S", "time_saving", "DeltaV_range",
        "DeltaE_range", "tau_common", "pd_t_Q", "pd_t_S",
        "elapsed_time_extension", "DeltaR_atm_exposure", "DeltaV_tau",
        "DeltaE_tau", "qian_total_loss", "sanger_total_loss",
        "sanger_vac_duration", "sanger_vac_range",
        "qian_h_min", "qian_h_max", "sanger_h_min", "sanger_h_max",
        "qian_q_max", "sanger_q_max", "qian_aD_max", "sanger_aD_max",
        "qian_terminal_time", "qian_terminal_range",
        "sanger_terminal_time", "sanger_terminal_range",
        "tau_at_common_time_qian", "tau_at_common_time_sanger",
        "tau_at_common_range_qian", "tau_at_common_range_sanger",
    ]
    production_vs_reference = _difference_table(prod, ref, table_keys)

    # Key derived-difference errors (E6 §11).
    derived_errors = {
        key: production_vs_reference[key]["absolute_error"]
        for key in ("DeltaR_time", "DeltaV_time", "DeltaE_time",
                    "time_saving", "DeltaV_range", "DeltaE_range",
                    "DeltaR_atm_exposure", "elapsed_time_extension",
                    "DeltaV_tau", "DeltaE_tau")
    }

    # ------------------------------------------------------------------
    # 5. Stability records.
    # ------------------------------------------------------------------
    limiter_rows = {}
    topology_rows = {}
    for case, r in results.items():
        limiter_rows[case] = {
            "time": r.common_time_limiter,
            "range": r.common_range_limiter,
            "exposure": r.exposure_limiter,
        }
        topology_rows[case] = {
            "qian_terminal_kind": r.qian_terminal_kind,
            "sanger_terminal_kind": r.sanger_terminal_kind,
            "sanger_skip_count": r.sanger_skip_count,
            "mode_sequence": r.sanger_mode_sequence,
            "protocol_d_status": (
                f"{r.protocol_d_qian_status}/{r.protocol_d_sanger_status}"),
            "checkpoint_modes": r.checkpoint_modes,
        }
    limiter_stable = all(
        row == limiter_rows["P9-20"] for row in limiter_rows.values())
    topology_stable = all(
        topo["qian_terminal_kind"] == "RTI"
        and topo["sanger_terminal_kind"] == "SRTI"
        and topo["sanger_skip_count"] == 2
        and topo["protocol_d_status"] == "UNIQUE/UNIQUE"
        for topo in topology_rows.values())

    # Common-range root residuals across all cases.
    root_residuals = {
        case: r.root_residuals for case, r in results.items()
    }
    max_root_residual = max(
        max(r.root_residuals.values()) for r in results.values())

    # Energy accounting stability: VAC invariant per case (the segment
    # telescoping identity itself is verified in the E3 regression
    # tests; here we record the VAC conservation invariant).
    vac_drift = {
        case: r.metrics["sanger_vac_max_rel_drift"]
        for case, r in results.items()
    }

    # ------------------------------------------------------------------
    # 6. Audit artifacts.
    # ------------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    git = _git_info()

    summary = {
        "schema_version": "e6-numerical-audit-v1",
        "git_commit": git["git_commit"],
        "branch": git["branch"],
        "production_config": {
            "method": PRODUCTION_SOLVER_CONFIG.method,
            "rtol": PRODUCTION_SOLVER_CONFIG.rtol,
            "atol": [float(a) for a in PRODUCTION_SOLVER_CONFIG.atol],
            "max_step": PRODUCTION_SOLVER_CONFIG.max_step,
        },
        "reference_config": {
            "method": REFERENCE_SOLVER_CONFIG.method,
            "rtol": REFERENCE_SOLVER_CONFIG.rtol,
            "atol": [float(a) for a in REFERENCE_SOLVER_CONFIG.atol],
            "max_step": REFERENCE_SOLVER_CONFIG.max_step,
        },
        "reference_self_stability": {
            "max_key_metric_difference": max_stability_diff,
            "semantics_equal": semantics_equal,
            "per_metric_abs_diff": self_stability,
        },
        "cross_phase_reference": {
            "qian_vs_phase_c": qian_cross,
            "sanger_vs_phase_d": sanger_cross,
        },
        "production_vs_reference": production_vs_reference,
        "key_derived_errors": derived_errors,
        "limiting_identities": {
            "per_case": limiter_rows,
            "stable": limiter_stable,
        },
        "hybrid_topology": {
            "per_case": topology_rows,
            "stable": topology_stable,
        },
        "root_residuals": {
            "per_case": root_residuals,
            "max": max_root_residual,
        },
        "vac_invariants": {
            "max_relative_drift_per_case": vac_drift,
        },
        "production_numerics_approved": (
            semantics_equal
            and limiter_stable
            and topology_stable
            and max_stability_diff < 1e-3
            and max_root_residual < 1e-3
        ),
    }

    with open(OUT_DIR / "reference_self_stability.json", "w",
              encoding="utf-8") as f:
        json.dump(summary["reference_self_stability"], f, indent=2)
    with open(OUT_DIR / "production_vs_reference.json", "w",
              encoding="utf-8") as f:
        json.dump(production_vs_reference, f, indent=2)
    with open(OUT_DIR / "audit_matrix.json", "w", encoding="utf-8") as f:
        json.dump({
            "rows": [_case_to_row(r) for r in results.values()],
            "limiting_identities": limiter_rows,
            "topology": topology_rows,
        }, f, indent=2)
    with open(OUT_DIR / "audit_matrix.csv", "w", newline="",
              encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(
            _case_to_row(results["P9-20"]).keys()))
        writer.writeheader()
        for r in results.values():
            writer.writerow(_case_to_row(r))
    with open(OUT_DIR / "numerical_audit_summary.json", "w",
              encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # ------------------------------------------------------------------
    # 7. Console summary tables.
    # ------------------------------------------------------------------
    print("\n=== Audit matrix (semantic columns) ===")
    header = (f"{'Case':<9}{'Qian term':<10}{'Sanger term':<11}"
              f"{'skip':<5}{'t-lim':<6}{'R-lim':<6}{'exp-lim':<7}"
              f"{'PD':<15}{'DeltaR_time [km]':>17}{'time_sav [s]':>13}"
              f"{'dR_tau [km]':>12}")
    print(header)
    for case in AUDIT_CASES:
        r = results[case]
        print(f"{case:<9}{r.qian_terminal_kind:<10}{r.sanger_terminal_kind:<11}"
              f"{r.sanger_skip_count:<5}{r.common_time_limiter:<6}"
              f"{r.common_range_limiter:<6}{r.exposure_limiter:<7}"
              f"{r.protocol_d_qian_status + '/' + r.protocol_d_sanger_status:<15}"
              f"{r.metrics['DeltaR_time'] / 1000:>17.6f}"
              f"{r.metrics['time_saving']:>13.6f}"
              f"{r.metrics['DeltaR_atm_exposure'] / 1000:>12.6f}")

    print("\n=== Reference self-stability (REF-0.1 vs REF-0.05) ===")
    print(f"max key metric difference = {max_stability_diff:.6e}")
    print(f"semantic topology equal   = {semantics_equal}")

    print("\n=== Cross-phase independent reference check (REF-0.1) ===")
    print(f"Qian vs Phase C: capture dT={qian_cross['capture_time_diff_s']:.3e} s  "
          f"RTI dT={qian_cross['rti_time_diff_s']:.3e} s  "
          f"RTI dR={qian_cross['rti_range_diff_m']:.3e} m")
    print(f"Sanger vs Phase D: SRTI dT={sanger_cross['srti_time_diff_s']:.3e} s  "
          f"SRTI dR={sanger_cross['srti_range_diff_m']:.3e} m  "
          f"h_max d={sanger_cross['max_altitude_diff_m']:.3e} m  "
          f"topology={sanger_cross['topology_equal']}")

    print("\n=== Key derived errors (P9-20 vs REF-0.1) ===")
    for key, value in derived_errors.items():
        print(f"  {key:<26} {value:.6e}")

    print("\n=== Limiting identities ===")
    for case, row in limiter_rows.items():
        print(f"  {case:<9} time={row['time']:<6} range={row['range']:<6} "
              f"exposure={row['exposure']}")
    print(f"stable across all cases = {limiter_stable}")

    print(f"\nMax common-range root residual = {max_root_residual:.3e} m")

    approved = summary["production_numerics_approved"]
    print(f"\nProduction comparison numerics: "
          f"{'APPROVED' if approved else 'NOT APPROVED'}")

    # ------------------------------------------------------------------
    # 8. Regression snapshot (production only).
    # ------------------------------------------------------------------
    if args.write_snapshot:
        if not approved:
            print("Snapshot NOT written: production numerics not approved.")
            return 1
        write_regression_snapshot(results["P9-20"], env, initial, control)
        print(f"Regression snapshot written: {SNAPSHOT_PATH}")

    print(f"\nArtifacts written to {OUT_DIR}")
    print("E6 RUNNER: PASS")
    return 0


def write_regression_snapshot(result, env, initial, control) -> None:
    """Tracked PRODUCTION (P9-20) regression reference (E6 §22-§25)."""
    m = result.metrics
    snapshot = {
        "schema_version": "phase-e-comparison-regression-v1",
        "reference_name": "qian-sanger-comparison-v1",
        "source_protocol": "Phase E E0",
        "qian_baseline": "qian-baseline-v1.0",
        "sanger_baseline": "sanger-baseline-v1.0",
        "solver": {
            "method": PRODUCTION_SOLVER_CONFIG.method,
            "rtol": PRODUCTION_SOLVER_CONFIG.rtol,
            "atol": [float(a) for a in PRODUCTION_SOLVER_CONFIG.atol],
            "max_step": PRODUCTION_SOLVER_CONFIG.max_step,
            "dense_output": True,
        },
        "initial_conditions": {
            "h0_m": initial.altitude,
            "v0_mps": initial.velocity,
            "gamma0_deg": initial.flight_path_angle_deg,
            "theta0_rad": initial.range_angle,
            "K": getattr(control, "value", None),
        },
        "terminal_semantics": {
            "qian": "RTI = QEG feasibility loss",
            "sanger": "SRTI = skip-capability loss",
        },
        "semantic_fields": {
            "qian_terminal_kind": result.qian_terminal_kind,
            "sanger_terminal_kind": result.sanger_terminal_kind,
            "sanger_skip_count": result.sanger_skip_count,
            "qian_source_structure": result.qian_source_structure,
            "sanger_mode_sequence": result.sanger_mode_sequence,
            "common_time_limiter": result.common_time_limiter,
            "common_range_limiter": result.common_range_limiter,
            "exposure_limiter": result.exposure_limiter,
            "protocol_d_qian_status": result.protocol_d_qian_status,
            "protocol_d_sanger_status": result.protocol_d_sanger_status,
            "checkpoint_modes": result.checkpoint_modes,
        },
        "production_values": m,
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
