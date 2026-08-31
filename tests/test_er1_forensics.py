from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results/evidence_repair/summary"


def _json(name: str):
    return json.loads((SUMMARY / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_er1_zero_simulator_forensics():
    assert _json("er1_source_manifest.json")["extra_simulator_calls"] == 0
    assert _json("er1_raw_repairability.json")["extra_simulator_calls"] == 0


def test_er1_source_hashes():
    manifest = _json("er1_source_manifest.json")
    assert manifest["sources_unchanged"] is True
    for source in manifest["sources"]:
        assert _sha(REPO / source["path"]) == source["sha256"]


def test_er1_contamination_boundary():
    boundary = _json("er1_contamination_boundary.json")
    assert boundary["last_known_clean_commit"].startswith("098fbc1")
    assert boundary["first_known_contaminated_commit"].startswith("0f6cdfe")
    assert boundary["first_known_contaminated_stage"] == "M3-v0 empirical scalar benchmark"
    assert boundary["confidence"] == "HIGH"


def test_er1_dependency_graph_complete():
    graph = _json("er1_dependency_graph.json")
    stages = [node["stage"] for node in graph["nodes"]]
    for required in ("M3-v0 empirical", "M3-D", "M3-G-v1", "M3-BV/BV2",
                     "M3-CA", "M4-PF0 theory", "M4-PF1", "M4-PF2",
                     "M4-PF3-0/PF3", "M5-AR parent freeze"):
        assert required in stages
    assert graph["child_requires_corrected_parent_gate"] is True


def test_er1_no_historical_tag_move():
    manifest = _json("er1_source_manifest.json")
    assert manifest["historical_tags_mutated"] is False
    for tag, commit in manifest["historical_tags"].items():
        live = subprocess.check_output(["git", "rev-list", "-n", "1", tag],
                                       cwd=REPO, text=True).strip()
        assert live == commit


def test_er1_corrected_schema_version():
    protocol = json.loads((REPO / "configs/evidence_repair/er1_protocol.json").read_text(encoding="utf-8"))
    lineage = _json("er1_final_lineage.json")
    assert protocol["event_semantics_schema_version"] == 2
    assert lineage["event_semantics_schema_version"] == 2


def test_er1_supersession_ledger():
    ledger = _json("er1_supersession_ledger.json")
    assert len(ledger) >= 13
    assert any(row["historical_tag"] == "RareTopo-M2-v0" and row["semantic_status"] == "VALID" for row in ledger)
    assert any(row["historical_tag"] == "RareTopo-M3-v0" and row["semantic_status"].startswith("SUPERSEDED") for row in ledger)


def test_er1_metric_impact_has_required_metrics():
    with (SUMMARY / "er1_metric_impact.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    metrics = {row["metric"] for row in rows}
    assert {"P_hat", "M2", "VRF_proposal", "VRF_budget", "ESS",
            "action label", "gradient sign", "gradient magnitude",
            "Oracle action", "BestFixed", "headroom", "FreeOracle",
            "coverage U99/U999", "allocation mismatch", "birth score"} <= metrics


def test_er1_raw_repairability_requires_m3_replay():
    audit = _json("er1_raw_repairability.json")
    assert audit["new_simulation_required"] is True
    assert audit["first_required_stage"] == "M3-v0"


def test_er1_output_schema():
    required = {
        "er1_source_manifest.json", "er1_contamination_boundary.json",
        "er1_dependency_graph.json", "er1_metric_impact.csv",
        "er1_raw_repairability.json", "er1_supersession_ledger.json",
        "er1_final_lineage.json",
    }
    assert required <= {path.name for path in SUMMARY.iterdir()}
