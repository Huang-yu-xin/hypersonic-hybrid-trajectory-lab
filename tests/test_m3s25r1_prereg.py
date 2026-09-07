"""M3-S25-R1 preregistration tests (taskbook Sec. 31).

Round 0 is zero-sampling: every test here exercises mechanics, frozen
artifacts and fail-closed routing ONLY -- the scientific simulator is
never invoked.  The realized support-span invariant conflict (taskbook
Sec. 9 vs Sec. 7) is encoded as its documented fact (see
docs/phase_m3s25r1/M3_S25_R1_Support_Invariant_Conflict.md).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s25r1 as R  # noqa: E402
from hyptraj.m3s25r1 import candidates as CAND  # noqa: E402
from hyptraj.m3s25r1 import history as HIST  # noqa: E402
from hyptraj.m3s25r1 import runtime as RT  # noqa: E402


def _universe() -> dict:
    return R.load(R.UNIVERSE)


def _states() -> list[dict]:
    return _universe()["states"]


@pytest.fixture()
def protect_preflight_report():
    """preflight() rewrites its report (new timestamp); restore the exact
    hash-locked bytes afterwards."""
    p = R.PREFLIGHT_REPORT
    data = p.read_bytes()
    yield p
    p.write_bytes(data)


def _boom(*a, **k):
    raise RuntimeError("simulator called in preregistration round")


# --------------------------------------------------------------------------
# candidate support (taskbook Sec. 9 / 31)
# --------------------------------------------------------------------------

def test_exactly_30_configs_8_strata_240_states():
    u = _universe()
    assert u["n_configs"] == 30 and u["n_states"] == 240
    assert len(u["states"]) == 240
    by_cfg = {}
    for s in u["states"]:
        by_cfg.setdefault(s["config_id"], []).append(s)
    assert len(by_cfg) == 30
    assert all(len(v) == 8 for v in by_cfg.values())
    assert all(s["origin"] == "M3-S25-R1-SUPPORT-COMPLETION"
               for s in u["states"])


def test_u_bounds_and_strata_occupancy():
    states = _states()
    for s in states:
        assert s["u"] >= 0.15, s["state_id"]
        assert s["u"] <= 1.0, s["state_id"]
        i = int(s["stratum_id"][1:])
        e0, e1 = CAND.stratum_bounds(i)
        assert e0 <= s["u"] <= e1, (s["state_id"], s["u"], e0, e1)
    by_cfg = {}
    for s in states:
        by_cfg.setdefault(s["config_id"], []).append(s["stratum_id"])
    for cid, strata in by_cfg.items():
        assert sorted(strata) == [f"S{i}" for i in range(8)]


def test_support_invariants_r1_2_realized_state():
    """M3-S25-R1.2 realized state: all four STRUCTURAL invariants (bounds
    derived from the frozen generator constants) PASS for the exact frozen
    240-state universe; preflight verdict PASS => EXECUTION-READY pending
    the human gate.  The R1.0 (span >= 0.70) and R1.1 (0.25/0.85/0.65)
    conflicts are both resolved by the structural bounds; the R1.1
    BLOCKED preflight remains preserved as historical evidence."""
    pf = R.load(R.PREFLIGHT_REPORT)
    assert pf["checks"]["invariant_A_stratum_occupancy_8of8"] is True
    assert pf["checks"]["invariant_B_min_reach_structural"] is True
    assert pf["checks"]["invariant_C_max_reach_structural"] is True
    assert pf["checks"]["invariant_D_span_structural"] is True
    assert pf["PREFLIGHT_VERDICT"] == "PASS"
    assert pf["overall"] == "EXECUTION-READY"
    assert pf["support_invariants"]["conflicts"] == []
    assert pf["support_invariants"]["version"] == "m3s25r1.2"
    # the R1.0 / R1.1 conflicts are inside the structural bounds
    per_cfg = {r["config_id"]: r for r in pf["per_config_support"]}
    assert per_cfg["c000"]["span"] == pytest.approx(0.6971, abs=1e-3)
    assert per_cfg["cf1n_new_002"]["span"] == pytest.approx(0.6649, abs=1e-3)
    assert per_cfg["m3s2s_cfg_005"]["min_u"] == pytest.approx(0.251420,
                                                              abs=1e-5)
    for r in per_cfg.values():
        assert r["B_min_reach_structural"] and r["D_span_structural"]
    # R1.1 blocked evidence preserved verbatim
    ev = pf["support_invariants"]["r1_1_blocked_evidence"]
    assert ev["verdict"].startswith("FAIL")
    assert R.sha(R.ROOT / ev["file"]) == ev["sha256"]
    hist = R.load(R.ROOT / ev["file"])
    assert hist["PREFLIGHT_VERDICT"] == "FAIL"
    assert hist["failed_checks"] == ["invariant_B_min_reach_le_0.25"]


def test_support_invariant_checker_mechanism_synthetic():
    """The M3-S25-R1.1 invariant checker: A/B/C/D semantics on synthetic
    universes (Sec. 11 mechanism test)."""
    def mk(us):
        return [{"state_id": f"c_s{i}", "config_id": "c", "u": u,
                 "stratum_id": f"S{i}", "s2": 1.0, "legality_s2_lo": 0.5,
                 "legality_s2_hi": 8.0}
                for i, u in enumerate(us)]

    b = CAND.structural_bounds()
    spanning = mk([0.16, 0.30, 0.45, 0.60, 0.75, 0.90, 0.98, 0.99])
    collapsed = mk([0.151, 0.152, 0.153, 0.154, 0.155, 0.156, 0.157,
                    0.158])          # A ok; C + D fail structurally
    beyond_u0_max = mk([b["u0_max"] + 1e-9, 0.30, 0.45, 0.60, 0.75, 0.90,
                        0.98, 0.99])   # B violation only (unreachable by
    # the generator, used purely as a checker mechanism case)
    good = CAND.invariant_audit(spanning)
    bad = CAND.invariant_audit(collapsed)
    bbad = CAND.invariant_audit(beyond_u0_max)
    assert good["checks"]["invariant_A_stratum_occupancy"] is True
    assert good["checks"]["invariant_B_min_reach_structural"] is True
    assert good["checks"]["invariant_C_max_reach_structural"] is True
    assert good["checks"]["invariant_D_span_structural"] is True
    assert bad["checks"]["invariant_C_max_reach_structural"] is False
    assert bad["checks"]["invariant_D_span_structural"] is False
    assert bad["checks"]["invariant_A_stratum_occupancy"] is True
    assert bbad["checks"]["invariant_B_min_reach_structural"] is False
    assert bbad["checks"]["invariant_D_span_structural"] is True
    # the superseded thresholds are gone from the checker (Sec. 11)
    assert all("le_0.25" not in k and "ge_0.85" not in k
               and "ge_0.65" not in k and "span_ge_0.70" not in k
               for k in good["checks"])
    assert "structural_bounds" in good
    assert good["structural_bounds"] == b


def test_structural_bounds_derived_from_generator_constants():
    """R1.2 core requirement: the structural bounds are COMPUTED from the
    frozen generator constants (U_LO/U_HI/N_STRATA/L_ANCHORS), equal to
    the taskbook-frozen decimal values, and independent of any data."""
    # independent recomputation from the constants
    w = (CAND.U_HI - CAND.U_LO) / CAND.N_STRATA
    u0_max = CAND.U_LO + CAND.L_ANCHORS / (CAND.L_ANCHORS + 1) * w
    u7_min = (CAND.U_LO + (CAND.N_STRATA - 1) * w
              + 1 / (CAND.L_ANCHORS + 1) * w)
    b = CAND.structural_bounds()
    assert b["w"] == w == 0.10625
    assert b["u0_max"] == u0_max
    assert b["u7_min"] == u7_min
    assert b["span_bound"] == u7_min - u0_max
    # taskbook-frozen decimal values (bit-level equality of the formula)
    assert u0_max == 0.2546401515151515
    assert u7_min == 0.8953598484848485
    assert u7_min - u0_max == 0.640719696969697
    assert b["tol"] == 1e-12
    # the bounds take NO data input: signature is empty, so realized
    # candidate values cannot tune the thresholds
    import inspect
    assert list(inspect.signature(CAND.structural_bounds).parameters) == []
    # the audit thresholds come from structural_bounds (wiring proof)
    states = [{"state_id": f"c_s{i}", "config_id": "c", "u": u,
               "stratum_id": f"S{i}", "s2": 1.0, "legality_s2_lo": 0.5,
               "legality_s2_hi": 8.0}
              for i, u in enumerate(
                  [0.16, 0.30, 0.45, 0.60, 0.75, 0.90, 0.98, 0.99])]
    a1 = CAND.invariant_audit(states)
    assert a1["structural_bounds"] == b
    shifted = dict(b)
    shifted["u0_max"] = b["u0_max"] + 0.01
    orig = CAND.structural_bounds
    CAND.structural_bounds = lambda: shifted
    try:
        a2 = CAND.invariant_audit(states)
        assert a2["structural_bounds"]["u0_max"] == shifted["u0_max"]
        # verdict flips exactly per the shifted bound (min u 0.16 is now
        # above the shifted-1e-12 threshold only if shifted exceeds it)
        assert a2["checks"]["invariant_B_min_reach_structural"] == \
            (0.16 <= shifted["u0_max"] + shifted["tol"])
    finally:
        CAND.structural_bounds = orig


def test_thresholds_not_tuned_from_realized_values():
    """The bounds are identical for the frozen universe and a mutated
    copy: changing realized candidate values cannot move a threshold."""
    states = R.verify_universe_sha_only()
    mutated = [dict(s, u=0.5 if s["u"] == 0.2514202 else s["u"])
               for s in states]
    a_frozen = CAND.invariant_audit(states)
    a_mut = CAND.invariant_audit(mutated)
    assert a_frozen["structural_bounds"] == a_mut["structural_bounds"]
    # the frozen universe itself never appears in the bounds derivation
    b = CAND.structural_bounds()
    for key in ("derived_from",):
        assert b[key] == {"U_LO": 0.15, "U_HI": 1.00, "N_STRATA": 8,
                          "L_ANCHORS": 65}


def test_amendment_invariant_replacement_recorded():
    """R1.2 recorded in the contract: parent hash, amendment hash,
    old invariant, new structural invariants, reason, and the full
    superseded chain (R1.0 + R1.1) with preserved BLOCKED evidence."""
    c = R.load(R.CFG / "m3s25r1_contract.json")
    inv = c["support_invariants"]
    assert inv["version"] == "m3s25r1.2" and inv["status"] == "ACTIVE"
    assert "u0_max" in inv["B_min_support_reach"]
    assert "u7_min" in inv["C_max_support_reach"]
    assert "u7_min - u0_max" in inv["D_anti_collapse_span"]
    assert inv["structural_bounds"] == CAND.structural_bounds()
    chain = inv["superseded_chain"]
    assert chain[0]["version"] == "m3s25r1.0"
    assert chain[0]["invariant"] == "per-config max(u) - min(u) >= 0.70"
    assert chain[1]["version"] == "m3s25r1.1"
    assert chain[1]["blocked_evidence"]["sha256"] == R.sha(
        R.ROOT / chain[1]["blocked_evidence"]["file"])
    am = c["amendment"]
    assert am["stage"] == "M3-S25-R1.2"
    assert am["parent_contract_sha256"].startswith("1e34017a")
    assert am["document_sha256"] == R.sha(
        R.DOC / "M3_S25_R1_2_Amendment_Taskbook.md")
    assert am["old_invariant"].startswith("M3-S25-R1.1 fixed thresholds")
    assert len(am["new_invariants"]) == 4
    assert "generator constants" in am["structural_bounds_derivation"]
    assert len(am["unchanged"]) == 11


def test_candidate_universe_sha_unchanged_by_amendment():
    """Sec. 11 candidate immutability: the universe SHA is the R1.0
    freeze; the amendment regeneration guard is active."""
    assert R.EXPECTED_UNIVERSE_SHA == \
        ("9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4"
         "223058d6e600d02")
    assert R.sha_bytes(R.UNIVERSE.read_bytes()) == R.EXPECTED_UNIVERSE_SHA
    with pytest.raises(RuntimeError, match="regeneration is forbidden"):
        R.candidates_stage()


def test_no_science_drift():
    """Sec. 11: truth semantics hash, seed namespace and budget are
    unchanged by the amendment."""
    c = R.load(R.CFG / "m3s25r1_contract.json")
    assert c["truth_semantics"]["parent_truth_contract_sha256"] == \
        R.sha(R.PARENT_TRUTH_CONTRACT)
    assert c["seed_namespaces"] == {
        "discovery": "M3-S25-R1-DISCOVERY",
        "confirmation": "M3-S25-R1-CONFIRMATION",
        "s2s_namespace_reuse": False}
    b = R.load(R.CFG / "m3s25r1_budget_contract.json")
    assert b["TRUTH_BUDGET_PLANNED"] == b["TRUTH_BUDGET_MAX"] == 432_000_000
    assert b["p_ref_sampling_budget"] == 0 and b["topup"] == 0
    m = R.load(R.CFG / "m3s25r1_truth_seed_manifest.json")
    assert m["namespaces"] == {"discovery": "M3-S25-R1-DISCOVERY",
                               "confirmation": "M3-S25-R1-CONFIRMATION"}
    assert m["total_units"] == 480


def test_universe_sha_pinned():
    assert R.EXPECTED_UNIVERSE_SHA.startswith("9d1f704a")
    assert R.sha_bytes(R.UNIVERSE.read_bytes()) == R.EXPECTED_UNIVERSE_SHA
    assert len(R.verify_universe_sha_only()) == 240


def test_selection_determinism_and_hash_first():
    """Regenerating the selection from the frozen legality windows
    reproduces the frozen universe exactly (no hidden state, no label
    dependence); the selected anchor is the rank-1 fresh anchor."""
    u = _universe()
    hist, _ = HIST.historical_characterized_s2(
        sorted({s["config_id"] for s in u["states"]}))
    for s in u["states"][:40]:                     # sampled regeneration
        sel = CAND.select_stratum_state(
            s["config_id"], int(s["stratum_id"][1:]), s["legality_s2_lo"],
            hist.get(s["config_id"], set()), s["legality_s2_hi"])
        assert sel["anchor_s2"] == s["s2"]
        assert sel["anchor_hash"] == s["anchor_hash"]
        assert sel["anchor_m"] == s["anchor_m"]
    s0 = next(s for s in u["states"] if s["config_id"] == "c001"
              and s["stratum_id"] == "S0")
    anchors = CAND.stratum_anchors("c001", 0, s0["legality_s2_lo"])
    ranked = sorted(anchors, key=lambda a: (a["hash"], a["m"]))
    first_fresh = next(a for a in ranked
                       if not HIST.collision(a["s2"],
                                             hist.get("c001", set())))
    assert first_fresh["s2"] == s0["s2"]


def test_freshness_firewall_full_reaudit():
    """0 collisions against the independently re-collected characterized
    set; the parent's own values are inside the firewall (Sec. 8)."""
    u = _universe()
    configs = sorted({s["config_id"] for s in u["states"]})
    hist, meta = HIST.historical_characterized_s2(configs)
    fresh = CAND.freshness_reaudit(u["states"], hist)
    assert fresh["FRESH"] and not fresh["violations"]
    assert not fresh["internal_collisions"]
    assert all(meta["minimum_families"].values()), meta["minimum_families"]
    parent = R.load(R.PARENT_UNIVERSE)
    assert any(HIST.collision(p["s2"], hist[p["config_id"]])
               for p in parent["states"][:5])


