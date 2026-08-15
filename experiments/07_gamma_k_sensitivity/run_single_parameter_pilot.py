"""F1 runner -- deterministic single-parameter pilot (gamma slice + K slice).

Executes the F0-frozen 17-point gamma slice and 17-point K slice
(baseline (-5 deg, 3) computed once and reused: 33 unique paired points,
66 model integrations) with the structured Phase-F regime APIs:

    Qian:   integrate_qian_research_trajectory + classify_qian_regime
    Sanger: integrate_sanger_hybrid + analyze_sanger_trajectory
            + classify_sanger_regime

Writes read-only artifacts under
``results/gamma_k_sensitivity/pilot/`` (untracked):
    gamma_slice.csv / gamma_slice.json
    k_slice.csv / k_slice.json
    pilot_summary.json
    transition_intervals.json

PHASE F — F1 SINGLE-PARAMETER PILOT
DETERMINISTIC REGIME EXPLORATION
NOT A DERIVATIVE STUDY
NOT AN OPTIMIZATION STUDY
"""

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from hyptraj.analysis.sensitivity_pilot import (
    PHASE_E_ANCHOR_COMMIT,
    PHASE_E_ANCHOR_TAG,
    SCHEMA_VERSION,
    QIAN_MAX_TIME_S,
    SANGER_MAX_SEGMENTS,
    SANGER_MAX_TIME_S,
    PairedPointResult,
    ParameterPoint,
    all_unique_points,
    audit_point_health,
    collect_stop_gate_reasons,
    detect_transition_intervals,
    gamma_slice_points,
    k_slice_points,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.models.parameters import (
    EnvironmentParams,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

OUT_DIR = Path("results/gamma_k_sensitivity/pilot")
FIG_DIR = OUT_DIR / "figures"
REFERENCE_PATH = Path("tests/data/qian_sanger_comparison_v1.json")


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _qian_range_km(row: dict) -> float | None:
    r = row.get("terminal_range_m")
    return None if r is None else r / 1000.0


def _sanger_range_km(row: dict) -> float | None:
    r = row.get("terminal_range_m")
    return None if r is None else r / 1000.0


def _sanger_key_margin(row: dict) -> float | None:
    """Key margin for the summary table: M_S (SRTI) or min M_A (fallback)."""
    if row.get("M_S_clearance_m") is not None:
        return row["M_S_clearance_m"]
    m_a = row.get("M_A_clearance_m") or []
    return min(m_a) if m_a else None


def _flat_pair(p: PairedPointResult) -> dict:
    """One flat row for the slice CSVs (NA -> empty string)."""
    q = p.qian_row
    s = p.sanger_row
    return {
        "gamma0_deg": q["gamma0_deg"],
        "K": q["K"],
        "qian_regime": q["qian_regime"],
        "qian_terminal_kind": q["terminal_kind"] or "",
        "qian_terminal_time_s": q["terminal_time_s"] or "",
        "qian_terminal_range_km": _fmt(_qian_range_km(q)),
        "sanger_regime": s["sanger_regime"],
        "sanger_terminal_kind": s["terminal_kind"] or "",
        "sanger_skip_count": s.get("skip_count"),
        "sanger_terminal_time_s": s["terminal_time_s"] or "",
        "sanger_terminal_range_km": _fmt(_sanger_range_km(s)),
        "sanger_M_S_clearance_m": _fmt(s.get("M_S_clearance_m")),
        "sanger_min_M_A_clearance_m": _fmt(_sanger_min_ma(s)),
    }


def _fmt(v) -> str:
    return "" if v is None else f"{v:.6f}"


def _sanger_min_ma(row: dict) -> float | None:
    m_a = row.get("M_A_clearance_m") or []
    return min(m_a) if m_a else None


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _regime_counts(rows: list[dict], key: str) -> dict[str, int]:
    return dict(sorted(Counter(r[key] for r in rows).items()))


def _terminal_kind_counts(rows: list[dict], key: str) -> dict[str, int]:
    return dict(
        sorted(Counter(r[key] for r in rows if r[key] is not None).items())
    )


def _slice_json(points: list[ParameterPoint], by_key: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "rows": [
            {
                "parameter": list(p.key),
                "qian": by_key[p.key].qian_row,
                "sanger": by_key[p.key].sanger_row,
            }
            for p in points
        ],
    }


def main() -> int:
    print("PHASE F — F1 SINGLE-PARAMETER PILOT")
    print("DETERMINISTIC REGIME EXPLORATION")
    print("NOT A DERIVATIVE STUDY")
    print("NOT AN OPTIMIZATION STUDY")
    print("=" * 72)

    git_commit = _git_commit()
    env = EnvironmentParams()
    vehicle = VehicleParams()

    # ---- 0. Baseline anchor HARD GATE -------------------------------------
    print("\n=== Baseline anchor gate (p0 = (-5 deg, 3)) ===")
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    anchor = verify_baseline_anchor(
        env, vehicle, git_commit, reference,
        solver=PRODUCTION_SOLVER_CONFIG,
    )
    for name, check in anchor["checks"].items():
        print(f"  [{('PASS' if check['pass'] else 'FAIL')}] {name}: "
              f"{check['detail']}")
    if not anchor["pass"]:
        print("BASELINE ANCHOR FAIL -- stopping F1.")
        return 1
    print("Baseline anchor: PASS")
    print(f"  Qian  : {anchor['qian']}")
    print(f"  Sanger: {anchor['sanger']}")

    # ---- 1. Execute the 33 unique paired points (baseline reused) ---------
    points = all_unique_points()
    results: dict[tuple[float, float], PairedPointResult] = {}
    violations: list[str] = []
    for i, p in enumerate(points, start=1):
        pr = run_parameter_point(
            env, vehicle, p, git_commit,
            solver=PRODUCTION_SOLVER_CONFIG,
            qian_max_time=QIAN_MAX_TIME_S,
            sanger_max_time=SANGER_MAX_TIME_S,
            sanger_max_segments=SANGER_MAX_SEGMENTS,
        )
        results[p.key] = pr
        if pr.qian_result is not None and pr.sanger_trajectory is not None:
            violations.extend(audit_point_health(p, pr.qian_result,
                                                 pr.sanger_trajectory))
        skip = pr.sanger_row.get("skip_count")
        print(f"[{i}/{len(points)}] "
              f"gamma0={p.gamma0_deg:.2f} K={p.K:.3f} "
              f"Qian={pr.qian_row['qian_regime']} "
              f"Sanger={pr.sanger_row['sanger_regime']} "
              f"skip={skip if skip is not None else 'NA'}")

    gamma_points = list(gamma_slice_points())
    k_points = list(k_slice_points())

    # ---- 2. Transition intervals (per slice, parameter-ordered) -----------
    gamma_compact, gamma_exact = detect_transition_intervals(
        [results[p.key] for p in gamma_points], "gamma0")
    k_compact, k_exact = detect_transition_intervals(
        [results[p.key] for p in k_points], "K")

    # ---- 3. Stop gates (F1 §23) -------------------------------------------
    qian_rows = [results[p.key].qian_row for p in points]
    sanger_rows = [results[p.key].sanger_row for p in points]
    stop_gate_reasons = collect_stop_gate_reasons(
        anchor["pass"], qian_rows, sanger_rows, violations
    )
    stop_gate_triggered = len(stop_gate_reasons) > 0

    # ---- 4. Summary statistics --------------------------------------------
    summary = {
        "schema_version": "f1-pilot-summary-v1",
        "git_commit": git_commit,
        "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
        "phase_e_anchor_commit": PHASE_E_ANCHOR_COMMIT,
        "baseline_anchor_pass": anchor["pass"],
        "baseline_anchor": {
            "qian": anchor["qian"],
            "sanger": anchor["sanger"],
        },
        "grid": {
            "gamma_points": len(gamma_points),
            "k_points": len(k_points),
            "requested_slice_positions": len(gamma_points) + len(k_points),
            "unique_points": len(points),
            "qian_integrations": len(points),
            "sanger_integrations": len(points),
        },
        "qian": {
            "regime_counts": _regime_counts(qian_rows, "qian_regime"),
            "terminal_kind_counts": _terminal_kind_counts(
                qian_rows, "terminal_kind"),
            "exact_topology_counts": _regime_counts(
                qian_rows, "exact_topology_signature"),
            "censored_count": sum(
                1 for r in qian_rows if r["qian_regime"] == "CENSORED"),
            "failure_count": sum(
                1 for r in qian_rows
                if r["qian_regime"] == "NUMERICAL_FAILURE"),
            "ambiguous_count": sum(
                1 for r in qian_rows
                if r["qian_regime"] == "BOUNDARY_AMBIGUOUS"),
        },
        "sanger": {
            "regime_counts": _regime_counts(sanger_rows, "sanger_regime"),
            "terminal_kind_counts": _terminal_kind_counts(
                sanger_rows, "terminal_kind"),
            "skip_count_distribution": _regime_counts(
                [r for r in sanger_rows if r.get("skip_count") is not None],
                "skip_count"),
            "exact_topology_counts": _regime_counts(
                sanger_rows, "exact_topology_signature"),
            "censored_count": sum(
                1 for r in sanger_rows if r["sanger_regime"] == "CENSORED"),
            "failure_count": sum(
                1 for r in sanger_rows
                if r["sanger_regime"] == "NUMERICAL_FAILURE"),
        },
        "gamma_slice": {
            "ordered_qian_regimes": [
                results[p.key].qian_row["qian_regime"] for p in gamma_points
            ],
            "ordered_sanger_regimes": [
                results[p.key].sanger_row["sanger_regime"]
                for p in gamma_points
            ],
            "transition_intervals": gamma_compact,
            "exact_topology_only": gamma_exact,
        },
        "k_slice": {
            "ordered_qian_regimes": [
                results[p.key].qian_row["qian_regime"] for p in k_points
            ],
            "ordered_sanger_regimes": [
                results[p.key].sanger_row["sanger_regime"] for p in k_points
            ],
            "transition_intervals": k_compact,
            "exact_topology_only": k_exact,
        },
        "stop_gate_triggered": stop_gate_triggered,
        "stop_gate_reasons": stop_gate_reasons,
        "ready_for_F2": not stop_gate_triggered,
    }

    # ---- 5. Artifacts ------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gamma_rows = [
        _flat_pair(results[p.key]) for p in gamma_points
    ]
    k_rows = [_flat_pair(results[p.key]) for p in k_points]
    _write_csv(OUT_DIR / "gamma_slice.csv", gamma_rows)
    _write_csv(OUT_DIR / "k_slice.csv", k_rows)
    _write_json(OUT_DIR / "gamma_slice.json",
                _slice_json(gamma_points, results))
    _write_json(OUT_DIR / "k_slice.json", _slice_json(k_points, results))
    _write_json(OUT_DIR / "pilot_summary.json", summary)
    _write_json(
        OUT_DIR / "transition_intervals.json",
        {
            "schema_version": "f1-transition-intervals-v1",
            "git_commit": git_commit,
            "gamma_slice": gamma_compact,
            "gamma_slice_exact_topology_only": gamma_exact,
            "k_slice": k_compact,
            "k_slice_exact_topology_only": k_exact,
        },
    )

    print("\n" + "=" * 72)
    print(f"Artifacts written to {OUT_DIR}")
    print(f"stop_gate_triggered : {stop_gate_triggered}")
    for reason in stop_gate_reasons:
        print(f"  STOP GATE: {reason}")
    print(f"ready_for_F2        : {summary['ready_for_F2']}")
    print("F1 RUNNER: " + ("PASS" if not stop_gate_triggered else "STOP GATE"))
    return 0 if not stop_gate_triggered else 2


if __name__ == "__main__":
    sys.exit(main())
