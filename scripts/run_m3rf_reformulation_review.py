"""Build the zero-simulator M3-RF corrected action-space review.

The program is intentionally an evidence reader: it imports neither the
simulator nor controller code.  It only reads committed corrected-lineage
artifacts, deduplicates frozen state identities, and writes review tables,
figures, documents, and the route decision.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results/phase_m3rf/summary"
DOCS = REPO / "docs/phase_m3rf"
FIGS = REPO / "figures/phase_m3rf"

SOURCES = [
    ("results/evidence_repair/summary/er1_final_lineage.json", "ER-1 corrected lineage"),
    ("results/evidence_repair/reanalysis/M3-D/m3d_corrected_reference_gate.json", "M3-D-v1 corrected reference gate"),
    ("results/evidence_repair/reanalysis/M3-D/m3d_corrected_reference_freeze.json", "M3-D corrected 24-state reference"),
    ("results/phase_m3d2/summary/m3d2_candidate_pool.json", "D2 frozen 72-state candidate pool"),
    ("results/phase_m3d2/summary/m3d2_discovery_summary.json", "D2 discovery"),
    ("results/phase_m3d2/summary/m3d2_confirmation_summary.json", "D2 independent confirmation"),
    ("results/phase_m3d2/summary/m3d2_class_transition.json", "D2 class transitions"),
    ("results/phase_m3d2/summary/m3d2_final_verdict.json", "D2 final verdict"),
    ("results/phase_m3d3/summary/m3d3_d3_0_summary.json", "D3-0 boundary diagnosis"),
    ("results/phase_m3d3/summary/d3_0_s2_boundary_brackets.csv", "D3-0 boundary brackets"),
    ("docs/phase_m3d3/M3_D3_D3_1_Pregistration.md", "D3-1 preregistration"),
    ("results/phase_m3d3/summary/m3d3_discovery_summary.json", "D3-2 raw discovery and summary"),
    ("results/phase_m3d3/summary/m3d3_discovery_candidate_audit.csv", "D3-2 candidate audit"),
    ("docs/phase_m3d3/M3_D3_D3_2_Discovery_Verdict.md", "D3-2 final discovery verdict"),
    ("docs/phase_m3d3/M3_D3_Classifier_Contract.md", "frozen classifier source"),
    ("docs/evidence_repair/ER1_Event_Semantics_Contract.md", "full-event semantics contract"),
]

COLORS = {"WIDEN": "#2878B5", "HOLD": "#3B9C5A", "SHRINK": "#D95319",
          "AMBIGUOUS": "#777777", "INVALID": "#111111"}
ORDER = ["WIDEN", "HOLD", "SHRINK", "AMBIGUOUS", "INVALID"]


def load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def source_manifest() -> dict:
    items = []
    for rel, role in SOURCES:
        path = REPO / rel
        items.append({
            "path": rel.replace("\\", "/"), "sha256": sha(path),
            "commit": git("rev-list", "-1", "HEAD", "--", rel),
            "role": role, "read_only": True,
        })
    required_tags = ["RareTopo-ER1-v0", "RareTopo-M3-v2", "RareTopo-M3-D-v1"]
    return {
        "schema_version": "raretopo-m3rf-source-manifest-v0",
        "stage": "M3-RF", "read_only_sources": True,
        "extra_simulator_calls": 0, "controller_online_trials": 0,
        "rarity_shift": "BLOCKED", "m3_q": "BLOCKED",
        "parent_lineage": {
            "ER1": git("rev-parse", "RareTopo-ER1-v0"),
            "M3-v2": git("rev-parse", "RareTopo-M3-v2"),
            "M3-D-v1": git("rev-parse", "RareTopo-M3-D-v1"),
            "D2_final_commit": git("rev-parse", "f031512"),
            "D3-0_commit": git("rev-parse", "7b38bec"),
            "D3-1_commit": git("rev-parse", "e3ed6dc"),
            "D3-2_commit": git("rev-parse", "a568418"),
        },
        "items": items,
    }


def paired_support(record: dict) -> tuple[float | None, float | None]:
    """Return min contrast support and a representative paired SE."""
    if "paired_contrasts" in record:
        contrasts = record["paired_contrasts"].values()
        values = [(abs(c["delta_m2"]) / (2 * c["paired_se"]), c["paired_se"])
                  for c in contrasts if c["paired_se"]]
        return min(x[0] for x in values), max(x[1] for x in values)
    base = record["arms"]["base"]["m2_batches"]
    values = []
    for arm in ("widen", "shrink"):
        delta = [a - b for a, b in zip(record["arms"][arm]["m2_batches"], base, strict=True)]
        mean = sum(delta) / len(delta)
        variance = sum((x - mean) ** 2 for x in delta) / (len(delta) - 1)
        se = math.sqrt(variance / len(delta))
        values.append((abs(mean) / (2 * se) if se else None, se))
    return min(x[0] for x in values if x[0] is not None), max(x[1] for x in values)


def ratios(record: dict) -> tuple[float | None, float | None]:
    if "r_w" in record:
        return record["r_w"], record["r_s"]
    item = record.get("oracle_details", {}).get("ratios", {})
    return item.get("widen_over_base"), item.get("shrink_over_base")


def build_universe() -> tuple[list[dict], dict, list[dict]]:
    m3 = load("results/evidence_repair/reanalysis/M3-D/m3d_corrected_reference_freeze.json")["states"]
    d2 = load("results/phase_m3d2/summary/m3d2_discovery_summary.json")["records"]
    confirmation = load("results/phase_m3d2/summary/m3d2_confirmation_summary.json")["records"]
    d3 = load("results/phase_m3d3/summary/m3d3_discovery_summary.json")["records"]
    conf = {row["state_id"]: row for row in confirmation}
    rows: dict[str, dict] = {}

    def add(state_id: str, source: str, values: dict) -> dict:
        row = rows.setdefault(state_id, {"state_id": state_id, "source_stages": []})
        row["source_stages"].append(source)
        for key, value in values.items():
            if value is not None and value != "":
                row[key] = value
        return row

    for item in m3:
        label = item["class"].replace("REFERENCE_", "")
        add(item["state_id"], "M3-D", {
            "config_id": item["config_id"], "s2": item["s2"], "m3d_class": label,
            "selected_mode": item.get("selected_mode"),
            "direction_margin": item.get("direction_margin_Delta_dir"),
            "confirmation_status": "REFERENCE_ONLY",
        })
    for item in d2:
        rw, rs = ratios(item)
        support, se = paired_support(item)
        row = add(item["state_id"], "D2-DISCOVERY", {
            "config_id": item["config_id"], "s2": item["s2"], "selected_mode": item.get("selected_mode"),
            "discovery_class": item["corrected_class"], "r_w": rw, "r_s": rs,
            "paired_support": support, "paired_se": se,
            "direction_margin": item["oracle_details"].get("direction_margin_Delta_dir"),
            "ambiguity_reason": item.get("ambiguity_or_invalid_reason"),
            "minimum_arm_ess": item.get("minimum_arm_ESS"),
            "hold_proximity_score": max(abs(rw), abs(rs)),
            "confirmation_status": "NOT_SELECTED",
        })
        if item["state_id"] in conf:
            c = conf[item["state_id"]]
            crw, crs = ratios(c)
            csup, cse = paired_support(c)
            row["source_stages"].append("D2-CONFIRMATION")
            row.update({
                "confirmed_class": c["corrected_class"], "confirmation_status": "CONFIRMED",
                "confirmation_r_w": crw, "confirmation_r_s": crs,
                "confirmation_paired_support": csup, "confirmation_paired_se": cse,
                "confirmation_direction_margin": c["oracle_details"].get("direction_margin_Delta_dir"),
                "confirmation_ambiguity_reason": c.get("ambiguity_or_invalid_reason"),
                "independent_confirmation_flag": True,
            })
        else:
            row["independent_confirmation_flag"] = False
    for item in d3:
        support, se = paired_support(item)
        add(item["state_id"], "D3-BOUNDARY", {
            "config_id": item["config_id"], "s2": item["generated_s2"],
            "d3_class": item["corrected_class"], "r_w": item["r_w"], "r_s": item["r_s"],
            "paired_support": support, "paired_se": se,
            "direction_margin": item["oracle_details"].get("direction_margin_Delta_dir"),
            "ambiguity_reason": item.get("ambiguity_or_invalid_reason"),
            "minimum_arm_ess": item.get("minimum_arm_ESS"),
            "hold_proximity_score": item["hold_proximity_score"],
            "confirmation_status": "NOT_APPLICABLE_D3_DISCOVERY", "independent_confirmation_flag": False,
        })
    out = []
    for row in rows.values():
        row["stage"] = "|".join(row.pop("source_stages"))
        row["class"] = row.get("confirmed_class") or row.get("d3_class") or row.get("discovery_class") or row.get("m3d_class")
        row.setdefault("independent_confirmation_flag", False)
        out.append(row)
    out.sort(key=lambda x: (x["config_id"], x["s2"], x["state_id"]))
    duplicate_observations = len(m3) + len(d2) + len(confirmation) + len(d3) - len(out)
    duplicate_identities = sum(1 for row in out if "|" in row["stage"])
    audit = {"unique_state_count": len(out), "duplicate_state_count": duplicate_observations,
             "duplicate_identity_count": duplicate_identities, "raw_observation_count": len(m3) + len(d2) + len(confirmation) + len(d3)}
    return out, audit, d3


def csv_write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def comparison_rows(universe: list[dict]) -> list[dict]:
    result = []
    for row in universe:
        group = None
        if "D3-BOUNDARY" in row["stage"] and row["d3_class"] == "HOLD":
            group = "D3_HOLD"
        elif "D3-BOUNDARY" in row["stage"] and row["d3_class"] == "AMBIGUOUS":
            group = "D3_AMBIGUOUS"
        elif row.get("discovery_class") == "HOLD" and row.get("confirmed_class") == "HOLD":
            group = "D2_CONFIRMED_HOLD"
        elif row.get("discovery_class") == "HOLD" and row.get("confirmed_class") != "HOLD":
            group = "D2_PROVISIONAL_HOLD_LOST_AT_CONFIRMATION"
        if group:
            item = {key: row.get(key) for key in ["state_id", "stage", "config_id", "s2", "class", "r_w", "r_s", "paired_support", "paired_se", "direction_margin", "hold_proximity_score", "minimum_arm_ess", "ambiguity_reason", "confirmation_ambiguity_reason"]}
            item["comparison_group"] = group
            result.append(item)
    return result


def status_matrix() -> list[dict]:
    evidence = [
        ("W availability", "SUPPORTED", "SUPPORTED", "SUPPORTED", "D2 confirmation: W=12"),
        ("S availability", "SUPPORTED", "SUPPORTED", "SUPPORTED", "D2 confirmation: S=10"),
        ("H availability", "WEAK", "NOT APPLICABLE", "NOT APPLICABLE", "D2 confirmed H=3; D3 H=2/14"),
        ("ambiguity handling", "UNSUPPORTED", "SUPPORTED", "WEAK", "D3: ambiguity=10/14; abstention has direct protocol interpretation"),
        ("independent confirmation", "WEAK", "SUPPORTED", "WEAK", "W/S confirmed; only 3 D2 HOLD reproduce"),
        ("boundary stability", "UNSUPPORTED", "SUPPORTED", "WEAK", "D3 targeted boundary: 2 HOLD vs 10 ambiguity"),
        ("natural benchmark construction", "UNSUPPORTED", "SUPPORTED", "WEAK", "Balanced 8/8/8 failed twice; W/S available without HOLD quota"),
        ("requires threshold change", "UNSUPPORTED", "SUPPORTED", "SUPPORTED", "RFB/RFC review does not alter the frozen classifier"),
        ("corrected lineage compatible", "SUPPORTED", "SUPPORTED", "SUPPORTED", "All routes use corrected frozen evidence only"),
    ]
    return [{"Evidence": n, "Three-action": a, "Two-direction+abstain": b, "Continuous": c, "Evidence path": p} for n, a, b, c, p in evidence]


def route_decision(audit: dict, d3: list[dict], comp: list[dict]) -> dict:
    ambiguity = Counter(item.get("ambiguity_or_invalid_reason") or "other" for item in d3 if item["corrected_class"] == "AMBIGUOUS")
    return {
        "schema_version": "raretopo-m3rf-route-decision-v0", "stage": "M3-RF",
        "status": "COMPLETE", "zero_simulator": {"extra_simulator_calls": 0, "controller_online_trials": 0},
        "corrected_evidence": {**audit, "confirmed_W": 12, "confirmed_H": 3, "confirmed_S": 10,
                               "d3_boundary_H": 2, "d3_boundary_ambiguous": 10},
        "hold_prevalence": {"d2_discovery_raw": "5/72 (6.94%)", "d2_confirmation_selection_conditioned": "3/27 (11.11%)", "d3_boundary_provisional": "2/14 (14.29%)"},
        "d3_enrichment_test": {"observed_provisional_hold": "2/14 (14.29%)", "preregistered_target": "10/14 (71.43%)", "absolute_gap_percentage_points": 57.14, "verdict": "FAIL_HOLD_INSUFFICIENT"},
        "ambiguity": {"d3_count": 10, "d3_prevalence": "10/14 (71.43%)", "causes": dict(ambiguity)},
        "three_action_identifiability": {
            "all_actions_exist": "PASS", "hold_independently_reproducible": "MIXED",
            "hold_not_dominated_by_ambiguity": "FAIL", "diverse_hold_without_posthoc_search": "FAIL",
            "no_classifier_weakening_required": "PASS", "overall": "NOT DEFENSIBLE",
        },
        "route_comparison": {"RFA": "UNSUPPORTED", "RFB": "SUPPORTED", "RFC": "WEAK", "RFD": "WEAK", "RFE": "NOT SELECTED"},
        "primary_route": "M3-RF-B",
        "primary_route_name": "REFORMULATE TO DIRECTIONAL WIDEN/SHRINK + ABSTAIN",
        "rationale": "Confirmed WIDEN=12 and SHRINK=10 provide directional support; HOLD is sparse and D3 boundary targeting yields mostly ambiguity. ABSTAIN is an uncertainty-aware protocol outcome, not a trained third scientific class.",
        "rarity_shift": "BLOCKED", "m3_q": "BLOCKED", "no_third_hold_search": True,
        "next_authorized_scientific_action": "Preregister M3-DS Corrected Directional-Sign Benchmark with WIDEN/SHRINK availability requirements and an abstention policy.",
    }


def save(fig, name: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(FIGS / name, dpi=220, bbox_inches="tight"); plt.close(fig)


def figures(universe: list[dict], d3: list[dict], matrix: list[dict]) -> None:
    d2 = [x for x in universe if "D2-DISCOVERY" in x["stage"]]
    confirmed = [x for x in universe if x.get("confirmed_class")]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sets = [("M3-D", [x.get("m3d_class") for x in universe if "M3-D" in x["stage"]]),
            ("D2 discovery", [x.get("discovery_class") for x in d2]),
            ("D2 confirmation", [x.get("confirmed_class") for x in confirmed]),
            ("D3 boundary", [x.get("d3_class") for x in universe if "D3-BOUNDARY" in x["stage"]])]
    x = np.arange(len(sets)); bottom = np.zeros(len(sets))
    for label in ORDER:
        vals = np.array([Counter(values)[label] for _, values in sets])
        ax.bar(x, vals, bottom=bottom, label=label, color=COLORS[label]); bottom += vals
    ax.set_xticks(x, [n for n, _ in sets]); ax.set_ylabel("state count"); ax.set_title("RF-1 Corrected action counts")
    ax.legend(ncol=5, fontsize=8); save(fig, "RF-1_corrected_class_counts.png")

    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    for label in ORDER:
        rows = [r for r in d2 + [r for r in universe if "D3-BOUNDARY" in r["stage"]] if r["class"] == label and r.get("r_w") is not None]
        if rows: ax.scatter([r["r_w"] for r in rows], [r["r_s"] for r in rows], label=label, color=COLORS[label], alpha=.8)
    ax.axhline(0, color="black", lw=.7); ax.axvline(0, color="black", lw=.7)
    ax.set_xlabel(r"$r_w$"); ax.set_ylabel(r"$r_s$"); ax.set_title("RF-2 D2+D3 corrected decision plane"); ax.legend(fontsize=8)
    save(fig, "RF-2_d2_d3_decision_plane.png")

    comp = comparison_rows(universe)
    fig, ax = plt.subplots(figsize=(6.7, 4.8))
    groups = sorted({r["comparison_group"] for r in comp})
    for group in groups:
        rows = [r for r in comp if r["comparison_group"] == group]
        ax.scatter([r.get("hold_proximity_score") for r in rows], [r.get("paired_support") for r in rows], label=group, s=48)
    ax.set_xlabel("hold proximity score"); ax.set_ylabel("minimum paired support ratio"); ax.set_title("RF-3 HOLD versus ambiguity near zero"); ax.legend(fontsize=7)
    save(fig, "RF-3_confirmed_hold_vs_ambiguity.png")

    fig, ax = plt.subplots(figsize=(8, 4.6))
    configs = sorted({r["config_id"] for r in d3}); ym = {c: i for i, c in enumerate(configs)}
    for label in ORDER:
        rows = [r for r in d3 if r["corrected_class"] == label]
        if rows: ax.scatter([r["generated_s2"] for r in rows], [ym[r["config_id"]] for r in rows], color=COLORS[label], label=label, s=52)
    ax.set_xscale("log"); ax.set_yticks(range(len(configs)), [c.split("_")[-1] for c in configs]); ax.set_xlabel(r"interpolated $s^2$"); ax.set_ylabel("config"); ax.set_title("RF-4 D3 boundary candidates and outcomes"); ax.legend(ncol=4, fontsize=8)
    save(fig, "RF-4_d3_boundary_outcomes.png")

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for label in ("WIDEN", "HOLD", "SHRINK", "AMBIGUOUS"):
        values = [r["paired_support"] for r in d2 if r["class"] == label and r.get("paired_support") is not None]
        if values: ax.hist(values, bins=12, alpha=.45, label=label, color=COLORS[label])
    ax.set_xlabel("minimum paired support ratio"); ax.set_ylabel("state count"); ax.set_title("RF-5 D2 paired-support distributions"); ax.legend(fontsize=8)
    save(fig, "RF-5_support_margin_distributions.png")

    statuses = ["SUPPORTED", "WEAK", "UNSUPPORTED", "NOT APPLICABLE"]
    cmap = {"SUPPORTED": "#52A675", "WEAK": "#E6B34A", "UNSUPPORTED": "#D9695F", "NOT APPLICABLE": "#D8D8D8"}
    cols = ["Three-action", "Two-direction+abstain", "Continuous"]
    fig, ax = plt.subplots(figsize=(8.4, 5.1)); ax.axis("off")
    table = ax.table(cellText=[[r[c] for c in cols] for r in matrix], rowLabels=[r["Evidence"] for r in matrix], colLabels=cols, loc="center", cellLoc="center")
    table.auto_set_font_size(False); table.set_fontsize(8); table.scale(1, 1.55)
    for i, r in enumerate(matrix, start=1):
        for j, c in enumerate(cols): table[(i, j)].set_facecolor(cmap[r[c]])
    ax.set_title("RF-6 Action-space evidence matrix", pad=16); save(fig, "RF-6_action_space_evidence_matrix.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.6)); ax.axis("off")
    boxes = [(0.08, .68, "Corrected D2 + D3 evidence"), (.38, .68, "HOLD independently abundant?\nNo: 3 confirmed; 2/14 targeted"), (.68, .68, "Three-action route\nREJECT"), (.38, .25, "W/S confirmed and ambiguity\nmeaningfully safety-relevant?\nYes: W=12, S=10, D3 A=10"), (.68, .25, "M3-RF-B\nWIDEN / SHRINK + ABSTAIN")]
    for x0, y0, txt in boxes:
        ax.text(x0, y0, txt, transform=ax.transAxes, ha="center", va="center", fontsize=10, bbox={"boxstyle": "round,pad=.55", "facecolor": "#EAF2F8", "edgecolor": "#2878B5"})
    ax.annotate("", xy=(.29, .68), xytext=(.20, .68), xycoords="axes fraction", arrowprops={"arrowstyle": "->"})
    ax.annotate("", xy=(.60, .68), xytext=(.51, .68), xycoords="axes fraction", arrowprops={"arrowstyle": "->"})
    ax.annotate("", xy=(.44, .35), xytext=(.44, .55), xycoords="axes fraction", arrowprops={"arrowstyle": "->"})
    ax.annotate("", xy=(.60, .25), xytext=(.51, .25), xycoords="axes fraction", arrowprops={"arrowstyle": "->"})
    ax.set_title("RF-7 Reformulation decision tree"); save(fig, "RF-7_reformulation_decision_tree.png")


def documents(manifest: dict, audit: dict, comp: list[dict], decision: dict, matrix: list[dict]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "M3_RF_Action_Space_Reformulation_Task.md").write_text("""# M3-RF Corrected Action-Space Reformulation Review

