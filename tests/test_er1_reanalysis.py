"""Tests for the zero-simulator ER-1 archive reanalysis."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "results/evidence_repair/reanalysis"


def _load(stage: str, name: str) -> dict:
    return json.loads((ROOT / stage / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pf2_reanalysis_is_diagnostic_and_zero_simulator() -> None:
    summary = _load("M4-PF2", "pf2_reanalysis_summary.json")
    assert summary["corrected_schema_version"] == 2
    assert summary["state_count"] == 24
    assert summary["extra_simulator_calls"] == 0
    assert summary["corrected_non_event_mass_max"] == 0.0
    assert not summary["final_evaluation_repairable_from_raw"]
    assert not summary["child_authorized"]
    source = REPO / summary["legacy_source_path"]
    assert summary["legacy_source_sha256"] == _sha(source)


def test_pf3_reanalysis_is_diagnostic_and_zero_simulator() -> None:
    summary = _load("M4-PF3", "pf3_reanalysis_summary.json")
    assert summary["corrected_schema_version"] == 2
    assert summary["state_count"] == 24
    assert summary["extra_simulator_calls"] == 0
    assert summary["corrected_non_event_mass_max"] == 0.0
    assert not summary["final_evaluation_repairable_from_raw"]
    assert not summary["child_authorized"]
    source = REPO / summary["legacy_source_path"]
    assert summary["legacy_source_sha256"] == _sha(source)


def test_reanalysis_tables_are_complete_and_provenanced() -> None:
    for stage, filename in (
        ("M4-PF2", "pf2_archive_legacy_vs_corrected.csv"),
        ("M4-PF3", "pf3_archive_legacy_vs_corrected.csv"),
    ):
        with (ROOT / stage / filename).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 24
        assert len({row["state_id"] for row in rows}) == 24
        assert all(row["corrected_schema_version"] == "2" for row in rows)
        assert all(float(row["corrected_non_event_mass_max"]) == 0.0 for row in rows)
        assert all((REPO / row["legacy_source_path"]).is_file() for row in rows)
        assert all(row["legacy_source_sha256"] == _sha(REPO / row["legacy_source_path"])
                   for row in rows)
