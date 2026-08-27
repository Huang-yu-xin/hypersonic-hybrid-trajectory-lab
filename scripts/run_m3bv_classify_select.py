"""M3-BV B5+B6+B7 -- classify eligible/stable states, Oracle headroom
audit, and deterministic 8/8/8 benchmark selection (task Sec. 7/8/11/12/13/
15/16).

Inputs (all benchmark-only):
  results/phase_m3bv/reference/m3bv_candidate_pool.json      (B3 reference)
  results/phase_m3bv/reference/m3bv_headline_stability.json  (B4 headline)

Pipeline:
  B5  eligibility:
      WIDEN/SHRINK : frozen label WIDEN/SHRINK (embeds support >= 2x paired
                     SE AND direction margin >= 0.05)
                     AND realized-best fraction >= 0.8 at headline budget
      HOLD         : frozen label HOLD (reference indifference inside the
                     frozen +-3% hold window)
                     AND >= 0.8 headline replicates place both perturbation
                     arms within +-5% of BASE
  B6  Oracle headroom audit over the eligible+stable pool (diagnostic) and
      over the selected 24 states (authoritative BV-3): Oracle = frozen
      reference action; fixed policies ALWAYS_WIDEN/SHRINK/HOLD; BestFixed =
      fixed policy minimizing the global median (median over states of the
      per-state median over 8 replicates) of headline M2.
  B7  deterministic selection (locked rule):
      1. eligible+stable only; 2. >= 4 distinct configs per class and <= 2
      states per (config, class); 3. larger stability; 4. larger margin;
      5. (config_id, s2) ascending.  Configs processed in (config_id)
      ascending; within a config take up to 2 by (stability desc, margin
      desc, s2 asc); accumulate to 8; if short, fill from remaining eligible
      by the same sort.  No controller performance enters selection.

Writes: results/phase_m3bv/reference/m3bv_analysis.json
"""

from __future__ import annotations

import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
DEST = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_analysis.json"

