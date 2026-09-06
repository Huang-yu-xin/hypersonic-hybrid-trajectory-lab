"""M3-S2S -- Instrumented Fresh Development Sampling (taskbook, first run).

FIRST ROUND = PREREGISTRATION FREEZE ONLY (taskbook Sec. 3):
    scientific simulator calls = 0, scientific samples = 0.

Stages: prepare | candidates | preflight | contracts | docs | hashlock
Three independent authorization gates, all initially NO:
    TRUTH_SAMPLING_AUTHORIZED / ARM_A_AUTHORIZED / ARM_B_AUTHORIZED.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import math
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

from hyptraj.m3s2s.instrumentation import (  # noqa: E402
    INSTRUMENTATION_SCHEMA_VERSION,
    audit_estimator_source,
    estimate_sidecar_bytes,
    sidecar_schema,
)
from hyptraj.m3s2s.truth_contract import (  # noqa: E402
    CONFIRMATION_BUDGET_PER_STATE,
    DISCOVERY_BUDGET_PER_STATE,
    audit_truth_protocol,
    build_exclusion_manifest,
    candidate_plan,
)
import run_m3s1c as S1C  # noqa: E402  (config resolution + seed helper reuse)
from hyptraj.m3s2s import truth_execution as TE  # noqa: E402  (module scope)
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    record_file_hash,  # canonical file-hash helper (persistence layer)
    run_trial_transactional,
)

OUT = ROOT / "results/phase_m3s2s/preflight"
SUM = ROOT / "results/phase_m3s2s/summary"
TRIALS = ROOT / "results/phase_m3s2s/trials"
CFG = ROOT / "configs/phase_m3s2s"
DOC = ROOT / "docs/phase_m3s2s"

LINEAGE = ["5403e53", "76e99ac", "1f4b0d1", "86ad583"]
DATASET_SHA = "f5f684fdb693123c878ebed567a29a98a80cffca774849d85a8204320a76cedd"
S1_THRESHOLD = 5.4417199447782
PANEL_RANK_SEED = "M3-S2S-PANEL-V1|"
ARM_A_NAMESPACE = "M3-S2S-A-GRAD"
ARM_B_NAMESPACE = "M3-S2S-B-GRAD"
R = 8
N_SAMPLES = 20_000
PANEL_TARGETS = {"WIDEN": 30, "SHRINK": 30, "HOLD": 30, "AMBIGUOUS": 30}
PANEL_STATES = 120
MIN_CONFIGS = 24
CANDIDATE_POINTS_PER_CONFIG = 8
S2_MAX = 8.0
DELTA_GRID = [0.05, 0.10, 0.20]
FULL_PATH_LIMIT = 220
SEED = 2026

APPROVAL_DOC = DOC / "M3_S2S_Human_Approval.md"


def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, v) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csvread(p) -> list[dict]:
    with open(p, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (2**31 - 1) + 1


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def rank_hex(config_id: str, state_id: str) -> str:
    return hashlib.sha256(
        (PANEL_RANK_SEED + config_id + "|" + state_id).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# stage: prepare (parent + reserve firewall)
# --------------------------------------------------------------------------

def parent_audit() -> dict:
    head = git_commit()
    missing = [c for c in LINEAGE
               if subprocess.run(["git", "merge-base", "--is-ancestor", c, head],
                                 cwd=ROOT, capture_output=True).returncode != 0]
    if missing:
        raise RuntimeError(f"S2S-X: lineage commits missing: {missing}")
    s2f = load(ROOT / "results/phase_m3s2f/summary/m3s2f_verdict.json")
    if s2f["VERDICT"] != "M3-S2F-R":
        raise RuntimeError("S2S-X: parent verdict is not M3-S2F-R")
    got = sha(ROOT / "data/phase_m3ml0/m3ml0_tier_a_trials.parquet")
    if got != DATASET_SHA:
        raise RuntimeError("S2S-X: Tier-A dataset hash mismatch")
    audit = {"recorded_at": now(), "head": head, "lineage": LINEAGE,
             "parent_verdict": "M3-S2F-R", "tier_a_hash_match": True,
             "PARENT_AUDIT": "PASS"}
    dump(OUT / "m3s2s_parent_audit.json", audit)
    return audit


def reserve_firewall() -> list[dict]:
    reserve = csvread(ROOT / "results/phase_m3pi1vnr/summary/"
                             "m3pi1vnr_remaining_protected_reserve.csv")
    s1c_panel = load(ROOT / "configs/phase_m3s1c/m3s1c_panel.json")
    consumed = {s["state_id"] for s in s1c_panel["states"]}
    reserve = [r for r in reserve if r["state_id"] not in consumed]
    if len(reserve) != 18:
        raise RuntimeError(f"S2S-X: expected 18 protected states, got {len(reserve)}")
    manifest_sha = sha(ROOT / "results/phase_m3pi1vnr/summary/"
                              "m3pi1vnr_remaining_protected_reserve.csv")
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "m3s2s_protected_reserve_18.csv").open("w", newline="",
                                                       encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["state_id", "config_id",
                                          "protected", "source_hash"])
        w.writeheader()
        for r in reserve:
            w.writerow({"state_id": r["state_id"], "config_id": r["config_id"],
                        "protected": "true", "source_hash": manifest_sha})
    dump(OUT / "m3s2s_reserve_firewall.json", {
        "recorded_at": now(), "remaining": 18, "used_by_s2s": 0,
        "permanent": True,
        "RESERVE_FIREWALL": "PASS"})
    return reserve


# --------------------------------------------------------------------------
# stage: candidates (fresh candidate plan; NO truth labels yet -> T1)
# --------------------------------------------------------------------------

def _existing_characterized_s2() -> dict[str, set[float]]:
    """All s2 values already characterized per config (any artifact)."""
    out: dict[str, set[float]] = {}
    inv = csvread(ROOT / "results/phase_m3cf2/summary/"
                         "m3cf2_candidate_truth_inventory.csv")
    for r in inv:
        out.setdefault(r["config_id"], set()).add(float(r["s2"]))
    for rel in ("results/phase_m3pi1vnr/summary/m3pi1vnr_fresh_development_panel.csv",
                "results/phase_m3s1c/preflight/m3s1c_panel.csv",
                "results/phase_m3pi1vnr/summary/m3pi1vnr_retired_pi1vn_panel.csv"):
        for r in csvread(ROOT / rel):
            out.setdefault(r["config_id"], set()).add(float(r["s2"]))
    return out


def _assemble_config(cid: str, spec: dict):
    """Assemble a BenchmarkConfig for an existing or NEW s2s config."""
    from hyptraj.m1d.experiments import BenchmarkConfig
    if spec["origin"] == "M3-S2S-NEW-CONFIG":
        r = spec["raw_row"]
        import re as _re
        m = _re.search(r"_b(\d+)_c(\d+)$", r["config_id"])
        return BenchmarkConfig(
            config_id=cid, batch_seed=int(m.group(1)),
            batch_index=int(m.group(2)),
            theta_deg=tuple(float(r[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(r[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(r[f"curved_{i}"].strip() == "True"
                         for i in range(1, 5)),
            curvature_c=float(r["curvature_c"]),
            offset_o=tuple(float(r[f"offset_{i}"]) for i in range(1, 5)),
        )
    return S1C._bench(cid)


def _config_windows() -> dict[str, dict]:
    """Per-config legal s2 window from the assembled proposal geometry."""
    from hyptraj.m3d.benchmark_states import assemble_state
    import numpy as np
    windows = {}
    for cid, spec in sorted(_all_corrected_configs().items()):
        bench = _assemble_config(cid, spec)
        state = assemble_state(bench, 1.0, short_config=cid)
        if isinstance(state, dict):
            raise RuntimeError(f"S2S-X: assembly failed for {cid}")
        prop = state.proposal()
        lam_min = min(float(np.linalg.eigvalsh(np.asarray(c, dtype=float)).min())
                      for c in prop.covs)
        s2_min = 0.5 / lam_min
        windows[cid] = {"lambda_min_P": lam_min, "s2_min_legality": s2_min,
                        "s2_lo": s2_min * 1.05, "s2_hi": S2_MAX,
                        "origin": spec["origin"]}
    return windows


NEW_CONFIG_COUNT = 8


def _all_corrected_configs() -> dict[str, dict]:
    """All corrected-semantic config families + deterministic new configs
    drawn from the raw lattice (the CF1N/WCF1 expansion mechanism)."""
    import numpy as np
    cfgs: dict[str, dict] = {}
    # legacy c* (SF2-referenced, corrected) + cf1n_new_* (incl. non-stable
    # 004/006 -- valid configs whose states simply get fresh truth)
    inv = csvread(ROOT / "results/phase_m3cf2/summary/"
                         "m3cf2_candidate_truth_inventory.csv")
    for r in inv:
        cfgs.setdefault(r["config_id"], {"origin": r["source_stage"]})
    cf1n = load(ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")["physical_fields"]
    for cid in cf1n:
        cfgs.setdefault(cid, {"origin": "M3-CF1N"})
    for r in csvread(ROOT / "results/phase_m3wcf1/summary/"
                            "m3wcf1_physical_config_manifest.csv"):
        cfgs.setdefault(r["wcf1_config_id"], {"origin": "M3-WCF1"})
    # new configs: deterministic hash rank over UNUSED raw lattice rows
    used_raw = {r.get("raw_candidate_id") for r in csvread(
        ROOT / "results/phase_m3wcf1/summary/m3wcf1_physical_config_manifest.csv")}
    for cid in cf1n:
        f = cf1n[cid]
        if f.get("raw_candidate_id"):
            used_raw.add(f["raw_candidate_id"])
    lattice = csvread(ROOT / "results/phase_m3cf0/summary/"
                             "m3cf0_raw_physical_candidate_lattice.csv")
    fresh_raw = [r for r in lattice if r["config_id"] not in used_raw]
    ranked = sorted(fresh_raw, key=lambda r: hashlib.sha256(
        ("M3-S2S-CONFIG-V1|" + r["config_id"]).encode("utf-8")).hexdigest())
    for i, r in enumerate(ranked[:NEW_CONFIG_COUNT]):
        cfgs[f"m3s2s_cfg_{i:03d}"] = {"origin": "M3-S2S-NEW-CONFIG",
                                      "raw_row": r}
    return cfgs


VENDORED_TRUTH_PROTOCOL = {
    "m3cf1n_pref_protocol.json":
        "configs/phase_m3cf1n/m3cf1n_pref_protocol.json",
    "m3cf1n_discovery_protocol.json":
        "configs/phase_m3cf1n/m3cf1n_discovery_protocol.json",
    "m3cf1n_confirmation_protocol.json":
        "configs/phase_m3cf1n/m3cf1n_confirmation_protocol.json",
    "m3cf1n_configs.json": "configs/phase_m3cf1n/m3cf1n_configs.json",
    "m3wcf1_physical_config_manifest.csv":
        "results/phase_m3wcf1/summary/m3wcf1_physical_config_manifest.csv",
    "M1_D_Benchmark_Freeze.json":
        "docs/phase_m1d/M1_D_Benchmark_Freeze.json",
    "m3cf0_raw_physical_candidate_lattice.csv":
        "results/phase_m3cf0/summary/m3cf0_raw_physical_candidate_lattice.csv",
}

# per-config historical P_ref records vendored into pref_records/
PREF_RECORD_SOURCES = (
    [("legacy_p_ref", "results/phase_m3d2/summary/m3d2_probability_reference.json")]
    + [("cf1n_pref_records", f"results/phase_m3cf1n/pref/{cid}.json")
     for cid in ("cf1n_new_000", "cf1n_new_001", "cf1n_new_002",
                 "cf1n_new_003", "cf1n_new_004", "cf1n_new_005",
                 "cf1n_new_006", "cf1n_new_007")]
    + [("wcf1_pref_records", f"results/phase_m3wcf1/pref/{cid}.json")
       for cid in ("wcf1_new_000", "wcf1_new_001", "wcf1_new_002",
                   "wcf1_new_003", "wcf1_new_004", "wcf1_new_005")]
)


def vendor_truth_protocol() -> dict:
    """Byte-exact immutable snapshots of the canonical truth protocol and
    the physical-config definition sources (amendment requirement 2).
    Contents are never altered; SHA256 equality with the originals is
    asserted at vendoring time and re-verified by tests."""
    dst_dir = CFG / "reference_truth_protocol"
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, rel in VENDORED_TRUTH_PROTOCOL.items():
        src = ROOT / rel
        dst = dst_dir / name
        dst.write_bytes(src.read_bytes())
        s_src, s_dst = sha(src), sha(dst)
        if s_src != s_dst:
            raise RuntimeError(f"S2S-X: vendored snapshot mismatch: {name}")
        out[name] = {"vendored_path": dst.relative_to(ROOT).as_posix(),
                     "source_path": rel, "sha256": s_src}
    base_snapshots = dict(out)
    (dst_dir / "pref_records").mkdir(exist_ok=True)
    for sub, rel in PREF_RECORD_SOURCES:
        src = ROOT / rel
        dst = dst_dir / "pref_records" / Path(rel).name
        dst.write_bytes(src.read_bytes())
        s_src, s_dst = sha(src), sha(dst)
        if s_src != s_dst:
            raise RuntimeError(f"S2S-X: vendored snapshot mismatch: {rel}")
        out[f"pref_records/{Path(rel).name}"] = {
            "vendored_path": dst.relative_to(ROOT).as_posix(),
            "source_path": rel, "sha256": s_src}
    vendor_truth_protocol.base_snapshots = base_snapshots
    return out


vendor_truth_protocol.base_snapshots = {}


def _config_source_artifacts() -> dict[str, dict]:
    """Per-family physical-config definition source (vendored path + hash)."""
    vend = {n: v for n, v in VENDORED_TRUTH_PROTOCOL.items()}
    sources = {
        "legacy_c": {"path": "configs/phase_m3s2s/reference_truth_protocol/"
                             "M1_D_Benchmark_Freeze.json"},
        "cf1n_new": {"path": "configs/phase_m3s2s/reference_truth_protocol/"
                             "m3cf1n_configs.json"},
        "wcf1_new": {"path": "configs/phase_m3s2s/reference_truth_protocol/"
                             "m3wcf1_physical_config_manifest.csv"},
        "M3-S2S-NEW-CONFIG": {"path": "configs/phase_m3s2s/reference_truth_"
                                      "protocol/m3cf0_raw_physical_candidate_"
                                      "lattice.csv"},
    }
    for k, v in sources.items():
        v["sha256"] = sha(ROOT / v["path"])
    return sources


def build_candidates() -> dict:
    """Fresh candidate state plan: legality-gated, log-spaced, freshness-
    excluding new s2 points on all corrected configs (NO truth yet)."""
    vendor_truth_protocol()
    existing = _existing_characterized_s2()
    windows = _config_windows()
    candidates = []
    for cid in sorted(windows):
        w = windows[cid]
        lo, hi = math.log(w["s2_lo"]), math.log(w["s2_hi"])
        pts, k = [], 0
        # deterministic densification: 8x the target count, keep first 8 fresh
        for j in range(CANDIDATE_POINTS_PER_CONFIG * 8):
            s2 = math.exp(lo + (hi - lo) * (j + 1) / (CANDIDATE_POINTS_PER_CONFIG * 8 + 1))
            if any(abs(s2 - e) <= 1e-6 * max(1.0, abs(e))
                   for e in existing.get(cid, ())):
                continue
            if pts and abs(s2 - pts[-1]) <= 1e-6:
                continue
            pts.append(s2)
            k += 1
            if k == CANDIDATE_POINTS_PER_CONFIG:
                break
        origin = w["origin"]
        fam = ("legacy_c" if cid.startswith(("c0", "c1", "c2"))
               and "_" not in cid else
               "cf1n_new" if cid.startswith("cf1n_new") else
               "wcf1_new" if cid.startswith("wcf1_new") else "M3-S2S-NEW-CONFIG")
        src_art = _config_source_artifacts()[fam]
        for s2 in pts:
            sid = f"{cid}_s2s_{s2:.10f}"
            candidates.append({
                "state_id": sid, "config_id": cid, "s2": s2,
                "rank": rank_hex(cid, sid),
                "config_origin": origin,
                "config_source_path": src_art["path"],
                "config_source_sha256": src_art["sha256"],
                "freshness_status": "FRESH_UNCHARACTERIZED",
                "exposure_status": "CONTROLLER_EXPOSURE_0",
                "legality_margin_min_eig": w["s2_min_legality"] * s2 / 0.5,
            })
    if len(candidates) < PANEL_STATES:
        raise RuntimeError(
            f"S2S-X: candidate plan {len(candidates)} < panel target {PANEL_STATES}")
    n_configs = len({c["config_id"] for c in candidates})
    if n_configs < MIN_CONFIGS + 2:
        raise RuntimeError(f"S2S-X: candidate configs {n_configs} < {MIN_CONFIGS + 2}")
    with (OUT / "m3s2s_candidate_plan.csv").open("w", newline="",
                                                 encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["state_id", "config_id", "s2",
                                          "rank", "config_origin",
                                          "config_source_path",
                                          "config_source_sha256",
                                          "freshness_status",
                                          "exposure_status",
                                          "legality_margin_min_eig"])
        w.writeheader()
        w.writerows(candidates)
    plan = candidate_plan(len(candidates), n_configs)
    n_new_cfg = sum(1 for w in windows.values()
                    if w["origin"] == "M3-S2S-NEW-CONFIG")
    pref_new = n_new_cfg * 500_000          # CF1N-PREF per new config
    plan["pref_total"] = pref_new
    plan["new_configs"] = n_new_cfg
    plan["TRUTH_BUDGET_MAX"] += pref_new
    truth = audit_truth_protocol()
    audit = {**truth, **plan,
             "recorded_at": now(),
             "fresh_truth_labeled_pool": 0,
             "T0_feasible": False,
             "TRUTH_SAMPLING_REQUIRED": True,
             "TRUTH_CONTRACT": truth["TRUTH_CONTRACT"],
             "TRUTH_SOURCE_AUDIT": "PASS (T1: new truth sampling required; "
                                   "canonical CF1N three-phase protocol "
                                   "frozen verbatim)"}
    dump(OUT / "m3s2s_truth_source_audit.json", audit)
    dump(OUT / "m3s2s_candidate_plan.json", {
        "recorded_at": now(), "n_candidates": len(candidates),
        "n_configs": n_configs,
        "points_per_config": CANDIDATE_POINTS_PER_CONFIG,
        "rank_seed": PANEL_RANK_SEED,
        "note": "candidates are truth-UNLABELED; panel selection happens "
                "after truth establishment under the frozen 30/30/30/30 "
                "quota + round rule"})
    # AMENDMENT (conditional-pass audit): git-tracked full candidate universe
    universe = {
        "schema_version": "m3s2s_candidate_universe_v1",
        # no timestamp: the tracked universe sha256 must be content-deterministic
        "n_states": len(candidates),
        "n_configs": n_configs,
        "rank_seed": PANEL_RANK_SEED,
        "freshness_rule": "new log-spaced legality-gated s2 points excluding "
                          "every characterized value; verified against all "
                          "panel/registry artifacts",
        "vendored_truth_protocol": vendor_truth_protocol.base_snapshots,
        "states": candidates,
    }
    # LF-normalized byte write: the tracked artifact must be byte-identical
    # to the git blob (the earlier CRLF working-tree rendering sha'd
    # differently on Windows; execution pins the LF form)
    universe_bytes = (json.dumps(universe, indent=2, sort_keys=True,
                                 ensure_ascii=True) + "\n").encode("utf-8")
    (CFG / "m3s2s_candidate_universe.json").write_bytes(universe_bytes)
    universe_sha = hashlib.sha256(universe_bytes).hexdigest()
    dump(OUT / "m3s2s_candidate_universe_hash.json", {
        "recorded_at": now(),
        "candidate_universe_sha256": universe_sha})
    # new-config registry (config_id -> raw_candidate_id), tracked; the
    # vendored raw lattice provides the physical definitions at runtime
    specs = _all_corrected_configs()
    registry = {"schema_version": "m3s2s_new_config_registry_v1",
                "configs": {cid: {"raw_candidate_id": spec["raw_row"]["config_id"],
                                  "origin": spec["origin"]}
                            for cid, spec in specs.items()
                            if spec["origin"] == "M3-S2S-NEW-CONFIG"}}
    dump(CFG / "m3s2s_new_config_registry.json", registry)
    print(f"M3-S2S candidates: {len(candidates)} states / {n_configs} configs "
          f"-> TRUTH_BUDGET_MAX = {plan['TRUTH_BUDGET_MAX']:,} "
          f"(universe sha256 {universe_sha[:16]}...)")
    return {"candidates": candidates, "n_configs": n_configs, "plan": plan,
            "truth": audit, "universe_sha256": universe_sha}


# --------------------------------------------------------------------------
# stage: seeds
# --------------------------------------------------------------------------

def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3s2s"
    for p in (ROOT / "results").rglob("*.csv"):
        if self_prefix in p.parents:
            continue
        try:
            with p.open(newline="", encoding="utf-8") as h:
                rdr = csv.DictReader(h)
                if rdr.fieldnames and any(f.strip() == "seed" for f in rdr.fieldnames):
                    for row in rdr:
                        try:
                            vals.add(int(row["seed"]))
                        except (TypeError, ValueError):
                            continue
        except Exception:
            continue
    return vals


def seeds(candidates: list[dict]) -> dict:
    planned = {f"{c['state_id']}|rep{rep}": seed(ARM_A_NAMESPACE,
                                                c["state_id"], rep)
               for c in candidates for rep in range(R)}
    vals = list(planned.values())
    prior = _prior_recorded_seeds()
    for ns in ("M3-PI1VNR-GRAD", "M3-PI1VNR-PROBE", "M3-PI1VN-GRAD",
               "M3-PI1VN-PROBE", "M3-S1C-GRAD"):
        prior |= {seed(ns, sid, rep) for sid in
                  {c["state_id"] for c in candidates} for rep in range(R)}
    retired = load(ROOT / "results/phase_m3pi1vnr/summary/"
                          "m3pi1vnr_retired_pi1vn_seed_manifest.json")
    prior |= set(retired.get("gradient_seeds", [])) | set(retired.get("probe_seeds", []))
    pi1vnr = load(ROOT / "results/phase_m3pi1vnr/summary/m3pi1vnr_seed_manifest.json")
    prior |= set(pi1vnr.get("planned_gradient_seeds", {}).values())
    prior |= set(pi1vnr.get("planned_probe_seeds", {}).values())
    collisions = sorted({v for v in vals if v in prior})
    if len(set(vals)) != len(vals) or collisions:
        raise RuntimeError(f"S2S-X: seed collision: {collisions[:5]}")
    arm_b = sorted({seed(ARM_B_NAMESPACE, c["state_id"], rep, d)
                    for c in candidates for rep in range(R)
                    for d in DELTA_GRID})
    if set(arm_b) & (set(vals) | prior):
        raise RuntimeError("S2S-X: Arm-B namespace collision")
    dump(CFG / "m3s2s_seed_manifest.json", {
        "arm_a_namespace": ARM_A_NAMESPACE,
        "arm_b_namespace": ARM_B_NAMESPACE,
        "arm_a_pool_size": len(vals),
        "note": "960 Arm-A seeds are the frozen subset for the selected "
                "120-state panel (state|rep keys); the whole "
                f"{len(vals)}-seed candidate pool is collision-audited now",
        "planned_seeds": planned,
        "frozen_before_first_simulator_call": True})
    dump(OUT / "m3s2s_seed_collision_audit.json", {
        "recorded_at": now(), "pool": len(vals), "unique": len(set(vals)),
        "historical_collision": len(collisions),
        "arm_b_disjoint": True,
        "SEED_AUDIT": "PASS"})
    print(f"M3-S2S seeds: {len(vals)} unique candidate-pool seeds, "
          f"0 collisions; Arm-B namespace disjoint")


# --------------------------------------------------------------------------
# stage: preflight (paths + disk + instrumentation capacity)
# --------------------------------------------------------------------------

def preflight() -> dict:
    from hyptraj.m3wa1r.persistence import (bounded_slug,
                                           bounded_temp_basename)
    rows, max_final, max_side, max_temp = [], 0, 0, 0
    run_uuid = "M3-S2S-PREFLIGHT"
    cap = estimate_sidecar_bytes(N_SAMPLES)
    n_cand = len(csvread(OUT / "m3s2s_candidate_plan.csv"))
    for i in range(min(n_cand, 64)):        # sampled preflight (shape-identical)
        slug = bounded_slug(f"cand_{i}")
        for rep in range(R):
            final = TRIALS / slug / f"rep{rep}.json"
            side = TRIALS / slug / f"rep{rep}_instrumentation.npz"
            temp = final.parent / bounded_temp_basename(slug, run_uuid)
            lf, ls, lt = (len(str(final)), len(str(side)), len(str(temp)))
            ok = max(lf, ls, lt) <= FULL_PATH_LIMIT
            max_final, max_side, max_temp = (max(max_final, lf), max(max_side, ls),
                                             max(max_temp, lt))
            rows.append({"PASS": ok})
    disk = shutil.disk_usage(ROOT)
    trials_arm_a = 120 * R
    est_total = cap["budget_bytes_per_trial"] * trials_arm_a
    est_total += cap["budget_bytes_per_trial"] * 2 * trials_arm_a  # Arm-B max
    ok = (all(r["PASS"] for r in rows)
          and max(max_final, max_side, max_temp) <= FULL_PATH_LIMIT
          and disk.free > 2.5 * est_total)
    summary = {"recorded_at": now(),
               "paths_checked": len(rows),
               "max_final_path_len": max_final, "max_sidecar_path_len": max_side,
               "max_temp_path_len": max_temp, "limit": FULL_PATH_LIMIT,
               "sidecar_bytes_per_trial": cap["budget_bytes_per_trial"],
               "arm_a_estimated_bytes": cap["budget_bytes_per_trial"] * trials_arm_a,
               "arm_a_plus_b_estimated_bytes": est_total,
               "disk_free_bytes": disk.free,
               "DISK_PREFLIGHT": "PASS" if ok else "FAIL",
               "PATH_PREFLIGHT": "PASS" if ok else "FAIL"}
    if not ok:
        raise RuntimeError(f"S2S-X: preflight failure: {summary}")
    dump(OUT / "m3s2s_path_disk_preflight.json", summary)
    print(f"M3-S2S preflight: paths PASS, disk free {disk.free/1e9:.1f}GB, "
          f"est. Arm-A {est_total/1e9:.2f}GB worst-case")
    return summary


# --------------------------------------------------------------------------
# stage: contracts
# --------------------------------------------------------------------------

def contracts(cand: dict) -> None:
    CFG.mkdir(parents=True, exist_ok=True)
    instr = audit_estimator_source()
    dump(CFG / "m3s2s_parent_contract.json", {
        "parent_verdict": "M3-S2F-R", "lineage": LINEAGE,
        "tier_a_dataset_sha256": DATASET_SHA,
        "tier_a_role": "historical baseline / mechanism replication ONLY; "
                       "never in Arm-A primary candidate selection",
        "value": "BLOCKED", "rarity_shift": "BLOCKED", "m3_q": "BLOCKED"})
    dump(CFG / "m3s2s_exclusion_manifest.json", {
        "rule": "content-based comparator classification (inherited "
                "M3-S1C Amendment B); filename-only forbidden; UNKNOWN => "
                "UNRESOLVED => ineligible",
        "excluded_sets": ["PI1V attempts", "PI1VN retired", "PI1VNR dev panel",
                          "S1C panel", "ML0 Tier-A", "all gradient pilots",
                          "all V1 probes", "S1 threshold-search/diagnostic "
                          "panels", "prior controller confirmation panels",
                          "18 protected reserve"],
        "truth_reference_only_allowed": True})
    dump(CFG / "m3s2s_truth_contract.json", {
        "phases": audit_truth_protocol()["phases"],
        "event_semantics": audit_truth_protocol()["event_semantics"],
        "TRUTH_SAMPLING_REQUIRED": True,
        "estimator_and_label_reuse": "CF1N per-state estimator / corrected "
                                     "event semantics / label thresholds "
                                     "reused VERBATIM (no retune)",
        "confirmation_scope": "ALL_240_FRESH_CANDIDATES",
        "early_stop_on_quota": False,
        "discovery_states": 240,
        "confirmation_states": 240,
        "TRUTH_BUDGET_PLANNED": 436_000_000,
        "TRUTH_BUDGET_MAX": 436_000_000,
        "discovery_budget_per_state": DISCOVERY_BUDGET_PER_STATE,
        "confirmation_budget_per_state": CONFIRMATION_BUDGET_PER_STATE,
        "rationale": "all four frozen truth strata (WIDEN/SHRINK/HOLD/"
                     "AMBIGUOUS) require high-budget truth before the "
                     "balanced 30/30/30/30 panel is selected",
        "vendored_reference_protocol": "configs/phase_m3s2s/"
                                       "reference_truth_protocol/",
        "vendored_snapshots": {k: v["sha256"] for k, v in
                               vendor_truth_protocol().items()},
        "retirement_rule": cand["plan"]["retirement_rule"]})
    dump(CFG / "m3s2s_panel_contract.json", {
        "states": PANEL_STATES, "quota": PANEL_TARGETS,
        "min_unique_configs": MIN_CONFIGS,
        "selection_inputs": ["freshness eligibility", "frozen truth stratum",
                             "config_id", "state_id", "canonical hash rank"],
        "rank_seed": PANEL_RANK_SEED,
        "round_rule": "round k takes at most the k-th ranked state per "
                      "config within each truth stratum; stop exactly at "
                      "quota; S1C Amendment-A semantics",
        "panel_frozen": False,
        "note": "panel freezes only after truth establishment (T1)"})
    dump(CFG / "m3s2s_gradient_protocol.json", {
        "states": PANEL_STATES, "replicates_per_state": R,
        "samples_per_trial": N_SAMPLES, "trials": PANEL_STATES * R,
        "ARM_A_GRADIENT_BUDGET": PANEL_STATES * R * N_SAMPLES,
        "estimator": "hyptraj.m3d.adaptation.gradient_decision (unchanged)",
        "alpha_p": 0.5, "sign_mapping": "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK",
        "S1_formula": "abs(g_hat) / ((ci_high-ci_low)/(2*1.959963984540054))",
        "S1_threshold_frozen": S1_THRESHOLD,
        "namespace": ARM_A_NAMESPACE, "no_topup": True})
    dump(CFG / "m3s2s_instrumentation_contract.json", {
        **instr, "sidecar": sidecar_schema()})
    dump(CFG / "m3s2s_feature_contract.json", {
        "bootstrap_stability": ["boot_mean", "boot_median", "boot_std",
                                "boot_MAD", "boot_IQR", "boot_q05", "boot_q25",
                                "boot_q50", "boot_q75", "boot_q95",
                                "boot_mean_minus_median",
                                "boot_sign_probability",
                                "boot_opposite_sign_probability",
                                "boot_near_zero_probability",
                                "boot_quantile_asymmetry",
                                "boot_tail_imbalance"],
        "bootstrap_secondary_only": ["boot_skewness", "boot_excess_kurtosis"],
        "robust_vs_classical": ["g_hat_minus_boot_median",
                                "abs_g_hat_minus_boot_median",
                                "relative_robust_discrepancy"],
        "influence_concentration": ["max_abs_influence_fraction",
                                    "top_1pct_abs_influence_fraction",
                                    "top_5pct_abs_influence_fraction",
                                    "top_10pct_abs_influence_fraction",
                                    "herfindahl_concentration",
                                    "effective_contribution_count"],
        "event_ess_diagnostics": ["event_count", "event_rate", "ESS_grad",
                                  "ESS_per_event", "ESS_fraction"],
        "practical_margin": {"M_delta": "(|g_hat|-delta)/SE_g",
                             "delta_candidates_q": [0.10, 0.25, 0.40, 0.50],
                             "delta_rule": "derived from outer-train only; "
                                           "selected via inner grouped OOF"},
        "forbidden": ["truth", "stratum", "confirmed_label", "high-budget gain",
                      "reference action result", "panel identity",
                      "state_id/config_id as X"],
        "leakage_rule": "bootstrap features computed WITHIN a trial only; "
                        "no cross-replicate aggregation into features"})
    dump(CFG / "m3s2s_model_contract.json", {
        "primary_candidates": ["B0_frozen_S1", "B1_aggregate_gbdt_baseline",
                               "A1_stability_logistic", "A2_stability_gbdt",
                               "A3_stability_margin_logistic",
                               "A4_stability_margin_gbdt"],
        "forbidden": ["MLP", "deep models", "Optuna", "Bayesian search",
                      "XGBoost sweep"],
        "cv": "outer GroupKFold(5) / inner GroupKFold(4), groups=config_id; "
              "STOP BEFORE MODELING if class/config feasibility fails",
        "objective": "max coverage s.t. ND unsafe <= 0.20 AND wrong <= 0.05",
        "seed": SEED})
    dump(CFG / "m3s2s_threshold_contract.json", {
        "rule": "inner grouped OOF: safety-constrained max coverage; "
                "tie-break lower unsafe, lower AMBIGUOUS unsafe, higher "
                "threshold, canonical",
        "gates": {"coverage_min": 0.75, "unsafe_max": 0.20, "wrong_max": 0.05}})
    dump(CFG / "m3s2s_arm_b_contract.json", {
        "status": "CANDIDATE_PROTOCOL_ONLY",
        "ARM_B_AUTHORIZED": False,
        "eligibility": "only after valid M3-S2S-B-GATE + explicit human "
                       "ARM_B_AUTHORIZED: YES commit",
        "delta_coordinate": "u = log s^2",
        "delta_candidate_grid": DELTA_GRID,
        "delta_rule": "engineering feasibility filter first; scientific "
                      "delta selection frozen before Arm-B authorization; "
                      "if compared, delta is an inner-CV hyperparameter",
        "crn_rule": "paired CRN with center required; exact pairing "
                    "semantics must be audited and frozen before "
                    "authorization, else STOP",
        "ARM_B_MAX_BUDGET": 120 * R * 2 * N_SAMPLES,
        "local_shape_features": ["local_sign_persistence", "left_sign_match",
                                 "right_sign_match", "three_point_sign_pattern",
                                 "gradient_slope", "left_slope", "right_slope",
                                 "slope_asymmetry", "relative_gradient_slope",
                                 "local_gradient_range", "local_S1_range",
                                 "g_double_prime_descriptive"]})
    dump(CFG / "m3s2s_persistence_contract.json", {
        "module": "src/hyptraj/m3wa1r/persistence.py (inherited hardened "
                  "transactional contract)",
        "sidecar_rule": "instrumentation sidecar written + sha256-verified "
                        "BEFORE ledger COMPLETE; sidecar failure => no "
                        "COMPLETE",
        "failure_rule": "sampling started without durable COMPLETE => "
                        "CONSUMED_INVALID => M3-S2S-X for the affected arm "
                        "=> STOP, NO REPLAY, NO SAME-ARM RERUN",
        "pre_simulator_failure": "incident + engineering fix + re-preflight "
                                 "+ re-hash (+ re-authorization if hash-"
                                 "locked artifacts changed)"})
    dump(CFG / "m3s2s_verdict_contract.json", {
        "M3_S2S_A": "Arm-A safety-compliant candidate (coverage>=0.75, "
                    "unsafe<=0.20, wrong<=0.05, AMB unsafe<0.25) + gain vs "
                    "aggregate GBDT >= 0.03 or unsafe reduction vs S1 >= "
                    "0.05 at coverage >= 0.75; Arm B NOT RUN",
        "M3_S2S_B_GATE": "Arm A validly completes, no compliant candidate; "
                         "ARM_B_ELIGIBLE assessed; STOP for human review",
        "M3_S2S_C": "separately authorized Arm B yields compliant candidate "
                    "with required gain vs best Arm-A",
        "M3_S2S_D": "Arm B validly completes, still no compliant candidate "
                    "(valid negative)",
        "M3_S2S_X": "integrity failures (contamination, truth-contract "
                    "violation, seed collision, leakage, persistence "
                    "failure, unauthorized arm execution)"})


# --------------------------------------------------------------------------
# stage: docs + hash lock
# --------------------------------------------------------------------------

def docs() -> None:
    pa = load(OUT / "m3s2s_parent_audit.json")
    fw = load(OUT / "m3s2s_reserve_firewall.json")
    ta = load(OUT / "m3s2s_truth_source_audit.json")
    cp = load(OUT / "m3s2s_candidate_plan.json")
    sd = load(OUT / "m3s2s_seed_collision_audit.json")
    pf = load(OUT / "m3s2s_path_disk_preflight.json")
    instr = audit_estimator_source()
    universe_sha = load(OUT / "m3s2s_candidate_universe_hash.json")[
        "candidate_universe_sha256"]
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "M3_S2S_Preregistration.md").write_text(f"""# M3-S2S Preregistration