This executed review is zero-simulator and reads only the frozen corrected ER-1, M3-D, D2, and D3 artifacts. It prohibits a third HOLD search, classifier/threshold changes, controller trials, rarity shift, and M3-Q. Historical M3-G/BV2/CA/PF artifacts are retained but are not corrected empirical evidence.
""", encoding="utf-8")
    causes = decision["ambiguity"]["causes"]
    (DOCS / "M3_RF_Corrected_Evidence_Audit.md").write_text(f"""# M3-RF Corrected Evidence Audit

## Provenance

The source manifest locks {len(manifest['items'])} read-only artifacts. Required corrected tags resolve: ER1 `{manifest['parent_lineage']['ER1']}`, M3-v2 `{manifest['parent_lineage']['M3-v2']}`, and M3-D-v1 `{manifest['parent_lineage']['M3-D-v1']}`.

## Deduplicated state universe

- Raw observations: {audit['raw_observation_count']}
- Unique frozen state identities: {audit['unique_state_count']}
- Duplicate observations removed: {audit['duplicate_state_count']}
- Identities observed in more than one source stage: {audit['duplicate_identity_count']}

## HOLD supply and D3 enrichment

- D2 raw candidate HOLD prevalence: 5/72 (6.94%).
- D2 independent-confirmation HOLD prevalence: 3/27 (11.11%), explicitly selection-conditioned and not a population prevalence estimate.
- D3 boundary-targeted provisional HOLD prevalence: 2/14 (14.29%).
- D3 preregistered target: at least 10/14 (71.43%); absolute shortfall: 57.14 percentage points.

