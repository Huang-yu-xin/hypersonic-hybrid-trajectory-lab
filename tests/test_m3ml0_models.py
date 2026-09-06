"""M3-ML0 model tests (taskbook Sec. 22 -- Model)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

from hyptraj.m3ml0 import evaluation as EV  # noqa: E402
from hyptraj.m3ml0 import features as FE  # noqa: E402
from hyptraj.m3ml0 import models as MO  # noqa: E402
from hyptraj.m3ml0 import splits as SP  # noqa: E402


@pytest.fixture(scope="module")
def rows():
    df = pd.read_parquet(ROOT / "data/phase_m3ml0/m3ml0_tier_a_trials.parquet")
    df["gradient_valid"] = df["gradient_valid"].astype(bool)
    rows = SP.canonical_order(df.to_dict("records"))
    for r in rows:
        r["_fr"] = FE.feature_row(r)
        r["_X"] = {name: [r["_fr"][f] for f in feats]
                   for name, feats in FE.MODEL_FEATURES.items()}
    return rows


def test_s1_baseline_reproducible(rows):
    m1 = EV.evaluate_policy(rows, EV.s1_frozen_deploy(rows))
    m2 = EV.evaluate_policy(rows, EV.s1_frozen_deploy(rows))
    assert m1 == m2
    # frozen S1 on the combined exposed dataset reproduces the recorded audit
    assert abs(m1["deployable_coverage"] - 0.859375) < 1e-12
    assert abs(m1["nd_unsafe"] - 0.2109375) < 1e-12
    assert m1["wrong"] == 0
    assert m1["truth_HOLD"]["unsafe"] == 0.0
    assert abs(m1["truth_AMBIGUOUS"]["unsafe"] - 0.375) < 1e-12


def test_s1_threshold_is_frozen_constant():
    assert EV.S1_THRESHOLD == 5.4417199447782


def test_logistic_deterministic(rows):
    folds = SP.grouped_outer_folds(rows, n_splits=5)
    r1 = MO.nested_cv_eval("B1_logistic_s1", [dict(r) for r in rows], folds)
    r2 = MO.nested_cv_eval("B1_logistic_s1", [dict(r) for r in rows], folds)
    assert r1["oof_deploy"] == r2["oof_deploy"]
    assert r1["oof_prob"] == r2["oof_prob"]


def test_gbdt_deterministic(rows):
    folds = SP.grouped_outer_folds(rows[:192], n_splits=3)
    r1 = MO.nested_cv_eval("B3_gbdt", [dict(r) for r in rows[:192]], folds)
    r2 = MO.nested_cv_eval("B3_gbdt", [dict(r) for r in rows[:192]], folds)
    assert r1["oof_deploy"] == r2["oof_deploy"]


def test_mlp_blocked_below_100_states(rows):
    n_states = len({(r["panel"], r["state_id"]) for r in rows})
    assert n_states == 48
    assert not MO.mlp_authorized(n_states)
    assert MO.mlp_authorized(100)


def test_invalid_gradient_rows_abstain_in_every_policy(rows):
    s1_dep = EV.s1_frozen_deploy(rows)
    for r, d in zip(rows, s1_dep):
        if not r["gradient_valid"]:
            assert d is False


def test_oof_metrics_recorded_consistent(rows):
    import json
    rec = json.loads((ROOT / "results/phase_m3ml0/summary/m3ml0_oof_metrics.json")
                     .read_text(encoding="utf-8"))
    for name in ("B1_logistic_s1", "B2_s2_logistic", "B3_gbdt"):
        m = rec["candidates"][name]["metrics"]
        assert m["trials"] == 384
        assert 0.0 <= m["deployable_coverage"] <= 1.0
        assert 0.0 <= m["nd_unsafe"] <= 1.0
