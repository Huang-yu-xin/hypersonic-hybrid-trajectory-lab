"""Phase E common-condition comparison protocols (E2).

Strict implementations of the frozen E0 protocols:

* Protocol B -- Common-Time Comparison (E0 §7): at
  ``t_common = min(T_Q_RTI, T_S_SRTI)`` evaluate both realized states
  continuously and form the primary differences
  ``DeltaR_time = R_S - R_Q``, ``DeltaV_time = v_S - v_Q``,
  ``DeltaE_time = E_S - E_Q``;

* Protocol C -- Common-Range Comparison (E0 §8): at
  ``R_common = min(R_Q_RTI, R_S_SRTI)`` invert both research
  trajectories through the E1 segment-aware root solver and form
  ``time_saving = t_Q - t_S`` (positive: Sanger arrives earlier),
  ``DeltaV_range = v_S - v_Q``, ``DeltaE_range = E_S - E_Q``.

Rules enforced here (E0 §5-§8, §10, §16, §17, §25, E1 §16-§18):

* continuous evaluation only (E1 ``ComparisonTrajectory`` dense API);
* no native-endpoint gain claim and no Protocol D (atmospheric
  exposure) metric is produced;
* energy loss is ``E0 - E`` (never ``abs``, never clipped);
* the common initial mechanical energy is verified to be numerically
  equal across both trajectories before any loss is formed;
* the downrange monotonicity prerequisite is re-checked before every
  common-range inversion;
* the endpoint-identity checks are conditional structural assertions
  (either side may be the limiting endpoint), never hard-coded.
"""

from dataclasses import dataclass

import numpy as np

from hyptraj.analysis.comparison import (
    ComparisonState,
    ComparisonTrajectory,
)

# Numerical-zero tolerance for the common initial mechanical energy
# (E ~ -3.4e7 J/kg; state agreement at the 1e-9 relative level maps to
# ~1e-4 J/kg).  Far below any reporting precision (MJ/kg).
INITIAL_ENERGY_ZERO_TOL_JPKG = 1e-3

# Root-residual policy for common-range checkpoints (E1 §18): the
# segment-aware brentq runs with xtol=1e-10 s, so dR/dt * xtol ~ 1e-7 m;
# 1e-3 m is a generous integrity bound, far below reporting precision.
RANGE_RESIDUAL_TOL_M = 1e-3

# Production-precision consistency bound for endpoint-identity checks.
_STATE_RTOL = 1e-9
_STATE_ATOL = 1e-9
_TIME_TOL_S = 1e-6


@dataclass(frozen=True)
class CommonTimeComparison:
    """Protocol B result: both realized states at the same elapsed time."""

    common_time_s: float
    qian_state: ComparisonState
    sanger_state: ComparisonState

    delta_range_m: float
    delta_altitude_m: float
    delta_velocity_mps: float
    delta_specific_energy_jpkg: float

    qian_energy_loss_jpkg: float
    sanger_energy_loss_jpkg: float

    qian_mode: str
    sanger_mode: str
    qian_source_mode: str
    sanger_source_mode: str

    # Verified-common initial specific mechanical energy (E0, J/kg).
    initial_energy_jpkg: float


@dataclass(frozen=True)
class CommonRangeComparison:
    """Protocol C result: both realized states at the same downrange."""

    common_range_m: float
    qian_state: ComparisonState
    sanger_state: ComparisonState

    qian_arrival_time_s: float
    sanger_arrival_time_s: float

    time_saving_s: float
    delta_altitude_m: float
    delta_velocity_mps: float
    delta_specific_energy_jpkg: float

    qian_energy_loss_jpkg: float
    sanger_energy_loss_jpkg: float

    qian_mode: str
    sanger_mode: str
    qian_source_mode: str
    sanger_source_mode: str

    # Verified-common initial specific mechanical energy (E0, J/kg).
    initial_energy_jpkg: float

    # Root residuals of the two range inversions (E0 §12).
    qian_range_residual_m: float
    sanger_range_residual_m: float


def _common_initial_energy(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
) -> float:
    """Verify E0_Q == E0_S to numerical zero and return the common E0."""
    e0_q = qian.specific_energy_at_time(qian.initial_time_s)
    e0_s = sanger.specific_energy_at_time(sanger.initial_time_s)
    if abs(e0_q - e0_s) > INITIAL_ENERGY_ZERO_TOL_JPKG:
        raise RuntimeError(
            "Common initial mechanical energy violated: "
            f"|E0_Q - E0_S| = {abs(e0_q - e0_s):.6e} J/kg "
            f"> {INITIAL_ENERGY_ZERO_TOL_JPKG} J/kg."
        )
    return float(e0_q)


def _energy_loss(e0: float, state: ComparisonState) -> float:
    """``E0 - E_current`` -- never ``abs``, never clipped (E0 §25)."""
    return e0 - state.specific_mechanical_energy_jpkg


def _endpoint_identity_time(
    trajectory: ComparisonTrajectory,
    t_check: float,
    label: str,
) -> None:
    """Conditional structural assertion: a state evaluated at a limiting
    endpoint time must equal the exact terminal state.

    ``t_check`` is compared against the trajectory's terminal time; the
    assertion fires only when this side actually is the limiting
    endpoint (E0 §7, §14).
    """
    if abs(t_check - trajectory.terminal_time_s) <= _TIME_TOL_S:
        state = trajectory.state_at_time(t_check)
        if not np.allclose(state.state_raw, trajectory.terminal_state,
                           rtol=_STATE_RTOL, atol=_STATE_ATOL):
            raise RuntimeError(
                f"{label} endpoint identity violated at the common-time "
                f"checkpoint: state differs from the exact terminal state."
            )


