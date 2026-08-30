"""Render the ten preregistered M4-PF1 result figures."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf1" / "summary"
RAW = REPO / "results" / "phase_m4pf1" / "m4pf1_confirmation_raw.json"
DEST = REPO / "figures" / "phase_m4pf1"
COLORS = {"S0": "#6E7781", "S1": "#2878B5", "S2": "#D95319"}


def rows(name: str) -> list[dict]:
    with (SUMMARY / name).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def gate_lines(ax, orientation="horizontal"):
    if orientation == "horizontal":
        ax.axhline(0.1, color="#E6A700", linestyle="--", linewidth=1,
                   label="material gate 0.1")
        ax.axhline(1.0, color="#B22222", linestyle=":", linewidth=1.2,
                   label="absolute gate 1")
    else:
        ax.axvline(0.1, color="#E6A700", linestyle="--", linewidth=1)
        ax.axvline(1.0, color="#B22222", linestyle=":", linewidth=1.2)


def save(fig, name: str):
    fig.tight_layout()
    fig.savefig(DEST / name, dpi=200)
    plt.close(fig)


def scatter_compare(state, family: str, filename: str):
    s0 = {r["state_id"]: float(r["VRF_budget"]) for r in state
          if r["family"] == "S0"}
    fam = {r["state_id"]: float(r["VRF_budget"]) for r in state
           if r["family"] == family}
    fig, ax = plt.subplots(figsize=(6.3, 5.7))
    for cls, marker in (("WIDEN", "o"), ("SHRINK", "s")):
        ids = [r["state_id"] for r in state
               if r["family"] == family and r["action_class"] == cls]
        ax.scatter([s0[i] for i in ids], [fam[i] for i in ids], marker=marker,
                   label=cls, alpha=0.85, color=COLORS[family])
    lo = min(min(s0.values()), min(fam.values())) * 0.9
    hi = max(max(s0.values()), max(fam.values())) * 1.1
    ax.plot([lo, hi], [lo, hi], color="black", linewidth=1, label="equal VRF")
    ax.set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
           xlabel="S0 statewise FreeOracle VRF",
           ylabel=f"{family} statewise FreeOracle VRF",
           title=f"PF1 statewise S0 vs {family}")
    ax.grid(True, which="both", alpha=0.2)
    ax.legend(frameon=False)
    save(fig, filename)


def add_covariance_ellipse(ax, covariance, color, label):
    vals, vecs = np.linalg.eigh(np.asarray(covariance, dtype=float))
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    angle = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    ellipse = Ellipse((0, 0), 2 * np.sqrt(vals[0]), 2 * np.sqrt(vals[1]),
                      angle=angle, fill=False, linewidth=2, color=color,
                      label=label)
    ax.add_patch(ellipse)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    family = rows("m4pf1_family_summary.csv")
    state = rows("m4pf1_state_table.csv")
    tails = rows("m4pf1_tail_diagnostics.csv")
    raw = json.loads(RAW.read_text(encoding="utf-8"))

    # PF1-1
    fig, ax = plt.subplots(figsize=(6.8, 5.2))
    names = [r["family"] for r in family]
    values = [float(r["median_FreeOracle_VRF"]) for r in family]
    bars = ax.bar(names, values, color=[COLORS[n] for n in names])
    gate_lines(ax)
    ax.set(yscale="log", ylabel="median FreeOracle VRF",
           title="PF1-1  Absolute efficiency by proposal family")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, value * 1.05,
                f"{value:.5f}", ha="center", va="bottom")
    ax.legend(frameon=False)
    save(fig, "PF1-1_freeoracle_vrf_by_family.png")

    scatter_compare(state, "S1", "PF1-2_s0_vs_s1_statewise_vrf.png")
    scatter_compare(state, "S2", "PF1-3_s0_vs_s2_statewise_vrf.png")

    # PF1-4
    ids = [r["state_id"] for r in state if r["family"] == "S0"]
    fig, ax = plt.subplots(figsize=(12.0, 5.2))
    x = np.arange(len(ids))
    for name in ("S0", "S1", "S2"):
        lookup = {r["state_id"]: float(r["VRF_budget"]) for r in state
                  if r["family"] == name}
        ax.plot(x, [lookup[i] for i in ids], marker="o", markersize=3,
                linewidth=1.2, color=COLORS[name], label=name)
    gate_lines(ax)
    ax.set(yscale="log", xticks=x, xticklabels=ids, ylabel="FreeOracle VRF",
           title="PF1-4  Frozen 24-state absolute-VRF comparison")
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    ax.legend(frameon=False, ncol=3)
    save(fig, "PF1-4_24_state_log_vrf.png")

    # PF1-5
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    x = np.arange(2)
    width = 0.24
    for offset, name in zip((-1, 0, 1), ("S0", "S1", "S2")):
        record = next(r for r in family if r["family"] == name)
        vals = [float(record["WIDEN_median_VRF"]),
                float(record["SHRINK_median_VRF"])]
        ax.bar(x + offset*width, vals, width, color=COLORS[name], label=name)
    gate_lines(ax)
    ax.set(yscale="log", xticks=x, xticklabels=["WIDEN", "SHRINK"],
           ylabel="class median FreeOracle VRF",
           title="PF1-5  Class-conditional structured comparison")
    ax.legend(frameon=False)
    save(fig, "PF1-5_class_conditional_vrf.png")

    # PF1-6
    s0 = {r["state_id"]: float(r["VRF_budget"]) for r in state
          if r["family"] == "S0"}
    fig, ax = plt.subplots(figsize=(6.8, 5.2))
    for name, marker in (("S1", "o"), ("S2", "s")):
        subset = [r for r in state if r["family"] == name]
        ax.scatter([float(r["anisotropy_score"]) for r in subset],
                   [float(r["VRF_budget"])/s0[r["state_id"]] for r in subset],
                   marker=marker, alpha=0.8, color=COLORS[name], label=name)
    ax.axhline(1, color="black", linewidth=1)
    ax.set(xscale="log", xlabel="gradient anisotropy score",
           ylabel="statewise VRF ratio to S0",
           title="PF1-6  Anisotropy does not close the efficiency gap")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False)
    save(fig, "PF1-6_vrf_gain_vs_anisotropy.png")

    # PF1-7
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), sharey=True)
    s1 = [r for r in state if r["family"] == "S1"]
    for ax, field, label in zip(
            axes, ("top1_spectral_fraction", "top2_spectral_fraction"),
            ("top-1 spectral fraction", "top-2 spectral fraction")):
        ax.scatter([float(r[field]) for r in s1],
                   [float(r["VRF_budget"])/s0[r["state_id"]] for r in s1],
                   c=["#2878B5" if r["action_class"] == "WIDEN" else "#D95319"
                      for r in s1], alpha=0.85)
        ax.axhline(1, color="black", linewidth=1)
        ax.set(xlabel=label)
        ax.grid(True, alpha=0.2)
    axes[0].set_ylabel("S1 VRF ratio to S0")
    fig.suptitle("PF1-7  Spectral concentration versus realized VRF gain")
    save(fig, "PF1-7_vrf_gain_vs_spectral_mass.png")

    # PF1-8
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8))
    for idx, name in enumerate(("S0", "S1", "S2")):
        vals_ess = [float(r["ESS"]) for r in tails if r["family"] == name]
        vals_max = [float(r["max_normalized_weight"]) for r in tails
                    if r["family"] == name]
        axes[0].boxplot(vals_ess, positions=[idx], widths=0.55,
                        patch_artist=True,
                        boxprops={"facecolor": COLORS[name], "alpha": 0.65})
        axes[1].boxplot(vals_max, positions=[idx], widths=0.55,
                        patch_artist=True,
                        boxprops={"facecolor": COLORS[name], "alpha": 0.65})
    for ax in axes:
        ax.set_xticks(range(3), ["S0", "S1", "S2"])
        ax.grid(True, axis="y", alpha=0.2)
    axes[0].set_ylabel("event-weight ESS")
    axes[1].set_ylabel("maximum normalized weight")
    fig.suptitle("PF1-8  Selected-arm ESS and tail concentration")
    save(fig, "PF1-8_ess_tail_risk.png")

    # PF1-9
    fig, ax = plt.subplots(figsize=(8.0, 3.5))
    ax.set_xscale("log")
    ax.set_xlim(0.004, 2)
    gate_lines(ax, "vertical")
    for y, (name, value) in enumerate(zip(names, values)):
        ax.scatter(value, y, s=95, color=COLORS[name], zorder=3)
        ax.text(value*1.05, y, f"{name}  {value:.5f}", va="center")
    ax.set(yticks=[], xlabel="median FreeOracle VRF",
           title="PF1-9  Structured proposal remains below both gates")
    ax.grid(True, axis="x", which="both", alpha=0.2)
    save(fig, "PF1-9_efficiency_gate.png")

    # PF1-10: state with greatest S1/S0 gain and state with greatest loss.
    ratio = {r["state_id"]: float(r["VRF_budget"])/s0[r["state_id"]]
             for r in s1}
    representative = [max(ratio, key=ratio.get), min(ratio, key=ratio.get)]
    raw_by_id = {r["state_id"]: r for r in raw["states"]}
    state_by_id = {r["state_id"]: r for r in state if r["family"] == "S0"}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.5))
    for ax, sid in zip(axes, representative):
        record = raw_by_id[sid]
        s2 = float(record["state_key"]["s2"])
        action = state_by_id[sid]["selected_arm"]
        shift = 0.2 if action == "widen" else (-0.2 if action == "shrink" else 0)
        cov0 = s2 * np.exp(shift) * np.eye(2)
        add_covariance_ellipse(ax, cov0, COLORS["S0"], "S0 selected")
        add_covariance_ellipse(ax, record["updates"]["S1"]["covariance"],
                               COLORS["S1"], "S1")
        add_covariance_ellipse(ax, record["updates"]["S2"]["covariance"],
                               COLORS["S2"], "S2")
        bound = 1.25 * np.sqrt(max(np.linalg.eigvalsh(cov0).max(),
                                  np.linalg.eigvalsh(record["updates"]["S1"]
                                                     ["covariance"]).max()))
        ax.set(xlim=(-bound, bound), ylim=(-bound, bound), aspect="equal",
               title=f"{sid}\nS1/S0 VRF={ratio[sid]:.3f}")
        ax.grid(True, alpha=0.2)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("PF1-10  Representative selected-component covariances")
    save(fig, "PF1-10_structured_covariance_examples.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
