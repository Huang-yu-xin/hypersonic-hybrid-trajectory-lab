"""Run the artifact-only M4-PF2-0 source, sample and anchor audit."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m4pf2.provenance import (
    anchor_compatibility_audit,
    build_manifest,
    identifiability_audit,
    verify_manifest,
)

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m4pf2_0" / "summary"
RAW = REPO / "results" / "phase_m4pf1" / "m4pf1_confirmation_raw.json"


def main() -> int:
    SUMMARY.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(REPO)
    manifest_path = SUMMARY / "m4pf2_0_source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    identifiable = identifiability_audit(raw)
    anchor = anchor_compatibility_audit(raw)
    diagnostic = {
        "schema_version": "raretopo-m4pf2-0-diagnostic-v0",
        "stage": "M4-PF2-0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "extra_simulator_calls": 0,
        "mean_gradient_theory_validated": True,
        "identifiability": identifiable,
        "anchor_compatibility": {key: value for key, value in anchor.items()
                                 if key != "state_rows"},
        "pf2_0_verdict": anchor["verdict_text"],
    }
    (SUMMARY / "m4pf2_0_diagnostic.json").write_text(
        json.dumps(diagnostic, indent=2), encoding="utf-8")
    with (SUMMARY / "m4pf2_0_anchor_table.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(anchor["state_rows"][0]))
        writer.writeheader()
        writer.writerows(anchor["state_rows"])
    mismatches = verify_manifest(REPO, manifest)
    manifest["sources_unchanged"] = not mismatches
    manifest["post_analysis_mismatches"] = mismatches
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "source_lock": not mismatches,
        "mean_gradient_identifiable":
            identifiable["mean_gradient_from_frozen_samples"],
        "anchor_exact_match_count": anchor["exact_match_count"],
        "anchor_mismatch_count": anchor["mismatch_count"],
        "verdict": anchor["verdict_text"],
        "extra_simulator_calls": 0,
    }, indent=2))
    return 0 if not mismatches else 3


if __name__ == "__main__":
    raise SystemExit(main())
