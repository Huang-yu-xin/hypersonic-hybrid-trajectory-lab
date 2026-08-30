"""M3-CA source lock and mutation-firewall tests."""

from __future__ import annotations

import json
from pathlib import Path

from hyptraj.m3ca.provenance import (
    SOURCE_SPECS,
    build_source_manifest,
    verify_source_manifest,
)

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "results" / "phase_m3ca" / "summary" / \
    "m3ca_source_manifest.json"


def test_m3ca_source_hashes():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert verify_source_manifest(REPO, manifest) == []
    assert manifest["sources_unchanged"] is True


def test_m3ca_source_manifest_complete():
    generated = build_source_manifest(REPO)
    assert generated["source_count"] == len(SOURCE_SPECS)
    assert {s["path"] for s in generated["sources"]} == {
        spec[0] for spec in SOURCE_SPECS
    }
    assert all(s["read_only"] for s in generated["sources"])


def test_m3ca_no_new_seed_generation():
    code = "\n".join(p.read_text(encoding="utf-8") for p in
                     (REPO / "src" / "hyptraj" / "m3ca").glob("*.py"))
    assert "default_rng" not in code
    assert "SeedSequence" not in code


def test_m3ca_no_proposal_or_budget_mutation():
    lock = json.loads((REPO / "configs" / "phase_m3ca" /
                       "m3ca_analysis_lock.json").read_text(encoding="utf-8"))
    assert lock["extra_simulator_calls"] == 0
    assert lock["pilot_n"] == 20000
    assert lock["eval_n"] == 100000
    assert "proposal_changes" in lock["forbidden"]
    assert "budget_changes" in lock["forbidden"]
