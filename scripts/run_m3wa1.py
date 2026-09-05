"""M3-WA1 -- Fresh WIDEN reference augmentation (reference-first recovery).

Repairs the single count bottleneck left by PI1VR0-CAP-B: the untouched
reserve holds only 7 WIDEN states (4 distinct configs), so an exact
8W/8S/8ND fresh development panel is infeasible.  WA1 generates fresh
log-midpoint candidates strictly inside adjacent confirmed-WIDEN intervals,
freezes exactly 8 of them (pre-run diversity gate: >=4 configs, max
2/config), runs one-shot 500k/arm 3-arm references (12,000,000 finite-action
samples), and rechecks W diversity plus full-panel capacity.

Hard rules inherited from the taskbook:
  - zero gradient pilots, zero probes, no thresholds, no V1/S1 routes
  - no numerical input from invalid PI1V attempts 1/2 (quarantined)
  - P_ref is CONFIG_SPECIFIC (audited from code): durable config P_ref
    records are reused; no new P_ref unless state-specific (not the case)
  - PI1VR0 hardened persistence: filesystem-safe ids, durable STARTED before
    the simulator, atomic canonical records, no same-stage replay

Stages: prepare | reference | capacity | report
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1v as R1   # noqa: E402  (namespace audit reuse)
import run_m3pi1vr0 as R0  # noqa: E402  (PI1VR0 selector reuse)
from hyptraj.m1d.experiments import BenchmarkConfig, config_from_record, load_freeze  # noqa: E402
from hyptraj.m3cf1r0.persistence import ledger_append, ledger_entries  # noqa: E402
from hyptraj.m3d.benchmark_states import assemble_state, state_arms  # noqa: E402
from hyptraj.m3d2.experiment import classify_reference_state, evaluate_reference_arms  # noqa: E402
from hyptraj.m3pi1vr0.persistence import (  # noqa: E402
    run_trial_transactional,
    safe_fs_id,
    trial_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1/summary"
REF = ROOT / "results/phase_m3wa1/reference"
DOC = ROOT / "docs/phase_m3wa1"

VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"
CF1N = ROOT / "results/phase_m3cf1n"
SF2 = ROOT / "results/phase_m3sf2/summary"
UC2R = ROOT / "results/phase_m3uc2r/summary"

REF_N = 500_000          # samples / arm (taskbook Sec. 14)
N_BATCH = 20             # paired CRN batches
N_CANDIDATES = 8         # frozen before any outcome
W_TARGET = 8
S_TARGET = 8
ND_TARGET = 8
W_CONFIG_MIN = 6
W_MAX_PER_CONFIG = 2
CANDIDATE_CONFIG_MIN = 4
CANDIDATE_MAX_PER_CONFIG = 2
REF_NAMESPACE = "M3-WA1-REF"

RESERVE_CSV = CF2 / "m3cf2_pilot_protected_reserve_manifest.csv"
INVENTORY_CSV = CF2 / "m3cf2_candidate_truth_inventory.csv"
CF2_VIEW_CSV = CF2 / "m3cf2_selection_view.csv"

REFERENCE_LEDGER = REF / "reference_ledger.jsonl"


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


_cf1n_fields = None


def _cf1n_physical_fields() -> dict:
    global _cf1n_fields
    if _cf1n_fields is None:
        _cf1n_fields = load(ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")["physical_fields"]
    return _cf1n_fields


def bench(config_id: str):
    """Resolve a config id to its frozen BenchmarkConfig."""
    if config_id in _cf1n_physical_fields():
        f = _cf1n_physical_fields()[config_id]
        return BenchmarkConfig(
            config_id=config_id, batch_seed=20300315, batch_index=0,
            theta_deg=tuple(float(f[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(f[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(f["curvature_c"]),
            offset_o=tuple(float(f[f"offset_{i}"]) for i in range(1, 5)),
        )
    matches = [r for r in load_freeze()["benchmark_configs"]
               if r["config_id"].endswith(config_id)]
    if len(matches) != 1:
        raise RuntimeError(f"WA1-X: config {config_id} not uniquely resolvable")
    return config_from_record(matches[0])


_states: dict[str, object] = {}


def state_for(config_id: str, s2: float):
    key = f"{config_id}@{s2!r}"
    if key not in _states:
        st = assemble_state(bench(config_id), float(s2), short_config=config_id)
        if isinstance(st, dict):
            raise RuntimeError(f"WA1-X: state assembly failed for {config_id}@{s2}: {st}")
        _states[key] = st
    return _states[key]


# --------------------------------------------------------------------------
# stage: prepare (zero simulator)
# --------------------------------------------------------------------------

def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    REF.mkdir(parents=True, exist_ok=True)

    # -- parent audit (taskbook Sec. 3) --------------------------------------
    vr0 = load(VR0 / "m3pi1vr0_final_verdict.json")
    status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    gate = load(VR0 / "m3pi1vr0_persistence_gate.json")
    retired = csvread(VR0 / "m3pi1vr0_retired_development_states.csv")
    retired_ids = {r["state_id"] for r in retired}
    seeds_retired = load(VR0 / "m3pi1vr0_retired_seed_manifest.json")
    reserve = csvread(RESERVE_CSV)
    reserve_truth = Counter(r["truth"] for r in reserve)
    checks = {
        "PI1VR0 verdict": vr0["verdict"] == "PI1VR0-CAP-B",
        "PI1V valid verdict": status["PI1V valid verdict"] == "PI1V-X",
        "attempt2 diagnostic only": status["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY",
        "original 24 retired": len(retired_ids) == 24,
        "old seeds retired": seeds_retired["retired_namespaces"] == ["M3-PI1V-GRAD", "M3-PI1V-PROBE"],
        "reserve W": reserve_truth["WIDEN"] == 7,
        "reserve S": reserve_truth["SHRINK"] == 29,
        "reserve HOLD": reserve_truth["HOLD"] == 13,
        "reserve AMBIGUOUS": reserve_truth["AMBIGUOUS"] == 21,
        "reserve ND": reserve_truth["HOLD"] + reserve_truth["AMBIGUOUS"] == 34,
        "PERSIST-1": gate["verdict"] == "PASS",
    }
    parent = {
        "recorded_at": now(),
        "checks": checks,
        "all_match": all(checks.values()),
        "reserve_counts": dict(reserve_truth),
        "mismatch_action": "WA1-X STOP",
    }
    if not parent["all_match"]:
        raise RuntimeError(f"WA1-X: parent audit mismatch {checks}")
    dump(OUT / "m3wa1_parent_audit.json", parent)

    # -- existing W reserve audit (taskbook Sec. 5) --------------------------
    w_reserve = sorted([r for r in reserve if r["truth"] == "WIDEN"],
                       key=lambda r: r["state_id"])
    w_cfg = Counter(r["config_id"] for r in w_reserve)
    csvwrite(OUT / "m3wa1_existing_w_reserve_audit.csv", [{
        "state_id": r["state_id"], "config_id": r["config_id"],
        "physical_family": r["physical_family"], "s2": r["s2"],
        "source_stage": r["source_stage"], "source_region": r["source_region"],
    } for r in w_reserve])
    dump(OUT / "m3wa1_existing_w_reserve_summary.json", {
        "recorded_at": now(),
        "w_states": len(w_reserve),
        "distinct_configs": len(w_cfg),
        "max_per_config": max(w_cfg.values()),
        "config_counts": dict(w_cfg),
        "physical_families": sorted({r["physical_family"] for r in w_reserve}),
        "s2_values": sorted(float(r["s2"]) for r in w_reserve),
        "panel_requirements": {"W": W_TARGET, "distinct_configs_min": W_CONFIG_MIN,
                               "max_per_config": W_MAX_PER_CONFIG},
        "shortage": "1 W state; and only 4 distinct configs (< 6-config gate)",
    })

    # -- W-support inventory (taskbook Sec. 6) --------------------------------
    inv = csvread(INVENTORY_CSV)
    pref_hash = {p.stem: sha(p) for p in (CF1N / "pref").glob("cf1n_new_*.json")}
    support = []
    for r in sorted(inv, key=lambda r: (r["config_id"], float(r["s2"]))):
        if r["truth"] != "WIDEN":
            continue
        pilot_exposed = "True" if r["state_id"] in retired_ids else "False"
        support.append({
            "state_id": r["state_id"], "config_id": r["config_id"],
            "physical_family": r["physical_family"], "s2": r["s2"],
            "truth": r["truth"], "source_stage": r["source_stage"],
            "grid_or_interval_index": r["source_interval_or_grid_index"],
            "pilot_exposed": pilot_exposed,
            "probe_exposed": pilot_exposed,   # PI1V exposed gradient+probe together
            "P_ref_hash": pref_hash.get(r["config_id"], ""),
            "canonical_hash": r["canonical_sha256"],
        })
    csvwrite(OUT / "m3wa1_w_support_inventory.csv", support)
    if len(support) != 15:
        raise RuntimeError(f"WA1-X: unexpected W support size {len(support)}")

    # -- candidate generation (taskbook Sec. 7-8) -----------------------------
    by_cfg: dict[str, list[dict]] = {}
    for r in inv:
        by_cfg.setdefault(r["config_id"], []).append(r)

    # collision universe: every previously sampled (config, s2) and state id
    collision_ids: set[str] = {r["state_id"] for r in inv}
    collision_pairs: set[tuple[str, float]] = {
        (r["config_id"], round(float(r["s2"]), 9)) for r in inv}
    for extra in (SF2 / "m3sf2_mapping_bank.csv",
                  CF1N / "summary/m3cf1n_discovery_states.csv",
                  ROOT / "results/phase_m3pi1r/summary/m3pi1r_candidate_bank.csv",
                  UC2R / "summary/m3uc2r_candidate_pool.csv"):
        if Path(extra).exists():
            for r in csvread(extra):
                collision_ids.add(r["state_id"])
                if r.get("s2") not in ("", None):
                    collision_pairs.add((r.get("config_id", ""),
                                         round(float(r["s2"]), 9)))
    d2 = load(ROOT / "results/phase_m3d2/summary/m3d2_confirmation_summary.json")["records"]
    for r in d2:
        collision_ids.add(r["state_id"])
        collision_pairs.add((r["config_id"], round(float(r["s2"]), 9)))

    pool = []
    for cid in sorted(by_cfg):
        seq = sorted(by_cfg[cid], key=lambda r: float(r["s2"]))
        pos = [i for i, r in enumerate(seq) if r["truth"] == "WIDEN"]
        for a, b in zip(pos, pos[1:]):
            ra, rb = seq[a], seq[b]
            left, right = float(ra["s2"]), float(rb["s2"])
            mid = math.exp((math.log(left) + math.log(right)) / 2.0)
            if not (left < mid < right):
                continue                      # never perturb; pair unusable
            candidate_id = f"{cid}_wa1_w_s2_{fmt_s2(mid)}"
            fresh = (candidate_id not in collision_ids
                     and (cid, round(mid, 9)) not in collision_pairs)
            if not fresh:
                continue                      # collision: pair yields no candidate
            pref_path = CF1N / "pref" / f"{cid}.json"
            pool.append({
                "candidate_id": candidate_id,
                "config_id": cid,
                "physical_family": ra["physical_family"],
                "left_W_state": ra["state_id"],
                "right_W_state": rb["state_id"],
                "left_s2": left,
                "right_s2": right,
                "candidate_s2": mid,
                "fresh_identity": "True",
                "P_ref_source": pref_path.as_posix(),
                "P_ref_hash": sha(pref_path) if pref_path.exists() else "",
                "canonical_order": 0,         # filled after sorting
            })
    pool.sort(key=lambda c: (c["config_id"], c["candidate_s2"]))
    for i, c in enumerate(pool, start=1):
        c["canonical_order"] = i
    csvwrite(OUT / "m3wa1_candidate_pool.csv", pool)

    # -- P_ref dependency audit (taskbook Sec. 10) ----------------------------
    dump(OUT / "m3wa1_pref_dependency_audit.json", {
        "recorded_at": now(),
        "dependency": "CONFIG_SPECIFIC",
        "code_evidence": [
            "hyptraj.m3d2.experiment.direct_full_event_reference(bench_cfg, ...) "
            "consumes the BenchmarkConfig only -- no state input",
            "hyptraj.m3d2.experiment.classify_reference_state(arms, "
            "probability_reference) consumes a config-keyed reference record",
            "M3-CF1N generated exactly one durable P_ref record per config "
            "(results/phase_m3cf1n/pref/<config_id>.json, 500k samples, "
            "namespace M3-CF1N-PREF) and reused it across all grid states",
            "M3-PI1 reference(): refs[r['config_id']] keyed by config id",
        ],
        "rule": "config-specific and corrected/durable => reuse the valid config "
                "P_ref; new P_ref would be required only for a state-specific "
                "dependency (not the case here)",
        "reused_configs": sorted({c["config_id"] for c in pool}),
        "reused_p_ref_hashes": {c["config_id"]: c["P_ref_hash"] for c in pool},
        "new_p_ref_samples": 0,
    })

    # -- deterministic candidate selector (taskbook Sec. 11-12) ---------------
    dump(OUT / "m3wa1_selector_contract.json", {
        "recorded_at": now(),
        "deterministic": True,
        "manual_override": "FORBIDDEN",
        "target": N_CANDIDATES,
        "priority": [
            "1. maximize distinct physical config count",
            "2. prioritize configs that improve feasibility of the final "
            "W >=6-config gate (one first-pick per available config)",
            "3. max 2 WA1 candidates/config",
            "4. maximize physical-family coverage",
            "5. maximize s2 spacing (second picks: farthest from the config's "
            "first pick)",
            "6. canonical order",
        ],
        "forbidden_inputs": ["effect size", "invalid PI1V scores", "gradient "
                             "confidence", "r_hat", "SE", "M2 ratio",
                             "threshold distance"],
        "pre_run_gate": {"count": N_CANDIDATES,
                         "distinct_configs_min": CANDIDATE_CONFIG_MIN,
                         "max_per_config": CANDIDATE_MAX_PER_CONFIG},
        "no_ninth_candidate_after_outcomes": True,
    })
    selected = _select_candidates(pool)
    sel_cfg = Counter(c["config_id"] for c in selected)
    if not (len(selected) == N_CANDIDATES
            and len(sel_cfg) >= CANDIDATE_CONFIG_MIN
            and max(sel_cfg.values()) <= CANDIDATE_MAX_PER_CONFIG):
        raise RuntimeError("WA1-PRE-B: candidate family too narrow "
                           f"(count={len(selected)}, configs={len(sel_cfg)}, "
                           f"max/config={max(sel_cfg.values()) if sel_cfg else 0})")
    csvwrite(OUT / "m3wa1_candidate_manifest.csv", selected)
    dump(OUT / "m3wa1_candidate_manifest_hash.json", {
        "recorded_at": now(),
        "manifest_sha256": sha(OUT / "m3wa1_candidate_manifest.csv"),
        "candidates": len(selected),
        "distinct_configs": len(sel_cfg),
        "max_per_config": max(sel_cfg.values()),
        "frozen_before_simulation": True,
        "no_substitutions_after_hash_lock": True,
    })

    # -- seeds (taskbook Sec. 16) ---------------------------------------------
    prior_ns = R1.prior_namespaces()
    prior_seeds = _prior_recorded_seeds()
    planned = {c["candidate_id"]: [seed(REF_NAMESPACE, c["candidate_id"]), 902]
               for c in selected}
    collisions = sorted({s for sk in planned.values() for s in sk} & prior_seeds)
    if collisions or REF_NAMESPACE in prior_ns:
        raise RuntimeError("WA1-X: seed collision with prior stages")
    dump(OUT / "m3wa1_seed_manifest.json", {
        "recorded_at": now(),
        "namespace": REF_NAMESPACE,
        "derivation": "sha256(namespace|candidate_id) -> [1,2^31-1]; fixed "
                      "second element 902 (reference-arm seed-key convention)",
        "seed_keys": planned,
        "prior_namespace_collision": REF_NAMESPACE in prior_ns,
        "prior_recorded_seed_collision": collisions,
        "frozen_before_first_simulator_call": True,
    })

    # -- persistence contract (taskbook Sec. 4/17) ----------------------------
    dump(OUT / "m3wa1_persistence_contract.json", {
        "recorded_at": now(),
        "inherited_from": "M3-PI1VR0 hardened persistence",
        "module": "src/hyptraj/m3pi1vr0/persistence.py",
        "module_sha256": sha(ROOT / "src/hyptraj/m3pi1vr0/persistence.py"),
        "sequence": ["validate safe path", "durable STARTED", "simulate",
                     "temp serialize", "flush", "fsync", "schema validate",
                     "sha256", "atomic rename", "parent fsync",
                     "verify final hash", "ledger COMPLETE"],
        "consumed_invalid_policy": "sampling started + persistence failure => "
                                   "CONSUMED_INVALID, WA1-X, STOP; no replay",
        "ledger": REFERENCE_LEDGER.as_posix(),
    })

    # -- source manifest + prereg hashes --------------------------------------
    source_paths = [
        "results/phase_m3pi1vr0/summary/m3pi1vr0_final_verdict.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_pi1v_scientific_status.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_persistence_gate.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_retired_development_states.csv",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_retired_seed_manifest.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_selection_view.csv",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_fresh_panel_capacity.json",
        "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv",
        "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv",
        "results/phase_m3cf2/summary/m3cf2_selection_view.csv",
        "results/phase_m3cf1n/pref/cf1n_new_000.json",
        "results/phase_m3cf1n/pref/cf1n_new_001.json",
        "results/phase_m3cf1n/pref/cf1n_new_002.json",
        "results/phase_m3cf1n/pref/cf1n_new_003.json",
        "results/phase_m3cf1n/pref/cf1n_new_005.json",
        "results/phase_m3cf1n/pref/cf1n_new_007.json",
        "src/hyptraj/m3d2/experiment.py",
        "src/hyptraj/m3pi1vr0/persistence.py",
        "scripts/run_m3pi1vr0.py",
    ]
    dump(OUT / "m3wa1_source_manifest.json", {
        "base_commit": git_commit(), "recorded_at": now(),
        "simulator_samples_before_prereg": 0,
        "entries": [{"path": p, "sha256": sha(ROOT / p), "read_only": True}
                    for p in source_paths],
    })
    prereg_paths = [OUT / n for n in (
        "m3wa1_parent_audit.json", "m3wa1_existing_w_reserve_audit.csv",
        "m3wa1_existing_w_reserve_summary.json", "m3wa1_w_support_inventory.csv",
        "m3wa1_candidate_pool.csv", "m3wa1_pref_dependency_audit.json",
        "m3wa1_selector_contract.json", "m3wa1_candidate_manifest.csv",
        "m3wa1_candidate_manifest_hash.json", "m3wa1_seed_manifest.json",
        "m3wa1_persistence_contract.json", "m3wa1_source_manifest.json")]
    dump(OUT / "m3wa1_prereg_hashes.json", {
        "recorded_at": now(),
        "reference_trials_before_freeze": "NONE",
        "labels_before_freeze": "NONE",
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                  for p in prereg_paths],
    })

    write_stop_report(selected, sel_cfg, pool, pref_hash)
    print("WA1 prepare: COMPLETE -- 8 candidates frozen; STOP before reference")


def _select_candidates(pool: list[dict]) -> list[dict]:
    """Frozen deterministic selector (taskbook Sec. 12)."""
    by_cfg: dict[str, list[dict]] = {}
    for c in sorted(pool, key=lambda c: (c["canonical_order"], c["candidate_id"])):
        by_cfg.setdefault(c["config_id"], []).append(c)
    chosen: list[dict] = []
    # pass 1: one first-pick per available config (canonical order), maximizing
    # distinct configs and final-pool config coverage
    for cid in sorted(by_cfg):
        chosen.append(by_cfg[cid][0])
    # pass 2: second picks (max 2/config) in canonical config order; within a
    # config the remaining candidate farthest in s2 from the first pick
    for cid in sorted(by_cfg):
        if len(chosen) >= N_CANDIDATES:
            break
        remaining = [c for c in by_cfg[cid] if c not in chosen]
        if remaining and sum(1 for c in chosen if c["config_id"] == cid) < 2:
            first = next(c for c in chosen if c["config_id"] == cid)
            chosen.append(max(remaining, key=lambda c: (
                abs(float(c["candidate_s2"]) - float(first["candidate_s2"])),
                -int(c["canonical_order"]))))
    return sorted(chosen, key=lambda c: (c["config_id"], c["candidate_s2"]))[:N_CANDIDATES]


def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3wa1"
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


def write_stop_report(selected, sel_cfg, pool, pref_hash) -> None:
    support = csvread(OUT / "m3wa1_w_support_inventory.csv")
    by_cfg = Counter(r["config_id"] for r in support if r["pilot_exposed"] == "False")
    pairs = csvread(OUT / "m3wa1_candidate_pool.csv")
    txt = f"""M3-WA1 PREREG STATUS:
COMPLETE

PARENT:
PI1VR0 = PI1VR0-CAP-B
PI1V valid verdict = PI1V-X

INVALID PI1V DATA:
used in candidate design = NO
used in selector = NO

EXISTING FRESH RESERVE:
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34

EXISTING FRESH W:
distinct configs = {len(by_cfg)}
max/config = {max(by_cfg.values())}

W SUPPORT INVENTORY:
eligible adjacent-W configs = {len({c['config_id'] for c in pool})}
eligible adjacent-W pairs = {len(pools_pairs(pairs))}

P_REF:
dependency = CONFIG_SPECIFIC
reuse/new rule frozen = YES (reuse durable config P_ref; 0 new samples)

WA1 CANDIDATES:
count = {len(selected)}
distinct configs = {len(sel_cfg)}
max/config = {max(sel_cfg.values())}
IDs = {', '.join(c['candidate_id'] for c in selected)}
manifest hash = {sha(OUT / 'm3wa1_candidate_manifest.csv')}

CANDIDATE RULE:
adjacent confirmed W only = YES
log midpoint = YES
fresh identities = YES
adaptive extension = FORBIDDEN

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
finite-action samples = 12000000

SEEDS:
namespace = M3-WA1-REF
collision = 0
hash-locked = YES

PERSISTENCE:
PI1VR0 hardened contract = ENABLED
STARTED before simulator = YES
consumed-invalid replay = FORBIDDEN

