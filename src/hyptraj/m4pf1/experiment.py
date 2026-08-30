"""Locked PF1 proposal construction, evaluation and accounting primitives."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

import numpy as np

from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal
from hyptraj.m3.covariance_gradient import MixtureSpec, component_responsibility
from hyptraj.m3.gradient_estimator import variance_mass_importance
from hyptraj.m3ca.metrics import budget_vrf
from hyptraj.m3d.adaptation import draw_online_pilot
from hyptraj.m4pf.gradient import (
    matrix_gradient_estimate,
    spectral_diagnostics,
    spd_log_covariance_update,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_locks(repo: Path) -> tuple[dict, dict, dict]:
    root = repo / "configs" / "phase_m4pf1"
    protocol = json.loads((root / "m4pf1_protocol.json").read_text(
        encoding="utf-8"))
    states = json.loads((root / "m4pf1_states.json").read_text(
        encoding="utf-8"))
    seeds = json.loads((root / "m4pf1_seeds.json").read_text(
        encoding="utf-8"))
    return protocol, states, seeds


def validate_state_lock(repo: Path, lock: dict) -> list[dict]:
    source = repo / lock["source_path"]
    if sha256_file(source) != lock["source_sha256"]:
        raise RuntimeError("PF1 state source hash mismatch")
    doc = json.loads(source.read_text(encoding="utf-8"))
    rows = list(doc["states"])
    joined = "\n".join(row["state_id"] for row in rows).encode("utf-8")
    actual = hashlib.sha256(joined).hexdigest()
    if actual != lock["state_ids_sha256_ordered_utf8_newline_join"]:
        raise RuntimeError("PF1 ordered state-id hash mismatch")
    if len(rows) != int(lock["expected_state_count"]):
        raise RuntimeError("PF1 state count mismatch")
    for label, expected in lock["expected_class_counts"].items():
        if sum(row["class"] == label for row in rows) != int(expected):
            raise RuntimeError(f"PF1 class split mismatch: {label}")
    return rows


def _invsqrt(covariance: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(0.5 * (covariance + covariance.T))
    if np.any(vals <= 0.0) or not np.all(np.isfinite(vals)):
        raise ValueError("covariance is not SPD")
    return (vecs * (1.0 / np.sqrt(vals))[None, :]) @ vecs.T


def estimate_pooled_gradient(st, seeds: list[int], n_per_seed: int,
                             alpha: float) -> dict:
    """Generate the preregistered audit-only pilots and pool sample factors."""
    prop = st.proposal()
    pi = np.asarray(prop.weights, dtype=float)
    means = np.asarray(prop.centers, dtype=float)
    covs = tuple(np.asarray(c, dtype=float) for c in prop.covs)
    spec = MixtureSpec(pi, means, covs)
    k = int(st.component_index)
    invsqrt = _invsqrt(covs[k])
    arrays = {"a": [], "r": [], "z": []}
    for seed in seeds:
        samples, logp, logr, _strata = draw_online_pilot(
            st, int(seed), int(n_per_seed), float(alpha))
        labels = st.bench_cfg.label(samples)
        indicators = (labels != "NOMINAL").astype(float)
        a = variance_mass_importance(samples, pi, means, covs, logp, logr,
                                     indicators)
        resp = component_responsibility(spec, samples, k)
        white = (samples - means[k][None, :]) @ invsqrt
        arrays["a"].append(a)
        arrays["r"].append(resp)
        arrays["z"].append(white)
    result = matrix_gradient_estimate(
        np.concatenate(arrays["a"]), np.concatenate(arrays["r"]),
        np.concatenate(arrays["z"]))
    result["spectral"] = spectral_diagnostics(result["gradient_matrix"])
    result["seeds"] = [int(seed) for seed in seeds]
    result["n_per_seed"] = int(n_per_seed)
    return result


def _clip_gradient_eigenvalues(gradient: np.ndarray, bound: float) -> np.ndarray:
    vals, vecs = np.linalg.eigh(0.5 * (gradient + gradient.T))
    vals = np.clip(vals, -float(bound), float(bound))
    return (vecs * vals[None, :]) @ vecs.T


def build_structured_proposal(st, gradient: np.ndarray, rank: int,
                              update_lock: dict) -> tuple[CovGaussianMixtureProposal, dict]:
    """Apply the frozen rank-r normalized matrix-exponential update."""
    if int(rank) not in (1, 2):
        raise ValueError("PF1 permits only rank 1 or 2")
    base = st.proposal()
    k = int(st.component_index)
    clipped_g = _clip_gradient_eigenvalues(
        np.asarray(gradient, dtype=float),
        float(update_lock["raw_gradient_eigenvalue_clip_abs"]))
    update = spd_log_covariance_update(
        np.asarray(base.covs[k], dtype=float), clipped_g,
        eta=float(update_lock["eta"]), rank=int(rank),
        normalize_frobenius=True,
        max_abs_log_step=float(update_lock["max_abs_log_step"]),
        condition_number_ceiling=float(update_lock["condition_number_ceiling"]))
    covariance = np.asarray(update["covariance"], dtype=float)
    eig = np.linalg.eigvalsh(covariance)
    valid = bool(
        np.all(np.isfinite(covariance)) and
        float(eig.min()) >= float(update_lock["minimum_covariance_eigenvalue"]) and
        float(update["condition_number"]) <=
        float(update_lock["condition_number_ceiling"]))
    update["minimum_eigenvalue_gate_passed"] = bool(
        float(eig.min()) >= float(update_lock["minimum_covariance_eigenvalue"]))
    update["valid"] = valid
    if not valid:
        covariance = np.asarray(base.covs[k], dtype=float).copy()
        update["fallback_to_base"] = True
    else:
        update["fallback_to_base"] = False
    covs = [np.asarray(c, dtype=float).copy() for c in base.covs]
    covs[k] = covariance
    min_eig_all = min(float(np.linalg.eigvalsh(c).min()) for c in covs)
    proposal = CovGaussianMixtureProposal(
        centers=base.centers.copy(), weights=base.weights.copy(),
        covs=tuple(covs), component_mode_ids=base.component_mode_ids,
        legality_checked=valid,
        min_eig_sigma_minus_halfI=min_eig_all - 0.5)
    return proposal, update


def tail_diagnostics(weights: np.ndarray) -> dict:
    weights = np.asarray(weights, dtype=float).reshape(-1)
    finite = np.isfinite(weights)
    nonfinite = int((~finite).sum())
    safe = np.where(finite & (weights >= 0.0), weights, 0.0)
    total = float(safe.sum())
    sumsq = float(np.sum(safe ** 2))
    ess = float(total ** 2 / sumsq) if sumsq > 0.0 else 0.0
    ordered = np.sort(safe)[::-1]

    def top_mass(frac: float) -> float:
        if total <= 0.0:
            return 0.0
        count = max(1, int(math.ceil(frac * ordered.size)))
        return float(ordered[:count].sum() / total)

    return {
        "ESS": ess,
        "max_normalized_weight": float(ordered[0] / total)
        if total > 0.0 and ordered.size else 0.0,
        "top_1pct_weight_mass": top_mass(0.01),
        "top_0_1pct_weight_mass": top_mass(0.001),
        "nonfinite_weights": nonfinite,
    }


def evaluate_proposal(prop: CovGaussianMixtureProposal, bench_cfg,
                      rng_key: list[int], n_eval: int,
                      n_batches: int) -> dict:
    """Evaluate one arm on the frozen M3-BV2 CRN draw order."""
    if int(n_eval) % int(n_batches):
        raise ValueError("n_eval must be divisible by n_batches")
    n_batch = int(n_eval) // int(n_batches)
    rng = np.random.default_rng([int(x) for x in rng_key])
    weights = []
    event_underflow = 0
    for _ in range(int(n_batches)):
        comp = rng.choice(prop.n_components, size=n_batch, p=prop.weights)
        eps = rng.standard_normal((n_batch, prop.centers.shape[1]))
        z = prop.centers[comp] + np.einsum(
            "njk,nk->nj", np.stack([prop.chols[c] for c in comp]), eps)
        labels = bench_cfg.label(z)
        event = labels != "NOMINAL"
        logw = np.asarray(bench_cfg.logp(z), dtype=float) - prop.log_density(z)
        w = np.zeros(n_batch, dtype=float)
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            w[event] = np.exp(logw[event])
        event_underflow += int(np.sum(event & (w == 0.0)))
        weights.append(w)
    all_weights = np.concatenate(weights)
    diag = tail_diagnostics(all_weights)
    diag["event_weight_underflow_count"] = int(event_underflow)
    diag.update({
        "M2": float(np.mean(all_weights ** 2)),
        "P_hat": float(np.mean(all_weights)),
        "n_eval": int(n_eval),
        "rng_key": [int(x) for x in rng_key],
    })
    return diag


def freeoracle_candidate(candidate_records: dict[str, list[dict]],
                         p_by_candidate: dict[str, float]) -> str:
    """Locked statewise selector: minimum median estimator variance, base tie."""
    scores = {}
    for name, records in candidate_records.items():
        p_value = float(p_by_candidate[name])
        scores[name] = float(statistics.median(
            max(0.0, float(row["M2"]) - p_value ** 2) for row in records))
    best = min(scores.values())
    tied = sorted(name for name, value in scores.items()
                  if math.isclose(value, best, rel_tol=0.0, abs_tol=1e-15))
    return "base" if "base" in tied else tied[0]


def attach_vrf(records: list[dict], p_ref: float, p_selected: float,
               deployable_budget: int) -> list[float]:
    return [budget_vrf(float(p_ref), float(row["M2"]), float(p_selected),
                       int(row["n_eval"]), int(deployable_budget))
            for row in records]


__all__ = [
    "attach_vrf", "build_structured_proposal", "estimate_pooled_gradient",
    "evaluate_proposal", "freeoracle_candidate", "load_locks",
    "sha256_file", "tail_diagnostics", "validate_state_lock",
]
