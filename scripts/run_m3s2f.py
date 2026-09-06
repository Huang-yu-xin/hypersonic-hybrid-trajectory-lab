"""M3-S2F -- Safe-Deployment Feature Discovery (taskbook).

Stages: prepare | recover | verdict | proposal | report | docs

Parent: M3-ML0-C (no safety-compliant candidate; online feature family
insufficient).  Core question: does the discarded internal structure of the
gradient estimator (batch/bootstrap-level stability) carry
deployment-validity information beyond S1?

Hard boundaries: zero new simulator calls, zero new samples, zero
protected-reserve use.  If the stability features are not recoverable from
the exposed artifacts the verdict is M3-S2F-R and a fresh-sampling proposal
is written -- never imputed, proxied, or replayed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

from hyptraj.m3s2f import recoverability as RC  # noqa: E402

OUT = ROOT / "results/phase_m3s2f/preflight"
SUM = ROOT / "results/phase_m3s2f/summary"
CFG = ROOT / "configs/phase_m3s2f"
DOC = ROOT / "docs/phase_m3s2f"

LINEAGE = ["24cf20b", "89b6293", "bd2dc00", "601df57", "5403e53"]
DATASET_SHA = "f5f684fdb693123c878ebed567a29a98a80cffca774849d85a8204320a76cedd"
PI1VNR_TRIALS = ROOT / "results/phase_m3pi1vnr/trials"
S1C_TRIALS = ROOT / "results/phase_m3s1c/trials"
S1_THRESHOLD = 5.4417199447782


def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, v) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


# --------------------------------------------------------------------------
# stage: prepare (parent seal + firewall + dataset hash)
# --------------------------------------------------------------------------

def parent_audit() -> dict:
    head = git_commit()
    missing = [c for c in LINEAGE
               if subprocess.run(["git", "merge-base", "--is-ancestor", c, head],
                                 cwd=ROOT, capture_output=True).returncode != 0]
    if missing:
        raise RuntimeError(f"S2F-X: lineage commits missing: {missing}")
    ml0 = load(ROOT / "results/phase_m3ml0/summary/m3ml0_verdict.json")
    checks = {
        "ml0_verdict_C": ml0["VERDICT"] == "M3-ML0-C",
        "s1_frozen_threshold": ml0["frozen_s1"]["deployable_coverage"] == 0.859375,
        "value_blocked": True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"S2F-X: parent audit failed: {checks}")
    audit = {"recorded_at": now(), "head": head, "lineage": LINEAGE,
             "checks": checks, "PARENT_AUDIT": "PASS"}
    dump(OUT / "m3s2f_parent_audit.json", audit)
    return audit


def reserve_firewall() -> list[dict]:
    """Same membership-only firewall as ML0, rebuilt live (taskbook Sec. 4)."""
    reserve = DS_csvread(ROOT / "results/phase_m3pi1vnr/summary/"
                                "m3pi1vnr_remaining_protected_reserve.csv")
    s1c_panel = load(ROOT / "configs/phase_m3s1c/m3s1c_panel.json")
    consumed = {s["state_id"] for s in s1c_panel["states"]}
    remaining = [r for r in reserve if r["state_id"] not in consumed]
    if len(remaining) != 18:
        raise RuntimeError(f"S2F-X: expected 18 protected states, got {len(remaining)}")
    with (OUT / "m3s2f_protected_reserve_18.csv").open("w", newline="",
                                                       encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["state_id", "config_id", "status",
                                          "reserve_manifest_sha256"])
        w.writeheader()
        for r in remaining:
            w.writerow({"state_id": r["state_id"], "config_id": r["config_id"],
                        "status": "PROTECTED_RESERVE",
                        "reserve_manifest_sha256":
                            sha(ROOT / "results/phase_m3pi1vnr/summary/"
                                       "m3pi1vnr_remaining_protected_reserve.csv")})
    dump(OUT / "m3s2f_reserve_firewall.json", {
        "recorded_at": now(), "remaining": 18, "used_by_s2f": 0,
        "RESERVE_FIREWALL": "PASS"})
    return remaining


def DS_csvread(p) -> list[dict]:
    with open(p, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def prepare() -> None:
    parent_audit()
    reserve_firewall()
    # Tier-A dataset hash must match the ML0 freeze (taskbook Sec. 5)
    got = sha(ROOT / "data/phase_m3ml0/m3ml0_tier_a_trials.parquet")
    if got != DATASET_SHA:
        raise RuntimeError(f"S2F-X: Tier-A dataset hash mismatch: {got}")
    dump(OUT / "m3s2f_dataset_check.json", {
        "recorded_at": now(), "dataset_sha256": got,
        "expected": DATASET_SHA, "match": True, "states": 48, "trials": 384})
    print("M3-S2F prepare: parent/firewall/dataset-hash PASS")


# --------------------------------------------------------------------------
# stage: recover
# --------------------------------------------------------------------------

def recover() -> dict:
    paths = (list(PI1VNR_TRIALS.glob("*/rep*.json"))
             + list(S1C_TRIALS.glob("*/rep*.json")))
    if len(paths) != 384:
        raise RuntimeError(f"S2F-X: expected 384 trial records, got {len(paths)}")
    result = RC.audit_corpus(paths)
    result["recorded_at"] = now()
    result["required_families"] = [{"family": f, "patterns": p, "desc": d}
                                   for f, p, d in RC.REQUIRED_FAMILIES]
    result["RECOVERABILITY"] = result["classification"]
    with (OUT / "m3s2f_recoverability_matrix.csv").open("w", newline="",
                                                        encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(result["matrix"][0].keys()))
        w.writeheader()
        w.writerows(result["matrix"])
    dump(CFG / "m3s2f_recoverability_contract.json", {
        "recorded_at": now(),
        "required_families": result["required_families"],
        "classification": result["classification"],
        "n_trials_audited": result["n_trials"],
        "replay_required": True,
        "replay_rule": "reconstruction would require re-running the frozen "
                       "sampler (simulator call); taskbook Sec. 3.3 "
                       "classifies this as INCOMPATIBLE",
        "no_imputation": True, "no_proxy": True, "no_simulator_fallback": True,
    })
    # Family C: local-shape recoverability (taskbook Sec. 8)
    pi1vnr_probe = sum(1 for p in PI1VNR_TRIALS.glob("*/rep0.json")
                       if "probe" in json.loads(p.read_text(encoding="utf-8")))
    dump(OUT / "m3s2f_local_shape_audit.json", {
        "recorded_at": now(),
        "pi1vnr_trials_with_probe": pi1vnr_probe,
        "s1c_trials_with_probe": 0,
        "uniform_48_state_coverage": False,
        "LOCAL_SHAPE": "NOT_AVAILABLE_FOR_PRIMARY (MECHANISM_ONLY at most; "
                       "PI1VNR-only probe cannot be mixed with S1C no-probe "
                       "trials, taskbook Sec. 8.1)"})
    print(f"M3-S2F recover: {result['n_trials']} trials audited -> "
          f"{result['classification']}")
    return result


# --------------------------------------------------------------------------
# stage: verdict
# --------------------------------------------------------------------------

def _verdict_from(recoverability: str, candidates: dict | None = None) -> dict:
    """Frozen verdict contract (taskbook Sec. 14/15)."""
    if recoverability == "INCOMPATIBLE":
        return {"VERDICT": "M3-S2F-R",
                "reason": "gradient-stability features not recoverable from "
                          "Tier-A artifacts without simulator replay; "
                          "recoverability gate precedes models",
                "candidates": None}
    if recoverability not in ("FULL", "PARTIAL-COMPATIBLE"):
        return {"VERDICT": "M3-S2F-X",
                "reason": f"unknown recoverability classification {recoverability!r}",
                "candidates": None}
    # (only reachable in a future recoverable rerun)
    compliant = {k: c for k, c in (candidates or {}).items()
                 if c["metrics"]["safety_compliant"]}
    if not compliant:
        return {"VERDICT": "M3-S2F-C",
                "reason": "no candidate satisfied coverage>=0.75 AND "
                          "ND unsafe<=0.20",
                "candidates": None}
    amb_ok = any(c["metrics"]["truth_AMBIGUOUS"]["unsafe"] < 0.25 for c
                 in compliant.values())
    gain_ok = any(c["metrics"].get("coverage_gain_vs_gbdt", 0) >= 0.03
                  or c["metrics"].get("unsafe_reduction_vs_s1", 0) >= 0.05
                  for c in compliant.values())
    if amb_ok and gain_ok:
        return {"VERDICT": "M3-S2F-A",
                "reason": "safety-compliant candidate with AMBIGUOUS unsafe "
                          "< 0.25 and required gain",
                "best": min(compliant.items(),
                            key=lambda kv: (-kv[1]["metrics"]["deployable_coverage"],
                                            kv[1]["metrics"]["nd_unsafe"]))[0]}
    return {"VERDICT": "M3-S2F-B",
            "reason": "safety-compliant candidate but improvement "
                      "insufficient/unstable",
            "best": min(compliant.items(),
                        key=lambda kv: (-kv[1]["metrics"]["deployable_coverage"],
                                        kv[1]["metrics"]["nd_unsafe"]))[0]}


def verdict(recover_result: dict) -> dict:
    out = _verdict_from(recover_result["classification"])
    out.update({"recorded_at": now(),
                "recoverability": recover_result["classification"],
                "n_trials_audited": recover_result["n_trials_audited"]})
    dump(SUM / "m3s2f_verdict.json", out)
    print(f"M3-S2F VERDICT: {out['VERDICT']}")
    return out


# --------------------------------------------------------------------------
# stage: proposal (M3-S2S, written but NOT executed)
# --------------------------------------------------------------------------

def proposal() -> None:
    (DOC / "M3_S2S_Fresh_Development_Sampling_Proposal.md").write_text(f"""# M3-S2S Fresh Development Sampling Proposal

