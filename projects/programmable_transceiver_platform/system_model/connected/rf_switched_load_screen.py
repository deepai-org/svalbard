"""Charge continuity, steady phasor, energy balance and switch sequencing."""
import json
import numpy as np
from scipy.integrate import quad
from chip_model import P
from rf_switched_load import SwitchedLoad

def main():
    rows=[]
    for cap in (1e-15,10e-15,50e-15):
        for sequence in ('break_before_make','overlap'):
            n=SwitchedLoad(dummy_feedthrough_f=cap)
            # Independent branch-reduced DC-in-envelope solution.
            w=n.omega
            yi=1e-6+1j*w*1e-15;yd=.2+1j*w*cap
            ym=1/10000+1j*w*50e-15
            yp=1/50+1j*w*100e-15;yload=1/50+1j*w*20e-15
            u=(1/50)/(1/50+1j*w*50e-15+yi*yp/(yi+yp)+yd*yload/(yd+yload)+ym/(1+1000*ym))
            expected=np.array([u,u*yi/(yi+yp),u/(1+1000*ym),u*yd/(yd+yload)])
            assert np.max(abs(n.steady(1)-expected))<1e-14
            n.voltage=n.steady(1);initial=n.voltage.copy()
            n.configure(sequence=='overlap',sequence=='overlap')
            assert np.array_equal(n.voltage,initial)
            e0=n.energy();duration=100e-12
            def net_power(t):
                v=n.forecast(t,1)
                return float((v[0].conjugate()/50).real-np.vdot(v,n.G@v).real)
            integral=quad(net_power,0,duration,epsabs=1e-25,epsrel=1e-10)[0]
            end=n.forecast(duration,1)
            assert abs(n.energy(end)-e0-integral)<1e-23
            peaks=[abs(n.forecast(t,1)[0]) for t in np.linspace(0,duration,101)]
            n.advance(duration,1);before=n.voltage.copy()
            n.configure(True,False);assert np.array_equal(before,n.voltage)
            # Subdivision and long-time agreement.
            direct=n.forecast(100e-12,1)
            n.advance(duration+40e-12,1);n.advance(duration+100e-12,1)
            assert np.max(abs(n.voltage-direct))<1e-13
            n.advance(duration+2e-9,1)
            assert np.max(abs(n.voltage-n.steady(1)))<1e-6
            rows.append(dict(dummy_feedthrough_f=cap,sequence=sequence,
                internal_peak_during_transition=max(peaks),initial_internal_amplitude=abs(initial[0]),
                final_internal_amplitude=abs(n.voltage[0]),final_pad_amplitude=abs(n.voltage[1]),
                energy_balance_error=abs(n.energy(end)-e0-integral)))
    report=dict(status='passed',cases=rows,limitations=[
        'Exploratory linear R/C network; no MOS gate charge injection, nonlinear R/C, supply coupling or package inductance.',
        '100ps sequencing example, not a timing specification; control resistance changes abruptly but capacitor charge persists.',
        'Fixed carrier and source; continuous detector/live full-chip integration remains open.',
        'Node shunt and switch feedthrough capacitances are declared assumptions.'])
    (P/'evidence/connected-rf-switched-load.json').write_text(json.dumps(report,indent=2)+'\n')
    print([(r['sequence'],r['dummy_feedthrough_f'],r['internal_peak_during_transition']) for r in rows])

if __name__=='__main__':main()
