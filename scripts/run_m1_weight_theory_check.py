"""M1-1 -- Mixture-weight theory numerical verification (V1..V6).

Runs the preregistered verification suite of
``docs/phase_m1/M1_Theory_Mixture_Weight_Convexity.md`` (Sec. 12) against the
frozen config ``configs/m1_closed_loop_v0.json`` and writes
``results/phase_m1/m1_weight_theory_check_v0.json``.

Checks:

- V1  unbiasedness of ``M2_hat(pi)`` (r = p closed form; r = q_pi0; pooled
       mixed pilots) against exact references
- V2  analytic gradient (T1) vs constraint-respecting central finite
       differences along simplex tangent directions
- V3  analytic Hessian (T2): symmetry / PSD (v^T H v >= 0) / eig min / FD
- V4  empirical convexity on fixed sample sets (segment midpoints)
- V5  frozen SLSQP solve: feasibility, improvement, KKT residue,
       init independence
- V6  degenerate identical components: flatness along the simplex direction

Pure synthetic analysis (standardized Gaussian space, no simulator);
debug-style run with a single recorded seed (task Sec. 19).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.stats import norm

from hyptraj.m1.mixture_weights import (
    component_log_densities,
    kkt_residue,
    m2_gradient,
    m2_hat,
    m2_hessian,
    mixture_log_density,
    optimize_mixture_weights,
)

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO / "configs" / "m1_closed_loop_v0.json"
OUT_PATH = REPO / "results" / "phase_m1" / "m1_weight_theory_check_v0.json"
SEED = 2026
D = 2

# task-doc locked values the config must match (pre-registration self-check)
TASK_LOCKED = {
    "tau_birth_main": 0.10,
    "tau_birth_lower_confidence": 0.05,
    "min_mode_observations": 5,
    "eta_main": 0.8,
    "pilot_per_iteration": 20000,
    "max_adaptation_iterations": 3,
    "final_eval_samples": 100000,
    "seeds": [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033],
}


def git_short_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def sha256_hex(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# toy geometry helpers (identical convention as tests)
# ---------------------------------------------------------------------------
def target_log_density(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def draw_from_mixture(rng, centers, pi, n: int) -> np.ndarray:
    cent = np.asarray(centers, dtype=float)
    pi = np.asarray(pi, dtype=float)
    comp = rng.choice(cent.shape[0], size=n, p=pi)
    return cent[comp] + rng.standard_normal((n, cent.shape[1]))


def make_inputs(z, centers, pi_r, event_a: float, event_b=None):
    logq_ji = component_log_densities(z, np.asarray(centers, dtype=float))
    logr = mixture_log_density(logq_ji, pi_r)
    logp = target_log_density(z)
    ind = (z[:, 0] <= event_a).astype(float)
    if event_b is not None:
        ind = np.maximum(ind, (z[:, 0] >= event_b).astype(float))
    return logq_ji, logp, logr, ind


def m2_quad_1d(centers, pi, a: float) -> float:
    centers = np.atleast_1d(np.asarray(centers, dtype=float))
    pi = np.asarray(pi, dtype=float)

    def integrand(z):
        z = np.asarray(z, dtype=float)
        log_p2 = -z * z - np.log(2.0 * np.pi)          # 2 log phi(z), d=1
        log_q = np.logaddexp.reduce(
            [np.log(w) - 0.5 * (z - m) ** 2 - 0.5 * np.log(2.0 * np.pi)
             for m, w in zip(centers, pi)], axis=0)
        return np.exp(log_p2 - log_q)

    val, _ = quad(integrand, -np.inf, float(a), limit=400)
    return float(val)


def _py(x):
    """Recursively convert numpy scalars/arrays/bools to python (JSON-safe)."""
    if isinstance(x, dict):
        return {k: _py(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_py(v) for v in x]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, np.ndarray):
        return _py(x.tolist())
    return x


def interior(rng, k: int, margin: float = 0.05) -> np.ndarray:
    a = rng.dirichlet(np.ones(k) * 2.0)
    a = np.clip(a, margin, None)
    return a / a.sum()


# ---------------------------------------------------------------------------
# V1 -- unbiasedness
# ---------------------------------------------------------------------------
def v1_unbiasedness(rng, rng_state) -> dict:
    out = {"checks": [], "pass": True}
    # V1a: r = p, J = 1 closed form M2 = exp(m^2) * Phi(a + m)
    m, a, n, b = 1.0, -0.75, 4000, 80
    reference = float(np.exp(m * m) * norm.cdf(a + m))
    ests = []
    for _ in range(b):
        z = rng.standard_normal((n, 1))
        logq = component_log_densities(z, np.array([[m]]))
        logp = target_log_density(z)
        ind = (z[:, 0] <= a).astype(float)
        ests.append(m2_hat(logq, logp, logp, ind, np.array([1.0])))
    ests = np.array(ests)
    sd = float(ests.std(ddof=1))
    se = sd / np.sqrt(b)
    ratio = abs(float(ests.mean()) - reference) / se
    passed = ratio <= 3.0
    out["checks"].append({
        "id": "V1a", "desc": "r=p, J=1 closed-form unbiasedness",
        "reference": reference, "mean": float(ests.mean()),
        "bias": float(ests.mean()) - reference, "se": se,
        "bias_se_ratio": ratio, "pass": passed,
    })
    out["pass"] &= passed

    # V1b: r = q_pi0 frozen, evaluated at pi != pi0 and pi == pi0 (w^2 form)
    centers = np.array([[-1.5], [0.5]])
    pi0 = np.array([0.6, 0.4])
    a = -0.75
    for name, pi_test in (("pi_test=pi0_w2", np.array([0.6, 0.4])),
                          ("pi_test=0.2/0.8", np.array([0.2, 0.8])),
                          ("pi_test=0.9/0.1", np.array([0.9, 0.1]))):
        reference = m2_quad_1d(centers.ravel(), pi_test, a)
        n, b = 4000, 60
        ests = []
        for _ in range(b):
            z = draw_from_mixture(rng, centers, pi0, n)
            logq, logp, logr, ind = make_inputs(z, centers, pi0, a)
            ests.append(m2_hat(logq, logp, logr, ind, pi_test))
        ests = np.array(ests)
        sd = float(ests.std(ddof=1))
        se = sd / np.sqrt(b)
        ratio = abs(float(ests.mean()) - reference) / se
        passed = ratio <= 3.0
        out["checks"].append({
            "id": f"V1b_{name}", "desc": f"r=q_pi0 frozen, {name}",
            "reference": reference, "mean": float(ests.mean()),
            "bias": float(ests.mean()) - reference, "se": se,
            "bias_se_ratio": ratio, "pass": passed,
        })
        out["pass"] &= passed

    # V1c: pooled mixed pilots (r1 = p, r2 = q_pi0)
    centers = np.array([[-1.5], [0.5]])
    pi0 = np.array([0.5, 0.5])
    pi_test = np.array([0.3, 0.7])
    a = -0.75
    reference = m2_quad_1d(centers.ravel(), pi_test, a)
    n1, n2, b = 2000, 2000, 60
    ests = []
    for _ in range(b):
        z1 = rng.standard_normal((n1, 1))
        z2 = draw_from_mixture(rng, centers, pi0, n2)
        z = np.vstack([z1, z2])
        logq = component_log_densities(z, centers)
        logp = target_log_density(z)
        logr = np.concatenate([target_log_density(z1), mixture_log_density(
            component_log_densities(z2, centers), pi0)])
        ind = (z[:, 0] <= a).astype(float)
        ests.append(m2_hat(logq, logp, logr, ind, pi_test))
    ests = np.array(ests)
    sd = float(ests.std(ddof=1))
    se = sd / np.sqrt(b)
    ratio = abs(float(ests.mean()) - reference) / se
    passed = ratio <= 3.0
    out["checks"].append({
        "id": "V1c", "desc": "pooled mixed pilots r1=p, r2=q_pi0",
        "reference": reference, "mean": float(ests.mean()),
        "bias": float(ests.mean()) - reference, "se": se,
        "bias_se_ratio": ratio, "pass": passed,
    })
    out["pass"] &= passed
    return out


# ---------------------------------------------------------------------------
# V2 / V3 -- gradient & Hessian vs finite differences
# ---------------------------------------------------------------------------
def v2_v3_derivatives(rng) -> dict:
    centers = np.array([[-1.5, 0.0], [0.5, 1.0], [1.8, -0.5]])
    pi0 = np.array([0.4, 0.3, 0.3])
    z = draw_from_mixture(rng, centers, pi0, 6000)
    logq, logp, logr, ind = make_inputs(z, centers, pi0, -1.1, event_b=2.2)
    k = logq.shape[1]

    # V2 gradient (simplex tangent directions)
    max_rel = 0.0
    n_points = 0
    for _ in range(5):
        a = interior(rng, k)
        g = m2_gradient(logq, logp, logr, ind, a)
        for j in range(1, k):
            d = np.zeros(k)
            d[j], d[0] = 1.0, -1.0
            h = 1e-6
            fp = m2_hat(logq, logp, logr, ind, a + h * d)
            fm = m2_hat(logq, logp, logr, ind, a - h * d)
            fd = (fp - fm) / (2.0 * h)
            denom = max(1e-12, abs(g[j] - g[0]))
            max_rel = max(max_rel, abs(fd - (g[j] - g[0])) / denom)
            n_points += 1
    v2_ok = max_rel <= 1e-6

    # V3 Hessian
    sym_max = 0.0
    eig_min = 1e300
    min_vhv = 1e300
    fd_max = 0.0
    n_pts = 0
    for _ in range(5):
        a = interior(rng, k)
        H = m2_hessian(logq, logp, logr, ind, a)
        sym_max = max(sym_max, float(np.max(np.abs(H - H.T))))
        eig_min = min(eig_min, float(np.linalg.eigvalsh(H).min()))
        for _v in range(100):
            v = rng.standard_normal(k)
            min_vhv = min(min_vhv, float(v @ H @ v))
        v = rng.standard_normal(k)
        v = v - v.mean()
        h = 1e-6
        gp = m2_gradient(logq, logp, logr, ind, a + h * v)
        gm = m2_gradient(logq, logp, logr, ind, a - h * v)
        fd = (gp - gm) / (2.0 * h)
        fd_max = max(fd_max, float(np.max(np.abs(fd - H @ v)
                    / np.maximum(1e-12, np.abs(H @ v)))))
        n_pts += 1
    v3_ok = sym_max <= 1e-12 and eig_min >= -1e-8 and min_vhv >= -1e-10 \
        and fd_max <= 1e-4
    return {
        "pass": v2_ok and v3_ok,
        "V2": {"desc": "analytic gradient vs simplex-direction central FD",
               "max_rel_err": max_rel, "n_directions": n_points,
               "tol": 1e-6, "pass": v2_ok},
        "V3": {"desc": "Hessian symmetry / PSD / v^T H v / FD of gradient",
               "symmetry_max_abs_diff": sym_max, "min_eig": eig_min,
               "min_vT_H_v": min_vhv, "fd_gradient_max_rel_err": fd_max,
               "n_points": n_pts, "pass": v3_ok},
    }


# ---------------------------------------------------------------------------
# V4 -- empirical convexity on fixed sample sets
# ---------------------------------------------------------------------------
def v4_convexity(rng) -> dict:
    centers = np.array([[-1.5, 0.0], [0.5, 1.0], [1.8, -0.5]])
    pi0 = np.array([0.4, 0.3, 0.3])
    z = draw_from_mixture(rng, centers, pi0, 6000)
    logq, logp, logr, ind = make_inputs(z, centers, pi0, -1.1, event_b=2.2)
    k = logq.shape[1]
    max_violation = 0.0
    for _ in range(200):
        a = interior(rng, k, margin=0.01)
        b = interior(rng, k, margin=0.01)
        lam = rng.uniform(0.05, 0.95)
        mid = lam * a + (1.0 - lam) * b
        f_mid = m2_hat(logq, logp, logr, ind, mid)
        f_line = lam * m2_hat(logq, logp, logr, ind, a) + \
            (1.0 - lam) * m2_hat(logq, logp, logr, ind, b)
        max_violation = max(max_violation, float(f_mid - f_line))
    ok = max_violation <= 1e-9
    return {"pass": ok, "max_midpoint_violation": max_violation, "n_segments": 200,
            "tol": 1e-9}


# ---------------------------------------------------------------------------
# V5 -- frozen SLSQP solve
# ---------------------------------------------------------------------------
def v5_optimizer(rng) -> dict:
    centers = np.array([[-1.5, 0.0], [0.5, 1.0], [1.8, -0.5]])
    pi0 = np.array([0.4, 0.3, 0.3])
    z = draw_from_mixture(rng, centers, pi0, 8000)
    logq, logp, logr, ind = make_inputs(z, centers, pi0, -1.1, event_b=2.2)
    inits = [np.full(3, 1.0 / 3.0), np.array([0.98, 0.01, 0.01]),
             np.array([0.01, 0.98, 0.01]), np.array([0.33, 0.34, 0.33])]
    results = []
    for w0 in inits:
        r = optimize_mixture_weights(logq, logp, logr, ind, pi0=w0)
        results.append({
            "success": r.success, "message": r.message,
            "weights": [float(x) for x in r.weights],
            "objective_init": r.objective_init,
            "objective_final": r.objective_final,
            "n_iter": r.n_iter, "kkt_residue": r.kkt_residue,
            "n_events": r.n_events,
            "feasible": bool(np.isclose(r.weights.sum(), 1.0, atol=1e-8)
                             and np.all(r.weights >= -1e-9)),
        })
        assert r.success, f"SLSQP failed: {r.message}"
    weights_mat = np.array([r["weights"] for r in results])
    w_spread = float(np.max(np.abs(weights_mat - weights_mat[0])))
    obj_spread = max(abs(r["objective_final"] - results[0]["objective_final"])
                     for r in results[1:])
    kkt_max = max(r["kkt_residue"] for r in results)
    improved = all(r["objective_final"] <= r["objective_init"] - 1e-8
                   for r in results)
    ok = (w_spread <= 1e-6 and obj_spread <= 1e-8 and kkt_max <= 1e-6
          and improved and all(r["feasible"] for r in results))
    return {
        "pass": bool(ok),
        "runs": results,
        "weights_max_spread": float(w_spread),
        "objective_max_spread": float(obj_spread),
        "kkt_residue_max": float(kkt_max),
        "tol_weights": 1e-6, "tol_objective": 1e-8, "tol_kkt": 1e-6,
        "all_improved": bool(improved),
    }


# ---------------------------------------------------------------------------
# V6 -- degenerate identical components
# ---------------------------------------------------------------------------
def v6_degenerate(rng) -> dict:
    centers = np.array([[-1.5, 0.0], [-1.5, 0.0]])
    z = draw_from_mixture(rng, centers, np.array([0.5, 0.5]), 4000)
    logq, logp, logr, ind = make_inputs(z, centers, np.array([0.5, 0.5]), -1.1)
    f1 = m2_hat(logq, logp, logr, ind, np.array([0.7, 0.3]))
    f2 = m2_hat(logq, logp, logr, ind, np.array([0.3, 0.7]))
    H = m2_hessian(logq, logp, logr, ind, np.array([0.5, 0.5]))
    v = np.array([1.0, -1.0])
    flat_obj = abs(float(f1 - f2))
    flat_hess = abs(float(v @ H @ v))
    ok = flat_obj <= 1e-12 and flat_hess <= 1e-10
    return {"pass": bool(ok), "objective_flatness": flat_obj,
            "hessian_vT_H_v_along_simplex": flat_hess}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    # prereg self-check: config must match the task-doc locked values
    mismatches = []
    if config["mode_birth"]["tau_birth_main"] != TASK_LOCKED["tau_birth_main"]:
        mismatches.append("tau_birth_main")
    if config["mode_birth"]["tau_birth_lower_confidence"] != TASK_LOCKED["tau_birth_lower_confidence"]:
        mismatches.append("tau_birth_lower_confidence")
    if config["mode_birth"]["min_mode_observations"] != TASK_LOCKED["min_mode_observations"]:
        mismatches.append("min_mode_observations")
    if config["eta"]["main"] != TASK_LOCKED["eta_main"]:
        mismatches.append("eta_main")
    if config["budget"]["pilot_per_iteration"] != TASK_LOCKED["pilot_per_iteration"]:
        mismatches.append("pilot_per_iteration")
    if config["budget"]["max_adaptation_iterations"] != TASK_LOCKED["max_adaptation_iterations"]:
        mismatches.append("max_adaptation_iterations")
    if config["budget"]["final_eval_samples"] != TASK_LOCKED["final_eval_samples"]:
        mismatches.append("final_eval_samples")
    if config["seeds"] != TASK_LOCKED["seeds"]:
        mismatches.append("seeds")
    if mismatches:
        print(f"PREREG MISMATCH vs task doc: {mismatches}", file=sys.stderr)
        return 2

    rng = np.random.default_rng(SEED)
    v1 = v1_unbiasedness(rng, None)
    v23 = v2_v3_derivatives(rng)
    v4 = v4_convexity(rng)
    v5 = v5_optimizer(rng)
    v6 = v6_degenerate(rng)

    all_pass = (v1["pass"] and v23["pass"] and v4["pass"]
                and v5["pass"] and v6["pass"])
    record = {
        "schema_version": "raretopo-m1-theory-weight-check-v0",
        "config_id": config["config_id"],
        "h3_frozen_tag": config["h3_frozen_tag"],
        "git_commit": git_short_head(),
        "config_sha256": sha256_hex(CONFIG_PATH),
        "seed": SEED,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task_doc": config["task_doc"],
        "verifications": {
            "V1_unbiasedness": v1, "V2_V3_derivatives": v23,
            "V4_convexity": v4, "V5_optimizer_slsqp": v5,
            "V6_degenerate_flatness": v6,
        },
        "overall_pass": bool(all_pass),
        "note": "FD checks are constraint-respecting central differences along "
                "simplex tangent directions (module enforces the simplex).",
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(_py(record), indent=2), encoding="utf-8"
    )

    print(json.dumps(_py({
        "V1": {"pass": v1["pass"], "checks": [c["id"] + ":" + str(c["pass"])
                                             for c in v1["checks"]]},
        "V2_gradient_fd_max_rel": v23["V2"]["max_rel_err"],
        "V3_hessian": {"sym": v23["V3"]["symmetry_max_abs_diff"],
                       "eig_min": v23["V3"]["min_eig"],
                       "min_vHv": v23["V3"]["min_vT_H_v"],
                       "fd_max_rel": v23["V3"]["fd_gradient_max_rel_err"]},
        "V4_convexity_max_violation": v4["max_midpoint_violation"],
        "V5_slsqp": {"weight_spread": v5["weights_max_spread"],
                     "obj_spread": v5["objective_max_spread"],
                     "kkt_max": v5["kkt_residue_max"],
                     "all_improved": v5["all_improved"]},
        "V6_flatness": {"obj": v6["objective_flatness"],
                        "hess": v6["hessian_vT_H_v_along_simplex"]},
        "overall_pass": bool(all_pass),
        "output": str(OUT_PATH),
    }), indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())