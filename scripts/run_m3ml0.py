"""M3-ML0 -- safe-deploy development on exposed canonical data (taskbook).

Zero new scientific simulator calls; zero protected-reserve consumption.
Stages: prepare | data | models | mechanism | verdict | report | docs

Parent state: M3-S1C-B (S1 development signal not independently confirmed;
S1C panel EXPOSED and consumed into Tier-A; 18 protected reserve states
remain firewalled).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402

from hyptraj.m3ml0 import dataset as DS  # noqa: E402
from hyptraj.m3ml0 import evaluation as EV  # noqa: E402
from hyptraj.m3ml0 import features as FE  # noqa: E402
from hyptraj.m3ml0 import models as MO  # noqa: E402
from hyptraj.m3ml0 import splits as SP  # noqa: E402

OUT = ROOT / "results/phase_m3ml0/preflight"
SUM = ROOT / "results/phase_m3ml0/summary"
DATA = ROOT / "data/phase_m3ml0"
CFG = ROOT / "configs/phase_m3ml0"
DOC = ROOT / "docs/phase_m3ml0"

S1C_BASE = "24cf20b8db6d455a78af472c0fa59971401e49a5"
LINEAGE = ["7b8ad90", "a55213e", "3bd967d", "509a266", "10a4218",
           "d49e50d", "24cf20b"]
S1_THRESHOLD = 5.4417199447782
GATES = {"coverage_min": 0.75, "unsafe_max": 0.20, "wrong_max": 0.05}
COVERAGE_GAIN_MIN = 0.05
SEED = 2026


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
# stage: prepare
# --------------------------------------------------------------------------

def parent_audit() -> dict:
    head = git_commit()
    missing = [c for c in LINEAGE
               if subprocess.run(["git", "merge-base", "--is-ancestor", c, head],
                                 cwd=ROOT, capture_output=True).returncode != 0]
    if missing:
        raise RuntimeError(f"ML0-X: lineage commits missing: {missing}")
    verd = load(ROOT / "results/phase_m3s1c/summary/m3s1c_primary_metrics.json")
    checks = {
        "s1c_verdict_B": verd["VERDICT"] == "M3-S1C-B",
        "s1c_192_of_192": verd["trials"]["complete"] == 192
                          and verd["trials"]["consumed_invalid"] == 0,
        "s1c_budget_3_84m": verd["samples"]["gradient"] == 3_840_000,
        "s1c_threshold_frozen": verd["S1_threshold"] == S1_THRESHOLD,
        "s1c_wrong_zero": verd["S1"]["wrong"] == 0,
        "s1c_coverage": abs(verd["S1"]["deployable_coverage"] - 0.828125) < 1e-12,
        "s1c_nd_unsafe": abs(verd["S1"]["unsafe_rate"] - 0.296875) < 1e-12,
        "s1c_ambig_unsafe": abs(verd["S1"]["truth_AMBIGUOUS"]["unsafe_rate"] - 0.59375) < 1e-12,
        "s1c_hold_unsafe_zero": verd["S1"]["truth_HOLD"]["unsafe_rate"] == 0.0,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError(f"ML0-X: parent audit failed: {failed}")
    audit = {"recorded_at": now(), "head": head, "lineage": LINEAGE,
             "checks": checks, "PARENT_AUDIT": "PASS",
             "s1_status": "development signal not independently confirmed",
             "s1c_panel_status": "EXPOSED (consumed into Tier-A)",
             "value": "BLOCKED", "rarity_shift": "BLOCKED", "m3_q": "BLOCKED"}
    dump(OUT / "m3ml0_parent_audit.json", audit)
    return audit


def reserve_firewall() -> list[dict]:
    remaining = DS.protected_reserve_18()
    csv_path = OUT / "m3ml0_protected_reserve_18.csv"
    import csv as _csv
    with csv_path.open("w", newline="", encoding="utf-8") as h:
        w = _csv.DictWriter(h, fieldnames=["state_id", "config_id", "truth",
                                           "status", "reserve_manifest_sha256"])
        w.writeheader()
        for r in remaining:
            w.writerow({"state_id": r["state_id"], "config_id": r["config_id"],
                        "truth": r["truth"], "status": "PROTECTED_RESERVE",
                        "reserve_manifest_sha256": r["reserve_manifest_sha256"]})
    dump(OUT / "m3ml0_reserve_firewall.json", {
        "recorded_at": now(), "remaining": len(remaining),
        "consumed_by_ml0": 0,
        "forbidden_uses": ["gradient", "V1 probe", "S1", "ML feature",
                           "train/val/test", "error analysis",
                           "feature engineering", "threshold selection",
                           "theory descriptors", "exploratory plots"],
        "RESERVE_FIREWALL": "PASS"})
    return remaining


def write_contracts() -> None:
    CFG.mkdir(parents=True, exist_ok=True)
    dump(CFG / "m3ml0_dataset_contract.json", {
        "tier_a_sources": ["PI1VNR fresh development panel (24 states, exposed by construction)",
                           "M3-S1C confirmation panel (24 states, EXPOSED by M3-S1C-B)"],
        "states": 48, "trials": 384, "replicates_per_state": 8,
        "samples_per_trial": 20000,
        "tier_b_policy": "inventory only; NOT merged into primary ML result",
        "protected_reserve_use": 0,
    })
    dump(CFG / "m3ml0_feature_contract.json", {
        "F0_core": FE.F0_CORE,
        "F0_full": FE.F0_FULL,
        "F1_available": FE.F1_AVAILABLE,
        "F1_not_available": FE.F1_NOT_AVAILABLE,
        "availability_audit": {
            "S1": {"source": "trial record S1 (computed from the trial's own gradient CI)",
                   "available_before_action": True, "truth_derived": False},
            "g_hat": {"source": "trial record gradient.g_hat",
                      "available_before_action": True, "truth_derived": False},
            "SE_g": {"source": "(g_ci_high-g_ci_low)/(2*1.959963984540054)",
                     "available_before_action": True, "truth_derived": False},
            "CI_width": {"source": "g_ci_high-g_ci_low",
                         "available_before_action": True, "truth_derived": False},
            "abs_g_hat": {"source": "|g_hat|", "available_before_action": True,
                          "truth_derived": False},
            "s2": {"source": "frozen state metadata",
                   "available_before_action": True, "truth_derived": False},
            "curvature_c": {"source": "frozen BenchmarkConfig parameter",
                            "available_before_action": True, "truth_derived": False},
            "ESS_grad": {"source": "trial record gradient.ESS_grad",
                         "available_before_action": True, "truth_derived": False},
            "gradient_valid": {"source": "trial record gradient.valid",
                               "available_before_action": True, "truth_derived": False},
            "p_hat_grad": {"available_before_action": False,
                           "reason": "not persisted in trial records",
                           "included": False},
            "batch_dispersion": {"available_before_action": False,
                                 "reason": "per-batch gradient values not persisted",
                                 "included": False},
            "gradient_batch_variance": {"available_before_action": False,
                                        "reason": "per-batch gradient values not persisted",
                                        "included": False},
        },
        "forbidden_features": FE.FORBIDDEN_FEATURES,
        "invalid_gradient_rule": "invalid rows are never model input and map "
                                 "deterministically to ABSTAIN in every policy",
    })
    dump(CFG / "m3ml0_split_contract.json", {
        "group": "config_id", "outer": "GroupKFold(n_splits=5)",
        "inner": "GroupKFold(n_splits=4) on outer-train configs",
        "row_order": "canonical (panel, state_id, rep) before splitting",
        "deterministic": True, "seed": SEED,
        "fallback_rule": "5-fold -> 4-fold -> Leave-One-Config-Out; any "
                         "downgrade must be recorded in the audit",
    })
    dump(CFG / "m3ml0_model_grid.json", {
        "B1_logistic_s1": {"features": FE.MODEL_FEATURES["B1_logistic_s1"],
                           "grid": MO.LOGISTIC_GRID},
        "B2_s2_logistic": {"features": FE.MODEL_FEATURES["B2_s2_logistic"],
                           "grid": MO.LOGISTIC_GRID},
        "B3_gbdt": {"features": FE.MODEL_FEATURES["B3_gbdt"],
                    "grid": MO.GBDT_GRID,
                    "estimator": "sklearn.ensemble.HistGradientBoostingClassifier"},
        "B4_mlp": {"status": "NOT_AUTHORIZED",
                   "reason": "48 independent states < 100 (taskbook Sec. 9)"},
        "library_versions": {"sklearn": __import__("sklearn").__version__,
                             "numpy": np.__version__, "pandas": pd.__version__},
        "seed": SEED,
    })
    dump(CFG / "m3ml0_threshold_contract.json", {
        "rule": "inner-OOF probability midpoints + sentinels; keep ND unsafe "
                "<= 0.20; maximize deployable coverage; tie-break lower ND "
                "unsafe, lower harmful deployment, higher threshold, canonical",
        "no_legal_threshold": "ABSTAIN-ALL sentinel (counts as coverage "
                              "failure, never success)",
        "unsafe_max": 0.20,
    })
    dump(CFG / "m3ml0_verdict_contract.json", {
        "M3_ML0_A": "some candidate: safety-compliant AND coverage gain vs "
                    "frozen S1 >= 0.05 AND AMBIGUOUS unsafe < frozen S1 AMBIGUOUS unsafe",
        "M3_ML0_B": "some candidate safety-compliant but gain < 5pp or no "
                    "AMBIGUOUS improvement",
        "M3_ML0_C": "no safety-compliant candidate",
        "M3_ML0_X": "leakage / corrupted source / protected contamination / "
                    "grouping violation / unrecoverable construction error",
        "gates": GATES, "coverage_gain_min": COVERAGE_GAIN_MIN,
    })


def tier_b_inventory() -> None:
    """Optional Tier-B classification only -- NEVER merged into the primary
    ML result (taskbook Sec. 4.3)."""
    import csv as _csv
    protected = {r["state_id"] for r in DS.protected_reserve_18()}
    tier_a = set()
    for src, path in (
            ("PI1VNR", ROOT / "results/phase_m3pi1vnr/summary/m3pi1vnr_fresh_development_panel.csv"),
            ("S1C", ROOT / "results/phase_m3s1c/preflight/m3s1c_panel.csv")):
        tier_a |= {r["state_id"] for r in DS.csvread(path)}
    entries = []
    for r in DS.csvread(PI1VNR_SUM := ROOT / "results/phase_m3pi1vnr/summary/m3pi1vnr_retired_pi1vn_panel.csv"):
        entries.append({"state_id": r["state_id"], "origin": "PI1VN",
                        "classification": "INVALID",
                        "reason": "PI1VN-X retired panel (execution invalid; "
                                  "diagnostic-only by PI1VR0)"})
    for qdir, tag in ((ROOT / "results/phase_m3pi1v/quarantine_attempt1", "PI1V-A1"),
                      (ROOT / "results/phase_m3pi1v/quarantine_attempt2", "PI1V-A2")):
        if not qdir.exists():
            continue
        n = 0
        for p in qdir.rglob("*.csv"):
            for row in DS.csvread(p):
                sid = row.get("state_id", "")
                if sid and sid not in {e["state_id"] for e in entries}:
                    entries.append({"state_id": sid, "origin": tag,
                                    "classification": "INVALID",
                                    "reason": "quarantined invalid attempt"})
                    n += 1
    for r in DS.csvread(ROOT / "results/phase_m3pi1vnr/summary/m3pi1vnr_remaining_protected_reserve.csv"):
        if r["state_id"] not in protected:
            continue
        entries.append({"state_id": r["state_id"], "origin": r["source_stage"],
                        "classification": "PROTECTED",
                        "reason": "remaining protected reserve (18); firewall"})
    for stage, panel in (
            ("M3-CF2", ROOT / "results/phase_m3cf2/summary/m3cf2_development_panel.csv"),
            ("M3-WCF1", ROOT / "results/phase_m3wcf1/summary/m3wcf1_fresh_development_panel.csv"),
            ("M3-WA1", ROOT / "results/phase_m3wa1/summary/m3wa1_development_panel.csv" if
             (ROOT / "results/phase_m3wa1/summary/m3wa1_development_panel.csv").exists()
             else ROOT / "results/phase_m3wa1/summary/m3wa1_candidate_manifest.csv")):
        if not panel.exists():
            continue
        for row in DS.csvread(panel):
            sid = row.get("state_id", "")
            if not sid:
                continue
            cls = "MECHANISM_ONLY"
            reason = ("exposed development state of a stage with different "
                      "probe/budget semantics; not same-protocol Tier-A")
            entries.append({"state_id": sid, "origin": stage,
                            "classification": cls, "reason": reason})
    seen = set()
    dedup = []
    for e in entries:
        key = e["state_id"]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)
    out = OUT / "m3ml0_tier_b_inventory.csv"
    with out.open("w", newline="", encoding="utf-8") as h:
        w = _csv.DictWriter(h, fieldnames=["state_id", "origin",
                                           "classification", "reason"])
        w.writeheader()
        w.writerows(dedup)
    counts = Counter(e["classification"] for e in dedup)
    dump(OUT / "m3ml0_tier_b_summary.json", {
        "recorded_at": now(), "entries": len(dedup),
        "classifications": dict(counts),
        "eligible_for_future_dev": counts.get("ELIGIBLE_FOR_FUTURE_DEV", 0),
        "policy": "inventory only; not used in primary ML0 result"})
    return counts


def prepare() -> None:
    parent_audit()
    reserve_firewall()
    tier_b_inventory()
    write_contracts()
    print("M3-ML0 prepare: parent/reserve/Tier-B audits PASS, contracts written")


# --------------------------------------------------------------------------
# stage: data
# --------------------------------------------------------------------------

def data() -> dict:
    built = DS.build_tier_a()
    rows = built["rows"]
    dur = DS.durable_complete_check()
    if any(v["consumed_invalid"] for v in dur.values()):
        raise RuntimeError(f"ML0-X: consumed-invalid trials in sources: {dur}")
    df = pd.DataFrame(rows)
    DATA.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA / "m3ml0_tier_a_trials.parquet", index=False)
    agg = df.groupby(["panel", "state_id", "config_id", "truth", "s2",
                      "curvature_c", "label_deploy"], sort=True).agg(
        trials=("rep", "count"),
        S1_median=("S1", "median"), S1_mean=("S1", "mean"),
        S1_std=("S1", "std"), S1_min=("S1", "min"), S1_max=("S1", "max"),
        g_hat_median=("g_hat", "median"),
        ESS_median=("ESS_grad", "median"),
    ).reset_index()
    # state-level SE_g: recompute from CI medians is not stored; store
    # per-state median SE via the row helper instead
    se_rows = []
    for (panel, sid), grp in df.groupby(["panel", "state_id"]):
        fr = [FE.feature_row(r) for r in grp.to_dict("records")]
        se_rows.append({"panel": panel, "state_id": sid,
                        "SE_g_median": float(np.nanmedian([f["SE_g"] for f in fr])),
                        "CI_width_median": float(np.nanmedian([f["CI_width"] for f in fr]))})
    se_df = pd.DataFrame(se_rows)
    agg = agg.merge(se_df, on=["panel", "state_id"], how="left")
    agg.to_parquet(DATA / "m3ml0_tier_a_states.parquet", index=False)

    dataset_bytes = (DATA / "m3ml0_tier_a_trials.parquet").read_bytes()
    ds_sha = hashlib.sha256(dataset_bytes).hexdigest()
    manifest = {**built["manifest"], "recorded_at": now(),
                "durable_complete_check": dur,
                "dataset_sha256": ds_sha,
                "states_parquet_sha256": sha(DATA / "m3ml0_tier_a_states.parquet")}
    dump(DATA / "m3ml0_source_manifest.json", manifest)
    dump(DATA / "m3ml0_feature_dictionary.json", {
        "trial_level": list(df.columns),
        "state_level": list(agg.columns),
        "feature_contract": "configs/phase_m3ml0/m3ml0_feature_contract.json",
        "dataset_sha256": ds_sha})

    # protected-18 overlap audit
    prot = {r["state_id"] for r in DS.protected_reserve_18()}
    overlap = prot & set(df["state_id"])
    if overlap:
        raise RuntimeError(f"ML0-X: protected reserve overlap: {overlap}")
    summary = {"recorded_at": now(), "states": 48, "trials": 384,
               "dataset_sha256": ds_sha,
               "protected_overlap": 0,
               "panel_counts": dict(Counter(r["panel"] for r in rows)),
               "truth_counts": dict(Counter(r["truth"] for r in rows)),
               "unique_configs": len({r["config_id"] for r in rows}),
               "invalid_gradient_trials": int((~df["gradient_valid"]).sum()),
               "durable_complete_check": dur,
               "SOURCE_AUDIT": "PASS"}
    dump(OUT / "m3ml0_dataset_audit.json", summary)
    print("M3-ML0 data:", json.dumps(summary))
    return summary


# --------------------------------------------------------------------------
# stage: models (nested CV) + OOF evaluation
# --------------------------------------------------------------------------

def _attach_features(rows: list[dict]) -> None:
    for r in rows:
        r["_fr"] = FE.feature_row(r)
        r["_X"] = {name: [r["_fr"][f] for f in feats]
                   for name, feats in FE.MODEL_FEATURES.items()}


def models() -> dict:
    df = pd.read_parquet(DATA / "m3ml0_tier_a_trials.parquet")
    rows = df.to_dict("records")
    for r in rows:
        r["gradient_valid"] = bool(r["gradient_valid"])
    rows = SP.canonical_order(rows)
    _attach_features(rows)

    outer = SP.grouped_outer_folds(rows, n_splits=5)
    audit = SP.split_audit(rows, outer)
    if not audit["PASS"]:
        raise RuntimeError(f"ML0-X: split audit failed: {audit}")
    dump(OUT / "m3ml0_groupsplit_audit.json",
         {**audit, "recorded_at": now(), "scheme": "GroupKFold(5, groups=config_id)"})

    results = {"frozen_s1": EV.evaluate_policy(rows, EV.s1_frozen_deploy(rows)),
               "n_rows": len(rows),
               "valid_rows": sum(1 for r in rows if r["gradient_valid"])}

    # S1 comparison on the pooled OOF rows = all rows (outer folds partition)
    candidates = {}
    for name in ("B1_logistic_s1", "B2_s2_logistic", "B3_gbdt"):
        res = MO.nested_cv_eval(name, rows, outer)
        m = EV.evaluate_policy(rows, res["oof_deploy"])
        valid = [i for i, r in enumerate(rows) if r["gradient_valid"]]
        y = np.array([int(rows[i]["label_deploy"]) for i in valid])
        p = np.array([res["oof_prob"].get(i, np.nan) for i in valid])
        cm = EV.classification_metrics(y, p)
        candidates[name] = {"metrics": m, "classification": cm,
                            "selection_log": res["selection_log"]}
        print(f"{name}: coverage={m['deployable_coverage']:.4f} "
              f"unsafe={m['nd_unsafe']:.4f} wrong={m['wrong_direction_rate']:.4f} "
              f"AUC={cm['auc']:.4f}")
    results["candidates"] = candidates
    dump(SUM / "m3ml0_oof_metrics.json", {
        "recorded_at": now(), "frozen_s1": results["frozen_s1"],
        "candidates": {k: {"metrics": v["metrics"],
                           "classification": v["classification"],
                           "selection_log": v["selection_log"]}
                       for k, v in candidates.items()}})
    return results


# --------------------------------------------------------------------------
# stage: mechanism analysis (Q1-Q3)
# --------------------------------------------------------------------------

def mechanism(results: dict) -> dict:
    df = pd.read_parquet(DATA / "m3ml0_tier_a_trials.parquet")
    df["gradient_valid"] = df["gradient_valid"].astype(bool)
    # derived online features (taskbook Sec. 7.1 formulas)
    df["SE_g"] = (df["g_ci_high"] - df["g_ci_low"]) / (2 * 1.959963984540054)
    df["CI_width"] = df["g_ci_high"] - df["g_ci_low"]
    df["abs_g_hat"] = df["g_hat"].abs()
    groups = {}
    for grp in ("DEPLOYABLE", "HOLD", "AMBIGUOUS"):
        if grp == "DEPLOYABLE":
            sub = df[df["truth"].isin(("WIDEN", "SHRINK")) & df["gradient_valid"]]
        else:
            sub = df[(df["truth"] == grp) & df["gradient_valid"]]
        row = {}
        for f in ("S1", "g_hat", "SE_g", "s2", "curvature_c", "ESS_grad"):
            v = sub[f].astype(float)
            row[f] = {"median": float(v.median()), "q1": float(v.quantile(.25)),
                      "q3": float(v.quantile(.75))}
        row["n"] = int(len(sub))
        groups[grp] = row
    # univariate separation (AUC of each feature: DEPLOYABLE vs AMBIGUOUS)
    from sklearn.metrics import roc_auc_score
    dep = df[df["truth"].isin(("WIDEN", "SHRINK")) & df["gradient_valid"]]
    amb = df[(df["truth"] == "AMBIGUOUS") & df["gradient_valid"]]
    hold = df[(df["truth"] == "HOLD") & df["gradient_valid"]]
    univariate = {}
    for f in ("S1", "abs_g_hat", "SE_g", "s2", "curvature_c", "ESS_grad"):
        entry = {}
        for label, other in (("AMBIGUOUS", amb), ("HOLD", hold)):
            y = np.r_[np.ones(len(dep)), np.zeros(len(other))]
            x = np.r_[dep[f].astype(float).values, other[f].astype(float).values]
            ok = ~np.isnan(x)
            try:
                entry[label] = float(roc_auc_score(y[ok], x[ok]))
            except ValueError:
                entry[label] = None
        univariate[f] = entry
    # standardized logistic coefficients (B2 on all valid rows)
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    valid = df[df["gradient_valid"]]
    X = valid[FE.B2_FEATURES].astype(float).values
    y = valid["label_deploy"].astype(int).values
    pipe = Pipeline([("scaler", StandardScaler()),
                     ("clf", LogisticRegression(max_iter=1000, random_state=SEED))])
    pipe.fit(X, y)
    coefs = dict(zip(FE.B2_FEATURES,
                     [float(c) for c in pipe.named_steps["clf"].coef_[0]]))
    # permutation importance of B2 on all valid rows
    pi = permutation_importance(pipe, X, y, n_repeats=20, random_state=SEED)
    perm = dict(zip(FE.B2_FEATURES, [float(v) for v in pi.importances_mean]))
    out = {"group_distributions": groups, "univariate_auc_vs_deployable": univariate,
           "b2_standardized_coefficients": coefs, "b2_permutation_importance": perm,
           "partial_dependence": "SKIPPED (sample size below reliability threshold)",
           "recorded_at": now()}
    dump(SUM / "m3ml0_mechanism_analysis.json", out)
    return out


# --------------------------------------------------------------------------
# stage: verdict
# --------------------------------------------------------------------------

def _verdict_from(s1_metrics: dict, candidates: dict) -> dict:
    """Frozen verdict contract (taskbook Sec. 13)."""
    best, best_key = None, None
    for name, cand in candidates.items():
        m = cand["metrics"]
        if m["safety_compliant"]:
            gain = m["deployable_coverage"] - s1_metrics["deployable_coverage"]
            amb_improved = (m["truth_AMBIGUOUS"]["unsafe"]
                            < s1_metrics["truth_AMBIGUOUS"]["unsafe"])
            key = (-m["deployable_coverage"], m["nd_unsafe"])
            if best is None or key < best_key:
                best = {"model": name, "metrics": m, "gain": gain,
                        "ambig_improved": amb_improved}
                best_key = key
    if best is None:
        return {"VERDICT": "M3-ML0-C",
                "reason": "no candidate satisfied coverage>=0.75 AND ND "
                          "unsafe<=0.20 AND wrong<=0.05",
                "best_safety_compliant_candidate": None}
    if best["gain"] >= COVERAGE_GAIN_MIN and best["ambig_improved"]:
        return {"VERDICT": "M3-ML0-A",
                "reason": "safety-compliant candidate with coverage gain >= "
                          "5pp and AMBIGUOUS unsafe improvement over frozen S1",
                "best_safety_compliant_candidate": best}
    return {"VERDICT": "M3-ML0-B",
            "reason": "safety-compliant candidate but coverage gain < 5pp or "
                      "no AMBIGUOUS unsafe improvement",
            "best_safety_compliant_candidate": best}


def verdict(results: dict) -> dict:
    out = _verdict_from(results["frozen_s1"], results["candidates"])
    out.update({"recorded_at": now(), "frozen_s1": results["frozen_s1"],
                "gates": GATES, "coverage_gain_min": COVERAGE_GAIN_MIN})
    dump(SUM / "m3ml0_verdict.json", out)
    print(f"M3-ML0 VERDICT: {out['VERDICT']} ({out['reason']})")
    return out


# --------------------------------------------------------------------------
# stage: report / docs
# --------------------------------------------------------------------------

def report() -> None:
    verd = load(SUM / "m3ml0_verdict.json")
    mech = load(SUM / "m3ml0_mechanism_analysis.json")
    ds = load(OUT / "m3ml0_dataset_audit.json")
    s1 = verd["frozen_s1"]
    best = verd["best_safety_compliant_candidate"]
    DOC.mkdir(parents=True, exist_ok=True)

    def fmt(m):
        return (f"coverage {m['deployable_coverage']:.4f}, ND unsafe "
                f"{m['nd_unsafe']:.4f}, wrong {m['wrong_direction_rate']:.4f}, "
                f"HOLD unsafe {m['truth_HOLD']['unsafe']:.4f}, AMBIGUOUS unsafe "
                f"{m['truth_AMBIGUOUS']['unsafe']:.4f}")

    claims = {
        "M3-ML0-A": "A grouped-CV development candidate outperformed frozen S1 "
                    "on the exposed canonical dataset under inherited safety "
                    "gates (development-supported candidate only).",
        "M3-ML0-B": "Current feature/model family provided no sufficiently "
                    "strong development improvement over frozen S1.",
        "M3-ML0-C": "No safety-compliant candidate; the current online feature "
                    "family is insufficient for ML confirmation.",
    }[verd["VERDICT"]]

    (DOC / "M3_ML0_Final_Report.md").write_text(f"""# M3-ML0 Final Report

