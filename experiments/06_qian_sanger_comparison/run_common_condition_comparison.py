"""E2 runner -- common-time and common-range comparison candidate.

Executes the frozen E0 Protocol B (common time) and Protocol C (common
range) on the two Phase-E comparison realizations, writes full-precision
JSON artifacts under ``results/qian_sanger_comparison/common_conditions/``
(untracked), and prints human-readable tables.

Status of the produced numbers:

    E2 COMMON-CONDITION COMPARISON CANDIDATE
    NOT FINAL PHASE E FREEZE

The physics are frozen and the numerical realization is harmonized, but
E6 will still run the regression / numerical audit; no Phase E tag is
created here and no number in this output is a frozen regression value.
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
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

OUT_DIR = Path("results/qian_sanger_comparison/common_conditions")


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


def _common_time_dict(result) -> dict:
    return {
        "common_time_s": result.common_time_s,
        "qian_state": _state_to_dict(result.qian_state),
        "sanger_state": _state_to_dict(result.sanger_state),
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


def _common_range_dict(result) -> dict:
    return {
        "common_range_m": result.common_range_m,
        "qian_state": _state_to_dict(result.qian_state),
        "sanger_state": _state_to_dict(result.sanger_state),
        "qian_arrival_time_s": result.qian_arrival_time_s,
        "sanger_arrival_time_s": result.sanger_arrival_time_s,
        "time_saving_s": result.time_saving_s,
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
        "qian_range_residual_m": result.qian_range_residual_m,
        "sanger_range_residual_m": result.sanger_range_residual_m,
    }


def _fmt_km(m: float) -> str:
    return f"{m / 1000.0:.6f}"


def _print_common_time(result) -> None:
    print("\n=== Common-Time Comparison (Protocol B) ===")
    print(f"t_common = {result.common_time_s:.6f} s "
          f"= min(T_Q_RTI, T_S_SRTI)")
    print(f"{'Metric':<24}{'Qian':>16}{'Sanger':>16}{'Sanger-Qian':>18}")
    rows = [
        ("time [s]",
         f"{result.common_time_s:.6f}",
         f"{result.common_time_s:.6f}",
         "0.0"),
        ("range [km]",
         _fmt_km(result.qian_state.range_m),
         _fmt_km(result.sanger_state.range_m),
         _fmt_km(result.delta_range_m)),
        ("altitude [km]",
         _fmt_km(result.qian_state.altitude_m),
         _fmt_km(result.sanger_state.altitude_m),
         _fmt_km(result.delta_altitude_m)),
        ("velocity [m/s]",
         f"{result.qian_state.velocity_mps:.3f}",
         f"{result.sanger_state.velocity_mps:.3f}",
         f"{result.delta_velocity_mps:.3f}"),
        ("specific energy [MJ/kg]",
         f"{result.qian_state.specific_mechanical_energy_jpkg / 1e6:.6f}",
         f"{result.sanger_state.specific_mechanical_energy_jpkg / 1e6:.6f}",
         f"{result.delta_specific_energy_jpkg / 1e6:.6f}"),
        ("energy loss [MJ/kg]",
         f"{result.qian_energy_loss_jpkg / 1e6:.6f}",
         f"{result.sanger_energy_loss_jpkg / 1e6:.6f}",
         f"{(result.qian_energy_loss_jpkg - result.sanger_energy_loss_jpkg) / 1e6:.6f}"),
        ("normalized mode",
         f"{result.qian_mode}", f"{result.sanger_mode}", ""),
        ("source mode",
         f"{result.qian_source_mode}", f"{result.sanger_source_mode}", ""),
    ]
    for label, q, s, d in rows:
        print(f"{label:<24}{q:>16}{s:>16}{d:>18}")


def _print_common_range(result) -> None:
    print("\n=== Common-Range Comparison (Protocol C) ===")
    print(f"R_common = {_fmt_km(result.common_range_m)} km "
          f"= min(R_Q_RTI, R_S_SRTI)")
    print(f"{'Metric':<28}{'Qian':>16}{'Sanger':>16}{'Difference':>18}")
    rows = [
        ("range [km]",
         _fmt_km(result.qian_state.range_m),
         _fmt_km(result.sanger_state.range_m),
         _fmt_km(result.common_range_m)),
        ("arrival time [s]",
         f"{result.qian_arrival_time_s:.6f}",
         f"{result.sanger_arrival_time_s:.6f}",
         f"{result.sanger_arrival_time_s - result.qian_arrival_time_s:.6f}"),
        ("altitude [km]",
         _fmt_km(result.qian_state.altitude_m),
         _fmt_km(result.sanger_state.altitude_m),
         _fmt_km(result.delta_altitude_m)),
        ("velocity [m/s]",
         f"{result.qian_state.velocity_mps:.3f}",
         f"{result.sanger_state.velocity_mps:.3f}",
         f"{result.delta_velocity_mps:.3f}"),
        ("specific energy [MJ/kg]",
         f"{result.qian_state.specific_mechanical_energy_jpkg / 1e6:.6f}",
         f"{result.sanger_state.specific_mechanical_energy_jpkg / 1e6:.6f}",
         f"{result.delta_specific_energy_jpkg / 1e6:.6f}"),
        ("energy loss [MJ/kg]",
         f"{result.qian_energy_loss_jpkg / 1e6:.6f}",
         f"{result.sanger_energy_loss_jpkg / 1e6:.6f}",
         f"{(result.qian_energy_loss_jpkg - result.sanger_energy_loss_jpkg) / 1e6:.6f}"),
        ("normalized mode",
         f"{result.qian_mode}", f"{result.sanger_mode}", ""),
        ("source mode",
         f"{result.qian_source_mode}", f"{result.sanger_source_mode}", ""),
    ]
    for label, q, s, d in rows:
        print(f"{label:<28}{q:>16}{s:>16}{d:>18}")
    # E0 §21: the time-saving convention is explicit and separate from
    # the ordinary Sanger - Qian difference.
    print(f"Arrival-time saving (Qian - Sanger) = "
          f"{result.time_saving_s:.6f} s "
          f"(positive: Sanger reaches the common range earlier)")


def main() -> int:
    print("E2 COMMON-CONDITION COMPARISON")
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
    print(f"Alignment: initial_state={alignment.initial_state_equal} "
          f"environment={alignment.environment_equal} "
          f"vehicle={alignment.vehicle_equal} K={alignment.K_equal} "
          f"solver={alignment.solver_equal}")

    # Terminal metadata only (no native-endpoint gain claim, E0 §15/§16).
    print(f"Qian  terminal: kind={qian.terminal_kind} "
          f"t={qian.terminal_time_s:.6f} s "
          f"R={_fmt_km(qian.range_at_time(qian.terminal_time_s))} km")
    print(f"Sanger terminal: kind={sanger.terminal_kind} "
          f"t={sanger.terminal_time_s:.6f} s "
          f"R={_fmt_km(sanger.range_at_time(sanger.terminal_time_s))} km")

    common_time = run_common_time_comparison(qian, sanger)
    common_range = run_common_range_comparison(qian, sanger)

    _print_common_time(common_time)
    _print_common_range(common_range)

    summary = {
        "schema_version": "e2-common-conditions-v1",
        "git_commit": _git_info()["git_commit"],
        "branch": _git_info()["branch"],
        "comparison_protocol": "E0",
        "qian": {
            "terminal_kind": qian.terminal_kind,
            "terminal_time": qian.terminal_time_s,
            "terminal_range": qian.range_at_time(qian.terminal_time_s),
        },
        "sanger": {
            "terminal_kind": sanger.terminal_kind,
            "terminal_time": sanger.terminal_time_s,
            "terminal_range": sanger.range_at_time(sanger.terminal_time_s),
        },
        "common_time": _common_time_dict(common_time),
        "common_range": _common_range_dict(common_range),
        "alignment": {
            "initial_state_equal": alignment.initial_state_equal,
            "environment_equal": alignment.environment_equal,
            "vehicle_equal": alignment.vehicle_equal,
            "K_equal": alignment.K_equal,
            "solver_equal": alignment.solver_equal,
        },
        "continuous_evaluation": {
            "dense_output": True,
            "sample_grid_used": False,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "common_time.json", "w", encoding="utf-8") as f:
        json.dump(_common_time_dict(common_time), f, indent=2)
    with open(OUT_DIR / "common_range.json", "w", encoding="utf-8") as f:
        json.dump(_common_range_dict(common_range), f, indent=2)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nArtifacts written to {OUT_DIR}")
    print("E2 RUNNER: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
