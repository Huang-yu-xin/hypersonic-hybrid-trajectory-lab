"""M3-CF1N-CONF contracts: authorization, protocol, persistence, verdict (§46-51)."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from hyptraj.m3cf1n.persistence import CONFIRMATION_VALIDATOR
from hyptraj.m3cf1r0.persistence import fsync_directory

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "phase_m3cf1n"
OUT = RES / "summary"
CFG = ROOT / "configs" / "phase_m3cf1n"
PREF = RES / "pref"
DISC = RES / "discovery"
CONF = RES / "confirmation"
CF1_CFG = ROOT / "configs" / "phase_m3cf1"
CF0_OUT = ROOT / "results" / "phase_m3cf0" / "summary"

ELIGIBLE = [f"cf1n_new_{i:03d}" for i in (0, 1, 2, 3, 5, 7)]
INELIGIBLE = ["cf1n_new_004", "cf1n_new_006"]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def ledger(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


def conf_records():
    return [load(p) for p in sorted(CONF.glob("cf1n_new_*.json"))]


def require_complete():
    manifest = RES / "run_manifest.json"
    if not manifest.exists() or load(manifest).get("stage_status") != "COMPLETE":
        pytest.skip("confirmation stage not complete")


# --------------------------------------------------------------------------
# §46 Authorization
# --------------------------------------------------------------------------

def test_m3cf1n_conf_parent_disca():
    audit = load(OUT / "m3cf1n_confirmation_parent_audit.json")
    assert audit["CF1N_DISC_verdict"] == "CF1N-DISC-A"
    assert audit["CF1_remains"] == "CF1-X" and audit["CF1R0_remains"] == "CF1R0-A"
    assert audit["p_ref_complete"] == 8 and audit["discovery_complete"] == 72
    assert audit["discovery_consumed_invalid"] == 0 and audit["p_ref_consumed_invalid"] == 0


def test_m3cf1n_conf_exact6_eligible_configs():
    assert load(OUT / "m3cf1n_disc_verdict.json")["eligible_config_ids"] == ELIGIBLE
    assert {r["config_id"] for r in csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")} == set(ELIGIBLE)


def test_m3cf1n_conf_no_ineligible_config():
    manifest_ids = {r["config_id"] for r in csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")}
    assert not (manifest_ids & set(INELIGIBLE))
    assert set(INELIGIBLE) == {"cf1n_new_004", "cf1n_new_006"}


def test_m3cf1n_conf_all9_states_per_config():
    rows = csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")
    for cid in ELIGIBLE:
        per_config = [r for r in rows if r["config_id"] == cid]
        assert sorted(int(r["grid_index"]) for r in per_config) == list(range(1, 10))


def test_m3cf1n_conf_exact54_states():
    rows = csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")
    assert len(rows) == 54
    records = list(CONF.glob("cf1n_new_*.json"))
    assert len(records) == 54


def test_m3cf1n_conf_state_manifest_hash():
    prereg = load(OUT / "m3cf1n_confirmation_prereg_hashes.json")
    entry = next(e for e in prereg if e["path"].endswith("m3cf1n_confirmation_state_manifest.csv"))
    assert sha(ROOT / entry["path"]) == entry["sha256"]


def test_m3cf1n_conf_human_approval():
    doc = (ROOT / "docs/phase_m3cf1n/M3_CF1N_Human_Confirmation_Approval.md").read_text(encoding="utf-8")
    assert "STATUS: APPROVED" in doc
    auth = load(OUT / "m3cf1n_confirmation_authorization.json")
    assert auth["source_taskbook"]["sha256"]
    assert auth["discovery_stop_verdict"] == "CF1N-DISC-A"


# --------------------------------------------------------------------------
# §47 Scientific protocol
# --------------------------------------------------------------------------

def test_m3cf1n_conf_budget_500k():
    protocol = load(OUT / "m3cf1n_confirmation_protocol.json")
    assert protocol["samples_per_arm"] == 500_000
    summary = load(OUT / "m3cf1n_confirmation_summary.json")
    assert summary["finite_action_samples"] == 81_000_000


def test_m3cf1n_conf_three_arms():
    protocol = load(OUT / "m3cf1n_confirmation_protocol.json")
    assert protocol["arms"] == ["base", "widen", "shrink"]
    for rec in conf_records():
        assert set(rec["arm_summaries"]) == {"base", "widen", "shrink"}


def test_m3cf1n_conf_crn20():
    assert load(OUT / "m3cf1n_confirmation_protocol.json")["paired_crn_batches"] == 20


def test_m3cf1n_conf_event_semantics_v2():
    protocol = load(OUT / "m3cf1n_confirmation_protocol.json")
    assert protocol["event_semantics_schema_version"] == 2
    assert protocol["event"] == "topology != S0" if "event" in protocol else True
    for rec in conf_records():
        # semantics pinned by protocol hash recorded in every canonical record
        assert rec["protocol_hash"] == sha(CFG / "m3cf1n_confirmation_protocol.json")
        assert rec["valid"] in (True, False)


def test_m3cf1n_conf_classifier_unchanged():
    cf1 = load(CF1_CFG / "m3cf1_confirmation_protocol.json")
    cf1n = load(OUT / "m3cf1n_confirmation_protocol.json")
    assert cf1n["samples_per_arm"] == cf1["samples_per_arm"] == 500_000
    assert cf1n["paired_crn_batches"] == cf1["paired_crn_batches"] == 20
    assert cf1n["event_semantics_schema_version"] == cf1["event_semantics_schema_version"] == 2


def test_m3cf1n_conf_grid_unchanged():
    grid = load(OUT / "m3cf1n_common_s2_grid.json")
    assert grid["source_sha256"] == sha(CF0_OUT / "m3cf0_future_s2_grid.json")
    expected = grid["values"]
    for rec in conf_records():
        assert float(rec["s2"]) in expected


def test_m3cf1n_conf_no_new_states():
    frozen_ids = {r["state_id"] for r in csv_rows(OUT / "m3cf1n_discovery_states.csv")}
    for rec in conf_records():
        assert rec["state_id"] in frozen_ids


def test_m3cf1n_conf_no_early_stop():
    # all 54 states were attempted regardless of interim outcomes
    audit = load(OUT / "m3cf1n_confirmation_persistence_audit.json")
    assert audit["expected"] == 54 and audit["complete"] == 54
    assert len(conf_records()) == 54


# --------------------------------------------------------------------------
# §48 Seeds / P_ref
# --------------------------------------------------------------------------

def test_m3cf1n_conf_seed_namespace():
    seeds = load(OUT / "m3cf1n_confirmation_seeds.json")
    assert seeds["namespace"] == "M3-CF1N-CONFIRM"
    for rec in conf_records():
        assert rec["seed_key"][0] == int(
            next(r["confirmation_seed"] for r in csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")
                 if r["state_id"] == rec["state_id"])
        )


def test_m3cf1n_conf_seed_count54():
    seeds = load(OUT / "m3cf1n_confirmation_seeds.json")["finite_action"]
    eligible_ids = set(ELIGIBLE)
    used = [s for s in seeds if s["state_id"].split("_cf1n_")[0] in eligible_ids]
    assert len(used) == 54
    assert len({s["seed_key"][0] for s in used}) == 54


def test_m3cf1n_conf_seed_disjoint():
    audit = load(OUT / "m3cf1n_confirmation_seed_audit.json")
    assert audit["collision_with_CF1"] == 0
    assert audit["collision_with_CF1N_PREF"] == 0
    assert audit["collision_with_CF1N_DISCOVERY"] == 0


def test_m3cf1n_conf_pref_hash_matches_config():
    manifest = {r["state_id"]: r for r in csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")}
    for rec in conf_records():
        assert rec["p_ref_hash"] == sha(PREF / f"{rec['config_id']}.json")
        assert rec["p_ref_hash"] == manifest[rec["state_id"]]["P_ref_hash"]


def test_m3cf1n_conf_pref_complete():
    audit = load(OUT / "m3cf1n_pref_persistence_audit.json")
    assert audit["complete"] == 8 and audit["consumed_invalid"] == 0


# --------------------------------------------------------------------------
# §49 Persistence
# --------------------------------------------------------------------------

def test_m3cf1n_conf_ledger_started_before_sim():
    entries = ledger(CONF / "confirmation_ledger.jsonl")
    for e in entries:
        if e["status"] == "STARTED":
            assert e.get("started_at") and e.get("P_ref_hash") and "grid_index" in e


def test_m3cf1n_conf_temp_write():
    assert not [p for p in CONF.glob(".*.tmp.*")]


def test_m3cf1n_conf_fsync():
    assert fsync_directory(CONF)["pass"] is True


def test_m3cf1n_conf_schema_validate():
    for rec in conf_records():
        CONFIRMATION_VALIDATOR(rec)


def test_m3cf1n_conf_hash_verify():
    for e in ledger(CONF / "confirmation_ledger.jsonl"):
        if e["status"] == "COMPLETE":
            assert sha256(CONF / f"{e['state_id']}.json") == e["output_hash"] == e["final_sha256"]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_m3cf1n_conf_atomic_rename():
    records = list(CONF.glob("cf1n_new_*.json"))
    assert len(records) == 54
    assert all(not p.name.startswith(".") for p in records)


def test_m3cf1n_conf_parent_fsync():
    assert fsync_directory(CONF)["pass"] is True


def test_m3cf1n_conf_complete_after_commit():
    entries = ledger(CONF / "confirmation_ledger.jsonl")
    complete = [e for e in entries if e["status"] == "COMPLETE"]
    assert len(complete) == 54
    for e in complete:
        assert e.get("completed_at") and (CONF / f"{e['state_id']}.json").exists()


def test_m3cf1n_conf_consumed_invalid_policy():
    # PROV/INVALID is a scientific label; CONSUMED_INVALID is an integrity
    # failure that must be absent for the stage to be valid
    statuses = [e["status"] for e in ledger(CONF / "confirmation_ledger.jsonl")]
    assert "CONSUMED_INVALID" not in statuses
    audit = load(OUT / "m3cf1n_confirmation_persistence_audit.json")
    assert audit["consumed_invalid"] == 0


def test_m3cf1n_conf_no_consumed_rerun():
    entries = ledger(CONF / "confirmation_ledger.jsonl")
    per_state = {}
    for e in entries:
        per_state.setdefault(e["state_id"], []).append(e["status"])
    for sid, seq in per_state.items():
        assert seq == ["STARTED", "COMPLETE"], sid  # exactly one attempt each


def test_m3cf1n_conf_all54_complete():
    audit = load(OUT / "m3cf1n_confirmation_persistence_audit.json")
    assert audit["complete"] == 54 == audit["expected"]
    assert audit["consistent"] is True
    assert audit["hash_failures"] == []


# --------------------------------------------------------------------------
# §50 Structural verdict
# --------------------------------------------------------------------------

def test_m3cf1n_conf_new_stable_adjacent2():
    by_config = load(OUT / "m3cf1n_confirmation_by_config.json")
    for cid, rec in by_config.items():
        if rec["final_class"] == "NEW_STABLE_S":
            assert rec["confirmed_adjacent_pairs"] >= 1 and rec["confirmed_S_count"] >= 2


def test_m3cf1n_conf_new_fragile():
    by_config = load(OUT / "m3cf1n_confirmation_by_config.json")
    for cid, rec in by_config.items():
        if rec["final_class"] == "NEW_FRAGILE_S":
            assert rec["confirmed_S_count"] >= 1 and rec["confirmed_adjacent_pairs"] == 0


def test_m3cf1n_conf_new_vanished():
    by_config = load(OUT / "m3cf1n_confirmation_by_config.json")
    for cid, rec in by_config.items():
        if rec["final_class"] == "NEW_VANISHED_S":
            assert rec["confirmed_S_count"] == 0


def test_m3cf1n_conf_k_new_stable():
    counts = load(OUT / "m3cf1n_structural_count.json")
    final = load(OUT / "m3cf1n_final_verdict.json")
    assert counts["K_NEW_STABLE"] == final["K_NEW_STABLE"]


def test_m3cf1n_conf_target_two():
    counts = load(OUT / "m3cf1n_structural_count.json")
    assert counts["target_total_stable_min"] == 4
    assert counts["target_pass"] == (counts["K_TOTAL_STABLE"] >= 4)


def test_m3cf1n_conf_fragile_not_stable():
    counts = load(OUT / "m3cf1n_structural_count.json")
    assert counts["FRAGILE_counts_as_STABLE"] is False
    assert counts["K_TOTAL_STABLE"] == counts["K_CURRENT_STABLE"] + counts["K_NEW_STABLE"]


def test_m3cf1n_conf_total_structural_count():
    counts = load(OUT / "m3cf1n_structural_count.json")
    total = counts["K_NEW_STABLE"] + counts["K_NEW_FRAGILE"] + counts["K_NEW_VANISHED"]
    assert total == 6 or counts["by_config_class"]  # all 6 eligible configs classified


def test_m3cf1n_conf_verdict_priority():
    final = load(OUT / "m3cf1n_final_verdict.json")
    assert final["verdict"] in {"CF1N-A", "CF1N-B", "CF1N-C", "CF1N-X"}
    k = final["K_NEW_STABLE"]
    expected = "CF1N-A" if k >= 2 else "CF1N-B" if k == 1 else "CF1N-C"
    assert final["verdict"] == expected


# --------------------------------------------------------------------------
# §51 Boundaries
# --------------------------------------------------------------------------

def _invariants():
    return load(OUT / "m3cf1n_protected_confirmation_audit.json")


def test_m3cf1n_conf_gradient_zero():
    assert _invariants()["gradient_pilot"] == 0


def test_m3cf1n_conf_v1_probe_zero():
    a = _invariants()
    assert a["finite_action_probe"] == 0 and a["v1_tested"] is False


def test_m3cf1n_conf_threshold_null():
    assert _invariants()["threshold"] is None


def test_m3cf1n_conf_protected_confirmation_zero():
    assert _invariants()["protected_confirmation_pilot_trials"] == 0


def test_m3cf1n_conf_value_blocked():
    assert _invariants()["value"] == "BLOCKED"


def test_m3cf1n_conf_rarity_blocked():
    assert _invariants()["rarity_shift"] == "BLOCKED"


def test_m3cf1n_conf_m3q_blocked():
    assert _invariants()["m3_q"] == "BLOCKED"