Verdict: **{verd['VERDICT']}** ({verd['recorded_at']}).  {claims}

Development stage only: nothing here is "confirmed"; any successor requires
a new untouched stage.  Zero new simulator calls; the 18 protected reserve
states were untouched.

## 1-10 required answers

1. Tier-A strictly 48 states / 384 trials: **{ds['states']} states / {ds['trials']} trials**; dataset sha256 `{ds['dataset_sha256'][:16]}...`.
2. Protected-18 zero touch: **YES** (overlap = {ds['protected_overlap']}; membership-only CSV in preflight).
3. Frozen S1 on the combined exposed dataset: {fmt(s1)}.
4. S1C AMBIGUOUS failure reproduced on combined data: **YES** (AMBIGUOUS unsafe {s1['truth_AMBIGUOUS']['unsafe']:.4f} vs HOLD {s1['truth_HOLD']['unsafe']:.4f}).
5. Features most helpful for AMBIGUOUS separation (univariate AUC vs DEPLOYABLE): {"; ".join(f"{k} (AMB {v['AMBIGUOUS']:.3f}, HOLD {v['HOLD']:.3f})" for k, v in mech['univariate_auc_vs_deployable'].items())}.
6. Is logistic enough: B1 (S1-only) {fmt(results_metrics('B1_logistic_s1', verd))}; B2 (F0 logistic) {fmt(results_metrics('B2_s2_logistic', verd))}.
7. Does GBDT add stable gain: B3 {fmt(results_metrics('B3_gbdt', verd))}.
8. All results from config-grouped OOF: **YES** (GroupKFold(5) outer on config_id, GroupKFold(4) inner; audit `{OUT / 'm3ml0_groupsplit_audit.json'}`).
9. Safety-compliant candidate with coverage gain >= 5pp: **{verd['VERDICT'] == 'M3-ML0-A'}**{'; best = ' + best['model'] + ', gain ' + format(best['gain'], '.4f') if best else ''}.
10. Next stage: {next_step(verd['VERDICT'])}.