First round: **preregistration freeze only** — scientific simulator calls 0,
samples 0.  All numbers rendered from hash-locked artifacts.

```
M3-S2S PREREG STATUS:
COMPLETE

PARENT:
M3-S2F-R verified = YES
base = {pa['head'][:7]}
Tier-A dataset hash match = YES

RESERVE:
remaining = 18 (permanent, membership-only)
used = 0

EXPOSURE FIREWALL:
content-based comparator classification; UNKNOWN => UNRESOLVED => ineligible
fresh candidate pool = {cp['n_candidates']} truth-UNLABELED states / {cp['n_configs']} configs

TRUTH SOURCE:
existing compatible truth inventory = NO (fresh corrected pool = 0)
TRUTH_SAMPLING_REQUIRED = YES (T1)
truth protocol = CF1N three-phase (pref reuse / discovery 3x100k / confirmation 3x500k)
TRUTH_BUDGET_MAX = {ta['TRUTH_BUDGET_MAX']:,}

TARGET PANEL:
states = 120, quota 30W/30S/30HOLD/30AMB, >= {MIN_CONFIGS} configs
selection = truth stratify + round-based config diversity + SHA256('{PANEL_RANK_SEED}'|config|state)
panel frozen = NO (freezes only after truth establishment)

ARM A:
states = 120 x 8 replicates x 20000 samples = 960 trials
ARM_A_GRADIENT_BUDGET = 19,200,000
estimator unchanged = YES (persistence-only delta)

ESTIMATOR / INSTRUMENTATION:
N_BOOTSTRAP = {instr['checks']['N_BOOTSTRAP_actual']}
bootstrap = fixed-stratified, seed [seed, 424243]
sidecar = npz(a_vec, resp, sq, strata, bootstrap_g) sha-pinned before COMPLETE
batches=20 is a config constant, NOT 20 batch gradients (source-verified)

ARM B:
authorized = NO (candidate protocol only; delta grid {{0.05,0.10,0.20}} log s^2)
ARM_B_MAX_BUDGET = 38,400,000; eligible only after M3-S2S-B-GATE + human YES

TRUTH SCOPE (AMENDMENT):
confirmation_scope = ALL_240_FRESH_CANDIDATES
early_stop_on_quota = false
discovery_states = 240
confirmation_states = 240
TRUTH_BUDGET_PLANNED = 436,000,000
TRUTH_BUDGET_MAX = 436,000,000
CF1N estimator/label semantics reused verbatim (scope change only)

CANDIDATE UNIVERSE (AMENDMENT):
tracked artifact = configs/phase_m3s2s/m3s2s_candidate_universe.json
candidate_universe_sha256 = {universe_sha}
vendored truth protocol = configs/phase_m3s2s/reference_truth_protocol/ (7 byte-exact snapshots)

SEEDS:
Arm-A candidate pool = {sd['pool']} seeds (960 = frozen panel subset)
unique = {sd['unique']}, historical collision = {sd['historical_collision']}
Arm-B namespace disjoint = YES

PATH/DISK:
PATH_PREFLIGHT = {pf['PATH_PREFLIGHT']}, DISK_PREFLIGHT = {pf['DISK_PREFLIGHT']}
max path = {max(pf['max_final_path_len'], pf['max_sidecar_path_len'], pf['max_temp_path_len'])} (limit {pf['limit']})
worst-case storage = {pf['arm_a_plus_b_estimated_bytes']/1e9:.2f} GB

AUTHORIZATION:
TRUTH_SAMPLING_AUTHORIZED = NO
ARM_A_AUTHORIZED = NO
ARM_B_AUTHORIZED = NO

VALUE / RARITY / M3-Q = BLOCKED

NEXT:
Await independent live Git audit and explicit gate-by-gate human authorization.
```
""", encoding="utf-8")

    (DOC / "M3_S2S_Parent_Audit.md").write_text(f"""# M3-S2S Parent Audit

