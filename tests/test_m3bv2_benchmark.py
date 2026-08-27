"""M3-BV2 benchmark-only tests (task Sec. 27 — all 18 required test names).

All checks operate on preregistered construction outputs only; zero
controller outputs are read anywhere.

Reading of the (untracked, per repo policy) results files:
  results/phase_m3bv/reference/m3bv_candidate_pool.json        (prior data)
  results/phase_m3bv/reference/m3bv_headline_stability.json    (prior data)
  results/phase_m3bv2/reuse_record.json / *_analysis.json      (BV2 outputs)
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
REUSE = REPO / "results" / "phase_m3bv2" / "reuse_record.json"
DAN = REPO / "results" / "phase_m3bv2" / "decision_analysis.json"
VAN = REPO / "results" / "phase_m3bv2" / "value_analysis.json"
BV0_AN = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_analysis.json"
LOCK = REPO / "configs" / "phase_m3bv2" / "m3bv2_construction_lock.json"
FREEZE_D = REPO / "docs" / "phase_m3bv2" / "M3_BV2_Decision_Benchmark_Freeze.json"
FREEZE_V = REPO / "docs" / "phase_m3bv2" / "M3_BV2_Value_Benchmark_Freeze.json"
CFG_D = REPO / "configs" / "phase_m3bv2" / "m3bv2_decision_benchmark.json"
CFG_V = REPO / "configs" / "phase_m3bv2" / "m3bv2_value_benchmark.json"

S2_GRID = [0.65, 0.85, 1.10, 1.40, 1.80, 2.30, 3.00, 4.00, 5.00, 6.40, 8.00]
LOG095 = -math.log(0.95)

GIT_TAG_V0 = "RareTopo-M3-BV-v0"
CORRECTION_COMMIT = "1eea183"          # "Correct M3-BV headroom ..."
PREREG_COMMIT = "37d17bc"              # "M3-BV2 task + construction lock ..."


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def med(xs) -> float:
    return float(statistics.median(xs))


# --------------------------------------------------------------------------
# 1. parent tags
# --------------------------------------------------------------------------

def test_m3bv2_parent_tags():
    tags = git("tag", "-l")
    assert GIT_TAG_V0 in tags, "RareTopo-M3-BV-v0 tag missing"
    assert git("rev-list", "-n", "1", GIT_TAG_V0).startswith(
        CORRECTION_COMMIT), "BV-v0 tag must point at the correction commit"
    # M3-G-v1 parent unchanged
    assert git("rev-parse", "RareTopo-M3-G-v1^{}").startswith("4505a36")
    # BV2 preregistration commit exists with the locked message
    log = git("log", "-1", "--format=%s", PREREG_COMMIT)
    assert "construction lock" in log
    # analysis runs happened at or after the preregistration commit
    # (git_commit == PREREG_COMMIT means science ran exactly at the
    # preregistered state, the strongest form of the discipline)
    for an in (load(DAN), load(VAN), load(REUSE)):
        rc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", PREREG_COMMIT,
             an["git_commit"]], cwd=REPO, capture_output=True)
        assert rc.returncode == 0, (
            f"analysis git_commit {an['git_commit']} not a descendant of "
            f"preregistration {PREREG_COMMIT}")


# --------------------------------------------------------------------------
# 2. candidate source lock
# --------------------------------------------------------------------------

def test_m3bv2_candidate_source_lock():
    lock = load(LOCK)
    assert lock["candidate_source"]["type"] == \
        "REUSE_bv0_pool_as_prior_characterization"
    reuse = load(REUSE)
    assert reuse["conclusion"] == "REUSE_OK"
    for src in ("candidate_pool", "headline_stability"):
        p = REPO / "results" / "phase_m3bv" / "reference" / \
            f"m3bv_{src}.json"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == \
            reuse["sources"][src]["sha256"], f"source {src} hash mismatch"
    assert reuse["byte_identity_anchors"]["n_states"] == 88
    anchors = reuse["byte_identity_anchors"]
    for k, v in anchors.items():
        if isinstance(v, bool):
            assert v, f"anchor {k} failed"
    assert reuse["no_new_simulation"] is True
    assert reuse["no_controller_output_used"] is True


# --------------------------------------------------------------------------
# 3. three-arm legality
# --------------------------------------------------------------------------

def test_m3bv2_three_arm_legality():
    pool = load(POOL)
    assert pool["counts"]["legal"] == 88
    assert pool["counts"]["illegal_pre_freeze"] == 0
    assert pool["counts"]["assembly_stops"] == 0
    assert all(s["all_three_arms_legal"] for s in pool["states_legal"])
    pool_keys = {(s["config_id"], s["s2"]) for s in pool["states_legal"]}
    for an, axis in ((load(DAN), "decision"), (load(VAN), "value")):
        for fs in an["freeze_selection"]:
            k = (fs["state_key"]["config_id"], fs["state_key"]["s2"])
            assert k in pool_keys, f"{axis} state {k} not in legal pool"


# --------------------------------------------------------------------------
# 4. reference CRN semantics
# --------------------------------------------------------------------------

def test_m3bv2_reference_crn():
    pool = load(POOL)
    reuse = load(REUSE)
    assert reuse["reference_semantics_checks"][
        "reference_budget_500k_20batches"] is True
    refs = pool["reference_fields"]
    assert len(refs) == 88
    for r in refs.values():
        assert r["n_ref_per_arm"] == 500000
        assert r["n_batches"] == 20
        assert r["delta_theta"] == 0.2
        assert len(r["state_rng_key"]) == 1
    stab = load(STAB)
    for key, e in stab["entries"].items():
        assert e["n_headline_per_arm"] == 100000
        assert e["n_batches"] == 10
        assert e["n_replicates"] == 8
        cid, s2 = key.split("|")
        idx = pool["frozen_configs"].index(cid) * 11 + S2_GRID.index(
            float(s2))
        for rep in e["replicates"]:
            assert rep["rng_key"] == [701001 + idx,
                                      10000 + rep["replicate"]]
    # CRN semantics locked: one shared Generator per state across arms
    assert "one shared Generator per state" in json.dumps(load(LOCK))


# --------------------------------------------------------------------------
# 5. M2 = sum L
# --------------------------------------------------------------------------

def test_m3bv2_m2_equals_sum_leakage():
    pool = load(POOL)
    for r in pool["reference_fields"].values():
        chk = r["m2_sum_L_checked"]["M2_equals_sum_L"]
        assert set(chk.keys()) == {"base", "widen", "shrink"}
        assert all(v["pass"] for v in chk.values())
    assert load(REUSE)["reference_semantics_checks"][
        "m2_equals_sum_L_all_264_arms"] is True


# --------------------------------------------------------------------------
# 6. decision class balance
# --------------------------------------------------------------------------

def test_m3bv2_decision_class_balance():
    dan = load(DAN)
    assert dan["selection_sizes"] == {"WIDEN": 8, "HOLD": 8, "SHRINK": 8}
    classes = {fs["class"] for fs in dan["freeze_selection"]}
    assert classes == {"WIDEN", "HOLD", "SHRINK"}
    for fs in dan["freeze_selection"]:
        assert fs["class"] == fs["oracle_action"], \
            f"selected class != frozen label at {fs['state_key']}"
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        assert dan["eligibility_counts"][cls] >= 8


# --------------------------------------------------------------------------
# 7. decision HOLD stability
# --------------------------------------------------------------------------

def test_m3bv2_decision_hold_stability():
    dan = load(DAN)
    stab = load(STAB)
    pool = load(POOL)
    holds = [fs for fs in dan["freeze_selection"] if fs["class"] == "HOLD"]
    assert len(holds) == 8
    for fs in holds:
        key = f"{fs['state_key']['config_id']}|{fs['state_key']['s2']}"
        assert fs["stability_fraction"] >= 0.8
        assert fs["stable"] is True
        # frozen reference indifference rule + support flags
        assert pool["reference_fields"][key]["oracle"]["oracle_action"] == \
            "HOLD"
        assert fs["support"]["hold_window_satisfied"] is True
        st = stab["entries"][key]["stability"]
        assert st["hold_stable"] is True
        assert st["fraction_hold_indiff"] >= 0.8


# --------------------------------------------------------------------------
# 8. decision config coverage
# --------------------------------------------------------------------------

def test_m3bv2_decision_config_coverage():
    dan = load(DAN)
    for cls in ("WIDEN", "HOLD", "SHRINK"):
        cov = dan["coverage"][cls]
        assert cov["coverage_ok"] is True
        assert cov["n_configs"] >= 4
        assert max(cov["per_config"].values()) <= 2


# --------------------------------------------------------------------------
# 9. value 12W/12S
# --------------------------------------------------------------------------

def test_m3bv2_value_12w12s():
    van = load(VAN)
    assert van["selection_sizes"] == {"WIDEN": 12, "SHRINK": 12}
    classes = {fs["class"] for fs in van["freeze_selection"]}
    assert classes == {"WIDEN", "SHRINK"}
    assert all(fs["class"] == fs["oracle_action"]
               for fs in van["freeze_selection"])
    assert van["eligibility_counts"]["WIDEN"] >= 12
    assert van["eligibility_counts"]["SHRINK"] >= 12


# --------------------------------------------------------------------------
# 10. value margin
# --------------------------------------------------------------------------

def test_m3bv2_value_margin():
    van = load(VAN)
    for fs in van["freeze_selection"]:
        assert fs["margin_Delta_dir"] is not None
        assert fs["margin_Delta_dir"] >= 0.05
    # diagnostic counts (preferred >= 0.10) recorded, not gating
    for cls in ("WIDEN", "SHRINK"):
        assert van["margin_diagnostic_ge_0.10"][cls] >= 0


# --------------------------------------------------------------------------
# 11. value stability
# --------------------------------------------------------------------------

def test_m3bv2_value_stability():
    van = load(VAN)
    stab = load(STAB)
    for fs in van["freeze_selection"]:
        assert fs["stability_fraction"] >= 0.80
        key = f"{fs['state_key']['config_id']}|{fs['state_key']['s2']}"
        st = stab["entries"][key]["stability"]
        if fs["class"] == "WIDEN":
            assert st["widen_stable"] is True
        else:
            assert st["shrink_stable"] is True


# --------------------------------------------------------------------------
# 12. unified objective (recompute J from raw replicate M2)
# --------------------------------------------------------------------------

FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "base"}
REF_ARM = {"WIDEN": "widen", "SHRINK": "shrink"}


def _recompute_J(van: dict) -> dict:
    states = van["freeze_selection"]
    J = {}
    for p in ("ORACLE", *FIXED_ARM):
        per_state = []
        for fs in states:
            m2 = fs["replicate_M2"]
            arm = REF_ARM[fs["class"]] if p == "ORACLE" else FIXED_ARM[p]
            logs = [math.log(m2[arm][i] / m2["base"][i])
                    for i in range(len(m2["base"]))]
            per_state.append(med(logs))
        J[p] = med(per_state)
    return J


def test_m3bv2_unified_objective():
    van = load(VAN)
    J = _recompute_J(van)
    stored = van["unified_functional"]["J"]
    assert set(stored) == set(J)
    for p in J:
        assert math.isclose(J[p], stored[p], rel_tol=0, abs_tol=1e-8), (
            f"J({p}) recomputed {J[p]:.9f} != stored {stored[p]:.9f}")


# --------------------------------------------------------------------------
# 13. BestFixed chosen by the SAME objective
# --------------------------------------------------------------------------

def test_m3bv2_bestfixed_same_objective():
    van = load(VAN)
    J = _recompute_J(van)
    argmin = min(FIXED_ARM, key=J.get)
    assert argmin == van["unified_functional"]["best_fixed"]
    G = J[argmin] - J["ORACLE"]
    assert math.isclose(G, van["unified_functional"]["G_Oracle"],
                        rel_tol=0, abs_tol=1e-8)
    # same functional is the one used for the Oracle headroom gate
    assert math.isclose(math.exp(-G),
                        van["unified_functional"]["equivalent_ratio_exp(-G)"],
                        rel_tol=1e-9, abs_tol=1e-9)


# --------------------------------------------------------------------------
# 14. Oracle feasibility
# --------------------------------------------------------------------------

def test_m3bv2_oracle_feasibility():
    van = load(VAN)
    uf = van["unified_functional"]
    assert uf["G_Oracle"] >= LOG095
    assert uf["equivalent_ratio_exp(-G)"] <= 0.95
    assert van["gates"]["V2"] is True
    # strong target recorded (report only)
    assert "strong_target_ratio_le_0.90_report_only" in \
        van["oracle_feasibility_V2"]
    # direct paired median-ratio diagnostic recorded (report only)
    assert van["oracle_feasibility_V2"]["direct_paired_median_ratio_diagnostic"] \
        is not None


# --------------------------------------------------------------------------
# 15. opposite-class regret
# --------------------------------------------------------------------------

def _recompute_regret(van: dict) -> tuple[float, float]:
    vals_w, vals_s = [], []
    for fs in van["freeze_selection"]:
        m2 = fs["replicate_M2"]
        if fs["class"] == "WIDEN":
            vals_w.append(med([m2["shrink"][i] / m2["widen"][i]
                               for i in range(len(m2["base"]))]))
        else:
            vals_s.append(med([m2["widen"][i] / m2["shrink"][i]
                               for i in range(len(m2["base"]))]))
    return med(vals_w), med(vals_s)


def test_m3bv2_opposite_class_regret():
    van = load(VAN)
    rw, rs = _recompute_regret(van)
    assert rw >= 1.05, f"R_opp,W {rw:.4f} < 1.05"
    assert rs >= 1.05, f"R_opp,S {rs:.4f} < 1.05"
    assert van["gates"]["V3"] is True
    assert math.isclose(rw, van["opposite_class_regret_V3"]["R_opp_W"],
                        rel_tol=1e-6, abs_tol=1e-8)
    assert math.isclose(rs, van["opposite_class_regret_V3"]["R_opp_S"],
                        rel_tol=1e-6, abs_tol=1e-8)


# --------------------------------------------------------------------------
# 16. deterministic selection (replay)
# --------------------------------------------------------------------------

def _pick_class(cands: list, n: int, max_per_config: int) -> list:
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


def _candidates_dec(pool: dict, stab: dict) -> dict:
    out = {}
    for key, r in pool["reference_fields"].items():
        label = r["oracle"]["oracle_action"]
        st = stab["entries"][key]["stability"]
        if label == "WIDEN":
            el, frac = bool(st["widen_stable"]), st["fraction_widen_best"]
        elif label == "SHRINK":
            el, frac = bool(st["shrink_stable"]), st["fraction_shrink_best"]
        elif label == "HOLD":
            el, frac = bool(st["hold_stable"]), st["fraction_hold_indiff"]
        else:
            continue
        out.setdefault(label, []).append({
            "config_id": r["state_key"]["config_id"], "s2": r["state_key"]["s2"],
            "stability_fraction": frac,
            "margin_Delta_dir": r["oracle"]["direction_margin_Delta_dir"],
            "eligible": el})
    return out


def _candidates_val(pool: dict, stab: dict) -> dict:
    out = {"WIDEN": [], "SHRINK": []}
    for key, r in pool["reference_fields"].items():
        label = r["oracle"]["oracle_action"]
        if label not in ("WIDEN", "SHRINK"):
            continue
        st = stab["entries"][key]["stability"]
        frac = st["fraction_widen_best"] if label == "WIDEN" else st[
            "fraction_shrink_best"]
        stable = bool(st["widen_stable"]) if label == "WIDEN" else bool(
            st["shrink_stable"])
        out[label].append({
            "config_id": r["state_key"]["config_id"], "s2": r["state_key"]["s2"],
            "stability_fraction": frac,
            "margin_Delta_dir": r["oracle"]["direction_margin_Delta_dir"],
            "eligible": bool(stable and frac >= 0.8)})
    return out


def test_m3bv2_selection_deterministic():
    pool = load(POOL)
    stab = load(STAB)
    dan, van = load(DAN), load(VAN)

    dec = _candidates_dec(pool, stab)
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        replay = _pick_class([c for c in dec[cls] if c["eligible"]], 8, 2)
        stored = {(s["config_id"], s["s2"]) for s in dan["selection"][cls]}
        assert {(c["config_id"], c["s2"]) for c in replay} == stored, (
            f"decision {cls} replay mismatch")

    val = _candidates_val(pool, stab)
    for cls in ("WIDEN", "SHRINK"):
        replay = _pick_class([c for c in val[cls] if c["eligible"]], 12, 3)
        stored = {(s["config_id"], s["s2"]) for s in van["selection"][cls]}
        assert {(c["config_id"], c["s2"]) for c in replay} == stored, (
            f"value {cls} replay mismatch")

    # BV-v0 recorded selection is replayed bit-identically (prior data)
    assert dan["bv0_replay_crosscheck_identical"] is True
    bv0 = load(BV0_AN)
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        bv0_set = {(s["config_id"], s["s2"]) for s in bv0["selection"][cls]}
        d_set = {(s["config_id"], s["s2"]) for s in dan["selection"][cls]}
        assert d_set == bv0_set, f"decision {cls} != BV-v0 recorded selection"


# --------------------------------------------------------------------------
# 17. no controller selection leakage
# --------------------------------------------------------------------------

FORBIDDEN_KEY_SUBSTRINGS = ("controller", "m3g", "gradient", "ga1", "rho",
                            "offline", "ess", "m3-d", "m3_d", "vrf_budget")


def _scan_keys(obj: object, prefix: str = "") -> list[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            low = k.lower()
            if low == "no_controller_output_used":      # declaration, not use
                continue
            if any(b in low for b in FORBIDDEN_KEY_SUBSTRINGS):
                hits.append(f"{prefix}{k}")
            hits += _scan_keys(v, prefix + k + ".")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _scan_keys(v, prefix + f"[{i}].")
    return hits


def test_m3bv2_no_controller_selection_leakage():
    # strict key scan on the two analysis outputs (the actual selection /
    # gate inputs); the reuse record may legitimately name the parent
    # M3-G-v1 tag as a byte-identity anchor, so only its declaration flag
    # and sources are checked there.
    for an in (load(DAN), load(VAN)):
        hits = _scan_keys(an)
        assert not hits, f"controller-related keys found: {hits}"
        assert an.get("no_controller_output_used", False) is True
    assert load(REUSE).get("no_controller_output_used", False) is True
    # sources reference only the allowed prior-characterization files
    allowed = {"results/phase_m3bv/reference/m3bv_candidate_pool.json",
               "results/phase_m3bv/reference/m3bv_headline_stability.json",
               "results/phase_m3bv2/reuse_record.json",
               "prior characterization data (B2 reuse record)"}
    for an in (load(DAN), load(VAN)):
        for k, v in an["source"].items():
            assert v in allowed, f"unexpected source {k}: {v}"


# --------------------------------------------------------------------------
# 18. freeze schema (+ self-consistency)
# --------------------------------------------------------------------------

REQ_FREEZE_KEYS = (
    "schema_version", "document_type", "stage", "frozen_at_utc", "git_commit",
    "parent_tags", "source_hashes", "gates", "states",
    "online_trials_run_before_this_freeze", "controller_runs_on_bv2",
    "seal_declaration", "freeze_sha256_of_body_above")


def test_m3bv2_freeze_schema():
    for path, n_states, sizes in (
            (FREEZE_D, 24, {"WIDEN": 8, "HOLD": 8, "SHRINK": 8}),
            (FREEZE_V, 24, {"WIDEN": 12, "SHRINK": 12})):
        assert path.exists(), f"missing {path}"
        doc = load(path)
        for k in REQ_FREEZE_KEYS:
            assert k in doc, f"{path.name} missing key {k}"
        assert doc["controller_runs_on_bv2"] == 0
        assert doc["online_trials_run_before_this_freeze"] == 0
        assert len(doc["states"]) == n_states
        from collections import Counter
        assert Counter(s["class"] for s in doc["states"]) == sizes
        # self-consistency: body hash reproducible with the field stripped
        body = {k: v for k, v in doc.items()
                if k != "freeze_sha256_of_body_above"}
        h = hashlib.sha256(json.dumps(body, indent=1,
                                      ensure_ascii=False).encode("utf-8"))
        assert h.hexdigest() == doc["freeze_sha256_of_body_above"]
        # state ids must match the legal pool records
        pool = load(POOL)
        sid_map = {(s["config_id"], s["s2"]): s["state_id"]
                   for s in pool["states_legal"]}
        for st in doc["states"]:
            k = (st["state_key"]["config_id"], st["state_key"]["s2"])
            assert st["state_id"] == sid_map[k]
    # benchmark consumption configs exist, match freeze states
    for cfg, freeze in ((CFG_D, load(FREEZE_D)), (CFG_V, load(FREEZE_V))):
        assert cfg.exists()
        c = load(cfg)
        assert c["controller_runs_on_bv2"] == 0
        cset = {(s["state_key"]["config_id"], s["state_key"]["s2"])
                for s in c["states"]}
        fset = {(s["state_key"]["config_id"], s["state_key"]["s2"])
                for s in freeze["states"]}
        assert cset == fset
    # freeze markdown docs exist
    assert (REPO / "docs" / "phase_m3bv2" /
            "M3_BV2_Decision_Benchmark_Freeze.md").exists()
    assert (REPO / "docs" / "phase_m3bv2" /
            "M3_BV2_Value_Benchmark_Freeze.md").exists()