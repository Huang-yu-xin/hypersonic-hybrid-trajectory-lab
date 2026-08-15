"""Trajectory integration and the standardized result container."""

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.metrics.trajectory_metrics import compute_trajectory_metrics
from hyptraj.modes.continuous_glide import (
    ENTRY_CAPTURE,
    GROUND_CONTINUATION,
    QEG_GLIDE,
    continuous_glide_rhs,
    qeg_lift_fraction,
)
from hyptraj.models.dynamics import (
    atmospheric_dynamics,
    derived_quantities,
    required_lift,
)
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.dense_output import (
    DenseOutputCollector,
    DenseSolutionSegment,
)
from hyptraj.simulation.events import (
    make_capture_event,
    make_ground_event,
    make_qeg_end_event,
)

MU = 9.81 * 6_371_000.0**2  # mu = g0 * Re^2 [m^3/s^2] (spherical model)


@dataclass(frozen=True)
class SolverConfig:
    """Numerical configuration of the Phase B baseline integration.

    Component-scaled absolute tolerances follow the state scales
    ``[r, theta, v, gamma]`` in [m], [rad], [m/s], [rad].

    These are Phase B reference settings, *not* the final paper settings;
    the systematic solver / tolerance comparison happens in Phase C.
    """

    method: str = "DOP853"
    rtol: float = 1e-8
    atol: np.ndarray = field(
        default_factory=lambda: np.array([1e-3, 1e-10, 1e-6, 1e-10])
    )
    max_step: float = 10.0
    t_span: tuple[float, float] = (0.0, 5000.0)
    dense_output: bool = True
    output_points: int = 2000


DEFAULT_SOLVER_CONFIG = SolverConfig()


@dataclass
class TrajectoryResult:
    """Standardized container for one integrated trajectory.

    ``state`` has shape ``(4, N)`` with rows ``[r, theta, v, gamma]`` sampled
    on the uniform grid ``time``.  ``derived`` holds per-point physical
    quantities, ``metrics`` the scalar summary, ``events`` the detected
    event information and ``metadata`` the full reproducibility record.

    For the approved Qian glide result, ``mode`` holds the per-sample mode
    label (``ENTRY_CAPTURE`` / ``QEG_GLIDE`` / ``GROUND_CONTINUATION``) and
    ``control_history`` the per-sample control quantities (``u_L``,
    ``sigma_deg``, ``K_aero``, ``K_eff``, ``lift_required_n``).
    """

    time: np.ndarray
    state: np.ndarray
    derived: dict[str, np.ndarray]
    metrics: dict[str, float]
    events: dict[str, Any]
    metadata: dict[str, Any]
    mode: np.ndarray | None = None
    control_history: dict[str, np.ndarray] | None = None


