"""M3-BV B4 -- headline-budget stability characterization (task Sec. 9, 12).

For every LEGAL candidate state runs R = 8 matched headline-budget replicate
blocks at the FROZEN headline evaluation budget (100k per arm, in 10
batches), replicating the frozen estimator semantics.  One replicate = one
CRN block in which base/shrink/widen share a single generator stream;
replicates are independent blocks (rng rule [701001 + idx, 10000 + rep],
locked in m3bv_construction_lock.json).

Per replicate records M2 per arm and the classification-relevant events:

    widen_best  = M2_widen < M2_base AND M2_widen < M2_shrink
    shrink_best = mirrored
    hold_indiff = |widen/base - 1| <= 0.05 AND |shrink/base - 1| <= 0.05

Stability summaries: realized-best fraction of the reference action,
hold-indifference fraction.

Writes:  results/phase_m3bv/reference/m3bv_headline_stability.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d.reference_direction import crn_batched_eval

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
DEST = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"

DELTA_THETA = 0.20
N_HEADLINE = 100_000          # frozen final_eval_n per arm
N_BATCHES = 10
N_REPS = 8                    # matched replicate blocks
REP_RNG_BASE = 10_000
HOLD_BAND = 0.05


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    if pool.get("reference_fields") is None:
        print("FATAL: reference characterization (B3) must run first",
              file=sys.stderr)
        return 2
    if DEST.exists():
        print("FATAL: headline stability already present; refusing to "
              "overwrite", file=sys.stderr)
        return 2
    if N_HEADLINE % N_BATCHES != 0:
        print("FATAL: headline budget must split evenly into batches",
              file=sys.stderr)
        return 2

    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    cfg_cache = {}

    def bc_of(cid):
        if cid not in cfg_cache:
            cfg_cache[cid] = config_from_record(freeze[cid])
        return cfg_cache[cid]

    states_sorted = sorted(pool["states_legal"],
                           key=lambda s: (s["config_id"], s["s2"]))
    t0 = time.perf_counter()
    entries, done = {}, 0
    for idx, s in enumerate(states_sorted):
        cid, s2 = s["config_id"], s["s2"]
        st = assemble_state(bc_of(cid), s2)
        if isinstance(st, dict):
            print("FATAL: state no longer legal:", cid, s2, file=sys.stderr)
            return 2
        arms = state_arms(st, DELTA_THETA)
        bc = bc_of(cid)
        reps = []
        for rep in range(1, N_REPS + 1):
            rng_key = [701001 + idx, REP_RNG_BASE + rep]
            ev = crn_batched_eval(arms, bc, rng_key, N_HEADLINE, N_BATCHES)
            m2 = {a: ev[a]["M2"] for a in ("base", "widen", "shrink")}
            r_wi = m2["widen"] / m2["base"] - 1.0
            r_sh = m2["shrink"] / m2["base"] - 1.0
            widen_best = bool(m2["widen"] < m2["base"]
                              and m2["widen"] < m2["shrink"])
            shrink_best = bool(m2["shrink"] < m2["base"]
                               and m2["shrink"] < m2["widen"])
            reps.append({
                "replicate": int(rep),
                "rng_key": rng_key,
                "M2": {a: round(float(v), 9) for a, v in m2.items()},
                "ratios_over_base": {
                    "widen_over_base": float(r_wi),
                    "shrink_over_base": float(r_sh)},
                "widen_best": widen_best,
                "shrink_best": shrink_best,
                "hold_indiff": bool(abs(r_wi) <= HOLD_BAND
                                    and abs(r_sh) <= HOLD_BAND),
            })
        frac_w = float(np.mean([r["widen_best"] for r in reps]))
        frac_s = float(np.mean([r["shrink_best"] for r in reps]))
        frac_h = float(np.mean([r["hold_indiff"] for r in reps]))
        entries[f"{cid}|{s2}"] = {
            "state_key": {"config_id": cid, "s2": s2},
            "n_headline_per_arm": N_HEADLINE,
            "n_batches": N_BATCHES,
            "n_replicates": N_REPS,
            "replicates": reps,
            "stability": {
                "fraction_widen_best": frac_w,
                "fraction_shrink_best": frac_s,
                "fraction_hold_indiff": frac_h,
                "widen_stable": bool(frac_w >= 0.8),
                "shrink_stable": bool(frac_s >= 0.8),
                "hold_stable": bool(frac_h >= 0.8),
            },
        }
        done += 1
        if done % 8 == 0:
            print(f"  {done} states done "
                  f"({time.perf_counter() - t0:.0f} s)", flush=True)

    payload = {
        "schema_version": "raretopo-m3bv-headline-stability-v0",
        "record_schema_version": "raretopo-m3bv-v0",
        "stage": "B4_headline_stability",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "n_headline_per_arm": N_HEADLINE,
        "n_batches": N_BATCHES,
        "n_replicates": N_REPS,
        "stability_rule": "WIDEN/SHRINK: reference action realized best in "
                          ">= 0.8 replicates; HOLD: >= 0.8 replicates with "
                          "both perturbations within +-5% of BASE",
        "entries": entries,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"[saved] {DEST.relative_to(REPO)} -- {done} states "
          f"({time.perf_counter() - t0:.0f} s total)")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())