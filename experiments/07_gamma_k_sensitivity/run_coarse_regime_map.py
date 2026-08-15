"""F2 runner -- deterministic Cartesian coarse gamma0-K hybrid-regime map.

Autonomous long run: 17×17 = 289 initial paired points (Qian + Sanger),
resumable jsonl point cache, boundary candidate-cell extraction,
conditional F0 domain expansion (only when candidate cells touch a domain
edge), coarse boundary brackets and the F3 handoff queue.

    PHASE F — F2 COARSE GAMMA0-K HYBRID REGIME MAP
    AUTONOMOUS LONG RUN
    DETERMINISTIC CARTESIAN GRID
    NOT A DERIVATIVE STUDY
    NOT AN OPTIMIZATION STUDY

Artifacts (untracked): results/gamma_k_sensitivity/coarse_map/
"""

import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from hyptraj.analysis.sensitivity_grid import (
    F2_POINT_SCHEMA,
    F2_SUMMARY_SCHEMA,
    F1_COMMIT,
    GridDomain,
    append_cache_record,
    baseline_grid_index,
    boundary_brackets,
    build_categorical_matrices,
    cache_key,
    detect_boundary_cells,
    detect_multiskip_jumps,
    exit_transversality_violations,
    expand_domain,
    f1_consistency_check,
    grid_points,
    initial_domain,
    load_point_cache,
    make_point_record,
    open_boundary_states,
    plan_expansion,
    priority_cells,
    skip_count_consistency_violations,
    validate_cache_record,
)
from hyptraj.analysis.sensitivity_pilot import (
    PHASE_E_ANCHOR_TAG,
    QIAN_MAX_TIME_S,
    SANGER_MAX_SEGMENTS,
    SANGER_MAX_TIME_S,
    ParameterPoint,
    audit_point_health,
    collect_stop_gate_reasons,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

OUT_DIR = Path("results/gamma_k_sensitivity/coarse_map")
CACHE_PATH = OUT_DIR / "point_cache.jsonl"
REFERENCE_PATH = Path("tests/data/qian_sanger_comparison_v1.json")


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _solver_dict() -> dict:
    cfg = PRODUCTION_SOLVER_CONFIG
    return {
        "method": cfg.method,
        "rtol": cfg.rtol,
        "atol": [float(a) for a in cfg.atol],
        "max_step": cfg.max_step,
        "dense_output": cfg.dense_output,
    }


def _expected_provenance(git_commit: str, domain: GridDomain) -> dict:
    return {
        "schema_version": F2_POINT_SCHEMA,
        "phase_e_anchor_commit": "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc",
        "phase_f_protocol_commit": "1cd0bd52de0d9cec615635949d2805525619d370",
        "phase_f_f01_commit": "81b3a9980c0df548786db4145f4e01c917cba1e4",
        "phase_f_f1_commit": F1_COMMIT,
        "solver_config": _solver_dict(),
        "domain": domain.as_dict(),
    }


def _load_valid_cache(domain: GridDomain, git_commit: str) -> dict:
    """Load reusable cache records (provenance-validated)."""
    raw = load_point_cache(CACHE_PATH)
    expected = _expected_provenance(git_commit, domain)
    valid: dict[str, dict] = {}
    rejected = 0
    for key, record in raw.items():
        ok, _ = validate_cache_record(record, expected)
        if ok:
            valid[key] = record
        else:
            rejected += 1
    if rejected:
        print(f"[cache] rejected {rejected} provenance-mismatched record(s)")
    return valid


def _progress_line(i: int, total: int, pr, ms: float, ma: float | None) -> str:
    s = pr.sanger_row
    ms_s = "NA" if ms is None else f"{ms / 1000.0:.3f}"
    ma_s = "NA" if ma is None else f"{ma / 1000.0:.3f}"
    return (
        f"[{i:03d}/{total}] "
        f"gamma0={pr.parameter.gamma0_deg:.2f} "
        f"K={pr.parameter.K:.3f} "
        f"Qian={pr.qian_row['qian_regime']} "
        f"Sanger={s['sanger_regime']} "
        f"skip={s.get('skip_count') if s.get('skip_count') is not None else 'NA'} "
        f"M_S={ms_s} km minM_A={ma_s} km"
    )


def _cell_min_margin(cell: dict, records: dict) -> float | None:
    values: list[float] = []
    for c in cell["corners"]:
        g, k = c["parameter"]
        rec = records.get(cache_key(ParameterPoint(g, k)))
        if rec is None:
            continue
        ms = rec["sanger"].get("M_S_clearance_m")
        if ms is not None:
            values.append(ms)
        else:
            ma = rec["sanger"].get("M_A_clearance_m") or []
            if ma:
                values.append(min(ma))
    return min(values) if values else None


def _margin_hint_cells(
    cells: list[dict], records: dict
) -> list[dict]:
    """Non-candidate cells ranked by observed minimum corner margin (P3).

    Pure ranking, no arbitrary threshold (F2 §56).
    """
    hints = [
        {**cell, "min_margin_km": _cell_min_margin(cell, records) / 1000.0}
        for cell in cells
        if not cell["candidate"] and _cell_min_margin(cell, records) is not None
    ]
    return sorted(hints, key=lambda c: c["min_margin_km"])


def _write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    print("PHASE F — F2 COARSE GAMMA0-K HYBRID REGIME MAP")
    print("AUTONOMOUS LONG RUN")
    print("DETERMINISTIC CARTESIAN GRID")
    print("NOT A DERIVATIVE STUDY")
    print("NOT AN OPTIMIZATION STUDY")
    print("=" * 72)

    git_commit = _git_commit()
    env = EnvironmentParams()
    vehicle = VehicleParams()
    solver = PRODUCTION_SOLVER_CONFIG
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Baseline anchor HARD GATE ----------------------------------------
    print("\n=== Baseline anchor gate (p0 = (-5 deg, 3)) ===")
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    anchor = verify_baseline_anchor(
        env, vehicle, git_commit, reference, solver=solver)
    for name, check in anchor["checks"].items():
        print(f"  [{'PASS' if check['pass'] else 'FAIL'}] {name}: "
              f"{check['detail']}")
    if not anchor["pass"]:
        print("BASELINE ANCHOR FAIL -- HARD STOP.")
        return 1

    # ---- Main loop: run grid + conditional expansion ----------------------
    domain = initial_domain()
    records: dict[str, dict] = {}
    fresh = 0
    reused = 0
    health_violations: list[str] = []
    stop_reasons: list[str] = []
    expansion_log: list[dict] = []
    open_boundaries: list[str] = []
    blockers: list[dict] = []
    stop_requested = False
    t_start = time.time()

    def _run_new_points(points, total_target: int) -> None:
        nonlocal fresh, stop_requested
        # Never re-integrate points already present (cache reuse must not
        # change results or inflate the fresh count).
        points = [p for p in points if cache_key(p) not in records]
        done = len(records)
        for p in points:
            if stop_requested:
                return
            done += 1
            t0 = time.time()
            try:
                pr = run_parameter_point(
                    env, vehicle, p, git_commit, solver=solver,
                    qian_max_time=QIAN_MAX_TIME_S,
                    sanger_max_time=SANGER_MAX_TIME_S,
                    sanger_max_segments=SANGER_MAX_SEGMENTS,
                )
            except RuntimeError as exc:
                # Frozen API expression boundary (e.g. Sanger SRTI
                # qualification rejection): record the blocker and STOP
                # adding points -- never modify frozen source, never
                # swallow the exception into a fake regime (F2 §19-M).
                blockers.append({
                    "parameter": [p.gamma0_deg, p.K],
                    "error": type(exc).__name__,
                    "message": str(exc),
                })
                stop_requested = True
                print(f"HARD STOP GATE: frozen API RuntimeError at "
                      f"gamma0={p.gamma0_deg:.2f}, K={p.K:.3f}: {exc}")
                return
            wall = time.time() - t0
            vio = (
                audit_point_health(p, pr.qian_result, pr.sanger_trajectory)
                if pr.qian_result is not None
                and pr.sanger_trajectory is not None
                else []
            )
            record = make_point_record(
                domain, p, pr.qian_row, pr.sanger_row, vio, wall,
                git_commit, _solver_dict())
            records[cache_key(p)] = record
            append_cache_record(CACHE_PATH, record)
            fresh += 1
            ms = pr.sanger_row.get("M_S_clearance_m")
            ma = (
                min(pr.sanger_row.get("M_A_clearance_m") or [])
                if pr.sanger_row.get("M_A_clearance_m") else None
            )
            print(_progress_line(done, total_target, pr, ms, ma))
            if done % 25 == 0:
                qian_c = Counter(
                    r["qian"]["qian_regime"] for r in records.values())
                sang_c = Counter(
                    r["sanger"]["sanger_regime"] for r in records.values())
                print(f"  [checkpoint] elapsed={time.time() - t_start:.1f}s "
                      f"cached={len(records)} "
                      f"Qian={dict(qian_c)} Sanger={dict(sang_c)}")

    # Resume from valid cache.
    domain_for_cache = initial_domain()
    cached = _load_valid_cache(domain_for_cache, git_commit)
    records.update(cached)
    reused = len(cached)
    initial_points = list(grid_points(initial_domain()))
    missing = [
        p for p in initial_points if cache_key(p) not in records
    ]
    print(f"\n[cache] valid cached = {len(cached)}  remaining = "
          f"{len(missing)}  (initial grid = {len(initial_points)})")
    _run_new_points(missing, len(initial_points))

    # ---- Conditional domain expansion loop (F0 §9, F2 §37–§42) ------------
    expansion_round = 0
    while not stop_requested:
        cells = detect_boundary_cells(domain, records)
        flags = plan_expansion(cells, domain)
        if not any(flags.values()):
            break
        expansion_round += 1
        new_domain, new_points = expand_domain(domain, flags)
        directions = [d for d, v in flags.items() if v]
        print(f"\n[expansion round {expansion_round}] directions="
              f"{directions} -> domain {domain.as_dict()} => "
              f"{new_domain.as_dict()}")
        expansion_log.append({
            "round": expansion_round,
            "directions": directions,
            "from_domain": domain.as_dict(),
            "to_domain": new_domain.as_dict(),
            "new_points": len(new_points),
        })
        if not new_points:
            # Guardrail reached: nothing new to add; re-check openness.
            open_boundaries = open_boundary_states(domain, cells)
            if open_boundaries:
                print(f"OPEN_BOUNDARY: {open_boundaries}")
            domain = new_domain
            break
        # The active domain must be updated BEFORE running new points so
        # their grid indices are computed against the expanded grid.
        domain = new_domain
        _run_new_points(new_points, len(records) + len(new_points))
        if stop_requested:
            break
        cells = detect_boundary_cells(domain, records)
        open_boundaries = open_boundary_states(domain, cells)
        if open_boundaries:
            print(f"OPEN_BOUNDARY: {open_boundaries}")
            break

    # ---- Post-run analyses ------------------------------------------------
    cells = detect_boundary_cells(domain, records)
    multiskip = detect_multiskip_jumps(domain, records)
    qian_rows = [r["qian"] for r in records.values()]
    sanger_rows = [r["sanger"] for r in records.values()]

    # Event-health + invariant checks.
    health_violations = [
        f"{key}: {v}"
        for key, rec in records.items()
        for v in rec["health"]["violations"]
    ]
    health_violations.extend(
        skip_count_consistency_violations(records))
    health_violations.extend(exit_transversality_violations(records))

    f1_consistency = f1_consistency_check(records)
    if not f1_consistency["pass"]:
        health_violations.append("F1 consistency check FAILED")

    stop_reasons = collect_stop_gate_reasons(
        anchor["pass"], qian_rows, sanger_rows, health_violations)
    if f1_consistency["pass"] is False:
        stop_reasons.append("F1 consistency check FAILED")
    for blocker in blockers:
        stop_reasons.append(
            f"frozen API RuntimeError at "
            f"gamma0={blocker['parameter'][0]}, K={blocker['parameter'][1]}: "
            f"{blocker['message']}")
    stop_gate_triggered = len(stop_reasons) > 0

    # Brackets, matrices, margins.
    brackets_gamma = boundary_brackets(domain, records, "gamma")
    brackets_k = boundary_brackets(domain, records, "K")
    matrices = build_categorical_matrices(domain, records)
    margin_hints = _margin_hint_cells(cells, records)
    priority = priority_cells(cells, multiskip, margin_hints)

    def _min_margin_global(records: dict, key: str) -> dict:
        best = None
        for rec in records.values():
            v = rec["sanger"].get(key)
            if v is None:
                continue
            vals = v if isinstance(v, list) else [v]
            for x in vals:
                if x is not None and (best is None or x < best["value"]):
                    best = {
                        "value": x,
                        "parameter": rec["parameter"],
                        "regime": rec["sanger"]["sanger_regime"],
                    }
        return best

    min_ma = _min_margin_global(records, "M_A_clearance_m")
    min_ms = _min_margin_global(records, "M_S_clearance_m")

    def _edge_minima(records: dict, key: str, domain: GridDomain) -> dict:
        out = {}
        for edge, pred in (
            ("gamma_lower", lambda r: r["parameter"][0] <= domain.gamma_min),
            ("gamma_upper", lambda r: r["parameter"][0] >= domain.gamma_max),
            ("K_lower", lambda r: r["parameter"][1] <= domain.k_min),
            ("K_upper", lambda r: r["parameter"][1] >= domain.k_max),
        ):
            vals = []
            for rec in records.values():
                if not pred(rec):
                    continue
                v = rec["sanger"].get(key)
                if v is None:
                    continue
                if isinstance(v, list):
                    vals.extend(x for x in v if x is not None)
                else:
                    vals.append(v)
            out[edge] = min(vals) if vals else None
        return out

    # ---- Summary artifact ---------------------------------------------------
    summary = {
        "schema_version": F2_SUMMARY_SCHEMA,
        "git_commit": git_commit,
        "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
        "initial_domain": initial_domain().as_dict(),
        "final_domain": domain.as_dict(),
        "grid_spacing": {
            "gamma_deg": 0.25, "K": 0.125},
        "initial_points": len(initial_points),
        "total_unique_points": len(records),
        "fresh_points": fresh,
        "cache_reused_points": reused,
        "baseline_anchor_pass": anchor["pass"],
        "qian": {
            "regime_counts": dict(sorted(
                Counter(r["qian_regime"] for r in qian_rows).items())),
            "terminal_kind_counts": dict(sorted(
                Counter(r["terminal_kind"] for r in qian_rows
                        if r["terminal_kind"] is not None).items())),
            "exact_topology_counts": dict(sorted(
                Counter(r["exact_topology_signature"] for r in qian_rows
                        if r["exact_topology_signature"] is not None)
                .items())),
        },
        "sanger": {
            "regime_counts": dict(sorted(
                Counter(r["sanger_regime"] for r in sanger_rows).items())),
            "terminal_kind_counts": dict(sorted(
                Counter(r["terminal_kind"] for r in sanger_rows
                        if r["terminal_kind"] is not None).items())),
            "skip_count_distribution": dict(sorted(
                Counter(r["skip_count"] for r in sanger_rows
                        if r.get("skip_count") is not None).items())),
            "exact_topology_counts": dict(sorted(
                Counter(r["exact_topology_signature"] for r in sanger_rows
                        if r["exact_topology_signature"] is not None)
                .items())),
        },
        "joint": {
            "regime_counts": {
                "(" + ", ".join(map(str, k)) + ")": v
                for k, v in sorted(
                    Counter(
                        tuple(r["joint_regime"]) for r in records.values()
                    ).items(),
                    key=lambda kv: str(kv[0]),
                )
            },
        },
        "boundary": {
            "cell_count": len(cells),
            "candidate_cell_count": sum(1 for c in cells if c["candidate"]),
            "exact_only_count": sum(
                1 for c in cells if c["exact_topology_only"]),
            "multiskip_warning_count": len(multiskip),
            "edge_touch_counts": {
                "gamma_lower": sum(
                    1 for c in cells
                    if c["candidate"] and c["touches_gamma_lower"]),
                "gamma_upper": sum(
                    1 for c in cells
                    if c["candidate"] and c["touches_gamma_upper"]),
                "K_lower": sum(
                    1 for c in cells
                    if c["candidate"] and c["touches_K_lower"]),
                "K_upper": sum(
                    1 for c in cells
                    if c["candidate"] and c["touches_K_upper"]),
            },
        },
        "margins": {
            "global_min_M_A": min_ma,
            "global_min_M_S": min_ms,
            "edge_min_M_A": _edge_minima(records, "M_A_clearance_m", domain),
            "edge_min_M_S": _edge_minima(records, "M_S_clearance_m", domain),
        },
        "domain_expansion": {
            "triggered": bool(expansion_log),
            "rounds": expansion_log,
            "open_boundaries": open_boundaries,
        },
        "health": {
            "censored": sum(1 for r in qian_rows + sanger_rows
                            if r.get("qian_regime") == "CENSORED"
                            or r.get("sanger_regime") == "CENSORED"),
            "failure": sum(
                1 for r in qian_rows + sanger_rows
                if r.get("qian_regime") == "NUMERICAL_FAILURE"
                or r.get("sanger_regime") == "NUMERICAL_FAILURE"),
            "ambiguous": sum(
                1 for r in qian_rows
                if r.get("qian_regime") == "BOUNDARY_AMBIGUOUS"),
            "invalid": sum(
                1 for r in qian_rows + sanger_rows
                if r.get("qian_regime") == "INVALID_INPUT"
                or r.get("sanger_regime") == "INVALID_INPUT"),
            "chatter": 0,
            "bad_order": 0,
            "nan_inf": 0,
            "violations": health_violations,
        },
        "f1_consistency": f1_consistency,
        "stop_gate_triggered": stop_gate_triggered,
        "stop_gate_reasons": stop_reasons,
        "ready_for_F3": not stop_gate_triggered,
        "total_runtime_s": time.time() - t_start,
    }

    # ---- Artifacts ---------------------------------------------------------
    flat_rows = []
    for key in sorted(records):
        rec = records[key]
        s = rec["sanger"]
        ma = s.get("M_A_clearance_m") or []
        flat_rows.append({
            "gamma0_deg": rec["parameter"][0],
            "K": rec["parameter"][1],
            "qian_regime": rec["qian"]["qian_regime"],
            "qian_terminal_kind": rec["qian"]["terminal_kind"],
            "qian_terminal_time_s": rec["qian"]["terminal_time_s"],
            "qian_terminal_range_m": rec["qian"]["terminal_range_m"],
            "sanger_regime": s["sanger_regime"],
            "sanger_terminal_kind": s["terminal_kind"],
            "skip_count": s.get("skip_count"),
            "sanger_terminal_time_s": s["terminal_time_s"],
            "sanger_terminal_range_m": s["terminal_range_m"],
            "M_S_clearance_m": s.get("M_S_clearance_m"),
            "min_M_A_clearance_m": min(ma) if ma else None,
            "qian_exact_topology": rec["qian"]["exact_topology_signature"],
            "sanger_exact_topology": s["exact_topology_signature"],
            "health": "OK" if not rec["health"]["violations"] else "VIOLATION",
        })

    _write_csv(OUT_DIR / "coarse_map.csv", flat_rows)
    _write_json(OUT_DIR / "coarse_map.json", {
        "schema_version": F2_POINT_SCHEMA,
        "git_commit": git_commit,
        "points": sorted(records.values(),
                         key=lambda r: (r["parameter"][0], r["parameter"][1])),
    })
    _write_json(OUT_DIR / "coarse_map_summary.json", summary)
    _write_json(OUT_DIR / "regime_matrices.json", {
        "schema_version": "f2-regime-matrices-v1",
        "domain": domain.as_dict(),
        **matrices,
    })
    _write_json(OUT_DIR / "boundary_cells.json", {
        "schema_version": "f2-boundary-cells-v1",
        "cells": cells,
    })
    _write_json(OUT_DIR / "F3_priority_cells.json", {
        "schema_version": "f2-f3-priority-cells-v1",
        "note": "refinement queue only; NOT a boundary proof (F2 §57)",
        "cells": priority,
    })
    _write_json(OUT_DIR / "boundary_brackets_by_gamma.json", {
        "schema_version": "f2-brackets-by-gamma-v1",
        "brackets": brackets_gamma,
    })
    _write_csv(OUT_DIR / "boundary_brackets_by_gamma.csv", brackets_gamma)
    _write_json(OUT_DIR / "boundary_brackets_by_K.json", {
        "schema_version": "f2-brackets-by-K-v1",
        "brackets": brackets_k,
    })
    _write_csv(OUT_DIR / "boundary_brackets_by_K.csv", brackets_k)
    _write_json(OUT_DIR / "domain_expansion.json", {
        "schema_version": "f2-domain-expansion-v1",
        "initial_domain": initial_domain().as_dict(),
        "final_domain": domain.as_dict(),
        "triggered": bool(expansion_log),
        "rounds": expansion_log,
        "open_boundaries": open_boundaries,
    })
    _write_json(OUT_DIR / "stop_gate_report.json", {
        "schema_version": "f2-stop-gate-report-v1",
        "stop_gate_triggered": stop_gate_triggered,
        "reasons": stop_reasons,
    })

    print("\n" + "=" * 72)
    print(f"total unique points : {len(records)} "
          f"(fresh={fresh}, cache-reused={reused})")
    print(f"total runtime       : {summary['total_runtime_s']:.1f} s")
    print(f"stop_gate_triggered : {stop_gate_triggered}")
    for reason in stop_reasons:
        print(f"  STOP GATE: {reason}")
    print(f"domain expansion    : {expansion_log}")
    print(f"OPEN_BOUNDARY       : {open_boundaries}")
    print(f"ready_for_F3        : {summary['ready_for_F3']}")
    print(f"F1 consistency      : {f1_consistency['pass']}")
    print("Artifacts written to " + str(OUT_DIR))
    print("F2 RUN: " + ("COMPLETE" if not stop_gate_triggered else "BLOCKED"))
    return 0 if not stop_gate_triggered else 2


if __name__ == "__main__":
    sys.exit(main())
