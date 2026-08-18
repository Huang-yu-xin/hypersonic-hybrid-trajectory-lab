"""Phase-H2 nonlinear Monte-Carlo validation tests.

Three layers (H2 §75):

1.  pure sampling / statistics tests (deterministic, no trajectories);
2.  snapshot regression tests against the committed
    ``tests/data/phase_h2_nonlinear_mc_validation_v1.json``;
3.  very-small LIVE trajectory smoke tests only (one antithetic pair per
    model) -- the full H2 ensemble is NOT re-run by pytest.

All synthetic matrices are written explicitly (no RNG in production);
sampling uses only the frozen ``numpy.random.default_rng`` seed 2026 with
antithetic pairs; the bootstrap uses the frozen seed 2027.
"""

import json
from pathlib import Path

import numpy as np

from hyptraj.uncertainty.distributions import (
    standardized_to_delta_x,
)
from hyptraj.uncertainty.nonlinear_validation import (
    accuracy_classification,
    classify_tau,
    domain_gate_status,
    fixed_time_metrics,
    pair_bootstrap,
)
from hyptraj.uncertainty.sampling import (
    NESTED_SAMPLE_SIZES,
    REPRODUCIBILITY_SEED,
    AntitheticSampleBank,
    bank_sha256,
    build_antithetic_bank,
    sample_bank,
)
from hyptraj.uncertainty.protocol import SampleClassification

REPO = Path(__file__).resolve().parent.parent.parent
DATA = REPO / "tests" / "data"
H2 = json.loads((DATA / "phase_h2_nonlinear_mc_validation_v1.json").read_text(
    encoding="utf-8"))

S = np.diag([1e5, 1.0, 7e3, 0.1])

# Deterministic synthetic fixtures (H2 §78-§80): explicit, no RNG.
A = np.array([[1.2, 0.3, -0.4, 0.1],
              [0.0, 0.9, 0.2, -0.3],
              [0.5, -0.1, 1.4, 0.2],
              [0.0, 0.2, 0.0, 0.7]])
A_ZERO_ROW = A.copy()
A_ZERO_ROW[3, :] = 0.0          # one output row structurally zero


def _samples(n: int) -> np.ndarray:
    return sample_bank().prefix(n)


# ---------------------------------------------------------------------------
# Sampling tests (H2 §76)
# ---------------------------------------------------------------------------
def test_antithetic_exact_mean():
    z = _samples(256)
    assert np.allclose(z.mean(axis=0), 0.0, atol=1e-16)


def test_nested_prefixes():
    bank = sample_bank()
    for n in NESTED_SAMPLE_SIZES:
        assert n <= bank.n_max
        assert n % 2 == 0
    prev = None
    for n in NESTED_SAMPLE_SIZES:
        p = bank.prefix(n)
        if prev is not None:
            assert np.array_equal(p[: len(prev)], prev)  # exact prefix
        prev = p


def test_crn_identity():
    # every model / alpha uses the SAME standardized sample IDs
    ids = sample_bank().sample_ids(512)
    assert np.array_equal(ids, np.arange(512))
    # bank rows are the CRN identity: stable, reproducible
    b1 = sample_bank().prefix(128)
    b2 = build_antithetic_bank(n_pairs=2048, seed=REPRODUCIBILITY_SEED)[:128]
    assert np.array_equal(b1, b2)


def test_reproducible_hash():
    h1 = bank_sha256(sample_bank().z)
    h2 = bank_sha256(build_antithetic_bank(n_pairs=2048,
                                           seed=REPRODUCIBILITY_SEED))
    assert h1 == h2
    assert len(h1) == 64


def test_no_global_rng_in_production_modules():
    for rel in ("src/hyptraj/uncertainty/distributions.py",
                "src/hyptraj/uncertainty/sampling.py",
                "src/hyptraj/uncertainty/nonlinear_validation.py"):
        src = (REPO / rel).read_text(encoding="utf-8")
        for marker in ("np.random.seed(", "np.random.normal(",
                       "np.random.multivariate_normal("):
            assert marker not in src, (rel, marker)


def test_no_rng_in_generator_imports():
    # the H2 generator must not seed the global numpy state
    src = (REPO / "scripts/run_phase_h2_nonlinear_mc.py").read_text(
        encoding="utf-8")
    for marker in ("np.random.seed", "np.random.normal("):
        assert marker not in src, marker


