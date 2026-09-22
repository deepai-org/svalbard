import json
from pathlib import Path
from chip_model import P
from calibration_adc_lifecycle import AutomaticCalibrationChip
from managed_resources import command
rows=[]
for chunks in (1,61):
 for bound in (None,.0003):
  c=AutomaticCalibrationChip(observation_error_bound_v=bound,load_capacitance=1e-12,adc_latency_s=300e-9,watchdog_s=1e-3)
  assert command(c,'cal_start',48)['accepted']
  begin=c.time;end=begin+40e-6
  for i in range(chunks):c.advance(begin+(end-begin)*(i+1)/chunks)
  assert c.cal.state=='done' and c.cal.valid==(bound is not None)
  assert c.state=='reset' and not c.session.armed
  assert c.adc_reference.samples==1 and c.adc_reference.charge>0
  assert c.adc_diagnostics['conversions']==1
  assert c.maintenance_accounting()==dict(sampled=1,completed=1,cancelled=0,pending=0)
  assert not c.adc_words and not c.host_samples
  rows.append(dict(chunks=chunks,declared_error_bound_v=bound,trace=c.maintenance_trace,
                   reference_charge_c=c.adc_reference.charge,accounting=c.maintenance_accounting()))
assert rows[0]['trace']==rows[2]['trace'] and rows[1]['trace']==rows[3]['trace']
# Stop reference during a long conversion: result must not survive cancellation.
c=AutomaticCalibrationChip(adc_latency_s=10e-6,watchdog_s=1e-3)
assert command(c,'cal_start',48)['accepted']
while c.maintenance_pending is None:
 c.advance(min(c.cal.next_event if c.cal.next_event is not None else float('inf'),c.maintenance_next))
c.set_reference(False,c.time+1e-6)
c.advance(c.time+20e-6)
assert c.cal.state=='cancelled' and c.trim.code==2048 and not c.maintenance_trace
assert c.maintenance_accounting()==dict(sampled=1,completed=0,cancelled=1,pending=0)
report=dict(status='passed',cases=rows,reference_loss_accounting=c.maintenance_accounting(),
 limitations=['Separate maintenance conversion scheduler shares actual converter transfer/reference but not normal host-return pipeline.',
 '12-bit maintenance mode and independent zero-input route are architecture candidates.',
 'Total observer uncertainty must be supplied explicitly; 300uV is a test assumption, not an established physical bound.',
 'Calibration target is a static offset fixture; full RF target insertion remains.'])
(P/'evidence/connected-calibration-adc.json').write_text(json.dumps(report,indent=2)+'\n')
print('Passed automatic ADC observation, reference loading, subdivision and in-flight cancellation')
