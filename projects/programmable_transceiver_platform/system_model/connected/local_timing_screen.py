"""Command-driven relative converter timing and atomic invalid-start rejection."""
import json
import math
from chip_model import P
from timed_management import ManagedChip
from managed_resources import command
from managed_local_run import prepared


def run(mode, ticks):
    c=ManagedChip()
    assert command(c,'configure_local_timing',ticks & 0xffff)['accepted']
    assert c.local_rx_offset_s == ticks*c.control_period
    old=c.local_rx_offset_s
    assert not command(c,'configure_local_timing',1<<16)['accepted']
    assert c.local_rx_offset_s==old
    # Configure the same setting before arming a fully provisioned converter run.
    c=prepared_with_timing(mode,ticks)
    before=c.local_rx_offset_s
    assert not command(c,'configure_local_timing',0)['accepted']
    assert c.local_rx_offset_s==before
    token,apply,reply=c.submit('start_local',c.time,c.epoch,c.rx_generation,3|(32<<2)|(8<<18))
    c.advance(apply)
    tx_start=c.next_sample;rx_start=c.next_adc
    assert math.isclose(rx_start-tx_start,ticks*c.control_period,abs_tol=1e-18)
    assert c.tx.consumed==c.adc_sampled==0
    assert c.read_reply(token,reply)['accepted']
    c.host_decoder.finish()
    assert c.tx.consumed==c.adc_sampled==32
    assert c.host_samples==c.adc_words and len(c.host_samples)==32
    assert c.capture_bank.done
    return dict(mode=mode,offset_ticks=ticks,tx_start_s=tx_start,rx_start_s=rx_start,samples=32)


def prepared_with_timing(mode,ticks):
    # Share the real provisioning routine, inserting the setting before its arm.
    return prepared(mode, timing_ticks=ticks)


def invalid_start(mode):
    c=prepared_with_timing(mode,-8)
    before=(c.next_sample,c.next_adc,c.remaining,c.adc_left,c.play_index)
    result=command(c,'start_local',3|(32<<2)|(4<<18))
    assert not result['accepted']
    assert before==(c.next_sample,c.next_adc,c.remaining,c.adc_left,c.play_index)
    assert c.tx.consumed==c.adc_sampled==0
    return dict(mode=mode,rejection=result['reason'],atomic=True)


def main():
    rows=[run(m,t) for m in (0,1) for t in (-4,0,4)]
    failures=[invalid_start(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,invalid_start=failures,
                complete_architecture=False,physical_qualification=False,
                contract=['Signed16-bit relative RX offset in control-clock periods, configured while disarmed; upper16 bits reserved.',
                          'Default remains10ns for prior profiles; an explicit zero setting means simultaneous converter deadlines.',
                          'Both directions are preflighted atomically, including future-start validity.'],
                limitations=['Control-period resolution is a mathematical scheduling contract, not a verified clock-phase implementation.',
                             'External trigger routing and continuous run control remain open.'])
    (P/'evidence/connected-local-timing.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six relative-timing runs and two atomic invalid-start cases')

if __name__=='__main__':main()
