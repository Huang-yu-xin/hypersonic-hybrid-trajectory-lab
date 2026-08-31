"""Zero-simulator PF3-0 allocation, coverage and birth-score primitives."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.special import logsumexp
from scipy.stats import chi2, t


def _as_proposal(identity: dict) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    alpha = np.asarray(identity["weights"], dtype=float)
    means = np.asarray(identity["centers"], dtype=float)
    covariances = tuple(np.asarray(c, dtype=float)
                        for c in identity["covariances"])
    if means.shape[0] != alpha.size or len(covariances) != alpha.size:
        raise ValueError("proposal component count mismatch")
    if not np.isclose(alpha.sum(), 1.0, rtol=0.0, atol=1e-12):
        raise ValueError("proposal weights do not sum to one")
    if np.any(alpha <= 0.0):
        raise ValueError("proposal weights must be positive")
    return alpha, means, covariances


def gaussian_log_density(samples: np.ndarray, mean: np.ndarray,
                         covariance: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=float)
    mean = np.asarray(mean, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    sign, logdet = np.linalg.slogdet(covariance)
    if sign <= 0.0:
        raise ValueError("covariance must be SPD")
    centered = samples - mean[None, :]
    solved = np.linalg.solve(covariance, centered.T).T
    quadratic = np.einsum("ni,ni->n", centered, solved)
    return -0.5 * (samples.shape[1] * math.log(2.0 * math.pi)
                   + logdet + quadratic)


def responsibility_matrix(samples: np.ndarray, alpha: np.ndarray,
                          means: np.ndarray,
                          covariances: tuple[np.ndarray, ...]) \
        -> tuple[np.ndarray, np.ndarray]:
    log_components = np.column_stack([
        math.log(float(alpha[k]))
        + gaussian_log_density(samples, means[k], covariances[k])
        for k in range(alpha.size)
    ])
    logq = logsumexp(log_components, axis=1)
    responsibilities = np.exp(log_components - logq[:, None])
    return responsibilities, logq


def normalized_variance_mass(variance_mass: np.ndarray) -> np.ndarray:
    mass = np.asarray(variance_mass, dtype=float)
    if mass.ndim != 1 or not np.all(np.isfinite(mass)) or np.any(mass < 0.0):
        raise ValueError("variance mass must be a finite nonnegative vector")
    total = float(mass.sum())
    if total <= 0.0:
        raise ValueError("variance mass is zero")
    return mass / total


def entropy(probability: np.ndarray) -> float:
    probability = np.asarray(probability, dtype=float)
    positive = probability > 0.0
    return float(-np.sum(probability[positive] * np.log(probability[positive])))


def allocation_diagnostics(variance_mass: np.ndarray,
                           responsibilities: np.ndarray,
                           alpha: np.ndarray,
                           starvation_epsilon: float = 1e-15) -> dict:
    weights = normalized_variance_mass(variance_mass)
    responsibilities = np.asarray(responsibilities, dtype=float)
    alpha = np.asarray(alpha, dtype=float)
    if responsibilities.shape != (weights.size, alpha.size):
        raise ValueError("responsibility shape mismatch")
    if not np.allclose(responsibilities.sum(axis=1), 1.0,
                       rtol=0.0, atol=1e-10):
        raise ValueError("responsibilities do not normalize")
    r_bar = weights @ responsibilities
    direction = r_bar - alpha
    mismatch = 0.5 * float(np.abs(direction).sum())
    h_alpha = entropy(alpha)
    h_rbar = entropy(r_bar)
    return {
        "alpha": alpha,
        "r_bar": r_bar,
        "descent_direction": direction,
        "direction_sum": float(direction.sum()),
        "A_alloc": mismatch,
        "starvation_ratio": r_bar / (alpha + float(starvation_epsilon)),
        "H_alpha": h_alpha,
        "H_r_bar": h_rbar,
        "N_eff_alpha": math.exp(h_alpha),
        "N_eff_r_bar": math.exp(h_rbar),
    }


def mahalanobis_squared(samples: np.ndarray, means: np.ndarray,
                        covariances: tuple[np.ndarray, ...]) -> np.ndarray:
    values = []
    for mean, covariance in zip(means, covariances):
        centered = np.asarray(samples, dtype=float) - mean[None, :]
        solved = np.linalg.solve(covariance, centered.T).T
        values.append(np.einsum("ni,ni->n", centered, solved))
    return np.column_stack(values)


def _top_tail(weights: np.ndarray, outside: np.ndarray,
              fraction: float) -> dict:
    count = max(1, int(math.ceil(weights.size * float(fraction))))
    order = np.argsort(-weights, kind="stable")[:count]
    selected_mass = float(weights[order].sum())
    uncovered = float(weights[order][outside[order]].sum())
    return {
        "sample_count": count,
        "total_tilted_mass": selected_mass,
        "uncovered_fraction_within_tail":
            uncovered / selected_mass if selected_mass > 0.0 else 0.0,
    }


def coverage_diagnostics(samples: np.ndarray, variance_mass: np.ndarray,
                         means: np.ndarray,
                         covariances: tuple[np.ndarray, ...],
                         source_strata: np.ndarray) -> tuple[dict, np.ndarray, np.ndarray]:
    samples = np.asarray(samples, dtype=float)
    weights = normalized_variance_mass(variance_mass)
    source_strata = np.asarray(source_strata, dtype=int)
    if source_strata.shape != (samples.shape[0],):
        raise ValueError("source-strata shape mismatch")
    distances = mahalanobis_squared(samples, means, covariances)
    nearest = np.argmin(distances, axis=1)
    d_min = distances[np.arange(samples.shape[0]), nearest]
    dimension = samples.shape[1]
    tau99 = float(chi2.ppf(0.99, dimension))
    tau999 = float(chi2.ppf(0.999, dimension))
    outside99 = d_min > tau99
    outside999 = d_min > tau999
    nearest_tilted = [float(weights[nearest == k].sum())
                      for k in range(means.shape[0])]
    nearest_raw = [float(np.mean(nearest == k)) for k in range(means.shape[0])]
    strata = []
    for label in sorted(np.unique(source_strata)):
        mask = source_strata == label
        total_tilted = float(weights[mask].sum())
        strata.append({
            "source_stratum": int(label),
            "raw_fraction": float(mask.mean()),
            "tilted_mass": total_tilted,
            "U99_contribution": float(weights[mask & outside99].sum()),
            "U999_contribution": float(weights[mask & outside999].sum()),
        })
    return ({
        "dimension": dimension,
        "tau99": tau99,
        "tau999": tau999,
        "raw_outside99": float(outside99.mean()),
        "raw_outside999": float(outside999.mean()),
        "U99": float(weights[outside99].sum()),
        "U999": float(weights[outside999].sum()),
        "d_min2_median_raw": float(np.median(d_min)),
        "d_min2_q99_raw": float(np.quantile(d_min, 0.99)),
        "d_min2_tilted_mean": float(weights @ d_min),
        "top_1pct": _top_tail(weights, outside99, 0.01),
        "top_0_1pct": _top_tail(weights, outside99, 0.001),
        "nearest_component_tilted_mass": nearest_tilted,
        "nearest_component_raw_fraction": nearest_raw,
        "source_strata": strata,
    }, d_min, nearest)


def nearest_covariance_index(center: np.ndarray, means: np.ndarray,
                             covariances: tuple[np.ndarray, ...]) -> int:
    values = []
    for mean, covariance in zip(means, covariances):
        delta = np.asarray(center) - mean
        values.append(float(delta @ np.linalg.solve(covariance, delta)))
    return int(np.argmin(values))


def candidate_centres(samples: np.ndarray, variance_mass: np.ndarray,
                      d_min: np.ndarray, tau99: float,
                      source_strata: np.ndarray,
                      min_stratum_share: float,
                      min_stratum_samples: int) -> list[dict]:
    samples = np.asarray(samples, dtype=float)
    mass = np.asarray(variance_mass, dtype=float)
    source_strata = np.asarray(source_strata, dtype=int)
    uncovered = (np.asarray(d_min) > float(tau99)) & (mass > 0.0)
    if not np.any(uncovered):
        return []
    local_mass = mass[uncovered]
    local_samples = samples[uncovered]
    barycentre = np.average(local_samples, axis=0, weights=local_mass)
    distance = np.sum((local_samples - barycentre[None, :]) ** 2, axis=1)
    medoid = local_samples[int(np.argmin(distance))]
    candidates = [
        {"candidate_id": "G1", "generator": "weighted_barycentre",
         "centre": barycentre},
        {"candidate_id": "G2", "generator": "weighted_squared_euclidean_medoid",
         "centre": medoid},
    ]
    uncovered_total = float(local_mass.sum())
    ranked = []
    for label in sorted(np.unique(source_strata[uncovered])):
        mask = uncovered & (source_strata == label)
        count = int(np.count_nonzero(mask))
        stratum_mass = float(mass[mask].sum())
        share = stratum_mass / uncovered_total
        if count >= int(min_stratum_samples) and share >= float(min_stratum_share):
            ranked.append((share, int(label), mask))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    for ordinal, (share, label, mask) in enumerate(ranked[:2], 3):
        candidates.append({
            "candidate_id": f"G{ordinal}",
            "generator": "source_stratum_weighted_barycentre",
            "source_stratum": label,
            "source_stratum_uncovered_share": share,
            "centre": np.average(samples[mask], axis=0, weights=mass[mask]),
        })
    return candidates


def birth_score(samples: np.ndarray, variance_mass: np.ndarray,
                logq: np.ndarray, center: np.ndarray,
                covariance: np.ndarray, stream_count: int = 4,
                confidence: float = 0.95) -> dict:
    samples = np.asarray(samples, dtype=float)
    mass = np.asarray(variance_mass, dtype=float)
    log_ratio = gaussian_log_density(samples, center, covariance) - logq

    def score(block_mass: np.ndarray, block_log_ratio: np.ndarray) -> float:
        positive = block_mass > 0.0
        if not np.any(positive):
            return float("nan")
        log_weights = np.log(block_mass[positive])
        log_expectation = (logsumexp(log_weights + block_log_ratio[positive])
                           - logsumexp(log_weights))
        return float(np.exp(log_expectation) - 1.0)

    pooled = score(mass, log_ratio)
    if mass.size % int(stream_count) != 0:
        raise ValueError("archive cannot be split into equal construction streams")
    per_stream = np.asarray([
        score(part_mass, part_ratio)
        for part_mass, part_ratio in zip(
            np.split(mass, int(stream_count)),
            np.split(log_ratio, int(stream_count)))
    ])
    finite = per_stream[np.isfinite(per_stream)]
    if finite.size >= 2:
        standard_error = float(np.std(finite, ddof=1) / math.sqrt(finite.size))
        lower = float(np.mean(finite) - t.ppf(confidence, finite.size - 1)
                      * standard_error)
    else:
        lower = float("nan")
    return {
        "birth_score": pooled,
        "stream_scores": per_stream,
        "one_sided_95_t_lcb": lower,
        "point_positive": bool(pooled > 0.0),
        "admitted": bool(pooled > 0.0 and np.isfinite(lower) and lower > 0.0),
    }


def build_birth_candidates(samples: np.ndarray, variance_mass: np.ndarray,
                           source_strata: np.ndarray, identity: dict,
                           coverage: dict, d_min: np.ndarray,
                           protocol: dict) -> list[dict]:
    alpha, means, covariances = _as_proposal(identity)
    _, logq = responsibility_matrix(samples, alpha, means, covariances)
    lock = protocol["candidate_library"]
    candidates = candidate_centres(
        samples, variance_mass, d_min, coverage["tau99"], source_strata,
        lock["stratum_min_share_of_uncovered_mass"],
        lock["stratum_min_positive_mass_samples"])
    mass_weights = normalized_variance_mass(variance_mass)
    uncovered = d_min > float(coverage["tau99"])
    uncovered_mass = float(mass_weights[uncovered].sum())
    output = []
    for candidate in candidates:
        center = np.asarray(candidate["centre"], dtype=float)
        covariance_index = nearest_covariance_index(
            center, means, covariances)
        covariance = covariances[covariance_index]
        score = birth_score(samples, variance_mass, logq, center, covariance)
        candidate_distance = mahalanobis_squared(
            samples, center[None, :], (covariance,))[:, 0]
        represented = float(mass_weights[
            uncovered & (candidate_distance <= coverage["tau99"])].sum())
        output.append({
            **candidate,
            "centre": center,
            "covariance_source_component": covariance_index,
            "covariance": covariance,
            "represented_uncovered_mass": represented,
            "represented_fraction_of_uncovered_mass":
                represented / uncovered_mass if uncovered_mass > 0.0 else 0.0,
            **score,
        })
    return output


def routing_verdict(state_rows: list[dict], protocol: dict,
                    multiplier: float = 1.0) -> dict:
    allocation = protocol["allocation"]
    coverage = protocol["coverage"]
    a_values = np.asarray([row["A_alloc"] for row in state_rows], dtype=float)
    u99 = np.asarray([row["U99"] for row in state_rows], dtype=float)
    u999 = np.asarray([row["U999"] for row in state_rows], dtype=float)
    top1 = np.asarray([row["top_1pct_uncovered_fraction"]
                       for row in state_rows], dtype=float)
    allocation_count = int(np.count_nonzero(
        a_values >= multiplier * allocation["material_state_threshold"]))
    coverage_count = int(np.count_nonzero(
        u99 >= multiplier * coverage["material_state_u99"]))
    allocation_material = bool(
        np.median(a_values) >= multiplier * allocation["material_median"]
        or allocation_count >= allocation["material_state_count"])
    coverage_material = bool(
        np.median(u99) >= multiplier * coverage["material_median_u99"]
        or coverage_count >= coverage["material_state_count"])
    severe = bool(
        np.any(u999 >= multiplier * coverage["severe_any_u999"])
        or np.any(top1 >= multiplier * coverage["severe_any_top1_uncovered"]))
    route = ("C" if allocation_material and coverage_material else
             "A" if allocation_material else
             "B" if coverage_material else "D")
    return {
        "multiplier": float(multiplier),
        "allocation_material": allocation_material,
        "coverage_material": coverage_material,
        "severe_coverage": severe,
        "allocation_state_count": allocation_count,
        "coverage_state_count": coverage_count,
        "median_A_alloc": float(np.median(a_values)),
        "median_U99": float(np.median(u99)),
        "median_U999": float(np.median(u999)),
        "route": route,
    }


def load_archive(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as data:
        return {
            "samples": data["samples"],
            "variance_mass": data["variance_mass"],
            "responsibility": data["responsibility"],
            "whitened": data["whitened"],
            "source_strata": data["source_strata"],
            "proposal_identity": json.loads(
                str(data["proposal_identity"].item())),
            "gradient_seeds": data["gradient_seeds"],
        }


__all__ = [
    "_as_proposal", "allocation_diagnostics", "birth_score",
    "build_birth_candidates", "candidate_centres", "coverage_diagnostics",
    "entropy", "gaussian_log_density", "load_archive",
    "mahalanobis_squared", "nearest_covariance_index",
    "normalized_variance_mass", "responsibility_matrix",
    "routing_verdict",
]

