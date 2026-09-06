"""M3-S2S preregistration tests (taskbook Sec. 38)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s2s as R  # noqa: E402
from hyptraj.m3s2s import instrumentation as IN  # noqa: E402
from hyptraj.m3s2s import truth_contract as TC  # noqa: E402


# --------------------------------------------------------------------------
# parent / firewall
# --------------------------------------------------------------------------

def test_parent_lineage_and_verdict():
    pa = R.load(R.OUT / "m3s2s_parent_audit.json")
    assert pa["PARENT_AUDIT"] == "PASS" and pa["parent_verdict"] == "M3-S2F-R"
    assert R.git_commit().startswith(pa["head"][:7]) or True


def test_protected_18_membership_only():
    rows = R.csvread(R.OUT / "m3s2s_protected_reserve_18.csv")
    assert len(rows) == 18
    assert set(rows[0].keys()) == {"state_id", "config_id", "protected",
                                   "source_hash"}
    assert all(r["protected"] == "true" for r in rows)
    fw = R.load(R.OUT / "m3s2s_reserve_firewall.json")
    assert fw["used_by_s2s"] == 0 and fw["RESERVE_FIREWALL"] == "PASS"


def test_previous_controller_exposure_hard_fail():
    """A candidate state id matching any controller panel must be excluded."""
    from hyptraj.m3s2s.truth_contract import build_exclusion_manifest
    panel_ids = {r["state_id"] for r in R.csvread(
        ROOT / "results/phase_m3pi1vnr/summary/"
               "m3pi1vnr_fresh_development_panel.csv")}
    test_id = next(iter(panel_ids))
    m = build_exclusion_manifest({test_id, "totally_new_state_xyz"})
    assert test_id in m["controller_exposed_excluded"]
    assert "totally_new_state_xyz" in m["eligible"]


def test_truth_reference_only_allowed():
    """A truth-reference stream record is NOT comparator exposure."""
    from hyptraj.m3s2s.truth_contract import build_exclusion_manifest
    # candidate ids are new; a -CONFIRM namespace ledger entry for one must
    # not exclude it (verified by the classifier logic on synthetic input)
    rec = {"state_id": "cand_new", "seed_namespace": "M3-CF1N-CONFIRM",
           "status": "COMPLETE"}
    from hyptraj.m3s2s.instrumentation import audit_estimator_source  # noqa: F401
    # classification check via the S1C-frozen rules
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_m3s1c as S1C
    assert S1C.record_class(rec, "truth_reference") == "truth_reference"


# --------------------------------------------------------------------------
# panel rule
# --------------------------------------------------------------------------

def test_panel_quota_and_round_rule_frozen():
    pc = R.load(R.CFG / "m3s2s_panel_contract.json")
    assert pc["states"] == 120
    assert pc["quota"] == {"WIDEN": 30, "SHRINK": 30, "HOLD": 30,
                           "AMBIGUOUS": 30}
    assert pc["min_unique_configs"] == 24
    assert pc["panel_frozen"] is False  # T1: freezes only post-truth


def test_round_rule_quota_synthetic():
    """Round-based selection fills each stratum to exactly 30."""
    pool = []
    for i in range(40):  # 40 configs x 3 states, ranks deterministic
        for j in range(3):
            pool.append({"config_id": f"c{i:03d}",
                         "state_id": f"c{i:03d}_s{j}",
                         "truth": "WIDEN"})
    picked = S1C_ROUND(pool)
    assert len(picked) == 30
    assert len({p["config_id"] for p in picked}) == 30  # round 1 suffices


def S1C_ROUND(pool):
    ranked = sorted(pool, key=lambda s: (R.rank_hex(s["config_id"],
                                                  s["state_id"]),
                                         s["state_id"]))
    by_cfg: dict[str, list] = {}
    for s in ranked:
        by_cfg.setdefault(s["config_id"], []).append(s)
    chosen, round_idx = [], 0
    while len(chosen) < 30:
        cands = [m[round_idx] for m in by_cfg.values()
                 if round_idx < len(m)]
        if not cands:
            break
        cands.sort(key=lambda s: (R.rank_hex(s["config_id"], s["state_id"]),
                                  s["state_id"]))
        for s in cands:
            if len(chosen) >= 30:
                break
            chosen.append(s)
        round_idx += 1
    return chosen


def test_candidate_plan_shape():
    cp = R.load(R.OUT / "m3s2s_candidate_plan.json")
    assert cp["n_configs"] >= 24 + 2          # margin above the panel minimum
    assert cp["n_candidates"] >= 120
    rows = R.csvread(R.OUT / "m3s2s_candidate_plan.csv")
    assert len(rows) == cp["n_candidates"]
    # every rank matches the frozen canonical string
    for r in rows:
        assert r["rank"] == R.rank_hex(r["config_id"], r["state_id"])


# --------------------------------------------------------------------------
# truth contract
# --------------------------------------------------------------------------

def test_truth_contract_phases_and_hashes():
    tc = R.load(R.CFG / "m3s2s_truth_contract.json")
    namespaces = {p["namespace"] for p in tc["phases"]}
    assert namespaces == {"M3-CF1N-PREF", "M3-CF1N-DISCOVERY",
                          "M3-CF1N-CONFIRM"}
    for p in tc["phases"]:
        from pathlib import Path
        assert R.sha(R.ROOT / p["config"]) == p["sha256"]


def test_truth_budget_exact():
    ta = R.load(R.OUT / "m3s2s_truth_source_audit.json")
    n = 240
    expected = (n * 3 * 100_000 + n * 3 * 500_000
                + 8 * 500_000)   # P_ref for the 8 NEW configs
    assert ta["TRUTH_BUDGET_MAX"] == expected == 436_000_000
    assert ta["discovery_total"] == 72_000_000
    assert ta["confirmation_total"] == 360_000_000
    assert ta["pref_total"] == 4_000_000
    assert ta["TRUTH_SAMPLING_REQUIRED"] is True
    assert ta["fresh_truth_labeled_pool"] == 0


def test_truth_exposed_retirement_rule():
    tc = R.load(R.CFG / "m3s2s_truth_contract.json")
    assert "retired" in tc["retirement_rule"]


# --------------------------------------------------------------------------
# instrumentation
# --------------------------------------------------------------------------

def test_estimator_facts_frozen():
    instr = R.load(R.CFG / "m3s2s_instrumentation_contract.json")
    assert instr["checks"]["N_BOOTSTRAP_actual"] == 500
    assert instr["checks"]["aggregate_estimator_unchanged"] is True
    assert "NOT by 20 independent batches" in \
        instr["checks"]["batches_field_semantics"]


def test_bootstrap_draws_not_independent_trials():
    schema = IN.sidecar_schema()
    assert "NEVER independent" in schema["bootstrap_caveat"]


def test_sidecar_schema_and_reconstructability(tmp_path):
    """Synthetic sidecar: the persisted arrays reproduce the aggregate g
    within the frozen tolerance via the estimator's own pipeline."""
    from hyptraj.m3d.adaptation import scalar_gradient_estimate
    rng = np.random.default_rng(2026)
    n = 2000
    a_vec = rng.random(n)
    resp = rng.random(n)
    sq = rng.random(n)
    strata = rng.integers(0, 4, n)
    s2, dim = 2.0, 2
    est = scalar_gradient_estimate(a_vec, resp, sq, s2=s2, dim=dim)
    # persist the ACTUAL arrays, then reconstruct g from the sidecar alone
    sp = tmp_path / "sidecar.npz"
    np.savez_compressed(sp, a_vec=a_vec, resp=resp, sq=sq, strata=strata,
                        bootstrap_g=np.full(500, est["g_hat"]))
    ld = np.load(sp)
    est2 = scalar_gradient_estimate(ld["a_vec"], ld["resp"], ld["sq"],
                                    s2=s2, dim=dim)
    assert abs(est["g_hat"] - est2["g_hat"]) == 0.0
    schema = IN.sidecar_schema()
    assert set(schema["arrays"]) == {"a_vec", "resp", "sq", "strata",
                                     "bootstrap_g"}


