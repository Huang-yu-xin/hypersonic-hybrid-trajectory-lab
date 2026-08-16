"""Phase-F fixed-topology structural sensitivity mapping (F5).

F5 — Fixed-Topology Structural Sensitivity Mapping
(docs/phase_f/f5_structural_sensitivity.md).

Canonical-center derivative map over the F2 33x33 grid, using the F4
frozen derivative machinery as the single source of truth:

* canonical centers are exactly the F2 canonical grid points (no uniform
  dense upsampling -- F3 owns boundary refinement);
* model-specific masks: Qian eligibility never depends on the Sanger
  grazing geometry (only Qian exact topology + guardrail + validity);
  Sanger eligibility additionally enforces the F3 exclusion geometry,
  exact Sanger topology, and the recovered-event exclusion;
* global-step-first: h_gamma = 0.1 deg and h_K = 0.025 with the F4
  h/2 plateau audit map-wide; ADAPTIVE_STEP_POLICY fallback
  (largest-safe-converged central step) where the global step fails;
* statuses: GLOBAL_ACCEPTED / ADAPTIVE_ACCEPTED / BOUNDARY_INTERSECTION /
  TOPOLOGY_CHANGE / RECOVERED_EVENT_EXCLUDED /
  GUARDRAIL_CENTRAL_UNAVAILABLE / NO_SAFE_STENCIL / NO_CONVERGENCE /
  INVALID; categorical, never interpolated;
* canonical storage per radian (gamma) and per unit K; visualization
  may convert to per-degree with explicit captions.

No STM / saltation / FTLE / optimization / Phase-E B/C/D surfaces /
topology derivatives / boundary fitting.
"""

from dataclasses import dataclass

import numpy as np

from hyptraj.analysis.sensitivity_fd import (
    GAMMA_STEPS_DEG,
    GAMMA_STEPS_DEG_EXTRA,
    K_STEPS,
    K_STEPS_EXTRA,
    QIAN_OUTPUTS,
    SANGER_OUTPUTS,
    central_difference_K,
    central_difference_gamma,
    evaluate_stencil,
    qian_output_vector,
    sanger_output_vector,
    successive_differences,
)
from hyptraj.analysis.sensitivity_grid import (
    GAMMA_GUARDRAIL,
    K_GUARDRAIL,
    cache_key,
)
from hyptraj.analysis.sensitivity_pilot import ParameterPoint

# F4 frozen global steps.
GLOBAL_GAMMA_STEP_DEG = 0.1
GLOBAL_K_STEP = 0.025

# Adaptive candidate sequences (F4 §13 + F5 §8; K=0.0015625 is the last
# resort fallback candidate, reported separately when used).
ADAPTIVE_GAMMA_STEPS = GAMMA_STEPS_DEG + GAMMA_STEPS_DEG_EXTRA
ADAPTIVE_K_STEPS = K_STEPS + K_STEPS_EXTRA + (0.0015625,)

# Status vocabulary (F5 §24).
STATUS_GLOBAL_ACCEPTED = "GLOBAL_ACCEPTED"
STATUS_ADAPTIVE_ACCEPTED = "ADAPTIVE_ACCEPTED"
STATUS_BOUNDARY_INTERSECTION = "BOUNDARY_INTERSECTION"
STATUS_TOPOLOGY_CHANGE = "TOPOLOGY_CHANGE"
STATUS_RECOVERED_EVENT_EXCLUDED = "RECOVERED_EVENT_EXCLUDED"
STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE = "GUARDRAIL_CENTRAL_UNAVAILABLE"
STATUS_NO_SAFE_STENCIL = "NO_SAFE_STENCIL"
STATUS_NO_CONVERGENCE = "NO_CONVERGENCE"
STATUS_INVALID = "INVALID"
STATUS_REFERENCE_AUDIT_FAILED = "REFERENCE_AUDIT_FAILED"

# F4 negligible-output thresholds used as the near-zero floor for the
# sign structure (F4 policy, dimension-aware; documented).
NEAR_ZERO_FLOOR_GAMMA = 1e-3   # per radian
NEAR_ZERO_FLOOR_K = 1e-2       # per unit K


