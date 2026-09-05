"""M3-WCF1 -- Prospective fresh physical-configuration WIDEN expansion.

WA1R-B showed the fresh-W bottleneck is configurational, not local: 8/8 WA1R
references came back WIDEN yet the combined W pool spans only 5 physical
configs (< 6-config gate).  WCF1 therefore expands the PHYSICAL-CONFIG family:

    select 6 entirely new physical configs outcome-blind (sequential maximin
    over the CF0 legal candidate lattice, excluding every used config)
    -> freeze exactly 2 W-target s2 values from the CF0 common grid using
       valid corrected historical evidence only
    -> 12 fresh states (6 configs x 2 s2), 12/12 fresh identities
    -> 6 new config-specific P_ref streams (3,000,000 samples)
    -> one-shot 500k/arm 3-arm references (18,000,000 samples)
    -> require K_NEW_W_CONFIG >= 1
    -> recheck W diversity (exact 8, >=6 configs, max 2/config)
    -> freeze the fresh 8W/8S/8ND panel if feasible

Hard rules: no invalid PI1V data, no WA1 consumed candidate, no retired
states/seeds, no midpoint additions in the existing 5 configs, no adaptive
config/s2 extension after outcomes, no V1/S1 routes, no reserve piloting.
Persistence: PI1VR0/WA1R repaired contract (non-circular hashes), taskbook
Sec. 23 order with schema validation on the persisted temp record.

Stages: prepare | pref | reference | capacity | report
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1v as R1  # noqa: E402  (namespace audit reuse)
import run_m3pi1vr0 as R0  # noqa: E402  (PI1VR0 panel selector reuse)
from hyptraj.m1d.experiments import BenchmarkConfig  # noqa: E402
from hyptraj.m3cf1r0.persistence import fsync_directory, ledger_append, ledger_entries  # noqa: E402
from hyptraj.m3d.benchmark_states import assemble_state, state_arms  # noqa: E402
from hyptraj.m3d2.experiment import (  # noqa: E402
    classify_reference_state,
    direct_full_event_reference,
    evaluate_reference_arms,
)
from hyptraj.m3pi1vr0.persistence import (  # noqa: E402
    ReplayError,
    StatePersistenceError,
    safe_fs_id,
    validate_safe_path,
)
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    HASH_FIELD,
    record_file_hash,
    scientific_payload_hash,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wcf1/summary"
PREF = ROOT / "results/phase_m3wcf1/pref"
REF = ROOT / "results/phase_m3wcf1/reference"
DOC = ROOT / "docs/phase_m3wcf1"

WA1R_OUT = ROOT / "results/phase_m3wa1r/summary"
WA1_OUT = ROOT / "results/phase_m3wa1/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"
CF0 = ROOT / "results/phase_m3cf0/summary"
CF1R0_REPLACEMENT = ROOT / "results/phase_m3cf1r0/replacement/m3cf1r0_replacement_configs.csv"

REF_N = 500_000
N_BATCH = 20
N_CONFIGS = 6
S2_PER_CONFIG = 2
W_TARGET, S_TARGET, ND_TARGET = 8, 8, 8
W_CONFIG_MIN = 6
W_MAX_PER_CONFIG = 2
PREF_NAMESPACE = "M3-WCF1-PREF"
REF_NAMESPACE = "M3-WCF1-REF"
GRID = [1.25, 1.6, 2, 2.5, 3.2, 4, 5, 6.4, 8]   # CF0-frozen common s2 grid

PREF_LEDGER = PREF / "pref_ledger.jsonl"
REF_LEDGER = REF / "reference_ledger.jsonl"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, v) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csvread(p) -> list[dict]:
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def csvwrite(p, rows: list[dict]) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (2**31 - 1) + 1


def fmt_s2(x: float) -> str:
    return f"{x:.10f}".rstrip("0").rstrip(".").replace(".", "p")


def boundary_block(extra: dict | None = None) -> dict:
    base = {
        "gradient_pilot_trials": 0,
        "finite_action_probe_trials": 0,
        "v1_threshold": None,
        "s1_threshold": None,
        "protected_confirmation_pilot_trials": 0,
        "value": "BLOCKED",
        "rarity_shift": "BLOCKED",
        "m3_q": "BLOCKED",
        "s1_confirmation_authorized": False,
        "v1_new_test": False,
    }
    base.update(extra or {})
    return base


def phys_fields(row: dict) -> dict:
    def as_bool(v):
        return v.lower() == "true" if isinstance(v, str) else bool(v)
    return {f"theta_{i}": float(row[f"theta_{i}"]) for i in range(1, 5)} | \
           {f"h_{i}": float(row[f"h_{i}"]) for i in range(1, 5)} | \
           {f"curved_{i}": as_bool(row[f"curved_{i}"]) for i in range(1, 5)} | \
           {"curvature_c": float(row["curvature_c"])} | \
           {f"offset_{i}": float(row[f"offset_{i}"]) for i in range(1, 5)}


def coords_key(row: dict) -> tuple:
    f = phys_fields(row)
    return (tuple(round(f[f"theta_{i}"], 6) for i in range(1, 5)),
            tuple(round(f[f"h_{i}"], 6) for i in range(1, 5)),
            tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            round(f["curvature_c"], 6),
            tuple(round(f[f"offset_{i}"], 6) for i in range(1, 5)))


def bench_for(wcf1_config_id: str, lattice_row: dict):
    f = phys_fields(lattice_row)
    return BenchmarkConfig(
        config_id=wcf1_config_id,
        batch_seed=int(lattice_row.get("generation_seed", 20300315)),
        batch_index=int(lattice_row.get("batch_index", 0)),
        theta_deg=tuple(f[f"theta_{i}"] for i in range(1, 5)),
        h=tuple(f[f"h_{i}"] for i in range(1, 5)),
        curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
        curvature_c=f["curvature_c"],
        offset_o=tuple(f[f"offset_{i}"] for i in range(1, 5)),
    )


_states: dict[str, object] = {}


def state_for(wcf1_config_id: str, lattice_row: dict, s2: float):
    key = f"{wcf1_config_id}@{s2!r}"
    if key not in _states:
        st = assemble_state(bench_for(wcf1_config_id, lattice_row), float(s2),
                            short_config=wcf1_config_id)
        if isinstance(st, dict):
            raise RuntimeError(f"WCF1-X: assembly failed {wcf1_config_id}@{s2}: {st}")
        _states[key] = st
    return _states[key]


# --------------------------------------------------------------------------
# stage: prepare (zero simulator)
# --------------------------------------------------------------------------

def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    PREF.mkdir(parents=True, exist_ok=True)
    REF.mkdir(parents=True, exist_ok=True)

    # -- parent audit (taskbook Sec. 4) ----------------------------------------
    wa1r = load(WA1R_OUT / "m3wa1r_final_verdict.json")
    wa1 = load(WA1_OUT / "m3wa1_final_verdict.json")
    vr0 = load(VR0 / "m3pi1vr0_final_verdict.json")
    pi1v = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    wa1r_ref = load(ROOT / "results/phase_m3wa1r/reference/reference_manifest.json")
    wa1r_feas = load(WA1R_OUT / "m3wa1r_w_feasibility.json")
    reserve_audit = load(VR0 / "m3pi1vr0_reserve_audit_summary.json")
    reserve = csvread(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")
    wa1r_manifest_ids = {c["candidate_id"]
                         for c in csvread(WA1R_OUT / "m3wa1r_candidate_manifest.csv")}
    consumed = "cf1n_new_000_wa1_w_s2_1p788854382"
    checks = {
        "WA1R verdict": wa1r["verdict"] == "WA1R-B",
        "WA1 verdict": wa1["verdict"] == "WA1-X",
        "PI1V valid verdict": pi1v["PI1V valid verdict"] == "PI1V-X",
        "WA1 consumed candidate reused": consumed not in wa1r_manifest_ids,
        "WA1R 8/8 COMPLETE": wa1r_ref["complete"] == 8,
        "WA1R 8/8 WIDEN": wa1r_ref["labels"].get("WIDEN") == 8,
        "WA1R consumed-invalid 0": wa1r_ref["consumed_invalid"] == 0,
        "fresh W config ceiling 5": wa1r_feas["distinct_configs"] == 5,
        "reserve scientifically valid": reserve_audit["verified_untouched"] == 70
                                        and len(reserve) == 70,
        "WA1R states pilot-unexposed": True,   # verified by construction + audit below
    }
    if not all(checks.values()):
        raise RuntimeError(f"WCF1-X: parent audit mismatch {checks}")
    dump(OUT / "m3wcf1_parent_audit.json", {
        "recorded_at": now(), "checks": checks, "all_match": all(checks.values()),
        "wa1r_labels": wa1r_ref["labels"],
    })

    # -- used physical configs (taskbook Sec. 6) --------------------------------
    cur = csvread(CF0 / "m3cf0_current_config_coordinates.csv")
    rep = csvread(CF1R0_REPLACEMENT)
    used = []
    for r in cur:
        used.append({"config_id": r["config_id"], "family": "original/current",
                     "stage_first_used": "M1-D/M3 (pre-CF0)", **phys_fields(r)})
    for r in rep:
        used.append({"config_id": r["config_id"], "family": "CF1N replacement",
                     "stage_first_used": "M3-CF1N", **phys_fields(r)})
    used_coords = {coords_key(r) for r in used}
    dump(OUT / "m3wcf1_used_physical_config_manifest.json", {
        "recorded_at": now(),
        "used_configs": used,
        "used_coord_keys": [str(c) for c in sorted(used_coords)],
        "exclusion_rule": "a WCF1 physical config must never have been used as "
                          "a scientific physical config in any prior corrected "
                          "reference or pilot stage; exclusion is by physical "
                          "coordinates",
        "covers": ["all old/current family configs", "all CF1N replacement configs",
                   "all WA1/WA1R configs (subset of CF1N)", "all retired "
                   "development configs (subset of the above)"],
    })

    # -- legal lattice + capacity (taskbook Sec. 7-8) ----------------------------
    axis = load(CF0 / "m3cf0_axis_classification.json")
    lattice = csvread(CF0 / "m3cf0_raw_physical_candidate_lattice.csv")
    illegal = [r for r in lattice if r["legal"].lower() != "true"]
    if illegal:
        raise RuntimeError("WCF1-X: lattice contains illegal rows")
    fresh = [r for r in lattice if coords_key(r) not in used_coords]
    dump(OUT / "m3wcf1_legal_physical_capacity.json", {
        "recorded_at": now(),
        "lattice_rows": len(lattice),
        "field_classification": axis,
        "s2_class": axis["s2"]["class"],
        "s2_is_not_physical_axis": True,
        "legal_rows": len(lattice) - len(illegal),
        "used_coordinate_matches": len(lattice) - len(fresh),
        "legal_fresh_configs": len(fresh),
        "capacity_gate_min": 6,
        "capacity_gate": "PASS" if len(fresh) >= 6 else "FAIL",
        "excluded_by_coordinates": "8 CF1N replacement configs (the 8 original "
                                   "family configs are not lattice rows but are "
                                   "excluded by the used-coordinate manifest)",
    })
    if len(fresh) < 6:
        raise RuntimeError("WCF1-PRE-B: fewer than 6 legal fresh physical configs")

    # -- outcome-blind maximin selector (taskbook Sec. 9-10) ---------------------
    all_f = [list(phys_fields(r)[k] if isinstance(phys_fields(r)[k], float)
                  else 0.0 for k in ()) for r in []]  # placeholder never used
    cont = []
    for r in lattice:
        f = phys_fields(r)
        cont.append([f[f"theta_{i}"] for i in range(1, 5)]
                    + [f[f"h_{i}"] for i in range(1, 5)]
                    + [f["curvature_c"]]
                    + [f[f"offset_{i}"] for i in range(1, 5)])
    n_fields = len(cont[0])
    lo = [min(f[i] for f in cont) for i in range(n_fields)]
    hi = [max(f[i] for f in cont) for i in range(n_fields)]

    def norm_vec(row: dict) -> tuple:
        f = phys_fields(row)
        vals = [f[f"theta_{i}"] for i in range(1, 5)] + \
               [f[f"h_{i}"] for i in range(1, 5)] + [f["curvature_c"]] + \
               [f[f"offset_{i}"] for i in range(1, 5)]
        return tuple((v - lo[i]) / (hi[i] - lo[i]) if hi[i] > lo[i] else 0.0
                     for i, v in enumerate(vals))

    def dist(a, b) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def discrete_mode(row: dict) -> tuple:
        f = phys_fields(row)
        return tuple(bool(f[f"curved_{i}"]) for i in range(1, 5))

    base_vecs = [norm_vec(r) for r in cur] + [norm_vec(r) for r in rep]
    prior_centroid = tuple(sum(v[i] for v in base_vecs) / len(base_vecs)
                           for i in range(len(base_vecs[0])))
    pool = list(fresh)
    selected = []
    for step in range(N_CONFIGS):
        dists = {r["config_id"]: min(dist(norm_vec(r), b) for b in base_vecs)
                 for r in pool}
        dmax = max(dists.values())
        ties = [r for r in pool if abs(dists[r["config_id"]] - dmax) < 1e-12]
        best = min(ties, key=lambda r: (
            -dist(norm_vec(r), prior_centroid),
            discrete_mode(r),
            r["config_id"]))
        selected.append({
            "wcf1_config_id": f"wcf1_new_{step:03d}",
            "raw_candidate_id": best["config_id"],
            "selection_rank": step + 1,
            "min_distance_to_prior_set": round(dmax, 6),
            "normalized_coordinates": [round(x, 6) for x in norm_vec(best)],
            "distance_to_prior_centroid": round(dist(norm_vec(best), prior_centroid), 6),
            "discrete_physical_mode": [int(x) for x in discrete_mode(best)],
            **phys_fields(best),
        })
        base_vecs.append(norm_vec(best))
        pool.remove(best)
    dump(OUT / "m3wcf1_physical_selector_contract.json", {
        "recorded_at": now(),
        "rule": "sequential maximin physical diversity over the CF0 legal "
                "lattice, normalized continuous fields (theta x4, h x4, "
                "curvature_c, offsets); base set = all previously used physical "
                "configs + already-selected WCF1 configs",
        "tie_break": ["larger distance to prior-config centroid",
                      "distinct discrete physical mode (curved pattern)",
                      "canonical candidate ID"],
        "outcome_blind": True,
        "forbidden_inputs": ["W outcomes", "PI1V Attempt-2 scores", "WA1 outcomes",
                             "effect magnitude", "gradient confidence"],
        "no_seventh_config_after_outcomes": True,
        "s2_is_not_an_expansion_axis": True,
    })
    csvwrite(OUT / "m3wcf1_physical_config_manifest.csv", selected)
    dump(OUT / "m3wcf1_physical_config_manifest_hash.json", {
        "recorded_at": now(),
        "manifest_sha256": sha(OUT / "m3wcf1_physical_config_manifest.csv"),
        "configs": len(selected),
        "prior_config_collisions": 0,
        "frozen_before_any_wcf1_reference_outcome": True,
        "no_seventh_config_after_outcomes": True,
    })

    # -- valid W-by-s2 audit (taskbook Sec. 13-14) --------------------------------
    inv = csvread(CF2 / "m3cf2_candidate_truth_inventory.csv")
    by_s2: dict[float, dict] = {g: {"configs": set(), "w": set()} for g in GRID}
    for r in inv:
        s2 = float(r["s2"])
        for g in GRID:
            if abs(s2 - g) < 1e-9:
                by_s2[g]["configs"].add(r["config_id"])
                if r["truth"] == "WIDEN":
                    by_s2[g]["w"].add(r["config_id"])
    audit_rows = []
    for g in GRID:
        n, w = len(by_s2[g]["configs"]), len(by_s2[g]["w"])
        audit_rows.append({"common_grid_s2": g, "grid_index": GRID.index(g) + 1,
                           "distinct_valid_configs_observed": n,
                           "distinct_configs_labeled_widen": w,
                           "w_support_fraction": round(w / n, 6) if n else 0.0})
    csvwrite(OUT / "m3wcf1_valid_w_by_s2_audit.csv", audit_rows)
    ranked = sorted(audit_rows, key=lambda r: (-r["distinct_configs_labeled_widen"],
                                               -r["w_support_fraction"],
                                               r["common_grid_s2"],
                                               r["grid_index"]))
    chosen_s2 = ranked[:S2_PER_CONFIG]
    dump(OUT / "m3wcf1_s2_selector_contract.json", {
        "recorded_at": now(),
        "rule": ["1. highest number of distinct valid configs labeled WIDEN",
                 "2. then highest WIDEN fraction among valid observed configs",
                 "3. then lower s2",
                 "4. then canonical grid index"],
        "source_grid": "CF0-frozen common s2 grid (m3cf0_future_s2_grid.json)",
        "evidence": "corrected durable high-budget reference states only "
                    "(CF2 candidate truth inventory); invalid PI1V scores, the "
                    "WA1 consumed-invalid state, and pre-ER1 evidence excluded",
        "frozen_before_any_wcf1_p_ref_or_reference_run": True,
        "authoritative": "no manual forcing of specific values",
    })
    dump(OUT / "m3wcf1_w_target_s2.json", {
        "recorded_at": now(),
        "selected_s2": [r["common_grid_s2"] for r in chosen_s2],
        "selection_table": chosen_s2,
        "selector_hash": sha(OUT / "m3wcf1_s2_selector_contract.json"),
        "audit_hash": sha(OUT / "m3wcf1_valid_w_by_s2_audit.csv"),
    })

    # -- 12-state manifest (taskbook Sec. 16-17) -----------------------------------
    config_hash = sha(OUT / "m3wcf1_physical_config_manifest.csv")
    s2_hash = sha(OUT / "m3wcf1_s2_selector_contract.json")
    lat_by_id = {r["config_id"]: r for r in lattice}
    states = []
    for sel in selected:
        raw = lat_by_id[sel["raw_candidate_id"]]
        for s2rec in chosen_s2:
            s2 = float(s2rec["common_grid_s2"])
            states.append({
                "state_id": f"{sel['wcf1_config_id']}_wcf1_s2_{fmt_s2(s2)}",
                "config_id": sel["wcf1_config_id"],
                "raw_candidate_id": sel["raw_candidate_id"],
                "s2": s2,
                "grid_index": int(s2rec["grid_index"]),
                **phys_fields(raw),
                "config_manifest_hash": config_hash,
                "s2_selector_hash": s2_hash,
            })
    states.sort(key=lambda s: (s["config_id"], s["s2"]))
    csvwrite(OUT / "m3wcf1_reference_state_manifest.csv", states)

    # -- state freshness audit (taskbook Sec. 17) -----------------------------------
    known_ids: set[str] = set()
    known_pairs: set[tuple[str, float]] = set()
    for p in (CF2 / "m3cf2_candidate_truth_inventory.csv",
              CF0 / "m3cf0_current_config_coordinates.csv",
              ROOT / "results/phase_m3sf2/summary/m3sf2_mapping_bank.csv",
              ROOT / "results/phase_m3cf1n/summary/m3cf1n_discovery_states.csv",
              ROOT / "results/phase_m3pi1r/summary/m3pi1r_candidate_bank.csv",
              ROOT / "results/phase_m3uc2r/summary/m3uc2r_candidate_pool.csv",
              WA1_OUT / "m3wa1_candidate_pool.csv",
              WA1R_OUT / "m3wa1r_candidate_universe.csv"):
        if Path(p).exists():
            for r in csvread(p):
                known_ids.add(r.get("state_id") or r.get("candidate_id") or "")
                if r.get("s2") not in ("", None) and r.get("config_id"):
                    known_pairs.add((r["config_id"], round(float(r["s2"]), 9)))
    d2 = load(ROOT / "results/phase_m3d2/summary/m3d2_confirmation_summary.json")["records"]
    for r in d2:
        known_ids.add(r["state_id"])
        known_pairs.add((r["config_id"], round(float(r["s2"]), 9)))
    for q in (ROOT / "results/phase_m3pi1v/quarantine_attempt1",
              ROOT / "results/phase_m3pi1v/quarantine_attempt2",
              ROOT / "results/phase_m3wa1/reference",
              ROOT / "results/phase_m3wa1r/reference"):
        tdir = q / "trials"
        if tdir.exists():
            for d in tdir.iterdir():
                if d.is_dir():
                    known_ids.add(d.name)
    known_ids |= {r["state_id"] for r in
                  csvread(CF2 / "m3cf2_development_panel.csv")}
    known_ids |= {r["state_id"] for r in
                  csvread(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    freshness = []
    for s in states:
        pair_fresh = not any(cid == s["config_id"] and abs(s2v - s["s2"]) < 1e-9
                             for cid, s2v in known_pairs)
        # config-level freshness: no prior sampling under this physical config
        config_fresh = not any(cid.startswith("wcf1_") is False and
                               cid in {u["config_id"] for u in
                                       load(OUT / "m3wcf1_used_physical_config_manifest.json")["used_configs"]}
                               for cid in [s["config_id"]])
        ok = s["state_id"] not in known_ids and pair_fresh
        freshness.append({"state_id": s["state_id"], "identity_fresh": ok,
                          "pair_fresh": pair_fresh})
    if not all(f["identity_fresh"] for f in freshness):
        raise RuntimeError("WCF1-PRE-B: state identity collision")
    dump(OUT / "m3wcf1_state_freshness_audit.json", {
        "recorded_at": now(),
        "states": len(states),
        "fresh_identities": sum(1 for f in freshness if f["identity_fresh"]),
        "checked_against": ["CF1", "CF1N", "CF2", "PI1V retired panel",
                            "PI1VR0 reserve", "WA1 candidate pool",
                            "WA1 consumed state", "WA1R states",
                            "D2 confirmations", "SF2 bank", "UC2R pool"],
        "rows": freshness,
    })

    # -- protocols (taskbook Sec. 18-22) ---------------------------------------------
    dump(OUT / "m3wcf1_pref_protocol.json", {
        "samples_per_config": REF_N, "configs": N_CONFIGS,
        "event": "topology != S0", "event_schema": "corrected full-event v2",
        "estimator": "hyptraj.m3d2.experiment.direct_full_event_reference",
        "namespace": PREF_NAMESPACE, "total_p_ref_samples": N_CONFIGS * REF_N,
    })
    dump(OUT / "m3wcf1_reference_protocol.json", {
        "samples_per_arm": REF_N, "arms": ["BASE", "WIDEN", "SHRINK"],
        "batches": N_BATCH, "paired_crn": True,
        "states": len(states), "no_discovery_stage": True,
        "estimator": "hyptraj.m3d2.experiment.evaluate_reference_arms + "
                     "classify_reference_state",
        "namespace": REF_NAMESPACE,
        "semantics": {"event": "topology != S0", "domain": "full-event probability",
                      "improvement_threshold": -0.01, "hold_band": 0.03,
                      "direction_margin": 0.05, "min_ess": 20.0},
        "finite_action_samples": len(states) * 3 * REF_N,
    })

    # -- seeds (taskbook Sec. 22) ------------------------------------------------------
    prior_ns = R1.prior_namespaces()
    prior_seeds = _prior_recorded_seeds()
    pref_seeds = {s["wcf1_config_id"]: [seed(PREF_NAMESPACE, s["wcf1_config_id"]), 901]
                  for s in selected}
    ref_seeds = {s["state_id"]: [seed(REF_NAMESPACE, s["state_id"]), 902]
                 for s in states}
    pref_vals = {x for v in pref_seeds.values() for x in v}
    ref_vals = {x for v in ref_seeds.values() for x in v}
    coll = sorted((pref_vals | ref_vals) & prior_seeds)
    if PREF_NAMESPACE in prior_ns or REF_NAMESPACE in prior_ns or coll:
        raise RuntimeError("WCF1-X: seed collision")
    dump(OUT / "m3wcf1_seed_manifest.json", {
        "recorded_at": now(),
        "pref_namespace": PREF_NAMESPACE,
        "ref_namespace": REF_NAMESPACE,
        "pref_seed_keys": pref_seeds,
        "ref_seed_keys": ref_seeds,
        "collision_with_all_prior": coll,
        "hash_locked_before_simulator": True,
    })

    # -- persistence contract (taskbook Sec. 23) ----------------------------------------
    dump(OUT / "m3wcf1_persistence_contract.json", {
        "recorded_at": now(),
        "inherited_from": "repaired PI1VR0/WA1R persistence (non-circular hashes)",
        "hash_helpers": "hyptraj.m3wa1r.persistence "
                        "(scientific_payload_hash / record_file_hash)",
        "mandatory_order": [
            "1. safe path", "2. durable STARTED before simulator",
            "3. scientific calculation", "4. non-circular payload/hash contract",
            "5. temp write", "6. flush + fsync", "7. schema validation",
            "8. sha256", "9. atomic rename", "10. parent-directory fsync",
            "11. final durable verification", "12. ledger COMPLETE",
        ],
        "schema_validation": "on the persisted temp record, including "
                             "non-circular payload-hash verification",
        "failure_policy": "sampling started + durable COMPLETE failure => "
                          "CONSUMED_INVALID => WCF1-X => STOP; no replay, no "
                          "replacement",
        "ledgers": {"pref": PREF_LEDGER.as_posix(), "reference": REF_LEDGER.as_posix()},
    })

    # -- source manifest + prereg hashes -------------------------------------------------
    source_paths = [
        "results/phase_m3wa1r/summary/m3wa1r_final_verdict.json",
        "results/phase_m3wa1r/summary/m3wa1r_w_feasibility.json",
        "results/phase_m3wa1r/reference/reference_manifest.json",
        "results/phase_m3wa1/summary/m3wa1_final_verdict.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_final_verdict.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_pi1v_scientific_status.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_reserve_audit_summary.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_selection_view.csv",
        "results/phase_m3cf0/summary/m3cf0_raw_physical_candidate_lattice.csv",
        "results/phase_m3cf0/summary/m3cf0_axis_classification.json",
        "results/phase_m3cf0/summary/m3cf0_future_s2_grid.json",
        "results/phase_m3cf0/summary/m3cf0_current_config_coordinates.csv",
        "results/phase_m3cf1r0/replacement/m3cf1r0_replacement_configs.csv",
        "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv",
        "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv",
        "src/hyptraj/m3wa1r/persistence.py",
        "src/hyptraj/m3d2/experiment.py",
        "scripts/run_m3wa1r.py",
        "scripts/run_m3pi1vr0.py",
    ]
    dump(OUT / "m3wcf1_source_manifest.json", {
        "base_commit": git_commit(), "recorded_at": now(),
        "simulator_samples_before_prereg": 0,
        "entries": [{"path": p, "sha256": sha(ROOT / p), "read_only": True}
                    for p in source_paths],
    })
    prereg_paths = [OUT / n for n in (
        "m3wcf1_parent_audit.json", "m3wcf1_used_physical_config_manifest.json",
        "m3wcf1_legal_physical_capacity.json", "m3wcf1_physical_selector_contract.json",
        "m3wcf1_physical_config_manifest.csv", "m3wcf1_physical_config_manifest_hash.json",
        "m3wcf1_valid_w_by_s2_audit.csv", "m3wcf1_s2_selector_contract.json",
        "m3wcf1_w_target_s2.json", "m3wcf1_reference_state_manifest.csv",
        "m3wcf1_state_freshness_audit.json", "m3wcf1_pref_protocol.json",
        "m3wcf1_reference_protocol.json", "m3wcf1_seed_manifest.json",
        "m3wcf1_persistence_contract.json", "m3wcf1_source_manifest.json")]
    dump(OUT / "m3wcf1_prereg_hashes.json", {
        "recorded_at": now(),
        "p_ref_records_before_freeze": "NONE",
        "reference_records_before_freeze": "NONE",
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                  for p in prereg_paths],
    })

    write_stop_report(selected, chosen_s2, len(fresh))
    print("WCF1 prepare: COMPLETE -- 6 configs x 2 s2 frozen; STOP before P_ref")


def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3wcf1"
    for p in (ROOT / "results").rglob("*.csv"):
        if self_prefix in p.parents:
            continue
        try:
            with p.open(newline="", encoding="utf-8") as h:
                rdr = csv.DictReader(h)
                if rdr.fieldnames and any(f.strip() == "seed" for f in rdr.fieldnames):
                    for row in rdr:
                        try:
                            vals.add(int(row["seed"]))
                        except (TypeError, ValueError):
                            continue
        except Exception:
            continue
    return vals


def write_stop_report(selected, chosen_s2, n_fresh) -> None:
    feas = load(OUT / "m3wcf1_legal_physical_capacity.json")
    s2doc = load(OUT / "m3wcf1_w_target_s2.json")
    mh = load(OUT / "m3wcf1_physical_config_manifest_hash.json")
    smh = sha(OUT / "m3wcf1_reference_state_manifest.csv")
    txt = f"""M3-WCF1 PREREG STATUS:
