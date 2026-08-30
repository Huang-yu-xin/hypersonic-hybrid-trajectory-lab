"""M4-PF1 protocol, arithmetic, accounting and output tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from hyptraj.m2.covariance_policy import CovGaussianMixtureProposal
from hyptraj.m4pf1.experiment import (
    build_structured_proposal,
    freeoracle_candidate,
    load_locks,
    tail_diagnostics,
    validate_state_lock,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf1" / "summary"
PROTOCOL, STATE_LOCK, SEEDS = load_locks(REPO)


class DummyState:
    component_index = 0

    def proposal(self):
        return CovGaussianMixtureProposal(
            centers=np.array([[0.0, 0.0], [1.0, 1.0]]),
            weights=np.array([0.6, 0.4]),
            covs=(np.eye(2), np.eye(2)),
            component_mode_ids=("a", "b"))


def _summary_json() -> dict:
    path = SUMMARY / "m4pf1_family_summary.json"
    if not path.exists():
        pytest.skip("PF1 confirmation output not generated yet")
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict]:
    path = SUMMARY / name
    if not path.exists():
        pytest.skip("PF1 confirmation output not generated yet")
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_m4pf1_protocol_frozen():
    assert PROTOCOL["parent_tag"] == "RareTopo-M4-PF0-v0"
    assert PROTOCOL["families"].keys() == {"S0", "S1", "S2"}
    assert PROTOCOL["primary_endpoint"]["name"] == \
        "median_state_FreeOracle_VRF_budget"


def test_m4pf1_state_lock():
    rows = validate_state_lock(REPO, STATE_LOCK)
    assert len(rows) == 24


def test_m4pf1_seed_lock():
    discovery = set(SEEDS["discovery"]["gradient_seeds"])
    confirmation = set(SEEDS["confirmation"]["gradient_seeds"])
    assert discovery.isdisjoint(confirmation)
    assert len(confirmation) == 4


def test_m4pf1_rank1_update():
    proposal, record = build_structured_proposal(
        DummyState(), np.diag([-2.0, 0.5]), 1, PROTOCOL["update"])
    assert record["rank"] == 1
    assert not np.allclose(proposal.covs[0], np.eye(2))
    assert np.isclose(np.linalg.eigvalsh(proposal.covs[0])[0], 1.0)


def test_m4pf1_rank2_update():
    proposal, record = build_structured_proposal(
        DummyState(), np.diag([-2.0, 0.5]), 2, PROTOCOL["update"])
    assert record["rank"] == 2
    assert np.linalg.matrix_rank(proposal.covs[0] - np.eye(2)) == 2


def test_m4pf1_spd():
    proposal, record = build_structured_proposal(
        DummyState(), np.array([[1.0, 0.7], [0.7, -1.0]]), 2,
        PROTOCOL["update"])
    assert record["valid"]
    assert np.linalg.eigvalsh(proposal.covs[0]).min() > 0.0


def test_m4pf1_condition_number_guard():
    lock = dict(PROTOCOL["update"])
    lock["condition_number_ceiling"] = 1.01
    with pytest.raises(ValueError, match="condition-number"):
        build_structured_proposal(DummyState(), np.diag([-2.0, 0.5]), 2, lock)


def test_m4pf1_no_posthoc_rank_change():
    assert PROTOCOL["families"]["S1"]["rank"] == 1
    assert PROTOCOL["families"]["S2"]["rank"] == 2
    with pytest.raises(ValueError, match="only rank"):
        build_structured_proposal(DummyState(), np.eye(2), 3,
                                  PROTOCOL["update"])


def test_m4pf1_no_posthoc_eta_change():
    assert PROTOCOL["update"]["eta"] == 0.2
    assert PROTOCOL["update"]["max_abs_log_step"] == 0.2


def test_m4pf1_freeoracle_formula():
    candidates = {
        "base": [{"M2": 4.0}, {"M2": 5.0}],
        "structured": [{"M2": 2.0}, {"M2": 3.0}],
    }
    assert freeoracle_candidate(candidates, {"base": 0.1,
                                             "structured": 0.1}) == "structured"
    tied = {"base": [{"M2": 2.0}], "structured": [{"M2": 2.0}]}
    assert freeoracle_candidate(tied, {"base": 0.1,
                                       "structured": 0.1}) == "base"


def test_m4pf1_tail_schema():
    result = tail_diagnostics(np.array([0.0, 1.0, 2.0, 3.0]))
    assert set(result) == {"ESS", "max_normalized_weight",
                           "top_1pct_weight_mass", "top_0_1pct_weight_mass",
                           "nonfinite_weights"}
    assert 0.0 <= result["max_normalized_weight"] <= 1.0


def test_m4pf1_scalar_baseline_reproduction():
    summary = _summary_json()
    assert summary["scalar_anchor_pass"] is True
    assert summary["scalar_replay_max_abs_m2_error"] <= 5.1e-9


def test_m4pf1_cost_accounting():
    rows = _csv("m4pf1_cost_ledger.csv")
    assert len(rows) == 72
    assert all(int(row["pilot_cost"]) == 0 for row in rows)
    assert all(int(row["decision_cost"]) == 0 for row in rows)
    assert all(int(row["deployable_cost"]) == 100000 for row in rows)


def test_m4pf1_state_count_and_class_split():
    rows = _csv("m4pf1_state_table.csv")
    assert len(rows) == 72
    unique_states = {row["state_id"] for row in rows}
    assert len(unique_states) == 24
    s0 = [row for row in rows if row["family"] == "S0"]
    assert sum(row["action_class"] == "WIDEN" for row in s0) == 12
    assert sum(row["action_class"] == "SHRINK" for row in s0) == 12


def test_m4pf1_output_schema():
    summary = _summary_json()
    assert summary["schema_version"] == "raretopo-m4pf1-family-summary-v0"
    assert summary["verdict"] in {"PF1-A", "PF1-B", "PF1-C", "PF1-D"}
    assert len(summary["families"]) == 3

