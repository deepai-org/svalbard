"""Trace inherited scheduler order at a real DAC-completion/ADC-aperture tie."""
import json
from chip_model import P,encode_iq
from playback_memory_lifecycle import PlaybackChip,ready

class TracedChip(PlaybackChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.converter_events=[]
        transfer=self.tx.dac_transfer
        def dac(time,value):
            self.converter_events.append((time,'dac_transfer'))
            return transfer(time,value)
        self.tx.dac_transfer=dac
    def convert_adc(self,value):
        self.converter_events.append((self.tx.time,'adc_sample'))
        return super().convert_adc(value)

def main():
    rows=[]
    for mode in (0,1):
        period=1/(40e6 if mode==0 else 20e6)
        c=TracedChip(dac_latency_s=period,adc_latency_s=period,watchdog_s=20e-6)
        bits=12 if mode==0 else 8
        for i in range(32):c.write_playback(i,encode_iq(.2+.1j,bits))
        c.select_playback(True);ready(c,mode)
        start=c.time+100e-9;c.schedule(32,start)
        c.advance(c.next_sample)
        tie=c.dac_pending[0][0]
        c.capture(32,tie)
        natural_aperture=c.next_adc
        # Explicit tie-injection fixture: free clock phase need not coincide.
        # This tests the event dispatcher, not physical clock alignment.
        c.next_adc=tie;c.advance(tie)
        events=[name for t,name in c.converter_events if t==tie]
        assert events==['dac_transfer','adc_sample'],(mode,tie,c.converter_events)
        assert c.adc_sampled==1 and c.dac_pipeline_updates==1
        rows.append(dict(mode=mode,tie_time_s=tie,natural_aperture_s=natural_aperture,events=events))
    report=dict(status='passed',cases=rows,limitations=[
        'Explicit exact-aperture tie injected into PlaybackChip scheduler; not unified analog acquisition/payload validation.',
        'Confirms software convention only; physical aperture skew and reference kickback remain unqualified.'])
    (P/'evidence/connected-converter-tie-order.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
