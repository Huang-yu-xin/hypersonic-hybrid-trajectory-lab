"""M1 -- Closed-Loop Variance-Geometry Adaptive Importance Sampling.

M1 research line (preregistered in
``docs/phase_m1/M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md``):

    q_t -> estimated variance geometry -> diagnose
         -> proposal action -> q_{t+1}

Firewall (frozen by H3): H3 = ``q -> variance geometry``; M1 = ``variance
geometry -> q_next``.  Nothing in this namespace modifies ``RareTopo-H3-v1.0``
frozen artifacts; this is a pure analysis layer.

v0 scope (task Sec. 8.3 / 10): component birth, component mean from variance
geometry, mixture-weight reallocation.  Covariance adaptation, deletion and
ML policy are explicitly deferred.

Modules:

- ``mixture_weights`` -- M1-1: fixed-component mixture-weight convexity,
  unbiased finite-sample ``M2_hat(pi)`` objective, analytic gradient /
  Hessian, frozen SLSQP solver (theory doc
  ``docs/phase_m1/M1_Theory_Mixture_Weight_Convexity.md``).
- ``variance_measure`` -- M1-2: variance-mass weights, ``M2_hat``, mode-wise
  ``L_k`` / ``omega_k_V``, bootstrap LCB (task Sec. 7).
- ``mode_discovery`` -- M1-2: missing-mode definition and the frozen
  mode-birth gate (task Sec. 11 / 12).
- ``proposal_update`` -- M1-2: ADD_COMPONENT (eta centroid) and
  UPDATE_WEIGHTS (frozen SLSQP) actions (task Sec. 13 / 15).
- ``closed_loop`` -- M1-2: Discover + Add + Reweight iteration with the
  preregistered stop rule (task Sec. 10 / 17).
"""

from hyptraj.m1.closed_loop import (
    ClosedLoopIteration,
    ClosedLoopResult,
    run_closed_loop,
)
from hyptraj.m1.mixture_weights import (
    WeightOptimizeResult,
    component_log_densities,
    kkt_residue,
    m2_gradient,
    m2_hat,
    m2_hessian,
    mixture_log_density,
    optimize_mixture_weights,
    validate_weights,
)
from hyptraj.m1.mode_discovery import (
    DiscoveryResult,
    ModeStat,
    diagnose_missing_mode,
)
from hyptraj.m1.proposal_update import (
    MixtureProposal,
    add_component,
    eta_region_centroid,
    update_weights,
)
from hyptraj.m1.variance_measure import (
    VarianceMeasure,
    estimate_variance_measure,
    variance_mass_weights,
)

__all__ = [
    # mixture_weights
    "validate_weights",
    "component_log_densities",
    "mixture_log_density",
    "m2_hat",
    "m2_gradient",
    "m2_hessian",
    "kkt_residue",
    "optimize_mixture_weights",
    "WeightOptimizeResult",
    # variance_measure
    "variance_mass_weights",
    "estimate_variance_measure",
    "VarianceMeasure",
    # mode_discovery
    "diagnose_missing_mode",
    "ModeStat",
    "DiscoveryResult",
    # proposal_update
    "MixtureProposal",
    "add_component",
    "eta_region_centroid",
    "update_weights",
    # closed_loop
    "run_closed_loop",
    "ClosedLoopIteration",
    "ClosedLoopResult",
]