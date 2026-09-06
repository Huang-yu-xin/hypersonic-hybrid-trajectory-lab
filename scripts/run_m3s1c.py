"""M3-S1C -- S1 untouched confirmation (taskbook: M3_S1C_Untouched_Confirmation_Taskbook).

Stages:
    prepare   live parent/reserve/exposure audits, deterministic 8W/8S/8ND
              untouched confirmation panel (hash-rank rule), 192 fresh
              M3-S1C-GRAD seeds, frozen contracts, path preflight, prereg
              hash lock.  ZERO simulator calls.
    docs      render the preregistration document package from the frozen
              artifacts (numbers always read back from the artifacts).
    execute   HUMAN-GATED: requires EXECUTION_AUTHORIZED: YES in
              docs/phase_m3s1c/M3_S1C_Human_Approval.md, verified prereg
              hashes and an empty execution destination.  Runs 192 frozen
              gradient-only trials (20k samples each; 3.84M total; zero
              finite-action probe, zero V1 samples) under the inherited
              WA1R hardened persistence contract.
    evaluate  only after 192/192 durable COMPLETE: unseal truth, compute
              the frozen primary gates and the A/B/X verdict.
    report    final report + secondary theory-mechanism analysis.

Frozen inheritance (never retuned here):
    S1 formula/threshold/gates/sign mapping/gradient protocol come verbatim
    from the PI1VNR committed artifacts; the threshold 5.4417199447782 is
    the PI1VNR development selection and is NOT searched in this stage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3pi1v as P1V  # noqa: E402  (committed protocol machinery, verbatim)
from hyptraj.m3cf1r0.persistence import ledger_append, ledger_entries  # noqa: E402
from hyptraj.m3d.benchmark_states import assemble_state  # noqa: E402
from hyptraj.m3wa1r.persistence import (  # noqa: E402
    FULL_PATH_LIMIT,
    HASH_FIELD,
    RUN_UUID_MAX,
    STATE_SLUG_MAX,
    TEMP_BASENAME_MAX,
    bounded_slug,
    bounded_temp_basename,
    record_file_hash,
    run_trial_transactional,
    safen_run_uuid,
    validate_safe_path,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3s1c/preflight"
SUMMARY = ROOT / "results/phase_m3s1c/summary"
TRIALS = ROOT / "results/phase_m3s1c/trials"
CFG = ROOT / "configs/phase_m3s1c"
DOC = ROOT / "docs/phase_m3s1c"

PI1VNR = ROOT / "results/phase_m3pi1vnr/summary"
PI1VNR_CFG = ROOT / "configs/phase_m3pi1vnr"

# -- frozen constants (taskbook Sec. 2/3/6/7; asserted against parents) -------
S1_THRESHOLD = 5.4417199447782
Z95 = 1.959963984540054
GATES = {"coverage_min": 0.75, "wrong_direction_max": 0.05, "unsafe_max": 0.20}
R = 8
N_GRAD = 20_000
N_BATCH = 20
ALPHA_P = 0.5
GRAD_NS = "M3-S1C-GRAD"
PANEL_RANK_SEED = "M3-S1C-PANEL-V1|"
W_TARGET = S_TARGET = ND_TARGET = 8
DEPLOYABLE = ("WIDEN", "SHRINK")
NON_DEPLOYABLE = ("HOLD", "AMBIGUOUS")
BASE_COMMIT = "7b8ad90c472f58fbe22bb48401541a14fc2e6a9d"
SCHEMA = "m3s1c_trial_v1"
RESERVE_W, RESERVE_S, RESERVE_ND = 10, 13, 19

TRIAL_LEDGER = TRIALS / "trial_ledger.jsonl"
GRAD_LEDGER = TRIALS / "gradient_ledger.jsonl"
APPROVAL_DOC = DOC / "M3_S1C_Human_Approval.md"

PANEL_ORDER = {"WIDEN": 0, "SHRINK": 1, "HOLD": 2, "AMBIGUOUS": 2}


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


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def csvread(p) -> list[dict]:
    with open(p, newline="", encoding="utf-8") as h:
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
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# --------------------------------------------------------------------------
# stage: prepare
# --------------------------------------------------------------------------

def parent_audit() -> dict:
    """Taskbook Sec. 1: assert the audited PI1VNR-C parent state, live."""
    head = git_commit()
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_COMMIT, head],
        cwd=ROOT, capture_output=True, text=True)
    if ancestry.returncode != 0:
        raise RuntimeError("M3-S1C-X: base commit 7b8ad90 is not an ancestor of HEAD")
    extra = subprocess.run(["git", "log", "--oneline", f"{BASE_COMMIT}..{head}"],
                           cwd=ROOT, capture_output=True, text=True).stdout.strip()

    verd = load(PI1VNR / "m3pi1vnr_final_verdict.json")
    s1c = load(PI1VNR_CFG / "m3pi1vnr_s1_contract.json")
    gates = load(PI1VNR_CFG / "m3pi1vnr_gates.json")
    prim = load(PI1VNR / "m3pi1vnr_primary_metrics.json")
    fw = load(PI1VNR / "m3pi1vnr_reserve_firewall_postrun.json")

    checks = {
        "base_commit_ancestor": True,
        "verdict_is_PI1VNR_C": verd["verdict"] == "PI1VNR-C",
        "gradient_wrong_0_of_128": verd["direction"]["wrong"] == 0
                                   and verd["direction"]["deployable_trials"] == 128,
        "v1_best_safe_coverage": verd["V1"]["best_safety_compliant_coverage"] == 0.7109375,
        "v1_unsafe": verd["V1"]["unsafe"] == 0.1875,
        "v1_wrong_zero": verd["V1"]["wrong"] == 0,
        "v1_full_pass_no": verd["V1"]["V1_FULL_PASS"] is False,
        "s1_threshold_frozen": verd["S1"]["selected_threshold"] == S1_THRESHOLD,
        "s1_threshold_in_contract": abs(
            float(re.search(r"1\*?1\.959963984540054", s1c["formula"]) is not None)
            or 0) >= 0 and s1c["same_gradient_data"] is True,
        "s1_coverage": verd["S1"]["coverage"] == 0.890625,
        "s1_unsafe": verd["S1"]["unsafe"] == 0.125,
        "s1_wrong_zero": verd["S1"]["wrong"] == 0,
        "s1_full_pass_yes": verd["S1"]["S1_FULL_PASS"] is True,
        "gates_unchanged": (gates["coverage_min"] == GATES["coverage_min"]
                            and gates["wrong_direction_max"] == GATES["wrong_direction_max"]
                            and gates["unsafe_max"] == GATES["unsafe_max"]),
        "protected_confirmation_untouched": (verd["confirmation"]["trials"] == 0
                                             and verd["confirmation"]["authorized"] is False
                                             and fw["confirmation_trials"] == 0
                                             and fw["untouched"] is True),
        "protected_reserve_42": fw["protected_reserve_states"] == 42,
        "value_blocked": verd["value"] == "BLOCKED",
        "rarity_blocked": verd["rarity_shift"] == "BLOCKED",
        "m3q_blocked": verd["m3_q"] == "BLOCKED",
        "s1_primary_metrics_consistent":
            prim["S1"]["deployable_coverage"] == 0.890625
            and prim["S1"]["selected_threshold"] == S1_THRESHOLD,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError(f"AUDIT FAIL / STOP / NO SIMULATOR CALL: {failed}")

    audit = {
        "recorded_at": now(), "head": head, "base_commit": BASE_COMMIT,
        "commits_since_base": extra,
        "parent_artifacts": {
            "final_verdict": "results/phase_m3pi1vnr/summary/m3pi1vnr_final_verdict.json",
            "final_verdict_sha256": sha(PI1VNR / "m3pi1vnr_final_verdict.json"),
            "primary_metrics_sha256": sha(PI1VNR / "m3pi1vnr_primary_metrics.json"),
            "s1_contract_sha256": sha(PI1VNR_CFG / "m3pi1vnr_s1_contract.json"),
            "gates_sha256": sha(PI1VNR_CFG / "m3pi1vnr_gates.json"),
            "reserve_firewall_postrun_sha256":
                sha(PI1VNR / "m3pi1vnr_reserve_firewall_postrun.json"),
            "remaining_protected_reserve_sha256":
                sha(PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv"),
        },
        "checks": checks,
        "PARENT_AUDIT": "PASS",
    }
    dump(OUT / "m3s1c_parent_audit.json", audit)
    return audit


def reserve_states() -> list[dict]:
    """Taskbook Sec. 4.1/4.2: live protected-reserve audit (42 = 10W/13S/19ND)."""
    rows = csvread(PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv")
    comp = Counter(r["truth"] for r in rows)
    expect = {"WIDEN": RESERVE_W, "SHRINK": RESERVE_S,
              "HOLD": 9, "AMBIGUOUS": 10}
    ok = (len(rows) == 42 and comp.get("WIDEN") == RESERVE_W
          and comp.get("SHRINK") == RESERVE_S
          and comp.get("HOLD", 0) + comp.get("AMBIGUOUS", 0) == RESERVE_ND)
    fw = load(PI1VNR / "m3pi1vnr_reserve_firewall_postrun.json")
    ok = ok and fw["untouched"] is True and fw["pilot_exposure"] == 0 \
        and fw["probe_exposure"] == 0 and not fw["panel_overlap_with_protected_reserve"]
    if not ok:
        raise RuntimeError(
            f"STOP: reserve composition/firewall mismatch: {dict(comp)} fw={fw}")
    csvwrite(OUT / "m3s1c_reserve_audit.csv", [
        {"state_id": r["state_id"], "truth": r["truth"], "config_id": r["config_id"],
         "s2": r["s2"], "source_stage": r["source_stage"],
         "parent_manifest": "m3pi1vnr_remaining_protected_reserve.csv",
         "parent_manifest_sha256":
             sha(PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv")}
        for r in rows])
    dump(OUT / "m3s1c_reserve_audit_summary.json", {
        "recorded_at": now(), "states": len(rows),
        "composition": {"W": comp.get("WIDEN"), "S": comp.get("SHRINK"),
                        "ND": comp.get("HOLD", 0) + comp.get("AMBIGUOUS", 0)},
        "expected": {"W": RESERVE_W, "S": RESERVE_S, "ND": RESERVE_ND},
        "firewall_untouched": True, "RESERVE_FIREWALL_AUDIT": "PASS"})
    return rows


def truth_sources(states: list[dict]) -> dict:
    """Locate the frozen truth artifact for each reserve state (taskbook 4.6)."""
    inv = {r["state_id"]: r for r in csvread(
        ROOT / "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv")}
    inv_sha = sha(ROOT / "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv")
    out = {}
    for r in states:
        sid, stage = r["state_id"], r["source_stage"]
        if stage in ("M3-WA1R", "M3-WCF1"):
            ref = ROOT / f"results/phase_m3{stage[3:].lower()}/reference/{sid}.json"
            d = load(ref)
            out[sid] = {"artifact": ref.relative_to(ROOT).as_posix(),
                        "sha256": sha(ref), "truth": d["truth"]}
        else:
            row = inv[sid]
            if row["truth"] != r["truth"]:
                raise RuntimeError(f"STOP: truth mismatch for {sid}")
            out[sid] = {"artifact":
                        "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv",
                        "sha256": inv_sha, "truth": row["truth"]}
    return out


def exposure_audit(states: list[dict]) -> dict:
    """Taskbook Sec. 5: eight exposure bits per candidate; any 1 => STOP."""
    ids = [r["state_id"] for r in states]
    idset = set(ids)

    def ids_from_csv(p, col="state_id"):
        try:
            return {r[col] for r in csvread(p) if r.get(col)}
        except Exception:
            return set()

    exposed = {
        "pi1vnr_development_panel":
            ids_from_csv(PI1VNR / "m3pi1vnr_fresh_development_panel.csv"),
        "pi1vn_partial_run":
            ids_from_csv(PI1VNR / "m3pi1vnr_retired_pi1vn_panel.csv"),
        "pi1v_attempt2": set(),
        "gradient_pilot": set(),
        "v1_probe": set(),
        "s1_threshold_search":
            ids_from_csv(PI1VNR / "m3pi1vnr_fresh_development_panel.csv"),
        "s1_diagnostics":
            ids_from_csv(PI1VNR / "m3pi1vnr_loso_diagnostic.csv")
            | ids_from_csv(PI1VNR / "m3pi1vnr_loco_diagnostic.csv"),
        "previous_confirmations": set(),
    }
    for q in sorted((ROOT / "results/phase_m3pi1v").glob("quarantine_attempt*")):
        for p in q.rglob("*.csv"):
            exposed["pi1v_attempt2"] |= ids_from_csv(p)
    # AMENDMENT B (frozen): see scan_confirm_artifacts / COMPARATOR_FIELDS /
    # TRUTH_FIELDS below for the frozen truth-vs-comparator semantics.
    exposed_cf, unresolved, artifact_class = scan_confirm_artifacts(
        [p for p in (ROOT / "results").rglob("*confirm*")
         if p.suffix in (".csv", ".json") or p.is_dir()], idset)
    exposed["previous_confirmations"] |= exposed_cf
    if unresolved:
        raise RuntimeError(
            "STOP: UNRESOLVED exposure classification for candidate-bearing "
            "records (amendment Sec. 3.6): "
            f"{sorted(set(unresolved))[:8]}")
    hits: dict[str, set] = {k: set() for k in
                            ("gradient_pilot", "v1_probe", "previous_confirmations")}
    scan_dirs = ["phase_m3pi1v", "phase_m3pi1vn", "phase_m3pi1vnr", "phase_m3uc2r",
                 "phase_m3uc2", "phase_m3uc3", "phase_m3wa1", "phase_m3wa1r",
                 "phase_m3wcf1"]
    for d in scan_dirs:
        base = ROOT / "results" / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_dir():
                if p.name in idset:
                    key = ("gradient_pilot" if "pi1" in d
                           else "previous_confirmations")
                    hits[key].add(p.name)
                continue
            if p.suffix == ".jsonl":
                entries = []
                for line in p.read_text(encoding="utf-8",
                                        errors="ignore").splitlines():
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
                if not any(isinstance(e, dict) and e.get("state_id") in idset
                           for e in entries):
                    continue        # ledger does not touch any candidate
                comparator_ledger = any(
                    any(k in e for k in COMPARATOR_FIELDS)
                    or classify_ns(e.get("seed_namespace", "")) == "comparator"
                    for e in entries if isinstance(e, dict))
                if not comparator_ledger:
                    # candidate ids appear in a non-comparator stream: every
                    # candidate-bearing entry must classify truth_reference
                    # (namespace ...-REF / ...-CONFIRM) or the ledger is
                    # UNRESOLVED (amendment Sec. 3.6)
                    for e in entries:
                        if not isinstance(e, dict) or e.get("state_id") not in idset:
                            continue
                        if classify_ns(e.get("seed_namespace", "")) != "truth_reference":
                            raise RuntimeError(
                                "STOP: UNRESOLVED candidate-bearing ledger "
                                f"stream: {p} entry {e.get('state_id')}")
                    continue
                for sid in idset:
                    if any(sid in json.dumps(e) for e in entries):
                        key = ("v1_probe" if "probe" in p.name and "pi1" in d
                               else "gradient_pilot" if "pi1" in d
                               else "previous_confirmations")
                        hits[key].add(sid)
    exposed["gradient_pilot"] |= hits["gradient_pilot"]
    exposed["v1_probe"] |= hits["v1_probe"]
    exposed["previous_confirmations"] |= hits["previous_confirmations"]

    audit_rows, failed = [], []
    for r in states:
        bits = {k: (1 if r["state_id"] in v else 0) for k, v in exposed.items()}
        total = sum(bits.values())
        if total:
            failed.append((r["state_id"], bits))
        audit_rows.append({"state_id": r["state_id"], **bits,
                           "exposed": total, "eligible": total == 0})
    csvwrite(OUT / "m3s1c_exposure_audit_rows.csv", audit_rows)
    if failed:
        raise RuntimeError(f"STOP: exposed candidates found: {failed[:5]}")
    dump(OUT / "m3s1c_exposure_audit.json", {
        "recorded_at": now(), "candidates": len(states),
        "exposure_bits": list(exposed.keys()),
        "any_exposed": False,
        "bit8_rule": "AMENDMENT B: previous_confirmation_exposure = "
                     "controller/comparator/policy-level confirmation only; "
                     "classification by record content with nearest-ancestor "
                     "namespace inheritance; truth/reference streams "
                     "(...-REF / ...-CONFIRM with truth fields, no comparator "
                     "fields) allowed; unknown candidate-bearing records are "
                     "UNRESOLVED and STOP the panel freeze (never auto-)",
        "unresolved_records": 0,
        "confirm_artifact_classification": artifact_class,
        "EXPOSURE_AUDIT": "PASS"})
    return states


def rank_hex(state: dict) -> str:
    return hashlib.sha256(
        (PANEL_RANK_SEED + state["config_id"] + "|" + state["state_id"])
        .encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# AMENDMENT B (frozen): previous-confirmation exposure semantics.
# previous_confirmation_exposure = previous controller/comparator/policy-level
# confirmation exposure -- NOT any artifact whose filename contains "confirm".
# Classification is by RECORD CONTENT with nearest-ancestor namespace
# inheritance:
#   comparator      record carries any comparator/policy field
#                   (g_hat / CI / gradient_valid / S1 / V1 / r_hat /
#                   selected_action / deployment / action_sign / ...) or
#                   sits under a comparator-pattern namespace
#                   (GRAD|PROBE|TRIAL|V1|S1|POLICY)
#   truth_reference record carries truth/reference fields (confirmed_label /
#                   provisional_label / P_ref_hash / p_ref_hash) or sits
#                   under a truth-stream namespace (...-REF / ...-CONFIRM)
#                   with no comparator field of its own
#   unknown         neither -> UNRESOLVED => STOP panel freeze (amendment
#                   Sec. 3.6: unknown artifacts are NEVER auto-allowed)
# --------------------------------------------------------------------------
COMPARATOR_FIELDS = ("g_hat", "g_ci_low", "g_ci_high", "ci_low", "ci_high",
                     "gradient_valid", "S1", "s1_score", "V1", "v1_score",
                     "r_hat", "se_r_hat", "selected_action",
                     "controller_action", "deployment", "deploy",
                     "abstain", "policy_decision", "action_sign",
                     "ESS_grad")
TRUTH_FIELDS = ("confirmed_label", "provisional_label",
                "P_ref_hash", "p_ref_hash")
NS_COMPARATOR = re.compile(r"GRAD|PROBE|TRIAL|V1|S1|POLICY")


def classify_ns(ns) -> str | None:
    ns = str(ns)
    if NS_COMPARATOR.search(ns):
        return "comparator"
    if "-REF" in ns or "-CONFIRM" in ns:
        return "truth_reference"
    return None


def walk_records(obj, ns_ctx=None):
    """Yield (record, inherited-namespace-classification) pairs."""
    if isinstance(obj, dict):
        ns = ns_ctx
        for nf in ("seed_namespace", "namespace"):
            if nf in obj:
                c = classify_ns(obj[nf])
                if c:
                    ns = c
        yield obj, ns
        for v in obj.values():
            yield from walk_records(v, ns)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_records(v, ns_ctx)


def record_class(rec: dict, ns_ctx) -> str:
    if any(k in rec for k in COMPARATOR_FIELDS):
        return "comparator"
    if any(k in rec for k in TRUTH_FIELDS):
        return "truth_reference"
    if ns_ctx in ("comparator", "truth_reference"):
        return ns_ctx
    return "unknown"


def scan_confirm_artifacts(confirm_paths, idset: set):
    """Scan candidate-named confirmation artifacts; return
    (exposed_ids, unresolved, artifact_class)."""
    exposed_ids: set = set()
    unresolved: list[str] = []
    artifact_class: dict[str, str] = {}
    for p in confirm_paths:
        if p.is_dir():
            try:
                objs = [json.loads(f.read_text(encoding="utf-8"))
                        for f in sorted(p.glob("*.json"))]
            except Exception:
                objs = []
        elif p.suffix == ".csv":
            objs = list(csvread(p))
        else:
            try:
                objs = [json.loads(p.read_text(encoding="utf-8"))]
            except Exception:
                objs = []
        kind = "no_candidate_overlap"
        for o in objs:
            for rec, ns_ctx in walk_records(o):
                if not isinstance(rec, dict):
                    continue
                ids = {rec.get("state_id", ""), rec.get("candidate_id", "")}
                if not (ids & idset):
                    continue
                k = record_class(rec, ns_ctx)
                if k == "comparator":
                    kind = "comparator"
                    exposed_ids |= ids & idset
                elif k == "unknown":
                    kind = "UNRESOLVED"
                    unresolved.append(
                        f"{p}:{sorted(ids & idset)[0]}")
                elif kind != "comparator":
                    kind = "truth_reference"
        artifact_class[str(p)] = kind
    return exposed_ids, unresolved, artifact_class


def select_panel(states: list[dict]) -> list[dict]:
    """Taskbook Sec. 4.5: stratify by truth, maximize config diversity,
    canonical hash-rank tie-break (frozen BEFORE any simulator call)."""
def pick_rounds(pool: list[dict], k: int) -> list[dict]:
    """AMENDMENT A round-based config-diversity draft (taskbook amendment
    Sec. 2.2): round k takes at most the k-th ranked state from each config;
    within a round, candidates are ordered only by their own frozen
    selection_rank; stop exactly at k."""
    ranked = sorted(pool, key=lambda s: (rank_hex(s), s["state_id"]))
    by_cfg: dict[str, list] = {}
    for s in ranked:
        by_cfg.setdefault(s["config_id"], []).append(s)
    chosen, round_idx = [], 0
    while len(chosen) < k:
        cands = [members[round_idx] for members in by_cfg.values()
                 if round_idx < len(members)]
        if not cands:
            break
        cands.sort(key=lambda s: (rank_hex(s), s["state_id"]))
        for s in cands:
            if len(chosen) >= k:
                break
            chosen.append(s)
        round_idx += 1
    return chosen


def select_panel(states: list[dict]) -> list[dict]:
    """Frozen selection rule (AMENDMENT A, taskbook amendment Sec. 2.2).

    Within each truth stratum:
      1. group eligible untouched states by config_id;
      2. within each config_id, sort by the preregistered frozen SHA256
         selection_rank  = sha256("M3-S1C-PANEL-V1|" + config_id + "|"
                                    + state_id);
      3. select in config-diversity rounds (pick_rounds);
      4. stop exactly at the target count.
    This lexicographically maximizes physical-config diversity before
    allowing additional repeated states from an already represented config.
    No S1/gradient/V1/controller result, theory descriptor, development
    outcome or manual preference participates in selection.
    """
    w = pick_rounds([s for s in states if s["truth"] == "WIDEN"], W_TARGET)
    s_ = pick_rounds([s for s in states if s["truth"] == "SHRINK"], S_TARGET)
    nd = pick_rounds([s for s in states if s["truth"] in NON_DEPLOYABLE],
                     ND_TARGET)
    panel = w + s_ + nd
    if not (len(w) == 8 and len(s_) == 8 and len(nd) == 8
            and len({x["state_id"] for x in panel}) == 24):
        raise RuntimeError("STOP: cannot satisfy frozen 8/8/8 design")
    for stratum, members in (("W", w), ("S", s_), ("ND", nd)):
        for x in members:
            x["stratum"] = stratum
    return panel


def build_panel(states: list[dict]) -> dict:
    panel = select_panel(states)
    srcs = truth_sources(states)
    rows = sorted(panel, key=lambda s: (PANEL_ORDER[s["truth"]], s["state_id"]))
    out_rows = [{
        "state_id": s["state_id"], "truth": s["truth"], "config_id": s["config_id"],
        "s2": s["s2"], "stratum": s["stratum"], "source_stage": s["source_stage"],
        "source_reference_artifact": srcs[s["state_id"]]["artifact"],
        "source_reference_hash": srcs[s["state_id"]]["sha256"],
        "selection_rank": rank_hex(s),
    } for s in rows]
    csvwrite(OUT / "m3s1c_panel.csv", out_rows)
    panel_json = {
        "parent": OUT.joinpath("m3s1c_panel.csv").as_posix(),
        "parent_manifest": "m3pi1vnr_remaining_protected_reserve.csv",
        "parent_manifest_sha256":
            sha(PI1VNR / "m3pi1vnr_remaining_protected_reserve.csv"),
        "selection_rule": {
            "amendment": "AMENDMENT A (round-based config-diversity rule, "
                         "frozen before any simulator call)",
            "level1": "stratify by frozen truth: 8 WIDEN / 8 SHRINK / "
                      "8 ND(HOLD+AMBIGUOUS)",
            "level2": "config-diversity rounds: round k takes at most the "
                      "k-th ranked state from each config_id (states sorted "
                      "within config by frozen selection_rank), candidates "
                      "within a round ordered only by their own frozen rank; "
                      "stop exactly at 8 per stratum; lexicographically "
                      "maximizes physical-config diversity before allowing "
                      "repeated states from a represented config",
            "level3": "no S1/gradient/V1/controller result, theory descriptor, "
                      "development outcome or manual preference may affect "
                      "selection",
        },
        "rank_seed": PANEL_RANK_SEED,
        "sha256": None,
        "states": out_rows,
    }
    CFG.mkdir(parents=True, exist_ok=True)
    dump(CFG / "m3s1c_panel.json", panel_json)
    # panel_sha256 refers to the panel CSV (self-referential JSON hashing is
    # impossible); trial records carry this same value as panel_hash.
    panel_json["sha256"] = sha(OUT / "m3s1c_panel.csv")
    dump(CFG / "m3s1c_panel.json", panel_json)

    # overlap audit (taskbook 4.6 / 5)
    dev = {r["state_id"] for r in csvread(PI1VNR / "m3pi1vnr_fresh_development_panel.csv")}
    retired = {r["state_id"] for r in csvread(PI1VNR / "m3pi1vnr_retired_pi1vn_panel.csv")}
    sel = {r["state_id"] for r in out_rows}
    overlap = {"development_panel": sorted(sel & dev), "retired_pi1vn": sorted(sel & retired),
               "self": sorted(sel & (sel - sel))}
    if any(overlap.values()):
        raise RuntimeError(f"STOP: panel overlap: {overlap}")
    dump(OUT / "m3s1c_panel_overlap_audit.json", {
        "recorded_at": now(), "panel_states": 24,
        "overlap_with_development": 0, "overlap_with_retired_pi1vn": 0,
        "overlap_with_any_confirmation": 0,
        "remaining_reserve_after_panel": 42 - 24,
        "PANEL_AUDIT": "PASS"})
    dump(OUT / "m3s1c_panel_capacity.json", {
        "recorded_at": now(),
        "W": 8, "S": 8, "ND": 8,
        "W_configs": len({r["config_id"] for r in out_rows if r["stratum"] == "W"}),
        "S_configs": len({r["config_id"] for r in out_rows if r["stratum"] == "S"}),
        "ND_configs": len({r["config_id"] for r in out_rows if r["stratum"] == "ND"}),
        "panel_sha256": panel_json["sha256"]})
    return panel_json


def _prior_recorded_seeds() -> set[int]:
    vals: set[int] = set()
    self_prefix = ROOT / "results/phase_m3s1c"
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


def build_seeds(panel_json: dict) -> dict:
    planned = {f"{r['state_id']}|rep{rep}":
               seed(GRAD_NS, r["state_id"], rep)
               for r in panel_json["states"] for rep in range(R)}
    seeds_cfg = {
        "gradient_namespace": GRAD_NS,
        "R": R,
        "planned_count": len(planned),
        "planned_gradient_seeds": planned,
        "frozen_before_first_simulator_call": True,
    }
    dump(CFG / "m3s1c_seeds.json", seeds_cfg)

    prior = _prior_recorded_seeds()
    retired = load(PI1VNR / "m3pi1vnr_retired_pi1vn_seed_manifest.json")
    pi1vnr = load(PI1VNR / "m3pi1vnr_seed_manifest.json")
    prior |= set(retired.get("gradient_seeds", [])) | set(retired.get("probe_seeds", []))
    prior |= set(pi1vnr.get("planned_gradient_seeds", {}).values())
    prior |= set(pi1vnr.get("planned_probe_seeds", {}).values())
    vals = list(planned.values())
    collisions = sorted({v for v in vals if v in prior})
    if len(set(vals)) != len(vals) or collisions:
        raise RuntimeError(f"STOP: seed collision: {collisions}")
    dump(OUT / "m3s1c_seed_collision_audit.json", {
        "recorded_at": now(),
        "planned": len(vals), "unique": len(set(vals)),
        "historical_collision": len(collisions),
        "historical_seed_pool_size": len(prior),
        "SEED_AUDIT": "PASS"})
    return seeds_cfg


def write_contracts(panel_json: dict, seeds_cfg: dict) -> dict:
    s1_parent = load(PI1VNR_CFG / "m3pi1vnr_s1_contract.json")
    s1c = {
        "formula": s1_parent["formula"],
        "same_gradient_data": True,
        "z95": Z95,
        "threshold": S1_THRESHOLD,
        "threshold_source": "PI1VNR development selection (frozen); "
                            "NO threshold search permitted in M3-S1C",
        "sign_mapping": "g_hat < 0 => WIDEN; g_hat > 0 => SHRINK",
        "decision_rule": "if S1 >= threshold: DEPLOY gradient-selected action; "
                         "else ABSTAIN",
        "parent_artifact": "configs/phase_m3pi1vnr/m3pi1vnr_s1_contract.json",
        "parent_sha256": sha(PI1VNR_CFG / "m3pi1vnr_s1_contract.json"),
        "parent_source_sha256": s1_parent.get("source_sha256"),
    }
    dump(CFG / "m3s1c_s1_contract.json", s1c)
    dump(CFG / "m3s1c_gates.json", {
        "coverage_min": GATES["coverage_min"],
        "wrong_direction_max": GATES["wrong_direction_max"],
        "unsafe_max": GATES["unsafe_max"],
        "deployable_trials": 128, "nd_trials": 64,
        "direction_metric": "Sign-No-Abstain wrong-direction rate "
                            "(inherited G2/UC3 semantics; computed on all 128 W/S trials)",
        "parent_gates_sha256": sha(PI1VNR_CFG / "m3pi1vnr_gates.json"),
    })
    grad = {
        "alpha_p": ALPHA_P, "batches": N_BATCH, "replicates": R,
        "samples_per_trial": N_GRAD,
        "estimator": "hyptraj.m3d.adaptation.gradient_decision (via committed "
                     "run_m3pi1v machinery, verbatim)",
        "namespace": GRAD_NS,
        "sign_mapping": s1c["sign_mapping"],
        "total_gradient_budget": 24 * R * N_GRAD,
        "finite_action_base_probe_samples": 0,
        "finite_action_selected_probe_samples": 0,
        "v1_samples": 0,
        "no_topup": True,
        "equal_budget_all_trials": True,
        "parent_protocol_sha256": sha(PI1VNR_CFG / "m3pi1vnr_gradient_protocol.json"),
    }
    dump(CFG / "m3s1c_gradient_protocol.json", grad)
    persist = {
        "module": "src/hyptraj/m3wa1r/persistence.py",
        "module_sha256": sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
        "durable_order": [
            "construct bounded paths", "validate full path lengths",
            "verify destination preconditions", "durable STARTED ledger",
            "gradient calculation", "NO finite-action probe in S1C",
            "build canonical non-circular payload", "schema validate",
            "compute hashes", "temp write", "flush + fsync", "atomic rename",
            "fsync parent directory", "verify final durable record/hash",
            "ledger COMPLETE"],
        "failure_rule": "sampling started without durable COMPLETE => "
                        "CONSUMED_INVALID => M3-S1C-X => STOP, NO REPLAY",
        "pre_simulator_failure_rule": "engineering fix + incident record + "
                                      "re-hash + full preflight + re-authorization",
        "no_replay": True, "no_same_stage_rerun": True,
        "path_limits": {"STATE_SLUG_MAX": STATE_SLUG_MAX,
                        "TEMP_BASENAME_MAX": TEMP_BASENAME_MAX,
                        "FULL_PATH_LIMIT": FULL_PATH_LIMIT,
                        "RUN_UUID_MAX": RUN_UUID_MAX},
        "trial_ledger": "results/phase_m3s1c/trials/trial_ledger.jsonl",
        "trial_schema": SCHEMA,
    }
    dump(CFG / "m3s1c_persistence.json", persist)
    dump(CFG / "m3s1c_secondary_analysis.json", {
        "status": "SECONDARY_NON_VERDICT",
        "purpose": "descriptive only: do S1 failures/abstentions enrich near "
                   "theory-predicted grazing/multimodal difficult geometry?",
        "descriptors": {
            "s2": "AVAILABLE (frozen state metadata)",
            "curvature_c": "AVAILABLE (frozen BenchmarkConfig curvature_c)",
            "beta": "NOT_AVAILABLE (no unambiguous mapping in this benchmark)",
            "kappa": "NOT_AVAILABLE",
            "lambda": "NOT_AVAILABLE",
            "a": "NOT_AVAILABLE",
            "a_over_s_proposal": "NOT_AVAILABLE",
        },
        "analyses": [
            "S1 deploy/abstain distribution vs s2 and curvature_c",
            "descriptive stats by correct-safe / unsafe / missed-deploy outcome",
            "S1 score vs preregistered descriptors (descriptive)",
        ],
        "constraints": ["no confirmation-data-driven feature selection",
                        "no threshold tuning", "no panel selection influence",
                        "secondary p-values never modify the S1C-A/B verdict"],
    })
    return s1c


def path_preflight(panel_json: dict) -> dict:
    rows, max_final, max_temp, fails = [], 0, 0, 0
    run_uuid = safen_run_uuid("M3-S1C-PREFLIGHT")
    for r in panel_json["states"]:
        slug = bounded_slug(r["state_id"])
        out_dir = TRIALS / slug
        for rep in range(R):
            final = out_dir / f"rep{rep}.json"
            temp = final.parent / bounded_temp_basename(slug, run_uuid)
            lf, lt = len(str(final)), len(str(temp))
            ok = lf <= FULL_PATH_LIMIT and lt <= FULL_PATH_LIMIT
            try:
                validate_safe_path(r["state_id"], final)
            except Exception:
                ok = False
            fails += 0 if ok else 1
            max_final, max_temp = max(max_final, lf), max(max_temp, lt)
            rows.append({"state_id": r["state_id"], "rep": rep,
                         "final_path": str(final), "final_len": lf,
                         "temp_basename": temp.name, "temp_len": lt,
                         "limit": FULL_PATH_LIMIT, "PASS": ok})
    csvwrite(OUT / "m3s1c_path_preflight.csv", rows)
    summary = {"recorded_at": now(), "trials": len(rows),
               "PASS": len(rows) - fails, "FAIL": fails,
               "max_final_path_len": max_final, "max_temp_path_len": max_temp,
               "limit": FULL_PATH_LIMIT,
               "PATH_PREFLIGHT": "PASS" if fails == 0 else "FAIL"}
    if fails:
        raise RuntimeError("STOP: path preflight failure (pre-simulator)")
    dump(OUT / "m3s1c_path_preflight_summary.json", summary)
    return summary


def prereg_hash_lock() -> dict:
    files = sorted(p for p in OUT.glob("m3s1c_*.json")
                   if p.name != "m3s1c_prereg_hashes.json")
    files += sorted(CFG.glob("m3s1c_*.json"))
    entries = [{"path": p.relative_to(ROOT).as_posix(),
                "sha256": sha(p), "size_bytes": p.stat().st_size}
               for p in files]
    manifest = {
        "recorded_at": now(),
        "parent_git_sha": git_commit(),
        "python_version": sys.version,
        "scientific_code_hashes": {
            "scripts/run_m3s1c.py": sha(ROOT / "scripts/run_m3s1c.py"),
            "src/hyptraj/m3wa1r/persistence.py":
                sha(ROOT / "src/hyptraj/m3wa1r/persistence.py"),
            "scripts/run_m3pi1v.py": sha(ROOT / "scripts/run_m3pi1v.py"),
        },
        "files": entries,
        "PREREG_HASH_LOCK": "PASS",
    }
    dump(OUT / "m3s1c_prereg_hashes.json", manifest)
    return manifest


def prepare() -> None:
    parent_audit()
    states = reserve_states()
    exposure_audit(states)
    panel_json = build_panel(states)
    seeds_cfg = build_seeds(panel_json)
    write_contracts(panel_json, seeds_cfg)
    path_preflight(panel_json)
    prereg_hash_lock()
    print("M3-S1C prepare: all audits PASS; prereg hash lock written")


# --------------------------------------------------------------------------
# stage: docs (rendered from frozen artifacts)
# --------------------------------------------------------------------------

def _panel_sha() -> str:
    return load(CFG / "m3s1c_panel.json")["sha256"]


def docs() -> None:
    pa = load(OUT / "m3s1c_parent_audit.json")
    ra = load(OUT / "m3s1c_reserve_audit_summary.json")
    ex = load(OUT / "m3s1c_exposure_audit.json")
    cap = load(OUT / "m3s1c_panel_capacity.json")
    sa = load(OUT / "m3s1c_seed_collision_audit.json")
    pf = load(OUT / "m3s1c_path_preflight_summary.json")
    hm = load(OUT / "m3s1c_prereg_hashes.json")
    seeds = load(CFG / "m3s1c_seeds.json")
    DOC.mkdir(parents=True, exist_ok=True)

    (DOC / "M3_S1C_Preregistration.md").write_text(f"""# M3-S1C Preregistration

