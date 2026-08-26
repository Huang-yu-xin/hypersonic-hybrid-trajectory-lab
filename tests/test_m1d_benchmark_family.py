"""M1-D benchmark family unit tests (candidate generation layer, D1).

Anchors the estimator physics BEFORE any benchmark freeze:

- deterministic candidate generation (SeedSequence-driven);
- label partition / frozen-style precedence;
- stratified-IS reference estimators against CLOSED FORM physics
  (axis-separated linear caps: P(A_k) = 1 - Phi(h_k),
   L_k(q0) = exp(||m||^2) * (1 - Phi(h_k + m.n_k));
   overlaps between axis-cap pairs are quadratic-tail small at the chosen
   thresholds and covered by the stated tolerances);
- eligibility logic E1-E6 on synthetic tables.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from hyptraj.m1d.benchmark_family import (
    DIM,
    MODE_IDS,
    NOMINAL,
    OFFSET_O_RANGE,
    BenchmarkConfig,
    compute_eligibility,
    generate_candidate_pool,
    reference_characterize,
)


def _axis_config() -> BenchmarkConfig:
    """Crafted config: 4 axis directions, high thresholds -> overlap slivers
    carry <1e-4 mass so closed-form anchors hold to stated tolerances."""
    return BenchmarkConfig(
        config_id="m1d_test_axis",
        batch_seed=20260827,
        batch_index=999,
        theta_deg=(180.0, 0.0, 90.0, 270.0),
        h=(1.6, 2.4, 2.4, 2.4),
        curved=(False, False, False, False),
        curvature_c=0.35,
        offset_o=(0.0, 0.0, 0.0, 0.0),
    )


def _me(mode, mid):
    return mode[mid]


# ---------------------------------------------------------------------------
# generation determinism + structure
# ---------------------------------------------------------------------------
def test_pool_deterministic_bitwise():
    p1 = generate_candidate_pool(20260827, 8)
    p2 = generate_candidate_pool(20260827, 8)
    assert [c.params_dict() for c in p1] == [c.params_dict() for c in p2]
    assert [c.config_id for c in p1] == [c.config_id for c in p2]

    p3 = generate_candidate_pool(20260828, 8)
    assert [c.params_dict() for c in p1] != [c.params_dict() for c in p3]


def test_pool_structure_and_separation():
    pool = generate_candidate_pool(20260827, 16)
    for c in pool:
        assert len(c.theta_deg) == len(MODE_IDS)
        assert len(c.h) == len(MODE_IDS)
        assert len(c.curved) == len(MODE_IDS)
        assert len(c.offset_o) == len(MODE_IDS)      # regression: was 3-tuple
        assert c.h[0] == c.h[0]                      # finite float sanity
        th = np.asarray(c.theta_deg)
        for i in range(4):
            for j in range(i + 1, 4):
                d = abs(th[i] - th[j]) % 360.0
                d = min(d, 360.0 - d)
                assert d >= 39.999 or d <= 0.001     # sep rule (fallback -10 grace never binds here)
            if i == 0:
                assert not c.curved[i]               # primary always linear
                assert c.offset_o[i] == 0.0
            elif c.curved[i]:
                assert OFFSET_O_RANGE[0] <= c.offset_o[i] <= OFFSET_O_RANGE[1]


def test_all_curved_end_to_end_reference():
    """Regression: exercise the curved-apex stratum path incl. S4 curved."""
    cfg = BenchmarkConfig(
        config_id="m1d_test_allcurved",
        batch_seed=20260827,
        batch_index=998,
        theta_deg=(180.0, 20.0, 140.0, 260.0),
        h=(1.7, 2.1, 1.9, 2.3),
        curved=(False, True, True, True),
        curvature_c=0.35,
        offset_o=(0.0, 0.6, -0.8, 0.5),
    )
    rec = reference_characterize(cfg, n_reference=40_000, bootstrap_reps=10)
    for mid in MODE_IDS[1:]:
        m = rec["modes"][mid]
        assert m["raw_count"] > 0, mid               # every apex stratum hits
        assert np.isfinite(m["L_ref"]) and m["L_ref"] > 0.0
    # sanity: curved sets are subsets of their linear caps -> P <= 1-Phi(h)
    from scipy.stats import norm as _norm
    for k, mid in enumerate(MODE_IDS):
        if mid == MODE_IDS[0]:
            continue
        assert rec["modes"][mid]["P_ref"] <= _norm.sf(cfg.h[k]) * 1.05


# ---------------------------------------------------------------------------
# labels / geometry
# ---------------------------------------------------------------------------
def test_label_partition_and_precedence():
    cfg = _axis_config()
    z = np.array([
        [0.0, 0.0],       # nominal
        [-3.0, 0.0],      # S1 only (primary dir 180deg)
        [3.0, 0.0],       # S2 (dir 0deg) -- also satisfies nothing else
        [0.0, 3.0],       # S3
        [0.0, -3.0],      # S4
        [3.0, 3.0],       # both S2&S3 true -> later index wins -> S3
    ])
    lab = cfg.label(z)
    assert list(lab) == ["S0", "S1", "S2", "S3", "S4", "S3"]
    assert set(np.unique(lab)) <= {NOMINAL, *MODE_IDS}


def test_initial_proposal_is_single_primary_component():
    cfg = _axis_config()
    q0 = cfg.initial_proposal()
    assert q0.n_components == 1
    np.testing.assert_allclose(q0.centers[0], cfg.primary_z_star)
    np.testing.assert_allclose(q0.centers[0], [-1.6, 0.0], atol=1e-12)
    assert q0.component_mode_ids == ("S1",)


# ---------------------------------------------------------------------------
# estimator physics vs closed form (axis separated linear caps)
# ---------------------------------------------------------------------------
@pytest.mark.filterwarnings("ignore")
def test_reference_estimators_match_closed_form():
    cfg = _axis_config()
    rec = reference_characterize(cfg, n_reference=240_000,
                                 bootstrap_reps=60)

    zstar = cfg.primary_z_star
    m_norm2 = float(zstar @ zstar)
    for k, mid in enumerate(MODE_IDS):
        if mid == MODE_IDS[0]:
            continue
        m = rec["modes"][mid]
        shift = float(zstar @ cfg.normals[k])
        ana_p = float(norm.sf(cfg.h[k]))
        ana_l = float(np.exp(m_norm2) * norm.sf(cfg.h[k] + shift))

        # IS estimate vs closed form (tolerance covers MC/IS noise + the
        # <1e-4-mass overlap slivers this config deliberately leaves open)
        assert abs(m["P_ref"] - ana_p) / ana_p < 0.06, (mid, "P", m, ana_p)
        l_rel = abs(m["L_ref"] - ana_l) / max(ana_l, 1e-300)
        assert l_rel < 0.08, (mid, "L", m["L_ref"], ana_l)

        # independent plain-MC cross-check agrees within generous noise band
        mc = m["P_ref_mc_crosscheck"]
        assert abs(mc - ana_p) / ana_p < 0.15, (mid, "MC-crosscheck")

        # diagnostic analytic column mirrors hand formula for linear caps
        assert abs(m["analytic_P"] - ana_p) < 1e-12
        assert abs(m["analytic_L"] - ana_l) < 1e-9


def test_bootstrap_cis_cover_point_estimates():
    cfg = _axis_config()
    rec = reference_characterize(cfg, n_reference=120_000, bootstrap_reps=50)
    for mid in MODE_IDS[1:]:
        lo, hi = rec["bootstrap_ci"]["P"][mid]
        assert lo <= rec["modes"][mid]["P_ref"] * 1.2 + 1e-9
        assert hi >= rec["modes"][mid]["P_ref"] * 0.8 - 1e-9


# ---------------------------------------------------------------------------
# eligibility logic (synthetic tables -- task Sec. 11 verbatim conditions)
# ---------------------------------------------------------------------------
def _tbl(P, L):
    keys = ["S2", "S3", "S4"]
    out = {}
    for k, p, l in zip(keys, P, L):
        out[k] = {"P_ref": p, "L_ref": l}
    return out


def test_eligibility_full_pass():
    # engineered: top-1 conflict + strong inversion A=S2/B=S3 +
    # omega_top(L) in [0.35, 0.90]
    P = [0.050, 0.030, 0.002]
    L = [0.100, 0.600, 0.050]      # omega_S3 = .60/.75 = .80
    e = compute_eligibility(_tbl(P, L), alpha_p=0.5, pilot_n=20_000)
    assert e["k_P_star"] == "S2" and e["k_V_star"] == "S3"
    for key in ("E1_K_missing_ge3", "E2_observability", "E3_top_rank_conflict",
                "E4_strong_inversion", "E5_variance_criticality",
                "E6_no_degenerate_domination"):
        assert e[key], key
    assert e["eligible"]
    inv = {(i["a"], i["b"]) for i in e["pairwise_inversions"]}
    assert ("S2", "S3") in inv
    si = e["strongest_inversion"]
    assert si["ratio_P"] >= 1.5 and si["ratio_L"] >= 1.5


def test_eligibility_individual_failures():
    base_P = [0.050, 0.030, 0.002]
    base_L = [0.100, 0.600, 0.050]
    kw = dict(alpha_p=0.5, pilot_n=20_000)

    # E3 fails: same top for both rankings
    P = [0.600, 0.300, 0.002]
    L = [0.700, 0.050, 0.020]                       # omega_top=.91>0.90
    e = compute_eligibility(_tbl(P, L), **kw)
    assert not e["E3_top_rank_conflict"]
    assert not e["E6_no_degenerate_domination"]

    # E4 fails: inversion exists but ratios below 1.5
    P = [0.050, 0.040, 0.002]
    L = [0.100, 0.130, 0.010]                        # omega_top .593
    e = compute_eligibility(_tbl(P, L), **kw)
    assert e["E3_top_rank_conflict"]
    assert not e["E4_strong_inversion"]

    # E5 fails: balanced variance masses -> top share just below floor
    P = [0.050, 0.030, 0.002]
    L = [1.000, 0.980, 0.970]
    e = compute_eligibility(_tbl(P, L), **kw)
    assert e["omega_top_missing"] == pytest.approx(1.0 / 2.95, abs=1e-9)
    assert not e["E5_variance_criticality"]

    # E2 fails: deep unobservable mode
    P = [0.050, 0.030, 0.0008]
    L = [0.100, 0.400, 0.250]
    e = compute_eligibility(_tbl(P, L), **kw)
    assert not e["E2_observability"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