def run_common_time_comparison(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
) -> CommonTimeComparison:
    """Protocol B (E0 §7-§8): compare at the same elapsed time.

    ``t_common = min(T_Q_RTI, T_S_SRTI)``, read from the real
    trajectories (never hard-coded).  Both states are evaluated
    continuously (E1 dense API); if a side is the limiting endpoint its
    state must reproduce the exact terminal state.
    """
    t_common = min(qian.terminal_time_s, sanger.terminal_time_s)

    qian_state = qian.state_at_time(t_common)
    sanger_state = sanger.state_at_time(t_common)

    # Conditional endpoint identity (either side may be limiting).
    _endpoint_identity_time(qian, t_common, "Qian")
    _endpoint_identity_time(sanger, t_common, "Sanger")

    e0 = _common_initial_energy(qian, sanger)

    return CommonTimeComparison(
        common_time_s=float(t_common),
        qian_state=qian_state,
        sanger_state=sanger_state,
        # E0 §18 sign conventions.
        delta_range_m=float(sanger_state.range_m - qian_state.range_m),
        delta_altitude_m=float(sanger_state.altitude_m - qian_state.altitude_m),
        delta_velocity_mps=float(
            sanger_state.velocity_mps - qian_state.velocity_mps
        ),
        delta_specific_energy_jpkg=float(
            sanger_state.specific_mechanical_energy_jpkg
            - qian_state.specific_mechanical_energy_jpkg
        ),
        qian_energy_loss_jpkg=_energy_loss(e0, qian_state),
        sanger_energy_loss_jpkg=_energy_loss(e0, sanger_state),
        qian_mode=qian_state.mode,
        sanger_mode=sanger_state.mode,
        qian_source_mode=qian_state.source_mode,
        sanger_source_mode=sanger_state.source_mode,
        initial_energy_jpkg=e0,
    )


def run_common_range_comparison(
    qian: ComparisonTrajectory,
    sanger: ComparisonTrajectory,
) -> CommonRangeComparison:
    """Protocol C (E0 §8): compare at the same downrange distance.

    ``R_common = min(R_Q_RTI, R_S_SRTI)``; the monotonicity prerequisite
    is re-checked (E0 §9, §11), the inversion goes through the E1
    ``first_time_at_range`` segment-aware root solver, and the root
    residuals are bounded by ``RANGE_RESIDUAL_TOL_M``.
    """
    r_common = min(
        qian.range_at_time(qian.terminal_time_s),
        sanger.range_at_time(sanger.terminal_time_s),
    )

    # E0 §9 / §11: common-range inversion requires strict monotonicity.
    qian_mono = qian.is_range_monotone()
    sanger_mono = sanger.is_range_monotone()
    if not (qian_mono.is_strictly_monotone
            and sanger_mono.is_strictly_monotone):
        raise RuntimeError(
            "Common-range comparison disabled: downrange monotonicity "
            f"prerequisite failed (Qian: {qian_mono.is_strictly_monotone}, "
            f"Sanger: {sanger_mono.is_strictly_monotone})."
        )

    t_q = qian.first_time_at_range(r_common)
    t_s = sanger.first_time_at_range(r_common)

    qian_state = qian.state_at_time(t_q)
    sanger_state = sanger.state_at_time(t_s)

    # Root residuals (E0 §12 / E1 §18 policy).
    qian_res = abs(qian_state.range_m - r_common)
    sanger_res = abs(sanger_state.range_m - r_common)
    if qian_res > RANGE_RESIDUAL_TOL_M or sanger_res > RANGE_RESIDUAL_TOL_M:
        raise RuntimeError(
            "Common-range root residual out of policy: "
            f"Qian {qian_res:.6e} m, Sanger {sanger_res:.6e} m "
            f"> {RANGE_RESIDUAL_TOL_M} m."
        )

    # Conditional endpoint identity (E0 §14): if R_common is a side's
    # terminal range, that side's arrival time and state must equal the
    # exact terminal ones.  Handled inside first_time_at_range as exact
    # boundary cases; re-verified here structurally.
    for trajectory, t_check, label in (
        (qian, t_q, "Qian"),
        (sanger, t_s, "Sanger"),
    ):
        if abs(t_check - trajectory.terminal_time_s) <= _TIME_TOL_S:
            state = trajectory.state_at_time(t_check)
            if not np.allclose(state.state_raw, trajectory.terminal_state,
                               rtol=_STATE_RTOL, atol=_STATE_ATOL):
                raise RuntimeError(
                    f"{label} endpoint identity violated at the "
                    "common-range checkpoint."
                )

    e0 = _common_initial_energy(qian, sanger)

    return CommonRangeComparison(
        common_range_m=float(r_common),
        qian_state=qian_state,
        sanger_state=sanger_state,
        qian_arrival_time_s=float(t_q),
        sanger_arrival_time_s=float(t_s),
        # E0 §18: positive -> Sanger reaches the common range earlier.
        time_saving_s=float(t_q - t_s),
        delta_altitude_m=float(sanger_state.altitude_m - qian_state.altitude_m),
        delta_velocity_mps=float(
            sanger_state.velocity_mps - qian_state.velocity_mps
        ),
        delta_specific_energy_jpkg=float(
            sanger_state.specific_mechanical_energy_jpkg
            - qian_state.specific_mechanical_energy_jpkg
        ),
        qian_energy_loss_jpkg=_energy_loss(e0, qian_state),
        sanger_energy_loss_jpkg=_energy_loss(e0, sanger_state),
        qian_mode=qian_state.mode,
        sanger_mode=sanger_state.mode,
        qian_source_mode=qian_state.source_mode,
        sanger_source_mode=sanger_state.source_mode,
        initial_energy_jpkg=e0,
        qian_range_residual_m=float(qian_res),
        sanger_range_residual_m=float(sanger_res),
    )
