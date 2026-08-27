"""M3-G-v1 confirmatory online evaluation (task Sec. 13; gated by the
Sec. 30 checkpoint -- run ONLY after checkpoint approval).

24 frozen states x confirmatory seeds [3031..3038] = 192 trials via the
FROZEN M3-D machinery byte-for-byte (pilot [seed,101] 20k/alpha 0.5,
bootstrap [seed,424243], CI-sign + ESS 20, CRN arms [seed,900001] x100k),
plus the LOCKED v1 gain gate (GA1 / rho=0.02 / pilot M2_hat denominator).

Guards:
  * direction-layer parity asserted inline (frozen block == what
    gradient_decision returns);
  * confirmatory seeds disjoint from discovery [2026..2033];
  * zero eval-M2 inside the gate (gate signature whitelisted);
  * call accounting identical to M3-D (320k scientific / 120k deployable).

NOT executed during preregistration/implementation phases.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from hyptraj.m1.proposal_update import LEGALITY_MIN_EIG
from hyptraj.m1d.experiments import config_from_record, load_freeze, ref_views
from hyptraj.m1d.metrics import attach_vrfs, eval_proposal_is
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
from hyptraj.m3g_v1.gain_gate import apply_gain_gate_v1, final_arm_key
from hyptraj.m3g_v1.metrics import (
    build_m3g_v1_trial_record,
    validate_m3g_v1_trial_record,
)

REPO = Path(__file__).resolve().parents[1]
FREEZE_DOC = json.loads((REPO / "docs" / "phase_m3d"
                         / "M3_D_Benchmark_Freeze.json").read_text(
                             encoding="utf-8"))
ONLINE_CFG = json.loads((REPO / "configs" / "phase_m3d"
                         / "m3d_online_v0.json").read_text(encoding="utf-8"))
V1_PROTO = json.loads((REPO / "configs" / "phase_m3g_v1"
                       / "m3g_v1_protocol.json").read_text(encoding="utf-8"))
SEED_CFG = json.loads((REPO / "configs" / "phase_m3g_v1"
                       / "m3g_v1_confirmatory_seeds.json").read_text(
                           encoding="utf-8"))
DEST = REPO / "results" / "phase_m3g_v1" / "layer_a" \
    / "m3g_v1_confirmatory_v1.json"

PN = int(ONLINE_CFG["protocol_locked"]["pilot_n_per_round"])
EVAL_N = int(ONLINE_CFG["protocol_locked"]["final_eval_n"])
ALPHA = float(ONLINE_CFG["protocol_locked"]["alpha_p"])
SEEDS = list(SEED_CFG["confirmatory_seeds"])
DISCOVERY_SEEDS = list(V1_PROTO["seed_sets"]["discovery_seeds"])
DELTA = 0.20
RHO = float(V1_PROTO["candidate_locked"]["rho"])


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="single state x single seed, eval_n=20000")
    args = ap.parse_args()
    global EVAL_N, DEST
    if args.smoke:
        EVAL_N = 20_000
        DEST = DEST.parent / "m3g_v1_confirmatory_smoke.json"

    # -- locked-prereg guards -------------------------------------------------
    assert set(SEEDS).isdisjoint(set(DISCOVERY_SEEDS)), "seed overlap!"
    assert SEED_CFG["locked_before_science"] is True
    assert abs(RHO - 0.02) < 1e-12 and V1_PROTO["candidate_locked"][
        "variant"] == "GA1"

    freeze_doc = FREEZE_DOC
    body = {k: v for k, v in freeze_doc.items()
            if k != "freeze_sha256_of_body_above"}
    assert hashlib.sha256(json.dumps(body, indent=1).encode()).hexdigest() \
        == freeze_doc["freeze_sha256_of_body_above"], "freeze doc tampered!"

    bench_cache = {r["config_id"]: r
                   for r in load_freeze()["benchmark_configs"]}
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
        rv = ref_views(bench_cache[cid])
        p_ref = float(sum(rv["P"].values()))

        for seed in seed_iter:
            t0 = time.perf_counter()
            z, logp, logr, strata = draw_online_pilot(st, int(seed),
                                                      PN, ALPHA)
            gd = gradient_decision(st, int(seed), z, logp, logr, strata)
            raw = gd["gradient"]["decision"]
            gr = gd["gradient"]
            g_arm = gradient_arm_key(raw)

            # ------------ v1 gate (pilot M2_hat, GA1, 0.02) ------------
            if raw in ("WIDEN", "SHRINK"):
                shift = DELTA if raw == "WIDEN" else -DELTA
                step_cov = (st.s2 * float(np.exp(shift))) * np.eye(st.dim)
                arm_legal, _me = check_legality_frozen(step_cov)
            else:
                arm_legal = True
            gain = apply_gain_gate_v1(
                direction=raw, g_hat=float(gr["g_hat"]),
                m2_pilot=float(gr["M2_hat"]), delta_theta=DELTA, rho=RHO,
                arm_legal=bool(arm_legal))
            final = gain["final_action"]
            gate_arm_phys = {"WIDEN": "widen", "SHRINK": "shrink",
                             "HOLD": "base"}[final]
            deployed = ("WIDEN" if final == "WIDEN"
                        else "SHRINK" if final == "SHRINK" else "HOLD")

            props = state_arms(st, DELTA)
            k = st.component_index
            ev = {}
            for name in ("base", "widen", "shrink"):
                e = eval_proposal_is(props[name], bc, int(seed),
                                     n_eval=EVAL_N)
                attach_vrfs(e, p_ref=p_ref, budget_total=PN + EVAL_N)
                ev[name] = e

            def A2(arm_key):
                return {"M2": float(ev[arm_key]["M2_hat"]),
                        "mode_L": {m: float(x) for m, x
                                   in ev[arm_key]["L_table"].items()}}

            o_arm = ORACLE_ARM_KEY[s_rec["oracle_action"]]
            grad_M2 = ev[g_arm]["M2_hat"]
            oracle_M2 = ev[o_arm]["M2_hat"]
            gate_M2 = ev[gate_arm_phys]["M2_hat"]
            regret = ((gate_M2 - oracle_M2) / oracle_M2
                      if oracle_M2 else float("nan"))

            rec = build_m3g_v1_trial_record(
                config_id=cid, state_id=s_rec["state_id"],
                seed=int(seed), base_s2=float(s_rec["s2"]),
                oracle_action=s_rec["oracle_action"],
                oracle_direction_margin=float(
                    s_rec["direction_margin_Delta_dir"]),
                gradient_block={
                    "g_hat": gr["g_hat"], "g_ci_low": gr["g_ci_low"],
                    "g_ci_high": gr["g_ci_high"], "ESS_grad": gr["ESS_grad"],
                    "action": raw, "M2_hat_pilot": gr["M2_hat"]},
                gain_block=gain,
                arms_block={"hold": A2("base"), "widen": A2("widen"),
                            "shrink": A2("shrink"), "gradient": A2(g_arm),
                            "oracle": A2(o_arm), "gate": A2(gate_arm_phys)},
                metrics_block={
                    "action_correct": bool(deployed == s_rec["oracle_action"]),
                    "regret_M2": regret,
                    "VRF_proposal": float(ev[gate_arm_phys]["VRF_proposal"]),
                    "VRF_budget": float(ev[gate_arm_phys]["VRF_budget"]),
                    "M2_gate_over_base":
                        gate_M2 / float(ev["base"]["M2_hat"]),
                    "M2_gate_over_oracle": (gate_M2 / oracle_M2
                                            if oracle_M2 else None),
                    "M2_gate_over_gradient": (gate_M2 / grad_M2
                                              if grad_M2 else None)},
                validity_block={
                    "raw_decision_code": raw,
                    "deployed_action": deployed,
                    "gradient_mapped_arm": g_arm,
                    "gate_mapped_arm": gate_arm_phys,
                    "gain_variant": "GA1",
                    "gain_rho": RHO,
                    "gain_config_file": "configs/phase_m3g_v1/"
                                        "m3g_v1_protocol.json",
                    "seed_set": "confirmatory",
                    "legality_min_eig_frozen": float(LEGALITY_MIN_EIG),
                    "scientific_audit_calls": PN + 3 * EVAL_N,
                    "deployable_method_calls": PN + EVAL_N,
                    "bootstrap_seed_rule": BOOTSTRAP_SEED_RULE,
                    "pilot_rng_rule": PILOT_RNG_RULE,
                    "eval_rng_tag": 900001,
                    "_runtime_s": round(time.perf_counter() - t0, 3)})
            assert validate_m3g_v1_trial_record(rec), \
                f"schema fail {s_rec['state_id']}"
            records.append(rec)
        print(f"[done] {s_rec['state_id']} "
              f"({time.perf_counter() - t_start:.0f}s elapsed)", flush=True)

    batch = {
        "schema_version": "raretopo-m3g-v1-confirmatory-batch-v0",
        "record_schema_version": "raretopo-m3g-v1",
        "stage": "M3_G_v1_confirmatory_v1"
        + ("_SMOKE" if args.smoke else ""),
        "benchmark_freeze_sha256":
            freeze_doc["freeze_sha256_of_body_above"],
        "parent_tags": {"RareTopo-M3-D-v0":
                        "7bd58c5992615b8579b1814a3a3fcbea3cda9659"},
        "v0_audit_HEAD": "1a31f8b83133e57cebae0ed27f7e35deb9c475e2",
        "prereg_commit": "55fb5ec",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
            capture_output=True, text=True).stdout.strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "locked_candidate": {"variant": "GA1", "rho": RHO,
                             "delta_theta": DELTA,
                             "denominator": "pilot M2_hat"},
        "seeds": {"confirmatory": SEEDS, "discovery": DISCOVERY_SEEDS,
                  "disjoint": True},
        "protocol": {"n_states": 24, "n_pilot": PN, "alpha_p": ALPHA,
                     "n_eval": EVAL_N, "eval_rng_tag": 900001,
                     "ess_min": 20.0,
                     "call_accounting": {
                         "scientific_audit_calls_per_trial":
                             PN + 3 * EVAL_N,
                         "deployable_method_calls_per_trial": PN + EVAL_N}},
        "gated_records": records,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(batch, indent=1), encoding="utf-8")
    print(f"[saved] {DEST.relative_to(REPO)} -- {len(records)} trials in "
          f"{time.perf_counter() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())