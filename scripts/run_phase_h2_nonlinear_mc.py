"""Phase-H2 nonlinear Monte-Carlo validation & alpha validity audit generator.

VALIDATE ONLY -- validates the H1 first-order linear uncertainty model
against the FROZEN nonlinear trajectory model.  It performs NO new
physics, NO Phase-G derivative theory, NO topology-risk estimation, NO
uncertainty maps, NO optimization.

For each ``(model, alpha)`` cell it:

  * draws the SAME standardized antithetic sample bank (H0
    PAIRED_COMMON_RANDOM_NUMBERS; H2 §12);
  * propagates each sample through the frozen nonlinear Qian / Sanger
    research-trajectory integrators (production solver) and extracts BOTH
    the fixed-time T = 600 state and the native terminal (RTI / SRTI)
    from ONE run per sample (H2 §16, §17);
  * builds the SAMPLE-MATCHED linear ensemble from the accepted H1 maps
    (``tilde Phi``, ``eta S_A``, ``tilde J``) (H2 §20, §21);
  * classifies every sample against the frozen H0 taxonomy and applies the
    fixed-topology / terminal domain gates (H2 §22-§24, §41-§42);
  * computes the fixed-time / terminal discrepancy metrics and pair
    bootstrap intervals, and classifies the 1% / 5% numerical-accuracy
    levels (H2 §26-§48);
  * performs the REF-0.1 reference-solver subset (H2 §51-§52) and the deep
    Sanger N0-N5 secondary generality audit (H2 §55-§60);
  * writes ``tests/data/phase_h2_nonlinear_mc_validation_v1.json``
    (``schema_version = phase-h2-nonlinear-mc-validation-v1``).

Reproducibility: sample order, sampling seed, bootstrap seed, alpha order
and JSON key order are fixed; with a complete cache the snapshot is
byte-identical across runs.  A strictly-fingerprinted per-(case, alpha,
solver-profile) sample cache lives under ``results/phase_h2/cache/``.

Run::

    python scripts/run_phase_h2_nonlinear_mc.py --pilot        # N=256 grid
    python scripts/run_phase_h2_nonlinear_mc.py --primary      # sequential N on key alphas
    python scripts/run_phase_h2_nonlinear_mc.py --deep         # N0-N5 generality audit
    python scripts/run_phase_h2_nonlinear_mc.py --all          # full pipeline (cache-aware)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hyptraj.analysis.comparison_validation import (  # noqa: E402
    REFERENCE_05_SOLVER_CONFIG,
    REFERENCE_SOLVER_CONFIG,
)
from hyptraj.controls.constant_k import ConstantKControl  # noqa: E402
from hyptraj.models.parameters import (  # noqa: E402
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.predictability.hybrid_stm import build_hybrid_stm  # noqa: E402
from hyptraj.predictability.protocol import REPRESENTATIVE_CASES  # noqa: E402
from hyptraj.predictability.stm import stm_strict_reference_config  # noqa: E402
from hyptraj.simulation.dense_output import DenseOutputCollector  # noqa: E402
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG  # noqa: E402
from hyptraj.simulation.qian_research_trajectory import (  # noqa: E402
    integrate_qian_research_trajectory,
)
from hyptraj.simulation.sanger_research_trajectory import (  # noqa: E402
    integrate_sanger_research_trajectory,
)
from hyptraj.uncertainty.distributions import sample_initial_states  # noqa: E402
from hyptraj.uncertainty.nonlinear_validation import (  # noqa: E402
    accuracy_classification,
    classification_detail_counts,
    classify_fixed_time_sample,
    classify_terminal_sample,
    classification_counts,
    composite_terminal_discrepancy,
    domain_gate_status,
    extract_sample_observations,
    fixed_time_metrics,
    pair_bootstrap,
    signature_from_observables,
)
from hyptraj.uncertainty.sampling import NESTED_SAMPLE_SIZES, sample_bank  # noqa: E402

DATA = REPO / "tests" / "data"
RESULTS = REPO / "results" / "phase_h2"
CACHE = RESULTS / "cache"

H1 = json.loads((DATA / "phase_h1_linear_uncertainty_v1.json").read_text(
    encoding="utf-8"))
G5 = json.loads((DATA / "phase_g5_predictability_metrics_v1.json").read_text(
    encoding="utf-8"))

SCHEMA_VERSION = "phase-h2-nonlinear-mc-validation-v1"
STARTING_H1_COMMIT = "7120feb9cfd8c013a4bdc7ef27261d6e248ca440"
PHASE_G_COMMIT = "6fb75c4a5f7b6460a5c9503c99fe2b2b2c96854c"
PHASE_F_COMMIT = "96253f1ef7785764d8da3156d7d614d2b244b577"

ALPHA_GRID = (1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1)
T_PRIMARY = 600.0
MAX_TIME_S = 5000.0
PILOT_N = 256
MAX_N = 4096
N_BOOT = 1000

ENV = EnvironmentParams()
VEH = VehicleParams()
RE = float(ENV.earth_radius)
S = np.diag([1e5, 1.0, 7e3, 0.1])
Sinv = np.linalg.inv(S)
BANK = sample_bank()
STD_CASES = ("n0_deep", "n1_deep", "n2_deep", "n3_deep", "n4_deep", "n5_deep")
DEEP_HORIZON_CANDIDATES = (600.0, 300.0, 120.0, 60.0)

PROFILE_SOLVERS = {
    "production": PRODUCTION_SOLVER_CONFIG,
    "ref01": REFERENCE_SOLVER_CONFIG,
    "ref05": REFERENCE_05_SOLVER_CONFIG,
}
_TERMINAL_T = {"qian": 723.03797, "sanger": 1119.546}
_TERMINAL_STATE = {
    "qian": np.array(G5["terminal"]["qian"]["terminal_state"]),
    "sanger": np.array(G5["terminal"]["sanger"]["terminal_state"]),
}
_ETA_SCALED = {"qian": np.array(G5["terminal"]["qian"]["etaS"]),
               "sanger": np.array(G5["terminal"]["sanger"]["etaS"])}
_J_SCALED = {
    "qian": Sinv @ np.array(G5["terminal"]["qian"]["J"]) @ S,
    "sanger": Sinv @ np.array(G5["terminal"]["sanger"]["J"]) @ S,
}
_KERNEL_T = {m: _J_SCALED[m] @ _J_SCALED[m].T for m in ("qian", "sanger")}

MODE_CODES = {"QEG_GLIDE": 1.0, "ENTRY_CAPTURE": 2.0, "SANGER_ATM": 3.0,
              "SANGER_VAC": 4.0, "GROUND_CONTINUATION": 5.0}
KIND_CODES = {"RTI": 1.0, "GROUND_BEFORE_CAPTURE": 2.0,
              "GROUND_AFTER_CAPTURE_BEFORE_RTI": 3.0, "MAX_TIME": 4.0,
              "SOLVER_FAILURE": 5.0, "AMBIGUOUS_SIMULTANEOUS_EVENT": 6.0,
              "srti": 21.0, "ground_before_srti": 22.0, "max_time": 23.0,
              "grazing_or_unresolved_event": 25.0, "max_segments": 26.0,
              "solver_failure": 27.0, "UNKNOWN": 0.0}


def _fp() -> str:
    import hashlib
    blob = BANK.sha256 + "|" + json.dumps(
        {k: str(v) for k, v in PROFILE_SOLVERS.items()}, sort_keys=True) \
        + "|" + STARTING_H1_COMMIT[:12] + PHASE_G_COMMIT[:12]
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


CACHE_FP = _fp()
CACHE_DIR = CACHE / CACHE_FP
# H2R reaggregation mode: read cache ONLY, never run an expensive trajectory;
# a required-cache miss raises (H2R §20).
CACHE_ONLY = False


def _ini(x0: np.ndarray) -> InitialCondition:
    return InitialCondition(altitude=float(x0[0]) - RE, range_angle=float(x0[1]),
                            velocity=float(x0[2]),
                            flight_path_angle_deg=np.rad2deg(float(x0[3])))


def _integrate(model: str, x0: np.ndarray, k: float, solver, T: float, max_t: float):
    coll = DenseOutputCollector()
    if model == "qian":
        traj = integrate_qian_research_trajectory(
            ENV, VEH, _ini(x0), ConstantKControl(k), solver=solver,
            dense_output_collector=coll, max_time=max_t)
    else:
        traj = integrate_sanger_research_trajectory(
            ENV, VEH, _ini(x0), ConstantKControl(k), solver=solver,
            dense_output_collector=coll, max_time=max_t)
    return extract_sample_observations(model, traj, coll.segments, T)


def _obs_to_row(obs) -> np.ndarray:
    """13-column cache row layout:
    [0] terminal_time; [1:5] terminal_state; [5:9] state_T;
    [9] switches_at_T; [10] terminal_switches; [11] mode_code; [12] kind_code.
    """
    st = obs.get("state_T")
    st_arr = st if (st is not None and np.all(np.isfinite(st))) else np.full(4, np.nan)
    ts = np.asarray(obs["terminal_state"]).reshape(-1)
    return np.concatenate([
        [obs["terminal_time"] if np.isfinite(obs["terminal_time"]) else np.nan],
        np.asarray(ts, dtype=float), np.asarray(st_arr, dtype=float),
        [float(obs["switches_at_T"]), float(obs["terminal_switches"]),
         float(MODE_CODES.get(obs["mode_at_T"], 0.0)),
         float(KIND_CODES.get(obs["terminal_kind"], 0.0))],
    ]).astype(np.float64)


def _row_to_obs(model: str, row) -> dict:
    rmode = {v: k for k, v in MODE_CODES.items()}
    rkind = {v: k for k, v in KIND_CODES.items()}
    st = row[5:9]
    switches = int(row[9])
    mode_at_T = rmode.get(float(row[11]))
    obs = {"terminal_kind": rkind.get(float(row[12]), "UNKNOWN"),
           "terminal_time": float(row[0]),
           "terminal_state": np.asarray(row[1:5], dtype=float),
           "state_T": st if bool(np.all(np.isfinite(st))) else None,
           "switches_at_T": switches,
           "terminal_switches": int(row[10]),
           "mode_at_T": mode_at_T}
    # true-switch signature through T (H2R §8): reconstructed deterministically
    # from the stored observables for cache-only reaggregation.
    obs["true_switch_signature_at_T"] = signature_from_observables(
        model, switches, mode_at_T)
    return obs


def _cache_path(case: str, model: str, alpha: float, profile: str) -> Path:
    return CACHE_DIR / f"{model}__{case}__{profile}__alpha_{alpha:.6e}.npz"


def _cache_filled(case: str, model: str, alpha: float, profile: str) -> int:
    path = _cache_path(case, model, alpha, profile)
    if not path.exists():
        return 0
    with np.load(path) as f:
        return int(f["filled"][0])


def _load_or_build_cache(case: str, model: str, alpha: float, k: float,
                         xbar: np.ndarray, profile: str, T: float,
                         max_n: int = MAX_N) -> np.ndarray:
    """Deterministic per-(case, alpha, profile) sample cache (npz).

    The array is always sized ``(MAX_N, 15)``; only the first ``max_n``
    rows are REQUIRED to be filled.  A pilot call with ``max_n=256`` runs
    the first 256 samples and records ``filled=256``; a later sequential
    call with ``max_n=4096`` resumes from row 256 (H2 §14, §15, §67), so
    the pilot is cheap and the sequential expansion never recomputes.
    """
    path = _cache_path(case, model, alpha, profile)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    arr = np.full((MAX_N, 13), np.nan, dtype=np.float64)
    filled = 0
    if path.exists():
        with np.load(path) as f:
            arr = np.asarray(f["arr_0"], dtype=np.float64)
            filled = int(f["filled"][0])
    target = min(int(max_n), MAX_N)
    if CACHE_ONLY and filled < target:
        raise RuntimeError(
            f"cache-only reaggregation requires {case}/{model}/alpha={alpha:.2e}"
            f"/{profile} to have >= {target} rows; has {filled}.")
    solver = PROFILE_SOLVERS[profile]
    for i in range(filled, target):
        # H0 law: delta X0 = S_A (alpha z)  (canonical-A covariance geometry)
        x0 = np.asarray(xbar, dtype=float) + S @ (alpha * np.asarray(BANK.z[i]))
        try:
            obs = _integrate(model, x0, k, solver, T, MAX_TIME_S)
            arr[i] = _obs_to_row(obs)
        except Exception:
            fail_kind = "SOLVER_FAILURE" if model == "qian" else "solver_failure"
            arr[i] = _obs_to_row({"terminal_kind": fail_kind,
                                  "terminal_time": np.nan,
                                  "terminal_state": np.full(4, np.nan),
                                  "state_T": None, "switches_at_T": -1,
                                  "mode_at_T": None,
                                  "terminal_switches": -1})
        filled = i + 1
        if (i + 1) % 512 == 0:
            np.savez(path, arr_0=arr, filled=np.asarray([filled], np.int64))
    np.savez(path, arr_0=arr, filled=np.asarray([filled], np.int64))
    return arr


def _map_primary(model: str) -> dict:
    h1key = "qian_T600" if model == "qian" else "sanger_T600"
    return {"scaled_phi": np.array(H1["fixed_time"][h1key]["scaled_phi"]),
            "kernel": np.array(H1["fixed_time"][h1key]["kernel_ref_01"]),
            "eta_scaled": _ETA_SCALED[model], "J_scaled": _J_SCALED[model],
            "K_T": _KERNEL_T[model], "expected_kind": "RTI" if model == "qian"
            else "srti", "t_nom": _TERMINAL_T[model],
            "xT_nom": _TERMINAL_STATE[model]}


def _ensembles(model: str, alpha: float, n: int, obs_arr: np.ndarray,
               x_nom_T: np.ndarray, maps: dict) -> dict:
    z = BANK.z[:n]
    u = alpha * z
    y_L = u @ maps["scaled_phi"].T
    dt_L = maps["eta_scaled"] @ u.T
    zT_L = u @ maps["J_scaled"].T
    y_N = np.empty((n, 4)); dt_N = np.empty(n); zT_N = np.empty((n, 4))
    obs = []
    for i in range(n):
        row = obs_arr[i]
        o = _row_to_obs(model, row)
        obs.append(o)
        st = row[5:9]
        y_N[i] = Sinv @ (st - x_nom_T) if np.all(np.isfinite(st)) else np.full(4, np.nan)
        ts = row[1:5]
        dt_N[i] = row[0] - maps["t_nom"] if np.isfinite(row[0]) else np.nan
        zT_N[i] = Sinv @ (ts - maps["xT_nom"]) if np.all(np.isfinite(ts)) \
            else np.full(4, np.nan)
    return {"y_L": y_L, "y_N": y_N, "dt_L": dt_L, "dt_N": dt_N,
            "zT_L": zT_L, "zT_N": zT_N, "obs": obs}


def _nominal_obs(model: str, xbar: np.ndarray, k: float, T: float,
                 profile: str = "production") -> dict:
    """Nominal reference trajectory observation at a fixed time T (H2 §18)."""
    coll = DenseOutputCollector()
    solver = PROFILE_SOLVERS[profile]
    if model == "qian":
        traj = integrate_qian_research_trajectory(
            ENV, VEH, _ini(xbar), ConstantKControl(k), solver=solver,
            dense_output_collector=coll, max_time=MAX_TIME_S)
    else:
        traj = integrate_sanger_research_trajectory(
            ENV, VEH, _ini(xbar), ConstantKControl(k), solver=solver,
            dense_output_collector=coll, max_time=MAX_TIME_S)
    return extract_sample_observations(model, traj, coll.segments, T)


def _fixed_time_cell(model: str, alpha: float, n: int, ens: dict, maps: dict,
                     *, T: float, nominal_signature: tuple,
                     nominal_mode: str) -> dict:
    pairs = []
    for o in ens["obs"]:
        pairs.append(classify_fixed_time_sample(
            model, o, T=T, nominal_signature=nominal_signature,
            nominal_mode_at_T=nominal_mode))
    cls = [c for c, _ in pairs]
    counts = classification_counts(cls)
    detail_counts = classification_detail_counts(pairs)
    gate = domain_gate_status(cls)
    P_H1 = (alpha ** 2) * maps["kernel"]
    out = {"model": model, "alpha": round(float(alpha), 12), "T": T,
           "sample_count": n, "classification_counts": counts,
           "classification_detail_counts": detail_counts,
           "domain_gate_status": gate}
    if gate == "PASS":
        m = fixed_time_metrics(ens["y_L"], ens["y_N"], P_H1)
        med, lo, hi = pair_bootstrap(
            ens["y_L"], ens["y_N"],
            statistic=lambda L, NN: fixed_time_metrics(L, NN, P_H1)["E_H2"],
            n_boot=N_BOOT)
        st1 = accuracy_classification(med, lo, hi, 0.01, gate)
        st5 = accuracy_classification(med, lo, hi, 0.05, gate)
        out.update({
            "linear_sample_mean": [round(float(x), 10) for x in m["linear_sample_mean"]],
            "nonlinear_sample_mean": [round(float(x), 10) for x in m["nonlinear_sample_mean"]],
            "linear_sample_covariance": _mt(m["linear_sample_covariance"]),
            "nonlinear_sample_covariance": _mt(m["nonlinear_sample_covariance"]),
            "analytic_H1_covariance": _mt(m["analytic_H1_covariance"]),
            "E_sampling": round(m["E_sampling"], 10),
            "E_mu": round(m["E_mu"], 10), "E_cov": round(m["E_cov"], 10),
            "E_sigma1": round(m["E_sigma1"], 10),
            "principal_alignment": round(m["principal_alignment"], 10),
            "principal_angle": round(m["principal_angle"], 10),
            "marginal_std_linear": [round(float(x), 10) for x in m["marginal_std_linear"]],
            "marginal_std_nonlinear": [round(float(x), 10) for x in m["marginal_std_nonlinear"]],
            "marginal_relative_errors": _nn(list(m["marginal_relative_errors"])),
            "structural_zero_leakage": _nn(list(m["structural_zero_leakage"])),
            "E_marginal_max": round(m["E_marginal_max"], 10),
            "E_zero_max": round(m["E_zero_max"], 10),
            "E_H2": round(m["E_H2"], 10),
            "bootstrap": {"E_H2_median": round(med, 10), "lower95": round(lo, 10),
                          "upper95": round(hi, 10)},
            "status_1pct": st1, "status_5pct": st5,
        })
    else:
        out.update({"status_1pct": "DOMAIN_GATE_FAIL", "status_5pct": "DOMAIN_GATE_FAIL"})
    return out


def _terminal_cell(model: str, alpha: float, n: int, ens: dict, maps: dict) -> dict:
    expected = maps["expected_kind"]
    nominal_sw = 1 if model == "qian" else 4
    cls = []
    for o in ens["obs"]:
        c, _ = classify_terminal_sample(model, o, expected_kind=expected,
                                        nominal_terminal_switches=nominal_sw)
        cls.append(c)
    counts = classification_counts(cls)
    gate = domain_gate_status(cls)
    out = {"terminal_kind": expected, "classification_counts": counts,
           "terminal_gate_status": gate}
    if gate == "PASS":
        valid = [i for i, c in enumerate(cls) if c.value == "TOPOLOGY_PRESERVED"]
        dL = ens["dt_L"][valid]; dN = ens["dt_N"][valid]
        zL = ens["zT_L"][valid]; zN = ens["zT_N"][valid]
        P_T = (alpha ** 2) * maps["K_T"]
        # SINGLE SOURCE OF TRUTH for the terminal composite (H2R §16) -- it
        # now explicitly includes the state-time cross-covariance mismatch.
        # ``ts`` (full terminal-state sub-metrics) is recomputed here only
        # for serialization; the composite E_H2_terminal / cross fields are
        # taken from composite_terminal_discrepancy.
        ts = fixed_time_metrics(zL, zN, P_T)
        comp = composite_terminal_discrepancy(dL, dN, zL, zN, P_T)
        tt = comp["terminal_time"]
        cm = comp["cross"]
        eH2T = comp["E_H2_terminal"]
        # pair bootstrap recomputes the SAME corrected composite inside
        # every replicate (H2R §17).
        med, lo, hi = pair_bootstrap(
            dL, dN, zL, zN,
            statistic=lambda ddL, ddN, zzL, zzN:
            composite_terminal_discrepancy(ddL, ddN, zzL, zzN, P_T)["E_H2_terminal"],
            n_boot=N_BOOT)
        st1 = accuracy_classification(med, lo, hi, 0.01, gate)
        st5 = accuracy_classification(med, lo, hi, 0.05, gate)
        out.update({
            "linear_terminal_time_mean": round(tt["linear_terminal_time_mean"], 10),
            "nonlinear_terminal_time_mean": round(tt["nonlinear_terminal_time_mean"], 10),
            "linear_terminal_time_std": round(tt["linear_terminal_time_std"], 10),
            "nonlinear_terminal_time_std": round(tt["nonlinear_terminal_time_std"], 10),
            "linear_terminal_state_mean": [round(float(x), 10) for x in ts["linear_sample_mean"]],
            "nonlinear_terminal_state_mean": [round(float(x), 10) for x in ts["nonlinear_sample_mean"]],
            "linear_terminal_state_cov": _mt(ts["linear_sample_covariance"]),
            "nonlinear_terminal_state_cov": _mt(ts["nonlinear_sample_covariance"]),
            "linear_state_time_cross_cov": [round(float(x), 10) for x in cm["linear_state_time_cross_cov"]],
            "nonlinear_state_time_cross_cov": [round(float(x), 10) for x in cm["nonlinear_state_time_cross_cov"]],
            "linear_cross_norm": round(cm["linear_cross_norm"], 10),
            "cross_natural_scale": round(cm["cross_natural_scale"], 10),
            "cross_metric_mode": cm["cross_metric_mode"],
            "E_cross_rel": _nn([cm["E_cross_rel"]])[0],
            "E_cross_absnorm": round(cm["E_cross_absnorm"], 10),
            "E_cross_composite": round(cm["E_cross_composite"], 10),
            "E_t_mu": round(tt["E_t_mu"], 10), "E_t_sigma": round(tt["E_t_sigma"], 10),
            "E_cov_T": round(ts["E_cov"], 10), "E_sigma1_T": round(ts["E_sigma1"], 10),
            "E_H2_terminal": round(eH2T, 10),
            "bootstrap_terminal": {"E_H2_T_median": round(med, 10),
                                   "lower95": round(lo, 10), "upper95": round(hi, 10)},
            "status_1pct": st1, "status_5pct": st5,
        })
    else:
        out.update({"status_1pct": "DOMAIN_GATE_FAIL", "status_5pct": "DOMAIN_GATE_FAIL"})
    return out


def _mt(mat) -> list:
    return [[round(float(x), 10) for x in row] for row in np.asarray(mat)]


def _nn(vals) -> list:
    return [None if isinstance(x, float) and (np.isnan(x) or np.isinf(x)) else x
            for x in vals]


def _primary_cell(model: str, alpha: float, n: int) -> dict:
    xbar, k = _baseline_case_x0(-5.0, 3.0)
    nom = _nominal_obs(model, xbar, k, T_PRIMARY)
    maps = _map_primary(model)
    obs = _load_or_build_cache(f"baseline_T{T_PRIMARY:.0f}", model, alpha, k,
                               xbar, "production", T_PRIMARY, max_n=n)
    ens = _ensembles(model, alpha, n, obs, nom["state_T"], maps)
    ft = _fixed_time_cell(model, alpha, n, ens, maps, T=T_PRIMARY,
                          nominal_signature=nom["true_switch_signature_at_T"],
                          nominal_mode=nom["mode_at_T"])
    te = _terminal_cell(model, alpha, n, ens, maps)
    return {"fixed_time": ft, "terminal": te}


def _baseline_case_x0(gamma0_deg: float, k: float) -> tuple[np.ndarray, float]:
    return (np.array([RE + 100_000.0, 0.0, 7000.0, np.deg2rad(gamma0_deg)]), k)


# ---------------------------------------------------------------------------
# Pilot / primary / reference / deep drivers
# ---------------------------------------------------------------------------
def run_pilot() -> dict:
    print("== PILOT (N=256) ==")
    grid: dict = {}
    for model in ("qian", "sanger"):
        grid[model] = {}
        for alpha in ALPHA_GRID:
            r = _primary_cell(model, alpha, PILOT_N)
            grid[model][alpha] = r
            ft, te = r["fixed_time"], r["terminal"]
            print(f"  {model:6s} a={alpha:9.1e} gate={ft['domain_gate_status']:14s} "
                  f"E_mu={ft.get('E_mu', float('nan')):8.3f} E_cov={ft.get('E_cov', float('nan')):8.3f} "
                  f"E_H2={ft.get('E_H2', float('nan')):8.3f} 1%={ft.get('status_1pct','-'):15s} "
                  f"5%={ft.get('status_5pct','-'):15s} | Tgate={te['terminal_gate_status']:14s} "
                  f"T5%={te.get('status_5pct','-')}")
    return grid


def _select_targets(grid: dict) -> dict:
    """Informative alphas + max sequential N per (model, alpha) (H2 §15).

    * the smallest-alpha linear anchor is expanded to N=1024 only;
    * the largest PASS_1% and PASS_5% alphas and the first non-PASS_5%
      alpha (while the fixed-topology domain still holds) are expanded to
      N=4096 to pin the 1% / 5% validity brackets;
    * alphas whose fixed-topology domain gate ALREADY fails at pilot are
      NOT expanded further (no need to spend N to prove H1 invalid there).
    """
    targets = {}
    for model in ("qian", "sanger"):
        ft = {a: grid[model][a]["fixed_time"] for a in ALPHA_GRID}
        gate = {a: ft[a].get("domain_gate_status") for a in ALPHA_GRID}
        st1 = {a: ft[a].get("status_1pct") for a in ALPHA_GRID}
        st5 = {a: ft[a].get("status_5pct") for a in ALPHA_GRID}
        pass1 = [a for a in ALPHA_GRID if st1[a] == "PASS"]
        pass5 = [a for a in ALPHA_GRID if st5[a] == "PASS"]
        nonp5 = [a for a in ALPHA_GRID
                 if st5[a] not in ("PASS",) and gate[a] == "PASS"]
        targets[(model, ALPHA_GRID[0])] = 1024        # linear anchor
        if pass1:
            targets[(model, pass1[-1])] = 4096        # 1% boundary
        if pass5:
            targets[(model, pass5[-1])] = 4096        # 5% boundary
        if nonp5:
            targets[(model, nonp5[0])] = 4096         # first topped-5% alpha
    return targets


def run_primary(targets: dict) -> dict:
    print("== PRIMARY (sequential N) targets ==", targets)
    cells: dict = {}
    for (model, alpha), max_n in sorted(targets.items()):
        recs = []
        for n in NESTED_SAMPLE_SIZES:
            if n > max_n:
                break
            r = _primary_cell(model, alpha, n)
            ft = r["fixed_time"]
            ci = ft.get("bootstrap", {})
            print(f"  {model:6s} a={alpha:9.1e} N={n:5d} gate={ft['domain_gate_status']:14s} "
                  f"E_H2={ft.get('E_H2', float('nan')):8.3f} CI=[{ci.get('lower95', float('nan')):7.3f},"
                  f"{ci.get('upper95', float('nan')):7.3f}] 1%={ft.get('status_1pct','-'):15s} "
                  f"5%={ft.get('status_5pct','-'):15s}")
            recs.append(r)
        cells[(model, alpha)] = recs
    return cells


def run_primary_reaggregate() -> dict:
    """H2R §19-§22: reaggregate EVERY cached (model, alpha) cell at its
    cached sample depth -- cache-only (raises on a real cache miss), never
    re-running trajectories."""
    print("== PRIMARY REAGGREGATION (cache-only) ==")
    cells = {}
    for model in ("qian", "sanger"):
        for alpha in ALPHA_GRID:
            filled = _cache_filled(f"baseline_T{T_PRIMARY:.0f}", model, alpha,
                                   "production")
            if filled == 0:
                continue
            recs = []
            for n in NESTED_SAMPLE_SIZES:
                if n > filled:
                    break
                r = _primary_cell(model, alpha, n)
                recs.append(r)
                ft = r["fixed_time"]
                te = r["terminal"]
                print(f"  {model:6s} a={alpha:9.1e} N={n:5d} gate={ft['domain_gate_status']:14s} "
                      f"E_H2={ft.get('E_H2', float('nan')):8.3f} 1%={ft.get('status_1pct','-'):15s} "
                      f"5%={ft.get('status_5pct','-'):15s} | T5%={te.get('status_5pct','-')}")
            cells[(model, alpha)] = recs
    return cells


def run_reference_subset(best: dict) -> dict:
    print("== REFERENCE SUBSET (REF-0.1, 8 pairs) ==")
    out = {}
    for model in ("qian", "sanger"):
        alpha = None
        for a in reversed(ALPHA_GRID):
            r = best.get((model, a))
            if r:
                ft = r["fixed_time"]
                if ft["domain_gate_status"] == "PASS" and ft.get("status_5pct") == "PASS":
                    alpha = a
                    break
        if alpha is None:
            alpha = ALPHA_GRID[-1]
        xbar, k = _baseline_case_x0(-5.0, 3.0)
        prod = _load_or_build_cache(f"baseline_T{T_PRIMARY:.0f}", model, alpha, k,
                                    xbar, "production", T_PRIMARY, 16)
        ref = _load_or_build_cache(f"baseline_T{T_PRIMARY:.0f}", model, alpha, k,
                                   xbar, "ref01", T_PRIMARY, 16)
        xT_nom = _TERMINAL_STATE[model]
        max_scaled = 0.0
        max_tt = 0.0
        max_ts = 0.0
        for p in range(8):
            for sgn in (0, 1):
                i = 2 * p + sgn
                pr, rf = prod[i], ref[i]
                df = np.linalg.norm(Sinv @ (rf[5:9] - pr[5:9])) if (
                    np.all(np.isfinite(rf[5:9])) and np.all(np.isfinite(pr[5:9]))
                ) else float("inf")
                dtt = abs(rf[0] - pr[0]) if (np.isfinite(rf[0]) and np.isfinite(pr[0])) else float("inf")
                dts = np.linalg.norm(Sinv @ (rf[1:5] - pr[1:5])) if (
                    np.all(np.isfinite(rf[1:5])) and np.all(np.isfinite(pr[1:5]))
                ) else float("inf")
                max_scaled = max(max_scaled, df)
                max_tt = max(max_tt, dtt)
                max_ts = max(max_ts, dts)
        norm = max(max_scaled, max_tt, max_ts)
        out[model] = {"alpha": float(alpha), "n_samples": 16,
                      "T600_scaled_state_max_diff": round(max_scaled, 10),
                      "terminal_time_max_diff_s": round(max_tt, 10),
                      "terminal_state_scaled_max_diff": round(max_ts, 10),
                      "normalized_max_error": round(norm, 10),
                      "separation_status": "PASS" if norm < 1e-3 else "CHECK"}
        print(f"  {model:6s} a={alpha:9.1e} norm_err={norm:.3e} "
              f"{out[model]['separation_status']}")
    return out


def run_deep(cells: dict) -> dict:
    print("== DEEP N0-N5 AUDIT ==")
    horizon_ok = {}
    for T in DEEP_HORIZON_CANDIDATES:
        ok_all = True
        per = {}
        for case in STD_CASES:
            rep = next(c for c in REPRESENTATIVE_CASES if c.key == case)
            xbar, k = _baseline_case_x0(rep.gamma0_deg, rep.K)
            obs = _integrate("sanger", xbar, k, PRODUCTION_SOLVER_CONFIG, T, MAX_TIME_S)
            t_end = float(obs["terminal_time"])
            try:
                build_hybrid_stm("sanger", xbar, T, ENV, VEH, k,
                                 research_solver=PRODUCTION_SOLVER_CONFIG,
                                 stm_solver=stm_strict_reference_config())
                stm_ok = True
            except Exception:
                stm_ok = False
            per[case] = {"terminal_time": t_end, "terminal_kind": obs["terminal_kind"],
                         "stm_ok": stm_ok, "ok": (t_end > T and stm_ok)}
            ok_all = ok_all and per[case]["ok"]
        horizon_ok[T] = per
        if ok_all:
            t_deep = T
            break
    else:
        return {"status": "DEEP_AUDIT_NOT_RUN_NO_COMMON_HORIZON",
                "horizon_info": {str(k): v for k, v in horizon_ok.items()}}
    # alpha_deep = largest common PASS_1% from the primary / pilot best cells
    common = []
    for a in ALPHA_GRID:
        q = cells.get(("qian", a))
        s = cells.get(("sanger", a))
        if q and s and q["fixed_time"].get("status_1pct") == "PASS" \
                and s["fixed_time"].get("status_1pct") == "PASS":
            common.append(a)
    if not common:
        return {"status": "DEEP_AUDIT_NOT_RUN_NO_COMMON_PASS_1PCT", "t_deep": float(t_deep)}
    alpha_deep = max(common)
    per_deep = {}
    for case in STD_CASES:
        rep = next(c for c in REPRESENTATIVE_CASES if c.key == case)
        xbar, k = _baseline_case_x0(rep.gamma0_deg, rep.K)
        nom = _nominal_obs("sanger", xbar, k, t_deep)
        kernel = _deep_kernel(xbar, k, t_deep)
        # deep audit is FIXED-TIME only: the terminal map keys are present
        # as placeholders because _ensembles assembles them unconditionally.
        maps = {"scaled_phi": _deep_phi(xbar, k, t_deep), "kernel": kernel,
                "expected_kind": "srti", "t_nom": 0.0, "xT_nom": np.zeros(4),
                "eta_scaled": np.zeros(4), "J_scaled": np.zeros((4, 4))}
        obs = _load_or_build_cache(case, "sanger", alpha_deep, k, xbar,
                                   "production", t_deep, 256)
        ens = _ensembles("sanger", alpha_deep, 256, obs, nom["state_T"], maps)
        ft = _fixed_time_cell(
            "sanger", alpha_deep, 256, ens, maps, T=t_deep,
            nominal_signature=nom["true_switch_signature_at_T"],
            nominal_mode=nom["mode_at_T"])
        per_deep[case] = {
            "gamma0_deg": float(rep.gamma0_deg), "K": float(rep.K),
            "t_deep": float(t_deep),
            "nominal_terminal_time": horizon_ok[t_deep][case]["terminal_time"],
            "nominal_switches_at_t_deep": int(nom["switches_at_T"]),
            "nominal_mode_at_t_deep": nom["mode_at_T"],
            "topology_gate": ft["domain_gate_status"],
            "E_H2": ft.get("E_H2"),
            "status_5pct": ft.get("status_5pct"),
        }
        print(f"  {case:8s} a={alpha_deep:9.1e} N=256 switches={nom['switches_at_T']} "
              f"gate={ft['domain_gate_status']:14s} E_H2={ft.get('E_H2', float('nan')):8.3f} "
              f"5%={ft.get('status_5pct','-')}")
    return {"status": "DEEP_FIXED_TOPOLOGY_GENERALITY_AUDIT", "t_deep": float(t_deep),
            "alpha_deep": float(alpha_deep), "n": 256, "cases": per_deep}


def _deep_phi(xbar, k, T) -> np.ndarray:
    r = build_hybrid_stm("sanger", xbar, T, ENV, VEH, k,
                         research_solver=PRODUCTION_SOLVER_CONFIG,
                         stm_solver=stm_strict_reference_config())
    return Sinv @ np.asarray(r.phi_final) @ S


def _deep_kernel(xbar, k, T) -> np.ndarray:
    phi = _deep_phi(xbar, k, T)
    return phi @ phi.T


# ---------------------------------------------------------------------------
# Snapshot assembly / CLI
# ---------------------------------------------------------------------------
def _alpha_validity_table(cells) -> dict:
    """``cells`` maps (model, alpha) to the BEST (highest-N) record."""
    out = {}
    for obj, model, kind in (("qian_T600", "qian", "fixed"),
                             ("sanger_T600", "sanger", "fixed"),
                             ("qian_RTI", "qian", "terminal"),
                             ("sanger_SRTI", "sanger", "terminal")):
        tbl = {}
        for a in ALPHA_GRID:
            r = cells.get((model, a))
            if r is None:
                continue
            if kind == "fixed":
                ft = r["fixed_time"]
                tbl[a] = {"status_1pct": ft.get("status_1pct"),
                          "status_5pct": ft.get("status_5pct"),
                          "E_H2": ft.get("E_H2"),
                          "limiting_mechanism": _limiting(ft)}
            else:
                te = r["terminal"]
                tbl[a] = {"status_1pct": te.get("status_1pct"),
                          "status_5pct": te.get("status_5pct"),
                          "E_H2_terminal": te.get("E_H2_terminal"),
                          "limiting_mechanism": _limiting_terminal(te)}
        if tbl:
            out[obj] = {"alpha_profile": tbl,
                        ** _bracket(tbl, kind)}
    return out


def _limiting(ft: dict) -> str:
    if ft.get("domain_gate_status") == "DOMAIN_GATE_FAIL":
        return "FIXED_TOPOLOGY_DOMAIN_GATE"
    if "E_H2" not in ft:
        return "INSUFFICIENT_MC_CONVERGENCE"
    vals = [("NONLINEAR_MEAN_SHIFT", ft["E_mu"]),
            ("NONLINEAR_COVARIANCE_ERROR", ft["E_cov"]),
            ("PRINCIPAL_SPREAD_ERROR", ft["E_sigma1"]),
            ("MARGINAL_ERROR", ft.get("E_marginal_max", 0.0)),
            ("STRUCTURAL_ZERO_LEAKAGE", ft.get("E_zero_max", 0.0))]
    return max(vals, key=lambda x: x[1])[0]


def _limiting_terminal(te: dict) -> str:
    if te.get("terminal_gate_status") == "DOMAIN_GATE_FAIL":
        return "TERMINAL_DOMAIN_GATE"
    if "E_H2_terminal" not in te:
        return "INSUFFICIENT_MC_CONVERGENCE"
    comps = [("TERMINAL_TIME_NONLINEARITY", te.get("E_t_mu", 0), te.get("E_t_sigma", 0)),
             ("TERMINAL_STATE_NONLINEARITY", te.get("E_cov_T", 0), te.get("E_sigma1_T", 0))]
    return max(comps, key=lambda x: max(x[1], x[2]))[0]


def _bracket(tbl: dict, kind: str) -> dict:
    ekey = "E_H2" if kind == "fixed" else "E_H2_terminal"
    keys1 = [a for a, v in tbl.items() if v["status_1pct"] == "PASS"]
    keys5 = [a for a, v in tbl.items() if v["status_5pct"] == "PASS"]
    non1 = [a for a in ALPHA_GRID if a in tbl and tbl[a]["status_1pct"] not in ("PASS",)]
    non5 = [a for a in ALPHA_GRID if a in tbl and tbl[a]["status_5pct"] not in ("PASS",)]
    statuses = [tbl[a]["status_1pct"] for a in ALPHA_GRID if a in tbl]
    mono = all(s in ("PASS", "DOMAIN_GATE_FAIL") for s in statuses) or \
        statuses == sorted(statuses, key=lambda s: 0 if s == "PASS" else 1)
    return {
        "largest_PASS_1pct": float(keys1[-1]) if keys1 else None,
        "first_nonPASS_1pct": float(non1[0]) if non1 else None,
        "largest_PASS_5pct": float(keys5[-1]) if keys5 else None,
        "first_nonPASS_5pct": float(non5[0]) if non5 else None,
        "monotone_profile": bool(mono),
        "limiting_mechanism": _bracket_limiting(keys5, keys1, tbl),
    }


def _bracket_limiting(keys5, keys1, tbl) -> str:
    if keys5:
        a = keys5[-1]
        if tbl[a].get("limiting_mechanism"):
            return tbl[a]["limiting_mechanism"]
    if keys1:
        return tbl[keys1[-1]].get("limiting_mechanism", "NONLINEAR_COVARIANCE_ERROR")
    return "NONLINEAR_COVARIANCE_ERROR"


def _merge_cells(pilot: dict, primary: dict) -> dict:
    """Best record per (model, alpha): sequential highest-N or pilot N=256."""
    best = {}
    for model in ("qian", "sanger"):
        for a in ALPHA_GRID:
            if (model, a) in primary and primary[(model, a)]:
                best[(model, a)] = primary[(model, a)][-1]
            elif a in pilot.get(model, {}):
                best[(model, a)] = pilot[model][a]
    return best


def build_snapshot(primary, reference, deep, pilot) -> dict:
    best = _merge_cells(pilot, primary)
    primary_serial = {}
    for (model, alpha), recs in sorted(primary.items()):
        sizes = list(NESTED_SAMPLE_SIZES)[: len(recs)]
        primary_serial[f"{model}|{alpha}"] = [
            {"sample_count": n, "fixed_time": r["fixed_time"],
             "terminal": r["terminal"]}
            for n, r in zip(sizes, recs)]
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": "phase-h-uncertainty-risk-protocol-v1",
        "h1_snapshot_schema": "phase-h1-linear-uncertainty-v1",
        "starting_h1_commit": STARTING_H1_COMMIT,
        "upstream_phase_g_commit": PHASE_G_COMMIT,
        "upstream_phase_f_commit": PHASE_F_COMMIT,
        # H2R corrective provenance: the same physical experiment (sampling
        # seed / bank / alpha grid / nonlinear model) reaggregated with the
        # endpoint-scoped fixed-time gate and the corrected terminal joint
        # metric.  The sample bank is preserved bit-for-bit (H2R §31).
        "h2r": {
            "endpoint_scoped_fixed_time_gate": True,
            "terminal_cross_covariance_in_composite": True,
            "terminal_cross_covariance_in_bootstrap": True,
            "sample_bank_changed": False,
            "alpha_grid_changed": False,
            "nonlinear_model_changed": False,
            "reaggregation_mode": "cache_only",
        },
        "sample_law": {
            "distribution": "Z0 = S_A^-1 delta X0 ~ N(0, alpha^2 I) (canonical R=I)",
            "canonical_scale": {"r": 1e5, "theta": 1.0, "v": 7e3, "gamma": 0.1},
            "alpha_status": "PENDING_NUMERICAL_AUDIT",
            "alpha_role": "synthetic dimensionless research amplitude (numerical probes)",
        },
        "sampling": {
            "seed": 2026, "bootstrap_seed": 2027, "bit_generator": "PCG64",
            "antithetic": True, "antithetic_ordering": "z1,-z1,z2,-z2,...",
            "sample_bank_sha256": BANK.sha256, "n_max_samples": BANK.n_max,
            "nested_sample_sizes": list(NESTED_SAMPLE_SIZES),
            "common_random_numbers": True, "sample_matched_linear_comparator": True,
        },
        "alpha_probe_grid": [float(a) for a in ALPHA_GRID],
        "T_primary": T_PRIMARY,
        "bulk_solver": str(PRODUCTION_SOLVER_CONFIG),
        "reference_subset_solver": str(REFERENCE_SOLVER_CONFIG),
        "pilot": {m: {str(a): r for a, r in grid.items()}
                  for m, grid in pilot.items()},
        "primary": primary_serial,
        "reference_subset": reference,
        "deep_generality_audit": deep,
        "alpha_validity": _alpha_validity_table(best),
        "claim_boundaries": {
            "synthetic_uncertainty_only": True,
            "no_real_world_calibration": True,
            "common_random_numbers": True,
            "antithetic_sampling": True,
            "sample_matched_linear_comparator": True,
            "topology_probability_not_estimated": True,
            "B0_B4_not_sampled": True,
            "mixture_analysis_not_performed": True,
            "optimization_not_performed": True,
            "interception_not_performed": True,
            "survival_not_performed": True,
        },
    }


def main() -> None:
    global CACHE_ONLY
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--primary", action="store_true")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--reaggregate-only", action="store_true",
                    help="H2R: reclassify / re-metric / re-bootstrap / rebuild "
                         "the snapshot from the existing cache ONLY; raise on "
                         "a required cache miss, never run trajectories")
    ap.add_argument("--workers", type=int, default=1,
                    help="accepted for interface parity; output is worker-independent "
                         "(this build runs single-process)")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if args.reaggregate_only:
        CACHE_ONLY = True
        pilot = run_pilot()
        cells = run_primary_reaggregate()
        best = _merge_cells(pilot, cells)
        ref = run_reference_subset(best)
        deep = run_deep(best)
    else:
        pilot = {}
        cells = {}
        ref = {}
        deep = {}
        if args.pilot or args.all:
            pilot = run_pilot()
        if args.primary or args.all:
            targets = _select_targets(pilot) if pilot else {}
            cells = run_primary(targets)
        best = _merge_cells(pilot, cells)
        if args.primary or args.all:
            ref = run_reference_subset(best)
        if args.deep or args.all:
            deep = run_deep(best)

    if not (args.pilot or args.primary or args.deep or args.all
            or args.reaggregate_only):
        ap.error("choose --pilot / --primary / --deep / --all / --reaggregate-only")

    if args.write:
        snap = build_snapshot(cells, ref, deep, pilot)
        out = DATA / "phase_h2_nonlinear_mc_validation_v1.json"
        out.write_text(json.dumps(snap, indent=1, ensure_ascii=False, sort_keys=True),
                       encoding="utf-8")
        print("wrote", out.relative_to(REPO))
    else:
        print("dry run (no snapshot written); add --write to emit.")


if __name__ == "__main__":
    main()
