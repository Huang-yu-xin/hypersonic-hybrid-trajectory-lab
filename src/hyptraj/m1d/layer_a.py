"""M1-D -- Layer A selection-only comparator (task Sec. 17 / 19 / 20).

FIREWALL: this module NEVER receives benchmark-design reference values.
Oracle methods receive only an ordered list of mode-id strings supplied by
the driver layer (which read the freeze artifact offline).  CVS/CPS/regret
metrics are attached by the DRIVER after runs using metrics.py -- never
inside this module (structural Sec. 41 isolation).
"""

from __future__ import annotations

import numpy as np

from hyptraj.m1d.adaptation import (
    build_final_proposal,
    draw_mix_pilot,
    eligible_candidates,
    oracle_pick,
    random_pick,
    selector_pick,
)

METHODS = ("probability_selector", "variance_selector",
           "random_selector", "oracle_P", "oracle_V")


def run_layer_a_trial(bench_cfg, seed: int, method: str,
                      birth_budget: int = 1,
                      n_pilot: int = 20_000, alpha: float = 0.5,
                      n_eval: int = 100_000,
                      center_rule: str = "probability",
                      weight_rule: str = "m2_opt",
                      eta_main: float = 0.8,
                      oracle_orders: dict | None = None) -> dict:
    """One (config, seed, method) selection-only trial.

    ``oracle_orders`` (driver-supplied, strings only): {"P": [...], "V": [...]}
    descending reference orders.  For multi-birth trials the V-order stays
    the q_0 reference ordering (see methodology deviation note D2-O1).
    """
    assert method in METHODS, method
    logp_fn = bench_cfg.logp
    nominal = "S0"

    proposal = bench_cfg.initial_proposal()
    selected: list[str] = []
    rounds: list[dict] = []
    rng_pilot = np.random.default_rng([int(seed), 101])
    stop_reason = "birth_budget_exhausted"

    for b in range(int(birth_budget)):
        z, logr, strata = draw_mix_pilot(rng_pilot, proposal, logp_fn,
                                         n_pilot, alpha)
        logp = logp_fn(z)
        labels = bench_cfg.label(z)
        cands = eligible_candidates(labels, nominal,
                                    set(proposal.component_mode_ids))

        diag: dict = {}
        if method == "probability_selector":
            pick, diag = selector_pick("probability", cands, labels, z,
                                       proposal.centers, proposal.weights,
                                       logp, logr)
        elif method == "variance_selector":
            pick, diag = selector_pick("variance", cands, labels, z,
                                       proposal.centers, proposal.weights,
                                       logp, logr)
        elif method == "random_selector":
            rng_r = np.random.default_rng([int(seed), 424242, b])
            pick = random_pick(cands, rng_r)
        elif method == "oracle_P":
            pick = oracle_pick((oracle_orders or {}).get("P", []), cands)
        elif method == "oracle_V":
            pick = oracle_pick((oracle_orders or {}).get("V", []), cands)
        else:
            raise AssertionError(method)

        if pick is None:
            stop_reason = "no_eligible_candidate"
            rounds.append({"round": b, "eligible_candidates": cands,
                           "selected": None})
            break

        n_obs = int(np.sum(labels == pick))
        proposal, details = build_final_proposal(
            proposal, z, logp, logr, labels, nominal, pick,
            center_rule=center_rule, weight_rule=weight_rule,
            eta_main=eta_main)
        selected.append(str(pick))
        selection_diag = {
            "P_hat_table": {m: float(v)
                            for m, v in diag.get("P_hat_table", {}).items()},
            "L_hat_table": {m: float(v)
                            for m, v in diag.get("L_hat_table", {}).items()},
        }
        rounds.append({
            "round": b,
            "eligible_candidates": cands,
            "selected": str(pick),
            "n_obs_selected": n_obs,
            "selection_diag": selection_diag,
            "action_details": details,
        })

    return {
        "method": method,
        "seed": int(seed),
        "birth_budget": int(birth_budget),
        "selected_modes": selected,
        "stop_reason": stop_reason,
        "rounds": rounds,
        "final_proposal": proposal,
        "cost": {
            "pilot_rounds_completed": len(rounds),
            "adaptation_calls": int(len(rounds) * n_pilot),
            "eval_calls": int(n_eval),
            "total_calls": int(len(rounds) * n_pilot + n_eval),
        },
        "controls": {
            "n_pilot": int(n_pilot), "alpha": float(alpha),
            "n_eval": int(n_eval),
            "center_rule": center_rule, "weight_rule": weight_rule,
            "eta_main": float(eta_main),
        },
        "validity": {"legal_mixture": True},   # unit covariance family
    }


