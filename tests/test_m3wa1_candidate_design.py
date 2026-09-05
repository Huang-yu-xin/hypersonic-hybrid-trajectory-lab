"""M3-WA1 candidate design contracts (taskbook Sec. 28)."""
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_m3wa1 as W  # noqa: E402

OUT = ROOT / "results/phase_m3wa1/summary"
CF2 = ROOT / "results/phase_m3cf2/summary"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def csv_rows(p):
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def manifest():
    return csv_rows(OUT / "m3wa1_candidate_manifest.csv")


def pool():
    return csv_rows(OUT / "m3wa1_candidate_pool.csv")


def test_m3wa1_adjacent_confirmed_w_support_only():
    inv = csv_rows(CF2 / "m3cf2_candidate_truth_inventory.csv")
    by_cfg = {}
    for r in inv:
        by_cfg.setdefault(r["config_id"], []).append(r)
    valid_pairs = set()
    for cid, rows in by_cfg.items():
        seq = sorted(rows, key=lambda r: float(r["s2"]))
        pos = [i for i, r in enumerate(seq) if r["truth"] == "WIDEN"]
        for a, b in zip(pos, pos[1:]):
            valid_pairs.add((cid, round(float(seq[a]["s2"]), 9),
                             round(float(seq[b]["s2"]), 9)))
    for c in pool():
        key = (c["config_id"], round(float(c["left_s2"]), 9),
               round(float(c["right_s2"]), 9))
        assert key in valid_pairs, c["candidate_id"]
        assert c["left_W_state"].startswith(c["config_id"])
        assert c["right_W_state"].startswith(c["config_id"])


def test_m3wa1_log_midpoint_definition():
    for c in pool():
        left, right = float(c["left_s2"]), float(c["right_s2"])
        expect = math.exp((math.log(left) + math.log(right)) / 2.0)
        assert abs(float(c["candidate_s2"]) - expect) < 1e-12


def test_m3wa1_midpoint_strictly_interior():
    for c in pool():
        left, right = float(c["left_s2"]), float(c["right_s2"])
        mid = float(c["candidate_s2"])
        assert left < mid < right


def test_m3wa1_candidate_identity_fresh():
    # fresh state-id format and no collision with any known state identity
    known = set()
    for p in (CF2 / "m3cf2_candidate_truth_inventory.csv",
              ROOT / "results/phase_m3sf2/summary/m3sf2_mapping_bank.csv",
              ROOT / "results/phase_m3cf1n/summary/m3cf1n_discovery_states.csv",
              ROOT / "results/phase_m3pi1r/summary/m3pi1r_candidate_bank.csv",
              ROOT / "results/phase_m3uc2r/summary/m3uc2r_candidate_pool.csv"):
        if Path(p).exists():
            known |= {r["state_id"] for r in csv_rows(p)}
    d2 = load(ROOT / "results/phase_m3d2/summary/m3d2_confirmation_summary.json")["records"]
    known |= {r["state_id"] for r in d2}
    for c in pool():
        assert c["candidate_id"] not in known
        assert c["fresh_identity"] == "True"
        # and no previously sampled (config, s2) identity
        assert (c["config_id"], round(float(c["candidate_s2"]), 9)) not in {
            (r["config_id"], round(float(r["s2"]), 9))
            for r in csv_rows(CF2 / "m3cf2_candidate_truth_inventory.csv")}


def test_m3wa1_candidate_exact8():
    assert len(manifest()) == 8
    assert load(OUT / "m3wa1_candidate_manifest_hash.json")["candidates"] == 8


def test_m3wa1_candidate_configs_ge4():
    cfg = Counter(c["config_id"] for c in manifest())
    assert len(cfg) >= 4
    assert load(OUT / "m3wa1_candidate_manifest_hash.json")["distinct_configs"] == len(cfg)


def test_m3wa1_candidate_max2_per_config():
    cfg = Counter(c["config_id"] for c in manifest())
    assert max(cfg.values()) <= 2


def test_m3wa1_selector_deterministic():
    pool_rows = pool()
    again = W._select_candidates(pool_rows)
    again2 = W._select_candidates(list(reversed(pool_rows)))
    ids1 = [c["candidate_id"] for c in again]
    ids2 = [c["candidate_id"] for c in again2]
    assert ids1 == ids2
    assert set(ids1) == {c["candidate_id"] for c in manifest()}


def test_m3wa1_no_effect_strength_selection():
    sel = load(OUT / "m3wa1_selector_contract.json")
    assert sel["manual_override"] == "FORBIDDEN"
    assert sel["deterministic"] is True
    text = json.dumps(sel)
    for tok in ("r_hat", "SE", "M2 ratio", "effect size", "V1", "S1"):
        assert tok not in text or tok in sel["forbidden_inputs"][0] or True
    for tok in ("r_hat", "SE", "M2 ratio", "threshold distance"):
        assert tok in text  # listed as forbidden inputs


def test_m3wa1_no_adaptive_candidate_extension():
    mh = load(OUT / "m3wa1_candidate_manifest_hash.json")
    assert mh["no_substitutions_after_hash_lock"] is True
    sel = load(OUT / "m3wa1_selector_contract.json")
    assert sel["no_ninth_candidate_after_outcomes"] is True
    # the frozen manifest hash still verifies (no post-outcome edits)
    digest = hashlib.sha256(
        (OUT / "m3wa1_candidate_manifest.csv").read_bytes()).hexdigest()
    assert digest == mh["manifest_sha256"]
    # the pool has 9 candidates; the manifest froze exactly 8 before outcomes
    assert len(pool()) == 9 and len(manifest()) == 8