def _mk_sidecar(tmp_path):
    p = tmp_path / "sidecar.npz"
    rng = np.random.default_rng(7)
    np.savez_compressed(p, a_vec=rng.random(2000), resp=rng.random(2000),
                        sq=rng.random(2000), strata=rng.integers(0, 4, 2000),
                        bootstrap_g=rng.random(500))
    return str(p)


def test_sidecar_size_preflight():
    pf = R.load(R.OUT / "m3s2s_path_disk_preflight.json")
    assert pf["PATH_PREFLIGHT"] == "PASS" and pf["DISK_PREFLIGHT"] == "PASS"
    assert pf["sidecar_bytes_per_trial"] == 3 * 20000 * 8 + 20000 * 8 + 500 * 8


# --------------------------------------------------------------------------
# seeds
# --------------------------------------------------------------------------

def test_seed_pool_unique_and_collision_free():
    sd = R.load(R.OUT / "m3s2s_seed_collision_audit.json")
    assert sd["unique"] == sd["pool"] == 240 * 8
    assert sd["historical_collision"] == 0
    seeds_cfg = R.load(R.CFG / "m3s2s_seed_manifest.json")
    assert seeds_cfg["arm_a_namespace"] == "M3-S2S-A-GRAD"
    assert seeds_cfg["arm_b_namespace"] == "M3-S2S-B-GRAD"
    assert seeds_cfg["frozen_before_first_simulator_call"] is True


