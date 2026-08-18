"""Phase-G5 fixed-time predictability metrics tests (G5 §58-§61).

Covers: scaled STM convention, unit-system invariance, SVD algebra
(reconstruction / orthogonality / dominant pair / sign canonicalization /
sigma ordering), FTLE formula + horizon guard, scale positivity, rank
tolerance, structural-singular condition handling (Qian post-Capture
rank deficiency), row/column interpretability, the A/B/C scale-sensitivity
audit, the canonical scientific scale freeze (Candidate A), the common
fixed horizons for Qian / Sanger (+ Sanger T900 descriptive), canonical
scale-key consistency, and reference (REF-0.1 vs REF-0.05) stability of
the primary endpoints.
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
from hyptraj.predictability import ftle, metrics as M
from hyptraj.predictability.ftle import (
    canonicalize_svd_signs,
    finite_time_metrics,
    numerical_rank,
    scaled_svd,
    unit_conversion_scaling_invariance,
)
from hyptraj.predictability.scaling import (
    CANONICAL_SCALE_NUMERIC_VALUES_FROZEN,
    CANONICAL_SCALE_NUMERIC_STATUS,
    SCALING_CANDIDATES,
    canonical_candidate,
    scaled_stm,
)
from hyptraj.predictability.stm import (
    stm_production_like_config,
    stm_strict_reference_config,
)
from hyptraj.analysis.comparison_validation import (
    REFERENCE_05_SOLVER_CONFIG,
    REFERENCE_SOLVER_CONFIG,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g5_predictability_metrics_v1.json").read_text(
        encoding="utf-8"
    ))

K = 3.0
STATE = ("r", "theta", "v", "gamma")

# Common fixed scientific horizons (G5 §19).
HORIZONS = {"T60": 60.0, "T120": 120.0, "T300": 300.0, "T600": 600.0}


@pytest.fixture(scope="module")
def base():
    env = EnvironmentParams()
    veh = VehicleParams()
    ini = InitialCondition()
    x0 = np.array([env.earth_radius + ini.altitude, ini.range_angle,
                   ini.velocity, np.deg2rad(ini.flight_path_angle_deg)])
    return env, veh, x0


@pytest.fixture(scope="module")
def fast_results(base):
    """Production-solver metrics at the common horizons (fast; signatures)."""
    env, veh, _ = base
    out = {}
    for model in ("qian", "sanger"):
        for htag, T in HORIZONS.items():
            out[(model, htag)] = M.compute_fixed_time_metrics(
                model, T, env, veh, K,
                research_solver=PRODUCTION_SOLVER_CONFIG,
                stm_solver=stm_production_like_config(), scale_key="A")
    out[("sanger", "T900")] = M.compute_fixed_time_metrics(
        "sanger", 900.0, env, veh, K,
        research_solver=PRODUCTION_SOLVER_CONFIG,
        stm_solver=stm_production_like_config(), scale_key="A")
    return out


# ---------------------------------------------------------------------------
# 1. Scaled STM convention + unit-system invariance (G5 §11)
# ---------------------------------------------------------------------------
def test_scaled_stm_convention_matches_g0():
    rng = np.random.default_rng(0)
    phi = rng.normal(size=(4, 4))
    S_A = canonical_candidate().scales
    # tilde_Phi = S^-1 Phi S (diagonal S), identity free.
    S_diag = np.diag([S_A[k] for k in STATE])
    expected = np.linalg.solve(S_diag, phi @ S_diag)
    assert np.allclose(scaled_stm(phi, S_A), expected)
    # Phi = I -> tilde_Phi = I
    assert np.allclose(scaled_stm(np.eye(4), S_A), np.eye(4))


def test_unit_system_invariance():
    rng = np.random.default_rng(1)
    phi = rng.normal(size=(4, 4))
    S_A = canonical_candidate().scales
    # m -> km, m/s -> km/s, rad unchanged
    D = np.array([1000.0, 1.0, 1000.0, 1.0])
    assert unit_conversion_scaling_invariance(phi, S_A, D)


# ---------------------------------------------------------------------------
# 2. SVD algebra (G5 §27, §14, §15, §16)
# ---------------------------------------------------------------------------
def test_svd_reconstruction_orthogonality():
    rng = np.random.default_rng(2)
    phi = rng.normal(size=(4, 4))
    S_A = canonical_candidate().scales
    scaled, u, sigma, v = scaled_svd(phi, S_A)
    assert np.allclose(u.T @ u, np.eye(4), atol=1e-12)
    assert np.allclose(v.T @ v, np.eye(4), atol=1e-12)
    assert np.allclose(u @ np.diag(sigma) @ v.T, scaled, atol=1e-12)
    # sigma is sorted descending
    assert np.all(np.diff(sigma) <= 0)


def test_dominant_singular_pair_identity():
    rng = np.random.default_rng(3)
    phi = rng.normal(size=(4, 4))
    S_A = canonical_candidate().scales
    scaled, u, sigma, v = scaled_svd(phi, S_A)
    assert np.allclose(scaled @ v[:, 0], sigma[0] * u[:, 0], atol=1e-12)


def test_svd_sign_canonicalization_deterministic():
    rng = np.random.default_rng(4)
    v = rng.normal(size=(4, 4))
    u = rng.normal(size=(4, 4))
    for _ in range(3):
        u1, v1 = canonicalize_svd_signs(u.copy(), v.copy())
        u2, v2 = canonicalize_svd_signs(u.copy(), v.copy())
        assert np.array_equal(u1, u2)
        assert np.array_equal(v1, v2)
    # largest-magnitude component of each v column >= 0
    u_, v_ = canonicalize_svd_signs(u.copy(), v.copy())
    for i in range(4):
        k = int(np.argmax(np.abs(v_[:, i])))
        assert v_[k, i] >= 0.0


def test_ftle_formula_and_horizon_guard():
    S_A = canonical_candidate().scales
    ident = scaled_stm(np.eye(4), S_A)
    for T in (60.0, 300.0, 600.0):
        assert ftle.finite_time_lyapunov_exponent(ident, T) == pytest.approx(0.0)
    phi2 = np.diag([2.0, 1.0, 1.0, 1.0])
    lam = finite_time_metrics(phi2, S_A, 10.0)["lambda_max"]
    assert lam == pytest.approx(np.log(2.0) / 10.0, abs=1e-12)
    with pytest.raises(ValueError):
        ftle.finite_time_lyapunov_exponent(np.eye(4), 0.0)


def test_scale_values_positive():
    scales = canonical_candidate().scales
    for k in STATE:
        assert scales[k] > 0.0


def test_numerical_rank_tolerance():
    # standard SVD rank tol: sigma_max * max(m,n) * eps_machine
    sv = np.array([1.0, 1e-8, 1e-9, 0.0])
    assert numerical_rank(sv) == 3  # 1e-9 ~ tol threshold (not grabbed)


def test_structural_singular_condition_handling():
    # A matrix with an exact zero row -> sigma_min = 0 -> STRUCTURAL_SINGULAR
    phi = np.array([[1.0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0],
                    [0, 0, 0, 0.0]])
    S_A = canonical_candidate().scales
    m = finite_time_metrics(phi, S_A, 600.0)
    assert m["condition_status"] == "STRUCTURAL_SINGULAR"
    assert m["condition_number"] is None
    assert m["nullity"] >= 1
    # rank deficiency comes from event/geometry, not "chaos" or "perfect
    # stability" -- verified structurally only.


# ---------------------------------------------------------------------------
# 3. Canonical scale freeze (G5 §10)
# ---------------------------------------------------------------------------
def test_canonical_scale_frozen_and_key():
    assert CANONICAL_SCALE_NUMERIC_STATUS == CANONICAL_SCALE_NUMERIC_VALUES_FROZEN
    assert canonical_candidate().key == "A"
    decision = SNAPSHOT["canonical_scaling_decision"]
    assert decision["decision"] == "FROZEN"
    assert decision["canonical_key"] == "A"
    assert decision["status_flag"] == "CANONICAL_SCALE_NUMERIC_VALUES_FROZEN"


def test_scale_audit_generated_all_finite():
    for tag, s in SNAPSHOT["scale_audit"].items():
        for k in ("A", "B", "C"):
            assert np.isfinite(s[k]["sigma_max"]), (tag, k)
            assert s[k]["rank"] in (3, 4)


def test_raw_dimensional_singular_values_tagged_anti_example():
    # raw dimensional singular values are stored only under the explicit
    # ANTI_EXAMPLE tag (never used for scientific ranking).
    for tag, s in SNAPSHOT["scale_audit"].items():
        assert "raw_sigma_ANTI_EXAMPLE" in s["A"]


# ---------------------------------------------------------------------------
# 4. Common fixed horizons (real hybrid STMs; production fast path)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("model,htag,expected_sig", [
    ("qian", "T60", ()),
    ("qian", "T120", ("qian_capture",)),
    ("qian", "T300", ("qian_capture",)),
    ("qian", "T600", ("qian_capture",)),
    ("sanger", "T60", ()),
    ("sanger", "T120", ()),
    ("sanger", "T300", ("sanger_atmosphere_exit",)),
    ("sanger", "T600", ("sanger_atmosphere_exit",
                        "sanger_atmosphere_entry")),
    ("sanger", "T900", ("sanger_atmosphere_exit", "sanger_atmosphere_entry",
                        "sanger_atmosphere_exit", "sanger_atmosphere_entry")),
])
def test_common_horizon_signatures(fast_results, model, htag, expected_sig):
    r = fast_results[(model, htag)]
    assert tuple(r.topology_signature) == tuple(expected_sig), (model, htag)
    assert r.scale_key == "A"  # canonical scale applied identically
    assert r.sigma_max > 0.0
    assert r.lambda_max == pytest.approx(np.log(r.sigma_max) / r.horizon_s)


def test_qian_post_capture_rank_deficiency(fast_results):
    # before capture rank 4 finite; after capture rank 3 structural singular
    t60 = fast_results[("qian", "T60")]
    assert t60.topology_signature == ()
    assert t60.numerical_rank == 4
    assert t60.condition_status == "FINITE"
    t600 = fast_results[("qian", "T600")]
    assert t600.topology_signature == ("qian_capture",)
    assert t600.numerical_rank == 3
    assert t600.condition_status == "STRUCTURAL_SINGULAR"


def test_row_column_interpretability(fast_results):
    r = fast_results[("sanger", "T600")]
    assert len(r.scaled_column_norms) == 4
    assert len(r.scaled_row_norms) == 4
    assert all(np.isfinite(r.scaled_column_norms))
    assert r.svd_reconstruction_error < 1e-12


# ---------------------------------------------------------------------------
# 5. Reference stability (REF-0.1 vs REF-0.05) on primary endpoints
# ---------------------------------------------------------------------------
def test_reference_metric_self_stability():
    for tag, v in SNAPSHOT["reference_stability"].items():
        assert v["status"] == "PASS", tag
        assert v["v1_alignment"] > 0.99
        assert v["u1_alignment"] > 0.99
        assert v["sigma_max_diff"] < 1e-6


def test_snapshot_schema_and_constants():
    assert SNAPSHOT["schema_version"] == "phase-g5-predictability-metrics-v1"
    assert SNAPSHOT["state_order"] == ["r", "theta", "v", "gamma"]
    assert SNAPSHOT["grazing_anchors_excluded"] is True
    assert SNAPSHOT["grazing_threshold"] is None
    assert SNAPSHOT["common_horizons_s"] == [60.0, 120.0, 300.0, 600.0]
    assert SNAPSHOT["native_terminal_comparison_warning"].startswith(
        "Qian RTI and Sanger SRTI")


def test_scale_sensitivity_conclusion_documented():
    decision = SNAPSHOT["canonical_scaling_decision"]
    assert "SCALE-SENSITIVE" in decision["scale_sensitivity_note"]


def test_no_g6_scope_leak():
    src_root = Path(__file__).resolve().parents[2] / "src" / "hyptraj" / "predictability"
    for mod in ("ftle", "metrics"):
        src = (src_root / f"{mod}.py").read_text(encoding="utf-8")
        for token in ("grazing_threshold", "B0", "B4", "anchor"):
            assert token not in src, (mod, token)
    assert (src_root / "observability.py").read_text(encoding="utf-8").strip() == ""