def integrate_trajectory(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control: Callable[[float, np.ndarray], float],
    solver: SolverConfig | None = None,
) -> TrajectoryResult:
    """Integrate the planar atmospheric dynamics until ground impact.

    The integration runs with the configured solver until the terminal
    ground event (``h = 0``, descending crossing) is detected by
    ``solve_ivp`` root detection.  The adaptive solver nodes are then
    re-sampled on a uniform grid of ``solver.output_points`` points in
    ``[0, t_f]`` via the dense output, and the derived quantities and
    summary metrics are computed on that grid.

    Raises
    ------
    RuntimeError
        If the integration fails, or no ground event is detected within
        ``solver.t_span`` (the experiment must never silently accept that).
    """
    solver = solver or DEFAULT_SOLVER_CONFIG

    state0 = np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ],
        dtype=float,
    )

    ground_event = make_ground_event(env)

    solution = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        solver.t_span,
        state0,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=ground_event,
    )

    if not solution.success:
        raise RuntimeError(
            f"Trajectory integration failed: {solution.message}"
        )

    if solution.t_events[0].size == 0:
        raise RuntimeError(
            f"Ground event not detected within t_span={solver.t_span}; "
            "the trajectory did not reach the ground."
        )

    impact_time = float(solution.t_events[0][0])

    # Uniform output grid from the dense output (adaptive nodes are not a
    # valid final data sampling).
    time_grid = np.linspace(0.0, impact_time, solver.output_points)
    state_grid = solution.sol(time_grid)  # shape (4, N)

    derived = _compute_derived_grid(
        time_grid,
        state_grid,
        env,
        vehicle,
        control,
    )

    metrics = compute_trajectory_metrics(
        time_s=time_grid,
        altitude_m=derived["altitude_m"],
        range_m=derived["range_m"],
        velocity_mps=state_grid[2],
        dynamic_pressure_pa=derived["dynamic_pressure_pa"],
    )

    ground_residual = float(abs(solution.y[0, -1] - env.earth_radius))
    metrics["ground_event_altitude_residual_m"] = ground_residual

    events = {
        "ground_detected": True,
        "ground_time_s": impact_time,
        "ground_event_altitude_residual_m": ground_residual,
    }

    metadata = {
        "trajectory_type": "qian_continuous_glide",
        "initial_conditions": {
            "h0_m": initial.altitude,
            "v0_mps": initial.velocity,
            "gamma0_deg": initial.flight_path_angle_deg,
            "theta0_rad": initial.range_angle,
        },
        "vehicle_parameters": {
            "mass_kg": vehicle.mass,
            "reference_area_m2": vehicle.reference_area,
            "drag_coefficient": vehicle.drag_coefficient,
        },
        "environment_parameters": {
            "earth_radius_m": env.earth_radius,
            "gravity_sea_level_mps2": env.gravity_sea_level,
            "density_sea_level_kgm3": env.density_sea_level,
            "scale_height_m": env.scale_height,
            "atmosphere_boundary_m": env.atmosphere_boundary,
        },
        "control": {
            "type": type(control).__name__,
            "K": getattr(control, "value", None),
        },
        "solver": {
            "method": solver.method,
            "rtol": solver.rtol,
            "atol": [float(a) for a in solver.atol],
            "max_step": solver.max_step,
            "dense_output": solver.dense_output,
            "t_span": [float(x) for x in solver.t_span],
            "output_points": solver.output_points,
        },
        "integration": {
            "success": bool(solution.success),
            "message": solution.message,
            "nfev": int(solution.nfev),
            "ground_event_detected": True,
            "ground_event_time_s": impact_time,
        },
    }

    return TrajectoryResult(
        time=time_grid,
        state=state_grid,
        derived=derived,
        metrics=metrics,
        events=events,
        metadata=metadata,
    )


