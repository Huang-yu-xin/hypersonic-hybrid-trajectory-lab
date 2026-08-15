"""E3 runner -- atmospheric exposure and energy mechanism analysis.

Executes the frozen E0 Protocol D (common atmospheric exposure), the E2
checkpoint exposure diagnostics, the segment-level mechanical-energy
accounting, and the Sanger VAC-coast diagnostics; writes full-precision
JSON artifacts and visualization-only curve CSVs under
``results/qian_sanger_comparison/mechanism/`` (untracked).

    E3 ATMOSPHERIC EXPOSURE / ENERGY MECHANISM
    CANDIDATE -- NOT FINAL PHASE E FREEZE
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

from hyptraj.analysis import (
    build_energy_budget,
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    energy_curve_samples,
    exposure_diagnostic_at_common_range,
    exposure_diagnostic_at_common_time,
    run_common_atmospheric_exposure_comparison,
    run_common_range_comparison,
    run_common_time_comparison,
    total_vac_duration,
    total_vac_range,
    verify_comparison_alignment,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

OUT_DIR = Path("results/qian_sanger_comparison/mechanism")


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


def _state_to_dict(state) -> dict:
    return {
        "time_s": state.time_s,
        "radius_m": state.radius_m,
        "altitude_m": state.altitude_m,
        "theta_rad": state.theta_rad,
        "range_m": state.range_m,
        "velocity_mps": state.velocity_mps,
        "gamma_rad": state.gamma_rad,
        "specific_mechanical_energy_jpkg":
            state.specific_mechanical_energy_jpkg,
        "mode": state.mode,
        "source_mode": state.source_mode,
    }


def _protocol_d_dict(result) -> dict:
    return {
        "status": result.status.value,
        "common_exposure_s": result.common_exposure_s,
        "qian_inverse_status": result.qian_inverse_status.value,
        "sanger_inverse_status": result.sanger_inverse_status.value,
        "qian_plateau_interval_s": result.qian_plateau_interval_s,
        "sanger_plateau_interval_s": result.sanger_plateau_interval_s,
        "qian_time_s": result.qian_time_s,
        "sanger_time_s": result.sanger_time_s,
        "qian_state": (_state_to_dict(result.qian_state)
                       if result.qian_state is not None else None),
        "sanger_state": (_state_to_dict(result.sanger_state)
                         if result.sanger_state is not None else None),
        "elapsed_time_extension_s": result.elapsed_time_extension_s,
        "delta_range_m": result.delta_range_m,
        "delta_altitude_m": result.delta_altitude_m,
        "delta_velocity_mps": result.delta_velocity_mps,
        "delta_specific_energy_jpkg": result.delta_specific_energy_jpkg,
        "qian_energy_loss_jpkg": result.qian_energy_loss_jpkg,
        "sanger_energy_loss_jpkg": result.sanger_energy_loss_jpkg,
        "qian_mode": result.qian_mode,
        "sanger_mode": result.sanger_mode,
        "qian_source_mode": result.qian_source_mode,
        "sanger_source_mode": result.sanger_source_mode,
        "initial_energy_jpkg": result.initial_energy_jpkg,
    }


def _diagnostic_dict(diag) -> dict:
    return {
        "checkpoint": diag.checkpoint,
        "qian_time_s": diag.qian_time_s,
        "sanger_time_s": diag.sanger_time_s,
        "qian_exposure_s": diag.qian_exposure_s,
        "sanger_exposure_s": diag.sanger_exposure_s,
        "delta_tau_s": diag.delta_tau_s,
        "qian_energy_loss_jpkg": diag.qian_energy_loss_jpkg,
        "sanger_energy_loss_jpkg": diag.sanger_energy_loss_jpkg,
        "qian_vac_duration_s": diag.qian_vac_duration_s,
        "sanger_vac_duration_s": diag.sanger_vac_duration_s,
    }


def _segment_dict(seg) -> dict:
    return {
        "trajectory_name": seg.trajectory_name,
        "segment_index": seg.segment_index,
        "source_mode": seg.source_mode,
        "normalized_mode": seg.normalized_mode,
        "t_start_s": seg.t_start_s,
        "t_end_s": seg.t_end_s,
        "duration_s": seg.duration_s,
        "range_start_m": seg.range_start_m,
        "range_end_m": seg.range_end_m,
        "delta_range_m": seg.delta_range_m,
        "energy_start_jpkg": seg.energy_start_jpkg,
        "energy_end_jpkg": seg.energy_end_jpkg,
        "raw_energy_loss_jpkg": seg.raw_energy_loss_jpkg,
        "relative_energy_change": seg.relative_energy_change,
    }


def _budget_dict(budget) -> dict:
    return {
        "trajectory_name": budget.trajectory_name,
        "initial_energy_jpkg": budget.initial_energy_jpkg,
        "terminal_energy_jpkg": budget.terminal_energy_jpkg,
        "total_energy_loss_jpkg": budget.total_energy_loss_jpkg,
        "atm": {
            "mode": budget.atm.mode,
            "duration_s": budget.atm.duration_s,
            "range_increment_m": budget.atm.range_increment_m,
            "raw_energy_loss_jpkg": budget.atm.raw_energy_loss_jpkg,
        },
        "vac": {
            "mode": budget.vac.mode,
            "duration_s": budget.vac.duration_s,
            "range_increment_m": budget.vac.range_increment_m,
            "raw_energy_loss_jpkg": budget.vac.raw_energy_loss_jpkg,
        },
        "segment_budgets": [_segment_dict(s) for s in budget.segment_budgets],
        "telescoping_residual_jpkg": budget.telescoping_residual_jpkg,
    }


def _write_curve_csv(path: Path, curve: dict) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_s", "range_m", "altitude_m", "velocity_mps",
            "specific_energy_jpkg", "energy_loss_jpkg",
            "normalized_mode", "source_mode", "segment_index",
        ])
        for row in zip(curve["time_s"], curve["range_m"],
                       curve["altitude_m"], curve["velocity_mps"],
                       curve["specific_energy_jpkg"],
                       curve["energy_loss_jpkg"],
                       curve["normalized_mode"], curve["source_mode"],
                       curve["segment_index"]):
            writer.writerow(row)


def _fmt_km(m: float) -> str:
    return f"{m / 1000.0:.6f}"


def _fmt_mj(e: float) -> str:
    return f"{e / 1e6:.6f}"


def main() -> int:
    print("E3 ATMOSPHERIC EXPOSURE / ENERGY MECHANISM")
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

    # E2 protocols are re-run ONLY to obtain the checkpoints; their
    # formulas are never re-implemented here.
    common_time = run_common_time_comparison(qian, sanger)
    common_range = run_common_range_comparison(qian, sanger)

    # Protocol D.
    protocol_d = run_common_atmospheric_exposure_comparison(qian, sanger)
    if protocol_d.status.value != "UNIQUE":
        print(f"Protocol D AMBIGUOUS: qian={protocol_d.qian_inverse_status} "
              f"sanger={protocol_d.sanger_inverse_status} -- aborting")
        return 1

    # E2 checkpoint exposure diagnostics.
    diag_time = exposure_diagnostic_at_common_time(qian, sanger, common_time)
    diag_range = exposure_diagnostic_at_common_range(qian, sanger,
                                                     common_range)

    # Energy budgets + VAC structure.
    qian_budget = build_energy_budget(qian)
    sanger_budget = build_energy_budget(sanger)
    sanger_vac_segments = [s for s in sanger_budget.segment_budgets
                           if s.normalized_mode == "VAC"]
    max_vac_drift = max(abs(s.raw_energy_loss_jpkg)
                        for s in sanger_vac_segments)
    max_vac_rel_drift = max(abs(s.relative_energy_change)
                            for s in sanger_vac_segments)

    print("\n=== Protocol D -- Common Atmospheric Exposure ===")
    print(f"tau_common = {protocol_d.common_exposure_s:.6f} s "
          f"(= min total exposures)")
    print(f"{'Metric':<24}{'Qian':>16}{'Sanger':>16}{'Sanger-Qian':>18}")
    rows = [
        ("atmospheric exposure [s]",
         f"{protocol_d.common_exposure_s:.6f}",
         f"{protocol_d.common_exposure_s:.6f}", "0.0"),
        ("elapsed time [s]",
         f"{protocol_d.qian_time_s:.6f}",
         f"{protocol_d.sanger_time_s:.6f}",
         f"{protocol_d.elapsed_time_extension_s:.6f}"),
        ("range [km]",
         _fmt_km(protocol_d.qian_state.range_m),
         _fmt_km(protocol_d.sanger_state.range_m),
         _fmt_km(protocol_d.delta_range_m)),
        ("altitude [km]",
         _fmt_km(protocol_d.qian_state.altitude_m),
         _fmt_km(protocol_d.sanger_state.altitude_m),
         _fmt_km(protocol_d.delta_altitude_m)),
        ("velocity [m/s]",
         f"{protocol_d.qian_state.velocity_mps:.3f}",
         f"{protocol_d.sanger_state.velocity_mps:.3f}",
         f"{protocol_d.delta_velocity_mps:.3f}"),
        ("specific energy [MJ/kg]",
         _fmt_mj(protocol_d.qian_state.specific_mechanical_energy_jpkg),
         _fmt_mj(protocol_d.sanger_state.specific_mechanical_energy_jpkg),
         _fmt_mj(protocol_d.delta_specific_energy_jpkg)),
        ("energy loss [MJ/kg]",
         _fmt_mj(protocol_d.qian_energy_loss_jpkg),
         _fmt_mj(protocol_d.sanger_energy_loss_jpkg), ""),
        ("normalized mode",
         f"{protocol_d.qian_mode}", f"{protocol_d.sanger_mode}", ""),
        ("source mode",
         f"{protocol_d.qian_source_mode}",
         f"{protocol_d.sanger_source_mode}", ""),
    ]
    for label, q, s, d in rows:
        print(f"{label:<24}{q:>16}{s:>16}{d:>18}")

    print("\n=== E2 Checkpoint Exposure Diagnostics ===")
    print("Checkpoint   | tau_Q [s]  | tau_S [s]  | DeltaTau [s] | "
          "Loss_Q [MJ/kg] | Loss_S [MJ/kg]")
    for diag in (diag_time, diag_range):
        print(f"{diag.checkpoint:<12} | {diag.qian_exposure_s:>9.6f} | "
              f"{diag.sanger_exposure_s:>9.6f} | {diag.delta_tau_s:>11.6f} | "
              f"{diag.qian_energy_loss_jpkg / 1e6:>13.6f} | "
              f"{diag.sanger_energy_loss_jpkg / 1e6:>13.6f}")

    print("\n=== Energy Budgets ===")
    print(f"{'Trajectory / Mode':<20}{'Duration [s]':>14}"
          f"{'Range [km]':>14}{'Raw loss [MJ/kg]':>18}")
    for label, agg in (
        ("Qian ATM", qian_budget.atm),
        ("Qian TOTAL", qian_budget),
        ("Sanger ATM", sanger_budget.atm),
        ("Sanger VAC", sanger_budget.vac),
        ("Sanger TOTAL", sanger_budget),
    ):
        if hasattr(agg, "total_energy_loss_jpkg"):
            print(f"{label:<20}{agg.atm.duration_s + agg.vac.duration_s:>14.6f}"
                  f"{(agg.atm.range_increment_m + agg.vac.range_increment_m) / 1000:>14.6f}"
                  f"{agg.total_energy_loss_jpkg / 1e6:>18.6f}")
        else:
            print(f"{label:<20}{agg.duration_s:>14.6f}"
                  f"{agg.range_increment_m / 1000:>14.6f}"
                  f"{agg.raw_energy_loss_jpkg / 1e6:>18.6f}")

    print("\nSanger segment detail:")
    for seg in sanger_budget.segment_budgets:
        print(f"  seg {seg.segment_index} {seg.source_mode:<10} "
              f"dur={seg.duration_s:>9.6f} s  "
              f"dR={seg.delta_range_m / 1000:>10.6f} km  "
              f"raw loss={seg.raw_energy_loss_jpkg:>14.9f} J/kg  "
              f"rel={seg.relative_energy_change:>12.3e}")

    print("\n=== Sanger VAC Diagnostics ===")
    print(f"total VAC duration = {total_vac_duration(sanger):.6f} s")
    print(f"total VAC range    = {total_vac_range(sanger) / 1000:.6f} km")
    print(f"VAC segments       = {len(sanger_vac_segments)}")
    print(f"max abs energy drift    = {max_vac_drift:.3e} J/kg")
    print(f"max relative energy drift = {max_vac_rel_drift:.3e}")

    # ------------------------------------------------------------------
    # Artifacts.
    # ------------------------------------------------------------------
    summary = {
        "schema_version": "e3-mechanism-v1",
        "git_commit": _git_info()["git_commit"],
        "branch": _git_info()["branch"],
        "comparison_protocol": "E0",
        "protocol_d": {
            "tau_common": protocol_d.common_exposure_s,
            "qian_inverse_status": protocol_d.qian_inverse_status.value,
            "sanger_inverse_status": protocol_d.sanger_inverse_status.value,
            "qian_time_s": protocol_d.qian_time_s,
            "sanger_time_s": protocol_d.sanger_time_s,
            "elapsed_time_extension_s": protocol_d.elapsed_time_extension_s,
            "delta_range_m": protocol_d.delta_range_m,
            "delta_altitude_m": protocol_d.delta_altitude_m,
            "delta_velocity_mps": protocol_d.delta_velocity_mps,
            "delta_specific_energy_jpkg":
                protocol_d.delta_specific_energy_jpkg,
            "qian_energy_loss_jpkg": protocol_d.qian_energy_loss_jpkg,
            "sanger_energy_loss_jpkg": protocol_d.sanger_energy_loss_jpkg,
        },
        "e2_mechanism_diagnostics": {
            "common_time": _diagnostic_dict(diag_time),
            "common_range": _diagnostic_dict(diag_range),
        },
        "energy_budgets": {
            "qian": _budget_dict(qian_budget),
            "sanger": _budget_dict(sanger_budget),
        },
        "vac_diagnostics": {
            "total_vac_duration_s": total_vac_duration(sanger),
            "total_vac_range_m": total_vac_range(sanger),
            "max_abs_energy_drift_jpkg": max_vac_drift,
            "max_relative_energy_drift": max_vac_rel_drift,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "common_atmospheric_exposure.json", "w",
              encoding="utf-8") as f:
        json.dump(_protocol_d_dict(protocol_d), f, indent=2)
    with open(OUT_DIR / "energy_budget.json", "w", encoding="utf-8") as f:
        json.dump({
            "qian": _budget_dict(qian_budget),
            "sanger": _budget_dict(sanger_budget),
        }, f, indent=2)
    with open(OUT_DIR / "mechanism_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Visualization-only curve data (E3 §23-§24): these CSV samples are
    # ONLY for the future E5 R-vs-energy-loss figures and never drive
    # any formal checkpoint.
    _write_curve_csv(OUT_DIR / "qian_energy_curve.csv",
                     energy_curve_samples(qian))
    _write_curve_csv(OUT_DIR / "sanger_energy_curve.csv",
                     energy_curve_samples(sanger))

    print(f"\nArtifacts written to {OUT_DIR}")
    print("E3 RUNNER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
