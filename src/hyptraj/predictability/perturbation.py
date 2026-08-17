"""Phase-G2 nonlinear flow-map validation (G2 §20-§23, G2R corrective patch).

Independent fixed-time nonlinear validation of the continuous STM:

    D_j^NL = [ x(t1; x0 + eps_j e_j) - x(t1; x0 - eps_j e_j) ] / (2 eps_j)

compared against the STM column ``Phi(:, j) = d x(t1)/d x_0,j``.  The
perturbation magnitudes are swept over a multiplier ladder anchored to
the G0 tolerance-candidate-B base step (``[100 m, 1e-5 rad, 1 m/s,
1e-4 rad]``) -- this is an FD RESEARCH STEP, NEVER the canonical
scientific scaling (PENDING until G5) and never a predictability ranking.

Validation gate (G2 §22 + G2R):

* A centered-FD column is valid IFF BOTH the ``+epsilon`` and the
  ``-epsilon`` trajectories are ``VALID_SMOOTH_FLOW`` (G2R Issue 1:
  the acceptance rule formerly gated only the plus side).  Either side
  invalid -> column rejected (never entered into the STM error metric).
* ``MODE_WINDOW_INVALID`` is fully enforced (G2R Issue 2): the gate
  observes the FROZEN true-switch event surfaces of the mode being
  validated (Qian capture ``gamma=0,+1``; Sanger ATM exit / VAC entry
  ``h-h_atm``) and rejects any perturbation whose trajectory crosses one
  inside the window.  Diagnostic events (Sanger atmospheric pullout /
  VAC apogee, ``gamma=0``) are NOT true switches and never invalidate.
  This is a validation OBSERVER only: no hybrid propagation, no reset,
  no RHS switching, no saltation.
* QEG keeps the strictest rule: the WHOLE interval of every perturbed
  trajectory must stay ``0 < u_L* < 1``; any excursion into a saturated /
  non-differentiable rate gives ``ACTIVE_SET_CHANGED`` (a
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
    """Smooth-flow validation gate (G2 §22 + G2R)."""

    VALID_SMOOTH_FLOW = "VALID_SMOOTH_FLOW"
    ACTIVE_SET_CHANGED = "ACTIVE_SET_CHANGED"
    MODE_WINDOW_INVALID = "MODE_WINDOW_INVALID"
    NONPHYSICAL_STATE = "NONPHYSICAL_STATE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    # Derived pair-level label (G2R Issue 1): a centered-FD column is
    # VALID_SMOOTH_FLOW only when BOTH sides are VALID_SMOOTH_FLOW.
    PAIR_INVALID = "PAIR_INVALID"


def column_pair_class(cls_plus, cls_minus) -> FlowValidationClass:
    """Derived pair acceptance (G2R): valid iff both sides valid."""
    if cls_plus == FlowValidationClass.VALID_SMOOTH_FLOW and \
            cls_minus == FlowValidationClass.VALID_SMOOTH_FLOW:
        return FlowValidationClass.VALID_SMOOTH_FLOW
    return FlowValidationClass.PAIR_INVALID


def mode_window_detection_event(mode: str, env: EnvironmentParams):
    """Frozen true-switch event observed by the gate (G2R Issue 2).

    Returns the FROZEN event primitive whose upward/downward surface
    crossing leaves the single continuous window being validated, or
    ``None`` for modes whose window is instead governed by the active-set
    gate.  The gate only OBSERVES these surfaces (via ``solve_ivp``'s
    event machinery); it never runs a hybrid state machine, never applies
    a reset and never switches the RHS.
    """
    if mode == "entry_capture":
        from hyptraj.simulation.events import make_capture_event

        return make_capture_event()          # gamma=0, direction=+1
    if mode == "sanger_atm":
        from hyptraj.simulation.sanger_events import make_atmosphere_exit_event

        return make_atmosphere_exit_event(env)  # h-h_atm, direction=+1
    if mode == "sanger_vac":
        from hyptraj.simulation.sanger_events import make_atmosphere_entry_event

        return make_atmosphere_entry_event(env)  # h-h_atm, direction=-1
    if mode == "qeg_interior":
        return None                          # active-set gate covers RTI
    raise ValueError(f"unknown mode {mode!r}")


def _gate_integration(mode, x0, t_span, env, vehicle, k, solver):
    """Integrate one finite-perturbation trajectory for gating.

    Attaches the mode's frozen true-switch detection event (terminal=True)
    so a crossing stops the integration early and is reported via
    ``t_events``.  Pure observer: single-mode RHS only.
    """
    from hyptraj.predictability.stm import StmSolverConfig
    from scipy.integrate import solve_ivp

    rhs = frozen_rhs(mode, env, vehicle, k)
    ev = mode_window_detection_event(mode, env)
    events = None if ev is None else [ev]
    return solve_ivp(
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
        events=events,
    )


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
    """Classify one finite-perturbation trajectory (G2 §22 + G2R).

    Resolution order:

    * NUMERICAL_FAILURE        -- solver failed;
    * MODE_WINDOW_INVALID      -- a FROZEN true-switch surface of the mode
      (Qian capture / Sanger ATM exit / Sanger VAC entry) was crossed
      inside the window: the real flow would have left the single
      continuous mode;
    * NONPHYSICAL_STATE        -- altitude non-positive anywhere (outside
      the G1 research domain ``h > 0``);
    * ACTIVE_SET_CHANGED       -- QEG trajectory leaves the strict
      interior ``0 < u_L* < 1`` on the interval (RTI ``u_L* -> 1`` is
      naturally captured);
    * VALID_SMOOTH_FLOW        -- usable for ordinary smooth STM acceptance.

    Diagnostic events (Sanger pullout / VAC apogee, ``gamma = 0``) are NOT
    true switches and never invalidate the window.
    """
    sol = _gate_integration(mode, x0, t_span, env, vehicle, k, solver)
    if not sol.success:
        return FlowValidationClass.NUMERICAL_FAILURE

    # True-switch detection: terminal event triggered before t1.
    if sol.t_events is not None and any(
        se.size > 0 for se in sol.t_events if se is not None
    ):
        return FlowValidationClass.MODE_WINDOW_INVALID

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
) -> tuple[np.ndarray | None, dict]:
    """Centered nonlinear FD column ``D_j^NL`` (independent of any STM).

    Integrates the FROZEN nonlinear RHS at ``x0 +/- eps e_j`` over the
    same fixed elapsed time and physical RHS as the STM, and returns the
    (4,) difference column plus per-side metadata.  The value is computed
    for every column; the GATE decides whether the column may enter the
    acceptance metric (G2R: both sides must be VALID_SMOOTH_FLOW).
    """
    x0 = np.asarray(x0, dtype=float)
    rhs = frozen_rhs(mode, env, vehicle, k)
    e_j = np.zeros(STATE_DIM)
    e_j[column] = 1.0
    x_plus = x0 + epsilon * e_j
    x_minus = x0 - epsilon * e_j

    from hyptraj.predictability.stm import StmSolverConfig
    from scipy.integrate import solve_ivp

    def _integrate(xi):
        return solve_ivp(
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
    """Full finite-perturbation sweep against an STM (G2 §21-§23 + G2R).

    For every column and every multiplier: integrates BOTH the +eps and
    the -eps trajectories (independent nonlinear FD), GATES BOTH SIDES
    (G2R Issue 1), and forms the centered-FD matrix.  A column enters the
    acceptance comparison only when its derived pair classification is
    VALID_SMOOTH_FLOW (both sides VALID_SMOOTH_FLOW); per-side classes
    are always recorded (``plus`` / ``minus``) so the exact failing side
    and reason are never lost.
    """
    x0 = np.asarray(x0, dtype=float)
    sweep = {}
    for mult in multipliers:
        eps = base_step * mult
        fd = np.zeros((STATE_DIM, STATE_DIM))
        valid_cols = np.zeros(STATE_DIM, dtype=bool)
        cls_plus: list[str] = []
        cls_minus: list[str] = []
        pair: list[str] = []
        for j in range(STATE_DIM):
            e_j = np.eye(STATE_DIM)[:, j]
            d, meta = fixed_time_nonlinear_difference(
                mode, x0, j, float(eps[j]), t_span, env, vehicle, k, solver
            )
            cplus = gate_perturbed_trajectory(
                mode, x0 + eps[j] * e_j, t_span, env, vehicle, k, solver
            )
            cminus = gate_perturbed_trajectory(
                mode, x0 - eps[j] * e_j, t_span, env, vehicle, k, solver
            )
            cls_plus.append(cplus.value)
            cls_minus.append(cminus.value)
            pair.append(column_pair_class(cplus, cminus).value)
            if d is None:
                continue
            fd[:, j] = d
            if pair[-1] == "VALID_SMOOTH_FLOW":
                valid_cols[j] = True

        n_valid = int(valid_cols.sum())
        summary = {
            "multiplier": mult,
            "n_valid_columns": n_valid,
            "fd_matrix": [[float(fd[i, j]) for j in range(STATE_DIM)]
                          for i in range(STATE_DIM)],
            "classification_plus": cls_plus,
            "classification_minus": cls_minus,
            "classification": pair,
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