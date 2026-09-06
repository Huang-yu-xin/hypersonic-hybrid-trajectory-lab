"""M3-PI zero-simulator information-sufficiency invariants."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3pi/summary'
def j(n):return json.loads((OUT/n).read_text())
def rows(n):
 with (OUT/n).open(newline='') as h:return list(csv.DictReader(h))
def test_m3pi_parent_and_confirmation_protection():
 f=j('m3pi_final_verdict.json');s=j('m3pi_source_manifest.json')
 assert f['verdict']=='PI-B' and f['confirmation_pilot_samples']==0 and s['zero_simulator'] and s['development_only'] and not s['confirmation_pilot_access']
def test_m3pi_existing_rules_are_limited_interpretable_and_state_level():
 inv=j('m3pi_existing_feature_inventory.json');cv=rows('m3pi_existing_rule_cv.csv')
 assert inv['max_existing_rules']==3 and len(inv['frozen_rules'])==3 and inv['black_box_models_forbidden']
 assert {r['fold_config'] for r in cv}>={'c000','c001','c004','c010','c020','POOLED_OOF'} and all(r['rule'] in inv['frozen_rules'] for r in cv)
def test_m3pi_output_mismatch_cost_and_firewall():
 assert len(rows('m3pi_uc3_dev_state_summary.csv'))==40
 assert len(rows('m3pi_local_finite_mismatch.csv'))==40
 matrix=rows('m3pi_information_candidate_matrix.csv');assert any(r['candidate']=='low_budget_paired_finite_action_contrast' and r['cost_multiplier']=='2.0' for r in matrix)
 f=j('m3pi_final_verdict.json');assert f['value_evaluation']==f['rarity_shift']==f['m3_q']=='BLOCKED'
