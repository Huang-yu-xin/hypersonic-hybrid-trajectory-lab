"""M3-WCF1 persistence + capacity + boundary contracts (taskbook Sec. 37)."""
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402
from hyptraj.m3pi1vr0.persistence import (  # noqa: E402
    ReplayError,
    safe_fs_id,
    validate_safe_path,
)
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    HASH_FIELD,
    record_file_hash,
    scientific_payload_hash,
)

OUT = ROOT / "results/phase_m3wcf1/summary"
PREF = ROOT / "results/phase_m3wcf1/pref"
REF = ROOT / "results/phase_m3wcf1/reference"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def _final():
    return load(OUT / "m3wcf1_final_verdict.json")


# --------------------------- persistence -----------------------------------

def test_m3wcf1_safe_path(tmp_path):
    enc = validate_safe_path("wcf1_new_000_wcf1_s2_1p25", tmp_path / "r.json")
    assert ":" not in enc
    contract = load(OUT / "m3wcf1_persistence_contract.json")
    assert contract["mandatory_order"][0] == "1. safe path"
    assert contract["mandatory_order"][1] == "2. durable STARTED before simulator"


def test_m3wcf1_started_before_simulator(tmp_path):
    # verified on the real ledgers: every COMPLETE has an earlier STARTED
    for ledger in (PREF / "pref_ledger.jsonl", REF / "reference_ledger.jsonl"):
        entries = ledger_entries(ledger)
        first = {}
        ok = True
        for i, e in enumerate(entries):
            rid = e.get("state_id")
            if e.get("status") == "STARTED":
                first.setdefault(rid, i)
            elif e.get("status") == "COMPLETE":
                ok &= rid in first and first[rid] < i
        assert ok


def test_m3wcf1_non_circular_hash_contract():
    for d, n in ((PREF, 6), (REF, 12)):
        checked = 0
        for p in d.glob("*.json"):
            rec = load(p)
            if rec.get("schema") not in ("m3wcf1_pref_v1", "m3wcf1_reference_v1"):
                continue                      # skip sealed manifests
            assert HASH_FIELD in rec
            assert scientific_payload_hash(rec) == rec[HASH_FIELD]
            checked += 1
        assert checked == n
    # non-circularity: removing the field and re-hashing reproduces it
    rec = load(REF / "wcf1_new_000_wcf1_s2_1p25.json")
    body = {k: v for k, v in rec.items() if k != HASH_FIELD}
    assert hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() \
        == rec[HASH_FIELD]


def test_m3wcf1_atomic_persistence():
    for ledger, directory, n in ((PREF / "pref_ledger.jsonl", PREF, 6),
                                 (REF / "reference_ledger.jsonl", REF, 12)):
        entries = ledger_entries(ledger)
        complete = [e for e in entries if e.get("status") == "COMPLETE"]
        assert len(complete) == n
        for e in complete:
            f = directory / f"{e['state_id']}.json"
            assert f.exists()
            assert hashlib.sha256(f.read_bytes()).hexdigest() == e["record_file_hash"]
            assert not list(f.parent.glob(".*.tmp.*"))


def test_m3wcf1_hash_verify():
    for name in ("m3wcf1_pref_persistence_audit.json",
                 "m3wcf1_reference_persistence_audit.json"):
        audit = load(OUT / name)
        assert audit["hashes"] == "PASS" and not audit["problems"]


def test_m3wcf1_consumed_invalid_no_replay():
    for ledger in (PREF / "pref_ledger.jsonl", REF / "reference_ledger.jsonl"):
        entries = ledger_entries(ledger)
        assert not any(e.get("status") == "CONSUMED_INVALID" for e in entries)
        seen = {}
        for e in entries:
            seen.setdefault(e.get("state_id"), set()).add(e.get("status"))
        assert all(s == {"STARTED", "COMPLETE"} for s in seen.values())


