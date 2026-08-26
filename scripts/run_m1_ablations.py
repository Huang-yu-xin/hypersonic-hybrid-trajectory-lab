"""M1-6 -- Ablations A-E (task Sec. 27) on the H3-1 L2 benchmark.

- Ablation A  No variance geometry: birth by topology probability P_k_hat
              with the same 0.10 threshold (expected FAIL on the
              probability-small variance-dominant S2 -> demonstrates the
              necessity of the variance signal).
- Ablation B  Add without reweight: UPDATE_WEIGHTS disabled; naive split
              weights kept after birth.
- Ablation C  Reweight without birth: component set fixed, only pi updated
              = the "fixed variance-aware mixture" baseline of Benchmark B
              (reused from m1_closed_loop_leakage_v0.json, no new runs).
- Ablation D  Point vs set-valued center: max-weight pilot point vs the
              eta=0.8 variance-region centroid (v0).
- Ablation E  eta sensitivity on the frozen set {0.5, 0.8, 0.9}; main = 0.8.

All ablation runs: 8 preregistered seeds, same pairs as Benchmark B
(mix_50 pilot, 20k/round, <=3 rounds, 100k independent eval).

Output: results/phase_m1/m1_ablation_v0.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1.baselines import Z_STAR, label_h3_1, logp, run_m1_closed_loop
from hyptraj.m1.proposal_update import MixtureProposal

import os

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_SUFFIX = os.environ.get("M1_OUT_SUFFIX", "")
OUT_DIR = REPO / "results" / ("phase_m1" + OUT_SUFFIX)
OUT_PATH = OUT_DIR / "m1_ablation_v0.json"
B_JSON = OUT_DIR / "m1_closed_loop_leakage_v0.json"

SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
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


def run_ablation(config, *, birth_signal="variance", reweight=True,
                 center_method="eta_centroid", eta_main=0.8,
                 weight_mode="m2_opt", pilot_alpha=None,
                 seed_bootstrap_off=0) -> list[dict]:
    out = []
    for seed in SEEDS:
        kw = dict(birth_signal=birth_signal, reweight_after_birth=reweight,
                 center_method=center_method, eta_main=eta_main,
                 weight_mode=weight_mode)
        if pilot_alpha is not None:
            kw["pilot_policy"] = "mix"
            kw["pilot_alpha"] = pilot_alpha
        res = run_m1_closed_loop(seed, ADAPT_PILOT, EVAL_N, config, **kw)
        extra = res.extra
        ev = res.eval
        out.append({
            "seed": seed,
            "stop_reason": extra["stop_reason"],
            "births": extra["births"],
            "M2_hat": ev["M2_hat"],
            "P_hat": ev["P_hat"],
            "n_components": len(extra["final_components"]),
            "final_weights": extra["final_weights"],
            "adaptation_calls": res.adaptation_calls,
            "weight": (extra["iterations"][0].get("weight")
                       if extra["iterations"] else None),
        })
    return out


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    t0 = time.perf_counter()

    abl_a = run_ablation(config, birth_signal="probability")
    # Issue 4 comparator: threshold-free top-ranked probability signal with
    # probability-only internals (no variance geometry anywhere)
    abl_a_top = run_ablation(config, birth_signal="probability_top",
                             center_method="probability_centroid",
                             weight_mode="probability")
    abl_b = run_ablation(config, reweight=False)
    abl_d = run_ablation(config, center_method="max_weight_point")
    abl_e = {str(eta): run_ablation(config, eta_main=eta)
             for eta in (0.5, 0.8, 0.9)}

    # Ablation C: reuse the fixed variance-aware baseline from Benchmark B
    b_data = json.loads(B_JSON.read_text(encoding="utf-8"))
    abl_c = [{"seed": SEEDS[i],
              "M2_hat": b_data["per_seed"][i]["fixed_variance_aware_mixture"]["M2_hat"],
              "P_hat": b_data["per_seed"][i]["fixed_variance_aware_mixture"]["P_hat"],
              "n_components": 2} for i in range(len(SEEDS))]
    m1_ref = [s["m1_closed_loop"]["M2_hat"] for s in b_data["per_seed"]]
    q0_ref = [s["single_geometry_q0"]["M2_hat"] for s in b_data["per_seed"]]

    m1_main = [s["m1_closed_loop"] for s in b_data["per_seed"]]

    def _med(x):
        return float(np.median(np.asarray(x, dtype=float)))

    summary = {
        "m1_main_M2_median": _med(m1_ref),
        "m1_main_births": sum(1 for s in m1_main if s["extra"]["births"] == ["S2"]),
        "ablation_A": {
            "question": "probability signal sufficient to replace variance signal?",
            "births": [r["births"] for r in abl_a],
            "n_births": sum(1 for r in abl_a if r["births"]),
            "M2_median": _med([r["M2_hat"] for r in abl_a]),
            "conclusion": "correct P_k_hat(S2) ~ 6e-3 still << 0.10 -> the "
                          "variance signal is necessary to gate birth by "
                          "variance importance",
        },
        "ablation_A2_probability_top_comparator": {
            "question": "threshold-free top-ranked probability comparator "
                        "(no variance geometry anywhere): what does it do?",
            "births": [r["births"] for r in abl_a_top],
            "n_births": sum(1 for r in abl_a_top if r["births"]),
            "M2_median": _med([r["M2_hat"] for r in abl_a_top]),
            "center": "probability centroid (IS-weight p/r)",
            "weights": "normalized P_k_hat",
            "note": "top-ranked comparator always picks the only unrepresented "
                    "mode when observed -- it cannot rank by variance "
                    "importance; M2 outcome reported as-is",
        },
        "ablation_B": {
            "question": "improvement from component coverage or weight optimization?",
            "M2_median_no_reweight": _med([r["M2_hat"] for r in abl_b]),
            "M2_median_main": _med(m1_ref),
            "n_births": sum(1 for r in abl_b if r["births"]),
        },
        "ablation_C": {
            "question": "can weight-only updates fix a truly missing mode?",
            "M2_median_fixed_weights_only": _med([r["M2_hat"] for r in abl_c]),
            "M2_median_main": _med(m1_ref),
            "note": "component set GIVEN (S1,S2 MPPs); only pi optimized "
                    "(SLSQP) -> equals Benchmark B fixed_variance_aware",
        },
        "ablation_D": {
            "question": "does the set-valued eta centroid improve stability vs single point?",
            "M2_median_max_weight_point": _med([r["M2_hat"] for r in abl_d]),
            "M2_median_eta_centroid": _med(m1_ref),
            "births_point": [r["births"] for r in abl_d],
            "n_births_point": sum(1 for r in abl_d if r["births"]),
        },
        "ablation_E": {
            "question": "eta sensitivity (frozen set 0.5/0.8/0.9, main 0.8)",
            "M2_median": {eta: _med([r["M2_hat"] for r in runs])
                          for eta, runs in abl_e.items()},
        },
    }

    record = {
        "schema_version": "raretopo-m1-ablation-v0",
        "config_id": config["config_id"],
        "h3_frozen_tag": config["h3_frozen_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark": "B_h3_1_leakage (ablation variants)",
        "runs": {"A_probability_gate": abl_a,
                 "A2_probability_top_comparator": abl_a_top,
                 "B_add_no_reweight": abl_b,
                 "C_reweight_no_birth_fixed": abl_c,
                 "D_max_weight_point": abl_d, "E_eta_sensitivity": abl_e},
        "summary": summary,
        "total_wall_time_s": time.perf_counter() - t0,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())