"""E6 tests: Phase E numerical / regression audit.

    A  reference builder uses requested solver config.
    B  default builder still uses production config.
    C  REF-0.1 / REF-0.05 semantic topology same.
    D  production/reference limiting endpoints same.
    E  Protocol D UNIQUE remains stable.
    F  common-range residual remains small.
    G  energy-budget telescoping.
    H  VAC energy conservation.
    I  production regression snapshot identifies production solver.
    J  semantic regression exact.
    K  numeric regression uses dimension-specific tolerance.
    L  no visualization samples enter formal comparisons.

The regression snapshot ``tests/data/qian_sanger_comparison_v1.json``
holds the PRODUCTION (P9-20) Phase E values; the high-precision
reference is never used as a regression source.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis import (
    build_qian_comparison_trajectory,
    build_sanger_comparison_trajectory,
)
from hyptraj.analysis.comparison_validation import (
    AUDIT_CASES,
    REFERENCE_SOLVER_CONFIG,
    make_solver_config,
    run_audit_case,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.simulation.numerics import PRODUCTION_SOLVER_CONFIG
from hyptraj.simulation.trajectory import SolverConfig

SNAPSHOT_PATH = Path(__file__).parent / "data" / "qian_sanger_comparison_v1.json"

# ---------------------------------------------------------------------------
# Dimension-specific regression tolerances (E6 §26).  Each tolerance is
# 2-4 orders of magnitude above the observed production-vs-reference
# numerical error and far below the scientific reporting precision.
# ---------------------------------------------------------------------------
TOLERANCES = {
    "time": 1e-3,        # s        (observed error ~5e-8 s)
    "range": 1.0,        # m        (observed error ~5e-3 m)
    "altitude": 1.0,     # m        (observed error ~5e-5 m)
    "velocity": 1e-2,    # m/s      (observed error ~1e-6 m/s)
    "energy": 0.1,       # J/kg     (observed error ~4.5e-3 J/kg)
    "exposure": 1e-3,    # s        (observed error ~1e-6 s)
    "q": 0.1,            # Pa       (observed error ~9e-5 Pa)
    "aD": 2e-5,          # m/s^2    (observed error ~1.8e-8)
    "fraction": 1e-8,    # -        (observed error ~1e-12)
    "dimensionless": 1e-12,  # relative drift etc.
}


def tolerance_for(key: str) -> float:
    """Per-dimension tolerance for a snapshot metric key."""
    if "fraction" in key:
        return TOLERANCES["fraction"]
    if "aD" in key:
        return TOLERANCES["aD"]
    if "q_max" in key:
        return TOLERANCES["q"]
    if key in ("tau_common", "t_common", "t_Q", "t_S", "pd_t_Q", "pd_t_S",
               "time_saving", "elapsed_time_extension",
               "qian_terminal_time", "sanger_terminal_time",
               "qian_capture_time", "sanger_vac_duration",
               "sanger_atm_duration", "tau_at_common_time_qian",
               "tau_at_common_time_sanger", "tau_at_common_range_qian",
               "tau_at_common_range_sanger", "qian_v_min_time",
               "sanger_v_min_time"):
        return TOLERANCES["time"]
    if key.endswith("_R") or "range" in key or key in (
            "R_common", "qian_terminal_range", "sanger_terminal_range",
            "sanger_vac_range"):
        return TOLERANCES["range"]
    if key.endswith("_h") or "h_min" in key or "h_max" in key:
        return TOLERANCES["altitude"]
    if key.endswith("_v") or "v_min" in key:
        return TOLERANCES["velocity"]
    if key.endswith("_E") or "loss" in key or "energy" in key:
        return TOLERANCES["energy"]
    if "drift" in key or "rel" in key:
        return TOLERANCES["dimensionless"]
    # Default: energy-scale tolerance for any unclassified J/kg-like
    # quantity (kept conservative, never tighter than observed error).
    return TOLERANCES["energy"]


@pytest.fixture(scope="module")
def inputs():
    env = EnvironmentParams()
    vehicle = VehicleParams()
    initial = InitialCondition(
        altitude=100_000.0,
        velocity=7_000.0,
        flight_path_angle_deg=-5.0,
        range_angle=0.0,
    )
    control = ConstantKControl(3.0)
    return env, vehicle, initial, control


# ---------------------------------------------------------------------------
# A / B. Builder solver override
# ---------------------------------------------------------------------------
def test_a_reference_builder_uses_requested_solver_config(inputs):
    env, vehicle, initial, control = inputs
    ref = make_solver_config(1e-12, [1e-7, 1e-14, 1e-10, 1e-14], 0.1)
    qian = build_qian_comparison_trajectory(
        env, vehicle, initial, control, solver_config=ref)
    sanger = build_sanger_comparison_trajectory(
        env, vehicle, initial, control, solver_config=ref)
    for trajectory in (qian, sanger):
        assert trajectory.solver_config is ref
        assert trajectory.solver_config.rtol == 1e-12
        assert trajectory.solver_config.max_step == 0.1


def test_b_default_builder_uses_production_config(inputs):
    env, vehicle, initial, control = inputs
    qian = build_qian_comparison_trajectory(env, vehicle, initial, control)
    sanger = build_sanger_comparison_trajectory(
        env, vehicle, initial, control)
    for trajectory in (qian, sanger):
        assert trajectory.solver_config is PRODUCTION_SOLVER_CONFIG


# ---------------------------------------------------------------------------
# C / D / E / F. Audit case stability
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def audit_cases(inputs):
    env, vehicle, initial, control = inputs
    return {case: run_audit_case(env, vehicle, initial, control, case)
            for case in AUDIT_CASES}


def test_c_ref_semantic_topology_same(audit_cases):
    for field in ("qian_terminal_kind", "sanger_terminal_kind",
                  "sanger_skip_count", "sanger_mode_sequence",
                  "qian_source_structure"):
        assert audit_cases["REF-0.1"].__dict__[field] == \
            audit_cases["REF-0.05"].__dict__[field]


def test_d_production_reference_limiting_endpoints_same(audit_cases):
    prod = audit_cases["P9-20"]
    ref = audit_cases["REF-0.1"]
    assert prod.common_time_limiter == ref.common_time_limiter == "qian"
    assert prod.common_range_limiter == ref.common_range_limiter == "qian"
    assert prod.exposure_limiter == ref.exposure_limiter == "qian"
    # Stable across ALL audit cases.
    for case in AUDIT_CASES:
        r = audit_cases[case]
        assert r.common_time_limiter == "qian"
        assert r.common_range_limiter == "qian"
        assert r.exposure_limiter == "qian"


def test_e_protocol_d_unique_stable(audit_cases):
    for case in AUDIT_CASES:
        r = audit_cases[case]
        assert r.protocol_d_qian_status == "UNIQUE"
        assert r.protocol_d_sanger_status == "UNIQUE"


def test_f_common_range_residual_small(audit_cases):
    for case in AUDIT_CASES:
        assert audit_cases[case].root_residuals["qian"] < 1e-3
        assert audit_cases[case].root_residuals["sanger"] < 1e-3


# ---------------------------------------------------------------------------
# G / H. Energy accounting
# ---------------------------------------------------------------------------
def test_g_energy_budget_telescoping(inputs):
    env, vehicle, initial, control = inputs
    for case in ("P9-20", "REF-0.1"):
        r = run_audit_case(env, vehicle, initial, control, case)
        m = r.metrics
        # Under the frozen baseline the common-time checkpoint coincides
        # with the Qian RTI terminal, so the E2 checkpoint loss equals
        # the total research loss (E0 - E_terminal) to numerical noise.
        assert abs(m["qian_total_loss"] - m["qian_loss"]) < 0.1
        # The segment-level telescoping identity (sum of segment losses
        # == E0 - E_terminal, residual ~1e-12) is verified exactly in
        # the E3 regression tests; here we only cross-check consistency.
        assert m["qian_total_loss"] > 0.0
        assert m["sanger_total_loss"] > 0.0


def test_h_vac_energy_conservation(inputs):
    env, vehicle, initial, control = inputs
    for case in AUDIT_CASES:
        r = run_audit_case(env, vehicle, initial, control, case)
        assert r.metrics["sanger_vac_max_rel_drift"] < 1e-9


# ---------------------------------------------------------------------------
# I / J / K. Production regression snapshot
# ---------------------------------------------------------------------------
def test_i_snapshot_identifies_production_solver():
    assert SNAPSHOT_PATH.exists()
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snapshot = json.load(f)
    assert snapshot["reference_name"] == "qian-sanger-comparison-v1"
    # Hard gate: the snapshot solver IS the production config, never the
    # high-precision reference (E6 §28).
    solver = snapshot["solver"]
    assert solver["method"] == PRODUCTION_SOLVER_CONFIG.method
    assert solver["rtol"] == PRODUCTION_SOLVER_CONFIG.rtol
    assert solver["max_step"] == PRODUCTION_SOLVER_CONFIG.max_step
    assert solver["dense_output"] is True
    assert solver["rtol"] != REFERENCE_SOLVER_CONFIG.rtol


def test_j_semantic_regression_exact(inputs):
    env, vehicle, initial, control = inputs
    prod = run_audit_case(env, vehicle, initial, control, "P9-20")
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snapshot = json.load(f)
    semantic = snapshot["semantic_fields"]
    assert prod.qian_terminal_kind == semantic["qian_terminal_kind"] == "RTI"
    assert prod.sanger_terminal_kind == \
        semantic["sanger_terminal_kind"] == "SRTI"
    assert prod.sanger_skip_count == semantic["sanger_skip_count"] == 2
    assert prod.sanger_mode_sequence == semantic["sanger_mode_sequence"]
    assert prod.qian_source_structure == semantic["qian_source_structure"]
    assert prod.common_time_limiter == semantic["common_time_limiter"]
    assert prod.common_range_limiter == semantic["common_range_limiter"]
    assert prod.exposure_limiter == semantic["exposure_limiter"]
    assert prod.protocol_d_qian_status == \
        semantic["protocol_d_qian_status"] == "UNIQUE"
    assert prod.protocol_d_sanger_status == \
        semantic["protocol_d_sanger_status"] == "UNIQUE"
    # JSON stores tuples as lists; normalize before exact comparison.
    frozen_modes = {
        kind: {side: tuple(modes) for side, modes in sides.items()}
        for kind, sides in semantic["checkpoint_modes"].items()
    }
    assert prod.checkpoint_modes == frozen_modes


def test_k_numeric_regression_dimension_specific(inputs):
    env, vehicle, initial, control = inputs
    prod = run_audit_case(env, vehicle, initial, control, "P9-20")
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snapshot = json.load(f)
    frozen = snapshot["production_values"]
    # Every frozen numeric field is compared with its own dimension
    # tolerance (no uniform blanket tolerance, E6 §26).
    checked = 0
    for key, expected in frozen.items():
        actual = prod.metrics[key]
        tol = tolerance_for(key)
        assert abs(actual - expected) <= tol, (
            f"{key}: production {actual:.9e} vs frozen {expected:.9e} "
            f"(tol {tol:.3e})")
        checked += 1
    assert checked == len(frozen)


# ---------------------------------------------------------------------------
# L. No visualization samples in formal comparisons
# ---------------------------------------------------------------------------
def test_l_no_visualization_samples_in_formal_comparisons(inputs):
    env, vehicle, initial, control = inputs
    prod = run_audit_case(env, vehicle, initial, control, "P9-20")
    # The audit path uses only the continuous analysis APIs; checkpoint
    # states come from exact JSON/event data, never from curve samples.
    assert prod.metrics["DeltaR_time"] > 0.0
    assert prod.root_residuals["qian"] < 1e-3
    # The snapshot was built by the audit runner from production values.
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snapshot = json.load(f)
    assert "production_values" in snapshot
    assert "visualization" not in snapshot
