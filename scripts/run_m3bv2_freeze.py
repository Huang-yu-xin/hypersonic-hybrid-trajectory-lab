"""M3-BV2 B9 -- generate the Decision and Value benchmark freeze artifacts
from the B3/B4-B7 analysis outputs (task Sec. 21, construction lock
"outputs").

Creates:
  docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.md|.json
  docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.md|.json
  configs/phase_m3bv2/m3bv2_decision_benchmark.json
  configs/phase_m3bv2/m3bv2_value_benchmark.json

Each freeze JSON records freeze_sha256_of_body_above computed over the JSON
with that field stripped (json.dumps indent=1) -- the repo-standard
self-consistency pattern (same as M3-D freeze).

Freeze gates must already be PASS in the analysis files; the script refuses
to write a freeze when a gate is FALSE.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
REUSE = REPO / "results" / "phase_m3bv2" / "reuse_record.json"
DAN = REPO / "results" / "phase_m3bv2" / "decision_analysis.json"
VAN = REPO / "results" / "phase_m3bv2" / "value_analysis.json"

FREEZE_D = REPO / "docs" / "phase_m3bv2" / "M3_BV2_Decision_Benchmark_Freeze.json"
FREEZE_DM = REPO / "docs" / "phase_m3bv2" / "M3_BV2_Decision_Benchmark_Freeze.md"
FREEZE_V = REPO / "docs" / "phase_m3bv2" / "M3_BV2_Value_Benchmark_Freeze.json"
FREEZE_VM = REPO / "docs" / "phase_m3bv2" / "M3_BV2_Value_Benchmark_Freeze.md"
CFG_D = REPO / "configs" / "phase_m3bv2" / "m3bv2_decision_benchmark.json"
CFG_V = REPO / "configs" / "phase_m3bv2" / "m3bv2_value_benchmark.json"


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_id_lookup(pool: dict) -> dict:
    return {(s["config_id"], s["s2"]): s["state_id"]
            for s in pool["states_legal"]}


def body_hash(doc: dict) -> str:
    body = {k: v for k, v in doc.items() if k != "freeze_sha256_of_body_above"}
    return hashlib.sha256(json.dumps(body, indent=1, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def write_freeze(doc: dict, path: Path) -> str:
    h = body_hash(doc)
    doc["freeze_sha256_of_body_above"] = h
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return h


def parent_tags() -> dict:
    return {
        "m3g_v1": "RareTopo-M3-G-v1 (peeled commit 4505a36)",
        "m3d_v0": "RareTopo-M3-D-v0 (7bd58c5992615b8579b1814a3a3fcbea3cda9659)",
        "m3bv_v0": "RareTopo-M3-BV-v0 (frozen negative benchmark-design "
                   "result, annotated tag on commit 1eea183)",
    }


def source_hashes() -> dict:
    return {
        "candidate_pool": sha256(POOL),
        "headline_stability": sha256(STAB),
        "reuse_record": sha256(REUSE),
    }


SEAL = [
    "no state replacement",
    "no metric change",
    "no functional change",
    "no margin change",
    "no controller-informed amendment",
]


def main() -> int:
    dan = json.loads(DAN.read_text(encoding="utf-8"))
    van = json.loads(VAN.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    sids = state_id_lookup(pool)

    d_gates = dan["gates"]
    if not (d_gates["D1_diversity_8_8_8"] and d_gates["D2_stability_all_selected_ge_0.80"]
            and d_gates["coverage_pass"]):
        print("FATAL: decision gates not all PASS; no freeze", file=__import__(
            "sys").stderr)
        return 3
    v_gates = van["gates"]
    if not (v_gates["V0"] and v_gates["V2"] and v_gates["V3"]):
        print("FATAL: value gates not all PASS; no freeze", file=__import__(
            "sys").stderr)
        return 4

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    git = _git()

    # ---------------- Decision freeze --------------------------------------
    d_states = []
    for f in dan["freeze_selection"]:
        s2 = f["state_key"]["s2"]
        d_states.append({
            "state_key": f["state_key"],
            "state_id": sids[(f["state_key"]["config_id"], s2)],
            "class": f["class"],
            "oracle_action": f["oracle_action"],
            "margin_Delta_dir": f["margin_Delta_dir"],
            "stability_fraction": f["stability_fraction"],
            "support": f["support"],
            "reference_median_M2": f["reference_median_M2"],
        })
    d_doc = {
        "schema_version": "raretopo-m3bv2-decision-freeze-v0",
        "document_type": "M3-BV2 Axis A (Decision) benchmark freeze: frozen "
                         "8W/8H/8S state set for WIDEN/HOLD/SHRINK action-"
                         "correctness evaluation; NO controller run before "
                         "this freeze commit",
        "stage": "B9_decision_freeze",
        "frozen_at_utc": now,
        "git_commit": git,
        "parent_tags": parent_tags(),
        "source_hashes": source_hashes(),
        "benchmark_semantics": {
            "axis": "A_decision",
            "structure": {"WIDEN": 8, "HOLD": 8, "SHRINK": 8},
            "eligibility_rule": "frozen label (support + margin >= 0.05 "
                                "embedded) AND headline stability >= 0.80; "
                                "HOLD adds the frozen indifference-stability "
                                "rule",
            "selection_rule": "task Sec. 11 + construction lock "
                              "axis_a_decision (deterministic, coverage-aware, "
                              "config_id ascending, stability/margin/s2 sort)",
            "headline_budget": "100000/arm x 8 matched replicates (frozen "
                               "final_eval_n)",
            "reference_budget": "500000/arm x 20 CRN batches (prior "
                                "characterization, B2 reuse record)",
        },
        "selection_executed": dan["selection"],
        "selection_sizes": dan["selection_sizes"],
        "coverage": dan["coverage"],
        "gates": {
            "D0_validity": "B2 reuse record (source hashes, legality, "
                           "M2=sum L) + test_m3bv2_* suite + full pytest",
            "D1_diversity_8_8_8": d_gates["D1_diversity_8_8_8"],
            "D2_stability_all_selected_ge_0.80":
                d_gates["D2_stability_all_selected_ge_0.80"],
            "coverage_pass": d_gates["coverage_pass"],
        },
        "states": d_states,
        "online_trials_run_before_this_freeze": 0,
        "controller_runs_on_bv2": 0,
        "seal_declaration": SEAL,
    }
    h_d = write_freeze(d_doc, FREEZE_D)
    FREEZE_DM.write_text(decision_md(d_doc, dan), encoding="utf-8")

    # ---------------- Value freeze -----------------------------------------
    v_states = []
    for f in van["freeze_selection"]:
        s2 = f["state_key"]["s2"]
        v_states.append({
            "state_key": f["state_key"],
            "state_id": sids[(f["state_key"]["config_id"], s2)],
            "class": f["class"],
            "oracle_action": f["oracle_action"],
            "margin_Delta_dir": f["margin_Delta_dir"],
            "stability_fraction": f["stability_fraction"],
            "reference_median_M2": f["reference_median_M2"],
            "state_J": f["state_J"],
        })
    v_doc = {
        "schema_version": "raretopo-m3bv2-value-freeze-v0",
        "document_type": "M3-BV2 Axis B (Value) benchmark freeze: frozen "
                         "12W/12S state set for adaptive WIDEN/SHRINK value "
                         "over one globally fixed scalar rule under the "
                         "unified functional; Oracle feasibility PASS required "
                         "before this freeze",
        "stage": "B9_value_freeze",
        "frozen_at_utc": now,
        "git_commit": git,
        "parent_tags": parent_tags(),
        "source_hashes": source_hashes(),
        "unified_functional": van["unified_functional"],
        "benchmark_semantics": {
            "axis": "B_value",
            "structure": {"WIDEN": 12, "SHRINK": 12},
            "no_hold_states": True,
            "hold_as_fixed_comparator": True,
            "eligibility_rule": "frozen label WIDEN/SHRINK (statistical "
                                "support AND direction margin >= 0.05 "
                                "embedded) AND headline stability >= 0.80",
            "selection_rule": "task Sec. 13/14 + construction lock "
                              "axis_b_value (deterministic, coverage-aware, "
                              ">=4 configs/class, <=3 states/config/class)",
            "oracle_per_state": "frozen reference action arm",
            "fixed_policies": ["ALWAYS_WIDEN", "ALWAYS_SHRINK",
                               "ALWAYS_HOLD"],
            "best_fixed_definition": "argmin over the fixed policies of J "
                                     "(same functional as Oracle headroom)",
            "headline_budget": "100000/arm x 8 matched replicates (frozen "
                               "final_eval_n)",
            "reference_budget": "500000/arm x 20 CRN batches (prior "
                                "characterization, B2 reuse record)",
        },
        "selection_executed": van["selection"],
        "selection_sizes": van["selection_sizes"],
        "coverage": van["coverage"],
        "margin_diagnostic_ge_0.10": van["margin_diagnostic_ge_0.10"],
        "fixed_rule_tradeoff_V1": van["fixed_rule_tradeoff_V1"],
        "oracle_feasibility_V2": van["oracle_feasibility_V2"],
        "opposite_class_regret_V3": van["opposite_class_regret_V3"],
        "gates": {
            "V0": v_gates["V0"],
            "V1_diagnostic": v_gates["V1_diagnostic"],
            "V2_oracle_feasibility": v_gates["V2"],
            "V3_opposite_class_regret": v_gates["V3"],
        },
        "states": v_states,
        "online_trials_run_before_this_freeze": 0,
        "controller_runs_on_bv2": 0,
        "seal_declaration": SEAL,
    }
    h_v = write_freeze(v_doc, FREEZE_V)
    FREEZE_VM.write_text(value_md(v_doc, van), encoding="utf-8")

    # ---------------- benchmark configs -------------------------------------
    cfg_d = {
        "schema_version": "raretopo-m3bv2-decision-benchmark-v0",
        "axis": "A_decision",
        "freeze_doc": "docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.json",
        "n_each_class": 8,
        "states": [{k: s[k] for k in ("state_key", "state_id", "class",
                                      "oracle_action", "margin_Delta_dir",
                                      "stability_fraction")}
                   for s in d_states],
        "evaluation_budget": "headline 100000/arm x 8 matched replicates "
                             "(frozen final_eval_n)",
        "estimator_frozen": "M2 = mean(w^2), w = exp(logp-logq)*1_A",
        "controller_runs_on_bv2": 0,
    }
    cfg_v = {
        "schema_version": "raretopo-m3bv2-value-benchmark-v0",
        "axis": "B_value",
        "freeze_doc": "docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.json",
        "n_each_class": 12,
        "states": [{k: s[k] for k in ("state_key", "state_id", "class",
                                      "oracle_action", "margin_Delta_dir",
                                      "stability_fraction")}
                   for s in v_states],
        "unified_functional": van["unified_functional"],
        "evaluation_budget": "headline 100000/arm x 8 matched replicates "
                             "(frozen final_eval_n)",
        "estimator_frozen": "M2 = mean(w^2), w = exp(logp-logq)*1_A",
        "controller_runs_on_bv2": 0,
    }
    CFG_D.write_text(json.dumps(cfg_d, indent=1, ensure_ascii=False),
                     encoding="utf-8")
    CFG_V.write_text(json.dumps(cfg_v, indent=1, ensure_ascii=False),
                     encoding="utf-8")

    print("decision freeze:", FREEZE_D.relative_to(REPO),
          "body sha256:", h_d)
    print("value freeze:  ", FREEZE_V.relative_to(REPO),
          "body sha256:", h_v)
    print(f"[saved] {CFG_D.relative_to(REPO)}")
    print(f"[saved] {CFG_V.relative_to(REPO)}")
    return 0


def decision_md(doc: dict, dan: dict) -> str:
    rows = "\n".join(
        f"| {s['state_key']['config_id']} | {s['state_key']['s2']:g} | "
        f"{s['state_id']} | {s['class']} | "
        f"{s['margin_Delta_dir'] if s['margin_Delta_dir'] is not None else 'n/a':} | "
        f"{s['stability_fraction']} |"
        for s in doc["states"])
    return f"""# M3-BV2 Decision Benchmark Freeze (Axis A)

