"""C4/C5/C6: aggregate consistency, accuracy/cost and freeze production config."""

import csv
import json
from pathlib import Path

from common import PRODUCTION_CONFIG, RESULTS_ROOT, flatten, load_reference, run_case, write_json


def load_rows(name):
    p = RESULTS_ROOT / name / "results.json"
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    reference = load_reference()
    solver_rows = load_rows("solver_comparison")
    tol_rows = load_rows("tolerance_sweep")
    step_rows = load_rows("max_step_sweep")
    all_rows = solver_rows + tol_rows + step_rows

    hybrid_ok = all(bool(r.get("hybrid_consistency_ok", False)) for r in all_rows)
    production = run_case(PRODUCTION_CONFIG)

    # C6 production-candidate benchmark (companion artifact): if the
    # benchmark has been run, carry its rows into summary.json as an additive
    # key; the canonical summary structure is left untouched otherwise.
    fc_path = RESULTS_ROOT / "final_candidates" / "final_candidates.json"
    final_candidates = (
        json.loads(fc_path.read_text(encoding="utf-8"))["rows"]
        if fc_path.exists()
        else None
    )

    summary = {
        "reference": reference,
        "hybrid_consistency_all_sweeps": hybrid_ok,
        "sweep_case_count": len(all_rows),
        "production_configuration": {
            "method": PRODUCTION_CONFIG.method,
            "rtol": PRODUCTION_CONFIG.rtol,
            "atol": [float(x) for x in PRODUCTION_CONFIG.atol],
            "max_step_s": PRODUCTION_CONFIG.max_step,
            "dense_output": PRODUCTION_CONFIG.dense_output,
        },
        "production_result": production,
        "final_candidates": final_candidates,
        "acceptance": {
            "all_four_solvers_compared": len({r["method"] for r in solver_rows}) == 4,
            "reference_exists": True,
            "tolerance_sweep_complete": len(tol_rows) >= 4 * 6,
            "max_step_sweep_complete": len(step_rows) >= 6,
            "hybrid_consistency": hybrid_ok,
        },
    }
    write_json(RESULTS_ROOT / "summary.json", summary)

    flat = [flatten(r) for r in all_rows]
    fields = sorted({k for r in flat for k in r})
    with (RESULTS_ROOT / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(flat)

    print("===== Phase C Summary =====")
    print("cases:", len(all_rows))
    print("hybrid consistency:", hybrid_ok)
    print("production:", summary["production_configuration"])
    if final_candidates:
        print("final candidates included:",
              [r["candidate"] for r in final_candidates])


if __name__ == "__main__":
    main()
