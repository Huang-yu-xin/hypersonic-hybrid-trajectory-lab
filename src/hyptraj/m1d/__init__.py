"""M1-D -- multi-missing-mode variance-geometry benchmark (RareTopo M1-D).

New namespace for the preregistered M1-D task
(``docs/phase_m1d/M1_D_Multi_Missing_Mode_Variance_Geometry_Benchmark_Task.md``).
Scientific firewall (task Sec. 2): nothing here modifies the frozen
``hyptraj.m1`` v0 method; this package only *constructs benchmarks*,
characterizes them offline, and checks eligibility.
"""

from hyptraj.m1d.benchmark_family import (
    BenchmarkConfig,
    compute_eligibility,
    generate_candidate_pool,
    reference_characterize,
)

__all__ = [
    "BenchmarkConfig",
    "generate_candidate_pool",
    "reference_characterize",
    "compute_eligibility",
]
