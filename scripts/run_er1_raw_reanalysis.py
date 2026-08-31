"""Run zero-simulator ER-1 reanalysis on persisted PF2/PF3 archives."""

from __future__ import annotations

import json
from pathlib import Path

from hyptraj.er1 import run_raw_reanalysis


REPO = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    result = run_raw_reanalysis(REPO)
    print(json.dumps({
        "extra_simulator_calls": result["extra_simulator_calls"],
        "PF2_mass_ratio": result["M4-PF2"]["median_corrected_to_legacy_mass_ratio"],
        "PF3_mass_ratio": result["M4-PF3"]["median_corrected_to_legacy_mass_ratio"],
        "PF3_corrected_A_alloc": result["M4-PF3"]["median_corrected_A_alloc"],
    }, indent=2))
