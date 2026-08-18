"""Phase-G6 grazing transversality-loss & linearization-validity (G6).

G6 studies the breakdown / conditioning of the already-validated G3/G4/G5
linearization near the already-frozen Phase-F Sanger skip-count grazing
boundaries (B0-B4) and their 10 dual-reference extremal anchors.  It
studies, as ``n^T f^- = v sin(gamma) -> 0``:

* event-time gradient and saltation conditioning (exact scaled
  identities): ``||q S_A|| = s_r / |d|`` and
  ``|d| ||(S_A^-1 Xi S_A - I)||_2 = s_r ||S_A^-1 (f^+ - f^-)||_2``;
* dimensionless incidence ``chi = |sin(gamma)|`` (separates incidence
  geometry from vehicle speed; NO universal physics threshold);
* individual saltation growth vs the paired
  ``P_excursion = Xi_entry C_VAC Xi_exit`` factor;
* the nonlinear validity domain contraction (radial clearance-normalized
  perturbations, ``|dr| = beta * Phi_local``), 1%/5% linearization
  validity radii;
* the actual-anchor initial-state topology-preserving radius.

NOTATION: the Phase-F SCALAR grazing clearance is ``grazing_phi`` /
``phi_N_clearance``; the Phase-G MATRIX STM is ``phi_stm`` /
``phi_hybrid``.  They must never share a bare ``phi`` name.  G6 does NOT
re-scan the gamma0-K domain, does NOT refit B0-B4, does NOT compute
asymptotic/chaos claims, and either freezes an EMPIRICAL OPERATIONAL
threshold or freezes NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED based on
evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np

from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability.saltation import (
    identity_reset_saltation,
)
from hyptraj.predictability.hybrid_stm import (
    DISCRETE_TO_JACOBIAN_MODE,
    true_switch_events_before,
    build_split_tail,
)
from hyptraj.predictability.scaling import canonical_candidate
from hyptraj.predictability.metrics import scale_values_by_key
from hyptraj.predictability.ftle import (
    canonicalize_svd_signs,
    condition_status,
    numerical_rank,
)

_STATE_DIM = 4


class GrazingTopologyContractError(RuntimeError):
    """The actual frozen trajectory topology contradicts the Phase-F
    expected grazing-branch contract (e.g. an N-side anchor that contains
    the target newly-created exit/apogee/entry ordinal, or an N+1 anchor
    missing one, or a regime mismatch against the Phase-F expected
    SRTI_N/SRTI_{N+1}).  This is a phase-F source-of-truth mismatch, NOT a
    G6 numerical-tolerance issue; the caller hard-stops."""


# Canonical scientific scaling (G5 frozen Candidate A) -- G6 must not change it.
def _canonical_scales():
    return scale_values_by_key(canonical_candidate().key)


@dataclass(frozen=True)
class FrozenGrazingAnchor:
    """One Phase-F frozen dual-reference extremal grazing anchor."""

    branch: str            # "B0".."B4"
    N: int
    side: str              # "N_side" | "N1_side"
    gamma0_deg: float
    K: float
    phase_f_reference_phi_m: float        # REF-0.1 Phi_N clearance [m]
    phase_f_reference_phi_ref01: float    # REF-0.1 Phi_N [m]
    phase_f_reference_phi_ref005: float   # REF-0.05 Phi_N [m]
    reference_dual_stable: bool           # Phase-F dual-reference flag
    expected_regime: str    # SRTI_N / SRTI_{N+1}


@dataclass(frozen=True)
class GrazingExcursion:
    """Newly-created short VAC excursion of an N+1-side anchor."""

    branch: str
    N: int
    has_excursion: bool
    exit_time: float | None
    exit_state: np.ndarray | None
    exit_ordinal: int | None
    apogee_time: float | None
    apogee_state: np.ndarray | None
    entry_time: float | None
    entry_state: np.ndarray | None
    entry_ordinal: int | None
    vac_duration_s: float | None
    clearance_m: float | None
    exit_denominator: float | None
    exit_incidence: float | None      # |sin gamma|
    exit_velocity_mps: float | None
    entry_denominator: float | None


@dataclass(frozen=True)
class ControlledFamilyPoint:
    """One controlled local grazing family point (not trajectory-backed)."""

    alpha: float
    gamma_exit_rad: float
    d_exit: float
    apogee_clearance_m: float
    vac_duration_s: float
    d_entry: float
    entry_state: np.ndarray
    ref_stable: bool
    classification: str   # "REF_STABLE" | "NUMERICAL_RESOLUTION_LIMIT"


@dataclass(frozen=True)
class ExcursionFactor:
    """Paired exit-VAC-entry factor ``P = Xi_entry C_VAC Xi_exit``."""

    exit_lin_matrix: np.ndarray
    c_vac: np.ndarray
    entry_lin_matrix: np.ndarray
    p_excursion: np.ndarray
    p_scaled: np.ndarray
    singular_values: np.ndarray
    sigma_max: float
    condition_status: str
    numerical_rank: int
    nullity: int
    norm_scaled_minus_I: float
    dominant_input_scaled: np.ndarray
    dominant_output_scaled: np.ndarray
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Frozen anchor loading (programmatic; no hard-coded table in production)
# ---------------------------------------------------------------------------
def load_frozen_grazing_anchors(snapshot_path=None) -> tuple[FrozenGrazingAnchor, ...]:
    """Read the 10 Phase-F extremal grazing anchors from the frozen snapshot."""
    path = Path(snapshot_path) if snapshot_path else (
        Path(__file__).resolve().parents[3] / "tests" / "data" /
        "phase_f_gamma_k_sensitivity_v1.json")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    anchors = data["grazing"]["extremal_anchors"]
    out = []
    for a in anchors:
        branch = a["branch"]
        n = int(branch[1:])
        side = a["side"]  # "N_side" | "N1_side"
        gamma0_deg, K = a["parameter"]
        ref01 = a["reference_phi"]["REF-0.1"]
        ref005 = a["reference_phi"]["REF-0.05"]
        dual = bool(a["reference_dual_stable"])
        regime = f"SRTI_N{n}" if side == "N_side" else f"SRTI_N{n + 1}"
        out.append(FrozenGrazingAnchor(
            branch=branch, N=n, side=side,
            gamma0_deg=float(gamma0_deg), K=float(K),
            phase_f_reference_phi_m=float(ref01),
            phase_f_reference_phi_ref01=float(ref01),
            phase_f_reference_phi_ref005=float(ref005),
            reference_dual_stable=dual,
            expected_regime=regime))
    return tuple(out)


def anchor_initial_state(anchor: FrozenGrazingAnchor, env: EnvironmentParams) -> np.ndarray:
    """Phase-G full initial continuous state for an anchor (h0=100 km, v0=7000)."""
    return np.array([
        env.earth_radius + env.atmosphere_boundary,
        0.0,
        7000.0,
        np.deg2rad(anchor.gamma0_deg),
    ], dtype=float)


def _anchor_initial_condition(anchor, env) -> InitialCondition:
    return InitialCondition(
        altitude=float(env.atmosphere_boundary),
        velocity=7000.0,
        flight_path_angle_deg=anchor.gamma0_deg,
        range_angle=0.0,
    )


# ---------------------------------------------------------------------------
# Structured event extraction with physical kind-ordinals
# ---------------------------------------------------------------------------
def _kind_ordinals(events) -> tuple[dict, dict]:
    """Chronological kind-ordinals: event -> (kind, ordinal)."""
    counters: dict[str, int] = {}
    out = {}
    for ev in events:
        kind = getattr(ev, "kind", "?")
        if kind == "atmosphere_exit":
            kind = "exit"
        elif kind == "atmosphere_entry":
            kind = "entry"
        elif kind == "vacuum_apogee":
            kind = "apogee"
        ordinal = counters.get(kind, 0)
        counters[kind] = ordinal + 1
        out[id(ev)] = (kind, ordinal)
    return out, counters


def _trajectory_of(result):
    if hasattr(result, "trajectory"):
        return result.trajectory
    return result


def sanger_anchor_topology(result) -> tuple[str, int]:
    """``(regime_label, skip_count)`` of a frozen Sanger research result."""
    traj = _trajectory_of(result)
    from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
    from hyptraj.analysis.sensitivity_trajectory import classify_sanger_regime
    metrics = analyze_sanger_trajectory(traj, EnvironmentParams())
    regime = classify_sanger_regime(
        traj, skip_count=metrics.skip_count)
    return regime, int(metrics.skip_count)


def extract_branch_excursion(
    anchor: FrozenGrazingAnchor,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    solver,
) -> GrazingExcursion:
    """Extract the newly-created short VAC excursion for an N+1 anchor,
    or confirm its absence on the N-side (G6 §7, §9)."""
    from hyptraj.simulation.sanger_research_trajectory import (
        integrate_sanger_research_trajectory,
    )

    ctl = ConstantKControl(anchor.K)
    traj = integrate_sanger_research_trajectory(
        env, vehicle, _anchor_initial_condition(anchor, env), ctl,
        solver=solver)
    result = _trajectory_of(traj)
    events = list(result.events)
    ordinal_map, _ = _kind_ordinals(events)
    n = anchor.N

    # Hard regime guard (G6R Issue 1 §3): the ACTUAL frozen regime must
    # equal the Phase-F expected SRTI_N / SRTI_{N+1}; mismatch is a
    # Phase-F source-of-truth mismatch (HARD STOP).
    actual_regime, _ = sanger_anchor_topology(result)
    if actual_regime != anchor.expected_regime:
        raise GrazingTopologyContractError(
            f"{anchor.branch} {anchor.side}: actual frozen regime "
            f"{actual_regime!r} != expected {anchor.expected_regime!r} "
            "(Phase-F source-of-truth mismatch).")

    def find(kind, ordinal):
        for ev in events:
            k, o = ordinal_map[id(ev)]
            if k == kind and o == ordinal:
                return ev
        return None

    def fail(msg):
        raise GrazingTopologyContractError(
            f"{anchor.branch} {anchor.side} "
            f"(expected {anchor.expected_regime}): {msg}")

    if anchor.side == "N_side":
        # For SRTI_N there are N exits (kind-ordinals 0..N-1): exit /
        # apogee / entry ordinal N MUST NOT exist (hard absence guard).
        for kind, ev in (("exit", find("exit", n)),
                         ("apogee", find("apogee", n)),
                         ("entry", find("entry", n))):
            if ev is not None:
                raise GrazingTopologyContractError(
                    f"{anchor.branch} {anchor.side} expected no "
                    f"{kind}-ordinal-N (newly-created excursion absent), but "
                    f"found {kind} ordinal {n} at t = {ev.time:.6f} s.")
        return GrazingExcursion(
            branch=anchor.branch, N=n, has_excursion=False,
            exit_time=None, exit_state=None, exit_ordinal=None,
            apogee_time=None, apogee_state=None,
            entry_time=None, entry_state=None, entry_ordinal=None,
            vac_duration_s=None, clearance_m=None,
            exit_denominator=None, exit_incidence=None,
            exit_velocity_mps=None, entry_denominator=None,
        )

    exit_N = find("exit", n)
    apogee_N = find("apogee", n)
    entry_N = find("entry", n)
    if exit_N is None:
        fail(f"expected newly-created exit ordinal {n} not found.")
    if apogee_N is None:
        fail(f"expected newly-created VAC apogee ordinal {n} not found.")
    if entry_N is None:
        fail(f"expected matching atmosphere entry ordinal {n} not found.")
    x_exit = np.asarray(exit_N.state, dtype=float)
    x_apo = np.asarray(apogee_N.state, dtype=float)
    x_entry = np.asarray(entry_N.state, dtype=float)
    vac_duration = float(entry_N.time - exit_N.time)
    clearance = float(x_apo[0] - env.earth_radius - env.atmosphere_boundary)
    d_exit = float(x_exit[2] * np.sin(x_exit[3]))
    d_entry = float(x_entry[2] * np.sin(x_entry[3]))
    # chronological + sign + positivity hard guards (G6R §2)
    if not (exit_N.time < apogee_N.time < entry_N.time):
        fail("wrong chronology "
             f"(t_exit={exit_N.time:.6f} < t_apo={apogee_N.time:.6f} < "
             f"t_entry={entry_N.time:.6f} violated).")
    if not d_exit > 0.0:
        fail(f"exit denominator d_exit = {d_exit} must be > 0.")
    if not d_entry < 0.0:
        fail(f"entry denominator d_entry = {d_entry} must be < 0.")
    if not vac_duration > 0.0:
        fail(f"VAC duration = {vac_duration} must be > 0.")
    if not clearance > 0.0:
        fail(f"apogee clearance = {clearance} must be > 0.")
    return GrazingExcursion(
        branch=anchor.branch, N=n, has_excursion=True,
        exit_time=float(exit_N.time), exit_state=x_exit, exit_ordinal=n,
        apogee_time=float(apogee_N.time), apogee_state=x_apo,
        entry_time=float(entry_N.time), entry_state=x_entry, entry_ordinal=n,
        vac_duration_s=vac_duration, clearance_m=clearance,
        exit_denominator=d_exit, exit_incidence=abs(np.sin(x_exit[3])),
        exit_velocity_mps=float(x_exit[2]),
        entry_denominator=d_entry,
    )


# ---------------------------------------------------------------------------
# Conditioning algebra (G6 §10-§13, §58)
# ---------------------------------------------------------------------------
def grazing_event_metrics(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
) -> dict:
    """Exit conditioning metrics: d, chi, q, Xi, scaled norms + identities."""
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs, sanger_vac_rhs
    from hyptraj.predictability.saltation import event_time_gradient

    x = np.asarray(exit_state, dtype=float)
    ctl = ConstantKControl(k)
    f_minus = sanger_atm_rhs(0.0, x, env, vehicle, ctl)
    f_plus = sanger_vac_rhs(0.0, x, env, vehicle)
    normal = np.array([1.0, 0.0, 0.0, 0.0])
    d = float(normal @ f_minus)
    q = event_time_gradient(normal, d)
    xi = identity_reset_saltation(f_minus, f_plus, normal)
    scales = _canonical_scales()
    s_r = float(scales["r"])
    svec = np.array([scales[v] for v in ("r", "theta", "v", "gamma")],
                    dtype=float)
    qS = q * svec
    qS_norm = float(np.linalg.norm(qS))
    S = np.diag(svec)
    S_inv = np.diag(1.0 / svec)
    xi_tilde = S_inv @ xi @ S
    norm_tilde_minus_I = float(np.linalg.norm(xi_tilde - np.eye(4), ord=2))
    delta_f = f_plus - f_minus
    s_db = float(np.linalg.norm(S_inv @ delta_f, ord=2))
    # exact conditioning identities (G6 §12-§13, §58) -- machine precision
    resid_q = abs(d * qS_norm - s_r)
    resid_xi = abs(d * norm_tilde_minus_I - s_r * s_db)
    return {
        "f_minus": f_minus, "f_plus": f_plus,
        "xi": xi, "xi_scaled": xi_tilde,
        "denominator": d,
        "incidence": abs(np.sin(x[3])),
        "q": q, "q_scaled_norm": qS_norm,
        "norm_xi_scaled_minus_I": norm_tilde_minus_I,
        "scaled_delta_f_norm": s_db,
        "identity_q_residual": resid_q,
        "identity_xi_residual": resid_xi,
        "det_xi": float(np.linalg.det(xi)),
    }


# ---------------------------------------------------------------------------
# Local VAC excursion reconstruction (G6 §19-§20)
# ---------------------------------------------------------------------------
class VacExcursionFailure(RuntimeError):
    """Structured VAC-excursion reconstruction failure (G6R Issue 5).

    Carries a ``status`` from ``PairedExcursionClass`` so the caller can
    distinguish a topology loss (``VAC_EXCURSION_LOST`` /
    ``VAC_APOGEE_NOT_FOUND`` / ``NONPHYSICAL_STATE`` /
    ``WRONG_ENTRY_DIRECTION``) from a pure integrator failure
    (``NUMERICAL_FAILURE``) instead of string-matching messages."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def _nonphysical_state(x_start, env) -> str | None:
    """Return an ``NONPHYSICAL_STATE`` reason if ``x_start`` is not a
    physical Sanger flight state, else ``None`` (G6R Issue 5)."""
    x = np.asarray(x_start, dtype=float)
    if not np.all(np.isfinite(x)):
        return "non-finite state"
    if float(x[0]) <= float(env.earth_radius):
        return f"radius {x[0]:.6g} <= R_E {env.earth_radius:.6g}"
    if float(x[2]) <= 0.0:
        return f"velocity {x[2]:.6g} <= 0"
    return None