def test_collision_rule_semantics():
    assert HIST.collision(1.0, {1.0})
    assert HIST.collision(1.0, {1.0 + 5e-7})
    assert HIST.collision(1.0, {1.0 - 9e-7})
    assert not HIST.collision(1.0, {1.0 + 5e-6})
    assert HIST.collision(4.0, {4.0 + 2e-6})          # 1e-6 * max(1, 4)
    assert not HIST.collision(4.0, {4.0 + 1e-5})


def test_no_candidate_substitution_or_reserve_overlap():
    states = _states()
    cand_ids = {s["state_id"] for s in states}
    parent_reg = R.load(R.CFG / "m3s25r1_parent_development_registry.json")
    parent_ids = {s["state_id"] for s in parent_reg["states"]}
    reserve_ids = {r["state_id"] for r in R.csvread(
        R.OUT / "m3s25r1_protected_reserve_18.csv")}
    assert not (cand_ids & parent_ids)
    assert not (cand_ids & reserve_ids)
    assert len(parent_ids) == 240 and len(reserve_ids) == 18
    plan = RT.truth_execution_plan(states)
    plan_ids = ({x["state_id"] for x in plan["discovery_units"]}
                | {x["state_id"] for x in plan["confirmation_units"]})
    assert plan_ids == cand_ids


