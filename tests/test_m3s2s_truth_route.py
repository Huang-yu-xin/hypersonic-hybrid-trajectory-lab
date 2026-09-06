"""M3-S2S route-level ZERO-SAMPLING test (execution-readiness amendment).

Executes the REAL control flow truth_execute -> PREF -> discovery ->
confirmation -> truth_panel -> frozen panel with mocked simulator/reference
functions and temporary persistence paths.  The real simulator is never
invoked; the vendored P_ref hash verification runs for real.
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

import run_m3s2s as R  # noqa: E402
from hyptraj.m3s2s import truth_execution as TE  # noqa: E402
from hyptraj.m3s2s import vendored_runtime as VR  # noqa: E402


@pytest.fixture()
def route(tmp_path, monkeypatch):
    """Route harness: tmp persistence, gated approval doc, mocked sim."""
    # tmp approval doc: TRUTH=YES, Arm gates NO
    approval = tmp_path / "M3_S2S_Human_Approval.md"
    approval.write_text(
        "TRUTH_SAMPLING_AUTHORIZED: YES\nARM_A_AUTHORIZED: NO\n"
        "ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)

    # tmp truth persistence dirs
    pref, disc, conf = (tmp_path / "pref", tmp_path / "discovery",
                        tmp_path / "confirmation")
    monkeypatch.setattr(R, "TRUTH_PREF", pref)
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "pref": pref / "pref_ledger.jsonl",
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    # tmp summary/config outputs for the panel stage
    tsum, tcfg = tmp_path / "summary", tmp_path / "configs"
    tcfg.mkdir(parents=True, exist_ok=True)
    (tcfg / "m3s2s_truth_contract.json").write_bytes(
        R.ROOT.joinpath("configs/phase_m3s2s/m3s2s_truth_contract.json")
        .read_bytes())
    monkeypatch.setattr(R, "SUM", tsum)
    monkeypatch.setattr(R, "CFG", tcfg)

    # -- mocked simulator/reference layer (NEVER the real simulator) -----
    calls = {"pref": 0, "arms": 0, "classify": 0}
    classes = ["WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"]

    def mock_direct_full_event_reference(bench, seed_key, n, n_batches):
        calls["pref"] += 1
        return {"sample_count": int(n), "n_batches": int(n_batches),
                "p_ref_full": 0.1, "p_ref_full_SE": 0.001,
                "p_ref_full_CI": [0.098, 0.102],
                "p_batches": [0.1] * n_batches,
                "topology_counts": {"S1": 1}}

    def mock_evaluate_reference_arms(arms, bench_cfg, seed_key, n, n_batches):
        calls["arms"] += 1
        out = {}
        for name in ("base", "widen", "shrink"):
            out[name] = {"P": 0.1, "P_CI": [0.09, 0.11], "ESS": 1000.0,
                         "sample_count": int(n), "M2": 0.01,
                         "m2_batches": [0.01] * n_batches}
        return out

    def mock_classify_reference_state(arms, p_ref, **kw):
        calls["classify"] += 1
        cls = classes[calls["classify"] % 4]  # 60 per stratum over 240
        return {"corrected_class": cls,
                "minimum_arm_ESS": 100.0,
                "numerical_valid": True,
                "probability_semantics_valid": True,
                "ess_valid": True}

    monkeypatch.setattr(TE, "direct_full_event_reference",
                        mock_direct_full_event_reference)
    monkeypatch.setattr(TE, "evaluate_reference_arms",
                        mock_evaluate_reference_arms)
    monkeypatch.setattr(TE, "classify_reference_state",
                        mock_classify_reference_state)
    return {"calls": calls, "tmp": tmp_path}


def test_route_execute_to_frozen_panel(route, monkeypatch):
    calls = route["calls"]
    # -- truth_execute through all three streams --------------------------
    summary = R.truth_execute()
    assert calls["pref"] == 8 and calls["arms"] == 480 and calls["classify"] == 480
    # exact per-stream consumption, planned == actual, no top-up
    assert summary["pref"] == {"planned": 4_000_000, "actual": 4_000_000,
                               "difference": 0, "topup": 0}
    assert summary["discovery"]["actual"] == 72_000_000
    assert summary["confirmation"]["actual"] == 360_000_000
    assert summary["total"]["planned"] == summary["total"]["actual"] == 436_000_000

    # -- completion semantics: frozen truth + exposed inventory ------------
    selection = R.truth_panel()
    assert selection["PANEL"] == "FROZEN"
    assert len(selection["panel"]) == 120
    assert selection["n_configs"] >= 24
    truth = json.loads((route["tmp"] / "summary" / "m3s2s_frozen_truth.json")
                       .read_text(encoding="utf-8"))
    assert truth["n_states"] == 240
    assert truth["composition"] == {"WIDEN": 60, "SHRINK": 60,
                                    "HOLD": 60, "AMBIGUOUS": 60}
    inv = json.loads((route["tmp"] / "summary" /
                      "m3s2s_truth_exposed_inventory.json").read_text(
                          encoding="utf-8"))
    assert inv["n"] == 240   # ALL truth-sampled states, selected or not

    # panel JSON written and hash-consistent
    panel = json.loads((route["tmp"] / "configs" / "m3s2s_panel.json")
                       .read_text(encoding="utf-8"))
    assert panel["frozen"] is True
    assert panel["panel_sha256"] == selection["panel_sha256"]


def test_route_seed_namespaces_equal_frozen_contract():
    manifest = json.loads((R.CFG / "m3s2s_truth_seed_manifest.json")
                          .read_text(encoding="utf-8"))
    consts = VR.load_vendored_protocol_constants()
    assert manifest["namespaces"] == consts["namespaces"] == {
        "pref": "M3-CF1N-PREF", "discovery": "M3-CF1N-DISCOVERY",
        "confirmation": "M3-CF1N-CONFIRM"}
    assert manifest["counts"] == {"pref": 8, "discovery": 240,
                                  "confirmation": 240}
    assert manifest["frozen_before_first_simulator_call"] is True
    audit = json.loads((R.OUT / "m3s2s_truth_seed_audit.json")
                       .read_text(encoding="utf-8"))
    assert audit["unique_seed_keys"] == 488
    assert audit["historical_collision"] == 0
    assert audit["namespaces_match_contract"] is True


def test_route_plan_assertions():
    from hyptraj.m3s2s import truth_execution as TE
    states = VR.verify_universe()
    consts = VR.load_vendored_protocol_constants()
    plan = TE.truth_execution_plan(states, namespaces=consts["namespaces"])
    assert len(plan["pref_units"]) == 8
    assert len(plan["discovery_units"]) == 240
    assert len(plan["confirmation_units"]) == 240
    assert plan["early_stop_on_quota"] is False
    assert plan["confirmation_scope"] == "ALL_240_FRESH_CANDIDATES"
    assert plan["total_samples"] == TE.TRUTH_BUDGET_PLANNED == \
        TE.TRUTH_BUDGET_MAX == 436_000_000
    # no candidate substitution: plan ids == universe ids exactly
    universe_ids = {s["state_id"] for s in states}
    assert ({u["state_id"] for u in plan["discovery_units"]}
            | {u["state_id"] for u in plan["confirmation_units"]}
            == universe_ids)


def test_route_p_ref_vendored_hashes_verified_all_families():
    """The vendored P_ref loader hash-verifies every artifact against the
    truth contract BEFORE parsing, for all three source families."""
    for cid in ("cf1n_new_000", "cf1n_new_007", "wcf1_new_000",
                "wcf1_new_005", "c000", "c020"):
        rec = VR.load_config_p_ref(cid)
        assert rec["p_ref_full"] > 0
    # tamper => hard fail (CF1N family)
    contract = json.loads(VR.TRUTH_CONTRACT.read_text(encoding="utf-8"))
    name = "pref_records/cf1n_new_000.json"
    saved = contract["vendored_snapshots"][name]
    contract["vendored_snapshots"][name] = "0" * 64
    bad = R.OUT / "_tmp_bad_contract.json"
    bad.write_text(json.dumps(contract), encoding="utf-8")
    monkey_target = VR.TRUTH_CONTRACT
    try:
        VR.TRUTH_CONTRACT = bad
        with pytest.raises(VR.VendoredRuntimeError, match="hash mismatch"):
            VR.load_config_p_ref("cf1n_new_000")
        # tamper => hard fail (legacy family)
        name2 = "pref_records/m3d2_probability_reference.json"
        contract2 = json.loads(VR.TRUTH_CONTRACT.read_text(encoding="utf-8"))
        contract2["vendored_snapshots"][name2] = "1" * 64
        bad2 = R.OUT / "_tmp_bad_contract2.json"
        bad2.write_text(json.dumps(contract2), encoding="utf-8")
        VR.TRUTH_CONTRACT = bad2
        with pytest.raises(VR.VendoredRuntimeError, match="hash mismatch"):
            VR.load_config_p_ref("c000")
    finally:
        VR.TRUTH_CONTRACT = monkey_target


def test_route_panel_blocked_synthetic():
    states = [{"state_id": f"s{i}", "config_id": f"c{i % 5}",
               "rank": R.rank_hex(f"c{i % 5}", f"s{i}"), "truth": "WIDEN"}
              for i in range(40)]
    truth = {s["state_id"]: "WIDEN" for s in states}
    out = TE.select_panel(states, truth)
    assert out["PANEL"] == "M3-S2S-PANEL-BLOCKED"


def test_route_gates_still_no():
    assert not R._gate("TRUTH_SAMPLING_AUTHORIZED")
    assert not R._gate("ARM_A_AUTHORIZED")
    assert not R._gate("ARM_B_AUTHORIZED")


# --------------------------------------------------------------------------
# RUNTIME-INTEGRITY AMENDMENT: CSV guards, registry pin, PREF restart
# --------------------------------------------------------------------------

def test_wcf1_manifest_csv_sha_tamper_hard_fail(tmp_path, monkeypatch):
    from hyptraj.m3s2s import vendored_runtime as VR
    contract = json.loads(VR.TRUTH_CONTRACT.read_text(encoding="utf-8"))
    contract["vendored_snapshots"]["m3wcf1_physical_config_manifest.csv"] = "0" * 64
    bad = tmp_path / "_bad_contract.json"
    bad.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(VR, "TRUTH_CONTRACT", bad)
    with pytest.raises(VR.VendoredRuntimeError, match="vendored CSV hash mismatch"):
        VR.load_vendored_csv("wcf1_manifest")


def test_raw_lattice_csv_sha_tamper_hard_fail(tmp_path, monkeypatch):
    from hyptraj.m3s2s import vendored_runtime as VR
    contract = json.loads(VR.TRUTH_CONTRACT.read_text(encoding="utf-8"))
    contract["vendored_snapshots"]["m3cf0_raw_physical_candidate_lattice.csv"] = "1" * 64
    bad = tmp_path / "_bad_contract.json"
    bad.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(VR, "TRUTH_CONTRACT", bad)
    with pytest.raises(VR.VendoredRuntimeError, match="vendored CSV hash mismatch"):
        VR.load_vendored_csv("raw_lattice")


def test_new_config_registry_sha_tamper_hard_fail(tmp_path, monkeypatch):
    from hyptraj.m3s2s import vendored_runtime as VR
    reg = json.loads(VR.NEW_CONFIG_REGISTRY.read_text(encoding="utf-8"))
    reg["configs"]["m3s2s_cfg_000"]["raw_candidate_id"] = "tampered"
    bad = tmp_path / "m3s2s_new_config_registry.json"
    bad.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setattr(VR, "NEW_CONFIG_REGISTRY", bad)
    with pytest.raises(VR.VendoredRuntimeError, match="registry sha mismatch"):
        VR.verify_new_config_registry()


def test_new_config_registry_id_drift_hard_fail(tmp_path, monkeypatch):
    from hyptraj.m3s2s import vendored_runtime as VR
    reg = json.loads(VR.NEW_CONFIG_REGISTRY.read_text(encoding="utf-8"))
    del reg["configs"]["m3s2s_cfg_007"]
    bad = tmp_path / "m3s2s_new_config_registry.json"
    bad.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setattr(VR, "NEW_CONFIG_REGISTRY", bad)
    # pin matches the tampered file's sha => id validation must trigger
    monkeypatch.setattr(VR, "EXPECTED_NEW_CONFIG_REGISTRY_SHA",
                        hashlib.sha256(bad.read_bytes()).hexdigest())
    with pytest.raises(VR.VendoredRuntimeError, match="config-id drift"):
        VR.verify_new_config_registry()


def _make_completed_pref(tmp_path, tamper=False):
    """Durable STARTED+COMPLETE ledger entry + record file for one PREF unit."""
    import hashlib
    pref = tmp_path / "pref"
    pref.mkdir(parents=True, exist_ok=True)
    out = pref / "m3s2s_cfg_000.json"
    rec = {"record_type": "M3S2S-PREF", "config_id": "m3s2s_cfg_000",
           "p_ref_full": 0.1}
    out.write_text(json.dumps(rec), encoding="utf-8")
    file_hash = hashlib.sha256(out.read_bytes()).hexdigest()
    if tamper:
        rec["p_ref_full"] = 0.9
        out.write_text(json.dumps(rec), encoding="utf-8")
    ledger = pref / "pref_ledger.jsonl"
    with ledger.open("w", encoding="utf-8") as h:
        h.write(json.dumps({"state_id": "PREF|m3s2s_cfg_000",
                            "status": "STARTED"}) + "\n")
        h.write(json.dumps({"state_id": "PREF|m3s2s_cfg_000",
                            "status": "COMPLETE",
                            "record_file_hash": file_hash}) + "\n")
    return out, ledger, {"unit_id": "PREF|m3s2s_cfg_000"}


def test_completed_pref_tamper_before_restart_hard_fail(tmp_path, monkeypatch):
    out, ledger, unit = _make_completed_pref(tmp_path, tamper=True)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {"pref": ledger})
    monkeypatch.setattr(R, "TRUTH_PREF", pref_dir := tmp_path / "pref")
    with pytest.raises(RuntimeError, match="hash mismatch on restart"):
        R.load_completed_pref_verified(unit, out)
    # no downstream: discovery dir untouched / never created
    assert not (tmp_path / "discovery").exists()


def test_valid_completed_pref_restart_succeeds(tmp_path, monkeypatch):
    out, ledger, unit = _make_completed_pref(tmp_path, tamper=False)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {"pref": ledger})
    rec = R.load_completed_pref_verified(unit, out)
    assert rec["config_id"] == "m3s2s_cfg_000"
    assert rec["p_ref_full"] == 0.1


def test_completed_pref_missing_file_hard_fail(tmp_path, monkeypatch):
    out, ledger, unit = _make_completed_pref(tmp_path, tamper=False)
    out.unlink()
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {"pref": ledger})
    with pytest.raises(RuntimeError, match="file missing"):
        R.load_completed_pref_verified(unit, out)


def test_completed_pref_duplicate_complete_hard_fail(tmp_path, monkeypatch):
    out, ledger, unit = _make_completed_pref(tmp_path, tamper=False)
    with ledger.open("a", encoding="utf-8") as h:
        h.write(json.dumps({"state_id": "PREF|m3s2s_cfg_000",
                            "status": "COMPLETE",
                            "record_file_hash": "x"}) + "\n")
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {"pref": ledger})
    with pytest.raises(RuntimeError, match="duplicate/inconsistent"):
        R.load_completed_pref_verified(unit, out)


# --------------------------------------------------------------------------
# RUNTIME-INTEGRITY BLOCKER FIX: PREF any-ledger-state fails closed at
# step 3, BEFORE authorization and before any downstream stream
# --------------------------------------------------------------------------

def _pref_blocker_harness(tmp_path, monkeypatch, ledger_status):
    """Harness with TRUTH=YES approval (so a gate-first implementation would
    pass the gate) + mocked simulators + one PREF unit in the given
    non-fresh ledger state."""
    calls = {"pref": 0, "arms": 0, "classify": 0}
    classes = ["WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"]

    def mock_ref(bench, seed_key, n, nb):
        calls["pref"] += 1
        return {"sample_count": int(n), "n_batches": int(nb),
                "p_ref_full": 0.1, "p_ref_full_SE": 0.001,
                "p_ref_full_CI": [0.098, 0.102], "p_batches": [0.1] * nb,
                "topology_counts": {"S1": 1}}

    def mock_arms(arms, bench_cfg, seed_key, n, nb):
        calls["arms"] += 1
        return {name: {"P": 0.1, "P_CI": [0.09, 0.11], "ESS": 1000.0,
                       "sample_count": int(n), "M2": 0.01,
                       "m2_batches": [0.01] * nb}
                for name in ("base", "widen", "shrink")}

    def mock_classify(arms, p_ref, **kw):
        calls["classify"] += 1
        return {"corrected_class": classes[calls["classify"] % 4],
                "minimum_arm_ESS": 100.0, "numerical_valid": True,
                "probability_semantics_valid": True, "ess_valid": True}

    monkeypatch.setattr(TE, "direct_full_event_reference", mock_ref)
    monkeypatch.setattr(TE, "evaluate_reference_arms", mock_arms)
    monkeypatch.setattr(TE, "classify_reference_state", mock_classify)

    approval = tmp_path / "approval.md"
    approval.write_text("TRUTH_SAMPLING_AUTHORIZED: YES\n"
                        "ARM_A_AUTHORIZED: NO\nARM_B_AUTHORIZED: NO\n",
                        encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    pref, disc, conf = (tmp_path / "pref", tmp_path / "discovery",
                        tmp_path / "confirmation")
    monkeypatch.setattr(R, "TRUTH_PREF", pref)
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "pref": pref / "pref_ledger.jsonl",
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    tsum, tcfg = tmp_path / "summary", tmp_path / "configs"
    tcfg.mkdir(parents=True, exist_ok=True)
    (tcfg / "m3s2s_truth_contract.json").write_bytes(
        R.ROOT.joinpath("configs/phase_m3s2s/m3s2s_truth_contract.json")
        .read_bytes())
    monkeypatch.setattr(R, "SUM", tsum)
    monkeypatch.setattr(R, "CFG", tcfg)
    # seed the non-fresh PREF ledger state
    pref.mkdir(parents=True, exist_ok=True)
    with (pref / "pref_ledger.jsonl").open("w", encoding="utf-8") as h:
        h.write(json.dumps({"state_id": "PREF|m3s2s_cfg_000",
                            "status": ledger_status}) + "\n")
    return calls


def test_pref_started_only_fails_before_authorization_and_downstream(
        tmp_path, monkeypatch):
    calls = _pref_blocker_harness(tmp_path, monkeypatch, "STARTED")
    with pytest.raises(RuntimeError, match="STARTED-only"):
        R.truth_execute()
    assert calls == {"pref": 0, "arms": 0, "classify": 0}  # simulator = 0
    assert not (tmp_path / "discovery").exists()
    assert not (tmp_path / "confirmation").exists()


def test_pref_consumed_invalid_fails_before_authorization_and_downstream(
        tmp_path, monkeypatch):
    calls = _pref_blocker_harness(tmp_path, monkeypatch, "CONSUMED_INVALID")
    with pytest.raises(RuntimeError, match="CONSUMED_INVALID"):
        R.truth_execute()
    assert calls == {"pref": 0, "arms": 0, "classify": 0}  # simulator = 0
    assert not (tmp_path / "discovery").exists()
    assert not (tmp_path / "confirmation").exists()
