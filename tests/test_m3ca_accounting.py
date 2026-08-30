"""M3-CA reproduction, accounting and counterfactual tests."""

from __future__ import annotations

import ast
import math
from pathlib import Path

from hyptraj.m3ca.accounting import run_attribution
from hyptraj.m3ca.metrics import budget_vrf

REPO = Path(__file__).resolve().parents[1]


def result() -> dict:
    return run_attribution(REPO)


def test_m3ca_zero_simulator_calls():
    paths = list((REPO / "src" / "hyptraj" / "m3ca").glob("*.py")) + [
        REPO / "scripts" / "run_m3ca_cost_attribution.py",
        REPO / "scripts" / "plot_m3ca_cost_attribution.py",
    ]
    banned = {
        "draw_online_pilot", "matched_arm_m2", "assemble_state",
        "eval_proposal_is", "run_mc", "default_rng", "simulate",
        "run_simulation", "generate_pilot",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not banned & (names | attrs), (path, banned & (names | attrs))
    assert result()["extra_simulator_calls"] == 0


def test_m3ca_deployable_vs_audit_cost_separation():
    rows = result()["cost_ledger"]
    audit = [r for r in rows if r["method"] == "AUDIT_REFERENCE_CHARACTERIZATION"]
    assert len(audit) == 24
    assert all(r["deployable_cost"] == 0 and r["audit_only_cost"] > 0
               for r in audit)
    deployed = [r for r in rows if r["method"] != "AUDIT_REFERENCE_CHARACTERIZATION"]
    assert all(r["audit_only_cost"] == 0 for r in deployed)


def test_m3ca_vrf_recompute():
    r = result()
    h = r["headline_reproduction"]
    assert h["pass"]
    assert round(h["vrf_budget_m3g_v1_median"], 4) == 0.0084
    assert max(row["stored_vrf_formula_max_abs_diff"]
               for row in r["state_rows"]) < 1e-15


def test_m3ca_oracle_capture_recompute():
    h = result()["headline_reproduction"]
    assert math.isclose(h["oracle_headroom"], 0.054152015,
                        rel_tol=0, abs_tol=1e-8)
    assert math.isclose(h["v1_headroom"], 0.05255944,
                        rel_tol=0, abs_tol=1e-8)
    assert math.isclose(h["capture_fraction"], 0.970590655,
                        rel_tol=0, abs_tol=1e-8)


def test_m3ca_free_adaptation_formula():
    r = result()["counterfactuals"]
    assert math.isclose(r["vrf_budget_free_adaptation"],
                        1.2 * r["vrf_budget_m3g_v1"],
                        rel_tol=0, abs_tol=1e-12)


def test_m3ca_free_oracle_formula():
    r = result()
    assert all(row["free_oracle_vrf_median"] > 0 for row in r["state_rows"])
    assert math.isclose(r["counterfactuals"]["vrf_budget_free_oracle"],
                        0.010053236113756588, rel_tol=0, abs_tol=1e-12)
    assert r["counterfactuals"]["free_oracle_gt_1"] is False


def test_m3ca_bestfixed_no_adaptation():
    rows = [r for r in result()["cost_ledger"] if r["method"] == "BestFixed"]
    assert len(rows) == 24
    assert all(r["pilot_cost"] == 0 and r["decision_cost"] == 0
               and r["deployable_cost"] == 100000 for r in rows)


def test_m3ca_value_axis_action_parity():
    r = result()
    assert r["headline_reproduction"]["value_axis_action_parity"] is True
    assert all(row["value_axis_action_parity"] for row in r["state_rows"])


def test_m3ca_budget_formula_reference():
    # Frozen semantic: changing B from 120k to 100k multiplies VRF by 1.2.
    a = budget_vrf(0.04, 8.0, 0.04, 100000, 120000)
    b = budget_vrf(0.04, 8.0, 0.04, 100000, 100000)
    assert math.isclose(b / a, 1.2, rel_tol=0, abs_tol=1e-15)
