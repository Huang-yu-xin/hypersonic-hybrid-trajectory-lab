"""M3-WA1 zero-simulator boundary contracts (taskbook Sec. 28)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wa1/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def final():
    return load(OUT / "m3wa1_final_verdict.json")


def test_m3wa1_gradient_zero():
    assert final()["gradient_pilot_trials"] == 0


def test_m3wa1_probe_zero():
    assert final()["finite_action_probe_trials"] == 0


def test_m3wa1_threshold_null():
    assert final()["v1_threshold"] is None
    assert final()["s1_threshold"] is None


def test_m3wa1_confirmation_zero():
    assert final()["protected_confirmation_pilot_trials"] == 0
    assert final()["s1_confirmation_authorized"] is False


def test_m3wa1_value_blocked():
    assert final()["value"] == "BLOCKED"


def test_m3wa1_rarity_blocked():
    assert final()["rarity_shift"] == "BLOCKED"


def test_m3wa1_m3q_blocked():
    assert final()["m3_q"] == "BLOCKED"
