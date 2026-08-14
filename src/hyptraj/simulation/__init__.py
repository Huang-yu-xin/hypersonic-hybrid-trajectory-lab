"""Numerical simulation of hypersonic trajectories."""

from .events import (
    make_capture_event,
    make_ground_event,
    make_qeg_end_event,
)
from .trajectory import (
    DEFAULT_SOLVER_CONFIG,
    SolverConfig,
    TrajectoryResult,
    integrate_qian_glide,
    integrate_trajectory,
    run_sanity_checks,
)

__all__ = [
    "DEFAULT_SOLVER_CONFIG",
    "SolverConfig",
    "TrajectoryResult",
    "integrate_qian_glide",
    "integrate_trajectory",
    "make_capture_event",
    "make_ground_event",
    "make_qeg_end_event",
    "run_sanity_checks",
]
