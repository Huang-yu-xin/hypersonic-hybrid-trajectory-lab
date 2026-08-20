"""ML-B1 -- First-Order Topology Geometry Gate.

Validates, on the real nonlinear Sanger hybrid simulator, the RareTopo
first-order topology geometry:

* virtual topology margin ``b(x0) = sigma * g*(phi*_ext(t*; x0))``
  (prior true hybrid events are really executed; the critical
  topology-changing switch is NOT executed; the tracked extremum stays on
  the same local branch);
* exact topology oracle ``T(x0)`` from the real hybrid simulator (regime /
  true-switch signature / terminal type);
* analytic gradient ``a = Phi*^T n*`` (prior continuous STMs + prior
  transverse saltations, WITHOUT the critical grazing saltation);
* scaled / whitened finite-difference gate with epsilon plateau;
* covariance-weighted geometry direction ``v_geom = -P0 a / sqrt(a^T P0 a)``
  and the directional boundary approach with random / tangent controls.

Scope (ML-B1, frozen): NO H3 probability estimation, NO P(N)/P(N+1), NO
q_geom production sampler, NO Geometry-IS, NO CEM / subset simulation, NO
flow model, NO SORM / ML-B2, NO Phase-F (gamma0,K) rescan.  The frozen
Phase-A..G physics and the H0/H1/H2/H2R protocol are NOT modified.

Channel semantics (Sanger ``atmosphere_exit``):

* guard ``G_h = h - h_atm``, critical condition ``dG_h/dt = v sin(gamma)
  = 0`` (local extremum of the interface function);
* critical segment = the ``(branch_index+1)``-th atmospheric pass
  (``segments[2*branch_index]``); on the N side it ends at SRTI, on the
  N+1 side it ends at the next ``atmosphere_exit``;
* virtual continuation: keep the pre-critical vector field (``SANGER_ATM``)
  from the critical segment start and track the ``gamma: + -> -``
  extremum (the srti-candidate root); the critical exit is NOT executed;
* orientation ``sigma = -1`` for this channel so that ``b > 0`` is the
  nominal-side clearance and ``b < 0`` is the transition-side event-pair
  regime.  sigma is verified per anchor against the reference-certified
  side (never assumed).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.integrate import solve_ivp

from hyptraj.analysis.comparison_validation import (
    REFERENCE_05_SOLVER_CONFIG,
    REFERENCE_SOLVER_CONFIG,
)
from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.modes.sanger_hybrid import SANGER_ATM, sanger_atm_rhs
from hyptraj.predictability.hybrid_stm import jacobian_mode
from hyptraj.predictability.saltation import identity_reset_saltation
from hyptraj.predictability.stm import (
    integrate_continuous_stm,
    stm_companion_reference_config,
    stm_production_like_config,
    stm_strict_reference_config,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_events import (
    atmosphere_interface_normal,
    atmosphere_interface_value,
    make_pullout_event,
    make_srti_candidate_event,
)
from hyptraj.simulation.sanger_trajectory import (
    ATMOSPHERE_ENTRY,
    ATMOSPHERE_EXIT,
    integrate_sanger_hybrid,
)
from hyptraj.uncertainty.protocol import (
    STATE_DIM,
    canonical_scale_matrix,
    synthetic_alpha_covariance,
)

# ---------------------------------------------------------------------------
# Frozen channel registry
# ---------------------------------------------------------------------------
#: ML-B1 Sanger channel: the atmosphere-interface crossing (ATM -> VAC).
CHANNEL_ATMOSPHERE_EXIT = "atmosphere_exit"

#: True-switch taxonomy names (Phase-G0 registry) for the Sanger switches.
SWITCH_ATMOSPHERE_EXIT = "sanger_atmosphere_exit"
SWITCH_ATMOSPHERE_ENTRY = "sanger_atmosphere_entry"

#: Orientation convention of the atmosphere-exit channel (verified per
#: anchor by the M2 orientation gate; never used unverified).
SIGMA_ATMOSPHERE_EXIT = -1.0

#: Default research horizon for the virtual continuation (safety guard).
DEFAULT_MAX_TIME = 3000.0

#: Reference solver used as the certified basis (Phase-F/G6 dual-reference
#: stability is a prerequisite; the production solver is too coarse for the
#: shallow N+1 excursions and is only used as a secondary audit).
MARGIN_SOLVERS = {
    "production": PRODUCTION_SOLVER_CONFIG,
    "REF-0.1": REFERENCE_SOLVER_CONFIG,
    "REF-0.05": REFERENCE_05_SOLVER_CONFIG,
}

#: STM augmented-system solvers (same 3 levels).
STM_SOLVERS = {
    "production": stm_production_like_config(),
    "REF-0.1": stm_strict_reference_config(),
    "REF-0.05": stm_companion_reference_config(),
}

#: Canonical-A scaling matrix ``S_A = diag(1e5, 1, 7e3, 0.1)`` (frozen).
S_A = canonical_scale_matrix()

#: Default synthetic research covariance ``P0 = S_A (alpha^2 I) S_A^T``
#: with ``alpha = 1`` (unit dimensionless amplitude; geometry direction and
#: whitening are invariant under a positive scaling of ``alpha``).
DEFAULT_P0 = synthetic_alpha_covariance(alpha=1.0)


# ---------------------------------------------------------------------------
# Classification vocabulary (brief §10)
# ---------------------------------------------------------------------------
class MarginClassification(str, Enum):
    """Margin-pipeline status taxonomy (ML-B1 §10)."""

    VALID_MARGIN = "VALID_MARGIN"
    PRIOR_TOPOLOGY_CHANGED = "PRIOR_TOPOLOGY_CHANGED"
    PRIOR_EVENT_ORDER_CHANGED = "PRIOR_EVENT_ORDER_CHANGED"
    EXTREMUM_NOT_FOUND = "EXTREMUM_NOT_FOUND"
    EXTREMUM_BRANCH_CHANGED = "EXTREMUM_BRANCH_CHANGED"
    NONPHYSICAL_STATE = "NONPHYSICAL_STATE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    ORIENTATION_ERROR = "ORIENTATION_ERROR"
    CRITICAL_SEGMENT_NOT_FOUND = "CRITICAL_SEGMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TopologyInfo:
    """Exact hybrid topology from the real nonlinear simulator."""

    regime: str                  # "SRTI_N0" .. "SRTI_N5"
    skip_count: int
    true_switch_signature: tuple[str, ...]
    event_kinds: tuple[str, ...]
    terminal_kind: str
    terminal_time: float
    success: bool


@dataclass(frozen=True)
class MarginRecord:
    """One virtual topology-margin evaluation (brief §10, §14)."""

    classification: MarginClassification
    b: float | None
    sigma: float | None
    initial_state: np.ndarray
    K: float
    channel: str
    branch_index: int
    exact_regime: str | None
    prior_event_sequence: tuple[str, ...] = ()
    prior_switch_signature: tuple[str, ...] = ()
    critical_segment_id: int | None = None
    critical_mode: str | None = None
    critical_trigger: str | None = None
    t_star: float | None = None
    x_star: np.ndarray | None = None
    guard_value: float | None = None
    guard_derivative: float | None = None
    n_star: np.ndarray | None = None
    solver_label: str = "REF-0.1"
    message: str = ""

    def as_dict(self) -> dict:
        """Serializable snapshot (no dense arrays)."""
        return {
            "classification": self.classification.value,
            "b": None if self.b is None else float(self.b),
            "sigma": None if self.sigma is None else float(self.sigma),
            "initial_state": [float(v) for v in self.initial_state],
            "K": float(self.K),
            "channel": self.channel,
            "branch_index": int(self.branch_index),
            "exact_regime": self.exact_regime,
            "prior_event_sequence": list(self.prior_event_sequence),
            "prior_switch_signature": list(self.prior_switch_signature),
            "critical_segment_id": self.critical_segment_id,
            "critical_mode": self.critical_mode,
            "critical_trigger": self.critical_trigger,
            "t_star": self.t_star,
            "x_star": None if self.x_star is None else [float(v) for v in self.x_star],
            "guard_value": self.guard_value,
            "guard_derivative": self.guard_derivative,
            "n_star": None if self.n_star is None else [float(v) for v in self.n_star],
            "solver_label": self.solver_label,
            "message": self.message,
        }


@dataclass(frozen=True)
class AnalyticGradient:
    """Analytic first-order topology gradient (brief §14)."""

    a_raw: np.ndarray            # (4,) d b / d x0 (raw physical units)
    phi_star: np.ndarray         # (4,4) hybrid STM x0 -> x* (no critical saltation)
    n_star: np.ndarray           # (4,) oriented guard normal sigma * e_r
    phi_prior: np.ndarray | None = None
    phi_critical: np.ndarray | None = None
    prior_saltation_denominators: tuple[float, ...] = ()
    critical_saltation_excluded: bool = True
    solver_label: str = "REF-0.1"

    @property
    def a_scaled(self) -> np.ndarray:
        """``grad_z b = S_A^T a_raw`` (z = S_A^-1 (x - xbar))."""
        return S_A.T @ self.a_raw

    @property
    def a_whitened(self) -> np.ndarray:
        """``grad_u b = L0^T a_raw`` (u = L0^-1 delta x, P0 = L0 L0^T)."""
        l0 = _p0_cholesky(DEFAULT_P0)
        return l0.T @ self.a_raw

    @property
    def sqrt_aT_P0_a(self) -> float:
        return float(np.sqrt(np.dot(self.a_raw, DEFAULT_P0 @ self.a_raw)))


@dataclass(frozen=True)
class FdColumn:
    """One centered-FD column at one epsilon (brief §15, §18)."""

    coordinate: int
    epsilon: float
    plus_classification: MarginClassification
    minus_classification: MarginClassification
    derivative: float | None
    valid_pair: bool
    plus_b: float | None = None
    minus_b: float | None = None


@dataclass(frozen=True)
class FdGradientResult:
    """Scaled-space FD gradient at a fixed epsilon (all four columns)."""

    epsilon: float
    columns: tuple[FdColumn, ...]
    gradient: np.ndarray | None        # (4,) valid entries only
    valid_coordinates: tuple[int, ...]

    @property
    def all_columns_valid(self) -> bool:
        return len(self.valid_coordinates) == STATE_DIM


@dataclass(frozen=True)
class EpsilonSweepResult:
    """Full epsilon sweep for one margin record (brief §17)."""

    epsilons: tuple[float, ...]
    per_epsilon: tuple[FdGradientResult, ...]
    plateau: dict[int, tuple[float, float]]          # coord -> (eps_min, eps_max)
    plateau_value: dict[int, float]                  # coord -> median FD derivative
    coordinate_status: dict[int, str]                # "PLATEAU_OK" | "NO_CLEAR_PLATEAU"


@dataclass(frozen=True)
class GeometryDirection:
    """Covariance-weighted geometry direction (brief §20)."""

    v_geom: np.ndarray
    alpha: np.ndarray
    beta_local: float
    identity_residual: float
    sqrt_aT_P0_a: float


@dataclass(frozen=True)
class BoundaryScanPoint:
    """One directional scan point ``x(lambda) = x0 + lambda v``."""

    lambda_value: float
    b: float | None
    b_linear: float
    exact_regime: str | None
    classification: MarginClassification
    t_star: float | None = None


@dataclass(frozen=True)
class DirectionControl:
    """One random / tangent control direction scan (brief §22)."""

    direction_type: str          # "random" | "tangent" | "geometry"
    v: np.ndarray
    initial_db_dlambda: float
    min_abs_b: float
    b_at_min: float | None
    topology_changed: bool
    distance_to_transition: float | None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _p0_cholesky(p0: np.ndarray) -> np.ndarray:
    """Lower-triangular ``L0`` with ``P0 = L0 L0^T`` (diagonal case)."""
    p0 = np.asarray(p0, dtype=float)
    if p0.shape != (STATE_DIM, STATE_DIM):
        raise ValueError(f"P0 must be ({STATE_DIM},{STATE_DIM}); got {p0.shape}.")
    return np.linalg.cholesky(p0)


def _scaled_coordinate_delta(epsilon: float, j: int) -> np.ndarray:
    """Physical perturbation ``delta x = S_A (epsilon e_j)`` (scaled FD)."""
    return np.asarray(S_A[:, j], dtype=float) * epsilon


def state_to_initial_condition(state: np.ndarray, env: EnvironmentParams):
    """Map a raw state ``[r, theta, v, gamma]`` back to an InitialCondition."""
    from hyptraj.models.parameters import InitialCondition

    state = np.asarray(state, dtype=float)
    if state.shape != (STATE_DIM,):
        raise ValueError(f"state must be ({STATE_DIM},); got {state.shape}.")
    return InitialCondition(
        altitude=float(state[0] - env.earth_radius),
        velocity=float(state[2]),
        flight_path_angle_deg=float(np.rad2deg(state[3])),
        range_angle=float(state[1]),
    )


def _event_to_switch_name(kind: str) -> str | None:
    """Map a trajectory event kind to the Phase-G0 switch taxonomy name."""
    if kind == ATMOSPHERE_EXIT:
        return SWITCH_ATMOSPHERE_EXIT
    if kind == ATMOSPHERE_ENTRY:
        return SWITCH_ATMOSPHERE_ENTRY
    return None


def _regime_label(skip_count: int) -> str:
    return f"SRTI_N{int(skip_count)}"


# ---------------------------------------------------------------------------
# Exact topology oracle (brief §12)
# ---------------------------------------------------------------------------
def run_exact_topology(
    initial_state: np.ndarray,
    *,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    K: float,
    solver_label: str = "REF-0.1",
    max_time: float = DEFAULT_MAX_TIME,
) -> tuple[TopologyInfo, object]:
    """Run the real nonlinear hybrid simulator and extract exact topology.

    Returns ``(TopologyInfo, trajectory)`` where the trajectory is the
    ``SangerHybridTrajectory`` (segments / events) reused by the margin
    pipeline.  The topology label always comes from the real simulator,
    never from a linearized surrogate.
    """
    from hyptraj.simulation.sanger_trajectory import TERMINAL_SRTI

    solver = MARGIN_SOLVERS[solver_label]
    initial = state_to_initial_condition(initial_state, env)
    traj = integrate_sanger_hybrid(
        env,
        vehicle,
        initial,
        lambda t, s: float(K),
        solver=solver,
        max_time=max_time,
    )
    kinds = tuple(e.kind for e in traj.events)
    skip_count = kinds.count(ATMOSPHERE_EXIT)
    switch_signature = tuple(
        name for k in kinds if (name := _event_to_switch_name(k)) is not None
    )
    info = TopologyInfo(
        regime=_regime_label(skip_count),
        skip_count=skip_count,
        true_switch_signature=switch_signature,
        event_kinds=kinds,
        terminal_kind=traj.terminal_kind,
        terminal_time=traj.terminal_time,
        success=traj.terminal_kind == TERMINAL_SRTI,
    )
    return info, traj


# ---------------------------------------------------------------------------
# Critical segment localization (branch semantics)
# ---------------------------------------------------------------------------
def locate_critical_segment(
    branch_index: int,
    segments,
) -> tuple[int, str, str]:
    """Locate the critical atmospheric pass for a grazing branch.

    Branch ``B_k`` (``branch_index = k``) sits between ``SRTI_Nk`` and
    ``SRTI_N{k+1}``; the critical channel is the ``(k+1)``-th atmospheric
    pass, i.e. ``segments[2*k]``.  Raises ``ValueError`` when the located
    segment is not an atmospheric pass or the trajectory is too short.
    """
    seg_index = 2 * int(branch_index)
    if seg_index >= len(segments):
        raise ValueError(
            f"branch B{branch_index} requires segment index {seg_index} but "
            f"the trajectory has only {len(segments)} segments (topology "
            "changed?)."
        )
    seg = segments[seg_index]
    if seg.mode != SANGER_ATM:
        raise ValueError(
            f"critical segment {seg_index} is {seg.mode}, expected {SANGER_ATM}."
        )
    return seg_index, seg.mode, seg.trigger_event


def _prior_events(events, segments, seg_index: int) -> list:
    """Non-synthetic events really executed BEFORE the critical segment.

    The prior part is ``segments[0..seg_index-1]``; for ``seg_index == 0``
    (B0) there is no prior hybrid segment and the prior chart is empty.
    """
    if seg_index <= 0:
        return []
    t_prior_end = segments[seg_index - 1].t_end
    return [
        e for e in events
        if not e.is_synthetic and e.time <= t_prior_end + 1e-9
    ]


def _prior_switch_signature(prior_events) -> tuple[str, ...]:
    """True-switch taxonomy signature of the prior part."""
    names: list[str] = []
    for e in prior_events:
        name = _event_to_switch_name(e.kind)
        if name is not None:
            names.append(name)
    return tuple(names)


# ---------------------------------------------------------------------------
# Virtual continuation (brief §1 Goal A, §7, §9)
# ---------------------------------------------------------------------------
def _virtual_continuation(
    state_start: np.ndarray,
    t_start: float,
    *,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    K: float,
    solver_label: str,
    max_time: float,
) -> tuple[float, np.ndarray, float | None, str]:
    """Integrate the pre-critical vector field to the tracked extremum.

    Keeps ``SANGER_ATM`` (the critical ``atmosphere_exit`` is NOT in the
    event list); the tracked extremum is the ``gamma: + -> -`` root of the
    interface function (the srti-candidate root) on the same branch as the
    real SRTI / would-be exit.  Returns ``(t*, x*, guard_derivative, status)``
    with ``status`` in {"found", "extremum_not_found", "numerical_failure",
    "nonphysical"}.
    """
    solver = MARGIN_SOLVERS[solver_label]
    rhs = lambda t, x: sanger_atm_rhs(t, x, env, vehicle, lambda tt, ss: float(K))
    events = [make_pullout_event(), make_srti_candidate_event()]
    sol = solve_ivp(
        rhs,
        (float(t_start), float(max_time)),
        np.asarray(state_start, dtype=float),
        method=solver.method,
        rtol=solver.rtol,
        atol=solver.atol,
        max_step=solver.max_step,
        dense_output=True,
        events=events,
    )
    if not sol.success:
        return float("nan"), np.full(STATE_DIM, np.nan), None, "numerical_failure"
    t_ext = sol.t_events[1] if len(sol.t_events) > 1 else np.array([])
    if t_ext.size == 0:
        return float("nan"), np.full(STATE_DIM, np.nan), None, "extremum_not_found"
    t_star = float(t_ext[0])
    x_star = np.asarray(sol.sol(t_star), dtype=float).reshape(STATE_DIM)
    guard_deriv = float(x_star[2] * np.sin(x_star[3]))
    if x_star[0] - env.earth_radius <= 0.0:
        return t_star, x_star, guard_deriv, "nonphysical"
    return t_star, x_star, guard_deriv, "found"


# ---------------------------------------------------------------------------
# Margin pipeline (brief §10)
# ---------------------------------------------------------------------------
def evaluate_topology_margin(
    initial_state: np.ndarray,
    *,
    K: float,
    branch_index: int,
    env: EnvironmentParams | None = None,
    vehicle: VehicleParams | None = None,
    channel: str = CHANNEL_ATMOSPHERE_EXIT,
    solver_label: str = "REF-0.1",
    max_time: float = DEFAULT_MAX_TIME,
    expected_regime: str | None = None,
    expected_switch_signature: tuple[str, ...] | None = None,
    check_prior_topology: bool = True,
) -> MarginRecord:
    """Evaluate the virtual topology margin for one initial state.

    ``expected_regime`` / ``expected_switch_signature`` define the nominal
    prior chart (the reference context).  When ``check_prior_topology`` is
    True and the sample deviates from that chart, the sample is classified
    as ``PRIOR_TOPOLOGY_CHANGED`` / ``PRIOR_EVENT_ORDER_CHANGED`` instead of
    producing a margin (brief §13: only consistent-prior samples count).
    """
    env = env or EnvironmentParams()
    vehicle = vehicle or VehicleParams()
    initial_state = np.asarray(initial_state, dtype=float)
    if initial_state.shape != (STATE_DIM,):
        raise ValueError(
            f"initial_state must be ({STATE_DIM},); got {initial_state.shape}."
        )

    try:
        info, traj = run_exact_topology(
            initial_state,
            env=env,
            vehicle=vehicle,
            K=K,
            solver_label=solver_label,
            max_time=max_time,
        )
    except Exception as exc:  # solver-level failure -> numerical failure
        return MarginRecord(
            classification=MarginClassification.NUMERICAL_FAILURE,
            b=None, sigma=None, initial_state=initial_state, K=K,
            channel=channel, branch_index=branch_index,
            exact_regime=None, message=f"topology oracle failure: {exc}",
        )

    # ---- critical segment ------------------------------------------------
    try:
        seg_index, critical_mode, critical_trigger = locate_critical_segment(
            branch_index, traj.segments
        )
    except (ValueError, IndexError) as exc:
        seg_index = None
        critical_mode = critical_trigger = None
        locate_message = f"critical segment localization failed: {exc}"
    if seg_index is not None:
        prior_events = _prior_events(traj.events, traj.segments, seg_index)
        prior_signature = _prior_switch_signature(prior_events)
        prior_event_kinds = tuple(e.kind for e in prior_events)
    else:
        prior_events = []
        prior_signature = info.true_switch_signature
        prior_event_kinds = info.event_kinds

    # ---- prior chart guard -------------------------------------------------
    if check_prior_topology and expected_regime is not None:
        if info.regime != expected_regime:
            return MarginRecord(
                classification=MarginClassification.PRIOR_TOPOLOGY_CHANGED,
                b=None, sigma=None, initial_state=initial_state, K=K,
                channel=channel, branch_index=branch_index,
                exact_regime=info.regime,
                prior_event_sequence=prior_event_kinds,
                prior_switch_signature=prior_signature,
                message=(
                    f"regime {info.regime} != expected {expected_regime} "
                    "(prior topology changed)."
                ),
            )
    if check_prior_topology and expected_switch_signature is not None:
        if prior_signature != expected_switch_signature:
            return MarginRecord(
                classification=MarginClassification.PRIOR_EVENT_ORDER_CHANGED,
                b=None, sigma=None, initial_state=initial_state, K=K,
                channel=channel, branch_index=branch_index,
                exact_regime=info.regime,
                prior_event_sequence=prior_event_kinds,
                prior_switch_signature=prior_signature,
                message=(
                    f"switch signature {prior_signature} != "
                    f"expected {expected_switch_signature}."
                ),
            )

    if seg_index is None:
        return MarginRecord(
            classification=MarginClassification.CRITICAL_SEGMENT_NOT_FOUND,
            b=None, sigma=None, initial_state=initial_state, K=K,
            channel=channel, branch_index=branch_index,
            exact_regime=info.regime,
            prior_event_sequence=prior_event_kinds,
            prior_switch_signature=prior_signature,
            message=locate_message or "critical segment missing.",
        )

    seg = traj.segments[seg_index]
    t_star, x_star, guard_deriv, vstatus = _virtual_continuation(
        seg.state_start, seg.t_start,
        env=env, vehicle=vehicle, K=K,
        solver_label=solver_label, max_time=max_time,
    )
    if vstatus in ("extremum_not_found", "numerical_failure", "nonphysical"):
        classification = {
            "extremum_not_found": MarginClassification.EXTREMUM_NOT_FOUND,
            "numerical_failure": MarginClassification.NUMERICAL_FAILURE,
            "nonphysical": MarginClassification.NONPHYSICAL_STATE,
        }[vstatus]
        return MarginRecord(
            classification=classification,
            b=None, sigma=None, initial_state=initial_state, K=K,
            channel=channel, branch_index=branch_index,
            exact_regime=info.regime,
            prior_event_sequence=prior_event_kinds,
            prior_switch_signature=prior_signature,
            critical_segment_id=seg_index, critical_mode=critical_mode,
            critical_trigger=critical_trigger,
            message=f"virtual continuation: {vstatus}.",
        )

    # ---- margin ------------------------------------------------------------
    if channel != CHANNEL_ATMOSPHERE_EXIT:
        raise ValueError(f"unsupported channel {channel!r}.")
    sigma = SIGMA_ATMOSPHERE_EXIT
    n_star = sigma * atmosphere_interface_normal()
    guard_value = atmosphere_interface_value(x_star, env)
    b = sigma * guard_value

    return MarginRecord(
        classification=MarginClassification.VALID_MARGIN,
        b=b, sigma=sigma, initial_state=initial_state, K=K,
        channel=channel, branch_index=branch_index,
        exact_regime=info.regime,
        prior_event_sequence=prior_event_kinds,
        prior_switch_signature=prior_signature,
        critical_segment_id=seg_index, critical_mode=critical_mode,
        critical_trigger=critical_trigger,
        t_star=t_star, x_star=x_star,
        guard_value=guard_value, guard_derivative=guard_deriv,
        n_star=n_star, solver_label=solver_label,
        message="virtual margin evaluated on the tracked extremum branch.",
    )


# ---------------------------------------------------------------------------
# Analytic gradient (brief §14)
# ---------------------------------------------------------------------------
def analytic_margin_gradient(
    record: MarginRecord,
    *,
    env: EnvironmentParams | None = None,
    vehicle: VehicleParams | None = None,
    stm_solver_label: str = "REF-0.1",
    trajectory=None,
) -> AnalyticGradient:
    """``a = Phi*^T n*`` with prior hybrid chain, NO critical saltation.

    ``Phi* = Phi_critical(t* <- t_seg) @ Phi_prior(t_seg <- 0)`` where
    ``Phi_prior`` chains the continuous STMs and the transverse saltations
    of the prior true switches (reusing Phase-G validated primitives) and
    ``Phi_critical`` is the pure continuous STM of the pre-critical segment
    (the critical grazing saltation is explicitly excluded).
    """
    if record.classification != MarginClassification.VALID_MARGIN:
        raise ValueError(
            "analytic gradient requires a VALID_MARGIN record; got "
            f"{record.classification.value}."
        )
    env = env or EnvironmentParams()
    vehicle = vehicle or VehicleParams()
    stm_solver = STM_SOLVERS[stm_solver_label]
    K = record.K
    x0 = record.initial_state

    # Re-run the trajectory (self-contained) unless provided by the caller.
    if trajectory is None:
        _, trajectory = run_exact_topology(
            x0, env=env, vehicle=vehicle, K=K,
            solver_label=record.solver_label,
        )
    seg_index = record.critical_segment_id
    assert seg_index is not None

    # ---- prior chain: segments [0, seg_index) + saltations ---------------
    phi_prior = np.eye(STATE_DIM)
    denominators: list[float] = []
    for i in range(0, seg_index):
        seg = trajectory.segments[i]
        res = integrate_continuous_stm(
            jacobian_mode(seg.mode),
            seg.state_start,
            (seg.t_start, seg.t_end),
            env, vehicle, K,
            solver=stm_solver,
        )
        if not res.success:
            raise RuntimeError(
                f"prior continuous STM failure on segment {i}: {res.message}"
            )
        phi_prior = res.phi @ phi_prior
        # saltation at the segment-end event (true switches only): match the
        # frozen event record by time and trigger kind (diagnostic events
        # store f_minus = None and are skipped automatically).
        end_ev = next(
            (
                e for e in trajectory.events
                if not e.is_synthetic
                and e.time == seg.t_end
                and e.kind == seg.trigger_event
            ),
            None,
        )
        if end_ev is not None and end_ev.f_minus is not None:
            xi = identity_reset_saltation(end_ev.f_minus, end_ev.f_plus, end_ev.normal)
            denominators.append(float(end_ev.normal @ end_ev.f_minus))
            phi_prior = xi @ phi_prior

    # ---- critical continuous segment (no saltation) ----------------------
    seg = trajectory.segments[seg_index]
    res_c = integrate_continuous_stm(
        jacobian_mode(seg.mode),
        seg.state_start,
        (seg.t_start, record.t_star),
        env, vehicle, K,
        solver=stm_solver,
    )
    if not res_c.success:
        raise RuntimeError(f"critical continuous STM failure: {res_c.message}")
    phi_star = res_c.phi @ phi_prior
    n_star = record.n_star
    a_raw = phi_star.T @ n_star
    return AnalyticGradient(
        a_raw=a_raw,
        phi_star=phi_star,
        n_star=n_star,
        phi_prior=phi_prior,
        phi_critical=res_c.phi,
        prior_saltation_denominators=tuple(denominators),
        solver_label=stm_solver_label,
    )


# ---------------------------------------------------------------------------
# Scaled finite-difference gate (brief §15, §16, §18)
# ---------------------------------------------------------------------------
def scaled_fd_margin_gradient(
    nominal: MarginRecord,
    epsilon: float,
    *,
    env: EnvironmentParams | None = None,
    vehicle: VehicleParams | None = None,
    max_time: float = DEFAULT_MAX_TIME,
    expected_regime: str | None = None,
    expected_switch_signature: tuple[str, ...] | None = None,
    evaluator=None,
) -> FdGradientResult:
    """Centered FD of the margin in scaled coordinates at one epsilon.

    Column ``j`` perturbs ``x_j += S_A[j,j] * epsilon`` (scaled step);
    both sides independently re-run the FULL margin pipeline (real prior
    propagation, virtual continuation, extremum tracking).  A column is
    valid only when both the plus and the minus evaluation are VALID with
    an unchanged prior chart (brief §18 pair gate).

    ``evaluator`` is an optional callable with the same signature as
    ``evaluate_topology_margin`` (used to run the evaluation behind the
    process-level timeout guard).
    """
    env = env or EnvironmentParams()
    vehicle = vehicle or VehicleParams()
    eval_fn = evaluator or evaluate_topology_margin
    x0 = nominal.initial_state
    columns: list[FdColumn] = []
    gradient = np.zeros(STATE_DIM)
    valid: list[int] = []
    for j in range(STATE_DIM):
        delta = _scaled_coordinate_delta(epsilon, j)
        plus = eval_fn(
            x0 + delta, K=nominal.K, branch_index=nominal.branch_index,
            env=env, vehicle=vehicle, channel=nominal.channel,
            solver_label=nominal.solver_label, max_time=max_time,
            expected_regime=expected_regime,
            expected_switch_signature=expected_switch_signature,
        )
        minus = eval_fn(
            x0 - delta, K=nominal.K, branch_index=nominal.branch_index,
            env=env, vehicle=vehicle, channel=nominal.channel,
            solver_label=nominal.solver_label, max_time=max_time,
            expected_regime=expected_regime,
            expected_switch_signature=expected_switch_signature,
        )
        ok = (
            plus.classification == MarginClassification.VALID_MARGIN
            and minus.classification == MarginClassification.VALID_MARGIN
        )
        derivative = None
        if ok:
            derivative = float((plus.b - minus.b) / (2.0 * epsilon))
            gradient[j] = derivative
            valid.append(j)
        columns.append(
            FdColumn(
                coordinate=j, epsilon=epsilon,
                plus_classification=plus.classification,
                minus_classification=minus.classification,
                derivative=derivative, valid_pair=ok,
                plus_b=plus.b, minus_b=minus.b,
            )
        )
    return FdGradientResult(
        epsilon=epsilon,
        columns=tuple(columns),
        gradient=gradient if len(valid) == STATE_DIM else None,
        valid_coordinates=tuple(valid),
    )


# ---------------------------------------------------------------------------
# Epsilon sweep (brief §17)
# ---------------------------------------------------------------------------
#: Dimensionless scaled-space sweep.  Extremal grazing anchors sit very close
#: to the boundary (|b| ~ 0.1 m), so a scaled step epsilon that moves the
#: margin by more than |b| flips the topology and the FD column is correctly
#: rejected by the pair gate (brief §18).  The sweep therefore extends below
#: the brief's nominal 1e-6 .. 1e-2 ladder into the same-side FD window.
#:
#: The upper limit is 1e-6: beyond it every material column crosses the
#: topology boundary (delta b > |b|), so those columns are invalid by the
#: pair gate and are not evaluated.  (Evaluating them anyway is not only
#: useless; the near-grazing REF-0.1 DOP853 integration of the flipped
#: topology has been observed to stall for an unbounded wall-clock time on
#: Windows, so the sweep stops at the valid-window boundary.)
DEFAULT_EPSILON_SWEEP: tuple[float, ...] = (
    1e-8, 3e-8, 1e-7, 3e-7, 1e-6,
)


def epsilon_sweep_fd(
    nominal: MarginRecord,
    *,
    epsilons: tuple[float, ...] = DEFAULT_EPSILON_SWEEP,
    env=None,
    vehicle=None,
    max_time: float = DEFAULT_MAX_TIME,
    expected_regime: str | None = None,
    expected_switch_signature: tuple[str, ...] | None = None,
    evaluator=None,
) -> EpsilonSweepResult:
    """Run the scaled-FD sweep and identify per-coordinate plateaus.

    A coordinate has a clear plateau when a contiguous window of at least
    three epsilons keeps the centered derivative within a relative spread
    ``PLATEAU_RELATIVE_SPREAD``; the plateau value is the window median.
    ``evaluator`` (optional) is passed through to the FD columns.
    """
    env = env or EnvironmentParams()
    vehicle = vehicle or VehicleParams()
    per_eps: list[FdGradientResult] = []
    for eps in epsilons:
        per_eps.append(
            scaled_fd_margin_gradient(
                nominal, eps, env=env, vehicle=vehicle, max_time=max_time,
                expected_regime=expected_regime,
                expected_switch_signature=expected_switch_signature,
                evaluator=evaluator,
            )
        )
    plateau: dict[int, tuple[float, float]] = {}
    plateau_value: dict[int, float] = {}
    coordinate_status: dict[int, str] = {}
    for j in range(STATE_DIM):
        vals = np.array(
            [r.columns[j].derivative for r in per_eps
             if r.columns[j].derivative is not None],
            dtype=float,
        )
        valid_eps = np.array(
            [r.epsilon for r in per_eps if r.columns[j].derivative is not None],
            dtype=float,
        )
        if vals.size == 0:
            coordinate_status[j] = "NO_CLEAR_PLATEAU"
            continue
        # longest contiguous window with relative spread below tolerance
        best_lo, best_hi = None, None
        n = vals.size
        for lo in range(n):
            for hi in range(lo + 2, n + 1):  # at least 3 points
                window = vals[lo:hi]
                med = float(np.median(window))
                if med == 0.0:
                    spread = float(np.max(np.abs(window)))
                else:
                    spread = float(np.max(np.abs(window - med)) / np.abs(med))
                if spread <= PLATEAU_RELATIVE_SPREAD:
                    if best_lo is None or (hi - lo) > (best_hi - best_lo):
                        best_lo, best_hi = lo, hi
        if best_lo is not None:
            plateau[j] = (float(valid_eps[best_lo]), float(valid_eps[best_hi - 1]))
            plateau_value[j] = float(np.median(vals[best_lo:best_hi]))
            coordinate_status[j] = "PLATEAU_OK"
        else:
            coordinate_status[j] = "NO_CLEAR_PLATEAU"
    return EpsilonSweepResult(
        epsilons=tuple(epsilons),
        per_epsilon=tuple(per_eps),
        plateau=plateau,
        plateau_value=plateau_value,
        coordinate_status=coordinate_status,
    )


#: Relative spread tolerance for a plateau window (brief §17).
PLATEAU_RELATIVE_SPREAD = 0.05


# ---------------------------------------------------------------------------
# Gradient error metrics (brief §19)
# ---------------------------------------------------------------------------
def gradient_error_metrics(
    a_ana_scaled: np.ndarray,
    a_fd_scaled: np.ndarray,
) -> dict:
    """Per-coordinate errors, cosine similarity and normalized L2 (scaled)."""
    a_ana = np.asarray(a_ana_scaled, dtype=float)
    a_fd = np.asarray(a_fd_scaled, dtype=float)
    abs_err = np.abs(a_fd - a_ana)
    denom = np.maximum(np.abs(a_ana), 1e-300)
    rel_err = abs_err / denom
    sym_rel = abs_err / np.maximum((np.abs(a_fd) + np.abs(a_ana)) / 2.0, 1e-300)
    cosine = float(
        np.dot(a_ana, a_fd)
        / (np.linalg.norm(a_ana) * np.linalg.norm(a_fd) + 1e-300)
    )
    norm_l2 = float(
        np.linalg.norm(a_fd - a_ana) / (np.linalg.norm(a_ana) + 1e-300)
    )
    return {
        "abs_error": [float(v) for v in abs_err],
        "relative_error": [float(v) for v in rel_err],
        "symmetric_relative_error": [float(v) for v in sym_rel],
        "cosine_similarity": cosine,
        "normalized_l2_error": norm_l2,
    }


# ---------------------------------------------------------------------------
# Geometry direction (brief §20, §21)
# ---------------------------------------------------------------------------
def geometry_direction(
    a_raw: np.ndarray,
    p0: np.ndarray | None = None,
    b0: float | None = None,
) -> GeometryDirection:
    """Covariance-weighted geometry direction and the local beta.

    ``beta_local = b0 / sqrt(a^T P0 a)`` when ``b0`` is provided (the
    first-order estimate of the boundary distance along ``v_geom``).
    """
    p0 = DEFAULT_P0 if p0 is None else np.asarray(p0, dtype=float)
    a = np.asarray(a_raw, dtype=float)
    s = float(np.sqrt(np.dot(a, p0 @ a)))
    v_geom = -((p0 @ a) / (s + 1e-300))
    identity_residual = float(np.dot(a, v_geom) + s)
    l0 = _p0_cholesky(p0)
    lta = l0.T @ a
    alpha = lta / (np.linalg.norm(lta) + 1e-300)
    beta_local = float("nan")
    if b0 is not None:
        beta_local = float(b0) / (s + 1e-300)
    return GeometryDirection(
        v_geom=v_geom,
        alpha=alpha,
        beta_local=beta_local,
        identity_residual=identity_residual,
        sqrt_aT_P0_a=s,
    )


def directional_boundary_scan(
    nominal: MarginRecord,
    direction: np.ndarray,
    *,
    lambda_scale: float,
    n_points: int = 24,
    env=None,
    vehicle=None,
    max_time: float = DEFAULT_MAX_TIME,
    expected_regime: str | None = None,
    expected_switch_signature: tuple[str, ...] | None = None,
    b_linear_offset: float | None = None,
    a_raw: np.ndarray | None = None,
    p0: np.ndarray | None = None,
) -> tuple[list[BoundaryScanPoint], dict]:
    """Scan ``x(lambda) = x0 + lambda * direction`` and record margin / topology.

    The lambda ladder is placed RELATIVE to the first-order boundary
    distance ``lambda_scale`` (``beta_local``): ``lambda = lambda_scale *
    10^linspace(log10(0.1), log10(6), n_points)``.  ``lambda_scale`` may be
    negative (transition-side anchors), in which case the scan covers the
    negative half-line and crosses the boundary inside the same relative
    interval.  Returns the scan points plus a summary dict with the exact
    boundary bracket (last lambda with ``b >= 0`` and first with ``b < 0``)
    and the linearized crossing estimate.
    """
    env = env or EnvironmentParams()
    vehicle = vehicle or VehicleParams()
    x0 = nominal.initial_state
    lam_scale = float(lambda_scale)
    if not np.isfinite(lam_scale) or lam_scale == 0.0:
        raise ValueError("lambda_scale (beta_local) must be finite and non-zero.")
    log_lo, log_hi = np.log10(0.1), np.log10(6.0)
    lambdas = lam_scale * np.power(10.0, np.linspace(log_lo, log_hi, n_points))
    if a_raw is not None:
        p0 = DEFAULT_P0 if p0 is None else np.asarray(p0, dtype=float)
        slope = -float(np.sqrt(np.dot(a_raw, p0 @ a_raw)))
    else:
        slope = None
    points: list[BoundaryScanPoint] = []
    for lam in lambdas:
        rec = evaluate_topology_margin(
            x0 + lam * direction, K=nominal.K,
            branch_index=nominal.branch_index,
            env=env, vehicle=vehicle, channel=nominal.channel,
            solver_label=nominal.solver_label, max_time=max_time,
            expected_regime=expected_regime,
            expected_switch_signature=expected_switch_signature,
        )
        b_lin = None
        if slope is not None and nominal.b is not None:
            b_lin = nominal.b + slope * lam
        points.append(
            BoundaryScanPoint(
                lambda_value=float(lam),
                b=rec.b,
                b_linear=float(b_lin) if b_lin is not None else float("nan"),
                exact_regime=rec.exact_regime,
                classification=rec.classification,
                t_star=rec.t_star,
            )
        )
    # bracket: locate the sign change of b along the scan, whatever its
    # direction (N-side anchors cross + -> -, N+1-side anchors cross
    # - -> +).  The side is read from the exact topology (regime); a point
    # whose margin is None because the prior chart changed still carries its
    # exact regime and closes the bracket.  lambda_minus is the N-side
    # (b >= 0 / SRTI_N{branch}) point, lambda_plus the transition-side
    # (b < 0 / SRTI_N{branch+1}) point.
    def _side(regime, bval):
        if regime is not None:
            n = int(str(regime).replace("SRTI_N", ""))
            if n == nominal.branch_index:
                return +1
            if n == nominal.branch_index + 1:
                return -1
        if bval is not None:
            return +1 if bval >= 0 else -1
        return None

    bracket = {"lambda_minus": None, "lambda_plus": None,
               "b_at_minus": None, "b_at_plus": None}
    prev_side = _side(nominal.exact_regime, nominal.b)
    prev_lam, prev_b = 0.0, nominal.b
    if prev_side == +1:
        bracket["lambda_minus"] = 0.0
        bracket["b_at_minus"] = None if nominal.b is None else float(nominal.b)
    for p in points:
        side = _side(p.exact_regime, p.b)
        if side is None:
            continue
        if prev_side is not None and side != prev_side:
            if side == +1:
                bracket["lambda_minus"] = p.lambda_value
                bracket["b_at_minus"] = p.b
                bracket["lambda_plus"] = prev_lam
                bracket["b_at_plus"] = prev_b
            else:
                bracket["lambda_plus"] = p.lambda_value
                bracket["b_at_plus"] = p.b
                bracket["lambda_minus"] = prev_lam
                bracket["b_at_minus"] = prev_b
            break
        prev_side = side
        prev_lam = p.lambda_value
        prev_b = p.b
    return points, bracket


# ---------------------------------------------------------------------------
# Random / tangent controls (brief §22)
# ---------------------------------------------------------------------------
def _random_unit_whitened(seed: int, rng_dim: int = STATE_DIM) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(rng_dim)
    return v / (np.linalg.norm(v) + 1e-300)


def _tangent_whitened(alpha: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(STATE_DIM)
    v = v - np.dot(v, alpha) * alpha
    n = np.linalg.norm(v)
    return v / (n + 1e-300)


def direction_controls(
    nominal: MarginRecord,
    a_raw: np.ndarray,
    *,
    n_random: int = 3,
    n_tangent: int = 2,
    seeds: tuple[int, ...] = (101, 202, 303),
    p0: np.ndarray | None = None,
    env=None,
    vehicle=None,
    max_time: float = DEFAULT_MAX_TIME,
    expected_regime: str | None = None,
    expected_switch_signature: tuple[str, ...] | None = None,
    n_points: int = 16,
) -> tuple[list[DirectionControl], dict]:
    """Compare geometry / random / tangent whitened directions."""
    p0 = DEFAULT_P0 if p0 is None else np.asarray(p0, dtype=float)
    env = env or EnvironmentParams()
    vehicle = vehicle or VehicleParams()
    l0 = _p0_cholesky(p0)
    a = np.asarray(a_raw, dtype=float)
    s = float(np.sqrt(np.dot(a, p0 @ a)))
    lta = l0.T @ a
    alpha = lta / (np.linalg.norm(lta) + 1e-300)
    v_geom_u = -alpha

    dirs: list[tuple[str, np.ndarray]] = [("geometry", v_geom_u)]
    for k in range(n_random):
        dirs.append((f"random{k}", _random_unit_whitened(seeds[k % len(seeds)])))
    for k in range(n_tangent):
        dirs.append((f"tangent{k}", _tangent_whitened(alpha, seeds[k])))

    out: list[DirectionControl] = []
    summary: dict = {}
    # initial directional-derivative FD step: a small fraction of the
    # local boundary distance so the two sides stay on the nominal side
    beta = float("nan")
    if nominal.b is not None:
        beta = float(nominal.b) / (s + 1e-300)
    eps_init = 0.05 * abs(beta) if np.isfinite(beta) else 1e-4
    eps_init = max(float(eps_init), 1e-6)
    for dtype, v_u in dirs:
        v = l0 @ v_u
        # initial directional derivative (finite difference at small step)
        b_plus = evaluate_topology_margin(
            nominal.initial_state + eps_init * v, K=nominal.K,
            branch_index=nominal.branch_index, env=env, vehicle=vehicle,
            channel=nominal.channel, solver_label=nominal.solver_label,
            max_time=max_time, expected_regime=expected_regime,
            expected_switch_signature=expected_switch_signature,
        ).b
        b_minus = evaluate_topology_margin(
            nominal.initial_state - eps_init * v, K=nominal.K,
            branch_index=nominal.branch_index, env=env, vehicle=vehicle,
            channel=nominal.channel, solver_label=nominal.solver_label,
            max_time=max_time, expected_regime=expected_regime,
            expected_switch_signature=expected_switch_signature,
        ).b
        if b_plus is not None and b_minus is not None:
            init_db = (b_plus - b_minus) / (2.0 * eps_init)
        else:
            init_db = float("nan")
        # scan to find minimum |b| and topology change (lambda ladder is
        # relative to the local boundary distance beta)
        points, bracket = directional_boundary_scan(
            nominal, v, lambda_scale=beta, n_points=n_points,
            env=env, vehicle=vehicle, max_time=max_time,
            expected_regime=expected_regime,
            expected_switch_signature=expected_switch_signature,
        )
        valid_b = [p.b for p in points if p.b is not None]
        min_abs_b = float(np.min(np.abs(valid_b))) if valid_b else float("inf")
        b_at_min = float(
            valid_b[int(np.argmin(np.abs(np.asarray(valid_b))))]
        ) if valid_b else None
        regime0 = nominal.exact_regime
        topology_changed = any(
            p.exact_regime is not None and p.exact_regime != regime0 for p in points
        )
        distance = bracket["lambda_plus"] if bracket["lambda_plus"] is not None else None
        out.append(
            DirectionControl(
                direction_type=dtype,
                v=np.asarray(v, dtype=float),
                initial_db_dlambda=init_db,
                min_abs_b=min_abs_b,
                b_at_min=b_at_min,
                topology_changed=bool(topology_changed),
                distance_to_transition=distance,
            )
        )
    return out, summary
