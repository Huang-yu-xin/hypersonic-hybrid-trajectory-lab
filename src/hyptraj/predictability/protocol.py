"""Phase-G0 predictability protocol freeze (G0 -- metadata / convention).

THIS IS THE MACHINE-READABLE SINGLE SOURCE OF TRUTH for the Phase-G
predictability protocol (``docs/phase_g/predictability_protocol.md`` is the
human-readable companion).  G0 freezes MATHEMATICAL SEMANTICS and
CONVENTIONS ONLY:

* frozen state ordering and units;
* initial-state-only perturbation scope;
* STM / continuous-Jacobian / saltation / event-time conventions;
* reset convention;
* fixed-time vs event-conditioned predictability semantics;
* FTLE definition (deferred to ``predictability/scaling.py``);
* grazing / transversality policy (no numeric threshold invented);
* error taxonomy and validation categories;
* representative trajectory set (baselines, N0-N5 deep interiors, grazing
  anchors reserved for G6);
* trajectory production / reference solver policy;
* claim boundaries and status flags.

Hard boundaries honoured by this module (G0 §0): NO continuous Jacobian,
NO variational integration, NO STM propagation, NO saltation computation,
NO FTLE production, NO Monte Carlo, NO optimization, NO gamma0-K domain
re-scan.  The only arithmetic below implements the frozen CONVENTION
formulas so that G1+ code and the G0 semantic tests reason about the
documented convention instead of drifting to local notation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

import numpy as np

from hyptraj.predictability.event_metadata import (
    EVENT_TAXONOMY,
    STATE_ORDER,
    EventClassification,
    all_taxonomy_rows,
)
from hyptraj.predictability.scaling import (
    CANONICAL_SCALE_NUMERIC_STATUS,
    CANONICAL_SCALING_STATUS,
    SCALING_CANDIDATES,
)

# ---------------------------------------------------------------------------
# Status flags (G0 §0, §24)
# ---------------------------------------------------------------------------
PHASE_G0_DONE = True
G1_STARTED = False
CONTINUOUS_JACOBIAN_IMPLEMENTED = False
VARIATIONAL_SOLVER_IMPLEMENTED = False
HYBRID_STM_IMPLEMENTED = False
SALTATION_IMPLEMENTED = False
PRODUCTION_FTLE_COMPUTED = False
MONTE_CARLO_PERFORMED = False
OPTIMIZATION_PERFORMED = False

# ---------------------------------------------------------------------------
# Frozen state convention (G0 §4)
# ---------------------------------------------------------------------------
STATE_UNITS: Mapping[str, str] = {
    "r": "m",
    "theta": "rad",
    "v": "m/s",
    "gamma": "rad",
}
STATE_IDX_R, STATE_IDX_THETA, STATE_IDX_V, STATE_IDX_GAMMA = 0, 1, 2, 3

# h = r - R_E (altitude from the geocentric radius; R_E = 6_371_000 m).
# Any Phase-G mathematical notation that re-orders to [h, v, gamma, theta]
# is strictly a DISPLAY re-ordering and must be declared as such.
DISPLAY_REORDERING_H_V_GAMMA_THETA_NOT_ALLOWED_AS_IMPL = True

# STM convention: rows = output state component, columns = initial
# perturbation component:
#     Phi_ij(t, t0) = d x_i(t) / d x_0,j,   Phi(t0, t0) = I.
STM_ROW_OUTPUT, STM_COL_INITIAL = "output-component", "initial-perturbation"
STM_INITIAL_VALUE = "I"


# ---------------------------------------------------------------------------
# Perturbation scope (G0 §5)
# ---------------------------------------------------------------------------
PERTURBATION_SCOPE = "initial-state-only"
PERTURBATION_VECTOR = ["delta r_0", "delta theta_0", "delta v_0", "delta gamma_0"]

# Phase-G distinguishes the Phase-F PARAMETER study (d y / d gamma0 at
# fixed topology) from the Phase-G STATE-component perturbation
# (partial x(t) / partial gamma_initial column of the STM).  gamma0 is a
# controlled sweep parameter in Phase F; delta gamma_0 enters the STM as a
# STATE-component initial perturbation in Phase G.
PHASE_F_PARAMETER_JACOBIAN_DISTINCT = True

# ---------------------------------------------------------------------------
# Reset convention (G0 §7)
# ---------------------------------------------------------------------------
RESET_CONVENTION = "R(x) = x,  DR = I  (state continuous at every Phase-G normal true mode switch)"
VECTOR_FIELD_CONTINUITY_DISTINCT_FROM_STATE_CONTINUITY = True

# ---------------------------------------------------------------------------
# Saltation / event-time conventions (G0 §8, §9) -- pure convention helpers
# ---------------------------------------------------------------------------
def saltation_identity_reset(
    f_minus: np.ndarray, f_plus: np.ndarray, normal: np.ndarray
) -> np.ndarray:
    """Frozen saltation matrix for the identity-reset case (G0 §8 boxed form).

    For an autonomous event ``g(x) = 0`` with ``x+ = R(x-)``, ``DR = I``:

        Xi = I + (f^+ - f^-) n^T / (n^T f^-),

    with ``f^-`` = vector field immediately before the event, ``f^+`` =
    vector field immediately after, and ``n = grad g(x^-)`` evaluated on
    the PRE-EVENT side.  The formula is one convention-level arithmetic
    expression; no trajectory / STM is involved here.
    """
    f_minus = np.asarray(f_minus, dtype=float)
    f_plus = np.asarray(f_plus, dtype=float)
    normal = np.asarray(normal, dtype=float)
    denom = float(normal @ f_minus)
    eye = np.eye(f_minus.size)
    if abs(denom) < 1e-300:
        # Convention guard: the formula is undefined at exact grazing.
        raise FloatingPointError(
            "Saltation denominator n^T f^- ~ 0 (grazing / nontransverse); "
            "standard transverse linearization is undefined here (G0 §10)."
        )
    return eye + np.outer(f_plus - f_minus, normal) / denom


def generic_saltation(
    dr: np.ndarray, f_minus: np.ndarray, f_plus: np.ndarray, normal: np.ndarray
) -> np.ndarray:
    """Frozen general saltation convention: ``DR + (f^+ - DR f^-) n^T/(n^T f^-)``.

    With ``DR = I`` this reduces exactly to :func:`saltation_identity_reset`
    (verified by the G0 semantic tests).
    """
    dr = np.asarray(dr, dtype=float)
    f_minus = np.asarray(f_minus, dtype=float)
    f_plus = np.asarray(f_plus, dtype=float)
    normal = np.asarray(normal, dtype=float)
    denom = float(normal @ f_minus)
    if abs(denom) < 1e-300:
        raise FloatingPointError(
            "Saltation denominator n^T f^- ~ 0 (grazing / nontransverse)."
        )
    return dr + np.outer(f_plus - dr @ f_minus, normal) / denom


def event_time_first_order(
    dx_minus: np.ndarray, f_minus: np.ndarray, normal: np.ndarray
) -> float:
    """Frozen first-order event-time perturbation (G0 §9):

        delta t_e = - (n^T delta x^-) / (n^T f^-)

    where ``delta x^-`` is the pre-event first-order perturbation at the
    NOMINAL event time.  The sign follows from linearizing
    ``g(x^- + f^- delta t_e + delta x^-) = 0`` to first order.  Pure
    convention formula (no STM).
    """
    dx_minus = np.asarray(dx_minus, dtype=float)
    f_minus = np.asarray(f_minus, dtype=float)
    normal = np.asarray(normal, dtype=float)
    denom = float(normal @ f_minus)
    if abs(denom) < 1e-300:
        raise FloatingPointError(
            "Event-time denominator n^T f^- ~ 0 (grazing / nontransverse)."
        )
    return -float(normal @ dx_minus) / denom


# ---------------------------------------------------------------------------
# Grazing / transversality policy (G0 §10)
# ---------------------------------------------------------------------------
class GrazingRegime(Enum):
    """Frozen grazing classification vocabulary (G0 §10).

    * ``TRANSVERSE``            -- ``|n^T f^-|`` sufficiently large; the
      standard transverse saltation / event-time linearization applies.
    * ``GRAZING_ADJACENT``      -- ``|n^T f^-|`` small; the standard
      transverse linearization is ill-conditioned and its first-order
      validity domain shrinks; this is a loss-of-transversality /
      linearization-conditioning statement, NOT a claim of infinite
      physical sensitivity.
    * ``GRAZING_NONTRANSVERSE`` -- ``n^T f^- -> 0`` (limiting geometry
      ``G_h = 0`` and ``gamma = 0``); standard transverse formulas break
      down.  G6 owns this regime.  No "FTLE = infinity" / "chaos" claim.

    No numeric threshold is force-frozen at G0: the classification logic
    and the diagnostic quantity are frozen; the numerical threshold is
    deferred to the G6 numerical convergence study.
    """

    TRANSVERSE = "TRANSVERSE"
    GRAZING_ADJACENT = "GRAZING_ADJACENT"
    GRAZING_NONTRANSVERSE = "GRAZING_NONTRANSVERSE"


def interface_crossing_rate(state: np.ndarray) -> float:
    """Diagnostic transversality quantity for the atmosphere interface.

    For ``G_h = h - h_atm`` with ``n = [1,0,0,0]^T``:
    ``n^T f^- = dG_h/dt = v sin(gamma)``.  Frozen diagnostic primitive;
    a numerical threshold for the grazing classification is intentionally
    NOT hard-coded (G0 §10, deferred to G6).
    """
    return float(state[2] * np.sin(state[3]))


def classify_transversality(
    crossing_rate_abs: float, threshold: float | None = None
) -> GrazingRegime:
    """Classification logic frozen at G0; numeric threshold deferred to G6.

    ``crossing_rate_abs = |n^T f^-|``.  G0 deliberately freezes no numeric
    threshold, so calling without an explicit ``threshold`` raises
    ``TypeError`` (the threshold is an output of the G6 numerical
    convergence study, never a G0-invented constant).

    With an explicit threshold the rule is:

    * ``crossing_rate_abs >= threshold``            -> TRANSVERSE;
    * ``0 < crossing_rate_abs < threshold``         -> GRAZING_ADJACENT;
    * ``crossing_rate_abs == 0`` (exact)            -> GRAZING_NONTRANSVERSE.
    """
    if threshold is None:
        raise TypeError(
            "G0 freezes the grazing classification logic but NOT the "
            "numeric threshold.  Pass an explicit threshold (deferred to G6)."
        )
    if crossing_rate_abs < 0.0:
        raise ValueError("crossing_rate_abs must be non-negative.")
    if crossing_rate_abs == 0.0:
        return GrazingRegime.GRAZING_NONTRANSVERSE
    if crossing_rate_abs < threshold:
        return GrazingRegime.GRAZING_ADJACENT
    return GrazingRegime.TRANSVERSE


# ---------------------------------------------------------------------------
# Error taxonomy and validation categories (G0 §17, §18)
# ---------------------------------------------------------------------------
class ValidationErrorCategory(Enum):
    """Frozen Phase-G error taxonomy.  Reports MUST assign one category per
    mismatch; "STM error" alone is never an acceptable catch-all."""

    PHYSICS_SEMANTICS_ERROR = "PHYSICS_SEMANTICS_ERROR"
    NUMERICAL_ERROR = "NUMERICAL_ERROR"
    TOPOLOGY_CHANGE = "TOPOLOGY_CHANGE"
    EVENT_ORDER_CHANGE = "EVENT_ORDER_CHANGE"
    GRAZING_CROSSING = "GRAZING_CROSSING"
    LINEARIZATION_BREAKDOWN = "LINEARIZATION_BREAKDOWN"
    INVALID_ACCEPTANCE_DOMAIN = "INVALID_ACCEPTANCE_DOMAIN"


class TopologyGateResult(Enum):
    """Finite-perturbation topology gate (G0 §17).

    Only ``TOPOLOGY_PRESERVED`` perturbations may feed ordinary first-order
    hybrid STM acceptance; anything else invalidates the comparison
    (reported under its own category, never as STM error).
    """

    TOPOLOGY_PRESERVED = "TOPOLOGY_PRESERVED"
    TOPOLOGY_CHANGED = "TOPOLOGY_CHANGED"
    EVENT_ORDER_CHANGED = "EVENT_ORDER_CHANGED"
    GRAZING_CROSSED = "GRAZING_CROSSED"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


# ---------------------------------------------------------------------------
# Representative trajectories (G0 §15 -- FROZEN set, no re-selection)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RepresentativeCase:
    """One Phase-G representative trajectory (frozen metadata)."""

    key: str
    model: str
    gamma0_deg: float
    K: float
    expected_regime: str
    purpose: str


REPRESENTATIVE_CASES: tuple[RepresentativeCase, ...] = (
    RepresentativeCase(
        key="qian_baseline", model="Qian", gamma0_deg=-5.0, K=3.0,
        expected_regime="QIAN_RTI",
        purpose="Phase-G Qian fixed-time and RTI terminal predictability baseline",
    ),
    RepresentativeCase(
        key="sanger_baseline", model="Sanger", gamma0_deg=-5.0, K=3.0,
        expected_regime="SRTI_N2",
        purpose="Phase-G Sanger fixed-time and SRTI terminal predictability baseline",
    ),
    RepresentativeCase(
        key="n0_deep", model="Sanger", gamma0_deg=-1.25, K=1.125,
        expected_regime="SRTI_N0",
        purpose="F4 reference-certified deep fixed-topology interior (N0)",
    ),
    RepresentativeCase(
        key="n1_deep", model="Sanger", gamma0_deg=-4.5, K=2.375,
        expected_regime="SRTI_N1",
        purpose="F4 reference-certified deep fixed-topology interior (N1)",
    ),
    RepresentativeCase(
        key="n2_deep", model="Sanger", gamma0_deg=-8.75, K=2.5,
        expected_regime="SRTI_N2",
        purpose="F4 reference-certified deep fixed-topology interior (N2 deep)",
    ),
    RepresentativeCase(
        key="n3_deep", model="Sanger", gamma0_deg=-8.25, K=3.5,
        expected_regime="SRTI_N3",
        purpose="F4 reference-certified deep fixed-topology interior (N3)",
    ),
    RepresentativeCase(
        key="n4_deep", model="Sanger", gamma0_deg=-7.0, K=4.875,
        expected_regime="SRTI_N4",
        purpose="F4 reference-certified deep fixed-topology interior (N4)",
    ),
    RepresentativeCase(
        key="n5_deep", model="Sanger", gamma0_deg=-8.75, K=4.875,
        expected_regime="SRTI_N5",
        purpose="F4 reference-certified deep fixed-topology interior (N5)",
    ),
)
# Grazing anchors are RESERVED for G6 and must never enter normal G1-G5
# acceptance.  The 10 dual-reference extremal anchors (B0..B4 N-side /
# N+1-side) are the Phase-F regression snapshot values.
GRAZING_ANCHOR_COUNT = 10
GRAZING_ANCHORS_G6_RESERVED = True
GRAZING_ANCHOR_BRANCHES = ("B0", "B1", "B2", "B3", "B4")

# The 10 anchor coordinates read from the FROZEN regression snapshot
# (tests/data/phase_f_gamma_k_sensitivity_v1.json) -- the G0 tests verify
# these against the snapshot instead of re-deriving them.
GRAZING_ANCHOR_PARAMETERS = (
    # branch, side, (gamma0_deg, K)
    ("B0", "N_side", (-2.046875, 3.984375)),
    ("B0", "N1_side", (-1.7421875, 4.875)),
    ("B1", "N_side", (-3.2421875, 4.1953125)),
    ("B1", "N1_side", (-7.296875, 2.234375)),
    ("B2", "N_side", (-5.7265625, 3.703125)),
    ("B2", "N1_side", (-4.03125, 4.82421875)),
    ("B3", "N_side", (-6.125, 4.57421875)),
    ("B3", "N1_side", (-8.0546875, 3.98046875)),
    ("B4", "N_side", (-8.875, 4.69140625)),
    ("B4", "N1_side", (-7.9296875, 4.8984375)),
)

# ---------------------------------------------------------------------------
# Numerical reference policy (G0 §19)
# ---------------------------------------------------------------------------
# Trajectory production remains the Phase-C FROZEN configuration.
PRODUCTION_SOLVER_POLICY = {
    "method": "DOP853",
    "rtol": 1e-9,
    "atol": [1e-4, 1e-11, 1e-7, 1e-11],
    "max_step_s": 20.0,
    "dense_output": True,
    "status": "frozen (Phase C) -- trajectory baseline ONLY",
}
# Phase-G variational numerics are DEFERRED; the strict-reference config
# already frozen in the repo (comparison_validation.REFERENCE_SOLVER_CONFIG
# / REFERENCE_05_SOLVER_CONFIG) is the planned G2/G5 companion policy.
REFERENCE_SOLVER_POLICY = {
    "method": "DOP853",
    "rtol": 1e-12,
    "atol": [1e-7, 1e-14, 1e-10, 1e-14],
    "max_step_s": 0.1,
    "companion_max_step_s": 0.05,
    "status": "deferred -- independent Phase-G variational convergence audit required",
}

# ---------------------------------------------------------------------------
# Claim boundaries (G0 §23)
# ---------------------------------------------------------------------------
FORBIDDEN_CLAIMS = (
    "raw dimensional STM norm = objective predictability",
    "large Xi near grazing = physical infinity",
    "grazing = chaos",
    "larger FTLE always means worse trajectory",
    "Sanger RTI/SRTI native endpoint directly comparable to Qian",
    "diagnostic gamma crossing = hybrid switch",
    "all nonlinear mismatch = STM failure",
)
SCOPE_STATEMENT = (
    "Phase G studies finite-time local predictability "
    "(fixed-time and event-conditioned), NOT asymptotic chaos analysis, "
    "NOT global stability proofs, NOT certified flight-envelope "
    "robustness, NOT probabilistic uncertainty, NOT optimization."
)

# ---------------------------------------------------------------------------
# Machine-readable protocol payload (G0 §21)
# ---------------------------------------------------------------------------
def machine_readable_protocol() -> dict:
    """Single JSON-able protocol snapshot (G0 §21 acceptance surface)."""
    return {
        "protocol_version": "phase-g-predictability-protocol-v1",
        "g0_status": {
            "g0_complete": PHASE_G0_DONE,
            "g1_started": G1_STARTED,
            "continuous_jacobian_implemented": CONTINUOUS_JACOBIAN_IMPLEMENTED,
            "variational_solver_implemented": VARIATIONAL_SOLVER_IMPLEMENTED,
            "hybrid_stm_implemented": HYBRID_STM_IMPLEMENTED,
            "saltation_implemented": SALTATION_IMPLEMENTED,
            "production_ftle_computed": PRODUCTION_FTLE_COMPUTED,
            "monte_carlo_performed": MONTE_CARLO_PERFORMED,
            "optimization_performed": OPTIMIZATION_PERFORMED,
        },
        "state_order": list(STATE_ORDER),
        "state_units": dict(STATE_UNITS),
        "stm_convention": {
            "rows": STM_ROW_OUTPUT,
            "columns": STM_COL_INITIAL,
            "initial_value": STM_INITIAL_VALUE,
        },
        "perturbation_scope": PERTURBATION_SCOPE,
        "perturbation_vector": list(PERTURBATION_VECTOR),
        "phase_f_parameter_jacobian_distinct": (
            PHASE_F_PARAMETER_JACOBIAN_DISTINCT
        ),
        "reset_convention": RESET_CONVENTION,
        "saltation_convention": {
            "general": "DR + (f^+ - DR f^-) n^T / (n^T f^-)",
            "identity_reset": "I + (f^+ - f^-) n^T / (n^T f^-)",
            "notes": [
                "f_minus = vector field immediately before the event",
                "f_plus  = vector field immediately after the event",
                "n       = event-surface normal on the pre-event side",
            ],
        },
        "event_time_convention": "delta t_e = - (n^T delta x^-) / (n^T f^-)",
        "predictability_questions": {
            "fixed_time": (
                "compare x(T) for identical elapsed time via tilde_Phi(T); "
                "sigma_max / condition / singular vectors / FTLE"
            ),
            "event_conditioned": (
                "terminal state + event-time sensitivity (Qian@RTI, "
                "Sanger@SRTI); native RTI/SRTI amplification is descriptive"
            ),
        },
        "ftle_definition": (
            "lambda_max(T) = ln(sigma_max(S^-1 Phi(T) S)) / T "
            "(scaled STM only; no raw dimensional claim)"
        ),
        "scaling_status": {
            "convention_status": CANONICAL_SCALING_STATUS,
            "numeric_values_status": CANONICAL_SCALE_NUMERIC_STATUS,
            "candidates": [c.key for c in SCALING_CANDIDATES],
        },
        "grazing_policy": {
            "diagnostic": "n^T f^- = dh/dt = v sin(gamma)",
            "regimes": [r.value for r in GrazingRegime],
            "threshold_status": "DEFERRED to G6 numerical convergence study",
        },
        "event_taxonomy": list(all_taxonomy_rows()),
        "validation_categories": [c.value for c in ValidationErrorCategory],
        "topology_gate": [g.value for g in TopologyGateResult],
        "representative_cases": [
            {
                "key": c.key,
                "model": c.model,
                "gamma0_deg": c.gamma0_deg,
                "K": c.K,
                "expected_regime": c.expected_regime,
                "purpose": c.purpose,
            }
            for c in REPRESENTATIVE_CASES
        ],
        "grazing_anchors": {
            "count": GRAZING_ANCHOR_COUNT,
            "g6_reserved": GRAZING_ANCHORS_G6_RESERVED,
            "branches": list(GRAZING_ANCHOR_BRANCHES),
            "parameters": [
                {"branch": b, "side": s, "parameter": list(p)}
                for b, s, p in GRAZING_ANCHOR_PARAMETERS
            ],
        },
        "reference_solver_policy": {
            "production": PRODUCTION_SOLVER_POLICY,
            "phase_g_variational": REFERENCE_SOLVER_POLICY,
        },
        "forbidden_claims": list(FORBIDDEN_CLAIMS),
        "scope_statement": SCOPE_STATEMENT,
        "event_taxonomy_count": len(EVENT_TAXONOMY),
    }