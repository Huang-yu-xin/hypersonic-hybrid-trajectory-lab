"""M3-PI1VN parent/freshness/retired-data contracts (taskbook Sec. 37)."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vn/summary"
CFG = ROOT / "configs/phase_m3pi1vn"
WCF1_OUT = ROOT / "results/phase_m3wcf1/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
TRIALS = ROOT / "results/phase_m3pi1vn/trials"

CONSUMED = "cf1n_new_000_wa1_w_s2_1p788854382"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3pi1vn_parent_wcf1a():
    assert load(ROOT / "results/phase_m3wcf1/summary/m3wcf1_final_verdict.json")["verdict"] == "WCF1-A"
    pa = load(OUT / "m3pi1vn_parent_audit.json")
    assert pa["all_match"] is True


def test_m3pi1vn_panel_hash_matches_wcf1():
    a = load(OUT / "m3pi1vn_panel_hash_audit.json")
    w = load(WCF1_OUT / "m3wcf1_fresh_development_panel_hash.json")
    assert a["recomputed_sha256"] == a["wcf1_committed_sha256"] == w["panel_sha256"]
    assert a["panel_regeneration_attempted"] is False


def test_m3pi1vn_panel_exact24():
    rows = csv_rows(WCF1_OUT / "m3wcf1_fresh_development_panel.csv")
    assert len(rows) == 24
    cfg = load(CFG / "m3pi1vn_panel.json")
    assert len(cfg["states"]) == 24


def test_m3pi1vn_panel_exact8w8s8nd():
    from collections import Counter
    rows = csv_rows(WCF1_OUT / "m3wcf1_fresh_development_panel.csv")
    tru = Counter(r["truth"] for r in rows)
    assert tru == {"WIDEN": 8, "SHRINK": 8, "HOLD": 1, "AMBIGUOUS": 7}


def test_m3pi1vn_panel_pilot_zero_pretrial():
    rows = csv_rows(OUT / "m3pi1vn_panel_freshness_audit.csv")
    assert all(int(r["pilot_exposure_pre_pi1vn"]) == 0 for r in rows)


def test_m3pi1vn_panel_probe_zero_pretrial():
    rows = csv_rows(OUT / "m3pi1vn_panel_freshness_audit.csv")
    assert all(int(r["probe_exposure_pre_pi1vn"]) == 0 for r in rows)
    assert all(int(r["threshold_replay_exposure"]) == 0 for r in rows)


def test_m3pi1vn_no_panel_replacement():
    a = load(OUT / "m3pi1vn_panel_hash_audit.json")
    assert a["panel_regeneration_attempted"] is False


def test_m3pi1vn_reserve_overlap_zero():
    fw = load(OUT / "m3pi1vn_reserve_firewall_audit.json")
    assert fw["panel_current_reserve_overlap"] == []
    remaining = {r["state_id"] for r in csv_rows(
        WCF1_OUT / "m3wcf1_remaining_protected_reserve.csv")}
    panel = {r["state_id"] for r in csv_rows(WCF1_OUT / "m3wcf1_fresh_development_panel.csv")}
    assert panel & remaining == set()


def test_m3pi1vn_reserve_pilot_zero():
    fw = load(OUT / "m3pi1vn_reserve_firewall_audit.json")
    assert fw["planned_reserve_pilot_exposure"] == 0
    v = load(OUT / "m3pi1vn_final_verdict.json") \
        if (OUT / "m3pi1vn_final_verdict.json").exists() else None
    if v is not None:
        assert v["reserve_pilot_trials"] == 0


# ------------------------- retired/invalid data ----------------------------

def test_m3pi1vn_pi1v_primary_x():
    status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["PI1V valid verdict"] == "PI1V-X"
    assert status["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY"


def test_m3pi1vn_no_attempt2_v1_input():
    fw = load(OUT / "m3pi1vn_retired_data_firewall.json")
    assert fw["attempt2_diagnostics_used_in_design"] is False
    assert "V1 best-safe coverage" in fw["forbidden_attempt2_diagnostics"]


def test_m3pi1vn_no_attempt2_s1_input():
    fw = load(OUT / "m3pi1vn_retired_data_firewall.json")
    assert "S1 best-safe coverage" in fw["forbidden_attempt2_diagnostics"]


def test_m3pi1vn_no_old_cf2_panel():
    fw = load(OUT / "m3pi1vn_retired_data_firewall.json")
    assert fw["old_cf2_panel_states_in_panel"] == 0


def test_m3pi1vn_no_wa1_consumed_state():
    fw = load(OUT / "m3pi1vn_retired_data_firewall.json")
    assert fw["consumed_candidate_in_panel"] is False
    manifest = (OUT / "m3pi1vn_reference_state_manifest.csv")
    if manifest.exists():
        assert CONSUMED not in manifest.read_text(encoding="utf-8")
    panel = (WCF1_OUT / "m3wcf1_fresh_development_panel.csv").read_text(encoding="utf-8")
    assert CONSUMED not in panel


def test_m3pi1vn_no_retired_seed_reuse():
    seeds = load(OUT / "m3pi1vn_seed_manifest.json")
    assert seeds["collision_with_retired_seeds"] == []
    assert seeds["collision_with_all_prior"] == []
    fw = load(OUT / "m3pi1vn_retired_data_firewall.json")
    assert "M3-PI1V-GRAD" in fw["retired_seed_namespaces"]