> **Frozen:** {doc['frozen_at_utc']} UTC ｜ commit `{doc['git_commit']}`
> **Status:** 8 WIDEN / 8 HOLD / 8 SHRINK — decision-correctness benchmark; **no adaptive-value claim from this axis**.
> **Seal:** after this freeze: {', '.join(SEAL)}.
> Freeze body sha256: `{doc['freeze_sha256_of_body_above']}`

## Gates

| Gate | Result |
|---|---|
| D0 validity (BV-v0 tag, task/lock-before-science, source hashes, legality, M2=sum L, no controller leakage) | PASS (see B2 reuse record + test suite) |
| D1 diversity 8/8/8 | {doc['gates']['D1_diversity_8_8_8']} |
| D2 stability >= 0.80 every state + HOLD indifference rule | {doc['gates']['D2_stability_all_selected_ge_0.80']} |
| config coverage (>=4 configs/class, <=2 states/config/class) | {doc['gates']['coverage_pass']} |

## Selected states (24)

| config | s2 | state_id | class | margin | stability |
|---|---|---|---|---|---|
{rows}

## Semantics

- Eligibility: frozen label (statistical support + direction margin >= 0.05) AND headline stability >= 0.80; HOLD adds the frozen +/-3% indifference + headline +/-5% rule.
- Selection: deterministic, coverage-aware, config_id ascending, (stability desc, margin desc, s2 asc) — verbatim replay of the BV-v0 locked rule (cross-check identical).
- Budgets: reference 500k/arm x 20 CRN batches (prior characterization, B2 reuse); headline 100k/arm x 8 matched replicates.
- Controller runs on BV2: **0**.
"""


def value_md(doc: dict, van: dict) -> str:
    rows = "\n".join(
        f"| {s['state_key']['config_id']} | {s['state_key']['s2']:g} | "
        f"{s['state_id']} | {s['class']} | "
        f"{s['margin_Delta_dir'] if s['margin_Delta_dir'] is not None else 'n/a':} | "
        f"{s['stability_fraction']} |"
        for s in doc["states"])
    uf = doc["unified_functional"]
    return f"""# M3-BV2 Value Benchmark Freeze (Axis B)