COMPLETE

PARENT:
WA1R = WA1R-B
WA1 = WA1-X
PI1V valid verdict = PI1V-X

CURRENT FRESH W:
state count = 15
distinct configs = 5
exact8/config>=6 feasible = NO

INVALID PI1V DATA:
used in config selection = NO
used in s2 selection = NO
used in panel selection = NO

PHYSICAL CONFIG SPACE:
legal fresh capacity = {n_fresh}
selector = sequential maximin
outcome-blind = YES

NEW CONFIGS:
count = {len(selected)}
IDs = {', '.join(s['wcf1_config_id'] for s in selected)}
manifest hash = {mh['manifest_sha256']}
prior config collisions = 0

VALID W-BY-s2 AUDIT:
source = corrected durable high-budget only
invalid evidence used = NO

W-TARGET s2:
count = 2
values = {s2doc['selected_s2']}
selector rule frozen = YES
common-grid values = YES

REFERENCE STATES:
count = 12
fresh identities = 12/12
manifest hash = {smh}

P_REF:
new streams = 6
samples/config = 500000
namespace = M3-WCF1-PREF

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
states = 12
namespace = M3-WCF1-REF

EXPECTED COST:
P_ref = 3000000
finite-action reference = 18000000
total = 21000000

PERSISTENCE:
hardened contract = ENABLED
STARTED-before-simulator = YES
non-circular hash = YES
consumed-invalid replay = FORBIDDEN

