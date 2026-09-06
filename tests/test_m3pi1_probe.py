"""M3-PI1 fresh-state, fixed-cost, protected-confirmation invariants."""
import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3pi1/summary';CFG=ROOT/'configs/phase_m3pi1'
def j(n):return json.loads((OUT/n).read_text())
def rows(n):
 with (OUT/n).open(newline='') as h:return list(csv.DictReader(h))
def test_pi1_prereg_fresh_allocation_and_protection():
 r=rows('m3pi1_fresh_dev_states.csv');m=j('m3pi1_prior_state_exclusion_manifest.json');p=json.loads((CFG/'m3pi1_fa_probe.json').read_text())
 assert len(r)==40 and Counter(x['design_stratum'] for x in r)=={'DW':8,'DS':8,'U':24} and m['includes_uc2r_all_80']
 assert p['base_samples']==p['selected_arm_samples']==10000 and p['extra_samples_per_trial']==20000 and p['cost_ratio']==2.0 and p['paired_crn']
def test_pi1_reference_and_probe_outputs_when_complete():
 if not (OUT/'m3pi1_final_verdict.json').exists():return
 f=j('m3pi1_final_verdict.json');ref=j('m3pi1_reference_summary.json')
 if f['verdict']=='PI1-REF-B':
  assert not ref['pass'] and f['gradient_pilot_samples']==f['finite_action_probe_samples']==0
  assert not (OUT/'m3pi1_gradient_trials.csv').exists() and f['protected_confirmation_pilot_untouched']
  return
 g=rows('m3pi1_gradient_trials.csv');q=rows('m3pi1_probe_trials.csv')
 assert ref['pass'] and len(g)==len(q)==320 and f['protected_confirmation_pilot_untouched']
 assert {x['extra_samples'] for x in q if x['probe_executed']=='True'}=={'20000'}
 assert f['online_cost_ratio']<=2.0 and f['value_evaluation']==f['rarity_shift']==f['m3_q']=='BLOCKED'
