"""Phase-H2 nonlinear Monte-Carlo validation statistics (H2 §63).

Pure statistics / classification / metrics over ensemble data:

* sample classification against the H0 frozen ``SampleClassification``
  taxonomy (H2 §22, §23, §42);
* linear / nonlinear ensemble statistics with a single frozen ``ddof=1``
  convention (H2 §25);
* SAMPLE-MATCHED comparator: the nonlinear and linear ensembles use
  EXACTLY the same standardized samples, so the finite-N Wishart noise is
  largely cancelled (H2 §20, §21); the analytic H1 covariance ``alpha^2 K``
  is kept as a secondary closure (H2 §40);
* fixed-time metrics ``E_mu, E_P, E_sigma1, E_H2`` + separately-reported
  principal alignment (H2 §26-§31);
* structural-zero leakage (Qian post-Capture projected gamma direction,
  H2 §30, §53);
* terminal metrics (terminal time mean/std, terminal-state, state-time
  cross covariance, composite ``E_H2_T``, H2 §45-§48);
* pair bootstrap over antithetic pairs as indivisible units (H2 §33-§35)
  and the 1% / 5% operational accuracy classification (H2 §32, §36).

Trajectory integration is NEVER performed here (the generator injects the
per-sample nonlinear observations); sampling is NEVER performed here
(``sampling.py`` owns the RNG).  This module is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from hyptraj.uncertainty.protocol import SampleClassification
from hyptraj.uncertainty.sampling import BOOTSTRAP_SEED, NESTED_SAMPLE_SIZES

# Sanger / Qian terminal-kind constants (frozen, for classification).
from hyptraj.simulation.sanger_research_trajectory import (
    TERMINAL_GRAZING_OR_UNRESOLVED_EVENT,
)
from hyptraj.simulation.sanger_trajectory import (
    SANGER_ATM,
    TERMINAL_GROUND_BEFORE_SRTI,
    TERMINAL_MAX_SEGMENTS,
    TERMINAL_MAX_TIME as SANGER_MAX_TIME,
    TERMINAL_SOLVER_FAILURE as SANGER_SOLVER_FAILURE,
    TERMINAL_SRTI,
)
from hyptraj.simulation.qian_research_trajectory import (
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE,
    TERMINAL_MAX_TIME as QIAN_MAX_TIME,
    TERMINAL_RTI,
    TERMINAL_SOLVER_FAILURE as QIAN_SOLVER_FAILURE,
)

DDof = 1
SCALED_EPS = 1e-300          # floor against divide-by-zero (metrics keep finite)
ZERO_SIGMA_REL = 1e-8        # structural-zero component scale (relative to RMS)


# ---------------------------------------------------------------------------
# Trajectory -> per-sample observation extraction (H2 §16, §17)
# ---------------------------------------------------------------------------
def _state_at_T(segments, T: float):
    """Physical state at fixed time via the frozen dense-output channel."""
    for s in segments:
        if s.t_start <= T <= s.t_end:
            return np.asarray(s.solution([T])).reshape(-1)
    return None


def extract_sample_observations(model: str, traj, segments, T: float) -> dict:
    """Pure observation extractor: fixed-time state + terminal + switch info."""
    state_T = None
    for seg in segments:
        if seg.t_start <= T <= seg.t_end:
            state_T = np.asarray(seg.solution([T])).reshape(-1)
            break
    switches = 0
    mode_at_T = None
    terminal_switches = 0
    if model == "qian":
        # true switch = capture; mode at T from mode_sequence.
        captured_at_T = bool(getattr(traj, "capture_event", None) is not None)
        mode_seq = tuple(getattr(traj, "mode_sequence", ()))
        switches = 1 if (captured_at_T and traj.capture_event.time_s <= T) else 0
        mode_at_T = "QEG_GLIDE" if (captured_at_T and traj.capture_event.time_s <= T) else "ENTRY_CAPTURE"
        terminal_switches = switches
    else:
        for e in getattr(traj, "events", ()):
            if e.kind in ("atmosphere_exit", "atmosphere_entry"):
                if e.time <= T:
                    switches += 1
                terminal_switches += 1
        for seg in segments:
            if seg.t_start <= T <= seg.t_end:
                mode_at_T = getattr(seg, "mode", None)
                break
    return {
        "terminal_kind": getattr(traj, "terminal_kind", None),
        "terminal_time": float(getattr(traj, "terminal_time", np.nan)),
        "terminal_state": np.asarray(getattr(traj, "terminal_state", np.full(4, np.nan))),
        "state_T": state_T,
        "switches_at_T": int(switches),
        "mode_at_T": mode_at_T,
        "terminal_switches": int(terminal_switches),
        "success": bool(getattr(traj, "success", True)),
    }


def _obs_state_T_finite(obs: dict) -> bool:
    st = obs.get("state_T")
    return st is not None and bool(np.all(np.isfinite(st)))


# ---------------------------------------------------------------------------
# Fixed-time sample classification (H2 §22, §23)
# ---------------------------------------------------------------------------
QIAN_FIXED_FAILURE_KINDS = {
    QIAN_MAX_TIME, QIAN_SOLVER_FAILURE, TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
}
SANGER_FIXED_FAILURE_KINDS = {
    SANGER_MAX_TIME, SANGER_SOLVER_FAILURE, TERMINAL_MAX_SEGMENTS,
}
QIAN_TERMINAL_KIND_CHANGED = {
    TERMINAL_GROUND_BEFORE_CAPTURE, TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
}


def classify_fixed_time_sample(
    model: str,
    obs: dict,
    *,
    T: float,
    nominal_switches_at_T: int,
    nominal_mode_at_T: str,
) -> tuple[SampleClassification, str]:
    """Classify one nonlinear sample for the fixed-time T validation gate.

    Returning ``TOPOLOGY_PRESERVED`` means the sample is inside the same
    fixed-topology / event-order domain as the nominal trajectory at time T.
    Any other class excludes the alpha from the ordinary H1-covariance
    acceptance population (H2 §23); the counts are still recorded.
    """
    tkind = obs["terminal_kind"]
    t_time = obs["terminal_time"]

    if not _obs_state_T_finite(obs):
        return (SampleClassification.NONPHYSICAL_STATE, "NON_FINITE_STATE_AT_T")

    if model == "qian":
        if tkind in QIAN_FIXED_FAILURE_KINDS:
            return (SampleClassification.NUMERICAL_FAILURE, f"{tkind}")
        if t_time <= T:
            if tkind == TERMINAL_RTI:
                return (SampleClassification.TOPOLOGY_CHANGED, "RTI_BEFORE_T600")
            return (SampleClassification.TERMINAL_KIND_CHANGED, f"{tkind}_BEFORE_T600")
        if obs["switches_at_T"] == nominal_switches_at_T and obs["mode_at_T"] == nominal_mode_at_T:
            return (SampleClassification.TOPOLOGY_PRESERVED, "")
        return (SampleClassification.TOPOLOGY_CHANGED, "QIAN_TOPOLOGY_MISMATCH_AT_T")

    # sanger
    if tkind == TERMINAL_GRAZING_OR_UNRESOLVED_EVENT:
        return (SampleClassification.GRAZING_CROSSED, f"{tkind}")
    if tkind in SANGER_FIXED_FAILURE_KINDS:
        return (SampleClassification.NUMERICAL_FAILURE, f"{tkind}")
    if tkind in (TERMINAL_SRTI, TERMINAL_GROUND_BEFORE_SRTI) and t_time <= T:
        if tkind == TERMINAL_SRTI:
            return (SampleClassification.TOPOLOGY_CHANGED, "SRTI_BEFORE_T600")
        return (SampleClassification.TERMINAL_KIND_CHANGED, f"{tkind}_BEFORE_T600")
    if tkind == TERMINAL_GROUND_BEFORE_SRTI:
        return (SampleClassification.TERMINAL_KIND_CHANGED, f"{tkind}")
    # terminal_time > T (mid-flight)
    if obs["switches_at_T"] == nominal_switches_at_T:
        if obs["mode_at_T"] == nominal_mode_at_T:
            return (SampleClassification.TOPOLOGY_PRESERVED, "")
        return (SampleClassification.EVENT_ORDER_CHANGED, f"mode_at_T={obs['mode_at_T']}")
    return (SampleClassification.TOPOLOGY_CHANGED,
            f"switches_at_T={obs['switches_at_T']}")


def classify_terminal_sample(
    model: str,
    obs: dict,
    *,
    expected_kind: str,
    nominal_terminal_switches: int,
) -> tuple[SampleClassification, str]:
    """Classify one nonlinear sample for the NATIVE-terminal validation gate
    (H2 §41, §42).  Only a sample with the expected terminal kind AND the
    nominal true-switch topology is a terminal validation candidate."""
    tkind = obs["terminal_kind"]
    if model == "qian":
        if tkind == TERMINAL_RTI:
            return (SampleClassification.TOPOLOGY_PRESERVED, "RTI")
        if tkind in QIAN_FIXED_FAILURE_KINDS:
            return (SampleClassification.NUMERICAL_FAILURE, f"{tkind}")
        return (SampleClassification.TERMINAL_KIND_CHANGED, f"{tkind}")
    # sanger
    if tkind == TERMINAL_SRTI:
        if obs["terminal_switches"] == nominal_terminal_switches:
            return (SampleClassification.TOPOLOGY_PRESERVED, "srti")
        return (SampleClassification.TOPOLOGY_CHANGED,
                f"SRTI_switch_count={obs['terminal_switches']}")
    if tkind == TERMINAL_GRAZING_OR_UNRESOLVED_EVENT:
        return (SampleClassification.GRAZING_CROSSED, f"{tkind}")
    if tkind in SANGER_FIXED_FAILURE_KINDS:
        return (SampleClassification.NUMERICAL_FAILURE, f"{tkind}")
    return (SampleClassification.TERMINAL_KIND_CHANGED, f"{tkind}")


def domain_gate_status(classifications: Sequence[SampleClassification]) -> str:
    """H2 §23 / §36: any non-TOPOLOGY_PRESERVED sample fails the domain gate.

    Samples are NEVER dropped to compute a conditioned covariance (that
    would be selection bias); the alpha is simply excluded from ordinary
    H1-covariance acceptance and the classification counts are recorded.
    """
    cls = list(classifications)
    if not cls:
        return "NO_SAMPLES"
    if all(c == SampleClassification.TOPOLOGY_PRESERVED for c in cls):
        return "PASS"
    return "DOMAIN_GATE_FAIL"


def classification_counts(classifications: Sequence[SampleClassification]) -> dict:
    counts: dict[str, int] = {}
    for c in classifications:
        counts[c.value] = counts.get(c.value, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Ensemble statistics (H2 §25)
# ---------------------------------------------------------------------------
def ensemble_mean_cov(Y: np.ndarray, ddof: int = DDof) -> tuple[np.ndarray, np.ndarray]:
    Y = np.asarray(Y, dtype=float)
    if Y.ndim != 2:
        raise ValueError(f"Y must be (N, 4); got {Y.shape}.")
    mu = Y.mean(axis=0)
    P = np.cov(Y, rowvar=False, ddof=ddof) if Y.shape[0] > 1 else np.zeros((4, 4))
    return mu, P


def ensemble_std(Y: np.ndarray, ddof: int = DDof) -> np.ndarray:
    if Y.shape[0] == 0:
        return np.zeros(4)
    return np.std(Y, axis=0, ddof=ddof) if Y.shape[0] > 1 else np.zeros(4)


def _sym(A: np.ndarray) -> np.ndarray:
    return 0.5 * (np.asarray(A) + np.asarray(A).T)


def _frob(A: np.ndarray) -> float:
    return float(np.sqrt(np.sum(np.asarray(A) ** 2)))


def _max_eig(K: np.ndarray) -> float:
    ev = np.linalg.eigvalsh(_sym(K))
    return float(np.max(ev)) if ev.size else 0.0


def principal_alignment(P_L: np.ndarray, P_N: np.ndarray) -> tuple[float, float]:
    """Largest principal-direction alignment ``A1 = |u1N . u1L|`` and angle."""
    evL, uL = np.linalg.eigh(_sym(P_L))
    evN, uN = np.linalg.eigh(_sym(P_N))
    u1L = uL[:, -1]
    u1N = uN[:, -1]
    align = float(abs(u1L @ u1N))
    angle = float(np.arccos(np.clip(align, -1.0, 1.0)))
    return align, angle


def structural_zero_mask(P_ref: np.ndarray, sigma_rms: float) -> np.ndarray:
    """Components whose H1 linear variance is numerically zero (H2 §30)."""
    sig = np.sqrt(np.maximum(np.diag(_sym(P_ref)), 0.0))
    return sig <= max(ZERO_SIGMA_REL * sigma_rms, 1e-14)


# ---------------------------------------------------------------------------
# Fixed-time metrics (H2 §26-§31)
# ---------------------------------------------------------------------------
def fixed_time_metrics(
    y_L: np.ndarray,
    y_N: np.ndarray,
    P_H1: np.ndarray,
) -> dict:
    """Sample-matched fixed-time linear-vs-nonlinear validation metrics.

    ``y_L`` / ``y_N`` are the canonical-A scaled outputs of the SAME
    standardized samples (H2 §19-§21); ``P_H1 = alpha^2 K_x`` is the
    analytic H1 covariance (secondary closure, H2 §40).
    """
    mu_L, P_L = ensemble_mean_cov(y_L)
    mu_N, P_N = ensemble_mean_cov(y_N)
    sigma_rms_L = float(np.sqrt(np.trace(P_L)))
    denom_mu = max(sigma_rms_L, SCALED_EPS)
    denom_P = max(_frob(P_L), SCALED_EPS)
    # sampling noise of the linear ensemble vs the analytic H1 covariance
    E_sampling = float(_frob(P_L - P_H1) / max(_frob(P_H1), SCALED_EPS))
    E_mu = float(np.linalg.norm(mu_N - mu_L) / denom_mu)
    E_P = float(_frob(P_N - P_L) / denom_P)
    s1L = float(np.sqrt(max(_max_eig(P_L), 0.0)))
    s1N = float(np.sqrt(max(_max_eig(P_N), 0.0)))
    E_sigma1 = float(abs(s1N - s1L) / max(s1L, SCALED_EPS))
    align, angle = principal_alignment(P_L, P_N)

    sigL = ensemble_std(y_L)
    sigN = ensemble_std(y_N)
    zero = structural_zero_mask(P_H1, sigma_rms_L)
    marginal_rel = np.full(4, np.nan, dtype=float)
    for j in range(4):
        if not zero[j]:
            marginal_rel[j] = float(abs(sigN[j] - sigL[j]) / max(sigL[j], SCALED_EPS))
    leakage = np.full(4, np.nan, dtype=float)
    for j in range(4):
        if zero[j]:
            leakage[j] = float(sigN[j] / denom_mu)
    E_marginal_max = float(np.nanmax(marginal_rel)) if np.any(~zero) else 0.0
    E_zero_max = float(np.nanmax(leakage)) if np.any(zero) else 0.0
    E_H2 = float(max(E_mu, E_P, E_sigma1, E_marginal_max, E_zero_max))
    return {
        "linear_sample_mean": mu_L,
        "nonlinear_sample_mean": mu_N,
        "linear_sample_covariance": P_L,
        "nonlinear_sample_covariance": P_N,
        "analytic_H1_covariance": np.asarray(P_H1, dtype=float),
        "E_sampling": E_sampling,
        "E_mu": E_mu,
        "E_cov": E_P,
        "E_sigma1": E_sigma1,
        "principal_alignment": align,
        "principal_angle": angle,
        "sigma_rms_L": sigma_rms_L,
        "marginal_std_linear": sigL,
        "marginal_std_nonlinear": sigN,
        "marginal_relative_errors": marginal_rel,
        "structural_zero_leakage": leakage,
        "structural_zero_mask": zero,
        "E_marginal_max": E_marginal_max,
        "E_zero_max": E_zero_max,
        "E_H2": E_H2,
    }


# ---------------------------------------------------------------------------
# Terminal metrics (H2 §45-§48)
# ---------------------------------------------------------------------------
def terminal_time_metrics(
    dt_L: np.ndarray, dt_N: np.ndarray
) -> dict:
    mu_L = float(np.mean(dt_L)); mu_N = float(np.mean(dt_N))
    sig_L = float(np.std(dt_L, ddof=DDof)) if dt_L.size > 1 else 0.0
    sig_N = float(np.std(dt_N, ddof=DDof)) if dt_N.size > 1 else 0.0
    denom = max(sig_L, SCALED_EPS)
    E_t_mu = float(abs(mu_N - mu_L) / denom)
    E_t_sigma = float(abs(sig_N - sig_L) / denom)
    return {
        "linear_terminal_time_mean": mu_L,
        "nonlinear_terminal_time_mean": mu_N,
        "linear_terminal_time_std": sig_L,
        "nonlinear_terminal_time_std": sig_N,
        "E_t_mu": E_t_mu,
        "E_t_sigma": E_t_sigma,
    }


def cross_covariance_metrics(
    cross_L: np.ndarray, cross_N: np.ndarray
) -> dict:
    """Norm-relative mismatch of the scaled state-time cross covariance."""
    nL = float(np.linalg.norm(cross_L))
    rel = float(np.linalg.norm(cross_N - cross_L) / max(nL, SCALED_EPS))
    return {
        "linear_state_time_cross_cov": np.asarray(cross_L),
        "nonlinear_state_time_cross_cov": np.asarray(cross_N),
        "E_cross_rel": rel,
        "linear_cross_norm": nL,
    }


def terminal_state_metrics(
    zT_L: np.ndarray, zT_N: np.ndarray, P_T_H1: np.ndarray
) -> dict:
    """Same fixed-time-style metrics applied to the scaled terminal state."""
    m = fixed_time_metrics(zT_L, zT_N, P_T_H1)
    # keep only terminal-state relevant keys (cov/sigma/mu/alignment/leakage)
    m = {k: v for k, v in m.items() if k != "E_sampling"}
    m["E_sampling_terminal"] = fixed_time_metrics(zT_L, zT_N, P_T_H1)["E_sampling"]
    return m


def composite_terminal_discrepancy(
    dt_L: np.ndarray,
    dt_N: np.ndarray,
    zT_L: np.ndarray,
    zT_N: np.ndarray,
    P_T_H1: np.ndarray,
) -> dict:
    """Composite terminal discrepancy ``E_H2_T`` (H2 §48)."""
    tt = terminal_time_metrics(dt_L, dt_N)
    ts = fixed_time_metrics(zT_L, zT_N, P_T_H1)
    ts_mod = dict(ts)
    ts_mod["E_mu"] = ts["E_mu"]
    E_H2_T = max(
        tt["E_t_mu"], tt["E_t_sigma"],
        ts["E_mu"], ts["E_cov"], ts["E_sigma1"],
        ts["E_marginal_max"], ts["E_zero_max"],
    )
    return {
        "terminal_time": tt,
        "terminal_state": {k: v for k, v in ts.items() if k not in
                           ("linear_sample_covariance", "nonlinear_sample_covariance",
                            "analytic_H1_covariance", "marginal_relative_errors",
                            "structural_zero_leakage", "marginal_std_linear",
                            "marginal_std_nonlinear", "structural_zero_mask")},
        "E_H2_terminal": float(E_H2_T),
    }


# ---------------------------------------------------------------------------
# Pair bootstrap (H2 §33-§35)
# ---------------------------------------------------------------------------
def _resample_pairs(arrs, rng: np.random.Generator, n_pairs: int):
    idx_pair = rng.integers(0, n_pairs, size=n_pairs)
    idx = np.empty(2 * n_pairs, dtype=int)
    idx[0::2] = 2 * idx_pair
    idx[1::2] = 2 * idx_pair + 1
    return tuple(np.asarray(a)[idx] for a in arrs)


def pair_bootstrap(
    *arrs: np.ndarray,
    statistic: Callable[..., float],
    n_boot: int = 1000,
    rng_seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Pair bootstrap over antithetic pairs as indivisible units (H2 §33).

    Resamples (z_j, -z_j) pairs WITH replacement (never +z / -z
    independently), recomputes ``statistic`` on the resampled ensembles,
    and returns ``(median, lower_2.5, upper_97.5)`` empirical 95% CI.
    Deterministic for a fixed ``rng_seed`` (bootstrap reproducibility only).
    """
    n = int(np.asarray(arrs[0]).shape[0])
    if n % 2 != 0:
        raise ValueError("pair bootstrap requires an even (antithetic) N.")
    n_pairs = n // 2
    rng = np.random.default_rng(rng_seed)
    vals = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        rs = _resample_pairs(arrs, rng, n_pairs)
        vals[b] = float(statistic(*rs))
    median = float(np.median(vals))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return median, float(lo), float(hi)


