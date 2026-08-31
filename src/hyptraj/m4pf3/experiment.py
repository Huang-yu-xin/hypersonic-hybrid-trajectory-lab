"""Locked PF3-A P11-anchor allocation experiment primitives."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

import numpy as np

from hyptraj.m1d.adaptation import draw_mix_pilot
from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal
from hyptraj.m3.gradient_estimator import variance_mass_importance
from hyptraj.m4pf2.experiment import clone_proposal
from hyptraj.m4pf3.diagnostics import (
    allocation_diagnostics,
    coverage_diagnostics,
    responsibility_matrix,
)


ARM_ORDER = ("A0", "A1")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_locks(repo: Path) -> tuple[dict, dict, dict]:
    root = repo / "configs" / "phase_m4pf3"
    return tuple(json.loads((root / name).read_text(encoding="utf-8"))
                 for name in ("m4pf3_protocol.json", "m4pf3_states.json",
                              "m4pf3_seeds.json"))


def validate_state_lock(repo: Path, lock: dict) -> list[dict]:
    source = repo / lock["source_path"]
    if sha256_file(source) != lock["source_sha256"]:
        raise RuntimeError("PF3 state source hash mismatch")
    if sha256_file(repo / lock["pf2_state_lock"]) != \
            lock["pf2_state_lock_sha256"]:
        raise RuntimeError("PF2 state lock changed")
    rows = json.loads(source.read_text(encoding="utf-8"))["states"]
    joined = "\n".join(row["state_id"] for row in rows).encode("utf-8")
    if hashlib.sha256(joined).hexdigest() != \
            lock["state_ids_sha256_ordered_utf8_newline_join"]:
        raise RuntimeError("PF3 ordered state IDs changed")
    if len(rows) != lock["expected_state_count"]:
        raise RuntimeError("PF3 state count changed")
    for label, count in lock["expected_class_counts"].items():
        if sum(row["class"] == label for row in rows) != count:
            raise RuntimeError(f"PF3 class count changed: {label}")
    return rows


def proposal_from_identity(identity: dict) -> CovGaussianMixtureProposal:
    covariances = tuple(np.asarray(c, dtype=float)
                        for c in identity["covariances"])
    eig_min = min(float(np.linalg.eigvalsh(c).min()) for c in covariances)
    return CovGaussianMixtureProposal(
        centers=np.asarray(identity["centers"], dtype=float),
        weights=np.asarray(identity["weights"], dtype=float),
        covs=covariances,
        component_mode_ids=None,
        legality_checked=eig_min >= 0.5,
        min_eig_sigma_minus_halfI=eig_min - 0.5,
    )


def p11_anchor(pf2_state: dict) -> CovGaussianMixtureProposal:
    base = proposal_from_identity(pf2_state["proposal_identity"])
    k = int(pf2_state["proposal_identity"]["component_index"])
    center = (np.asarray(base.centers[k], dtype=float)
              + np.asarray(pf2_state["update"]["mean"]["displacement"],
                           dtype=float))
    covariance = np.asarray(
        pf2_state["update"]["covariance"]["covariance"], dtype=float)
    return clone_proposal(base, k, center=center, covariance=covariance)


def proposal_identity(state_id: str, proposal: CovGaussianMixtureProposal) -> dict:
    return {
        "state_id": state_id,
        "anchor": "PF2_P11",
        "centers": np.asarray(proposal.centers).tolist(),
        "weights": np.asarray(proposal.weights).tolist(),
        "covariances": [np.asarray(c).tolist() for c in proposal.covs],
    }


def construct_allocation_gradient(state, anchor: CovGaussianMixtureProposal,
                                  seeds: list[int], n_per_seed: int,
                                  pilot_alpha: float) -> tuple[dict, dict]:
    alpha = np.asarray(anchor.weights, dtype=float)
    means = np.asarray(anchor.centers, dtype=float)
    covariances = tuple(np.asarray(c, dtype=float) for c in anchor.covs)
    collected = {name: [] for name in (
        "samples", "variance_mass", "responsibilities", "source_strata")}
    for seed in seeds:
        rng = np.random.default_rng([int(seed), 303])
        samples, logr, strata = draw_mix_pilot(
            rng, anchor, state.bench_cfg.logp, int(n_per_seed),
            float(pilot_alpha))
        logp = np.asarray(state.bench_cfg.logp(samples), dtype=float)
        indicators = (state.bench_cfg.label(samples) != "NOMINAL").astype(float)
        mass = variance_mass_importance(
            samples, alpha, means, covariances, logp, logr, indicators)
        responsibilities, _ = responsibility_matrix(
            samples, alpha, means, covariances)
        collected["samples"].append(samples)
        collected["variance_mass"].append(mass)
        collected["responsibilities"].append(responsibilities)
        collected["source_strata"].append(np.asarray(strata, dtype=np.int16))
    arrays = {name: np.concatenate(parts) for name, parts in collected.items()}
    allocation = allocation_diagnostics(
        arrays["variance_mass"], arrays["responsibilities"], alpha)
    allocation["M2_hat"] = float(arrays["variance_mass"].mean())
    allocation["n"] = int(arrays["variance_mass"].size)
    return allocation, arrays


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = np.asarray(values, dtype=float) - float(np.max(values))
    result = np.exp(shifted)
    return result / result.sum()


def allocation_step(alpha: np.ndarray, direction: np.ndarray,
                    eta_alpha: float = 0.20,
                    numerical_zero_threshold: float = 1e-12) -> dict:
    alpha = np.asarray(alpha, dtype=float)
    direction = np.asarray(direction, dtype=float)
    if alpha.shape != direction.shape or np.any(alpha <= 0.0):
        raise ValueError("invalid allocation-step inputs")
    norm = float(np.linalg.norm(direction))
    skipped = norm <= float(numerical_zero_threshold)
    delta_beta = (np.zeros_like(direction) if skipped else
                  float(eta_alpha) * direction / norm)
    updated = softmax(np.log(alpha) + delta_beta)
    tv = 0.5 * float(np.abs(updated - alpha).sum())
    kl = float(np.sum(updated * np.log(updated / alpha)))
    return {
        "alpha": alpha,
        "alpha_prime": updated,
        "direction": direction,
        "direction_norm": norm,
        "delta_beta": delta_beta,
        "delta_beta_norm": float(np.linalg.norm(delta_beta)),
        "direction_dot_delta_beta": float(direction @ delta_beta),
        "TV_alpha_prime_alpha": tv,
        "KL_alpha_prime_alpha": kl,
        "allocation_update_skipped_numerical_zero": skipped,
        "eta_alpha": float(eta_alpha),
        "numerical_zero_threshold": float(numerical_zero_threshold),
    }


def reweighted_post_update_diagnostics(arrays: dict,
                                       anchor: CovGaussianMixtureProposal,
                                       updated_alpha: np.ndarray) -> dict:
    alpha = np.asarray(anchor.weights, dtype=float)
    means = np.asarray(anchor.centers, dtype=float)
    covariances = tuple(np.asarray(c, dtype=float) for c in anchor.covs)
    responsibilities0, logq0 = responsibility_matrix(
        arrays["samples"], alpha, means, covariances)
    responsibilities1, logq1 = responsibility_matrix(
        arrays["samples"], np.asarray(updated_alpha), means, covariances)
    mass1 = arrays["variance_mass"] * np.exp(logq0 - logq1)
    allocation1 = allocation_diagnostics(
        mass1, responsibilities1, np.asarray(updated_alpha))
    coverage0, _, _ = coverage_diagnostics(
        arrays["samples"], arrays["variance_mass"], means, covariances,
        arrays["source_strata"])
    coverage1, _, _ = coverage_diagnostics(
        arrays["samples"], mass1, means, covariances,
        arrays["source_strata"])
    return {
        "allocation_after": allocation1,
        "coverage_A0": coverage0,
        "coverage_A1_reweighted": coverage1,
        "M2_A0_hat": float(np.mean(arrays["variance_mass"])),
        "M2_A1_reweighted_hat": float(np.mean(mass1)),
        "M2_reweighted_log_ratio": float(
            math.log(np.mean(mass1) / np.mean(arrays["variance_mass"]))),
        "responsibility_replay_error": float(np.max(np.abs(
            responsibilities0 - arrays["responsibilities"]))),
    }


def build_allocation_arms(anchor: CovGaussianMixtureProposal,
                          allocation: dict, protocol: dict,
                          arrays: dict | None = None) -> tuple[dict, dict]:
    lock = protocol["allocation_update"]
    update = allocation_step(
        np.asarray(anchor.weights), allocation["descent_direction"],
        eta_alpha=float(lock["eta_alpha"]),
        numerical_zero_threshold=float(lock["numerical_zero_threshold"]))
    a1 = CovGaussianMixtureProposal(
        centers=np.asarray(anchor.centers).copy(),
        weights=np.asarray(update["alpha_prime"]).copy(),
        covs=tuple(np.asarray(c).copy() for c in anchor.covs),
        component_mode_ids=anchor.component_mode_ids,
        legality_checked=anchor.legality_checked,
        min_eig_sigma_minus_halfI=anchor.min_eig_sigma_minus_halfI,
    )
    if arrays is not None:
        update["post_update_diagnostics"] = reweighted_post_update_diagnostics(
            arrays, anchor, update["alpha_prime"])
    return {"A0": anchor, "A1": a1}, update


def select_freeoracle(candidate_records: dict[str, list[dict]],
                      probabilities: dict[str, float]) -> str:
    scores = {
        arm: float(statistics.median(
            max(0.0, float(row["M2"]) - float(probabilities[arm]) ** 2)
            for row in candidate_records[arm]))
        for arm in ARM_ORDER
    }
    best = min(scores.values())
    for arm in ARM_ORDER:
        if math.isclose(scores[arm], best, rel_tol=0.0, abs_tol=1e-15):
            return arm
    raise RuntimeError("PF3 FreeOracle selection failed")


__all__ = [
    "ARM_ORDER", "allocation_step", "build_allocation_arms",
    "construct_allocation_gradient", "load_locks", "p11_anchor",
    "proposal_from_identity", "proposal_identity",
    "reweighted_post_update_diagnostics", "select_freeoracle",
    "sha256_file", "softmax", "validate_state_lock",
]
