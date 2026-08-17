"""Phase-G2 nonlinear flow-map validation (G2 §20-§23).

Independent fixed-time nonlinear validation of the continuous STM:

    D_j^NL = [ x(t1; x0 + eps_j e_j) - x(t1; x0 - eps_j e_j) ] / (2 eps_j)

compared against the STM column ``Phi(:, j) = d x(t1)/d x_0,j``.  The
perturbation magnitudes are swept over a multiplier ladder anchored to
the G0 tolerance-candidate-B base step (``[100 m, 1e-5 rad, 1 m/s,
1e-4 rad]``) -- this is an FD RESEARCH STEP, NEVER the canonical
scientific scaling (PENDING until G5) and never a predictability ranking.

Every accepted perturbation is classified by the smooth-flow gate (G2
§22): ordinary STM acceptance only uses VALID_SMOOTH_FLOW.  In
particular, for the QEG mode the WHOLE interval of each perturbed
trajectory must remain ``0 < u_L* < 1``; any excursion into a saturated /
non-differentiable rate renders the column ACTIVE_SET_CHANGED (a
validation-domain violation, NOT an STM error).
"""

from __future__ import annotations

from enum import Enum

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.predictability.jacobian import (
    STATE_DIM,
    classify_qeg_active_set,
    frozen_rhs,
    jacobian_error_summary,
    u_l_star,
)
from hyptraj.predictability.scaling import scaled_stm

# G0 tolerance-candidate-B as the FD RESEARCH base step (never canonical).
FD_BASE_STEP = np.array([100.0, 1e-5, 1.0, 1e-4])
FD_MULTIPLIERS = (1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0, 3.0, 10.0)


class FlowValidationClass(Enum):
    """Smooth-flow validation gate (G2 §22)."""

    VALID_SMOOTH_FLOW = "VALID_SMOOTH_FLOW"
    ACTIVE_SET_CHANGED = "ACTIVE_SET_CHANGED"
    MODE_WINDOW_INVALID = "MODE_WINDOW_INVALID"
    NONPHYSICAL_STATE = "NONPHYSICAL_STATE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


def fixed_time_nonlinear_difference(
    mode: str,
    x0: np.ndarray,
    column: int,
    epsilon: float,
    t_span: tuple[float, float],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    solver,
) -> tuple[np.ndarray, dict]:
    """Centered nonlinear FD column ``D_j^NL`` (independent of any STM).

    Integrates the FROZEN nonlinear RHS at ``x0 +/- eps e_j`` over the
    same fixed elapsed time and physical RHS as the STM.  Returns the
    (4,) difference column and per-side metadata (success flags).
    """
    x0 = np.asarray(x0, dtype=float)
    rhs = frozen_rhs(mode, env, vehicle, k)
    e_j = np.zeros(STATE_DIM)
    e_j[column] = 1.0
    x_plus = x0 + epsilon * e_j
    x_minus = x0 - epsilon * e_j

    def _integrate(xi):
        from hyptraj.predictability.stm import StmSolverConfig
        from scipy.integrate import solve_ivp

        sol = solve_ivp(
            lambda t, x: rhs(x),
            (float(t_span[0]), float(t_span[1])),
            xi,
            method="DOP853",
            rtol=solver.rtol,
            atol=(solver.state_atol
                  if isinstance(solver, StmSolverConfig) else solver.atol),
            max_step=(solver.max_step
                      if isinstance(solver, StmSolverConfig) else solver.max_step),
            dense_output=True,
        )
        return sol

    sol_p = _integrate(x_plus)
    sol_m = _integrate(x_minus)
    meta = {
        "plus_success": bool(sol_p.success),
        "minus_success": bool(sol_m.success),
    }
    if not (sol_p.success and sol_m.success):
        return None, meta
    d = (np.asarray(sol_p.y[:, -1], dtype=float)
         - np.asarray(sol_m.y[:, -1], dtype=float)) / (2.0 * epsilon)
    return d, meta


def _u_l_star_bounds(
    mode: str,
    x0: np.ndarray,
    t_span: tuple[float, float],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    solver,
    n_grid: int = 41,
) -> tuple[float, float, bool]:
    """Min/max ``u_L*`` along a trajectory (for the QEG branch gate).

    ``valid`` is False when any sample is at/outside the interior
    ``(0, 1)`` (i.e. LOWER_SATURATED / UPPER_SATURATED /
    NONDIFFERENTIABLE).
    """
    from hyptraj.predictability.stm import StmSolverConfig
    from scipy.integrate import solve_ivp

    rhs = frozen_rhs(mode, env, vehicle, k)
    sol = solve_ivp(
        lambda t, x: rhs(x),
        (float(t_span[0]), float(t_span[1])),
        np.asarray(x0, dtype=float),
        method="DOP853",
        rtol=solver.rtol,
        atol=(solver.state_atol
              if isinstance(solver, StmSolverConfig) else solver.atol),
        max_step=(solver.max_step
                  if isinstance(solver, StmSolverConfig) else solver.max_step),
        dense_output=True,
    )
    if not sol.success:
        return float("nan"), float("nan"), False
    grid_t = np.linspace(t_span[0], t_span[1], n_grid)
    xs = np.asarray(sol.sol(grid_t))[:STATE_DIM, :]
    vals = []
    valid = True
    for j in range(xs.shape[1]):
        try:
            us = u_l_star(xs[:, j], env, vehicle, k)
        except ValueError:
            valid = False
            continue
        vals.append(us)
        if classify_qeg_active_set(us) != classify_qeg_active_set(0.5):
            valid = False
    if not vals:
        return float("nan"), float("nan"), False
    return float(min(vals)), float(max(vals)), valid


