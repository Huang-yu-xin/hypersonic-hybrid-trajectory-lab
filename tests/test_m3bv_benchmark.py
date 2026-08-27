"""M3-BV benchmark-only tests (task Sec. 18 list, negative-result adapted).

The M3-BV benchmark construction ran to completion of its preregistered
gates: BV-0/BV-1/BV-2 PASS, BV-3 FAIL (Oracle ratio median 0.9946 > 0.95,
wins 14/24 < 16) => VALUE-INFEASIBLE => Case A: benchmark freeze artifacts
are NOT created and controller runs stay 0 (task Sec. 13/26/30).  These
tests pin the constructed facts AND the discipline (no freeze, no
controller, no post-hoc relaxation), re-computing every headline number
from the stored benchmark-only artifacts.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
LOCK = json.loads((REPO / "configs" / "phase_m3bv"
                   / "m3bv_construction_lock.json").read_text(
                       encoding="utf-8"))
POOL_PATH = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_candidate_pool.json"
STAB_PATH = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
ANA_PATH = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_analysis.json"

POOL = json.loads(POOL_PATH.read_text(encoding="utf-8"))
STAB = json.loads(STAB_PATH.read_text(encoding="utf-8"))
ANA = json.loads(ANA_PATH.read_text(encoding="utf-8"))
REF = POOL["reference_fields"]

PARENT_FREEZE_SHA = "b613f45dc6645c6da26ab58b5185764f14d771ca6b996" \
                    "bffed88fea1f467a5f3"
WINS_MIN = 16
RATIO_MAX = 0.95


def med(xs):
    return float(statistics.median(xs))


# --------------------------------------------------------------------------- #
# 1. parent tags + seals
# --------------------------------------------------------------------------- #
def test_m3bv_parent_tags():
    tag = subprocess.run(["git", "rev-parse", "RareTopo-M3-G-v1^{}"],
                         cwd=REPO, capture_output=True, text=True)
    assert tag.returncode == 0, "RareTopo-M3-G-v1 tag must exist"
    # construction lock records the same parent freeze seal
    assert (LOCK["parent_tags"]["freeze_reference"].endswith(PARENT_FREEZE_SHA))
    assert (POOL["parent_benchmark_freeze_hash"] == PARENT_FREEZE_SHA)


# --------------------------------------------------------------------------- #
# 2. grid locked before characterization
# --------------------------------------------------------------------------- #
def test_m3bv_grid_locked():
    lock_grid = LOCK["candidate_grid"]["s2_grid_bv"]
    assert len(lock_grid) == 11
    assert lock_grid[0] == 0.65 and lock_grid[-1] == 8.0
    # execution artifact pins the same lock hash
    lock_sha = hashlib.sha256(
        (REPO / "configs" / "phase_m3bv"
         / "m3bv_construction_lock.json").read_bytes()).hexdigest()
    assert POOL["construction_lock_sha256"] == lock_sha
    assert set(POOL["s2_grid_bv"]) == set(lock_grid)
    assert POOL["counts"]["max_pool"] == 8 * len(lock_grid)


# --------------------------------------------------------------------------- #
# 3. all three required arms legal
# --------------------------------------------------------------------------- #
def test_m3bv_all_three_arms_legal():
    assert POOL["counts"]["legal"] == 88
    assert POOL["counts"]["illegal_pre_freeze"] == 0
    assert POOL["counts"]["assembly_stops"] == 0
    for s in POOL["states_legal"]:
        assert s["all_three_arms_legal"] is True
        assert s["arms_legal"] == {"base": True, "widen": True,
                                   "shrink": True}
    # legality floor: lowest grid point 0.65*exp(-0.20) ~ 0.532 > 0.5
    from hyptraj.m3g.metrics import arm_legal_at
    assert arm_legal_at(0.65, -0.20) is True
    assert arm_legal_at(0.65, +0.20) is True
    assert arm_legal_at(0.55, -0.20) is False      # old-grid pathology


# --------------------------------------------------------------------------- #
# 4. reference CRN protocol executed as locked
# --------------------------------------------------------------------------- #
def test_m3bv_reference_crn():
    ex = POOL["reference_protocol_executed"]
    assert ex["n_ref_per_arm"] == 500_000
    assert ex["n_batches"] == 20
    assert ex["states_characterized"] == 88
    # rng rule [701001 + idx] over (config_id, s2) sorted cells
    states = sorted(POOL["states_legal"], key=lambda s: (s["config_id"],
                                                         s["s2"]))
    for i, s in enumerate(states):
        key = f"{s['config_id']}|{s['s2']}"
        assert REF[key]["state_rng_key"] == [701001 + i]
        assert REF[key]["n_ref_per_arm"] == 500_000
        assert REF[key]["n_batches"] == 20


# --------------------------------------------------------------------------- #
# 5. identity M2 = sum_j L_j
# --------------------------------------------------------------------------- #
def test_m3bv_m2_equals_sum_leakage():
    ex = POOL["reference_protocol_executed"]
    assert ex["m2_equals_sum_l_arms_checked"] == 88 * 3
    assert ex["m2_equals_sum_l_arms_pass"] == 88 * 3
    for key, r in REF.items():
        for aname in ("base", "widen", "shrink"):
            arm = r["arms"][aname]
            l_sum = sum(v["L"] for v in arm["L_modes"].values())
            assert abs(arm["M2"] - l_sum) <= 1e-9


# --------------------------------------------------------------------------- #
# 6. active WIDEN/SHRINK margin threshold (Delta_best >= 0.05) + support
# --------------------------------------------------------------------------- #
def test_m3bv_active_margin_threshold():
    for s in ANA["selection"]["WIDEN"] + ANA["selection"]["SHRINK"]:
        key = f"{s['config_id']}|{s['s2']}"
        lab = REF[key]["oracle"]
        assert lab["oracle_action"] in ("WIDEN", "SHRINK")
        assert lab["direction_margin_Delta_dir"] >= 0.05 - 1e-12
        sup = lab["support"]
        assert sup["base_vs_widen_supported"] is True
        assert sup["base_vs_shrink_supported"] is True
        assert lab.get("margin_below_threshold") is not True


# --------------------------------------------------------------------------- #
# 7. HOLD reference indifference (frozen +-3% hold window, both perturbations)
# --------------------------------------------------------------------------- #
def test_m3bv_hold_reference_indifference():
    for s in ANA["selection"]["HOLD"]:
        key = f"{s['config_id']}|{s['s2']}"
        lab = REF[key]["oracle"]
        assert lab["oracle_action"] == "HOLD"
        r = lab["ratios"]
        assert abs(r["widen_over_base"]) <= 0.03
        assert abs(r["shrink_over_base"]) <= 0.03
        assert lab["support"]["hold_window_satisfied"] is True


# --------------------------------------------------------------------------- #
# 8. HOLD headline stability (>= 0.8 replicates inside +-5% of BASE)
# --------------------------------------------------------------------------- #
def test_m3bv_hold_headline_stability():
    for s in ANA["selection"]["HOLD"]:
        key = f"{s['config_id']}|{s['s2']}"
        st = STAB["entries"][key]["stability"]
        assert st["fraction_hold_indiff"] >= 0.8
        for rep in STAB["entries"][key]["replicates"]:
            assert rep["hold_indiff"] is True


# --------------------------------------------------------------------------- #
# 9. action stability (W/S realized best in >= 0.8 replicates)
# --------------------------------------------------------------------------- #
def test_m3bv_action_stability():
    widen_keys = {(s["config_id"], s["s2"])
                  for s in ANA["selection"]["WIDEN"]}
    shrink_keys = {(s["config_id"], s["s2"])
                   for s in ANA["selection"]["SHRINK"]}
    for cls_lst, expect_attr, frac_field in (
            (ANA["selection"]["WIDEN"], "widen_best",
             "fraction_widen_best"),
            (ANA["selection"]["SHRINK"], "shrink_best",
             "fraction_shrink_best")):
        for s in cls_lst:
            key = f"{s['config_id']}|{s['s2']}"
            reps = STAB["entries"][key]["replicates"]
            assert all(r[expect_attr] for r in reps)
            st = STAB["entries"][key]["stability"]
            assert st[frac_field] >= 0.8
    assert len(widen_keys) == 8 and len(shrink_keys) == 8


# --------------------------------------------------------------------------- #
# 10. oracle / best-fixed definition (frozen median aggregation)
# --------------------------------------------------------------------------- #
def test_m3bv_oracle_best_fixed_definition():
    fixed_arms = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
                  "ALWAYS_HOLD": "base"}
    ref_arm = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}
    sel = ANA["selection"]
    keys = [(s["config_id"], s["s2"])
            for cls in ("WIDEN", "SHRINK", "HOLD") for s in sel[cls]]
    assert len(keys) == 24 and len(set(keys)) == 24
    global_med = {}
    for f, arm in fixed_arms.items():
        per_state = []
        for cid, s2 in keys:
            key = f"{cid}|{s2}"
            rep_m2 = [r["M2"][arm]
                      for r in STAB["entries"][key]["replicates"]]
            per_state.append(med(rep_m2))
        global_med[f] = med(per_state)
    bf = min(global_med, key=global_med.get)
    assert bf == "ALWAYS_WIDEN"
    assert bf == ANA["oracle_audit"]["bv3"]["best_fixed_policy"]
    assert abs(global_med[bf] - 6.265058) < 1e-5


# --------------------------------------------------------------------------- #
# 11. oracle headroom gate BV-3 (correctly FAILS, recorded honestly)
# --------------------------------------------------------------------------- #
def test_m3bv_oracle_headroom_gate():
    bf = ANA["oracle_audit"]["bv3"]["best_fixed_policy"]
    ref_arm = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}
    bf_arm = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
              "ALWAYS_HOLD": "base"}[bf]
    sel = ANA["selection"]
    per_state_ratio, wins = [], 0
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        for s in sel[cls]:
            key = f"{s['config_id']}|{s['s2']}"
            reps = STAB["entries"][key]["replicates"]
            ratios = [r["M2"][ref_arm[cls]] / r["M2"][bf_arm] for r in reps]
            per_state_ratio.append(med(ratios))
            if med([r["M2"][ref_arm[cls]] for r in reps]) < med(
                    [r["M2"][bf_arm] for r in reps]):
                wins += 1
    ratio_med = med(per_state_ratio)
    assert abs(ratio_med - 0.9946) < 1e-3
    assert ratio_med > RATIO_MAX                    # gate must fail
    assert wins == 14 and wins < WINS_MIN           # gate must fail
    bv3 = ANA["oracle_audit"]["bv3"]
    assert bv3["ratio_gate_pass"] is False
    assert bv3["wins_gate_pass"] is False
    assert bv3["bv3_pass"] is False
    assert bv3["wins"] == 14 and bv3["losses"] == 2 and bv3["ties"] == 8


# --------------------------------------------------------------------------- #
# 12. class balance (8/8/8 selected)
# --------------------------------------------------------------------------- #
def test_m3bv_class_balance():
    sizes = ANA["selection_sizes"]
    assert sizes == {"WIDEN": 8, "SHRINK": 8, "HOLD": 8}
    assert ANA["eligibility_counts"]["WIDEN"] >= 8
    assert ANA["eligibility_counts"]["SHRINK"] >= 8
    assert ANA["eligibility_counts"]["HOLD"] >= 8   # BV-1 passed


# --------------------------------------------------------------------------- #
# 13. config coverage (>= 4 configs/class, <= 2 states per config per class)
# --------------------------------------------------------------------------- #
def test_m3bv_config_coverage():
    cov = ANA["coverage"]
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        assert cov[cls]["n_configs"] >= 4
        assert max(cov[cls]["per_config"].values()) <= 2
        assert cov[cls]["coverage_ok"] is True


# --------------------------------------------------------------------------- #
# 14. deterministic selection replay
# --------------------------------------------------------------------------- #
def test_m3bv_selection_deterministic():
    # replay the locked rule from classification + stability only
    cls_of = {}
    for key, r in REF.items():
        cid, s2 = r["state_key"]["config_id"], r["state_key"]["s2"]
        lab = r["oracle"]["oracle_action"]
        if lab not in ("WIDEN", "SHRINK", "HOLD"):
            continue
        st = STAB["entries"][key]["stability"]
        if lab == "WIDEN":
            ok = st["widen_stable"]
            frac = st["fraction_widen_best"]
        elif lab == "SHRINK":
            ok = st["shrink_stable"]
            frac = st["fraction_shrink_best"]
        else:
            ok = st["hold_stable"]
            frac = st["fraction_hold_indiff"]
        if ok:
            cls_of.setdefault(lab, []).append(
                (cid, float(s2), frac,
                 r["oracle"].get("direction_margin_Delta_dir")))

    def pick(cands):
        by_cfg = {}
        for cid, s2, frac, margin in cands:
            by_cfg.setdefault(cid, []).append((cid, s2, frac, margin))
        sel = []
        for cid in sorted(by_cfg):
            if len(sel) >= 8:
                break
            grp = sorted(by_cfg[cid],
                         key=lambda c: (-c[2],
                                        -(c[3] if c[3] is not None else -1.0),
                                        c[1]))
            take = min(2, 8 - len(sel))
            sel += [c for c in grp[:take]]
        if len(sel) < 8:
            taken = {(c[0], c[1]) for c in sel}
            rest = [c for c in cands if (c[0], c[1]) not in taken]
            rest.sort(key=lambda c: (-c[2],
                                     -(c[3] if c[3] is not None else -1.0),
                                     c[0], c[1]))
            sel += rest[: 8 - len(sel)]
        return {(c[0], c[1]) for c in sel}

    for cls in ("WIDEN", "SHRINK", "HOLD"):
        expected = pick(cls_of[cls])
        actual = {(s["config_id"], s["s2"]) for s in ANA["selection"][cls]}
        assert expected == actual, f"selection replay mismatch for {cls}"


# --------------------------------------------------------------------------- #
# 15. no controller performance enters selection
# --------------------------------------------------------------------------- #
def test_m3bv_no_controller_selection_leakage():
    # selection records carry ONLY benchmark-only fields
    allowed = {"config_id", "s2", "stability_fraction", "margin_Delta_dir"}
    for cls, lst in ANA["selection"].items():
        for s in lst:
            assert set(s.keys()) == allowed
    # oracle audit was computed AFTER selection and does not feed it:
    # B6 numbers are absent from selection records; oracle fields never
    # appear in the construction lock selection rule
    assert "oracle" not in json.dumps(ANA["selection"])


# --------------------------------------------------------------------------- #
# 16. negative-result discipline: no freeze artifacts, zero controller runs
# --------------------------------------------------------------------------- #
def test_m3bv_negative_result_discipline():
    # BV-3 FAIL => Case A: benchmark freeze must NOT exist
    assert not (REPO / "docs" / "phase_m3bv"
                / "M3_BV_Benchmark_Freeze.md").exists()
    assert not (REPO / "docs" / "phase_m3bv"
                / "M3_BV_Benchmark_Freeze.json").exists()
    assert not (REPO / "configs" / "phase_m3bv"
                / "m3bv_benchmark_v0.json").exists()
    # zero controller evaluation on this benchmark
    ctrls = list((REPO / "results" / "phase_m3bv").rglob(
        "*controller*")) if (REPO / "results" / "phase_m3bv").exists() \
        else []
    assert ctrls == []