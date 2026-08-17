"""Phase-G2 continuous STM integration (G2 -- velocity/flow-map derivative).

G2 augments the validated G1 linearization into a single smooth continuous
mode:

    x_dot   = f_m(x)                    (frozen nonlinear RHS)
    A       = A_m(x)                    (G1 analytic Jacobian, constant K)
    Phi_dot = A(x) * Phi,   Phi(t0,t0) = I

and integrates the 20-dimensional augmented system ``z = [x; vec(Phi)]``.
The STM is validated against independent nonlinear flow-map finite
differences (see ``predictability/perturbation.py``) for the four frozen
continuous modes, each in one representative no-event window.

Conventions (G0 §4 / G1 §3, frozen):

    x       = [r, theta, v, gamma]^T
    Phi_ij  = d x_i(t) / d x_0,j
    rows    = output state component, columns = initial perturbation
    Phi     flattened in numpy C-order (row-major); pack/unpack round-trip
            is locked by the G2 semantic tests.

Computational vs scientific scaling (G2 §12-§13): a COMPUTATIONAL
integration scaling ``S_num`` may be used purely to condition the 20-D
augmented system (``Psi = S^-1 Phi S``, ``A_num = S^-1 A S``,
``Psi(t0)=I``, recover ``Phi = S Psi S^-1``).  This is an INTEGRATION
representation choice only; it is NEVER called the canonical scientific
scaling (which remains PENDING until G5) and never used for
predictability ranking.

Scope boundaries (G2): no hybrid event crossing, no saltation, no
event-time / terminal sensitivity, no FTLE, no grazing, no Monte Carlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.predictability.jacobian import (
    analytic_jacobian,
    constant_k_value,
    frozen_rhs,
)
from hyptraj.predictability.scaling import SCALING_CANDIDATES

STATE_DIM = 4
PHI_DIM = STATE_DIM * STATE_DIM          # 16
AUGMENTED_DIM = STATE_DIM + PHI_DIM      # 20

# Frozen trajectory production tolerances (Phase C) on the 4 state channels.
_STATE_ATOL_PRODUCTION = np.array([1e-4, 1e-11, 1e-7, 1e-11])
_STATE_ATOL_STRICT = np.array([1e-7, 1e-14, 1e-10, 1e-14])
_RTOL_PRODUCTION = 1e-9
_RTOL_STRICT = 1e-12

# Default absolute tolerance for the 16 dimensionless STM channels.
# (A tiny convergence audit over {1e-9, 1e-11, 1e-13} backs the defaults;
# see docs/phase_g/g2_continuous_stm.md.)
PSI_ATOL_PRODUCTION_DEFAULT = 1e-11
PSI_ATOL_STRICT_DEFAULT = 1e-13


# ---------------------------------------------------------------------------
# Pack / unpack (numpy C-order / row-major, frozen)
# ---------------------------------------------------------------------------
def pack_augmented(x: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """``z = [x; vec(Phi)]`` with ``Phi`` flattened C-order (row-major)."""
    x = np.asarray(x, dtype=float)
    phi = np.asarray(phi, dtype=float)
    if x.shape != (STATE_DIM,):
        raise ValueError(f"x must be ({STATE_DIM},); got {x.shape}.")
    if phi.shape != (STATE_DIM, STATE_DIM):
        raise ValueError(
            f"phi must be ({STATE_DIM},{STATE_DIM}); got {phi.shape}."
        )
    z = np.empty(AUGMENTED_DIM, dtype=float)
    z[:STATE_DIM] = x
    z[STATE_DIM:] = phi.reshape(PHI_DIM, order="C")
    return z


def unpack_augmented(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inverse of ``pack_augmented``: ``(x, Phi)``."""
    z = np.asarray(z, dtype=float)
    if z.shape != (AUGMENTED_DIM,):
        raise ValueError(
            f"z must be ({AUGMENTED_DIM},); got {z.shape}."
        )
    x = z[:STATE_DIM].copy()
    phi = z[STATE_DIM:].reshape((STATE_DIM, STATE_DIM), order="C").copy()
    return x, phi


