import json,cmath,math
from pathlib import Path
from chip_model import P
from calibration_adc_lifecycle import AutomaticCalibrationChip
from fractional_rf_chip import FractionalRFChip
from managed_resources import command
from chip_model import decode_iq
from rf_quality_screen import quality
from calibrated_fractional_chip import CalibratedFractionalChip as Candidate
rows=[]
for mode in (0,1):
 c=Candidate(trim_offsets_v=(.07,-.03),observation_error_bound_v=.0003,adc_latency_s=30e-9,watchdog_s=1e-3)
 results=[]
 for target in (0,1):
  before=c.trim_targets[1-target].code
  assert command(c,'cal_start',48|(target<<16))['accepted'];c.advance(c.time+40e-6)
  assert c.cal.valid and c.trim_targets[1-target].code==before
  assert command(c,'cal_status')['value']>>16==target
  results.append(dict(target=target,code=command(c,'cal_trim',target)['value'],result=c.cal.result))
 assert c.maintenance_accounting()['completed']==2
 target_hz=2412000000 if mode==0 else 2437000000
 c.configure_rf_carrier(target_hz)
 c.configure_rx('external_tone',1,5e6,5e6,.2+.1j,target_hz-2400000000+250000)
 c.configure(mode,c.time);c.advance(c.time+40e-6)
 assert c.state=='active'
 start=c.time+100e-9;c.capture(64,start,gain=1)
 c.advance(start+6e-6);c.host_decoder.finish()
 assert c.host_samples==c.adc_words and len(c.host_samples)==64
 reference=[(.2+.1j)*cmath.exp(2j*math.pi*250000*t) for t in c.sample_times[-64:]]
 measured=[decode_iq(w,c.bits) for w in c.host_samples]
 q=quality(reference,measured)
 assert q['screen_pass'],q
 # Add back the known fixture offsets only as an offline negative control;
 # the calibration controller and quality fit never use this truth.
 negative=quality(reference,[z+(.07-.03j) for z in measured])
 assert not negative['screen_pass']
 rows.append(dict(mode=mode,target_hz=target_hz,calibrations=results,samples=64,
                 quality=q,offset_negative_control=negative,
                 maintenance=c.maintenance_accounting(),state=c.state))
(P/'evidence/connected-calibration-iq.json').write_text(json.dumps(dict(status='passed',cases=rows,limitations=['Two independent post-filter offset targets with shared calibration ownership','64-sample coherent tone, no combined wideband/noise/traffic stress; negative control is an offline offset injection']),indent=2)+'\n')
print(rows)
