"""M2 -- covariance candidate policy, locked selection/mean stage and the
two-layer paired trial machinery (task Sec. 7-24, 37).

FIREWALL mirrors ``hyptraj.m1d.adaptation``: nothing here receives
benchmark-design reference tables or any offline freeze artifact; topology
labels come only from the frozen oracle label function and every sampling
density used in estimators is recorded at draw time.  Selection is computed
EXACTLY ONCE per (config, seed) -- C0..C4 cannot re-select or re-compute a
different centroid structurally: they consume the same frozen
:class:`SharedStage`.

Layer semantics (task Sec. 21):

- Layer A "shape_only"    : pi = pi_C0 (frozen M1-D update weights) for ALL
  variants -> isolated covariance effect.
- Layer B "shape_reweight": each variant refits mixture weights with the SAME
  frozen SLSQP optimizer core (``optimize_mixture_weights`` -- unmodified;
  only the component-density provider is extended to general Gaussian
  covariances, which IS the M2 controlled variable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from hyptraj.m1.mixture_weights import optimize_mixture_weights
from hyptraj.m1.proposal_update import (
    LEGALITY_MIN_EIG,
    MixtureProposal,
    add_component,
    eta_region_centroid,
    update_weights,
)
from hyptraj.m1d.adaptation import (
    draw_mix_pilot,
    eligible_candidates,
    selector_pick,
)
from hyptraj.m1d.metrics import NOMINAL, eval_proposal_is
from hyptraj.m2.covariance_projection import (
    ProjectionResult,
    base_covariance_from_frozen_metadata,
    project_covariance,
)
from hyptraj.m2.variance_covariance import (
    ESS_V_MIN,
    VarianceRegionStats,
    diagonal_covariance,
    estimate_variance_region,
    isotropic_scale_covariance,
    shrunk_full_covariance,
)

COV_METHODS = ("C0", "C1", "C2", "C3", "C4")
LAMBDA_MAIN = 0.50


# ---------------------------------------------------------------------------
# general-covariance Gaussian mixture proposal (M2-controlled extension)
# ---------------------------------------------------------------------------
def component_log_densities_cov(z: np.ndarray, centers: np.ndarray,
                                covs: tuple[np.ndarray, ...]) -> np.ndarray:
    """``(N, K)`` matrix ``log q_j(z_i)`` with per-component covariance."""
    z = np.asarray(z, dtype=float)
    K = len(covs)
    out = np.empty((z.shape[0], K))
    consts = np.empty(K)
    invs = []
    for j, cov in enumerate(covs):
        cov = np.asarray(cov, dtype=float)
        sign, logdet = np.linalg.slogdet(cov)
        if sign <= 0:
            raise ValueError(f"component {j} covariance not SPD")
        inv = np.linalg.inv(cov)
        diff = z - centers[j][None, :]
        quad = np.einsum("ni,ij,nj->n", diff, inv, diff)
        consts[j] = -0.5 * (z.shape[1] * np.log(2.0 * np.pi) + logdet)
        out[:, j] = consts[j] - 0.5 * quad
        invs.append(inv)
    return out


@dataclass(frozen=True)
class CovGaussianMixtureProposal:
    """Gaussian mixture with PER-COMPONENT covariance ``N(m_j, Sigma_j)``.

    Mirrors the frozen ``MixtureProposal`` API (``sample`` / ``log_density`` /
    legality metadata) so the FROZEN evaluator ``eval_proposal_is`` runs
    unchanged.  The RNG call sequence of :meth:`sample` matches the frozen
    implementation (one ``choice`` then one ``standard_normal`` block), which
    makes unit-covariance instances share common random numbers with the
    frozen family.
    """

    centers: np.ndarray
    weights: np.ndarray
    covs: tuple[np.ndarray, ...]
    component_mode_ids: tuple[str, ...] = ()
    legality_checked: bool = True
    min_eig_sigma_minus_halfI: float = LEGALITY_MIN_EIG   # re-recorded below

    def __post_init__(self) -> None:
        centers = np.asarray(self.centers, dtype=float)
        w = np.asarray(self.weights, dtype=float)
        if centers.ndim != 2 or w.ndim != 1 or centers.shape[0] != w.size:
            raise ValueError("centers / weights shape mismatch")
        if len(self.covs) != centers.shape[0]:
            raise ValueError("covs / centers component count mismatch")
        if np.any(w < 0) or not np.isclose(w.sum(), 1.0, atol=1e-9):
            raise ValueError("weights must be non-negative and sum to 1")
        object.__setattr__(self, "centers", centers)
        object.__setattr__(self, "weights", w)

    @property
    def n_components(self) -> int:
        return self.centers.shape[0]

    @property
    def chols(self) -> tuple[np.ndarray, ...]:
        return tuple(np.linalg.cholesky(np.asarray(c, dtype=float))
                     for c in self.covs)

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        comp = rng.choice(self.n_components, size=n, p=self.weights)
        d = self.centers.shape[1]
        eps = rng.standard_normal((n, d))
        chols = self.chols
        transformed = np.einsum("njk,nk->nj",
                                np.stack([chols[c] for c in comp]), eps)
        return self.centers[comp] + transformed

    def log_density(self, z: np.ndarray) -> np.ndarray:
        from hyptraj.m1.mixture_weights import mixture_log_density
        logq_ji = component_log_densities_cov(z, self.centers, self.covs)
        return mixture_log_density(logq_ji, self.weights)


def proposal_from_frozen(base: MixtureProposal, dim: int) \
        -> CovGaussianMixtureProposal:
    """Convert a frozen unit-covariance ``MixtureProposal`` (metadata-checked).

    Reads ``Sigma_base`` through the frozen metadata discipline (task Sec. 13)
    and attaches it to every existing component; the returned instance's own
    metadata re-records the frozen values.
    """
    sigma_base, meta_checks = base_covariance_from_frozen_metadata(
        base.min_eig_sigma_minus_halfI, base.legality_checked, dim)
    del meta_checks
    return CovGaussianMixtureProposal(
        centers=base.centers.copy(),
        weights=base.weights.copy(),
        covs=tuple(sigma_base.copy() for _ in range(base.n_components)),
        component_mode_ids=tuple(base.component_mode_ids),
        legality_checked=bool(base.legality_checked),
        min_eig_sigma_minus_halfI=float(base.min_eig_sigma_minus_halfI),
    )


def add_component_cov(prop: CovGaussianMixtureProposal, center: np.ndarray,
                      sigma_new: np.ndarray, mode_id: str,
                      pi_fallback: float = 0.5) -> CovGaussianMixtureProposal:
    """ADD_COMPONENT with covariance ``sigma_new`` on the newborn component.

    Weight initialization preserves old relative ratios EXACTLY like the
    frozen ``add_component`` (joint ``(1-a)`` scaling + ``a`` on the newborn).
    """
    centers = np.vstack([prop.centers,
                         np.asarray(center, dtype=float).reshape(1, -1)])
    w = (1.0 - pi_fallback) * prop.weights
    w = np.append(w, pi_fallback)
    # recorded legality discipline: min_eig(Sigma_j - I/2) per component
    min_eig_new = float(np.linalg.eigvalsh(
        symmetrize_min(np.asarray(sigma_new, dtype=float)))[0])
    return CovGaussianMixtureProposal(
        centers=centers, weights=w,
        covs=tuple(prop.covs) + (np.asarray(sigma_new, dtype=float).copy(),),
        component_mode_ids=prop.component_mode_ids + (mode_id,),
        legality_checked=True,
        min_eig_sigma_minus_halfI=float(min(
            prop.min_eig_sigma_minus_halfI,
            min_eig_new - LEGALITY_MIN_EIG)),
    )


def symmetrize_min(mat: np.ndarray) -> np.ndarray:
    m = np.asarray(mat, dtype=float)
    return 0.5 * (m + m.T)


# ---------------------------------------------------------------------------
# covariance candidates C0-C4 (task Sec. 14)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CandidateSpec:
    method: str                            # 'C0'..'C4'
    sigma_pre_raw: np.ndarray              # pre-projection candidate matrix
    projection: ProjectionResult           # symmetrize+clip+frozen legality
    held: bool                             # HOLD_BASE_COVARIANCE fired?
    hold_reason: str
    lambda_used: float                     # shrinkage actually applied (C4)

    @property
    def sigma_final(self) -> np.ndarray:
        """Matrix actually handed to the policy after HOLD/projection."""
        if self.held:
            if self.sigma_base is None:
                raise RuntimeError("HOLD candidate missing Sigma_base")
            return np.array(self.sigma_base, dtype=float, copy=True)
        return self.projection.sigma_final

    sigma_base: np.ndarray | None = None   # populated post-construction


def build_candidates(region: VarianceRegionStats, sigma_base: np.ndarray,
                     lambda_main: float = LAMBDA_MAIN) -> dict[str, CandidateSpec]:
    """Construct C0-C4 specs from one variance region (task Sec. 12-16).

    HOLD rule (task Sec. 12): when the preregistered finite-sample
    requirements fail (``n_region < d+2``, ``ESS_V_region < 20`` or any
    non-finite estimator), C1-C4 collapse to ``Sigma_base`` -- recorded as a
    legitimate finite-sample HOLD action, NOT a failed trial.  C0 is defined
    as ``Sigma_base`` and is unaffected by construction.
    """
    hold, reason = region.hold_required
    pre: dict[str, np.ndarray] = {
        "C0": np.asarray(sigma_base, dtype=float).copy(),
        "C1": isotropic_scale_covariance(region.cov),
        "C2": diagonal_covariance(region.cov),
        "C3": np.asarray(region.cov, dtype=float).copy(),
        "C4": shrunk_full_covariance(region.cov, sigma_base, float(lambda_main)),
    }
    out: dict[str, CandidateSpec] = {}
    for name in COV_METHODS:
        proj = project_covariance(pre[name])
        # an invalid raw input must be surfaced, never silently mapped to base
        if not proj.valid_input:
            hold_invalid = True
            invalid_reason = ";".join(proj.validity_reasons)
            proj_base = project_covariance(pre["C0"])
            out[name] = CandidateSpec(
                method=name, sigma_pre_raw=pre[name],
                projection=proj_base, held=True,
                hold_reason=f"invalid_input({invalid_reason})",
                lambda_used=lambda_main if name == "C4" else float("nan"),
            )
            continue
        spec_hold = hold if name != "C0" else False
        spec_reason = reason if name != "C0" else ""
        out[name] = CandidateSpec(
            method=name, sigma_pre_raw=pre[name], projection=proj,
            held=bool(spec_hold), hold_reason=str(spec_reason),
            lambda_used=float(lambda_main) if name == "C4" else float("nan"),
        )
    for spec in out.values():                      # attach base for held path
        object.__setattr__(spec, "sigma_base", np.asarray(sigma_base).copy())
    return out


# ---------------------------------------------------------------------------
# locked shared stage (task Sec. 18-20)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SharedStage:
    """One (config, seed): pilot + selection lock + mean lock + C_eta."""

    bench_cfg: object
    seed: int
    z: np.ndarray
    logr: np.ndarray
    source_strata: np.ndarray
    logp: np.ndarray
    labels: np.ndarray
    q0_frozen: MixtureProposal
    q0_cov: CovGaussianMixtureProposal
    eligible: list[str]
    selected_mode: str | None
    P_hat_table: dict
    L_hat_table: dict
    region: VarianceRegionStats | None
    centroid_frozen_check: float          # max abs dev vs frozen centroid fn
    sigma_base: np.ndarray
    pi_c0: np.ndarray                     # frozen SLSQP weights (unit family)
    c0_build_details: dict
    stop_reason: str | None               # None when stage completed legally
    controls: dict = field(default_factory=dict)

    @property
    def pilot_n(self) -> int:
        return int(self.controls["n_pilot"])


def run_shared_stage(bench_cfg, seed: int, *, n_pilot: int = 20_000,
                     alpha: float = 0.5, eta: float = 0.8,
                     n_eval: int = 100_000) -> SharedStage:
    """Locked selection + mean + covariance-estimation stage.

    Replicates the frozen M1-D selection pathway bit-for-bit
    (``rng=[seed,101]`` mixed pilot -> Sec. 16 gate -> argmax ``L_hat``), so
    the selected mode is checkable against archived M1-D
    ``variance_selector`` runs offline.  After the lock, the mean is computed
    by the frozen ``eta_region_centroid`` AND independently verified against
    the region statistics (dual computation equality).  Then the frozen C0
    update (add_component + SLSQP ``update_weights``) produces ``pi_C0``.

    Cost accounting: exactly one pilot of ``n_pilot`` samples; the covariance
    machinery adds ZERO simulator calls (task Sec. 23).
    """
    logp_fn: Callable = bench_cfg.logp
    nominal = NOMINAL
    q0 = bench_cfg.initial_proposal()

    # ---- ONE shared pilot -------------------------------------------------
    rng_pilot = np.random.default_rng([int(seed), 101])
    z, logr, strata = draw_mix_pilot(rng_pilot, q0, logp_fn, int(n_pilot),
                                     alpha)
    logp = np.asarray(logp_fn(z), dtype=float)
    labels = bench_cfg.label(z)

    indicators = (labels != nominal).astype(float)

    # ---- SELECTION LOCK (computed exactly once; task Sec. 19) -------------
    cands = eligible_candidates(labels, nominal, set(q0.component_mode_ids))
    pick, diag = selector_pick("variance", cands, labels, z, q0.centers,
                               q0.weights, logp, logr)
    if pick is None:
        empty_pi = q0.weights.copy()
        return SharedStage(
            bench_cfg=bench_cfg, seed=int(seed), z=z, logr=logr,
            source_strata=strata, logp=logp, labels=labels, q0_frozen=q0,
            q0_cov=proposal_from_frozen(q0, z.shape[1]), eligible=cands,
            selected_mode=None, P_hat_table=diag.get("P_hat_table", {}),
            L_hat_table=diag.get("L_hat_table", {}), region=None,
            centroid_frozen_check=float("nan"), sigma_base=np.eye(z.shape[1]),
            pi_c0=empty_pi, c0_build_details={},
            stop_reason="no_eligible_candidate",
            controls={"n_pilot": int(n_pilot), "alpha": float(alpha),
                      "eta": float(eta), "n_eval": int(n_eval)},
        )

    # ---- region + MEAN LOCK ----------------------------------------------
    region = estimate_variance_region(z, q0.centers, q0.weights, logp, logr,
                                      labels, nominal, str(pick), eta=eta)
    cen_frozen, eta_used = eta_region_centroid(
        z, logp, logr, q0.weights, q0.centers, labels, nominal,
        mode=str(pick), eta=eta)
    frozen_dev = float(np.max(np.abs(cen_frozen - region.centroid)))
    if frozen_dev > 1e-10:
        raise RuntimeError("mean-lock violated: M2 region centroid differs "
                           "from frozen eta_region_centroid")

    # ---- frozen base covariance read-out (task Sec. 13) -------------------
    sigma_base, _meta = base_covariance_from_frozen_metadata(
        q0.min_eig_sigma_minus_halfI, q0.legality_checked, z.shape[1])

    # ---- frozen C0 update on the UNIT family (add + SLSQP) ---------------
    prop_c0_unit = add_component(q0, region.centroid, mode_id=str(pick))
    prop_c0_unit, res_w = update_weights(prop_c0_unit, z, logp, logr,
                                         indicators)
    details = {
        "solver": "frozen SLSQP (M1)", "success": bool(res_w.success),
        "message": str(res_w.message), "kkt_residue": float(res_w.kkt_residue),
        "weights": [float(v) for v in res_w.weights],
        "center_rule": "variance_hdr", "eta_used_by_frozen_action":
            float(eta_used),
    }

    return SharedStage(
        bench_cfg=bench_cfg, seed=int(seed), z=z, logr=logr,
        source_strata=strata, logp=logp, labels=labels, q0_frozen=q0,
        q0_cov=proposal_from_frozen(q0, z.shape[1]), eligible=cands,
        selected_mode=str(pick),
        P_hat_table={k: float(v) for k, v in diag.get("P_hat_table",
                                                      {}).items()},
        L_hat_table={k: float(v) for k, v in diag.get("L_hat_table",
                                                      {}).items()},
        region=region, centroid_frozen_check=frozen_dev,
        sigma_base=sigma_base, pi_c0=prop_c0_unit.weights.copy(),
        c0_build_details=details, stop_reason=None,
        controls={"n_pilot": int(n_pilot), "alpha": float(alpha),
                  "eta": float(eta), "n_eval": int(n_eval)},
    )


# ---------------------------------------------------------------------------
# two-layer variant construction (task Sec. 18-21)
# ---------------------------------------------------------------------------
LAYER_A = "shape_only"
LAYER_B = "shape_reweight"


def build_variant_proposal(stage: SharedStage, cand: CandidateSpec,
                           layer: str) -> CovGaussianMixtureProposal:
    """Assemble one (candidate, layer) proposal.  Zero simulator calls.

    Layer A: copy ``pi_C0`` onto the covariance-augmented family.
    Layer B: refit weights with the FROZEN SLSQP core on the declared pilot
    fit data (same pilot as selection; task Sec. 22 declares the fit set),
    starting from the identical add_component split init the frozen update
    uses.
    """
    if stage.selected_mode is None or stage.region is None:
        raise RuntimeError("shared stage did not complete selection lock")
    if layer not in (LAYER_A, LAYER_B):
        raise ValueError(layer)
    sigma_new = cand.sigma_final
    if not np.all(np.isfinite(sigma_new)):
        raise RuntimeError("non-finite final covariance leaked into policy")
    prop = add_component_cov(stage.q0_cov, stage.region.centroid,
                             sigma_new, mode_id=str(stage.selected_mode))

    indicators = (stage.labels != NOMINAL).astype(float)
    if layer == LAYER_A:
        weights = stage.pi_c0.copy()
        solver_info = {"solver": "layer_A_passthrough_pi_C0"}
    else:
        logq_ji = component_log_densities_cov(stage.z, prop.centers, prop.covs)
        res = optimize_mixture_weights(logq_ji, stage.logp, stage.logr,
                                       indicators, pi0=prop.weights,
                                       floor=0.0, maxiter=500)
        if not res.success:
            raise RuntimeError(f"Layer B weight refit failed: {res.message}")
        weights = res.weights
        solver_info = {"solver": "frozen SLSQP (M1)",
                       "message": str(res.message),
                       "kkt_residue": float(res.kkt_residue)}
    return CovGaussianMixtureProposal(
        centers=prop.centers, weights=weights, covs=prop.covs,
        component_mode_ids=prop.component_mode_ids,
        legality_checked=True, min_eig_sigma_minus_halfI=
        float(min(prop.min_eig_sigma_minus_halfI,
                  float(np.linalg.eigvalsh(symmetrize_min(sigma_new))[0]))),
    ), solver_info


def evaluate_variant(stage: SharedStage, prop: CovGaussianMixtureProposal,
                     n_eval: int) -> dict:
    """Frozen independent IS evaluation (task Sec. 23 budget semantics).

    Delegates verbatim to ``hyptraj.m1d.metrics.eval_proposal_is`` (rng tag
    900001); VRF attachment stays with the DRIVER (reference denominators are
    benchmark-design data, firewall Sec. 41 of M1-D inherited).
    """
    ev = eval_proposal_is(prop, stage.bench_cfg, int(stage.seed),
                          n_eval=int(n_eval))
    return ev


__all__ = [
    "COV_METHODS", "LAMBDA_MAIN", "SharedStage", "CandidateSpec",
    "run_shared_stage", "build_candidates", "build_variant_proposal",
    "evaluate_variant", "proposal_from_frozen", "add_component_cov",
    "component_log_densities_cov", "CovGaussianMixtureProposal",
    "LAYER_A", "LAYER_B", "ESS_V_MIN",
]
