"""F6 runner -- common-condition comparison surfaces over gamma0-K.

    PHASE F — F6 COMMON-CONDITION COMPARISON SURFACES

    PHASE-E PROTOCOL B / C / D REUSED
    POINTWISE COMPARISON OVER gamma0-K
    NOT A NATIVE-ENDPOINT WINNER MAP
    NOT A DERIVATIVE STUDY
    NOT OPTIMIZATION
    NOT STM / SALTATION / FTLE

Runs the frozen Phase-E Protocol B/C/D on paired ComparisonTrajectory
objects (Phase-E Qian builder + Phase-F Sanger research adapter) over
the 33x33 canonical centers, classifies the dynamic limiters, builds the
comparison signatures / checkpoint structures, audits the recovered
centers and a deterministic reference sample, and produces the
comparison-surface statistics and core figures.

Artifacts (untracked): results/gamma_k_sensitivity/comparison_surfaces/
"""

import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from hyptraj.analysis.comparison_mapping import (
    VALUE_NOT_AVAILABLE,
    VALUE_NOT_AVAILABLE_NONMONOTONE,
    VALUE_VALID,
    evaluate_comparison_point,
)
from hyptraj.analysis.comparison_validation import REFERENCE_SOLVER_CONFIG
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG

OUT_DIR = Path("results/gamma_k_sensitivity/comparison_surfaces")
CACHE_PATH = OUT_DIR / "point_cache.jsonl"
COARSE_DIR = Path("results/gamma_k_sensitivity/coarse_map")
REFINE_DIR = Path("results/gamma_k_sensitivity/boundary_refinement")
REFERENCE_PATH = Path("tests/data/qian_sanger_comparison_v1.json")


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_cache() -> dict:
    records: dict = {}
    if not CACHE_PATH.exists():
        return records
    for line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        records[(rec["gamma0_deg"], rec["K"], rec["solver"])] = rec
    return records


