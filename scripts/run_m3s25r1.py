"""M3-S25-R1 -- Support-Completion Replacement Development Stage (first run).

FIRST ROUND = PREREGISTRATION FREEZE ONLY (taskbook Sec. 33):
    scientific simulator calls = 0, scientific samples = 0.

Stages: prepare | candidates | p_ref_registry | truth_seed_manifest |
        budget | preflight | contracts | docs | hashlock |
        truth_execute | truth_panel | all

Three independent NEW authorization gates, all initially NO (taskbook
Sec. 3/21/29); the sealed parent's M3-S2S T1 gate may NOT be reused:
    M3_S25_R1_TRUTH_AUTHORIZED / M3_S25_R1_ARM_A_AUTHORIZED /
    M3_S25_R1_ARM_B_AUTHORIZED.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

from hyptraj.m3s25r1 import arm_a as AA  # noqa: E402
from hyptraj.m3s25r1 import arm_a_eval as AE  # noqa: E402
from hyptraj.m3s25r1 import candidates as CAND  # noqa: E402
from hyptraj.m3s25r1 import history as HIST  # noqa: E402
from hyptraj.m3s25r1 import runtime as RT  # noqa: E402
from hyptraj.m3s2s import vendored_runtime as VR  # noqa: E402 (parent pins)
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    bounded_slug, bounded_temp_basename, record_file_hash,
    run_trial_transactional)
from hyptraj.m3cf1r0.persistence import ledger_entries  # noqa: E402

OUT = ROOT / "results/phase_m3s25r1/preflight"
SUM = ROOT / "results/phase_m3s25r1/summary"
TRIALS = ROOT / "results/phase_m3s25r1/trials"
CFG = ROOT / "configs/phase_m3s25r1"
DOC = ROOT / "docs/phase_m3s25r1"

PARENT_HEAD = "f0d73702dc284f9a2ce1f1a205bb5f56f1324d38"
PARENT_STAGE = "M3-S2S"
PARENT_TERMINAL = "M3-S2S-PANEL-BLOCKED"
PARENT_TRUTH_BUDGET = 436_000_000
PARENT_UNIVERSE = ROOT / "configs/phase_m3s2s/m3s2s_candidate_universe.json"
PARENT_REGISTRY = ROOT / "configs/phase_m3s2s/m3s2s_new_config_registry.json"
PARENT_APPROVAL_DOC = ROOT / "docs/phase_m3s2s/M3_S2S_Human_Approval.md"
PARENT_TRUTH_CONTRACT = ROOT / "configs/phase_m3s2s/m3s2s_truth_contract.json"
PARENT_TRUTH_CONSUMPTION = ROOT / ("results/phase_m3s2s/summary/"
                                   "m3s2s_truth_consumption.json")
PARENT_INVENTORY = ROOT / ("results/phase_m3s2s/summary/"
                           "m3s2s_truth_exposed_inventory.json")
PARENT_PANEL_DECISION = ROOT / ("results/phase_m3s2s/summary/"
                                "m3s2s_panel_decision.json")
PARENT_PREF = ROOT / "results/phase_m3s2s/pref"
PARENT_LEDGERS = {
    "pref": ROOT / "results/phase_m3s2s/pref/pref_ledger.jsonl",
    "discovery": ROOT / "results/phase_m3s2s/discovery/discovery_ledger.jsonl",
    "confirmation": ROOT / ("results/phase_m3s2s/confirmation/"
                            "confirmation_ledger.jsonl")}
VENDORED = ROOT / "configs/phase_m3s2s/reference_truth_protocol"

UNIVERSE = CFG / "m3s25r1_candidate_universe.json"
PREFLIGHT_REPORT = OUT / "m3s25r1_preflight.json"
APPROVAL_DOC = DOC / "M3_S25_R1_Human_Approval.md"

N_CONFIGS = 30
N_STRATA = 8
N_STATES = 240
N_UNITS = 480
SPAN_MIN = 0.70
# frozen after the one deterministic generation (LF bytes; .gitattributes
# pins the artifact as -text so working tree == git blob)
EXPECTED_UNIVERSE_SHA = ("9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4"
                         "223058d6e600d02")
EXPECTED_CONTRACT_SHA = ("96585379805a2cc5f390f37b35633571"
                         "23de497c2df05b58eb5f6efe166fab98")
FULL_PATH_LIMIT = 220

TRUTH_DISC = ROOT / "results/phase_m3s25r1/discovery"
TRUTH_CONF = ROOT / "results/phase_m3s25r1/confirmation"
TRUTH_LEDGERS = {"discovery": TRUTH_DISC / "discovery_ledger.jsonl",
                 "confirmation": TRUTH_CONF / "confirmation_ledger.jsonl"}

# ---- M3-S25-R1-A0: Arm-A rebind & execution readiness (zero sampling) ----
ARM_A_DIR = ROOT / "results/phase_m3s25r1/arm_a"
ARM_A_TRIALS = ARM_A_DIR / "trials"
ARM_A_LEDGER = ARM_A_DIR / "trial_ledger.jsonl"
ARM_A_EVAL = SUM / "m3s25r1_arm_a_evaluation.json"
PANEL_TRUTH_MANIFEST = CFG / "m3s25r1_panel_truth_manifest.json"
ARM_A_CONTRACT = CFG / "m3s25r1_arm_a_contract.json"
ARM_A_SEED_MANIFEST = CFG / "m3s25r1_arm_a_seed_manifest.json"
TRUTH_TERMINAL_HEAD = "089c6a48c73831fbd95e2caa5b21137b485080aa"
OLD_ARM_A_TERMINAL_HEAD = "73e91823fc562a8b5be65a86fa6f1e2a01803d42"
PANEL_TRUTH_MANIFEST_PIN = ("75f5993bc6a251220e5e533f0b96de15"
                         "3bcef313d95706e6e0b7294db57af880")
ARM_A_CONTRACT_PIN = ("f02fc399834e5d950d46f29d8e609f1b"
                         "8df3697097a705db6de8d5474c6085d6")
ARM_A_SEED_MANIFEST_PIN = ("20cbe999286df7c4664a53067a1796b7"
                         "b1ce9da37eb5c42939e07a456b8bf30d")
PANEL_JSON = CFG / "m3s25r1_panel.json"
EXPECTED_PANEL_FILE_SHA = ("136830a2bdd5291882564e6bba922161"
                           "ae519139573921161c50f7dfa20950ff")
PARENT_CONTRACTS = (
    "m3s2s_gradient_protocol.json", "m3s2s_instrumentation_contract.json",
    "m3s2s_feature_contract.json", "m3s2s_model_contract.json",
    "m3s2s_threshold_contract.json", "m3s2s_persistence_contract.json",
    "m3s2s_arm_b_contract.json", "m3s2s_verdict_contract.json",
    "m3s2s_panel_contract.json")

# ---- M3-S25-R1-A1R0: replacement Arm-A preregistration (zero sampling) ----
A1R_NAMESPACE = "M3-S25-R1-A1R-GRAD"
A1R_DIR = ROOT / "results/phase_m3s25r1/arm_a1r"
A1R_TRIALS = A1R_DIR / "trials"
A1R_LEDGER = A1R_DIR / "trial_ledger.jsonl"
A1R_EVAL = SUM / "m3s25r1_a1r_evaluation.json"
A1R_RETIRED = CFG / "m3s25r1_a1r_retired_stream.json"
A1R_CONTRACT = CFG / "m3s25r1_a1r_contract.json"
A1R_SEED_MANIFEST = CFG / "m3s25r1_a1r_seed_manifest.json"
A1R_RETIRED_PIN = ("7e673af48d3547fd2dedbd4a9fe882d7"
                           "1c1598fb8f55bef52e6e1b4695f9ab41")
A1R_CONTRACT_PIN = ("fdf0c42d4922890a6c17b004278253ec"
                           "4a4797e76373ece6292c7512b2863985")
A1R_SEED_MANIFEST_PIN = ("067062d89f76486aacb6dfd892d0f77f"
                           "ae9729c1063a201388ceea892c336b6e")

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_lf_bytes(p, data: bytes) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_bytes(data)


def dump_json(p, v) -> bytes:
    """LF-normalized canonical JSON artifact; returns the exact bytes."""
    data = (json.dumps(v, indent=2, sort_keys=True,
                       ensure_ascii=True) + "\n").encode("utf-8")
    write_lf_bytes(p, data)
    return data


def dump(p, v) -> None:
    dump_json(p, v)


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_text_lf(p, text: str) -> None:
    write_lf_bytes(p, text.encode("utf-8"))


def csvread(p) -> list[dict]:
    with open(p, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def csvwrite(p, rows: list[dict], fieldnames: list[str]) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    write_lf_bytes(p, buf.getvalue().encode("utf-8"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def _gate_file(name: str, path: Path) -> bool:
    txt = Path(path).read_text(encoding="utf-8")
    m = re.search(rf"^{name}:\s*(\w+)\s*$", txt, re.M)
    return bool(m and m.group(1).strip().upper() == "YES")


def gate(name: str) -> bool:
    return _gate_file(name, APPROVAL_DOC)


def parent_gate(name: str) -> bool:
    return _gate_file(name, PARENT_APPROVAL_DOC)


def _windows() -> dict[str, dict]:
    """Inherited legality windows -- computed by the PARENT's own frozen
    code (byte-identical legality calculation; taskbook Sec. 5)."""
    import run_m3s2s as S2S
    return S2S._config_windows()


def _config_meta(windows: dict[str, dict]) -> dict[str, dict]:
    """Frozen per-config identity from the PARENT candidate universe."""
    u = load(PARENT_UNIVERSE)
    meta = {}
    for s in u["states"]:
        meta.setdefault(s["config_id"], {
            "origin": s["config_origin"],
            "config_source_path": s["config_source_path"],
            "config_source_sha256": s["config_source_sha256"]})
    missing = [c for c in windows if c not in meta]
    if missing:
        raise RuntimeError(f"M3-S25-R1-X: configs absent from parent "
                           f"universe: {missing}")
    return meta


def verify_parent_universe_pin() -> dict:
    got = sha_bytes(PARENT_UNIVERSE.read_bytes())
    expected = VR.EXPECTED_UNIVERSE_SHA
    if got != expected:
        raise RuntimeError(
            f"M3-S25-R1-X: parent candidate-universe sha drift: {got} != {expected}")
    reg_got = sha_bytes(PARENT_REGISTRY.read_bytes())
    reg_expected = VR.EXPECTED_NEW_CONFIG_REGISTRY_SHA
    if reg_got != reg_expected:
        raise RuntimeError(
            f"M3-S25-R1-X: parent new-config registry sha drift: "
            f"{reg_got} != {reg_expected}")
    return {"parent_universe_sha256": got,
            "parent_new_config_registry_sha256": reg_got}


# --------------------------------------------------------------------------
# stage: prepare (parent closure audit + parent development registry +
# reserve firewall)
# --------------------------------------------------------------------------

def parent_audit() -> dict:
    head = git_commit()
    if subprocess.run(["git", "merge-base", "--is-ancestor", PARENT_HEAD, head],
                      cwd=ROOT, capture_output=True).returncode != 0:
        raise RuntimeError(
            f"M3-S25-R1-X: parent frozen HEAD {PARENT_HEAD[:7]} is not an "
            "ancestor of the R1 HEAD")
    decision = load(PARENT_PANEL_DECISION)
    if decision.get("PANEL") != PARENT_TERMINAL:
        raise RuntimeError(
            f"M3-S25-R1-X: parent terminal verdict drift: {decision.get('PANEL')}")
    cons = load(PARENT_TRUTH_CONSUMPTION)
    if cons["total"]["actual"] != PARENT_TRUTH_BUDGET or \
            cons["total"]["planned"] != PARENT_TRUTH_BUDGET or \
            cons["total"].get("topup", 1) != 0:
        raise RuntimeError("M3-S25-R1-X: parent truth budget accounting drift")
    closed = {}
    for g in ("TRUTH_SAMPLING_AUTHORIZED", "ARM_A_AUTHORIZED",
              "ARM_B_AUTHORIZED"):
        closed[g] = (not parent_gate(g))
    if not all(closed.values()):
        raise RuntimeError(
            f"M3-S25-R1-X: parent M3-S2S gates are not closed: {closed}; "
            "close the old T1 gate (closure-only) before R1")
    units = {}
    for stream, ledger in PARENT_LEDGERS.items():
        entries = ledger_entries(ledger) if Path(ledger).exists() else []
        comp = sum(1 for e in entries if e.get("status") == "COMPLETE")
        inv = sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID")
        units[stream] = {"COMPLETE": comp, "CONSUMED_INVALID": inv}
    total_complete = sum(v["COMPLETE"] for v in units.values())
    total_invalid = sum(v["CONSUMED_INVALID"] for v in units.values())
    if total_complete != 488 or total_invalid != 0:
        raise RuntimeError(
            f"M3-S25-R1-X: parent ledger state drift: {total_complete} "
            f"COMPLETE / {total_invalid} CONSUMED_INVALID (expected 488 / 0)")
    inv = load(PARENT_INVENTORY)
    if len(inv.get("states", [])) != N_STATES:
        raise RuntimeError("M3-S25-R1-X: parent inventory drift")
    audit = {
        "recorded_at": now(), "head": head,
        "parent_stage": PARENT_STAGE,
        "parent_terminal": PARENT_TERMINAL,
        "parent_frozen_head": PARENT_HEAD,
        "parent_head_is_ancestor": True,
        "parent_truth_budget_consumed": PARENT_TRUTH_BUDGET,
        "parent_truth_budget": f"{PARENT_TRUTH_BUDGET:,} / {PARENT_TRUTH_BUDGET:,}",
        "parent_gates": {k: ("CLOSED" if v else "OPEN") for k, v in closed.items()},
        "parent_ledgers": units,
        "parent_truth_exposed_states": len(inv["states"]),
        "closure_record": "docs/phase_m3s2s/M3_S2S_Closure_Record.md",
        "PARENT_CLOSURE_AUDIT": "PASS"}
    dump(OUT / "m3s25r1_parent_audit.json", audit)
    return audit


def parent_registry(windows: dict[str, dict]) -> dict:
    """All 240 parent truth-exposed states enter the R1 parent development
    registry (taskbook Sec. 2): state_id, config_id, s2, u, frozen truth,
    truth source + source hashes, exposure status.  Nothing is deleted,
    replaced or repackaged."""
    u = load(PARENT_UNIVERSE)
    inv = load(PARENT_INVENTORY)
    truth_by_sid = {s["state_id"]: s["confirmed_truth"] for s in inv["states"]}
    conf_ledger = [e for e in ledger_entries(PARENT_LEDGERS["confirmation"])
                   if e.get("status") == "COMPLETE"]
    conf_hash = {e["state_id"].split("|", 1)[1]: e.get("record_file_hash")
                 for e in conf_ledger}
    entries = []
    for s in sorted(u["states"], key=lambda x: (x["config_id"], x["s2"])):
        sid = s["state_id"]
        if sid not in truth_by_sid:
            raise RuntimeError(f"M3-S25-R1-X: parent state missing truth: {sid}")
        entries.append({
            "state_id": sid, "config_id": s["config_id"], "s2": s["s2"],
            "u": CAND.u_of(s["s2"], windows[s["config_id"]]["s2_lo"]),
            "confirmed_truth": truth_by_sid[sid],
            "source_stage": PARENT_STAGE,
            "truth_record_path":
                f"results/phase_m3s2s/confirmation/{sid}.json",
            "truth_record_file_hash": conf_hash.get(sid),
            "parent_candidate_rank": s["rank"],
            "development_eligible": True,
            "untouched_confirmation_eligible": False,
            "exposure_status": "TRUTH_EXPOSED_DEVELOPMENT"})
    reg = {"schema_version": "m3s25r1_parent_development_registry_v1",
           "parent_stage": PARENT_STAGE,
           "parent_terminal": PARENT_TERMINAL,
           "n_states": len(entries),
           "rule": "development-only union member; retired from all future "
                   "untouched confirmation use; preserved verbatim",
           "states": entries}
    dump(CFG / "m3s25r1_parent_development_registry.json", reg)
    return reg


def _window_lo(w: dict) -> float:
    return w["s2_lo"]


def reserve_firewall() -> list[dict]:
    reserve = csvread(ROOT / "results/phase_m3pi1vnr/summary/"
                             "m3pi1vnr_remaining_protected_reserve.csv")
    s1c_panel = load(ROOT / "configs/phase_m3s1c/m3s1c_panel.json")
    consumed = {s["state_id"] for s in s1c_panel["states"]}
    reserve = [r for r in reserve if r["state_id"] not in consumed]
    if len(reserve) != 18:
        raise RuntimeError(
            f"M3-S25-R1-X: expected 18 protected states, got {len(reserve)}")
    manifest_sha = sha(ROOT / "results/phase_m3pi1vnr/summary/"
                              "m3pi1vnr_remaining_protected_reserve.csv")
    rows = [{"state_id": r["state_id"], "config_id": r["config_id"],
             "protected": "true", "source_hash": manifest_sha} for r in reserve]
    csvwrite(OUT / "m3s25r1_protected_reserve_18.csv", rows,
             ["state_id", "config_id", "protected", "source_hash"])
    dump(OUT / "m3s25r1_reserve_firewall.json", {
        "recorded_at": now(), "remaining": 18, "used_by_r1": 0,
        "permanent": True,
        "rule": "protected reserve / untouched confirmation / final "
                "validation states are FORBIDDEN to R1 (taskbook Sec. 30)",
        "RESERVE_FIREWALL": "PASS"})
    return reserve


def prepare() -> dict:
    audit = parent_audit()
    windows = _windows()
    reg = parent_registry(windows)
    reserve_firewall()
    print(f"M3-S25-R1 prepare: parent closure PASS ({PARENT_TERMINAL}); "
          f"{reg['n_states']} parent states registered; 18 reserve protected")
    return {"audit": audit, "parent_registry": reg, "windows": windows}


# --------------------------------------------------------------------------
# stage: candidates (support-completion universe; NO truth labels)
# --------------------------------------------------------------------------

def candidates_stage() -> dict:
    # M3-S25-R1.1 Sec. 2/6: the candidate universe is FROZEN and its SHA is
    # immutable -- regeneration (re-hash / re-draw / substitution) is
    # forbidden once it exists.
    if UNIVERSE.exists():
        raise RuntimeError(
            "M3-S25-R1-X: candidate universe already frozen at "
            f"{UNIVERSE} (sha {sha_bytes(UNIVERSE.read_bytes())[:16]}...); "
            "regeneration is forbidden by the M3-S25-R1.1 amendment "
            "(Sec. 2/6: no re-hash, no re-draw, no substitution)")
    pins = verify_parent_universe_pin()
    windows = _windows()
    # cross-check inherited windows against the parent universe's recorded
    # legality margins (byte-identical legality calculation regression)
    u = load(PARENT_UNIVERSE)
    drift = []
    for s in u["states"]:
        w = windows[s["config_id"]]
        expect = w["s2_min_legality"] * s["s2"] / 0.5
        if abs(expect - s["legality_margin_min_eig"]) > 1e-9:
            drift.append(s["state_id"])
    if drift:
        raise RuntimeError(
            f"M3-S25-R1-X: legality-window drift vs parent universe: "
            f"{drift[:5]}")
    meta = _config_meta(windows)
    configs = sorted(windows)
    hist, hist_meta = HIST.historical_characterized_s2(configs)
    states = CAND.build_states(windows, hist, meta)
    audit = CAND.invariant_audit(states)
    fresh = CAND.freshness_reaudit(states, hist)
    universe = {
        "schema_version": "m3s25r1_candidate_universe_v1",
        "n_states": len(states),
        "n_configs": len(configs),
        "n_strata": N_STRATA,
        "anchors_per_stratum": CAND.L_ANCHORS,
        "support_interval": [CAND.U_LO, CAND.U_HI],
        "strata_boundaries": [list(CAND.stratum_bounds(i))
                              for i in range(N_STRATA + 1)],
        "rank_seed": CAND.PANEL_RANK_SEED,
        "anchor_salt": CAND.ANCHOR_SALT,
        "canonical_s2_rule": "repr(float(s2)): shortest round-trip decimal, "
                             "identical to the JSON serialization of the "
                             "value in this artifact",
        "freshness_rule": "first legal+fresh anchor in SHA256 anchor-hash "
                          "ascending order per config x stratum; collision "
                          "|s2-s2_h| <= 1e-6*max(1,|s2_h|) against every "
                          "historically characterized s2 of the same config "
                          "(M3-CF*/M3-WCF*/M3-PI*/M3-S1*/M3-S2S and all "
                          "retired/truth-exposed/development artifacts)",
        "selection_independence": ["truth labels", "discovery results",
                                   "SHRINK/HOLD counts",
                                   "candidate numeric ordering"],
        "parent_reference": {
            "parent_stage": PARENT_STAGE,
            "parent_terminal": PARENT_TERMINAL,
            "parent_frozen_head": PARENT_HEAD,
            "parent_candidate_universe_sha256":
                pins["parent_universe_sha256"],
            "parent_new_config_registry_sha256":
                pins["parent_new_config_registry_sha256"]},
        "historical_sweep": {
            "rule": "content-classified characterized-artifact sweep "
                    "(truth/reference/discovery/confirmation/panel/reserve/"
                    "state-table/universe/inventory); proposal artifacts "
                    "(pools/banks/selection views/plans) are not "
                    "characterized; parent stage M3-S2S included via its "
                    "tracked universe",
            "per_config_counts": hist_meta["per_config_counts"],
            "minimum_families": hist_meta["minimum_families"],
            "n_sources": len(hist_meta["sources"])},
        "freshness_audit": fresh,
        "support_invariant_audit": {
            "invariant_failures": audit["invariant_failures"],
            "checks": audit["checks"]},
        "states": states,
    }
    data = dump_json(UNIVERSE, universe)
    universe_sha = sha_bytes(data)
    dump(OUT / "m3s25r1_candidate_universe_hash.json", {
        "recorded_at": now(), "candidate_universe_sha256": universe_sha,
        "parent_universe_sha256": pins["parent_universe_sha256"]})
    dump(OUT / "m3s25r1_freshness_sources.json", {
        "recorded_at": now(), "n_sources": len(hist_meta["sources"]),
        "sources": hist_meta["sources"]})
    csvwrite(OUT / "m3s25r1_freshness_audit.csv",
             [{"state_id": s["state_id"], "config_id": s["config_id"],
               "stratum_id": s["stratum_id"], "u": s["u"], "s2": s["s2"],
               "anchor_m": s["anchor_m"],
               "anchor_rank_position": s["anchor_rank_position"],
               "n_collided": s["n_collided"], "n_fresh": s["n_fresh"],
               "anchor_hash": s["anchor_hash"], "fresh": "true"}
              for s in states],
             ["state_id", "config_id", "stratum_id", "u", "s2", "anchor_m",
              "anchor_rank_position", "n_collided", "n_fresh",
              "anchor_hash", "fresh"])
    n_bad = len(audit["invariant_failures"])
    print(f"M3-S25-R1 candidates: {len(states)} states / {len(configs)} "
          f"configs / 8 strata each (universe sha256 {universe_sha[:16]}...); "
          f"support invariants A-D: {30 - n_bad}/30 configs pass")
    return {"states": states, "windows": windows, "hist": hist,
            "hist_meta": hist_meta, "audit": audit, "fresh": fresh,
            "universe_sha256": universe_sha, "pins": pins}


# --------------------------------------------------------------------------
# stage: P_ref registry (Sec. 11: reuse only; budget = 0)
# --------------------------------------------------------------------------

def p_ref_registry_stage() -> dict:
    u = load(UNIVERSE)
    configs = sorted({s["config_id"] for s in u["states"]})
    pref_protocol_sha = sha(VENDORED / "m3cf1n_pref_protocol.json")
    parent_pref_ledger = ledger_entries(PARENT_LEDGERS["pref"])
    entries = []
    for cid in configs:
        if cid.startswith("m3s2s_cfg_"):
            src = PARENT_PREF / f"{cid}.json"
            if not src.exists():
                raise RuntimeError(
                    f"M3-S25-R1-X: durable parent PREF record missing: {src}")
            comp = [e for e in parent_pref_ledger
                    if e.get("state_id") == f"PREF|{cid}"
                    and e.get("status") == "COMPLETE"]
            started = [e for e in parent_pref_ledger
                       if e.get("state_id") == f"PREF|{cid}"
                       and e.get("status") == "STARTED"]
            invalid = [e for e in parent_pref_ledger
                       if e.get("state_id") == f"PREF|{cid}"
                       and e.get("status") == "CONSUMED_INVALID"]
            if invalid or len(comp) != 1 or len(started) != 1:
                raise RuntimeError(
                    f"M3-S25-R1-X: parent PREF ledger not a single durable "
                    f"COMPLETE for {cid}")
            file_hash = sha(src)
            if comp[0].get("record_file_hash") != file_hash:
                raise RuntimeError(
                    f"M3-S25-R1-X: parent PREF record hash mismatch: {cid}")
            rec = load(src)
            entry = {"config_id": cid, "source_stage": PARENT_STAGE,
                     "source_file": src.relative_to(ROOT).as_posix(),
                     "record_file_hash": file_hash,
                     "protocol_hash": pref_protocol_sha,
                     "record_protocol_hash": rec.get("protocol_hash"),
                     "sample_count": int(rec["sample_count"]),
                     "n_batches": int(rec["n_batches"]),
                     "p_ref": float(rec["p_ref_full"]),
                     "p_ref_full_SE": float(rec["p_ref_full_SE"]),
                     "p_ref_full_CI": [float(x) for x in rec["p_ref_full_CI"]],
                     "namespace": rec["namespace"],
                     "record_type": rec["record_type"],
                     "durable_complete_verified": True}
        elif cid.startswith("cf1n_new_"):
            src = VENDORED / "pref_records" / f"{cid}.json"
            rec = load(src)
            entry = {"config_id": cid, "source_stage": "M3-CF1N",
                     "source_file": src.relative_to(ROOT).as_posix(),
                     "record_file_hash": sha(src),
                     "protocol_hash": pref_protocol_sha,
                     "record_protocol_hash": rec.get("protocol_hash"),
                     "sample_count": int(rec["sample_count"]),
                     "n_batches": int(rec["n_batches"]),
                     "p_ref": float(rec["p_ref_full"]),
                     "p_ref_full_SE": float(rec["p_ref_full_SE"]),
                     "p_ref_full_CI": [float(x) for x in rec["p_ref_full_CI"]],
                     "namespace": rec["namespace"],
                     "record_type": rec.get("record_type",
                                            rec["namespace"]),
                     "durable_complete_verified": True}
        elif cid.startswith("wcf1_new_"):
            src = VENDORED / "pref_records" / f"{cid}.json"
            rec = load(src)
            entry = {"config_id": cid, "source_stage": "M3-WCF1",
                     "source_file": src.relative_to(ROOT).as_posix(),
                     "record_file_hash": sha(src),
                     "protocol_hash": pref_protocol_sha,
                     "record_protocol_hash": rec.get("protocol_hash"),
                     "sample_count": int(rec["sample_count"]),
                     "n_batches": int(rec["n_batches"]),
                     "p_ref": float(rec["p_ref_full"]),
                     "p_ref_full_SE": float(rec["p_ref_full_SE"]),
                     "p_ref_full_CI": [float(x) for x in rec["p_ref_full_CI"]],
                     "namespace": rec["namespace"],
                     "record_type": rec.get("record_type",
                                            rec["namespace"]),
                     "durable_complete_verified": True}
        else:
            src = VENDORED / "pref_records" / "m3d2_probability_reference.json"
            refs = load(src)
            recs = refs["records"] if isinstance(refs, dict) and "records" in refs \
                else refs
            matches = [r for r in recs
                       if str(r.get("config_id", "")).endswith(cid)]
            if len(matches) != 1:
                raise RuntimeError(
                    f"M3-S25-R1-X: legacy P_ref not uniquely resolvable "
                    f"for {cid}")
            rec = matches[0]
            entry = {"config_id": cid, "source_stage": "M3-D2",
                     "source_file": src.relative_to(ROOT).as_posix(),
                     "record_file_hash": sha(src),
                     "protocol_hash": pref_protocol_sha,
                     "record_protocol_hash": rec.get("protocol_hash"),
                     "sample_count": int(rec["sample_count"]),
                     "n_batches": int(rec["n_batches"]),
                     "p_ref": float(rec["p_ref_full"]),
                     "p_ref_full_SE": float(rec["p_ref_full_SE"]),
                     "p_ref_full_CI": [float(x) for x in rec["p_ref_full_CI"]],
                     "namespace": None,
                     "record_type": rec.get("event_definition_id"),
                     "durable_complete_verified": True}
        entries.append(entry)
    if len(entries) != N_CONFIGS or len({e["config_id"] for e in entries}) != N_CONFIGS:
        raise RuntimeError("M3-S25-R1-X: P_ref registry must have exactly 30 "
                           "unique entries")
    registry = {"schema_version": "m3s25r1_p_ref_registry_v1",
                "p_ref_sampling_budget": 0,
                "rule": "P_ref reuse only: source exists -> source hash "
                        "verified -> protocol compatible -> exactly one "
                        "durable source; any failure => M3-S25-R1-X / STOP "
                        "/ NO P_ref RESAMPLING",
                "governing_pref_protocol": {
                    "path": "configs/phase_m3s2s/reference_truth_protocol/"
                            "m3cf1n_pref_protocol.json",
                    "sha256": pref_protocol_sha},
                "configs": entries}
    dump(CFG / "m3s25r1_p_ref_registry.json", registry)
    by_stage = Counter(e["source_stage"] for e in entries)
    print(f"M3-S25-R1 P_ref registry: {len(entries)} entries "
          f"({dict(by_stage)}); sampling budget = 0")
    return registry


# --------------------------------------------------------------------------
# stage: truth seed manifest (Sec. 13)
# --------------------------------------------------------------------------

def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3s25r1"
    for p in (ROOT / "results").rglob("*.csv"):
        if self_prefix in p.parents:
            continue
        try:
            with p.open(newline="", encoding="utf-8") as h:
                rdr = csv.DictReader(h)
                if rdr.fieldnames and any(f.strip() == "seed"
                                          for f in rdr.fieldnames):
                    for row in rdr:
                        try:
                            vals.add(int(row["seed"]))
                        except (TypeError, ValueError):
                            continue
        except Exception:
            continue
    return vals


def truth_seed_manifest_stage() -> dict:
    states = verify_universe_sha_only()
    plan = RT.truth_execution_plan(states)
    units = plan["discovery_units"] + plan["confirmation_units"]
    manifest = {
        "recorded_at": now(),
        "namespaces": plan["namespaces"],
        "s2s_namespace_reuse": False,
        "units": [{"unit_id": u2["unit_id"], "stream":
                   "discovery" if u2["unit_id"].startswith("DISC|") else
                   "confirmation", "state_id": u2["state_id"],
                   "namespace": u2["namespace"],
                   "seed_key": u2["seed_key"], "samples": u2["samples"]}
                  for u2 in units],
        "counts": {"discovery": len(plan["discovery_units"]),
                   "confirmation": len(plan["confirmation_units"]),
                   "pref": 0},
        "total_units": len(units),
        "frozen_before_first_simulator_call": True,
    }
    dump(CFG / "m3s25r1_truth_seed_manifest.json", manifest)
    # ---- collision audit ----
    seed_keys = [tuple(u2["seed_key"]) for u2 in units]
    if len(set(seed_keys)) != len(seed_keys) == N_UNITS:
        raise RuntimeError("M3-S25-R1-X: duplicate truth seed key")
    disc_keys = {k for u2 in plan["discovery_units"]
                 for k in [tuple(u2["seed_key"])]}
    conf_keys = {tuple(u2["seed_key"]) for u2 in plan["confirmation_units"]}
    if disc_keys & conf_keys:
        raise RuntimeError("M3-S25-R1-X: cross-stream seed collision")
    prior = _prior_recorded_seeds()
    parent_manifest = load(ROOT / "configs/phase_m3s2s/m3s2s_truth_seed_manifest.json")
    prior |= {u2["seed_key"][0] for u2 in parent_manifest.get("units", [])}
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
        raise RuntimeError(
            f"M3-S25-R1-X: historical truth seed collision: {collisions[:5]}")
    audit = {"recorded_at": now(), "units": len(units),
             "unique_seed_keys": len(set(seed_keys)),
             "duplicate_logical_unit": 0,
             "cross_stream_collision": 0,
             "historical_namespace_collision": len(collisions),
             "namespaces": plan["namespaces"],
             "TRUTH_SEED_AUDIT": "PASS"}
    dump(OUT / "m3s25r1_truth_seed_audit.json", audit)
    print(f"M3-S25-R1 truth seeds: {len(units)} units, 0 collisions, "
          "new namespaces (no S2S reuse)")
    return audit


# --------------------------------------------------------------------------
# stage: budget contract (Sec. 15-17)
# --------------------------------------------------------------------------

def budget_stage() -> dict:
    budget = {
        "schema_version": "m3s25r1_budget_contract_v1",
        "TRUTH_BUDGET_FROZEN": True,
        "p_ref_sampling_budget": 0,
        "discovery": {"units": N_STATES, "arms": 3,
                      "samples_per_arm": RT.DISCOVERY_SAMPLES_PER_ARM,
                      "samples_per_unit": RT.DISCOVERY_BUDGET_PER_STATE,
                      "total": N_STATES * RT.DISCOVERY_BUDGET_PER_STATE},
        "confirmation": {"units": N_STATES, "arms": 3,
                         "samples_per_arm": RT.CONFIRMATION_SAMPLES_PER_ARM,
                         "samples_per_unit": RT.CONFIRMATION_BUDGET_PER_STATE,
                         "total": N_STATES * RT.CONFIRMATION_BUDGET_PER_STATE},
        "TRUTH_BUDGET_PLANNED": RT.TRUTH_BUDGET_PLANNED,
        "TRUTH_BUDGET_MAX": RT.TRUTH_BUDGET_MAX,
        "planned_equals_max": RT.TRUTH_BUDGET_PLANNED == RT.TRUTH_BUDGET_MAX,
        "truth_units_total": N_UNITS,
        "topup": 0, "early_stop": False, "candidate_substitution": False,
        "parent_budget_relation": "independent NEW budget; does NOT extend "
                                  "the exhausted M3-S2S 436,000,000 budget",
    }
    if budget["TRUTH_BUDGET_PLANNED"] != 432_000_000:
        raise RuntimeError("M3-S25-R1-X: budget contract drift")
    dump(CFG / "m3s25r1_budget_contract.json", budget)
    print(f"M3-S25-R1 budget: planned == max == "
          f"{budget['TRUTH_BUDGET_PLANNED']:,}; P_ref = 0")
    return budget


# --------------------------------------------------------------------------
# stage: preflight (Sec. 9/31; zero sampling)
# --------------------------------------------------------------------------

def verify_universe_sha_only() -> list[dict]:
    recorded = load(OUT / "m3s25r1_candidate_universe_hash.json")[
        "candidate_universe_sha256"]
    got = sha_bytes(UNIVERSE.read_bytes())
    if got != recorded:
        raise RuntimeError(
            f"M3-S25-R1-X: candidate-universe sha drift: {got} != {recorded}")
    if EXPECTED_UNIVERSE_SHA != "PENDING-SET-AFTER-GENERATION" \
            and got != EXPECTED_UNIVERSE_SHA:
        raise RuntimeError(
            f"M3-S25-R1-X: candidate-universe sha pin drift: {got} != "
            f"{EXPECTED_UNIVERSE_SHA}")
    u = load(UNIVERSE)
    if u["n_states"] != N_STATES or len(u["states"]) != N_STATES:
        raise RuntimeError("M3-S25-R1-X: candidate universe shape drift")
    return u["states"]


def verify_frozen_preflight_pass() -> dict:
    pf = load(PREFLIGHT_REPORT)
    if pf.get("PREFLIGHT_VERDICT") != "PASS":
        raise RuntimeError(
            "M3-S25-R1-X: frozen preflight verdict is "
            f"{pf.get('PREFLIGHT_VERDICT')!r} ({pf.get('overall')}); "
            "execution is not authorized; STOP")
    return pf


def _restart_scan_all(states: list[dict]) -> dict:
    """Taskbook Sec. 19: scan ALL existing R1 ledgers BEFORE the simulator.
    FRESH => allowed; durable COMPLETE (hash-verified) => safe skip; ANY
    other state => M3-S25-R1-X / STOP / NO REPLAY."""
    summary = {"discovery": {"fresh": 0, "complete_verified": 0},
               "confirmation": {"fresh": 0, "complete_verified": 0}}
    for stream, states_units in (("discovery", states), ("confirmation", states)):
        ledger = TRUTH_LEDGERS[stream]
        entries = ledger_entries(ledger) if Path(ledger).exists() else []
        for s in states_units:
            unit_id = ("DISC|" if stream == "discovery" else "CONF|") + \
                s["state_id"]
            out = (TRUTH_DISC if stream == "discovery" else TRUTH_CONF) / \
                f"{s['state_id']}.json"
            rec = RT.verify_unit_fresh_or_verified(
                unit_id, out, entries, record_file_hash)
            if rec is None:
                summary[stream]["fresh"] += 1
            else:
                summary[stream]["complete_verified"] += 1
    return summary


def preflight() -> dict:
    # ---- gates frozen NO (R1 + parent) ----
    gates = {g: gate(g) for g in ("M3_S25_R1_TRUTH_AUTHORIZED",
                                  "M3_S25_R1_ARM_A_AUTHORIZED",
                                  "M3_S25_R1_ARM_B_AUTHORIZED")}
    parent_closed = {g: (not parent_gate(g)) for g in
                     ("TRUTH_SAMPLING_AUTHORIZED", "ARM_A_AUTHORIZED",
                      "ARM_B_AUTHORIZED")}
    if any(gates.values()):
        raise RuntimeError("M3-S25-R1-X: R1 gates must stay NO during "
                           "preregistration")
    if not all(parent_closed.values()):
        raise RuntimeError("M3-S25-R1-X: parent gates must stay closed")
    # ---- candidate universe mechanical audit ----
    states = verify_universe_sha_only()
    windows = _windows()
    audit = CAND.invariant_audit(states)
    hist, hist_meta = HIST.historical_characterized_s2(
        sorted({s["config_id"] for s in states}))
    fresh = CAND.freshness_reaudit(states, hist)
    parent_reg = load(CFG / "m3s25r1_parent_development_registry.json")
    parent_ids = {s["state_id"] for s in parent_reg["states"]}
    cand_ids = {s["state_id"] for s in states}
    reserve_ids = {r["state_id"] for r in csvread(
        OUT / "m3s25r1_protected_reserve_18.csv")}
    # structural isolation: the generation path never reads any
    # label-bearing artifact (the only label-bearing summaries are
    # m3s2s_frozen_truth.json / m3s2s_panel_decision.json; the sweep
    # touches s2/config_id columns of characterized artifacts only, and
    # the frozen universe carries no truth fields)
    sweep_paths = [s["path"] for s in
                   load(OUT / "m3s25r1_freshness_sources.json")["sources"]]
    labels_isolated = (
        not any("frozen_truth" in p or "panel_decision" in p
                for p in sweep_paths)
        and not any(k in json.dumps(states[0]) for k in
                    ("confirmed_truth", "confirmed label", "corrected_class")))
    # ---- P_ref registry re-verification ----
    registry = load(CFG / "m3s25r1_p_ref_registry.json")
    p_ref_ok, p_ref_notes = [], []
    pref_protocol_sha = sha(VENDORED / "m3cf1n_pref_protocol.json")
    for entry in registry["configs"]:
        p = ROOT / entry["source_file"]
        ok = (p.exists()
              and sha(p) == entry["record_file_hash"]
              and entry["protocol_hash"] == pref_protocol_sha)
        p_ref_ok.append(ok)
        if not ok:
            p_ref_notes.append(entry["config_id"])
    # ---- seed manifest audit ----
    manifest = load(CFG / "m3s25r1_truth_seed_manifest.json")
    seed_keys = [tuple(x["seed_key"]) for x in manifest["units"]]
    seeds_ok = (len(manifest["units"]) == N_UNITS
                and len(set(seed_keys)) == N_UNITS
                and manifest["counts"] == {"discovery": N_STATES,
                                           "confirmation": N_STATES,
                                           "pref": 0})
    # ---- budget audit ----
    budget = load(CFG / "m3s25r1_budget_contract.json")
    budget_ok = (budget["TRUTH_BUDGET_PLANNED"]
                 == budget["TRUTH_BUDGET_MAX"] == 432_000_000
                 and budget["discovery"]["total"] == 72_000_000
                 and budget["confirmation"]["total"] == 360_000_000
                 and budget["p_ref_sampling_budget"] == 0
                 and budget["topup"] == 0 and budget["early_stop"] is False)
    # ---- dry assembly (no simulator) ----
    from hyptraj.m3d.benchmark_states import assemble_state
    assembled = 0
    for s in states:
        bench = VR.resolve_bench_config(s["config_id"])
        st = assemble_state(bench, float(s["s2"]), short_config=s["config_id"])
        if isinstance(st, dict):
            raise RuntimeError(f"M3-S25-R1-X: dry assembly failed: {s['state_id']}")
        assembled += 1
    # ---- destination state: stage-aware.  Pre-truth everything is
    # empty; post-truth the ledgers must be EXACTLY the durable terminal
    # state (240+240 COMPLETE, 0 CONSUMED_INVALID); the Arm-A destinations
    # must always be empty at preflight time ----
    def _dir_empty(d: Path) -> bool:
        return not d.exists() or not any(d.iterdir())

    def _truth_ledger_terminal(path: Path, expected: int) -> bool:
        if not path.exists() or not path.read_text(
                encoding="utf-8").strip():
            return True                      # pre-truth: empty is fine
        c = Counter(e.get("status") for e in ledger_entries(path))
        return (c.get("COMPLETE", 0) == expected
                and c.get("CONSUMED_INVALID", 0) == 0)

    dest_empty = (_truth_ledger_terminal(
                      TRUTH_LEDGERS["discovery"], N_STATES)
                  and _truth_ledger_terminal(
                      TRUTH_LEDGERS["confirmation"], N_STATES)
                  and _dir_empty(ARM_A_TRIALS) and not ARM_A_LEDGER.exists()
                  and not ARM_A_EVAL.exists())
    # ---- path/disk ----
    max_path = 0
    run_uuid = "M3-S25-R1-PREFLIGHT"
    for s in states[:64]:
        slug = bounded_slug(s["state_id"])
        for stream_dir in (TRUTH_DISC, TRUTH_CONF):
            final = stream_dir / f"{s['state_id']}.json"
            temp = final.parent / bounded_temp_basename(slug, run_uuid)
            max_path = max(max_path, len(str(final)), len(str(temp)))
    disk = shutil.disk_usage(ROOT)
    paths_ok = max_path <= FULL_PATH_LIMIT
    # ---- assemble verdict (M3-S25-R1.1 support-coverage invariants) ----
    inv_failures = audit["invariant_failures"]
    checks = {
        "configs_30": audit["checks"]["configs"],
        "strata_per_config_8": audit["checks"]["states_per_config_8"],
        "candidates_240": audit["checks"]["candidates"],
        "duplicate_state_id_0": audit["checks"]["duplicate_state_id"],
        "freshness_violations_0": fresh["FRESH"],
        "legality_violations_0": audit["checks"]["legality_violations"] == 0,
        "truth_labels_consulted_0": labels_isolated,
        "candidate_substitution_0": not (cand_ids & parent_ids) and
                                    not (cand_ids & reserve_ids),
        "min_u_ge_0.15": audit["checks"]["min_u_ge_0.15"],
        "max_u_le_1.0": audit["checks"]["max_u_le_1.0"],
        "invariant_A_stratum_occupancy_8of8":
            audit["checks"]["invariant_A_stratum_occupancy"],
        "invariant_B_min_reach_structural":
            audit["checks"]["invariant_B_min_reach_structural"],
        "invariant_C_max_reach_structural":
            audit["checks"]["invariant_C_max_reach_structural"],
        "invariant_D_span_structural":
            audit["checks"]["invariant_D_span_structural"],
        "p_ref_registry_30_verified": all(p_ref_ok) and len(registry["configs"]) == 30,
        "truth_seed_manifest_480_unique": seeds_ok,
        "budget_432M_planned_eq_max": budget_ok,
        "dry_assembly_240": assembled == N_STATES,
        "destinations_empty": dest_empty,
        "r1_gates_frozen_no": not any(gates.values()),
        "parent_gates_closed": all(parent_closed.values()),
        "path_length_ok": paths_ok,
        "disk_ok": disk.free > 1_000_000_000,
    }
    failed = sorted(k for k, v in checks.items() if not v)
    support_conflicts = []
    for r in inv_failures:
        support_conflicts.append({
            "config_id": r["config_id"],
            "failed_invariants": r["failed"],
            "min_u": r["min_u"], "max_u": r["max_u"], "span": r["span"],
            "note": "no candidate substitution, no rule relaxation "
                    "(amendment chain: FAIL => PREFLIGHT BLOCKED; rule "
                    "changes require a new taskbook)",
        })
    ok_all = not failed
    verdict = "PASS" if ok_all else "FAIL"
    overall = ("EXECUTION-READY" if ok_all else
               "M3-S25-R1 PREFLIGHT BLOCKED: structural support invariant "
               "FAIL (" + "; ".join(
                   f"{c['config_id']}: {','.join(c['failed_invariants'])}"
                   for c in support_conflicts) + "); samples = 0; all gates "
               "remain NO; human adjudication required (no self-modification "
               "of rules)")
    r1_1_evidence = OUT / "m3s25r1_1_preflight_R1_1_historical.json"
    report = {
        "recorded_at": now(), "simulator_calls": 0, "samples": 0,
        "checks": checks, "failed_checks": failed,
        "support_invariants": {
            "version": CAND.INVARIANT_VERSION,
            "definition": audit["invariant_definition"],
            "structural_bounds": audit["structural_bounds"],
            "superseded_chain": audit["superseded_invariant"],
            "amendment_document":
                "docs/phase_m3s25r1/M3_S25_R1_2_Amendment_Taskbook.md",
            "r1_1_blocked_evidence": {
                "file": r1_1_evidence.relative_to(ROOT).as_posix(),
                "sha256": sha(r1_1_evidence) if r1_1_evidence.exists() else None,
                "verdict": "FAIL (invariant_B_min_reach_le_0.25: "
                           "m3s2s_cfg_005 min u 0.251420 > 0.25)"},
            "conflicts": support_conflicts or [],
            "status": "PASS" if not support_conflicts else "FAIL"},
        "per_config_support": audit["per_config"],
        "freshness_reaudit": fresh,
        "historical_sweep": {k: v for k, v in hist_meta.items()
                             if k != "sources"},
        "p_ref_registry_entries": len(registry["configs"]),
        "seed_manifest_units": len(manifest["units"]),
        "budget_planned": budget["TRUTH_BUDGET_PLANNED"],
        "dry_assembly": assembled,
        "max_path_len": max_path, "path_limit": FULL_PATH_LIMIT,
        "disk_free_bytes": disk.free,
        "PREFLIGHT_VERDICT": verdict,
        "overall": overall,
    }
    dump(PREFLIGHT_REPORT, report)
    print(f"M3-S25-R1 preflight: {verdict} "
          f"({len(checks) - len(failed)}/{len(checks)} checks PASS; "
          f"invariant conflicts: "
          f"{[(c['config_id'], c['failed_invariants']) for c in support_conflicts]})")
    return report


# --------------------------------------------------------------------------
# stage: contracts (Sec. 32)
# --------------------------------------------------------------------------

def contracts() -> dict:
    pins = verify_parent_universe_pin()
    tc = load(PARENT_TRUTH_CONTRACT)
    pf = load(PREFLIGHT_REPORT)
    contract = {
        "schema_version": "m3s25r1_contract_v1",
        "stage": "M3-S25-R1",
        "stage_nature": "Replacement Development / Parameter-Support "
                        "Completion",
        "parent": {
            "stage": PARENT_STAGE, "terminal": PARENT_TERMINAL,
            "frozen_head": PARENT_HEAD,
            "gates_closed": True,
            "truth_budget_consumed": PARENT_TRUTH_BUDGET,
            "closure_record": "docs/phase_m3s2s/M3_S2S_Closure_Record.md",
            "old_t1_gate_reuse": "FORBIDDEN"},
        "config_universe": {
            "rule": "strict inheritance of the M3-S2S frozen 30-config "
                    "universe (taskbook Sec. 4)",
            "n_configs": N_CONFIGS,
            "parent_universe_sha256": pins["parent_universe_sha256"],
            "parent_new_config_registry_sha256":
                pins["parent_new_config_registry_sha256"],
            "no_new_configs": True, "no_substitution": True,
            "no_deletion": True, "no_label_based_reweighting": True,
            "hash_pin": True},
        "support": {
            "coordinate": "u = (log s2 - log s2_lo)/(log s2_hi - log s2_lo)",
            "s2_hi": CAND.S2_HI,
            "legality_calculation": "inherited byte-identical (parent "
                                    "_config_windows machinery)",
            "u_interval": [CAND.U_LO, CAND.U_HI],
            "frozen_before_truth_sampling": True,
            "n_strata": N_STRATA,
            "strata_boundaries": [list(CAND.stratum_bounds(i))
                                  for i in range(N_STRATA + 1)],
            "anchors_per_stratum": CAND.L_ANCHORS,
            "anchor_formula": "u_{i,m} = e_i + (m+1)/(L+1) (e_{i+1}-e_i)",
            "anchor_hash_template": 'SHA256("M3-S25-R1-CANDIDATE-V1|'
                                    '<config_id>|<stratum_id>|'
                                    '<canonical_s2>")',
            "canonical_s2_rule": "repr(float(s2)) (shortest round-trip "
                                 "decimal == JSON serialization form)",
            "selection_rule": "hash-ascending; first legal AND fresh anchor",
            "selection_independence": ["truth labels", "discovery results",
                                       "SHRINK/HOLD counts",
                                       "candidate numeric ordering"],
            "no_cross_stratum_borrowing": True,
            "parent_realized_u_max": 0.123077},
        "support_invariants": {
            "version": "m3s25r1.2",
            "status": "ACTIVE",
            "A_stratum_occupancy": "each config occupies all 8 strata "
                                   "exactly once (0 empty strata)",
            "B_min_support_reach":
                "per config: min(u) <= u0_max + tol "
                "(structural, derived from generator constants)",
            "C_max_support_reach":
                "per config: max(u) >= u7_min - tol "
                "(structural, derived from generator constants)",
            "D_anti_collapse_span":
                "per config: max(u) - min(u) >= (u7_min - u0_max) - tol "
                "(structural, derived from generator constants)",
            "structural_bounds": CAND.structural_bounds(),
            "rationale": "test structural coverage rather than luck in the "
                         "hash-first anchor position; the bounds are "
                         "deterministic generator guarantees, removing the "
                         "remaining random-hash dependence of fixed decimal "
                         "thresholds",
            "superseded_chain": [
                {"version": "m3s25r1.0",
                 "invariant": "per-config max(u) - min(u) >= 0.70",
                 "verdict": "FAIL (c000 span 0.6971, cf1n_new_002 span "
                            "0.6649; rank-1 zero-collision hash draws)",
                 "record": "docs/phase_m3s25r1/"
                           "M3_S25_R1_Support_Invariant_Conflict.md"},
                {"version": "m3s25r1.1",
                 "invariant": "A 8/8 strata; B min(u) <= 0.25; "
                              "C max(u) >= 0.85; D span >= 0.65",
                 "verdict": "FAIL (m3s2s_cfg_005 min u 0.251420 > 0.25; "
                            "stratum-0 rank-1 zero-collision hash draw)",
                 "record": "docs/phase_m3s25r1/"
                           "M3_S25_R1_1_Amendment_Record.md",
                 "blocked_evidence": {
                     "file": "results/phase_m3s25r1/preflight/"
                             "m3s25r1_1_preflight_R1_1_historical.json",
                     "sha256": "5cdf399fd9ab7b8a76840ef10e1a6b12744bfbc656e"
                               "816f55e473160fc2e54aa"}}]},
        "amendment": {
            "stage": "M3-S25-R1.2",
            "document": "docs/phase_m3s25r1/"
                        "M3_S25_R1_2_Amendment_Taskbook.md",
            "document_sha256": sha(DOC /
                                   "M3_S25_R1_2_Amendment_Taskbook.md"),
            "parent_contract_sha256": "1e34017adfab4975e26d9177c61b94f98b908"
                                      "b8a9b1acadba71367c32e2a7da5",
            "old_invariant": "M3-S25-R1.1 fixed thresholds: B min(u) <= 0.25; "
                             "C max(u) >= 0.85; D span >= 0.65",
            "new_invariants": ["A: stratum occupancy 8/8",
                               "B: min(u) <= u0_max + tol",
                               "C: max(u) >= u7_min - tol",
                               "D: span >= (u7_min - u0_max) - tol"],
            "structural_bounds_derivation":
                "w = (U_HI-U_LO)/N_STRATA; u0_max = U_LO + "
                "L_ANCHORS/(L_ANCHORS+1)*w; u7_min = U_LO + (N_STRATA-1)*w "
                "+ 1/(L_ANCHORS+1)*w; computed from the frozen generator "
                "constants (not independently tunable decimals); "
                "tol = 1e-12",
            "reason": "R1.1 correctly identified that support invariants "
                      "must test structural coverage rather than luck in "
                      "the hash-first anchor position; B <= 0.25 remained "
                      "stricter than the generator guarantee and D >= 0.65 "
                      "remained slightly stricter than the deterministic "
                      "extreme-stratum interior-anchor guarantee; R1.2 "
                      "removes the remaining random-hash dependence",
            "unchanged": ["candidate universe + its SHA",
                          "candidate generation mechanism",
                          "hash ranking", "freshness rules", "legality",
                          "seeds", "truth semantics", "budget",
                          "runtime ordering", "panel rules",
                          "all authorization gates"]},
        "freshness_firewall": {
            "rule": "fresh against EVERY historically characterized s2 of "
                    "the same config",
            "tolerance": "|s2 - s2_h| <= 1e-6 * max(1, |s2_h|)",
            "minimum_families": ["M3-CF*", "M3-WCF*", "M3-PI*", "M3-S1*",
                                 "M3-S2S",
                                 "all retired/truth-exposed/development "
                                 "artifacts"],
            "parent_240_truth_exposed_included": True},
        "truth_semantics": {
            "inherited": "byte-identical / hash-pinned to the parent "
                         "protocol (taskbook Sec. 12)",
            "event_semantics": "corrected full-event v2",
            "parent_truth_contract_sha256": sha(PARENT_TRUTH_CONTRACT),
            "parent_vendored_snapshots": tc["vendored_snapshots"],
            "changed_vs_parent": "state support ONLY",
            "classifier_retune_forbidden": True,
            "discovery_budget_per_state": RT.DISCOVERY_BUDGET_PER_STATE,
            "confirmation_budget_per_state": RT.CONFIRMATION_BUDGET_PER_STATE},
        "confirmation_scope": "ALL_240_R1_CANDIDATES",
        "early_stop": False,
        "seed_namespaces": {
            "discovery": RT.DISCOVERY_NAMESPACE,
            "confirmation": RT.CONFIRMATION_NAMESPACE,
            "s2s_namespace_reuse": False},
        "budget": {
            "planned": 432_000_000, "max": 432_000_000,
            "discovery": 72_000_000, "confirmation": 360_000_000,
            "p_ref": 0, "topup": 0,
            "budget_contract": "configs/phase_m3s25r1/"
                               "m3s25r1_budget_contract.json"},
        "p_ref": {
            "registry": "configs/phase_m3s25r1/m3s25r1_p_ref_registry.json",
            "entries": 30, "sampling_budget": 0,
            "rule": "reuse only; hash-verified; any failure => "
                    "M3-S25-R1-X / STOP / NO P_ref RESAMPLING"},
        "persistence": {
            "module": "hyptraj.m3wa1r.persistence.run_trial_transactional",
            "durable_unit_contract": "exactly one STARTED + exactly one "
                                     "COMPLETE + valid artifact hash",
            "consumed_invalid_rule": "sampling without durable COMPLETE => "
                                     "CONSUMED_INVALID => M3-S25-R1-X => "
                                     "STOP => NO REPLAY",
            "restart_scan": "all ledgers scanned before the simulator; "
                            "STARTED-only / CONSUMED_INVALID / orphan "
                            "artifact / hash mismatch => STOP"},
        "development": {
            "union": "D_union = D_old (M3-S2S 240) u D_new (R1 240), "
                     "max 480 states",
            "old_states_registry": "configs/phase_m3s25r1/"
                                   "m3s25r1_parent_development_registry.json",
            "old_development_eligible": True,
            "old_untouched_confirmation_eligible": False,
            "new_inventory_rule": "all 240 R1 states enter "
                                  "m3s25r1_truth_exposed_inventory.json; "
                                  "development_eligible = YES; "
                                  "untouched_confirmation_eligible = NO"},
        "panel": {
            "states": 120, "quota": RT.PANEL_QUOTA,
            "min_unique_configs": RT.MIN_CONFIGS,
            "input_pool": "D_union only",
            "rank_seed": RT.PANEL_RANK_SEED,
            "round_rule": "round k takes at most the k-th ranked state per "
                          "config within each truth stratum; stop exactly "
                          "at quota (inherited S1C Amendment-A semantics)",
            "duplicate_protection": True,
            "no_quota_relaxation": True, "no_panel_shrinkage": True,
            "no_class_merging": True, "no_provisional_truth": True,
            "no_manual_state_picking": True},
        "verdicts": {
            "success": "M3-S25-R1-PANEL-FROZEN",
            "panel_blocked": "M3-S25-R1-PANEL-BLOCKED",
            "preflight_blocked": "M3-S25-R1-PREFLIGHT-BLOCKED",
            "failure": "M3-S25-R1-X"},
        "reserve_firewall": {
            "protected_states": 18,
            "rule": "protected reserve / untouched confirmation / final "
                    "validation states are forbidden to R1 (Sec. 30)"},
        "arm_gates": {"M3_S25_R1_ARM_A_AUTHORIZED": "NO",
                      "M3_S25_R1_ARM_B_AUTHORIZED": "NO",
                      "value_rarity_m3q": "BLOCKED"},
        "preregistration_round0": {
            "simulator_calls": 0, "samples": 0,
            "preflight_verdict": pf["PREFLIGHT_VERDICT"]},
        "runtime_fail_closed_ordering": [
            "1. verify parent terminal state",
            "2. verify old S2S gate closed",
            "3. verify R1 frozen inputs / candidate universe",
            "4. verify P_ref registry and source hashes",
            "5. verify all existing R1 ledger/restart states",
            "6. verify R1 human truth authorization",
            "7. construct pure execution plan",
            "8. simulator calls"],
    }
    data = dump_json(CFG / "m3s25r1_contract.json", contract)
    print("M3-S25-R1 contract frozen "
          f"(sha256 {sha_bytes(data)[:16]}...)")
    return contract


# --------------------------------------------------------------------------
# stage: docs
# --------------------------------------------------------------------------

def docs() -> None:
    pa = load(OUT / "m3s25r1_parent_audit.json")
    pf = load(PREFLIGHT_REPORT)
    univ_hash = load(OUT / "m3s25r1_candidate_universe_hash.json")
    seeds = load(OUT / "m3s25r1_truth_seed_audit.json")
    budget = load(CFG / "m3s25r1_budget_contract.json")
    registry = load(CFG / "m3s25r1_p_ref_registry.json")
    u = load(UNIVERSE)
    inv = pf["support_invariants"]
    conflicts = inv["conflicts"]
    min_u = min(s["u"] for s in u["states"])
    max_u = max(s["u"] for s in u["states"])
    write_text_lf(DOC / "M3_S25_R1_Preregistration.md", f"""# M3-S25-R1 Preregistration