The D3 test therefore rejects the hypothesis that the frozen thin transition-boundary sampling design would strongly enrich HOLD. No target was changed after observing this result.
""", encoding="utf-8")
    group_counts = Counter(row["comparison_group"] for row in comp)
    (DOCS / "M3_RF_Ambiguity_vs_HOLD_Audit.md").write_text(f"""# M3-RF Ambiguity versus HOLD Audit

The comparison table contains the requested categories: {dict(group_counts)}. D2 contains three independently confirmed HOLD states, while two provisional D2 HOLD states became ambiguous at confirmation. D3 contributes two provisional HOLD outcomes and ten ambiguous outcomes.

For the D3 boundary sample, ambiguity is the dominant near-zero outcome (10/14), not a stable third action class. Recorded D3 ambiguity causes are `{causes}`. The comparison CSV retains `r_w`, `r_s`, paired support/SE, direction margin, hold-proximity score, and ESS for every relevant row.

Interpretation is descriptive only: strict corrected evidence rules identify a broad uncertainty/transition region around the nominal HOLD boundary. This review does not retune the classifier or relabel any state.
""", encoding="utf-8")
    matrix_lines = "\n".join(f"| {r['Evidence']} | {r['Three-action']} | {r['Two-direction+abstain']} | {r['Continuous']} |" for r in matrix)
    (DOCS / "M3_RF_Action_Space_Decision.md").write_text(f"""# M3-RF Action-Space Decision