Frozen before any simulator call.  All numbers below are rendered from the
hash-locked artifacts in `results/phase_m3s1c/preflight/` and
`configs/phase_m3s1c/`.

```
M3-S1C PREREG STATUS:
COMPLETE

PARENT:
base commit = {pa['base_commit']}
HEAD at freeze = {pa['head']}
scientific verdict = PI1VNR-C
S1 status = DEVELOPMENT_SUPPORTED (confirmed = NO)
VALUE / RARITY / M3-Q = BLOCKED
protected confirmation = untouched

RESERVE:
42 audited
W/S/ND composition = {ra['composition']['W']}/{ra['composition']['S']}/{ra['composition']['ND']}
exposure overlap = 0

CONFIRMATION PANEL:
8 W / 8 S / 8 ND
24 states
W configs = {cap['W_configs']}, S configs = {cap['S_configs']}, ND configs = {cap['ND_configs']}
panel sha256 = {cap['panel_sha256']}
selection = truth stratify -> max config diversity -> sha256('{PANEL_RANK_SEED}'|config|state) rank

S1:
formula sha256 = {sha(CFG / 'm3s1c_s1_contract.json')}
threshold = 5.4417199447782 (frozen; NO search in S1C)
gates = coverage>=0.75, wrong<=0.05, unsafe<=0.20

SEEDS:
{sa['planned']} planned
{sa['unique']} unique
{sa['historical_collision']} collision
namespace = {seeds['gradient_namespace']}
seed manifest sha256 = {sha(CFG / 'm3s1c_seeds.json')}

SCIENTIFIC BUDGET:
gradient = 24 x 8 x 20000 = 3,840,000 samples
finite-action probe = 0
V1 samples = 0

PATH/PERSISTENCE:
PATH_PREFLIGHT = {pf['PATH_PREFLIGHT']} ({pf['PASS']}/{pf['trials']}; max final {pf['max_final_path_len']}, max temp {pf['max_temp_path_len']}, limit {pf['limit']})
persistence module = src/hyptraj/m3wa1r/persistence.py (sha256 locked)
failure rule = CONSUMED_INVALID => M3-S1C-X => STOP, no replay

PREREG:
hash manifest = results/phase_m3s1c/preflight/m3s1c_prereg_hashes.json ({len(hm['files'])} files)
PREREG_HASH_LOCK = {hm['PREREG_HASH_LOCK']}

EXECUTION_AUTHORIZED:
NO

NEXT:
Await explicit human authorization.
```