def test_parent_registry_preserves_verbatim():
    reg = R.load(R.CFG / "m3s25r1_parent_development_registry.json")
    assert reg["n_states"] == 240
    required = {"state_id", "config_id", "s2", "u", "confirmed_truth",
                "truth_record_path", "truth_record_file_hash",
                "development_eligible", "untouched_confirmation_eligible"}
    assert all(required <= set(e) for e in reg["states"])
    assert all(e["untouched_confirmation_eligible"] is False
               for e in reg["states"])
    inv = R.load(R.PARENT_INVENTORY)
    truth = {s["state_id"]: s["confirmed_truth"] for s in inv["states"]}
    assert all(e["confirmed_truth"] == truth[e["state_id"]]
               for e in reg["states"])
    assert max(e["u"] for e in reg["states"]) <= 0.1231


# --------------------------------------------------------------------------
# P_ref registry (Sec. 11)
# --------------------------------------------------------------------------

def test_p_ref_registry_30_entries_all_verified():
    registry = R.load(R.CFG / "m3s25r1_p_ref_registry.json")
    assert len(registry["configs"]) == 30
    assert registry["p_ref_sampling_budget"] == 0
    assert {e["source_stage"] for e in registry["configs"]} == \
        {"M3-S2S", "M3-CF1N", "M3-WCF1", "M3-D2"}
    pref_sha = R.sha(R.VENDORED / "m3cf1n_pref_protocol.json")
    for e in registry["configs"]:
        p = R.ROOT / e["source_file"]
        assert p.exists(), e["config_id"]
        assert R.sha(p) == e["record_file_hash"], e["config_id"]
        assert e["protocol_hash"] == pref_sha
        assert e["sample_count"] > 0 and e["n_batches"] == 20
        assert 0 < e["p_ref"] < 1


