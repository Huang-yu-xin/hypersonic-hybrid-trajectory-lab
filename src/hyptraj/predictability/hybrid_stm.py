"""Phase-G4 hybrid STM chaining (G4).

G4 composes the G2-validated continuous-mode STMs and the G3-validated
transverse saltation matrices into the fixed-time, topology-preserving
hybrid flow state transition matrix:

    Phi_H(T, t0) = C_{N+1} Xi_N C_N ... Xi_2 C_2 Xi_1 C_1

with (incremental convention, G4 §0):

    Phi_global = I
    Phi_global = C @ Phi_global          # continuous segment
    Phi_minus   = Phi_global             # immediately before true switch k
    eta_k       = q_local_k @ Phi_minus  # global event-time gradient
    Phi_global = Xi @ Phi_global         # saltation
    ...
    Phi_global = C_final @ Phi_global    # final continuous segment

``eta_k = d t_{e_k} / d x_0 = q_k Phi_k^-`` (G4 §19).

Initial discrete-mode semantics (G4 §5): the continuous-state derivative
is conditional on the FROZEN initial discrete-mode rule -- Qian
``ENTRY_CAPTURE``; Sanger ``SANGER_ATM`` via the synthetic E0 (NO
saltation, NO Xi at t=0).  Diagnostic events (pullout / VAC apogee),
RTI / SRTI terminals and the synthetic initial entry are NOT matrix
factors.  G4 is fixed-time topology-preserving hybrid flow derivative;
no G5 predictability ranking, no grazing, no FTLE.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability.saltation import (
    linearize_qian_capture_event,
    linearize_sanger_event_record,
)
from hyptraj.predictability.stm import integrate_continuous_stm

TRUE_SWITCH_KINDS = frozenset({
    "qian_capture",
    "sanger_atmosphere_exit",
    "sanger_atmosphere_entry",
})

# Discrete-mode label -> G1/G2 jacobian-mode vocabulary (G1 §3/G2 §5).
DISCRETE_TO_JACOBIAN_MODE = {
    "ENTRY_CAPTURE": "entry_capture",
    "QEG_GLIDE": "qeg_interior",
    "SANGER_ATM": "sanger_atm",
    "SANGER_VAC": "sanger_vac",
}


def jacobian_mode(discrete_mode: str) -> str:
    """Map a discrete-mode label to the G1/G2 Jacobian mode string."""
    try:
        return DISCRETE_TO_JACOBIAN_MODE[discrete_mode]
    except KeyError:
        raise ValueError(f"unknown discrete mode {discrete_mode!r}") from None

# Kinds that must NEVER become a matrix factor.
DIAGNOSTIC_KINDS = frozenset({
    "sanger_atmospheric_pullout",
    "sanger_vac_apogee",
    "synthetic_initial_entry",
    "qian_rti",
    "sanger_srti",
    "ground_before_capture",
    "ground_after_capture_before_rti",
    "ground_before_srti",
})


# ---------------------------------------------------------------------------
# Factor / cumulative / result containers (G4 §8)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HybridFactor:
    """One hybrid STM matrix factor (continuous segment or saltation)."""

    kind: str                    # "CONTINUOUS" | "SALTATION" | "SALTATION_NAIVE"
    mode: str | None             # continuous mode, or event mode_before/after
    event_name: str | None       # saltation event name (None for continuous)
    t_start: float
    t_end: float
    matrix: np.ndarray
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class HybridEventCumulative:
    """Cumulative hybrid sensitivity at one true switch (G4 §8.2)."""

    event_name: str
    event_index: int
    event_time: float
    phi_minus_initial: np.ndarray     # Phi_k^- (from x0 to pre-switch)
    q_local: np.ndarray               # d t_e / d x_e^-
    event_time_gradient_initial: np.ndarray   # eta_k = q @ Phi_minus
    xi: np.ndarray
    phi_plus_initial: np.ndarray      # Phi_k^+ = Xi @ Phi_minus
    denominator: float
    event_resolution: str


@dataclass(frozen=True)
class HybridStmResult:
    """Fixed-time hybrid STM result (no dense trajectory arrays)."""

    model: str                       # "qian" | "sanger"
    t0: float
    t_final: float
    x0: np.ndarray
    x_final: np.ndarray              # frozen nonlinear state at T
    initial_mode: str
    endpoint_mode: str
    topology_signature: tuple[str, ...]
    factors: tuple[HybridFactor, ...]
    event_cumulatives: tuple[HybridEventCumulative, ...]
    phi_final: np.ndarray            # raw physical hybrid STM Phi_H(T,t0)
    solver_label: str
    terminal_margin: float           # T distance to research terminal (s)
    event_margins: tuple[float, ...] # T distance to each true switch (s)
    computational_scaling_metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# True-switch extraction (G4 §23, §15)
# ---------------------------------------------------------------------------
def true_switch_events_before(t_scan: float, events) -> list[dict]:
    """Chronological true-hybrid-switch events before ``t_scan``.

    Filters out diagnostics / terminals / synthetic E0; reads from the
    frozen structured event records (never assumes an event count).
    ``events`` is a sequence of objects exposing ``kind``/``index``/
    ``time`` (Sanger ``HybridEventRecord``) or with a ``kind`` plus
    ``time_s`` (Qian ``QianResearchEvent``).
    """
    out = []
    for ev in events:
        kind = ev.kind
        if kind == "capture":
            kind = "qian_capture"
        elif kind == "atmosphere_exit":
            kind = "sanger_atmosphere_exit"
        elif kind == "atmosphere_entry":
            kind = "sanger_atmosphere_entry"
        if kind not in TRUE_SWITCH_KINDS:
            continue
        _t = getattr(ev, "time", None)
        if _t is None:
            _t = getattr(ev, "time_s", None)
        t = float(_t)
        if t >= t_scan:
            continue
        out.append({"kind": kind, "index": int(getattr(ev, "index", 0)),
                    "time": t, "event": ev})
    # ensure chronological order
    out.sort(key=lambda d: d["time"])
    return out


def event_margins_to(t_scan: float, events) -> tuple[float, ...]:
    return tuple(round(abs(t_scan - d["time"]), 12)
                 for d in true_switch_events_before(t_scan, events))


def _initial_condition_from_state(
    x0: np.ndarray, env: EnvironmentParams,
) -> InitialCondition:
    x0 = np.asarray(x0, dtype=float)
    return InitialCondition(
        altitude=float(x0[0] - env.earth_radius),
        velocity=float(x0[2]),
        flight_path_angle_deg=float(np.rad2deg(x0[3])),
        range_angle=float(x0[1]),
    )


# ---------------------------------------------------------------------------
# Hybrid STM builder (G4 §9-§14)
# ---------------------------------------------------------------------------
def build_hybrid_stm(
    model: str,
    x0: np.ndarray,
    t_final: float,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k=3.0,
    research_solver=None,
    stm_solver=None,
    computational_scaling: np.ndarray | None = None,
    include_saltation: bool = True,
) -> HybridStmResult:
    """Build the fixed-time hybrid STM ``Phi_H(t_final, 0)``.

    ``x0`` is the full ``[r, theta, v, gamma]`` initial continuous state.
    ``research_solver`` (trajectory ``SolverConfig``) fixes the nominal
    event times/states; ``stm_solver`` (G2 ``StmSolverConfig``) drives the
    continuous factors.  Continuous factors come from G2
    ``integrate_continuous_stm`` (each restored to the physical raw STM);
    saltation factors come from the G3 ``linearize_*`` adapters.  With
    ``include_saltation=False`` the saltation factors are replaced by the
    identity (Qian no-saltation negative control; NEVER a production
    result).
    """
    model = model
    x0 = np.asarray(x0, dtype=float)
    k_float = float(k)
    ctl = ConstantKControl(k_float)
    initial = _initial_condition_from_state(x0, env)

    # ---- integrate the FROZEN research trajectory once --------------------
    from hyptraj.simulation.dense_output import DenseOutputCollector
    from hyptraj.simulation.qian_research_trajectory import (
        integrate_qian_research_trajectory,
    )
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    collector = DenseOutputCollector()
    events = []
    terminal_time = float("inf")
    if model == "qian":
        traj = integrate_qian_research_trajectory(
            env, vehicle, initial, ctl,
            solver=research_solver, dense_output_collector=collector,
        )
        events = list(traj.events)
        terminal_time = traj.terminal_time
        initial_mode = "ENTRY_CAPTURE"
    else:
        sanger = integrate_sanger_research_trajectory(
            env, vehicle, initial, ctl,
            solver=research_solver, dense_output_collector=collector,
        )
        events = list(sanger.trajectory.events)
        terminal_time = sanger.trajectory.terminal_time
        initial_mode = "SANGER_ATM"

    switches = true_switch_events_before(t_final, events)

    # ---- factor chain ------------------------------------------------------
    factors: list[HybridFactor] = []
    cumulatives: list[HybridEventCumulative] = []
    phi_global = np.eye(4)
    t_prev = 0.0
    x_prev = np.array([float(x0[0]), float(x0[1]), float(x0[2]),
                       float(x0[3])], dtype=float)
    mode = initial_mode

    for sw in switches:
        kind = sw["kind"]
        t_e = sw["time"]
        x_e = np.asarray(sw["event"].state, dtype=float)
        # continuous factor to the pre-switch side
        C = integrate_continuous_stm(
            jacobian_mode(mode), x_prev, (t_prev, t_e), env, vehicle, k_float,
            solver=stm_solver, computational_scaling=computational_scaling,
        )
        if not C.success:
            raise RuntimeError(f"{model}: continuous factor failed ({mode}).")
        factors.append(HybridFactor(
            kind="CONTINUOUS", mode=mode, event_name=None,
            t_start=t_prev, t_end=t_e, matrix=C.phi, source="G2:integrate_continuous_stm",
            metadata={"state_continuity_error": float(
                np.max(np.abs(C.x1 - x_e)))},
        ))
        phi_global = C.phi @ phi_global
        phi_minus = phi_global

        # saltation (G3 adapter; identity for the negative control)
        if model == "qian":
            lin = linearize_qian_capture_event(env, vehicle, ctl, x_e, t_e)
        else:
            lin = linearize_sanger_event_record(sw["event"], env, vehicle, ctl)
        xi = np.eye(4) if not include_saltation else lin.saltation_matrix
        factors.append(HybridFactor(
            kind=("SALTATION" if include_saltation else "SALTATION_NAIVE"),
            mode=None, event_name=kind, t_start=t_e, t_end=t_e, matrix=xi,
            source=("G3:linearize_*" if include_saltation
                    else "NAIVE no-saltation identity (negative control)"),
        ))
        phi_plus = xi @ phi_minus
        eta = lin.event_time_gradient @ phi_minus
        cumulatives.append(HybridEventCumulative(
            event_name=kind,
            event_index=sw["index"],
            event_time=t_e,
            phi_minus_initial=phi_minus,
            q_local=lin.event_time_gradient,
            event_time_gradient_initial=eta,
            xi=xi,
            phi_plus_initial=phi_plus,
            denominator=lin.denominator,
            event_resolution=lin.event_resolution,
        ))
        phi_global = phi_plus
        x_prev = x_e
        t_prev = t_e
        mode = lin.mode_after

    # final continuous factor [last_event, T]
    C_final = integrate_continuous_stm(
        jacobian_mode(mode), x_prev, (t_prev, t_final), env, vehicle, k_float,
        solver=stm_solver, computational_scaling=computational_scaling,
    )
    if not C_final.success:
        raise RuntimeError(f"{model}: final continuous factor failed ({mode}).")
    factors.append(HybridFactor(
        kind="CONTINUOUS", mode=mode, event_name=None,
        t_start=t_prev, t_end=t_final, matrix=C_final.phi,
        source="G2:integrate_continuous_stm",
        metadata={},
    ))
    phi_global = C_final.phi @ phi_global

    # fixed-time endpoint via the frozen nonlinear dense output
    x_final, endpoint_mode = _fixed_time_state(collector.segments, t_final)

    return HybridStmResult(
        model=model,
        t0=0.0,
        t_final=float(t_final),
        x0=x0,
        x_final=x_final,
        initial_mode=initial_mode,
        endpoint_mode=endpoint_mode,
        topology_signature=tuple(sw["kind"] for sw in switches),
        factors=tuple(factors),
        event_cumulatives=tuple(cumulatives),
        phi_final=phi_global,
        solver_label=getattr(research_solver, "label", "custom"),
        terminal_margin=float(terminal_time - t_final),
        event_margins=event_margins_to(t_final, events),
        computational_scaling_metadata={
            "computational_scaling": (
                None if computational_scaling is None
                else [float(v) for v in computational_scaling]),
            "note": "COMPUTATIONAL REPRESENTATION ONLY (continuous factors restored "
                    "to physical raw STM); NOT canonical scientific scaling",
        },
    )


def _fixed_time_state(
    segments: tuple, t: float,
) -> tuple[np.ndarray, str]:
    """Exact fixed-time state/mode from a frozen dense-output segment set."""
    for seg in segments:
        if float(seg.t_start) <= float(t) <= float(seg.t_end):
            state = np.asarray(seg.solution(float(t)), dtype=float)
            return state, str(seg.mode)
    raise ValueError(f"t = {t} lies outside the collected segment domain.")


# ---------------------------------------------------------------------------
# Qian no-saltation negative control (G4 §13, §39)
# ---------------------------------------------------------------------------
def qian_no_saltation_negative_control(
    x0: np.ndarray,
    t_final: float,
    env, vehicle, k=3.0,
    research_solver=None,
    stm_solver=None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(phi_correct, phi_naive)`` for the Qian chain.

    ``phi_correct = C_QEG Xi_capture C_ENTRY``;
    ``phi_naive   = C_QEG I C_ENTRY`` (deliberately omits the Capture
    saltation -- a diagnostic comparator, NEVER a production result).
    """
    correct = build_hybrid_stm(
        "qian", x0, t_final, env, vehicle, k,
        research_solver=research_solver, stm_solver=stm_solver,
        include_saltation=True,
    ).phi_final
    naive = build_hybrid_stm(
        "qian", x0, t_final, env, vehicle, k,
        research_solver=research_solver, stm_solver=stm_solver,
        include_saltation=False,
    ).phi_final
    return correct, naive

