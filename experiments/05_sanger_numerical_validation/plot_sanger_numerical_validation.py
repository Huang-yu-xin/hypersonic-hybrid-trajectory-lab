"""D6 figures: event convergence and hybrid-topology stability.

    D6_event_convergence.png     |Δt_SRTI| and |ΔR_SRTI| vs -log10(rtol)
    D7_max_step_sensitivity.png  |ΔR_SRTI| vs max_step (log-y)
    D8_topology_stability.png    case vs skip_count with topology match
    D9_accuracy_cost.png         |ΔR_SRTI| vs nfev (production marked)

Reads only the aggregated summary (results/.../numerical_validation).
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RESULTS_DIR  # noqa: E402

FIG_DIR = RESULTS_DIR / "figures"
DPI = 300


def main() -> None:
    s = json.load(open(RESULTS_DIR / "summary.json", encoding="utf-8"))
    tol = s["tolerance_sweep"]
    ms = s["max_step_sweep"]
    prod = s["production"]
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # ---- D6: event convergence vs rtol --------------------------------
    import math
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    rt = [round(abs(math.log10(r["rtol"]))) for r in tol]
    dt = [r["errors"]["srti_dt_s"] for r in tol]
    dR = [r["errors"]["srti_dR_m"] for r in tol]
    ax.plot(rt, dt, "o-", color="#1f77b4", label=r"$|\Delta t_{\mathrm{SRTI}}|$ [s]")
    ax.set_xlabel(r"$-\log_{10}(\mathrm{rtol})$")
    ax.set_ylabel(r"$|\Delta t_{\mathrm{SRTI}}|$ [s]", color="#1f77b4")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax2 = ax.twinx()
    ax2.plot(rt, dR, "s--", color="#d62728",
             label=r"$|\Delta R_{\mathrm{SRTI}}|$ [m]")
    ax2.set_ylabel(r"$|\Delta R_{\mathrm{SRTI}}|$ [m]", color="#d62728")
    ax2.set_yscale("log")
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], fontsize=8,
              loc="upper right")
    ax.set_title("D6 — SRTI event convergence vs rtol")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D6_event_convergence.png", dpi=DPI)
    plt.close(fig)

    # ---- D7: max_step sensitivity --------------------------------------
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    xs = [r["max_step_s"] for r in ms]
    dR = [r["errors"]["srti_dR_m"] for r in ms]
    ax.plot(xs, dR, "o-", color="#2ca02c")
    ax.set_xlabel("max_step [s]")
    ax.set_ylabel(r"$|\Delta R_{\mathrm{SRTI}}|$ [m]")
    ax.set_yscale("log")
    ax.set_title("D7 — max_step sensitivity (rtol = 1e-9)")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D7_max_step_sensitivity.png", dpi=DPI)
    plt.close(fig)

    # ---- D8: hybrid topology stability ----------------------------------
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    cases = [f"rtol={r['rtol']:.0e}" for r in tol]
    cases += [f"ms={r['max_step_s']:g}" for r in ms]
    counts = [r["topology"]["skip_count"] for r in tol]
    counts += [r["topology"]["skip_count"] for r in ms]
    match = [r["topology_equal_reference"] for r in tol]
    match += [r["topology_equal_reference"] for r in ms]
    colors = ["#2ca02c" if m else "#d62728" for m in match]
    ax.bar(range(len(cases)), counts, color=colors, edgecolor="black",
           linewidth=0.5)
    ax.set_xticks(range(len(cases)))
    ax.set_xticklabels(cases, rotation=90, fontsize=7)
    ax.set_ylabel("skip_count")
    ax.set_ylim(0, 3)
    ax.set_title("D8 — Hybrid topology stability (green = matches reference)")
    ax.axhline(2.0, color="gray", ls="--", lw=0.8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D8_topology_stability.png", dpi=DPI)
    plt.close(fig)

    # ---- D9: accuracy / cost --------------------------------------------
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    xs = [r["nfev_total"] for r in tol] + [r["nfev_total"] for r in ms]
    dR = [r["errors"]["srti_dR_m"] for r in tol] + [
        r["errors"]["srti_dR_m"] for r in ms]
    ax.plot(xs, dR, "o", color="#7f7f7f", ms=5, label="sweep cases")
    ax.plot(prod["nfev_total"], prod["srti_errors"]["dR_m"], "r*", ms=16,
            label="production (1e-9, max_step=20)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("nfev (total)")
    ax.set_ylabel(r"$|\Delta R_{\mathrm{SRTI}}|$ [m]")
    ax.set_title("D9 — Accuracy vs cost")
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D9_accuracy_cost.png", dpi=DPI)
    plt.close(fig)

    print("Figures written (300 dpi PNG):")
    for name in (
        "D6_event_convergence.png", "D7_max_step_sensitivity.png",
        "D8_topology_stability.png", "D9_accuracy_cost.png",
    ):
        path = FIG_DIR / name
        img = plt.imread(path)
        print(
            f"  {name:28s} {img.shape[1]}x{img.shape[0]} px  "
            f"{path.stat().st_size / 1024.0:.1f} KiB"
        )


if __name__ == "__main__":
    main()
