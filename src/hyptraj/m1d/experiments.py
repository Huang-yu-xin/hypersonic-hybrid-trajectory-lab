"""M1-D -- experiment assembly utilities (drivers share these).

Only DRIVER-layer code imports reference tables (from the frozen benchmark
freeze artifact); policy modules stay blind to them (Sec. 41).
"""

from __future__ import annotations

import json
from pathlib import Path

from hyptraj.m1d.benchmark_family import DIM, MODE_IDS, BenchmarkConfig
from hyptraj.m1d.metrics import (
    MISSING,
    attach_vrfs,
    cps_of,
    cvs_of,
    eval_proposal_is,
)

REPO = Path(__file__).resolve().parents[3]
FREEZE_JSON = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"
SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]


def load_freeze(path: Path | None = None) -> dict:
    return json.loads((path or FREEZE_JSON).read_text(encoding="utf-8"))


def config_from_record(rec: dict) -> BenchmarkConfig:
    p = rec["params"]
    cid = rec["config_id"]
    bs = int(rec.get("batch_seed", cid.split("_b")[1].split("_c")[0]))
    bi = int(rec.get("batch_index", cid.split("_c")[1]))
    return BenchmarkConfig(
        config_id=cid,
        batch_seed=bs,
        batch_index=bi,
        theta_deg=tuple(p["theta_deg"]),
        h=tuple(p["h"]),
        curved=tuple(bool(c) for c in p["curved"]),
        curvature_c=float(p["curvature_c"]),
        offset_o=tuple(p["offset_o"]),
    )


def ref_views(freeze_rec: dict) -> dict:
    """Reference tables of ONE frozen config (missing modes only)."""
    P = {mid: float(freeze_rec["modes"][mid]["P_ref"]) for mid in MISSING}
    L = {mid: float(freeze_rec["modes"][mid]["L_ref"]) for mid in MISSING}
    return {
        "P": P,
        "L": L,
        "order_P": sorted(MISSING, key=lambda m: P[m], reverse=True),
        "order_V": sorted(MISSING, key=lambda m: L[m], reverse=True),
    }


def choose_freeze(eligible_ids: list[str], n: int = 8) -> list[str]:
    """Frozen Sec. 12 rule: sort eligible by config_id ascending, take n.

    Raises BEFORE any relaxation if fewer than n are available -- callers
    must generate the next deterministic batch instead.
    """
    ordered = sorted(eligible_ids)
    if len(ordered) < n:
        raise RuntimeError(
            f"only {len(ordered)} eligible < {n}; next deterministic batch "
            "required BEFORE freezing (task Sec. 12; thresholds NOT relaxed)")
    return ordered[:n]


def make_record(*, batch_dir: str, parent_freeze_sha: str,
                bench_cfg: BenchmarkConfig, rv: dict,
                budget_total_declared: int, core: dict) -> dict:
    """Full Sec. 37 machine-readable record for one trial.

    ``rv`` is used ONLY here (offline metric attachment) -- never inside the
    policy pathway.  ``p_event_ref`` = reference event probability restricted
    to the missing-mode union; identical denominator across every method on
    a config keeps VRF / ratio statements paired.
    """
    proposal = core.pop("final_proposal")
    evaluation = eval_proposal_is(proposal, bench_cfg, int(core["seed"]),
                                  n_eval=int(core["controls"]["n_eval"]))
    attach_vrfs(evaluation,
                p_ref=float(sum(rv["P"].values())),
                budget_total=int(budget_total_declared))

    selected = list(core.get("selected_modes", []))
    k_v_star = rv["order_V"][0]
    cvs = cvs_of(selected, rv["L"])
    cps = cps_of(selected, rv["P"])
    for b in range(1, len(selected) + 1):
        core[f"CVS_{b}"] = float(cvs_of(selected[:b], rv["L"]))
        core[f"CPS_{b}"] = float(cps_of(selected[:b], rv["P"]))

    return {
        "schema_version": "raretopo-m1d-v0",
        "record_kind": batch_dir,
        "parent_tag": "RareTopo-M1-v0",
        "h3_tag": "RareTopo-H3-v1.0",
        "benchmark_freeze_hash": parent_freeze_sha,
        "config_id": bench_cfg.config_id,
        "seed": int(core["seed"]),
        "birth_budget": int(core["birth_budget"]),
        "method": str(core["method"]),
        "pilot": {"n": core["controls"]["n_pilot"],
                  "alpha_p": core["controls"]["alpha"]},
        "mode_estimates": [
            {"round": r["round"], **({"selected": r["selected"]}
                                     if "selected" in r else {}),
             **r.get("selection_diag", {})}
            for r in core.get("rounds", [])],
        "selected_modes": selected,
        "selection_metrics": {
            "top1_variance_correct": bool(selected and selected[0] == k_v_star),
            "captured_variance_share": float(cvs),
            "captured_probability_share": float(cps),
            **{k: v for k, v in core.items() if k.startswith(("CVS_", "CPS_"))},
        },
        "evaluation": evaluation,
        "stop_reason": core.get("stop_reason"),
        "rounds": core.get("rounds", []),
        "cost": core.get("cost", {}),
        "controls": core.get("controls", {}),
        "validity": core.get("validity", {}),
    }


__all__ = ["load_freeze", "config_from_record", "ref_views", "choose_freeze",
           "make_record", "SEEDS", "MISSING", "MODE_IDS", "DIM"]
