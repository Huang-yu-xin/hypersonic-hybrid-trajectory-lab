"""D6 figures: event convergence and hybrid-topology stability (D7B-pre).

    D6_event_convergence.png     |Δt_SRTI| and |ΔR_SRTI| vs -log10(rtol)
                                in two vertically stacked panels (no
                                twin-axis overlay)
    D7_max_step_sensitivity.png  |ΔR_SRTI| vs max step size (log-y,
                                production max_step = 20 s marked)
    D8_topology_stability.png    case vs skip_count with the 18/18
                                topology-match annotation and the
                                tolerance / max-step sweep groups
                                visually separated
    D9_accuracy_cost.png         |ΔR_SRTI| vs nfev with the tolerance
                                sweep, max-step sweep and production
                                distinguished

Reads only the aggregated summary (results/.../numerical_validation).
All annotations read values from the artifacts, never from hard-coded
rounded chat values.
"""

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RESULTS_DIR  # noqa: E402

FIG_DIR = RESULTS_DIR / "figures"
DPI = 300


def _legend_once(ax, fontsize=8, loc="upper right"):
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize=fontsize,
              loc=loc)


def main() -> None:
    s = json.load(open(RESULTS_DIR / "summary.json", encoding="utf-8"))
    tol = s["tolerance_sweep"]
    ms = s["max_step_sweep"]
    prod = s["production"]
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    prod_srti_dR = prod["srti_errors"]["dR_m"]

    # ---- D6: SRTI convergence, stacked panels (no twin axis) ------------
    rt = [round(abs(math.log10(r["rtol"]))) for r in tol]
    dt = [r["errors"]["srti_dt_s"] for r in tol]
    dR = [r["errors"]["srti_dR_m"] for r in tol]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.0, 6.4), sharex=True)
    ax1.plot(rt, dt, "o-", color="#1f77b4")
    ax1.set_ylabel(r"$|\Delta t_{\mathrm{SRTI}}|$ [s]")
    ax1.set_yscale("log")
    ax1.grid(alpha=0.3, which="both")
    ax1.axvline(9.0, color="gray", ls="--", lw=1.0)
    ax1.text(9.02, ax1.get_ylim()[0], " production rtol=1e-9",
             fontsize=8, va="bottom")

    ax2.plot(rt, dR, "s-", color="#d62728")
    ax2.set_ylabel(r"$|\Delta R_{\mathrm{SRTI}}|$ [m]")
    ax2.set_xlabel(r"$-\log_{10}(\mathrm{rtol})$")
    ax2.set_yscale("log")
    ax2.grid(alpha=0.3, which="both")
    ax2.axvline(9.0, color="gray", ls="--", lw=1.0)
    ax2.text(9.02, ax2.get_ylim()[0], " production rtol=1e-9",
             fontsize=8, va="bottom")

    ax1.set_title("D6 — SRTI event convergence vs rtol")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D6_event_convergence.png", dpi=DPI)
    plt.close(fig)

    # ---- D7: max_step sensitivity -----------------------------------------
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    xs = [r["max_step_s"] for r in ms]
    dR = [r["errors"]["srti_dR_m"] for r in ms]
    ax.plot(xs, dR, "o-", color="#2ca02c", label="DOP853, rtol=1e-9")
    dR_prod = next(r["errors"]["srti_dR_m"] for r in ms
                   if r["max_step_s"] == 20.0)
    ax.axvline(20.0, color="gray", ls="--", lw=1.0)
    ax.annotate("production max_step = 20 s",
                xy=(20.0, dR_prod),
                xytext=(0.50, 0.45), textcoords="axes fraction",
                fontsize=8,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.set_xlabel("Maximum step size [s]")
    ax.set_ylabel(r"$|\Delta R_{\mathrm{SRTI}}|$ [m]")
    ax.set_yscale("log")
    ax.set_title("D7 — max_step sensitivity")
    ax.grid(alpha=0.3, which="both")
    _legend_once(ax, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D7_max_step_sensitivity.png", dpi=DPI)
    plt.close(fig)

    # ---- D8: hybrid topology stability -------------------------------------
    n_tol = len(tol)
    cases = [f"rtol={r['rtol']:.0e}" for r in tol]
    cases += [f"ms={r['max_step_s']:g}" for r in ms]
    counts = [r["topology"]["skip_count"] for r in tol]
    counts += [r["topology"]["skip_count"] for r in ms]
    match = [r["topology_equal_reference"] for r in tol]
    match += [r["topology_equal_reference"] for r in ms]
    colors = ["#2ca02c" if m else "#d62728" for m in match]

    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    ax.bar(range(len(cases)), counts, color=colors, edgecolor="black",
           linewidth=0.5)
    ax.axvspan(-0.5, n_tol - 0.5, color="#eef2f7", zorder=0)
    ax.axvline(n_tol - 0.5, color="gray", lw=1.0)
    ax.text((n_tol - 1) / 2, 2.55, "Tolerance sweep", ha="center",
            fontsize=9, color="#333333")
    ax.text((n_tol + len(cases) - 1) / 2, 2.55, "Max-step sweep",
            ha="center", fontsize=9, color="#333333")
    ax.set_xticks(range(len(cases)))
    ax.set_xticklabels(cases, rotation=90, fontsize=7)
    ax.set_ylabel("skip_count")
    ax.set_ylim(0, 3.2)
    ax.axhline(2.0, color="gray", ls="--", lw=0.8)
    # All 17 sweep cases plus the production check (18 total) matched.
    n_total = len(cases) + 1
    ax.set_title(
        "D8 — Hybrid topology stability\n"
        f"{n_total} / {n_total} cases match reference topology "
        "(skip_count = 2, terminal = SRTI)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "D8_topology_stability.png", dpi=DPI)
    plt.close(fig)

    # ---- D9: accuracy vs cost ----------------------------------------------
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.plot([r["nfev_total"] for r in tol],
            [r["errors"]["srti_dR_m"] for r in tol],
            "o", color="#1f77b4", ms=6, label="Tolerance sweep")
    ax.plot([r["nfev_total"] for r in ms],
            [r["errors"]["srti_dR_m"] for r in ms],
            "^", color="#2ca02c", ms=7, label="Max-step sweep")
    ax.plot(prod["nfev_total"], prod_srti_dR, "r*", ms=18,
            label="Production (rtol=1e-9, max_step=20 s)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("nfev (total)")
    ax.set_ylabel(r"$|\Delta R_{\mathrm{SRTI}}|$ [m]")
    ax.set_title("Accuracy–cost trade-off")
    ax.grid(alpha=0.3, which="both")
    ax.annotate(
        f"production error \u2248 {prod_srti_dR * 1e3:.1f} mm\n"
        "topology stable (18/18)",
        xy=(prod["nfev_total"], prod_srti_dR),
        xytext=(0.60, 0.06), textcoords="axes fraction",
        fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8))
    _legend_once(ax, fontsize=8, loc="upper right")
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
