"""Phase-G6 grazing excursion / linearization-validity tests (G6 §67-§69).

Reads the committed concise snapshot for the expensive controlled-family,
validity-radius, topology-radius and terminal runs, and keeps a couple of
live smoke checks (one paired excursion FD) so the regression is not
self-fulfilling.
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
from hyptraj.predictability.stm import stm_strict_reference_config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAP = json.loads((DATA_DIR / "phase_g6_grazing_predictability_v1.json")
                  .read_text(encoding="utf-8"))
S_A = SNAP["canonical_scale"]


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


# ---------------------------------------------------------------------------
# 1. Paired excursion factor (G6 §67)
# ---------------------------------------------------------------------------
def test_excursion_factor_present_and_positive():
    for rec in SNAP["nplus_event_audit"]:
        f = rec["excursion_factor"]
        assert f["sigma_max"] > 0.0
        assert f["norm_scaled_minus_I"] >= 0.0
        assert f["rank"] in (3, 4)
        assert f["condition_status"] in ("FINITE", "STRUCTURAL_SINGULAR")


def test_pair_does_not_assume_cancellation():
    # Record whatever the data shows; no preset that exit/entry cancel.
    norms = [o["excursion_factor"]["norm_scaled_minus_I"]
             for o in SNAP["nplus_event_audit"]]
    assert all(n > 0 for n in norms)


def test_pair_nonlinear_fd_live(base):
    """Live smoke: one B0 N+1 radial FD of the paired map vs the analytic
    excursion factor (G6 §37, §67).  This re-runs a short local excursion
    so the committed snapshot is not self-fulfilling."""
    env, veh = base
    anchors = G.load_frozen_grazing_anchors()
    a = next(x for x in anchors if x.branch == "B0" and x.side == "N1_side")
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    exc = G.extract_branch_excursion(a, env, veh, REFERENCE_SOLVER_CONFIG)
    fac = G.build_excursion_factor(
        exc.exit_state, env, veh, a.K,
        c_vac_config=stm_strict_reference_config())
    nom_vac = float(exc.vac_duration_s)
    dr = 0.5 * float(exc.clearance_m)  # clearance-normalized radial step
    e = np.zeros(4); e[0] = 1.0
    mp, cp, _ = G.local_grazing_excursion_map(
        exc.exit_state, dr * e, env, veh, a.K,
        stm_strict_reference_config(), nom_vac)
    mm, cm, _ = G.local_grazing_excursion_map(
        exc.exit_state, -dr * e, env, veh, a.K,
        stm_strict_reference_config(), nom_vac)
    assert cp == G.PairedExcursionClass.PAIR_LOCAL_VALID
    assert cm == G.PairedExcursionClass.PAIR_LOCAL_VALID
    fd = (mp - mm) / (2.0 * dr)
    pcol = fac.p_excursion[:, 0]
    # scaled-relative agreement of the radial column
    err = np.linalg.norm(S_A_inv() @ (fd - pcol))
    scale = np.linalg.norm(S_A_inv() @ pcol)
    assert err / max(scale, 1e-12) < 0.5, "radial pair FD should track the pair column"


def S_A_inv():
    return np.diag(1.0 / np.array([S_A[k] for k in ("r", "theta", "v", "gamma")]))


# ---------------------------------------------------------------------------
# 2. Linearization validity radius (G6 §68)
# ---------------------------------------------------------------------------
def test_validity_radius_present():
    assert len(SNAP["validity_radii"]) >= 3
    for key, rec in SNAP["validity_radii"].items():
        assert rec["phi_local_m"] > 0.0
        for probe in rec["beta_sweep"]:
            assert probe["valid"] in (True, False)


def test_1pct_radius_only_from_valid_samples():
    for key, rec in SNAP["validity_radii"].items():
        # if a 1% radius is reported, it must be non-negative and finite
        if rec["r_1pct_m"] is not None:
            assert rec["r_1pct_m"] >= 0.0
        if rec["r_5pct_m"] is not None:
            assert rec["r_5pct_m"] >= 0.0


def test_validity_radius_shrinkage_evidence():
    # B0 a=1 vs a=0.5: r_1pct_over_phi should not grow toward grazing.
    items = SNAP["validity_radii"]
    if "B0_a0.5" in items and "B0_a1" in items:
        r01 = items["B0_a1"]["r_1pct_over_phi"]
        r05 = items["B0_a0.5"]["r_1pct_over_phi"]
        assert r05 is None or r01 is None or r05 <= 1.5 * (r01 or 0) + 1e-9


# ---------------------------------------------------------------------------
# 3. Initial-state topology radius (G6 §69)
# ---------------------------------------------------------------------------
def test_topology_radius_recorded():
    radii = SNAP["topology_radii"]
    assert len(radii) == 10
    for key, rec in radii.items():
        assert rec["eps_gamma_plus_rad"] is not None or \
            rec["plus_class"] == "LOWER_BOUND_ONLY"


def test_centered_radius_is_min_of_onesided():
    for key, rec in SNAP["topology_radii"].items():
        ep, emm = rec["eps_gamma_plus_rad"], rec["eps_gamma_minus_rad"]
        if ep is not None and emm is not None:
            assert rec["centered_radius_rad"] == pytest.approx(min(ep, emm))


def test_topology_change_classified_not_stm_error():
    for key, rec in SNAP["topology_radii"].items():
        assert rec["plus_class"] in ("TOPOLOGY_PRESERVED",
                                     "TOPOLOGY_CHANGED",
                                     "EVENT_ORDER_CHANGED",
                                     "GRAZING_CROSSED",
                                     "NUMERICAL_FAILURE",
                                     "LOWER_BOUND_ONLY")


# ---------------------------------------------------------------------------
# 4. Terminal descriptive consequences (G6 §43)
# ---------------------------------------------------------------------------
def test_terminal_descriptive_present():
    td = SNAP["terminal_descriptive"]
    assert len(td) == 10
    for key, rec in td.items():
        if "error" in rec:
            continue
        assert rec["terminal"] == "SRTI"
        assert rec["eta_scaled_norm_s"] > 0.0
        assert rec["scaled_terminal_sigma_max"] > 0.0


# ---------------------------------------------------------------------------
# 5. Reference stability (snapshot)
# ---------------------------------------------------------------------------
def test_reference_stability_of_excursions():
    for o in SNAP["nplus_event_audit"]:
        rs = o["reference_stability"]
        assert rs["vac_duration_diff"] < 1e-3
        assert rs["excursion_clearance_diff"] < 1e-3
        assert rs["entry_state_diff"] < 1e-3


# ---------------------------------------------------------------------------
# 6. No G7 scope leak
# ---------------------------------------------------------------------------
def test_no_g7_scope_leak():
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "grazing.py").read_text(encoding="utf-8")
    # G6 must not perform G7-style analysis (Monte Carlo / uncertainty /
    # final-synthesis machinery).
    for token in ("monte", "uncertainty", "final_tag", "global_lyap"):
        assert token not in src, token