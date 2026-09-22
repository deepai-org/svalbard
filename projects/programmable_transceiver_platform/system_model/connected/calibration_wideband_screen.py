"""Calibrate first, then run the existing combined four-path quality harness."""
import copy,json,hashlib
from pathlib import Path
from chip_model import P
from calibration_adc_lifecycle import AutomaticCalibrationChip
from fractional_rf_chip import FractionalRFChip
from programmable_chip import ProgrammableChip
from managed_resources import command
from fractional_wideband_quality import PROFILE,PROFILE_PATH
from wideband_clock_quality import simulate
from rf_quality_screen import quality

def prepared(base,target,ideal=False,preparation_s=0.,warmup=None,postprepare=None,before_mode=None):
 parent=base if issubclass(base,AutomaticCalibrationChip) else type('CalibrationAdapter',(AutomaticCalibrationChip,base),{})
 class Prepared(parent):
  def __init__(self,**kwargs):
   kwargs['watchdog_s']=PROFILE['watchdog_s']
   super().__init__(trim_offsets_v=(0.,0.) if ideal else (.07,-.03),**kwargs)
   self.calibration_records=[]
  def receiver_value(self):
   if ideal:return super(AutomaticCalibrationChip,self).receiver_value()
   return super().receiver_value()
  def configure(self,mode,time):
   assert time==0 and self.time==0
   if warmup is not None:warmup(self,mode)
   if preparation_s:
    if hasattr(self,'coarse'):
     assert command(self,'rf_coarse_start',target)['accepted']
    self.advance(preparation_s)
    if hasattr(self,'coarse'):assert self.coarse.qualified
   for target_index in (0,1):
    assert command(self,'cal_start',48|(target_index<<16))['accepted']
    self.advance(self.time+40e-6)
    assert self.cal.state=='done'
    assert not self.cal.valid # No physically justified uncertainty bound supplied.
    self.calibration_records.append(dict(target=target_index,code=self.trim.code,result=self.cal.result))
   self.configure_rf_carrier(target)
   # These are only observation logs; preserve all analog and reference state.
   self.calibration_sample_times=list(self.sample_times)
   self.sample_times=[];self.analog_samples=[]
   if before_mode is not None:before_mode(self)
   start=self.time
   super().configure(mode,start)
   self.advance(start+PROFILE['settle_s']);assert self.state=='active'
   self.detect_start(self.time,self.epoch)
   self.advance(start+PROFILE['detection_end_s'])
   assert self.detect_result(self.epoch)['decision']=='present'
   if postprepare is not None:postprepare(self,mode)
  def reference_metrics(self):
   result=super().reference_metrics()
   result['calibration']=dict(records=self.calibration_records,maintenance=self.maintenance_accounting())
   if hasattr(self,'coarse'):
    result['coarse_tuning']=dict(code=self.rf_pll.bank_code,qualified=self.coarse.qualified,observations=self.coarse.history)
   return result
 return Prepared

def main(bandwidth_hz=None,output='connected-calibration-wideband.json'):
 global PROFILE
 PROFILE=copy.deepcopy(PROFILE)
 if bandwidth_hz is not None:PROFILE['rf_pulse_bandwidth_hz']=bandwidth_hz
 rows=[]
 # Two combinations cover both transport modes and two fractional ratios.
 for mode,target in ((0,2412000000),(1,2437000000)):
  experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=8000
  experiment['source_offset_hz']+=target-2400000000
  common=dict(experiment=experiment,service_pauses={16:16})
  baseline,times,reference=simulate(mode,False,chip_class=prepared(ProgrammableChip,target,True),
    chip_options=dict(load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0),**common)
  shift=target-2400000000
  blockers=[(a,f+shift) for a,f in PROFILE['blockers']]
  traffic,actual,measured=simulate(mode,True,chip_class=prepared(FractionalRFChip,target),
    blockers=blockers,cubic=PROFILE['cubic'],
    chip_options=dict(rf_pulse_bandwidth_hz=PROFILE['rf_pulse_bandwidth_hz'],**PROFILE['shared_reference'],**PROFILE['coupling']),**common)
  assert times==actual and len(reference)==len(measured)
  assert actual[-1]<(experiment['source_count']-1)/experiment['source_rate_hz']
  q=quality(reference,measured)
  rows.append(dict(mode=mode,target_hz=target,quality=q,traffic=traffic,reference_traffic=baseline,experiment=experiment))
  print(mode,target,q['corrected_relative_rms'],q['screen_pass'],flush=True)
  report=dict(status=('passed' if len(rows)==2 else 'running') if all(r['quality']['screen_pass'] for r in rows) else 'failed',cases=rows,
    source_profile_sha256=hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),
    rf_pulse_bandwidth_hz=PROFILE['rf_pulse_bandwidth_hz'],
    complete_architecture=False,physical_qualification=False,
    limitations=['Two mode/carrier combinations, one source/noise seed and positive coupling.',
    'Source record extended to cover actual calibration and acquisition time; all analog state retained.',
    'Calibration completion remains unverified without a justified observer bound; useful waveform quality is tested separately.',
    '10% waveform screen remains provisional.'])
  (P/'evidence'/output).write_text(json.dumps(report,indent=2)+'\n')
 assert len(rows)==2 and all(r['quality']['screen_pass'] for r in rows)

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument('--bandwidth-hz',type=float)
 parser.add_argument('--output',default='connected-calibration-wideband.json')
 args=parser.parse_args();main(args.bandwidth_hz,args.output)
