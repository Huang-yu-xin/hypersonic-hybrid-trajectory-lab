"""F3 summarizer -- read-only view of the boundary-refinement artifacts.

Reads ONLY ``results/gamma_k_sensitivity/boundary_refinement/`` (no
re-integration) and prints the branch summary, extremal certification,
grazing-margin convergence, OPEN_BOUNDARY intersections, multiplicity
and health.
"""

import json
import sys
from pathlib import Path

OUT_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")


def _load(name: str) -> dict:
    with open(OUT_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    summary = _load("refinement_summary.json")
    cert = _load("branch_extremal_certification.json")
    margin = _load("grazing_margin_by_depth.json")
    open_int = _load("open_boundary_intersections.json")
    branch_sum = _load("branch_summary.json")

    print("F3 ADAPTIVE GRAZING-BOUNDARY REFINEMENT -- READ-ONLY SUMMARY")
    print("=" * 72)
    print(f"git commit : {summary['git_commit']}")
    print(f"initial candidate cells : {summary['initial_candidate_cells']}")
    print(f"max depth / target      : {summary['max_depth']} / "
          f"{summary['target_resolution']}")
    print(f"evaluated points        : {summary['total_evaluated_unique_points']} "
          f"(fresh={summary['fresh_refinement_points']}, "
          f"cache={summary['cache_reused_points']})")
    print(f"terminal refined cells  : {summary['terminal_refined_cells']}")
    print(f"cells per branch        : {summary['cells_per_branch']}")
    print(f"multiskip unresolved    : {summary['multiskip_unresolved']}")
    print(f"exact-only cells        : {summary['exact_only_cells']}")
    print(f"Qian topology changes   : {summary['qian_topology_changes']}")
    print(f"recovered / verified    : {summary['recovered_points']} / "
          f"{summary['reference_verified_count']}")
    print(f"sign anomalies          : {summary['sign_anomaly_count']}")
    print(f"row / col multiplicity  : {summary['row_multiplicity']} / "
          f"{summary['column_multiplicity']}")

    print("\n## Branches")
    for b, info in branch_sum["branches"].items():
        print(f"  {b}: cells={info['terminal_cells']} "
              f"gamma=[{info['gamma_extent'][0]:.4f},"
              f"{info['gamma_extent'][1]:.4f}] "
              f"K=[{info['K_extent'][0]:.4f},{info['K_extent'][1]:.4f}] "
              f"open={info['open_edges']}")

    print("\n## Branch extremal certification (dual reference)")
    for b, c in sorted(cert.items()):
        print(f"  {b}:")
        for side in ("N_side", "N1_side"):
            e = c.get(side)
            if e is None:
                print(f"    {side}: (no sampled points)")
                continue
            ref_str = "; ".join(
                f"{r['solver']}={r.get('regime')} "
                f"phi={r.get('phi')} equal={r.get('topology_equal')}"
                for r in e["reference_rows"])
            print(f"    {side}: point={e['parameter']} "
                  f"prod_phi={e['production_phi']:.6f} "
                  f"new_exit_dhdt={e['new_exit_dhdt_mps']} "
                  f"dual_stable={e['reference_dual_stable']} | {ref_str}")

    print("\n## Grazing-margin convergence by depth (signed Phi)")
    print("| branch | depth | closest negative Phi [m] | closest positive Phi [m] |")
    print("|---|---|---|---|")
    for b in sorted(margin):
        for d, vals in margin[b].items():
            print(f"| {b} | {d} | {vals['closest_negative_phi_m']} | "
                  f"{vals['closest_positive_phi_m']} |")

    print("\n## OPEN_BOUNDARY refined intersections")
    for edge, brackets in open_int.items():
        print(f"  {edge}: {len(brackets)} refined bracket(s)")
        for b in brackets[:6]:
            print(f"    {b}")

    print("\n## Health / stop gates")
    print(json.dumps(summary["health"], indent=2))
    print(f"stop gate triggered : {summary['stop_gate_triggered']}")
    for r in summary["stop_gate_reasons"]:
        print(f"  {r}")
    print(f"ready_for_F4        : {summary['ready_for_F4']}")
    print("F3 SUMMARIZER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
