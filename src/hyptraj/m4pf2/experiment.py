"""Locked PF2 anchor, joint-cell, gradient and factorial primitives."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

import numpy as np

from hyptraj.m1d.adaptation import draw_mix_pilot
from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal
from hyptraj.m3.covariance_gradient import MixtureSpec, component_responsibility
from hyptraj.m3.gradient_estimator import variance_mass_importance
from hyptraj.m4pf.gradient import matrix_gradient_estimate, spectral_diagnostics
from hyptraj.m4pf1.experiment import build_structured_proposal
from hyptraj.m4pf2.mean_gradient import (
    mean_gradient_estimate,
    whitened_mean_step,
)

CELL_ORDER = ("P00", "P10", "P01", "P11")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_locks(repo: Path) -> tuple[dict, dict, dict]:
    root = repo / "configs" / "phase_m4pf2"
    return tuple(json.loads((root / name).read_text(encoding="utf-8"))
                 for name in ("m4pf2_protocol.json", "m4pf2_states.json",
                              "m4pf2_seeds.json"))


def validate_state_lock(repo: Path, lock: dict) -> list[dict]:
    source = repo / lock["source_path"]
    anchor_source = repo / lock["anchor_action_source"]
    if sha256_file(source) != lock["source_sha256"]:
        raise RuntimeError("PF2 state source hash mismatch")
    if sha256_file(anchor_source) != lock["anchor_action_source_sha256"]:
        raise RuntimeError("PF2 anchor source hash mismatch")
    rows = json.loads(source.read_text(encoding="utf-8"))["states"]
    joined = "\n".join(row["state_id"] for row in rows).encode("utf-8")
    if hashlib.sha256(joined).hexdigest() != \
            lock["state_ids_sha256_ordered_utf8_newline_join"]:
        raise RuntimeError("PF2 ordered state IDs changed")
    if len(rows) != lock["expected_state_count"]:
        raise RuntimeError("PF2 state count changed")
    for label, count in lock["expected_class_counts"].items():
        if sum(row["class"] == label for row in rows) != count:
            raise RuntimeError(f"PF2 class count changed: {label}")
    return rows


def clone_proposal(base: CovGaussianMixtureProposal, component_index: int,
                   *, center: np.ndarray | None = None,
                   covariance: np.ndarray | None = None) \
        -> CovGaussianMixtureProposal:
    centers = np.asarray(base.centers, dtype=float).copy()
    covs = [np.asarray(c, dtype=float).copy() for c in base.covs]
    k = int(component_index)
    if center is not None:
        centers[k] = np.asarray(center, dtype=float)
    if covariance is not None:
        covs[k] = np.asarray(covariance, dtype=float)
    eig_min = min(float(np.linalg.eigvalsh(0.5 * (c + c.T)).min())
                  for c in covs)
    return CovGaussianMixtureProposal(
        centers=centers, weights=base.weights.copy(), covs=tuple(covs),
        component_mode_ids=base.component_mode_ids,
        legality_checked=eig_min >= 0.5,
        min_eig_sigma_minus_halfI=eig_min - 0.5)


def anchor_proposal(state, selected_arm: str, eta: float = 0.20) \
        -> CovGaussianMixtureProposal:
    if selected_arm not in ("widen", "shrink"):
        raise ValueError("PF2 locked anchors are widen or shrink")
    shift = float(eta) if selected_arm == "widen" else -float(eta)
    base = state.proposal()
    covariance = state.s2 * math.exp(shift) * np.eye(state.dim)
    return clone_proposal(base, state.component_index, covariance=covariance)


def _invsqrt(covariance: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh(0.5 * (covariance + covariance.T))
    if np.any(vals <= 0.0):
        raise ValueError("anchor covariance is not SPD")
    return (vecs * (1.0 / np.sqrt(vals))[None, :]) @ vecs.T


def construct_joint_gradients(state, anchor: CovGaussianMixtureProposal,
                              seeds: list[int], n_per_seed: int,
                              alpha: float) -> tuple[dict, dict]:
    """Generate fresh anchor samples and estimate both PF2 gradients."""
    pi = np.asarray(anchor.weights, dtype=float)
    means = np.asarray(anchor.centers, dtype=float)
    covs = tuple(np.asarray(c, dtype=float) for c in anchor.covs)
    spec = MixtureSpec(pi, means, covs)
    k = int(state.component_index)
    invsqrt = _invsqrt(covs[k])
    collected = {name: [] for name in (
        "samples", "variance_mass", "responsibility", "whitened",
        "source_strata")}
    for seed in seeds:
        rng = np.random.default_rng([int(seed), 101])
        samples, logr, strata = draw_mix_pilot(
            rng, anchor, state.bench_cfg.logp, int(n_per_seed), float(alpha))
        logp = np.asarray(state.bench_cfg.logp(samples), dtype=float)
        labels = state.bench_cfg.label(samples)
        indicators = (labels != "NOMINAL").astype(float)
        mass = variance_mass_importance(samples, pi, means, covs, logp, logr,
                                        indicators)
        responsibility = component_responsibility(spec, samples, k)
        whitened = (samples - means[k][None, :]) @ invsqrt
        collected["samples"].append(samples)
        collected["variance_mass"].append(mass)
        collected["responsibility"].append(responsibility)
        collected["whitened"].append(whitened)
        collected["source_strata"].append(np.asarray(strata, dtype=np.int16))
    arrays = {name: np.concatenate(parts) for name, parts in collected.items()}
    mean = mean_gradient_estimate(
        arrays["variance_mass"], arrays["responsibility"], arrays["whitened"])
    covariance = matrix_gradient_estimate(
        arrays["variance_mass"], arrays["responsibility"], arrays["whitened"])
    covariance["spectral"] = spectral_diagnostics(
        covariance["gradient_matrix"])
    return {"mean": mean, "covariance": covariance}, arrays


class _AnchorState:
    def __init__(self, proposal: CovGaussianMixtureProposal, component_index: int):
        self._proposal = proposal
        self.component_index = int(component_index)

    def proposal(self) -> CovGaussianMixtureProposal:
        return self._proposal


def build_factorial_cells(state, anchor: CovGaussianMixtureProposal,
                          mean_a: np.ndarray, covariance_g: np.ndarray,
                          protocol: dict) -> tuple[dict, dict]:
    mean_lock = protocol["mean_update"]
    cov_lock = protocol["covariance_update"]
    k = int(state.component_index)
    mean = whitened_mean_step(
        anchor.covs[k], mean_a,
        delta_mu=float(mean_lock["delta_mu_mahalanobis"]),
        numerical_zero_threshold=float(mean_lock["numerical_zero_threshold"]))
    p01, covariance = build_structured_proposal(
        _AnchorState(anchor, k), covariance_g, rank=1,
        update_lock={
            "raw_gradient_eigenvalue_clip_abs":
                cov_lock["raw_gradient_eigenvalue_clip_abs"],
            "eta": cov_lock["eta_sigma"],
            "max_abs_log_step": cov_lock["max_abs_log_step"],
            "condition_number_ceiling": cov_lock["condition_number_ceiling"],
            "minimum_covariance_eigenvalue":
                cov_lock["minimum_covariance_eigenvalue"],
        })
    shifted_center = anchor.centers[k] + mean["displacement"]
    p10 = clone_proposal(anchor, k, center=shifted_center)
    p11 = clone_proposal(anchor, k, center=shifted_center,
                         covariance=p01.covs[k])
    cells = {"P00": anchor, "P10": p10, "P01": p01, "P11": p11}
    valid = bool(covariance["valid"] and
                 all(prop.legality_checked for prop in cells.values()))
    return cells, {"mean": mean, "covariance": covariance,
                   "valid": valid,
                   "joint_gradient_recomputed": False,
                   "joint_application": "simultaneous"}


def select_freeoracle(candidate_records: dict[str, list[dict]],
                      probabilities: dict[str, float]) -> str:
    scores = {}
    for cell in CELL_ORDER:
        p = float(probabilities[cell])
        scores[cell] = float(statistics.median(
            max(0.0, float(row["M2"]) - p * p)
            for row in candidate_records[cell]))
    best = min(scores.values())
    for cell in CELL_ORDER:
        if math.isclose(scores[cell], best, rel_tol=0.0, abs_tol=1e-15):
            return cell
    raise RuntimeError("FreeOracle selection failed")


def factorial_contrasts(state_rows: list[dict]) -> list[dict]:
    by_state = {}
    for row in state_rows:
        by_state.setdefault(row["state_id"], {})[row["cell"]] = row
    output = []
    for state_id, cells in sorted(by_state.items()):
        if set(cells) != set(CELL_ORDER):
            raise ValueError(f"incomplete factorial state: {state_id}")
        logv = {cell: math.log(float(cells[cell]["VRF_budget"]))
                for cell in CELL_ORDER}
        mean0 = logv["P10"] - logv["P00"]
        mean1 = logv["P11"] - logv["P01"]
        cov0 = logv["P01"] - logv["P00"]
        cov1 = logv["P11"] - logv["P10"]
        output.append({
            "state_id": state_id,
            "action_class": cells["P00"]["action_class"],
            "mean_effect_without_covariance": mean0,
            "mean_effect_with_covariance": mean1,
            "covariance_effect_without_mean": cov0,
            "covariance_effect_with_mean": cov1,
            "interaction": mean1 - mean0,
        })
    return output


__all__ = [
    "CELL_ORDER", "anchor_proposal", "build_factorial_cells",
    "clone_proposal", "construct_joint_gradients", "factorial_contrasts",
    "load_locks", "select_freeoracle", "sha256_file",
    "validate_state_lock",
]
