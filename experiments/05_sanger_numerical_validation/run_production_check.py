"""D6 production-configuration accuracy check.

Runs PRODUCTION_SOLVER_CONFIG (DOP853, rtol=1e-9, coupled atol,
max_step=20 s) and quantifies the error of every event, the SRTI state,
the max altitude, the research time and range against the high-precision
numerical reference (results/.../reference/ref_0_1.json).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    RESULTS_DIR,
    crossing_directions,
    event_errors,
    event_residuals,
    get_baseline_setup,
    run_case,
    topological_margins,
    topology_equal,
    topology_record,
    vac_invariant_drifts,
    write_json,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG  # noqa: E402
from hyptraj.simulation.sanger_trajectory import SRTI  # noqa: E402


def main() -> None:
    ref = json.load(open(
        RESULTS_DIR / "reference" / "ref_0_1.json", encoding="utf-8"))
    env, vehicle, initial, control = get_baseline_setup()

    traj, metrics, runtime = run_case(PRODUCTION_SOLVER_CONFIG)

    topo = topology_record(traj, metrics)
    ref_topo = ref["topology"]
    if traj.terminal_kind != SRTI:
        raise RuntimeError(
            f"Production run must reach SRTI; got {traj.terminal_kind}.")

    errors = event_errors(traj, ref["events"])

    srti_err = {
        "dt_s": abs(traj.terminal_time - ref["SRTI"]["time_s"]),
        "dh_m": abs(traj.terminal_state[0] - env.earth_radius
                    - ref["SRTI"]["altitude_m"]),
        "dv_mps": abs(traj.terminal_state[2]
                      - ref["SRTI"]["velocity_mps"]),
        "dR_m": abs(env.earth_radius * traj.terminal_state[1]
                    - ref["SRTI"]["range_m"]),
    }
    global_err = {
        "d_research_time_s": abs(metrics.research_flight_time_s
                                 - ref["global"]["research_time_s"]),
        "d_research_range_m": abs(metrics.research_range_m
                                  - ref["global"]["research_range_m"]),
        "d_max_altitude_m": abs(metrics.maximum_altitude_m
                                - ref["global"]["max_altitude_m"]),
    }

    check = {
        "solver": {
            "method": PRODUCTION_SOLVER_CONFIG.method,
            "rtol": PRODUCTION_SOLVER_CONFIG.rtol,
            "atol": [float(a) for a in PRODUCTION_SOLVER_CONFIG.atol],
            "max_step": PRODUCTION_SOLVER_CONFIG.max_step,
        },
        "topology": topo,
        "topology_equal_reference": topology_equal(topo, ref_topo),
        "event_errors": errors,
        "srti_errors": srti_err,
        "global_errors": global_err,
        "event_residuals": event_residuals(traj, env),
        "crossing_directions": crossing_directions(traj, env),
        "vacuum_invariants": vac_invariant_drifts(metrics),
        "margins": topological_margins(traj, metrics, env, vehicle,
                                       control),
        "nfev_total": sum(s.nfev for s in traj.segments),
        "runtime_s": runtime,
    }
    write_json(RESULTS_DIR / "production" / "production_check.json", check)

    print("===== D6 production configuration check =====")
    print(f"topology equal to reference : "
          f"{check['topology_equal_reference']}")
    print(f"skip_count = {topo['skip_count']} (reference "
          f"{ref_topo['skip_count']})")
    print("event errors (max over all events):")
    for k in ("max_dt_s", "max_dh_m", "max_dv_mps", "max_dR_m"):
        print(f"  {k:12s} = {errors[k]:.3e}")
    print("SRTI errors:")
    for k, v in srti_err.items():
        print(f"  {k:7s} = {v:.3e}")
    print("global errors:")
    for k, v in global_err.items():
        print(f"  {k:22s} = {v:.3e}")
    print(f"nfev = {check['nfev_total']}, runtime = {runtime:.2f} s")
    print(f"Results written to {RESULTS_DIR / 'production'}")


if __name__ == "__main__":
    main()
