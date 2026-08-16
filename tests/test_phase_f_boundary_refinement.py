"""Phase-F boundary-refinement tests (F3).

Covers the F3 acceptance surface A-Y (the full refinement is executed
manually by experiments/07_gamma_k_sensitivity/run_boundary_refinement.py,
never under pytest):

A. Phi_N N-side = terminal altitude - h_atm
B. Phi_N N+1 side uses NEW/LAST VAC apogee, not min(M_A)
C. Phi sign synthetic examples correct
D. Phi undefined for unrelated regime
E. new-exit index correct
F. new-exit dhdt positive on baseline branch example
G. coarse cell splits into 4 exact children
H. five midpoint evaluations dedup
I. depth-5 resolution satisfies target
J. uniform child terminates
K. adjacent-regime child refines
L. exact-only child refines
M. multiskip gets P0 classification
N. guardrail child never samples outside domain
O. OPEN edge flag works
P. terminal cell center marked visualization-only
Q. cache resume works (point-cache round-trip)
R. cache provenance mismatch rejected
S. recovered point enters reference queue
T. sign anomaly enters reference queue
U. boundary exclusion artifact schema
V. no derivative fields
W. no Phase-E B/C/D fields
X. row multiplicity logic
Y. Phase E/F1/F2 anchor behavior unchanged
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis.sensitivity_refinement import (
    ADJACENT_SKIP_BRANCH,
    EXACT_TOPOLOGY_ONLY,
    GAMMA_GUARD_MAX,
    GAMMA_GUARD_MIN,
    K_GUARD_MAX,
    K_GUARD_MIN,
    MAX_DEPTH,
    MULTISKIP,
    TERMINAL_REFINED_BOUNDARY_CELL,
    TERMINAL_UNRESOLVED_MULTISKIP_CELL,
    UNIFORM,
    DyadicCell,
    assemble_terminal_cell,
    branch_from_regimes,
    branch_label,
    build_f4_exclusion_cells,
    child_is_candidate,
    classify_cell_branch,
    coarse_cell_from_rectangle,
    new_exit_transversality,
    open_edges_of_cell,
    phi_n_for_point,
    phi_sign_anomaly,
    row_column_multiplicity,
    target_resolution_reached,
)
from hyptraj.analysis.sensitivity_pilot import (
    ParameterPoint,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.models.parameters import EnvironmentParams, VehicleParams

DATA_DIR = Path(__file__).resolve().parent / "data"
REFERENCE = json.loads(
    (DATA_DIR / "qian_sanger_comparison_v1.json").read_text(encoding="utf-8")
)

H_ATM = 100_000.0


def _sanger_row(regime="SRTI_N2", m_s=1000.0, m_a=None,
                exit_dhdt=None, skip=None) -> dict:
    return {
        "sanger_regime": regime,
        "terminal_kind": "srti" if regime.startswith("SRTI_N") else regime,
        "skip_count": skip if skip is not None else (
            int(regime[-1]) if regime.startswith("SRTI_N") else None),
        "M_S_clearance_m": m_s,
        "M_A_clearance_m": m_a if m_a is not None else [5000.0, 3000.0],
        "exit_dhdt_mps": exit_dhdt if exit_dhdt is not None else [100.0, 80.0],
        "exact_topology_signature": "sig",
        "event_sequence": ["atmosphere_exit", "atmosphere_entry",
                           "atmosphere_exit", "atmosphere_entry"],
    }


# ---------------------------------------------------------------------------
# A / B / C / D. Phi_N
# ---------------------------------------------------------------------------
def test_phi_n_side_terminal_minus_h_atm():
    row = _sanger_row(regime="SRTI_N2", m_s=13861.26)
    phi, side, diag = phi_n_for_point(row, 2, H_ATM)
    assert side == "N"
    assert phi == pytest.approx(-13861.26)
    assert diag["h_SRTI_m"] == pytest.approx(H_ATM - 13861.26)


def test_phi_n1_side_uses_new_last_vac_apogee_not_min():
    # SRTI_N4 for branch B3: FOUR VAC apogees; the newly-created one is
    # arc index 3 (zero-based), NOT min(M_A).
    m_a = [5000.0, 4000.0, 3000.0, 150.0]
    row = _sanger_row(regime="SRTI_N4", m_a=m_a)
    phi, side, diag = phi_n_for_point(row, 3, H_ATM)
    assert side == "N+1"
    assert phi == pytest.approx(150.0)          # arc index 3
    assert diag["apogee_index"] == 3
    assert phi != min(m_a) or min(m_a) == 150.0
    # A counter-example: min is at arc 0, newly-created is arc 3.
    m_a2 = [50.0, 4000.0, 3000.0, 2000.0]
    row2 = _sanger_row(regime="SRTI_N4", m_a=m_a2)
    phi2, _, _ = phi_n_for_point(row2, 3, H_ATM)
    assert phi2 == pytest.approx(2000.0)
    assert phi2 != min(m_a2)  # min = 50.0 would be the wrong choice


def test_phi_sign_synthetic_examples():
    neg, side_n, _ = phi_n_for_point(
        _sanger_row(regime="SRTI_N2", m_s=1000.0), 2, H_ATM)
    # SRTI_N3 has three VAC arcs; branch B2's newly-created apogee is
    # arc index 2 (zero-based).
    pos, side_p, _ = phi_n_for_point(
        _sanger_row(regime="SRTI_N3", m_a=[1000.0, 500.0, 200.0]), 2, H_ATM)
    assert neg < 0.0 and side_n == "N"
    assert pos == pytest.approx(200.0) and side_p == "N+1"


def test_phi_undefined_for_unrelated_regime():
    phi, side, diag = phi_n_for_point(
        _sanger_row(regime="SRTI_N0"), 2, H_ATM)
    assert phi is None and side is None
    assert "not in branch" in diag["reason"]


# ---------------------------------------------------------------------------
# E / F. new-exit transversality
# ---------------------------------------------------------------------------
def test_new_exit_index_correct():
    row = _sanger_row(regime="SRTI_N4", exit_dhdt=[10.0, 20.0, 30.0, 40.0])
    # SRTI_N4 is the N+1 side of branch B3 (n=3): the newly-created exit
    # is index 3 (zero-based).
    assert new_exit_transversality(row, 3) == pytest.approx(40.0)
    # For branch B2 (n=2) the SRTI_N4 point is not the N+1 side.
    assert new_exit_transversality(row, 2) is None
    assert new_exit_transversality(
        _sanger_row(regime="SRTI_N3"), 3) is None


def test_new_exit_dhdt_positive_on_baseline_example():
    # Baseline (-5 deg, 3) is SRTI_N2 = branch B1 N+1 side.
    env, veh = EnvironmentParams(), VehicleParams()
    pr = run_parameter_point(
        env, veh, ParameterPoint(-5.0, 3.0), git_commit="test")
    tn = new_exit_transversality(pr.sanger_row, 1)
    assert tn is not None
    assert tn > 0.0


# ---------------------------------------------------------------------------
# G / H / I. dyadic geometry
# ---------------------------------------------------------------------------
def test_coarse_cell_splits_into_4_exact_children():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    children = cell.subdivide()
    assert len(children) == 4
    for child in children:
        assert child.depth == 1
        assert child.delta_gamma_deg == pytest.approx(0.125)
        assert child.delta_k == pytest.approx(0.0625)
    # Children tile the parent exactly.
    g_lo = min(c.gamma_min for c in children)
    g_hi = max(c.gamma_max for c in children)
    k_lo = min(c.k_min for c in children)
    k_hi = max(c.k_max for c in children)
    assert (g_lo, g_hi, k_lo, k_hi) == (-7.0, -6.75, 2.0, 2.125)


def test_midpoint_evaluations_dedup():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    pts = cell.midpoint_points()
    keys = [(p.gamma0_deg, p.K) for p in pts]
    assert len(keys) == len(set(keys))  # five distinct points
    assert len(pts) == 5
    # Center is exactly the parent center.
    assert cell.center in [(p.gamma0_deg, p.K) for p in pts]


def test_depth5_resolution_satisfies_target():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    for _ in range(5):
        cell = cell.subdivide()[0]
    assert cell.depth == 5
    assert cell.delta_gamma_deg <= 0.01
    assert cell.delta_k <= 0.01
    assert target_resolution_reached(cell)


# ---------------------------------------------------------------------------
# J / K / L / M. child candidate rule
# ---------------------------------------------------------------------------
def _record_for(regime, sig="s", m_s=5000.0, m_a=None):
    from hyptraj.analysis.sensitivity_grid import cache_key
    rec = {
        "parameter": None,
        "qian": {
            "qian_regime": "QIAN_RTI",
            "exact_topology_signature": "q",
        },
        "sanger": _sanger_row(regime=regime, m_s=m_s, m_a=m_a),
    }
    rec["sanger"]["exact_topology_signature"] = sig
    return rec


def _lookup_from_grid(cell: DyadicCell, regimes: dict) -> dict:
    from hyptraj.analysis.sensitivity_grid import cache_key
    lookup = {}
    for p in cell.corner_points():
        lookup[cache_key(p)] = _record_for(regimes[(p.gamma0_deg, p.K)])
    return lookup


def test_uniform_child_terminates():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    regimes = {(g, k): "SRTI_N2" for g, k in
               ((p.gamma0_deg, p.K) for p in cell.corner_points())}
    lookup = _lookup_from_grid(cell, regimes)
    ok, reasons = child_is_candidate(cell, lookup, branch_n=1, h_atm=H_ATM)
    assert not ok
    assert reasons == []


def test_adjacent_regime_child_refines():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    corners = list(cell.corner_points())
    regimes = {p.key: "SRTI_N2" for p in corners}
    regimes[corners[1].key] = "SRTI_N3"  # adjacent-skip corner difference
    lookup = _lookup_from_grid(cell, regimes)
    ok, reasons = child_is_candidate(cell, lookup, branch_n=2, h_atm=H_ATM)
    assert ok
    assert "sanger_compact_differs" in reasons


def test_exact_only_child_refines():
    from hyptraj.analysis.sensitivity_grid import cache_key
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    corners = list(cell.corner_points())
    regimes = {p.key: "SRTI_N2" for p in corners}
    lookup = _lookup_from_grid(cell, regimes)
    lookup[cache_key(corners[1])]["sanger"][
        "exact_topology_signature"] = "variant"
    ok, reasons = child_is_candidate(cell, lookup, branch_n=1, h_atm=H_ATM)
    assert ok
    assert "sanger_exact_differs" in reasons


def test_multiskip_gets_p0_classification():
    classification, branch = classify_cell_branch(
        ("SRTI_N1", "SRTI_N3", "SRTI_N1", "SRTI_N3"))
    assert classification == MULTISKIP
    assert branch is None


def test_adjacent_branch_classification():
    classification, branch = classify_cell_branch(
        ("SRTI_N2", "SRTI_N3", "SRTI_N2", "SRTI_N3"))
    assert classification == ADJACENT_SKIP_BRANCH
    assert branch == "B2"
    assert branch_from_regimes("SRTI_N2", "SRTI_N3") == "B2"
    assert branch_from_regimes("SRTI_N2", "SRTI_N4") is None


# ---------------------------------------------------------------------------
# N / O / P. guardrail / open edges / visualization-only center
# ---------------------------------------------------------------------------
def test_guardrail_child_never_samples_outside_domain():
    # A cell touching the gamma lower guardrail: midpoints stay inside.
    cell = DyadicCell(depth=0, g_i=0, k_i=16)  # gamma=-9..-8.75, K=3..3.125
    assert cell.gamma_min == GAMMA_GUARD_MIN
    for p in cell.midpoint_points():
        assert GAMMA_GUARD_MIN - 1e-12 <= p.gamma0_deg <= GAMMA_GUARD_MAX
        assert K_GUARD_MIN - 1e-12 <= p.K <= K_GUARD_MAX
    # K lower guardrail cell.
    cell2 = DyadicCell(depth=0, g_i=16, k_i=0)  # gamma=-5..-4.75, K=1..1.125
    assert cell2.k_min == K_GUARD_MIN
    for p in cell2.midpoint_points():
        assert GAMMA_GUARD_MIN <= p.gamma0_deg <= GAMMA_GUARD_MAX
        assert K_GUARD_MIN <= p.K <= K_GUARD_MAX


def test_open_edge_flag_works():
    cell = DyadicCell(depth=0, g_i=0, k_i=0)  # gamma lower + K lower
    edges = open_edges_of_cell(cell)
    assert "gamma_lower" in edges and "K_lower" in edges
    # Depth-5 grid has 32*2^5 = 1024 gamma cells; the last cell
    # (g_i = 1023) touches the gamma upper guardrail.
    cell2 = DyadicCell(depth=5, g_i=1023, k_i=0)
    assert "gamma_upper" in open_edges_of_cell(cell2)


def test_terminal_cell_center_visualization_only():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    from hyptraj.analysis.sensitivity_grid import cache_key
    lookup = {
        cache_key(p): _record_for("SRTI_N2") for p in cell.corner_points()
    }
    rec = assemble_terminal_cell(
        cell, ADJACENT_SKIP_BRANCH, "B1", lookup, H_ATM)
    assert rec["terminal_type"] == TERMINAL_REFINED_BOUNDARY_CELL
    assert rec["visualization_center_only"] is True
    assert rec["rectangle"]["gamma_min"] == -7.0
    assert "center" in rec


# ---------------------------------------------------------------------------
# Q / R. cache resume / provenance
# ---------------------------------------------------------------------------
def test_cache_round_trip_and_provenance_mismatch(tmp_path):
    from hyptraj.analysis.sensitivity_refinement import (
        validate_f3_cache_record)
    rec = {
        "schema_version": "f3-refinement-point-v1",
        "parameter": [-5.0, 3.0],
        "provenance": {
            "phase_e_anchor_commit":
                "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc",
            "phase_f_protocol_commit": "x",
            "phase_f_f01_commit": "x",
            "phase_f_f1_commit": "x",
            "phase_f_f21_commit": "x",
            "phase_f_f2_commit": "35c66375081bf9f4924f365f2a5517dcfee3e3f4",
            "sanger_research_event_resolution_version": "v1",
            "solver_config": {"method": "DOP853"},
            "domain_guardrails": {
                "gamma0_deg": [GAMMA_GUARD_MIN, GAMMA_GUARD_MAX],
                "K": [K_GUARD_MIN, K_GUARD_MAX],
            },
            "max_depth": MAX_DEPTH,
        },
    }
    expected = dict(rec["provenance"])
    expected["schema_version"] = rec["schema_version"]
    ok, _ = validate_f3_cache_record(rec, expected)
    assert ok
    bad = dict(rec)
    bad["provenance"] = dict(rec["provenance"])
    bad["provenance"]["phase_f_f2_commit"] = "wrong"
    ok2, reason = validate_f3_cache_record(bad, expected)
    assert not ok2
    assert "phase_f_f2_commit" in reason


# ---------------------------------------------------------------------------
# S / T. reference queues
# ---------------------------------------------------------------------------
def test_recovered_point_enters_reference_queue():
    from hyptraj.analysis.sensitivity_refinement import (
        recovered_event_reference_entry)
    entry = recovered_event_reference_entry((-7.75, 3.125), "SRTI_N3", 3)
    assert entry["reason"] == "DENSE_RECOVERED"
    assert entry["parameter"] == [-7.75, 3.125]


def test_sign_anomaly_enters_reference_queue():
    from hyptraj.analysis.sensitivity_refinement import (
        sign_anomaly_reference_entry)
    entry = sign_anomaly_reference_entry((-5.0, 3.0), "SRTI_N2", 5.0, "N")
    assert entry["reason"] == "PHI_SIGN_ANOMALY"
    assert entry["phi"] == 5.0
    # phi_sign_anomaly itself:
    assert phi_sign_anomaly(5.0, "N") is True     # N side >= 0 -> anomaly
    assert phi_sign_anomaly(-5.0, "N") is False
    assert phi_sign_anomaly(-1.0, "N+1") is True  # N+1 side <= 0 -> anomaly
    assert phi_sign_anomaly(1.0, "N+1") is False
    assert phi_sign_anomaly(None, None) is False


# ---------------------------------------------------------------------------
# U. F4 exclusion schema
# ---------------------------------------------------------------------------
def test_f4_exclusion_schema():
    cell = coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125)
    from hyptraj.analysis.sensitivity_grid import cache_key
    lookup = {
        cache_key(p): _record_for("SRTI_N2") for p in cell.corner_points()
    }
    refined = assemble_terminal_cell(
        cell, ADJACENT_SKIP_BRANCH, "B1", lookup, H_ATM)
    excl = build_f4_exclusion_cells([refined], [], [])
    assert excl["schema_version"] == "f3-f4-exclusion-v1"
    assert len(excl["cells"]) == 1
    assert excl["cells"][0]["type"] == TERMINAL_REFINED_BOUNDARY_CELL
    assert "rectangle" in excl["cells"][0]


# ---------------------------------------------------------------------------
# V / W. schema purity
# ---------------------------------------------------------------------------
def test_no_derivative_fields():
    payload = json.dumps(assemble_terminal_cell(
        coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125),
        ADJACENT_SKIP_BRANCH, "B1", {}, H_ATM))
    for token in ("dR/dgamma", "dR/dK", "gradient", "derivative"):
        assert token.lower() not in payload.lower()


def test_no_protocol_bcd_fields():
    payload = json.dumps(assemble_terminal_cell(
        coarse_cell_from_rectangle(-7.0, -6.75, 2.0, 2.125),
        ADJACENT_SKIP_BRANCH, "B1", {}, H_ATM))
    for token in ("time_limiter", "range_limiter", "exposure_limiter",
                  "common_time", "common_range", "protocol_d"):
        assert token not in payload


# ---------------------------------------------------------------------------
# X. multiplicity
# ---------------------------------------------------------------------------
def test_row_column_multiplicity_logic():
    cells = [
        {"rectangle": {"gamma_min": -7.0, "gamma_max": -6.99,
                       "K_min": 2.0, "K_max": 2.01}},
        {"rectangle": {"gamma_min": -7.0, "gamma_max": -6.99,
                       "K_min": 3.0, "K_max": 3.01}},
        {"rectangle": {"gamma_min": -6.0, "gamma_max": -5.99,
                       "K_min": 2.0, "K_max": 2.01}},
    ]
    m = row_column_multiplicity(cells)
    # gamma=-7 row has two disjoint K clusters; K=2.0 column has two
    # disjoint gamma clusters (gap between -7 and -6).
    assert m["max_row_multiplicity"] == 2
    assert m["max_column_multiplicity"] == 2
    assert len(m["rows_with_multiplicity_gt_1"]) == 1
    assert len(m["columns_with_multiplicity_gt_1"]) == 1


# ---------------------------------------------------------------------------
# Y. anchor behavior unchanged
# ---------------------------------------------------------------------------
def test_anchor_behavior_unchanged():
    env, veh = EnvironmentParams(), VehicleParams()
    anchor = verify_baseline_anchor(
        env, veh, git_commit="test", reference_json=REFERENCE)
    assert anchor["pass"]
    assert anchor["qian"]["regime"] == "QIAN_RTI"
    assert anchor["sanger"]["regime"] == "SRTI_N2"
    pr = run_parameter_point(
        env, veh, ParameterPoint(-5.0, 3.0), git_commit="test")
    assert pr.sanger_row["sanger_regime"] == "SRTI_N2"
    assert pr.sanger_row["skip_count"] == 2