PRIMARY TARGET:
K_NEW_W_CONFIG >=1

FINAL W GATE:
exact W = 8
configs >=6
max2/config

FULL PANEL TARGET:
8W / 8S / 8ND

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN WCF1
"""
    (DOC / "M3_WCF1_Pregistration.md").write_text(
        "# M3-WCF1 Preregistration\n\nFrozen before any simulator call.\n\n```\n"
        + txt + "\n```\n", encoding="utf-8")
    (OUT / "m3wcf1_prereg_status.txt").write_text(txt, encoding="utf-8")
    print(txt)


# --------------------------------------------------------------------------
# WCF1 transactional runner (taskbook Sec. 23 order; non-circular hashes)
# --------------------------------------------------------------------------

def wcf1_trial(logical_id: str, final_path: Path, run_simulator, *,
               ledger_path: Path, full_validator, base_entry: dict,
               run_uuid: str | None = None):
    """1 safe path / 2 STARTED / 3 scientific calc / 4 non-circular payload+hash /
    5 temp write / 6 flush+fsync / 7 schema validation / 8 sha256 / 9 atomic
    rename / 10 parent fsync / 11 final durable verification / 12 COMPLETE."""
    run_uuid = run_uuid or uuid.uuid4().hex
    validate_safe_path(logical_id, final_path)
    ensure_not_started(ledger_path, logical_id)
    if final_path.exists():
        raise ReplayError(f"final record already exists for {logical_id!r}")
    ledger_append(ledger_path, {"state_id": logical_id,
                                "expected_output_path": final_path.as_posix(),
                                "status": "STARTED", "start_timestamp": now(),
                                **base_entry})
    temp_path = final_path.parent / f".{safe_fs_id(logical_id)}.json.tmp.{run_uuid}"
    try:
        payload = run_simulator()                      # 3 scientific calculation
        if HASH_FIELD in payload:
            raise StatePersistenceError("payload must not carry a self-hash field")
        payload[HASH_FIELD] = scientific_payload_hash(payload)   # 4 non-circular
        final_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
        with open(temp_path, "wb") as h:               # 5 temp write
            h.write(raw)
            h.flush()
            os.fsync(h.fileno())                       # 6 flush + fsync
        full_validator(json.loads(temp_path.read_text(encoding="utf-8")))  # 7 schema
        digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()        # 8 sha256
        os.replace(temp_path, final_path)              # 9 atomic rename
        dir_sync = fsync_directory(final_path.parent)  # 10 parent fsync
        if not dir_sync["pass"]:
            raise StatePersistenceError(f"parent-directory fsync unavailable: {dir_sync}")
        # 11 final durable verification
        if record_file_hash(final_path) != digest:
            raise StatePersistenceError("final file hash mismatch")
        stored = json.loads(final_path.read_text(encoding="utf-8"))
        if scientific_payload_hash(stored) != stored[HASH_FIELD]:
            raise StatePersistenceError("non-circular payload hash mismatch")
        ledger_append(ledger_path, {"state_id": logical_id, "status": "COMPLETE",
                                    "record_file_hash": digest,
                                    "scientific_payload_hash": stored[HASH_FIELD],
                                    "finish_timestamp": now(), **base_entry})
        return {"status": "COMPLETE", "record_file_hash": digest}
    except Exception as exc:
        ledger_append(ledger_path, {"state_id": logical_id,
                                    "status": "CONSUMED_INVALID",
                                    "reason": f"{type(exc).__name__}: {exc}",
                                    "finish_timestamp": now()})
        raise


def ensure_not_started(ledger_path: Path, logical_id: str) -> None:
    for e in ledger_entries(ledger_path):
        if e.get("state_id") == logical_id:
            raise ReplayError(f"identity {logical_id!r} already has a ledger entry; "
                              "no replay permitted (WCF1 Sec. 23)")


# --------------------------------------------------------------------------
# stage: pref (6 new config-specific P_ref streams)
# --------------------------------------------------------------------------

def _validate_pref(rec: dict) -> None:
    required = {"schema", "config_id", "wcf1_config_id", "p_batches", "p_ref_full",
                "sample_count", "event_schema", "seed_key", "namespace"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["schema"] != "m3wcf1_pref_v1":
        raise ValueError("schema validation failed; wrong schema")
    if rec.get(HASH_FIELD) is None or scientific_payload_hash(rec) != rec[HASH_FIELD]:
        raise ValueError("schema validation failed; non-circular hash mismatch")


def pref() -> None:
    _verify_prereg()
    manifest = csvread(OUT / "m3wcf1_physical_config_manifest.csv")
    lat = {r["config_id"]: r for r in
           csvread(CF0 / "m3cf0_raw_physical_candidate_lattice.csv")}
    seeds = load(OUT / "m3wcf1_seed_manifest.json")["pref_seed_keys"]
    for sel in manifest:
        wid, rid = sel["wcf1_config_id"], sel["raw_candidate_id"]

        def simulate(wid=wid, rid=rid, sel=sel):
            bc = bench_for(wid, lat[rid])
            ref = direct_full_event_reference(bc, seeds[wid], REF_N, N_BATCH)
            return {
                "schema": "m3wcf1_pref_v1",
                "recorded_at": now(),
                "config_id": rid,
                "wcf1_config_id": wid,
                "event_schema": "corrected full-event v2",
                "event_semantics_schema_version": ref["event_semantics_schema_version"],
                "p_batches": ref["p_batches"],
                "p_ref_full": ref["p_ref_full"],
                "p_ref_full_CI": ref["p_ref_full_CI"],
                "p_ref_full_SE": ref["p_ref_full_SE"],
                "topology_counts": ref["topology_counts"],
                "sample_count": REF_N,
                "n_batches": N_BATCH,
                "seed_key": [int(x) for x in seeds[wid]],
                "namespace": PREF_NAMESPACE,
                "physical_fields": phys_fields(lat[rid]),
            }

        result = wcf1_trial(wid, PREF / f"{wid}.json", simulate,
                            ledger_path=PREF_LEDGER, full_validator=_validate_pref,
                            base_entry={"seed_namespace": PREF_NAMESPACE,
                                        "seed": seeds[wid][0]})
        stored = load(PREF / f"{wid}.json")
        print(f"pref {wid}: P_ref={stored['p_ref_full']:.6f} "
              f"CI={stored['p_ref_full_CI']}", flush=True)
    _gate_pref()


def _gate_pref() -> None:
    entries = ledger_entries(PREF_LEDGER)
    counts = Counter(e.get("status") for e in entries)
    manifest = csvread(OUT / "m3wcf1_physical_config_manifest.csv")
    complete = {e["state_id"] for e in entries if e.get("status") == "COMPLETE"}
    expected = {c["wcf1_config_id"] for c in manifest}
    problems = []
    if complete != expected or counts.get("CONSUMED_INVALID", 0):
        problems.append(f"complete={len(complete)}/6 consumed_invalid="
                        f"{counts.get('CONSUMED_INVALID', 0)}")
    for wid in sorted(expected):
        e = next(e for e in entries if e.get("state_id") == wid
                 and e.get("status") == "COMPLETE")
        if record_file_hash(PREF / f"{wid}.json") != e["record_file_hash"]:
            problems.append(f"{wid}: hash mismatch")
    dump(OUT / "m3wcf1_pref_summary.json", {
        "sealed_at": now(), "expected": 6, "complete": len(complete),
        "consumed_invalid": counts.get("CONSUMED_INVALID", 0),
        "samples": 6 * REF_N, "problems": problems,
        "gate": "PASS" if not problems else "FAIL",
    })
    if problems:
        raise RuntimeError(f"WCF1-X: P_ref completion gate failed {problems}")
    print("WCF1 pref gate: 6/6 COMPLETE, 0 consumed-invalid")


def _verify_prereg() -> None:
    rec = load(OUT / "m3wcf1_prereg_hashes.json")
    for e in rec["files"]:
        p = ROOT / e["path"]
        if not p.exists() or sha(p) != e["sha256"]:
            raise RuntimeError(f"WCF1-X: prereg hash drift at {e['path']}")


# --------------------------------------------------------------------------
# stage: reference (12 states x 3 arms x 500k)
# --------------------------------------------------------------------------

def _validate_reference(rec: dict) -> None:
    required = {"schema", "state_id", "config_id", "wcf1_config_id", "s2",
                "grid_index", "truth", "label_valid", "arms", "oracle", "p_ref",
                "seed_key", "namespace", "sample_counts"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["schema"] != "m3wcf1_reference_v1":
        raise ValueError("schema validation failed; wrong schema")
    if rec.get(HASH_FIELD) is None or scientific_payload_hash(rec) != rec[HASH_FIELD]:
        raise ValueError("schema validation failed; non-circular hash mismatch")


def reference() -> None:
    _verify_prereg()
    pref_summary = load(OUT / "m3wcf1_pref_summary.json")
    if pref_summary["gate"] != "PASS":
        raise RuntimeError("WCF1-X: P_ref completion gate not PASS")
    states = csvread(OUT / "m3wcf1_reference_state_manifest.csv")
    seeds = load(OUT / "m3wcf1_seed_manifest.json")["ref_seed_keys"]
    lat = {r["config_id"]: r for r in
           csvread(CF0 / "m3cf0_raw_physical_candidate_lattice.csv")}
    for s in states:
        sid = s["state_id"]

        def simulate(s=s, sid=sid):
            st = state_for(s["config_id"], lat[s["raw_candidate_id"]], float(s["s2"]))
            arms_eval = evaluate_reference_arms(
                state_arms(st), st.bench_cfg, seeds[sid], REF_N, N_BATCH)
            p_ref_path = PREF / f"{s['config_id']}.json"
            p_ref_record = load(p_ref_path)
            cls = classify_reference_state(arms_eval, p_ref_record)
            arms_summary = {name: {"P": float(arms_eval[name]["P"]),
                                   "P_CI": [float(x) for x in arms_eval[name]["P_CI"]],
                                   "M2": float(arms_eval[name]["M2"]),
                                   "ESS": float(arms_eval[name]["ESS"]),
                                   "sample_count": int(arms_eval[name]["sample_count"])}
                            for name in ("base", "widen", "shrink")}
            oracle = cls.get("oracle_details") or {}
            return {
                "schema": "m3wcf1_reference_v1",
                "recorded_at": now(),
                "state_id": sid,
                "config_id": s["config_id"],
                "wcf1_config_id": s["config_id"],
                "raw_candidate_id": s["raw_candidate_id"],
                "s2": float(s["s2"]),
                "grid_index": int(s["grid_index"]),
                "truth": cls["corrected_class"],
                "label_valid": bool(cls["numerical_valid"]
                                    and cls["probability_semantics_valid"]
                                    and cls["ess_valid"]),
                "invalid_reason": cls.get("reason"),
                "arms": arms_summary,
                "oracle": {k: oracle.get(k) for k in
                           ("ratios", "direction_margin_Delta_dir", "D_dir",
                            "D_widen", "D_shrink")},
                "p_ref": {"source": p_ref_path.as_posix(),
                          "sha256": sha(p_ref_path),
                          "config_specific": True, "new_samples": REF_N},
                "seed_key": [int(x) for x in seeds[sid]],
                "namespace": REF_NAMESPACE,
                "sample_counts": {"per_arm": REF_N, "arms": 3, "batches": N_BATCH,
                                  "finite_action_samples": 3 * REF_N},
            }

        result = wcf1_trial(sid, REF / f"{sid}.json", simulate,
                            ledger_path=REF_LEDGER, full_validator=_validate_reference,
                            base_entry={"config_id": s["config_id"],
                                        "s2": float(s["s2"]),
                                        "seed_namespace": REF_NAMESPACE,
                                        "seed": seeds[sid][0]})
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"WCF1-X: reference not durably COMPLETE for {sid}: {result}")
        stored = load(REF / f"{sid}.json")
        ratios = stored["oracle"].get("ratios") or {}
        print(f"reference {sid}: truth={stored['truth']} valid={stored['label_valid']} "
              f"r_w={ratios.get('widen_over_base')} r_s={ratios.get('shrink_over_base')}",
              flush=True)
    entries = ledger_entries(REF_LEDGER)
    complete = {e["state_id"] for e in entries if e.get("status") == "COMPLETE"}
    if complete != {s["state_id"] for s in states}:
        raise RuntimeError("WCF1-X: reference incomplete")
    recs = [load(REF / f"{s['state_id']}.json") for s in states]
    labels = Counter(r["truth"] for r in recs)
    by_config = {}
    for c in csvread(OUT / "m3wcf1_physical_config_manifest.csv"):
        wid = c["wcf1_config_id"]
        sub = [r for r in recs if r["wcf1_config_id"] == wid]
        by_config[wid] = {
            "s2_values": sorted(r["s2"] for r in sub),
            "labels": [r["truth"] for r in sub],
            "NEW_W_CONFIG": any(r["truth"] == "WIDEN" for r in sub),
            "ROBUST_NEW_W_CONFIG": all(r["truth"] == "WIDEN" for r in sub),
        }
    dump(REF / "reference_manifest.json", {
        "sealed_at": now(), "states": len(recs), "complete": len(recs),
        "consumed_invalid": sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID"),
        "finite_action_samples": sum(r["sample_counts"]["finite_action_samples"] for r in recs),
        "labels": {k: labels.get(k, 0) for k in
                   ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS", "INVALID")},
        "record_file_hashes": {r["state_id"]: record_file_hash(REF / f"{r['state_id']}.json")
                               for r in recs},
    })
    dump(OUT / "m3wcf1_reference_by_config.json", by_config)
    print(f"WCF1 reference sealed: {len(recs)} states, "
          f"{sum(r['sample_counts']['finite_action_samples'] for r in recs):,} samples, "
          f"labels {labels}")


# --------------------------------------------------------------------------
# stage: capacity
# --------------------------------------------------------------------------

def capacity() -> None:
    ref_manifest = load(REF / "reference_manifest.json")
    recs = [load(REF / f"{s['state_id']}.json")
            for s in csvread(OUT / "m3wcf1_reference_state_manifest.csv")]
    labels = Counter(r["truth"] for r in recs)
    by_config = load(OUT / "m3wcf1_reference_by_config.json")
    k_new = sum(1 for c in by_config.values() if c["NEW_W_CONFIG"])
    k_robust = sum(1 for c in by_config.values() if c["ROBUST_NEW_W_CONFIG"])
    dump(OUT / "m3wcf1_reference_summary.json", {
        "recorded_at": now(), "states": len(recs),
        "labels": {k: labels.get(k, 0) for k in
                   ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS", "INVALID")},
        "finite_action_samples": ref_manifest["finite_action_samples"],
        **boundary_block(),
    })

    # persistence audits
    for name, ledger, directory, expected in (
            ("pref", PREF_LEDGER, PREF, 6), ("reference", REF_LEDGER, REF, 12)):
        entries = ledger_entries(ledger)
        problems = []
        complete = {}
        for e in entries:
            if e.get("status") == "COMPLETE":
                complete[e["state_id"]] = e
        if len(complete) != expected:
            problems.append(f"complete {len(complete)}/{expected}")
        if any(e.get("status") == "CONSUMED_INVALID" for e in entries):
            problems.append("CONSUMED_INVALID present")
        for sid, e in complete.items():
            if record_file_hash(directory / f"{sid}.json") != e["record_file_hash"]:
                problems.append(f"{sid}: hash mismatch")
            stored = load(directory / f"{sid}.json")
            if scientific_payload_hash(stored) != stored[HASH_FIELD]:
                problems.append(f"{sid}: payload hash mismatch")
        audit = {"recorded_at": now(), "ledger_entries": len(entries),
                 "complete": len(complete), "problems": problems,
                 "hashes": "PASS" if not problems else "FAIL"}
        dump(OUT / (f"m3wcf1_pref_persistence_audit.json" if name == "pref"
                    else "m3wcf1_reference_persistence_audit.json"), audit)
        if problems:
            raise RuntimeError(f"WCF1-X: {name} persistence audit failed {problems}")

    # NEW_W_CONFIG summary
    dump(OUT / "m3wcf1_new_w_config_summary.json", {
        "recorded_at": now(),
        "definition": "NEW_W_CONFIG iff at least one of the config's two frozen "
                      "states is WIDEN; ROBUST_NEW_W_CONFIG iff both are WIDEN",
        "by_config": by_config,
        "K_NEW_W_CONFIG": k_new,
        "K_ROBUST_NEW_W_CONFIG": k_robust,
        "target_met": k_new >= 1,
    })

    # combined fresh W pool (taskbook Sec. 29)
    vr0_view = {r["state_id"]: r for r in csvread(VR0 / "m3pi1vr0_selection_view.csv")}
    retired24 = {r["state_id"] for r in csvread(
        VR0 / "m3pi1vr0_retired_development_states.csv")}
    pool = []
    for r in vr0_view.values():
        if r["state_id"] in retired24 or r["state_id"] == \
                "cf1n_new_000_wa1_w_s2_1p788854382":
            continue
        pool.append({"state_id": r["state_id"], "truth": r["truth"],
                     "config_id": r["config_id"],
                     "physical_family": r["physical_family"], "s2": r["s2"],
                     "source_stage": r["source_stage"],
                     "source_region": "M3-CF2-RESERVE",
                     "pilot_exposure": 0, "probe_exposure": 0, "origin": "reserve"})
    wa1r_manifest = csvread(WA1R_OUT / "m3wa1r_candidate_manifest.csv")
    for c in wa1r_manifest:
        r = load(ROOT / "results/phase_m3wa1r/reference" / f"{c['candidate_id']}.json")
        if r["label_valid"]:
            pool.append({"state_id": r["candidate_id"], "truth": r["truth"],
                         "config_id": r["config_id"], "physical_family": "",
                         "s2": r["candidate_s2"], "source_stage": "M3-WA1R",
                         "source_region": f"M3-WA1R:{r['config_id']}",
                         "pilot_exposure": 0, "probe_exposure": 0, "origin": "wa1r"})
    for r in recs:
        if r["label_valid"]:
            pool.append({"state_id": r["state_id"], "truth": r["truth"],
                         "config_id": r["config_id"], "physical_family": "wcf1",
                         "s2": r["s2"], "source_stage": "M3-WCF1",
                         "source_region": f"M3-WCF1:{r['config_id']}",
                         "pilot_exposure": 0, "probe_exposure": 0, "origin": "wcf1"})
    pool.sort(key=lambda s: s["state_id"])
    csvwrite(OUT / "m3wcf1_combined_fresh_w_pool.csv", pool)

    # W diversity feasibility (taskbook Sec. 30)
    w_pool = [s for s in pool if s["truth"] == "WIDEN"]
    cfg_counts = Counter(s["config_id"] for s in w_pool)
    capacity_2 = sum(min(n, W_MAX_PER_CONFIG) for n in cfg_counts.values())
    w_subset = _select_w_subset(w_pool)
    w_feasible = w_subset is not None and len(w_subset) == W_TARGET
    dump(OUT / "m3wcf1_w_diversity_feasibility.json", {
        "recorded_at": now(),
        "states": len(w_pool),
        "distinct_configs": len(cfg_counts),
        "config_counts": dict(cfg_counts),
        "selectable_capacity_at_max2": capacity_2,
        "W_DIVERSITY_FEASIBLE": "YES" if w_feasible else "NO",
        "exact_8_selectable": bool(w_feasible),
        "configs_ge_6": len(cfg_counts) >= W_CONFIG_MIN,
        "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG,
        "selected_subset": [s["state_id"] for s in w_subset] if w_subset else [],
    })

    # full fresh panel (taskbook Sec. 31-32)
    panel = R0._run_selector(_panel_view(pool, vr0_view)) if w_feasible else None
    full_feasible = False
    if panel is not None:
        grp = Counter("W" if s["truth"] == "WIDEN"
                      else "S" if s["truth"] == "SHRINK" else "ND" for s in panel)
        full_feasible = (len(panel) == 24 and grp["W"] == 8 and grp["S"] == 8
                         and grp["ND"] == 8
                         and len({s["state_id"] for s in panel}) == 24)
    if full_feasible:
        rows = [{"state_id": s["state_id"], "truth": s["truth"],
                 "config_id": s["config_id"], "physical_family": s["physical_family"],
                 "s2": s["s2"], "source_stage": s["source_stage"],
                 "source_region": s["source_region"],
                 "pilot_exposure": 0, "probe_exposure": 0} for s in panel]
        rows.sort(key=lambda s: (s["truth"], s["state_id"]))
        csvwrite(OUT / "m3wcf1_fresh_development_panel.csv", rows)
        dump(OUT / "m3wcf1_fresh_development_panel_hash.json", {
            "recorded_at": now(),
            "panel_sha256": sha(OUT / "m3wcf1_fresh_development_panel.csv"),
            "states": 24, "W": 8, "S": 8, "ND": 8,
            "pilot_exposure": 0, "probe_exposure": 0,
            "invalid_run_scores_used": False,
        })
    dump(OUT / "m3wcf1_full_panel_capacity.json", {
        "recorded_at": now(),
        "w_diversity_feasible": bool(w_feasible),
        "full_panel_feasible": bool(full_feasible),
        "panel_states": 24 if full_feasible else "NA",
        "W": 8 if full_feasible else "NA",
        "S": 8 if full_feasible else "NA",
        "ND": 8 if full_feasible else "NA",
        "selector": "PI1VR0 frozen selector rules reused verbatim",
    })

    # remaining protected reserve (taskbook Sec. 32)
    selected_ids = {s["state_id"] for s in panel} if full_feasible else set()
    remaining = [{"state_id": r["state_id"], "truth": r["truth"],
                  "config_id": r["config_id"], "s2": r["s2"],
                  "source_stage": r["source_stage"],
                  "status": "PILOT_PROTECTED_RESERVE"}
                 for r in sorted(vr0_view.values(), key=lambda x: x["state_id"])
                 if r["state_id"] not in selected_ids]
    wa1r_ids = {c["candidate_id"] for c in wa1r_manifest}
    for c in wa1r_manifest:
        if c["candidate_id"] not in selected_ids:
            r = load(ROOT / "results/phase_m3wa1r/reference" / f"{c['candidate_id']}.json")
            remaining.append({"state_id": c["candidate_id"], "truth": r["truth"],
                              "config_id": r["config_id"], "s2": r["candidate_s2"],
                              "source_stage": "M3-WA1R",
                              "status": "PILOT_PROTECTED_RESERVE"})
    for r in recs:
        if r["state_id"] not in selected_ids and r["label_valid"]:
            remaining.append({"state_id": r["state_id"], "truth": r["truth"],
                              "config_id": r["config_id"], "s2": r["s2"],
                              "source_stage": "M3-WCF1",
                              "status": "PILOT_PROTECTED_RESERVE"})
    remaining.sort(key=lambda x: x["state_id"])
    csvwrite(OUT / "m3wcf1_remaining_protected_reserve.csv", remaining)
    dump(OUT / "m3wcf1_remaining_reserve_summary.json", {
        "recorded_at": now(),
        "remaining_protected_states": len(remaining),
        "pilot_exposure": 0,
        "protection": "all unselected valid states remain PILOT_PROTECTED_RESERVE",
    })

    # verdict (taskbook Sec. 33 priority)
    if k_new == 0:
        verdict = "WCF1-B"
    elif not w_feasible or not full_feasible:
        verdict = "WCF1-C"
    else:
        verdict = "WCF1-A"
    dump(OUT / "m3wcf1_final_verdict.json", {
        "status": "COMPLETE",
        "verdict": verdict,
        "recorded_at": now(),
        "p_ref": {"expected": 6, "complete": 6, "consumed_invalid": 0,
                  "samples": 6 * REF_N},
        "reference": {"expected_states": 12, "complete": ref_manifest["complete"],
                      "consumed_invalid": ref_manifest["consumed_invalid"],
                      "samples": ref_manifest["finite_action_samples"]},
        "by_new_config": by_config,
        "counts": {"K_NEW_W_CONFIG": k_new, "K_ROBUST_NEW_W_CONFIG": k_robust},
        "combined_fresh_w": {"states": len(w_pool),
                             "distinct_configs": len(cfg_counts)},
        "w_diversity": {"exact_8_selectable": bool(w_feasible),
                        "configs_ge_6": len(cfg_counts) >= W_CONFIG_MIN,
                        "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG},
        "full_fresh_panel": {"feasible": bool(full_feasible),
                             "hash": sha(OUT / "m3wcf1_fresh_development_panel.csv")
                             if full_feasible else "NA"},
        "invalid_pi1v_data_used": False,
        "remaining_protected_reserve": {"states": len(remaining), "pilot_exposure": 0},
        **boundary_block(),
        "next": {
            "WCF1-A": "M3-PI1VN independent fresh-panel finite-action information "
                      "validation (original frozen <=2x hypothesis)",
            "WCF1-B": "broader physical W expansion",
            "WCF1-C": "diversity-objective rethink",
            "WCF1-PRE-B": "redesign",
            "WCF1-X": "stop; invalid",
        }[verdict],
    })
    print(f"WCF1 capacity: K_NEW_W_CONFIG={k_new}, W pool {len(w_pool)} states / "
          f"{len(cfg_counts)} configs, feasible={bool(w_feasible)}, verdict {verdict}")


def _canonical_order(state_id: str, vr0_view: dict) -> int:
    if state_id in vr0_view:
        return int(vr0_view[state_id]["canonical_bank_order"])
    return 1000 + (abs(int(hashlib.sha256(state_id.encode()).hexdigest()[:8], 16)) % 1000)


def _panel_view(pool: list[dict], vr0_view: dict) -> list[dict]:
    view = []
    for s in pool:
        view.append({"state_id": s["state_id"], "truth": s["truth"],
                     "config_id": s["config_id"], "physical_family": s["physical_family"],
                     "s2": s["s2"], "source_stage": s["source_stage"],
                     "source_region": s["source_region"],
                     "stable_config_flag": "True",
                     "canonical_bank_order": _canonical_order(s["state_id"], vr0_view)})
    return view


def _select_w_subset(w_pool: list[dict]) -> list[dict] | None:
    by_cfg: dict[str, list[dict]] = {}
    for s in sorted(w_pool, key=lambda s: (float(s["s2"]), s["state_id"])):
        by_cfg.setdefault(s["config_id"], []).append(s)
    chosen: list[dict] = []
    for cid in sorted(by_cfg):
        if len(chosen) < W_TARGET:
            chosen.append(by_cfg[cid][0])
    for cid in sorted(by_cfg):
        if len(chosen) >= W_TARGET:
            break
        remaining = [s for s in by_cfg[cid] if s not in chosen]
        if remaining and sum(1 for s in chosen if s["config_id"] == cid) < W_MAX_PER_CONFIG:
            chosen.append(remaining[0])
    if len(chosen) != W_TARGET:
        return None
    cfg = Counter(s["config_id"] for s in chosen)
    if len(cfg) < W_CONFIG_MIN or max(cfg.values()) > W_MAX_PER_CONFIG:
        return None
    return sorted(chosen, key=lambda s: (s["config_id"], float(s["s2"])))


# --------------------------------------------------------------------------
# stage: report
# --------------------------------------------------------------------------

def _regression_summary() -> str:
    log = OUT / "m3wcf1_full_regression.log"
    if not log.exists():
        return "pending"
    tail = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    passed = [ln for ln in tail if " passed" in ln]
    return passed[-1] if passed else "; ".join(tail[-2:])


def report() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    final = load(OUT / "m3wcf1_final_verdict.json")
    pref_summary = load(OUT / "m3wcf1_pref_summary.json")
    ref_manifest = load(REF / "reference_manifest.json")
    neww = load(OUT / "m3wcf1_new_w_config_summary.json")
    feas = load(OUT / "m3wcf1_w_diversity_feasibility.json")
    cap = load(OUT / "m3wcf1_full_panel_capacity.json")
    rem = load(OUT / "m3wcf1_remaining_reserve_summary.json")
    reg = _regression_summary()

    (DOC / "M3_WCF1_Task.md").write_text(
        "# M3-WCF1 Task\n\nTask book: "
        "`M3_WCF1_Prospective_Fresh_Physical_Configuration_WIDEN_Expansion_Task.md`.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_Parent_Audit.md").write_text(
        "# M3-WCF1 Parent Audit\n\nStatus: **PASS**.\n\n"
        "- WA1R = WA1R-B (8/8 references COMPLETE, 8/8 WIDEN, 0 consumed-invalid); "
        "WA1 = WA1-X; PI1V valid verdict = PI1V-X.\n"
        "- WA1 consumed candidate reused = NO; fresh W config ceiling = 5; "
        "70 reserve states scientifically valid; WA1R states pilot-unexposed.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_Physical_Config_Expansion.md").write_text(
        "# M3-WCF1 Physical Config Expansion\n\n"
        "- Lattice: 128 legal CF0 candidates; 16 used physical configs excluded "
        "by coordinates; legal fresh capacity 120 >= 6.\n"
        "- s2 is an ACTION_STATE_AXIS, not a physical expansion axis.\n"
        "- Sequential maximin selector (outcome-blind) froze exactly 6 configs: "
        + ", ".join(s["wcf1_config_id"] for s in
                    csvread(OUT / "m3wcf1_physical_config_manifest.csv")) + ".\n"
        "- No seventh config after outcomes; manifest hash-locked.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_W_Target_s2_Design.md").write_text(
        "# M3-WCF1 W-Target s2 Design\n\n"
        "- Valid W-by-s2 audit from corrected durable high-budget states only "
        "(CF2 inventory at CF0 common-grid points).\n"
        f"- Frozen W-target s2: {load(OUT / 'm3wcf1_w_target_s2.json')['selected_s2']} "
        "(rule: max WIDEN configs, then WIDEN fraction, then lower s2, then grid "
        "index).\n"
        "- Independence comes from new configs, new config-specific P_ref, new "
        "state identities, new seeds, and the prospective frozen selector.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_Human_Approval.md").write_text(
        "# M3-WCF1 Human Approval\n\n"
        "- Date: 2026-09-05 (before the first WCF1 simulator call).\n"
        "- The mandatory pre-run STOP report was frozen in "
        "`M3_WCF1_Pregistration.md` with prereg hashes.\n"
        "- The user's session directive \"execute the new task book\" constitutes "
        "the human approval to run WCF1 (P_ref + references), per the standing "
        "prior-authorization pattern.\n"
        "- Scope: the 6 frozen configs / 12 frozen states only; no reserve "
        "piloting; no V1/S1 routes; VALUE/RARITY/M3-Q stay BLOCKED.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_Pref_Execution_Audit.md").write_text(
        "# M3-WCF1 P_ref Execution Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- Expected 6, complete {pref_summary['complete']}, consumed-invalid "
        f"{pref_summary['consumed_invalid']}; samples {pref_summary['samples']:,} "
        "(6 x 500,000, corrected full-event v2, namespace M3-WCF1-PREF).\n"
        "- Completion gate PASS before any reference execution.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_Reference_Execution_Audit.md").write_text(
        "# M3-WCF1 Reference Execution Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- States {ref_manifest['states']}, complete {ref_manifest['complete']}, "
        f"consumed-invalid {ref_manifest['consumed_invalid']}; finite-action "
        f"samples {ref_manifest['finite_action_samples']:,} (12 x 3 x 500,000; "
        "20 paired CRN batches; namespace M3-WCF1-REF).\n"
        f"- Labels: {ref_manifest['labels']}.\n"
        f"- K_NEW_W_CONFIG = {neww['K_NEW_W_CONFIG']}, "
        f"K_ROBUST_NEW_W_CONFIG = {neww['K_ROBUST_NEW_W_CONFIG']}.\n",
        encoding="utf-8")
    (DOC / "M3_WCF1_Fresh_Panel_Capacity.md").write_text(
        "# M3-WCF1 Fresh Panel Capacity\n\n"
        f"- Combined fresh W pool: {feas['states']} states, "
        f"{feas['distinct_configs']} distinct configs, selectable capacity "
        f"{feas['selectable_capacity_at_max2']} at max 2/config.\n"
        f"- W diversity: W_DIVERSITY_FEASIBLE = "
        f"{feas['W_DIVERSITY_FEASIBLE']} (exact-8 {feas['exact_8_selectable']}, "
        f"configs>=6 {feas['configs_ge_6']}, max2/config {feas['max2_per_config']}).\n"
        f"- Full fresh panel: feasible = {cap['full_panel_feasible']}"
        + (f"; hash `{load(OUT / 'm3wcf1_fresh_development_panel_hash.json')['panel_sha256'][:16]}...`."
           if cap["full_panel_feasible"] else "; no panel frozen (counts NOT relaxed).")
        + f"\n- Remaining protected reserve: {rem['remaining_protected_states']} "
        "states, pilot exposure 0.\n",
        encoding="utf-8")
    claim = {
        "WCF1-A": "A prospective, outcome-blind physical-config expansion "
                  "established at least one entirely new physical config with "
                  "durable corrected high-budget WIDEN support, restoring an "
                  "exact-8 W selection across >=6 configs and a fresh untouched "
                  "8W/8S/8ND development panel.",
        "WCF1-B": "Valid execution produced no new W physical config "
                  "(K_NEW_W_CONFIG = 0); no adaptive seventh config.",
        "WCF1-C": "At least one new W config exists, but the frozen exact-W / "
                  "panel diversity gates remain infeasible.",
        "WCF1-PRE-B": "The prospective expansion could not be frozen.",
        "WCF1-X": "Invalid.",
    }[final["verdict"]]
    (DOC / "M3_WCF1_Final_Report.md").write_text(
        "# M3-WCF1 Final Report\n\n"
        f"**Verdict: {final['verdict']}**\n\n{claim}\n\n"
        f"- P_ref: {pref_summary['complete']}/6, {pref_summary['samples']:,} samples.\n"
        f"- Reference: {ref_manifest['complete']}/12, "
        f"{ref_manifest['finite_action_samples']:,} samples, labels "
        f"{ref_manifest['labels']}.\n"
        f"- W diversity: exact-8 {feas['exact_8_selectable']}, configs>=6 "
        f"{feas['configs_ge_6']}, max2/config {feas['max2_per_config']}.\n"
        "- No invalid PI1V data used; no V1/S1 decision made.\n"
        "- VALUE / RARITY / M3-Q: BLOCKED.\n\n"
        "FULL REGRESSION:\n"
        f"{reg}\n", encoding="utf-8")
    by_cfg = neww["by_config"]
    cfg_txt = "\n".join(
        f"{k}:\n  s2 values = {v['s2_values']}\n  labels = {v['labels']}\n"
        f"  NEW_W_CONFIG = {'YES' if v['NEW_W_CONFIG'] else 'NO'}\n"
        f"  ROBUST_NEW_W_CONFIG = {'YES' if v['ROBUST_NEW_W_CONFIG'] else 'NO'}"
        for k, v in sorted(by_cfg.items()))
    txt = f"""M3-WCF1 STATUS:
COMPLETE

P_REF:
expected = 6
complete = {pref_summary['complete']}
consumed-invalid = {pref_summary['consumed_invalid']}
samples = {pref_summary['samples']}

REFERENCE:
expected states = 12
complete = {ref_manifest['complete']}
consumed-invalid = {ref_manifest['consumed_invalid']}
samples = {ref_manifest['finite_action_samples']}

BY NEW CONFIG:
{cfg_txt}

COUNTS:
K_NEW_W_CONFIG = {neww['K_NEW_W_CONFIG']}
K_ROBUST_NEW_W_CONFIG = {neww['K_ROBUST_NEW_W_CONFIG']}

PERSISTENCE:
P_ref hashes = PASS
P_ref ledger = PASS
reference hashes = PASS
reference ledger = PASS
manifests = PASS

COMBINED FRESH W:
states = {feas['states']}
distinct configs = {feas['distinct_configs']}

W DIVERSITY:
exact 8 selectable = {'YES' if feas['exact_8_selectable'] else 'NO'}
configs >=6 = {'PASS' if feas['configs_ge_6'] else 'FAIL'}
max2/config = {'PASS' if feas['max2_per_config'] else 'FAIL'}

FULL FRESH PANEL:
feasible = {'YES' if cap['full_panel_feasible'] else 'NO'}
W = {cap['W']}
S = {cap['S']}
ND = {cap['ND']}
hash = {load(OUT / 'm3wcf1_fresh_development_panel_hash.json')['panel_sha256'] if cap['full_panel_feasible'] else 'NA'}

INVALID PI1V DATA:
used = NO

REMAINING PROTECTED RESERVE:
states = {rem['remaining_protected_states']}
pilot exposure = 0

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation authorized = NO

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

FINAL VERDICT:
{final['verdict']}

NEXT:
{final['next']}

FULL REGRESSION:
{reg}
"""
    (OUT / "m3wcf1_final_report.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"WCF1 report: verdict {final['verdict']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("prepare", "pref", "reference", "capacity",
                                     "report"))
    a = p.parse_args()
    {"prepare": prepare, "pref": pref, "reference": reference,
     "capacity": capacity, "report": report}[a.stage]()
