"""M3-ML0 config-grouped deterministic splits (taskbook Sec. 5/18).

The independent unit is the state; all splits are grouped by config_id so
every state and every replicate of a config stays in exactly one fold.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.model_selection import GroupKFold

SEED = 2026


def canonical_order(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["panel"], r["state_id"], r["rep"]))


def grouped_outer_folds(rows: list[dict], n_splits: int = 5) -> list[tuple[list[int], list[int]]]:
    """Deterministic GroupKFold over config_id.

    Rows must already be in canonical order; sklearn GroupKFold is then a
    deterministic function of the group sequence (no shuffling anywhere).
    """
    X = np.zeros((len(rows), 1))
    y = np.array([int(r["label_deploy"]) for r in rows])
    groups = np.array([r["config_id"] for r in rows])
    gkf = GroupKFold(n_splits=n_splits)
    return [(list(tr), list(te)) for tr, te in gkf.split(X, y, groups)]


def grouped_inner_folds(rows: list[dict], indices: list[int], n_splits: int = 4):
    X = np.zeros((len(indices), 1))
    y = np.array([int(rows[i]["label_deploy"]) for i in indices])
    groups = np.array([rows[i]["config_id"] for i in indices])
    gkf = GroupKFold(n_splits=n_splits)
    return [( [indices[j] for j in tr], [indices[j] for j in te] )
            for tr, te in gkf.split(X, y, groups)]


def split_audit(rows: list[dict], folds: list[tuple[list[int], list[int]]]) -> dict:
    """No config overlap train/test; each config in exactly one test fold;
    all replicates of a state stay together."""
    ok = True
    seen_test: set[str] = set()
    state_folds: dict[str, set[int]] = defaultdict(set)
    for k, (tr, te) in enumerate(folds):
        tr_cfg = {rows[i]["config_id"] for i in tr}
        te_cfg = {rows[i]["config_id"] for i in te}
        if tr_cfg & te_cfg:
            ok = False
        dup = te_cfg & seen_test
        if dup:
            ok = False
        seen_test |= te_cfg
        for i in te:
            state_folds[rows[i]["state_id"]].add(k)
    if any(len(v) != 1 for v in state_folds.values()):
        ok = False
    # test folds must partition the full row set exactly once; each fold's
    # train+test must cover every row (train = complement of that fold's test)
    all_test = sorted(i for tr, te in folds for i in te)
    if all_test != list(range(len(rows))):
        ok = False
    for tr, te in folds:
        if sorted(set(tr) | set(te)) != list(range(len(rows))):
            ok = False
    return {
        "n_folds": len(folds),
        "configs_total": len({r["config_id"] for r in rows}),
        "configs_in_test_union": len(seen_test),
        "train_test_config_overlap": 0 if ok else 1,
        "states_spanning_multiple_folds": sum(1 for v in state_folds.values() if len(v) != 1),
        "PASS": ok,
    }
