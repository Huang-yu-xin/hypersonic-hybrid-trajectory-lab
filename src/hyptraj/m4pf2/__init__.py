"""M4-PF2 joint mean/covariance objective-gradient utilities."""

from .mean_gradient import (
    gaussian_mean_directional_fd,
    gaussian_mean_gradient_terms,
    mean_gradient_estimate,
    whitened_mean_step,
)

__all__ = [
    "gaussian_mean_directional_fd",
    "gaussian_mean_gradient_terms",
    "mean_gradient_estimate",
    "whitened_mean_step",
]