def test_m3wcf1_no_frozen_overwrite():
    prereg = load(OUT / "m3wcf1_prereg_hashes.json")
    for e in prereg["files"]:
        p = ROOT / e["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]


# ----------------------------- capacity ------------------------------------

def test_m3wcf1_new_w_config_definition():
    doc = load(OUT / "m3wcf1_new_w_config_summary.json")
    assert doc["K_NEW_W_CONFIG"] >= 1
    by = doc["by_config"]
    for wid, v in by.items():
        assert v["NEW_W_CONFIG"] == any(l == "WIDEN" for l in v["labels"])
        assert v["ROBUST_NEW_W_CONFIG"] == all(l == "WIDEN" for l in v["labels"])


def test_m3wcf1_combined_fresh_w_pool():
    rows = csv_rows(OUT / "m3wcf1_combined_fresh_w_pool.csv")
    retired = {r["state_id"] for r in csv_rows(
        VR0 / "m3pi1vr0_retired_development_states.csv")}
    assert not any(r["state_id"] in retired for r in rows)
    origins = Counter(r["origin"] for r in rows)
    assert set(origins) <= {"reserve", "wa1r", "wcf1"}
    assert all(r["truth"] == "WIDEN" for r in rows)


def test_m3wcf1_exact8_w_feasibility():
    f = load(OUT / "m3wcf1_w_diversity_feasibility.json")
    subset = f["selected_subset"]
    assert len(subset) == 8
    assert f["W_DIVERSITY_FEASIBLE"] == "YES"


def test_m3wcf1_w_configs_ge6():
    f = load(OUT / "m3wcf1_w_diversity_feasibility.json")
    assert f["distinct_configs"] >= 6 and f["configs_ge_6"] is True


def test_m3wcf1_w_max2_per_config():
    f = load(OUT / "m3wcf1_w_diversity_feasibility.json")
    assert f["max2_per_config"] is True
    pool = {s["state_id"]: s for s in csv_rows(OUT / "m3wcf1_combined_fresh_w_pool.csv")}
    cfg = Counter(pool[sid]["config_id"] for sid in f["selected_subset"])
    assert max(cfg.values()) <= 2 and len(cfg) >= 6


def test_m3wcf1_full_panel_8w8s8nd():
    cap = load(OUT / "m3wcf1_full_panel_capacity.json")
    assert cap["full_panel_feasible"] is True
    rows = csv_rows(OUT / "m3wcf1_fresh_development_panel.csv")
    grp = Counter("W" if r["truth"] == "WIDEN"
                  else "S" if r["truth"] == "SHRINK" else "ND" for r in rows)
    assert len(rows) == 24 and grp == {"W": 8, "S": 8, "ND": 8}


def test_m3wcf1_fresh_panel_unique():
    rows = csv_rows(OUT / "m3wcf1_fresh_development_panel.csv")
    assert len({r["state_id"] for r in rows}) == 24


def test_m3wcf1_fresh_panel_pilot_zero():
    rows = csv_rows(OUT / "m3wcf1_fresh_development_panel.csv")
    assert all(int(r["pilot_exposure"]) == 0 for r in rows)


def test_m3wcf1_fresh_panel_probe_zero():
    rows = csv_rows(OUT / "m3wcf1_fresh_development_panel.csv")
    assert all(int(r["probe_exposure"]) == 0 for r in rows)


def test_m3wcf1_fresh_panel_hash():
    import hashlib
    rec = load(OUT / "m3wcf1_fresh_development_panel_hash.json")
    digest = hashlib.sha256(
        (OUT / "m3wcf1_fresh_development_panel.csv").read_bytes()).hexdigest()
    assert rec["panel_sha256"] == digest
    assert rec["invalid_run_scores_used"] is False


def test_m3wcf1_remaining_reserve_protected():
    rem = {r["state_id"] for r in csv_rows(OUT / "m3wcf1_remaining_protected_reserve.csv")}
    panel = {r["state_id"] for r in csv_rows(OUT / "m3wcf1_fresh_development_panel.csv")}
    reserve = {r["state_id"] for r in csv_rows(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    # every unselected reserve state remains protected; selected ones joined
    # the frozen panel
    assert (reserve - panel) <= rem
    assert not (panel & rem)
    summary = load(OUT / "m3wcf1_remaining_reserve_summary.json")
    assert summary["pilot_exposure"] == 0


# ----------------------------- boundaries ----------------------------------

def test_m3wcf1_gradient_zero():
    assert _final()["gradient_pilot_trials"] == 0


def test_m3wcf1_probe_zero():
    assert _final()["finite_action_probe_trials"] == 0


def test_m3wcf1_threshold_null():
    assert _final()["v1_threshold"] is None and _final()["s1_threshold"] is None


def test_m3wcf1_confirmation_zero():
    assert _final()["protected_confirmation_pilot_trials"] == 0
    assert _final()["s1_confirmation_authorized"] is False


def test_m3wcf1_value_blocked():
    assert _final()["value"] == "BLOCKED"


def test_m3wcf1_rarity_blocked():
    assert _final()["rarity_shift"] == "BLOCKED"


def test_m3wcf1_m3q_blocked():
    assert _final()["m3_q"] == "BLOCKED"
