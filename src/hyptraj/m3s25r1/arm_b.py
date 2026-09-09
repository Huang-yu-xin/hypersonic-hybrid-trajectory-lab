"""M3-S25-R1-A2R Arm-B machinery: side (±Delta) CRN evaluation.

CRN (Common Random Numbers) stage: for each center logical unit with frozen
center seed ``seed_c``:

  - Left side:  ``draw_online_pilot(st_left, seed_c)`` -- uses its OWN
    returned z, logp, logr, strata (NOT the center's).
  - Right side: ``draw_online_pilot(st_right, seed_c)`` -- uses its OWN
    returned z, logp, logr, strata (NOT the center's).
  - Center is NEVER rerun.
  - The SAME seed_c is used for both left and right (CRN anchor).
  - Each side runs the full frozen gradient pipeline independently.

Side state construction from a center state with ``s2_center``:

  - s2_left  = s2_center * exp(-0.10)
  - s2_right = s2_center * exp(+0.10)

The side state's proposal uses the side s2 for the selected component
covariance while keeping everything else (config, bench_cfg, centers,
weights, component_index, etc.) identical to the center state.

Frozen inheritance from the parent stage M3-S2S (no scientific retuning):
estimator ``hyptraj.m3d.adaptation.gradient_decision`` (untouched -- the
trial below re-executes the identical frozen pipeline, captures the
lossless instrumentation arrays and proves BIT-EXACT equality against the
unmodified estimator on every trial); alpha_p = 0.5; S1 threshold
5.4417199447782; 960 center anchors x 2 sides = 1920 side trials;
instrumentation m3s2s_instr_v1 (N_BOOTSTRAP = 500).
"""
from __future__ import annotations

import dataclasses
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
from hyptraj.m3d.benchmark_states import BenchmarkState
from hyptraj.m3.gradient_estimator import (
    MixtureSpec,
    component_responsibility,
    scalar_gradient_estimate,
    variance_mass_importance,
)
from hyptraj.m3s2s.instrumentation import INSTRUMENTATION_SCHEMA_VERSION

# --- constants (mirrors arm_a; delta-specific additions) ---
ARM_B_NAMESPACE = "M3-S25-R1-A2R-ARM-B"
N_SAMPLES = 20_000
ALPHA_P = 0.5
Z95 = 1.959963984540054
S1_THRESHOLD = 5.4417199447782
SIDE_SCHEMA = "m3s25r1_arm_b_side_trial_v1"
DELTA = 0.10

GATES = {"coverage_min": 0.75, "unsafe_max": 0.20, "wrong_max": 0.05,
         "ambiguous_unsafe_max": 0.25}
IMPROVEMENT = {"coverage_gain_vs_aggregate_gbdt": 0.03,
               "unsafe_reduction_vs_frozen_s1": 0.05,
               "at_coverage_min": 0.75}


# --------------------------------------------------------------------------
# seed derivation (deterministic, frozen)
# --------------------------------------------------------------------------

def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (
        2**31 - 1) + 1


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# side state construction: modify s2, preserve everything else
# --------------------------------------------------------------------------

def make_side_state(center_st: BenchmarkState, side: str,
                    delta: float = DELTA) -> BenchmarkState:
    """Build a side state from a center state by modifying s2.

    For ``side == "L"``:  s2_side = s2_center * exp(-delta).
    For ``side == "R"``:  s2_side = s2_center * exp(+delta).

    All other fields (config, bench_cfg, centers, weights, component_index,
    etc.) are preserved identically from the center state.  The state's
    ``proposal()`` method will use the side s2 for the selected component
    covariance, which is exactly the controlled perturbation for the ±Delta
    arm evaluation."""
    if side not in ("L", "R"):
        raise ValueError(f"side must be 'L' or 'R', got {side!r}")
    shift = -delta if side == "L" else +delta
    s2_side = float(center_st.s2 * math.exp(shift))
    return dataclasses.replace(center_st, s2=s2_side)


# --------------------------------------------------------------------------
# seed plan: 960 center anchors x 2 sides = 1920 side units
# --------------------------------------------------------------------------

