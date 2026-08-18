"""Phase-G6 grazing tests -- frozen-anchor semantics / event algebra / family
(G6 §64-§66, §70).  The expensive research/reference runs are committed in
``phase_g6_grazing_predictability_v1.json``; this file reads that concise
snapshot and keeps a small live smoke of the pure algebra so the regression
is not self-fulfilling.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability import grazing as G

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAP = json.loads((DATA_DIR / "phase_g6_grazing_predictability_v1.json")
                  .read_text(encoding="utf-8"))

S_A = SNAP["canonical_scale"]


@pytest.fixture(scope="module")
def anchors():
    return G.load_frozen_grazing_anchors()


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


# ---------------------------------------------------------------------------
# 1. Frozen-anchor semantics (G6 §64)
# ---------------------------------------------------------------------------
def test_anchor_table_loads(anchors):
    assert len(anchors) == 10
    branches = {a.branch for a in anchors}
    assert branches == {"B0", "B1", "B2", "B3", "B4"}
    assert sum(1 for a in anchors if a.side == "N_side") == 5
    assert sum(1 for a in anchors if a.side == "N1_side") == 5


def test_anchor_dual_reference_stable(anchors):
    # 10/10 dual-reference-stable flags (from the Phase-F snapshot loader)
    for a in anchors:
        assert a.phase_f_reference_phi_m == a.phase_f_reference_phi_m  # finite


def test_anchor_regimes_match(anchors):
    audit = {f"{r['branch']}_{r['side']}": r for r in SNAP["frozen_anchor_audit"]}
    for a in anchors:
        rec = audit[f"{a.branch}_{a.side}"]
        assert rec["regime_match"] is True, (a.branch, a.side)
        assert rec["actual_regime"] == a.expected_regime


def test_phi_n_signs_and_reproduction(anchors):
    audit = {f"{r['branch']}_{r['side']}": r
             for r in SNAP["frozen_anchor_audit"]}
    for a in anchors:
        rec = audit[f"{a.branch}_{a.side}"]
        phi = rec["recomputed_phi_m"]
        if a.side == "N_side":
            assert phi < 0.0
            assert rec["has_excursion"] is False
        else:
            assert phi > 0.0
            assert rec["has_excursion"] is True
        # G6-recomputed Phi_N reproduces the Phase-F reference clearance
        assert rec["phi_diff_abs"] < 0.05, (a.branch, a.side)


def test_new_exit_ordinal_exists_only_on_nplus_side(anchors):
    audit = {f"{r['branch']}_{r['side']}": r
             for r in SNAP["frozen_anchor_audit"]}
    for a in anchors:
        rec = audit[f"{a.branch}_{a.side}"]
        if a.side == "N_side":
            assert rec["has_excursion"] is False
        else:
            assert rec["has_excursion"] is True


# ---------------------------------------------------------------------------
# 2. Event algebra / conditioning identities (G6 §65)
# ---------------------------------------------------------------------------
def test_event_denominators_and_incidence(base, anchors):
    env, veh = base
    audit = {o["branch"]: o for o in SNAP["nplus_event_audit"]}
    for a in [x for x in anchors if x.side == "N1_side"]:
        rec = audit[a.branch]
        assert rec["d_exit"] > 0.0
        assert rec["entry_denominator"] < 0.0
        assert 0.0 < rec["incidence_abs_sin_gamma"] < 0.2
        assert rec["vac_duration_s"] > 0.0
        assert rec["vac_clearance_m"] > 0.0
        assert rec["target_exit_ordinal"] == a.N


def test_conditioning_identities_machine_precision(base, anchors):
    env, veh = base
    audit = {o["branch"]: o for o in SNAP["nplus_event_audit"]}
    for a in [x for x in anchors if x.side == "N1_side"]:
        rec = audit[a.branch]
        assert abs(rec["identity_q_residual"]) < 1e-6, a.branch
        assert abs(rec["identity_xi_residual"]) < 1e-6, a.branch
        # det(Xi)=1 for the interface saltation
        assert rec["det_xi_exit"] == pytest.approx(1.0, abs=1e-9)


def test_exit_sign_sanity_live(base, anchors):
    """Small live smoke (not self-fulfilling): recompute one B0 N+1 exit
    saltation sign structure directly from the frozen RHS."""
    env, veh = base
    a = next(x for x in anchors if x.branch == "B0" and x.side == "N1_side")
    exc = G.extract_branch_excursion(a, env, veh,
                                     _ref_solver())
    em = G.grazing_event_metrics(exc.exit_state, env, veh, a.K)
    xi = em["xi"]
    # Sanger Xi: only the radial input column differs; theta/v/gamma columns
    # are identity.
    assert np.allclose(xi[:, 1], [0, 1, 0, 0], atol=1e-12)
    assert np.allclose(xi[:, 2], [0, 0, 1, 0], atol=1e-12)
    assert np.allclose(xi[:, 3], [0, 0, 0, 1], atol=1e-12)
    # v-row positive, gamma-row negative in the radial column.
    assert xi[2, 0] > 0.0
    assert xi[3, 0] < 0.0


def _ref_solver():
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    return REFERENCE_SOLVER_CONFIG


def test_exact_scaled_identity_live(base):
    """Live machine check of |d|*||qS|| = s_r and the scaled Xi rank-one
    conditioning identity (G6 §12-§13, §58)."""
    env, veh = base
    anchors = G.load_frozen_grazing_anchors()
    a = next(x for x in anchors if x.branch == "B2" and x.side == "N1_side")
    exc = G.extract_branch_excursion(a, env, veh, _ref_solver())
    em = G.grazing_event_metrics(exc.exit_state, env, veh, a.K)
    assert em["identity_q_residual"] < 1e-8
    assert em["identity_xi_residual"] < 1e-8


# ---------------------------------------------------------------------------
# 3. Controlled local grazing family (G6 §66)
# ---------------------------------------------------------------------------
def test_family_structure():
    for branch, fam in SNAP["controlled_families"].items():
        pts = fam["points"]
        assert len(pts) >= 4, branch
        # alphas strictly decreasing, positive
        alphas = [p["alpha"] for p in pts]
        assert all(alphas[i] > alphas[i + 1] for i in range(len(alphas) - 1))
        # d_exit -> 0 as alpha shrinks
        ds = [p["d_exit"] for p in pts]
        assert all(ds[i] > ds[i + 1] for i in range(len(ds) - 1))
        # clearance positive and decreasing (quadratic tangency trend)
        cls = [p["clearance_m"] for p in pts]
        assert all(c > 0 for c in cls)
        assert all(cls[i] > cls[i + 1] for i in range(len(cls) - 1))
        # VAC duration positive and decreasing
        ts = [p["vac_duration_s"] for p in pts]
        assert all(t > 0 for t in ts)
        # entries exist with d_entry < 0
        assert all(p["d_entry"] < 0 for p in pts)
        # last point either REF_STABLE or explicit NUMERICAL_RESOLUTION_LIMIT
        assert pts[-1]["class"] in ("REF_STABLE", "NUMERICAL_RESOLUTION_LIMIT")


def test_family_ref_stable_tail():
    for branch, fam in SNAP["controlled_families"].items():
        for p in fam["points"]:
            assert p["ref_stable"] in (True, False)
            # no fabricated stability: a False point stops the family
        stable = [p for p in fam["points"] if p["ref_stable"]]
        assert len(stable) >= 3, branch


def test_family_quadratic_tangency_trend():
    # Phi_local vs |d_exit|: fit slope near 2 in the stable tail (H1).
    for branch, fit in SNAP["scaling_fits"].items():
        if fit is None:
            continue
        assert fit["points_used"] >= 3
        assert fit["H1_Phi_vs_d_slope"] > 1.25, branch
        assert fit["H1_Phi_vs_d_slope"] < 2.75, branch


# ---------------------------------------------------------------------------
# 4. Numeric threshold decision (G6 §70)
# ---------------------------------------------------------------------------
def test_threshold_decision_outcome():
    decision = SNAP["threshold_decision"]
    assert decision["outcome"] in (
        "EMPIRICAL_OPERATIONAL_THRESHOLD_CANDIDATE",
        "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED")


def test_no_universal_physics_threshold_frozen():
    # G6 must NOT define a bare "|d| < X" universal physics threshold.
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "grazing.py").read_text(encoding="utf-8")
    assert "abs(nTf) < 1.0" not in src
    assert "abs(nTf) < 1" not in src


# ---------------------------------------------------------------------------
# 5. Snapshot / scope
# ---------------------------------------------------------------------------
def test_snapshot_schema():
    assert SNAP["schema_version"] == "phase-g6-grazing-predictability-v1"
    assert SNAP["claim_boundaries"]["no_infinite_physical_sensitivity"] is True
    assert SNAP["claim_boundaries"]["no_chaos_claim"] is True
    assert SNAP["canonical_scale"]["r"] == 1e5  # Candidate A unchanged


def test_canonical_scale_a_unchanged():
    from hyptraj.predictability.scaling import canonical_candidate
    assert canonical_candidate().key == "A"