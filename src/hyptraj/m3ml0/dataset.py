"""M3-ML0 Tier-A canonical dataset (taskbook Sec. 4/16).

Only two exposed same-protocol sources are eligible:
  A. PI1VNR fresh development panel  (24 states, 8 gradient reps, 20k/trial)
  B. M3-S1C confirmation panel       (24 states, 8 gradient reps, 20k/trial;
                                      EXPOSED by M3-S1C-B)

The remaining 18-state protected reserve is NEVER read beyond
state_id/config_id/membership/source-hash (firewall, taskbook Sec. 3).
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

PI1VNR_SUM = ROOT / "results/phase_m3pi1vnr/summary"
PI1VNR_CFG = ROOT / "configs/phase_m3pi1vnr"
PI1VNR_TRIALS = ROOT / "results/phase_m3pi1vnr/trials"
S1C_CFG = ROOT / "configs/phase_m3s1c"
S1C_TRIALS = ROOT / "results/phase_m3s1c/trials"
ML0_PRE = ROOT / "results/phase_m3ml0/preflight"

DEPLOYABLE = ("WIDEN", "SHRINK")
NON_DEPLOYABLE = ("HOLD", "AMBIGUOUS")

EXPECTED_PANEL_SHA = {
    "pi1vnr": "1914bf6d2c173107b955c00b2c49e9775c3e0c4e14ab0354b3f10d7e2fdcbd66",
}


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csvread(p) -> list[dict]:
    with open(p, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def json_load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def curvature_lookup(config_ids: set[str]) -> dict[str, float]:
    """Frozen curvature_c resolution (same sources as the S1C stage)."""
    out: dict[str, float] = {}
    cf1n = json.loads((ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")
                      .read_text(encoding="utf-8"))["physical_fields"]
    wcf1 = {r["wcf1_config_id"]: r for r in csvread(
        ROOT / "results/phase_m3wcf1/summary/m3wcf1_physical_config_manifest.csv")}
    freeze = json.loads((ROOT / "results/phase_m1d/freeze/m1d_freeze.json")
                        .read_text(encoding="utf-8")) if (ROOT / "results/phase_m1d/freeze/m1d_freeze.json").exists() else None
    if freeze is None:
        from hyptraj.m1d.experiments import load_freeze
        freeze = load_freeze()
    for cid in sorted(config_ids):
        if cid in wcf1:
            out[cid] = float(wcf1[cid]["curvature_c"])
        elif cid in cf1n:
            out[cid] = float(cf1n[cid]["curvature_c"])
        else:
            matches = [r for r in freeze["benchmark_configs"]
                       if r["config_id"].endswith(cid)]
            if len(matches) != 1:
                raise RuntimeError(f"ML0-X: config {cid} not uniquely resolvable")
            out[cid] = float(matches[0]["params"]["curvature_c"])
    return out


def _trial_rows(trials_dir: Path, panel_rows: list[dict], panel: str) -> list[dict]:
    truth_by_state = {r["state_id"]: r["truth"] for r in panel_rows}
    cfg_by_state = {r["state_id"]: r["config_id"] for r in panel_rows}
    s2_by_state = {r["state_id"]: float(r["s2"]) for r in panel_rows}
    rows = []
    for rep_file in sorted(trials_dir.glob("*/rep*.json")):
        rec = json.loads(rep_file.read_text(encoding="utf-8"))
        sid = rec["state_id"]
        if sid not in truth_by_state:
            raise RuntimeError(f"ML0-X: trial state {sid} not in panel manifest")
        g = rec["gradient"]
        rows.append({
            "panel": panel,
            "state_id": sid,
            "config_id": rec["config_id"],
            "s2": float(rec["s2"]),
            "rep": int(rec["rep_id"]),
            "seed": int(g["seed"]),
            "g_hat": float(g["g_hat"]),
            "g_ci_low": float(g["g_ci_low"]),
            "g_ci_high": float(g["g_ci_high"]),
            "ESS_grad": float(g["ESS_grad"]),
            "M2_hat": float(g["M2_hat"]),
            "responsibility_mass": float(g["responsibility_mass"]),
            "D_hat": float(g["D_hat"]),
            "gradient_valid": bool(g["valid"]),
            "S1": None if rec.get("S1") is None else float(rec["S1"]),
            "truth": truth_by_state[sid],
        })
    # cross-check truth/config/s2 against panel metadata
    for r in rows:
        assert r["truth"] == truth_by_state[r["state_id"]]
        assert r["config_id"] == cfg_by_state[r["state_id"]]
        assert abs(r["s2"] - s2_by_state[r["state_id"]]) < 1e-12
    return rows


def build_tier_a() -> dict:
    """Construct the 48-state / 384-trial canonical dataset with provenance."""
    # source hashes must match the frozen prereg anchors
    pi1vnr_panel_sha = sha(PI1VNR_SUM / "m3pi1vnr_fresh_development_panel.csv")
    s1c_panel_json_sha = sha(S1C_CFG / "m3s1c_panel.json")
    s1c_panel_csv_sha = sha(ROOT / "results/phase_m3s1c/preflight/m3s1c_panel.csv")
    if pi1vnr_panel_sha != EXPECTED_PANEL_SHA["pi1vnr"]:
        raise RuntimeError("ML0-X: PI1VNR panel hash mismatch")
    s1c_panel = json.loads((S1C_CFG / "m3s1c_panel.json").read_text(encoding="utf-8"))
    # the S1C panel json's sha256 field anchors the panel CSV (no
    # self-referential JSON hashing)
    if s1c_panel["sha256"] != s1c_panel_csv_sha:
        raise RuntimeError("ML0-X: S1C panel csv hash mismatch")

    pi1vnr_panel = csvread(PI1VNR_SUM / "m3pi1vnr_fresh_development_panel.csv")
    s1c_states = s1c_panel["states"]
    s1c_panel_rows = [{"state_id": s["state_id"], "truth": s["truth"],
                       "config_id": s["config_id"], "s2": s["s2"]}
                      for s in s1c_states]

    rows = (_trial_rows(PI1VNR_TRIALS, pi1vnr_panel, "pi1vnr")
            + _trial_rows(S1C_TRIALS, s1c_panel_rows, "s1c"))

    states = sorted({(r["panel"], r["state_id"]) for r in rows})
    if len(rows) != 384 or len(states) != 48:
        raise RuntimeError(
            f"ML0-X: Tier-A must be 48 states / 384 trials, got {len(states)}/{len(rows)}")

    curv = curvature_lookup({r["config_id"] for r in rows})
    for r in rows:
        r["curvature_c"] = curv[r["config_id"]]
        r["label_deploy"] = 1 if r["truth"] in DEPLOYABLE else 0

    rows.sort(key=lambda r: (r["panel"], r["state_id"], r["rep"]))
    manifest = {
        "recorded_at": None,
        "sources": {
            "pi1vnr_panel_csv": {
                "path": "results/phase_m3pi1vnr/summary/m3pi1vnr_fresh_development_panel.csv",
                "sha256": pi1vnr_panel_sha, "states": 24},
            "pi1vnr_trials_dir": {
                "path": "results/phase_m3pi1vnr/trials", "trials": 192,
                "ledger": "results/phase_m3pi1vnr/trials/trial_ledger.jsonl"},
            "s1c_panel_json": {
                "path": "configs/phase_m3s1c/m3s1c_panel.json",
                "sha256": s1c_panel_json_sha, "states": 24},
            "s1c_panel_csv": {
                "path": "results/phase_m3s1c/preflight/m3s1c_panel.csv",
                "sha256": s1c_panel_csv_sha},
            "s1c_trials_dir": {
                "path": "results/phase_m3s1c/trials", "trials": 192,
                "ledger": "results/phase_m3s1c/trials/trial_ledger.jsonl"},
        },
        "rows": len(rows), "states": 48,
    }
    return {"rows": rows, "manifest": manifest}


def durable_complete_check() -> dict:
    """Only valid durable COMPLETE rows may enter the dataset (Sec. 22)."""
    out = {}
    for name, trials in (("pi1vnr", PI1VNR_TRIALS), ("s1c", S1C_TRIALS)):
        ledger = trials / "trial_ledger.jsonl"
        entries = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
                   if l.strip()]
        comp = [e for e in entries if e.get("status") == "COMPLETE"]
        inv = [e for e in entries if e.get("status") == "CONSUMED_INVALID"]
        out[name] = {"complete": len(comp), "consumed_invalid": len(inv),
                     "unique": len({e["state_id"] for e in comp})}
    return out


def protected_reserve_18() -> list[dict]:
    """Firewall: the 18 remaining protected states (42 reserve - 24 S1C)."""
    reserve = csvread(PI1VNR_SUM / "m3pi1vnr_remaining_protected_reserve.csv")
    s1c_panel = json.loads((S1C_CFG / "m3s1c_panel.json").read_text(encoding="utf-8"))
    consumed = {s["state_id"] for s in s1c_panel["states"]}
    remaining = [r for r in reserve if r["state_id"] not in consumed]
    if len(remaining) != 18:
        raise RuntimeError(
            f"ML0-X: expected 18 remaining protected states, got {len(remaining)}")
    src_sha = {
        "reserve_manifest": sha(PI1VNR_SUM / "m3pi1vnr_remaining_protected_reserve.csv"),
        "s1c_panel_json": sha(S1C_CFG / "m3s1c_panel.json"),
    }
    for r in remaining:
        r["reserve_manifest_sha256"] = src_sha["reserve_manifest"]
    return remaining
