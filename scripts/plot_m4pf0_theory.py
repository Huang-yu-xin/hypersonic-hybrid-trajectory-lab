"""Render PF0 deterministic theory-validation figures only."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf0" / "summary"
DEST = REPO / "figures" / "phase_m4pf0"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    doc = json.loads((SUMMARY / "m4pf0_gradient_diagnostics.json").read_text(
        encoding="utf-8"))
    fixture = doc["gaussian_fixture"]
    records = fixture["fd_records"]

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for name in ("identity", "rank1", "mixed"):
        rows = sorted((r for r in records if r["direction"] == name),
                      key=lambda r: r["epsilon"])
        ax.loglog([r["epsilon"] for r in rows],
                  [r["relative_error"] for r in rows], marker="o", label=name)
    ax.set(xlabel="central-difference epsilon",
           ylabel="relative error",
           title="PF0-T1  Log-covariance directional derivative validation")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(DEST / "PF0-T1_directional_fd_convergence.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.8))
    values = [fixture["scalar_trace"], fixture["identity_directional"]]
    bars = ax.bar(["trace(G)", "<G, I>"], values,
                  color=["#2878B5", "#D95319"])
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value,
                f"{value:.10f}", ha="center",
                va="bottom" if value >= 0 else "top")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set(ylabel="directional derivative",
           title="PF0-T2  Scalar direction is the matrix trace")
    fig.tight_layout()
    fig.savefig(DEST / "PF0-T2_scalar_trace_recovery.png", dpi=200)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
