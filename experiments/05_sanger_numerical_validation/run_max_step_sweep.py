"""D6 max_step sweep (fixed production tolerance coupling).

rtol = 1e-9, atol = [1e-4, 1e-11, 1e-7, 1e-11], max_step swept over
{40, 30, 20, 15, 10, 5, 2, 1, 0.5} (plus 0.2 / 0.1 when affordable).

Records per case: topology, key-event and SRTI errors vs the
high-precision reference, nfev and runtime.  The main failure mode under
test is an event-order swap (e.g. X1 vs the SRTI candidate), which
would change the hybrid topology.
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
    topology_equal,
    topology_record,
    vac_invariant_drifts,
    write_json,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG  # noqa: E402
from hyptraj.simulation.trajectory import SolverConfig  # noqa: E402

MAX_STEPS = [40.0, 30.0, 20.0, 15.0, 10.0, 5.0, 2.0, 1.0, 0.5]
EXTRA_MAX_STEPS = [0.2, 0.1]  # added when the 0.5 s case is affordable


def _solver(max_step: float) -> SolverConfig:
    return SolverConfig(
        method=PRODUCTION_SOLVER_CONFIG.method,
        rtol=PRODUCTION_SOLVER_CONFIG.rtol,
        atol=PRODUCTION_SOLVER_CONFIG.atol.copy(),
        max_step=max_step,
        dense_output=PRODUCTION_SOLVER_CONFIG.dense_output,
    )


def _run_one(max_step: float, ref, env) -> dict:
    traj, metrics, runtime = run_case(_solver(max_step))
    topo = topology_record(traj, metrics)
    errors = event_errors(traj, ref["events"])
    case = {
        "max_step_s": max_step,
        "topology": topo,
        "topology_equal_reference": topology_equal(topo, ref["topology"]),
        "errors": {
            "max_dt_s": errors["max_dt_s"],
            "max_dh_m": errors["max_dh_m"],
            "max_dv_mps": errors["max_dv_mps"],
            "max_dR_m": errors["max_dR_m"],
            "srti_dt_s": abs(traj.terminal_time - ref["SRTI"]["time_s"]),
            "srti_dh_m": abs(
                traj.terminal_state[0] - env.earth_radius
                - ref["SRTI"]["altitude_m"]),
            "srti_dv_mps": abs(
                traj.terminal_state[2] - ref["SRTI"]["velocity_mps"]),
            "srti_dR_m": abs(
                env.earth_radius * traj.terminal_state[1]
                - ref["SRTI"]["range_m"]),
            "d_research_range_m": abs(
                metrics.research_range_m
                - ref["global"]["research_range_m"]),
        },
        "event_residuals": event_residuals(traj, env),
        "crossing_directions": crossing_directions(traj, env),
        "vacuum_invariants": vac_invariant_drifts(metrics),
        "nfev_total": sum(s.nfev for s in traj.segments),
        "runtime_s": runtime,
    }
    write_json(
        RESULTS_DIR / "max_step_sweep" / "cases"
        / f"max_step_{max_step:g}.json", case)
    print(
        f"max_step={max_step:5g}  skip={topo['skip_count']}  "
        f"topo_eq={case['topology_equal_reference']}  "
        f"dR_srti={case['errors']['srti_dR_m']:.3e} m  nfev="
        f"{case['nfev_total']}  t={runtime:.2f} s")
    return case


def main() -> None:
    ref = json.load(open(
        RESULTS_DIR / "reference" / "ref_0_1.json", encoding="utf-8"))
    env, vehicle, initial, control = get_baseline_setup()

    cases = []
    extra = False
    for max_step in MAX_STEPS:
        case = _run_one(max_step, ref, env)
        cases.append(case)
        if max_step == 0.5 and case["runtime_s"] < 10.0:
            extra = True

    if extra:
        for max_step in EXTRA_MAX_STEPS:
            cases.append(_run_one(max_step, ref, env))

    write_json(RESULTS_DIR / "max_step_sweep" / "sweep.json",
               {"cases": cases})
    print(f"Results written to {RESULTS_DIR / 'max_step_sweep'}")


if __name__ == "__main__":
    main()
