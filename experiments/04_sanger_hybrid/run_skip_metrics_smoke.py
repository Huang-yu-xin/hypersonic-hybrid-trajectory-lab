"""D4 smoke: skip-cycle metrics / trajectory diagnostics.

Integrates one frozen-IC Sanger hybrid trajectory (D3) and prints the
D4 derived metrics as a compact text table.

    python experiments/04_sanger_hybrid/run_skip_metrics_smoke.py

D4 SMOKE -- VALUES NOT FROZEN.  Canonical artifacts (trajectory.csv /
events.csv / skip_cycles.csv / summary.json) are produced by D5 only.
"""

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import integrate_sanger_hybrid


def main() -> None:
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)

    traj = integrate_sanger_hybrid(env, vehicle, initial, control)
    m = analyze_sanger_trajectory(traj, env)

    print("D4 SMOKE -- VALUES NOT FROZEN")
    print()
    print("Per-cycle table:")
    print(
        f"{'Cycle':>5} | {'Entry t':>10} {'h_min':>8} | "
        f"{'Exit t':>10} | {'Apogee h_max':>12} | "
        f"{'ATM dt':>9} {'VAC dt':>9} | {'dR_atm km':>10} "
        f"{'dR_vac km':>10}"
    )
    for c in m.completed_cycles:
        print(
            f"{c.index:>5} | {c.entry_time:>10.2f} "
            f"{c.pullout_altitude_m / 1000.0:>8.3f} | "
            f"{c.exit_time:>10.2f} | "
            f"{c.apogee_altitude_m / 1000.0:>12.3f} | "
            f"{c.atmospheric_duration_s:>9.2f} "
            f"{c.vacuum_duration_s:>9.2f} | "
            f"{c.atmospheric_range_m / 1000.0:>10.2f} "
            f"{c.vacuum_range_m / 1000.0:>10.2f}"
        )

    print()
    print("Global (NOT FROZEN):")
    print(f"  skip_count              = {m.skip_count}")
    print(f"  ATM segments            = {m.atm_segment_count}")
    print(f"  VAC segments            = {m.vac_segment_count}")
    print(f"  total ATM time          = {m.total_atmospheric_time_s:.2f} s")
    print(f"  total VAC time          = {m.total_vacuum_time_s:.2f} s")
    print(f"  research flight time    = {m.research_flight_time_s:.2f} s")
    print(f"  research range          = {m.research_range_m / 1000.0:.2f} km")
    print(f"  maximum altitude        = {m.maximum_altitude_m / 1000.0:.3f} km")
    print(
        f"  SRTI time / h / v        = {m.terminal_time_s:.2f} s / "
        f"{m.terminal_altitude_m / 1000.0:.3f} km / "
        f"{m.terminal_velocity_mps:.2f} m/s"
    )
    p = m.terminal_incomplete_pass
    if p is not None:
        print("Terminal incomplete pass (NOT FROZEN):")
        print(
            f"  entry / pullout / SRTI   = {p.entry_time:.2f} / "
            f"{p.pullout_time:.2f} / {p.srti_time:.2f} s"
        )
        print(
            f"  duration / range / dE    = {p.atmospheric_duration_s:.2f} s / "
            f"{p.range_increment_m / 1000.0:.2f} km / "
            f"{p.mechanical_energy_loss_jpkg:.1f} J/kg"
        )

    print()
    print("Energy diagnostics (NOT FROZEN):")
    for c in m.completed_cycles:
        print(
            f"  cycle {c.index}: ATM loss = {c.atmospheric_energy_loss_jpkg:.1f} J/kg"
            f", VAC rel E drift = {c.vacuum_energy_relative_drift:.2e}"
            f", VAC rel H drift = {c.vacuum_angular_momentum_relative_drift:.2e}"
        )


if __name__ == "__main__":
    main()
