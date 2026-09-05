"""M3-WCF1 parent/leakage + physical expansion contracts (taskbook Sec. 37)."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3wcf1/summary"
VR0 = ROOT / "results/phase_m3pi1vr0/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"
CF0 = ROOT / "results/phase_m3cf0/summary"
WA1R_OUT = ROOT / "results/phase_m3wa1r/summary"

CONSUMED = "cf1n_new_000_wa1_w_s2_1p788854382"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_m3wcf1_parent_wa1rb():
    assert load(ROOT / "results/phase_m3wa1r/summary/m3wa1r_final_verdict.json")["verdict"] == "WA1R-B"
    pa = load(OUT / "m3wcf1_parent_audit.json")
    assert pa["all_match"] is True
    ref = load(ROOT / "results/phase_m3wa1r/reference/reference_manifest.json")
    assert ref["complete"] == 8 and ref["labels"]["WIDEN"] == 8
    assert ref["consumed_invalid"] == 0


def test_m3wcf1_pi1v_primary_x():
    status = load(VR0 / "m3pi1vr0_pi1v_scientific_status.json")
    assert status["PI1V valid verdict"] == "PI1V-X"
    assert status["attempt-2 numerical result"] == "DIAGNOSTIC_ONLY"


def test_m3wcf1_no_invalid_pi1v_scores():
    forbidden = ("r_hat", "se_r_hat", "V1", "S1", "gradient_confidence")
    for name in ("m3wcf1_physical_config_manifest.csv",
                 "m3wcf1_reference_state_manifest.csv",
                 "m3wcf1_valid_w_by_s2_audit.csv"):
        header = (OUT / name).read_text(encoding="utf-8").splitlines()[0]
        for tok in forbidden:
            assert tok not in header, (name, tok)


def test_m3wcf1_no_wa1_consumed_state():
    universe_text = (OUT / "m3wcf1_reference_state_manifest.csv").read_text(encoding="utf-8")
    assert CONSUMED not in universe_text
    pool = (OUT / "m3wcf1_combined_fresh_w_pool.csv").read_text(encoding="utf-8")
    assert CONSUMED not in pool


def test_m3wcf1_no_retired_state_reuse():
    retired = {r["state_id"] for r in csv_rows(
        VR0 / "m3pi1vr0_retired_development_states.csv")}
    states = {r["state_id"] for r in csv_rows(OUT / "m3wcf1_reference_state_manifest.csv")}
    pool = {r["state_id"] for r in csv_rows(OUT / "m3wcf1_combined_fresh_w_pool.csv")}
    assert states & retired == set() and pool & retired == set()


def test_m3wcf1_reserve_unpiloted():
    reserve = {r["state_id"] for r in csv_rows(
        CF2 / "m3cf2_pilot_protected_reserve_manifest.csv")}
    states = {r["state_id"] for r in csv_rows(OUT / "m3wcf1_reference_state_manifest.csv")}
    assert states & reserve == set()
    ref = load(ROOT / "results/phase_m3wcf1/reference/reference_manifest.json") \
        if (ROOT / "results/phase_m3wcf1/reference/reference_manifest.json").exists() else None
    if ref is not None:
        assert all(sid not in reserve for sid in ref["record_file_hashes"])


# ------------------------- physical expansion ------------------------------

def test_m3wcf1_s2_not_physical_axis():
    axis = load(CF0 / "m3cf0_axis_classification.json")
    assert axis["s2"]["class"] == "ACTION_STATE_AXIS"
    cap = load(OUT / "m3wcf1_legal_physical_capacity.json")
    assert cap["s2_is_not_physical_axis"] is True


def test_m3wcf1_legal_candidate_lattice():
    lat = csv_rows(CF0 / "m3cf0_raw_physical_candidate_lattice.csv")
    assert len(lat) == 128
    assert all(r["legal"].lower() == "true" for r in lat)
    cap = load(OUT / "m3wcf1_legal_physical_capacity.json")
    assert cap["legal_fresh_configs"] == 120
    assert cap["capacity_gate"] == "PASS"


def test_m3wcf1_fresh_config_capacity_ge6():
    cap = load(OUT / "m3wcf1_legal_physical_capacity.json")
    assert cap["legal_fresh_configs"] >= 6


def test_m3wcf1_exact6_new_configs():
    m = csv_rows(OUT / "m3wcf1_physical_config_manifest.csv")
    assert len(m) == 6
    assert [r["wcf1_config_id"] for r in m] == \
        [f"wcf1_new_{i:03d}" for i in range(6)]


def test_m3wcf1_no_prior_config_reuse():
    used = load(OUT / "m3wcf1_used_physical_config_manifest.json")
    used_ids = {u["config_id"] for u in used["used_configs"]}
    m = csv_rows(OUT / "m3wcf1_physical_config_manifest.csv")
    assert all(r["raw_candidate_id"] not in used_ids for r in m)
    # coordinate-level exclusion: no manifest row shares used coordinates
    def key(r):
        return (tuple(round(float(r[f"theta_{i}"]), 6) for i in range(1, 5)),
                tuple(round(float(r[f"h_{i}"]), 6) for i in range(1, 5)),
                tuple(bool(r[f"curved_{i}"]) for i in range(1, 5)),
                round(float(r["curvature_c"]), 6),
                tuple(round(float(r[f"offset_{i}"]), 6) for i in range(1, 5)))
    used_keys = {key(u) for u in used["used_configs"]}
    assert all(key(r) not in used_keys for r in m)


def test_m3wcf1_maximin_selector():
    import math
    m = csv_rows(OUT / "m3wcf1_physical_config_manifest.csv")
    sel = load(OUT / "m3wcf1_physical_selector_contract.json")
    assert sel["outcome_blind"] is True
    assert sel["rule"].startswith("sequential maximin")
    # recompute: each selected config's recorded min-distance must be its true
    # distance to the used set plus previously selected configs
    lat_rows = csv_rows(CF0 / "m3cf0_raw_physical_candidate_lattice.csv")
    lat = {r["config_id"]: r for r in lat_rows}
    cur = csv_rows(CF0 / "m3cf0_current_config_coordinates.csv")
    rep = csv_rows(ROOT / "results/phase_m3cf1r0/replacement/m3cf1r0_replacement_configs.csv")

    def fields13(r):
        return ([float(r[f"theta_{i}"]) for i in range(1, 5)]
                + [float(r[f"h_{i}"]) for i in range(1, 5)]
                + [float(r["curvature_c"])]
                + [float(r[f"offset_{i}"]) for i in range(1, 5)])

    allf = [fields13(r) for r in lat_rows]
    lo = [min(f[i] for f in allf) for i in range(13)]
    hi = [max(f[i] for f in allf) for i in range(13)]

    def vec(r):
        f = fields13(r)
        return tuple((f[i] - lo[i]) / (hi[i] - lo[i]) if hi[i] > lo[i] else 0.0
                     for i in range(13))

    def dist(a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    base = [vec(r) for r in cur] + [vec(r) for r in rep]
    for r in m:
        raw = lat[r["raw_candidate_id"]]
        d = min(dist(vec(raw), b) for b in base)
        assert abs(d - float(r["min_distance_to_prior_set"])) < 1e-3
        base.append(vec(raw))


def test_m3wcf1_config_selector_outcome_blind():
    sel = load(OUT / "m3wcf1_physical_selector_contract.json")
    assert sel["forbidden_inputs"][0] == "W outcomes"
    text = json.dumps(sel)
    for tok in ("PI1V Attempt-2 scores", "WA1 outcomes", "effect magnitude"):
        assert tok in text


def test_m3wcf1_config_manifest_hash():
    mh = load(OUT / "m3wcf1_physical_config_manifest_hash.json")
    digest = hashlib.sha256(
        (OUT / "m3wcf1_physical_config_manifest.csv").read_bytes()).hexdigest()
    assert digest == mh["manifest_sha256"]
    assert mh["prior_config_collisions"] == 0
    assert mh["no_seventh_config_after_outcomes"] is True