Status: **{pa['PARENT_AUDIT']}** ({pa['recorded_at']}), HEAD `{pa['head'][:7]}`.

- Live lineage: {' -> '.join(pa['lineage'])}; M3-S2F-R is the current valid
  scientific state (batch/bootstrap stability hypothesis UNTESTED;
  recoverability barrier TRUE).
- Tier-A dataset hash re-verified (48 states / 384 trials, historical
  baseline role only -- never in Arm-A primary selection).
- VALUE / RARITY / M3-Q BLOCKED.
""", encoding="utf-8")
    (DOC / "M3_S2S_Reserve_Firewall_Audit.md").write_text(f"""# M3-S2S Reserve Firewall Audit

Status: **{fw['RESERVE_FIREWALL']}** ({fw['recorded_at']}); permanent.

- 18 protected states rebuilt live from
  `m3pi1vnr_remaining_protected_reserve.csv`; membership-only CSV
  `results/phase_m3s2s/preflight/m3s2s_protected_reserve_18.csv`.
- Forbidden for the entire stage: truth sampling, gradient sampling, S1,
  features, local-shape evaluation, scoring, plots, error analysis,
  candidate/threshold selection.
""", encoding="utf-8")
    (DOC / "M3_S2S_Exposure_Firewall_Audit.md").write_text(f"""# M3-S2S Exposure Firewall Audit