MIN_STABLE = 0.8
MIN_COVERAGE_PER_CLASS = 4
MAX_PER_CONFIG_PER_CLASS = 2
N_PER_CLASS = 8
ORACLE_RATIO_MAX = 0.95
WINS_MIN = 16


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def med(xs):
    return float(statistics.median(xs))


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    stab = json.loads(STAB.read_text(encoding="utf-8"))
    if "reference_fields" not in pool:
        print("FATAL: B3 reference fields missing", file=__import__(
            "sys").stderr)
        return 2
    if "entries" not in stab:
        print("FATAL: B4 headline stability missing", file=__import__(
            "sys").stderr)
        return 2

    ref = pool["reference_fields"]
    st_entries = stab["entries"]

    # ---------------- B5: classify ----------------
    classified = {}
    for key, r in ref.items():
        cid, s2 = r["state_key"]["config_id"], r["state_key"]["s2"]
        label = r["oracle"]["oracle_action"]
        margin = r["oracle"].get("direction_margin_Delta_dir")
        st = st_entries[key]["stability"]
        rec = {
            "config_id": cid, "s2": s2,
            "oracle_action": label,
            "margin_Delta_dir": margin,
            "fraction_widen_best": st["fraction_widen_best"],
            "fraction_shrink_best": st["fraction_shrink_best"],
            "fraction_hold_indiff": st["fraction_hold_indiff"],
            "reference_ratios":
                r["oracle"].get("ratios") or r.get("ratios"),
            "support": r["oracle"].get("support"),
        }
        if label == "WIDEN":
            rec["eligible"] = bool(st["widen_stable"])
            rec["stable"] = bool(st["widen_stable"])
            rec["stability_fraction"] = st["fraction_widen_best"]
            rec["class"] = "WIDEN"
        elif label == "SHRINK":
            rec["eligible"] = bool(st["shrink_stable"])
            rec["stable"] = bool(st["shrink_stable"])
            rec["stability_fraction"] = st["fraction_shrink_best"]
            rec["class"] = "SHRINK"
        elif label == "HOLD":
            rec["eligible"] = bool(st["hold_stable"])
            rec["stable"] = bool(st["hold_stable"])
            rec["stability_fraction"] = st["fraction_hold_indiff"]
            rec["class"] = "HOLD"
        else:
            rec["eligible"] = False
            rec["stable"] = False
            rec["class"] = label          # REFERENCE_AMBIGUOUS
        classified[key] = rec

    counts = {}
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        el = [k for k, r in classified.items()
              if r["class"] == cls and r["eligible"]]
        counts[cls] = {"eligible": len(el), "states": el}

    # ---------------- BV-1 check ----------------
    bv1 = {cls: counts[cls]["eligible"] >= N_PER_CLASS
           for cls in ("WIDEN", "SHRINK", "HOLD")}
    if not all(bv1.values()):
        print("BV-1 FAIL:", json.dumps({k: v["eligible"]
                                        for k, v in counts.items()}))
        print("STOP benchmark construction (negative result); no selection.")
        return 3

    # ---------------- B7: deterministic selection ----------------
    def pick_class(cls):
        cands = [classified[k] for k in counts[cls]["states"]]
        by_cfg = {}
        for c in cands:
            by_cfg.setdefault(c["config_id"], []).append(c)
        sel = []
        # coverage pass: process configs in (config_id) ascending, take up
        # to MAX_PER_CONFIG_PER_CLASS per config
        for cid in sorted(by_cfg):
            if len(sel) >= N_PER_CLASS:
                break
            if len(sel) + MAX_PER_CONFIG_PER_CLASS > N_PER_CLASS:
                # would overflow the 8 cap: take only the remainder
                take = N_PER_CLASS - len(sel)
            else:
                take = MAX_PER_CONFIG_PER_CLASS
            grp = sorted(by_cfg[cid],
                         key=lambda c: (-c["stability_fraction"],
                                        -(c["margin_Delta_dir"]
                                          if c["margin_Delta_dir"]
                                          is not None else -1.0),
                                        c["s2"]))
            for c in grp[:take]:
                if len(sel) < N_PER_CLASS:
                    sel.append(c)
        # fill pass (only reached if the coverage pass could not fill 8)
        if len(sel) < N_PER_CLASS:
            taken_key = {(c["config_id"], c["s2"]) for c in sel}
            rest = [c for c in cands
                    if (c["config_id"], c["s2"]) not in taken_key]
            rest.sort(key=lambda c: (-c["stability_fraction"],
                                     -(c["margin_Delta_dir"]
                                       if c["margin_Delta_dir"]
                                       is not None else -1.0),
                                     c["config_id"], c["s2"]))
            for c in rest:
                if len(sel) < N_PER_CLASS:
                    sel.append(c)
                else:
                    break
        sel.sort(key=lambda c: (c["config_id"], c["s2"]))
        return sel

    selection = {cls: pick_class(cls) for cls in ("WIDEN", "SHRINK", "HOLD")}
    selected_keys = {(c["config_id"], c["s2"], cls)
                     for cls, lst in selection.items() for c in lst}

    coverage = {}
    for cls, lst in selection.items():
        cfgs = {}
        for c in lst:
            cfgs[c["config_id"]] = cfgs.get(c["config_id"], 0) + 1
        coverage[cls] = {
            "n_configs": len(cfgs), "per_config": cfgs,
            "coverage_ok":
                len(cfgs) >= MIN_COVERAGE_PER_CLASS
                and max(cfgs.values()) <= MAX_PER_CONFIG_PER_CLASS,
        }

    # ---------------- B6: Oracle audit ----------------
    # per selected state, per replicate M2 of: oracle arm, each fixed arm
    fixed_arms = {
        "ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
        "ALWAYS_HOLD": "base"}
    ref_arm_of = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}

    state_audit = {}
    for cid, s2, cls in sorted(selected_keys, key=lambda t: (t[0], t[1])):
        key = f"{cid}|{s2}"
        reps = st_entries[key]["replicates"]
        m2_oracle = [r["M2"][ref_arm_of[cls]] for r in reps]
        fixed_m2 = {f: [r["M2"][a] for r in reps]
                    for f, a in fixed_arms.items()}
        median_m2 = {f: med(xs) for f, xs in fixed_m2.items()}
        state_audit[key] = {
            "state_key": {"config_id": cid, "s2": s2}, "class": cls,
            "replicate_M2_oracle": m2_oracle,
            "median_M2_oracle": med(m2_oracle),
            "fixed_median_M2": median_m2,
            "replicate_ratios": {},     # vs each fixed policy
        }
        for f in fixed_arms:
            state_audit[key]["replicate_ratios"][f] = [
                float(o / x) for o, x in zip(m2_oracle, fixed_m2[f])]

    # BestFixed on the selected 24 states (frozen aggregation, same as V1-5)
    global_med = {}
    for f in fixed_arms:
        global_med[f] = med([state_audit[k]["fixed_median_M2"][f]
                             for k in state_audit])
    best_fixed = min(global_med, key=global_med.get)
    bf_arm_of = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
                 "ALWAYS_HOLD": "base"}

    per_state_ratio_vs_bf = {}
    wins = losses = ties = 0
    for k in sorted(state_audit):
        sa = state_audit[k]
        r = [sa["replicate_ratios"][best_fixed][i]
             for i in range(len(sa["replicate_M2_oracle"]))]
        per_state_ratio_vs_bf[k] = med(r)
        om = sa["median_M2_oracle"]
        bm = sa["fixed_median_M2"][best_fixed]
        if om < bm:
            wins += 1
        elif om > bm:
            losses += 1
        else:
            ties += 1
    oracle_global = med([state_audit[k]["median_M2_oracle"]
                         for k in state_audit])
    bf_global = global_med[best_fixed]
    oracle_ratio_median = med(list(per_state_ratio_vs_bf.values()))

    bv3 = {
        "best_fixed_policy": best_fixed,
        "best_fixed_global_median_M2": bf_global,
        "oracle_global_median_M2": oracle_global,
        "median_state_median_replicate_Oracle_over_BestFixed":
            oracle_ratio_median,
        "wins": wins, "losses": losses, "ties": ties,
        "of_states": len(state_audit),
        "ratio_gate_pass": bool(oracle_ratio_median <= ORACLE_RATIO_MAX),
        "wins_gate_pass": bool(wins >= WINS_MIN),
        "bv3_pass": bool(oracle_ratio_median <= ORACLE_RATIO_MAX
                         and wins >= WINS_MIN),
    }

    # strong target (report only)
    strong = {"oracle_over_best_fixed_le_0.90":
              bool(oracle_ratio_median <= 0.90)}

    analysis = {
        "schema_version": "raretopo-m3bv-analysis-v0",
        "record_schema_version": "raretopo-m3bv-v0",
        "stage": "B5_B6_B7_classify_audit_select",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "classification": {k: {kk: vv for kk, vv in v.items()
                               if kk not in ("support",)}
                           for k, v in classified.items()},
        "eligibility_counts": {cls: counts[cls]["eligible"]
                               for cls in ("WIDEN", "SHRINK", "HOLD")},
        "bv1": bv1,
        "selection": {cls: [{"config_id": c["config_id"], "s2": c["s2"],
                             "stability_fraction":
                                 c["stability_fraction"],
                             "margin_Delta_dir": c["margin_Delta_dir"]}
                            for c in lst]
                      for cls, lst in selection.items()},
        "selection_sizes": {cls: len(lst)
                            for cls, lst in selection.items()},
        "coverage": coverage,
        "oracle_audit": {
            "state_audit": state_audit,
            "per_state_ratio_vs_best_fixed": per_state_ratio_vs_bf,
            "fixed_global_medians": global_med,
            "bv3": bv3,
            "strong_report_only": strong,
        },
    }
    DEST.write_text(json.dumps(analysis, indent=1), encoding="utf-8")

    # ---------------- console summary ----------------
    print("eligibility:", json.dumps(
        {c: counts[c]["eligible"] for c in ("WIDEN", "SHRINK", "HOLD")}))
    print("BV-1:", json.dumps(bv1))
    print("selection sizes:", json.dumps(
        {c: len(selection[c]) for c in ("WIDEN", "SHRINK", "HOLD")}))
    print("coverage:", json.dumps(
        {c: coverage[c]["n_configs"] for c in ("WIDEN", "SHRINK", "HOLD")}))
    print("BestFixed:", best_fixed, "global M2 med:",
          round(bf_global, 6))
    print("Oracle global med:", round(oracle_global, 6),
          "ratio median:", round(oracle_ratio_median, 5))
    print("wins/losses/ties:", wins, "/", losses, "/", ties)
    print("BV-3:", "PASS" if bv3["bv3_pass"] else "FAIL", json.dumps(
        {k: bv3[k] for k in ("median_state_median_replicate_"
                             "Oracle_over_BestFixed",
                             "wins", "bv3_pass")}))
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())