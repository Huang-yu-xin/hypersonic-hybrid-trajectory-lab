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
from .comparison_protocols import (
    CommonRangeComparison,
    CommonTimeComparison,
    run_common_range_comparison,
    run_common_time_comparison,
)
from .comparison_mechanisms import (
    CheckpointExposureDiagnostic,
    CommonAtmosphericExposureComparison,
    ModeAggregate,
    ProtocolDStatus,
    SegmentEnergyBudget,
    TrajectoryEnergyBudget,
    build_energy_budget,
    energy_curve_samples,
    exposure_diagnostic_at_common_range,
    exposure_diagnostic_at_common_time,
    run_common_atmospheric_exposure_comparison,
    total_vac_duration,
    total_vac_range,
    vac_duration_before_time,
)

__all__ = [
    "AtmosphericExposureInverseResult",
    "AtmosphericExposureInverseStatus",
    "CheckpointExposureDiagnostic",
    "CommonAtmosphericExposureComparison",
    "CommonRangeComparison",
    "CommonTimeComparison",
    "ComparisonEvent",
    "ComparisonState",
    "ComparisonTrajectory",
    "DenseSegmentView",
    "ModeAggregate",
    "ProtocolDStatus",
    "RangeMonotonicityResult",
    "SegmentEnergyBudget",
    "TrajectoryEnergyBudget",
    "build_energy_budget",
    "build_qian_comparison_trajectory",
    "build_sanger_comparison_trajectory",
    "energy_curve_samples",
    "exposure_diagnostic_at_common_range",
    "exposure_diagnostic_at_common_time",
    "run_common_atmospheric_exposure_comparison",
    "run_common_range_comparison",
    "run_common_time_comparison",
    "total_vac_duration",
    "total_vac_range",
    "vac_duration_before_time",
    "verify_comparison_alignment",
]
