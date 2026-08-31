"""Build the corrected ER-1 M3-v0 gate and legacy delta table."""

from pathlib import Path
import json

from hyptraj.er1 import build_m3v0_gate


REPO = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    result = build_m3v0_gate(REPO)
    print(json.dumps({
        "core_gates_all_pass": result["core_gates_all_pass"],
        "child_stage": result["child_stage"],
        "child_authorized": result["child_authorized"],
        "repair_simulator_calls": result["repair_simulator_calls"],
    }, indent=2))
