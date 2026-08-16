"""Phase-F fixed-regime local sensitivity / FD convergence (F4).

F4 — Fixed-Regime Local Sensitivity and Finite-Difference Convergence
(docs/phase_f/f4_fd_convergence.md).

Ordinary parameter derivatives are defined ONLY inside a fixed exact
topology interior:

* central difference ``D_gamma(h) = [y(g+h) - y(g-h)] / (2 h_rad)`` with
  ``h_rad = h_deg * pi / 180`` (canonical stored unit: per radian;
  per-degree version reported explicitly);
* ``D_K(h) = [y(K+h) - y(K-h)] / (2h)`` (per unit K);
* stencil eligibility requires the F3 boundary-exclusion geometry gate
  (segment-vs-rectangle intersection, NOT only endpoint labels), the
  exact-topology gate, guardrail containment, and the exclusion of
  grazing / recovered / reference-extremal points;
* this is a parameter-output Jacobian
  ``J = d y_terminal / d(gamma0, K)`` -- NOT an STM, NOT a variational
  matrix, NOT a saltation matrix;
* skip_count is a discrete topology label and is NEVER differentiated.

Frozen constraints (F4): no physics duplication (point execution reuses
the F2/F2.1 executor), no Phase-E B/C/D surfaces, no optimization, no
STM/saltation/FTLE, no mixed-unit global error, no normalized composite
sensitivity, no elasticity.
"""

from dataclasses import dataclass

import numpy as np

from hyptraj.analysis.sensitivity_grid import (
    GAMMA_GUARDRAIL,
    K_GUARDRAIL,
    cache_key,
)
from hyptraj.analysis.sensitivity_pilot import ParameterPoint

# ---------------------------------------------------------------------------
# Primary output vectors (F4 §6) -- no skip_count, no max-based outputs.
# ---------------------------------------------------------------------------
QIAN_OUTPUTS = (
    "qian_rti_time_s",
    "qian_rti_range_m",
    "qian_rti_altitude_m",
    "qian_rti_velocity_mps",
    "qian_energy_loss_jpkg",
)

SANGER_OUTPUTS = (
    "sanger_srti_time_s",
    "sanger_srti_range_m",
    "sanger_srti_altitude_m",
    "sanger_srti_velocity_mps",
    "sanger_energy_loss_jpkg",
    "sanger_atm_duration_s",
    "sanger_vac_duration_s",
)

QIAN_JACOBIAN_SHAPE = (5, 2)
SANGER_JACOBIAN_SHAPE = (7, 2)


def qian_output_vector(qian_row: dict) -> list[float] | None:
    """Primary Qian output vector (RTI semantics); None if not a valid RTI."""
    if qian_row.get("terminal_kind") != "RTI":
        return None
    return [
        qian_row["terminal_time_s"],
        qian_row["terminal_range_m"],
        qian_row["terminal_altitude_m"],
        qian_row["terminal_velocity_mps"],
        qian_row["energy_loss_jpkg"],
    ]


def sanger_output_vector(sanger_row: dict) -> list[float] | None:
    """Primary Sanger output vector (SRTI semantics); None if not SRTI."""
    if sanger_row.get("terminal_kind") != "srti":
        return None
    return [
        sanger_row["terminal_time_s"],
        sanger_row["terminal_range_m"],
        sanger_row["terminal_altitude_m"],
        sanger_row["terminal_velocity_mps"],
        sanger_row["energy_loss_jpkg"],
        sanger_row["ATM_duration_s"],
        sanger_row["VAC_duration_s"],
    ]


# ---------------------------------------------------------------------------
# Candidate FD steps (F4 §13)
# ---------------------------------------------------------------------------
GAMMA_STEPS_DEG = (0.100000, 0.050000, 0.025000, 0.012500)
GAMMA_STEPS_DEG_EXTRA = (0.006250,)
K_STEPS = (0.050000, 0.025000, 0.012500, 0.006250)
K_STEPS_EXTRA = (0.003125,)


