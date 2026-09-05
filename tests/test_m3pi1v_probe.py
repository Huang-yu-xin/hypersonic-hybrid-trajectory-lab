"""M3-PI1V finite-action probe contracts, post-incident status.

Attempt-2 records (diagnostic quarantine) still prove the probe protocol was
implemented exactly as preregistered: BASE + gradient-selected action only,
paired CRN, single fixed budget.  No primary claim is supported.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1v as P  # noqa: E402

OUT = ROOT / "results/phase_m3pi1v/summary"
QTRIALS = ROOT / "results/phase_m3pi1v/quarantine_attempt2/trials"
P.TRIALS = QTRIALS
CFG = ROOT / "configs/phase_m3pi1v"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def trial_records():
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    return P._load_trial_records(rows)


def test_m3pi1v_probe_selected_action_only():
    proto = load(CFG / "m3pi1v_probe_protocol.json")
    assert proto["base_samples"] == P.N_PROBE
    assert proto["selected_arm_samples"] == P.N_PROBE
    assert proto["invalid_gradient"] == "ABSTAIN_NO_PROBE"
    for t in trial_records():
        if t["gradient"]["valid"]:
            assert t["probe"]["executed"] is True
            assert t["probe"]["samples_base"] == P.N_PROBE
            assert t["probe"]["samples_action"] == P.N_PROBE


def test_m3pi1v_no_opposite_action_probe():
    proto = load(CFG / "m3pi1v_probe_protocol.json")
    assert proto["opposite_action_probe"] == "FORBIDDEN"
    for t in trial_records():
        assert t["probe"]["opposite_action_probe_samples"] == 0
    manifest = load(QTRIALS / "trial_manifest.json")
    assert manifest["opposite_action_probe_samples"] == 0


def test_m3pi1v_probe_budget_le_gradient_budget():
    assert 2 * P.N_PROBE <= P.N_GRAD
    proto = load(CFG / "m3pi1v_probe_protocol.json")
    assert proto["extra_samples_per_trial"] == 2 * P.N_PROBE <= P.N_GRAD


def test_m3pi1v_total_budget_le_2x():
    manifest = load(QTRIALS / "trial_manifest.json")
    acc = manifest["sample_accounting"]
    assert acc["total_samples"] <= acc["max_total_online_samples"]
    assert acc["total_samples"] == acc["gradient_samples"] + acc["base_probe_samples"] \
        + acc["selected_action_probe_samples"]
    assert acc["total_le_2x"] is True
    assert acc["total_samples"] == 7_680_000


def test_m3pi1v_probe_paired_crn():
    proto = load(CFG / "m3pi1v_probe_protocol.json")
    assert proto["paired_crn"] is True
    for t in trial_records():
        pr = t["probe"]
        if pr["executed"]:
            assert pr["paired_batches"] == P.N_BATCH == 20
            assert len(pr["batch_m2_base"]) == P.N_BATCH
            assert len(pr["batch_m2_action"]) == P.N_BATCH
    # functional CRN check on a real (retired) panel state: same seed
    # reproduces the same paired realizations across both arms
    rows = csv_rows(CF2 / "m3cf2_development_panel.csv")
    st = P.state_for(rows[0])
    a = P.paired_probe(st, "WIDEN", 987654321)
    b = P.paired_probe(st, "WIDEN", 987654321)
    assert a["batch_m2_base"] == b["batch_m2_base"]
    assert a["batch_m2_action"] == b["batch_m2_action"]
    assert a["r_hat"] == b["r_hat"]


def test_m3pi1v_single_budget_level():
    for t in trial_records():
        pr = t["probe"]
        assert pr["samples_base"] in (0, P.N_PROBE)
        assert pr["samples_action"] in (0, P.N_PROBE)
        if pr["executed"]:
            assert (pr["samples_base"], pr["samples_action"]) == (P.N_PROBE, P.N_PROBE)


def test_m3pi1v_no_adaptive_probe():
    manifest = load(QTRIALS / "trial_manifest.json")
    acc = manifest["sample_accounting"]
    recs = trial_records()
    n_exec = sum(1 for t in recs if t["probe"]["executed"])
    assert acc["base_probe_samples"] == n_exec * P.N_PROBE
    assert acc["selected_action_probe_samples"] == n_exec * P.N_PROBE
    assert acc["invalid_gradient_saved_probe_samples"] == (len(recs) - n_exec) * 2 * P.N_PROBE
    proto = load(CFG / "m3pi1v_probe_protocol.json")
    assert proto["no_adaptive_probe"] is True and proto["single_budget_level"] is True
