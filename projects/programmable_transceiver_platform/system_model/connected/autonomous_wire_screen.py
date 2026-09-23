"""Full-chip wired oscillator ownership, four paths, lock faults and recovery."""
import json
import math
from autonomous_wire_lifecycle import AutonomousWireChip
from chip_model import P,encode,encode_iq
from burst_codec import BurstEncoder
from whole_chip_lifecycle import expect_rejection
from sustained_lifecycle import run as sustained


def burst(mode,sign):
    c=AutonomousWireChip(watchdog_s=50e-6);c.configure(mode,0);c.advance(5e-6)
    assert c.state=='active' and c.wire_pll.locked
    rate=250e6 if mode==0 else 312.5e6
    begin=c.time;start=begin+192/rate;wire=[17,801,3,999,0,1023]
    c.descriptor(3);enc=BurstEncoder(2*c.bits,3);iq=[]
    for v in (.5,-.25,.125):iq+=enc.push(encode_iq(v,c.bits))
    iq+=enc.finish()
    c.schedule(3,start);c.schedule_wire(len(wire),start);first=c.next_wire
    assert first>=start and first-start<1/c.channel.rate
    c.capture(3,start+10e-9);c.incoming_wire(wire,begin)
    for i,word in enumerate(encode(mode,wire,iq,0)):
        c.feed(word,c.epoch,begin+(i+1)/rate)
    c.finish_burst();c.advance(first+3.25/c.channel.rate)
    old_word=c.next_wire;old_bit=c.serializer.deadline
    assert c.disturb_wire_tx(c.time,frequency_hz=sign*50000)
    assert (c.next_wire-old_word)*sign<0 and (c.serializer.deadline-old_bit)*sign<0
    word_shift=c.next_wire-old_word;bit_shift=c.serializer.deadline-old_bit
    c.advance(begin+3e-6);c.host_decoder.finish()
    assert c.wired_output==wire and c.host_wire==wire
    assert len(c.host_samples)==3 and c.host_samples==c.adc_words
    assert c.tx.consumed==3 and c.state=='active'
    c.wire_accounting();c.dac_accounting();c.adc_accounting()
    return dict(mode=mode,sign=sign,word_edge_shift_s=word_shift,bit_edge_shift_s=bit_shift,
                words_each_direction=len(wire),rf_samples_each_direction=3)


def controls(mode):
    c=AutonomousWireChip(watchdog_s=50e-6,wire_free_offset=.25)
    c.configure(mode,0);c.advance(10e-6)
    assert c.state=='acquiring' and not c.wire_pll.locked and not c.session.armed
    expect_rejection(lambda:c.schedule_wire(1,c.time+1e-6))
    c=AutonomousWireChip(watchdog_s=50e-6);c.configure(mode,0);c.advance(5e-6)
    for word in (17,801,3):c.accept_wire(word)
    c.schedule_wire(3,c.time+100e-9);start=c.next_wire
    c.advance(start+3.25/c.channel.rate)
    assert c.serializer.active
    # A phase step which skips a pending edge must fault rather than replay.
    assert not c.disturb_wire_tx(c.time,phase_cycles=-.1)
    assert c.state=='draining' and c.events[-1][1]=='wired TX phase discontinuity'
    assert c.wire_accounting()['partial_words_discarded']==1
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    old=c.wire_pll;phase=old.output_phase_cycles;integral=old.integral
    c.configure(1-mode,c.time)
    assert abs(c.wire_pll.output_phase_cycles-phase)<1e-10 and c.wire_pll.integral==integral
    c.advance(c.time+5e-6);assert c.state=='active' and c.wire_pll.locked
    # Large frequency disturbance is detected at a later reference observation.
    c.disturb_wire_tx(c.time,frequency_hz=10e6)
    c.advance(c.next_wire_reference)
    assert c.state=='draining' and c.events[-1][1]=='wired TX clock lock loss'
    return dict(mode=mode,outside_range_blocked=True,skipped_edge_fault=True,
                phase_and_filter_retained_on_mode_change=True,frequency_fault=True)


def management(mode):
    c=AutonomousWireChip(watchdog_s=50e-6)
    token,apply,reply=c.submit('configure_mode',0,c.epoch,c.rx_generation,mode)
    result=c.read_reply(token,reply)
    assert result['accepted'] and c.state=='active' and c.wire_pll.locked
    c.set_reference(False,c.time);old=c.wire_pll.output_phase_cycles
    c.advance(c.time+1e-6)
    assert c.wire_pll.output_phase_cycles>old and not c.wire_pll.locked and c.state=='draining'
    return dict(mode=mode,timed_configuration=True,reference_loss_holds_running_oscillator=True)


