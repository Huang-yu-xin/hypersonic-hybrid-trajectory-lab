"""M3-S25-R1-A2R-B0.5 execute-route amendment tests (ZERO scientific
simulator calls).

Background
----------
The Arm-B execute route passed 57/57 preregistration tests yet aborted
on the very first side trial when actually exercised under the human
authorization of 2026-09-09 (commit ``3f86694``).  The pre-sampling
verifiers PASSED (960 centers / 19.2M samples / B0 runtime plan); the
defects were purely mechanical wiring inside ``arm_b_execute``:

1. ``math`` was never imported although the loop calls ``math.exp``.
2. ``run_trial_transactional`` was called with 5 positional arguments
   against a keyword-only signature.
3. The mandatory ``pre_hash_validator`` was omitted, the compute
   callable returned a ``(record, arrays)`` tuple where a dict payload
   is required, and the instrumentation sidecar was never written, so
   ``instrumentation_sha256`` would have stayed null.

Every pre-existing test inspected the route with
``inspect.getsource()`` and never *executed* the trial loop, so none of
this could be caught.

These tests close that gap: they drive the REAL execute route through
the REAL persistence path (temp write -> fsync -> atomic rename ->
bounded directory-fsync retry -> durable hash verification -> ledger
COMPLETE), with the sampling entry point
(``draw_online_pilot``) substituted so that the scientific simulator is
never called.  They therefore assert the wiring, not the physics.

No test here writes into ``results/phase_m3s25r1/arm_b``; the route is
redirected to ``tmp_path``.
"""
from __future__ import annotations

import inspect
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3s25r1 as R  # noqa: E402
from hyptraj.m3s25r1 import arm_b as AB  # noqa: E402

# one LEFT/RIGHT pair sharing a single frozen center CRN anchor
KEEP = ("m3s2s_cfg_001_s2s_0.5708962241|rep0|sideL",
        "m3s2s_cfg_001_s2s_0.5708962241|rep0|sideR")

REAL_ARM_B_DIR = ROOT / "results/phase_m3s25r1/arm_b"

# pytest's tmp_path lives under ...\AppData\Local\Temp\pytest-of-<user>\
# pytest-NNN\<test_name>\ which already eats most of the 220-character
# FULL_PATH_LIMIT once the state slug and the temp basename are appended.
# The persistence layer legitimately refuses those paths BEFORE the
# simulator runs, so the route is redirected to a deliberately short
# scratch directory instead.
SCRATCH = ROOT / ".b05tmp"


@pytest.fixture
def short_tmp():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
        yield SCRATCH
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)


def _substitute_pilot(counter: dict):
    """Deterministic stand-in for the sampling entry point.

    The scientific simulator (``draw_online_pilot``) is the ONLY place
    where samples are drawn; replacing it keeps real sample consumption
    at zero while still exercising the whole downstream pipeline
    (frozen estimator, bit-exact crosscheck, bootstrap, record, sidecar,
    persistence).
    """

    def _fake(st, seed, n_pilot, alpha):
        counter["calls"] += 1
        rng = np.random.default_rng([int(seed), 999])
        n, dim = int(n_pilot), int(st.dim)
        z = rng.standard_normal((n, dim))
        logp = -0.5 * np.einsum("ni,ni->n", z, z)
        logr = np.zeros(n)
        strata = rng.integers(0, 8, size=n)
        return z, logp, logr, strata

    return _fake


