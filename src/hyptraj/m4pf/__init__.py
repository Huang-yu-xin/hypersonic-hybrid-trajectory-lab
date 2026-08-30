"""M4-PF structured objective-gradient arithmetic."""

from .gradient import (
    cancellation_score,
    directional_gradient,
    gaussian_log_covariance_gradient,
    gaussian_second_moment,
    matrix_gradient_estimate,
    rank_truncate,
    spectral_diagnostics,
    spd_log_covariance_update,
)

__all__ = [
    "matrix_gradient_estimate",
    "directional_gradient",
    "rank_truncate",
    "spectral_diagnostics",
    "cancellation_score",
    "spd_log_covariance_update",
    "gaussian_second_moment",
    "gaussian_log_covariance_gradient",
]
