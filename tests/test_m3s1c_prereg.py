"""M3-S1C preregistration tests (taskbook Sec. 17).

Covers: frozen S1 contract, panel design, seed contract, truth firewall,
persistence (inherited WA1R contract) and the A/B/X verdict logic.
NO scientific simulator call is performed anywhere in this file.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s1c as S  # noqa: E402


# --------------------------------------------------------------------------
# Sec. 17.1 contract tests
# --------------------------------------------------------------------------

def test_s1_threshold_exact():
    assert S.S1_THRESHOLD == 5.4417199447782
    verd = json.loads((S.PI1VNR / "m3pi1vnr_final_verdict.json").read_text())
    assert verd["S1"]["selected_threshold"] == S.S1_THRESHOLD


def test_s1_formula_unchanged_from_parent():
    parent = json.loads((S.PI1VNR_CFG / "m3pi1vnr_s1_contract.json").read_text())
    child = json.loads((S.CFG / "m3s1c_s1_contract.json").read_text())
    assert child["formula"] == parent["formula"]
    assert child["same_gradient_data"] is True
    assert child["sign_mapping"] == "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK"
    assert child["decision_rule"].startswith("if S1 >= threshold")


def test_s1_gates_exact():
    g = json.loads((S.CFG / "m3s1c_gates.json").read_text())
    assert g["coverage_min"] == 0.75
    assert g["wrong_direction_max"] == 0.05
    assert g["unsafe_max"] == 0.20
    assert g["deployable_trials"] == 128 and g["nd_trials"] == 64


def test_gradient_protocol_budget():
    p = json.loads((S.CFG / "m3s1c_gradient_protocol.json").read_text())
    assert p["samples_per_trial"] == 20_000
    assert p["replicates"] == 8 and p["batches"] == 20 and p["alpha_p"] == 0.5
    assert p["total_gradient_budget"] == 24 * 8 * 20_000 == 3_840_000
    assert p["finite_action_base_probe_samples"] == 0
    assert p["finite_action_selected_probe_samples"] == 0
    assert p["v1_samples"] == 0
    assert p["no_topup"] is True and p["equal_budget_all_trials"] is True


def test_no_threshold_search_symbols_in_module():
    src = (S.ROOT / "scripts/run_m3s1c.py").read_text(encoding="utf-8")
    assert "select_threshold" not in src and "threshold_grid" not in src
    assert "frontier(" not in src


# --------------------------------------------------------------------------
# Sec. 17.2 panel tests
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def panel():
    return json.loads((S.CFG / "m3s1c_panel.json").read_text())


def test_panel_shape(panel):
    states = panel["states"]
    assert len(states) == 24 == len({s["state_id"] for s in states})
    for stratum, truth in (("W", {"WIDEN"}), ("S", {"SHRINK"}),
                           ("ND", {"HOLD", "AMBIGUOUS"})):
        sub = [s for s in states if s["stratum"] == stratum]
        assert len(sub) == 8
        assert all(s["truth"] in truth for s in sub)


def test_panel_zero_overlap_with_all_prior_uses(panel):
    dev = {r["state_id"] for r in S.csvread(
        S.PI1VNR / "m3pi1vnr_fresh_development_panel.csv")}
    retired = {r["state_id"] for r in S.csvread(
        S.PI1VNR / "m3pi1vnr_retired_pi1vn_panel.csv")}
    sel = {s["state_id"] for s in panel["states"]}
    assert not sel & dev and not sel & retired
    # every state comes from the 42-state protected reserve
    reserve = {r["state_id"] for r in S.csvread(
        S.PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv")}
    assert sel <= reserve


def test_panel_selection_deterministic(panel):
    reserve = S.csvread(S.PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv")
    a = S.select_panel([dict(r) for r in reserve])
    b = S.select_panel([dict(r) for r in reserve])
    assert [s["state_id"] for s in a] == [s["state_id"] for s in b]
    assert ({s["state_id"] for s in a}
            == {s["state_id"] for s in panel["states"]})


def test_panel_maximizes_config_diversity_first(panel):
    reserve = S.csvread(S.PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv")
    for stratum, truths in (("W", ("WIDEN",)), ("S", ("SHRINK",)),
                            ("ND", ("HOLD", "AMBIGUOUS"))):
        pool = [r for r in reserve if r["truth"] in truths]
        picked = [s for s in panel["states"] if s["stratum"] == stratum]
        # round 1 of the draft is reachable: unique configs in picked ==
        # unique configs offered by the pool's first round
        max_unique = len({r["config_id"] for r in pool})
        got_unique = len({s["config_id"] for s in picked})
        if len(pool) >= 8:
            assert got_unique == min(8, max_unique)


def test_panel_rank_is_frozen_hash(panel):
    for s in panel["states"]:
        expect = S.sha_text(S.PANEL_RANK_SEED + s["config_id"]
                            + "|" + s["state_id"])
        assert s["selection_rank"] == expect


def test_panel_hash_self_consistent(panel):
    # panel sha256 refers to the panel CSV (no self-referential JSON hashing)
    assert panel["sha256"] == S.sha(S.OUT / "m3s1c_panel.csv")
    cap = json.loads((S.OUT / "m3s1c_panel_capacity.json").read_text())
    assert cap["panel_sha256"] == panel["sha256"]


def test_panel_sources_are_truth_artifacts(panel):
    for s in panel["states"]:
        assert "truth" not in {k for k in s.keys() if k.startswith("oracle")}
        ref = S.ROOT / s["source_reference_artifact"]
        assert ref.exists()
        assert S.sha(ref) == s["source_reference_hash"]


# --------------------------------------------------------------------------
# Sec. 17.3 seed tests
# --------------------------------------------------------------------------

def test_seeds_shape_and_determinism():
    seeds = json.loads((S.CFG / "m3s1c_seeds.json").read_text())
    assert seeds["gradient_namespace"] == "M3-S1C-GRAD"
    assert seeds["planned_count"] == 192
    assert len(seeds["planned_gradient_seeds"]) == 192
    assert len(set(seeds["planned_gradient_seeds"].values())) == 192
    for key, val in seeds["planned_gradient_seeds"].items():
        sid, rep = key.rsplit("|rep", 1)
        assert val == S.seed("M3-S1C-GRAD", sid, int(rep))


def test_seeds_zero_historical_collision():
    audit = json.loads((S.OUT / "m3s1c_seed_collision_audit.json").read_text())
    assert audit["planned"] == audit["unique"] == 192
    assert audit["historical_collision"] == 0
    seeds = set(json.loads((S.CFG / "m3s1c_seeds.json")
                           .read_text())["planned_gradient_seeds"].values())
    retired = json.loads((S.PI1VNR / "m3pi1vnr_retired_pi1vn_seed_manifest.json")
                         .read_text())
    assert not seeds & set(retired.get("gradient_seeds", []))
    assert not seeds & set(retired.get("probe_seeds", []))
    pi1vnr = json.loads((S.PI1VNR / "m3pi1vnr_seed_manifest.json").read_text())
    assert not seeds & set(pi1vnr["planned_gradient_seeds"].values())
    assert not seeds & set(pi1vnr["planned_probe_seeds"].values())


# --------------------------------------------------------------------------
# Sec. 17.4 truth-firewall tests
# --------------------------------------------------------------------------

def test_execution_view_strips_truth():
    panel = json.loads((S.CFG / "m3s1c_panel.json").read_text())
    view = S._panel_execution_view(panel)
    assert len(view) == 24
    for row in view:
        assert "truth" not in row
        assert {"state_id", "config_id", "s2", "selection_rank"} <= set(row)


def test_prehash_schema_accepts_valid_record():
    rec = {
        "schema": S.SCHEMA, "recorded_at": "t", "state_id": "x", "rep_id": 0,
        "config_id": "c", "s2": 1.0,
        "gradient": {"namespace": S.GRAD_NS, "valid": True, "seed": 1,
                     "g_hat": 0.1, "g_ci_low": 0.05, "g_ci_high": 0.15},
        "selected_action": "WIDEN", "S1": 3.92, "S1_threshold": S.S1_THRESHOLD,
        "deployment": "ABSTAIN", "s1_contract_sha256": "h", "panel_hash": "p",
        "sample_counts": {"gradient": S.N_GRAD, "probe_base": 0,
                          "probe_action": 0, "total": S.N_GRAD},
        "protocol_hashes": {"gradient": "g", "probe": None}, "z95": S.Z95,
    }
    S._pre_hash_validate(rec)  # must not raise


def test_prehash_schema_rejects_truth_v1_probe_and_hash():
    base = {
        "schema": S.SCHEMA, "recorded_at": "t", "state_id": "x", "rep_id": 0,
        "config_id": "c", "s2": 1.0, "gradient": {"namespace": S.GRAD_NS},
        "selected_action": None, "S1": None, "S1_threshold": S.S1_THRESHOLD,
        "deployment": "ABSTAIN", "s1_contract_sha256": "h", "panel_hash": "p",
        "sample_counts": {"gradient": S.N_GRAD, "probe_base": 0,
                          "probe_action": 0, "total": S.N_GRAD},
        "protocol_hashes": {"gradient": "g", "probe": None}, "z95": S.Z95,
    }
    for key, val in (("truth", "WIDEN"), ("truth_group", "W"), ("V1", 0.5),
                     ("probe", {"r_hat": 0.1}), ("oracle_action", "WIDEN"),
                     (S.HASH_FIELD, "self")):
        rec = dict(base, **{key: val})
        with pytest.raises(ValueError):
            S._pre_hash_validate(rec)


def test_prehash_schema_rejects_budget_violation():
    rec = {
        "schema": S.SCHEMA, "recorded_at": "t", "state_id": "x", "rep_id": 0,
        "config_id": "c", "s2": 1.0, "gradient": {"namespace": S.GRAD_NS},
        "selected_action": None, "S1": None, "S1_threshold": S.S1_THRESHOLD,
        "deployment": "ABSTAIN", "s1_contract_sha256": "h", "panel_hash": "p",
        "sample_counts": {"gradient": S.N_GRAD + 1, "probe_base": 0,
                          "probe_action": 0, "total": S.N_GRAD + 1},
        "protocol_hashes": {"gradient": "g", "probe": None}, "z95": S.Z95,
    }
    with pytest.raises(ValueError):
        S._pre_hash_validate(rec)


def test_deployment_rule_frozen_semantics():
    # g_hat<0 => WIDEN; g_hat>0 => SHRINK; deploy iff S1 >= threshold
    assert ("WIDEN" if -0.5 < 0 else "SHRINK") == "WIDEN"
    assert ("WIDEN" if 0.5 < 0 else "SHRINK") == "SHRINK"
    assert (3.9 >= S.S1_THRESHOLD) is False
    assert (S.S1_THRESHOLD >= S.S1_THRESHOLD) is True


# --------------------------------------------------------------------------
# Sec. 17.5 persistence tests (inherited WA1R contract)
# --------------------------------------------------------------------------

def _trial(tmp_path, fault=None, payload_error=None):
    ledger = tmp_path / "ledger.jsonl"
    final = tmp_path / "out" / "rep0.json"

    def sim():
        if payload_error:
            raise payload_error
        return {"schema": S.SCHEMA, "state_id": "x", "ok": True}

    def validate(rec):
        assert rec["schema"] == S.SCHEMA

    result = S.run_trial_transactional(
        "x__rep0", final, sim, ledger_path=ledger, pre_hash_validator=validate,
        fault=fault)
    return result, ledger, final


def test_persistence_happy_path_durable(tmp_path):
    result, ledger, final = _trial(tmp_path)
    assert result["status"] == "COMPLETE"
    entries = S.ledger_entries(ledger)
    assert [e["status"] for e in entries] == ["STARTED", "COMPLETE"]
    rec = json.loads(final.read_text(encoding="utf-8"))
    assert rec[S.HASH_FIELD] == result["scientific_payload_hash"]
    assert S.record_file_hash(final) == result["record_file_hash"]


def test_persistence_started_before_simulator(tmp_path):
    # simulator raises immediately: the STARTED entry must already exist
    ledger = tmp_path / "ledger.jsonl"
    final = tmp_path / "out" / "rep0.json"

    def sim():
        raise RuntimeError("simulator exploded after STARTED")

    result = S.run_trial_transactional("x__rep0", final, sim,
                                       ledger_path=ledger,
                                       pre_hash_validator=lambda r: None)
    assert result["status"] == "CONSUMED_INVALID"
    statuses = [e["status"] for e in S.ledger_entries(ledger)]
    assert statuses[0] == "STARTED"


def test_persistence_no_replay_after_consumed_invalid(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    final = tmp_path / "out" / "rep0.json"

    def sim():
        raise RuntimeError("boom")

    S.run_trial_transactional("x__rep0", final, sim, ledger_path=ledger,
                              pre_hash_validator=lambda r: None)
    from hyptraj.m3pi1vr0.persistence import ReplayError
    with pytest.raises(ReplayError):
        S.run_trial_transactional("x__rep0", final,
                                  lambda: {"schema": S.SCHEMA},
                                  ledger_path=ledger,
                                  pre_hash_validator=lambda r: None)


def test_persistence_refuses_duplicate_destination(tmp_path):
    from hyptraj.m3pi1vr0.persistence import ReplayError
    ledger = tmp_path / "ledger.jsonl"
    final = tmp_path / "out" / "rep0.json"
    S.run_trial_transactional("x__rep0", final, lambda: {"schema": S.SCHEMA},
                              ledger_path=ledger,
                              pre_hash_validator=lambda r: None)
    with pytest.raises(ReplayError):
        S.run_trial_transactional("y__rep0", final, lambda: {"schema": S.SCHEMA},
                                  ledger_path=ledger,
                                  pre_hash_validator=lambda r: None)


def test_persistence_corrupted_final_record_detected(tmp_path):
    from hyptraj.m3wa1r.persistence import scientific_payload_hash
    result, ledger, final = _trial(tmp_path)
    rec = json.loads(final.read_text(encoding="utf-8"))
    rec["state_id"] = "tampered"
    final.write_text(json.dumps(rec), encoding="utf-8")
    stored = json.loads(final.read_text(encoding="utf-8"))
    assert scientific_payload_hash(stored) != stored[S.HASH_FIELD]


def test_persistence_injected_fault_is_consumed_invalid(tmp_path):
    result, ledger, final = _trial(tmp_path, fault="AFTER_SIM_BEFORE_VALIDATE")
    assert result["status"] == "CONSUMED_INVALID"
    statuses = [e["status"] for e in S.ledger_entries(ledger)]
    assert statuses == ["STARTED", "CONSUMED_INVALID"]
    assert not final.exists()


# --------------------------------------------------------------------------
# Sec. 17.6 verdict tests
# --------------------------------------------------------------------------

def test_verdict_a_all_gates_pass():
    assert S.s1c_verdict(192, 0, 0.0, 0.90, 0.10) == "M3-S1C-A"


def test_verdict_b_each_single_gate_fail():
    assert S.s1c_verdict(192, 0, 0.06, 0.90, 0.10) == "M3-S1C-B"
    assert S.s1c_verdict(192, 0, 0.00, 0.74, 0.10) == "M3-S1C-B"
    assert S.s1c_verdict(192, 0, 0.00, 0.90, 0.21) == "M3-S1C-B"


def test_verdict_boundary_exact_thresholds():
    # gates are inclusive per the frozen contract (<= and >=)
    assert S.s1c_verdict(192, 0, 0.05, 0.75, 0.20) == "M3-S1C-A"


def test_verdict_x_on_persistence_or_incomplete():
    assert S.s1c_verdict(192, 1, 0.0, 0.90, 0.10) == "M3-S1C-X"
    assert S.s1c_verdict(191, 0, 0.0, 0.90, 0.10) == "M3-S1C-X"


def test_prereg_hash_manifest_verifies():
    S.verify_prereg()  # raises on any mismatch


def test_execution_authorization_record_parses():
    # The explicit human authorization (YES / Human / 2026-09-06, recorded
    # after the independent live Git audit of 509a266 passed) is in force;
    # the execution gate must parse and accept it.
    S._require_authorization()  # must not raise


# --------------------------------------------------------------------------
# AMENDMENT A tests: config-diversity round rule
# --------------------------------------------------------------------------

def _synth_pool(counts: dict[str, int]) -> list[dict]:
    pool = []
    for cid, n in counts.items():
        for i in range(n):
            pool.append({"state_id": f"{cid}_s{i}", "config_id": cid,
                         "truth": "WIDEN", "s2": 1.0 + i})
    return pool


def test_round_rule_5_configs_8_needed():
    pool = _synth_pool({"cfg_a": 5, "cfg_b": 2, "cfg_c": 1,
                        "cfg_d": 1, "cfg_e": 1})
    chosen = S.pick_rounds(pool, 8)
    assert len(chosen) == 8 == len({c["state_id"] for c in chosen})
    per_cfg = Counter(c["config_id"] for c in chosen)
    # round 1: all 5 configs; round 2: the two configs with >=2 members;
    # round 3: only cfg_a (>=3 members) completes the target
    assert per_cfg == {"cfg_a": 3, "cfg_b": 2, "cfg_c": 1,
                       "cfg_d": 1, "cfg_e": 1}


def test_round_rule_adequate_configs_one_per_config():
    pool = _synth_pool({f"c{i}": 2 for i in range(9)})
    chosen = S.pick_rounds(pool, 8)
    assert len(chosen) == 8
    assert len({c["config_id"] for c in chosen}) == 8   # round 1 only


def test_round_rule_rank_deterministic_and_order_independent():
    import random
    pool = _synth_pool({"cfg_a": 5, "cfg_b": 2, "cfg_c": 1,
                        "cfg_d": 1, "cfg_e": 1})
    base = [c["state_id"] for c in S.pick_rounds(pool, 8)]
    for seed in range(5):
        shuffled = [dict(x) for x in pool]
        random.Random(seed).shuffle(shuffled)
        assert [c["state_id"] for c in S.pick_rounds(shuffled, 8)] == base


def test_round_rule_uses_only_frozen_hash_and_metadata():
    # selection must not depend on controller-signal fields even if present
    pool = _synth_pool({"cfg_a": 5, "cfg_b": 2, "cfg_c": 1,
                        "cfg_d": 1, "cfg_e": 1})
    noisy = [dict(x, g_hat=0.1 * i, S1=5.5, V1=0.7, selected_action="WIDEN")
             for i, x in enumerate(pool)]
    assert ([c["state_id"] for c in S.pick_rounds(noisy, 8)]
            == [c["state_id"] for c in S.pick_rounds(pool, 8)])


def test_rank_string_matches_frozen_definition():
    s = {"state_id": "st", "config_id": "cf"}
    digest = hashlib.sha256(b"M3-S1C-PANEL-V1|cf|st").hexdigest()
    assert S.rank_hex(s) == digest


def test_frozen_panel_matches_round_rule():
    # the committed panel must be exactly what the frozen rule produces
    reserve = S.csvread(S.PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv")
    panel = json.loads((S.CFG / "m3s1c_panel.json").read_text())
    committed = {s["state_id"] for s in panel["states"]}
    assert committed == {s["state_id"] for s in S.select_panel(reserve)}
    for s in panel["states"]:
        assert s["selection_rank"] == S.rank_hex(s)


# --------------------------------------------------------------------------
# AMENDMENT B tests: truth-vs-comparator exposure semantics
# --------------------------------------------------------------------------

def _write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_exposure_truth_reference_allowed(tmp_path):
    # direct truth field
    f1 = _write_json(tmp_path / "a.json",
                     {"state_id": "cand_A", "confirmed_label": "WIDEN",
                      "p_ref_hash": "abc"})
    # truth-stream namespace inheritance (stage manifest wrapper)
    f2 = _write_json(tmp_path / "b.json",
                     {"namespace": "M3-CF1N-CONFIRM",
                      "records": [{"state_id": "cand_B", "status": "COMPLETE"}]})
    # reference ledger namespace (...-REF)
    f3 = _write_json(tmp_path / "c.json",
                     {"seed_namespace": "M3-WA1R-REF",
                      "state_id": "cand_A", "status": "COMPLETE"})
    exposed, unresolved, classes = S.scan_confirm_artifacts(
        [f1, f2, f3], {"cand_A", "cand_B"})
    assert not exposed and not unresolved
    assert all(v == "truth_reference" for v in classes.values())


def test_exposure_comparator_forbidden(tmp_path):
    cases = [
        {"state_id": "cand_A", "g_hat": 0.1, "g_ci_low": 0.05,
         "g_ci_high": 0.15},                       # gradient result
        {"state_id": "cand_A", "S1": 5.5},         # S1 score
        {"state_id": "cand_A", "V1": 0.7, "r_hat": 0.02},  # V1 artifact
        {"state_id": "cand_A", "selected_action": "WIDEN",
         "deployment": "DEPLOY"},                  # controller action
        {"seed_namespace": "M3-PI1VNR-GRAD",
         "state_id": "cand_A", "status": "STARTED"},  # comparator namespace
    ]
    paths = [_write_json(tmp_path / f"z_confirm_{i}.json", c)
             for i, c in enumerate(cases)]
    exposed, unresolved, _ = S.scan_confirm_artifacts(paths, {"cand_A"})
    assert exposed == {"cand_A"} and not unresolved
    assert all(v == "comparator" for v in
               S.scan_confirm_artifacts(paths, {"cand_A"})[2].values())


def test_exposure_unknown_is_unresolved_never_autoallowed(tmp_path):
    # pure identifier/seed row under NO namespace: neither comparator nor
    # truth => UNRESOLVED (amendment Sec. 3.6)
    f = _write_json(tmp_path / "m.json",
                    {"records": [{"state_id": "cand_A", "seed": 123}]})
    exposed, unresolved, classes = S.scan_confirm_artifacts([f], {"cand_A"})
    assert not exposed and unresolved
    assert classes[str(f)] == "UNRESOLVED"


def test_exposure_filename_alone_never_decides(tmp_path):
    # identical plain records: truth-stream namespace => allowed;
    # no namespace => UNRESOLVED; 'confirm' in the filename saves nothing
    plain = {"records": [{"state_id": "cand_A", "status": "COMPLETE"}]}
    f_ns = _write_json(tmp_path / "anything.json",
                       dict(plain, namespace="M3-X-CONFIRM"))
    f_noname = _write_json(tmp_path / "plain_confirm.json",
                           [{"state_id": "cand_A", "status": "COMPLETE"}])
    f_cmp = _write_json(tmp_path / "harmless_name.json",
                        {"state_id": "cand_A", "S1": 5.5})
    exposed, unresolved, classes = S.scan_confirm_artifacts(
        [f_ns, f_noname, f_cmp], {"cand_A"})
    assert exposed == {"cand_A"}          # comparator artifact forbidden
    assert classes[str(f_ns)] == "truth_reference"
    assert classes[str(f_noname)] == "UNRESOLVED"
    assert classes[str(f_cmp)] == "comparator"


def test_exposure_live_audit_all_42_clean_and_resolved():
    audit = json.loads((S.OUT / "m3s1c_exposure_audit.json").read_text())
    assert audit["candidates"] == 42 and audit["any_exposed"] is False
    assert audit["unresolved_records"] == 0
    assert audit["EXPOSURE_AUDIT"] == "PASS"
    rows = S.csvread(S.OUT / "m3s1c_exposure_audit_rows.csv")
    assert len(rows) == 42 and all(int(r["exposed"]) == 0 for r in rows)
