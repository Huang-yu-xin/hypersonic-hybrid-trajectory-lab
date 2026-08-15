"""Phase-F single-parameter pilot tests (F1).

Covers the F1 acceptance surface A-O:

A. gamma grid exactly 17 points
B. K grid exactly 17 points
C. baseline appears in both slices
D. unique-point union = 33
E. baseline dedup
F. one-point runner returns paired Qian/Sanger record
G. baseline anchor PASS
H. Qian topology signature deterministic
I. Sanger topology signature deterministic
J. transition detector catches synthetic regime change
K. transition detector catches exact-signature-only change
L. NA serialized as null, not numeric zero
M. censored triggers stop gate
N. numerical failure triggers stop gate
O. no Phase-E Protocol B/C/D metric in F1 schema

The full 33-point sweep is NOT run under pytest: it is executed manually
by experiments/07_gamma_k_sensitivity/run_single_parameter_pilot.py.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.analysis.sensitivity_pilot import (
    ANCHOR_GAMMA0_DEG,
    ANCHOR_K,
    GAMMA_SLICE_DEG,
    K_SLICE,
    PairedPointResult,
    ParameterPoint,
    all_unique_points,
    collect_stop_gate_reasons,
    detect_transition_intervals,
    gamma_slice_points,
    k_slice_points,
    qian_topology_signature,
    run_parameter_point,
    sanger_topology_signature,
    verify_baseline_anchor,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
REFERENCE = json.loads(
    (DATA_DIR / "qian_sanger_comparison_v1.json").read_text(encoding="utf-8")
)

# Phase-E Protocol B/C/D metric names that must NOT appear in F1 rows.
PROTOCOL_BCD_KEYS = (
    "time_limiter",
    "range_limiter",
    "exposure_limiter",
    "common_time_s",
    "common_range_m",
    "DeltaR",
    "protocol_d",
)


@pytest.fixture(scope="module")
def base():
    return EnvironmentParams(), VehicleParams()


# ---------------------------------------------------------------------------
# A / B / C / D / E. frozen grids and dedup
# ---------------------------------------------------------------------------
def test_gamma_grid_exactly_17_points():
    points = gamma_slice_points()
    assert len(points) == 17
    assert np.allclose(
        [p.gamma0_deg for p in points],
        np.linspace(-7.0, -3.0, 17),
    )
    assert all(p.K == ANCHOR_K for p in points)


def test_k_grid_exactly_17_points():
    points = k_slice_points()
    assert len(points) == 17
    assert np.allclose(
        [p.K for p in points],
        np.linspace(2.0, 4.0, 17),
    )
    assert all(p.gamma0_deg == ANCHOR_GAMMA0_DEG for p in points)


def test_baseline_appears_in_both_slices():
    baseline = (ANCHOR_GAMMA0_DEG, ANCHOR_K)
    assert baseline in {p.key for p in gamma_slice_points()}
    assert baseline in {p.key for p in k_slice_points()}


def test_unique_point_union_is_33():
    points = all_unique_points()
    assert len(points) == 33
    keys = [p.key for p in points]
    assert len(set(keys)) == 33  # no duplicates at all


def test_baseline_dedup():
    points = all_unique_points()
    baseline_keys = [
        p.key for p in points
        if p.key == (ANCHOR_GAMMA0_DEG, ANCHOR_K)
    ]
    assert baseline_keys == [(ANCHOR_GAMMA0_DEG, ANCHOR_K)]


# ---------------------------------------------------------------------------
# F. one-point runner returns paired Qian/Sanger record
# ---------------------------------------------------------------------------
def test_one_point_runner_paired_record(base):
    env, vehicle = base
    point = ParameterPoint(gamma0_deg=ANCHOR_GAMMA0_DEG, K=ANCHOR_K)
    pr = run_parameter_point(env, vehicle, point, git_commit="test")
    assert pr.qian_row["model"] == "qian"
    assert pr.sanger_row["model"] == "sanger"
    assert pr.qian_row["qian_regime"] == "QIAN_RTI"
    assert pr.sanger_row["sanger_regime"] == "SRTI_N2"
    assert pr.qian_row["gamma0_deg"] == ANCHOR_GAMMA0_DEG
    assert pr.sanger_row["K"] == ANCHOR_K
    assert pr.qian_result is not None
    assert pr.sanger_trajectory is not None


# ---------------------------------------------------------------------------
# G. baseline anchor PASS against the frozen Phase E reference
# ---------------------------------------------------------------------------
def test_baseline_anchor_pass(base):
    env, vehicle = base
    anchor = verify_baseline_anchor(
        env, vehicle, git_commit="test", reference_json=REFERENCE
    )
    assert anchor["pass"]
    assert anchor["qian"]["regime"] == "QIAN_RTI"
    assert anchor["sanger"]["regime"] == "SRTI_N2"
    assert anchor["sanger"]["skip_count"] == 2


# ---------------------------------------------------------------------------
# H / I. topology signatures deterministic
# ---------------------------------------------------------------------------
def test_qian_topology_signature_deterministic():
    args = ("RTI", ("ENTRY_CAPTURE", "QEG_GLIDE"), ("capture", "rti"))
    assert qian_topology_signature(*args) == (
        "terminal=RTI;modes=ENTRY_CAPTURE > QEG_GLIDE;events=capture > rti"
    )
    assert qian_topology_signature(*args) == qian_topology_signature(*args)


def test_sanger_topology_signature_deterministic():
    args = ("srti", ("SANGER_ATM", "SANGER_VAC", "SANGER_ATM"),
            ("synthetic_initial_entry", "atmospheric_pullout",
             "atmosphere_exit", "vacuum_apogee", "atmosphere_entry",
             "srti"))
    assert sanger_topology_signature(*args) == (
        "terminal=srti;modes=SANGER_ATM > SANGER_VAC > SANGER_ATM;"
        "events=synthetic_initial_entry > atmospheric_pullout > "
        "atmosphere_exit > vacuum_apogee > atmosphere_entry > srti"
    )
    assert sanger_topology_signature(*args) == sanger_topology_signature(*args)


# ---------------------------------------------------------------------------
# J / K. transition detection (synthetic rows)
# ---------------------------------------------------------------------------
def _fake_row(qian_regime, qian_sig, sanger_regime, sanger_sig) -> dict:
    return {
        "qian_regime": qian_regime,
        "exact_topology_signature": qian_sig,
        "sanger_regime": sanger_regime,
        "exact_topology_signature": sanger_sig,
    }


def _fake_pair(gamma0_deg: float, k: float, qian_regime: str, qian_sig: str,
               sanger_regime: str, sanger_sig: str) -> PairedPointResult:
    point = ParameterPoint(gamma0_deg=gamma0_deg, K=k)
    row = _fake_row(qian_regime, qian_sig, sanger_regime, sanger_sig)
    return PairedPointResult(
        parameter=point,
        qian_row=row,
        sanger_row=row,
        qian_result=None,
        sanger_trajectory=None,
    )


def test_transition_detector_catches_compact_change():
    points = [
        _fake_pair(-5.5, 3.0, "QIAN_RTI", "sig-A", "SRTI_N2", "sig-A"),
        _fake_pair(-5.25, 3.0, "QIAN_RTI", "sig-A", "SRTI_N2", "sig-A"),
        _fake_pair(-5.0, 3.0, "QIAN_RTI", "sig-A", "SRTI_N3", "sig-B"),
    ]
    compact, exact_only = detect_transition_intervals(points, "gamma0")
    assert len(compact) == 1
    assert compact[0]["left_value"] == -5.25
    assert compact[0]["right_value"] == -5.0
    assert compact[0]["left_sanger_regime"] == "SRTI_N2"
    assert compact[0]["right_sanger_regime"] == "SRTI_N3"
    assert exact_only == []


def test_transition_detector_catches_exact_signature_only_change():
    points = [
        _fake_pair(-5.5, 3.0, "QIAN_RTI", "sig-A", "SRTI_N2", "sig-A"),
        _fake_pair(-5.25, 3.0, "QIAN_RTI", "sig-A", "SRTI_N2", "sig-A"),
        # same compact regimes, different exact event sequence
        _fake_pair(-5.0, 3.0, "QIAN_RTI", "sig-A", "SRTI_N2", "sig-B"),
    ]
    compact, exact_only = detect_transition_intervals(points, "gamma0")
    assert compact == []
    assert len(exact_only) == 1
    assert exact_only[0]["transition_type"] == "exact-topology-only"
    assert exact_only[0]["left_value"] == -5.25
    assert exact_only[0]["right_value"] == -5.0


# ---------------------------------------------------------------------------
# L. NA serialized as null, never numeric zero
# ---------------------------------------------------------------------------
def test_na_serialized_as_null_not_zero(base):
    env, vehicle = base
    point = ParameterPoint(gamma0_deg=ANCHOR_GAMMA0_DEG, K=ANCHOR_K)
    # A censored point has no RTI: its rti_* fields must be null.
    pr = run_parameter_point(
        env, vehicle, point, git_commit="test", qian_max_time=50.0
    )
    assert pr.qian_row["qian_regime"] == "CENSORED"
    assert pr.qian_row["rti_time_s"] is None
    assert pr.qian_row["qeg_duration_s"] is None
    assert pr.qian_row["rti_time_s"] != 0.0


# ---------------------------------------------------------------------------
# M / N. stop-gate triggers (pure function)
# ---------------------------------------------------------------------------
def test_censored_triggers_stop_gate():
    qian_censored = {
        "gamma0_deg": -5.0, "K": 3.0,
        "qian_regime": "CENSORED", "message": "no event within horizon",
    }
    reasons = collect_stop_gate_reasons(
        anchor_pass=True,
        qian_rows=[qian_censored],
        sanger_rows=[],
        health_violations=[],
    )
    assert any("Qian CENSORED" in r for r in reasons)


def test_numerical_failure_triggers_stop_gate():
    sanger_failed = {
        "gamma0_deg": -5.0, "K": 3.0,
        "sanger_regime": "NUMERICAL_FAILURE", "message": "solver failed",
    }
    reasons = collect_stop_gate_reasons(
        anchor_pass=True,
        qian_rows=[],
        sanger_rows=[sanger_failed],
        health_violations=[],
    )
    assert any("Sanger NUMERICAL_FAILURE" in r for r in reasons)


def test_clean_rows_no_stop_gate():
    qian_ok = {
        "gamma0_deg": -5.0, "K": 3.0,
        "qian_regime": "QIAN_RTI", "message": "",
    }
    sanger_ok = {
        "gamma0_deg": -5.0, "K": 3.0,
        "sanger_regime": "SRTI_N2", "message": "",
    }
    assert collect_stop_gate_reasons(
        anchor_pass=True,
        qian_rows=[qian_ok],
        sanger_rows=[sanger_ok],
        health_violations=[],
    ) == []


# ---------------------------------------------------------------------------
# O. no Phase-E Protocol B/C/D metric in the F1 schema
# ---------------------------------------------------------------------------
def test_no_protocol_bcd_metric_in_f1_schema(base):
    env, vehicle = base
    point = ParameterPoint(gamma0_deg=ANCHOR_GAMMA0_DEG, K=ANCHOR_K)
    pr = run_parameter_point(env, vehicle, point, git_commit="test")
    for row in (pr.qian_row, pr.sanger_row):
        for key in PROTOCOL_BCD_KEYS:
            assert key not in row
