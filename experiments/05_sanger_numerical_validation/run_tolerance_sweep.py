"""D6 DOP853 tolerance sweep (coupled component-scaled atol).

rtol in {1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11} (+ 1e-5 stress case),
atol = rtol * [1e5, 1e-2, 1e2, 1e-2] (Phase C coupling), max_step = 20 s.

Each case records the hybrid topology and the error of every key event,
the SRTI state and the research range vs the high-precision reference.
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
    scaled_atol,
    topology_equal,
    topology_record,
    vac_invariant_drifts,
    write_json,
)
from hyptraj.simulation.sanger_trajectory import SRTI  # noqa: E402
from hyptraj.simulation.trajectory import SolverConfig  # noqa: E402

RTOLS = [1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11]
MAX_STEP = 20.0


def _solver(rtol: float) -> SolverConfig:
    return SolverConfig(
        method="DOP853",
        rtol=rtol,
        atol=scaled_atol(rtol),
        max_step=MAX_STEP,
        dense_output=True,
    )


def main() -> None:
    ref = json.load(open(
        RESULTS_DIR / "reference" / "ref_0_1.json", encoding="utf-8"))
    env, vehicle, initial, control = get_baseline_setup()

    cases = []
    for rtol in RTOLS:
        traj, metrics, runtime = run_case(_solver(rtol))
        topo = topology_record(traj, metrics)
        errors = event_errors(traj, ref["events"])
        srti = {
            "dt_s": abs(traj.terminal_time - ref["SRTI"]["time_s"]),
            "dh_m": abs(traj.terminal_state[0] - env.earth_radius
                        - ref["SRTI"]["altitude_m"]),
            "dv_mps": abs(traj.terminal_state[2]
                          - ref["SRTI"]["velocity_mps"]),
            "dR_m": abs(env.earth_radius * traj.terminal_state[1]
                        - ref["SRTI"]["range_m"]),
        }
        case = {
            "rtol": rtol,
            "atol": [float(a) for a in scaled_atol(rtol)],
            "topology": topo,
            "topology_equal_reference": topology_equal(topo, ref["topology"]),
            "errors": {
                "max_dt_s": errors["max_dt_s"],
                "max_dh_m": errors["max_dh_m"],
                "max_dv_mps": errors["max_dv_mps"],
                "max_dR_m": errors["max_dR_m"],
                "srti_dt_s": srti["dt_s"],
                "srti_dh_m": srti["dh_m"],
                "srti_dv_mps": srti["dv_mps"],
                "srti_dR_m": srti["dR_m"],
                "d_research_range_m": abs(
                    metrics.research_range_m
                    - ref["global"]["research_range_m"]),
                "d_max_altitude_m": abs(
                    metrics.maximum_altitude_m
                    - ref["global"]["max_altitude_m"]),
            },
            "event_residuals": event_residuals(traj, env),
            "crossing_directions": crossing_directions(traj, env),
            "vacuum_invariants": vac_invariant_drifts(metrics),
            "nfev_total": sum(s.nfev for s in traj.segments),
            "runtime_s": runtime,
        }
        cases.append(case)
        write_json(
            RESULTS_DIR / "tolerance_sweep" / "cases"
            / f"rtol_{rtol:.0e}.json", case)
        print(
            f"rtol={rtol:.0e}  skip={topo['skip_count']}  "
            f"topo_eq={case['topology_equal_reference']}  "
            f"dR_srti={srti['dR_m']:.3e} m  nfev="
            f"{case['nfev_total']}  t={runtime:.2f} s")

    write_json(RESULTS_DIR / "tolerance_sweep" / "sweep.json",
               {"cases": cases})
    print(f"Results written to {RESULTS_DIR / 'tolerance_sweep'}")


if __name__ == "__main__":
    main()
