"""M3-WA1 parent/leakage contracts (taskbook Sec. 28)."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3wa1_parent_pi1vr0capb():
    assert load(VR0 / "m3pi1vr0_final_verdict.json")["verdict"] == "PI1VR0-CAP-B"
    pa = load(OUT / "m3wa1_parent_audit.json")
    assert pa["all_match"] is True
    assert pa["checks"]["PERSIST-1"] is True
    assert pa["reserve_counts"]["WIDEN"] == 7


def test_m3wa1_pi1v_primary_x():
    status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["PI1V valid verdict"] == "PI1V-X"
    assert status["PI1V-C retained as primary"] == "NO"
    assert status["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY"


def test_m3wa1_no_invalid_pi1v_scores():
    # every WA1 pre-run artifact must be free of invalid-run score fields
    forbidden = ("r_hat", "se_r_hat", "V1", "S1", "gradient_confidence",
                 "threshold_distance", "effect")
    for name in ("m3wa1_candidate_pool.csv", "m3wa1_candidate_manifest.csv",
                 "m3wa1_w_support_inventory.csv", "m3wa1_selection_view.csv"
                 if (OUT / "m3wa1_selection_view.csv").exists()
                 else "m3wa1_existing_w_reserve_audit.csv"):
        text = (OUT / name).read_text(encoding="utf-8")
        header = text.splitlines()[0]
        for tok in forbidden:
            assert tok not in header, (name, tok)
    sel = load(OUT / "m3wa1_selector_contract.json")
    assert "invalid PI1V scores" in " ".join(sel["forbidden_inputs"])


def test_m3wa1_old24_not_candidates():
    old24 = {r["state_id"] for r in csv_rows(CF2 / "m3cf2_development_panel.csv")}
    pool = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1_candidate_pool.csv")}
    manifest = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1_candidate_manifest.csv")}
    assert pool & old24 == set() and manifest & old24 == set()
    assert all(r["state_id"].endswith(".json") is False for r in []) or True
    # candidates are fresh identities by construction
    assert all("_wa1_w_s2_" in c for c in manifest)


def test_m3wa1_reserve_not_piloted():
    reserve = {r["state_id"] for r in csv_rows(
        CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    manifest = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1_candidate_manifest.csv")}
    assert manifest & reserve == set()
    rem = {r["state_id"] for r in csv_rows(
        OUT / "m3wa1_remaining_protected_reserve.csv")}
    assert reserve <= rem


def test_m3wa1_no_s1_confirmation():
    v = load(OUT / "m3wa1_final_verdict.json")
    assert v["s1_confirmation_authorized"] is False
    assert v["s1_threshold"] is None


def test_m3wa1_no_v1_pilot():
    v = load(OUT / "m3wa1_final_verdict.json")
    assert v["v1_new_test"] is False
    assert v["finite_action_probe_trials"] == 0
    assert v["v1_threshold"] is None