@dataclass(frozen=True)
class DerivativeResult:
    """One model/parameter derivative evaluation at a canonical center."""

    status: str
    step_used: float | None
    derivatives: dict[str, float] | None   # output -> canonical value
    reason: tuple[str, ...] = ()


def _stencil_points(g0: float, k0: float, param: str, h: float):
    if param == "gamma":
        return (g0 - h, k0), (g0 + h, k0)
    return (g0, k0 - h), (g0, k0 + h)


def _gate(
    center_rec: dict,
    plus_rec: dict,
    minus_rec: dict,
    center: tuple[float, float],
    plus: tuple[float, float],
    minus: tuple[float, float],
    model: str,
    exclusion_cells: list[dict],
    use_geometry: bool,
) -> tuple[bool, tuple[str, ...]]:
    """Model-specific gate.

    ``use_geometry`` = False for Qian (Sanger exclusion geometry must
    never mask the Qian derivative field, F5 §5); True for Sanger.
    """
    cells = exclusion_cells if use_geometry else []
    el = evaluate_stencil(
        center_rec, plus_rec, minus_rec, center, plus, minus,
        cells, model)
    return el.eligible, el.reasons


def _status_from_reasons(reasons: tuple[str, ...]) -> str:
    if not reasons:
        return STATUS_GLOBAL_ACCEPTED
    if any(r.startswith("OUTSIDE_DOMAIN") for r in reasons):
        return STATUS_GUARDRAIL_CENTRAL_UNAVAILABLE
    if any(r.startswith("BOUNDARY_INTERSECTION") for r in reasons):
        return STATUS_BOUNDARY_INTERSECTION
    if any(r.startswith("TOPOLOGY_CHANGE") for r in reasons):
        return STATUS_TOPOLOGY_CHANGE
    if any(r.startswith("RECOVERED_EVENT") for r in reasons):
        return STATUS_RECOVERED_EVENT_EXCLUDED
    if any(r.startswith("INVALID_NEIGHBOR") for r in reasons):
        return STATUS_INVALID
    return STATUS_NO_SAFE_STENCIL


def _central_derivative(
    plus_rec: dict,
    minus_rec: dict,
    param: str,
    h: float,
    model: str,
) -> dict[str, float] | None:
    vector_of = qian_output_vector if model == "qian" else sanger_output_vector
    outputs = QIAN_OUTPUTS if model == "qian" else SANGER_OUTPUTS
    yp = vector_of(plus_rec[model])
    ym = vector_of(minus_rec[model])
    if yp is None or ym is None:
        return None
    out = {}
    for i, name in enumerate(outputs):
        if param == "gamma":
            out[name] = central_difference_gamma(yp[i], ym[i], h)
        else:
            out[name] = central_difference_K(yp[i], ym[i], h)
    return out


def _plateau_ok(
    d_h: dict[str, float] | None,
    d_half: dict[str, float] | None,
    param: str,
) -> bool:
    """F4 relative plateau criterion over all non-negligible outputs."""
    if d_h is None or d_half is None:
        return False
    floor = NEAR_ZERO_FLOOR_GAMMA if param == "gamma" else NEAR_ZERO_FLOOR_K
    for name in d_h:
        ref = abs(d_half[name])
        if ref < floor:
            continue  # negligible output: not a criterion
        if abs(d_h[name] - d_half[name]) > 0.01 * ref:
            return False
    return True


