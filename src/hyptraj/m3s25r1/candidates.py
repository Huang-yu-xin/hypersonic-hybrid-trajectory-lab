"""M3-S25-R1 candidate-generation mechanics (taskbook Sec. 5-10).

Frozen mechanism:
  - normalized log-support coordinate u(s2; c) over the inherited legality
    window [s2_lo(c), s2_hi(c)] with s2_hi = 8.0;
  - support-completion interval u in [0.15, 1.00], split into K = 8 strata
    with boundaries e_i = 0.15 + 0.85 i / 8;
  - per config x stratum exactly one fresh state selected from L = 65
    deterministic interior anchors
        u_{i,m} = e_i + (m+1)/(L+1) (e_{i+1}-e_i),  m = 0..L-1,
        s2_{i,m} = exp(log s2_lo + u_{i,m} (log s2_hi - log s2_lo));
  - anchor hash SHA256("M3-S25-R1-CANDIDATE-V1|" + config_id + "|" +
    stratum_id + "|" + canonical_s2), sorted ascending; selection = the
    first anchor in hash order that is legal AND fresh;
  - canonical_s2 = repr(float(s2)): the shortest round-trip decimal form
    of the exact float value -- identical to the value's JSON serialization
    inside the frozen universe artifact (auditable bit-for-bit);
  - selection is independent of truth labels, discovery results,
    SHRINK/HOLD counts and the numeric ordering of candidate values.

Regression invariants (taskbook Sec. 9) are mechanically audited by
`invariant_audit`; the support-span invariant (per-config
max u - min u >= 0.70) is reported with its realized verdict.
"""
from __future__ import annotations

import hashlib
import math

ANCHOR_SALT = "M3-S25-R1-CANDIDATE-V1"
ORIGIN = "M3-S25-R1-SUPPORT-COMPLETION"
SOURCE_STAGE = "M3-S25-R1"
U_LO = 0.15
U_HI = 1.00
N_STRATA = 8
L_ANCHORS = 65
S2_HI = 8.0
PANEL_RANK_SEED = "M3-S25-R1-PANEL-V1|"
STATE_SUFFIX = "s25r1"


def stratum_bounds(i: int) -> tuple[float, float]:
    """[e_i, e_{i+1}] with e_i = 0.15 + 0.85 i / 8."""
    return (U_LO + 0.85 * i / N_STRATA, U_LO + 0.85 * (i + 1) / N_STRATA)


def stratum_id(i: int) -> str:
    return f"S{i}"


def u_of(s2: float, s2_lo: float, s2_hi: float = S2_HI) -> float:
    return (math.log(s2) - math.log(s2_lo)) / (math.log(s2_hi) - math.log(s2_lo))


def s2_of(u: float, s2_lo: float, s2_hi: float = S2_HI) -> float:
    return math.exp(math.log(s2_lo) + u * (math.log(s2_hi) - math.log(s2_lo)))


def canonical_s2(s2: float) -> str:
    """Frozen canonical form: shortest round-trip decimal (== JSON form)."""
    return repr(float(s2))


def anchor_hash(config_id: str, stratum: int, s2: float) -> str:
    return hashlib.sha256(
        (ANCHOR_SALT + "|" + config_id + "|" + stratum_id(stratum) + "|"
         + canonical_s2(s2)).encode("utf-8")).hexdigest()


def panel_rank(config_id: str, state_id: str) -> str:
    return hashlib.sha256(
        (PANEL_RANK_SEED + config_id + "|" + state_id).encode("utf-8")).hexdigest()


def stratum_anchors(config_id: str, stratum: int, s2_lo: float,
                    s2_hi: float = S2_HI) -> list[dict]:
    """The L=65 deterministic interior anchors of one stratum, in generation
    order (m = 0..L-1), NOT yet hash-sorted."""
    e0, e1 = stratum_bounds(stratum)
    lo, hi = math.log(s2_lo), math.log(s2_hi)
    out = []
    for m in range(L_ANCHORS):
        u = e0 + (m + 1) / (L_ANCHORS + 1) * (e1 - e0)
        s2 = math.exp(lo + u * (hi - lo))
        out.append({"m": m, "u": u, "s2": s2,
                    "hash": anchor_hash(config_id, stratum, s2)})
    return out


def select_stratum_state(config_id: str, stratum: int, s2_lo: float,
                         historical: set[float], s2_hi: float = S2_HI) -> dict:
    """Hash-ascending scan; select the first legal AND fresh anchor.

    Legality is structural (u in (0,1] keeps s2 in (s2_lo, s2_hi]) but is
    re-asserted; freshness excludes every historically characterized s2 of
    the same config.  Raises if no fresh anchor exists (taskbook Sec. 6:
    M3-S25-R1-PREFLIGHT-BLOCKED / samples = 0)."""
    anchors = stratum_anchors(config_id, stratum, s2_lo, s2_hi)
    from hyptraj.m3s25r1.history import collision
    fresh = []
    for a in anchors:
        s2 = a["s2"]
        if not (s2_lo < s2 <= s2_hi):          # legality re-assertion
            continue
        if not collision(s2, historical):
            fresh.append(a)
    if not fresh:
        raise RuntimeError(
            f"M3-S25-R1-PREFLIGHT-BLOCKED: config {config_id} stratum "
            f"{stratum} has no legal fresh anchor; STOP; samples = 0")
    ranked = sorted(fresh, key=lambda a: (a["hash"], a["m"]))
    sel = ranked[0]
    return {"stratum": stratum, "anchor_m": sel["m"], "anchor_u": sel["u"],
            "anchor_s2": sel["s2"], "anchor_hash": sel["hash"],
            "anchor_rank_position": sorted(
                anchors, key=lambda a: (a["hash"], a["m"])).index(sel) + 1,
            "n_anchors": L_ANCHORS,
            "n_collided": len(anchors) - len(fresh),
            "n_fresh": len(fresh)}


