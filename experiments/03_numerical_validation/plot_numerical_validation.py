"""Generate the Phase C accuracy/convergence/cost figures."""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from common import RESULTS_ROOT

FIG = RESULTS_ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def load(name):
    return json.loads((RESULTS_ROOT / name / "results.json").read_text(encoding="utf-8"))


def save(name):
    plt.tight_layout(); plt.savefig(FIG / name, dpi=180); plt.close()


def main():
    solver = load("solver_comparison")
    tol = load("tolerance_sweep")
    step = load("max_step_sweep")

    # C1 solver accuracy
    plt.figure()
    plt.bar([r["method"] for r in solver], [r["abs_error_rti_range_m"] for r in solver])
    plt.yscale("log"); plt.ylabel("|ΔR_RTI| [m]"); plt.xlabel("solver")
    save("C1_solver_accuracy.png")

    # C2 tolerance convergence, scaled-atol branch
    plt.figure()
    for method in ["RK45", "DOP853", "Radau", "BDF"]:
        rr = [r for r in tol if r["method"] == method and r["atol_mode"] == "scaled"]
        rr.sort(key=lambda r: r["rtol"], reverse=True)
        plt.plot([-np.log10(r["rtol"]) for r in rr], [r["abs_error_rti_range_m"] for r in rr], marker="o", label=method)
    plt.yscale("log"); plt.xlabel("-log10(rtol)"); plt.ylabel("|ΔR_RTI| [m]"); plt.legend()
    save("C2_tolerance_convergence.png")

    # C3 event-time convergence
    rr = [r for r in tol if r["method"] == "DOP853" and r["atol_mode"] == "scaled"]
    rr.sort(key=lambda r: r["rtol"], reverse=True)
    plt.figure()
    x = [-np.log10(r["rtol"]) for r in rr]
    plt.plot(x, [r["abs_error_capture_time_s"] for r in rr], marker="o", label="capture")
    plt.plot(x, [r["abs_error_rti_time_s"] for r in rr], marker="o", label="RTI")
    plt.yscale("log"); plt.xlabel("-log10(rtol)"); plt.ylabel("event-time error [s]"); plt.legend()
    save("C3_event_time_convergence.png")

    # C4 max_step sensitivity
    rr = sorted(step, key=lambda r: r["max_step_s"])
    plt.figure()
    plt.plot([r["max_step_s"] for r in rr], [r["abs_error_rti_range_m"] for r in rr], marker="o")
    plt.yscale("log"); plt.xlabel("max_step [s]"); plt.ylabel("|ΔR_RTI| [m]")
    save("C4_max_step_sensitivity.png")

    # C5 accuracy/cost
    plt.figure()
    for r in solver:
        plt.scatter(r["wall_s"], r["abs_error_rti_range_m"], label=r["method"])
    plt.yscale("log"); plt.xlabel("wall time [s]"); plt.ylabel("|ΔR_RTI| [m]"); plt.legend()
    save("C5_accuracy_cost.png")


if __name__ == "__main__":
    main()
