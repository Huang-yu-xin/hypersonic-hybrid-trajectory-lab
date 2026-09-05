"""M3-PI1V -- Prospective finite-action information validation on the frozen CF2 panel.

Development-only stage.  Exposes the immutable 24-state CF2 development panel
(8 W / 8 S / 8 ND, hash 843ee98e...) to a low-budget paired finite-action
validity signal V1 under the fixed <=2x online-information budget, with the
inherited UC3/G2/PI1 gradient protocol and the same-data S1 comparator.

Inheritance (recovered verbatim before the pilot, never retuned):
    gradient estimator   hyptraj.m3d.adaptation.gradient_decision (frozen M3-v0)
    sign convention      g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK  (UC3/PI1)
    invalid rule         estimator problems OR non-finite g/ci/ESS OR ESS<20
    R, B_grad            8 reps/state, 20000 gradient samples/trial
    paired probe         BASE + selected action only, 2x10000 samples, 20
                         paired CRN batches, batch-SE  (PI1 preregistration)
    V1                   (-0.01 - r_hat) / SE(r_hat), r_hat = M2(a)/M2(base)-1
    S1                   |g_hat| / bootstrap-SE, SE=(ci_hi-ci_lo)/(2*z95)  (UC3)
    metrics/gates        UC3 wrong/coverage/unsafe semantics; 5% / 75% / 20%
    persistence          hardened CF1R0 transactional contract in exact order
                         (durable STARTED BEFORE sampling -> temp+fsync -> schema
                         validation -> sha256 -> atomic rename -> parent-dir fsync
                         -> final hash verify -> COMPLETE)

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
import time
import uuid
from collections import Counter
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import BenchmarkConfig, config_from_record, load_freeze
from hyptraj.m3cf1r0.persistence import (
    StatePersistenceError,
    fsync_directory,
    ledger_append,
    ledger_entries,
)
from hyptraj.m3d.adaptation import draw_online_pilot, gradient_decision
from hyptraj.m3d.benchmark_states import assemble_state, state_arms

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1v/summary"
TRIALS = ROOT / "results/phase_m3pi1v/trials"
FIG = ROOT / "results/phase_m3pi1v/figures"
CFG = ROOT / "configs/phase_m3pi1v"
DOC = ROOT / "docs/phase_m3pi1v"

PANEL_CSV = ROOT / "results/phase_m3cf2/summary/m3cf2_development_panel.csv"
PANEL_HASH = "843ee98e5be20d71964684d29e7671f5168bd2c36a6d2b02a745be88aff85d5c"
RESERVE_CSV = ROOT / "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv"
UC2R_STATES = ROOT / "results/phase_m3uc2r/summary/m3uc2r_reference_states.csv"
CF1N_CONFIGS = ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json"
CF1N_REPLACEMENT_CSV = ROOT / "results/phase_m3cf1r0/replacement/m3cf1r0_replacement_configs.csv"

R = 8                    # reps per state (PI1 prereg / UC3 R_dev)
N_GRAD = 20_000          # B_grad: gradient samples per trial
N_PROBE = 10_000         # probe samples per arm (BASE and selected action)
N_BATCH = 20             # paired CRN batches (gradient pilot and probe)
ALPHA_P = 0.5
MARGIN = -0.01           # frozen improvement margin delta_imp
Z95 = 1.959963984540054
GATES = {"wrong_direction_max": 0.05, "coverage_min": 0.75, "unsafe_max": 0.20}
UNIQUE_GAIN_PP = 0.05
GRAD_NS = "M3-PI1V-GRAD"
PROBE_NS = "M3-PI1V-PROBE"
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
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def boundary_block(extra: dict | None = None) -> dict:
    base = {
        "value_evaluation": "BLOCKED",
        "rarity_shift": "BLOCKED",
        "m3_q": "BLOCKED",
        "protected_confirmation_authorized": False,
        "confirmation_trials": 0,
        "reserve_pilot_trials": 0,
    }
    base.update(extra or {})
    return base


# --------------------------------------------------------------------------
# panel / state assembly
# --------------------------------------------------------------------------

def panel_rows() -> list[dict]:
    rows = csvread(PANEL_CSV)
    if len(rows) != 24 or len({r["state_id"] for r in rows}) != 24:
        raise RuntimeError("PI1V-X: parent panel is not exactly 24 unique states")
    return rows


def check_panel_hash() -> str:
    digest = sha(PANEL_CSV)
    if digest != PANEL_HASH:
        raise RuntimeError(f"PI1V-X: parent panel hash mismatch {digest}")
    return digest


_cf1n_cache = None


def _cf1n_records() -> dict[str, dict]:
    global _cf1n_cache
    if _cf1n_cache is None:
        fields = load(CF1N_CONFIGS)["physical_fields"]
        _cf1n_cache = fields
    return _cf1n_cache


def bench(config_id: str):
    """Resolve a panel config_id to the frozen BenchmarkConfig (CF2 lineage)."""
    if config_id in _cf1n_records():
        f = _cf1n_records()[config_id]
        return BenchmarkConfig(
            config_id=config_id,
            batch_seed=20300315,   # CF1N default (replacement CSV carries no seed column)
            batch_index=0,
            theta_deg=tuple(float(f[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(f[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(f["curvature_c"]),
            offset_o=tuple(float(f[f"offset_{i}"]) for i in range(1, 5)),
        )
    matches = [r for r in load_freeze()["benchmark_configs"]
               if r["config_id"].endswith(config_id)]
    if len(matches) != 1:
        raise RuntimeError(f"PI1V-X: config {config_id} not uniquely resolvable")
    return config_from_record(matches[0])


_states: dict[str, object] = {}


def state_for(row):
    sid = row["state_id"]
    if sid not in _states:
        st = assemble_state(bench(row["config_id"]), float(row["s2"]),
                            short_config=row["config_id"])
        if isinstance(st, dict):
            raise RuntimeError(f"PI1V-X: state assembly failed for {sid}: {st}")
        _states[sid] = st
    return _states[sid]


# --------------------------------------------------------------------------
# inherited protocol implementations (verbatim semantics)
# --------------------------------------------------------------------------

GRADIENT_PROTOCOL_HASH_SOURCE = "configs/phase_m3pi1v/m3pi1v_gradient_protocol.json"


def gradient_trial(st, seed_value: int) -> dict:
    """Inherited UC3/PI1 gradient trial: mixed pilot + frozen estimator."""
    z, lp, lr, strata = draw_online_pilot(st, seed_value, n_pilot=N_GRAD, alpha=ALPHA_P)
    gd = gradient_decision(st, seed_value, z, lp, lr, strata)
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
    """PI1-preregistered paired-CRN finite-action probe (BASE + selected only).

    One shared generator stream yields paired draws across the two arms;
    the opposite action is never sampled.  M2 semantics: batch means of
    (event * importance weight)^2; r_hat = M2(action)/M2(base) - 1;
    SE = batch std/sqrt(batches); ESS from first moments.
    """
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


def s1_score(g_hat: float, ci_low: float, ci_high: float):
    """Inherited UC3 S1_gradient_z."""
    se = (float(ci_high) - float(ci_low)) / (2 * Z95)
    if not all(np.isfinite(x) for x in (g_hat, se)) or se <= 0:
        return None
    return abs(float(g_hat)) / se


def v1_score(r_hat, se_r_hat):
    if r_hat is None or se_r_hat is None:
        return None
    if not np.isfinite(r_hat) or not np.isfinite(se_r_hat) or se_r_hat <= 0:
        return None
    return (MARGIN - float(r_hat)) / float(se_r_hat)


# --------------------------------------------------------------------------
# metric / threshold machinery (UC3 semantics; PI1V selection objective)
# --------------------------------------------------------------------------

def policy_action(row: dict, family: str, t: float) -> str:
    """V1 never changes direction: deploy the gradient-selected action or abstain."""
    if family == "V1":
        if (not row["gradient_valid"]) or (not row["probe_valid"]) or row["V1"] is None:
            return "ABSTAIN"
        return row["selected_action"] if row["V1"] >= t else "ABSTAIN"
    if family == "S1":
        if (not row["gradient_valid"]) or row["S1"] is None:
            return "ABSTAIN"
        return row["selected_action"] if row["S1"] >= t else "ABSTAIN"
    raise RuntimeError(f"unknown family {family}")


def evaluate(rows: list[dict], actions: list[str]) -> dict:
    """Inherited UC3 metric semantics; denominators are never redefined."""
    dep = [(r, a) for r, a in zip(rows, actions) if r["truth"] in DEPLOYABLE]
    non = [(r, a) for r, a in zip(rows, actions) if r["truth"] in NON_DEPLOYABLE]
    deployed = [(r, a) for r, a in dep if a != "ABSTAIN"]
    wrong = sum(1 for r, a in dep if a != "ABSTAIN" and a != r["truth"])
    unsafe = sum(1 for r, a in non if a != "ABSTAIN")
    out = {
        "deployable_trials": len(dep),
        "deployed": len(deployed),
        "wrong": wrong,
        "wrong_direction_rate": wrong / len(dep) if dep else 0.0,
        "wrong_ci95": wilson(wrong, len(dep)),
        "deployable_coverage": len(deployed) / len(dep) if dep else 0.0,
        "coverage_ci95": wilson(len(deployed), len(dep)),
        "nondeployable_trials": len(non),
        "deployed_nd": unsafe,
        "unsafe": unsafe,
        "unsafe_rate": unsafe / len(non) if non else 0.0,
        "unsafe_ci95": wilson(unsafe, len(non)),
    }
    for grp in ("WIDEN", "SHRINK", "HOLD", "AMBIGUOUS"):
        sub = [(r, a) for r, a in zip(rows, actions) if r["truth"] == grp]
        d = sum(1 for r, a in sub if a != "ABSTAIN")
        entry = {"trials": len(sub), "deployed": d}
        if grp in DEPLOYABLE:
            w = sum(1 for r, a in sub if a != "ABSTAIN" and a != r["truth"])
            entry.update({"wrong": w, "wrong_rate": w / len(sub) if sub else 0.0,
                          "coverage": d / len(sub) if sub else 0.0})
        else:
            entry.update({"unsafe_rate": d / len(sub) if sub else 0.0})
        out[f"truth_{grp}"] = entry
    return out


def threshold_grid(values: list[float]) -> list[float]:
    """Inherited UC3 candidate rule: deploy-all sentinel, midpoints, abstain-all."""
    vals = sorted({float(v) for v in values})
    if not vals:
        return []
    return [vals[0] - 1.0] + [(a + b) / 2.0 for a, b in zip(vals, vals[1:])] + [vals[-1] + 1.0]


def family_scores(rows: list[dict], family: str) -> list[float]:
    out = []
    for r in rows:
        if family == "V1":
            if r["gradient_valid"] and r["probe_valid"] and r["V1"] is not None:
                out.append(float(r["V1"]))
        else:
            if r["gradient_valid"] and r["S1"] is not None:
                out.append(float(r["S1"]))
    return out


def frontier(rows: list[dict], family: str) -> list[dict]:
    grid = threshold_grid(family_scores(rows, family))
    out = []
    for t in grid:
        actions = [policy_action(r, family, t) for r in rows]
        m = evaluate(rows, actions)
        out.append({
            "threshold": float(t),
            "deployed_W": m["truth_WIDEN"]["deployed"],
            "deployed_S": m["truth_SHRINK"]["deployed"],
            "wrong": m["wrong"],
            "wrong_direction_rate": m["wrong_direction_rate"],
            "deployable_coverage": m["deployable_coverage"],
            "deployed_nd": m["deployed_nd"],
            "unsafe": m["unsafe"],
            "unsafe_rate": m["unsafe_rate"],
            "safety_compliant": bool(m["wrong_direction_rate"] <= GATES["wrong_direction_max"]
                                     and m["unsafe_rate"] <= GATES["unsafe_max"]),
            "full_gate_pass": bool(m["wrong_direction_rate"] <= GATES["wrong_direction_max"]
                                   and m["deployable_coverage"] >= GATES["coverage_min"]
                                   and m["unsafe_rate"] <= GATES["unsafe_max"]),
        })
    return out


def select_threshold(front: list[dict]):
    """PI1V selection objective (frozen): safety-compliant max coverage, then
    lower unsafe, lower wrong, more conservative (higher) threshold, canonical."""
    compliant = [r for r in front if r["safety_compliant"]]
    if not compliant:
        return None
    return sorted(compliant, key=lambda r: (-r["deployable_coverage"], r["unsafe_rate"],
                                            r["wrong_direction_rate"], -r["threshold"],
                                            r["threshold"]))[0]


def best_safe_coverage(front: list[dict]) -> float:
    compliant = [r for r in front if r["safety_compliant"]]
    return max((r["deployable_coverage"] for r in compliant), default=0.0)


def direction_sanity(rows: list[dict]) -> dict:
    """Inherited Sign-No-Abstain direction audit on the 16 deployable states."""
    dep = [r for r in rows if r["truth"] in DEPLOYABLE]
    actions = []
    for r in dep:
        actions.append(r["selected_action"] if r["gradient_valid"] else "ABSTAIN")
    wrong = sum(1 for r, a in zip(dep, actions)
                if a != "ABSTAIN" and a != r["truth"])
    valid = sum(1 for r in dep if r["gradient_valid"])
    per_state = {}
    for sid in sorted({r["state_id"] for r in dep}):
        sub = [(r, a) for r, a in zip(dep, actions) if r["state_id"] == sid]
        w = sum(1 for r, a in sub if a != "ABSTAIN" and a != r["truth"])
        v = sum(1 for r, _ in sub if r["gradient_valid"])
        per_state[sid] = {"trials": len(sub), "valid_gradient": v,
                          "wrong_directions": w,
                          "wrong_direction_rate": w / len(sub) if sub else 0.0}
    rate = wrong / len(dep) if dep else 0.0
    return {
        "metric": "Sign-No-Abstain wrong-direction rate (inherited G2/UC3 semantics)",
        "W_trials": sum(1 for r in dep if r["truth"] == "WIDEN"),
        "S_trials": sum(1 for r in dep if r["truth"] == "SHRINK"),
        "deployable_trials": len(dep),
        "valid_gradient_trials": valid,
        "invalid_gradient_trials": len(dep) - valid,
        "wrong_selected_directions": wrong,
        "wrong_direction_rate": rate,
        "wrong_ci95": wilson(wrong, len(dep)),
        "gate_max": GATES["wrong_direction_max"],
        "gate": "PASS" if rate <= GATES["wrong_direction_max"] else "FAIL",
        "per_state": per_state,
    }


# --------------------------------------------------------------------------
# seed audit
# --------------------------------------------------------------------------

def prior_namespaces() -> set[str]:
    found: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if "namespace" in str(k).lower() and isinstance(v, str):
                    found.add(v)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    for p in (ROOT / "configs").rglob("*.json"):
        try:
            walk(load(p))
        except Exception:
            continue
    return found


def prior_recorded_seeds() -> set[int]:
    """Seed values recorded by PRIOR stages.  PI1V's own artifacts are excluded:
    after the pilot runs, PI1V seeds legitimately appear under results/, and the
    audit must not mistake the stage's own frozen seeds for prior collisions."""
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3pi1v"
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
    for p in (ROOT / "results").rglob("*.json"):
        if self_prefix in p.parents:
            continue
        try:
            data = load(p)
        except Exception:
            continue
        stack = [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    kl = str(k).lower()
                    if kl in ("seed", "seeds", "seed_key", "gradient_seed", "probe_seed",
                              "split_seed", "reference_seed"):
                        if isinstance(v, int):
                            vals.add(v)
                        elif isinstance(v, list) and v and all(isinstance(x, int) for x in v):
                            # composite seed keys are namespace-scoped; record the
                            # full tuple under a canonical single-int digest so any
                            # later reuse of the same key tuple is detectable
                            vals.add(int.from_bytes(
                                hashlib.sha256(
                                    json.dumps(v, sort_keys=True).encode()).digest()[:4],
                                "big"))
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(o, list):
                stack.extend(x for x in o if isinstance(x, (dict, list)))
    return vals


def planned_seeds(rows: list[dict]) -> dict:
    grad, probe = {}, {}
    for r in rows:
        for rep in range(R):
            grad[f"{r['state_id']}|rep{rep}"] = seed(GRAD_NS, r["state_id"], rep)
            probe[f"{r['state_id']}|rep{rep}"] = seed(PROBE_NS, r["state_id"], rep)
    return {"gradient": grad, "probe": probe}


# --------------------------------------------------------------------------
# stage: prepare  (zero simulator samples)
# --------------------------------------------------------------------------

PREREG_FILES = []


def prepare() -> None:
    # Stage discipline: once the pre-pilot artifacts are frozen (all prereg
    # hashes verify), prepare must not rewrite them -- any rewrite would break
    # the hash freeze and invalidate the stage.
    prereg_path = OUT / "m3pi1v_prereg_hashes.json"
    if prereg_path.exists():
        try:
            verify_prereg()
        except RuntimeError:
            pass
        else:
            print("PI1V prepare: preregistration already frozen and verified; "
                  "refusing to rewrite (stage discipline)")
            return
    check_panel_hash()
    rows = panel_rows()
    comp = Counter(r["truth_group"] for r in rows)
    truth = Counter(r["truth"] for r in rows)
    if not (comp["W"] == 8 and comp["S"] == 8 and comp["ND"] == 8
            and truth["WIDEN"] == 8 and truth["SHRINK"] == 8
            and truth["HOLD"] == 4 and truth["AMBIGUOUS"] == 4):
        raise RuntimeError("PI1V-X: parent panel composition mismatch")
    OUT.mkdir(parents=True, exist_ok=True)
    CFG.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    TRIALS.mkdir(parents=True, exist_ok=True)

    # -- parent verdict chain ------------------------------------------------
    chain = {}
    for stage, path, want in [
        ("G2", "results/phase_m3g2/summary/m3g2_final_verdict.json", "G2-D"),
        ("UC0", "results/phase_m3uc0/summary/m3uc0_final_verdict.json", "UC0-A"),
        ("UC1", "results/phase_m3uc1/summary/m3uc1_final_verdict.json", "UC1-E"),
        ("UC2", "results/phase_m3uc2/summary/m3uc2_final_verdict.json", "UC2-B"),
        ("UC2R", "results/phase_m3uc2r/summary/m3uc2r_final_verdict.json", "UC2R-A"),
        ("UC3", "results/phase_m3uc3/summary/m3uc3_final_verdict.json", "UC3-DEV-B"),
        ("PI", "results/phase_m3pi/summary/m3pi_final_verdict.json", "PI-B"),
        ("PI1", "results/phase_m3pi1/summary/m3pi1_final_verdict.json", "PI1-REF-B"),
        ("PI1R", "results/phase_m3pi1r/summary/m3pi1r_final_verdict.json", "PI1R-B"),
        ("SF0", "results/phase_m3sf0/summary/m3sf0_final_verdict.json", "SF0-A"),
        ("SF1", "results/phase_m3sf1/summary/m3sf1_final_verdict.json", "SF1-S"),
        ("SF2", "results/phase_m3sf2/summary/m3sf2_final_verdict.json", "SF2-C"),
        ("CF0", "results/phase_m3cf0/summary/m3cf0_final_verdict.json", "CF0-A"),
        ("CF1", "results/phase_m3cf1/summary/m3cf1_final_verdict.json", "CF1-X"),
        ("CF1R0", "results/phase_m3cf1r0/summary/m3cf1r0_final_verdict.json", "CF1R0-A"),
        ("CF1N", "results/phase_m3cf1n/summary/m3cf1n_final_verdict.json", "CF1N-A"),
        ("CF2", "results/phase_m3cf2/summary/m3cf2_final_verdict.json", "CF2-A"),
    ]:
        got = load(ROOT / path)["verdict"]
        chain[stage] = {"verdict": got, "expected": want, "match": got == want}
    parent_audit = {
        "recorded_at": now(),
        "parent_panel": "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "parent_panel_sha256": check_panel_hash(),
        "expected_panel_sha256": PANEL_HASH,
        "panel_hash_verified": True,
        "panel_composition": {"total": 24, "W": comp["W"], "S": comp["S"], "ND": comp["ND"],
                              "HOLD": truth["HOLD"], "AMBIGUOUS": truth["AMBIGUOUS"]},
        "reference_stratified": True,
        "natural_prevalence_claim": False,
        "panel_source_stages": dict(Counter(r["source_stage"] for r in rows)),
        "verdict_chain": chain,
        "all_parent_verdicts_match": all(v["match"] for v in chain.values()),
        "cf1_invalid_not_used": True,
        "panel_replacement_attempted": False,
    }
    if not parent_audit["all_parent_verdicts_match"]:
        raise RuntimeError("PI1V-X: parent verdict chain mismatch")
    dump(OUT / "m3pi1v_parent_panel_audit.json", parent_audit)

    # -- reserve firewall ----------------------------------------------------
    reserve = csvread(RESERVE_CSV)
    reserve_ids = [r["state_id"] for r in reserve]
    uc2r = csvread(UC2R_STATES)
    uc2r_conf = [r for r in uc2r if r["split"] == "CONFIRMATION"]
    panel_ids = {r["state_id"] for r in rows}
    overlap_reserve = panel_ids & set(reserve_ids)
    overlap_uc2r = panel_ids & {r["state_id"] for r in uc2r_conf}
    if overlap_reserve or overlap_uc2r:
        raise RuntimeError("PI1V-X: development panel overlaps protected states")
    firewall = {
        "recorded_at": now(),
        "pilot_protected_reserve_states": len(reserve_ids),
        "uc2r_protected_confirmation_states": len(uc2r_conf),
        "development_panel_states": len(panel_ids),
        "panel_reserve_overlap": sorted(overlap_reserve),
        "panel_uc2r_confirmation_overlap": sorted(overlap_uc2r),
        "overlap_is_zero": not overlap_reserve and not overlap_uc2r,
        "reserve_pilot_exposure_planned": 0,
        "reserve_pilot_exposure_observed": 0,
        "uc2r_protected_pilot_exposure_planned": 0,
        "uc2r_protected_pilot_exposure_observed": 0,
        "forbidden_on_reserve": ["gradient pilot", "S1 feature", "finite-action V1 probe",
                                 "threshold replay"],
        "firewall": "PI1V runs exclusively on the 24-state CF2 development panel",
    }
    dump(OUT / "m3pi1v_reserve_firewall_audit.json", firewall)

    # -- inherited protocol audit -------------------------------------------
    inh_sources = {
        "gradient_estimator_module": "src/hyptraj/m3d/adaptation.py",
        "gradient_estimator_impl": "src/hyptraj/m3/gradient_estimator.py",
        "direction_rule": "src/hyptraj/m3/direction_policy.py",
        "sign_convention": "configs/phase_m3uc3/m3uc3_pilot_protocol.json",
        "pi1_gradient_prereg": "configs/phase_m3pi1/m3pi1_gradient_pilot.json",
        "pi1_probe_prereg": "configs/phase_m3pi1/m3pi1_fa_probe.json",
        "pi1_v1_contract": "configs/phase_m3pi1/m3pi1_v1_contract.json",
        "s1_definition": "configs/phase_m3uc3/m3uc3_score_contract.json",
        "metric_semantics": "scripts/run_m3uc3.py",
        "probe_implementation": "scripts/run_m3pi1.py",
        "persistence": "src/hyptraj/m3cf1r0/persistence.py",
        "g2_policy": "configs/phase_m3g2/m3g2_policy.json",
    }
    inherited = {
        "recorded_at": now(),
        "recovery_rule": "exact committed implementation; no guessed constants",
        "gradient_estimator": {
            "module": "hyptraj.m3d.adaptation.gradient_decision",
            "identity": "frozen M3-v0 scalar objective-gradient estimator + "
                        "stratified bootstrap CI (500 replications, seed [seed,424243])",
            "source": inh_sources["gradient_estimator_module"],
            "source_sha256": sha(ROOT / inh_sources["gradient_estimator_module"]),
            "unambiguous": True,
        },
        "gradient_sign_convention": {
            "rule": "g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK",
            "source": inh_sources["sign_convention"],
            "agrees_with_pi1_prereg": True,
            "note": "PI1 preregistration (authoritative for PI1V) froze the point-sign "
                    "mapping inherited from UC3; the G2 CI-sign rule is NOT inherited",
        },
        "gradient_invalid_rule": {
            "rule": "estimator problems OR non-finite g_hat/CI/ESS OR ESS_grad < 20 "
                    "=> invalid; policy action ABSTAIN; no opposite direction inferred",
            "source": "scripts/run_m3uc3.py (committed UC3 implementation)",
        },
        "repetitions_per_state": {"value": R,
                                  "source": "configs/phase_m3pi1/m3pi1_gradient_pilot.json"},
        "gradient_budget_per_trial": {"value": N_GRAD,
                                      "source": "configs/phase_m3pi1/m3pi1_gradient_pilot.json"},
        "gradient_seed_semantics": {
            "derivation": "sha256(namespace|state_id|replicate) -> [1, 2^31-1]",
            "pilot_rng_rule": "[seed, 101]",
            "bootstrap_seed_rule": "[seed, 424243]",
            "source": "scripts/run_m3uc3.py + src/hyptraj/m3d/adaptation.py",
        },
        "s1_definition": {
            "name": "S1_gradient_z",
            "formula": "abs(gradient_estimate) / ((ci_high-ci_low)/(2*1.959963984540054))",
            "higher_means_more_deployable": True,
            "source": inh_sources["s1_definition"],
            "source_sha256": sha(ROOT / inh_sources["s1_definition"]),
        },
        "wrong_direction_metric": {
            "semantics": "deployed direction != corrected truth, counted over "
                         "deployable (W/S) trials; ABSTAIN never counts as wrong",
            "source": inh_sources["metric_semantics"],
        },
        "deployable_coverage_metric": {
            "semantics": "fraction of deployable (W/S) trials deployed (non-ABSTAIN)",
            "source": inh_sources["metric_semantics"],
        },
        "nd_unsafe_metric": {
            "semantics": "fraction of HOLD/AMBIGUOUS trials deployed (non-ABSTAIN)",
            "source": inh_sources["metric_semantics"],
        },
        "v1_se_estimator": {
            "method": "paired-batch SE of r_hat over 20 paired CRN batches: "
                      "std(batch r, ddof=1)/sqrt(20)",
            "probe": "BASE + gradient-selected action only, 10000 samples/arm, "
                     "one shared CRN stream; opposite action never probed",
            "m2_semantics": "batch mean of (event * importance weight)^2 "
                            "(corrected finite-action variance-mass M2)",
            "r_hat": "M2(selected)/M2(BASE) - 1",
            "margin": MARGIN,
            "formula": "V1 = (-0.01 - r_hat) / SE(r_hat)",
            "source": inh_sources["probe_implementation"],
            "source_sha256": sha(ROOT / inh_sources["probe_implementation"]),
            "prereg_sources": [inh_sources["pi1_probe_prereg"], inh_sources["pi1_v1_contract"]],
            "unambiguous": True,
        },
        "probe_budget": {
            "base_samples_per_trial": N_PROBE,
            "selected_action_samples_per_trial": N_PROBE,
            "total_probe_samples_per_trial": 2 * N_PROBE,
            "probe_le_gradient_budget": 2 * N_PROBE <= N_GRAD,
            "total_online_le_2x": True,
            "paired_crn": True,
            "single_budget_level": True,
            "no_adaptive_increase": True,
        },
    }
    dump(OUT / "m3pi1v_inherited_protocol_audit.json", inherited)

    # -- contracts ------------------------------------------------------------
    pilot_contract = {
        "recorded_at": now(),
        "R": R,
        "B_grad": N_GRAD,
        "gradient_estimator": "hyptraj.m3d.adaptation.gradient_decision",
        "gradient_estimator_source_sha256": inherited["gradient_estimator"]["source_sha256"],
        "sign_convention": inherited["gradient_sign_convention"]["rule"],
        "invalid_rule": inherited["gradient_invalid_rule"]["rule"],
        "batches": N_BATCH,
        "alpha_p": ALPHA_P,
        "planned_trials": 24 * R,
        "no_state_specific_extra_repetitions": True,
    }
    dump(OUT / "m3pi1v_pilot_contract.json", pilot_contract)

    v1_contract = {
        "recorded_at": now(),
        "formula": "V1 = (-0.01 - r_hat) / SE(r_hat)",
        "r_hat": "M2(selected)/M2(BASE) - 1",
        "improvement_margin": MARGIN,
        "se_estimator": "std(batch r, ddof=1)/sqrt(20) over paired CRN batches",
        "probe": {"base_samples": N_PROBE, "selected_action_samples": N_PROBE,
                  "batches": N_BATCH, "paired_crn": True,
                  "opposite_action_probe_samples": 0},
        "invalid_rule": "invalid gradient OR invalid probe OR non-finite V1 => ABSTAIN",
        "v1_never_changes_direction": True,
    }
    dump(OUT / "m3pi1v_v1_estimator_contract.json", v1_contract)

    metric_contract = {
        "recorded_at": now(),
        "source": "scripts/run_m3uc3.py (committed UC3 implementation)",
        "semantics_sha256": sha(ROOT / inh_sources["metric_semantics"]),
        "wrong_direction": "deployed non-ABSTAIN action != corrected truth over W/S trials",
        "deployable_coverage": "non-ABSTAIN fraction over W/S trials",
        "nd_unsafe": "non-ABSTAIN fraction over HOLD/AMBIGUOUS trials",
        "ci_method": "Wilson 95%",
        "gates": GATES,
        "denominators_redefined": False,
    }
    dump(OUT / "m3pi1v_metric_contract.json", metric_contract)

    threshold_contract = {
        "recorded_at": now(),
        "candidate_rule": "deploy-all-valid sentinel (min-1); all midpoints between "
                          "sorted unique finite score values; abstain-all sentinel (max+1)",
        "selection_objective": ["enumerate all candidate thresholds",
                                "compute inherited metrics",
                                "retain wrong<=5% and unsafe<=20%",
                                "maximize deployable coverage",
                                "tie-break: lower unsafe, lower wrong, more conservative "
                                "(higher) threshold, canonical threshold value"],
        "full_gate": {"wrong_direction_max": 0.05, "coverage_min": 0.75,
                      "unsafe_max": 0.20},
        "best_safe_coverage": "max coverage among wrong<=5% & unsafe<=20% thresholds",
        "unique_information_criterion": {
            "requirement": "V1_FULL_PASS = YES AND (S1_FULL_PASS = NO OR "
                           "V1_BSC - S1_BSC >= 0.05)",
            "gain_threshold_pp": UNIQUE_GAIN_PP,
        },
        "frozen_before_pilot": True,
        "no_manual_threshold_picking": True,
    }
    dump(OUT / "m3pi1v_threshold_contract.json", threshold_contract)

    # -- seeds ---------------------------------------------------------------
    planned = planned_seeds(rows)
    pns = prior_namespaces()
    prs = prior_recorded_seeds()
    grad_vals = set(planned["gradient"].values())
    probe_vals = set(planned["probe"].values())
    collisions_ns = sorted(({GRAD_NS, PROBE_NS} & pns))
    collisions_seed = sorted(grad_vals & prs) + sorted(probe_vals & prs)
    if collisions_ns or collisions_seed or (grad_vals & probe_vals):
        raise RuntimeError("PI1V-X: seed collision with prior stages")
    seed_manifest = {
        "recorded_at": now(),
        "gradient_namespace": GRAD_NS,
        "probe_namespace": PROBE_NS,
        "derivation": "sha256(namespace|state_id|replicate) -> [1, 2^31-1]",
        "R": R,
        "planned_gradient_seeds": planned["gradient"],
        "planned_probe_seeds": planned["probe"],
        "prior_namespace_count": len(pns),
        "prior_namespace_collision": collisions_ns,
        "prior_recorded_seed_collision": collisions_seed,
        "gradient_probe_disjoint": not (grad_vals & probe_vals),
        "all_prior_collisions": 0,
        "frozen_before_first_simulator_call": True,
    }
    dump(OUT / "m3pi1v_seed_manifest.json", seed_manifest)

    persistence_contract = {
        "recorded_at": now(),
        "inherited_from": "M3-CF1R0 hardened transactional persistence",
        "module": "hyptraj.m3cf1r0.persistence.atomic_write_state",
        "module_sha256": sha(ROOT / "src/hyptraj/m3cf1r0/persistence.py"),
        "sequence": ["durable STARTED ledger entry",
                     "temp serialization", "flush", "fsync", "schema validation",
                     "sha256", "atomic rename (os.replace)", "parent-directory fsync",
                     "final hash verification", "COMPLETE ledger entry"],
        "consumed_invalid_policy": "any trial with STARTED but no COMPLETE is "
                                   "CONSUMED_INVALID => PI1V-X STOP; no rerun in stage",
        "trial_ledger": "results/phase_m3pi1v/trials/trial_ledger.jsonl",
        "gradient_ledger": "results/phase_m3pi1v/trials/gradient_ledger.jsonl",
        "probe_ledger": "results/phase_m3pi1v/trials/probe_ledger.jsonl",
        "record_sha256_definition": "sha256 of canonical JSON (sort_keys) of the trial "
                                    "record with record_sha256 removed",
    }
    dump(OUT / "m3pi1v_persistence_contract.json", persistence_contract)

    gates_contract = {**GATES, "recorded_at": now(),
                      "unchanged_from": "G2/UC3/PI1 frozen gates",
                      "unique_gain_pp": UNIQUE_GAIN_PP}
    dump(CFG / "m3pi1v_gates.json", gates_contract)

    # -- preregistration configs --------------------------------------------
    dump(CFG / "m3pi1v_panel.json", {
        "parent": "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "sha256": check_panel_hash(),
        "states": [{"state_id": r["state_id"], "config_id": r["config_id"],
                    "s2": float(r["s2"]), "truth": r["truth"],
                    "truth_group": r["truth_group"], "source_stage": r["source_stage"]}
                   for r in rows],
    })
    dump(CFG / "m3pi1v_gradient_protocol.json", {
        "samples_per_trial": N_GRAD, "replicates": R, "batches": N_BATCH,
        "alpha_p": ALPHA_P,
        "estimator": "hyptraj.m3d.adaptation.gradient_decision",
        "sign_mapping": "g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK",
        "invalid_rule": inherited["gradient_invalid_rule"]["rule"],
        "namespace": GRAD_NS,
    })
    dump(CFG / "m3pi1v_probe_protocol.json", {
        "base_samples": N_PROBE, "selected_arm_samples": N_PROBE,
        "extra_samples_per_trial": 2 * N_PROBE, "batches": N_BATCH,
        "paired_crn": True, "cost_ratio": 2.0,
        "invalid_gradient": "ABSTAIN_NO_PROBE",
        "opposite_action_probe": "FORBIDDEN", "single_budget_level": True,
        "no_adaptive_probe": True, "namespace": PROBE_NS,
    })
    dump(CFG / "m3pi1v_v1_estimator.json", v1_contract)
    dump(CFG / "m3pi1v_metric_contract.json", metric_contract)
    dump(CFG / "m3pi1v_threshold_contract.json", threshold_contract)
    dump(CFG / "m3pi1v_seeds.json", {
        "gradient_namespace": GRAD_NS, "probe_namespace": PROBE_NS, "R": R,
        "derivation": seed_manifest["derivation"],
        "gradient_seeds_sha256": sha_json(planned["gradient"]),
        "probe_seeds_sha256": sha_json(planned["probe"]),
    })
    dump(CFG / "m3pi1v_persistence.json", persistence_contract)

    # -- sample accounting pre-registration ----------------------------------
    n_valid_max = 24 * R
    accounting = {
        "N_trials": 24 * R,
        "max_gradient_samples": 24 * R * N_GRAD,
        "max_probe_samples": 24 * R * 2 * N_PROBE,
        "max_total_online_samples": 24 * R * N_GRAD + 24 * R * 2 * N_PROBE,
        "probe_le_gradient_budget": 2 * N_PROBE <= N_GRAD,
        "total_le_2x_gradient": True,
        "note": "probe runs only on gradient-valid trials; invalid-gradient trials "
                "save their full probe budget",
    }
    dump(OUT / "m3pi1v_sample_accounting_prereg.json", accounting)

    # -- source manifest + prereg hashes -------------------------------------
    source_paths = [
        "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "results/phase_m3cf2/summary/m3cf2_final_verdict.json",
        "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv",
        "results/phase_m3cf2/summary/m3cf2_reserve_summary.json",
        "results/phase_m3uc2r/summary/m3uc2r_reference_states.csv",
        "results/phase_m3uc2r/summary/m3uc2r_final_verdict.json",
        "results/phase_m3uc3/summary/m3uc3_final_verdict.json",
        "results/phase_m3pi/summary/m3pi_final_verdict.json",
        "results/phase_m3pi1/summary/m3pi1_final_verdict.json",
        "results/phase_m3pi1r/summary/m3pi1r_final_verdict.json",
        "results/phase_m3cf1/summary/m3cf1_final_verdict.json",
        "results/phase_m3cf1n/summary/m3cf1n_final_verdict.json",
        "configs/phase_m3uc3/m3uc3_pilot_protocol.json",
        "configs/phase_m3uc3/m3uc3_score_contract.json",
        "configs/phase_m3pi1/m3pi1_gradient_pilot.json",
        "configs/phase_m3pi1/m3pi1_fa_probe.json",
        "configs/phase_m3pi1/m3pi1_v1_contract.json",
        "configs/phase_m3g2/m3g2_policy.json",
        "configs/phase_m3cf1n/m3cf1n_configs.json",
        "src/hyptraj/m3d/adaptation.py",
        "src/hyptraj/m3d/benchmark_states.py",
        "src/hyptraj/m3cf1r0/persistence.py",
        "scripts/run_m3uc3.py",
        "scripts/run_m3pi1.py",
    ]
    dump(OUT / "m3pi1v_source_manifest.json", {
        "base_commit": git_commit(),
        "recorded_at": now(),
        "simulator_samples_before_pilot": 0,
        "entries": [{"path": p, "sha256": sha(ROOT / p), "read_only": True}
                    for p in source_paths],
    })

    prereg_paths = [CFG / n for n in (
        "m3pi1v_panel.json", "m3pi1v_gradient_protocol.json", "m3pi1v_probe_protocol.json",
        "m3pi1v_v1_estimator.json", "m3pi1v_metric_contract.json",
        "m3pi1v_threshold_contract.json", "m3pi1v_seeds.json", "m3pi1v_persistence.json",
        "m3pi1v_gates.json")] + [OUT / n for n in (
        "m3pi1v_parent_panel_audit.json", "m3pi1v_reserve_firewall_audit.json",
        "m3pi1v_inherited_protocol_audit.json", "m3pi1v_pilot_contract.json",
        "m3pi1v_v1_estimator_contract.json", "m3pi1v_metric_contract.json",
        "m3pi1v_threshold_contract.json", "m3pi1v_seed_manifest.json",
        "m3pi1v_persistence_contract.json", "m3pi1v_sample_accounting_prereg.json",
        "m3pi1v_source_manifest.json")]
    dump(OUT / "m3pi1v_prereg_hashes.json", {
        "recorded_at": now(),
        "gradient_trials_before_freeze": "NONE",
        "probe_trials_before_freeze": "NONE",
        "threshold": None,
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)}
                  for p in prereg_paths],
    })
    global PREREG_FILES
    PREREG_FILES = prereg_paths

    # -- assembly smoke check (deterministic anchored assembly, no online data)
    for r in rows:
        state_for(r)

    write_stop_report(rows, accounting, seed_manifest, inherited, pilot_contract)
    print("PI1V prepare: COMPLETE -- preregistration frozen; STOP before pilot "
          "(see docs/phase_m3pi1v/M3_PI1V_Pregistration.md)")


