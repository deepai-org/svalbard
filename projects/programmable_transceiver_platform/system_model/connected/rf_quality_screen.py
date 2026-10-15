"""Standalone held-out waveform metric; explicit 10% diagnostic, not protocol acceptance."""
import math

BUDGET=.10


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


def controls():
    x=[complex(math.cos(i*.7),math.sin(i*.7)) for i in range(128)]
    assert quality(x,x)['corrected_relative_rms']==0
    q=quality(x,[(.8+.2j)*z for z in x]);assert q['screen_pass'] and q['corrected_relative_rms']<1e-14
    assert not quality(x,[0j]*len(x))['screen_pass']
    assert not quality(x,[.1*z for z in x])['screen_pass']
    y=x[:32]+[-z for z in x[32:]]
    q=quality(x,y);assert q['corrected_relative_rms']>1.99 and not q['screen_pass']


if __name__=="__main__":
    controls()
    print("Held-out waveform metric controls passed; no chip integration exercised.")
