"""M3 -- analytical second-moment covariance gradient (candidate theorem,
task Sec. 4-7, 18) plus deterministic quadrature machinery for its
finite-difference proof obligation (Sec. 19).

Population-level ONLY: every function here takes explicit mixture parameters
(weights / means / covariances) and returns exact quantities computed by
tensor-product Gauss-Legendre quadrature of

    M2(q)  = int_A p(x)^2 / q(x) dx,
    nu_V   = 1_A p^2/q / M2,

    grad_{Sigma_k} M2 = (M2/2) Sigma^-1 [ E[r_k] Sigma - E[r_k delta delta'] ] Sigma^-1
    g(theta)          = (M2/2) E[r_k] (dim - D_k / s_k^2)

(task Sec. 5 boxed formulas; derivation docs/phase_m3/
M3_Covariance_Gradient_Derivation.md).  Finite-sample estimators on real
pilots belong to ``gradient_estimator``; the split keeps the theorem verifiable
at quadrature accuracy BEFORE any estimator noise can mask a wrong sign.

FIREWALL: no benchmark-design reference data enters this module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# --------------------------------------------------------------------------- #
# mixture primitives (general per-component covariance Gaussian mixtures)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MixtureSpec:
    """Immutable explicit-parameter Gaussian mixture ``sum_j pi_j N(m_j, S_j)``."""

    pi: np.ndarray            # (K,) positive, sums to 1
    means: np.ndarray         # (K, d)
    covs: tuple[np.ndarray, ...]   # K matrices (d, d)

    def __post_init__(self) -> None:
        pi = np.asarray(self.pi, dtype=float)
        means = np.asarray(self.means, dtype=float)
        if pi.ndim != 1 or means.ndim != 2 or pi.size != means.shape[0]:
            raise ValueError("pi / means shape mismatch")
        if np.any(pi < 0) or not np.isclose(pi.sum(), 1.0, atol=1e-9):
            raise ValueError("pi must be non-negative and sum to 1")
        if len(self.covs) != pi.size:
            raise ValueError("covs / pi length mismatch")
        object.__setattr__(self, "pi", pi)
        object.__setattr__(self, "means", means)

    @property
    def dim(self) -> int:
        return int(self.means.shape[1])

    @property
    def n_components(self) -> int:
        return int(self.pi.size)


def with_component_covariance(spec: MixtureSpec, k: int,
                              sigma_new: np.ndarray) -> MixtureSpec:
    """Return the mixture with ONLY component ``k``'s covariance replaced."""
    covs = list(spec.covs)
    covs[k] = np.asarray(sigma_new, dtype=float)
    return MixtureSpec(spec.pi.copy(), spec.means.copy(),
                       tuple(np.asarray(c, dtype=float) for c in covs))


def mixture_log_density(spec: MixtureSpec, z: np.ndarray) -> np.ndarray:
    """Stable ``log q(z)`` via log-sum-exp over components."""
    z = np.asarray(z, dtype=float)
    blocks = []
    for j in range(spec.n_components):
        s = spec.covs[j]
        sign, logdet = np.linalg.slogdet(s)
        if sign <= 0:
            raise ValueError(f"component {j} covariance not SPD")
        inv = np.linalg.inv(s)
        diff = z - spec.means[j][None, :]
        quad = np.einsum("ni,ij,nj->n", diff, inv, diff)
        blocks.append(-0.5 * (z.shape[1] * np.log(2.0 * np.pi) + logdet)
                      - 0.5 * quad + np.log(spec.pi[j]))
    stack = np.stack(blocks, axis=1)
    m = stack.max(axis=1)
    return m + np.log(np.exp(stack - m[:, None]).sum(axis=1))


def component_responsibility(spec: MixtureSpec, z: np.ndarray,
                             k: int) -> np.ndarray:
    """``r_k(z) = pi_k q_k(z) / q(z)`` (task Sec. 4 identity)."""
    sig = spec.covs[k]
    diff = z - spec.means[k][None, :]
    inv = np.linalg.inv(sig)
    quad = np.einsum("ni,ij,nj->n", diff, inv, diff)
    _, logdet = np.linalg.slogdet(sig)
    log_qk = (-0.5 * (z.shape[1] * np.log(2.0 * np.pi) + logdet) - 0.5 * quad
              + np.log(spec.pi[k]))
    return np.exp(log_qk - mixture_log_density(spec, z))


# --------------------------------------------------------------------------- #
# Gauss-Legendre quadrature of the variance-measure moments
# --------------------------------------------------------------------------- #

_GL_REF_CACHE: dict[tuple[float, int], tuple[np.ndarray, np.ndarray]] = {}


def _gl_nodes_weights(center: np.ndarray, reach: float, n_per_axis: int) \
        -> tuple[np.ndarray, np.ndarray]:
    """Tensor-product Gauss-Legendre grid on ``prod[center_j +- reach_j]``.

    Cached per (center-hash-ish, n) because the driver reuses the same box for
    every finite-difference probe of one case.
    """
    key = (float(reach), int(n_per_axis))
    if key in _GL_REF_CACHE:
        ref_x, ref_w = _GL_REF_CACHE[key]
    else:
        ref_x, ref_w = np.polynomial.legendre.leggauss(int(n_per_axis))
        _GL_REF_CACHE[key] = (ref_x, ref_w)
    lo = center - reach
    hi = center + reach
    axes = [lo[j] + (hi[j] - lo[j]) * 0.5 * (ref_x + 1.0)
            for j in range(center.size)]
    ws = [0.5 * (hi[j] - lo[j]) * ref_w for j in range(center.size)]
    grid_x = np.stack([g.ravel() for g in np.meshgrid(*axes, indexing="ij")],
                      axis=1)
    grid_w = np.prod(np.stack([w.ravel() for w in
                               np.meshgrid(*ws, indexing="ij")], axis=1),
                     axis=1)
    return grid_x, grid_w


