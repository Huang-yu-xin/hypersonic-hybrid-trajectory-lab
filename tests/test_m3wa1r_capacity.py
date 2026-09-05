"""M3-WA1R fresh-capacity + boundary contracts (taskbook Sec. 48-49)."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1r/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def executed():
    return (ROOT / "results/phase_m3wa1r/reference/reference_manifest.json").exists()


def test_m3wa1r_combined_fresh_pool():
    p = OUT / "m3wa1r_combined_fresh_reference_pool.csv"
    if not executed():
        assert not p.exists()
        return
    rows = csv_rows(p)
    retired = {r["state_id"] for r in csv_rows(
        VR0 / "m3pi1vr0_retired_development_states.csv")}
    assert not any(r["state_id"] in retired for r in rows)
    assert not any(r["state_id"] == "cf1n_new_000_wa1_w_s2_1p788854382" for r in rows)
    origins = Counter(r["origin"] for r in rows)
    assert set(origins) <= {"reserve", "wa1r"}


def test_m3wa1r_w_exact8_feasibility():
    if not executed():
        assert not (OUT / "m3wa1r_w_feasibility.json").exists()
        return
    f = load(OUT / "m3wa1r_w_feasibility.json")
    assert f["old_untouched_w"] == 7
    assert f["exact_8_selectable"] is bool(f["configs_ge_6"] and f["max2_per_config"]
                                           and f["selectable_capacity_at_max2"] >= 8)


def test_m3wa1r_w_configs_ge6():
    if not executed():
        return
    f = load(OUT / "m3wa1r_w_feasibility.json")
    # retiring the consumed config-000 candidate caps the union at 5 configs
    assert f["distinct_configs"] <= 5
    assert f["configs_ge_6"] is (f["distinct_configs"] >= 6)


def test_m3wa1r_w_max2_per_config():
    if not executed():
        return
    f = load(OUT / "m3wa1r_w_feasibility.json")
    pool_counts = Counter(s["config_id"] for s in
                          csv_rows(OUT / "m3wa1r_combined_fresh_reference_pool.csv")
                          if s["truth"] == "WIDEN")
    assert f["config_counts"] == dict(pool_counts)
    assert f["max2_per_config"] == (max(pool_counts.values()) <= 2
                                    if pool_counts else False)


def test_m3wa1r_full_panel_8w8s8nd():
    if not executed():
        assert not (OUT / "m3wa1r_full_panel_capacity.json").exists()
        return
    cap = load(OUT / "m3wa1r_full_panel_capacity.json")
    if not cap["full_panel_feasible"]:
        assert cap["W"] == "NA" and cap["panel_states"] == "NA"
        assert not (OUT / "m3wa1r_fresh_development_panel.csv").exists()
    else:
        rows = csv_rows(OUT / "m3wa1r_fresh_development_panel.csv")
        grp = Counter("W" if r["truth"] == "WIDEN"
                      else "S" if r["truth"] == "SHRINK" else "ND" for r in rows)
        assert len(rows) == 24 and grp == {"W": 8, "S": 8, "ND": 8}


def test_m3wa1r_fresh_panel_unique():
    if not executed():
        return
    cap = load(OUT / "m3wa1r_full_panel_capacity.json")
    if cap["full_panel_feasible"]:
        rows = csv_rows(OUT / "m3wa1r_fresh_development_panel.csv")
        assert len({r["state_id"] for r in rows}) == 24


def test_m3wa1r_fresh_panel_pilot_zero():
    v = load(OUT / "m3wa1r_final_verdict.json") \
        if (OUT / "m3wa1r_final_verdict.json").exists() else None
    if v is not None:
        assert v["gradient_pilot_trials"] == 0
    if executed():
        rem = load(OUT / "m3wa1r_remaining_reserve_summary.json")
        assert rem["pilot_exposure"] == 0


def test_m3wa1r_fresh_panel_probe_zero():
    v = load(OUT / "m3wa1r_final_verdict.json") \
        if (OUT / "m3wa1r_final_verdict.json").exists() else None
    if v is not None:
        assert v["finite_action_probe_trials"] == 0
    if executed():
        rem = load(OUT / "m3wa1r_remaining_reserve_summary.json")
        assert rem["pilot_exposure"] == 0


def test_m3wa1r_fresh_panel_hash():
    if not executed():
        assert not (OUT / "m3wa1r_fresh_development_panel_hash.json").exists()
        return
    cap = load(OUT / "m3wa1r_full_panel_capacity.json")
    if not cap["full_panel_feasible"]:
        assert not (OUT / "m3wa1r_fresh_development_panel_hash.json").exists()
        v = load(OUT / "m3wa1r_final_verdict.json")
        assert v["full_fresh_panel"]["hash"] == "NA"
    else:
        import hashlib
        rec = load(OUT / "m3wa1r_fresh_development_panel_hash.json")
        digest = hashlib.sha256(
            (OUT / "m3wa1r_fresh_development_panel.csv").read_bytes()).hexdigest()
        assert rec["panel_sha256"] == digest


def test_m3wa1r_remaining_reserve_protected():
    if not executed():
        return
    rem = csv_rows(OUT / "m3wa1r_remaining_protected_reserve.csv")
    reserve = csv_rows(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")
    assert {r["state_id"] for r in rem} >= {r["state_id"] for r in reserve}
    assert all(r["status"] == "PILOT_PROTECTED_RESERVE" for r in rem
               if r["source_stage"] != "M3-WA1R")


# ------------------------------ boundaries --------------------------------

def _final():
    return load(OUT / "m3wa1r_final_verdict.json")


def test_m3wa1r_gradient_zero():
    if executed():
        assert _final()["gradient_pilot_trials"] == 0


def test_m3wa1r_probe_zero():
    if executed():
        assert _final()["finite_action_probe_trials"] == 0


def test_m3wa1r_threshold_null():
    status = load(OUT / "m3wa1r_wa1_incident_status.json")
    assert status["WA1 primary augmentation result"] == "UNAVAILABLE"


def test_m3wa1r_confirmation_zero():
    if executed():
        assert _final()["protected_confirmation_pilot_trials"] == 0
        assert _final()["s1_confirmation_authorized"] is False


def test_m3wa1r_value_blocked():
    if executed():
        assert _final()["value"] == "BLOCKED"


def test_m3wa1r_rarity_blocked():
    if executed():
        assert _final()["rarity_shift"] == "BLOCKED"


def test_m3wa1r_m3q_blocked():
    if executed():
        assert _final()["m3_q"] == "BLOCKED"
