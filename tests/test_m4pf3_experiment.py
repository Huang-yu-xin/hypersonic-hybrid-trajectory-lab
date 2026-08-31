import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from hyptraj.m4pf3.experiment import (
    allocation_step,
    build_allocation_arms,
    load_locks,
    p11_anchor,
    select_freeoracle,
    validate_state_lock,
)


REPO = Path(__file__).resolve().parents[1]
PROTOCOL, STATE_LOCK, SEEDS = load_locks(REPO)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pf2_first_state():
    raw = json.loads((
        REPO / "results/phase_m4pf2/m4pf2_confirmation_raw.json"
    ).read_text(encoding="utf-8"))
    return raw["states"][0]


def test_m4pf3_parent_pf2_freeze():
    peeled = subprocess.run(
        ["git", "rev-parse", "RareTopo-M4-PF2-v0^{}"], cwd=REPO,
        check=True, capture_output=True, text=True).stdout.strip()
    assert peeled == "82e6f36438fa1db6cf0b10055c16b573c07dd6b9"


def test_m4pf3_protocol_frozen_sources():
    route = PROTOCOL["routing"]
    anchor = PROTOCOL["anchor"]
    assert sha256(REPO / route["source"]) == route["source_sha256"]
    assert sha256(REPO / anchor["source"]) == anchor["source_sha256"]
    assert route["locked_route"] == "A"


def test_m4pf3_state_lock():
    rows = validate_state_lock(REPO, STATE_LOCK)
    assert len(rows) == 24
    assert sum(row["class"] == "WIDEN" for row in rows) == 12
    assert sum(row["class"] == "SHRINK" for row in rows) == 12


def test_m4pf3_seed_lock():
    pf2 = json.loads((
        REPO / "configs/phase_m4pf2/m4pf2_seeds.json"
    ).read_text(encoding="utf-8"))
    pf3_values = set(SEEDS["discovery"]["gradient_seeds"])
    pf3_values.update(SEEDS["confirmation"]["gradient_seeds"])
    pf2_values = set(pf2["discovery"]["gradient_seeds"])
    pf2_values.update(pf2["confirmation"]["gradient_seeds"])
    assert pf3_values.isdisjoint(pf2_values)
    assert set(SEEDS["discovery"]["gradient_seeds"]).isdisjoint(
        SEEDS["confirmation"]["gradient_seeds"])


def test_m4pf3_anchor_p11():
    row = pf2_first_state()
    anchor = p11_anchor(row)
    k = int(row["proposal_identity"]["component_index"])
    expected_center = (
        np.asarray(row["proposal_identity"]["centers"])[k]
        + np.asarray(row["update"]["mean"]["displacement"]))
    assert np.allclose(anchor.centers[k], expected_center)
    assert np.allclose(anchor.covs[k],
                       row["update"]["covariance"]["covariance"])
    assert np.allclose(anchor.weights, row["proposal_identity"]["weights"])


def test_m4pf3_fresh_gradient_if_anchor_changed():
    assert PROTOCOL["anchor"]["fresh_gradient_construction_required"] is True
    assert PROTOCOL["anchor"]["S0_gradient_reuse_forbidden"] is True
    assert PROTOCOL["gradient_construction"]["pooled_samples_per_state"] == 400000


def test_m4pf3_weight_update_simplex():
    update = allocation_step(np.asarray([0.7, 0.3]),
                             np.asarray([-0.2, 0.2]))
    assert np.isclose(update["alpha_prime"].sum(), 1.0)
    assert np.all(update["alpha_prime"] > 0.0)
    assert np.isclose(update["delta_beta_norm"], 0.20)


def test_m4pf3_weight_update_descent_direction():
    direction = np.asarray([-0.2, 0.2])
    update = allocation_step(np.asarray([0.7, 0.3]), direction)
    assert update["direction_dot_delta_beta"] > 0.0
    assert -update["direction_dot_delta_beta"] < 0.0


def test_m4pf3_weight_update_identity_on_zero():
    alpha = np.asarray([0.7, 0.3])
    update = allocation_step(alpha, np.zeros(2))
    assert np.array_equal(update["alpha_prime"], alpha)
    assert update["allocation_update_skipped_numerical_zero"] is True


def test_m4pf3_no_birth_arm():
    assert PROTOCOL["routing"]["birth_authorized"] is False
    assert set(PROTOCOL["arms"]) == {"A0", "A1"}
    assert "birth arm" in PROTOCOL["forbidden"]


def test_m4pf3_build_arms_changes_weights_only():
    anchor = p11_anchor(pf2_first_state())
    direction = np.asarray([-0.1, 0.1])
    arms, update = build_allocation_arms(
        anchor, {"descent_direction": direction}, PROTOCOL)
    assert np.array_equal(arms["A0"].centers, arms["A1"].centers)
    assert all(np.array_equal(a, b)
               for a, b in zip(arms["A0"].covs, arms["A1"].covs))
    assert not np.array_equal(arms["A0"].weights, arms["A1"].weights)
    assert update["TV_alpha_prime_alpha"] > 0.0


def test_m4pf3_cost_accounting_lock():
    confirmation = PROTOCOL["confirmation"]
    assert confirmation["deployable_selected_arm_budget"] == 100000
    per_state_audit = (
        PROTOCOL["gradient_construction"]["pooled_samples_per_state"]
        + confirmation["new_A1_probability_characterization_n"]
        + len(PROTOCOL["arms"])
        * confirmation["evaluation_replicates"]
        * confirmation["evaluation_n_per_arm_replicate"])
    assert per_state_audit == 2_500_000


def test_m4pf3_freeoracle_formula():
    records = {
        "A0": [{"M2": 5.0}, {"M2": 6.0}],
        "A1": [{"M2": 4.0}, {"M2": 4.5}],
    }
    assert select_freeoracle(records, {"A0": 1.0, "A1": 1.0}) == "A1"
    assert select_freeoracle(records, {"A0": 1.0, "A1": 0.1}) == "A1"


def test_m4pf3_confirmation_lock():
    confirmation = PROTOCOL["confirmation"]
    assert confirmation["state_count"] == 24
    assert confirmation["class_split"] == {"WIDEN": 12, "SHRINK": 12}
    assert confirmation["evaluation_replicates"] == 8
    assert confirmation["evaluation_n_per_arm_replicate"] == 100000


def test_m4pf3_output_schema_if_present():
    path = REPO / "results/phase_m4pf3/summary/m4pf3_family_summary.json"
    if not path.exists():
        return
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["state_count"] == 24
    assert set(row["arm"] for row in summary["arms"]) == {"A0", "A1"}
    assert summary["verdict"] in {"PF3-A", "PF3-C", "PF3-D", "PF3-E"}
