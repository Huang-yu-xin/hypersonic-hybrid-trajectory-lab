"""M3-BV B2 -- build the legal candidate-state pool (task Sec. 5).

Enumerates ALL (config, s2) cells of the preregistered M3-BV grid
(8 frozen event configs x 11 s2 values = max 88), records the FROZEN
legality verdict per cell BEFORE any reference data exists
(ILLEGAL_PRE_FREEZE states are never replaced post hoc), and additionally
verifies ALL THREE required arms (BASE / WIDEN / SHRINK at delta_theta=0.20)
with the frozen deterministic checker.  Cross-checks the selected component
against the archived M1-D variance-selector record at the assembly anchor
seed, exactly like M3-D.

Writes:

    results/phase_m3bv/reference/m3bv_candidate_pool.json

Pure structure stage: zero simulator evaluation draws beyond the ONE shared
20k assembly pilot per config.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import (
    ANCHOR_SEED,
    archive_selected_mode,
    assemble_state,
)
from hyptraj.m3g.metrics import arm_legal_at

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"

DELTA_THETA = 0.20          # frozen step (identical to M3-D / M3-G-v1)


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    lock = json.loads((REPO / "configs" / "phase_m3bv"
                       / "m3bv_construction_lock.json").read_text(
                           encoding="utf-8"))
    configs = lock["candidate_grid"]["frozen_configs"]
    grid = lock["candidate_grid"]["s2_grid_bv"]

    cache = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    bcs = {}
    for cid in configs:
        if cid not in cache:
            print(f"FATAL: config {cid} not in M1-D freeze", file=__import__(
                "sys").stderr)
            return 2
        bcs[cid] = config_from_record(cache[cid])

    states_legal, illegal, stops = [], [], []
    mode_checks = {}
    for cid in configs:
        short = cid.split("_")[-1]
        bc = bcs[cid]
        st0 = None
        archived = archive_selected_mode(cid)
        for s2 in grid:
            st = assemble_state(bc, float(s2), short_config=short)
            if isinstance(st, dict):
                rec = {"config_id": cid, "state_id": st["state_id"],
                       "s2": float(s2), "status": st["status"],
                       "min_eig_selected": st.get("min_eig_selected")}
                if st["status"] == "ILLEGAL_PRE_FREEZE":
                    illegal.append(rec)
                else:
                    stops.append(rec)
                continue
            if st0 is None:
                st0 = st
                mode_checks[cid] = {
                    "assembled": st.selected_mode, "archived": archived,
                    "match": bool(archived == st.selected_mode)}
            arms_legal = {}
            for name, shift in (("base", 0.0), ("widen", +DELTA_THETA),
                                ("shrink", -DELTA_THETA)):
                ok = arm_legal_at(float(s2), shift)
                arms_legal[name] = ok
            fp = st.fingerprint()
            fp["delta_theta"] = DELTA_THETA
            fp["arms_legal"] = arms_legal
            fp["all_three_arms_legal"] = bool(
                all(arms_legal.values()))
            states_legal.append(fp)

    bad_arms = [s for s in states_legal if not s["all_three_arms_legal"]]
    if bad_arms or stops:
        print("FATAL: illegal arms or assembly stops:",
              json.dumps({"bad_arms": bad_arms, "stops": stops}, indent=1))
        return 2

    task_path = REPO / "docs" / "phase_m3bv" \
        / "M3_BV_Adaptive_Value_Benchmark_Redesign_Task.md"
    lock_path = REPO / "configs" / "phase_m3bv" \
        / "m3bv_construction_lock.json"

    pool = {
        "schema_version": "raretopo-m3bv-candidate-pool-v0",
        "record_schema_version": "raretopo-m3bv-v0",
        "stage": "B2_candidate_pool",
        "task_sha256": hashlib.sha256(task_path.read_bytes()).hexdigest(),
        "construction_lock_sha256": hashlib.sha256(
            lock_path.read_bytes()).hexdigest(),
        "m3g_v1_tag": "RareTopo-M3-G-v1",
        "parent_benchmark_freeze_hash":
            "b613f45dc6645c6da26ab58b5185764f14d771ca6b996bffed88fea1f467a5f3",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "assembly_anchor_seed": ANCHOR_SEED,
        "delta_theta": DELTA_THETA,
        "s2_grid_bv": grid,
        "frozen_configs": configs,
        "n_configs": len(configs),
        "selection_lock_crosscheck_anchor_seed": mode_checks,
        "states_legal": states_legal,
        "illegal_pre_freeze": illegal,
        "counts": {
            "legal": len(states_legal),
            "illegal_pre_freeze": len(illegal),
            "assembly_stops": len(stops),
            "max_pool": len(configs) * len(grid)},
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(pool, indent=1), encoding="utf-8")
    print(json.dumps({k: pool["counts"][k] for k in pool["counts"]},
                     indent=1))
    print("mode_checks:", json.dumps(mode_checks, indent=1))
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())