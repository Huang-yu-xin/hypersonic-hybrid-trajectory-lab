"""M3-PI1V persistence and boundary contracts, post-incident status.

The authoritative PI1V verdict is PI1V-X.  Attempt-1 and attempt-2 artifacts
live in the diagnostic quarantine; the pre-pilot preregistration artifacts in
``results/phase_m3pi1v/summary`` remain hash-locked and verified.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1v/summary"
CFG = ROOT / "configs/phase_m3pi1v"
QTRIALS = ROOT / "results/phase_m3pi1v/quarantine_attempt2/trials"
QSUM = ROOT / "results/phase_m3pi1v/quarantine_attempt2/summary_analysis"
QUAR1 = ROOT / "results/phase_m3pi1v/quarantine_attempt1"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"

REQUIRED_PREREG_SUMMARY = [
    "m3pi1v_source_manifest.json", "m3pi1v_parent_panel_audit.json",
    "m3pi1v_reserve_firewall_audit.json", "m3pi1v_inherited_protocol_audit.json",
    "m3pi1v_pilot_contract.json", "m3pi1v_v1_estimator_contract.json",
    "m3pi1v_metric_contract.json", "m3pi1v_threshold_contract.json",
    "m3pi1v_seed_manifest.json", "m3pi1v_persistence_contract.json",
    "m3pi1v_prereg_hashes.json", "m3pi1v_sample_accounting_prereg.json",
    "m3pi1v_persistence_incident_audit.json",
]

REQUIRED_QUARANTINED_ANALYSIS = [
    "m3pi1v_direction_sanity.json", "m3pi1v_v1_trials.csv", "m3pi1v_s1_trials.csv",
    "m3pi1v_v1_threshold_frontier.csv", "m3pi1v_s1_threshold_frontier.csv",
    "m3pi1v_selected_thresholds.json", "m3pi1v_primary_metrics.json",
    "m3pi1v_comparative_information_gain.json",
    "m3pi1v_state_level_policy_audit.csv", "m3pi1v_loso_diagnostic.csv",
    "m3pi1v_loco_diagnostic.csv", "m3pi1v_truth_stratified_metrics.json",
    "m3pi1v_persistence_audit.json", "m3pi1v_final_verdict.json",
]

REQUIRED_CONFIGS = [
    "m3pi1v_panel.json", "m3pi1v_gradient_protocol.json", "m3pi1v_probe_protocol.json",
    "m3pi1v_v1_estimator.json", "m3pi1v_metric_contract.json",
    "m3pi1v_threshold_contract.json", "m3pi1v_seeds.json", "m3pi1v_persistence.json",
    "m3pi1v_gates.json",
]

REQUIRED_TRIAL_FIELDS = {
    "schema", "state_id", "rep_id", "config_id", "s2", "truth", "truth_group",
    "gradient", "selected_action", "probe", "V1", "S1", "sample_counts",
    "source_hashes", "record_sha256",
}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def ledger(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def status():
    return load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")


def test_m3pi1v_ledger_started_before_trial():
    entries = ledger(QTRIALS / "trial_ledger.jsonl")
    first = {}
    ok = True
    for i, e in enumerate(entries):
        rid = e.get("state_id")
        if e.get("status") == "STARTED":
            first.setdefault(rid, i)
        elif e.get("status") == "COMPLETE":
            ok &= rid in first and first[rid] < i
    assert ok and len(first) == 192
    # the attempt-1 defect (STARTED after sampling) is documented in the
    # incident audit and repaired by the PI1VR0 persistence contract
    inc = load(OUT / "m3pi1v_persistence_incident_audit.json")
    assert any("BEFORE" in f or "before" in f for f in inc["fix"])
    contract = load(VR0 / "m3pi1vr0_persistence_contract.json")
    assert contract["mandatory_order"][0].startswith("1. validate filesystem-safe")
    assert contract["mandatory_order"][1] == "2. durable STARTED ledger entry"
    assert contract["mandatory_order"][2] == "3. invoke scientific simulator"


def test_m3pi1v_atomic_persistence():
    entries = ledger(QTRIALS / "trial_ledger.jsonl")
    complete = [e for e in entries if e.get("status") == "COMPLETE"]
    assert len(complete) == 192
    for e in complete:
        f = QTRIALS / e["panel_state_id"] / f"rep{e['rep_id']}.json"
        assert f.exists()
        assert hashlib.sha256(f.read_bytes()).hexdigest() == e["final_sha256"]
        assert not list(f.parent.glob(f".{e['state_id']}.json.tmp.*"))


def test_m3pi1v_consumed_invalid_policy():
    # authoritative accounting: attempt 1 = 192 CONSUMED_INVALID, 0 COMPLETE
    q1 = Counter(e.get("status") for e in ledger(QUAR1 / "trial_ledger.jsonl"))
    assert q1["STARTED"] == 192 and q1["CONSUMED_INVALID"] == 192
    assert q1["COMPLETE"] == 0
    # attempt 2 records are durable but carry no primary scientific authority
    audit = load(QSUM / "m3pi1v_persistence_audit.json")
    assert audit["canonical_hashes"] == "PASS"
    assert status()["PI1V valid verdict"] == "PI1V-X"


def test_m3pi1v_no_consumed_rerun():
    entries = ledger(QTRIALS / "trial_ledger.jsonl")
    seen = {}
    for e in entries:
        seen.setdefault(e.get("state_id"), set()).add(e.get("status"))
    assert all(s == {"STARTED", "COMPLETE"} for s in seen.values()) and len(seen) == 192
    # attempt-1 identities were quarantined, never rewritten in place
    q1_ids = {e.get("state_id") for e in ledger(QUAR1 / "trial_ledger.jsonl")}
    assert len(q1_ids) == 192
    assert status()["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY"


def test_m3pi1v_no_reserve_pilot():
    reserve = {r["state_id"] for r in csv_rows(
        CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    touched = set()
    for q in (QUAR1, QTRIALS.parent):
        tdir = q / "trials"
        if tdir.exists():
            touched |= {d.name for d in tdir.iterdir() if d.is_dir()}
    assert touched & reserve == set()


def test_m3pi1v_no_confirmation():
    assert status()["primary V1 sufficiency result"] == "UNAVAILABLE"
    assert not (VR0 / "m3pi1vn_confirmation_trials.csv").exists()
    quarantined = load(QSUM / "m3pi1v_final_verdict.json")
    assert quarantined["confirmation"]["confirmation_trials"] == 0
    assert quarantined["protected_confirmation_authorized"] is False


def test_m3pi1v_value_blocked():
    assert load(VR0 / "m3pi1vr0_final_verdict.json")["value"] == "BLOCKED"


def test_m3pi1v_rarity_blocked():
    assert load(VR0 / "m3pi1vr0_final_verdict.json")["rarity_shift"] == "BLOCKED"


def test_m3pi1v_m3q_blocked():
    assert load(VR0 / "m3pi1vr0_final_verdict.json")["m3_q"] == "BLOCKED"


def test_m3pi1v_output_schema():
    for n in REQUIRED_PREREG_SUMMARY:
        assert (OUT / n).exists(), n
    for n in REQUIRED_QUARANTINED_ANALYSIS:
        assert (QSUM / n).exists(), n
    for n in REQUIRED_CONFIGS:
        assert (CFG / n).exists(), n
    for n in ("M3_PI1V_Task.md", "M3_PI1V_Parent_CF2_Audit.md",
              "M3_PI1V_Inherited_Protocol_Audit.md", "M3_PI1V_Pregistration.md",
              "M3_PI1V_Human_Approval.md", "M3_PI1V_Pilot_Execution_Audit.md",
              "M3_PI1V_V1_Analysis.md", "M3_PI1V_S1_Comparator.md",
              "M3_PI1V_Robustness_Diagnostics.md", "M3_PI1V_Reserve_Firewall_Audit.md",
              "M3_PI1V_Final_Report.md"):
        assert (ROOT / "docs/phase_m3pi1v" / n).exists(), n
    figures = list((ROOT / "results/phase_m3pi1v/quarantine_attempt2/figures")
                   .glob("PI1V-*.png"))
    assert len(figures) >= 9
    # prereg hash verification (no drift in the frozen pre-pilot artifacts)
    rec = load(OUT / "m3pi1v_prereg_hashes.json")
    for e in rec["files"]:
        p = ROOT / e["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"], e["path"]
    # quarantined trial record schema
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    for r in rows:
        for rep in range(8):
            t = load(QTRIALS / r["state_id"] / f"rep{rep}.json")
            assert REQUIRED_TRIAL_FIELDS <= set(t)
            assert t["schema"] == "m3pi1v_trial_v1"
            assert t["truth"] == r["truth"]
            body = {k: v for k, v in t.items() if k != "record_sha256"}
            digest = hashlib.sha256(
                json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
            assert digest == t["record_sha256"]
