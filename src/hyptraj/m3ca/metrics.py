"""Pure arithmetic metrics for M3-CA.

This module deliberately has no dependency on a simulator, proposal builder,
random-number generator, or online controller.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence


def median(values: Iterable[float]) -> float:
    return float(statistics.median(float(v) for v in values))


def estimator_variance(m2_hat: float, p_hat: float, n_eval: int) -> float:
    if n_eval <= 0:
        raise ValueError("n_eval must be positive")
    return max(0.0, float(m2_hat) - float(p_hat) ** 2) / int(n_eval)


def proposal_vrf(
    p_ref: float, m2_hat: float, p_hat: float, n_eval: int
) -> float:
    """Crude-MC variance / IS variance at the same evaluation count."""
    den = estimator_variance(m2_hat, p_hat, n_eval)
    num = float(p_ref) * (1.0 - float(p_ref)) / int(n_eval)
    return float(num / den) if den > 0.0 else float("inf")


def budget_vrf(
    p_ref: float,
    m2_hat: float,
    p_hat: float,
    n_eval: int,
    deployable_budget: int,
) -> float:
    """Crude-MC variance at total budget / reduced-budget IS variance."""
    if deployable_budget <= 0:
        raise ValueError("deployable_budget must be positive")
    den = estimator_variance(m2_hat, p_hat, n_eval)
    num = float(p_ref) * (1.0 - float(p_ref)) / int(deployable_budget)
    return float(num / den) if den > 0.0 else float("inf")


def unified_j(per_state_log_ratios: Sequence[Sequence[float]]) -> float:
    """median_state(median_replicate(log(M2(policy)/M2(BASE))))."""
    if not per_state_log_ratios:
        raise ValueError("at least one state is required")
    return median(median(row) for row in per_state_log_ratios)


def log_ratio(numerator: float, denominator: float) -> float:
    if numerator <= 0.0 or denominator <= 0.0:
        raise ValueError("M2 values must be positive")
    return float(math.log(float(numerator) / float(denominator)))


def relative_close(actual: float, expected: float, atol: float = 1e-8) -> bool:
    return bool(math.isclose(float(actual), float(expected), rel_tol=0.0,
                             abs_tol=float(atol)))
