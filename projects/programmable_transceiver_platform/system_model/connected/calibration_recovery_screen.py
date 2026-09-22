import json
from pathlib import Path
from chip_model import P
from calibration_adc_lifecycle import AutomaticCalibrationChip
from managed_resources import command

def pending(c):
 while c.maintenance_pending is None:
  c.advance(min(c.cal.next_event if c.cal.next_event is not None else float('inf'),c.maintenance_next))
rows=[]
for abort in ('command','quiesce'):
 c=AutomaticCalibrationChip(observation_error_bound_v=.0003,adc_latency_s=20e-6,watchdog_s=1e-3)
 assert command(c,'cal_start',48)['accepted'];pending(c)
 old_generation=c.cal.generation;old_deadline=c.maintenance_pending[0]
 if abort=='command':assert command(c,'cal_abort')['accepted']
 else:
  c.quiesce(c.time,'test maintenance abort')
  assert c.maintenance_pending is None
  assert command(c,'ack_abort')['accepted'];assert command(c,'ack_drain')['accepted']
 assert c.maintenance_accounting()==dict(sampled=1,completed=0,cancelled=1,pending=0)
 assert command(c,'cal_trim')['value']==2048
 assert command(c,'cal_start',48)['accepted'];c.advance(c.time+70e-6)
 assert c.time>old_deadline and c.cal.generation!=old_generation
 assert c.cal.valid and len(c.maintenance_trace)==1
 assert c.maintenance_accounting()==dict(sampled=2,completed=1,cancelled=1,pending=0)
 status=command(c,'cal_status')['value'];assert status&512 and not status&256
 assert command(c,'cal_trim')['value']==c.trim.code!=2048
 rows.append(dict(abort=abort,status=status,accounting=c.maintenance_accounting(),epoch=c.epoch))
# Missing confidence bound is observable through the same management status.
c=AutomaticCalibrationChip(watchdog_s=1e-3)
assert command(c,'cal_start',48)['accepted'];c.advance(c.time+45e-6)
status=command(c,'cal_status')['value'];assert status&4096 and not status&512
(P/'evidence/connected-calibration-recovery.json').write_text(json.dumps(dict(status='passed',cases=rows,unverified_status=status),indent=2)+'\n')
print(rows)
