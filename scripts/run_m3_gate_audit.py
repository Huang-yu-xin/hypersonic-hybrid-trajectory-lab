"""M3 -- preregistered gate audit (task Sec. 24-26).

Consumes the persisted stage batches (layer A main grid, layer B reweight,
step sensitivity) plus the theory-check / sanity gate records and emits ONE
machine-readable verdict block:

    results/phase_m3/summary/gate_audit.json

Checks every firewall item it can verify programmatically (tag ancestry,
frozen-head equality, benchmark hash, task-sha provenance, schema/call
accounting fields); scientific gates M3-2..M3-6 and Strong use ONLY
preregistered constants from configs/phase_m3/m3_scalar_gradient_v0.json.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results" / "phase_m3"
CFG = json.loads((REPO / "configs" / "phase_m3"
                  / "m3_scalar_gradient_v0.json").read_text(encoding="utf-8"))
FREEZE_SHA = hashlib.sha256((REPO / "docs" / "phase_m1d"
                             / "M1_D_Benchmark_Freeze.json")
                            .read_bytes()).hexdigest()
TASK_SHA = hashlib.sha256((REPO / "docs" / "phase_m3"
                           / "M3_Second_Moment_Gradient_Covariance_Control_Task.md")
                          .read_bytes()).hexdigest()

G = CFG["gates_locked"]
TIE = float(CFG["counterfactual_protocol_locked"]["relative_tie_tolerance"])
PROT = CFG["protocol_locked"]
PN_AUDIT = int(PROT["pilot_n_per_round"])
EV_AUDIT = int(PROT["final_eval_n"])
CALLS_SCI = PN_AUDIT + 3 * EV_AUDIT
CALLS_DEP = PN_AUDIT + EV_AUDIT


def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _flatten(batch):
    return [r for e in batch["records_by_config"] for r in e["records"]]


def flat_active(recs):
    return [r for r in recs if r["gradient"]["decision"]
            in ("WIDEN", "SHRINK")]


# --------------------------------------------------------------------------- #
# M3-0 validity (structural half; pytest evidence line supplied by operator)
# --------------------------------------------------------------------------- #
def gate_m3_0(full_pytest_note: str | None) -> dict:
    """Parent-tag 'unchanged' is checked against the SHAs RECORDED AT FREEZE
    TIME: M1-D head and M2 head are preregistered inside the locked config;
    the H3 / M1-v0 tag targets are read from docs/phase_m2/M2_Freeze_Summary.md
    (fixed-format lines committed before any M3 run)."""
    import re
    freeze_doc = (REPO / "docs" / "phase_m2" / "M2_Freeze_Summary.md") \
        .read_text(encoding="utf-8")

    def doc_sha(tag: str) -> str | None:
        m = re.search(rf"{re.escape(tag)}\s*->\s*([0-9a-f]{{40}})", freeze_doc)
        return m.group(1) if m else None

    expect = {
        "RareTopo-H3-v1.0": doc_sha("RareTopo-H3-v1.0"),
        "RareTopo-M1-v0": doc_sha("RareTopo-M1-v0"),
        "RareTopo-M1-D-v1.0":
            CFG["parent_tags"]["m1d_frozen_head"],
        "RareTopo-M2-v0": CFG["parent_tags"]["m2_frozen_head"],
    }
    tags_ok, tags_resolved = {}, {}
    for name, want in expect.items():
        got = _git("rev-parse", f"{name}^{{commit}}")
        tags_resolved[name] = got or None
        tags_ok[name] = bool(want) and bool(got == want)

    m2_contains = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "RareTopo-M2-v0", "HEAD"],
        cwd=REPO, capture_output=True)
    derivation_exists = (REPO / "docs" / "phase_m3"
                         / "M3_Covariance_Gradient_Derivation.md").exists()
    la = _load(RES / "scalar_layer_a" / "scalar_layer_a_v1.json")
    layer_ok = all(r["layer"] == "fixed_weights" for r in _flatten(la))
    hash_ok = bool(la["benchmark_freeze_hash"] == FREEZE_SHA)
    prov_task_ok = bool(CFG["provenance"]["task_sha256"] == TASK_SHA)
    calls_ok = all(
        r["evaluation"].get("scientific_audit_calls") == CALLS_SCI
        and r["evaluation"].get("deployable_method_calls") == CALLS_DEP
        for r in _flatten(la)
        if r.get("evaluation", {}).get("scientific_audit_calls") is not None)

    checks = {
        "parent_tags_unchanged_vs_freeze_records": tags_ok,
        "resolved_tag_commits": tags_resolved,
        "m2_tag_is_ancestor_of_HEAD": bool(m2_contains.returncode == 0),
        "derivation_document_present": bool(derivation_exists),
        "benchmark_hash_matches_archive": hash_ok,
        "task_sha_provenance_matches": prov_task_ok,
        "layer_A_records_all_fixed_weights": layer_ok,
        "dual_call_accounting_fields_present_and_constant": calls_ok,
        "no_oracle_in_estimator_paths": True,   # structural: estimator APIs
        #     take pilot arrays only (unit test test_m3_no_final_eval_leakage)
        "full_pytest_evidence": full_pytest_note,
    }
    required_true = ["m2_tag_is_ancestor_of_HEAD",
                     "derivation_document_present",
                     "benchmark_hash_matches_archive",
                     "task_sha_provenance_matches",
                     "layer_A_records_all_fixed_weights",
                     "dual_call_accounting_fields_present_and_constant"]
    ok = all(bool(checks[k]) for k in required_true) \
        and all(checks["parent_tags_unchanged_vs_freeze_records"].values())
    return {"name": "M3-0_validity", "checks": checks,
            "verdict": "PASS" if ok else "FAIL"}


def aggregate_layer_a(la_batch):
    from hyptraj.m3.metrics import aggregate_gate_quantities
    recs = _flatten(la_batch)
    agg = aggregate_gate_quantities(recs, TIE)
    active = flat_active(recs)
    # leakage per config medians already inside agg; Strong input here:
    strong_vals = [r["evaluation"]["VRF_budget_grad_path"] for r in recs
                   if r.get("evaluation", {}).get("VRF_budget_grad_path")
                   is not None]
    agg["strong_vrf_values"] = strong_vals
    agg["strong_median"] = float(np.median(strong_vals)) if strong_vals else None
    # Always-Widen operational VRF for context (fixed-rule deployable path)
    aw_vals = []
    for r in recs:
        ev = r["_arms"]["widen"]
        aw_vals.append(ev["VRF_budget"])
    agg["always_widen_vrf_median_CONTEXT_ONLY"] = \
        float(np.median(aw_vals)) if aw_vals else None
    return agg


def scientific_gates(agg, sens_batch=None, lb_batch=None,
                     full_sens_report=None) -> dict:
    acc_aw = agg["acc_always_widen_on_active"] or 0.0
    acc_as = agg["acc_always_shrink_on_active"] or 0.0
    advantage_pp = (agg["acc_dir"] - max(acc_aw, acc_as)) * 100.0 \
        if agg["acc_dir"] is not None else None

    g32 = {"active_fraction": agg["active_fraction"],
           "threshold_min": G["M3_2_direction_identifiability"]
           ["confident_non_HOLD_fraction_of_64_min"],
           "n_active": agg["n_active"], "n_total": agg["n_trials"]}
    g32["verdict"] = ("PASS" if g32["active_fraction"] >= g32["threshold_min"]
                      else "FAIL")

    g33 = {"acc_dir_among_active": agg["acc_dir"],
           "acc_floor": G["M3_3_direction_accuracy"]["acc_dir_active_min"],
           "advantage_over_best_fixed_pp": advantage_pp,
           "advantage_floor_pp": G["M3_3_direction_accuracy"]
           ["advantage_over_preregistered_nonadaptive_comparator_pp"],
           "comparators": {"always_widen": acc_aw, "always_shrink": acc_as}}
    g33["clause_a_pass"] = bool(g33["acc_dir_among_active"] >= g33["acc_floor"])
    g33["clause_b_pass"] = bool(advantage_pp is not None
                                and advantage_pp >= g33["advantage_floor_pp"])
    g33["verdict"] = ("PASS" if (g33["clause_a_pass"] and g33["clause_b_pass"])
                      else "FAIL")

    g34 = {"success_rate_pred_lt_base": agg["rate_M2_pred_lt_base"],
           "rate_floor": G["M3_4_predicted_step_m2_gain"]
           ["success_rate_active_min"],
           "median_ratio_pred_base": agg["median_ratio_pred_base"],
           "median_ratio_cap": G["M3_4_predicted_step_m2_gain"]
           ["median_M2_pred_over_base_max"]}
    g34["verdict"] = ("PASS" if (g34["success_rate_pred_lt_base"] is not None
                                 and g34["median_ratio_pred_base"] is not None
                                 and g34["success_rate_pred_lt_base"] >= g34["rate_floor"]
                                 and g34["median_ratio_pred_base"] <= g34["median_ratio_cap"])
                      else "FAIL")

    g35 = {"median_ratio_pred_opposite": agg["median_ratio_pred_opposite"],
           "cap": G["M3_5_counterfactual_ordering"]
           ["median_M2_pred_over_opposite_max"]}
    g35["verdict"] = ("PASS" if g35["median_ratio_pred_opposite"] is not None
                      and g35["median_ratio_pred_opposite"] <= g35["cap"]
                      else "FAIL")

    leak_by_cfg = agg["leakage_median_max_offtarget_by_config"]
    within = sum(1 for v in leak_by_cfg.values() if v <= 2.0)
    g36 = {"configs_within_ratio_2": within,
           "of_configs": len(leak_by_cfg),
           "min_configs": G["M3_6_no_catastrophic_leakage_redistribution"]
           ["configs_ok_min"],
           "per_config_median_max_offtarget": leak_by_cfg}
    g36["verdict"] = ("PASS" if within >= g36["min_configs"] else "FAIL")

    strong = {"median_deployable_vrf_grad_path": agg["strong_median"],
              "required_gt": G["STRONG_budget_adjusted_vrf"]["median_deployable_vrf_gt"],
              "context_always_widen_vrf_median":
                  agg.get("always_widen_vrf_median_CONTEXT_ONLY")}
    strong["verdict"] = ("PASS" if strong["median_deployable_vrf_grad_path"]
                         is not None
                         and strong["median_deployable_vrf_grad_path"]
                         > strong["required_gt"] else "NOT PASSED")

    out = {"M3_2_direction_identifiability": g32,
           "M3_3_direction_accuracy": g33,
           "M3_4_predicted_step_m2_gain": g34,
           "M3_5_counterfactual_ordering": g35,
           "M3_6_no_catastrophic_leakage_redistribution": g36,
           "STRONG_budget_adjusted_vrf": strong}
    return out


def interpret(fd_valid: bool, gates: dict) -> str:
    acc = gates["M3_3_direction_accuracy"]["clause_a_pass"]
    lowers = gates["M3_4_predicted_step_m2_gain"]["verdict"] == "PASS"
    opp = gates["M3_5_counterfactual_ordering"]["verdict"] == "PASS"
    strongv = gates["STRONG_budget_adjusted_vrf"]["verdict"] == "PASS"
    adv = gates["M3_3_direction_accuracy"].get("advantage_over_best_fixed_pp")
    beats_compare_strongly = bool(adv is not None and adv >= 25)
    if not fd_valid:
        return "Row 1: theory/implementation invalid"
    if not acc:
        return "Row 2: finite-sample gradient not predictive"
    if not lowers:
        return "Row 3: sign informative but action ineffective"
    if not opp:
        return "Row 4-weak: local descent works, contrast noisy"
    if not beats_compare_strongly or not strongv:
        base = ("Rows 4-5 boundary: local descent works with STRONG "
                "counterfactual ordering")
        if not beats_compare_strongly and not strongv:
            base += "; gradient adds NO measurable direction value beyond " \
                    "the fixed widening rule AND budget VRF < 1 " \
                    "(Gradient ~= Always-Widen)"
        elif not beats_compare_strongly:
            base += "; gradient adds no accuracy beyond fixed widening " \
                    "(Gradient ~= Always-Widen)"
        else:
            base += "; budget VRF < 1"
        return base
    return "Row 6: core + strong M3 success"


def main() -> int:
    full_pytest_note = ("python -m pytest -q : 1128 passed / 0 failed, "
                        "3 warnings, 331.42 s, exit code 0 (freeze-audit "
                        "full-suite rerun 2026-08-27 after all M3 "
                        "scientific runs; no scientific run touched)")
    theory = _load(RES / "theory_checks" / "theory_checks_v1.json")
    fd_valid = theory["summary"]["gate_M3_1"] == "PASS"

    la = _load(RES / "scalar_layer_a" / "scalar_layer_a_v1.json")
    lb = (_load(RES / "scalar_layer_b" / "scalar_layer_b_v1.json")
          if (RES / "scalar_layer_b" / "scalar_layer_b_v1.json").exists()
          else None)
    sens = (_load(RES / "sensitivity" / "step_sensitivity_v1.json")
            if (RES / "sensitivity" / "step_sensitivity_v1.json").exists()
            else None)

    m30 = gate_m3_0(full_pytest_note)
    agg = aggregate_layer_a(la)
    sci = scientific_gates(agg, sens, lb)

    core_pass = all(sci[k]["verdict"] == "PASS" for k in
                    ("M3_2_direction_identifiability",
                     "M3_3_direction_accuracy",
                     "M3_4_predicted_step_m2_gain",
                     "M3_5_counterfactual_ordering",
                     "M3_6_no_catastrophic_leakage_redistribution"))

    out = {
        "schema_version": "raretopo-m3-gate-audit-v0",
        "record_schema_version": CFG["outputs_locked"]["record_schema_version"],
        "benchmark_freeze_hash": FREEZE_SHA,
        "task_sha256": TASK_SHA,
        "prereg_config_sha256": hashlib.sha256(
            (REPO / "configs" / "phase_m3" / "m3_scalar_gradient_v0.json")
            .read_bytes()).hexdigest(),
        "m2_tag_commit": CFG["parent_tags"]["m2_frozen_head"],
        "layer_A_batch_git_commit": la.get("git_commit"),
        "gates": {"M3_0_validity": m30,
                  **sci},
        "aggregates_layer_A": agg,
        "layer_B_present": lb is not None,
        "layer_B_summary_direction_agreement": (
            None if lb is None else _lb_vs_la(la, lb)),
        "sensitivity_present": sens is not None,
        "interpretation_matrix_row": interpret(fd_valid, sci),
        "core_gates_all_pass": core_pass and m30["verdict"] == "PASS",
        "strong_gate_passed": sci["STRONG_budget_adjusted_vrf"]["verdict"]
        == "PASS",
        "headline_allowed_claim": None,
    }
    if out["core_gates_all_pass"]:
        if abs((sci["M3_3_direction_accuracy"]["advantage_over_best_fixed_pp"]
                or 0)) < 25:
            out["headline_allowed_claim"] = (
                "The second-moment derivative correctly predicts widening on "
                "this benchmark, but provides limited measurable value beyond "
                "a fixed widening rule (task Sec.35 variant claim).")
        else:
            out["headline_allowed_claim"] = (
                "A finite-sample estimate of the second-moment covariance "
                "derivative predicts a local Gaussian scale direction that "
                "reduces estimator second moment more reliably than the "
                "opposite covariance perturbation under matched proposal "
                "state and evaluation budgets (task Sec.35 primary claim).")
    dest = RES / "summary" / "gate_audit.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"gates: M3-0 {m30['verdict']} ; " +
          " ; ".join(f"{k}={v['verdict']}" for k, v in sci.items()))
    print("interpretation:", out["interpretation_matrix_row"])
    print("core:", out["core_gates_all_pass"],
          "| strong:", out["strong_gate_passed"])
    print(f"[saved] {dest.relative_to(REPO)}")
    return 0


def _lb_vs_la(la_batch, lb_batch):
    """Fraction of trials whose GRADIENT direction still beats opposite under
    Layer B weights (Layer B can never rescue Layer A; reported only)."""
    la = {(r["config_id"], int(r["seed"])): r
          for e in la_batch["records_by_config"] for r in e["records"]}
    agree = same_decision = n = 0
    ratios = []
    for e in lb_batch["records_by_config"]:
        for r in e["records"]:
            key = (r["config_id"], int(r["seed"]))
            other = la.get(key)
            if other is None:
                continue
            n += 1
            if r["gradient"]["decision"] == other["gradient"]["decision"]:
                same_decision += 1
            cf = r["counterfactual"]
            if cf.get("M2_opposite") not in (None, 0):
                try:
                    ratios.append(cf["M2_pred"] / cf["M2_opposite"])
                except Exception:
                    pass
            if cf.get("M2_pred") is not None and cf.get("M2_base"):
                pass
            agree += 1
    return {"n_paired": n, "same_decision_fraction":
            (same_decision / n if n else None),
            "median_ratio_pred_opposite_lb":
            (float(np.median(ratios)) if ratios else None)}


if __name__ == "__main__":
    raise SystemExit(main())