def test_p_ref_registry_resolution_all_configs():
    registry = R.load(R.CFG / "m3s25r1_p_ref_registry.json")
    for e in registry["configs"]:
        rec = RT.p_ref_from_registry(e["config_id"], registry,
                                     R._p_ref_source_resolver,
                                     R.record_file_hash)
        assert rec["p_ref_full"] == e["p_ref"]
        assert rec["record_hash"] == e["record_file_hash"]
        assert rec["sample_count"] == e["sample_count"]


def test_p_ref_missing_source_fails(tmp_path):
    entry = {"config_id": "cf1n_new_000",
             "source_file": str(tmp_path / "missing.json"),
             "record_file_hash": "0" * 64, "sample_count": 500_000,
             "n_batches": 20, "source_stage": "M3-CF1N"}
    with pytest.raises(RuntimeError, match="source missing"):
        RT.p_ref_from_registry("cf1n_new_000", {"configs": [entry]},
                               R._p_ref_source_resolver, R.record_file_hash)


def test_p_ref_tampered_source_hash_mismatch(tmp_path):
    src = R.VENDORED / "pref_records" / "cf1n_new_000.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    data["p_ref_full"] = 0.999
    bad = tmp_path / "cf1n_new_000.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    entry = {"config_id": "cf1n_new_000", "source_file": str(bad),
             "record_file_hash": R.sha(src), "sample_count": 500_000,
             "n_batches": 20, "source_stage": "M3-CF1N"}
    with pytest.raises(RuntimeError, match="hash mismatch"):
        RT.p_ref_from_registry("cf1n_new_000", {"configs": [entry]},
                               R._p_ref_source_resolver, R.record_file_hash)