def integrate_qian_glide(
    env: EnvironmentParams,
    vehicle: VehicleParams,
    initial: InitialCondition,
    control: Callable[[float, np.ndarray], float],
    solver: SolverConfig | None = None,
    dense_output_collector: DenseOutputCollector | None = None,
) -> TrajectoryResult:
    """Integrate the APPROVED Qian continuous-glide baseline (dual endpoint).

    Event-driven three-mode integration (Phase B.5, DECISION:
    FREEZE-DUAL-ENDPOINT-QIAN):

    * ``ENTRY_CAPTURE``: literal Eq.(4) dynamics, ``u_L = 1``, terminated
      by the first upward zero crossing of ``gamma`` (QEG capture, a hybrid
      control switch);
    * ``QEG_GLIDE``: ``u_L = clip(L_req/L, 0, 1)``, terminated by the first
      post-capture upward crossing of ``u_L* = 1`` (``L_req = L``) -- the
      Research Terminal Interface (QEG feasibility loss);
    * ``GROUND_CONTINUATION``: literal Eq.(4) dynamics, ``u_L = 1``,
      continued naturally to the ground event ``h = 0`` (problem
      compatibility only, NOT a terminal-guidance law).

    No state value is modified at any transition; no altitude clipping is
    used.  Saltation-matrix handling across the hybrid capture event is
    deferred to the predictability phase (documented in metadata).

    ``dense_output_collector`` (E0.1 amendment) is an opt-in observer
    hook: when passed, the solver dense interpolants already computed by
    this function are exposed as ``DenseSolutionSegment`` objects (one
    per stage, in integration order).  The default ``None`` leaves every
    existing call byte-identical; the hook never re-integrates and never
    alters results.  Collected solutions are runtime-only and must not be
    serialized into canonical artifacts.

    Raises
    ------
    RuntimeError
        If any stage fails or its terminating event is not detected.
    """
    solver = solver or DEFAULT_SOLVER_CONFIG

    state0 = np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ],
        dtype=float,
    )

    # ---- Stage 0: ENTRY_CAPTURE ------------------------------------------
    sol_cap = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        solver.t_span,
        state0,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=[make_capture_event()],
    )
    if not sol_cap.success or sol_cap.t_events[0].size == 0:
        raise RuntimeError(
            f"QEG capture event not detected ({sol_cap.message})."
        )
    t_capture = float(sol_cap.t_events[0][0])
    state_capture = sol_cap.sol(t_capture)
    if dense_output_collector is not None:
        dense_output_collector.add(
            DenseSolutionSegment(
                index=0,
                name=ENTRY_CAPTURE,
                mode=ENTRY_CAPTURE,
                t_start=0.0,
                t_end=t_capture,
                solution=sol_cap.sol,
            )
        )

    # ---- Stage 1: QEG_GLIDE ----------------------------------------------
    sol_qeg = solve_ivp(
        lambda t, y: continuous_glide_rhs(
            QEG_GLIDE, t, y, env, vehicle, control),
        (t_capture, solver.t_span[1]),
        state_capture,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=[make_qeg_end_event(env, vehicle, control)],
    )
    if not sol_qeg.success or sol_qeg.t_events[0].size == 0:
        raise RuntimeError(
            f"QEG feasibility-loss (RTI) event not detected ({sol_qeg.message})."
        )
    t_rti = float(sol_qeg.t_events[0][0])
    state_rti = sol_qeg.sol(t_rti)
    if dense_output_collector is not None:
        dense_output_collector.add(
            DenseSolutionSegment(
                index=1,
                name=QEG_GLIDE,
                mode=QEG_GLIDE,
                t_start=t_capture,
                t_end=t_rti,
                solution=sol_qeg.sol,
            )
        )

    # ---- Stage 2: GROUND_CONTINUATION ------------------------------------
    ground = make_ground_event(env)
    sol_gnd = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (t_rti, solver.t_span[1]),
        state_rti,
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=solver.dense_output,
        events=[ground],
    )
    if not sol_gnd.success or sol_gnd.t_events[0].size == 0:
        raise RuntimeError(
            f"Ground event not detected in GROUND_CONTINUATION ({sol_gnd.message})."
        )
    t_ground = float(sol_gnd.t_events[0][0])
    state_ground = sol_gnd.sol(t_ground)
    if dense_output_collector is not None:
        dense_output_collector.add(
            DenseSolutionSegment(
                index=2,
                name=GROUND_CONTINUATION,
                mode=GROUND_CONTINUATION,
                t_start=t_rti,
                t_end=t_ground,
                solution=sol_gnd.sol,
            )
        )

    # ---- assemble uniform grids per stage --------------------------------
    n_pts = [400, 1200, 1200]  # ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION
    grids, states = [], []
    for n, (ta, tb, sol) in zip(
        n_pts,
        [
            (0.0, t_capture, sol_cap),
            (t_capture, t_rti, sol_qeg),
            (t_rti, t_ground, sol_gnd),
        ],
    ):
        t = np.linspace(ta, tb, n)
        grids.append(t)
        states.append(sol.sol(t))
    modes = np.concatenate([
        np.full(n_pts[0], ENTRY_CAPTURE, dtype=object),
        np.full(n_pts[1], QEG_GLIDE, dtype=object),
        np.full(n_pts[2], GROUND_CONTINUATION, dtype=object),
    ])
    time = np.concatenate(grids)
    state = np.concatenate(states, axis=1)

    # ---- derived quantities + control history -----------------------------
    derived = _compute_derived_grid(time, state, env, vehicle, control)

    energy = np.empty(time.size)
    lift_required = np.empty(time.size)
    u_L = np.empty(time.size)
    K_aero = np.empty(time.size)
    for i in range(time.size):
        energy[i] = 0.5 * state[2, i] ** 2 - MU / state[0, i]
        lift_required[i] = required_lift(state[:, i], env, vehicle)
        K_aero[i] = control(time[i], state[:, i])
        u_L[i] = (
            qeg_lift_fraction(time[i], state[:, i], env, vehicle, control)
            if modes[i] == QEG_GLIDE
            else 1.0
        )
    derived["energy_jpkg"] = energy
    derived["lift_required_n"] = lift_required
    control_history = {
        "u_L": u_L,
        "sigma_deg": np.degrees(np.arccos(np.clip(u_L, 0.0, 1.0))),
        "K_aero": K_aero,
        "K_eff": K_aero * u_L,
        "lift_required_n": lift_required,
    }

    # ---- metrics: dual-endpoint schema ------------------------------------
    q = derived["dynamic_pressure_pa"]
    h = derived["altitude_m"]
    rng = derived["range_m"]
    v = state[2]
    gamma = state[3]

    rti_idx = n_pts[0] + n_pts[1] - 1
    metrics: dict[str, float] = {
        # research terminal interface (RTI) metrics on [0, t_RTI]
        "research_terminal_time_s": t_rti,
        "research_terminal_range_km": float(rng[rti_idx] / 1000.0),
        "research_terminal_altitude_km": float(h[rti_idx] / 1000.0),
        "research_terminal_velocity_mps": float(v[rti_idx]),
        "research_terminal_gamma_deg": float(np.degrees(gamma[rti_idx])),
        "research_terminal_energy_jpkg": float(energy[rti_idx]),
        # ground continuation metrics on [0, t_ground]
        "ground_time_s": t_ground,
        "ground_range_km": float(rng[-1] / 1000.0),
        "ground_velocity_mps": float(v[-1]),
        "ground_gamma_deg": float(np.degrees(gamma[-1])),
        # QEG segment statistics
        "qeg_capture_time_s": t_capture,
        "qeg_duration_s": t_rti - t_capture,
        "qeg_range_gain_km": float((rng[rti_idx] - rng[n_pts[0] - 1]) / 1000.0),
        "max_bank_angle_deg": float(np.max(control_history["sigma_deg"][
            n_pts[0]:rti_idx + 1])),
        "median_bank_angle_deg": float(np.median(control_history["sigma_deg"][
            n_pts[0]:rti_idx + 1])),
        # legacy full-flight metrics (ground-compatible; backward compatible)
        "flight_time_s": t_ground,
        "range_km": float(rng[-1] / 1000.0),
        "terminal_velocity_mps": float(v[-1]),
        "max_altitude_km": float(np.max(h) / 1000.0),
        "max_dynamic_pressure_pa": float(np.max(q)),
        "dynamic_pressure_integral_pas": float(np.trapezoid(q, time)),
        "ground_event_altitude_residual_m": float(
            abs(state_ground[0] - env.earth_radius)
        ),
    }

    # ---- events + metadata -------------------------------------------------
    ground_residual = metrics["ground_event_altitude_residual_m"]
    events = {
        "ground_detected": True,
        "ground_time_s": t_ground,
        "ground_event_altitude_residual_m": ground_residual,
        "capture_event": {
            "g_capture": "gamma",
            "direction": +1,
            "terminal": True,
            "hybrid_switch": True,
            "time_s": t_capture,
            "state": [float(x) for x in state_capture],
        },
        "research_terminal_interface": {
            "reason": "qeg_feasibility_loss",
            "time_s": t_rti,
            "state": [float(x) for x in state_rti],
        },
    }

    dq_rti = derived_quantities(t_rti, state_rti, env, vehicle, control)
    metadata = {
        "trajectory_type": "qian_continuous_glide",
        "modes": [ENTRY_CAPTURE, QEG_GLIDE, GROUND_CONTINUATION],
        "research_terminal_reason": "qeg_feasibility_loss",
        "qeg_feasibility_condition": "u_L_star <= 1",
        "capture_event_is_hybrid_switch": True,
        "stm_ftle_note": (
            "Cross-capture STM/FTLE must account for the hybrid event "
            "sensitivity / saltation update. Saltation matrix NOT "
            "implemented in Phase B.5; deferred to the predictability phase."
        ),
        "control_semantics": {
            "K_aero": "L/D = 3 (aerodynamic, fixed)",
            "u_L": "cos(sigma), effective longitudinal lift projection, in [0,1]",
            "K_eff": "K_aero * u_L (reported only, never replaces K_aero)",
        },
        "research_terminal_state": {
            "t_RTI": t_rti,
            "r_RTI": float(state_rti[0]),
            "h_RTI": float(state_rti[0] - env.earth_radius),
            "theta_RTI": float(state_rti[1]),
            "R_RTI": float(env.earth_radius * state_rti[1]),
            "v_RTI": float(state_rti[2]),
            "gamma_RTI": float(state_rti[3]),
            "E_RTI": float(0.5 * state_rti[2] ** 2 - MU / state_rti[0]),
            "q_RTI": dq_rti["dynamic_pressure_pa"],
            "L_RTI": dq_rti["lift_n"],
            "L_req_RTI": float(required_lift(state_rti, env, vehicle)),
            "u_L_RTI": 1.0,
        },
        "initial_conditions": {
            "h0_m": initial.altitude,
            "v0_mps": initial.velocity,
            "gamma0_deg": initial.flight_path_angle_deg,
            "theta0_rad": initial.range_angle,
        },
        "vehicle_parameters": {
            "mass_kg": vehicle.mass,
            "reference_area_m2": vehicle.reference_area,
            "drag_coefficient": vehicle.drag_coefficient,
        },
        "environment_parameters": {
            "earth_radius_m": env.earth_radius,
            "gravity_sea_level_mps2": env.gravity_sea_level,
            "density_sea_level_kgm3": env.density_sea_level,
            "scale_height_m": env.scale_height,
            "atmosphere_boundary_m": env.atmosphere_boundary,
        },
        "control": {
            "type": type(control).__name__,
            "K": getattr(control, "value", None),
        },
        "solver": {
            "method": solver.method,
            "rtol": solver.rtol,
            "atol": [float(a) for a in solver.atol],
            "max_step": solver.max_step,
            "dense_output": solver.dense_output,
            "t_span": [float(x) for x in solver.t_span],
            "output_points": [int(x) for x in n_pts],
        },
        "integration": {
            "success": True,
            "message": "all three terminating events detected",
            "stages": {
                "entry_capture": {"nfev": int(sol_cap.nfev), "event_time_s": t_capture},
                "qeg_glide": {"nfev": int(sol_qeg.nfev), "event_time_s": t_rti},
                "ground_continuation": {"nfev": int(sol_gnd.nfev), "event_time_s": t_ground},
            },
            "ground_event_detected": True,
            "ground_event_time_s": t_ground,
        },
    }

    return TrajectoryResult(
        time=time,
        state=state,
        derived=derived,
        metrics=metrics,
        events=events,
        metadata=metadata,
        mode=modes,
        control_history=control_history,
    )


