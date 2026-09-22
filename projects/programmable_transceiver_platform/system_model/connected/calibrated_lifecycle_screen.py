"""Continuous transport and reference-loss recovery on the unified candidate."""
import json
from chip_model import P
from calibrated_fractional_chip import CalibratedFractionalChip
from managed_resources import command
from continuous_transmit_screen import run as continuous

def prepare(c,target):
    for axis in (0,1):
        assert command(c,'cal_start',48|(axis<<16))['accepted']
        c.advance(c.time+40e-6)
        assert c.cal.valid
    c.configure_rf_carrier(target)

def stream_case(mode,stop):
    chips=[]
    def factory(**kwargs):
        c=CalibratedFractionalChip(trim_offsets_v=(.07,-.03),observation_error_bound_v=.0003,**kwargs)
        prepare(c,2412000000 if mode==0 else 2437000000)
        chips.append(c);return c
    result=continuous(mode,stop,duplex=True,chip_factory=factory,preparation_s=40e-6)
    c=chips[0]
    assert not c.cal.valid and c.cal.state=='cancelled'
    assert c.maintenance_accounting()['completed']==2
    result['rf_clock']=type(c.rf_pll).__name__
    result['calibration_valid_after_stop']=c.cal.valid
    return result

def recovery(mode):
    c=CalibratedFractionalChip(trim_offsets_v=(.07,-.03),observation_error_bound_v=.0003,
        watchdog_s=1e-3,wire_noise_rms_hz=10000,rf_noise_rms_hz=20000)
    prepare(c,2412000000 if mode==0 else 2437000000)
    c.configure(mode,c.time);c.advance(c.time+40e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    codes=[p.code for p in c.trim_targets];phase=c.rf_pll.output_phase_cycles
    c.set_reference(False,c.time);epoch=c.epoch
    assert not c.cal.valid and [p.code for p in c.trim_targets]==codes
    c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    c.advance(c.time+1e-6)
    assert c.rf_pll.output_phase_cycles>phase and not c.rf_pll.locked
    assert command(c,'detect_rearm')['accepted']
    c.set_reference(True,c.time)
    target=2437000000 if mode==0 else 2412000000
    c.configure_rf_carrier(target)
    c.configure(1-mode,c.time);c.advance(c.time+50e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked,(c.state,c.events)
    c.accept_wire(123);c.schedule_wire(1,c.time+100e-9)
    c.capture(16,c.time+100e-9)
    c.advance(c.time+3e-6);c.host_decoder.finish()
    assert c.wired_output[-1]==123 and c.host_samples==c.adc_words and len(c.adc_words)==16
    return dict(initial_mode=mode,recovered_mode=1-mode,target_hz=target,
        initial_epoch=epoch,recovered_epoch=c.epoch,trim_codes=codes,
        calibration_valid=c.cal.valid,rf_samples=16,wired_word=123)

def main():
    rows=[]
    for mode in (0,1):
        for stop in (False,True):
            rows.append(dict(kind='continuous',result=stream_case(mode,stop)))
            print('Passed continuous',mode,stop,flush=True)
        rows.append(dict(kind='reference_recovery',result=recovery(mode)))
        print('Passed reference recovery',mode,flush=True)
    (P/'evidence/connected-calibrated-lifecycle.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Finite 64-frame continuous observation, not an infinite-duration FIFO proof.',
        'Stop/underrun discards unfinished samples; graceful stop remains unresolved.',
        'Calibration bound is an assumed fixture; reference loss invalidates accuracy while retaining applied trims.',
        'Two carrier/mode transitions and one finite noise realization only.']),indent=2)+'\n')
if __name__=='__main__':main()
