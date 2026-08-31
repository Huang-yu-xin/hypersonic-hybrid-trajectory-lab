"""Deterministic M3-D2 shortlist and final-benchmark selectors."""

from __future__ import annotations

from collections import Counter


TARGET_CLASSES = ("WIDEN", "HOLD", "SHRINK")


def _ordered(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda row: (
        -float(row["class_certainty_score"]),
        str(row["config_id"]), float(row["s2"]), str(row["state_id"])))


def diverse_select(records: list[dict], target: int,
                   max_per_config: int) -> dict:
    """Select deterministically under a strict per-config diversity cap."""
    chosen = []
    counts: Counter[str] = Counter()
    for row in _ordered(records):
        cid = str(row["config_id"])
        if counts[cid] >= max_per_config:
            continue
        chosen.append(row)
        counts[cid] += 1
        if len(chosen) == target:
            break
    distinct = len(counts)
    return {
        "selected": chosen,
        "target": int(target),
        "available": len(records),
        "selected_count": len(chosen),
        "max_per_config": int(max_per_config),
        "distinct_configs": distinct,
        "complete": bool(len(chosen) == target and distinct >= 3),
    }


def build_shortlist(records: list[dict], target_per_class: int = 12,
                    max_per_config: int = 4) -> dict:
    result = {}
    for action in TARGET_CLASSES:
        eligible = [row for row in records
                    if row["corrected_class"] == action]
        target = min(target_per_class, len(eligible))
        result[action] = diverse_select(eligible, target, max_per_config)
    return result


def build_final_benchmark(records: list[dict], target_per_class: int = 8,
                          max_per_config: int = 3) -> dict:
    result = {}
    for action in TARGET_CLASSES:
        eligible = [row for row in records
                    if row["corrected_class"] == action]
        result[action] = diverse_select(eligible, target_per_class,
                                        max_per_config)
    passed = all(result[action]["complete"] for action in TARGET_CLASSES)
    return {"classes": result, "M3D2_1": "PASS" if passed else "FAIL",
            "verdict": "D2-A" if passed else "D2-B"}


__all__ = ["TARGET_CLASSES", "build_final_benchmark", "build_shortlist",
           "diverse_select"]
