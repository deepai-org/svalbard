"""Finite playback/capture without high-speed host service clocks."""
import json,math
from chip_model import P,encode_iq
from playback_memory_lifecycle import PlaybackChip,ready
from whole_chip_lifecycle import expect_rejection

class ManagementChip(PlaybackChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.streaming_watchdog_enabled=False
    def capture(self,count,start,**kwargs):
        if count!=32:raise ValueError('Local capture requires32 samples')
        if self.capture_bank.done:raise ValueError('Capture bank requires disarmed rearm')
        super().capture(count,start,**kwargs)
        self.next_return=math.inf
    def queue_adc_words(self,words,time):
        # Explicit local-only routing: samples have already reached capture RAM.
        # Transport words produced by the shared encoder are not sent to D2H.
        return True
    def feed(self,word,epoch,time):
        raise ValueError('High-speed host stream disabled in management-only mode')
    def incoming_wire(self,*args,**kwargs):
        raise ValueError('Wired capture routing is not selected in this local RF mode')
    def read_capture(self,index,time):
        self.advance(time)
        return self.capture_bank.read(index)


def run(mode,abort=False):
    c=ManagementChip()
    bits=12 if mode==0 else 8
    for i in range(32):c.write_playback(i,encode_iq(complex((i%7-3)/8,.25),bits))
    c.select_playback(True);ready(c,mode)
    expect_rejection(lambda:c.feed(0,c.epoch,c.time))
    start=c.time+100e-9;c.schedule(32,start);c.capture(32,start+10e-9)
    assert c.read_capture(0,c.time)==0
    if abort:
        c.advance(start+7.5*c.period);assert c.capture_bank.count>0
        c.set_reference(False,c.time)
        assert not c.capture_bank.done and c.read_capture(0,c.time+100e-6)==0
        return dict(mode=mode,aborted=True,partial_data_hidden=True)
    c.advance(start+32*c.period+1e-6)
    assert c.capture_bank.done and c.tx.consumed==32 and any(c.adc_words)
    expect_rejection(lambda:c.capture(32,c.time+100e-9))
    received=[c.read_capture(i,c.time+10e-6) for i in range(32)]
    assert received==c.adc_words and c.state=='active'
    assert c.return_ticks==0 and not c.host_samples and not c.return_queue and not c.return_frame
    assert c.transitions==0 and c.return_transitions==0
    # No streaming watchdog is required, but reference loss still mutes/faults.
    c.set_reference(False,c.time)
    assert c.state=='draining' and c.tx.held==0
    return dict(mode=mode,management_read_count=32,read_duration_s=320e-6,
                streaming_word_edges=c.return_ticks,captured=len(received))


def main():
    rows=[run(m,stop) for m in (0,1) for stop in (False,True)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Management reads are coherent timed transactions, not SPI bit/CDC simulation.',
        'Management readiness reuses session host_ready as abstract controller readiness; no high-speed host data is required.',
        'RF input is the existing external loopback fixture; arbitrary external RF source selection remains open.',
        'Playback finishes holding its final value until explicit quiesce; global memory reset/rearm still needs full coverage.'])
    (P/'evidence/connected-management-only-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four management-only capture/playback/readout and fault cases')

if __name__=='__main__':main()
