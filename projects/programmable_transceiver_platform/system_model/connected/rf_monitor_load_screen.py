"""Passivity and on/off RF monitor loading sensitivity; not circuit qualification."""
import json,math,cmath,itertools
from chip_model import P
from rf_monitor_load import solve

def main():
    rows=[]
    for freq,cap,tap,enabled in itertools.product((2.3e9,2.412e9,2.5e9),(10e-15,50e-15,200e-15),(500.,1000.,5000.),(False,True)):
        r=solve(freq,input_f=cap,tap_ohm=tap,input_ohm=1e4 if enabled else 1e9)
        assert r['pad_kcl_error']<1e-15 and r['monitor_kcl_error']<1e-15
        balance=abs(sum(r['losses'].values())-r['source_real_power']);assert balance<1e-15
        assert all(v>=0 for v in r['losses'].values()) and abs(r['relative_output'])<=1+1e-12
        rows.append(dict(frequency_hz=freq,capacitance_f=cap,tap_ohm=tap,enabled=enabled,
            output_loss_db=-20*math.log10(abs(r['relative_output'])),output_phase_deg=math.degrees(cmath.phase(r['relative_output'])),
            detector_to_pad_power_ratio=abs(r['monitor']/r['output'])**2,
            resistor_power_w_at_1Vrms_source=r['losses'],power_balance_error=balance))
    off=solve(2.412e9,input_ohm=1e9,input_f=200e-15)
    assert abs(off['relative_output']-1)>1e-3
    cases=[r for r in rows if r['frequency_hz']==2.412e9 and r['capacitance_f']==50e-15 and r['tap_ohm']==1000]
    report=dict(status='passed',cases=rows,nominal_comparison=cases,
        limitations=['Assumed RMS linear network, no pad/package inductance, matching network, nonlinear detector current or buffer feedback.',
        'One-way budget only; not connected into live RF waveform/calibration or supply domains.',
        'Signal resistor power is not detector bias power; neither is an allocated physical chip budget.'])
    (P/'evidence/connected-rf-monitor-load.json').write_text(json.dumps(report,indent=2)+'\n');print(cases)
if __name__=='__main__':main()
