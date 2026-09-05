"""M3-PI1V inherited-direction contracts, post-incident status.

The attempt-2 trial records live under the diagnostic quarantine
(``results/phase_m3pi1v/quarantine_attempt2/trials``) and are verified here
for internal/protocol consistency only; they support no primary claim.
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
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    return P._load_trial_records(rows)


def test_m3pi1v_gradient_protocol_hash():
    rec = load(OUT / "m3pi1v_prereg_hashes.json")
    h = {e["path"]: e["sha256"] for e in rec["files"]}
    assert h["configs/phase_m3pi1v/m3pi1v_gradient_protocol.json"] \
        == sha(CFG / "m3pi1v_gradient_protocol.json")
    proto = load(CFG / "m3pi1v_gradient_protocol.json")
    assert proto["estimator"] == "hyptraj.m3d.adaptation.gradient_decision"
    for t in trial_records():
        assert t["gradient"]["protocol_hash"] == sha(CFG / "m3pi1v_gradient_protocol.json")


def test_m3pi1v_gradient_sign_convention():
    proto = load(CFG / "m3pi1v_gradient_protocol.json")
    assert proto["sign_mapping"] == "g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK"
    for t in trial_records():
        g = t["gradient"]
        expect = "WIDEN" if g["g_hat"] < 0 else "SHRINK"
        assert g["sign"] == expect
        if g["valid"]:
            assert t["selected_action"] == expect


def test_m3pi1v_gradient_invalid_rule():
    proto = load(CFG / "m3pi1v_gradient_protocol.json")
    assert "ABSTAIN" in proto["invalid_rule"]
    for t in trial_records():
        g = t["gradient"]
        valid = (not g["problems"]) and all(
            math.isfinite(g[k])
            for k in ("g_hat", "g_ci_low", "g_ci_high", "ESS_grad")) and g["ESS_grad"] >= 20
        assert g["valid"] == valid
        if not g["valid"]:
            assert t["selected_action"] is None
            assert t["probe"]["executed"] is False


def test_m3pi1v_exact_repetitions_per_state():
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    recs = trial_records()
    by_state = {}
    for t in recs:
        by_state.setdefault(t["state_id"], []).append(t["rep_id"])
    assert len(by_state) == 24
    assert all(sorted(v) == list(range(P.R)) for v in by_state.values())
    assert len(recs) == 24 * P.R


def test_m3pi1v_exact_gradient_budget():
    recs = trial_records()
    assert {t["gradient"]["samples"] for t in recs} == {P.N_GRAD}
    assert P.N_GRAD == 20000
    total = sum(t["gradient"]["samples"] for t in recs)
    assert total == 24 * P.R * P.N_GRAD == 3_840_000
