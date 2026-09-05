"""M3-PI1VR0 fresh-reserve audit contracts (taskbook Sec. 29)."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vr0/summary"
PI1V = ROOT / "results/phase_m3pi1v"
CF2 = ROOT / "results/phase_m3cf2/summary"
UC2R = ROOT / "results/phase_m3uc2r/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3pi1vr0_reserve_exact_exposure_audit():
    rows = csv_rows(OUT / "m3pi1vr0_reserve_exposure_audit.csv")
    reserve = csv_rows(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")
    assert len(rows) == len(reserve) == 70
    assert {r["state_id"] for r in rows} == {r["state_id"] for r in reserve}
    required = {"state_id", "truth", "config_id", "source_stage", "source_region",
                "was_CF2_reserve", "gradient_exposure", "probe_exposure",
                "threshold_replay_exposure", "eligible_fresh_development", "reason"}
    assert required <= set(rows[0])
    assert all(r["was_CF2_reserve"] == "True" for r in rows)
    assert all(r["gradient_exposure"] == "0" and r["probe_exposure"] == "0"
               and r["threshold_replay_exposure"] == "0" for r in rows)
    summary = load(OUT / "m3pi1vr0_reserve_audit_summary.json")
    assert summary["exposures_all_zero"] is True
    assert summary["verified_untouched"] == 70


def test_m3pi1vr0_no_old24_in_fresh_candidates():
    view = {r["state_id"] for r in csv_rows(OUT / "m3pi1vr0_selection_view.csv")}
    old24 = {r["state_id"] for r in csv_rows(CF2 / "m3cf2_development_panel.csv")}
    assert view & old24 == set()
    retired = {r["state_id"] for r in csv_rows(
        OUT / "m3pi1vr0_retired_development_states.csv")}
    assert view & retired == set()


def _touched_trial_states():
    touched = set()
    for q in (PI1V / "quarantine_attempt1", PI1V / "quarantine_attempt2"):
        tdir = q / "trials"
        if tdir.exists():
            touched |= {d.name for d in tdir.iterdir() if d.is_dir()}
    return touched


def test_m3pi1vr0_no_pilot_exposed_candidates():
    view = {r["state_id"] for r in csv_rows(OUT / "m3pi1vr0_selection_view.csv")}
    assert view & _touched_trial_states() == set()


def test_m3pi1vr0_no_probe_exposed_candidates():
    rows = csv_rows(OUT / "m3pi1vr0_reserve_exposure_audit.csv")
    assert all(int(r["probe_exposure"]) == 0 for r in rows)
    assert all(int(r["gradient_exposure"]) == 0 for r in rows)
    view = {r["state_id"] for r in csv_rows(OUT / "m3pi1vr0_selection_view.csv")}
    assert view & _touched_trial_states() == set()


def test_m3pi1vr0_no_uc2r_protected_use():
    view = {r["state_id"] for r in csv_rows(OUT / "m3pi1vr0_selection_view.csv")}
    uc2r_conf = {r["state_id"] for r in csv_rows(
        UC2R / "m3uc2r_reference_states.csv") if r["split"] == "CONFIRMATION"}
    assert view & uc2r_conf == set()
    remaining = {r["state_id"] for r in csv_rows(
        OUT / "m3pi1vr0_remaining_reserve_manifest.csv")}
    assert remaining & uc2r_conf == set()


def test_m3pi1vr0_selection_view_redacted():
    rows = csv_rows(OUT / "m3pi1vr0_selection_view.csv")
    allowed = {"state_id", "truth", "config_id", "physical_family", "s2",
               "source_stage", "source_region", "stable_config_flag",
               "canonical_bank_order"}
    assert set(rows[0]) == allowed
    for forbidden in ("V1", "S1", "r_hat", "SE", "gradient", "M2", "threshold",
                      "margin", "confidence"):
        assert all(forbidden.lower() not in k.lower() for k in rows[0])


def test_m3pi1vr0_invalid_run_scores_absent():
    # the quarantined attempt-2 score tables were never read by any audit step:
    # the redacted view and capacity audit carry no score fields
    cap = load(OUT / "m3pi1vr0_fresh_panel_capacity.json")
    assert "attempt2_influence" in cap
    assert "never read" in cap["attempt2_influence"] or \
        cap["attempt2_influence"].startswith("none")
    view_text = (OUT / "m3pi1vr0_selection_view.csv").read_text(encoding="utf-8")
    for score_token in ("V1", "S1", "r_hat", "se_r_hat"):
        assert score_token not in view_text
