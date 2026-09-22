"""Explicit host abort barrier and same-object recovery at every frame position."""
import json
from chip_model import P
from wired_return_lifecycle import DuplexChip
from whole_chip_lifecycle import expect_rejection

def run(mode,position):
    c=DuplexChip(watchdog_s=20e-6);c.configure(mode,0);c.advance(c.acquisition_s)
    c.capture(3,c.time+1e-9)
    # Second return frame: capture has progressed and frame position is explicit.
    for _ in range(64+position):c.advance(c.next_return)
    assert c.host_receiver.pos==position
    prefix=list(c.host_samples);old_epoch=c.epoch
    c.set_reference(False,c.time)
    stopped_pos=c.host_receiver.pos
    c.advance(c.time+137e-9)  # Arbitrary management latency; no return clock activity.
    assert c.host_receiver.pos==stopped_pos and c.host_samples==prefix
    expect_rejection(lambda:c.acknowledge_drain(old_epoch,c.time))
    expect_rejection(lambda:c.acknowledge_host_abort(old_epoch+1,c.time))
    c.acknowledge_host_abort(old_epoch,c.time)
    assert c.host_receiver.pos==0 and c.host_decoder is None
    c.acknowledge_drain(old_epoch,c.time)
    expect_rejection(lambda:c.acknowledge_host_abort(old_epoch,c.time))
    c.set_reference(True,c.time);c.configure(1-mode,c.time)
    c.advance(c.time+c.acquisition_s)
    c.capture(3,c.time+1e-9)
    c.incoming_wire([511,17,803],c.time)
    c.advance(c.time+3e-6);c.host_decoder.finish()
    assert c.host_samples==prefix+[0,0,0]
    assert c.host_wire==[511,17,803]
    return dict(initial_mode=mode,frame_position=position,old_samples_delivered=len(prefix),
                new_samples_delivered=3,new_epoch=c.epoch)

def main():
    rows=[run(m,pos) for m in (0,1) for pos in range(64)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Acknowledgements are coherent management events; serialized SPI, CDC latency and corrupt messages remain unmodeled.',
        'Restart assumes external word-clock alignment at a new frame boundary; pin-level acquisition is not proved.',
        'Already delivered samples remain visible; no rollback or payload quarantine is implied.',
        'Recovery RF input is zero; modulated recovery and sustained traffic remain separate work.'])
    (P/'evidence/connected-return-epoch-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed128 frame-position host-abort and mode-recovery cases')

if __name__=='__main__':main()
