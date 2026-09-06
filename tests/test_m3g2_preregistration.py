"""G2-0 firewall tests: no online controller trial is run here."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from hyptraj.m3g2.policy import ABSTAIN, SHRINK, WIDEN, decide_from_gradient

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3g2" / "summary"
CONFIG = REPO / "configs" / "phase_m3g2"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m3g2_parent_m3ds():
    source = load(SUMMARY / "m3g2_source_manifest.json")
    parent = source["parent_audit"]
    assert parent["tag_commit"].startswith("feb32ab")
    assert parent["m3ds_verdict"] == "M3DS-A"
    assert parent["directional_primary"] == "8W/8S"
    assert parent["safety_primary"] == "3 HOLD/2 AMBIGUOUS"


def test_m3g2_zero_sim_prereg():
    source = load(SUMMARY / "m3g2_source_manifest.json")
    hashes = load(SUMMARY / "m3g2_prereg_hashes.json")
    assert source["zero_simulator"] == {"extra_simulator_calls": 0,
                                         "controller_online_trials": 0}
    assert hashes["controller_online_trials"] == 0
    assert hashes["extra_simulator_calls"] == 0


def test_m3g2_benchmark_hash_and_counts():
    manifest = load(SUMMARY / "m3g2_benchmark_manifest.json")
    origin = REPO / manifest["origin"]["path"]
    assert sha(origin) == manifest["origin"]["sha256"]
    assert manifest["counts"] == {"directional_primary": 16,
                                  "safety_primary": 5,
                                  "directional_reserve": 6}


def test_m3g2_policy_hashes_lock_current_configs():
    hashes = load(SUMMARY / "m3g2_prereg_hashes.json")
    for name, stem in (("policy", "m3g2_policy.json"),
                       ("gates", "m3g2_gates.json"),
                       ("seeds", "m3g2_seeds.json"),
                       ("protocol", "m3g2_protocol.json")):
        assert hashes[name] == sha(CONFIG / stem)


def test_m3g2_action_definition_corrected():
    policy = load(CONFIG / "m3g2_policy.json")
    action = policy["action_definitions"]
    assert action["widen"]["delta_theta"] == 0.2
    assert action["shrink"]["delta_theta"] == -0.2
    assert action["base"]["meaning"] == "ABSTAIN fallback"


def test_m3g2_abstain_not_truth_class():
    manifest = load(SUMMARY / "m3g2_benchmark_manifest.json")
    assert manifest["abstention"]["is_ground_truth_class"] is False
    assert manifest["abstention"]["fallback"] == "BASE"


def test_m3g2_historical_empirical_not_autoinherited():
    audit = load(SUMMARY / "m3g2_inheritance_audit.json")
    assert set(audit["reject"]) >= {"gain_gate", "GA1", "rho"}
    assert audit["unclear"] == []
    assert "GA1" in load(CONFIG / "m3g2_policy.json")["forbidden"]


def test_m3g2_inheritance_inventory():
    rows = (SUMMARY / "m3g2_controller_component_inventory.csv").read_text(
        encoding="utf-8")
    assert "gradient estimator" in rows
    assert "gain gate" in rows
    assert "I-C" in rows


def test_m3g2_corrected_gradient_source():
    policy = load(CONFIG / "m3g2_policy.json")
    assert policy["gradient_source"]["module"] == \
        "hyptraj.m3d.adaptation.gradient_decision"
    assert policy["gradient_source"]["sign_convention"] == \
        "g_ci_high < 0 => WIDEN; g_ci_low > 0 => SHRINK"


def test_m3g2_seed_disjoint_namespace():
    seeds = load(CONFIG / "m3g2_seeds.json")
    assert seeds["namespace"] == "M3-G2-ONLINE"
    assert set(seeds["disjoint_from"]) >= {"ER1", "D2", "D3", "M3-DS"}
    assert seeds["replicates_per_state"] == 8


def test_m3g2_no_benchmark_tuning():
    policy = load(CONFIG / "m3g2_policy.json")
    protocol = load(CONFIG / "m3g2_protocol.json")
    assert "reference truth in online policy" in policy["forbidden"]
    assert "benchmark tuning" in protocol["prohibited"]
    assert protocol["human_freeze_required"] is True


def test_m3g2_policy_semantics_and_no_oracle_argument():
    assert decide_from_gradient({"g_hat": -1, "g_ci_low": -2,
                                 "g_ci_high": -0.1, "ESS_grad": 30})[
        "action"] == WIDEN
    assert decide_from_gradient({"g_hat": 1, "g_ci_low": 0.1,
                                 "g_ci_high": 2, "ESS_grad": 30})[
        "action"] == SHRINK
    assert decide_from_gradient({"g_hat": 0, "g_ci_low": -1,
                                 "g_ci_high": 1, "ESS_grad": 30})[
        "action"] == ABSTAIN
    assert decide_from_gradient({"g_hat": 1, "g_ci_low": .1,
                                 "g_ci_high": 2, "ESS_grad": 19})[
        "reason"] == "LOW_ESS"
    invalid = {"g_hat": 1, "g_ci_low": .1, "g_ci_high": 2,
               "ESS_grad": 30, "problems": ["non-finite probability"]}
    assert decide_from_gradient(invalid)["reason"] == "INVALID"
    assert "truth" not in inspect.signature(decide_from_gradient).parameters


def test_m3g2_policy_deterministic():
    gradient = {"g_hat": -1.0, "g_ci_low": -2.0,
                "g_ci_high": -0.1, "ESS_grad": 50.0}
    assert decide_from_gradient(gradient) == decide_from_gradient(gradient)


def test_m3g2_rarity_and_m3q_blocked():
    audit = load(SUMMARY / "m3g2_inheritance_audit.json")
    assert audit["firewalls"]["rarity_shift"] == "BLOCKED"
    assert audit["firewalls"]["m3_q"] == "BLOCKED"


def test_m3g2_source_manifest_integrity():
    manifest = load(SUMMARY / "m3g2_source_manifest.json")
    for entry in manifest["entries"]:
        assert sha(REPO / entry["path"]) == entry["sha256"], entry["path"]
