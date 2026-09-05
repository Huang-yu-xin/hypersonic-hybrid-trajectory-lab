"""M3-PI1V V1/S1 score contracts, post-incident status.

Verified against the quarantined attempt-2 diagnostic record.  These tests
pin the exact inherited formulas; they support no primary scientific claim
(the authoritative PI1V verdict is PI1V-X; attempt-2 results are
DIAGNOSTIC_ONLY per m3pi1vr0_pi1v_scientific_status.json).
"""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1v as P  # noqa: E402

OUT = ROOT / "results/phase_m3pi1v/summary"
QSUM = ROOT / "results/phase_m3pi1v/quarantine_attempt2/summary_analysis"
P.TRIALS = ROOT / "results/phase_m3pi1v/quarantine_attempt2/trials"
CFG = ROOT / "configs/phase_m3pi1v"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def trial_records():
    return P._load_trial_records(csv_rows(CF2 / "m3cf2_development_panel.csv"))


def test_m3pi1v_rhat_definition():
    for t in trial_records():
        pr = t["probe"]
        if pr["executed"] and pr["r_hat"] is not None:
            expect = pr["m2_action"] / pr["m2_base"] - 1
            assert pr["r_hat"] == expect
            # batch-mean recomputation (numpy pairwise sum vs math.fsum) agrees
            # to floating-point tolerance
            batch_r = (sum(pr["batch_m2_action"]) / len(pr["batch_m2_action"])) \
                / (sum(pr["batch_m2_base"]) / len(pr["batch_m2_base"])) - 1
            assert math.isclose(pr["r_hat"], batch_r, rel_tol=1e-12, abs_tol=1e-15)


def test_m3pi1v_margin_minus_one_percent():
    contract = load(CFG / "m3pi1v_v1_estimator.json")
    assert contract["improvement_margin"] == -0.01
    assert P.MARGIN == -0.01
    for t in trial_records():
        if t["V1"] is not None:
            assert t["V1"] == (-0.01 - t["probe"]["r_hat"]) / t["probe"]["se_r_hat"]


def test_m3pi1v_v1_definition():
    contract = load(CFG / "m3pi1v_v1_estimator.json")
    assert contract["formula"] == "V1 = (-0.01 - r_hat) / SE(r_hat)"
    for t in trial_records():
        v1 = P.v1_score(t["probe"].get("r_hat"), t["probe"].get("se_r_hat")) \
            if t["gradient"]["valid"] and t["probe"].get("valid") else None
        assert t["V1"] == v1
        if t["V1"] is not None:
            assert t["V1"] == (P.MARGIN - t["probe"]["r_hat"]) / t["probe"]["se_r_hat"]


def test_m3pi1v_se_estimator_hash():
    inh = load(OUT / "m3pi1v_inherited_protocol_audit.json")
    contract = load(OUT / "m3pi1v_v1_estimator_contract.json")
    assert contract["se_estimator"] == \
        "std(batch r, ddof=1)/sqrt(20) over paired CRN batches"
    assert inh["v1_se_estimator"]["source_sha256"] == \
        sha(ROOT / inh["v1_se_estimator"]["source"])
    rec = load(OUT / "m3pi1v_prereg_hashes.json")
    h = {e["path"]: e["sha256"] for e in rec["files"]}
    assert h["results/phase_m3pi1v/summary/m3pi1v_v1_estimator_contract.json"] \
        == sha(OUT / "m3pi1v_v1_estimator_contract.json")


def test_m3pi1v_invalid_probe_abstains():
    rows = [{"truth": "WIDEN", "gradient_valid": True, "probe_valid": False,
             "V1": 100.0, "S1": 10.0, "selected_action": "WIDEN"},
            {"truth": "SHRINK", "gradient_valid": True, "probe_valid": False,
             "V1": None, "S1": 10.0, "selected_action": "SHRINK"},
            {"truth": "HOLD", "gradient_valid": False, "probe_valid": False,
             "V1": None, "S1": None, "selected_action": None}]
    for t in (-1e9, 0.0, 1e9):
        assert all(P.policy_action(r, "V1", t) == "ABSTAIN" for r in rows)


def test_m3pi1v_v1_never_changes_direction():
    for t in trial_records():
        if t["gradient"]["valid"]:
            assert t["selected_action"] == t["gradient"]["sign"]
    v1_rows = list(csv_rows(QSUM / "m3pi1v_v1_trials.csv"))
    for r in v1_rows:
        if r["selected_action"]:
            assert r["selected_action"] in ("WIDEN", "SHRINK")


def test_m3pi1v_s1_inherited_exact():
    z = 1.959963984540054
    for t in trial_records():
        g = t["gradient"]
        if g["valid"]:
            se = (g["g_ci_high"] - g["g_ci_low"]) / (2 * z)
            expect = abs(g["g_hat"]) / se if se > 0 else None
            assert t["S1"] == expect
        else:
            assert t["S1"] is None


def test_m3pi1v_s1_same_gradient_data():
    v1 = {(r["state_id"], r["rep_id"]): r
          for r in csv_rows(QSUM / "m3pi1v_v1_trials.csv")}
    s1 = {(r["state_id"], r["rep_id"]): r
          for r in csv_rows(QSUM / "m3pi1v_s1_trials.csv")}
    assert set(v1) == set(s1) and len(v1) == 192
    for k in v1:
        assert v1[k]["gradient_seed"] == s1[k]["gradient_seed"]
        assert v1[k]["truth"] == s1[k]["truth"]
        assert v1[k]["selected_action"] == s1[k]["selected_action"]


def test_m3pi1v_s1_no_probe_information():
    z = 1.959963984540054
    for t in trial_records():
        g = t["gradient"]
        if not g["valid"]:
            assert t["S1"] is None
            continue
        se = (g["g_ci_high"] - g["g_ci_low"]) / (2 * z)
        recomputed = abs(g["g_hat"]) / se if se > 0 else None
        assert t["S1"] == recomputed
        if t["probe"].get("executed") and not t["probe"]["valid"]:
            assert t["S1"] is not None and t["V1"] is None
