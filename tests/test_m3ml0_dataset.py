"""M3-ML0 dataset tests (taskbook Sec. 22 -- Dataset)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(ROOT := Path(__file__).resolve().parents[1]))

from hyptraj.m3ml0 import dataset as DS  # noqa: E402


@pytest.fixture(scope="module")
def tier_a():
    return pd.read_parquet(ROOT / "data/phase_m3ml0/m3ml0_tier_a_trials.parquet")


def test_exactly_48_states_384_trials(tier_a):
    assert len(tier_a) == 384
    assert tier_a.groupby(["panel", "state_id"]).ngroups == 48


def test_two_sources_24_states_each(tier_a):
    counts = tier_a.groupby("panel")["state_id"].nunique()
    assert counts["pi1vnr"] == 24 and counts["s1c"] == 24
    assert tier_a.groupby("panel").size()["pi1vnr"] == 192
    assert tier_a.groupby("panel").size()["s1c"] == 192


def test_no_duplicate_state_replicate(tier_a):
    assert not tier_a.duplicated(subset=["panel", "state_id", "rep"]).any()


def test_replicates_per_state(tier_a):
    counts = tier_a.groupby(["panel", "state_id"]).size()
    assert (counts == 8).all()


def test_only_valid_durable_complete_rows(tier_a):
    dur = DS.durable_complete_check()
    assert dur["pi1vnr"] == {"complete": 192, "consumed_invalid": 0, "unique": 192}
    assert dur["s1c"] == {"complete": 192, "consumed_invalid": 0, "unique": 192}


def test_source_hashes_match_frozen_anchors(tier_a):
    assert (DS.sha(DS.PI1VNR_SUM / "m3pi1vnr_fresh_development_panel.csv")
            == DS.EXPECTED_PANEL_SHA["pi1vnr"])
    panel = DS.json_load(S1C_PANEL := DS.S1C_CFG / "m3s1c_panel.json")
    assert panel["sha256"] == DS.sha(
        ROOT / "results/phase_m3s1c/preflight/m3s1c_panel.csv")


def test_no_protected_18_overlap(tier_a):
    protected = {r["state_id"] for r in DS.protected_reserve_18()}
    assert len(protected) == 18
    assert not (protected & set(tier_a["state_id"]))


def test_labels_frozen_semantics(tier_a):
    dep = tier_a["truth"].isin(("WIDEN", "SHRINK"))
    assert (tier_a.loc[dep, "label_deploy"] == 1).all()
    assert (tier_a.loc[~dep, "label_deploy"] == 0).all()


def test_truth_matches_panel_manifest(tier_a):
    panel = DS.json_load(DS.S1C_CFG / "m3s1c_panel.json")
    s1c_truth = {s["state_id"]: s["truth"] for s in panel["states"]}
    sub = tier_a[tier_a["panel"] == "s1c"]
    assert all(s1c_truth[r.state_id] == r.truth for r in sub.itertuples())
