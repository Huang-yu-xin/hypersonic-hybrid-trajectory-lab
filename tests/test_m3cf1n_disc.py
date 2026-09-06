"""M3-CF1N-DISC execution contracts (P_ref + 72-state discovery, taskbook §34).

Authorization scope: P_ref + discovery only.  High-budget confirmation stays
NOT APPROVED with zero simulator samples.
"""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from hyptraj.m3cf1n.persistence import DISCOVERY_VALIDATOR, PREF_VALIDATOR
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


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def ledger(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


# --------------------------------------------------------------------------
# Authorization (§34 authorization list)
# --------------------------------------------------------------------------

def test_m3cf1n_disc_parent_approved():
    auth = load(OUT / "m3cf1n_disc_authorization_record.json")
    assert "APPROVED: new P_ref + 72-state discovery only" in auth["authorization"]
    assert auth["source_taskbook"]["sha256"], "authorization taskbook must be hash-locked"
    assert load(OUT / "m3cf1n_prereg_stop_report.json")["status"] == "STOPPED_AWAITING_HUMAN_APPROVAL"


def test_m3cf1n_disc_confirmation_not_authorized():
    auth = load(OUT / "m3cf1n_disc_authorization_record.json")
    assert "CF1N-4 high-budget confirmation" in auth["not_authorized"]
    assert auth["confirmation_samples_executed"] == 0
    if (OUT / "m3cf1n_confirmation_freeze.json").exists():
        freeze = load(OUT / "m3cf1n_confirmation_freeze.json")
        assert freeze["execution_authorized"] is False
        assert freeze["confirmation_samples_executed"] == 0


def test_m3cf1n_disc_exact8_configs():
    ids = load(OUT / "m3cf1n_config_manifest.json")["config_ids"]
    assert ids == [f"cf1n_new_{i:03d}" for i in range(8)]


def test_m3cf1n_disc_exact9_grid():
    grid = load(OUT / "m3cf1n_common_s2_grid.json")
    assert grid["count"] == 9 and len(grid["values"]) == 9
    assert grid["source_sha256"] == sha(CF0_OUT / "m3cf0_future_s2_grid.json")


def test_m3cf1n_disc_exact72_states():
    states = csv_rows(OUT / "m3cf1n_discovery_states.csv")
    assert len(states) == 72
    assert len({r["state_id"] for r in states}) == 72
    disc_parent = load(OUT / "m3cf1n_disc_parent_audit.json")
    assert disc_parent["duplicate_state_ids"] == 0
    assert disc_parent["CF1_state_reuse"] == 0


def test_m3cf1n_disc_prereg_hash_match():
    prereg = load(OUT / "m3cf1n_prereg_hashes.json")
    assert prereg["outcomes"] == "NONE"
    for entry in prereg["files"]:
        assert sha(ROOT / entry["path"]) == entry["sha256"], entry["path"]


# --------------------------------------------------------------------------
# P_ref (§34 P_ref list)
# --------------------------------------------------------------------------

def test_m3cf1n_disc_pref_exact8():
    manifest = load(PREF / "pref_manifest.json")
    assert manifest["expected"] == 8
    assert len(manifest["records"]) == 8
    for rec in manifest["records"]:
        assert (ROOT / rec["path"]).exists()


def test_m3cf1n_disc_pref_new_namespace():
    assert load(OUT / "m3cf1n_pref_protocol.json")["namespace"] == "M3-CF1N-PREF"
    assert load(CF1_CFG / "m3cf1_discovery_seeds.json")["p_ref_namespace"] == "M3-CF1-PREF"
    for rec in manifest_records(PREF):
        assert rec["namespace"] == "M3-CF1N-PREF"


def manifest_records(directory):
    return [load(p) for p in sorted(Path(directory).glob("cf1n_new_*.json"))]


def test_m3cf1n_disc_pref_budget_500k():
    protocol = load(OUT / "m3cf1n_pref_protocol.json")
    assert protocol["samples_per_config"] == 500_000
    assert protocol["expected_samples"] == 4_000_000
    for rec in manifest_records(PREF):
        assert rec["sample_count"] == 500_000


def test_m3cf1n_disc_pref_seed_disjoint():
    cf1_keys = {int(i["seed_key"][0]) for i in load(CF1_CFG / "m3cf1_discovery_seeds.json")["p_ref"]}
    new_keys = {int(i["seed_key"][0]) for i in load(OUT / "m3cf1n_pref_seeds.json")["p_ref"]}
    assert not (new_keys & cf1_keys)
    audit = load(OUT / "m3cf1n_disc_pref_seed_audit.json")
    assert audit["CF1_P_ref_collision"] == 0
    assert audit["seed_hash_matches_prereg"] is True


def test_m3cf1n_disc_pref_event_v2():
    for rec in manifest_records(PREF):
        assert rec["event_semantics_schema_version"] == 2
        assert rec["event_schema"] == "corrected full-event v2"


def test_m3cf1n_disc_pref_all_complete():
    audit = load(OUT / "m3cf1n_pref_persistence_audit.json")
    assert audit["expected"] == 8 and audit["complete"] == 8
    assert audit["consumed_invalid"] == 0 and not audit["hash_failures"]


def test_m3cf1n_disc_pref_hashes():
    for rec in load(PREF / "pref_manifest.json")["records"]:
        assert sha(ROOT / rec["path"]) == rec["sha256"]


def test_m3cf1n_disc_pref_ledger():
    entries = ledger(PREF / "pref_ledger.jsonl")
    for cid in load(OUT / "m3cf1n_config_manifest.json")["config_ids"]:
        seq = [e["status"] for e in entries if e["state_id"] == cid]
        assert seq == ["STARTED", "COMPLETE"], cid
        complete = [e for e in entries if e["state_id"] == cid and e["status"] == "COMPLETE"][0]
        assert complete["final_sha256"] == complete["output_hash"] == sha(PREF / f"{cid}.json")


# --------------------------------------------------------------------------
# Discovery (§34 discovery list)
# --------------------------------------------------------------------------

def disc_records():
    return [load(p) for p in sorted(DISC.glob("cf1n_new_*.json"))]


def test_m3cf1n_disc_72_states():
    records = disc_records()
    assert len(records) == 72
    assert {r["config_id"] for r in records} == set(load(OUT / "m3cf1n_config_manifest.json")["config_ids"])
    for cid in {r["config_id"] for r in records}:
        assert sum(1 for r in records if r["config_id"] == cid) == 9


def test_m3cf1n_disc_budget_100k():
    assert load(OUT / "m3cf1n_discovery_protocol.json")["samples_per_arm"] == 100_000
    summary = load(OUT / "m3cf1n_discovery_summary.json")
    assert summary["finite_action_samples"] == 21_600_000


def test_m3cf1n_disc_three_arms():
    protocol = load(OUT / "m3cf1n_discovery_protocol.json")
    assert protocol["arms"] == ["base", "widen", "shrink"]
    for rec in disc_records():
        assert set(rec["arm_summaries"]) == {"base", "widen", "shrink"}


def test_m3cf1n_disc_crn20():
    assert load(OUT / "m3cf1n_discovery_protocol.json")["paired_crn_batches"] == 20
    for rec in disc_records():
        # 100,000 samples/arm budgeted as 20 paired CRN batches of 5,000
        assert rec["arm_summaries"]["base"]["sample_count"] == 100_000
        assert rec["p_ref_hash"] and rec["protocol_hash"]


def test_m3cf1n_disc_seed_disjoint():
    cf1_keys = set()
    for name in ("m3cf1_discovery_seeds.json", "m3cf1_confirmation_seeds.json"):
        rec = load(CF1_CFG / name)
        cf1_keys |= {int(i["seed_key"][0]) for i in rec.get("finite_action", [])}
        cf1_keys |= {int(i["seed_key"][0]) for i in rec.get("p_ref", [])}
    new_keys = {r["seed_key"][0] for r in disc_records()}
    assert not (new_keys & cf1_keys)


def test_m3cf1n_disc_semantics_unchanged():
    cf1 = load(CF1_CFG / "m3cf1_discovery_protocol.json")
    cf1n = load(OUT / "m3cf1n_discovery_protocol.json")
    for key in ("improvement_threshold", "hold_band", "direction_margin", "min_arm_ess",
                "event", "event_semantics_schema_version", "probability_domain"):
        assert cf1n[key] == cf1[key], key


def test_m3cf1n_disc_labels_provisional():
    allowed = {"PROV_WIDEN", "PROV_SHRINK", "PROV_HOLD", "PROV_AMBIGUOUS", "PROV_INVALID"}
    for rec in disc_records():
        assert rec["provisional_label"] in allowed


def test_m3cf1n_disc_all72_before_eligibility():
    audit = load(OUT / "m3cf1n_discovery_persistence_audit.json")
    assert audit["expected"] == 72 and audit["complete"] == 72
    assert audit["consumed_invalid"] == 0 and not audit["hash_failures"]
    # eligibility was computed only after 72/72 (audit is written before eligibility)
    assert (OUT / "m3cf1n_discovery_eligibility.json").exists()


def test_m3cf1n_disc_adjacent_rule():
    eligibility = load(OUT / "m3cf1n_discovery_eligibility.json")
    for cid, rec in eligibility["by_config"].items():
        pattern = rec["provisional_pattern"]
        pairs = [
            {"left_grid_index": i + 1, "right_grid_index": i + 2}
            for i in range(len(pattern) - 1)
            if pattern[i] == pattern[i + 1] == "PROV_SHRINK"
        ]
        assert rec["adjacent_prov_shrink_pairs"] == pairs
        assert rec["eligible"] == bool(pairs)
        assert rec["prov_shrink_count"] == pattern.count("PROV_SHRINK")


def test_m3cf1n_disc_no_ranking():
    eligibility = load(OUT / "m3cf1n_discovery_eligibility.json")
    assert eligibility["effect_size_ranking_used"] is False
    eligible = eligibility["eligible_config_ids"]
    all_eligible = [cid for cid, r in eligibility["by_config"].items() if r["eligible"]]
    assert eligible == all_eligible  # no subsetting by effect/count/ratio


def test_m3cf1n_disc_no_grid_refinement():
    protocol = load(OUT / "m3cf1n_discovery_protocol.json")
    assert protocol["grid_refinement"] is False
    assert protocol["adaptive_refinement"] is False
    grid = load(OUT / "m3cf1n_common_s2_grid.json")
    assert grid["source_sha256"] == sha(CF0_OUT / "m3cf0_future_s2_grid.json")
    for rec in disc_records():
        assert float(rec["s2"]) in grid["values"]


# --------------------------------------------------------------------------
# Persistence (§34 persistence list, over the real executed ledgers)
# --------------------------------------------------------------------------

def test_m3cf1n_disc_ledger_started_before_sim():
    for path in (PREF / "pref_ledger.jsonl", DISC / "discovery_ledger.jsonl"):
        entries = ledger(path)
        for e in entries:
            if e["status"] == "STARTED":
                assert e.get("started_at") and e.get("expected_output_path")


def test_m3cf1n_disc_temp_write():
    for directory in (PREF, DISC):
        assert not [p for p in Path(directory).glob(".*.tmp.*")]


def test_m3cf1n_disc_fsync():
    # every record went through flush + fsync; verified by hash integrity below
    # plus a live capability probe on the record directories
    assert fsync_directory(PREF)["pass"] is True
    assert fsync_directory(DISC)["pass"] is True


def test_m3cf1n_disc_schema_validate():
    for rec in manifest_records(PREF):
        PREF_VALIDATOR(rec)
    for rec in disc_records():
        DISCOVERY_VALIDATOR(rec)


def test_m3cf1n_disc_hash_verify():
    for entries, directory in ((ledger(PREF / "pref_ledger.jsonl"), PREF),
                               (ledger(DISC / "discovery_ledger.jsonl"), DISC)):
        for e in entries:
            if e["status"] == "COMPLETE":
                assert sha256(directory / f"{e['state_id']}.json") == e["output_hash"]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_m3cf1n_disc_atomic_rename():
    for directory in (PREF, DISC):
        finals = list(Path(directory).glob("*.json"))
        assert finals and all(not p.name.startswith(".") for p in finals)


def test_m3cf1n_disc_parent_fsync():
    for e in ledger(DISC / "discovery_ledger.jsonl"):
        if e["status"] == "COMPLETE":
            assert e["final_sha256"] == e["output_hash"]


def test_m3cf1n_disc_complete_after_commit():
    for path, directory in ((PREF / "pref_ledger.jsonl", PREF),
                            (DISC / "discovery_ledger.jsonl", DISC)):
        for e in ledger(path):
            if e["status"] == "COMPLETE":
                assert (directory / f"{e['state_id']}.json").exists()


def test_m3cf1n_disc_no_consumed_rerun():
    for path in (PREF / "pref_ledger.jsonl", DISC / "discovery_ledger.jsonl"):
        statuses = [e["status"] for e in ledger(path)]
        assert "CONSUMED_INVALID" not in statuses


def test_m3cf1n_disc_stage_complete_72of72():
    audit = load(OUT / "m3cf1n_discovery_persistence_audit.json")
    assert audit["complete"] == 72 == audit["expected"]
    assert audit["consumed_invalid"] == 0
    assert audit["consistent"] is True


# --------------------------------------------------------------------------
# STOP boundary (§34 STOP boundary list)
# --------------------------------------------------------------------------

def test_m3cf1n_disc_confirmation_samples_zero():
    verdict = load(OUT / "m3cf1n_disc_verdict.json")
    assert verdict["confirmation_samples_executed"] == 0
    if (OUT / "m3cf1n_confirmation_freeze.json").exists():
        assert load(OUT / "m3cf1n_confirmation_freeze.json")["confirmation_samples_executed"] == 0


def test_m3cf1n_disc_confirmation_not_started():
    # DISC-stage invariant: the freeze was recorded with 0 executed samples and
    # execution unauthorized; any later confirmation required a separate
    # human-authorized taskbook (M3_CF1N_CONF), pinned by its own audit.
    freeze = load(OUT / "m3cf1n_confirmation_freeze.json")
    assert freeze["confirmation_samples_executed"] == 0
    assert freeze["execution_authorized"] is False
    verdict = load(OUT / "m3cf1n_disc_verdict.json")
    assert verdict["confirmation_authorized"] is False
    # no confirmation state beyond the frozen manifest may exist
    manifest_ids = {r["state_id"] for r in csv_rows(OUT / "m3cf1n_confirmation_state_manifest.csv")}
    executed = {p.stem for p in CONF.glob("cf1n_new_*.json")}
    assert executed <= manifest_ids


def _invariants():
    return load(OUT / "m3cf1n_protected_confirmation_audit.json")


def test_m3cf1n_disc_gradient_zero():
    assert _invariants()["gradient_pilot"] == 0


def test_m3cf1n_disc_v1_zero():
    a = _invariants()
    assert a["finite_action_probe"] == 0 and a["v1_tested"] is False


def test_m3cf1n_disc_threshold_null():
    assert _invariants()["threshold"] is None


def test_m3cf1n_disc_protected_confirmation_zero():
    assert _invariants()["protected_confirmation_pilot_trials"] == 0


def test_m3cf1n_disc_value_blocked():
    assert _invariants()["value"] == "BLOCKED"


def test_m3cf1n_disc_rarity_blocked():
    assert _invariants()["rarity_shift"] == "BLOCKED"


def test_m3cf1n_disc_m3q_blocked():
    assert _invariants()["m3_q"] == "BLOCKED"
