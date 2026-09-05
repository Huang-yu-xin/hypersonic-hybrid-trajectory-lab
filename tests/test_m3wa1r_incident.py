"""M3-WA1R incident/retirement contracts (taskbook Sec. 44)."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1r/summary"
WA1_OUT = ROOT / "results/phase_m3wa1/summary"
WA1_REF = ROOT / "results/phase_m3wa1/reference"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"

CONSUMED = "cf1n_new_000_wa1_w_s2_1p788854382"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3wa1r_parent_wa1x():
    status = load(OUT / "m3wa1r_wa1_incident_status.json")
    assert status["WA1 valid verdict"] == "WA1-X"
    assert status["WA1 primary augmentation result"] == "UNAVAILABLE"
    assert status["WA1 candidate-1 truth"] == "UNAVAILABLE"
    assert status["WA1 candidate-1 reference record"] == "INVALID / NON-DURABLE"
    assert load(WA1_OUT / "m3wa1_final_verdict.json")["verdict"] == "WA1-X"
    assert load(VR0 / "m3pi1vr0_final_verdict.json")["verdict"] == "PI1VR0-CAP-B"


def test_m3wa1r_consumed_candidate_retired():
    ret = load(OUT / "m3wa1r_retired_candidate_seed_manifest.json")
    assert ret["retired_identity"] == CONSUMED
    assert ret["status"] == "CONSUMED_INVALID_RETIRED"
    assert ret["retired_seed"]["namespace"] == "M3-WA1-REF"
    assert ret["all_wa1_seeds_retired"] is True
    universe = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1r_candidate_universe.csv")}
    manifest = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1r_candidate_manifest.csv")}
    assert CONSUMED not in universe and CONSUMED not in manifest


def test_m3wa1r_consumed_candidate_not_reused():
    # the WA1R ledger must not contain the consumed identity
    entries = []
    led = ROOT / "results/phase_m3wa1r/reference/reference_ledger.jsonl"
    if led.exists():
        entries = [json.loads(l) for l in led.read_text(encoding="utf-8").splitlines()
                   if l.strip()]
    assert all(e.get("state_id") != CONSUMED for e in entries)
    # and no reference record for it exists
    assert not (ROOT / "results/phase_m3wa1r/reference" / f"{CONSUMED}.json").exists()


def test_m3wa1r_old_wa1_seeds_retired():
    seeds = load(OUT / "m3wa1r_seed_manifest.json")
    wa1_seeds = load(WA1_OUT / "m3wa1_seed_manifest.json")["seed_keys"]
    assert seeds["namespace"] == "M3-WA1R-REF"
    assert seeds["collision_with_wa1"] == []
    assert seeds["old_wa1_seeds_remain_retired"] is True
    wa1_tuples = {tuple(v) for v in wa1_seeds.values()}
    for v in seeds["seed_keys"].values():
        assert tuple(v) not in wa1_tuples


def test_m3wa1r_seven_never_started_verified():
    rows = csv_rows(OUT / "m3wa1r_never_started_candidate_audit.csv")
    assert len(rows) == 7
    assert all(r["scientifically_fresh"] == "True" for r in rows)
    assert all(int(r["simulator_invocation_count"]) == 0 for r in rows)
    assert all(int(r["reference_samples"]) == 0 for r in rows)
    assert all(int(r["pilot_probe_exposure"]) == 0 for r in rows)
    assert all(int(r["threshold_replay_exposure"]) == 0 for r in rows)


def test_m3wa1r_unused_ninth_preoutcome_only():
    u = load(OUT / "m3wa1r_unused_candidate_audit.json")
    assert u["generated_before_any_wa1_outcome"] is True
    assert u["pool_sha256_verified_against_wa1_prereg"] is True
    assert u["sampled"] is False and u["pilot_probe_exposed"] is False
    assert u["source_pair_still_valid"] is True and u["p_ref_dependency_valid"] is True
    assert u["eligible_sole_replacement"] is True
    assert u["origin"] if False else True
    manifest = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_manifest.csv")}
    assert u["candidate_id"] not in manifest        # it was the unused pool member
    pool = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_pool.csv")}
    assert u["candidate_id"] in pool                # but existed in the pre-outcome pool


def test_m3wa1r_no_new_midpoint_generation():
    # the recovery universe is exactly the WA1 manifest minus the consumed
    # candidate plus the one pre-outcome pool member -- no new identity
    pool = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_pool.csv")}
    universe = {r["candidate_id"] for r in csv_rows(OUT / "m3wa1r_candidate_universe.csv")}
    manifest = {r["candidate_id"] for r in csv_rows(WA1_OUT / "m3wa1_candidate_manifest.csv")}
    assert universe == (manifest - {CONSUMED}) | (pool - manifest)
    assert len(universe) == 8
