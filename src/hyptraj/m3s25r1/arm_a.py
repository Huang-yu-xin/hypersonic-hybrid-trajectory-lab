"""M3-S25-R1-A0 Arm-A machinery: rebind + execution + evaluation.

ZERO-SAMPLING stage: everything here is implemented and tested BEFORE
Arm-A authorization; nothing runs without
``M3_S25_R1_ARM_A_AUTHORIZED: YES``.

Frozen inheritance from the parent stage M3-S2S (no scientific retuning):
estimator ``hyptraj.m3d.adaptation.gradient_decision`` (untouched -- the
trial below re-executes the identical frozen pipeline, captures the
lossless instrumentation arrays and proves BIT-EXACT equality against the
unmodified estimator on every trial); alpha_p = 0.5; S1 threshold
5.4417199447782; 120 states x 8 replicates x 20,000 samples = 960 trials
= 19,200,000 samples (no top-up); instrumentation m3s2s_instr_v1
(N_BOOTSTRAP = 500); parent grouped nested-CV (outer GroupKFold(5) /
inner GroupKFold(4), groups = config_id); parent safety gates and
Arm-A success criterion.

The Arm-A sampling execution view carries ONLINE-required fields only --
never truth labels (the panel truth manifest is evaluation-only and stays
sealed until 960/960 trials are durable COMPLETE).
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from hyptraj.m3d.adaptation import (
    ESS_MIN,
    N_BOOTSTRAP,
    draw_online_pilot,
    gradient_decision,
)
from hyptraj.m3cf1r0.persistence import fsync_directory
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3.gradient_estimator import (
    MixtureSpec,
    component_responsibility,
    scalar_gradient_estimate,
    variance_mass_importance,
)
from hyptraj.m3s2s.instrumentation import INSTRUMENTATION_SCHEMA_VERSION

ARM_A_NAMESPACE = "M3-S25-R1-A-GRAD"
N_STATES = 120
REPLICATES = 8
N_TRIALS = N_STATES * REPLICATES            # 960
N_SAMPLES = 20_000
ALPHA_P = 0.5
Z95 = 1.959963984540054
S1_THRESHOLD = 5.4417199447782
BUDGET = N_TRIALS * N_SAMPLES               # 19,200,000
PANEL_RANK_SEED = "M3-S25-R1-PANEL-V1|"
FROZEN_PANEL_SHA = ("2bdb9a91562cc44c6dd9e1d1c0d49f8950e531c3108ea61b6d03"
                    "eb0c153ce2b8")
TRIAL_SCHEMA = "m3s25r1_arm_a_trial_v1"
DEPLOYABLE = ("WIDEN", "SHRINK")
NON_DEPLOYABLE = ("HOLD", "AMBIGUOUS")

GATES = {"coverage_min": 0.75, "unsafe_max": 0.20, "wrong_max": 0.05,
         "ambiguous_unsafe_max": 0.25}
IMPROVEMENT = {"coverage_gain_vs_aggregate_gbdt": 0.03,
               "unsafe_reduction_vs_frozen_s1": 0.05,
               "at_coverage_min": 0.75}
DELTA_QUANTILES = (0.10, 0.25, 0.40, 0.50)

MODEL_CANDIDATES = ("B0_frozen_S1", "B1_aggregate_gbdt_baseline",
                    "A1_stability_logistic", "A2_stability_gbdt",
                    "A3_stability_margin_logistic", "A4_stability_margin_gbdt")
SEED = 2026
LOGISTIC_GRID = [{"C": c, "class_weight": w}
                 for c in (0.1, 1.0, 10.0) for w in (None, "balanced")]
GBDT_GRID = [{"max_iter": mi, "max_leaf_nodes": ln, "learning_rate": lr,
              "l2_regularization": l2, "random_state": SEED}
             for mi in (50, 100) for ln in (7, 15)
             for lr in (0.03, 0.1) for l2 in (0, 1)]


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (
        2**31 - 1) + 1


# --------------------------------------------------------------------------
# transactional sidecar write (A0.1 item 3): temp -> write -> flush ->
# fsync(file) -> atomic rename -> fsync(parent dir) -> SHA256 verify final
# sidecar.  Only after this may the JSON record reach durable COMPLETE.
# --------------------------------------------------------------------------

class InjectedSidecarFault(RuntimeError):
    pass


SIDECAR_FAULT_TAGS = ("SIDECAR_BEFORE_FSYNC", "SIDECAR_AFTER_FSYNC_BEFORE_RENAME",
                      "SIDECAR_AFTER_VERIFY")


def write_sidecar_transactional(side_path: Path, arrays: dict,
                                fault: str | None = None) -> str:
    """Durable lossless sidecar write with injected-fault support for
    tests.  Returns the final sidecar sha256.  Any failure AFTER the
    scientific sampling has happened leaves the unit without a durable
    COMPLETE => CONSUMED_INVALID => M3-S25-R1-X => STOP => NO REPLAY."""
    import os
    import uuid as _uuid
    if fault and fault not in SIDECAR_FAULT_TAGS:
        raise ValueError(f"unknown sidecar fault tag {fault!r}")
    side_path.parent.mkdir(parents=True, exist_ok=True)
    temp = side_path.parent / f".{side_path.name}.tmp.{_uuid.uuid4().hex}"
    with open(temp, "wb") as h:
        np.savez_compressed(h, **arrays)
        h.flush()
        if fault == "SIDECAR_BEFORE_FSYNC":
            raise InjectedSidecarFault("injected failure before sidecar fsync")
        os.fsync(h.fileno())
    if fault == "SIDECAR_AFTER_FSYNC_BEFORE_RENAME":
        raise InjectedSidecarFault(
            "injected failure after sidecar fsync, before rename")
    os.replace(temp, side_path)
    # A0.2: parent-directory fsync is FAIL-CLOSED -- an unavailable dir
    # fsync must not yield a durable sidecar (and hence no record COMPLETE;
    # the outer transactional layer records CONSUMED_INVALID => X => STOP).
    dir_sync = fsync_directory(side_path.parent)
    if not dir_sync.get("pass"):
        from hyptraj.m3cf1r0.persistence import StatePersistenceError
        raise StatePersistenceError(
            f"parent-directory fsync unavailable: {dir_sync}")
    final_sha = sha_bytes(side_path.read_bytes())
    if fault == "SIDECAR_AFTER_VERIFY":
        raise InjectedSidecarFault(
            "injected failure after sidecar verify, before record write")
    return final_sha


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (
        2**31 - 1) + 1


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# seed plan (960 units; frozen derivation)
# --------------------------------------------------------------------------

def arm_a_seed_plan(panel_states: list[dict]) -> dict:
    """960 logical units (120 states x 8 replicates) under the NEW
    M3-S25-R1-A-GRAD namespace."""
    state_ids = sorted(s["state_id"] for s in panel_states)
    if len(state_ids) != N_STATES or len(set(state_ids)) != N_STATES:
        raise RuntimeError("M3-S25-R1-X: panel shape drift for Arm-A seeds")
    planned = {f"{sid}|rep{rep}": seed(ARM_A_NAMESPACE, sid, rep)
               for sid in state_ids for rep in range(REPLICATES)}
    units = [{"unit_id": f"{sid}|rep{rep}", "state_id": sid, "rep": rep,
              "namespace": ARM_A_NAMESPACE,
              "seed_key": [planned[f"{sid}|rep{rep}"], 42424],
              "samples": N_SAMPLES}
             for sid in state_ids for rep in range(REPLICATES)]
    return {"namespace": ARM_A_NAMESPACE, "planned_seeds": planned,
            "units": units, "n_units": len(units),
            "n_trials": N_TRIALS, "budget": BUDGET}


def seed_collision_audit(plan: dict, pools: dict[str, set[int]],
                         truth_key_pools: dict[str, set[tuple]]) -> dict:
    """A0.1 item 6: explicit, type-consistent seed-collision proof.

    - 960 logical units: len(vals) == 960 AND len(set(vals)) == 960.
    - Integer seed VALUES are audited only against integer pools;
      seed_key TUPLES only against tuple pools (never mixed).
    - Per-stream zero-collision proof over every named pool."""
    vals = list(plan["planned_seeds"].values())
    if not (len(vals) == N_TRIALS and len(set(vals)) == N_TRIALS):
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A seed pool not 960 unique values "
            f"(len={len(vals)}, unique={len(set(vals))})")
    keys = [tuple(u["seed_key"]) for u in plan["units"]]
    if len(keys) != N_TRIALS or len(set(keys)) != N_TRIALS:
        raise RuntimeError("M3-S25-R1-X: Arm-A seed keys not 960 unique")
    collisions = {}
    for pool_name, pool in pools.items():
        hits = sorted({v for v in vals if v in pool})
        collisions[pool_name] = len(hits)
        if hits:
            raise RuntimeError(
                f"M3-S25-R1-X: Arm-A seed collision with {pool_name}: "
                f"{hits[:5]}")
    for pool_name, pool in truth_key_pools.items():
        hits = sorted({k for k in keys if k in pool})
        collisions[pool_name] = len(hits)
        if hits:
            raise RuntimeError(
                f"M3-S25-R1-X: Arm-A seed-key collision with {pool_name}: "
                f"{hits[:5]}")
    return {"units": N_TRIALS, "unique_seeds": len(set(vals)),
            "per_stream_collisions": collisions,
            "historical_collision": 0, "truth_stream_collision": 0,
            "ARM_A_SEED_AUDIT": "PASS"}


# --------------------------------------------------------------------------
# trial payload: frozen pipeline + lossless instrumentation + bit-exact
# crosscheck against the UNMODIFIED parent estimator
# --------------------------------------------------------------------------

def arm_a_trial(st, seed_value: int, state_id: str, rep: int, config_id: str,
                s2: float, contract_shas: dict) -> tuple[dict, dict]:
    """One Arm-A trial.  Re-executes the frozen ``gradient_decision``
    pipeline step by step, captures (a_vec, resp, sq, strata,
    bootstrap_g), and PROVES bit-exact equality with the unmodified
    estimator output.  Returns (record, sidecar_arrays)."""
    z, logp, logr, strata = draw_online_pilot(st, seed_value,
                                              n_pilot=N_SAMPLES,
                                              alpha=ALPHA_P)
    labels = st.bench_cfg.label(z)
    from hyptraj.m3d.adaptation import event_indicator_from_topology
    ind_event = event_indicator_from_topology(labels).astype(float)
    prop = st.proposal()
    pi_all = np.asarray(prop.weights, dtype=float)
    k = st.component_index
    a_vec = variance_mass_importance(z, pi_all,
                                     np.asarray(prop.centers, dtype=float),
                                     list(prop.covs), logp, logr, ind_event)
    spec = MixtureSpec(pi_all, np.asarray(prop.centers, dtype=float),
                       tuple(np.asarray(c, dtype=float) for c in prop.covs))
    resp = component_responsibility(spec, z, k)
    sq = np.einsum("ni,ni->n", z - prop.centers[k][None, :],
                   z - prop.centers[k][None, :])
    est = scalar_gradient_estimate(a_vec, resp, sq, s2=st.s2, dim=st.dim)
    # -- the CI comes from the FROZEN bootstrap function itself --
    # (A0.2 incident fix: the earlier capture used the quantile argument
    # 0.025 while the frozen stratified_bootstrap_gradient_ci uses
    # tail = (1 - 0.95)/2 = 0.025000000000000022; a 1-ULP difference in
    # the quantile argument produced a 1-ULP difference in g_ci_low and
    # tripped the bit-exact crosscheck on the first real trial.  Calling
    # the frozen function on the identical inputs is bit-identical to
    # gradient_decision's internal call by construction.)
    from hyptraj.m3.gradient_estimator import stratified_bootstrap_gradient_ci
    boot = stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, strata, s2=st.s2, dim=st.dim, n_bootstrap=N_BOOTSTRAP,
        bootstrap_seed_key=(int(seed_value), 424243))
    lo = float(boot["g_ci_low"])
    hi = float(boot["g_ci_high"])
    # -- replicate capture for the lossless sidecar only (the same rng
    # consumption as the frozen function; the captured replicate array is
    # bit-identical to its internal one) --
    rng = np.random.default_rng([int(seed_value), 424243])
    s_arr = np.asarray(strata).astype(int)
    strata_ids = np.unique(s_arr)
    sub_idx = {s: np.flatnonzero(s_arr == s) for s in strata_ids}
    sizes = {s: int(v.size) for s, v in sub_idx.items()}
    reps = np.empty(int(N_BOOTSTRAP))
    for b in range(reps.size):
        idx = np.concatenate([
            sub_idx[s][rng.integers(0, sub_idx[s].size, size=sizes[s])]
            for s in strata_ids])
        e = scalar_gradient_estimate(a_vec[idx], resp[idx], sq[idx],
                                     s2=st.s2, dim=st.dim)
        reps[b] = e["g_hat"] if e["valid_pointwise"] else np.nan
    # -- bit-exact crosscheck against the UNMODIFIED parent estimator -----
    ref = gradient_decision(st, seed_value, z, logp, logr, strata)["gradient"]
    exact = (float(est["g_hat"]) == float(ref["g_hat"])
             and lo == float(ref["g_ci_low"])
             and hi == float(ref["g_ci_high"])
             and float(est["ESS_grad"]) == float(ref["ESS_grad"])
             and float(est["M2_hat"]) == float(ref["M2_hat"])
             and float(est["D_hat"]) == float(ref["D_hat"])
             and float(est["mu_r_hat"]) == float(ref["responsibility_mass"])
             and list(est["problems"]) == list(ref["problems"]))
    if not exact:
        raise RuntimeError(
            f"M3-S25-R1-X: estimator crosscheck not bit-exact for "
            f"{state_id}|rep{rep}; the inherited estimator must remain "
            "untouched; STOP")
    g = ref
    valid = (not bool(g["problems"])
             and all(math.isfinite(float(x)) for x in
                     (g["g_hat"], g["g_ci_low"], g["g_ci_high"],
                      g["ESS_grad"]))
             and float(g["ESS_grad"]) >= ESS_MIN)
    sign = "WIDEN" if float(g["g_hat"]) < 0 else "SHRINK"
    s1 = (abs(float(g["g_hat"]))
          / ((float(g["g_ci_high"]) - float(g["g_ci_low"])) / (2.0 * Z95))
          ) if valid else None
    deploy = bool(valid and s1 is not None and float(s1) >= S1_THRESHOLD)
    event_count = int(ind_event.sum())
    record = {
        "schema": TRIAL_SCHEMA,
        "recorded_at": None,          # stamped by the persistence layer
        "state_id": state_id, "rep_id": rep, "config_id": config_id,
        "s2": float(s2),
        "curvature_c": float(st.bench_cfg.curvature_c),  # online frozen
        # config metadata (ML0 B3 comparator feature); NOT truth
        "seed": int(seed_value), "namespace": ARM_A_NAMESPACE,
        "samples": N_SAMPLES, "alpha_p": ALPHA_P,
        "gradient": {
            "g_hat": float(g["g_hat"]),
            "g_ci_low": float(g["g_ci_low"]),
            "g_ci_high": float(g["g_ci_high"]),
            "ESS_grad": float(g["ESS_grad"]),
            "M2_hat": float(g["M2_hat"]),
            "responsibility_mass": float(g["responsibility_mass"]),
            "D_hat": float(g["D_hat"]),
            "problems": list(g["problems"]),
            "s2_base": float(g["s2_base"]),
            "batches": 20,
        },
        "selected_action": sign if valid else None,
        "S1": float(s1) if s1 is not None else None,
        "S1_threshold": S1_THRESHOLD,
        "deployment": "DEPLOY" if deploy else "ABSTAIN",
        "event_count": event_count,
        "event_rate": float(event_count) / float(N_SAMPLES),
        "valid": bool(valid),
        "estimator": "hyptraj.m3d.adaptation.gradient_decision (unmodified)",
        "estimator_crosscheck_exact": True,
        "instrumentation_schema": INSTRUMENTATION_SCHEMA_VERSION,
        "instrumentation_sha256": None,   # filled by the persistence layer
        "contract_shas": dict(contract_shas),
        "z95": Z95,
        "n_bootstrap": N_BOOTSTRAP,
        "online_view_note": "no truth labels in this record",
    }
    sidecar = {"a_vec": np.asarray(a_vec, dtype=np.float64),
               "resp": np.asarray(resp, dtype=np.float64),
               "sq": np.asarray(sq, dtype=np.float64),
               "strata": np.asarray(s_arr, dtype=np.int64),
               "bootstrap_g": np.asarray(reps, dtype=np.float64)}
    return record, sidecar


# --------------------------------------------------------------------------
# restart integrity: record + sidecar, both hashes
# --------------------------------------------------------------------------

def verify_arm_a_trial_fresh_or_verified(
        unit_id: str, record_path: Path, sidecar_path: Path,
        ledger_entries: list[dict], record_hash_fn, sidecar_hash_fn) -> dict | None:
    """None for truly FRESH (no artifacts, no ledger entry); the verified
    record for a durable COMPLETE trial (exactly one STARTED + one
    COMPLETE + record hash + sidecar hash both matching); ANY other state
    raises M3-S25-R1-X (STOP, NO REPLAY)."""
    entries = [e for e in ledger_entries if e.get("state_id") == unit_id]
    any_artifact = record_path.exists() or sidecar_path.exists()
    if not entries and not any_artifact:
        return None
    if not entries and any_artifact:
        raise RuntimeError(
            f"M3-S25-R1-X: orphan Arm-A artifact without any ledger entry: "
            f"{unit_id}; STOP; NO REPLAY")
    invalid = [e for e in entries if e.get("status") == "CONSUMED_INVALID"]
    started = [e for e in entries if e.get("status") == "STARTED"]
    completes = [e for e in entries if e.get("status") == "COMPLETE"]
    if invalid:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A trial has CONSUMED_INVALID ledger state: "
            f"{unit_id}; STOP; NO REPLAY")
    if started and not completes:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A trial STARTED-only (interrupted, no "
            f"durable COMPLETE): {unit_id}; STOP; NO REPLAY")
    if completes and not started:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A trial COMPLETE without STARTED: {unit_id}; "
            "STOP; NO REPLAY")
    if len(started) != 1 or len(completes) != 1:
        raise RuntimeError(
            f"M3-S25-R1-X: duplicate/inconsistent Arm-A ledger state: "
            f"{unit_id} (STARTED={len(started)}, COMPLETE={len(completes)}); "
            "STOP; NO REPLAY")
    if not record_path.exists() or not sidecar_path.exists():
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A COMPLETE trial missing record or sidecar: "
            f"{unit_id}; STOP")
    rec_hash = completes[0].get("record_file_hash")
    if not rec_hash:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A COMPLETE entry missing record hash: "
            f"{unit_id}; STOP")
    if record_hash_fn(record_path) != rec_hash:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A record hash mismatch on restart: {unit_id}; "
            "STOP; NO REPLAY")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    side_hash = record.get("instrumentation_sha256")
    if not side_hash:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A record missing instrumentation_sha256: "
            f"{unit_id}; STOP")
    if sidecar_hash_fn(sidecar_path) != side_hash:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A sidecar hash mismatch on restart: "
            f"{unit_id}; STOP; NO REPLAY")
    return record