def _run_vac_excursion(x_start, env, vehicle, cfg, horizon=5000.0):
    """From an exit state, VAC flow to apogee (gamma,+->-), then to
    atmosphere entry (h-h_atm, downward).  Returns (apogee_state,
    entry_state, t_apo, t_entry, clearance, d_entry).  Dense-root based;
    never attaches an entry event at t=0.  Raises ``VacExcursionFailure``
    (never bare ``RuntimeError``) so failures carry a structured status."""
    from scipy.integrate import solve_ivp
    from hyptraj.modes.sanger_hybrid import sanger_vac_rhs
    from hyptraj.simulation.sanger_events import (
        atmosphere_interface_value,
    )

    st = PairedExcursionClass
    bad = _nonphysical_state(x_start, env)
    if bad is not None:
        raise VacExcursionFailure(st.NONPHYSICAL_STATE, bad)
    x0 = np.asarray(x_start, dtype=float)
    # A valid short VAC excursion starts ascending; gamma<=0 means the
    # apogee (up->down) topology can never fire -> excursion topology lost.
    if float(x0[3]) <= 0.0:
        raise VacExcursionFailure(
            st.VAC_EXCURSION_LOST,
            f"gamma = {float(x0[3]):.6g} <= 0 at excursion start: "
            "ascending short-VAC topology lost.")

    def ev_apo(t, s, *a):
        return float(s[3])
    ev_apo.terminal = True
    ev_apo.direction = -1

    def ev_entry(t, s, *a):
        return atmosphere_interface_value(np.asarray(s), env)
    ev_entry.terminal = True
    ev_entry.direction = -1

    atol = getattr(cfg, "state_atol", getattr(cfg, "atol", None))
    rtol = getattr(cfg, "rtol", 1e-12)
    ms = getattr(cfg, "max_step", 0.1)
    sol = solve_ivp(
        lambda t, s: sanger_vac_rhs(t, np.asarray(s), env, vehicle),
        (0.0, horizon), x0,
        method="DOP853", rtol=rtol, atol=atol, max_step=ms,
        dense_output=True, events=[ev_apo])
    if not sol.success:
        raise VacExcursionFailure(
            st.NUMERICAL_FAILURE, f"VAC apogee integrator failed: {sol.message}")
    if sol.t_events[0].size == 0:
        # No up->down turnover within the horizon: escape / non-terminating
        # topology, NOT an integrator error.
        raise VacExcursionFailure(
            st.VAC_APOGEE_NOT_FOUND,
            "no VAC apogee (up->down gamma turnover) within the horizon.")
    t_apo = float(sol.t_events[0][0])
    x_apo = np.asarray(sol.y[:, -1], dtype=float)
    sol2 = solve_ivp(
        lambda t, s: sanger_vac_rhs(t, np.asarray(s), env, vehicle),
        (t_apo, t_apo + horizon), x_apo,
        method="DOP853", rtol=rtol, atol=atol, max_step=ms,
        dense_output=True, events=[ev_entry])
    if not sol2.success:
        raise VacExcursionFailure(
            st.NUMERICAL_FAILURE, f"VAC entry integrator failed: {sol2.message}")
    if sol2.t_events[0].size == 0:
        # Re-entry (downward) never found within the horizon: the excursion
        # left the atmosphere and did not return -> topology lost.
        raise VacExcursionFailure(
            st.VAC_EXCURSION_LOST,
            "no atmosphere re-entry found after apogee within the horizon.")
    t_entry = float(sol2.t_events[0][0])
    x_entry = np.asarray(sol2.y[:, -1], dtype=float)
    clearance = float(x_apo[0] - env.earth_radius - env.atmosphere_boundary)
    d_entry = float(x_entry[2] * np.sin(x_entry[3]))
    # The entry event fires downward (direction -1); require the
    # reconstructed denominator to agree (wrong orientation = bad root).
    if d_entry >= 0.0:
        raise VacExcursionFailure(
            st.WRONG_ENTRY_DIRECTION,
            f"reconstructed entry denominator d_entry = {d_entry:.6g} >= 0 "
            "(entry must be descending into the atmosphere).")
    return x_apo, x_entry, t_apo, t_entry, clearance, d_entry


