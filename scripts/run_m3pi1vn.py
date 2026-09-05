"""M3-PI1VN -- Independent fresh-panel finite-action information validation.

The first valid clean test of the frozen <=2x V1 hypothesis, run on the
WCF1-A fresh 8W/8S/8ND development panel with entirely fresh seeds:

    fresh panel + fresh seeds + same gradient + same 10k/10k paired probe
    + same V1 + same S1 + same 5%/75%/20% gates + same 5pp criterion
    = first valid verdict on the <=2x V1 hypothesis

Protocol inheritance (frozen, never retuned by any diagnostic):
    gradient/probe/V1/S1/metric/threshold semantics are the committed PI1V
    objects: the pure metric-threshold machinery is imported verbatim from
    scripts/run_m3pi1v.py, and the gradient/probe trial functions are
    line-identical clones differing only in the seed namespaces
    (M3-PI1VN-GRAD / M3-PI1VN-PROBE).  Persistence follows the repaired
    non-circular WA1R contract (pre-hash schema validation; the WA1 bug class
    is structurally impossible).

Stages: prepare | pilot | analyze | figures | report
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

import run_m3pi1v as P1V  # noqa: E402  (committed protocol machinery, verbatim)
import run_m3pi1v as _  # noqa: E402  (ensures protocol module loaded)
import run_m3pi1vr0 as R0  # noqa: E402
import run_m3pi1v as R1  # noqa: E402  (namespace audit reuse)
from hyptraj.m1d.experiments import BenchmarkConfig, config_from_record, load_freeze  # noqa: E402
from hyptraj.m3cf1r0.persistence import ledger_append, ledger_entries  # noqa: E402
from hyptraj.m3d.benchmark_states import assemble_state, state_arms  # noqa: E402
from hyptraj.m3pi1vr0.persistence import safe_fs_id  # noqa: E402
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    HASH_FIELD,
    ReplayError,
    StatePersistenceError,
    record_file_hash,
    run_trial_transactional,
    scientific_payload_hash,
    validate_safe_path,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vn/summary"
TRIALS = ROOT / "results/phase_m3pi1vn/trials"
FIG = ROOT / "results/phase_m3pi1vn/figures"
CFG = ROOT / "configs/phase_m3pi1vn"
DOC = ROOT / "docs/phase_m3pi1vn"

WCF1_OUT = ROOT / "results/phase_m3wcf1/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
WA1_OUT = ROOT / "results/phase_m3wa1/summary"
WA1R_OUT = ROOT / "results/phase_m3wa1r/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"

PANEL_CSV = WCF1_OUT / "m3wcf1_fresh_development_panel.csv"
CONSUMED_CANDIDATE = "cf1n_new_000_wa1_w_s2_1p788854382"

R = 8                    # reps per state (frozen)
N_GRAD = 20_000          # B_grad
N_PROBE = 10_000         # per arm
N_BATCH = 20
ALPHA_P = 0.5
MARGIN = -0.01
Z95 = 1.959963984540054
GATES = {"wrong_direction_max": 0.05, "coverage_min": 0.75, "unsafe_max": 0.20}
UNIQUE_GAIN_PP = 0.05
GRAD_NS = "M3-PI1VN-GRAD"
PROBE_NS = "M3-PI1VN-PROBE"
DEPLOYABLE = ("WIDEN", "SHRINK")
NON_DEPLOYABLE = ("HOLD", "AMBIGUOUS")

TRIAL_LEDGER = TRIALS / "trial_ledger.jsonl"
GRAD_LEDGER = TRIALS / "gradient_ledger.jsonl"
PROBE_LEDGER = TRIALS / "probe_ledger.jsonl"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, v) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_json(v) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True).encode("utf-8")).hexdigest()


def csvread(p) -> list[dict]:
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def csvwrite(p, rows: list[dict]) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def seed(namespace: str, *parts) -> int:
    material = "|".join((namespace, *(str(x) for x in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % (2**31 - 1) + 1


def wilson(k: int, n: int):
    if not n:
        return None
    z = Z95
    p_ = k / n
    d = 1 + z * z / n
    c = (p_ + z * z / (2 * n)) / d
    h = z * math.sqrt(p_ * (1 - p_) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def boundary_block(extra: dict | None = None) -> dict:
    base = {
        "value": "BLOCKED",
        "rarity_shift": "BLOCKED",
        "m3_q": "BLOCKED",
        "protected_confirmation_authorized": False,
        "confirmation_trials": 0,
        "reserve_pilot_trials": 0,
    }
    base.update(extra or {})
    return base


def family_of(row: dict) -> str:
    stage = row.get("source_stage", "")
    if stage == "M3-WCF1":
        return "WCF1 new"
    if stage in ("M3-CF1N", "M3-WA1R") or row["config_id"].startswith("cf1n_new"):
        return "CF1N replacement"
    return "legacy/current corrected"


_cf1n_fields = None
_wcf1_fields = None


def bench(config_id: str):
    global _cf1n_fields, _wcf1_fields
    if _cf1n_fields is None:
        _cf1n_fields = load(ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")["physical_fields"]
    if _wcf1_fields is None:
        _wcf1_fields = {r["wcf1_config_id"]: r
                        for r in csvread(WCF1_OUT / "m3wcf1_physical_config_manifest.csv")}
    if config_id in _wcf1_fields:
        f = _wcf1_fields[config_id]
        raw = {r["config_id"]: r for r in
               csvread(ROOT / "results/phase_m3cf0/summary/"
                       "m3cf0_raw_physical_candidate_lattice.csv")}
        gen = raw[f["raw_candidate_id"]]
        return BenchmarkConfig(
            config_id=config_id,
            batch_seed=int(gen.get("generation_seed", 20300315)),
            batch_index=int(gen.get("batch_index", 0)),
            theta_deg=tuple(float(f[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(f[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(f["curvature_c"]),
            offset_o=tuple(float(f[f"offset_{i}"]) for i in range(1, 5)),
        )
    if config_id in _cf1n_fields:
        f = _cf1n_fields[config_id]
        return BenchmarkConfig(
            config_id=config_id, batch_seed=20300315, batch_index=0,
            theta_deg=tuple(float(f[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(f[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(f["curvature_c"]),
            offset_o=tuple(float(f[f"offset_{i}"]) for i in range(1, 5)),
        )
    matches = [r for r in load_freeze()["benchmark_configs"]
               if r["config_id"].endswith(config_id)]
    if len(matches) != 1:
        raise RuntimeError(f"PI1VN-X: config {config_id} not uniquely resolvable")
    return config_from_record(matches[0])


_states: dict[str, object] = {}


def state_for(row: dict):
    sid = row["state_id"]
    if sid not in _states:
        st = assemble_state(bench(row["config_id"]), float(row["s2"]),
                            short_config=row["config_id"])
        if isinstance(st, dict):
            raise RuntimeError(f"PI1VN-X: state assembly failed for {sid}: {st}")
        _states[sid] = st
    return _states[sid]


# --------------------------------------------------------------------------
# inherited protocol implementations (verbatim PI1V semantics; PI1VN seeds)
# --------------------------------------------------------------------------

def gradient_trial(st, seed_value: int) -> dict:
    """Line-identical clone of run_m3pi1v.gradient_trial (PI1VN namespace)."""
    z, lp, lr, strata = P1V.draw_online_pilot(st, seed_value, n_pilot=N_GRAD, alpha=ALPHA_P)
    gd = P1V.gradient_decision(st, seed_value, z, lp, lr, strata)
    g = gd["gradient"]
    valid = (not bool(g["problems"])
             and np.isfinite(g["g_hat"]) and np.isfinite(g["g_ci_low"])
             and np.isfinite(g["g_ci_high"]) and np.isfinite(g["ESS_grad"])
             and g["ESS_grad"] >= 20)
    return {
        "seed": int(seed_value),
        "namespace": GRAD_NS,
        "samples": N_GRAD,
        "batches": N_BATCH,
        "alpha_p": ALPHA_P,
        "g_hat": float(g["g_hat"]),
        "g_ci_low": float(g["g_ci_low"]),
        "g_ci_high": float(g["g_ci_high"]),
        "ESS_grad": float(g["ESS_grad"]),
        "M2_hat": float(g["M2_hat"]),
        "responsibility_mass": float(g["responsibility_mass"]),
        "D_hat": float(g["D_hat"]),
        "problems": list(g["problems"]),
        "s2_base": float(g["s2_base"]),
        "sign": "WIDEN" if g["g_hat"] < 0 else "SHRINK",
        "valid": bool(valid),
    }


def paired_probe(st, chosen: str, seed_value: int) -> dict:
    """Line-identical clone of run_m3pi1v.paired_probe (PI1VN namespace)."""
    arms = state_arms(st)
    base, act = arms["base"], arms[chosen.lower()]
    rng = np.random.default_rng([int(seed_value), 717])
    bn = N_PROBE // N_BATCH
    mb, ma, pb, pa = [], [], [], []
    for _ in range(N_BATCH):
        comp = rng.choice(base.n_components, size=bn, p=base.weights)
        eps = rng.standard_normal((bn, base.centers.shape[1]))
        z0 = base.centers[comp] + np.einsum(
            "njk,nk->nj", np.stack([base.chols[i] for i in comp]), eps)
        z1 = act.centers[comp] + np.einsum(
            "njk,nk->nj", np.stack([act.chols[i] for i in comp]), eps)
        for z, prop, m, p in ((z0, base, mb, pb), (z1, act, ma, pa)):
            event = np.asarray(st.bench_cfg.label(z), dtype=object) != "S0"
            w = np.exp(np.asarray(st.bench_cfg.logp(z), dtype=float)
                       - prop.log_density(z))
            c = event * w
            m.append(float(np.mean(c * c)))
            p.append(float(np.mean(c)))
    m0, m1 = float(np.mean(mb)), float(np.mean(ma))
    r_batches = np.asarray(ma) / np.asarray(mb) - 1
    se = float(r_batches.std(ddof=1) / math.sqrt(N_BATCH))
    ess0 = N_PROBE * float(np.mean(pb)) ** 2 / m0 if m0 > 0 else 0.0
    ess1 = N_PROBE * float(np.mean(pa)) ** 2 / m1 if m1 > 0 else 0.0
    valid = (all(np.isfinite(x) for x in (m0, m1, se, ess0, ess1))
             and se > 0 and ess0 >= 20 and ess1 >= 20)
    return {
        "seed": int(seed_value),
        "namespace": PROBE_NS,
        "executed": True,
        "samples_base": N_PROBE,
        "samples_action": N_PROBE,
        "opposite_action_probe_samples": 0,
        "paired_batches": N_BATCH,
        "batch_size": bn,
        "batch_m2_base": [float(x) for x in mb],
        "batch_m2_action": [float(x) for x in ma],
        "batch_mean_w_base": [float(x) for x in pb],
        "batch_mean_w_action": [float(x) for x in pa],
        "m2_base": m0,
        "m2_action": m1,
        "r_hat": float(m1 / m0 - 1) if m0 else None,
        "se_r_hat": se,
        "ess_base": ess0,
        "ess_action": ess1,
        "valid": bool(valid),
    }


s1_score = P1V.s1_score                # committed UC3/PI1 S1, verbatim
v1_score = P1V.v1_score                # committed PI1 V1, verbatim
policy_action = P1V.policy_action      # committed V1/S1 policies, verbatim
evaluate = P1V.evaluate                # committed UC3 metric semantics
frontier = P1V.frontier                # committed threshold enumeration
select_threshold = P1V.select_threshold
best_safe_coverage = P1V.best_safe_coverage
direction_sanity = P1V.direction_sanity
threshold_grid = P1V.threshold_grid


# --------------------------------------------------------------------------
# panel
# --------------------------------------------------------------------------

def panel_rows() -> list[dict]:
    rows = csvread(PANEL_CSV)
    if len(rows) != 24 or len({r["state_id"] for r in rows}) != 24:
        raise RuntimeError("PI1VN-X: fresh panel is not 24 unique states")
    return rows


def check_panel_hash() -> str:
    digest = sha(PANEL_CSV)
    expected = load(WCF1_OUT / "m3wcf1_fresh_development_panel_hash.json")["panel_sha256"]
    if digest != expected:
        raise RuntimeError(f"PI1VN-X: panel hash mismatch {digest} != {expected}")
    return digest


# --------------------------------------------------------------------------
# stage: prepare (zero simulator)
# --------------------------------------------------------------------------

def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    CFG.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    TRIALS.mkdir(parents=True, exist_ok=True)
    check_panel_hash()
    rows = panel_rows()
    comp = Counter(r["truth"] for r in rows)
    if not (comp["WIDEN"] == 8 and comp["SHRINK"] == 8
            and comp["HOLD"] + comp["AMBIGUOUS"] == 8 and len(rows) == 24):
        raise RuntimeError("PI1VN-X: panel composition mismatch")

    # -- parent audit (taskbook Sec. 1) ---------------------------------------
    wcf1 = load(WCF1_OUT / "m3wcf1_final_verdict.json")
    wa1r = load(WA1R_OUT / "m3wa1r_final_verdict.json")
    wa1 = load(WA1_OUT / "m3wa1_final_verdict.json")
    pi1v_status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    wcf1_pref = load(WCF1_OUT / "m3wcf1_pref_summary.json")
    wcf1_ref = load(ROOT / "results/phase_m3wcf1/reference/reference_manifest.json")
    checks = {
        "WCF1 verdict": wcf1["verdict"] == "WCF1-A",
        "WCF1 P_ref 6/6": wcf1_pref["complete"] == 6
                          and wcf1_pref["consumed_invalid"] == 0,
        "WCF1 reference 12/12": wcf1_ref["complete"] == 12
                                and wcf1_ref["consumed_invalid"] == 0,
        "panel 24/8W/8S/8ND": len(rows) == 24 and comp["WIDEN"] == 8
                              and comp["SHRINK"] == 8,
        "panel pilot exposure 0": all(int(r["pilot_exposure"]) == 0 for r in rows),
        "panel probe exposure 0": all(int(r["probe_exposure"]) == 0 for r in rows),
        "PI1V valid verdict": pi1v_status["PI1V valid verdict"] == "PI1V-X",
        "PI1V Attempt-2 diagnostic only":
            pi1v_status["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY",
        "WA1 verdict": wa1["verdict"] == "WA1-X",
        "WA1R verdict": wa1r["verdict"] == "WA1R-B",
        "retired states remain retired": True,   # verified in firewall audits
    }
    if not all(checks.values()):
        raise RuntimeError(f"PI1VN-X: parent audit mismatch {checks}")
    dump(OUT / "m3pi1vn_parent_audit.json", {
        "recorded_at": now(), "checks": checks, "all_match": all(checks.values()),
        "panel_source_stages": dict(Counter(r["source_stage"] for r in rows)),
    })

    # -- panel hash audit (taskbook Sec. 2) ------------------------------------
    dump(OUT / "m3pi1vn_panel_hash_audit.json", {
        "recorded_at": now(),
        "panel_csv": PANEL_CSV.as_posix(),
        "recomputed_sha256": check_panel_hash(),
        "wcf1_committed_sha256":
            load(WCF1_OUT / "m3wcf1_fresh_development_panel_hash.json")["panel_sha256"],
        "match": True,
        "panel_regeneration_attempted": False,
        "panel_states": [{"state_id": r["state_id"], "truth": r["truth"],
                          "config_id": r["config_id"], "s2": float(r["s2"]),
                          "source_stage": r["source_stage"]} for r in rows],
    })

    # -- freshness firewall (taskbook Sec. 4) -----------------------------------
    touched: set[str] = set()
    for q in (ROOT / "results/phase_m3pi1v/quarantine_attempt1",
              ROOT / "results/phase_m3pi1v/quarantine_attempt2",
              ROOT / "results/phase_m3wa1/reference",
              ROOT / "results/phase_m3wa1r/reference"):
        tdir = q / "trials"
        if tdir.exists():
            touched |= {d.name for d in tdir.iterdir() if d.is_dir()}
    old_panel = {r["state_id"] for r in csvread(CF2 / "m3cf2_development_panel.csv")}
    reserve = {r["state_id"] for r in
               csvread(CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    freshness = []
    for r in rows:
        pilot_exposed = r["state_id"] in touched
        probe_exposed = pilot_exposed
        # threshold replay: fresh panel states never appeared in any PI1V
        # Attempt-2 threshold artifact (quarantined) nor any WA1R analysis
        replay = (PI1VQ := ROOT / "results/phase_m3pi1v/quarantine_attempt2"
                  / "summary_analysis") .exists() and any(
            r["state_id"] in (PI1VQ / n).read_text(encoding="utf-8")
            for n in ("m3pi1v_state_level_policy_audit.csv",)
            if (PI1VQ / n).exists())
        ok = not pilot_exposed and not probe_exposed and not replay \
            and r["state_id"] not in old_panel and r["state_id"] != CONSUMED_CANDIDATE
        freshness.append({"state_id": r["state_id"], "truth": r["truth"],
                          "config_id": r["config_id"],
                          "pilot_exposure_pre_pi1vn": 0 if not pilot_exposed else 1,
                          "probe_exposure_pre_pi1vn": 0 if not probe_exposed else 1,
                          "threshold_replay_exposure": 1 if replay else 0,
                          "scientifically_fresh": "True" if ok else "RETIRED"})
    if not all(f["scientifically_fresh"] == "True" for f in freshness):
        raise RuntimeError("PI1VN-X: panel freshness firewall violated")
    csvwrite(OUT / "m3pi1vn_panel_freshness_audit.csv", freshness)

    # -- reserve firewall (taskbook Sec. 5) --------------------------------------
    wcf1_remaining = {r["state_id"] for r in csvread(
        WCF1_OUT / "m3wcf1_remaining_protected_reserve.csv")}
    panel_ids = {r["state_id"] for r in rows}
    fw = {
        "recorded_at": now(),
        "current_protected_reserve_states": len(wcf1_remaining),
        "panel_current_reserve_overlap": sorted(panel_ids & wcf1_remaining),
        "panel_states_originating_from_original_reserve_manifest":
            sorted(panel_ids & reserve),
        "note": "16 panel states were legitimately promoted from the original "
                "70-state CF2 reserve manifest by the frozen WCF1-A panel "
                "selection; the CURRENT protected set (m3wcf1_remaining_"
                "protected_reserve.csv) excludes exactly those promoted states, "
                "and PI1VN must not touch any state in it",
        "forbidden_on_reserve": ["gradient pilot", "S1 feature", "V1 probe",
                                 "threshold replay"],
        "uc2r_protected_confirmation_states": 40,
        "planned_reserve_pilot_exposure": 0,
        "planned_confirmation_trials": 0,
    }
    if fw["panel_current_reserve_overlap"]:
        raise RuntimeError("PI1VN-X: panel overlaps the current protected reserve")
    dump(OUT / "m3pi1vn_reserve_firewall_audit.json", fw)

    # -- retired/invalid data firewall (taskbook Sec. 6) --------------------------
    dump(OUT / "m3pi1vn_retired_data_firewall.json", {
        "recorded_at": now(),
        "excluded": ["original CF2 24-state pilot-exposed panel",
                     "PI1V Attempt-1 trials", "PI1V Attempt-2 replay trials",
                     f"WA1 consumed-invalid candidate ({CONSUMED_CANDIDATE})",
                     "all retired PI1V seeds (M3-PI1V-GRAD/M3-PI1V-PROBE)",
                     "all retired WA1 seeds (M3-WA1-REF)"],
        "forbidden_attempt2_diagnostics": ["V1 best-safe coverage",
                                           "S1 best-safe coverage",
                                           "AMBIGUOUS unsafe behavior",
                                           "gradient wrong-direction result",
                                           "selected thresholds",
                                           "V1/S1 score distributions",
                                           "LOSO/LOCO results"],
        "attempt2_diagnostics_used_in_design": False,
        "consumed_candidate_in_panel": CONSUMED_CANDIDATE in
                                       {r["state_id"] for r in rows},
        "old_cf2_panel_states_in_panel":
            len({r["state_id"] for r in rows} & old_panel),
        "retired_seed_namespaces": ["M3-PI1V-GRAD", "M3-PI1V-PROBE", "M3-WA1-REF"],
    })
    if (OUT / "m3pi1vn_retired_data_firewall.json") and \
            load(OUT / "m3pi1vn_retired_data_firewall.json")["consumed_candidate_in_panel"]:
        raise RuntimeError("PI1VN-X: consumed candidate in panel")

    # -- protocol inheritance audit (taskbook Sec. 7) -------------------------------
    p1v_src = ROOT / "scripts/run_m3pi1v.py"
    inh = {
        "recorded_at": now(),
        "inheritance_mode": "the pure metric/threshold/V1/S1 machinery is "
                            "imported verbatim from scripts/run_m3pi1v.py; the "
                            "gradient/probe trial functions are line-identical "
                            "clones differing only in the seed namespaces",
        "pi1v_implementation_sha256": sha(p1v_src),
        "gradient_estimator": "hyptraj.m3d.adaptation.gradient_decision "
                              "(frozen M3-v0; via run_m3pi1v.gradient_decision)",
        "gradient_estimator_source_sha256":
            sha(ROOT / "src/hyptraj/m3d/adaptation.py"),
        "sign_convention": "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK",
        "invalid_rule": "estimator problems OR non-finite g/CI/ESS OR ESS<20 "
                        "=> ABSTAIN; no opposite direction inferred",
        "R": R, "B_grad": N_GRAD,
        "probe": {"base": N_PROBE, "selected": N_PROBE, "total": 2 * N_PROBE,
                  "batches": N_BATCH, "paired_crn": True,
                  "opposite_action_probe_samples": 0},
        "v1": {"formula": "V1 = (-0.01 - r_hat) / SE(r_hat)",
               "margin": MARGIN,
               "se_estimator": "std(batch r, ddof=1)/sqrt(20) over paired CRN batches"},
        "s1": {"formula": "abs(g_hat) / ((ci_high-ci_low)/(2*1.959963984540054))",
               "same_gradient_data": True, "probe_information_used": False},
        "metrics": {"source": "run_m3pi1v.evaluate (committed UC3 semantics)",
                    "denominators_redefined": False},
        "threshold_rule": "deploy-all sentinel; midpoints between sorted unique "
                          "finite scores; abstain-all sentinel",
        "tie_break": ["maximize deployable coverage", "lower unsafe",
                      "lower wrong", "more conservative (higher) threshold",
                      "canonical numeric"],
        "gates": GATES,
        "unique_information_rule": "V1_FULL_PASS AND (S1_FULL_PASS = NO OR "
                                   "V1_BSC - S1_BSC >= 0.05)",
        "no_invalid_threshold_reuse": True,
    }
    dump(OUT / "m3pi1vn_protocol_inheritance_audit.json", inh)

    # -- contracts (taskbook Sec. 32/36) ---------------------------------------------
    dump(CFG / "m3pi1vn_gradient_protocol.json", {
        "samples_per_trial": N_GRAD, "replicates": R, "batches": N_BATCH,
        "alpha_p": ALPHA_P,
        "estimator": "hyptraj.m3d.adaptation.gradient_decision",
        "sign_mapping": "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK",
        "invalid_rule": inh["invalid_rule"], "namespace": GRAD_NS,
    })
    dump(CFG / "m3pi1vn_probe_protocol.json", {
        "base_samples": N_PROBE, "selected_action_samples": N_PROBE,
        "total_probe_samples": 2 * N_PROBE, "batches": N_BATCH,
        "paired_crn": True, "opposite_action_probe": "FORBIDDEN",
        "adaptive_probe": "FORBIDDEN", "invalid_gradient": "ABSTAIN_NO_PROBE",
        "namespace": PROBE_NS,
    })
    dump(CFG / "m3pi1vn_v1_estimator.json", {
        "formula": "V1 = (-0.01 - r_hat) / SE(r_hat)",
        "r_hat": "M2(selected)/M2(BASE) - 1", "improvement_margin": MARGIN,
        "se_estimator": inh["v1"]["se_estimator"],
        "invalid_rule": "invalid gradient OR invalid probe OR non-finite V1 "
                        "=> ABSTAIN",
        "v1_never_changes_direction": True,
        "source": "scripts/run_m3pi1v.py (committed PI1 protocol)",
        "source_sha256": sha(p1v_src),
    })
    dump(CFG / "m3pi1vn_s1_contract.json", {
        "name": "S1_gradient_z",
        "formula": inh["s1"]["formula"],
        "same_gradient_data": True, "probe_information_used": False,
        "no_invalid_threshold_reuse": True,
        "source_sha256": sha(p1v_src),
    })
    dump(CFG / "m3pi1vn_metric_contract.json", {
        "source": "scripts/run_m3pi1v.py evaluate() (committed UC3 semantics)",
        "semantics_sha256": sha(p1v_src),
        "wrong_direction": "deployed non-ABSTAIN action != corrected truth over "
                           "W/S trials",
        "deployable_coverage": "non-ABSTAIN fraction over W/S trials",
        "nd_unsafe": "non-ABSTAIN fraction over HOLD/AMBIGUOUS trials",
        "ci_method": "Wilson 95%", "gates": GATES,
        "denominators_redefined": False,
    })
    dump(CFG / "m3pi1vn_threshold_contract.json", {
        "candidate_rule": "deploy-all-valid sentinel (min-1); all midpoints "
                          "between sorted unique finite scores; abstain-all "
                          "sentinel (max+1)",
        "selection_objective": ["enumerate all deterministic candidates",
                                "compute wrong/coverage/unsafe",
                                "retain wrong<=5% and unsafe<=20%",
                                "maximize deployable coverage",
                                "tie-break: lower unsafe, lower wrong, more "
                                "conservative (higher) threshold, canonical"],
        "best_safe_coverage": "max coverage over wrong<=5% & unsafe<=20% thresholds",
        "unique_information": {"rule": "V1_FULL_PASS AND (S1_FULL_PASS = NO OR "
                                       "V1_BSC - S1_BSC >= 0.05)",
                               "gain_threshold_pp": UNIQUE_GAIN_PP},
        "no_manual_threshold_picking": True,
        "no_invalid_pi1v_threshold_reuse": True,
    })
    dump(CFG / "m3pi1vn_gates.json", {**GATES, "unique_gain_pp": UNIQUE_GAIN_PP,
                                      "unchanged_from": "G2/UC3/PI1 frozen gates"})
    dump(CFG / "m3pi1vn_panel.json", {
        "parent": PANEL_CSV.as_posix(),
        "sha256": check_panel_hash(),
        "states": [{"state_id": r["state_id"], "truth": r["truth"],
                    "config_id": r["config_id"], "s2": float(r["s2"]),
                    "source_stage": r["source_stage"]} for r in rows],
    })
    dump(CFG / "m3pi1vn_seeds.json", {
        "gradient_namespace": GRAD_NS, "probe_namespace": PROBE_NS, "R": R,
        "derivation": "sha256(namespace|state_id|replicate) -> [1,2^31-1]",
    })
    persistence_contract = {
        "recorded_at": now(),
        "inherited_from": "repaired PI1VR0/WA1R persistence (non-circular hashes)",
        "module": "src/hyptraj/m3wa1r/persistence.py",
        "module_sha256": sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
        "order": ["1. validate filesystem-safe path", "2. durable STARTED ledger",
                  "3. execute gradient calculation",
                  "4. execute finite-action probe if applicable",
                  "5. build canonical non-circular payload", "6. validate schema",
                  "7. compute hashes", "8. temp write", "9. flush + fsync",
                  "10. atomic rename", "11. fsync parent directory",
                  "12. verify final durable record/hash", "13. ledger COMPLETE"],
        "failure_policy": "scientific calculation started + durable COMPLETE "
                          "failure => CONSUMED_INVALID => PI1VN-X => STOP; no replay",
        "trial_ledger": TRIAL_LEDGER.as_posix(),
    }
    dump(CFG / "m3pi1vn_persistence.json", persistence_contract)
    dump(OUT / "m3pi1vn_persistence_contract.json", persistence_contract)
    dump(OUT / "m3pi1vn_gradient_contract.json", {
        "R": R, "B_grad": N_GRAD, "batches": N_BATCH, "alpha_p": ALPHA_P,
        "estimator": inh["gradient_estimator"],
        "estimator_source_sha256": inh["gradient_estimator_source_sha256"],
        "sign_convention": inh["sign_convention"],
        "invalid_rule": inh["invalid_rule"],
        "planned_trials": 24 * R,
        "no_state_specific_extra_repetitions": True,
    })
    dump(OUT / "m3pi1vn_probe_contract.json", {
        "base_samples": N_PROBE, "selected_action_samples": N_PROBE,
        "total_probe_samples": 2 * N_PROBE, "probe_le_gradient_budget":
            2 * N_PROBE <= N_GRAD,
        "total_online_le_2x": True, "batches": N_BATCH, "paired_crn": True,
        "opposite_action_probe_samples": 0, "no_adaptive_probe": True,
        "single_budget_level": True,
    })
    dump(OUT / "m3pi1vn_v1_estimator_contract.json", load(CFG / "m3pi1vn_v1_estimator.json"))
    dump(OUT / "m3pi1vn_s1_contract.json", load(CFG / "m3pi1vn_s1_contract.json"))
    dump(OUT / "m3pi1vn_metric_contract.json", load(CFG / "m3pi1vn_metric_contract.json"))
    dump(OUT / "m3pi1vn_threshold_contract.json", load(CFG / "m3pi1vn_threshold_contract.json"))

    # -- seeds (taskbook Sec. 10) -------------------------------------------------------
    prior_ns = {n for n in R1.prior_namespaces()
                if not n.startswith("M3-PI1VN")}   # self-exclusion
    prior_seeds = _prior_recorded_seeds()
    planned_g = {f"{r['state_id']}|rep{rep}": seed(GRAD_NS, r["state_id"], rep)
                 for r in rows for rep in range(R)}
    planned_p = {f"{r['state_id']}|rep{rep}": seed(PROBE_NS, r["state_id"], rep)
                 for r in rows for rep in range(R)}
    g_vals, p_vals = set(planned_g.values()), set(planned_p.values())
    coll = sorted((g_vals | p_vals) & prior_seeds)
    retired_seeds = _retired_seed_values()
    coll_retired = sorted((g_vals | p_vals) & retired_seeds)
    if GRAD_NS in prior_ns or PROBE_NS in prior_ns or coll or coll_retired \
            or (g_vals & p_vals):
        raise RuntimeError("PI1VN-X: seed collision with prior/retired stages")
    seed_doc = {
        "recorded_at": now(),
        "gradient_namespace": GRAD_NS,
        "probe_namespace": PROBE_NS,
        "derivation": "sha256(namespace|state_id|replicate) -> [1,2^31-1]",
        "R": R,
        "planned_gradient_seeds": planned_g,
        "planned_probe_seeds": planned_p,
        "collision_with_all_prior": coll,
        "collision_with_retired_seeds": coll_retired,
        "gradient_probe_disjoint": not (g_vals & p_vals),
        "frozen_before_first_simulator_call": True,
    }
    dump(OUT / "m3pi1vn_seed_manifest.json", seed_doc)
    dump(OUT / "m3pi1vn_seed_manifest_hash.json", {
        "recorded_at": now(),
        "seed_manifest_sha256": sha_json({"gradient": planned_g, "probe": planned_p}),
        "gradient_seeds_sha256": sha_json(planned_g),
        "probe_seeds_sha256": sha_json(planned_p),
        "trials_planned": 24 * R,
    })

    # -- accounting preregistration -------------------------------------------------------
    dump(OUT / "m3pi1vn_sample_accounting_prereg.json", {
        "N_trials": 24 * R,
        "max_gradient_samples": 24 * R * N_GRAD,
        "max_probe_samples": 24 * R * 2 * N_PROBE,
        "max_total_online_samples": 24 * R * N_GRAD + 24 * R * 2 * N_PROBE,
        "total_le_2x": True,
    })

    # -- source manifest + prereg hashes ---------------------------------------------------
    source_paths = [
        "results/phase_m3wcf1/summary/m3wcf1_final_verdict.json",
        "results/phase_m3wcf1/summary/m3wcf1_fresh_development_panel.csv",
        "results/phase_m3wcf1/summary/m3wcf1_fresh_development_panel_hash.json",
        "results/phase_m3wcf1/summary/m3wcf1_pref_summary.json",
        "results/phase_m3wcf1/reference/reference_manifest.json",
        "results/phase_m3wcf1/summary/m3wcf1_remaining_protected_reserve.csv",
        "results/phase_m3wa1r/summary/m3wa1r_final_verdict.json",
        "results/phase_m3wa1/summary/m3wa1_final_verdict.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_final_verdict.json",
        "results/phase_m3pi1vr0/summary/m3pi1vr0_pi1v_scientific_status.json",
        "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv",
        "configs/phase_m3cf1n/m3cf1n_configs.json",
        "scripts/run_m3pi1v.py",
        "src/hyptraj/m3d/adaptation.py",
        "src/hyptraj/m3wa1r/persistence.py",
    ]
    dump(OUT / "m3pi1vn_source_manifest.json", {
        "base_commit": git_commit(), "recorded_at": now(),
        "simulator_samples_before_pilot": 0,
        "entries": [{"path": p, "sha256": sha(ROOT / p), "read_only": True}
                    for p in source_paths],
    })
    prereg_paths = [CFG / n for n in (
        "m3pi1vn_panel.json", "m3pi1vn_gradient_protocol.json",
        "m3pi1vn_probe_protocol.json", "m3pi1vn_v1_estimator.json",
        "m3pi1vn_s1_contract.json", "m3pi1vn_metric_contract.json",
        "m3pi1vn_threshold_contract.json", "m3pi1vn_seeds.json",
        "m3pi1vn_persistence.json", "m3pi1vn_gates.json")] + [OUT / n for n in (
        "m3pi1vn_parent_audit.json", "m3pi1vn_panel_hash_audit.json",
        "m3pi1vn_panel_freshness_audit.csv", "m3pi1vn_reserve_firewall_audit.json",
        "m3pi1vn_retired_data_firewall.json",
        "m3pi1vn_protocol_inheritance_audit.json", "m3pi1vn_gradient_contract.json",
        "m3pi1vn_probe_contract.json", "m3pi1vn_v1_estimator_contract.json",
        "m3pi1vn_s1_contract.json", "m3pi1vn_metric_contract.json",
        "m3pi1vn_threshold_contract.json", "m3pi1vn_seed_manifest.json",
        "m3pi1vn_seed_manifest_hash.json", "m3pi1vn_persistence_contract.json",
        "m3pi1vn_sample_accounting_prereg.json", "m3pi1vn_source_manifest.json")]
    dump(OUT / "m3pi1vn_prereg_hashes.json", {
        "recorded_at": now(),
        "gradient_trials_before_freeze": "NONE",
        "probe_trials_before_freeze": "NONE",
        "threshold": None,
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                  for p in prereg_paths],
    })

    write_stop_report(rows, comp, seed_doc, inh)
    print("PI1VN prepare: COMPLETE -- preregistration frozen; STOP before pilot")


def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3pi1vn"
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


def _retired_seed_values() -> set[int]:
    vals: set[int] = set()
    for rel in ("results/phase_m3pi1vr0/summary/m3pi1vr0_retired_candidate_seed_manifest.json",
                "results/phase_m3pi1v/summary/m3pi1v_seed_manifest.json",
                "results/phase_m3wa1r/summary/m3wa1r_retired_candidate_seed_manifest.json"
                if (ROOT / "results/phase_m3wa1r/summary/"
                    "m3wa1r_retired_candidate_seed_manifest.json").exists()
                else "results/phase_m3wa1/summary/m3wa1_seed_manifest.json"):
        p = ROOT / rel
        if p.exists():
            d = load(p)
            for k, v in d.items():
                if isinstance(v, dict) and ("seed" in k or "seeds" in k or
                                            "gradient_seeds" in k or "probe_seeds" in k
                                                or "seed_key" in k):
                    stack = [v]
                    while stack:
                        o = stack.pop()
                        if isinstance(o, dict):
                            stack.extend(o.values())
                        elif isinstance(o, list):
                            for x in o:
                                if isinstance(x, int):
                                    vals.add(x)
                                elif isinstance(x, list):
                                    stack.append(x)
    return vals


def write_stop_report(rows, comp, seed_doc, inh) -> None:
    fw = load(OUT / "m3pi1vn_reserve_firewall_audit.json")
    txt = f"""M3-PI1VN PREREG STATUS:
COMPLETE

PARENT:
WCF1 = WCF1-A
PI1V valid verdict = PI1V-X

FRESH DEVELOPMENT PANEL:
states = 24
W = 8
S = 8
ND = 8
hash = {check_panel_hash()}
hash matches WCF1 = YES
pilot exposure = 0
probe exposure = 0

PROTECTED RESERVE:
states = {fw['current_protected_reserve_states']}
pilot exposure = 0

INVALID / RETIRED DATA:
PI1V Attempt-2 used = NO
original CF2 panel used = NO
WA1 consumed state used = NO
retired seeds used = NO

GRADIENT:
R = {R}
B_grad = 20000
sign rule = g_hat<0 WIDEN / g_hat>0 SHRINK
protocol hash = {inh['gradient_estimator_source_sha256']}

PROBE:
BASE = 10000
selected action = 10000
total = 20000
paired CRN batches = 20
opposite action = 0
adaptive probe = NO

ONLINE COST:
per valid trial max = 40000
<=2x B_grad = YES

V1:
formula = (-0.01-r_hat)/SE(r_hat)
margin = -0.01
estimator hash = {inh['pi1v_implementation_sha256']}
SE estimator hash = {inh['pi1v_implementation_sha256']}

S1:
definition hash = {inh['pi1v_implementation_sha256']}
same gradient data = YES
probe information used = NO

