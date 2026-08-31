"""M3-D D6 -- online Layer A adaptive-value experiment (task Sec. 14-21).

24 frozen states x 8 seeds = 192 paired trials.  The controller is the
FROZEN M3-v0 estimator/policy VERBATIM; Layer A locks fixed weights pi_C0;
three PHYSICAL arms (BASE/WIDEN/SHRINK) are evaluated per trial with matched
CRN ([seed,900001]); every comparator action maps onto these arms:

    GRADIENT      -> widen/shrink arm by CI-sign decision; any HOLD_* -> base
    ALWAYS_WIDEN  -> widen        ALWAYS_SHRINK -> shrink
    ALWAYS_HOLD   -> base         ORACLE_ACTION -> frozen freeze-label arm

Dual call accounting per trial: scientific_audit = 20k + 3x100k;
deployable_method = 20k + 1x100k (chosen GRADIENT action path only).

Output: results/phase_m3d/layer_a/m3d_layer_a_v1.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m1.proposal_update import LEGALITY_MIN_EIG
from hyptraj.m1d.experiments import (
    config_from_record,
    load_freeze,
    ref_views,
)
from hyptraj.m1d.metrics import attach_vrfs, eval_proposal_is
from hyptraj.m2.covariance_policy import evaluate_variant
from hyptraj.m2.covariance_projection import check_legality_frozen
from hyptraj.m3d.adaptation import (
    BOOTSTRAP_SEED_RULE,
    FIXED_RULE_ARM,
    ORACLE_ARM_KEY,
    PILOT_RNG_RULE,
    draw_online_pilot,
    gradient_arm_key,
    gradient_decision,
)
from hyptraj.m3d.benchmark_states import assemble_state, state_arms
from hyptraj.m3d.metrics import build_trial_record, validate_trial_record

REPO = Path(__file__).resolve().parents[1]
FREEZE_DOC = REPO / "docs" / "phase_m3d" / "M3_D_Benchmark_Freeze.json"
ONLINE_CFG = json.loads((REPO / "configs" / "phase_m3d"
                         / "m3d_online_v0.json").read_text(encoding="utf-8"))
DEST = REPO / "results" / "phase_m3d" / "layer_a" / "m3d_layer_a_v1.json"

PN = int(ONLINE_CFG["protocol_locked"]["pilot_n_per_round"])
EVAL_N = int(ONLINE_CFG["protocol_locked"]["final_eval_n"])
ALPHA = float(ONLINE_CFG["protocol_locked"]["alpha_p"])
SEEDS = list(ONLINE_CFG["protocol_locked"]["seeds"])
DELTA = 0.20


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="single state x single seed, eval_n=20000, "
                         "writes preflight file")
    ap.add_argument("--freeze-doc", type=Path, default=FREEZE_DOC)
    ap.add_argument("--dest", type=Path, default=DEST)
    ap.add_argument("--parent-tag", default="RareTopo-M3-v0")
    args = ap.parse_args()
    global PN, EVAL_N
    if args.smoke:
        EVAL_N = 20_000

    freeze_path = args.freeze_doc.resolve()
    freeze_doc = json.loads(freeze_path.read_text(encoding="utf-8"))
    body = {k: v for k, v in freeze_doc.items()
            if k != "freeze_sha256_of_body_above"}
    assert hashlib.sha256(json.dumps(body, indent=1).encode()).hexdigest() \
        == freeze_doc["freeze_sha256_of_body_above"], "freeze doc tampered!"

    bench_cache = {r["config_id"]: r
                   for r in load_freeze()["benchmark_configs"]}
    frec = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}

    state_iter = freeze_doc["states"][:1] if args.smoke \
        else freeze_doc["states"]
    seed_iter = SEEDS[:1] if args.smoke else SEEDS

    records = []
    t_start = time.perf_counter()
    for s_rec in state_iter:
        cid = s_rec["config_id"]
        bc = config_from_record(bench_cache[cid])
        st = assemble_state(bc, float(s_rec["s2"]))
        assert not isinstance(st, dict), f"state illegal: {s_rec}"
        rv = ref_views(frec[cid])
        p_ref = float(sum(rv["P"].values()))

        for seed in seed_iter:
            t0 = time.perf_counter()
            z, logp, logr, strata = draw_online_pilot(st, int(seed),
                                                      PN, ALPHA)
            gd = gradient_decision(st, int(seed), z, logp, logr, strata)
            raw = gd["gradient"]["decision"]
            deployed = ("WIDEN" if raw == "WIDEN"
                        else "SHRINK" if raw == "SHRINK" else "HOLD")
            g_arm = gradient_arm_key(raw)

            props = state_arms(st, DELTA)
            k = st.component_index
            ev, legality_flags = {}, {}
            for name in ("base", "widen", "shrink"):
                # evaluate_variant is a 1-line delegate of this frozen call;
                # called directly because BenchmarkState is seed-less by
                # design (the anchor mixture), while CRN seeding comes from
                # the ONLINE (state, seed) pair here.
                e = eval_proposal_is(props[name], bc, int(seed),
                                     n_eval=EVAL_N)
                attach_vrfs(e, p_ref=p_ref, budget_total=PN + EVAL_N)
                ev[name] = e
                okl, _me = check_legality_frozen(props[name].covs[k])
                legality_flags[name] = bool(okl)

            def A2(arm_key):
                return {"M2": float(ev[arm_key]["M2_hat"]),
                        "mode_L": {m: float(x) for m, x
                                   in ev[arm_key]["L_table"].items()}}

            oracle_action = s_rec["oracle_action"]
            o_arm = ORACLE_ARM_KEY[oracle_action]
            grad_M2 = ev[g_arm]["M2_hat"]
            oracle_M2 = ev[o_arm]["M2_hat"]
            regret = ((grad_M2 - oracle_M2) / oracle_M2
                      if oracle_M2 else float("nan"))

            rec = build_trial_record(
                config_id=cid, state_id=s_rec["state_id"],
                seed=int(seed), base_s2=float(s_rec["s2"]),
                oracle_action=oracle_action,
                oracle_direction_margin=float(
                    s_rec["direction_margin_Delta_dir"]),
                gradient_block={
                    "g_hat": gd["gradient"]["g_hat"],
                    "g_ci_low": gd["gradient"]["g_ci_low"],
                    "g_ci_high": gd["gradient"]["g_ci_high"],
                    "ESS_grad": gd["gradient"]["ESS_grad"],
                    "action": raw},
                arms_block={"hold": A2("base"), "widen": A2("widen"),
                            "shrink": A2("shrink"), "gradient": A2(g_arm),
                            "oracle": A2(o_arm)},
                metrics_block={
                    "action_correct": bool(deployed == oracle_action),
                    "regret_M2": regret,
                    "VRF_proposal": float(ev[g_arm]["VRF_proposal"]),
                    "VRF_budget": float(ev[g_arm]["VRF_budget"])},
                validity_block={
                    "raw_decision_code": raw,
                    "deployed_action": deployed,
                    "gradient_mapped_arm": g_arm,
                    "always_widen_mapped_arm": FIXED_RULE_ARM["ALWAYS_WIDEN"],
                    "arm_legality_all_passed":
                        bool(all(legality_flags.values())),
                    "legality_min_eig_frozen": float(LEGALITY_MIN_EIG),
                    "scientific_audit_calls": PN + 3 * EVAL_N,
                    "deployable_method_calls": PN + EVAL_N,
                    "bootstrap_seed_rule": BOOTSTRAP_SEED_RULE,
                    "pilot_rng_rule": PILOT_RNG_RULE,
                    "eval_rng_tag": 900001,
                    "_runtime_s": round(time.perf_counter() - t0, 3)})
            assert validate_trial_record(rec), f"schema fail {s_rec['state_id']}"
            records.append(rec)
        print(f"[done] {s_rec['state_id']} "
              f"({time.perf_counter() - t_start:.0f}s elapsed)", flush=True)

    batch = {
        "schema_version": "raretopo-m3d-layer-a-batch-v0",
        "record_schema_version": "raretopo-m3d-v0",
        "stage": "D6_layer_a" + ("_SMOKE" if args.smoke else ""),
        "benchmark_freeze_sha256":
            freeze_doc["freeze_sha256_of_body_above"],
        "m3v0_parent_tag": args.parent_tag,
        "m3v0_frozen_head": subprocess.run(
            ["git", "rev-parse", f"{args.parent_tag}^{{commit}}"], cwd=REPO,
            check=True, capture_output=True, text=True).stdout.strip(),
        "git_commit": _git(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "protocol": {"n_states": 24, "seeds": SEEDS, "n_pilot": PN,
                     "alpha_p": ALPHA, "n_eval": EVAL_N,
                     "eval_rng_tag": 900001, "delta_theta_main": DELTA,
                     "ess_min": 20.0,
                     "comparators": ["GRADIENT", "ALWAYS_WIDEN",
                                     "ALWAYS_SHRINK", "ALWAYS_HOLD"],
                     "call_accounting": {
                         "scientific_audit_calls_per_trial":
                             PN + 3 * EVAL_N,
                         "deployable_method_calls_per_trial": PN + EVAL_N}},
        "event_semantics": {
            "schema_version": 2,
            "event_definition_id": "topology-label-non-nominal-v1",
            "event_predicate_source": "hyptraj.event_semantics.event_indicator_from_topology",
        },
        "evidence_repair": {
            "repair_id": "ER-1",
            "run_kind": "isolated_corrected_replay",
            "repair_simulator_calls": len(records) * (PN + 3 * EVAL_N),
            "seed_reuse_status": "EXACT",
            "draw_order_status": "EXACT",
        },
        "records": records,
    }
    dest = (args.dest.parent / "m3d_layer_a_smoke.json"
            if args.smoke else args.dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    print(f"[saved] {dest.relative_to(REPO)} -- {len(records)} trials "
          f"in {time.perf_counter() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
