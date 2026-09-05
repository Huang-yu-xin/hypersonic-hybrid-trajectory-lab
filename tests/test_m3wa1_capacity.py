"""M3-WA1 capacity contracts (taskbook Sec. 28) -- WA1-X state of record."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3wa1_combined_w_pool():
    rows = csv_rows(OUT / "m3wa1_combined_fresh_w_pool.csv")
    assert len(rows) == 7                     # no augmentation reached a label
    retired = {r["state_id"] for r in csv_rows(
        ROOT / "results/phase_m3pi1vr0/summary/m3pi1vr0_retired_development_states.csv")}
    assert not any(r["state_id"] in retired for r in rows)


def test_m3wa1_w_exact8_feasibility():
    f = load(OUT / "m3wa1_w_feasibility.json")
    assert f["old_untouched_w"] == 7 and f["new_w"] == 0
    assert f["exact_8_selectable"] is False


def test_m3wa1_w_configs_ge6():
    f = load(OUT / "m3wa1_w_feasibility.json")
    assert f["distinct_configs"] == 4
    assert f["configs_ge_6"] is False


def test_m3wa1_w_max2_per_config():
    f = load(OUT / "m3wa1_w_feasibility.json")
    pool_counts = Counter(s["config_id"] for s in
                          csv_rows(OUT / "m3wa1_combined_fresh_w_pool.csv"))
    assert f["config_counts"] == dict(pool_counts)
    # the raw pool violates max2/config (cf1n_new_003 holds 3) -- exactly why
    # the PI1VR0 capacity audit failed and WA1 was chartered
    assert f["max2_per_config"] == (max(pool_counts.values()) <= 2)


def test_m3wa1_full_panel_8w8s8nd():
    cap = load(OUT / "m3wa1_full_panel_capacity.json")
    assert cap["full_panel_feasible"] is False
    assert cap["W"] == "NA" and cap["S"] == "NA" and cap["ND"] == "NA"
    assert not (OUT / "m3wa1_fresh_development_panel.csv").exists()


def test_m3wa1_fresh_panel_unique():
    assert not (OUT / "m3wa1_fresh_development_panel.csv").exists()
    assert not (OUT / "m3wa1_fresh_development_panel_hash.json").exists()


def test_m3wa1_fresh_panel_pilot_zero():
    rem = csv_rows(OUT / "m3wa1_remaining_protected_reserve.csv")
    summary = load(OUT / "m3wa1_remaining_reserve_summary.json")
    assert summary["pilot_exposure"] == 0
    assert len(rem) == 70


def test_m3wa1_fresh_panel_probe_zero():
    summary = load(OUT / "m3wa1_remaining_reserve_summary.json")
    assert summary["pilot_exposure"] == 0
    v = load(OUT / "m3wa1_final_verdict.json")
    assert v["finite_action_probe_trials"] == 0


def test_m3wa1_fresh_panel_hash():
    assert not (OUT / "m3wa1_fresh_development_panel_hash.json").exists()
    # the final verdict records the NA hash explicitly
    v = load(OUT / "m3wa1_final_verdict.json")
    assert v["full_fresh_panel"]["feasible"] is False
    assert v["full_fresh_panel"]["hash"] == "NA"


def test_m3wa1_remaining_reserve_protected():
    rem = csv_rows(OUT / "m3wa1_remaining_protected_reserve.csv")
    reserve = csv_rows(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")
    assert {r["state_id"] for r in rem} == {r["state_id"] for r in reserve}
    assert all(r["status"] == "PILOT_PROTECTED_RESERVE" for r in rem)
