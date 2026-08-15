"""E4 runner -- native endpoint, structural and aerodynamic diagnostics.

Executes Protocol A (native endpoint mode-persistence comparison), the
structural diagnostics, and the aerodynamic diagnostics in the three
reporting windows (native / common-time / common-range, reusing the E2
checkpoints); writes full-precision JSON artifacts under
``results/qian_sanger_comparison/diagnostics/`` (untracked).

    E4 NATIVE / STRUCTURAL / AERODYNAMIC DIAGNOSTICS
    CANDIDATE -- NOT FINAL PHASE E FREEZE
"""

import json
import subprocess
import sys
from pathlib import Path

from hyptraj.analysis import (
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    run_common_range_comparison,
    run_common_time_comparison,
    verify_comparison_alignment,
)
from hyptraj.analysis.comparison_diagnostics import (
    aerodynamic_diagnostic_state,
    build_structural_diagnostics,
    native_aerodynamic_maxima,
    run_native_endpoint_comparison,
    windowed_aerodynamic_maxima,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

OUT_DIR = Path("results/qian_sanger_comparison/diagnostics")


def _git_info() -> dict[str, str]:
    def _run(cmd: list[str]) -> str:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 check=True)
            return out.stdout.strip()
        except (subprocess.CalledProcessError, OSError):
            return "unknown"

    return {
        "git_commit": _run(["git", "rev-parse", "HEAD"]),
        "branch": _run(["git", "branch", "--show-current"]),
    }


def _terminal_dict(term) -> dict:
    return {
        "kind": term.kind,
        "semantics": term.semantics,
        "time_s": term.time_s,
        "range_m": term.range_m,
        "altitude_m": term.altitude_m,
        "velocity_mps": term.velocity_mps,
        "specific_energy_jpkg": term.specific_energy_jpkg,
        "energy_loss_jpkg": term.energy_loss_jpkg,
        "normalized_mode": term.normalized_mode,
        "source_mode": term.source_mode,
    }


def _native_dict(result) -> dict:
    return {
        "semantics": result.semantics,
        "qian_terminal": _terminal_dict(result.qian_terminal),
        "sanger_terminal": _terminal_dict(result.sanger_terminal),
        "qian_duration_s": result.qian_duration_s,
        "sanger_duration_s": result.sanger_duration_s,
        "qian_range_m": result.qian_range_m,
        "sanger_range_m": result.sanger_range_m,
        "delta_duration_s": result.delta_duration_s,
        "delta_range_m": result.delta_range_m,
        "delta_altitude_m": result.delta_altitude_m,
        "delta_velocity_mps": result.delta_velocity_mps,
        "delta_specific_energy_jpkg": result.delta_specific_energy_jpkg,
    }


def _structural_dict(s) -> dict:
    return {
        "trajectory_name": s.trajectory_name,
        "research_duration_s": s.research_duration_s,
        "research_range_m": s.research_range_m,
        "min_altitude": {
            "value_m": s.min_altitude.value_m,
            "time_s": s.min_altitude.time_s,
            "source_mode": s.min_altitude.source_mode,
        },
        "max_altitude": {
            "value_m": s.max_altitude.value_m,
            "time_s": s.max_altitude.time_s,
            "source_mode": s.max_altitude.source_mode,
        },
        "min_velocity_mps": s.min_velocity_mps,
        "min_velocity_time_s": s.min_velocity_time_s,
        "terminal_velocity_mps": s.terminal_velocity_mps,
        "ATM_duration_s": s.ATM_duration_s,
        "VAC_duration_s": s.VAC_duration_s,
        "ATM_fraction": s.ATM_fraction,
        "VAC_fraction": s.VAC_fraction,
        "normalized_segment_count": s.normalized_segment_count,
        "source_segment_count": s.source_segment_count,
        "terminal_kind": s.terminal_kind,
        "qian_specific": s.qian_specific,
        "sanger_specific": s.sanger_specific,
    }


def _max_dict(m) -> dict:
    return {
        "quantity": m.quantity,
        "value": m.value,
        "time_s": m.time_s,
        "range_m": m.range_m,
        "altitude_m": m.altitude_m,
        "velocity_mps": m.velocity_mps,
        "normalized_mode": m.normalized_mode,
        "source_mode": m.source_mode,
        "segment_index": m.segment_index,
        "optimization_success": m.optimization_success,
        "candidate_count": m.candidate_count,
    }


