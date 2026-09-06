"""M3-UC3 anti-leakage and calibration-run invariants."""
import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/phase_m3uc3/summary';CFG=ROOT/'configs/phase_m3uc3'
def j(n):return json.loads((OUT/n).read_text())
def rows(n):
 with (OUT/n).open(newline='') as h:return list(csv.DictReader(h))
def test_uc3_prereg_parent_score_and_firewall():
 b=j('m3uc3_benchmark_manifest.json');p=json.loads((CFG/'m3uc3_protocol.json').read_text());s=json.loads((CFG/'m3uc3_score_contract.json').read_text())
 assert (b['development'],b['confirmation'])==(40,40) and s['score_name']=='S1_gradient_z' and s['threshold'] is None
 assert p['pilot']['R_dev']==p['pilot']['R_confirm']==8 and p['pilot']['samples_per_trial']==20000
 assert p['value_evaluation']==p['rarity_shift']==p['m3_q']=='BLOCKED'
def test_uc3_dev_integrity_and_frozen_policy_when_available():
 if not (OUT/'m3uc3_dev_pilot_trials.csv').exists():return
 r=rows('m3uc3_dev_pilot_trials.csv');assert len(r)==320 and len({x['seed'] for x in r})==320 and set(Counter(x['state_id'] for x in r).values())=={8} and {x['pilot_samples'] for x in r}=={'20000'}
 if (OUT/'m3uc3_frozen_policy.json').exists():assert j('m3uc3_policy_freeze_manifest.json')['confirmation_trials_before_freeze']==0
def test_uc3_confirmation_exactly_once_and_firewall_when_available():
 if not (OUT/'m3uc3_confirm_pilot_trials.csv').exists():return
 r=rows('m3uc3_confirm_pilot_trials.csv');f=j('m3uc3_final_verdict.json');assert len(r)==320 and set(Counter(x['state_id'] for x in r).values())=={8}
 assert f['confirmation']['run_count']==1 and f['threshold'] is not None and f['rarity_shift']==f['m3_q']==f['value_evaluation']=='BLOCKED'

def test_uc3_development_failure_preserves_confirmation_when_applicable():
 if not (OUT/'m3uc3_final_verdict.json').exists():return
 f=j('m3uc3_final_verdict.json')
 if f['verdict']=='UC3-DEV-B':
  assert f['confirmation_pilot_samples']==0 and f['threshold'] is None
  assert not (OUT/'m3uc3_confirm_pilot_trials.csv').exists()