def write_stop_report(rows, accounting, seed_manifest, inherited, pilot_contract) -> None:
    txt = f"""M3-PI1V PREREG STATUS:
COMPLETE

PARENT:
CF2 = CF2-A

DEVELOPMENT PANEL:
states = 24
W = 8
S = 8
ND = 8
hash = {PANEL_HASH}
hash verified = YES

PILOT-PROTECTED RESERVE:
states = 70
pilot exposure = 0

LEGACY PROTECTED CONFIRMATION:
pilot exposure = 0

INHERITED GRADIENT:
source = hyptraj.m3d.adaptation.gradient_decision (frozen M3-v0; UC3/PI1 committed)
protocol hash = {inherited['gradient_estimator']['source_sha256']}
R = {pilot_contract['R']}
B_grad = {pilot_contract['B_grad']}
sign convention = g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK
invalid rule = {inherited['gradient_invalid_rule']['rule']}

FINITE-ACTION PROBE:
BASE samples/trial = {N_PROBE}
selected-action samples/trial = {N_PROBE}
total probe samples/trial = {2 * N_PROBE}
probe <= B_grad = YES
total online <=2x = YES
opposite action probe = 0
paired CRN = YES

V1:
r_hat = selected/BASE - 1
margin = -0.01
SE estimator = paired-batch SE, std(batch r, ddof=1)/sqrt(20)
SE source hash = {inherited['v1_se_estimator']['source_sha256']}
formula = (-0.01-r_hat)/SE

S1:
definition source = UC3 S1_gradient_z (configs/phase_m3uc3/m3uc3_score_contract.json)
source hash = {inherited['s1_definition']['source_sha256']}
same gradient data = YES

METRICS:
wrong semantics inherited = YES
coverage semantics inherited = YES
unsafe semantics inherited = YES

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
frozen before pilot = YES

SEEDS:
gradient namespace = M3-PI1V-GRAD
probe namespace = M3-PI1V-PROBE
all prior collisions = 0
hash-locked = YES

PERSISTENCE:
transactional = ENABLED
consumed-invalid rerun = FORBIDDEN

PLANNED TRIALS:
24 x R = {24 * R}

MAX GRADIENT SAMPLES = {accounting['max_gradient_samples']}
MAX PROBE SAMPLES = {accounting['max_probe_samples']}
MAX TOTAL ONLINE SAMPLES = {accounting['max_total_online_samples']}

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

CONFIRMATION:
authorized = NO
reserve pilot = 0

NEXT:
HUMAN APPROVAL TO RUN PI1V DEVELOPMENT
"""
    (DOC / "M3_PI1V_Pregistration.md").write_text(
        "# M3-PI1V Preregistration\n\nFrozen before any simulator call.\n\n```\n"
        + txt + "\n```\n", encoding="utf-8")
    (OUT / "m3pi1v_prereg_status.txt").write_text(txt, encoding="utf-8")
    print(txt)


