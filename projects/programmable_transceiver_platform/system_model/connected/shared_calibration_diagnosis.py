"""Reproduce failed mode1 preparation without rerunning ideal payload traffic."""
import json
from chip_model import P
from shared_phase_loaded_tx import SharedPhaseLoadedTxChip
from calibration_wideband_screen import prepared,PROFILE
from managed_resources import command

class RecordedChip(SharedPhaseLoadedTxChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.detector_readouts=[]
    def _sample_detector(self,power,time):
        value,invalid=super()._sample_detector(power,time)
        self.detector_readouts.append(dict(time_s=time,input_power=power,decoded_power=value,invalid=invalid))
        return value,invalid

def diagnose(c):
    deadline=c.time+50e-6
    while True:
        status=command(c,'tx_cal_status');assert status['accepted']
        if status['value']&(1<<10):break
        if c.time>=deadline:raise TimeoutError('Calibration readiness')
    reply=command(c,'tx_cal_start');assert reply['accepted']
    c.advance(c.time+20e-6)
    report=dict(state=c.tx_cal.state,reason=getattr(c.tx_cal,'reason',None),
        powers=c.tx_cal.powers,samples=c.tx_adc_samples,time_s=c.time,
        adc_diagnostics=c.adc_diagnostics,detector_power=c.tx_detector.value,readouts=c.detector_readouts,
        limitations=['Preparation-only reproduction of mode1 failure; no traffic quality claim.'])
    (P/'evidence/shared-calibration-mode1-signed-readout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report,flush=True)
    assert c.tx_cal.state=='ready',report
    assert command(c,'tx_cal_commit',reply['value'])['accepted']
    raise SystemExit(0)

if __name__=='__main__':
    import copy
    from wideband_clock_quality import simulate
    cls=prepared(RecordedChip,2437000000,False,50e-6,before_mode=diagnose)
    experiment=copy.deepcopy(PROFILE['experiment'])
    experiment['source_count']=18000
    experiment['source_offset_hz']+=37000000
    options=dict(tx_relative_gain=True,rf_free_offset=-.08,coarse_noise_bound_hz=80000,
        rf_fast_fraction=.30,rf_pulse_bandwidth_hz=300e3,
        **PROFILE['shared_reference'],**PROFILE['coupling'])
    simulate(1,True,chip_class=cls,chip_options=options,experiment=experiment,
        blockers=[(a,f+37000000) for a,f in PROFILE['blockers']],cubic=PROFILE['cubic'])