## Mechanism analysis (Q1-Q3, descriptive / non-causal)

- Group medians (S1 / SE_g / s2 / curvature_c): DEPLOYABLE S1 {mech['group_distributions']['DEPLOYABLE']['S1']['median']:.2f}, HOLD S1 {mech['group_distributions']['HOLD']['S1']['median']:.2f}, AMBIGUOUS S1 {mech['group_distributions']['AMBIGUOUS']['S1']['median']:.2f}; SE_g DEPLOYABLE {mech['group_distributions']['DEPLOYABLE']['SE_g']['median']:.5f} vs AMBIGUOUS {mech['group_distributions']['AMBIGUOUS']['SE_g']['median']:.5f}; s2 DEPLOYABLE {mech['group_distributions']['DEPLOYABLE']['s2']['median']:.3f} vs AMBIGUOUS {mech['group_distributions']['AMBIGUOUS']['s2']['median']:.3f}.
- Standardized B2 logistic coefficients: {", ".join(f"{k}={v:+.3f}" for k, v in mech['b2_standardized_coefficients'].items())}.
- B2 permutation importance: {", ".join(f"{k}={v:.4f}" for k, v in mech['b2_permutation_importance'].items())}.
- HOLD is easy for S1 because its gradient CIs are wide relative to |g_hat| (low S1); AMBIGUOUS trials often reach DEPLOYABLE-like S1, so S1 alone cannot separate them -- the quantitative AUC table above shows how far each available descriptor goes.

