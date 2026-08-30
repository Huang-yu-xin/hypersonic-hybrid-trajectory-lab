"""M4-PF0 matrix-gradient and zero-simulator tests."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np

from hyptraj.m3.gradient_estimator import scalar_gradient_estimate
from hyptraj.m4pf.gradient import (
    cancellation_score,
    directional_gradient,
    gaussian_log_covariance_gradient,
    log_covariance_directional_fd,
    matrix_gradient_estimate,
    rank_truncate,
    spectral_diagnostics,
    spd_log_covariance_update,
)

REPO = Path(__file__).resolve().parents[1]


def fixed_inputs():
    a = np.array([0.4, 1.2, 0.7, 1.8, 0.3, 0.9])
    resp = np.array([0.8, 0.3, 0.5, 0.9, 0.1, 0.6])
    z = np.array([
        [0.2, -0.7], [1.1, 0.4], [-0.5, 0.9],
        [0.8, -1.2], [0.1, 0.3], [-0.9, -0.2],
    ])
    return a, resp, z


def test_m4pf0_zero_simulator_calls():
    paths = list((REPO / "src" / "hyptraj" / "m4pf").glob("*.py")) + [
        REPO / "scripts" / "run_m4pf0_audit.py",
        REPO / "scripts" / "plot_m4pf0_theory.py",
    ]
    banned = {
        "draw_online_pilot", "assemble_state", "eval_proposal_is",
        "matched_arm_m2", "simulate", "run_simulation", "default_rng",
        "generate_pilot",
    }
    for path in paths:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not banned & (names | attrs), (path, banned & (names | attrs))


def test_m4pf0_matrix_gradient_symmetry():
    a, resp, z = fixed_inputs()
    g = matrix_gradient_estimate(a, resp, z)["gradient_matrix"]
    assert np.array_equal(g, g.T)


def test_m4pf0_scalar_trace_recovery():
    a, resp, z = fixed_inputs()
    matrix = matrix_gradient_estimate(a, resp, z)
    scalar = scalar_gradient_estimate(
        a, resp, np.sum(z ** 2, axis=1), s2=1.0, dim=z.shape[1])
    assert math.isclose(matrix["scalar_trace"], scalar["g_hat"],
                        rel_tol=0, abs_tol=1e-15)


def test_m4pf0_directional_gradient_fd():
    target = np.array([[1.35, 0.18], [0.18, 0.82]])
    proposal = np.array([[1.05, 0.08], [0.08, 1.22]])
    direction = np.array([[0.4, 0.7], [0.7, -0.2]])
    gradient = gaussian_log_covariance_gradient(target, proposal)
    analytic = directional_gradient(gradient, direction)
    fd = log_covariance_directional_fd(target, proposal, direction, 1e-4)
    assert math.isclose(analytic, fd, rel_tol=2e-7, abs_tol=1e-10)


def test_m4pf0_rank1_direction_formula():
    a, resp, z = fixed_inputs()
    gradient = matrix_gradient_estimate(a, resp, z)["gradient_matrix"]
    vector = np.array([3.0, 4.0]) / 5.0
    direction = np.outer(vector, vector)
    assert math.isclose(directional_gradient(gradient, direction),
                        float(vector @ gradient @ vector),
                        rel_tol=0, abs_tol=1e-15)


def test_m4pf0_spd_update():
    covariance = np.array([[1.3, 0.2], [0.2, 0.9]])
    gradient = np.array([[0.7, -0.4], [-0.4, -0.2]])
    for rank in (1, 2):
        out = spd_log_covariance_update(
            covariance, gradient, eta=0.15, rank=rank,
            normalize_frobenius=True, max_abs_log_step=0.2,
            condition_number_ceiling=10.0)
        assert out["min_eigenvalue"] > 0.0
        assert np.allclose(out["covariance"], out["covariance"].T,
                           rtol=0, atol=1e-15)
        assert out["condition_number"] < 10.0


def test_m4pf0_eigen_ordering():
    gradient = np.diag([0.2, -1.5, 0.8, -0.4])
    vals = rank_truncate(gradient, 2)["eigenvalues_abs_order"]
    assert np.array_equal(vals, np.array([-1.5, 0.8, -0.4, 0.2]))


def test_m4pf0_cancellation_score_bounds():
    for values in (np.array([1.0, -1.0]), np.array([2.0, 1.0]),
                   np.zeros(3), np.array([3.0, -1.0, -2.0])):
        score = cancellation_score(values)
        assert 0.0 <= score <= 1.0
    assert cancellation_score(np.array([1.0, -1.0])) > 0.999999


def test_m4pf0_spectral_fraction_bounds():
    diag = spectral_diagnostics(np.diag([2.0, -1.0, 0.5]))
    assert 0.0 <= diag["top1_spectral_fraction"] <= 1.0
    assert diag["top1_spectral_fraction"] <= \
        diag["top2_spectral_fraction"] <= 1.0