def _maxima_dict(maxima: dict) -> dict:
    return {key: _max_dict(m) for key, m in maxima.items()}


def _aero_state_dict(d) -> dict:
    return {
        "time_s": d.time_s,
        "range_m": d.range_m,
        "altitude_m": d.altitude_m,
        "velocity_mps": d.velocity_mps,
        "normalized_mode": d.normalized_mode,
        "source_mode": d.source_mode,
        "density_kgpm3": d.density_kgpm3,
        "dynamic_pressure_pa": d.dynamic_pressure_pa,
        "drag_n": d.drag_n,
        "drag_deceleration_mps2": d.drag_deceleration_mps2,
    }


def _fmt_kpa(pa: float) -> str:
    return f"{pa / 1000.0:.6f}"


def main() -> int:
    print("E4 NATIVE / STRUCTURAL / AERODYNAMIC DIAGNOSTICS")
    print("CANDIDATE -- NOT FINAL PHASE E FREEZE")
    print("=" * 72)

    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)

    qian = build_qian_comparison_trajectory(env, vehicle, initial, control)
    sanger = build_sanger_comparison_trajectory(env, vehicle, initial, control)

    alignment = verify_comparison_alignment(qian, sanger)
    if not alignment.all_equal:
        print("ALIGNMENT FAILED -- aborting")
        return 1
    print(f"Alignment: {alignment.all_equal}")

    # E2 checkpoints reused (never redefined).
    common_time = run_common_time_comparison(qian, sanger)
    common_range = run_common_range_comparison(qian, sanger)

    # --- Protocol A ------------------------------------------------------
    native = run_native_endpoint_comparison(qian, sanger)
    print("\n=== Protocol A -- Native Research Endpoint / Mode Persistence ===")
    print("RTI and SRTI have different feasibility semantics; this table "
          "is not a common-condition performance ranking.")
    print(f"{'Metric':<26}{'Qian @ RTI':>16}{'Sanger @ SRTI':>16}"
          f"{'Difference':>18}")
    rows = [
        ("research duration [s]",
         f"{native.qian_duration_s:.6f}",
         f"{native.sanger_duration_s:.6f}",
         f"{native.delta_duration_s:.6f}"),
        ("research range [km]",
         f"{native.qian_range_m / 1000:.6f}",
         f"{native.sanger_range_m / 1000:.6f}",
         f"{native.delta_range_m / 1000:.6f}"),
        ("terminal altitude [km]",
         f"{native.qian_terminal.altitude_m / 1000:.6f}",
         f"{native.sanger_terminal.altitude_m / 1000:.6f}",
         f"{native.delta_altitude_m / 1000:.6f}"),
        ("terminal velocity [m/s]",
         f"{native.qian_terminal.velocity_mps:.3f}",
         f"{native.sanger_terminal.velocity_mps:.3f}",
         f"{native.delta_velocity_mps:.3f}"),
        ("terminal energy [MJ/kg]",
         f"{native.qian_terminal.specific_energy_jpkg / 1e6:.6f}",
         f"{native.sanger_terminal.specific_energy_jpkg / 1e6:.6f}",
         f"{native.delta_specific_energy_jpkg / 1e6:.6f}"),
        ("total energy loss [MJ/kg]",
         f"{native.qian_terminal.energy_loss_jpkg / 1e6:.6f}",
         f"{native.sanger_terminal.energy_loss_jpkg / 1e6:.6f}", ""),
        ("normalized mode",
         f"{native.qian_terminal.normalized_mode}",
         f"{native.sanger_terminal.normalized_mode}", ""),
        ("source mode",
         f"{native.qian_terminal.source_mode}",
         f"{native.sanger_terminal.source_mode}", ""),
    ]
    for label, q, s, d in rows:
        print(f"{label:<26}{q:>16}{s:>16}{d:>18}")
    print(f"semantics: {native.semantics}")

    # --- Structural ------------------------------------------------------
    qian_struct = build_structural_diagnostics(qian)
    sanger_struct = build_structural_diagnostics(sanger)
    print("\n=== Structural Diagnostics ===")
    print(f"{'Metric':<26}{'Qian':>16}{'Sanger':>16}")
    struct_rows = [
        ("research duration [s]",
         f"{qian_struct.research_duration_s:.6f}",
         f"{sanger_struct.research_duration_s:.6f}"),
        ("ATM duration [s]",
         f"{qian_struct.ATM_duration_s:.6f}",
         f"{sanger_struct.ATM_duration_s:.6f}"),
        ("VAC duration [s]",
         f"{qian_struct.VAC_duration_s:.6f}",
         f"{sanger_struct.VAC_duration_s:.6f}"),
        ("ATM fraction",
         f"{qian_struct.ATM_fraction:.6f}",
         f"{sanger_struct.ATM_fraction:.6f}"),
        ("VAC fraction",
         f"{qian_struct.VAC_fraction:.6f}",
         f"{sanger_struct.VAC_fraction:.6f}"),
        ("min altitude [km]",
         f"{qian_struct.min_altitude.value_m / 1000:.6f}",
         f"{sanger_struct.min_altitude.value_m / 1000:.6f}"),
        ("max altitude [km]",
         f"{qian_struct.max_altitude.value_m / 1000:.6f}",
         f"{sanger_struct.max_altitude.value_m / 1000:.6f}"),
        ("min velocity [m/s]",
         f"{qian_struct.min_velocity_mps:.3f}",
         f"{sanger_struct.min_velocity_mps:.3f}"),
        ("normalized segment count",
         f"{qian_struct.normalized_segment_count}",
         f"{sanger_struct.normalized_segment_count}"),
    ]
    for label, q, s in struct_rows:
        print(f"{label:<26}{q:>16}{s:>16}")
    print("Qian-specific structure:")
    for key, value in qian_struct.qian_specific.items():
        print(f"  {key} = {value}")
    print("Sanger-specific structure:")
    for key, value in sanger_struct.sanger_specific.items():
        print(f"  {key} = {value}")

    # --- Aerodynamic -----------------------------------------------------
    print("\n=== Aerodynamic Diagnostics ===")
    print("q = 0.5 * rho * v^2 [Pa, kPa reporting]; a_D = D/m [m/s^2];")
    print("VAC mode: rho_eff = q = D = a_D = 0 (frozen hybrid semantics).")

    qian_native = native_aerodynamic_maxima(qian)
    sanger_native = native_aerodynamic_maxima(sanger)
    qian_ct = windowed_aerodynamic_maxima(qian, common_time.common_time_s)
    sanger_ct = windowed_aerodynamic_maxima(sanger, common_time.common_time_s)
    qian_cr = windowed_aerodynamic_maxima(qian,
                                          common_range.qian_arrival_time_s)
    sanger_cr = windowed_aerodynamic_maxima(sanger,
                                            common_range.sanger_arrival_time_s)

    def _print_max(title, q_dict, s_dict, q_label, s_label):
        qm, sm = q_dict, s_dict
        print(f"\n{title}")
        print(f"{'Quantity':<28}{q_label:>16}{s_label:>16}"
              f"{'Sanger-Qian':>18}")
        print(f"{'max dynamic pressure [kPa]':<28}"
              f"{_fmt_kpa(qm['max_q'].value):>16}"
              f"{_fmt_kpa(sm['max_q'].value):>16}"
              f"{_fmt_kpa(sm['max_q'].value - qm['max_q'].value):>18}")
        print(f"{'max drag deceleration [m/s2]':<28}"
              f"{qm['max_aD'].value:>16.6f}"
              f"{sm['max_aD'].value:>16.6f}"
              f"{sm['max_aD'].value - qm['max_aD'].value:>18.6f}")

    _print_max("A. Native research windows", qian_native, sanger_native,
               "Qian", "Sanger")
    _print_max(f"B. Common-time window [0, {common_time.common_time_s:.3f} s]",
               qian_ct, sanger_ct, "Qian", "Sanger")
    _print_max(f"C. Common-range window (R_common = "
               f"{common_range.common_range_m / 1000:.3f} km)",
               qian_cr, sanger_cr, "Qian", "Sanger")

    print("\nPeak locations (time / altitude / mode):")
    for label, m in (
        ("Qian native q", qian_native["max_q"]),
        ("Qian native aD", qian_native["max_aD"]),
        ("Sanger native q", sanger_native["max_q"]),
        ("Sanger native aD", sanger_native["max_aD"]),
        ("Qian ct q", qian_ct["max_q"]),
        ("Sanger ct q", sanger_ct["max_q"]),
        ("Qian cr q", qian_cr["max_q"]),
        ("Sanger cr q", sanger_cr["max_q"]),
    ):
        print(f"  {label:<18} t={m.time_s:.6f} s  h={m.altitude_m / 1000:.3f} "
              f"km  {m.source_mode}")

    # Instantaneous E2 checkpoint diagnostics (separate from maxima).
    inst = {
        "common_time": {
            "t_s": common_time.common_time_s,
            "qian": _aero_state_dict(
                aerodynamic_diagnostic_state(qian,
                                             common_time.common_time_s)),
            "sanger": _aero_state_dict(
                aerodynamic_diagnostic_state(sanger,
                                             common_time.common_time_s)),
        },
        "common_range": {
            "qian_t_s": common_range.qian_arrival_time_s,
            "sanger_t_s": common_range.sanger_arrival_time_s,
            "qian": _aero_state_dict(
                aerodynamic_diagnostic_state(qian,
                                             common_range.qian_arrival_time_s)),
            "sanger": _aero_state_dict(
                aerodynamic_diagnostic_state(sanger,
                                             common_range.sanger_arrival_time_s)),
        },
    }
    print("\nInstantaneous E2 checkpoint diagnostics (not window maxima):")
    print(f"  common-time q: Qian={inst['common_time']['qian']['dynamic_pressure_pa'] / 1000:.6f} kPa  "
          f"Sanger={inst['common_time']['sanger']['dynamic_pressure_pa'] / 1000:.6f} kPa")
    print(f"  common-range q: Qian={inst['common_range']['qian']['dynamic_pressure_pa'] / 1000:.6f} kPa  "
          f"Sanger={inst['common_range']['sanger']['dynamic_pressure_pa'] / 1000:.6f} kPa")

    # --- Artifacts --------------------------------------------------------
    summary = {
        "schema_version": "e4-diagnostics-v1",
        "git_commit": _git_info()["git_commit"],
        "branch": _git_info()["branch"],
        "comparison_protocol": "E0",
        "native_endpoint": _native_dict(native),
        "structural": {
            "qian": _structural_dict(qian_struct),
            "sanger": _structural_dict(sanger_struct),
        },
        "aerodynamic": {
            "definition": {
                "q": "0.5 * rho * v^2 [Pa]",
                "a_D": "D / m [m/s^2]",
                "vac_semantics": "rho_eff = q = D = a_D = 0 (frozen "
                                  "hybrid L = D = 0)",
            },
            "native": {
                "qian": _maxima_dict(qian_native),
                "sanger": _maxima_dict(sanger_native),
            },
            "common_time": {
                "t_common_s": common_time.common_time_s,
                "qian": _maxima_dict(qian_ct),
                "sanger": _maxima_dict(sanger_ct),
            },
            "common_range": {
                "R_common_m": common_range.common_range_m,
                "qian_arrival_time_s": common_range.qian_arrival_time_s,
                "sanger_arrival_time_s": common_range.sanger_arrival_time_s,
                "qian": _maxima_dict(qian_cr),
                "sanger": _maxima_dict(sanger_cr),
            },
            "instantaneous_checkpoints": inst,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "native_endpoint.json", "w", encoding="utf-8") as f:
        json.dump(_native_dict(native), f, indent=2)
    with open(OUT_DIR / "structural_diagnostics.json", "w",
              encoding="utf-8") as f:
        json.dump(summary["structural"], f, indent=2)
    with open(OUT_DIR / "aerodynamic_diagnostics.json", "w",
              encoding="utf-8") as f:
        json.dump(summary["aerodynamic"], f, indent=2)
    with open(OUT_DIR / "diagnostics_summary.json", "w",
              encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nArtifacts written to {OUT_DIR}")
    print("E4 RUNNER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
