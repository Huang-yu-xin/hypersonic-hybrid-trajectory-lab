"""Analysis layer for Phase E comparison infrastructure (E1).

Pure analysis / alignment / evaluation layer on top of the frozen
simulation stack: never re-integrates, never modifies frozen results.
"""

from .comparison import (
    AtmosphericExposureInverseResult,
    AtmosphericExposureInverseStatus,
    ComparisonEvent,
    ComparisonState,
    ComparisonTrajectory,
    DenseSegmentView,
    RangeMonotonicityResult,
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
    verify_comparison_alignment,
)

__all__ = [
    "AtmosphericExposureInverseResult",
    "AtmosphericExposureInverseStatus",
    "ComparisonEvent",
    "ComparisonState",
    "ComparisonTrajectory",
    "DenseSegmentView",
    "RangeMonotonicityResult",
    "build_qian_comparison_trajectory",
    "build_sanger_comparison_trajectory",
    "verify_comparison_alignment",
]
