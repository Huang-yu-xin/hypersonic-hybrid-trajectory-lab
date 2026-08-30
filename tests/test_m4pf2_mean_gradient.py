"""PF2-0 deterministic mean-gradient and parameterization tests."""

from __future__ import annotations

import numpy as np

from hyptraj.m4pf2.mean_gradient import (
    gaussian_mean_directional_fd,
    gaussian_mean_gradient_terms,
    mean_gradient_estimate,
    whitened_mean_step,
)


TARGET_MEAN = np.array([0.35, -0.20])
TARGET_COV = np.array([[1.20, 0.12], [0.12, 0.90]])
PROPOSAL_MEAN = np.array([-0.10, 0.25])
PROPOSAL_COV = np.array([[1.05, 0.08], [0.08, 1.18]])


def test_m4pf2_mean_gradient_fd():
    terms = gaussian_mean_gradient_terms(
        TARGET_MEAN, TARGET_COV, PROPOSAL_MEAN, PROPOSAL_COV)
    for direction in (np.array([1.0, 0.0]), np.array([0.3, -0.7])):
        analytic = -terms["M2"] * float(
            terms["dimensionless_mean_gradient"] @ direction)
        fd = gaussian_mean_directional_fd(
            TARGET_MEAN, TARGET_COV, PROPOSAL_MEAN, PROPOSAL_COV,
            direction, 1e-5)
        assert np.isclose(fd, analytic, rtol=2e-9, atol=2e-10)


def test_m4pf2_mean_descent_sign():
    terms = gaussian_mean_gradient_terms(
        TARGET_MEAN, TARGET_COV, PROPOSAL_MEAN, PROPOSAL_COV)
    a = terms["dimensionless_mean_gradient"]
    direction = a / np.linalg.norm(a)
    derivative = -terms["M2"] * float(a @ direction)
    assert derivative < 0.0


def test_m4pf2_whitened_mean_parameterization():
    a = np.array([0.8, -0.6])
    covariance = np.array([[1.4, 0.2], [0.2, 0.9]])
    base = whitened_mean_step(covariance, a, delta_mu=0.2)
    scaled = whitened_mean_step(49.0 * covariance, a, delta_mu=0.2)
    assert np.allclose(scaled["displacement"], 7.0 * base["displacement"])
    assert np.isclose(base["mahalanobis_norm"], 0.2)
    assert np.isclose(scaled["mahalanobis_norm"], 0.2)


def test_m4pf2_mean_step_magnitude():
    result = whitened_mean_step(PROPOSAL_COV, np.array([1.0, 2.0]), 0.2)
    assert np.isclose(result["mahalanobis_norm"], 0.2, atol=1e-14)
    assert result["mean_update_skipped_numerical_zero"] is False


def test_m4pf2_mean_numerical_zero_is_identity():
    result = whitened_mean_step(PROPOSAL_COV, np.array([1e-14, 0.0]),
                                0.2, numerical_zero_threshold=1e-12)
    assert np.array_equal(result["displacement"], np.zeros(2))
    assert result["mean_update_skipped_numerical_zero"] is True


def test_m4pf2_mean_gradient_estimator_normalization():
    mass = np.array([1.0, 3.0])
    resp = np.array([0.5, 1.0])
    z = np.array([[1.0, 2.0], [-1.0, 4.0]])
    result = mean_gradient_estimate(mass, resp, z)
    expected = (1.0/4.0)*0.5*z[0] + (3.0/4.0)*z[1]
    assert np.allclose(result["dimensionless_mean_gradient"], expected)
    assert np.isclose(result["M2_hat"], 2.0)
