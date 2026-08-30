"""PF2 frozen protocol, anchor, factorial and output tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal
from hyptraj.m4pf1.experiment import tail_diagnostics
from hyptraj.m4pf2.experiment import (
    anchor_proposal,
    build_factorial_cells,
    factorial_contrasts,
    load_locks,
    select_freeoracle,
    validate_state_lock,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf2" / "summary"
PROTOCOL, STATE_LOCK, SEEDS = load_locks(REPO)


class DummyState:
    component_index = 0
    s2 = 1.3
    dim = 2

    def proposal(self):
        return CovGaussianMixtureProposal(
            centers=np.array([[0.0, 0.0], [2.0, -1.0]]),
            weights=np.array([0.55, 0.45]),
            covs=(self.s2*np.eye(2), np.eye(2)),
            component_mode_ids=("new", "old"))


def _summary() -> dict:
    path = SUMMARY / "m4pf2_family_summary.json"
    if not path.exists():
        pytest.skip("PF2 confirmation output not generated yet")
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict]:
    path = SUMMARY / name
    if not path.exists():
        pytest.skip("PF2 confirmation output not generated yet")
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_m4pf2_protocol_frozen():
    assert tuple(PROTOCOL["cells"]) == ("P00", "P10", "P01", "P11")
    assert PROTOCOL["mean_update"]["delta_mu_mahalanobis"] == 0.2
    assert PROTOCOL["covariance_update"]["eta_sigma"] == 0.2
    assert PROTOCOL["covariance_update"]["rank"] == 1


def test_m4pf2_state_lock():
    assert len(validate_state_lock(REPO, STATE_LOCK)) == 24


def test_m4pf2_seed_lock():
    discovery = set(SEEDS["discovery"]["gradient_seeds"])
    confirmation = set(SEEDS["confirmation"]["gradient_seeds"])
    pf1 = {40001, 40002, 41001, 41002, 41003, 41004}
    assert discovery.isdisjoint(confirmation)
    assert discovery.isdisjoint(pf1)
    assert confirmation.isdisjoint(pf1)


def test_m4pf2_anchor_identity():
    state = DummyState()
    widen = anchor_proposal(state, "widen")
    shrink = anchor_proposal(state, "shrink")
    assert np.allclose(widen.covs[0], state.s2*np.exp(0.2)*np.eye(2))
    assert np.allclose(shrink.covs[0], state.s2*np.exp(-0.2)*np.eye(2))
    assert np.array_equal(widen.centers, state.proposal().centers)


def test_m4pf2_rank1_covariance_reuse():
    state = DummyState()
    anchor = anchor_proposal(state, "widen")
    cells, record = build_factorial_cells(
        state, anchor, np.array([1.0, -0.3]),
        np.diag([-2.0, 0.4]), PROTOCOL)
    assert record["covariance"]["rank"] == 1
    assert not np.allclose(cells["P01"].covs[0], anchor.covs[0])
    assert np.allclose(cells["P10"].covs[0], anchor.covs[0])


def test_m4pf2_joint_update_semantics():
    state = DummyState()
    anchor = anchor_proposal(state, "shrink")
    cells, record = build_factorial_cells(
        state, anchor, np.array([0.5, 1.0]),
        np.array([[0.7, 0.2], [0.2, -0.1]]), PROTOCOL)
    assert np.allclose(cells["P11"].centers, cells["P10"].centers)
    assert np.allclose(cells["P11"].covs[0], cells["P01"].covs[0])
    assert record["joint_gradient_recomputed"] is False
    assert record["joint_application"] == "simultaneous"


def test_m4pf2_spd():
    state = DummyState()
    cells, record = build_factorial_cells(
        state, anchor_proposal(state, "widen"), np.array([1.0, 1.0]),
        np.array([[1.0, 0.4], [0.4, -0.2]]), PROTOCOL)
    assert record["valid"]
    assert all(np.linalg.eigvalsh(cell.covs[0]).min() > 0 for cell in cells.values())


def test_m4pf2_condition_number_guard():
    state = DummyState()
    protocol = json.loads(json.dumps(PROTOCOL))
    protocol["covariance_update"]["condition_number_ceiling"] = 1.01
    with pytest.raises(ValueError, match="condition-number"):
        build_factorial_cells(
            state, anchor_proposal(state, "widen"), np.array([1.0, 0.0]),
            np.diag([-2.0, 0.4]), protocol)


def test_m4pf2_freeoracle_formula():
    records = {cell: [{"M2": value}, {"M2": value+0.1}]
               for cell, value in zip(("P00", "P10", "P01", "P11"),
                                      (5.0, 3.0, 4.0, 2.0))}
    assert select_freeoracle(records, {cell: 0.1 for cell in records}) == "P11"
    tied = {cell: [{"M2": 2.0}] for cell in records}
    assert select_freeoracle(tied, {cell: 0.1 for cell in tied}) == "P00"


def test_m4pf2_factorial_contrasts():
    rows = [{"state_id": "s", "action_class": "WIDEN", "cell": cell,
             "VRF_budget": value}
            for cell, value in zip(("P00", "P10", "P01", "P11"),
                                   (1.0, 2.0, 4.0, 16.0))]
    result = factorial_contrasts(rows)[0]
    assert np.isclose(result["mean_effect_without_covariance"], np.log(2))
    assert np.isclose(result["mean_effect_with_covariance"], np.log(4))
    assert np.isclose(result["interaction"], np.log(2))


def test_m4pf2_tail_schema():
    result = tail_diagnostics(np.array([0.0, 1.0, 2.0]))
    assert {"ESS", "max_normalized_weight", "top_1pct_weight_mass",
            "top_0_1pct_weight_mass", "nonfinite_weights"} == set(result)


def test_m4pf2_p00_reproduction():
    summary = _summary()
    assert summary["p00_reproduction"]["pass"] is True


def test_m4pf2_cost_accounting():
    rows = _csv("m4pf2_cost_ledger.csv")
    deployable = [r for r in rows if r["record_type"] == "counterfactual_deployable"]
    audit = [r for r in rows if r["record_type"].startswith("AUDIT_")]
    assert len(deployable) == 24
    assert all(int(r["deployable_cost"]) == 100000 for r in deployable)
    assert sum(int(r["audit_only_cost"]) for r in audit) == 122600000


def test_m4pf2_state_count_and_class_split():
    rows = _csv("m4pf2_state_table.csv")
    assert len(rows) == 96
    assert len({r["state_id"] for r in rows}) == 24
    p00 = [r for r in rows if r["cell"] == "P00"]
    assert sum(r["action_class"] == "WIDEN" for r in p00) == 12
    assert sum(r["action_class"] == "SHRINK" for r in p00) == 12


def test_m4pf2_output_schema():
    summary = _summary()
    assert summary["schema_version"] == "raretopo-m4pf2-family-summary-v0"
    assert summary["verdict"] in {"PF2-A", "PF2-B", "PF2-C", "PF2-D"}
    assert len(summary["cells"]) == 4