def _E_H2_statistic(P_H1: np.ndarray, y_L: np.ndarray, y_N: np.ndarray) -> float:
    return float(fixed_time_metrics(y_L, y_N, P_H1)["E_H2"])


def _E_P_statistic(P_H1: np.ndarray, y_L: np.ndarray, y_N: np.ndarray) -> float:
    return float(fixed_time_metrics(y_L, y_N, P_H1)["E_cov"])


def _E_sigma1_statistic(P_H1: np.ndarray, y_L: np.ndarray, y_N: np.ndarray) -> float:
    return float(fixed_time_metrics(y_L, y_N, P_H1)["E_sigma1"])


# ---------------------------------------------------------------------------
# Operational 1% / 5% accuracy classification (H2 §32, §36)
# ---------------------------------------------------------------------------
def classify_tau(ci_lower: float, ci_upper: float, tau: float) -> str:
    """PASS / FAIL / UNRESOLVED for the numerical-accuracy criterion tau."""
    if ci_upper <= tau:
        return "PASS"
    if ci_lower > tau:
        return "FAIL"
    return "UNRESOLVED"


def accuracy_classification(
    median: float, lower95: float, upper95: float, tau: float,
    domain_gate: str,
) -> str:
    """Combine the domain gate and the bootstrap interval (H2 §36)."""
    if domain_gate == "DOMAIN_GATE_FAIL":
        return "DOMAIN_GATE_FAIL"
    if domain_gate != "PASS":
        return "DOMAIN_GATE_FAIL"
    return classify_tau(lower95, upper95, tau)


# ---------------------------------------------------------------------------
# Sequential-N / alpha-bracket helpers (H2 §37-§39)
# ---------------------------------------------------------------------------
def sequential_status_run(records: Sequence[dict]) -> str:
    """Stable-PASS/FAIL (two consecutive equal) vs UNRESOLVED (H2 §37)."""
    if len(records) < 2:
        return "INSUFFICIENT_MONTE_CARLO_CONVERGENCE"
    last = records[-1]["status"]
    if last == "UNRESOLVED":
        return "INSUFFICIENT_MONTE_CARLO_CONVERGENCE"
    prev = records[-2]["status"]
    if last == prev and last in ("PASS", "FAIL"):
        return last
    return "INSUFFICIENT_MONTE_CARLO_CONVERGENCE"