def controlled_local_grazing_family(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    alphas=(1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625),
    ref_cfg_01=None,
    ref_cfg_05=None,
) -> tuple[list[ControlledFamilyPoint], int]:
    """CONTROLLED_LOCAL_GRAZING_FAMILY (G6 §16-§20, §53).

    Holds altitude/theta/velocity fixed at the actual near-grazing exit
    state and continuously reduces the interface incidence ``gamma ->
    alpha*gamma_exit`` toward tangency.  NOT trajectory-backed (states are
    not claimed to arise from any gamma0-K point).  Stops at the first
    numerically unstable layer (NUMERICAL_RESOLUTION_LIMIT).
    """
    from hyptraj.analysis.comparison_validation import (
        REFERENCE_05_SOLVER_CONFIG,
        REFERENCE_SOLVER_CONFIG,
    )
    from hyptraj.predictability.stm import (
        stm_companion_reference_config,
        stm_strict_reference_config,
    )

    ref01_c = ref_cfg_01 or REFERENCE_SOLVER_CONFIG
    ref05_c = ref_cfg_05 or REFERENCE_05_SOLVER_CONFIG
    stm01 = None
    stm05 = None
    x0 = np.asarray(exit_state, dtype=float)
    r_e, v_e, gamma_e = x0[0], x0[2], x0[3]
    points = []
    last_stable_index = -1
    for idx, alpha in enumerate(alphas):
        if alpha <= 0.0 or alpha > 1.0:
            continue
        xa = np.array([r_e, x0[1], v_e, alpha * gamma_e], dtype=float)
        try:
            apo01, ent01, _t, t_e01, clr01, d_in01 = _run_vac_excursion(
                xa, env, vehicle, ref01_c)
            apo05, ent05, _t2, t_e05, clr05, d_in05 = _run_vac_excursion(
                xa, env, vehicle, ref05_c)
        except RuntimeError:
            points.append(ControlledFamilyPoint(
                alpha=alpha, gamma_exit_rad=alpha * gamma_e,
                d_exit=float(v_e * np.sin(alpha * gamma_e)),
                apogee_clearance_m=float("nan"),
                vac_duration_s=float("nan"),
                d_entry=float("nan"),
                entry_state=np.zeros(4),
                ref_stable=False,
                classification="NUMERICAL_RESOLUTION_LIMIT"))
            break
        stable = (abs(t_e01 - t_e05) < 1e-6
                  and abs(clr01 - clr05) < 1e-3
                  and np.max(np.abs(ent01 - ent05)) < 1e-3)
        if not stable:
            points.append(ControlledFamilyPoint(
                alpha=alpha, gamma_exit_rad=alpha * gamma_e,
                d_exit=float(v_e * np.sin(alpha * gamma_e)),
                apogee_clearance_m=clr01,
                vac_duration_s=float(t_e01),
                d_entry=d_in01,
                entry_state=ent01,
                ref_stable=False,
                classification="NUMERICAL_RESOLUTION_LIMIT"))
            break
        points.append(ControlledFamilyPoint(
            alpha=alpha, gamma_exit_rad=alpha * gamma_e,
            d_exit=float(v_e * np.sin(alpha * gamma_e)),
            apogee_clearance_m=clr01,
            vac_duration_s=float(t_e01),
            d_entry=d_in01,
            entry_state=ent01,
            ref_stable=True,
            classification="REF_STABLE"))
        last_stable_index = idx
    return points, last_stable_index


