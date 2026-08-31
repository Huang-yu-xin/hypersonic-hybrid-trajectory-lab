"""Generate ER-1 zero-simulator forensic records."""

from __future__ import annotations

import json
from pathlib import Path

from hyptraj.er1 import run_forensics


REPO = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    result = run_forensics(REPO)
    print(json.dumps({
        "status": result["lineage"]["status"],
        "first_contaminated_stage": result["boundary"]["first_known_contaminated_stage"],
        "new_simulation_required": result["repairability"]["new_simulation_required"],
        "extra_simulator_calls": result["manifest"]["extra_simulator_calls"],
    }, indent=2))
