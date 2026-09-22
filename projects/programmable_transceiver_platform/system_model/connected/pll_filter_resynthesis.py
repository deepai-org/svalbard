"""Bounded passive-filter search; linear screening only, not PLL qualification."""
import json
import numpy as np
from chip_model import P
from pll_third_pole_screen import transfer
from types import SimpleNamespace


def impedance(s,r,cf,cs,r3,c3):
    return 1/(s*cf+s*cs/(1+s*r*cs)+s*c3/(1+s*r3*c3))/(1+s*r3*c3)

if __name__=='__main__':
    rng=np.random.default_rng(20260921)
    freq=np.geomspace(100,1e9,1800);s=2j*np.pi*freq;gain=100e-6*200e6/(2437/40)
    offsets=np.arange(1,9)*250e3;sn=2j*np.pi*offsets
    candidates=[]
    for index in range(12000):
        r,cf,cs,r3,c3=10**rng.uniform(np.log10([2e3,1e-12,10e-12,2e3,.5e-12]),np.log10([150e3,50e-12,250e-12,300e3,30e-12]))
        z=impedance(s,r,cf,cs,r3,c3);loop=gain*z/s
        cross=np.flatnonzero(np.diff((abs(loop)>1).astype(int)))
        if len(cross)!=1:continue
        i=cross[0]
        # The two low-frequency integrators approach -180 degrees, never +180.
        # Anchor the unwrap branch there before evaluating crossover margin.
        phase=np.unwrap(np.angle(loop))
        phase-=2*np.pi*round((phase[0]+np.pi)/(2*np.pi))
        pm=180+phase[i]*180/np.pi
        if pm<45 or not 200e3<freq[i]<1.5e6:continue
        noise=np.sqrt(np.sum((10000/offsets*abs(1/(1+gain*impedance(sn,r,cf,cs,r3,c3)/sn)))**2/2))
        # Rank using noise only after a damping constraint; retain ripple metric separately.
        candidates.append(dict(r_ohm=r,cf_f=cf,cs_f=cs,r3_ohm=r3,c3_f=c3,
            sampled_phase_margin_deg=pm,crossover_hz=freq[i],predicted_noise_rms_rad=noise,
            transimpedance_4mhz_ohm=float(abs(impedance(2j*np.pi*4e6,r,cf,cs,r3,c3)))))
    candidates.sort(key=lambda v:v['predicted_noise_rms_rad'])
    # Keep the noise/ripple Pareto frontier instead of selecting on noise alone.
    frontier=[];lowest_ripple=float('inf')
    for row in candidates:
        if row['transimpedance_4mhz_ohm']<lowest_ripple:
            frontier.append(row);lowest_ripple=row['transimpedance_4mhz_ohm']
    for row in candidates[:10]:
        f=SimpleNamespace(r=row['r_ohm'],cf=row['cf_f'],cs=row['cs_f'])
        for hz in (1e3,1e6,4e6):
            ss=2j*np.pi*hz
            assert np.isclose(impedance(ss,f.r,f.cf,f.cs,row['r3_ohm'],row['c3_f']),transfer(ss,f,row['r3_ohm'],row['c3_f']),rtol=1e-10)
    report=dict(status='screened_only',seed=20260921,samples=12000,qualifying_linear_candidates=len(candidates),best=candidates[:10],noise_ripple_frontier=frontier,limitations=[
        '45-degree sampled phase-margin search constraint is provisional, not a chip acceptance gate.',
        'No sampled divider, pump compliance, resistor noise, startup or full-chip loading included.',
        'Parameter bounds are exploratory, not PDK feasibility or area qualification.',
        'Noise ranking omits fractional spurs; selected circuits require edge-driven validation.'])
    (P/'evidence/pll-filter-resynthesis-corrected.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Candidates:',len(candidates));print(json.dumps(candidates[:2],indent=2))
