"""M3-BV2 B4/B5/B6/B7 -- construct the Axis B (Value) benchmark candidates,
deterministic 12W/12S selection, unified-functional BestFixed audit,
Oracle feasibility gate V2, opposite-class regret gate V3, and the
deterministic freeze-selection record (task Sec. 9/12/13/14/16/17/18/19,
construction lock "axis_b_value" / "unified_functional" / "value_gates").

Reuses the BV-v0 candidate characterization recorded at B2.

Unified functional (ONE functional for BestFixed AND Oracle headroom):

    J(pi) = median_state [ median_replicate log( M2(pi)/M2(BASE) ) ]
    BestFixed = argmin f in {ALWAYS_WIDEN, ALWAYS_SHRINK, ALWAYS_HOLD} J(f)
    G_Oracle = J(BestFixed) - J(Oracle)
    BV2-V2: G_Oracle >= -log(0.95)   (equivalent ratio exp(-G_Oracle) <= 0.95)
    BV2-V3: R_opp,W >= 1.05 and R_opp,S >= 1.05 (paired replicate-level ratios)

Writes: results/phase_m3bv2/value_analysis.json
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
DEST = REPO / "results" / "phase_m3bv2" / "value_analysis.json"

MIN_STABLE = 0.8
MIN_MARGIN = 0.05
MARGIN_DIAGNOSTIC = 0.10
MIN_COVERAGE_PER_CLASS = 4
MAX_PER_CONFIG_PER_CLASS = 3
N_PER_CLASS = 12
LOG095 = -math.log(0.95)          # G_Oracle threshold (task Sec. 17)
R_OPP_MIN = 1.05

FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "base"}
REF_ARM = {"WIDEN": "widen", "SHRINK": "shrink"}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def med(xs):
    return float(statistics.median(xs))


def pick_class(cands: list, n: int, max_per_config: int) -> list:
    """Deterministic selection (task Sec. 14): eligible only -> max config
    coverage -> larger stability -> larger margin -> (config_id, s2) order."""
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

    # ---------------- B4: eligibility + deterministic selection ------------
    classified = {}
    for key, r in pool["reference_fields"].items():
        label = r["oracle"]["oracle_action"]
        st = st_entries[key]["stability"]
        if label not in ("WIDEN", "SHRINK"):
            continue
        stable = bool(st["widen_stable"]) if label == "WIDEN" else bool(
            st["shrink_stable"])
        frac = st["fraction_widen_best"] if label == "WIDEN" else st[
            "fraction_shrink_best"]
        classified[key] = {
            "config_id": r["state_key"]["config_id"],
            "s2": r["state_key"]["s2"],
            "oracle_action": label,
            "class": label,
            "margin_Delta_dir": r["oracle"]["direction_margin_Delta_dir"],
            "stability_fraction": frac,
            "eligible": bool(stable and frac >= MIN_STABLE),
            "support": r["oracle"]["support"],
        }

    eligible = {cls: [c for c in classified.values()
                      if c["class"] == cls and c["eligible"]]
                for cls in ("WIDEN", "SHRINK")}
    selection = {cls: pick_class(eligible[cls], N_PER_CLASS,
                                 MAX_PER_CONFIG_PER_CLASS)
                 for cls in ("WIDEN", "SHRINK")}

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

    margin_diag = {
        cls: sum(1 for c in lst if c["margin_Delta_dir"] is not None
                 and c["margin_Delta_dir"] >= MARGIN_DIAGNOSTIC)
        for cls, lst in selection.items()}

    # ---------------- per-state records (24 states) ------------------------
    states = {}
    for cls in ("WIDEN", "SHRINK"):
        for c in selection[cls]:
            key = f"{c['config_id']}|{c['s2']}"
            reps = st_entries[key]["replicates"]
            m2 = {"base": [r["M2"]["base"] for r in reps],
                  "widen": [r["M2"]["widen"] for r in reps],
                  "shrink": [r["M2"]["shrink"] for r in reps]}
            states[f"{c['config_id']}|{c['s2']}"] = {
                "state_key": {"config_id": c["config_id"], "s2": c["s2"]},
                "class": cls,
                "oracle_action": c["oracle_action"],
                "margin_Delta_dir": c["margin_Delta_dir"],
                "stability_fraction": c["stability_fraction"],
                "support": c["support"],
                "reference_median_M2": {a: med(xs) for a, xs in m2.items()},
                "replicate_M2": m2,
            }

    # ---------------- B5: unified functional J -----------------------------
    policies = {"ORACLE": None}
    policies.update({k: v for k, v in FIXED_ARM.items()})

    def logr_reps(state: dict, arm: str) -> list[float]:
        m2 = state["replicate_M2"]
        return [math.log(m2[arm][i] / m2["base"][i])
                for i in range(len(m2["base"]))]

    # per state, per policy: replicate log-ratios + per-state median
    for key, st in states.items():
        arm_of = {p: (REF_ARM[st["class"]] if p == "ORACLE" else a)
                  for p, a in policies.items() if p != "ORACLE"}
        arm_of["ORACLE"] = REF_ARM[st["class"]]
        st["replicate_log_ratio"] = {
            p: logr_reps(st, arm_of[p]) for p in policies}
        st["state_J"] = {p: med(st["replicate_log_ratio"][p])
                         for p in policies}

    order = [f"{c['config_id']}|{c['s2']}"
             for cls in ("WIDEN", "SHRINK") for c in selection[cls]]
    J = {p: med([states[k]["state_J"][p] for k in order])
         for p in policies}

    best_fixed = min(FIXED_ARM, key=J.get)
    oracle_gain = J[best_fixed] - J["ORACLE"]
    ratio_equiv = math.exp(-oracle_gain)          # exp(J(O) - J(BestFixed))
    v2_pass = bool(oracle_gain >= LOG095)
    strong_target = bool(ratio_equiv <= 0.90)

    # direct paired ratio diagnostic (median over states of per-state
    # median-replicate M2(Oracle)/M2(BestFixed)) -- report only
    diag_ratios = []
    for k in order:
        st = states[k]
        o_arm = REF_ARM[st["class"]]
        b_arm = FIXED_ARM[best_fixed]
        r = [st["replicate_M2"][o_arm][i] /
             st["replicate_M2"][b_arm][i]
             for i in range(len(st["replicate_M2"]["base"]))]
        diag_ratios.append(med(r))
    diag_median_ratio = med(diag_ratios)

    # ---------------- B6: V1 fixed-rule tradeoff ----------------------------
    class_med = {}
    for cls in ("WIDEN", "SHRINK"):
        keys = [k for k in order if states[k]["class"] == cls]
        class_med[cls] = {p: med([states[k]["state_J"][p] for k in keys])
                          for p in policies}
    best_per_class = {cls: min(FIXED_ARM, key=lambda f: class_med[cls][f])
                      for cls in ("WIDEN", "SHRINK")}
    weak_flag = bool(best_per_class["WIDEN"] == best_per_class["SHRINK"])

    # ---------------- B6: V3 opposite-class regret --------------------------
    def opp_regret(cls: str, num_arm: str, den_arm: str) -> float:
        vals = []
        for k in order:
            st = states[k]
            if st["class"] != cls:
                continue
            m2 = st["replicate_M2"]
            vals.append(med([m2[num_arm][i] / m2[den_arm][i]
                             for i in range(len(m2["base"]))]))
        return med(vals)

    r_opp_w = opp_regret("WIDEN", "shrink", "widen")
    r_opp_s = opp_regret("SHRINK", "widen", "shrink")
    v3_pass = bool(r_opp_w >= R_OPP_MIN and r_opp_s >= R_OPP_MIN)

    # ---------------- gates + freeze selection ------------------------------
    def _state_out(key: str) -> dict:
        st = states[key]
        return {
            "state_key": st["state_key"], "class": st["class"],
            "oracle_action": st["oracle_action"],
            "margin_Delta_dir": st["margin_Delta_dir"],
            "stability_fraction": st["stability_fraction"],
            "reference_median_M2": st["reference_median_M2"],
            "replicate_M2": st["replicate_M2"],
            "state_J": st["state_J"],
        }

    freeze_selection = [_state_out(k) for k in order]

    v0_pass = bool(
        len(selection["WIDEN"]) == N_PER_CLASS
        and len(selection["SHRINK"]) == N_PER_CLASS
        and all(c["eligible"] for c in selection["WIDEN"]
                + selection["SHRINK"])
        and all(c["stability_fraction"] >= MIN_STABLE
                for c in selection["WIDEN"] + selection["SHRINK"])
        and all(c["margin_Delta_dir"] is not None
                and c["margin_Delta_dir"] >= MIN_MARGIN
                for c in selection["WIDEN"] + selection["SHRINK"])
        and coverage["WIDEN"]["coverage_ok"]
        and coverage["SHRINK"]["coverage_ok"])

    analysis = {
        "schema_version": "raretopo-m3bv2-value-analysis-v0",
        "document_type": "Axis B (Value) benchmark: deterministic 12W/12S "
                         "selection, unified-functional BestFixed audit, "
                         "Oracle feasibility (V2), opposite-class regret (V3)",
        "stage": "B4_B5_B6_B7_value_benchmark",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "source": {
            "candidate_pool": POOL.relative_to(REPO).as_posix(),
            "headline_stability": STAB.relative_to(REPO).as_posix(),
            "reuse_record": "results/phase_m3bv2/reuse_record.json",
            "reused_as": "prior characterization data (B2 reuse record)",
        },
        "unified_functional": {
            "definition": "J(pi) = median_state [ median_replicate "
                          "log( M2(pi)/M2(BASE) ) ] over the 24 selected "
                          "states; paired per replicate",
            "one_functional_only": True,
            "J": {p: round(v, 9) for p, v in J.items()},
            "best_fixed": best_fixed,
            "G_Oracle": round(oracle_gain, 9),
            "equivalent_ratio_exp(-G)": round(ratio_equiv, 9),
            "threshold_minus_log095": round(LOG095, 9),
        },
        "eligibility_counts": {cls: sum(1 for c in
                                        classified.values()
                                        if c["class"] == cls and c["eligible"])
                               for cls in ("WIDEN", "SHRINK")},
        "selection": {cls: [{"config_id": c["config_id"], "s2": c["s2"],
                             "stability_fraction":
                                 c["stability_fraction"],
                             "margin_Delta_dir": c["margin_Delta_dir"]}
                            for c in lst]
                      for cls, lst in selection.items()},
        "selection_sizes": {cls: len(lst)
                            for cls, lst in selection.items()},
        "coverage": coverage,
        "margin_diagnostic_ge_0.10": margin_diag,
        "fixed_rule_tradeoff_V1": {
            "class_conditional_J": {cls: {p: round(v, 9)
                                          for p, v in m.items()}
                                    for cls, m in class_med.items()},
            "best_fixed_per_class": best_per_class,
            "weak_flag_one_fixed_rule_dominates_both_classes": weak_flag,
        },
        "oracle_feasibility_V2": {
            "pass": v2_pass,
            "G_Oracle_ge_minus_log095": round(oracle_gain, 9) >= LOG095,
            "equivalent_ratio_le_0.95": ratio_equiv <= 0.95,
            "strong_target_ratio_le_0.90_report_only": strong_target,
            "direct_paired_median_ratio_diagnostic":
                round(diag_median_ratio, 9),
        },
        "opposite_class_regret_V3": {
            "pass": v3_pass,
            "R_opp_W": round(r_opp_w, 9),
            "R_opp_S": round(r_opp_s, 9),
            "threshold": R_OPP_MIN,
            "semantics": "paired ratio M2(num)/M2(den) per replicate, "
                         "median over 8 replicates per state, median over "
                         "class states",
        },
        "gates": {
            "V0": v0_pass,
            "V1_diagnostic": {"weak_flag": weak_flag,
                              "recorded": True},
            "V2": v2_pass,
            "V3": v3_pass,
            "freeze_required": bool(v0_pass and v2_pass and v3_pass),
        },
        "freeze_selection": freeze_selection,
        "no_controller_output_used": True,
    }
    DEST.write_text(json.dumps(analysis, indent=1), encoding="utf-8")

    print("eligible W/S:", analysis["eligibility_counts"])
    print("selection sizes:", json.dumps(analysis["selection_sizes"]))
    print("coverage:", json.dumps({c: coverage[c]["n_configs"]
                                   for c in ("WIDEN", "SHRINK")}))
    print("margin >=0.10:", json.dumps(margin_diag))
    print("J:", json.dumps({p: round(v, 6) for p, v in J.items()}))
    print("BestFixed:", best_fixed)
    print("G_Oracle:", round(oracle_gain, 6),
          "| equiv ratio:", round(ratio_equiv, 5))
    print("V1 weak flag:", weak_flag,
          "| best per class:", json.dumps(best_per_class))
    print("R_opp W/S:", round(r_opp_w, 5), "/", round(r_opp_s, 5))
    print("V2:", "PASS" if v2_pass else "FAIL",
          "| V3:", "PASS" if v3_pass else "FAIL",
          "| V0:", "PASS" if v0_pass else "FAIL")
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0 if (v0_pass and v2_pass and v3_pass) else 4


if __name__ == "__main__":
    import sys
    raise SystemExit(main())