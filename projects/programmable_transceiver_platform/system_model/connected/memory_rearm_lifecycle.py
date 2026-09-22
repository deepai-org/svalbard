"""Repeated local epochs and explicit memory-validity reset on one chip object."""
import json
from chip_model import P,encode_iq
from management_only_lifecycle import ManagementChip
from whole_chip_lifecycle import expect_rejection

def stop(c):
    x,y=c.tx.filtered,c.tx.received
    c.quiesce(c.time,'local operation complete')
    assert c.tx.filtered==x and c.tx.received==y
    c.acknowledge_host_abort(c.epoch,c.time)
    c.acknowledge_drain(c.epoch,c.time)

def run(first_mode):
    c=ManagementChip();snapshots=[];rows=[]
    for epoch,mode in enumerate((first_mode,1-first_mode,first_mode)):
        bits=12 if mode==0 else 8
        words=[encode_iq(complex((i%7-3)/8,(epoch-1)/4),bits) for i in range(32)]
        for i,w in enumerate(words):c.write_playback(i,w)
        c.select_playback(True);c.configure_capture(True)
        assert c.capture_bank.read(0)==0
        c.configure(mode,c.time)
        while c.state!='active':c.advance(c.next_reference)
        expect_rejection(c.reset_memory)
        begin=len(c.adc_words);start=c.time+100e-9
        c.schedule(32,start);c.capture(32,start+10e-9)
        c.advance(start+32*c.period+1e-6)
        snapshot=[c.read_capture(i,c.time+1e-6) for i in range(32)]
        assert snapshot==c.adc_words[begin:begin+32]
        c.reference_metrics()  # Must compare against this epoch, not first-ever samples.
        if snapshots:assert snapshot!=snapshots[-1]
        snapshots.append(snapshot);rows.append(dict(epoch=c.epoch,mode=mode,adc_start=begin,count=32))
        stop(c)
        assert c.playback==words and c.capture_bank.read(0)==0
    # Memory reset invalidates loaded entries but must not erase analog state.
    x,y=c.tx.filtered,c.tx.received
    c.reset_memory()
    assert all(w is None for w in c.playback) and not c.capture_bank.done
    assert c.tx.filtered==x and c.tx.received==y
    c.write_playback(0,0);c.select_playback(True);c.configure(first_mode,c.time)
    while c.state!='active':c.advance(c.next_reference)
    expect_rejection(lambda:c.schedule(32,c.time+100e-9))
    return dict(initial_mode=first_mode,epochs=rows,partial_reload_rejected=True)

def main():
    rows=[run(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Memory reset is explicit stopped-controller invalidation, not a full asynchronous chip reset waveform.',
        'Management acknowledgement and reads remain coherent transactions, not SPI/CDC equivalence.',
        'RAM bit clearing is not assumed; invalid entries and zero-until-done reads hide stale contents.'])
    (P/'evidence/connected-memory-rearm-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six same-object memory epochs and reset/partial-reload controls')

if __name__=='__main__':main()