# ---------------------------------------------------------------------------
# Augmented RHS (reuses the FROZEN nonlinear RHS and G1 analytic Jacobian)
# ---------------------------------------------------------------------------
def make_augmented_rhs(
    mode: str,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    computational_scaling: np.ndarray | None = None,
) -> Callable[[float, np.ndarray], np.ndarray]:
    """Build ``z_dot = [x_dot; vec(Psi_dot)]`` (20-D).

    ``x_dot`` is the FROZEN nonlinear RHS (via ``jacobian.frozen_rhs``);
    ``A = A_m(x)`` is the G1 analytic Jacobian.  With
    ``computational_scaling`` ``S`` (diagonal, positive) the Phi channel is
    integrated as the COMPUTATIONALLY SCALED ``Psi = S^-1 Phi S`` with
    ``A_num = S^-1 A S``; ``z`` then carries ``[x; vec(Psi)]``.
    """
    x_rhs = frozen_rhs(mode, env, vehicle, k)

    def a_mat(x: np.ndarray) -> np.ndarray:
        return analytic_jacobian(mode, x, env, vehicle, k)

    if computational_scaling is None:
        def augmented(t, z):
            x, phi = unpack_augmented(z)
            xdot = np.asarray(x_rhs(x), dtype=float)
            A = a_mat(x)
            phidot = A @ phi
            return pack_augmented(xdot, phidot)

        return augmented

    s = np.asarray(computational_scaling, dtype=float)
    if s.shape != (STATE_DIM,) or not np.all(s > 0.0):
        raise ValueError("computational_scaling must be a positive 4-vector.")
    S = np.diag(s)
    S_inv = np.diag(1.0 / s)

    def augmented_scaled(t, z):
        x, psi = unpack_augmented(z)
        xdot = np.asarray(x_rhs(x), dtype=float)
        A = a_mat(x)
        A_num = S_inv @ A @ S
        psidot = A_num @ psi
        return pack_augmented(xdot, psidot)

    return augmented_scaled


def computational_scaling_transform(
    phi: np.ndarray,
    s_num: np.ndarray | None,
    inverse: bool = False,
) -> np.ndarray:
    """Computational scaling transform for a raw STM.

    ``Psi = S^-1 Phi S`` (``inverse=False``) and ``Phi = S Psi S^-1``
    (``inverse=True``).  ``None`` scaling is the identity (no transform).
    Pure representation algebra; the recovered physical ``Phi`` is what
    all G2 comparisons use.
    """
    phi = np.asarray(phi, dtype=float)
    if s_num is None:
        return phi
    s_num = np.asarray(s_num, dtype=float)
    S = np.diag(s_num)
    S_inv = np.diag(1.0 / s_num)
    if not inverse:
        return S_inv @ phi @ S
    return S @ phi @ S_inv


# ---------------------------------------------------------------------------
# Solver configurations (G0 §19 trajectory baseline + G2 §11 audit policy)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StmSolverConfig:
    """Augmented-system numerical configuration (20-D integrated vector)."""

    label: str
    rtol: float
    state_atol: np.ndarray  # (4,) on [r, theta, v, gamma]
    psi_atol: float         # scalar atol on the 16 dimensionless STM channels
    max_step: float

    def full_atol(self) -> np.ndarray:
        """(20,) tolerance: state channels then 16 STM channels."""
        return np.concatenate(
            [np.asarray(self.state_atol, dtype=float),
             np.full(PHI_DIM, float(self.psi_atol))]
        )


def stm_production_like_config(psi_atol: float = PSI_ATOL_PRODUCTION_DEFAULT):
    """Production-like augmented config (G2 §11; trajectory baseline style)."""
    return StmSolverConfig(
        label="production_like",
        rtol=_RTOL_PRODUCTION,
        state_atol=_STATE_ATOL_PRODUCTION.copy(),
        psi_atol=psi_atol,
        max_step=20.0,
    )


def stm_strict_reference_config(
    psi_atol: float = PSI_ATOL_STRICT_DEFAULT, max_step: float = 0.1
):
    """Strict reference augmented config (Phase C/F reference style)."""
    return StmSolverConfig(
        label="strict_reference_0.1" if max_step == 0.1 else f"strict_{max_step}",
        rtol=_RTOL_STRICT,
        state_atol=_STATE_ATOL_STRICT.copy(),
        psi_atol=psi_atol,
        max_step=max_step,
    )


def stm_companion_reference_config(psi_atol: float = PSI_ATOL_STRICT_DEFAULT):
    """Companion self-stability config: strict tolerances, max_step = 0.05 s."""
    return stm_strict_reference_config(psi_atol=psi_atol, max_step=0.05)


def default_stm_solver_configs() -> dict[str, StmSolverConfig]:
    """The three G2 comparing configurations (production / 0.1 / 0.05)."""
    return {
        "production_like": stm_production_like_config(),
        "REF-0.1": stm_strict_reference_config(),
        "REF-0.05": stm_companion_reference_config(),
    }


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ContinuousStmResult:
    """One continuous-mode STM over ``[t0, t1]`` (single smooth flow)."""

    mode: str
    t0: float
    t1: float
    x0: np.ndarray
    x1: np.ndarray
    phi: np.ndarray              # physical STM Phi(t1, t0) (raw units)
    solver: StmSolverConfig
    computational_scaling: np.ndarray | None = None
    success: bool = True
    message: str = ""

    @property
    def elapsed_s(self) -> float:
        return float(self.t1 - self.t0)


