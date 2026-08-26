"""M1-D preregistered test suite (task Sec. 40) -- execution-layer D4.

Covers the eleven mandated test names against the m1d execution modules.
Heavy runs are smoke-sized (small pilots / evaluations); full-budget
protocol parameters live exclusively in configs/, never here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m1.proposal_update import MixtureProposal
from hyptraj.m1d.adaptation import (
    build_final_proposal,
    l_hat_online,
    oracle_pick,
    p_hat_online,
    random_pick,
    selector_pick,
)
from hyptraj.m1d.benchmark_family import (
    compute_eligibility,
    generate_candidate_pool,
)
from hyptraj.m1d.experiments import (
    SEEDS,
    choose_freeze,
    load_freeze,
    make_record,
    ref_views,
)
from hyptraj.m1d.layer_a import run_layer_a_trial, run_layer_b_trial
from hyptraj.m1d.metrics import cps_of, cvs_of

REPO = Path(__file__).resolve().parents[1]
FREEZE = REPO / "docs" / "phase_m1d" / "M1_D_Benchmark_Freeze.json"


def _cfg(cid="m1d_b20260827_c000"):
    recs = load_freeze()["benchmark_configs"]
    return _as_cfg([r for r in recs if r["config_id"] == cid][0])


def _as_cfg(rec):
    from hyptraj.m1d.experiments import config_from_record
    return config_from_record(rec)


SMOKE = dict(n_pilot=4000, n_eval=2000)


# ---------------------------------------------------------------------------
# 1 -- benchmark eligibility logic
# ---------------------------------------------------------------------------
def test_m1d_benchmark_eligibility():
    tbl = lambda P, L: {k: {"P_ref": p, "L_ref": l}
                        for k, p, l in zip(("S2", "S3", "S4"), P, L)}
    kw = dict(alpha_p=0.5, pilot_n=20_000)
    e = compute_eligibility(tbl([.05, .03, .002], [.10, .60, .05]), **kw)
    assert e["eligible"] and e["k_P_star"] != e["k_V_star"]
    e = compute_eligibility(tbl([.60, .30, .002], [.70, .05, .02]), **kw)
    assert not e["E3_top_rank_conflict"]          # top ranks coincide
    e = compute_eligibility(tbl([.05, .04, .002], [.10, .13, .01]), **kw)
    assert not e["E4_strong_inversion"]           # ratios below 1.5


# ---------------------------------------------------------------------------
# 2 -- freeze determinism / non-relaxation rule
# ---------------------------------------------------------------------------
def test_m1d_benchmark_freeze_deterministic():
    freeze = load_freeze()
    ids = [c["config_id"] for c in freeze["benchmark_configs"]]
    elig_ids = [c["config_id"] for c in freeze["benchmark_configs"]]
    assert choose_freeze(elig_ids + ["m1d_extra"])[:len(ids)] == sorted(ids)

    pool_a = generate_candidate_pool(20260827, 6)
    pool_b = generate_candidate_pool(20260827, 6)
    assert [c.params_dict() for c in pool_a] == \
           [c.params_dict() for c in pool_b]

    with pytest.raises(RuntimeError, match="NOT relaxed|batch"):
        choose_freeze(["a_c1", "b_c2"])


# ---------------------------------------------------------------------------
# 3 -- no-oracle leakage (structural + runtime behaviour)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mod", ["adaptation", "layer_a"])
def test_m1d_no_oracle_leakage(mod):
    src = (REPO / "src" / "hyptraj" / "m1d" / f"{mod}.py").read_text(
        encoding="utf-8")
    for token in ("P_ref", "L_ref", "reference_P", "reference_L",
                  "Benchmark_Freeze", "benchmark_freeze",
                  "json.load", "open(", "read_text"):
        assert token not in src, (mod, token)


def test_m1d_online_modules_run_without_any_reference_input():
    cfg = _cfg()
    rec = run_layer_a_trial(cfg, SEEDS[0], "variance_selector",
                            birth_budget=1, **SMOKE)
    assert rec["selected_modes"]                      # decided purely online


# ---------------------------------------------------------------------------
# 4 / 5 -- probability and variance ranking estimators & selectors
# ---------------------------------------------------------------------------
def _synthetic_bundle():
    """Two well-separated Gaussians as 'modes' with a recorded wide design.

    Cluster draws are EQUAL-SIZE (750/750) so that with symmetric placement
    the target-probability estimates form a near-tie (sampling noise only).
    """
    rng = np.random.default_rng(7)
    z_s2 = rng.standard_normal((750, 2)) * [0.2, 0.2] + [3.2, 0.0]
    z_s3 = rng.standard_normal((750, 2)) * [0.2, 0.2] + [0.0, 3.2]
    z = np.vstack([z_s2, z_s3])
    labels = np.array(["S2"] * 750 + ["S3"] * 750, dtype=object)
    logp = -np.sum(z**2, axis=1) / 2 - np.log(2 * np.pi)      # d=2 constant
    sigma2 = 16.0
    logr = -np.sum(z**2, axis=1) / (2 * sigma2) - np.log(2 * np.pi * sigma2)
    centers = np.array([[0.0, 0.0]])
    pi = np.array([1.0])
    return z, logp, logr, labels, centers, pi


def test_m1d_probability_ranking():
    z, logp, logr, labels, centers, pi = _synthetic_bundle()
    p2 = p_hat_online(logp, logr, labels, "S2")
    p3 = p_hat_online(logp, logr, labels, "S3")
    # symmetric placement at equal ||mu|| -> near-tie in expected mass
    assert abs(p2 - p3) / max(p2, p3) < 0.12
    pick, diag = selector_pick("probability", ["S2", "S3"], labels, z,
                               centers, pi, logp, logr)
    assert pick == max(["S2", "S3"], key=lambda m: diag["P_hat_table"][m])

    # tilt: shift the S2 cluster inward -> strictly higher probability
    z[:, 0][labels == "S2"] -= 1.0
    logp = -np.sum(z**2, axis=1) / 2 - np.log(2 * np.pi)
    pick, _ = selector_pick("probability", ["S2", "S3"], labels, z,
                            centers, pi, logp, logr)
    assert pick == "S2"


def test_m1d_variance_ranking():
    z, logp, logr, labels, centers, pi = _synthetic_bundle()
    # leakage explodes where the proposal is DEPLETED: park the probe
    # component on top of the S2 cloud -> S3 (proposal-starved side of the
    # target plane at equal radius) carries the dominant variance mass
    probe = np.array([[3.2, 0.0]])
    l3 = l_hat_online(z, probe, pi, logp, logr, labels, "S3")
    l2 = l_hat_online(z, probe, pi, logp, logr, labels, "S2")
    assert l3 > 10.0 * max(l2, 1e-300)
    pick, diag = selector_pick("variance", ["S2", "S3"], labels, z,
                               probe, pi, logp, logr)
    assert pick == "S3"
    assert diag["L_hat_table"]["S3"] > diag["L_hat_table"]["S2"]


# ---------------------------------------------------------------------------
# 6 -- common action identity / CRN pilots across selectors
# ---------------------------------------------------------------------------
def test_m1d_common_action_identical():
    cfg = _cfg()
    a = run_layer_a_trial(cfg, SEEDS[0], "probability_selector",
                          birth_budget=1, **SMOKE)
    b = run_layer_a_trial(cfg, SEEDS[0], "variance_selector",
                          birth_budget=1, **SMOKE)
    ta = a["rounds"][0]["selection_diag"]
    tb = b["rounds"][0]["selection_diag"]
    assert ta["P_hat_table"].keys() == tb["P_hat_table"].keys()
    for m in ta["P_hat_table"]:
        assert abs(ta["P_hat_table"][m] - tb["P_hat_table"][m]) == 0.0
        assert abs(ta["L_hat_table"][m] - tb["L_hat_table"][m]) == 0.0

    # builder identity: same inputs -> bit-equal downstream proposal
    rng = np.random.default_rng([1, 2])
    prop0 = MixtureProposal(centers=np.zeros((1, 2)), weights=np.array([1.0]),
                            component_mode_ids=("S1",))
    z = rng.standard_normal((500, 2))
    logr = -np.sum(z**2, axis=1) / 2 - np.log(2 * np.pi)
    labels = np.array(["S2"] * 250 + ["S1"] * 250, dtype=object)
    labels_z = z.copy()
    labels_z[:250] += [3.0, 0.0]
    logp = -np.sum(labels_z**2, axis=1) / 2 - np.log(2 * np.pi)
    p1, d1 = build_final_proposal(prop0, labels_z, logp, logr, labels, "S1",
                                  "S2")
    p2, d2 = build_final_proposal(prop0, labels_z, logp, logr, labels, "S1",
                                  "S2")
    np.testing.assert_array_equal(p1.centers, p2.centers)
    np.testing.assert_array_equal(p1.weights, p2.weights)


# ---------------------------------------------------------------------------
# 7 -- birth budget enforcement
# ---------------------------------------------------------------------------
def test_m1d_birth_budget_enforced():
    cfg = _cfg()
    la = run_layer_a_trial(cfg, SEEDS[1], "random_selector", birth_budget=1,
                           **SMOKE)
    assert len(la["selected_modes"]) <= 1
    assert la["cost"]["adaptation_calls"] <= (1 + 1) * SMOKE["n_pilot"]

    lb1 = run_layer_b_trial(cfg, SEEDS[1], "variance", birth_budget=1,
                            n_bootstrap=20, **{k: v for k, v in SMOKE.items()})
    adds = sum(1 for it in lb1["rounds"] if it["action"] == "ADD_COMPONENT")
    assert adds <= 1
    assert lb1["cost"]["budget_assertion_passed"]

    lb2 = run_layer_b_trial(cfg, SEEDS[1], "probability", birth_budget=2,
                            n_bootstrap=20, n_pilot=3000, n_eval=1500)
    adds2 = sum(1 for it in lb2["rounds"] if it["action"] == "ADD_COMPONENT")
    assert adds2 <= 2
    assert lb2["cost"]["budget_assertion_passed"]


# ---------------------------------------------------------------------------
# 8 -- captured shares
# ---------------------------------------------------------------------------
def test_m1d_captured_variance_share():
    L = {"S2": 2.0, "S3": 6.0, "S4": 2.0}
    P = {"S2": 3.0, "S3": 1.0, "S4": 1.0}
    assert cvs_of(["S2"], L) == pytest.approx(0.2)
    assert cvs_of([], L) == 0.0
    assert cps_of(["S3"], P) == pytest.approx(0.2)
    assert cvs_of(["S2", "S4"], L) == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# 9 -- oracle-V selector obeys reference order within eligible set
# ---------------------------------------------------------------------------
def test_m1d_oracle_v_selector():
    cands = ["S3", "S4"]                       # S2 missing from candidate set
    assert oracle_pick(["S2", "S4", "S3"], cands) == "S4"
    assert oracle_pick(["S9"], cands) is None
    assert random_pick(cands, np.random.default_rng(0)) in cands


# ---------------------------------------------------------------------------
# 10 -- dynamic re-ranking under q1 (Sec. 26)
# ---------------------------------------------------------------------------
def test_m1d_dynamic_reranking():
    cfg = _cfg()
    rec = run_layer_b_trial(cfg, SEEDS[0], "variance", birth_budget=2,
                            n_bootstrap=30, n_pilot=8000, n_eval=1000)
    acts = [it["action"] for it in rec["rounds"]]
    assert acts.count("ADD_COMPONENT") >= 1
    if acts.count("ADD_COMPONENT") < 2 or len(rec["rounds"]) < 2:
        pytest.skip("policy stopped before second birth on this seed")

    r0 = {ms["mode_id"]: ms["L_k_hat"] for ms in rec["rounds"][0]["mode_stats"]}
    r1 = {ms["mode_id"]: ms["L_k_hat"] for ms in rec["rounds"][1]["mode_stats"]}
    leaked = any(r0[m] != r1[m] for m in r0)           # re-estimated under q1
    assert leaked

    born_first = rec["selected_modes"][0]
    remaining = [m for m in r1 if m != born_first
                 and not any(ms["represented_by_component"]
                             for ms in rec["rounds"][1]["mode_stats"]
                             if ms["mode_id"] == m)]
    stale_next = max((m for m in r0 if m != born_first), key=lambda m: r0[m])
    actual_next = rec["selected_modes"][1] if len(rec["selected_modes"]) > 1 \
        else None
    if actual_next is not None and actual_next in r1 and stale_next in r1:
        expect_new = max(remaining, key=lambda m: r1[m])
        assert actual_next == expect_new               # fresh ranking honoured


# ---------------------------------------------------------------------------
# 11 -- machine-readable result schema (task Sec. 37)
# ---------------------------------------------------------------------------
def test_m1d_result_schema():
    cfg = _cfg()
    freeze_rec = [r for r in load_freeze()["benchmark_configs"]
                  if r["config_id"] == cfg.config_id][0]
    rv = ref_views(freeze_rec)
    core = run_layer_a_trial(cfg, SEEDS[2], "variance_selector",
                             birth_budget=1, **SMOKE)
    rec = make_record(batch_dir="test", parent_freeze_sha="deadbeef",
                      bench_cfg=cfg, rv=rv, budget_total_declared=104000,
                      core=core)
    for key in ("schema_version", "parent_tag", "h3_tag",
                "benchmark_freeze_hash", "config_id", "seed", "birth_budget",
                "method", "pilot", "mode_estimates", "selected_modes",
                "selection_metrics", "evaluation"):
        assert key in rec, key
    ev = rec["evaluation"]
    assert {"P_hat", "M2_hat", "VRF_proposal", "VRF_budget"} <= set(ev)
    assert all(np.isfinite(ev[k]) for k in
               ("P_hat", "M2_hat", "VRF_proposal", "VRF_budget"))
    sm = rec["selection_metrics"]
    assert isinstance(sm["top1_variance_correct"], bool)
    assert 0.0 <= sm["captured_variance_share"] <= 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