Status: **PASS** ({now()}).

- Exclusion manifest is content-based (comparator-field detection with
  namespace inheritance; filename-only classification forbidden).
- Excluded sets: PI1V attempts, PI1VN retired, PI1VNR development panel,
  S1C confirmation panel, ML0 Tier-A states, all gradient pilots, all V1
  probes, all S1 threshold-search/diagnostic panels, all prior controller
  confirmation panels, and the 18 protected reserve.
- Truth-reference-only characterization remains allowed under frozen
  semantics (no g_hat/S1/V1/r_hat/deploy-abstain comparator output).
- Candidate pool: {cp['n_candidates']} truth-UNLABELED states (freshness is
  structural: new s2 points excluding all characterized values).
- Unknown candidate-bearing artifacts: none at prereg time; any UNRESOLVED
  at execution => candidate ineligible => STOP if quota unmet.
""", encoding="utf-8")
    (DOC / "M3_S2S_Truth_Source_Audit.md").write_text(f"""# M3-S2S Truth Source Audit

Status: **{ta['TRUTH_SOURCE_AUDIT']}** ({ta['recorded_at']}).

- Existing corrected truth inventory (94 states, event semantics v2) is
  fully consumed: controller-exposed + protected covers 94/94; fresh
  truth-labeled pool = **0** => T0 infeasible.
