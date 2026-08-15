"""Phase-F coarse gamma0-K hybrid-regime map infrastructure (F2).

Deterministic Cartesian grid definition, F1 point-runner reuse, nested F2
point records, joint topology signatures, categorical regime matrices,
boundary candidate-cell detection, edge-touch / domain-expansion planning,
coarse boundary brackets and checkpoint/cache validation.

F2 policy (frozen in docs/phase_f/sensitivity_protocol.md + F2 task):

* reuses ``sensitivity_pilot.run_parameter_point`` -- no second point
  execution, no copied physics;
* categorical data is NEVER interpolated; categorical IDs are
  visualization-only encodings, string labels always retained;
* no derivative / gradient (F4 only), no Phase-E Protocol B/C/D surfaces
  (F6 only), no optimization;
* domain expansion fires ONLY when a boundary-candidate cell touches a
  domain edge (F0 §9); small margins alone are edge hints, not triggers;
* guardrails: gamma0 ∈ [-9,-1] deg, K ∈ [1,5]; at the guardrail an
  unclosed boundary is reported OPEN_BOUNDARY.
"""

from dataclasses import dataclass

import numpy as np

from hyptraj.analysis.sensitivity_pilot import (
    ANCHOR_GAMMA0_DEG,
    ANCHOR_K,
    F01_COMMIT,
    F0_PROTOCOL_COMMIT,
    GAMMA_SLICE_DEG,
    K_SLICE,
    PHASE_E_ANCHOR_COMMIT,
    PHASE_E_ANCHOR_TAG,
    SCHEMA_VERSION as F1_SCHEMA_VERSION,
    ParameterPoint,
    audit_point_health,
    run_parameter_point,
)

# Frozen Phase F commits (provenance anchors, never recomputed).
F1_COMMIT = "417b2a46cd9e3e621a4914f35f531ef7f0a092f4"

# F2 schema / cache versions.
F2_POINT_SCHEMA = "f2-coarse-map-point-v1"
F2_SUMMARY_SCHEMA = "f2-coarse-map-summary-v1"

# Frozen initial coarse grid (F0 §8).
GAMMA_MIN_INIT = -7.0
GAMMA_MAX_INIT = -3.0
K_MIN_INIT = 2.0
K_MAX_INIT = 4.0
GAMMA_STEP_DEG = 0.25
K_STEP = 0.125

# Absolute computational guardrails (F0 §9).
GAMMA_GUARDRAIL = (-9.0, -1.0)
K_GUARDRAIL = (1.0, 5.0)

# Expansion increments (F0 §9).
GAMMA_EXPAND_WIDTH_DEG = 1.0
K_EXPAND_WIDTH = 0.5

# F1 observed compact regime sequences (from docs/phase_f/f1_pilot_report.md;
# used ONLY for the F2-vs-F1 consistency gate, not as physics).
GAMMA_SLICE_F1_SANGER = (
    ("SRTI_N2",) * 10 + ("SRTI_N1",) * 7
)  # gamma0 -7.00..-4.75, then -4.50..-3.00
K_SLICE_F1_SANGER = (
    ("SRTI_N1",) * 7 + ("SRTI_N2",) * 10
)  # K 2.000..2.750, then 2.875..4.000


@dataclass(frozen=True)
class GridDomain:
    """One rectangular coarse domain (canonical values, exact spacing)."""

    gamma_min: float
    gamma_max: float
    k_min: float
    k_max: float

    @property
    def gamma_grid(self) -> tuple[float, ...]:
        n = int(round((self.gamma_max - self.gamma_min) / GAMMA_STEP_DEG)) + 1
        return tuple(float(x) for x in np.linspace(
            self.gamma_min, self.gamma_max, n))

    @property
    def k_grid(self) -> tuple[float, ...]:
        n = int(round((self.k_max - self.k_min) / K_STEP)) + 1
        return tuple(float(x) for x in np.linspace(self.k_min, self.k_max, n))

    def as_dict(self) -> dict:
        return {
            "gamma0_range_deg": [self.gamma_min, self.gamma_max],
            "K_range": [self.k_min, self.k_max],
            "gamma_step_deg": GAMMA_STEP_DEG,
            "K_step": K_STEP,
        }


def initial_domain() -> GridDomain:
    return GridDomain(GAMMA_MIN_INIT, GAMMA_MAX_INIT, K_MIN_INIT, K_MAX_INIT)