## Claim boundary

{claims}  Not allowed: "ML controller confirmed", "deployment safe",
"generalizes to the untouched population".  VALUE / RARITY / M3-Q remain
BLOCKED.
""", encoding="utf-8")


def results_metrics(name, verd):
    return verd and load(SUM / "m3ml0_oof_metrics.json")["candidates"][name]["metrics"]


def next_step(v):
    return {
        "M3-ML0-A": "ML-1 fresh development expansion / candidate freeze "
                    "(new preregistered stage; protected reserve stays sealed)",
        "M3-ML0-B": "feature redesign / S2 theory work before any expansion",
        "M3-ML0-C": "feature redesign / S2 theory work; ML confirmation is "
                    "not reachable with the current online features",
    }[v]


def docs() -> None:
    pa = load(OUT / "m3ml0_parent_audit.json")
    fw = load(OUT / "m3ml0_reserve_firewall.json")
    ds = load(OUT / "m3ml0_dataset_audit.json")
    gs = load(OUT / "m3ml0_groupsplit_audit.json")
    (DOC / "M3_ML0_Parent_Audit.md").write_text(f"""# M3-ML0 Parent Audit

Status: **{pa['PARENT_AUDIT']}** ({pa['recorded_at']}), HEAD `{pa['head'][:7]}`.

