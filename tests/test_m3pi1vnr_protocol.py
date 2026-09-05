"""M3-PI1VNR path hardening + persistence + protocol + boundary contracts."""
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402
from hyptraj.m3pi1vr0.persistence import safe_fs_id  # noqa: E402
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    FULL_PATH_LIMIT,
    HASH_FIELD,
    RUN_UUID_MAX,
    STATE_SLUG_MAX,
    TEMP_BASENAME_MAX,
    FrozenArtifactError,
    ReplayError,
    assert_not_frozen,
    bounded_slug,
    bounded_temp_basename,
    record_file_hash,
    run_trial_transactional,
    safen_run_uuid,
    scientific_payload_hash,
)

OUT = ROOT / "results/phase_m3pi1vnr/summary"
CFG = ROOT / "configs/phase_m3pi1vnr"
TRIALS = ROOT / "results/phase_m3pi1vnr/trials"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"

CONSUMED = "cf1n_new_000_wa1_w_s2_1p788854382"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


# --------------------------- path hardening --------------------------------

def test_m3pi1vnr_run_uuid_bounded():
    for n in (1, 32, 64, 256, 1024):
        u = safen_run_uuid("u" * n)
        assert len(u) <= RUN_UUID_MAX == 32
    contract = load(OUT / "m3pi1vnr_path_contract.json")
    assert contract["run_uuid_max_length"] == 32


def test_m3pi1vnr_run_uuid_no_state_id():
    long_id = "cf1n_new_005_wa1_w_s2_1p4142135624" * 3
    u = safen_run_uuid(f"pi1vn-{long_id}-0")
    assert long_id not in u and len(u) <= RUN_UUID_MAX
    contract = load(OUT / "m3pi1vnr_path_contract.json")
    assert "hashed into a bounded token" in contract["run_uuid"]


def test_m3pi1vnr_state_slug_bounded():
    for lid in ("cf1n_new_005_wa1_w_s2_1p4142135624__rep0", "a::0",
                "wcf1_new_005_wcf1_s2_1p6__rep7"):
        assert len(bounded_slug(lid)) <= STATE_SLUG_MAX == 64


def test_m3pi1vnr_temp_basename_bounded():
    for lid in ("cf1n_new_005_wa1_w_s2_1p4142135624__rep0", "a::0"):
        b = bounded_temp_basename(bounded_slug(lid), safen_run_uuid(None))
        assert len(b) <= TEMP_BASENAME_MAX   # 76: sized for the 220-char gate


def test_m3pi1vnr_actual_192_paths_preflight():
    rows = csv_rows(OUT / "m3pi1vnr_path_preflight.csv")
    assert len(rows) == 192
    summary = load(OUT / "m3pi1vnr_path_preflight_summary.json")
    assert summary["pass"] == 192 and summary["fail"] == 0
    assert summary["gate"] == "PASS"


def test_m3pi1vnr_all_actual_paths_le220():
    rows = csv_rows(OUT / "m3pi1vnr_path_preflight.csv")
    assert max(int(r["final_path_length"]) for r in rows) <= FULL_PATH_LIMIT == 220
    assert max(int(r["temp_path_length"]) for r in rows) <= FULL_PATH_LIMIT


def test_m3pi1vnr_worst_case_long_state(tmp_path):
    doc = load(OUT / "m3pi1vnr_synthetic_bug_regression.json")
    lens = {w["state_id_length"] for w in doc["worst_case_path_matrix"]}
    assert lens == {40, 80, 160, 320}
    assert doc["worst_case_all_bounded"] is True


def test_m3pi1vnr_overlimit_fails_before_simulator(tmp_path):
    from hyptraj.m3pi1vr0.persistence import PathSafetyError
    invoked = {"sim": False}

    def sim():
        invoked["sim"] = True
        return {"schema": "m3pi1vnr_trial_v1", "state_id": "x"}

    deep = tmp_path
    for i in range(8):
        deep = deep / f"padding_level_{i:02d}_0123456789012345678901"
    final = deep / ("x" * 160) / "rec.json"
    with pytest.raises(Exception) as ei:
        run_trial_transactional("over_limit::rep0", final, sim,
                                ledger_path=tmp_path / "led.jsonl",
                                pre_hash_validator=lambda r: None)
    assert invoked["sim"] is False           # failed BEFORE the simulator
    assert not (tmp_path / "led.jsonl").exists() or all(
        e.get("state_id") != "over_limit::rep0"
        for e in ledger_entries(tmp_path / "led.jsonl"))
    doc = load(OUT / "m3pi1vnr_synthetic_bug_regression.json")
    assert doc["assertions"]["overlimit_fails_before_simulator"] is True


