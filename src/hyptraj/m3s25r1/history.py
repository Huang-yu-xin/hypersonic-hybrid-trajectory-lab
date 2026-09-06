"""M3-S25-R1 historical characterized-s2 collection (taskbook Sec. 8).

Freshness firewall input: for each of the 30 inherited configs, every
s2 value that any prior stage has CHARACTERIZED (truth / reference /
discovery / confirmation / panel membership / protected reserve /
state-gradient tables / corrected state universe), plus the sealed
parent stage M3-S2S (240 truth-exposed states).

Content-based, fixed a priori (preregistration):
  - candidate PROPOSAL artifacts (candidate_pool / candidate_bank /
    candidate_plan / selection_view / candidate_states / candidate_universe)
    are NOT characterized and are excluded -- a proposed-but-never-sampled
    s2 carries no truth and no exposure.  The one exception is the parent
    stage's own plan, whose 240 states are all truth-exposed and enter the
    firewall through the tracked M3-S2S candidate universe + truth-exposed
    inventory below.
  - every state-level characterization / protection artifact is included.

config_id normalization: historical artifacts record legacy configs both
short ("c000") and long ("m1d_b20260827_c000"); a row belongs to universe
config `cid` iff raw == cid or raw.endswith("_" + cid).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# The stage's OWN outputs are not historical characterization: a candidate
# is by definition fresh vs every PRIOR stage, and R1's own summary /
# preflight artifacts merely record the R1 candidates themselves.  Without
# this exclusion the firewall would self-collide (fixed a priori,
# M3-S25-R1.2).
SELF_RESULTS_PREFIX = "results/phase_m3s25r1/"

S2S_UNIVERSE = ROOT / "configs/phase_m3s2s/m3s2s_candidate_universe.json"
S2S_INVENTORY = ROOT / ("results/phase_m3s2s/summary/"
                        "m3s2s_truth_exposed_inventory.json")
S1C_PANEL = ROOT / "configs/phase_m3s1c/m3s1c_panel.json"

# content-classified artifact families (fixed a priori, preregistration)
NON_CHARACTERIZED_TOKENS = (
    "candidate_pool", "candidate_bank", "candidate_plan",
    "selection_view", "candidate_states", "candidate_universe")
CHARACTERIZED_TOKENS = (
    "truth_inventory", "confirmation", "discovery", "reference", "panel",
    "reserve", "state_table", "inventory", "ledger", "universe",
    "state_manifest", "benchmark")

# minimum families the taskbook Sec. 8 names explicitly (audit reporting)
MINIMUM_FAMILY_TOKENS = {
    "M3-CF*": ("m3cf",),
    "M3-WCF*": ("m3wcf",),
    "M3-PI*": ("m3pi",),
    "M3-S1*": ("m3s1",),
    "M3-S2S": ("m3s2s",),
}


def _norm_config(raw: str, configs: list[str]) -> str | None:
    raw = str(raw).strip()
    for cid in configs:
        if raw == cid or raw.endswith("_" + cid):
            return cid
    return None


def historical_characterized_s2(configs: list[str]) -> tuple[dict[str, set[float]], dict]:
    """Per-config set of every historically characterized s2 + audit meta."""
    hist: dict[str, set[float]] = {}
    sources: list[dict] = []

    def add(cid, value):
        if cid is not None and math.isfinite(value):
            hist.setdefault(cid, set()).add(float(value))

    for p in sorted((ROOT / "results").rglob("*.csv")):
        rel = p.relative_to(ROOT).as_posix().replace("\\", "/")
        if rel.startswith(SELF_RESULTS_PREFIX):
            continue
        name = p.name.lower()
        if any(t in name for t in NON_CHARACTERIZED_TOKENS):
            continue
        if not any(t in name for t in CHARACTERIZED_TOKENS):
            continue
        rows = 0
        try:
            with p.open(newline="", encoding="utf-8") as h:
                rdr = csv.DictReader(h)
                if not rdr.fieldnames:
                    continue
                fns = [f.strip() for f in rdr.fieldnames]
                if "s2" not in fns or "config_id" not in fns:
                    continue
                for row in rdr:
                    try:
                        v = float(row["s2"])
                    except (TypeError, ValueError):
                        continue
                    before = sum(len(s) for s in hist.values())
                    add(_norm_config(row.get("config_id"), configs), v)
                    if sum(len(s) for s in hist.values()) > before:
                        rows += 1
        except Exception:
            continue
        sources.append({"path": p.relative_to(ROOT).as_posix(),
                        "classification": "characterized",
                        "new_values_added": rows})

    if S1C_PANEL.exists():
        panel = json.loads(S1C_PANEL.read_text(encoding="utf-8"))
        for s in panel.get("states", []):
            if s.get("s2") is not None:
                add(_norm_config(s.get("config_id", ""), configs), float(s["s2"]))
        sources.append({"path": S1C_PANEL.relative_to(ROOT).as_posix(),
                        "classification": "characterized", "new_values_added": 0})

    if S2S_UNIVERSE.exists():
        u = json.loads(S2S_UNIVERSE.read_text(encoding="utf-8"))
        for s in u["states"]:
            hist.setdefault(s["config_id"], set()).add(float(s["s2"]))
        sources.append({"path": S2S_UNIVERSE.relative_to(ROOT).as_posix(),
                        "classification": "parent stage M3-S2S (240 truth-exposed)",
                        "new_values_added": len(u["states"])})
    if S2S_INVENTORY.exists():
        inv = json.loads(S2S_INVENTORY.read_text(encoding="utf-8"))
        if len(inv.get("states", [])) != 240:
            raise RuntimeError(
                f"M3-S25-R1-PREFLIGHT-BLOCKED: parent truth-exposed inventory "
                f"has {len(inv.get('states', []))} states, expected 240")

    meta = {"sources": sources,
            "minimum_families": {k: any(any(t in s["path"] for t in toks)
                                        for s in sources)
                                 for k, toks in MINIMUM_FAMILY_TOKENS.items()},
            "per_config_counts": {c: len(hist.get(c, ())) for c in configs}}
    return hist, meta


def collision(s2: float, historical: set[float]) -> bool:
    """Taskbook Sec. 8 rule: |s2 - s2_h| <= 1e-6 * max(1, |s2_h|)."""
    return any(abs(s2 - e) <= 1e-6 * max(1.0, abs(e)) for e in historical)
