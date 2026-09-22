"""Held-out waveform distortion against a matched ideal envelope/quantizer path."""
import json,math
from chip_model import P,decode_iq
from rf_phase_lifecycle import PhaseChip,trace
from sustained_lifecycle import run

BUDGET=.10  # Provisional 10% incremental waveform error; not a modem specification.


def quality(reference,measured):
    if len(reference)!=len(measured) or len(reference)<16:
        raise ValueError('Aligned nontrivial reference and measured records required')
    if not all(math.isfinite(z.real) and math.isfinite(z.imag) for z in reference+measured):
        raise ValueError('Nonfinite waveform')
    split=len(reference)//4
    power=sum(abs(x)**2 for x in reference[:split])
    if power==0:raise ValueError('No calibration signal')
    gain=sum(x.conjugate()*y for x,y in zip(reference[:split],measured[:split]))/power
    x=reference[split:];y=measured[split:];power=sum(abs(v)**2 for v in x)
    if power==0:raise ValueError('No validation signal')
    raw=math.sqrt(sum(abs(b-a)**2 for a,b in zip(x,y))/power)
    residual=math.sqrt(sum(abs(b-gain*a)**2 for a,b in zip(x,y))/power)
    corrected=residual/abs(gain) if abs(gain)>1e-12 else None
    gain_ok=.5<=abs(gain)<=2
    return dict(calibration_samples=split,validation_samples=len(x),gain_real=gain.real,gain_imag=gain.imag,
        gain_magnitude=abs(gain),raw_relative_rms=raw,corrected_relative_rms=corrected,
        gain_in_screen_range=gain_ok,screen_budget=BUDGET,
        screen_pass=gain_ok and corrected is not None and corrected<=BUDGET)


class ObservedChip(PhaseChip):
    def __init__(self,**kwargs):super().__init__(**kwargs);self.sample_times=[];self.sample_values=[]
    def convert_adc(self,value):
        self.sample_times.append(self.tx.time);self.sample_values.append(value)
        return super().convert_adc(value)


def simulate(mode,sign,setting,blocker_frequencies=(10e6,20e6),rx_filter=None,waveform=None,phase_scale=1.,analog_reference=False):
    if not math.isfinite(phase_scale) or phase_scale<0:raise ValueError('Invalid phase scale')
    if analog_reference and setting!='ideal':raise ValueError('Analog reference requires ideal path')
    chips=[]
    def factory(**kwargs):
        options=dict(load_capacitance=0) if setting=='ideal' else dict(
            coupling_per_v=sign,return_charge_per_transition=50e-15,dac_coupling_per_v=sign,
            frontend=dict(gain_error=sign*.03,phase_error=sign*.03,saturation=.8,noise_rms=.001,seed=800))
        c=ObservedChip(**options,**kwargs)
        if rx_filter is not None:c.tx.set_butterworth(*rx_filter)
        if setting!='ideal':
            c.configure_rf_input(() if setting=='no_blockers' else tuple((.1,f) for f in blocker_frequencies),sign*.05,envelope_limit=1.5)
            scale=phase_scale*(8 if setting=='severe_phase' else (0 if setting=='no_phase' else 1))
            c.schedule_lo([(t,tx*scale,rx*scale,tf,rf) for t,tx,rx,tf,rf in trace(False)])
        chips.append(c);return c
    row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100,
            disturbance_sign=sign,service_pauses={48:16},waveform=waveform)
    c=chips[0]
    decoded=[decode_iq(w,c.bits) for w in c.adc_words]
    if setting=='ideal':
        row['ideal_adc_quantization_quality']=quality(c.sample_values,decoded)
        limit=1/(1 << c.bits)
        assert all(abs(a.real-b.real)<=limit+1e-15 and abs(a.imag-b.imag)<=limit+1e-15
                   for a,b in zip(c.sample_values,decoded))
    return row,c.sample_times,c.sample_values if analog_reference else decoded


def controls():
    x=[complex(math.cos(i*.7),math.sin(i*.7)) for i in range(128)]
    assert quality(x,x)['corrected_relative_rms']==0
    q=quality(x,[(.8+.2j)*z for z in x]);assert q['screen_pass'] and q['corrected_relative_rms']<1e-14
    assert not quality(x,[0j]*len(x))['screen_pass']
    assert not quality(x,[.1*z for z in x])['screen_pass']
    y=x[:32]+[-z for z in x[32:]]
    q=quality(x,y);assert q['corrected_relative_rms']>1.99 and not q['screen_pass']


def main():
    controls();rows=[]
    for mode in (0,1):
        for sign in (-1,1):
            baseline,times,reference=simulate(mode,sign,'ideal')
            for setting in ('combined','severe_phase','no_blockers','no_phase'):
                traffic,t,values=simulate(mode,sign,setting)
                assert times==t  # No post-hoc time alignment can hide oscillator error.
                q=quality(reference,values)
                if setting=='severe_phase':assert not q['screen_pass']
                rows.append(dict(mode=mode,sign=sign,setting=setting,quality=q,
                    traffic=traffic,reference_adc_sha256=baseline['adc_sha256']))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Provisional10% incremental single-tone waveform error is not Wi-Fi EVM or protocol compliance.',
        'Reference retains intended filter response, converter quantization and identical sample-clock events; impairment increment is measured.',
        'One complex gain fitted on first quarter is frozen for the remaining samples; no adaptive carrier recovery or equalizer.',
        'Passing a test means classification worked; individual signal-quality screens may fail despite lossless transport.',
        'Physical noise, gain, LO and blocker parameters remain assumptions; these results do not qualify GF180.'])
    (P/'evidence/connected-rf-quality-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in rows:print(r['mode'],r['sign'],r['setting'],r['quality']['corrected_relative_rms'],r['quality']['screen_pass'])

if __name__=='__main__':main()