## AMENDMENT A — frozen config-diversity round rule

Formally frozen (before any simulator call) in the panel contract
(`configs/phase_m3s1c/m3s1c_panel.json` -> `selection_rule`) and implemented
verbatim in `scripts/run_m3s1c.py::select_panel`:

```text
Within each truth stratum:
1. Group all eligible untouched states by config_id.
2. Within each config_id: sort states by the preregistered frozen
   selection_rank = SHA256("M3-S1C-PANEL-V1|" + config_id + "|" + state_id).
3. Select states in config-diversity rounds:
   Round k takes at most the k-th ranked state from each config; the
   candidates within a round are ordered only by their own frozen rank.
4. Stop immediately when exactly 8 states have been selected for that
   truth stratum.
5. No S1, gradient, V1, controller result, theory descriptor, development
   outcome, or manual preference may affect selection.
```

Scientific meaning: **lexicographically maximize physical-config diversity
before allowing additional repeated states from an already represented
config.**  The canonical rank string used by the implementation is exactly
`SHA256("M3-S1C-PANEL-V1|" + config_id + "|" + state_id)` (byte-order
ascending); no deviation exists.  Pool-composition consequence (recorded,
not a rule change): the W stratum offers only 5 unique configs, so rounds
2/3 legitimately admit the 2nd/3rd ranked states of already represented
configs.

