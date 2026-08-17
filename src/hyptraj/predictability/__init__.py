"""Phase G -- finite-time local predictability of the hybrid trajectories.

G0 freezes the mathematical protocol (state / STM / saltation / event-time
conventions, event taxonomy, grazing policy, state-scaling candidates,
representative cases, validation and reference-solver policies) in the
metadata modules:

* ``event_metadata`` -- frozen event-taxonomy registry;
* ``scaling``        -- state scaling candidates and canonical-scaling
  status (``S^-1 Phi S`` convention);
* ``protocol``       -- machine-readable protocol payload and the frozen
  convention formulas.

G0 performs NO G1 computation: no continuous Jacobian, no variational
solver, no STM propagation, no saltation, no FTLE production.  The empty
placeholder modules (``stm``, ``jacobian``, ``perturbation``, ``ftle``,
``metrics``, ``observability``) stay unimplemented for the G1-G5 layers.
"""

from hyptraj.predictability.protocol import machine_readable_protocol

__all__ = ["machine_readable_protocol"]