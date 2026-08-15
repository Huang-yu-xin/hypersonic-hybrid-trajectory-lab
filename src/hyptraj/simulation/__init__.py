"""Numerical simulation of hypersonic trajectories."""

from .events import (
    make_capture_event,
    make_ground_event,
    make_qeg_end_event,
)
from .qian_research_trajectory import (
    DEFAULT_MAX_TIME_S,
    SIMULTANEOUS_EVENT_TOL_S,
    QianResearchEvent,
    QianResearchTrajectory,
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE,
    TERMINAL_KINDS,
    TERMINAL_MAX_TIME,
    TERMINAL_RTI,
    TERMINAL_SOLVER_FAILURE,
    integrate_qian_research_trajectory,
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
    "DEFAULT_MAX_TIME_S",
    "DEFAULT_SOLVER_CONFIG",
    "SIMULTANEOUS_EVENT_TOL_S",
    "SolverConfig",
    "TrajectoryResult",
    "integrate_qian_glide",
    "integrate_qian_research_trajectory",
    "integrate_trajectory",
    "make_capture_event",
    "make_ground_event",
    "make_qeg_end_event",
    "run_sanity_checks",
    "QianResearchEvent",
    "QianResearchTrajectory",
    "TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT",
    "TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI",
    "TERMINAL_GROUND_BEFORE_CAPTURE",
    "TERMINAL_KINDS",
    "TERMINAL_MAX_TIME",
    "TERMINAL_RTI",
    "TERMINAL_SOLVER_FAILURE",
]
