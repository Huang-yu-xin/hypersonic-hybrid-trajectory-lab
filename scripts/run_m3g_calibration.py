"""M3-G offline calibration (handoff Sec. 6-8, 28-G3).

Reads ONLY the stored M3-D Layer-A batch; simulates the folded decisions
for GA1 x {0.0025, 0.005, 0.01, 0.02} + GA2 x same + baseline row;
applies the preregistered selection rule (W/S recall >= 0.90 each, then
max accuracy) and writes the full calibration payload to
results/phase_m3g/calibration/m3g_calibration_v0.json.

HARD INVARIANT: extra_simulator_calls == 0 (calibration never draws).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from hyptraj.m3g.calibration import LAYER_A_PATH, run_offline_calibration

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "results" / "phase_m3g" / "calibration" \
    / "m3g_calibration_v0.json"


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    payload = run_offline_calibration()
    payload["git_commit"] = _git()
    payload["data_source_abs"] = str(LAYER_A_PATH.resolve())
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    sel = payload["selection"]["selected"]
    print(f"[saved] {DEST.relative_to(REPO)}")
    print(f"[selection] {sel if sel else 'STOP (no candidate meets 0.90/0.90)'} "
          f"- extra_simulator_calls={payload['extra_simulator_calls']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())