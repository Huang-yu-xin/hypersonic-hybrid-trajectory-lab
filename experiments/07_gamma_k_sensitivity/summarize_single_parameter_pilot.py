"""F1 summarizer -- read-only view of the single-parameter pilot.

Reads ONLY ``results/gamma_k_sensitivity/pilot/`` artifacts (no
re-integration) and prints the gamma / K slice regime tables with
Phase-F limits:

* regime labels are categorical observations, NOT derivatives;
* NA fields are printed as ``NA`` (never 0);
* no Phase-E Protocol B/C/D metrics exist in the F1 schema (F6 only);
* no optimization interpretation.
"""

import json
import sys
from pathlib import Path

SUMMARY_PATH = Path("results/gamma_k_sensitivity/pilot/pilot_summary.json")
GAMMA_JSON = Path("results/gamma_k_sensitivity/pilot/gamma_slice.json")
K_JSON = Path("results/gamma_k_sensitivity/pilot/k_slice.json")


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and v != v):  # NaN
        return "NA"
    return f"{v:.3f}"


def _km(m) -> str:
    return "NA" if m is None else f"{m / 1000.0:.3f}"


def _margin(row: dict) -> str:
    m_s = row.get("M_S_clearance_m")
    if m_s is not None:
        return f"{m_s / 1000.0:.3f} km"
    m_a = row.get("M_A_clearance_m") or []
    return f"{min(m_a) / 1000.0:.3f} km" if m_a else "NA"


def _table(rows: list[dict], param_name: str) -> None:
    header = (
        f"| {param_name} | Qian regime | Qian terminal range [km] | "
        f"Sanger regime | skip_count | Sanger terminal range [km] | "
        f"key margin |"
    )
    sep = "|---|---|---|---|---|---|---|"
    print(header)
    print(sep)
    for r in rows:
        q = r["qian"]
        s = r["sanger"]
        pv = q[param_name]
        q_range = _km(q.get("terminal_range_m"))
        s_range = _km(s.get("terminal_range_m"))
        skip = s.get("skip_count")
        print(
            f"| {_fmt(pv)} | {q['qian_regime']} | {q_range} | "
            f"{s['sanger_regime']} | "
            f"{skip if skip is not None else 'NA'} | {s_range} | "
            f"{_margin(s)} |"
        )


def main() -> int:
    if not SUMMARY_PATH.exists():
        print(f"pilot summary not found: {SUMMARY_PATH}")
        print("Run experiments/07_gamma_k_sensitivity/"
              "run_single_parameter_pilot.py first.")
        return 1

    with open(SUMMARY_PATH, encoding="utf-8") as f:
        s = json.load(f)
    with open(GAMMA_JSON, encoding="utf-8") as f:
        gamma = json.load(f)
    with open(K_JSON, encoding="utf-8") as f:
        k = json.load(f)

    print("F1 SINGLE-PARAMETER PILOT -- REGIME OBSERVATIONS (read-only)")
    print("=" * 72)
    print(f"git commit : {s['git_commit']}")
    print(f"anchor     : {'PASS' if s['baseline_anchor_pass'] else 'FAIL'} "
          f"({s['phase_e_anchor_tag']})")
    print(f"grid       : {s['grid']}")

    print("\n## Gamma slice (K = 3.0)")
    _table(gamma["rows"], "gamma0_deg")

    print("\n## K slice (gamma0 = -5.0 deg)")
    _table(k["rows"], "K")

    print("\n## Regime counts")
    print("Qian  :", json.dumps(s["qian"]["regime_counts"], indent=2))
    print("Sanger:", json.dumps(s["sanger"]["regime_counts"], indent=2))
    print("Sanger skip-count distribution:",
          json.dumps(s["sanger"]["skip_count_distribution"], indent=2))

    print("\n## Transition intervals")
    print("Gamma:", json.dumps(s["gamma_slice"]["transition_intervals"],
                               indent=2))
    print("K    :", json.dumps(s["k_slice"]["transition_intervals"],
                               indent=2))
    print("Gamma exact-topology-only:",
          json.dumps(s["gamma_slice"]["exact_topology_only"], indent=2))
    print("K exact-topology-only:",
          json.dumps(s["k_slice"]["exact_topology_only"], indent=2))

    print("\n## Stop gates")
    print(f"triggered : {s['stop_gate_triggered']}")
    for reason in s["stop_gate_reasons"]:
        print(f"  {reason}")
    print(f"ready_for_F2 : {s['ready_for_F2']}")

    print("\nF1 SUMMARIZER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
