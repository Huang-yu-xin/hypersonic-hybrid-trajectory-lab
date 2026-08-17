"""Phase-G0 state-scaling convention freeze (G0 §11 -- metadata only).

Purpose
-------
The raw dimensional STM ``Phi`` acts on ``x = [r, theta, v, gamma]`` with
incommensurate units and magnitudes (``r ~ 6.4e6 m``, ``theta ~ 0.5 rad``,
``v ~ 3e3 m/s``, ``gamma ~ 0.1 rad``).  A raw 2-norm / singular value /
condition number / FTLE computed on ``Phi`` would therefore depend on the
unit system.  G0 freezes the *convention*:

    tilde_Phi(T) = S^-1 * Phi(T) * S,   S = diag(s_r, s_theta, s_v, s_gamma)

and therefore the future eigenvalue-free predictability quantities
(``sigma_max``, ``condition number``, FTLE) are always computed on the
SCALED STM, never on the raw dimensional matrix.

This module is METADATA ONLY:

* three physically interpretable scale candidates (A/B/C) anchored to the
  FROZEN Phase-A..F baselines (no generic textbook numbers);
* canonical-scaling status flags;
* a small set of PURE protocol-level sanity checks over ``S^-1 Phi S``
  (identity invariance, spectrum invariance, singular-value
  non-invariance) that the G0 semantic tests exercise WITHOUT any
  trajectory / STM integration.

No canonical numeric scale is force-frozen without numerical evidence:
G0 marks the canonical scale preferences and defers the final numeric
selection to the G2/G5 scale-sensitivity audit (with the scale-sensitivity
protocol documented in ``docs/phase_g/predictability_protocol.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np

# Frozen baseline anchors used to DERIVE the scale candidates (Phase
# A-F frozen numbers, read from the frozen docs/regression snapshots;
# do not silently change these).
_R_E_M = 6_371_000.0           # earth radius (EnvironmentParams)
_H_ATM_M = 100_000.0           # atmosphere boundary / h0 (frozen)
_V0_MPS = 7_000.0              # initial speed (frozen baseline)
_GAMMA0_RAD = -5.0 * np.pi / 180.0  # initial flight-path angle (-5 deg)
# Phase-E baseline terminal anchors (qian_sanger_comparison_v1.json):
_V_RTI_MPS = 3192.5331828      # Qian @ RTI
_R_RTI_M = 3490.698336e3       # Qian @ RTI range
_SANGER_X1_EXIT_GAMMA_RAD = 0.02245911898378354  # Sanger cycle-1 exit gamma
# Phase-D Sanger baseline anchors:
_V_SRTI_MPS = 5482.9461135     # Sanger @ SRTI
_MAX_ALT_M = 130_352.1211817   # Sanger max altitude


# ---------------------------------------------------------------------------
# Canonical-scaling status flags (G0 §11)
# ---------------------------------------------------------------------------
SCALING_CONVENTION_DEFINED = "SCALING_CONVENTION_DEFINED"
CANONICAL_SCALE_NUMERIC_VALUES_PENDING_VALIDATION = (
    "CANONICAL_SCALE_NUMERIC_VALUES_PENDING_VALIDATION"
)


@dataclass(frozen=True)
class ScalingCandidate:
    """One physically interpretable scale set (G0 §11, "candidate family")."""

    key: str
    label: str
    scales: Mapping[str, float]      # {"r": .., "theta": .., "v": .., "gamma": ..}
    units: Mapping[str, str]
    physical_interpretation: str
    advantages: tuple[str, ...]
    limitations: tuple[str, ...]

    @property
    def matrix(self) -> np.ndarray:
        """Diagonal scaling matrix in frozen order ``[r, theta, v, gamma]``."""
        return np.diag(
            [self.scales[k] for k in ("r", "theta", "v", "gamma")]
        )


# ---------------------------------------------------------------------------
# Candidate A -- characteristic vehicle/trajectory scales (G0 §11.5)
# ---------------------------------------------------------------------------
CANDIDATE_A = ScalingCandidate(
    key="A",
    label="characteristic trajectory scales",
    scales={
        "r": _H_ATM_M,                      # flight-domain altitude extent
        "theta": 1.0,                       # radian
        "v": _V0_MPS,                       # initial speed
        "gamma": 0.1,                       # nominal FPA scale (|-5 deg|, RTI region)
    },
    units={"r": "m", "theta": "rad", "v": "m/s", "gamma": "rad"},
    physical_interpretation=(
        "Each state component is measured in units of a characteristic "
        "motion quantity of the FROZEN trajectories: the flight-domain "
        "altitude extent h_atm, one radian of ground-range angle, the "
        "initial speed v0, and a nominal flight-path-angle magnitude.  "
        "A unit perturbation therefore reads as 'one characteristic "
        "altitude / one radian / one v0 / one nominal FPA'."
    ),
    advantages=(
        "Directly derivable from frozen Phase A-F baselines (no arbitrary "
        "engineering tolerances); the state is O(1) at t0 by construction; "
        "independent of any specific terminal; transparent SI units for "
        "reporting.",
    ),
    limitations=(
        "Characteristic motion scales are not perturbation-precision "
        "statements; normalizing gamma by 0.1 rad is coarse for the "
        "small-gamma capture / SRTI neighborhood; 'one-unit' norms are "
        "meaningful only relative to these baselines.",
    ),
)


# ---------------------------------------------------------------------------
# Candidate B -- initial-condition perturbation tolerance scales (G0 §11.5)
# ---------------------------------------------------------------------------
CANDIDATE_B = ScalingCandidate(
    key="B",
    label="initial-condition perturbation tolerance scales",
    scales={
        "r": 1e2,                           # 100 m altitude/radius tolerance
        "theta": 1e-5,                      # ~64 m ground range at R_E
        "v": 1.0,                           # 1 m/s
        "gamma": 1e-4,                      # ~0.0057 deg
    },
    units={"r": "m", "theta": "rad", "v": "m/s", "gamma": "rad"},
    physical_interpretation=(
        "Each initial perturbation is delivered in units of a small, "
        "engineering-plausible precision cell: 100 m of altitude/radius, "
        "10 micro-radians of range angle, 1 m/s, and 1e-4 rad of "
        "flight-path angle.  Scaled STM entries then read as 'output "
        "displacement per tolerance-sized input cell', which matches the "
        "magnitudes used by the G2/G4 finite-perturbation validation."
    ),
    advantages=(
        "Directly interpretable in the language of initial-state delivery "
        "precision; aligns with the finite-perturbation validation "
        "magnitudes of the G2 protocol; makes the dominant direction "
        "physically meaningful (which input cell is amplified most).",
    ),
    limitations=(
        "The tolerance levels are a research-choice convention, not "
        "derived from the flight dynamics; exaggerates the weight of "
        "theta/gamma relative to r/v; candidate values must be re-stated "
        "together with their precision semantics.",
    ),
)


# ---------------------------------------------------------------------------
# Candidate C -- research-domain / terminal-geometry scales (G0 §11.5)
# ---------------------------------------------------------------------------
CANDIDATE_C = ScalingCandidate(
    key="C",
    label="research-domain / terminal-geometry scales",
    scales={
        "r": _H_ATM_M,                      # atmosphere boundary / research domain
        "theta": _R_RTI_M / _R_E_M,         # Qian baseline @ RTI range angle
        "v": _V0_MPS - _V_RTI_MPS,          # velocity retention range over research
        "gamma": _SANGER_X1_EXIT_GAMMA_RAD, # representative transverse exit FPA
    },
    units={"r": "m", "theta": "rad", "v": "m/s", "gamma": "rad"},
    physical_interpretation=(
        "The state is normalized by research-interval spans of the frozen "
        "baselines: the atmospheric altitude domain, the Qian baseline "
        "terminal range angle, the velocity retained over the research "
        "interval (v0 - v_RTI), and a representative transverse "
        "atmosphere-exit flight-path angle.  Scaled states are "
        "commensurable with the terminal observables used by "
        "event-conditioned predictability."
    ),
    advantages=(
        "Anchored to frozen research endpoints (Qian RTI range, Sanger "
        "transverse exit FPA); directly relevant to terminal and "
        "event-conditioned predictability; all values reconstructable "
        "from the Phase-E comparison snapshot.",
    ),
    limitations=(
        "Endpoint-relative (the theta/v anchors differ between Qian and "
        "Sanger research terminals); heavier bookkeeping; the gamma "
        "anchor represents one particular transverse event, not the "
        "global flight-path-angle range.",
    ),
)

SCALING_CANDIDATES: tuple[ScalingCandidate, ...] = (
    CANDIDATE_A,
    CANDIDATE_B,
    CANDIDATE_C,
)


# ---------------------------------------------------------------------------
# Canonical-scaling decision (G0 §11)
# ---------------------------------------------------------------------------
# The CONVENTION (form of S, scaled STM, all FTLE/singular-value work on
# the scaled matrix) is frozen.  The NUMERIC canonical choice is NOT
# force-frozen: G0 has no STM evidence to rank A/B/C fairly, so the
# numeric selection is deferred to the G2/G5 scale-sensitivity audit.
PREFERRED_CANONICAL_CANDIDATE = "A"

CANONICAL_SCALING_STATUS = SCALING_CONVENTION_DEFINED
CANONICAL_SCALE_STATUS = SCALING_CONVENTION_DEFINED
CANONICAL_SCALE_NUMERIC_STATUS = (
    CANONICAL_SCALE_NUMERIC_VALUES_PENDING_VALIDATION
)


def canonical_candidate() -> ScalingCandidate:
    """The preferred canonical candidate (A by default; pending validation)."""
    for cand in SCALING_CANDIDATES:
        if cand.key == PREFERRED_CANONICAL_CANDIDATE:
            return cand
    raise KeyError(PREFERRED_CANONICAL_CANDIDATE)


# ---------------------------------------------------------------------------
# Scaled STM definition and PURE protocol-level sanity checks (G0 §11, §13).
# These helpers implement the frozen DEFINITIONS only.  They take matrices
# as inputs and never integrate any trajectory -- G1+ production modules
# (stm.py / ftle.py) remain unimplemented.
# ---------------------------------------------------------------------------
def scaled_stm(phi: np.ndarray, scales: Mapping[str, float]) -> np.ndarray:
    """``tilde_Phi = S^-1 Phi S`` with ``S = diag(scales)`` (frozen, G0 §11)."""
    phi = np.asarray(phi, dtype=float)
    s = np.diag([float(scales[k]) for k in ("r", "theta", "v", "gamma")])
    return np.linalg.solve(s, phi @ s)


def identity_scaled_stm(scales: Mapping[str, float]) -> np.ndarray:
    """Sanity: ``Phi = I`` yields ``tilde_Phi = I`` for ANY positive S."""
    return scaled_stm(np.eye(4), scales)


def spectrum_invariance(phi: np.ndarray, scales: Mapping[str, float]) -> bool:
    """``S^-1 Phi S`` is a similarity transform: eigenvalues are invariant.

    This documents why the raw spectral radius is scale-free while the
    SINGULAR VALUES (and hence 2-norm based FTLE) are not.
    """
    phi = np.asarray(phi, dtype=float)
    out = scaled_stm(phi, scales)
    return np.allclose(
        np.sort_complex(np.linalg.eigvals(out)),
        np.sort_complex(np.linalg.eigvals(phi)),
        atol=1e-10,
    )


def singular_value_non_invariance(
    phi: np.ndarray, scales_a: Mapping[str, float], scales_b: Mapping[str, float]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(sigma_raw, sigma_A, sigma_B)`` for documentation purposes.

    G0 protocol sanity: singular values of a dimensional STM are NOT
    invariant under re-scaling, which is exactly why all Phase-G
    predictability quantities require the frozen scaled convention.
    """
    phi = np.asarray(phi, dtype=float)
    raw = np.linalg.svd(phi, compute_uv=False)
    sa = np.linalg.svd(scaled_stm(phi, scales_a), compute_uv=False)
    sb = np.linalg.svd(scaled_stm(phi, scales_b), compute_uv=False)
    return raw, sa, sb


def finite_time_lyapunov_exponent(
    scaled_phi_T: np.ndarray, horizon_s: float
) -> float:
    """Frozen FTLE definition (G0 §13): ``lambda_max = ln(sigma_max)/T``.

    ``scaled_phi_T`` must ALREADY be the scaled STM at the fixed time
    horizon ``T`` (the caller applies ``scaled_stm``).  G0 only freezes
    the definition; no production FTLE is computed anywhere in G0.
    """
    scaled_phi_T = np.asarray(scaled_phi_T, dtype=float)
    if horizon_s <= 0.0:
        raise ValueError("horizon_s must be positive for the FTLE convention.")
    sigma_max = np.linalg.svd(scaled_phi_T, compute_uv=False)[0]
    return float(np.log(sigma_max) / horizon_s)