def _redirect(monkeypatch, tmp_path, keep=KEEP):
    """Point the execute route at tmp_path and shrink it to ``keep``."""
    monkeypatch.setattr(R, "B0_TRIALS", tmp_path / "trials")
    monkeypatch.setattr(R, "B0_LEDGER", tmp_path / "trial_ledger.jsonl")
    monkeypatch.setattr(R, "B0_SIDE_COUNT", len(keep))

    real_load = R.load

    def _load(p):
        v = real_load(p)
        if Path(p) == Path(R.B0_SEED_MANIFEST):
            v = dict(v)
            units = [u for u in v["units"] if u["unit_id"] in keep]
            assert len(units) == len(keep), "fixture units missing"
            v["units"] = units
            v["n_units"] = len(units)
            v["n_trials"] = len(units)
        return v

    monkeypatch.setattr(R, "load", _load)

    # The two pre-sampling verifiers are covered by their own real-data
    # tests below; here they are stubbed so this test isolates the
    # persistence wiring it is meant to protect.
    monkeypatch.setattr(
        AB, "verify_center_artifacts",
        lambda *a, **k: {"ARM_B_CENTER_VERIFIED": "PASS",
                         "inherited_verified": 269, "a2r_verified": 691,
                         "total_centers": 960,
                         "effective_sample_sum": 19_200_000,
                         "center_seeds": {}})
    monkeypatch.setattr(AB, "verify_arm_b_runtime_plan",
                        lambda *a, **k: {"ARM_B_PLAN_VERIFIED": "PASS"})

    real_gate = R.gate

    def _gate(name):
        if name == "M3_S25_R1_A2R_ARM_B_AUTHORIZED":
            return True
        return real_gate(name)  # old ARM-B / A1R-ARM-B must stay NO

    monkeypatch.setattr(R, "gate", _gate)


# =====================================================================
# the wiring itself
# =====================================================================

def test_b05_execute_route_durable_complete(short_tmp, monkeypatch):
    """Real execute route, real persistence path, zero real samples."""
    units_by_id = {u["unit_id"]: u
                   for u in R.load(R.B0_SEED_MANIFEST)["units"]}
    counter = {"calls": 0}
    monkeypatch.setattr(AB, "draw_online_pilot",
                        _substitute_pilot(counter))
    _redirect(monkeypatch, short_tmp)

    out = R.arm_b_execute()

    assert out["complete"] == 2, out
    assert out["invalid"] == 0, out
    assert out["new"] == 2, out
    assert counter["calls"] == 2  # substitute only; real pilot untouched

    entries = R.ledger_entries(short_tmp / "trial_ledger.jsonl")
    assert sum(1 for e in entries if e["status"] == "STARTED") == 2
    assert sum(1 for e in entries if e["status"] == "COMPLETE") == 2
    assert not [e for e in entries if e["status"] == "CONSUMED_INVALID"]

    seeds = set()
    for uid in KEEP:
        u = units_by_id[uid]
        slug = R.bounded_slug(u["state_id"])
        rec_p = (short_tmp / "trials" / slug
                 / f"rep{u['rep']}_{u['side']}.json")
        sc_p = (short_tmp / "trials" / slug
                / f"rep{u['rep']}_{u['side']}_instrumentation.npz")
        assert rec_p.exists(), f"record missing: {rec_p}"
        assert sc_p.exists(), f"sidecar missing: {sc_p}"

        rec = json.loads(rec_p.read_text(encoding="utf-8"))
        assert rec["schema"] == AB.SIDE_SCHEMA
        assert rec["namespace"] == AB.ARM_B_NAMESPACE
        assert rec["side"] == u["side"]
        assert rec["seed"] == u["seed"]
        assert rec["samples"] == 20_000
        assert rec["delta"] == 0.10
        assert rec["center_unit_id"] == u["center_unit_id"]
        # the sidecar must exist AND be bound into the record
        assert rec["instrumentation_sha256"], "sidecar hash not bound"
        assert R.record_file_hash(sc_p) == rec["instrumentation_sha256"]
        assert "truth" not in rec and not rec.get("confirmed_truth")
        seeds.add(rec["seed"])

    # CRN anchor: LEFT and RIGHT share the frozen center seed
    assert len(seeds) == 1, f"L/R CRN anchor drift: {seeds}"

    # the real result tree must not have been touched
    assert not (REAL_ARM_B_DIR / "trial_ledger.jsonl").exists()
    assert not any((REAL_ARM_B_DIR / "trials").rglob("*")) if (
        REAL_ARM_B_DIR / "trials").exists() else True