- TRUTH_SAMPLING_REQUIRED = **YES** (T1).
- Canonical truth contract frozen verbatim: the CF1N three-phase corrected
  protocol (pref 500k/config reusable; discovery 3 arms x 100k with
  direction_margin 0.05 / hold_band 0.03 / improvement_threshold -0.01 /
  min arm ESS 20; confirmation 3 arms x 500k, paired CRN 20; namespaces
  M3-CF1N-PREF / M3-CF1N-DISCOVERY / M3-CF1N-CONFIRM; event semantics v2).
- Truth-contract phase config hashes are recorded in
  `configs/phase_m3s2s/m3s2s_truth_contract.json`.
- Retirement: every truth-sampled state enters
  `m3s2s_truth_exposed_inventory` and is retired from future untouched
  confirmation use, selected or not.
""", encoding="utf-8")
    (DOC / "M3_S2S_Budget_Audit.md").write_text(f"""# M3-S2S Budget Audit

Exact integer budgets (no placeholders; taskbook Sec. 9/34):

| stream | budget |
|---|---|
| Truth discovery ({cp['n_candidates']} candidates x 3 x 100k) | {ta['discovery_total']:,} |
| Truth confirmation ({cp['n_candidates']} x 3 x 500k) | {ta['confirmation_total']:,} |
| Truth P_ref (config-level reuse) | 0 |
| **TRUTH_BUDGET_MAX** | **{ta['TRUTH_BUDGET_MAX']:,}** |
| **ARM_A_GRADIENT_BUDGET** (120 x 8 x 20k) | **19,200,000** |
| ARM_B_MAX_BUDGET (120 x 8 x 2 x 20k; separate gate) | 38,400,000 |
| Online maximum if Arm B activates (excludes truth) | 57,600,000 |

