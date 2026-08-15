"""E1 alignment smoke -- structural audit of the comparison infrastructure.

Prints ONLY structural adapter information (terminal metadata, range
monotonicity, exposure structure, alignment flags).  No performance
deltas, no time savings, no range gains, no winner claims are computed
or printed -- those belong to E2/E3 under the E0 protocol.

Run:

    python experiments/06_qian_sanger_comparison/run_alignment_smoke.py
"""

import sys

from hyptraj.analysis import (
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    verify_comparison_alignment,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)


def main() -> int:
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

    q_mono = qian.is_range_monotone()
    s_mono = sanger.is_range_monotone()

    print("E1 ALIGNMENT SMOKE -- NO PERFORMANCE CLAIMS")
    print("=" * 60)
    print("Qian:")
    print(f"  terminal_kind          = {qian.terminal_kind}")
    print(f"  terminal_time          = {qian.terminal_time_s:.6f} s")
    print(f"  terminal_range         = {qian.range_at_time(qian.terminal_time_s) / 1000.0:.6f} km")
    print(f"  total_ATM_exposure     = {qian.total_atmospheric_exposure():.6f} s")
    print(f"  range_monotone         = {q_mono.is_strictly_monotone}")
    print(f"  minimum_dRdt           = {q_mono.minimum_drange_dt:.6e} m/s")
    print("Sanger:")
    print(f"  terminal_kind          = {sanger.terminal_kind}")
    print(f"  terminal_time          = {sanger.terminal_time_s:.6f} s")
    print(f"  terminal_range         = {sanger.range_at_time(sanger.terminal_time_s) / 1000.0:.6f} km")
    print(f"  total_ATM_exposure     = {sanger.total_atmospheric_exposure():.6f} s")
    print(f"  range_monotone         = {s_mono.is_strictly_monotone}")
    print(f"  minimum_dRdt           = {s_mono.minimum_drange_dt:.6e} m/s")
    print("Alignment:")
    alignment = verify_comparison_alignment(qian, sanger)
    print(f"  initial_state_equal    = {alignment.initial_state_equal}")
    print(f"  environment_equal      = {alignment.environment_equal}")
    print(f"  vehicle_equal          = {alignment.vehicle_equal}")
    print(f"  K_equal                = {alignment.K_equal}")
    print(f"  solver_equal           = {alignment.solver_equal}")
    print("Dense access:")
    print(f"  Qian stage count       = {len(qian.dense_segments)}")
    print(f"  Sanger segment count   = {len(sanger.dense_segments)}")
    print("Exposure structure:")
    print(f"  Qian ATM intervals     = {len(qian.atmospheric_intervals)}")
    print(f"  Sanger ATM intervals   = {len(sanger.atmospheric_intervals)}")
    sanger_vac_plateaus = sum(
        1 for seg in sanger.dense_segments if seg.normalized_mode == "VAC"
    )
    print(f"  Sanger VAC plateaus    = {sanger_vac_plateaus}")
    print("=" * 60)

    ok = (
        alignment.all_equal
        and q_mono.is_strictly_monotone
        and s_mono.is_strictly_monotone
        and qian.terminal_kind == "RTI"
        and sanger.terminal_kind == "SRTI"
    )
    print(f"E1 ALIGNMENT SMOKE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
