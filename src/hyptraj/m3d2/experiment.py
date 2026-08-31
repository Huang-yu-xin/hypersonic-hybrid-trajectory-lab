"""M3-D2 full-event reference and finite-step characterization.

This module is benchmark-construction code only.  It deliberately has no
controller import and consumes only typed topology labels S0--S4.
"""

from __future__ import annotations

from itertools import combinations
from statistics import NormalDist

import numpy as np

from hyptraj.event_semantics import (
    EVENT_SEMANTICS_SCHEMA_VERSION,
    TopologyLabel,
    event_indicator_from_topology,
)
from hyptraj.m3d.reference_direction import label_state

EVENT_DEFINITION_ID = "FULL_TOPOLOGY_EVENT_S1_S4"
NOMINAL_TOPOLOGY = TopologyLabel.S0.value
ARM_ORDER = ("base", "widen", "shrink")


def _mean_se_ci(values: list[float], level: float = 0.95) -> dict:
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    se = float(arr.std(ddof=1) / np.sqrt(arr.size)) if arr.size > 1 else 0.0
    z = NormalDist().inv_cdf(0.5 + level / 2.0)
    return {"mean": mean, "se": se,
            "ci95": [float(mean - z * se), float(mean + z * se)]}


def direct_full_event_reference(bench_cfg, seed_key: list[int], n: int,
                                n_batches: int = 20) -> dict:
    """Estimate P(S1 union ... union S4) by independent target MC.

    ``BenchmarkConfig.logp`` is the standard-normal target density, so direct
    standard-normal draws are a clean full-event reference stream.
    """
    if n <= 0 or n % n_batches:
        raise ValueError("n must be positive and divisible by n_batches")
    rng = np.random.default_rng(list(seed_key))
    batch_n = n // n_batches
    p_batches: list[float] = []
    counts = {member.value: 0 for member in TopologyLabel}
    for _ in range(n_batches):
        z = rng.standard_normal((batch_n, 2))
        labels = np.asarray(bench_cfg.label(z), dtype=object)
        for member in TopologyLabel:
            counts[member.value] += int(np.sum(labels == member.value))
        event = event_indicator_from_topology(labels)
        p_batches.append(float(np.mean(event)))
    stats = _mean_se_ci(p_batches)
    return {
        "schema_version": "raretopo-m3d2-full-event-reference-v0",
        "event_semantics_schema_version": EVENT_SEMANTICS_SCHEMA_VERSION,
        "event_definition_id": EVENT_DEFINITION_ID,
        "nominal_topology": NOMINAL_TOPOLOGY,
        "sampling_law": "N(0,I_2) direct target Monte Carlo",
        "seed_key": [int(x) for x in seed_key],
        "sample_count": int(n),
        "n_batches": int(n_batches),
        "batch_n": int(batch_n),
        "p_ref_full": stats["mean"],
        "p_ref_full_SE": stats["se"],
        "p_ref_full_CI": stats["ci95"],
        "p_batches": p_batches,
        "topology_counts": counts,
    }


def evaluate_reference_arms(arms: dict, bench_cfg, seed_key: list[int],
                            n: int, n_batches: int = 20) -> dict:
    """Evaluate BASE/WIDEN/SHRINK with paired CRN and schema-2 semantics."""
    if n <= 0 or n % n_batches:
        raise ValueError("n must be positive and divisible by n_batches")
    missing = set(ARM_ORDER) - set(arms)
    if missing:
        raise ValueError(f"missing arms: {sorted(missing)}")
    batch_n = n // n_batches
    rng = np.random.default_rng(list(seed_key))
    raw = {name: {"m2": [], "p": [], "l": {}} for name in ARM_ORDER}
    for _ in range(n_batches):
        comp = None
        eps = None
        for name in ARM_ORDER:
            proposal = arms[name]
            if comp is None:
                comp = rng.choice(proposal.n_components, size=batch_n,
                                  p=proposal.weights)
                eps = rng.standard_normal((batch_n,
                                           proposal.centers.shape[1]))
            z = proposal.centers[comp] + np.einsum(
                "njk,nk->nj",
                np.stack([proposal.chols[index] for index in comp]), eps)
            logq = proposal.log_density(z)
            labels = np.asarray(bench_cfg.label(z), dtype=object)
            event = event_indicator_from_topology(labels)
            ratio = np.exp(np.asarray(bench_cfg.logp(z), dtype=float) - logq)
            contribution = event.astype(float) * ratio
            raw[name]["p"].append(float(np.mean(contribution)))
            raw[name]["m2"].append(float(np.mean(contribution ** 2)))
            for member in TopologyLabel:
                if member is TopologyLabel.S0:
                    continue
                mode_mass = contribution * (labels == member.value)
                raw[name]["l"].setdefault(member.value, []).append(
                    float(np.mean(mode_mass ** 2)))
    output = {}
    for name in ARM_ORDER:
        p_stats = _mean_se_ci(raw[name]["p"])
        m2_stats = _mean_se_ci(raw[name]["m2"])
        p_hat = p_stats["mean"]
        m2_hat = m2_stats["mean"]
        ess = float(n * p_hat * p_hat / m2_hat) if m2_hat > 0.0 else 0.0
        output[name] = {
            "P": p_hat,
            "P_batch_se": p_stats["se"],
            "P_CI": p_stats["ci95"],
            "M2": m2_hat,
            "M2_batch_se": m2_stats["se"],
            "m2_batches": raw[name]["m2"],
            "p_batches": raw[name]["p"],
            "ESS": ess,
            "L_modes": {
                mode: {"L": _mean_se_ci(vals)["mean"],
                       "se": _mean_se_ci(vals)["se"]}
                for mode, vals in sorted(raw[name]["l"].items())
            },
            "sample_count": int(n),
            "n_batches": int(n_batches),
            "batch_n": int(batch_n),
        }
    return output


