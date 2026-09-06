import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3sf0/summary'
def j(n): return json.loads((OUT/n).read_text())
def rows(n):
 with (OUT/n).open(newline='') as h:return list(csv.DictReader(h))
def test_m3sf0_parent_zero_simulator_and_firewalls():
 f=j('m3sf0_final_verdict.json')
 assert f['parent_pi1r_verdict']=='PI1R-B' and f['extra_simulator_samples']==f['new_reference_states']==0
 assert f['gradient_pilot_trials']==f['finite_action_probe_trials']==f['protected_confirmation_pilot_trials']==0
 assert f['v1_threshold'] is None and f['value']==f['rarity_shift']==f['m3_q']=='BLOCKED'
def test_m3sf0_corrected_support_and_accessibility():
 s=rows('m3sf0_shrink_support_by_config.csv');w=rows('m3sf0_widen_support_by_config.csv');f=j('m3sf0_final_verdict.json')
 assert len(s)==len(w)==8 and f['K_S0']==f['K_S1']==f['K_S2_primary']==8
 assert all(x['S0_observed']==x['S1_same_class_interval']==x['S2_fresh_accessible']=='True' for x in s)
 assert all(x['W0_observed']==x['W1_same_class_interval']==x['W2_fresh_accessible']=='True' for x in w)
def test_m3sf0_primary_protection_and_no_gate_relaxation():
 c=j('m3sf0_confirmation_eligibility_audit.json');p=j('m3sf0_diversity_gate_provenance.json');f=j('m3sf0_final_verdict.json')
 assert c['protected_pilot_untouched'] and not c['state_specific_protected_reference_used_in_primary_audit']
 assert p['classification']=='HEURISTIC_DESIGN_CHOICE' and not p['pi1r_gate_changed'] and not f['pi1r_gate_relaxed']
 assert f['verdict']=='SF0-A' and f['failure_type']=='GENERATOR_BOTTLENECK'
def test_m3sf0_required_output_schema():
 names=['m3sf0_source_manifest.json','m3sf0_config_inventory.csv','m3sf0_reference_truth_ledger.csv','m3sf0_truth_by_config.csv','m3sf0_same_class_intervals.csv','m3sf0_prior_exclusion_union.json','m3sf0_shrink_support_by_config.csv','m3sf0_widen_support_by_config.csv','m3sf0_diversity_gate_provenance.json','m3sf0_config_geometry_distance.csv','m3sf0_diversity_metric_options.json','m3sf0_confirmation_eligibility_audit.json','m3sf0_final_verdict.json']
 assert all((OUT/n).exists() for n in names)
