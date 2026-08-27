"""M3-BV2 controller evaluation (task Sec. 22-25) -- FIRST controller runs
on the frozen BV2 benchmarks, executed only after the benchmark freeze
(commit 2e814a5) and the mandatory-checkpoint approval.

Controllers (frozen, in order of the firewall list):
    ORACLE, ALWAYS_WIDEN, ALWAYS_SHRINK, ALWAYS_HOLD,
    M3-D (raw gradient decision), M3-G-v1 GA1/rho=0.02 (gain gate).

Evaluation protocol (recorded, deterministic; zero new tunables):

  * decision per (state, replicate r): frozen M3-G-v1 confirmatory seeds
    [3031..3038] aligned to replicate r (decision_seed = 3031 + r - 1);
    pilot 20k alpha 0.5 via the frozen draw_online_pilot, gradient +
    bootstrap [seed, 424243] + CI-sign + ESS 20 via the frozen
    gradient_decision; M3-D deploys the raw decision (frozen fold), the
    v1 gate applies apply_gain_gate_v1 (GA1 / rho=0.02 / pilot M2_hat).

  * evaluation of the DECIDED arm on the benchmark-matched replicate
    streams [701001 + idx, 10000 + r] x 100k, 10 batches, reproducing the
    frozen crn_batched_eval draw order (shared comp/eps block per batch) so
    that per-replicate M2 is BIT-IDENTICAL to the frozen characterization
    for the same arm -- this makes the unified functional J exactly
    comparable to the frozen J(BestFixed) / J(Oracle) values.

  * fixed controllers and Oracle use the frozen characterization replicate
    M2 directly (same streams); their J values must reproduce the freeze.

Outputs: results/phase_m3bv2/controller_evaluation.json
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze, ref_views
from hyptraj.m1.baselines import vrf_budget
from hyptraj.m2.covariance_projection import check_legality_frozen
from hyptraj.m3d.adaptation import (
    draw_online_pilot,
    deployed_action,
    gradient_decision,
)
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3g_v1.gain_gate import final_arm_key, apply_gain_gate_v1

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "results" / "phase_m3bv" / "reference" / "m3bv_candidate_pool.json"
STAB = REPO / "results" / "phase_m3bv" / "reference" / \
    "m3bv_headline_stability.json"
DAN = REPO / "results" / "phase_m3bv2" / "decision_analysis.json"
VAN = REPO / "results" / "phase_m3bv2" / "value_analysis.json"
DEST = REPO / "results" / "phase_m3bv2" / "controller_evaluation.json"

ONLINE_CFG = json.loads((REPO / "configs" / "phase_m3d"
                         / "m3d_online_v0.json").read_text(encoding="utf-8"))
V1_PROTO = json.loads((REPO / "configs" / "phase_m3g_v1"
                       / "m3g_v1_protocol.json").read_text(encoding="utf-8"))
SEED_CFG = json.loads((REPO / "configs" / "phase_m3g_v1"
                       / "m3g_v1_confirmatory_seeds.json").read_text(
                           encoding="utf-8"))

PN = int(ONLINE_CFG["protocol_locked"]["pilot_n_per_round"])
EVAL_N = int(ONLINE_CFG["protocol_locked"]["final_eval_n"])
ALPHA = float(ONLINE_CFG["protocol_locked"]["alpha_p"])
RHO = float(V1_PROTO["candidate_locked"]["rho"])
DELTA = 0.20
SV1_DECISION_SEEDS = list(SEED_CFG["confirmatory_seeds"])   # 8 seeds
N_REPS = 8
N_BATCHES = 10
REP_RNG_BASE = 10_000

S2_GRID = [0.65, 0.85, 1.10, 1.40, 1.80, 2.30, 3.00, 4.00, 5.00, 6.40, 8.00]

FIXED_ARM = {"ALWAYS_WIDEN": "widen", "ALWAYS_SHRINK": "shrink",
             "ALWAYS_HOLD": "base"}
REF_ARM = {"WIDEN": "widen", "SHRINK": "shrink", "HOLD": "base"}


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def med(xs):
    return float(statistics.median(xs))


def matched_arm_m2(prop, bench_cfg, rng_key, n_ref: int, n_batches: int,
                   delta_theta: float = DELTA) -> dict:
    """M2 / P / L of ONE arm on a replicated characterization stream.

    Reproduces the frozen crn_batched_eval generator usage exactly: one
    Generator seeded by the full state rng key; per batch ONE shared
    (component choice, standard-normal) block; the requested arm's z is
    computed from that block.  Because the shared block is drawn before any
    arm evaluation in the frozen loop and arm z is a deterministic function
    of (comp, eps, arm cholesky), the M2 is bit-identical to the frozen
    characterization value of that arm on that replicate stream.
    """
    n_b = int(n_ref) // int(n_batches)
    rng = np.random.default_rng(list(rng_key))
    m2b, pb = [], []
    Lmodes = {}
    for _ in range(n_batches):
        comp = rng.choice(prop.n_components, size=n_b, p=prop.weights)
        eps = rng.standard_normal((n_b, prop.centers.shape[1]))
        chols = prop.chols
        z = prop.centers[comp] + np.einsum(
            "njk,nk->nj", np.stack([chols[c] for c in comp]), eps)
        logq = prop.log_density(z)
        lab = bench_cfg.label(z)
        ind = (lab != "NOMINAL").astype(float)
        logp = bench_cfg.logp(z)
        w = np.exp(logp - logq) * ind
        m2b.append(float(np.mean(w ** 2)))
        pb.append(float(np.mean(w)))
        for mid in sorted(set(lab.tolist()) - {"NOMINAL"}):
            Lmodes.setdefault(mid, []).append(float(np.mean((w * (lab == mid)) ** 2)))
    m2 = float(np.mean(m2b))
    p_hat = float(np.mean(pb))
    return {"M2": m2, "P_hat": p_hat, "n_eval": n_ref,
            "L_table": {m: float(np.mean(v)) for m, v in Lmodes.items()}}


def main() -> int:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    stab = json.loads(STAB.read_text(encoding="utf-8"))
    dan = json.loads(DAN.read_text(encoding="utf-8"))
    van = json.loads(VAN.read_text(encoding="utf-8"))

    # ---- union of benchmark states (Axis A 24 + Axis B 24, dedup) --------
    axis = {}
    for fs in dan["freeze_selection"]:
        k = (fs["state_key"]["config_id"], fs["state_key"]["s2"])
        axis.setdefault(k, {"axis": set(), "cls": fs["class"]})
        axis[k]["axis"].add("A")
    for fs in van["freeze_selection"]:
        k = (fs["state_key"]["config_id"], fs["state_key"]["s2"])
        axis.setdefault(k, {"axis": set(), "cls": fs["class"]})
        axis[k]["axis"].add("B")

    sids = {(s["config_id"], s["s2"]): s["state_id"]
            for s in pool["states_legal"]}
    refs = pool["reference_fields"]
    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    cfg_cache = {}

    def bc_of(cid):
        if cid not in cfg_cache:
            cfg_cache[cid] = config_from_record(freeze[cid])
        return cfg_cache[cid]

    def rng_of(key):
        cid, s2 = key
        cfg = bc_of(cid)
        st = assemble_state(cfg, float(s2))
        assert not isinstance(st, dict), f"illegal {key}"
        return st

    # NOTE: idx in the frozen RNG rule is the position in the FULL 88-state
    # (config_id, s2) ascending grid, exactly as in the characterization.
    pool_keys_sorted = sorted((s["config_id"], s["s2"])
                              for s in pool["states_legal"])
    idx_of = {k: i for i, k in enumerate(pool_keys_sorted)}

    states = {}
    t_start = time.perf_counter()
    for (cid, s2), info in sorted(axis.items()):
        st = rng_of((cid, s2))
        props = state_arms(st, DELTA)
        bc = bc_of(cid)
        idx = idx_of[(cid, s2)]
        p_ref = float(sum(ref_views(freeze[cid])["P"].values()))
        st_rec = {"state_key": {"config_id": cid, "s2": s2},
                  "state_id": sids[(cid, s2)],
                  "idx": idx,
                  "axes": sorted(info["axis"]),
                  "class": info["cls"],
                  "oracle_action": refs[f"{cid}|{s2}"]["oracle"][
                      "oracle_action"],
                  "replicates": []}
        st_rep_m2 = stab["entries"][f"{cid}|{s2}"]["replicates"]
        for r in range(1, N_REPS + 1):
            decision_seed = SV1_DECISION_SEEDS[r - 1]
            # frozen decision machinery (pilot + gradient + bootstrap)
            z, logp, logr, strata = draw_online_pilot(st, decision_seed,
                                                      PN, ALPHA)
            gd = gradient_decision(st, decision_seed, z, logp, logr, strata)
            raw = gd["gradient"]["decision"]
            m3d_act = deployed_action(raw)
            # v1 gain gate (verbatim firewall block from run_m3g_v1_online)
            if raw in ("WIDEN", "SHRINK"):
                shift = DELTA if raw == "WIDEN" else -DELTA
                step_cov = (st.s2 * float(np.exp(shift))) * np.eye(st.dim)
                arm_legal, _me = check_legality_frozen(step_cov)
            else:
                arm_legal = True
            gain = apply_gain_gate_v1(
                direction=raw, g_hat=float(gd["gradient"]["g_hat"]),
                m2_pilot=float(gd["gradient"]["M2_hat"]),
                delta_theta=DELTA, rho=RHO, arm_legal=bool(arm_legal))
            v1_act = final_arm_key(gain["final_action"])     # widen/shrink/base
            m3d_arm = {"WIDEN": "widen", "SHRINK": "shrink",
                       "HOLD": "base"}[m3d_act]

            # eval the decided arms on the benchmark-matched stream
            rng_key = [701001 + idx, REP_RNG_BASE + r]
            arm_ev = {}
            for arm in dict.fromkeys((m3d_arm, v1_act)):
                e = matched_arm_m2(props[arm], bc, rng_key, EVAL_N,
                                   N_BATCHES)
                e["VRF_budget"] = vrf_budget(
                    p_mc=p_ref, budget=PN + EVAL_N, m2_hat=e["M2"],
                    p_hat=e["P_hat"], n_eval=EVAL_N)
                arm_ev[arm] = e
            # fixed comparison arms come from the frozen characterization
            base_m2 = float(st_rep_m2[r - 1]["M2"]["base"])
            st_rec["replicates"].append({
                "replicate": r,
                "decision_seed": decision_seed,
                "raw_decision": raw,
                "gain_proxy": gain["gain_proxy"],
                "gain_hold_reason": gain["gain_hold_reason"],
                "m3d_action": m3d_act, "m3d_arm": m3d_arm,
                "v1_action": {"base": "HOLD", "widen": "WIDEN",
                              "shrink": "SHRINK"}[v1_act],
                "v1_arm": v1_act,
                "base_M2_frozen": base_m2,
                "arm_M2": {a: e["M2"] for a, e in arm_ev.items()},
                "arm_P_hat": {a: e["P_hat"] for a, e in arm_ev.items()},
                "arm_VRF_budget": {a: e["VRF_budget"]
                                   for a, e in arm_ev.items()},
            })
        states[f"{cid}|{s2}"] = st_rec
        print(f"[done] {st_rec['state_id']} "
              f"({time.perf_counter() - t_start:.0f}s)", flush=True)

    # ---- J per controller over the 24 Axis-B states -----------------------
    van_keys = sorted({f"{fs['state_key']['config_id']}|"
                       f"{fs['state_key']['s2']}"
                       for fs in van["freeze_selection"]})
    # frozen characterization replicate M2 (the SAME arrays the freeze J was
    # computed from) -- fixed policies and the Oracle must reproduce the
    # frozen J values exactly; only the pilot-based controllers use the new
    # matched-stream evals of their decided arms.
    stored_m2 = {f"{fs['state_key']['config_id']}|{fs['state_key']['s2']}":
                 fs["replicate_M2"] for fs in van["freeze_selection"]}

    def logr_table(key: str, arm_fn, source: str) -> list[float]:
        rec = states[key]
        out = []
        for i, r in enumerate(rec["replicates"]):
            arm = arm_fn(r)
            if source == "stored":
                m2 = stored_m2[key][arm][i]
            else:
                m2 = r["arm_M2"][arm]
            out.append(math.log(m2 / r["base_M2_frozen"]))
        return out

    def J_of(arm_fn, source: str) -> float:
        per_state = [med(logr_table(k, arm_fn, source)) for k in van_keys]
        return med(per_state)

    J = {}
    for f, a in FIXED_ARM.items():
        J[f] = J_of(lambda r, a=a: a, "stored")
    or_cls = {f"{fs['state_key']['config_id']}|{fs['state_key']['s2']}":
              fs["class"] for fs in van["freeze_selection"]}
    per_state_o = [med([
        math.log(stored_m2[k][REF_ARM[or_cls[k]]][i] / r["base_M2_frozen"])
        for i, r in enumerate(states[k]["replicates"])]) for k in van_keys]
    J["ORACLE"] = med(per_state_o)
    J["M3-D"] = J_of(lambda r: {"WIDEN": "widen", "SHRINK": "shrink",
                                "HOLD": "base"}[r["m3d_action"]], "eval")
    J["M3-G-v1"] = J_of(lambda r: r["v1_arm"], "eval")

    uf = van["unified_functional"]
    best_fixed = uf["best_fixed"]
    G_oracle = uf["G_Oracle"]
    G_v1 = J[best_fixed] - J["M3-G-v1"]
    G_m3d = J[best_fixed] - J["M3-D"]
    capture_v1 = G_v1 / G_oracle if G_oracle > 0 else float("nan")
    c1_gate = bool(capture_v1 >= 0.5 and J["M3-G-v1"] < J[best_fixed])

    # ---- Axis A decision correctness --------------------------------------
    def axis_a_metrics(ctrl: str):
        preds = []
        for fs in dan["freeze_selection"]:
            k = f"{fs['state_key']['config_id']}|{fs['state_key']['s2']}"
            label = fs["class"]
            for r in states[k]["replicates"]:
                act = r["v1_action"] if ctrl == "M3-G-v1" else r["m3d_action"]
                preds.append({"label": label, "pred": act})
        classes = ("WIDEN", "HOLD", "SHRINK")
        cm = {t: {p: 0 for p in classes} for t in classes}
        for d in preds:
            cm[d["label"]][d["pred"]] = cm[d["label"]].get(d["pred"], 0) + 1
        recall = {}
        for c in classes:
            tot = sum(cm[c].values())
            recall[c] = cm[c][c] / tot if tot else float("nan")
        bal_acc = float(np.mean(list(recall.values())))
        prec = {}
        for p in classes:
            col = sum(cm[t][p] for t in classes)
            prec[p] = cm[p][p] / col if col else float("nan")
        f1 = {c: (2 * prec[c] * recall[c] / (prec[c] + recall[c])
                  if prec[c] + recall[c] > 0 else float("nan"))
              for c in classes}
        macro_f1 = float(np.mean(list(f1.values())))
        correct = sum(1 for d in preds if d["pred"] == d["label"])
        return {"n_decisions": len(preds),
                "accuracy": correct / len(preds),
                "recall": recall, "balanced_accuracy": bal_acc,
                "precision": prec, "macro_F1": macro_f1,
                "confusion_matrix": cm}

    out = {
        "schema_version": "raretopo-m3bv2-controller-evaluation-v0",
        "document_type": "FIRST controller runs on the frozen M3-BV2 "
                         "benchmarks (task Sec. 22-25); unified functional J "
                         "computed on the benchmark-matched replicate streams",
        "stage": "controller_evaluation",
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "benchmark_freeze_commits": ["2e814a5"],
        "protocol": {
            "decision_seed_rule": "per (state, replicate r): seed = "
                                  "3031 + (r - 1), the frozen M3-G-v1 "
                                  "confirmatory seeds; pilot 20k alpha 0.5; "
                                  "bootstrap [seed, 424243]; CI-sign + ESS "
                                  "20",
            "m3d_deployment": "frozen fold of the raw gradient decision",
            "v1_gate": "GA1 / rho=0.02 / pilot M2_hat denominator / frozen "
                       "legality floor",
            "eval_streams": "benchmark-matched [701001 + idx, 10000 + r] x "
                            "100k x 10 batches, frozen crn_batched_eval draw "
                            "order (bit-identical to the characterization "
                            "streams)",
            "pilot_n": PN, "eval_n": EVAL_N, "alpha_p": ALPHA,
            "call_accounting_deployable_per_trial": PN + EVAL_N,
            "n_replicates": N_REPS,
            "fixed_policies_use_frozen_characterization_streams": True,
        },
        "states": states,
        "axis_b_van_keys": van_keys,
        "J": {k: round(v, 9) for k, v in J.items()},
        "unified_functional": {
            "best_fixed": best_fixed,
            "J_BestFixed": round(J[best_fixed], 9),
            "J_Oracle": round(J["ORACLE"], 9),
            "G_Oracle": round(G_oracle, 9),
            "J_M3-G-v1": round(J["M3-G-v1"], 9),
            "J_M3-D": round(J["M3-D"], 9),
            "G_v1": round(G_v1, 9),
            "G_M3D": round(G_m3d, 9),
            "capture_v1": round(capture_v1, 9),
            "c1_gate_capture_ge_0.5_and_Jv1_lt_Jbf": c1_gate,
        },
        "axis_a": {"M3-D": axis_a_metrics("M3-D"),
                   "M3-G-v1": axis_a_metrics("M3-G-v1")},
        "controller_runs_on_bv2": {
            "unique_state_blocks": len(states),
            "axisA_state_replicate_trials": 24 * N_REPS,
            "axisB_state_replicate_trials": 24 * N_REPS,
        },
        "freeze_records_unchanged": {
            "J_ALWAYS_WIDEN_matches": math.isclose(
                J["ALWAYS_WIDEN"], uf["J"]["ALWAYS_WIDEN"], abs_tol=1e-8),
            "J_ALWAYS_SHRINK_matches": math.isclose(
                J["ALWAYS_SHRINK"], uf["J"]["ALWAYS_SHRINK"], abs_tol=1e-8),
            "J_ALWAYS_HOLD_matches": math.isclose(
                J["ALWAYS_HOLD"], uf["J"]["ALWAYS_HOLD"], abs_tol=1e-8),
            "J_ORACLE_matches": math.isclose(
                J["ORACLE"], uf["J"]["ORACLE"], abs_tol=1e-8),
        },
    }
    DEST.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("J:", json.dumps({k: round(v, 6) for k, v in J.items()}))
    print("G_v1:", round(G_v1, 6), "| capture:", round(capture_v1, 4),
          "| C1 gate:", c1_gate)
    print("Axis A M3-G-v1: acc",
          round(out["axis_a"]["M3-G-v1"]["accuracy"], 4),
          "balanced", round(out["axis_a"]["M3-G-v1"]
                            ["balanced_accuracy"], 4))
    print("controller runs: unique", len(states),
          "| axis-A trials", out["controller_runs_on_bv2"]
          ["axisA_state_replicate_trials"],
          "| axis-B trials", out["controller_runs_on_bv2"]
          ["axisB_state_replicate_trials"])
    print(f"[saved] {DEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())