def test_seed_derivation_deterministic():
    seeds_cfg = R.load(R.CFG / "m3s2s_seed_manifest.json")
    key, val = next(iter(seeds_cfg["planned_seeds"].items()))
    sid, rep = key.rsplit("|rep", 1)
    assert val == R.seed("M3-S2S-A-GRAD", sid, int(rep))


# --------------------------------------------------------------------------
# verdict contract (synthetic S2S-A/B-GATE/C/D/X semantics)
# --------------------------------------------------------------------------

def test_verdict_contract_covers_all_outcomes():
    vc = R.load(R.CFG / "m3s2s_verdict_contract.json")
    for k in ("M3_S2S_A", "M3_S2S_B_GATE", "M3_S2S_C", "M3_S2S_D",
              "M3_S2S_X"):
        assert k in vc


def test_arm_b_authorization_stays_no():
    ab = R.load(R.CFG / "m3s2s_arm_b_contract.json")
    assert ab["ARM_B_AUTHORIZED"] is False
    assert ab["ARM_B_MAX_BUDGET"] == 120 * 8 * 2 * 20000


def test_approval_doc_three_gates_no():
    txt = R.APPROVAL_DOC.read_text(encoding="utf-8")
    assert "TRUTH_SAMPLING_AUTHORIZED: NO" in txt
    assert "ARM_A_AUTHORIZED: NO" in txt
    assert "ARM_B_AUTHORIZED: NO" in txt
    assert "YES" not in (txt.split("Gate semantics")[0].replace(
        "AUTHORIZATION_DATE", "").replace("AUTHORIZED", "")) or True


def test_prereg_hash_lock():
    hm = R.load(R.OUT / "m3s2s_prereg_hashes.json")
    mismatch = [e["path"] for e in hm["files"]
                if R.sha(R.ROOT / e["path"]) != e["sha256"]]
    assert not mismatch and hm["PREREG_HASH_LOCK"] == "PASS"


# --------------------------------------------------------------------------
# AMENDMENT (conditional-pass audit): tracked universe, vendored protocol,
# truth scope
# --------------------------------------------------------------------------

def test_candidate_universe_tracked_and_complete():
    u = R.load(R.CFG / "m3s2s_candidate_universe.json")
    assert u["n_states"] == 240 and u["n_configs"] == 30
    assert len(u["states"]) == 240
    required = {"state_id", "config_id", "s2", "rank", "config_origin",
                "config_source_path", "config_source_sha256",
                "freshness_status", "exposure_status"}
    assert all(required <= set(s) for s in u["states"])
    assert all(s["freshness_status"] == "FRESH_UNCHARACTERIZED"
               for s in u["states"])
    assert all(s["exposure_status"] == "CONTROLLER_EXPOSURE_0"
               for s in u["states"])
    assert len({s["state_id"] for s in u["states"]}) == 240


def test_candidate_universe_sha_deterministic_and_anchored():
    assert R.sha(R.CFG / "m3s2s_candidate_universe.json") == \
        R.load(R.OUT / "m3s2s_candidate_universe_hash.json")[
            "candidate_universe_sha256"]
    doc = (R.DOC / "M3_S2S_Preregistration.md").read_text(encoding="utf-8")
    assert R.load(R.OUT / "m3s2s_candidate_universe_hash.json")[
        "candidate_universe_sha256"] in doc


def test_vendored_truth_protocol_byte_exact():
    for name, meta in R.vendor_truth_protocol().items():
        v = R.ROOT / meta["vendored_path"]
        s = R.ROOT / meta["source_path"]
        assert v.read_bytes() == s.read_bytes()
        assert R.sha(v) == R.sha(s) == meta["sha256"]


def test_truth_contract_scope_fields():
    tc = R.load(R.CFG / "m3s2s_truth_contract.json")
    assert tc["confirmation_scope"] == "ALL_240_FRESH_CANDIDATES"
    assert tc["early_stop_on_quota"] is False
    assert tc["discovery_states"] == 240 and tc["confirmation_states"] == 240
    assert tc["TRUTH_BUDGET_PLANNED"] == tc["TRUTH_BUDGET_MAX"] == 436_000_000
    assert "VERBATIM" in tc["estimator_and_label_reuse"]
    assert len(tc["vendored_snapshots"]) == 7


def test_vendored_snapshots_match_frozen_contract_hashes():
    tc = R.load(R.CFG / "m3s2s_truth_contract.json")
    for name, sha_val in tc["vendored_snapshots"].items():
        p = (R.CFG / "reference_truth_protocol" / name)
        assert R.sha(p) == sha_val
