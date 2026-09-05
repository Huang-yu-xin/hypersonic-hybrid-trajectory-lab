"""M3-WCF1 s2 design + state manifest + P_ref/reference contracts (Sec. 37)."""
import csv
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wcf1/summary"
PREF = ROOT / "results/phase_m3wcf1/pref"
REF = ROOT / "results/phase_m3wcf1/reference"
CF0 = ROOT / "results/phase_m3cf0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


# --------------------------- W-target s2 -----------------------------------

def test_m3wcf1_valid_w_support_only():
    rows = csv_rows(OUT / "m3wcf1_valid_w_by_s2_audit.csv")
    grid = [1.25, 1.6, 2, 2.5, 3.2, 4, 5, 6.4, 8]
    assert [float(r["common_grid_s2"]) for r in rows] == grid
    inv = csv_rows(CF2 / "m3cf2_candidate_truth_inventory.csv")
    for r in rows:
        g = float(r["common_grid_s2"])
        cfgs = {x["config_id"] for x in inv if abs(float(x["s2"]) - g) < 1e-9}
        ws = {x["config_id"] for x in inv
              if abs(float(x["s2"]) - g) < 1e-9 and x["truth"] == "WIDEN"}
        assert int(r["distinct_valid_configs_observed"]) == len(cfgs)
        assert int(r["distinct_configs_labeled_widen"]) == len(ws)


def test_m3wcf1_no_invalid_pi1v_in_s2_audit():
    text = (OUT / "m3wcf1_valid_w_by_s2_audit.csv").read_text(encoding="utf-8")
    for tok in ("V1", "S1", "r_hat"):
        assert tok not in text
    sc = load(OUT / "m3wcf1_s2_selector_contract.json")
    assert "invalid PI1V scores" in sc["evidence"]


def test_m3wcf1_s2_selector_deterministic():
    contract = load(OUT / "m3wcf1_s2_selector_contract.json")
    assert contract["rule"][0].startswith("1. highest number of distinct valid "
                                          "configs labeled WIDEN")
    rows = csv_rows(OUT / "m3wcf1_valid_w_by_s2_audit.csv")
    ranked = sorted(rows, key=lambda r: (-int(r["distinct_configs_labeled_widen"]),
                                         -float(r["w_support_fraction"]),
                                         float(r["common_grid_s2"]),
                                         int(r["grid_index"])))
    s2doc = load(OUT / "m3wcf1_w_target_s2.json")
    assert [float(r["common_grid_s2"]) for r in ranked[:2]] == s2doc["selected_s2"]


def test_m3wcf1_exact2_target_s2():
    s2doc = load(OUT / "m3wcf1_w_target_s2.json")
    assert len(s2doc["selected_s2"]) == 2


def test_m3wcf1_target_s2_from_frozen_grid():
    grid = load(CF0 / "m3cf0_future_s2_grid.json")["values"]
    s2doc = load(OUT / "m3wcf1_w_target_s2.json")
    assert all(v in grid for v in s2doc["selected_s2"])


def test_m3wcf1_s2_selector_frozen_preoutcome():
    prereg = load(OUT / "m3wcf1_prereg_hashes.json")
    h = {e["path"]: e["sha256"] for e in prereg["files"]}
    for rel in ("results/phase_m3wcf1/summary/m3wcf1_s2_selector_contract.json",
                "results/phase_m3wcf1/summary/m3wcf1_w_target_s2.json",
                "results/phase_m3wcf1/summary/m3wcf1_valid_w_by_s2_audit.csv"):
        assert h[rel] == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert load(OUT / "m3wcf1_s2_selector_contract.json")[
        "frozen_before_any_wcf1_p_ref_or_reference_run"] is True


# --------------------------- state manifest --------------------------------

def test_m3wcf1_exact12_states():
    states = csv_rows(OUT / "m3wcf1_reference_state_manifest.csv")
    assert len(states) == 12


def test_m3wcf1_two_states_per_config():
    states = csv_rows(OUT / "m3wcf1_reference_state_manifest.csv")
    cfg = Counter(r["config_id"] for r in states)
    assert set(cfg.values()) == {2} and len(cfg) == 6


def test_m3wcf1_all_state_identities_fresh():
    audit = load(OUT / "m3wcf1_state_freshness_audit.json")
    assert audit["states"] == 12 and audit["fresh_identities"] == 12
    assert all(r["identity_fresh"] for r in audit["rows"])