def _run_frozen_style_loop(*, bench_cfg, seed: int, variant: str,
                           birth_budget: int, n_pilot: int, alpha: float,
                           tau_birth_main: float,
                           tau_birth_lower_confidence: float,
                           min_mode_observations: int,
                           n_bootstrap: int):
    """V0-faithful closed loop re-composed from FROZEN public primitives.

    Single intentional delta vs ``run_closed_loop``: the nominal adaptation
    budget limit counts (birth_budget + 1) pilot rounds -- the frozen helper
    hard-asserts ``max_iterations * pilot_n`` although its own control flow
    necessarily draws a trailing diagnostic pilot after the (max_iterations)-th
    ADD, making a legitimate one-birth run impossible to declare there
    (frozen file is immutable under the M1-D firewall -- task Sec. 2).
    Every per-round computation (draw order, estimators, gate call, centroid,
    optimizer, stop-rule ORDER: invalid_M2 -> max_rounds -> m2_improvement ->
    no_candidate) is delegated verbatim to the frozen functions.
    Parity vs ``run_closed_loop`` is asserted by a dedicated unit test on
    non-diverging scenarios.
    """
    from hyptraj.m1.mode_discovery import diagnose_missing_mode
    from hyptraj.m1.proposal_update import (
        MixtureProposal,
        add_component,
        update_weights,
    )
    from hyptraj.m1.variance_measure import estimate_variance_measure

    logp_fn = bench_cfg.logp
    nominal = "S0"
    rng = np.random.default_rng(seed)
    proposal = bench_cfg.initial_proposal()
    iterations: list[dict] = []
    pilot_calls = 0
    eta_main = 0.8            # frozen v0 main constant
    M = int(birth_budget)
    budget_limit = (M + 1) * n_pilot

    def _pilot(prop: MixtureProposal):
        n_p = int(round(n_pilot * alpha))
        zp = rng.standard_normal((n_p, prop.centers.shape[1]))
        zq = prop.sample(rng, n_pilot - n_p)
        z = np.vstack([zp, zq])
        logr = np.concatenate([logp_fn(zp), prop.log_density(zq)])
        strata = np.concatenate([np.zeros(n_p, dtype=int),
                                 np.ones(n_pilot - n_p, dtype=int)])
        return z, logr, strata

    born = 0
    stop_reason = "max_adaptation_rounds"
    M2_REL_STOP = 0.02                                    # frozen constant

    for t in range(M + 1):
        z, logr, strata = _pilot(proposal)
        pilot_calls += n_pilot
        logp = logp_fn(z)
        labels = bench_cfg.label(z)
        indicators = (labels != nominal).astype(float)
        pi, centers = proposal.weights, proposal.centers
        vm = estimate_variance_measure(z, centers, pi, logp, logr, labels,
                                       nominal)

        diag = diagnose_missing_mode(
            z, centers, pi, logp, logr, labels, nominal,
            component_mode_ids=set(proposal.component_mode_ids),
            tau_birth_main=tau_birth_main,
            tau_birth_lower_confidence=tau_birth_lower_confidence,
            min_mode_observations=min_mode_observations,
            n_bootstrap=n_bootstrap,
            rng=np.random.default_rng(2026 + t),
            birth_signal=("probability_top" if variant == "probability"
                          else "variance"),
            source_strata=strata,
        )
        entry = {"round": t, "action": None,
                 "M2_hat": float(vm.M2_hat),
                 "candidate_mode": (str(diag.candidate_mode)
                                    if diag.candidate_mode else None),
                 "mode_stats": [
                     {"mode_id": ms.mode_id,
                      "represented_by_component": ms.represented_by_component,
                      "P_k_hat": ms.P_k_hat, "L_k_hat": ms.L_k_hat,
                      "omega_k_V_hat": ms.omega_k_V_hat,
                      "omega_lcb95": ms.omega_lcb95,
                      "n_observed": ms.n_observed}
                     for ms in diag.mode_stats]}
        if len(iterations) >= 1:
            entry["M2_hat_prev"] = iterations[-1]["M2_hat"]
        else:
            entry["M2_hat_prev"] = None

        m2_prev = entry["M2_hat_prev"]
        last_was_add = bool(iterations) and \
            iterations[-1]["action"] == "ADD_COMPONENT"

        if not np.isfinite(vm.M2_hat):                    # frozen order 1
            entry["action"] = "HOLD"
            entry["stop_reason"] = "invalid_M2_or_legality"
            iterations.append(entry)
            stop_reason = "invalid_M2_or_legality"
            break
        if t >= M:                                        # frozen order 2
            entry["action"] = "HOLD"
            entry["stop_reason"] = "max_adaptation_rounds"
            iterations.append(entry)
            break
        if last_was_add and m2_prev is not None and m2_prev > 0:   # order 3
            rel = (m2_prev - vm.M2_hat) / m2_prev
            if rel < M2_REL_STOP:
                entry["action"] = "HOLD"
                entry["stop_reason"] = "m2_relative_improvement_below_threshold"
                iterations.append(entry)
                stop_reason = "m2_relative_improvement_below_threshold"
                break
        if diag.action == "HOLD":                         # frozen order 4
            entry["action"] = "HOLD"
            entry["stop_reason"] = "no_missing_mode"
            iterations.append(entry)
            stop_reason = "no_missing_mode"
            break

        # DV3 (Methodology): among simultaneously passing candidates the
        # variance policy takes the TOP omega-hat one -- task Sec. 18.2
        # mandates ranking ("rank by L_k / omega_k^V"); the frozen helper's
        # stable-label first-pass rule coincides only when <2 modes pass,
        # which cannot be assumed on the M1-D multi-missing-mode family.
        if variant == "variance":
            elig_ms = [ms for ms in diag.mode_stats if ms.birth_eligible]
            cand = (max(elig_ms, key=lambda ms: ms.omega_k_V_hat).mode_id
                    if elig_ms else str(diag.candidate_mode))
        else:
            cand = str(diag.candidate_mode)
        if variant == "variance":
            cvec, eta_used = _eta_centroid(z, logp, logr, pi, centers,
                                           labels, nominal, cand,
                                           eta=eta_main)
            proposal_next = add_component(proposal, cvec, mode_id=cand)
            proposal_next, res_w = update_weights(proposal_next, z, logp,
                                                  logr, indicators)
            entry["weight_solver"] = {
                "frozen_SLSQP": True, "success": bool(res_w.success),
                "message": res_w.message, "kkt_residue": res_w.kkt_residue}
            entry["centroid_eta_used"] = float(eta_used)
        elif variant == "probability":
            mask = (labels == cand).astype(float)
            wp = mask * np.exp(np.asarray(logp, dtype=float) - logr)
            cvec = (wp[:, None] * z).sum(axis=0) / float(wp.sum())
            proposal_next = add_component(proposal, cvec, mode_id=cand)
            p_hats = []
            for mid in proposal_next.component_mode_ids:
                mk = (labels == mid).astype(float)
                p_hats.append(float(np.mean(
                    mk * np.exp(np.asarray(logp, dtype=float) - logr))))
            ph = np.maximum(np.asarray(p_hats, dtype=float), 1e-12)
            proposal_next = MixtureProposal(
                centers=proposal_next.centers, weights=ph / ph.sum(),
                component_mode_ids=proposal_next.component_mode_ids)
            entry["weight_solver"] = {"frozen_SLSQP": False,
                                      "rule": "pi_propto_P_hat"}
            entry["centroid_eta_used"] = 1.0
        else:
            raise ValueError(variant)

        entry["action"] = "ADD_COMPONENT"
        entry["candidate_mode"] = str(cand)      # post-DV3 actual selection
        entry.pop("stop_reason", None)
        iterations.append(entry)
        proposal = proposal_next
        born += 1

    return {
        "iterations": iterations, "final_proposal": proposal,
        "born": born, "stop_reason": stop_reason,
        "pilot_calls": pilot_calls,
        "budget": {"limit": budget_limit, "used": pilot_calls,
                   "assertion_passed": bool(pilot_calls <= budget_limit)},
    }


