"""Phase-G5 terminal sensitivity (G5 -- event-conditioned descriptive).

For the two RESEARCH TERMINALS (Qian RTI = QEG feasibility loss; Sanger
SRTI = skip-capability loss) G5 computes the event-conditioned:

    eta_e = d t_e / d x_0 = - n^T Phi_e^- / (n^T f_e^-)        (4,)
    J_e   = d x_e / d x_0 = Phi_e^- + f_e^- eta_e (= (I - f n^T/(n^T f)) Phi)

with ``Phi_e^-`` the PRE-TERMINAL hybrid STM (all true switches before the
terminal, NO terminal saltation -- RTI / SRTI are RESEARCH_TERMINAL
events, never a Xi factor), ``n`` the terminal event surface normal and
``f_e^-`` the pre-terminal vector field.  Terminal tangency invariant:

    n^T J_e = 0.

Terminal-state map ``J_e`` is a state-to-state derivative for the
native event (perturbed terminal states occur at perturbed terminal
times), NEVER called a saltation and NEVER confused with the fixed-time
hybrid STM.  Native RTI and SRTI are different research terminals; their
sensitivities are DESCRIPTIVE and not a fair cross-model ranking.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability.ftle import (
    canonicalize_svd_signs,
    condition_status,
    numerical_rank,
)
from hyptraj.predictability.hybrid_stm import (
    DISCRETE_TO_JACOBIAN_MODE,
    build_split_tail,
    true_switch_events_before,
)
from hyptraj.predictability.metrics import scale_values_by_key
from hyptraj.predictability.scaling import canonical_candidate

_STATE_DIM = 4

# Expected frozen terminal kinds per model (G5R §1).
EXPECTED_TERMINAL_KIND = {
    "qian": "RTI",
    "sanger": "srti",
}
TERMINAL_NAME = {
    "qian": "RTI",
    "sanger": "SRTI",
}


class TerminalSensitivityEligibilityError(RuntimeError):
    """The actual frozen research terminal is NOT the expected research
    terminal (e.g. Qian ended with GROUND/MAX_TIME/SOLVER_FAILURE instead
    of RTI, or Sanger with ground/censor/failure/grazing instead of srti).
    Terminal sensitivity is only defined on the expected branch; no
    eta / J / terminal-SVD is computed on a wrong terminal."""


class NonTransverseTerminalError(RuntimeError):
    """The terminal event has an EXACT-ZERO or NONFINITE transversality
    denominator ``n^T f^-``; the standard first-order terminal event-time
    linearization is undefined.  Only exact-zero / nonfinite are rejected
    -- a small FINITE denominator is never threshold-rejected here (G6
    owns the near-grazing validity domain)."""


class TerminalGate(Enum):
    TOPOLOGY_PRESERVED = "TOPOLOGY_PRESERVED"
    TOPOLOGY_CHANGED = "TOPOLOGY_CHANGED"
    EVENT_ORDER_CHANGED = "EVENT_ORDER_CHANGED"
    GRAZING_CROSSED = "GRAZING_CROSSED"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


def validate_terminal_transversality(denominator) -> float:
    """Terminal transversality policy (G5R §5-§7).

    Escalate the scalar denominator to float and reject ONLY
    non-finite / exact-zero values with ``NonTransverseTerminalError``.
    A small finite denominator (e.g. 1e-12) is ACCEPTED -- no
    grazing / transversality numerical threshold is defined here (G6).
    """
    denom = float(denominator)
    if not np.isfinite(denom):
        raise NonTransverseTerminalError(
            f"Terminal denominator n^T f^- is not finite ({denom}).")
    if denom == 0.0:
        raise NonTransverseTerminalError(
            "Terminal denominator n^T f^- is exactly zero: standard "
            "first-order terminal event-time linearization is undefined "
            "(near-grazing validity is G6, not thresholded here).")
    return denom


def terminal_event_time_gradient(normal, phi_preterminal, f_minus) -> np.ndarray:
    """``eta_e = -n^T Phi_e^- / (n^T f_e^-)`` with transversality guard.

    Concentrates shape / finite / exact-zero-denominator checking and the
    frozen event-time formula in one helper (G5R §8), so future G6 never
    re-implements an unchecked division.  Only exact-zero / nonfinite
    denominators are rejected.
    """
    normal = np.asarray(normal, dtype=float)
    phi_preterminal = np.asarray(phi_preterminal, dtype=float)
    f_minus = np.asarray(f_minus, dtype=float)
    if normal.shape != (_STATE_DIM,) or phi_preterminal.shape != (
            _STATE_DIM, _STATE_DIM) or f_minus.shape != (_STATE_DIM,):
        raise ValueError("terminal_event_time_gradient received wrong shapes.")
    if not (np.all(np.isfinite(normal)) and np.all(np.isfinite(phi_preterminal))
            and np.all(np.isfinite(f_minus))):
        raise ValueError("terminal sensitivity inputs must be finite.")
    denom = validate_terminal_transversality(float(normal @ f_minus))
    return -normal @ phi_preterminal / denom


def _terminal_kind_and_time(result):
    if hasattr(result, "trajectory"):
        return (str(result.trajectory.terminal_kind),
                float(result.trajectory.terminal_time),
                np.asarray(result.trajectory.terminal_state, dtype=float))
    return (str(result.terminal_kind), float(result.terminal_time),
            np.asarray(result.terminal_state, dtype=float))


def _terminal_events(result):
    if hasattr(result, "events"):
        return list(result.events)
    return list(result.trajectory.events)


# ---------------------------------------------------------------------------
# Terminal surfaces
# ---------------------------------------------------------------------------
def qian_rti_event_surface_value(state, env, vehicle, k) -> float:
    """Frozen QEG-end event scalar ``g_R = L_req - L`` (SOURCE-mirror).

    Reproduces ``make_qeg_end_event`` exactly: ``L_req`` from
    ``required_lift`` and ``L`` from ``q S K C_D`` with the clamped
    density channel.
    """
    from hyptraj.models.aerodynamics import aerodynamic_forces
    from hyptraj.models.atmosphere import atmospheric_density
    from hyptraj.models.dynamics import required_lift

    state = np.asarray(state, dtype=float)
    r, _t, v, _gamma = state
    alt = max(r - env.earth_radius, 0.0)
    req = required_lift(state, env, vehicle)
    rho = atmospheric_density(alt, env)
    k_val = float(k.value) if isinstance(k, ConstantKControl) else float(k)
    aero = aerodynamic_forces(rho, v, k_val, vehicle)
    return float(req - aero.lift)


def qian_rti_terminal_normal(state, env, vehicle, k) -> np.ndarray:
    """Analytic ``n_RTI = grad_x(L_req - L)`` under constant K (G5 §34-§35).

    ``L_req = m (g - v^2/r) cos(gamma)`` with
    ``g = g0 (R_E/(R_E+h))^2``; ``L = q S K C_D`` with
    ``rho = rho0 exp(-h/H)``.  Partial derivatives:

    dg/dr = -2g/r ; drho/dr = -rho/H
    dL_req/dr = m(-2g/r + v^2/r^2) cos(gamma)
    dL_req/dv = -2 m v/r cos(gamma)
    dL_req/dg = -m (g - v^2/r) sin(gamma)
    dL/dr = -L/H ; dL/dv = 2L/v

    Validated against an independent centered-FD oracle on the frozen
    scalar surface in the G5 tests (SOURCE WINS; no frozen source changed).
    """
    from hyptraj.models.aerodynamics import aerodynamic_forces
    from hyptraj.models.atmosphere import atmospheric_density
    from hyptraj.models.gravity import gravity_acceleration

    state = np.asarray(state, dtype=float)
    r, _theta, v, gamma = state
    alt = r - env.earth_radius
    g = gravity_acceleration(alt, env)
    rho = atmospheric_density(max(alt, 0.0), env)
    k_val = float(k.value) if isinstance(k, ConstantKControl) else float(k)
    L = aerodynamic_forces(rho, v, k_val, vehicle).lift
    m = vehicle.mass
    h = env.scale_height
    dr = m * (-2.0 * g / r + v**2 / (r * r)) * np.cos(gamma) + L / h
    dv = -2.0 * m * v / r * np.cos(gamma) - 2.0 * L / v
    dg = -m * (g - v**2 / r) * np.sin(gamma)
    return np.array([dr, 0.0, dv, dg], dtype=float)


def srti_terminal_normal() -> np.ndarray:
    """``n_SRTI = [0,0,0,1]^T`` (surface ``g_S = gamma``, direction -1)."""
    return np.array([0.0, 0.0, 0.0, 1.0])


# ---------------------------------------------------------------------------
# TerminalSensitivityResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TerminalSensitivityResult:
    model: str
    terminal_name: str
    terminal_kind: str          # frozen structured terminal_kind ("RTI"/"srti")

    terminal_time: float
    terminal_state: np.ndarray
    topology_signature: tuple[str, ...]

    normal: np.ndarray
    f_minus: np.ndarray
    denominator: float

    phi_preterminal: np.ndarray
    event_time_gradient_initial: np.ndarray   # eta_e
    terminal_state_jacobian: np.ndarray       # J_e

    canonical_scale_key: str
    scaled_terminal_jacobian: np.ndarray
    singular_values: np.ndarray
    sigma_max: float
    rank: int
    nullity: int
    condition_status: str

    scaled_event_time_gradient: np.ndarray
    scaled_event_time_norm_seconds: float
    fractional_event_time_sensitivity: float

    terminal_surface_tangency_residual: float

    solver_label: str
    metadata: dict = field(default_factory=dict)

    @property
    def theta_terminal_time_residual(self) -> float:
        return float(abs(self.event_time_gradient_initial[1]))

    @property
    def theta_terminal_state_column_residual(self) -> float:
        return float(np.max(np.abs(
            self.terminal_state_jacobian[:, 1] - np.array([0., 1., 0., 0.]))))

    @property
    def srti_gamma_row_residual(self) -> float:
        if self.terminal_name == "SRTI":
            return float(np.max(np.abs(self.terminal_state_jacobian[3, :])))
        return float("nan")


def _qeg_trim_time(collector, capture_time: float, rti_time: float,
                   env, vehicle, k, u_eps: float = 1e-9) -> float:
    """Largest ``t < rti_time`` with ``u_L*(x(t)) <= 1 - u_eps``.

    The QEG-end (RTI) state has ``u_L* = 1`` which is the QEG clipping
    boundary where the smooth-interior Jacobian is NOT defined (G1 §9).
    The preterminal QEG factor is therefore integrated only up to a
    strict-interior trim time; the omitted boundary neighbourhood has
    length -> 0 and contributes ``O(u_eps)`` to the flow STM (negligible
    vs. the reference error).
    """
    from hyptraj.predictability.jacobian import u_l_star

    seg = None
    for s in collector.segments:
        if s.t_start <= capture_time and s.t_end >= rti_time - 1e-9:
            seg = s
            break
    if seg is None:
        raise RuntimeError("Qian QEG dense segment not found for the trim.")

    lo, hi = capture_time, rti_time

    def u_at(t):
        return u_l_star(np.asarray(seg.solution(t), dtype=float),
                        env, vehicle, k)

    # confirm u_L* crosses 1 - u_eps on [lo, hi]
    if u_at(lo) > 1.0 - u_eps:
        return lo
    if u_at(hi) < 1.0 - u_eps:
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if u_at(mid) <= 1.0 - u_eps:
            lo = mid
        else:
            hi = mid
    return lo


def check_terminal_eligibility(model: str, frozen_terminal_kind: str,
                               terminal_time: float) -> None:
    """G5R eligibility contract (Issue 1) as a pure helper.

    Terminal sensitivity is only defined when the actual frozen
    ``terminal_kind`` equals the expected research terminal (Qian ``RTI``,
    Sanger ``srti``).  Raises ``TerminalSensitivityEligibilityError``
    otherwise -- no eta / J / terminal-SVD is ever computed on a wrong
    terminal.  Reads only frozen structured metadata.
    """
    expected = EXPECTED_TERMINAL_KIND.get(model)
    if expected is None:
        raise ValueError(f"model must be 'qian' or 'sanger'; got {model!r}.")
    if str(frozen_terminal_kind) != expected:
        raise TerminalSensitivityEligibilityError(
            f"{TERMINAL_NAME[model]} terminal sensitivity requires "
            f"terminal_kind == {expected!r}, but the frozen trajectory "
            f"ended with terminal_kind = {frozen_terminal_kind!r} at "
            f"t = {terminal_time:.6f} s.")


def build_terminal_sensitivity(
    model: str,
    x0: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k=3.0,
    research_solver=None,
    stm_solver=None,
    scale_key: str | None = None,
    *,
    qian_trim_u_eps: float = 1e-9,
) -> TerminalSensitivityResult:
    """Analytic terminal sensitivity for Qian RTI / Sanger SRTI (G5 §30-§37).

    G5R eligibility contract: the terminal sensitivity is ONLY defined
    when the actual frozen ``terminal_kind`` equals the expected research
    terminal (Qian ``RTI``, Sanger ``srti``); otherwise
    ``TerminalSensitivityEligibilityError`` is raised and no eta / J /
    terminal-SVD is produced.  ``model`` must be exactly ``"qian"`` or
    ``"sanger"``.
    """
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    from hyptraj.modes.continuous_glide import QEG_GLIDE, continuous_glide_rhs
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs
    from hyptraj.predictability.stm import stm_strict_reference_config

    if model not in EXPECTED_TERMINAL_KIND:
        raise ValueError(
            f"model must be 'qian' or 'sanger'; got {model!r}.")
    if not (np.isfinite(qian_trim_u_eps) and 0.0 < qian_trim_u_eps < 1.0):
        raise ValueError(
            f"qian_trim_u_eps must satisfy 0 < u_eps < 1 finite; "
            f"got {qian_trim_u_eps!r}.")

    research_solver = research_solver or REFERENCE_SOLVER_CONFIG
    stm_solver = stm_solver or stm_strict_reference_config()
    scale_key = scale_key or canonical_candidate().key
    scales = scale_values_by_key(scale_key)
    x0 = np.asarray(x0, dtype=float)
    ctl = ConstantKControl(k)

    # ---- frozen research trajectory --------------------------------------
    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    collector = DenseOutputCollector()
    research_ic = InitialCondition(
        altitude=float(x0[0] - env.earth_radius),
        velocity=float(x0[2]),
        flight_path_angle_deg=float(np.rad2deg(x0[3])),
        range_angle=float(x0[1]))
    if model == "qian":
        traj = integrate_qian_research_trajectory(
            env, vehicle, research_ic, ctl,
            solver=research_solver, dense_output_collector=collector)
        initial_mode = "ENTRY_CAPTURE"
    elif model == "sanger":
        sanger = integrate_sanger_research_trajectory(
            env, vehicle, research_ic, ctl,
            solver=research_solver, dense_output_collector=collector)
        traj = sanger
        initial_mode = "SANGER_ATM"
    else:  # pragma: no cover -- guarded above
        raise ValueError(f"model must be 'qian' or 'sanger'; got {model!r}.")

    terminal_name = TERMINAL_NAME[model]
    frozen_kind, t_e, x_e = _terminal_kind_and_time(traj)

    # G5R eligibility guard (Issue 1): only the expected research terminal
    # may enter the terminal-sensitivity algebra.
    check_terminal_eligibility(model, frozen_kind, t_e)
    events = _terminal_events(traj)
    switches = true_switch_events_before(t_e, events)
    sig = tuple(sw["kind"] for sw in switches)

    # preterminal hybrid STM (no terminal saltation); the QIAN last QEG
    # factor is trimmed to a strict-interior neighbourhood of the RTI
    # clipping boundary (u_L* <= 1 - qian_trim_u_eps).  The omitted
    # boundary contribution is bounded by the trim-sensitivity convergence
    # audit (G5R §9-§14): ``Phi(t_eps,0) -> Phi^-_RTI`` as u_eps -> 0.
    pre_terminal_time = t_e
    if model == "qian":
        capture_time = next((sw["time"] for sw in switches
                             if sw["kind"] == "qian_capture"), None)
        if capture_time is not None:
            pre_terminal_time = _qeg_trim_time(collector, capture_time, t_e,
                                               env, vehicle, k,
                                               u_eps=qian_trim_u_eps)
    phi_pre = build_split_tail(model, 0.0, x0, initial_mode, pre_terminal_time,
                               events, env, vehicle, k, stm_solver=stm_solver)

    # terminal surface / normal / pre-terminal vector field
    if model == "qian":
        normal = qian_rti_terminal_normal(x_e, env, vehicle, k)
        f_minus = continuous_glide_rhs(QEG_GLIDE, t_e, x_e, env, vehicle, ctl)
    elif model == "sanger":
        normal = srti_terminal_normal()
        f_minus = sanger_atm_rhs(t_e, x_e, env, vehicle, ctl)
    else:  # pragma: no cover -- guarded above
        raise ValueError(f"model must be 'qian' or 'sanger'; got {model!r}.")

    denom = validate_terminal_transversality(float(normal @ f_minus))
    eta = terminal_event_time_gradient(normal, phi_pre, f_minus)
    J = phi_pre + np.outer(f_minus, eta)
    # n^T J_e = 0 is a 4-component row identity; report the max absolute.
    tangency = float(np.max(np.abs(normal @ J)))

    # scaled terminal metrics
    S = np.diag([float(scales[k]) for k in ("r", "theta", "v", "gamma")])
    S_inv = np.diag(1.0 / np.diag(S))
    J_tilde = S_inv @ J @ S
    u, sigma, vt = np.linalg.svd(J_tilde)
    u, v = canonicalize_svd_signs(u, vt.T)
    rank = numerical_rank(sigma)
    cond = condition_status(sigma)
    eta_S = eta @ S
    eta_norm_s = float(np.linalg.norm(eta_S))

    return TerminalSensitivityResult(
        model=model,
        terminal_name=terminal_name,
        terminal_kind=frozen_kind,
        terminal_time=t_e,
        terminal_state=x_e,
        topology_signature=sig,
        normal=normal,
        f_minus=f_minus,
        denominator=denom,
        phi_preterminal=phi_pre,
        event_time_gradient_initial=eta,
        terminal_state_jacobian=J,
        canonical_scale_key=scale_key,
        scaled_terminal_jacobian=J_tilde,
        singular_values=sigma,
        sigma_max=float(sigma[0]) if sigma.size else 0.0,
        rank=rank,
        nullity=int(_STATE_DIM - rank),
        condition_status=cond["condition_status"],
        scaled_event_time_gradient=eta_S,
        scaled_event_time_norm_seconds=eta_norm_s,
        fractional_event_time_sensitivity=eta_norm_s / t_e,
        terminal_surface_tangency_residual=tangency,
        solver_label=getattr(research_solver, "label", "custom"),
        metadata={
            "scales": dict(scales),
            "pre_terminal_trim_time": pre_terminal_time,
            "raw_dimensional_terminal_sigma_ANTI_EXAMPLE": list(
                np.linalg.svd(J, compute_uv=False)),
        },
    )


# ---------------------------------------------------------------------------
# Terminal nonlinear validation (G5 §40-§44)
# ---------------------------------------------------------------------------
def classify_terminal_side(
    model: str,
    nominal_kind: str,
    nominal_sig: tuple[str, ...],
    result,
) -> tuple[TerminalGate, dict]:
    """Terminal topology gate for one perturbed side (G5 §40-§41)."""
    if result is None:
        return TerminalGate.NUMERICAL_FAILURE, {"reason": "no_result"}
    kind, _t, _x = _terminal_kind_and_time(result)
    solver_fail = {"SOLVER_FAILURE", "solver_failure"}
    grazing = {"grazing_or_unresolved_event"}
    if kind in solver_fail:
        return TerminalGate.NUMERICAL_FAILURE, {"reason": "solver_failure"}
    if kind in grazing:
        return TerminalGate.GRAZING_CROSSED, {"reason": "grazing_or_unresolved"}
    if kind != nominal_kind:
        return TerminalGate.TOPOLOGY_CHANGED, {
            "reason": f"terminal_kind_changed:{kind}", "terminal_kind": kind}
    switches = true_switch_events_before(_t, _terminal_events(result))
    pert_sig = tuple(sw["kind"] for sw in switches)
    if pert_sig != nominal_sig:
        if (len(pert_sig) == len(nominal_sig)
                and Counter(pert_sig) == Counter(nominal_sig)):
            return TerminalGate.EVENT_ORDER_CHANGED, {
                "reason": "event_order_changed",
                "pert_signature": list(pert_sig)}
        return TerminalGate.TOPOLOGY_CHANGED, {
            "reason": "preterminal_signature_changed",
            "pert_signature": list(pert_sig)}
    return TerminalGate.TOPOLOGY_PRESERVED, {"reason": "ok",
                                             "terminal_kind": kind}


def terminal_fd_sweep(
    model: str,
    x0: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    research_solver,
    nominal_kind: str,
    nominal_sig: tuple[str, ...],
    eta: np.ndarray,
    J: np.ndarray,
    base_step,
    multipliers,
) -> dict:
    """Multi-epsilon terminal event-time + terminal-state FD (G5 §42-§44)."""
    from hyptraj.predictability.hybrid_validation import (
        HYBRID_FD_BASE_STEP,
        run_nonlinear_hybrid,
    )

    base_step = base_step if base_step is not None else HYBRID_FD_BASE_STEP
    x0 = np.asarray(x0, dtype=float)
    out = {}
    for mult in multipliers:
        eps = base_step * mult
        rec = {"multiplier": mult, "columns": {}}
        for j in range(_STATE_DIM):
            e_j = np.eye(_STATE_DIM)[:, j]
            vals = []
            for sign in (1.0, -1.0):
                result, _ = run_nonlinear_hybrid(
                    model, x0 + sign * eps[j] * e_j, env, vehicle, k,
                    research_solver)
                gate, info = classify_terminal_side(
                    model, nominal_kind, nominal_sig, result)
                if gate != TerminalGate.TOPOLOGY_PRESERVED:
                    vals.append((None, None, gate.value, info["reason"]))
                else:
                    t, x = _terminal_kind_and_time(result)[1:3]
                    vals.append((t, x, gate.value, info.get("reason", "ok")))
            t_p, x_p, c_p, r_p = vals[0]
            t_m, x_m, c_m, r_m = vals[1]
            d_t = None if (t_p is None or t_m is None) else \
                (t_p - t_m) / (2.0 * float(eps[j]))
            d_x = None if (x_p is None or x_m is None) else \
                (x_p - x_m) / (2.0 * float(eps[j]))
            rec["columns"][f"col_{j}"] = {
                "epsilon": float(eps[j]),
                "event_time_fd": (None if d_t is None else float(d_t)),
                "event_time_analytic": float(eta[j]),
                "event_time_abs_error": (None if d_t is None
                                         else abs(d_t - eta[j])),
                "event_time_material_rel_error": (
                    None if d_t is None or abs(eta[j]) <= 1e-12
                    else abs(d_t - eta[j]) / abs(eta[j])),
                "terminal_state_fd": (None if d_x is None
                                      else [float(v) for v in d_x]),
                "terminal_state_analytic": [float(v) for v in J[:, j]],
                "terminal_state_max_abs_error": (None if d_x is None else
                    float(np.max(np.abs(d_x - J[:, j])))),
                "classification_plus": c_p,
                "classification_minus": c_m,
                "reason_plus": r_p,
                "reason_minus": r_m,
            }
        out[f"mult_{mult:g}"] = rec
    return out

# ---------------------------------------------------------------------------
# Qian RTI strict-interior trim convergence audit (G5R §9-§14)
# ---------------------------------------------------------------------------
def qian_rti_trim_audit(
    x0: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k=3.0,
    research_solver=None,
    stm_solver=None,
    scale_key: str | None = None,
    u_eps_list=(1e-6, 1e-7, 1e-8, 1e-9, 1e-10),
    default_u_eps: float = 1e-9,
) -> dict:
    """Convergence evidence for the RTI strict-interior trim (G5R §10-§14).

    The scientific object is ``Phi^-_RTI = lim_{t -> t_RTI-} Phi(t, 0)``.
    build_terminal_sensitivity computes ``Phi(t_eps, 0)`` with
    ``u_L*(t_eps) = 1 - eps_u``; this audit verifies convergence as
    ``eps_u -> 0`` by comparing Phi / eta / J / scaled sigma_max at each
    ``u_eps`` relative to the default (1e-9).  ``build_split_tail`` is the
    only per-u_eps cost (the research trajectory is integrated once).
    """
    from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
    from hyptraj.modes.continuous_glide import QEG_GLIDE, continuous_glide_rhs
    from hyptraj.predictability.metrics import scale_values_by_key
    from hyptraj.predictability.stm import stm_strict_reference_config

    research_solver = research_solver or REFERENCE_SOLVER_CONFIG
    stm_solver = stm_solver or stm_strict_reference_config()
    scale_key = scale_key or canonical_candidate().key
    scales = scale_values_by_key(scale_key)
    x0 = np.asarray(x0, dtype=float)
    ctl = ConstantKControl(k)

    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )

    collector = DenseOutputCollector()
    traj = integrate_qian_research_trajectory(
        env, vehicle, InitialCondition(
            altitude=float(x0[0] - env.earth_radius),
            velocity=float(x0[2]),
            flight_path_angle_deg=float(np.rad2deg(x0[3])),
            range_angle=float(x0[1])),
        ctl, solver=research_solver, dense_output_collector=collector)
    frozen_kind, t_rti, x_e = _terminal_kind_and_time(traj)
    if frozen_kind != "RTI":
        raise TerminalSensitivityEligibilityError(
            f"Qian RTI trim audit requires terminal_kind == 'RTI'; got "
            f"{frozen_kind!r} at t = {t_rti:.6f} s.")
    events = _terminal_events(traj)
    switches = true_switch_events_before(t_rti, events)
    cap_t = next((sw["time"] for sw in switches
                  if sw["kind"] == "qian_capture"), None)
    if cap_t is None:
        raise RuntimeError("Qian capture not found for the trim audit.")
    f_minus = continuous_glide_rhs(QEG_GLIDE, t_rti, x_e, env, vehicle, ctl)
    normal = qian_rti_terminal_normal(x_e, env, vehicle, k)
    denom = validate_terminal_transversality(float(normal @ f_minus))
    S = np.diag([float(scales[v]) for v in ("r", "theta", "v", "gamma")])
    S_inv = np.diag(1.0 / np.diag(S))

    from hyptraj.predictability.ftle import numerical_rank

    results = {}
    for eps_u in u_eps_list:
        t_trim = _qeg_trim_time(collector, cap_t, t_rti, env, vehicle, k,
                                u_eps=eps_u)
        phi_pre = build_split_tail("qian", 0.0, x0, "ENTRY_CAPTURE", t_trim,
                                   events, env, vehicle, k, stm_solver=stm_solver)
        eta = terminal_event_time_gradient(normal, phi_pre, f_minus)
        J = phi_pre + np.outer(f_minus, eta)
        J_tilde = S_inv @ J @ S
        sigma = np.linalg.svd(J_tilde, compute_uv=False)
        results[eps_u] = {
            "u_eps": eps_u,
            "trim_time": t_trim,
            "t_rti_minus_trim": t_rti - t_trim,
            "phi_pre": phi_pre,
            "eta": eta,
            "J": J,
            "sigma_max": float(sigma[0]) if sigma.size else 0.0,
        }

    def mat_rel(a, b, key):
        da = results[a][key]
        db = results[b][key]
        if isinstance(da, np.ndarray) and da.ndim == 2:
            m = np.abs(db) >= 1e-8 * np.max(np.abs(db), initial=1e-300)
            denom = np.maximum(np.abs(db[m]), 1e-300) if m.any() else 1e-300
            return float(np.max(np.abs(da[m] - db[m]) / denom)) if m.any() else 0.0
        # vector
        m = np.abs(db) >= 1e-8 * np.max(np.abs(db), initial=1e-300)
        denom = np.maximum(np.abs(db[m]), 1e-300) if m.any() else 1e-300
        return float(np.max(np.abs(da[m] - db[m]) / denom)) if m.any() else 0.0

    rep = {}
    for eps_u in u_eps_list:
        r = results[eps_u]
        rep[eps_u] = {
            "trim_time": r["trim_time"],
            "t_rti_minus_trim": r["t_rti_minus_trim"],
            "phi_material_rel_vs_default": mat_rel(eps_u, default_u_eps, "phi_pre"),
            "eta_material_rel_vs_default": mat_rel(eps_u, default_u_eps, "eta"),
            "J_material_rel_vs_default": mat_rel(eps_u, default_u_eps, "J"),
            "sigma_max_rel_vs_default": (
                abs(r["sigma_max"] - results[default_u_eps]["sigma_max"])
                / results[default_u_eps]["sigma_max"]
                if results[default_u_eps]["sigma_max"] > 0 else None),
            "sigma_max": r["sigma_max"],
        }
    # consecutive-pair convergence in the accepted tail: prefer the
    # (1e-8, 1e-9) pair when present, else the two smallest u_eps supplied.
    avail = sorted(u_eps_list)
    if len(avail) >= 2 and 1e-8 in avail and 1e-9 in avail:
        pair_a, pair_b = 1e-8, 1e-9
    else:
        pair_a, pair_b = avail[-2], avail[-1]
    tail_rel = mat_rel(pair_a, pair_b, "phi_pre")
    return {
        "u_eps_list": list(u_eps_list),
        "default_u_eps": default_u_eps,
        "terminal_time": t_rti,
        "per_u_eps": rep,
        "consecutive_phi_material_rel_1e-8_vs_1e-9": tail_rel,
        "converged_below_reference_budget": bool(tail_rel < 1e-8),
    }
