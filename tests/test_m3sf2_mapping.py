import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3sf2/summary'
def j(n):return json.loads((OUT/n).read_text())
def test_m3sf2_prereg_mapping_bank():
 b=list(csv.DictReader((OUT/'m3sf2_mapping_bank.csv').open(newline='')));c=j('m3sf2_generator_capacity.json');m=j('m3sf2_s2_config_manifest.json')
 assert len(b)==40 and c['prior_collisions']==0 and len(m['config_ids'])==8 and all(v==5 for v in Counter(x['config_id'] for x in b).values())
 assert [int(x['mapping_position_index']) for x in b[:5]]==[1,2,3,4,5]
def test_m3sf2_prereg_firewalls_and_hash():
 a=j('m3sf2_protected_confirmation_audit.json');h=j('m3sf2_prereg_hashes.json')
 assert a['pilot_untouched'] and not a['state_specific_protected_reference_used_in_mapping_design'] and h['outcomes']=='NONE' and len(h['bank_sha256'])==64
def test_m3sf2_stability_and_verdict_logic():
 f=j('m3sf2_final_verdict.json');c=j('m3sf2_config_classifications.json');r=j('m3sf2_reference_summary.json')
 assert (f['K_STABLE'],f['K_FRAGILE'],f['K_VANISHED'])==(2,1,5) and f['verdict']=='SF2-C'
 assert r['states_referenced']==40 and r['truth']['SHRINK']==12 and not r['natural_prevalence_claim']
 assert f['gradient_pilot_trials']==f['finite_action_probe_trials']==f['protected_confirmation_pilot_trials']==0 and f['v1_threshold'] is None
def test_m3sf2_output_schema():
 names=['m3sf2_source_manifest.json','m3sf2_s2_config_manifest.json','m3sf2_canonical_interval_manifest.json','m3sf2_prior_state_exclusion_manifest.json','m3sf2_generator_capacity.json','m3sf2_mapping_bank.csv','m3sf2_prereg_hashes.json','m3sf2_protected_confirmation_audit.json','m3sf2_reference_states.csv','m3sf2_reference_summary.json','m3sf2_interval_truth_patterns.csv','m3sf2_support_stability_by_config.csv','m3sf2_config_classifications.json','m3sf2_final_verdict.json']
 assert all((OUT/n).exists() for n in names)
