"""F2 summarizer -- read-only view of the coarse regime map artifacts.

Reads ONLY ``results/gamma_k_sensitivity/coarse_map/`` (no re-integration)
and prints: domain, regime counts, skip-count distribution, joint
regimes, boundary candidates, brackets by gamma / by K, topology
margins, domain-edge / expansion status, health audit, ready-for-F3,
plus a compact 2D Sanger skip-count / regime matrix (rows = gamma0,
columns = K; split into two K blocks when wide).
"""

import json
import sys
from pathlib import Path

OUT_DIR = Path("results/gamma_k_sensitivity/coarse_map")


def _load(name: str) -> dict:
    with open(OUT_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _cell_label(regime) -> str:
    """Matrix cell code: N0/N1/N2..., GB, C, F, GR, or ?"""
    if isinstance(regime, int):
        return f"N{regime}"  # skip-count matrix cells
    if regime is None:
        return "?"
    if regime.startswith("SRTI_N"):
        return regime[-2:]  # "N2"
    if regime == "SANGER_GRAZING_BOUNDARY":
        return "GR"
    if regime == "GROUND_BEFORE_SRTI":
        return "GB"
    if regime == "CENSORED":
        return "C"
    if regime == "NUMERICAL_FAILURE":
        return "F"
    if regime == "INVALID_INPUT":
        return "I"
    return "?"


def _print_matrix(matrices: dict, sanger_key: str = "sanger_regime_matrix",
                  label: str = "Sanger regime") -> None:
    rows = matrices["gamma_grid"]
    cols = matrices["K_grid"]
    matrix = matrices[sanger_key]
    header = "gamma0\\K" + "".join(f"{k:>6}" for k in cols)
    print(f"\n## {label} matrix (rows = gamma0 [deg], cols = K)")
    print(header)
    for g, row in zip(rows, matrix):
        cells = "".join(f"{_cell_label(v):>6}" for v in row)
        print(f"{g:>7.2f}{cells}")


def _print_bracket_table(brackets: list[dict], by: str) -> None:
    if by == "gamma":
        print("\n| gamma0 | K_left | K_right | left regime | right regime |")
        print("|---|---|---|---|---|")
        for b in brackets:
            print(f"| {b['gamma0']:.2f} | {b['K_left']:.3f} | "
                  f"{b['K_right']:.3f} | {b['left_sanger_regime']} | "
                  f"{b['right_sanger_regime']} |")
    else:
        print("\n| K | gamma_left | gamma_right | left regime | right regime |")
        print("|---|---|---|---|---|")
        for b in brackets:
            print(f"| {b['K']:.3f} | {b['gamma_left']:.2f} | "
                  f"{b['gamma_right']:.2f} | {b['left_sanger_regime']} | "
                  f"{b['right_sanger_regime']} |")


def main() -> int:
    summary = _load("coarse_map_summary.json")
    matrices = _load("regime_matrices.json")
    cells = _load("boundary_cells.json")["cells"]
    brackets_g = _load("boundary_brackets_by_gamma.json")["brackets"]
    brackets_k = _load("boundary_brackets_by_K.json")["brackets"]

    print("F2 COARSE GAMMA0-K HYBRID REGIME MAP -- READ-ONLY SUMMARY")
    print("=" * 72)
    print(f"git commit : {summary['git_commit']}")

    print("\n## 1. Domain")
    print(f"initial : {summary['initial_domain']}")
    print(f"final   : {summary['final_domain']}")
    print(f"points  : initial={summary['initial_points']} "
          f"total={summary['total_unique_points']} "
          f"fresh={summary['fresh_points']} "
          f"cache-reused={summary['cache_reused_points']}")

    print("\n## 2. Qian regime counts")
    print(json.dumps(summary["qian"]["regime_counts"], indent=2))
    print("\n## 3. Sanger regime counts")
    print(json.dumps(summary["sanger"]["regime_counts"], indent=2))
    print("\n## 4. Sanger skip-count distribution")
    print(json.dumps(summary["sanger"]["skip_count_distribution"], indent=2))
    print("\n## 5. Joint regimes")
    print(json.dumps(summary["joint"]["regime_counts"], indent=2))

    print("\n## 6. Boundary candidates")
    b = summary["boundary"]
    print(f"cells           : {b['cell_count']}")
    print(f"candidates      : {b['candidate_cell_count']}")
    print(f"exact-only      : {b['exact_only_count']}")
    print(f"multiskip warns : {b['multiskip_warning_count']}")

    _print_matrix(matrices, "sanger_regime_matrix", "Sanger regime")
    _print_matrix(matrices, "skip_count_matrix", "Sanger skip count")

    print("\n## 7. Boundary brackets by gamma")
    _print_bracket_table(brackets_g, "gamma")
    print("\n## 8. Boundary brackets by K")
    _print_bracket_table(brackets_k, "K")

    print("\n## 9. Topology margins")
    print("global min M_A:", json.dumps(summary["margins"]["global_min_M_A"]))
    print("global min M_S:", json.dumps(summary["margins"]["global_min_M_S"]))
    print("edge min M_A:", json.dumps(summary["margins"]["edge_min_M_A"]))
    print("edge min M_S:", json.dumps(summary["margins"]["edge_min_M_S"]))

    print("\n## 10. Domain edge / expansion status")
    print(f"edge touches (candidate): {b['edge_touch_counts']}")
    exp = summary["domain_expansion"]
    print(f"expansion triggered: {exp['triggered']}")
    print(f"rounds: {json.dumps(exp['rounds'], indent=2)}")
    print(f"OPEN_BOUNDARY: {exp['open_boundaries']}")

    print("\n## 11. Health audit")
    print(json.dumps(summary["health"], indent=2))
    print(f"stop gate triggered: {summary['stop_gate_triggered']}")
    for r in summary["stop_gate_reasons"]:
        print(f"  {r}")

    print("\n## 12. Ready for F3")
    print(f"ready_for_F3: {summary['ready_for_F3']}")
    print("F2 SUMMARIZER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