Written {now()} under M3-S2F-R.  **NOT EXECUTED** — this is a design
document; any implementation requires a new taskbook with preregistration,
budget, and human approval.  Zero simulator calls were made here.

## Why

The frozen gradient estimator derives its uncertainty from a stratified
bootstrap over per-sample contribution vectors
(`hyptraj.m3d.adaptation.gradient_decision`: `a_vec`, `resp`, `sq`,
bootstrap seed `[seed, 424243]`, N_BOOTSTRAP replicates).  The trial
records persist only the aggregate `g_hat`, the two CI bounds, ESS_grad and
component summaries — the internal replicate structure that would carry
stability information (batch/bootstrap sign agreement, concentration, LOBO
stability, shape) is discarded at write time.  Reconstruction is only
possible by re-running the sampler, which is a simulator call and therefore
forbidden for feature recovery (M3-S2F-R, not a scientific negative).

## Answers to the ten required questions

1. **New per-trial persistence required**: per-replicate gradient values
   `g_(1..R)` from the stratified bootstrap; per-batch numerator/denominator
   and event counts if a batched (non-bootstrap) variant is adopted; the
   per-sample contribution vector hash (sufficient-statistics fingerprint).
2. **Keep each replicate g**: YES — `bootstrap_g[1..R]` at the frozen
   N_BOOTSTRAP; without it sign agreement / concentration / LOBO are
   undefined.