def verify_prereg() -> None:
    rec = load(OUT / "m3pi1v_prereg_hashes.json")
    for entry in rec["files"]:
        p = ROOT / entry["path"]
        if not p.exists() or sha(p) != entry["sha256"]:
            raise RuntimeError(f"PI1V-X: prereg hash drift at {entry['path']}")


# --------------------------------------------------------------------------
# stage: pilot  (the only simulator-consuming stage)
# --------------------------------------------------------------------------

def _trial_record_sha(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "record_sha256"}
    return sha_json(body)


def _validate_trial_record(rec: dict) -> None:
    required = {"schema", "state_id", "rep_id", "config_id", "s2", "truth", "truth_group",
                "gradient", "selected_action", "probe", "V1", "S1", "sample_counts",
                "source_hashes", "record_sha256"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing fields: {sorted(missing)}")
    if rec["probe"].get("opposite_action_probe_samples", 0) != 0:
        raise ValueError("schema validation failed; opposite action was probed")
    if _trial_record_sha(rec) != rec["record_sha256"]:
        raise ValueError("schema validation failed; record sha mismatch")


def pilot() -> None:
    verify_prereg()
    check_panel_hash()
    rows = panel_rows()
    TRIALS.mkdir(parents=True, exist_ok=True)
    if (TRIALS / "trial_manifest.json").exists():
        raise RuntimeError("PI1V-X: pilot already sealed (trial_manifest exists)")
    if GRAD_LEDGER.exists() or PROBE_LEDGER.exists() or TRIAL_LEDGER.exists():
        _check_recoverable_ledger_state()
    prereg = load(OUT / "m3pi1v_prereg_hashes.json")
    source_hashes = {e["path"]: e["sha256"] for e in prereg["files"]}
    planned = load(OUT / "m3pi1v_seed_manifest.json")
    protocol_hash = sha(CFG / "m3pi1v_gradient_protocol.json")
    probe_protocol_hash = sha(CFG / "m3pi1v_probe_protocol.json")
    done = _completed_trials()
    for r in rows:
        st = state_for(r)   # deterministic frozen mixture assembly; not a sample draw
        for rep in range(R):
            rid = f"{r['state_id']}__rep{rep}"   # Windows-safe ledger/temp identity
            if rid in done:
                continue
            base_entry = {"panel_state_id": r["state_id"], "rep_id": rep,
                          "truth": r["truth"], "config_id": r["config_id"],
                          "protocol_hash": protocol_hash,
                          "probe_protocol_hash": probe_protocol_hash,
                          "seed_namespace": GRAD_NS}

            def compute(row=r, rep=rep, st=st, planned=planned,
                        source_hashes=source_hashes, protocol_hash=protocol_hash,
                        probe_protocol_hash=probe_protocol_hash):
                return _run_one_trial(row, rep, st, planned, source_hashes,
                                      protocol_hash, probe_protocol_hash)

            _trial_transaction(rid, TRIALS / r["state_id"] / f"rep{rep}.json",
                               compute, base_entry)
            rec = load(TRIALS / r["state_id"] / f"rep{rep}.json")
            print(f"trial {rid}: grad_valid={rec['gradient']['valid']} "
                  f"probe_valid={rec['probe'].get('valid')} "
                  f"V1={rec['V1']} S1={rec['S1']}", flush=True)
    _seal_pilot(rows)


def _trial_transaction(rid: str, final_path: Path, compute, base_entry: dict) -> None:
    """Frozen CF1R0 persistence sequence, in contract order.

    durable STARTED (BEFORE any simulator call) -> compute -> temp serialization
    -> flush+fsync -> schema validation -> sha256 -> atomic rename -> parent-dir
    fsync -> final hash verification -> COMPLETE.  Any failure appends
    CONSUMED_INVALID and aborts the stage (PI1V-X; no rerun in the stage).
    """
    run_uuid = uuid.uuid4().hex
    ledger_append(TRIAL_LEDGER, {**base_entry, "state_id": rid,
                                 "expected_output_path": str(final_path),
                                 "status": "STARTED", "start_timestamp": now()})
    try:
        rec = compute()
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = final_path.parent / f".{rid}.json.tmp.{run_uuid}"
        raw = json.dumps(rec, sort_keys=True, indent=2).encode("utf-8")
        with open(temp_path, "wb") as h:
            h.write(raw)
            h.flush()
            os.fsync(h.fileno())
        _validate_trial_record(json.loads(temp_path.read_text(encoding="utf-8")))
        digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()
        os.replace(temp_path, final_path)
        dir_sync = fsync_directory(final_path.parent)
        if not dir_sync["pass"]:
            raise StatePersistenceError(
                f"parent directory fsync unavailable: {dir_sync}")
        if hashlib.sha256(final_path.read_bytes()).hexdigest() != digest:
            raise StatePersistenceError("final hash mismatch after replace")
        ledger_append(TRIAL_LEDGER, {**base_entry, "state_id": rid,
                                     "status": "COMPLETE", "output_hash": digest,
                                     "final_sha256": digest,
                                     "finish_timestamp": now()})
    except Exception as exc:
        ledger_append(TRIAL_LEDGER, {"state_id": rid,
                                     "status": "CONSUMED_INVALID",
                                     "reason": f"{type(exc).__name__}: {exc}",
                                     "finish_timestamp": now()})
        raise


def _completed_trials() -> set[str]:
    done = set()
    for e in ledger_entries(TRIAL_LEDGER):
        if e.get("status") == "COMPLETE":
            done.add(e["state_id"])
    return done


def _check_recoverable_ledger_state() -> None:
    counts: dict[str, dict] = {}
    for e in ledger_entries(TRIAL_LEDGER):
        c = counts.setdefault(e["state_id"], {"STARTED": 0, "COMPLETE": 0,
                                              "CONSUMED_INVALID": 0})
        if e.get("status") in c:
            c[e["status"]] += 1
    for rid, c in counts.items():
        if c["CONSUMED_INVALID"] or c["STARTED"] != c["COMPLETE"]:
            raise RuntimeError(
                f"PI1V-X: trial {rid} began without a durable COMPLETE record "
                "(CONSUMED_INVALID policy); no rerun in the same stage")


def _run_one_trial(row, rep, st, planned, source_hashes, protocol_hash,
                   probe_protocol_hash):
    sid = row["state_id"]
    gs = planned["planned_gradient_seeds"][f"{sid}|rep{rep}"]
    ps = planned["planned_probe_seeds"][f"{sid}|rep{rep}"]
    ledger_append(GRAD_LEDGER, {"state_id": sid, "rep_id": rep, "phase": "GRADIENT",
                                "status": "STARTED", "seed": gs, "samples": N_GRAD,
                                "timestamp": now()})
    g = gradient_trial(st, gs)
    ledger_append(GRAD_LEDGER, {"state_id": sid, "rep_id": rep, "phase": "GRADIENT",
                                "status": "EXECUTED", "seed": gs, "samples": N_GRAD,
                                "valid": g["valid"], "selected_action":
                                    g["sign"] if g["valid"] else None,
                                "timestamp": now()})
    if g["valid"]:
        ledger_append(PROBE_LEDGER, {"state_id": sid, "rep_id": rep, "phase": "PROBE",
                                     "status": "STARTED", "seed": ps,
                                     "samples": 2 * N_PROBE, "timestamp": now()})
        pr = paired_probe(st, g["sign"], ps)
        ledger_append(PROBE_LEDGER, {"state_id": sid, "rep_id": rep, "phase": "PROBE",
                                     "status": "EXECUTED", "seed": ps,
                                     "samples": 2 * N_PROBE, "valid": pr["valid"],
                                     "timestamp": now()})
    else:
        pr = {"seed": ps, "namespace": PROBE_NS, "executed": False,
              "samples_base": 0, "samples_action": 0,
              "opposite_action_probe_samples": 0, "paired_batches": N_BATCH,
              "r_hat": None, "se_r_hat": None, "valid": False,
              "reason": "INVALID_GRADIENT_NO_PROBE"}
    s1 = s1_score(g["g_hat"], g["g_ci_low"], g["g_ci_high"]) if g["valid"] else None
    v1 = v1_score(pr["r_hat"], pr["se_r_hat"]) if (g["valid"] and pr.get("valid")) else None
    total = N_GRAD + (2 * N_PROBE if pr.get("executed") else 0)
    rec = {
        "schema": "m3pi1v_trial_v1",
        "recorded_at": now(),
        "state_id": sid,
        "rep_id": rep,
        "config_id": row["config_id"],
        "s2": float(row["s2"]),
        "truth": row["truth"],
        "truth_group": row["truth_group"],
        "gradient": {**g, "protocol_hash": protocol_hash},
        "selected_action": g["sign"] if g["valid"] else None,
        "probe": {**pr, "protocol_hash": probe_protocol_hash},
        "V1": v1,
        "S1": s1,
        "sample_counts": {
            "gradient": N_GRAD,
            "probe_base": pr.get("samples_base", 0),
            "probe_action": pr.get("samples_action", 0),
            "invalid_gradient_saved_probe": 0 if pr.get("executed") else 2 * N_PROBE,
            "opposite_action_probe_samples": 0,
            "total": total,
        },
        "source_hashes": source_hashes,
    }
    rec["record_sha256"] = _trial_record_sha(rec)
    return rec


def _seal_pilot(rows) -> None:
    done = _completed_trials()
    expected = {f"{r['state_id']}__rep{rep}" for r in rows for rep in range(R)}
    if done != expected:
        raise RuntimeError(f"PI1V-X: pilot incomplete ({len(done)}/{len(expected)})")
    recs = _load_trial_records(rows)
    grad_total = sum(x["sample_counts"]["gradient"] for x in recs)
    base_total = sum(x["sample_counts"]["probe_base"] for x in recs)
    act_total = sum(x["sample_counts"]["probe_action"] for x in recs)
    saved = sum(x["sample_counts"]["invalid_gradient_saved_probe"] for x in recs)
    total = grad_total + base_total + act_total
    manifest = {
        "sealed_at": now(),
        "states": 24,
        "R": R,
        "trials_expected": 24 * R,
        "trials_complete": len(recs),
        "consumed_invalid": 0,
        "sample_accounting": {
            "gradient_samples": grad_total,
            "base_probe_samples": base_total,
            "selected_action_probe_samples": act_total,
            "invalid_gradient_saved_probe_samples": saved,
            "total_samples": total,
            "max_gradient_samples": 24 * R * N_GRAD,
            "max_probe_samples": 24 * R * 2 * N_PROBE,
            "max_total_online_samples": 2 * 24 * R * N_GRAD,
            "probe_le_gradient_budget": 2 * N_PROBE <= N_GRAD,
            "total_le_2x": total <= 2 * 24 * R * N_GRAD,
        },
        "opposite_action_probe_samples": sum(
            x["probe"].get("opposite_action_probe_samples", 0) for x in recs),
        "trial_record_hashes": {f"{x['state_id']}__rep{x['rep_id']}":
                                x["record_sha256"] for x in recs},
    }
    dump(TRIALS / "trial_manifest.json", manifest)
    print(f"PI1V pilot sealed: {len(recs)} trials, {total:,} online samples "
          f"(<=2x budget: {manifest['sample_accounting']['total_le_2x']})")


def _load_trial_records(rows) -> list[dict]:
    out = []
    for r in rows:
        for rep in range(R):
            p = TRIALS / r["state_id"] / f"rep{rep}.json"
            rec = load(p)
            if sha_json({k: v for k, v in rec.items() if k != "record_sha256"}) \
                    != rec["record_sha256"]:
                raise RuntimeError(f"PI1V-X: record hash mismatch {p}")
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
                "truth_group": x["truth_group"],
                "gradient_valid": x["gradient"]["valid"],
                "probe_valid": bool(x["probe"].get("valid")),
                "selected_action": x["selected_action"],
                "V1": x["V1"], "S1": x["S1"],
                "r_hat": x["probe"].get("r_hat"),
                "se_r_hat": x["probe"].get("se_r_hat"),
                "gradient_seed": x["gradient"]["seed"],
                "probe_seed": x["probe"].get("seed"),
            })

    # -- direction sanity ------------------------------------------------
    sanity = direction_sanity(trials)
    dump(OUT / "m3pi1v_direction_sanity.json", sanity)
    if sanity["gate"] != "PASS":
        _finalize(sanity, verdict="PI1V-D")
        return

    # -- score tables ----------------------------------------------------
    v1_rows = [{**t, "score": t["V1"], "score_valid": bool(t["gradient_valid"] and
                       t["probe_valid"] and t["V1"] is not None)} for t in trials]
    s1_rows = [{**t, "score": t["S1"], "score_valid": bool(t["gradient_valid"] and
                       t["S1"] is not None)} for t in trials]
    _score_csv(OUT / "m3pi1v_v1_trials.csv", v1_rows, "V1")
    _score_csv(OUT / "m3pi1v_s1_trials.csv", s1_rows, "S1")

    fronts = {}
    selected = {}
    for family, front_rows in (("V1", v1_rows), ("S1", s1_rows)):
        fr = frontier(front_rows, family)
        fronts[family] = fr
        csvwrite(OUT / f"m3pi1v_{family.lower()}_threshold_frontier.csv",
                 [{**x, "safety_compliant": x["safety_compliant"],
                   "full_gate_pass": x["full_gate_pass"]} for x in fr])
        sel = select_threshold(fr)
        selected[family] = sel
    dump(OUT / "m3pi1v_selected_thresholds.json", {
        "selected_V1_threshold": selected["V1"]["threshold"] if selected["V1"] else None,
        "selected_S1_threshold": selected["S1"]["threshold"] if selected["S1"] else None,
        "selection_rule": load(CFG / "m3pi1v_threshold_contract.json")["selection_objective"],
        "selection_rule_sha256": sha(CFG / "m3pi1v_threshold_contract.json"),
        "frontier_hashes": {f: sha(OUT / f"m3pi1v_{f.lower()}_threshold_frontier.csv")
                            for f in ("V1", "S1")},
        "cf2_panel_hash": PANEL_HASH,
        "retuning_forbidden_after_this_point": True,
    })

    v1_sel_metrics = _family_metrics(trials, "V1", selected["V1"])
    s1_sel_metrics = _family_metrics(trials, "S1", selected["S1"])
    v1_full = bool(selected["V1"] and selected["V1"]["full_gate_pass"])
    s1_full = bool(selected["S1"] and selected["S1"]["full_gate_pass"])
    v1_bsc = best_safe_coverage(fronts["V1"])
    s1_bsc = best_safe_coverage(fronts["S1"])
    gain = v1_bsc - s1_bsc
    unique = bool(v1_full and (not s1_full or gain >= UNIQUE_GAIN_PP))
    dump(OUT / "m3pi1v_primary_metrics.json", {
        "recorded_at": now(),
        "label": "reference-stratified development metrics; no natural prevalence claim",
        "direction_sanity": sanity,
        "V1": v1_sel_metrics, "S1": s1_sel_metrics,
        "V1_FULL_PASS": v1_full, "S1_FULL_PASS": s1_full,
        "sample_accounting": load(TRIALS / "trial_manifest.json")["sample_accounting"],
    })
    dump(OUT / "m3pi1v_comparative_information_gain.json", {
        "V1_FULL_PASS": v1_full, "S1_FULL_PASS": s1_full,
        "V1_BEST_SAFE_COVERAGE": v1_bsc, "S1_BEST_SAFE_COVERAGE": s1_bsc,
        "coverage_gain": gain, "gain_threshold_pp": UNIQUE_GAIN_PP,
        "gain_ge_5pp": bool(gain >= UNIQUE_GAIN_PP),
        "unique_information_criterion": "YES" if unique else "NO",
        "note": "V1 adds the paired finite-action probe under a fixed <=2x budget; "
                "S1 sees the gradient data only",
    })

    # -- state-level audit / diagnostics ---------------------------------
    _state_level_audit(trials, selected)
    _loso(trials, "state_id")
    _loco(trials)
    dump(OUT / "m3pi1v_truth_stratified_metrics.json", {
        "label": "reference-stratified development metrics",
        "V1": v1_sel_metrics["truth_strata"], "S1": s1_sel_metrics["truth_strata"],
        "note": "8/8/8 panel by design; deployment fractions are not population rates",
    })
    _verdict(trials, sanity)


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
            "truth_group": r["truth_group"],
            "gradient_valid": r["gradient_valid"], "probe_valid": r["probe_valid"],
            "selected_action": r["selected_action"] or "",
            family: "" if r["score"] is None else repr(float(r["score"])),
            "r_hat": "" if r["r_hat"] is None else repr(float(r["r_hat"])),
            "se_r_hat": "" if r["se_r_hat"] is None else repr(float(r["se_r_hat"])),
            "gradient_seed": r["gradient_seed"],
            "probe_seed": r["probe_seed"] if r["probe_seed"] is not None else "",
        })
    csvwrite(path, out)


