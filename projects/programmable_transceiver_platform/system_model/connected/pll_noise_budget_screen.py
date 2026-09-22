"""Averaged loop prediction for the exact declared finite noise lines.

Frequency noise in Hz integrates to phase radians with magnitude 1/f at each
Fourier offset f. The feedback sensitivity multiplies that free-running phase.
"""
import json,math
import numpy as np
from chip_model import P
from autonomous_pll import AutonomousPLL
from charge_pump_filter import ChargePumpFilter
from oscillator_noise import FrequencyNoise

def main():
    rows=[];noise=FrequencyNoise.seeded(20000.)
    for target in (2412e6,2437e6):
      ratio=target/40e6
      for fraction in (.5,.35,.3,.25,.2,.1):
        g=AutonomousPLL(reference_hz=40e6,divider=ratio,bandwidth_hz=300e3)
        filt=ChargePumpFilter.from_gains(g.kp,g.ki,100e-6,fraction)
        lines=[]
        for freq,amplitude,phase in noise.tones:
            s=2j*math.pi*freq
            impedance=(1+s*filt.r*filt.cs)/(s*filt.total*(1+s/filt.pole))
            loop=100e-6*g.kvco*impedance/(ratio*s)
            sensitivity=abs(1/(1+loop));rms=amplitude/freq*sensitivity/math.sqrt(2)
            lines.append(dict(offset_hz=freq,sensitivity=sensitivity,phase_rms_rad=rms))
        total=math.sqrt(sum(x['phase_rms_rad']**2 for x in lines))
        rows.append(dict(target_hz=target,fast_fraction=fraction,phase_rms_rad=total,lines=lines))
    r=dict(status='characterized',cases=rows,limitations=['Averaged linear infinite-observation variance, not finite-window training/validation error.',
        'Ignores supply pulling, pump/reference noise, fractional spurs and sampled acquisition.',
        'Lower predicted RMS does not imply a usable design: prior smaller-fraction acquisition failures remain.'])
    (P/'evidence/connected-pll-noise-budget.json').write_text(json.dumps(r,indent=2)+'\n')
    for row in rows:print(row['target_hz'],row['fast_fraction'],row['phase_rms_rad'])
if __name__=='__main__':main()