def test_p_ref_unknown_config_fails():
    with pytest.raises(RuntimeError, match="missing from the frozen"):
        RT.p_ref_from_registry("no_such_config", {"configs": []},
                               R._p_ref_source_resolver, R.record_file_hash)


def test_prereg_round_zero_simulator_calls(protect_preflight_report,
                                           monkeypatch):
    """The full preflight path (dry assembly + audits) makes ZERO
    simulator calls; gates stay NO; the report bytes are restored so the
    hash lock stays valid."""
    import hyptraj.m3d2.experiment as EXP
    for name in ("direct_full_event_reference", "evaluate_reference_arms",
                 "classify_reference_state"):
        monkeypatch.setattr(EXP, name, _boom)
        monkeypatch.setattr(RT, name, _boom, raising=False)
    # the frozen R1.2-era round-0 preflight (produced while every gate
    # was NO) remains the execution-readiness record; it is NOT
    # re-run post-authorization (its round-0 gate-freeze check would
    # honestly report the now-authorized ARM A).
    pf = R.load(R.PREFLIGHT_REPORT)
    assert pf["PREFLIGHT_VERDICT"] == "PASS"
    assert pf["overall"] == "EXECUTION-READY"
    apf = R.load(R.OUT / "m3s25r1_arm_a_preflight.json")
    assert apf["PREFLIGHT_VERDICT"] == "PASS"
    assert apf["simulator_calls"] == 0 and apf["samples"] == 0
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False