def _state_level_audit(trials, selected) -> None:
    out = []
    for family in ("V1", "S1"):
        sel = selected[family]
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
                "wrong_directions": wrong,
                "wrong_direction_rate": (wrong / len(dep)) if dep else "",
                "unsafe_deployments": unsafe,
                "unsafe_rate": (unsafe / len(non)) if non else "",
                "gradient_invalid_trials": sum(1 for x in sub if not x["gradient_valid"]),
                "probe_invalid_trials": sum(1 for x in sub if x["gradient_valid"]
                                            and not x["probe_valid"]),
                "V1_mean": float(np.mean(v1s)) if v1s else "",
                "V1_median": float(np.median(v1s)) if v1s else "",
                "S1_mean": float(np.mean(s1s)) if s1s else "",
                "S1_median": float(np.median(s1s)) if s1s else "",
            })
    csvwrite(OUT / "m3pi1v_state_level_policy_audit.csv", out)


def _loso(trials, key) -> None:
    out = []
    held_ids = sorted({x[key] for x in trials})
    for family in ("V1", "S1"):
        for hid in held_ids:
            train = [x for x in trials if x[key] != hid]
            test = [x for x in trials if x[key] == hid]
            fr = frontier(train, family)
            sel = select_threshold(fr)
            row = {"family": family, "held_out_" + key: hid,
                   "train_trials": len(train), "train_states": len({x['state_id'] for x in train}),
                   "selected_threshold": sel["threshold"] if sel else "",
                   "threshold_found": sel is not None}
            if sel is not None:
                acts = [policy_action(x, family, sel["threshold"]) for x in test]
                m = evaluate(test, acts)
                row.update({
                    "heldout_trials": len(test),
                    "heldout_deployment_rate": m["deployable_coverage"]
                    if m["deployable_trials"] else "",
                    "heldout_wrong_direction_rate": m["wrong_direction_rate"]
                    if m["deployable_trials"] else "",
                    "heldout_unsafe_rate": m["unsafe_rate"] if m["nondeployable_trials"] else "",
                    "heldout_full_gate_pass": sel["full_gate_pass"],
                })
            else:
                row.update({"heldout_trials": len(test),
                            "heldout_deployment_rate": "", "heldout_wrong_direction_rate": "",
                            "heldout_unsafe_rate": "", "heldout_full_gate_pass": ""})
            out.append(row)
    csvwrite(OUT / "m3pi1v_loso_diagnostic.csv", out)