# ---------------------------------------------------------------------------
# Stencil geometry: segment-vs-rectangle intersection (F4 §10–§11)
# ---------------------------------------------------------------------------
def segment_intersects_rectangle(
    p0: tuple[float, float],
    p1: tuple[float, float],
    rect: dict,
) -> bool:
    """True when the parameter-space segment [p0, p1] touches the box.

    ``p0/p1 = (gamma0_deg, K)``; ``rect`` holds gamma_min/gamma_max/K_min/
    K_max.  The check is closed (endpoints on the boundary count as
    intersection), so a stencil whose interval crosses a narrow box and
    returns to the same label is rejected (F4 §11).
    """
    g0, k0 = p0
    g1, k1 = p1
    g_min, g_max = rect["gamma_min"], rect["gamma_max"]
    k_min, k_max = rect["K_min"], rect["K_max"]

    # Trivial acceptances.
    if (g_min <= g0 <= g_max and k_min <= k0 <= k_max):
        return True
    if (g_min <= g1 <= g_max and k_min <= k1 <= k_max):
        return True

    dg = g1 - g0
    dk = k1 - k0

    def _cross(g, k):
        # Sign of point relative to the directed segment (clockwise +).
        return dg * (k - k0) - dk * (g - g0)

    corners = [(g_min, k_min), (g_max, k_min),
               (g_min, k_max), (g_max, k_max)]
    # Segment crosses the rectangle iff the four corners are not all on
    # the same side of the line AND the segment's bounding box overlaps
    # the rectangle's bounding box.
    signs = [_cross(g, k) for g, k in corners]
    all_same_side = (all(s >= 0 for s in signs) or all(s <= 0 for s in signs))
    bbox_overlap = (
        min(g0, g1) <= g_max and max(g0, g1) >= g_min
        and min(k0, k1) <= k_max and max(k0, k1) >= k_min
    )
    if all_same_side:
        return False
    return bbox_overlap


def stencil_intersects_exclusion(
    center: tuple[float, float],
    plus: tuple[float, float],
    minus: tuple[float, float],
    exclusion_cells: list[dict],
) -> bool:
    """True when either half-stencil segment crosses an exclusion box."""
    for cell in exclusion_cells:
        rect = cell.get("rectangle", cell)
        if segment_intersects_rectangle(center, plus, rect):
            return True
        if segment_intersects_rectangle(center, minus, rect):
            return True
    return False


# ---------------------------------------------------------------------------
# Stencil eligibility (F4 §10, §12)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StencilEligibility:
    eligible: bool
    reasons: tuple[str, ...]


def _topology_key(row: dict, model: str) -> str:
    if model == "qian":
        return row["qian"]["exact_topology_signature"]
    return row["sanger"]["exact_topology_signature"]


def _recovered_flag(row: dict, model: str) -> bool:
    if model == "sanger":
        return row["sanger"].get("recovered_exit_count", 0) > 0
    return False


def evaluate_stencil(
    center_rec: dict,
    plus_rec: dict,
    minus_rec: dict,
    center: tuple[float, float],
    plus: tuple[float, float],
    minus: tuple[float, float],
    exclusion_cells: list[dict],
    model: str,
) -> StencilEligibility:
    """Full F4 stencil gate (guardrail + geometry + topology + recovery).

    ``model`` = "qian" | "sanger": the topology / recovery checks are
    model-specific; the geometry gate (F3 exclusion boxes) applies to
    both but is driven by the Sanger boundaries (Qian is uniform over the
    sampled domain, so its geometry gate is trivially satisfied).
    """
    reasons: list[str] = []

    # A. guardrails.
    for label, p in (("minus", minus), ("center", center), ("plus", plus)):
        if not (
            GAMMA_GUARDRAIL[0] - 1e-12 <= p[0] <= GAMMA_GUARDRAIL[1] + 1e-12
            and K_GUARDRAIL[0] - 1e-12 <= p[1] <= K_GUARDRAIL[1] + 1e-12
        ):
            reasons.append(f"OUTSIDE_DOMAIN:{label}")

    # B. segment-vs-exclusion geometry (F4 §11).
    if stencil_intersects_exclusion(center, plus, minus, exclusion_cells):
        reasons.append("BOUNDARY_INTERSECTION")

    # C. exact topology identity.
    keys = {
        _topology_key(center_rec, model),
        _topology_key(plus_rec, model),
        _topology_key(minus_rec, model),
    }
    if None in keys or len(keys) > 1:
        reasons.append("TOPOLOGY_CHANGE")

    # D. recovered / grazing exclusion (F4 §30).
    for label, rec in (("minus", minus_rec), ("center", center_rec),
                       ("plus", plus_rec)):
        row = rec[model]
        if row.get("event_resolution") in (
            "DENSE_RECOVERED", "GRAZING_OR_UNRESOLVED",
            "GRAZING_BOUNDARY", "REFERENCE_CONFIRMED",
        ):
            reasons.append(f"RECOVERED_EVENT:{label}")
        if _recovered_flag(rec, model):
            reasons.append(f"RECOVERED_EVENT:{label}")

    # E. valid physical terminal.
    for label, rec in (("minus", minus_rec), ("center", center_rec),
                       ("plus", plus_rec)):
        kind = rec[model].get("terminal_kind")
        if model == "qian" and kind != "RTI":
            reasons.append(f"INVALID_NEIGHBOR:{label}")
        if model == "sanger" and kind != "srti":
            reasons.append(f"INVALID_NEIGHBOR:{label}")

    if reasons:
        return StencilEligibility(eligible=False, reasons=tuple(reasons))
    return StencilEligibility(eligible=True, reasons=())


