"""M3-VA -- Adaptive-Value Headroom Audit (pure analysis; ZERO new simulator
runs; no controller/benchmark/rho changes; reads ONLY stored M3-G-v1
confirmatory results + stored M3-D Layer-A results).

Questions answered:
  1. Oracle vs globally best fixed rule: ratio, wins/losses/ties (global +
     per class), and whether Oracle itself passes the V1-5-style check.
  2. v1-vs-M3-D value decomposition into six groups with per-trial
     dM2 = M2(M3D) - M2(v1) and total attribution.
  3. Four explanatory questions (HOLD-accuracy vs M2 invariance, corrected
     HOLD margins, false-HOLD cost, BestFixed vs Oracle proximity).
  4. Counterfactual (read-only arithmetic): v1 without gate-caused
     false-HOLD, to arbitrate verdict B vs C.
  5. Three-way verdict A (benchmark headroom) / B (controller modeling) /
     C (uncertainty/false-HOLD policy first).

Existing M3-G-v1 claim and all existing result files are untouched.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np

from hyptraj.m3d.metrics import state_seed_medians, win_counts

REPO = Path(__file__).resolve().parents[1]
V1_BATCH = json.loads((REPO / "results" / "phase_m3g_v1" / "layer_a"
                       / "m3g_v1_confirmatory_v1.json").read_text(
                           encoding="utf-8"))
M3D_BATCH = json.loads((REPO / "results" / "phase_m3d" / "layer_a"
                        / "m3d_layer_a_v1.json").read_text(encoding="utf-8"))
DEST = REPO / "results" / "phase_m3va" / "summary" \
    / "m3va_headroom_audit.json"

FIXED_RULES = ("ALWAYS_WIDEN", "ALWAYS_SHRINK", "ALWAYS_HOLD")
FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "hold"}
ORACLE_ARM = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "hold"}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def state_med(by_state: dict) -> dict:
    return state_seed_medians({k: v for k, v in by_state.items()})


def per_state_values(recs, arm_or_fn, cls_of=None):
    """by_state[state] = list over seeds of M2 at arm_or_fn(rec)."""
    by = {}
    for r in recs:
        m2 = (float(r["arms"][arm_or_fn]["M2"]) if isinstance(arm_or_fn, str)
              else float(arm_or_fn(r)))
        by.setdefault(r["state_id"], []).append(m2)
    return by


def summary_block(med_vs: dict, med_ref: dict, subset_states=None):
    states = [s for s in med_vs if s in med_ref] if subset_states is None \
        else [s for s in subset_states if s in med_vs and s in med_ref]
    ratios = {s: med_vs[s] / med_ref[s] for s in states
              if med_ref[s] > 0}
    w, l, t = win_counts({s: med_vs[s] for s in states},
                         {s: med_ref[s] for s in states})
    return {"n_states": len(states),
            "median_ratio": float(median(ratios.values())) if ratios
            else None,
            "wins": w, "losses": l, "ties": t}


def v15_style_pass(block, ratio_max=0.95, wins_min=16):
    return bool(block["median_ratio"] is not None
                and block["median_ratio"] <= ratio_max
                and block["wins"] >= wins_min)


def main() -> int:
    recs = V1_BATCH["gated_records"]
    assert len(recs) == 192
    cls_of = {}
    for r in recs:
        cls_of.setdefault(r["state_id"], r["oracle_action"])
    states_by_cls = {"WIDEN": [], "SHRINK": [], "HOLD": []}
    for sid, c in cls_of.items():
        states_by_cls[c].append(sid)

    # ---------------------------------------------------------------- 1.
    # per-state seed medians for oracle and each fixed rule
    med_oracle = state_med(per_state_values(recs, "oracle"))
    med_rules = {}
    for rule in FIXED_RULES:
        med_rules[rule] = state_med(per_state_values(recs, FIXED_ARM[rule]))
    fixed_global = {rule: float(median(med_rules[rule].values()))
                    for rule in FIXED_RULES}
    best_fixed = min(fixed_global, key=fixed_global.get)

    per_rule = {}
    for rule in FIXED_RULES:
        blk = summary_block(med_oracle, med_rules[rule])
        per_rule[rule] = {**blk,
                          "rule_global_median": fixed_global[rule]}
    headline = per_rule[best_fixed]
    per_class = {}
    for c in ("WIDEN", "SHRINK", "HOLD"):
        per_class[c] = summary_block(med_oracle, med_rules[best_fixed],
                                     subset_states=states_by_cls[c])
    oracle_v1 = summary_block(med_oracle,
                              state_med(per_state_values(recs, "gate")))
    oracle_headroom_pct = 100.0 * (1.0 - headline["median_ratio"]) \
        if headline["median_ratio"] is not None else None

    # ---------------------------------------------------------------- 2.
    def m3d_deployed(r):
        a = r["gradient"]["action"]
        return ("WIDEN" if a == "WIDEN" else "SHRINK" if a == "SHRINK"
                else "HOLD")

    groups = {k: [] for k in ("corrected_hold", "false_hold_widen",
                              "false_hold_shrink", "unchanged_correct_widen",
                              "unchanged_correct_shrink", "other_unchanged")}
    for r in recs:
        o, g, m = r["oracle_action"], r["gain"]["final_action"], \
            m3d_deployed(r)
        d = float(r["arms"]["gradient"]["M2"]) - \
            float(r["arms"]["gate"]["M2"])
        if o == "HOLD" and m != "HOLD" and g == "HOLD":
            groups["corrected_hold"].append((r, d))
        elif o == "WIDEN" and g == "HOLD":
            groups["false_hold_widen"].append((r, d))
        elif o == "SHRINK" and g == "HOLD":
            groups["false_hold_shrink"].append((r, d))
        elif o == "WIDEN" and g == "WIDEN" and m == "WIDEN":
            groups["unchanged_correct_widen"].append((r, d))
        elif o == "SHRINK" and g == "SHRINK" and m == "SHRINK":
            groups["unchanged_correct_shrink"].append((r, d))
        else:
            groups["other_unchanged"].append((r, d))

    decomp = {}
    total_d = 0.0
    for k, rows in groups.items():
        ds = [d for _, d in rows]
        total_d += sum(ds)
        decomp[k] = {
            "n": len(rows),
            "dM2_sum": float(sum(ds)),
            "dM2_mean": float(np.mean(ds)) if ds else None,
            "dM2_median": float(median(ds)) if ds else None,
            "m3d_m2_median": float(median(float(r["arms"]["gradient"]["M2"])
                                           for r, _ in rows)) if rows
            else None,
            "v1_m2_median": float(median(float(r["arms"]["gate"]["M2"])
                                          for r, _ in rows)) if rows
            else None,
        }
    all_d = [r["arms"]["gradient"]["M2"] - r["arms"]["gate"]["M2"]
             for r in recs]
    decomp["overall"] = {"n": len(recs),
                         "dM2_sum": float(sum(all_d)),
                         "dM2_mean": float(np.mean(all_d)),
                         "dM2_median": float(median(all_d)),
                         "sum_check_ok": bool(
                             abs(sum(all_d) - total_d) < 1e-9)}
    gain_groups = {k: v["dM2_sum"] for k, v in decomp.items()
                   if k != "overall" and v["dM2_sum"] > 0}
    loss_groups = {k: v["dM2_sum"] for k, v in decomp.items()
                   if k != "overall" and v["dM2_sum"] < 0}

    # ---------------------------------------------------------------- 3.
    # corrected-HOLD per-trial action-value margins:
    # margin = (M2(acted arm M3-D) - M2(base)) / M2(base) on the 49 holds
    margins = []
    for r, d in groups["corrected_hold"]:
        base = float(r["arms"]["hold"]["M2"])
        acted = float(r["arms"]["gradient"]["M2"])
        if base > 0:
            margins.append((acted - base) / base)
    # false-HOLD (gate-caused vs inherited)
    fh_widen = groups["false_hold_widen"]
    carried = [r for r, _ in fh_widen
               if r["gain"]["gain_hold_reason"] in (
                   "HOLD_UNCERTAIN", "HOLD_LOW_ESS", "HOLD_INVALID")]
    gate_caused = [r for r, _ in fh_widen
                   if r["gain"]["gain_hold_reason"] == "HOLD_GAIN"]
    # net accounting
    corrected_total = decomp["corrected_hold"]["dM2_sum"]
    fh_total = decomp["false_hold_widen"]["dM2_sum"] \
        + decomp["false_hold_shrink"]["dM2_sum"]
    expl = {
        "corrected_hold_margin": {
            "n": len(margins),
            "mean": float(np.mean(margins)) if margins else None,
            "median": float(median(margins)) if margins else None,
            "p75": float(np.quantile(margins, 0.75)) if margins else None,
            "p95": float(np.quantile(margins, 0.95)) if margins else None,
            "max_abs": float(max(abs(x) for x in margins))
            if margins else None},
        "false_hold_on_widen": {
            "n_total": len(fh_widen),
            "n_inherited_uncertainty": len(carried),
            "n_gate_caused_hold_gain": len(gate_caused),
            "dM2_sum": decomp["false_hold_widen"]["dM2_sum"]},
        "false_hold_on_shrink": decomp["false_hold_shrink"],
        "net": {"corrected_hold_total_dM2": corrected_total,
                "false_hold_total_dM2": fh_total,
                "net_of_two": corrected_total + fh_total,
                "overall_dM2_sum": decomp["overall"]["dM2_sum"]},
        "best_fixed_vs_oracle": {
            "best_fixed_rule": best_fixed,
            "median_M2_bf_over_M2_oracle":
                1.0 / headline["median_ratio"]
                if headline["median_ratio"] else None,
            "headroom_pct_global": oracle_headroom_pct,
            "headroom_pct_per_class": {
                c: (100.0 * (1.0 - per_class[c]["median_ratio"])
                    if per_class[c]["median_ratio"] is not None else None)
                for c in ("WIDEN", "SHRINK", "HOLD")}},
    }

    # ------------------------------------------------- counterfactual
    # v1 without gate-caused false-HOLD: replace gate M2 with the WIDEN arm
    # value on the (if any) HOLD_GAIN-caused WIDEN losses, recompute V1-5.
    med_gate_cf = per_state_values(recs, "gate")
    for r, _ in groups["false_hold_widen"]:
        if r["gain"]["gain_hold_reason"] == "HOLD_GAIN":
            med_gate_cf[r["state_id"]][med_gate_cf[r["state_id"]].index(
                float(r["arms"]["gate"]["M2"]))] = \
                float(r["arms"]["widen"]["M2"])
    med_gate_cf = state_med(med_gate_cf)
    cf_block = summary_block(med_gate_cf, med_rules[best_fixed])
    counterfactual = {"v1_no_gate_caused_false_hold": {
        **cf_block, "v15_style_pass": v15_style_pass(cf_block)}}

    # ------------------------------------------------ supplementary
    # discovery-seed robustness: same analysis on M3-D Layer-A (2026..2033)
    recs_d = M3D_BATCH["records"]
    med_oracle_d = state_med(per_state_values(recs_d, "oracle"))
    med_rules_d = {}
    for rule in FIXED_RULES:
        med_rules_d[rule] = state_med(
            per_state_values(recs_d, FIXED_ARM[rule]))
    fixed_d = {rule: float(median(med_rules_d[rule].values()))
               for rule in FIXED_RULES}
    best_d = min(fixed_d, key=fixed_d.get)
    blk_d = summary_block(med_oracle_d, med_rules_d[best_d])
    supp = {"best_fixed_rule": best_d,
            "fixed_global_medians": fixed_d, "oracle_vs_best_fixed": blk_d,
            "v15_style_pass": v15_style_pass(blk_d)}

    # --------------------------------------------------------- verdict
    oracle_pass = v15_style_pass(headline)
    if not oracle_pass:
        verdict = ("A",
                   "Oracle itself fails the V1-5-style check on the frozen "
                   "benchmark -> benchmark adaptive headroom insufficient; "
                   "prioritize benchmark redesign")
    else:
        cf_pass = bool(counterfactual["v1_no_gate_caused_false_hold"][
            "v15_style_pass"])
        gate_loss_share = (
            decomp["false_hold_widen"]["dM2_sum"]
            + decomp["false_hold_shrink"]["dM2_sum"]) / \
            decomp["overall"]["dM2_sum"] \
            if decomp["overall"]["dM2_sum"] < 0 else 0.0
        if cf_pass and gate_loss_share > 0.5:
            verdict = ("C",
                       "Oracle has headroom; v1's deficit is dominated by "
                       "false-HOLD / uncertainty -> fix the gain-uncertainty "
                       "policy before curvature (M3-Q)")
        else:
            verdict = ("B",
                       "Oracle clearly passes V1-5 but v1 does not -> "
                       "controller action-value modeling insufficient; "
                       "M3-Q (curvature) is the sanctioned next step")

    payload = {
        "schema_version": "raretopo-m3va-headroom-audit-v0",
        "stage": "M3_VA_adaptive_value_headroom_audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "git_commit": _git(),
        "disclosure": {
            "new_simulator_scientific_calls": 0,
            "controller_changed": False, "benchmark_changed": False,
            "rho_changed": False,
            "existing_results_modified": False,
            "v1_claim_unchanged": True,
            "data_sources": [
                "results/phase_m3g_v1/layer_a/m3g_v1_confirmatory_v1.json",
                "results/phase_m3d/layer_a/m3d_layer_a_v1.json (suppl.)"]},
        "oracle_vs_best_fixed": {
            "best_fixed_rule": best_fixed,
            "fixed_rule_global_medians": fixed_global,
            "per_rule": per_rule,
            "headline": headline,
            "oracle_v1_style": oracle_v1,
            "v15_style_pass_oracle": oracle_pass,
            "per_class": per_class,
            "headroom_pct_global": oracle_headroom_pct,
            "headroom_pct_per_class": {
                c: (100.0 * (1.0 - per_class[c]["median_ratio"])
                    if per_class[c]["median_ratio"] is not None else None)
                for c in ("WIDEN", "SHRINK", "HOLD")}},
        "value_decomposition": decomp,
        "explanations": expl,
        "counterfactuals": counterfactual,
        "supplementary_discovery_seeds": supp,
        "verdict": {"decision": verdict[0], "reasoning": verdict[1]},
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[saved] {DEST.relative_to(REPO)}")
    print(f"oracle V1-5-style pass: {oracle_pass}  | verdict: {verdict[0]}")
    print("oracle vs best fixed:", {k: headline[k] for k in
                                    ("median_ratio", "wins", "losses",
                                     "ties")})
    print("per class:", {c: {k: per_class[c][k] for k in
                             ("median_ratio", "wins", "losses", "ties")}
                         for c in ("WIDEN", "SHRINK", "HOLD")})
    print("decomp sums:", {k: round(v["dM2_sum"], 6) for k, v in
                           decomp.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())