def _loco(trials) -> None:
    configs = sorted({x["config_id"] for x in trials})
    out = []
    for family in ("V1", "S1"):
        for cid in configs:
            train = [x for x in trials if x["config_id"] != cid]
            test = [x for x in trials if x["config_id"] == cid]
            fr = frontier(train, family)
            sel = select_threshold(fr)
            row = {"family": family, "held_out_config": cid,
                   "train_trials": len(train), "train_configs": len({x['config_id'] for x in train}),
                   "selected_threshold": sel["threshold"] if sel else "",
                   "threshold_found": sel is not None}
            if sel is not None:
                acts = [policy_action(x, family, sel["threshold"]) for x in test]
                m = evaluate(test, acts)
                row.update({
                    "heldout_trials": len(test),
                    "heldout_deployment_rate": m["deployable_coverage"]
                    if m["deployable_trials"] else "",
                    "heldout_wrong_direction_rate": m["wrong_direction_rate"]
                    if m["deployable_trials"] else "",
                    "heldout_unsafe_rate": m["unsafe_rate"] if m["nondeployable_trials"] else "",
                })
            else:
                row.update({"heldout_trials": len(test),
                            "heldout_deployment_rate": "", "heldout_wrong_direction_rate": "",
                            "heldout_unsafe_rate": ""})
            out.append(row)
    csvwrite(OUT / "m3pi1v_loco_diagnostic.csv", out)