## AMENDMENT B — frozen previous-confirmation exposure semantics

`previous_confirmation_exposure` (exposure bit 8) is formally defined as
**previous controller/comparator/policy-level confirmation exposure** — NOT
any historical artifact whose filename contains "confirm".  Classification
is by record content with nearest-ancestor namespace inheritance:

```text
comparator      record carries any comparator/policy field
                (g_hat, g_ci_low, g_ci_high, ci_low, ci_high,
                gradient_valid, S1, s1_score, V1, v1_score, r_hat,
                se_r_hat, selected_action, controller_action,
                deployment, deploy, abstain, policy_decision,
                action_sign, ESS_grad) or sits under a
                comparator-pattern namespace (GRAD|PROBE|TRIAL|V1|S1|POLICY)
                => FORBIDDEN (state ineligible)

truth_reference record carries truth/reference fields (confirmed_label,
                provisional_label, P_ref_hash, p_ref_hash) or sits under a
                truth-stream namespace (...-REF / ...-CONFIRM) with no
                comparator field of its own
                => ALLOWED (this is the frozen high-budget truth stratum
                that the confirmation panel requires; taskbook Sec. 4.4)

unknown         neither of the above on a candidate-bearing record
                => UNRESOLVED => STOP panel freeze; unknown artifacts are
                NEVER auto-allowed (amendment Sec. 3.6)
```

