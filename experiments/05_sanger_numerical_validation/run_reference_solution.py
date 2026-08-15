"""D6 reference solution and self-stability check.

Runs the high-precision numerical reference (DOP853, rtol=1e-12,
atol=[1e-7,1e-14,1e-10,1e-14], max_step=0.1 s) plus a max_step=0.05 s
re-run and compares ALL key events, global metrics, cycle metrics and
the hybrid topology.

The reference is a NUMERICAL reference, not an analytic solution.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    REFERENCE_0_05,
    REFERENCE_0_1,
    RESULTS_DIR,
    crossing_directions,
    event_residuals,
    f16,
    get_baseline_setup,
    run_case,
    topological_margins,
    topology_equal,
    topology_record,
    vac_invariant_drifts,
    write_json,
)
from hyptraj.simulation.sanger_trajectory import SRTI  # noqa: E402


def _serialize_events(traj, env):
    return [
        {
            "kind": e.kind,
            "time": e.time,
            "state": [f16(x) for x in e.state],
            "earth_radius": env.earth_radius,
        }
        for e in traj.events
    ]


def _serialize_result(traj, metrics, runtime, env, vehicle, control):
    return {
        "topology": topology_record(traj, metrics),
        "runtime_s": runtime,
        "nfev_total": sum(s.nfev for s in traj.segments),
        "SRTI": {
            "time_s": f16(traj.terminal_time),
            "altitude_m": f16(traj.terminal_state[0] - env.earth_radius),
            "range_m": f16(env.earth_radius * traj.terminal_state[1]),
            "velocity_mps": f16(traj.terminal_state[2]),
            "gamma_rad": f16(traj.terminal_state[3]),
        },
        "global": {
            "research_time_s": f16(metrics.research_flight_time_s),
            "research_range_m": f16(metrics.research_range_m),
            "max_altitude_m": f16(metrics.maximum_altitude_m),
            "max_altitude_time_s": f16(metrics.maximum_altitude_time_s),
        },
        "cycles": [
            {
                "atmospheric_duration_s": f16(c.atmospheric_duration_s),
                "vacuum_duration_s": f16(c.vacuum_duration_s),
                "atmospheric_range_m": f16(c.atmospheric_range_m),
                "vacuum_range_m": f16(c.vacuum_range_m),
                "pullout_altitude_m": f16(c.pullout_altitude_m),
                "apogee_altitude_m": f16(c.apogee_altitude_m),
            }
            for c in metrics.completed_cycles
        ],
        "events": _serialize_events(traj, env),
        "event_residuals": event_residuals(traj, env),
        "crossing_directions": crossing_directions(traj, env),
        "vacuum_invariants": vac_invariant_drifts(metrics),
        "margins": topological_margins(traj, metrics, env, vehicle,
                                       control),
    }


def _event_diffs(a_events, b_events, env):
    """Max absolute differences of the common event sequence."""
    by_kind_a: dict[str, list] = {}
    for e in a_events:
        by_kind_a.setdefault(e["kind"], []).append(e)
    max_dt = max_dh = max_dv = max_dR = max_dgam = 0.0
    for e in b_events:
        refs = by_kind_a.get(e["kind"])
        if not refs:
            continue
        ref = refs.pop(0)
        max_dt = max(max_dt, abs(e["time"] - ref["time"]))
        max_dh = max(max_dh, abs(e["state"][0] - ref["state"][0]))
        max_dv = max(max_dv, abs(e["state"][2] - ref["state"][2]))
        max_dR = max(
            max_dR, abs(e["state"][1] - ref["state"][1]) * env.earth_radius)
        max_dgam = max(max_dgam, abs(e["state"][3] - ref["state"][3]))
    return {
        "max_dt_s": max_dt,
        "max_dh_m": max_dh,
        "max_dv_mps": max_dv,
        "max_dR_m": max_dR,
        "max_dgamma_rad": max_dgam,
    }


def main() -> None:
    env, vehicle, initial, control = get_baseline_setup()

    traj_a, metrics_a, rt_a = run_case(REFERENCE_0_1)
    traj_b, metrics_b, rt_b = run_case(REFERENCE_0_05)

    topo_a = topology_record(traj_a, metrics_a)
    topo_b = topology_record(traj_b, metrics_b)

    if traj_a.terminal_kind != SRTI or traj_b.terminal_kind != SRTI:
        raise RuntimeError(
            "Reference must reach the SRTI: "
            f"{traj_a.terminal_kind} / {traj_b.terminal_kind}.")

    if not topology_equal(topo_b, topo_a):
        raise RuntimeError(
            "Reference topologies differ between max_step=0.1 and 0.05: "
            f"{topo_a} vs {topo_b}.")

    out_a = _serialize_result(traj_a, metrics_a, rt_a, env, vehicle, control)
    out_b = _serialize_result(traj_b, metrics_b, rt_b, env, vehicle, control)

    stability = {
        "topology_identical": True,
        "event_diffs": _event_diffs(out_a["events"], out_b["events"], env),
        "srti_diffs": {
            "dt_s": abs(out_a["SRTI"]["time_s"] - out_b["SRTI"]["time_s"]),
            "dh_m": abs(out_a["SRTI"]["altitude_m"]
                        - out_b["SRTI"]["altitude_m"]),
            "dv_mps": abs(out_a["SRTI"]["velocity_mps"]
                          - out_b["SRTI"]["velocity_mps"]),
            "dR_m": abs(out_a["SRTI"]["range_m"]
                        - out_b["SRTI"]["range_m"]),
        },
        "global_diffs": {
            "d_research_time_s": abs(
                out_a["global"]["research_time_s"]
                - out_b["global"]["research_time_s"]),
            "d_research_range_m": abs(
                out_a["global"]["research_range_m"]
                - out_b["global"]["research_range_m"]),
            "d_max_altitude_m": abs(
                out_a["global"]["max_altitude_m"]
                - out_b["global"]["max_altitude_m"]),
        },
        "cycle_diffs": {
            "max_atm_duration_s": max(
                abs(ca["atmospheric_duration_s"]
                    - cb["atmospheric_duration_s"])
                for ca, cb in zip(out_a["cycles"], out_b["cycles"])),
            "max_vac_duration_s": max(
                abs(ca["vacuum_duration_s"] - cb["vacuum_duration_s"])
                for ca, cb in zip(out_a["cycles"], out_b["cycles"])),
            "max_range_m": max(
                abs(ca["atmospheric_range_m"] - cb["atmospheric_range_m"])
                for ca, cb in zip(out_a["cycles"], out_b["cycles"])),
        },
    }

    write_json(RESULTS_DIR / "reference" / "ref_0_1.json", out_a)
    write_json(RESULTS_DIR / "reference" / "ref_0_05.json", out_b)
    write_json(RESULTS_DIR / "reference" / "self_stability.json", stability)

    print("===== D6 reference solution =====")
    print(f"max_step=0.1 : skip_count={topo_a['skip_count']} "
          f"terminal={topo_a['terminal_kind']} nfev="
          f"{out_a['nfev_total']} runtime={rt_a:.2f} s")
    print(f"max_step=0.05: skip_count={topo_b['skip_count']} "
          f"terminal={topo_b['terminal_kind']} nfev="
          f"{out_b['nfev_total']} runtime={rt_b:.2f} s")
    print(f"topology identical : {stability['topology_identical']}")
    print("event diffs (0.1 vs 0.05):")
    for k, v in stability["event_diffs"].items():
        print(f"  {k:14s} = {v:.3e}")
    print("SRTI diffs:")
    for k, v in stability["srti_diffs"].items():
        print(f"  {k:8s} = {v:.3e}")
    print(f"Results written to {RESULTS_DIR / 'reference'}")


if __name__ == "__main__":
    main()
