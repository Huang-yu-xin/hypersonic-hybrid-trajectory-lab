"""Run the M3-CA artifact-only attribution audit.

This entry point reads existing JSON artifacts and writes hashes, tables and a
summary. It contains no simulator/controller/proposal execution path.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from hyptraj.m3ca.accounting import run_attribution
from hyptraj.m3ca.provenance import build_source_manifest, verify_source_manifest

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "results" / "phase_m3ca" / "summary"


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    SUMMARY.mkdir(parents=True, exist_ok=True)

    # CA1 happens before any scientific arithmetic.
    manifest = build_source_manifest(REPO)
    manifest_path = SUMMARY / "m3ca_source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = run_attribution(REPO)
    result["generated_at_utc"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    state_rows = result.pop("state_rows")
    ledger = result.pop("cost_ledger")
    correlations = result["correlations"]

    write_csv(SUMMARY / "m3ca_state_table.csv", state_rows)
    write_csv(SUMMARY / "m3ca_cost_ledger.csv", ledger)
    write_csv(SUMMARY / "m3ca_correlation_summary.csv", correlations)

    mismatches = verify_source_manifest(REPO, manifest)
    manifest["sources_unchanged"] = not mismatches
    manifest["post_analysis_mismatches"] = mismatches
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result["source_lock"] = {
        "verified": not mismatches,
        "sources_unchanged": not mismatches,
        "manifest": "results/phase_m3ca/summary/m3ca_source_manifest.json",
    }
    result["outputs"] = {
        "state_table": "results/phase_m3ca/summary/m3ca_state_table.csv",
        "cost_ledger": "results/phase_m3ca/summary/m3ca_cost_ledger.csv",
        "correlations": "results/phase_m3ca/summary/m3ca_correlation_summary.csv",
    }
    (SUMMARY / "m3ca_cost_attribution.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    print(json.dumps({
        "headline_pass": result["headline_reproduction"]["pass"],
        "capture": result["headline_reproduction"]["capture_fraction"],
        "vrf_budget": result["headline_reproduction"][
            "vrf_budget_m3g_v1_median"],
        "free_oracle": (result["counterfactuals"] or {}).get(
            "vrf_budget_free_oracle"),
        "verdict": result["verdict"]["code"],
        "sources_unchanged": not mismatches,
        "extra_simulator_calls": result["extra_simulator_calls"],
    }, indent=2))
    return 0 if result["headline_reproduction"]["pass"] and not mismatches else 3


if __name__ == "__main__":
    raise SystemExit(main())
