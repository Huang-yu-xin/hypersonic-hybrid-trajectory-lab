"""M3-CF1N recovery-lineage and boundary contracts (taskbook §42)."""
import json
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "phase_m3cf1n"
OUT = RES / "summary"
CFG = ROOT / "configs" / "phase_m3cf1n"
DOC = ROOT / "docs" / "phase_m3cf1n"
CF1_OUT = ROOT / "results" / "phase_m3cf1" / "summary"
CF1R0_OUT = ROOT / "results" / "phase_m3cf1r0" / "summary"
CF1R0_REPL = ROOT / "results" / "phase_m3cf1r0" / "replacement"
CF0_OUT = ROOT / "results" / "phase_m3cf0" / "summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    import csv

    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


# --------------------------------------------------------------------------
# recovery lineage (§42 lineage list)
# --------------------------------------------------------------------------

def test_m3cf1n_parent_cf1r0a():
    v = load(CF1R0_OUT / "m3cf1r0_final_verdict.json")
    g = load(CF1R0_OUT / "m3cf1r0_persistence_gate.json")
    assert v["verdict"] == "CF1R0-A"
    assert g["gate"] == "M3CF1R0-PERSIST-1"
    assert g["pass"] is True
    assert g["full_regression"] == "PASS"


def test_m3cf1n_cf1_stays_invalid():
    v = load(CF1_OUT / "m3cf1_final_verdict.json")
    assert v["verdict"] == "CF1-X"
    assert v["status"] == "INVALID"
    assert v["rerun_authorized"] is False
    assert load(OUT / "m3cf1n_source_manifest.json")["parent_audit"]["cf1_verdict"] == "CF1-X"


def test_m3cf1n_no_cf1_config_reuse():
    m = load(OUT / "m3cf1n_config_manifest.json")
    assert m["CF1_config_reuse"] == []
    assert m["old_family_collision"] == []
    cf1_ids = set(load(CF1_OUT / "m3cf1_new_config_manifest.json")["config_ids"])
    assert not (set(m["config_ids"]) & cf1_ids)


def test_m3cf1n_no_cf1_state_reuse():
    a = load(OUT / "m3cf1n_disjointness_audit.json")
    assert a["state_collision"] == 0
    states = csv_rows(OUT / "m3cf1n_discovery_states.csv")
    new_ids = {r["state_id"] for r in states}
    cf1_ids = {r["state_id"] for r in csv_rows(CF1_OUT / "m3cf1_discovery_states.csv")}
    cf1_ids |= {r["state_id"] for r in csv_rows(CF1_OUT / "m3cf1_confirmation_states.csv")}
    assert not (new_ids & cf1_ids)
    assert all("_cf1n_" in sid for sid in new_ids)


def test_m3cf1n_no_cf1_seed_reuse():
    a = load(OUT / "m3cf1n_disjointness_audit.json")
    assert a["discovery_seed_collision"] == 0
    assert a["confirmation_seed_collision"] == 0
    assert a["p_ref_seed_collision"] == 0


def test_m3cf1n_cf1_outcomes_not_inputs():
    assert load(OUT / "m3cf1n_prereg_hashes.json")["outcomes"] == "NONE"
    att = load(CF1R0_REPL / "m3cf1r0_replacement_prereg_hashes.json")[
        "outcome_independence_attestation"
    ]
    assert att["cf1_outcome_labels_used_in_selection"] is False
    assert load(OUT / "m3cf1n_source_manifest.json")["parent_audit"][
        "cf1_outcomes_used_in_replacement_selection"
    ] is False


def test_m3cf1n_exact8_replacement_configs():
    m = load(OUT / "m3cf1n_config_manifest.json")
    assert m["count"] == 8
    assert m["config_ids"] == [f"cf1n_new_{i:03d}" for i in range(8)]
    assert m["legal_domain_status"] == "valid"


def test_m3cf1n_replacement_hash_match():
    m = load(OUT / "m3cf1n_config_manifest.json")
    assert m["source_sha256"] == sha(CF1R0_REPL / "m3cf1r0_replacement_configs.csv")
    rows = {r["config_id"]: r for r in csv_rows(CF1R0_REPL / "m3cf1r0_replacement_configs.csv")}
    states = csv_rows(OUT / "m3cf1n_discovery_states.csv")
    for r in states:
        src = rows[r["config_id"]]
        for axis in ("theta_1", "theta_2", "theta_3", "theta_4", "h_1", "h_2", "h_3", "h_4"):
            assert abs(float(r[axis]) - float(src[axis])) < 1e-12


def test_m3cf1n_grid_hash_matches_cf0():
    g = load(OUT / "m3cf1n_common_s2_grid.json")
    assert g["count"] == 9
    assert g["values"] == [1.25, 1.6, 2.0, 2.5, 3.2, 4.0, 5.0, 6.4, 8.0]
    assert g["source_sha256"] == sha(CF0_OUT / "m3cf0_future_s2_grid.json")
    assert g["hash_matches_cf0"] is True


# --------------------------------------------------------------------------
# boundaries (§42 boundaries list)
# --------------------------------------------------------------------------

def _invariants():
    merged = load(OUT / "m3cf1n_protected_confirmation_audit.json")
    return merged


def test_m3cf1n_gradient_pilot_zero():
    a = _invariants()
    assert a["gradient_pilot"] == 0


def test_m3cf1n_v1_probe_zero():
    a = _invariants()
    assert a["finite_action_probe"] == 0
    assert a["v1_tested"] is False


