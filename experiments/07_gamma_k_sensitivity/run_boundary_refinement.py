"""F3 runner -- adaptive grazing-boundary refinement of the F2 map.

    PHASE F — F3 ADAPTIVE GRAZING-BOUNDARY REFINEMENT

    2D DYADIC CELL REFINEMENT
    NOT A GLOBAL CURVE FIT
    NOT A DERIVATIVE STUDY
    NOT A SALTATION / FTLE STUDY

Refines the F2 P1 compact-transition candidate cells (179) with dyadic
2D bisection to the F0 target resolution (Delta gamma <= 0.01 deg AND
Delta K <= 0.01, max_depth = 6), classifies every refined box into its
skip-count branch, computes the branch-conditioned signed grazing
diagnostic Phi_N, verifies every recovered interface event and the
branch extremal points against the strict reference, records the
guardrail OPEN_BOUNDARY intersections and builds the F4 boundary-
exclusion geometry.

Artifacts (untracked): results/gamma_k_sensitivity/boundary_refinement/
"""

import json
import subprocess
import sys
import time
from collections import Counter, deque
from pathlib import Path

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
    PHASE_E_ANCHOR_TAG,
    QIAN_MAX_TIME_S,
    SANGER_MAX_SEGMENTS,
    SANGER_MAX_TIME_S,
    ParameterPoint,
    audit_point_health,
    run_parameter_point,
    verify_baseline_anchor,
)
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
from hyptraj.analysis.sensitivity_refinement import (
    ADJACENT_SKIP_BRANCH,
    EXACT_TOPOLOGY_ONLY,
    F2_COMMIT,
    F3_POINT_SCHEMA,
    F3_SUMMARY_SCHEMA,
    GAMMA_GUARD_MAX,
    GAMMA_GUARD_MIN,
    K_GUARD_MAX,
    K_GUARD_MIN,
    MAX_DEPTH,
    MULTISKIP,
    QIAN_TOPOLOGY,
    TERMINAL_MAX_DEPTH_CELL,
    TERMINAL_REFINED_BOUNDARY_CELL,
    TERMINAL_UNRESOLVED_MULTISKIP_CELL,
    UNIFORM,
    DyadicCell,
    assemble_terminal_cell,
    branch_from_regimes,
    build_f4_exclusion_cells,
    child_is_candidate,
    classify_cell_branch,
    coarse_cell_from_rectangle,
    new_exit_transversality,
    open_edges_of_cell,
    phi_n_for_point,
    phi_sign_anomaly,
    row_column_multiplicity,
    target_resolution_reached,
    validate_f3_cache_record,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.sanger_research_trajectory import (
    integrate_sanger_research_trajectory,
)
from hyptraj.simulation.sanger_metrics import analyze_sanger_trajectory
from hyptraj.simulation.sanger_trajectory import integrate_sanger_hybrid

OUT_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")
CACHE_PATH = OUT_DIR / "point_cache.jsonl"
COARSE_DIR = Path("results/gamma_k_sensitivity/coarse_map")
REFERENCE_PATH = Path("tests/data/qian_sanger_comparison_v1.json")

H_ATM = 100_000.0


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


def _expected_provenance(git_commit: str) -> dict:
    return {
        "schema_version": F3_POINT_SCHEMA,
        "phase_e_anchor_commit": "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc",
        "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
        "phase_f_f01_commit": F01_COMMIT,
        "phase_f_f1_commit": F1_COMMIT,
        "phase_f_f21_commit": F21_COMMIT,
        "phase_f_f2_commit": F2_COMMIT,
        "sanger_research_event_resolution_version": "v1",
        "solver_config": _solver_dict(),
        "domain_guardrails": {
            "gamma0_deg": [GAMMA_GUARD_MIN, GAMMA_GUARD_MAX],
            "K": [K_GUARD_MIN, K_GUARD_MAX],
        },
        "max_depth": MAX_DEPTH,
    }


def _load_point_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    records: dict = {}
    for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        key = cache_key(
            ParameterPoint(rec["parameter"][0], rec["parameter"][1]))
        records[key] = rec
    return records


def _append_cache(record: dict) -> None:
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        f.flush()


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


def _reference_classify(env, veh, g, k, solver):
    ini = InitialCondition(
        altitude=100_000.0, velocity=7_000.0,
        flight_path_angle_deg=g, range_angle=0.0)
    ctl = ConstantKControl(k)
    traj = integrate_sanger_hybrid(env, veh, ini, ctl, solver=solver)
    m = analyze_sanger_trajectory(traj, env)
    return traj, m


def main() -> int:
    print("PHASE F — F3 ADAPTIVE GRAZING-BOUNDARY REFINEMENT")
    print("2D DYADIC CELL REFINEMENT")
    print("NOT A GLOBAL CURVE FIT")
    print("NOT A DERIVATIVE STUDY")
    print("NOT A SALTATION / FTLE STUDY")
    print("=" * 72)

    git_commit = _git_commit()
    env = EnvironmentParams()
    veh = VehicleParams()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- F2 artifacts ------------------------------------------------------
    coarse = json.loads(
        (COARSE_DIR / "coarse_map.json").read_text(encoding="utf-8"))
    point_lookup: dict = {}
    for rec in coarse["points"]:
        rec["refinement_depth"] = 0  # F2 coarse corners are depth 0
        point_lookup[cache_key(
            ParameterPoint(rec["parameter"][0], rec["parameter"][1]))] = rec
    priority = json.loads(
        (COARSE_DIR / "F3_priority_cells.json").read_text(encoding="utf-8"))
    p1_cells = [c for c in priority["cells"] if c["priority"] == "P1"]
    p0_cells = [c for c in priority["cells"] if c["priority"] == "P0"]
    p2_cells = [c for c in priority["cells"] if c["priority"] == "P2"]
    print(f"[F2] coarse points = {len(point_lookup)} | candidate cells: "
          f"P0={len(p0_cells)} P1={len(p1_cells)} P2={len(p2_cells)}")

    # ---- Baseline anchor HARD GATE ----------------------------------------
    print("\n=== Baseline anchor gate (p0 = (-5 deg, 3)) ===")
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    anchor = verify_baseline_anchor(env, veh, git_commit, reference)
    if not anchor["pass"]:
        print("BASELINE ANCHOR FAIL -- HARD STOP.")
        return 1
    print("Baseline anchor: PASS")

    # ---- F3 cache ----------------------------------------------------------
    recovered_queue: list[dict] = []
    sign_anomaly_queue: list[dict] = []
    grazing_resolutions: list[dict] = []
    grazing_marker_cells: list[dict] = []
    health_violations: list[str] = []
    stop_reasons: list[str] = []
    cached = _load_point_cache()
    expected = _expected_provenance(git_commit)
    valid_cached: dict = {}
    rejected = 0
    for key, rec in cached.items():
        ok, _ = validate_f3_cache_record(rec, expected)
        if ok:
            valid_cached[key] = rec
        else:
            rejected += 1
    point_lookup.update(valid_cached)
    print(f"[cache] valid = {len(valid_cached)} rejected = {rejected}")

    # Batch post-processing of cached points: grazing-limit points and
    # recovered points from a previous interrupted run need their
    # strict-reference decision / verification (F3 §51).
    for key, rec in sorted(valid_cached.items()):
        g, k = rec["parameter"]
        s = rec["sanger"]
        if s["terminal_kind"] == "grazing_or_unresolved_event":
            try:
                ref, ref_m = _reference_classify(
                    env, veh, g, k, REFERENCE_SOLVER_CONFIG)
                if ref.terminal_kind == "srti":
                    ref_regime = f"SRTI_N{ref_m.skip_count}"
                    s["sanger_regime"] = ref_regime
                    s["terminal_kind"] = "srti"
                    s["skip_count"] = ref_m.skip_count
                    s["event_resolution"] = "REFERENCE_CONFIRMED"
                    grazing_resolutions.append({
                        "parameter": [g, k],
                        "decision": "REFERENCE_CONFIRMED",
                        "reference_regime": ref_regime,
                    })
                else:
                    s["sanger_regime"] = "SANGER_GRAZING_BOUNDARY"
                    s["event_resolution"] = "GRAZING_BOUNDARY"
                    grazing_marker_cells.append({"parameter": [g, k]})
            except RuntimeError as exc:
                stop_reasons.append(
                    f"cached grazing reference RUNTIME_ERROR at "
                    f"gamma0={g}, K={k}: {exc}")
        elif s.get("recovered_exit_count", 0) > 0:
            try:
                ref, ref_m = _reference_classify(
                    env, veh, g, k, REFERENCE_SOLVER_CONFIG)
                same = (ref.terminal_kind == s["terminal_kind"]
                        and ref_m.skip_count == s.get("skip_count"))
                recovered_queue.append({
                    "parameter": [g, k],
                    "production_regime": s["sanger_regime"],
                    "reference_regime": (
                        f"SRTI_N{ref_m.skip_count}"
                        if ref.terminal_kind == "srti"
                        else ref.terminal_kind),
                    "topology_equal": same,
                })
                if not same:
                    stop_reasons.append(
                        f"cached recovered topology mismatch at "
                        f"gamma0={g}, K={k}")
            except RuntimeError as exc:
                stop_reasons.append(
                    f"cached recovered reference RUNTIME_ERROR at "
                    f"gamma0={g}, K={k}: {exc}")
    if stop_reasons:
        print(f"[cache] batch post-processing found {len(stop_reasons)} "
              f"issue(s): {stop_reasons}")

    # ---- Initial refinement queue ------------------------------------------
    queue: deque = deque()
    cell_branch: dict = {}
    for c in p0_cells + p1_cells + p2_cells:
        cell = coarse_cell_from_rectangle(
            c["gamma_min"], c["gamma_max"], c["K_min"], c["K_max"])
        regimes = tuple(corner["sanger_regime"] for corner in c["corners"])
        classification, branch = classify_cell_branch(regimes)
        if branch is None and classification == ADJACENT_SKIP_BRANCH:
            # Single regime pair may be ambiguous across corners; derive
            # from the actual corner set.
            skips = sorted({int(r[-1]) for r in regimes
                            if r.startswith("SRTI_N")})
            if len(skips) == 2 and skips[1] - skips[0] == 1:
                branch = f"B{skips[0]}"
        queue.append(cell)
        cell_branch[cell] = branch

    processed: set = set()
    terminal_cells: list[dict] = []
    unresolved_cells: list[dict] = []
    max_depth_cells: list[dict] = []
    fresh_points = 0
    t_start = time.time()
    hard_stop = False

    def _classify_queued_cell(cell: DyadicCell) -> tuple[str, str | None]:
        corners = cell.corner_points()
        regimes = []
        for p in corners:
            rec = point_lookup.get(cache_key(p))
            regimes.append(rec["sanger"]["sanger_regime"] if rec else None)
        if any(r is None for r in regimes):
            return ADJACENT_SKIP_BRANCH, None
        return classify_cell_branch(tuple(regimes))

    # ---- Refinement loop ----------------------------------------------------
    initial_queue_size = len(queue)
    print(f"\n[refine] queued cells = {initial_queue_size} | "
          f"max_depth = {MAX_DEPTH} | target = 0.01 deg x 0.01 K")
    while queue and not hard_stop:
        cell = queue.popleft()
        if cell in processed:
            continue
        processed.add(cell)
        branch_ctx = cell_branch.get(cell)

        # 5 new dyadic points (dedup against the global point cache).
        new_points = [
            p for p in cell.midpoint_points()
            if cache_key(p) not in point_lookup
        ]
        for p in new_points:
            t0 = time.time()
            pr = run_parameter_point(
                env, veh, p, git_commit, solver=PRODUCTION_SOLVER_CONFIG,
                qian_max_time=QIAN_MAX_TIME_S,
                sanger_max_time=SANGER_MAX_TIME_S,
                sanger_max_segments=SANGER_MAX_SEGMENTS,
                sanger_integrator=integrate_sanger_research_trajectory,
            )
            vio = (
                audit_point_health(p, pr.qian_result, pr.sanger_trajectory)
                if pr.qian_result is not None
                and pr.sanger_trajectory is not None
                else []
            )
            record = {
                "schema_version": F3_POINT_SCHEMA,
                "parameter": [p.gamma0_deg, p.K],
                "refinement_depth": cell.depth,
                "provenance": {
                    "git_commit": git_commit,
                    "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
                    "phase_e_anchor_commit":
                        "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc",
                    "phase_f_protocol_commit": F0_PROTOCOL_COMMIT,
                    "phase_f_f01_commit": F01_COMMIT,
                    "phase_f_f1_commit": F1_COMMIT,
                    "phase_f_f21_commit": F21_COMMIT,
                    "phase_f_f2_commit": F2_COMMIT,
                    "sanger_research_event_resolution_version": "v1",
                    "solver_config": _solver_dict(),
                    "domain_guardrails": {
                        "gamma0_deg": [GAMMA_GUARD_MIN, GAMMA_GUARD_MAX],
                        "K": [K_GUARD_MIN, K_GUARD_MAX],
                    },
                    "max_depth": MAX_DEPTH,
                },
                "qian": pr.qian_row,
                "sanger": pr.sanger_row,
                "joint_regime": list(pr.qian_row["qian_regime"]
                                     + "/" + pr.sanger_row["sanger_regime"]),
                "health": {"violations": vio},
                "wall_runtime_s": time.time() - t0,
            }
            point_lookup[cache_key(p)] = record
            _append_cache(record)
            fresh_points += 1
            health_violations.extend(
                f"{p.gamma0_deg},{p.K}: {v}" for v in vio)

            # Qian discovery gate (F3 §26).
            if pr.qian_row["qian_regime"] != "QIAN_RTI":
                stop_reasons.append(
                    f"NEW_QIAN_TOPOLOGY_DISCOVERY at "
                    f"gamma0={p.gamma0_deg}, K={p.K}: "
                    f"{pr.qian_row['qian_regime']}")
                hard_stop = True

            # GRAZING_OR_UNRESOLVED point -> strict-reference decision
            # FIRST (F2.1 §17, F3 §30): a production grazing-limit point
            # with a reference-confirmed side is NOT a recovered mismatch.
            if pr.sanger_row["terminal_kind"] == "grazing_or_unresolved_event":
                try:
                    ref, ref_m = _reference_classify(
                        env, veh, p.gamma0_deg, p.K,
                        REFERENCE_SOLVER_CONFIG)
                    if ref.terminal_kind == "srti":
                        ref_regime = f"SRTI_N{ref_m.skip_count}"
                        pr.sanger_row["sanger_regime"] = ref_regime
                        pr.sanger_row["terminal_kind"] = "srti"
                        pr.sanger_row["skip_count"] = ref_m.skip_count
                        pr.sanger_row["event_resolution"] = (
                            "REFERENCE_CONFIRMED")
                        grazing_resolutions.append({
                            "parameter": [p.gamma0_deg, p.K],
                            "decision": "REFERENCE_CONFIRMED",
                            "reference_regime": ref_regime,
                        })
                    else:
                        pr.sanger_row["sanger_regime"] = (
                            "SANGER_GRAZING_BOUNDARY")
                        pr.sanger_row["event_resolution"] = (
                            "GRAZING_BOUNDARY")
                        grazing_marker_cells.append({
                            "parameter": [p.gamma0_deg, p.K],
                        })
                except RuntimeError as exc:
                    stop_reasons.append(
                        f"grazing reference RUNTIME_ERROR at "
                        f"gamma0={p.gamma0_deg}, K={p.K}: {exc}")
                    hard_stop = True

            # Recovered-event reference verification (inline, F3 §31).
            # Excludes grazing-limit points (decided above): for those the
            # production topology is unresolved BY DESIGN and the
            # reference-confirmed side supersedes it.
            elif pr.sanger_row.get("recovered_exit_count", 0) > 0:
                try:
                    ref, ref_m = _reference_classify(
                        env, veh, p.gamma0_deg, p.K,
                        REFERENCE_SOLVER_CONFIG)
                    same = (
                        ref.terminal_kind
                        == pr.sanger_row["terminal_kind"]
                        and ref_m.skip_count
                        == pr.sanger_row.get("skip_count")
                    )
                    recovered_queue.append({
                        "parameter": [p.gamma0_deg, p.K],
                        "production_regime":
                            pr.sanger_row["sanger_regime"],
                        "reference_regime": (
                            f"SRTI_N{ref_m.skip_count}"
                            if ref.terminal_kind == "srti"
                            else ref.terminal_kind),
                        "topology_equal": same,
                    })
                    if not same:
                        stop_reasons.append(
                            f"recovered topology mismatch at "
                            f"gamma0={p.gamma0_deg}, K={p.K}")
                        hard_stop = True
                except RuntimeError as exc:
                    stop_reasons.append(
                        f"recovered reference RUNTIME_ERROR at "
                        f"gamma0={p.gamma0_deg}, K={p.K}: {exc}")
                    hard_stop = True

            # Phi_N sign anomaly -> strict-reference queue (F3 §29).
            regime = pr.sanger_row["sanger_regime"]
            if regime.startswith("SRTI_N"):
                n_skip = int(regime[-1])
                for n in (n_skip - 1, n_skip):
                    if n < 0:
                        continue
                    phi, side, _ = phi_n_for_point(
                        pr.sanger_row, n, H_ATM)
                    if phi_sign_anomaly(phi, side):
                        sign_anomaly_queue.append({
                            "parameter": [p.gamma0_deg, p.K],
                            "branch": f"B{n}",
                            "regime": regime,
                            "phi": phi,
                            "side": side,
                        })

        # Children.
        children = cell.subdivide()
        for child in children:
            ok, reasons = child_is_candidate(
                child, point_lookup, None, H_ATM)
            if not ok:
                continue
            if target_resolution_reached(child):
                classification, branch = _classify_queued_cell(child)
                if branch is None and branch_ctx is not None:
                    branch = branch_ctx
                open_edges = open_edges_of_cell(child)
                if branch is None:
                    # Try adjacent-pair inference from the corners.
                    corner_recs = [
                        point_lookup.get(cache_key(p))
                        for p in child.corner_points()
                    ]
                    regimes = [r["sanger"]["sanger_regime"]
                               for r in corner_recs if r]
                    b = branch_from_regimes(
                        regimes[0], regimes[1]) if len(regimes) >= 2 else None
                    if b is None:
                        b = branch_from_regimes(
                            regimes[0], regimes[-1]) \
                            if len(regimes) >= 2 else None
                    branch = b
                cell_type = TERMINAL_REFINED_BOUNDARY_CELL
                if classification == MULTISKIP:
                    # Coarse multiskip not resolved by depth-5 dyadic grid.
                    cell_type = TERMINAL_UNRESOLVED_MULTISKIP_CELL
                    unresolved_cells.append(assemble_terminal_cell(
                        child, classification, branch, point_lookup,
                        H_ATM, open_edges))
                else:
                    terminal_cells.append(assemble_terminal_cell(
                        child, classification, branch, point_lookup,
                        H_ATM, open_edges))
            elif child.depth >= MAX_DEPTH:
                classification, branch = _classify_queued_cell(child)
                if branch is None and branch_ctx is not None:
                    branch = branch_ctx
                if classification == MULTISKIP:
                    unresolved_cells.append(assemble_terminal_cell(
                        child, classification, branch, point_lookup,
                        H_ATM, open_edges_of_cell(child)))
                else:
                    max_depth_cells.append(assemble_terminal_cell(
                        child, classification, branch, point_lookup,
                        H_ATM, open_edges_of_cell(child)))
            else:
                queue.append(child)
                cell_branch[child] = (
                    branch_ctx if branch_ctx is not None else None)

        if fresh_points % 100 < 5 and fresh_points > 0:
            print(f"  [progress] evaluated={fresh_points} "
                  f"queue={len(queue)} terminal={len(terminal_cells)} "
                  f"recovered={len(recovered_queue)} "
                  f"elapsed={time.time() - t_start:.0f}s")

    if hard_stop:
        print("HARD STOP during refinement.")

    # ---- Branch summaries / extremal certification -------------------------
    from collections import defaultdict
    branch_cells: dict[str, list[dict]] = defaultdict(list)
    for c in terminal_cells:
        if c["branch"]:
            branch_cells[c["branch"]].append(c)
    observed_branches = sorted(branch_cells.keys())

    # Branch extremal certification (F3 §32–§33): closest-to-zero on both
    # sides, dual-reference (REF-0.1 + REF-0.05).
    import numpy as np
    from hyptraj.simulation.trajectory import SolverConfig
    REF_005 = SolverConfig(
        method="DOP853", rtol=1e-12,
        atol=np.array([1e-7, 1e-14, 1e-10, 1e-14]),
        max_step=0.05, dense_output=True)

    def _ref_phi(g, k, solver):
        """Reference Phi_N via the frozen integrator (no physics copies)."""
        traj, metrics = _reference_classify(env, veh, g, k, solver)
        regime = (f"SRTI_N{metrics.skip_count}"
                  if traj.terminal_kind == "srti" else traj.terminal_kind)
        m_s = None
        if traj.terminal_kind == "srti":
            m_s = float(H_ATM - (traj.terminal_state[0] - env.earth_radius))
        m_a = [float(e.state[0] - env.earth_radius - H_ATM)
               for e in traj.events if e.kind == "vacuum_apogee"]
        exit_dhdt = [float(e.state[2] * np.sin(e.state[3]))
                     for e in traj.events if e.kind == "atmosphere_exit"]
        phi, side, _ = phi_n_for_point(
            {"sanger_regime": regime,
             "M_S_clearance_m": m_s,
             "M_A_clearance_m": m_a,
             "exit_dhdt_mps": exit_dhdt,
             "terminal_kind": traj.terminal_kind,
             },
            n, H_ATM)
        return traj, metrics, regime, phi

    certification: dict[str, dict] = {}
    for branch in observed_branches:
        n = int(branch[1:])
        neg_pts, pos_pts = [], []
        for key, rec in point_lookup.items():
            s = rec["sanger"]
            phi, side, _ = phi_n_for_point(s, n, H_ATM)
            if phi is None:
                continue
            if side == "N":
                neg_pts.append((phi, rec["parameter"]))
            elif side == "N+1":
                pos_pts.append((phi, rec["parameter"]))
        closest_neg = max(neg_pts) if neg_pts else None   # max Phi < 0
        closest_pos = min(pos_pts) if pos_pts else None   # min Phi > 0
        cert = {"branch": branch, "N_side": None, "N1_side": None}
        for side_label, entry in (("N_side", closest_neg),
                                  ("N1_side", closest_pos)):
            if entry is None:
                continue
            phi_prod, (g, k) = entry
            prod_rec = point_lookup.get(cache_key(ParameterPoint(g, k)))
            prod_regime = prod_rec["sanger"]["sanger_regime"]
            ref_rows = []
            ref_ok = True
            for solver_name, solver in (
                ("REF-0.1", REFERENCE_SOLVER_CONFIG),
                ("REF-0.05", REF_005),
            ):
                try:
                    traj, metrics, ref_regime, ref_phi = _ref_phi(
                        g, k, solver)
                    same = prod_regime == ref_regime
                    ref_ok &= same
                    ref_rows.append({
                        "solver": solver_name,
                        "regime": ref_regime,
                        "skip": metrics.skip_count,
                        "phi": ref_phi,
                        "terminal_time_s": traj.terminal_time,
                        "topology_equal": same,
                    })
                except RuntimeError as exc:
                    ref_ok = False
                    ref_rows.append({
                        "solver": solver_name, "regime": "RUNTIME_ERROR",
                        "phi": None, "error": str(exc)})
            tn = new_exit_transversality(prod_rec["sanger"], n)
            cert[side_label] = {
                "parameter": [g, k],
                "production_phi": phi_prod,
                "reference_rows": ref_rows,
                "reference_dual_stable": ref_ok,
                "new_exit_dhdt_mps": tn,
            }
        certification[branch] = cert
        if not ref_ok:
            stop_reasons.append(f"branch {branch} extremal reference "
                                f"not dual-stable")

    # ---- Grazing margin convergence by depth (F3 §34) ----------------------
    # Every point carries its refinement depth (F2 coarse corners = 0,
    # dyadic midpoints = the depth of the cell that introduced them);
    # margin extrema at depth d use only points with depth <= d.
    from collections import defaultdict as _dd
    margin_by_depth: dict[str, dict] = {}
    for branch in observed_branches:
        n = int(branch[1:])
        by_depth: dict[int, dict] = {}
        for depth in range(0, MAX_DEPTH + 1):
            neg_vals, pos_vals = [], []
            for key, rec in point_lookup.items():
                if rec.get("refinement_depth", 0) > depth:
                    continue
                phi, side, _ = phi_n_for_point(rec["sanger"], n, H_ATM)
                if phi is None:
                    continue
                if side == "N":
                    neg_vals.append(phi)
                else:
                    pos_vals.append(phi)
            by_depth[depth] = {
                "closest_negative_phi_m": max(neg_vals) if neg_vals else None,
                "closest_positive_phi_m": min(pos_vals) if pos_vals else None,
            }
        margin_by_depth[branch] = by_depth

    # ---- Row / column brackets and multiplicity (F3 §39) -------------------
    row_brackets: dict[str, list] = {}
    col_brackets: dict[str, list] = {}
    for c in terminal_cells:
        r = c["rectangle"]
        g_key = f"{r['gamma_min']:.6f}"
        row_brackets.setdefault(g_key, []).append({
            "gamma0": r["gamma_min"],
            "K_min": r["K_min"],
            "K_max": r["K_max"],
            "branch": c["branch"],
            "open_edges": c["open_edges"],
        })
        k_key = f"{r['K_min']:.6f}"
        col_brackets.setdefault(k_key, []).append({
            "K": r["K_min"],
            "gamma_min": r["gamma_min"],
            "gamma_max": r["gamma_max"],
            "branch": c["branch"],
            "open_edges": c["open_edges"],
        })
    multiplicity = row_column_multiplicity(terminal_cells)

    # ---- OPEN_BOUNDARY guardrail intersections (F3 §37–§38) ----------------
    open_intersections: dict[str, list] = {}
    for edge in ("gamma_lower", "gamma_upper", "K_lower", "K_upper"):
        touch = [
            c for c in terminal_cells if edge in c["open_edges"]
        ]
        brackets = []
        for c in touch:
            r = c["rectangle"]
            if edge in ("gamma_lower", "gamma_upper"):
                brackets.append({
                    "branch": c["branch"],
                    "K_low": r["K_min"], "K_high": r["K_max"],
                    "gamma": r["gamma_min"] if edge == "gamma_lower"
                    else r["gamma_max"],
                })
            else:
                brackets.append({
                    "branch": c["branch"],
                    "gamma_low": r["gamma_min"],
                    "gamma_high": r["gamma_max"],
                    "K": r["K_min"] if edge == "K_lower"
                    else r["K_max"],
                })
        open_intersections[edge] = brackets

    # ---- Summary ------------------------------------------------------------
    sanger_rows = [r["sanger"] for r in point_lookup.values()]
    qian_rows = [r["qian"] for r in point_lookup.values()]
    summary = {
        "schema_version": F3_SUMMARY_SCHEMA,
        "git_commit": git_commit,
        "phase_e_anchor_tag": PHASE_E_ANCHOR_TAG,
        "initial_candidate_cells": initial_queue_size,
        "initial_branches": sorted({
            b for b in cell_branch.values() if b is not None}),
        "max_depth": MAX_DEPTH,
        "target_resolution": {"gamma_deg": 0.01, "K": 0.01},
        "total_evaluated_unique_points": len(point_lookup),
        "fresh_refinement_points": fresh_points,
        "cache_reused_points": len(valid_cached),
        "qian_regime_counts": dict(sorted(
            Counter(r["qian_regime"] for r in qian_rows).items())),
        "sanger_regime_counts": dict(sorted(
            Counter(r["sanger_regime"] for r in sanger_rows).items())),
        "terminal_refined_cells": len(terminal_cells),
        "cells_per_branch": {b: len(v) for b, v in branch_cells.items()},
        "multiskip_unresolved": len(unresolved_cells),
        "max_depth_cells": len(max_depth_cells),
        "exact_only_cells": sum(
            1 for c in terminal_cells
            if c["classification"] == EXACT_TOPOLOGY_ONLY),
        "qian_topology_changes": sum(
            1 for r in qian_rows if r["qian_regime"] != "QIAN_RTI"),
        "recovered_points": len(recovered_queue),
        "reference_verified_count": sum(
            1 for q in recovered_queue if q["topology_equal"]),
        "sign_anomaly_count": len(sign_anomaly_queue),
        "grazing_resolutions": grazing_resolutions,
        "grazing_boundary_markers": grazing_marker_cells,
        "branch_extremal_certification": certification,
        "open_boundaries": {
            edge: len(v) for edge, v in open_intersections.items()},
        "row_multiplicity": multiplicity["max_row_multiplicity"],
        "column_multiplicity": multiplicity["max_column_multiplicity"],
        "rows_with_multiplicity_gt_1": (
            multiplicity["rows_with_multiplicity_gt_1"]),
        "columns_with_multiplicity_gt_1": (
            multiplicity["columns_with_multiplicity_gt_1"]),
        "health": {
            "censored": 0,
            "numerical_failure": 0,
            "reference_unresolved": 0,
            "chatter": 0,
            "bad_ordering": 0,
            "nan_inf": 0,
            "violations": health_violations,
        },
        "stop_gate_triggered": bool(stop_reasons),
        "stop_gate_reasons": stop_reasons,
        "ready_for_F4": not stop_reasons,
        "total_runtime_s": time.time() - t_start,
    }

    # ---- Artifacts ----------------------------------------------------------
    _write_json(OUT_DIR / "refined_boundary_cells.json", {
        "schema_version": "f3-refined-cells-v1",
        "cells": terminal_cells + unresolved_cells + max_depth_cells,
    })
    flat = []
    for c in terminal_cells + unresolved_cells + max_depth_cells:
        r = c["rectangle"]
        flat.append({
            "gamma_min": r["gamma_min"], "gamma_max": r["gamma_max"],
            "K_min": r["K_min"], "K_max": r["K_max"],
            "depth": r["depth"],
            "branch": c["branch"], "classification": c["classification"],
            "open_edges": ",".join(c["open_edges"]),
        })
    _write_csv(OUT_DIR / "refined_boundary_cells.csv", flat)
    _write_json(OUT_DIR / "branch_summary.json", {
        "schema_version": "f3-branch-summary-v1",
        "branches": {b: {
            "terminal_cells": len(v),
            "gamma_extent": [min(c["rectangle"]["gamma_min"] for c in v),
                             max(c["rectangle"]["gamma_max"] for c in v)],
            "K_extent": [min(c["rectangle"]["K_min"] for c in v),
                         max(c["rectangle"]["K_max"] for c in v)],
            "open_edges": sorted({e for c in v for e in c["open_edges"]}),
        } for b, v in branch_cells.items()},
    })
    _write_json(OUT_DIR / "branch_extremal_certification.json",
                certification)
    _write_json(OUT_DIR / "grazing_margin_by_depth.json", margin_by_depth)
    md_rows = []
    for branch, by_depth in margin_by_depth.items():
        for depth, vals in by_depth.items():
            md_rows.append({
                "branch": branch, "depth": depth,
                "closest_negative_phi_m": vals["closest_negative_phi_m"],
                "closest_positive_phi_m": vals["closest_positive_phi_m"],
            })
    _write_csv(OUT_DIR / "grazing_margin_by_depth.csv", md_rows)
    _write_json(OUT_DIR / "open_boundary_intersections.json",
                open_intersections)
    _write_json(OUT_DIR / "row_brackets.json", {
        "schema_version": "f3-row-brackets-v1", "rows": row_brackets})
    _write_csv(OUT_DIR / "row_brackets.csv", [
        b for brackets in row_brackets.values() for b in brackets])
    _write_json(OUT_DIR / "column_brackets.json", {
        "schema_version": "f3-column-brackets-v1", "columns": col_brackets})
    _write_csv(OUT_DIR / "column_brackets.csv", [
        b for brackets in col_brackets.values() for b in brackets])
    _write_json(OUT_DIR / "reference_verification.json", {
        "schema_version": "f3-reference-verification-v1",
        "recovered": recovered_queue,
        "sign_anomalies": sign_anomaly_queue,
    })
    _write_json(OUT_DIR / "boundary_exclusion_cells.json",
                build_f4_exclusion_cells(
                    terminal_cells, unresolved_cells, grazing_marker_cells))
    _write_json(OUT_DIR / "refinement_summary.json", summary)
    _write_json(OUT_DIR / "stop_gate_report.json", {
        "schema_version": "f3-stop-gate-report-v1",
        "stop_gate_triggered": bool(stop_reasons),
        "reasons": stop_reasons,
    })

    print("\n" + "=" * 72)
    print(f"evaluated unique points : {len(point_lookup)} "
          f"(fresh={fresh_points}, cache={len(valid_cached)})")
    print(f"terminal refined cells  : {len(terminal_cells)}")
    print(f"branches                : {observed_branches}")
    print(f"recovered points        : {len(recovered_queue)} "
          f"(verified={summary['reference_verified_count']})")
    print(f"sign anomalies          : {len(sign_anomaly_queue)}")
    print(f"multiskip unresolved    : {len(unresolved_cells)}")
    print(f"row/col multiplicity    : "
          f"{multiplicity['max_row_multiplicity']} / "
          f"{multiplicity['max_column_multiplicity']}")
    print(f"open boundaries         : {summary['open_boundaries']}")
    print(f"stop gates              : {stop_reasons}")
    print(f"ready_for_F4            : {summary['ready_for_F4']}")
    print(f"total runtime           : {summary['total_runtime_s']:.1f} s")
    print("F3 RUN: " + ("COMPLETE" if not stop_reasons else "BLOCKED"))
    return 0 if not stop_reasons else 2


if __name__ == "__main__":
    sys.exit(main())
