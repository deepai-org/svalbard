"""Digital receive reset preserves the external waveform and analog channel state."""
import json,math
from chip_model import P
from live_wired_lifecycle import LiveWireChip,LiveReceiver


def run(mode,phase):
    c=LiveWireChip(watchdog_s=20e-6);c.configure(mode,0)
    while c.state!='active':c.advance(c.next_reference)
    old_words=[0x155,0x2aa,0x139];start=c.time
    c.incoming_wire(old_words,start,phase,100)
    rx=c.live_rx
    while rx.framer.state!='PAYLOAD' or rx.framer.count!=3:c.advance(rx.next_time())
    cut=c.time;state=rx.state;held=rx.held;launched=rx.launch_index;samples=rx.samples
    c.set_reference(False,cut)
    assert rx.state==state and rx.held==held and not rx.enabled and c.live_rx is rx
    dt=(rx.next_time()-cut)/4
    assert dt>0
    c.advance(cut+dt)
    assert abs(rx.state-(held+(state-held)*math.exp(-rx.pole*dt)))<1e-13
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    c.advance(rx.stop+100e-9)
    assert rx.done and rx.launch_index>launched and rx.samples==samples
    assert not c.host_wire and c.rx_accepted==0
    # Independent uninterrupted channel must end at the same analog state.
    reference=LiveReceiver(old_words,1.25e9 if mode==0 else 2.5e9,start,phase,100)
    while not reference.done:reference.step()
    reference.evolve(c.time)
    assert abs(reference.state-rx.state)<1e-13
    c.set_reference(True,c.time);c.configure(mode,c.time)
    while c.state!='active':c.advance(c.next_reference)
    before=rx.state;new_words=[0x321,0x12a,0x17]
    c.incoming_wire(new_words,c.time,-phase,-100)
    assert c.live_rx.state==before and c.live_rx is not rx
    # A zero-length RF capture starts framed D2H service without inventing RF data.
    c.capture(0,c.time+10e-9)
    c.advance(c.live_rx.stop+2e-6);c.host_decoder.finish()
    assert c.host_wire==new_words and not c.host_samples
    return dict(mode=mode,phase_ui=phase,discarded_partial_bits=3,
        disabled_launches=rx.launch_index-launched,disabled_samples=rx.samples-samples,
        reset_state=state,new_frame_initial_state=before,returned_words=c.host_wire)


def main():
    rows=[run(m,p) for m in (0,1) for p in (-.3,.3)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['External fixture holds its last symbol after end; electrical idle is a separate unimplemented contract.',
        'Peer explicitly transmits new training/marker after recovery; arbitrary mid-payload restart is not guaranteed.',
        'Only digital tracking/framing reset is modeled; physical termination/bias changes could alter channel state.',
        'No clock lock qualification or protocol-specific link training is implied.'])
    (P/'evidence/connected-wired-persistent-reset.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four persistent-channel stop/retrain and stale-word exclusion cases')

if __name__=='__main__':main()
