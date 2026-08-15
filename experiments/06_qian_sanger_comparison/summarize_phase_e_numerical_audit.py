"""E6 summarizer -- read-only view of the numerical audit artifacts.

Reads ONLY ``results/qian_sanger_comparison/numerical_audit/`` (no
re-integration) and prints the audit conclusions: reference
self-stability, cross-phase reference checks, production-vs-reference
errors, protocol stability, and the production approval verdict.
"""

import json
import sys
from pathlib import Path

AUDIT_DIR = Path("results/qian_sanger_comparison/numerical_audit")


def main() -> int:
    missing = [p for p in ("numerical_audit_summary.json",
                           "production_vs_reference.json",
                           "audit_matrix.json",
                           "reference_self_stability.json")
               if not (AUDIT_DIR / p).exists()]
    if missing:
        print(f"Missing artifacts: {missing}")
        print("Run experiments/06_qian_sanger_comparison/"
              "run_phase_e_numerical_audit.py first.")
        return 1

    with open(AUDIT_DIR / "numerical_audit_summary.json",
              encoding="utf-8") as f:
        s = json.load(f)

    print("E6 NUMERICAL / REGRESSION AUDIT -- CANDIDATE (NOT FREEZED)")
    print("=" * 72)
    print(f"git commit : {s['git_commit']} ({s['branch']})")
    prod = s["production_config"]
    ref = s["reference_config"]
    print(f"production : DOP853 rtol={prod['rtol']} "
          f"max_step={prod['max_step']} s")
    print(f"reference  : DOP853 rtol={ref['rtol']} "
          f"max_step={ref['max_step']} s")

    ss = s["reference_self_stability"]
    print("\nReference self-stability (REF-0.1 vs REF-0.05)")
    print("-----------------------------------------------")
    print(f"max key metric difference = {ss['max_key_metric_difference']:.6e}")
    print(f"semantic topology equal   = {ss['semantics_equal']}")

    cr = s["cross_phase_reference"]
    print("\nCross-phase independent reference check (REF-0.1)")
    print("--------------------------------------------------")
    print(f"Qian vs Phase C: capture dT = "
          f"{cr['qian_vs_phase_c']['capture_time_diff_s']:.3e} s, "
          f"RTI dT = {cr['qian_vs_phase_c']['rti_time_diff_s']:.3e} s, "
          f"RTI dR = {cr['qian_vs_phase_c']['rti_range_diff_m']:.3e} m")
    print(f"Sanger vs Phase D: SRTI dT = "
          f"{cr['sanger_vs_phase_d']['srti_time_diff_s']:.3e} s, "
          f"SRTI dR = {cr['sanger_vs_phase_d']['srti_range_diff_m']:.3e} m, "
          f"h_max d = {cr['sanger_vs_phase_d']['max_altitude_diff_m']:.3e} m, "
          f"topology = {cr['sanger_vs_phase_d']['topology_equal']}")

    print("\nKey derived errors (P9-20 vs REF-0.1)")
    print("--------------------------------------")
    for key, value in s["key_derived_errors"].items():
        print(f"  {key:<26} {value:.6e}")

    li = s["limiting_identities"]
    print("\nLimiting identities (time / range / exposure)")
    print("---------------------------------------------")
    for case, row in li["per_case"].items():
        print(f"  {case:<9} {row['time']:<6} {row['range']:<6} {row['exposure']}")
    print(f"stable across all cases = {li['stable']}")

    ht = s["hybrid_topology"]
    stable = ht["stable"]
    print(f"\nHybrid topology stable = {stable} "
          f"(RTI/SRTI/skip=2/UNIQUE in all {len(ht['per_case'])} cases)")

    print(f"\nMax common-range root residual = "
          f"{s['root_residuals']['max']:.3e} m")

    print("\nProduction comparison numerics:")
    print(f"  {'APPROVED' if s['production_numerics_approved'] else 'NOT APPROVED'}")

    print("\nRegression snapshot:")
    snap = Path("tests/data/qian_sanger_comparison_v1.json")
    if snap.exists():
        with open(snap, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  path   = {snap}")
        print(f"  source = PRODUCTION (P9-20): rtol={data['solver']['rtol']} "
              f"max_step={data['solver']['max_step']} s")
        print(f"  semantic: {data['semantic_fields']['qian_terminal_kind']} / "
              f"{data['semantic_fields']['sanger_terminal_kind']} / "
              f"skip={data['semantic_fields']['sanger_skip_count']}")
        print(f"  numeric fields = {len(data['production_values'])}")
    else:
        print("  NOT FOUND (run with --write-snapshot)")

    print("\nInterpretation boundary: the numerical reference is a NUMERICAL")
    print("reference, not an analytic solution and not physical truth; the")
    print("production snapshot remains the official Phase E regression")
    print("reference.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