Round 0: **preregistration freeze only** -- scientific simulator calls 0,
samples 0.  All numbers rendered from hash-locked artifacts.  Amended by
**M3-S25-R1.1** then **M3-S25-R1.2** (structural support invariants;
candidate universe and its SHA unchanged throughout).

```
M3-S25-R1 PREREG STATUS:
ROUND 0 COMPLETE (amended by M3-S25-R1.1, then M3-S25-R1.2)

PARENT (sealed):
M3-S2S terminal = {pa['parent_terminal']}
old T1 gate closed = YES ({', '.join(f"{k} CLOSED" for k in pa['parent_gates'])})
parent truth budget consumed = {pa['parent_truth_budget']}
parent HEAD = {pa['parent_frozen_head'][:7]} (ancestor verified)
parent ledgers = 488 COMPLETE / 0 CONSUMED_INVALID
parent truth-exposed states preserved = {pa['parent_truth_exposed_states']}

CONFIG UNIVERSE:
strict inheritance = 30 configs (parent universe sha {univ_hash['parent_universe_sha256'][:16]}...)
no new / substituted / deleted / reweighted configs = YES (hash pin)

SUPPORT COMPLETION:
u interval = [0.15, 1.00] frozen before any truth sampling
strata = 8/config, anchors = L=65/stratum, hash-first fresh selection
candidates = 240 (30 x 8), all fresh, 0 collisions
parent realized u coverage <= 0.1231; R1 realized u range = [{min_u:.4f}, {max_u:.4f}]

STRUCTURAL SUPPORT INVARIANTS (M3-S25-R1.2; bounds derived from the
frozen generator constants U_LO=0.15, U_HI=1.00, N_STRATA=8,
L_ANCHORS=65; tol=1e-12; NO hash-draw dependence):
A stratum occupancy 8/8          = {pf['checks']['invariant_A_stratum_occupancy_8of8']}
B min(u) <= u0_max + tol        = {pf['checks']['invariant_B_min_reach_structural']}
C max(u) >= u7_min - tol        = {pf['checks']['invariant_C_max_reach_structural']}
D span >= (u7_min-u0_max) - tol = {pf['checks']['invariant_D_span_structural']}
structural bounds: u0_max = {inv['structural_bounds']['u0_max']:.16f}
                   u7_min = {inv['structural_bounds']['u7_min']:.16f}
                   span   = {inv['structural_bounds']['span_bound']:.16f}
conflicts ({len(conflicts)}/30):
{chr(10).join('  - %s: failed %s (min u %.4f, max u %.4f, span %.4f)' % (c['config_id'], ','.join(c['failed_invariants']), c['min_u'], c['max_u'], c['span']) for c in conflicts) if conflicts else '  (none)'}
superseded chain: R1.0 span >= 0.70 (FAIL c000 0.6971 / cf1n_new_002 0.6649);
                  R1.1 fixed 0.25/0.85/0.65 (FAIL m3s2s_cfg_005 min u
                  0.251420 > 0.25) -- both RESOLVED by the structural
                  bounds; records: M3_S25_R1_Support_Invariant_Conflict.md,
                  M3_S25_R1_1_Amendment_Record.md; R1.1 BLOCKED preflight
                  preserved as historical evidence (m3s25r1_1_preflight_
                  R1_1_historical.json, sha {inv['r1_1_blocked_evidence']['sha256'][:16]}...)

=> PREFLIGHT VERDICT = {pf['PREFLIGHT_VERDICT']}
   {pf['overall']}

TRUTH (NOT authorized):
confirmation_scope = ALL_240_R1_CANDIDATES; early_stop = false
discovery 240 x 3x100k = 72,000,000
confirmation 240 x 3x500k = 360,000,000
P_ref = 0 (30-entry reuse registry, hash-verified, no resampling)
TRUTH_BUDGET_PLANNED = TRUTH_BUDGET_MAX = {budget['TRUTH_BUDGET_PLANNED']:,}

SEEDS:
{seeds['units']} units, new namespaces M3-S25-R1-DISCOVERY / M3-S25-R1-CONFIRMATION
unique seed keys = {seeds['unique_seed_keys']}, historical collision = {seeds['historical_namespace_collision']}, cross-stream = {seeds['cross_stream_collision']}

PANEL (post-truth only):
union pool = D_old (240) u D_new (240) <= 480; 120 states; 30/30/30/30
>= 24 distinct configs; rank seed M3-S25-R1-PANEL-V1|; duplicate protection
PANEL-BLOCKED if quotas or diversity cannot be met; NO relaxation

DEVELOPMENT UNION:
D_union = M3-S2S 240 truth-exposed states + R1 240 (registry preserved verbatim)

ARM GATES: M3_S25_R1_ARM_A_AUTHORIZED = NO; M3_S25_R1_ARM_B_AUTHORIZED = NO
VALUE / RARITY / M3-Q = BLOCKED

NEXT:
Round 0 STOP.  Structural support invariants PASS; per the M3-S25-R1.2
amendment, M3_S25_R1_TRUTH_AUTHORIZED remains NO pending the human
execution-readiness audit.  Only an explicit human NO -> YES commit
enables `python scripts/run_m3s25r1.py truth_execute`.
```

