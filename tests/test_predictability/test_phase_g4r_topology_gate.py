"""Phase-G4R hybrid topology-gate corrective patch tests (G4R §9-§10, §13).

G4R fixes two topology-gate contract defects in the G4 full-hybrid
nonlinear validation layer (``hybrid_validation.py``):

Issue 1 -- ``result.success == False`` was incorrectly treated as a generic
``NUMERICAL_FAILURE``.  The frozen research ``success`` flag only marks the
RESEARCH SUCCESS (RTI / SRTI reached); it is NOT equivalent to solver
failure.  Classification is now ENDPOINT-SCOPED: a structured terminal
only affects the gate when it occurs at or before the fixed endpoint ``T``
(or prevents obtaining the dense fixed-time state / topology at ``T``),
and it is routed by the structured ``terminal_kind``:

    solver failure            -> NUMERICAL_FAILURE
    grazing_or_unresolved     -> GRAZING_CROSSED
    physical terminals        -> TOPOLOGY_CHANGED
    computational censor      -> TOPOLOGY_CHANGED
    ambiguous simultaneous    -> TOPOLOGY_CHANGED
    terminal strictly after T -> prefix may still be TOPOLOGY_PRESERVED

Issue 2 -- ``EVENT_ORDER_CHANGED`` used ``set(signature)`` and lost
repeated-switch multiplicity (a missing repeated pair was mislabelled as
an order change).  It now requires SAME LENGTH + SAME MULTISET (with
multiplicity, via ``Counter``) + DIFFERENT chronological sequence;
anything else is ``TOPOLOGY_CHANGED``.

These tests use synthetic structured objects (no expensive full
trajectories).  No hybrid math is redefined -- only the classification
contract.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.predictability import hybrid_validation as V
from hyptraj.predictability.hybrid_validation import HybridTopologyGate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT = json.loads(
    (DATA_DIR / "phase_g4_hybrid_stm_v1.json").read_text(encoding="utf-8")
)

K = 3.0
PRESERVED = HybridTopologyGate.TOPOLOGY_PRESERVED
CHANGED = HybridTopologyGate.TOPOLOGY_CHANGED
ORDER = HybridTopologyGate.EVENT_ORDER_CHANGED
GRAZING = HybridTopologyGate.GRAZING_CROSSED
NUM_ERR = HybridTopologyGate.NUMERICAL_FAILURE


def _qian_result(terminal_time, terminal_kind, events, success=False):
    """Synthetic Qian-style structured result (frozen API fields only)."""
    return SimpleNamespace(terminal_time=terminal_time,
                           terminal_kind=terminal_kind,
                           success=success, events=events)


def _sanger_result(terminal_time, terminal_kind, events, success=False):
    """Synthetic Sanger-style structured result (trajectory wrapper)."""
    return SimpleNamespace(
        trajectory=SimpleNamespace(terminal_time=terminal_time,
                                   terminal_kind=terminal_kind,
                                   success=success,
                                   terminal_state=np.zeros(4),
                                   events=events))


def _collector(mode="SANGER_ATM", t_start=0.0, t_end=1e9):
    seg = SimpleNamespace(t_start=t_start, t_end=t_end, mode=mode,
                          solution=lambda t: np.ones(4))
    return SimpleNamespace(segments=(seg,))


def _sw(kind, t):
    return SimpleNamespace(kind=kind, index=0, time=t, state=np.ones(4))


def _classify(result, collector, nominal, ep_mode, t_final,
              model="sanger", check_qeg=False, env=None, veh=None):
    env = env or EnvironmentParams()
    veh = veh or VehicleParams()
    return V.classify_perturbed_topology(
        model, tuple(nominal), ep_mode, result, collector, t_final,
        env, veh, K, check_qeg_interior=check_qeg)


# ---------------------------------------------------------------------------
# Issue 1: success=False is NOT generic numerical failure (endpoint-scoped)
# ---------------------------------------------------------------------------
def test_success_false_not_automatic_numerical_failure():
    # Qian: success=False (research RTI unresolved), terminal AFTER T,
    # valid fixed-time prefix -> TOPOLOGY_PRESERVED.
    events = [_sw("capture", 50.0)]
    result = _qian_result(700.0, "RTI", events, success=False)
    gate, info = _classify(result, _collector("QEG_GLIDE"),
                           ("qian_capture",), "QEG_GLIDE", 600.0,
                           model="qian")
    assert gate == PRESERVED
    assert info["reason"] == "ok"


def test_success_false_after_t_sanger_preserved():
    events = [_sw("atmosphere_exit", 100.0)]
    result = _sanger_result(1000.0, "srti", events, success=False)
    gate, _ = _classify(result, _collector("SANGER_ATM"),
                        ("sanger_atmosphere_exit",), "SANGER_ATM", 600.0)
    assert gate == PRESERVED


def test_solver_failure_before_t_numerical():
    for kind in ("SOLVER_FAILURE", "solver_failure"):
        result = _qian_result(100.0, kind, [], success=False)
        gate, info = _classify(result, _collector("QEG_GLIDE"),
                               ("qian_capture",), "QEG_GLIDE", 600.0,
                               model="qian")
        assert gate == NUM_ERR
        assert info["reason"] == "solver_failure_before_fixed_endpoint"


def test_ground_terminal_before_t_topology_changed():
    # Qian ground-before-capture
    result = _qian_result(100.0, "GROUND_BEFORE_CAPTURE", [])
    gate, info = _classify(result, _collector("QEG_GLIDE"),
                           ("qian_capture",), "QEG_GLIDE", 600.0,
                           model="qian")
    assert gate == CHANGED
    assert info["reason"] == (
        "terminal_before_fixed_endpoint:GROUND_BEFORE_CAPTURE")
    # Sanger ground-before-srti
    result = _sanger_result(300.0, "ground_before_srti", [])
    gate, info = _classify(result, _collector("SANGER_ATM"),
                           ("sanger_atmosphere_exit",), "SANGER_ATM", 600.0)
    assert gate == CHANGED
    assert info["reason"] == "terminal_before_fixed_endpoint:ground_before_srti"


def test_rti_srti_before_t_topology_changed():
    result = _qian_result(500.0, "RTI", [])
    gate, info = _classify(result, _collector("QEG_GLIDE"),
                           ("qian_capture",), "QEG_GLIDE", 600.0,
                           model="qian")
    assert gate == CHANGED
    assert info["reason"] == "terminal_before_fixed_endpoint:RTI"
    result = _sanger_result(500.0, "srti", [])
    gate, _ = _classify(result, _collector("SANGER_ATM"),
                        ("sanger_atmosphere_exit",), "SANGER_ATM", 600.0)
    assert gate == CHANGED


def test_grazing_before_t_grazing_crossed():
    # KEY regression: grazing_or_unresolved must reach GRAZING_CROSSED,
    # never be swallowed by a generic success=False / solver-failure path.
    result = _sanger_result(500.0, "grazing_or_unresolved_event", [],
                            success=False)
    gate, info = _classify(result, _collector("SANGER_ATM"),
                           ("sanger_atmosphere_exit",), "SANGER_ATM", 600.0)
    assert gate == GRAZING
    assert info["reason"] == "grazing_or_unresolved_before_fixed_endpoint"


def test_censor_before_t_topology_changed():
    for kind in ("MAX_TIME", "max_time", "max_segments"):
        result = _qian_result(300.0, kind, [], success=False)
        gate, info = _classify(result, _collector("QEG_GLIDE"),
                               ("qian_capture",), "QEG_GLIDE", 600.0,
                               model="qian")
        assert gate == CHANGED
        assert info["reason"] == "computational_censor_before_fixed_endpoint"


def test_ambiguous_before_t_topology_changed():
    result = _qian_result(300.0, "AMBIGUOUS_SIMULTANEOUS_EVENT", [],
                          success=False)
    gate, info = _classify(result, _collector("QEG_GLIDE"),
                           ("qian_capture",), "QEG_GLIDE", 600.0,
                           model="qian")
    assert gate == CHANGED
    assert info["reason"] == (
        "ambiguous_simultaneous_event_before_fixed_endpoint")


def test_missing_dense_endpoint_numerical():
    # dense output does NOT cover t_final -> fixed_endpoint_unavailable
    events = [_sw("atmosphere_exit", 100.0)]
    result = _sanger_result(1000.0, "srti", events)
    gate, info = _classify(result, _collector(t_end=100.0),
                           ("sanger_atmosphere_exit",), "SANGER_ATM", 600.0)
    assert gate == NUM_ERR
    assert info["reason"] == "fixed_endpoint_unavailable"


def test_endpoint_mode_changed_topology_changed():
    events = [_sw("atmosphere_exit", 100.0)]
    result = _sanger_result(1000.0, "srti", events)
    gate, info = _classify(result, _collector("SANGER_VAC"),
                           ("sanger_atmosphere_exit",), "SANGER_ATM", 600.0)
    assert gate == CHANGED
    assert info["reason"] == "endpoint_mode_changed"


# ---------------------------------------------------------------------------
# Issue 2: EVENT_ORDER_CHANGED preserves repeated-switch multiplicity
# ---------------------------------------------------------------------------
_SIG4 = ("sanger_atmosphere_exit", "sanger_atmosphere_entry",
         "sanger_atmosphere_exit", "sanger_atmosphere_entry")


def test_same_repeated_signature_preserved():
    events = [_sw("atmosphere_exit", 100.0), _sw("atmosphere_entry", 200.0),
              _sw("atmosphere_exit", 300.0), _sw("atmosphere_entry", 400.0)]
    result = _sanger_result(1000.0, "srti", events)
    gate, _ = _classify(result, _collector("SANGER_ATM"), _SIG4,
                        "SANGER_ATM", 600.0)
    assert gate == PRESERVED


def test_same_multiset_different_order_event_order_changed():
    # (exit, entry, exit, entry) -> (exit, exit, entry, entry)
    events = [_sw("atmosphere_exit", 100.0), _sw("atmosphere_exit", 200.0),
              _sw("atmosphere_entry", 300.0), _sw("atmosphere_entry", 400.0)]
    result = _sanger_result(1000.0, "srti", events)
    gate, info = _classify(result, _collector("SANGER_ATM"), _SIG4,
                           "SANGER_ATM", 600.0)
    assert gate == ORDER
    assert info["reason"] == "event_order_changed"


def test_missing_repeated_pair_topology_changed():
    # nominal (exit, entry, exit, entry) vs perturbed (exit, entry):
    # set() identical but multiplicity differs -> TOPOLOGY_CHANGED,
    # never EVENT_ORDER_CHANGED (the G4R key regression).
    events = [_sw("atmosphere_exit", 100.0), _sw("atmosphere_entry", 200.0)]
    result = _sanger_result(1000.0, "srti", events)
    gate = _classify(result, _collector("SANGER_ATM"), _SIG4,
                     "SANGER_ATM", 600.0)[0]
    assert gate == CHANGED


def test_extra_repeated_pair_topology_changed():
    # nominal (exit, entry) vs perturbed (exit, entry, exit, entry).
    events = [_sw("atmosphere_exit", 50.0), _sw("atmosphere_entry", 100.0),
              _sw("atmosphere_exit", 150.0), _sw("atmosphere_entry", 200.0)]
    result = _sanger_result(1000.0, "srti", events)
    gate = _classify(result, _collector("SANGER_ATM"),
                     ("sanger_atmosphere_exit", "sanger_atmosphere_entry"),
                     "SANGER_ATM", 600.0)[0]
    assert gate == CHANGED


# ---------------------------------------------------------------------------
# Endpoint-scoped helpers contract
# ---------------------------------------------------------------------------
def test_terminal_helpers_read_frozen_metadata():
    q = _qian_result(100.0, "GROUND_BEFORE_CAPTURE", [])
    assert V._trajectory_terminal_kind(q) == "GROUND_BEFORE_CAPTURE"
    assert V._trajectory_terminal_time(q) == 100.0
    s = _sanger_result(300.0, "srti", [])
    assert V._trajectory_terminal_kind(s) == "srti"
    assert V._trajectory_terminal_time(s) == 300.0


def test_success_false_does_not_map_to_failure_kind():
    # RTI reached (terminal after T) => frozen kind stays RTI, not failure.
    events = [_sw("capture", 50.0)]
    result = _qian_result(700.0, "RTI", events, success=False)
    tg, _ = V._classify_terminal_before(result, 600.0)
    assert tg is None  # terminal after T -> no terminal-before gate


# ---------------------------------------------------------------------------
# Snapshot g4r metadata + G4 baseline revalidation
# ---------------------------------------------------------------------------
def test_snapshot_g4r_metadata_present():
    g4r = SNAPSHOT["g4r"]
    assert g4r["endpoint_scoped_terminal_classification"] is True
    assert g4r["success_false_not_equal_numerical_failure"] is True
    assert g4r["event_order_preserves_multiplicity"] is True


def test_snapshot_g4_numerical_results_unchanged():
    # The G4R patch must not alter the recorded numerical payload: the
    # reference-grade FD material errors are still present and below 1e-5.
    for tag, e in SNAPSHOT["endpoints"].items():
        assert e["reference_grade_fd"]["material_rel_error"] < 1e-5, tag
        assert e["reference_convergence"]["status"] == "PASS", tag
    nc = SNAPSHOT["qian_no_saltation_negative_control"]
    assert nc["correct_hybrid_error_vs_FD"] < 1e-3


def test_no_g5_g6_scope_leak():
    # G4R only touches classification routing: no FTLE / SVD / grazing
    # analysis, no hybrid math redefinition.
    src = (Path(__file__).resolve().parents[2] / "src" / "hyptraj" /
           "predictability" / "hybrid_validation.py").read_text(encoding="utf-8")
    for token in ("ftle", "singular_value", "sigma_max", "lyap",
                  "grazing_threshold"):
        assert token not in src, token
    assert "Counter" in src  # multiplicity-preserving event order used
    assert "grazing_or_unresolved" in src  # GRAZING_CROSSED reachable