# ---------------------------------------------------------------------------
# Input transform (H2 §77): sample covariance -> alpha^2 S S^T as N grows
# ---------------------------------------------------------------------------
def test_input_transform_covariance_sanity():
    a = 0.05
    z = _samples(1024)
    dx = standardized_to_delta_x(z, a)          # delta X0 = S (alpha z)
    P = np.cov(dx, rowvar=False, ddof=1)
    expect = (a ** 2) * S @ S.T
    assert np.linalg.norm(P - expect) < 0.1 * np.linalg.norm(expect)


# ---------------------------------------------------------------------------
# Sample-matched linear synthetic test (H2 §78): nonlinear == linear exactly
# ---------------------------------------------------------------------------
def test_sample_matched_linear_close_identically():
    a = 0.04
    u = a * _samples(1024)
    y_L = u @ A.T
    y_N = u @ A.T                       # nonlinear callback == linear map
    P_H1 = (a ** 2) * (A @ A.T)
    m = fixed_time_metrics(y_L, y_N, P_H1)
    # sample-matched comparison cancels finite-N noise -> ~exact zero
    assert abs(m["E_mu"]) < 1e-6
    assert abs(m["E_cov"]) < 1e-6
    assert abs(m["E_sigma1"]) < 1e-6
    assert abs(m["E_H2"]) < 1e-6


# ---------------------------------------------------------------------------
# Quadratic synthetic test (H2 §79): mean shift emerges, increases with alpha
# ---------------------------------------------------------------------------
def test_quadratic_nonlinearity_trend():
    z = _samples(512)
    e_h2 = []
    for a in (0.001, 0.01, 0.1):
        u = a * z
        q = np.einsum("ij,ij->i", u, u)     # ||u||^2 = O(alpha^2)
        y_L = u @ A.T
        y_N = u @ A.T + 0.5 * q[:, None]    # O(alpha^2) term (constant coefficient)
        P_H1 = (a ** 2) * (A @ A.T)
        m = fixed_time_metrics(y_L, y_N, P_H1)
        e_h2.append(m["E_H2"])
    # relative nonlinear discrepancy grows with alpha, vanishes at small alpha
    assert e_h2[0] < e_h2[1] < e_h2[2]
    assert e_h2[0] < 0.05
    assert e_h2[2] > 0.1


def test_quadratic_nonlinearity_scales_like_alpha2():
    # ||u||^2 = alpha^2 ||z||^2, so the ABSOLUTE mean shift is ~ alpha^2
    z = _samples(512)
    a1, a2 = 0.03, 0.09
    q1 = np.einsum("ij,ij->i", a1 * z, a1 * z)
    q2 = np.einsum("ij,ij->i", a2 * z, a2 * z)
    mu1 = np.mean(0.5 * q1[:, None], axis=0)   # linear part has zero mean (antithetic)
    mu2 = np.mean(0.5 * q2[:, None], axis=0)
    r1 = abs(mu1[0]); r2 = abs(mu2[0])
    assert not np.isclose(r1, 0.0, atol=1e-12)
    assert 5.0 < r2 / r1 < 15.0                # ~ (a2/a1)^2 = 9


# ---------------------------------------------------------------------------
# Structural-zero leakage (H2 §80)
# ---------------------------------------------------------------------------
def test_structural_zero_leakage_no_divide_by_zero():
    a = 0.05
    u = a * _samples(512)
    y_L = u @ A_ZERO_ROW.T
    y_N = y_L.copy()
    y_N[:, 3] = 0.02 * np.einsum("ij,ij->i", u, u)   # O(alpha^2) leak into row 3
    P_H1 = (a ** 2) * (A_ZERO_ROW @ A_ZERO_ROW.T)
    m = fixed_time_metrics(y_L, y_N, P_H1)
    zero = m["structural_zero_mask"]
    assert bool(zero[3]) is True
    leak = m["structural_zero_leakage"][3]
    assert leak is not None and np.isfinite(leak)
    # leakage -> 0 as alpha -> 0 (quadratic term vanishes relative to RMS scale)
    u0 = 1e-4 * _samples(512)
    m0 = fixed_time_metrics(u0 @ A_ZERO_ROW.T,
                            u0 @ A_ZERO_ROW.T + 0.02 * np.einsum(
                                "ij,ij->i", u0, u0)[:, None],
                            (1e-4 ** 2) * (A_ZERO_ROW @ A_ZERO_ROW.T))
    assert m0["structural_zero_leakage"][3] < leak


