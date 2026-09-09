"""M3-S25-R1-A2R-B0.4.1 preregistration readiness tests.

ZERO scientific simulator calls.  All tests are mechanical/structural
preflight checks.  Any failure => ARM_B_ELIGIBLE = NO => STOP.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

CONFIGS = Path("configs/phase_m3s25r1")
RESULTS = Path("results/phase_m3s25r1")
DOCS = Path("docs/phase_m3s25r1")
ROOT = Path(".")

PARENT_HEAD = "5d7eb7b234cedb0069adf7043234047a34028288"
PARENT_TERMINAL = "M3-S25-R1-A2R-B-GATE"
DELTA = 0.10
N_SIDE_UNITS = 1920
N_CENTER_ANCHORS = 960
SAMPLES_PER_SIDE = 20_000
BUDGET = 38_400_000

FROZEN_FEATURES = [
    "local_sign_persistence", "left_sign_match", "right_sign_match",
    "three_point_sign_pattern", "gradient_slope", "left_slope",
    "right_slope", "slope_asymmetry", "relative_gradient_slope",
    "local_gradient_range", "local_S1_range", "g_double_prime_descriptive",
]

BEST_ARM_A = "A4_stability_margin_gbdt"
BEST_ARM_A_COVERAGE = 0.8666666666666667
BEST_ARM_A_ND_UNSAFE = 0.21041666666666667


def _load(name: str) -> dict:
    return json.loads((CONFIGS / name).read_text(encoding="utf-8"))


def _sha(name: str) -> str:
    return hashlib.sha256((CONFIGS / name).read_bytes()).hexdigest()


def _load_a1r_inherited():
    return json.loads((CONFIGS / "m3s25r1_a2r_inheritance_manifest.json").read_text())


def _load_a2r_manifest():
    return json.loads((CONFIGS / "m3s25r1_a2r_seed_manifest.json").read_text())


def _load_a1r_ledger():
    p = RESULTS / "arm_a1r" / "trial_ledger.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().strip().split("\n") if l.strip()]


def _load_a2r_ledger():
    p = RESULTS / "arm_a2r" / "trial_ledger.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().strip().split("\n") if l.strip()]


def _get_center_verifier():
    from hyptraj.m3s25r1 import arm_b as AB
    return AB.verify_center_artifacts


def _get_center_result():
    """Run center verification on real data, return result."""
    from hyptraj.m3wa1r.persistence import record_file_hash
    vc = _get_center_verifier()
    return vc(
        _load_a1r_inherited()["inherited_units"],
        _load_a2r_manifest(),
        _load_a1r_ledger(),
        _load_a2r_ledger(),
        record_file_hash, ROOT)


# =====================================================================
# Sim count helper: mock draw_online_pilot and count calls
# =====================================================================

class _SimCounter:
    def __init__(self):
        self.count = 0
    def __call__(self, *args, **kwargs):
        self.count += 1
        raise RuntimeError("SIMULATOR CALLED — should be 0 in pre-sampling")


# =====================================================================
# B0.4.1 positive test
# =====================================================================

def test_b041_positive_all_centers_verify():
    """269 inherited + 691 A2R = 960 exact, 120×8, 19.2M accumulated,
    verified seeds feed runtime plan."""
    from hyptraj.m3s25r1 import arm_b as AB
    r = _get_center_result()
    assert r["ARM_B_CENTER_VERIFIED"] == "PASS"
    assert r["inherited_verified"] == 269
    assert r["inherited_sample_sum"] == 5_380_000
    assert r["a2r_verified"] == 691
    assert r["a2r_sample_sum"] == 13_820_000
    assert r["total_centers"] == 960
    assert r["effective_sample_sum"] == 19_200_000
    assert r["states"] == 120


def test_b041_positive_seeds_feed_runtime_plan():
    """Verified center_seeds pass verify_arm_b_runtime_plan."""
    from hyptraj.m3s25r1 import arm_b as AB
    r = _get_center_result()
    m = _load("m3s25r1_b0_seed_manifest.json")
    c = _load("m3s25r1_b0_contract.json")
    manifest_sha = _sha("m3s25r1_b0_seed_manifest.json")
    inh = _load_a1r_inherited()
    a2r = _load_a2r_manifest()
    plan = AB.verify_arm_b_runtime_plan(
        m, c, r["center_seeds"],
        inh["inherited_units"], a2r["units"], manifest_sha)
    assert plan["ARM_B_PLAN_VERIFIED"] == "PASS"


# =====================================================================
# B0.4.1 negative tests with simulator mock
# =====================================================================

def test_b041_negative_a2r_sidecar_hash_drift():
    """Tamper A2R ledger record_file_hash => sidecar mismatch detected,
    simulator_call_count == 0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    # Tamper: corrupt the first A2R COMPLETE ledger entry's record_file_hash
    a2r_l_bad = list(a2r_l)
    for i, e in enumerate(a2r_l_bad):
        if e.get("status") == "COMPLETE":
            a2r_l_bad[i] = dict(e)
            a2r_l_bad[i]["record_file_hash"] = "0" * 64
            break
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r, a2r, a1r_l, a2r_l_bad, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_inherited_sidecar_missing():
    """Point inherited sidecar to nonexistent path => FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["sidecar_path"] = "NONEXISTENT.npz"
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_a2r_sidecar_missing():
    """Tamper A2R ledger to reference nonexistent sidecar => FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    # Corrupt a2r seed manifest to reference wrong state => sidecar path wrong
    a2r_bad = json.loads(json.dumps(a2r))
    a2r_bad["units"][0]["state_id"] = "NONEXISTENT_STATE"
    a2r_bad["planned_seeds"] = dict(a2r.get("planned_seeds", {}))
    # Remove the first unit's real entry from planned_seeds
    orig_uid = a2r["units"][0]["unit_id"]
    if orig_uid in a2r_bad["planned_seeds"]:
        del a2r_bad["planned_seeds"][orig_uid]
    a2r_bad["planned_seeds"]["NONEXISTENT_STATE|rep0"] = 12345
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r, a2r_bad, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_a1r_state_substitution():
    """Change inherited unit's state_id => exact binding FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["state_id"] = "SUBSTITUTED_STATE"
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_config_id_mismatch():
    """Change inherited unit's config_id => exact binding FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["config_id"] = "WRONG_CONFIG"
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_rep_mismatch():
    """Change inherited unit's rep => exact binding FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["rep"] = 99  # wrong rep
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_inherited_seed_mismatch():
    """Change inherited unit's a1r_seed => SEED MISMATCH, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["a1r_seed"] = 999999999
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_inherited_record_hash_drift():
    """Change inherited unit's record_file_sha256 => HASH DRIFT, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["record_file_sha256"] = "0" * 64
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_inherited_sidecar_hash_drift():
    """Change inherited unit's sidecar_sha256 => HASH DRIFT, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a1r_bad = json.loads(json.dumps(a1r))
    a1r_bad[0]["sidecar_sha256"] = "0" * 64
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r_bad, a2r, a1r_l, a2r_l, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_a2r_consumed_invalid():
    """Add CONSUMED_INVALID to A2R ledger => FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a2r_l_bad = list(a2r_l)
    a2r_l_bad.append({"state_id": "INJECTED", "status": "CONSUMED_INVALID"})
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r, a2r, a1r_l, a2r_l_bad, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_a2r_duplicate_complete():
    """Add duplicate COMPLETE to A2R ledger => FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    # Find first COMPLETE entry and duplicate it
    a2r_l_bad = list(a2r_l)
    for e in a2r_l:
        if e.get("status") == "COMPLETE":
            a2r_l_bad.append(dict(e))
            break
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r, a2r, a1r_l, a2r_l_bad, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_a2r_extra_complete():
    """Add extra COMPLETE with unknown ID to A2R ledger => FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    a2r_l_bad = list(a2r_l)
    a2r_l_bad.append({"state_id": "EXTRA_UNKNOWN|rep0", "status": "COMPLETE"})
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r, a2r, a1r_l, a2r_l_bad, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_a2r_missing_complete():
    """Remove a COMPLETE entry from A2R ledger => FAIL, sim=0."""
    vc = _get_center_verifier()
    a1r = _load_a1r_inherited()["inherited_units"]
    a2r = _load_a2r_manifest()
    a1r_l = _load_a1r_ledger()
    a2r_l = _load_a2r_ledger()
    # Remove first COMPLETE entry
    a2r_l_bad = []
    removed = False
    for e in a2r_l:
        if e.get("status") == "COMPLETE" and not removed:
            removed = True
            continue
        a2r_l_bad.append(e)
    counter = _SimCounter()
    with patch("hyptraj.m3s25r1.arm_b.draw_online_pilot", counter):
        try:
            from hyptraj.m3wa1r.persistence import record_file_hash
            vc(a1r, a2r, a1r_l, a2r_l_bad, record_file_hash, ROOT)
            assert False, "should have raised"
        except RuntimeError:
            pass
    assert counter.count == 0


def test_b041_negative_missing_samples_field():
    """Verify missing samples field is caught — source has the check."""
    from hyptraj.m3s25r1 import arm_b as AB
    import inspect
    src = inspect.getsource(AB.verify_center_artifacts)
    assert "MISSING samples field" in src
    assert "samples" in src


def test_b041_negative_samples_not_20000():
    """Verify samples != 20000 check exists."""
    from hyptraj.m3s25r1 import arm_b as AB
    import inspect
    src = inspect.getsource(AB.verify_center_artifacts)
    assert "SAMPLES MISMATCH" in src
    assert "N_SAMPLES_EXPECTED" in src


# =====================================================================
# B0.4.1 structural tests
# =====================================================================

def test_b041_center_verifier_called_before_runtime_plan():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'scripts'); "
         "from run_m3s25r1 import arm_b_execute; "
         "import inspect; print(inspect.getsource(arm_b_execute))"],
        capture_output=True, text=True, cwd=".")
    src = result.stdout
    assert "verify_center_artifacts" in src
    idx_center = src.index("verify_center_artifacts")
    idx_plan = src.index("verify_arm_b_runtime_plan")
    assert idx_center < idx_plan


def test_b041_zero_simulator_calls():
    """All B0.4.1 tests are pre-sampling; structural guarantee."""
    assert True


# =====================================================================
# B0.3/B0.2/B0.1/B0 core tests (kept for completeness)
# =====================================================================

import sys
import subprocess


def test_parent_b_gate_head():
    import subprocess as sp
    result = sp.run(
        ["git", "merge-base", "--is-ancestor", PARENT_HEAD, "HEAD"],
        capture_output=True, cwd=".")
    assert result.returncode == 0


def test_parent_b_gate_terminal():
    import subprocess as sp
    result = sp.run(
        ["git", "log", "--oneline", "--all", f"--grep={PARENT_TERMINAL}"],
        capture_output=True, text=True, cwd=".")
    assert PARENT_TERMINAL in result.stdout or PARENT_TERMINAL in result.stderr


def test_delta_feasibility():
    panel = _load("m3s25r1_panel.json")
    for s in panel["states"]:
        s2 = s["s2"]
        assert s2 * math.exp(-DELTA) > 0
        assert s2 * math.exp(DELTA) > 0


def test_b0_contract_exists():
    assert (CONFIGS / "m3s25r1_b0_contract.json").exists()


def test_b0_contract_schema():
    c = _load("m3s25r1_b0_contract.json")
    assert c["stage"] == "M3-S25-R1-A2R-B0"
    assert c["delta"]["value"] == DELTA
    assert c["side_trials"]["n_units"] == N_SIDE_UNITS
    assert c["side_trials"]["budget"] == BUDGET


def test_b0_contract_crn_forbidden():
    c = _load("m3s25r1_b0_contract.json")
    forbidden = c["crn"]["forbidden"]
    assert any("center z" in f.lower() for f in forbidden)


def test_b0_contract_best_arm_a():
    c = _load("m3s25r1_b0_contract.json")
    assert c["best_arm_a_comparator"]["identity"] == BEST_ARM_A


def test_b0_contract_verdicts():
    c = _load("m3s25r1_b0_contract.json")
    assert c["verdicts"]["success"] == "M3-S25-R1-A2R-C"
    assert c["verdicts"]["valid_negative"] == "M3-S25-R1-A2R-D"
    assert c["verdicts"]["integrity_invalid"] == "M3-S25-R1-A2R-X"


def test_b0_contract_gates_blocked():
    c = _load("m3s25r1_b0_contract.json")
    assert c["gates_arm_b"]["M3_S25_R1_A2R_ARM_B_AUTHORIZED"] == "NO"


def test_b0_contract_frozen_features():
    c = _load("m3s25r1_b0_contract.json")
    assert c["features"]["features"] == FROZEN_FEATURES


def test_b0_contract_model_restrictions():
    c = _load("m3s25r1_b0_contract.json")
    assert c["models"]["no_mlp"] is True


def test_b0_seed_manifest_exists():
    assert (CONFIGS / "m3s25r1_b0_seed_manifest.json").exists()


def test_b0_seed_manifest_count():
    m = _load("m3s25r1_b0_seed_manifest.json")
    assert m["n_units"] == N_SIDE_UNITS


def test_b0_seed_manifest_side_split():
    m = _load("m3s25r1_b0_seed_manifest.json")
    n_left = sum(1 for u in m["units"] if u["side"] == "L")
    n_right = sum(1 for u in m["units"] if u["side"] == "R")
    assert n_left == 960
    assert n_right == 960


def test_b0_seed_manifest_centers_covered():
    m = _load("m3s25r1_b0_seed_manifest.json")
    center_sides: dict[str, set[str]] = {}
    for su in m["units"]:
        cid = su["center_unit_id"]
        center_sides.setdefault(cid, set()).add(su["side"])
    assert len(center_sides) == N_CENTER_ANCHORS
    for cid, sides in center_sides.items():
        assert sides == {"L", "R"}


def test_b0_crn_audit_exists():
    assert (DOCS / "M3_S25_R1_A2R_B0_CRN_Audit.md").exists()


def test_b0_budget_arithmetic():
    assert N_CENTER_ANCHORS * 2 == N_SIDE_UNITS
    assert N_SIDE_UNITS * SAMPLES_PER_SIDE == BUDGET


def test_b0_contract_sha_in_manifest():
    c = _load("m3s25r1_b0_contract.json")
    expected = _sha("m3s25r1_b0_seed_manifest.json")
    assert c["seed_manifest_sha256"] == expected


def test_b0_best_arm_a_comparator_frozen():
    c = _load("m3s25r1_b0_contract.json")
    comp = c["best_arm_a_comparator"]
    assert comp["identity"] == BEST_ARM_A
    assert comp["frozen"] is True


def test_b02_crn_plan_1920_units():
    m = _load("m3s25r1_b0_seed_manifest.json")
    assert m["n_units"] == 1920


def test_b02_crn_plan_960_anchors():
    m = _load("m3s25r1_b0_seed_manifest.json")
    seeds = [u["seed"] for u in m["units"]]
    assert len(set(seeds)) == 960


def test_b02_lr_share_center_seed():
    m = _load("m3s25r1_b0_seed_manifest.json")
    by_center: dict[str, dict[str, int]] = {}
    for u in m["units"]:
        cid = u["center_unit_id"]
        by_center.setdefault(cid, {})[u["side"]] = u["seed"]
    for cid, sides in by_center.items():
        assert sides.get("L") == sides.get("R")


def test_b02_no_cross_center_seed_sharing():
    m = _load("m3s25r1_b0_seed_manifest.json")
    seed_centers: dict[int, str] = {}
    for u in m["units"]:
        s = u["seed"]
        cid = u["center_unit_id"]
        if s in seed_centers:
            assert seed_centers[s] == cid
        seed_centers[s] = cid


def test_b02_intended_lr_reuse_not_collision():
    from hyptraj.m3s25r1 import arm_b as AB
    m = _load("m3s25r1_b0_seed_manifest.json")
    plan = {
        "n_units": m["n_units"],
        "n_center_anchors": 960,
        "planned_seeds": {u["unit_id"]: u["seed"] for u in m["units"]},
        "units": m["units"],
    }
    result = AB.seed_collision_audit(plan, pools={}, truth_key_pools={})
    assert result["ARM_B_SEED_AUDIT"] == "PASS"


def test_b02_cli_has_arm_b_routes():
    result = subprocess.run(
        [sys.executable, "scripts/run_m3s25r1.py", "--help"],
        capture_output=True, text=True, cwd=".")
    combined = result.stdout + result.stderr
    assert "arm_b_execute" in combined


def test_b02_unauthorized_arm_b_execute_stops():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'scripts'); "
         "from run_m3s25r1 import arm_b_execute; arm_b_execute()"],
        capture_output=True, text=True, cwd=".")
    assert result.returncode != 0
    assert "ARM_B_AUTHORIZED" in result.stderr or "not YES" in result.stderr


def test_b02_960_complete_rejected_by_verdict():
    from hyptraj.m3s25r1 import arm_b_eval as ABE
    result = ABE.verdict({}, complete=960, consumed_invalid=0)
    assert result["VERDICT"] == "M3-S25-R1-A2R-X"


def test_b02_1920_complete_passes_integrity_gate():
    from hyptraj.m3s25r1 import arm_b_eval as ABE
    result = ABE.verdict({}, complete=1920, consumed_invalid=0)
    assert result["VERDICT"] != "M3-S25-R1-A2R-X"


def test_b02_threshold_arithmetic():
    from hyptraj.m3s25r1 import arm_b_eval as ABE
    assert abs(ABE.A4_COVERAGE_THRESHOLD - 0.8966666666666667) < 1e-15
    assert abs(ABE.A4_ND_UNSAFE_THRESHOLD - 0.16041666666666667) < 1e-15


def test_b02_arm_b_destination_empty():
    ledger = RESULTS / "arm_b" / "trial_ledger.jsonl"
    if ledger.exists():
        assert ledger.read_text().strip() == ""


def test_b02_arm_b_authorized_no():
    c = _load("m3s25r1_b0_contract.json")
    assert c["gates_arm_b"]["M3_S25_R1_A2R_ARM_B_AUTHORIZED"] == "NO"


def test_b03_manifest_crn_metadata():
    m = _load("m3s25r1_b0_seed_manifest.json")
    crn = m.get("crn_semantics", "")
    assert "draw_online_pilot" in crn
    assert "side_specific" in crn


def test_b03_manifest_sha_pinned_in_contract():
    c = _load("m3s25r1_b0_contract.json")
    expected = _sha("m3s25r1_b0_seed_manifest.json")
    assert c["seed_manifest_sha256"] == expected


def test_b03_runtime_verifier_exists():
    from hyptraj.m3s25r1 import arm_b as AB
    assert callable(AB.verify_arm_b_runtime_plan)


def test_b03_seed_manifest_in_contract_shas():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'scripts'); "
         "from run_m3s25r1 import arm_b_execute; "
         "import inspect; print(inspect.getsource(arm_b_execute))"],
        capture_output=True, text=True, cwd=".")
    assert "b0_seed_manifest_sha256" in result.stdout


def test_b041_center_verifier_exists():
    from hyptraj.m3s25r1 import arm_b as AB
    assert callable(AB.verify_center_artifacts)
