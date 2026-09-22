"""Separate32x24 playback bank, requested by actual DAC deadlines."""
import json
from chip_model import P,encode_iq,decode_iq
from capture_memory_lifecycle import CaptureChip
from whole_chip_lifecycle import expect_rejection

class PlaybackChip(CaptureChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.playback=[None]*32;self.playback_selected=False;self.play_index=0
    def reset_memory(self):
        if self.session.armed:raise ValueError('Memory reset requires stopped/disarmed controller')
        self.capture_bank.enable(False)
        self.capture_start=len(self.adc_words)
        self.playback=[None]*32;self.playback_selected=False;self.play_index=0
        # None models invalid initialization, not physical clearing of SRAM bits.

    def write_playback(self,index,word):
        if self.session.armed:raise ValueError('Playback writes require disarmed state')
        if not isinstance(index,int) or not 0<=index<32 or not isinstance(word,int) or not 0<=word<1<<24:
            raise ValueError('Playback address/width')
        self.playback[index]=word
    def select_playback(self,enabled):
        if self.session.armed:raise ValueError('DAC source frozen while armed')
        self.playback_selected=bool(enabled);self.play_index=0
    def descriptor(self,count):
        if self.playback_selected:raise ValueError('Memory owns DAC; host IQ stream forbidden')
        super().descriptor(count)
    def schedule(self,count,start,ppm=0,jitter_s=0):
        if self.playback_selected:
            if count!=32 or self.play_index or any(w is None for w in self.playback) or self.tx.queue:
                raise ValueError('Playback requires complete fresh32-word bank and empty DAC queue')
            if any(w >= 1<<(2*self.bits) for w in self.playback):
                raise ValueError('Playback word exceeds active IQ format')
        super().schedule(count,start,ppm,jitter_s)
    def provide_dac_sample(self):
        if self.playback_selected:
            assert not self.tx.queue and self.play_index<32
            assert self.tx.accept(decode_iq(self.playback[self.play_index],self.bits))
            self.play_index+=1
    def quiesce(self,time,reason):
        super().quiesce(time,reason)
        self.playback_selected=False;self.play_index=0
        # Engine quiesce keeps loaded data; global memory reset is separate.


def ready(c,mode):
    c.configure(mode,0)
    while c.state!='active':c.advance(c.next_reference)


def run(mode,interrupt):
    c=PlaybackChip(watchdog_s=20e-6)
    bits=12 if mode==0 else 8
    values=[encode_iq(complex((i%7-3)/8,(i%5-2)/8),bits) for i in range(32)]
    for i,w in enumerate(values):c.write_playback(i,w)
    c.select_playback(True);ready(c,mode)
    expect_rejection(lambda:c.write_playback(0,0))
    expect_rejection(lambda:c.select_playback(False))
    expect_rejection(lambda:c.descriptor(1))
    start=c.time+100e-9;c.schedule(32,start)
    c.capture(32,start+10e-9);c.incoming_wire([3,511,97],c.time)
    assert c.play_index==0 and not c.tx.queue
    if interrupt:
        c.advance(start+7.5*c.period)
        assert c.play_index==8 and c.tx.consumed==8
        before=list(c.played);c.set_reference(False,c.time);c.advance(c.time+2e-6)
        assert c.played==before and not c.playback_selected and c.playback==values
    else:
        c.advance(start+32*c.period+2e-6);c.host_decoder.finish()
        assert c.play_index==32 and c.tx.consumed==32 and not c.tx.queue
        assert [z for _,z in c.played]==[decode_iq(w,bits) for w in values]
        assert c.host_samples==c.adc_words and len(c.adc_words)==32
        assert [c.capture_bank.read(i) for i in range(32)]==c.adc_words
        assert c.host_wire==[3,511,97]
        expect_rejection(lambda:c.schedule(32,c.time+100e-9))
    return dict(mode=mode,interrupted=interrupt,played=c.tx.consumed,captured=len(c.adc_words))


def main():
    c=PlaybackChip();c.select_playback(True)
    for i in range(31):c.write_playback(i,0)
    ready(c,0);expect_rejection(lambda:c.schedule(32,c.time+100e-9))
    rows=[run(m,stop) for m in (0,1) for stop in (False,True)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Management access is coherent/disarmed; SPI and loaded-flag CDC timing are not modeled.',
        'Engine quiesce preserves bank initialization; full asynchronous reset behavior remains separate.',
        'Playback completion holds the final DAC level; application mute/rearm policy must be explicit.',
        'MCU-only capture operation and generic analog routing remain open.'])
    (P/'evidence/connected-playback-memory-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four playback/capture cases and loading/ownership/completion controls')

if __name__=='__main__':main()