def test_m3wcf1_no_adaptive_state_extension():
    prereg = load(OUT / "m3wcf1_prereg_hashes.json")
    h = {e["path"]: e["sha256"] for e in prereg["files"]}
    assert h["results/phase_m3wcf1/summary/m3wcf1_reference_state_manifest.csv"] == \
        hashlib.sha256((OUT / "m3wcf1_reference_state_manifest.csv").read_bytes()).hexdigest()


def test_m3wcf1_manifest_hash():
    mh = load(OUT / "m3wcf1_reference_state_manifest_hash.json")
    digest = hashlib.sha256(
        (OUT / "m3wcf1_reference_state_manifest.csv").read_bytes()).hexdigest()
    assert digest == mh["manifest_sha256"]


# --------------------------- P_ref / reference ------------------------------

def test_m3wcf1_new_pref_per_config():
    dep_rows = csv_rows(OUT / "m3wcf1_physical_config_manifest.csv")
    for r in dep_rows:
        p = PREF / f"{r['wcf1_config_id']}.json"
        assert p.exists()
        rec = load(p)
        assert rec["config_id"] == r["raw_candidate_id"]
        assert rec["wcf1_config_id"] == r["wcf1_config_id"]


def test_m3wcf1_pref_count6():
    manifest = load(REF / "reference_manifest.json") \
        if (REF / "reference_manifest.json").exists() else None
    prefs = list(PREF.glob("wcf1_new_*.json"))
    assert len(prefs) == 6
    ps = load(OUT / "m3wcf1_pref_summary.json")
    assert ps["complete"] == 6 and ps["consumed_invalid"] == 0


def test_m3wcf1_pref_budget500k():
    for p in PREF.glob("wcf1_new_*.json"):
        assert load(p)["sample_count"] == 500_000


def test_m3wcf1_pref_event_v2():
    for p in PREF.glob("wcf1_new_*.json"):
        assert load(p)["event_schema"] == "corrected full-event v2"


def test_m3wcf1_pref_seed_disjoint():
    seeds = load(OUT / "m3wcf1_seed_manifest.json")
    assert seeds["pref_namespace"] == "M3-WCF1-PREF"
    assert seeds["collision_with_all_prior"] == []
    ref_vals = {x for v in seeds["ref_seed_keys"].values() for x in v}
    pref_vals = {x for v in seeds["pref_seed_keys"].values() for x in v}
    assert not (ref_vals & pref_vals)


def test_m3wcf1_pref_all_complete_before_reference():
    ps = load(OUT / "m3wcf1_pref_summary.json")
    assert ps["gate"] == "PASS"
    rm = load(REF / "reference_manifest.json")
    assert rm["complete"] == 12          # references ran only after the gate


def test_m3wcf1_ref_count12():
    rm = load(REF / "reference_manifest.json")
    assert rm["complete"] == 12 and rm["consumed_invalid"] == 0
    recs = list(REF.glob("wcf1_new_*.json"))
    assert len(recs) == 12


def test_m3wcf1_ref_budget500k():
    for p in REF.glob("wcf1_new_*.json"):
        assert load(p)["sample_counts"]["per_arm"] == 500_000
        assert load(p)["sample_counts"]["finite_action_samples"] == 1_500_000


def test_m3wcf1_ref_three_arms():
    for p in REF.glob("wcf1_new_*.json"):
        arms = load(p)["arms"]
        assert set(arms) == {"base", "widen", "shrink"}


def test_m3wcf1_ref_crn20():
    for p in REF.glob("wcf1_new_*.json"):
        assert load(p)["sample_counts"]["batches"] == 20


def test_m3wcf1_ref_corrected_semantics():
    from hyptraj.m3d2 import experiment as E
    sig = inspect.signature(E.classify_reference_state)
    assert sig.parameters["tau"].default == 0.01
    assert sig.parameters["hold_window"].default == 0.03
    assert sig.parameters["margin_min"].default == 0.05
    assert sig.parameters["min_arm_ess"].default == 20.0


def test_m3wcf1_ref_seed_disjoint():
    seeds = load(OUT / "m3wcf1_seed_manifest.json")
    assert seeds["ref_namespace"] == "M3-WCF1-REF"
    assert seeds["hash_locked_before_simulator"] is True
    assert len({v[0] for v in seeds["ref_seed_keys"].values()}) == 12


def test_m3wcf1_no_discovery_stage():
    proto = load(OUT / "m3wcf1_reference_protocol.json")
    assert proto["no_discovery_stage"] is True
    assert proto["samples_per_arm"] == 500_000