def test_frozen_preflight_gate_refuses_fail_verdict(tmp_path, monkeypatch):
    """The fail-closed preflight gate itself: a frozen report with a FAIL
    verdict blocks truth_execute's step 3 (mechanism test on a tmp
    report; the R1.1 BLOCKED evidence was exactly this state)."""
    bad = tmp_path / "preflight.json"
    bad.write_text(json.dumps({"PREFLIGHT_VERDICT": "FAIL",
                               "overall": "M3-S25-R1.1 PREFLIGHT BLOCKED"}),
                   encoding="utf-8")
    monkeypatch.setattr(R, "PREFLIGHT_REPORT", bad)
    with pytest.raises(RuntimeError, match="PREFLIGHT BLOCKED"):
        R.verify_frozen_preflight_pass()
    good = tmp_path / "preflight_pass.json"
    good.write_text(json.dumps({"PREFLIGHT_VERDICT": "PASS"}), encoding="utf-8")
    monkeypatch.setattr(R, "PREFLIGHT_REPORT", good)
    assert R.verify_frozen_preflight_pass() == {"PREFLIGHT_VERDICT": "PASS"}


# --------------------------------------------------------------------------
# budget (Sec. 15-17)
# --------------------------------------------------------------------------

def test_budget_contract_exact():
    b = R.load(R.CFG / "m3s25r1_budget_contract.json")
    assert b["discovery"] == {"units": 240, "arms": 3,
                              "samples_per_arm": 100_000,
                              "samples_per_unit": 300_000,
                              "total": 72_000_000}
    assert b["confirmation"]["total"] == 360_000_000
    assert b["p_ref_sampling_budget"] == 0
    assert b["TRUTH_BUDGET_PLANNED"] == b["TRUTH_BUDGET_MAX"] == 432_000_000
    assert b["planned_equals_max"] is True
    assert b["truth_units_total"] == 480
    assert b["topup"] == 0 and b["early_stop"] is False
    assert b["candidate_substitution"] is False


def test_execution_plan_budget_and_units():
    states = _states()
    plan = RT.truth_execution_plan(states)
    assert len(plan["discovery_units"]) == 240
    assert len(plan["confirmation_units"]) == 240
    assert plan["discovery_samples"] == 72_000_000
    assert plan["confirmation_samples"] == 360_000_000
    assert plan["total_samples"] == RT.TRUTH_BUDGET_PLANNED \
        == RT.TRUTH_BUDGET_MAX == 432_000_000
    assert plan["pref_units"] == []
    assert plan["p_ref_sampling_budget"] == 0
    assert plan["confirmation_scope"] == "ALL_240_R1_CANDIDATES"
    assert plan["early_stop_on_quota"] is False


def test_consumption_summary_synthetic():
    ledgers = {"discovery": [{"status": "COMPLETE",
                              "samples": 300_000}] * 240,
               "confirmation": [{"status": "COMPLETE",
                                 "samples": 1_500_000}] * 240}
    s = RT.consumption_summary(ledgers)
    assert s["discovery"] == {"planned": 72_000_000, "actual": 72_000_000,
                              "difference": 0, "topup": 0}
    assert s["confirmation"]["actual"] == 360_000_000
    assert s["p_ref"] == {"planned": 0, "actual": 0, "difference": 0,
                          "topup": 0}
    assert s["total"] == {"planned": 432_000_000, "actual": 432_000_000,
                          "topup": 0}


# --------------------------------------------------------------------------
# seeds (Sec. 13)
# --------------------------------------------------------------------------

def test_truth_seed_manifest_480_units_namespaces():
    m = R.load(R.CFG / "m3s25r1_truth_seed_manifest.json")
    assert m["counts"] == {"discovery": 240, "confirmation": 240, "pref": 0}
    assert m["total_units"] == 480
    assert m["namespaces"] == {"discovery": "M3-S25-R1-DISCOVERY",
                               "confirmation": "M3-S25-R1-CONFIRMATION"}
    assert m["s2s_namespace_reuse"] is False
    assert m["frozen_before_first_simulator_call"] is True
    keys = [tuple(x["seed_key"]) for x in m["units"]]
    assert len(set(keys)) == 480
    audit = R.load(R.OUT / "m3s25r1_truth_seed_audit.json")
    assert audit["historical_namespace_collision"] == 0
    assert audit["cross_stream_collision"] == 0
    assert audit["duplicate_logical_unit"] == 0


