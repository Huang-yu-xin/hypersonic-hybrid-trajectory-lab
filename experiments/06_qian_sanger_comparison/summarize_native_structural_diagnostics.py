"""E4 summarizer -- read-only view of the diagnostics artifacts.

Reads ONLY the E4 JSON artifacts under
``results/qian_sanger_comparison/diagnostics/`` (no re-integration).
"""

import json
import sys
from pathlib import Path

DIAG_DIR = Path("results/qian_sanger_comparison/diagnostics")


def _km(m: float) -> str:
    return f"{m / 1000.0:.3f}"


def _mj(e: float) -> str:
    return f"{e / 1e6:.4f}"


def _kpa(pa: float) -> str:
    return f"{pa / 1000.0:.4f}"


def main() -> int:
    missing = [p for p in ("diagnostics_summary.json",
                           "native_endpoint.json",
                           "structural_diagnostics.json",
                           "aerodynamic_diagnostics.json")
               if not (DIAG_DIR / p).exists()]
    if missing:
        print(f"Missing artifacts: {missing}")
        print("Run experiments/06_qian_sanger_comparison/"
              "run_native_structural_diagnostics.py first.")
        return 1

    with open(DIAG_DIR / "diagnostics_summary.json", encoding="utf-8") as f:
        s = json.load(f)

    print("E4 NATIVE / STRUCTURAL / AERODYNAMIC DIAGNOSTICS -- CANDIDATE "
          "(NOT FREEZED)")
    print("=" * 72)
    print(f"git commit : {s['git_commit']} ({s['branch']})")
    print(f"protocol   : {s['comparison_protocol']}")

    ne = s["native_endpoint"]
    print("\nProtocol A (native research endpoint / mode persistence)")
    print("-------------------------------------------------------")
    print("RTI and SRTI have different feasibility semantics; this is "
          "not a common-condition performance ranking.")
    qt, st = ne["qian_terminal"], ne["sanger_terminal"]
    print(f"{'Metric':<26}{'Qian @ RTI':>16}{'Sanger @ SRTI':>16}")
    print(f"{'research duration [s]':<26}{qt['time_s']:>16.3f}"
          f"{st['time_s']:>16.3f}")
    print(f"{'research range [km]':<26}{_km(qt['range_m']):>16}"
          f"{_km(st['range_m']):>16}")
    print(f"{'terminal altitude [km]':<26}{_km(qt['altitude_m']):>16}"
          f"{_km(st['altitude_m']):>16}")
    print(f"{'terminal velocity [m/s]':<26}{qt['velocity_mps']:>16.1f}"
          f"{st['velocity_mps']:>16.1f}")
    print(f"{'terminal energy [MJ/kg]':<26}{_mj(qt['specific_energy_jpkg']):>16}"
          f"{_mj(st['specific_energy_jpkg']):>16}")
    print(f"{'total energy loss [MJ/kg]':<26}{_mj(qt['energy_loss_jpkg']):>16}"
          f"{_mj(st['energy_loss_jpkg']):>16}")
    print(f"descriptive differences: DeltaT={ne['delta_duration_s']:.3f} s  "
          f"DeltaR={_km(ne['delta_range_m'])} km  "
          f"DeltaV={ne['delta_velocity_mps']:.1f} m/s  "
          f"DeltaE={_mj(ne['delta_specific_energy_jpkg'])} MJ/kg")
    print(f"semantics: {ne['semantics']}")

    print("\nStructural diagnostics")
    print("----------------------")
    for name in ("qian", "sanger"):
        st2 = s["structural"][name]
        print(f"{name.upper()}: dur={st2['research_duration_s']:.3f} s  "
              f"ATM={st2['ATM_duration_s']:.3f} s ({st2['ATM_fraction']:.4f})  "
              f"VAC={st2['VAC_duration_s']:.3f} s ({st2['VAC_fraction']:.4f})  "
              f"h_min={_km(st2['min_altitude']['value_m'])} km  "
              f"h_max={_km(st2['max_altitude']['value_m'])} km  "
              f"v_min={st2['min_velocity_mps']:.1f} m/s")
        if st2["sanger_specific"]:
            sp = st2["sanger_specific"]
            print(f"  Sanger-specific: skip_count={sp['skip_count']}  "
                  f"VAC arcs={sp['vac_arc_count']}  apogees="
                  f"{[round(a, 1) for a in sp['vac_apogee_altitudes_m']]} m")

    aero = s["aerodynamic"]
    print(f"\nAerodynamic definition: q = {aero['definition']['q']}; "
          f"a_D = {aero['definition']['a_D']}")
    print(f"VAC semantics: {aero['definition']['vac_semantics']}")

    for window in ("native", "common_time", "common_range"):
        w = aero[window]
        qm = w["qian"]["max_q"]
        sm = w["sanger"]["max_q"]
        qa = w["qian"]["max_aD"]
        sa = w["sanger"]["max_aD"]
        print(f"\n{window} window maxima:")
        print(f"  max q  : Qian={_kpa(qm['value'])} kPa @ t={qm['time_s']:.2f} s "
              f"h={_km(qm['altitude_m'])} km | "
              f"Sanger={_kpa(sm['value'])} kPa @ t={sm['time_s']:.2f} s "
              f"h={_km(sm['altitude_m'])} km | "
              f"Delta={_kpa(sm['value'] - qm['value'])} kPa")
        print(f"  max a_D: Qian={qa['value']:.4f} m/s2 | "
              f"Sanger={sa['value']:.4f} m/s2 | "
              f"Delta={sa['value'] - qa['value']:.4f} m/s2")

    inst = aero["instantaneous_checkpoints"]
    print("\nInstantaneous E2 checkpoint diagnostics (not maxima):")
    ct = inst["common_time"]
    print(f"  common-time  t={ct['t_s']:.2f} s: q_Q={_kpa(ct['qian']['dynamic_pressure_pa'])} kPa  "
          f"q_S={_kpa(ct['sanger']['dynamic_pressure_pa'])} kPa  "
          f"aD_S={ct['sanger']['drag_deceleration_mps2']:.4f} m/s2")
    cr = inst["common_range"]
    print(f"  common-range t_Q={cr['qian_t_s']:.2f} / t_S={cr['sanger_t_s']:.2f} s: "
          f"q_Q={_kpa(cr['qian']['dynamic_pressure_pa'])} kPa  "
          f"q_S={_kpa(cr['sanger']['dynamic_pressure_pa'])} kPa")

    print("\nInterpretation boundaries")
    print("-------------------------")
    print("Native endpoint numbers are a mode-persistence description, not")
    print("a fair performance ranking.  q is dynamic pressure, NOT heat")
    print("flux; no thermal model exists (NO THERMAL CLAIMS).  a_D = D/m is")
    print("a drag deceleration magnitude, NOT a total g-load or load")
    print("factor.  No arbitrary thresholds and no composite scores are")
    print("used.  All statements are deterministic frozen-baseline")
    print("comparisons.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