def arm_b_seed_plan(center_units: list[dict],
                    panel_states: list[dict],
                    namespace: str = ARM_B_NAMESPACE,
                    delta: float = DELTA) -> dict:
    """1920 logical side units derived from 960 center anchors.

    Each center unit with seed_c produces two side units (L and R) that
    share the SAME seed_c as their CRN anchor.  The side unit_id encodes
    the center unit_id plus the side tag (e.g.
    ``"cfg1_s2_03000|rep3|L"``).

    Returns a dict with:
      - ``namespace``
      - ``planned_seeds``: {unit_id: crn_anchor_seed} for all 1920 units
      - ``units``: list of 1920 side unit descriptors
      - ``n_units``, ``n_trials``, ``budget``
    """
    center_state_ids = sorted(s["state_id"] for s in panel_states)
    # Build lookup: state_id -> list of center units with their seeds
    center_by_state: dict[str, list[dict]] = {}
    for cu in center_units:
        sid = cu["state_id"]
        center_by_state.setdefault(sid, []).append(cu)

    planned: dict[str, int] = {}
    units: list[dict] = []

    for cu in center_units:
        center_uid = cu["unit_id"]
        seed_c = cu["seed"]
        sid = cu["state_id"]
        rep = cu["rep"]
        s2_center = cu.get("s2")

        for side in ("L", "R"):
            side_uid = f"{center_uid}|{side}"
            # CRN anchor: same seed_c for both sides
            planned[side_uid] = seed_c
            units.append({
                "unit_id": side_uid,
                "state_id": f"{sid}|{side}",
                "config_id": cu.get("config_id"),
                "rep": rep,
                "namespace": namespace,
                "seed": seed_c,               # CRN anchor = center seed
                "seed_key": [seed_c, 42424],
                "samples": N_SAMPLES,
                "center_unit_id": center_uid,
                "side": side,
                "s2_center": s2_center,
                "delta": delta,
            })

    n_units = len(units)
    n_center = len(center_units)
    if n_units != 2 * n_center:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: expected {2 * n_center} side units, "
            f"got {n_units}")

    return {
        "namespace": namespace,
        "planned_seeds": planned,
        "units": units,
        "n_units": n_units,
        "n_trials": n_units,
        "budget": n_units * N_SAMPLES,
        "n_center_anchors": n_center,
        "delta": delta,
    }


def seed_collision_audit(plan: dict, pools: dict[str, set[int]],
                          truth_key_pools: dict[str, set[tuple]],
                          expected_units: int | None = None,
                          expected_anchors: int | None = None) -> dict:
    """Side-seed collision audit: prove zero overlap across named pools.

    Arm-B has 1920 side units derived from 960 center CRN anchors.
    LEFT and RIGHT for the same center share the same historical center
    seed.  Therefore there are 960 UNIQUE seed values (not 1920).

    Checks:
      - exactly ``expected_units`` side units (default 1920)
      - exactly ``expected_anchors`` unique anchor seeds (default 960)
      - every side unit's seed equals its center anchor seed
      - each anchor seed appears exactly twice (L + R)
      - no cross-center seed sharing (each center has a distinct anchor)
      - zero overlap with retired/excluded pools
      - intentional L/R center-anchor reuse is NOT a collision

    ``expected_count`` parameter is deprecated; use ``expected_units``.
    """
    if expected_units is None:
        expected_units = plan["n_units"]
    if expected_anchors is None:
        expected_anchors = plan.get("n_center_anchors",
                                     plan.get("n_center_anchors", 960))

    # --- structural checks ---
    units = plan["units"]
    if len(units) != expected_units:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: expected {expected_units} side units, "
            f"got {len(units)}")

    # --- anchor pairing: each center seed appears exactly L + R = 2 ---
    anchor_counts: dict[int, list[str]] = {}
    for u in units:
        anchor_counts.setdefault(u["seed"], []).append(u["unit_id"])
    for seed_val, uids in anchor_counts.items():
        if len(uids) != 2:
            raise RuntimeError(
                f"M3-S25-R1-A2R-ARM-B-X: anchor seed {seed_val} appears "
                f"{len(uids)} times (expected exactly 2: L+R)")
        # Extract side from the unit's side field, not from unit_id
        sides = set()
        for u in units:
            if u["seed"] == seed_val:
                sides.add(u["side"])
        if sides != {"L", "R"}:
            raise RuntimeError(
                f"M3-S25-R1-A2R-ARM-B-X: anchor seed {seed_val} has "
                f"sides {sides} (expected {{L, R}})")

    unique_anchors = set(anchor_counts.keys())
    if len(unique_anchors) != expected_anchors:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: expected {expected_anchors} unique "
            f"anchor seeds, got {len(unique_anchors)}")

    # --- cross-center isolation: different centers must not share seeds ---
    center_for_seed: dict[int, str] = {}
    for u in units:
        cid = u.get("center_unit_id", "?")
        s = u["seed"]
        if s in center_for_seed and center_for_seed[s] != cid:
            raise RuntimeError(
                f"M3-S25-R1-A2R-ARM-B-X: cross-center seed sharing: "
                f"seed {s} used by both {center_for_seed[s]} and {cid}")
        center_for_seed[s] = cid

    # --- pool collision checks (retired/excluded seeds) ---
    vals = list(unique_anchors)
    collisions: dict[str, int] = {}
    for pool_name, pool in pools.items():
        hits = sorted({v for v in vals if v in pool})
        collisions[pool_name] = len(hits)
        if hits:
            raise RuntimeError(
                f"M3-S25-R1-A2R-ARM-B-X: anchor seed collision with "
                f"{pool_name}: {hits[:5]}")

    keys = [(s, center_for_seed[s]) for s in vals]
    for pool_name, pool in truth_key_pools.items():
        hits = sorted({k for k in keys if k in pool})
        collisions[pool_name] = len(hits)
        if hits:
            raise RuntimeError(
                f"M3-S25-R1-A2R-ARM-B-X: anchor key collision with "
                f"{pool_name}: {hits[:5]}")

    return {
        "side_units": expected_units,
        "unique_anchors": len(unique_anchors),
        "anchors_per_center": 2,
        "per_stream_collisions": collisions,
        "cross_center_sharing": 0,
        "historical_collision": 0,
        "ARM_B_SEED_AUDIT": "PASS",
    }


