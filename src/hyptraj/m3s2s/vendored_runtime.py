"""M3-S2S vendored runtime: execution-time resolution reads ONLY the
vendored snapshots under configs/phase_m3s2s/reference_truth_protocol/, the
tracked candidate universe, and the tracked new-config registry
(execution-readiness amendment, items 1-2).

Forbidden at execution time (historical-comparison inputs only):
    configs/phase_m3cf1n/*, results/phase_m3wcf1/*, results/phase_m3cf0/*,
    docs/phase_m1d/*
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VENDORED = ROOT / "configs/phase_m3s2s/reference_truth_protocol"
UNIVERSE = ROOT / "configs/phase_m3s2s/m3s2s_candidate_universe.json"
NEW_CONFIG_REGISTRY = ROOT / "configs/phase_m3s2s/m3s2s_new_config_registry.json"
TRUTH_CONTRACT = ROOT / "configs/phase_m3s2s/m3s2s_truth_contract.json"

# LF-normalized sha of the tracked universe (byte-identical to the git
# blob audited at 926a5fc).  The earlier prereg-report value d74a7be7... was
# the CRLF working-tree rendering of the identical logical content on
# Windows; the execution-readiness amendment normalizes writes to LF so
# working tree == git blob == audited sha.
EXPECTED_UNIVERSE_SHA = ("1ff92a140e8ceb0878100ebdeea6bdcf5f6f5fd91ec0838bf9"
                         "a84b3931412ca0")
FORBIDDEN_RUNTIME_ROOTS = ("configs/phase_m3cf1n/", "results/phase_m3wcf1/",
                           "results/phase_m3cf0/", "docs/phase_m1d/")

VENDORED_FILES = {
    "pref": "m3cf1n_pref_protocol.json",
    "discovery": "m3cf1n_discovery_protocol.json",
    "confirmation": "m3cf1n_confirmation_protocol.json",
    "cf1n_configs": "m3cf1n_configs.json",
    "wcf1_manifest": "m3wcf1_physical_config_manifest.csv",
    "m1d_freeze": "M1_D_Benchmark_Freeze.json",
    "raw_lattice": "m3cf0_raw_physical_candidate_lattice.csv",
    "legacy_p_ref": "m3d2_probability_reference.json",
}
# per-config historical P_ref records (vendored under pref_records/)
PREF_RECORD_DIRS = {"cf1n_new": ("m3cf1n_pref_protocol.json", "results/phase_m3cf1n/pref"),
                    "wcf1_new": ("m3wcf1_physical_config_manifest.csv", "results/phase_m3wcf1/pref")}


class VendoredRuntimeError(RuntimeError):
    pass


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _guarded_read_bytes(path: Path) -> bytes:
    """Defense-in-depth: refuse to read any forbidden runtime root."""
    rel = path.resolve().as_posix().replace("\\", "/")
    for forbidden in FORBIDDEN_RUNTIME_ROOTS:
        if f"/{forbidden}" in rel or rel.startswith(forbidden):
            raise VendoredRuntimeError(
                f"execution-time read from forbidden runtime root: {rel}")
    return path.read_bytes()


def _sha(path: Path) -> str:
    return _sha_bytes(_guarded_read_bytes(path))


def load_vendored(name: str) -> dict:
    """Load a vendored protocol snapshot and verify its sha256 against the
    frozen truth contract.  Hash change => hard fail (no silent swap)."""
    contract = json.loads(TRUTH_CONTRACT.read_text(encoding="utf-8"))
    fname = VENDORED_FILES[name]
    expected = contract["vendored_snapshots"].get(fname)
    p = VENDORED / fname
    got = _sha(p)
    if expected is None or got != expected:
        raise VendoredRuntimeError(
            f"vendored protocol hash mismatch for {name}: {got} != {expected}")
    return json.loads(_guarded_read_bytes(p))


def load_vendored_csv(name: str) -> list[dict]:
    text = _guarded_read_bytes(VENDORED / VENDORED_FILES[name]).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def verify_universe() -> list[dict]:
    """Load the tracked 240-state universe and verify its sha256 against
    the frozen constant BEFORE any simulator call.  Never regenerated or
    substituted at execution time."""
    got = _sha_bytes(UNIVERSE.read_bytes())
    if got != EXPECTED_UNIVERSE_SHA:
        raise VendoredRuntimeError(
            f"candidate-universe sha mismatch: {got} != {EXPECTED_UNIVERSE_SHA}")
    u = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    if u["n_states"] != 240 or len(u["states"]) != 240:
        raise VendoredRuntimeError("candidate universe shape drift")
    return u["states"]


def load_vendored_protocol_constants() -> dict:
    """The three truth-protocol snapshots (byte-verified) are the runtime
    source of the budgets, thresholds and CRN semantics."""
    pref = load_vendored("pref")
    disc = load_vendored("discovery")
    conf = load_vendored("confirmation")
    return {
        "pref_samples_per_config": int(pref["samples_per_config"]),
        "discovery_samples_per_arm": int(disc["samples_per_arm"]),
        "confirmation_samples_per_arm": int(conf["samples_per_arm"]),
        "direction_margin": float(disc["direction_margin"]),
        "hold_band": float(disc["hold_band"]),
        "improvement_threshold": float(disc["improvement_threshold"]),
        "min_arm_ess": float(disc["min_arm_ess"]),
        "paired_crn_batches": int(conf["paired_crn_batches"]),
        "namespaces": {"pref": pref["namespace"],
                       "discovery": disc["namespace"],
                       "confirmation": conf["namespace"]},
    }


def _new_config_registry() -> dict:
    reg = json.loads(NEW_CONFIG_REGISTRY.read_text(encoding="utf-8"))
    if len(reg["configs"]) != 8:
        raise VendoredRuntimeError("new-config registry shape drift")
    return reg


def resolve_bench_config(cid: str):
    """Build the BenchmarkConfig for a candidate's config from VENDORED
    sources only (never configs/phase_m3cf1n, results/phase_m3wcf1,
    results/phase_m3cf0, docs/phase_m1d)."""
    from hyptraj.m1d.experiments import BenchmarkConfig

    if cid.startswith("cf1n_new_"):
        fields = load_vendored("cf1n_configs")["physical_fields"][cid]
        return BenchmarkConfig(
            config_id=cid, batch_seed=20300315, batch_index=0,
            theta_deg=tuple(float(fields[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(fields[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(fields[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(fields["curvature_c"]),
            offset_o=tuple(float(fields[f"offset_{i}"]) for i in range(1, 5)),
        )
    if cid.startswith("wcf1_new_"):
        row = next(r for r in load_vendored_csv("wcf1_manifest")
                   if r["wcf1_config_id"] == cid)
        m = re.search(r"_b(\d+)_c(\d+)$", row["raw_candidate_id"])
        return BenchmarkConfig(
            config_id=cid, batch_seed=int(m.group(1)),
            batch_index=int(m.group(2)),
            theta_deg=tuple(float(row[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(row[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(row[f"curved_{i}"].strip() == "True"
                         for i in range(1, 5)),
            curvature_c=float(row["curvature_c"]),
            offset_o=tuple(float(row[f"offset_{i}"]) for i in range(1, 5)),
        )
    if cid.startswith("m3s2s_cfg_"):
        reg = _new_config_registry()
        raw_cid = reg["configs"][cid]["raw_candidate_id"]
        row = next(r for r in load_vendored_csv("raw_lattice")
                   if r["config_id"] == raw_cid)
        m = re.search(r"_b(\d+)_c(\d+)$", raw_cid)
        return BenchmarkConfig(
            config_id=cid, batch_seed=int(m.group(1)),
            batch_index=int(m.group(2)),
            theta_deg=tuple(float(row[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(row[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(row[f"curved_{i}"].strip() == "True"
                         for i in range(1, 5)),
            curvature_c=float(row["curvature_c"]),
            offset_o=tuple(float(row[f"offset_{i}"]) for i in range(1, 5)),
        )
    # legacy c* configs: vendored M1-D benchmark freeze
    freeze = load_vendored("m1d_freeze")
    matches = [r for r in freeze["benchmark_configs"]
               if r["config_id"].endswith(cid)]
    if len(matches) != 1:
        raise VendoredRuntimeError(f"config {cid} not uniquely resolvable")
    rec = matches[0]
    p = rec["params"]
    m = re.search(r"_b(\d+)_c(\d+)$", rec["config_id"])
    return BenchmarkConfig(
        config_id=cid, batch_seed=int(m.group(1)), batch_index=int(m.group(2)),
        theta_deg=tuple(float(v) for v in p["theta_deg"]),
        h=tuple(float(v) for v in p["h"]),
        curved=tuple(bool(v) for v in p["curved"]),
        curvature_c=float(p["curvature_c"]),
        offset_o=tuple(float(v) for v in p["offset_o"]),
    )


def load_config_p_ref(config_id: str) -> dict:
    """Config-level corrected probability reference for the classification
    gate, read from VENDORED snapshots (existing configs) or from the
    stage's own durable PREF record (8 new configs)."""
    if config_id.startswith("m3s2s_cfg_"):
        p = ROOT / "results/phase_m3s2s/pref" / f"{config_id}.json"
        return json.loads(p.read_text(encoding="utf-8"))
    if config_id.startswith("cf1n_new_") or config_id.startswith("wcf1_new_"):
        p = VENDORED / "pref_records" / f"{config_id}.json"
        rec = json.loads(_guarded_read_bytes(p))
        if rec.get("record_type") not in ("M3CF1N-PREF", "M3WCF1-PREF"):
            raise VendoredRuntimeError(f"unexpected pref record type: {p}")
        return rec
    # legacy c* configs: vendored M3-D2 per-config probability reference
    refs = json.loads(_guarded_read_bytes(VENDORED / VENDORED_FILES["legacy_p_ref"]))
    entries = refs["records"] if isinstance(refs, dict) and "records" in refs else refs
    matches = [e for e in entries
               if str(e.get("config_id", "")).endswith(config_id)]
    if len(matches) != 1:
        raise VendoredRuntimeError(
            f"config-level P_ref not uniquely resolvable for {config_id}")
    e = matches[0]
    return {"p_ref_full": float(e["p_ref_full"]),
            "p_ref_full_SE": float(e["p_ref_full_SE"]),
            "p_ref_full_CI": [float(x) for x in e["p_ref_full_CI"]],
            "source": "vendored m3d2_probability_reference"}
