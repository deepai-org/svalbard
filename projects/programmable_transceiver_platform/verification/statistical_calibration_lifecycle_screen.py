"""Repeated shared ADC observations: timing, accounting and cancellation."""
import sys,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from statistical_calibration_lifecycle import StatisticalCalibrationChip
from managed_resources import command
POLICY=dict(planned_samples=64,confidence=.999,noise_sigma_v=.001,
    systematic_bound_v=1/4096,gain_interval=(.95,1.05),assumptions_validated=True)

def create():
    return StatisticalCalibrationChip(calibration_statistics=POLICY,
        adc_latency_s=300e-9,load_capacitance=1e-12,watchdog_s=1e-3)
rows=[]
for chunks in (1,173):
    c=create();assert command(c,'cal_start',48)['accepted']
    start=c.time;end=start+80e-6
    for i in range(chunks):c.advance(start+(end-start)*(i+1)/chunks)
    assert c.cal.state=='done' and c.cal.result['statistical_pass'] and not c.cal.valid
    assert c.maintenance_accounting()==dict(sampled=64,completed=64,cancelled=0,pending=0)
    assert c.adc_reference.samples==64 and c.adc_reference.charge>0
    assert not c.adc_words and not c.host_samples
    status=command(c,'cal_status')['value']
    assert status&(1<<13) and status&(1<<12) and not status&(1<<9)
    assert not status&(1<<14)
    rows.append(dict(chunks=chunks,result=c.cal.result,trace=c.maintenance_trace,
                     reference_charge_c=c.adc_reference.charge))
assert rows[0]['trace']==rows[1]['trace']
# Cancel after partial collection, with the next conversion in flight.
c=create();assert command(c,'cal_start',48)['accepted']
while c.maintenance_completed<7 or c.maintenance_pending is None:
    c.advance(c.time+50e-9)
saved=c.cal.saved_code
c.set_reference(False,c.time+1e-9)
c.advance(c.time+20e-6)
assert c.cal.state=='cancelled' and not c.cal.valid and c.trim.code==saved
assert c.statistics_samples==[] and c.statistics_generation is None
assert c.maintenance_accounting()['pending']==0
assert c.maintenance_cancelled==1
status=command(c,'cal_status')['value']
assert not status&(1<<13) and not status&(1<<9)
cancel_accounting=c.maintenance_accounting()
# Missing physical assumptions must remain visible through the host reply.
c=StatisticalCalibrationChip(calibration_statistics=POLICY|{'assumptions_validated':False},
    adc_latency_s=300e-9,watchdog_s=1e-3)
assert command(c,'cal_start',48)['accepted']
c.advance(c.time+80e-6)
status=command(c,'cal_status')['value']
assert status&(1<<12) and not status&(1<<13) and not status&(1<<9)
report=dict(status='passed',cases=rows,cancel_accounting=cancel_accounting,
    limitations=['Standalone maintenance path; no full coupled three-cap run yet.',
      'Declared statistical budget remains a fixture, not physically qualified.',
      'No frontend noise injected in this lifecycle screen; statistical coverage tested separately.',
      'Host statistical flags are model-level protocol additions; RTL implementation pending.'])
(P/'evidence/statistical-calibration-lifecycle-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print('Passed 64-observation timing subdivision, reference loading, traffic isolation and in-flight cancellation')