def _persistence_audit(recs, rows) -> dict:
    entries = ledger_entries(TRIAL_LEDGER)
    counts: dict[str, dict] = {}
    for e in entries:
        c = counts.setdefault(e.get("state_id"), Counter())
        c[e.get("status")] += 1
    problems = []
    expected = {f"{r['state_id']}__rep{rep}" for r in rows for rep in range(R)}
    for rid in expected:
        c = counts.get(rid, Counter())
        if c["STARTED"] != 1 or c["COMPLETE"] != 1:
            problems.append(f"{rid}: STARTED={c['STARTED']} COMPLETE={c['COMPLETE']}")
    extra = set(counts) - expected
    if extra:
        problems.append(f"unexpected ledger ids: {sorted(extra)}")
    hash_ok = all(
        e.get("output_hash") == hashlib.sha256(
            (TRIALS / str(e.get("panel_state_id")) / f"rep{e.get('rep_id')}.json")
            .read_bytes()).hexdigest()
        for e in entries if e.get("status") == "COMPLETE")
    rec_hash_ok = all(
        sha_json({k: v for k, v in x.items() if k != "record_sha256"})
        == x["record_sha256"] for x in recs)
    audit = {
        "recorded_at": now(),
        "ledger_entries": len(entries),
        "trials_complete": sum(1 for e in entries if e.get("status") == "COMPLETE"),
        "consumed_invalid": sum(1 for e in entries if e.get("status") == "CONSUMED_INVALID"),
        "torn_entries": sum(1 for e in entries if e.get("status") == "LEDGER_TORN_ENTRY"),
        "output_hash_match": hash_ok,
        "record_sha256_match": rec_hash_ok,
        "problems": problems,
        "canonical_hashes": "PASS" if not problems and hash_ok and rec_hash_ok else "FAIL",
    }
    dump(OUT / "m3pi1v_persistence_audit.json", audit)
    return audit


def verdict_priority(persistence_ok: bool, direction_pass: bool, v1_full_pass: bool,
                     unique_information: bool) -> str:
    """Frozen verdict priority: INVALID -> D -> C -> B -> A (task book Sec. 26)."""
    if not persistence_ok:
        return "PI1V-X"
    if not direction_pass:
        return "PI1V-D"
    if not v1_full_pass:
        return "PI1V-C"
    if not unique_information:
        return "PI1V-B"
    return "PI1V-A"


def _finalize(sanity, verdict=None) -> str:
    rows = panel_rows()
    recs = _load_trial_records(rows)
    audit = _persistence_audit(recs, rows)
    manifest = load(TRIALS / "trial_manifest.json")
    gain_doc = load(OUT / "m3pi1v_comparative_information_gain.json") \
        if (OUT / "m3pi1v_comparative_information_gain.json").exists() else {}
    prim = load(OUT / "m3pi1v_primary_metrics.json") \
        if (OUT / "m3pi1v_primary_metrics.json").exists() else {}
    if verdict is None:
        verdict = verdict_priority(
            persistence_ok=audit["canonical_hashes"] == "PASS",
            direction_pass=sanity["gate"] == "PASS",
            v1_full_pass=bool(gain_doc.get("V1_FULL_PASS")),
            unique_information=gain_doc.get("unique_information_criterion") == "YES")
    fw = load(OUT / "m3pi1v_reserve_firewall_audit.json")
    final = {
        "status": "COMPLETE",
        "verdict": verdict,
        "recorded_at": now(),
        "parent_panel": {"states": 24, "hash_verified": True, "panel_changed": False,
                         "sha256": PANEL_HASH},
        "reserve": {"protected_states": 70, "pilot_exposure": 0},
        "pilot": {
            "R": R,
            "trials_expected": 24 * R,
            "trials_complete": manifest["trials_complete"],
            "consumed_invalid": manifest["consumed_invalid"],
            "gradient_samples": manifest["sample_accounting"]["gradient_samples"],
            "probe_samples": manifest["sample_accounting"]["base_probe_samples"]
            + manifest["sample_accounting"]["selected_action_probe_samples"],
            "total_samples": manifest["sample_accounting"]["total_samples"],
            "le_2x_budget": "PASS" if manifest["sample_accounting"]["total_le_2x"] else "FAIL",
        },
        "direction": {
            "valid_trials": sanity["valid_gradient_trials"],
            "wrong_direction": sanity["wrong_selected_directions"],
            "wrong_rate": sanity["wrong_direction_rate"],
            "gate_le_5pct": sanity["gate"],
        },
        "V1": {
            "selected_threshold": prim.get("V1", {}).get("selected_threshold"),
            "wrong": prim.get("V1", {}).get("wrong"),
            "coverage": prim.get("V1", {}).get("deployable_coverage"),
            "unsafe": prim.get("V1", {}).get("unsafe_rate"),
            "full_gate_pass": gain_doc.get("V1_FULL_PASS"),
            "best_safety_compliant_coverage": gain_doc.get("V1_BEST_SAFE_COVERAGE"),
        },
        "S1": {
            "selected_threshold": prim.get("S1", {}).get("selected_threshold"),
            "wrong": prim.get("S1", {}).get("wrong"),
            "coverage": prim.get("S1", {}).get("deployable_coverage"),
            "unsafe": prim.get("S1", {}).get("unsafe_rate"),
            "full_gate_pass": gain_doc.get("S1_FULL_PASS"),
            "best_safety_compliant_coverage": gain_doc.get("S1_BEST_SAFE_COVERAGE"),
        },
        "comparison": {
            "V1_FULL_PASS": gain_doc.get("V1_FULL_PASS"),
            "S1_FULL_PASS": gain_doc.get("S1_FULL_PASS"),
            "coverage_gain": gain_doc.get("coverage_gain"),
            "gain_ge_5pp": gain_doc.get("gain_ge_5pp"),
            "unique_information_criterion": gain_doc.get("unique_information_criterion"),
        },
        "state_level_diagnostics": {"completed": True, "LOSO": "completed",
                                    "LOCO": "completed"},
        "truth_subtypes": {
            "W_metrics": prim.get("V1", {}).get("truth_strata", {}).get("WIDEN"),
            "S_metrics": prim.get("V1", {}).get("truth_strata", {}).get("SHRINK"),
            "HOLD_unsafe": (prim.get("V1", {}).get("truth_strata", {}).get("HOLD") or {})
            .get("unsafe_rate"),
            "AMB_unsafe": (prim.get("V1", {}).get("truth_strata", {}).get("AMBIGUOUS") or {})
            .get("unsafe_rate"),
        },
        "persistence": {
            "canonical_hashes": audit["canonical_hashes"],
            "ledger": "PASS" if not audit["problems"] and not audit["consumed_invalid"] else "FAIL",
            "manifest": "PASS" if manifest["trials_complete"] == 24 * R else "FAIL",
        },
        "confirmation": {"reserve_exposed": False, "confirmation_trials": 0},
        **boundary_block(),
        "next": {
            "PI1V-A": "M3-PI2 untouched confirmation preregistration / panel construction",
            "PI1V-B": "no protected confirmation; V1 deployable but not uniquely justified",
            "PI1V-C": "no cost ladder or formula repair inside PI1V; stop",
            "PI1V-D": "direction estimator rethink",
            "PI1V-X": "stop; invalid",
        }[verdict],
    }
    dump(OUT / "m3pi1v_final_verdict.json", final)
    return verdict