## Decision

**Primary route: M3-RF-B — reformulate to directional WIDEN/SHRINK + ABSTAIN.**

Confirmed D2 evidence provides WIDEN=12 and SHRINK=10. HOLD is not sufficiently available as a balanced action: only three D2 states independently confirm and D3's preregistered boundary refinement produced 2 HOLD versus 10 ambiguous outcomes. The decision retains every negative result and requires no classifier, threshold, event-semantics, or parent-gate change.

ABSTAIN is not a trained HOLD class. It is a protocol decision triggered by insufficient paired support, near-zero gradient confidence, or classifier ambiguity; deployment uses BASE/no adaptation.

## Three-action identifiability

| Criterion | Result |
|---|---|
| All W/H/S exist under corrected semantics | PASS |
| HOLD independently reproducible | MIXED |
| HOLD not dominated by ambiguity at boundary | FAIL |
| Diverse HOLD without post-hoc search | FAIL |
| No weakening of classifier evidence | PASS |

Overall: **not defensible** as a balanced three-action controller benchmark. RFA is not allowed: D3 already tested the coarse-grid explanation and no untested artifact-supported explanation remains.

## Evidence matrix

| Evidence | Three-action | Two-direction+abstain | Continuous |
|---|---|---|---|
{matrix_lines}

RFA is unsupported; RFC is weak (transition paths suggest continuity but no continuous-action protocol is yet validated); RFD is weak because W/S availability is established; RFE is not selected because RF-B is already preregistrable. The next authorized action is a separately preregistered M3-DS directional-sign benchmark with a predeclared abstention policy. Rarity shift and M3-Q remain blocked.
""", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    universe, audit, d3 = build_universe()
    manifest = source_manifest()
    matrix = status_matrix()
    comp = comparison_rows(universe)
    decision = route_decision(audit, d3, comp)
    csv_write(OUT / "m3rf_corrected_state_universe.csv", universe)
    csv_write(OUT / "m3rf_hold_ambiguity_comparison.csv", comp)
    csv_write(OUT / "m3rf_action_space_evidence.csv", matrix)
    (OUT / "m3rf_source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "m3rf_route_decision.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    figures(universe, d3, matrix)
    documents(manifest, audit, comp, decision, matrix)
    print(json.dumps({"status": decision["status"], "primary_route": decision["primary_route"], **audit}, indent=2))


if __name__ == "__main__":
    main()