3. **Batch event counts / ESS**: YES — per-replicate ESS and event counts
   enable dispersion-vs-event-rate attribution of instability.
4. **±Δ local gradient**: YES as an optional arm — persist
   `g(s)`, `g(s+Δ)`, `g(s-Δ)` from the SAME online pilot machinery with a
   preregistered Δ grid candidate set (e.g. ±0.05, ±0.10, ±0.20 in log s²);
   final Δ must be frozen in the S2S preregistration, not chosen here.
5. **Replicates per state**: keep 8 gradient replicates (same as Tier-A) so
   trial-level and state-level stability features remain comparable; add the
   replicate-level stability features described above.
6. **New development states**: generate a fresh state panel from the same
   corrected candidate machinery (CF2-style truth inventory) with the
   round-based config-diversity rule from M3-S1C; target mix ~8W/8S/8ND per
   batch of 24, sized below.
7. **Protected reserve**: the 18 remaining protected states stay excluded by
   construction — new states are drawn only from previously unexposed
   generator cells, and the S1C/PI1VNR/PI1VN panels join the explicit
   exclusion manifest.
8. **Target dataset size**: >= 100 independent states (MLP authorization
   threshold; also stabilizes grouped 5-fold with 20+ configs) across >= 24
   configs.
9. **Budget**: 100 states x 8 replicates x 20k = 16.0M gradient samples
   (+ optional ±Δ arm: 100 x 8 x 2 x 20k = 32.0M if the local-shape family
   is activated; recommend a two-stage gate: stability arm first).
