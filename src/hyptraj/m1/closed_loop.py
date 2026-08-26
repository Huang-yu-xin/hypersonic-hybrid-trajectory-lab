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
from hyptraj.m1.variance_measure import estimate_variance_measure

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


@dataclass(frozen=True)
class ClosedLoopResult:
    seed: int
    initial_proposal: MixtureProposal
    final_proposal: MixtureProposal
    iterations: tuple[ClosedLoopIteration, ...]
    stop_reason: str
    n_pilot_calls: int
    total_calls: int


def run_closed_loop(
    *,
    seed: int,
    initial_proposal: MixtureProposal,
    label_oracle: Callable[[np.ndarray], np.ndarray],
    logp_fn: Callable[[np.ndarray], np.ndarray],
    nominal_topology: str,
    pilot_n: int = 20_000,
    pilot_policy: str = "proposal",
    max_iterations: int = MAX_ADAPTATION_ITERATIONS,
    tau_birth_main: float = 0.10,
    tau_birth_lower_confidence: float = 0.05,
    min_mode_observations: int = 5,
    weight_floor: float = 0.0,
    m2_stop_threshold: float = M2_RELATIVE_STOP_THRESHOLD,
    n_bootstrap: int = 200,
    seed_bootstrap: int = 2026,
    rng_in: np.random.Generator | None = None,
) -> ClosedLoopResult:
    """Run the v0 closed loop: Discover + Add + Reweight until the stop rule.

    ``label_oracle(z)`` returns the exact topology label per row (event =
    label != nominal); ``logp_fn(z)`` is the log target density.  The pilot of
    each round has size ``pilot_n`` drawn from the DECLARED ``r_t``:

    - ``pilot_policy="proposal"`` (default): ``r_t = q_t``;
    - ``pilot_policy="mix_50"`` (v0 choice on the H3-1 benchmark, declared in
      ``configs/m1_closed_loop_v0.json``): half the calls from ``q_t``, half
      from the target ``p`` -- legal mixed pilot (task Sec. 7 / 29.2),
      each sample keeps its own ``r_i``.

    All pilots are independent of previous ones (adaptation firewall); the
    weight-fit samples are the frozen pilot of the birth round.
    """
    rng = np.random.default_rng(seed) if rng_in is None else rng_in
    proposal = initial_proposal
    iterations: list[ClosedLoopIteration] = []
    pilot_calls = 0
    stop_reason = "max_iterations"

    def _draw_pilot(n: int, prop: MixtureProposal) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(z, logr)`` for ``n`` calls under the declared policy."""
        if pilot_policy == "proposal":
            z = prop.sample(rng, n)
            return z, prop.log_density(z)
        if pilot_policy == "mix_50":
            half = n // 2
            z1 = prop.sample(rng, half)
            r1 = prop.log_density(z1)
            z2 = rng.standard_normal((n - half, prop.centers.shape[1]))
            r2 = logp_fn(z2)                  # r = p (target MC)
            return np.vstack([z1, z2]), np.concatenate([r1, r2])
        raise ValueError(f"unknown pilot_policy {pilot_policy!r}")

    for t in range(max_iterations + 1):
        z, logr = _draw_pilot(pilot_n, proposal)
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
        )

        m2_prev = iterations[-1].M2_hat if iterations else None

        # ---- stop rule (task Sec. 17) ----
        if vm.M2_hat != vm.M2_hat or not np.isfinite(vm.M2_hat):
            stop_reason = "invalid_M2_or_legality"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=None, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
            ))
            break
        if t >= max_iterations:
            stop_reason = "max_adaptation_iterations"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=None, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
            ))
            break
        if diag.action == "HOLD":
            stop_reason = "no_missing_mode"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=None, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
            ))
            break

        # ---- ADD_COMPONENT + UPDATE_WEIGHTS ----
        try:
            new_center, centroid_eta_used = eta_region_centroid(
                z, logp, logr, proposal.weights, proposal.centers,
                labels, nominal_topology, mode=diag.candidate_mode, eta=ETA_MAIN,
            )
        except ValueError as exc:
            stop_reason = f"centroid_failed: {exc}"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=diag.candidate_mode, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
            ))
            break
        proposal_next = add_component(
            proposal, new_center, mode_id=str(diag.candidate_mode)
        )
        try:
            proposal_next, wres = update_weights(
                proposal_next, z, logp, logr, indicators, floor=weight_floor
            )
        except RuntimeError:
            stop_reason = "optimizer_non_convergence"
            iterations.append(ClosedLoopIteration(
                iteration=t, pilot_n=pilot_n, action="HOLD",
                M2_hat=vm.M2_hat, M2_hat_prev=m2_prev,
                candidate_mode=diag.candidate_mode, mode_stats=diag.mode_stats,
                stop_reason=stop_reason,
            ))
            break

        # independent diagnostic pilot for the relative-improvement stop rule:
        z_diag, logr_diag = _draw_pilot(pilot_n, proposal_next)
        pilot_calls += pilot_n
        logp_diag = logp_fn(z_diag)
        labels_diag = label_oracle(z_diag)
        vm_next = estimate_variance_measure(
            z_diag, proposal_next.centers, proposal_next.weights,
            logp_diag, logr_diag, labels_diag, nominal_topology,
        )
        rel_improvement = (vm.M2_hat - vm_next.M2_hat) / vm.M2_hat if vm.M2_hat > 0 else 0.0
        iterations.append(ClosedLoopIteration(
            iteration=t, pilot_n=pilot_n, action="ADD_COMPONENT",
            M2_hat=vm_next.M2_hat, M2_hat_prev=vm.M2_hat,
            candidate_mode=diag.candidate_mode, mode_stats=diag.mode_stats,
            proposal_after=proposal_next,
            weight_result={
                "success": wres.success,
                "message": wres.message,
                "kkt_residue": wres.kkt_residue,
                "objective_init": wres.objective_init,
                "objective_final": wres.objective_final,
                "n_iter": wres.n_iter,
                "centroid_eta_used": centroid_eta_used,
            },
            stop_reason=None,
        ))
        proposal = proposal_next
        if rel_improvement < m2_stop_threshold:
            stop_reason = "m2_relative_improvement_below_threshold"
            break

    return ClosedLoopResult(
        seed=seed,
        initial_proposal=initial_proposal,
        final_proposal=proposal,
        iterations=tuple(iterations),
        stop_reason=stop_reason,
        n_pilot_calls=pilot_calls,
        total_calls=pilot_calls,
    )


__all__ = [
    "ClosedLoopIteration",
    "ClosedLoopResult",
    "run_closed_loop",
    "MAX_ADAPTATION_ITERATIONS",
    "M2_RELATIVE_STOP_THRESHOLD",
    "ETA_MAIN",
]