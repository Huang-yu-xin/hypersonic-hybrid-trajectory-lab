"""M3-S25-R1 route-level ZERO-SAMPLING test (taskbook Sec. 31).

Executes the REAL control flow truth_execute -> discovery 240 ->
confirmation 480/480 -> truth assignment -> inventory -> union pool ->
panel freeze, with mocked simulator/reference functions and temporary
persistence paths.  The real simulator is never invoked; the P_ref
registry hash verification runs for real.  The frozen Round-0 preflight
verdict (FAIL, span conflict) is bypassed ONLY inside the route harness
-- the fail-closed refusal on the real frozen verdict is tested
separately.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s25r1 as R  # noqa: E402
from hyptraj.m3s25r1 import runtime as RT  # noqa: E402

CLASSES = ["WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"]


def _mock_sims(monkeypatch, calls):
    def mock_arms(arms, bench_cfg, seed_key, n, n_batches):
        calls["arms"] += 1
        return {name: {"P": 0.1, "P_CI": [0.09, 0.11], "ESS": 1000.0,
                       "sample_count": int(n), "M2": 0.01,
                       "m2_batches": [0.01] * n_batches}
                for name in ("base", "widen", "shrink")}

    def mock_classify(arms, p_ref, **kw):
        calls["classify"] += 1
        return {"corrected_class": CLASSES[calls["classify"] % 4],
                "minimum_arm_ESS": 100.0, "numerical_valid": True,
                "probability_semantics_valid": True, "ess_valid": True}

    monkeypatch.setattr(RT, "evaluate_reference_arms", mock_arms)
    monkeypatch.setattr(RT, "classify_reference_state", mock_classify)


@pytest.fixture()
def route(tmp_path, monkeypatch):
    """Route harness: tmp persistence + gated approval + mocked sims."""
    calls = {"arms": 0, "classify": 0}
    _mock_sims(monkeypatch, calls)

    approval = tmp_path / "M3_S25_R1_Human_Approval.md"
    approval.write_text(
        "M3_S25_R1_TRUTH_AUTHORIZED: YES\nM3_S25_R1_ARM_A_AUTHORIZED: NO\n"
        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    # the frozen Round-0 preflight verdict is FAIL (documented span
    # conflict); the route harness bypasses THAT gate only
    monkeypatch.setattr(R, "verify_frozen_preflight_pass",
                        lambda: {"PREFLIGHT_VERDICT": "PASS"})

    disc, conf = tmp_path / "discovery", tmp_path / "confirmation"
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    tsum, tcfg = tmp_path / "summary", tmp_path / "configs"
    tcfg.mkdir(parents=True, exist_ok=True)
    for name in ("m3s25r1_contract.json", "m3s25r1_p_ref_registry.json",
                 "m3s25r1_parent_development_registry.json"):
        (tcfg / name).write_bytes(
            (R.CFG / name).read_bytes())
    monkeypatch.setattr(R, "SUM", tsum)
    monkeypatch.setattr(R, "CFG", tcfg)
    return {"calls": calls, "tmp": tmp_path}


def test_route_execute_to_frozen_panel(route):
    calls = route["calls"]
    summary = R.truth_execute()
    assert calls["arms"] == 480 and calls["classify"] == 480
    assert summary["discovery"] == {"planned": 72_000_000,
                                    "actual": 72_000_000,
                                    "difference": 0, "topup": 0}
    assert summary["confirmation"]["actual"] == 360_000_000
    assert summary["p_ref"] == {"planned": 0, "actual": 0, "difference": 0,
                                "topup": 0}
    assert summary["total"]["planned"] == summary["total"]["actual"] \
        == 432_000_000
    # completion semantics: frozen truth + exposed inventory + union
    truth = json.loads((route["tmp"] / "summary" / "m3s25r1_frozen_truth.json")
                       .read_text(encoding="utf-8"))
    assert truth["n_states"] == 240
    assert truth["composition"] == {"WIDEN": 60, "SHRINK": 60, "HOLD": 60,
                                    "AMBIGUOUS": 60}
    inv = json.loads((route["tmp"] / "summary" /
                      "m3s25r1_truth_exposed_inventory.json").read_text(
                          encoding="utf-8"))
    assert inv["n"] == 240
    assert all(s["status"] == "TRUTH_EXPOSED_DEVELOPMENT"
               for s in inv["states"])
    union = json.loads((route["tmp"] / "summary" /
                        "m3s25r1_development_union.json").read_text(
                            encoding="utf-8"))
    assert union["n_old"] == 240 and union["n_new"] == 240
    assert union["n_union"] == 480
    # panel frozen under the NEW rank namespace
    panel = json.loads((route["tmp"] / "configs" / "m3s25r1_panel.json")
                       .read_text(encoding="utf-8"))
    assert panel["frozen"] is True and panel["n_states"] == 120
    assert panel["n_configs"] >= 24
    rows = list(csv_rows(route["tmp"] / "summary" / "m3s25r1_panel.csv"))
    assert len(rows) == 120
    assert {r["source_stage"] for r in rows} <= {"M3-S2S", "M3-S25-R1"}
    assert all(r["truth"] in CLASSES for r in rows)
    assert Counter(r["truth"] for r in rows) == {"WIDEN": 30, "SHRINK": 30,
                                                 "HOLD": 30, "AMBIGUOUS": 30}


def csv_rows(p):
    import csv
    with open(p, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_route_seed_namespaces_frozen():
    m = json.loads((R.CFG / "m3s25r1_truth_seed_manifest.json")
                   .read_text(encoding="utf-8"))
    assert m["namespaces"] == {"discovery": "M3-S25-R1-DISCOVERY",
                               "confirmation": "M3-S25-R1-CONFIRMATION"}
    assert m["counts"] == {"discovery": 240, "confirmation": 240, "pref": 0}
    assert m["frozen_before_first_simulator_call"] is True


def test_route_panel_blocked_synthetic():
    states = [{"state_id": f"s{i}", "config_id": f"c{i % 5}",
               "rank": RT.seed("M3-S25-R1-PANEL-V1|", f"s{i}"),
               "truth": "WIDEN"} for i in range(40)]
    truth = {s["state_id"]: "WIDEN" for s in states}
    out = RT.select_panel(states, truth)
    assert out["PANEL"] == "M3-S25-R1-PANEL-BLOCKED"


def test_route_panel_freeze_synthetic_meets_design():
    states, truth = [], {}
    for gi, grp in enumerate(("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS")):
        for i in range(30):
            cid = f"c{gi}_{i % 10}"
            sid = f"{cid}_{grp}_{i}"
            states.append({"state_id": sid, "config_id": cid,
                           "rank": RT.seed("M3-S25-R1-PANEL-V1|", sid)})
            truth[sid] = grp
    out = RT.select_panel(states, truth)
    assert out["PANEL"] == "FROZEN"
    assert len(out["panel"]) == 120 and out["n_configs"] >= 24
    assert len({s["state_id"] for s in out["panel"]}) == 120


def test_route_union_duplicate_protection():
    a = [{"state_id": "x", "config_id": "c", "s2": 1.0, "rank": "r"}]
    with pytest.raises(RuntimeError, match="duplicate state"):
        RT.union_development_pool(a, list(a))


def test_route_truth_execute_refuses_on_frozen_preflight_fail(
        tmp_path, monkeypatch):
    """Fail-closed property against a FAIL preflight verdict: with the
    frozen report verdict flipped to FAIL (tmp report -- the R1.1 BLOCKED
    evidence state), truth_execute refuses before ANY simulator call or
    write, even if the human gate said YES.  (Under R1.2 the real frozen
    verdict is PASS; the FAIL-refusal mechanism is verified on a tmp
    report.)"""
    calls = {"arms": 0, "classify": 0}
    _mock_sims(monkeypatch, calls)
    approval = tmp_path / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: YES\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    bad = tmp_path / "preflight_fail.json"
    bad.write_text(json.dumps({"PREFLIGHT_VERDICT": "FAIL",
                               "overall": "M3-S25-R1.1 PREFLIGHT BLOCKED"}),
                   encoding="utf-8")
    monkeypatch.setattr(R, "PREFLIGHT_REPORT", bad)
    disc, conf = tmp_path / "discovery", tmp_path / "confirmation"
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    with pytest.raises(RuntimeError, match="PREFLIGHT BLOCKED"):
        R.truth_execute()
    assert calls == {"arms": 0, "classify": 0}
    assert not (tmp_path / "discovery").exists()
    assert not (tmp_path / "confirmation").exists()


def test_route_truth_execute_refuses_without_authorization(
        tmp_path, monkeypatch):
    """Steps 1-5 run (no writes), step 6 refuses while the human gate is
    NO; simulator calls stay 0."""
    calls = {"arms": 0, "classify": 0}
    _mock_sims(monkeypatch, calls)
    monkeypatch.setattr(R, "verify_frozen_preflight_pass",
                        lambda: {"PREFLIGHT_VERDICT": "PASS"})
    disc, conf = tmp_path / "discovery", tmp_path / "confirmation"
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    with pytest.raises(RuntimeError,
                       match="M3_S25_R1_TRUTH_AUTHORIZED is not YES"):
        R.truth_execute()
    assert calls == {"arms": 0, "classify": 0}
    assert not disc.exists() and not conf.exists()


def test_route_restart_started_only_fails_before_authorization_and_downstream(
        tmp_path, monkeypatch):
    """Taskbook Sec. 20 ordering: the restart scan (step 5) precedes the
    authorization check (step 6) and every simulator call (step 8)."""
    calls = {"arms": 0, "classify": 0}
    _mock_sims(monkeypatch, calls)
    approval = tmp_path / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: YES\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: NO\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    monkeypatch.setattr(R, "verify_frozen_preflight_pass",
                        lambda: {"PREFLIGHT_VERDICT": "PASS"})
    disc, conf = tmp_path / "discovery", tmp_path / "confirmation"
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    # seed a non-fresh DISCOVERY ledger state
    disc.mkdir(parents=True, exist_ok=True)
    with (disc / "discovery_ledger.jsonl").open("w", encoding="utf-8") as h:
        h.write(json.dumps({"state_id": "DISC|"
                            + R.verify_universe_sha_only()[0]["state_id"],
                            "status": "STARTED"}) + "\n")
    with pytest.raises(RuntimeError, match="STARTED-only"):
        R.truth_execute()
    assert calls == {"arms": 0, "classify": 0}
    assert not (tmp_path / "confirmation").exists()


def test_route_arm_gates_must_stay_no_during_truth(tmp_path, monkeypatch):
    calls = {"arms": 0, "classify": 0}
    _mock_sims(monkeypatch, calls)
    approval = tmp_path / "approval.md"
    approval.write_text("M3_S25_R1_TRUTH_AUTHORIZED: YES\n"
                        "M3_S25_R1_ARM_A_AUTHORIZED: YES\n"
                        "M3_S25_R1_ARM_B_AUTHORIZED: NO\n", encoding="utf-8")
    monkeypatch.setattr(R, "APPROVAL_DOC", approval)
    monkeypatch.setattr(R, "verify_frozen_preflight_pass",
                        lambda: {"PREFLIGHT_VERDICT": "PASS"})
    disc, conf = tmp_path / "discovery", tmp_path / "confirmation"
    monkeypatch.setattr(R, "TRUTH_DISC", disc)
    monkeypatch.setattr(R, "TRUTH_CONF", conf)
    monkeypatch.setattr(R, "TRUTH_LEDGERS", {
        "discovery": disc / "discovery_ledger.jsonl",
        "confirmation": conf / "confirmation_ledger.jsonl"})
    with pytest.raises(RuntimeError, match="Arm gates must remain NO"):
        R.truth_execute()
    assert calls == {"arms": 0, "classify": 0}


def test_route_real_p_ref_registry_hash_verified():
    """The P_ref path the truth stage will use: every source hash verified
    against the registry BEFORE parsing (real files)."""
    registry = json.loads((R.CFG / "m3s25r1_p_ref_registry.json")
                          .read_text(encoding="utf-8"))
    for cid in ("c000", "cf1n_new_007", "wcf1_new_003", "m3s2s_cfg_004"):
        rec = RT.p_ref_from_registry(cid, registry, R._p_ref_source_resolver,
                                     R.record_file_hash)
        assert 0 < rec["p_ref_full"] < 1
        assert rec["sample_count"] > 0


def test_route_gates_match_authorization_after_all_tests():
    assert not R.gate("M3_S25_R1_TRUTH_AUTHORIZED")
    assert R.gate("M3_S25_R1_ARM_A_AUTHORIZED") is True
    assert not R.gate("M3_S25_R1_ARM_B_AUTHORIZED")