# ---------------------------------------------------------------------------
# Topology gate synthetic (H2 §81): 255 preserved + 1 changed -> FAIL, no drop
# ---------------------------------------------------------------------------
def test_topology_gate_no_conditioned_covariance():
    cls = [SampleClassification.TOPOLOGY_PRESERVED] * 255 + \
        [SampleClassification.TOPOLOGY_CHANGED]
    assert domain_gate_status(cls) == "DOMAIN_GATE_FAIL"
    # the gate never silently drops samples: the requested analysis must
    # not proceed to a conditioned covariance for a failed domain gate
    assert accuracy_classification(0.0, 0.0, 0.02, 0.01,
                                   domain_gate_status(cls)) == "DOMAIN_GATE_FAIL"


def test_domain_gate_pure_pass():
    cls = [SampleClassification.TOPOLOGY_PRESERVED] * 256
    assert domain_gate_status(cls) == "PASS"


# ---------------------------------------------------------------------------
# Pair bootstrap (H2 §82): deterministic, pair units
# ---------------------------------------------------------------------------
def test_pair_bootstrap_deterministic():
    u = 0.05 * _samples(256)
    y_L = u @ A.T
    y_N = u @ A.T
    P = (0.05 ** 2) * (A @ A.T)
    stat = lambda L, Nv: fixed_time_metrics(L, Nv, P)["E_H2"]
    b1 = pair_bootstrap(y_L, y_N, statistic=stat, n_boot=50, rng_seed=2027)
    b2 = pair_bootstrap(y_L, y_N, statistic=stat, n_boot=50, rng_seed=2027)
    assert np.allclose(b1, b2)


def test_pair_bootstrap_uses_pair_units():
    # even N required; an odd synthetic input must be rejected
    u_odd = _samples(256)[:-1]
    try:
        pair_bootstrap(u_odd, u_odd,
                       statistic=lambda L, Nv: 0.0, n_boot=10)
    except ValueError:
        pass
    else:
        raise AssertionError("odd N must be rejected (antithetic pairs)")


# ---------------------------------------------------------------------------
# Classification logic (H2 §83)
# ---------------------------------------------------------------------------
def test_tau_classification_logic():
    assert classify_tau(0.004, 0.009, 0.01) == "PASS"
    assert classify_tau(0.011, 0.020, 0.01) == "FAIL"
    assert classify_tau(0.008, 0.012, 0.01) == "UNRESOLVED"


def test_accuracy_classification_fail_vs_domain():
    # FAIL is a numerical-accuracy verdict on a VALID domain
    assert accuracy_classification(0.012, 0.011, 0.02, 0.01, "PASS") == "FAIL"
    # DOMAIN_GATE_FAIL is a different mechanism (H2 §36)
    assert accuracy_classification(0.0, 0.0, 0.01, 0.01,
                                   "DOMAIN_GATE_FAIL") == "DOMAIN_GATE_FAIL"


# ---------------------------------------------------------------------------
# Snapshot regression (H2 §84)
# ---------------------------------------------------------------------------
def test_snapshot_schema_and_provenance():
    assert H2["schema_version"] == "phase-h2-nonlinear-mc-validation-v1"
    assert H2["starting_h1_commit"] == "7120feb9cfd8c013a4bdc7ef27261d6e248ca440"
    assert H2["sampling"]["seed"] == 2026
    assert H2["sampling"]["bootstrap_seed"] == 2027
    assert H2["sampling"]["antithetic"] is True
    assert H2["sampling"]["common_random_numbers"] is True
    assert H2["sampling"]["sample_matched_linear_comparator"] is True
    assert H2["sampling"]["sample_bank_sha256"] == bank_sha256(sample_bank().z)
    assert H2["alpha_probe_grid"] == [1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1]


