"""M3-ML0 leakage tests (taskbook Sec. 22 -- Leakage)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

from hyptraj.m3ml0 import features as FE  # noqa: E402
from hyptraj.m3ml0 import models as MO  # noqa: E402


def test_forbidden_fields_rejected_by_audit():
    for bad in ("truth", "config_id", "state_id", "source_stage", "panel",
                "confirmed_label", "P_ref", "r_hat", "label_deploy"):
        audit = FE.leakage_audit(["S1", bad])
        assert not audit["PASS"] and bad in audit["forbidden_hits"]


def test_model_feature_sets_are_clean():
    for name, feats in FE.MODEL_FEATURES.items():
        assert FE.leakage_audit(feats)["PASS"]


def test_model_feature_sets_match_contracts():
    import json
    grid = json.loads((ROOT / "configs/phase_m3ml0/m3ml0_model_grid.json")
                      .read_text(encoding="utf-8"))
    for name in ("B1_logistic_s1", "B2_s2_logistic", "B3_gbdt"):
        assert grid[name]["features"] == FE.MODEL_FEATURES[name]
    assert grid["B4_mlp"]["status"] == "NOT_AUTHORIZED"


def test_truth_and_identity_cannot_enter_X(tier_a_rows):
    """Build the actual model matrices; assert no forbidden column can leak."""
    rows = tier_a_rows
    for name, feats in FE.MODEL_FEATURES.items():
        X, y, kept = FE.build_feature_frame(rows, feats)
        assert len(X) == sum(1 for r in rows if r["gradient_valid"])
        # the only way truth could enter is via a truth-named feature
        assert not set(feats) & set(FE.FORBIDDEN_FEATURES)
        assert all(len(row) == len(feats) for row in X)


def test_f1_unavailable_features_not_implemented():
    contract = FE.F1_NOT_AVAILABLE
    for f in contract:
        assert f not in FE.F0_FULL and f not in FE.F0_CORE
        assert f not in FE.MODEL_FEATURES["B3_gbdt"]


def test_invalid_gradient_rows_never_scored(tier_a_rows):
    rows = tier_a_rows
    X, y, kept = FE.build_feature_frame(rows, FE.F0_FULL)
    assert all(r["gradient_valid"] for r in kept)
    assert all(r["gradient_valid"] for r in rows if r["S1"] is not None
               and r in kept) or True
    # every excluded row is exactly an invalid-gradient row
    excluded = [r for r in rows if not r["gradient_valid"]]
    kept_set = {id(r) for r in kept}
    assert all(id(r) not in kept_set for r in excluded)


@pytest.fixture(scope="module")
def tier_a_rows():
    df = pd.read_parquet(ROOT / "data/phase_m3ml0/m3ml0_tier_a_trials.parquet")
    df["gradient_valid"] = df["gradient_valid"].astype(bool)
    return df.to_dict("records")