# ---------------------------------------------------------------------------
# Paired excursion factor (G6 §24-§25)
# ---------------------------------------------------------------------------
def build_excursion_factor(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    c_vac_config=None,
    scales=None,
) -> ExcursionFactor:
    """``P = Xi_entry @ C_VAC @ Xi_exit`` (matrix order locked, G6 §24)."""
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs, sanger_vac_rhs
    from hyptraj.predictability.saltation import identity_reset_saltation
    from hyptraj.predictability.stm import integrate_continuous_stm

    scales = scales or _canonical_scales()
    x = np.asarray(exit_state, dtype=float)
    ctl = ConstantKControl(k)
    f_atm = sanger_atm_rhs(0.0, x, env, vehicle, ctl)
    f_vac = sanger_vac_rhs(0.0, x, env, vehicle)
    n = np.array([1.0, 0.0, 0.0, 0.0])
    xi_exit = identity_reset_saltation(f_atm, f_vac, n)

    # VAC continuous STM via G2 integrate_continuous_stm (raw physical).
    if c_vac_config is None:
        from hyptraj.predictability.stm import stm_strict_reference_config
        c_vac_config = stm_strict_reference_config()
    from hyptraj.predictability.stm import StmSolverConfig
    stm_cfg = (c_vac_config if isinstance(c_vac_config, StmSolverConfig)
               else stm_strict_reference_config())
    # Reconstruct the VAC excursion span (apogee -> matching entry) using
    # the G6 local VAC reconstruction; then integrate the G2 augmented VAC
    # STM over [0, t_entry] from the exact exit state.
    _, ent_state, _t_apo, t_entry, _clr, d_in = _run_vac_excursion(
        x, env, vehicle, stm_cfg)
    c_vac = integrate_continuous_stm(
        "sanger_vac", x, (0.0, float(t_entry)), env, vehicle, k,
        solver=stm_cfg)
    x_entry = ent_state
    f_vac_e = sanger_vac_rhs(0.0, x_entry, env, vehicle)
    f_atm_e = sanger_atm_rhs(0.0, x_entry, env, vehicle, ctl)
    xi_entry = identity_reset_saltation(f_vac_e, f_atm_e, n)

    p = xi_entry @ c_vac.phi @ xi_exit
    S = np.diag([scales[v] for v in ("r", "theta", "v", "gamma")])
    S_inv = np.diag(1.0 / np.diag(S))
    p_tilde = S_inv @ p @ S
    u, sigma, vt = np.linalg.svd(p_tilde)
    u, v = canonicalize_svd_signs(u, vt.T)
    cond = condition_status(sigma)
    return ExcursionFactor(
        exit_lin_matrix=xi_exit,
        c_vac=c_vac.phi,
        entry_lin_matrix=xi_entry,
        p_excursion=p,
        p_scaled=p_tilde,
        singular_values=sigma,
        sigma_max=float(sigma[0]) if sigma.size else 0.0,
        condition_status=cond["condition_status"],
        numerical_rank=numerical_rank(sigma),
        nullity=int(_STATE_DIM - numerical_rank(sigma)),
        norm_scaled_minus_I=float(np.linalg.norm(p_tilde - np.eye(4), ord=2)),
        dominant_input_scaled=v[:, 0],
        dominant_output_scaled=u[:, 0],
        metadata={
            "exit_vac_duration_s": float(t_entry),
            "exit_entry_denominator": float(d_in),
        },
    )