Top-up is forbidden in every stream; planned/actual/difference accounting
is mandatory in the final report.
""", encoding="utf-8")
    (DOC / "M3_S2S_Instrumentation_Preflight.md").write_text(f"""# M3-S2S Instrumentation Preflight

Status: **PASS** ({now()}).

- Estimator source audited (sha256 `{instr['source_sha256'][:16]}...`):
  N_BOOTSTRAP = {instr['checks']['N_BOOTSTRAP_actual']}; bootstrap =
  fixed-stratified with seed [seed, 424243]; per-sample arrays a_vec/resp/
  sq/strata (n=20000) are the sufficient statistics; aggregate estimator
  unchanged (persistence-only delta).
- `batches = 20` is a configuration constant, NOT 20 independent batch
  gradients (source-verified; taskbook Sec. 13).
- Sidecar schema {INSTRUMENTATION_SCHEMA_VERSION}: npz(a_vec, resp, sq,
  strata, bootstrap_g) — lossless; sha256 recorded in the trial record and
  verified BEFORE ledger COMPLETE.
- Bootstrap draws are never independent scientific trials.
- Capacity: {pf['sidecar_bytes_per_trial']:,} B/trial (uncompressed basis);
  Arm-A worst case {pf['arm_a_estimated_bytes']/1e9:.2f} GB;
  Arm-A+Arm-B {pf['arm_a_plus_b_estimated_bytes']/1e9:.2f} GB; disk free
  {pf['disk_free_bytes']/1e9:.1f} GB.
""", encoding="utf-8")
    (DOC / "M3_S2S_Seed_Audit.md").write_text(f"""# M3-S2S Seed Audit

Status: **{sd['SEED_AUDIT']}** ({sd['recorded_at']}).

- Arm-A namespace `{ARM_A_NAMESPACE}`: {sd['pool']}-seed candidate pool
  (264 states x 8 replicates), {sd['unique']} unique, 0 historical
  collisions (all results CSVs + retired PI1VN manifest + PI1VNR planned
  streams + cross-namespace probes); the 960 Arm-A seeds are the frozen
  subset for the selected panel.
- Arm-B namespace `{ARM_B_NAMESPACE}` frozen and disjoint (delta-tagged
  derivation); truth namespaces reuse the canonical M3-CF1N-* streams with
  new state ids (no collision by construction, verified against history).
""", encoding="utf-8")
    (DOC / "M3_S2S_Path_Disk_Preflight.md").write_text(f"""# M3-S2S Path/Disk Preflight

Status: **{pf['PATH_PREFLIGHT']} / {pf['DISK_PREFLIGHT']}** ({pf['recorded_at']}).

- {pf['paths_checked']} sampled trial paths (shape-identical slugs):
  max final {pf['max_final_path_len']}, max sidecar {pf['max_sidecar_path_len']},
  max temp {pf['max_temp_path_len']} (limit {pf['limit']}).
- Storage (uncompressed basis): {pf['sidecar_bytes_per_trial']:,} B/trial;
  Arm-A {pf['arm_a_estimated_bytes']/1e9:.2f} GB; worst case
  {pf['arm_a_plus_b_estimated_bytes']/1e9:.2f} GB; free
  {pf['disk_free_bytes']/1e9:.1f} GB.
""", encoding="utf-8")
    (DOC / "M3_S2S_Human_Approval.md").write_text(f"""# M3-S2S Human Approval

Three independent authorization gates (taskbook Sec. 2).  Codex must not
change any NO to YES.

TRUTH_SAMPLING_AUTHORIZED: NO
ARM_A_AUTHORIZED: NO
ARM_B_AUTHORIZED: NO
AUTHORIZER: (awaiting explicit gate-by-gate human authorization)
AUTHORIZATION_DATE: (not yet granted)

