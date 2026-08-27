"""M3-D D1 -- build the legal candidate-state pool (task Sec. 6, 11).

Enumerates ALL (config, s2) cells of the preregistered grid, records the
FROZEN-legality verdict per cell BEFORE any reference data exists
(ILLEGAL_PRE_FREEZE states are never replaced), cross-checks the selected
component against the archived M1-D variance-selector record at the assembly
anchor seed, and writes:

    results/phase_m3d/reference/m3d_candidate_pool.json

Pure structure stage: zero simulator evaluation draws beyond the ONE shared
20k assembly pilot per config.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m3d.benchmark_states import (
    ANCHOR_SEED,
    archive_selected_mode,
    enumerate_candidate_states,
)

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "results" / "phase_m3d" / "reference" / \
    "m3d_candidate_pool.json"


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    enum = enumerate_candidate_states()
    grid = enum["grid"]
    if enum["assembly_stops"]:
        print(f"FATAL: {len(enum['assembly_stops'])} assembly stops:",
              json.dumps(enum["assembly_stops"], indent=1))
        return 2

    mode_checks = {}
    for st in enum["states"][:7]:            # one state per config suffices:
        cid = st.config_id                   # all s2 share the same mixture
        archived = archive_selected_mode(cid)
        mode_checks[cid] = {
            "assembled": st.selected_mode, "archived": archived,
            "match": bool(archived == st.selected_mode)}

    pool = {
        "schema_version": "raretopo-m3d-candidate-pool-v0",
        "record_schema_version": "raretopo-m3d-v0",
        "stage": "D1_candidate_pool",
        "task_sha256": hashlib.sha256(
            (REPO / "docs" / "phase_m3d"
             / "M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md")
            .read_bytes()).hexdigest(),
        "benchmark_freeze_hash": hashlib.sha256(
            (REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json")
            .read_bytes()).hexdigest(),
        "m3v0_frozen_head": grid["parent_tags"]["m3_v0_frozen_head"],
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "assembly_anchor_seed": ANCHOR_SEED,
        "s2_grid": grid["s2_grid_locked"],
        "n_configs": len(grid["frozen_configs"]),
        "selection_lock_crosscheck_anchor_seed": mode_checks,
        "states_legal": [st.fingerprint() for st in enum["states"]],
        "illegal_pre_freeze": enum["illegal_pre_freeze"],
        "counts": {
            "legal": len(enum["states"]),
            "illegal_pre_freeze": len(enum["illegal_pre_freeze"]),
            "max_pool": len(grid["frozen_configs"]) * len(
                grid["s2_grid_locked"])},
        "reference_fields_placeholder": None,   # filled by D2 driver only
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(pool, indent=1), encoding="utf-8")
    bad = [c for c, v in mode_checks.items() if not v["match"]]
    print(f"pool: {pool['counts']['legal']} legal / "
          f"{pool['counts']['illegal_pre_freeze']} illegal / cap "
          f"{pool['counts']['max_pool']}")
    print("selection lock (anchor seed):",
          "ALL MATCH" if not bad else f"MISMATCH {bad}")
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