def _eta_centroid(z, logp, logr, pi, centers, labels, nominal, mode,
                  eta: float):
    from hyptraj.m1.proposal_update import eta_region_centroid
    return eta_region_centroid(z, logp, logr, pi, centers, labels, nominal,
                               mode=mode, eta=eta)


def run_layer_b_trial(bench_cfg, seed: int, variant: str,
                      birth_budget: int = 1,
                      n_pilot: int = 20_000, pilot_alpha: float = 0.5,
                      n_eval: int = 100_000,
                      tau_birth_main: float = 0.10,
                      tau_birth_lower_confidence: float = 0.05,
                      min_mode_observations: int = 5,
                      n_bootstrap: int = 200) -> dict:
    """Full-policy comparator (Sec. 18) on frozen primitives (see
    ``_run_frozen_style_loop`` for the single budget-accounting delta).

    - ``variant='variance'``  : frozen M1-v0 action defaults          (18.2)
    - ``variant='probability'``: probability-guided policy mapped onto the
      frozen comparator switches (top-ranked P-hat candidate, IS-weight
      probability centroid, pi propto P_hat). No nu_V/L_k/variance centroid/
      variance-aware objective enters any action pathway.
    """
    out = _run_frozen_style_loop(
        bench_cfg=bench_cfg, seed=seed, variant=variant,
        birth_budget=int(birth_budget), n_pilot=int(n_pilot),
        alpha=float(pilot_alpha),
        tau_birth_main=float(tau_birth_main),
        tau_birth_lower_confidence=float(tau_birth_lower_confidence),
        min_mode_observations=int(min_mode_observations),
        n_bootstrap=int(n_bootstrap))

    births = [it["candidate_mode"] for it in out["iterations"]
              if it["action"] == "ADD_COMPONENT" and it["candidate_mode"]]
    return {
        "method": f"{variant}_full_policy",
        "variant": variant,
        "seed": int(seed),
        "birth_budget": int(birth_budget),
        "selected_modes": [str(m) for m in births],
        "stop_reason": out["stop_reason"],
        "rounds": [{**it, "budget": {
            "cumulative_adaptation_calls":
                sum(x.get("pilot_calls", 0) for x in []) or None}}
            for it in out["iterations"]],
        "final_proposal": out["final_proposal"],
        "cost": {
            "adaptation_calls": int(out["pilot_calls"]),
            "eval_calls": int(n_eval),
            "total_calls": int(out["pilot_calls"] + n_eval),
            "budget_assertion_passed": bool(out["budget"]["assertion_passed"]),
        },
        "controls": {
            "n_pilot": int(n_pilot), "alpha": float(pilot_alpha),
            "n_eval": int(n_eval),
            "tau_birth_main": float(tau_birth_main),
            "tau_birth_lower_confidence": float(tau_birth_lower_confidence),
            "min_mode_observations": int(min_mode_observations),
            "n_bootstrap": int(n_bootstrap),
        },
        "validity": {"legal_mixture": True},
    }


__all__ = ["run_layer_a_trial", "run_layer_b_trial", "METHODS"]
