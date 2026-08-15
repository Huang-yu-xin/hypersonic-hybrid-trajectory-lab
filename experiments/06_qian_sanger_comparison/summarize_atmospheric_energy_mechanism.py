"""E3 summarizer -- read-only view of the mechanism analysis.

Reads ONLY the E3 artifacts under
``results/qian_sanger_comparison/mechanism/`` (no re-integration) and
prints the Protocol D result, the E2 exposure context, the energy
budgets, the VAC diagnostics, and the interpretation boundaries.
"""

import json
import sys
from pathlib import Path

MECH_DIR = Path("results/qian_sanger_comparison/mechanism")


def _km(m: float) -> str:
    return f"{m / 1000.0:.3f}"


def _mj(e: float) -> str:
    return f"{e / 1e6:.4f}"


def main() -> int:
    missing = [p for p in ("mechanism_summary.json", "energy_budget.json",
                           "common_atmospheric_exposure.json")
               if not (MECH_DIR / p).exists()]
    if missing:
        print(f"Missing artifacts: {missing}")
        print("Run experiments/06_qian_sanger_comparison/"
              "run_atmospheric_energy_mechanism.py first.")
        return 1

    with open(MECH_DIR / "mechanism_summary.json", encoding="utf-8") as f:
        s = json.load(f)
    with open(MECH_DIR / "energy_budget.json", encoding="utf-8") as f:
        budgets = json.load(f)

    print("E3 ATMOSPHERIC EXPOSURE / ENERGY MECHANISM -- CANDIDATE "
          "(NOT FREEZED)")
    print("=" * 72)
    print(f"git commit : {s['git_commit']} ({s['branch']})")
    print(f"protocol   : {s['comparison_protocol']}")

    pd = s["protocol_d"]
    print("\nProtocol D (common atmospheric exposure)")
    print("-----------------------------------------")
    print(f"tau_common                    = {pd['tau_common']:.6f} s")
    print(f"Qian  elapsed time            = {pd['qian_time_s']:.6f} s")
    print(f"Sanger elapsed time           = {pd['sanger_time_s']:.6f} s")
    print(f"elapsed-time extension (S-Q)  = {pd['elapsed_time_extension_s']:.6f} s")
    print(f"DeltaR_atm_exposure          = {_km(pd['delta_range_m'])} km")
    print(f"DeltaH_tau                   = {_km(pd['delta_altitude_m'])} km")
    print(f"DeltaV_tau                   = {pd['delta_velocity_mps']:.2f} m/s")
    print(f"DeltaE_tau                   = {_mj(pd['delta_specific_energy_jpkg'])} MJ/kg")
    print(f"Qian energy loss             = {_mj(pd['qian_energy_loss_jpkg'])} MJ/kg")
    print(f"Sanger energy loss           = {_mj(pd['sanger_energy_loss_jpkg'])} MJ/kg")

    print("\nE2 exposure context")
    print("-------------------")
    for name, diag in s["e2_mechanism_diagnostics"].items():
        print(f"{name:<13} tau_Q={diag['qian_exposure_s']:.3f} s  "
              f"tau_S={diag['sanger_exposure_s']:.3f} s  "
              f"DeltaTau={diag['delta_tau_s']:.3f} s  "
              f"Loss_Q={_mj(diag['qian_energy_loss_jpkg'])} MJ/kg  "
              f"Loss_S={_mj(diag['sanger_energy_loss_jpkg'])} MJ/kg")

    print("\nEnergy budget")
    print("-------------")
    for traj in ("qian", "sanger"):
        b = budgets[traj]
        print(f"{traj.upper()}: total loss = {_mj(b['total_energy_loss_jpkg'])} MJ/kg "
              f"| ATM dur={b['atm']['duration_s']:.1f} s "
              f"range={_km(b['atm']['range_increment_m'])} km "
              f"loss={_mj(b['atm']['raw_energy_loss_jpkg'])} MJ/kg"
              + (f" | VAC dur={b['vac']['duration_s']:.1f} s "
                 f"range={_km(b['vac']['range_increment_m'])} km "
                 f"raw loss={b['vac']['raw_energy_loss_jpkg']:.3e} J/kg"
                 if traj == "sanger" else ""))

    vd = s["vac_diagnostics"]
    print("\nVAC diagnostics")
    print("---------------")
    print(f"total VAC duration        = {vd['total_vac_duration_s']:.6f} s")
    print(f"total VAC range           = {_km(vd['total_vac_range_m'])} km")
    print(f"max abs energy drift      = {vd['max_abs_energy_drift_jpkg']:.3e} J/kg")
    print(f"max relative energy drift = {vd['max_relative_energy_drift']:.3e}")

    print("\nInterpretation boundaries")
    print("-------------------------")
    print("tau_ATM is atmospheric-mode exposure TIME only; it is not a")
    print("thermal/heat exposure and not a TPS load.  DeltaR_atm_exposure")
    print("is a same-exposure downrange difference; it is NOT a causal")
    print("'VAC contribution' quantity.  The accumulated VAC range is")
    print("structural accounting ('downrange accumulated while")
    print("aerodynamic force is disabled under the frozen VAC semantics'),")
    print("never 'VAC causes exactly X km of advantage'.  All statements")
    print("are deterministic, frozen-baseline comparisons.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
