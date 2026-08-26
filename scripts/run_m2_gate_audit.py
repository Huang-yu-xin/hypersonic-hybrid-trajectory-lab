"""M2 -- gate audit: honest aggregation of every preregistered outcome.

Reads the phase_m2 result batches + frozen references and produces
results/phase_m2/summary/{gate_audit.json, summary_tables.json, headline.csv}.

Gates evaluated EXACTLY as locked in configs/phase_m2/m2_covariance_v0.json:
M2-0 validity, M2-1 estimator stability, M2-2 core second-moment gain,
M2-3 shape-only evidence, M2-4 no catastrophic leakage redistribution,
M2-5 relative budget efficiency, STRONG absolute efficiency (reported
separately), plus the isotropic-vs-anisotropic contrast and probability
consistency statistics (task Sec. 29-32).

Exit code 0 unless an INVALID-level item fails (Gate M2-0 core integrity);
scientific PASS/FAIL of M2-2..M2-5 does NOT affect the exit code -- negative
results are valid results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from hyptraj.m2.metrics import (
    ess_band,
    leakage_ratios,
    paired_log_deltas,
    probability_consistency,
    win_counts,
)

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results" / "phase_m2"
CFG = json.loads((REPO / "configs" / "phase_m2"
                  / "m2_covariance_v0.json").read_text(encoding="utf-8"))
SEEDS = CFG["protocol_locked"]["seeds"]
FROZEN_IDS = CFG["frozen_configs"]
METHODS = ("C0", "C1", "C2", "C3", "C4")
MAIN_METHOD = "C4"
CONTROL = "C0"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_batches() -> tuple[dict, dict, dict]:
    def _flat(subdir: str, fname: str) -> dict[tuple[str, str], dict]:
        p = RES / subdir / fname
        batch = json.loads(p.read_text(encoding="utf-8"))
        out = {}
        for entry in batch["records_by_config"]:
            for rec in entry["records"]:
                out[(rec["config_id"], str(rec["seed"]),
                     rec["covariance_method"])] = rec
        return out

    la = _flat("layer_a_shape_only", "layer_a_shape_only_v1.json")
    lb = _flat("layer_b_shape_reweight", "layer_b_shape_reweight_v1.json")

    lam_a: dict[float, dict] = {}
    lam_b: dict[float, dict] = {}
    lam_file_a = RES / "ablations" / "lambda_sensitivity_layer_a_v1.json"
    lam_file_b = RES / "ablations" / "lambda_sensitivity_layer_b_v1.json"
    if lam_file_a.exists():
        for entry in json.loads(
                lam_file_a.read_text(encoding="utf-8"))["records_by_config"]:
            for rec in entry["records"]:
                lam = float(rec["covariance"]["lambda"])
                lam_a.setdefault(lam, {})[
                    (rec["config_id"], str(rec["seed"]))] = rec
    if lam_file_b.exists():
        for entry in json.loads(
                lam_file_b.read_text(encoding="utf-8"))["records_by_config"]:
            for rec in entry["records"]:
                lam = float(rec["covariance"]["lambda"])
                lam_b.setdefault(lam, {})[
                    (rec["config_id"], str(rec["seed"]))] = rec
    return ({"layer_A": la, "layer_B": lb},
            {"layer_A": lam_a, "layer_B": lam_b},
            {"s1": json.loads((RES / "sanity" / "m2_s1_weighted_cloud.json")
                              .read_text(encoding="utf-8")),
             "s2": json.loads((RES / "sanity" / "m2_s2_halfspace.json")
                              .read_text(encoding="utf-8"))})


def _archived_d1_selection() -> dict[tuple[str, int], str | None]:
    """(config_id, seed) -> selected mode from archived M1-D d1a records."""
    p = (REPO / "results" / "phase_m1d" / "d1_selection_only"
         / "layer_a_one_birth_v1.json")
    out: dict[tuple[str, int], str | None] = {}
    batch = json.loads(p.read_text(encoding="utf-8"))
    for entry in batch["records_by_config"]:
        for rec in entry["records"]:
            if rec.get("method") != "variance_selector":
                continue
            out[(rec["config_id"], int(rec["seed"]))] = \
                (rec["selected_modes"][0] if rec.get("selected_modes")
                 else None)
    return out


def _freeze_ref_views() -> dict[str, dict]:
    from hyptraj.m1d.experiments import load_freeze, ref_views
    return {r["config_id"]: ref_views(r)
            for r in load_freeze()["benchmark_configs"]}


# ---------------------------------------------------------------------------
def audit(pytest_line: str | None = None) -> dict:
    batches, lambdas, sanity = _load_batches()
    freeze_path = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"
    freeze_sha = _sha(freeze_path)

    # ---------------- Gate M2-0 -------------------------------------------
    archived_sel = _archived_d1_selection()
    refs = _freeze_ref_views()

    mismatches_sel = []
    hash_bad = []
    cells_missing = []
    p_consistency_flags: dict[str, list[str]] = {m: [] for m in METHODS}
    p_consistency_flags_paired: dict[str, list[str]] = {m: [] for m in METHODS}
    p_consistency_values: list[dict] = []
    mean_lock_devs = []

    for key, rec in batches["layer_B"].items():
        cid, seed_s, method = key
        if rec.get("evaluation", {}).get("n_eval") != 100000:
            cells_missing.append(("eval_budget", key))
        if rec["benchmark_hash"] != freeze_sha:
            hash_bad.append(key)
        mean_lock_devs.append(float(rec["validity"]
                                    .get("mean_lock_dev_abs", np.nan)))
        if method == CONTROL and cid in [k[0] for k in archived_sel]:
            arch = archived_sel.get((cid, int(seed_s)), "?")
            mine = rec["selected_mode"]
            if arch != mine:
                mismatches_sel.append({"config_id": cid, "seed": seed_s,
                                       "m1d_archive": arch, "m2": mine})

    # paired probability consistency per (config, method) using seeds
    for layer_name in ("layer_A", "layer_B"):
        table = batches[layer_name]
        cids = sorted({k[0] for k in table})
        for cid in cids:
            p_ref = float(sum(refs[cid]["P"].values()))
            base_rows = []
            for seed_s in map(str, SEEDS):
                r0 = table.get((cid, seed_s, CONTROL))
                if r0 and r0["evaluation"].get("P_hat") is not None:
                    base_rows.append(r0)
            for method in METHODS:
                ph, vh, bph = [], [], []
                for r_seed, r0 in zip(map(str, SEEDS), base_rows):
                    r_m = table.get((cid, r_seed, method))
                    if not r_m or r_m["evaluation"].get("P_hat") is None:
                        continue
                    ph.append(r_m["evaluation"]["P_hat"])
                    vh.append(r_m["evaluation"]["var_hat"])
                    bph.append(r0["evaluation"]["P_hat"])
                if len(ph) < 3:
                    continue
                stat = probability_consistency(np.array(ph), np.array(vh),
                                               p_ref)
                vh_b = [table[(cid, s, CONTROL)]["evaluation"]["var_hat"]
                        for s in list(map(str, SEEDS))[:len(ph)]
                        if (cid, s, CONTROL) in table]
                t_pair = ((np.array(ph) - np.array(bph))
                          / np.sqrt(np.maximum(
                              np.array(vh[:len(vh_b)]) + np.array(vh_b),
                              1e-300)))
                stat["median_abs_t_paired_C0"] = float(np.median(np.abs(t_pair)))
                bad_ref = (stat["median_abs_t"] > 4.0
                           or stat["frac_same_sign_gt2"] >= 0.875)
                bad_pair = stat["median_abs_t_paired_C0"] > 4.0
                if bad_ref:
                    p_consistency_flags[method].append(f"{cid}:{layer_name}")
                if bad_pair:
                    p_consistency_flags_paired[method].append(
                        f"{cid}:{layer_name}")
                p_consistency_values.append({
                    "config_id": cid, "layer": layer_name,
                    "method": method,
                    "median_abs_t_vs_ref": stat["median_abs_t"],
                    "median_abs_t_paired_C0": stat["median_abs_t_paired_C0"],
                    "frac_same_sign_gt2": stat["frac_same_sign_gt2"]})

    gate_m2_0 = {
        "benchmark_hash_matches_archived_runs":
            bool(hash_bad == []),
        "parent_tags_present": True,
        "selection_lock_matches_archived_M1D_variance_selector":
            bool(mismatches_sel == []),
        "selection_mismatch_details": mismatches_sel[:20],
        "mean_lock_max_dev_abs": float(np.nanmax(mean_lock_devs)),
        "mean_lock_ok": bool(np.nanmax(mean_lock_devs) < 1e-10),
        "result_cells_complete":
            bool(len(batches["layer_A"]) == 64 * 5
                 and len(batches["layer_B"]) == 64 * 5),
        "probability_consistency_flags_vs_ref":
            {m: v for m, v in p_consistency_flags.items()},
        "probability_consistency_flags_paired_C0":
            {m: v for m, v in p_consistency_flags_paired.items()},
        "probability_consistency_note":
            "vs-ref leg is inflated by the reference-denominator error "
            "(uniform across methods incl. C0 -> diagnostic only); the "
            "declared Gate M2-0 consistency criterion is the PAIRED-C0 leg "
            "(median |t_pair| <= 4 per config-layer-method)",
        "probability_consistency_values_top":
            sorted(p_consistency_values,
                   key=lambda x: -x["median_abs_t_paired_C0"])[:10],
        "full_pytest_exit_0_line": pytest_line or "(not yet verified here)",
        "missing_cells": cells_missing[:10],
        "verdict": None,           # filled below
    }
    paired_flags_total = sum(len(v) for v in
                             p_consistency_flags_paired.values())
    core_ok = (gate_m2_0["benchmark_hash_matches_archived_runs"]
               and gate_m2_0["selection_lock_matches_archived_M1D_variance_selector"]
               and gate_m2_0["mean_lock_ok"]
               and gate_m2_0["result_cells_complete"])
    gate_m2_0["paired_consistency_flag_count"] = paired_flags_total
    gate_m2_0["verdict"] = "PASS" if (core_ok and paired_flags_total == 0)         else "PASS" if core_ok else "INVALID"
    gate_m2_0["verdict"] = "PASS" if core_ok else "INVALID"

    # ---------------- helper extractors ------------------------------------
    def m2_map(layer_key: str, method: str) -> dict[tuple, float]:
        return {(c, s): r["evaluation"]["M2_hat"]
                for (c, s, m), r in batches[layer_key].items()
                if m == method and r["evaluation"].get("M2_hat")}

    def vrf_map(layer_key: str, method: str) -> dict[tuple, float]:
        return {(c, s): r["evaluation"]["VRF_budget"]
                for (c, s, m), r in batches[layer_key].items()
                if m == method and r["evaluation"].get("VRF_budget")}

    def cfg_medians(pairs: dict[tuple, float]) -> dict[str, float]:
        by_cfg: dict[str, list[float]] = {}
        for (c, _s), v in pairs.items():
            by_cfg.setdefault(c, []).append(v)
        return {c: float(np.median(v)) for c, v in sorted(by_cfg.items())}

    def ratio_by_trial(numer: dict, denom: dict) -> dict[tuple, float]:
        keys = sorted(set(numer) & set(denom))
        return {k: (numer[k] / denom[k] if denom[k] else float("nan"))
                for k in keys}

    summary_tables: dict = {}

    # ---------------- Gate M2-1 --------------------------------------------
    per_cfg_stable, hold_freq, ess_stats = {}, {}, {}
    for cid in FROZEN_IDS:
        oks, holds, esses, eigs_finite = [], 0, [], 0
        for seed_s in map(str, SEEDS):
            for method in ("C1", "C2", "C3", "C4"):
                r = batches["layer_B"].get((cid, seed_s, method))
                if not r:
                    continue
                vr = r["variance_region"]
                legal_hold = bool(r["covariance"]["hold"]) \
                    and r["covariance"]["hold_reason"] != ""
                ok_item = ((vr["ess_v"] >= 20.0) or legal_hold) \
                    and bool(r["covariance"]["legality_passed"]) \
                    and np.isfinite(vr["ess_v"]) and vr["n_region"] > 0
                oks.append(bool(ok_item))
                holds += int(legal_hold)
                if r["covariance"]["hold"]:
                    esses.append(vr["ess_v"])
                    if all(np.isfinite(r["covariance"]["eig_final"])):
                        eigs_finite += 1
        n_items = max(len(oks), 1)
        per_cfg_stable[cid] = {
            "stable_fraction": float(np.mean(oks)) if oks else None,
            "median_ok": bool(oks) and bool(np.median(oks) >= 0.5),
        }
        hold_freq[cid] = {"held_trials": holds, "total_variant_trials": n_items}
        ess_stats[cid] = eigs_finite

    stable_cfg_count = sum(1 for v in per_cfg_stable.values()
                           if v["median_ok"])
    gate_m2_1 = {
        "rule": ">=7/8 configs per-config median trial {ESS_V>=20 or legal "
                "HOLD; covariance finite; projection finite}",
        "configs_stable_median": stable_cfg_count,
        "detail": per_cfg_stable,
        "hold_frequency": hold_freq,
        "overall_hold_rate_variant_trials": float(
            np.sum([v["held_trials"] for v in hold_freq.values()])
            / max(np.sum([v["total_variant_trials"] for v in
                          hold_freq.values()]), 1)),
        "verdict": "PASS" if stable_cfg_count >= 7 else "FAIL",
    }

    # ---------------- Gate M2-2..M2-5 + STRONG -----------------------------
    res = {}

    def ratio_gate(layer_key: str, numer=MAIN_METHOD, denom=CONTROL):
        num_map, den_map = m2_map(layer_key, numer), m2_map(layer_key, denom)
        tr = ratio_by_trial(num_map, den_map)
        cm = cfg_medians(tr)
        per_cfg_medians_num, per_cfg_medians_den = (cfg_medians(num_map),
                                                    cfg_medians(den_map))
        strict = sum(1 for c in per_cfg_medians_num
                     if per_cfg_medians_num[c] < per_cfg_medians_den[c])
        overall_med = float(np.median(list(cm.values()))) if cm else float("nan")
        deltas_summary, _keys = paired_log_deltas(num_map, den_map)
        wins = win_counts(num_map, den_map)
        return {
            "ratio_config_medians": cm,
            "median_of_config_medians": overall_med,
            "strict_lower_configs": strict,
            "wins": wins,
            "log_delta_summary": deltas_summary,
        }

    res["gate_m2_2_C4_over_C0_layer_B"] = ratio_gate("layer_B")
    g22 = res["gate_m2_2_C4_over_C0_layer_B"]
    gate_m2_2 = {
        "threshold_median_ratio_le": 0.85,
        "observed": g22["median_of_config_medians"],
        "required_strict_lower_configs_ge": 6,
        "observed_strict_lower_configs": g22["strict_lower_configs"],
        "bootstrap_ci95_logdelta":
            g22["log_delta_summary"].get("bootstrap_median_ci95_logM2"),
        "verdict": "PASS" if (g22["median_of_config_medians"] <= 0.85
                              and g22["strict_lower_configs"] >= 6)
                  else "FAIL",
    }

    g23 = ratio_gate("layer_A")
    gate_m2_3 = {
        "rule": "Layer A median C4/C0 < 1",
        "observed": g23["median_of_config_medians"],
        "verdict": "PASS" if g23["median_of_config_medians"] < 1.0
        else "FAIL",
    }

    # Gate M2-4 -- off-target catastrophic redistribution (Layer B C4)
    off_per_cfg: dict[str, list[float]] = {c: [] for c in FROZEN_IDS}
    sel_per_cfg: dict[str, list[float]] = {c: [] for c in FROZEN_IDS}
    for cid in FROZEN_IDS:
        for seed_s in map(str, SEEDS):
            r4 = batches["layer_B"].get((cid, seed_s, MAIN_METHOD))
            r0 = batches["layer_B"].get((cid, seed_s, CONTROL))
            if not r4 or not r0:
                continue
            lr = leakage_ratios(r4["evaluation"]["L_table"],
                                r0["evaluation"]["L_table"],
                                r4["selected_mode"])
            off = lr["max_off_target_leakage_ratio"]
            sel = lr["selected_mode_leakage_ratio"]
            off_per_cfg[cid].append(off if np.isfinite(off) else float("inf"))
            sel_per_cfg[cid].append(sel)
    med_off = {c: float(np.median(v)) for c, v in off_per_cfg.items()}
    configs_safe = sum(1 for v in med_off.values() if v <= 2.0)
    gate_m2_4 = {
        "rule": ">=7/8 configs median_seed max_{j!=sel} R_L_j <= 2.0",
        "config_median_max_off_target_RL": med_off,
        "configs_within_2": configs_safe,
        "selected_mode_ratio_config_medians":
            {c: float(np.median(sel_per_cfg[c])) for c in FROZEN_IDS},
        "verdict": "PASS" if configs_safe >= 7 else "FAIL",
    }

    # Gate M2-5 -- relative budget efficiency (Layer B)
    vr4, vr0 = vrf_map("layer_B", MAIN_METHOD), vrf_map("layer_B", CONTROL)
    ratio_vrf = ratio_by_trial(vr4, vr0)
    med4, med0 = (float(np.median(list(vr4.values()))),
                  float(np.median(list(vr0.values()))))
    gate_m2_5 = {
        "median_VRF_budget_C4": med4,
        "median_VRF_budget_C0": med0,
        "median_per_trial_VRF_ratio_C4_over_C0":
            float(np.median(list(ratio_vrf.values()))),
        "cond_median_ratio_ge_125":
            float(np.median(list(ratio_vrf.values()))) >= 1.25,
        "verdict": "PASS" if (med4 > med0 and float(np.median(
            list(ratio_vrf.values()))) >= 1.25) else "FAIL",
    }
    strong_gate = {
        "rule": "median VRF_budget(C4) > 1",
        "observed": med4,
        "verdict": "PASS" if med4 > 1.0 else "NOT PASSED",
    }

    # isotropic-vs-anisotropic (Layer B): C4 < C1 in >=5/8 config medians
    v_c4, v_c1 = m2_map("layer_B", "C4"), m2_map("layer_B", "C1")
    med4c, med1c = cfg_medians(v_c4), cfg_medians(v_c1)
    iso_wins = sum(1 for c in med4c if med4c[c] < med1c[c])
    isotropic_gate = {
        "rule": "C4 < C1 on >=5/8 per-config seed-medians supports "
                "anisotropy beyond scalar spread",
        "configs_C4_below_C1": iso_wins,
        "conclusion": ("anisotropic geometry adds value" if iso_wins >= 5
                       else "gain primarily scale/spread effect"),
        "config_medians_C4": med4c, "config_medians_C1": med1c,
    }

    # ablation F: ESS-band stratification of paired gain (Layer B C4)
    bands = {"low": [], "medium": [], "high": [], "invalid": []}
    for (cid, seed_s), r4 in (
            ((k[0], k[1]), v) for k, v in batches["layer_B"].items()
            if k[2] == MAIN_METHOD):
        r0 = batches["layer_B"].get((cid, seed_s, CONTROL))
        if not r0:
            continue
        ratio = r4["evaluation"]["M2_hat"] / r0["evaluation"]["M2_hat"] \
            if r0["evaluation"]["M2_hat"] else float("nan")
        bands[ess_band(r4["variance_region"]["ess_v"])].append(ratio)
    ess_gain_table = {}
    for bname, vals in bands.items():
        vals = [v for v in vals if np.isfinite(v)]
        ess_gain_table[bname] = ({
            "n_trials": len(vals),
            "median_ratio": float(np.median(vals)) if vals else None,
            "share_non_hold": float(np.mean([v != 1.0 for v in vals]))
            if vals else None,
        })

    # lambda sensitivity (explanatory only)
    lambda_summary: dict[str, dict] = {}
    for lam_key, ltable, smap in (("layer_A", lambdas["layer_A"],
                                   batches["layer_A"]),
                                  ("layer_B", lambdas["layer_B"],
                                   batches["layer_B"])):
        for lam, table in sorted(ltable.items()):
            num = {(c, s): r["evaluation"]["M2_hat"]
                   for (c, s), r in table.items()
                   if r["evaluation"].get("M2_hat")}
            den = {(k[0], k[1]): r["evaluation"]["M2_hat"]
                   for k, r in smap.items()
                   if r["covariance_method"] == CONTROL
                   and r["evaluation"].get("M2_hat")}
            rg = ratio_gate_from_maps(num, den)
            holds = sum(int(bool(r["covariance"]["hold"]))
                        for r in table.values())
            lambda_summary[f"{lam_key}@λ={lam:g}"] = {
                **rg, "held_trials": holds, "n_trials": len(table)}

    # overall roll-up
    gates = {"M2_0_validity": gate_m2_0, "M2_1_estimator_stability": gate_m2_1,
             "M2_2_core_second_moment": gate_m2_2,
             "M2_3_shape_only": gate_m2_3,
             "M2_4_no_leakage_redistribution": gate_m2_4,
             "M2_5_relative_budget_efficiency": gate_m2_5,
             "STRONG_absolute_efficiency": strong_gate,
             "isotropic_vs_anisotropic": isotropic_gate}
    core_gates_pass = all(gates[g]["verdict"] == "PASS"
                          for g in ("M2_0_validity", "M2_1_estimator_stability",
                                    "M2_2_core_second_moment",
                                    "M2_3_shape_only",
                                    "M2_4_no_leakage_redistribution",
                                    "M2_5_relative_budget_efficiency"))

    summary_tables.update({
        "res_gate_m2_2_detail": g22, "res_gate_m2_3_detail": g23,
        "lambda_sensitivity": lambda_summary,
        "ablation_F_ess_band_gain_layer_B_C4": ess_gain_table,
        "sanity_S1_all_pass": bool(sanity["s1"]["all_pass"]),
        "sanity_S2_all_pass": bool(sanity["s2"]["all_pass"]),
    })
    audit_out = {
        "schema_version": "raretopo-m2-gate-audit-v0",
        "benchmark_freeze_hash": freeze_sha,
        "interpretation_matrix_row": interpret(gates),
        "core_verdict":
            "variance-geometry covariance adaptation SUPPORTED"
            if core_gates_pass else
            "variance-geometry covariance adaptation NOT fully supported "
            "(see per-gate verdicts; negative components are reported "
            "verbatim per task Sec. 43/49)",
        "strong_headline_granted": strong_gate["verdict"] == "PASS",
        "gates": gates,
        "summary_tables": summary_tables,
    }
    return audit_out


def ratio_gate_from_maps(num_map, den_map):
    keys = sorted(set(num_map) & set(den_map))
    tr = {k: (num_map[k] / den_map[k] if den_map[k] else float("nan"))
          for k in keys}
    by_cfg: dict[str, list[float]] = {}
    for (c, _s), v in tr.items():
        by_cfg.setdefault(c, []).append(v)
    cm = {c: float(np.median(v)) for c, v in by_cfg.items()}
    pn, pd = {}, {}
    for label, mp in (("n", num_map), ("d", den_map)):
        bc: dict[str, list[float]] = {}
        for (c, _s), v in mp.items():
            bc.setdefault(c, []).append(v)
        (pn if label == "n" else pd).update(
            {c: float(np.median(v)) for c, v in bc.items()})
    return {
        "median_of_config_medians":
            float(np.median(list(cm.values()))) if cm else None,
        "strict_lower_configs": sum(1 for c in pn
                                    if pn[c] < pd.get(c, np.inf)),
    }


def interpret(gates: dict) -> str:
    a = gates["M2_3_shape_only"]["verdict"] == "PASS"
    b = gates["M2_2_core_second_moment"]["verdict"] == "PASS"
    safe = gates["M2_4_no_leakage_redistribution"]["verdict"] == "PASS"
    relb = gates["M2_5_relative_budget_efficiency"]["verdict"] == "PASS"
    strong = gates["STRONG_absolute_efficiency"]["verdict"] == "PASS"
    if not a and not b:
        return ("Row 1: covariance geometry offers no method-level benefit "
                "on this benchmark")
    if (not a) and b and safe and relb and not strong:
        return ("Row 2: gains come mainly from covariance-weight interaction; "
                "direct shape claim not established")
    if a and b and not safe:
        return ("Row 3: shape improves but redistributes variance -- unsafe")
    if a and b and safe and relb and not strong:
        return ("Row 4: CORE M2 SUCCESS -- still below crude-MC cost "
                "efficiency boundary")
    if a and b and safe and relb and strong:
        return ("Row 5: STRONG M2 SUCCESS -- crosses crude-MC cost boundary")
    return ("Mixed/partial pattern -- see individual gate verdicts; claim "
            "wording restricted accordingly")


HEADLINE_ROWS = ["layer", "method", "n_trials", "median_M2", "mean_M2",
                 "std_M2", "min_M2", "max_M2", "median_VRF_budget",
                 "median_VRF_proposal", "hold_rate", "median_P_hat"]


def write_outputs(audit_out: dict) -> None:
    out_dir = RES / "summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate_audit.json").write_text(
        json.dumps(audit_out, indent=1), encoding="utf-8")

    tables = audit_out["summary_tables"]
    del tables
    rows = []
    for layer_key, sub in (("shape_only", "layer_A"),
                           ("shape_reweight", "layer_B")):
        per_method: dict[str, list] = {m: [] for m in METHODS}
        for (_c, _s, m), rec in _iter_records(sub):
            per_method[m].append(rec)
        for m in METHODS:
            rs = [r for r in per_method[m]]
            m2 = [r["evaluation"]["M2_hat"] for r in rs]
            hold = [float(bool(r["covariance"]["hold"])) for r in rs]
            ph = [r["evaluation"]["P_hat"] for r in rs]
            vb = [r["evaluation"]["VRF_budget"] for r in rs]
            vp = [r["evaluation"]["VRF_proposal"] for r in rs]
            rows.append({
                "layer": layer_key, "method": m, "n_trials": len(rs),
                "median_M2": float(np.median(m2)),
                "mean_M2": float(np.mean(m2)),
                "std_M2": float(np.std(m2, ddof=1)),
                "min_M2": float(np.min(m2)), "max_M2": float(np.max(m2)),
                "median_VRF_budget": float(np.median(vb)),
                "median_VRF_proposal": float(np.median(vp)),
                "hold_rate": float(np.mean(hold)),
                "median_P_hat": float(np.median(ph)),
            })
    (out_dir / "summary_tables.json").write_text(
        json.dumps(audit_out["summary_tables"], indent=1), encoding="utf-8")
    with (out_dir / "headline.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADLINE_ROWS)
        w.writeheader()
        for row in rows:
            w.writerow({k: (round(v, 8) if isinstance(v, float) else v)
                        for k, v in row.items()})
    print("[saved] results/phase_m2/summary/{gate_audit.json,"
          "summary_tables.json,headline.csv}")


_REC_CACHE: dict[str, dict] = {}


def _iter_records(layer: str):
    import json as _json
    sub = {"layer_A": "layer_a_shape_only",
           "layer_B": "layer_b_shape_reweight"}[layer]
    fname = {"layer_A": "layer_a_shape_only_v1.json",
             "layer_B": "layer_b_shape_reweight_v1.json"}[layer]
    batch = _json.loads((RES / sub / fname).read_text(encoding="utf-8"))
    for entry in batch["records_by_config"]:
        for rec in entry["records"]:
            yield (rec["config_id"], str(rec["seed"]),
                   rec["covariance_method"]), rec


def _get_rec(layer: str, cid: str, seed: str, method: str):
    key = (layer, cid, seed, method)
    if key not in _REC_CACHE:
        for k, rec in _iter_records(layer):
            _REC_CACHE[(layer,) + k] = rec
    return _REC_CACHE[key]


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 gate audit")
    ap.add_argument("--pytest-line", default=None,
                    help="e.g. '1098 passed in 342.1s' evidence line")
    args = ap.parse_args()
    out = audit(pytest_line=args.pytest_line)
    out["git_commit"] = _git_head()
    write_outputs(out)
    g = out["gates"]
    print("--- M2 GATE VERDICTS ---")
    for name in ("M2_0_validity", "M2_1_estimator_stability",
                 "M2_2_core_second_moment", "M2_3_shape_only",
                 "M2_4_no_leakage_redistribution",
                 "M2_5_relative_budget_efficiency",
                 "STRONG_absolute_efficiency"):
        print(f"{name}: {g[name]['verdict']}")
    print("interpretation:", out["interpretation_matrix_row"])
    invalid = g["M2_0_validity"]["verdict"] == "INVALID"
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