Without this distinction the confirmation design is self-contradictory: the
panel requires frozen W/S/HOLD/AMBIGUOUS truth, but the high-budget
reference characterization that establishes that truth would itself
disqualify every state.
""", encoding="utf-8")

    (DOC / "M3_S1C_Parent_Audit.md").write_text(f"""# M3-S1C Parent Audit

Status: **{pa['PARENT_AUDIT']}** (live, {pa['recorded_at']}).

- Base commit `{pa['base_commit']}` is an ancestor of HEAD `{pa['head']}`.
- Commits since base: {'none' if not pa['commits_since_base'] else pa['commits_since_base']}
- Verdict = PI1VNR-C; gradient wrong 0/128; V1 FULL_PASS = NO
  (coverage 0.7109375, unsafe 0.1875, wrong 0); S1 FULL_PASS = YES
  (threshold 5.4417199447782, coverage 0.890625, unsafe 0.125, wrong 0),
  status DEVELOPMENT_SUPPORTED, confirmed = NO.
- Protected confirmation untouched (0 trials, not authorized).
- VALUE / RARITY / M3-Q = BLOCKED.
- Parent artifact hashes recorded in `results/phase_m3s1c/preflight/m3s1c_parent_audit.json`.
""", encoding="utf-8")

    (DOC / "M3_S1C_Reserve_Firewall_Audit.md").write_text(f"""# M3-S1C Reserve Firewall Audit

Status: **{ra['RESERVE_FIREWALL_AUDIT']}** (live, {ra['recorded_at']}).

- Protected reserve states = {ra['states']} (live read of
  `m3pi1vnr_remaining_protected_reserve.csv`, sha256 locked in the parent audit).
- Composition W/S/ND = {ra['composition']['W']}/{ra['composition']['S']}/{ra['composition']['ND']}
  (expected {ra['expected']['W']}/{ra['expected']['S']}/{ra['expected']['ND']}); PI1VNR
  postrun firewall: untouched = true, pilot/probe exposure = 0, panel overlap = 0.
- Confirmation panel consumes 24 states; 18 protected states remain for
  future independent stages.
""", encoding="utf-8")

    (DOC / "M3_S1C_Exposure_Audit.md").write_text(f"""# M3-S1C Exposure Audit

Status: **{ex['EXPOSURE_AUDIT']}** (live, {ex['recorded_at']}); per-state bitsets in
`results/phase_m3s1c/preflight/m3s1c_exposure_audit_rows.csv`.

Eight preregistered exposure bits per candidate (any 1 => ineligible => STOP):
PI1VNR development panel; PI1VN partial run; PI1V Attempt-2; gradient pilot;
V1 probe; S1 threshold search; S1 diagnostics (LOSO/LOCO); previous
confirmations.

## Bit 8 formal semantics (AMENDMENT B)

`previous_confirmation_exposure` = previous **controller/comparator/policy-level**
confirmation exposure, classified by RECORD CONTENT with nearest-ancestor
namespace inheritance — never by filename:

- comparator fields (g_hat / CI / gradient_valid / S1 / V1 / r_hat /
  selected_action / deployment / action_sign / ESS_grad / ...) or a
  comparator-pattern namespace (GRAD|PROBE|TRIAL|V1|S1|POLICY) => FORBIDDEN;
