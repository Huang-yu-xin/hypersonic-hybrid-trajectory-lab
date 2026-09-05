"""M3-PI1VR0 zero-simulator boundary contracts (taskbook Sec. 29)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vr0/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def final():
    return load(OUT / "m3pi1vr0_final_verdict.json")


def test_m3pi1vr0_zero_simulator():
    assert final()["simulator_samples"] == 0
    assert load(OUT / "m3pi1vr0_source_manifest.json")["simulator_samples"] == 0


def test_m3pi1vr0_zero_new_reference():
    assert final()["new_reference_samples"] == 0
    assert final()["new_p_ref_samples"] == 0


def test_m3pi1vr0_gradient_zero():
    assert final()["gradient_pilot_trials"] == 0


def test_m3pi1vr0_probe_zero():
    assert final()["finite_action_probe_trials"] == 0


def test_m3pi1vr0_threshold_null():
    assert final()["threshold"] is None
    status = load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["primary V1 sufficiency result"] == "UNAVAILABLE"


def test_m3pi1vr0_confirmation_zero():
    assert final()["protected_confirmation_pilot_trials"] == 0
    assert final()["s1_confirmation_authorized"] is False


def test_m3pi1vr0_value_blocked():
    assert final()["value"] == "BLOCKED"


def test_m3pi1vr0_rarity_blocked():
    assert final()["rarity_shift"] == "BLOCKED"


def test_m3pi1vr0_m3q_blocked():
    assert final()["m3_q"] == "BLOCKED"