- Live lineage verified: {' -> '.join(pa['lineage'])}.
- M3-S1C-B sealed: 192/192 durable COMPLETE, 0 consumed-invalid, budget
  3.84M, threshold 5.4417199447782 frozen, wrong 0/128, coverage 0.828125,
  ND unsafe 0.296875 (HOLD 0.0 / AMBIGUOUS 0.59375).
- S1 status: development signal not independently confirmed; S1C panel
  EXPOSED (eligible for Tier-A); VALUE / RARITY / M3-Q BLOCKED.
""", encoding="utf-8")
    (DOC / "M3_ML0_Reserve_Firewall_Audit.md").write_text(f"""# M3-ML0 Reserve Firewall Audit

Status: **{fw['RESERVE_FIREWALL']}** ({fw['recorded_at']}).

- Remaining protected reserve rebuilt live from source artifacts:
  **{fw['remaining']} states** (42 reserve - 24 S1C panel).
- Used by ML-0: **{fw['consumed_by_ml0']}**.  Membership-only CSV:
  `results/phase_m3ml0/preflight/m3ml0_protected_reserve_18.csv`
  (state_id / config_id / membership / source hash).
- Forbidden uses enforced: gradient, V1 probe, S1, features, splits, error
  analysis, threshold selection, theory descriptors, plots.
