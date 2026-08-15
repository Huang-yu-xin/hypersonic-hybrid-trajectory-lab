"""D3 smoke: run one frozen-IC structural Sanger hybrid trajectory.

Prints the mode / event sequence, the terminal kind and the segment
count ONLY.  No skip metrics, no figures, no frozen baseline numbers.

    python experiments/04_sanger_hybrid/run_state_machine_smoke.py

All numerical values printed here are structural audit output and are
NOT frozen (D0 spec §19, §22).
"""

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
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

    print("===== Sanger hybrid state-machine smoke (structural only) =====")
    print(f"Mode sequence : {' -> '.join(s.mode for s in traj.segments)}")
    print(f"Segment count : {len(traj.segments)}")
    print(f"Terminal kind : {traj.terminal_kind}")
    print(f"Success       : {traj.success}")
    print(f"Message       : {traj.message}")
    print("Event sequence (audit only, NOT FROZEN):")
    for e in traj.events:
        h_km = (e.state[0] - env.earth_radius) / 1000.0
        tag = " [synthetic]" if e.is_synthetic else ""
        print(
            f"  {e.kind:24s} t={e.time:12.4f} s  h={h_km:9.3f} km"
            f"  gamma={e.state[3]:+.6f} rad{tag}"
        )


if __name__ == "__main__":
    main()