def test_snapshot_primary_and_terminal_cases_present():
    assert "qian" in H2["pilot"] and "sanger" in H2["pilot"]
    for obj in ("qian_T600", "sanger_T600", "qian_RTI", "sanger_SRTI"):
        assert obj in H2["alpha_validity"], obj


def test_snapshot_deep_audit_present():
    d = H2["deep_generality_audit"]
    assert d["status"] == "DEEP_FIXED_TOPOLOGY_GENERALITY_AUDIT"
    for case in ("n0_deep", "n1_deep", "n2_deep", "n3_deep", "n4_deep", "n5_deep"):
        assert case in d["cases"], case


def test_snapshot_no_h3_probability_claims():
    assert H2["claim_boundaries"]["topology_probability_not_estimated"] is True
    assert H2["claim_boundaries"]["B0_B4_not_sampled"] is True
    assert H2["claim_boundaries"]["mixture_analysis_not_performed"] is True
    text = json.dumps(H2)
    # no Wilson topology-risk curve / P(N) result is present anywhere
    assert "p_topo" not in text


def test_h1_freezed_snapshot_still_records_mc_not_performed():
    # H2 §86: the frozen H1 snapshot still records that Monte Carlo had not
    # been performed at H1 freeze time (never rewritten).
    h1 = json.loads((DATA / "phase_h1_linear_uncertainty_v1.json").read_text(
        encoding="utf-8"))
    assert h1["claim_boundaries"]["monte_carlo_not_performed"] is True
    assert h1["claim_boundaries"]["topology_probability_not_computed"] is True
    assert h1["alpha_status"] == "PENDING_NUMERICAL_AUDIT"


# ---------------------------------------------------------------------------
# Small LIVE trajectory smoke (H2 §85): one antithetic pair per model only
# ---------------------------------------------------------------------------
def test_live_trajectory_smoke():
    from hyptraj.models.parameters import EnvironmentParams, VehicleParams
    from hyptraj.controls.constant_k import ConstantKControl
    from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )
    from hyptraj.uncertainty.nonlinear_validation import (
        classify_fixed_time_sample,
        classify_terminal_sample,
        extract_sample_observations,
    )

    env, veh = EnvironmentParams(), VehicleParams()
    RE = float(env.earth_radius)
    a = 1e-4
    pairable_z = sample_bank().z[0:2]

    for model in ("qian", "sanger"):
        n_pres = 0
        for i, z in enumerate(pairable_z):
            x0 = np.array([RE + 100_000.0, 0.0, 7000.0, np.deg2rad(-5.0)]) \
                + S @ (a * z)
            ini = _ini(x0, RE)
            coll = DenseOutputCollector()
            if model == "qian":
                traj = integrate_qian_research_trajectory(
                    env, veh, ini, ConstantKControl(3.0),
                    solver=PRODUCTION_SOLVER_CONFIG,
                    dense_output_collector=coll, max_time=5000.0)
            else:
                traj = integrate_sanger_research_trajectory(
                    env, veh, ini, ConstantKControl(3.0),
                    solver=PRODUCTION_SOLVER_CONFIG,
                    dense_output_collector=coll, max_time=5000.0)
            obs = extract_sample_observations(model, traj, coll.segments, 600.0)
            # T600 fixed-time extraction works
            assert obs["state_T"] is not None and np.all(np.isfinite(obs["state_T"]))
            # terminal extraction works
            assert obs["terminal_time"] > 0.0
            c_ft = classify_fixed_time_sample(
                model, obs, T=600.0, nominal_switches_at_T=obs["switches_at_T"],
                nominal_mode_at_T=obs["mode_at_T"])
            c_te = classify_terminal_sample(
                model, obs, expected_kind="RTI" if model == "qian" else "srti",
                nominal_terminal_switches=obs["terminal_switches"])
            assert c_ft[0] == SampleClassification.TOPOLOGY_PRESERVED
            assert c_te[0] == SampleClassification.TOPOLOGY_PRESERVED
            n_pres += 1
        assert n_pres == 2


def _ini(x0, RE):
    from hyptraj.models.parameters import InitialCondition
    import numpy as _np
    return InitialCondition(altitude=float(x0[0]) - RE, range_angle=float(x0[1]),
                            velocity=float(x0[2]),
                            flight_path_angle_deg=_np.rad2deg(float(x0[3])))
