"""M3-S2F verdict + firewall/leakage tests (taskbook Sec. 18)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s2f as R  # noqa: E402
from hyptraj.m3s2f import recoverability as RC  # noqa: E402


# --------------------------------------------------------------------------
# verdict contract (synthetic S2F-A/B/C/R/X)
# --------------------------------------------------------------------------

def test_verdict_r_on_incompatible_recoverability():
    v = R._verdict_from("INCOMPATIBLE")
    assert v["VERDICT"] == "M3-S2F-R"
    assert v["candidates"] is None


def test_verdict_c_when_no_compliant_candidate():
    cands = {"S2F-LR": {"metrics": {"safety_compliant": False,
                                    "deployable_coverage": 0.848,
                                    "nd_unsafe": 0.219,
                                    "truth_AMBIGUOUS": {"unsafe": 0.333}}}}
    v = R._verdict_from("FULL", cands)
    assert v["VERDICT"] == "M3-S2F-C"


def _cand(cov, uns, amb, compliant=True):
    return {"metrics": {"safety_compliant": compliant,
                        "deployable_coverage": cov, "nd_unsafe": uns,
                        "truth_AMBIGUOUS": {"unsafe": amb},
                        "coverage_gain_vs_gbdt": 0.05,
                        "unsafe_reduction_vs_s1": 0.06}}


def test_verdict_a_requires_amb_and_gain():
    cands = {"S2F-GBDT": _cand(0.80, 0.15, 0.20)}
    v = R._verdict_from("FULL", cands)
    assert v["VERDICT"] == "M3-S2F-A"


def test_verdict_b_when_improvement_insufficient():
    cands = {"S2F-GBDT": _cand(0.80, 0.15, 0.30)}  # AMB not < 0.25
    v = R._verdict_from("FULL", cands)
    assert v["VERDICT"] == "M3-S2F-B"


def test_verdict_x_on_unknown_classification():
    v = R._verdict_from("SOMETHING_ELSE")
    assert v["VERDICT"] == "M3-S2F-X"


def test_verdict_matches_actual_s2f_outcome():
    verd = R.load(ROOT / "results/phase_m3s2f/summary/m3s2f_verdict.json")
    assert verd["VERDICT"] == "M3-S2F-R"
    assert verd["n_trials_audited"] == 384


# --------------------------------------------------------------------------
# firewall / parent seal
# --------------------------------------------------------------------------

def test_protected_18_firewall():
    fw = R.load(ROOT / "results/phase_m3s2f/preflight/m3s2f_reserve_firewall.json")
    assert fw["remaining"] == 18 and fw["used_by_s2f"] == 0
    assert fw["RESERVE_FIREWALL"] == "PASS"
    rows = R.DS_csvread(ROOT / "results/phase_m3s2f/preflight/"
                               "m3s2f_protected_reserve_18.csv")
    assert len(rows) == 18
    assert all(r["status"] == "PROTECTED_RESERVE" for r in rows)
    # membership-only: no feature/truth columns
    assert set(rows[0].keys()) == {"state_id", "config_id", "status",
                                   "reserve_manifest_sha256"}


def test_parent_dataset_hash_seal():
    ck = R.load(ROOT / "results/phase_m3s2f/preflight/m3s2f_dataset_check.json")
    assert ck["match"] and ck["states"] == 48 and ck["trials"] == 384


def test_recoverability_contract_freezes_no_imputation():
    rc = R.load(ROOT / "configs/phase_m3s2f/m3s2f_recoverability_contract.json")
    assert rc["classification"] == "INCOMPATIBLE"
    assert rc["no_imputation"] and rc["no_proxy"] and rc["no_simulator_fallback"]
    assert rc["replay_required"] is True
