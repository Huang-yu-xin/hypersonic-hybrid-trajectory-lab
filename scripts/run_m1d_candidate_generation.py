"""M1-D1/D2 -- deterministic candidate generation + offline oracle characterization.

Task preregistration: ``docs/phase_m1d/M1_D_Multi_Missing_Mode_Variance_
Geometry_Benchmark_Task.md`` Sec. 10-12, Sec. 42 (run order M1-D1, M1-D2,
M1-D3) and Sec. 49.

Stages
------
``pool``   generate one deterministic candidate batch and characterize every
           candidate offline (P_k^ref, L_k^ref(q_0), bootstrap CIs, eligibility
           E1-E6).  Writes ``candidate_pool_b<seed>_v1.json`` + CSV table.
           NO adaptive/policy code runs here or anywhere in M1-D1/D2.
``freeze`` load all existing pool files in batch order, apply the frozen
           deterministic rule (eligible configs sorted by config_id ascending,
           take the first 8; batch seed 20260828 continues if short), write
           ``M1_D_Benchmark_Freeze.json`` / ``.md``.  Refuses to overwrite an
           existing freeze artifact.

Usage
-----
    python scripts/run_m1d_candidate_generation.py --stage pool
    python scripts/run_m1d_candidate_generation.py --stage freeze
    python scripts/run_m1d_candidate_generation.py --stage pool --smoke
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.benchmark_family import (
    BOOTSTRAP_REPS,
    MC_FRACTION,
    MODE_IDS,
    generate_candidate_pool,
    reference_characterize,
)

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "phase_m1d" / "m1d_candidate_generation.json"
OUT_DIR = REPO / "results" / "phase_m1d" / "benchmark_freeze"


def git_short_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=REPO, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _smoke_rewrite(cfg: dict) -> dict:
    cfg = json.loads(json.dumps(cfg))                       # deep copy
    gen = cfg["candidate_generation"]
    gen["batch_1"]["size"] = 4
    gen["batch_2_fallback"]["size"] = 4
    ref = cfg["reference_characterization"]
    ref["n_reference_total"] = 20_000
    ref["bootstrap"]["reps"] = 40
    cfg["_smoke"] = True
    return cfg


# ---------------------------------------------------------------------------
# stage: pool
# ---------------------------------------------------------------------------
def run_pool(config: dict, batch_seed: int, size: int) -> Path:
    t0 = time.perf_counter()
    n_ref = int(config["reference_characterization"]["n_reference_total"])
    reps = int(config["reference_characterization"]["bootstrap"]["reps"])

    print(f"[pool] batch_seed={batch_seed} size={size} "
          f"n_reference={n_ref} boot_reps={reps}", flush=True)
    pool = generate_candidate_pool(batch_seed, size)

    records = []
    for i, bc in enumerate(pool):
        rec = reference_characterize(bc, n_reference=n_ref,
                                     bootstrap_reps=reps)
        records.append(rec)
        e = rec["eligibility"]
        flags = "".join("1" if e[k] else "0" for k in (
            "E1_K_missing_ge3", "E2_observability", "E3_top_rank_conflict",
            "E4_strong_inversion", "E5_variance_criticality",
            "E6_no_degenerate_domination"))
        print(f"  [{i + 1:03d}/{size}] {bc.config_id} E={flags} "
              f"kP*={e['k_P_star']} kV*={e['k_V_star']} "
              f"omega_top={e['omega_top_missing']:.3f} "
              f"tau={e['kendall_tau_PV']:+.2f}", flush=True)

    eligible_ids = [r["config_id"] for r in records if r["eligibility"]["eligible"]]
    payload = {
        "schema_version": "raretopo-m1d-candidate-pool-v0",
        "config_sha256": sha256_hex(CONFIG_PATH),
        "git_commit": git_short_head(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_smoke": bool(config.get("_smoke", False)),
        "batch_seed": int(batch_seed),
        "pool_size": int(size),
        "n_reference_total": n_ref,
        "bootstrap_reps": reps,
        "mc_fraction": MC_FRACTION,
        "mode_ids": list(MODE_IDS),
        "n_eligible": len(eligible_ids),
        "eligible_config_ids": eligible_ids,
        "candidates": records,
        "total_wall_time_s": round(time.perf_counter() - t0, 1),
    }
    suffix = "_smoke" if config.get("_smoke") else ""
    out_path = OUT_DIR / f"candidate_pool_b{batch_seed}{suffix}_v1.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    _write_csv(records, OUT_DIR / f"eligibility_table_b{batch_seed}"
               f"{suffix}_v1.csv")
    print(f"[pool] written {out_path.name}: eligible "
          f"{len(eligible_ids)}/{size}", flush=True)
    return out_path


def _write_csv(records: list[dict], path: Path) -> None:
    cols = ["config_id", "theta_S1", "theta_S2", "theta_S3", "theta_S4",
            "h_S1", "h_S2", "h_S3", "h_S4", "curved_S2", "curved_S3",
            "curved_S4",
            "P_S2", "P_S3", "P_S4", "L_S2", "L_S3", "L_S4",
            "rank_P_S2", "rank_P_S3", "rank_P_S4",
            "rank_L_S2", "rank_L_S3", "rank_L_S4",
            "k_P_star", "k_V_star", "kendall_tau", "spearman_rho",
            "omega_top", "E1", "E2", "E3", "E4", "E5", "E6", "eligible"]

    def m(r, mid):
        return r["modes"][mid]

    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in records:
            e = r["eligibility"]
            par = r["params"]
            th, hh = par["theta_deg"], par["h"]
            cv = par["curved"]
            P = [m(r, x)["P_ref"] for x in MODE_IDS[1:]]
            L = [m(r, x)["L_ref"] for x in MODE_IDS[1:]]
            w.writerow(
                [r["config_id"], *th, *hh, *[int(c) for c in cv[1:]],
                 *P, *L,
                 *[e["rank_P"][x] for x in MODE_IDS[1:]],
                 *[e["rank_L"][x] for x in MODE_IDS[1:]],
                 e["k_P_star"], e["k_V_star"],
                 e["kendall_tau_PV"], e["spearman_rho_PV"],
                 e["omega_top_missing"],
                 *[int(e[k]) for k in ("E1_K_missing_ge3", "E2_observability",
                                       "E3_top_rank_conflict",
                                       "E4_strong_inversion",
                                       "E5_variance_criticality",
                                       "E6_no_degenerate_domination")],
                 int(e["eligible"])])
    print(f"[pool] csv table -> {path.name}", flush=True)


# ---------------------------------------------------------------------------
# stage: freeze
# ---------------------------------------------------------------------------
FREEZE_N = 8


def run_freeze(config: dict) -> tuple[Path, Path]:
    pool_files = sorted(OUT_DIR.glob("candidate_pool_b*_v1.json"))
    pool_files = [p for p in pool_files if "_smoke" not in p.name]
    if not pool_files:
        raise SystemExit("[freeze] no pool artifacts found -- run --stage pool first")
    print(f"[freeze] pooling {len(pool_files)} batches: "
          f"{[p.name for p in pool_files]}")

    records_by_id: dict[str, dict] = {}
    per_batch_summary = []
    for pf in pool_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        per_batch_summary.append({
            "file": str(pf.relative_to(REPO)),
            "sha256": sha256_hex(pf),
            "batch_seed": data["batch_seed"],
            "pool_size": data["pool_size"],
            "n_eligible": data["n_eligible"],
        })
        for rec in data["candidates"]:
            rid = rec["config_id"]
            if rid in records_by_id:
                raise SystemExit(f"[freeze] duplicate config id {rid}")
            records_by_id[rid] = rec

    eligible = sorted((rec for rec in records_by_id.values()
                       if rec["eligibility"]["eligible"]),
                      key=lambda r: r["config_id"])
    print(f"[freeze] total candidates={len(records_by_id)} "
          f"eligible={len(eligible)}")
    if len(eligible) < FREEZE_N:
        raise SystemExit(
            f"[freeze] only {len(eligible)} eligible < {FREEZE_N}; generate "
            "the next deterministic batch (task Sec. 12) BEFORE freezing -- "
            "thresholds must NOT be relaxed.")

    chosen = eligible[:FREEZE_N]

    task_path = REPO / config["task_file"]
    record = {
        "schema_version": "raretopo-m1d-benchmark-freeze-v0",
        "parent_tag": config["parent_tag"],
        "parent_commit": config["parent_commit"],
        "h3_tag": config["h3_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "task_sha256": sha256_hex(task_path) if task_path.exists() else None,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rule": {
            **config["freeze_rule"],
            "n_candidates_seen": len(records_by_id),
            "n_eligible_total": len(eligible),
            "batches_consumed": per_batch_summary,
        },
        "benchmark_configs": [
            {
                "config_id": rec["config_id"],
                "params": rec["params"],
                "reference_budget": rec["reference_budget"],
                "modes": rec["modes"],
                "bootstrap_ci": rec["bootstrap_ci"],
                "eligibility": rec["eligibility"],
            }
            for rec in chosen
        ],
        "not_yet_run": {
            "adaptive_policies": "NOT STARTED (Gate D0 requires this freeze first)",
        },
    }
    freeze_json = OUT_DIR / "M1_D_Benchmark_Freeze.json"
    if freeze_json.exists():
        raise SystemExit(f"[freeze] {freeze_json.name} already exists -- "
                         "freeze is immutable (task Sec. 12)")
    freeze_json.write_text(json.dumps(record, indent=1), encoding="utf-8")
    md_path = OUT_DIR / "M1_D_Benchmark_Freeze.md"
    md_path.write_text(_render_md(record), encoding="utf-8")
    print(f"[freeze] FROZEN {len(chosen)} configs -> {freeze_json.name}, "
          f"{md_path.name}")
    for c in chosen:
        e = c["eligibility"]
        print(f"  - {c['config_id']}: kP*={e['k_P_star']} "
              f"kV*={e['k_V_star']} omega_top={e['omega_top_missing']:.3f}")
    return freeze_json, md_path


def _render_md(rec: dict) -> str:
    lines = [
        "# M1-D Frozen Benchmark Set",
        "",
        f"- Frozen at: `{rec['frozen_at_utc']}`",
        f"- Parent tag: `{rec['parent_tag']}` (`{rec['parent_commit']}`)",
        f"- H3 tag: `{rec['h3_tag']}`",
        f"- Task SHA256: `{rec['task_sha256']}`",
        f"- Config SHA256: `{rec['config_sha256']}`",
        f"- Candidates seen: {rec['rule']['n_candidates_seen']} "
        f"(eligible: {rec['rule']['n_eligible_total']})",
        "- Deterministic rule: eligible configs sorted by `config_id` "
        "ascending, first 8 taken; no threshold relaxation "
        "(preregistered task Sec. 12).",
        "",
        "| # | config_id | theta (deg) | h | curved | k*_P | k*_V | "
        "omega_top | tau_PV | inversions |",
        "|---|-----------|-------------|---|--------|------|------|"
        "-----------|--------|------------|",
    ]
    for i, c in enumerate(rec["benchmark_configs"], start=1):
        p = c["params"]
        e = c["eligibility"]
        curved_txt = ",".join(m for m, f in zip(MODE_IDS[1:], p["curved"]) if f)
        inv = len(e["pairwise_inversions"])
        lines.append(
            f"| {i} | `{c['config_id']}` | "
            f"{', '.join(f'{t:.1f}' for t in p['theta_deg'])} | "
            f"{', '.join(f'{h:.2f}' for h in p['h'])} | "
            f"{curved_txt or '-'} | {e['k_P_star']} | {e['k_V_star']} | "
            f"{e['omega_top_missing']:.3f} | {e['kendall_tau_PV']:+.2f} | "
            f"{inv} |")
    lines += [
        "",
        "## Per-mode references (offline benchmark-design oracle)",
        "",
        "| config_id | mode | P_ref | L_ref(q0) | rank_P | rank_L | "
        "P CI95 | L CI95 |",
        "|-----------|------|-------|-----------|--------|--------|"
        "--------|--------|",
    ]
    for c in rec["benchmark_configs"]:
        e = c["eligibility"]
        for mid in MODE_IDS[1:]:
            m = c["modes"][mid]
            ci_p = c["bootstrap_ci"]["P"][mid]
            ci_l = c["bootstrap_ci"]["L"][mid]
            lines.append(
                f"| `{c['config_id']}` | {mid} | {m['P_ref']:.6g} | "
                f"{m['L_ref']:.6g} | {e['rank_P'][mid]} | {e['rank_L'][mid]} | "
                f"[{ci_p[0]:.3g}, {ci_p[1]:.3g}] | "
                f"[{ci_l[0]:.3g}, {ci_l[1]:.3g}] |")
    lines += [
        "",
        "## Status",
        "",
        "- Adaptive policies (probability selector / variance selector / M1 "
        "full policy): **NOT STARTED**.",
        "- This file was generated before any adaptive run (Gate D0).",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="M1-D1/D2 candidate generation")
    ap.add_argument("--stage", choices=["pool", "freeze"], required=True)
    ap.add_argument("--smoke", action="store_true",
                    help="tiny budgets, outputs marked _smoke (sanity only)")
    args = ap.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.smoke:
        config = _smoke_rewrite(config)

    if args.stage == "pool":
        b1 = config["candidate_generation"]["batch_1"]
        run_pool(config, int(b1["seed"]), int(b1["size"]))
    else:
        run_freeze(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
