"""M3-BV B3 -- high-budget reference characterization (task Sec. 6).

For every LEGAL candidate state evaluates the frozen-semantics CRN batched
reference at N_ref = 500k per arm in 20 batches (frozen BATCHES_REF),
computes the frozen oracle label + direction margin + support, verifies
M2 = sum_j L_j to numerical tolerance per arm, and enriches:

    results/phase_m3bv/reference/m3bv_candidate_pool.json

(reference block filled; oracle fields stay OUT of any online module).

Usage:
    python scripts/run_m3bv_reference.py            # full 500k pool
    python scripts/run_m3bv_reference.py --only c000:0.65,...  # preflight
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d.reference_direction import (
    BATCHES_REF,
    crn_batched_eval,
    label_state,
)

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
DELTA_THETA = 0.20
TOL = 1e-9


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-ref", type=int, default=500_000)
    ap.add_argument("--only", type=str, default=None)
    args = ap.parse_args()

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    if pool.get("reference_fields") is not None and args.only is None:
        print("FATAL: reference fields already present; refusing to overwrite",
              file=sys.stderr)
        return 2

    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    cfg_cache = {}

    def bc_of(cid):
        if cid not in cfg_cache:
            cfg_cache[cid] = config_from_record(freeze[cid])
        return cfg_cache[cid]

    def arms_of(cid, s2):
        st = assemble_state(bc_of(cid), s2)
        if isinstance(st, dict):
            raise RuntimeError(f"state {cid} s2={s2} not legal: {st}")
        return st, state_arms(st, DELTA_THETA)

    wanted = None
    if args.only:
        short2full = {c.split("_")[-1]: c
                      for c in {s["config_id"] for s in
                                pool["states_legal"]}}
        wanted = set()
        for tok in args.only.split(","):
            short, s2 = tok.split(":")
            wanted.add((short2full[short], float(s2)))

    n_ref = int(args.n_ref)
    t0 = time.perf_counter()
    ref_fields, ambiguous = {}, 0
    states_sorted = sorted(pool["states_legal"],
                           key=lambda s: (s["config_id"], s["s2"]))
    n_done = 0
    m2_sum_l_checked = 0
    m2_sum_l_pass = 0
    for s in states_sorted:
        key = (s["config_id"], s["s2"])
        if wanted is not None and key not in wanted:
            continue
        idx = len(ref_fields)
        rng_key = [701001 + idx]
        st, arms = arms_of(*key)
        bc = bc_of(key[0])
        ev = crn_batched_eval(arms, bc, rng_key, n_ref, BATCHES_REF)
        lab = label_state(ev, ev, tau=0.01)
        checked = {"M2_equals_sum_L": {}}
        for aname, arm_sum in ev.items():
            l_sum = float(sum(v["L"] for v in
                              arm_sum["L_modes"].values()))
            diff = abs(arm_sum["M2"] - l_sum)
            checked["M2_equals_sum_L"][aname] = {
                "diff": float(diff), "pass": bool(diff <= TOL)}
            m2_sum_l_checked += 1
            if diff <= TOL:
                m2_sum_l_pass += 1
        ref_fields[f"{key[0]}|{key[1]}"] = {
            "state_key": {"config_id": key[0], "s2": key[1]},
            "state_rng_key": rng_key,
            "n_ref_per_arm": n_ref, "n_batches": BATCHES_REF,
            "delta_theta": DELTA_THETA,
            "arms": ev,
            "oracle": lab,
            "m2_sum_L_checked": checked,
        }
        if lab["oracle_action"] == "REFERENCE_AMBIGUOUS":
            ambiguous += 1
        n_done += 1
        if n_done % 8 == 0 or wanted is not None:
            print(f"  {n_done} states done "
                  f"({time.perf_counter() - t0:.0f} s)", flush=True)

    print(f"M2=sum(L) verified on {m2_sum_l_pass}/{m2_sum_l_checked} arms")

    if args.only is None:
        pool["reference_fields"] = ref_fields
        pool["reference_protocol_executed"] = {
            "n_ref_per_arm": n_ref, "n_batches": BATCHES_REF,
            "executed_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "git_commit": _git(),
            "states_characterized": len(ref_fields),
            "ambiguous_after_labeling": ambiguous,
            "m2_equals_sum_l_arms_checked": m2_sum_l_checked,
            "m2_equals_sum_l_arms_pass": m2_sum_l_pass,
        }
        POOL.write_text(json.dumps(pool, indent=1), encoding="utf-8")
        print(f"[saved] {POOL.relative_to(REPO)} -- {len(ref_fields)} states, "
              f"{ambiguous} REFERENCE_AMBIGUOUS "
              f"({time.perf_counter() - t0:.0f} s total)")
    else:
        out = REPO / "results" / "phase_m3bv" / "reference" / \
            "m3bv_preflight_reference.json"
        out.write_text(json.dumps(ref_fields, indent=1), encoding="utf-8")
        print(json.dumps({k: v["oracle"]["oracle_action"]
                          for k, v in ref_fields.items()}, indent=1))
        k0 = next(iter(ref_fields))
        print("[preflight]", k0,
              "M2:", {a: round(v["M2"], 6)
                      for a, v in ref_fields[k0]["arms"].items()})
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())