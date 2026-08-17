"""Phase-G1 minimal variational equation algebra (G1 §16 -- contract only).

G1 establishes the algebraic building block of the variational equation:

    d(Phi) / dt = A_m(t) * Phi,    Phi(t0, t0) = I

as a PURE matrix operation (``dphi = A @ phi``).  Explicitly NOT
implemented in G1 (G2/G3/G4 scope): ``solve_ivp`` over ``[x, Phi]``,
continuous STM propagation, event-spanning propagation, saltation
insertion, event-time/terminal sensitivity, FTLE/SVD predictability.

The state-transition convention is frozen by G0 §4: ``Phi_ij =
d x_i(t) / d x_0,j`` with rows = output component, columns = initial
perturbation component.
"""

from __future__ import annotations

import numpy as np

_STATE_DIM = 4


def state_transition_initial_value() -> np.ndarray:
    """``Phi(t0, t0) = I`` (frozen convention, G0 §4)."""
    return np.eye(_STATE_DIM)


def variational_rhs(
    phi: np.ndarray,
    a_matrix: np.ndarray,
) -> np.ndarray:
    """Variational RHS ``dphi = A(x) @ phi`` for ``Phi`` shape ``(4,4)``.

    ``a_matrix`` must be the continuous-mode Jacobian ``A_m`` in the frozen
    column/row order ``[r, theta, v, gamma]``.  Shape guards enforce the
    ``(4,4)`` contract; ``Phi = I`` maps to ``dphi = A`` (verified by the
    G1 semantic tests).  Pure algebra -- no integration is performed here.
    """
    phi = np.asarray(phi, dtype=float)
    a_matrix = np.asarray(a_matrix, dtype=float)
    if a_matrix.shape != (_STATE_DIM, _STATE_DIM):
        raise ValueError(
            "a_matrix must be (4,4); got "
            f"{a_matrix.shape}."
        )
    if phi.shape != (_STATE_DIM, _STATE_DIM):
        raise ValueError(
            "phi must be (4,4); got "
            f"{phi.shape}."
        )
    return a_matrix @ phi