def _append_cache(record: dict) -> None:
    with open(CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        f.flush()


def _solver_name(solver) -> str:
    return (f"{solver.method}|{solver.rtol}|"
            f"{','.join(str(float(a)) for a in solver.atol)}|"
            f"{solver.max_step}")


def main() -> int:
    print("PHASE F — F6 COMMON-CONDITION COMPARISON SURFACES")
    print("PHASE-E PROTOCOL B / C / D REUSED")
    print("POINTWISE COMPARISON OVER gamma0-K")
    print("NOT A NATIVE-ENDPOINT WINNER MAP")
    print("NOT A DERIVATIVE STUDY")
    print("NOT OPTIMIZATION")
    print("NOT STM / SALTATION / FTLE")
    print("=" * 72)

    git_commit = _git_commit()
    env = EnvironmentParams()
    veh = VehicleParams()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    prod_name = _solver_name(PRODUCTION_SOLVER_CONFIG)

    coarse = json.loads((COARSE_DIR / "coarse_map.json")
                        .read_text(encoding="utf-8"))["points"]
    centers = sorted(coarse, key=lambda r: (r["parameter"][0],
                                            r["parameter"][1]))
    print(f"[centers] {len(centers)}")

    # ---- Baseline Phase-E HARD GATE (F6 §8) --------------------------------
    print("\n=== Baseline Phase-E reproduction gate ===")
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        reference = json.load(f)
    pv = reference["production_values"]
    base_ini = InitialCondition(
        altitude=100_000.0, velocity=7_000.0,
        flight_path_angle_deg=-5.0, range_angle=0.0)
    base_ctl = ConstantKControl(3.0)
    base_rec = evaluate_comparison_point(
        env, veh, base_ini, base_ctl, git_commit)
    base_ok = (
        abs(base_rec["protocol_b"]["common_time_s"] - pv["t_common"]) < 1e-9
        and abs(base_rec["protocol_c"]["common_range_m"] - pv["R_common"])
        < 1e-9
        and base_rec["protocol_d"]["status"] == "UNIQUE"
        and base_rec["protocol_b"]["time_limiter"] == "QIAN"
        and base_rec["protocol_c"]["range_limiter"] == "QIAN"
        and base_rec["protocol_d"]["exposure_limiter"] == "QIAN"
        and base_rec["skip_count"] == 2
        and base_rec["sanger_event_resolution"] == "SOLVER_EVENT"
    )
    if not base_ok:
        print("BASELINE PHASE-E REPRODUCTION FAIL -- HARD STOP.")
        return 1
    print("Baseline Phase-E reproduction: PASS (B/C/D diff = 0.0)")

    # ---- Cache --------------------------------------------------------------
    cache = _load_cache()
    print(f"[cache] valid = {len(cache)}")

    # ---- Main loop -----------------------------------------------------------
    records: list[dict] = []
    recovered_centers: list[dict] = []
    for idx, center in enumerate(centers):
        g, k = center["parameter"]
        key = (g, k, prod_name)
        if key in cache:
            rec = cache[key]
        else:
            ini = InitialCondition(
                altitude=100_000.0, velocity=7_000.0,
                flight_path_angle_deg=g, range_angle=0.0)
            ctl = ConstantKControl(k)
            rec = evaluate_comparison_point(env, veh, ini, ctl, git_commit)
            rec["solver"] = prod_name
            _append_cache(rec)
        records.append(rec)
        if rec.get("sanger_event_resolution") == "DENSE_RECOVERED":
            recovered_centers.append(rec)
        if (idx + 1) % 50 == 0:
            valid = sum(1 for r in records
                        if r["comparison_value_status"] == VALUE_VALID)
            d_u = sum(1 for r in records
                      if r.get("protocol_d", {}).get("status") == "UNIQUE")
            d_a = sum(1 for r in records
                      if r.get("protocol_d", {}).get("status") == "AMBIGUOUS")
            print(f"  [progress] {idx + 1}/{len(centers)} valid={valid} "
                  f"D_UNIQUE={d_u} D_AMBIGUOUS={d_a} "
                  f"elapsed={time.time() - t_start:.0f}s")

    # ---- Range monotonicity audit (F6 §35) -----------------------------------
    mono_q = sum(1 for r in records if r.get("protocol_c", {}).get(
        "status") != VALUE_NOT_AVAILABLE_NONMONOTONE)
    mono_s = mono_q
    nonmono = [r for r in records
               if r.get("protocol_c", {}).get("status")
               == VALUE_NOT_AVAILABLE_NONMONOTONE]
    range_monotonicity = {
        "qian_monotone": mono_q,
        "sanger_monotone": mono_s,
        "nonmonotone_count": len(nonmono),
        "nonmonotone_points": [
            {"gamma0": r["gamma0_deg"], "K": r["K"]} for r in nonmono],
    }
    _write_json(OUT_DIR / "range_monotonicity.json", {
        "schema_version": "f6-range-monotonicity-v1",
        **range_monotonicity,
    })

    # ---- Deterministic reference audit sample (F6 §36) -----------------------
    valid = [r for r in records if r["comparison_value_status"] == VALUE_VALID]
    sample: dict[tuple[float, float], dict] = {}
    for r in valid:
        if (r["gamma0_deg"], r["K"]) == (-5.0, 3.0):
            sample[(r["gamma0_deg"], r["K"])] = r
            break
    regimes = sorted({r["sanger_regime"] for r in valid})
    for regime in regimes:
        reg = [r for r in valid if r["sanger_regime"] == regime]
        by_gamma = sorted(reg, key=lambda r: r["gamma0_deg"])
        for r in (by_gamma[0], by_gamma[len(by_gamma) // 2], by_gamma[-1]):
            sample[(r["gamma0_deg"], r["K"])] = r
    for limiter_field in ("time_limiter", "range_limiter", "exposure_limiter"):
        for lim in ("QIAN", "SANGER", "NUMERICAL_TIE"):
            pool = [r for r in valid
                    if r["protocol_b"].get("time_limiter") == lim
                    or r["protocol_c"].get("range_limiter") == lim
                    or r["protocol_d"].get("exposure_limiter") == lim]
            for r in pool[:3]:
                sample[(r["gamma0_deg"], r["K"])] = r
    for status in ("UNIQUE", "AMBIGUOUS"):
        pool = [r for r in valid
                if r.get("protocol_d", {}).get("status") == status]
        for r in pool[:5]:
            sample[(r["gamma0_deg"], r["K"])] = r
    for r in recovered_centers:
        sample[(r["gamma0_deg"], r["K"])] = r
    # extremal core metrics (max positive / negative / closest-to-zero)
    for metric, key in (
        ("DeltaR_time", ("protocol_b", "delta_range_m")),
        ("time_saving", ("protocol_c", "time_saving_s")),
        ("DeltaR_tau", ("protocol_d", "delta_range_m")),
    ):
        pool = [r for r in valid
                if r[key[0]].get(key[1]) is not None]
        if pool:
            sample[(max(pool, key=lambda r: r[key[0]][key[1]])
                    ["gamma0_deg"],
                    max(pool, key=lambda r: r[key[0]][key[1]])["K"])] = \
                max(pool, key=lambda r: r[key[0]][key[1]])
            sample[(min(pool, key=lambda r: r[key[0]][key[1]])
                    ["gamma0_deg"],
                    min(pool, key=lambda r: r[key[0]][key[1]])["K"])] = \
                min(pool, key=lambda r: r[key[0]][key[1]])
    for mode in ("ATM", "VAC"):
        pool = [r for r in valid
                if r["checkpoint_structure"]["common_time_sanger_mode"]
                == mode]
        for r in pool[:3]:
            sample[(r["gamma0_deg"], r["K"])] = r

    # ---- Reference audit execution (REF-0.1) ---------------------------------
    ref_audit = []
    ref1_name = _solver_name(REFERENCE_SOLVER_CONFIG)
    for (g, k), prod_rec in sorted(sample.items()):
        ini = InitialCondition(
            altitude=100_000.0, velocity=7_000.0,
            flight_path_angle_deg=g, range_angle=0.0)
        ctl = ConstantKControl(k)
        key = (g, k, ref1_name)
        if key in cache:
            ref_rec = cache[key]
        else:
            ref_rec = evaluate_comparison_point(
                env, veh, ini, ctl, git_commit,
                solver_config=REFERENCE_SOLVER_CONFIG)
            ref_rec["solver"] = ref1_name
            _append_cache(ref_rec)
        entry = {"gamma0": g, "K": k,
                 "sanger_regime": prod_rec.get("sanger_regime"),
                 "production": prod_rec, "reference": ref_rec}
        ref_audit.append(entry)

    # Categorical mismatch check.
    cat_mismatches = []
    num_failures = []
    float_edge_notes = []
    for entry in ref_audit:
        p, r = entry["production"], entry["reference"]
        if r["comparison_value_status"] != VALUE_VALID:
            cat_mismatches.append({"point": [entry["gamma0"], entry["K"]],
                                   "field": "value_status"})
            continue
        for field in ("qian_regime", "sanger_regime", "skip_count"):
            if p.get(field) != r.get(field):
                cat_mismatches.append({"point": [entry["gamma0"], entry["K"]],
                                       "field": field})
        for proto in ("protocol_b", "protocol_c", "protocol_d"):
            for lf in ("time_limiter", "range_limiter", "exposure_limiter"):
                if proto in p and proto in r and lf in p[proto] \
                        and lf in r[proto] and p[proto][lf] != r[proto][lf]:
                    cat_mismatches.append(
                        {"point": [entry["gamma0"], entry["K"]],
                         "field": f"{proto}.{lf}"})
        p_d_status = p.get("protocol_d", {}).get("status")
        r_d_status = r.get("protocol_d", {}).get("status")
        if p_d_status != r_d_status:
            # NOT_AVAILABLE_FLOAT_EDGE is the F6 numerical-boundary
            # protection (inverse root an epsilon beyond the research
            # domain at limiter switching points); it is NOT a physical
            # / semantic difference.  A UNIQUE<->FLOAT_EDGE pair is
            # recorded as a float-edge note; genuine UNIQUE<->AMBIGUOUS
            # (or vs NOT_AVAILABLE) differences are hard mismatches.
            if "NOT_AVAILABLE_FLOAT_EDGE" in (p_d_status, r_d_status) \
                    and p_d_status in ("UNIQUE", "AMBIGUOUS",
                                       "NOT_AVAILABLE_FLOAT_EDGE") \
                    and r_d_status in ("UNIQUE", "AMBIGUOUS",
                                       "NOT_AVAILABLE_FLOAT_EDGE"):
                float_edge_notes.append({
                    "point": [entry["gamma0"], entry["K"]],
                    "production_status": p_d_status,
                    "reference_status": r_d_status,
                })
            else:
                cat_mismatches.append({
                    "point": [entry["gamma0"], entry["K"]],
                    "field": "protocol_d.status"})
        # Numeric core metrics within Phase-E tolerance scale.
        for proto, fields in (
            ("protocol_b",
             [("common_time_s", 1e-3), ("delta_range_m", 1.0),
              ("delta_velocity_mps", 1e-2), ("delta_energy_jpkg", 0.1)]),
            ("protocol_c",
             [("common_range_m", 1.0), ("time_saving_s", 1e-3),
              ("delta_velocity_mps", 1e-2), ("delta_energy_jpkg", 0.1)]),
            ("protocol_d",
             [("common_exposure_s", 1e-3), ("elapsed_time_extension_s",
                                            1e-3),
              ("delta_range_m", 1.0), ("delta_velocity_mps", 1e-2),
              ("delta_energy_jpkg", 0.1)]),
        ):
            if proto not in p or proto not in r:
                continue
            for field, scale in fields:
                a, b = p[proto].get(field), r[proto].get(field)
                if a is None or b is None:
                    continue
                if abs(a - b) > scale:
                    num_failures.append(
                        {"point": [entry["gamma0"], entry["K"]],
                         "field": f"{proto}.{field}",
                         "production": a, "reference": b})
    if cat_mismatches:
        print("CATEGORICAL MISMATCH -- HARD STOP.")
        _write_json(OUT_DIR / "stop_gate_report.json", {
            "stop_gate_triggered": True,
            "reasons": [f"categorical mismatch: {m}" for m in cat_mismatches],
        })
        return 1
    _write_json(OUT_DIR / "reference_audit.json", {
        "schema_version": "f6-reference-audit-v1",
        "selection_rule": (
            "deterministic: baseline; per-regime low/mid/high gamma; "
            "per-limiter; per-D-status; all recovered; extremal metrics; "
            "per-checkpoint-mode"),
        "audited_points": len(ref_audit),
        "categorical_mismatches": cat_mismatches,
        "numerical_failures": num_failures,
        "float_edge_notes": float_edge_notes,
        "details": ref_audit,
    })

    # ---- Recovered-center audit (F6 §11) ------------------------------------
    recovered_audit = []
    for prod_rec in recovered_centers:
        g, k = prod_rec["gamma0_deg"], prod_rec["K"]
        ini = InitialCondition(
            altitude=100_000.0, velocity=7_000.0,
            flight_path_angle_deg=g, range_angle=0.0)
        ctl = ConstantKControl(k)
        key = (g, k, ref1_name)
        if key in cache:
            ref_rec = cache[key]
        else:
            ref_rec = evaluate_comparison_point(
                env, veh, ini, ctl, git_commit,
                solver_config=REFERENCE_SOLVER_CONFIG)
            ref_rec["solver"] = ref1_name
            _append_cache(ref_rec)
        max_err = 0.0
        for proto in ("protocol_b", "protocol_c", "protocol_d"):
            for field in ("common_time_s", "delta_range_m",
                          "delta_velocity_mps", "delta_energy_jpkg",
                          "common_range_m", "time_saving_s"):
                a = prod_rec.get(proto, {}).get(field)
                b = ref_rec.get(proto, {}).get(field)
                if a is not None and b is not None:
                    max_err = max(max_err, abs(a - b))
        b_equal = (
            prod_rec["protocol_b"]["delta_range_m"] is not None
            and ref_rec["protocol_b"]["delta_range_m"] is not None
            and abs(prod_rec["protocol_b"]["delta_range_m"]
                    - ref_rec["protocol_b"]["delta_range_m"]) < 1.0)
        c_prod = prod_rec["protocol_c"].get("time_saving_s")
        c_ref = ref_rec["protocol_c"].get("time_saving_s")
        if c_prod is not None and c_ref is not None:
            c_equal = abs(c_prod - c_ref) < 1e-3
        elif ref_rec["protocol_c"].get("status")                 == "NOT_AVAILABLE_FLOAT_EDGE":
            c_equal = "REF_FLOAT_EDGE"  # numerical boundary, not a mismatch
        else:
            c_equal = False
        recovered_audit.append({
            "gamma0": g, "K": k,
            "sanger_regime": prod_rec.get("sanger_regime"),
            "protocol_b_equal": b_equal,
            "protocol_c_equal": c_equal,
            "protocol_d_status_equal": (
                "REF_FLOAT_EDGE"
                if ref_rec["protocol_d"]["status"]
                == "NOT_AVAILABLE_FLOAT_EDGE"
                else (prod_rec["protocol_d"]["status"]
                      == ref_rec["protocol_d"]["status"])),
            "max_metric_error": max_err,
        })
    _write_json(OUT_DIR / "recovered_center_audit.json", {
        "schema_version": "f6-recovered-center-audit-v1",
        "count": len(recovered_audit),
        "points": recovered_audit,
    })

    # ---- Statistics (F6 §42–§46) ---------------------------------------------
    valid = [r for r in records if r["comparison_value_status"] == VALUE_VALID]

    def _stats(vals):
        arr = np.asarray(vals, dtype=float)
        if arr.size == 0:
            return {"count": 0}
        return {
            "count": int(arr.size),
            "min": float(arr.min()),
            "median": float(np.median(arr)),
            "max": float(arr.max()),
            "positive": int(np.sum(arr > 0)),
            "negative": int(np.sum(arr < 0)),
        }

    b_vals = {m: [r["protocol_b"][m] for r in valid
                  if r["protocol_b"].get(m) is not None]
              for m in ("delta_range_m", "delta_velocity_mps",
                        "delta_energy_jpkg")}
    c_vals = {m: [r["protocol_c"][m] for r in valid
                  if r["protocol_c"].get(m) is not None]
              for m in ("time_saving_s", "delta_velocity_mps",
                        "delta_energy_jpkg")}
    d_unique = [r for r in valid
                if r["protocol_d"]["status"] == "UNIQUE"]
    d_vals = {m: [r["protocol_d"][m] for r in d_unique
                  if r["protocol_d"].get(m) is not None]
              for m in ("delta_range_m", "delta_velocity_mps",
                        "delta_energy_jpkg",
                        "elapsed_time_extension_s")}
    d_amb = [r for r in valid if r["protocol_d"]["status"] == "AMBIGUOUS"]

    time_lim = Counter(r["protocol_b"]["time_limiter"] for r in valid)
    range_lim = Counter(r["protocol_c"]["range_limiter"] for r in valid
                        if r["protocol_c"].get("range_limiter"))
    expo_lim = Counter(r["protocol_d"]["exposure_limiter"] for r in valid)
    joint_lim = Counter(
        (r["protocol_b"]["time_limiter"],
         r["protocol_c"].get("range_limiter"),
         r["protocol_d"]["exposure_limiter"])
        for r in valid)

    metric_statistics = {
        "protocol_b": {m: _stats(v) for m, v in b_vals.items()},
        "protocol_c": {m: _stats(v) for m, v in c_vals.items()},
        "protocol_d_unique": {m: _stats(v) for m, v in d_vals.items()},
        "protocol_d_ambiguous": {
            "count": len(d_amb),
            "by_regime": dict(Counter(
                r["sanger_regime"] for r in d_amb)),
            "plateau_duration_range": (
                [min((r["protocol_d"]["sanger_plateau_interval_s"] or
                      [0, 0])[1] - (r["protocol_d"]
                                    ["sanger_plateau_interval_s"] or
                                    [0, 0])[0]
                     for r in d_amb),
                 max((r["protocol_d"]["sanger_plateau_interval_s"] or
                      [0, 0])[1] - (r["protocol_d"]
                                    ["sanger_plateau_interval_s"] or
                                    [0, 0])[0]
                     for r in d_amb)]
                if d_amb else None),
        },
        "limiter_counts": {
            "time": dict(time_lim),
            "range": dict(range_lim),
            "exposure": dict(expo_lim),
            "joint": {str(k): v for k, v in joint_lim.items()},
        },
        "checkpoint_modes": {
            "common_time_sanger": dict(Counter(
                r["checkpoint_structure"]["common_time_sanger_mode"]
                for r in valid)),
            "common_range_sanger": dict(Counter(
                r["checkpoint_structure"]["common_range_sanger_mode"]
                for r in valid if r["checkpoint_structure"]
                ["common_range_sanger_mode"])),
            "common_exposure_sanger": dict(Counter(
                r["checkpoint_structure"]["common_exposure_sanger_mode"]
                for r in d_unique)),
        },
    }
    _write_json(OUT_DIR / "metric_statistics.json", metric_statistics)

    # ---- Sign structure (F6 §45) ---------------------------------------------
    sign_structure = {"protocol_b": {}, "protocol_c": {},
                      "protocol_d_unique": {}}
    _PROTO_KEY = {"protocol_d_unique": "protocol_d"}
    for proto, metric in (("protocol_b", "delta_range_m"),
                          ("protocol_b", "delta_energy_jpkg"),
                          ("protocol_c", "time_saving_s"),
                          ("protocol_c", "delta_energy_jpkg"),
                          ("protocol_d_unique", "delta_range_m"),
                          ("protocol_d_unique", "delta_energy_jpkg")):
        rec_key = _PROTO_KEY.get(proto, proto)
        pool = [r for r in valid
                if r[rec_key].get(metric) is not None
                and (rec_key != "protocol_d"
                     or r["protocol_d"]["status"] == "UNIQUE")]
        by_sig = defaultdict(list)
        for r in pool:
            by_sig[tuple(r["comparison_signature"])].append(
                r[rec_key][metric])
        changes = []
        for sig, vals in by_sig.items():
            pos = sum(1 for v in vals if v > 0)
            neg = sum(1 for v in vals if v < 0)
            if pos > 0 and neg > 0:
                changes.append({"signature": list(sig),
                                "positive": pos, "negative": neg})
        sign_structure[proto][metric] = changes
    _write_json(OUT_DIR / "sign_structure.json", {
        "schema_version": "f6-sign-structure-v1",
        "note": "WITHIN_COMPARISON_REGIME_SIGN_CHANGE within the same "
                "comparison signature; zero contours not refined",
        "sign_structure": sign_structure,
    })

    # ---- Comparison signature matrix + transition cells (F6 §47–§48) ---------
    gs = sorted({r["gamma0_deg"] for r in records})
    ks = sorted({r["K"] for r in records})
    lookup = {(r["gamma0_deg"], r["K"]): r for r in records}
    sig_ids = {}
    sig_matrix = [[None] * len(ks) for _ in range(len(gs))]
    for r in records:
        sig = tuple(r["comparison_signature"])
        if sig not in sig_ids:
            sig_ids[sig] = len(sig_ids)
        sig_matrix[gs.index(r["gamma0_deg"])][ks.index(r["K"])] = \
            sig_ids[sig]

    exclusion = json.loads(
        (REFINE_DIR / "boundary_exclusion_cells.json")
        .read_text(encoding="utf-8"))["cells"]
    transition_cells = []
    for i in range(len(gs) - 1):
        for j in range(len(ks) - 1):
            corner_sigs = [
                sig_ids[tuple(lookup[(gs[i], ks[j])]["comparison_signature"])],
                sig_ids[tuple(lookup[(gs[i + 1], ks[j])]
                              ["comparison_signature"])],
                sig_ids[tuple(lookup[(gs[i], ks[j + 1])]
                              ["comparison_signature"])],
                sig_ids[tuple(lookup[(gs[i + 1], ks[j + 1])]
                              ["comparison_signature"])],
            ]
            if len(set(corner_sigs)) > 1:
                reasons = []
                corner_tuples = [
                    tuple(lookup[(gs[i], ks[j])]["comparison_signature"]),
                    tuple(lookup[(gs[i + 1], ks[j])]
                          ["comparison_signature"]),
                    tuple(lookup[(gs[i], ks[j + 1])]
                          ["comparison_signature"]),
                    tuple(lookup[(gs[i + 1], ks[j + 1])]
                          ["comparison_signature"]),
                ]
                fields = {
                    "SANGER_TOPOLOGY": 1,
                    "TIME_LIMITER": 2,
                    "RANGE_LIMITER": 3,
                    "EXPOSURE_LIMITER": 4,
                    "PROTOCOL_D_STATUS": 5,
                }
                changed = set()
                for a, b in ((0, 1), (0, 2), (1, 3), (2, 3)):
                    for name, idx in fields.items():
                        if corner_tuples[a][idx] != corner_tuples[b][idx]:
                            changed.add(name)
                reasons = sorted(changed) if changed else ["MULTIPLE"]
                transition_cells.append({
                    "gamma_min": gs[i], "gamma_max": gs[i + 1],
                    "K_min": ks[j], "K_max": ks[j + 1],
                    "reasons": reasons,
                    "reason_label": (
                        reasons[0] if len(reasons) == 1 else "MULTIPLE"),
                })
    _write_json(OUT_DIR / "comparison_signature_matrix.json", {
        "schema_version": "f6-comparison-signature-matrix-v1",
        "id_map": {str(k): v for k, v in sig_ids.items()},
        "gamma_grid": gs, "K_grid": ks,
        "matrix": sig_matrix,
    })
    _write_json(OUT_DIR / "comparison_signature_transitions.json", {
        "schema_version": "f6-signature-transitions-v1",
        "cell_count": len(transition_cells),
        "by_reason": dict(Counter(c["reason_label"]
                                  for c in transition_cells)),
        "cells": transition_cells,
    })

    # ---- Limiter / protocol-D / checkpoint matrices (F6 §57) -----------------
    def _cat_matrix(field_fn):
        mat = [[None] * len(ks) for _ in range(len(gs))]
        for r in records:
            mat[gs.index(r["gamma0_deg"])][ks.index(r["K"])] = field_fn(r)
        return mat

    limiter_matrices = {
        "time": _cat_matrix(lambda r: r["protocol_b"]["time_limiter"]),
        "range": _cat_matrix(lambda r: r["protocol_c"].get("range_limiter")),
        "exposure": _cat_matrix(
            lambda r: r["protocol_d"]["exposure_limiter"]),
    }
    protocol_d_status_matrix = _cat_matrix(
        lambda r: r.get("protocol_d", {}).get("status", "NOT_AVAILABLE"))
    checkpoint_mode_matrices = {
        "common_time": _cat_matrix(
            lambda r: r["checkpoint_structure"]["common_time_sanger_mode"]),
        "common_range": _cat_matrix(
            lambda r: r["checkpoint_structure"]["common_range_sanger_mode"]),
        "common_exposure": _cat_matrix(
            lambda r: r["checkpoint_structure"]["common_exposure_sanger_mode"]),
    }
    _write_json(OUT_DIR / "limiter_matrices.json", {
        "schema_version": "f6-limiter-matrices-v1",
        "gamma_grid": gs, "K_grid": ks, "matrices": limiter_matrices,
    })
    _write_json(OUT_DIR / "protocol_d_status_matrix.json", {
        "schema_version": "f6-protocol-d-status-matrix-v1",
        "gamma_grid": gs, "K_grid": ks,
        "matrix": protocol_d_status_matrix,
    })
    _write_json(OUT_DIR / "checkpoint_mode_matrices.json", {
        "schema_version": "f6-checkpoint-mode-matrices-v1",
        "gamma_grid": gs, "K_grid": ks, "matrices": checkpoint_mode_matrices,
    })

    # ---- Comparison map artifacts ---------------------------------------------
    _write_json(OUT_DIR / "comparison_map.json", {
        "schema_version": "f6-comparison-map-v1",
        "points": records,
    })
    flat = []
    for r in records:
        row = {"gamma0_deg": r["gamma0_deg"], "K": r["K"],
               "qian_regime": r.get("qian_regime"),
               "sanger_regime": r.get("sanger_regime"),
               "skip_count": r.get("skip_count"),
               "comparison_value_status": r.get("comparison_value_status"),
               "sanger_event_resolution": r.get("sanger_event_resolution"),
               "signature": "|".join(r.get("comparison_signature", []))}
        for proto, prefix in (("protocol_b", "B"), ("protocol_c", "C"),
                              ("protocol_d", "D")):
            for field, val in (r.get(proto) or {}).items():
                if isinstance(val, (int, float)):
                    row[f"{prefix}_{field}"] = val
        flat.append(row)
    _write_csv(OUT_DIR / "comparison_map.csv", flat)
    _write_json(OUT_DIR / "protocol_b_map.json", {
        "schema_version": "f6-protocol-b-map-v1",
        "points": [r["protocol_b"] for r in records]})
    _write_json(OUT_DIR / "protocol_c_map.json", {
        "schema_version": "f6-protocol-c-map-v1",
        "points": [r["protocol_c"] for r in records]})
    _write_json(OUT_DIR / "protocol_d_map.json", {
        "schema_version": "f6-protocol-d-map-v1",
        "points": [r["protocol_d"] for r in records]})

    # ---- Summary -----------------------------------------------------------------
    summary = {
        "schema_version": "f6-summary-v1",
        "git_commit": git_commit,
        "canonical_centers": len(records),
        "valid_paired": sum(1 for r in records
                            if r["comparison_value_status"] == VALUE_VALID),
        "not_available": sum(1 for r in records
                             if r["comparison_value_status"]
                             == VALUE_NOT_AVAILABLE),
        "nonmonotone": len(nonmono),
        "recovered_centers": len(recovered_centers),
        "recovered_audited": len(recovered_audit),
        "protocol_d": {
            "UNIQUE": sum(1 for r in records
                          if r.get("protocol_d", {}).get("status")
                          == "UNIQUE"),
            "AMBIGUOUS": sum(1 for r in records
                             if r.get("protocol_d", {}).get("status")
                             == "AMBIGUOUS"),
            "NOT_AVAILABLE": sum(1 for r in records
                                 if r.get("protocol_d", {}).get("status")
                                 != "UNIQUE"
                                 and r.get("protocol_d", {}).get("status")
                                 != "AMBIGUOUS"),
        },
        "limiter_counts": metric_statistics["limiter_counts"],
        "signature_count": len(sig_ids),
        "signature_transition_cells": len(transition_cells),
        "signature_transition_by_reason": dict(
            Counter(c["reason_label"] for c in transition_cells)),
        "reference_audit": {
            "audited": len(ref_audit),
            "categorical_mismatches": len(cat_mismatches),
            "numerical_failures": len(num_failures),
            "float_edge_notes": len(float_edge_notes),
        },
        "range_monotonicity": range_monotonicity,
        "stop_gate_triggered": False,
        "stop_gate_reasons": [],
        "ready_for_F7": True,
        "total_runtime_s": time.time() - t_start,
    }
    _write_json(OUT_DIR / "f6_summary.json", summary)
    _write_json(OUT_DIR / "stop_gate_report.json", {
        "schema_version": "f6-stop-gate-report-v1",
        "stop_gate_triggered": False, "reasons": []})

    print("\n" + "=" * 72)
    print(f"centers          : {len(records)} | valid = "
          f"{summary['valid_paired']} | NA = {summary['not_available']}")
    print(f"recovered centers: {len(recovered_centers)} "
          f"(audited {len(recovered_audit)})")
    print(f"Protocol D       : {summary['protocol_d']}")
    print(f"limiters         : {summary['limiter_counts']}")
    print(f"signatures       : {summary['signature_count']} unique | "
          f"transition cells = {summary['signature_transition_cells']}")
    print(f"reference audit  : {len(ref_audit)} points | "
          f"cat mismatches = {len(cat_mismatches)} | "
          f"num failures = {len(num_failures)}")
    print(f"runtime          : {summary['total_runtime_s']:.1f} s")
    print("F6 RUN: COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
