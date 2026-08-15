"""E2 summarizer -- read-only view of the common-condition candidate.

Reads ONLY ``results/qian_sanger_comparison/common_conditions/summary.json``
(no re-integration) and prints the common-time / common-range results
with the E0-limited deterministic interpretation.

The numbers shown are E2 CANDIDATE values (E6 will run the regression /
numerical audit); native endpoint ranges are never interpreted as direct
fair performance gains (E0 §4, §15).
"""

import json
import sys
from pathlib import Path

SUMMARY_PATH = Path("results/qian_sanger_comparison/common_conditions/"
                    "summary.json")


def _km(m: float) -> str:
    return f"{m / 1000.0:.3f}"


def _mj(e: float) -> str:
    return f"{e / 1e6:.4f}"


def main() -> int:
    if not SUMMARY_PATH.exists():
        print(f"summary.json not found: {SUMMARY_PATH}")
        print("Run experiments/06_qian_sanger_comparison/"
              "run_common_condition_comparison.py first.")
        return 1

    with open(SUMMARY_PATH, encoding="utf-8") as f:
        s = json.load(f)

    print("E2 COMMON-CONDITION COMPARISON -- CANDIDATE (NOT FREEZED)")
    print("=" * 72)
    print(f"git commit : {s['git_commit']} ({s['branch']})")
    print(f"protocol   : {s['comparison_protocol']}")

    ct = s["common_time"]
    print("\nCommon Time")
    print("-----------")
    print(f"t_common                       = {ct['common_time_s']:.6f} s")
    print(f"range      [km]  Qian={_km(ct['qian_state']['range_m'])}  "
          f"Sanger={_km(ct['sanger_state']['range_m'])}  "
          f"DeltaR={_km(ct['delta_range_m'])}")
    print(f"altitude   [km]  Qian={_km(ct['qian_state']['altitude_m'])}  "
          f"Sanger={_km(ct['sanger_state']['altitude_m'])}  "
          f"DeltaH={_km(ct['delta_altitude_m'])}")
    print(f"velocity [m/s]  Qian={ct['qian_state']['velocity_mps']:.2f}  "
          f"Sanger={ct['sanger_state']['velocity_mps']:.2f}  "
          f"DeltaV={ct['delta_velocity_mps']:.2f}")
    print(f"energy  [MJ/kg] Qian={_mj(ct['qian_state']['specific_mechanical_energy_jpkg'])}  "
          f"Sanger={_mj(ct['sanger_state']['specific_mechanical_energy_jpkg'])}  "
          f"DeltaE={_mj(ct['delta_specific_energy_jpkg'])}")
    print(f"energy loss [MJ/kg] Qian={_mj(ct['qian_energy_loss_jpkg'])}  "
          f"Sanger={_mj(ct['sanger_energy_loss_jpkg'])}")
    print(f"mode: Qian {ct['qian_mode']} ({ct['qian_source_mode']}) | "
          f"Sanger {ct['sanger_mode']} ({ct['sanger_source_mode']})")

    cr = s["common_range"]
    print("\nCommon Range")
    print("-----------")
    print(f"R_common                       = {_km(cr['common_range_m'])} km")
    print(f"arrival [s]  Qian={cr['qian_arrival_time_s']:.3f}  "
          f"Sanger={cr['sanger_arrival_time_s']:.3f}")
    print(f"time saving (Qian - Sanger)    = {cr['time_saving_s']:.3f} s")
    print(f"altitude   [km]  Qian={_km(cr['qian_state']['altitude_m'])}  "
          f"Sanger={_km(cr['sanger_state']['altitude_m'])}  "
          f"DeltaH={_km(cr['delta_altitude_m'])}")
    print(f"velocity [m/s]  Qian={cr['qian_state']['velocity_mps']:.2f}  "
          f"Sanger={cr['sanger_state']['velocity_mps']:.2f}  "
          f"DeltaV={cr['delta_velocity_mps']:.2f}")
    print(f"energy  [MJ/kg] Qian={_mj(cr['qian_state']['specific_mechanical_energy_jpkg'])}  "
          f"Sanger={_mj(cr['sanger_state']['specific_mechanical_energy_jpkg'])}  "
          f"DeltaE={_mj(cr['delta_specific_energy_jpkg'])}")
    print(f"root residuals [m]: Qian={cr['qian_range_residual_m']:.3e}  "
          f"Sanger={cr['sanger_range_residual_m']:.3e}")

    print("\nInterpretation (E0-limited, deterministic baseline only)")
    print("--------------------------------------------------------")
    delta_r = ct["delta_range_m"]
    delta_v = ct["delta_velocity_mps"]
    saving = cr["time_saving_s"]
    if delta_r > 0:
        print(f"At the same elapsed time t_common = {ct['common_time_s']:.1f} s, "
              f"Sanger has flown {_km(delta_r)} km farther downrange than "
              f"Qian (absolute).")
    if delta_v > 0:
        print(f"At t_common, Sanger retains {delta_v:.1f} m/s more velocity "
              f"than Qian (absolute).")
    if saving > 0:
        print(f"At the same downrange R_common = {_km(cr['common_range_m'])} km, "
              f"Sanger reaches the checkpoint {saving:.1f} s earlier than "
              f"Qian (absolute).")
    else:
        print(f"At the same downrange R_common = {_km(cr['common_range_m'])} km, "
              f"Sanger reaches the checkpoint {-saving:.1f} s later than "
              f"Qian (absolute).")
    print("These statements are limited to the frozen baseline "
          "configuration; they are deterministic comparisons, not "
          "statistical results, and not a native-endpoint ranking.")
    print("Native endpoint ranges are not interpreted as direct fair "
          "performance gains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
