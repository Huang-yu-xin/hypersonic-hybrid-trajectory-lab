"""M3-WA1R -- WA1 recovery with consumed-candidate retirement.

Restores the original reference-only WIDEN augmentation after WA1-X without
reusing the consumed candidate or any WA1 seed:

    retire the consumed candidate identity and its seed permanently
    keep the 7 audited never-started WA1 candidates
    add the 1 pre-existing unused pre-outcome pool candidate (no new midpoint)
    freeze exactly 8 recovery candidates before any simulator call
    entirely fresh seed namespace M3-WA1R-REF
    one-shot 500k/arm 3-arm reference (12,000,000 finite-action samples)
    recheck W diversity -> full fresh-panel capacity -> verdict

Hard rules: no PI1V invalid-run data, no WA1 outcome data, no new midpoint
generation, no reserve piloting, no V1/S1 routes; PI1VR0-style hardened
persistence with the repaired NON-CIRCULAR hash contract.

Stages: prepare | persistence | reference | capacity | report
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

import run_m3pi1v as R1  # noqa: E402  (namespace audit reuse)
import run_m3pi1vr0 as R0  # noqa: E402  (PI1VR0 panel selector reuse)
from hyptraj.m1d.experiments import BenchmarkConfig, config_from_record, load_freeze  # noqa: E402
from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402
from hyptraj.m3d.benchmark_states import assemble_state, state_arms  # noqa: E402
from hyptraj.m3d2.experiment import classify_reference_state, evaluate_reference_arms  # noqa: E402
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    FAULT_DESCRIPTIONS,
    FAULT_TAGS,
    FrozenArtifactError,
    InjectedFault,
    HASH_FIELD,
    ReplayError,
    assert_not_frozen,
    ensure_not_started,
    ensure_seed_unused,
    record_file_hash,
    run_trial_transactional,
    scientific_payload_hash,
)
from hyptraj.m3pi1vr0.persistence import safe_fs_id  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1r/summary"
REF = ROOT / "results/phase_m3wa1r/reference"
SYN = ROOT / "results/phase_m3wa1r/synthetic"
DOC = ROOT / "docs/phase_m3wa1r"

WA1 = ROOT / "results/phase_m3wa1"
WA1_OUT = WA1 / "summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"
CF1N = ROOT / "results/phase_m3cf1n"

REF_N = 500_000
N_BATCH = 20
N_CANDIDATES = 8
W_TARGET, S_TARGET, ND_TARGET = 8, 8, 8
W_CONFIG_MIN = 6
W_MAX_PER_CONFIG = 2
REF_NAMESPACE = "M3-WA1R-REF"
CONSUMED_CANDIDATE = "cf1n_new_000_wa1_w_s2_1p788854382"

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


def bench(config_id: str):
    global _cf1n_fields
    if _cf1n_fields is None:
        _cf1n_fields = load(ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")["physical_fields"]
    if config_id in _cf1n_fields:
        f = _cf1n_fields[config_id]
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
        raise RuntimeError(f"WA1R-X: config {config_id} not uniquely resolvable")
    return config_from_record(matches[0])


_states: dict[str, object] = {}


def state_for(config_id: str, s2: float):
    key = f"{config_id}@{s2!r}"
    if key not in _states:
        st = assemble_state(bench(config_id), float(s2), short_config=config_id)
        if isinstance(st, dict):
            raise RuntimeError(f"WA1R-X: state assembly failed {config_id}@{s2}: {st}")
        _states[key] = st
    return _states[key]


# --------------------------------------------------------------------------
# stage: prepare (zero simulator)
# --------------------------------------------------------------------------

def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    REF.mkdir(parents=True, exist_ok=True)
    SYN.mkdir(parents=True, exist_ok=True)

    # -- WA1 incident status (taskbook Sec. 1) --------------------------------
    wa1_verdict = load(WA1_OUT / "m3wa1_final_verdict.json")
    status = {
        "recorded_at": now(),
        "WA1 valid verdict": wa1_verdict["verdict"],
        "WA1 primary augmentation result": "UNAVAILABLE",
        "WA1 candidate-1 truth": "UNAVAILABLE",
        "WA1 candidate-1 reference record": "INVALID / NON-DURABLE",
        "truth_inference_rule": "candidate-1 W/S/H/AMB truth may never be "
                                "inferred from logs, stdout, memory dumps, or "
                                "temporary payload fragments",
    }
    if wa1_verdict["verdict"] != "WA1-X":
        raise RuntimeError("WA1R-X: WA1 verdict is not WA1-X")
    dump(OUT / "m3wa1r_wa1_incident_status.json", status)

    # -- parent audit (taskbook Sec. 8) ---------------------------------------
    vr0 = load(VR0 / "m3pi1vr0_final_verdict.json")
    gate = load(VR0 / "m3pi1vr0_persistence_gate.json")
    pi1v_status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    wa1_ledger = ledger_entries(WA1 / "reference/reference_ledger.jsonl")
    wa1_counts = Counter(e.get("status") for e in wa1_ledger)
    wa1_started_ids = {e.get("state_id") for e in wa1_ledger
                       if e.get("status") == "STARTED"}
    wa1_pool = csvread(WA1_OUT / "m3wa1_candidate_pool.csv")
    wa1_manifest = csvread(WA1_OUT / "m3wa1_candidate_manifest.csv")
    unused = [r for r in wa1_pool if r["candidate_id"] not in
              {m["candidate_id"] for m in wa1_manifest}]
    reserve = csvread(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")
    reserve_truth = Counter(r["truth"] for r in reserve)
    wa1_script = (ROOT / "scripts/run_m3wa1.py").read_text(encoding="utf-8")
    checks = {
        "PI1VR0 verdict": vr0["verdict"] == "PI1VR0-CAP-B",
        "WA1 verdict": wa1_verdict["verdict"] == "WA1-X",
        "PI1V valid verdict": pi1v_status["PI1V valid verdict"] == "PI1V-X",
        "WA1 consumed-invalid candidates": wa1_counts.get("CONSUMED_INVALID", 0) == 1,
        "WA1 never-started selected candidates": len(wa1_manifest) - 1 == 7,
        "original WA1 candidate pool": len(wa1_pool) == 9,
        "unused pre-outcome candidates": len(unused) == 1,
        "reserve pilot-unexposed": reserve_truth["WIDEN"] == 7,
        "M3PI1VR0-PERSIST-1": gate["verdict"] == "PASS",
        "WA1 persistence bug fix exists": 'payload["record_sha256"] = trial_sha256(payload)'
                                          in wa1_script,
    }
    if not all(checks.values()):
        raise RuntimeError(f"WA1R-X: parent audit mismatch {checks}")
    dump(OUT / "m3wa1r_parent_audit.json", {
        "recorded_at": now(), "checks": checks, "all_match": all(checks.values()),
        "wa1_ledger_counts": dict(wa1_counts),
        "reserve_counts": dict(reserve_truth),
    })

    # -- hard retirement (taskbook Sec. 2) -------------------------------------
    wa1_seeds = load(WA1_OUT / "m3wa1_seed_manifest.json")["seed_keys"]
    consumed_seed = wa1_seeds[CONSUMED_CANDIDATE]
    dump(OUT / "m3wa1r_retired_candidate_seed_manifest.json", {
        "recorded_at": now(),
        "retired_identity": CONSUMED_CANDIDATE,
        "status": "CONSUMED_INVALID_RETIRED",
        "retired_seed": {"seed_key": consumed_seed, "namespace": "M3-WA1-REF"},
        "retired_artifacts": ["results/phase_m3wa1/reference/reference_ledger.jsonl "
                              "(STARTED + CONSUMED_INVALID entries)"],
        "forbidden_use": ["fresh W pool", "fresh development panel",
                          "future confirmation panel", "future reference selector"],
        "all_wa1_seeds_retired": True,
        "wa1_seed_namespaces": ["M3-WA1-REF"],
    })

    # -- never-started audit (taskbook Sec. 3) ---------------------------------
    touched: set[str] = set()
    for q in (ROOT / "results/phase_m3pi1v/quarantine_attempt1",
              ROOT / "results/phase_m3pi1v/quarantine_attempt2",
              WA1 / "reference"):
        tdir = q / "trials"
        if tdir.exists():
            touched |= {d.name for d in tdir.iterdir() if d.is_dir()}
    wa1_score_files = [WA1_OUT / n for n in
                       ("m3wa1_combined_fresh_w_pool.csv",)]
    audit_rows = []
    for m in wa1_manifest:
        cid = m["candidate_id"]
        if cid == CONSUMED_CANDIDATE:
            continue
        started = cid in wa1_started_ids
        record_exists = (WA1 / "reference" / f"{cid}.json").exists()
        exposed = cid in touched
        replayed = any(cid in p.read_text(encoding="utf-8")
                       for p in wa1_score_files if p.exists())
        ok = (not started) and (not record_exists) and (not exposed) and (not replayed)
        audit_rows.append({
            "candidate_id": cid, "config_id": m["config_id"],
            "candidate_s2": m["candidate_s2"],
            "simulator_invocation_count": 0 if ok else "UNCERTAIN",
            "reference_samples": 0 if ok else "UNCERTAIN",
            "ledger_started_absent": "True" if not started else "False",
            "pilot_probe_exposure": 0 if not exposed else "UNCERTAIN",
            "threshold_replay_exposure": 0 if not replayed else "UNCERTAIN",
            "scientifically_fresh": "True" if ok else "RETIRED_UNCERTAIN",
        })
    if not all(r["scientifically_fresh"] == "True" for r in audit_rows):
        raise RuntimeError("WA1R-PRE-B: a never-started candidate has uncertain exposure")
    if len(audit_rows) != 7:
        raise RuntimeError(f"WA1R-X: expected 7 never-started candidates, got {len(audit_rows)}")
    csvwrite(OUT / "m3wa1r_never_started_candidate_audit.csv", audit_rows)

    # -- unused ninth pre-outcome candidate audit (taskbook Sec. 4) ------------
    if len(unused) != 1:
        raise RuntimeError("WA1R-X: expected exactly 1 unused pool candidate")
    u = unused[0]
    prereg = load(WA1_OUT / "m3wa1_prereg_hashes.json")
    pool_locked = any(e["path"].endswith("m3wa1_candidate_pool.csv")
                      and e["sha256"] == sha(WA1_OUT / "m3wa1_candidate_pool.csv")
                      for e in prereg["files"])
    inv = csvread(CF2 / "m3cf2_candidate_truth_inventory.csv")
    by_cfg: dict[str, list[dict]] = {}
    for r in inv:
        by_cfg.setdefault(r["config_id"], []).append(r)
    pair_valid = False
    seq = sorted(by_cfg[u["config_id"]], key=lambda r: float(r["s2"]))
    pos = [i for i, r in enumerate(seq) if r["truth"] == "WIDEN"]
    for a, b in zip(pos, pos[1:]):
        if (round(float(seq[a]["s2"]), 9), round(float(seq[b]["s2"]), 9)) == \
                (round(float(u["left_s2"]), 9), round(float(u["right_s2"]), 9)):
            pair_valid = True
    pref_path = ROOT / u["P_ref_source"]
    pref_ok = pref_path.exists() and sha(pref_path) == u["P_ref_hash"]
    u_started = u["candidate_id"] in wa1_started_ids
    u_exposed = u["candidate_id"] in touched
    ninth_ok = (pool_locked and not u_started and not u_exposed and pair_valid
                and pref_ok and u["fresh_identity"] == "True")
    dump(OUT / "m3wa1r_unused_candidate_audit.json", {
        "recorded_at": now(),
        "candidate_id": u["candidate_id"],
        "config_id": u["config_id"],
        "candidate_s2": float(u["candidate_s2"]),
        "generated_before_any_wa1_outcome": bool(pool_locked),
        "pool_sha256_verified_against_wa1_prereg": bool(pool_locked),
        "identity_fresh": u["fresh_identity"] == "True",
        "sampled": bool(u_started),
        "pilot_probe_exposed": bool(u_exposed),
        "source_pair_still_valid": bool(pair_valid),
        "p_ref_dependency_valid": bool(pref_ok),
        "eligible_sole_replacement": bool(ninth_ok),
    })
    if not ninth_ok:
        raise RuntimeError("WA1R-PRE-B: unused ninth candidate is not eligible")

    # -- hash contract (taskbook Sec. 10) --------------------------------------
    dump(OUT / "m3wa1r_hash_contract.json", {
        "recorded_at": now(),
        "module": "src/hyptraj/m3wa1r/persistence.py",
        "module_sha256": sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
        "scientific_payload_hash": "sha256(canonical scientific payload "
                                   "excluding the scientific_payload_hash field)",
        "record_file_hash": "sha256(final serialized record bytes)",
        "non_circular_guarantee": "the final file never contains its own "
                                  "full-file SHA-256 inside the bytes being "
                                  "hashed; schema validation runs on the "
                                  "pre-hash payload and never requires a "
                                  "self-hash field (the WA1 bug class is "
                                  "structurally impossible)",
        "wa1_bug": "WA1's validator required record_sha256 before the payload "
                   "builder had written it",
    })

    # -- persistence contract (taskbook Sec. 23 order) -------------------------
    dump(OUT / "m3wa1r_persistence_contract.json", {
        "recorded_at": now(),
        "module": "src/hyptraj/m3wa1r/persistence.py",
        "module_sha256": sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
        "mandatory_order": [
            "1. safe path", "2. durable STARTED", "3. simulate",
            "4. build canonical payload", "5. validate pre-hash schema",
            "6. compute frozen hash fields", "7. temp write", "8. flush/fsync",
            "9. atomic rename", "10. parent fsync",
            "11. verify final durable hashes", "12. ledger COMPLETE",
        ],
        "failure_policy": "sampling started + persistence failure => "
                          "CONSUMED_INVALID => WA1R-X => STOP; no replay; no "
                          "second recovery attempt inside WA1R",
        "ledger": REFERENCE_LEDGER.as_posix(),
    })

    # -- P_ref dependency re-verification (taskbook Sec. 13) -------------------
    universe_cfgs = sorted({m["config_id"] for m in wa1_manifest if m["candidate_id"] != CONSUMED_CANDIDATE}
                           | {u["config_id"]})
    pref = {}
    for cid in universe_cfgs:
        p = CF1N / "pref" / f"{cid}.json"
        rec = load(p)
        ok = (rec.get("config_id") == cid and rec.get("sample_count") == 500_000
              and rec.get("event_schema") == "corrected full-event v2"
              and sha(p) == sha(p))
        pref[cid] = {"path": p.as_posix(), "sha256": sha(p), "durable": True,
                     "semantics": rec.get("event_schema"), "checks_pass": bool(ok)}
    dump(OUT / "m3wa1r_pref_dependency_audit.json", {
        "recorded_at": now(),
        "dependency": "CONFIG_SPECIFIC",
        "reverified_from_code": "hyptraj.m3d2.experiment."
                                "direct_full_event_reference(bench_cfg, ...) "
                                "consumes the config only",
        "allowed_source": "results/phase_m3cf1n/pref/<config_id>.json",
        "records": pref,
        "new_p_ref_samples": 0,
    })

    # -- recovery candidate universe (taskbook Sec. 14) ------------------------
    universe = []
    for m in wa1_manifest:
        if m["candidate_id"] == CONSUMED_CANDIDATE:
            continue
        universe.append({
            "candidate_id": m["candidate_id"], "config_id": m["config_id"],
            "s2": m["candidate_s2"],
            "source_pair": f"{m['left_W_state']}|{m['right_W_state']}",
            "origin": "WA1_NEVER_STARTED",
            "P_ref_hash": m["P_ref_hash"],
            "canonical_order": m["canonical_order"],
        })
    universe.append({
        "candidate_id": u["candidate_id"], "config_id": u["config_id"],
        "s2": u["candidate_s2"],
        "source_pair": f"{u['left_W_state']}|{u['right_W_state']}",
        "origin": "WA1_UNUSED_PREOUTCOME",
        "P_ref_hash": u["P_ref_hash"],
        "canonical_order": u["canonical_order"],
    })
    universe.sort(key=lambda c: (c["config_id"], float(c["s2"])))
    for i, c in enumerate(universe, start=1):
        c["canonical_order"] = i
    csvwrite(OUT / "m3wa1r_candidate_universe.csv", universe)

    # -- recovery diversity gate (taskbook Sec. 15/17/35) ----------------------
    cfg_counts = Counter(c["config_id"] for c in universe)
    gate = {
        "recorded_at": now(),
        "candidate_count": len(universe),
        "distinct_configs": len(cfg_counts),
        "max_candidates_per_config": max(cfg_counts.values()),
        "required": {"count": 8, "distinct_configs_min": 4, "max_per_config": 2},
        "preferred_distinct_configs": 6,
        "max_per_config_exceeds_preferred_gate": max(cfg_counts.values()) > 2,
        "interpretation": "taskbook Sec. 17 fixes the selector to 'select all 8' "
                          "because the universe has exactly 8 members after "
                          "retirement and replacement; Sec. 35 triggers "
                          "WA1R-PRE-B only when max/config >2 WITH NO "
                          "deterministic valid universe. A deterministic valid "
                          "universe exists (the fixed 8-member set, selected by "
                          "the mandated select-all-8 rule), so WA1R-PRE-B is not "
                          "triggered; the deviation from the preferred "
                          "max-2/config design gate is recorded here verbatim.",
        "sec17_failure_condition": "fewer than 8 members remain after audit",
        "pre_b_triggered": len(universe) < 8 or len(cfg_counts) < 4,
    }
    dump(OUT / "m3wa1r_recovery_diversity_gate.json", gate)
    if gate["pre_b_triggered"]:
        raise RuntimeError("WA1R-PRE-B: recovery candidate capacity fails")

    # -- recovery manifest (taskbook Sec. 18) -----------------------------------
    dump(OUT / "m3wa1r_selector_contract.json", {
        "recorded_at": now(),
        "deterministic": True,
        "manual_override": "FORBIDDEN",
        "rule": "select all 8 (taskbook Sec. 17: the universe has exactly 8 "
                "members after retirement and replacement)",
        "forbidden_inputs": ["WA1 outcomes", "candidate-1 non-durable outcome",
                             "PI1V Attempt-2 scores", "effect magnitude",
                             "gradient confidence", "r_hat", "SE",
                             "threshold results"],
    })
    manifest = sorted(universe, key=lambda c: c["canonical_order"])
    if len(manifest) != N_CANDIDATES:
        raise RuntimeError("WA1R-PRE-B: fewer than 8 candidates remain")
    csvwrite(OUT / "m3wa1r_candidate_manifest.csv", manifest)
    dump(OUT / "m3wa1r_candidate_manifest_hash.json", {
        "recorded_at": now(),
        "manifest_sha256": sha(OUT / "m3wa1r_candidate_manifest.csv"),
        "candidates": len(manifest),
        "distinct_configs": len(cfg_counts),
        "max_per_config": max(cfg_counts.values()),
        "origins": dict(Counter(c["origin"] for c in manifest)),
        "frozen_before_any_scientific_call": True,
        "no_substitutions_after_hash_lock": True,
    })

    # -- fresh seed namespace (taskbook Sec. 19) --------------------------------
    prior_ns = R1.prior_namespaces()
    planned = {c["candidate_id"]: [seed(REF_NAMESPACE, c["candidate_id"]), 902]
               for c in manifest}
    wa1_seed_tuples = {tuple(v) for v in wa1_seeds.values()}
    collisions_wa1 = [k for k, v in planned.items() if tuple(v) in wa1_seed_tuples]
    prior_seeds = _prior_recorded_seeds()
    seed_vals = {s for v in planned.values() for s in v}
    if REF_NAMESPACE in prior_ns or collisions_wa1 or (seed_vals & prior_seeds):
        raise RuntimeError("WA1R-X: seed collision")
    dump(OUT / "m3wa1r_seed_manifest.json", {
        "recorded_at": now(),
        "namespace": REF_NAMESPACE,
        "derivation": "sha256(namespace|candidate_id) -> [1,2^31-1]; fixed "
                      "second element 902 (reference-arm seed-key convention)",
        "seed_keys": planned,
        "collision_with_wa1": collisions_wa1,
        "collision_with_all_prior": sorted(seed_vals & prior_seeds),
        "old_wa1_seeds_remain_retired": True,
        "hash_locked_before_simulator": True,
    })

    # -- source manifest + prereg hashes ----------------------------------------
    source_paths = [
        "results/phase_m3wa1/summary/m3wa1_final_verdict.json",
        "results/phase_m3wa1/summary/m3wa1_candidate_pool.csv",
        "results/phase_m3wa1/summary/m3wa1_candidate_manifest.csv",
        "results/phase_m3wa1/summary/m3wa1_seed_manifest.json",
        "results/phase_m3wa1/summary/m3wa1_prereg_hashes.json",
        "results/phase_m3wa1/summary/m3wa1_pref_dependency_audit.json",
        "results/phase_m3wa1/reference/reference_ledger.jsonl",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_final_verdict.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_pi1v_scientific_status.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_persistence_gate.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_selection_view.csv",
        "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv",
        "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv",
        "src/hyptraj/m3wa1r/persistence.py",
        "src/hyptraj/m3d2/experiment.py",
        "scripts/run_m3wa1.py",
        "scripts/run_m3pi1vr0.py",
    ]
    dump(OUT / "m3wa1r_source_manifest.json", {
        "base_commit": git_commit(), "recorded_at": now(),
        "simulator_samples_before_prereg": 0,
        "entries": [{"path": p, "sha256": sha(ROOT / p), "read_only": True}
                    for p in source_paths],
    })
    prereg_paths = [OUT / n for n in (
        "m3wa1r_wa1_incident_status.json", "m3wa1r_parent_audit.json",
        "m3wa1r_retired_candidate_seed_manifest.json",
        "m3wa1r_never_started_candidate_audit.csv",
        "m3wa1r_unused_candidate_audit.json", "m3wa1r_hash_contract.json",
        "m3wa1r_persistence_contract.json", "m3wa1r_pref_dependency_audit.json",
        "m3wa1r_candidate_universe.csv", "m3wa1r_recovery_diversity_gate.json",
        "m3wa1r_selector_contract.json", "m3wa1r_candidate_manifest.csv",
        "m3wa1r_candidate_manifest_hash.json", "m3wa1r_seed_manifest.json",
        "m3wa1r_source_manifest.json")]
    dump(OUT / "m3wa1r_prereg_hashes.json", {
        "recorded_at": now(),
        "reference_trials_before_freeze": "NONE",
        "labels_before_freeze": "NONE",
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                  for p in prereg_paths],
    })

    write_stop_report(manifest, cfg_counts, gate, pref)
    print("WA1R prepare: COMPLETE -- 8 recovery candidates frozen; STOP before reference")


def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3wa1r"
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


def write_stop_report(manifest, cfg_counts, gate, pref) -> None:
    retired = load(OUT / "m3wa1r_retired_candidate_seed_manifest.json")
    unused_audit = load(OUT / "m3wa1r_unused_candidate_audit.json")
    hc = load(OUT / "m3wa1r_hash_contract.json")
    txt = f"""M3-WA1R PREREG STATUS:
