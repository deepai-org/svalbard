"""Assess isolation capacitance and monitor-location/loading tradeoffs."""
import json,math
from itertools import product
from scipy.optimize import brentq
from chip_model import P
from rf_isolation_load import solve

def main():
    rows=[]
    for hz,location,cap in product((2.412e9,2.437e9),('upstream','pad'),(0.,1e-15,10e-15,50e-15)):
        on=solve(hz,monitor_location=location,feedthrough_f=cap,isolation_ohm=5.)
        off=solve(hz,monitor_location=location,feedthrough_f=cap,isolation_ohm=1e6)
        for r in (on,off):
            assert r['kcl_error']<1e-14
            assert r['power_error']<1e-14 and all(x>=0 for x in r['losses'].values())
        # Almost-disconnected monitor yields an independently solvable series network.
        plain=solve(hz,monitor_location=location,feedthrough_f=cap,isolation_ohm=5.,tap_ohm=1e18)
        zi=1/(1/5.+2j*math.pi*hz*cap)
        expected=50/(50+zi+50)
        assert abs(plain['pad']-expected)<1e-14
        rows.append(dict(frequency_hz=hz,monitor_location=location,feedthrough_f=cap,
            on_pad_amplitude=abs(on['pad']),off_pad_amplitude=abs(off['pad']),
            off_to_on_db=20*math.log10(abs(off['pad']/on['pad'])),
            on_monitor_amplitude=abs(on['monitor']),off_monitor_amplitude=abs(off['monitor']),
            off_to_on_monitor_power_ratio=abs(off['monitor']/on['monitor'])**2,
            off_to_on_internal_amplitude_ratio=abs(off['internal']/on['internal']),
            on_source_real_power=on['source_real_power'],off_source_real_power=off['source_real_power']))
    # Failures are reported rather than changing the assumed -60 dB criterion.
    for r in rows:
        if r['feedthrough_f']>=1e-15:assert r['off_to_on_db']>-60
    ceilings=[]
    for hz in (2.412e9,2.437e9):
        def margin(cap_ff):
            on=solve(hz,feedthrough_f=cap_ff*1e-15,isolation_ohm=5.)
            off=solve(hz,feedthrough_f=cap_ff*1e-15,isolation_ohm=1e6)
            return abs(off['pad']/on['pad'])-.001
        cap_ff=brentq(margin,0.,1.,xtol=1e-12)
        assert abs(margin(cap_ff))<1e-12
        ceilings.append(dict(frequency_hz=hz,feedthrough_ceiling_f=cap_ff*1e-15,
                             criterion_off_to_on_db=-60))
    report=dict(status='characterized',cases=rows,capacitance_ceilings=ceilings,
        assumptions=dict(source_ohm=50,load_ohm=50,on_ohm=5,off_ohm=1e6,
            tap_ohm=1000,input_ohm=10000,input_f=50e-15),
        limitations=['Fixed-frequency small-signal RMS phasors; no envelope transients, active driver regulation, nonlinear switch or supply efficiency.',
            'Exploratory lumped component values, not extracted parasitics or a claim of achievable on/off resistance.',
            'Source real power is RF network power, not chip DC consumption.',
            'Not connected to live calibration or waveform model yet.'])
    (P/'evidence/connected-rf-isolation-load.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in rows[:8]:print(r['monitor_location'],r['feedthrough_f'],r['off_to_on_db'],r['off_to_on_monitor_power_ratio'])

if __name__=='__main__':main()