def grid_points(domain: GridDomain) -> tuple[ParameterPoint, ...]:
    """All Cartesian grid points, row-major (gamma rows, K columns)."""
    return tuple(
        ParameterPoint(gamma0_deg=g, K=k)
        for g in domain.gamma_grid
        for k in domain.k_grid
    )


def grid_index(domain: GridDomain, point: ParameterPoint) -> tuple[int, int]:
    """(i_gamma, i_K) grid index; canonical values must match exactly."""
    g_list = list(domain.gamma_grid)
    k_list = list(domain.k_grid)
    return (g_list.index(point.gamma0_deg), k_list.index(point.K))


def baseline_grid_index(domain: GridDomain) -> tuple[int, int]:
    return grid_index(
        domain, ParameterPoint(gamma0_deg=ANCHOR_GAMMA0_DEG, K=ANCHOR_K))


# ---------------------------------------------------------------------------
# Joint topology signatures (F2 §10–§11)
# ---------------------------------------------------------------------------
def joint_regime(qian_regime: str, sanger_regime: str) -> tuple[str, str]:
    """Joint regime = (qian_regime, sanger_regime); never a winner class."""
    return (qian_regime, sanger_regime)


def joint_exact_topology_signature(
    qian_sig: str, sanger_sig: str
) -> str:
    """Deterministic concatenation of the two exact signatures."""
    return f"QIAN[{qian_sig}] || SANGER[{sanger_sig}]"


# ---------------------------------------------------------------------------
# F2 point record (wraps F1 rows; no recomputation)
# ---------------------------------------------------------------------------
def make_point_record(
    domain: GridDomain,
    point: ParameterPoint,
    qian_row: dict,
    sanger_row: dict,
    health_violations: list[str],
    wall_runtime_s: float,
    git_commit: str,
    solver_config: dict,
) -> dict:
    """Nested F2 point record (F2 §8–§9); reuses the F1 rows verbatim."""
    i_g, i_k = grid_index(domain, point)
    return {
        "schema_version": F2_POINT_SCHEMA,
        "parameter": [point.gamma0_deg, point.K],
        "grid_index": [i_g, i_k],
        "provenance": {
            "git_commit": git_commit,
            "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
            "phase_e_anchor_commit": PHASE_E_ANCHOR_COMMIT,
            "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
            "phase_f_f01_commit": F01_COMMIT,
            "phase_f_f1_commit": F1_COMMIT,
            "f1_row_schema": F1_SCHEMA_VERSION,
            "f2_point_schema": F2_POINT_SCHEMA,
            "solver_config": solver_config,
            "domain": domain.as_dict(),
        },
        "qian": qian_row,
        "sanger": sanger_row,
        "joint_regime": joint_regime(
            qian_row["qian_regime"], sanger_row["sanger_regime"]),
        "joint_exact_topology_signature": joint_exact_topology_signature(
            qian_row["exact_topology_signature"],
            sanger_row["exact_topology_signature"]),
        "health": {"violations": list(health_violations)},
        "wall_runtime_s": wall_runtime_s,
    }


# ---------------------------------------------------------------------------
# Checkpoint cache (F2 §14–§16, §60)
# ---------------------------------------------------------------------------
def cache_key(point: ParameterPoint) -> str:
    """Canonical cache key ``"gamma0_deg|K"`` (exact frozen grid values)."""
    return f"{point.gamma0_deg:.6f}|{point.K:.6f}"


