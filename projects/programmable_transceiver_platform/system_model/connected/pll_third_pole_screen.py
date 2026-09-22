"""Loaded three-capacitor passive filter frequency screen, not edge-loop closure.

Pump node v: Cf to ground, R to Cs node w, R3 to VCO node u with C3.
All three node loads are included; no ideal buffer or unloaded RC multiplication.
"""
import json,math
import numpy as np
from chip_model import P
from autonomous_pll import AutonomousPLL
from charge_pump_filter import ChargePumpFilter


def transfer(s,f,r3,c3):
    a=1/f.r;b=1/r3
    Y=np.array([[s*f.cf+a+b,-a,-b],[-a,s*f.cs+a,0],[-b,0,s*c3+b]],complex)
    return np.linalg.solve(Y,np.array([1,0,0],complex))[2]

if __name__=='__main__':
    rows=[]
    g=AutonomousPLL(reference_hz=40e6,divider=60,bandwidth_hz=450e3)
    f=ChargePumpFilter.from_gains(g.kp,g.ki,100e-6,.3)
    freq=np.geomspace(100,100e6,4000);s=2j*np.pi*freq
    original=(1+s*f.r*f.cs)/(s*f.total*(1+s/f.pole))
    for c3 in (1e-12,3e-12,10e-12):
        for pole in (.5e6,1e6,2e6,4e6):
            r3=1/(2*math.pi*pole*c3)
            z=np.array([transfer(v,f,r3,c3) for v in s]);loop=100e-6*g.kvco*z/((2437/40)*s)
            phase=np.unwrap(np.angle(loop));cross=np.where(np.diff((abs(loop)>1).astype(int))!=0)[0]
            margins=[float(180+phase[i]*180/math.pi) for i in cross]
            # Noise contribution from original finite lines, interpolated frequency response.
            offsets=np.arange(1,9)*250e3
            sensitivity=np.interp(offsets,freq,abs(1/(1+loop)))
            noise=float(np.sqrt(np.sum((10000/offsets*sensitivity)**2/2)))
            rows.append(dict(c3_f=c3,r3_ohm=r3,nominal_unloaded_pole_hz=pole,
                crossover_count=len(cross),minimum_sampled_phase_margin_deg=min(margins,default=None),
                predicted_noise_rms_rad=noise,
                transimpedance_ratio_at_4mhz=float(np.interp(4e6,freq,abs(z/original)))))
    report=dict(status='diagnostic_only',cases=rows,limitations=[
        'Loaded linear nodal solve; excludes fractional edge dynamics, pump compliance, resistor noise and acquisition.',
        'Sampled crossover estimates only; neither rigorous stability proof nor usable full-chip result.',
        '4MHz attenuation is illustrative; actual divider spectrum has multiple lines.',
        'Added capacitor changes low-frequency integral gain; original PI mapping is not preserved.'])
    (P/'evidence/pll-third-pole-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    for row in rows:print(row)