Universe sha256: `{univ_hash['candidate_universe_sha256']}`
""")

    write_text_lf(DOC / "M3_S25_R1_Parent_Closure_Audit.md", f"""# M3-S25-R1 Parent Closure Audit

Status: **{pa['PARENT_CLOSURE_AUDIT']}** ({pa['recorded_at']});
R1 HEAD `{pa['head'][:7]}`.

- Parent stage M3-S2S sealed at terminal **{pa['parent_terminal']}**
  (frozen HEAD `{pa['parent_frozen_head'][:7]}`, verified ancestor).
- Old T1 gate closed closure-only: TRUTH_SAMPLING_AUTHORIZED exercised
  and exhausted; {', '.join(f'{k} = CLOSED' for k in pa['parent_gates'])}.
- Parent truth budget consumed exactly
  {pa['parent_truth_budget']} / {pa['parent_truth_budget']} (topup 0);
  ledgers 488/488 durable COMPLETE, 0 CONSUMED_INVALID.
- All 240 parent truth-exposed states preserved verbatim in
  `configs/phase_m3s25r1/m3s25r1_parent_development_registry.json`
  (state_id / config_id / s2 / u / frozen truth / truth record path /
  record_file_hash / exposure status).
- VALUE / RARITY / M3-Q = BLOCKED.
""")

    write_text_lf(DOC / "M3_S25_R1_Candidate_Support_Audit.md", f"""# M3-S25-R1 Candidate Support Audit

