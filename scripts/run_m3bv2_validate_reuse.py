"""M3-BV2 B2 -- validate and record the reuse of the BV-v0 candidate
characterization as prior data (task Sec. 5 / 7 / 8, construction lock
"candidate_source").

Reuse is legal only if the raw state definitions are byte-identical AND the
reuse is explicitly recorded as prior characterization data.  This script:

  1. records sha256 of both source files
     (results/phase_m3bv/reference/m3bv_candidate_pool.json,
      results/phase_m3bv/reference/m3bv_headline_stability.json);
  2. verifies the pool's internal byte-identity anchors against the frozen
     BV-v0 task doc, the BV-v0 construction lock, the M3-D state grid, and
     the locked s2 grid (8 x 11 = 88 state keys, no extras);
  3. re-checks the frozen reference semantics: N_ref = 500k/arm, 20 CRN
     batches, delta_theta = 0.20, M2 = sum_j L_j on all 264 arm records,
     3-arm legality on all 88 states, label counts;
  4. re-checks the frozen headline semantics: 100k/arm, 10 batches,
     8 replicates, replicate RNG rule, matched-per-replicate records;
  5. writes the explicit reuse record to
     results/phase_m3bv2/reuse_record.json.

NO controller output enters anywhere.  NO new simulation is executed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
DEST = REPO / "results" / "phase_m3bv2" / "reuse_record.json"

BV_TASK = REPO / "docs" / "phase_m3bv" / \
    "M3_BV_Adaptive_Value_Benchmark_Redesign_Task.md"
BV_LOCK = REPO / "configs" / "phase_m3bv" / "m3bv_construction_lock.json"
M3D_GRID = REPO / "configs" / "phase_m3d" / "m3d_candidate_state_grid.json"

S2_GRID_FROZEN = [0.65, 0.85, 1.10, 1.40, 1.80, 2.30, 3.00, 4.00, 5.00,
                  6.40, 8.00]


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    stab = json.loads(STAB.read_text(encoding="utf-8"))

    checks = {}

    # ---- byte-identity anchors -----------------------------------------
    checks["pool_task_sha256_matches_bv_task_doc"] = bool(
        pool.get("task_sha256") == sha256(BV_TASK))
    checks["pool_lock_sha256_matches_bv_lock"] = bool(
        pool.get("construction_lock_sha256") == sha256(BV_LOCK))
    checks["pool_m3g_v1_tag"] = bool(
        pool.get("m3g_v1_tag") == "RareTopo-M3-G-v1")

    grid_cfgs = json.loads(M3D_GRID.read_text(encoding="utf-8"))[
        "frozen_configs"]
    checks["pool_configs_match_m3d_grid"] = bool(
        pool.get("frozen_configs") == grid_cfgs)
    checks["pool_s2_grid_matches_lock"] = bool(
        [float(x) for x in pool.get("s2_grid_bv", [])]
        == S2_GRID_FROZEN)

    keys = sorted(pool.get("reference_fields", {}).keys())
    expected_keys = sorted(
        f"{cid}|{s2}" for cid in pool["frozen_configs"] for s2 in S2_GRID_FROZEN
        if s2 in [float(x) for x in pool["s2_grid_bv"]])
    checks["state_keys_exactly_8x11_grid"] = bool(keys == expected_keys)
    checks["n_states"] = len(keys)

    # ---- legality (task Sec. 6 / gate BV2-D0) ---------------------------
    legal_recs = [s for s in pool["states_legal"]
                  if s.get("all_three_arms_legal")]
    checks["legality_88_of_88"] = bool(
        len(legal_recs) == 88 and pool["counts"]["legal"] == 88)
    checks["zero_illegal_pre_freeze"] = bool(
        pool["counts"]["illegal_pre_freeze"] == 0
        and pool["counts"]["assembly_stops"] == 0)
    bad_arms = [s["state_id"] for s in pool["states_legal"]
                if not s.get("all_three_arms_legal")]
    checks["all_three_arms_legal_every_state"] = bool(len(bad_arms) == 0)

    # ---- reference semantics --------------------------------------------
    ref_fields = pool["reference_fields"]
    ns = {r["n_ref_per_arm"] for r in ref_fields.values()}
    nb = {r["n_batches"] for r in ref_fields.values()}
    dt = {r["delta_theta"] for r in ref_fields.values()}
    checks["reference_budget_500k_20batches"] = bool(
        ns == {500000} and nb == {20} and dt == {0.2})

    m2_ok = all(
        all(arm["pass"] for arm in r["m2_sum_L_checked"]
            ["M2_equals_sum_L"].values()) for r in ref_fields.values())
    checks["m2_equals_sum_L_all_264_arms"] = bool(m2_ok)

    labels = {}
    for r in ref_fields.values():
        a = r["oracle"]["oracle_action"]
        labels[a] = labels.get(a, 0) + 1
    checks["label_counts"] = labels

    # ---- headline semantics ----------------------------------------------
    hstab = stab["entries"]
    hn = {e["n_headline_per_arm"] for e in hstab.values()}
    hb = {e["n_batches"] for e in hstab.values()}
    hr = {e["n_replicates"] for e in hstab.values()}
    checks["headline_budget_100k_10batches_8reps"] = bool(
        hn == {100000} and hb == {10} and hr == {8})
    nrep = {len(e["replicates"]) for e in hstab.values()}
    checks["replicate_counts_8"] = bool(nrep == {8})
    checks["headline_states_88"] = bool(len(hstab) == 88)

    # replicate RNG rule: [701001 + candidate_idx, 10000 + replicate]
    rng_ok = []
    for key, e in sorted(hstab.items()):
        cid, s2 = key.split("|")
        idx = pool["frozen_configs"].index(cid) * 11 + S2_GRID_FROZEN.index(
            float(s2))
        for r in e["replicates"]:
            rng_ok.append(r["rng_key"] == [701001 + idx, 10000 + r["replicate"]])
    checks["replicate_rng_rule_exact"] = bool(all(rng_ok))

    # ---- reference RNG rule present --------------------------------------
    rng_ref = {(r["state_rng_key"][0], r["n_batches"]) for r in
               ref_fields.values()}
    checks["reference_rng_rule_anchored"] = bool(
        all(len(r["state_rng_key"]) == 1 for r in ref_fields.values())
        and len(rng_ref) == 88)

    all_ok = all(
        isinstance(v, bool) and v for k, v in checks.items()
        if k not in ("label_counts", "n_states"))

    record = {
        "schema_version": "raretopo-m3bv2-reuse-record-v0",
        "document_type": "explicit record that the BV-v0 candidate "
                         "characterization is reused as prior characterization "
                         "data (task Sec. 5); byte-identical state definitions "
                         "verified below",
        "stage": "B2_validate_reuse",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "sources": {
            "candidate_pool": {"path": POOL.relative_to(REPO).as_posix(),
                               "sha256": sha256(POOL)},
            "headline_stability": {"path": STAB.relative_to(REPO).as_posix(),
                                   "sha256": sha256(STAB)},
        },
        "reuse_condition": "raw state definitions byte-identical "
                           "(anchors below) AND reuse explicitly recorded "
                           "here as prior characterization data",
        "byte_identity_anchors": checks,
        "reference_semantics_checks": {
            "m2_equals_sum_L_all_264_arms": checks[
                "m2_equals_sum_L_all_264_arms"],
            "reference_budget_500k_20batches": checks[
                "reference_budget_500k_20batches"],
            "legality_88_of_88": checks["legality_88_of_88"],
            "zero_illegal_pre_freeze": checks["zero_illegal_pre_freeze"],
            "all_three_arms_legal_every_state": checks[
                "all_three_arms_legal_every_state"],
            "label_counts": labels,
        },
        "headline_semantics_checks": {
            "headline_budget_100k_10batches_8reps": checks[
                "headline_budget_100k_10batches_8reps"],
            "replicate_counts_8": checks["replicate_counts_8"],
            "replicate_rng_rule_exact": checks["replicate_rng_rule_exact"],
            "headline_states_88": checks["headline_states_88"],
        },
        "conclusion": "REUSE_OK" if all_ok else "REUSE_FAIL",
        "no_new_simulation": True,
        "no_controller_output_used": True,
    }

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(record, indent=1), encoding="utf-8")

    print("conclusion:", record["conclusion"])
    for k, v in checks.items():
        print(f"  {k}: {v}")
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    import sys
    raise SystemExit(main())