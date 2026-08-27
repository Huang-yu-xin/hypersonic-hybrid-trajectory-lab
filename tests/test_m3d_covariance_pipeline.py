"""M3-D structural + behavioral unit tests (task Sec. 36, all 16 items).

Covers:
    legality / reference labels x3 / direction margin / balanced freeze /
    no-oracle leakage / controller parity with M3 / same-pilot /
    fixed-weight Layer A / CRN counterfactuals / three-class accuracy /
    best-fixed-rule metric / oracle regret / modewise decomposition /
    result schema
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m2.covariance_projection import check_legality_frozen
from hyptraj.m3.direction_policy import DirectionRule
from hyptraj.m3.gradient_estimator import (
    scalar_gradient_estimate,
    stratified_bootstrap_gradient_ci,
    variance_mass_importance,
)
from hyptraj.m3.covariance_gradient import (
    MixtureSpec,
    component_responsibility,
)
from hyptraj.m3d.adaptation import (
    BOOTSTRAP_SEED_RULE,
    ESS_MIN,
    PILOT_RNG_RULE,
    deployed_action,
    draw_online_pilot,
    gradient_arm_key,
    gradient_decision,
)
from hyptraj.m3d.benchmark_states import ANCHOR_SEED, assemble_state, state_arms
from hyptraj.m3d.metrics import (
    build_trial_record,
    identity_closure_ok,
    max_offtarget_ratio,
    median_of_state_seed_medians,
    paired_bootstrap_ci,
    regret_rows,
    state_seed_medians,
    three_class_metrics,
    validate_trial_record,
    win_counts,
)
from hyptraj.m3d.reference_direction import label_state

REPO = Path(__file__).resolve().parents[1]
FREEZE_JSON = REPO / "docs" / "phase_m3d" / "M3_D_Benchmark_Freeze.json"


# --------------------------------------------------------------------------- #
# shared real state (one anchored assembly reused by several tests)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def real_state():
    freeze = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    cid = [c for c in freeze if c.endswith("_c000")][0]
    bc = config_from_record(freeze[cid])
    st = assemble_state(bc, 1.0)
    assert not isinstance(st, dict)
    return st


@pytest.fixture(scope="module")
def real_pilot(real_state):
    return draw_online_pilot(real_state, seed=int(ANCHOR_SEED),
                             n_pilot=4000)


@pytest.fixture(scope="module")
def freeze_doc():
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. candidate-state legality
# --------------------------------------------------------------------------- #
def test_m3d_candidate_state_legality(freeze_doc):
    for rec in freeze_doc["states"]:
        assert rec["legality_passed"] is True
        assert rec["min_eig_selected"] >= 0.5 - 1e-12
        s2 = rec["s2"]
        ok, min_eig = check_legality_frozen(s2 * np.eye(2))
        assert ok and abs(min_eig - s2) < 1e-12


# --------------------------------------------------------------------------- #
# 2-4. reference labels (synthetic refs, rules verbatim from Sec. 8-9)
# --------------------------------------------------------------------------- #
def _arm(m2, batch_offsets):
    return {
        "M2": float(m2), "P": 0.1,
        "M2_batch_se": float(np.std(batch_offsets, ddof=1)
                             / np.sqrt(len(batch_offsets))),
        "n_batches": len(batch_offsets), "batch_n": 100,
        "m2_batches": [float(m2 + d) for d in batch_offsets],
        "L_modes": {}}


def _mk_ref(b, sh, wi, nb=(0.0, 0.0), nw=(0.0, 0.0), ns=(0.0, 0.0)):
    return {"base": _arm(b, nb), "shrink": _arm(sh, ns),
            "widen": _arm(wi, nw)}


def _batches(refs):
    return refs


def test_m3d_reference_widen_label():
    refs = _mk_ref(1.0, 1.20, 0.85)
    out = label_state(refs, _batches(refs), tau=0.01)
    assert out["oracle_action"] == "WIDEN"
    assert out["direction_margin_Delta_dir"] >= 0.05


def test_m3d_reference_shrink_label():
    refs = _mk_ref(1.0, 0.85, 1.25)
    out = label_state(refs, _batches(refs), tau=0.01)
    assert out["oracle_action"] == "SHRINK"
    assert out["direction_margin_Delta_dir"] >= 0.05


def test_m3d_reference_hold_label():
    refs = _mk_ref(1.0, 1.02, 0.999)      # no >1% improvement either way
    out = label_state(refs, _batches(refs), tau=0.01)
    assert out["oracle_action"] == "HOLD"


def test_m3d_direction_margin_threshold():
    # margin is measured between the TWO PERTURBATION ARMS ONLY:
    # widen 0.9091 vs shrink 0.95 -> Delta ~ 4.4% < 0.05 -> demoted
    refs = _mk_ref(1.0, 0.95, 0.9091)
    out = label_state(refs, _batches(refs), tau=0.01)
    assert out["direction_margin_Delta_dir"] < 0.05
    assert out["oracle_action"] == "REFERENCE_AMBIGUOUS"
    # support failure: big UNCORRELATED widen-side batch noise makes the
    # required base-vs-widen contrast unresolvable at 2x SE even though the
    # point gaps are large -> REFERENCE_AMBIGUOUS
    refs2 = _mk_ref(1.0, 1.30, 0.70,
                    nb=[0.0] * 16,
                    nw=[-3.0, 3.0] * 8, ns=[0.0] * 16)
    out2 = label_state(refs2, _batches(refs2), tau=0.01)
    assert out2["support"]["base_vs_widen_supported"] is False
    assert out2["oracle_action"] == "REFERENCE_AMBIGUOUS"


# --------------------------------------------------------------------------- #
# 5. balanced benchmark freeze integrity
# --------------------------------------------------------------------------- #
def test_m3d_balanced_benchmark_freeze(freeze_doc):
    body = json.dumps(freeze_doc_without_hash(freeze_doc), indent=1)
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert h == freeze_doc["freeze_sha256_of_body_above"]
    assert freeze_doc["composition"] == {"WIDEN": 8, "SHRINK": 8, "HOLD": 8}
    assert freeze_doc["online_trials_run_before_this_freeze"] == 0
    seen = set()
    for blk in freeze_doc["selection_executed"]:
        ks = [tuple(x) for x in blk["states"]]
        assert ks == sorted(ks)                    # ascending order rule
        seen.update(ks)
    assert len(seen) == 24                         # all distinct states
    gens = {g["file"] for g in freeze_doc["candidate_pool_generations"]}
    assert any("extension1" in f for f in gens)


def freeze_doc_without_hash(doc):
    d = dict(doc)
    d.pop("freeze_sha256_of_body_above")
    return d


# --------------------------------------------------------------------------- #
# 6. no-oracle leakage (structural)
# --------------------------------------------------------------------------- #
def test_m3d_no_oracle_leakage():
    import hyptraj.m3d.adaptation as adaptation_module

    src = inspect.getsource(adaptation_module)
    for banned in ("reference_direction", "oracle_action",
                   "direction_margin", "M2_base_ref", "mode_L_base"):
        assert banned not in src, f"forbidden symbol {banned!r} in module"
    sig = inspect.signature(adaptation_module.gradient_decision)
    allowed = {"st", "seed", "z", "logp", "logr", "source_strata"}
    assert set(sig.parameters.keys()) <= allowed
    banned_params = {"oracle", "label", "margin", "ref"}
    assert not (set(sig.parameters.keys()) & banned_params)


# --------------------------------------------------------------------------- #
# 7. controller parity with M3-v0 (independent recomposition, bitwise)
# --------------------------------------------------------------------------- #
def test_m3d_controller_parity_with_m3(real_state, real_pilot):
    z, logp, logr, strata = real_pilot
    st = real_state

    out = gradient_decision(st, int(ANCHOR_SEED), z, logp, logr, strata)

    # independent recomposition using ONLY the frozen M3 modules --
    # mirrors the M3-v0 Layer-A driver estimator block verbatim:
    prop = st.proposal()
    pi_all = np.asarray(prop.weights, dtype=float)
    k = st.component_index
    labels = st.bench_cfg.label(z)
    ind_event = (labels != "NOMINAL").astype(float)
    a_vec = variance_mass_importance(
        z, pi_all, np.asarray(prop.centers, dtype=float), list(prop.covs),
        logp, logr, ind_event)
    spec = MixtureSpec(pi_all, np.asarray(prop.centers, dtype=float),
                       tuple(np.asarray(c, dtype=float) for c in prop.covs))
    resp = component_responsibility(spec, z, k)
    sq = np.einsum("ni,ni->n", z - prop.centers[k][None, :],
                   z - prop.centers[k][None, :])
    est = scalar_gradient_estimate(a_vec, resp, sq, s2=st.s2, dim=st.dim)
    est.update(stratified_bootstrap_gradient_ci(
        a_vec, resp, sq, strata, s2=st.s2, dim=st.dim,
        n_bootstrap=500, bootstrap_seed_key=(int(ANCHOR_SEED), 424243)))
    dec = DirectionRule(ess_min=ESS_MIN).decide(
        validity_ok=bool(est["valid_pointwise"]),
        validity_reasons=tuple(est["problems"]),
        ess_grad=float(est["ESS_grad"]),
        g_ci_low=float(est["g_ci_low"]), g_ci_high=float(est["g_ci_high"]))

    g = out["gradient"]
    assert g["g_hat"] == est["g_hat"]
    assert g["responsibility_mass"] == est["mu_r_hat"]
    assert g["D_hat"] == est["D_hat"]
    assert g["g_ci_low"] == est["g_ci_low"]
    assert g["g_ci_high"] == est["g_ci_high"]
    assert g["ESS_grad"] == est["ESS_grad"]
    assert g["decision"] == dec
    assert np.isfinite(g["g_hat"])
    # frozen constants pinned by the module constants (not retuned):
    assert ESS_MIN == 20.0 and N_BOOT_500() == 500
    assert BOOTSTRAP_SEED_RULE == "[seed, 424243]"
    assert PILOT_RNG_RULE == "[seed, 101]"


def N_BOOT_500():
    from hyptraj.m3d import adaptation as A
    return A.N_BOOTSTRAP


# --------------------------------------------------------------------------- #
# 8. same pilot (frozen rng discipline + determinism)
# --------------------------------------------------------------------------- #
def test_m3d_same_pilot(real_state):
    a = draw_online_pilot(real_state, seed=int(ANCHOR_SEED), n_pilot=1000)
    b = draw_online_pilot(real_state, seed=int(ANCHOR_SEED), n_pilot=1000)
    za, lpa, lra, sa = a
    zb, lpb, lrb, sb = b
    assert np.array_equal(za, zb) and np.array_equal(lra, lrb)
    assert np.array_equal(sa, sb) and np.array_equal(lpa, lpb)
    # frozen design: first round(alpha)=500 rows are p-source standard normal
    n_p = int(round(1000 * 0.5))
    assert sa[:n_p].tolist() == [0] * n_p and sa[n_p:].tolist() == [1] * n_p
    assert abs(za[:n_p].mean()) < 0.2
    assert 0.8 < za[:n_p].std() < 1.25        # N(0, I) target-source rows
    # different seed must change the pilot (not accidentally global-seeded)
    c = draw_online_pilot(real_state, seed=int(ANCHOR_SEED) + 1,
                          n_pilot=1000)
    assert not np.array_equal(c[0], za)


# --------------------------------------------------------------------------- #
# 9. fixed-weight Layer A
# --------------------------------------------------------------------------- #
def test_m3d_fixed_weights_layer_a(real_state):
    st = real_state
    arms = state_arms(st, 0.20)
    for name, pr in arms.items():
        assert np.array_equal(pr.weights, st.weights_pi_c0)   # pi_C0 lock
        assert abs(pr.weights.sum() - 1.0) < 1e-12
    k = st.component_index
    for j in range(len(arms["base"].covs)):
        if j == k:
            continue
        for name_a in arms:
            assert np.array_equal(arms[name_a].covs[j],
                                  arms["base"].covs[j])
    assert abs(arms["base"].covs[k][0, 0] - st.s2) < 1e-14
    assert abs(arms["widen"].covs[k][0, 0]
               - st.s2 * np.exp(0.20)) < 1e-12
    assert abs(arms["shrink"].covs[k][0, 0]
               - st.s2 * np.exp(-0.20)) < 1e-12


# --------------------------------------------------------------------------- #
# 10. CRN counterfactual pairing
# --------------------------------------------------------------------------- #
def test_m3d_crn_counterfactuals(real_state):
    st = real_state
    arms = state_arms(st, 0.20)
    k = st.component_index
    n = 2048
    rb = np.random.default_rng([777])
    rw = np.random.default_rng([777])
    rs = np.random.default_rng([777])
    zb = arms["base"].sample(rb, n)
    zw = arms["widen"].sample(rw, n)
    zs = arms["shrink"].sample(rs, n)

    def comp_of(z_prop, n_, arr):   # reproduce choice stream deterministically
        r2 = np.random.default_rng([777])
        return r2.choice(z_prop.n_components, size=n_,
                         p=z_prop.weights)

    comps = [comp_of(arms[a], n, None) for a in ("base", "widen", "shrink")]
    assert np.array_equal(comps[0], comps[1]) \
        and np.array_equal(comps[1], comps[2])
    off = comps[0] != k                      # rows where scaling is inactive
    assert off.any()
    assert np.array_equal(zb[off], zw[off]) \
        and np.array_equal(zw[off], zs[off])
    onk = ~off
    assert not np.allclose(zb[onk], zw[onk])  # active rows do differ
    # deployment mapping folds HOLD reasons onto base arm
    assert gradient_arm_key("HOLD_UNCERTAIN") == "base"
    assert gradient_arm_key("WIDEN") == "widen"
    assert deployed_action("HOLD_LOW_ESS") == "HOLD"


# --------------------------------------------------------------------------- #
# 11. three-class accuracy metric
# --------------------------------------------------------------------------- #
def test_m3d_three_class_accuracy():
    yt = ["WIDEN"] * 4 + ["SHRINK"] * 3 + ["HOLD"] * 3
    yp = ["WIDEN"] * 3 + ["HOLD"] * 1 + ["SHRINK"] * 2 + ["HOLD"] * 1 \
        + ["WIDEN"] * 2 + ["HOLD"] * 1
    m = three_class_metrics(yt, yp)
    assert m["accuracy"] == pytest.approx(6 / 10)
    assert m["recall_per_class"]["WIDEN"] == pytest.approx(3 / 4)
    assert m["recall_per_class"]["SHRINK"] == pytest.approx(2 / 3)
    assert m["recall_per_class"]["HOLD"] == pytest.approx(1 / 3)
    conf = m["confusion_matrix"]
    assert conf["WIDEN"]["WIDEN"] == 3 and conf["WIDEN"]["HOLD"] == 1
    assert conf["SHRINK"]["SHRINK"] == 2 and conf["SHRINK"]["HOLD"] == 1
    assert conf["HOLD"]["WIDEN"] == 2 and conf["HOLD"]["HOLD"] == 1
    assert 0.0 <= m["macro_F1"] <= 1.0
    assert 0.0 <= m["balanced_accuracy"] <= 1.0


# --------------------------------------------------------------------------- #
# 12. best-fixed-rule metric (median of per-state seed medians)
# --------------------------------------------------------------------------- #
def test_m3d_best_fixed_rule_metric():
    grad = {"a": [1.0, 1.2, 0.8], "b": [2.0, 1.9], "c": [0.5]}
    rule = {"a": [1.05], "b": [1.8], "c": [0.6]}
    gm = state_seed_medians(grad)
    rm = state_seed_medians(rule)
    agg_g = median_of_state_seed_medians(grad)
    agg_r = median_of_state_seed_medians(rule)
    assert gm == {"a": 1.0, "b": 1.95, "c": 0.5}
    assert rm == {"a": 1.05, "b": 1.8, "c": 0.6}
    assert agg_g == pytest.approx(1.0) and agg_r == pytest.approx(1.05)
    g_wins, r_wins, ties = win_counts(gm, rm)
    assert (g_wins, r_wins, ties) == (2, 1, 0)      # a: win, b: lose, c: win
    val, lo, hi = paired_bootstrap_ci([gm[k] - rm.get(k, np.nan)
                                       for k in gm if k in rm],
                                      n_boot=999, seed=(20260827,))
    assert lo <= val <= hi


# --------------------------------------------------------------------------- #
# 13. oracle regret
# --------------------------------------------------------------------------- #
def test_m3d_oracle_regret():
    recs = [
        {"oracle_action": "WIDEN",
         "metrics": {"regret_M2": 0.04}},
        {"oracle_action": "WIDEN",
         "metrics": {"regret_M2": 0.06}},
        {"oracle_action": "SHRINK",
         "metrics": {"regret_M2": 0.10}},
        {"oracle_action": "HOLD", "metrics": {"regret_M2": 0.01}},
    ]
    r = regret_rows(recs)
    assert r["global_median"] == pytest.approx(0.05)
    assert r["per_class_median"]["WIDEN"] == pytest.approx(0.05)
    assert r["per_class_median"]["SHRINK"] == pytest.approx(0.10)
    assert r["per_class_median"]["HOLD"] == pytest.approx(0.01)


# --------------------------------------------------------------------------- #
# 14. modewise decomposition M2 = sum_j L_j
# --------------------------------------------------------------------------- #
def test_m3d_modewise_decomposition():
    L = {"S1": 0.30, "S2": 0.22, "S3": 0.08, "S4": 0.40}
    m2 = sum(L.values())
    assert identity_closure_ok(L, m2, rel_tol=1e-12)
    L_broken = dict(L, S4=L["S4"] + 1e-3)
    assert not identity_closure_ok(L_broken, m2, rel_tol=1e-9)
    # selected-mode column is EXCLUDED from the off-target max:
    # if S2 (huge 9.9 vs base .22 ~45x) were counted, result would be ~45;
    # the true off-target modes are unchanged => ratio exactly 1.0
    Lg_sel_only = {"S1": 0.30, "S2": 9.9, "S3": 0.08, "S4": 0.40}
    assert max_offtarget_ratio(L, Lg_sel_only, selected_mode="S2") \
        == pytest.approx(1.0)
    Lg = {"S1": 0.45, "S2": 0.10, "S3": 0.16, "S4": 0.40}
    assert max_offtarget_ratio(L, Lg, selected_mode="S2") == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# 15-16. result schema
# --------------------------------------------------------------------------- #
def _mk_record() -> dict:
    L = {"S1": 0.30, "S2": 0.20, "S3": 0.50}
    arms = {k: {"M2": sum(L.values()), "mode_L": L}
            for k in ("hold", "widen", "shrink", "gradient", "oracle")}
    return build_trial_record(
        config_id="m1d_x_c000", state_id="c000_s2_00100", seed=2026,
        base_s2=1.0, oracle_action="WIDEN",
        oracle_direction_margin=0.21,
        gradient_block={"g_hat": -1.5, "g_ci_low": -2.0, "g_ci_high": -1.0,
                        "ESS_grad": 187.5, "action": "WIDEN"},
        arms_block=arms,
        metrics_block={"action_correct": True, "regret_M2": 0.03,
                       "VRF_proposal": 1.07, "VRF_budget": 0.91},
        validity_block={"legality_all_passed": True})


def test_m3d_result_schema():
    rec = _mk_record()
    assert validate_trial_record(rec)
    bad = _mk_record()
    bad["gradient"]["action"] = "ALWAYS_WIDEN"
    assert not validate_trial_record(bad)
    bad2 = _mk_record()
    bad2["arms"]["gradient"]["mode_L"] = {"S1": 99.0, "S2": 0.0, "S3": 0.0}
    assert not validate_trial_record(bad2)   # closure violated -> reject