def evaluate_map_derivative(
    g0: float,
    k0: float,
    param: str,
    model: str,
    center_rec: dict,
    point_lookup: dict,
    exclusion_cells: list[dict],
    use_geometry: bool,
) -> DerivativeResult:
    """Global-step-first map derivative with adaptive fallback (F5 §7–§11).

    ``point_lookup`` maps cache_key(g, k) -> record (production solver).
    The global step is tried first with its h/2 plateau audit; on gate or
    plateau failure the adaptive sequence is scanned from large to small,
    selecting the largest safe converged step.
    """
    steps = (ADAPTIVE_GAMMA_STEPS if param == "gamma"
             else ADAPTIVE_K_STEPS)
    global_h = (GLOBAL_GAMMA_STEP_DEG if param == "gamma"
                else GLOBAL_K_STEP)
    center = (g0, k0)

    # ---- Global step first (F5 §6–§7) -------------------------------------
    minus, plus = _stencil_points(g0, k0, param, global_h)
    m_rec = point_lookup.get(cache_key(ParameterPoint(*minus)))
    p_rec = point_lookup.get(cache_key(ParameterPoint(*plus)))
    if m_rec is not None and p_rec is not None:
        ok, reasons = _gate(
            center_rec, p_rec, m_rec, center, plus, minus,
            model, exclusion_cells, use_geometry)
        if ok:
            # h/2 plateau audit.
            h_half = global_h / 2.0
            minus2, plus2 = _stencil_points(g0, k0, param, h_half)
            m2 = point_lookup.get(cache_key(ParameterPoint(*minus2)))
            p2 = point_lookup.get(cache_key(ParameterPoint(*plus2)))
            if m2 is not None and p2 is not None:
                ok2, _ = _gate(
                    center_rec, p2, m2, center, plus2, minus2,
                    model, exclusion_cells, use_geometry)
                if ok2:
                    d_h = _central_derivative(p_rec, m_rec, param,
                                              global_h, model)
                    d_half = _central_derivative(p2, m2, param,
                                                 h_half, model)
                    if _plateau_ok(d_h, d_half, param):
                        return DerivativeResult(
                            STATUS_GLOBAL_ACCEPTED, global_h, d_h)

    # ---- Adaptive fallback (F5 §8–§9) --------------------------------------
    for h in steps:
        if h == global_h:
            continue
        minus, plus = _stencil_points(g0, k0, param, h)
        m_rec = point_lookup.get(cache_key(ParameterPoint(*minus)))
        p_rec = point_lookup.get(cache_key(ParameterPoint(*plus)))
        if m_rec is None or p_rec is None:
            continue
        ok, reasons = _gate(
            center_rec, p_rec, m_rec, center, plus, minus,
            model, exclusion_cells, use_geometry)
        if not ok:
            continue
        # Find the next smaller eligible step for the plateau check.
        idx = steps.index(h)
        smaller = None
        for h2 in steps[idx + 1:]:
            m2 = point_lookup.get(cache_key(ParameterPoint(*(
                _stencil_points(g0, k0, param, h2)[0]))))
            p2 = point_lookup.get(cache_key(ParameterPoint(*(
                _stencil_points(g0, k0, param, h2)[1]))))
            if m2 is None or p2 is None:
                continue
            ok2, _ = _gate(
                center_rec, p2, m2, center,
                _stencil_points(g0, k0, param, h2)[1],
                _stencil_points(g0, k0, param, h2)[0],
                model, exclusion_cells, use_geometry)
            if ok2:
                smaller = (h2, m2, p2)
                break
        if smaller is None:
            continue
        h2, m2, p2 = smaller
        d_h = _central_derivative(p_rec, m_rec, param, h, model)
        d_half = _central_derivative(p2, m2, param, h2, model)
        if _plateau_ok(d_h, d_half, param):
            return DerivativeResult(STATUS_ADAPTIVE_ACCEPTED, h, d_h)

    # ---- No convergence / no safe stencil ---------------------------------
    # Distinguish: any gate-passed step exists but no plateau?
    any_gate_pass = False
    final_reasons: tuple[str, ...] = ()
    for h in steps:
        minus, plus = _stencil_points(g0, k0, param, h)
        m_rec = point_lookup.get(cache_key(ParameterPoint(*minus)))
        p_rec = point_lookup.get(cache_key(ParameterPoint(*plus)))
        if m_rec is None or p_rec is None:
            continue
        ok, reasons = _gate(
            center_rec, p_rec, m_rec, center, plus, minus,
            model, exclusion_cells, use_geometry)
        if ok:
            any_gate_pass = True
        elif not final_reasons:
            final_reasons = reasons
    if any_gate_pass:
        return DerivativeResult(STATUS_NO_CONVERGENCE, None, None)
    if final_reasons:
        return DerivativeResult(
            _status_from_reasons(final_reasons), None, None, final_reasons)
    return DerivativeResult(STATUS_NO_SAFE_STENCIL, None, None)