# ---------------------------------------------------------------------------
# Central differences (F4 §4)
# ---------------------------------------------------------------------------
def central_difference_gamma(
    y_plus: float, y_minus: float, h_deg: float
) -> float:
    """Per-radian central difference for gamma0."""
    h_rad = h_deg * np.pi / 180.0
    return (y_plus - y_minus) / (2.0 * h_rad)


def central_difference_K(
    y_plus: float, y_minus: float, h_k: float
) -> float:
    """Per-unit-K central difference."""
    return (y_plus - y_minus) / (2.0 * h_k)


def per_degree_from_per_rad(d_per_rad: float) -> float:
    return d_per_rad * np.pi / 180.0


# ---------------------------------------------------------------------------
# Convergence diagnostics (F4 §17–§18)
# ---------------------------------------------------------------------------
def successive_differences(values: list[float]) -> list[float]:
    """``|D(h) - D(h/2)|`` over a decreasing step sequence."""
    return [
        abs(a - b) for a, b in zip(values, values[1:])
    ]


def observed_order(diffs: list[float]) -> float | None:
    """``p_obs = log2(|D(h)-D(h/2)| / |D(h/2)-D(h/4)|)`` (diagnostic only).

    Returns None when either difference is not finite / not positive
    (near-zero derivatives do not produce a meaningful order).
    """
    if len(diffs) < 2:
        return None
    d1, d2 = diffs[0], diffs[1]
    if not (np.isfinite(d1) and np.isfinite(d2)) or d1 <= 0.0 or d2 <= 0.0:
        return None
    return float(np.log2(d1 / d2))


def in_plateau(
    diffs: list[float],
    ref_magnitude: float,
    rel_tol: float = 0.01,
) -> bool:
    """Convergence plateau: the two largest-step successive differences
    are small RELATIVE to the reference derivative magnitude.

    Dimension-aware (F4 §24): an absolute floor is meaningless across
    outputs whose derivatives span m/rad .. (J/kg)/rad; the plateau
    criterion is ``|D(h)-D(h/2)| <= rel_tol * |D_ref|`` for two
    consecutive differences.  ``ref_magnitude`` must be strictly
    positive (near-zero derivatives are handled by the caller as
    negligible and are never a policy criterion).
    """
    if len(diffs) < 2 or ref_magnitude <= 0.0:
        return False
    return (diffs[0] <= rel_tol * ref_magnitude
            and diffs[1] <= rel_tol * ref_magnitude)


# ---------------------------------------------------------------------------
# Representative selection (F4 §8–§9) -- computational, not scientific
# ---------------------------------------------------------------------------
def clearance_to_boxes(
    point: tuple[float, float],
    exclusion_cells: list[dict],
) -> float:
    """L-infinity clearance to the exclusion geometry (selection only)."""
    g, k = point
    best = np.inf
    for cell in exclusion_cells:
        rect = cell.get("rectangle", cell)
        dg = max(rect["gamma_min"] - g, 0.0, g - rect["gamma_max"])
        dk = max(rect["K_min"] - k, 0.0, k - rect["K_max"])
        best = min(best, max(dg, dk))
    return float(best)