# --------------------------------------------------------------------------
# transactional sidecar write (identical durability protocol to arm_a)
# --------------------------------------------------------------------------

class InjectedSidecarFault(RuntimeError):
    pass


SIDECAR_FAULT_TAGS = ("SIDECAR_BEFORE_FSYNC", "SIDECAR_AFTER_FSYNC_BEFORE_RENAME",
                      "SIDECAR_AFTER_VERIFY")


def write_sidecar_transactional(side_path: Path, arrays: dict,
                                fault: str | None = None,
                                dir_fsync_fn=None) -> str:
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
    _dir_fsync = dir_fsync_fn or fsync_directory
    dir_sync = _dir_fsync(side_path.parent)
    if not dir_sync.get("pass"):
        from hyptraj.m3cf1r0.persistence import StatePersistenceError
        raise StatePersistenceError(
            f"parent-directory fsync unavailable: {dir_sync}")
    final_sha = sha_bytes(side_path.read_bytes())
    if fault == "SIDECAR_AFTER_VERIFY":
        raise InjectedSidecarFault(
            "injected failure after sidecar verify, before record write")
    return final_sha


# --------------------------------------------------------------------------
# trial payload: frozen pipeline + lossless instrumentation + bit-exact
# crosscheck against the UNMODIFIED parent estimator
# --------------------------------------------------------------------------