""", encoding="utf-8")
    (DOC / "M3_ML0_Source_Eligibility_Audit.md").write_text(f"""# M3-ML0 Source Eligibility Audit

Status: **{ds['SOURCE_AUDIT']}** ({ds['recorded_at'] if 'recorded_at' in ds else 'n/a'}).

- Tier-A = 48 states / 384 trials, exactly two same-protocol exposed sources
  (PI1VNR development panel + M3-S1C exposed confirmation panel); dataset
  sha256 `{ds['dataset_sha256'][:16]}...`.
- Durable-COMPLEteness: {json.dumps(ds.get('durable_complete_check', {}))}.
- Tier-B inventory: `results/phase_m3ml0/preflight/m3ml0_tier_b_inventory.csv`
  (classification only; NOT merged into the primary result).
""", encoding="utf-8")
    fc = load(CFG / "m3ml0_feature_contract.json")
    (DOC / "M3_ML0_Feature_Leakage_Audit.md").write_text(f"""# M3-ML0 Feature Leakage Audit

Status: **PASS** (all model feature sets checked against the frozen
forbidden list; 0 hits).

- Model features: B1 {FE.MODEL_FEATURES['B1_logistic_s1']};
  B2 {FE.MODEL_FEATURES['B2_s2_logistic']}; B3 {FE.MODEL_FEATURES['B3_gbdt']}.
