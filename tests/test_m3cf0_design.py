import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3cf0/summary'
def j(n):return json.loads((OUT/n).read_text())
def test_m3cf0_parent_zero_simulator_and_firewalls():
 f=j('m3cf0_final_verdict.json');assert f['parent']['SF2']=='SF2-C' and f['extra_simulator_samples']==f['new_reference_states']==0
 assert f['gradient_pilot_trials']==f['finite_action_probe_trials']==f['protected_confirmation_pilot_trials']==0 and f['v1_threshold'] is None
 assert not f['diversity_gate_relaxed'] and not f['outcome_labels_used_in_selection']
def test_m3cf0_exact_eight_outcome_independent_new_configs():
 n=list(csv.DictReader((OUT/'m3cf0_frozen_new_configs.csv').open(newline='')));c=j('m3cf0_expansion_coverage_audit.json')
 assert len(n)==8 and [x['new_config_id'] for x in n]==[f'cf0_new_{i:03d}' for i in range(8)]
 assert c['selected']==8 and not c['outcome_labels_used_in_selection'] and not c['shrink_label_quota']
def test_m3cf0_future_grid_and_target_frozen():
 g=j('m3cf0_future_s2_grid.json');p=j('m3cf0_future_mapping_protocol.json');a=j('m3cf0_protected_confirmation_audit.json')
 assert g['values']==[1.25,1.6,2,2.5,3.2,4,5,6.4,8] and g['frozen']
 assert p['future_target']['new_stable_required']==2 and p['future_target']['final_stable_configs_min']==4 and a['pilot_untouched']
def test_m3cf0_output_schema():
 names=['m3cf0_source_manifest.json','m3cf0_current_config_coordinates.csv','m3cf0_axis_classification.json','m3cf0_physical_domain.json','m3cf0_existing_geometry_distance.csv','m3cf0_support_geometry_overlay.csv','m3cf0_raw_physical_candidate_lattice.csv','m3cf0_physical_candidate_exclusion.json','m3cf0_frozen_new_configs.csv','m3cf0_expansion_coverage_audit.json','m3cf0_future_s2_grid.json','m3cf0_future_mapping_protocol.json','m3cf0_protected_confirmation_audit.json','m3cf0_final_verdict.json']
 assert all((OUT/n).exists() for n in names)