> **Frozen:** {doc['frozen_at_utc']} UTC ｜ commit `{doc['git_commit']}`
> **Status:** 12 WIDEN / 12 SHRINK — adaptive-value benchmark; Oracle feasibility PASS required before this freeze.
> **Seal:** after this freeze: {', '.join(SEAL)}.
> Freeze body sha256: `{doc['freeze_sha256_of_body_above']}`

## Unified functional

```
J(pi) = median_state [ median_replicate log( M2(pi) / M2(BASE) ) ]
BestFixed = argmin f in {{ALWAYS_WIDEN, ALWAYS_SHRINK, ALWAYS_HOLD}} J(f)
G_Oracle = J(BestFixed) - J(Oracle)
```

## Gates

| Gate | Result |
|---|---|
| V0 validity (12W/12S deterministic, legal, stable, margin >= 0.05, coverage, no controller) | {doc['gates']['V0']} |
| V1 fixed-rule tradeoff (diagnostic; weak flag = one fixed rule dominates both classes) | weak flag = {doc['fixed_rule_tradeoff_V1']['weak_flag_one_fixed_rule_dominates_both_classes']} |
| V2 Oracle feasibility (G_Oracle >= -log(0.95)) | {doc['gates']['V2_oracle_feasibility']} |
| V3 opposite-class regret (R_opp,W / R_opp,S >= 1.05) | {doc['gates']['V3_opposite_class_regret']} |