def arm_b_trial(st_side: BenchmarkState, seed_c: int, state_id: str,
                rep: int, side: str, center_unit_id: str,
                contract_shas: dict,
                namespace: str = ARM_B_NAMESPACE) -> tuple[dict, dict]:
    """One Arm-B side trial.  Re-executes the frozen ``gradient_decision``
    pipeline on the SIDE state, using the CENTER seed as the CRN anchor.

    ``st_side``: the side state (s2 perturbed by ±Delta from center).
    ``seed_c``: the center's CRN anchor seed (SAME for L and R).
    ``side``: "L" or "R".

    The pilot is drawn from the SIDE state's proposal using seed_c, so the
    returned z, logp, logr, strata are SIDE-specific (NOT center's).
    Each side runs the full frozen gradient pipeline independently.

    Returns (record, sidecar_arrays) with the same schema as arm_a_trial
    plus side-specific provenance fields."""
    # --- CRN pilot: same seed_c, but applied to the SIDE state ---
    z, logp, logr, strata = draw_online_pilot(st_side, seed_c,
                                               n_pilot=N_SAMPLES,
                                               alpha=ALPHA_P)
    # --- frozen gradient pipeline (identical to arm_a_trial) ---
    labels = st_side.bench_cfg.label(z)
    from hyptraj.m3d.adaptation import event_indicator_from_topology
    ind_event = event_indicator_from_topology(labels).astype(float)
    prop = st_side.proposal()
    pi_all = np.asarray(prop.weights, dtype=float)
    k = st_side.component_index
    a_vec = variance_mass_importance(z, pi_all,
                                     np.asarray(prop.centers, dtype=float),
                                     list(prop.covs), logp, logr, ind_event)
    spec = MixtureSpec(pi_all, np.asarray(prop.centers, dtype=float),
                       tuple(np.asarray(c, dtype=float) for c in prop.covs))
    resp = component_responsibility(spec, z, k)
    sq = np.einsum("ni,ni->n", z - prop.centers[k][None, :],
                   z - prop.centers[k][None, :])
    est = scalar_gradient_estimate(a_vec, resp, sq,
                                   s2=st_side.s2, dim=st_side.dim)
    # -- bootstrap CI from the FROZEN bootstrap function --
    from hyptraj.m3.gradient_estimator import stratified_bootstrap_gradient_ci
    boot = stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, strata, s2=st_side.s2, dim=st_side.dim,
        n_bootstrap=N_BOOTSTRAP,
        bootstrap_seed_key=(int(seed_c), 424243))
    lo = float(boot["g_ci_low"])
    hi = float(boot["g_ci_high"])
    # -- replicate capture for the lossless sidecar --
    rng = np.random.default_rng([int(seed_c), 424243])
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
                                     s2=st_side.s2, dim=st_side.dim)
        reps[b] = e["g_hat"] if e["valid_pointwise"] else np.nan
    # -- bit-exact crosscheck against the UNMODIFIED parent estimator --
    ref = gradient_decision(st_side, seed_c, z, logp, logr, strata)["gradient"]
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
            f"M3-S25-R1-A2R-ARM-B-X: estimator crosscheck not bit-exact for "
            f"{state_id}|{side}; the inherited estimator must remain "
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
        "schema": SIDE_SCHEMA,
        "recorded_at": None,          # stamped by the persistence layer
        "state_id": state_id, "rep_id": rep,
        "config_id": st_side.config_id,
        "s2": float(st_side.s2),
        "s2_center": float(st_side.s2 / math.exp(-DELTA)
                           if side == "L"
                           else st_side.s2 / math.exp(+DELTA)),
        "s2_side": float(st_side.s2),
        "delta": DELTA,
        "side": side,
        "center_unit_id": center_unit_id,
        "curvature_c": float(st_side.bench_cfg.curvature_c),  # online frozen
        # config metadata (ML0 B3 comparator feature); NOT truth
        "seed": int(seed_c), "namespace": namespace,
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

def verify_arm_b_trial_fresh_or_verified(
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
            f"M3-S25-R1-A2R-ARM-B-X: orphan Arm-B artifact without any "
            f"ledger entry: {unit_id}; STOP; NO REPLAY")
    invalid = [e for e in entries if e.get("status") == "CONSUMED_INVALID"]
    started = [e for e in entries if e.get("status") == "STARTED"]
    completes = [e for e in entries if e.get("status") == "COMPLETE"]
    if invalid:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B trial has CONSUMED_INVALID "
            f"ledger state: {unit_id}; STOP; NO REPLAY")
    if started and not completes:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B trial STARTED-only "
            f"(interrupted, no durable COMPLETE): {unit_id}; STOP; NO REPLAY")
    if completes and not started:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B trial COMPLETE without STARTED: "
            f"{unit_id}; STOP; NO REPLAY")
    if len(started) != 1 or len(completes) != 1:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: duplicate/inconsistent Arm-B ledger "
            f"state: {unit_id} (STARTED={len(started)}, "
            f"COMPLETE={len(completes)}); STOP; NO REPLAY")
    if not record_path.exists() or not sidecar_path.exists():
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B COMPLETE trial missing record "
            f"or sidecar: {unit_id}; STOP")
    rec_hash = completes[0].get("record_file_hash")
    if not rec_hash:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B COMPLETE entry missing record "
            f"hash: {unit_id}; STOP")
    if record_hash_fn(record_path) != rec_hash:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B record hash mismatch on "
            f"restart: {unit_id}; STOP; NO REPLAY")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    side_hash = record.get("instrumentation_sha256")
    if not side_hash:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B record missing "
            f"instrumentation_sha256: {unit_id}; STOP")
    if sidecar_hash_fn(sidecar_path) != side_hash:
        raise RuntimeError(
            f"M3-S25-R1-A2R-ARM-B-X: Arm-B sidecar hash mismatch on "
            f"restart: {unit_id}; STOP; NO REPLAY")
    return record
