"""M1-4 -- Benchmark B: closed-loop variance-geometry adaptive IS on H3-1 L2.

Full preregistered comparison on the H3-1 L2 benchmark (frozen semantics):

methods (task Sec. 21, oracle levels Sec. 22): crude MC / single Geometry-IS
q0 / H3-2 M2 topology-aware mixture / H3-2 M3 leakage-point mixture (hand
designed oracle) / fixed variance-aware mixture (weights only) / M1
closed-loop (Discover + Add + Reweight, mix_50 pilot) / CEM.

Gates (task Sec. 25, paired same-seed comparisons):
- Gate 2 Leakage: >= 7/8 seeds L_S2(q_final) < L_S2(q0); median ratio <= 0.5
- Gate 3 M2:      >= 7/8 seeds M2(q_final) < M2(q0); median ratio <= 0.5
- Gate 4 Oracle:  median M2(M1)/M2(M3) <= 1.10 (competitive); < 1 strong
- Gate 5 Budget:  median VRF_budget > 1 (+ 8-seed success count)
Then the task Sec. 34 interpretation matrix.

Budget: B = 160,000 calls/seed.  Adaptive methods: 3 x 20,000 adaptation +
100,000 final eval; non-adaptive: 160,000 direct eval; fixed variance-aware:
20,000 weight-fit + 140,000 eval.  Final eval always drawn from the frozen
final proposal (r = q_final), generated after freezing (Sec. 18).

Outputs: results/phase_m1/m1_closed_loop_leakage_v0.json
         results/phase_m1/m1_baseline_comparison_v0.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1.baselines import (
    TRUE_LEAK,
    BaselineResult,
    label_h3_1,
    logp,
    run_cem,
    run_fixed_variance_aware,
    run_h3_2_m2,
    run_h3_2_m3,
    run_m1_closed_loop,
    run_mc,
    run_single_geometry,
    vrf_budget,
    vrf_proposal,
)

import os

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_SUFFIX = os.environ.get("M1_OUT_SUFFIX", "")
OUT_DIR = REPO / "results" / ("phase_m1" + OUT_SUFFIX)
OUT_LEAK = OUT_DIR / "m1_closed_loop_leakage_v0.json"
OUT_BASE = OUT_DIR / "m1_baseline_comparison_v0.json"

SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
BUDGET = 160_000
ADAPT_ROUNDS = 3
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


ORACLE_TABLE = {
    "crude_mc": {"secondary_known": False, "leakage_geometry_known": False,
                 "online_adaptation": False},
    "single_geometry_q0": {"secondary_known": False, "leakage_geometry_known": False,
                           "online_adaptation": False},
    "h3_2_m2_topology_mixture": {"secondary_known": True, "leakage_geometry_known": False,
                                 "online_adaptation": False},
    "h3_2_m3_leakage_mixture": {"secondary_known": True, "leakage_geometry_known": True,
                                "online_adaptation": False},
    "fixed_variance_aware_mixture": {"secondary_known": True,
                                     "leakage_geometry_known": "geometry_fixed",
                                     "online_adaptation": "weight_only"},
    "m1_closed_loop": {"secondary_known": False, "leakage_geometry_known": False,
                       "online_adaptation": True},
    "cross_entropy": {"secondary_known": False, "leakage_geometry_known": False,
                      "online_adaptation": True},
}


def run_all_seed(seed: int, config, p_mc_ref: float) -> dict:
    """Run every method on one seed; paired same-seed statistics."""
    out: dict = {}
    mc = run_mc(seed, BUDGET)
    single = run_single_geometry(seed, BUDGET)
    m2 = run_h3_2_m2(seed, BUDGET)
    m3 = run_h3_2_m3(seed, BUDGET)
    fixed = run_fixed_variance_aware(seed, ADAPT_PILOT, BUDGET - ADAPT_PILOT)
    m1 = run_m1_closed_loop(seed, ADAPT_PILOT, EVAL_N, config)
    cem = run_cem(seed, ADAPT_ROUNDS, ADAPT_PILOT, EVAL_N)

    for r in (mc, single, m2, m3, fixed, m1, cem):
        ev = r.eval
        vrf_prop = vrf_proposal(p_mc_ref, ev["n_eval"], ev["var_hat"])
        out[r.method] = {
            **ev,
            "adaptation_calls": r.adaptation_calls,
            "total_calls": r.total_calls,
            "VRF_proposal": float(vrf_prop),
            "VRF_budget": vrf_budget(p_mc_ref, BUDGET, ev["M2_hat"],
                                     ev["P_hat"], ev["n_eval"]),
            "extra": r.extra,
        }
    return out


def compute_gates(rows: list[dict]) -> dict:
    """Paired gates across 8 preregistered seeds (task Sec. 25)."""
    n = len(rows)
    l_ratio = [r["m1_closed_loop"]["L_S2"] / r["single_geometry_q0"]["L_S2"]
               for r in rows]
    m2_ratio = [r["m1_closed_loop"]["M2_hat"] / r["single_geometry_q0"]["M2_hat"]
                for r in rows]
    oracle_ratio = [r["m1_closed_loop"]["M2_hat"] / r["h3_2_m3_leakage_mixture"]["M2_hat"]
                    for r in rows]
    vrf_budget = [r["m1_closed_loop"]["VRF_budget"] for r in rows]

    def med(x):
        return float(np.median(np.asarray(x, dtype=float)))

    gate2 = {
        "n_reduced": sum(1 for x in l_ratio if x < 1.0),
        "median_ratio": med(l_ratio), "ratios": l_ratio,
        "pass": sum(1 for x in l_ratio if x < 1.0) >= 7 and med(l_ratio) <= 0.5,
    }
    gate3 = {
        "n_reduced": sum(1 for x in m2_ratio if x < 1.0),
        "median_ratio": med(m2_ratio), "ratios": m2_ratio,
        "pass": sum(1 for x in m2_ratio if x < 1.0) >= 7 and med(m2_ratio) <= 0.5,
    }
    gate4 = {
        "competitive_pass": med(oracle_ratio) <= 1.10,
        "strong_pass": med(oracle_ratio) < 1.0,
        "median_ratio_M1_over_M3": med(oracle_ratio), "ratios": oracle_ratio,
    }
    gate5 = {
        "median_vrf_budget": med(vrf_budget),
        "n_above_one": sum(1 for x in vrf_budget if x > 1.0),
        "values": vrf_budget,
        "pass": med(vrf_budget) > 1.0,
    }
    return {"gate2_leakage": gate2, "gate3_second_moment": gate3,
            "gate4_oracle_gap": gate4, "gate5_budget": gate5, "n_seeds": n}


def interpretation_matrix(g: dict) -> dict:
    """task Sec. 34 matrix row for the observed gate pattern."""
    d, lk, m2, cost = (
        True, g["gate2_leakage"]["pass"], g["gate3_second_moment"]["pass"],
        g["gate5_budget"]["pass"],
    )
    if not d:
        return {"discovery": "Pass", "leakage": lk, "m2": m2, "cost": cost,
                "interpretation": "variance geometry 尚不能稳定驱动 mode discovery"}
    if lk and m2 and cost and g["gate4_oracle_gap"]["strong_pass"]:
        return {"discovery": "Pass", "leakage": lk, "m2": m2, "cost": cost,
                "interpretation": "strong method result (beats M3 oracle)"}
    if lk and m2 and cost:
        return {"discovery": "Pass", "leakage": lk, "m2": m2, "cost": cost,
                "interpretation": "核心 M1 方法链成立"}
    if lk and m2:
        return {"discovery": "Pass", "leakage": lk, "m2": m2, "cost": cost,
                "interpretation": "机制成立，但 adaptation overhead 暂不经济"}
    if lk:
        return {"discovery": "Pass", "leakage": lk, "m2": m2, "cost": cost,
                "interpretation": "局部 leakage 被修复，但 variance 转移到其他 region/mode"}
    return {"discovery": "Pass", "leakage": lk, "m2": m2, "cost": cost,
            "interpretation": "diagnosis 有效，action design 无效"}


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    t0 = time.perf_counter()

    # common probability reference from the 160k MC run of seed 2026
    mc_ref = run_mc(SEEDS[0], BUDGET)
    p_mc_ref = mc_ref.eval["P_hat"]

    rows = [run_all_seed(seed, config, p_mc_ref) for seed in SEEDS]
    gates = compute_gates(rows)
    matrix = interpretation_matrix(gates)

    summary = {
        "p_mc_ref": float(p_mc_ref),
        "budget_per_seed": BUDGET,
        "median_M2": {m: float(np.median([r[m]["M2_hat"] for r in rows]))
                      for m in ORACLE_TABLE},
        "median_VRF_proposal": {
            m: float(np.median([r[m]["VRF_proposal"] for r in rows]))
            for m in ORACLE_TABLE},
        "median_VRF_budget": {
            m: float(np.median([r[m]["VRF_budget"] for r in rows]))
            for m in ORACLE_TABLE},
        "median_L_S2": {m: float(np.median([r[m]["L_S2"] for r in rows]))
                        for m in ORACLE_TABLE},
    }

    record = {
        "schema_version": "raretopo-m1-benchmark-b-v0",
        "config_id": config["config_id"],
        "h3_frozen_tag": config["h3_frozen_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark": "B_h3_1_leakage_closed_loop",
        "benchmark_definition": {
            "source": "H3-1 L2_synthetic_multi_mode (frozen semantics)",
            "d": 4, "q0": "N(-1.5 e1, I)", "nominal": "S0",
            "A1": {"label": "S1", "condition": "u1 < -1.5"},
            "A2": {"label": "S2", "condition": "u1 > 2.5"},
            "analytic_leak_s1": TRUE_LEAK[0], "analytic_leak_s2": TRUE_LEAK[1],
        },
        "pilot_policy": config["pilot_policy"],
        "budget": {"B": BUDGET, "adapt_rounds": ADAPT_ROUNDS,
                   "adapt_pilot": ADAPT_PILOT, "final_eval": EVAL_N},
        "oracle_table": ORACLE_TABLE,
        "per_seed": rows,
        "gates": gates,
        "summary": summary,
        "interpretation_matrix": matrix,
        "total_wall_time_s": time.perf_counter() - t0,
    }
    OUT_LEAK.parent.mkdir(parents=True, exist_ok=True)
    OUT_LEAK.write_text(json.dumps(record, indent=2), encoding="utf-8")

    comparison = {
        "schema_version": "raretopo-m1-baseline-comparison-v0",
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "p_mc_ref": p_mc_ref,
        "oracle_table": ORACLE_TABLE,
        "summary": summary,
        "per_seed": [
            {"seed": SEEDS[i], "methods": rows[i]} for i in range(len(rows))],
    }
    OUT_BASE.write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    print(json.dumps({
        "gates": {k: ({kk: vv for kk, vv in v.items() if kk != "ratios"}
                      if isinstance(v, dict) else v)
                  for k, v in gates.items()},
        "interpretation": matrix["interpretation"],
        "median_M2": summary["median_M2"],
        "median_VRF_budget": summary["median_VRF_budget"],
        "outputs": [str(OUT_LEAK), str(OUT_BASE)],
    }, indent=2))
    ok = gates["gate2_leakage"]["pass"] and gates["gate3_second_moment"]["pass"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())