"""Management-owned initial RF coarse search then fine lock and converter traffic."""
import json
from chip_model import P
from coarse_startup_lifecycle import CoarseStartupChip
from managed_resources import command

def run(mode):
    c=CoarseStartupChip(rf_free_offset=-.08,watchdog_s=1e-3,adc_latency_s=30e-9)
    target=2437000000 if mode==0 else 2500000000
    assert not command(c,'configure_mode',mode)['accepted']
    assert command(c,'rf_coarse_start',target)['accepted']
    assert not command(c,'cal_start',48)['accepted']
    c.advance(c.time+30e-6)
    assert c.coarse.qualified and c.coarse.state=='done'
    assert command(c,'rf_coarse_status')['value']&512
    assert command(c,'configure_mode',mode)['accepted']
    c.advance(c.time+40e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    c.capture(16,c.time+100e-9);c.accept_wire(123);c.schedule_wire(1,c.time+100e-9)
    c.advance(c.time+3e-6);c.host_decoder.finish()
    assert c.host_samples==c.adc_words and len(c.adc_words)==16 and c.wired_output==[123]
    return dict(mode=mode,target_hz=target,bank_code=c.rf_pll.bank_code,observations=c.coarse.history,rf_samples=16,wired_word=123)

def main():
    rows=[run(m) for m in (0,1)]
    (P/'evidence/connected-coarse-startup.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Startup-only experimental profile; fresh fine filter is held from construction.',
        'Live coarse retuning/recentering and full bank/process uncertainty are not implemented.',
        'Transport/lock checks only; coarse bank phase-noise and full RF quality need separate validation.']),indent=2)+'\n')
    print('Passed timed coarse startup, shared ownership, fine lock and RF/wired transport')
if __name__=='__main__':main()
