"""M3-S2F recoverability tests (taskbook Sec. 18 -- Recoverability)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

from hyptraj.m3s2f import recoverability as RC  # noqa: E402


def _rec(**extra):
    g = {"g_hat": 0.1, "g_ci_low": 0.05, "g_ci_high": 0.15,
         "batches": 20, "ESS_grad": 100.0, "valid": True, "seed": 1}
    g.update(extra.pop("gradient", {}))
    return {"state_id": "s", "rep_id": 0, "gradient": g, **extra}


def test_real_records_have_no_batch_families():
    """The audit must detect the actual persisted schema: 0/9 families."""
    paths = (list((ROOT / "results/phase_m3pi1vnr/trials").glob("*/rep0.json"))
             + list((ROOT / "results/phase_m3s1c/trials").glob("*/rep0.json")))
    assert len(paths) == 48
    for p in paths:
        rec = json.loads(p.read_text(encoding="utf-8"))
        a = RC.audit_trial_record(rec)
        assert a["n_persisted"] == 0
        assert a["ci_only"] and a["batches_constant_only"]


def test_audit_detects_batch_fields_when_present():
    rec = _rec(gradient={"batch_g": [0.1] * 20, "batch_signs": [1] * 20})
    a = RC.audit_trial_record(rec)
    assert a["families"]["per_batch_gradient"]
    assert a["families"]["batch_signs"]
    assert a["n_persisted"] >= 2


def test_classification_full_requires_all_families_all_trials():
    leaf = {pats[-1].split(".")[-1]: [1] for _, pats, _ in RC.REQUIRED_FAMILIES}
    full_rec = _rec(gradient=leaf)
    matrix = [RC.audit_trial_record(full_rec) for _ in range(4)]
    matrix = [{"families": m["families"], "n_persisted": m["n_persisted"]}
              for m in matrix]
    assert RC.classify(matrix) == "FULL"


def test_classification_incompatible_when_missing():
    matrix = [{"families": {f: False for f in RC.FAMILIES}, "n_persisted": 0}
              for _ in range(4)]
    assert RC.classify(matrix) == "INCOMPATIBLE"


def test_classification_incompatible_when_partial_single_panel():
    """Families present on some trials only => INCOMPATIBLE, never silently
    reduced (the missing mechanism must be label/panel-independent AND
    uniformly computable; here it is not uniform)."""
    rich = {"families": {f: True for f in RC.FAMILIES}, "n_persisted": 9}
    poor = {"families": {f: False for f in RC.FAMILIES}, "n_persisted": 0}
    assert RC.classify([rich, rich, poor, rich]) == "INCOMPATIBLE"


def test_audit_is_pure_no_simulator_fallback():
    """The audit module must not import or invoke any simulator machinery."""
    src = Path(RC.__file__).read_text(encoding="utf-8")
    for forbidden in ("draw_online_pilot", "gradient_decision",
                      "run_trial_transactional", "subprocess",
                      "np.random", "numpy"):
        assert forbidden not in src


def test_corpus_audit_deterministic():
    paths = (list((ROOT / "results/phase_m3pi1vnr/trials").glob("*/rep0.json"))
             + list((ROOT / "results/phase_m3s1c/trials").glob("*/rep0.json")))
    r1 = RC.audit_corpus(paths)
    r2 = RC.audit_corpus(paths)
    assert r1["classification"] == r2["classification"]
    assert [m["path"] for m in r1["matrix"]] == [m["path"] for m in r2["matrix"]]


def test_missing_source_file_is_incompatible_not_crash(tmp_path):
    """A missing/corrupt corpus cannot be classified; the audit refuses an
    empty matrix rather than silently passing any gate."""
    with pytest.raises(RuntimeError):
        RC.audit_corpus([])
