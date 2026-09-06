import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3sf1/summary'
def j(n):return json.loads((OUT/n).read_text())
def test_m3sf1_parent_and_frozen_quotas():
 b=list(csv.DictReader((OUT/'m3sf1_candidate_bank.csv').open(newline='')));s=j('m3sf1_s2_config_manifest.json');w=j('m3sf1_w2_config_manifest.json')
 assert s['K_S2']==8 and len(b)==52 and Counter(x['design_stratum'] for x in b)=={'S-CS':16,'W-CS':12,'U-CORE':24}
 assert s['all_eight_used'] and len(s['config_ids'])==8 and w['K_W2']>=4 and w['K_W_use']==6
def test_m3sf1_scs_and_ucore_diversity_preregistered():
 b=list(csv.DictReader((OUT/'m3sf1_candidate_bank.csv').open(newline='')));c=j('m3sf1_generator_capacity.json');p=j('m3sf1_prereg_hashes.json')
 s=[x for x in b if x['design_stratum']=='S-CS'];u=[x for x in b if x['design_stratum']=='U-CORE']
 assert all(v==2 for v in Counter(x['config_id'] for x in s).values()) and len({x['source_interval_or_bracket'] for x in u})>=4
 assert c['all_prior_collisions']==0 and p['outcomes']=='NONE' and len(p['bank_sha256'])==64
def test_m3sf1_firewalls_before_reference():
 a=j('m3sf1_protected_confirmation_audit.json');assert a['pilot_untouched'] and not a['state_specific_reference_used_in_SF1_design']
def test_m3sf1_reference_failure_is_s_and_no_panel_is_frozen():
 f=j('m3sf1_final_verdict.json');a=j('m3sf1_panel_selection_audit.json');s=j('m3sf1_reference_summary.json')
 panel=list(csv.DictReader((OUT/'m3sf1_development_panel.csv').open(newline='')))
 assert f['verdict']=='SF1-S' and f['gradient_pilot_trials']==f['finite_action_probe_trials']==f['protected_confirmation_pilot_trials']==0
 assert s['states_referenced']==52 and s['S']==5 and not a['constructible'] and a['S_configs']==3 and panel==[]
def test_m3sf1_output_schema_and_no_prevalence_claim():
 names=['m3sf1_source_manifest.json','m3sf1_prior_state_exclusion_manifest.json','m3sf1_s2_config_manifest.json','m3sf1_w2_config_manifest.json','m3sf1_generator_capacity.json','m3sf1_candidate_bank.csv','m3sf1_prereg_hashes.json','m3sf1_protected_confirmation_audit.json','m3sf1_reference_states.csv','m3sf1_reference_summary.json','m3sf1_reference_by_stratum.json','m3sf1_shrink_yield_by_config.csv','m3sf1_widen_yield_by_config.csv','m3sf1_nd_yield_by_bracket.csv','m3sf1_development_panel.csv','m3sf1_panel_selection_audit.json','m3sf1_final_verdict.json']
 assert all((OUT/n).exists() for n in names) and not j('m3sf1_reference_summary.json')['natural_prevalence_claim']