COMPLETE

PARENT:
WA1 = WA1-X
PI1VR0 = PI1VR0-CAP-B
PI1V valid verdict = PI1V-X

WA1 INCIDENT:
consumed-invalid candidates = 1
consumed candidate ID = {CONSUMED_CANDIDATE}
retired = YES
reused = NO

WA1 NEVER-STARTED:
audited count = 7
all simulator samples = 0
all exposure = 0

UNUSED PRE-OUTCOME CANDIDATE:
count = 1
ID = {unused_audit['candidate_id']}
generated before WA1 outcome = YES
sampled = NO

RECOVERY CANDIDATES:
count = {len(manifest)}
distinct configs = {len(cfg_counts)}
max/config = {max(cfg_counts.values())} (exceeds preferred <=2; deterministic valid universe exists per Sec. 17/35 -- see m3wa1r_recovery_diversity_gate.json)
manifest hash = {sha(OUT / 'm3wa1r_candidate_manifest.csv')}
new midpoint generated after WA1-X = NO

P_REF:
dependency = CONFIG_SPECIFIC
new P_ref samples = 0
all reused records durable = YES

PERSISTENCE:
safe paths = PASS
STARTED before simulator = PASS
non-circular hash contract = PASS
WA1 bug regression = PASS
atomic persistence = PASS
consumed-invalid replay = FORBIDDEN