# ---------------------------------------------------------------------------
# Local paired grazing-excursion nonlinear map (G6 §34-§37)
# ---------------------------------------------------------------------------
class PairedExcursionClass:
    """Paired ``M_excursion`` outcome classes (G6 §36, G6R Issue 5).

    Topology/direction loss (``EXIT_NO_LOCAL_ROOT``, ``WRONG_EXIT_DIRECTION``,
    ``WRONG_ENTRY_DIRECTION``, ``VAC_APOGEE_NOT_FOUND``, ``VAC_EXCURSION_LOST``,
    ``NONPHYSICAL_STATE``) is deliberately separated from pure numerical
    failure (``NUMERICAL_FAILURE``): a lost excursion is a topology
    statement, not a solver defect."""

    PAIR_LOCAL_VALID = "PAIR_LOCAL_VALID"
    EXIT_NO_LOCAL_ROOT = "EXIT_NO_LOCAL_ROOT"
    WRONG_EXIT_DIRECTION = "WRONG_EXIT_DIRECTION"
    WRONG_ENTRY_DIRECTION = "WRONG_ENTRY_DIRECTION"
    VAC_EXCURSION_LOST = "VAC_EXCURSION_LOST"
    VAC_APOGEE_NOT_FOUND = "VAC_APOGEE_NOT_FOUND"
    ENTRY_NO_ROOT = "ENTRY_NO_ROOT"
    NONPHYSICAL_STATE = "NONPHYSICAL_STATE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


def _atm_flow_duration(x_start, duration, env, vehicle, ctl, cfg):
    """Integrated ATM RHS for a signed duration (m->s flow)."""
    from scipy.integrate import solve_ivp
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs

    x_start = np.asarray(x_start, dtype=float)
    if abs(duration) < 1e-12:
        return x_start.copy()
    dt = float(duration)
    rhs = (lambda t, s: sanger_atm_rhs(t, np.asarray(s), env, vehicle, ctl)) \
        if dt >= 0 else \
        (lambda t, s: -sanger_atm_rhs(t, np.asarray(s), env, vehicle, ctl))
    atol = getattr(cfg, "state_atol", getattr(cfg, "atol", None))
    sol = solve_ivp(rhs, (0.0, abs(dt)), x_start, method="DOP853",
                    rtol=getattr(cfg, "rtol", 1e-12), atol=atol,
                    max_step=getattr(cfg, "max_step", 0.1), dense_output=True)
    if not sol.success:
        raise RuntimeError("ATM duration flow failed.")
    return np.asarray(sol.y[:, -1], dtype=float)


def local_grazing_excursion_map(
    exit_state: np.ndarray,
    delta_x: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    cfg,
    nominal_vac_duration: float,
) -> tuple[np.ndarray, str, dict]:
    """Paired nonlinear map ``M_excursion(dx)`` (G6 §35-§36).

    Steps: pre-event ATM root -> (identity reset) -> VAC to matching entry
    (apogee checks) -> (identity reset) -> ATM flow sync to the nominal
    vacation duration ``nominal_vac_duration``.  ``DM_excursion(0) =
    P_excursion`` (validated by FD).

    G6R Issue 5 routing: outcome classes separate topology/direction loss
    (``EXIT_NO_LOCAL_ROOT``, ``WRONG_EXIT_DIRECTION``,
    ``WRONG_ENTRY_DIRECTION``, ``NONPHYSICAL_STATE``,
    ``VAC_APOGEE_NOT_FOUND``, ``VAC_EXCURSION_LOST``) from integrator
    failure (``NUMERICAL_FAILURE``); ``_run_vac_excursion`` now raises with
    a structured status instead of a bare ``RuntimeError``.
    """
    from hyptraj.modes.sanger_hybrid import sanger_atm_rhs, sanger_vac_rhs
    from hyptraj.predictability.saltation import (
        local_event_crossing_time,
    )

    st = PairedExcursionClass
    ctl = ConstantKControl(k)
    x_e = np.asarray(exit_state, dtype=float)
    x_pert = x_e + np.asarray(delta_x, dtype=float)
    # nonphysical-state guard (G6R Issue 5)
    bad = _nonphysical_state(x_pert, env)
    if bad is not None:
        return None, st.NONPHYSICAL_STATE, {"reason": bad}

    def atm_rhs(s):
        return sanger_atm_rhs(0.0, np.asarray(s, dtype=float), env, vehicle, ctl)

    def exit_surf(t, s):
        return float(s[0] - env.earth_radius - env.atmosphere_boundary)

    tau, x_exit_p, meta = local_event_crossing_time(
        atm_rhs, exit_surf, x_pert, cfg)
    if tau is None:
        return None, st.EXIT_NO_LOCAL_ROOT, meta
    # The crossing must be an upward-velocity ATM->VAC exit.
    d_cross = float(x_exit_p[2] * np.sin(x_exit_p[3]))
    if d_cross <= 0.0:
        return None, st.WRONG_EXIT_DIRECTION, {
            "reason": f"exit denominator d = {d_cross:.6g} <= 0 at crossing",
            "tau_exit": tau}
    # identity reset then VAC excursion (structured failures)
    try:
        x_apo, x_entry, _tA, t_entry, _clr, d_in = _run_vac_excursion(
            x_exit_p, env, vehicle, cfg)
    except VacExcursionFailure as e:
        return None, e.status, {"reason": str(e)}
    # Defensive: the entry root must also be descending.
    if d_in >= 0.0:
        return None, st.WRONG_ENTRY_DIRECTION, {
            "reason": f"entry denominator d = {d_in:.6g} >= 0", "tau_exit": tau}
    # sync ATM to the nominal vacation duration
    total = tau + float(t_entry)  # local elapsed at perturbed entry
    sync = nominal_vac_duration - total
    y_plus = _atm_flow_duration(x_entry, sync, env, vehicle, ctl, cfg)
    return y_plus, st.PAIR_LOCAL_VALID, {
        "tau_exit": tau, "vac_duration": float(t_entry), "sync": float(sync)}


