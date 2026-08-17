"""Phase-G3 transverse hybrid saltation (G3).

G3 establishes and independently validates the event-local transverse
hybrid linearization for the three FROZEN true hybrid switches:

    * Qian Capture                  ENTRY_CAPTURE -> QEG_GLIDE
    * Sanger atmosphere exit        SANGER_ATM   -> SANGER_VAC
    * Sanger atmosphere entry       SANGER_VAC   -> SANGER_ATM

Event-time sensitivity (local):

    q_e = d t_e / d x^- = - n^T / (n^T f^-)          shape (4,), dt = q @ dx

Saltation matrix (identity-reset autonomous event, G0 §8):

    Xi = I + (f^+ - f^-) n^T / (n^T f^-)

with ``f^-`` = pre-event frozen RHS, ``f^+`` = post-event frozen RHS and
``n`` = event normal on the pre-event state.  Determinant lemma:

    det(Xi) = (n^T f^+) / (n^T f^-).

G3 differentiates the FROZEN hybrid event semantics; it never redesigns
them.  Scope: event-local transverse linearization ONLY.  No full hybrid
trajectory STM, no continuous-STMs chained across switches (G4), no RTI /
SRTI terminal sensitivity, no FTLE, no grazing anchors (G6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability.jacobian import (
    STATE_DIM,
    classify_qeg_active_set,
    qeg_distance_metrics,
    u_l_star,
)

# ---------------------------------------------------------------------------
# Exceptions and classification vocabulary (G3 §16, §21)
# ---------------------------------------------------------------------------
class NonTransverseEventError(ValueError):
    """Reject the standard transverse formula at an EXACT zero denominator
    (``n^T f^- == 0``).  Never divide by zero into inf/nan.  A small
    NONZERO denominator is NOT rejected here (G6 owns the grazing
    validity domain)."""


class NotHybridSwitchError(ValueError):
    """Raised when a saltation / event-time gradient is requested for an
    event that is NOT a Phase-G transverse hybrid switch (RTI / SRTI
    research terminals, pullout / apogee diagnostics, synthetic initial
    entry are ineligible)."""


class LocalEventValidationClass(Enum):
    """Local event validation classification (G3 §21)."""

    TRANSVERSE_LOCAL_VALID = "TRANSVERSE_LOCAL_VALID"
    WRONG_EVENT_DIRECTION = "WRONG_EVENT_DIRECTION"
    NO_LOCAL_ROOT = "NO_LOCAL_ROOT"
    ACTIVE_SET_CHANGED = "ACTIVE_SET_CHANGED"
    NONPHYSICAL_STATE = "NONPHYSICAL_STATE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


# ---------------------------------------------------------------------------
# Saltation eligibility (G3 §3, §4)
# ---------------------------------------------------------------------------
SALTATION_ELIGIBLE_EVENTS = frozenset(
    {"qian_capture", "sanger_atmosphere_exit", "sanger_atmosphere_entry"}
)

NON_SALTATION_EVENTS_REASONS = {
    "qian_rti": "RESEARCH_TERMINAL (no post-RTI mode, no saltation)",
    "sanger_srti": "RESEARCH_TERMINAL (no fake post-SRTI mode)",
    "sanger_atmospheric_pullout": "DIAGNOSTIC event (no mode change)",
    "sanger_vac_apogee": "DIAGNOSTIC event (no mode change)",
    "synthetic_initial_entry": "not a physical root crossing",
}


def assert_saltation_eligible(event_name: str) -> None:
    """Guard: saltation is defined ONLY for the three true hybrid switches."""
    if event_name in SALTATION_ELIGIBLE_EVENTS:
        return
    reason = NON_SALTATION_EVENTS_REASONS.get(
        event_name, "not a Phase-G transverse hybrid switch"
    )
    raise NotHybridSwitchError(
        f"event {event_name!r} has no saltation: {reason}."
    )


# ---------------------------------------------------------------------------
# Saltation algebra (G3 §5-§7, §14)
# ---------------------------------------------------------------------------
def _check_vector(v: np.ndarray, name: str) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    if v.shape != (STATE_DIM,):
        raise ValueError(f"{name} must be shape ({STATE_DIM},); got {v.shape}.")
    if not np.all(np.isfinite(v)):
        raise ValueError(f"{name} must be finite.")
    return v


def transversality_denominator(
    f_minus: np.ndarray,
    normal: np.ndarray,
) -> float:
    """``d_e = n^T f^-`` (G3 §7).  Pure evaluation; reports magnitude only.

    An exactly-zero denominator is rejected by the callers that build the
    transverse formulas; this function itself only evaluates (a PURE
    diagnostic with no division, so no inf/nan risk).
    """
    f_minus = _check_vector(f_minus, "f_minus")
    normal = _check_vector(normal, "normal")
    return float(float(normal @ f_minus))


def event_time_gradient(
    normal: np.ndarray,
    denominator: float | np.ndarray,
) -> np.ndarray:
    """``q_e = d t_e / d x^- = - n^T / (n^T f^-)``, shape ``(4,)``.

    Frozen sign convention (G0 §9 / G3 §6):
    ``delta t_e = q_e @ delta x^-``, ``q_e = -n^T / (n^T f^-)``.
    """
    normal = _check_vector(normal, "normal")
    denom = float(denominator)
    if denom == 0.0 or not np.isfinite(denom):
        raise NonTransverseEventError(
            "n^T f^- is exactly zero: standard transverse event-time "
            "gradient is undefined (G3 §7; grazing/nontransverse is G6)."
        )
    return -normal / denom


def identity_reset_saltation(
    f_minus: np.ndarray,
    f_plus: np.ndarray,
    normal: np.ndarray,
) -> np.ndarray:
    """``Xi = I + (f^+ - f^-) n^T / (n^T f^-)`` (G0 §8 boxed identity-reset form).

    Input guards: shapes ``(4,)`` / ``(4,)`` / ``(4,)``, all finite; an
    EXACTLY-zero denominator raises ``NonTransverseEventError`` (a small
    nonzero denominator is recorded, never auto-rejected at G3).
    """
    f_minus = _check_vector(f_minus, "f_minus")
    f_plus = _check_vector(f_plus, "f_plus")
    normal = _check_vector(normal, "normal")
    denom = float(normal @ f_minus)
    if denom == 0.0 or not np.isfinite(denom):
        raise NonTransverseEventError(
            "n^T f^- is exactly zero: standard transverse saltation is "
            "undefined (G3 §16; grazing/nontransverse is G6)."
        )
    return np.eye(STATE_DIM) + np.outer(f_plus - f_minus, normal) / denom


def saltation_matrix(
    reset_jacobian: np.ndarray,
    f_minus: np.ndarray,
    f_plus: np.ndarray,
    normal: np.ndarray,
) -> np.ndarray:
    """General autonomous saltation (G0 §8):

        Xi = DR + (f^+ - DR f^-) n^T / (n^T f^-).

    With ``DR = I`` this reduces exactly to :func:`identity_reset_saltation`
    (verified by the tests).
    """
    dr = np.asarray(reset_jacobian, dtype=float)
    if dr.shape != (STATE_DIM, STATE_DIM) or not np.all(np.isfinite(dr)):
        raise ValueError(
            f"reset_jacobian must be ({STATE_DIM},{STATE_DIM}) and finite."
        )
    f_minus = _check_vector(f_minus, "f_minus")
    f_plus = _check_vector(f_plus, "f_plus")
    normal = _check_vector(normal, "normal")
    denom = float(normal @ f_minus)
    if denom == 0.0 or not np.isfinite(denom):
        raise NonTransverseEventError(
            "n^T f^- is exactly zero: standard transverse saltation is "
            "undefined (G3 §16)."
        )
    return dr + np.outer(f_plus - dr @ f_minus, normal) / denom


def saltation_determinant_lemma(
    f_minus: np.ndarray,
    f_plus: np.ndarray,
    normal: np.ndarray,
) -> float:
    """``det(Xi) = (n^T f^+) / (n^T f^-)`` (G3 §14 algebraic cross-check)."""
    f_minus = _check_vector(f_minus, "f_minus")
    f_plus = _check_vector(f_plus, "f_plus")
    normal = _check_vector(normal, "normal")
    den_minus = float(normal @ f_minus)
    if den_minus == 0.0:
        raise NonTransverseEventError("n^T f^- is exactly zero (lemma undefined).")
    return float(normal @ f_plus) / den_minus


# ---------------------------------------------------------------------------
# Hybrid local linearization container (G3 §15)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HybridLocalLinearization:
    """Event-local hybrid linearization (no full-trajectory STM stored)."""

    event_name: str
    event_index: int
    time: float
    state: np.ndarray
    mode_before: str
    mode_after: str

    normal: np.ndarray
    f_minus: np.ndarray
    f_plus: np.ndarray
    reset_jacobian: np.ndarray

    denominator: float
    event_time_gradient: np.ndarray
    saltation_matrix: np.ndarray

    event_resolution: str
    metadata: dict = field(default_factory=dict)

    @property
    def abs_denominator(self) -> float:
        return abs(self.denominator)

    @property
    def determinant(self) -> float:
        return float(np.linalg.det(self.saltation_matrix))


# ---------------------------------------------------------------------------
# Event extraction (G3 §9-§12) -- base linearizations from frozen results
# ---------------------------------------------------------------------------
_QIAN_CAPTURE_NORMAL = np.array([0.0, 0.0, 0.0, 1.0])


def _as_research_solver(solver):
    """Coerce an elapsed/G3 solver to a trajectory ``SolverConfig``.

    The frozen research integrators require a ``SolverConfig``
    (``simulation/trajectory.py``).  A G2 ``StmSolverConfig`` is converted
    using its ``state_atol`` for the 4 state channels (same DOP853
    semantics); ``None`` defaults to the frozen production config.
    """
    from hyptraj.predictability.stm import StmSolverConfig
    from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
    from hyptraj.simulation.trajectory import SolverConfig

    if solver is None:
        return PRODUCTION_SOLVER_CONFIG
    if isinstance(solver, StmSolverConfig):
        return SolverConfig(
            method="DOP853",
            rtol=solver.rtol,
            atol=np.asarray(solver.state_atol, dtype=float).copy(),
            max_step=solver.max_step,
            dense_output=True,
        )
    return solver


def _qian_capture_linearization(
    env, vehicle, initial, control, solver=None, mode_after="QEG_GLIDE",
) -> HybridLocalLinearization:
    from hyptraj.modes.continuous_glide import ENTRY_CAPTURE, QEG_GLIDE
    from hyptraj.models.dynamics import atmospheric_dynamics
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )

    k_val = float(control.value) if isinstance(control, ConstantKControl) \
        else float(control)
    ctl = control if isinstance(control, ConstantKControl) \
        else ConstantKControl(k_val)
    traj = integrate_qian_research_trajectory(
        env, vehicle, initial, ctl, solver=_as_research_solver(solver)
    )
    cap = traj.capture_event
    if cap is None:
        raise RuntimeError("Qian research trajectory has no capture event.")
    state = np.asarray(cap.state, dtype=float)
    t = float(cap.time_s)

    def _mode_rhs(name, x):
        if name == ENTRY_CAPTURE:
            return atmospheric_dynamics(t, x, env, vehicle, ctl)
        from hyptraj.modes.continuous_glide import continuous_glide_rhs
        return continuous_glide_rhs(
            QEG_GLIDE if name == "QEG_GLIDE" else name,
            t, x, env, vehicle, ctl,
        )

    f_minus = _mode_rhs(ENTRY_CAPTURE, state)
    f_plus = _mode_rhs(mode_after, state)
    normal = _QIAN_CAPTURE_NORMAL.copy()

    denom = transversality_denominator(f_minus, normal)
    q = event_time_gradient(normal, denom)
    xi = identity_reset_saltation(f_minus, f_plus, normal)

    # QEG active-set audit at the exact capture state (G3 §10).
    try:
        us = u_l_star(state, env, vehicle, k_val)
        aset = classify_qeg_active_set(us).value
    except ValueError:
        us, aset = None, "DEGENERATE_L_LE_0"
    d0, d1 = (qeg_distance_metrics(us) if us is not None else (None, None))

    return HybridLocalLinearization(
        event_name="qian_capture",
        event_index=0,
        time=t,
        state=state,
        mode_before=ENTRY_CAPTURE,
        mode_after="QEG_GLIDE",
        normal=normal,
        f_minus=f_minus,
        f_plus=f_plus,
        reset_jacobian=np.eye(STATE_DIM),
        denominator=denom,
        event_time_gradient=q,
        saltation_matrix=xi,
        event_resolution="SOLVER_EVENT",
        metadata={
            "capture_u_l_star": us,
            "capture_active_set": aset,
            "distance_to_0": d0,
            "distance_to_1": d1,
        },
    )


def extract_qian_capture(
    env, vehicle, initial, k=3.0,
    solver=None,
):
    """Baseline Qian Capture hybrid local linearization (gamma0=-5, K)."""
    ctl = ConstantKControl(k)
    return _qian_capture_linearization(env, vehicle, initial, ctl, solver=solver)


def _sanger_switch_linearization(
    event,
    env, vehicle, control,
    solver_tolerance=None,
) -> HybridLocalLinearization:
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs, sanger_vac_rhs
    from hyptraj.simulation.sanger_events import atmosphere_interface_normal
    from hyptraj.simulation.sanger_trajectory import (
        ATMOSPHERE_EXIT,
        ATMOSPHERE_ENTRY,
        SANGER_ATM as SANGER_ATM_STR,
        SANGER_VAC as SANGER_VAC_STR,
    )

    state = np.asarray(event.state, dtype=float)
    t = float(event.time)
    is_exit = event.kind == ATMOSPHERE_EXIT
    mode_before = SANGER_ATM_STR if is_exit else SANGER_VAC_STR
    mode_after = SANGER_VAC_STR if is_exit else SANGER_ATM_STR
    f_minus = (sanger_atm_rhs(t, state, env, vehicle, control)
               if is_exit else sanger_vac_rhs(t, state, env, vehicle))
    f_plus = (sanger_vac_rhs(t, state, env, vehicle)
              if is_exit else sanger_atm_rhs(t, state, env, vehicle, control))
    normal = atmosphere_interface_normal()

    # Metadata crosscheck: recompute f_minus / f_plus and compare with the
    # FROZEN HybridEventRecord stored values (metadata integrity test).
    f_minus_record = np.asarray(event.f_minus, dtype=float)
    f_plus_record = np.asarray(event.f_plus, dtype=float)
    meta_err = {
        "f_minus_metadata_abs_err": float(np.max(np.abs(f_minus_record - f_minus))),
        "f_plus_metadata_abs_err": float(np.max(np.abs(f_plus_record - f_plus))),
        "normal_metadata_match": bool(np.array_equal(
            np.asarray(event.normal, dtype=float), normal)),
    }

    denom = transversality_denominator(f_minus, normal)
    q = event_time_gradient(normal, denom)
    xi = identity_reset_saltation(f_minus, f_plus, normal)

    return HybridLocalLinearization(
        event_name=("sanger_atmosphere_exit" if is_exit
                    else "sanger_atmosphere_entry"),
        event_index=int(event.index),
        time=t,
        state=state,
        mode_before=mode_before,
        mode_after=mode_after,
        normal=normal,
        f_minus=f_minus,
        f_plus=f_plus,
        reset_jacobian=np.eye(STATE_DIM),
        denominator=denom,
        event_time_gradient=q,
        saltation_matrix=xi,
        event_resolution="SOLVER_EVENT",
        metadata={
            "mode_before": mode_before,
            "mode_after": mode_after,
            "f_minus_metadata_abs_err": meta_err["f_minus_metadata_abs_err"],
            "f_plus_metadata_abs_err": meta_err["f_plus_metadata_abs_err"],
            "normal_metadata_match": meta_err["normal_metadata_match"],
        },
    )


def extract_sanger_switches(
    env, vehicle, initial, k=3.0, solver=None,
) -> list[HybridLocalLinearization]:
    """All real solver-resolved ATM<->VAC switches of the baseline SRTI_N2.

    Synthetic initial entry, pullout, apogee and SRTI are excluded;
    ``DENSE_RECOVERED`` exits remain the same physical ATM->VAC switch
    (resolution metadata only) but the G3 normal acceptance set prefers
    the solver-resolved baseline events.
    """
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )
    from hyptraj.simulation.sanger_trajectory import (
        ATMOSPHERE_ENTRY,
        ATMOSPHERE_EXIT,
    )

    ctl = ConstantKControl(k)
    traj = integrate_sanger_research_trajectory(
        env, vehicle, initial, ctl, solver=_as_research_solver(solver)
    )
    out = []
    for ev in traj.events:
        if ev.kind not in (ATMOSPHERE_ENTRY, ATMOSPHERE_EXIT):
            continue
        lin = _sanger_switch_linearization(ev, env, vehicle, ctl)
        # recovered events: same physics; mark resolution metadata.
        if any(abs(r.time_s - lin.time) < 1e-9 for r in traj.recovered_events):
            lin = HybridLocalLinearization(
                **{k: getattr(lin, k) for k in (
                    "event_name", "event_index", "time", "state",
                    "mode_before", "mode_after", "normal", "f_minus", "f_plus",
                    "reset_jacobian", "denominator", "event_time_gradient",
                    "saltation_matrix",
                )},
                event_resolution="DENSE_RECOVERED",
                metadata=lin.metadata,
            )
        out.append(lin)
    return out


# ---------------------------------------------------------------------------
# Local nonlinear validation (G3 §17-§23)
# ---------------------------------------------------------------------------
def _solver_tolerances(solver, state_dim=STATE_DIM):
    from hyptraj.predictability.stm import StmSolverConfig

    if isinstance(solver, StmSolverConfig):
        return solver.rtol, solver.state_atol, solver.max_step
    return solver.rtol, solver.atol, solver.max_step


def local_event_crossing_time(
    rhs_before: Callable[[np.ndarray], np.ndarray],
    event_surface: Callable[[float, np.ndarray], float],
    x_eps: np.ndarray,
    solver,
    horizon_s: float = 200.0,
) -> tuple[float | None, np.ndarray | None, dict]:
    """Nearest event-surface crossing time ``tau`` (signed) from ``x_eps``.

    Local problem: at ``tau = 0`` the state is ``x_eps``; propagate with
    the FROZEN pre-event RHS and locate the NEAREST zero of the event
    surface (crossing may be before ``tau=0`` or after -- the flow can
    only go one way, so we search both flow directions via ``+f`` and
    ``-f``, whichever keeps the surface root nearest).  No sampled-grid
    crossing: a terminal event root is located by the solver.  Returns
    ``(tau, x_at_crossing, meta)``; ``tau`` is ``None`` when no local root
    is found within ``horizon_s``.
    """
    from scipy.integrate import solve_ivp

    x_eps = np.asarray(x_eps, dtype=float)
    rtol, atol, max_step = _solver_tolerances(solver)

    # Frozen event surface wrapper (terminal, direction-agnostic: we want
    # the NEAREST crossing regardless of side).
    def _ev(t, state, *args):
        return float(event_surface(t, state))

    _ev.terminal = True
    _ev.direction = 0

    f0 = np.asarray(rhs_before(x_eps), dtype=float)
    g0 = float(event_surface(0.0, x_eps))

    def _dir_deriv():
        h = 1e-6
        gp = float(event_surface(0.0, x_eps + h * f0))
        gm = float(event_surface(0.0, x_eps - h * f0))
        return (gp - gm) / (2.0 * h)

    dgdt = _dir_deriv()
    if abs(g0) < 1e-13:
        return 0.0, x_eps.copy(), {"method": "tangent", "surface_residual": abs(g0)}
    if abs(dgdt) < 1e-300:
        return None, None, {"reason": "zero_directional_derivative"}

    tau_lin = -g0 / dgdt  # first-order root-time estimate (direction only)
    candidates = [1.0, -1.0] if tau_lin >= 0 else [-1.0, 1.0]
    for sign in candidates:
        rhs_eff = (lambda t, x, s=sign: s * np.asarray(rhs_before(x), dtype=float))
        try:
            sol = solve_ivp(
                rhs_eff, (0.0, horizon_s), x_eps,
                method="DOP853", rtol=rtol, atol=atol, max_step=max_step,
                dense_output=True, events=[_ev],
            )
        except ValueError:
            continue
        if not sol.success:
            continue
        if sol.t_events is not None and sol.t_events[0].size > 0:
            root_clock = float(sol.t_events[0][0])
            x_root = np.asarray(sol.y[:, -1], dtype=float)
            return sign * root_clock, x_root, {
                "tau_lin": tau_lin, "dgdt": dgdt, "surface_residual": abs(g0),
                "search_direction": sign,
            }
    return None, None, {"reason": "no_local_root", "tau_lin": tau_lin}


def _integrate_duration(current_rhs, x0, duration):
    """Integrate ``current_rhs`` from ``x0`` for a signed duration."""
    from scipy.integrate import solve_ivp

    x0 = np.asarray(x0, dtype=float)
    if abs(duration) < 1e-12:
        return x0.copy()
    dt = float(duration)
    rhs = (lambda t, x: np.asarray(current_rhs(x), dtype=float)) if dt >= 0 \
        else (lambda t, x: -np.asarray(current_rhs(x), dtype=float))
    sol = solve_ivp(rhs, (0.0, abs(dt)), x0,
                    method="DOP853", rtol=1e-12,
                    atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
                    max_step=0.05, dense_output=True)
    if not sol.success:
        raise RuntimeError(f"local duration integration failed: {sol.message}")
    return np.asarray(sol.y[:, -1], dtype=float)


def synchronized_post_event_map(
    rhs_before,
    rhs_after,
    event_surface,
    x_e: np.ndarray,
    delta_x: np.ndarray,
    solver,
) -> tuple[np.ndarray | None, dict]:
    """Nonlinear synchronized event map ``M(delta x) = y^+`` (G3 §19-§20).

    1. pre-event flow root ``tau`` from ``x_e + delta_x``;
    2. perturbed event state ``x_e,delta`` (identity reset: ``x+ = x-``);
    3. post-event flow ``-tau`` from ``x_e,delta`` to synchronise with the
       nominal event time.

    ``M(0) = x_e`` and ``DM(0) = Xi`` (validated by FD sweeps).
    """
    x_e = np.asarray(x_e, dtype=float)
    x_eps = x_e + np.asarray(delta_x, dtype=float)
    tau, x_event, meta = local_event_crossing_time(
        rhs_before, event_surface, x_eps, solver
    )
    if tau is None:
        return None, meta
    # identity reset: x+ = x-
    y_plus = _integrate_duration(rhs_after, x_event, -tau)
    meta = {**meta, "tau": tau, "x_event": x_event}
    return y_plus, meta


def classify_local_side(
    mode_after: str,
    x_event: np.ndarray | None,
    tau: float | None,
    meta: dict,
    env,
    vehicle,
    k,
    check_qeg_interior: bool,
) -> LocalEventValidationClass:
    """Classify one +/- perturbed local side (G3 §21)."""
    if tau is None:
        reason = meta.get("reason")
        return (
            LocalEventValidationClass.NUMERICAL_FAILURE
            if reason == "zero_directional_derivative"
            else LocalEventValidationClass.NO_LOCAL_ROOT
        )
    if x_event is None:
        return LocalEventValidationClass.NUMERICAL_FAILURE
    alt = float(x_event[0] - env.earth_radius)
    if alt <= 0.0:
        return LocalEventValidationClass.NONPHYSICAL_STATE
    if check_qeg_interior:
        try:
            us = u_l_star(x_event, env, vehicle, k)
        except ValueError:
            return LocalEventValidationClass.ACTIVE_SET_CHANGED
        if classify_qeg_active_set(us) != classify_qeg_active_set(0.5):
            return LocalEventValidationClass.ACTIVE_SET_CHANGED
    return LocalEventValidationClass.TRANSVERSE_LOCAL_VALID


# ---------------------------------------------------------------------------
# Local validation FD sweeps (G3 §20-§23)
# ---------------------------------------------------------------------------
# Local FD RESEARCH base step (G0 candidate-B); NEVER canonical scaling.
LOCAL_FD_BASE_STEP = np.array([100.0, 1e-5, 1.0, 1e-4])
LOCAL_FD_MULTIPLIERS = (1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0)


def local_flows_for(event_name, env, vehicle, k):
    """Frozen pre/post RHS pairs for the three transverse hybrid switches.

    ``rhs(state)`` closures over the FROZEN mode RHS (no second physics);
    returns ``(rhs_before, rhs_after)``.
    """
    from hyptraj.modes.continuous_glide import QEG_GLIDE, continuous_glide_rhs
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs, sanger_vac_rhs

    ctl = ConstantKControl(k)

    if event_name == "qian_capture":
        def before(x):
            from hyptraj.models.dynamics import atmospheric_dynamics
            return atmospheric_dynamics(0.0, np.asarray(x, dtype=float),
                                        env, vehicle, ctl)

        def after(x):
            return continuous_glide_rhs(
                QEG_GLIDE, 0.0, np.asarray(x, dtype=float), env, vehicle, ctl
            )
        return before, after

    if event_name == "sanger_atmosphere_exit":
        def before(x):
            return sanger_atm_rhs(0.0, np.asarray(x, dtype=float), env, vehicle, ctl)

        def after(x):
            return sanger_vac_rhs(0.0, np.asarray(x, dtype=float), env, vehicle)
        return before, after

    if event_name == "sanger_atmosphere_entry":
        def before(x):
            return sanger_vac_rhs(0.0, np.asarray(x, dtype=float), env, vehicle)

        def after(x):
            return sanger_atm_rhs(0.0, np.asarray(x, dtype=float), env, vehicle, ctl)
        return before, after

    raise NotHybridSwitchError(f"{event_name!r} has no local hybrid flow pair.")


def event_surface_for(event_name, env):
    """Frozen scalar event surface for the local-crossing problem."""
    from hyptraj.simulation.sanger_events import atmosphere_interface_value

    if event_name == "qian_capture":
        return lambda t, x: float(x[3])
    if event_name in ("sanger_atmosphere_exit", "sanger_atmosphere_entry"):
        return lambda t, x: atmosphere_interface_value(
            np.asarray(x, dtype=float), env)
    raise NotHybridSwitchError(f"{event_name!r} has no event surface.")


def event_time_fd_sweep(
    lin: HybridLocalLinearization,
    rhs_before,
    event_surface,
    env, vehicle, k,
    solver,
    base_step=LOCAL_FD_BASE_STEP,
    multipliers=LOCAL_FD_MULTIPLIERS,
    check_qeg_interior=False,
) -> dict:
    """Multi-epsilon event-time FD ``dt/dx`` vs analytic ``q_e`` (G3 §17, §22)."""
    x_e = lin.state
    q_analytic = lin.event_time_gradient
    out = {}
    for mult in multipliers:
        eps = base_step * mult
        rec = {"multiplier": mult, "columns": {}}
        for j in range(STATE_DIM):
            e_j = np.eye(STATE_DIM)[:, j]
            tau_p, xp, mp = local_event_crossing_time(
                rhs_before, event_surface, x_e + eps[j] * e_j, solver)
            tau_m, xm, mm = local_event_crossing_time(
                rhs_before, event_surface, x_e - eps[j] * e_j, solver)
            cls_p = classify_local_side(lin.mode_after, xp, tau_p, mp, env,
                                        vehicle, k, check_qeg_interior)
            cls_m = classify_local_side(lin.mode_after, xm, tau_m, mm, env,
                                        vehicle, k, check_qeg_interior)
            analytic = float(q_analytic[j])
            if tau_p is not None and tau_m is not None:
                fd = (float(tau_p) - float(tau_m)) / (2.0 * float(eps[j]))
            else:
                fd = None
            abs_err = None if fd is None else abs(fd - analytic)
            material = abs(analytic) > 1e-12
            rel_err = None
            if material and abs_err is not None:
                rel_err = abs_err / abs(analytic)
            rec["columns"][f"col_{j}"] = {
                "epsilon": float(eps[j]),
                "tau_plus": (None if tau_p is None else float(tau_p)),
                "tau_minus": (None if tau_m is None else float(tau_m)),
                "fd_dt_dx": (None if fd is None else fd),
                "analytic_dt_dx": analytic,
                "absolute_error": abs_err,
                "material_relative_error": rel_err,
                "classification_plus": cls_p.value,
                "classification_minus": cls_m.value,
            }
        out[f"mult_{mult:g}"] = rec
    return out


def saltation_local_map_fd_sweep(
    lin: HybridLocalLinearization,
    rhs_before,
    rhs_after,
    event_surface,
    env, vehicle, k,
    solver,
    base_step=LOCAL_FD_BASE_STEP,
    multipliers=LOCAL_FD_MULTIPLIERS,
    check_qeg_interior=False,
) -> dict:
    """Multi-epsilon saltation local-map FD ``DM dx`` vs ``Xi`` (G3 §19-§20, §23)."""
    x_e = lin.state
    xi = lin.saltation_matrix
    out = {}
    for mult in multipliers:
        eps = base_step * mult
        rec = {"multiplier": mult, "columns": {}}
        for j in range(STATE_DIM):
            e_j = np.eye(STATE_DIM)[:, j]
            mp_, mp = synchronized_post_event_map(
                rhs_before, rhs_after, event_surface, x_e, eps[j] * e_j, solver)
            mm_, mm = synchronized_post_event_map(
                rhs_before, rhs_after, event_surface, x_e, -eps[j] * e_j, solver)
            cls_p = classify_local_side(
                lin.mode_after, mp.get("x_event"), mp.get("tau"), mp, env,
                vehicle, k, check_qeg_interior)
            cls_m = classify_local_side(
                lin.mode_after, mm.get("x_event"), mm.get("tau"), mm, env,
                vehicle, k, check_qeg_interior)
            if mp_ is not None and mm_ is not None:
                fd_col = (mp_ - mm_) / (2.0 * float(eps[j]))
            else:
                fd_col = None
            abs_err = None if fd_col is None else float(
                np.max(np.abs(fd_col - xi[:, j])))
            material = float(np.max(np.abs(xi[:, j]))) > 1e-12
            rel_err = None
            if material and abs_err is not None:
                rel_err = abs_err / float(np.max(np.abs(xi[:, j])))
            rec["columns"][f"col_{j}"] = {
                "epsilon": float(eps[j]),
                "fd_column": (None if fd_col is None
                              else [float(v) for v in fd_col]),
                "analytic_column": [float(v) for v in xi[:, j]],
                "absolute_error": abs_err,
                "material_relative_error": rel_err,
                "classification_plus": cls_p.value,
                "classification_minus": cls_m.value,
            }
        out[f"mult_{mult:g}"] = rec
    return out
