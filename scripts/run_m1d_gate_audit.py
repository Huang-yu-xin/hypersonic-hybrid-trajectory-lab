"""M1-D -- gate audit + hierarchical aggregation (task Sec. 24 / 35 / 36).

Reads the frozen benchmark set plus every experiment batch artifact and
produces, under results/phase_m1d/summary/:

    gate_audit.json     all preregistered gate verdicts + evidence
    summary_tables.json compact per-(config, method) aggregates
    headline.csv        one row per method × birth_budget key metrics
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "phase_m1d"
FREEZE_JSON = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"
SEEDS = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]

METHOD_ORDER = ["probability_selector", "variance_selector",
                "random_selector", "oracle_P", "oracle_V",
                "probability_full_policy", "variance_full_policy"]


def _boot_median_ci(v, boots=2000, seed=20260827):
    a = np.asarray(v, float)
    if a.size < 2:
        m = float(np.median(a)) if a.size else float("nan")
        return [m, m]
    rng = np.random.default_rng(seed)
    s = np.median(a[rng.integers(0, a.size, size=(boots, a.size))], axis=1)
    return [float(x) for x in np.quantile(s, [0.025, 0.975])]


def _load_batch(path: Path):
    if not path.exists():
        raise SystemExit(f"[audit] missing batch artifact {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _trials(batch):
    for cb in batch["records_by_config"]:
        for rec in cb["records"]:
            yield cb["config_id"], rec


def main() -> int:
    t0 = datetime.now(timezone.utc)
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    frozen_ids = [c["config_id"] for c in freeze["benchmark_configs"]]
    free_sha = hashlib.sha256(FREEZE_JSON.read_bytes()).hexdigest()

    b_d1a = _load_batch(RESULTS / "d1_selection_only" /
                        "layer_a_one_birth_v1.json")
    b_d1b = _load_batch(RESULTS / "d1_full_policy" /
                        "layer_b_one_birth_v1.json")
    b_d2a = _load_batch(RESULTS / "d2_two_birth" /
                        "layer_a_two_birth_v1.json")
    b_d2b = _load_batch(RESULTS / "d2_two_birth" /
                        "layer_b_two_birth_v1.json")

    def index(batch):
        idx = {}
        for cid, r in _trials(batch):
            idx[(cid, r["seed"], r["method"])] = r
        return idx

    I_d1a, I_d1b = index(b_d1a), index(b_d1b)
    I_d2a, I_d2b = index(b_d2a), index(b_d2b)

    methods_a = sorted({r["method"] for _, r in _trials(b_d1a)})
    methods_ab = ["variance_full_policy", "probability_full_policy"]

    # ---------------- per-trial flattening --------------------------------
    flat = defaultdict(dict)
    for name, idx in (("d1a", I_d1a), ("d1b", I_d1b), ("d2a", I_d2a),
                      ("d2b", I_d2b)):
        for (cid, sd, m), r in idx.items():
            sm = r["selection_metrics"]
            ev = r["evaluation"]
            flat[(name, m)][(cid, sd)] = {
                "top1": int(bool(sm.get("top1_variance_correct"))),
                "CVS1": float(sm.get("captured_variance_share", np.nan)),
                "CPS1": float(sm.get("captured_probability_share", np.nan)),
                "M2": float(ev["M2_hat"]),
                "VRFp": float(ev["VRF_proposal"]),
                "VRFb": float(ev["VRF_budget"]),
                "selected": r.get("selected_modes", []),
            }
            if name in ("d2a", "d2b"):
                flat[(name, m)][(cid, sd)]["CVS2"] = float(
                    sm.get("captured_variance_share", np.nan))
                c2 = sm.get("CVS_2") or sm.get("captured_variance_share")
                flat[(name, m)][(cid, sd)]["CVS2"] = float(c2)

    # ---------------- hierarchical helpers --------------------------------
    def series(source, method, metric):
        return {(cid, sd): v[metric]
                for (cid, sd), v in flat[(source, method)].items()}

    def aggregate(vals_by_key):
        vals = list(vals_by_key.values())
        per_cfg = defaultdict(list)
        for (cid, _), v in vals_by_key.items():
            per_cfg[cid].append(float(v))
        return {
            "n_trials": len(vals),
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals, ddof=1)),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
            "median_global": float(np.median(vals)),
            "per_config_median": {cid: float(np.median(v))
                                  for cid, v in sorted(per_cfg.items())},
            "median_of_config_medians":
                float(np.median([np.median(v)
                                 for v in per_cfg.values()])),
        }

    # ---------------- Gates -------------------------------------------------
    gates: dict = {}

    # ---- Gate D0 validity
    adapt_ts = min(_load_meta(x)["timestamp_utc"] for x in
                   (RESULTS / "d1_selection_only" / "layer_a_one_birth_v1.json",))
    gates["D0_validity"] = {
        "freeze_before_adaptive_runs": bool(freeze["frozen_at_utc"] < adapt_ts),
        "freeze_hash_matches_batches": all(
            _load_meta(p)["benchmark_freeze_hash"] == free_sha for p in (
                RESULTS / "d1_selection_only" / "layer_a_one_birth_v1.json",
                RESULTS / "d1_full_policy" / "layer_b_one_birth_v1.json",
                RESULTS / "d2_two_birth" / "layer_a_two_birth_v1.json",
                RESULTS / "d2_two_birth" / "layer_b_two_birth_v1.json")),
        "n_configs_frozen": len(frozen_ids),
        "pytest_note": "pytest suites green at commit f127858 (see report)",
        "pass": None,
    }
    g0_ok = gates["D0_validity"]["freeze_before_adaptive_runs"] \
        and gates["D0_validity"]["freeze_hash_matches_batches"] \
        and len(frozen_ids) == 8 \
        and all(set(methods_a) == {"probability_selector", "variance_selector",
                                   "random_selector", "oracle_P", "oracle_V"}
                for _ in [0])
    gates["D0_validity"]["pass"] = bool(g0_ok)

    # completeness: each (config,seed) present per method in d1a
    missing_pairs = [(cid, sd, m)
                     for m in methods_a
                     for cid in frozen_ids
                     for sd in SEEDS if (cid, sd, m) not in I_d1a]
    gates["D0_validity"]["missing_trial_cells_d1a"] = missing_pairs
    gates["D0_validity"]["pass"] = bool(g0_ok and not missing_pairs)

    # ---- Gate D1 conflict (recompute from freeze records)
    e_rows = [c["eligibility"] for c in freeze["benchmark_configs"]]
    gates["D1_conflict"] = {
        "n_configs_top_conflict": sum(e["E3_top_rank_conflict"] for e in e_rows),
        "n_configs_strong_inversion": sum(e["E4_strong_inversion"] for e in e_rows),
        "pass": all(e["E3_top_rank_conflict"] and e["E4_strong_inversion"]
                    for e in e_rows) and len(e_rows) == 8,
    }

    # ---- Gate D2 selection advantage (Layer A)
    accv_v = aggregate(series("d1a", "variance_selector", "top1"))
    accv_p = aggregate(series("d1a", "probability_selector", "top1"))
    acc_gap = accv_v["mean"] - accv_p["mean"]
    gates["D2_selection_advantage"] = {
        "Acc_V@1_variance": accv_v,
        "Acc@1_probability": accv_p,
        "acc_gap_pp": acc_gap * 100,
        "thresholds": {"acc_var_ge": 0.75, "gap_ge_pp": 25.0},
        "pass": bool(accv_v["mean"] >= 0.75 and acc_gap >= 0.25),
    }

    # ---- Gate D3 captured variance advantage
    def ratio_metric(num_m, den_m, metric, source="d1a"):
        num = series(source, num_m, metric)
        den = series(source, den_m, metric)
        keys = sorted(set(num) & set(den))
        return [float(num[k]) / max(float(den[k]), 1e-300) for k in keys], keys

    cvs_ratio_vals, keys_c = ratio_metric("variance_selector",
                                          "probability_selector", "CVS1")
    gates["D3_captured_variance"] = {
        "CVS1_variance_median": float(np.median(
            list(series("d1a", "variance_selector", "CVS1").values()))),
        "CVS1_probability_median": float(np.median(
            list(series("d1a", "probability_selector", "CVS1").values()))),
        "median_CVS_ratio_V_over_P": float(np.median(cvs_ratio_vals)),
        "ratio_ci95": _boot_median_ci(cvs_ratio_vals),
        "thresholds": {"strictly_greater": True, "ratio_ge": 1.25},
        "pass": None,
    }
    gates["D3_captured_variance"]["pass"] = bool(
        gates["D3_captured_variance"]["CVS1_variance_median"] >
        gates["D3_captured_variance"]["CVS1_probability_median"] and
        gates["D3_captured_variance"]["median_CVS_ratio_V_over_P"] >= 1.25)

    # ---- Gate D4 selection converts to M2 gain (Layer A)
    m2_ratio_vp, _k4 = ratio_metric("variance_selector", "probability_selector",
                                    "M2")
    gates["D4_m2_gain_layerA"] = {
        "median_M2_ratio_VarSel_over_ProbSel": float(np.median(m2_ratio_vp)),
        "ci95": _boot_median_ci(m2_ratio_vp),
        "threshold_le": 0.90,
        "pass": bool(np.median(m2_ratio_vp) <= 0.90),
    }

    # ---- Gate D5 near-oracle
    m2_ratio_vo, _k5 = ratio_metric("variance_selector", "oracle_V", "M2")
    gates["D5_near_oracle"] = {
        "median_M2_ratio_VarSel_over_OracleV": float(np.median(m2_ratio_vo)),
        "ci95": _boot_median_ci(m2_ratio_vo),
        "threshold_le": 1.10,
        "pass": bool(np.median(m2_ratio_vo) <= 1.10),
    }

    # ---- Gate D6 full-policy advantage
    m2_ratio_fb, _k6 = ratio_metric("variance_full_policy",
                                    "probability_full_policy", "M2", "d1b")
    vrf_v = list(series("d1b", "variance_full_policy", "VRFb").values())
    vrf_p = list(series("d1b", "probability_full_policy", "VRFb").values())
    gates["D6_full_policy"] = {
        "median_M2_ratio_M1Var_over_ProbFull": float(np.median(m2_ratio_fb)),
        "ci95": _boot_median_ci(m2_ratio_fb),
        "median_VRFbudget_M1Var": float(np.median(vrf_v)),
        "median_VRFbudget_ProbFull": float(np.median(vrf_p)),
        "thresholds": {"m2_ratio_le": 0.90, "vrf_median_greater": True},
        "pass": bool(np.median(m2_ratio_fb) <= 0.90
                     and np.median(vrf_v) > np.median(vrf_p)),
    }

    # ---------------- method summary table ---------------------------------
    summary = {}
    for src, tag in (("d1a", "B1"), ("d1b", "B1"), ("d2a", "B2"),
                     ("d2b", "B2")):
        src_methods = sorted({mm for (nn, mm) in list(flat.keys())
                              if nn == src})
        for m in src_methods:
            keyset = flat[(src, m)]
            if not keyset:
                continue
            entry = {}
            metrics_here = ["top1", "CVS1", "CPS1", "M2", "VRFp", "VRFb"]
            if src.startswith("d2"):
                metrics_here.append("CVS2")
            for metric in metrics_here:
                vals = {k: v[metric] for k, v in keyset.items()
                        if metric in v}
                if not vals:
                    continue
                entry[metric] = aggregate(vals)
            summary[f"{src}:{tag}:{m}"] = entry

    # selection regret vs Oracle-V (Layer A one-birth, Sec. 23)
    reg = {}
    o_m2 = series("d1a", "oracle_V", "M2")
    o_cvs = series("d1a", "oracle_V", "CVS1")
    for m in ("variance_selector", "probability_selector", "random_selector",
              "oracle_P"):
        mm = series("d1a", m, "M2")
        cc = series("d1a", m, "CVS1")
        keys = sorted(set(mm) & set(o_m2))
        reg[m] = {
            "R_M2_median": float(np.median([mm[k] / max(o_m2[k], 1e-300) - 1
                                            for k in keys])),
            "R_CVS_median": float(np.median([1 - cc[k] / max(o_cvs[k], 1e-300)
                                             for k in keys])),
        }
    gates["_regret_vs_oracleV_layerA"] = reg

    # Ablation D-C / D-D contrasts (variance selector + probability selector,
    # cell minus main, paired by (config, seed))
    abl = {}
    for cell_file, cell_tag in (("center_variance_hdr_v1.json", "D-C_hdr_center"),
                                ("weight_probability_v1.json", "D-D_prob_weights")):
        path = RESULTS / "ablations" / cell_file
        if not path.exists():
            continue
        batch = json.loads(path.read_text(encoding="utf-8"))
        out_cell = {}
        for cb in batch["records_by_config"]:
            for r in cb["records"]:
                out_cell[(cb["config_id"], int(r["seed"]), r["method"])] = r
        per_method = {}
        for m in ("variance_selector", "probability_selector"):
            main_keys = flat[("d1a", m)]
            d_m2, d_cvs = [], []
            flips = 0
            n_cmp = 0
            for k, r in sorted(out_cell.items()):
                if k[2] != m:                    # restrict to THIS method
                    continue
                kk = (k[0], k[1])
                if kk not in main_keys:
                    continue
                n_cmp += 1
                base_sel = list(main_keys[kk]["selected"])
                cell_sel = list(r.get("selected_modes", []))
                if base_sel != cell_sel:
                    flips += 1
                ev = r["evaluation"]
                evb = main_keys[kk]
                d_m2.append(ev["M2_hat"] - evb["M2"])
                d_cvs.append(r["selection_metrics"]["captured_variance_share"]
                             - evb["CVS1"])
            per_method[m] = {"n_paired": n_cmp,
                             "median_dM2_vs_main": float(np.median(d_m2)),
                             "median_dCVS_vs_main": float(np.median(d_cvs)),
                             "selection_flips_when_signal_fixed": flips}
        abl[cell_tag] = per_method
    gates["_ablation_tables_DC_DD"] = abl

    # D-E contrast (B1 -> B2): does probability close the gap?
    de = {}
    for layer, src1, src2 in (("A", "d1a", "d2a"), ("B", "d1b", "d2b")):
        cols = {}
        for m in ((["variance_selector", "probability_selector"]
                   if layer == "A" else methods_ab)):
            m2_1 = np.median(list(series(src1, m, "M2").values()))
            m2_2 = np.nanmedian([series(src2, m, "M2")[k]
                                 for k in series(src1, m, "M2")
                                 if k in series(src2, m, "M2")] or [np.nan])
            cvs_1 = np.median(list(series(src1, m, "CVS1").values()))
            cvs_2 = np.nanmedian([series(src2, m, "CVS1")[k]
                                  for k in series(src1, m, "CVS1")
                                  if k in series(src2, m, "CVS1")] or [np.nan])
            cols[m] = {"median_M2_B1": m2_1, "median_M2_B2": m2_2,
                       "median_CVS_B1": cvs_1, "median_CVS_B2": cvs_2}
        if len(cols) == 2:
            vm, pm = list(cols.values())
            de[f"layer_{layer}_gap_M2_B1"] = vm["median_M2_B1"] - pm["median_M2_B1"]
            de[f"layer_{layer}_gap_M2_B2"] = vm["median_M2_B2"] - pm["median_M2_B2"]
        de.update(cols)
    gates["_ablation_DE_budget_contrast"] = de

    # ---------------- persist ------------------------------------------------
    SUM = RESULTS / "summary"
    SUM.mkdir(parents=True, exist_ok=True)
    (SUM / "gate_audit.json").write_text(
        json.dumps({"generated_utc": t0.isoformat(timespec="seconds"),
                    "freeze_sha256": free_sha,
                    "headline_gates": {k: gates[k] for k in
                                       ("D0_validity", "D1_conflict",
                                        "D2_selection_advantage",
                                        "D3_captured_variance",
                                        "D4_m2_gain_layerA", "D5_near_oracle",
                                        "D6_full_policy")},
                    **gates}, indent=1), encoding="utf-8")

    # compact csv headline
    import csv
    with (SUM / "headline.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "birth_tag", "method", "n", "Acc_top1_mean",
                    "median_CVS1", "median_CPS1", "median_M2",
                    "median_VRF_prop", "median_VRF_budget",
                    "median_of_cfgMedians_M2"])
        for key, e in summary.items():
            src, tag, m = key.split(":", 2)
            w.writerow([src, tag, m, e["top1"]["n_trials"],
                        round(e["top1"]["mean"], 4),
                        round(e["CVS1"]["median_global"], 5),
                        round(e["CPS1"]["median_global"], 5),
                        round(e["M2"]["median_global"], 6),
                        round(e["VRFp"]["median_global"], 4),
                        round(e["VRFb"]["median_global"], 4),
                        round(e["M2"]["median_of_config_medians"], 6)])
    (SUM / "summary_tables.json").write_text(json.dumps(summary, indent=1),
                                             encoding="utf-8")

    # stdout verdict
    print("=" * 62)
    verdicts = {k: gates[k] for k in
                ("D0_validity", "D1_conflict", "D2_selection_advantage",
                 "D3_captured_variance", "D4_m2_gain_layerA",
                 "D5_near_oracle", "D6_full_policy")}
    for k, v in verdicts.items():
        print(f"{k:26s}: {'PASS' if v['pass'] else 'FAIL'}")
    print("=" * 62)
    dv = gates["D2_selection_advantage"]
    print(f"D2 details: AccV={dv['Acc_V@1_variance']['mean']:.3f} "
          f"AccP={dv['Acc@1_probability']['mean']:.3f} "
          f"gap={dv['acc_gap_pp']:.1f}pp")
    print(f"D3: medianCVS V={gates['D3_captured_variance']['CVS1_variance_median']:.4f} "
          f"P={gates['D3_captured_variance']['CVS1_probability_median']:.4f} "
          f"ratio={gates['D3_captured_variance']['median_CVS_ratio_V_over_P']:.3f}")
    print(f"D4 ratio={gates['D4_m2_gain_layerA']['median_M2_ratio_VarSel_over_ProbSel']:.4f}"
          f"  D5 ratio={gates['D5_near_oracle']['median_M2_ratio_VarSel_over_OracleV']:.4f}")
    print(f"D6 ratio={gates['D6_full_policy']['median_M2_ratio_M1Var_over_ProbFull']:.4f}"
          f" VRFb(M1/P)="
          f"{gates['D6_full_policy']['median_VRFbudget_M1Var']:.2f}/"
          f"{gates['D6_full_policy']['median_VRFbudget_ProbFull']:.2f}")
    return 0


def _load_meta(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
