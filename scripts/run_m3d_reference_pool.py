"""M3-D D2 -- offline reference characterization over the candidate pool.

For every LEGAL candidate state, evaluates the frozen-semantics CRN batched
reference at N_ref per arm (preregistered 500k in 20 batches), computes the
frozen oracle label + direction margin + support, and enriches:

    results/phase_m3d/reference/m3d_candidate_pool.json

(reference block filled; oracle fields stay OUT of any online module).

Usage:
    python scripts/run_m3d_reference_pool.py            # full 500k
    python scripts/run_m3d_reference_pool.py --n-ref 5000 --states c000:0.55,...   # preflight
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m2.covariance_policy import run_shared_stage
from hyptraj.m3d.benchmark_states import ANCHOR_SEED
from hyptraj.m3d.reference_direction import BATCHES_REF, crn_batched_eval, label_state

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3d" / "reference" / "m3d_candidate_pool.json"


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-ref", type=int, default=500_000)
    ap.add_argument("--only", type=str, default=None,
                    help="comma list config_short:s2 preflight subset")
    args = ap.parse_args()

    pool = json.loads(POOL.read_text(encoding="utf-8"))
    if pool.get("reference_fields") is not None and args.only is None:
        print("FATAL: reference fields already present; refusing to overwrite",
              file=sys.stderr)
        return 2

    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    from hyptraj.m3d.benchmark_states import assemble_state, state_arms

    cfg_cache = {}

    def bc_of(cid):
        if cid not in cfg_cache:
            cfg_cache[cid] = config_from_record(freeze[cid])
        return cfg_cache[cid]

    def arms_of(cid, s2):
        st = assemble_state(bc_of(cid), s2)
        if isinstance(st, dict):
            raise RuntimeError(f"state {cid} s2={s2} not legal: {st}")
        return state_arms(st, 0.20)

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
    for s in states_sorted:
        key = (s["config_id"], s["s2"])
        if wanted is not None and key not in wanted:
            continue
        idx = len(ref_fields)
        rng_key = [701001 + idx]
        arms = arms_of(*key)
        bc = bc_of(key[0])
        ev = crn_batched_eval(arms, bc, rng_key, n_ref, BATCHES_REF)
        lab = label_state(ev, ev, tau=0.01)
        ref_fields[f"{key[0]}|{key[1]}"] = {
            "state_key": {"config_id": key[0], "s2": key[1]},
            "state_rng_key": rng_key,
            "n_ref_per_arm": n_ref, "n_batches": BATCHES_REF,
            "arms": ev,
            "oracle": lab,
        }
        if lab["oracle_action"] == "REFERENCE_AMBIGUOUS":
            ambiguous += 1
        n_done += 1
        if n_done % 7 == 0 or wanted is not None:
            print(f"  {n_done} states done "
                  f"({time.perf_counter() - t0:.0f} s)", flush=True)

    if args.only is None:
        pool["reference_fields_placeholder"] = {
            "replaced_by": "reference_fields"}
        pool.pop("reference_fields_placeholder", None)
        pool["reference_protocol_executed"] = {
            "n_ref_per_arm": n_ref, "n_batches": BATCHES_REF,
            "executed_at_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "git_commit": _git(),
            "states_characterized": len(ref_fields),
            "ambiguous_after_labeling": ambiguous,
            "source_pool_sha256": None,
        }
        pool["reference_fields"] = ref_fields
        DEST = POOL
        DEST.write_text(json.dumps(pool, indent=1), encoding="utf-8")
        print(f"[saved] {DEST.relative_to(REPO)} -- {len(ref_fields)} states, "
              f"{ambiguous} REFERENCE_AMBIGUOUS "
              f"({time.perf_counter() - t0:.0f} s total)")
    else:
        out = REPO / "results" / "phase_m3d" / "reference" / \
            "preflight_reference.json"
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
