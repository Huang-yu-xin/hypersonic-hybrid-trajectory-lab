"""M1 semantic audit -- Issue 5: exploration fraction sensitivity.

alpha = P(pilot source = p).  Frozen main config: alpha = 0.5 (config
``pilot_policy.mix_50``).  This is an EXPLANATORY experiment -- it does NOT
replace the main configuration and no alpha is "selected" afterwards.

Runs the preregistered seed set [2026..2033] for each alpha in
{0.00, 0.10, 0.25, 0.50, 0.75, 1.00} at the frozen pilot budget (20k/round,
<= 3 rounds, 100k independent eval; total nominal budget 160k).

Answers: how sensitive is closed-loop discovery to the exploration
fraction?  Expected: alpha = 0 (q-only) cannot observe the far
variance-dominant mode (P(S2|q0) = 3.2e-5 -> ~0.6 observations), so the
failed proposal cannot discover unseen modes from its own samples alone --
the discovery requires explicit exploration; variance geometry decides
which OBSERVED modes are variance-important and how to adapt.

Output: results/phase_m1_semantic_fix/m1_exploration_sensitivity_v0.json
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1.baselines import run_m1_closed_loop, run_mc, vrf_budget, vrf_proposal

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_PATH = REPO / "results" / "phase_m1_semantic_fix" / "m1_exploration_sensitivity_v0.json"

SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
ALPHAS = [0.00, 0.10, 0.25, 0.50, 0.75, 1.00]
ADAPT_PILOT = 20_000
EVAL_N = 100_000


def git_short_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=REPO, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    p_mc_ref = run_mc(SEEDS[0], 160_000).eval["P_hat"]
    per_alpha: dict[str, list[dict]] = {}
    summary: dict[str, dict] = {}
    for alpha in ALPHAS:
        runs = []
        for seed in SEEDS:
            res = run_m1_closed_loop(
                seed, ADAPT_PILOT, EVAL_N, config,
                pilot_policy="mix", pilot_alpha=alpha,
            )
            extra, ev = res.extra, res.eval
            runs.append({
                "seed": seed,
                "births": extra["births"],
                "n_components": len(extra["final_components"]),
                "final_weights": extra["final_weights"],
                "M2_hat": ev["M2_hat"],
                "P_hat": ev["P_hat"],
                "L_S2": ev["L_S2"],
                "omega_S2": ev["omega_S2_hat"],
                "adaptation_calls": res.adaptation_calls,
                "total_calls": res.total_calls,
                "VRF_proposal": vrf_proposal(p_mc_ref, ev["n_eval"], ev["var_hat"]),
                "VRF_budget": vrf_budget(p_mc_ref, 160_000, ev["M2_hat"],
                                         ev["P_hat"], ev["n_eval"]),
                "stop_reason": extra["stop_reason"],
            })
        per_alpha[f"{alpha:.2f}"] = runs
        n_ok = sum(1 for r in runs if r["births"] == ["S2"])
        n_wrong = sum(1 for r in runs if r["births"] not in ([], ["S2"]))
        summary[f"{alpha:.2f}"] = {
            "alpha": alpha,
            "discovery_count": n_ok,
            "false_birth_count": n_wrong,
            "median_M2": float(np.median([r["M2_hat"] for r in runs])),
            "median_L_S2": float(np.median([r["L_S2"] for r in runs])),
            "median_adaptation_calls": int(np.median(
                [r["adaptation_calls"] for r in runs])),
            "median_total_calls": int(np.median([r["total_calls"] for r in runs])),
            "n_S2_last_seed": runs[-1]["births"] and "births-recorded" or "none",
        }

    record = {
        "schema_version": "raretopo-m1-exploration-sensitivity-v0",
        "semantic_fix_version": "m1-v0-semantic-fix-1",
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "h3_frozen_tag": config["h3_frozen_tag"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark": "B_h3_1_leakage",
        "alphas": ALPHAS,
        "main_config_alpha": 0.5,
        "note": "explanatory experiment; alpha=0.5 stays the preregistered main "
                "configuration; no alpha is selected post-hoc.",
        "budget": {"pilot_per_round": ADAPT_PILOT, "max_rounds": 3,
                   "final_eval": EVAL_N},
        "runs_per_alpha": per_alpha,
        "summary_per_alpha": summary,
        "total_wall_time_s": time.perf_counter() - t0,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({
        "alpha": {a: {k: v for k, v in s.items() if k != "n_S2_last_seed"}
                  for a, s in summary.items()},
        "output": str(OUT_PATH),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())