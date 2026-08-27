"""M3-D -- sign-diverse scalar covariance-control benchmark (task
M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md).

Modules
-------
benchmark_states    frozen proposal-STATE construction over the preregistered
                    candidate grid (config x s2), legality pre-freeze gate,
                    assembly anchored deterministically per config
reference_direction offline reference characterization + oracle labels +
                    direction margins ( barred from the online controller)
adaptation          ONLINE controller path reusing hyptraj.m3 VERBATIM
metrics             record builders + gate aggregates for raretopo-m3d-v0

FIREWALL: nothing in this package may read oracle / reference fields inside
any online API surface (task Sec. 13); structural test enforces it.
"""

from hyptraj.m3d.benchmark_states import (
    ANCHOR_SEED,
    BenchmarkState,
    assemble_state,
    enumerate_candidate_states,
    state_arms,
)

__all__ = [
    "ANCHOR_SEED",
    "BenchmarkState",
    "assemble_state",
    "enumerate_candidate_states",
    "state_arms",
]