def excursion_fd_sweep(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    cfg,
    nominal_vac_duration: float,
    column: int,
    epsilons,
) -> dict:
    """Centered FD of ``M_excursion`` vs ``P_excursion(:, column)`` (G6 §37)."""
    from hyptraj.predictability.hybrid_stm import true_switch_events_before  # noqa
    out = {}
    for eps in epsilons:
        e = np.zeros(_STATE_DIM)
        e[column] = 1.0
        mp, cp, _ = local_grazing_excursion_map(
            exit_state, eps * e, env, vehicle, k, cfg, nominal_vac_duration)
        mm, cm, _ = local_grazing_excursion_map(
            exit_state, -eps * e, env, vehicle, k, cfg, nominal_vac_duration)
        if mp is None or mm is None:
            out[eps] = {"fd": None, "cls_plus": cp, "cls_minus": cm}
            continue
        fd = (mp - mm) / (2.0 * eps)
        out[eps] = {"fd": fd, "cls_plus": cp, "cls_minus": cm}
    return out


# ---------------------------------------------------------------------------
# G6R Issue 3/4: live paired FD -- radial derivative plateau + full 4-column
# validation (canonical-A scaled errors)
# ---------------------------------------------------------------------------
def _canonical_scale_vector() -> np.ndarray:
    """Canonical-A scale vector [[r],[theta],[v],[gamma]] (G5 frozen)."""
    s = _canonical_scales()
    return np.array([s[v] for v in ("r", "theta", "v", "gamma")], dtype=float)


def _scaled_residual(fd, pcol, relative):
    """Canonical-A scaled residual ``||S^-1 (fd - pcol)||`` (absolute) or
    its scaled-relative form (divided by the scaled column norm)."""
    svec = _canonical_scale_vector()
    resid = float(np.linalg.norm((fd - pcol) / svec))
    if relative:
        norm_ref = float(np.linalg.norm(pcol / svec))
        return resid / max(norm_ref, 1e-12)
    return resid


def paired_radial_fd_plateau(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    cfg,
    nominal_vac_duration: float,
    phi_local: float,
    beta_grid=(1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2),
    tolerance: float = 1e-2,
) -> dict:
    """Radial-column DERIVATIVE PLATEAU of the paired map at
    clearance-normalized ``beta = dr/phi_local`` (G6R Issue 3).

    Live centered FD of ``M_excursion`` along ``e_r`` at every ``beta`` in
    [1e-4, 3e-2] (NOT ``beta = 0.5`` with a <50% tolerance).  The plateau
    passes only when BOTH sides are ``PAIR_LOCAL_VALID`` at every beta AND
    the canonical-A scaled-relative error vs ``P_excursion[:, 0]`` stays
    below ``tolerance``.  This is the operational validity-domain
    acceptance: the derivative tracks the analytic pair on a scale-free
    plateau far from the grazing singularity.
    """
    st = PairedExcursionClass
    from hyptraj.predictability.stm import stm_strict_reference_config
    cfg2 = cfg if cfg is not None else stm_strict_reference_config()
    fac = build_excursion_factor(exit_state, env, vehicle, k,
                                 c_vac_config=cfg2)
    pcol = np.asarray(fac.p_excursion[:, 0], dtype=float)

    records = []
    for beta in beta_grid:
        eps = float(beta) * float(phi_local)
        e = np.zeros(_STATE_DIM, dtype=float)
        e[0] = 1.0
        mp, cp, _ = local_grazing_excursion_map(
            exit_state, eps * e, env, vehicle, k, cfg2, nominal_vac_duration)
        mm, cm, _ = local_grazing_excursion_map(
            exit_state, -eps * e, env, vehicle, k, cfg2, nominal_vac_duration)
        rec = {"beta": float(beta), "dr_m": float(eps),
               "cls_plus": cp, "cls_minus": cm}
        if mp is None or mm is None:
            rec["scaled_rel_error"] = None
            rec["both_valid"] = False
            records.append(rec)
            continue
        fd = (mp - mm) / (2.0 * eps)
        rec["scaled_rel_error"] = _scaled_residual(fd, pcol, relative=True)
        rec["both_valid"] = True
        records.append(rec)
    errs = [r["scaled_rel_error"] for r in records
            if r["scaled_rel_error"] is not None]
    both_valid = all(r["both_valid"] for r in records)
    max_err = float(max(errs)) if errs else float("inf")
    plateau_pass = bool(both_valid and max_err < float(tolerance))
    return {
        "plateau_beta_range": [float(beta_grid[0]), float(beta_grid[-1])],
        "records": records,
        "max_scaled_rel_error": max_err,
        "both_sides_valid": both_valid,
        "tolerance": float(tolerance),
        "plateau_pass": plateau_pass,
        "note": ("radial derivative plateau at clearance-normalized beta in "
                 "[1e-4, 3e-2]; acceptance on plateau, not digit-sampled 0.5"),
    }


_PAIRED_FD_COLUMN_GRIDS = {
    0: ("beta", (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2),
        1e-2),  # clearance-normalized, relative err
    1: ("rad", (1e-7, 1e-6, 1e-5, 1e-4, 1e-3), 1e-3),   # theta
    2: ("mps", (1e-4, 1e-3, 1e-2, 1e-1, 1.0), 1e-3),    # velocity
    3: ("frac", (0.01, 0.03, 0.1, 0.3, 0.5), 1e-3),  # frac(gamma_exit); stays
        # strictly INSIDE the incidence cone (|Δγ| < γ_exit): at frac=1.0
        # the minus side starts at γ≈0 grazing-degenerate, so the exit
        # crossing is direction-ambiguous (WRONG_EXIT_DIRECTION).
}


