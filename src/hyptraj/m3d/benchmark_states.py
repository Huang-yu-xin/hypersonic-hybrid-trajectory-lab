"""M3-D benchmark states -- proposal-state construction and legality
pre-freeze enumeration (task Sec. 4-6, 11).

A benchmark STATE freezes one (config, s2) cell:

    frozen event/topology config
  + frozen mixture means (= eta-region centroid of the locked shared stage)
  + frozen mixture weights (= frozen SLSQP pi_C0 of that stage)
  + selected controlled component (frozen M1-D variance-selector choice)
  + candidate scalar covariance Sigma_k = s^2 I on that component only

MIXTURE ASSEMBLY ANCHOR (preregistered before any characterization data):
each config's means/weights/selected mode are assembled ONCE from the frozen
shared-stage pathway ``run_shared_stage`` at ANCHOR SEED 2026 (the first seed
of the locked seed set) and never vary across the s2 grid or the online seed
set.  Online trials then differ ONLY through estimator noise on the pilot.
The s2 = 1.00 state therefore reproduces the original M3-v0 gradient point
exactly (unit-family covariance), which is what the Sec. 31 replay control
compares against.

Legality: every candidate passes/fails the FROZEN checker before any
reference data exists; an illegal candidate is recorded ILLEGAL_PRE_FREEZE
and is NEVER replaced post hoc (task Sec. 6).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hyptraj.m1d.experiments import config_from_record, load_freeze
from hyptraj.m2.covariance_policy import (
    CovGaussianMixtureProposal,
    add_component_cov,
    run_shared_stage,
)
from hyptraj.m2.covariance_projection import check_legality_frozen

REPO = Path(__file__).resolve().parents[3]   # src/hyptraj/m3d -> repo root

ANCHOR_SEED = 2026          # deterministic mixture-assembly anchor (locked)
ETA_FROZEN = 0.8            # frozen selector bandwidth (identical to M3-v0)
PILOT_N_STAGE = 20_000      # shared-stage pilot size (same constant online)


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class BenchmarkState:
    """One frozen (config, s2) proposal-state cell."""

    config_id: str
    state_id: str
    s2: float
    selected_mode: str
    component_index: int
    component_mean: np.ndarray
    centers: np.ndarray              # full mixture centers incl. newborn
    weights_pi_c0: np.ndarray        # frozen SLSQP output (sums to 1)
    covs_other: tuple                # covariances of non-selected comps
    legality_passed: bool
    min_eig_selected: float
    bench_cfg: object

    @property
    def dim(self) -> int:
        return int(self.centers.shape[1])

    def proposal(self) -> CovGaussianMixtureProposal:
        """Full mixture proposal with Sigma_k = s^2 I on the newborn comp."""
        covs = list(self.covs_other)
        covs.insert(self.component_index, self.s2 * np.eye(self.dim))
        sig_new = self.s2 * np.eye(self.dim)
        base_meta = min(
            float(np.linalg.eigvalsh(0.5 * (c + c.T))[0]) - 0.5
            for j, c in enumerate(covs) if j != self.component_index)
        return CovGaussianMixtureProposal(
            centers=self.centers.copy(),
            weights=self.weights_pi_c0.copy(),
            covs=tuple(np.asarray(c, dtype=float) for c in covs),
            component_mode_ids=(
                self.bench_cfg.initial_proposal().component_mode_ids
                + (str(self.selected_mode), )),
            legality_checked=True,
            min_eig_sigma_minus_halfI=min(base_meta, float(
                np.linalg.eigvalsh(0.5 * (sig_new + sig_new.T))[0] - 0.5)),
        )

    def fingerprint(self) -> dict:
        return {
            "config_id": self.config_id,
            "state_id": self.state_id,
            "s2": self.s2,
            "selected_mode": str(self.selected_mode),
            "component_index": int(self.component_index),
            "component_mean": [float(x) for x in self.component_mean],
            "centers": [[float(x) for x in row] for row in self.centers],
            "weights_pi_c0": [float(x) for x in self.weights_pi_c0],
            "covs_selected_s2I": [float(self.s2)] * self.dim,
            "legality_passed": bool(self.legality_passed),
            "min_eig_selected": float(self.min_eig_selected),
            "assembly_anchor_seed": int(ANCHOR_SEED),
        }


def _load_grid() -> dict:
    return json.loads((REPO / "configs" / "phase_m3d"
                       / "m3d_candidate_state_grid.json").read_text(
                           encoding="utf-8"))


_STAGE_CACHE: dict[str, object] = {}


def _anchored_stage(bc):
    """Shared-stage assembly for one config, cached at the anchor seed."""
    key = str(getattr(bc, "config_id", id(bc)))
    if key not in _STAGE_CACHE:
        _STAGE_CACHE[key] = run_shared_stage(bc, ANCHOR_SEED,
                                             n_pilot=PILOT_N_STAGE,
                                             alpha=0.5, eta=ETA_FROZEN,
                                             n_eval=1)
    return _STAGE_CACHE[key]


def assemble_state(bc, s2: float, *, short_config: str | None = None) \
        -> BenchmarkState | dict:
    """Assemble one candidate state or return ILLEGAL_PRE_FREEZE marker."""
    stage = _anchored_stage(bc)
    if stage.stop_reason is not None or stage.selected_mode is None \
            or stage.region is None:
        return {"status": "ASSEMBLY_STOP", "stop_reason":
                str(stage.stop_reason)}
    dim = int(stage.z.shape[1])
    q0_cov = stage.q0_cov
    newborn_center = np.asarray(stage.region.centroid, dtype=float)

    # provisional full-mixture assembly mirrors M3-v0 _scaled_proposal shape;
    # weights come from the FROZEN SLSQP output (Layer A lock), replacing the
    # add_component fallback ratio like the M3 driver does.
    prov = add_component_cov(q0_cov, newborn_center, s2 * np.eye(dim),
                             mode_id=str(stage.selected_mode))
    k_idx = prov.n_components - 1

    ok_leg, min_eig = check_legality_frozen(s2 * np.eye(dim))
    if short_config is None:
        short_config = bc.config_id.split("_")[-1] \
            if hasattr(bc, "config_id") else "cfg"
    state_id = f"{short_config}_s2_{int(round(s2 * 100)):05d}"

    if not ok_leg:
        return {"status": "ILLEGAL_PRE_FREEZE", "config_id": bc.config_id,
                "state_id": state_id, "s2": float(s2),
                "min_eig_selected": float(min_eig)}

    centers = np.asarray(prov.centers, dtype=float)
    other = tuple(np.asarray(prov.covs[j], dtype=float)
                  for j in range(prov.n_components) if j != k_idx)
    return BenchmarkState(
        config_id=getattr(bc, "config_id", short_config),
        state_id=state_id,
        s2=float(s2),
        selected_mode=str(stage.selected_mode),
        component_index=int(k_idx),
        component_mean=newborn_center.copy(),
        centers=centers,
        weights_pi_c0=np.asarray(stage.pi_c0, dtype=float).copy(),
        covs_other=other,
        legality_passed=True,
        min_eig_selected=float(min_eig),
        bench_cfg=bc,
    )


def state_arms(st: BenchmarkState, delta_theta: float = 0.20) \
        -> dict[str, CovGaussianMixtureProposal]:
    """BASE / WIDEN / SHRINK arm proposals of a state (selected comp only).

    CRN-ready: identical centers, weights, component order; only comp
    ``component_index``'s Cholesky differs, so one shared generator stream
    yields paired draws across arms (frozen family contract)."""
    base = st.proposal()
    out = {}
    for name, shift in (("base", 0.0), ("widen", +delta_theta),
                        ("shrink", -delta_theta)):
        covs = list(base.covs)
        covs[st.component_index] = (st.s2 * float(np.exp(shift))) \
            * np.eye(st.dim)
        out[name] = CovGaussianMixtureProposal(
            centers=base.centers.copy(), weights=base.weights.copy(),
            covs=tuple(np.asarray(c, dtype=float) for c in covs),
            component_mode_ids=base.component_mode_ids,
            legality_checked=True,
            min_eig_sigma_minus_halfI=base.min_eig_sigma_minus_halfI)
    return out


def enumerate_candidate_states(load_config=None) -> dict:
    """D1 entry: enumerate ALL 56 (config, s2) candidates w/ legality verdicts."""
    grid = load_config() if load_config else _load_grid()

    def _grid_default():
        from hyptraj.m1d.experiments import load_freeze as _lf
        cache = {r["config_id"]: r for r in _lf()["benchmark_configs"]}
        return lambda cid: config_from_record(cache[cid])

    bcs = {}
    from hyptraj.m1d.experiments import load_freeze
    cache = {r["config_id"]: r for r in load_freeze()["benchmark_configs"]}
    for cid in grid["frozen_configs"]:
        bcs[cid] = config_from_record(cache[cid])

    states, illegal, stops = [], [], []
    for cid in grid["frozen_configs"]:
        bc = bcs[cid]
        short = cid.split("_")[-1]
        for s2 in grid["s2_grid_locked"]:
            st = assemble_state(bc, float(s2), short_config=short)
            if isinstance(st, dict):
                rec = {"config_id": cid, "state_id": st["state_id"],
                       "s2": float(s2), "status": st["status"],
                       "min_eig_selected": st.get("min_eig_selected")}
                if st["status"] == "ILLEGAL_PRE_FREEZE":
                    illegal.append(rec)
                else:
                    stops.append(rec)
            else:
                states.append(st)
    return {"grid": grid, "states": states,
            "illegal_pre_freeze": illegal, "assembly_stops": stops}


def archive_selected_mode(cid: str) -> str | None:
    """Archived M1-D ``variance_selector`` choice for (config, ANCHOR_SEED)."""
    try:
        arch = json.loads((REPO / "results" / "phase_m1d" / "d1_selection_only"
                           / "layer_a_one_birth_v1.json").read_text(
                               encoding="utf-8"))
        for entry in arch["records_by_config"]:
            if entry.get("config_id") != cid:
                continue
            for r in entry["records"]:
                if int(r.get("seed", -1)) == int(ANCHOR_SEED) \
                        and str(r.get("method")) == "variance_selector":
                    return (r.get("selected_modes") or [None])[0]
    except Exception:
        return None
    return None


__all__ = [
    "ANCHOR_SEED", "BenchmarkState", "assemble_state", "state_arms",
    "enumerate_candidate_states", "archive_selected_mode",
]
