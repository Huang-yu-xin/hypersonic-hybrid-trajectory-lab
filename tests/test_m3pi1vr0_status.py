"""M3-PI1VR0 scientific status contracts (taskbook Sec. 29)."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vr0/summary"
PI1V = ROOT / "results/phase_m3pi1v"
QUAR2 = PI1V / "quarantine_attempt2"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3pi1vr0_pi1v_verdict_x():
    status = load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["PI1V valid verdict"] == "PI1V-X"
    forensics = load(OUT / "m3pi1vr0_incident_forensics.json")
    assert forensics["valid_verdict"] == "PI1V-X"
    final = load(OUT / "m3pi1vr0_final_verdict.json")
    assert final["pi1v_scientific_status"]["PI1V valid verdict"] == "PI1V-X"


def test_m3pi1vr0_pi1vc_not_primary():
    status = load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["PI1V-C retained as primary"] == "NO"
    # the PI1V-C verdict file survives only inside the diagnostic quarantine
    assert not (PI1V / "summary/m3pi1v_final_verdict.json").exists()
    qv = load(QUAR2 / "summary_analysis/m3pi1v_final_verdict.json")
    assert qv["verdict"] == "PI1V-C"          # preserved for provenance
    assert qv["status"] == "COMPLETE"


def test_m3pi1vr0_attempt2_diagnostic_only():
    status = load(OUT / "m3pi1vr0_scientific_status.json") \
        if (OUT / "m3pi1vr0_scientific_status.json").exists() \
        else load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY"
    assert status["primary V1 sufficiency result"] == "UNAVAILABLE"
    assert status["primary S1 comparator result"] == "UNAVAILABLE"
    for marker in (PI1V / "quarantine_attempt1/DIAGNOSTIC_ONLY.txt",
                   QUAR2 / "DIAGNOSTIC_ONLY.txt"):
        assert marker.exists()
    qm = load(OUT / "m3pi1vr0_quarantine_manifest.json")
    assert qm["scientific_use"] == "diagnostic only"


def test_m3pi1vr0_original24_retired():
    rows = csv_rows(OUT / "m3pi1vr0_retired_development_states.csv")
    old24 = csv_rows(ROOT / "results/phase_m3cf2/summary/m3cf2_development_panel.csv")
    assert len(rows) == 24
    assert {r["state_id"] for r in rows} == {r["state_id"] for r in old24}
    assert all(r["status"] == "PILOT_EXPOSED_RETIRED" for r in rows)
    assert all("confirmation" in r["forbidden_use"] for r in rows)


def test_m3pi1vr0_old_pi1v_seeds_retired():
    seeds = load(OUT / "m3pi1vr0_retired_seed_manifest.json")
    assert seeds["retired_namespaces"] == ["M3-PI1V-GRAD", "M3-PI1V-PROBE"]
    assert seeds["gradient_seed_count"] == 192 and seeds["probe_seed_count"] == 192
    assert "never reused" in seeds["retirement_rule"]
    assert set(seeds["used_by_attempts"]) == {"attempt1 (CONSUMED_INVALID)",
                                              "attempt2 (deterministic replay)"}


def test_m3pi1vr0_no_s1_route_from_invalid_data():
    status = load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    assert "authorizing S1 confirmation" in status["forbidden_uses_of_attempt2"]
    final = load(OUT / "m3pi1vr0_final_verdict.json")
    assert final["s1_confirmation_authorized"] is False
    assert final["value"] == final["rarity_shift"] == final["m3_q"] == "BLOCKED"


def test_m3pi1vr0_no_budget_escalation_from_invalid_data():
    status = load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    assert "choosing a higher V1 budget" in status["forbidden_uses_of_attempt2"]
    final = load(OUT / "m3pi1vr0_final_verdict.json")
    assert final["budget_escalation"] == "PREMATURE"
    assert final["v1_new_test"] is False
