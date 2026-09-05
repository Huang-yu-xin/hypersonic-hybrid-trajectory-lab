"""M3-PI1V parent/firewall contracts, post-incident status.

M3-PI1V was invalidated (PI1V-X) by the frozen persistence rule: attempt 1
began trials without durable COMPLETE records and attempt 2 was a same-stage
deterministic replay.  Both attempts are quarantined under
``results/phase_m3pi1v/quarantine_attempt*`` (DIAGNOSTIC ONLY) and the
original 24-state panel is retired by M3-PI1VR0.  These tests verify the
frozen parent-provenance facts that remain true of the retired panel.
"""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1v/summary"
CFG = ROOT / "configs/phase_m3pi1v"
CF2 = ROOT / "results/phase_m3cf2/summary"
UC2R = ROOT / "results/phase_m3uc2r/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
QUAR1 = PI1V_Q1 = ROOT / "results/phase_m3pi1v/quarantine_attempt1"
QUAR2 = ROOT / "results/phase_m3pi1v/quarantine_attempt2"

PANEL_HASH = "843ee98e5be20d71964684d29e7671f5168bd2c36a6d2b02a745be88aff85d5c"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3pi1v_parent_cf2a():
    assert load(CF2 / "m3cf2_final_verdict.json")["verdict"] == "CF2-A"
    pa = load(OUT / "m3pi1v_parent_panel_audit.json")
    assert pa["parent_panel_sha256"] == PANEL_HASH
    assert pa["all_parent_verdicts_match"] is True


def test_m3pi1v_panel_hash_exact():
    assert sha(CF2 / "m3cf2_development_panel.csv") == PANEL_HASH
    cfg = load(CFG / "m3pi1v_panel.json")
    assert cfg["sha256"] == PANEL_HASH


def test_m3pi1v_panel_exact24():
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    assert len(rows) == 24
    assert len({r["state_id"] for r in rows}) == 24


def test_m3pi1v_panel_exact8w8s8nd():
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    grp = Counter(r["truth_group"] for r in rows)
    tru = Counter(r["truth"] for r in rows)
    assert grp == {"W": 8, "S": 8, "ND": 8}
    assert tru == {"WIDEN": 8, "SHRINK": 8, "HOLD": 4, "AMBIGUOUS": 4}


def test_m3pi1v_no_panel_replacement():
    pa = load(OUT / "m3pi1v_parent_panel_audit.json")
    assert pa["panel_replacement_attempted"] is False
    assert pa["panel_hash_verified"] is True
    # the panel itself was never regenerated; it was retired intact by PI1VR0
    retired = {r["state_id"]: r["status"]
               for r in csv_rows(VR0 / "m3pi1vr0_retired_development_states.csv")}
    assert len(retired) == 24
    assert all(s == "PILOT_EXPOSED_RETIRED" for s in retired.values())


def _pi1v_touched_states():
    touched = set()
    for q in (QUAR1, QUAR2):
        tdir = q / "trials"
        if tdir.exists():
            touched |= {d.name for d in tdir.iterdir() if d.is_dir()}
    return touched


def test_m3pi1v_reserve_overlap_zero():
    fw = load(OUT / "m3pi1v_reserve_firewall_audit.json")
    assert fw["panel_reserve_overlap"] == []
    assert fw["panel_uc2r_confirmation_overlap"] == []
    assert fw["overlap_is_zero"] is True
    panel = {r["state_id"] for r in csv_rows(CF2 / "m3cf2_development_panel.csv")}
    reserve = {r["state_id"] for r in csv_rows(
        CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    assert panel & reserve == set()
    # even after the incident, no reserve state was ever touched
    assert _pi1v_touched_states() & reserve == set()


def test_m3pi1v_reserve_pilot_zero():
    fw = load(OUT / "m3pi1v_reserve_firewall_audit.json")
    assert fw["pilot_protected_reserve_states"] == 70
    reserve = {r["state_id"] for r in csv_rows(
        CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    assert _pi1v_touched_states() & reserve == set()


def test_m3pi1v_uc2r_protected_pilot_zero():
    fw = load(OUT / "m3pi1v_reserve_firewall_audit.json")
    assert fw["uc2r_protected_pilot_exposure_planned"] == 0
    assert fw["uc2r_protected_pilot_exposure_observed"] == 0
    uc2r_conf = {r["state_id"] for r in csv_rows(
        UC2R / "m3uc2r_reference_states.csv") if r["split"] == "CONFIRMATION"}
    assert len(uc2r_conf) == 40
    assert _pi1v_touched_states() & uc2r_conf == set()


def test_m3pi1v_cf1_invalid_not_used():
    assert load(ROOT / "results/phase_m3cf1/summary/m3cf1_final_verdict.json")["verdict"] == "CF1-X"
    pa = load(OUT / "m3pi1v_parent_panel_audit.json")
    assert pa["cf1_invalid_not_used"] is True
    assert set(pa["panel_source_stages"]) <= {"M3-SF2", "M3-CF1N"}