# ---------------------------------------------------------------------------
# Continuous STM integrator
# ---------------------------------------------------------------------------
def integrate_continuous_stm(
    mode: str,
    x0: np.ndarray,
    t_span: tuple[float, float],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    solver: StmSolverConfig | None = None,
    computational_scaling: np.ndarray | None = None,
    research_domain_guard: bool = True,
    output_times: np.ndarray | None = None,
) -> ContinuousStmResult:
    """Integrate the 20-D augmented variational system for one mode window.

    ``[t0, t1]`` must lie strictly inside one continuous mode (no hybrid
    switch).  With ``research_domain_guard=True`` and an atmospheric mode
    the altitude is required to stay ``> 0`` (G1 Jacobian validity domain);
    the guard never modifies the frozen RHS.  ``computational_scaling`` is
    the integration representation only; the returned ``phi`` is the raw
    physical STM.
    """
    mode = mode
    x0 = np.asarray(x0, dtype=float)
    if x0.shape != (STATE_DIM,):
        raise ValueError(f"x0 must be ({STATE_DIM},); got {x0.shape}.")
    solver = solver or stm_production_like_config()
    t0, t1 = float(t_span[0]), float(t_span[1])
    if not t1 > t0:
        raise ValueError("t_span must satisfy t1 > t0.")

    k_float = constant_k_value(k)
    z0 = pack_augmented(x0, state_transition_initial_value())
    augmented = make_augmented_rhs(
        mode, env, vehicle, k_float,
        computational_scaling=computational_scaling,
    )

    sol = solve_ivp(
        augmented,
        (t0, t1),
        z0,
        method="DOP853",
        rtol=solver.rtol,
        atol=solver.full_atol(),
        max_step=solver.max_step,
        dense_output=True,
    )
    if not sol.success:
        return ContinuousStmResult(
            mode=mode, t0=t0, t1=t1, x0=x0,
            x1=np.asarray(sol.y[:STATE_DIM, -1], dtype=float),
            phi=np.zeros((STATE_DIM, STATE_DIM)),
            solver=solver,
            computational_scaling=computational_scaling,
            success=False,
            message=f"solver failure: {sol.message}",
        )

    x1, psi1 = unpack_augmented(np.asarray(sol.y[:, -1], dtype=float))
    phi1 = computational_scaling_transform(
        psi1, computational_scaling, inverse=True
    )

    if research_domain_guard and mode in ("entry_capture", "qeg_interior",
                                          "sanger_atm"):
        grid_t = np.linspace(t0, t1, 401)
        grid_x = sol.sol(grid_t)[:STATE_DIM]
        h_min = float(np.min(grid_x[0] - env.earth_radius))
        if h_min <= 0.0:
            raise ValueError(
                f"research-domain guard: altitude non-positive on [t0,t1] "
                f"(h_min = {h_min:.6e} m) for mode {mode}; "
                "G1 atmospheric Jacobian requires h > 0."
            )

    return ContinuousStmResult(
        mode=mode, t0=t0, t1=t1, x0=x0, x1=x1, phi=phi1,
        solver=solver,
        computational_scaling=computational_scaling,
    )


def integrate_standalone_mode(
    mode: str,
    x0: np.ndarray,
    t_span: tuple[float, float],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    solver: StmSolverConfig | None = None,
) -> np.ndarray:
    """Frozen nonlinear standalone trajectory ``x(t1)`` (G2 §19 consistency).

    Uses exactly ``jacobian.frozen_rhs(mode)`` with the same tolerance
    policy; the result must match the augmented state channel.
    """
    x_rhs = frozen_rhs(mode, env, vehicle, k)
    cfg = solver or stm_production_like_config()
    sol = solve_ivp(
        lambda t, x: x_rhs(x),
        (float(t_span[0]), float(t_span[1])),
        np.asarray(x0, dtype=float),
        method="DOP853",
        rtol=cfg.rtol,
        atol=cfg.state_atol,
        max_step=cfg.max_step,
        dense_output=True,
    )
    if not sol.success:
        raise RuntimeError(f"standalone integration failed: {sol.message}")
    return np.asarray(sol.y[:, -1], dtype=float)


# Keep the G1 contract available (pure algebraic building block).
def variational_rhs(phi, a_matrix) -> np.ndarray:
    """G1 contract ``dphi = A @ phi`` (kept for backward compatibility).

    ``phi`` and ``a_matrix`` must both be ``(4,4)`` (frozen convention);
    shape violations raise ``ValueError`` (G1 shape-guard contract).
    """
    phi = np.asarray(phi, dtype=float)
    a_matrix = np.asarray(a_matrix, dtype=float)
    if a_matrix.shape != (STATE_DIM, STATE_DIM):
        raise ValueError(
            "a_matrix must be (4,4); got "
            f"{a_matrix.shape}."
        )
    if phi.shape != (STATE_DIM, STATE_DIM):
        raise ValueError(
            "phi must be (4,4); got "
            f"{phi.shape}."
        )
    return a_matrix @ phi


def state_transition_initial_value() -> np.ndarray:
    """``Phi(t0, t0) = I`` (frozen convention, G0 §4)."""
    return np.eye(STATE_DIM)