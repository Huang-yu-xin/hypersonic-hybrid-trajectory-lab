"""M1 -- missing-mode discovery and the preregistered mode-birth gate.

Missing-mode definition (task Sec. 11): a topology mode is "missing" when the
current proposal component set has no representation for it AND its estimated
share of the variance measure is non-negligible.  A mode is NOT missing just
because the pilot sees a new label string.

Preregistered birth gate (task Sec. 12, frozen in
``configs/m1_closed_loop_v0.json``):

    birth(k) = 1[ omega_k_V_hat >= tau_birth_main
                 AND LCB95%(omega_k_V) >= tau_birth_lower_confidence
                 AND n_k >= min_mode_observations ]

with ``tau_birth_main = 0.10``, ``tau_birth_lower_confidence = 0.05``,
``min_mode_observations = 5``.  These are M1-v0 preregistered engineering
choices, NOT universal constants, and must not be silently retuned after
looking at final evaluation (task Sec. 12 / 37).

This module never imports the simulator; it consumes pilot samples, labels
and densities produced elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hyptraj.m1.variance_measure import estimate_variance_measure, omega_bootstrap_lcb

N_BOOTSTRAP_DEFAULT = 500


@dataclass(frozen=True)
class ModeStat:
    """Per-mode discovery state (task Sec. 11)."""

    mode_id: str
    represented_by_component: bool
    P_k_hat: float
    L_k_hat: float
    omega_k_V_hat: float
    omega_lcb95: float
    n_observed: int
    variance_mass_ess: float
    birth_eligible: bool


@dataclass(frozen=True)
class DiscoveryResult:
    """Outcome of one diagnosis round (task Sec. 10.1 steps 5-7)."""

    M2_hat: float
    mode_stats: tuple[ModeStat, ...]
    candidate_mode: str | None      # mode that passes the birth gate
    action: str                     # "HOLD" | "ADD_COMPONENT"
    variance_mass_ess: float
    n_events: int


def infer_represented_modes(labels: np.ndarray, nominal_topology: str) -> set[str]:
    """``represented`` is a proposal-level property in v0: v0 freezes unit
    covariance and a single component is crafted for the primary mode only.

    In v0 the proposal is represented for the nominal geometry's primary mode
    (single Geometry-IS component centered at the primary design point) and
    for every previously born mode.  Interpretation: a component set
    ``component_mode_ids`` explicitly tracks which topology modes the
    components were built for.  All observed modes NOT in that set are
    "unrepresented" (task Sec. 11 definition).
    """
    return set(labels[labels != nominal_topology].tolist())


def diagnose_missing_mode(
    z: np.ndarray,
    centers: np.ndarray,
    pi: np.ndarray,
    logp: np.ndarray,
    logr: np.ndarray,
    labels: np.ndarray,
    nominal_topology: str,
    component_mode_ids: set[str],
    tau_birth_main: float = 0.10,
    tau_birth_lower_confidence: float = 0.05,
    min_mode_observations: int = 5,
    n_bootstrap: int = N_BOOTSTRAP_DEFAULT,
    rng: np.random.Generator | None = None,
    birth_signal: str = "variance",
) -> DiscoveryResult:
    """Run one diagnosis: estimate the variance measure, then test every
    observed unrepresented mode against the frozen birth gate.

    Returns a candidate mode (first, in stable label order) when the gate
    passes; otherwise ``action = HOLD``.

    ``birth_signal="variance"`` (v0) gates on ``omega_k^V`` with the bootstrap
    LCB; ``birth_signal="probability"`` (Ablation A, task Sec. 27) replaces
    the variance-share gate by the topology-probability gate ``P_k_hat`` with
    the SAME 0.10 threshold -- the ablation that demonstrates the necessity
    of the variance signal on probability-small variance-dominant modes.
    """
    vm = estimate_variance_measure(
        z, centers, pi, logp, logr, labels, nominal_topology
    )
    mode_stats: list[ModeStat] = []
    candidates: list[str] = []
    for topo in vm.mode_ids:
        represented = topo in component_mode_ids
        omega = vm.omega_k_V[vm.mode_ids.index(topo)]
        n_obs = vm.n_observed[vm.mode_ids.index(topo)]
        p_k_hat = float(n_obs / vm.n_samples)
        if birth_signal == "probability":
            signal_ok = p_k_hat >= tau_birth_main
            lcb = float("nan")
        elif birth_signal == "variance":
            # bootstrap LCB only for potential candidates: an unrepresented
            # mode with enough observations (saves ~10x cost on HOLD rounds)
            lcb = float("nan")
            if (not represented) and n_obs >= min_mode_observations and n_obs > 0:
                lcb, _ub = omega_bootstrap_lcb(
                    z, centers, pi, logp, logr, labels, nominal_topology,
                    mode=str(topo), n_bootstrap=n_bootstrap, rng=rng,
                )
            signal_ok = omega >= tau_birth_main and lcb >= tau_birth_lower_confidence
        else:
            raise ValueError(f"unknown birth_signal {birth_signal!r}")
        eligible = (
            (not represented)
            and signal_ok
            and n_obs >= min_mode_observations
            and n_obs > 0
        )
        mode_stats.append(ModeStat(
            mode_id=str(topo),
            represented_by_component=represented,
            P_k_hat=p_k_hat,
            L_k_hat=float(vm.L_k[vm.mode_ids.index(topo)]),
            omega_k_V_hat=float(omega),
            omega_lcb95=float(lcb),
            n_observed=n_obs,
            variance_mass_ess=vm.variance_mass_ess,
            birth_eligible=bool(eligible),
        ))
        if eligible:
            candidates.append(str(topo))
    candidate = candidates[0] if candidates else None
    return DiscoveryResult(
        M2_hat=vm.M2_hat,
        mode_stats=tuple(mode_stats),
        candidate_mode=candidate,
        action="ADD_COMPONENT" if candidate is not None else "HOLD",
        variance_mass_ess=vm.variance_mass_ess,
        n_events=vm.n_events,
    )


__all__ = [
    "ModeStat",
    "DiscoveryResult",
    "diagnose_missing_mode",
    "infer_represented_modes",
    "N_BOOTSTRAP_DEFAULT",
]