def test_m3pi1vnr_caller_long_uuid_safened_module_level():
    # the module safens any caller-supplied overlong run_uuid automatically
    u = safen_run_uuid("x" * 512)
    assert len(u) <= RUN_UUID_MAX
    contract = load(OUT / "m3pi1vnr_path_contract.json")
    assert "module-level" in contract["enforcement"]


# ------------------------------- persistence -------------------------------

def test_m3pi1vnr_started_before_simulator():
    entries = ledger_entries(TRIALS / "trial_ledger.jsonl")
    first = {}
    ok = True
    for i, e in enumerate(entries):
        rid = e.get("state_id")
        if e.get("status") == "STARTED":
            first.setdefault(rid, i)
        elif e.get("status") == "COMPLETE":
            ok &= rid in first and first[rid] < i
    assert ok and len(first) == 192


def test_m3pi1vnr_non_circular_hash():
    recs = list(TRIALS.glob("*/*.json"))
    assert len(recs) == 192
    for p in recs:
        rec = load(p)
        assert scientific_payload_hash(rec) == rec[HASH_FIELD]


def test_m3pi1vnr_atomic_persistence():
    entries = ledger_entries(TRIALS / "trial_ledger.jsonl")
    complete = [e for e in entries if e.get("status") == "COMPLETE"]
    assert len(complete) == 192
    for e in complete:
        f = TRIALS / bounded_slug(e["panel_state_id"]) / f"rep{e['rep_id']}.json"
        assert f.exists()
        assert record_file_hash(f) == e["record_file_hash"]
        assert not list(f.parent.glob(".*.tmp.*"))


def test_m3pi1vnr_final_hash_verify():
    audit = load(OUT / "m3pi1vnr_persistence_audit.json")
    assert audit["canonical_hashes"] == "PASS" and not audit["problems"]


def test_m3pi1vnr_consumed_invalid_no_replay():
    entries = ledger_entries(TRIALS / "trial_ledger.jsonl")
    assert not any(e.get("status") == "CONSUMED_INVALID" for e in entries)
    seen = {}
    for e in entries:
        seen.setdefault(e.get("state_id"), set()).add(e.get("status"))
    assert all(s == {"STARTED", "COMPLETE"} for s in seen.values())


