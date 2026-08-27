"""M3-BV2 B3 -- construct the Axis A (Decision) benchmark candidates and
deterministic 8W/8H/8S selection (task Sec. 10/11/15, construction lock
"axis_a_decision").

Reuses the BV-v0 candidate characterization recorded at B2.  Classification
and selection replay the BV-v0 locked rule verbatim (same eligibility,
same stability rule, same coverage rule, same sort), so the expected result
is bit-identical to the recorded BV-v0 8/8/8 selection -- cross-checked
against results/phase_m3bv/reference/m3bv_analysis.json (prior
characterization output; determinism check only).

Writes: results/phase_m3bv2/decision_analysis.json
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
BV0_ANALYSIS = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_analysis.json"
DEST = REPO / "results" / "phase_m3bv2" / "decision_analysis.json"

MIN_STABLE = 0.8
MIN_COVERAGE_PER_CLASS = 4
MAX_PER_CONFIG_PER_CLASS = 2
N_PER_CLASS = 8


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def med(xs):
    return float(statistics.median(xs))


def classify(pool: dict, st_entries: dict) -> dict:
    """Replay the frozen BV-v0 B5 classification rule (unchanged)."""
    classified = {}
    for key, r in pool["reference_fields"].items():
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
            rec["class"] = label
        classified[key] = rec
    return classified


def pick_class(cands: list, n: int, max_per_config: int) -> list:
    """Verbatim BV-v0 locked selection algorithm (parameterized N / cap)."""
    by_cfg = {}
    for c in cands:
        by_cfg.setdefault(c["config_id"], []).append(c)
    sel = []
    for cid in sorted(by_cfg):
        if len(sel) >= n:
            break
        take = min(max_per_config, n - len(sel))
        grp = sorted(by_cfg[cid],
                     key=lambda c: (-c["stability_fraction"],
                                    -(c["margin_Delta_dir"]
                                      if c["margin_Delta_dir"] is not None
                                      else -1.0),
                                    c["s2"]))
        for c in grp[:take]:
            if len(sel) < n:
                sel.append(c)
    if len(sel) < n:
        taken_key = {(c["config_id"], c["s2"]) for c in sel}
        rest = [c for c in cands
                if (c["config_id"], c["s2"]) not in taken_key]
        rest.sort(key=lambda c: (-c["stability_fraction"],
                                 -(c["margin_Delta_dir"]
                                   if c["margin_Delta_dir"] is not None
                                   else -1.0),
                                 c["config_id"], c["s2"]))
        for c in rest:
            if len(sel) < n:
                sel.append(c)
            else:
                break
    sel.sort(key=lambda c: (c["config_id"], c["s2"]))
    return sel


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    stab = json.loads(STAB.read_text(encoding="utf-8"))
    st_entries = stab["entries"]

    classified = classify(pool, st_entries)

    counts = {}
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        el = [k for k, r in classified.items()
              if r["class"] == cls and r["eligible"]]
        counts[cls] = {"eligible": len(el), "states": el}

    # ---------------- deterministic selection (B3) ------------------------
    selection = {cls: pick_class(
        [classified[k] for k in counts[cls]["states"]],
        N_PER_CLASS, MAX_PER_CONFIG_PER_CLASS)
        for cls in ("WIDEN", "SHRINK", "HOLD")}

    # ---------------- cross-check vs BV-v0 recorded selection --------------
    bv0_sel = {}
    if BV0_ANALYSIS.exists():
        a0 = json.loads(BV0_ANALYSIS.read_text(encoding="utf-8"))
        bv0_sel = {cls: {(s["config_id"], s["s2"])
                         for s in a0["selection"][cls]}
                   for cls in ("WIDEN", "SHRINK", "HOLD")}
    replay_identical = all(
        {(c["config_id"], c["s2"]) for c in selection[cls]} == bv0_sel[cls]
        for cls in ("WIDEN", "SHRINK", "HOLD"))

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

    # ---------------- per-selected-state record ----------------------------
    ref_arm_of = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}
    sel_keys = sorted(
        {(c["config_id"], c["s2"], cls)
         for cls, lst in selection.items() for c in lst},
        key=lambda t: (t[0], t[1]))
    freeze_selection = []
    for cid, s2, cls in sel_keys:
        key = f"{cid}|{s2}"
        rec = classified[key]
        reps = st_entries[key]["replicates"]
        m2 = {"base": [r["M2"]["base"] for r in reps],
              "widen": [r["M2"]["widen"] for r in reps],
              "shrink": [r["M2"]["shrink"] for r in reps]}
        freeze_selection.append({
            "state_key": {"config_id": cid, "s2": s2},
            "class": cls,
            "oracle_action": rec["oracle_action"],
            "margin_Delta_dir": rec["margin_Delta_dir"],
            "stability_fraction": rec["stability_fraction"],
            "stable": rec["stable"],
            "support": rec["support"],
            "reference_median_M2": {a: med(xs) for a, xs in m2.items()},
            "replicate_M2": m2,
        })

    # ---------------- gates -------------------------------------------------
    d1_pass = all(len(selection[cls]) == N_PER_CLASS
                  for cls in ("WIDEN", "SHRINK", "HOLD"))
    d2_pass = all(
        fs["stable"] and fs["stability_fraction"] >= MIN_STABLE
        for fs in freeze_selection)
    # HOLD indifference-stability rule is embedded in hold_stable; assert it
    hold_ok = all(
        fs["class"] != "HOLD" or
        (fs["stability_fraction"] >= MIN_STABLE and fs["stable"])
        for fs in freeze_selection)
    d2_pass = bool(d2_pass and hold_ok)
    coverage_pass = all(coverage[cls]["coverage_ok"]
                        for cls in ("WIDEN", "SHRINK", "HOLD"))

    analysis = {
        "schema_version": "raretopo-m3bv2-decision-analysis-v0",
        "document_type": "Axis A (Decision) benchmark candidates: eligibility "
                         "counts, deterministic 8W/8H/8S selection, D-gates",
        "stage": "B3_decision_benchmark",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": {
            "candidate_pool": POOL.relative_to(REPO).as_posix(),
            "headline_stability": STAB.relative_to(REPO).as_posix(),
            "reuse_record": "results/phase_m3bv2/reuse_record.json",
            "reused_as": "prior characterization data (B2 reuse record)",
        },
        "eligibility_counts": {cls: counts[cls]["eligible"]
                               for cls in ("WIDEN", "SHRINK", "HOLD")},
        "selection": {cls: [{"config_id": c["config_id"], "s2": c["s2"],
                             "stability_fraction":
                                 c["stability_fraction"],
                             "margin_Delta_dir": c["margin_Delta_dir"]}
                            for c in lst]
                      for cls, lst in selection.items()},
        "selection_sizes": {cls: len(lst)
                            for cls, lst in selection.items()},
        "coverage": coverage,
        "freeze_selection": freeze_selection,
        "bv0_replay_crosscheck_identical": replay_identical,
        "gates": {
            "D1_diversity_8_8_8": d1_pass,
            "D2_stability_all_selected_ge_0.80": d2_pass,
            "coverage_pass": coverage_pass,
            "D0_validity": "see reuse_record.json (source hashes, legality, "
                           "M2=sum L) + test_m3bv2_* suite; full pytest",
        },
        "no_controller_output_used": True,
    }
    DEST.write_text(json.dumps(analysis, indent=1), encoding="utf-8")

    print("eligibility:", json.dumps({cls: counts[cls]["eligible"]
                                      for cls in ("WIDEN", "SHRINK", "HOLD")}))
    print("selection sizes:", json.dumps({cls: len(selection[cls])
                                          for cls in ("WIDEN", "SHRINK",
                                                      "HOLD")}))
    print("coverage:", json.dumps(
        {cls: coverage[cls]["n_configs"]
         for cls in ("WIDEN", "SHRINK", "HOLD")}))
    print("bv0 replay identical:", replay_identical)
    print("D1:", d1_pass, "| D2:", d2_pass, "| coverage:", coverage_pass)
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0 if (d1_pass and d2_pass and coverage_pass) else 3


if __name__ == "__main__":
    import sys
    raise SystemExit(main())