"""Build the M3-D3 D3-0 HOLD-boundary diagnosis without simulation.

This program reads the committed M3-D2 JSON artifacts only.  It imports no
simulator/controller module and writes descriptive D3-0 tables, figures, and
reports.  Formal labels remain the D2 classifier labels; ``hold_proximity`` is
explicitly diagnostic-only.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO = Path(__file__).resolve().parents[1]
DISCOVERY = REPO / "results/phase_m3d2/summary/m3d2_discovery_summary.json"
CONFIRMATION = REPO / "results/phase_m3d2/summary/m3d2_confirmation_summary.json"
CONFIG_FREEZE = REPO / "docs/phase_m1d/M1_D_Benchmark_Freeze.json"
OUT = REPO / "results/phase_m3d3/summary"
DOCS = REPO / "docs/phase_m3d3"
FIGURES = REPO / "figures/phase_m3d3"

COLORS = {"WIDEN": "#1f77b4", "HOLD": "#2ca02c", "SHRINK": "#d62728",
          "AMBIGUOUS": "#7f7f7f", "INVALID": "#9467bd"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _paired(a: list[float], b: list[float]) -> tuple[float, float, float]:
    delta = [x - y for x, y in zip(a, b, strict=True)]
    mean = sum(delta) / len(delta)
    variance = sum((x - mean) ** 2 for x in delta) / (len(delta) - 1)
    se = math.sqrt(variance / len(delta))
    return mean, se, abs(mean) / (2.0 * se) if se else math.inf


def _enrich(record: dict, confirmation: dict[str, dict]) -> dict:
    arms = record["arms"]
    base, widen, shrink = arms["base"], arms["widen"], arms["shrink"]
    dw, sew, sw = _paired(widen["m2_batches"], base["m2_batches"])
    ds, ses, ss = _paired(shrink["m2_batches"], base["m2_batches"])
    ratios = record["oracle_details"]["ratios"]
    conf = confirmation.get(record["state_id"], {})
    row = {
        "candidate_index": record["candidate_index"],
        "state_id": record["state_id"],
        "config_id": record["config_id"],
        "s2": record["s2"],
        "original_stratum": record["candidate_stratum"],
        "discovery_class": record["corrected_class"],
        "confirmation_class": conf.get("corrected_class", ""),
        "widen_ratio_over_base": ratios["widen_over_base"],
        "shrink_ratio_over_base": ratios["shrink_over_base"],
        "widen_minus_base_m2": dw,
        "widen_paired_se": sew,
        "widen_support_ratio_abs_delta_over_2se": sw,
        "shrink_minus_base_m2": ds,
        "shrink_paired_se": ses,
        "shrink_support_ratio_abs_delta_over_2se": ss,
        "widen_support": record["oracle_details"]["support"].get("base_vs_widen_supported", ""),
        "shrink_support": record["oracle_details"]["support"].get("base_vs_shrink_supported", ""),
        "direction_margin": record["oracle_details"]["direction_margin_Delta_dir"],
        "discovery_ambiguity_reason": record.get("ambiguity_or_invalid_reason") or "",
        "confirmation_ambiguity_reason": conf.get("ambiguity_or_invalid_reason") or "",
        "p_ref_full": record["p_ref_full"],
        "p_ref_full_se": record["p_ref_full_SE"],
        "minimum_arm_ess": record["minimum_arm_ESS"],
        "hold_proximity_score_diagnostic_only": max(abs(ratios["widen_over_base"]),
                                                      abs(ratios["shrink_over_base"])),
    }
    return row


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _brackets(rows: list[dict]) -> list[dict]:
    """Return W-to-S paths with an interior HOLD or ambiguity-only corridor."""
    result: list[dict] = []
    by_config: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_config[row["config_id"]].append(row)
    for config_id, group in sorted(by_config.items()):
        group.sort(key=lambda item: item["s2"])
        for i, left in enumerate(group):
            if left["discovery_class"] != "WIDEN":
                continue
            for j in range(i + 1, len(group)):
                right = group[j]
                if right["discovery_class"] != "SHRINK":
                    continue
                interior = group[i + 1:j]
                classes = [item["discovery_class"] for item in interior]
                if any(item == "INVALID" for item in classes):
                    continue
                if "HOLD" in classes and all(item in {"AMBIGUOUS", "HOLD"}
                                             for item in classes):
                    kind = "W_H_S_PATH"
                elif classes and all(item == "AMBIGUOUS" for item in classes):
                    kind = "W_AMBIGUOUS_S_PATH"
                else:
                    continue
                result.append({
                    "config_id": config_id,
                    "s2_left": left["s2"],
                    "class_left": "WIDEN",
                    "s2_right": right["s2"],
                    "class_right": "SHRINK",
                    "interior_state_ids": ";".join(item["state_id"] for item in interior),
                    "interior_classes": ";".join(classes),
                    "boundary_type": kind,
                    "confirmed_hold_inside_path": any(
                        item["confirmation_class"] == "HOLD" for item in interior),
                })
                break
    return result


def _axis_inventory(configs: list[dict], brackets: list[dict]) -> list[dict]:
    values = ";".join(str(x) for x in [1.25, 1.6, 2.0, 2.5, 3.2, 4.0, 5.0, 6.4, 8.0])
    config_ids = ";".join(item["config_id"] for item in configs)
    return [
        {
            "axis_name": "s2_selected_component_covariance_scale",
            "source_file": "configs/phase_m3d2/m3d2_candidate_states.json; src/hyptraj/m3d/benchmark_states.py",
            "current_values": values,
            "scientific_meaning": "isotropic covariance scale of the frozen selected proposal component",
            "continuous_or_discrete": "continuous, sampled on a fixed grid",
            "can_interpolate_scientifically": "YES",
            "already_varied_in_d2": "YES",
            "evidence_of_class_transition": f"YES: {len(brackets)} W-to-S transition paths across fixed configs",
            "hold_enrichment_plausibility": "HIGH; confirmed HOLD occurs inside two observed W-H-S paths",
        },
        {
            "axis_name": "frozen_config_id",
            "source_file": "docs/phase_m1d/M1_D_Benchmark_Freeze.json",
            "current_values": config_ids,
            "scientific_meaning": "joint frozen event-geometry configuration",
            "continuous_or_discrete": "discrete multivariate configuration",
            "can_interpolate_scientifically": "NOT AS A SINGLE AXIS",
            "already_varied_in_d2": "YES",
            "evidence_of_class_transition": "Not isolatable: all geometry parameters co-vary between configs",
            "hold_enrichment_plausibility": "SECONDARY ONLY",
        },
        {
            "axis_name": "event_geometry_theta_h_curvature_offset",
            "source_file": "docs/phase_m1d/M1_D_Benchmark_Freeze.json; src/hyptraj/m1d/benchmark_family.py",
            "current_values": "theta_deg, h, curved, curvature_c, offset_o recorded per frozen config",
            "scientific_meaning": "topology-cap directions, thresholds, and missing-mode curvature",
            "continuous_or_discrete": "mixed, but coupled in D2 configs",
            "can_interpolate_scientifically": "NOT IDENTIFIABLE FROM D2 ALONE",
            "already_varied_in_d2": "Only through coupled frozen config identities",
            "evidence_of_class_transition": "No controlled one-axis transition in D2",
            "hold_enrichment_plausibility": "UNRESOLVED; rejected as primary",
        },
        {
            "axis_name": "selected_mode_and_component_mean",
            "source_file": "results/phase_m3d2/summary/m3d2_candidate_pool.json",
            "current_values": "selected modes S2/S3/S4 and derived anchor means",
            "scientific_meaning": "frozen M1-D variance-selector outcome and resulting newborn-component location",
            "continuous_or_discrete": "categorical / derived",
            "can_interpolate_scientifically": "NO",
            "already_varied_in_d2": "YES across configs",
            "evidence_of_class_transition": "Transitions occur within fixed modes as s2 varies",
            "hold_enrichment_plausibility": "SECONDARY ONLY",
        },
    ]


def _figures(rows: list[dict], brackets: list[dict]) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    by_config: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_config[row["config_id"]].append(row)
    fig, axes = plt.subplots(4, 2, figsize=(11, 12), sharex=True, sharey=True)
    y = {"WIDEN": 2, "HOLD": 1, "SHRINK": 0, "AMBIGUOUS": -1, "INVALID": -2}
    for ax, (config, group) in zip(axes.flat, sorted(by_config.items())):
        for row in group:
            ax.scatter(row["s2"], y[row["discovery_class"]], color=COLORS[row["discovery_class"]], s=45)
        ax.set_title(config.split("_")[-1]); ax.grid(alpha=.25)
    fig.supxlabel("s2"); fig.supylabel("discovery class: W=2, H=1, S=0, A=-1")
    fig.tight_layout(); fig.savefig(FIGURES / "D3-0-1_class_vs_s2_by_config.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 6))
    for label, color in COLORS.items():
        group = [row for row in rows if row["discovery_class"] == label]
        ax.scatter([row["widen_ratio_over_base"] for row in group], [row["shrink_ratio_over_base"] for row in group], label=label, color=color, alpha=.8)
    ax.axvline(-.01, color="black", lw=.7); ax.axhline(-.01, color="black", lw=.7)
    ax.axvline(.03, color="gray", lw=.5, ls="--"); ax.axvline(-.03, color="gray", lw=.5, ls="--")
    ax.axhline(.03, color="gray", lw=.5, ls="--"); ax.axhline(-.03, color="gray", lw=.5, ls="--")
    ax.set(xlabel="WIDEN ratio M2(widen)/M2(base)-1", ylabel="SHRINK ratio M2(shrink)/M2(base)-1")
    ax.legend(); ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(FIGURES / "D3-0-2_widen_shrink_contrast_plane.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 6))
    for row in rows:
        if row["confirmation_class"] == "HOLD":
            ax.scatter(row["widen_ratio_over_base"], row["shrink_ratio_over_base"], s=100, marker="*", color=COLORS["HOLD"], label="confirmed HOLD")
    ax.axvspan(-.03, .03, alpha=.12, color=COLORS["HOLD"]); ax.axhspan(-.03, .03, alpha=.12, color=COLORS["HOLD"])
    ax.set(xlabel="WIDEN ratio", ylabel="SHRINK ratio", title="Confirmed HOLD locations (discovery contrasts)")
    ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(FIGURES / "D3-0-3_confirmed_hold_locations.png", dpi=160); plt.close(fig)
    lost = [row for row in rows if row["discovery_class"] == "HOLD" and row["confirmation_class"] == "AMBIGUOUS"]
    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar([row["state_id"] for row in lost], [row["hold_proximity_score_diagnostic_only"] for row in lost], color=COLORS["AMBIGUOUS"])
    ax.set(ylabel="diagnostic H-proximity", title="Lost HOLD: discovery HOLD → confirmation AMBIGUOUS"); fig.tight_layout(); fig.savefig(FIGURES / "D3-0-4_lost_hold_transitions.png", dpi=160); plt.close(fig)
    ambiguous = [row for row in rows if row["discovery_class"] == "AMBIGUOUS"]
    counts = Counter(row["discovery_ambiguity_reason"] for row in ambiguous)
    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(list(counts), list(counts.values()), color=COLORS["AMBIGUOUS"]); ax.set(ylabel="states", title="Discovery ambiguity reasons"); fig.tight_layout(); fig.savefig(FIGURES / "D3-0-5_ambiguity_reason_map.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 3)); ax.axis("off")
    table = [[b["config_id"].split("_")[-1], b["s2_left"], b["s2_right"], b["boundary_type"], b["confirmed_hold_inside_path"]] for b in brackets]
    ax.table(cellText=table, colLabels=["config", "left", "right", "path", "confirmed H"], loc="center")
    fig.tight_layout(); fig.savefig(FIGURES / "D3-0-6_detected_boundary_brackets.png", dpi=160); plt.close(fig)


def _docs(rows: list[dict], brackets: list[dict], axes: list[dict]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    unsupported = [row for row in rows if row["discovery_ambiguity_reason"] == "unsupported_required_contrast"]
    nonunique = [row for row in rows if row["discovery_ambiguity_reason"] == "no_unique_preregistered_class"]
    med = lambda values: sorted(values)[len(values) // 2]
    (DOCS / "M3_D3_HOLD_Enriched_Benchmark_Task.md").write_text(
        "# M3-D3 HOLD-Enriched Corrected Benchmark Study\n\n"
        "D3-0 is the only completed part of this task record. It reads D2 artifacts, makes zero simulator calls, and routes to a human scientific decision before any D3-1 preregistration or simulation. The immutable user-supplied source taskbook is `D:/Users/huangyx/Downloads/M3_D3_HOLD_Enriched_Corrected_Benchmark_Task.md`.\n",
        encoding="utf-8")
    (DOCS / "M3_D3_Classifier_Contract.md").write_text(
        "# M3-D3 classifier contract (verbatim D2 reuse)\n\n"
        "D3-0 does not change the D2 classifier. Objective is `M2=mean((I[topology != S0] p/q_arm)^2)`. The three CRN arms are BASE, WIDEN and SHRINK. WIDEN requires its relative M2 reduction below -1%, lower M2 than SHRINK, both base contrasts supported at |delta M2| >= 2 paired SE, and direction margin >=5%. SHRINK is symmetric. HOLD requires neither improvement rule and both arm/base ratios within +/-3%. Unsupported required contrast, failed direction margin, or no unique class is AMBIGUOUS. Probability failure, non-finite arithmetic, illegality, draw mismatch, or ESS<20 is INVALID.\n\n"
        "Decision-map coordinates are the native ratios `M2(widen)/M2(base)-1` and `M2(shrink)/M2(base)-1`. `hold_proximity_score=max(abs(r_w),abs(r_s))` is descriptive only and never replaces this contract.\n",
        encoding="utf-8")
    (DOCS / "M3_D3_Lost_HOLD_Audit.md").write_text(
        "# Lost HOLD audit\n\n"
        "The two D2 provisional HOLD states `c006_s2_00125` and `c006_s2_00800` became AMBIGUOUS at independent confirmation. Both retain valid full-event probability and numerical/ESS checks; the recorded cause is `unsupported_required_contrast`. This is a support failure for the action comparison, not evidence permitting reassignment to HOLD. No replacement or rerun is authorized.\n",
        encoding="utf-8")
    (DOCS / "M3_D3_HOLD_Boundary_Diagnosis.md").write_text(
        "# M3-D3 D3-0 HOLD Boundary Diagnosis\n\n"
        "## Zero-simulator provenance\n\nAll figures and tables are reconstructed from committed M3-D2 discovery and confirmation JSON. This script imports no simulator or controller code; `extra_simulator_calls = 0`.\n\n"
        "## Result\n\n**HOLD concentrated near an identifiable boundary: YES.** The primary candidate-family axis is the selected-component covariance scale `s2`. Five fixed configurations have a W-to-S path through either ambiguity or HOLD; two (`c001`, `c010`) contain an independently confirmed HOLD interior to a W-H-S path.\n\n"
        "## Why s2 is primary\n\nWithin each frozen configuration D2 varies only `s2`, making its action transition identifiable without changing event semantics or the classifier. The physical geometry fields (`theta_deg`, `h`, curvature flags and offsets) are meaningful but co-vary as discrete frozen configurations; D2 has no controlled one-axis evidence to select one of them. Selected mode/component mean are likewise frozen, categorical or derived.\n\n"
        f"Detected paths: {len(brackets)}. Unsupported-contrast ambiguity has median diagnostic H-proximity {med([r['hold_proximity_score_diagnostic_only'] for r in unsupported]):.4f}; no-unique-class ambiguity has median {med([r['hold_proximity_score_diagnostic_only'] for r in nonunique]):.4f}. These descriptive values do not establish that unsupported states are HOLD-like.\n\n"
        "## Route\n\n**D3-0A — Boundary Identified.** The only next permitted step is a human scientific decision whether to preregister a fixed, boundary-focused `s2` family. D3-1, discovery, confirmation, controller trials, and rarity-shift remain unstarted and unauthorized.\n",
        encoding="utf-8")


def build_d3_0() -> dict:
    discovery = _load(DISCOVERY)
    confirmation_doc = _load(CONFIRMATION)
    confirmation = {row["state_id"]: row for row in confirmation_doc["records"]}
    rows = [_enrich(row, confirmation) for row in discovery["records"]]
    rows.sort(key=lambda row: row["candidate_index"])
    brackets = _brackets(rows)
    configs = _load(CONFIG_FREEZE)["benchmark_configs"]
    axes = _axis_inventory(configs, brackets)
    _write_csv(OUT / "d3_0_d2_state_table.csv", rows)
    holds = [row for row in rows if row["confirmation_class"] == "HOLD"]
    signature = []
    for row in holds:
        copy = dict(row)
        copy["distance_to_widen_improvement_boundary"] = row["widen_ratio_over_base"] + .01
        copy["distance_to_shrink_improvement_boundary"] = row["shrink_ratio_over_base"] + .01
        copy["hold_window_min_slack"] = .03 - max(abs(row["widen_ratio_over_base"]), abs(row["shrink_ratio_over_base"]))
        signature.append(copy)
    _write_csv(OUT / "d3_0_confirmed_hold_signature.csv", signature)
    _write_csv(OUT / "d3_0_s2_boundary_brackets.csv", brackets)
    _write_csv(OUT / "d3_0_candidate_axis_inventory.csv", axes)
    _figures(rows, brackets)
    _docs(rows, brackets, axes)
    return {"extra_simulator_calls": 0, "state_rows": len(rows), "confirmed_hold": len(holds), "brackets": len(brackets), "route": "D3-0A", "primary_axis": "s2_selected_component_covariance_scale"}


if __name__ == "__main__":
    print(json.dumps(build_d3_0(), indent=2))
