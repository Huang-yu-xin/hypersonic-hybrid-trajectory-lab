"""M3-S2S instrumentation contract: audit the real estimator source and
freeze the persisted sidecar schema (taskbook Sec. 13/14/15).

Estimator facts are read from ``hyptraj.m3d.adaptation`` source at prereg
time and frozen here; nothing about the estimator is changed -- Arm A only
adds persistence.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src/hyptraj/m3d/adaptation.py"

INSTRUMENTATION_SCHEMA_VERSION = "m3s2s_instr_v1"
SIDECAR_ARRAYS = {
    # name: (dtype, shape, description, truth_free)
    "a_vec": ("float64", ("n_samples",),
              "variance-mass importance per sample: event * weight "
              "(variance_mass_importance output)", True),
    "resp": ("float64", ("n_samples",),
             "selected-component responsibility per sample "
             "(component_responsibility output)", True),
    "sq": ("float64", ("n_samples",),
           "squared distance of each sample to the selected component "
           "center", True),
    "strata": ("int64", ("n_samples",),
               "source-stratum id per sample (draw_online_pilot)", True),
    "bootstrap_g": ("float64", ("N_BOOTSTRAP",),
                    "per-bootstrap-replicate gradient value; NaN where the "
                    "replicate point estimate was invalid", True),
}


def audit_estimator_source() -> dict:
    """Read the actual estimator source and freeze its instrumentation-
    relevant facts.  Zero mutation; audit only."""
    src = SRC.read_text(encoding="utf-8")
    boot_src = (ROOT / "src/hyptraj/m3/gradient_estimator.py").read_text(
        encoding="utf-8")
    n_bootstrap = int(re.search(r"N_BOOTSTRAP\s*=\s*(\d+)", src).group(1))
    checks = {
        "N_BOOTSTRAP_actual": n_bootstrap,
        "bootstrap_seed_construction":
            "np.random.default_rng([seed, 424243]) inside "
            "stratified_bootstrap_gradient_ci (bootstrap_seed_key)",
        "bootstrap_method":
            "fixed-stratified bootstrap: resample WITHIN each source "
            "stratum at preserved sizes; full point pipeline recomputed per "
            "replicate; percentiles (2.5/97.5) form the CI",
        "per_sample_arrays": ["a_full (a_vec)", "resp_k (resp)",
                              "sq_radius (sq)", "source_strata (strata)"],
        "ess_definition": "ESS_grad from scalar_gradient_estimate "
                          "(variance-mass importance weighting)",
        "event_counts_online": "event indicator from topology labels "
                               "(topology != S0), available online",
        "batches_field_semantics":
            "gradient.batches = 20 is a CONFIGURATION constant of the "
            "protocol record; the bootstrap is stratified by source strata, "
            "NOT by 20 independent batches (source-verified)",
        "aggregate_estimator_unchanged": True,
        "arm_a_delta": "persistence only: the replicate array (bootstrap_g) "
                       "and the four per-sample arrays are additionally "
                       "persisted; all estimator numbers are bit-identical",
    }
    # source assertions (fail fast if the estimator changed shape)
    assert str(n_bootstrap) == "500"
    assert "def stratified_bootstrap_gradient_ci" in boot_src
    assert "424243" in boot_src
    assert "scalar_gradient_estimate(a_full[idx], resp[idx], sq[idx]" in boot_src
    return {"schema_version": INSTRUMENTATION_SCHEMA_VERSION,
            "source_file": ["src/hyptraj/m3d/adaptation.py",
                            "src/hyptraj/m3/gradient_estimator.py"],
            "source_sha256": hashlib.sha256(
                (src + boot_src).encode("utf-8")).hexdigest(),
            "checks": checks}


def estimate_sidecar_bytes(n_samples: int = 20_000,
                           n_bootstrap: int | None = None) -> dict:
    """Lossless-sidecar capacity estimate for one trial (Sec. 15)."""
    if n_bootstrap is None:
        n_bootstrap = audit_estimator_source()["checks"]["N_BOOTSTRAP_actual"]
    raw = 3 * n_samples * 8 + n_samples * 8 + n_bootstrap * 8
    # observed np.savez_compressed ratio on float payloads is conservative
    # at 0.80 (i.e. ~20% reduction); budget with the RAW size to be safe
    return {"raw_bytes_per_trial": raw,
            "budget_bytes_per_trial": raw,   # conservative: no compression
            "per_million_trials_note": "960 trials => raw x 960"}


def sidecar_schema() -> dict:
    return {"schema_version": INSTRUMENTATION_SCHEMA_VERSION,
            "format": "np.savez_compressed",
            "arrays": SIDECAR_ARRAYS,
            "integrity": "instrumentation_sha256 recorded in the trial "
                         "record; sidecar durable + hash verified BEFORE "
                         "ledger COMPLETE",
            "bootstrap_caveat": "bootstrap draws are resamples of the same "
                                "20k online samples -- NEVER independent "
                                "scientific trials; N_BOOTSTRAP is not a "
                                "sample size for standalone inference"}