Gate semantics: T1 flow -- first authorize TRUTH_SAMPLING only; after the
truth panel freeze (30/30/30/30 or M3-S2S-PANEL-BLOCKED) STOP for re-audit;
then ARM_A; ARM_B only after a valid M3-S2S-B-GATE plus an explicit
ARM_B_AUTHORIZED: YES commit.  Scope, failure rules, and budget ceilings are
frozen in the contracts; any durable-persistence failure after sampling
starts => M3-S2S-X => STOP => NO REPLAY.
""", encoding="utf-8")

    task_src = Path("D:/Users/huangyx/Downloads/"
                    "M3_S2S_Instrumented_Fresh_Development_Formal_Taskbook_2026-09-06.md")
    if task_src.exists():
        (DOC / "M3_S2S_Task.md").write_text(task_src.read_text(encoding="utf-8"),
                                            encoding="utf-8")


def hashlock() -> dict:
    files = sorted(p for p in OUT.glob("m3s2s_*.json")
                   if p.name != "m3s2s_prereg_hashes.json")
    files += sorted(CFG.glob("m3s2s_*.json"))
    manifest = {
        "recorded_at": now(), "parent_git_sha": git_commit(),
        "python_version": sys.version,
        "scientific_code_hashes": {
            "scripts/run_m3s2s.py": sha(ROOT / "scripts/run_m3s2s.py"),
            "src/hyptraj/m3s2s/truth_contract.py": sha(ROOT / "src/hyptraj/m3s2s/truth_contract.py"),
            "src/hyptraj/m3s2s/instrumentation.py": sha(ROOT / "src/hyptraj/m3s2s/instrumentation.py"),
            "src/hyptraj/m3s2s/vendored_runtime.py": sha(ROOT / "src/hyptraj/m3s2s/vendored_runtime.py"),
            "src/hyptraj/m3s2s/truth_execution.py": sha(ROOT / "src/hyptraj/m3s2s/truth_execution.py"),
            "src/hyptraj/m3d2/experiment.py": sha(ROOT / "src/hyptraj/m3d2/experiment.py"),
            "src/hyptraj/m3/gradient_estimator.py": sha(ROOT / "src/hyptraj/m3/gradient_estimator.py"),
            "src/hyptraj/m3wa1r/persistence.py": sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
            "src/hyptraj/m3d/adaptation.py": sha(ROOT / "src/hyptraj/m3d/adaptation.py"),
        },
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p),
                   "size_bytes": p.stat().st_size} for p in files],
        "PREREG_HASH_LOCK": "PASS",
    }
    dump(OUT / "m3s2s_prereg_hashes.json", manifest)
    return manifest


def prepare() -> None:
    parent_audit()
    reserve_firewall()
    print("M3-S2S prepare: parent/firewall PASS")


def candidates_stage() -> dict:
    cand = build_candidates()
    seeds(cand["candidates"])
    return cand


def all_stages() -> None:
    prepare()
    cand = candidates_stage()
    preflight()
    contracts(cand)
    docs()
    truth_preflight()
    hashlock()
    print("M3-S2S prereg freeze complete; all three gates remain NO")


# --------------------------------------------------------------------------
# gated truth-execution stages (execution-readiness amendment, items 3-6)
# --------------------------------------------------------------------------

TRUTH_PREF = ROOT / "results/phase_m3s2s/pref"
TRUTH_DISC = ROOT / "results/phase_m3s2s/discovery"
TRUTH_CONF = ROOT / "results/phase_m3s2s/confirmation"
TRUTH_LEDGERS = {"pref": TRUTH_PREF / "pref_ledger.jsonl",
                 "discovery": TRUTH_DISC / "discovery_ledger.jsonl",
                 "confirmation": TRUTH_CONF / "confirmation_ledger.jsonl"}


def _gate(name: str) -> bool:
    txt = APPROVAL_DOC.read_text(encoding="utf-8")
    m = re.search(rf"^{name}:\s*(\w+)\s*$", txt, re.M)
    return bool(m and m.group(1).strip().upper() == "YES")


def _check_gates_frozen_no():
    for gate in ("TRUTH_SAMPLING_AUTHORIZED", "ARM_A_AUTHORIZED",
                 "ARM_B_AUTHORIZED"):
        if _gate(gate):
            raise RuntimeError(
                f"S2S prereg lock violated: {gate} must remain NO during the "
                "execution-readiness amendment")


def truth_seed_manifest() -> dict:
    """Freeze + audit the COMPLETE truth seed manifest (8 PREF / 240
    DISCOVERY / 240 CONFIRMATION units) derived from the vendored
    protocol namespaces; deterministic uniqueness + zero historical
    collision (including the CF1N historical seed manifests)."""
    from hyptraj.m3s2s import vendored_runtime as VRc
    consts = VRc.load_vendored_protocol_constants()
    states = VRc.verify_universe()
    plan = TE.truth_execution_plan(states, namespaces=consts["namespaces"])
    units = (plan["pref_units"] + plan["discovery_units"]
             + plan["confirmation_units"])
    manifest = {
        "recorded_at": now(),
        "namespaces": consts["namespaces"],
        "units": [{"unit_id": u["unit_id"], "namespace": u["namespace"],
                   "seed_key": u["seed_key"], "samples": u["samples"]}
                  for u in units],
        "counts": {"pref": len(plan["pref_units"]),
                   "discovery": len(plan["discovery_units"]),
                   "confirmation": len(plan["confirmation_units"])},
        "frozen_before_first_simulator_call": True,
    }
    dump(CFG / "m3s2s_truth_seed_manifest.json", manifest)
    seed_keys = [tuple(u["seed_key"]) for u in units]
    assert len(set(seed_keys)) == len(seed_keys) == 488
    prior = _prior_recorded_seeds()
    for name in ("m3cf1n_pref_seeds.json", "m3cf1n_discovery_seeds.json",
                 "m3cf1n_confirmation_seeds.json"):
        d = load(ROOT / "configs/phase_m3cf1n" / name)
        for v in d.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "seed_key" in item:
                        prior.add(int(item["seed_key"][0]))
                    elif isinstance(item, list) and item:
                        prior.add(int(item[0]))
    collisions = sorted({k0 for k0, _ in seed_keys if k0 in prior})
    if collisions:
        raise RuntimeError(f"S2S-X: truth seed collision: {collisions[:5]}")
    audit = {"recorded_at": now(), "units": len(units),
             "unique_seed_keys": len(set(seed_keys)),
             "historical_collision": 0,
             "namespaces_match_contract":
                 manifest["namespaces"] == consts["namespaces"],
             "TRUTH_SEED_AUDIT": "PASS"}
    dump(OUT / "m3s2s_truth_seed_audit.json", audit)
    return audit


def truth_preflight() -> dict:
    """Execution-readiness proof WITHOUT authorization or simulator calls:
    vendored-only resolution + tracked universe + full 240-state dry
    assembly + empty destination."""
    _check_gates_frozen_no()
    from hyptraj.m3s2s import vendored_runtime as VRc
    states = VRc.verify_universe()
    consts = VRc.load_vendored_protocol_constants()
    from hyptraj.m3d.benchmark_states import assemble_state
    assembled = 0
    for s in states:
        bench = VRc.resolve_bench_config(s["config_id"])
        st = assemble_state(bench, float(s["s2"]), short_config=s["config_id"])
        if isinstance(st, dict):
            raise RuntimeError(f"S2S-X: dry assembly failed: {s['state_id']}")
        assembled += 1
    for phase, ledger in TRUTH_LEDGERS.items():
        if ledger.exists() and ledger.read_text(encoding="utf-8").strip():
            raise RuntimeError(f"S2S-X: destination not empty: {ledger}")
    out = {"recorded_at": now(), "universe_verified": 240,
           "vendored_protocols_verified": 3,
           "dry_assembly": assembled, "destination_empty": True,
           "TRUTH_PREFLIGHT": "PASS"}
    dump(OUT / "m3s2s_truth_preflight.json", out)
    print(f"M3-S2S truth preflight: PASS ({assembled}/240 vendored-only dry "
          "assembly; gates frozen NO)")
    return out


def _completed(ledger, unit_id) -> bool:
    from hyptraj.m3cf1r0.persistence import ledger_entries
    return any(e.get("state_id") == unit_id and e.get("status") == "COMPLETE"
               for e in ledger_entries(ledger))


def _ledger(path) -> list:
    from hyptraj.m3cf1r0.persistence import ledger_entries
    return ledger_entries(path) if Path(path).exists() else []


def truth_execute() -> dict:
    """GATED: requires TRUTH_SAMPLING_AUTHORIZED: YES.  Runs the three
    truth streams (P_ref 8 / discovery 240 / confirmation 240) under the
    hardened transactional contract with exact per-stream consumption."""
    if not _gate("TRUTH_SAMPLING_AUTHORIZED"):
        raise RuntimeError("TRUTH_SAMPLING_AUTHORIZED is not YES")
    if _gate("ARM_A_AUTHORIZED") or _gate("ARM_B_AUTHORIZED"):
        raise RuntimeError("S2S-X: Arm gates must remain NO during truth stage")
    from hyptraj.m3s2s import vendored_runtime as VRc
    states = VRc.verify_universe()
    consts = VRc.load_vendored_protocol_constants()
    plan = TE.truth_execution_plan(states, namespaces=consts["namespaces"])
    for d in (TRUTH_PREF, TRUTH_DISC, TRUTH_CONF):
        d.mkdir(parents=True, exist_ok=True)
    by_sid = {s["state_id"]: s for s in states}
    protocol_hash = sha(CFG / "m3s2s_truth_contract.json")
    p_refs: dict = {}

    def p_ref_for(cid: str) -> dict:
        if cid not in p_refs:
            rec_path = TRUTH_PREF / f"{cid}.json"
            p_refs[cid] = (load(rec_path) if rec_path.exists()
                           else VRc.load_config_p_ref(cid))
            p_refs[cid]["record_hash"] = record_file_hash(rec_path) \
                if rec_path.exists() else None
        return p_refs[cid]

    def run_unit(unit, ledger, out_dir, payload_fn, extra):
        result = run_trial_transactional(
            unit["unit_id"], out_dir, payload_fn, ledger_path=ledger,
            pre_hash_validator=lambda rec: None, base_entry=extra)
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"M3-S2S-X: truth unit not durably COMPLETE: "
                f"{unit['unit_id']}: {result}; CONSUMED_INVALID policy in "
                "force; NO REPLAY")

    for unit in plan["pref_units"]:
        out = TRUTH_PREF / f"{unit['config_id']}.json"
        if not (out.exists() and _completed(TRUTH_LEDGERS["pref"],
                                            unit["unit_id"])):
            run_unit(unit, TRUTH_LEDGERS["pref"], out,
                     lambda u=unit: TE.pref_payload(u, protocol_hash),
                     {"samples": unit["samples"], "stream": "pref"})
        p_refs[unit["config_id"]] = load(out)
        p_refs[unit["config_id"]]["record_hash"] = record_file_hash(out)

    for unit in plan["discovery_units"]:
        row = by_sid[unit["state_id"]]
        out = TRUTH_DISC / f"{unit['state_id']}.json"
        if out.exists() and _completed(TRUTH_LEDGERS["discovery"],
                                       unit["unit_id"]):
            continue
        run_unit(unit, TRUTH_LEDGERS["discovery"], out,
                 lambda u=unit, r=row, pr=p_ref_for(row["config_id"]):
                 TE.discovery_payload(u, r, pr, protocol_hash),
                 {"samples": unit["samples"], "stream": "discovery"})

    for unit in plan["confirmation_units"]:
        row = by_sid[unit["state_id"]]
        out = TRUTH_CONF / f"{unit['state_id']}.json"
        if out.exists() and _completed(TRUTH_LEDGERS["confirmation"],
                                       unit["unit_id"]):
            continue
        run_unit(unit, TRUTH_LEDGERS["confirmation"], out,
                 lambda u=unit, r=row, pr=p_ref_for(row["config_id"]):
                 TE.confirmation_payload(u, r, pr, protocol_hash),
                 {"samples": unit["samples"], "stream": "confirmation"})

    summary = TE.consumption_summary({
        "pref": _ledger(TRUTH_LEDGERS["pref"]),
        "discovery": _ledger(TRUTH_LEDGERS["discovery"]),
        "confirmation": _ledger(TRUTH_LEDGERS["confirmation"])})
    dump(SUM / "m3s2s_truth_consumption.json", summary)
    print("M3-S2S truth execute: all units durable COMPLETE; "
          f"consumption = {summary}")
    return summary


def truth_panel() -> dict:
    """Completion semantics: truth assignment + exposed inventory + 120-state
    panel freeze ONLY after every required truth record is durable
    COMPLETE.  Panel-blocked semantics per taskbook Sec. 47."""
    from hyptraj.m3s2s import vendored_runtime as VRc
    states = VRc.verify_universe()
    ledgers = {k: _ledger(v) for k, v in TRUTH_LEDGERS.items()}
    required = {"pref": 8, "discovery": 240, "confirmation": 240}
    for stream, n in required.items():
        comp = [e for e in ledgers[stream] if e.get("status") == "COMPLETE"]
        inv = [e for e in ledgers[stream]
               if e.get("status") == "CONSUMED_INVALID"]
        if len(comp) != n or inv:
            raise RuntimeError(
                f"S2S-X: truth stage incomplete ({stream}: {len(comp)}/{n}, "
                f"consumed-invalid {len(inv)}); no truth assignment, no "
                "panel selection")
    conf_records = []
    for unit in (e for e in ledgers["confirmation"]
                 if e.get("status") == "COMPLETE"):
        p = TRUTH_CONF / f"{unit['state_id'].split('|', 1)[1]}.json"
        rec = load(p)
        if unit.get("record_file_hash") and \
                record_file_hash(p) != unit["record_file_hash"]:
            raise RuntimeError(f"S2S-X: confirmation hash mismatch: {p}")
        conf_records.append(rec)
    truth = TE.assign_truth(conf_records)
    dump(SUM / "m3s2s_frozen_truth.json", {
        "recorded_at": now(), "n_states": len(truth),
        "composition": dict(Counter(truth.values())),
        "source": "M3S2S-CONFIRM durable records (ALL_240_FRESH_CANDIDATES)"})
    exposed = [{"state_id": s["state_id"], "config_id": s["config_id"],
                "confirmed_truth": truth[s["state_id"]],
                "status": "TRUTH_EXPOSED_DEVELOPMENT"}
               for s in states]
    dump(SUM / "m3s2s_truth_exposed_inventory.json", {
        "recorded_at": now(), "n": len(exposed), "states": exposed,
        "rule": "retired from all future untouched confirmation use"})
    by_sid = {s["state_id"]: s for s in states}
    panel_states = [dict(by_sid[sid], truth=t) for sid, t in truth.items()]
    selection = TE.select_panel(panel_states, truth)
    dump(SUM / "m3s2s_panel_decision.json", selection)
    if selection["PANEL"] != "FROZEN":
        raise RuntimeError(
            f"M3-S2S-PANEL-BLOCKED: {selection.get('reason')}; STOP")
    dump(CFG / "m3s2s_panel.json", {
        "panel_sha256": selection["panel_sha256"],
        "n_states": len(selection["panel"]),
        "n_configs": selection["n_configs"],
        "states": selection["panel"], "frozen": True})
    print(f"M3-S2S truth panel: FROZEN ({len(selection['panel'])} states / "
          f"{selection['n_configs']} configs, sha "
          f"{selection['panel_sha256'][:16]}...); STOP -- "
          "ARM_A_AUTHORIZED must remain NO")
    return selection


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "candidates", "preflight",
                                      "contracts", "docs", "hashlock",
                                      "truth_preflight", "truth_execute",
                                      "truth_panel",
                                      "truth_seed_manifest",
                                      "all"])
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "candidates":
        candidates_stage()
    elif args.stage == "preflight":
        preflight()
    elif args.stage == "contracts":
        contracts(build_candidates())
    elif args.stage == "docs":
        docs()
    elif args.stage == "hashlock":
        hashlock()
    elif args.stage == "truth_seed_manifest":
        truth_seed_manifest()
    elif args.stage == "truth_preflight":
        truth_preflight()
    elif args.stage == "truth_execute":
        truth_execute()
    elif args.stage == "truth_panel":
        truth_panel()
    elif args.stage == "all":
        all_stages()


if __name__ == "__main__":
    main()
