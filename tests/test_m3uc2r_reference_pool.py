"""M3-UC2R preregistration and reference-firewall invariants."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"results/phase_m3uc2r/summary"; CFG=ROOT/"configs/phase_m3uc2r"
def j(name): return json.loads((OUT/name).read_text())
def rows(name):
    with (OUT/name).open(newline="") as h:return list(csv.DictReader(h))

def test_m3uc2r_parent_isolation_and_firewall():
    a=j("m3uc2r_uc2_outcome_isolation_audit.json");p=json.loads((CFG/"m3uc2r_reference_protocol.json").read_text())
    assert a["pass"] and a["uc2_final_verdict_used"] and a["uc2_aggregate_by_stratum_counts_used"]
    assert not any(a[k] for k in a if k.startswith("uc2_per_state_"))
    assert p["pilot_samples"]==0 and p["threshold"] is None and p["rarity_shift"]==p["m3_q"]=="BLOCKED"

def test_m3uc2r_exclusion_capacity_and_frozen_fractions():
    m=j("m3uc2r_prior_state_exclusion_manifest.json");c=j("m3uc2r_generator_capacity.json");f=json.loads((CFG/"m3uc2r_fraction_libraries.json").read_text())
    assert m["uc1_48_identities_included"] and m["uc2_60_identities_included"]
    assert c["capacity"]=={"DW":84,"DS":60,"U":140}
    assert len(f["F_DW"])==len(f["F_DS"])==12 and len(f["F_U"])==28 and f["frozen_order"]

def test_m3uc2r_exact_fresh_allocation_and_preoutcome_split():
    r=rows("m3uc2r_fresh_states.csv")
    assert len(r)==80==len({x["state_id"] for x in r})
    assert Counter(x["design_stratum"] for x in r)=={"DW":16,"DS":16,"U":48}
    assert Counter(x["split"] for x in r)=={"DEVELOPMENT":40,"CONFIRMATION":40}
    for split in ("DEVELOPMENT","CONFIRMATION"):
        assert Counter(x["design_stratum"] for x in r if x["split"]==split)=={"DW":8,"DS":8,"U":24}
    h=j("m3uc2r_prereg_hashes.json");assert h["reference_outcomes"]=="NONE" and h["pilot_samples"]==0 and h["threshold"] is None

def test_m3uc2r_reference_outputs_when_complete():
    if not (OUT/"m3uc2r_final_verdict.json").exists():return
    f=j("m3uc2r_final_verdict.json"); r=rows("m3uc2r_reference_states.csv")
    assert len(r)==80 and f["development_pilot_samples"]==f["confirmation_pilot_samples"]==0
    assert f["threshold"] is None and not f["outcome_adaptive_rebalancing"]