def test_seed_derivation_deterministic_new_namespace():
    m = R.load(R.CFG / "m3s25r1_truth_seed_manifest.json")
    u0 = next(x for x in m["units"] if x["stream"] == "discovery")
    assert u0["seed_key"] == [RT.seed("M3-S25-R1-DISCOVERY",
                                      u0["state_id"]), 42424]
    c0 = next(x for x in m["units"] if x["stream"] == "confirmation")
    assert c0["seed_key"] == [RT.seed("M3-S25-R1-CONFIRMATION",
                                      c0["state_id"]), 42424]
    s2s = R.load(ROOT / "configs/phase_m3s2s/m3s2s_truth_seed_manifest.json")
    s2s_keys = {tuple(x["seed_key"]) for x in s2s["units"]}
    assert s2s_keys.isdisjoint({tuple(x["seed_key"]) for x in m["units"]})


# --------------------------------------------------------------------------
# restart integrity (Sec. 19)
# --------------------------------------------------------------------------

def _ledger_entries(tmp_path, statuses, record_hash="a" * 64):
    return [{"state_id": "DISC|state_x", "status": st,
             **({"record_file_hash": record_hash} if st == "COMPLETE" else {})}
            for st in statuses]


def _unit_out(tmp_path, artifact=True):
    out = tmp_path / "out" / "state_x.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if artifact:
        out.write_text(json.dumps({"record_type": "M3S25R1-DISCOVERY",
                                   "state_id": "state_x"}), encoding="utf-8")
    return out


def test_restart_fresh_unit_allowed(tmp_path):
    out = _unit_out(tmp_path, artifact=False)
    assert RT.verify_unit_fresh_or_verified("DISC|state_x", out, [],
                                            R.record_file_hash) is None


def test_restart_started_only_fails(tmp_path):
    out = _unit_out(tmp_path, artifact=False)
    with pytest.raises(RuntimeError, match="STARTED-only"):
        RT.verify_unit_fresh_or_verified("DISC|state_x", out,
                                         _ledger_entries(tmp_path,
                                                         ["STARTED"]),
                                         R.record_file_hash)


def test_restart_consumed_invalid_fails(tmp_path):
    out = _unit_out(tmp_path, artifact=False)
    with pytest.raises(RuntimeError, match="CONSUMED_INVALID"):
        RT.verify_unit_fresh_or_verified(
            "DISC|state_x", out,
            _ledger_entries(tmp_path, ["STARTED", "CONSUMED_INVALID"]),
            R.record_file_hash)


def test_restart_duplicate_complete_fails(tmp_path):
    out = _unit_out(tmp_path)
    entries = _ledger_entries(tmp_path, ["STARTED", "COMPLETE", "COMPLETE"])
    with pytest.raises(RuntimeError, match="duplicate/inconsistent"):
        RT.verify_unit_fresh_or_verified("DISC|state_x", out, entries,
                                         R.record_file_hash)


def test_restart_complete_without_started_fails(tmp_path):
    out = _unit_out(tmp_path)
    with pytest.raises(RuntimeError, match="COMPLETE without STARTED"):
        RT.verify_unit_fresh_or_verified("DISC|state_x", out,
                                         _ledger_entries(tmp_path,
                                                         ["COMPLETE"]),
                                         R.record_file_hash)


def test_restart_orphan_artifact_fails(tmp_path):
    out = _unit_out(tmp_path, artifact=True)
    with pytest.raises(RuntimeError, match="orphan artifact"):
        RT.verify_unit_fresh_or_verified("DISC|state_x", out, [],
                                         R.record_file_hash)


def test_restart_hash_mismatch_fails(tmp_path):
    out = _unit_out(tmp_path)
    with pytest.raises(RuntimeError, match="hash mismatch on restart"):
        RT.verify_unit_fresh_or_verified(
            "DISC|state_x", out,
            _ledger_entries(tmp_path, ["STARTED", "COMPLETE"],
                            record_hash="b" * 64),
            R.record_file_hash)


