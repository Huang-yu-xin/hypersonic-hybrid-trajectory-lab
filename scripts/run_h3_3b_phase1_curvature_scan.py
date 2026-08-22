#!/usr/bin/env python3
"""H3-3B Phase 1 -- Curvature Transition Scan (task book v2, FROZEN design).

Implements ``docs/phase_h/H3_3B_Phase1_Curvature_Transition_Scan_Task.md`` (v2):

  * Layer D (deterministic, primary): d_L(gamma) on a beta-pinned parabola
    family h_a(t) = c(a) + a (t-1.5)^2, with the *interior/boundary branch*
    of the mirror query point s = -mu_base = (1.5, 0) (task book Sec. 5.1).
    Two proposal conventions, reported separately:
        main : q = N(mu_base, I)   (frozen corpus anchor, offset anchor)
        aux  : q = N(x*_a, I)      (MPP-centred; Blindness Theorem 4.4
                                    predicts D_L* == 0 identically)
  * Grid bridge layer: frozen 481x401 grid replication per config (C1 gate).
  * Layer M (MC, main convention only): H3-3B pilot region estimator
    (C_eta, R_eta, G_eta, D_eta, S_eta; eta in {0.5, 0.8, 0.9}) + IS perf.
  * union-A control: union-level vs per-mode geometry under an MPP-of-union
    anchor (pseudo-mismatch ~3.19 expected; Note 4.7).
  * Second (non-quadratic) family probe: h = c + b |t-1.5|^r, r in {1.5, 3},
    Layer D only, gamma targets matched to the main family (Gate C7).
  * Gates P1-A/B/C auto-evaluation (pre-registered thresholds).

Claim boundary: measures the alignment response on the frozen synthetic
curved testbed family only; no regime-map completion, no optimal-proposal,
no causal VRF claims.  Frozen artifacts are read-only.

Schema: h3-3b-phase1-curvature-scan-v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, curve_fit, minimize_scalar
from scipy.stats import spearmanr
from scipy.special import logsumexp

REPO = Path(__file__).resolve().parents[1]
H3_2_DATASET = REPO / "tests" / "data" / "h3_2_leakage_point_dataset_v1.json"
OUT_JSON = REPO / "results" / "phase_h3" / "h3_3b_phase1_curvature_scan_v1.json"
FIG_DIR = REPO / "results" / "phase_h3"
FIG18 = FIG_DIR / "fig18_alignment_transition_curve.png"

# ---------------------------------------------------------------------------
# Frozen protocol constants (task book Sec. 1 / 3)
# ---------------------------------------------------------------------------
DIM = 4
NOMINAL = "S0"
V_OFFSET = 1.5                    # vertex offset, frozen B value
MU_BASE = np.array([-1.5, 0.0, 0.0, 0.0])
SEEDS = [1, 2120, 3, 4]
N_MC = 50_000                     # frozen synthetic MC exploration
N_IS = 200_000                    # frozen synthetic IS samples (antithetic)
ETAS = [0.5, 0.8, 0.9]
ETA_MAIN = 0.8
EPS = 1e-8

GRID_A = [0.0, 0.01, 0.02, 0.05, 0.05306, 0.075, 0.1, 0.2,
          0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
DRY_RUN_A = [0.0, 0.05306, 0.5, 3.0]

T_LO, T_HI, T_N = -6.0, 9.0, 300_001      # deterministic boundary scan
TOL_OPT = 1e-12
G1_GRID = np.linspace(-8.0, 8.0, 481)     # frozen bridge grid (H3-2)
G2_GRID = np.linspace(-6.0, 9.0, 401)

# pre-registered Gate thresholds (task book Sec. 7)
DELTA_MIS = 0.1
JUMP_THRESH = 0.3
GAP_RATIO_AMBIG = 1.05
GAMMA_TARGETS = [0.274, 0.848, 1.349]     # second-family gamma targets
SECOND_FAMILIES_R = [1.5, 3.0]


# ---------------------------------------------------------------------------
# Frozen anchors (read-only)
# ---------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_b_anchors() -> tuple[np.ndarray, np.ndarray, float]:
    data = json.loads(H3_2_DATASET.read_text(encoding="utf-8"))
    b = [e for e in data["experiments"]
         if e["experiment_id"] == "B_synthetic_curvature_beta_kappa"][0]
    s2 = [g for g in b["point_geometry"] if g["topology_label"] == "S2"][0]
    xs = np.asarray(s2["probability_design_point"], dtype=float)
    xl = np.asarray(s2["leakage_point"], dtype=float)
    return xs, xl, float(s2["distance_between_points"])


X_STAR_F, X_L_F, DL_FROZEN = _load_b_anchors()
BETA_B = float(np.linalg.norm(X_STAR_F[:2]))
DELTA0 = 1.5 - BETA_B                    # baked-in baseline offset (Sec. 5.2)
assert abs(BETA_B - 1.483825) < 1e-3, "beta_B drifted from frozen value"


# ---------------------------------------------------------------------------
# Boundary families
# ---------------------------------------------------------------------------
class Parabola:
    """h(t) = c + a (t-v)^2  (main family; a=0.5,c=1 reproduces frozen B)."""

    kind = "parabola"

    def __init__(self, a: float, c: float, v: float = V_OFFSET):
        self.a, self.c, self.v = float(a), float(c), float(v)

    def h(self, t):
        return self.c + self.a * (t - self.v) ** 2

    def hp(self, t):
        return 2.0 * self.a * (t - self.v)

    def hpp(self, _t):
        return 2.0 * self.a


class PowerFamily:
    """h(t) = c + b |t-v|^r   (second, non-quadratic family; Layer D only)."""

    kind = "power"

    def __init__(self, b: float, c: float, r: float, v: float = V_OFFSET):
        self.b, self.c, self.r, self.v = float(b), float(c), float(r), float(v)

    def h(self, t):
        return self.c + self.b * np.abs(t - self.v) ** self.r

    def hp(self, t):
        dt = t - self.v
        return self.b * self.r * np.sign(dt) * np.abs(dt) ** (self.r - 1.0)

    def hpp(self, t):
        dt = np.abs(t - self.v)
        return self.b * self.r * (self.r - 1.0) * dt ** (self.r - 2.0)


T_GRID = np.linspace(T_LO, T_HI, T_N)


# ---------------------------------------------------------------------------
# Layer D primitives (deterministic; interior/boundary branch per Sec. 5.1)
# ---------------------------------------------------------------------------
def _refine(fun, t0: float) -> float:
    lo = max(T_LO, t0 - 0.05)
    hi = min(T_HI, t0 + 0.05)
    r = minimize_scalar(fun, bounds=(lo, hi), method="bounded",
                        options={"xatol": TOL_OPT})
    return float(r.x)


def xs_on_boundary(fam):
    """argmin_t ||(h(t), t)||  ->  (x*, t*)."""
    f = fam.h(T_GRID) ** 2 + T_GRID ** 2
    t0 = float(T_GRID[int(np.argmin(f))])
    ts = _refine(lambda t: float(fam.h(t)) ** 2 + t * t, t0)
    return np.array([float(fam.h(ts)), ts]), ts


def in_interior(s: np.ndarray, fam) -> bool:
    """Kernel centre s strictly inside A_S2 = {u1 > h(u2)}?"""
    return bool(s[0] > fam.h(s[1]))


def xL_given_center(s: np.ndarray, fam) -> tuple[np.ndarray, str]:
    """argmax_A rho_V  <=>  argmin ||z - s|| over closure of A_S2.

    Interior branch: s in int(A)  =>  x_L = s (unconstrained mode).
    Boundary branch: constrained minimisation over the boundary graph.
    """
    if in_interior(s, fam):
        return np.array(s, dtype=float), "interior"
    g = (fam.h(T_GRID) - s[0]) ** 2 + (T_GRID - s[1]) ** 2
    t0 = float(T_GRID[int(np.argmin(g))])
    ts = _refine(lambda t: (float(fam.h(t)) - s[0]) ** 2 + (t - s[1]) ** 2, t0)
    return np.array([float(fam.h(ts)), ts]), "boundary"


def gap_ratio(values: np.ndarray) -> float:
    """Ratio of 2nd distinct local minimum to global min (C1-audit metric)."""
    v = np.asarray(values, dtype=float)
    interior = v[1:-1]
    loc = np.where((interior < v[:-2]) & (interior < v[2:]))[0] + 1
    mins = np.sort(v[loc])
    if mins.size < 2:
        return float("inf")
    return float(mins[1] / mins[0]) if mins[0] > 0 else float("inf")


def kappa_mpp(fam, ts: float) -> float:
    hp, hpp = float(fam.hp(ts)), float(fam.hpp(ts))
    return abs(hpp) / (1.0 + hp * hp) ** 1.5


def solve_c_for_beta(a: float) -> float:
    """Bisection: c(a) pinning the *continuous*-layer ||x*(a,c)|| = BETA_B.

    Well-posed: the continuous optimum moves smoothly with c.  (A grid-layer
    pinning would face a step-function landscape -- discrete argmin jumps --
    and is ill-posed for bisection; rejected during dry-run v2.1.)

    Anchor exception: at a = 0.5 the frozen boundary c = 1.0 is used
    VERBATIM (bit-exact frozen-B reproduction, task book Sec. 3.3); its
    continuous beta (=1.4793...) then deviates from the global BETA_B by
    ~0.3%, which is recorded per-config as the cost of bit-exact anchoring.
    """
    if a == 0.0:
        return BETA_B
    lo, hi = 0.02, 2.5
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fam = Parabola(a, mid)
        if float(np.linalg.norm(xs_on_boundary(fam)[0])) < BETA_B:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def family_for_config(a: float) -> tuple:
    """Family for a grid config: pinned series, except the a=0.5 anchor
    which is the exact frozen boundary (c = 1.0)."""
    if a == 0.5:
        return Parabola(0.5, 1.0), True
    return Parabola(a, solve_c_for_beta(a)), False


def solve_a_star() -> float:
    """Branch point: c(a) + 2.25 a = 1.5  (mirror query enters/leaves A_S2)."""
    return float(brentq(lambda a: solve_c_for_beta(a) + 2.25 * a - 1.5,
                        1e-4, 0.2, xtol=1e-10))


def grid_bridge_layer(fam) -> dict:
    """Frozen 481x401 grid replication (both conventions), C1 gate."""
    G1, G2 = np.meshgrid(G1_GRID, G2_GRID)
    mask = G1 > fam.h(G2)
    P = np.stack([G1[mask], G2[mask]], axis=1)
    xs = P[int(np.argmin(np.sum(P ** 2, axis=1)))]
    xL_main = P[int(np.argmin(np.sum((P + MU_BASE[:2]) ** 2, axis=1)))]
    xL_aux = P[int(np.argmin(np.sum((P - xs) ** 2, axis=1)))]
    return {
        "x_star": xs.tolist(),
        "x_L_main": xL_main.tolist(),
        "d_L_main": float(np.linalg.norm(xL_main - xs)),
        "x_L_aux": xL_aux.tolist(),
        "D_L_aux": float(np.linalg.norm(xL_aux - xs)),
        "n_points": int(P.shape[0]),
    }


def deterministic_config(a: float, fam: Parabola | None = None,
                         anchor_exact: bool = False) -> dict:
    """Full deterministic record for one grid value (both conventions)."""
    if fam is None:
        fam, anchor_exact = family_for_config(a)
    c = fam.c
    xs, ts = xs_on_boundary(fam)
    kappa = kappa_mpp(fam, ts)

    # main convention: kernel centre s = -mu_base = (1.5, 0)
    s_main = -MU_BASE[:2]
    xL_main, branch_main = xL_given_center(s_main, fam)
    f_main = (fam.h(T_GRID) - s_main[0]) ** 2 + (T_GRID - s_main[1]) ** 2 \
        if branch_main == "boundary" else None

    # aux convention: kernel centre s = -x*(a)  (Blindness Theorem 4.4)
    s_aux = -xs
    xL_aux, branch_aux = xL_given_center(s_aux, fam)
    f_aux = (fam.h(T_GRID) - s_aux[0]) ** 2 + (T_GRID - s_aux[1]) ** 2 \
        if branch_aux == "boundary" else None

    rec = {
        "a": a, "c": c, "t_star": ts,
        "anchor_exact_frozen": anchor_exact,
        "beta_continuous": float(np.linalg.norm(xs)),
        "x_star": [float(v) for v in xs],
        "beta": BETA_B,
        "kappa_mpp": kappa,
        "gamma": BETA_B * kappa,
        "main": {
            "kernel_center": [float(v) for v in s_main],
            "branch": branch_main,
            "x_L": [float(v) for v in xL_main],
            "d_L": float(np.linalg.norm(xL_main - xs)),
            "gap_ratio": gap_ratio(f_main) if f_main is not None
            else float("inf"),
            "analytic_note": "a=0: d_L = delta_0 = 1.5 - beta_B" if a == 0
            else None,
        },
        "aux": {
            "kernel_center": [float(v) for v in s_aux],
            "branch": branch_aux,
            "x_L": [float(v) for v in xL_aux],
            "D_L_star": float(np.linalg.norm(xL_aux - xs)),
            "gap_ratio": gap_ratio(f_aux) if f_aux is not None
            else float("inf"),
        },
        "grid_bridge": grid_bridge_layer(fam),
    }
    return rec


# ---------------------------------------------------------------------------
# union-A control (Note 4.7): frozen B geometry + S1 half-space
# ---------------------------------------------------------------------------
def union_a_control() -> dict:
    fam = Parabola(0.5, 1.0)                       # exact frozen B
    xs_s2, _ = xs_on_boundary(fam)
    xs_s1 = np.array([-1.5, 0.0])                  # closure of {u1 < -1.5}
    norms = [float(np.linalg.norm(xs_s2)), float(np.linalg.norm(xs_s1))]
    xs_union = xs_s2 if norms[0] <= norms[1] else xs_s1

    mirror = -xs_union
    # nearest point in S1 closure {u1 <= -1.5}
    proj_s1 = np.array([min(mirror[0], -1.5), mirror[1]])
    xL_s2, _ = xL_given_center(mirror, fam)
    d_s1 = float(np.linalg.norm(proj_s1 - mirror))
    d_s2 = float(np.linalg.norm(xL_s2 - mirror))
    xL_union = proj_s1 if d_s1 <= d_s2 else xL_s2
    dl_union = float(np.linalg.norm(xs_union - xL_union))

    # per-mode MPP-anchored checks (Theorem 4.4: must both be zero)
    xL_s2_mpp, br_s2 = xL_given_center(-xs_s2, fam)
    dl_s2_mpp = float(np.linalg.norm(xL_s2_mpp - xs_s2))
    dl_s1_mpp = float(np.linalg.norm(np.array([-1.5, 0.0]) - xs_s1))

    return {
        "x_star_S1": xs_s1.tolist(),
        "x_star_S2": [float(v) for v in xs_s2],
        "x_star_union": [float(v) for v in xs_union],
        "mirror": [float(v) for v in mirror],
        "x_L_union": [float(v) for v in xL_union],
        "D_L_union": dl_union,
        "nearest_mode": "S1" if d_s1 <= d_s2 else "S2",
        "per_mode_mpp_anchor": {
            "S1_D_L": dl_s1_mpp,
            "S2_D_L": dl_s2_mpp,
            "S2_branch": br_s2,
        },
        "expected": {"D_L_union": 3.193, "per_mode": 0.0},
    }


# ---------------------------------------------------------------------------
# Layer M (MC, main convention only) -- pilot idioms, Sigma = I
# ---------------------------------------------------------------------------
def log_w_general(z: np.ndarray, m: np.ndarray) -> np.ndarray:
    dz = z - m.reshape(1, -1)
    return -0.5 * np.sum(z * z, axis=1) + 0.5 * np.sum(dz * dz, axis=1)


def log_rho_v(z: np.ndarray, m: np.ndarray) -> np.ndarray:
    dz = z - m.reshape(1, -1)
    d = z.shape[1]
    return (-np.sum(z * z, axis=1) + 0.5 * np.sum(dz * dz, axis=1)
            - 0.5 * d * np.log(2.0 * np.pi))


def make_label_fn(fam: Parabola):
    def label(z: np.ndarray) -> np.ndarray:
        u1, u2 = z[:, 0], z[:, 1]
        lab = np.full(z.shape[0], NOMINAL, dtype=object)
        lab[u1 > fam.h(u2)] = "S2"
        lab[u1 < -1.5] = "S1"
        return lab
    return label


def sample_antithetic(rng, m: np.ndarray, n: int) -> np.ndarray:
    half = n // 2
    r = rng.standard_normal((half, m.size))
    return np.vstack([m + r, m - r])[:n]


def mode_region_geometry(z_mode, source, m, eta_list):
    lrho = log_rho_v(z_mode, m)
    lw = log_w_general(z_mode, m)
    lwV = np.where(np.asarray(source) == "is", 2.0 * lw, lw)
    lwV = lwV - logsumexp(lwV)
    wV = np.exp(lwV)
    if not np.all(np.isfinite(wV)):
        raise ValueError("degenerate variance-mass weights")

    x_star = z_mode[int(np.argmin(np.sum(z_mode ** 2, axis=1)))]
    x_L = z_mode[int(np.argmax(lrho))]
    order = np.argsort(lrho)[::-1]
    cum = np.cumsum(wV[order])
    per_eta = {}
    for eta in eta_list:
        k = int(np.searchsorted(cum, eta))
        reg = order[: k + 1]
        wv = wV[reg]
        m_eta = np.average(z_mode[reg], axis=0, weights=wv)
        R = float(np.sqrt(np.average(
            np.sum((z_mode[reg] - m_eta) ** 2, axis=1), weights=wv)))
        C = float(np.linalg.norm(m_eta - x_star))
        G = C / (R + EPS)
        D = float(np.min(np.linalg.norm(z_mode[reg] - x_star, axis=1)))
        per_eta[f"eta_{eta}"] = {
            "D": D, "R": R, "C": C, "G": G,
            "m_eta": [float(v) for v in m_eta],
            "n_points": int(reg.size), "mass": float(cum[k]),
        }
    return {
        "x_star": [float(v) for v in x_star],
        "x_L": [float(v) for v in x_L],
        "d_L_sample": float(np.linalg.norm(x_L - x_star)),
        "per_eta": per_eta,
    }


def mc_config_run(a: float, c: float, seeds: list[int],
                  fam: Parabola | None = None) -> dict:
    if fam is None:
        fam, _ = family_for_config(a)
    label = make_label_fn(fam)
    per_seed = {}
    for seed in seeds:
        rng = np.random.default_rng(seed)
        z_mc = rng.standard_normal((N_MC, DIM))
        labels_mc = label(z_mc)
        ind_mc = labels_mc != NOMINAL
        p_mc = float(ind_mc.mean())
        var_mc = p_mc * (1.0 - p_mc) / N_MC

        z_q = sample_antithetic(rng, MU_BASE, N_IS)
        labels_q = label(z_q)
        lw = log_w_general(z_q, MU_BASE)
        ind = (labels_q != NOMINAL).astype(float)
        n = N_IS
        p_is = float(np.exp(logsumexp(lw, b=ind) - np.log(n)))
        m2 = float(np.exp(logsumexp(2.0 * lw, b=ind) - np.log(n)))
        var_is = max(0.0, (m2 - p_is ** 2) / n)
        ess = float(np.exp(2.0 * logsumexp(lw) - logsumexp(2.0 * lw)))
        vrf = float("inf") if var_is <= 0.0 else var_mc / var_is

        region = {}
        for topo in sorted(set(labels_q.tolist()) | set(labels_mc.tolist())):
            if topo == NOMINAL:
                continue
            m_mc, m_is = labels_mc == topo, labels_q == topo
            if not (m_mc.any() or m_is.any()):
                continue
            z_mode = np.vstack([z_mc[m_mc], z_q[m_is]])
            src = np.concatenate([np.full(int(m_mc.sum()), "mc"),
                                  np.full(int(m_is.sum()), "is")])
            region[topo] = mode_region_geometry(z_mode, src, MU_BASE, ETAS)

        per_seed[str(seed)] = {
            "p_mc": p_mc, "var_mc": var_mc,
            "p_is": p_is, "m2_estimate": m2, "var_is": var_is,
            "ess": ess, "vrf": vrf,
            "n_accepted_is": int(ind.sum()),
            "region": region,
        }
    return per_seed


# ---------------------------------------------------------------------------
# Second non-quadratic family probe (Layer D only; task book Sec. 4.4)
# ---------------------------------------------------------------------------
def second_family_probe() -> list[dict]:
    out = []
    for r in SECOND_FAMILIES_R:
        for g_tgt in GAMMA_TARGETS:
            kappa_tgt = g_tgt / BETA_B

            def kap_of(b: float) -> float:
                c = _solve_c_power(b, r)
                fam = PowerFamily(b, c, r)
                _, ts = xs_on_boundary(fam)
                if abs(ts - fam.v) < 1e-4 and r < 2.0:
                    return float("nan")       # curvature blow-up guard
                return kappa_mpp(fam, ts)

            bs = np.linspace(0.02, 6.0, 25)
            kvals = np.array([kap_of(b) for b in bs])
            kvals = np.where(np.isfinite(kvals), kvals, np.nan)
            if np.all(np.isnan(kvals)) or np.nanmax(kvals) < kappa_tgt:
                out.append({"family": "power", "r": r, "gamma_target": g_tgt,
                            "reachable": False,
                            "note": "kappa target not attained on b grid"})
                continue
            b_sol = float(brentq(lambda b: kap_of(b) - kappa_tgt,
                                 bs[0], bs[np.nanmax(np.where(
                                     np.nan_to_num(kvals) >= kappa_tgt,
                                     np.arange(bs.size), 0))],
                                 xtol=1e-8))
            c_sol = _solve_c_power(b_sol, r)
            fam = PowerFamily(b_sol, c_sol, r)
            xs, ts = xs_on_boundary(fam)
            xL_main, br = xL_given_center(-MU_BASE[:2], fam)
            xL_aux, _ = xL_given_center(-xs, fam)
            out.append({
                "family": "power", "r": r, "gamma_target": g_tgt,
                "reachable": True, "b": b_sol, "c": c_sol, "t_star": ts,
                "x_star": [float(v) for v in xs],
                "kappa_mpp": kappa_mpp(fam, ts),
                "gamma": BETA_B * kappa_mpp(fam, ts),
                "main_branch": br,
                "d_L_main": float(np.linalg.norm(xL_main - xs)),
                "D_L_star_aux": float(np.linalg.norm(xL_aux - xs)),
            })
    return out


def _solve_c_power(b: float, r: float) -> float:
    lo, hi = 0.02, 2.5
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        fam = PowerFamily(b, mid, r)
        if float(np.linalg.norm(xs_on_boundary(fam)[0])) < BETA_B:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Gates (pre-registered; task book Sec. 7)
# ---------------------------------------------------------------------------
def evaluate_gates(det: list[dict], union: dict, second: list[dict],
                   mc: list[dict] | None, a_star: float) -> dict:
    main = [(r["gamma"], r["main"]["d_L"]) for r in det]
    gam = np.array([g for g, _ in main])
    dl = np.array([d for _, d in main])

    # A1: endpoints
    a0 = [r for r in det if r["a"] == 0.0][0]
    a1_main_ok = abs(a0["main"]["d_L"] - DELTA0) <= 1e-3
    a1_mis_ok = bool(np.max(dl) >= DELTA_MIS)

    # A2: s0 (curvature-branch linear fit) and gamma_sat
    g_star = BETA_B * kappa_mpp(Parabola(a_star, solve_c_for_beta(a_star)),
                                _t_star_at(a_star))
    win = (gam >= g_star) & (gam <= 2.0 * g_star)
    if win.sum() >= 2:
        s0 = float(np.polyfit(gam[win], dl[win], 1)[0])
    else:
        s0 = float("nan")
    d_inf = float(np.max(dl))
    sat = gam[dl >= 0.9 * d_inf]
    gamma_sat = float(sat.min()) if sat.size else float("nan")

    # A3: jump classification (branch-adjacent pairs excluded from the check)
    order = np.argsort(gam)
    adj = [(gam[i], gam[i + 1], dl[i], dl[i + 1],
            det[order[i]]["a"], det[order[i + 1]]["a"])
           for i in range(len(order) - 1)]
    jumps = [(g1, g2, abs(d2 - d1)) for g1, g2, d1, d2, aa, bb in adj
             if abs(d2 - d1) > JUMP_THRESH
             and not (min(aa, bb) <= a_star <= max(aa, bb))]
    shape = "jump/bifurcation" if jumps else "gradual-onset"

    # B: monotonicity
    rho, _ = spearmanr(gam, dl)
    viol = 0.0
    for i in range(len(order) - 1):
        aa = det[order[i]]["a"]
        bb = det[order[i + 1]]["a"]
        drop = dl[order[i]] - dl[order[i + 1]]
        if drop > 1e-3 and not (min(aa, bb) <= a_star <= max(aa, bb)):
            viol = max(viol, float(drop))

    # C1/C2/C5/C6
    anchor = [r for r in det if r["a"] == 0.5][0]
    c1_grid = abs(anchor["grid_bridge"]["d_L_main"] - DL_FROZEN) <= 0.01
    c1_cont = abs(anchor["main"]["d_L"] - DL_FROZEN) <= 0.05
    c2_aux = all(abs(r["aux"]["D_L_star"]) <= 1e-6 for r in det)
    c2_main_a0 = a1_main_ok
    c5 = c2_aux
    c6_union = abs(union["D_L_union"] - 3.193) <= 0.15
    c6_permode = (union["per_mode_mpp_anchor"]["S1_D_L"] <= 1e-6
                  and union["per_mode_mpp_anchor"]["S2_D_L"] <= 1e-6)

    # C7: second family direction
    ok_fam, ratio_lo, ratio_hi = True, [], []
    main_by_gamma = {round(g, 3): d for g, d in main}
    for rec in second:
        if not rec.get("reachable"):
            continue
        g = rec["gamma"]
        ref = min(main_by_gamma.items(), key=lambda kv: abs(kv[0] - round(g, 3)))
        if ref[1] > 0:
            ratio = rec["d_L_main"] / ref[1]
            ratio_lo.append(min(ratio, 1.0 / ratio))
            ratio_hi.append(max(ratio, 1.0 / ratio))
        if rec["d_L_main"] <= 0:
            ok_fam = False
    c7 = ok_fam and (not ratio_lo or min(ratio_lo) >= 1.0 / 3.0)

    gates = {
        "A": {"a1_main_delta0": a1_main_ok, "a1_mis_exists": a1_mis_ok,
              "shape": shape, "s0_curvature_branch": s0,
              "gamma_star": g_star, "gamma_sat": gamma_sat,
              "d_inf": d_inf, "jumps": jumps},
        "B": {"spearman_dL_gamma": float(rho), "max_violation": viol,
              "pass": bool(rho >= 0.9 and viol <= 1e-3)},
        "C": {"C1_grid": c1_grid, "C1_continuous": c1_cont,
              "C2_aux_zero": c2_aux, "C2_main_a0_delta0": c2_main_a0,
              "C5_blindness_zero": c5, "C6_union_value": c6_union,
              "C6_per_mode_zero": c6_permode, "C7_second_family": c7},
    }
    if mc is not None:
        anchor_mc = [r for r in mc if r["a"] == 0.5][0]
        dls = [seed["region"]["S2"]["d_L_sample"]
               for seed in anchor_mc["per_seed"].values() if "S2" in seed["region"]]
        gates["C"]["C4_seed_range_anchor"] = {
            "values": dls, "range": float(np.max(dls) - np.min(dls)),
            "pass_le_0.05": bool(np.max(dls) - np.min(dls) <= 0.05),
        }
    return gates


def _t_star_at(a: float) -> float:
    fam = Parabola(a, solve_c_for_beta(a))
    return xs_on_boundary(fam)[1]


# ---------------------------------------------------------------------------
# JSON safety + figure
# ---------------------------------------------------------------------------
def _safe(o):
    if isinstance(o, dict):
        return {k: _safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_safe(v) for v in o]
    if isinstance(o, float):
        if np.isnan(o):
            return "nan"
        if np.isinf(o):
            return "inf" if o > 0 else "-inf"
        return o
    if isinstance(o, (np.floating, np.integer)):
        return _safe(float(o))
    if isinstance(o, np.ndarray):
        return _safe(o.tolist())
    return o


def make_figure(det: list[dict], a_star: float, gates: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    gam = [r["gamma"] for r in det]
    dl = [r["main"]["d_L"] for r in det]
    dst = [r["aux"]["D_L_star"] for r in det]
    branches = [r["main"]["branch"] for r in det]
    g_star = BETA_B * kappa_mpp(Parabola(a_star, solve_c_for_beta(a_star)),
                                _t_star_at(a_star))

    ax = axes[0]
    for branch, color in [("interior", "#d62728"), ("boundary", "#1f77b4")]:
        pts = [(g, d) for g, d, b in zip(gam, dl, branches) if b == branch]
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-",
                    color=color, ms=4, label=f"{branch} branch")
    ax.axvline(g_star, ls="--", color="gray", lw=1,
               label=f"$a^*$ (branch, $\\gamma^*$={g_star:.3f})")
    ax.plot([0.8482], [DL_FROZEN], "*", color="black", ms=12,
            label="frozen B grid anchor (0.7751)")
    gs = gates["A"]
    ax.axhline(gs["d_inf"] * 0.9, ls=":", color="green", lw=1,
               label="90% plateau")
    ax.set_xlabel(r"$\gamma=\beta\kappa$")
    ax.set_ylabel(r"$d_L$  (main conv., $\mu_{base}$)")
    ax.set_title("Phase 1 alignment transition (Layer D)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(gam, dst, "s-", color="#2ca02c", ms=4)
    ax.set_xlabel(r"$\gamma=\beta\kappa$")
    ax.set_ylabel(r"$D_L^\star$  (aux conv., $m=x^*$)")
    ax.set_title("Blindness theorem check (Thm 4.4): expected identically 0")
    ax.set_ylim(-0.02, 0.1)
    ax.grid(alpha=0.3)

    fig.suptitle("H3-3B Phase 1 - Curvature Transition Scan (fig18)", y=1.02)
    fig.tight_layout()
    fig.savefig(FIG18, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="only the 4 pre-registered dry-run configs")
    ap.add_argument("--layer-d-only", action="store_true",
                    help="skip the MC layer (deterministic + controls only)")
    args = ap.parse_args()

    t0 = time.time()
    sha_before = _sha256(H3_2_DATASET)
    grid_a = DRY_RUN_A if args.dry_run else GRID_A

    a_star = solve_a_star()
    print(f"[init] beta_B={BETA_B:.6f}  delta0={DELTA0:.6f}  "
          f"d_L_frozen={DL_FROZEN:.4f}  a*={a_star:.5f}")

    fams = {}
    det = []
    for a in grid_a:
        fam, anchor_exact = family_for_config(a)
        fams[a] = fam
        rec = deterministic_config(a, fam, anchor_exact)
        det.append(rec)
        if anchor_exact:
            print(f"[anchor] a=0.5 uses frozen boundary c=1.0 verbatim "
                  f"(beta_continuous={rec['beta_continuous']:.6f}, "
                  f"deviates from beta_B by "
                  f"{abs(rec['beta_continuous'] - BETA_B) / BETA_B:.3%})")
    print(f"[layer-D] {len(det)} configs done ({time.time() - t0:.1f}s)")

    union = union_a_control()
    print(f"[union-A] D_L_union={union['D_L_union']:.4f} "
          f"(nearest {union['nearest_mode']})  per-mode S2="
          f"{union['per_mode_mpp_anchor']['S2_D_L']:.2e}")

    second = second_family_probe()
    n_reach = sum(1 for s in second if s.get("reachable"))
    print(f"[second-family] {n_reach}/{len(second)} configs reachable")

    mc = None
    if not args.layer_d_only:
        mc = []
        for a in grid_a:
            fam = fams[a]
            per_seed = mc_config_run(a, fam.c, SEEDS, fam)
            mc.append({"a": a, "c": fam.c, "per_seed": per_seed})
            s2 = per_seed[str(SEEDS[0])]["region"].get("S2")
            if s2:
                e = s2["per_eta"][f"eta_{ETA_MAIN}"]
                print(f"[layer-M] a={a:<6} seed1: R={e['R']:.3f} "
                      f"C={e['C']:.3f} G={e['G']:.3f} d_L_sample="
                      f"{s2['d_L_sample']:.4f}")
        print(f"[layer-M] done ({time.time() - t0:.1f}s total)")

    gates = evaluate_gates(det, union, second, mc, a_star)
    make_figure(det, a_star, gates)

    payload = {
        "schema_version": "h3-3b-phase1-curvature-scan-v1",
        "status": "COMPLETE" if not args.dry_run else "DRY_RUN",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task_ref": "docs/phase_h/H3_3B_Phase1_Curvature_Transition_Scan_Task.md (v2)",
        "theory_ref": "H3_3B_Theory_Extension.md Thm 4.4 / Cor 4.5 / Notes 4.6-4.7 / 5.1",
        "mode": "dry_run" if args.dry_run else
                ("layer_d_only" if args.layer_d_only else "full"),
        "frozen_inputs": {
            "dataset": str(H3_2_DATASET.relative_to(REPO)),
            "dataset_sha256": sha_before,
            "x_star_S2_frozen": X_STAR_F.tolist(),
            "x_L_S2_frozen": X_L_F.tolist(),
            "d_L_frozen": DL_FROZEN,
            "beta_B": BETA_B,
            "delta0_baseline_offset": DELTA0,
            "mu_base": MU_BASE.tolist(),
            "v_offset": V_OFFSET,
        },
        "grid_a": grid_a,
        "a_star_analytic": a_star,
        "seeds": SEEDS,
        "n_mc": N_MC, "n_is": N_IS,
        "deterministic": det,
        "union_A_control": union,
        "second_family_probe": second,
        "mc_layer": mc,
        "gates": gates,
        "integrity": {
            "dataset_sha256_after": _sha256(H3_2_DATASET),
            "unchanged": _sha256(H3_2_DATASET) == sha_before,
        },
        "wall_seconds": time.time() - t0,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(_safe(payload), indent=1),
                        encoding="utf-8")
    print(f"[out] {OUT_JSON}")
    print(f"[gates] A.shape={gates['A']['shape']}  "
          f"B.pass={gates['B']['pass']}  "
          f"C={ {k: v for k, v in gates['C'].items() if isinstance(v, bool)} }")
    print(f"[integrity] dataset unchanged: "
          f"{payload['integrity']['unchanged']}")


if __name__ == "__main__":
    main()
