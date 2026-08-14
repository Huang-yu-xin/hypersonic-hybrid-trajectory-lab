"""C3: max_step sensitivity around the selected DOP853 tolerance regime."""

import csv
from common import BASE_ATOL, RESULTS_ROOT, add_reference_errors, flatten, load_reference, run_case, write_json
from hyptraj.simulation.trajectory import SolverConfig

MAX_STEPS = [40.0, 30.0, 20.0, 15.0, 10.0, 7.5, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1]


def main() -> None:
    ref = load_reference()
    rows = []
    for max_step in MAX_STEPS:
        cfg = SolverConfig(
            method="DOP853",
            rtol=1e-9,
            atol=BASE_ATOL * 0.1,
            max_step=max_step,
            dense_output=True,
        )
        row = add_reference_errors(run_case(cfg), ref)
        rows.append(row)
        print(max_step, row["abs_error_rti_time_s"], row["abs_error_rti_range_m"], row["nfev"], row["wall_s"])

    out = RESULTS_ROOT / "max_step_sweep"
    write_json(out / "results.json", rows)
    flat = [flatten(r) for r in rows]
    fields = sorted({k for r in flat for k in r})
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(flat)


if __name__ == "__main__":
    main()
