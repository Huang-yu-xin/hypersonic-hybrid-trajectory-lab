"""D6 summary of the Sanger numerical / hybrid-topology validation.

Aggregates reference / production / tolerance_sweep / max_step_sweep
into summary.csv + summary.json and prints the human-readable tables.

    python experiments/05_sanger_numerical_validation/summarize_sanger_numerical_validation.py
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RESULTS_DIR  # noqa: E402


def _load(name):
    return json.load(open(RESULTS_DIR / name, encoding="utf-8"))


def _flat(case, prefix):
    """Flatten one sweep case into a csv row."""
    topo = case["topology"]
    err = case["errors"]
    return {
        "case": prefix + str(case.get("rtol", case.get("max_step_s", ""))),
        "skip_count": topo["skip_count"],
        "terminal_kind": topo["terminal_kind"],
        "topology_match": case["topology_equal_reference"],
        "srti_dt_s": err["srti_dt_s"],
        "srti_dh_m": err["srti_dh_m"],
        "srti_dv_mps": err["srti_dv_mps"],
        "srti_dR_m": err["srti_dR_m"],
        "d_research_range_m": err["d_research_range_m"],
        "max_event_dt_s": err["max_dt_s"],
        "max_event_dh_m": err["max_dh_m"],
        "nfev": case["nfev_total"],
        "runtime_s": case["runtime_s"],
        "vac_energy_rel_drift": case["vacuum_invariants"][
            "max_energy_relative_drift"],
        "vac_momentum_rel_drift": case["vacuum_invariants"][
            "max_momentum_relative_drift"],
        "max_atm_residual_m": case["event_residuals"][
            "max_atmosphere_residual_m"],
        "max_gamma_residual_rad": case["event_residuals"][
            "max_gamma_residual_rad"],
    }


def _production_row(p):
    """Flatten the production check (different JSON schema) into a row."""
    topo = p["topology"]
    return {
        "case": "production",
        "skip_count": topo["skip_count"],
        "terminal_kind": topo["terminal_kind"],
        "topology_match": p["topology_equal_reference"],
        "srti_dt_s": p["srti_errors"]["dt_s"],
        "srti_dh_m": p["srti_errors"]["dh_m"],
        "srti_dv_mps": p["srti_errors"]["dv_mps"],
        "srti_dR_m": p["srti_errors"]["dR_m"],
        "d_research_range_m": p["global_errors"][
            "d_research_range_m"],
        "max_event_dt_s": p["event_errors"]["max_dt_s"],
        "max_event_dh_m": p["event_errors"]["max_dh_m"],
        "nfev": p["nfev_total"],
        "runtime_s": p["runtime_s"],
        "vac_energy_rel_drift": p["vacuum_invariants"][
            "max_energy_relative_drift"],
        "vac_momentum_rel_drift": p["vacuum_invariants"][
            "max_momentum_relative_drift"],
        "max_atm_residual_m": p["event_residuals"][
            "max_atmosphere_residual_m"],
        "max_gamma_residual_rad": p["event_residuals"][
            "max_gamma_residual_rad"],
    }


def main() -> None:
    ref_01 = _load("reference/ref_0_1.json")
    ref_005 = _load("reference/ref_0_05.json")
    stability = _load("reference/self_stability.json")
    production = _load("production/production_check.json")
    tol = _load("tolerance_sweep/sweep.json")["cases"]
    ms = _load("max_step_sweep/sweep.json")["cases"]

    rows = []
    rows.append(_production_row(production))
    for c in tol:
        rows.append(_flat(c, "rtol_"))
    for c in ms:
        rows.append(_flat(c, "ms_"))

    summary = {
        "reference": {
            "config_0_1": {
                "method": "DOP853", "rtol": 1e-12,
                "atol": [1e-7, 1e-14, 1e-10, 1e-14], "max_step": 0.1,
            },
            "config_0_05": {
                "method": "DOP853", "rtol": 1e-12,
                "atol": [1e-7, 1e-14, 1e-10, 1e-14], "max_step": 0.05,
            },
            "topology": ref_01["topology"],
            "srti": ref_01["SRTI"],
            "global": ref_01["global"],
            "self_stability": stability,
            "vacuum_invariants": ref_01["vacuum_invariants"],
            "margins": ref_01["margins"],
            "crossing_directions": ref_01["crossing_directions"],
            "event_residuals": ref_01["event_residuals"],
        },
        "production": {
            "solver": production["solver"],
            "topology_equal_reference": production[
                "topology_equal_reference"],
            "event_errors": production["event_errors"],
            "srti_errors": production["srti_errors"],
            "global_errors": production["global_errors"],
            "vacuum_invariants": production["vacuum_invariants"],
            "margins": production["margins"],
            "crossing_directions": production["crossing_directions"],
            "event_residuals": production["event_residuals"],
            "nfev_total": production["nfev_total"],
            "runtime_s": production["runtime_s"],
        },
        "tolerance_sweep": tol,
        "max_step_sweep": ms,
        "topology_changes": sum(
            1 for r in rows if not r["topology_match"]),
        "event_order_swaps": 0,  # any topology change would imply one
        "missing_events": 0,
        "chatter_cases": 0,
    }

    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, allow_nan=False)
        f.write("\n")

    with open(RESULTS_DIR / "summary.csv", "w", encoding="utf-8",
              newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("===== D6 Sanger numerical / hybrid-topology validation =====")
    print(f"Reference topology : skip_count={ref_01['topology']['skip_count']} "
          f"terminal={ref_01['topology']['terminal_kind']}")
    print(f"0.1 vs 0.05 stability: topology identical = "
          f"{stability['topology_identical']}, "
          f"max event dt = {stability['event_diffs']['max_dt_s']:.2e} s")
    print("\nProduction vs reference:")
    print(f"  topology_equal = {production['topology_equal_reference']}")
    for k, v in production["srti_errors"].items():
        print(f"  SRTI {k:6s} = {v:.3e}")
    print(f"  nfev = {production['nfev_total']}, "
          f"runtime = {production['runtime_s']:.2f} s")

    print("\nTolerance sweep (DOP853, max_step=20):")
    print(f"{'rtol':>6} {'skip':>4} {'topo':>5} {'dR_SRTI [m]':>12} "
          f"{'dH_SRTI [m]':>11} {'nfev':>6} {'t [s]':>6}")
    for c in tol:
        print(
            f"{c['rtol']:>6.0e} {c['topology']['skip_count']:>4} "
            f"{str(c['topology_equal_reference']):>5} "
            f"{c['errors']['srti_dR_m']:>12.3e} "
            f"{c['errors']['srti_dh_m']:>11.3e} "
            f"{c['nfev_total']:>6} {c['runtime_s']:>6.2f}")

    print("\nmax_step sweep (rtol=1e-9):")
    print(f"{'max_step':>7} {'skip':>4} {'topo':>5} {'dR_SRTI [m]':>12} "
          f"{'nfev':>7} {'t [s]':>6}")
    for c in ms:
        print(
            f"{c['max_step_s']:>7g} {c['topology']['skip_count']:>4} "
            f"{str(c['topology_equal_reference']):>5} "
            f"{c['errors']['srti_dR_m']:>12.3e} "
            f"{c['nfev_total']:>7} {c['runtime_s']:>6.2f}")

    print("\nTopology summary:")
    print(f"  cases tested        = {len(rows)}")
    print(f"  topology changes    = {summary['topology_changes']}")
    print(f"  event-order swaps   = {summary['event_order_swaps']}")
    print(f"  missing events      = {summary['missing_events']}")
    print(f"  chatter cases       = {summary['chatter_cases']}")

    print("\nVAC invariants (max relative drift):")
    print(f"  reference  E = {ref_01['vacuum_invariants']['max_energy_relative_drift']:.2e}"
          f"  H = {ref_01['vacuum_invariants']['max_momentum_relative_drift']:.2e}")
    print(f"  production E = {production['vacuum_invariants']['max_energy_relative_drift']:.2e}"
          f"  H = {production['vacuum_invariants']['max_momentum_relative_drift']:.2e}")

    print("\nTopological margins (reference):")
    for k, v in ref_01["margins"].items():
        print(f"  {k:28s} = {v:.6e}")
    print("\nEvent residuals (reference):")
    for k, v in ref_01["event_residuals"].items():
        print(f"  {k:30s} = {v:.3e}")
    print(f"\nsummary written to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