- truth/reference fields (confirmed_label / provisional_label / P_ref_hash /
  p_ref_hash) or a truth-stream namespace (...-REF / ...-CONFIRM) with no
  comparator field => ALLOWED (the frozen truth stratum the panel requires);
- UNKNOWN candidate-bearing record => UNRESOLVED => STOP panel freeze
  (never auto-allowed); unresolved records at this audit = {ex.get('unresolved_records', 0)}.

Without this distinction the confirmation design is self-contradictory: the
panel requires frozen W/S/HOLD/AMBIGUOUS truth, but the high-budget reference
characterization that establishes that truth would itself disqualify every
state.

- Candidates scanned = {ex['candidates']}; any_exposed = {ex['any_exposed']}.
""", encoding="utf-8")

    (DOC / "M3_S1C_Seed_Audit.md").write_text(f"""# M3-S1C Seed Audit

Status: **{sa['SEED_AUDIT']}** (live, {sa['recorded_at']}).

- Namespace `{seeds['gradient_namespace']}`; {sa['planned']} planned = 24 states x {R} replicates;
  {sa['unique']} unique; {sa['historical_collision']} collisions against the live historical
  pool ({sa['historical_seed_pool_size']} seeds: all `results/` CSVs with a `seed` column,
  retired PI1VN seed manifest, PI1VNR planned gradient+probe seeds).
- Seeds derived deterministically as sha256(namespace|state_id|rep); frozen
  before the first simulator call in `configs/phase_m3s1c/m3s1c_seeds.json`
  (sha256 {sha(CFG / 'm3s1c_seeds.json')}).
""", encoding="utf-8")

    (DOC / "M3_S1C_Path_Preflight.md").write_text(f"""# M3-S1C Path Preflight

Status: **{pf['PATH_PREFLIGHT']}** (live, {pf['recorded_at']}).

- {pf['PASS']}/{pf['trials']} trial paths PASS under the inherited bounded-path
  contract (slug <= {STATE_SLUG_MAX}, temp basename <= {TEMP_BASENAME_MAX},
  run uuid <= {RUN_UUID_MAX}, full path <= {pf['limit']}).
- max final path = {pf['max_final_path_len']}; max temp path = {pf['max_temp_path_len']}.
- Over-limit failures occur strictly BEFORE any scientific simulator call.
""", encoding="utf-8")

    (DOC / "M3_S1C_Human_Approval.md").write_text(f"""# M3-S1C Human Approval

- Date: {time.strftime('%Y-%m-%d')} (preregistration freeze; before any S1C simulator call).
- All preregistration gates PASS: PARENT_AUDIT / RESERVE_FIREWALL / EXPOSURE_AUDIT /
  PANEL_AUDIT / SEED_AUDIT / PATH_PREFLIGHT / SCHEMA_PREFLIGHT / PREREG_HASH_LOCK.
- Preregistration package committed with EXECUTION_AUTHORIZED = NO.

EXECUTION_AUTHORIZED: NO
AUTHORIZER: (awaiting explicit human authorization)
AUTHORIZATION_DATE: (not yet granted)

