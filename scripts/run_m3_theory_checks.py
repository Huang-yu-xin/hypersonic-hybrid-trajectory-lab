"""M3 -- theory proof obligation (task Sec. 18/19): validate the candidate
matrix / isotropic second-moment gradient against central finite differences
on deterministic quadrature toys BEFORE any benchmark science.

Locked constants come from configs/phase_m3/m3_scalar_gradient_v0.json
(gates.M3_1_numerical_gradient_validity): h = 1e-3, sign agreement 100%,
relative error <= 5e-3; FAILURE => STOP (exit code 1), no benchmark may start.

Cases
-----
identity_fullplane   p == q single Gaussian on the full plane:
                     M2 == 1 exactly and grad ~ 0 -> audit-only sanity
s1_halfspace_single  one-component proposal, half-space event region;
                     matrix directions {I/sqrt(d), e11, e22, offdiag sym}
                     at several interior Sigma_0 incl. anisotropic ones,
                     PLUS isotropic-path dM2/dtheta probes
s2_two_component     two-component mixtures, responsibility weighting
                     exercised on BOTH components k
s3_narrow_widen      explanatory demo: responsibility mass outruns the
                     component radius => g<0, WIDEN step lowers M2

Outputs -> results/phase_m3/theory_checks/theory_checks_v1.json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from hyptraj.m3.covariance_gradient import (           # noqa: E402
    MixtureSpec,
    directional_finite_difference,
    m2_of_sigma,
    variance_measure_moments,
    with_component_covariance,
)

CFG = json.loads((REPO / "configs" / "phase_m3"
                  / "m3_scalar_gradient_v0.json").read_text(encoding="utf-8"))
GATE = CFG["gates_locked"]["M3_1_numerical_gradient_validity"]
H = float(GATE["fd_h_main"])
REL_MAX = float(GATE["relative_error_max"])

TASK_SHA = hashlib.sha256((REPO / "docs" / "phase_m3"
                           / "M3_Second_Moment_Gradient_Covariance_Control_Task.md")
                          .read_bytes()).hexdigest()
FREEZE_SHA = hashlib.sha256((REPO / "docs" / "phase_m1d"
                             / "M1_D_Benchmark_Freeze.json").read_bytes()).hexdigest()

N_QUAD = 320          # primary resolution (convergence-QA'd below)
N_QUAD_REF = 480      # refinement used only for the QA crosscheck


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- #
# toy targets / regions
# --------------------------------------------------------------------------- #
def gauss_mix_logpdf(pi, means, covs):
    spec = MixtureSpec(np.asarray(pi, float),
                       np.asarray(means, float),
                       tuple(np.asarray(c, float) for c in covs))

    def f(z):
        from hyptraj.m3.covariance_gradient import mixture_log_density
        return mixture_log_density(spec, z)
    return f


def half_space(t: float):
    def f(z):
        return z[:, 0] >= t
    return f


def full_plane():
    def f(z):
        return np.ones(z.shape[0], dtype=bool)
    return f


def _sym_directions(dim: int) -> dict[str, np.ndarray]:
    """Spanning set of the symmetric matrices, Frobenius-normalized."""
    out = {}
    eye = np.eye(dim)
    out["isotropic"] = eye / np.sqrt(dim)
    for i in range(dim):
        E = np.zeros((dim, dim))
        E[i, i] = 1.0
        out[f"e{i}{i}"] = E
    if dim >= 2:
        off = np.array([[0.0, 0.5], [0.5, 0.0]])
        out["offdiag_sym"] = off / np.linalg.norm(off)
    return out


CHECKS: list[dict] = []
AUDITS: list[dict] = []


def record_check(case, probe_kind, label, sigma0, analytic, fd,
                 abs_floor: float = 1e-30) -> None:
    """Gate one directional probe.

    ``abs_floor`` is a case-local curvature-scale threshold below which BOTH
    sides count as structurally zero (exact symmetry directions yield
    analytic ~ 1e-15 and truncated-quadrature fd == 0.0 -- comparing their
    RATIO would be ill-posed). Otherwise the preregistered relative budget
    applies."""
    denom = max(abs(analytic), float(abs_floor))
    rel = abs(fd - analytic) / denom
    structurally_zero = max(abs(analytic), abs(fd)) <= abs_floor
    sign_ok = bool(np.sign(analytic) == np.sign(fd)) \
        if not structurally_zero else True
    CHECKS.append({
        "case": case, "probe": probe_kind, "label": label,
        "sigma0": np.asarray(sigma0, float).tolist(),
        "analytic": float(analytic), "fd_h1e-3": float(fd),
        "abs_err": float(abs(fd - analytic)), "rel_err": float(rel),
        "structurally_zero": bool(structurally_zero),
        "sign_agreement": bool(sign_ok),
        "pass": bool((structurally_zero and abs(fd - analytic) <= abs_floor)
                     or (rel <= REL_MAX and sign_ok)),
    })


def audit_matrix_gradient(case, target_logp, region_fn, spec, k,
                          reach, n_quad=N_QUAD) -> None:
    """Directional checks of the boxed matrix theorem across a spanning set."""
    mom = variance_measure_moments(spec, k, target_logp, region_fn, reach,
                                   n_per_axis=n_quad)
    # structurally-zero floor: exact symmetry directions have analytic ~ 1e-15
    grad_scale = max(1.0, float(np.max(np.abs(mom.grad_matrix))))
    floor = 1e-9 * grad_scale
    s0 = spec.covs[k]
    for name, E in _sym_directions(spec.dim).items():
        fd = directional_finite_difference(target_logp, region_fn, spec, k,
                                           s0, E, H, reach, n_per_axis=n_quad)
        analytic = float(np.sum(mom.grad_matrix * E))
        record_check(case, "matrix_direction", name, s0, analytic, fd,
                     abs_floor=floor)


def audit_isotropic(case, target_logp, region_fn, spec, k,
                    reach, n_quad=N_QUAD) -> None:
    """Isotropic formula (5) vs FD of theta = log s^2 path."""
    sigma = np.asarray(spec.covs[k], dtype=float)
    dim = sigma.shape[0]
    # requires the tested slice to be exactly isotropic
    if not np.allclose(sigma, float(np.trace(sigma) / dim) * np.eye(dim)):
        raise ValueError("audit_isotropic needs an isotropic slice")
    mom_iso = variance_measure_moments(spec, k, target_logp, region_fn,
                                       reach, n_per_axis=n_quad)

    # FD along theta: probe covariances s^2 I * exp(+/-h)
    s2_0 = float(sigma[0, 0])
    up = m2_of_sigma(target_logp, region_fn, spec, k,
                     s2_0 * np.exp(H) * np.eye(dim), reach, n_per_axis=n_quad)
    dn = m2_of_sigma(target_logp, region_fn, spec, k,
                     s2_0 * np.exp(-H) * np.eye(dim), reach, n_per_axis=n_quad)
    fd = (up - dn) / (2.0 * H)
    record_check(case, "isotropic_theta", f"s2={s2_0:g}", sigma,
                 mom_iso.g_isotropic, fd)


def run_case_identity() -> None:
    """p == q single standard Gaussian, full plane: M2 == 1, grad ~ 0."""
    lp = gauss_mix_logpdf([1.0], [[0.0, 0.0]], [np.eye(2)])
    spec = MixtureSpec(np.array([1.0]), np.array([[0.0, 0.0]]),
                       (np.eye(2),))
    mom = variance_measure_moments(spec, 0, lp, full_plane(), reach=10.0,
                                   n_per_axis=N_QUAD)
    AUDITS.append({
        "case": "identity_fullplane",
        "M2": float(mom.M2),
        "M2_abs_dev_from_1": float(abs(mom.M2 - 1.0)),
        "max_abs_grad_entry": float(np.max(np.abs(mom.grad_matrix))),
        "max_abs_g_isotropic": float(abs(mom.g_isotropic)),
        "quadrature_acc_budget": 1e-7,
        "pass": bool(abs(mom.M2 - 1.0) < 1e-7
                     and np.max(np.abs(mom.grad_matrix)) < 1e-6
                     and abs(mom.g_isotropic) < 1e-6),
    })


def run_case_s1() -> None:
    """Single-component probe points, ALL inside assumption A3's integrability
    window: single-vs-single Gaussian p^2/q decays on axis i iff
    s^2 > lambda_i(P) / 2 (= 0.72 here); probes below the window make M2
    exponentially ill-conditioned (~e^260) and are MEANINGLESS FD targets --
    they violate A3 rather than refute the theorem (see derivation Sec. 3)."""
    lp = gauss_mix_logpdf([1.0], [[1.0, 0.0]], [np.diag([1.44, 0.64])])
    reg = half_space(0.4)
    reach = 12.0

    sigmas = {
        "unit":          (np.eye(2), True),
        "iso_0_81":      (0.81 * np.eye(2), True),
        "iso_1_21":      (1.21 * np.eye(2), True),
        "iso_2_25":      (2.25 * np.eye(2), True),
        "iso_4_00":      (4.00 * np.eye(2), True),
        "aniso":         (np.array([[0.81, 0.10], [0.10, 1.96]]), False),
        "aniso_rotish":  (np.array([[2.25, -0.18], [-0.18, 0.81]]), False),
    }
    for tag, (s, iso_flag) in sigmas.items():
        spec = MixtureSpec(np.array([1.0]),
                           np.array([[0.0, 0.0]]), (np.asarray(s), ))
        audit_matrix_gradient(f"s1_halfspace[{tag}]", lp, reg, spec, 0, reach)
        if iso_flag:
            audit_isotropic(f"s1_halfspace[{tag}]", lp, reg, spec, 0, reach)


def run_case_s2() -> None:
    # two-component proposals against two-component targets, both comps
    lp_t = gauss_mix_logpdf(
        [0.55, 0.45],
        [[-1.6, 0.2], [1.2, -0.6]],
        [np.diag([0.81, 0.36]), np.diag([0.49, 1.0])])
    cases = {
        "asym_pi_shifted_means": {
            "pi": [0.30, 0.70],
            "means": [[-1.2, 0.0], [1.4, -0.4]],
            "covs": [np.eye(2), 0.36 * np.eye(2)],
            "reach": 12.0,
        },
        "overlapping_equal": {
            "pi": [0.60, 0.40],
            "means": [[-0.4, 0.3], [0.5, -0.2]],
            "covs": [np.diag([0.64, 1.44]), np.array([[1.0, 0.12], [0.12, 0.49]])],
            "reach": 12.0,
        },
    }
    for tag, c in cases.items():
        spec = MixtureSpec(np.asarray(c["pi"], float),
                           np.asarray(c["means"], float),
                           tuple(np.asarray(x, float) for x in c["covs"]))
        for k in range(2):
            audit_matrix_gradient(f"s2_two_comp[{tag}]k{k}", lp_t,
                                  full_plane(), spec, k, c["reach"])


def run_case_s3_demo() -> dict:
    """Explanatory: narrow HDR-style start with heavy variance mass outside ->
    g < 0, preregistered widen step lowers M2."""
    # target: variance mass concentrated around radius ~ sqrt(1.8) ring-ish
    lp = gauss_mix_logpdf([0.5, 0.5],
                          [[-1.35, 0.0], [1.35, 0.0]],
                          [0.36 * np.eye(2), 0.36 * np.eye(2)])
    s2_start = 0.30                      # deliberately narrow component
    spec = MixtureSpec(np.array([1.0]), np.array([[0.0, 0.0]]),
                       (s2_start * np.eye(2),))
    reach = 10.0
    mom0 = variance_measure_moments(spec, 0, lp, full_plane(), reach=reach,
                                    n_per_axis=N_QUAD)
    delta_theta_main = float(CFG["step_policy_locked"]["delta_theta_main"])
    spec_w = with_component_covariance(
        spec, 0, s2_start * float(np.exp(delta_theta_main)) * np.eye(2))
    m2_w = m2_of_sigma(lp, full_plane(), spec, 0,
                       s2_start * float(np.exp(delta_theta_main)) * np.eye(2),
                       reach=reach, n_per_axis=N_QUAD)
    return {
        "case": "s3_narrow_hdr_explanatory",
        "s2_start": s2_start,
        "M2_start": float(mom0.M2),
        "g_isotropic_at_start": float(mom0.g_isotropic),
        "prediction": "WIDEN" if mom0.g_isotropic < 0 else ("SHRINK" if
                       mom0.g_isotropic > 0 else "HOLD"),
        "delta_theta_applied": delta_theta_main,
        "M2_after_step": float(m2_w),
        "M2_decreased": bool(m2_w < mom0.M2),
        "note": "HDR-covariance-narrow-but-gradient-widens narrative demo "
                "(task Sec. 20 S3); NOT a hard gate",
    }


def quadrature_qa(spec, target_logp, region_fn, reach) -> dict:
    a = variance_measure_moments(spec, 0, target_logp, region_fn, reach,
                                 n_per_axis=N_QUAD)
    b = variance_measure_moments(spec, 0, target_logp, region_fn, reach,
                                 n_per_axis=N_QUAD_REF)
    dev_M2 = abs(a.M2 - b.M2) / max(abs(b.M2), 1e-30)
    dev_grad = float(np.max(np.abs(a.grad_matrix - b.grad_matrix))) \
        / max(float(np.max(np.abs(b.grad_matrix))), 1e-30)
    return {"dev_M2_rel": float(dev_M2), "dev_grad_rel": float(dev_grad),
            "budget": 1e-8, "pass": bool(dev_M2 < 1e-8 and dev_grad < 1e-6)}


def main() -> int:
    print("== M3 theory proof obligation ==")
    run_case_identity()
    run_case_s1()
    run_case_s2()
    s3 = run_case_s3_demo()

    # quadrature self-convergence QA on one representative hard case
    lp_hard = gauss_mix_logpdf([1.0], [[1.0, 0.0]], [np.diag([1.44, 0.64])])
    spec_hard = MixtureSpec(np.array([1.0]), np.array([[0.0, 0.0]]),
                            (np.diag([0.25, 4.0]),))
    qa = quadrature_qa(spec_hard, lp_hard, half_space(0.4), 12.0)

    total = len(CHECKS)
    passed = sum(1 for c in CHECKS if c["pass"])
    sign_all = all(c["sign_agreement"] for c in CHECKS)
    max_rel = max((c["rel_err"] for c in CHECKS), default=0.0)
    gate_pass = (passed == total) and sign_all and max_rel <= REL_MAX \
        and AUDITS[0]["pass"] and qa["pass"]

    out = {
        "schema_version": "raretopo-m3-theory-checks-v0",
        "task_sha256": TASK_SHA,
        "benchmark_freeze_sha256": FREEZE_SHA,
        "git_commit": _git_head(),
        "locked": {"h": H, "rel_max": REL_MAX,
                   "n_quad": N_QUAD, "n_quad_ref": N_QUAD_REF},
        "checks": CHECKS,
        "audits": AUDITS,
        "s3_explanatory": s3,
        "quadrature_qa": qa,
        "summary": {
            "n_checks": total, "n_passed": passed,
            "sign_agreement_rate": (sum(c["sign_agreement"] for c in CHECKS)
                                    / total if total else 1.0),
            "max_relative_error": max_rel,
            "gate_M3_1": "PASS" if gate_pass else "FAIL",
        },
    }
    dest = REPO / "results" / "phase_m3" / "theory_checks" \
        / "theory_checks_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"checks: {passed}/{total} passed ; sign agreement "
          f"{out['summary']['sign_agreement_rate']:.0%} ; "
          f"max rel err {max_rel:.3e}")
    print(f"identity audit: M2-1={AUDITS[0]['M2_abs_dev_from_1']:.2e}, "
          f"|grad|max={AUDITS[0]['max_abs_grad_entry']:.2e}")
    print(f"S3 demo: prediction={s3['prediction']} "
          f"M2 {s3['M2_start']:.6f} -> {s3['M2_after_step']:.6f}")
    print(f"gate M3-1: {out['summary']['gate_M3_1']} -> {dest.relative_to(REPO)}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