def _linearize_by_kind(kind, sw_event, env, vehicle, ctl):
    """Dispatch the G3 event-local linearizer by event kind."""
    if kind == "qian_capture":
        t = getattr(sw_event, "time", None)
        if t is None:
            t = getattr(sw_event, "time_s")
        from hyptraj.predictability.saltation import linearize_qian_capture_event

        return linearize_qian_capture_event(
            env, vehicle, ctl, np.asarray(sw_event.state, dtype=float), float(t))
    from hyptraj.predictability.saltation import linearize_sanger_event_record

    return linearize_sanger_event_record(sw_event, env, vehicle, ctl)


def build_split_tail(
    model: str,
    t_start: float,
    x_start: np.ndarray,
    mode_start: str,
    t_final: float,
    events,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k=3.0,
    stm_solver=None,
) -> np.ndarray:
    """Hybrid STM ``Phi_H(t_final, t_start)`` from an interior anchor.

    Used by the hybrid split / composition audit (G4 §18):
    ``Phi_H(T, 0) = Phi_H(T, t_a) @ Phi_mode(t_a, 0)``.  ``events`` are the
    FROZEN structured event records of the same nominal trajectory;
    ``x_start`` / ``mode_start`` are the exact anchor state / discrete
    mode at ``t_start``.  Continuous factors run between exact stored
    event states (G4 §17), saltation factors come from G3 adapters.
    """
    switches = [
        s for s in true_switch_events_before(t_final, events)
        if s["time"] >= t_start - 1e-9
    ]
    ctl = ConstantKControl(k)
    phi = np.eye(4)
    t_prev = float(t_start)
    x_prev = np.asarray(x_start, dtype=float)
    mode = mode_start
    for sw in switches:
        C = integrate_continuous_stm(
            jacobian_mode(mode), x_prev, (t_prev, sw["time"]),
            env, vehicle, k, solver=stm_solver)
        phi = C.phi @ phi
        lin = _linearize_by_kind(sw["kind"], sw["event"], env, vehicle, ctl)
        phi = lin.saltation_matrix @ phi
        x_prev = np.asarray(sw["event"].state, dtype=float)
        t_prev = sw["time"]
        mode = lin.mode_after
    C_last = integrate_continuous_stm(
        jacobian_mode(mode), x_prev, (t_prev, t_final),
        env, vehicle, k, solver=stm_solver)
    phi = C_last.phi @ phi
    return phi
