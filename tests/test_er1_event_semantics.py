from __future__ import annotations

import numpy as np
import pytest

from hyptraj.event_semantics import (
    EVENT_SEMANTICS_SCHEMA_VERSION,
    EventSemanticsError,
    ProposalArm,
    SourceStratum,
    TopologyLabel,
    compute_event_statistics,
    event_indicator_from_topology,
    legacy_event_indicator,
    probability_scale_guard,
    probability_semantics_manifest,
    require_parent_gate,
)


def _fixture():
    return {
        "topology_label": np.array(["S0", "S1", "S0", "S3"], dtype=object),
        "event_indicator": np.array([False, True, False, True]),
        "proposal_arm": ProposalArm("S0"),
        "source_stratum": [SourceStratum(0), SourceStratum(1), SourceStratum(0), SourceStratum(1)],
        "likelihood_ratio": np.array([10.0, 2.0, 7.0, 0.5]),
    }


def test_event_indicator_independent_of_proposal_label():
    fixture = _fixture()
    expected = event_indicator_from_topology(fixture["topology_label"])
    for arm in (ProposalArm("S0"), ProposalArm("A1"), ProposalArm("NOMINAL")):
        fixture["proposal_arm"] = arm
        assert np.array_equal(event_indicator_from_topology(fixture["topology_label"]), expected)


def test_event_indicator_independent_of_source_stratum():
    fixture = _fixture()
    expected = event_indicator_from_topology(fixture["topology_label"])
    fixture["source_stratum"] = [SourceStratum(99)] * 4
    assert np.array_equal(event_indicator_from_topology(fixture["topology_label"]), expected)


def test_nominal_literal_not_event_predicate():
    with pytest.raises(EventSemanticsError):
        legacy_event_indicator(np.array(["S0", "S1"]), nominal_literal="NOMINAL")


def test_s0_literal_not_event_predicate():
    assert ProposalArm("S0") != TopologyLabel.S0
    assert np.array_equal(
        event_indicator_from_topology(np.array(["S0", "S2"])),
        np.array([False, True]),
    )


def test_p_hat_from_authoritative_event_contribution():
    f = _fixture()
    stats = compute_event_statistics(f["event_indicator"], f["likelihood_ratio"])
    assert stats.p_hat == pytest.approx((2.0 + 0.5) / 4.0)


def test_m2_from_authoritative_event_contribution():
    f = _fixture()
    stats = compute_event_statistics(f["event_indicator"], f["likelihood_ratio"])
    assert stats.m2_hat == pytest.approx((4.0 + 0.25) / 4.0)


def test_variance_mass_contract():
    f = _fixture()
    stats = compute_event_statistics(f["event_indicator"], f["likelihood_ratio"])
    assert np.array_equal(stats.variance_mass, np.array([0.0, 4.0, 0.0, 0.25]))


def test_non_event_sample_zero_event_contribution():
    f = _fixture()
    stats = compute_event_statistics(f["event_indicator"], f["likelihood_ratio"])
    assert np.all(stats.contribution[~f["event_indicator"]] == 0.0)


def test_probability_reference_scale():
    assert probability_scale_guard(0.075, 0.0748, standard_error=0.001)
    with pytest.raises(EventSemanticsError):
        probability_scale_guard(1.0, 0.0748, standard_error=0.001)


def test_event_semantics_schema():
    assert EVENT_SEMANTICS_SCHEMA_VERSION == 2
    manifest = probability_semantics_manifest(ProposalArm("A1"), [SourceStratum(0)])
    assert manifest["schema_version"] == 2
    assert manifest["event_definition_id"].endswith("S0-complement")


def test_legacy_semantics_adapter():
    result = legacy_event_indicator(np.array(["S0", "S4"]), nominal_literal="S0")
    assert np.array_equal(result, np.array([False, True]))


def test_ambiguous_legacy_label_rejected():
    with pytest.raises(EventSemanticsError):
        legacy_event_indicator(np.array(["S0", "S1"]), nominal_literal="base")


def test_child_requires_parent_gate():
    require_parent_gate("M3-D", parent_gate_passed=True)
    with pytest.raises(EventSemanticsError):
        require_parent_gate("M3-D", parent_gate_passed=False)