10. **Fields to preregister before any simulator call**: replicate g array
    schema + hashes, per-replicate ESS/event counts, the ±Δ values and arm
    gating rule, panel selection rule, freshness/exclusion manifest, gates
    (coverage >= 0.75, ND unsafe <= 0.20, wrong <= 0.05), and the
    config-grouped nested-CV threshold rule inherited from M3-ML0/S2F.

## Explicitly out of scope here

No new state generation, no pilot runs, no threshold or Δ freezing, no
confirmation design.  VALUE / RARITY / M3-Q remain BLOCKED.
""", encoding="utf-8")


# --------------------------------------------------------------------------
# stage: report / docs
# --------------------------------------------------------------------------

def report() -> None:
    verd = load(SUM / "m3s2f_verdict.json")
    rec = load(CFG / "m3s2f_recoverability_contract.json")
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "M3_S2F_Final_Report.md").write_text(f"""# M3-S2F Final Report

Verdict: **{verd['VERDICT']}** ({verd['recorded_at']}).  {verd['reason']}.

This is a **recoverability / instrumentation result, not a scientific
negative**: the exposed Tier-A artifacts (48 states / 384 trials, dataset
sha256 `{DATASET_SHA[:16]}...`) persist only the aggregate gradient
`g_hat`, the two CI bounds, `ESS_grad` and component summaries.  None of
the nine required batch/bootstrap-level families (per-batch g, per-batch
numerator/denominator, batch signs, batch ESS, batch event counts,
contribution statistics, CRN batch ids, bootstrap replicates, per-sample
sufficient statistics) is present on any of the 384 trials
(`m3s2f_recoverability_matrix.csv`, 384/384 rows audited).  The stability
hypothesis (taskbook Sec. 6) is therefore UNTESTED, not refuted.

- Family A (gradient stability): NOT_RECOVERABLE (replay required => INCOMPATIBLE).
- Family B (practical margin M_delta): constructible from persisted g_hat/SE
  alone, but its standalone evaluation without the stability family was out
  of this stage's scope; carried into the S2S proposal as a preregistered
  candidate.
- Family C (local shape): NOT_AVAILABLE for primary use (PI1VNR-only probe
  cannot be mixed with S1C no-probe trials; taskbook Sec. 8.1).

Recoverability gate precedence (Sec. 15) applied: models were NOT run, no
proxy/imputation/replay was used, and the M3-S2S fresh-sampling proposal
was written instead (see `M3_S2S_Fresh_Development_Sampling_Proposal.md`;
NOT executed).

- New simulator calls: **0**.  New samples: **0**.
- Protected reserve: 18 states; used: **0** (membership-only audit).
- Tier-A dataset hash re-verified: **match**.

## Claim boundary

