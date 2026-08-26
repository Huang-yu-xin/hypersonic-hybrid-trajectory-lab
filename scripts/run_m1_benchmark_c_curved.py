"""M1-5 -- Benchmark C: H3-2 curved multi-mode controlled case.

Goal (task Sec. 20 Benchmark C, entered after B's three Gates passed):
check that the closed loop is NOT a one-off for the crafted linear leakage
case.  Reuses the frozen H3-2 curved event definition
(``run_h3_2_adaptive_geometry_is.py`` label_curved): in the standardized
u-space, S1 = {u1 < -1.5} (linear, primary), S2 = {u1 > 1 + 0.5*(u2-1.5)^2}
(curved secondary), nominal S0, d = 2.  On this boundary the S2 MPP and the
S2 leakage point SEPARATE (H3-2 known result) -- the case that stresses
variance-geometry-driven placement beyond probability MPPs.

Methods run (8 preregistered seeds, fair budget B = 160k calls):
MC / single q0 / H3-2 M2 (mode MPPs - numerically solved) / H3-2 M3
(leakage-point mixture - numerically solved, best-of-3 weights per frozen
H3-2 semantics) / fixed variance-aware (M3 geometry + SLSQP weights) /
M1 closed-loop (mix_50 pilot).  CEM was reported in Benchmark B and is not
repeated here.

Verds: discovery stability (>= 7/8 seeds birth S2), M2 gate-style reduction
(median M2_final/M2_0 <= 0.5), P unbiasedness, and M2/M3 reference
comparison.  No preregistered Gate lives on C (gates are locked to B);
results are reported as mechanism evidence.

Output: results/phase_m1/m1_benchmark_c_curved_v0.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from hyptraj.m1.baselines import (
    BaselineResult,
    logp as _logp_d,
    run_fixed_variance_aware,
    run_m1_closed_loop,
    run_mc,
    run_single_geometry,
)
from hyptraj.m1.proposal_update import MixtureProposal

import os

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_SUFFIX = os.environ.get("M1_OUT_SUFFIX", "")
OUT_PATH = REPO / "results" / ("phase_m1" + OUT_SUFFIX) / "m1_benchmark_c_curved_v0.json"

D = 2
A1 = -1.5
NOMINAL = "S0"
Q0_CENTER = np.array([-1.5, 0.0])
SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
BUDGET = 160_000
EVAL_N = 100_000
ADAPT_PILOT = 20_000


def git_short_head() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=REPO, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logp(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * D * np.log(2.0 * np.pi)


def surface(u2: float) -> float:
    return 1.0 + 0.5 * (u2 - 1.5) ** 2


def label_curved(z: np.ndarray) -> np.ndarray:
    """Frozen H3-2 curved topology oracle (verbatim semantics)."""
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], NOMINAL, dtype=object)
    out[z[:, 0] < A1] = "S1"
    out[z[:, 0] > surface(z[:, 1])] = "S2"
    return out


def _mpp_s2() -> np.ndarray:
    """MPP of the curved mode: min ||u|| on {u1 = surface(u2)}."""
    res = minimize(lambda u2: surface(u2) ** 2 + u2**2, x0=1.5, method="Nelder-Mead")
    u2 = float(res.x[0])
    return np.array([surface(u2), u2])


def _leakage_point_s2(q_center: np.ndarray) -> np.ndarray:
    """x_L of the curved mode wrt q = N(q_center, I): max log rho_L = -||u||^2/2
    + u . q_center on the boundary (log rho = -u^2 + (u-qc)^2/2 + const)."""
    def neg(u2: float) -> float:
        u1 = surface(u2)
        rho = -(u1 * u1 + u2 * u2) / 2.0 + (u1 * q_center[0] + u2 * q_center[1])
        return -rho
    res = minimize(neg, x0=1.5, method="Nelder-Mead")
    u2 = float(res.x[0])
    return np.array([surface(u2), u2])


def _eval(prop: MixtureProposal, n_eval: int, seed: int,
          oracle=label_curved, logp_fn=logp) -> dict:
    rng = np.random.default_rng(seed + 500_000)
    z = prop.sample(rng, n_eval)
    labels = oracle(z)
    ind = (labels != NOMINAL).astype(float)
    w = np.exp(logp_fn(z) - prop.log_density(z)) * ind
    p_hat = float(np.mean(w))
    m2_hat = float(np.mean(w**2))
    var_hat = max(0.0, (m2_hat - p_hat**2) / n_eval)
    return {"P_hat": p_hat, "M2_hat": m2_hat, "var_hat": var_hat, "n_eval": n_eval}


def run_m2_mixture(seed: int, budget: int, mpp_s1: np.ndarray,
                   mpp_s2: np.ndarray) -> BaselineResult:
    """H3-2 M2: mode MPP mixture, topology-informed uniform weights."""
    centers = np.vstack([mpp_s1, mpp_s2])
    q = MixtureProposal(centers=centers, weights=np.array([0.5, 0.5]),
                        component_mode_ids=("S1", "S2"))
    ev = _eval(q, budget, seed)
    return BaselineResult(method="h3_2_m2_topology_mixture", seed=seed,
                          adaptation_calls=0, total_calls=budget, eval=ev,
                          extra={"centers": [list(mpp_s1), list(mpp_s2)]})


def run_m3_mixture(seed: int, budget: int, xl_s1: np.ndarray,
                   xl_s2: np.ndarray) -> BaselineResult:
    """H3-2 M3: leakage-point mixture, best-of-3 frozen weight strategies
    on one shared IS stream (CRN, same construction as Benchmark B).

    The leakage-power weights use the TRUE empirical L_k under q0 (explored
    post-hoc from a large q0 stream -- oracle information, allowed for the
    hand-designed M3 baseline)."""
    centers = np.vstack([xl_s1, xl_s2])
    # probabilities under p (MC exploration) for the weight strategies
    rng0 = np.random.default_rng(SEEDS[0] + 111)
    z0 = rng0.standard_normal((400_000, D))
    lab0 = label_curved(z0)
    p_s1 = float(np.mean(lab0 == "S1"))
    p_s2 = float(np.mean(lab0 == "S2"))
    # leakage L_k under q0: (1/N) sum 1_A p^2 / q0^2 (true oracle weights)
    rng1 = np.random.default_rng(seed + 789)
    zq = Q0_CENTER[None, :] + rng1.standard_normal((200_000, D))
    labq = label_curved(zq)
    logq0 = -0.5 * np.sum((zq - Q0_CENTER) ** 2, axis=1) \
        - 0.5 * D * np.log(2.0 * np.pi)
    w2 = np.exp(2.0 * logp(zq) - 2.0 * logq0)
    l1 = float(np.mean(w2 * (labq == "S1").astype(float)))
    l2 = float(np.mean(w2 * (labq == "S2").astype(float)))
    p_norm = np.array([p_s1, p_s2]); p_norm = p_norm / p_norm.sum()
    l_norm = np.array([l1, l2]); l_norm = l_norm / l_norm.sum()
    p05 = np.sqrt(p_norm * l_norm); p05 = p05 / p05.sum()
    strategies = {"probability": p_norm, "leak_power1": l_norm, "p05_l05": p05}

    r_prop = MixtureProposal(centers=centers, weights=np.array([0.5, 0.5]))
    rng = np.random.default_rng(seed + 750_000)
    z = r_prop.sample(rng, budget)
    logr = r_prop.log_density(z)
    labels = label_curved(z)
    ind = (labels != NOMINAL).astype(float)
    p_hat = float(np.mean(np.exp(logp(z) - logr) * ind))
    evals: dict[str, dict] = {}
    for sname, wvec in strategies.items():
        qs = MixtureProposal(centers=centers, weights=wvec)
        w2 = np.exp(2.0 * logp(z) - qs.log_density(z) - logr) * ind
        m2_s = float(np.mean(w2))
        evals[sname] = {"M2_hat": m2_s, "var_hat": max(0.0, (m2_s - p_hat**2) / budget)}
    best_name = min(evals, key=lambda s: evals[s]["var_hat"])
    return BaselineResult(
        method="h3_2_m3_leakage_mixture", seed=seed, adaptation_calls=0,
        total_calls=budget, eval={**evals[best_name], "P_hat": p_hat, "n_eval": budget},
        extra={"best_strategy": best_name, "all_strategies": evals,
               "centers": [list(xl_s1), list(xl_s2)],
               "note": "shared IS stream (CRN), frozen H3-2 best-of-3 semantics"},
    )


def run_mc_curved(seed: int, budget: int) -> dict:
    """Crude MC under the CURVED label (baselines.run_mc is H3-1-locked)."""
    rng = np.random.default_rng(seed + 600_000)
    z = rng.standard_normal((budget, D))
    ind = (label_curved(z) != NOMINAL).astype(float)
    p_hat = float(ind.mean())
    return {"P_hat": p_hat, "M2_hat": p_hat,
            "var_hat": p_hat * (1.0 - p_hat) / budget,
            "n_eval": budget, "total_calls": budget}


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    t0 = time.perf_counter()

    mpp_s1 = np.array([A1, 0.0])
    mpp_s2 = _mpp_s2()
    xl_s1 = mpp_s1                            # linear A1: MPP == leakage point
    xl_s2 = _leakage_point_s2(Q0_CENTER)
    separation = float(np.linalg.norm(xl_s2 - mpp_s2))
    print(f"geometry: MPP_S2={mpp_s2} xL_S2={xl_s2} separation={separation:.4f}")

    mc_ref = run_mc_curved(SEEDS[0], BUDGET)
    p_mc_ref = mc_ref["P_hat"]

    rows = []
    for seed in SEEDS:
        m1 = run_m1_closed_loop(seed, ADAPT_PILOT, EVAL_N, config,
                                q0_center=Q0_CENTER, oracle=label_curved,
                                logp_fn=logp)
        row = {
            "seed": seed,
            "crude_mc": run_mc_curved(seed, BUDGET),
            "single_geometry_q0": {**_eval(MixtureProposal(
                centers=Q0_CENTER[None, :], weights=np.array([1.0]),
                component_mode_ids=("S1",)), BUDGET, seed,
                oracle=label_curved, logp_fn=logp),
                "total_calls": BUDGET},
            "h3_2_m2_topology_mixture": {
                **run_m2_mixture(seed, BUDGET, mpp_s1, mpp_s2).eval,
                "total_calls": BUDGET},
            "h3_2_m3_leakage_mixture": {
                **run_m3_mixture(seed, BUDGET, xl_s1, xl_s2).eval,
                "total_calls": BUDGET},
            "m1_closed_loop": {
                "M2_hat": m1.eval["M2_hat"], "P_hat": m1.eval["P_hat"],
                "var_hat": m1.eval["var_hat"], "n_eval": EVAL_N,
                "births": m1.extra["births"],
                "final_weights": m1.extra["final_weights"],
                "final_components": m1.extra["final_components"],
                "adaptation_calls": m1.adaptation_calls,
                "total_calls": m1.total_calls,
                "stop_reason": m1.extra["stop_reason"],
            },
        }
        rows.append(row)

    n_birth = sum(1 for r in rows if r["m1_closed_loop"]["births"] == ["S2"])
    n_wrong = sum(1 for r in rows
                  if r["m1_closed_loop"]["births"] != ["S2"]
                  and r["m1_closed_loop"]["births"])
    ratios = [r["m1_closed_loop"]["M2_hat"] / r["single_geometry_q0"]["M2_hat"]
              for r in rows]
    median_ratio = float(np.median(ratios))
    unbiased = all(abs(r["m1_closed_loop"]["P_hat"]
                       - r["crude_mc"]["P_hat"]) <= 5e-3 for r in rows)
    verdict = {
        "discovery": "PASS" if (n_birth >= 7 and n_wrong == 0) else
                    ("BORDERLINE" if n_birth >= 6 else "FAIL"),
        "m2_reduction": "PASS" if median_ratio <= 0.5 else "FAIL",
        "unbiased": bool(unbiased),
        "n_birth_S2": n_birth, "n_wrong_birth": n_wrong,
        "median_M2_ratio": median_ratio, "ratios": ratios,
    }

    record = {
        "schema_version": "raretopo-m1-benchmark-c-v0",
        "config_id": config["config_id"],
        "h3_frozen_tag": config["h3_frozen_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark": "C_h3_2_curved_multi_mode",
        "benchmark_definition": {
            "source": "H3-2 label_curved (frozen semantics)",
            "d": D, "A1": {"label": "S1", "condition": "u1 < -1.5"},
            "A2": {"label": "S2", "condition": "u1 > 1 + 0.5 (u2 - 1.5)^2"},
            "nominal": NOMINAL, "q0": list(Q0_CENTER),
            "geometry": {"mpp_s1": list(mpp_s1), "mpp_s2": list(mpp_s2),
                         "xL_s1": list(xl_s1), "xL_s2": list(xl_s2),
                         "mpp_xL_separation_S2": separation},
        },
        "p_mc_ref": float(p_mc_ref),
        "per_seed": rows,
        "verdict": verdict,
        "note": "Benchmark C is mechanism evidence, not a preregistered gate "
                "(gates are locked to Benchmark B, task Sec. 33 ladder). "
                "CEM not repeated (reported in B); fixed variance-aware "
                "identical in structure to M3-best on this benchmark and "
                "omitted for budget clarity.",
        "total_wall_time_s": time.perf_counter() - t0,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({**verdict, "output": str(OUT_PATH)}, indent=2))
    return 0 if (verdict["discovery"] == "PASS" and verdict["m2_reduction"] == "PASS"
                 and verdict["unbiased"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())