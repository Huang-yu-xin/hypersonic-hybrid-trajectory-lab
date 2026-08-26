"""M2 preregistered test suite (task Sec. 40) -- the fourteen mandated names.

Heavy runs are smoke-sized where possible; the two driver-level tests
(``test_m2_no_extra_simulator_calls`` / ``test_m2_no_final_eval_leakage``)
run ONE frozen config x TWO seeds at the locked protocol budgets into a
temporary directory (~25 s).  Full-budget grid lives exclusively in
scripts/run_m2_covariance_experiments.py, never here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m1.mixture_weights import optimize_mixture_weights
from hyptraj.m1.proposal_update import (
    LEGALITY_MIN_EIG,
    add_component,
    eta_region_centroid,
    update_weights,
    variance_mass_hdr_indices,
)
from hyptraj.m1.variance_measure import variance_mass_weights
from hyptraj.m1d.adaptation import draw_mix_pilot
from hyptraj.m1d.layer_a import run_layer_a_trial
from hyptraj.m2 import covariance_policy as cp
from hyptraj.m2.covariance_projection import (
    LAMBDA_MAX_CAP,
    LAMBDA_MIN_FLOOR,
    base_covariance_from_frozen_metadata,
    check_legality_frozen,
    project_covariance,
)
from hyptraj.m2.metrics import (
    REQUIRED_SCHEMA_KEYS,
    anisotropy_ratio,
    build_trial_record,
    leakage_ratios,
    principal_alignment,
)
from hyptraj.m2.variance_covariance import (
    ESS_V_MIN,
    diagonal_covariance,
    estimate_variance_region,
    isotropic_scale_covariance,
    shrunk_full_covariance,
    symmetrize_matrix,
)

REPO = Path(__file__).resolve().parents[1]
SMOKE_PILOT = 4000


def _frozen_cfg(cid="m1d_b20260827_c000"):
    from hyptraj.m1d.experiments import config_from_record, load_freeze
    recs = load_freeze()["benchmark_configs"]
    return config_from_record([r for r in recs if r["config_id"] == cid][0])


# A config with comparatively healthy in-region ESS at smoke sizes (identified
# offline; c004 has the largest region ESS medians).
_CFG_HI_ESS = "m1d_b20260827_c004"


def _synthetic_pilot():
    """Deterministic synthetic pilot with hand-computable region moments.

    Construction: target p = N(0, I_2); proposal q_t = N(center=[0,0], pi=1)
    (= p itself); every sample gets its OWN recorded r_i so that the
    variance-mass weights become exactly chosen values (each sample keeps its
    recorded sampling density -- task Sec. 10 legality respected by design).

    Mode samples S3 carry log-weights: a few "dominant" points then a long
    equal-weight tail -> HDR prefix selection is fully predictable.
    """
    rng = np.random.default_rng(20260831)
    n_mode, n_tail = 6, 30
    centers = np.zeros((1, 2))
    pi = np.array([1.0])
    X_mode = rng.normal(0.0, 0.8, size=(n_mode + n_tail, 2)) + [4.0, 4.0]
    z = X_mode.copy()
    labels = np.array(["S3"] * (n_mode + n_tail))

    # desired weights: dominant block w=100 each; tail w=1 each
    w_des = np.concatenate([np.full(n_mode, 100.0), np.ones(n_tail)])

    def logp_fn(x):
        return -np.sum(x ** 2, axis=1) / 2.0 - np.log(2.0 * np.pi)

    q_at = -np.sum((z - centers[0]) ** 2, axis=1) / 2.0 - np.log(2.0 * np.pi)
    lp = logp_fn(z)
    # w = exp(2 lp - logq - logr) = w_des  =>  logr = 2lp - logq - ln w_des
    logr = 2.0 * lp - q_at - np.log(w_des)

    # replicate the FROZEN hdr rule to know the expected region exactly:
    idx_expected, achieved = variance_mass_hdr_indices(
        z, centers, pi, lp, logr, labels, "S0", "S3", eta=0.8)
    return dict(z=z, centers=centers, pi=pi, logp=lp, logr=logr,
                labels=labels, eta=0.8, idx_expected=idx_expected,
                achieved=achieved, w_des=w_des)


# ---------------------------------------------------------------------------
# 1 -- weighted variance covariance toy
# ---------------------------------------------------------------------------
def test_m2_weighted_variance_covariance_toy():
    s = _synthetic_pilot()
    st = estimate_variance_region(s["z"], s["centers"], s["pi"], s["logp"],
                                  s["logr"], s["labels"], "S0", "S3",
                                  eta=s["eta"])
    # region membership equals the frozen HDR prefix (mirrored expectation)
    assert set(st.region_indices.tolist()) == set(s["idx_expected"].tolist())

    wr = s["w_des"][st.region_indices]
    sw = float(wr.sum())
    m_exp = (wr[:, None] * s["z"][st.region_indices]).sum(axis=0) / sw
    dX = s["z"][st.region_indices] - m_exp
    C_exp = ((dX * wr[:, None]).T @ dX) / sw

    assert np.allclose(st.centroid, m_exp, atol=1e-12)
    assert np.allclose(st.cov, C_exp, atol=1e-12)
    assert abs(st.weight_sum - sw) < 1e-9
    wb = wr / sw
    assert abs(st.ess_v_region - float(1.0 / np.sum(wb ** 2))) < 1e-9

    # eigen orientation of the region cloud is recoverable
    eigval, eigvec = np.linalg.eigh(C_exp)
    _, _v = np.linalg.eigh(st.cov)
    if eigval[-1] / max(eigval[0], 1e-12) > 1.5:
        assert principal_alignment(C_exp, st.cov) > 0.999

    # candidate constructors on the same object behave per formula
    base = np.eye(2)
    assert np.allclose(isotropic_scale_covariance(st.cov),
                       float(np.trace(st.cov)) / 2 * np.eye(2))
    assert np.allclose(diagonal_covariance(st.cov), np.diag(np.diag(st.cov)))
    lam = 0.5
    assert np.allclose(shrunk_full_covariance(st.cov, base, lam),
                       0.5 * base + 0.5 * st.cov)
    with pytest.raises(ValueError):
        shrunk_full_covariance(st.cov, base, 1.0)
    assert anisotropy_ratio(st.cov) >= 1.0


# ---------------------------------------------------------------------------
# 2 -- symmetry discipline
# ---------------------------------------------------------------------------
def test_m2_covariance_symmetry():
    rng = np.random.default_rng(7)
    for _ in range(20):
        a = rng.normal(size=(3, 3))
        s = symmetrize_matrix(a)
        assert np.allclose(s, s.T)
        pr = project_covariance(a)
        assert np.allclose(pr.sigma_pre, symmetrize_matrix(a))
        assert np.allclose(pr.sigma_final, pr.sigma_final.T)

    eps = 1e-13
    cov = np.array([[2.0 + eps, 0.0], [-eps, 0.7]])
    st_cov = symmetrize_matrix(cov)
    assert st_cov[0, 1] == pytest.approx(st_cov[1, 0])


# ---------------------------------------------------------------------------
# 3 -- ESS identity inside region stats
# ---------------------------------------------------------------------------
def test_m2_covariance_ess():
    s = _synthetic_pilot()
    st = estimate_variance_region(s["z"], s["centers"], s["pi"], s["logp"],
                                  s["logr"], s["labels"], "S0", "S3")
    wr = variance_mass_weights(s["z"], s["centers"], s["pi"], s["logp"],
                               s["logr"],
                               (s["labels"] == "S3").astype(float))
    wr_r = wr[st.region_indices]
    wb = wr_r / wr_r.sum()
    assert st.ess_v_region == pytest.approx(float(1.0 / np.sum(wb ** 2)))
    assert st.n_region <= int((s["labels"] == "S3").sum())
    # handcrafted weights must propagate exactly to region weight sums
    assert st.weight_sum == pytest.approx(float(wr_r.sum()))


# ---------------------------------------------------------------------------
# 4 -- HOLD_BASE_COVARIANCE behavior
# ---------------------------------------------------------------------------
def test_m2_covariance_hold_low_ess():
    from hyptraj.m2.variance_covariance import VarianceRegionStats
    degenerate = np.eye(2) * 0.01
    st = VarianceRegionStats(
        mode_id="S3", eta_requested=0.8, eta_used=1.0,
        region_indices=np.arange(10), n_region=10, centroid=np.zeros(2),
        cov=degenerate, weight_sum=0.03,
        ess_v_region=2.0,                                # far below 20
        eigenvalues_raw=np.linalg.eigvalsh(degenerate),
        condition_raw=1.0, finite=True)
    hold, reason = st.hold_required
    assert hold and "ESS" in reason

    # non-finite estimator also triggers the HOLD machinery explicitly
    st_bad = VarianceRegionStats(
        mode_id="S3", eta_requested=0.8, eta_used=1.0,
        region_indices=np.arange(4), n_region=4, centroid=np.zeros(2),
        cov=np.array([[float("nan"), 0.0], [0.0, 1.0]]), weight_sum=1.0,
        ess_v_region=float("nan"),
        eigenvalues_raw=np.array([np.nan, np.nan]),
        condition_raw=float("nan"), finite=False)
    hold_b, reason_b = st_bad.hold_required
    assert hold_b and "non_finite" in reason_b

    cands = cp.build_candidates(st, np.eye(2))
    for m in ("C1", "C2", "C3", "C4"):
        assert cands[m].held
        assert np.allclose(cands[m].sigma_final, np.eye(2))
        assert cands[m].hold_reason != ""
    assert not cands["C0"].held and not cands["C0"].hold_reason

    # end-to-end HOLD trial collapses variants to C0 bit-for-bit
    bc = _frozen_cfg("m1d_b20260827_c010")     # thinnest regions offline
    stage = cp.run_shared_stage(bc, 2100, n_pilot=1200, n_eval=2000)
    assert stage.region is not None and stage.region.hold_required[0]
    cand_h = cp.build_candidates(stage.region, stage.sigma_base)
    eval_ref = None
    for m in ("C0", "C1", "C3", "C4"):
        prop, _info = cp.build_variant_proposal(stage, cand_h[m], cp.LAYER_A)
        ev = cp.evaluate_variant(stage, prop, 2000)
        assert np.allclose(prop.covs[-1], stage.sigma_base)
        if eval_ref is None:
            eval_ref = ev
        else:
            assert ev["M2_hat"] == eval_ref["M2_hat"]      # identical CRN path
            assert ev["P_hat"] == eval_ref["P_hat"]


# ---------------------------------------------------------------------------
# 5 -- eigen projection
# ---------------------------------------------------------------------------
def test_m2_eigen_projection():
    wild = np.diag([1e-4, 50.0])
    proj = project_covariance(wild)
    assert proj.valid_input
    assert proj.n_eigen_clipped_low == 1 and proj.n_eigen_clipped_high == 1
    assert np.allclose(proj.eigenvalues_post,
                       [LAMBDA_MIN_FLOOR, LAMBDA_MAX_CAP])
    assert proj.projection_frobenius_norm == pytest.approx(
        float(np.linalg.norm(proj.sigma_final - proj.sigma_pre)))
    # axis preservation under diagonal input
    diag_in = np.diag([0.3, 3.5])
    out = project_covariance(diag_in).sigma_final
    assert np.allclose(out, np.diag([LAMBDA_MIN_FLOOR, 3.5]))
    in_range = project_covariance(np.diag([0.7, 3.9]))
    assert np.allclose(in_range.sigma_final, np.diag([0.7, 3.9]))
    assert in_range.n_eigen_clipped_low == in_range.n_eigen_clipped_high == 0
    rotated = np.array([[2.0, 0.4], [0.4, 2.0]])
    rp = project_covariance(rotated)
    assert np.allclose(rp.eigenvalues_post, [2.0 - 0.4, 2.0 + 0.4])
    assert rp.legality_passed


# ---------------------------------------------------------------------------
# 6 -- frozen legality checker reuse
# ---------------------------------------------------------------------------
def test_m2_frozen_legality_checker():
    ok, min_eig = check_legality_frozen(np.diag([0.55, 2.0]))
    assert ok and min_eig == pytest.approx(0.55)
    bad, _me = check_legality_frozen(np.diag([LEGALITY_MIN_EIG - 0.01, 2.0]))
    assert not bad
    boundary, me_b = check_legality_frozen(np.diag([LEGALITY_MIN_EIG, 2.0]))
    assert boundary

    # projection family automatically satisfies the frozen gate
    for mat in (np.diag([1e-6, 40.0]), np.diag([0.6, 0.61]),
                [[1.0, 0.2], [0.0, 1.0]]):
        pr = project_covariance(np.asarray(mat, dtype=float))
        assert pr.legality_passed
        assert pr.min_eig_final >= LEGALITY_MIN_EIG - 1e-12

    nan_mat = np.array([[float("nan"), 0.0], [0.0, 1.0]])
    pr_nan = project_covariance(nan_mat)
    assert not pr_nan.valid_input and not pr_nan.legality_passed

    sigma_base, checks = base_covariance_from_frozen_metadata(
        LEGALITY_MIN_EIG, True, 2)
    assert np.allclose(sigma_base, np.eye(2)) and \
        checks.get("reconstruction_verified")
    with pytest.raises(ValueError):
        base_covariance_from_frozen_metadata(0.42, True, 2)
    with pytest.raises(ValueError):
        base_covariance_from_frozen_metadata(LEGALITY_MIN_EIG, False, 2)


# ---------------------------------------------------------------------------
# 7 -- selection lock vs frozen M1-D selector pathway
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cid", ["m1d_b20260827_c000", _CFG_HI_ESS])
def test_m2_selection_lock(cid):
    bc = _frozen_cfg(cid)
    seed = 2026

    # reference replication of the frozen pathway, independently written
    q0 = bc.initial_proposal()
    rng = np.random.default_rng([seed, 101])
    z, logr, _strata = draw_mix_pilot(rng, q0, bc.logp, SMOKE_PILOT, 0.5)
    logp = bc.logp(z)
    labels = bc.label(z)
    from hyptraj.m1d.adaptation import eligible_candidates, selector_pick
    pick_ref, _diag = selector_pick(
        "variance", eligible_candidates(labels, "S0",
                                        set(q0.component_mode_ids)),
        labels, z, q0.centers, q0.weights, logp, logr)

    # M2 locked stage (same seed twice => bit-stable)
    st1 = cp.run_shared_stage(bc, seed, n_pilot=SMOKE_PILOT, n_eval=2000)
    st2 = cp.run_shared_stage(bc, seed, n_pilot=SMOKE_PILOT, n_eval=2000)
    assert st1.selected_mode == pick_ref
    assert st1.selected_mode == st2.selected_mode
    assert np.array_equal(np.sort(st1.region.region_indices),
                          np.sort(st2.region.region_indices))

    # equality with the archived M1-D Layer-A selector machinery itself
    core = run_layer_a_trial(bc, seed, "variance_selector", birth_budget=1,
                             n_pilot=SMOKE_PILOT, alpha=0.5, n_eval=1000,
                             center_rule="variance_hdr", weight_rule="m2_opt")
    assert core["selected_modes"][0] == st1.selected_mode


# ---------------------------------------------------------------------------
# 8 -- mean lock across variants
# ---------------------------------------------------------------------------
def test_m2_mean_lock():
    bc = _frozen_cfg(_CFG_HI_ESS)
    stage = cp.run_shared_stage(bc, 2029, n_pilot=SMOKE_PILOT, n_eval=2000)
    cen_frozen, eta_used = eta_region_centroid(
        stage.z, stage.logp, stage.logr, stage.q0_frozen.weights,
        stage.q0_frozen.centers, stage.labels, "S0",
        mode=str(stage.selected_mode), eta=0.8)
    assert np.allclose(stage.region.centroid, cen_frozen, rtol=0, atol=1e-12)
    assert stage.centroid_frozen_check < 1e-12

    cands = cp.build_candidates(stage.region, stage.sigma_base)
    for layer in (cp.LAYER_A, cp.LAYER_B):
        for m in cp.COV_METHODS:
            prop, _info = cp.build_variant_proposal(stage, cands[m], layer)
            assert prop.centers.shape[0] == 2
            assert np.allclose(prop.centers[-1], cen_frozen)
            assert np.allclose(prop.centers[0],
                               stage.q0_frozen.centers[0])
    # independent frozen action reconstruction reproduces pi_c0 (already the
    # C0 definition) AND uses the same centroid vector
    prop0 = add_component(stage.q0_frozen, cen_frozen,
                          mode_id=str(stage.selected_mode))
    indicators = (stage.labels != "S0").astype(float)
    prop0, res = update_weights(prop0, stage.z, stage.logp, stage.logr,
                                indicators)
    assert res.success and np.allclose(prop0.weights, stage.pi_c0)


# ---------------------------------------------------------------------------
# 9 -- Layer A shares pi_C0 exactly; only newborn covariance differs
# ---------------------------------------------------------------------------
def test_m2_shape_only_same_weights():
    bc = _frozen_cfg(_CFG_HI_ESS)
    stage = cp.run_shared_stage(bc, 2031, n_pilot=SMOKE_PILOT, n_eval=2000)
    cands = cp.build_candidates(stage.region, stage.sigma_base)
    props = {m: cp.build_variant_proposal(stage, cands[m], cp.LAYER_A)[0]
             for m in cp.COV_METHODS}
    ref_w = props["C0"].weights
    for m, prop in props.items():
        assert np.array_equal(prop.weights, ref_w)       # exact share
        assert prop.component_mode_ids == props["C0"].component_mode_ids
        assert np.allclose(prop.centers, props["C0"].centers)
        for j in range(prop.centers.shape[0] - 1):
            assert np.allclose(prop.covs[j], np.eye(2))
    differing = [m for m in cp.COV_METHODS
                 if not np.allclose(props[m].covs[-1], np.eye(2))]
    assert len(differing) >= 1 or all(cands[m].held for m in differing)


# ---------------------------------------------------------------------------
# 10 -- Layer B calls the frozen optimizer unmodified
# ---------------------------------------------------------------------------
def test_m2_shape_reweight_same_optimizer():
    bc = _frozen_cfg(_CFG_HI_ESS)
    stage = cp.run_shared_stage(bc, 2030, n_pilot=SMOKE_PILOT, n_eval=2000)
    cands = cp.build_candidates(stage.region, stage.sigma_base)

    call_args = []
    real_opt = cp.optimize_mixture_weights

    def spy(logq_ji, logp, logr, indicators, **kw):
        call_args.append(dict(kw))
        return real_opt(logq_ji, logp, logr, indicators, **kw)

    cp.optimize_mixture_weights = spy
    try:
        props = {}
        for m in cp.COV_METHODS:
            props[m] = cp.build_variant_proposal(stage, cands[m],
                                                 cp.LAYER_B)[0]
    finally:
        cp.optimize_mixture_weights = real_opt
    assert len(call_args) == len(cp.COV_METHODS)
    for kw in call_args:                     # frozen defaults untouched
        assert kw.get("floor", 0.0) == 0.0
        assert kw.get("maxiter", 500) == 500
        assert kw.get("ftol", 1e-12) == 1e-12
        assert kw.get("pi0") is not None

    # exact replication through an independent direct call
    spec = cands["C4"]
    prop_b = cp.build_variant_proposal(stage, spec, cp.LAYER_B)[0]
    ind = (stage.labels != "S0").astype(float)
    logq_ji = cp.component_log_densities_cov(stage.z, prop_b.centers,
                                             prop_b.covs)
    init_split = np.append(0.5 * stage.q0_frozen.weights, 0.5)
    res = optimize_mixture_weights(logq_ji, stage.logp, stage.logr, ind,
                                   pi0=init_split, floor=0.0)
    assert res.success and np.allclose(res.weights, prop_b.weights)


# ---------------------------------------------------------------------------
# helpers shared by leakage tests (11/12) -- one guarded mini-run
# ---------------------------------------------------------------------------
def _mini_run(tmp_path, monkeypatch, seeds=(2026,)):
    import scripts.run_m2_covariance_experiments as drv
    drv.RESULTS = tmp_path / "phase_m2"
    drv.FROZEN_IDS = [_CFG_HI_ESS]
    monkeypatch.setattr(drv, "SEEDS", list(seeds))
    drv.run_main(lam_extra=None)


def _load_records(tmp_path, which):
    name = {"la": "layer_a_shape_only_v1.json",
            "lb": "layer_b_shape_reweight_v1.json"}[which]
    sub = {"la": "layer_a_shape_only", "lb": "layer_b_shape_reweight"}[which]
    batch = json.loads(
        (tmp_path / "phase_m2" / sub / name).read_text(encoding="utf-8"))
    rows = []
    for entry in batch["records_by_config"]:
        rows.extend(entry["records"])
    return rows


# ---------------------------------------------------------------------------
# 11 -- no final-eval leakage into adaptation
# ---------------------------------------------------------------------------
def test_m2_no_final_eval_leakage(tmp_path, monkeypatch):
    bc = _frozen_cfg(_CFG_HI_ESS)

    # instrument the benchmark's oracle interfaces (frozen dataclass ->
    # inject through the object dict only)
    real_logp, real_label = bc.logp, bc.label
    calls: list[tuple[int, str]] = []

    def spy_logp(z):
        calls.append((int(np.asarray(z).shape[0]), "logp"))
        return real_logp(z)

    def spy_label(z):
        calls.append((int(np.asarray(z).shape[0]), "label"))
        return real_label(z)

    object.__setattr__(bc, "logp", staticmethod(spy_logp))
    object.__setattr__(bc, "label", staticmethod(spy_label))

    stage = cp.run_shared_stage(bc, 2026, n_pilot=SMOKE_PILOT, n_eval=1000)
    stage_end = len(calls)

    cands = cp.build_candidates(stage.region, stage.sigma_base)
    spec = cands["C4"]
    prop, _i = cp.build_variant_proposal(stage, spec, cp.LAYER_B)
    cov_finalized_at = len(calls)
    assert cov_finalized_at == stage_end       # freeze consumed NO simulator
    ev = cp.evaluate_variant(stage, prop, 1000)

    # everything drawn after the freeze belongs to the final evaluation
    post_freeze_sizes = [c[0] for c in calls[stage_end:]]
    assert post_freeze_sizes and set(post_freeze_sizes) == {1000}
    # the covariance used region indices strictly INSIDE the pilot arrays
    assert stage.region.region_indices.max() < SMOKE_PILOT


# ---------------------------------------------------------------------------
# 12 -- zero extra simulator calls + honest accounting
# ---------------------------------------------------------------------------
def test_m2_no_extra_simulator_calls(tmp_path, monkeypatch):
    _mini_run(tmp_path, monkeypatch, seeds=(2026,))
    for which in ("la", "lb"):
        for rec in _load_records(tmp_path, which):
            assert rec["cost"]["extra_simulator_calls_covariance"] == 0
            assert rec["cost"]["extra_simulator_calls_covariance"] is not None
            budget_total = 20000 + rec["evaluation"]["n"]
            assert rec["evaluation"]["n"] == 100000      # locked final budget
            assert isinstance(rec["evaluation"]["VRF_budget"], float)
            del budget_total


# ---------------------------------------------------------------------------
# 13 -- machine-readable schema (task Sec. 45)
# ---------------------------------------------------------------------------
def test_m2_result_schema(tmp_path, monkeypatch):
    _mini_run(tmp_path, monkeypatch, seeds=(2027,))
    recs = (_load_records(tmp_path, "la") + _load_records(tmp_path, "lb"))
    assert recs
    for rec in recs:
        for key in REQUIRED_SCHEMA_KEYS:
            assert key in rec, f"missing schema key {key}"
        assert rec["schema_version"] == "raretopo-m2-v0"
        assert rec["h3_tag"] == "RareTopo-H3-v1.0"
        assert rec["m1_tag"] == "RareTopo-M1-v0"
        assert rec["m1d_tag"] == "RareTopo-M1-D-v1.0"
        assert rec["covariance_method"] in ("C0", "C1", "C2", "C3", "C4")
        assert rec["layer"] in ("shape_only", "shape_reweight")
        assert rec["eta"] == 0.8
        assert rec["pilot"]["n"] == 20000 and rec["pilot"]["alpha_p"] == 0.5
        vr = rec["variance_region"]
        for k in ("n_region", "ess_v", "centroid", "cov_raw", "eig_raw"):
            assert k in vr
        cv = rec["covariance"]
        for k in ("lambda", "sigma_pre", "sigma_final", "eig_pre",
                  "eig_final", "clipped_low", "clipped_high",
                  "legality_passed", "hold"):
            assert k in cv
        evalu = rec["evaluation"]
        for k in ("n", "P_hat", "M2_hat", "VRF_proposal", "VRF_budget",
                  "mode_L"):
            assert k in evalu
        assert isinstance(cv["legality_passed"], bool)
        assert isinstance(cv["hold"], bool)
        # tags/hash coherence with parent freeze audit data
        from hyptraj.m1d.experiments import load_freeze
        assert rec["benchmark_hash"]


# ---------------------------------------------------------------------------
# 14 -- leakage redistribution metrics
# ---------------------------------------------------------------------------
def test_m2_leakage_redistribution_metrics():
    L0 = {"S2": 4.0, "S3": 2.0, "S4": 0.5}
    L_new = {"S2": 2.0, "S3": 3.0, "S4": 0.25}         # selected=S2 improved
    out = leakage_ratios(L_new, L0, selected_mode="S2")
    assert out["R_L_table"]["S2"] == pytest.approx(0.5)
    assert out["selected_mode_leakage_ratio"] == pytest.approx(0.5)
    assert out["max_off_target_leakage_ratio"] == pytest.approx(1.5)
    assert out["sum_off_target_leakage"] == pytest.approx(3.25)

    # zero-C0 side handled explicitly instead of silently
    out2 = leakage_ratios({"S2": 1.0, "S4": 0.5}, {"S2": 1.0}, "S2")
    assert out2["R_L_table"]["S4"] == float("inf")
    assert out2["max_off_target_leakage_ratio"] == float("inf")

    out3 = leakage_ratios({}, {"S3": 1.0}, None)
    assert out3["R_L_table"]["S3"] == 0.0
    assert out3["max_off_target_leakage_ratio"] == 0.0   # no off-target modes

    # record builder round trip carries the block verbatim
    rec = build_trial_record(
        benchmark_hash="x" * 64, config_id="c", seed=1, layer="shape_only",
        covariance_method="C4", selected_mode="S2", eta=0.8, pilot_n=20000,
        alpha_p=0.5, region={"n_region": 5},
        covariance_block={"hold": False}, evaluation={"mode_L": L_new})
    assert rec["variance_region"]["n_region"] == 5
    assert rec["evaluation"]["mode_L"]["S2"] == 2.0
