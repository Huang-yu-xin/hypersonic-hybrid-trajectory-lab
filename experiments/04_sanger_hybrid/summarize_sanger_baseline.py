"""D5 human-readable summary of the canonical Sanger baseline.

Reads results/sanger_hybrid/baseline/summary.json and
ground_summary.json and prints a compact table.

    python experiments/04_sanger_hybrid/summarize_sanger_baseline.py

Research metrics stop at the SRTI; the ground endpoint is a
compatibility / visualization continuation only.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT / "results" / "sanger_hybrid" / "baseline"


def main() -> None:
    s = json.load(open(BASE_DIR / "summary.json", encoding="utf-8"))
    g = json.load(open(BASE_DIR / "ground_summary.json", encoding="utf-8"))

    print(f"===== {s['baseline_name']} =====")
    print(f"git commit            : {s['git_commit']} ({s['branch']})")
    print(f"Research endpoint     : SRTI")
    print(f"Skip count            : {s['hybrid_structure']['completed_skip_count']}")
    print(f"Mode sequence         : {' -> '.join(s['hybrid_structure']['mode_sequence'])}")

    print("\nCycle table:")
    print(
        f"{'Cycle':>5} | {'Entry t':>10} {'h_min km':>9} | "
        f"{'Exit t':>10} | {'Apogee km':>10} | "
        f"{'ATM dt':>9} {'VAC dt':>9} | {'dR_atm km':>10} {'dR_vac km':>10}"
    )
    for c in s["completed_cycles"]:
        print(
            f"{c['cycle_index']:>5} | {c['entry_time_s']:>10.2f} "
            f"{c['pullout_altitude_m'] / 1000.0:>9.3f} | "
            f"{c['exit_time_s']:>10.2f} | "
            f"{c['apogee_altitude_m'] / 1000.0:>10.3f} | "
            f"{c['atmospheric_duration_s']:>9.2f} "
            f"{c['vacuum_duration_s']:>9.2f} | "
            f"{c['atmospheric_range_m'] / 1000.0:>10.2f} "
            f"{c['vacuum_range_m'] / 1000.0:>10.2f}"
        )

    gm = s["global_metrics"]
    rti = s["SRTI"]
    print("\nResearch (stop at SRTI):")
    print(f"  research flight time  = {gm['research_flight_time_s']:.4f} s")
    print(f"  research range        = {gm['research_range_m'] / 1000.0:.4f} km")
    print(f"  maximum altitude      = {gm['maximum_altitude_m'] / 1000.0:.6f} km")
    print(f"  SRTI time / h / v / R = {rti['time_s']:.4f} s / "
          f"{rti['altitude_m']:.3f} m / {rti['velocity_mps']:.4f} m/s / "
          f"{rti['range_m'] / 1000.0:.4f} km")

    p = s["terminal_incomplete_pass"]
    if p is not None:
        print("\nTerminal incomplete pass (NOT a completed skip):")
        print(f"  entry / pullout / SRTI = {p['entry_time_s']:.2f} / "
              f"{p['pullout_time_s']:.2f} / {p['srti_time_s']:.2f} s")
        print(f"  duration / range / dE   = {p['atmospheric_duration_s']:.2f} s / "
              f"{p['range_increment_m'] / 1000.0:.2f} km / "
              f"{p['mechanical_energy_loss_jpkg']:.1f} J/kg")

    print("\nCompatibility ground endpoint (NOT research):")
    print(f"  ground time / R / v     = {g['ground_time_s']:.4f} s / "
          f"{g['ground_range_m'] / 1000.0:.4f} km / "
          f"{g['ground_velocity_mps']:.4f} m/s")
    print(f"  duration after SRTI     = {g['duration_from_srti_s']:.2f} s")
    print(f"  range after SRTI        = {g['range_after_srti_m'] / 1000.0:.2f} km")
    print(f"  compatibility_only      = {g['compatibility_only']}")

    print("\nResearch metrics stop at SRTI.")


if __name__ == "__main__":
    main()
