"""C1: RK45 / DOP853 / Radau / BDF at a common numerical configuration."""

import csv
from common import BASE_ATOL, RESULTS_ROOT, add_reference_errors, flatten, load_reference, run_case, write_json
from hyptraj.simulation.trajectory import SolverConfig

METHODS = ["RK45", "DOP853", "Radau", "BDF"]


def main() -> None:
    ref = load_reference()
    rows = []
    for method in METHODS:
        cfg = SolverConfig(method=method, rtol=1e-8, atol=BASE_ATOL.copy(), max_step=10.0, dense_output=True)
        row = add_reference_errors(run_case(cfg), ref)
        rows.append(row)
        print(method, row["abs_error_rti_time_s"], row["abs_error_rti_range_m"], row["nfev"], row["wall_s"])

    out = RESULTS_ROOT / "solver_comparison"
    write_json(out / "results.json", rows)
    flat = [flatten(r) for r in rows]
    fields = sorted({k for r in flat for k in r})
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(flat)


if __name__ == "__main__":
    main()
