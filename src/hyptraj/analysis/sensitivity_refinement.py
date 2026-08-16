"""Phase-F adaptive grazing-boundary refinement infrastructure (F3).

F3 — Adaptive Grazing-Boundary Refinement
(docs/phase_f/f3_boundary_refinement.md).

Dyadic 2D cell refinement of the F2 skip-count transition candidate cells
(P1 compact transition cells, currently 179) down to the F0-frozen target
resolution ``Delta gamma <= 0.01 deg`` AND ``Delta K <= 0.01``, with the
formal branch-conditioned signed grazing diagnostic ``Phi_N``.

Frozen constraints (F3):

* point execution reuses the F2/F2.1 executor
  (``run_parameter_point`` with the Sanger research integrator); this
  module NEVER calls ``solve_ivp`` and never duplicates physics;
* the final domain is strictly the F2 guardrail domain
  gamma0 ∈ [-9,-1] deg, K ∈ [1,5]; no further expansion; cells touching
  a guardrail refine only inside the domain and are marked open;
* ``Phi_N`` is branch-conditioned: N-side uses the SRTI altitude
  (``h_SRTI - h_atm = -M_S``), N+1-side uses the NEWLY-CREATED LAST VAC
  apogee of the N+1 trajectory (VAC arc index N, zero-based) -- NEVER
  ``min(M_A_clearance_m)``;
* no boundary curve fit, no critical-K regression, no derivative, no
  Phase-E B/C/D surfaces, no optimization, no STM/saltation/FTLE;
* dyadic coordinates (0.25 / 0.125 and their successive bisections are
  exactly representable binary dyadics) with integer lattice indices --
  no ``while x += delta`` drift.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

import numpy as np

from hyptraj.analysis.sensitivity_grid import (
    F1_COMMIT,
    F21_COMMIT,
    F2_POINT_SCHEMA,
    cache_key,
    validate_cache_record,
)
from hyptraj.analysis.sensitivity_pilot import (
    F01_COMMIT,
    F0_PROTOCOL_COMMIT,
    PHASE_E_ANCHOR_COMMIT,
    PHASE_E_ANCHOR_TAG,
    ParameterPoint,
)
from hyptraj.simulation.sanger_research_trajectory import (
    SANGER_RESEARCH_EVENT_RESOLUTION_VERSION,
)

# ---------------------------------------------------------------------------
# Frozen F3 constants
# ---------------------------------------------------------------------------
F2_COMMIT = "35c66375081bf9f4924f365f2a5517dcfee3e3f4"

F3_POINT_SCHEMA = "f3-refinement-point-v1"
F3_SUMMARY_SCHEMA = "f3-refinement-summary-v1"

# F2 guardrail domain (F3 final domain; never expanded).
GAMMA_GUARD_MIN = -9.0
GAMMA_GUARD_MAX = -1.0
K_GUARD_MIN = 1.0
K_GUARD_MAX = 5.0

# Coarse cell size at depth 0 (F2 coarse grid).
GAMMA_CELL_DEG = 0.25
K_CELL = 0.125

# F0-frozen refinement targets / safety limit.
TARGET_GAMMA_DEG = 0.01
TARGET_K = 0.01
MAX_DEPTH = 6

# Terminal branch / candidate vocabulary.
ADJACENT_SKIP_BRANCH = "ADJACENT_SKIP_BRANCH"
EXACT_TOPOLOGY_ONLY = "EXACT_TOPOLOGY_ONLY"
MULTISKIP = "MULTISKIP"
QIAN_TOPOLOGY = "QIAN_TOPOLOGY"
GRAZING_MARKER = "GRAZING_MARKER"
UNIFORM = "UNIFORM"

TERMINAL_REFINED_BOUNDARY_CELL = "REFINED_BOUNDARY_CELL"
TERMINAL_UNIFORM_CELL = "UNIFORM_CELL"
TERMINAL_MAX_DEPTH_CELL = "MAX_DEPTH_CELL"
TERMINAL_UNRESOLVED_MULTISKIP_CELL = "UNRESOLVED_MULTISKIP_CELL"


# ---------------------------------------------------------------------------
# Dyadic lattice (integer-indexed, exact)
# ---------------------------------------------------------------------------
class DyadicLattice:
    """Exact dyadic coordinate helpers on the guardrail domain.

    At depth ``d`` the gamma spacing is ``0.25 / 2^d`` and the K spacing
    ``0.125 / 2^d``; every coordinate is ``guard_min + i * spacing`` with
    a binary-dyadic spacing, so float arithmetic is exact and the integer
    lattice index is the canonical identity.
    """

    def __init__(self) -> None:
        self._gamma_cells0 = Fraction(
            int(round((GAMMA_GUARD_MAX - GAMMA_GUARD_MIN)
                      / GAMMA_CELL_DEG)))      # 32
        self._k_cells0 = Fraction(
            int(round((K_GUARD_MAX - K_GUARD_MIN) / K_CELL)))  # 32

    def gamma_spacing(self, depth: int) -> float:
        return GAMMA_CELL_DEG / (2.0 ** depth)

    def k_spacing(self, depth: int) -> float:
        return K_CELL / (2.0 ** depth)

    def gamma_value(self, depth: int, g_i: int) -> float:
        return GAMMA_GUARD_MIN + g_i * self.gamma_spacing(depth)

    def k_value(self, depth: int, k_i: int) -> float:
        return K_GUARD_MIN + k_i * self.k_spacing(depth)

    def gamma_index(self, depth: int, gamma0_deg: float) -> int:
        i = round((gamma0_deg - GAMMA_GUARD_MIN) / self.gamma_spacing(depth))
        return int(i)

    def k_index(self, depth: int, k: float) -> int:
        i = round((k - K_GUARD_MIN) / self.k_spacing(depth))
        return int(i)

    def in_domain(self, gamma0_deg: float, k: float) -> bool:
        return (
            GAMMA_GUARD_MIN - 1e-12 <= gamma0_deg <= GAMMA_GUARD_MAX + 1e-12
            and K_GUARD_MIN - 1e-12 <= k <= K_GUARD_MAX + 1e-12
        )


LATTICE = DyadicLattice()


@dataclass(frozen=True)
class DyadicCell:
    """One dyadic cell at depth ``d`` with lower-left corner (g_i, k_i)."""

    depth: int
    g_i: int
    k_i: int

    @property
    def gamma_min(self) -> float:
        return LATTICE.gamma_value(self.depth, self.g_i)

    @property
    def gamma_max(self) -> float:
        return LATTICE.gamma_value(self.depth, self.g_i + 1)

    @property
    def k_min(self) -> float:
        return LATTICE.k_value(self.depth, self.k_i)

    @property
    def k_max(self) -> float:
        return LATTICE.k_value(self.depth, self.k_i + 1)

    @property
    def delta_gamma_deg(self) -> float:
        return self.gamma_max - self.gamma_min

    @property
    def delta_k(self) -> float:
        return self.k_max - self.k_min

    @property
    def center(self) -> tuple[float, float]:
        return ((self.gamma_min + self.gamma_max) / 2.0,
                (self.k_min + self.k_max) / 2.0)

    def corner_points(self) -> tuple[ParameterPoint, ...]:
        return (
            ParameterPoint(self.gamma_min, self.k_min),
            ParameterPoint(self.gamma_max, self.k_min),
            ParameterPoint(self.gamma_min, self.k_max),
            ParameterPoint(self.gamma_max, self.k_max),
        )

    def midpoint_points(self) -> tuple[ParameterPoint, ...]:
        """The up-to-5 new points introduced by bisection (F3 §16).

        Only points inside the guardrail domain are returned (a guardrail
        child never samples outside the domain).
        """
        gm = (self.gamma_min + self.gamma_max) / 2.0
        km = (self.k_min + self.k_max) / 2.0
        candidates = [
            ParameterPoint(gm, self.k_min),   # gamma-mid / K-low
            ParameterPoint(gm, self.k_max),   # gamma-mid / K-high
            ParameterPoint(self.gamma_min, km),  # gamma-low / K-mid
            ParameterPoint(self.gamma_max, km),  # gamma-high / K-mid
            ParameterPoint(gm, km),           # center
        ]
        return tuple(
            p for p in candidates
            if LATTICE.in_domain(p.gamma0_deg, p.K)
        )

    def subdivide(self) -> tuple["DyadicCell", ...]:
        """Four exact children at depth+1 (F3 §14)."""
        d = self.depth + 1
        return (
            DyadicCell(d, 2 * self.g_i, 2 * self.k_i),
            DyadicCell(d, 2 * self.g_i + 1, 2 * self.k_i),
            DyadicCell(d, 2 * self.g_i, 2 * self.k_i + 1),
            DyadicCell(d, 2 * self.g_i + 1, 2 * self.k_i + 1),
        )

    def as_dict(self) -> dict:
        return {
            "gamma_min": self.gamma_min,
            "gamma_max": self.gamma_max,
            "K_min": self.k_min,
            "K_max": self.k_max,
            "depth": self.depth,
            "delta_gamma_deg": self.delta_gamma_deg,
            "delta_K": self.delta_k,
            "center": list(self.center),
        }


def coarse_cell_from_rectangle(
    gamma_min: float, gamma_max: float, k_min: float, k_max: float
) -> DyadicCell:
    """Build the depth-0 dyadic cell covering an F2 coarse rectangle."""
    d = 0
    g_i = LATTICE.gamma_index(d, gamma_min)
    k_i = LATTICE.k_index(d, k_min)
    cell = DyadicCell(d, g_i, k_i)
    if (abs(cell.gamma_min - gamma_min) > 1e-9
            or abs(cell.gamma_max - gamma_max) > 1e-9
            or abs(cell.k_min - k_min) > 1e-9
            or abs(cell.k_max - k_max) > 1e-9):
        raise ValueError(
            f"F2 rectangle [{gamma_min},{gamma_max}] x [{k_min},{k_max}] "
            "is not an exact depth-0 dyadic cell.")
    return cell


def target_resolution_reached(cell: DyadicCell) -> bool:
    return (cell.delta_gamma_deg <= TARGET_GAMMA_DEG
            and cell.delta_k <= TARGET_K)


# ---------------------------------------------------------------------------
# Branch identity
# ---------------------------------------------------------------------------
def branch_label(n: int) -> str:
    return f"B{n}"


def branch_from_regimes(regime_a: str, regime_b: str) -> str | None:
    """``B_N`` for an adjacent pair ``SRTI_N <-> SRTI_{N+1}``, else None."""
    if regime_a.startswith("SRTI_N") and regime_b.startswith("SRTI_N"):
        na, nb = int(regime_a[-1]), int(regime_b[-1])
        if abs(na - nb) == 1:
            return branch_label(min(na, nb))
    return None


def classify_cell_branch(
    corner_regimes: tuple[str, ...],
) -> tuple[str, str | None]:
    """Classify a candidate cell into the F3 §23 branch vocabulary.

    Returns ``(classification, branch)`` where ``branch`` is ``B_N`` for
    ADJACENT_SKIP_BRANCH cells and None otherwise.
    """
    sanger = {r for r in corner_regimes if r.startswith("SRTI_N")}
    if len(sanger) >= 2:
        skips = sorted(int(r[-1]) for r in sanger)
        if max(skips) - min(skips) > 1:
            return MULTISKIP, None
        if len(skips) == 2 and skips[1] - skips[0] == 1:
            return ADJACENT_SKIP_BRANCH, branch_label(skips[0])
    return ADJACENT_SKIP_BRANCH, None


# ---------------------------------------------------------------------------
# Signed branch-conditioned grazing diagnostic Phi_N (F3 §7–§9)
# ---------------------------------------------------------------------------
def phi_n_for_point(
    sanger_row: dict,
    n: int,
    h_atm: float,
) -> tuple[float | None, str | None, dict]:
    """Branch-conditioned signed grazing diagnostic ``Phi_N``.

    * regime = SRTI_N   -> ``Phi = h_SRTI - h_atm = -M_S``  (N side, < 0);
    * regime = SRTI_{N+1} -> ``Phi = h_apogee,new - h_atm`` where the
      apogee is the NEWLY-CREATED LAST VAC apogee (VAC arc index N,
      zero-based) -- NEVER ``min(M_A_clearance_m)``;
    * any other regime -> ``(None, None, {})`` (Phi_N undefined there;
      no extension across N-1 / N+2).

    Returns ``(phi, side, diagnostics)``.
    """
    regime = sanger_row.get("sanger_regime")
    if regime == f"SRTI_N{n}":
        m_s = sanger_row.get("M_S_clearance_m")
        if m_s is None:
            return None, None, {"reason": "no M_S (non-SRTI terminal)"}
        phi = -float(m_s)
        return phi, "N", {
            "h_SRTI_m": float(h_atm + phi),   # h_SRTI = h_atm - M_S < h_atm
            "M_S_m": float(m_s),
        }
    if regime == f"SRTI_N{n + 1}":
        ma = sanger_row.get("M_A_clearance_m") or []
        if len(ma) <= n:
            return None, None, {
                "reason": f"SRTI_N{n+1} has only {len(ma)} VAC apogees; "
                          f"arc index {n} missing",
            }
        phi = float(ma[n])  # newly-created LAST VAC apogee (index N)
        return phi, "N+1", {
            "apogee_index": n,
            "h_apogee_new_m": float(h_atm + phi),
            "num_vac_arcs": len(ma),
        }
    return None, None, {"reason": f"regime {regime} not in branch B{n}"}


def phi_sign_anomaly(phi: float | None, side: str | None) -> bool:
    """True when a sampled point violates the expected Phi_N sign."""
    if phi is None or side is None:
        return False
    if side == "N":
        return phi >= 0.0
    if side == "N+1":
        return phi <= 0.0
    return False


# ---------------------------------------------------------------------------
# Newly-created exit transversality T_N (F3 §11)
# ---------------------------------------------------------------------------
def new_exit_transversality(
    sanger_row: dict,
    n: int,
) -> float | None:
    """``T_N = dh/dt`` at the newly-created atmosphere exit.

    For the SRTI_{N+1} trajectory the newly-created exit is the
    (N+1)-th ATM->VAC exit (zero-based index N) -- the exit that opened
    the new skip.  Returns None when not applicable.
    """
    regime = sanger_row.get("sanger_regime")
    if regime != f"SRTI_N{n + 1}":
        return None
    exits = sanger_row.get("exit_dhdt_mps") or []
    if len(exits) <= n:
        return None
    return float(exits[n])


def new_vac_duration(
    sanger_row: dict,
    n: int,
) -> float | None:
    """Optional newly-created VAC duration (F3 §12, non-acceptance).

    From the serialized event sequence: ``entry_new - exit_new`` for the
    newly-created skip.  Not an acceptance criterion; None when the
    metadata cannot be reconstructed without duplicating the state
    machine.
    """
    events = sanger_row.get("event_sequence") or []
    exit_indices = [i for i, k in enumerate(events) if k == "atmosphere_exit"]
    entry_indices = [i for i, k in enumerate(events)
                     if k == "atmosphere_entry"]
    if len(exit_indices) <= n or len(entry_indices) <= n:
        return None
    # The times are not in the event_sequence (kinds only); durations are
    # reconstructed from the grazing diagnostics when available.
    return None


# ---------------------------------------------------------------------------
# Child candidate rule (F3 §21–§22)
# ---------------------------------------------------------------------------
def child_is_candidate(
    child: DyadicCell,
    point_lookup: dict,
    branch_n: int | None,
    h_atm: float,
) -> tuple[bool, list[str]]:
    """Apply the F3 §21 child candidate rule to one child cell.

    A child is a candidate when any of its four corners differ in Sanger
    compact regime / exact topology, in Qian regime / signature, when
    Phi_N sampled points show both sides within the same B_N neighbourhood,
    or when a verified grazing marker is present.  Uniform children stop.
    """
    corners = child.corner_points()
    views = []
    for p in corners:
        rec = point_lookup.get(cache_key(p))
        if rec is None:
            return True, ["missing_corner"]  # must refine to fill the cell
        views.append(rec)

    sanger_regimes = {v["sanger"]["sanger_regime"] for v in views}
    sanger_sigs = {v["sanger"]["exact_topology_signature"] for v in views}
    qian_regimes = {v["qian"]["qian_regime"] for v in views}
    qian_sigs = {v["qian"]["exact_topology_signature"] for v in views}

    reasons: list[str] = []
    if len(sanger_regimes) > 1:
        reasons.append("sanger_compact_differs")
    if len(sanger_sigs) > 1:
        reasons.append("sanger_exact_differs")
    if len(qian_regimes) > 1:
        reasons.append("qian_compact_differs")
    if len(qian_sigs) > 1:
        reasons.append("qian_exact_differs")

    if branch_n is not None and not reasons:
        # Same B_N neighbourhood: both Phi_N sides present?
        sides = set()
        for v in views:
            phi, side, _ = phi_n_for_point(v["sanger"], branch_n, h_atm)
            if side is not None:
                sides.add(side)
        if {"N", "N+1"} <= sides:
            reasons.append("phi_n_both_sides")

    if any(
        v["sanger"].get("sanger_regime") == "SANGER_GRAZING_BOUNDARY"
        for v in views
    ):
        reasons.append("grazing_marker")

    return bool(reasons), reasons


# ---------------------------------------------------------------------------
# Terminal cell assembly (F3 §27–§28)
# ---------------------------------------------------------------------------
def assemble_terminal_cell(
    cell: DyadicCell,
    classification: str,
    branch: str | None,
    point_lookup: dict,
    h_atm: float,
    open_edges: tuple[str, ...] = (),
) -> dict:
    """One terminal refined boundary cell record (F3 §27–§28, §37).

    The scientific object is the enclosing parameter rectangle; the cell
    center is marked ``visualization_center_only``.
    """
    corners = cell.corner_points()
    corner_views = []
    for p in corners:
        rec = point_lookup.get(cache_key(p))
        corner_views.append({
            "parameter": [p.gamma0_deg, p.K],
            "sanger_regime": rec["sanger"]["sanger_regime"] if rec else None,
            "qian_regime": rec["qian"]["qian_regime"] if rec else None,
        })

    phi_vals: dict[str, float | None] = {}
    if branch is not None:
        n = int(branch[1:])
        for side_key, regime in (("N", f"SRTI_N{n}"),
                                 ("N+1", f"SRTI_N{n + 1}")):
            vals = []
            for p in corners:
                rec = point_lookup.get(cache_key(p))
                if rec is None or rec["sanger"]["sanger_regime"] != regime:
                    continue
                phi, side, _ = phi_n_for_point(
                    rec["sanger"], n, h_atm)
                if phi is not None:
                    vals.append(phi)
            phi_vals[side_key] = min(vals) if vals else None

    return {
        "terminal_type": TERMINAL_REFINED_BOUNDARY_CELL,
        "classification": classification,
        "branch": branch,
        "rectangle": {
            "gamma_min": cell.gamma_min,
            "gamma_max": cell.gamma_max,
            "K_min": cell.k_min,
            "K_max": cell.k_max,
            "delta_gamma_deg": cell.delta_gamma_deg,
            "delta_K": cell.delta_k,
            "depth": cell.depth,
            "target_resolution_met": target_resolution_reached(cell),
        },
        "center": list(cell.center),
        "visualization_center_only": True,
        "corners": corner_views,
        "phi_N_sampled": phi_vals,
        "open_edges": list(open_edges),
    }


def open_edges_of_cell(cell: DyadicCell) -> tuple[str, ...]:
    """Guardrail edges touched by the cell (F3 §37)."""
    edges = []
    if cell.gamma_min <= GAMMA_GUARD_MIN + 1e-12:
        edges.append("gamma_lower")
    if cell.gamma_max >= GAMMA_GUARD_MAX - 1e-12:
        edges.append("gamma_upper")
    if cell.k_min <= K_GUARD_MIN + 1e-12:
        edges.append("K_lower")
    if cell.k_max >= K_GUARD_MAX - 1e-12:
        edges.append("K_upper")
    return tuple(edges)


# ---------------------------------------------------------------------------
# Row / column multiplicity (F3 §39)
# ---------------------------------------------------------------------------
def row_column_multiplicity(
    terminal_cells: list[dict],
) -> dict:
    """Max number of disjoint brackets per fixed-gamma row / fixed-K column.

    Sampled-domain empirical multiplicity; never a global single-valued
    assumption.
    """
    rows: dict[float, list[tuple[float, float]]] = {}
    cols: dict[float, list[tuple[float, float]]] = {}
    for c in terminal_cells:
        r = c["rectangle"]
        rows.setdefault(round(r["gamma_min"], 6), []).append(
            (r["K_min"], r["K_max"]))
        cols.setdefault(round(r["K_min"], 6), []).append(
            (r["gamma_min"], r["gamma_max"]))

    def _max_disjoint(intervals: list[tuple[float, float]]) -> int:
        # Number of maximal disjoint clusters (adjacent intervals merge).
        if not intervals:
            return 0
        merged = sorted(intervals)
        clusters = 1
        prev_end = merged[0][1]
        for a, b in merged[1:]:
            if a > prev_end + 1e-12:
                clusters += 1
            prev_end = max(prev_end, b)
        return clusters

    return {
        "max_row_multiplicity": max(
            (_max_disjoint(v) for v in rows.values()), default=0),
        "max_column_multiplicity": max(
            (_max_disjoint(v) for v in cols.values()), default=0),
        "rows_with_multiplicity_gt_1": [
            {"gamma0": g, "multiplicity": _max_disjoint(v)}
            for g, v in sorted(rows.items()) if _max_disjoint(v) > 1
        ],
        "columns_with_multiplicity_gt_1": [
            {"K": k, "multiplicity": _max_disjoint(v)}
            for k, v in sorted(cols.items()) if _max_disjoint(v) > 1
        ],
    }


# ---------------------------------------------------------------------------
# F4 exclusion geometry (F3 §41)
# ---------------------------------------------------------------------------
def build_f4_exclusion_cells(
    refined_cells: list[dict],
    unresolved_cells: list[dict],
    grazing_marker_cells: list[dict],
) -> dict:
    """All final boxes excluded from ordinary finite differences (F3 §41).

    F4 stencils crossing these boxes or landing on a different exact
    topology must report the derivative undefined.
    """
    cells = (
        [{"type": TERMINAL_REFINED_BOUNDARY_CELL, **c}
         for c in refined_cells]
        + [{"type": TERMINAL_UNRESOLVED_MULTISKIP_CELL, **c}
           for c in unresolved_cells]
        + [{"type": GRAZING_MARKER, **c} for c in grazing_marker_cells]
    )
    return {
        "schema_version": "f3-f4-exclusion-v1",
        "note": "geometry only; derivatives are computed in F4 and are "
                "undefined across these boxes or across exact-topology "
                "changes",
        "cells": cells,
    }


# ---------------------------------------------------------------------------
# Reference queue bookkeeping (F3 §29–§31)
# ---------------------------------------------------------------------------
def validate_f3_cache_record(
    record: dict,
    expected_provenance: dict,
) -> tuple[bool, str]:
    """F3 cache validation: sensitivity-grid checks + the F2 commit.

    The F2 canonical cache schema does not carry ``phase_f_f2_commit``
    (the F2 commit is the moving HEAD at run time), so the F2 validator
    cannot check it; the F3 point cache pins the F2 commit explicitly and
    must reject any record computed before the F2 canonical freeze.
    """
    ok, reason = validate_cache_record(record, expected_provenance)
    if not ok:
        return False, reason
    prov = record.get("provenance", {})
    if prov.get("phase_f_f2_commit") != expected_provenance.get(
            "phase_f_f2_commit"):
        return False, "provenance mismatch: phase_f_f2_commit"
    return True, "valid"


def recovered_event_reference_entry(
    parameter: tuple[float, float],
    production_regime: str,
    production_skip: int | None,
) -> dict:
    return {
        "parameter": list(parameter),
        "reason": "DENSE_RECOVERED",
        "production_regime": production_regime,
        "production_skip": production_skip,
    }


def sign_anomaly_reference_entry(
    parameter: tuple[float, float],
    regime: str,
    phi: float,
    side: str,
) -> dict:
    return {
        "parameter": list(parameter),
        "reason": "PHI_SIGN_ANOMALY",
        "regime": regime,
        "phi": phi,
        "side": side,
    }


def branch_extremal_entry(
    branch: str,
    side: str,
    parameter: tuple[float, float],
    regime: str,
    production_phi: float,
) -> dict:
    return {
        "branch": branch,
        "side": side,
        "parameter": list(parameter),
        "regime": regime,
        "production_phi": production_phi,
    }
