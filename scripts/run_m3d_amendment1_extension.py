"""M3-D amendment-1 execution -- upward scale extension + bracket refinement.

Post-amendment benchmark construction per
configs/phase_m3d/m3d_candidate_state_grid.json -> amendments[0]
(committed BEFORE this script runs anything):

  extension grid : s2 in [2.50, 3.20, 4.00, 5.00, 6.40, 8.00] x 8 configs
  refinement     : log-space midpoints sqrt(sW^2*sS^2) between ADJACENT
                   opposite-label states within one config; max 2 rounds;
                   triggered only while eligible HOLD < 8
  protocol       : N_ref=500k/arm CRN batched (20 batches); tau=0.01;
                   margin>=0.05; HOLD +-3%; support |contrast|>=2x paired SE

Outputs (append-only artifacts; original pool file NEVER touched):
    results/phase_m3d/reference/m3d_candidate_pool_extension1.json
    results/phase_m3d/reference/m3d_candidate_pool_ext_round1.json   (opt)
    results/phase_m3d/reference/m3d_candidate_pool_ext_round2.json   (opt)
    results/phase_m3d/summary/d3_sign_diversity_gate_v2.json         (verdict)

Usage:
    python scripts/run_m3d_amendment1_extension.py           # full run incl. refinement
    python scripts/run_m3d_amendment1_extension.py --n-ref 5000   # smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d.reference_direction import BATCHES_REF, crn_batched_eval, label_state

REPO = Path(__file__).resolve().parents[1]
REFDIR = REPO / "results" / "phase_m3d" / "reference"
ORIG_POOL = REFDIR / "m3d_candidate_pool.json"
GRID = json.loads((REPO / "configs" / "phase_m3d"
                   / "m3d_candidate_state_grid.json").read_text(
                       encoding="utf-8"))
AMEND = next(a for a in GRID["amendments"]
             if a["id"] == "AMENDMENT_1_UPWARD_SCALE_EXTENSION")


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def characterize(states_in, *, n_ref: int, rng_offset: int) -> tuple[list, dict]:
    """Legality-first enumeration then CRN characterization of candidates.

    ``states_in``: iterable of (config_id, s2).  Returns (legal_states,
    reference_fields keyed 'config|s2')."""
    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    cfg_cache = {}

    def bc_of(cid):
        if cid not in cfg_cache:
            cfg_cache[cid] = config_from_record(freeze[cid])
        return cfg_cache[cid]

    legal, illegal, refs = [], [], {}
    order = sorted(states_in)
    for idx, (cid, s2) in enumerate(order):
        st = assemble_state(bc_of(cid), float(s2))
        if isinstance(st, dict):
            illegal.append({"config_id": cid, "s2": float(s2),
                            "status": st["status"],
                            "min_eig": st.get("min_eig_selected")})
            continue
        legal.append(st)
    for idx, st in enumerate(sorted(legal,
                                    key=lambda s: (s.config_id, s.s2))):
        arms = state_arms(st, 0.20)
        ev = crn_batched_eval(arms, bc_of(st.config_id),
                              [701001 + rng_offset + idx], n_ref,
                              BATCHES_REF)
        lab = label_state(ev, ev, tau=0.01)
        refs[f"{st.config_id}|{st.s2:g}"] = {
            "state_key": {"config_id": st.config_id, "s2": st.s2},
            "state_rng_key": [701001 + rng_offset + idx],
            "n_ref_per_arm": n_ref, "n_batches": BATCHES_REF,
            "arms": ev, "oracle": lab}
    return legal, {"reference_fields": refs, "illegal_pre_freeze": illegal}


def labels_from_file(path: Path) -> dict[str, str]:
    d = json.loads(path.read_text(encoding="utf-8"))
    rf = d.get("reference_fields", d)
    return {k: v["oracle"]["oracle_action"] for k, v in rf.items()}


def merged_labels(extra_files: list[Path]) -> dict[str, str]:
    """Union of oracle labels: original pool + extension + refinement files."""
    out = dict(labels_from_file(ORIG_POOL))
    for p in extra_files:
        if p.exists():
            out.update(labels_from_file(p))
    return out


def gate_check(lab: dict[str, str]) -> tuple[bool, dict]:
    acts = {"WIDEN": 0, "SHRINK": 0, "HOLD": 0,
            "REFERENCE_AMBIGUOUS": 0}
    cfg_by_class = {"WIDEN": set(), "SHRINK": set(), "HOLD": set()}
    for act in lab.values():
        if act in acts:
            acts[act] += 1
            if act != "REFERENCE_AMBIGUOUS":
                cfg_by_class[act].add(act.split("|")[0])
    ok = all(acts[c] >= 8 for c in ("WIDEN", "SHRINK", "HOLD"))
    multi = all(len({k.rsplit("|", 1)[0] for k, v in lab.items()
                     if v == c}) >= 2 for c in ("WIDEN", "SHRINK", "HOLD"))
    return bool(ok and multi), acts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-ref", type=int, default=500_000)
    ap.add_argument("--no-refine", action="store_true")
    args = ap.parse_args()

    pre_hash = _sha(ORIG_POOL)
    ext_grid = AMEND["s2_grid_extension_locked"]
    freeze_cfgs = GRID["frozen_configs"]
    t0 = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ---- stage E: extension characterization ----------------------------- #
    cand = [(cid, s2) for cid in freeze_cfgs for s2 in ext_grid]
    print(f"[ext] characterizing {len(cand)} extension states "
          f"@ {args.n_ref}/arm ...", flush=True)
    legal, refs = characterize(cand, n_ref=args.n_ref, rng_offset=1000)

    ext_out = {
        "schema_version": "raretopo-m3d-candidate-pool-ext-v1",
        "amendment_id": AMEND["id"],
        "executed_at_utc": t0, "git_commit_at_execution": _git(),
        "original_pool_sha256_recorded": pre_hash,
        "task_sha256_canonical": hashlib.sha256(
            (REPO / "docs" / "phase_m3d"
             / "M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md")
            .read_bytes()).hexdigest(),
        "extension_grid": ext_grid,
        "n_ref_per_arm": args.n_ref,
        "states_legal": [st.fingerprint() for st in legal],
        "illegal_pre_freeze": refs["illegal_pre_freeze"],
        "reference_fields": refs["reference_fields"],
    }
    EXT = REFDIR / "m3d_candidate_pool_extension1.json"
    EXT.write_text(json.dumps(ext_out, indent=1), encoding="utf-8")
    _, acts = gate_check(merged_labels([EXT]))
    print(f"[ext] labels after extension: {acts}")

    # ---- stage R: up to 2 refinement rounds ------------------------------ #
    rounds_done = []
    round_files = []
    if not args.no_refine:
        for rnd in (1, 2):
            ok, acts = gate_check(merged_labels([EXT] + round_files))
            if ok:
                print(f"[round {rnd}] gate already satisfied -- no "
                      f"refinement needed")
                break
            hold_n = acts.get("HOLD", 0)
            wid_n = acts.get("WIDEN", 0)
            shr_n = acts.get("SHRINK", 0)
            brackets = []
            lab = merged_labels([EXT] + round_files)
            by_cfg: dict[str, list[tuple[float, str]]] = {}
            for k, a in lab.items():
                if a in ("WIDEN", "SHRINK"):
                    cid, s2 = k.rsplit("|", 1)
                    by_cfg.setdefault(cid, []).append((float(s2), a))
            seen_pairs = set()
            for cid, vals in sorted(by_cfg.items()):
                vals.sort()
                for (sa, aa), (sb, ab) in zip(vals, vals[1:]):
                    if aa == ab:
                        continue
                    mid = float(np.sqrt(sa * sb))
                    if f"{cid}|{mid:g}" in lab:
                        continue
                    pk = (cid, sa, sb)
                    if pk in seen_pairs:
                        continue
                    seen_pairs.add(pk)
                    brackets.append((cid, mid))
            if not brackets:
                print(f"[round {rnd}] no WIDEN->SHRINK bracket available")
                break
            print(f"[round {rnd}] refining {len(brackets)} bracket "
                  f"midpoints (HOLD={hold_n} W={wid_n} S={shr_n})",
                  flush=True)
            rl, rr = characterize([(c, m) for c, m in brackets],
                                  n_ref=args.n_ref,
                                  rng_offset=2000 + 1000 * rnd)
            rout = {
                "schema_version": "raretopo-m3d-candidate-pool-refine-v1",
                "round": rnd, "rule": AMEND["bracket_refinement_locked"],
                "midpoint_candidates": [{"config_id": c, "s2": m}
                                        for c, m in brackets],
                "states_legal": [st.fingerprint() for st in rl],
                "illegal_pre_freeze": rr["illegal_pre_freeze"],
                "reference_fields": rr["reference_fields"],
            }
            rpath = REFDIR / f"m3d_candidate_pool_ext_round{rnd}.json"
            rpath.write_text(json.dumps(rout, indent=1), encoding="utf-8")
            round_files.append(rpath)
            rounds_done.append(rnd)
            _, acts = gate_check(merged_labels([EXT] + round_files))
            print(f"[round {rnd}] labels now: {acts}")

    # ---- final gate ------------------------------------------------------ #
    ok, acts = gate_check(merged_labels([EXT] + round_files))
    verdict = "GO" if ok else (
        ("REFINE_EXHAUSTED" if rounds_done else "NO_BRACKETS_OR_NOT_NEEDED"),
    )
    final = {
        "schema_version": "raretopo-m3d-sign-diversity-gate-v2",
        "stage": "D3 post-amendment sign-diversity gate",
        "date_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "rule_source": ["task Sec.10 (>=8/8/8 across multiple configs)",
                        "AMENDMENT_1_UPWARD_SCALE_EXTENSION"],
        "observed_label_counts": acts,
        "required": {"WIDEN": 8, "SHRINK": 8, "HOLD": 8},
        "gate_passed": bool(ok),
        "verdict": "GO" if ok else "PERMANENT_STOP_M3D_V0",
        "refinement_rounds_executed": rounds_done,
        "permanent_stop_clause":
            AMEND["permanent_stop_clause"],
        "online_trials_run_so_far": 0,
        "artifacts": {
            "original_pool_sha256_unchanged": _sha(ORIG_POOL) == pre_hash,
            "original_pool_sha256": pre_hash,
            "extension_pool_sha256": _sha(EXT),
            "refinement_round_files": [str(p.relative_to(REPO)).replace(
                "\\", "/") + f" sha256={_sha(p)}" for p in round_files]},
    }
    dest = REPO / "results" / "phase_m3d" / "summary" / \
        "d3_sign_diversity_gate_v2.json"
    dest.write_text(json.dumps(final, indent=1), encoding="utf-8")
    print(json.dumps({"gate_passed": ok, "labels": acts,
                      "rounds": rounds_done}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