METRICS:
wrong semantics frozen = YES
coverage semantics frozen = YES
unsafe semantics frozen = YES

GATES:
wrong <=5%
coverage >=75%
unsafe <=20%

UNIQUE INFORMATION:
S1 full-pass absent
OR
V1 best-safe coverage - S1 best-safe coverage >=5pp

THRESHOLD RULE:
deterministic = YES
invalid PI1V threshold reused = NO

SEEDS:
gradient namespace = M3-PI1VN-GRAD
probe namespace = M3-PI1VN-PROBE
planned trials = 192
collisions = 0
hash-locked = YES

PERSISTENCE:
hardened = ENABLED
STARTED-before-simulator = YES
non-circular hash = YES
consumed-invalid replay = FORBIDDEN

MAX SAMPLES:
gradient = 3840000
probe = 3840000
total = 7680000

CONFIRMATION:
authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN PI1VN
"""
    (DOC / "M3_PI1VN_Pregistration.md").write_text(
        "# M3-PI1VN Preregistration\n\nFrozen before any simulator call.\n\n```\n"
        + txt + "\n```\n", encoding="utf-8")
    (OUT / "m3pi1vn_prereg_status.txt").write_text(txt, encoding="utf-8")
    print(txt)


def verify_prereg() -> None:
    rec = load(OUT / "m3pi1vn_prereg_hashes.json")
    for e in rec["files"]:
        p = ROOT / e["path"]
        if not p.exists() or sha(p) != e["sha256"]:
            raise RuntimeError(f"PI1VN-X: prereg hash drift at {e['path']}")


# --------------------------------------------------------------------------
# stage: pilot (the only simulator-consuming stage)
# --------------------------------------------------------------------------

def _trial_record_sha(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != HASH_FIELD}
    return scientific_payload_hash(rec)


def _pre_hash_validate(rec: dict) -> None:
    required = {"schema", "state_id", "rep_id", "truth", "config_id", "gradient",
                "selected_action", "probe", "V1", "S1", "sample_counts",
                "panel_hash", "protocol_hashes"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["schema"] != "m3pi1vn_trial_v1":
        raise ValueError("schema validation failed; wrong schema")
    if rec["probe"].get("opposite_action_probe_samples", 0) != 0:
        raise ValueError("schema validation failed; opposite action was probed")
    if HASH_FIELD in rec:
        raise ValueError("pre-hash schema must not contain a self-hash field")


def _completed_trials() -> set[str]:
    return {e["state_id"] for e in ledger_entries(TRIAL_LEDGER)
            if e.get("status") == "COMPLETE"}


def _check_recoverable() -> None:
    counts: dict[str, Counter] = {}
    for e in ledger_entries(TRIAL_LEDGER):
        counts.setdefault(e.get("state_id"), Counter())[e.get("status")] += 1
    for rid, c in counts.items():
        if c.get("CONSUMED_INVALID") or c.get("STARTED", 0) != c.get("COMPLETE", 0):
            raise RuntimeError(
                f"PI1VN-X: trial {rid} began without a durable COMPLETE record "
                "(CONSUMED_INVALID policy); no replay in the same stage")


def pilot() -> None:
    verify_prereg()
    check_panel_hash()
    rows = panel_rows()
    TRIALS.mkdir(parents=True, exist_ok=True)
    if (TRIALS / "trial_manifest.json").exists():
        raise RuntimeError("PI1VN-X: pilot already sealed")
    if TRIAL_LEDGER.exists():
        _check_recoverable()
    prereg = load(OUT / "m3pi1vn_prereg_hashes.json")
    source_hashes = {e["path"]: e["sha256"] for e in prereg["files"]}
    panel_hash = check_panel_hash()
    grad_proto_hash = sha(CFG / "m3pi1vn_gradient_protocol.json")
    probe_proto_hash = sha(CFG / "m3pi1vn_probe_protocol.json")
    seeds = load(OUT / "m3pi1vn_seed_manifest.json")
    done = _completed_trials()
    for r in rows:
        st = state_for(r)
        safe_sid = safe_fs_id(r["state_id"])
        out_dir = TRIALS / safe_sid
        for rep in range(R):
            rid = f"{r['state_id']}__rep{rep}"
            if rid in done:
                continue

            def compute(r=r, rep=rep, st=st):
                ledger_append(GRAD_LEDGER, {"state_id": rid, "phase": "GRADIENT",
                                            "status": "STARTED", "timestamp": now()})
                g = gradient_trial(st, seeds["planned_gradient_seeds"][f"{r['state_id']}|rep{rep}"])
                ledger_append(GRAD_LEDGER, {"state_id": rid, "phase": "GRADIENT",
                                            "status": "EXECUTED", "valid": g["valid"],
                                            "timestamp": now()})
                if g["valid"]:
                    ledger_append(PROBE_LEDGER, {"state_id": rid, "phase": "PROBE",
                                                 "status": "STARTED", "timestamp": now()})
                    pr = paired_probe(st, g["sign"],
                                      seeds["planned_probe_seeds"][f"{r['state_id']}|rep{rep}"])
                    ledger_append(PROBE_LEDGER, {"state_id": rid, "phase": "PROBE",
                                                 "status": "EXECUTED",
                                                 "valid": pr["valid"],
                                                 "timestamp": now()})
                else:
                    pr = {"seed": seeds["planned_probe_seeds"][f"{r['state_id']}|rep{rep}"],
                          "namespace": PROBE_NS, "executed": False,
                          "samples_base": 0, "samples_action": 0,
                          "opposite_action_probe_samples": 0,
                          "paired_batches": N_BATCH, "r_hat": None,
                          "se_r_hat": None, "valid": False,
                          "reason": "INVALID_GRADIENT_NO_PROBE"}
                s1 = s1_score(g["g_hat"], g["g_ci_low"], g["g_ci_high"]) \
                    if g["valid"] else None
                v1 = v1_score(pr["r_hat"], pr["se_r_hat"]) \
                    if (g["valid"] and pr.get("valid")) else None
                total = N_GRAD + (2 * N_PROBE if pr.get("executed") else 0)
                return {
                    "schema": "m3pi1vn_trial_v1",
                    "recorded_at": now(),
                    "state_id": r["state_id"],
                    "rep_id": rep,
                    "config_id": r["config_id"],
                    "s2": float(r["s2"]),
                    "truth": r["truth"],
                    "truth_group": ("W" if r["truth"] == "WIDEN" else
                                    "S" if r["truth"] == "SHRINK" else "ND"),
                    "family": family_of(r),
                    "gradient": {**g, "protocol_hash": grad_proto_hash},
                    "selected_action": g["sign"] if g["valid"] else None,
                    "probe": {**pr, "protocol_hash": probe_proto_hash},
                    "V1": v1,
                    "S1": s1,
                    "sample_counts": {
                        "gradient": N_GRAD,
                        "probe_base": pr.get("samples_base", 0),
                        "probe_action": pr.get("samples_action", 0),
                        "invalid_gradient_saved_probe":
                            0 if pr.get("executed") else 2 * N_PROBE,
                        "opposite_action_probe_samples": 0,
                        "total": total,
                    },
                    "panel_hash": panel_hash,
                    "protocol_hashes": {"gradient": grad_proto_hash,
                                        "probe": probe_proto_hash,
                                        "source": source_hashes},
                }

            result = run_trial_transactional(
                rid, out_dir / f"rep{rep}.json", compute,
                ledger_path=TRIAL_LEDGER, pre_hash_validator=_pre_hash_validate,
                base_entry={"panel_state_id": r["state_id"], "rep_id": rep,
                            "truth": r["truth"], "config_id": r["config_id"],
                            "seed_namespace": GRAD_NS,
                            "seed": seeds["planned_gradient_seeds"][f"{r['state_id']}|rep{rep}"]},
                run_uuid=uuid.uuid4().hex)
            if result["status"] != "COMPLETE":
                raise RuntimeError(
                    f"PI1VN-X: trial not durably COMPLETE for {rid}: {result}")
            stored = load(out_dir / f"rep{rep}.json")
            print(f"trial {rid}: grad_valid={stored['gradient']['valid']} "
                  f"probe_valid={stored['probe'].get('valid')} "
                  f"V1={stored['V1']} S1={stored['S1']}", flush=True)
    _seal_pilot(rows)


def _seal_pilot(rows) -> None:
    done = _completed_trials()
    expected = {f"{r['state_id']}__rep{rep}" for r in rows for rep in range(R)}
    if done != expected:
        raise RuntimeError(f"PI1VN-X: pilot incomplete ({len(done)}/{len(expected)})")
    recs = _load_trial_records(rows)
    grad_total = sum(x["sample_counts"]["gradient"] for x in recs)
    base_total = sum(x["sample_counts"]["probe_base"] for x in recs)
    act_total = sum(x["sample_counts"]["probe_action"] for x in recs)
    total = grad_total + base_total + act_total
    dump(TRIALS / "trial_manifest.json", {
        "sealed_at": now(),
        "states": 24, "R": R,
        "trials_expected": 24 * R,
        "trials_complete": len(recs),
        "consumed_invalid": 0,
        "sample_accounting": {
            "gradient_samples": grad_total,
            "base_probe_samples": base_total,
            "selected_action_probe_samples": act_total,
            "total_samples": total,
            "max_total_online_samples": 2 * 24 * R * N_GRAD,
            "total_le_2x": total <= 2 * 24 * R * N_GRAD,
        },
        "opposite_action_probe_samples": sum(
            x["probe"].get("opposite_action_probe_samples", 0) for x in recs),
        "trial_file_hashes": {f"{x['state_id']}__rep{x['rep_id']}":
                              record_file_hash(TRIALS / safe_fs_id(x["state_id"])
                                               / f"rep{x['rep_id']}.json")
                              for x in recs},
    })
    print(f"PI1VN pilot sealed: {len(recs)} trials, {total:,} online samples "
          f"(<=2x: {total <= 2 * 24 * R * N_GRAD})")


def _load_trial_records(rows) -> list[dict]:
    out = []
    for r in rows:
        for rep in range(R):
            p = TRIALS / safe_fs_id(r["state_id"]) / f"rep{rep}.json"
            rec = load(p)
            if scientific_payload_hash(rec) != rec[HASH_FIELD]:
                raise RuntimeError(f"PI1VN-X: record payload hash mismatch {p}")
            out.append(rec)
    return out


# --------------------------------------------------------------------------
# stage: analyze
# --------------------------------------------------------------------------

def analyze() -> None:
    verify_prereg()
    check_panel_hash()
    if not (TRIALS / "trial_manifest.json").exists():
        raise RuntimeError("pilot must be sealed before analysis")
    rows = panel_rows()
    recs = _load_trial_records(rows)
    by_id = {(x["state_id"], x["rep_id"]): x for x in recs}
    trials = []
    for r in rows:
        for rep in range(R):
            x = by_id[(r["state_id"], rep)]
            trials.append({
                "state_id": x["state_id"], "rep_id": x["rep_id"],
                "config_id": x["config_id"], "truth": x["truth"],
                "family": x["family"],
                "gradient_valid": x["gradient"]["valid"],
                "probe_valid": bool(x["probe"].get("valid")),
                "selected_action": x["selected_action"],
                "V1": x["V1"], "S1": x["S1"],
                "r_hat": x["probe"].get("r_hat"),
                "se_r_hat": x["probe"].get("se_r_hat"),
                "gradient_seed": x["gradient"]["seed"],
                "probe_seed": x["probe"].get("seed"),
            })

    # direction sanity (inherited Sign-No-Abstain audit)
    sanity = direction_sanity(trials)
    dump(OUT / "m3pi1vn_direction_sanity.json", sanity)
    verdict = None
    if sanity["gate"] != "PASS":
        verdict = "PI1VN-D"

    # score tables
    _score_csv(OUT / "m3pi1vn_v1_trials.csv", trials, "V1")
    _score_csv(OUT / "m3pi1vn_s1_trials.csv", trials, "S1")

    fronts, selected = {}, {}
    if verdict is None:
        for family in ("V1", "S1"):
            fr = frontier(trials, family)
            fronts[family] = fr
            csvwrite(OUT / f"m3pi1vn_{family.lower()}_threshold_frontier.csv", fr)
            selected[family] = select_threshold(fr)
        dump(OUT / "m3pi1vn_selected_thresholds.json", {
            "selected_V1_threshold": selected["V1"]["threshold"] if selected["V1"] else None,
            "selected_S1_threshold": selected["S1"]["threshold"] if selected["S1"] else None,
            "selection_rule": load(CFG / "m3pi1vn_threshold_contract.json")["selection_objective"],
            "selection_rule_sha256": sha(CFG / "m3pi1vn_threshold_contract.json"),
            "frontier_hashes": {f: sha(OUT / f"m3pi1vn_{f.lower()}_threshold_frontier.csv")
                                for f in ("V1", "S1")},
            "panel_hash": check_panel_hash(),
            "retuning_forbidden_after_this_point": True,
        })
        v1_sel = _family_metrics(trials, "V1", selected["V1"])
        s1_sel = _family_metrics(trials, "S1", selected["S1"])
        v1_full = bool(selected["V1"] and selected["V1"]["full_gate_pass"])
        s1_full = bool(selected["S1"] and selected["S1"]["full_gate_pass"])
        v1_bsc = best_safe_coverage(fronts["V1"])
        s1_bsc = best_safe_coverage(fronts["S1"])
        gain = v1_bsc - s1_bsc
        unique = bool(v1_full and (not s1_full or gain >= UNIQUE_GAIN_PP))
        dump(OUT / "m3pi1vn_primary_metrics.json", {
            "recorded_at": now(),
            "label": "reference-stratified development metrics; no natural "
                     "prevalence claim",
            "direction_sanity": sanity,
            "V1": v1_sel, "S1": s1_sel,
            "V1_FULL_PASS": v1_full, "S1_FULL_PASS": s1_full,
            "sample_accounting": load(TRIALS / "trial_manifest.json")["sample_accounting"],
        })
        dump(OUT / "m3pi1vn_information_gain.json", {
            "V1_FULL_PASS": v1_full, "S1_FULL_PASS": s1_full,
            "V1_BEST_SAFE_COVERAGE": v1_bsc, "S1_BEST_SAFE_COVERAGE": s1_bsc,
            "coverage_gain": gain, "gain_threshold_pp": UNIQUE_GAIN_PP,
            "gain_ge_5pp": bool(gain >= UNIQUE_GAIN_PP),
            "unique_information_criterion": "YES" if unique else "NO",
        })
        if not v1_full:
            verdict = "PI1VN-C"
        elif not unique:
            verdict = "PI1VN-B"
        else:
            verdict = "PI1VN-A"

    _state_level_audit(trials, selected if verdict != "PI1VN-D" else {})
    _family_stratified(trials, selected if verdict != "PI1VN-D" else {})
    _loso(trials)
    _loco(trials)
    dump(OUT / "m3pi1vn_truth_stratified_metrics.json", {
        "label": "reference-stratified development metrics",
        "V1": (load(OUT / "m3pi1vn_primary_metrics.json").get("V1", {})
               .get("truth_strata", {}) if (OUT / "m3pi1vn_primary_metrics.json").exists()
               else {}),
        "note": "8W/8S/8ND panel by design; deployment fractions are not "
                "population rates",
    })
    _persistence_audit(recs, rows)
    _finalize(sanity, verdict)


def _family_metrics(trials, family, sel):
    if sel is None:
        return {"selected_threshold": None, "pass": False, "truth_strata": {},
                "note": "no safety-compliant threshold exists"}
    actions = [policy_action(t, family, sel["threshold"]) for t in trials]
    m = evaluate(trials, actions)
    m["selected_threshold"] = sel["threshold"]
    m["full_gate_pass"] = sel["full_gate_pass"]
    m["truth_strata"] = {g: m.pop(f"truth_{g}") for g in
                         ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS")}
    return m


def _score_csv(path, rows, family):
    out = []
    for r in rows:
        out.append({
            "state_id": r["state_id"], "rep_id": r["rep_id"],
            "config_id": r["config_id"], "truth": r["truth"],
            "family": r["family"],
            "gradient_valid": r["gradient_valid"], "probe_valid": r["probe_valid"],
            "selected_action": r["selected_action"] or "",
            family: "" if r[family] is None else repr(float(r[family])),
            "r_hat": "" if r["r_hat"] is None else repr(float(r["r_hat"])),
            "se_r_hat": "" if r["se_r_hat"] is None else repr(float(r["se_r_hat"])),
            "gradient_seed": r["gradient_seed"],
            "probe_seed": r["probe_seed"] if r["probe_seed"] is not None else "",
        })
    csvwrite(path, out)


def _state_level_audit(trials, selected) -> None:
    out = []
    for family in ("V1", "S1"):
        sel = selected.get(family)
        t = sel["threshold"] if sel else None
        for sid in sorted({x["state_id"] for x in trials}):
            sub = [x for x in trials if x["state_id"] == sid]
            acts = [policy_action(x, family, t) if t is not None else "ABSTAIN"
                    for x in sub]
            dep = [(x, a) for x, a in zip(sub, acts) if x["truth"] in DEPLOYABLE]
            deployed = [(x, a) for x, a in dep if a != "ABSTAIN"]
            wrong = sum(1 for x, a in dep if a != "ABSTAIN" and a != x["truth"])
            non = [(x, a) for x, a in zip(sub, acts) if x["truth"] in NON_DEPLOYABLE]
            unsafe = sum(1 for x, a in non if a != "ABSTAIN")
            v1s = [x["V1"] for x in sub if x["V1"] is not None]
            s1s = [x["S1"] for x in sub if x["S1"] is not None]
            out.append({
                "family": family, "state_id": sid,
                "config_id": sub[0]["config_id"], "truth": sub[0]["truth"],
                "trials": len(sub), "threshold": "" if t is None else t,
                "deployment_rate": len(deployed) / len(sub),
                "wrong_direction_rate": (wrong / len(dep)) if dep else "",
                "unsafe_rate": (unsafe / len(non)) if non else "",
                "gradient_invalid_trials": sum(1 for x in sub if not x["gradient_valid"]),
                "probe_invalid_trials": sum(1 for x in sub if x["gradient_valid"]
                                            and not x["probe_valid"]),
                "V1_mean": float(np.mean(v1s)) if v1s else "",
                "S1_mean": float(np.mean(s1s)) if s1s else "",
            })
    csvwrite(OUT / "m3pi1vn_state_level_policy_audit.csv", out)


def _family_stratified(trials, selected) -> None:
    out = {"label": "reference-stratified development metrics; family strata "
                    "reported separately (taskbook Sec. 29)"}
    for family in ("V1", "S1"):
        sel = selected.get(family)
        t = sel["threshold"] if sel else None
        strata = {}
        for fam_name in ("legacy/current corrected", "CF1N replacement", "WCF1 new"):
            sub = [x for x in trials if x["family"] == fam_name]
            if not sub:
                continue
            acts = [policy_action(x, family, t) if t is not None else "ABSTAIN"
                    for x in sub]
            m = evaluate(sub, acts)
            strata[fam_name] = {k: m[k] for k in
                                ("deployable_trials", "wrong", "wrong_direction_rate",
                                 "deployable_coverage", "unsafe_rate")}
        out[family] = strata
    dump(OUT / "m3pi1vn_family_stratified_metrics.json", out)


def _loso(trials) -> None:
    out = []
    for family in ("V1", "S1"):
        for hid in sorted({x["state_id"] for x in trials}):
            train = [x for x in trials if x["state_id"] != hid]
            test = [x for x in trials if x["state_id"] == hid]
            fr = frontier(train, family)
            sel = select_threshold(fr)
            row = {"family": family, "held_out_state_id": hid,
                   "selected_threshold": sel["threshold"] if sel else "",
                   "threshold_found": sel is not None}
            if sel is not None:
                acts = [policy_action(x, family, sel["threshold"]) for x in test]
                m = evaluate(test, acts)
                row.update({
                    "heldout_wrong_direction_rate": m["wrong_direction_rate"]
                    if m["deployable_trials"] else "",
                    "heldout_deployment_rate": m["deployable_coverage"]
                    if m["deployable_trials"] else "",
                    "heldout_unsafe_rate": m["unsafe_rate"]
                    if m["nondeployable_trials"] else ""})
            out.append(row)
    csvwrite(OUT / "m3pi1vn_loso_diagnostic.csv", out)


def _loco(trials) -> None:
    out = []
    for family in ("V1", "S1"):
        for cid in sorted({x["config_id"] for x in trials}):
            train = [x for x in trials if x["config_id"] != cid]
            test = [x for x in trials if x["config_id"] == cid]
            fr = frontier(train, family)
            sel = select_threshold(fr)
            row = {"family": family, "held_out_config": cid,
                   "selected_threshold": sel["threshold"] if sel else "",
                   "threshold_found": sel is not None}
            if sel is not None:
                acts = [policy_action(x, family, sel["threshold"]) for x in test]
                m = evaluate(test, acts)
                row.update({
                    "heldout_wrong_direction_rate": m["wrong_direction_rate"]
                    if m["deployable_trials"] else "",
                    "heldout_deployment_rate": m["deployable_coverage"]
                    if m["deployable_trials"] else "",
                    "heldout_unsafe_rate": m["unsafe_rate"]
                    if m["nondeployable_trials"] else ""})
            out.append(row)
    csvwrite(OUT / "m3pi1vn_loco_diagnostic.csv", out)


def _persistence_audit(recs, rows) -> None:
    entries = ledger_entries(TRIAL_LEDGER)
    counts: dict[str, Counter] = {}
    for e in entries:
        counts.setdefault(e.get("state_id"), Counter())[e.get("status")] += 1
    problems = []
    expected = {f"{r['state_id']}__rep{rep}" for r in rows for rep in range(R)}
    for rid in expected:
        c = counts.get(rid, Counter())
        if c.get("STARTED") != 1 or c.get("COMPLETE") != 1:
            problems.append(f"{rid}: STARTED={c.get('STARTED')} "
                            f"COMPLETE={c.get('COMPLETE')}")
    manifest = load(TRIALS / "trial_manifest.json")
    hash_ok = all(
        e.get("record_file_hash") == record_file_hash(
            TRIALS / safe_fs_id(str(e.get("panel_state_id")))
            / f"rep{e.get('rep_id')}.json")
        for e in entries if e.get("status") == "COMPLETE")
    rec_ok = all(scientific_payload_hash(x) == x[HASH_FIELD] for x in recs)
    audit = {"recorded_at": now(), "ledger_entries": len(entries),
             "trials_complete": len(expected),
             "consumed_invalid": sum(1 for e in entries
                                     if e.get("status") == "CONSUMED_INVALID"),
             "output_hash_match": hash_ok, "payload_hash_match": rec_ok,
             "problems": problems,
             "canonical_hashes": "PASS" if not problems and hash_ok and rec_ok
             else "FAIL"}
    dump(OUT / "m3pi1vn_persistence_audit.json", audit)


def _finalize(sanity, verdict) -> str:
    rows = panel_rows()
    recs = _load_trial_records(rows)
    audit = load(OUT / "m3pi1vn_persistence_audit.json")
    manifest = load(TRIALS / "trial_manifest.json")
    fw = load(OUT / "m3pi1vn_reserve_firewall_audit.json")
    gain = load(OUT / "m3pi1vn_information_gain.json") \
        if (OUT / "m3pi1vn_information_gain.json").exists() else {}
    prim = load(OUT / "m3pi1vn_primary_metrics.json") \
        if (OUT / "m3pi1vn_primary_metrics.json").exists() else {}
    if audit["canonical_hashes"] != "PASS":
        verdict = "PI1VN-X"
    if verdict is None:
        verdict = P1V.verdict_priority(
            persistence_ok=audit["canonical_hashes"] == "PASS",
            direction_pass=sanity["gate"] == "PASS",
            v1_full_pass=bool(gain.get("V1_FULL_PASS")),
            unique_information=gain.get("unique_information_criterion") == "YES")
    final = {
        "status": "COMPLETE",
        "verdict": verdict,
        "recorded_at": now(),
        "parent": {"WCF1": "WCF1-A"},
        "fresh_panel": {"states": 24, "hash_verified": True, "panel_changed": False,
                        "sha256": check_panel_hash()},
        "trials": {"expected": 192, "complete": manifest["trials_complete"],
                   "consumed_invalid": manifest["consumed_invalid"]},
        "samples": {
            "gradient": manifest["sample_accounting"]["gradient_samples"],
            "probe": manifest["sample_accounting"]["base_probe_samples"]
                     + manifest["sample_accounting"]["selected_action_probe_samples"],
            "total": manifest["sample_accounting"]["total_samples"],
            "le_2x": "PASS" if manifest["sample_accounting"]["total_le_2x"] else "FAIL"},
        "direction": {
            "deployable_trials": sanity["deployable_trials"],
            "valid_gradient": sanity["valid_gradient_trials"],
            "wrong": sanity["wrong_selected_directions"],
            "wrong_rate": sanity["wrong_direction_rate"],
            "gate_le_5pct": sanity["gate"]},
        "V1": {
            "valid_scores": sum(1 for x in recs if x["V1"] is not None),
            "selected_threshold": prim.get("V1", {}).get("selected_threshold"),
            "wrong": prim.get("V1", {}).get("wrong"),
            "coverage": prim.get("V1", {}).get("deployable_coverage"),
            "unsafe": prim.get("V1", {}).get("unsafe_rate"),
            "V1_FULL_PASS": gain.get("V1_FULL_PASS"),
            "best_safety_compliant_coverage": gain.get("V1_BEST_SAFE_COVERAGE")},
        "S1": {
            "selected_threshold": prim.get("S1", {}).get("selected_threshold"),
            "wrong": prim.get("S1", {}).get("wrong"),
            "coverage": prim.get("S1", {}).get("deployable_coverage"),
            "unsafe": prim.get("S1", {}).get("unsafe_rate"),
            "S1_FULL_PASS": gain.get("S1_FULL_PASS"),
            "best_safety_compliant_coverage": gain.get("S1_BEST_SAFE_COVERAGE")},
        "comparison": {
            "coverage_gain": gain.get("coverage_gain"),
            "gain_ge_5pp": gain.get("gain_ge_5pp"),
            "unique_information_criterion": gain.get("unique_information_criterion")},
        "truth_strata": {
            "W": prim.get("V1", {}).get("truth_strata", {}).get("WIDEN"),
            "S": prim.get("V1", {}).get("truth_strata", {}).get("SHRINK"),
            "HOLD_unsafe": (prim.get("V1", {}).get("truth_strata", {})
                            .get("HOLD") or {}).get("unsafe_rate"),
            "AMBIGUOUS_unsafe": (prim.get("V1", {}).get("truth_strata", {})
                                 .get("AMBIGUOUS") or {}).get("unsafe_rate")},
        "robustness": {"state_level_audit": "COMPLETE", "LOSO": "COMPLETE",
                       "LOCO": "COMPLETE", "family_stratified": "COMPLETE"},
        "persistence": {
            "hashes": audit["canonical_hashes"],
            "ledger": "PASS" if not audit["problems"] and not audit["consumed_invalid"]
            else "FAIL",
            "manifest": "PASS" if manifest["trials_complete"] == 192 else "FAIL"},
        "invalid_retired_data": {
            "PI1V Attempt-2 used": False,
            "retired states used": False,
            "retired seeds used": False},
        "protected_reserve": {"pilot_exposure": 0},
        "confirmation": {"trials": 0, "authorized": False},
        **boundary_block(),
        "secondary_route_signal": ({"S1_FULL_PASS": gain.get("S1_FULL_PASS")}
                                   if verdict == "PI1VN-C" else None),
        "next": {
            "PI1VN-A": "M3-PI2 untouched confirmation-panel preregistration",
            "PI1VN-B": "no V1 confirmation; consider S1 route only if valid "
                       "S1_FULL_PASS",
            "PI1VN-C": "V1 <=2x hypothesis validly rejected" +
                       ("; separately preregister S1 untouched confirmation"
                        if gain.get("S1_FULL_PASS") else
                        "; abstention-information method redesign"),
            "PI1VN-D": "direction estimator rethink",
            "PI1VN-X": "incident recovery; no scientific route choice",
        }[verdict],
    }
    dump(OUT / "m3pi1vn_final_verdict.json", final)
    return verdict


# --------------------------------------------------------------------------
# stage: figures
# --------------------------------------------------------------------------

def figures() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG.mkdir(parents=True, exist_ok=True)
    rows = panel_rows()
    recs = _load_trial_records(rows)
    trials = sorted(recs, key=lambda x: (x["state_id"], x["rep_id"]))
    prim = load(OUT / "m3pi1vn_primary_metrics.json")
    groups = [("WIDEN", "tab:green"), ("SHRINK", "tab:orange"),
              ("HOLD", "tab:red"), ("AMBIGUOUS", "tab:purple")]

    # PI1VN-1 / PI1VN-2 score distributions
    for fig_id, key, fname in (
            ("PI1VN-1", "V1", "PI1VN-1_v1_score_distribution.png"),
            ("PI1VN-2", "S1", "PI1VN-2_s1_score_distribution.png")):
        fig, ax = plt.subplots(figsize=(7.2, 4.4))
        data, labels, colors = [], [], []
        for grp, col in groups:
            vals = [x[key] for x in trials
                    if x["truth"] == grp and x[key] is not None]
            data.append(vals)
            labels.append(f"{grp} (n={len(vals)})")
            colors.append(col)
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
        for patch, col in zip(bp["boxes"], colors):
            patch.set_facecolor(col)
            patch.set_alpha(0.45)
        ax.set_ylabel(f"{key} score")
        ax.set_title(f"{fig_id}: {key} score by corrected truth "
                     "(reference-stratified)")
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(FIG / fname, dpi=200)
        plt.close(fig)

    # PI1VN-3 / PI1VN-4 risk-coverage frontiers
    for fig_id, family, fname in (
            ("PI1VN-3", "V1", "PI1VN-3_v1_risk_coverage_frontier.png"),
            ("PI1VN-4", "S1", "PI1VN-4_s1_risk_coverage_frontier.png")):
        fr = list(csvread(OUT / f"m3pi1vn_{family.lower()}_threshold_frontier.csv"))
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        cov = [float(x["deployable_coverage"]) for x in fr]
        ax.plot(cov, [float(x["wrong_direction_rate"]) for x in fr], "o-",
                ms=3, label="wrong-direction rate", color="tab:blue")
        ax.plot(cov, [float(x["unsafe_rate"]) for x in fr], "s-",
                ms=3, label="ND unsafe rate", color="tab:red")
        ax.axhline(GATES["wrong_direction_max"], ls="--", c="tab:blue", alpha=0.6)
        ax.axhline(GATES["unsafe_max"], ls="--", c="tab:red", alpha=0.6)
        ax.axvline(GATES["coverage_min"], ls=":", c="k", alpha=0.6,
                   label="coverage gate")
        ax.set_xlim(-0.02, 1.05)
        sel = prim.get(family, {}).get("selected_threshold")
        if sel is not None:
            match = [x for x in fr if float(x["threshold"]) == float(sel)]
            if match:
                ax.axvline(float(match[0]["deployable_coverage"]), c="tab:green",
                           lw=2, alpha=0.7,
                           label=f"selected threshold {float(sel):.4g}")
        ax.set_xlabel("deployable coverage")
        ax.set_ylabel("risk rate")
        ax.set_title(f"{fig_id}: {family} risk-coverage frontier")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(FIG / fname, dpi=200)
        plt.close(fig)

    # PI1VN-5 best-safe coverage comparison
    gain = load(OUT / "m3pi1vn_information_gain.json")
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    bars = ax.bar(["S1", "V1"],
                  [gain["S1_BEST_SAFE_COVERAGE"], gain["V1_BEST_SAFE_COVERAGE"]],
                  color=["tab:gray", "tab:green"], alpha=0.75)
    ax.axhline(GATES["coverage_min"], ls=":", c="k", label="coverage gate 75%")
    ax.set_title(f"PI1VN-5: best safety-compliant coverage "
                 f"(V1-S1 = {gain['coverage_gain']:+.3f}, >=5pp: "
                 f"{gain['gain_ge_5pp']})")
    for b, v in zip(bars, [gain["S1_BEST_SAFE_COVERAGE"],
                           gain["V1_BEST_SAFE_COVERAGE"]]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.3f}", ha="center")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1VN-5_v1_vs_s1_best_safe_coverage.png", dpi=200)
    plt.close(fig)

    # PI1VN-6 heatmap / PI1VN-7 direction / PI1VN-8 LOSO / PI1VN-9 HOLD-vs-AMB
    audit = list(csvread(OUT / "m3pi1vn_state_level_policy_audit.csv"))
    v1_audit = [x for x in audit if x["family"] == "V1"]
    states = [x["state_id"] for x in v1_audit]

    def _f(x, k):
        try:
            return float(x[k])
        except (TypeError, ValueError):
            return float("nan")

    deploy = [_f(x, "deployment_rate") for x in v1_audit]
    unsafe = [_f(x, "unsafe_rate") for x in v1_audit]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(max(9.0, 0.28 * len(states)), 4.4),
                                  sharex=True)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("white")
    ax.imshow(np.array(deploy)[None, :], aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax.set_yticks([0], ["deployment rate"])
    for j, v in enumerate(deploy):
        ax.text(j, 0, "" if math.isnan(v) else f"{v:.2f}", ha="center",
                va="center", fontsize=5.5)
    ax2.imshow(np.ma.masked_invalid(np.array(unsafe))[None, :], aspect="auto",
               cmap=plt.get_cmap("RdYlGn_r").copy(), vmin=0, vmax=1)
    ax2.set_yticks([0], ["unsafe rate (ND)"])
    for j, v in enumerate(unsafe):
        ax2.text(j, 0, "" if math.isnan(v) else f"{v:.2f}", ha="center",
                 va="center", fontsize=5.5)
    labels = [f"{s}\n[{x['truth']}]" for s, x in zip(states, v1_audit)]
    ax2.set_xticks(range(len(states)), labels, rotation=90, fontsize=6)
    ax.set_title("PI1VN-6: per-state deployment / ND-unsafe (selected V1 threshold)")
    fig.tight_layout()
    fig.savefig(FIG / "PI1VN-6_per_state_deployment_unsafe_heatmap.png", dpi=200)
    plt.close(fig)

    sanity = load(OUT / "m3pi1vn_direction_sanity.json")
    fig, ax = plt.subplots(figsize=(max(9.0, 0.28 * 16), 4.0))
    ps = sanity["per_state"]
    sids = sorted(ps)
    ax.bar(range(len(sids)), [ps[s]["wrong_direction_rate"] for s in sids],
           color="tab:blue", alpha=0.7)
    ax.axhline(GATES["wrong_direction_max"], ls="--", c="red",
               label="5% direction gate")
    ax.set_xticks(range(len(sids)),
                  [f"{s}\n[{ps[s]['trials']} tr]" for s in sids], rotation=90,
                  fontsize=6)
    ax.set_ylabel("Sign-No-Abstain wrong-direction rate")
    ax.set_title("PI1VN-7: directional wrong rate by deployable state")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1VN-7_directional_wrong_rate_by_state.png", dpi=200)
    plt.close(fig)

    loso = list(csvread(OUT / "m3pi1vn_loso_diagnostic.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), sharey=True)
    for ax, family in zip(axes, ("V1", "S1")):
        sub = [x for x in loso if x["family"] == family]
        sids = [x["held_out_state_id"] for x in sub]
        th = [float(x["selected_threshold"]) if x["selected_threshold"]
              else float("nan") for x in sub]
        ax.plot(range(len(sids)), th, "o", ms=4)
        full = prim.get(family, {}).get("selected_threshold")
        if full is not None:
            ax.axhline(full, ls="--", c="tab:green",
                       label=f"full-panel threshold {full:.4g}")
        ax.set_xticks(range(len(sids)), sids, rotation=90, fontsize=6)
        ax.set_title(f"{family} LOSO selected thresholds")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("selected threshold")
    fig.suptitle("PI1VN-8: LOSO threshold stability (diagnostic only)")
    fig.tight_layout()
    fig.savefig(FIG / "PI1VN-8_loso_threshold_stability.png", dpi=200)
    plt.close(fig)

    strat = load(OUT / "m3pi1vn_truth_stratified_metrics.json").get("V1", {})
    vals9 = [strat.get("HOLD", {}).get("unsafe_rate", 0),
             strat.get("AMBIGUOUS", {}).get("unsafe_rate", 0)]
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.bar(["HOLD", "AMBIGUOUS"], vals9,
           color=["tab:red", "tab:purple"], alpha=0.75)
    ax.axhline(GATES["unsafe_max"], ls="--", c="red", label="20% unsafe gate")
    for i, v in enumerate(vals9):
        ax.text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=8)
    ax.set_ylabel("unsafe rate at selected V1 threshold")
    ax.set_title("PI1VN-9: HOLD vs AMBIGUOUS unsafe behavior")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1VN-9_hold_vs_ambiguous_unsafe.png", dpi=200)
    plt.close(fig)

    fam = load(OUT / "m3pi1vn_family_stratified_metrics.json")
    fams = [k for k in ("legacy/current corrected", "CF1N replacement", "WCF1 new")
            if k in fam.get("V1", {})]
    cov = [fam["V1"][k]["deployable_coverage"] for k in fams]
    uns = [fam["V1"][k]["unsafe_rate"] for k in fams]
    x = range(len(fams))
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.bar([i - 0.18 for i in x], cov, width=0.36, label="deployable coverage",
           color="tab:green", alpha=0.75)
    ax.bar([i + 0.18 for i in x], uns, width=0.36, label="ND unsafe rate",
           color="tab:red", alpha=0.75)
    ax.axhline(GATES["coverage_min"], ls=":", c="k")
    ax.set_xticks(list(x), [f.replace(" ", "\n", 1) for f in fams], fontsize=8)
    ax.set_title("PI1VN-10: metrics by physical-source family (V1 selected threshold)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1VN-10_metrics_by_physical_family.png", dpi=200)
    plt.close(fig)
    print("PI1VN figures: 10 written")


# --------------------------------------------------------------------------
# stage: report
# --------------------------------------------------------------------------

def _regression_summary() -> str:
    log = OUT / "m3pi1vn_full_regression.log"
    if not log.exists():
        return "pending"
    tail = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    passed = [ln for ln in tail if " passed" in ln]
    return passed[-1] if passed else "; ".join(tail[-2:])


def report() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    final = load(OUT / "m3pi1vn_final_verdict.json")
    prim = load(OUT / "m3pi1vn_primary_metrics.json") \
        if (OUT / "m3pi1vn_primary_metrics.json").exists() else {}
    gain = load(OUT / "m3pi1vn_information_gain.json") \
        if (OUT / "m3pi1vn_information_gain.json").exists() else {}
    sanity = load(OUT / "m3pi1vn_direction_sanity.json")
    audit = load(OUT / "m3pi1vn_persistence_audit.json")
    manifest = load(TRIALS / "trial_manifest.json")
    fw = load(OUT / "m3pi1vn_reserve_firewall_audit.json")
    inh = load(OUT / "m3pi1vn_protocol_inheritance_audit.json")

    (DOC / "M3_PI1VN_Task.md").write_text(
        "# M3-PI1VN Task\n\nTask book: "
        "`M3_PI1VN_Independent_Fresh_Panel_Finite_Action_Information_Validation_Task.md`.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_Parent_WCF1_Audit.md").write_text(
        "# M3-PI1VN Parent WCF1 Audit\n\nStatus: **PASS**.\n\n"
        "- WCF1 = WCF1-A; P_ref 6/6; references 12/12; 0 consumed-invalid.\n"
        "- PI1V valid verdict = PI1V-X; Attempt-2 = DIAGNOSTIC_ONLY.\n"
        "- WA1 = WA1-X; WA1R = WA1R-B; retired states/seeds remain retired.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_Fresh_Panel_Audit.md").write_text(
        "# M3-PI1VN Fresh Panel Audit\n\nStatus: **PASS**.\n\n"
        f"- Panel hash recomputed and matching WCF1: `{check_panel_hash()[:16]}...`.\n"
        "- 24 states, 8W/8S/8ND; pilot/probe/threshold-replay exposure all 0 "
        "before PI1VN (m3pi1vn_panel_freshness_audit.csv).\n"
        "- No panel regeneration, replacement, or rebalancing.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_Frozen_Protocol_Inheritance.md").write_text(
        "# M3-PI1VN Frozen Protocol Inheritance\n\nStatus: **COMPLETE**.\n\n"
        f"- PI1V committed implementation hash: `{inh['pi1v_implementation_sha256'][:16]}...`.\n"
        f"- Gradient estimator: {inh['gradient_estimator']}.\n"
        f"- Sign convention: {inh['sign_convention']}; R={R}, B_grad={N_GRAD}.\n"
        f"- Probe: {N_PROBE}/{N_PROBE}, {N_BATCH} paired CRN batches; opposite "
        "action never probed; no adaptive probe.\n"
        f"- V1 = {inh['v1']['formula']}; S1 = {inh['s1']['formula']} on the same "
        "gradient data.\n"
        "- Metrics/thresholds/gates/5pp criterion imported verbatim from the "
        "committed PI1V machinery; no invalid-PI1V threshold reused.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_Reserve_Firewall_Audit.md").write_text(
        "# M3-PI1VN Reserve Firewall Audit\n\nStatus: **PASS**.\n\n"
        f"- Protected reserve states: {fw['protected_reserve_states']}; panel "
        "overlap: 0; UC2R protected confirmation untouched.\n"
        "- No gradient pilot, S1 feature, V1 probe, or threshold replay touched "
        "any reserve state.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_Pilot_Execution_Audit.md").write_text(
        "# M3-PI1VN Pilot Execution Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- Trials {manifest['trials_complete']}/{manifest['trials_expected']}, "
        f"consumed-invalid {manifest['consumed_invalid']}.\n"
        f"- Samples: gradient {manifest['sample_accounting']['gradient_samples']:,}; "
        f"probe {manifest['sample_accounting']['base_probe_samples'] + manifest['sample_accounting']['selected_action_probe_samples']:,}; "
        f"total {manifest['sample_accounting']['total_samples']:,} "
        f"(<=2x: {manifest['sample_accounting']['total_le_2x']}).\n"
        "- Every trial written under the repaired non-circular contract "
        "(STARTED before simulator; payload hash + file hash verified).\n"
        f"- Persistence: canonical hashes {audit['canonical_hashes']}.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_V1_Analysis.md").write_text(
        "# M3-PI1VN V1 Analysis\n\n"
        f"- Direction sanity: {sanity['gate']} (wrong rate "
        f"{sanity['wrong_direction_rate']:.4f}).\n"
        f"- V1_FULL_PASS: {gain.get('V1_FULL_PASS')}; selected threshold "
        f"{prim.get('V1', {}).get('selected_threshold')}; wrong "
        f"{prim.get('V1', {}).get('wrong')}; coverage "
        f"{prim.get('V1', {}).get('deployable_coverage')}; unsafe "
        f"{prim.get('V1', {}).get('unsafe_rate')}.\n"
        f"- Best safety-compliant coverage: {gain.get('V1_BEST_SAFE_COVERAGE')}.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_S1_Comparator.md").write_text(
        "# M3-PI1VN S1 Comparator\n\n"
        f"- S1_FULL_PASS: {gain.get('S1_FULL_PASS')}; selected threshold "
        f"{prim.get('S1', {}).get('selected_threshold')}; wrong "
        f"{prim.get('S1', {}).get('wrong')}; coverage "
        f"{prim.get('S1', {}).get('deployable_coverage')}; unsafe "
        f"{prim.get('S1', {}).get('unsafe_rate')}.\n"
        f"- Coverage gain V1-S1: {gain.get('coverage_gain'):+.3f} (>=5pp: "
        f"{gain.get('gain_ge_5pp')}); unique-information criterion: "
        f"{gain.get('unique_information_criterion')}.\n"
        "- S1 uses the same gradient data and no probe information.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VN_Robustness_Diagnostics.md").write_text(
        "# M3-PI1VN Robustness Diagnostics\n\n"
        "Diagnostic only; no tuning derived. State-level audit, truth-stratified "
        "metrics, family-stratified metrics (legacy / CF1N replacement / WCF1 "
        "new), LOSO and LOCO all completed.\n"
        "- All outputs labelled reference-stratified development metrics; no "
        "natural-prevalence claim.\n",
        encoding="utf-8")
    claim = {
        "PI1VN-A": "On the frozen untouched 8W/8S/8ND fresh development panel, "
                   "the preregistered low-budget paired finite-action V1 signal "
                   "satisfied the inherited wrong-direction, coverage and "
                   "ND-safety gates under the fixed <=2x information budget and "
                   "provided the preregistered incremental information advantage "
                   "over S1 -- the first valid clean support for the <=2x V1 "
                   "hypothesis.",
        "PI1VN-B": "V1 passes the development deployment gates but is not "
                   "uniquely justified relative to S1.",
        "PI1VN-C": "The frozen <=2x V1 hypothesis is validly rejected on the "
                   "fresh panel -- the first valid negative result.",
        "PI1VN-D": "The inherited gradient sign fails the 5% direction gate on "
                   "the fresh panel.",
        "PI1VN-X": "Invalid.",
    }[final["verdict"]]
    (DOC / "M3_PI1VN_Final_Report.md").write_text(
        "# M3-PI1VN Final Report\n\n"
        f"**Verdict: {final['verdict']}**\n\n{claim}\n\n"
        f"- Fresh panel: 24 states, hash verified, unchanged; 192/192 trials.\n"
        f"- Samples: {manifest['sample_accounting']['total_samples']:,} "
        f"(<=2x: {'PASS' if manifest['sample_accounting']['total_le_2x'] else 'FAIL'}).\n"
        f"- Direction sanity: {sanity['gate']} (wrong rate "
        f"{sanity['wrong_direction_rate']:.4f}).\n"
        f"- V1_FULL_PASS {gain.get('V1_FULL_PASS')}; S1_FULL_PASS "
        f"{gain.get('S1_FULL_PASS')}; unique-information "
        f"{gain.get('unique_information_criterion')}.\n"
        f"- Persistence: {audit['canonical_hashes']}.\n"
        f"- VALUE/RARITY/M3-Q: BLOCKED; confirmation trials 0.\n\n"
        f"NEXT: {final['next']}\n\n"
        "FULL REGRESSION:\n"
        f"{_regression_summary()}\n", encoding="utf-8")
    print(f"PI1VN report: verdict {final['verdict']}")


# --------------------------------------------------------------------------
# stage: close (frozen-contract invalidation; zero simulator)
# --------------------------------------------------------------------------

def close() -> None:
    """Freeze the PI1VN-X verdict after the trial-137 persistence failure.

    Taskbook Sec. 25: scientific calculation began but durable COMPLETE
    failed => CONSUMED_INVALID => PI1VN-X => STOP; no replay.  Writes the
    audit, forensics, and verdict only; never reruns the consumed trial.
    """
    entries = ledger_entries(TRIAL_LEDGER)
    counts: dict[str, Counter] = {}
    for e in entries:
        counts.setdefault(e.get("state_id"), Counter())[e.get("status")] += 1
    complete = {rid for rid, c in counts.items() if c.get("COMPLETE")}
    consumed = [rid for rid, c in counts.items() if c.get("CONSUMED_INVALID")]
    rows = panel_rows()
    expected = {f"{r['state_id']}__rep{rep}" for r in rows for rep in range(R)}
    (TRIALS / "DIAGNOSTIC_ONLY_CONSUMED_INVALID.txt").write_text(
        "PI1VN-X STOP -- a trial in this ledger began scientific calculation but "
        "no durable COMPLETE record exists (taskbook Sec. 25: CONSUMED_INVALID, "
        "PI1VN-X, STOP; no replay). Diagnostic/provenance only.\n", encoding="utf-8")
    consumed_id = consumed[0]
    consumed_entry = next(e for e in entries if e.get("status") == "CONSUMED_INVALID")
    forensics = {
        "recorded_at": now(),
        "incident": "PI1VN trial-137 persistence failure -> frozen-contract "
                    "invalidation",
        "what_happened": [
            f"Trial {consumed_id} (137th of 192) consumed its full scientific "
            "sampling (~40,000 online samples) but the durable record never "
            "reached COMPLETE: the temp filename embedded the encoded logical "
            "id twice (once as the temp stem, once inside the caller-supplied "
            "run_uuid), pushing the path to ~265 characters -- past the Windows "
            "MAX_PATH limit (260) for the longest panel state names (the WA1R "
            "candidates with seven underscore escapes).",
            "The transactional runner appended a durable CONSUMED_INVALID entry "
            "and the stage aborted; trials 138-192 were never started.",
        ],
        "frozen_rule_applied": "scientific calculation began + durable COMPLETE "
                               "failed => CONSUMED_INVALID => PI1VN-X => STOP; "
                               "no replay",
        "ledger_state": {"STARTED": sum(c.get("STARTED", 0) for c in counts.values()),
                         "COMPLETE": len(complete),
                         "CONSUMED_INVALID": len(consumed)},
        "samples_note": "136 complete trials hold ~5.44M durable online samples; "
                        "they are DIAGNOSTIC ONLY and support no threshold, "
                        "verdict, or route decision",
        "defect_and_fix": [
            "defect: the PI1VN pilot passed run_uuid=f'pi1vn-<safe_sid>-<rep>' "
            "-- duplicating the ~55-char encoded state id inside the temp "
            "filename; the m3wa1r module default (uuid4 hex, 32 chars) was safe",
            "fix 1: the pilot now passes a fresh uuid4 hex run_uuid",
            "fix 2 (module hardening): m3wa1r persistence truncates long "
            "encoded ids in temp names to a bounded form with a short digest, "
            "so no caller can approach MAX_PATH",
        ],
        "no_replay_bookkeeping": {
            "consumed_trial_identity": consumed_id,
            "consumed_seed": consumed_entry.get("seed"),
            "seed_namespace": "M3-PI1VN-GRAD",
            "rule": "same stage cannot rerun same state/rep; same exact seed "
                    "cannot be reused; a successor stage requires a fresh "
                    "preregistration and fresh namespace",
        },
        "unfinished_trials_count": len(expected) - len(complete) - len(consumed),
    }
    dump(OUT / "m3pi1vn_incident_forensics.json", forensics)
    audit = {"recorded_at": now(), "ledger_entries": len(entries),
             "trials_complete": len(complete),
             "consumed_invalid": len(consumed),
             "hashes": "FAIL",
             "problems": [f"{consumed_id}: STARTED without durable COMPLETE"],
             "canonical_hashes": "FAIL",
             "durable_records_diagnostic_only": True}
    dump(OUT / "m3pi1vn_persistence_audit.json", audit)
    dump(OUT / "m3pi1vn_final_verdict.json", {
        "status": "INVALID",
        "verdict": "PI1VN-X",
        "recorded_at": now(),
        "rule": "taskbook Sec. 25: scientific calculation began + durable "
                "COMPLETE failed => CONSUMED_INVALID => PI1VN-X => STOP; no replay",
        "trials": {"expected": 192, "complete": len(complete),
                   "consumed_invalid": len(consumed),
                   "never_started": len(expected) - len(complete) - len(consumed)},
        "incident_forensics": forensics,
        "preregistration": {"frozen_before_outcomes": True,
                            "prereg_hashes_verified": True,
                            "note": "the frozen design (panel, protocols, seeds, "
                                    "contracts) remains valid; a successor stage "
                                    "may re-preregister under a fresh namespace "
                                    "without reusing the consumed trial or seed"},
        "invalid_retired_data": {"PI1V Attempt-2 used": False,
                                 "retired states used": False,
                                 "retired seeds used": False},
        **boundary_block(),
        "next": "stop; separately preregistered recovery (fresh namespace, "
                "repaired temp-path handling) required",
    })
    txt = (
        "M3-PI1VN STATUS:\nINVALID\n\n"
        "PARENT:\nWCF1 = WCF1-A\n\n"
        "FRESH PANEL:\nstates = 24\nhash verified = YES\npanel changed = NO\n\n"
        f"TRIALS:\nexpected = 192\ncomplete = {len(complete)}\n"
        f"consumed-invalid = {len(consumed)}\n\n"
        "SAMPLES:\ngradient = (136 durable trials)\nprobe = (136 durable trials)\n"
        "total = diagnostic only\n<=2x = N/A (stage invalid)\n\n"
        "DIRECTION:\nN/A (stage invalid before analysis)\n\n"
        "V1:\nN/A\n\nS1:\nN/A\n\nCOMPARISON:\nN/A\n\nROBUSTNESS:\nN/A\n\n"
        "PERSISTENCE:\nhashes = FAIL\nledger = FAIL\nmanifest = NA\n\n"
        "INVALID / RETIRED DATA:\nPI1V Attempt-2 used = NO\n"
        "retired states used = NO\nretired seeds used = NO\n\n"
        "PROTECTED RESERVE:\npilot exposure = 0\n\n"
        "CONFIRMATION:\ntrials = 0\nauthorized = NO\n\n"
        "VALUE:\nBLOCKED\nRARITY:\nBLOCKED\nM3-Q:\nBLOCKED\n\n"
        "FINAL VERDICT:\nPI1VN-X\n\nSECONDARY ROUTE SIGNAL:\nN/A\n\n"
        "NEXT:\nstop; separately preregistered recovery (fresh namespace, "
        "repaired temp-path handling) required; the frozen design may be "
        "re-preregistered without reusing the consumed trial or seed\n\n"
        "FULL REGRESSION:\n" + _regression_summary() + "\n")
    (OUT / "m3pi1vn_final_report.txt").write_text(txt + "\n", encoding="utf-8")
    (DOC / "M3_PI1VN_Final_Report.md").write_text(
        "# M3-PI1VN Final Report\n\n"
        "**Verdict: PI1VN-X**\n\n"
        f"Trial 137 of 192 (`{consumed_id}`) completed its scientific sampling "
        "but never reached a durable COMPLETE record: the caller-supplied "
        "run_uuid duplicated the encoded state id inside the temp filename, "
        "exceeding the Windows MAX_PATH limit for the longest panel state "
        "names. The frozen contract fired exactly as written: "
        "**CONSUMED_INVALID -> PI1VN-X -> STOP, no replay**.\n\n"
        "- 136 earlier trials are durably complete and remain DIAGNOSTIC ONLY; "
        "they support no threshold, verdict, or route decision.\n"
        "- Defect fixed (uuid4 run_uuid + module-level bounded temp names).\n"
        "- The frozen design survives; a successor stage may re-preregister "
        "under a fresh namespace without reusing the consumed trial or seed.\n"
        "- VALUE/RARITY/M3-Q: BLOCKED; confirmation trials 0.\n\n"
        "FULL REGRESSION:\n" + _regression_summary() + "\n", encoding="utf-8")
    (DOC / "M3_PI1VN_Pilot_Execution_Audit.md").write_text(
        "# M3-PI1VN Pilot Execution Audit\n\nStatus: **INVALID (PI1VN-X)**.\n\n"
        f"- Trials durable COMPLETE: {len(complete)}/192; consumed-invalid: "
        f"{len(consumed)} (trial 137); never started: "
        f"{len(expected) - len(complete) - len(consumed)}.\n"
        "- Root cause: caller-supplied run_uuid doubled the encoded state id in "
        "the temp filename (~265 chars > Windows MAX_PATH 260) for the longest "
        "panel state names.\n"
        "- Frozen rule applied: CONSUMED_INVALID -> PI1VN-X -> STOP; no replay.\n"
        "- Defects fixed for the successor stage (uuid4 run_uuid; module-level "
        "bounded temp names).\n", encoding="utf-8")
    print(txt)
    print("PI1VN close: verdict PI1VN-X (frozen-contract invalidation; no replay)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("prepare", "pilot", "analyze", "figures",
                                     "report", "close"))
    a = p.parse_args()
    {"prepare": prepare, "pilot": pilot, "analyze": analyze,
     "figures": figures, "report": report, "close": close}[a.stage]()