def validate_cache_record(
    record: dict,
    expected_provenance: dict,
) -> tuple[bool, str]:
    """A cache record is reusable only if every provenance anchor matches.

    Compares schema version, Phase E anchor, F0 / F0.1 / F1 commits and
    the solver configuration; the declared domain must be SELF-CONSISTENT
    (the record's own parameter point lies inside its declared domain),
    because the active domain legitimately changes between the initial
    grid and expansion strips.  The running ``git_commit`` is deliberately
    NOT part of the reuse check (the HEAD may move between F2 runs).
    """
    prov = record.get("provenance", {})
    param = record.get("parameter")
    dom = prov.get("domain") or {}
    g_range = dom.get("gamma0_range_deg")
    k_range = dom.get("K_range")
    if g_range and k_range and param:
        in_domain = (
            g_range[0] - 1e-9 <= param[0] <= g_range[1] + 1e-9
            and k_range[0] - 1e-9 <= param[1] <= k_range[1] + 1e-9
        )
    else:
        in_domain = True
    checks = {
        "schema_version": record.get("schema_version")
        == expected_provenance.get("schema_version"),
        "phase_e_anchor_commit": prov.get("phase_e_anchor_commit")
        == expected_provenance.get("phase_e_anchor_commit"),
        "phase_f_protocol_commit": prov.get("phase_f_protocol_commit")
        == expected_provenance.get("phase_f_protocol_commit"),
        "phase_f_f01_commit": prov.get("phase_f_f01_commit")
        == expected_provenance.get("phase_f_f01_commit"),
        "phase_f_f1_commit": prov.get("phase_f_f1_commit")
        == expected_provenance.get("phase_f_f1_commit"),
        "solver_config": prov.get("solver_config")
        == expected_provenance.get("solver_config"),
        "domain_self_consistent": in_domain,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        return False, f"provenance mismatch: {', '.join(failed)}"
    return True, "valid"


def load_point_cache(path) -> dict[str, dict]:
    """Load a jsonl point cache; the last incomplete line is ignored.

    Every previously completed point survives an interrupted run; only a
    trailing partial record is dropped (F2 §60).
    """
    records: dict[str, dict] = {}
    if not path.exists():
        return records
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.strip():
            continue
        try:
            record = __import__("json").loads(line)
        except ValueError:
            # Incomplete trailing record from an interrupted write.
            continue
        key = cache_key(
            ParameterPoint(
                gamma0_deg=record["parameter"][0], K=record["parameter"][1]))
        records[key] = record
    return records


def append_cache_record(path, record: dict) -> None:
    """Append one point record to the jsonl cache (line + flush)."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(__import__("json").dumps(record) + "\n")
        f.flush()


# ---------------------------------------------------------------------------
# Boundary candidate cells (F2 §26–§29)
# ---------------------------------------------------------------------------
def _corner_view(record: dict) -> dict:
    return {
        "parameter": record["parameter"],
        "qian_regime": record["qian"]["qian_regime"],
        "sanger_regime": record["sanger"]["sanger_regime"],
        "joint_regime": record["joint_regime"],
        "qian_exact": record["qian"]["exact_topology_signature"],
        "sanger_exact": record["sanger"]["exact_topology_signature"],
    }


def detect_boundary_cells(
    domain: GridDomain,
    records: dict[str, dict],
) -> list[dict]:
    """Mark BOUNDARY_CANDIDATE cells over the 2D coarse grid (F2 §26–§27).

    A cell (four grid corners) is a candidate when any corner compact
    regime differs (Qian / Sanger / joint) or any corner exact topology
    signature differs.  Cells whose compact regimes agree but exact
    signatures differ are EXACT_TOPOLOGY_ONLY_CANDIDATE (still
    candidates).  No cell-center evaluation is done (F3).
    """
    g_grid = list(domain.gamma_grid)
    k_grid = list(domain.k_grid)
    cells: list[dict] = []
    for i_g in range(len(g_grid) - 1):
        for i_k in range(len(k_grid) - 1):
            corners_keys = [
                cache_key(ParameterPoint(g_grid[i_g], k_grid[i_k])),
                cache_key(ParameterPoint(g_grid[i_g + 1], k_grid[i_k])),
                cache_key(ParameterPoint(g_grid[i_g], k_grid[i_k + 1])),
                cache_key(ParameterPoint(g_grid[i_g + 1], k_grid[i_k + 1])),
            ]
            missing = [k for k in corners_keys if k not in records]
            if missing:
                continue  # cell not complete yet (partial map)
            corners = [_corner_view(records[k]) for k in corners_keys]
            reasons: list[str] = []
            if len({c["qian_regime"] for c in corners}) > 1:
                reasons.append("qian_compact_differs")
            if len({c["sanger_regime"] for c in corners}) > 1:
                reasons.append("sanger_compact_differs")
            if len({tuple(c["joint_regime"]) for c in corners}) > 1:
                reasons.append("joint_compact_differs")
            exact_differs = (
                len({c["qian_exact"] for c in corners}) > 1
                or len({c["sanger_exact"] for c in corners}) > 1
            )
            if exact_differs:
                reasons.append("exact_topology_differs")
            compact_differs = any(
                r.startswith(("qian_", "sanger_", "joint_"))
                for r in reasons
            )
            exact_only = (not compact_differs) and exact_differs
            cells.append(
                {
                    "gamma_min": g_grid[i_g],
                    "gamma_max": g_grid[i_g + 1],
                    "K_min": k_grid[i_k],
                    "K_max": k_grid[i_k + 1],
                    "corners": corners,
                    "candidate": bool(reasons),
                    "candidate_reasons": reasons,
                    "exact_topology_only": exact_only,
                    **edge_touch_flags(g_grid[i_g], g_grid[i_g + 1],
                                       k_grid[i_k], k_grid[i_k + 1],
                                       domain),
                }
            )
    return cells


def edge_touch_flags(
    gamma_min: float,
    gamma_max: float,
    k_min: float,
    k_max: float,
    domain: GridDomain,
) -> dict:
    return {
        "touches_gamma_lower": gamma_min <= domain.gamma_min,
        "touches_gamma_upper": gamma_max >= domain.gamma_max,
        "touches_K_lower": k_min <= domain.k_min,
        "touches_K_upper": k_max >= domain.k_max,
    }


def detect_multiskip_jumps(
    domain: GridDomain,
    records: dict[str, dict],
) -> list[dict]:
    """Adjacent-point skip-count jumps with |a - b| > 1 (F2 §28).

    Warning only -- not a numerical failure -- but P0 refinement priority
    for F3: the coarse grid may have skipped an intermediate regime.
    """
    jumps: list[dict] = []

    def _skip(rec: dict) -> int | None:
        return rec["sanger"].get("skip_count")

    # Rows (fixed gamma, adjacent K).
    for g in domain.gamma_grid:
        for k_a, k_b in zip(domain.k_grid, domain.k_grid[1:]):
            ra = records.get(cache_key(ParameterPoint(g, k_a)))
            rb = records.get(cache_key(ParameterPoint(g, k_b)))
            if ra is None or rb is None:
                continue
            sa, sb = _skip(ra), _skip(rb)
            if sa is not None and sb is not None and abs(sa - sb) > 1:
                jumps.append({
                    "direction": "K",
                    "gamma0": g,
                    "K_left": k_a,
                    "K_right": k_b,
                    "left_skip": sa,
                    "right_skip": sb,
                })
    # Columns (fixed K, adjacent gamma).
    for k in domain.k_grid:
        for g_a, g_b in zip(domain.gamma_grid, domain.gamma_grid[1:]):
            ra = records.get(cache_key(ParameterPoint(g_a, k)))
            rb = records.get(cache_key(ParameterPoint(g_b, k)))
            if ra is None or rb is None:
                continue
            sa, sb = _skip(ra), _skip(rb)
            if sa is not None and sb is not None and abs(sa - sb) > 1:
                jumps.append({
                    "direction": "gamma",
                    "K": k,
                    "gamma_left": g_a,
                    "gamma_right": g_b,
                    "left_skip": sa,
                    "right_skip": sb,
                })
    return jumps


def priority_cells(
    cells: list[dict],
    multiskip: list[dict],
    margin_hint_cells: list[dict],
) -> list[dict]:
    """Sort candidate cells into the F3 refinement queue (F2 §56).

    P0 = multiskip-jump cells; P1 = compact regime transition;
    P2 = exact-topology-only transition; P3 = margin near-zero hint
    without any label transition (ordered by observed min margin, no
    arbitrary threshold).
    """
    jump_cells = {
        (c["gamma_min"], c["gamma_max"], c["K_min"], c["K_max"])
        for c in _cells_touched_by_jumps(cells, multiskip)
    }
    queue: list[dict] = []
    for cell in cells:
        key = (cell["gamma_min"], cell["gamma_max"],
               cell["K_min"], cell["K_max"])
        if key in jump_cells:
            entry = {**cell, "priority": "P0"}
        elif any(r.startswith(("qian_", "sanger_", "joint_"))
                 for r in cell["candidate_reasons"]):
            entry = {**cell, "priority": "P1"}
        elif cell["exact_topology_only"]:
            entry = {**cell, "priority": "P2"}
        else:
            entry = {**cell, "priority": "P3"}
        queue.append(entry)
    queued_keys = {
        (q["gamma_min"], q["gamma_max"], q["K_min"], q["K_max"])
        for q in queue
    }
    queue.extend(
        {**c, "priority": "P3"}
        for c in margin_hint_cells
        if (c["gamma_min"], c["gamma_max"], c["K_min"], c["K_max"])
        not in queued_keys
    )
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(queue, key=lambda c: order.get(c["priority"], 9))


def _cells_touched_by_jumps(cells: list[dict], jumps: list[dict]) -> list[dict]:
    """Cells that contain at least one multiskip adjacent pair."""
    touched: list[dict] = []
    for cell in cells:
        g0, g1 = cell["gamma_min"], cell["gamma_max"]
        k0, k1 = cell["K_min"], cell["K_max"]
        for j in jumps:
            if j["direction"] == "K" and j["gamma0"] == g0:
                if (j["K_left"] == k0 and j["K_right"] == k1) or (
                    j["K_left"] == k1 and j["K_right"] == k0
                ):
                    touched.append(cell)
                    break
            if j["direction"] == "gamma" and j["K"] == k0:
                if (j["gamma_left"] == g0 and j["gamma_right"] == g1) or (
                    j["gamma_left"] == g1 and j["gamma_right"] == g0
                ):
                    touched.append(cell)
                    break
    return touched


# ---------------------------------------------------------------------------
# Domain expansion (F2 §37–§42, F0 §9)
# ---------------------------------------------------------------------------
def plan_expansion(
    cells: list[dict],
    domain: GridDomain,
) -> dict[str, bool]:
    """Expand a side ONLY if a candidate cell touches that domain edge.

    Small margins alone never trigger expansion (edge hint only).
    """
    flags = {
        "expand_gamma_lower": False,
        "expand_gamma_upper": False,
        "expand_K_lower": False,
        "expand_K_upper": False,
    }
    for cell in cells:
        if not cell["candidate"]:
            continue
        if cell["touches_gamma_lower"]:
            flags["expand_gamma_lower"] = True
        if cell["touches_gamma_upper"]:
            flags["expand_gamma_upper"] = True
        if cell["touches_K_lower"]:
            flags["expand_K_lower"] = True
        if cell["touches_K_upper"]:
            flags["expand_K_upper"] = True
    return flags


def expand_domain(
    domain: GridDomain,
    flags: dict[str, bool],
) -> tuple[GridDomain, tuple[ParameterPoint, ...]]:
    """Expand the touched sides by the F0 increments (spacing preserved).

    Returns the new domain and the NEW unique grid points that must be
    integrated (existing points are never re-integrated).
    """
    g_min, g_max = domain.gamma_min, domain.gamma_max
    k_min, k_max = domain.k_min, domain.k_max

    if flags.get("expand_gamma_lower"):
        g_min = max(g_min - GAMMA_EXPAND_WIDTH_DEG, GAMMA_GUARDRAIL[0])
    if flags.get("expand_gamma_upper"):
        g_max = min(g_max + GAMMA_EXPAND_WIDTH_DEG, GAMMA_GUARDRAIL[1])
    if flags.get("expand_K_lower"):
        k_min = max(k_min - K_EXPAND_WIDTH, K_GUARDRAIL[0])
    if flags.get("expand_K_upper"):
        k_max = min(k_max + K_EXPAND_WIDTH, K_GUARDRAIL[1])

    new_domain = GridDomain(g_min, g_max, k_min, k_max)
    old_keys = {cache_key(p) for p in grid_points(domain)}
    new_points = tuple(
        p for p in grid_points(new_domain) if cache_key(p) not in old_keys
    )
    return new_domain, new_points


def open_boundary_states(
    domain: GridDomain,
    cells: list[dict],
) -> list[str]:
    """OPEN_BOUNDARY when a candidate cell still touches a guardrail edge."""
    states: list[str] = []
    if domain.gamma_min <= GAMMA_GUARDRAIL[0] + 1e-12:
        if any(c["candidate"] and c["touches_gamma_lower"] for c in cells):
            states.append("gamma_lower")
    if domain.gamma_max >= GAMMA_GUARDRAIL[1] - 1e-12:
        if any(c["candidate"] and c["touches_gamma_upper"] for c in cells):
            states.append("gamma_upper")
    if domain.k_min <= K_GUARDRAIL[0] + 1e-12:
        if any(c["candidate"] and c["touches_K_lower"] for c in cells):
            states.append("K_lower")
    if domain.k_max >= K_GUARDRAIL[1] - 1e-12:
        if any(c["candidate"] and c["touches_K_upper"] for c in cells):
            states.append("K_upper")
    return states


# ---------------------------------------------------------------------------
# Coarse boundary brackets (F2 §30–§31)
# ---------------------------------------------------------------------------
def boundary_brackets(
    domain: GridDomain,
    records: dict[str, dict],
    axis: str,
) -> list[dict]:
    """Sampled brackets along one axis (never interpolation).

    axis="gamma": fixed gamma rows, adjacent K columns; axis="K": fixed K
    columns, adjacent gamma rows.  Fires on compact OR exact-topology
    change between adjacent sampled points.
    """
    brackets: list[dict] = []

    def _changed(ra: dict, rb: dict) -> bool:
        return (
            ra["qian"]["qian_regime"] != rb["qian"]["qian_regime"]
            or ra["sanger"]["sanger_regime"] != rb["sanger"]["sanger_regime"]
            or ra["qian"]["exact_topology_signature"]
            != rb["qian"]["exact_topology_signature"]
            or ra["sanger"]["exact_topology_signature"]
            != rb["sanger"]["exact_topology_signature"]
        )

    if axis == "gamma":
        for g in domain.gamma_grid:
            for k_a, k_b in zip(domain.k_grid, domain.k_grid[1:]):
                ra = records.get(cache_key(ParameterPoint(g, k_a)))
                rb = records.get(cache_key(ParameterPoint(g, k_b)))
                if ra is None or rb is None:
                    continue
                if _changed(ra, rb):
                    brackets.append({
                        "gamma0": g,
                        "K_left": k_a,
                        "K_right": k_b,
                        "left_sanger_regime": ra["sanger"]["sanger_regime"],
                        "right_sanger_regime": rb["sanger"]["sanger_regime"],
                        "left_qian_regime": ra["qian"]["qian_regime"],
                        "right_qian_regime": rb["qian"]["qian_regime"],
                    })
    elif axis == "K":
        for k in domain.k_grid:
            for g_a, g_b in zip(domain.gamma_grid, domain.gamma_grid[1:]):
                ra = records.get(cache_key(ParameterPoint(g_a, k)))
                rb = records.get(cache_key(ParameterPoint(g_b, k)))
                if ra is None or rb is None:
                    continue
                if _changed(ra, rb):
                    brackets.append({
                        "K": k,
                        "gamma_left": g_a,
                        "gamma_right": g_b,
                        "left_sanger_regime": ra["sanger"]["sanger_regime"],
                        "right_sanger_regime": rb["sanger"]["sanger_regime"],
                        "left_qian_regime": ra["qian"]["qian_regime"],
                        "right_qian_regime": rb["qian"]["qian_regime"],
                    })
    else:
        raise ValueError(f"Unknown bracket axis: {axis!r}")
    return brackets


# ---------------------------------------------------------------------------
# Categorical matrices (F2 §24–§25)
# ---------------------------------------------------------------------------
def build_categorical_matrices(
    domain: GridDomain,
    records: dict[str, dict],
) -> dict:
    """17×17 (or expanded) categorical matrices; labels always retained.

    ``exact_topology_id_matrix`` uses deterministic integer IDs; the
    mapping ``id -> joint exact signature`` is stored so the labels are
    never lost.
    """
    g_grid = list(domain.gamma_grid)
    k_grid = list(domain.k_grid)
    n_g, n_k = len(g_grid), len(k_grid)

    qian_regime = [[""] * n_k for _ in range(n_g)]
    sanger_regime = [[""] * n_k for _ in range(n_g)]
    skip_count = [[None] * n_k for _ in range(n_g)]
    joint_regime = [[["", ""] for _ in range(n_k)] for _ in range(n_g)]
    exact_sig = [[""] * n_k for _ in range(n_g)]

    for i_g, g in enumerate(g_grid):
        for i_k, k in enumerate(k_grid):
            rec = records.get(cache_key(ParameterPoint(g, k)))
            if rec is None:
                continue
            qian_regime[i_g][i_k] = rec["qian"]["qian_regime"]
            sanger_regime[i_g][i_k] = rec["sanger"]["sanger_regime"]
            skip_count[i_g][i_k] = rec["sanger"].get("skip_count")
            joint_regime[i_g][i_k] = list(rec["joint_regime"])
            exact_sig[i_g][i_k] = rec["joint_exact_topology_signature"]

    unique_sigs = sorted({s for row in exact_sig for s in row if s})
    id_map = {sig: i for i, sig in enumerate(unique_sigs)}
    exact_id = [
        [id_map[s] if s else None for s in row] for row in exact_sig
    ]

    return {
        "gamma_grid": g_grid,
        "K_grid": k_grid,
        "qian_regime_matrix": qian_regime,
        "sanger_regime_matrix": sanger_regime,
        "skip_count_matrix": skip_count,
        "joint_regime_matrix": joint_regime,
        "exact_topology_id_matrix": exact_id,
        "exact_topology_id_map": id_map,
        "categorical_ids_are_visualization_only": True,
    }


# ---------------------------------------------------------------------------
# Health / invariant checks (F2 §21–§23)
# ---------------------------------------------------------------------------
def skip_count_consistency_violations(records: dict[str, dict]) -> list[str]:
    """SRTI_N{k} must correspond to the 2k+1 segment structure (F2 §22)."""
    violations: list[str] = []
    for key, rec in records.items():
        s = rec["sanger"]
        if s["terminal_kind"] == "srti":
            skip = s["skip_count"]
            n_modes = len(s["mode_sequence"])
            if n_modes != 2 * skip + 1:
                violations.append(
                    f"{key}: SRTI_N{skip} has {n_modes} modes "
                    f"(expected {2 * skip + 1}).")
    return violations


def exit_transversality_violations(records: dict[str, dict]) -> list[str]:
    """Every atmosphere-exit must satisfy dh/dt > 0 (F2 §23)."""
    violations: list[str] = []
    for key, rec in records.items():
        dhdt = rec["sanger"].get("exit_dhdt_mps") or []
        for i, v in enumerate(dhdt):
            if v is not None and v <= 0.0:
                violations.append(
                    f"{key}: exit {i} dh/dt = {v} <= 0.")
    return violations


def f1_consistency_check(records: dict[str, dict]) -> dict:
    """Extract the F1 slices from the F2 grid and compare (F2 §66).

    Uses the F0-frozen F1 slice parameters (K=3 gamma slice over
    GAMMA_SLICE_DEG; gamma0=-5 K slice over K_SLICE) and the F1 tracked
    compact regime sequences.  A mismatch is a HARD STOP (never silently
    rewrite the historical F1 report).
    """
    result = {"pass": True, "checks": {}}

    def _row_sanger(g: float) -> str:
        rec = records.get(cache_key(ParameterPoint(g, ANCHOR_K)))
        return rec["sanger"]["sanger_regime"] if rec else None

    def _col_sanger(k: float) -> str:
        rec = records.get(cache_key(ParameterPoint(ANCHOR_GAMMA0_DEG, k)))
        return rec["sanger"]["sanger_regime"] if rec else None

    gamma_actual = [_row_sanger(g) for g in GAMMA_SLICE_DEG]
    ok = gamma_actual == list(GAMMA_SLICE_F1_SANGER)
    result["checks"]["gamma_slice"] = {
        "pass": ok, "actual": gamma_actual,
        "expected": list(GAMMA_SLICE_F1_SANGER)}
    result["pass"] &= ok

    k_actual = [_col_sanger(k) for k in K_SLICE]
    ok = k_actual == list(K_SLICE_F1_SANGER)
    result["checks"]["k_slice"] = {
        "pass": ok, "actual": k_actual,
        "expected": list(K_SLICE_F1_SANGER)}
    result["pass"] &= ok

    slice_keys = [
        cache_key(ParameterPoint(g, ANCHOR_K)) for g in GAMMA_SLICE_DEG
    ] + [
        cache_key(ParameterPoint(ANCHOR_GAMMA0_DEG, k)) for k in K_SLICE
    ]
    qian_all_rti = all(
        records[k]["qian"]["qian_regime"] == "QIAN_RTI"
        for k in slice_keys if k in records
    )
    result["checks"]["qian_uniform_rti_on_f1_slices"] = {
        "pass": qian_all_rti, "actual": qian_all_rti, "expected": True}
    result["pass"] &= qian_all_rti
    return result