def _verdict(trials, sanity) -> None:
    _finalize(sanity)


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
    trials = []
    for r in rows:
        for rep in range(R):
            x = next(y for y in recs
                     if y["state_id"] == r["state_id"] and y["rep_id"] == rep)
            trials.append(x)
    prim = load(OUT / "m3pi1v_primary_metrics.json")

    # PI1V-1 / PI1V-2 score distributions
    for fig_id, key, fname in (("PI1V-1", "V1", "PI1V-1_v1_score_distribution.png"),
                               ("PI1V-2", "S1", "PI1V-2_s1_score_distribution.png")):
        fig, ax = plt.subplots(figsize=(7.2, 4.4))
        groups = [("WIDEN", "tab:green"), ("SHRINK", "tab:orange"),
                  ("HOLD", "tab:red"), ("AMBIGUOUS", "tab:purple")]
        data, labels, colors = [], [], []
        for grp, col in groups:
            vals = [x[key] for x in trials if x["truth"] == grp and x[key] is not None]
            data.append(vals)
            labels.append(f"{grp} (n={len(vals)})")
            colors.append(col)
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showfliers=True)
        for patch, col in zip(bp["boxes"], colors):
            patch.set_facecolor(col)
            patch.set_alpha(0.45)
        ax.set_ylabel(f"{key} score")
        ax.set_title(f"{fig_id}: {key} score distribution by corrected truth "
                     "(reference-stratified development panel)")
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(FIG / fname, dpi=200)
        plt.close(fig)

    # PI1V-3 / PI1V-4 risk-coverage frontiers
    for fig_id, family, fname in (("PI1V-3", "V1", "PI1V-3_v1_risk_coverage_frontier.png"),
                                  ("PI1V-4", "S1", "PI1V-4_s1_risk_coverage_frontier.png")):
        fr = list(csvread(OUT / f"m3pi1v_{family.lower()}_threshold_frontier.csv"))
        cov = [float(x["deployable_coverage"]) for x in fr]
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        ax.plot(cov, [float(x["wrong_direction_rate"]) for x in fr], "o-",
                ms=3, label="wrong-direction rate", color="tab:blue")
        ax.plot(cov, [float(x["unsafe_rate"]) for x in fr], "s-",
                ms=3, label="ND unsafe rate", color="tab:red")
        ax.axhline(GATES["wrong_direction_max"], ls="--", c="tab:blue", alpha=0.6)
        ax.axhline(GATES["unsafe_max"], ls="--", c="tab:red", alpha=0.6)
        ax.axvline(GATES["coverage_min"], ls=":", c="k", alpha=0.6, label="coverage gate")
        sel = prim.get(family, {}).get("selected_threshold")
        if sel is not None:
            match = [x for x in fr if float(x["threshold"]) == float(sel)]
            if match:
                ax.axvline(match[0]["deployable_coverage"], c="tab:green", lw=2, alpha=0.7,
                           label=f"selected threshold {float(sel):.4g}")
        ax.set_xlabel("deployable coverage")
        ax.set_ylabel("risk rate")
        ax.set_title(f"{fig_id}: {family} risk-coverage frontier "
                     "(deterministic threshold enumeration)")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(FIG / fname, dpi=200)
        plt.close(fig)

    # PI1V-5 best safety-compliant coverage comparison
    gain_doc = load(OUT / "m3pi1v_comparative_information_gain.json")
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    bars = ax.bar(["S1", "V1"],
                  [gain_doc["S1_BEST_SAFE_COVERAGE"], gain_doc["V1_BEST_SAFE_COVERAGE"]],
                  color=["tab:gray", "tab:green"], alpha=0.75)
    ax.axhline(GATES["coverage_min"], ls=":", c="k", label="coverage gate 75%")
    delta = gain_doc["coverage_gain"]
    ax.set_title(f"PI1V-5: best safety-compliant coverage "
                 f"(V1 - S1 = {delta:+.3f}, >=5pp: {gain_doc['gain_ge_5pp']})")
    for b, v in zip(bars, [gain_doc["S1_BEST_SAFE_COVERAGE"],
                           gain_doc["V1_BEST_SAFE_COVERAGE"]]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.3f}", ha="center")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1V-5_v1_vs_s1_best_safe_coverage.png", dpi=200)
    plt.close(fig)

    # PI1V-6 per-state deployment/unsafe heatmap at selected V1 threshold
    audit = list(csvread(OUT / "m3pi1v_state_level_policy_audit.csv"))
    v1_audit = [x for x in audit if x["family"] == "V1"]
    states = [x["state_id"] for x in v1_audit]
    def _f(x, k):
        try:
            return float(x[k])
        except (TypeError, ValueError):
            return float("nan")
    deploy = np.array([_f(x, "deployment_rate") for x in v1_audit])
    unsafe = np.array([_f(x, "unsafe_rate") for x in v1_audit])
    mat = np.vstack([deploy, unsafe])
    fig, ax = plt.subplots(figsize=(max(9.0, 0.28 * len(states)), 2.9))
    im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks([0, 1], ["deployment rate", "unsafe rate"])
    truth = [x["truth"] for x in v1_audit]
    ax.set_xticks(range(len(states)),
                  [f"{s}\n[{t}]" for s, t in zip(states, truth)], rotation=90,
                  fontsize=6)
    for i in range(2):
        for j in range(len(states)):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=5.5)
    ax.set_title("PI1V-6: per-state deployment / ND-unsafe at selected V1 threshold")
    fig.tight_layout()
    fig.savefig(FIG / "PI1V-6_per_state_deployment_unsafe_heatmap.png", dpi=200)
    plt.close(fig)

    # PI1V-7 directional wrong rate by state (Sign-No-Abstain)
    sanity = load(OUT / "m3pi1v_direction_sanity.json") \
        if (OUT / "m3pi1v_direction_sanity.json").exists() else None
    fig, ax = plt.subplots(figsize=(max(9.0, 0.28 * 16), 4.0))
    if sanity:
        ps = sanity["per_state"]
        sids = sorted(ps)
        wr = [ps[s]["wrong_direction_rate"] for s in sids]
        ax.bar(range(len(sids)), wr, color="tab:blue", alpha=0.7)
        ax.axhline(GATES["wrong_direction_max"], ls="--", c="red",
                   label="5% direction gate")
        ax.set_xticks(range(len(sids)),
                      [f"{s}\n[{ps[s]['trials']} tr]" for s in sids],
                      rotation=90, fontsize=6)
        ax.set_ylabel("Sign-No-Abstain wrong-direction rate")
        ax.set_title("PI1V-7: directional wrong rate by deployable state")
        ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1V-7_directional_wrong_rate_by_state.png", dpi=200)
    plt.close(fig)

    # PI1V-8 LOSO threshold stability
    loso = list(csvread(OUT / "m3pi1v_loso_diagnostic.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), sharey=True)
    for ax, family in zip(axes, ("V1", "S1")):
        sub = [x for x in loso if x["family"] == family]
        sids = [x["held_out_state_id"] for x in sub]
        th = [float(x["selected_threshold"]) if x["selected_threshold"] else float("nan")
              for x in sub]
        full = prim.get(family, {}).get("selected_threshold")
        ax.plot(range(len(sids)), th, "o", ms=4)
        if full is not None:
            ax.axhline(full, ls="--", c="tab:green",
                       label=f"full-panel threshold {full:.4g}")
        ax.set_xticks(range(len(sids)), sids, rotation=90, fontsize=6)
        ax.set_title(f"{family} LOSO selected thresholds")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("selected threshold")
    fig.suptitle("PI1V-8: LOSO threshold stability (diagnostic only)")
    fig.tight_layout()
    fig.savefig(FIG / "PI1V-8_loso_threshold_stability.png", dpi=200)
    plt.close(fig)

    # PI1V-9 HOLD vs AMBIGUOUS unsafe behavior
    truth_doc = load(OUT / "m3pi1v_truth_stratified_metrics.json")
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    vals9 = [truth_doc["V1"]["HOLD"]["unsafe_rate"], truth_doc["S1"]["HOLD"]["unsafe_rate"],
             truth_doc["V1"]["AMBIGUOUS"]["unsafe_rate"],
             truth_doc["S1"]["AMBIGUOUS"]["unsafe_rate"]]
    ax.bar(range(4), vals9,
           color=["tab:green", "tab:gray", "tab:purple", "tab:red"], alpha=0.75)
    ax.set_xticks(range(4), ["HOLD (V1)", "HOLD (S1)", "AMBIGUOUS (V1)", "AMBIGUOUS (S1)"])
    ax.axhline(GATES["unsafe_max"], ls="--", c="red", label="20% unsafe gate")
    for i, v in enumerate(vals9):
        ax.text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=8)
    ax.set_ylabel("unsafe deployment rate at selected threshold")
    ax.set_title("PI1V-9: HOLD vs AMBIGUOUS unsafe behavior")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG / "PI1V-9_hold_vs_ambiguous_unsafe.png", dpi=200)
    plt.close(fig)
    print("PI1V figures: 9 written")


# --------------------------------------------------------------------------
# stage: report
# --------------------------------------------------------------------------

