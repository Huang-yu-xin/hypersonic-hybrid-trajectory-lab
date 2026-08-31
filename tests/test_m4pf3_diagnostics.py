import hashlib
import json
from pathlib import Path

import numpy as np

from hyptraj.m4pf3.diagnostics import (
    allocation_diagnostics,
    birth_score,
    build_birth_candidates,
    coverage_diagnostics,
    gaussian_log_density,
    responsibility_matrix,
    routing_verdict,
)


REPO = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((
    REPO / "configs/phase_m4pf3_0/m4pf3_0_protocol.json"
).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture():
    x = np.asarray([[-2.0], [-0.5], [0.2], [1.0], [3.0]])
    alpha = np.asarray([0.6, 0.4])
    means = np.asarray([[-1.0], [1.0]])
    covariances = (np.asarray([[1.0]]), np.asarray([[0.7]]))
    responsibilities, logq = responsibility_matrix(
        x, alpha, means, covariances)
    mass = np.asarray([0.2, 1.0, 2.0, 4.0, 8.0])
    return x, alpha, means, covariances, responsibilities, logq, mass


def test_m4pf3_zero_simulator_calls_pf3_0():
    assert PROTOCOL["extra_simulator_calls"] == 0
    source_lock = json.loads((
        REPO / "configs/phase_m4pf3_0/m4pf3_0_source_lock.json"
    ).read_text(encoding="utf-8"))
    assert source_lock["simulator_calls_before_analysis"] == 0


def test_m4pf3_source_hashes():
    lock = json.loads((
        REPO / "configs/phase_m4pf3_0/m4pf3_0_source_lock.json"
    ).read_text(encoding="utf-8"))
    manifest_path = REPO / lock["manifest_path"]
    assert sha256(manifest_path) == lock["manifest_sha256_before_analysis"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_count"] == 36
    assert sum(row["role"] == "PF2 S0-anchor gradient archive"
               for row in manifest["sources"]) == 24
    for row in manifest["sources"]:
        assert sha256(REPO / row["path"]) == row["sha256"]


def test_m4pf3_logit_gradient_identity():
    _, alpha, _, _, responsibilities, _, mass = fixture()
    diagnostic = allocation_diagnostics(mass, responsibilities, alpha)
    expected = alpha - diagnostic["r_bar"]
    assert np.allclose(-diagnostic["descent_direction"], expected)


def test_m4pf3_logit_gradient_fd():
    x, alpha, means, covariances, _, _, mass = fixture()
    target = mass.copy()
    beta = np.log(alpha)

    def objective(local_beta):
        local_alpha = np.exp(local_beta - np.max(local_beta))
        local_alpha /= local_alpha.sum()
        _, logq = responsibility_matrix(x, local_alpha, means, covariances)
        return float(np.sum(target * np.exp(-logq)))

    responsibilities, _ = responsibility_matrix(x, alpha, means, covariances)
    tilted_mass = target * np.exp(-responsibility_matrix(
        x, alpha, means, covariances)[1])
    diagnostic = allocation_diagnostics(tilted_mass, responsibilities, alpha)
    m2 = objective(beta)
    analytic = m2 * (alpha - diagnostic["r_bar"])
    epsilon = 1e-6
    numeric = np.asarray([
        (objective(beta + epsilon * np.eye(2)[k])
         - objective(beta - epsilon * np.eye(2)[k])) / (2.0 * epsilon)
        for k in range(2)
    ])
    assert np.allclose(numeric, analytic, rtol=2e-6, atol=1e-7)


def test_m4pf3_allocation_gradient_sum_zero():
    _, alpha, _, _, responsibilities, _, mass = fixture()
    diagnostic = allocation_diagnostics(mass, responsibilities, alpha)
    assert abs(diagnostic["direction_sum"]) < 1e-12


def test_m4pf3_allocation_tv_bounds():
    _, alpha, _, _, responsibilities, _, mass = fixture()
    mismatch = allocation_diagnostics(mass, responsibilities, alpha)["A_alloc"]
    assert 0.0 <= mismatch <= 1.0


def test_m4pf3_responsibility_normalization():
    _, _, _, _, responsibilities, _, _ = fixture()
    assert np.allclose(responsibilities.sum(axis=1), 1.0)


def test_m4pf3_coverage_thresholds():
    x, _, means, covariances, _, _, mass = fixture()
    diagnostic, _, _ = coverage_diagnostics(
        x, mass, means, covariances, np.asarray([0, 0, 0, 1, 1]))
    assert diagnostic["tau99"] > 0.0
    assert diagnostic["tau999"] > diagnostic["tau99"]
    assert 0.0 <= diagnostic["U999"] <= diagnostic["U99"] <= 1.0


def test_m4pf3_tilted_mass_normalization():
    x, _, means, covariances, _, _, mass = fixture()
    diagnostic, _, _ = coverage_diagnostics(
        x, mass, means, covariances, np.arange(x.shape[0]))
    assert np.isclose(sum(diagnostic["nearest_component_tilted_mass"]), 1.0)
    assert np.isclose(sum(row["tilted_mass"]
                          for row in diagnostic["source_strata"]), 1.0)


def test_m4pf3_birth_derivative_identity():
    x, alpha, means, covariances, _, logq, mass = fixture()
    center = np.asarray([2.0])
    covariance = np.asarray([[0.8]])
    diagnostic = birth_score(x, mass, logq, center, covariance,
                             stream_count=1)
    ratio = np.exp(gaussian_log_density(x, center, covariance) - logq)
    expected = float(np.sum(mass / mass.sum() * ratio) - 1.0)
    assert np.isclose(diagnostic["birth_score"], expected)


def test_m4pf3_birth_score_fd():
    x, _, _, _, _, logq, mass = fixture()
    logg = gaussian_log_density(x, np.asarray([2.0]), np.asarray([[0.8]]))
    q = np.exp(logq)
    g = np.exp(logg)

    def objective(epsilon):
        return float(np.sum(mass * q / ((1.0 - epsilon) * q + epsilon * g)))

    epsilon = 1e-6
    numeric = (objective(epsilon) - objective(-epsilon)) / (2.0 * epsilon)
    score = float(np.sum(mass / mass.sum() * g / q) - 1.0)
    analytic = -objective(0.0) * score
    assert np.isclose(numeric, analytic, rtol=1e-6, atol=1e-7)


def test_m4pf3_candidate_covariance_not_descriptive_fit():
    rng = np.random.default_rng(44)
    samples = rng.normal(5.0, 0.1, size=(400, 1))
    mass = np.ones(400)
    identity = {
        "weights": [0.5, 0.5], "centers": [[0.0], [1.0]],
        "covariances": [[[1.0]], [[2.0]]],
    }
    coverage, d_min, _ = coverage_diagnostics(
        samples, mass, np.asarray(identity["centers"]),
        tuple(np.asarray(c) for c in identity["covariances"]),
        np.zeros(400, dtype=int))
    candidates = build_birth_candidates(
        samples, mass, np.zeros(400, dtype=int), identity, coverage, d_min,
        PROTOCOL)
    allowed = [np.asarray([[1.0]]), np.asarray([[2.0]])]
    assert candidates
    assert all(any(np.array_equal(row["covariance"], item) for item in allowed)
               for row in candidates)


def test_m4pf3_anchor_identity():
    assert "S0" in PROTOCOL["diagnostic_anchor"]
    assert PROTOCOL["intervention_anchor"] == "PF2 P11"
    assert PROTOCOL["p11_requires_fresh_construction"] is True


def test_m4pf3_schema_and_routing():
    rows = [{"A_alloc": 0.2, "U99": 0.3, "U999": 0.0,
             "top_1pct_uncovered_fraction": 0.0} for _ in range(24)]
    result = routing_verdict(rows, PROTOCOL)
    assert result["route"] == "C"
    assert {"A", "B", "C", "D"}.issubset(PROTOCOL["routing"])


def test_m4pf3_locked_output_schema():
    path = (REPO / "results/phase_m4pf3_0/summary"
            / "m4pf3_0_diagnostic_summary.json")
    if not path.exists():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["extra_simulator_calls"] == 0
    assert summary["state_count"] == 24
    assert summary["routing"]["route"] in {"A", "B", "C", "D"}
    assert summary["source_manifest_sha256_before"] == \
        summary["source_manifest_sha256_after"]
