"""C6: production-candidate timing benchmark (reproducible final selection).

Repeated wall-time measurements for the four shortlisted production
solver configurations (P8-20 / P9-20 / P10-20 / P9-10).  Every run goes
through the frozen Phase B physics via ``common.run_case`` (no duplicated
dynamics, no hard-coded results); the errors are evaluated against the
C1 numerical reference.

Protocol: 2 untimed warmups, then 15 timed repeats per candidate.
Median / mean / std of the wall time are reported because wall time is
noisy; nfev / njev / nlu are deterministic per configuration.

Writes:
    results/numerical_validation/final_candidates/final_candidates.json
    results/numerical_validation/final_candidates/final_candidates.csv

Run from the project root (after run_reference_solution.py):

    python experiments/03_numerical_validation/run_final_candidates.py
"""

import csv
import statistics

import numpy as np

from common import (
    BASE_ATOL,
    RESULTS_ROOT,
    add_reference_errors,
    flatten,
    load_reference,
    run_case,
    write_json,
)
from hyptraj.simulation.trajectory import SolverConfig

CANDIDATES = [
    # (name, method, rtol, atol, max_step)
    ("P8-20", "DOP853", 1e-8, np.array([1e-3, 1e-10, 1e-6, 1e-10]), 20.0),
    ("P9-20", "DOP853", 1e-9, np.array([1e-4, 1e-11, 1e-7, 1e-11]), 20.0),
    ("P10-20", "DOP853", 1e-10, np.array([1e-5, 1e-12, 1e-8, 1e-12]), 20.0),
    ("P9-10", "DOP853", 1e-9, np.array([1e-4, 1e-11, 1e-7, 1e-11]), 10.0),
]
WARMUPS = 2
REPEATS = 15

OUTPUT_FIELDS = [
    "candidate",
    "method",
    "rtol",
    "atol",
    "max_step",
    "median_runtime_s",
    "mean_runtime_s",
    "std_runtime_s",
    "nfev",
    "njev",
    "nlu",
    "abs_error_capture_time_s",
    "abs_error_rti_time_s",
    "abs_error_rti_range_m",
    "abs_error_rti_velocity_mps",
    "hybrid_consistent",
]


def main() -> None:
    reference = load_reference()
    print("===== C6 production-candidate benchmark "
          f"({WARMUPS} warmups, {REPEATS} timed repeats each) =====")

    rows = []
    for name, method, rtol, atol, max_step in CANDIDATES:
        cfg = SolverConfig(
            method=method,
            rtol=rtol,
            atol=atol.copy(),
            max_step=max_step,
            dense_output=True,
        )
        for _ in range(WARMUPS):
            run_case(cfg)  # untimed warmup

        timed = []
        last = None
        for _ in range(REPEATS):
            last = run_case(cfg)
            timed.append(last["wall_s"])

        row = {
            "candidate": name,
            "method": method,
            "rtol": float(rtol),
            "atol": [float(x) for x in atol],
            "max_step": float(max_step),
            "median_runtime_s": statistics.median(timed),
            "mean_runtime_s": statistics.mean(timed),
            "std_runtime_s": statistics.stdev(timed),
            "nfev": last["nfev"],
            "njev": last["njev"],
            "nlu": last["nlu"],
            "hybrid_consistent": bool(last["hybrid_consistency_ok"]),
        }
        row.update(add_reference_errors(last, reference))
        rows.append(row)

        print(
            "%-7s median=%.4f s  mean=%.4f s  std=%.4f s  nfev=%d  "
            "dR_rti=%.4f m  dRti=%.3e s  hybrid=%s"
            % (
                name,
                row["median_runtime_s"],
                row["mean_runtime_s"],
                row["std_runtime_s"],
                row["nfev"],
                row["abs_error_rti_range_m"],
                row["abs_error_rti_time_s"],
                row["hybrid_consistent"],
            )
        )

    out = RESULTS_ROOT / "final_candidates"
    write_json(out / "final_candidates.json", {"rows": rows})
    flat = [{k: r[k] for k in OUTPUT_FIELDS} for r in rows]
    out.mkdir(parents=True, exist_ok=True)
    with (out / "final_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        w.writeheader()
        w.writerows(flat)

    print(f"\nArtifacts written to {out}")


if __name__ == "__main__":
    main()