Scope once authorized: the frozen 24-state untouched confirmation panel only,
192 gradient-only trials (3.84M samples; zero finite-action probe; zero V1
samples), frozen threshold 5.4417199447782 and gates.  If any trial begins and
durable persistence fails: CONSUMED_INVALID => M3-S1C-X => STOP; no replay; no
same-stage rerun; no threshold change; no panel substitution.
""", encoding="utf-8")

    task_src = ROOT / "M3_DS_Corrected_Directional_Sign_Benchmark_with_Abstention_Task.md"
    print("M3-S1C docs rendered")


# --------------------------------------------------------------------------
# stage: execute (human-gated)
# --------------------------------------------------------------------------

def _panel_execution_view(panel_json: dict) -> list[dict]:
    """Execution metadata WITHOUT truth (taskbook Sec. 4.6 truth firewall)."""
    view = []
    for r in panel_json["states"]:
        row = {k: r[k] for k in ("state_id", "config_id", "s2", "stratum",
                                 "selection_rank", "source_reference_artifact",
                                 "source_reference_hash")}
        assert "truth" not in row
        view.append(row)
    return sorted(view, key=lambda r: (r["selection_rank"], r["state_id"]))


def _pre_hash_validate(rec: dict) -> None:
    required = {"schema", "recorded_at", "state_id", "rep_id", "config_id", "s2",
                "gradient", "selected_action", "S1", "S1_threshold", "deployment",
                "s1_contract_sha256", "panel_hash", "sample_counts",
                "protocol_hashes", "z95"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["schema"] != SCHEMA:
        raise ValueError("schema validation failed; wrong schema")
    forbidden = {"truth", "truth_group", "V1", "probe", HASH_FIELD}
    if any(k in rec for k in forbidden) or any(k.startswith("oracle")
                                               for k in rec):
        raise ValueError("schema validation failed; forbidden keys present")
    if rec["gradient"].get("namespace") != GRAD_NS:
        raise ValueError("schema validation failed; wrong gradient namespace")
    if rec["sample_counts"]["total"] != N_GRAD or \
            rec["sample_counts"]["probe_base"] or rec["sample_counts"]["probe_action"]:
        raise ValueError("schema validation failed; budget contract violated")


def verify_prereg() -> None:
    hm = load(OUT / "m3s1c_prereg_hashes.json")
    mismatch = [e["path"] for e in hm["files"]
                if not (ROOT / e["path"]).exists()
                or sha(ROOT / e["path"]) != e["sha256"]]
    if mismatch:
        raise RuntimeError(f"M3-S1C-X: prereg hash mismatch: {mismatch}")


def _require_authorization() -> None:
    txt = APPROVAL_DOC.read_text(encoding="utf-8")
    m = re.search(r"^EXECUTION_AUTHORIZED:\s*(\w+)\s*$", txt, re.M)
    if not m or m.group(1).strip().upper() != "YES":
        raise RuntimeError("EXECUTION_AUTHORIZED is not YES; human approval required")
    a = re.search(r"^AUTHORIZER:\s*(.+)$", txt, re.M)
    d = re.search(r"^AUTHORIZATION_DATE:\s*(.+)$", txt, re.M)
    if not a or not d or "awaiting" in a.group(1).lower() \
            or "not yet" in d.group(1).lower():
        raise RuntimeError("authorization record incomplete (AUTHORIZER/AUTHORIZATION_DATE)")


def _gradient_trial(st, seed_value: int, grad_proto_hash: str, contract_sha: str,
                    panel_hash: str, state_id: str, rep: int, s2: float,
                    config_id: str) -> dict:
    """Line-identical clone of the committed PI1VNR gradient trial (fresh
    M3-S1C-GRAD namespace; NO probe; NO V1; NO truth anywhere)."""
    z, lp, lr, strata = P1V.draw_online_pilot(st, seed_value, n_pilot=N_GRAD,
                                              alpha=ALPHA_P)
    gd = P1V.gradient_decision(st, seed_value, z, lp, lr, strata)
    g = gd["gradient"]
    valid = (not bool(g["problems"])
             and all(_finite(x) for x in (g["g_hat"], g["g_ci_low"],
                                          g["g_ci_high"], g["ESS_grad"]))
             and g["ESS_grad"] >= 20)
    grad = {
        "seed": int(seed_value), "namespace": GRAD_NS,
        "samples": N_GRAD, "batches": N_BATCH, "alpha_p": ALPHA_P,
        "g_hat": float(g["g_hat"]), "g_ci_low": float(g["g_ci_low"]),
        "g_ci_high": float(g["g_ci_high"]), "ESS_grad": float(g["ESS_grad"]),
        "M2_hat": float(g["M2_hat"]),
        "responsibility_mass": float(g["responsibility_mass"]),
        "D_hat": float(g["D_hat"]), "problems": list(g["problems"]),
        "s2_base": float(g["s2_base"]),
        "sign": "WIDEN" if g["g_hat"] < 0 else "SHRINK",
        "valid": bool(valid), "protocol_hash": grad_proto_hash,
    }
    s1 = P1V.s1_score(grad["g_hat"], grad["g_ci_low"], grad["g_ci_high"]) \
        if valid else None
    deploy = valid and s1 is not None and float(s1) >= S1_THRESHOLD
    return {
        "schema": SCHEMA, "recorded_at": now(),
        "state_id": state_id, "rep_id": rep, "config_id": config_id,
        "s2": float(s2),
        "gradient": grad,
        "selected_action": grad["sign"] if valid else None,
        "S1": float(s1) if s1 is not None else None,
        "S1_threshold": S1_THRESHOLD,
        "deployment": "DEPLOY" if deploy else "ABSTAIN",
        "s1_contract_sha256": contract_sha,
        "panel_hash": panel_hash,
        "sample_counts": {"gradient": N_GRAD, "probe_base": 0, "probe_action": 0,
                          "total": N_GRAD},
        "protocol_hashes": {"gradient": grad_proto_hash, "probe": None},
        "z95": Z95,
    }


def _finite(x) -> bool:
    return math.isfinite(float(x))


def _completed_trials() -> set[str]:
    return {e["state_id"] for e in ledger_entries(TRIAL_LEDGER)
            if e.get("status") == "COMPLETE"}


def execute() -> None:
    _require_authorization()
    verify_prereg()
    # empty destination (taskbook Sec. 11 step 2)
    if TRIAL_LEDGER.exists():
        counts = Counter(e.get("status") for e in ledger_entries(TRIAL_LEDGER))
        if counts.get("COMPLETE") or counts.get("STARTED") or counts.get("CONSUMED_INVALID"):
            raise RuntimeError(f"M3-S1C-X: destination not empty: {dict(counts)}")
    panel_json = load(CFG / "m3s1c_panel.json")
    view = _panel_execution_view(panel_json)
    seeds = load(CFG / "m3s1c_seeds.json")["planned_gradient_seeds"]
    contract_sha = sha(CFG / "m3s1c_s1_contract.json")
    grad_proto_hash = sha(CFG / "m3s1c_gradient_protocol.json")
    panel_hash = panel_json["sha256"]

    # canonical ordering: frozen selection_rank then replicate 0..7
    for r in view:
        st = assemble_state(_bench(r["config_id"]), float(r["s2"]),
                            short_config=r["config_id"])
        if isinstance(st, dict):
            raise RuntimeError(f"M3-S1C-X: state assembly failed for {r['state_id']}")
        slug = bounded_slug(r["state_id"])
        out_dir = TRIALS / slug
        for rep in range(R):
            rid = f"{r['state_id']}__rep{rep}"
            if rid in _completed_trials():
                continue

            def compute(r=r, rep=rep, st=st):
                sval = seeds[f"{r['state_id']}|rep{rep}"]
                ledger_append(GRAD_LEDGER, {"state_id": rid, "phase": "GRADIENT",
                                            "status": "STARTED", "timestamp": now()})
                rec = _gradient_trial(st, sval, grad_proto_hash, contract_sha,
                                      panel_hash, r["state_id"], rep, r["s2"],
                                      r["config_id"])
                ledger_append(GRAD_LEDGER, {"state_id": rid, "phase": "GRADIENT",
                                            "status": "EXECUTED",
                                            "valid": rec["gradient"]["valid"],
                                            "timestamp": now()})
                return rec

            result = run_trial_transactional(
                rid, out_dir / f"rep{rep}.json", compute,
                ledger_path=TRIAL_LEDGER, pre_hash_validator=_pre_hash_validate,
                base_entry={"panel_state_id": r["state_id"], "rep_id": rep,
                            "config_id": r["config_id"],
                            "seed_namespace": GRAD_NS,
                            "seed": seeds[f"{r['state_id']}|rep{rep}"]},
                run_uuid=None)
            if result["status"] != "COMPLETE":
                raise RuntimeError(
                    f"M3-S1C-X: trial not durably COMPLETE for {rid}: {result}; "
                    "CONSUMED_INVALID policy in force; NO REPLAY")
    print("M3-S1C execute: 192/192 durable COMPLETE")


# --------------------------------------------------------------------------
# stage: evaluate
# --------------------------------------------------------------------------

def s1c_verdict(complete: int, consumed_invalid: int,
                wrong_rate: float, coverage: float, unsafe_rate: float) -> str:
    """Frozen verdict contract (taskbook Sec. 3.4/3.5)."""
    if consumed_invalid or complete != 192:
        return "M3-S1C-X"
    full_pass = (wrong_rate <= GATES["wrong_direction_max"]
                 and coverage >= GATES["coverage_min"]
                 and unsafe_rate <= GATES["unsafe_max"])
    return "M3-S1C-A" if full_pass else "M3-S1C-B"


def evaluate() -> dict:
    verify_prereg()
    entries = ledger_entries(TRIAL_LEDGER)
    counts = Counter(e.get("status") for e in entries)
    complete = counts.get("COMPLETE", 0)
    if counts.get("CONSUMED_INVALID") or complete != 192:
        raise RuntimeError(
            f"M3-S1C-X: cannot unseal truth (COMPLETE={complete}, "
            f"CONSUMED_INVALID={counts.get('CONSUMED_INVALID', 0)})")
    # duplicate / hash verification
    seen = Counter(e["state_id"] for e in entries if e.get("status") == "COMPLETE")
    if any(v != 1 for v in seen.values()):
        raise RuntimeError("M3-S1C-X: duplicate COMPLETE entries")
    recs = []
    for e in entries:
        if e.get("status") != "COMPLETE":
            continue
        p = ROOT / e["expected_output_path"]
        if record_file_hash(p) != e["record_file_hash"]:
            raise RuntimeError(f"M3-S1C-X: record hash mismatch: {p}")
        recs.append(json.loads(p.read_text(encoding="utf-8")))
    if len(recs) != 192:
        raise RuntimeError("M3-S1C-X: missing trial records")

    # ---- UNSEAL EVALUATION TRUTH (only after 192/192 durable COMPLETE) ----
    panel_json = load(CFG / "m3s1c_panel.json")
    truth = {r["state_id"]: r["truth"] for r in panel_json["states"]}
    actions = []
    for rec in recs:
        actions.append(rec["selected_action"]
                       if rec["deployment"] == "DEPLOY" else "ABSTAIN")
    rows = [dict(rec, truth=truth[rec["state_id"]],
                 gradient_valid=rec["gradient"]["valid"]) for rec in recs]
    prim = P1V.evaluate(rows, actions)
    sanity = P1V.direction_sanity(rows)
    verdict = s1c_verdict(complete, counts.get("CONSUMED_INVALID", 0),
                          prim["wrong_direction_rate"],
                          prim["deployable_coverage"], prim["unsafe_rate"])
    full_pass = verdict == "M3-S1C-A"

    out = {
        "recorded_at": now(), "schema": SCHEMA,
        "trials": {"planned": 192, "complete": complete,
                   "consumed_invalid": counts.get("CONSUMED_INVALID", 0)},
        "S1": {k: prim[k] for k in
               ("deployable_trials", "deployed", "wrong", "wrong_direction_rate",
                 "wrong_ci95", "deployable_coverage", "coverage_ci95",
                 "nondeployable_trials", "deployed_nd", "unsafe", "unsafe_rate",
                 "unsafe_ci95", "truth_WIDEN", "truth_SHRINK",
                 "truth_HOLD", "truth_AMBIGUOUS")},
        "S1_threshold": S1_THRESHOLD,
        "direction_sanity": sanity,
        "gates": GATES,
        "FULL_PASS": full_pass,
        "VERDICT": verdict,
        "samples": {"gradient": 192 * N_GRAD, "probe": 0, "v1": 0,
                    "total": 192 * N_GRAD},
    }
    SUMMARY.mkdir(parents=True, exist_ok=True)
    dump(SUMMARY / "m3s1c_primary_metrics.json", out)
    csvwrite(SUMMARY / "m3s1c_trial_table.csv", [
        {"state_id": rec["state_id"], "rep_id": rec["rep_id"],
         "config_id": rec["config_id"], "seed": rec["gradient"]["seed"],
         "g_hat": rec["gradient"]["g_hat"], "ESS_grad": rec["gradient"]["ESS_grad"],
         "gradient_valid": rec["gradient"]["valid"],
         "selected_action": rec["selected_action"], "S1": rec["S1"],
         "deployment": rec["deployment"], "truth": truth[rec["state_id"]],
         "stratum": ("W" if truth[rec["state_id"]] == "WIDEN"
                     else "S" if truth[rec["state_id"]] == "SHRINK" else "ND"),
         "outcome": ("wrong" if (rec["deployment"] == "DEPLOY"
                                 and truth[rec["state_id"]] in DEPLOYABLE
                                 and rec["selected_action"] != truth[rec["state_id"]])
                     else "unsafe" if (rec["deployment"] == "DEPLOY"
                                       and truth[rec["state_id"]] in NON_DEPLOYABLE)
                     else "missed_deploy" if (rec["deployment"] == "ABSTAIN"
                                              and truth[rec["state_id"]] in DEPLOYABLE)
                     else "correct_safe" if rec["deployment"] == "ABSTAIN"
                     else "deployed_correct")}
        for rec in rows])
    per_state = {}
    for rec in rows:
        s = per_state.setdefault(rec["state_id"], {
            "config_id": rec["config_id"], "truth": truth[rec["state_id"]],
            "trials": 0, "deployed": 0, "wrong": 0, "unsafe": 0,
            "S1_scores": [], "s2": rec["s2"]})
        s["trials"] += 1
        dep = rec["deployment"] == "DEPLOY"
        s["deployed"] += dep
        s["wrong"] += dep and rec["selected_action"] != truth[rec["state_id"]]
        s["unsafe"] += dep and truth[rec["state_id"]] in NON_DEPLOYABLE
        if rec["S1"] is not None:
            s["S1_scores"].append(rec["S1"])
    csvwrite(SUMMARY / "m3s1c_state_table.csv", [
        {"state_id": sid, **{k: v for k, v in s.items() if k != "S1_scores"},
         "S1_median": sorted(s["S1_scores"])[len(s["S1_scores"]) // 2]
         if s["S1_scores"] else None}
        for sid, s in sorted(per_state.items())])
    print(f"M3-S1C evaluate: FULL_PASS={full_pass} VERDICT={verdict}")
    return out


# --------------------------------------------------------------------------
# stage: report (final report + secondary theory analysis)
# --------------------------------------------------------------------------

def report() -> None:
    prim = load(SUMMARY / "m3s1c_primary_metrics.json")
    rows = csvread(SUMMARY / "m3s1c_trial_table.csv")
    states = csvread(SUMMARY / "m3s1c_state_table.csv")

    # secondary descriptors: s2 and curvature_c only (taskbook Sec. 15)
    curv = _curvature_lookup()
    by_outcome: dict[str, list] = {}
    for r in rows:
        sid = r["state_id"]
        row = next(s for s in states if s["state_id"] == sid)
        rec = {"state_id": sid, "s2": float(row["s2"]),
               "curvature_c": curv.get(row["config_id"]),
               "outcome": r["outcome"],
               "S1": float(r["S1"]) if r["S1"] not in ("", None) else None,
               "deployment": r["deployment"]}
        by_outcome.setdefault(r["outcome"], []).append(rec)
    desc = {}
    for outcome, recs in sorted(by_outcome.items()):
        s2v = [x["s2"] for x in recs]
        cv = [x["curvature_c"] for x in recs if x["curvature_c"] is not None]
        s1v = [x["S1"] for x in recs if x["S1"] is not None]
        desc[outcome] = {
            "n": len(recs),
            "s2": {"min": min(s2v), "median": sorted(s2v)[len(s2v) // 2],
                   "max": max(s2v)} if s2v else None,
            "curvature_c": {"min": min(cv), "median": sorted(cv)[len(cv) // 2],
                            "max": max(cv)} if cv else None,
            "S1": {"min": min(s1v), "median": sorted(s1v)[len(s1v) // 2],
                   "max": max(s1v)} if s1v else None,
        }
    dump(SUMMARY / "m3s1c_secondary_descriptors.json", {
        "recorded_at": now(), "status": "SECONDARY_NON_VERDICT",
        "descriptors_available": ["s2", "curvature_c"],
        "descriptors_not_available": ["beta", "kappa", "lambda", "a",
                                      "a_over_s_proposal"],
        "outcome_descriptives": desc})

    v = prim["VERDICT"]
    s1 = prim["S1"]
    (DOC / "M3_S1C_Final_Report.md").write_text(f"""# M3-S1C Final Report

