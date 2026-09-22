"""Wired RX idle and explicit retraining without stopping RF or wired TX."""
import json
from chip_model import P,encode_iq
from wired_idle_lifecycle import IdleWireChip
from playback_memory_lifecycle import ready
from whole_chip_lifecycle import expect_rejection


def run(mode):
    c=IdleWireChip(watchdog_s=20e-6,adc_latency_s=20e-9,dac_latency_s=10e-9)
    for i in range(32):c.write_playback(i,encode_iq(.25 if i%2 else -.25,12 if mode==0 else 8))
    c.select_playback(True);ready(c,mode)
    begin=c.time;start=begin+400e-9
    c.schedule(32,start);c.capture(32,start+10e-9)
    c.accept_wire(0x155);c.accept_wire(0x2aa);c.schedule_wire(2,begin+1.2e-6)
    c.incoming_wire([1023]*64,begin);rx=c.live_rx
    while rx.framer.state!='PAYLOAD' or rx.framer.count!=3:c.advance(rx.next_time())
    cut=c.time;c.set_wire_swing(cut,0);c.advance(cut+24*rx.ui)
    assert c.rx_idle_latched and c.state=='active' and c.session.enabled('rf')
    assert not rx.enabled and c.tx.consumed<32
    completed_at_idle=c.adc_completed;accepted=c.rx_accepted;epoch=c.epoch
    expect_rejection(lambda:c.acknowledge_wire_idle(c.time))
    expect_rejection(lambda:c.incoming_wire([1],c.time))
    c.advance(begin+4e-6);c.host_decoder.finish()
    assert c.tx.consumed==32 and c.adc_completed==32>completed_at_idle
    assert c.host_samples==c.adc_words and c.wired_output==[0x155,0x2aa]
    assert c.rx_accepted==accepted and len(c.host_wire)==accepted and c.epoch==epoch
    c.dac_accounting();c.adc_accounting()
    old_host=list(c.host_wire);c.set_wire_swing(c.time,1);c.advance(c.time+24*rx.ui)
    assert c.detector.idle is False and not rx.enabled and c.rx_idle_latched
    expect_rejection(lambda:c.incoming_wire([1],c.time))
    c.acknowledge_wire_idle(c.time)
    c.incoming_wire([0x123,0x267],c.time);assert c.rx_generation==2
    c.advance(c.live_rx.stop+2e-6)
    assert c.host_wire==old_host+[0x123,0x267] and c.epoch==epoch and c.state=='active'
    return dict(mode=mode,adc_completed_at_idle=completed_at_idle,adc_completed_final=c.adc_completed,
        rf_words=len(c.host_samples),wired_tx=c.wired_output,old_rx_words=accepted,
        retrained_rx_words=c.host_wire[len(old_host):],idle_events=c.rx_idle_events,global_epoch=epoch)


def main():
    rows=[run(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        contract=['Default idle response disables only wired RX tracking/framing; complete words retain their order in D2H.',
        'RF conversion, wired TX and shared host service continue; global epoch does not change.',
        'Signal return does not enable decoding. Explicit host idle acknowledgement and new peer training start a new RX generation.'],
        limitations=['Idle/generation notifications use coherent management APIs; hardware status bits and bounded CDC visibility remain unmapped.',
        'Bits sampled during detector latency may form words before idle is declared; protocol-level validation/discard remains external.',
        'No automatic idle-exit training or impedance receiver-detection implementation is claimed.'])
    (P/'evidence/connected-independent-wired-idle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode RF/TX continuation, explicit idle acknowledgement and same-epoch RX retraining')

if __name__=='__main__':main()