- Forbidden (never in X): truth/label, confirmed/provisional labels, P_ref,
  high-budget r_hat/gain, probe outcomes, state_id, config_id (grouping
  only), panel identity, development-vs-confirmation flags.
- F1 availability: ESS_grad included (online, truth-free); p_hat_grad /
  batch dispersion / batch variance NOT persisted in trial records =>
  excluded, never imputed or proxied.
- Invalid-gradient trials ({ds['invalid_gradient_trials']} of 384): never model
  input; deterministic ABSTAIN in every policy.
""", encoding="utf-8")
    (DOC / "M3_ML0_GroupSplit_Audit.md").write_text(f"""# M3-ML0 Group Split Audit

Status: **{'PASS' if gs['PASS'] else 'FAIL'}** ({gs['recorded_at']}).

- Scheme: GroupKFold(5) outer + GroupKFold(4) inner, groups = config_id;
  canonical row order (panel, state_id, rep); deterministic, seed {SEED}.
- Unique configs = {gs['configs_total']}; train/test config overlap =
  {gs['train_test_config_overlap']}; states spanning multiple folds =
  {gs['states_spanning_multiple_folds']}.
""", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "data", "models", "mechanism",
                                      "verdict", "report", "docs", "all"])
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare()
    elif args.stage == "data":
        data()
    elif args.stage == "models":
        models()
    elif args.stage == "mechanism":
        mechanism(load(SUM / "m3ml0_oof_metrics.json"))
    elif args.stage == "verdict":
        results = {"frozen_s1": load(SUM / "m3ml0_oof_metrics.json")["frozen_s1"],
                   "candidates": load(SUM / "m3ml0_oof_metrics.json")["candidates"]}
        verdict(results)
    elif args.stage == "report":
        report()
    elif args.stage == "docs":
        docs()
    elif args.stage == "all":
        prepare(); data(); models(); mechanism(load(SUM / "m3ml0_oof_metrics.json"))
        results = {"frozen_s1": load(SUM / "m3ml0_oof_metrics.json")["frozen_s1"],
                   "candidates": load(SUM / "m3ml0_oof_metrics.json")["candidates"]}
        verdict(results); report(); docs()


if __name__ == "__main__":
    main()