def test_m3pi1vnr_frozen_overwrite_guard():
    prereg = load(OUT / "m3pi1vnr_prereg_hashes.json")
    for e in prereg["files"]:
        p = ROOT / e["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]
    with pytest.raises(FrozenArtifactError):
        assert_not_frozen(ROOT / prereg["files"][0]["path"], prereg_record=prereg)


def test_m3pi1vnr_synthetic_e2e():
    doc = load(OUT / "m3pi1vnr_synthetic_bug_regression.json")
    assert doc["synthetic_e2e_complete"] is True
    assert doc["assertions"]["overlimit_fails_before_simulator"] is True
    assert doc["payloads"].startswith("mock only")


# --------------------------- scientific protocol ---------------------------

def test_m3pi1vnr_R_exact8():
    assert load(CFG / "m3pi1vnr_gradient_protocol.json")["replicates"] == 8


def test_m3pi1vnr_Bgrad_exact20000():
    assert load(CFG / "m3pi1vnr_gradient_protocol.json")["samples_per_trial"] == 20_000


def test_m3pi1vnr_gradient_sign_rule():
    assert load(CFG / "m3pi1vnr_gradient_protocol.json")["sign_mapping"] == \
        "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK"


def test_m3pi1vnr_base_probe_10000():
    assert load(CFG / "m3pi1vnr_probe_protocol.json")["base_samples"] == 10_000


def test_m3pi1vnr_selected_probe_10000():
    assert load(CFG / "m3pi1vnr_probe_protocol.json")["selected_action_samples"] == 10_000


def test_m3pi1vnr_probe_total_20000():
    assert load(CFG / "m3pi1vnr_probe_protocol.json")["total_probe_samples"] == 20_000


def test_m3pi1vnr_paired_crn20():
    pc = load(CFG / "m3pi1vnr_probe_protocol.json")
    assert pc["batches"] == 20 and pc["paired_crn"] is True


def test_m3pi1vnr_opposite_probe_zero():
    assert load(CFG / "m3pi1vnr_probe_protocol.json")["opposite_action_probe"] == \
        "FORBIDDEN"
    m = load(TRIALS / "trial_manifest.json")
    assert m["opposite_action_probe_samples"] == 0


def test_m3pi1vnr_v1_formula_exact():
    assert load(CFG / "m3pi1vnr_v1_estimator.json")["formula"] == \
        "V1 = (-0.01 - r_hat) / SE(r_hat)"


def test_m3pi1vnr_s1_definition_hash():
    s = load(CFG / "m3pi1vnr_s1_contract.json")
    assert s["source_sha256"] == hashlib.sha256(
        (ROOT / "scripts/run_m3pi1v.py").read_bytes()).hexdigest()


def test_m3pi1vnr_metric_contract_hash():
    m = load(CFG / "m3pi1vnr_metric_contract.json")
    assert m["semantics_sha256"] == hashlib.sha256(
        (ROOT / "scripts/run_m3pi1v.py").read_bytes()).hexdigest()


def test_m3pi1vnr_threshold_contract_hash():
    tc = load(CFG / "m3pi1vnr_threshold_contract.json")
    assert tc["no_invalid_threshold_reuse"] is True


# ----------------------------- gates / boundaries --------------------------

def _final():
    return load(OUT / "m3pi1vnr_final_verdict.json")


def test_m3pi1vnr_wrong_gate_5pct():
    assert load(CFG / "m3pi1vnr_gates.json")["wrong_direction_max"] == 0.05


def test_m3pi1vnr_coverage_gate_75pct():
    assert load(CFG / "m3pi1vnr_gates.json")["coverage_min"] == 0.75


def test_m3pi1vnr_unsafe_gate_20pct():
    assert load(CFG / "m3pi1vnr_gates.json")["unsafe_max"] == 0.20


def test_m3pi1vnr_best_safe_coverage():
    g = load(OUT / "m3pi1vnr_information_gain.json")
    for fam in ("V1", "S1"):
        rows = csv_rows(OUT / f"m3pi1vnr_{fam.lower()}_threshold_frontier.csv")
        compliant = [r for r in rows
                     if r["safety_compliant"] in ("True", True)]
        expect = max((float(r["deployable_coverage"]) for r in compliant),
                     default=0.0)
        assert g[f"{fam}_BEST_SAFE_COVERAGE"] == expect


def test_m3pi1vnr_unique_gain_5pp():
    g = load(OUT / "m3pi1vnr_information_gain.json")
    assert g["gain_ge_5pp"] == (g["coverage_gain"] >= 0.05)
    assert g["unique_information_criterion"] == (
        "YES" if g["V1_FULL_PASS"] and (not g["S1_FULL_PASS"]
                                        or g["coverage_gain"] >= 0.05) else "NO")


def test_m3pi1vnr_verdict_priority():
    v = _final()
    assert v["verdict"] == "PI1VNR-C"
    assert v["direction"]["gate_le_5pct"] == "PASS"
    assert v["V1"]["V1_FULL_PASS"] is False
    g = load(OUT / "m3pi1vnr_information_gain.json")
    assert g["V1_FULL_PASS"] is False


def test_m3pi1vnr_no_confirmation():
    assert _final()["confirmation"]["trials"] == 0
    assert _final()["confirmation"]["authorized"] is False


def test_m3pi1vnr_reserve_unexposed():
    fw = load(OUT / "m3pi1vnr_reserve_firewall_postrun.json")
    assert fw["pilot_exposure"] == 0 and fw["untouched"] is True


def test_m3pi1vnr_value_blocked():
    assert _final()["value"] == "BLOCKED"


def test_m3pi1vnr_rarity_blocked():
    assert _final()["rarity_shift"] == "BLOCKED"


def test_m3pi1vnr_m3q_blocked():
    assert _final()["m3_q"] == "BLOCKED"
