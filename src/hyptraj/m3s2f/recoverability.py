"""M3-S2F batch-feature recoverability audit (taskbook Sec. 3/15).

Determines whether the gradient-stability feature family (A0-A5:
batch sign agreement, robust centers/dispersion, concentration, LOBO
stability, shape) is recoverable from the exposed Tier-A trial records
WITHOUT any simulator call.

The frozen gradient estimator computes its uncertainty from a stratified
bootstrap over per-sample contribution vectors; per-batch / per-replicate
gradient values were never persisted.  Reconstruction would require
replaying the sampler (a simulator call), which the taskbook classifies as
INCOMPATIBLE.  This module performs the audit honestly and never imputes,
proxies, or replays.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Field families required by taskbook Sec. 3.2 for the stability family.
# Each entry: (family, required record-field patterns, description).
REQUIRED_FAMILIES = [
    ("per_batch_gradient", ["gradient.batch_g", "gradient.batch_g_hat",
                            "gradient.batch_gradients"],
     "per-batch gradient estimates g_1..g_B"),
    ("per_batch_numerator_denominator",
     ["gradient.batch_num", "gradient.batch_den",
      "gradient.batch_num_den"], "per-batch numerator/denominator pairs"),
    ("batch_signs", ["gradient.batch_signs"],
     "per-batch action signs"),
    ("batch_ess", ["gradient.batch_ess"], "per-batch ESS"),
    ("batch_event_counts", ["gradient.batch_event_counts",
                            "gradient.batch_events"],
     "per-batch event counts"),
    ("batch_contributions", ["gradient.batch_contributions",
                             "gradient.a_vec", "gradient.contributions"],
     "per-batch contribution statistics"),
    ("batch_identifiers", ["gradient.batch_ids", "gradient.crn_batch_ids"],
     "paired CRN batch identifiers"),
    ("bootstrap_replicates", ["gradient.bootstrap_g",
                              "gradient.bootstrap_replicate_g"],
     "per-bootstrap-replicate gradient values"),
    ("sample_contributions", ["gradient.a_vec_samples",
                              "gradient.per_sample_contributions"],
     "raw or sufficient per-sample statistics to reconstruct batch g"),
]

FAMILIES = [f for f, _, _ in REQUIRED_FAMILIES]

# Classification (taskbook Sec. 3.3):
#   FULL                all 384 trials persist every required family
#   PARTIAL-COMPATIBLE  missing families are label/panel-independent and a
#                       unified reduced family is computable on BOTH panels
#                       without imputation or replay
#   INCOMPATIBLE        any required family needs simulator replay,
#                       panel-specific artifacts, or truth/reference data
CLASSIFICATION = ("FULL", "PARTIAL-COMPATIBLE", "INCOMPATIBLE")


def _has_any(rec: dict, patterns: list[str]) -> bool:
    """True iff the record carries any field matching the patterns
    (dot-path check on the actual nested schema)."""
    def get(path: str) -> bool:
        cur = rec
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
        return True
    return any(get(p) for p in patterns)


def audit_trial_record(rec: dict) -> dict:
    """Per-trial recoverability bitset (pure function, no simulator)."""
    present = {fam: _has_any(rec, pats)
               for fam, pats, _ in REQUIRED_FAMILIES}
    g = rec.get("gradient", {})
    return {
        "families": present,
        "missing": [f for f, ok in present.items() if not ok],
        "n_persisted": sum(present.values()),
        # the only persisted uncertainty summary is the 2-number CI
        "ci_only": all(k in g for k in ("g_ci_low", "g_ci_high")),
        "batches_constant_only": isinstance(g.get("batches"), int),
    }


def classify(matrix: list[dict]) -> str:
    """Corpus-level classification over the per-trial audit rows."""
    if not matrix:
        raise RuntimeError("S2F-X: empty recoverability matrix")
    n_persisted = {r["n_persisted"] for r in matrix}
    # No trial carries any required family, or coverage is heterogeneous in
    # a way that would need replay/imputation -> INCOMPATIBLE.
    if all(r["n_persisted"] == 0 for r in matrix):
        return "INCOMPATIBLE"
    if all(r["n_persisted"] == len(FAMILIES) for r in matrix):
        return "FULL"
    # Partial case: only label/panel-independent, uniformly-present families
    # count.  Families present on one panel only are never eligible.
    uniformly = [f for f in FAMILIES
                 if all(r["families"][f] for r in matrix)]
    if uniformly and len(uniformly) == len(FAMILIES):
        return "FULL"
    return "INCOMPATIBLE"


def audit_corpus(trial_paths: list[Path]) -> dict:
    """Scan every exposed canonical trial record (deterministic order)."""
    matrix, per_panel = [], {}
    for p in sorted(trial_paths):
        rec = json.loads(p.read_text(encoding="utf-8"))
        a = audit_trial_record(rec)
        panel = "pi1vnr" if "phase_m3pi1vnr" in str(p) else "s1c"
        per_panel.setdefault(panel, []).append(a["n_persisted"])
        matrix.append({"path": str(p), "panel": panel,
                       "state_id": rec["state_id"], "rep": rec["rep_id"],
                       **{f: int(a["families"][f]) for f in FAMILIES},
                       "n_persisted": a["n_persisted"],
                       "ci_only": int(a["ci_only"]),
                       "batches_constant_only": int(a["batches_constant_only"])})
    classification = classify(matrix)
    return {"matrix": matrix, "classification": classification,
            "n_trials": len(matrix),
            "per_panel_persisted": {k: {"trials": len(v), "any_nonzero": any(v)}
                                    for k, v in per_panel.items()}}
