"""F4 summarizer -- read-only view of the FD-convergence artifacts.

Reads ONLY ``results/gamma_k_sensitivity/fd_convergence/`` (no
re-integration) and prints the multiplicity audit, representative
points, step policy, baseline Jacobians and key convergence tables.
"""

import json
import sys
from pathlib import Path

OUT_DIR = Path("results/gamma_k_sensitivity/fd_convergence")


def _load(name: str) -> dict:
    with open(OUT_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    summary = _load("f4_summary.json")
    reps = _load("representative_points.json")["representatives"]
    policy = _load("step_policy.json")
    jac = _load("local_jacobians.json")["jacobians"]
    mult = _load("multiplicity_audit.json")

    print("F4 FIXED-REGIME LOCAL SENSITIVITY -- READ-ONLY SUMMARY")
    print("=" * 72)
    print(f"git commit : {summary['git_commit']}")

    print("\n## Per-branch multiplicity clarification")
    print("max row multiplicity per branch:",
          mult["per_branch_max_row_multiplicity"])
    print("max column multiplicity per branch:",
          mult["per_branch_max_column_multiplicity"])

    print("\n## Representative points")
    print("| label | gamma0 | K | regime | baseline | clearance |")
    print("|---|---|---|---|---|---|")
    for r in reps:
        print(f"| {r['label']} | {r['gamma0_deg']} | {r['K']} | "
              f"{r['sanger_regime']} | {r['baseline']} | "
              f"{r['selection_clearance']:.4f} |")

    print("\n## Output vectors")
    print("Qian  :", summary["output_vectors"]["qian"])
    print("Sanger:", summary["output_vectors"]["sanger"])

    print("\n## Step policy")
    print(json.dumps(policy, indent=2))

    print("\n## Stencil audit")
    print(json.dumps(summary["stencil_counts"], indent=2))

    print("\n## Baseline Jacobians (production, approved step)")
    base = jac.get("baseline", {})
    if base:
        for model, label, outs in (
            ("qian", "Qian", summary["output_vectors"]["qian"]),
            ("sanger", "Sanger", summary["output_vectors"]["sanger"]),
        ):
            print(f"\n### {label} (d/dgamma0 per rad, d/dK per unit K)")
            print("| output | d/dgamma0 | d/dK |")
            print("|---|---|---|")
            for out in outs:
                dg = base[model].get("gamma", {}).get(out)
                dk = base[model].get("K", {}).get(out)
                print(f"| {out} | {dg} | {dk} |")

    print("\n## Health / stop gates")
    print(f"stop gates: {summary['stop_gate_reasons']}")
    print(f"ready_for_F5: {summary['ready_for_F5']}")
    print("F4 SUMMARIZER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