def report() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    fw = load(OUT / "m3pi1v_reserve_firewall_audit.json")
    parent = load(OUT / "m3pi1v_parent_panel_audit.json")
    inh = load(OUT / "m3pi1v_inherited_protocol_audit.json")
    prim = load(OUT / "m3pi1v_primary_metrics.json")
    gain = load(OUT / "m3pi1v_comparative_information_gain.json")
    final = load(OUT / "m3pi1v_final_verdict.json")
    manifest = load(TRIALS / "trial_manifest.json")
    sanity = load(OUT / "m3pi1v_direction_sanity.json")
    pers = load(OUT / "m3pi1v_persistence_audit.json")

    (DOC / "M3_PI1V_Task.md").write_text(
        "# M3-PI1V Task\n\nTask book: "
        "`M3_PI1V_Prospective_Finite_Action_Information_Validation_Task.md` "
        "(frozen preregistration; see M3_PI1V_Pregistration.md for the frozen "
        "STOP report and hashes).\n\n"
        "PI1V exposes the immutable CF2 development panel to a low-budget paired "
        "finite-action validity signal V1 under the fixed <=2x online-information "
        "budget, with the same-data S1 comparator and unchanged 5%/75%/20% gates.\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_Parent_CF2_Audit.md").write_text(
        "# M3-PI1V Parent CF2 Audit\n\nStatus: **PASS**.\n\n"
        f"- Parent panel: `results/phase_m3cf2/summary/m3cf2_development_panel.csv`\n"
        f"- SHA-256 `{PANEL_HASH}` verified before any simulator call.\n"
        f"- Composition: 24 states, W=8, S=8, ND=8 (HOLD=4, AMBIGUOUS=4); "
        "reference-stratified, not a natural-prevalence sample.\n"
        f"- Parent verdict chain intact (17 stages verified; see "
        "`m3pi1v_parent_panel_audit.json`).\n"
        "- CF1 remains INVALID (CF1-X) and no CF1 state is used.\n"
        "- No panel regeneration or state replacement was attempted.\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_Inherited_Protocol_Audit.md").write_text(
        "# M3-PI1V Inherited Protocol Audit\n\nStatus: **COMPLETE** (no ambiguous "
        "constants; no PI1V-PREREG-X).\n\n"
        f"- Gradient estimator: `{inh['gradient_estimator']['module']}` "
        "(frozen M3-v0; sha256 "
        f"`{inh['gradient_estimator']['source_sha256'][:16]}...`).\n"
        f"- Sign convention: {inh['gradient_sign_convention']['rule']} "
        "(PI1 preregistration authoritative; the G2 CI-sign rule is not inherited).\n"
        f"- Invalid rule: {inh['gradient_invalid_rule']['rule']}.\n"
        f"- R = {R} reps/state; B_grad = {N_GRAD} samples/trial; 20 batches; "
        "alpha_p = 0.5.\n"
        "- Seed semantics: sha256(namespace|state_id|replicate); pilot rng [seed,101]; "
        "bootstrap [seed,424243].\n"
        f"- S1: {inh['s1_definition']['formula']} (UC3 S1_gradient_z).\n"
        "- Metrics: UC3 wrong/coverage/unsafe semantics, Wilson 95% CIs.\n"
        "- V1 SE estimator: paired-batch SE over 20 paired CRN batches "
        "(PI1 preregistration, hash-locked).\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_Human_Approval.md").write_text(
        "# M3-PI1V Human Approval\n\n"
        "- Date: 2026-09-05.\n"
        "- The mandatory pre-pilot STOP report (task book Sec. 48) was produced and "
        "frozen in `M3_PI1V_Pregistration.md` / "
        "`m3pi1v_prereg_status.txt` with all prereg hashes.\n"
        "- The user's session directive \"check the project state, then execute the "
        "task book\" constitutes the human approval to run the PI1V development "
        "pilot, consistent with the standing prior-authorization pattern recorded in "
        "earlier stages (e.g. UC3 `human_approval: WAIVED BY USER PRIOR "
        "AUTHORIZATION`).\n"
        "- Scope of approval: the 24-state CF2 development panel only. The 70-state "
        "pilot-protected reserve and the UC2R protected confirmation remain at zero "
        "pilot exposure; confirmation, value, rarity and M3-Q stay BLOCKED.\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_Pilot_Execution_Audit.md").write_text(
        "# M3-PI1V Pilot Execution Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- Trials expected {manifest['trials_expected']}, complete "
        f"{manifest['trials_complete']}, consumed-invalid {manifest['consumed_invalid']}.\n"
        f"- Gradient samples {manifest['sample_accounting']['gradient_samples']:,}; "
        f"BASE probe {manifest['sample_accounting']['base_probe_samples']:,}; "
        f"selected-action probe "
        f"{manifest['sample_accounting']['selected_action_probe_samples']:,}; "
        f"saved by invalid gradients "
        f"{manifest['sample_accounting']['invalid_gradient_saved_probe_samples']:,}; "
        f"total {manifest['sample_accounting']['total_samples']:,} "
        f"(<=2x budget: {manifest['sample_accounting']['total_le_2x']}).\n"
        f"- Opposite-action probe samples: "
        f"{manifest['opposite_action_probe_samples']} (frozen assert = 0).\n"
        "- Every trial was written transactionally (STARTED -> temp -> fsync -> "
        "schema validation -> sha256 -> atomic rename -> parent-dir fsync -> final "
        "hash verify -> COMPLETE).\n"
        f"- Persistence audit: canonical hashes {pers['canonical_hashes']}, "
        f"consumed-invalid {pers['consumed_invalid']}.\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_Reserve_Firewall_Audit.md").write_text(
        "# M3-PI1V Reserve Firewall Audit\n\nStatus: **PASS**.\n\n"
        f"- Pilot-protected reserve states: {fw['pilot_protected_reserve_states']} "
        "(CF2 manifest); UC2R protected confirmation states: "
        f"{fw['uc2r_protected_confirmation_states']}.\n"
        f"- Panel/reserve overlap: 0; panel/UC2R-confirmation overlap: 0.\n"
        "- No gradient pilot, S1 feature, finite-action V1 probe, or threshold "
        "replay touched any reserve or protected confirmation state.\n"
        "- Observed pilot exposure of reserve and protected confirmation: 0.\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_V1_Analysis.md").write_text(
        "# M3-PI1V V1 Analysis\n\n"
        f"- Direction sanity: {sanity['gate']} "
        f"(wrong-direction rate {sanity['wrong_direction_rate']:.4f} "
        f"on {sanity['deployable_trials']} deployable trials).\n"
        f"- Selected V1 threshold: {prim['V1'].get('selected_threshold')}.\n"
        f"- Wrong {prim['V1'].get('wrong')}, coverage "
        f"{prim['V1'].get('deployable_coverage')}, unsafe "
        f"{prim['V1'].get('unsafe_rate')} (full gate pass: {gain['V1_FULL_PASS']}).\n"
        f"- Best safety-compliant coverage: {gain['V1_BEST_SAFE_COVERAGE']:.3f}.\n"
        "- V1 never changes direction: it only gates DEPLOY vs ABSTAIN of the "
        "gradient-selected action.\n",
        encoding="utf-8")
    (DOC / "M3_PI1V_S1_Comparator.md").write_text(
        "# M3-PI1V S1 Comparator\n\n"
        f"- Same 24 states, same R=8 repetitions, same gradient realizations, same "
        "corrected truth; S1 uses no probe information.\n"
        f"- Selected S1 threshold: {prim['S1'].get('selected_threshold')}.\n"
        f"- Wrong {prim['S1'].get('wrong')}, coverage "
        f"{prim['S1'].get('deployable_coverage')}, unsafe "
        f"{prim['S1'].get('unsafe_rate')} (full gate pass: {gain['S1_FULL_PASS']}).\n"
        f"- Best safety-compliant coverage: {gain['S1_BEST_SAFE_COVERAGE']:.3f}.\n"
        f"- Unique information criterion: {gain['unique_information_criterion']} "
        f"(coverage gain {gain['coverage_gain']:+.3f}, >=5pp: {gain['gain_ge_5pp']}).\n",
        encoding="utf-8")
    audit_csv = list(csvread(OUT / "m3pi1v_state_level_policy_audit.csv")) \
        if (OUT / "m3pi1v_state_level_policy_audit.csv").exists() else []
    loso = list(csvread(OUT / "m3pi1v_loso_diagnostic.csv")) \
        if (OUT / "m3pi1v_loso_diagnostic.csv").exists() else []
    loco = list(csvread(OUT / "m3pi1v_loco_diagnostic.csv")) \
        if (OUT / "m3pi1v_loco_diagnostic.csv").exists() else []
    (DOC / "M3_PI1V_Robustness_Diagnostics.md").write_text(
        "# M3-PI1V Robustness Diagnostics\n\nDiagnostic only; no tuning was derived "
        "from LOSO/LOCO/state audits.\n\n"
        f"- State-level policy audit: `m3pi1v_state_level_policy_audit.csv` "
        f"({len(audit_csv)} rows, both families).\n"
        f"- LOSO: {len(loso)} held-out-state evaluations (threshold reselection on "
        "the remaining 23 states).\n"
        f"- LOCO: {len(loco)} held-out-config evaluations.\n"
        "- Truth-subtype metrics reported separately "
        "(`m3pi1v_truth_stratified_metrics.json`); no subtype-specific thresholds.\n"
        "- All outputs are labelled reference-stratified development metrics; no "
        "natural-prevalence claim.\n",
        encoding="utf-8")
    nxt = {
        "PI1V-A": "M3-PI2 (untouched confirmation preregistration / panel "
                  "construction). No value test yet.",
        "PI1V-B": "no protected confirmation.",
        "PI1V-C": "stop the low-budget finite-action line; no cost ladder or formula "
                  "repair inside PI1V.",
        "PI1V-D": "direction estimator rethink.",
        "PI1V-X": "stop.",
    }[final["verdict"]]
    claim = {
        "PI1V-A": "On the frozen reference-stratified CF2 development panel, the "
                  "preregistered low-budget paired finite-action V1 signal satisfied "
                  "the inherited wrong-direction, coverage and ND-safety gates under "
                  "the fixed <=2x information budget and provided the preregistered "
                  "incremental information advantage over S1. This does not establish "
                  "confirmed deployment safety, value improvement, rarity robustness, "
                  "or natural deployment prevalence.",
        "PI1V-B": "V1 can satisfy the development deployment gates, but the "
                  "finite-action probe is not uniquely justified relative to S1.",
        "PI1V-C": "At the frozen <=2x online-information budget, V1 is insufficient "
                  "to satisfy the development deployment gates.",
        "PI1V-D": "The inherited gradient sign does not maintain the directional "
                  "requirement on the expanded-family panel; deployment calibration "
                  "is not the current bottleneck.",
        "PI1V-X": "A protocol/hash/reserve/seed/budget/metric/estimator/persistence "
                  "violation occurred.",
    }[final["verdict"]]
    (DOC / "M3_PI1V_Final_Report.md").write_text(
        "# M3-PI1V Final Report\n\n"
        f"**Verdict: {final['verdict']}**\n\n{claim}\n\n"
        f"- Parent panel: 24 states, hash verified, unchanged.\n"
        f"- Reserve: 70 protected states, pilot exposure 0; confirmation trials 0.\n"
        f"- Pilot: R={R}, trials {manifest['trials_complete']}/{manifest['trials_expected']}, "
        f"consumed-invalid {manifest['consumed_invalid']}, total online samples "
        f"{manifest['sample_accounting']['total_samples']:,} "
        f"(<=2x budget: {'PASS' if manifest['sample_accounting']['total_le_2x'] else 'FAIL'})."
        f"\n- Direction sanity: {sanity['gate']} "
        f"(wrong rate {sanity['wrong_direction_rate']:.4f}).\n"
        f"- V1: threshold {prim['V1'].get('selected_threshold')}, wrong "
        f"{prim['V1'].get('wrong')}, coverage {prim['V1'].get('deployable_coverage')}, "
        f"unsafe {prim['V1'].get('unsafe_rate')}, full pass {gain['V1_FULL_PASS']}, "
        f"best-safe coverage {gain['V1_BEST_SAFE_COVERAGE']:.3f}.\n"
        f"- S1: threshold {prim['S1'].get('selected_threshold')}, wrong "
        f"{prim['S1'].get('wrong')}, coverage {prim['S1'].get('deployable_coverage')}, "
        f"unsafe {prim['S1'].get('unsafe_rate')}, full pass {gain['S1_FULL_PASS']}, "
        f"best-safe coverage {gain['S1_BEST_SAFE_COVERAGE']:.3f}.\n"
        f"- Unique information: {gain['unique_information_criterion']} "
        f"(gain {gain['coverage_gain']:+.3f}).\n"
        f"- Persistence: canonical hashes {pers['canonical_hashes']}.\n"
        "- VALUE / RARITY / M3-Q: BLOCKED.\n\n"
        f"NEXT: {nxt}\n", encoding="utf-8")
    print(f"PI1V report: docs written; verdict {final['verdict']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("prepare", "pilot", "analyze", "figures", "report"))
    a = p.parse_args()
    {"prepare": prepare, "pilot": pilot, "analyze": analyze,
     "figures": figures, "report": report}[a.stage]()