def test_b05_sidecar_failure_leaves_no_complete(short_tmp, monkeypatch):
    """If the sidecar cannot be made durable there is no COMPLETE.

    This is the regression guard for the defect where the sidecar was
    never written at all: the route must fail closed rather than emit a
    COMPLETE record with a null instrumentation hash.
    """
    counter = {"calls": 0}
    monkeypatch.setattr(AB, "draw_online_pilot",
                        _substitute_pilot(counter))
    _redirect(monkeypatch, short_tmp)

    def _boom(*a, **k):
        raise RuntimeError("injected sidecar durability failure")

    monkeypatch.setattr(AB, "write_sidecar_transactional", _boom)

    with pytest.raises(RuntimeError, match="CONSUMED_INVALID|COMPLETE"):
        R.arm_b_execute()

    entries = R.ledger_entries(short_tmp / "trial_ledger.jsonl")
    assert not [e for e in entries if e["status"] == "COMPLETE"]
    assert [e for e in entries if e["status"] == "CONSUMED_INVALID"]


def test_b05_gate_no_stops_before_any_trial(short_tmp, monkeypatch):
    """With the gate NO the route must not write anything at all."""
    counter = {"calls": 0}
    monkeypatch.setattr(AB, "draw_online_pilot",
                        _substitute_pilot(counter))
    _redirect(monkeypatch, short_tmp)
    # undo the gate override -> back to the real (NO) gate
    monkeypatch.setattr(R, "gate", R.gate.__wrapped__
                        if hasattr(R.gate, "__wrapped__") else
                        lambda name: False)

    with pytest.raises(RuntimeError, match="not YES"):
        R.arm_b_execute()

    assert counter["calls"] == 0
    assert not (short_tmp / "trial_ledger.jsonl").exists()


# =====================================================================
# the frozen pre-sampling verifiers, on the real full artifacts
# =====================================================================

def test_b05_real_center_artifacts_verifier_passes():
    res = AB.verify_center_artifacts(
        R.load(R.A2R_INHERITANCE)["inherited_units"],
        R.load(R.A2R_SEED_MANIFEST),
        R.ledger_entries(R.A1R_LEDGER),
        R.ledger_entries(R.A2R_LEDGER),
        R.record_file_hash, ROOT)
    assert res["ARM_B_CENTER_VERIFIED"] == "PASS"
    assert res["inherited_verified"] == 269
    assert res["a2r_verified"] == 691
    assert res["total_centers"] == 960
    assert res["effective_sample_sum"] == 19_200_000


def test_b05_real_runtime_plan_verifier_passes():
    res = AB.verify_center_artifacts(
        R.load(R.A2R_INHERITANCE)["inherited_units"],
        R.load(R.A2R_SEED_MANIFEST),
        R.ledger_entries(R.A1R_LEDGER),
        R.ledger_entries(R.A2R_LEDGER),
        R.record_file_hash, ROOT)
    plan = AB.verify_arm_b_runtime_plan(
        R.load(R.B0_SEED_MANIFEST), R.load(R.B0_CONTRACT),
        res["center_seeds"],
        R.load(R.A2R_INHERITANCE)["inherited_units"],
        R.load(R.A2R_SEED_MANIFEST)["units"],
        R.sha(R.B0_SEED_MANIFEST))
    assert plan["ARM_B_PLAN_VERIFIED"] == "PASS"


# =====================================================================
# structural regression guards (cheap, but they pin the exact shape
# that the real-path test above already exercises)
# =====================================================================

def test_b05_math_is_imported():
    assert hasattr(R, "math"), "arm_b_execute needs module-level math"


def test_b05_transaction_call_is_keyword_form():
    src = inspect.getsource(R.arm_b_execute)
    assert "ledger_path=B0_LEDGER" in src
    assert "pre_hash_validator=validate" in src
    assert "write_sidecar_transactional" in src
    assert 'result["status"] != "COMPLETE"' in src
    # the broken positional form must never come back
    assert "B0_LEDGER, _compute" not in src
