"""H3-0 -- RareTopo benchmark definition freeze: schema regression tests.

Validates the machine-readable H3 sample schema v1
(``tests/data/h3_schema_v1.json``) as specified by Task 9:

- required fields of every schema section
- topology label consistency (event / label / switch invariants)
- geometry field availability (ML-B1 first-order geometry)

plus the frozen rules that make H3-0 a definition freeze:

- ground-truth oracle is the exact real hybrid simulator, never ``sign(b)``
- no sampler / estimator / proposal implemented, no dataset generated
- read-only cross-check against the frozen ML-B1 snapshot
  (``tests/data/ml_b1_first_order_geometry_v1.json``): H3 fields must be
  producible by the frozen pipeline without modifying it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "tests" / "data" / "h3_schema_v1.json"
ML_B1_SNAPSHOT_PATH = REPO_ROOT / "tests" / "data" / "ml_b1_first_order_geometry_v1.json"

SCHEMA_VERSION = "h3-sample-schema-v1"
REGIME_RE = re.compile(r"^SRTI_N([0-9]+)$")

#: Phase-G0 switch taxonomy names (frozen; see ML-B1 prior_switch_signature).
ALLOWED_SWITCH_NAMES = ("sanger_atmosphere_exit", "sanger_atmosphere_entry")

INPUT_REQUIRED = ("sample_id", "x0", "delta_x", "whitened_u", "alpha", "uncertainty_scale")
SIMULATOR_REQUIRED = (
    "topology_label",
    "nominal_topology",
    "transition_flag",
    "transition_channel",
    "event_sequence",
    "switch_signature",
    "terminal_state",
    "simulation_status",
)
GEOMETRY_REQUIRED = (
    "margin_b",
    "gradient_a",
    "beta_local",
    "design_direction",
    "u_star",
    "critical_guard",
    "critical_time",
    "d",
)
DIAGNOSTICS_REQUIRED = ("linear_prediction", "true_margin", "geometry_error", "epsilon_geo")
LABEL_REQUIRED = (
    "topology_id",
    "event_sequence",
    "switch_signature",
    "mode_sequence",
    "terminal_event",
    "critical_event",
    "skip_count",
)


def validate_h3_sample_record(rec: dict, schema: dict) -> None:
    """Pure-schema validator for one H3 sample record (no simulation).

    Raises ``ValueError`` on the first violated invariant.
    """
    # -- required fields ------------------------------------------------
    for section, required in (
        ("input", schema["input"]["required"]),
        ("exact_simulator_output", schema["exact_simulator_output"]["required"]),
        ("geometry_information", schema["geometry_information"]["required"]),
        ("nonlinearity_diagnostics", schema["nonlinearity_diagnostics"]["required"]),
    ):
        for f in required:
            if f not in rec:
                raise ValueError(f"missing required field {section}.{f}")
    for f in schema["topology_label_protocol"]["required_fields"]:
        if f not in rec:
            raise ValueError(f"missing required field topology_label.{f}")

    # -- topology label consistency -------------------------------------
    tl = rec["topology_label"]
    nt = rec["nominal_topology"]
    m = REGIME_RE.match(tl)
    if m is None:
        raise ValueError(f"topology_label {tl!r} does not match SRTI_N{{k}}")
    if int(m.group(1)) != rec["skip_count"]:
        raise ValueError(
            f"skip_count {rec['skip_count']} inconsistent with topology_label {tl!r}"
        )
    if bool(rec["transition_flag"]) != (tl != nt):
        raise ValueError(
            f"transition_flag {rec['transition_flag']} inconsistent with "
            f"(topology_label != nominal_topology): {tl!r} vs {nt!r}"
        )
    if rec["transition_flag"] and not rec.get("transition_channel"):
        raise ValueError("transition_flag=True requires a non-empty transition_channel")
    if not rec["transition_flag"] and rec.get("transition_channel") is not None:
        raise ValueError("transition_flag=False requires transition_channel=None")
    if len(rec["mode_sequence"]) != len(rec["switch_signature"]) + 1:
        raise ValueError(
            "mode_count invariant violated: "
            f"len(mode_sequence)={len(rec['mode_sequence'])} != "
            f"len(switch_signature)+1={len(rec['switch_signature']) + 1}"
        )
    for s in rec["switch_signature"]:
        if s not in schema["topology_label_protocol"]["allowed_switch_names"]:
            raise ValueError(f"unknown switch name {s!r}")

    # -- geometry / diagnostics sanity ----------------------------------
    if rec["epsilon_geo"] is not None and rec["epsilon_geo"] < 0:
        raise ValueError("epsilon_geo is a norm and must be >= 0")


def _sample_record_from_anchor(anchor: dict) -> dict:
    """Build a valid H3 sample record from one frozen ML-B1 anchor (read-only)."""
    nom, topo = anchor["nominal"], anchor["topology"]
    ag, gd = anchor["analytic_gradient"], anchor["geometry_direction"]
    signature = list(topo["true_switch_signature"])
    return {
        # input
        "sample_id": f"h3-smoke-{anchor['branch']}_{anchor['side']}-0000",
        "x0": list(nom["initial_state"]),
        "delta_x": [0.0, 0.0, 0.0, 0.0],
        "whitened_u": [0.0, 0.0, 0.0, 0.0],
        "alpha": 1.0,
        "uncertainty_scale": 1.0,
        # exact simulator output
        "topology_label": topo["regime"],
        "nominal_topology": topo["regime"],
        "transition_flag": False,
        "transition_channel": None,
        "event_sequence": list(topo["event_kinds"]),
        "switch_signature": signature,
        "terminal_state": list(nom["x_star"]),
        "simulation_status": "COMPLETE",
        # topology label protocol
        "topology_id": f"{topo['regime']}:{'+'.join(signature) if signature else 'none'}",
        "mode_sequence": ["SANGER_ATM"] * (len(signature) + 1),
        "terminal_event": topo["terminal_kind"],
        "critical_event": "atmosphere_exit",
        "skip_count": topo["skip_count"],
        # geometry information
        "margin_b": nom["b"],
        "gradient_a": list(ag["a_raw"]),
        "beta_local": gd["beta_local"],
        "design_direction": list(gd["v_geom"]),
        "u_star": list(gd["alpha"]),
        "critical_guard": nom["guard_value"],
        "critical_time": nom["t_star"],
        "d": 0.0,
        # nonlinearity diagnostics (smoke values; H3-1 computes real ones)
        "linear_prediction": nom["b"],
        "true_margin": nom["b"],
        "geometry_error": 0.0,
        "epsilon_geo": 0.0,
    }


@pytest.fixture(scope="module")
def schema() -> dict:
    if not SCHEMA_PATH.exists():
        pytest.fail(f"H3 schema not generated: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ml_b1() -> dict:
    if not ML_B1_SNAPSHOT_PATH.exists():
        pytest.skip("ML-B1 snapshot not generated yet")
    return json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Manifest / lifecycle
# ---------------------------------------------------------------------------
class TestSchemaManifest:
    def test_schema_version_and_status(self, schema):
        assert schema["schema_version"] == SCHEMA_VERSION
        assert schema["schema_kind"] == "sample-record-schema"
        assert schema["status"] == "FROZEN"
        assert schema["freeze_stage"] == "H3-0"

    def test_freeze_lifecycle(self, schema):
        lc = schema["lifecycle"]
        assert lc["h3_0_definition_freeze"] is True
        assert lc["dataset_generated"] is False
        assert lc["geometry_is_sampler_implemented"] is False
        assert lc["topology_probability_computed"] is False
        assert "H3-1" in schema["next_stage"]

    def test_success_criteria_complete(self, schema):
        assert set(schema["success_criteria"]) == {
            "rare topology event formally defined",
            "dataset schema frozen",
            "exact oracle defined",
            "geometry error metric defined",
            "evaluation protocol frozen",
            "claim boundaries documented",
        }


# ---------------------------------------------------------------------------
# Event definition (Task 1)
# ---------------------------------------------------------------------------
class TestEventDefinition:
    def test_rare_event_formally_defined(self, schema):
        ev = schema["event_definition"]
        assert ev["random_input"] == "X0 = xbar0 + deltaX0"
        assert ev["uncertainty_law"] == "deltaX0 ~ N(0, P0)"
        assert "N(0, P0)" in ev["uncertainty_law"]
        assert ev["nominal_topology"] == "Z0 = T(xbar0)"
        assert ev["sample_topology"] == "Z = T(X0)"
        assert ev["rare_event"] == "A = {Z != Z0}"

    def test_event_scope_topology_transition_only(self, schema):
        ev = schema["event_definition"]
        assert ev["event_scope"] == "topology transition only"
        for excluded in ("terminal state error", "range error", "energy error"):
            assert excluded in ev["excluded_events"]


# ---------------------------------------------------------------------------
# Required fields (Task 3)
# ---------------------------------------------------------------------------
class TestRequiredFields:
    def test_input_required_fields(self, schema):
        assert tuple(schema["input"]["required"]) == INPUT_REQUIRED

    def test_simulator_output_required_fields(self, schema):
        assert tuple(schema["exact_simulator_output"]["required"]) == SIMULATOR_REQUIRED

    def test_geometry_required_fields(self, schema):
        assert tuple(schema["geometry_information"]["required"]) == GEOMETRY_REQUIRED

    def test_diagnostics_required_fields(self, schema):
        assert tuple(schema["nonlinearity_diagnostics"]["required"]) == DIAGNOSTICS_REQUIRED

    def test_label_protocol_required_fields(self, schema):
        assert tuple(schema["topology_label_protocol"]["required_fields"]) == LABEL_REQUIRED

    def test_every_required_field_has_spec(self, schema):
        for section in ("input", "exact_simulator_output", "geometry_information", "nonlinearity_diagnostics"):
            fields = schema[section]["fields"]
            for name in schema[section]["required"]:
                assert name in fields, f"{section}.{name} required but not specified"
                spec = fields[name]
                assert spec["type"], f"{section}.{name} missing type"
                assert spec["required"] is True, f"{section}.{name} must be required"
                assert spec["description"], f"{section}.{name} missing description"


# ---------------------------------------------------------------------------
# Topology label consistency (Task 2)
# ---------------------------------------------------------------------------
class TestTopologyLabelConsistency:
    def test_minimal_success_failure_label_forbidden(self, schema):
        tlp = schema["topology_label_protocol"]
        assert tlp["forbidden_minimal_label"] == "success/failure only"
        assert "topology transition" in tlp["forbidden_reason"]
        assert tlp["regime_encoding"] == "SRTI_N{skip_count}"

    def test_switch_vocabulary_frozen(self, schema):
        assert tuple(schema["topology_label_protocol"]["allowed_switch_names"]) == ALLOWED_SWITCH_NAMES

    def test_invariants_documented(self, schema):
        tlp = schema["topology_label_protocol"]
        assert tlp["mode_count_invariant"] == "len(mode_sequence) == len(switch_signature) + 1"
        assert tlp["topology_id_encoding"].startswith("<regime>:")

    def test_valid_nominal_record_passes(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B0_N_side"]
        )
        validate_h3_sample_record(rec, schema)  # must not raise

    def test_transition_record_passes_when_consistent(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B1_N1_side"]
        )
        rec["topology_label"] = "SRTI_N3"
        rec["skip_count"] = 3
        rec["transition_flag"] = True
        rec["transition_channel"] = "atmosphere_exit"
        validate_h3_sample_record(rec, schema)  # must not raise

    def test_transition_flag_must_match_labels(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B0_N_side"]
        )
        rec["transition_flag"] = True  # labels unchanged -> inconsistent
        with pytest.raises(ValueError, match="transition_flag"):
            validate_h3_sample_record(rec, schema)

    def test_skip_count_must_match_topology_label(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B0_N_side"]
        )
        rec["skip_count"] = 99
        with pytest.raises(ValueError, match="skip_count"):
            validate_h3_sample_record(rec, schema)

    def test_transition_channel_required_when_flag(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B0_N_side"]
        )
        rec["topology_label"] = "SRTI_N1"
        rec["skip_count"] = 1
        rec["transition_flag"] = True
        rec["transition_channel"] = None
        with pytest.raises(ValueError, match="transition_channel"):
            validate_h3_sample_record(rec, schema)

    def test_mode_count_invariant_enforced(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B0_N_side"]
        )
        rec["mode_sequence"] = []
        with pytest.raises(ValueError, match="mode_count"):
            validate_h3_sample_record(rec, schema)

    def test_unknown_switch_name_rejected(self, schema):
        rec = _sample_record_from_anchor(
            json.loads(ML_B1_SNAPSHOT_PATH.read_text(encoding="utf-8"))["anchors"]["B0_N_side"]
        )
        rec["switch_signature"] = ["not_a_switch"]
        rec["mode_sequence"] = ["SANGER_ATM", "SANGER_VAC"]  # keep length invariant
        with pytest.raises(ValueError, match="unknown switch"):
            validate_h3_sample_record(rec, schema)


# ---------------------------------------------------------------------------
# Geometry field availability (Task 3 / Task 4)
# ---------------------------------------------------------------------------
class TestGeometryAvailability:
    def test_all_geometry_fields_defined(self, schema):
        fields = schema["geometry_information"]["fields"]
        assert set(fields) == set(GEOMETRY_REQUIRED)

    def test_geometry_field_types(self, schema):
        fields = schema["geometry_information"]["fields"]
        assert fields["margin_b"]["type"] == "number"
        assert fields["gradient_a"]["type"] == "array[4]"
        assert fields["beta_local"]["type"] == "number"
        assert fields["design_direction"]["type"] == "array[4]"
        assert fields["u_star"]["type"] == "array[4]"
        assert fields["critical_guard"]["type"] == "number"
        assert fields["critical_time"]["type"] == "number"
        assert fields["d"]["type"] == "number"

    def test_d_is_guard_normal_dot_vector_field(self, schema):
        d_spec = schema["geometry_information"]["fields"]["d"]["description"]
        assert "n^T f" in d_spec
        assert "grazing" in d_spec

    def test_geometry_error_definition(self, schema):
        ged = schema["geometry_error_definition"]
        assert ged["epsilon_geo"] == "epsilon_geo = ||g(x) - g_hat(x)||"
        assert "g_hat(x) = g(x0)" in ged["local_linear_approximation"]
        assert "NOT topology probability" in ged["note"]

    def test_nonlinearity_diagnostics_fields(self, schema):
        fields = schema["nonlinearity_diagnostics"]["fields"]
        assert set(fields) == set(DIAGNOSTICS_REQUIRED)
        assert "epsilon_geo" in fields["epsilon_geo"]["description"]


# ---------------------------------------------------------------------------
# Ground truth protocol (Task 7)
# ---------------------------------------------------------------------------
class TestGroundTruthProtocol:
    def test_oracle_is_exact_simulator(self, schema):
        gt = schema["ground_truth_protocol"]
        assert gt["oracle"] == "exact real hybrid simulator"
        assert gt["indicator"] == "I_A(x) = 1[T(x) != T(xbar)]"

    def test_sign_b_forbidden_as_oracle(self, schema):
        gt = schema["ground_truth_protocol"]
        assert "sign(b) as event oracle" in gt["forbidden"]
        assert "proposal geometry" in gt["forbidden_reason"]


# ---------------------------------------------------------------------------
# Claim boundaries / not implemented (scope)
# ---------------------------------------------------------------------------
class TestClaimBoundaries:
    def test_not_implemented_in_h3_0(self, schema):
        items = set(schema["not_implemented_in_h3_0"]["items"])
        assert items >= {
            "Geometry-IS sampler",
            "Importance sampling estimator",
            "CEM",
            "Flow model",
            "Residual learning",
        }

    def test_not_claimed(self, schema):
        nc = set(schema["claim_boundaries"]["not_claimed"])
        assert nc >= {
            "global optimal IS",
            "all hybrid systems valid",
            "Geometry-IS always superior",
            "topology probability solved",
            "adaptive proposal solved",
        }

    def test_experiment_matrix_frozen(self, schema):
        exps = {e["experiment"]: e["purpose"] for e in schema["experiment_matrix"]["frozen"]}
        assert exps == {
            "Smooth synthetic": "verify theorem limit",
            "Qian hybrid": "single topology transition",
            "Sanger hybrid": "multi-switch topology",
            "Grazing subset": "stress test",
            "Multi-channel subset": "future extension",
        }

    def test_git_rule(self, schema):
        gr = schema["git_rule"]
        assert set(gr["allowed"]) >= {"new docs", "schema", "tests"}
        assert set(gr["forbidden"]) >= {
            "ML-B1 implementation",
            "frozen physics",
            "simulator dynamics",
            "Geometry-IS sampler",
        }


# ---------------------------------------------------------------------------
# Read-only cross-check vs the frozen ML-B1 snapshot (Task 9 geometry fields)
# ---------------------------------------------------------------------------
class TestFrozenMlB1CrossCheck:
    ANCHORS = ("B0_N_side", "B1_N_side", "B1_N1_side", "B2_N_side", "B2_N1_side")

    def test_ml_b1_snapshot_intact(self, ml_b1):
        assert ml_b1["schema_version"] == "ml-b1-first-order-geometry-v1"
        assert ml_b1["status"] == "GENERATED"
        for a in self.ANCHORS:
            assert a in ml_b1["anchors"]

    def test_h3_geometry_fields_producible_by_ml_b1(self, ml_b1):
        # margin_b <- nominal.b ; critical_time <- nominal.t_star ;
        # critical_guard <- nominal.guard_value ; gradient_a <- a_raw ;
        # beta_local / design_direction / u_star <- geometry_direction.
        for a in self.ANCHORS:
            anchor = ml_b1["anchors"][a]
            nom, ag, gd = anchor["nominal"], anchor["analytic_gradient"], anchor["geometry_direction"]
            assert nom["classification"] == "VALID_MARGIN"
            assert nom["b"] is not None and abs(nom["b"]) < 1.0
            assert nom["t_star"] is not None
            assert nom["guard_value"] is not None
            assert len(ag["a_raw"]) == 4
            assert len(gd["v_geom"]) == 4
            assert len(gd["alpha"]) == 4
            # beta_local = b0 / sqrt(a^T P0 a): sign follows the margin
            assert gd["beta_local"] != 0.0
            assert (gd["beta_local"] > 0) == (nom["b"] > 0)

    def test_h3_label_fields_producible_by_ml_b1(self, ml_b1):
        for a in self.ANCHORS:
            topo = ml_b1["anchors"][a]["topology"]
            assert REGIME_RE.match(topo["regime"])
            assert isinstance(topo["skip_count"], int)
            assert isinstance(topo["true_switch_signature"], list)
            assert isinstance(topo["event_kinds"], list)
            assert isinstance(topo["terminal_kind"], str)
            for s in topo["true_switch_signature"]:
                assert s in ALLOWED_SWITCH_NAMES

    def test_n_star_and_x_star_available_for_d(self, ml_b1):
        # d = n^T f is a derived H3 quantity; the frozen snapshot must carry
        # n_star and x_star so H3-1 can compute it without re-running ML-B1.
        for a in self.ANCHORS:
            nom = ml_b1["anchors"][a]["nominal"]
            assert len(nom["n_star"]) == 4
            assert len(nom["x_star"]) == 4

    def test_schema_accepts_every_frozen_anchor_record(self, schema, ml_b1):
        for a in self.ANCHORS:
            validate_h3_sample_record(_sample_record_from_anchor(ml_b1["anchors"][a]), schema)


# ---------------------------------------------------------------------------
# Protocol intact (H3-0 must not have started production H3 work)
# ---------------------------------------------------------------------------
class TestProtocolIntact:
    def test_h3_not_started_flags(self):
        from hyptraj.uncertainty import protocol

        assert protocol.PHASE_H0_DONE
        assert not protocol.TOPOLOGY_PROBABILITY_COMPUTED
