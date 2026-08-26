"""M1-D -- execution driver for preregistered stages D5/D6/D7/D8 (task Sec. 42).

Stages
------
d1a   Layer A, one-birth challenge  -> results/phase_m1d/d1_selection_only/
d1b   Layer B full policies         -> results/phase_m1d/d1_full_policy/
d2    two-birth challenge (both)    -> results/phase_m1d/d2_two_birth/
abl   Ablations D-C / D-D cells     -> results/phase_m1d/ablations/
      (D-A oracle-ranking table is derived at gate-audit time; D-E is the
       d1-vs-d2 contrast itself.)

All stage parameters live in configs/phase_m1d/m1d_d{1,2}_*.json; this
script only orchestrates and never relaxes a protocol constant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m1d.experiments import (
    SEEDS,
    config_from_record,
    load_freeze,
    make_record,
    ref_views,
)
from hyptraj.m1d.layer_a import METHODS, run_layer_a_trial

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "phase_m1d"
FREEZE_SHA = hashlib.sha256(
    (REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json")
    .read_bytes()).hexdigest()

PN = 20_000
EVAL_N = 100_000


def _trial_total(core: dict) -> int:
    return int(core["cost"]["total_calls"])


def _stage_meta(stage: str) -> dict:
    return {
        "schema_version": "raretopo-m1d-batch-v0",
        "benchmark_freeze_hash": FREEZE_SHA,
        "git_commit": _git_head(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": {"n_pilot": PN, "alpha_p": 0.5, "n_eval": EVAL_N,
                     "seeds": SEEDS},
        "stage": stage,
    }


def _git_head() -> str:
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _save(batch: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    print(f"[saved] {path.relative_to(REPO)} "
          f"({len(batch.get('records', []))} trials)", flush=True)


def _iter_frozen():
    for rec in load_freeze()["benchmark_configs"]:
        yield rec, config_from_record(rec), ref_views(rec)


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------
def run_layer_a(birth_budget: int, out_dir: str, fname: str,
                methods=None, center_rule: str = "probability",
                weight_rule: str = "m2_opt") -> list[dict]:
    rows_all: list[dict] = []
    for frec, bc, rv in _iter_frozen():
        t0 = time.perf_counter()
        records = []
        for m in (methods or METHODS):
            for seed in SEEDS:
                core = run_layer_a_trial(
                    bc, seed, m, birth_budget=birth_budget,
                    n_pilot=PN, alpha=0.5, n_eval=EVAL_N,
                    center_rule=center_rule, weight_rule=weight_rule,
                    oracle_orders={"P": rv["order_P"], "V": rv["order_V"]})
                rec = make_record(
                    batch_dir=out_dir, parent_freeze_sha=FREEZE_SHA,
                    bench_cfg=bc, rv=rv,
                    budget_total_declared=_trial_total(core), core=core)
                records.append(rec)
        print(f"  [{bc.config_id}] {len(records)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        rows_all.append({"config_id": bc.config_id, "records": records})
    return rows_all


def stage_d1a() -> None:
    rows = run_layer_a(1, "d1_selection_only", "")
    meta = _stage_meta("d1a_layer_A_one_birth")
    meta["records_by_config"] = rows
    _save(meta, RESULTS / "d1_selection_only" / "layer_a_one_birth_v1.json")


def _run_layer_b_batch(bc, rv, birth_budget: int) -> list[dict]:
    from hyptraj.m1d.layer_a import run_layer_b_trial
    records = []
    for variant in ("variance", "probability"):
        for seed in SEEDS:
            core = run_layer_b_trial(bc, seed, variant,
                                     birth_budget=birth_budget,
                                     n_pilot=PN, pilot_alpha=0.5,
                                     n_eval=EVAL_N)
            rec = make_record(
                batch_dir=f"d{'1' if birth_budget == 1 else '2'}_full_policy"
                          if birth_budget == 1 else "d2_two_birth",
                parent_freeze_sha=FREEZE_SHA, bench_cfg=bc, rv=rv,
                budget_total_declared=_trial_total(core), core=core)
            records.append(rec)
    return records


def stage_d1b() -> None:
    rows = []
    for frec, bc, rv in _iter_frozen():
        t0 = time.perf_counter()
        recs = _run_layer_b_batch(bc, rv, birth_budget=1)
        print(f"  [{bc.config_id}] {len(recs)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        rows.append({"config_id": bc.config_id, "records": recs})
    meta = _stage_meta("d1b_layer_B_full_policy")
    meta["records_by_config"] = rows
    _save(meta, RESULTS / "d1_full_policy" / "layer_b_one_birth_v1.json")


def stage_d2() -> None:
    rows_a = run_layer_a(2, "d2_two_birth", "")
    meta = _stage_meta("d2_two_birth_layer_A")
    meta["records_by_config"] = rows_a
    _save(meta, RESULTS / "d2_two_birth" / "layer_a_two_birth_v1.json")

    rows_b = []
    for frec, bc, rv in _iter_frozen():
        t0 = time.perf_counter()
        recs = _run_layer_b_batch(bc, rv, birth_budget=2)
        print(f"  [d2b {bc.config_id}] {len(recs)} trials "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        rows_b.append({"config_id": bc.config_id, "records": recs})
    meta = _stage_meta("d2_two_birth_layer_B")
    meta["records_by_config"] = rows_b
    _save(meta, RESULTS / "d2_two_birth" / "layer_b_two_birth_v1.json")


def stage_abl() -> None:
    """Cells: selectors x {center=variance_hdr, weight=probability}."""
    jobs = [
        ("center_variance_hdr",
         dict(center_rule="variance_hdr"),
         ["probability_selector", "variance_selector"]),
        ("weight_probability",
         dict(weight_rule="probability"),
         ["probability_selector", "variance_selector"]),
    ]
    meta = _stage_meta("d8_ablations_DC_DD")
    meta["cells"] = []
    for cell_name, kw, methods in jobs:
        rows = run_layer_a(1, "ablations", "", methods=methods, **kw)
        meta["cells"].append({"cell": cell_name, **kw,
                              "records_by_config": rows})
        _save({**_stage_meta(f"abl_{cell_name}"), "records_by_config": rows},
              RESULTS / "ablations" / f"{cell_name}_v1.json")
    # master meta saved at end for convenience
    _save(meta, RESULTS / "ablations" / "ablations_master_v1.json")


STAGES = {"d1a": lambda: stage_d1a(), "d1b": lambda: stage_d1b(),
          "d2": lambda: stage_d2(), "abl": lambda: stage_abl()}


def main() -> int:
    ap = argparse.ArgumentParser(description="M1-D experiments D5-D8")
    ap.add_argument("--stage", choices=list(STAGES), required=True)
    args = ap.parse_args()
    t0 = time.perf_counter()
    STAGES[args.stage]()
    print(f"[stage {args.stage}] done in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
