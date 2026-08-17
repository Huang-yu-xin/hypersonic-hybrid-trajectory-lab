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
oracle, and the minimal variational algebra (``stm``).  G1 performs NO
STM propagation, NO saltation, NO FTLE production.  Placeholder modules
that remain empty for the G2-G6 layers: ``perturbation``, ``ftle``,
``metrics``, ``observability``.
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
]