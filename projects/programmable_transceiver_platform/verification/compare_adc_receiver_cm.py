#!/usr/bin/env python3
"""Compare same-history ADC common-mode substitution, not qualification."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1];paths=[P/'evidence/adc-shared-iq-same.json',P/'evidence/adc-shared-iq-receiver-cm.json'];b,c=[json.loads(p.read_text()) for p in paths]
out=dict(status='pending_completed_candidate',completed=False,inputs_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},limitations=['Code agreement is not transfer accuracy or ENOB.','First predecision plate differences include sampling/CDAC history; distinguish from later reset plate states.','Same-history ideal sources and clocks do not bound actual filter loading or I/Q skew.'])
assert b['completed']
if c['completed']:
 assert len(b['frames'])==len(c['frames'])==3;rows=[]
 for old,new in zip(b['frames'],c['frames']):
  assert old['hold_ns']==new['hold_ns'];channels={}
  for label in ('I','Q'):
   x,y=old['channels'][label],new['channels'][label]
   channels[label]=dict(baseline_codes=x['captured_codes'],candidate_codes=y['captured_codes'],codes_equal=x['captured_codes']==y['captured_codes'],candidate_logic_rails=y['all_samples_at_logic_rails'],baseline_predecision_differential_range_v=x['first_predecision_plate_differential_range_v'],candidate_predecision_differential_range_v=y['first_predecision_plate_differential_range_v'],baseline_predecision_cm_range_v=x['first_predecision_plate_common_mode_range_v'],candidate_predecision_cm_range_v=y['first_predecision_plate_common_mode_range_v'])
  assert len(old['shared_reference_decisions'])==len(new['shared_reference_decisions'])==8
  rows.append(dict(hold_ns=new['hold_ns'],channels=channels,largest_reference_span_mean_change_v=max(abs(x['span_sample_mean_v']-y['span_sample_mean_v']) for x,y in zip(old['shared_reference_decisions'],new['shared_reference_decisions'])),candidate_max_reference_span_motion_v=max(x['span_motion_v'] for x in new['shared_reference_decisions']),accounted_supply_power_change_w={k:new['observed_aggregate_supply_power_w'][k]-v for k,v in old['observed_aggregate_supply_power_w'].items()}))
 out.update(status='completed_controlled_comparison',completed=True,frames=rows)
(P/'evidence/adc-receiver-cm-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
