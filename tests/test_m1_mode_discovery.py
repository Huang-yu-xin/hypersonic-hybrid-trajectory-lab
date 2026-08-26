"""M1 -- mode discovery / birth-gate tests (task Sec. 11 / 12 / 29.6).

Covers:

- a crafted 2-mode case where the secondary topology mode is probability-
  small but variance-dominant: the birth gate must trigger on it (H-M1.1
  mechanism, §29.6);
- a low-variance "nuisance" far mode with ~0 observed samples must NOT
  trigger;
- an already-represented mode must NOT trigger even with a huge variance
  share (represented_by_component condition, task Sec. 11 definition);
- epsilon checks of the frozen gate constants taken from the frozen config
  (any change must go through the amendment protocol, task Sec. 37).

Pure numpy tests with fixed debug seeds; no simulator.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m1.mixture_weights import component_log_densities, mixture_log_density
from hyptraj.m1.mode_discovery import diagnose_missing_mode

REPO = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (REPO / "configs" / "m1_closed_loop_v0.json").read_text(encoding="utf-8")
)

A1, A2, A3 = -1.5, 1.9, 3.5
M0 = -1.5


def _logp(z):
    z = np.asarray(z, dtype=float)
    d = z.shape[1]
    return -np.sum(z**2, axis=1) / 2.0 - 0.5 * d * np.log(2.0 * np.pi)


def _draw(rng, centers, pi, n):
    cent = np.asarray(centers, dtype=float)
    pi = np.asarray(pi, dtype=float)
    comp = rng.choice(cent.shape[0], size=n, p=pi)
    return cent[comp] + rng.standard_normal((n, cent.shape[1]))


def _labels(z, include_far: bool, nominal="S0"):
    z = np.asarray(z, dtype=float)
    out = np.full(z.shape[0], nominal, dtype=object)
    out[z[:, 0] <= A1] = "S1"
    if include_far:
        out[z[:, 0] >= A3] = "S3"       # far nuisance mode
    out[z[:, 0] >= A2] = "S2"
    return out


def _pilot(rng, n=50_000, include_far=False):
    z = _draw(rng, np.array([[M0]]), np.array([1.0]), n)
    centers = np.array([[M0]])
    logq_ji = component_log_densities(z, centers)
    logr = mixture_log_density(logq_ji, np.array([1.0]))
    labels = _labels(z, include_far=include_far)
    return z, centers, _logp(z), logr, labels


class TestBirthGateFrozenConfig:
    def test_frozen_constants_match_task(self):
        # task Sec. 12 values must stay locked (amendment required to change)
        assert CONFIG["mode_birth"]["tau_birth_main"] == 0.10
        assert CONFIG["mode_birth"]["tau_birth_lower_confidence"] == 0.05
        assert CONFIG["mode_birth"]["min_mode_observations"] == 5
        assert CONFIG["eta"]["main"] == 0.8


class TestVarianceDominantTrigger:
    def test_secondary_variance_dominant_mode_triggers(self):
        # S2: P ~ 3e-4 under q0, but L_S2 >> L_S1 -> must pass the gate
        rng = np.random.default_rng(4242)
        z, centers, logp, logr, labels = _pilot(rng, n=50_000)
        d = diagnose_missing_mode(
            z, centers, np.array([1.0]), logp, logr, labels, "S0",
            component_mode_ids={"S1"},
            tau_birth_main=CONFIG["mode_birth"]["tau_birth_main"],
            tau_birth_lower_confidence=CONFIG["mode_birth"]["tau_birth_lower_confidence"],
            min_mode_observations=CONFIG["mode_birth"]["min_mode_observations"],
            n_bootstrap=200, rng=np.random.default_rng(42),
        )
        assert d.action == "ADD_COMPONENT"
        assert d.candidate_mode == "S2"
        stats = {s.mode_id: s for s in d.mode_stats}
        assert stats["S2"].omega_k_V_hat >= 0.10
        assert stats["S2"].omega_lcb95 >= 0.05
        assert stats["S2"].n_observed >= 5
        # S1 is represented: never a candidate despite any share
        assert stats["S1"].represented_by_component
        assert not stats["S1"].birth_eligible

    def test_low_variance_nuisance_mode_does_not_trigger(self):
        # S3 is far: ~0 pilot observations -> blocked by n_k >= 5 (and omega)
        rng = np.random.default_rng(4242)
        z, centers, logp, logr, labels = _pilot(rng, n=50_000, include_far=True)
        d = diagnose_missing_mode(
            z, centers, np.array([1.0]), logp, logr, labels, "S0",
            component_mode_ids={"S1"},
            n_bootstrap=200, rng=np.random.default_rng(42),
        )
        # S2 still triggers; S3 must never be a candidate: either it is not
        # observed at all (~0.015 expected samples) or it stays below the gate
        assert d.candidate_mode == "S2"
        stats = {s.mode_id: s for s in d.mode_stats}
        if "S3" in stats:
            assert stats["S3"].n_observed < 5
            assert not stats["S3"].birth_eligible
            assert stats["S3"].omega_k_V_hat < 0.10
        for s in d.mode_stats:
            assert s.mode_id != "S3" or not s.birth_eligible

    def test_represented_mode_never_triggers(self):
        # same variance-dominant S2, but declared represented -> HOLD
        rng = np.random.default_rng(4242)
        z, centers, logp, logr, labels = _pilot(rng, n=50_000)
        d = diagnose_missing_mode(
            z, centers, np.array([1.0]), logp, logr, labels, "S0",
            component_mode_ids={"S1", "S2"},
            n_bootstrap=200, rng=np.random.default_rng(42),
        )
        assert d.action == "HOLD"
        assert d.candidate_mode is None

    def test_single_mode_no_candidate(self):
        # only the represented primary mode observed -> HOLD (no false birth)
        rng = np.random.default_rng(4242)
        z = _draw(rng, np.array([[M0]]), np.array([1.0]), 50_000)
        centers = np.array([[M0]])
        logq_ji = component_log_densities(z, centers)
        logr = mixture_log_density(logq_ji, np.array([1.0]))
        labels = np.where(z[:, 0] <= A1, "S1", "S0")
        d = diagnose_missing_mode(
            z, centers, np.array([1.0]), _logp(z), logr, labels, "S0",
            component_mode_ids={"S1"},
            n_bootstrap=200, rng=np.random.default_rng(42),
        )
        assert d.action == "HOLD"
        assert d.candidate_mode is None