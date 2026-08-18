"""Phase G -- finite-time local predictability of the hybrid trajectories.

G0 freezes the mathematical protocol (state / STM / saltation / event-time
conventions, event taxonomy, grazing policy, state-scaling candidates,
representative cases, validation and reference-solver policies):

* ``event_metadata`` -- frozen event-taxonomy registry;
* ``scaling``        -- state scaling candidates and canonical-scaling
  status (``S^-1 Phi S`` convention);
* ``protocol``       -- machine-readable protocol payload and the frozen
  convention formulas.

G1 adds the continuous-mode Jacobians (``jacobian``), the numerical FD
oracle, and the minimal variational algebra (``stm``).  G2 extends
``stm`` with the 20-D augmented continuous STM integrator and activates
``perturbation`` for the fixed-time nonlinear flow-map validation (FD
sweep + smooth-flow gate).  G3 adds ``saltation`` (event-time gradient +
transverse hybrid saltation for the three frozen hybrid switches, with
event-local nonlinear validation).  G4 adds ``hybrid_stm`` (chaining the
validated continuous STMs and saltations into the fixed-time
topology-preserving hybrid STM with global event-time gradients) and
``hybrid_validation`` (the independent full-nonlinear comparator with the
hybrid topology gate).  G5 activates ``ftle`` (scaled-SVD / FTLE / rank /
condition / unit-invariance) and ``metrics`` (fixed-time predictability
result), and adds ``terminal_sensitivity`` (RTI / SRTI event-time and
terminal-state sensitivity).  G5 performs NO grazing analysis.  The G6+
placeholder module ``observability`` remains empty.
"""

from hyptraj.predictability.protocol import machine_readable_protocol
from hyptraj.predictability.jacobian import (
    atmospheric_jacobian,
    entry_capture_jacobian,
    sanger_atm_jacobian,
    sanger_vac_jacobian,
    qeg_interior_jacobian,
    finite_difference_jacobian,
    jacobian_error_summary,
)
from hyptraj.predictability.stm import (
    state_transition_initial_value,
    variational_rhs,
    pack_augmented,
    unpack_augmented,
    make_augmented_rhs,
    integrate_continuous_stm,
    integrate_standalone_mode,
    computational_scaling_transform,
    stm_production_like_config,
    stm_strict_reference_config,
    stm_companion_reference_config,
)
from hyptraj.predictability.hybrid_stm import (
    build_hybrid_stm,
    build_split_tail,
    qian_no_saltation_negative_control,
)
from hyptraj.predictability.ftle import (
    canonicalize_svd_signs,
    finite_time_metrics,
    numerical_rank,
    scaled_svd,
)
from hyptraj.predictability.metrics import (
    FixedTimePredictabilityResult,
    compute_fixed_time_metrics,
)
from hyptraj.predictability.terminal_sensitivity import (
    TerminalSensitivityResult,
    build_terminal_sensitivity,
    qian_rti_terminal_normal,
    srti_terminal_normal,
)
from hyptraj.predictability.grazing import (
    FrozenGrazingAnchor,
    GrazingExcursion,
    ControlledFamilyPoint,
    GrazingTopologyContractError,
    load_frozen_grazing_anchors,
    extract_branch_excursion,
    controlled_local_grazing_family,
    build_excursion_factor,
    local_grazing_excursion_map,
    directional_topology_radius,
    fit_loglog_scaling,
    paired_radial_fd_plateau,
    paired_fd_validation,
    refined_operational_radius,
)

__all__ = [
    "machine_readable_protocol",
    "atmospheric_jacobian",
    "entry_capture_jacobian",
    "sanger_atm_jacobian",
    "sanger_vac_jacobian",
    "qeg_interior_jacobian",
    "finite_difference_jacobian",
    "jacobian_error_summary",
    "state_transition_initial_value",
    "variational_rhs",
    "pack_augmented",
    "unpack_augmented",
    "make_augmented_rhs",
    "integrate_continuous_stm",
    "integrate_standalone_mode",
    "computational_scaling_transform",
    "stm_production_like_config",
    "stm_strict_reference_config",
    "stm_companion_reference_config",
    "build_hybrid_stm",
    "build_split_tail",
    "qian_no_saltation_negative_control",
    "canonicalize_svd_signs",
    "finite_time_metrics",
    "numerical_rank",
    "scaled_svd",
    "FixedTimePredictabilityResult",
    "compute_fixed_time_metrics",
    "TerminalSensitivityResult",
    "build_terminal_sensitivity",
    "qian_rti_terminal_normal",
    "srti_terminal_normal",
    "FrozenGrazingAnchor",
    "GrazingExcursion",
    "ControlledFamilyPoint",
    "GrazingTopologyContractError",
    "load_frozen_grazing_anchors",
    "extract_branch_excursion",
    "controlled_local_grazing_family",
    "build_excursion_factor",
    "local_grazing_excursion_map",
    "directional_topology_radius",
    "fit_loglog_scaling",
    "paired_radial_fd_plateau",
    "paired_fd_validation",
    "refined_operational_radius",
]