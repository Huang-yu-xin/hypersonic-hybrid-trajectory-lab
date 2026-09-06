"""M3-S2S gated truth-execution module (execution-readiness amendment).

Implements the complete truth stage semantics BEFORE human authorization;
nothing here runs without TRUTH_SAMPLING_AUTHORIZED: YES.  All estimator /
label semantics are reused verbatim from the committed m3d2 experiment
machinery (direct_full_event_reference, evaluate_reference_arms,
classify_reference_state); all config resolution reads ONLY vendored
snapshots + the tracked universe/registry (vendored_runtime).

Scope (frozen): confirmation_scope = ALL_240_FRESH_CANDIDATES;
early_stop_on_quota = false; planned = max = 436,000,000; no top-up; no
candidate substitution; no early stopping at 30/30/30/30.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d2.experiment import (
    classify_reference_state,
    direct_full_event_reference,
    evaluate_reference_arms,
)
from hyptraj.m3cf1.workflow import provisional_label
from hyptraj.m3s2s import vendored_runtime as VR

ARM_ORDER = ("base", "widen", "shrink")
DEPLOYABLE = ("WIDEN", "SHRINK")
NON_DEPLOYABLE = ("HOLD", "AMBIGUOUS")
PANEL_QUOTA = {"WIDEN": 30, "SHRINK": 30, "HOLD": 30, "AMBIGUOUS": 30}
PANEL_STATES = 120
MIN_CONFIGS = 24
PANEL_RANK_SEED = "M3-S2S-PANEL-V1|"

TRUTH_BUDGET_PLANNED = 436_000_000
TRUTH_BUDGET_MAX = 436_000_000

PREF_SAMPLES_PER_CONFIG = 500_000
DISCOVERY_SAMPLES_PER_ARM = 100_000
CONFIRMATION_SAMPLES_PER_ARM = 500_000
N_NEW_CONFIGS = 8
N_STATES = 240


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (
        2**31 - 1) + 1


# --------------------------------------------------------------------------
# execution plan (pure; no simulator)
# --------------------------------------------------------------------------

def truth_execution_plan(universe_states: list[dict]) -> dict:
    """Exact unit lists and sample accounting for the three truth streams."""
    configs = sorted({s["config_id"] for s in universe_states})
    new_configs = sorted({s["config_id"] for s in universe_states
                          if s["config_origin"] == "M3-S2S-NEW-CONFIG"})
    if len(new_configs) != N_NEW_CONFIGS:
        raise RuntimeError(
            f"S2S-X: expected {N_NEW_CONFIGS} new configs, got {len(new_configs)}")
    if len(universe_states) != N_STATES or len(configs) < MIN_CONFIGS:
        raise RuntimeError("S2S-X: universe shape drift")
    state_ids = sorted(s["state_id"] for s in universe_states)
    plan = {
        "pref_units": [{"unit_id": f"PREF|{cid}", "config_id": cid,
                        "samples": PREF_SAMPLES_PER_CONFIG,
                        "seed_key": [seed("M3-S2S-TRUTH-PREF", cid), 42424]}
                       for cid in new_configs],
        "discovery_units": [{"unit_id": f"DISC|{sid}", "state_id": sid,
                             "samples": 3 * DISCOVERY_SAMPLES_PER_ARM,
                             "seed_key": [seed("M3-S2S-TRUTH-DISCOVERY", sid),
                                          42424]}
                            for sid in state_ids],
        "confirmation_units": [{"unit_id": f"CONF|{sid}", "state_id": sid,
                                "samples": 3 * CONFIRMATION_SAMPLES_PER_ARM,
                                "seed_key": [seed("M3-S2S-TRUTH-CONFIRM", sid),
                                             42424]}
                               for sid in state_ids],
        "confirmation_scope": "ALL_240_FRESH_CANDIDATES",
        "early_stop_on_quota": False,
    }
    plan["pref_samples"] = len(plan["pref_units"]) * PREF_SAMPLES_PER_CONFIG
    plan["discovery_samples"] = (len(plan["discovery_units"])
                                 * 3 * DISCOVERY_SAMPLES_PER_ARM)
    plan["confirmation_samples"] = (len(plan["confirmation_units"])
                                    * 3 * CONFIRMATION_SAMPLES_PER_ARM)
    plan["total_samples"] = (plan["pref_samples"] + plan["discovery_samples"]
                             + plan["confirmation_samples"])
    if plan["total_samples"] != TRUTH_BUDGET_PLANNED or \
            plan["total_samples"] != TRUTH_BUDGET_MAX:
        raise RuntimeError("S2S-X: truth budget accounting drift")
    return plan


# --------------------------------------------------------------------------
# payload builders (verbatim CF1N estimator semantics)
# --------------------------------------------------------------------------

def _state(cid: str, s2: float):
    bench = VR.resolve_bench_config(cid)
    st = assemble_state(bench, float(s2), short_config=cid)
    if isinstance(st, dict):
        raise RuntimeError(f"S2S-X: state assembly failed for {cid}: {st}")
    return st


def pref_payload(unit: dict, protocol_hash: str) -> dict:
    cfg_id = unit["config_id"]
    bench = VR.resolve_bench_config(cfg_id)
    ref = direct_full_event_reference(bench, unit["seed_key"],
                                      PREF_SAMPLES_PER_CONFIG, 20)
    return {
        "record_type": "M3S2S-PREF",
        "config_id": cfg_id,
        "namespace": VR.load_vendored_protocol_constants()["namespaces"]["pref"],
        "seed_key": [int(x) for x in unit["seed_key"]],
        "sample_count": int(ref["sample_count"]),
        "n_batches": int(ref["n_batches"]),
        "p_ref_full": float(ref["p_ref_full"]),
        "p_ref_full_SE": float(ref["p_ref_full_SE"]),
        "p_ref_full_CI": [float(x) for x in ref["p_ref_full_CI"]],
        "p_batches": [float(x) for x in ref["p_batches"]],
        "topology_counts": {k: int(v) for k, v in ref["topology_counts"].items()},
        "event_semantics_schema_version": 2,
        "event_schema": "corrected full-event v2",
        "protocol_hash": protocol_hash,
    }


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
                         "M3S2S-DISCOVERY", unit["state_id"],
                         state_row["config_id"], state_row["s2"])


def confirmation_payload(unit: dict, state_row: dict, p_ref: dict,
                         protocol_hash: str) -> dict:
    st = _state(state_row["config_id"], state_row["s2"])
    return _arms_payload(st, st.bench_cfg, unit["seed_key"],
                         CONFIRMATION_SAMPLES_PER_ARM, 20, p_ref, protocol_hash,
                         "M3S2S-CONFIRM", unit["state_id"],
                         state_row["config_id"], state_row["s2"])


# --------------------------------------------------------------------------
# completion semantics: labels, retirement inventory, panel selection
# --------------------------------------------------------------------------

def consumption_summary(ledgers: dict[str, list[dict]]) -> dict:
    """Exact planned/actual/difference per stream (taskbook Sec. 34)."""
    out = {}
    for stream, planned in (("pref", N_NEW_CONFIGS * PREF_SAMPLES_PER_CONFIG),
                            ("discovery", N_STATES * 3 * DISCOVERY_SAMPLES_PER_ARM),
                            ("confirmation",
                             N_STATES * 3 * CONFIRMATION_SAMPLES_PER_ARM)):
        actual = sum(int(e.get("samples", 0)) for e in ledgers.get(stream, [])
                     if e.get("status") == "COMPLETE")
        out[stream] = {"planned": planned, "actual": actual,
                       "difference": actual - planned, "topup": 0}
    out["total"] = {"planned": TRUTH_BUDGET_PLANNED,
                    "actual": sum(v["actual"] for k, v in out.items()
                                  if k != "total"),
                    "topup": 0}
    return out


def assign_truth(confirmation_records: list[dict]) -> dict[str, str]:
    """Frozen truth = the durable confirmation corrected_class per state
    (assigned ONLY after every confirmation record is durable COMPLETE)."""
    truth = {}
    for rec in confirmation_records:
        if not rec.get("valid"):
            raise RuntimeError(
                f"S2S-X: invalid confirmation record for {rec['state_id']}")
        truth[rec["state_id"]] = rec["corrected_class"]
    return truth


def select_panel(states: list[dict], truth: dict[str, str]) -> dict:
    """Round-based config-diversity selection under the frozen 30/30/30/30
    quota; M3-S2S-PANEL-BLOCKED if quotas or the >=24-config floor cannot
    be met.  No quota relaxation, no panel shrinkage."""
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
    for s in states:
        strata[truth[s["state_id"]]].append(s)
    short = {g: len(v) for g, v in strata.items() if len(v) < PANEL_QUOTA[g]}
    if short:
        return {"PANEL": "M3-S2S-PANEL-BLOCKED", "short": short,
                "reason": "truth strata cannot fill the frozen 30/30/30/30 "
                          "quota; no relaxation, no panel shrinkage"}
    panel = (pick(strata["WIDEN"], 30) + pick(strata["SHRINK"], 30)
             + pick(strata["HOLD"], 30) + pick(strata["AMBIGUOUS"], 30))
    n_configs = len({s["config_id"] for s in panel})
    if len(panel) != PANEL_STATES or n_configs < MIN_CONFIGS:
        return {"PANEL": "M3-S2S-PANEL-BLOCKED",
                "reason": f"panel {len(panel)} states / {n_configs} configs "
                          f"violates the frozen 120/{MIN_CONFIGS} design"}
    panel_sorted = sorted(panel, key=lambda s: (s["rank"], s["state_id"]))
    body = json.dumps({"states": panel_sorted, "quota": PANEL_QUOTA,
                       "rank_seed": PANEL_RANK_SEED},
                      sort_keys=True, ensure_ascii=True).encode("utf-8")
    return {"PANEL": "FROZEN", "panel": panel_sorted,
            "n_configs": n_configs,
            "panel_sha256": hashlib.sha256(body).hexdigest()}
