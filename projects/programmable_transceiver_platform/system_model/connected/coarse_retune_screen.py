"""Full-chip warm retuning, analog continuity and disrupted centering recovery."""
import json
from chip_model import P
from managed_resources import command
from coarse_retune_lifecycle import CoarseRetuningChip

def quiet(c):
    c.quiesce(c.time,'retune requested')
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    assert c.quiet()
    assert command(c,'detect_rearm')['accepted']

def acquired(c,target,mode):
    assert command(c,'rf_coarse_start',target)['accepted']
    c.advance(c.time+35e-6)
    assert c.coarse.qualified and not c.rf_pll.filter.center_enabled
    assert command(c,'configure_mode',mode)['accepted']
    c.advance(c.time+40e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked

def main():
    rows=[]
    for mode,first,last in ((0,2437000000,2500000000),(1,2500000000,2300000000)):
        c=CoarseRetuningChip(rf_free_offset=-.08,watchdog_s=1e-3)
        acquired(c,first,mode)
        assert not command(c,'rf_coarse_start',last)['accepted']
        quiet(c)
        phase=c.rf_pll.phase;v=c.rf_pll.filter.v
        # Invalid request must not begin discharging the filter.
        assert not command(c,'rf_coarse_start',2200000000)['accepted']
        assert not c.rf_pll.filter.center_enabled
        acquired(c,last,mode)
        assert c.rf_pll.phase>phase and c.coarse.center_history
        c.capture(16,c.time+100e-9);c.accept_wire(123);c.schedule_wire(1,c.time+100e-9)
        c.advance(c.time+3e-6);c.host_decoder.finish()
        assert c.host_samples==c.adc_words and len(c.adc_words)==16 and c.wired_output==[123]
        rows.append(dict(mode=mode,initial_hz=first,target_hz=last,initial_control_v=v,
            centering=c.coarse.center_history,bank=c.rf_pll.bank_code,metrics=c.rf_pll.filter.metrics()))
        quiet(c)
        # Direct apply isolates the exact switching instant from SPI serialization.
        v,w,phase=c.rf_pll.filter.v,c.rf_pll.filter.w,c.rf_pll.phase
        c.execute_management('rf_coarse_start',first,c.time)
        assert (v,w,phase)==(c.rf_pll.filter.v,c.rf_pll.filter.w,c.rf_pll.phase)
        assert c.execute_management('rf_coarse_status',0,c.time)['value']&255==9
        try:c.execute_management('cal_start',48,c.time)
        except ValueError:pass
        else:raise AssertionError('Calibration accepted during centering')
        c.advance(c.time+100e-9)
        assert c.coarse.state=='centering' and c.rf_pll.filter.center_enabled
        if mode==0:
            c.execute_management('rf_coarse_abort',0,c.time)
        else:
            c.set_reference(False,c.time)
            c.set_reference(True,c.time)
            assert c.state=='reset' # Quiet-window loss has no active stream to drain.
        assert c.coarse.state=='cancelled' and not c.rf_pll.filter.center_enabled
        assert not c.rf_pll.present and c.coarse.next_event is None
        c.advance(c.time+3e-6)
        acquired(c,first,mode)
    (P/'evidence/connected-coarse-retune.json').write_text(json.dumps(dict(status='passed',cases=rows,
        controls=['active rejection','invalid target before discharge','switch continuity','shared ownership',
            'guard status','abort and reference-loss cancellation','restart after interrupted guard','RF and wired transport'],
        complete_architecture=False,physical_qualification=False,
        limitations=['Two warm retunes; RF waveform quality after retuning remains untested.',
            'Matched shunt RC and bank/noise bounds remain model assumptions.']),indent=2)+'\n')
    print('Passed managed warm coarse retunes, continuity, cancellation and recovery')
if __name__=='__main__':main()