BestFixed = **{uf['best_fixed']}**; J(BestFixed) = {uf['J'][uf['best_fixed']]:.6f};
J(Oracle) = {uf['J']['ORACLE']:.6f}; G_Oracle = {uf['G_Oracle']:.6f};
equivalent ratio exp(-G) = {uf['equivalent_ratio_exp(-G)']:.5f} (threshold 0.95).

Opposite-class regret: R_opp,W = **{doc['opposite_class_regret_V3']['R_opp_W']:.4f}**,
R_opp,S = **{doc['opposite_class_regret_V3']['R_opp_S']:.4f}** (threshold 1.05).

## Selected states (24)

| config | s2 | state_id | class | margin | stability |
|---|---|---|---|---|---|
{rows}

## Semantics

- No HOLD states by design; ALWAYS_HOLD remains a fixed comparator (J(ALWAYS_HOLD) = 0 by construction).
- Eligibility: frozen label WIDEN/SHRINK (statistical support + direction margin >= 0.05 embedded) AND headline stability >= 0.80.
- Selection: deterministic (task Sec. 13/14), coverage >= 4 configs/class, <= 3 states/config/class; Oracle feasibility checked AFTER selection; no manual headroom selection.
- Budgets: reference 500k/arm x 20 CRN batches (prior characterization, B2 reuse); headline 100k/arm x 8 matched replicates.
- Controller runs on BV2: **0**.
"""


if __name__ == "__main__":
    import sys
    raise SystemExit(main())