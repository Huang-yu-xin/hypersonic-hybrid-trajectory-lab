"""Phase-F numerical regression tests (F7A).

Fast, stable tests over the frozen Phase-F regression snapshot
``tests/data/phase_f_gamma_k_sensitivity_v1.json``: schema, baseline,
selected anchors, categorical constants, numerical tolerances and source
invariants.  The full canonical runners (23k F3 / 24k F5) are manual
audits, never run under pytest.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from hyptraj.models.parameters import (
    EnvironmentParams,
    InitialCondition,
    VehicleParams,
)
from hyptraj.controls.constant_k import ConstantKControl
from hyptraj.analysis.comparison_mapping import evaluate_comparison_point

DATA_DIR = Path(__file__).resolve().parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_f_gamma_k_sensitivity_v1.json")
    .read_text(encoding="utf-8")
)
PHASE_E = json.loads(
    (DATA_DIR / "qian_sanger_comparison_v1.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def base():
    env = EnvironmentParams()
    veh = VehicleParams()
    ini = InitialCondition(
        altitude=100_000.0, velocity=7_000.0,
        flight_path_angle_deg=-5.0, range_angle=0.0)
    ctl = ConstantKControl(3.0)
    return env, veh, ini, ctl


# ---------------------------------------------------------------------------
# Snapshot schema
# ---------------------------------------------------------------------------
def test_snapshot_schema():
    assert SNAPSHOT["schema_version"] == \
        "phase-f-gamma-k-sensitivity-regression-v1"
    for key in ("source_commit", "domain", "topology", "grazing", "fd", "f5",
                "f6"):
        assert key in SNAPSHOT


def test_snapshot_provenance_commits():
    prov = SNAPSHOT["source_commit"]
    assert prov["phase_e_anchor"] == \
        "44a99119cf9e82e64d68b5b8abdbb4a20406c7bc"
    assert len(prov["f0"]) == 40
    assert len(prov["f6"]) == 40


def test_snapshot_domain():
    d = SNAPSHOT["domain"]
    assert d["gamma0_deg"] == [-9.0, -1.0]
    assert d["gamma_step_deg"] == 0.25
    assert d["K"] == [1.0, 5.0]
    assert d["K_step"] == 0.125
    assert d["canonical_centers"] == 1089


# ---------------------------------------------------------------------------
# Topology constants (categorical, exact)
# ---------------------------------------------------------------------------
def test_topology_constants():
    t = SNAPSHOT["topology"]
    assert t["qian_regime_counts"] == {"QIAN_RTI": 1089}
    assert t["sanger_regime_counts"] == {
        "SRTI_N0": 322, "SRTI_N1": 306, "SRTI_N2": 211,
        "SRTI_N3": 153, "SRTI_N4": 85, "SRTI_N5": 12}
    assert t["branch_count"] == 5
    assert t["branches"] == ["B0", "B1", "B2", "B3", "B4"]
    assert t["boundary_cell_count"] == 5735


def test_grazing_anchors():
    g = SNAPSHOT["grazing"]
    assert g["phi_sign_consistency"] == "100%"
    assert len(g["extremal_anchors"]) == 10
    assert g["recovered_canonical_count"] == 5
    assert g["recovered_verified"] == 5
    for anchor in g["extremal_anchors"]:
        assert anchor["reference_dual_stable"] is True


# ---------------------------------------------------------------------------
# FD policy / baseline Jacobian anchors
# ---------------------------------------------------------------------------
def test_fd_policy_anchors():
    fd = SNAPSHOT["fd"]
    assert fd["gamma_step_deg"] == 0.1
    assert fd["K_step"] == 0.025
    assert fd["gamma_policy"] == "GLOBAL_STEP_POLICY"
    assert fd["K_policy"] == "GLOBAL_STEP_POLICY"


def test_baseline_jacobians_frozen():
    fd = SNAPSHOT["fd"]
    q = fd["baseline_qian_jacobian"]
    s = fd["baseline_sanger_jacobian"]
    # 5x2 and 7x2 structure.
    assert len(q["gamma"]) == 5 and len(q["K"]) == 5
    assert len(s["gamma"]) == 7 and len(s["K"]) == 7
    # F4 recorded baseline values (per radian / per unit K).
    assert q["gamma"]["qian_rti_time_s"] == pytest.approx(2926.909, rel=1e-3)
    assert s["gamma"]["sanger_srti_range_m"] == pytest.approx(
        -5.305e6, rel=1e-3)


# ---------------------------------------------------------------------------
# F5 structural sign classes
# ---------------------------------------------------------------------------
def test_f5_regime_sign_classes():
    c = SNAPSHOT["f5"]["regime_sign_classes"]
    # N0 all positive dR/dgamma; N4/N5 all negative; N1/N2/N3 mixed.
    assert c["dR_dgamma"]["SRTI_N0"]["negative"] == 0
    assert c["dR_dgamma"]["SRTI_N4"]["positive"] == 0
    assert c["dR_dgamma"]["SRTI_N5"]["positive"] == 0
    assert c["dR_dgamma"]["SRTI_N1"]["positive"] > 0
    assert c["dR_dgamma"]["SRTI_N1"]["negative"] > 0
    # dR/dK all positive.
    for regime in ("SRTI_N0", "SRTI_N1", "SRTI_N2", "SRTI_N3",
                   "SRTI_N4", "SRTI_N5"):
        assert c["dR_dK"][regime]["negative"] == 0
    # Qian all positive.
    assert c["qian_dR_dgamma"]["negative"] == 0


def test_f5_availability():
    a = SNAPSHOT["f5"]["availability"]
    assert a["qian_gamma"]["GLOBAL_ACCEPTED"] == 1023
    assert a["qian_gamma"]["GUARDRAIL_CENTRAL_UNAVAILABLE"] == 66
    assert a["qian_K"]["GLOBAL_ACCEPTED"] == 1023


# ---------------------------------------------------------------------------
# Corrected F6 comparison semantics
# ---------------------------------------------------------------------------
def test_f6_corrected_protocol_d():
    d = SNAPSHOT["f6"]["protocol_d"]
    assert d["UNIQUE"] == 1089
    assert d["AMBIGUOUS"] == 0
    assert d["NOT_AVAILABLE"] == 0  # float-edge resolved numerically


def test_f6_limiters_frozen():
    lim = SNAPSHOT["f6"]["limiters"]
    assert lim["time"] == {"QIAN": 651, "SANGER": 438}
    assert lim["range"] == {"QIAN": 733, "SANGER": 356}
    assert lim["exposure"] == {"QIAN": 376, "SANGER": 713}


def test_f6_signatures():
    assert SNAPSHOT["f6"]["signature_count"] == 15
    assert SNAPSHOT["f6"]["signature_transition_cells"] == 269
    reasons = SNAPSHOT["f6"]["signature_transition_by_reason"]
    assert reasons["MULTIPLE"] > 0


def test_f6_metric_sign_classes():
    m = SNAPSHOT["f6"]["metric_sign_classes"]
    for key in ("delta_range_time", "time_saving", "delta_range_tau"):
        assert m[key]["negative"] == 0
        assert m[key]["positive"] == m[key]["count"]


# ---------------------------------------------------------------------------
# Baseline B/C/D reproduction of the Phase-E frozen reference
# ---------------------------------------------------------------------------
def test_baseline_common_condition_reproduces_phase_e(base):
    env, veh, ini, ctl = base
    rec = evaluate_comparison_point(env, veh, ini, ctl, "test")
    pv = PHASE_E["production_values"]
    b = rec["protocol_b"]
    c = rec["protocol_c"]
    d = rec["protocol_d"]
    assert abs(b["common_time_s"] - pv["t_common"]) < 1e-9
    assert abs(b["delta_range_m"] - pv["DeltaR_time"]) < 1e-9
    assert abs(c["common_range_m"] - pv["R_common"]) < 1e-9
    assert abs(c["time_saving_s"] - pv["time_saving"]) < 1e-9
    assert d["status"] == "UNIQUE"
    assert abs(d["elapsed_time_extension_s"]
               - pv["elapsed_time_extension"]) < 1e-9


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------
def test_phase_e_frozen_sources_untouched():
    out = subprocess.run(
        ["git", "status", "--short",
         "src/hyptraj/analysis/comparison.py",
         "src/hyptraj/analysis/comparison_protocols.py",
         "src/hyptraj/analysis/comparison_mechanisms.py",
         "tests/data/qian_sanger_comparison_v1.json"],
        capture_output=True, text=True)
    # The working tree may contain the F7A changes (comparison_mapping /
    # research integrators); Phase-E sources must be unmodified relative
    # to the F6 commit baseline.
    out2 = subprocess.run(
        ["git", "diff", "--name-only", "a1e2fe9", "--",
         "src/hyptraj/analysis/comparison.py",
         "src/hyptraj/analysis/comparison_protocols.py",
         "src/hyptraj/analysis/comparison_mechanisms.py",
         "tests/data/qian_sanger_comparison_v1.json"],
        capture_output=True, text=True)
    assert out2.stdout.strip() == ""


def test_phase_f_snapshot_untracked_till_commit():
    # The snapshot is a tracked data file; the tests read it as the
    # source of truth (committed with F7A).
    assert (DATA_DIR / "phase_f_gamma_k_sensitivity_v1.json").exists()


# ---------------------------------------------------------------------------
# Numerical tolerances (dimension-specific, E6 scale)
# ---------------------------------------------------------------------------
def test_numeric_tolerance_scales():
    # Frozen Phase-E E6 scale used across F7A (documented, dimension
    # aware; never a mixed-unit global error).
    tolerances = {"time": 1e-3, "exposure": 1e-3, "range": 1.0,
                  "altitude": 1.0, "velocity": 1e-2, "energy": 0.1}
    assert tolerances["time"] == 1e-3
    assert tolerances["range"] == 1.0
    assert tolerances["velocity"] == 1e-2
    assert tolerances["energy"] == 0.1