@dataclass(frozen=True)
class VarianceMomentResult:
    """Exact-quadrature moments defining the candidate theorem (task Sec. 5-7)."""

    M2: float                    # second moment of the mixture on A
    mu_r: float                  # E_nuV[r_k]
    scatter_rd: float            # E_nuV[r_k delta delta']  (matrix)
    T_k: np.ndarray              # scatter_rd / mu_r   (stationary target)
    grad_matrix: np.ndarray      # (4) boxed matrix gradient
    g_isotropic: float           # (5) at the CURRENT isotropic slice of comp k
    region_mass_integral: float  # raw quadrature mass of 1_A p^2/q (== M2)
    quadrature_points: np.ndarray
    quadrature_nu_v: np.ndarray  # normalized discrete nu_V values


def variance_measure_moments(
    spec: MixtureSpec,
    k: int,
    logp_fn,
    region_fn,
    reach: float,
    n_per_axis: int = 320,
    box_center: np.ndarray | None = None,
) -> VarianceMomentResult:
    """Quadrature-exact ``nu_V`` moments + candidate-theorem outputs.

    ``logp_fn(z)`` vectorized target log-density; ``region_fn(z)`` boolean mask
    of the frozen event region ``A`` (e.g. half-space or full box).  The box is
    ``box_center +- reach`` per axis (component-wise scalar ``reach``).
    """
    spec_dim = spec.dim
    center = (np.zeros(spec_dim) if box_center is None
              else np.asarray(box_center, dtype=float))
    pts, ws = _gl_nodes_weights(center, float(reach), int(n_per_axis))

    logq = mixture_log_density(spec, pts)
    logp = np.asarray(logp_fn(pts), dtype=float).reshape(-1)
    mask = np.asarray(region_fn(pts), dtype=bool)

    integrand = np.where(mask, 2.0 * logp - logq, -np.inf)
    m = float(integrand.max())
    if not np.isfinite(m):
        raise ValueError("region A carries zero p^2/q quadrature mass")
    f = np.exp(integrand - m)
    m2_raw = float(np.exp(m) * np.sum(f * ws))       # int_A p^2/q dx

    nu_v = f * ws
    nu_v /= nu_v.sum()                                # discrete approx of nu_V

    r = component_responsibility(spec, pts, k)
    mu_r = float(np.sum(nu_v * r))
    diff = pts - spec.means[k][None, :]
    rd = np.einsum("n,ni,nj->ij", nu_v * r, diff, diff)

    sigma = np.asarray(spec.covs[k], dtype=float)
    inv = np.linalg.inv(sigma)
    grad = 0.5 * m2_raw * (inv @ (mu_r * sigma - rd) @ inv)

    s2 = float(np.trace(sigma) / sigma.shape[0])
    dim = sigma.shape[0]
    D_k = float(np.trace(rd) / mu_r) if mu_r > 0.0 else float("nan")
    g_iso = 0.5 * m2_raw * mu_r * (dim - D_k / s2)

    return VarianceMomentResult(
        M2=m2_raw, mu_r=mu_r, scatter_rd=rd, T_k=rd / mu_r,
        grad_matrix=grad, g_isotropic=g_iso,
        region_mass_integral=m2_raw,
        quadrature_points=pts, quadrature_nu_v=nu_v,
    )


# --------------------------------------------------------------------------- #
# finite-difference proof-obligation helpers (task Sec. 19)
# --------------------------------------------------------------------------- #


def m2_of_sigma(target_logp, region_fn, base: MixtureSpec, k: int,
                sigma_new: np.ndarray, reach: float,
                n_per_axis: int = 320) -> float:
    """Quadrature ``M2`` of the mixture whose component ``k`` got ``sigma_new``."""
    spec = with_component_covariance(base, k, sigma_new)
    res = variance_measure_moments(spec, k, target_logp, region_fn, reach,
                                   n_per_axis=n_per_axis)
    return res.M2


def directional_finite_difference(
    target_logp, region_fn, base: MixtureSpec, k: int,
    sigma_0: np.ndarray, direction: np.ndarray, h: float,
    reach: float, n_per_axis: int = 320,
) -> float:
    """Central difference ``[M2(S0 + hE) - M2(S0 - hE)] / 2h`` on one symmetric
    direction ``E`` (valid while both probes stay SPD)."""
    sigma_0 = np.asarray(sigma_0, dtype=float)
    d = np.asarray(direction, dtype=float)
    up = m2_of_sigma(target_logp, region_fn, base, k, sigma_0 + h * d,
                     reach, n_per_axis)
    dn = m2_of_sigma(target_logp, region_fn, base, k, sigma_0 - h * d,
                     reach, n_per_axis)
    return (up - dn) / (2.0 * float(h))


def safe_relative_error(analytic: float, fd: float,
                        floor_scale: float = 1e-30) -> float:
    """Relative error guarded against vanishing denominators."""
    denom = max(abs(analytic), floor_scale)
    return float(abs(fd - analytic) / denom)


__all__ = [
    "MixtureSpec", "with_component_covariance", "mixture_log_density",
    "component_responsibility", "VarianceMomentResult",
    "variance_measure_moments", "m2_of_sigma",
    "directional_finite_difference", "safe_relative_error",
]
