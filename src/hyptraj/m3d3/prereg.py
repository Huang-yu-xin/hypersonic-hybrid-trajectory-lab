"""Deterministic, artifact-only M3-D3-1 candidate-family construction."""

from __future__ import annotations

import math


FRACTIONS = (0.25, 0.50, 0.75)
RELATIVE_DEDUP_TOLERANCE = 1e-12


def _same_value(left: float, right: float) -> bool:
    return abs(left - right) <= RELATIVE_DEDUP_TOLERANCE * max(1.0, abs(left), abs(right))


def _canonical(value: float) -> str:
    return format(value, ".12g").replace(".", "p").replace("-", "m")


def build_boundary_candidates(brackets: list[dict], existing_by_config: dict[str, list[float]]) -> tuple[list[dict], dict]:
    """Generate 25/50/75% log-space points from every valid D3-0 bracket.

    Candidates are deduplicated only against an existing D2 state in the same
    frozen configuration.  This retains the complete bracket rule while never
    importing an outcome-derived selection preference.
    """
    raw: list[dict] = []
    final: list[dict] = []
    for bracket in sorted(brackets, key=lambda row: (row["config_id"], float(row["s2_left"]), float(row["s2_right"]))):
        left, right = float(bracket["s2_left"]), float(bracket["s2_right"])
        if not (left > 0 and right > left):
            raise ValueError(f"invalid log-space bracket: {bracket}")
        for fraction in FRACTIONS:
            s2 = math.exp((1.0 - fraction) * math.log(left) + fraction * math.log(right))
            row = {
                "config_id": bracket["config_id"],
                "s2": s2,
                "fraction_log_space": fraction,
                "source_s2_left": left,
                "source_s2_right": right,
                "source_boundary_type": bracket["boundary_type"],
                "candidate_id": f"{bracket['config_id']}_d3_s2_{_canonical(s2)}",
            }
            raw.append(row)
            if any(_same_value(s2, old) for old in existing_by_config.get(row["config_id"], [])):
                continue
            final.append(row)
    if len(final) > 96:
        raise ValueError("M3-D3 candidate cap exceeded; human preregistration decision required")
    summary = {
        "bracket_count": len(brackets),
        "raw_generated_candidates": len(raw),
        "deduplicated_candidates": len(final),
        "distinct_configs": len({row["config_id"] for row in final}),
        "interpolation_space": "log_s2",
        "fractions": list(FRACTIONS),
        "dedup_relative_tolerance": RELATIVE_DEDUP_TOLERANCE,
    }
    return final, summary