def select_representatives(
    coarse_records: dict,
    exclusion_cells: list[dict],
    baseline: tuple[float, float] = (-5.0, 3.0),
) -> list[dict]:
    """Auto-select deep fixed-topology interior representatives.

    Candidates are F2 canonical coarse points; excluded are points inside
    exclusion boxes, DENSE_RECOVERED / grazing / extremal points, health
    anomalies, and points too close to a guardrail to support the
    LARGEST candidate central stencil (F4 §9: guardrail point excluded
    when the largest central stencil would cross the boundary).

    One representative per available Sanger regime (deepest clearance),
    plus the Phase-E baseline (N2).

    ``selection_clearance`` is a computational selection diagnostic, NOT
    a scientific sensitivity metric (F4 §9).
    """
    max_gamma_half = max(GAMMA_STEPS_DEG)      # 0.1 deg
    max_k_half = max(K_STEPS)                  # 0.05

    def _stencil_inside(g: float, k: float) -> bool:
        return (
            GAMMA_GUARDRAIL[0] + max_gamma_half - 1e-12
            <= g <= GAMMA_GUARDRAIL[1] - max_gamma_half + 1e-12
            and K_GUARDRAIL[0] + max_k_half - 1e-12
            <= k <= K_GUARDRAIL[1] - max_k_half + 1e-12
        )

    candidates: list[tuple[float, dict]] = []
    for key, rec in coarse_records.items():
        g, k = rec["parameter"]
        s = rec["sanger"]
        if s.get("event_resolution") in (
            "DENSE_RECOVERED", "GRAZING_OR_UNRESOLVED",
            "GRAZING_BOUNDARY", "REFERENCE_CONFIRMED",
        ):
            continue
        if s.get("recovered_exit_count", 0) > 0:
            continue
        if s.get("terminal_kind") != "srti":
            continue
        if rec.get("health", {}).get("violations"):
            continue
        if not _stencil_inside(g, k):
            continue
        cl = clearance_to_boxes((g, k), exclusion_cells)
        if cl <= 0.0:
            continue
        candidates.append((cl, rec))

    by_regime: dict[str, tuple[float, dict]] = {}
    for cl, rec in candidates:
        regime = rec["sanger"]["sanger_regime"]
        if regime not in by_regime or cl > by_regime[regime][0]:
            by_regime[regime] = (cl, rec)

    reps: list[dict] = []
    baseline_rec = None
    for key, rec in coarse_records.items():
        if tuple(rec["parameter"]) == baseline:
            baseline_rec = rec
            break

    if baseline_rec is not None and _stencil_inside(*baseline):
        reps.append({
            "label": "baseline",
            "gamma0_deg": baseline_rec["parameter"][0],
            "K": baseline_rec["parameter"][1],
            "sanger_regime": baseline_rec["sanger"]["sanger_regime"],
            "exact_topology": (
                baseline_rec["sanger"]["exact_topology_signature"]),
            "baseline": True,
            "selection_clearance": clearance_to_boxes(
                tuple(baseline_rec["parameter"]), exclusion_cells),
            "recovered": False,
        })

    for regime in sorted(by_regime):
        cl, rec = by_regime[regime]
        if tuple(rec["parameter"]) == baseline:
            continue  # baseline already represents N2
        reps.append({
            "label": f"regime-{regime}",
            "gamma0_deg": rec["parameter"][0],
            "K": rec["parameter"][1],
            "sanger_regime": regime,
            "exact_topology": rec["sanger"]["exact_topology_signature"],
            "baseline": False,
            "selection_clearance": cl,
            "recovered": False,
        })
    return reps


# ---------------------------------------------------------------------------
# Adaptive step policy (F4 §24)
# ---------------------------------------------------------------------------
def largest_safe_converged_step(
    h_candidates: tuple[float, ...],
    eligible: dict[float, bool],
    diffs_by_h: dict[float, list[float]],
    floor: float,
) -> tuple[float | None, list[str]]:
    """Largest candidate h that passes the gate and sits on a plateau.

    Conceptual rule (F4 §24): iterate from the largest candidate; require
    (1) the stencil at h is eligible, (2) h and the next smaller eligible
    h are on the convergence plateau.  Returns ``(h, notes)`` or
    ``(None, notes)`` when no safe converged step exists.
    """
    notes: list[str] = []
    ordered = list(h_candidates)
    for i, h in enumerate(ordered):
        if not eligible.get(h, False):
            notes.append(f"h={h}: ineligible")
            continue
        # Plateau needs a smaller eligible step to compare against.
        smaller = [
            h2 for h2 in ordered[i + 1:] if eligible.get(h2, False)
        ]
        if not smaller:
            notes.append(f"h={h}: no smaller eligible step")
            continue
        h_next = smaller[0]
        d_h = diffs_by_h.get(h, [])
        d_next = diffs_by_h.get(h_next, [])
        if in_plateau(d_h, floor) and in_plateau(d_next, floor):
            return h, notes
        notes.append(f"h={h}: no plateau (|D(h)-D(h/2)| above floor)")
    return None, notes
