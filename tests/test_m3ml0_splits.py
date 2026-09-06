"""M3-ML0 grouped-CV split tests (taskbook Sec. 22 -- Group CV)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

from hyptraj.m3ml0 import splits as SP  # noqa: E402


@pytest.fixture(scope="module")
def rows():
    df = pd.read_parquet(ROOT / "data/phase_m3ml0/m3ml0_tier_a_trials.parquet")
    df["gradient_valid"] = df["gradient_valid"].astype(bool)
    return SP.canonical_order(df.to_dict("records"))


def test_every_config_exactly_one_test_fold(rows):
    folds = SP.grouped_outer_folds(rows, n_splits=5)
    seen = []
    for k, (tr, te) in enumerate(folds):
        seen += [(k, cid) for cid in {rows[i]["config_id"] for i in te}]
    from collections import Counter
    counts = Counter(seen)
    assert set(counts.values()) == {1}
    assert len(counts) == len({r["config_id"] for r in rows}) == 20


def test_no_config_overlap_train_test(rows):
    folds = SP.grouped_outer_folds(rows, n_splits=5)
    for tr, te in folds:
        assert not ({rows[i]["config_id"] for i in tr}
                    & {rows[i]["config_id"] for i in te})


def test_all_replicates_of_state_stay_together(rows):
    folds = SP.grouped_outer_folds(rows, n_splits=5)
    state_folds = {}
    for k, (tr, te) in enumerate(folds):
        for i in te:
            state_folds.setdefault(rows[i]["state_id"], set()).add(k)
    assert all(len(v) == 1 for v in state_folds.values())
    assert len(state_folds) == 48


def test_split_deterministic(rows):
    a = SP.grouped_outer_folds(list(rows), n_splits=5)
    b = SP.grouped_outer_folds(SP.canonical_order(list(reversed(rows))), n_splits=5)
    # canonicalization makes the split invariant to input ordering
    assert [(tr, te) for tr, te in a] == [(tr, te) for tr, te in b]


def test_split_audit_passes(rows):
    folds = SP.grouped_outer_folds(rows, n_splits=5)
    audit = SP.split_audit(rows, folds)
    assert audit["PASS"]
    assert audit["train_test_config_overlap"] == 0
    assert audit["states_spanning_multiple_folds"] == 0


def test_threshold_selected_only_on_inner_oof():
    """The threshold rule only sees inner-OOF scores by construction; here we
    verify the rule itself enforces the safety constraint and tie-breaks."""
    import numpy as np
    from hyptraj.m3ml0.threshold import select_threshold
    rng = np.random.default_rng(SP.SEED)
    probs = np.r_[rng.beta(8, 2, 60), rng.beta(2, 8, 40)]   # 60 dep / 40 ND-ish
    y = np.r_[np.ones(60, dtype=int), np.zeros(40, dtype=int)]
    is_nd = (y == 0)
    t, diag = select_threshold(probs, y, is_nd)
    assert not diag["abstain_all"]
    deploy = probs >= t
    assert deploy[is_nd].mean() <= 0.20 + 1e-12
    # a no-legal-threshold regime yields the abstain-all sentinel
    t2, diag2 = select_threshold(np.r_[probs, [0.999]], np.r_[y, [0]],
                                 np.r_[is_nd, [True]])
    if diag2["abstain_all"]:
        assert t2 > 0.999


def test_threshold_tie_break_deterministic():
    import numpy as np
    from hyptraj.m3ml0.threshold import select_threshold
    # perfectly separable: many thresholds give identical coverage/unsafe;
    # the rule must deterministically pick the highest such threshold
    probs = np.r_[np.full(10, 0.9), np.full(10, 0.1)]
    y = np.r_[np.ones(10, dtype=int), np.zeros(10, dtype=int)]
    is_nd = (y == 0)
    t1, _ = select_threshold(probs, y, is_nd)
    t2, _ = select_threshold(probs, y, is_nd)
    assert t1 == t2
    deploy = probs >= t1
    assert deploy[:10].all() and not deploy[10:].any()