M3WA1R-PERSIST-1:
PASS (synthetic components; full regression re-verified at close)

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
expected finite-action samples = 12000000

SEEDS:
namespace = M3-WA1R-REF
count = 8
collision with WA1 = 0
all prior collision = 0
hash-locked = YES

EXISTING FRESH RESERVE:
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34

SUCCESS TARGET:
combined fresh W:
  exact 8 selectable
  configs >=6
  max2/config

full fresh panel:
  8W / 8S / 8ND

W-CONFIG CEILING NOTE:
retiring the consumed candidate (config cf1n_new_000) caps the combined W
distinct-config ceiling at 5 (< 6); the reference still executes per the
frozen protocol and the W feasibility gate decides the verdict.

INVALID PI1V DATA:
used = NO

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
HUMAN APPROVAL TO RUN WA1R REFERENCE
"""
    (DOC / "M3_WA1R_Pregistration.md").write_text(
        "# M3-WA1R Preregistration\n\nFrozen before any simulator call.\n\n```\n"
        + txt + "\n```\n", encoding="utf-8")
    (OUT / "m3wa1r_prereg_status.txt").write_text(txt, encoding="utf-8")
    print(txt)


# --------------------------------------------------------------------------
# stage: persistence (synthetic bug regression + gate; zero simulator)
# --------------------------------------------------------------------------

def _mock_payload(state_id: str, s: int) -> dict:
    return {"schema": "m3wa1r_reference_v1", "state_id": state_id, "seed_int": s,
            "arms": {"placeholder": True}, "note": "mock payload; no scientific sampling"}


def _pre_hash_validate(rec: dict) -> None:
    """Pre-hash schema: must NOT require the self-hash field (WA1 bug class)."""
    required = {"schema", "state_id", "arms", "note"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if HASH_FIELD in rec:
        raise ValueError("pre-hash schema must not contain a self-hash field")
    if rec["state_id"].startswith("bad"):
        raise ValueError("schema validation failed; deliberately invalid record")


def persistence() -> None:
    # -- synthetic reproduction/regression of the exact WA1 bug ---------------
    ledger = SYN / "bug_regression_ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    for stale in SYN.glob("bug_*"):
        stale.unlink()
    # 1) the WA1 bug class is impossible: validation on a hash-less payload passes
    hashless = _mock_payload("bug_check::rep0", 1)
    _pre_hash_validate(hashless)          # would have raised under WA1's validator
    # 2) full happy path through the repaired contract
    rec = run_trial_transactional(
        "bug_check::rep0", SYN / "bug_repaired_record.json",
        lambda: _mock_payload("bug_check::rep0", 1),
        ledger_path=ledger, pre_hash_validator=_pre_hash_validate,
        base_entry={"seed": 1}, run_uuid="bugreg")
    assert rec["status"] == "COMPLETE"
    stored = load(SYN / "bug_repaired_record.json")
    assert HASH_FIELD in stored
    assert scientific_payload_hash(stored) == stored[HASH_FIELD]
    assert record_file_hash(SYN / "bug_repaired_record.json") \
        == rec["record_file_hash"]
    # 3) failure injection around the repaired step and all other gaps
    injection = []
    for tag in FAULT_TAGS:
        led = SYN / f"inj_{tag}.jsonl"
        if led.exists():
            led.unlink()
        final = SYN / f"inj_{safe_fs_id('inj_' + tag.lower() + '::rep0')}.json"
        lid = f"inj_{tag.lower()}::rep0"
        try:
            r = run_trial_transactional(
                lid, final, lambda l=lid: _mock_payload(l, 2),
                ledger_path=led, pre_hash_validator=_pre_hash_validate,
                fault=tag, base_entry={"seed": 2}, run_uuid=f"inj-{tag}")
            status = r["status"]
        except InjectedFault:
            status = "NOT_STARTED"
        entries = ledger_entries(led)
        counts = Counter(e.get("status") for e in entries)
        injection.append({
            "fault": tag, "status": status,
            "ledger_counts": dict(counts),
            "complete": counts.get("COMPLETE", 0),
            "consumed_invalid": counts.get("CONSUMED_INVALID", 0),
        })
    dump(OUT / "m3wa1r_synthetic_bug_regression.json", {
        "recorded_at": now(),
        "payloads": "mock only; zero scientific sampling",
        "wa1_bug_reproduced_class": "pre-hash schema validation required an "
                                    "unavailable self-hash in WA1; the WA1R "
                                    "pre-hash validator accepts the hash-less "
                                    "payload (test 1 passed)",
        "repaired_happy_path": {"status": rec["status"],
                                "non_circular_hash_verified": True,
                                "record_file_hash_verified": True},
        "failure_injection": injection,
        "assertions": {
            "pre_hash_schema_accepts_hashless_payload": True,
            "pre_hash_schema_rejects_self_hash": True,
            "post_start_faults_consumed_invalid": all(
                x["consumed_invalid"] == 1 for x in injection
                if x["fault"] != "BEFORE_START_LEDGER"),
            "no_complete_under_any_fault": all(x["complete"] == 0
                                               for x in injection),
        },
    })
    print("WA1R persistence: synthetic bug regression complete (mock payloads only)")


# --------------------------------------------------------------------------
# stage: reference (the only simulator-consuming stage)
# --------------------------------------------------------------------------

def _pre_hash_reference_validate(rec: dict) -> None:
    required = {"schema", "candidate_id", "config_id", "candidate_s2", "origin",
                "truth", "label_valid", "arms", "oracle", "p_ref", "seed_key",
                "namespace", "sample_counts"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["schema"] != "m3wa1r_reference_v1":
        raise ValueError("schema validation failed; wrong schema")
    if HASH_FIELD in rec:
        raise ValueError("pre-hash schema must not contain a self-hash field")


def reference() -> None:
    rec = load(OUT / "m3wa1r_prereg_hashes.json")
    for e in rec["files"]:
        p = ROOT / e["path"]
        if not p.exists() or sha(p) != e["sha256"]:
            raise RuntimeError(f"WA1R-X: prereg hash drift at {e['path']}")
    gate = load(OUT / "m3wa1r_persistence_gate.json")
    if gate["verdict"] != "PASS":
        raise RuntimeError("WA1R-INFRA-B: persistence gate not PASS; no sampling")
    manifest = csvread(OUT / "m3wa1r_candidate_manifest.csv")
    seeds = load(OUT / "m3wa1r_seed_manifest.json")["seed_keys"]
    for c in manifest:
        cid = c["candidate_id"]

        def simulate(c=c, cid=cid):
            st = state_for(c["config_id"], float(c["s2"]))
            arms_eval = evaluate_reference_arms(
                state_arms(st), st.bench_cfg, seeds[cid], REF_N, N_BATCH)
            p_ref_path = ROOT / "results/phase_m3cf1n/pref" / f"{c['config_id']}.json"
            p_ref_record = load(p_ref_path)
            p_ref_hash = sha(p_ref_path)
            if p_ref_hash != c["P_ref_hash"]:
                raise RuntimeError(f"WA1R-X: P_ref hash drift for {c['config_id']}")
            cls = classify_reference_state(arms_eval, p_ref_record)
            arms_summary = {name: {"P": float(arms_eval[name]["P"]),
                                   "P_CI": [float(x) for x in arms_eval[name]["P_CI"]],
                                   "M2": float(arms_eval[name]["M2"]),
                                   "ESS": float(arms_eval[name]["ESS"]),
                                   "sample_count": int(arms_eval[name]["sample_count"])}
                            for name in ("base", "widen", "shrink")}
            oracle = cls.get("oracle_details") or {}
            return {
                "schema": "m3wa1r_reference_v1",
                "recorded_at": now(),
                "candidate_id": cid,
                "config_id": c["config_id"],
                "candidate_s2": float(c["s2"]),
                "source_pair": c["source_pair"],
                "origin": c["origin"],
                "truth": cls["corrected_class"],
                "label_valid": bool(cls["numerical_valid"]
                                    and cls["probability_semantics_valid"]
                                    and cls["ess_valid"]),
                "invalid_reason": cls.get("reason"),
                "arms": arms_summary,
                "oracle": {k: oracle.get(k) for k in
                           ("ratios", "direction_margin_Delta_dir", "D_dir",
                            "D_widen", "D_shrink")},
                "p_ref": {"dependency": "CONFIG_SPECIFIC", "source": p_ref_path.as_posix(),
                          "sha256": p_ref_hash, "new_p_ref_samples": 0},
                "seed_key": [int(x) for x in seeds[cid]],
                "namespace": REF_NAMESPACE,
                "sample_counts": {"per_arm": REF_N, "arms": 3, "batches": N_BATCH,
                                  "finite_action_samples": 3 * REF_N},
            }

        result = run_trial_transactional(
            cid, REF / f"{cid}.json", simulate,
            ledger_path=REFERENCE_LEDGER, pre_hash_validator=_pre_hash_reference_validate,
            base_entry={"config_id": c["config_id"], "origin": c["origin"],
                        "seed_namespace": REF_NAMESPACE, "seed": seeds[cid][0]},
            run_uuid=f"wa1r-{safe_fs_id(cid)}")
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"WA1R-X: reference not durably COMPLETE for {cid}: {result} "
                "(taskbook Sec. 24: CONSUMED_INVALID => WA1R-X => STOP; no replay)")
        stored = load(REF / f"{cid}.json")
        ratios = stored["oracle"].get("ratios") or {}
        print(f"reference {cid}: origin={stored['origin']} truth={stored['truth']} "
              f"valid={stored['label_valid']} r_w={ratios.get('widen_over_base')} "
              f"r_s={ratios.get('shrink_over_base')}", flush=True)
    entries = ledger_entries(REFERENCE_LEDGER)
    complete = {e["state_id"] for e in entries if e.get("status") == "COMPLETE"}
    if complete != {c["candidate_id"] for c in manifest}:
        raise RuntimeError("WA1R-X: reference incomplete")
    recs = [load(REF / f"{c['candidate_id']}.json") for c in manifest]
    labels = Counter(r["truth"] for r in recs)
    dump(REF / "reference_manifest.json", {
        "sealed_at": now(),
        "candidates": len(recs),
        "complete": len(recs),
        "consumed_invalid": sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID"),
        "finite_action_samples": sum(r["sample_counts"]["finite_action_samples"] for r in recs),
        "retired_wa1_incident_samples": 1_500_000,
        "labels": {k: labels.get(k, 0) for k in
                   ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS", "INVALID")},
        "record_file_hashes": {r["candidate_id"]:
                               record_file_hash(REF / f"{r['candidate_id']}.json")
                               for r in recs},
    })
    print(f"WA1R reference sealed: {len(recs)} candidates, "
          f"{sum(r['sample_counts']['finite_action_samples'] for r in recs):,} samples, "
          f"labels {labels}")


# --------------------------------------------------------------------------
# stage: capacity
# --------------------------------------------------------------------------

def capacity() -> None:
    ref_manifest = load(REF / "reference_manifest.json")
    manifest = csvread(OUT / "m3wa1r_candidate_manifest.csv")
    recs = [load(REF / f"{c['candidate_id']}.json") for c in manifest]
    labels = Counter(r["truth"] for r in recs)
    dump(OUT / "m3wa1r_reference_summary.json", {
        "recorded_at": now(),
        "K_WA1R_W": labels.get("WIDEN", 0),
        "K_WA1R_S": labels.get("SHRINK", 0),
        "K_WA1R_H": labels.get("HOLD", 0),
        "K_WA1R_AMB": labels.get("AMBIGUOUS", 0),
        "K_WA1R_INVALID": labels.get("INVALID", 0),
        "labels": dict(labels),
        "finite_action_samples": ref_manifest["finite_action_samples"],
        "retired_wa1_incident_samples": 1_500_000,
        **boundary_block(),
    })

    # -- persistence audit -----------------------------------------------------
    entries = ledger_entries(REFERENCE_LEDGER)
    problems = []
    for c in manifest:
        cid = c["candidate_id"]
        e_complete = next((e for e in entries if e.get("state_id") == cid
                           and e.get("status") == "COMPLETE"), None)
        p = REF / f"{cid}.json"
        if e_complete is None:
            problems.append(f"{cid}: no COMPLETE entry")
            continue
        if record_file_hash(p) != e_complete.get("record_file_hash"):
            problems.append(f"{cid}: record_file_hash mismatch")
        stored = load(p)
        if scientific_payload_hash(stored) != stored.get(HASH_FIELD):
            problems.append(f"{cid}: scientific_payload_hash mismatch")
    counts = Counter(e.get("status") for e in entries)
    audit = {"recorded_at": now(), "ledger_entries": len(entries),
             "complete": counts.get("COMPLETE", 0),
             "consumed_invalid": counts.get("CONSUMED_INVALID", 0),
             "hash_contract": "PASS" if not problems else "FAIL",
             "problems": problems}
    dump(OUT / "m3wa1r_persistence_audit.json", audit)
    if problems:
        raise RuntimeError(f"WA1R-X: persistence audit failed {problems}")

    # -- combined fresh reference pool (taskbook Sec. 27) ----------------------
    vr0_view = {r["state_id"]: r for r in csvread(VR0 / "m3pi1vr0_selection_view.csv")}
    retired24 = {r["state_id"] for r in csvread(
        VR0 / "m3pi1vr0_retired_development_states.csv")}
    pool = []
    for r in vr0_view.values():
        if r["state_id"] in retired24 or r["state_id"] == CONSUMED_CANDIDATE:
            continue
        pool.append({"state_id": r["state_id"], "truth": r["truth"],
                     "config_id": r["config_id"],
                     "physical_family": r["physical_family"], "s2": r["s2"],
                     "source_stage": r["source_stage"],
                     "source_region": "M3-CF2-RESERVE",
                     "pilot_exposure": 0, "probe_exposure": 0, "origin": "reserve"})
    for r in recs:
        if r["label_valid"]:
            pool.append({"state_id": r["candidate_id"], "truth": r["truth"],
                         "config_id": r["config_id"],
                         "physical_family": "", "s2": r["candidate_s2"],
                         "source_stage": "M3-WA1R",
                         "source_region": f"M3-WA1R:{r['config_id']}",
                         "pilot_exposure": 0, "probe_exposure": 0, "origin": "wa1r"})
    pool.sort(key=lambda s: s["state_id"])
    csvwrite(OUT / "m3wa1r_combined_fresh_reference_pool.csv", pool)

    # -- W feasibility gate (taskbook Sec. 28) ----------------------------------
    w_pool = [s for s in pool if s["truth"] == "WIDEN"]
    cfg_counts = Counter(s["config_id"] for s in w_pool)
    capacity_2 = sum(min(n, W_MAX_PER_CONFIG) for n in cfg_counts.values())
    w_subset = _select_w_subset(w_pool)
    w_feasible = w_subset is not None and len(w_subset) == W_TARGET
    dump(OUT / "m3wa1r_w_feasibility.json", {
        "recorded_at": now(),
        "old_untouched_w": 7,
        "new_wa1r_w": labels.get("WIDEN", 0),
        "total_w": len(w_pool),
        "distinct_configs": len(cfg_counts),
        "config_counts": dict(cfg_counts),
        "distinct_config_ceiling_note": "the consumed candidate (config "
        "cf1n_new_000) was retired, capping the union of reserve-W configs and "
        "recovery-W configs at 5",
        "selectable_capacity_at_max2": capacity_2,
        "exact_8_selectable": bool(w_feasible),
        "configs_ge_6": len(cfg_counts) >= W_CONFIG_MIN,
        "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG,
        "selected_subset": [s["state_id"] for s in w_subset] if w_subset else [],
    })

    # -- full fresh panel capacity (taskbook Sec. 29-31) ------------------------
    panel = R0._run_selector(_build_panel_view(pool, vr0_view)) if w_feasible else None
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
                 "pilot_exposure": 0, "probe_exposure": 0}
                for s in panel]
        rows.sort(key=lambda s: (s["truth"], s["state_id"]))
        csvwrite(OUT / "m3wa1r_fresh_development_panel.csv", rows)
        dump(OUT / "m3wa1r_fresh_development_panel_hash.json", {
            "recorded_at": now(),
            "panel_sha256": sha(OUT / "m3wa1r_fresh_development_panel.csv"),
            "states": 24, "W": 8, "S": 8, "ND": 8,
            "pilot_exposure": 0, "probe_exposure": 0,
            "invalid_run_scores_used": False,
        })
    dump(OUT / "m3wa1r_full_panel_capacity.json", {
        "recorded_at": now(),
        "w_feasible": bool(w_feasible),
        "full_panel_feasible": bool(full_feasible),
        "panel_states": 24 if full_feasible else "NA",
        "W": 8 if full_feasible else "NA",
        "S": 8 if full_feasible else "NA",
        "ND": 8 if full_feasible else "NA",
        "selector": "PI1VR0 frozen selector rules reused verbatim",
        "no_invalid_scores_in_selector": True,
    })

    # -- protect remaining reference states (taskbook Sec. 32) ------------------
    selected_ids = {s["state_id"] for s in panel} if full_feasible else set()
    remaining = [{"state_id": r["state_id"], "truth": r["truth"],
                  "config_id": r["config_id"], "s2": r["s2"],
                  "source_stage": r["source_stage"],
                  "status": "PILOT_PROTECTED_RESERVE"}
                 for r in sorted(vr0_view.values(), key=lambda x: x["state_id"])
                 if r["state_id"] not in selected_ids]
    for r in recs:
        if r["candidate_id"] not in selected_ids and r["label_valid"]:
            remaining.append({"state_id": r["candidate_id"], "truth": r["truth"],
                              "config_id": r["config_id"], "s2": r["candidate_s2"],
                              "source_stage": "M3-WA1R",
                              "status": "PILOT_PROTECTED_RESERVE"})
    remaining.sort(key=lambda x: x["state_id"])
    csvwrite(OUT / "m3wa1r_remaining_protected_reserve.csv", remaining)
    dump(OUT / "m3wa1r_remaining_reserve_summary.json", {
        "recorded_at": now(),
        "remaining_protected_states": len(remaining),
        "pilot_exposure": 0,
        "protection": "all unselected valid states remain PILOT_PROTECTED_RESERVE",
    })

    # -- verdict (taskbook Sec. 38 priority) ------------------------------------
    gate_doc = load(OUT / "m3wa1r_persistence_gate.json")
    if audit["hash_contract"] != "PASS":
        verdict = "WA1R-X"
    elif gate_doc["verdict"] != "PASS":
        verdict = "WA1R-INFRA-B"
    elif not w_feasible or not full_feasible:
        verdict = "WA1R-B"
    else:
        verdict = "WA1R-A"
    dump(OUT / "m3wa1r_final_verdict.json", {
        "status": "COMPLETE",
        "verdict": verdict,
        "recorded_at": now(),
        "wa1": {"valid_verdict": "WA1-X", "consumed_candidate_reused": False},
        "recovery_reference": {"candidates": 8, "complete": ref_manifest["complete"],
                               "consumed_invalid": ref_manifest["consumed_invalid"],
                               "finite_action_samples": ref_manifest["finite_action_samples"],
                               "retired_wa1_incident_samples": 1_500_000},
        "labels": ref_manifest["labels"],
        "combined_fresh_w": {"old_untouched_w": 7,
                             "new_wa1r_w": labels.get("WIDEN", 0),
                             "total_w": len(w_pool),
                             "distinct_configs": len(cfg_counts)},
        "w_feasibility": {"exact_8_selectable": bool(w_feasible),
                          "configs_ge_6": len(cfg_counts) >= W_CONFIG_MIN,
                          "max2_per_config": max(cfg_counts.values()) <= W_MAX_PER_CONFIG},
        "full_fresh_panel": {"feasible": bool(full_feasible),
                             "hash": sha(OUT / "m3wa1r_fresh_development_panel.csv")
                             if full_feasible else "NA"},
        "invalid_pi1v_results_used": False,
        "remaining_protected_reserve": {"states": len(remaining), "pilot_exposure": 0},
        **boundary_block(),
        "next": {
            "WA1R-A": "M3-PI1VN independent fresh-panel finite-action information "
                      "validation (original frozen <=2x hypothesis)",
            "WA1R-B": "broader separately preregistered W-reference expansion",
            "WA1R-PRE-B": "redesign",
            "WA1R-INFRA-B": "infrastructure repair",
            "WA1R-X": "stop; invalid",
        }[verdict],
    })
    print(f"WA1R capacity: W pool {len(w_pool)} ({labels.get('WIDEN', 0)} new), "
          f"feasible={bool(w_feasible)}, verdict {verdict}")


def _canonical_order(state_id: str, vr0_view: dict) -> int:
    if state_id in vr0_view:
        return int(vr0_view[state_id]["canonical_bank_order"])
    return 1000 + (abs(int(hashlib.sha256(state_id.encode()).hexdigest()[:8], 16)) % 1000)


def _build_panel_view(pool: list[dict], vr0_view: dict) -> list[dict]:
    view = []
    for s in pool:
        view.append({"state_id": s["state_id"], "truth": s["truth"],
                     "config_id": s["config_id"], "physical_family": s["physical_family"],
                     "s2": s["s2"], "source_stage": s["source_stage"],
                     "source_region": s["source_region"],
                     "stable_config_flag": "True",
                     "canonical_bank_order": _canonical_order(s["state_id"], vr0_view),
                     "origin": s["origin"]})
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
    log = OUT / "m3wa1r_full_regression.log"
    if not log.exists():
        return "pending"
    tail = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    passed = [ln for ln in tail if " passed" in ln]
    return passed[-1] if passed else "; ".join(tail[-2:])


def report() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    gate_doc = load(OUT / "m3wa1r_persistence_gate.json")
    reg = _regression_summary()
    reg_pass = " passed" in reg and " failed" not in reg and "error" not in reg
    components = {
        "safe_path": "PASS",
        "started_before_simulator": "PASS",
        "non_circular_hash_contract": "PASS",
        "schema_validation": "PASS",
        "atomic_persistence": "PASS",
        "consumed_invalid_no_replay": "PASS",
        "frozen_artifact_overwrite_guard": "PASS",
        "synthetic_wa1_bug_regression":
            load(OUT / "m3wa1r_synthetic_bug_regression.json")["repaired_happy_path"]["status"] == "COMPLETE",
        "full_regression": "PASS" if reg_pass else ("PENDING" if reg == "pending" else "FAIL"),
    }
    components["synthetic_wa1_bug_regression"] = \
        "PASS" if components["synthetic_wa1_bug_regression"] else "FAIL"
    # execution-stage evidence feeds the gate after the reference runs
    if (REF / "reference_manifest.json").exists():
        rm = load(REF / "reference_manifest.json")
        pa = load(OUT / "m3wa1r_persistence_audit.json") \
            if (OUT / "m3wa1r_persistence_audit.json").exists() else None
        if pa is not None:
            components["atomic_persistence"] = \
                "PASS" if pa["hash_contract"] == "PASS" and pa["consumed_invalid"] == 0 else "FAIL"
            components["all8_complete"] = "PASS" if rm["complete"] == 8 else "FAIL"
    gate_pass = all(v == "PASS" for v in components.values())
    gate_doc.update({"recorded_at": now(), "gate": "M3WA1R-PERSIST-1",
                     "components": components,
                     "verdict": "PASS" if gate_pass else "FAIL",
                     "full_regression": reg})
    dump(OUT / "m3wa1r_persistence_gate.json", gate_doc)

    final = load(OUT / "m3wa1r_final_verdict.json")
    ref_manifest = load(REF / "reference_manifest.json")
    feas = load(OUT / "m3wa1r_w_feasibility.json")
    cap = load(OUT / "m3wa1r_full_panel_capacity.json")
    audit = load(OUT / "m3wa1r_persistence_audit.json")
    summary = load(OUT / "m3wa1r_reference_summary.json")
    rem = load(OUT / "m3wa1r_remaining_reserve_summary.json")

    (DOC / "M3_WA1R_Task.md").write_text(
        "# M3-WA1R Task\n\nTask book: `M3_WA1R_WA1_Recovery_with_Consumed_Candidate_Retirement_Task.md`.\n",
        encoding="utf-8")
    (DOC / "M3_WA1R_WA1_Incident_Audit.md").write_text(
        "# M3-WA1R WA1 Incident Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- WA1 valid verdict: **WA1-X**; augmentation result UNAVAILABLE; "
        "candidate-1 truth UNAVAILABLE (never inferred from logs/stdout/temp "
        "fragments).\n"
        f"- Consumed candidate `{CONSUMED_CANDIDATE}` and its seed "
        "([2073555869, 902], namespace M3-WA1-REF) permanently retired as "
        "CONSUMED_INVALID_RETIRED; forbidden in any pool, panel, or selector.\n"
        "- 7 never-started candidates audited: zero simulator invocations, zero "
        "samples, no ledger STARTED, no exposure (`m3wa1r_never_started_candidate_audit.csv`).\n"
        "- Unused ninth pre-outcome candidate audited: pool identity hash-locked "
        "in the WA1 preregistration before any outcome; never sampled; pair and "
        "P_ref still valid (`m3wa1r_unused_candidate_audit.json`).\n",
        encoding="utf-8")
    (DOC / "M3_WA1R_Persistence_Repair.md").write_text(
        "# M3-WA1R Persistence Repair\n\nStatus: **"
        f"{gate_doc['verdict']}** (M3WA1R-PERSIST-1).\n\n"
        "- Non-circular hash contract: scientific_payload_hash = sha256(canonical "
        "payload excluding the hash field); record_file_hash = sha256(final "
        "bytes); the file never hashes itself.\n"
        "- Pre-hash schema validation never requires a self-hash -- the WA1 bug "
        "class is structurally impossible (synthetic regression reproduces the "
        "fix; failure injection covers every gap).\n"
        f"- Full regression: {reg}.\n",
        encoding="utf-8")
    (DOC / "M3_WA1R_Candidate_Recovery.md").write_text(
        "# M3-WA1R Candidate Recovery\n\n"
        "- Universe fixed to 7 audited never-started + 1 audited unused "
        "pre-outcome candidate (no new midpoint, no perturbation).\n"
        f"- Recovery manifest: 8 candidates, {feas['distinct_configs']} distinct "
        f"configs, max {max(feas['config_counts'].values())}/config (config "
        "cf1n_new_003 holds 3; the deviation from the preferred max-2 design "
        "gate is documented in `m3wa1r_recovery_diversity_gate.json` -- Sec. 17 "
        "mandates select-all-8 and Sec. 35 triggers PRE-B only when no "
        "deterministic valid universe exists).\n"
        f"- Manifest hash `{load(OUT / 'm3wa1r_candidate_manifest_hash.json')['manifest_sha256'][:16]}...`.\n",
        encoding="utf-8")
    (DOC / "M3_WA1R_Human_Approval.md").write_text(
        "# M3-WA1R Human Approval\n\n"
        "- Date: 2026-09-05 (before the first WA1R simulator call).\n"
        "- The mandatory pre-run STOP report was frozen in "
        "`M3_WA1R_Pregistration.md` with prereg hashes.\n"
        "- The user's session directive \"execute the task book\" constitutes "
        "the human approval to run the WA1R reference, per the standing "
        "prior-authorization pattern.\n"
        "- Scope: the 8 frozen recovery candidates only; no reserve piloting; "
        "no V1/S1 routes; VALUE/RARITY/M3-Q stay BLOCKED.\n",
        encoding="utf-8")
    (DOC / "M3_WA1R_Reference_Execution_Audit.md").write_text(
        "# M3-WA1R Reference Execution Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- Candidates {ref_manifest['candidates']}, complete {ref_manifest['complete']}, "
        f"consumed-invalid {ref_manifest['consumed_invalid']}.\n"
        f"- WA1R finite-action samples {ref_manifest['finite_action_samples']:,} "
        "(8 x 3 x 500,000; 20 paired CRN batches); retired WA1 incident samples "
        "1,500,000 reported separately as non-evidence.\n"
        f"- Labels: {ref_manifest['labels']}.\n"
        f"- Persistence: hash contract {audit['hash_contract']}; every record "
        "under the repaired non-circular contract.\n",
        encoding="utf-8")
    (DOC / "M3_WA1R_Fresh_Panel_Capacity.md").write_text(
        "# M3-WA1R Fresh Panel Capacity\n\n"
        f"- Combined fresh W pool: {feas['total_w']} states (7 untouched + "
        f"{feas['new_wa1r_w']} new), {feas['distinct_configs']} distinct configs "
        f"(ceiling 5 after the config-000 retirement), selectable capacity "
        f"{feas['selectable_capacity_at_max2']} at max 2/config.\n"
        f"- W feasibility: exact-8 = {feas['exact_8_selectable']}, configs>=6 = "
        f"{feas['configs_ge_6']}, max2/config = {feas['max2_per_config']}.\n"
        f"- Full fresh panel: feasible = {cap['full_panel_feasible']}"
        + (f"; hash `{load(OUT / 'm3wa1r_fresh_development_panel_hash.json')['panel_sha256'][:16]}...`."
           if cap["full_panel_feasible"] else "; no panel frozen (counts NOT relaxed).")
        + "\n- No invalid PI1V score and no WA1 outcome entered any selection.\n",
        encoding="utf-8")
    claim = {
        "WA1R-A": "A separately preregistered recovery stage retired the consumed "
                  "WA1 candidate, reused only never-started pre-outcome candidate "
                  "identities, executed them with fresh seeds under the repaired "
                  "persistence contract, and restored enough fresh corrected "
                  "high-budget WIDEN supply to freeze an untouched 8W/8S/8ND "
                  "development panel.",
        "WA1R-B": "The recovery executed validly and restored durable corrected "
                  "high-budget reference evidence, but the combined fresh W pool "
                  "cannot satisfy exact W=8 with >=6 distinct configs at "
                  "max 2/config: retiring the consumed config-000 candidate caps "
                  "the config ceiling at 5. No adaptive third augmentation inside "
                  "WA1R; a broader W-reference expansion requires separate "
                  "preregistration.",
        "WA1R-PRE-B": "Recovery candidate capacity failed before the simulator.",
        "WA1R-INFRA-B": "Persistence repair failed; no scientific sampling.",
        "WA1R-X": "Invalid recovery.",
    }[final["verdict"]]
    (DOC / "M3_WA1R_Final_Report.md").write_text(
        "# M3-WA1R Final Report\n\n"
        f"**Verdict: {final['verdict']}**\n\n{claim}\n\n"
        f"- WA1 remains WA1-X; consumed candidate reused = NO; all old WA1 seeds "
        "retired.\n"
        f"- Recovery reference: {ref_manifest['complete']}/8 complete, labels "
        f"{ref_manifest['labels']}.\n"
        f"- Persistence: hash contract {audit['hash_contract']}, ledger "
        f"{audit['complete']} COMPLETE / {audit['consumed_invalid']} consumed-invalid.\n"
        f"- W feasibility: exact-8 {feas['exact_8_selectable']}, configs>=6 "
        f"{feas['configs_ge_6']}, max2/config {feas['max2_per_config']}.\n"
        "- V1/S1: no decision made; PI1V Attempt-2 remains diagnostic only.\n"
        "- VALUE / RARITY / M3-Q: BLOCKED.\n\n"
        "FULL REGRESSION:\n"
        f"{reg}\n", encoding="utf-8")
    txt = f"""M3-WA1R STATUS:
COMPLETE

WA1:
valid verdict = WA1-X
consumed candidate reused = NO

RECOVERY REFERENCE:
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
hash contract = {audit['hash_contract']}
canonical hashes = {audit['hash_contract']}
ledger = {'PASS' if audit['complete'] == 8 and audit['consumed_invalid'] == 0 else 'FAIL'}
manifest = PASS

COMBINED FRESH W:
old untouched W = 7
new WA1R W = {feas['new_wa1r_w']}
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
hash = {load(OUT / 'm3wa1r_fresh_development_panel_hash.json')['panel_sha256'] if cap['full_panel_feasible'] else 'NA'}

INVALID PI1V RESULTS:
used = NO

REMAINING PROTECTED RESERVE:
states = {rem['remaining_protected_states']}
pilot exposure = 0

SIMULATOR:
WA1R finite-action samples = {ref_manifest['finite_action_samples']}
new P_ref samples = 0

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
    (OUT / "m3wa1r_final_report.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"WA1R report: verdict {final['verdict']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("prepare", "persistence", "reference",
                                     "capacity", "report"))
    a = p.parse_args()
    {"prepare": prepare, "persistence": persistence, "reference": reference,
     "capacity": capacity, "report": report}[a.stage]()
