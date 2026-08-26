"""M1-D -- benchmark family: rotated cap multi-mode systems (task Sec. 8-12).

Family definition (minimal deterministic wrapper over the frozen H3-2 / M1
Benchmark C u-space physics -- target ``p = N(0, I_2)``, topology sets
declared by deterministic inequalities, initial proposal = single unit
Gaussian at the primary mode's nearest-boundary design point; no simulator
physics is changed, only the number of declared modes grows to satisfy the
preregistered ``K_missing >= 3`` requirement):

For each event mode k in {1..4} with outward direction ``n_k(cos th, sin th)``:

    linear  variant: A_k = { u : u . n_k > h_k }
    curved  variant: A_k = { u : u . n_k > h_k + c_k (v_k - o_k)^2 }

where ``v_k`` is the coordinate along the perpendicular direction and
``c_k >= 0`` is a curvature amplitude borrowed from the frozen H3-2 surface
form ``u1 > 1 + 0.5 (u2-1.5)^2``.  ``c_k = 0`` reduces exactly to the frozen
H3-1 linear halfspace family.  Only missing modes may be curved; the
primary mode stays linear so that its design point is exact (frozen rule
``z_star`` = nearest-boundary point, e.g. ``(-1.5, 0)`` for H3-1 S1).

Label precedence: ascending mode index, later index OVERWRITES earlier
(frozen ``label_curved`` semantics).  ``S0`` nominal is the complement.

Analytic anchor used by tests (linear caps, well separated):
    P(A_k)        = 1 - Phi(h_k)
    L_k(q_0)      = exp(||m||^2) * (1 - Phi(h_k + m . n_k))
with q_0 = N(m, I), m = h_1 n_1  (derived: p^2/q_0 = e^{||m||^2}
phi_{N(-m, I)}(x); standard identity behind the frozen "leakage point").

All randomness flows through ``np.random.SeedSequence([batch_seed, idx])``
spawned children -- bit-deterministic across runs and platforms.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from math import erf, sqrt

import numpy as np

from hyptraj.m1.proposal_update import MixtureProposal

# ---- frozen-family constants -------------------------------------------
DIM = 2
NOMINAL = "S0"
MODE_IDS = ("S1", "S2", "S3", "S4")     # S1 primary (represented), rest missing
N_MISSING = 3

# candidate parameter ranges (documented difficulty window; freeze doc lists
# every draw so nothing is hand-tuned post hoc)
PRIMARY_THETA_DEG = (120.0, 240.0)
PRIMARY_H_RANGE = (1.5, 2.0)
MISSING_H_RANGE = (1.5, 2.6)
CURVED_PROB = 0.25                      # Bernoulli per missing mode
CURVATURE_C = 0.35                      # amplitude when curved
OFFSET_O_RANGE = (-1.0, 1.0)
MIN_ANGLE_SEP_DEG = 40.0                # pairwise circular separation


def _circ_dist_deg(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


@dataclass(frozen=True)
class BenchmarkConfig:
    """One immutable benchmark config (all params recorded -> reproducible)."""

    config_id: str
    batch_seed: int
    batch_index: int
    theta_deg: tuple[float, ...]          # 4 directions, index matches MODE_IDS
    h: tuple[float, ...]                  # 4 linear thresholds
    curved: tuple[bool, ...]              # curvature flag per mode
    curvature_c: float                    # shared amplitude constant
    offset_o: tuple[float, ...]           # parabola apex offset per mode

    @property
    def normals(self) -> np.ndarray:
        t = np.radians(np.asarray(self.theta_deg))
        return np.stack([np.cos(t), np.sin(t)], axis=1)

    @property
    def primary_z_star(self) -> np.ndarray:
        """Nearest-boundary design point of the (linear) primary mode."""
        return self.h[0] * self.normals[0]

    def initial_proposal(self) -> MixtureProposal:
        return MixtureProposal(
            centers=self.primary_z_star.reshape(1, DIM),
            weights=np.array([1.0]),
            component_mode_ids=(MODE_IDS[0],),
        )

    def logp(self, z: np.ndarray) -> np.ndarray:
        z = np.asarray(z, dtype=float)
        return -np.sum(z**2, axis=1) / 2.0 \
            - 0.5 * DIM * np.log(2.0 * np.pi)

    def label(self, z: np.ndarray) -> np.ndarray:
        """Vectorized frozen-style topology oracle (later index wins)."""
        z = np.asarray(z, dtype=float)
        out = np.full(z.shape[0], NOMINAL, dtype=object)
        for k in range(len(MODE_IDS)):
            proj = z @ self.normals[k]
            s = np.full(z.shape[0], self.h[k])
            if self.curved[k]:
                perp = np.stack([-self.normals[k][1], self.normals[k][0]], axis=-1)
                v = z @ perp
                s = self.h[k] + self.curvature_c * (v - self.offset_o[k]) ** 2
            out[proj > s] = MODE_IDS[k]
        return out

    def params_dict(self) -> dict:
        return {
            "theta_deg": list(self.theta_deg),
            "h": list(self.h),
            "curved": [bool(c) for c in self.curved],
            "curvature_c": self.curvature_c,
            "offset_o": list(self.offset_o),
        }


def _sample_directions(rng: np.random.Generator) -> tuple[float, ...]:
    """Primary angle then rejection-sampled missing angles (>= MIN sep)."""
    thetas = [float(rng.uniform(*PRIMARY_THETA_DEG))]
    for _ in range(N_MISSING):
        placed = False
        for _try in range(500):
            cand = float(rng.uniform(0.0, 360.0))
            if all(_circ_dist_deg(cand, t) >= MIN_ANGLE_SEP_DEG for t in thetas):
                thetas.append(cand)
                placed = True
                break
        if not placed:                   # deterministic grid fallback (rare)
            start = rng.uniform(0.0, 45.0)
            for step in (72.0, 144.0, 216.0):
                cand = (start + step) % 360.0
                if all(_circ_dist_deg(cand, t) >= MIN_ANGLE_SEP_DEG - 10.0
                       for t in thetas):
                    thetas.append(cand)
                    placed = True
                    break
            if not placed:
                raise RuntimeError("direction sampling failed; widen pools")
    return tuple(thetas)


def generate_candidate_pool(batch_seed: int, size: int,
                            id_prefix: str = "m1d") -> list[BenchmarkConfig]:
    """Deterministically enumerate `size` candidate configs of one batch.

    Task Sec. 10.1: ``candidate_generation_seed = 20260827``,
    ``candidate_pool_size = 64``; a second batch uses seed ``20260828``.
    """
    pool = []
    for i in range(size):
        ss = np.random.SeedSequence([int(batch_seed), int(i)])
        rng = np.random.default_rng(ss.spawn(1)[0])
        thetas = _sample_directions(rng)
        h_primary = float(rng.uniform(*PRIMARY_H_RANGE))
        h_miss = [float(rng.uniform(*MISSING_H_RANGE)) for _ in range(N_MISSING)]
        flags = [bool(rng.random() < CURVED_PROB) for _ in range(N_MISSING)]
        # offsets ALIGNED to MODE_IDS slots (slot 0 = linear primary, unused);
        # uniform consumed exactly when the corresponding flag is true
        offs = [0.0]
        for f in flags:
            offs.append(float(rng.uniform(*OFFSET_O_RANGE)) if f else 0.0)
        pool.append(BenchmarkConfig(
            config_id=f"{id_prefix}_b{batch_seed}_c{i:03d}",
            batch_seed=int(batch_seed),
            batch_index=i,
            theta_deg=thetas,
            h=(h_primary, *h_miss),
            curved=(False, *flags),      # primary stays linear (exact z*)
            curvature_c=CURVATURE_C,
            offset_o=tuple(offs),
        ))
    return pool


# ---------------------------------------------------------------------------
# Offline reference characterization (task Sec. 9.1 + Sec. 10.2)
# ---------------------------------------------------------------------------
BOOTSTRAP_REPS = 200
MC_FRACTION = 0.3      # N_ref split: MC under p (cross-check) + stratified IS
_REF_SEQ_LABELS = ("cfg", "mc", "is", "boot")


def _ref_stream(cfg: BenchmarkConfig, n_mc: int, n_is_per: int,
                mc_rng: np.random.Generator, is_rng: np.random.Generator):
    """Fixed reference design: one MC block + K equal strata at mode apexes.

    Returns precomputed per-sample value vectors so bootstrap replicates are
    pure index resampling (fast, and identical rule for every candidate --
    task Sec. 10.2 uniform-budget requirement).
    """
    ref_rng = is_rng                     # stream source: stratified components
    centers = cfg.primary_z_star.reshape(1, -1)
    for k in range(1, len(MODE_IDS)):
        # design point of missing mode: argmin ||x|| on boundary -- exact for
        # linear caps; for curved caps use the apex v=o point (deterministic)
        if cfg.curved[k]:
            # apex (v = o) boundary point: projection on n_k equals h_k
            perp = np.stack([-cfg.normals[k][1], cfg.normals[k][0]])
            center = cfg.h[k] * cfg.normals[k] + cfg.offset_o[k] * perp
        else:
            center = cfg.h[k] * cfg.normals[k]
        centers = np.vstack([centers, center])

    # equal-stratum sampler with frozen mixture DENSITIES (recorded r)
    r_weights = np.full(len(MODE_IDS), 1.0 / len(MODE_IDS))
    xs, logrs = [], []
    for s in range(len(MODE_IDS)):
        Xs = centers[s] + ref_rng.standard_normal((n_is_per, DIM))
        xs.append(Xs)
    X_is = np.vstack(xs)

    r_prop = MixtureProposal(centers=centers, weights=r_weights,
                             component_mode_ids=MODE_IDS)
    logr_is = r_prop.log_density(X_is)
    labels_is = cfg.label(X_is)

    X_mc = mc_rng.standard_normal((n_mc, DIM))
    labels_mc = cfg.label(X_mc)

    return {
        "centers": centers,
        "X_is": X_is, "logr_is": logr_is, "labels_is": labels_is,
        "X_mc": X_mc, "labels_mc": labels_mc,
        "n_is_per": n_is_per, "K": len(MODE_IDS),
    }


def _mode_stats_from_precomputed(pre: dict, cfg: BenchmarkConfig) -> dict:
    """Point estimates P_k, L_k(q_0) from the fixed reference design.

    Stratified estimator over equal strata (+ separate plain-MC estimate for
    P as cross-check).  Same formulas online policies must implement offline
    legality rules aside, the L estimator IS task Eq. Sec. 29 with r =
    stratified component density.
    """
    X_is, logr, labels = pre["X_is"], pre["logr_is"], pre["labels_is"]
    n_per, K = pre["n_is_per"], pre["K"]
    logq0 = cfg.initial_proposal().log_density(X_is)
    logp = cfg.logp(X_is)

    lwP = logp - logr                        # p/r
    wP = np.exp(lwP)
    wL = np.exp(2.0 * logp - logq0 - logr)   # p^2/(q0 r)

    Wm = wP.reshape(n_per, K)
    WLm = wL.reshape(n_per, K)
    masks = {mid: (labels == mid).reshape(n_per, K) for mid in MODE_IDS[1:]}
    modes: dict[str, dict] = {}
    for mid in MODE_IDS[1:]:
        mk = masks[mid]
        cnt_s = mk.sum(axis=0)                                  # counts per stratum
        sumP_s = (Wm * mk).sum(axis=0)
        sumL_s = (WLm * mk).sum(axis=0)
        p_hat = float(sumP_s.sum() / (n_per * K))
        l_hat = float(sumL_s.sum() / (n_per * K))
        modes[mid] = {
            "P_ref": p_hat,
            "L_ref": l_hat,
            "raw_count": int(cnt_s.sum()),
            "raw_fraction": float(cnt_s.sum() / (n_per * K)),
            "counts_per_stratum": [int(v) for v in cnt_s],
        }
    return modes


def reference_characterize(cfg: BenchmarkConfig, n_reference: int = 500_000,
                           bootstrap_reps: int = BOOTSTRAP_REPS) -> dict:
    """Full offline characterization of one candidate (task Sec. 9-11).

    Deterministic: all RNG from SeedSequence([batch_seed, idx]) spawned
    children.  Reports stratified-IS references + MC cross-check +
    stratified-bootstrap CIs + eligibility checks E1-E6.
    """
    ss = np.random.SeedSequence([int(cfg.batch_seed), int(cfg.batch_index)])
    children = ss.spawn(len(_REF_SEQ_LABELS))
    cfg_r0, mc_rng, is_rng, boot_rng = (
        np.random.default_rng(c) for c in children)

    n_mc = int(round(n_reference * MC_FRACTION))
    n_is_total = n_reference - n_mc
    n_is_per = n_is_total // len(MODE_IDS)

    pre = _ref_stream(cfg, n_mc, n_is_per, mc_rng, is_rng)
    modes = _mode_stats_from_precomputed(pre, cfg)

    # MC cross-check for P (fixed rule across candidates, independent source)
    labels_mc = pre["labels_mc"]
    for mid in MODE_IDS[1:]:
        modes[mid]["P_ref_mc_crosscheck"] = float(np.mean(labels_mc == mid))

    # analytic anchors where applicable (linear caps, may double-count small
    # overlap slivers; diagnostic columns only -- never gate inputs)
    zstar = cfg.primary_z_star
    m_norm2 = float(zstar @ zstar)
    phi_bar = lambda t: 0.5 * (1.0 - erf(t / sqrt(2.0)))
    for k, mid in enumerate(MODE_IDS):
        if mid == MODE_IDS[0]:
            continue
        if not cfg.curved[k]:
            shift = float(zstar @ cfg.normals[k])          # m . n_k
            modes[mid]["analytic_P"] = float(phi_bar(cfg.h[k]))
            modes[mid]["analytic_L"] = float(
                math.exp(m_norm2) * phi_bar(cfg.h[k] + shift))

    # stratified bootstrap CIs (design-preserving: within-stratum resampling)
    ci = _bootstrap_cis(cfg, pre, modes, bootstrap_reps, boot_rng)

    elig = compute_eligibility({**modes}, alpha_p=0.5, pilot_n=20_000)

    return {
        "config_id": cfg.config_id,
        "params": cfg.params_dict(),
        "batch_seed": cfg.batch_seed,
        "batch_index": cfg.batch_index,
        "reference_budget": {
            "n_total": int(n_reference),
            "n_mc": int(pre["X_mc"].shape[0]),
            "n_is": int(pre["X_is"].shape[0]),
            "strata": int(pre["K"]),
        },
        "bootstrap_reps": int(bootstrap_reps),
        "modes": modes,
        "bootstrap_ci": ci,
        "eligibility": elig,
    }


def _bootstrap_cis(cfg: BenchmarkConfig, pre: dict, modes: dict,
                   reps: int, rng: np.random.Generator) -> dict:
    """Stratified bootstrap (within-stratum, size preserving) CIs.

    Frozen semantic family of ``variance_measure.omega_bootstrap_lcb`` with
    ``source_strata`` handling generalized to K proposal strata.  One set of
    stratum index draws is shared across modes per replicate (common random
    numbers -- paired uncertainty statements across modes).
    """
    X_is, logr, labels = pre["X_is"], pre["logr_is"], pre["labels_is"]
    n_per, K = pre["n_is_per"], pre["K"]
    mids = list(MODE_IDS[1:])
    logq0 = cfg.initial_proposal().log_density(X_is)
    logp = cfg.logp(X_is)
    wP = np.exp(logp - logr)                     # flat (N,)
    wL = np.exp(2.0 * logp - logq0 - logr)
    VP = np.stack([np.where(labels == m, wP, 0.0) for m in mids])   # (M, N)
    VL = np.stack([np.where(labels == m, wL, 0.0) for m in mids])
    denom = float(n_per * K)
    starts = [s * n_per for s in range(K)]

    p_reps = np.empty((reps, len(mids)))
    l_reps = np.empty((reps, len(mids)))
    for b in range(reps):
        tot_p = np.zeros(len(mids))
        tot_l = np.zeros(len(mids))
        for a in starts:
            idx = a + rng.integers(0, n_per, size=n_per)
            tot_p += VP[:, idx].sum(axis=1)
            tot_l += VL[:, idx].sum(axis=1)
        p_reps[b] = tot_p / denom
        l_reps[b] = tot_l / denom

    rep = {"P": {}, "L": {}}
    for j, mid in enumerate(mids):
        lo_p, hi_p = np.quantile(p_reps[:, j], [0.025, 0.975])
        lo_l, hi_l = np.quantile(l_reps[:, j], [0.025, 0.975])
        rep["P"][mid] = [float(lo_p), float(hi_p)]
        rep["L"][mid] = [float(lo_l), float(hi_l)]
    return rep


# ---------------------------------------------------------------------------
# Eligibility (task Sec. 11) -- operates ONLY on reference values
# ---------------------------------------------------------------------------
def compute_eligibility(mode_estimates: dict, alpha_p: float, pilot_n: float,
                        omega_lo: float = 0.35, omega_hi: float = 0.90,
                        ratio_min: float = 1.5,
                        min_expected_obs: float = 10.0) -> dict:
    """Deterministic eligibility checks E1-E6 from a reference table.

    ``mode_estimates``: {mid: {..., 'P_ref', 'L_ref'}} for MISSING modes.
    Rankings are descending (task Sec. 13).
    """
    mids = sorted(mode_estimates.keys())
    P = np.array([mode_estimates[m]["P_ref"] for m in mids])
    L = np.array([mode_estimates[m]["L_ref"] for m in mids])

    rankP = np.argsort(np.argsort(-P)) + 1     # descending ranks
    rankL = np.argsort(np.argsort(-L)) + 1

    kP_star = mids[int(np.argmax(P))]
    kV_star = mids[int(np.argmax(L))]

    inversions = []
    strongest = None
    for a_i in range(len(mids)):
        for b_i in range(len(mids)):
            if a_i == b_i:
                continue
            if P[a_i] > P[b_i] and L[a_i] < L[b_i]:
                pr = P[a_i] / P[b_i]
                lr = L[b_i] / L[a_i]
                inversions.append({"a": mids[a_i], "b": mids[b_i],
                                   "ratio_P": float(pr), "ratio_L": float(lr)})
                score = min(pr, lr)
                if strongest is None or score > strongest["score"]:
                    strongest = {**inversions[-1], "score": float(score)}
    strong_inversion = bool(strongest is not None
                            and strongest["ratio_P"] >= ratio_min
                            and strongest["ratio_L"] >= ratio_min)

    omega_v = L / max(L.sum(), 1e-300)
    top_idx = int(np.argmax(L))

    def kendall_tau(x: np.ndarray, y: np.ndarray) -> float:
        n = x.size
        if n < 2:
            return float("nan")
        num = den = 0
        for i in range(n):
            for j in range(i + 1, n):
                sx = int(np.sign(x[i] - x[j]))
                sy = int(np.sign(y[i] - y[j]))
                num += sx * sy
                den += abs(sx * sy)
        return float(num / den) if den > 0 else float("nan")

    def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
        rx = np.argsort(np.argsort(-x)).astype(float)
        ry = np.argsort(np.argsort(-y)).astype(float)
        if rx.std() == 0 or ry.std() == 0:
            return float("nan")
        return float(np.corrcoef(rx, ry)[0, 1])

    n_obs_needed = min_expected_obs
    e_checks = {
        "E1_K_missing_ge3": bool(len(mids) >= 3),
        "E2_observability": bool(np.all(P * alpha_p * pilot_n >= n_obs_needed)),
        "E3_top_rank_conflict": bool(kP_star != kV_star),
        "E4_strong_inversion": strong_inversion,
        "E5_variance_criticality": bool(float(omega_v[top_idx]) >= omega_lo),
        "E6_no_degenerate_domination": bool(float(omega_v[top_idx]) <= omega_hi),
    }
    return {
        "missing_modes": mids,
        "P_ref_order": [mids[i] for i in np.argsort(-P)],
        "L_ref_order": [mids[i] for i in np.argsort(-L)],
        "rank_P": {m: int(rankP[i]) for i, m in enumerate(mids)},
        "rank_L": {m: int(rankL[i]) for i, m in enumerate(mids)},
        "k_P_star": kP_star,
        "k_V_star": kV_star,
        "kendall_tau_PV": kendall_tau(P, L),
        "spearman_rho_PV": spearman_rho(P, L),
        "pairwise_inversions": inversions,
        "strongest_inversion": strongest,
        "omega_top_missing": float(omega_v[top_idx]),
        **e_checks,
        "eligible": bool(all(e_checks.values())),
    }


__all__ = [
    "BenchmarkConfig", "generate_candidate_pool",
    "reference_characterize", "compute_eligibility",
    "DIM", "NOMINAL", "MODE_IDS",
]