def probability_sanity_gate(arms: dict, reference: dict,
                            z_multiplier: float = 4.0) -> dict:
    """Apply the locked arm-vs-reference and arm-pair probability gates."""
    checks = []
    pref = float(reference["p_ref_full"])
    sref = float(reference["p_ref_full_SE"])
    for name in ARM_ORDER:
        phat = float(arms[name]["P"])
        se = float(arms[name]["P_batch_se"])
        tol = float(z_multiplier * np.hypot(se, sref))
        checks.append({"kind": "arm_vs_reference", "a": name,
                       "b": "p_ref_full", "difference": abs(phat - pref),
                       "tolerance": tol,
                       "pass": bool(abs(phat - pref) <= tol)})
    for first, second in combinations(ARM_ORDER, 2):
        p1, p2 = float(arms[first]["P"]), float(arms[second]["P"])
        s1 = float(arms[first]["P_batch_se"])
        s2 = float(arms[second]["P_batch_se"])
        tol = float(z_multiplier * np.hypot(s1, s2))
        checks.append({"kind": "arm_pair", "a": first, "b": second,
                       "difference": abs(p1 - p2), "tolerance": tol,
                       "pass": bool(abs(p1 - p2) <= tol)})
    return {"z_multiplier": float(z_multiplier), "checks": checks,
            "pass": bool(all(item["pass"] for item in checks))}


def _certainty(action: str, oracle: dict, arms: dict,
               tau: float, margin_min: float, hold_window: float,
               support_multiplier: float) -> float | None:
    ratios = oracle.get("ratios", {})
    rw = float(ratios.get("widen_over_base", np.nan))
    rs = float(ratios.get("shrink_over_base", np.nan))
    if action == "HOLD":
        return float(min(hold_window - abs(rw),
                         hold_window - abs(rs)) / hold_window)
    if action not in {"WIDEN", "SHRINK"}:
        return None
    best_ratio = rw if action == "WIDEN" else rs
    improvement_slack = (-tau - best_ratio) / tau
    margin_slack = float(oracle["direction_margin_Delta_dir"]) / margin_min
    required = []
    for other in ("widen", "shrink"):
        diff = np.asarray(arms[other]["m2_batches"]) - np.asarray(
            arms["base"]["m2_batches"])
        se = float(diff.std(ddof=1) / np.sqrt(diff.size))
        required.append(abs(float(diff.mean())) /
                        max(support_multiplier * se, 1e-300))
    return float(min(improvement_slack, margin_slack, *required))


def classify_reference_state(arms: dict, probability_reference: dict, *,
                             tau: float = 0.01,
                             margin_min: float = 0.05,
                             hold_window: float = 0.03,
                             support_multiplier: float = 2.0,
                             min_arm_ess: float = 20.0,
                             probability_z: float = 4.0) -> dict:
    """Return one authoritative D2 class record from reference-arm data."""
    finite = all(np.isfinite(float(arms[name][field]))
                 for name in ARM_ORDER for field in ("P", "M2", "ESS"))
    ess_ok = all(float(arms[name]["ESS"]) >= min_arm_ess
                 for name in ARM_ORDER)
    probability = probability_sanity_gate(arms, probability_reference,
                                          probability_z)
    if not finite or not ess_ok:
        action = "INVALID"
        oracle = None
        reason = "nonfinite_arithmetic" if not finite else "ess_below_minimum"
    elif not probability["pass"]:
        action = "INVALID"
        oracle = None
        reason = "probability_domain_fail"
    else:
        oracle = label_state(arms, arms, tau=tau, margin_min=margin_min,
                             hold_window=hold_window,
                             se_mult=support_multiplier)
        action = oracle["oracle_action"]
        if action == "REFERENCE_AMBIGUOUS":
            action = "AMBIGUOUS"
        reason = None if action != "AMBIGUOUS" else (
            oracle.get("ambiguity_reason") or
            ("direction_margin_below_threshold" if
             oracle.get("margin_below_threshold") else
             "no_unique_preregistered_class"))
    certainty = (_certainty(action, oracle, arms, tau, margin_min,
                            hold_window, support_multiplier)
                 if oracle is not None else None)
    return {
        "corrected_class": action,
        "class_certainty_score": certainty,
        "ambiguity_or_invalid_reason": reason,
        "probability_semantics_valid": bool(probability["pass"]),
        "reference_action_class_valid": action in {"WIDEN", "HOLD", "SHRINK"},
        "numerical_valid": bool(finite),
        "ess_valid": bool(ess_ok),
        "minimum_arm_ESS": float(min(arms[name]["ESS"] for name in ARM_ORDER)),
        "probability_sanity": probability,
        "oracle_details": oracle,
    }


__all__ = [
    "ARM_ORDER", "EVENT_DEFINITION_ID", "NOMINAL_TOPOLOGY",
    "classify_reference_state", "direct_full_event_reference",
    "evaluate_reference_arms", "probability_sanity_gate",
]
