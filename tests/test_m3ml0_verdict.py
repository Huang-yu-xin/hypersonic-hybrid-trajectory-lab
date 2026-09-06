"""M3-ML0 verdict tests (taskbook Sec. 22 -- Verdict, synthetic)."""
from __future__ import annotations

import sys
from pathlib import Path

import sys as _sys

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
_sys.path.insert(0, str(ROOT / "scripts"))

import run_m3ml0 as R  # noqa: E402

GATES = R.GATES


def _cand(coverage, unsafe, wrong=0.0, amb=0.5, name="B2_s2_logistic"):
    m = {
        "deployable_coverage": coverage, "nd_unsafe": unsafe,
        "wrong_direction_rate": wrong, "truth_AMBIGUOUS": {"unsafe": amb},
        "truth_HOLD": {"unsafe": 0.0}, "safety_compliant": bool(
            coverage >= GATES["coverage_min"] and unsafe <= GATES["unsafe_max"]
            and wrong <= GATES["wrong_max"]),
        "trials": 384,
    }
    return {"model": name, "metrics": m, "gain": None, "ambig_improved": None}


def _s1(coverage=0.859375, unsafe=0.2109375, amb=0.375):
    return _cand(coverage, unsafe, amb=amb, name="frozen_s1")


def test_verdict_a_strong_candidate():
    # candidate safety-compliant, gain >= 5pp, AMBIGUOUS improved
    s1 = _s1(coverage=0.75, unsafe=0.20, amb=0.35)
    cands = {"B2_s2_logistic": _cand(0.82, 0.15, amb=0.25)}
    v = R._verdict_from(s1["metrics"], cands)
    assert v["VERDICT"] == "M3-ML0-A"


def test_verdict_b_compliant_but_no_gain():
    s1 = _s1(coverage=0.80, unsafe=0.18, amb=0.30)
    cands = {"B2_s2_logistic": _cand(0.83, 0.19, amb=0.29)}  # gain 3pp
    v = R._verdict_from(s1["metrics"], cands)
    assert v["VERDICT"] == "M3-ML0-B"


def test_verdict_b_compliant_but_ambig_not_improved():
    s1 = _s1(coverage=0.75, unsafe=0.20, amb=0.20)
    cands = {"B3_gbdt": _cand(0.90, 0.15, amb=0.22)}  # gain ok, AMB worse
    v = R._verdict_from(s1["metrics"], cands)
    assert v["VERDICT"] == "M3-ML0-B"


def test_verdict_c_no_compliant_candidate():
    s1 = _s1()
    cands = {
        "B1_logistic_s1": _cand(0.785, 0.234),   # unsafe fail
        "B2_s2_logistic": _cand(0.848, 0.219),   # unsafe fail
        "B3_gbdt": _cand(0.742, 0.141),          # coverage fail
    }
    v = R._verdict_from(s1["metrics"], cands)
    assert v["VERDICT"] == "M3-ML0-C"


def test_verdict_matches_actual_ml0_outcome():
    import json
    verd = json.loads((ROOT / "results/phase_m3ml0/summary/m3ml0_verdict.json")
                      .read_text(encoding="utf-8"))
    assert verd["VERDICT"] == "M3-ML0-C"
    assert verd["best_safety_compliant_candidate"] is None