# ---------------------------------------------------------------------------
# Deterministic reference-audit sample selection (F5 §26, §56)
# ---------------------------------------------------------------------------
def select_reference_audit_sample(
    map_records: list[dict],
    reps_baseline: tuple[float, float] = (-5.0, 3.0),
) -> list[dict]:
    """Deterministic stratified sample (no random sampling).

    Rule (documented): baseline; per Sanger regime the 3 interior centers
    with the deepest exclusion clearance, the lowest eligible gamma0 and
    the highest eligible gamma0 (deduplicated); plus the per-regime
    extremal |dR/dgamma| and min/max signed dR/dgamma points (dedup);
    plus every ADAPTIVE_ACCEPTED center (cap 30 via deterministic
    lexicographic spread if exceeded).
    """
    selected: dict[tuple[float, float], dict] = {}

    def _add(rec: dict) -> None:
        selected[(rec["gamma0_deg"], rec["K"])] = rec

    # Baseline.
    for rec in map_records:
        if (rec["gamma0_deg"], rec["K"]) == reps_baseline:
            _add(rec)
            break

    regimes = sorted({rec["sanger_regime"] for rec in map_records
                      if rec["sanger_regime"]})
    for regime in regimes:
        reg = [r for r in map_records if r["sanger_regime"] == regime]
        eligible = [r for r in reg
                    if r["sanger"]["gamma"]["status"]
                    in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)
                    or r["sanger"]["K"]["status"]
                    in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)]
        if not eligible:
            eligible = [r for r in reg if r["sanger"]["gamma"]["status"]
                        not in (STATUS_NO_SAFE_STENCIL,)]
        # deepest clearance, lowest gamma, highest gamma.
        by_clearance = sorted(
            eligible, key=lambda r: r["selection_clearance"], reverse=True)
        by_gamma = sorted(eligible, key=lambda r: r["gamma0_deg"])
        for rec in (by_clearance[0], by_gamma[0], by_gamma[-1]):
            _add(rec)
        # Extremal dR/dgamma (any valid derivative).
        dvals = [
            (r["sanger"]["gamma"].get("derivatives", {})
             .get("sanger_srti_range_m"), r)
            for r in eligible
            if r["sanger"]["gamma"]["status"]
            in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)
        ]
        dvals = [(d, r) for d, r in dvals if d is not None]
        if dvals:
            _add(max(dvals, key=lambda t: abs(t[0]))[1])
            _add(min(dvals, key=lambda t: t[0])[1])
            _add(max(dvals, key=lambda t: t[0])[1])

    # Adaptive points.
    adaptive = [r for r in map_records
                if r["sanger"]["gamma"]["status"] == STATUS_ADAPTIVE_ACCEPTED
                or r["sanger"]["K"]["status"] == STATUS_ADAPTIVE_ACCEPTED]
    if len(adaptive) <= 30:
        for rec in adaptive:
            _add(rec)
    else:
        # Deterministic lexicographic spread: every 30th sorted point.
        ordered = sorted(adaptive, key=lambda r: (r["gamma0_deg"], r["K"]))
        for i in range(0, len(ordered), max(1, len(ordered) // 30)):
            _add(ordered[i])

    return [selected[k] for k in sorted(selected)]


# ---------------------------------------------------------------------------
# Regime statistics (F5 §30–§31)
# ---------------------------------------------------------------------------
def regime_statistics(
    map_records: list[dict],
    model: str,
    output: str,
    param: str,
) -> dict:
    """Descriptive statistics per Sanger regime (or whole-domain for Qian).

    Only GLOBAL_ACCEPTED / ADAPTIVE_ACCEPTED derivatives enter.  ``param``
    is "gamma" or "K"; map records follow the F5 schema
    ``rec[model][param] = {"status", "step_used", "derivatives"}``.
    """
    stats: dict = {}
    if model == "qian":
        vals = [
            r["qian"][param]["derivatives"][output]
            for r in map_records
            if r["qian"][param]["status"]
            in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)
            and r["qian"][param]["derivatives"] is not None
        ]
        stats["whole-domain"] = _stats_block(vals, param)
        return stats
    for regime in sorted({r["sanger_regime"] for r in map_records}):
        vals = [
            r["sanger"][param]["derivatives"][output]
            for r in map_records
            if r["sanger_regime"] == regime
            and r["sanger"][param]["status"]
            in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)
            and r["sanger"][param]["derivatives"] is not None
        ]
        stats[regime] = _stats_block(vals, param)
    return stats