def paired_fd_validation(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    cfg,
    nominal_vac_duration: float,
    phi_local: float,
    gamma_exit_rad: float,
) -> dict:
    """FULL 4-column paired-map FD validation (G6R Issue 4).

    Per column a multi-epsilon sweep of live centered FD vs the analytic
    ``P_excursion`` column in canonical-A scaled coordinates.  The radial
    column (the naive-validity dimension) is swept on the
    clearance-normalized plateau and accepted on its scaled-RELATIVE error;
    the tangent columns are swept at physical scales (theta rad / v m/s)
    and at fractions of the exit incidence for gamma, and accepted on the
    ABSOLUTE scaled residual (their scaled columns can be tiny or dominated
    by the small-incidence cone, so relative error is not well-posed).
    ``column_pass`` requires every epsilon to have both sides
    ``PAIR_LOCAL_VALID`` and the per-column metric below its tolerance.
    """
    st = PairedExcursionClass
    from hyptraj.predictability.stm import stm_strict_reference_config
    cfg2 = cfg if cfg is not None else stm_strict_reference_config()
    fac = build_excursion_factor(exit_state, env, vehicle, k,
                                 c_vac_config=cfg2)
    pcol = np.asarray(fac.p_excursion, dtype=float)
    phi = float(phi_local)
    ge = float(gamma_exit_rad)

    columns = {}
    all_pass = True
    for j in range(_STATE_DIM):
        kind, grid_vals, tol = _PAIRED_FD_COLUMN_GRIDS[j]
        if kind == "beta":
            epsilons = [float(b) * phi for b in grid_vals]
        elif kind == "frac":
            epsilons = [float(f) * abs(ge) for f in grid_vals]
        else:
            epsilons = [float(v) for v in grid_vals]
        records = []
        for eps in epsilons:
            e = np.zeros(_STATE_DIM, dtype=float)
            e[j] = 1.0
            mp, cp, _ = local_grazing_excursion_map(
                exit_state, eps * e, env, vehicle, k, cfg2,
                nominal_vac_duration)
            mm, cm, _ = local_grazing_excursion_map(
                exit_state, -eps * e, env, vehicle, k, cfg2,
                nominal_vac_duration)
            rec = {"eps": float(eps), "cls_plus": cp, "cls_minus": cm}
            if mp is None or mm is None:
                rec["scaled_rel_error"] = None
                rec["abs_scaled_residual"] = None
                rec["both_valid"] = False
                records.append(rec)
                continue
            fd = (mp - mm) / (2.0 * eps)
            rec["scaled_rel_error"] = _scaled_residual(
                fd, pcol[:, j], relative=True)
            rec["abs_scaled_residual"] = _scaled_residual(
                fd, pcol[:, j], relative=False)
            rec["both_valid"] = True
            records.append(rec)
        both_valid = all(r["both_valid"] for r in records)
        met = "scaled_rel_error" if j == 0 else "abs_scaled_residual"
        vals = [r[met] for r in records if r[met] is not None]
        max_m = float(max(vals)) if vals else float("inf")
        pass_col = bool(both_valid and max_m < float(tol))
        all_pass = all_pass and pass_col
        columns[j] = {
            "direction": "e_r" if j == 0 else ("e_theta" if j == 1
                                              else ("e_v" if j == 2 else "e_gamma")),
            "epsilon_unit": kind,
            "records": records,
            "both_sides_valid": both_valid,
            "metric": met,
            "max_error": max_m,
            "tolerance": float(tol),
            "column_pass": pass_col,
        }
    return {"four_column_pass": bool(all_pass), "columns": columns}


# ---------------------------------------------------------------------------
# G6R Issue 2: refined operational validity radius (bracket + deterministic
# bisection on the clearance-normalized beta coordinate; NOT grid-sampled
# lower bounds)
# ---------------------------------------------------------------------------
_VALIDITY_BETA_GRID = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2,
                       1e-1, 2e-1, 3e-1, 5e-1, 7e-1, 1.0, 1.5, 2.0)


def _elin_probe(exit_state, eps, env, vehicle, k, cfg, nominal_vac_duration,
                phi_local, pcol):
    """Single radial linearization-error probe.

    Returns a dict ``{E_pair, E_plus, E_minus, fd_scaled_norm, valid,
    cls_plus, cls_minus}`` with ``E_pair = max(E_plus, E_minus)`` (G6 §36;
    G6R Issue 2).  ``fd_scaled_norm`` is the canonical-A scaled norm of the
    centered radial FD column (the derivative-plateau diagnostic used by
    G6; ``||S^-1 FD||``).  A ``None`` map -> ``valid=False`` with the
    failing side's class (topology-side failure)."""
    st = PairedExcursionClass
    e = np.zeros(_STATE_DIM, dtype=float)
    e[0] = 1.0
    M0, c0, _ = local_grazing_excursion_map(
        exit_state, np.zeros(_STATE_DIM), env, vehicle, k, cfg,
        nominal_vac_duration)
    Mp, cp, _ = local_grazing_excursion_map(
        exit_state, eps * e, env, vehicle, k, cfg, nominal_vac_duration)
    Mm, cm, _ = local_grazing_excursion_map(
        exit_state, -eps * e, env, vehicle, k, cfg, nominal_vac_duration)
    fail = {"E_pair": None, "E_plus": None, "E_minus": None,
            "fd_scaled_norm": None, "valid": False,
            "cls_plus": cp, "cls_minus": cm}
    if M0 is None or Mp is None or Mm is None:
        return fail
    svec = _canonical_scale_vector()
    Ep = np.linalg.norm((Mp - (M0 + eps * pcol)) / svec) / \
        max(np.linalg.norm((Mp - M0) / svec), 1e-15)
    Em = np.linalg.norm((Mm - (M0 - eps * pcol)) / svec) / \
        max(np.linalg.norm((Mm - M0) / svec), 1e-15)
    fd = (Mp - Mm) / (2.0 * eps)
    fail.update({
        "E_pair": float(max(Ep, Em)), "E_plus": float(Ep),
        "E_minus": float(Em),
        "fd_scaled_norm": float(np.linalg.norm(fd / svec)),
        "valid": True, "cls_plus": cp, "cls_minus": cm})
    return fail


