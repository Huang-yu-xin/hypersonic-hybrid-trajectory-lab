"""M1-3 -- H3-1 variance-important missing-mode discovery (Benchmark B, Stage 1).

Reuses the FROZEN H3-1 L2 synthetic multi-mode benchmark definition
(``scripts/run_h3_variance_leakage.py`` L2_synthetic_multi_mode): d = 4
standardized space, alpha_dir = e1, beta_eff = 1.5, q0 = N(-1.5 e1, I),
labels: u1 < -1.5 -> S1 (primary, covered), u1 > 2.5 -> S2 (far,
probability-small but variance-dominant), else S0.

Frozen ground truth (read post-run ONLY, never fed to the algorithm):

- analytic leak: S1 = 0.012807, S2 = 1.505279 (true omega_S2 ~ 0.992);
- frozen dataset n_events(S2) = 5 per 200,000 q-only pilot samples
  (P(S2|q0) = 3.2e-5) -> the frozen 20,000-call q-only pilot would expect
  0.63 observations, making the birth gate numerically unusable;
  per config ``pilot_policy.mix_50`` half of each pilot comes from the
  target p (P(S2|p) = 6.2e-3, x195), so each 20,000-call pilot expects
  ~62 S2 observations at unchanged frozen budget.

Discovery Gate (task Sec. 25 Gate 1, frozen): >= 7/8 seeds identify the
variance-important missing mode (correct mode passes the birth gate) with no
comparable-frequency false births on wrong modes; 6/8 BORDERLINE; < 6/8 FAIL
(-> task Sec. 33 STOP, research finite-sample diagnosis).

The algorithm is never given the true leakage fraction or the S2 location.
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

from hyptraj.m1.mode_discovery import diagnose_missing_mode
from hyptraj.m1.proposal_update import MixtureProposal
from hyptraj.m1.variance_measure import estimate_variance_measure

import os

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_SUFFIX = os.environ.get("M1_OUT_SUFFIX", "")
OUT_PATH = REPO / "results" / ("phase_m1" + OUT_SUFFIX) / "m1_h3_1_discovery_v0.json"
H3_DATASET = REPO / "tests" / "data" / "h3_variance_leakage_dataset_v1.json"

D = 4
BETA_EFF = 1.5
ALPHA_DIR = np.zeros(D)
ALPHA_DIR[0] = 1.0
Z_STAR = -BETA_EFF * ALPHA_DIR       # q0 = N(z_star, I)
A1, A2 = -1.5, 2.5
NOMINAL = "S0"
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
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * D * np.log(2.0 * np.pi)


def label_h3_1(z: np.ndarray) -> np.ndarray:
    """Exact H3-1 L2 topology oracle (frozen script semantics, verbatim)."""
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], NOMINAL, dtype=object)
    out[z[:, 0] < A1] = "S1"
    out[z[:, 0] > A2] = "S2"
    return out


def load_ground_truth() -> dict:
    """Frozen H3-1 values for POST-RUN comparison only."""
    d = json.loads(H3_DATASET.read_text(encoding="utf-8"))
    c = next(x for x in d["configs"] if x["config_id"] == "L2_synthetic_multi_mode")
    leak_s1 = float(c["analytic_leak_s1"])
    leak_s2 = float(c["analytic_leak_s2"])
    return {
        "analytic_leak_s1": leak_s1,
        "analytic_leak_s2": leak_s2,
        "true_omega_S2": leak_s2 / (leak_s1 + leak_s2),
        "frozen_n_events_S2_at_200k_q_pilot": next(
            m["n_events"] for m in c["modes"] if m["transition_topology"] == "S2"
        ),
        "frozen_P_S2_mc": next(
            m["mode_probability"] for m in c["modes"]
            if m["transition_topology"] == "S2"
        ),
    }


def run_discovery_seed(seed: int, pilot_n: int, config) -> dict:
    """One seed: mix_50 pilot + diagnosis; record gate evidence."""
    q0 = MixtureProposal(centers=Z_STAR.reshape(1, -1), weights=np.array([1.0]),
                         component_mode_ids=("S1",))
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    half = pilot_n // 2
    z1 = q0.sample(rng, half)
    r1 = q0.log_density(z1)
    z2 = rng.standard_normal((pilot_n - half, D))
    r2 = logp(z2)
    z = np.vstack([z1, z2])
    logr = np.concatenate([r1, r2])
    logp_z = logp(z)
    labels = label_h3_1(z)

    vm = estimate_variance_measure(
        z, q0.centers, q0.weights, logp_z, logr, labels, NOMINAL
    )
    diag = diagnose_missing_mode(
        z, q0.centers, q0.weights, logp_z, logr, labels, NOMINAL,
        component_mode_ids=set(q0.component_mode_ids),
        tau_birth_main=config["mode_birth"]["tau_birth_main"],
        tau_birth_lower_confidence=config["mode_birth"]["tau_birth_lower_confidence"],
        min_mode_observations=config["mode_birth"]["min_mode_observations"],
        n_bootstrap=500,
        rng=np.random.default_rng(seed + 10),
    )
    stats = {s.mode_id: s for s in diag.mode_stats}
    candidate = diag.candidate_mode
    return {
        "seed": seed,
        "candidate_mode": candidate,
        "identified_S2": bool(candidate == "S2"),
        "false_birth": bool(candidate is not None and candidate != "S2"),
        "omega_S2_hat": stats["S2"].omega_k_V_hat if "S2" in stats else None,
        "omega_S2_lcb95": stats["S2"].omega_lcb95 if "S2" in stats else None,
        "n_S2_observed": stats["S2"].n_observed if "S2" in stats else 0,
        "n_S1_observed": stats["S1"].n_observed if "S1" in stats else 0,
        "M2_hat": diag.M2_hat,
        "variance_mass_ess": diag.variance_mass_ess,
        "n_events": diag.n_events,
        "wall_time_s": time.perf_counter() - t0,
    }


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    pilot_n = config["budget"]["pilot_per_iteration"]
    gt = load_ground_truth()

    runs = [run_discovery_seed(seed, pilot_n, config) for seed in SEEDS]
    n_ident = sum(1 for r in runs if r["identified_S2"])
    n_false = sum(1 for r in runs if r["false_birth"])

    if n_ident >= 7 and n_false == 0:
        gate = "PASS"
    elif n_ident >= 6 and n_false == 0:
        gate = "BORDERLINE"
    else:
        gate = "FAIL"

    record = {
        "schema_version": "raretopo-m1-h3-1-discovery-v0",
        "config_id": config["config_id"],
        "h3_frozen_tag": config["h3_frozen_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark": "B_h3_1_leakage_discovery_stage",
        "benchmark_definition": {
            "source": "H3-1 L2_synthetic_multi_mode (frozen script semantics, verbatim)",
            "d": D, "beta_eff": BETA_EFF, "q0": list(Z_STAR),
            "A1": {"label": "S1", "condition": f"u1 < {A1}"},
            "A2": {"label": "S2", "condition": f"u1 > {A2}"},
            "nominal": NOMINAL,
        },
        "oracle_used_by_algorithm": {
            "none": ["true_leakage_fraction", "secondary_mode_location",
                     "frozen_n_events", "analytic leaks"],
        },
        "ground_truth_postrun_only": gt,
        "pilot": {"n": pilot_n, "policy": config["pilot_policy"]["name"],
                  "expected_S2_observations_mix50": float(
                      pilot_n * (0.5 * (1.0 - norm.cdf(4.0))
                                 + 0.5 * (1.0 - norm.cdf(2.5)))),
        },
        "runs": runs,
        "discovery_gate": {
            "gate": gate,
            "n_identified_S2": n_ident,
            "n_false_births": n_false,
            "n_seeds": len(SEEDS),
            "pass_rule": ">=7/8 identified, 0 false births; 6/8 BORDERLINE; <6 FAIL",
            "stop_if_fail": "task Sec.33: research finite-sample diagnosis; "
                            "no oracle-mode patching",
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(json.dumps({
        "identified_S2": n_ident, "false_births": n_false,
        "gate": gate, "per_seed": [r["seed"] for r in runs if not r["identified_S2"]],
        "omega_S2_hats": [r["omega_S2_hat"] for r in runs],
        "n_S2_observed": [r["n_S2_observed"] for r in runs],
        "true_omega_S2": gt["true_omega_S2"],
        "output": str(OUT_PATH),
    }, indent=2))
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())