def run_sanity_checks(result: TrajectoryResult) -> dict[str, bool]:
    """Automatic sanity checks on a completed trajectory result.

    Returns a dict of named checks; the baseline experiment treats any
    ``False`` as an error.
    """
    checks: dict[str, bool] = {}

    checks["integration_success"] = bool(
        result.metadata["integration"]["success"]
    )
    checks["ground_event_detected"] = bool(result.events["ground_detected"])

    checks["state_finite"] = bool(np.all(np.isfinite(result.state)))
    checks["derived_finite"] = bool(
        all(np.all(np.isfinite(v)) for v in result.derived.values())
    )

    checks["velocity_positive"] = bool(np.all(result.state[2] > 0.0))
    checks["density_nonnegative"] = bool(
        np.all(result.derived["density_kgm3"] >= 0.0)
    )
    checks["dynamic_pressure_nonnegative"] = bool(
        np.all(result.derived["dynamic_pressure_pa"] >= 0.0)
    )
    checks["drag_nonnegative"] = bool(np.all(result.derived["drag_n"] >= 0.0))
    checks["lift_nonnegative"] = bool(np.all(result.derived["lift_n"] >= 0.0))

    checks["terminal_altitude_near_zero"] = bool(
        result.events["ground_event_altitude_residual_m"] <= 1.0
    )

    checks["range_forward"] = _range_moves_forward(result.derived["range_m"])

    return checks


def _compute_derived_grid(
    time_grid: np.ndarray,
    state_grid: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    control: Callable[[float, np.ndarray], float],
) -> dict[str, np.ndarray]:
    """Evaluate the derived physical quantities at every output-grid point."""
    keys = [
        "altitude_m",
        "range_m",
        "density_kgm3",
        "dynamic_pressure_pa",
        "drag_n",
        "lift_n",
    ]
    values: dict[str, np.ndarray] = {
        key: np.empty(state_grid.shape[1]) for key in keys
    }

    for i in range(state_grid.shape[1]):
        point = derived_quantities(
            time_grid[i],
            state_grid[:, i],
            env,
            vehicle,
            control,
        )
        for key in keys:
            values[key][i] = point[key]

    return values


def _range_moves_forward(range_m: np.ndarray) -> bool:
    """True when the ground range never moves backwards beyond noise.

    The overall range must grow (``R_f > 0``); pointwise strict monotonicity
    is not required, but any obvious backward motion is an error.
    """
    if range_m[-1] <= 0.0:
        return False

    diffs = np.diff(range_m)
    backward = -float(np.sum(diffs[diffs < 0.0]))

    return backward <= 1e-6 * float(range_m[-1])