def gate_perturbed_trajectory(
    mode: str,
    x0: np.ndarray,
    t_span: tuple[float, float],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    solver,
    n_grid: int = 41,
) -> FlowValidationClass:
    """Classify one finite-perturbation trajectory (G2 §22 gate).

    * NUMERICAL_FAILURE        -- solver failed;
    * NONPHYSICAL_STATE        -- altitude non-positive anywhere (an
      outside-the-research-domain state, G1 Jacobian validity);
    * ACTIVE_SET_CHANGED       -- QEG trajectory leaves the strict
      interior ``0 < u_L* < 1`` on the interval (a validation-domain
      violation, never an STM error);
    * MODE_WINDOW_INVALID      -- the trajectory cannot be certified to
      stay inside the single continuous window (reserved/defensive);
    * VALID_SMOOTH_FLOW        -- usable for ordinary smooth STM acceptance.
    """
    from hyptraj.predictability.stm import StmSolverConfig
    from scipy.integrate import solve_ivp

    rhs = frozen_rhs(mode, env, vehicle, k)
    sol = solve_ivp(
        lambda t, x: rhs(x),
        (float(t_span[0]), float(t_span[1])),
        np.asarray(x0, dtype=float),
        method="DOP853",
        rtol=solver.rtol,
        atol=(solver.state_atol
              if isinstance(solver, StmSolverConfig) else solver.atol),
        max_step=(solver.max_step
                  if isinstance(solver, StmSolverConfig) else solver.max_step),
        dense_output=True,
    )
    if not sol.success:
        return FlowValidationClass.NUMERICAL_FAILURE

    grid_t = np.linspace(t_span[0], t_span[1], n_grid)
    xs = np.asarray(sol.sol(grid_t))[:STATE_DIM, :]

    if mode in ("entry_capture", "qeg_interior", "sanger_atm"):
        h_min = float(np.min(xs[0] - env.earth_radius))
        if h_min <= 0.0:
            return FlowValidationClass.NONPHYSICAL_STATE

    if mode == "qeg_interior":
        for j in range(xs.shape[1]):
            try:
                us = u_l_star(xs[:, j], env, vehicle, k)
            except ValueError:
                return FlowValidationClass.ACTIVE_SET_CHANGED
            if classify_qeg_active_set(us) != classify_qeg_active_set(0.5):
                return FlowValidationClass.ACTIVE_SET_CHANGED

    return FlowValidationClass.VALID_SMOOTH_FLOW


def epsilon_sweep_fd(
    mode: str,
    x0: np.ndarray,
    t_span: tuple[float, float],
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k,
    solver,
    phi_stm: np.ndarray,
    base_step: np.ndarray = FD_BASE_STEP,
    multipliers: tuple[float, ...] = FD_MULTIPLIERS,
) -> dict:
    """Full finite-perturbation sweep against an STM (G2 §21-§23).

    For every column and every multiplier, computes the nonlinear FD
    column (gated), forms the FD matrix, and compares against the STM.
    Returns a structured summary ready for the G2 snapshot.
    """
    x0 = np.asarray(x0, dtype=float)
    sweep = {}
    classes_seen: set[str] = set()
    for mult in multipliers:
        eps = base_step * mult
        fd = np.zeros((STATE_DIM, STATE_DIM))
        valid_cols = np.zeros(STATE_DIM, dtype=bool)
        col_meta = []
        classification = []
        for j in range(STATE_DIM):
            d, meta = fixed_time_nonlinear_difference(
                mode, x0, j, float(eps[j]), t_span, env, vehicle, k, solver
            )
            cls = gate_perturbed_trajectory(
                mode, x0 + eps[j] * np.eye(STATE_DIM)[:, j],
                t_span, env, vehicle, k, solver,
            )
            classes_seen.add(cls.value)
            classification.append(cls.value)
            if d is None:
                continue
            fd[:, j] = d
            if cls == FlowValidationClass.VALID_SMOOTH_FLOW:
                valid_cols[j] = True

        # Only VALID_SMOOTH_FLOW columns enter the acceptance comparison.
        n_valid = int(valid_cols.sum())
        summary = {
            "multiplier": mult,
            "n_valid_columns": n_valid,
            "fd_matrix": [[float(fd[i, j]) for j in range(STATE_DIM)]
                          for i in range(STATE_DIM)],
            "classification": classification,
            "max_abs_error": (
                float(np.max(np.abs(fd - phi_stm))) if n_valid == STATE_DIM else None
            ),
            "max_rel_error_nonzero": (
                float(jacobian_error_summary(phi_stm, fd)["max_rel_error_nonzero"])
                if n_valid == STATE_DIM else None
            ),
            "per_column_abs": (
                [float(np.max(np.abs(fd[:, j] - phi_stm[:, j])))
                 for j in range(STATE_DIM)]
                if n_valid == STATE_DIM else None
            ),
        }
        sweep[f"mult_{mult:g}"] = summary
    return sweep


def validation_scaled_error(
    fd: np.ndarray,
    phi_stm: np.ndarray,
    scales: dict,
) -> float:
    """``|S^-1 (D^NL - Phi) S|_inf / max(1, |S^-1 Phi S|_inf)``.

    VALIDATION NORMALIZATION ONLY (dimension-aware numerical reporting,
    G2 §23).  Never a predictability ranking; different S must never be
    compared as such.
    """
    fd = np.asarray(fd, dtype=float)
    phi = np.asarray(phi_stm, dtype=float)
    err = scaled_stm(fd - phi, scales)
    ref = scaled_stm(phi, scales)
    n = float(np.max(np.abs(err))) if err.size else 0.0
    dden = max(1.0, float(np.max(np.abs(ref))))
    return n / dden