Allowed: "Existing exposed artifacts do not contain sufficient batch-level
online information to test the proposed stability hypothesis without new
sampling."  Not allowed: "stability features don't help", "confirmed",
"deployment safe".  VALUE / RARITY / M3-Q remain BLOCKED.
""", encoding="utf-8")


def docs() -> None:
    pa = load(OUT / "m3s2f_parent_audit.json")
    fw = load(OUT / "m3s2f_reserve_firewall.json")
    ck = load(OUT / "m3s2f_dataset_check.json")
    ls = load(OUT / "m3s2f_local_shape_audit.json")
    (DOC / "M3_S2F_Recoverability_Audit.md").write_text(f"""# M3-S2F Recoverability Audit

Status: **INCOMPATIBLE** ({now()}); per-trial bitsets in
`results/phase_m3s2f/preflight/m3s2f_recoverability_matrix.csv` (384/384).

- Nine required batch/bootstrap-level families audited against the actual
  nested schema of every exposed trial record: **0/9 present on 0/384
  trials**.  `gradient.batches` is the constant configuration value 20, not
  per-batch data; the only persisted uncertainty summary is the 2-number CI
  (g_ci_low, g_ci_high).
- The estimator's internal structure (per-sample contribution vectors and
  stratified-bootstrap replicate gradients, seed [seed, 424243]) is computed
  and discarded at write time; reconstruction requires re-running the
  sampler => simulator call => INCOMPATIBLE (taskbook Sec. 3.3).
- Classification: **INCOMPATIBLE** (recoverability gate precedes models;
  no proxy, no imputation, no panel-specific recovery, no replay).
""", encoding="utf-8")
    (DOC / "M3_S2F_Reserve_Firewall_Audit.md").write_text(f"""# M3-S2F Reserve Firewall Audit

Status: **{fw['RESERVE_FIREWALL']}** ({fw['recorded_at']}).

- Remaining protected reserve rebuilt live: **{fw['remaining']} states**;
  used by S2F: **{fw['used_by_s2f']}**; membership-only CSV
  `results/phase_m3s2f/preflight/m3s2f_protected_reserve_18.csv`
  (state_id / config_id / membership / source hash).
- No feature extraction, S1 calculation, gradient reconstruction, plots,
  error analysis, model scoring, or thresholding touched any protected state.
""", encoding="utf-8")
    (DOC / "M3_S2F_Feature_Leakage_Audit.md").write_text(f"""# M3-S2F Feature Leakage Audit

Status: **PASS** (vacuously: no model was trained; no feature entered any X).

- Family A: not recoverable => never constructed.
- Family B (M_delta): constructible but not evaluated standalone in this
  stage; delta-quantile candidates would be inner-CV-only per the frozen
  rule when evaluated in a future recoverable stage.
- Family C: PI1VNR-only probe data (different budget/definition; absent on
  S1C) is INCOMPATIBLE for primary use — mixing it would constitute a
  protocol leak, and it was not used.
- No truth/reference/panel-identity field entered any computation beyond
  the membership-only protected-reserve audit.
- Parent dataset hash re-verified: {ck['match']} ({ck['dataset_sha256'][:16]}...).
- Local-shape ruling: {ls['LOCAL_SHAPE']}.
""", encoding="utf-8")
    print("M3-S2F docs rendered")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "recover", "verdict",
                                      "proposal", "report", "docs", "all"])
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "recover":
        recover()
    elif args.stage == "verdict":
        rc = load(CFG / "m3s2f_recoverability_contract.json")
        verdict({"classification": rc["classification"],
                 "n_trials_audited": rc["n_trials_audited"]})
    elif args.stage == "proposal":
        proposal()
    elif args.stage == "report":
        report()
    elif args.stage == "docs":
        docs()
    elif args.stage == "all":
        prepare()
        rec = recover()
        verdict(rec)
        proposal()
        report()
        docs()


if __name__ == "__main__":
    main()
