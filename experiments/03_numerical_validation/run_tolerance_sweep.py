"""C2: tolerance convergence with fixed and proportionally-scaled vector atol."""

import csv
from common import BASE_ATOL, RESULTS_ROOT, add_reference_errors, flatten, load_reference, run_case, write_json
from hyptraj.simulation.trajectory import SolverConfig

METHODS = ["RK45", "DOP853", "Radau", "BDF"]
RTOLS = [1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10]


def main() -> None:
    ref = load_reference()
    rows = []
    for mode in ["fixed", "scaled"]:
        for method in METHODS:
            for rtol in RTOLS:
                atol = BASE_ATOL.copy() if mode == "fixed" else BASE_ATOL * (rtol / 1e-8)
                cfg = SolverConfig(method=method, rtol=rtol, atol=atol, max_step=10.0, dense_output=True)
                row = add_reference_errors(run_case(cfg), ref)
                row["atol_mode"] = mode
                row["atol_scale_vs_phase_b"] = 1.0 if mode == "fixed" else rtol / 1e-8
                rows.append(row)
                print(mode, method, rtol, row["abs_error_rti_time_s"], row["abs_error_rti_range_m"])

    out = RESULTS_ROOT / "tolerance_sweep"
    write_json(out / "results.json", rows)
    flat = [flatten(r) for r in rows]
    fields = sorted({k for r in flat for k in r})
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(flat)


if __name__ == "__main__":
    main()
