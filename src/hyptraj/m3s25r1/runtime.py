"""M3-S25-R1 gated truth-execution machinery (taskbook Sec. 12-22).

Implements the complete truth-stage semantics BEFORE human authorization;
nothing here runs without M3_S25_R1_TRUTH_AUTHORIZED: YES.  All estimator /
label semantics are byte-identical to the parent stage M3-S2S (the CF1N
corrected three-phase protocol, event semantics v2); config resolution
reads ONLY the parent's vendored snapshots + tracked parent universe /
registry via hyptraj.m3s2s.vendored_runtime.

Scope (frozen): confirmation_scope = ALL_240_R1_CANDIDATES;
early_stop_on_quota = false; planned = max = 432,000,000; P_ref sampling
budget = 0; no top-up; no candidate substitution.

Seed namespaces are NEW and independent (taskbook Sec. 13):
M3-S25-R1-DISCOVERY / M3-S25-R1-CONFIRMATION.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d2.experiment import (
    classify_reference_state,
    evaluate_reference_arms,
)
from hyptraj.m3cf1.workflow import provisional_label
from hyptraj.m3s2s import vendored_runtime as VR

ARM_ORDER = ("base", "widen", "shrink")
PANEL_QUOTA = {"WIDEN": 30, "SHRINK": 30, "HOLD": 30, "AMBIGUOUS": 30}
PANEL_STATES = 120
MIN_CONFIGS = 24
PANEL_RANK_SEED = "M3-S25-R1-PANEL-V1|"

DISCOVERY_NAMESPACE = "M3-S25-R1-DISCOVERY"
CONFIRMATION_NAMESPACE = "M3-S25-R1-CONFIRMATION"

DISCOVERY_SAMPLES_PER_ARM = 100_000
CONFIRMATION_SAMPLES_PER_ARM = 500_000
DISCOVERY_BUDGET_PER_STATE = 3 * DISCOVERY_SAMPLES_PER_ARM      # 300,000
CONFIRMATION_BUDGET_PER_STATE = 3 * CONFIRMATION_SAMPLES_PER_ARM  # 1,500,000
N_STATES = 240
N_UNITS = 480
P_REF_BUDGET = 0
TRUTH_BUDGET_PLANNED = (N_STATES * DISCOVERY_BUDGET_PER_STATE
                        + N_STATES * CONFIRMATION_BUDGET_PER_STATE)  # 432,000,000
TRUTH_BUDGET_MAX = TRUTH_BUDGET_PLANNED


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (
        2**31 - 1) + 1


# --------------------------------------------------------------------------
# execution plan (pure; no simulator)
# --------------------------------------------------------------------------

def truth_execution_plan(states: list[dict]) -> dict:
    """Exact unit lists + sample accounting for the two truth streams."""
    state_ids = sorted(s["state_id"] for s in states)
    if len(state_ids) != N_STATES or len(set(state_ids)) != N_STATES:
        raise RuntimeError("M3-S25-R1-X: universe shape drift")
    plan = {
        "pref_units": [],
        "discovery_units": [{"unit_id": f"DISC|{sid}", "state_id": sid,
                             "samples": DISCOVERY_BUDGET_PER_STATE,
                             "namespace": DISCOVERY_NAMESPACE,
                             "seed_key": [seed(DISCOVERY_NAMESPACE, sid),
                                          42424]}
                            for sid in state_ids],
        "confirmation_units": [{"unit_id": f"CONF|{sid}", "state_id": sid,
                                "samples": CONFIRMATION_BUDGET_PER_STATE,
                                "namespace": CONFIRMATION_NAMESPACE,
                                "seed_key": [seed(CONFIRMATION_NAMESPACE,
                                                  sid), 42424]}
                               for sid in state_ids],
        "namespaces": {"discovery": DISCOVERY_NAMESPACE,
                       "confirmation": CONFIRMATION_NAMESPACE},
        "confirmation_scope": "ALL_240_R1_CANDIDATES",
        "early_stop_on_quota": False,
        "p_ref_sampling_budget": P_REF_BUDGET,
    }
    plan["discovery_samples"] = (len(plan["discovery_units"])
                                 * DISCOVERY_BUDGET_PER_STATE)
    plan["confirmation_samples"] = (len(plan["confirmation_units"])
                                    * CONFIRMATION_BUDGET_PER_STATE)
    plan["total_samples"] = (plan["discovery_samples"]
                             + plan["confirmation_samples"]
                             + plan["p_ref_sampling_budget"])
    if plan["total_samples"] != TRUTH_BUDGET_PLANNED \
            or plan["total_samples"] != TRUTH_BUDGET_MAX:
        raise RuntimeError("M3-S25-R1-X: truth budget accounting drift")
    return plan


# --------------------------------------------------------------------------
# payload builders (verbatim parent estimator semantics)
# --------------------------------------------------------------------------

def _state(cid: str, s2: float):
    bench = VR.resolve_bench_config(cid)
    st = assemble_state(bench, float(s2), short_config=cid)
    if isinstance(st, dict):
        raise RuntimeError(f"M3-S25-R1-X: state assembly failed for {cid}: {st}")
    return st


def _arms_payload(state, bench_cfg, seed_key: list[int], n: int, n_batches: int,
                  p_ref: dict, protocol_hash: str, record_type: str,
                  state_id: str, config_id: str, s2: float) -> dict:
    arms = evaluate_reference_arms(state_arms(state), bench_cfg, seed_key,
                                   n, n_batches)
    classification = classify_reference_state(arms, p_ref)
    corrected = classification["corrected_class"]
    rel = lambda new, base: float((new - base) / base) if base else 0.0
    return {
        "record_type": record_type,
        "state_id": state_id, "config_id": config_id, "s2": float(s2),
        "seed_key": [int(x) for x in seed_key],
        "p_ref_hash": p_ref.get("record_hash"),
        "arm_summaries": {
            name: {"P": float(arms[name]["P"]),
                   "P_CI": [float(x) for x in arms[name]["P_CI"]],
                   "ESS": float(arms[name]["ESS"]),
                   "sample_count": int(arms[name]["sample_count"])}
            for name in ARM_ORDER},
        "paired_statistics": {
            "shrink_vs_base_relative":
                rel(float(arms["shrink"]["P"]), float(arms["base"]["P"])),
            "widen_vs_base_relative":
                rel(float(arms["widen"]["P"]), float(arms["base"]["P"]))},
        "minimum_arm_ESS": float(classification["minimum_arm_ESS"]),
        "provisional_label": provisional_label(corrected),
        "corrected_class": corrected,
        "protocol_hash": protocol_hash,
        "valid": bool(classification["numerical_valid"]
                      and classification["probability_semantics_valid"]
                      and classification["ess_valid"]),
    }


def discovery_payload(unit: dict, state_row: dict, p_ref: dict,
                      protocol_hash: str) -> dict:
    st = _state(state_row["config_id"], state_row["s2"])
    return _arms_payload(st, st.bench_cfg, unit["seed_key"],
                         DISCOVERY_SAMPLES_PER_ARM, 20, p_ref, protocol_hash,
                         "M3S25R1-DISCOVERY", unit["state_id"],
                         state_row["config_id"], state_row["s2"])


def confirmation_payload(unit: dict, state_row: dict, p_ref: dict,
                         protocol_hash: str) -> dict:
    st = _state(state_row["config_id"], state_row["s2"])
    return _arms_payload(st, st.bench_cfg, unit["seed_key"],
                         CONFIRMATION_SAMPLES_PER_ARM, 20, p_ref,
                         protocol_hash, "M3S25R1-CONFIRM", unit["state_id"],
                         state_row["config_id"], state_row["s2"])


# --------------------------------------------------------------------------
# restart integrity (taskbook Sec. 19): any-ledger-state fail-closed scan
# --------------------------------------------------------------------------

def verify_unit_fresh_or_verified(unit_id: str, out_path: Path,
                                  ledger_entries: list[dict],
                                  record_file_hash_fn) -> dict | None:
    """Returns the hash-verified record for a durable COMPLETE unit, or
    None for a truly FRESH unit (no artifact AND no ledger entry).  ANY
    other state -- STARTED-only, CONSUMED_INVALID, duplicate STARTED /
    COMPLETE, COMPLETE-without-STARTED, orphan artifact, hash mismatch --
    raises M3-S25-R1-X (STOP, NO REPLAY)."""
    entries = [e for e in ledger_entries if e.get("state_id") == unit_id]
    if not entries and not out_path.exists():
        return None                       # truly fresh
    if not entries and out_path.exists():
        raise RuntimeError(
            f"M3-S25-R1-X: orphan artifact without any ledger entry: "
            f"{unit_id} ({out_path}); STOP; NO REPLAY")
    invalid = [e for e in entries if e.get("status") == "CONSUMED_INVALID"]
    started = [e for e in entries if e.get("status") == "STARTED"]
    completes = [e for e in entries if e.get("status") == "COMPLETE"]
    if invalid:
        raise RuntimeError(
            f"M3-S25-R1-X: unit has CONSUMED_INVALID ledger state: {unit_id}; "
            "STOP; NO REPLAY")
    if started and not completes:
        raise RuntimeError(
            f"M3-S25-R1-X: unit STARTED-only (interrupted, no durable "
            f"COMPLETE): {unit_id}; STOP; NO REPLAY")
    if completes and not started:
        raise RuntimeError(
            f"M3-S25-R1-X: unit COMPLETE without STARTED (inconsistent "
            f"ledger): {unit_id}; STOP; NO REPLAY")
    if len(started) != 1 or len(completes) != 1:
        raise RuntimeError(
            f"M3-S25-R1-X: duplicate/inconsistent ledger state: {unit_id} "
            f"(STARTED={len(started)}, COMPLETE={len(completes)}); "
            "STOP; NO REPLAY")
    if not out_path.exists():
        raise RuntimeError(
            f"M3-S25-R1-X: unit marked COMPLETE but artifact missing: "
            f"{unit_id}; STOP")
    recorded = completes[0].get("record_file_hash")
    if not recorded:
        raise RuntimeError(
            f"M3-S25-R1-X: COMPLETE entry missing record_file_hash: "
            f"{unit_id}; STOP")
    if record_file_hash_fn(out_path) != recorded:
        raise RuntimeError(
            f"M3-S25-R1-X: record hash mismatch on restart: {unit_id}; "
            "STOP; NO REPLAY")
    return json.loads(out_path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# P_ref registry loading (taskbook Sec. 11): reuse only, hash-verified
# --------------------------------------------------------------------------

def p_ref_from_registry(cid: str, registry: dict, source_resolver,
                        record_file_hash_fn) -> dict:
    """Resolve a config's frozen P_ref through the R1 registry: the source
    file must exist, its record_file_hash MUST equal the registry pin
    BEFORE parsing, and exactly one durable source may exist."""
    configs = registry.get("configs", {})
    if isinstance(configs, dict):
        entry = configs.get(cid)
    else:
        matches = [e for e in configs if e.get("config_id") == cid]
        if len(matches) > 1:
            raise RuntimeError(
                f"M3-S25-R1-X: ambiguous P_ref registry entries for {cid}; "
                "STOP; NO P_ref RESAMPLING")
        entry = matches[0] if matches else None
    if entry is None:
        raise RuntimeError(
            f"M3-S25-R1-X: config {cid} missing from the frozen P_ref "
            "registry; STOP; NO P_ref RESAMPLING")
    path, record = source_resolver(entry)
    got = record_file_hash_fn(path)
    if got != entry["record_file_hash"]:
        raise RuntimeError(
            f"M3-S25-R1-X: P_ref source hash mismatch for {cid}: {got} != "
            f"{entry['record_file_hash']}; STOP; NO P_ref RESAMPLING")
    out = {"p_ref_full": float(record["p_ref_full"]),
           "p_ref_full_SE": float(record["p_ref_full_SE"]),
           "p_ref_full_CI": [float(x) for x in record["p_ref_full_CI"]],
           "record_hash": got,
           "source_stage": entry["source_stage"],
           "sample_count": int(entry["sample_count"]),
           "n_batches": int(entry["n_batches"])}
    return out


# --------------------------------------------------------------------------
# completion semantics: labels, inventory, union pool, panel selection
# --------------------------------------------------------------------------

def consumption_summary(ledgers: dict[str, list[dict]]) -> dict:
    """Exact planned/actual/difference per stream (taskbook Sec. 22)."""
    out = {}
    for stream, planned in (
            ("discovery", N_STATES * DISCOVERY_BUDGET_PER_STATE),
            ("confirmation", N_STATES * CONFIRMATION_BUDGET_PER_STATE)):
        actual = sum(int(e.get("samples", 0)) for e in ledgers.get(stream, [])
                     if e.get("status") == "COMPLETE")
        out[stream] = {"planned": planned, "actual": actual,
                       "difference": actual - planned, "topup": 0}
    out["p_ref"] = {"planned": 0, "actual": 0, "difference": 0, "topup": 0}
    out["total"] = {"planned": TRUTH_BUDGET_PLANNED,
                    "actual": sum(v["actual"] for k, v in out.items()
                                  if k != "total"),
                    "topup": 0}
    return out


def assign_truth(confirmation_records: list[dict]) -> dict[str, str]:
    """Frozen truth = durable confirmation corrected_class per state
    (assigned ONLY after every confirmation record is durable COMPLETE)."""
    truth = {}
    for rec in confirmation_records:
        if not rec.get("valid"):
            raise RuntimeError(
                f"M3-S25-R1-X: invalid confirmation record for "
                f"{rec['state_id']}")
        truth[rec["state_id"]] = rec["corrected_class"]
    return truth


def select_panel(union_states: list[dict], truth: dict[str, str]) -> dict:
    """Round-based config-diversity selection over the union development
    pool D_union = D_old (M3-S2S) u D_new (M3-S25-R1) under the frozen
    30/30/30/30 quota; M3-S25-R1-PANEL-BLOCKED if quotas or the >= 24-
    config floor cannot be met.  No quota relaxation, no panel shrinkage,
    no class merging, duplicate protection by exact state identity."""
    seen: set[str] = set()
    deduped = []
    for s in union_states:
        if s["state_id"] in seen:
            continue
        seen.add(s["state_id"])
        deduped.append(s)

    def pick(pool: list[dict], k: int) -> list[dict]:
        ranked = sorted(pool, key=lambda s: (s["rank"], s["state_id"]))
        by_cfg: dict[str, list] = {}
        for s in ranked:
            by_cfg.setdefault(s["config_id"], []).append(s)
        chosen, round_idx = [], 0
        while len(chosen) < k:
            cands = [m[round_idx] for m in by_cfg.values()
                     if round_idx < len(m)]
            if not cands:
                break
            cands.sort(key=lambda s: (s["rank"], s["state_id"]))
            for s in cands:
                if len(chosen) >= k:
                    break
                chosen.append(s)
            round_idx += 1
        return chosen

    strata = {"WIDEN": [], "SHRINK": [], "HOLD": [], "AMBIGUOUS": []}
    for s in deduped:
        strata[truth[s["state_id"]]].append(s)
    short = {g: len(v) for g, v in strata.items() if len(v) < PANEL_QUOTA[g]}
    if short:
        return {"PANEL": "M3-S25-R1-PANEL-BLOCKED", "short": short,
                "reason": "union-pool truth strata cannot fill the frozen "
                          "30/30/30/30 quota; no relaxation, no panel "
                          "shrinkage"}
    panel = (pick(strata["WIDEN"], 30) + pick(strata["SHRINK"], 30)
             + pick(strata["HOLD"], 30) + pick(strata["AMBIGUOUS"], 30))
    n_configs = len({s["config_id"] for s in panel})
    if len(panel) != PANEL_STATES or n_configs < MIN_CONFIGS:
        return {"PANEL": "M3-S25-R1-PANEL-BLOCKED",
                "reason": f"panel {len(panel)} states / {n_configs} configs "
                          f"violates the frozen 120/{MIN_CONFIGS} design"}
    if len({s["state_id"] for s in panel}) != PANEL_STATES:
        return {"PANEL": "M3-S25-R1-PANEL-BLOCKED",
                "reason": "duplicate state in panel"}
    panel_sorted = sorted(panel, key=lambda s: (s["rank"], s["state_id"]))
    body = json.dumps({"states": panel_sorted, "quota": PANEL_QUOTA,
                       "rank_seed": PANEL_RANK_SEED},
                      sort_keys=True, ensure_ascii=True).encode("utf-8")
    return {"PANEL": "FROZEN", "panel": panel_sorted, "n_configs": n_configs,
            "panel_sha256": hashlib.sha256(body).hexdigest()}


def union_development_pool(old_states: list[dict], new_states: list[dict]) -> list[dict]:
    """D_union = D_old (parent registry) u D_new (R1 universe); duplicates
    by state_id are a hard error (the freshness firewall makes collision
    impossible; any duplicate means firewall failure)."""
    out = []
    seen = set()
    for s in list(old_states) + list(new_states):
        if s["state_id"] in seen:
            raise RuntimeError(
                f"M3-S25-R1-X: duplicate state in development union: "
                f"{s['state_id']}")
        seen.add(s["state_id"])
        out.append(s)
    if len(out) > 2 * N_STATES:
        raise RuntimeError("M3-S25-R1-X: development union exceeds 480")
    return out


def truth_composition(truth: dict[str, str]) -> dict:
    return dict(Counter(truth.values()))
