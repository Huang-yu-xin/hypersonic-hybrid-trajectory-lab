"""F6 summarizer -- read-only view of the comparison surfaces."""

import json
import sys
from pathlib import Path

OUT_DIR = Path("results/gamma_k_sensitivity/comparison_surfaces")


def _load(name: str) -> dict:
    with open(OUT_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    summary = _load("f6_summary.json")
    stats = _load("metric_statistics.json")
    audit = _load("reference_audit.json")
    rec_audit = _load("recovered_center_audit.json")
    trans = _load("comparison_signature_transitions.json")
    mono = _load("range_monotonicity.json")

    print("F6 COMMON-CONDITION COMPARISON SURFACES -- READ-ONLY SUMMARY")
    print("=" * 72)
    print(f"git commit : {summary['git_commit']}")
    print(f"centers    : {summary['canonical_centers']} | "
          f"valid = {summary['valid_paired']} | "
          f"NA = {summary['not_available']}")
    print(f"recovered  : {summary['recovered_centers']} "
          f"(audited {summary['recovered_audited']})")

    print("\n## Protocol D status")
    print(json.dumps(summary["protocol_d"], indent=2))

    print("\n## Limiter counts")
    print(json.dumps(summary["limiter_counts"], indent=2))

    print("\n## Protocol B (common time)")
    for m, s in stats["protocol_b"].items():
        print(f"  {m}: n={s['count']} min={s['min']:.4g} "
              f"median={s['median']:.4g} max={s['max']:.4g} "
              f"pos={s['positive']} neg={s['negative']}")

    print("\n## Protocol C (common range)")
    for m, s in stats["protocol_c"].items():
        print(f"  {m}: n={s['count']} min={s['min']:.4g} "
              f"median={s['median']:.4g} max={s['max']:.4g} "
              f"pos={s['positive']} neg={s['negative']}")

    print("\n## Protocol D UNIQUE")
    for m, s in stats["protocol_d_unique"].items():
        print(f"  {m}: n={s['count']} min={s['min']:.4g} "
              f"median={s['median']:.4g} max={s['max']:.4g} "
              f"pos={s['positive']} neg={s['negative']}")

    amb = stats["protocol_d_ambiguous"]
    print("\n## Protocol D AMBIGUOUS")
    print(f"  count = {amb['count']} | by regime = {amb['by_regime']} | "
          f"plateau range = {amb['plateau_duration_range']}")

    print("\n## Checkpoint modes")
    print(json.dumps(stats["checkpoint_modes"], indent=2))

    print("\n## Comparison signatures")
    print(f"  unique signatures = {summary['signature_count']}")
    print(f"  transition cells = {summary['signature_transition_cells']} | "
          f"by reason = {summary['signature_transition_by_reason']}")

    print("\n## Recovered-center audit")
    for r in rec_audit["points"]:
        print(f"  ({r['gamma0']}, {r['K']}) {r['sanger_regime']} "
              f"B_eq={r['protocol_b_equal']} C_eq={r['protocol_c_equal']} "
              f"D_eq={r['protocol_d_status_equal']} "
              f"max_err={r['max_metric_error']:.4g}")

    print("\n## Reference audit")
    print(f"  audited = {audit['audited_points']} | "
          f"cat mismatches = {audit['categorical_mismatches']} | "
          f"num failures = {audit['numerical_failures']}")

    print("\n## Range monotonicity")
    print(f"  qian = {mono['qian_monotone']} | sanger = "
          f"{mono['sanger_monotone']} | nonmonotone = "
          f"{mono['nonmonotone_count']}")

    print(f"\nReady for F7: {summary['ready_for_F7']}")
    print("F6 SUMMARIZER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
