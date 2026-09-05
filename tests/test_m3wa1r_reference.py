"""M3-WA1R P_ref / reference contracts (taskbook Sec. 47)."""
import csv
import hashlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1r/summary"
REF = ROOT / "results/phase_m3wa1r/reference"
WA1_OUT = ROOT / "results/phase_m3wa1/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3wa1r_pref_config_specific():
    dep = load(OUT / "m3wa1r_pref_dependency_audit.json")
    assert dep["dependency"] == "CONFIG_SPECIFIC"
    assert "direct_full_event_reference" in dep["reverified_from_code"]
    assert dep["allowed_source"] == "results/phase_m3cf1n/pref/<config_id>.json"
    assert dep["new_p_ref_samples"] == 0


def test_m3wa1r_pref_durable_hash_valid():
    dep = load(OUT / "m3wa1r_pref_dependency_audit.json")
    for cid, meta in dep["records"].items():
        p = ROOT / meta["path"]
        assert p.exists()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
        rec = load(p)
        assert rec["config_id"] == cid and rec["sample_count"] == 500_000
        assert rec["event_schema"] == "corrected full-event v2"
        assert meta["durable"] is True and meta["checks_pass"] is True


def test_m3wa1r_reference_budget_500k():
    txt = (OUT / "m3wa1r_prereg_status.txt").read_text(encoding="utf-8")
    assert "samples/arm = 500000" in txt
    assert "expected finite-action samples = 12000000" in txt
    script = (ROOT / "scripts/run_m3wa1r.py").read_text(encoding="utf-8")
    assert "REF_N = 500_000" in script


def test_m3wa1r_reference_three_arms():
    txt = (OUT / "m3wa1r_prereg_status.txt").read_text(encoding="utf-8")
    assert "arms = 3" in txt
    script = (ROOT / "scripts/run_m3wa1r.py").read_text(encoding="utf-8")
    assert 'for name in ("base", "widen", "shrink")' in script


def test_m3wa1r_reference_crn20():
    txt = (OUT / "m3wa1r_prereg_status.txt").read_text(encoding="utf-8")
    assert "batches = 20" in txt
    script = (ROOT / "scripts/run_m3wa1r.py").read_text(encoding="utf-8")
    assert "N_BATCH = 20" in script
    assert "evaluate_reference_arms(" in script


def test_m3wa1r_reference_semantics_v2():
    from hyptraj.m3d2 import experiment as E
    sig = inspect.signature(E.classify_reference_state)
    assert sig.parameters["tau"].default == 0.01
    assert sig.parameters["hold_window"].default == 0.03
    assert sig.parameters["margin_min"].default == 0.05
    assert sig.parameters["min_arm_ess"].default == 20.0
    dep = load(OUT / "m3wa1r_pref_dependency_audit.json")
    assert all(m["semantics"] == "corrected full-event v2" for m in dep["records"].values())


def test_m3wa1r_seed_namespace_new():
    seeds = load(OUT / "m3wa1r_seed_manifest.json")
    assert seeds["namespace"] == "M3-WA1R-REF"
    assert len(seeds["seed_keys"]) == 8
    assert seeds["hash_locked_before_simulator"] is True


def test_m3wa1r_seed_collision_zero():
    seeds = load(OUT / "m3wa1r_seed_manifest.json")
    assert seeds["collision_with_wa1"] == []
    assert seeds["collision_with_all_prior"] == []
    # distinctness within the namespace
    vals = [v[0] for v in seeds["seed_keys"].values()]
    assert len(set(vals)) == 8


def test_m3wa1r_all8_complete():
    rm_path = REF / "reference_manifest.json"
    if not rm_path.exists():
        return                    # pre-run regression: execution not yet authorized
    rm = load(rm_path)
    assert rm["complete"] == 8 and rm["candidates"] == 8
    assert rm["consumed_invalid"] == 0
    entries = [json.loads(l) for l in (REF / "reference_ledger.jsonl")
               .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert sum(1 for e in entries if e.get("status") == "COMPLETE") == 8
    for c in csv_rows(OUT / "m3wa1r_candidate_manifest.csv"):
        p = REF / f"{c['candidate_id']}.json"
        assert p.exists()
        rec = load(p)
        assert rec["truth"] in ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS", "INVALID")
        e_complete = next(e for e in entries if e.get("state_id") == c["candidate_id"]
                          and e.get("status") == "COMPLETE")
        assert (hashlib.sha256(p.read_bytes()).hexdigest()
                == e_complete["record_file_hash"])
