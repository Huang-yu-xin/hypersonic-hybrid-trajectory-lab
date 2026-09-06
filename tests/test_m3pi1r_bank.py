import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3pi1r/summary'
def j(n):return json.loads((OUT/n).read_text())
def test_pi1r_prereg_bank_and_protection():
 with (OUT/'m3pi1r_candidate_bank.csv').open(newline='') as h:r=list(csv.DictReader(h))
 assert len(r)==92 and Counter(x['stratum'] for x in r)=={'DW':10,'DS':10,'U-CORE':72}
 assert j('m3pi1r_generator_capacity.json')['u_core_only'] and j('m3pi1r_protected_confirmation_audit.json')['pilot_untouched']
def test_pi1r_final_zero_pilot_when_complete():
 if not (OUT/'m3pi1r_final_verdict.json').exists():return
 f=j('m3pi1r_final_verdict.json');assert f['gradient_pilot_trials']==f['finite_action_probe_trials']==f['protected_confirmation_pilot_trials']==0
 assert f['v1_threshold'] is None and f['value_evaluation']==f['rarity_shift']==f['m3_q']=='BLOCKED'
def test_pi1r_reference_bank_and_stop_rule():
 s=j('m3pi1r_reference_summary.json');l=j('m3pi1r_reference_block_ledger.json')
 assert s['states_referenced']==92 and s['u_blocks_referenced']==9 and s['finite_action_samples']==138000000
 assert not s['natural_prevalence_claim'] and not s['panel_pass'] and not any(x['stop'] for x in l)
 assert [x['block'] for x in l[-9:]]==[f'U_BLOCK_{i}' for i in range(1,10)]
def test_pi1r_panel_failure_is_schema_preserving_and_auditable():
 a=j('m3pi1r_panel_selection_audit.json');f=j('m3pi1r_final_verdict.json')
 with (OUT/'m3pi1r_development_panel.csv').open(newline='') as h:r=list(csv.DictReader(h))
 assert f['verdict']=='PI1R-B' and not a['constructible'] and a['S_configs']==3 and a['W_configs']>=4
 assert a['ND_configs']>=4 and a['effect_strength_used'] is False and r==[]