def bounded_word_controls(mode,sensitivity=1e5,expect_loss=False):
    from autonomous_pll import SupplyTrajectory
    class BoundedChip(AutonomousWireChip):
        BOUNDED_WIRE_CLOCK=True
    c=BoundedChip(watchdog_s=50e-6);c.configure(mode,0.);c.advance(5e-6)
    assert c.state=='active' and c.wire_pll.locked
    words=[17,801,3,999,0,1023]
    for word in words:c.accept_wire(word)
    start=c.time+1e-9;c.schedule_wire(len(words),start)
    assert math.isinf(c.next_wire) and c.wire_phase_target is None
    steps=0;pending=0
    # The external controller here supplies bounded histories; the integrated
    # analog owner must eventually provide them and split at resolved edges.
    while c.wire_remaining or c.serializer.active:
        end=c.time+.1/c.channel.rate
        trace=SupplyTrajectory((c.time,end),(-.2,-.2))
        old=(c.time,c.wire_pll.time,c.wire_phase_target,c.next_wire,c.serializer.deadline)
        forecast=c.forecast_wire_edges(trace,sensitivity)
        assert old==(c.time,c.wire_pll.time,c.wire_phase_target,c.next_wire,c.serializer.deadline)
        c.commit_wire_forecast(trace,sensitivity,forecast)
        pending+=int(math.isinf(c.next_wire))
        c.advance(end);steps+=1
        assert steps<2000
    if expect_loss:
        assert c.state=='draining' and c.events[-1][1]=='wired TX clock lock loss'
        c.wire_accounting()
        assert c.wire_phase_target is None and c.wire_start_not_before is None and not c.serializer.pending_phase
        return dict(mode=mode,sensitivity_hz_per_v=sensitivity,expected_fault='wired TX clock lock loss',completed_words=len(c.wired_output))
    assert c.wired_output==words and c.serializer.channel.errors==0, (c.wired_output,c.serializer.channel.errors,c.state,c.events[-3:])
    assert c.serializer.accounting()==dict(started=6,completed=6,aborted=0,pending=0)
    c.wire_accounting()
    assert c.wire_times[0]>=start and pending>100
    return dict(mode=mode,sensitivity_hz_per_v=sensitivity,words=len(words),forecast_intervals=steps,pending_word_intervals=pending,
        private_forecast_preserves_state=True,complete_delivery=True,analog_owner_connected=False)

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--bounded-only',action='store_true')
    args=parser.parse_args()
    if args.bounded_only:
        report=dict(status='passed',cases=[bounded_word_controls(m) for m in (0,1)],negative_cases=[bounded_word_controls(m,2e6,True) for m in (0,1)],
            complete_architecture=False,physical_qualification=False,
            limitations=['Prescribed rail histories; integrated analog owner and wired drive-current feedback remain open.'])
        (P/'evidence/connected-bounded-wire-scheduling.json').write_text(json.dumps(report,indent=2)+'\n')
        print(report);return
    rows=[burst(m,s) for m in (0,1) for s in (-1,1)]
    failures=[controls(m) for m in (0,1)]
    commands=[management(m) for m in (0,1)]
    traffic=[]
    for m in (0,1):
        for ppm in (-100,100):
            factory=lambda **kw:AutonomousWireChip(wire_reference_ppm=ppm,**kw)
            traffic.append(sustained(m,ppm,frames=16,chip_factory=factory,matched_reference=True,host_ppm=-ppm))
    report=dict(status='passed',cases=rows,controls=failures,management=commands,sustained=traffic,
                complete_architecture=False,physical_qualification=False,
                limitations=['Wired PLL is connected; RF LO remains driven by the existing phase fixtures.',
                    'Ideal average divider, assumed VCO band/range and PI filter; no fractional spur or stochastic phase-noise model.',
                    'Mode change preserves oscillator phase and integral state but assumes an instantaneous VCO band/divider reconfiguration.',
                    'Reference loss and qualified clock loss retain conservative global-stop policy.',
                    'Payload pacing must match configured reference offset; supply-to-frequency coupling remains open.'])
    (P/'evidence/connected-autonomous-wire.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed autonomous wired full-chip bursts, lock/phase faults, timed configuration, mode reset and sustained four-path traffic')


if __name__=='__main__':main()
