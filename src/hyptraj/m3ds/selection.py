"""Deterministic M3-DS directional selection and abstention-safety assembly.

Selection rule (M3-DS taskbook, section 10), applied per directional class:

Step 1: maximize distinct config coverage
Step 2: within config, prefer greater s2 spacing from already selected states
Step 3: prefer stronger independent-confirmation support margin
Step 4: prefer larger absolute directional effect only after diversity/support
Step 5: lexical state_id tie-break

No future controller score, regret, or VRF may enter selection. ABSTAIN is a
protocol action and is never used as a ground-truth label here.
"""

from __future__ import annotations

DIRECTIONAL_CLASSES = ("WIDEN", "SHRINK")
SAFETY_REFERENCE_STATUSES = ("HOLD", "AMBIGUOUS")

#: Directional effect key per class: r_w = M2(widen)/M2(base) - 1 and
#: r_s = M2(shrink)/M2(base) - 1 (negative values indicate improvement).
_EFFECT_KEY = {"WIDEN": "r_w", "SHRINK": "r_s"}


def directional_effects(row: dict) -> dict:
    """Relative paired contrasts r_w and r_s from confirmation arm metrics."""
    arms = row["arms"]
    base = float(arms["base"]["M2"])
    return {
        "r_w": float(arms["widen"]["M2"]) / base - 1.0,
        "r_s": float(arms["shrink"]["M2"]) / base - 1.0,
    }


def _directional_pool(records: list[dict], class_name: str) -> list[dict]:
    if class_name not in DIRECTIONAL_CLASSES:
        raise ValueError(f"not a directional class: {class_name}")
    pool = []
    for row in records:
        if row["corrected_class"] != class_name:
            continue
        if not (row["probability_semantics_valid"]
                and row["reference_action_class_valid"]):
            continue
        effects = directional_effects(row)
        pool.append({**row, **effects})
    return pool


def _rank_key(row: dict, selected: list[dict]) -> tuple:
    """Greedy key implementing taskbook section 10 steps 1-5.

    Smaller tuple wins. Step 1 (uncovered config) dominates; step 2 uses the
    minimum s2 distance to already selected states (+inf when none are
    selected yet, so the first pick falls through to support margin).
    """
    covered = {str(item["config_id"]) for item in selected}
    config_not_covered = str(row["config_id"]) not in covered
    if selected:
        s2_spacing = min(abs(float(row["s2"]) - float(item["s2"]))
                         for item in selected)
    else:
        s2_spacing = float("inf")
    support = float(row["class_certainty_score"])
    effect = abs(float(row[_EFFECT_KEY[row["corrected_class"]]]))
    return (not config_not_covered, -s2_spacing, -support, -effect,
            str(row["state_id"]))


def select_directional(records: list[dict], class_name: str,
                       target: int = 8,
                       min_distinct_configs: int = 4) -> dict:
    """Greedy deterministic selection of one directional class."""
    pool = _directional_pool(records, class_name)
    selected: list[dict] = []
    while len(selected) < target and len(selected) < len(pool):
        remaining = [row for row in pool
                     if row["state_id"] not in
                     {item["state_id"] for item in selected}]
        pick = min(remaining, key=lambda row: _rank_key(row, selected))
        selected.append({**pick, "selection_rank": len(selected) + 1,
                         "selection_reason": _reason(pick, selected)})
    reserve = [row for row in pool
               if row["state_id"] not in
               {item["state_id"] for item in selected}]
    for rank, row in enumerate(sorted(reserve,
                                      key=lambda row: str(row["state_id"])),
                               start=len(selected) + 1):
        row["selection_rank"] = rank
        row["selection_reason"] = "reserve: not needed for primary target"
    distinct = len({str(row["config_id"]) for row in selected})
    strata = sorted({str(row["candidate_stratum"]) for row in selected})
    return {
        "class": class_name,
        "target": int(target),
        "available": len(pool),
        "selected": selected,
        "reserve": reserve,
        "selected_count": len(selected),
        "distinct_configs": distinct,
        "distinct_strata": strata,
        "diversity_gate": {
            "min_distinct_configs": int(min_distinct_configs),
            "distinct_configs_pass": bool(distinct >= min_distinct_configs),
            "min_strata": 2,
            "strata_pass": bool(len(strata) >= 2),
        },
        "complete": bool(len(selected) == target),
    }


def _reason(row: dict, selected: list[dict]) -> str:
    covered = {str(item["config_id"]) for item in selected}
    parts = []
    if str(row["config_id"]) not in covered:
        parts.append("new config coverage")
    else:
        parts.append("s2 spacing from selected states")
    parts.append(f"support={float(row['class_certainty_score']):.6g}")
    effect = abs(float(row[_EFFECT_KEY[row["corrected_class"]]]))
    parts.append(f"|effect|={effect:.6g}")
    return "; ".join(parts)


def build_directional_axis(records: list[dict], target: int = 8,
                           min_distinct_configs: int = 4) -> dict:
    """Build the full directional axis (primary + reserve) and gate."""
    classes = {name: select_directional(records, name, target,
                                        min_distinct_configs)
               for name in DIRECTIONAL_CLASSES}
    invalid = sum(1 for row in records
                  if not (row["probability_semantics_valid"]
                          and row["reference_action_class_valid"])
                  and row["corrected_class"] in DIRECTIONAL_CLASSES)
    gates = {
        "selected_widen_8": classes["WIDEN"]["selected_count"] == target,
        "selected_shrink_8": classes["SHRINK"]["selected_count"] == target,
        "invalid_zero": invalid == 0,
        "diversity_pass": all(
            classes[name]["diversity_gate"]["distinct_configs_pass"]
            and classes[name]["diversity_gate"]["strata_pass"]
            for name in DIRECTIONAL_CLASSES),
    }
    return {
        "classes": classes,
        "invalid_directional": invalid,
        "gates": gates,
        "M3DS_DIR_1": "PASS" if all(gates.values()) else "FAIL",
    }


def safety_primary(records: list[dict]) -> list[dict]:
    """Independently confirmed safety reference states (HOLD + AMBIGUOUS).

    Reference statuses are preserved verbatim; they are never relabelled as
    an ABSTAIN ground-truth class.
    """
    rows = []
    for row in records:
        if row["corrected_class"] not in SAFETY_REFERENCE_STATUSES:
            continue
        effects = directional_effects(row)
        rows.append({
            "state_id": row["state_id"],
            "config_id": row["config_id"],
            "s2": float(row["s2"]),
            "candidate_stratum": row["candidate_stratum"],
            "reference_status": row["corrected_class"],
            "confirmation_support": row.get("class_certainty_score"),
            "r_w": effects["r_w"],
            "r_s": effects["r_s"],
            "probability_semantics_valid": bool(
                row["probability_semantics_valid"]),
            "reference_action_class_valid": bool(
                row["reference_action_class_valid"]),
            "ambiguity_or_invalid_reason": row.get(
                "ambiguity_or_invalid_reason") or "",
            "safe_protocol_behavior": "ABSTAIN / BASE (no adaptation)",
            "independently_confirmed": True,
        })
    return sorted(rows, key=lambda row: (row["reference_status"],
                                         str(row["state_id"])))


__all__ = ["DIRECTIONAL_CLASSES", "SAFETY_REFERENCE_STATUSES",
           "build_directional_axis", "directional_effects",
           "safety_primary", "select_directional"]
