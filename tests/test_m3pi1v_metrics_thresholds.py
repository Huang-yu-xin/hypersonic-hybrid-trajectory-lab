"""M3-PI1V metric/threshold contracts, post-incident status.

Frontier/selection logic is verified against the quarantined attempt-2
diagnostic record and against the frozen pure functions.  The authoritative
PI1V verdict is PI1V-X (see m3pi1vr0_pi1v_scientific_status.json): the
quarantined PI1V-C verdict file is retained for provenance only.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1v as P  # noqa: E402

OUT = ROOT / "results/phase_m3pi1v/summary"
QSUM = ROOT / "results/phase_m3pi1v/quarantine_attempt2/summary_analysis"
CFG = ROOT / "configs/phase_m3pi1v"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3pi1v_metric_contract_hash():
    rec = load(OUT / "m3pi1v_prereg_hashes.json")
    h = {e["path"]: e["sha256"] for e in rec["files"]}
    for rel in ("configs/phase_m3pi1v/m3pi1v_metric_contract.json",
                "results/phase_m3pi1v/summary/m3pi1v_metric_contract.json"):
        assert h[rel] == sha(ROOT / rel)
    mc = load(CFG / "m3pi1v_metric_contract.json")
    assert mc["denominators_redefined"] is False
    assert mc["gates"] == {"wrong_direction_max": 0.05, "coverage_min": 0.75,
                           "unsafe_max": 0.20}


def test_m3pi1v_wrong_gate_5pct():
    for fam in ("V1", "S1"):
        for r in csv_rows(QSUM / f"m3pi1v_{fam.lower()}_threshold_frontier.csv"):
            if r["full_gate_pass"] in ("True", True):
                assert float(r["wrong_direction_rate"]) <= 0.05
    assert P.GATES["wrong_direction_max"] == 0.05


def test_m3pi1v_coverage_gate_75pct():
    for fam in ("V1", "S1"):
        for r in csv_rows(QSUM / f"m3pi1v_{fam.lower()}_threshold_frontier.csv"):
            if r["full_gate_pass"] in ("True", True):
                assert float(r["deployable_coverage"]) >= 0.75
    assert P.GATES["coverage_min"] == 0.75


def test_m3pi1v_unsafe_gate_20pct():
    for fam in ("V1", "S1"):
        for r in csv_rows(QSUM / f"m3pi1v_{fam.lower()}_threshold_frontier.csv"):
            if r["full_gate_pass"] in ("True", True):
                assert float(r["unsafe_rate"]) <= 0.20
    assert P.GATES["unsafe_max"] == 0.20


def test_m3pi1v_threshold_candidate_rule():
    grid = P.threshold_grid([1.0, 2.0, 4.0])
    assert grid[0] == 0.0 and grid[-1] == 5.0          # deploy-all / abstain-all sentinels
    assert grid[1:-1] == [1.5, 3.0]                    # all midpoints of unique values
    for fam in ("V1", "S1"):
        fr = csv_rows(QSUM / f"m3pi1v_{fam.lower()}_threshold_frontier.csv")
        assert float(fr[0]["deployable_coverage"]) >= float(fr[1]["deployable_coverage"])
        assert float(fr[-1]["deployable_coverage"]) == 0.0


def test_m3pi1v_threshold_tie_break():
    # two thresholds with identical coverage: lower unsafe wins
    fr = [{"threshold": 1.0, "deployable_coverage": 0.8, "unsafe_rate": 0.1,
           "wrong_direction_rate": 0.0, "safety_compliant": True,
           "full_gate_pass": False},
          {"threshold": 2.0, "deployable_coverage": 0.8, "unsafe_rate": 0.05,
           "wrong_direction_rate": 0.0, "safety_compliant": True,
           "full_gate_pass": False}]
    assert P.select_threshold(fr)["threshold"] == 2.0
    # identical coverage and unsafe: lower wrong wins
    fr2 = [dict(fr[1], wrong_direction_rate=0.02),
           dict(fr[1], threshold=3.0, wrong_direction_rate=0.01)]
    assert P.select_threshold(fr2)["threshold"] == 3.0
    # identical metrics: the more conservative (higher) threshold wins
    fr3 = [dict(fr[1]), dict(fr[1], threshold=4.0)]
    assert P.select_threshold(fr3)["threshold"] == 4.0
    # unsafe above 20% is never retained
    assert P.select_threshold([{"threshold": 1.0, "deployable_coverage": 0.8,
                                "unsafe_rate": 0.3, "wrong_direction_rate": 0.0,
                                "safety_compliant": False}]) is None


def test_m3pi1v_best_safe_coverage():
    fr = [{"threshold": 1.0, "deployable_coverage": 0.9, "unsafe_rate": 0.5,
           "wrong_direction_rate": 0.0, "safety_compliant": False},
          {"threshold": 2.0, "deployable_coverage": 0.7, "unsafe_rate": 0.1,
           "wrong_direction_rate": 0.0, "safety_compliant": True},
          {"threshold": 3.0, "deployable_coverage": 0.6, "unsafe_rate": 0.0,
           "wrong_direction_rate": 0.0, "safety_compliant": True}]
    assert P.best_safe_coverage(fr) == 0.7
    gain = load(QSUM / "m3pi1v_comparative_information_gain.json")
    for fam in ("V1", "S1"):
        frn = csv_rows(QSUM / f"m3pi1v_{fam.lower()}_threshold_frontier.csv")
        compliant = [r for r in frn if r["safety_compliant"] in ("True", True)]
        expect = max((float(r["deployable_coverage"]) for r in compliant), default=0.0)
        assert gain[f"{fam}_BEST_SAFE_COVERAGE"] == expect


def test_m3pi1v_unique_gain_5pp():
    contract = load(CFG / "m3pi1v_threshold_contract.json")
    assert contract["unique_information_criterion"]["gain_threshold_pp"] == 0.05
    gain = load(QSUM / "m3pi1v_comparative_information_gain.json")
    assert gain["gain_ge_5pp"] == (gain["coverage_gain"] >= 0.05)
    assert gain["unique_information_criterion"] == (
        "YES" if gain["V1_FULL_PASS"] and (not gain["S1_FULL_PASS"]
                                           or gain["coverage_gain"] >= 0.05) else "NO")


def test_m3pi1v_verdict_priority():
    f = P.verdict_priority
    assert f(False, False, False, False) == "PI1V-X"
    assert f(True, False, False, False) == "PI1V-D"
    assert f(True, True, False, False) == "PI1V-C"
    assert f(True, True, True, False) == "PI1V-B"
    assert f(True, True, True, True) == "PI1V-A"
    # authoritative status: attempt-1 made the whole PI1V stage persistence-
    # invalid, so the frozen priority yields PI1V-X (persistence_ok = False)
    status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["PI1V valid verdict"] == "PI1V-X"
    assert status["PI1V-C retained as primary"] == "NO"
    # the quarantined PI1V-C verdict remains internally consistent with its own
    # (then-trusted persistence) inputs -- diagnostic provenance only
    final = load(QSUM / "m3pi1v_final_verdict.json")
    gain = load(QSUM / "m3pi1v_comparative_information_gain.json")
    sanity = load(QSUM / "m3pi1v_direction_sanity.json")
    pers = load(QSUM / "m3pi1v_persistence_audit.json")
    diagnostic = f(pers["canonical_hashes"] == "PASS", sanity["gate"] == "PASS",
                   bool(gain["V1_FULL_PASS"]),
                   gain["unique_information_criterion"] == "YES")
    assert final["verdict"] == diagnostic == "PI1V-C"