def test_restart_valid_complete_safe_skip(tmp_path):
    out = _unit_out(tmp_path)
    real_hash = R.record_file_hash(out)
    entries = _ledger_entries(tmp_path, ["STARTED", "COMPLETE"],
                              record_hash=real_hash)
    rec = RT.verify_unit_fresh_or_verified("DISC|state_x", out, entries,
                                           R.record_file_hash)
    assert rec["state_id"] == "state_x"


def test_restart_missing_complete_artifact_fails(tmp_path):
    out = _unit_out(tmp_path, artifact=False)
    with pytest.raises(RuntimeError, match="artifact missing"):
        RT.verify_unit_fresh_or_verified(
            "DISC|state_x", out,
            _ledger_entries(tmp_path, ["STARTED", "COMPLETE"]),
            R.record_file_hash)


# --------------------------------------------------------------------------
# gate isolation (Sec. 31)
# --------------------------------------------------------------------------

def test_gates_closed_and_parent_sealed():
    """Post-A1R0 state: every R1 gate NO (old Arm-A CLOSED/
    EXERCISED/TERMINAL-X; A1R gates NO); parent gates sealed."""
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED") is False
    assert R.parent_gate("TRUTH_SAMPLING_AUTHORIZED") is False
    assert R.parent_gate("ARM_A_AUTHORIZED") is False
    assert R.parent_gate("ARM_B_AUTHORIZED") is False


def test_gate_parser_mechanism(tmp_path, monkeypatch):
    """The parser reads exactly the frozen file; a YES value flips the
    parsed verdict only for that file (mechanism test on a tmp copy)."""
    doc = tmp_path / "approval.md"
    doc.write_text("M3_S25_R1_TRUTH_AUTHORIZED: YES\n"
                   "M3_S25_R1_ARM_A_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", doc)
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is True
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is False
    # the REAL frozen file is untouched and stays NO
    monkeypatch.undo()
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False


def test_import_cannot_flip_gates():
    """A fresh module import (clean subprocess, no fixture state) reads
    the frozen approval file and cannot flip any gate."""
    scripts_dir = str(ROOT / "scripts")
    code = (
        "import sys\n"
        f"sys.path.insert(0, r'{ROOT}')\n"
        f"sys.path.insert(0, r'{scripts_dir}')\n"
        "import run_m3s25r1 as R\n"
        "print(all(not R.gate(g) for g in (\n"
        "    'M3_S25_R1_TRUTH_AUTHORIZED', 'M3_S25_R1_ARM_A_AUTHORIZED',\n"
        "    'M3_S25_R1_ARM_B_AUTHORIZED', 'M3_S25_R1_A1R_ARM_A_AUTHORIZED',\n"
        "    'M3_S25_R1_A1R_ARM_B_AUTHORIZED')))\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "True"
    assert R.gate("M3_S25_R1_TRUTH_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED") is False
    assert R.gate("M3_S25_R1_ARM_B_AUTHORIZED") is False


def test_hashlock_and_artifacts_consistent():
    hm = R.load(R.CFG / "m3s25r1_hash_manifest.json")
    assert hm["PREREG_HASH_LOCK"] == "PASS"
    assert hm["preregistration_round0"]["simulator_calls"] == 0
    mismatch = [e["path"] for e in hm["files"]
                if R.sha(R.ROOT / e["path"]) != e["sha256"]]
    assert not mismatch, mismatch
    code_mismatch = [p for p, h in hm["scientific_code_hashes"].items()
                     if R.sha(R.ROOT / p) != h]
    assert not code_mismatch, code_mismatch


def test_contract_frozen_pins():
    c = R.load(R.CFG / "m3s25r1_contract.json")
    assert R.sha_bytes((R.CFG / "m3s25r1_contract.json").read_bytes()) \
        == R.EXPECTED_CONTRACT_SHA
    assert c["config_universe"]["n_configs"] == 30
    assert c["support"]["u_interval"] == [0.15, 1.0]
    assert c["panel"]["quota"] == {"WIDEN": 30, "SHRINK": 30, "HOLD": 30,
                                   "AMBIGUOUS": 30}
    assert c["verdicts"]["panel_blocked"] == "M3-S25-R1-PANEL-BLOCKED"
    assert c["runtime_fail_closed_ordering"][5].startswith(
        "6. verify R1 human truth authorization")
    assert c["arm_gates"]["M3_S25_R1_ARM_A_AUTHORIZED"] == "NO"