def refined_operational_radius(
    exit_state: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k: float,
    cfg,
    nominal_vac_duration: float,
    phi_local: float,
    taus=(0.01, 0.05),
    grid=_VALIDITY_BETA_GRID,
    max_bisections: int = 24,
) -> dict:
    """REFINED operational validity radius (G6R Issue 2).

    ``r_tau = sup{ beta*phi_local : both sides PAIR_LOCAL_VALID and
    E_pair(beta*phi_local) <= tau }`` on the clearance-normalized beta
    coordinate.  Unlike G6 (which returned only the coarse grid sample
    below the crossing), this brackets ``[beta_lo (PASS), beta_hi (FAIL)]``
    and runs a deterministic bisection on the E_pair>tau predicate.  If the
    validity profile is non-monotone (E_pair rises, falls, then rises
    again, or a FAIL beta precedes a PASS beta) the profile is classified
    ``NONMONOTONE_VALIDITY_PROFILE`` and no refined beta is claimed.
    Returns per-tau: lower_pass_beta, upper_fail_beta, refined_beta,
    refined_radius_m, radius_over_phi, bracket_width.
    """
    st = PairedExcursionClass
    from hyptraj.predictability.stm import stm_strict_reference_config
    cfg2 = cfg if cfg is not None else stm_strict_reference_config()
    fac = build_excursion_factor(exit_state, env, vehicle, k,
                                 c_vac_config=cfg2)
    pcol = np.asarray(fac.p_excursion[:, 0], dtype=float)
    phi = float(phi_local)

    probes = []
    for beta in grid:
        eps = float(beta) * phi
        probe = _elin_probe(
            exit_state, eps, env, vehicle, k, cfg2,
            nominal_vac_duration, phi, pcol)
        probes.append({
            "beta": float(beta),
            "E_pair": probe["E_pair"],
            "E_plus": probe["E_plus"],
            "E_minus": probe["E_minus"],
            "fd_scaled_norm": probe["fd_scaled_norm"],
            "valid": probe["valid"],
            "cls_plus": probe["cls_plus"],
            "cls_minus": probe["cls_minus"]})

    radii = {}
    monotone_profile = True
    for tau in taus:
        t = float(tau)
        # lower PASS = largest beta with E<=tau and both-side-valid.
        lower = None
        for p in probes:
            if p["valid"] and p["E_pair"] is not None and p["E_pair"] <= t:
                lower = p["beta"]
        # upper FAIL = smallest beta > lower that either exceeds tau or
        # loses topology.
        upper = None
        upper_reason = None
        if lower is not None:
            for p in probes:
                if p["beta"] <= lower:
                    continue
                if not p["valid"] or p["E_pair"] is None or p["E_pair"] > t:
                    upper = p["beta"]
                    upper_reason = ("topology" if not p["valid"] else "E>tau")
                    break
        rec = {
            "tau": t,
            "lower_pass_beta": lower,
            "upper_fail_beta": upper,
            "upper_fail_reason": upper_reason,
            "refined_beta": None,
            "refined_radius_m": None,
            "radius_over_phi": None,
            "bracket_width": None,
        }
        if lower is None:
            rec["classification"] = "NO_PASS_BOUND_IN_GRID"
            radii[f"r_{int(t*100)}pct"] = rec
            continue
        if upper is None:
            rec["classification"] = "CAP_EXTENDS_ABOVE_MAX_BETA"
            radii[f"r_{int(t*100)}pct"] = rec
            continue
        # NONMONOTONE only when a probe at beta > upper_fail re-PASSES tau:
        # the sup{r: E(r)<=tau} set is then non-contiguous and the
        # refined crossing is not well-defined.  (Tiny-beta rounding-noise
        # dips BELOW tau do not make the profile non-monotone.)
        re_entrant = any(
            p["valid"] and p["E_pair"] is not None and p["E_pair"] <= t
            for p in probes if p["beta"] > upper)
        if re_entrant:
            rec["classification"] = "NONMONOTONE_VALIDITY_PROFILE"
            radii[f"r_{int(t*100)}pct"] = rec
            monotone_profile = False
            continue
        # deterministic bisection on E_pair<=tau && both-sides-valid
        lo, hi = lower, upper
        for _ in range(max_bisections):
            mid = 0.5 * (lo + hi)
            eps = mid * phi
            probe = _elin_probe(
                exit_state, eps, env, vehicle, k, cfg2,
                nominal_vac_duration, phi, pcol)
            if probe["valid"] and probe["E_pair"] is not None \
                    and probe["E_pair"] <= t:
                lo = mid
            else:
                hi = mid
        refined = 0.5 * (lo + hi)
        if upper_reason == "topology":
            rec["classification"] = "TOPOLOGY_LIMITED_BELOW_TAU"
        else:
            rec["classification"] = "MONOTONE_REFINED_RADIUS"
        rec.update({
            "refined_beta": float(refined),
            "refined_radius_m": float(refined * phi),
            "radius_over_phi": float(refined),
            "bracket_width": float(hi - lo),
        })
        radii[f"r_{int(t*100)}pct"] = rec
    return {
        "phi_local_m": phi,
        "beta_probes": probes,
        "monotone_profile": bool(monotone_profile),
        "radii": radii,
    }


# ---------------------------------------------------------------------------
# Log-log scaling fit (G6 §21-§23, §57)
# ---------------------------------------------------------------------------
def fit_loglog_scaling(xs, ys):
    """OLS fit of ``log(ys) = a + p log(xs)`` on positive, REF-stable
    tail points (G6 §21-§23, §57)."""
    xs = [float(v) for v in xs]
    ys = [float(v) for v in ys]
    sel = [i for i in range(min(len(xs), len(ys)))
           if xs[i] > 0.0 and ys[i] > 0.0]
    if len(sel) < 2:
        return {"n_points": len(sel), "slope": None, "intercept": None,
                "r2": None}
    xs_p = np.log(np.asarray([xs[i] for i in sel]))
    ys_p = np.log(np.asarray([ys[i] for i in sel]))
    A = np.vstack([xs_p, np.ones_like(xs_p)]).T
    coef, *_ = np.linalg.lstsq(A, ys_p, rcond=None)
    resid = ys_p - A @ coef
    ss = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((ys_p - np.mean(ys_p)) ** 2))
    r2 = 1.0 - ss / ss_tot if ss_tot > 0 else None
    return {"n_points": len(sel), "slope": float(coef[0]),
            "intercept": float(coef[1]), "r2": r2}


# ---------------------------------------------------------------------------
# Actual-anchor directional topology radius (G6 §39-§42)
# ---------------------------------------------------------------------------
def directional_topology_radius(
    model: str,
    x0: np.ndarray,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    nominal_kind: str,
    nominal_sig: tuple[str, ...],
    direction: int,
    sign: float,
    research_solver,
    cap: float,
    k: float = 3.0,
    starts: tuple = (1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0),
) -> dict:
    """One-sided topology-change radius via geometric expansion + bisection.

    Uses the terminal topology gate (G5R) on full frozen research
    trajectories: preserved iff terminal_kind == nominal AND preterminal
    signature == nominal.  ``k`` is the FROZEN anchor aerodynamic L/D of
    the trajectory under study (NOT the baseline 3.0).  Returns
    ``LOWER_BOUND_ONLY`` if no transition within ``cap``.
    """
    from hyptraj.predictability.terminal_sensitivity import classify_terminal_side
    from hyptraj.predictability.hybrid_validation import run_nonlinear_hybrid

    preserved = []
    e = np.zeros(_STATE_DIM)
    e[direction] = sign

    # geometric expansion for the bracket
    lo = 0.0
    hi = None
    for s in starts:
        if s > cap:
            break
        result, _ = run_nonlinear_hybrid(
            model, x0 + s * e, env, vehicle, k, research_solver)
        gate, _ = classify_terminal_side(
            model, nominal_kind, nominal_sig, result)
        if gate.value == "TOPOLOGY_PRESERVED":
            lo = s
            preserved.append(s)
        else:
            hi = s
            break
    if hi is None:
        if lo == 0.0:
            return {"epsilon": None, "classification": "LOWER_BOUND_ONLY",
                    "note": "no preserved bracket found in the search"}
        return {"epsilon": float(cap), "classification": "LOWER_BOUND_ONLY",
                "note": "preserved up to the declared cap"}
    # bisection between lo (preserved) and hi (changed)
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        result, _ = run_nonlinear_hybrid(
            model, x0 + mid * e, env, vehicle, k, research_solver)
        gate, _ = classify_terminal_side(
            model, nominal_kind, nominal_sig, result)
        if gate.value == "TOPOLOGY_PRESERVED":
            lo = mid
        else:
            hi = mid
    transition = 0.5 * (lo + hi)
    result_hi, _ = run_nonlinear_hybrid(
        model, x0 + hi * e, env, vehicle, k, research_solver)
    gate_hi, info_hi = classify_terminal_side(
        model, nominal_kind, nominal_sig, result_hi)
    return {
        "epsilon": float(transition),
        "classification": gate_hi.value,
        "reason": info_hi.get("reason"),
        "upper_bracket": float(hi),
        "lower_bracket": float(lo),
        "preserved_samples": preserved,
    }