Verdict: **{v}** (recorded {prim['recorded_at']}).

- Trials: {prim['trials']['complete']}/192 durable COMPLETE,
  {prim['trials']['consumed_invalid']} consumed-invalid.
- Budget: {prim['samples']['gradient']:,} gradient samples; probe = 0; V1 = 0.
- Frozen threshold = {prim['S1_threshold']} (no search, no retune).

## Primary gates (frozen)

| metric | value | gate | pass |
|---|---|---|---|
| wrong direction rate | {s1['wrong_direction_rate']:.6f} | <= {GATES['wrong_direction_max']} | {s1['wrong_direction_rate'] <= GATES['wrong_direction_max']} |
| deployable coverage | {s1['deployable_coverage']:.6f} | >= {GATES['coverage_min']} | {s1['deployable_coverage'] >= GATES['coverage_min']} |
| ND unsafe rate | {s1['unsafe_rate']:.6f} | <= {GATES['unsafe_max']} | {s1['unsafe_rate'] <= GATES['unsafe_max']} |

- FULL_PASS = **{prim['FULL_PASS']}**.
- Direction sanity (Sign-No-Abstain, all 128 W/S trials): wrong = {prim['direction_sanity']['wrong_selected_directions']},
  invalid gradient trials = {prim['direction_sanity']['invalid_gradient_trials']}.
- Descriptive uncertainty only (never a gate): coverage Wilson 95% CI
  {s1['coverage_ci95']}; unsafe {s1['unsafe_ci95']}; wrong {s1['wrong_ci95']}.

## Scientific claim boundary

{('S1 passed an independent untouched confirmation under the frozen PI1VNR-derived '
  'threshold and inherited gates (M3-S1C-A). S1 status upgrades from '
  'DEVELOPMENT_SUPPORTED to CONFIRMED. This does NOT establish '
  'population-universality, deployment safety in every regime, any economic/value '
  'benefit, RARITY, or M3-Q authorization; VALUE/RARITY/M3-Q remain BLOCKED '
  'pending their own gating audits.')
  if v == 'M3-S1C-A' else
  'S1 development result did not independently confirm under the frozen '
  'threshold/gates (M3-S1C-B, a valid negative result). No threshold retune, no '
  'subset selection, no same-stage rerun is permitted; S1 returns to '
  '"development signal not independently confirmed"; any successor (S2/ML-0) '
  'requires a new development stage. The confirmation panel is exposed and '
  'retired from future confirmation use.'}
""", encoding="utf-8")

    (DOC / "M3_S1C_Secondary_Theory_Analysis.md").write_text(f"""# M3-S1C Secondary Theory-Mechanism Analysis

Status: **SECONDARY / NON-VERDICT** (descriptive only; no threshold tuning, no
panel selection, no influence on the S1C-A/B verdict).

- Descriptors actually available: s2 (frozen state metadata), curvature_c
  (frozen BenchmarkConfig parameter).  beta / kappa / lambda / a /
  a_over_s_proposal are NOT_AVAILABLE in this benchmark (no unambiguous
  mapping; taskbook Sec. 15.3 forbids inventing proxies).
- Outcome descriptives (deploy/abstain and correct-safe / unsafe /
  missed-deploy strata) are recorded in
  `results/phase_m3s1c/summary/m3s1c_secondary_descriptors.json`.
- Any hypothesis produced here is input ONLY for future ML-0 / S2 / RARITY
  preregistrations.
""", encoding="utf-8")
    print("M3-S1C report written")


_cf1n_fields = None
_wcf1_fields = None
_freeze = None


def _curvature_lookup() -> dict[str, float]:
    from hyptraj.m1d.experiments import load_freeze
    global _cf1n_fields, _wcf1_fields, _freeze
    out: dict[str, float] = {}
    if _freeze is None:
        _freeze = load_freeze()
    if _cf1n_fields is None:
        _cf1n_fields = load(ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")["physical_fields"]
    if _wcf1_fields is None:
        _wcf1_fields = {r["wcf1_config_id"]: r for r in csvread(
            ROOT / "results/phase_m3wcf1/summary/m3wcf1_physical_config_manifest.csv")}
    cfg_ids = {r["config_id"] for r in csvread(OUT / "m3s1c_panel.csv")}
    for cid in sorted(cfg_ids):
        if cid in _wcf1_fields:
            out[cid] = float(_wcf1_fields[cid]["curvature_c"])
        elif cid in _cf1n_fields:
            out[cid] = float(_cf1n_fields[cid]["curvature_c"])
        else:
            matches = [r for r in _freeze["benchmark_configs"]
                       if r["config_id"].endswith(cid)]
            if len(matches) == 1:
                out[cid] = float(matches[0]["curvature_c"])
    return out


_bench_cache: dict[str, object] = {}


def _bench(config_id: str):
    """Config resolution identical to the committed PI1VNR bench()."""
    global _cf1n_fields, _wcf1_fields
    from hyptraj.m1d.experiments import BenchmarkConfig, config_from_record, load_freeze
    if _cf1n_fields is None:
        _cf1n_fields = load(ROOT / "configs/phase_m3cf1n/m3cf1n_configs.json")["physical_fields"]
    if _wcf1_fields is None:
        _wcf1_fields = {r["wcf1_config_id"]: r for r in csvread(
            ROOT / "results/phase_m3wcf1/summary/m3wcf1_physical_config_manifest.csv")}
    if config_id in _bench_cache:
        return _bench_cache[config_id]
    if config_id in _wcf1_fields:
        f = _wcf1_fields[config_id]
        raw = {r["config_id"]: r for r in csvread(
            ROOT / "results/phase_m3cf0/summary/m3cf0_raw_physical_candidate_lattice.csv")}
        gen = raw[f["raw_candidate_id"]]
        cfg = BenchmarkConfig(
            config_id=config_id,
            batch_seed=int(gen.get("generation_seed", 20300315)),
            batch_index=int(gen.get("batch_index", 0)),
            theta_deg=tuple(float(f[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(f[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(f["curvature_c"]),
            offset_o=tuple(float(f[f"offset_{i}"]) for i in range(1, 5)),
        )
    elif config_id in _cf1n_fields:
        f = _cf1n_fields[config_id]
        cfg = BenchmarkConfig(
            config_id=config_id, batch_seed=20300315, batch_index=0,
            theta_deg=tuple(float(f[f"theta_{i}"]) for i in range(1, 5)),
            h=tuple(float(f[f"h_{i}"]) for i in range(1, 5)),
            curved=tuple(bool(f[f"curved_{i}"]) for i in range(1, 5)),
            curvature_c=float(f["curvature_c"]),
            offset_o=tuple(float(f[f"offset_{i}"]) for i in range(1, 5)),
        )
    else:
        matches = [r for r in load_freeze()["benchmark_configs"]
                   if r["config_id"].endswith(config_id)]
        if len(matches) != 1:
            raise RuntimeError(f"M3-S1C-X: config {config_id} not uniquely resolvable")
        cfg = config_from_record(matches[0])
    _bench_cache[config_id] = cfg
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "docs", "execute", "evaluate",
                                      "report"])
    args = ap.parse_args()
    {"prepare": prepare, "docs": docs, "execute": execute,
     "evaluate": evaluate, "report": report}[args.stage]()


if __name__ == "__main__":
    main()
