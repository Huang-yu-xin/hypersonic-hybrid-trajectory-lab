"""M3-G -- offline calibration driver (task Sec. 3 protocol).

Consumes ONLY the STORED M3-D Layer-A batch (results/phase_m3d/layer_a/
m3d_layer_a_v1.json).  HARD INVARIANT: ``extra_simulator_calls == 0`` --
this module's only I/O is reading and writing JSON; no sampling entry
point of the simulator is imported here (the structural test injects
raising stand-ins for the pilot-draw and arm-evaluation entry points of
the frozen pipeline to prove the invariant at runtime).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m3g.metrics import (
    RHO_GRID,
    VARIANT_GRID,
    build_calibration_table,
    per_class_summary,
    per_state_summary,
    select_candidate,
)

LAYER_A_PATH = (Path(__file__).resolve().parents[3] / "results" / "phase_m3d"
                / "layer_a" / "m3d_layer_a_v1.json")
BENCHMARK_FREEZE_SHA256 = \
    "b613f45dc6645c6da26ab58b5185764f14d771ca6b996bffed88fea1f467a5f3"


def load_calibration_batch(path=LAYER_A_PATH) -> dict:
    """Load + validate the stored Layer-A batch (schema, completeness)."""
    path = Path(path)
    batch = json.loads(path.read_text(encoding="utf-8"))
    assert batch["schema_version"] == "raretopo-m3d-layer-a-batch-v0"
    assert (batch["benchmark_freeze_sha256"]
            == BENCHMARK_FREEZE_SHA256), "sealed benchmark hash changed!"
    recs = batch["records"]
    cells = {(r["state_id"], int(r["seed"])) for r in recs}
    assert len(recs) == 192 and len(cells) == 192, "batch incomplete"
    seeds = set(batch["protocol"]["seeds"])
    assert len(seeds) == 8
    return batch


def layer_a_records(batch: dict) -> list[dict]:
    return batch["records"]


def run_offline_calibration(records: list[dict] | None = None,
                            batch_path=None) -> dict:
    """Full preregistered offline calibration -> freeze-ready payload.

    extra_simulator_calls is a hard zero by construction; the returned
    payload carries it plus every candidate row so the freeze artifact can
    be written verbatim from it.
    """
    if records is None:
        batch = load_calibration_batch(batch_path
                                       if batch_path is not None
                                       else LAYER_A_PATH)
        records = batch["records"]
    records = list(records)
    table = build_calibration_table(records)
    selection = select_candidate(table)
    per_state = {}
    per_class = {}
    for v in VARIANT_GRID:
        for rho in RHO_GRID:
            key = f"{v}-{rho}"
            per_state[key] = per_state_summary(records, v, rho)
            per_class[key] = per_class_summary(records, v, rho)
    return {
        "schema_version": "raretopo-m3g-calibration-v0",
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "data_source": str(LAYER_A_PATH),
        "benchmark_freeze_sha256": BENCHMARK_FREEZE_SHA256,
        "n_trials": int(len(records)),
        "rho_grid": [float(x) for x in RHO_GRID],
        "variants": list(VARIANT_GRID),
        "recall_min_each": 0.90,
        "selection_rule": (
            "eligible = WIDEN recall>=0.90 AND SHRINK recall>=0.90; "
            "among eligible maximize accuracy (Acc3); tie-break balanced "
            "accuracy, macro-F1, smaller rho, GA1 before GA2"),
        "extra_simulator_calls": 0,
        "table": table,
        "selection": selection,
        "per_state": per_state,
        "per_class": per_class,
    }


def freeze_payload(calibration: dict, *, task_commit_sha: str,
                   calibration_code_commit: str) -> dict:
    """Compose the calibration-freeze JSON body (handoff Sec. 9 fields)."""
    sel = calibration["selection"]
    return {
        "schema_version": "raretopo-m3g-calibration-freeze-v0",
        "stage": "M3_G_calibration_freeze",
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "parent_tag": {"RareTopo-M3-v0":
                       "32b285625494d9b3da08be3c559db3855df77667",
                       "RareTopo-M3-D-v0":
                       "7bd58c5992615b8579b1814a3a3fcbea3cda9659"},
        "task_commit": task_commit_sha,
        "calibration_code_commit": calibration_code_commit,
        "benchmark_freeze_sha256": calibration["benchmark_freeze_sha256"],
        "data_source": calibration["data_source"],
        "raw_m3d_source_hashes": {
            "layer_a_batch": _sha256_of(Path(calibration["data_source"])),
        },
        "rho_grid": calibration["rho_grid"],
        "variants": calibration["variants"],
        "recall_min_each": calibration["recall_min_each"],
        "selection_rule": calibration["selection_rule"],
        "candidate_results": calibration["table"],
        "per_state_summary": calibration["per_state"],
        "per_class_summary": calibration["per_class"],
        "selection": {
            "selected": sel["selected"],
            "why": sel["why"],
            "winner_row": sel["winner_row"],
            "candidates": sel["candidates"],
        },
        "extra_simulator_calls": calibration["extra_simulator_calls"],
        "immutable_after_commit": (
            "variant and rho are immutable after this freeze commit; "
            "no further tuning allowed"),
    }


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


__all__ = [
    "LAYER_A_PATH", "BENCHMARK_FREEZE_SHA256", "load_calibration_batch",
    "layer_a_records", "run_offline_calibration", "freeze_payload",
]