def build_states(windows: dict[str, dict], historical: dict[str, set[float]],
                 config_meta: dict[str, dict]) -> list[dict]:
    """Assemble the 240-state support-completion universe (30 x 8 x 1)."""
    states = []
    for cid in sorted(windows):
        w = windows[cid]
        meta = config_meta[cid]
        for i in range(N_STRATA):
            sel = select_stratum_state(cid, i, w["s2_lo"],
                                       historical.get(cid, set()), w["s2_hi"])
            s2 = sel["anchor_s2"]
            u = u_of(s2, w["s2_lo"], w["s2_hi"])
            sid = f"{cid}_{STATE_SUFFIX}_{s2:.10f}"
            states.append({
                "state_id": sid,
                "config_id": cid,
                "s2": s2,
                "u": u,
                "stratum_id": stratum_id(i),
                "rank": panel_rank(cid, sid),
                "anchor_m": sel["anchor_m"],
                "anchor_u": sel["anchor_u"],
                "anchor_hash": sel["anchor_hash"],
                "anchor_rank_position": sel["anchor_rank_position"],
                "n_anchors": sel["n_anchors"],
                "n_collided": sel["n_collided"],
                "n_fresh": sel["n_fresh"],
                "legality_s2_lo": w["s2_lo"],
                "legality_s2_hi": w["s2_hi"],
                "legality_s2_min": w["s2_min_legality"],
                "legality_lambda_min_P": w["lambda_min_P"],
                "config_origin": meta["origin"],
                "config_source_path": meta["config_source_path"],
                "config_source_sha256": meta["config_source_sha256"],
                "freshness_status": "FRESH_UNCHARACTERIZED",
                "exposure_status": "CONTROLLER_EXPOSURE_0",
                "origin": ORIGIN,
                "source_stage": SOURCE_STAGE,
            })
    states.sort(key=lambda s: (s["config_id"], s["stratum_id"]))
    return states


def invariant_audit(states: list[dict], windows: dict[str, dict]) -> dict:
    """Mechanical regression audit (taskbook Sec. 9).  Returns per-check
    verdicts plus the realized per-config support-span report."""
    per_config: dict[str, list[dict]] = {}
    for s in states:
        per_config.setdefault(s["config_id"], []).append(s)
    configs = sorted(per_config)
    rows, span_failures = [], []
    for cid in configs:
        ss = per_config[cid]
        us = [s["u"] for s in ss]
        strata = sorted(s["stratum_id"] for s in ss)
        span = max(us) - min(us)
        row = {"config_id": cid,
               "min_u": min(us), "max_u": max(us), "span": span,
               "min_u_ge_0.15": min(us) >= U_LO,
               "max_u_le_1.0": max(us) <= U_HI,
               "span_ge_0.70": span >= 0.70,
               "strata_occupied": strata,
               "each_stratum_exactly_once": (
                   strata == [stratum_id(i) for i in range(N_STRATA)]
                   and len(strata) == len(set(strata)) == N_STRATA),
               "states": len(ss)}
        rows.append(row)
        if not row["span_ge_0.70"]:
            span_failures.append(row)
    strata_ok = all(r["each_stratum_exactly_once"] for r in rows)
    checks = {
        "configs": len(configs) == 30,
        "candidates": len(states) == 240,
        "duplicate_state_id": len({s["state_id"] for s in states}) == 240,
        "states_per_config_8": all(len(v) == N_STRATA for v in per_config.values()),
        "min_u_ge_0.15": all(r["min_u_ge_0.15"] for r in rows),
        "max_u_le_1.0": all(r["max_u_le_1.0"] for r in rows),
        "each_stratum_exactly_once": strata_ok,
        "legality_violations": sum(
            1 for s in states
            if not (s["legality_s2_lo"] < s["s2"] <= s["legality_s2_hi"])),
        "support_span_ge_0.70": not span_failures,
    }
    return {"per_config": rows, "span_failures": span_failures,
            "checks": checks,
            "strata_boundaries": [stratum_bounds(i) for i in range(N_STRATA + 1)]}


def freshness_reaudit(states: list[dict],
                      historical: dict[str, set[float]]) -> dict:
    """Independent re-check: every frozen state is fresh against the FULL
    historical characterized set of its config (taskbook Sec. 8)."""
    from hyptraj.m3s25r1.history import collision
    violations = []
    for s in states:
        if collision(s["s2"], historical.get(s["config_id"], set())):
            violations.append(s["state_id"])
    cross = [(a["state_id"], b["state_id"]) for a, b in
             ((states[i], states[j]) for i in range(len(states))
              for j in range(i + 1, len(states)))
             if a["config_id"] == b["config_id"]
             and abs(a["s2"] - b["s2"]) <= 1e-6 * max(1.0, abs(a["s2"]))]
    return {"violations": violations, "internal_collisions": cross,
            "FRESH": not violations and not cross}
