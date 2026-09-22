"""Small-signal screening of the actual two-capacitor filter impedance."""
import json,math
import numpy as np
from chip_model import P
from autonomous_pll import AutonomousPLL
from charge_pump_filter import ChargePumpFilter

def main():
 g=AutonomousPLL(reference_hz=40e6,divider=60,bandwidth_hz=300e3)
 freq=np.geomspace(1e3,40e6,30000);s=2j*np.pi*freq;rows=[]
 for fraction in (.5,.35,.3,.25,.2,.1):
    f=ChargePumpFilter.from_gains(g.kp,g.ki,100e-6,fraction)
    z=(1+s*f.r*f.cs)/(s*f.total*(1+s/f.pole))
    loop=100e-6*g.kvco*z/(60*s);sensitivity=1/(1+loop)
    cross=int(np.argmin(abs(np.log(abs(loop)))))
    # Characteristic equation s^3/p + s^2 + K R Cs s + K = 0.
    k=100e-6*g.kvco/(60*f.total)
    poles=np.roots([1/f.pole,1,k*f.r*f.cs,k])
    assert all(z.real<0 for z in poles)
    rows.append(dict(fast_fraction=fraction,resistance_ohm=f.r,cf_f=f.cf,cs_f=f.cs,
        extra_pole_hz=f.pole/(2*math.pi),unity_hz=float(freq[cross]),
        phase_margin_degrees=float(180+np.angle(loop[cross],deg=True)),
        peak_sensitivity=float(max(abs(sensitivity))),peak_frequency_hz=float(freq[np.argmax(abs(sensitivity))]),
        closed_loop_poles=[[float(z.real),float(z.imag)] for z in poles]))
 report=dict(status='passed',cases=rows,scope='Averaged small-signal screening only; no sampled-delay, fractional spur, compliance, startup, noise or full-chip qualification.')
 (P/'evidence/connected-pll-filter-response.json').write_text(json.dumps(report,indent=2)+'\n')
 for r in rows:print(r['fast_fraction'],r['phase_margin_degrees'],r['peak_sensitivity'])
if __name__=='__main__':main()