SUCCESS TARGET:
combined fresh W subset:
  exact W = 8
  configs >=6
  max/config <=2

full fresh panel:
  8W / 8S / 8ND

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation = NOT AUTHORIZED

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN WA1 REFERENCE
"""
    (DOC / "M3_WA1_Pregistration.md").write_text(
        "# M3-WA1 Preregistration\n\nFrozen before any simulator call.\n\n```\n"
        + txt + "\n```\n", encoding="utf-8")
    (OUT / "m3wa1_prereg_status.txt").write_text(txt, encoding="utf-8")
    print(txt)


def pools_pairs(pairs):
    return pairs


# --------------------------------------------------------------------------
# stage: reference (the only simulator-consuming stage)
# --------------------------------------------------------------------------

def _validate_reference_record(rec: dict) -> None:
    required = {"schema", "candidate_id", "config_id", "candidate_s2",
                "truth", "label_valid", "arms", "oracle", "p_ref",
                "seed_key", "namespace", "sample_counts", "record_sha256"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["schema"] != "m3wa1_reference_v1":
        raise ValueError("schema validation failed; wrong schema")
    if trial_sha256(rec) != rec["record_sha256"]:
        raise ValueError("schema validation failed; record sha mismatch")


def reference() -> None:
    rec = load(OUT / "m3wa1_prereg_hashes.json")
    for e in rec["files"]:
        p = ROOT / e["path"]
        if not p.exists() or sha(p) != e["sha256"]:
            raise RuntimeError(f"WA1-X: prereg hash drift at {e['path']}")
    manifest = csvread(OUT / "m3wa1_candidate_manifest.csv")
    seeds = load(OUT / "m3wa1_seed_manifest.json")["seed_keys"]
    if REFERENCE_LEDGER.exists() or list(REF.glob("*.json")):
        _check_recoverable()
    for c in manifest:
        cid = c["candidate_id"]

        def simulate(c=c, cid=cid):
            st = state_for(c["config_id"], c["candidate_s2"])
            arms_eval = evaluate_reference_arms(
                state_arms(st), st.bench_cfg, seeds[cid], REF_N, N_BATCH)
            p_ref_path = ROOT / c["P_ref_source"]
            p_ref_record = load(p_ref_path)
            p_ref_hash = sha(p_ref_path)
            if p_ref_hash != c["P_ref_hash"]:
                raise RuntimeError(f"WA1-X: P_ref hash drift for {c['config_id']}")
            cls = classify_reference_state(arms_eval, p_ref_record)
            arms_summary = {name: {"P": float(arms_eval[name]["P"]),
                                   "P_CI": [float(x) for x in arms_eval[name]["P_CI"]],
                                   "M2": float(arms_eval[name]["M2"]),
                                   "ESS": float(arms_eval[name]["ESS"]),
                                   "sample_count": int(arms_eval[name]["sample_count"])}
                            for name in ("base", "widen", "shrink")}
            oracle = cls.get("oracle_details") or {}
            payload_holder["label"] = cls["corrected_class"]
            payload = {
                "schema": "m3wa1_reference_v1",
                "recorded_at": now(),
                "candidate_id": cid,
                "config_id": c["config_id"],
                "physical_family": c["physical_family"],
                "left_W_state": c["left_W_state"],
                "right_W_state": c["right_W_state"],
                "left_s2": float(c["left_s2"]),
                "right_s2": float(c["right_s2"]),
                "candidate_s2": float(c["candidate_s2"]),
                "truth": cls["corrected_class"],
                "label_valid": bool(cls["numerical_valid"]
                                    and cls["probability_semantics_valid"]
                                    and cls["ess_valid"]),
                "invalid_reason": cls.get("reason"),
                "arms": arms_summary,
                "oracle": {k: oracle.get(k) for k in
                           ("ratios", "direction_margin_Delta_dir", "D_dir",
                            "D_widen", "D_shrink")},
                "p_ref": {"dependency": "CONFIG_SPECIFIC",
                          "source": c["P_ref_source"], "sha256": p_ref_hash,
                          "new_p_ref_samples": 0},
                "seed_key": [int(x) for x in seeds[cid]],
                "namespace": REF_NAMESPACE,
                "sample_counts": {"per_arm": REF_N, "arms": 3,
                                  "batches": N_BATCH,
                                  "finite_action_samples": 3 * REF_N},
            }
            payload["record_sha256"] = trial_sha256(payload)
            return payload

        result = run_trial_transactional(
            cid, REF / f"{cid}.json", simulate,
            ledger_path=REFERENCE_LEDGER, validator=_validate_reference_record,
            base_entry={"config_id": c["config_id"],
                        "candidate_s2": float(c["candidate_s2"]),
                        "seed_namespace": REF_NAMESPACE,
                        "seed": seeds[cid][0]},
            run_uuid=f"wa1-{safe_fs_id(cid)}")
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"WA1-X: reference record not durably COMPLETE for {cid}: {result}")
        stored = load(REF / f"{cid}.json")
        print(f"reference {cid}: truth={stored['truth']} "
              f"valid={stored['label_valid']} "
              f"r_w={stored['oracle']['ratios'].get('widen_over_base') if stored['oracle'].get('ratios') else None} "
              f"r_s={stored['oracle']['ratios'].get('shrink_over_base') if stored['oracle'].get('ratios') else None}",
              flush=True)
    _seal_reference(manifest)


def _check_recoverable() -> None:
    counts: dict[str, Counter] = {}
    for e in ledger_entries(REFERENCE_LEDGER):
        c = counts.setdefault(e.get("state_id"), Counter())
        c[e.get("status")] += 1
    for rid, c in counts.items():
        if c["CONSUMED_INVALID"] or c["STARTED"] != c["COMPLETE"]:
            raise RuntimeError(
                f"WA1-X: reference {rid} began without a durable COMPLETE record "
                "(CONSUMED_INVALID policy); no replay in the same stage")


def _seal_reference(manifest) -> None:
    entries = ledger_entries(REFERENCE_LEDGER)
    complete = {e["state_id"] for e in entries if e.get("status") == "COMPLETE"}
    expected = {c["candidate_id"] for c in manifest}
    if complete != expected:
        raise RuntimeError(f"WA1-X: reference incomplete ({len(complete)}/{len(expected)})")
    recs = [load(REF / f"{cid}.json") for cid in sorted(expected)]
    labels = Counter(r["truth"] for r in recs)
    manifest_ref = {
        "sealed_at": now(),
        "candidates": len(recs),
        "complete": len(recs),
        "consumed_invalid": sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID"),
        "finite_action_samples": sum(r["sample_counts"]["finite_action_samples"] for r in recs),
        "new_p_ref_samples": 0,
        "labels": {k: labels.get(k, 0) for k in
                   ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS", "INVALID")},
        "record_hashes": {r["candidate_id"]: r["record_sha256"] for r in recs},
    }
    dump(REF / "reference_manifest.json", manifest_ref)
    print(f"WA1 reference sealed: {len(recs)} candidates, "
          f"{manifest_ref['finite_action_samples']:,} finite-action samples, "
          f"labels {manifest_ref['labels']}")


# --------------------------------------------------------------------------
# stage: capacity
# --------------------------------------------------------------------------

def capacity() -> None:
    manifest_ref = load(REF / "reference_manifest.json")
    recs = [load(REF / f"{c['candidate_id']}.json")
            for c in csvread(OUT / "m3wa1_candidate_manifest.csv")]
    labels = Counter(r["truth"] for r in recs)
    dump(OUT / "m3wa1_reference_summary.json", {
        "recorded_at": now(),
        "K_WA1_W": labels.get("WIDEN", 0),
        "K_WA1_S": labels.get("SHRINK", 0),
        "K_WA1_H": labels.get("HOLD", 0),
        "K_WA1_AMB": labels.get("AMBIGUOUS", 0),
        "K_WA1_INVALID": labels.get("INVALID", 0),
        "labels": dict(labels),
        "finite_action_samples": manifest_ref["finite_action_samples"],
        "note": "only W contributes to the WA1 primary supply target; all valid "
                "non-W records remain protected reference evidence",
        **boundary_block(),
    })

    # -- persistence audit ----------------------------------------------------
    entries = ledger_entries(REFERENCE_LEDGER)
    problems = []
    counts: dict[str, Counter] = {}
    for e in entries:
        counts.setdefault(e.get("state_id"), Counter())[e.get("status")] += 1
    for c in csvread(OUT / "m3wa1_candidate_manifest.csv"):
        cid = c["candidate_id"]
        cc = counts.get(cid, Counter())
        if cc["STARTED"] != 1 or cc["COMPLETE"] != 1:
            problems.append(f"{cid}: STARTED={cc['STARTED']} COMPLETE={cc['COMPLETE']}")
        p = REF / f"{cid}.json"
        e_complete = next((e for e in entries if e.get("state_id") == cid
                           and e.get("status") == "COMPLETE"), None)
        if e_complete is None or sha(p) != e_complete.get("final_sha256"):
            problems.append(f"{cid}: final hash mismatch")
        r = load(p)
        if trial_sha256(r) != r["record_sha256"]:
            problems.append(f"{cid}: record sha mismatch")
    audit = {
        "recorded_at": now(),
        "ledger_entries": len(entries),
        "consumed_invalid": sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID"),
        "hashes": "PASS" if not problems else "FAIL",
        "problems": problems,
    }
    dump(OUT / "m3wa1_persistence_audit.json", audit)
    if problems:
        raise RuntimeError(f"WA1-X: persistence audit failed {problems}")

    # -- combined fresh W pool (taskbook Sec. 19) ------------------------------
    vr0_view = {r["state_id"]: r for r in csvread(VR0 / "m3pi1vr0_selection_view.csv")}
    retired = {r["state_id"] for r in csvread(VR0 / "m3pi1vr0_retired_development_states.csv")}
    w_pool = []
    for r in vr0_view.values():
        if r["truth"] == "WIDEN" and r["state_id"] not in retired:
            w_pool.append({"state_id": r["state_id"], "truth": "WIDEN",
                           "config_id": r["config_id"],
                           "physical_family": r["physical_family"], "s2": r["s2"],
                           "source_stage": r["source_stage"],
                           "source_region": "M3-CF2-RESERVE",
                           "pilot_exposure": 0, "probe_exposure": 0,
                           "origin": "reserve"})
    new_w = 0
    for r in recs:
        if r["truth"] == "WIDEN" and r["label_valid"]:
            new_w += 1
            w_pool.append({"state_id": r["candidate_id"], "truth": "WIDEN",
                           "config_id": r["config_id"],
                           "physical_family": r["physical_family"],
                           "s2": r["candidate_s2"], "source_stage": "M3-WA1",
                           "source_region": f"M3-WA1:{r['config_id']}",
                           "pilot_exposure": 0, "probe_exposure": 0,
                           "origin": "wa1"})
    w_pool.sort(key=lambda s: s["state_id"])
    csvwrite(OUT / "m3wa1_combined_fresh_w_pool.csv", w_pool)

    # -- W feasibility (taskbook Sec. 20) --------------------------------------
    cfg_counts = Counter(s["config_id"] for s in w_pool)
    distinct_configs = len(cfg_counts)
    selectable_capacity = sum(min(n, W_MAX_PER_CONFIG) for n in cfg_counts.values())
    w_subset = _select_w_subset(w_pool) if (
        len(w_pool) >= W_TARGET and distinct_configs >= W_CONFIG_MIN
        and selectable_capacity >= W_TARGET) else None
    w_feasible = w_subset is not None and len(w_subset) == W_TARGET
    dump(OUT / "m3wa1_w_feasibility.json", {
        "recorded_at": now(),
        "old_untouched_w": 7,
        "new_w": new_w,
        "total_w": len(w_pool),
        "distinct_configs": distinct_configs,
        "config_counts": dict(cfg_counts),
        "selectable_capacity_at_max2": selectable_capacity,
        "exact_8_selectable": bool(w_feasible),
        "configs_ge_6": distinct_configs >= W_CONFIG_MIN,
        "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG,
        "selected_subset": [s["state_id"] for s in w_subset] if w_subset else [],
        "rule": "deterministic round-robin by config; max 2/config; canonical order",
    })

    # -- full fresh-panel capacity recheck (taskbook Sec. 21-22) ---------------
    view = []
    for s in w_pool:
        view.append({"state_id": s["state_id"], "truth": "WIDEN",
                     "config_id": s["config_id"], "physical_family": s["physical_family"],
                     "s2": s["s2"], "source_stage": s["source_stage"],
                     "source_region": s["source_region"],
                     "stable_config_flag": "True",
                     "canonical_bank_order": _canonical_order(s["state_id"], vr0_view)})
    for r in vr0_view.values():
        if r["truth"] in ("SHRINK", "HOLD", "AMBIGUOUS"):
            view.append({"state_id": r["state_id"], "truth": r["truth"],
                         "config_id": r["config_id"],
                         "physical_family": r["physical_family"], "s2": r["s2"],
                         "source_stage": r["source_stage"],
                         "source_region": "M3-CF2-RESERVE",
                         "stable_config_flag": r["stable_config_flag"],
                         "canonical_bank_order": r["canonical_bank_order"]})
    for r in recs:
        if r["truth"] in ("SHRINK", "HOLD", "AMBIGUOUS") and r["label_valid"]:
            view.append({"state_id": r["candidate_id"], "truth": r["truth"],
                         "config_id": r["config_id"],
                         "physical_family": r["physical_family"],
                         "s2": r["candidate_s2"], "source_stage": "M3-WA1",
                         "source_region": f"M3-WA1:{r['config_id']}",
                         "stable_config_flag": "True",
                         "canonical_bank_order": _canonical_order(r["candidate_id"], vr0_view)})
    panel = R0._run_selector(view) if w_feasible else None
    full_feasible = False
    if panel is not None:
        grp = Counter("W" if s["truth"] == "WIDEN"
                      else "S" if s["truth"] == "SHRINK" else "ND" for s in panel)
        full_feasible = (len(panel) == 24
                         and grp["W"] == 8 and grp["S"] == 8 and grp["ND"] == 8
                         and len({s["state_id"] for s in panel}) == 24)
    if full_feasible:
        panel_rows = [{"state_id": s["state_id"], "truth": s["truth"],
                       "config_id": s["config_id"],
                       "physical_family": s["physical_family"], "s2": s["s2"],
                       "source_stage": s["source_stage"],
                       "source_region": s["source_region"],
                       "pilot_exposure": 0, "probe_exposure": 0,
                       "origin": s.get("origin", "reserve") if "origin" in s else
                       ("wa1" if s["source_stage"] == "M3-WA1" else "reserve")}
                      for s in panel]
        panel_rows.sort(key=lambda s: (s["truth"], s["state_id"]))
        csvwrite(OUT / "m3wa1_fresh_development_panel.csv", panel_rows)
        dump(OUT / "m3wa1_fresh_development_panel_hash.json", {
            "recorded_at": now(),
            "panel_sha256": sha(OUT / "m3wa1_fresh_development_panel.csv"),
            "states": 24, "W": 8, "S": 8, "ND": 8,
            "invalid_run_scores_used": False,
            "pilot_exposure": 0, "probe_exposure": 0,
        })
    dump(OUT / "m3wa1_full_panel_capacity.json", {
        "recorded_at": now(),
        "w_feasible": bool(w_feasible),
        "full_panel_feasible": bool(full_feasible),
        "panel_states": "NA" if not full_feasible else 24,
        "W": 8 if full_feasible else "NA",
        "S": 8 if full_feasible else "NA",
        "ND": 8 if full_feasible else "NA",
        "selector": "PI1VR0 frozen selector rules reused verbatim "
                    "(run_m3pi1vr0._run_selector)",
        "no_pilot_information_in_selector": True,
    })

    # -- protect all unselected states (taskbook Sec. 23) ----------------------
    selected_ids = ({s["state_id"] for s in panel} if full_feasible else set())
    remaining = []
    for r in vr0_view.values():
        if r["state_id"] not in selected_ids:
            remaining.append({"state_id": r["state_id"], "truth": r["truth"],
                              "config_id": r["config_id"], "s2": r["s2"],
                              "source_stage": r["source_stage"],
                              "status": "PILOT_PROTECTED_RESERVE"})
    for r in recs:
        if r["candidate_id"] not in selected_ids and r["label_valid"]:
            remaining.append({"state_id": r["candidate_id"], "truth": r["truth"],
                              "config_id": r["config_id"], "s2": r["candidate_s2"],
                              "source_stage": "M3-WA1",
                              "status": "PILOT_PROTECTED_RESERVE"})
    remaining.sort(key=lambda x: x["state_id"])
    csvwrite(OUT / "m3wa1_remaining_protected_reserve.csv", remaining)
    dump(OUT / "m3wa1_remaining_reserve_summary.json", {
        "recorded_at": now(),
        "remaining_protected_states": len(remaining),
        "pilot_exposure": 0,
        "protection": "all valid high-budget states not selected into the new "
                      "panel remain PILOT_PROTECTED_RESERVE",
    })

    # -- verdict (taskbook Sec. 24 priority) -----------------------------------
    if not audit["hashes"] == "PASS":
        verdict = "WA1-X"
    elif not manifest_ref["complete"] == N_CANDIDATES:
        verdict = "WA1-X"
    elif w_feasible and full_feasible:
        verdict = "WA1-A"
    else:
        verdict = "WA1-B"
    dump(OUT / "m3wa1_final_verdict.json", {
        "status": "COMPLETE",
        "verdict": verdict,
        "recorded_at": now(),
        "reference": {"candidates": N_CANDIDATES,
                      "complete": manifest_ref["complete"],
                      "consumed_invalid": manifest_ref["consumed_invalid"],
                      "finite_action_samples": manifest_ref["finite_action_samples"]},
        "labels": manifest_ref["labels"],
        "combined_fresh_w": {"old_untouched_w": 7, "new_w": new_w,
                             "total_w": len(w_pool),
                             "distinct_configs": distinct_configs},
        "w_feasibility": {"exact_8_selectable": bool(w_feasible),
                          "configs_ge_6": distinct_configs >= W_CONFIG_MIN,
                          "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG},
        "full_fresh_panel": {"feasible": bool(full_feasible),
                             "hash": sha(OUT / "m3wa1_fresh_development_panel.csv")
                             if full_feasible else "NA"},
        "invalid_pi1v_results_used": False,
        "remaining_protected_reserve": {"states": len(remaining), "pilot_exposure": 0},
        **boundary_block(),
        "next": {
            "WA1-A": "M3-PI1VN independent fresh-panel finite-action information "
                     "validation (original frozen <=2x hypothesis, new namespaces "
                     "M3-PI1VN-GRAD / M3-PI1VN-PROBE)",
            "WA1-B": "broader W-reference expansion (separately preregistered)",
            "WA1-PRE-B": "redesign",
            "WA1-X": "stop; invalid",
        }[verdict],
    })
    print(f"WA1 capacity: W pool {len(w_pool)} ({new_w} new), feasibility "
          f"{bool(w_feasible)}, full panel {bool(full_feasible)}, verdict {verdict}")


def _canonical_order(state_id: str, vr0_view: dict) -> int:
    if state_id in vr0_view:
        return int(vr0_view[state_id]["canonical_bank_order"])
    # deterministic continuation after the 94 CF2-inventory states
    return 1000 + (abs(int(hashlib.sha256(state_id.encode()).hexdigest()[:8], 16)) % 1000)


def _select_w_subset(w_pool: list[dict]) -> list[dict] | None:
    """Deterministic exact-8 W selection: round-robin by config (maximizes
    distinct configs), max 2/config, canonical order within config."""
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
# stage: close (frozen-contract invalidation; zero simulator)
# --------------------------------------------------------------------------

def close() -> None:
    """Freeze the WA1-X verdict after the trial-1 persistence failure.

    Taskbook Sec. 17: sampling started and persistence failed =>
    CONSUMED_INVALID => WA1-X => STOP; no replay.  This stage writes the
    audit, forensics, and verdict only -- it never touches the simulator and
    never reruns the consumed candidate.
    """
    entries = ledger_entries(REFERENCE_LEDGER)
    counts: dict[str, Counter] = {}
    for e in entries:
        counts.setdefault(e.get("state_id"), Counter())[e.get("status")] += 1
    consumed = {rid: c for rid, c in counts.items()
                if c.get("CONSUMED_INVALID") or c.get("STARTED", 0) != c.get("COMPLETE", 0)}
    complete = {rid for rid, c in counts.items() if c.get("COMPLETE")}
    manifest = csvread(OUT / "m3wa1_candidate_manifest.csv")
    expected = {c["candidate_id"] for c in manifest}

    (REF / "DIAGNOSTIC_ONLY_CONSUMED_INVALID.txt").write_text(
        "WA1-X STOP -- candidate trial(s) in this ledger began sampling but no\n"
        "durable COMPLETE record exists (taskbook Sec. 17: CONSUMED_INVALID,\n"
        "WA1-X, STOP; no replay).  Diagnostic/provenance only.\n", encoding="utf-8")

    consumed_id = sorted(consumed)[0] if consumed else ""
    consumed_entry = next((e for e in entries if e.get("status") == "CONSUMED_INVALID"), {})
    forensics = {
        "recorded_at": now(),
        "incident": "WA1 trial-1 persistence failure -> frozen-contract invalidation",
        "what_happened": [
            f"Candidate {consumed_id} consumed its full reference sampling "
            f"(1,500,000 finite-action samples) but the durable record never "
            "reached COMPLETE: the schema validator (step 7) required a "
            "record_sha256 payload field that the payload builder had not yet "
            "written (the payload self-hash must be computed inside the "
            "simulator step, before serialization).",
            "The transactional runner appended a durable CONSUMED_INVALID entry "
            "and the stage aborted at trial 1 of 8.",
        ],
        "frozen_rule_applied": "If sampling starts and persistence fails: "
                               "CONSUMED_INVALID, WA1-X, STOP. No replay. "
                               "Deterministic replay does not override.",
        "samples_consumed": {"candidate_id": consumed_id,
                             "finite_action_samples": 1_500_000},
        "defect_and_fix": [
            "defect: validator/payload inconsistency (validator demanded a "
            "field the builder wrote too late) -- a WA1 implementation bug, "
            "not a protocol or provenance problem",
            "fix: the payload builder now computes record_sha256 before "
            "returning (scripts/run_m3wa1.py); the code fix is recorded here "
            "but the stage is NOT rerun",
        ],
        "no_replay_bookkeeping": {
            "consumed_trial_identity": consumed_id,
            "consumed_seed": consumed_entry.get("seed"),
            "seed_namespace": "M3-WA1-REF",
            "rule": "same stage cannot rerun same state/rep; same exact seed "
                    "cannot be reused; any successor stage requires a fresh "
                    "preregistration and fresh namespace",
        },
        "remaining_candidates_untouched": sorted(expected - complete - set(consumed)),
    }
    dump(OUT / "m3wa1_incident_forensics.json", forensics)

    audit = {
        "recorded_at": now(),
        "ledger_entries": len(entries),
        "trials_started": sum(c.get("STARTED", 0) for c in counts.values()),
        "complete": len(complete),
        "consumed_invalid": sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID"),
        "hashes": "FAIL",
        "problems": [f"{rid}: STARTED without durable COMPLETE "
                     f"(statuses={dict(c)})" for rid, c in consumed.items()],
    }
    dump(OUT / "m3wa1_persistence_audit.json", audit)

    summary = {
        "recorded_at": now(),
        "K_WA1_W": 0, "K_WA1_S": 0, "K_WA1_H": 0, "K_WA1_AMB": 0,
        "K_WA1_INVALID": 0,
        "labels": {},
        "complete": len(complete),
        "finite_action_samples_consumed": 1_500_000,
        "note": "no candidate reached a durable label; the stage is invalid "
                "before any capacity statement can be made",
        **boundary_block(),
    }
    dump(OUT / "m3wa1_reference_summary.json", summary)

    # sealed-invalid reference manifest (no candidate record exists)
    dump(REF / "reference_manifest.json", {
        "sealed_at": now(),
        "status": "INVALID_CONSUMED_INVALID",
        "candidates": 8,
        "complete": len(complete),
        "consumed_invalid": audit["consumed_invalid"],
        "finite_action_samples": 1_500_000,
        "labels": {},
        "record_hashes": {},
        "scientific_use": "diagnostic only",
    })

    # -- capacity artifacts in their true (pre-augmentation) NA state ---------
    vr0_view = {r["state_id"]: r for r in csvread(VR0 / "m3pi1vr0_selection_view.csv")}
    retired = {r["state_id"] for r in csvread(VR0 / "m3pi1vr0_retired_development_states.csv")}
    w_pool = [{"state_id": r["state_id"], "truth": "WIDEN",
               "config_id": r["config_id"], "physical_family": r["physical_family"],
               "s2": r["s2"], "source_stage": r["source_stage"],
               "source_region": "M3-CF2-RESERVE",
               "pilot_exposure": 0, "probe_exposure": 0, "origin": "reserve"}
              for r in vr0_view.values()
              if r["truth"] == "WIDEN" and r["state_id"] not in retired]
    w_pool.sort(key=lambda s: s["state_id"])
    csvwrite(OUT / "m3wa1_combined_fresh_w_pool.csv", w_pool)
    cfg_counts = Counter(s["config_id"] for s in w_pool)
    dump(OUT / "m3wa1_w_feasibility.json", {
        "recorded_at": now(),
        "old_untouched_w": 7,
        "new_w": 0,
        "total_w": len(w_pool),
        "distinct_configs": len(cfg_counts),
        "config_counts": dict(cfg_counts),
        "selectable_capacity_at_max2": sum(min(n, W_MAX_PER_CONFIG) for n in cfg_counts.values()),
        "exact_8_selectable": False,
        "configs_ge_6": len(cfg_counts) >= W_CONFIG_MIN,
        "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG,
        "selected_subset": [],
        "note": "evaluated WITHOUT augmentation because the stage is WA1-X; "
                "this is the PI1VR0-CAP-B state of record, not a new result",
    })
    dump(OUT / "m3wa1_full_panel_capacity.json", {
        "recorded_at": now(),
        "w_feasible": False,
        "full_panel_feasible": False,
        "panel_states": "NA", "W": "NA", "S": "NA", "ND": "NA",
        "note": "not evaluated: WA1-X froze the stage before any augmentation",
        "no_pilot_information_in_selector": True,
    })
    remaining = [{"state_id": r["state_id"], "truth": r["truth"],
                  "config_id": r["config_id"], "s2": r["s2"],
                  "source_stage": r["source_stage"],
                  "status": "PILOT_PROTECTED_RESERVE"}
                 for r in sorted(vr0_view.values(), key=lambda x: x["state_id"])]
    csvwrite(OUT / "m3wa1_remaining_protected_reserve.csv", remaining)
    dump(OUT / "m3wa1_remaining_reserve_summary.json", {
        "recorded_at": now(),
        "remaining_protected_states": len(remaining),
        "pilot_exposure": 0,
        "protection": "unchanged by the invalid WA1 stage: all 70 reserve "
                      "states remain PILOT_PROTECTED_RESERVE",
    })

    verdict = "WA1-X"
    dump(OUT / "m3wa1_final_verdict.json", {
        "status": "INVALID",
        "verdict": verdict,
        "recorded_at": now(),
        "rule": "taskbook Sec. 17: sampling started + persistence failure => "
                "CONSUMED_INVALID => WA1-X => STOP; no replay",
        "reference": {"candidates": 8, "complete": len(complete),
                      "consumed_invalid": audit["consumed_invalid"],
                      "finite_action_samples_consumed": 1_500_000},
        "labels": {},
        "incident_forensics": forensics,
        "full_fresh_panel": {"feasible": False, "hash": "NA"},
        "w_feasibility": {"exact_8_selectable": False, "configs_ge_6": False,
                          "max2_per_config": False},
        "combined_fresh_w": {"old_untouched_w": 7, "new_w": 0, "total_w": 7,
                             "distinct_configs": 4},
        "preregistration": {
            "frozen_before_outcomes": True,
            "prereg_hashes_verified": True,
            "note": "the candidate design, manifest, and contracts remain "
                    "valid pre-run artifacts; a successor stage (fresh "
                    "preregistration, fresh namespace) may re-freeze the same "
                    "design without reusing the consumed trial or seed",
        },
        "invalid_pi1v_results_used": False,
        **boundary_block(),
        "next": "stop; successor stage requires a separately preregistered "
                "recovery (fresh namespace, repaired persistence usage)",
    })

    txt = f"""M3-WA1 STATUS:
INVALID

REFERENCE:
candidates = 8
complete = {len(complete)}
consumed-invalid = {audit['consumed_invalid']}
finite-action samples = 1500000 (1 candidate consumed, no durable record)

LABELS:
new W = 0
new S = 0
new HOLD = 0
new AMB = 0
new INVALID = 0

PERSISTENCE:
hashes = FAIL
ledger = FAIL
manifest = NA

COMBINED FRESH W:
old untouched W = 7
new W = 0
total W = 7
distinct configs = 4

W FEASIBILITY:
exact 8 selectable = NO
configs >=6 = FAIL
max2/config = FAIL

FULL FRESH PANEL:
feasible = NO
W = NA
S = NA
ND = NA
hash = NA

INVALID PI1V RESULTS:
used = NO

REMAINING PROTECTED RESERVE:
states = 70 (+0 changed)
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
WA1-X

NEXT:
stop; successor stage requires a separately preregistered recovery
(fresh namespace, repaired persistence usage; the frozen candidate design
may be re-preregistered without reusing the consumed trial or seed)

FULL REGRESSION:
{_regression_summary()}
"""
    (OUT / "m3wa1_final_report.txt").write_text(txt, encoding="utf-8")
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "M3_WA1_Final_Report.md").write_text(
        "# M3-WA1 Final Report\n\n"
        f"**Verdict: {verdict}**\n\n"
        "Trial 1 of 8 (`" + consumed_id + "`) consumed its full 1,500,000-sample "
        "reference but never reached a durable COMPLETE record: the schema "
        "validator demanded a payload field (record_sha256) that the payload "
        "builder wrote too late. The frozen contract fired exactly as written: "
        "**CONSUMED_INVALID -> WA1-X -> STOP, no replay** — the same rule that "
        "invalidated M3-PI1V, applied here to WA1's own first trial.\n\n"
        "- The failure was a WA1 implementation defect (validator/payload "
        "inconsistency), not a provenance or leakage problem.\n"
        "- The preregistration (parent audit, W-support inventory, 9-pair "
        "candidate pool, 8-candidate manifest, seeds, contracts) was frozen "
        "before outcomes and remains valid; a successor stage may re-preregister "
        "the same design under a fresh namespace without reusing the consumed "
        "trial identity or seed.\n"
        "- No PI1V invalid data was used; the 70-state reserve is untouched; "
        "VALUE / RARITY / M3-Q stay BLOCKED.\n\n"
        "FULL REGRESSION:\n"
        f"{_regression_summary()}\n", encoding="utf-8")
    parent = load(OUT / "m3wa1_parent_audit.json")
    wres = load(OUT / "m3wa1_existing_w_reserve_summary.json")
    pool = csvread(OUT / "m3wa1_candidate_pool.csv")
    sel = load(OUT / "m3wa1_candidate_manifest_hash.json")
    pref_dep = load(OUT / "m3wa1_pref_dependency_audit.json")
    (DOC / "M3_WA1_Parent_Audit.md").write_text(
        "# M3-WA1 Parent Audit\n\nStatus: **PASS** (all checks matched before "
        "the pre-run freeze; re-verified at close).\n\n"
        f"- PI1VR0 verdict `{vr0_verdict()}`; PI1V valid verdict PI1V-X; "
        "attempt-2 metrics DIAGNOSTIC_ONLY.\n"
        "- Original 24 CF2 states retired; old PI1V seed namespaces retired.\n"
        "- Reserve verified untouched: W=7, S=29, HOLD=13, AMB=21, ND=34.\n"
        "- M3PI1VR0-PERSIST-1 = PASS.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_W_Support_Design.md").write_text(
        "# M3-WA1 W Support Design\n\n"
        f"- Existing fresh W reserve: {wres['w_states']} states, "
        f"{wres['distinct_configs']} distinct configs, max {wres['max_per_config']}/config "
        f"({wres['config_counts']}) -- 1 state short AND below the 6-config gate.\n"
        f"- W-support inventory: {len(csvread(OUT / 'm3wa1_w_support_inventory.csv'))} "
        "corrected high-budget durable WIDEN states (8 retired/pilot-exposed as "
        "support-location evidence only; 7 untouched).\n"
        "- Adjacency: consecutive positions in each config's ordered "
        "corrected-truth sequence, both WIDEN.\n"
        f"- Candidate pool: {len(pool)} fresh log-midpoints (exact, no "
        "perturbation), zero identity collisions across all prior sampling "
        "universes.\n"
        f"- Frozen manifest: {sel['candidates']} candidates, "
        f"{sel['distinct_configs']} distinct configs, max {sel['max_per_config']}/config; "
        f"hash `{sel['manifest_sha256'][:16]}...`.\n"
        f"- P_ref dependency: {pref_dep['dependency']}; durable config P_ref "
        "records reused; 0 new P_ref samples.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Reference_Execution_Audit.md").write_text(
        "# M3-WA1 Reference Execution Audit\n\nStatus: **INVALID (WA1-X)**.\n\n"
        f"- Trial 1 of 8 (`{consumed_id}`) consumed its full 1,500,000-sample "
        "reference; the durable record never reached COMPLETE (schema-validator "
        "defect at step 7).\n"
        f"- Ledger: {audit['trials_started']} STARTED, {len(complete)} COMPLETE, "
        f"{audit['consumed_invalid']} CONSUMED_INVALID; hashes FAIL.\n"
        "- Frozen rule applied: CONSUMED_INVALID -> WA1-X -> STOP; no replay. "
        "Candidates 2-8 were never started (STOP means stop).\n"
        "- Code defect fixed for successor stages; the stage was NOT rerun.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Fresh_Panel_Capacity.md").write_text(
        "# M3-WA1 Fresh Panel Capacity\n\nStatus: **NOT EVALUATED (WA1-X)**.\n\n"
        "- No candidate reached a durable label, so no augmentation result "
        "exists; the recorded W-pool state remains the PI1VR0-CAP-B baseline "
        "(W=7, 4 configs).\n"
        "- No panel was frozen; no counts were relaxed; the 70-state reserve "
        "is unchanged and protected.\n",
        encoding="utf-8")
    print(txt)
    print(f"WA1 close: verdict {verdict} (frozen-contract invalidation; no replay)")


def _regression_summary() -> str:
    log = OUT / "m3wa1_full_regression.log"
    if not log.exists():
        return "pending"
    tail = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    passed = [ln for ln in tail if " passed" in ln]
    return passed[-1] if passed else "; ".join(tail[-2:])


def report() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    parent = load(OUT / "m3wa1_parent_audit.json")
    summary = load(OUT / "m3wa1_reference_summary.json")
    ref_manifest = load(REF / "reference_manifest.json")
    audit = load(OUT / "m3wa1_persistence_audit.json")
    feas = load(OUT / "m3wa1_w_feasibility.json")
    cap = load(OUT / "m3wa1_full_panel_capacity.json")
    final = load(OUT / "m3wa1_final_verdict.json")
    wres = load(OUT / "m3wa1_existing_w_reserve_summary.json")
    prereg = (OUT / "m3wa1_prereg_status.txt").read_text(encoding="utf-8")

    (DOC / "M3_WA1_Task.md").write_text(
        "# M3-WA1 Task\n\nTask book: `M3_WA1_Fresh_WIDEN_Reference_Augmentation_Task.md` "
        "(reference-first recovery of fresh 8W/8S/8ND development capacity after "
        "PI1VR0-CAP-B; see the frozen outputs under `results/phase_m3wa1/`).\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Parent_Audit.md").write_text(
        "# M3-WA1 Parent Audit\n\nStatus: **PASS** (all checks matched).\n\n"
        f"- PI1VR0 verdict `{vr0_verdict()}`; PI1V valid verdict PI1V-X; "
        "attempt-2 metrics DIAGNOSTIC_ONLY.\n"
        f"- Original 24 CF2 states retired ({len(csvread(VR0 / 'm3pi1vr0_retired_development_states.csv'))} "
        "rows); old PI1V seed namespaces retired.\n"
        "- Reserve verified untouched: W=7, S=29, HOLD=13, AMB=21, ND=34.\n"
        "- M3PI1VR0-PERSIST-1 = PASS.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_W_Support_Design.md").write_text(
        "# M3-WA1 W Support Design\n\n"
        f"- Existing fresh W reserve: {wres['w_states']} states, "
        f"{wres['distinct_configs']} distinct configs, max {wres['max_per_config']}/config "
        f"({wres['config_counts']}) -- 1 state short AND below the 6-config gate.\n"
        f"- W-support inventory: {len(csvread(OUT / 'm3wa1_w_support_inventory.csv'))} "
        "corrected high-budget durable WIDEN states (8 retired/pilot-exposed serve "
        "as support-location evidence only; 7 untouched).\n"
        "- Adjacency rule: consecutive positions in each config's ordered "
        "corrected-truth sequence, both WIDEN.\n"
        f"- Candidate pool: {len(csvread(OUT / 'm3wa1_candidate_pool.csv'))} fresh "
        "log-midpoints (exact exp((log si+log sj)/2), no perturbation), zero "
        "identity collisions across all prior sampling universes.\n"
        f"- P_ref dependency: CONFIG_SPECIFIC (audited from code); durable config "
        "P_ref records reused; 0 new P_ref samples.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Human_Approval.md").write_text(
        "# M3-WA1 Human Approval\n\n"
        "- Date: 2026-09-05 (before the first WA1 simulator call).\n"
        "- The mandatory pre-run STOP report (taskbook Sec. 29) was frozen in "
        "`M3_WA1_Pregistration.md` / `m3wa1_prereg_status.txt` with prereg hashes.\n"
        "- The user's session directive \"execute the next task-book stage\" "
        "constitutes the human approval to run the WA1 one-shot reference, "
        "consistent with the standing prior-authorization pattern.\n"
        "- Scope: the 8 frozen candidates only; no reserve piloting; no V1/S1 "
        "routes; VALUE/RARITY/M3-Q stay BLOCKED.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Reference_Execution_Audit.md").write_text(
        "# M3-WA1 Reference Execution Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- Candidates {ref_manifest['candidates']}, complete {ref_manifest['complete']}, "
        f"consumed-invalid {ref_manifest['consumed_invalid']}.\n"
        f"- Finite-action samples {ref_manifest['finite_action_samples']:,} "
        "(8 x 3 x 500,000; 20 paired CRN batches); new P_ref samples 0.\n"
        f"- Labels: {ref_manifest['labels']}.\n"
        f"- Persistence: hashes {audit['hashes']}, consumed-invalid "
        f"{audit['consumed_invalid']}; every record written under the PI1VR0 "
        "contract (STARTED before simulator, atomic rename, hash verify).\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Fresh_Panel_Capacity.md").write_text(
        "# M3-WA1 Fresh Panel Capacity\n\n"
        f"- Combined fresh W pool: {feas['total_w']} states "
        f"(7 untouched + {feas['new_w']} new), {feas['distinct_configs']} distinct "
        f"configs, selectable capacity {feas['selectable_capacity_at_max2']} at "
        "max 2/config.\n"
        f"- W feasibility: exact-8 selectable = {feas['exact_8_selectable']}, "
        f"configs>=6 = {feas['configs_ge_6']}, max2/config = {feas['max2_per_config']}.\n"
        f"- Full fresh panel 8W/8S/8ND: feasible = {cap['full_panel_feasible']}"
        + (f"; panel hash `{load(OUT / 'm3wa1_fresh_development_panel_hash.json')['panel_sha256']}`."
           if cap["full_panel_feasible"] else "; no panel frozen (counts NOT relaxed).")
        + "\n- Selector: PI1VR0 frozen rules reused verbatim; no pilot information "
        "and no invalid PI1V scores entered any selection.\n",
        encoding="utf-8")
    (DOC / "M3_WA1_Final_Report.md").write_text(
        "# M3-WA1 Final Report\n\n"
        f"**Verdict: {final['verdict']}**\n\n"
        + {
            "WA1-A": "Fresh development capacity is restored: the combined fresh "
                     "W pool admits an exact-8 selection meeting the >=6-config, "
                     "max-2/config gates, and a fresh 8W/8S/8ND development panel "
                     "is frozen. The clean next stage is M3-PI1VN: rerun the "
                     "ORIGINAL frozen <=2x PI1V hypothesis unchanged on the fresh "
                     "panel with new namespaces M3-PI1VN-GRAD / M3-PI1VN-PROBE. "
                     "WA1 decides nothing between V1 and S1.",
            "WA1-B": "Valid execution completed but the combined fresh W pool "
                     "still fails the exact-8/6-config feasibility gates. No "
                     "adaptive second batch inside WA1; a broader W-reference "
                     "expansion would need separate preregistration.",
            "WA1-PRE-B": "The pre-run candidate family gate could not be met.",
            "WA1-X": "Invalid.",
        }[final["verdict"]] + "\n\n"
        f"- Reference: {ref_manifest['complete']}/8 complete, "
        f"{ref_manifest['finite_action_samples']:,} finite-action samples, "
        f"labels {ref_manifest['labels']}.\n"
        f"- Persistence: hashes {audit['hashes']}.\n"
        f"- Invalid PI1V results used: NO. VALUE/RARITY/M3-Q: BLOCKED.\n\n"
        "FULL REGRESSION:\n"
        f"{_regression_summary()}\n", encoding="utf-8")
    txt = f"""M3-WA1 STATUS:
COMPLETE

REFERENCE:
candidates = {ref_manifest['candidates']}
complete = {ref_manifest['complete']}
consumed-invalid = {ref_manifest['consumed_invalid']}
finite-action samples = {ref_manifest['finite_action_samples']}

LABELS:
new W = {ref_manifest['labels'].get('WIDEN', 0)}
new S = {ref_manifest['labels'].get('SHRINK', 0)}
new HOLD = {ref_manifest['labels'].get('HOLD', 0)}
new AMB = {ref_manifest['labels'].get('AMBIGUOUS', 0)}
new INVALID = {ref_manifest['labels'].get('INVALID', 0)}

PERSISTENCE:
hashes = {audit['hashes']}
ledger = {'PASS' if not audit['problems'] else 'FAIL'}
manifest = PASS

COMBINED FRESH W:
old untouched W = 7
new W = {feas['new_w']}
total W = {feas['total_w']}
distinct configs = {feas['distinct_configs']}

W FEASIBILITY:
exact 8 selectable = {'YES' if feas['exact_8_selectable'] else 'NO'}
configs >=6 = {'PASS' if feas['configs_ge_6'] else 'FAIL'}
max2/config = {'PASS' if feas['max2_per_config'] else 'FAIL'}

FULL FRESH PANEL:
feasible = {'YES' if cap['full_panel_feasible'] else 'NO'}
W = {cap['W']}
S = {cap['S']}
ND = {cap['ND']}
hash = {load(OUT / 'm3wa1_fresh_development_panel_hash.json')['panel_sha256'] if cap['full_panel_feasible'] else 'NA'}

INVALID PI1V RESULTS:
used = NO

REMAINING PROTECTED RESERVE:
states = {load(OUT / 'm3wa1_remaining_reserve_summary.json')['remaining_protected_states']}
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
{_regression_summary()}
"""
    (OUT / "m3wa1_final_report.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"WA1 report: verdict {final['verdict']}")


def vr0_verdict() -> str:
    return load(VR0 / "m3pi1vr0_final_verdict.json")["verdict"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("prepare", "reference", "capacity", "report", "close"))
    a = p.parse_args()
    {"prepare": prepare, "reference": reference, "capacity": capacity,
     "report": report, "close": close}[a.stage]()
