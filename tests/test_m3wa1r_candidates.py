"""M3-WA1R candidate-recovery contracts (taskbook Sec. 46)."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1r/summary"
WA1_OUT = ROOT / "results/phase_m3wa1/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"

CONSUMED = "cf1n_new_000_wa1_w_s2_1p788854382"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def manifest():
    return csv_rows(OUT / "m3wa1r_candidate_manifest.csv")


def test_m3wa1r_candidate_universe_only_preoutcome():
    wa1_pool = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_pool.csv")}
    universe = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1r_candidate_universe.csv")}
    assert universe <= wa1_pool                     # every member pre-existed
    origins = Counter(r["origin"] for r in csv_rows(OUT / "m3wa1r_candidate_universe.csv"))
    assert set(origins) <= {"WA1_NEVER_STARTED", "WA1_UNUSED_PREOUTCOME"}


def test_m3wa1r_candidate_exact8():
    assert len(manifest()) == 8
    assert load(OUT / "m3wa1r_candidate_manifest_hash.json")["candidates"] == 8


def test_m3wa1r_candidate_configs_ge4():
    cfg = Counter(c["config_id"] for c in manifest())
    assert len(cfg) >= 4
    assert len(cfg) == load(OUT / "m3wa1r_recovery_diversity_gate.json")["distinct_configs"]


def test_m3wa1r_candidate_max2_per_config():
    # the fixed universe holds 3 candidates in config cf1n_new_003 -- a recorded
    # deviation from the preferred gate that Sec. 17/35 resolve to select-all-8;
    # the PANEL-level max-2/config gate is enforced separately in capacity
    cfg = Counter(c["config_id"] for c in manifest())
    gate = load(OUT / "m3wa1r_recovery_diversity_gate.json")
    assert gate["max_candidates_per_config"] == max(cfg.values())
    assert gate["max_per_config_exceeds_preferred_gate"] is True
    assert gate["pre_b_triggered"] is False


def test_m3wa1r_candidate_manifest_frozen():
    mh = load(OUT / "m3wa1r_candidate_manifest_hash.json")
    digest = hashlib.sha256(
        (OUT / "m3wa1r_candidate_manifest.csv").read_bytes()).hexdigest()
    assert digest == mh["manifest_sha256"]
    assert mh["frozen_before_any_scientific_call"] is True
    assert mh["no_substitutions_after_hash_lock"] is True
    # prereg hashes still verify (no mutation after freeze)
    prereg = load(OUT / "m3wa1r_prereg_hashes.json")
    for e in prereg["files"]:
        p = ROOT / e["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]


def test_m3wa1r_no_invalid_pi1v_scores():
    forbidden = ("r_hat", "se_r_hat", "V1", "S1", "gradient_confidence")
    for name in ("m3wa1r_candidate_universe.csv", "m3wa1r_candidate_manifest.csv"):
        header = (OUT / name).read_text(encoding="utf-8").splitlines()[0]
        for tok in forbidden:
            assert tok not in header, (name, tok)
    sel = load(OUT / "m3wa1r_selector_contract.json")
    text = json.dumps(sel)
    assert "PI1V Attempt-2 scores" in text and "WA1 outcomes" in text


def test_m3wa1r_no_wa1_outcome_selection():
    # the recovery manifest was frozen from pre-outcome identities only; the
    # WA1 candidate-1 outcome (UNAVAILABLE) entered no selection decision
    status = load(OUT / "m3wa1r_wa1_incident_status.json")
    assert status["WA1 candidate-1 truth"] == "UNAVAILABLE"
    sel = load(OUT / "m3wa1r_selector_contract.json")
    assert sel["rule"].startswith("select all 8")
    assert sel["manual_override"] == "FORBIDDEN"
    # manifest membership is fully determined by the pre-outcome WA1 manifest
    # and pool (retire consumed + add unused), independent of any outcome
    wa1_manifest = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_manifest.csv")}
    wa1_pool = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_pool.csv")}
    expect = (wa1_manifest - {CONSUMED}) | (wa1_pool - wa1_manifest)
    assert {c["candidate_id"] for c in manifest()} == expect