def _stats_block(vals: list[float], param: str) -> dict:
    floor = NEAR_ZERO_FLOOR_GAMMA if param == "gamma" else NEAR_ZERO_FLOOR_K
    arr = np.asarray(vals, dtype=float)
    if arr.size == 0:
        return {"count": 0, "min": None, "median": None, "max": None,
                "q25": None, "q75": None,
                "sign": {"positive": 0, "negative": 0, "near_zero": 0}}
    return {
        "count": int(arr.size),
        "min": float(arr.min()),
        "median": float(np.median(arr)),
        "max": float(arr.max()),
        "q25": float(np.percentile(arr, 25)),
        "q75": float(np.percentile(arr, 75)),
        "sign": {
            "positive": int(np.sum(arr > floor)),
            "negative": int(np.sum(arr < -floor)),
            "near_zero": int(np.sum(np.abs(arr) <= floor)),
        },
    }


def within_regime_sign_change(
    stats: dict,
) -> list[str]:
    """Regimes with both clear positive and negative derivatives."""
    out = []
    for regime, block in stats.items():
        sign = block.get("sign", {})
        if sign.get("positive", 0) > 0 and sign.get("negative", 0) > 0:
            out.append(regime)
    return out


# ---------------------------------------------------------------------------
# Field-health diagnostic (F5 §34–§35)
# ---------------------------------------------------------------------------
def field_health(
    map_records: list[dict],
    model: str,
    output: str,
    param: str,
    jump_factor: float = 5.0,
) -> dict:
    """Adjacent-derivative jump audit within same exact topology.

    Marks adjacent canonical centers (grid neighbours) whose valid
    derivatives differ by more than ``jump_factor`` relative to the
    larger magnitude -- a field-health diagnostic, NOT a second
    derivative (F5 §34).  Flagged pairs enter the reference audit.
    """
    valid = [
        r for r in map_records
        if r[model][param]["status"]
        in (STATUS_GLOBAL_ACCEPTED, STATUS_ADAPTIVE_ACCEPTED)
        and r[model][param]["derivatives"] is not None
    ]
    by_key = {(r["gamma0_deg"], r["K"]): r for r in valid}
    key_sig = f"{model}_exact_topology"
    jumps = []
    for rec in valid:
        g, k = rec["gamma0_deg"], rec["K"]
        for dg, dk in ((0.25, 0.0), (0.0, 0.125)):
            nb = by_key.get((g + dg, k + dk))
            if nb is None:
                continue
            if rec[key_sig] != nb[key_sig]:
                continue  # different exact topology: not a field jump
            a = rec[model][param]["derivatives"].get(output)
            b = nb[model][param]["derivatives"].get(output)
            if a is None or b is None:
                continue
            denom = max(abs(a), abs(b))
            if denom <= 0:
                continue
            if abs(a - b) > jump_factor * denom:
                jumps.append({
                    "point_a": [g, k],
                    "point_b": [g + dg, k + dk],
                    "derivative_a": a,
                    "derivative_b": b,
                    "relative_jump": abs(a - b) / denom,
                })
    return {"jump_count": len(jumps), "jumps": jumps}
