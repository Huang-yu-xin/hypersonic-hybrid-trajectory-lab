"""Typed event semantics and estimator arithmetic for RareTopo repairs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

import numpy as np


EVENT_SEMANTICS_SCHEMA_VERSION = 2
EVENT_DEFINITION_ID = "m1d-benchmark-family-label-v1:S0-complement"
EVENT_PREDICATE_SOURCE = "hyptraj.m1d.benchmark_family.BenchmarkConfig.label"


class EventSemanticsError(ValueError):
    """Raised when values from different semantic namespaces are mixed."""


class TopologyLabel(str, Enum):
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


@dataclass(frozen=True)
class ProposalArm:
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise EventSemanticsError("proposal arm must be a non-empty string")


@dataclass(frozen=True)
class SourceStratum:
    index: int

    def __post_init__(self) -> None:
        if not isinstance(self.index, (int, np.integer)) or int(self.index) < 0:
            raise EventSemanticsError("source stratum must be a non-negative integer")


@dataclass(frozen=True)
class EventStatistics:
    contribution: np.ndarray
    variance_mass: np.ndarray
    p_hat: float
    m2_hat: float
    variance_hat: float
    sample_count: int


def _topology_values(labels: Iterable[object]) -> np.ndarray:
    values = np.asarray(labels, dtype=object)
    flat = values.ravel()
    normalized = np.empty(flat.shape, dtype=object)
    allowed = {member.value for member in TopologyLabel}
    for index, value in enumerate(flat):
        item = value.value if isinstance(value, TopologyLabel) else value
        if item not in allowed:
            raise EventSemanticsError(f"unknown topology label: {item!r}")
        normalized[index] = item
    return normalized.reshape(values.shape)


def event_indicator_from_topology(labels: Iterable[object]) -> np.ndarray:
    """Return rare-event membership from the frozen S0-complement predicate."""
    return _topology_values(labels) != TopologyLabel.S0.value


def legacy_event_indicator(labels: Iterable[object], *, nominal_literal: str) -> np.ndarray:
    """Explicit adapter for unambiguous historical topology arrays."""
    if nominal_literal != TopologyLabel.S0.value:
        raise EventSemanticsError(
            f"legacy nominal literal {nominal_literal!r} is incompatible with "
            f"the frozen topology nominal {TopologyLabel.S0.value!r}"
        )
    return event_indicator_from_topology(labels)


def compute_event_statistics(event_indicator: Iterable[object],
                             likelihood_ratio: Iterable[float]) -> EventStatistics:
    indicator = np.asarray(event_indicator)
    if indicator.dtype != np.bool_:
        raise EventSemanticsError("event_indicator must have boolean dtype")
    ratio = np.asarray(likelihood_ratio, dtype=float)
    if indicator.shape != ratio.shape or indicator.ndim != 1:
        raise EventSemanticsError("event indicator and likelihood ratio must be equal-length vectors")
    if ratio.size == 0 or np.any(~np.isfinite(ratio)) or np.any(ratio < 0.0):
        raise EventSemanticsError("likelihood ratios must be finite, non-negative and non-empty")
    contribution = indicator.astype(float) * ratio
    variance_mass = contribution ** 2
    p_hat = float(np.mean(contribution))
    m2_hat = float(np.mean(variance_mass))
    variance_hat = float(max(0.0, (m2_hat - p_hat ** 2) / ratio.size))
    return EventStatistics(contribution, variance_mass, p_hat, m2_hat,
                           variance_hat, int(ratio.size))


def probability_scale_guard(p_hat: float, p_ref: float, *, standard_error: float,
                            standard_error_multiplier: float = 8.0,
                            relative_reference_allowance: float = 0.25) -> bool:
    values = np.asarray([p_hat, p_ref, standard_error], dtype=float)
    if np.any(~np.isfinite(values)) or p_ref <= 0.0 or standard_error < 0.0:
        raise EventSemanticsError("invalid probability scale-guard inputs")
    tolerance = (standard_error_multiplier * standard_error
                 + relative_reference_allowance * p_ref)
    if abs(p_hat - p_ref) > tolerance:
        raise EventSemanticsError(
            f"claimed event probability {p_hat:.8g} is catastrophically "
            f"incompatible with reference {p_ref:.8g} (tolerance {tolerance:.8g})"
        )
    return True


def probability_semantics_manifest(proposal_arm: ProposalArm,
                                   source_strata: Iterable[SourceStratum]) -> dict:
    strata = list(source_strata)
    if not all(isinstance(item, SourceStratum) for item in strata):
        raise EventSemanticsError("source strata must use SourceStratum values")
    return {
        "schema_version": EVENT_SEMANTICS_SCHEMA_VERSION,
        "event_definition_id": EVENT_DEFINITION_ID,
        "event_predicate_source": EVENT_PREDICATE_SOURCE,
        "proposal_arm": proposal_arm.name,
        "source_strata": sorted({int(item.index) for item in strata}),
        "p_hat_definition": "mean(event_indicator * likelihood_ratio)",
        "m2_definition": "mean((event_indicator * likelihood_ratio)^2)",
        "variance_mass_definition": "(event_indicator * likelihood_ratio)^2",
        "likelihood_ratio_definition": "p(x)/q(x)",
    }


def require_parent_gate(child_stage: str, *, parent_gate_passed: bool) -> None:
    if not parent_gate_passed:
        raise EventSemanticsError(
            f"corrected parent gate did not authorize child stage {child_stage}"
        )
