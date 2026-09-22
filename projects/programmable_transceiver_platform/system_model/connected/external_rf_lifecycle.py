"""Independent externally modulated RF envelope, concurrent with local TX and wired paths."""
from collections import deque
import json,math
from chip_model import P
from combined_platform import PlatformChip
from rf_modulated_quality import Multicarrier
from rf_selectivity_screen import butterworth_order
from sustained_lifecycle import run

class ExternalChip(PlatformChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.external_events=deque();self.external_updates=0
    def external_source(self,values,start,period,offset_hz=0.):
        if self.session.armed or not math.isfinite(start) or start<self.time or not math.isfinite(period) or period<=0 or not math.isfinite(offset_hz):
            raise ValueError('Invalid external source schedule')
        values=list(values)
        if not values or not all(math.isfinite(v.real) and math.isfinite(v.imag) for v in values):
            raise ValueError('Invalid external waveform')
        self.tx.rx_route='external_tone';self.tx.external_amplitude=0j;self.tx.external_frequency=offset_hz
        self.external_events=deque((start+i*period,complex(v)) for i,v in enumerate(values))
    def advance(self,time):
        while self.external_events and self.external_events[0][0]<=time:
            when,value=self.external_events.popleft()
            super().advance(when)
            self.tx.external_amplitude=value;self.external_updates+=1
        super().advance(time)


def simulate(mode,variant):
    chips=[];source=Multicarrier(seed=816);values=source(1600,40e6)
    order,cutoff=butterworth_order(8e6,20e6,1,30)
    def factory(**kwargs):
        c=ExternalChip(adc_latency_s=30e-9,dac_latency_s=20e-9,**kwargs)
        c.tx.set_butterworth(order,cutoff)
        c.configure_lo(tx_offset_hz=3e6 if variant=='tx_changed' else 0,
                       tx_phase_rad=.7 if variant=='tx_changed' else 0,
                       rx_phase_rad=.15 if variant=='rx_changed' else 0)
        c.external_source(values,0,25e-9,offset_hz=250e3)
        chips.append(c);return c
    # Different source data and TX LO must not alter an uncoupled external RX path.
    tx_wave=lambda n,fs:[complex(-.6 if variant=='tx_changed' else .2,0)]*n
    row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100,waveform=tx_wave)
    c=chips[0];assert c.external_updates>1000 and c.tx.consumed==len(c.adc_words)
    c.adc_accounting();c.dac_accounting()
    row.update(variant=variant,external_source=source.metadata,external_updates=c.external_updates,
               external_carrier_offset_hz=250e3,tx_last_held_real=c.tx.held.real)
    return row


def main():
    # External stimulus remains an independent environment while the chip is reset.
    c=ExternalChip();c.external_source([.1,.2,-.1],0,25e-9)
    c.advance(100e-9)
    assert c.state=='reset' and c.external_updates==3 and c.tx.external_amplitude==-.1
    assert c.tx.received!=0 and not c.adc_words
    rows=[]
    for mode in (0,1):
        baseline=simulate(mode,'baseline');tx=simulate(mode,'tx_changed');rx=simulate(mode,'rx_changed')
        assert baseline['adc_sha256']==tx['adc_sha256']
        assert baseline['tx_last_held_real']!=tx['tx_last_held_real']
        assert baseline['adc_sha256']!=rx['adc_sha256']
        rows.extend((baseline,tx,rx))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['External source is a held complex-envelope waveform with250kHz carrier offset; no physical RF source matching or images.',
        'Source timing is independent of local DAC timing, but this screen does not bound arbitrary source/sample frequency mismatch.',
        'Coupling is disabled for the TX-independence control; this is not a claim of physical TX/RX isolation.',
        'This test proves independent reception and transport, not a carrier-recovery modem or packet/EVM qualification.',
        'Source updates continue across chip lifecycle changes and hold the last value when exhausted.'])
    (P/'evidence/connected-external-rf-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six independent RF source / TX isolation / RX LO response cases with live wired traffic')

if __name__=='__main__':main()