Status: mechanics **PASS**, structural support invariants (M3-S25-R1.2,
bounds derived from the frozen generator constants) **{inv['status']}**
({now()}).

- Mechanism: u in [0.15, 1.00] split into 8 frozen strata; per config x
  stratum exactly one fresh state chosen as the FIRST legal+fresh anchor
  in SHA256 anchor-hash ascending order over L=65 deterministic interior
  anchors (taskbook Sec. 6/7).  Selection is independent of truth labels,
  discovery results, SHRINK/HOLD counts and candidate numeric ordering.
- 240 candidates / 30 configs / 8 strata each; duplicate state_id = 0;
  freshness violations = 0; legality violations = 0; truth labels
  consulted = 0; candidate substitution = 0.
- Realized u range over the universe: [{min_u:.4f}, {max_u:.4f}].
- M3-S25-R1.2 STRUCTURAL invariants (bounds derived from the frozen
  generator constants; tol = 1e-12): A stratum occupancy 8/8 =
  {pf['checks']['invariant_A_stratum_occupancy_8of8']}; B min(u) <= u0_max + tol =
  {pf['checks']['invariant_B_min_reach_structural']}; C max(u) >= u7_min - tol =
  {pf['checks']['invariant_C_max_reach_structural']}; D span >= (u7_min-u0_max) - tol =
  {pf['checks']['invariant_D_span_structural']}.
- Superseded chain: R1.0 span >= 0.70 (FAIL c000 0.6971 / cf1n_new_002
  0.6649) and R1.1 fixed thresholds 0.25/0.85/0.65 (FAIL m3s2s_cfg_005
  min u 0.251420 > 0.25) -- both resolved by the structural bounds.
- Per-config report:
  `results/phase_m3s25r1/preflight/m3s25r1_preflight.json`
  (`per_config_support`); historical records:
  `M3_S25_R1_Support_Invariant_Conflict.md` (R1.0),
  `M3_S25_R1_1_Amendment_Record.md` (R1.1, BLOCKED evidence preserved),
  `M3_S25_R1_2_Amendment_Record.md` (R1.2).
""")

    write_text_lf(DOC / "M3_S25_R1_Freshness_Audit.md", f"""# M3-S25-R1 Freshness Audit

Status: **{'PASS' if pf['freshness_reaudit']['FRESH'] else 'FAIL'}** ({now()}).

- Historical set: content-classified sweep over all characterized
  artifacts (truth/reference/discovery/confirmation/panel/reserve/
  state-table/universe/inventory), the M3-S1C panel, and the sealed
  parent stage M3-S2S (all 240 truth-exposed states).  Candidate
  PROPOSAL artifacts (pools/banks/selection views/plans) are not
  characterized and are excluded; the parent's own plan enters through
  its tracked universe because all 240 of its states are truth-exposed.
- Collision rule: |s2 - s2_h| <= 1e-6 * max(1, |s2_h|).
- Independent re-audit of the frozen universe: 0 collisions with any
  historical value; 0 internal collisions.
- Per-state selection audit trail:
  `results/phase_m3s25r1/preflight/m3s25r1_freshness_audit.csv`
  (selected anchor m, hash-rank position, collided/fresh counts).
""")

    write_text_lf(DOC / "M3_S25_R1_P_Ref_Source_Audit.md", f"""# M3-S25-R1 P_ref Source Audit

Status: **PASS** ({now()}); P_ref sampling budget = **0**.

- Registry: `configs/phase_m3s25r1/m3s25r1_p_ref_registry.json`
  (exactly {len(registry['configs'])} entries:
  {dict(Counter(e['source_stage'] for e in registry['configs']))}).
- The 8 M3-S2S new configs use the durable COMPLETE parent PREF records
  (`results/phase_m3s2s/pref/`): parent pref ledger shows exactly one
  STARTED + one COMPLETE per unit and COMPLETE.record_file_hash equals
  the file hash.
- All other configs use the byte-verified vendored snapshots under
  `configs/phase_m3s2s/reference_truth_protocol/pref_records/`
  (CF1N / WCF1 / legacy M3-D2).
- Every entry: source exists -> source hash verified -> protocol
  compatible (governing pref protocol snapshot
  `{registry['governing_pref_protocol']['sha256'][:16]}...`) -> exactly
  one durable source.  Any failure => M3-S25-R1-X / STOP / NO P_ref
  RESAMPLING.
""")

    write_text_lf(DOC / "M3_S25_R1_Seed_Audit.md", f"""# M3-S25-R1 Seed Audit

Status: **{seeds['TRUTH_SEED_AUDIT']}** ({seeds['recorded_at']}).

- New independent namespaces `{RT.DISCOVERY_NAMESPACE}` /
  `{RT.CONFIRMATION_NAMESPACE}`; the M3-S2S seed namespace is NOT reused
  (taskbook Sec. 13).
- {seeds['units']} truth units (240 discovery + 240 confirmation), all
  seeds derived by the frozen deterministic function; {seeds['unique_seed_keys']}
  unique seed keys; duplicate logical unit = 0; cross-stream collision =
  0; historical namespace collision = {seeds['historical_namespace_collision']}
  (all recorded historical seed pools + M3-S2S truth manifest + CF1N
  manifests audited).
""")

    write_text_lf(DOC / "M3_S25_R1_Budget_Audit.md", f"""# M3-S25-R1 Budget Audit

Exact integer budgets (taskbook Sec. 15-17; no placeholders):

| stream | budget |
|---|---|
| Truth discovery (240 x 3 x 100k) | {budget['discovery']['total']:,} |
| Truth confirmation (240 x 3 x 500k) | {budget['confirmation']['total']:,} |
| Truth P_ref (reuse registry; sampling forbidden) | 0 |
| **TRUTH_BUDGET_PLANNED** | **{budget['TRUTH_BUDGET_PLANNED']:,}** |
| **TRUTH_BUDGET_MAX** | **{budget['TRUTH_BUDGET_MAX']:,}** |
| truth units | {budget['truth_units_total']} |

planned == max; topup = 0; early_stop = false; candidate substitution =
false.  This is an independent NEW budget and does NOT extend the
exhausted M3-S2S budget of 436,000,000.
""")


def amendment_record_doc() -> None:
    """M3-S25-R1.1 amendment application record (zero sampling).

    The R1.0 conflict record (M3_S25_R1_Support_Invariant_Conflict.md) is
    a sealed historical document and is NOT rewritten; this record
    documents the amendment application and its realized outcome."""
    pf = load(PREFLIGHT_REPORT)
    inv = pf["support_invariants"]
    conflicts = inv["conflicts"]
    rows = "\n".join(
        "| %s | %s | %.6f | %.6f | %.6f |" % (
            c["config_id"], ", ".join(c["failed_invariants"]),
            c["min_u"], c["max_u"], c["span"])
        for c in conflicts) or "| (none) | | | | |"
    per = pf["per_config_support"]
    amendment_sha = sha(DOC / "M3_S25_R1_1_Amendment_Taskbook.md")         if Path(DOC / "M3_S25_R1_1_Amendment_Taskbook.md").exists() else "n/a"
    write_text_lf(DOC / "M3_S25_R1_1_Amendment_Record.md", f"""# M3-S25-R1.1 Amendment Record (zero sampling)

Amendment document:
`docs/phase_m3s25r1/M3_S25_R1_1_Amendment_Taskbook.md` (sha256
`{amendment_sha}`).
Applied per amendment Sec. 13: amendment document -> contract invariant
update only -> hash manifest -> zero-sampling preflight -> regression
tests -> candidate-SHA verification -> commit -> push -> STOP.

## What changed (and what did not)

- REPLACED: the M3-S25-R1.0 support-span regression invariant
  (per-config `span >= 0.70`) with the M3-S25-R1.1 support-coverage
  invariants A/B/C/D (recorded in `m3s25r1_contract.json` together with
  the parent contract hash, the amendment hash, the old invariant, the
  new invariants and the reason).
- UNCHANGED (amendment Sec. 2/6): the candidate universe file and its
  SHA256 (`9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`),
  the generation mechanism, hash-first selection, freshness firewall,
  legality rules, seeds, truth semantics, budget (432,000,000),
  runtime fail-closed ordering, panel rules.  No re-hash, no re-draw,
  no candidate substitution.

## Zero-sampling validation outcome (amendment Sec. 8/12)

- Candidate immutability: 240 states / 30 configs / 8 strata per config,
  universe SHA unchanged -- PASS.
- Freshness: 0 collisions, 0 substitutions -- PASS.
- Support invariants:
  - A (stratum occupancy 8/8): PASS for all 30 configs.
  - C (max(u) >= 0.85): PASS for all 30 configs (worst max u =
    {min(r['max_u'] for r in per):.6f}).
  - D (span >= 0.65): PASS for all 30 configs (worst span =
    {min(r['span'] for r in per):.6f}) -- the ORIGINAL R1.0 conflict
    (c000 span 0.6971, cf1n_new_002 span 0.6649) is RESOLVED by D.
  - B (min(u) <= 0.25): **FAIL for {len(conflicts)}/30 configs**:

| config | failed | min u | max u | span |
|---|---|---|---|---|
{rows}

## Residual conflict (same structural class as the R1.0 conflict)

The B-violating selection is the stratum-0 rank-1 (lowest-hash) fresh
anchor with ZERO collisions -- again a pure hash draw, not a freshness
or legality artifact.  A stratum-0 anchor is uniform over
u in (0.1516, 0.2546); `min(u) <= 0.25` fails iff the draw lands in the
top 3 of 65 positions (m >= 62), a per-config probability of about
4.6 percent, hence about 76 percent across 30 configs.  The mechanism's
structural guarantee is `min(u) < e_1 = 0.25625`, so the frozen 0.25
threshold again exceeds what the mechanism guarantees.  Measured fact
for adjudication: any B threshold in [0.251421, 0.25625) passes the
frozen universe; `0.25625` (= e_1) is the exact structural bound.

## Disposition (amendment Sec. 12; fail-closed)

- Preflight verdict: **{pf['PREFLIGHT_VERDICT']}** -- outcome
  **M3-S25-R1.1 PREFLIGHT BLOCKED**, samples = 0, simulator calls = 0.
- No self-modification of rules (amendment Sec. 12); `truth_execute`
  refuses while the frozen preflight verdict is not PASS; all three R1
  gates and the sealed parent gates remain NO.
- The original R1.0 conflict is resolved (D); the residual B conflict is
  documented above with its exact numbers for the next human
  adjudication.
""")


def amendment2_record_doc() -> None:
    """M3-S25-R1.2 amendment application record (zero sampling).

    The R1.0/R1.1 records are sealed historical documents and are NOT
    rewritten; the R1.1 BLOCKED preflight report is preserved verbatim as
    historical evidence.  This record documents the R1.2 structural
    amendment application and its realized outcome."""
    pf = load(PREFLIGHT_REPORT)
    inv = pf["support_invariants"]
    conflicts = inv["conflicts"]
    rows = "\n".join(
        "| %s | %s | %.6f | %.6f | %.6f |" % (
            c["config_id"], ", ".join(c["failed_invariants"]),
            c["min_u"], c["max_u"], c["span"])
        for c in conflicts) or "| (none) | | | | |"
    per = pf["per_config_support"]
    b = inv["structural_bounds"]
    amendment_sha = sha(DOC / "M3_S25_R1_2_Amendment_Taskbook.md")
    write_text_lf(DOC / "M3_S25_R1_2_Amendment_Record.md", f"""# M3-S25-R1.2 Amendment Record (zero sampling)

Amendment document:
`docs/phase_m3s25r1/M3_S25_R1_2_Amendment_Taskbook.md` (sha256
`{amendment_sha}`).  Parent: M3-S25-R1.1 at commit
`37553a207d96b2edcc827595f0b711e392c4358f`.

## What changed (and what did not)

- REPLACED: the M3-S25-R1.1 fixed decimal support thresholds
  (B min(u) <= 0.25; C max(u) >= 0.85; D span >= 0.65) with
  GENERATOR-DERIVED STRUCTURAL invariants computed from the frozen
  constants U_LO = 0.15, U_HI = 1.00, N_STRATA = 8, L_ANCHORS = 65:
  `w = (U_HI-U_LO)/N_STRATA`; `u0_max = U_LO + L_ANCHORS/(L_ANCHORS+1)*w`;
  `u7_min = U_LO + (N_STRATA-1)*w + 1/(L_ANCHORS+1)*w`; frozen numerical
  tolerance tol = 1e-12.  The implementation
  (`hyptraj.m3s25r1.candidates.structural_bounds`) computes the bounds
  from the constants and takes no data input, so realized candidate
  values cannot tune the thresholds.
- UNCHANGED: the frozen candidate universe and its byte SHA256
  (`9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`),
  candidate generation, hash ranking, freshness rules, legality, seeds,
  truth semantics, budget (432,000,000), runtime ordering, panel rules,
  and every authorization gate.
- PRESERVED: the R1.1 preflight BLOCKED report as historical evidence --
  `results/phase_m3s25r1/preflight/m3s25r1_1_preflight_R1_1_historical.json`
  (sha256 `{inv['r1_1_blocked_evidence']['sha256']}`, verdict FAIL,
  failed check invariant_B_min_reach_le_0.25 for m3s2s_cfg_005).

## Zero-sampling validation outcome

- Universe byte SHA unchanged: PASS.  240 states / 30 configs /
  8 strata per config: PASS.  Freshness: 0 collisions, 0 substitutions:
  PASS.  Truth-semantics hash, seed manifests, budget 432,000,000:
  PASS.  Simulator calls = 0; samples = 0.
- Structural invariants (all PASS):
  - A (stratum occupancy 8/8): PASS for all 30 configs.
  - B min(u) <= u0_max + tol, u0_max = {b['u0_max']:.16f}: PASS
    (worst realized min u = {max(r['min_u'] for r in per):.6f}).
  - C max(u) >= u7_min - tol, u7_min = {b['u7_min']:.16f}: PASS
    (worst realized max u = {min(r['max_u'] for r in per):.6f}).
  - D span >= (u7_min - u0_max) - tol = {b['span_bound']:.16f}: PASS
    (worst realized span = {min(r['span'] for r in per):.6f}).
- Realized conflicts: {len(conflicts)}/30.

| config | failed | min u | max u | span |
|---|---|---|---|---|
{rows}

## Disposition

- Preflight verdict: **{pf['PREFLIGHT_VERDICT']}** --
  {pf['overall']}.
- Per amendment: M3_S25_R1_TRUTH_AUTHORIZED remains NO pending the human
  execution-readiness audit; ARM_A / ARM_B remain NO; VALUE / RARITY /
  M3-Q BLOCKED; simulator calls = 0; samples = 0.
