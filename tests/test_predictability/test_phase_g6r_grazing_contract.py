"""Phase-G6R grazing validation-conTRACT tests (G6R Issues 1-5).

Reads the committed snapshot's ``g6r`` block (hardened extraction
contract / dual-reference lock / refined operational radii / paired radial
plateau / full 4-column paired-map FD / threshold re-audit) and keeps a
small number of LIVE routing smokes (contract raise on planted wrong
regime, event-direction / nonphysical-state classification) so the
regression is not self-fulfilling.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from dataclasses import replace

from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)
from hyptraj.predictability import grazing as G
from hyptraj.predictability.stm import stm_strict_reference_config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAP = json.loads((DATA_DIR / "phase_g6_grazing_predictability_v1.json")
                  .read_text(encoding="utf-8"))
G6R = SNAP["g6r"]


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


@pytest.fixture(scope="module")
def anchors():
    return G.load_frozen_grazing_anchors()


# ---------------------------------------------------------------------------
# 1. Issue 1 -- hardened extraction contract (snapshot + live)
# ---------------------------------------------------------------------------
def test_snapshot_contract_audit_counts():
    ca = G6R["contract_audit"]
    assert ca["n_anchors"] == 10
    assert ca["n_side_absence_confirmations"] == 5
    assert ca["n1_side_extractions"] == 5
    assert ca["dual_reference_stable_10of10"] is True


def test_snapshot_contract_anchor_details(anchors):
    ca = G6R["contract_audit"]
    by_key = {f"{r['branch']}_{r['side']}": r for r in ca["anchors"]}
    assert len(by_key) == 10
    for a in anchors:
        rec = by_key[f"{a.branch}_{a.side}"]
        assert rec["expected_regime"] == a.expected_regime
        assert rec["reference_dual_stable"] is True
        # N+1 side: extracted short-VAC excursion with the hard sign guards
        if a.side == "N1_side":
            assert rec["has_excursion"] is True
            assert rec["target_exit_ordinal"] == a.N
            assert rec["entry_ordinal"] == a.N
            assert rec["exit_denominator"] > 0.0
            assert rec["entry_denominator"] < 0.0
            assert rec["vac_clearance_m"] > 0.0
            assert rec["vac_duration_s"] > 0.0
        else:
            assert rec["has_excursion"] is False


def test_extraction_is_hard_guard_live(base, anchors):
    """A planted Phase-F regime mismatch must raise
    GrazingTopologyContractError (HARD STOP), not return a soft flag."""
    env, veh = base
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    a = next(x for x in anchors if x.side == "N_side")
    with pytest.raises(G.GrazingTopologyContractError):
        G.extract_branch_excursion(
            replace(a, expected_regime="SRTI_N99"),
            env, veh, REFERENCE_SOLVER_CONFIG)
    a1 = next(x for x in anchors if x.side == "N1_side")
    with pytest.raises(G.GrazingTopologyContractError):
        G.extract_branch_excursion(
            replace(a1, expected_regime="SRTI_PULLOUT"),
            env, veh, REFERENCE_SOLVER_CONFIG)


# ---------------------------------------------------------------------------
# 1b. Issue 5 -- Phase-F dual-reference lock (10/10)
# ---------------------------------------------------------------------------
def test_dual_reference_lock_10of10(anchors):
    for a in anchors:
        assert a.reference_dual_stable is True, a.branch
        assert np.isfinite(a.phase_f_reference_phi_ref01)
        assert np.isfinite(a.phase_f_reference_phi_ref005)


# ---------------------------------------------------------------------------
# 2. Issue 2 -- refined operational radius (bracket + bisection)
# ---------------------------------------------------------------------------
def test_refined_radius_present_for_all_cases():
    rv = G6R["refined_validity_radii"]
    assert set(rv.keys()) == {"B0_a1", "B0_a0.5", "B3_a1", "B4_a1"}
    for key, rec in rv.items():
        assert rec["phi_local_m"] > 0.0
        assert rec["monotone_profile"] is True
        for tau in ("r_1pct_refined", "r_5pct_refined"):
            rr = rec[tau]
            assert rr["classification"] == "MONOTONE_REFINED_RADIUS"
            assert rr["lower_pass_beta"] < rr["refined_beta"] < (
                rr["upper_fail_beta"])
            assert rr["refined_radius_m"] == pytest.approx(
                rr["refined_beta"] * rec["phi_local_m"])
            assert rr["radius_over_phi"] == pytest.approx(rr["refined_beta"])
            assert rr["bracket_width"] > 0.0


def test_refined_radius_supersedes_grid_sample():
    """The refined radii must be strictly between the G6 coarse samples
    (0.03 / 0.10) -- i.e. no longer a grid lower bound."""
    rv = G6R["refined_validity_radii"]
    for key, rec in rv.items():
        r1 = rec["r_1pct_refined"]["radius_over_phi"]
        r5 = rec["r_5pct_refined"]["radius_over_phi"]
        # refined 1% lies between grid samples 0.03 (pass) and 0.1 (fail)
        assert r1 > 0.03 and r1 < 0.1, (key, r1)
        # refined 5% lies between grid samples 0.1 (pass) and 0.2 (fail)
        assert r5 > 0.1 and r5 < 0.2, (key, r5)


def test_refined_radius_scale_free_uniform():
    rv = G6R["refined_validity_radii"]
    r1 = [rec["r_1pct_refined"]["radius_over_phi"] for rec in rv.values()]
    r5 = [rec["r_5pct_refined"]["radius_over_phi"] for rec in rv.values()]
    assert max(r1) - min(r1) < 0.01  # scale-free uniform near ~0.04
    assert max(r5) - min(r5) < 0.02  # scale-free uniform near ~0.19


# ---------------------------------------------------------------------------
# 3. Issue 3 -- radial derivative plateau at clearance-normalized beta
# ---------------------------------------------------------------------------
def test_radial_plateau_passes_strong_and_mild():
    for br in ("B0", "B4"):
        pl = G6R["paired_fd"][br]["radial_plateau"]
        assert pl["plateau_pass"] is True, br
        assert pl["both_sides_valid"] is True, br
        assert pl["max_scaled_rel_error"] < 1e-2, br
        assert pl["beta_range"] == [1e-4, 3e-2]


def test_radial_plateau_every_beta_both_sides_valid():
    for br in ("B0", "B4"):
        for rec in G6R["paired_fd"][br]["radial_plateau"]["records"]:
            assert rec["both_valid"] is True, (br, rec["beta"])
            assert rec["scaled_rel_error"] < 1e-2, (br, rec["beta"])


# ---------------------------------------------------------------------------
# 4. Issue 4 -- full 4-column paired-map FD (canonical-A scaled errors)
# ---------------------------------------------------------------------------
def test_four_column_validation_passes_strong_and_mild():
    for br in ("B0", "B4"):
        four = G6R["paired_fd"][br]["four_column"]
        assert four["four_column_pass"] is True, br
        assert set(four["columns"].keys()) == {"0", "1", "2", "3"}


def test_four_column_metric_contract():
    # radial column -> scaled-relative error; tangent columns -> absolute
    # scaled residual (per G6R Issue 4)
    for br in ("B0", "B4"):
        cols = G6R["paired_fd"][br]["four_column"]["columns"]
        assert cols["0"]["metric"] == "scaled_rel_error"
        assert cols["0"]["column_pass"] is True
        for j in ("1", "2", "3"):
            assert cols[j]["metric"] == "abs_scaled_residual"
            assert cols[j]["column_pass"] is True
            assert cols[j]["both_sides_valid"] is True


# ---------------------------------------------------------------------------
# 5. Issue 5 -- event-direction / nonphysical / numerical classes + routing
# ---------------------------------------------------------------------------
def test_event_direction_classes_present():
    P = G.PairedExcursionClass
    assert P.WRONG_EXIT_DIRECTION == "WRONG_EXIT_DIRECTION"
    assert P.WRONG_ENTRY_DIRECTION == "WRONG_ENTRY_DIRECTION"
    assert P.NONPHYSICAL_STATE == "NONPHYSICAL_STATE"
    assert P.VAC_EXCURSION_LOST == "VAC_EXCURSION_LOST"
    assert P.NUMERICAL_FAILURE == "NUMERICAL_FAILURE"
    # topology/direction loss is separated from pure numerical failure
    assert P.PAIR_LOCAL_VALID == "PAIR_LOCAL_VALID"


def test_wrong_exit_direction_routing_live(base, anchors):
    """A gamma perturbation BEYOND the incidence cone flips the minus-side
    exit crossing descending -> WRONG_EXIT_DIRECTION (not a PREDEFINED
    numerical failure)."""
    env, veh = base
    cfg = stm_strict_reference_config()
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    a = next(x for x in anchors if x.branch == "B0" and x.side == "N1_side")
    exc = G.extract_branch_excursion(a, env, veh, REFERENCE_SOLVER_CONFIG)
    x = exc.exit_state
    e = np.zeros(4)
    e[3] = 1.0
    eps = 1.5 * abs(x[3])
    _mp, cp, _ = G.local_grazing_excursion_map(
        x, eps * e, env, veh, a.K, cfg, exc.vac_duration_s)
    _mm, cm, _ = G.local_grazing_excursion_map(
        x, -eps * e, env, veh, a.K, cfg, exc.vac_duration_s)
    assert G.PairedExcursionClass.WRONG_EXIT_DIRECTION in (cp, cm)


def test_nonphysical_state_routing_live(base, anchors):
    """A radial delta pushing r below R_E routes to NONPHYSICAL_STATE."""
    env, veh = base
    cfg = stm_strict_reference_config()
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    a = next(x for x in anchors if x.branch == "B0" and x.side == "N1_side")
    exc = G.extract_branch_excursion(a, env, veh, REFERENCE_SOLVER_CONFIG)
    x = exc.exit_state
    e = np.zeros(4)
    e[0] = 1.0
    _m, cls, _ = G.local_grazing_excursion_map(
        x, -2.0e5 * e, env, veh, a.K, cfg, exc.vac_duration_s)
    assert cls == G.PairedExcursionClass.NONPHYSICAL_STATE


def test_nonphysical_class_in_extract_enum_order():
    # physical-kind ordinals stay exact: synthetic / pullout / SRTI
    # excluded from the excursion kind-ordinals
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "grazing.py").read_text(encoding="utf-8")
    assert "WRONG_ENTRY_DIRECTION" in src
    assert "_run_vac_excursion" in src


# ---------------------------------------------------------------------------
# 6. Threshold re-audit after refined radii
# ---------------------------------------------------------------------------
def test_threshold_reauth_confirmed():
    assert SNAP["threshold_decision"]["outcome"] == \
        "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED"
    assert G6R["threshold_reauth"]["after_refined_radii"] == \
        "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED"
    # refined radii remain scale-free uniform -> no dimensionful cutoff
    r1 = G6R["threshold_reauth"]["refined_radii_over_phi"]["r_1pct"]
    assert all(0.03 < v < 0.1 for v in r1.values())


# ---------------------------------------------------------------------------
# 7. Scope / snapshot integrity
# ---------------------------------------------------------------------------
def test_g6r_schema_and_no_phase_g_tag_creation():
    assert G6R["schema_version"] == "phase-g6r-grazing-contract-v1"
    assert "g6r" in SNAP
    # frozen G6 sections must be untouched
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "grazing.py").read_text(encoding="utf-8")
    for token in ("monte", "uncertainty", "final_tag", "global_lyap"):
        assert token not in src, token


def test_claim_boundaries_still_true():
    cb = SNAP["claim_boundaries"]
    assert cb["no_gamma0K_rescan"] is True
    assert cb["no_branch_refit"] is True
    assert cb["no_chaos_claim"] is True
