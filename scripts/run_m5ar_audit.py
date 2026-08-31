"""Run the M5-AR frozen-artifact audit (zero simulator calls)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hyptraj.m5ar import run_audit


REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    args = parser.parse_args()
    result = run_audit(args.repo)
    payload = {
        "status": result["routing"]["status"],
        "route": result["routing"]["primary_route"],
        "sources_unchanged": result["manifest"]["sources_unchanged"],
        "extra_simulator_calls": result["routing"]["extra_simulator_calls"],
    }
    if "ceiling" in result:
        payload["median_local_ceiling"] = result["ceiling"]["median_local_ceiling"]
    if "parent" in result:
        payload["parent_freeze_gate"] = result["parent"]["gate"]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