- Amendment history preserved without squashing: R1.0 (commit e244a06)
  and R1.1 (commit 37553a2) remain in history; this amendment is the
  next commit.
- STOP for human audit.
""")


# --------------------------------------------------------------------------
# stage: hashlock (Sec. 32)
# --------------------------------------------------------------------------

def hashlock() -> dict:
    pf = load(PREFLIGHT_REPORT)
    files = sorted(p for p in CFG.glob("m3s25r1_*.json")
                   if p.name != "m3s25r1_hash_manifest.json") + \
        sorted(OUT.glob("m3s25r1_*.json")) + \
        sorted(p for p in DOC.glob("M3_S25_R1_*.md")
               if p.name != "M3_S25_R1_Human_Approval.md")
    manifest = {
        "recorded_at": now(), "head": git_commit(),
        "python_version": sys.version,
        "preregistration_round0": {"simulator_calls": 0, "samples": 0},
        "preflight_verdict": pf["PREFLIGHT_VERDICT"],
        "scientific_code_hashes": {
            "scripts/run_m3s25r1.py": sha(ROOT / "scripts/run_m3s25r1.py"),
            "src/hyptraj/m3s25r1/__init__.py": sha(ROOT / "src/hyptraj/m3s25r1/__init__.py"),
            "src/hyptraj/m3s25r1/candidates.py": sha(ROOT / "src/hyptraj/m3s25r1/candidates.py"),
            "src/hyptraj/m3s25r1/history.py": sha(ROOT / "src/hyptraj/m3s25r1/history.py"),
            "src/hyptraj/m3s25r1/runtime.py": sha(ROOT / "src/hyptraj/m3s25r1/runtime.py"),
            "src/hyptraj/m3s25r1/arm_a.py": sha(ROOT / "src/hyptraj/m3s25r1/arm_a.py"),
            "src/hyptraj/m3s25r1/arm_a_eval.py": sha(ROOT / "src/hyptraj/m3s25r1/arm_a_eval.py"),
            "src/hyptraj/m3ml0/evaluation.py": sha(ROOT / "src/hyptraj/m3ml0/evaluation.py"),
            "src/hyptraj/m3ml0/threshold.py": sha(ROOT / "src/hyptraj/m3ml0/threshold.py"),
            "src/hyptraj/m3ml0/features.py": sha(ROOT / "src/hyptraj/m3ml0/features.py"),
            "src/hyptraj/m3ml0/models.py": sha(ROOT / "src/hyptraj/m3ml0/models.py"),
            "src/hyptraj/m3pi1vr0/persistence.py": sha(ROOT / "src/hyptraj/m3pi1vr0/persistence.py"),
            "scripts/run_m3s2s.py": sha(ROOT / "scripts/run_m3s2s.py"),
            "src/hyptraj/m3s2s/truth_contract.py": sha(ROOT / "src/hyptraj/m3s2s/truth_contract.py"),
            "src/hyptraj/m3s2s/instrumentation.py": sha(ROOT / "src/hyptraj/m3s2s/instrumentation.py"),
            "src/hyptraj/m3s2s/vendored_runtime.py": sha(ROOT / "src/hyptraj/m3s2s/vendored_runtime.py"),
            "src/hyptraj/m3s2s/truth_execution.py": sha(ROOT / "src/hyptraj/m3s2s/truth_execution.py"),
            "src/hyptraj/m3d2/experiment.py": sha(ROOT / "src/hyptraj/m3d2/experiment.py"),
            "src/hyptraj/m3/gradient_estimator.py": sha(ROOT / "src/hyptraj/m3/gradient_estimator.py"),
            "src/hyptraj/m3wa1r/persistence.py": sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
            "src/hyptraj/m3cf1r0/persistence.py": sha(ROOT / "src/hyptraj/m3cf1r0/persistence.py"),
            "src/hyptraj/m3cf1/workflow.py": sha(ROOT / "src/hyptraj/m3cf1/workflow.py"),
            "src/hyptraj/m3d/benchmark_states.py": sha(ROOT / "src/hyptraj/m3d/benchmark_states.py"),
            "src/hyptraj/m3d/adaptation.py": sha(ROOT / "src/hyptraj/m3d/adaptation.py"),
            "src/hyptraj/m1d/experiments.py": sha(ROOT / "src/hyptraj/m1d/experiments.py"),
        },
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p),
                   "size_bytes": p.stat().st_size} for p in files],
        "PREREG_HASH_LOCK": "PASS",
    }
    dump(CFG / "m3s25r1_hash_manifest.json", manifest)
    return manifest


# --------------------------------------------------------------------------
# gated truth execution (Sec. 14/20/22/34)
# --------------------------------------------------------------------------

def _p_ref_source_resolver(entry: dict):
    path = ROOT / entry["source_file"]
    if not path.exists():
        raise RuntimeError(
            f"M3-S25-R1-X: P_ref source missing: {path}; STOP; NO P_ref "
            "RESAMPLING")
    raw = path.read_text(encoding="utf-8")
    if entry["source_stage"] == "M3-D2":
        refs = json.loads(raw)
        recs = refs["records"] if isinstance(refs, dict) and "records" in refs \
            else refs
        matches = [r for r in recs
                   if str(r.get("config_id", "")).endswith(entry["config_id"])]
        if len(matches) != 1:
            raise RuntimeError(
                f"M3-S25-R1-X: legacy P_ref ambiguous for "
                f"{entry['config_id']}")
        return path, matches[0]
    return path, json.loads(raw)


def _p_refs_for(states: list[dict]) -> dict[str, dict]:
    registry = load(CFG / "m3s25r1_p_ref_registry.json")
    out = {}
    for cid in sorted({s["config_id"] for s in states}):
        out[cid] = RT.p_ref_from_registry(cid, registry,
                                          _p_ref_source_resolver,
                                          record_file_hash)
    return out


def truth_execute() -> dict:
    """GATED truth command (taskbook Sec. 20/34).  Fail-closed ordering:
    parent terminal state -> old gate closed -> frozen inputs/universe ->
    P_ref registry -> restart scan -> authorization -> pure plan ->
    simulator.  Zero writes before step 6."""
    # 1. verify parent terminal state
    pa = load(OUT / "m3s25r1_parent_audit.json")
    if pa["PARENT_CLOSURE_AUDIT"] != "PASS" or \
            pa["parent_terminal"] != PARENT_TERMINAL:
        raise RuntimeError("M3-S25-R1-X: parent terminal state drift")
    # 2. verify old S2S gate closed
    for g in ("TRUTH_SAMPLING_AUTHORIZED", "ARM_A_AUTHORIZED",
              "ARM_B_AUTHORIZED"):
        if parent_gate(g):
            raise RuntimeError(
                f"M3-S25-R1-X: old M3-S2S gate {g} is not closed; the old "
                "T1 authorization may not be reused")
    # 3. verify R1 frozen inputs / candidate universe + frozen preflight
    states = verify_universe_sha_only()
    pf = verify_frozen_preflight_pass()
    reg_sha = sha(CFG / "m3s25r1_parent_development_registry.json")
    contract_sha = sha(CFG / "m3s25r1_contract.json")
    if contract_sha != EXPECTED_CONTRACT_SHA and \
            EXPECTED_CONTRACT_SHA != "PENDING-SET-AFTER-GENERATION":
        raise RuntimeError(
            f"M3-S25-R1-X: contract sha pin drift: {contract_sha} != "
            f"{EXPECTED_CONTRACT_SHA}")
    # 4. verify P_ref registry and source hashes (all 30, before anything)
    p_refs = _p_refs_for(states)
    if len(p_refs) != 30:
        raise RuntimeError("M3-S25-R1-X: P_ref registry incomplete")
    # 5. verify all existing R1 ledger/restart states (BEFORE authorization)
    restart = _restart_scan_all(states)
    # 6. verify R1 human truth authorization
    if not gate("M3_S25_R1_TRUTH_AUTHORIZED"):
        raise RuntimeError("M3_S25_R1_TRUTH_AUTHORIZED is not YES")
    if gate("M3_S25_R1_ARM_A_AUTHORIZED") or gate("M3_S25_R1_ARM_B_AUTHORIZED"):
        raise RuntimeError(
            "M3-S25-R1-X: Arm gates must remain NO during the truth stage")
    # 7. construct pure execution plan (no side effects)
    plan = RT.truth_execution_plan(states)
    protocol_hash = sha(CFG / "m3s25r1_contract.json")
    by_sid = {s["state_id"]: s for s in states}
    for d in (TRUTH_DISC, TRUTH_CONF):
        d.mkdir(parents=True, exist_ok=True)

    def run_unit(unit, ledger, out_dir, payload_fn):
        result = run_trial_transactional(
            unit["unit_id"], out_dir / f"{unit['state_id']}.json",
            payload_fn, ledger_path=ledger,
            pre_hash_validator=lambda rec: None,
            base_entry={"samples": unit["samples"], "stream": ledger.name
                        .replace("_ledger.jsonl", "")})
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"M3-S25-R1-X: truth unit not durably COMPLETE: "
                f"{unit['unit_id']}: {result}; CONSUMED_INVALID policy in "
                "force; NO REPLAY")

    # 8. simulator calls: discovery 240 -> confirmation 240
    for unit in plan["discovery_units"]:
        row = by_sid[unit["state_id"]]
        out = TRUTH_DISC / f"{unit['state_id']}.json"
        rec = RT.verify_unit_fresh_or_verified(
            unit["unit_id"], out,
            [e for e in ledger_entries(TRUTH_LEDGERS["discovery"])
             if e.get("state_id") == unit["unit_id"]], record_file_hash)
        if rec is not None:
            continue
        run_unit(unit, TRUTH_LEDGERS["discovery"], TRUTH_DISC,
                 lambda u=unit, r=row, cid=row["config_id"]:
                 RT.discovery_payload(u, r, p_refs[cid], protocol_hash))
    for unit in plan["confirmation_units"]:
        row = by_sid[unit["state_id"]]
        out = TRUTH_CONF / f"{unit['state_id']}.json"
        rec = RT.verify_unit_fresh_or_verified(
            unit["unit_id"], out,
            [e for e in ledger_entries(TRUTH_LEDGERS["confirmation"])
             if e.get("state_id") == unit["unit_id"]], record_file_hash)
        if rec is not None:
            continue
        run_unit(unit, TRUTH_LEDGERS["confirmation"], TRUTH_CONF,
                 lambda u=unit, r=row, cid=row["config_id"]:
                 RT.confirmation_payload(u, r, p_refs[cid], protocol_hash))

    ledgers = {k: ledger_entries(v) for k, v in TRUTH_LEDGERS.items()}
    summary = RT.consumption_summary(ledgers)
    dump(SUM / "m3s25r1_truth_consumption.json", summary)
    if summary["total"]["actual"] != RT.TRUTH_BUDGET_PLANNED:
        raise RuntimeError(
            f"M3-S25-R1-X: truth consumption {summary['total']['actual']} != "
            f"planned {RT.TRUTH_BUDGET_PLANNED}")
    print("M3-S25-R1 truth execute: all units durable COMPLETE; "
          f"consumption total = {summary['total']['actual']:,}")
    # completion semantics (taskbook Sec. 23/24/26/28): truth assignment ->
    # inventory -> union pool -> panel freeze or PANEL-BLOCKED -> STOP
    selection = truth_panel()
    print(f"M3-S25-R1 truth stage terminus: {selection['PANEL']}; STOP")
    return summary


def truth_panel() -> dict:
    """Completion semantics ONLY after 480/480 durable COMPLETE."""
    ledgers = {k: ledger_entries(v) for k, v in TRUTH_LEDGERS.items()}
    required = {"discovery": N_STATES, "confirmation": N_STATES}
    for stream, n in required.items():
        comp = [e for e in ledgers[stream] if e.get("status") == "COMPLETE"]
        inv = [e for e in ledgers[stream]
               if e.get("status") == "CONSUMED_INVALID"]
        if len(comp) != n or inv:
            raise RuntimeError(
                f"M3-S25-R1-X: truth stage incomplete ({stream}: "
                f"{len(comp)}/{n}, consumed-invalid {len(inv)}); no truth "
                "assignment, no panel selection")
    conf_records, conf_hash = [], {}
    for e in (x for x in ledgers["confirmation"]
              if x.get("status") == "COMPLETE"):
        sid = e["state_id"].split("|", 1)[1]
        p = TRUTH_CONF / f"{sid}.json"
        if e.get("record_file_hash") and \
                record_file_hash(p) != e["record_file_hash"]:
            raise RuntimeError(
                f"M3-S25-R1-X: confirmation hash mismatch: {p}")
        rec = load(p)
        conf_records.append(rec)
        conf_hash[sid] = e["record_file_hash"]
    truth = RT.assign_truth(conf_records)
    dump(SUM / "m3s25r1_frozen_truth.json", {
        "recorded_at": now(), "n_states": len(truth),
        "composition": RT.truth_composition(truth),
        "source": "M3S25R1-CONFIRM durable records "
                  "(ALL_240_R1_CANDIDATES)"})
    states = verify_universe_sha_only()
    w_by_cid = {s["config_id"]: s for s in states}
    new_states = [{"state_id": s["state_id"], "config_id": s["config_id"],
                   "s2": s["s2"], "u": s["u"],
                   "rank": s["rank"], "source_stage": "M3-S25-R1",
                   "truth_artifact_hash": conf_hash[s["state_id"]]}
                  for s in states]
    exposed = [{"state_id": s["state_id"], "config_id": s["config_id"],
                "confirmed_truth": truth[s["state_id"]],
                "status": "TRUTH_EXPOSED_DEVELOPMENT"}
               for s in states]
    dump(SUM / "m3s25r1_truth_exposed_inventory.json", {
        "recorded_at": now(), "n": len(exposed), "states": exposed,
        "rule": "development_eligible = YES; "
                "untouched_confirmation_eligible = NO; retired from all "
                "future untouched confirmation use"})
    # union development pool (taskbook Sec. 24)
    parent_reg = load(CFG / "m3s25r1_parent_development_registry.json")
    old_states = [{"state_id": e["state_id"], "config_id": e["config_id"],
                   "s2": e["s2"],
                   "u": CAND.u_of(e["s2"],
                                  w_by_cid[e["config_id"]]["legality_s2_lo"]),
                   "rank": CAND.panel_rank(e["config_id"], e["state_id"]),
                   "source_stage": "M3-S2S",
                   "truth_artifact_hash": e["truth_record_file_hash"]}
                  for e in parent_reg["states"]]
    # the union pool's frozen truth covers BOTH generations
    full_truth = dict(truth)
    for e in parent_reg["states"]:
        full_truth[e["state_id"]] = e["confirmed_truth"]
    union = RT.union_development_pool(old_states, new_states)
    missing = [s["state_id"] for s in union if s["state_id"] not in full_truth]
    if missing:
        raise RuntimeError(
            f"M3-S25-R1-X: union states without frozen truth: {missing[:5]}")
    dump(SUM / "m3s25r1_development_union.json", {
        "recorded_at": now(), "n_old": len(old_states),
        "n_new": len(new_states), "n_union": len(union),
        "rule": "D_union = D_old u D_new (max 480)"})
    selection = RT.select_panel(union, full_truth)
    dump(SUM / "m3s25r1_panel_decision.json", selection)
    if selection["PANEL"] != "FROZEN":
        raise RuntimeError(
            f"M3-S25-R1-PANEL-BLOCKED: {selection.get('reason')}; STOP; "
            "no top-up, no relaxation (taskbook Sec. 27)")
    csvwrite(SUM / "m3s25r1_panel.csv",
             [{"state_id": s["state_id"], "source_stage": s["source_stage"],
               "truth": full_truth[s["state_id"]],
               "config_id": s["config_id"],
               "s2": s["s2"], "u": s["u"], "rank": s["rank"],
               "truth_artifact_hash": s["truth_artifact_hash"]}
              for s in selection["panel"]],
             ["state_id", "source_stage", "truth", "config_id", "s2", "u",
              "rank", "truth_artifact_hash"])
    dump(CFG / "m3s25r1_panel.json", {
        "panel_sha256": selection["panel_sha256"],
        "n_states": len(selection["panel"]),
        "n_configs": selection["n_configs"],
        "states": selection["panel"], "frozen": True})
    print(f"M3-S25-R1 truth panel: FROZEN ({len(selection['panel'])} states "
          f"/ {selection['n_configs']} configs, sha "
          f"{selection['panel_sha256'][:16]}...); STOP -- "
          "M3_S25_R1_ARM_A_AUTHORIZED must remain NO")
    return selection


# ==========================================================================
# M3-S25-R1-A0: Arm-A rebind & execution readiness (ZERO SAMPLING)
# ==========================================================================

def _panel_row_fields(r: dict) -> dict:
    return {"state_id": r["state_id"], "truth": r["truth"],
            "config_id": r["config_id"], "source_stage": r["source_stage"],
            "s2": float(r["s2"]), "u": float(r["u"]), "rank": r["rank"],
            "truth_artifact_hash": r["truth_artifact_hash"]}


def panel_truth_manifest_stage() -> dict:
    """A0 item 2: tracked evaluation-only truth manifest for the FROZEN
    panel (never modified; never used during Arm-A sampling; sealed until
    960/960 trials are durable COMPLETE)."""
    panel = load(PANEL_JSON)
    rows = csvread(SUM / "m3s25r1_panel.csv")
    by_sid = {r["state_id"]: r for r in rows}
    entries = []
    for s in panel["states"]:
        r = by_sid.get(s["state_id"])
        if r is None:
            raise RuntimeError(
                f"M3-S25-R1-A0-X: panel state missing from panel.csv: "
                f"{s['state_id']}")
        entries.append(_panel_row_fields(r))
    manifest = {
        "schema_version": "m3s25r1_panel_truth_manifest_v1",
        "role": "evaluation-only; SEALED until 960/960 Arm-A trials are "
                "durable COMPLETE; never used during Arm-A sampling",
        "panel_body_sha256": panel["panel_sha256"],
        "panel_file_sha256": sha(PANEL_JSON),
        "n_states": len(entries),
        "states": entries,
    }
    data = dump_json(PANEL_TRUTH_MANIFEST, manifest)
    audit = verify_panel_truth_manifest()
    dump(OUT / "m3s25r1_panel_truth_manifest_audit.json", {
        "recorded_at": now(), **audit,
        "manifest_sha256": sha_bytes(data)})
    print(f"M3-S25-R1-A0 panel truth manifest: {audit['n_states']} states, "
          f"composition {audit['composition']}, "
          f"source mix {audit['source_mix']} (sha {sha_bytes(data)[:16]}...)")
    return manifest


def verify_panel_truth_manifest() -> dict:
    """Mechanical verification (A0 item 2): identity, composition,
    diversity, source mix, SHRINK origin; binding to both panel SHAs."""
    panel = load(PANEL_JSON)
    m = load(PANEL_TRUTH_MANIFEST)
    from collections import Counter
    ids = [s["state_id"] for s in m["states"]]
    panel_ids = [s["state_id"] for s in panel["states"]]
    comp = Counter(s["truth"] for s in m["states"])
    srcs = Counter(s["source_stage"] for s in m["states"])
    shrink_sources = {s["source_stage"] for s in m["states"]
                      if s["truth"] == "SHRINK"}
    checks = {
        "n_unique_states": len(set(ids)) == 120 and len(ids) == 120,
        "exact_panel_identity": sorted(ids) == sorted(panel_ids),
        "composition_30_30_30_30": dict(comp) == {"WIDEN": 30, "SHRINK": 30,
                                                  "HOLD": 30,
                                                  "AMBIGUOUS": 30},
        "distinct_configs_30": len({s["config_id"]
                                    for s in m["states"]}) == 30,
        "source_mix_r1_83_s2s_37": dict(srcs) == {"M3-S25-R1": 83,
                                                  "M3-S2S": 37},
        "all_shrink_from_r1": shrink_sources == {"M3-S25-R1"},
        "panel_body_sha_bound":
            m["panel_body_sha256"] == panel["panel_sha256"]
            == AA.FROZEN_PANEL_SHA,
        "panel_file_sha_bound": m["panel_file_sha256"]
        == sha(PANEL_JSON),
        "required_fields": all(
            {"state_id", "truth", "config_id", "source_stage", "s2", "u",
             "rank", "truth_artifact_hash"} <= set(s)
            for s in m["states"]),
    }
    if not all(checks.values()):
        raise RuntimeError(
            f"M3-S25-R1-A0-X: panel truth manifest verification failed: "
            f"{[k for k, v in checks.items() if not v]}")
    return {"PANEL_TRUTH_MANIFEST_AUDIT": "PASS", "n_states": 120,
            "composition": dict(comp), "source_mix": dict(srcs),
            "checks": checks}


def _parent_contract_hashes() -> dict:
    return {name: sha(ROOT / "configs/phase_m3s2s" / name)
            for name in PARENT_CONTRACTS}


def arm_a_contracts_stage() -> dict:
    """A0 item 3: rebind the frozen parent Arm-A contracts to the R1
    panel (no scientific retuning) + freeze the 960-unit seed manifest."""
    import hyptraj.m3s2s.instrumentation as IN
    panel = load(PANEL_JSON)
    states = panel["states"]
    if panel["panel_sha256"] != AA.FROZEN_PANEL_SHA:
        raise RuntimeError("M3-S25-R1-A0-X: panel SHA drift")
    plan = AA.arm_a_seed_plan(states)
    dump(ARM_A_SEED_MANIFEST, {
        "schema_version": "m3s25r1_arm_a_seed_manifest_v1",
        "frozen_before_first_simulator_call": True,
        **{k: plan[k] for k in ("namespace", "planned_seeds", "units",
                                "n_units", "n_trials", "budget")}})
    # collision audit (A0.1 item 6): type-consistent per-stream pools;
    # integer seed VALUES vs integer pools, seed_key TUPLES vs tuple pools
    s2s_arm_a = set(load(
        ROOT / "configs/phase_m3s2s/m3s2s_seed_manifest.json")
        .get("planned_seeds", {}).values())
    s2s_truth = {int(u["seed_key"][0]) for u in load(
        ROOT / "configs/phase_m3s2s/m3s2s_truth_seed_manifest.json")
        .get("units", [])}
    r1_truth = {int(u["seed_key"][0]) for u in load(
        CFG / "m3s25r1_truth_seed_manifest.json")["units"]}
    csv_history = _prior_recorded_seeds()
    cf1n_ints: set = set()
    for name in ("m3cf1n_pref_seeds.json", "m3cf1n_discovery_seeds.json",
                 "m3cf1n_confirmation_seeds.json"):
        d = load(ROOT / "configs/phase_m3cf1n" / name)
        for v in d.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "seed_key" in item:
                        cf1n_ints.add(int(item["seed_key"][0]))
                    elif isinstance(item, list) and item:
                        cf1n_ints.add(int(item[0]))
    pools = {"m3s2s_arm_a_candidate_seeds": s2s_arm_a,
             "m3s2s_truth_seeds": s2s_truth,
             "m3s25r1_truth_seeds": r1_truth,
             "recorded_historical_seed_pools": csv_history,
             "m3cf1n_seed_pools": cf1n_ints}
    truth_key_pools = {
        "m3s2s_truth_seed_keys": {tuple(u["seed_key"]) for u in load(
            ROOT / "configs/phase_m3s2s/m3s2s_truth_seed_manifest.json")
            .get("units", [])},
        "m3s25r1_truth_seed_keys": {tuple(u["seed_key"]) for u in load(
            CFG / "m3s25r1_truth_seed_manifest.json")["units"]}}
    audit = AA.seed_collision_audit(plan, pools, truth_key_pools)
    dump(OUT / "m3s25r1_arm_a_seed_audit.json", {
        "recorded_at": now(), **audit})
    contract = {
        "schema_version": "m3s25r1_arm_a_contract_v1",
        "stage": "M3-S25-R1-A0",
        "rebind": "frozen M3-S2S Arm-A contracts inherited VERBATIM to the "
                  "R1 panel; no scientific retuning",
        "inherited_parent_contract_sha256": _parent_contract_hashes(),
        "estimator": "hyptraj.m3d.adaptation.gradient_decision (unmodified; "
                     "bit-exact crosscheck enforced on every trial)",
        "alpha_p": AA.ALPHA_P,
        "S1_formula": "abs(g_hat) / ((g_ci_high-g_ci_low)/(2*"
                      "1.959963984540054))",
        "S1_threshold_frozen": AA.S1_THRESHOLD,
        "panel": {"n_states": 120,
                  "panel_body_sha256": panel["panel_sha256"],
                  "panel_file_sha256": sha(PANEL_JSON)},
        "trials": {"states": AA.N_STATES, "replicates": AA.REPLICATES,
                   "samples_per_trial": AA.N_SAMPLES, "n_trials":
                       AA.N_TRIALS,
                   "ARM_A_BUDGET": AA.BUDGET, "no_topup": True},
        "namespace": AA.ARM_A_NAMESPACE,
        "seed_manifest": "configs/phase_m3s25r1/"
                         "m3s25r1_arm_a_seed_manifest.json",
        "seed_audit": audit,
        "instrumentation": {
            "schema": IN.INSTRUMENTATION_SCHEMA_VERSION,
            "N_BOOTSTRAP": IN.audit_estimator_source()["checks"]
            ["N_BOOTSTRAP_actual"],
            "sidecar_arrays": ["a_vec", "resp", "sq", "strata",
                               "bootstrap_g"],
            "lossless": True},
        "feature_contract": "parent m3s2s feature family (bootstrap "
                            "stability + robust vs classical + influence "
                            "concentration + event/ESS diagnostics + "
                            "practical margin), per-trial rows only",
        "model_contract": {
            "primary_candidates": ["B0_frozen_S1"]
            + list(AE.MODEL_FEATURES.keys()),
            "grids": {"logistic": AA.LOGISTIC_GRID, "gbdt": AA.GBDT_GRID},
            "cv": "outer GroupKFold(5) / inner GroupKFold(4), "
                  "groups = config_id; no test-fold threshold/delta tuning",
            "delta_quantiles": list(AA.DELTA_QUANTILES),
            "delta_rule": "delta = q-quantile of |g_hat| over outer-train "
                          "only; selected via inner grouped OOF"},
        "safety_gates": AA.GATES,
        "improvement_criterion": AA.IMPROVEMENT,
        "b1_comparator": {
            "source": "ML0-style aggregate GBDT baseline (ML0 B3)",
            "features": AE.ML0_B1_FEATURES,
            "grid": AA.GBDT_GRID,
            "ml0_feature_contract_sha256":
                sha(ROOT / "src/hyptraj/m3ml0/features.py"),
            "ml0_model_grid_sha256":
                sha(ROOT / "src/hyptraj/m3ml0/models.py"),
            "curvature_c_route": "curvature_c = online frozen config metadata "
                                 "persisted in every trial record "
                                 "(truth-free)"},
        "success_eligibility": {
            "comparators_only": ["B0_frozen_S1",
                                 "B1_aggregate_gbdt_baseline"],
            "may_trigger_success": list(AE.SUCCESS_ELIGIBLE),
            "rule": "if only B1 is compliant/improved but A1-A4 are not, "
                    "the verdict remains M3-S25-R1-B-GATE"},
        "secondary_metrics": {
            "metrics": ["roc_auc", "pr_auc", "brier", "ece"],
            "rows": "scored OOF rows of the nested CV (oof_prob "
                    "preserved)",
            "binding": "report-only; never affects the primary verdict"},
        "verdicts": {"success": "M3-S25-R1-A",
                     "b_gate": "M3-S25-R1-B-GATE",
                     "failure": "M3-S25-R1-X"},
        "truth_manifest_rule": "evaluation-only; SEALED until 960/960 "
                               "durable COMPLETE; never in the Arm-A "
                               "sampling execution view",
        "persistence": "STARTED -> 20k simulator -> aggregate gradient "
                       "record -> sidecar -> sidecar SHA verify -> record "
                       "SHA verify -> COMPLETE; restart requires exactly "
                       "one STARTED + one COMPLETE + both hashes",
    }
    data = dump_json(ARM_A_CONTRACT, contract)
    print(f"M3-S25-R1-A0 Arm-A contract frozen "
          f"(sha {sha_bytes(data)[:16]}...); seeds {audit['units']} unique, "
          "0 collisions")
    return contract


def _verify_frozen_arm_a_inputs() -> dict:
    got_universe = sha_bytes(UNIVERSE.read_bytes())
    if got_universe != EXPECTED_UNIVERSE_SHA:
        raise RuntimeError("M3-S25-R1-A0-X: universe SHA drift")
    got_contract = sha_bytes((CFG / "m3s25r1_contract.json").read_bytes())
    if got_contract != EXPECTED_CONTRACT_SHA:
        raise RuntimeError("M3-S25-R1-A0-X: contract SHA drift")
    got_panel = sha_bytes(PANEL_JSON.read_bytes())
    # A0.1 item 2: the frozen panel FILE sha is enforced at runtime; the
    # stored panel_sha256 field alone is NOT trusted.  The pin must also
    # equal the rebind contract's recorded panel_file_sha256.
    contract = load(ARM_A_CONTRACT)
    if got_panel != EXPECTED_PANEL_FILE_SHA or             contract["panel"]["panel_file_sha256"] != got_panel:
        raise RuntimeError(
            "M3-S25-R1-X: frozen panel FILE sha drift: "
            f"{got_panel} != {EXPECTED_PANEL_FILE_SHA}")
    manifest_sha = sha_bytes(PANEL_TRUTH_MANIFEST.read_bytes())
    if PANEL_TRUTH_MANIFEST_PIN != "PENDING-SET-AFTER-GENERATION" \
            and manifest_sha != PANEL_TRUTH_MANIFEST_PIN:
        raise RuntimeError("M3-S25-R1-A0-X: panel truth manifest SHA drift")
    contract_sha = sha_bytes(ARM_A_CONTRACT.read_bytes())
    if ARM_A_CONTRACT_PIN != "PENDING-SET-AFTER-GENERATION" \
            and contract_sha != ARM_A_CONTRACT_PIN:
        raise RuntimeError("M3-S25-R1-A0-X: Arm-A contract SHA drift")
    seeds_sha = sha_bytes(ARM_A_SEED_MANIFEST.read_bytes())
    if ARM_A_SEED_MANIFEST_PIN != "PENDING-SET-AFTER-GENERATION" \
            and seeds_sha != ARM_A_SEED_MANIFEST_PIN:
        raise RuntimeError("M3-S25-R1-A0-X: Arm-A seed manifest SHA drift")
    return {"universe_sha256": got_universe,
            "contract_sha256": got_contract,
            "panel_file_sha256": got_panel,
            "panel_truth_manifest_sha256": manifest_sha,
            "arm_a_contract_sha256": contract_sha,
            "arm_a_seed_manifest_sha256": seeds_sha}


def arm_a_preflight() -> dict:
    """A0 item 6: the full zero-sampling Arm-A readiness checklist."""
    checks = {}
    head = git_commit()
    for name, target in (("parent", PARENT_HEAD),
                         ("truth_terminal", TRUTH_TERMINAL_HEAD)):
        checks[f"{name}_head_ancestor"] = subprocess.run(
            ["git", "merge-base", "--is-ancestor", target, head],
            cwd=ROOT, capture_output=True).returncode == 0
    decision = load(SUM / "m3s25r1_panel_decision.json")
    checks["truth_stage_panel_frozen"] = decision.get("PANEL") == "FROZEN"
    panel = load(PANEL_JSON)
    checks["frozen_panel_sha"] = (panel.get("panel_sha256")
                                  == AA.FROZEN_PANEL_SHA
                                  and panel.get("frozen") is True)
    pins = _verify_frozen_arm_a_inputs()
    ptm = verify_panel_truth_manifest()
    checks["panel_truth_manifest"] = \
        ptm["PANEL_TRUTH_MANIFEST_AUDIT"] == "PASS"
    checks["panel_identity_120"] = len({s["state_id"]
                                        for s in panel["states"]}) == 120
    seeds_cfg = load(ARM_A_SEED_MANIFEST)
    audit = load(OUT / "m3s25r1_arm_a_seed_audit.json")
    checks["seeds_960_unique"] = (seeds_cfg["n_units"] == 960
                                  and audit["unique_seeds"] == 960)
    checks["seed_collisions_zero"] = (audit["historical_collision"] == 0
                                      and audit["truth_stream_collision"]
                                      == 0)
    reserve = {r["state_id"] for r in csvread(
        OUT / "m3s25r1_protected_reserve_18.csv")}
    panel_ids = {s["state_id"] for s in panel["states"]}
    checks["reserve_18_untouched"] = len(reserve) == 18 \
        and not (reserve & panel_ids)

    def _empty(d: Path) -> bool:
        return not d.exists() or not any(d.iterdir())

    checks["destination_empty"] = (_empty(ARM_A_TRIALS)
                                   and not ARM_A_LEDGER.exists()
                                   and not ARM_A_EVAL.exists())
    disk = shutil.disk_usage(ROOT)
    max_path = 0
    for s in panel["states"]:
        # mirror the REAL execute layout exactly: dir slug = bounded_slug
        # (state_id); temp basename = bounded_temp_basename(unit slug, uuid)
        from hyptraj.m3wa1r.persistence import safen_run_uuid
        dir_slug = bounded_slug(s["state_id"])
        unit_slug = bounded_slug(f"{s['state_id']}|rep7")
        temp_name = bounded_temp_basename(unit_slug,
                                          safen_run_uuid("M3-S25-R1-A0"))
        rec = ARM_A_TRIALS / dir_slug / "rep7.json"
        side = ARM_A_TRIALS / dir_slug / "rep7_instrumentation.npz"
        temp = ARM_A_TRIALS / dir_slug / temp_name
        max_path = max(max_path, len(str(rec)), len(str(side)),
                       len(str(temp)))
    checks["path_length_ok"] = max_path <= FULL_PATH_LIMIT
    checks["disk_ok"] = disk.free > 2_000_000_000
    panel_rows = [{"_state_id": s["state_id"], "_config_id": s["config_id"],
                   "_truth": s["truth"]}
                  for s in load(PANEL_TRUTH_MANIFEST)["states"]]
    feas = AE.split_feasibility(panel_rows)
    checks["groupkfold_feasible"] = feas["PASS"]
    hashes = _parent_contract_hashes()
    missing = [n for n in PARENT_CONTRACTS
               if not (ROOT / "configs/phase_m3s2s" / n).exists()]
    checks["inherited_contract_hashes"] = not missing and all(hashes.values())
    checks["arm_a_gate_no"] = not gate("M3_S25_R1_ARM_A_AUTHORIZED")
    checks["arm_b_gate_no"] = not gate("M3_S25_R1_ARM_B_AUTHORIZED")
    checks["truth_gate_closed"] = not gate("M3_S25_R1_TRUTH_AUTHORIZED")
    failed = sorted(k for k, v in checks.items() if not v)
    report = {
        "recorded_at": now(), "simulator_calls": 0, "samples": 0,
        "checks": checks, "failed_checks": failed,
        "frozen_pins": pins,
        "groupkfold_feasibility": feas,
        "parent_contract_hashes": hashes,
        "arm_a_budget": AA.BUDGET,
        "PREFLIGHT_VERDICT": "PASS" if not failed else "FAIL",
        "overall": ("ARM-A EXECUTION-READY (gates remain NO; awaiting "
                    "human authorization)" if not failed else
                    "ARM-A NOT EXECUTION-READY: " + ", ".join(failed)),
    }
    dump(OUT / "m3s25r1_arm_a_preflight.json", report)
    print(f"M3-S25-R1-A0 arm_a preflight: {report['PREFLIGHT_VERDICT']} "
          f"({len(checks) - len(failed)}/{len(checks)} checks PASS)")
    return report


def verify_frozen_arm_a_preflight_pass() -> dict:
    pf = load(OUT / "m3s25r1_arm_a_preflight.json")
    if pf.get("PREFLIGHT_VERDICT") != "PASS":
        raise RuntimeError(
            f"M3-S25-R1-X: frozen Arm-A preflight verdict is "
            f"{pf.get('PREFLIGHT_VERDICT')!r}; execution not authorized; "
            "STOP")
    return pf


def _arm_a_restart_scan(panel_states: list[dict]) -> dict:
    entries = ledger_entries(ARM_A_LEDGER) \
        if Path(ARM_A_LEDGER).exists() else []
    summary = {"fresh": 0, "complete_verified": 0}
    for s in panel_states:
        slug_dir = ARM_A_TRIALS / bounded_slug(s["state_id"])
        for rep in range(AA.REPLICATES):
            unit_id = f"{s['state_id']}|rep{rep}"
            rec_p = slug_dir / f"rep{rep}.json"
            side_p = slug_dir / f"rep{rep}_instrumentation.npz"
            rec = AA.verify_arm_a_trial_fresh_or_verified(
                unit_id, rec_p, side_p, entries, record_file_hash,
                record_file_hash)
            if rec is None:
                summary["fresh"] += 1
            else:
                summary["complete_verified"] += 1
    return summary


def arm_a_execute() -> dict:
    """GATED: requires M3_S25_R1_ARM_A_AUTHORIZED: YES.  Fail-closed
    ordering: truth terminal -> frozen pins -> restart scan -> gates ->
    pure plan -> simulator.  Zero writes before the gate."""
    import hyptraj.m3d.benchmark_states as BS
    decision = load(SUM / "m3s25r1_panel_decision.json")
    if decision.get("PANEL") != "FROZEN":
        raise RuntimeError("M3-S25-R1-X: truth terminal is not PANEL-FROZEN")
    if gate("M3_S25_R1_TRUTH_AUTHORIZED"):
        raise RuntimeError(
            "M3-S25-R1-X: truth gate must be CLOSED/EXERCISED during Arm A")
    panel = load(PANEL_JSON)
    if panel["panel_sha256"] != AA.FROZEN_PANEL_SHA:
        raise RuntimeError("M3-S25-R1-X: panel SHA drift")
    _verify_frozen_arm_a_inputs()
    seeds_cfg = load(ARM_A_SEED_MANIFEST)
    panel_states = panel["states"]
    restart = _arm_a_restart_scan(panel_states)
    if not gate("M3_S25_R1_ARM_A_AUTHORIZED"):
        raise RuntimeError("M3_S25_R1_ARM_A_AUTHORIZED is not YES")
    if gate("M3_S25_R1_ARM_B_AUTHORIZED"):
        raise RuntimeError("M3-S25-R1-X: Arm B must remain NO during Arm A")
    contract_shas = {"arm_a_contract": sha(ARM_A_CONTRACT),
                     "stage_contract": sha(CFG / "m3s25r1_contract.json"),
                     "panel_truth_manifest": sha(PANEL_TRUTH_MANIFEST)}
    plan_seeds = seeds_cfg["planned_seeds"]
    ARM_A_TRIALS.mkdir(parents=True, exist_ok=True)

    def run_trial(s, rep):
        unit_id = f"{s['state_id']}|rep{rep}"
        slug_dir = ARM_A_TRIALS / bounded_slug(s["state_id"])
        rec_p = slug_dir / f"rep{rep}.json"
        side_p = slug_dir / f"rep{rep}_instrumentation.npz"
        rec = AA.verify_arm_a_trial_fresh_or_verified(
            unit_id, rec_p, side_p, ledger_entries(ARM_A_LEDGER),
            record_file_hash, record_file_hash)
        if rec is not None:
            return

        def compute():
            bench = VR.resolve_bench_config(s["config_id"])
            st = BS.assemble_state(bench, float(s["s2"]),
                                   short_config=s["config_id"])
            if isinstance(st, dict):
                raise RuntimeError(
                    f"M3-S25-R1-X: assembly failed for {s['state_id']}")
            record, arrays = AA.arm_a_trial(
                st, plan_seeds[unit_id], s["state_id"], rep,
                s["config_id"], float(s["s2"]), contract_shas)
            record["recorded_at"] = now()
            # A0.1 item 3: transactional sidecar durability (temp -> write
            # -> flush -> fsync -> atomic rename -> dir fsync -> SHA verify)
            record["instrumentation_sha256"] =                 AA.write_sidecar_transactional(side_p, arrays)
            return record

        def validate(payload):
            if payload.get("schema") != AA.TRIAL_SCHEMA:
                raise RuntimeError("M3-S25-R1-X: trial schema drift")
            if not payload.get("instrumentation_sha256"):
                raise RuntimeError("M3-S25-R1-X: sidecar hash missing")
            if record_file_hash(side_p) != payload["instrumentation_sha256"]:
                raise RuntimeError("M3-S25-R1-X: sidecar hash mismatch")
            if "truth" in payload or payload.get("confirmed_truth") \
                    or payload.get("corrected_class"):
                raise RuntimeError(
                    "M3-S25-R1-X: truth label leaked into the execution "
                    "view")

        result = run_trial_transactional(
            unit_id, rec_p, compute, ledger_path=ARM_A_LEDGER,
            pre_hash_validator=validate,
            base_entry={"panel_state_id": s["state_id"], "rep_id": rep,
                        "config_id": s["config_id"],
                        "seed_namespace": AA.ARM_A_NAMESPACE,
                        "seed": plan_seeds[unit_id],
                        "samples": AA.N_SAMPLES,
                        "stream": "arm_a_gradient"})
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"M3-S25-R1-X: Arm-A trial not durably COMPLETE: {unit_id}: "
                f"{result}; CONSUMED_INVALID policy in force; NO REPLAY")

    for s in panel_states:
        for rep in range(AA.REPLICATES):
            run_trial(s, rep)
    entries = ledger_entries(ARM_A_LEDGER)
    counts = Counter(e.get("status") for e in entries)
    complete = counts.get("COMPLETE", 0)
    invalid = counts.get("CONSUMED_INVALID", 0)
    if invalid or complete != AA.N_TRIALS:
        raise RuntimeError(
            f"M3-S25-R1-X: Arm-A incomplete ({complete}/960, invalid "
            f"{invalid}); STOP")
    consumed = sum(AA.N_SAMPLES for e in entries
                   if e.get("status") == "COMPLETE")
    summary = {"n_trials": complete, "CONSUMED_INVALID": invalid,
               "actual_samples": consumed, "planned": AA.BUDGET,
               "topup": 0}
    dump(SUM / "m3s25r1_arm_a_consumption.json", summary)
    print(f"M3-S25-R1 Arm-A execute: {complete}/960 durable COMPLETE; "
          f"{consumed:,} samples; STOP -- evaluation is a separate stage")
    return summary


def arm_a_evaluate() -> dict:
    """ONLY after 960/960 durable COMPLETE: unseal the panel truth
    manifest and run the frozen parent development comparison."""
    verify_frozen_arm_a_preflight_pass()
    _verify_frozen_arm_a_inputs()
    entries = ledger_entries(ARM_A_LEDGER) \
        if Path(ARM_A_LEDGER).exists() else []
    counts = Counter(e.get("status") for e in entries)
    complete = counts.get("COMPLETE", 0)
    invalid = counts.get("CONSUMED_INVALID", 0)
    if invalid or complete != AA.N_TRIALS:
        raise RuntimeError(
            f"M3-S25-R1-X: evaluation requires 960/960 durable COMPLETE "
            f"(got {complete}, invalid {invalid}); STOP")
    manifest_sha = sha(PANEL_TRUTH_MANIFEST)
    if PANEL_TRUTH_MANIFEST_PIN != "PENDING-SET-AFTER-GENERATION" \
            and manifest_sha != PANEL_TRUTH_MANIFEST_PIN:
        raise RuntimeError("M3-S25-R1-X: truth manifest SHA drift")
    manifest = load(PANEL_TRUTH_MANIFEST)
    truth_by_state = {s["state_id"]: s["truth"] for s in manifest["states"]}
    records, sidecars = [], []
    for s in load(PANEL_JSON)["states"]:
        slug_dir = ARM_A_TRIALS / bounded_slug(s["state_id"])
        for rep in range(AA.REPLICATES):
            unit_id = f"{s['state_id']}|rep{rep}"
            rec = AA.verify_arm_a_trial_fresh_or_verified(
                unit_id, slug_dir / f"rep{rep}.json",
                slug_dir / f"rep{rep}_instrumentation.npz", entries,
                record_file_hash, record_file_hash)
            if rec is None:
                raise RuntimeError(
                    f"M3-S25-R1-X: trial missing at evaluation: {unit_id}")
            records.append(rec)
            with np.load(slug_dir / f"rep{rep}_instrumentation.npz") as z:
                sidecars.append({k: z[k] for k in z.files})
    results = AE.run_comparison(records, sidecars, truth_by_state)
    verdict = AE.verdict(results, complete, invalid)
    out = {"recorded_at": now(),
           "truth_manifest_unsealed": {"sha256": manifest_sha,
                                       "after_complete_960": True},
           "results": results, "verdict": verdict}
    dump(ARM_A_EVAL, out)
    print(f"M3-S25-R1 Arm-A evaluate: VERDICT = {verdict['VERDICT']} "
          f"({verdict.get('compliant', [])}); STOP")
    return out




# ==========================================================================
# M3-S25-R1-A1R0: Replacement Arm-A preregistration (ZERO SAMPLING)
# ==========================================================================

def a1r_retired_stream_stage() -> dict:
    """A1R0 item 2: freeze the failed old Arm-A stream as RETIRED
    evidence (tracked).  All 960 old logical units are RETIRED FROM
    REPLACEMENT; the old ledger/artifacts are preserved verbatim."""
    old_manifest = load(ARM_A_SEED_MANIFEST)
    old_ledger = ledger_entries(ARM_A_LEDGER) \
        if Path(ARM_A_LEDGER).exists() else []
    consumed = [e for e in old_ledger if e.get("status") == "CONSUMED_INVALID"]
    completes = [e for e in old_ledger if e.get("status") == "COMPLETE"]
    started = [e for e in old_ledger if e.get("status") == "STARTED"]
    if len(consumed) != 1 or completes or len(started) != 1:
        raise RuntimeError(
            "M3-S25-R1-A1R0-X: old Arm-A ledger state drift "
            f"(consumed={len(consumed)}, complete={len(completes)}, "
            f"started={len(started)})")
    consumed_unit = consumed[0]["state_id"]
    if consumed_unit not in old_manifest["planned_seeds"]:
        raise RuntimeError("M3-S25-R1-A1R0-X: consumed unit unknown to the "
                           "old seed manifest")
    units = []
    for unit_id, seed_value in sorted(old_manifest["planned_seeds"].items()):
        status = ("CONSUMED_INVALID_20K" if unit_id == consumed_unit
                  else "RETIRED_FRESH_NEVER_STARTED")
        units.append({"unit_id": unit_id, "seed": int(seed_value),
                      "seed_key": [int(seed_value), 42424], "status": status})
    record = {
        "schema_version": "m3s25r1_a1r_retired_stream_v1",
        "old_stage": "M3-S25-R1 Arm-A",
        "old_terminal": "M3-S25-R1-X",
        "old_terminal_head": OLD_ARM_A_TERMINAL_HEAD,
        "old_arm_a_seed_manifest_sha256":
            sha_bytes(ARM_A_SEED_MANIFEST.read_bytes()),
        "old_incident_report_sha256":
            sha(DOC / "M3_S25_R1_Arm_A_Incident_Report.md"),
        "old_ledger_path": ARM_A_LEDGER.relative_to(ROOT).as_posix(),
        "old_ledger_sha256_expected": sha_bytes(ARM_A_LEDGER.read_bytes()),
        "consumed_unit": {
            "unit_id": consumed_unit,
            "seed": int(old_manifest["planned_seeds"][consumed_unit]),
            "seed_key": [int(old_manifest["planned_seeds"][consumed_unit]),
                         42424],
            "samples_consumed": 20000},
        "counts": {"total_units": 960, "consumed_invalid": 1,
                   "complete": 0, "never_started": 959},
        "rule": "logical unit_id slots intentionally repeat because "
                "A1R reruns the same frozen 120 x 8 design; the "
                "forbidden reuse is old seed values, old seed keys, old "
                "artifacts and old scientific realizations/data -- never "
                "unit_id naming; the old ledger/artifacts are preserved "
                "verbatim and never reused, truncated, ignored or "
                "reinterpreted",
        "units": units,
    }
    data = dump_json(A1R_RETIRED, record)
    dump(OUT / "m3s25r1_a1r_retired_stream_audit.json", {
        "recorded_at": now(),
        "retired_stream_sha256": sha_bytes(data),
        **record["counts"]})
    print(f"M3-S25-R1-A1R0 retired stream frozen: 960 units retired "
          f"(1 consumed / 959 fresh), sha {sha_bytes(data)[:16]}...")
    return record


def a1r_seed_manifest_stage() -> dict:
    """A1R0 item 5: an entirely NEW 960-unit seed stream under the new
    M3-S25-R1-A1R-GRAD namespace; zero collisions against the retired
    old Arm-A stream, R1 truth seeds, S2S Arm-A/truth seeds, CF1N and all
    recorded historical scientific streams."""
    retired = load(A1R_RETIRED)
    old_values = {u["seed"] for u in retired["units"]}
    old_keys = {tuple(u["seed_key"]) for u in retired["units"]}
    panel_states = load(PANEL_JSON)["states"]
    plan = AA.arm_a_seed_plan(panel_states, namespace=A1R_NAMESPACE)
    new_vals = set(plan["planned_seeds"].values())
    if new_vals & old_values:
        raise RuntimeError(
            "M3-S25-R1-A1R0-X: replacement seeds overlap the RETIRED old "
            f"Arm-A stream: {sorted(new_vals & old_values)[:5]}")
    dump(A1R_SEED_MANIFEST, {
        "schema_version": "m3s25r1_a1r_seed_manifest_v1",
        "frozen_before_first_simulator_call": True,
        "old_stream_exclusion": {
            "retired_stream": "configs/phase_m3s25r1/"
                              "m3s25r1_a1r_retired_stream.json",
            "old_values_overlap": 0,
            "rule": "no old Arm-A unit or seed may appear in A1R"},
        **{k: plan[k] for k in ("namespace", "planned_seeds", "units",
                                "n_units", "n_trials", "budget")}})
    # typed per-stream collision audit (incl. the retired pool)
    s2s_arm_a = set(load(
        ROOT / "configs/phase_m3s2s/m3s2s_seed_manifest.json")
        .get("planned_seeds", {}).values())
    s2s_truth = {int(u["seed_key"][0]) for u in load(
        ROOT / "configs/phase_m3s2s/m3s2s_truth_seed_manifest.json")
        .get("units", [])}
    r1_truth = {int(u["seed_key"][0]) for u in load(
        CFG / "m3s25r1_truth_seed_manifest.json")["units"]}
    csv_history = _prior_recorded_seeds()
    cf1n_ints = set()
    for name in ("m3cf1n_pref_seeds.json", "m3cf1n_discovery_seeds.json",
                 "m3cf1n_confirmation_seeds.json"):
        d = load(ROOT / "configs/phase_m3cf1n" / name)
        for v in d.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "seed_key" in item:
                        cf1n_ints.add(int(item["seed_key"][0]))
                    elif isinstance(item, list) and item:
                        cf1n_ints.add(int(item[0]))
    pools = {"retired_old_arm_a_seeds": old_values,
             "m3s2s_arm_a_candidate_seeds": s2s_arm_a,
             "m3s2s_truth_seeds": s2s_truth,
             "m3s25r1_truth_seeds": r1_truth,
             "recorded_historical_seed_pools": csv_history,
             "m3cf1n_seed_pools": cf1n_ints}
    truth_key_pools = {
        "m3s25r1_truth_seed_keys": {tuple(u["seed_key"]) for u in load(
            CFG / "m3s25r1_truth_seed_manifest.json")["units"]},
        "retired_old_arm_a_seed_keys": old_keys}
    audit = AA.seed_collision_audit(plan, pools, truth_key_pools)
    dump(OUT / "m3s25r1_a1r_seed_audit.json", {"recorded_at": now(), **audit})
    print(f"M3-S25-R1-A1R0 seeds: 960 new units under {A1R_NAMESPACE}, "
          "0 collisions (incl. the retired old stream)")
    return plan


def a1r_contract_stage() -> dict:
    """A1R0 items 3/4/6/7: the replacement contract -- the SAME frozen
    scientific panel and contracts (inherited by exact SHA), the
    corrected instrumentation implementation, separate persistence
    paths, the replacement budget with cumulative accounting, and the
    A1R-local terminal names."""
    a0_contract = load(ARM_A_CONTRACT)
    panel = load(PANEL_JSON)
    old_ledger_sha = sha_bytes(ARM_A_LEDGER.read_bytes())
    retired_sha = sha_bytes(A1R_RETIRED.read_bytes())
    contract = {
        "schema_version": "m3s25r1_a1r_contract_v1",
        "stage": "M3-S25-R1-A1R",
        "parent_terminal": "M3-S25-R1-X (old Arm-A stage, PERMANENT)",
        "parent_terminal_head": OLD_ARM_A_TERMINAL_HEAD,
        "scientific_inheritance": {
            "rule": "SAME frozen scientific panel and contracts, "
                    "byte-identical; no truth resampling, no panel "
                    "reselection",
            "panel_body_sha256": panel["panel_sha256"],
            "panel_file_sha256": sha(PANEL_JSON),
            "panel_truth_manifest_sha256": sha(PANEL_TRUTH_MANIFEST),
            "a0_rebind_contract_sha256":
                sha_bytes(ARM_A_CONTRACT.read_bytes()),
            "inherited_parent_contract_sha256": _parent_contract_hashes(),
            "estimator": a0_contract["estimator"],
            "alpha_p": AA.ALPHA_P,
            "S1_threshold_frozen": AA.S1_THRESHOLD,
            "feature_families": a0_contract["feature_contract"],
            "b1_comparator": a0_contract["b1_comparator"],
            "model_grids": a0_contract["model_contract"]["grids"],
            "cv": a0_contract["model_contract"]["cv"],
            "safety_gates": AA.GATES,
            "improvement_criterion": AA.IMPROVEMENT,
            "arm_b_rules": "unchanged; never authorized with Arm A",
        },
        "corrected_instrumentation": {
            "fix": "post-incident A0.2 correction: CI bounds come from "
                   "the frozen stratified_bootstrap_gradient_ci on the "
                   "identical inputs (bit-identical to gradient_decision's "
                   "internal call); the replicate capture loop is "
                   "sidecar-only",
            "crosscheck": "unmodified gradient_decision bit-exact "
                          "crosscheck remains MANDATORY on every trial",
            "code_sha256": {
                "src/hyptraj/m3s25r1/arm_a.py":
                    sha(ROOT / "src/hyptraj/m3s25r1/arm_a.py"),
                "src/hyptraj/m3s25r1/arm_a_eval.py":
                    sha(ROOT / "src/hyptraj/m3s25r1/arm_a_eval.py")},
            "transactional_sidecar": "temp -> write -> flush -> fsync -> "
                                     "atomic rename -> parent-dir fsync "
                                     "(fail-closed) -> SHA verify"},
        "old_stream_retirement": {
            "retired_stream": "configs/phase_m3s25r1/"
                              "m3s25r1_a1r_retired_stream.json",
            "retired_stream_sha256": retired_sha,
            "old_ledger_sha256_expected": old_ledger_sha,
            "rule": "the old failed 20k realization is EXPOSED / "
                    "CONSUMED_INVALID and must never enter the "
                    "replacement dataset, features, CV, metrics or "
                    "verdict"},
        "namespace": A1R_NAMESPACE,
        "seed_manifest": "configs/phase_m3s25r1/m3s25r1_a1r_seed_manifest.json",
        "persistence": {
            "dir": "results/phase_m3s25r1/arm_a1r/",
            "ledger": "results/phase_m3s25r1/arm_a1r/trial_ledger.jsonl",
            "rule": "separate replacement paths; never reuse, truncate, "
                    "ignore or reinterpret the old Arm-A ledger",
            "chain": "STARTED -> 20k sampling -> transactional sidecar -> "
                     "record hash -> COMPLETE",
            "failure": "any replacement consumed-invalid unit => "
                       "M3-S25-R1-A1R-X => STOP => NO REPLAY"},
        "budget": {
            "n_trials": 960, "samples_per_trial": 20000,
            "replacement_planned": 19_200_000,
            "replacement_max": 19_200_000,
            "topup": 0, "substitution": 0,
            "old_invalid_stage_samples": 20_000,
            "cumulative_if_replacement_completes": 19_220_000,
            "rule": "the old 20,000 never counts toward replacement "
                    "completeness; cumulative project consumption is "
                    "reported separately"},
        "evaluation_protocol": {
            "frozen": "B0/B1/A1-A4 comparison, outer GroupKFold(5) / "
                      "inner GroupKFold(4), groups = config_id; no "
                      "test-fold tuning; truth manifest unseals ONLY "
                      "after 960/960 durable COMPLETE with 0 "
                      "CONSUMED_INVALID and exactly 19,200,000 "
                      "replacement samples",
            "terminal_names": {"success": "M3-S25-R1-A1R-A",
                               "b_gate": "M3-S25-R1-A1R-B-GATE",
                               "failure": "M3-S25-R1-A1R-X"}},
        "gates": {"M3_S25_R1_A1R_ARM_A_AUTHORIZED": "NO",
                  "M3_S25_R1_A1R_ARM_B_AUTHORIZED": "NO",
                  "old_M3_S25_R1_ARM_A_AUTHORIZED": "NO (CLOSED/EXERCISED/"
                                                    "TERMINAL-X)",
                  "truth": "NO (CLOSED/EXERCISED)",
                  "value_rarity_m3q": "BLOCKED"},
    }
    data = dump_json(A1R_CONTRACT, contract)
    print(f"M3-S25-R1-A1R0 contract frozen (sha {sha_bytes(data)[:16]}...) "
          f"replacement 19,200,000; cumulative 19,220,000")
    return contract


def _verify_frozen_a1r_inputs() -> dict:
    if sha_bytes(UNIVERSE.read_bytes()) != EXPECTED_UNIVERSE_SHA:
        raise RuntimeError("M3-S25-R1-A1R-X: universe SHA drift")
    if sha_bytes((CFG / "m3s25r1_contract.json").read_bytes()) \
            != EXPECTED_CONTRACT_SHA:
        raise RuntimeError("M3-S25-R1-A1R-X: contract SHA drift")
    got_panel = sha_bytes(PANEL_JSON.read_bytes())
    if got_panel != EXPECTED_PANEL_FILE_SHA:
        raise RuntimeError("M3-S25-R1-A1R-X: panel FILE sha drift")
    retired = load(A1R_RETIRED)
    got_ledger = sha_bytes(ARM_A_LEDGER.read_bytes())
    if got_ledger != retired["old_ledger_sha256_expected"]:
        raise RuntimeError(
            "M3-S25-R1-A1R-X: the old Arm-A ledger was modified after "
            "retirement (preservation violated)")
    # A1R0.1: runtime-verify the incident provenance SHAs match the
    # retired stream's frozen pins exactly
    if sha(DOC / "M3_S25_R1_Arm_A_Incident_Report.md") !=             retired["old_incident_report_sha256"]:
        raise RuntimeError(
            "M3-S25-R1-A1R-X: incident-report SHA drift vs retired stream")
    if sha_bytes(ARM_A_SEED_MANIFEST.read_bytes()) !=             retired["old_arm_a_seed_manifest_sha256"]:
        raise RuntimeError(
            "M3-S25-R1-A1R-X: old Arm-A seed-manifest SHA drift vs "
            "retired stream")
    manifest_sha = sha_bytes(PANEL_TRUTH_MANIFEST.read_bytes())
    if PANEL_TRUTH_MANIFEST_PIN != "PENDING-SET-AFTER-GENERATION" \
            and manifest_sha != PANEL_TRUTH_MANIFEST_PIN:
        raise RuntimeError("M3-S25-R1-A1R-X: truth manifest SHA drift")
    a1r_contract_sha = sha_bytes(A1R_CONTRACT.read_bytes())
    if A1R_CONTRACT_PIN != "PENDING-SET-AFTER-GENERATION" \
            and a1r_contract_sha != A1R_CONTRACT_PIN:
        raise RuntimeError("M3-S25-R1-A1R-X: A1R contract SHA drift")
    a1r_seeds_sha = sha_bytes(A1R_SEED_MANIFEST.read_bytes())
    if A1R_SEED_MANIFEST_PIN != "PENDING-SET-AFTER-GENERATION" \
            and a1r_seeds_sha != A1R_SEED_MANIFEST_PIN:
        raise RuntimeError("M3-S25-R1-A1R-X: A1R seed manifest SHA drift")
    a1r_retired_sha = sha_bytes(A1R_RETIRED.read_bytes())
    if A1R_RETIRED_PIN != "PENDING-SET-AFTER-GENERATION" \
            and a1r_retired_sha != A1R_RETIRED_PIN:
        raise RuntimeError("M3-S25-R1-A1R-X: A1R retired-stream SHA drift")
    return {"universe_sha256": EXPECTED_UNIVERSE_SHA,
            "panel_file_sha256": got_panel,
            "panel_truth_manifest_sha256": manifest_sha,
            "old_ledger_sha256": got_ledger,
            "a1r_contract_sha256": a1r_contract_sha,
            "a1r_seed_manifest_sha256": a1r_seeds_sha,
            "a1r_retired_stream_sha256": a1r_retired_sha}


def _a1r_old_stream_exclusion() -> dict:
    """Mechanical proof (A1R0 item 5): no old Arm-A SEED VALUE appears in
    the replacement stream.  Unit IDs intentionally repeat (the same 120
    panel states x 8 replicate slots are re-run with entirely new seeds --
    that is the replacement design); what is retired is the old
    REALIZATION (seeds + data), which must never enter A1R."""
    retired = load(A1R_RETIRED)
    old_vals = {u["seed"] for u in retired["units"]}
    old_keys = {tuple(u["seed_key"]) for u in retired["units"]}
    manifest = load(A1R_SEED_MANIFEST)
    new_vals = set(manifest["planned_seeds"].values())
    new_keys = {tuple(u["seed_key"]) for u in manifest["units"]}
    overlap_vals = sorted(new_vals & old_vals)
    overlap_keys = sorted(new_keys & old_keys)
    if overlap_vals or overlap_keys:
        raise RuntimeError(
            f"M3-S25-R1-A1R-X: retired-seed overlap: vals={overlap_vals[:3]} "
            f"keys={overlap_keys[:3]}")
    return {"old_seed_value_overlap": 0, "old_seed_key_overlap": 0,
            "old_values_total": len(old_vals),
            "EXCLUSION": "PASS",
            "note": "unit_id slots intentionally repeat; seeds are "
                    "entirely new"}


def a1r_preflight() -> dict:
    """A1R0 item 9: the full zero-sampling replacement readiness
    checklist."""
    checks = {}
    head = git_commit()
    checks["parent_incident_head_ancestor"] = subprocess.run(
        ["git", "merge-base", "--is-ancestor", OLD_ARM_A_TERMINAL_HEAD, head],
        cwd=ROOT, capture_output=True).returncode == 0
    # old stage terminal X + old gate CLOSED
    led = ledger_entries(ARM_A_LEDGER) if Path(ARM_A_LEDGER).exists() else []
    c = Counter(e.get("status") for e in led)
    checks["old_stage_terminal_x"] = (c.get("CONSUMED_INVALID", 0) == 1
                                      and c.get("COMPLETE", 0) == 0)
    checks["old_arm_a_gate_closed"] = not gate("M3_S25_R1_ARM_A_AUTHORIZED")
    checks["truth_gate_closed"] = not gate("M3_S25_R1_TRUTH_AUTHORIZED")
    checks["old_arm_b_gate_no"] = not gate("M3_S25_R1_ARM_B_AUTHORIZED")
    retired = load(A1R_RETIRED)
    checks["consumed_unit_retired"] = any(
        u["status"] == "CONSUMED_INVALID_20K"
        and u["unit_id"] == retired["consumed_unit"]["unit_id"]
        for u in retired["units"])
    pins = _verify_frozen_a1r_inputs()
    checks["old_ledger_preserved"] = True
    excl = _a1r_old_stream_exclusion()
    checks["old_seed_stream_excluded"] = excl["EXCLUSION"] == "PASS"
    # same panel / truth / contracts
    checks["same_panel_and_contracts"] = (
        pins["panel_file_sha256"] == EXPECTED_PANEL_FILE_SHA
        and pins["panel_truth_manifest_sha256"]
        == PANEL_TRUTH_MANIFEST_PIN)
    contract = load(A1R_CONTRACT)
    checks["corrected_instrumentation_sha"] = (
        contract["corrected_instrumentation"]["code_sha256"]
        ["src/hyptraj/m3s25r1/arm_a.py"]
        == sha(ROOT / "src/hyptraj/m3s25r1/arm_a.py")
        and contract["corrected_instrumentation"]["code_sha256"]
        ["src/hyptraj/m3s25r1/arm_a_eval.py"]
        == sha(ROOT / "src/hyptraj/m3s25r1/arm_a_eval.py"))
    seeds_cfg = load(A1R_SEED_MANIFEST)
    audit = load(OUT / "m3s25r1_a1r_seed_audit.json")
    checks["new_seeds_960_unique"] = (seeds_cfg["n_units"] == 960
                                      and audit["unique_seeds"] == 960
                                      and audit["historical_collision"] == 0)
    checks["replacement_destination_empty"] = (
        (not A1R_TRIALS.exists() or not any(A1R_TRIALS.iterdir()))
        and not A1R_LEDGER.exists() and not A1R_EVAL.exists())
    reserve = {r["state_id"] for r in csvread(
        OUT / "m3s25r1_protected_reserve_18.csv")}
    panel_ids = {s["state_id"] for s in load(PANEL_JSON)["states"]}
    checks["reserve_untouched"] = len(reserve) == 18 \
        and not (reserve & panel_ids)
    checks["evaluation_truth_sealed"] = verify_panel_truth_manifest()[
        "PANEL_TRUTH_MANIFEST_AUDIT"] == "PASS"
    checks["a1r_arm_a_gate_no"] = not gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED")
    checks["a1r_arm_b_gate_no"] = not gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED")
    checks["zero_sampling"] = True
    failed = sorted(k for k, v in checks.items() if not v)
    report = {
        "recorded_at": now(), "simulator_calls": 0, "samples": 0,
        "checks": checks, "failed_checks": failed,
        "frozen_pins": pins, "old_stream_exclusion": excl,
        "PREFLIGHT_VERDICT": "PASS" if not failed else "FAIL",
        "overall": ("A1R EXECUTION-READY (gates remain NO; awaiting the "
                    "human replacement-execution audit)" if not failed else
                    "A1R NOT EXECUTION-READY: " + ", ".join(failed)),
    }
    dump(OUT / "m3s25r1_a1r_preflight.json", report)
    print(f"M3-S25-R1-A1R0 preflight: {report['PREFLIGHT_VERDICT']} "
          f"({len(checks) - len(failed)}/{len(checks)} checks PASS)")
    return report


def verify_frozen_a1r_preflight_pass() -> dict:
    pf = load(OUT / "m3s25r1_a1r_preflight.json")
    if pf.get("PREFLIGHT_VERDICT") != "PASS":
        raise RuntimeError(
            f"M3-S25-R1-A1R-X: frozen A1R preflight verdict is "
            f"{pf.get('PREFLIGHT_VERDICT')!r}; execution not authorized; "
            "STOP")
    return pf


def _a1r_restart_scan(panel_states: list[dict]) -> dict:
    entries = ledger_entries(A1R_LEDGER) \
        if Path(A1R_LEDGER).exists() else []
    summary = {"fresh": 0, "complete_verified": 0}
    for s in panel_states:
        slug_dir = A1R_TRIALS / bounded_slug(s["state_id"])
        for rep in range(AA.REPLICATES):
            unit_id = f"{s['state_id']}|rep{rep}"
            rec = AA.verify_arm_a_trial_fresh_or_verified(
                unit_id, slug_dir / f"rep{rep}.json",
                slug_dir / f"rep{rep}_instrumentation.npz", entries,
                record_file_hash, record_file_hash)
            if rec is None:
                summary["fresh"] += 1
            else:
                summary["complete_verified"] += 1
    return summary


def arm_a1r_execute() -> dict:
    """GATED by M3_S25_R1_A1R_ARM_A_AUTHORIZED: YES.  Fail-closed
    ordering: old terminal X + old gate closed -> frozen pins + retired
    exclusion -> restart scan (NEW ledger) -> gates -> pure plan ->
    simulator.  Zero writes before the gate."""
    import hyptraj.m3d.benchmark_states as BS
    decision = load(SUM / "m3s25r1_panel_decision.json")
    if decision.get("PANEL") != "FROZEN":
        raise RuntimeError("M3-S25-R1-A1R-X: truth terminal is not "
                           "PANEL-FROZEN")
    if gate("M3_S25_R1_TRUTH_AUTHORIZED"):
        raise RuntimeError("M3-S25-R1-A1R-X: truth gate must remain "
                           "CLOSED/EXERCISED")
    if gate("M3_S25_R1_ARM_A_AUTHORIZED"):
        raise RuntimeError("M3-S25-R1-A1R-X: the OLD Arm-A gate is "
                           "CLOSED/TERMINAL-X and must remain NO")
    if gate("M3_S25_R1_ARM_B_AUTHORIZED") \
            or gate("M3_S25_R1_A1R_ARM_B_AUTHORIZED"):
        raise RuntimeError("M3-S25-R1-A1R-X: Arm B must remain NO")
    panel = load(PANEL_JSON)
    if panel["panel_sha256"] != AA.FROZEN_PANEL_SHA:
        raise RuntimeError("M3-S25-R1-A1R-X: panel SHA drift")
    _verify_frozen_a1r_inputs()
    _a1r_old_stream_exclusion()
    seeds_cfg = load(A1R_SEED_MANIFEST)
    panel_states = panel["states"]
    restart = _a1r_restart_scan(panel_states)
    if not gate("M3_S25_R1_A1R_ARM_A_AUTHORIZED"):
        raise RuntimeError(
            "M3_S25_R1_A1R_ARM_A_AUTHORIZED is not YES")
    contract_shas = {"a1r_contract": sha(A1R_CONTRACT),
                     "stage_contract": sha(CFG / "m3s25r1_contract.json"),
                     "panel_truth_manifest": sha(PANEL_TRUTH_MANIFEST)}
    plan_seeds = seeds_cfg["planned_seeds"]
    A1R_TRIALS.mkdir(parents=True, exist_ok=True)

    def run_trial(s, rep):
        unit_id = f"{s['state_id']}|rep{rep}"
        slug_dir = A1R_TRIALS / bounded_slug(s["state_id"])
        rec_p = slug_dir / f"rep{rep}.json"
        side_p = slug_dir / f"rep{rep}_instrumentation.npz"
        rec = AA.verify_arm_a_trial_fresh_or_verified(
            unit_id, rec_p, side_p, ledger_entries(A1R_LEDGER),
            record_file_hash, record_file_hash)
        if rec is not None:
            return

        def compute():
            bench = VR.resolve_bench_config(s["config_id"])
            st = BS.assemble_state(bench, float(s["s2"]),
                                   short_config=s["config_id"])
            if isinstance(st, dict):
                raise RuntimeError(
                    f"M3-S25-R1-A1R-X: assembly failed for {s['state_id']}")
            record, arrays = AA.arm_a_trial(
                st, plan_seeds[unit_id], s["state_id"], rep,
                s["config_id"], float(s["s2"]), contract_shas,
                namespace=A1R_NAMESPACE)
            record["recorded_at"] = now()
            record["stream"] = "arm_a1r_gradient"
            record["instrumentation_sha256"] = \
                AA.write_sidecar_transactional(side_p, arrays)
            return record

        def validate(payload):
            if payload.get("schema") != AA.TRIAL_SCHEMA:
                raise RuntimeError("M3-S25-R1-A1R-X: trial schema drift")
            # A1R0.1: namespace + seed provenance are part of the frozen
            # pre-hash contract
            if payload.get("namespace") != A1R_NAMESPACE:
                raise RuntimeError(
                    f"M3-S25-R1-A1R-X: trial namespace drift: "
                    f"{payload.get('namespace')!r} != {A1R_NAMESPACE!r}")
            if payload.get("seed") != plan_seeds[unit_id]:
                raise RuntimeError(
                    f"M3-S25-R1-A1R-X: trial seed drift vs the frozen "
                    f"A1R seed manifest for {unit_id}")
            if not payload.get("instrumentation_sha256"):
                raise RuntimeError("M3-S25-R1-A1R-X: sidecar hash missing")
            if record_file_hash(side_p) != payload["instrumentation_sha256"]:
                raise RuntimeError("M3-S25-R1-A1R-X: sidecar hash mismatch")
            if "truth" in payload or payload.get("confirmed_truth") \
                    or payload.get("corrected_class"):
                raise RuntimeError(
                    "M3-S25-R1-A1R-X: truth label leaked into the "
                    "execution view")

        result = run_trial_transactional(
            unit_id, rec_p, compute, ledger_path=A1R_LEDGER,
            pre_hash_validator=validate,
            base_entry={"panel_state_id": s["state_id"], "rep_id": rep,
                        "config_id": s["config_id"],
                        "seed_namespace": A1R_NAMESPACE,
                        "seed": plan_seeds[unit_id],
                        "samples": AA.N_SAMPLES,
                        "stream": "arm_a1r_gradient"})
        if result["status"] != "COMPLETE":
            raise RuntimeError(
                f"M3-S25-R1-A1R-X: trial not durably COMPLETE: {unit_id}: "
                f"{result}; CONSUMED_INVALID policy in force; NO REPLAY")

    for s in panel_states:
        for rep in range(AA.REPLICATES):
            run_trial(s, rep)
    entries = ledger_entries(A1R_LEDGER)
    counts = Counter(e.get("status") for e in entries)
    complete = counts.get("COMPLETE", 0)
    invalid = counts.get("CONSUMED_INVALID", 0)
    if invalid or complete != AA.N_TRIALS:
        raise RuntimeError(
            f"M3-S25-R1-A1R-X: replacement incomplete ({complete}/960, "
            f"invalid {invalid}); STOP")
    consumed = sum(AA.N_SAMPLES for e in entries
                   if e.get("status") == "COMPLETE")
    summary = {"n_trials": complete, "CONSUMED_INVALID": invalid,
               "replacement_samples": consumed,
               "replacement_planned": AA.BUDGET, "topup": 0,
               "old_invalid_stage_samples": 20_000,
               "cumulative_project_samples": 20_000 + consumed}
    dump(SUM / "m3s25r1_a1r_consumption.json", summary)
    print(f"M3-S25-R1-A1R execute: {complete}/960 durable COMPLETE; "
          f"replacement {consumed:,}; cumulative "
          f"{summary['cumulative_project_samples']:,}; STOP -- evaluation "
          "is a separate stage")
    return summary


def arm_a1r_evaluate() -> dict:
    """ONLY after 960/960 durable COMPLETE (0 CONSUMED_INVALID, exactly
    19,200,000 replacement samples): unseal the SAME sealed truth
    manifest and run the frozen comparison with A1R-local terminal
    names."""
    verify_frozen_a1r_preflight_pass()
    _verify_frozen_a1r_inputs()
    _a1r_old_stream_exclusion()
    entries = ledger_entries(A1R_LEDGER) \
        if Path(A1R_LEDGER).exists() else []
    counts = Counter(e.get("status") for e in entries)
    complete = counts.get("COMPLETE", 0)
    invalid = counts.get("CONSUMED_INVALID", 0)
    if invalid or complete != AA.N_TRIALS:
        raise RuntimeError(
            f"M3-S25-R1-A1R-X: evaluation requires 960/960 durable "
            f"COMPLETE (got {complete}, invalid {invalid}); the old 20k "
            "never counts; STOP")
    manifest_sha = sha(PANEL_TRUTH_MANIFEST)
    if PANEL_TRUTH_MANIFEST_PIN != "PENDING-SET-AFTER-GENERATION" \
            and manifest_sha != PANEL_TRUTH_MANIFEST_PIN:
        raise RuntimeError("M3-S25-R1-A1R-X: truth manifest SHA drift")
    truth_by_state = {s["state_id"]: s["truth"] for s in
                      load(PANEL_TRUTH_MANIFEST)["states"]}
    records, sidecars = [], []
    for s in load(PANEL_JSON)["states"]:
        slug_dir = A1R_TRIALS / bounded_slug(s["state_id"])
        for rep in range(AA.REPLICATES):
            unit_id = f"{s['state_id']}|rep{rep}"
            rec = AA.verify_arm_a_trial_fresh_or_verified(
                unit_id, slug_dir / f"rep{rep}.json",
                slug_dir / f"rep{rep}_instrumentation.npz", entries,
                record_file_hash, record_file_hash)
            if rec is None:
                raise RuntimeError(
                    f"M3-S25-R1-A1R-X: trial missing at evaluation: "
                    f"{unit_id}")
            records.append(rec)
            with np.load(slug_dir / f"rep{rep}_instrumentation.npz") as z:
                sidecars.append({k: z[k] for k in z.files})
    results = AE.run_comparison(records, sidecars, truth_by_state)
    verdict = AE.verdict(results, complete, invalid,
                         prefix="M3-S25-R1-A1R")
    out = {"recorded_at": now(),
           "truth_manifest_unsealed": {"sha256": manifest_sha,
                                       "after_complete_960": True},
           "results": results, "verdict": verdict}
    dump(A1R_EVAL, out)
    print(f"M3-S25-R1-A1R evaluate: VERDICT = {verdict['VERDICT']} "
          f"({verdict.get('compliant', [])}); STOP")
    return out




# --------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------

def all_stages() -> None:
    prepare()
    candidates_stage()
    p_ref_registry_stage()
    truth_seed_manifest_stage()
    budget_stage()
    preflight()
    contracts()
    docs()
    amendment2_record_doc()
    hashlock()
    print("M3-S25-R1 Round 0 prereg freeze complete; all gates remain NO")


def a0_stages() -> None:
    """M3-S25-R1-A0: zero-sampling Arm-A rebind & execution readiness."""
    panel_truth_manifest_stage()
    arm_a_contracts_stage()
    arm_a_preflight()
    print("M3-S25-R1-A0 complete; ARM_A/ARM_B remain NO; zero sampling")


def a1r_stages() -> None:
    """M3-S25-R1-A1R0: zero-sampling replacement Arm-A preregistration."""
    a1r_retired_stream_stage()
    a1r_seed_manifest_stage()
    a1r_contract_stage()
    a1r_preflight()
    print("M3-S25-R1-A1R0 complete; all A1R gates remain NO; zero sampling")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=[
        "prepare", "candidates", "p_ref_registry", "truth_seed_manifest",
        "budget", "preflight", "contracts", "docs", "hashlock",
        "truth_execute", "truth_panel", "all", "a0",
        "panel_truth_manifest", "arm_a_contracts", "arm_a_preflight",
        "arm_a_execute", "arm_a_evaluate", "a1r",
        "a1r_retired_stream", "a1r_seed_manifest", "a1r_contract",
        "a1r_preflight", "arm_a1r_execute", "arm_a1r_evaluate"])
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "candidates":
        candidates_stage()
    elif args.stage == "p_ref_registry":
        p_ref_registry_stage()
    elif args.stage == "truth_seed_manifest":
        truth_seed_manifest_stage()
    elif args.stage == "budget":
        budget_stage()
    elif args.stage == "preflight":
        preflight()
    elif args.stage == "contracts":
        contracts()
    elif args.stage == "docs":
        docs()
        amendment2_record_doc()
    elif args.stage == "hashlock":
        hashlock()
    elif args.stage == "truth_execute":
        truth_execute()
    elif args.stage == "truth_panel":
        truth_panel()
    elif args.stage == "all":
        all_stages()
    elif args.stage == "a0":
        a0_stages()
    elif args.stage == "panel_truth_manifest":
        panel_truth_manifest_stage()
    elif args.stage == "arm_a_contracts":
        arm_a_contracts_stage()
    elif args.stage == "arm_a_preflight":
        arm_a_preflight()
    elif args.stage == "arm_a_execute":
        arm_a_execute()
    elif args.stage == "arm_a_evaluate":
        arm_a_evaluate()
    elif args.stage == "a1r":
        a1r_stages()
    elif args.stage == "a1r_retired_stream":
        a1r_retired_stream_stage()
    elif args.stage == "a1r_seed_manifest":
        a1r_seed_manifest_stage()
    elif args.stage == "a1r_contract":
        a1r_contract_stage()
    elif args.stage == "a1r_preflight":
        a1r_preflight()
    elif args.stage == "arm_a1r_execute":
        arm_a1r_execute()
    elif args.stage == "arm_a1r_evaluate":
        arm_a1r_evaluate()


if __name__ == "__main__":
    main()