def test_m3cf1n_threshold_null():
    assert _invariants()["threshold"] is None


def test_m3cf1n_protected_confirmation_zero():
    a = _invariants()
    assert a["protected_confirmation_pilot"] == 0
    assert a["protected_confirmation_pilot_trials"] == 0


def test_m3cf1n_value_blocked():
    assert _invariants()["value"] == "BLOCKED"


def test_m3cf1n_rarity_blocked():
    assert _invariants()["rarity_shift"] == "BLOCKED"


def test_m3cf1n_m3q_blocked():
    assert _invariants()["m3_q"] == "BLOCKED"


def test_m3cf1n_prereg_stop_report_locked():
    """The CF1R0-added provenance/persistence gate must be explicitly frozen
    in the pre-simulator STOP report (taskbook §44 + CF1R0 layer)."""
    r = load(OUT / "m3cf1n_prereg_stop_report.json")
    assert r["status"] == "STOPPED_AWAITING_HUMAN_APPROVAL"
    assert r["reverified"] is True
    assert r["CF1_RETIREMENT"] == {
        "CF1 configs reused": 0,
        "CF1 states reused": 0,
        "CF1 seeds reused": 0,
        "CF1 outcomes used": "NO",
        "evidence": r["CF1_RETIREMENT"]["evidence"],
    }
    assert r["REPLACEMENT"]["configs"] == [f"cf1n_new_{i:03d}" for i in range(8)]
    assert r["REPLACEMENT"]["hash matches CF1R0"] == "YES"
    assert r["GRID"]["hash matches CF0"] == "YES" and r["GRID"]["count"] == 9
    d = r["DISJOINTNESS"]
    assert d["state collision"] == 0
    assert d["P_ref seed collision"] == 0
    assert d["discovery seed collision"] == 0
    assert d["confirmation seed collision"] == 0
    assert r["P_REF"]["new config-specific streams"] == 8
    assert r["P_REF"]["namespace"] == "M3-CF1N-PREF"
    assert r["P_REF"]["budget_per_config"] == 500_000
    seeds = r["SEEDS"]
    for ns in ("M3-CF1N-PREF", "M3-CF1N-DISCOVERY", "M3-CF1N-CONFIRM"):
        assert seeds[ns]["hash_locked"] is True
    p = r["PERSISTENCE"]
    for flag in ("write-ahead ledger", "temp + fsync", "schema validation", "sha256",
                 "atomic rename", "directory fsync", "final hash verification",
                 "COMPLETE only after durable record"):
        assert p[flag] is True, flag
    assert p["consumed-invalid rerun"] == "FORBIDDEN"
    assert r["PROTECTED CONFIRMATION"]["pilot trials"] == 0
    assert r["V1"] == {"not tested": True, "threshold": None}
    assert r["VALUE / RARITY / M3-Q"] == {"VALUE": "BLOCKED", "RARITY": "BLOCKED", "M3-Q": "BLOCKED"}
    # the report itself is hash-locked into the run manifest
    manifest = load(RES / "run_manifest.json")
    assert manifest["stop_report_sha256"] == sha(OUT / "m3cf1n_prereg_stop_report.json")


def test_m3cf1n_output_schema():
    required_summary = [
        "m3cf1n_source_manifest.json",
        "m3cf1n_config_manifest.json",
        "m3cf1n_common_s2_grid.json",
        "m3cf1n_discovery_states.csv",
        "m3cf1n_disjointness_audit.json",
        "m3cf1n_persistence_contract.json",
        "m3cf1n_pref_protocol.json",
        "m3cf1n_pref_seeds.json",
        "m3cf1n_discovery_protocol.json",
        "m3cf1n_discovery_seeds.json",
        "m3cf1n_confirmation_protocol.json",
        "m3cf1n_confirmation_seeds.json",
        "m3cf1n_gates.json",
        "m3cf1n_prereg_hashes.json",
        "m3cf1n_protected_confirmation_audit.json",
    ]
    assert all((OUT / n).exists() for n in required_summary)
    required_cfg = [
        "m3cf1n_configs.json",
        "m3cf1n_s2_grid.json",
        "m3cf1n_persistence.json",
        "m3cf1n_pref_protocol.json",
        "m3cf1n_pref_seeds.json",
        "m3cf1n_discovery_protocol.json",
        "m3cf1n_discovery_seeds.json",
        "m3cf1n_confirmation_protocol.json",
        "m3cf1n_confirmation_seeds.json",
        "m3cf1n_stability_rule.json",
        "m3cf1n_gates.json",
    ]
    assert all((CFG / n).exists() for n in required_cfg)
    required_docs = [
        "M3_CF1N_Task.md",
        "M3_CF1N_Parent_Recovery_Audit.md",
        "M3_CF1N_Persistence_Contract.md",
        "M3_CF1N_Pregistration.md",
        "M3_CF1N_Human_Discovery_Approval.md",
        "M3_CF1N_Pref_Audit.md",
        "M3_CF1N_Discovery_Audit.md",
        "M3_CF1N_Confirmation_Eligibility.md",
        "M3_CF1N_Human_Confirmation_Approval.md",
        "M3_CF1N_Confirmation_Audit.md",
        "M3_CF1N_Final_Report.md",
    ]
    assert all((DOC / n).exists() for n in required_docs)
    # every preregistered artifact hash must still match
    for entry in load(OUT / "m3cf1n_prereg_hashes.json")["files"]:
        assert sha(ROOT / entry["path"]) == entry["sha256"], entry["path"]
