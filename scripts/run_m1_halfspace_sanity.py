"""M1-2 -- Benchmark A: Affine / Half-Space Sanity (task Sec. 20 Benchmark A).

Purpose (not a headline claim):

- verify unbiasedness of the closed-loop estimator (P_hat vs analytic);
- verify the M2 estimator against the closed form M2 = exp(||m||^2) Phi(a+m1);
- verify the frozen mixture-weight optimizer inside the loop (success / KKT /
  objective decrease recorded per birth);
- verify the closed loop HOLDS when no mode is missing, with ZERO false
  component births (8 preregistered seeds);
- exercise the adaptive path on a crafted 2-mode case (expected: the
  variance-dominant secondary mode is born on seeds with enough observations;
  no wrong-mode birth ever).

Budget (frozen, config m1_closed_loop_v0.json): pilot = 20,000 per round,
max 3 iterations, final evaluation = 100,000 samples, generated only after
q_final is frozen.  Preregistered seeds [2026..2033]; only these seeds enter
the summary.

Outputs: results/phase_m1/m1_halfspace_sanity_v0.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import norm

from hyptraj.m1.closed_loop import run_closed_loop
from hyptraj.m1.proposal_update import MixtureProposal

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_PATH = REPO / "results" / "phase_m1" / "m1_halfspace_sanity_v0.json"

D = 2
A1, A2 = -1.5, 1.9
M0 = np.array([-1.5, 0.0])
SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]


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
    return (-np.sum(z**2, axis=1) / 2.0 - 0.5 * D * np.log(2.0 * np.pi))


def labels_single(z):
    z = np.asarray(z, dtype=float)
    return np.where(z[:, 0] <= A1, "S1", "S0")


def labels_double(z):
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], "S0", dtype=object)
    out[z[:, 0] <= A1] = "S1"
    out[z[:, 0] >= A2] = "S2"
    return out


def p_ref() -> float:
    """Analytic P_p(A) under the TARGET p = N(0, I): A1 union A2."""
    return float(norm.cdf(A1) + (1.0 - norm.cdf(A2)))


def p_ref_a1() -> float:
    """Analytic P_p(A1) under the TARGET p = N(0, I): A = {z1 <= -1.5}."""
    return float(norm.cdf(A1))


def m2_ref_q0() -> float:
    """Analytic M2(q0) = exp(||m||^2) * Phi(a + m1), A = {z1 <= a} half-space."""
    return float(np.exp(np.sum(M0**2)) * norm.cdf(A1 + M0[0]))


def eval_proposal(proposal: MixtureProposal, oracle, n_eval: int, seed: int):
    """Independent final evaluation on fresh samples after q_final freezes."""
    rng = np.random.default_rng(seed + 400_000)   # fresh eval stream
    z = proposal.sample(rng, n_eval)
    labels = oracle(z)
    ind = (labels != "S0").astype(float)
    w = np.exp(logp(z) - proposal.log_density(z)) * ind
    p_hat = float(np.mean(w))
    m2_hat = float(np.mean(w**2))
    var_hat = max(0.0, (m2_hat - p_hat**2) / n_eval)
    return {"P_hat": p_hat, "M2_hat": m2_hat, "var_hat": var_hat, "n": n_eval}


def run_case_a1(seed: int, pilot_n: int, eval_n: int, config) -> dict:
    """Single-mode half-space: expect HOLD, no false birth, unbiased."""
    q0 = MixtureProposal(centers=M0[None, :], weights=np.array([1.0]),
                         component_mode_ids=("S1",))
    t0 = time.perf_counter()
    res = run_closed_loop(
        seed=seed, initial_proposal=q0, label_oracle=labels_single,
        logp_fn=logp, nominal_topology="S0", pilot_n=pilot_n,
        max_iterations=config["budget"]["max_adaptation_iterations"],
        tau_birth_main=config["mode_birth"]["tau_birth_main"],
        tau_birth_lower_confidence=config["mode_birth"]["tau_birth_lower_confidence"],
        min_mode_observations=config["mode_birth"]["min_mode_observations"],
    )
    ev = eval_proposal(res.final_proposal, labels_single, eval_n, seed)
    prec = 3.0 * np.sqrt(ev["var_hat"])
    return {
        "seed": seed,
        "stop_reason": res.stop_reason,
        "n_iterations": len(res.iterations),
        "actions": [it.action for it in res.iterations],
        "false_births": [it.candidate_mode for it in res.iterations
                         if it.candidate_mode is not None],
        "n_components_final": res.final_proposal.n_components,
        "P_hat": ev["P_hat"],
        "P_ref": p_ref_a1(),
        "P_unbiased": bool(abs(ev["P_hat"] - p_ref_a1()) <= max(prec, 2e-3)),
        "M2_hat": ev["M2_hat"],
        "M2_ref_q0": m2_ref_q0(),
        "M2_consistent": bool(abs(ev["M2_hat"] - m2_ref_q0()) / m2_ref_q0() <= 0.1),
        "pilot_calls": res.n_pilot_calls,
        "eval_calls": eval_n,
        "total_calls": res.total_calls + eval_n,
        "wall_time_s": time.perf_counter() - t0,
    }


def run_case_a2(seed: int, pilot_n: int, eval_n: int, config) -> dict:
    """Crafted 2-mode: variance-dominant secondary mode; birth when the pilot
    has enough observations (Poisson mean ~6.8) -- HOLD is the correct
    behavior on information-poor seeds; wrong-mode birth is never allowed."""
    q0 = MixtureProposal(centers=M0[None, :], weights=np.array([1.0]),
                         component_mode_ids=("S1",))
    t0 = time.perf_counter()
    res = run_closed_loop(
        seed=seed, initial_proposal=q0, label_oracle=labels_double,
        logp_fn=logp, nominal_topology="S0", pilot_n=pilot_n,
        max_iterations=config["budget"]["max_adaptation_iterations"],
        tau_birth_main=config["mode_birth"]["tau_birth_main"],
        tau_birth_lower_confidence=config["mode_birth"]["tau_birth_lower_confidence"],
        min_mode_observations=config["mode_birth"]["min_mode_observations"],
    )
    it0 = res.iterations[0]
    births = [it.candidate_mode for it in res.iterations
              if it.candidate_mode is not None]
    m2_drop = None
    if it0.M2_hat_prev is not None and it0.M2_hat_prev > 0:
        m2_drop = float((it0.M2_hat_prev - it0.M2_hat) / it0.M2_hat_prev)
    ev = eval_proposal(res.final_proposal, labels_double, eval_n, seed)
    prec = 3.0 * np.sqrt(ev["var_hat"])
    return {
        "seed": seed,
        "stop_reason": res.stop_reason,
        "n_iterations": len(res.iterations),
        "actions": [it.action for it in res.iterations],
        "births": births,
        "correct_birth": True if births == ["S2"] else
                         (None if not births else False),
        "P_hat": ev["P_hat"],
        "P_ref": p_ref(),
        "P_unbiased": bool(abs(ev["P_hat"] - p_ref()) <= max(prec, 2e-3)),
        "M2_hat_final": ev["M2_hat"],
        "m2_relative_drop_after_birth": m2_drop,
        "weight_opt": res.iterations[0].weight_result,
        "pilot_calls": res.n_pilot_calls,
        "eval_calls": eval_n,
        "total_calls": res.total_calls + eval_n,
        "wall_time_s": time.perf_counter() - t0,
    }


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    pilot_n = config["budget"]["pilot_per_iteration"]
    eval_n = config["budget"]["final_eval_samples"]

    a1, a2 = [], []
    t_start = time.perf_counter()
    for seed in SEEDS:
        a1.append(run_case_a1(seed, pilot_n, eval_n, config))
        a2.append(run_case_a2(seed, pilot_n, eval_n, config))

    a1_pass = all(
        r["stop_reason"] == "no_missing_mode"
        and r["n_components_final"] == 1
        and not r["false_births"]
        and r["P_unbiased"]
        and r["M2_consistent"]
        for r in a1
    )
    n_birth = sum(1 for r in a2 if r["births"])
    n_correct = sum(1 for r in a2 if r["correct_birth"] is True)
    n_wrong = sum(1 for r in a2 if r["correct_birth"] is False)
    a2_pass = (n_wrong == 0) and (n_birth >= 1) and all(r["P_unbiased"] for r in a2)

    record = {
        "schema_version": "raretopo-m1-halfspace-sanity-v0",
        "config_id": config["config_id"],
        "h3_frozen_tag": config["h3_frozen_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark": "A_halfspace_sanity",
        "pilot_per_iteration": pilot_n,
        "final_eval_samples": eval_n,
        "seeds": SEEDS,
        "case_A1_single_mode": {"pass": a1_pass, "runs": a1},
        "case_A2_two_mode_demo": {"pass": a2_pass, "runs": a2,
                                  "n_birth": n_birth, "n_correct": n_correct,
                                  "n_wrong_mode_birth": n_wrong},
        "sanity_overall_pass": bool(a1_pass and a2_pass),
        "note": "Benchmark A is a sanity benchmark, NOT a headline performance "
                "claim (task Sec. 20).  A2 birth depends on pilot information "
                "(Poisson mean ~6.8 observations of the far mode); HOLD on "
                "information-poor seeds is correct behavior.",
        "total_wall_time_s": time.perf_counter() - t_start,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(json.dumps({
        "case_A1": {"pass": a1_pass,
                    "hold": sum(1 for r in a1 if r["stop_reason"] == "no_missing_mode"),
                    "false_births": sum(len(r["false_births"]) for r in a1),
                    "P_unbiased": sum(r["P_unbiased"] for r in a1),
                    "M2_consistent": sum(r["M2_consistent"] for r in a1)},
        "case_A2": {"pass": a2_pass, "n_birth": n_birth, "n_correct": n_correct,
                    "n_wrong_mode_birth": n_wrong,
                    "m2_drops": [r["m2_relative_drop_after_birth"]
                                 for r in a2 if r["m2_relative_drop_after_birth"] is not None]},
        "sanity_overall_pass": bool(a1_pass and a2_pass),
        "output": str(OUT_PATH),
    }, indent=2))
    return 0 if (a1_pass and a2_pass) else 1


if __name__ == "__main__":
    raise SystemExit(main())