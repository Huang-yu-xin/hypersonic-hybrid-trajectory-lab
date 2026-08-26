"""M1 v0 -- closed-loop Discover + Add + Reweight iteration (task Sec. 10).

Skeleton per task Sec. 10.1:

    1. draw pilot samples from the declared proposal r = q_t
    2. run the exact event / topology oracle (labels supplied by caller)
    3. evaluate p, q_t, r_t
    4. estimate nu_V^(q_t)          (variance_measure)
    5. estimate M2, L_k, omega_k^V  (variance_measure)
    6. mode-level uncertainty diagnostics (bootstrap LCB, ESS)
    7. search for unrepresented variance-important mode (mode_discovery)
       -> HOLD or ADD_COMPONENT(+UPDATE_WEIGHTS)
    8. repeat with q_{t+1}
    9. stop by the preregistered rule (Sec. 17)
    10. freeze q_final
    11. independent final evaluation (caller-provided evaluator)

Stop rule (task Sec. 17, frozen): max 3 adaptation iterations; stop when no
mode passes the birth gate; when every observed variance-important mode is
represented; when relative M2 improvement of an update < 0.02 on an
independent diagnostic pilot; on validity / legality failure.

HOLD is always available (task Sec. 16): no forced modification.  The
adaptation firewall (task Sec. 18): the pilot for round t+1 is always drawn
from the frozen q_{t+1}; final evaluation samples are generated only after
q_final is frozen and are never used for adaptation.

Semantic-fix lifecycle (issue 8 of the freeze audit): the pilot of round
t+1 doubles as the independent diagnostic for round t's update, so each
round costs exactly one pilot (no extra diagnostic draw).  Budget
accounting is recorded per round and asserted against the preregistered
nominal limit ``max_iterations * pilot_n`` (+ final evaluation budget held
outside, task Sec. 19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from hyptraj.m1.mode_discovery import diagnose_missing_mode
from hyptraj.m1.proposal_update import (
    MixtureProposal,
    add_component,
    eta_region_centroid,
    update_weights,
)
from hyptraj.m1.variance_measure import estimate_variance_measure, variance_mass_weights

# frozen v0 stop rule constants (config m1_closed_loop_v0.json)
MAX_ADAPTATION_ITERATIONS = 3
M2_RELATIVE_STOP_THRESHOLD = 0.02
ETA_MAIN = 0.8


@dataclass(frozen=True)
class ClosedLoopIteration:
    iteration: int
    pilot_n: int
    action: str                      # "HOLD" | "ADD_COMPONENT" (+UPDATE_WEIGHTS)
    M2_hat: float
    M2_hat_prev: float | None
    candidate_mode: str | None
    mode_stats: tuple = ()           # tuples of ModeStat
    proposal_after: MixtureProposal | None = None
    weight_result: dict = field(default_factory=dict)  # solver convergence (Sec. 31)
    stop_reason: str | None = None
    # budget accounting (freeze audit issue 8)
    pilot_calls: int = 0
    cumulative_adaptation_calls: int = 0


@dataclass(frozen=True)
class ClosedLoopResult:
    seed: int
    initial_proposal: MixtureProposal
    final_proposal: MixtureProposal
    iterations: tuple[ClosedLoopIteration, ...]
    stop_reason: str
    n_pilot_calls: int
    total_calls: int
    budget: dict = field(default_factory=dict)


def run_closed_loop(
    *,
    seed: int,
    initial_proposal: MixtureProposal,
    label_oracle: Callable[[np.ndarray], np.ndarray],
    logp_fn: Callable[[np.ndarray], np.ndarray],
    nominal_topology: str,
    pilot_n: int = 20_000,
    pilot_policy: str = "proposal",
    pilot_alpha: float = 0.5,
    max_iterations: int = MAX_ADAPTATION_ITERATIONS,
    tau_birth_main: float = 0.10,
    tau_birth_lower_confidence: float = 0.05,
    min_mode_observations: int = 5,
    weight_floor: float = 0.0,
    m2_stop_threshold: float = M2_RELATIVE_STOP_THRESHOLD,
    n_bootstrap: int = 200,
    seed_bootstrap: int = 2026,
    rng_in: np.random.Generator | None = None,
    eta_main: float = ETA_MAIN,
    birth_signal: str = "variance",
    reweight_after_birth: bool = True,
    center_method: str = "eta_centroid",
    weight_mode: str = "m2_opt",
) -> ClosedLoopResult:
    """Run the v0 closed loop: Discover + Add + Reweight until the stop rule.

    ``label_oracle(z)`` returns the exact topology label per row (event =
    label != nominal); ``logp_fn(z)`` is the log target density.  The pilot of
    each round has size ``pilot_n`` drawn from the DECLARED ``r_t``:

    - ``pilot_policy="proposal"``: ``r_t = q_t`` (``pilot_alpha=0``);
    - ``pilot_policy="mix"`` (also accepted legacy name "mix_50"): fraction
      ``pilot_alpha`` of the calls from the target ``p`` (exploration; v0
      main config ``alpha = 0.5``, declared in
      ``configs/m1_closed_loop_v0.json``) and the rest from ``q_t`` -- legal
      mixed pilot (task Sec. 7 / 29.2), each sample keeps its own ``r_i``
      and its SOURCE STRATUM (stratified bootstrap, freeze audit issue 6).

    All pilots are independent of previous ones (adaptation firewall); the
    weight-fit samples are the frozen pilot of the birth round; the pilot of
    round t+1 doubles as the independent diagnostic of round t's update
    (reused-call accounting, freeze audit issue 8).

    Ablation / audit switches (defaults = v0 main configuration):

    - ``birth_signal``: "variance" (v0) / "probability" (Ablation A) /
      "probability_top" (threshold-free probability comparator);
    - ``reweight_after_birth``: False disables UPDATE_WEIGHTS (Ablation B);
    - ``center_method``: "eta_centroid" (v0, H3-3A HDR region centroid) /
      "max_weight_point" (Ablation D) / "probability_centroid" (probability
      comparator: IS-weight centroid, NO variance geometry);
    - ``eta_main``: eta for the centroid region (Ablation E;
      frozen sensitivity set 0.5 / 0.8 / 0.9, main = 0.8);
    - ``weight_mode``: "m2_opt" (v0, frozen SLSQP) / "probability"
      (probability comparator: mixture weights by normalized P_k_hat).
    """
    rng = np.random.default_rng(seed) if rng_in is None else rng_in
    proposal = initial_proposal
    iterations: list[ClosedLoopIteration] = []
    pilot_calls = 0
    stop_reason = "max_iterations"

    def _draw_pilot(
        n: int, prop: MixtureProposal
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(z, logr, source_strata)`` for ``n`` calls.

        ``source_strata``: 1 = q-source, 0 = p-source (kept per sample for
        the stratified bootstrap, freeze audit issue 6).
        """
        alpha = 0.0 if pilot_policy in ("proposal", "proposal_only") else (
            pilot_alpha if pilot_policy in ("mix", "mix_50") else None)
        if alpha is None:
            raise ValueError(f"unknown pilot_policy {pilot_policy!r}")
        n_p = int(round(n * alpha))
        n_q = n - n_p
        zp = rng.standard_normal((n_p, prop.centers.shape[1]))
        rp = logp_fn(zp)                                  # r = p
        zq = prop.sample(rng, n_q)
        rq = prop.log_density(zq)                         # r = q
        if n_p:
            z = np.vstack([zp, zq])
            logr = np.concatenate([rp, rq])
            strata = np.concatenate([np.zeros(n_p, dtype=int),
                                     np.ones(n_q, dtype=int)])
        else:
            z, logr, strata = zq, rq, np.ones(n_q, dtype=int)
        return z, logr, strata

    budget_limit = max_iterations * pilot_n               # nominal adaptation budget

    for t in range(max_iterations + 1):
        z, logr, strata = _draw_pilot(pilot_n, proposal)
        pilot_calls += pilot_n
        logp = logp_fn(z)
        labels = label_oracle(z)
        indicators = (labels != nominal_topology).astype(float)
        vm = estimate_variance_measure(
            z, proposal.centers, proposal.weights, logp, logr, labels, nominal_topology
        )

        diag = diagnose_missing_mode(
            z, proposal.centers, proposal.weights, logp, logr, labels,
            nominal_topology,
            component_mode_ids=set(proposal.component_mode_ids),
            tau_birth_main=tau_birth_main,
            tau_birth_lower_confidence=tau_birth_lower_confidence,
            min_mode_observations=min_mode_observations,
            n_bootstrap=n_bootstrap,
            rng=np.random.default_rng(seed_bootstrap + t),
            birth_signal=birth_signal,
            source_strata=strata,
        )

        m2_prev = iterations[-1].M2_hat if iterations else None
        last_was_add = bool(iterations) and iterations[-1].action == "ADD_COMPONENT"

        # ---- stop rule (task Sec. 17) ----
        if vm.M2_hat != vm.M2_hat or not np.isfinite(vm.M2_hat):
            stop_reason = "invalid_M2_or_legality"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=None, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
                pilot_calls=pilot_n,
                cumulative_adaptation_calls=pilot_calls,
            ))
            break
        if t >= max_iterations:
            stop_reason = "max_adaptation_iterations"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=None, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
                pilot_calls=pilot_n,
                cumulative_adaptation_calls=pilot_calls,
            ))
            break
        # condition 3: after an update, relative M2 improvement < 0.02 on the
        # independent (reused) diagnostic pilot of the current round
        if last_was_add and m2_prev is not None and m2_prev > 0:
            rel = (m2_prev - vm.M2_hat) / m2_prev
            if rel < m2_stop_threshold:
                stop_reason = "m2_relative_improvement_below_threshold"
                iterations.append(ClosedLoopIteration(
                    iteration=t, pilot_n=pilot_n, action="HOLD",
                    M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                    candidate_mode=diag.candidate_mode, mode_stats=diag.mode_stats,
                    stop_reason=stop_reason,
                    pilot_calls=pilot_n,
                    cumulative_adaptation_calls=pilot_calls,
                ))
                break
        if diag.action == "HOLD":
            stop_reason = "no_missing_mode"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=None, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
                pilot_calls=pilot_n,
                cumulative_adaptation_calls=pilot_calls,
            ))
            break

        # ---- ADD_COMPONENT ----
        cand = str(diag.candidate_mode)
        try:
            if center_method == "eta_centroid":
                new_center, centroid_eta_used = eta_region_centroid(
                    z, logp, logr, proposal.weights, proposal.centers,
                    labels, nominal_topology, mode=cand, eta=eta_main,
                )
            elif center_method == "max_weight_point":
                # Ablation D: single highest variance-mass pilot observation
                wt = variance_mass_weights(
                    z, proposal.centers, proposal.weights, logp, logr,
                    (labels == cand).astype(float),
                )
                new_center = z[int(np.argmax(wt))]
                centroid_eta_used = 1.0
            elif center_method == "probability_centroid":
                # probability comparator: IS-weight (p/r) centroid, no variance
                # geometry (freeze audit issue 4)
                mask = (labels == cand).astype(float)
                wp = np.exp(np.asarray(logp, dtype=float)
                            - np.asarray(logr, dtype=float)) * mask
                new_center = np.sum(wp[:, None] * z, axis=0) / float(wp.sum())
                centroid_eta_used = 1.0
            else:
                raise ValueError(f"unknown center_method {center_method!r}")
        except (ValueError, ZeroDivisionError) as exc:
            stop_reason = f"centroid_failed: {exc}"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=cand, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
                pilot_calls=pilot_n,
                cumulative_adaptation_calls=pilot_calls,
            ))
            break
        proposal_next = add_component(proposal, new_center, mode_id=cand)

        # ---- UPDATE_WEIGHTS ----
        if not reweight_after_birth:
            # Ablation B: Discover + Add only -- naive split weights kept
            wres = {
                "success": True, "message": "ablation_B_no_reweight",
                "kkt_residue": float("nan"),
                "objective_init": float("nan"),
                "objective_final": float("nan"),
                "n_iter": 0,
            }
        elif weight_mode == "probability":
            # probability comparator: mixture weights by normalized P_k_hat
            p_hats = []
            for mid in proposal_next.component_mode_ids:
                mask = (labels == mid).astype(float)
                p_hats.append(float(np.mean(
                    mask * np.exp(np.asarray(logp, dtype=float)
                                  - np.asarray(logr, dtype=float)))))
            p_hats = np.maximum(np.asarray(p_hats, dtype=float), 1e-12)
            p_hats = p_hats / p_hats.sum()
            proposal_next = MixtureProposal(
                centers=proposal_next.centers, weights=p_hats,
                component_mode_ids=proposal_next.component_mode_ids,
            )
            wres = {
                "success": True, "message": "probability_weights",
                "kkt_residue": float("nan"),
                "objective_init": float("nan"),
                "objective_final": float("nan"),
                "n_iter": 0,
            }
        else:
            try:
                proposal_next, wres = update_weights(
                    proposal_next, z, logp, logr, indicators, floor=weight_floor
                )
            except RuntimeError:
                stop_reason = "optimizer_non_convergence"
                iterations.append(ClosedLoopIteration(
                    iteration=t, pilot_n=pilot_n, action="HOLD",
                    M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                    candidate_mode=cand, mode_stats=diag.mode_stats,
                    stop_reason=stop_reason,
                    pilot_calls=pilot_n,
                    cumulative_adaptation_calls=pilot_calls,
                ))
                break

        _wres = wres if isinstance(wres, dict) else {
            "success": wres.success, "message": wres.message,
            "kkt_residue": wres.kkt_residue,
            "objective_init": wres.objective_init,
            "objective_final": wres.objective_final,
            "n_iter": wres.n_iter,
        }
        iterations.append(ClosedLoopIteration(
            iteration=t, pilot_n=pilot_n, action="ADD_COMPONENT",
            M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
            candidate_mode=cand, mode_stats=diag.mode_stats,
            proposal_after=proposal_next,
            weight_result={**_wres, "centroid_eta_used": centroid_eta_used},
            stop_reason=None,
            pilot_calls=pilot_n,
            cumulative_adaptation_calls=pilot_calls,
        ))
        proposal = proposal_next

    budget = {
        "pilot_calls_total": pilot_calls,
        "diagnostic_calls_total": 0,      # diagnostic reused as next pilot
        "reused_calls_total": max(0, len(iterations) - 1) * pilot_n,
        "new_calls_total": pilot_calls,
        "cumulative_adaptation_calls": pilot_calls,
        "budget_limit": budget_limit,
        "assertion_passed": bool(pilot_calls <= budget_limit),
    }
    assert budget["assertion_passed"], (
        f"adaptation budget exceeded: {pilot_calls} > {budget_limit}"
    )
    return ClosedLoopResult(
        seed=seed,
        initial_proposal=initial_proposal,
        final_proposal=proposal,
        iterations=tuple(iterations),
        stop_reason=stop_reason,
        n_pilot_calls=pilot_calls,
        total_calls=pilot_calls,
        budget=budget,
    )


__all__ = [
    "ClosedLoopIteration",
    "ClosedLoopResult",
    "run_closed_loop",
    "MAX_ADAPTATION_ITERATIONS",
    "M2_RELATIVE_STOP_THRESHOLD",
    "ETA_MAIN",
]