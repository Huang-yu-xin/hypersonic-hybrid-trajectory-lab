"""M3-D D4' -- frozen headline benchmark selection + seal (task Sec. 12).

Selection rule executed VERBATIM, no substitutions allowed:
    eligible state = labeled WIDEN / SHRINK / HOLD by the committed reference
                     characterization (support already enforced in labeling;
                     REFERENCE_AMBIGUOUS ineligible)
    within class   : sort by (config_id, s2) ASCENDING, take the FIRST 8

Writes (tracked): docs/phase_m3d/M3_D_Benchmark_Freeze.{json,md}
Read-only anchors: both artifact generations of the candidate pool
(original 56-state pool byte-exact; extension + refinement files appended
by amendment-1 execution -- none deleted/modified here).

After the freeze commit the benchmark is PERMANENTLY sealed: no further
amendment, no state deletion/substitution, no threshold change, no
benchmark adjustment based on gradient outcomes.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REFDIR = REPO / "results" / "phase_m3d" / "reference"
DOCDIR = REPO / "docs" / "phase_m3d"

GENERATIONS = [
    REFDIR / "m3d_candidate_pool.json",
    REFDIR / "m3d_candidate_pool_extension1.json",
    REFDIR / "m3d_candidate_pool_ext_round1.json",
    REFDIR / "m3d_candidate_pool_ext_round2.json",
]
PER_CLASS = 8


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    import numpy as np

    generations_meta, fps, refs = [], {}, {}
    for gen_path in GENERATIONS:
        if not gen_path.exists():
            continue
        d = json.loads(gen_path.read_text(encoding="utf-8"))
        generations_meta.append({
            "file": str(gen_path.relative_to(REPO)).replace("\\", "/"),
            "sha256": _sha(gen_path),
            "n_reference_states": len(d.get("reference_fields", {}))})
        for st in d.get("states_legal", []):
            fps[(st["config_id"], round(st["s2"], 10))] = st
        for k, v in d.get("reference_fields", {}).items():
            sk = v["state_key"]
            refs[(sk["config_id"], round(float(sk["s2"]), 10))] = v
        for k, v in d.items():     # refinement files nest differently
            if isinstance(v, dict) and "state_key" in v and "oracle" in v \
                    and "arms" in v:
                sk = v["state_key"]
                refs[(sk["config_id"], round(float(sk["s2"]), 10))] = v

    classes = {"WIDEN": [], "SHRINK": [], "HOLD": []}
    for key, r in refs.items():
        act = r["oracle"]["oracle_action"]
        if act in classes:
            classes[act].append(key)

    selected = {}
    for cls, pool_keys in classes.items():
        ordered = sorted(pool_keys, key=lambda k: (k[0], k[1]))
        if len(ordered) < PER_CLASS:
            raise SystemExit(f"FATAL: only {len(ordered)} {cls}-eligible "
                             f"states < required {PER_CLASS}")
        picked = ordered[:PER_CLASS]           # VERBATIM first-8, no swaps
        if len(selected) == 0:
            selected[f"_rule_{cls}"] = None
        selected[cls] = picked

    states_payload = []
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        rank = 0
        for (cid, s2v) in selected[cls]:
            rank += 1
            fp = fps[(cid, s2v)]
            r = refs[(cid, s2v)]
            b = r["arms"]["base"]
            rec = {
                "class": cls, "rank_within_class": rank,
                "config_id": cid, "state_id": fp["state_id"],
                "s2": float(s2v),
                "selected_mode": fp["selected_mode"],
                "component_index": fp["component_index"],
                "component_mean": fp["component_mean"],
                "weights_pi_c0": fp["weights_pi_c0"],
                "assembly_anchor_seed": fp.get("assembly_anchor_seed", 2026),
                "legality_passed": fp["legality_passed"],
                "min_eig_selected": fp["min_eig_selected"],
                "oracle_action": r["oracle"]["oracle_action"],
                "direction_margin_Delta_dir":
                    r["oracle"]["direction_margin_Delta_dir"],
                "reference": {
                    "n_ref_per_arm": r["n_ref_per_arm"],
                    "n_batches": r["n_batches"],
                    "M2_shrink_ref": r["arms"]["shrink"]["M2"],
                    "M2_base_ref": b["M2"],
                    "M2_widen_ref": r["arms"]["widen"]["M2"],
                    "uncertainty": {
                        "rel_M2_batch_se": {
                            arm: (r["arms"][arm]["M2_batch_se"]
                                  / r["arms"][arm]["M2"])
                            for arm in ("base", "widen", "shrink")},
                        "paired_support": r["oracle"]["support"]},
                    "ratios_over_base": r["oracle"]["ratios"],
                    "L_modes_base": {mid: lv["L"] for mid, lv
                                     in b["L_modes"].items()},
                },
            }
            states_payload.append(rec)

    sel_json = [{"class": cls,
                 "states": [[cid, s2v] for cid, s2v in selected[cls]]}
                for cls in ("WIDEN", "SHRINK", "HOLD")]

    payload = {
        "schema_version": "raretopo-m3d-benchmark-freeze-v0",
        "record_schema_version": "raretopo-m3d-v0",
        "stage": "D4_benchmark_freeze",
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "git_commit_at_freeze": _git("rev-parse", "--short", "HEAD"),
        "provenance_chain": {
            "task_canonical_sha256": "f90f8b10296070fb92346813c8ca64dcee"
                                     "5df0851644143a46246de890d6c55e",
            "amendment_1_commit_subject":
                "AMENDMENT_1_UPWARD_SCALE_EXTENSION (c79d2c8)",
            "prereg_lock_commit": "0dc9188"},
        "candidate_pool_generations": generations_meta,
        "selection_rule_locked": (
            "eligible = oracle_action in {WIDEN,SHRINK,HOLD}; within class "
            "sort by (config_id, s2) ascending; take FIRST 8; substitutions "
            "forbidden (task Sec. 12)"),
        "selection_executed": sel_json,
        "n_states_total": len(states_payload),
        "composition": {"WIDEN": len(selected["WIDEN"]),
                        "SHRINK": len(selected["SHRINK"]),
                        "HOLD": len(selected["HOLD"])},
        "online_trials_run_before_this_freeze": 0,
        "seal_declaration": {
            "after_freeze_commit": [
                "no further amendment",
                "no state deletion",
                "no threshold change",
                "no benchmark adjustment based on Gradient outcomes"]},
        "label_source_counts_all_eligible": {
            cls: len(classes[cls]) for cls in classes},
        "states": states_payload,
    }
    body = json.dumps(payload, indent=1, sort_keys=False)
    freeze_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    payload["freeze_sha256_of_body_above"] = freeze_hash
    dest_json = DOCDIR / "M3_D_Benchmark_Freeze.json"
    dest_json.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    lines = ["# M3-D Benchmark Freeze — 24 Sign-Diverse Proposal States",
             "",
             "> **Schema:** `raretopo-m3d-benchmark-freeze-v0` ｜ "
             "**Date:** 2026-08-27 ｜ **Seal:** permanent after this commit",
             "> **Commit discipline:** this freeze is committed BEFORE any "
             "online adaptive trial (task Sec. 12/42)",
             "> **Freeze hash:** `" + freeze_hash[:16] + "…`",
             "",
             "## Selection (verbatim rule, zero substitutions)",
             "",
             "`eligible = oracle_action ∈ {WIDEN, SHRINK, HOLD}; sort by "
             "(config_id, s²) ascending within class; FIRST 8.`",
             "", "| class | states (config@s² in rank order) |", "|---|---|"]
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        cells = ", ".join(f"{c.split('_')[-1]}@{s2v:g}"
                          for c, s2v in selected[cls])
        lines.append(f"| {cls} | {cells} |")
    lines += ["", "## Per-state margins & reference uncertainty",
              "", "| class | state | Δ_dir | rel SE base | "
              "ratios S/B, W/B |", "|---|---|---:|---:|---|"]
    for rec in states_payload:
        u = rec["reference"]["uncertainty"]["rel_M2_batch_se"]
        rr = rec["reference"]["ratios_over_base"]
        lines.append(
            f"| {rec['class']} | {rec['config_id'].split('_')[-1]}"
            f"@{rec['s2']:g} | {rec['direction_margin_Delta_dir']:.3f} | "
            f"{u['base']:.4f} | {rr['shrink_over_base']:+.4f} / "
            f"{rr['widen_over_base']:+.4f} |")
    lines += ["", "## Artifacts referenced",
              ""]
    for g in generations_meta:
        lines.append(f"- `{g['file']}` sha256 `{g['sha256'][:16]}…` "
                     f"({g['n_reference_states']} reference states)")
    lines += ["",
              "## Seal",
              "",
              "After the commit of this freeze the 24-state benchmark is "
              "permanently closed: no further amendment, no state deletion, "
              "no threshold change, no benchmark adjustment informed by "
              "Gradient outcomes (operator directive 2026-08-27).",
              ""]
    (DOCDIR / "M3_D_Benchmark_Freeze.md").write_text(
        "\n".join(lines), encoding="utf-8")

    print(f"frozen: {payload['composition']} | hash {freeze_hash[:16]}…")
    for cls in ("WIDEN", "SHRINK", "HOLD"):
        print(cls, [(c.split('_')[-1], s2) for c, s2 in selected[cls]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
