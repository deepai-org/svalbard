"""Switched total dummy resistance: loading remedy, not ideal RF isolation."""
import json,math
from itertools import product
from chip_model import P
from rf_isolation_load import solve

def main():
    rows=[]
    for hz,cap,mismatch,load in product((2.412e9,2.437e9),(1e-15,10e-15),(-.1,0.,.1),(40.,50.,60.)):
        # 55ohm includes dummy switch on resistance, matching nominal 5+50ohm.
        on=solve(hz,load_ohm=load,feedthrough_f=cap,isolation_ohm=5.)
        off=solve(hz,load_ohm=load,feedthrough_f=cap,isolation_ohm=1e6,dummy_ohm=55*(1+mismatch))
        for r in (on,off):
            assert r['kcl_error']<1e-14 and r['power_error']<1e-14
        ratio=off['monitor']/on['monitor']
        rows.append(dict(frequency_hz=hz,feedthrough_f=cap,load_ohm=load,dummy_mismatch=mismatch,
            calibration_amplitude_ratio=abs(ratio),calibration_phase_deg=math.degrees(math.atan2(ratio.imag,ratio.real)),
            off_to_on_db=20*math.log10(abs(off['pad']/on['pad'])),
            dummy_power_per_source_v_rms_squared=off['losses']['dummy_load']))
    nominal=[r for r in rows if r['load_ohm']==50 and r['dummy_mismatch']==0]
    assert all(abs(r['calibration_amplitude_ratio']-1)<.001 for r in nominal)
    # Residual feedthrough remains; resistor matching cannot remove capacitance.
    assert all(r['off_to_on_db']>-45 for r in nominal if r['feedthrough_f']==10e-15)
    report=dict(status='characterized',cases=rows,nominal_cases=nominal,
        worst_calibration_amplitude_error=max(abs(r['calibration_amplitude_ratio']-1) for r in rows),
        limitations=['Static small-signal RF load preservation only; dummy switching capacitance and transition sequencing absent.',
        'Dummy total resistance includes switch on resistance; its off-state parasitics remain unmodeled.',
        'No active-driver load dependence, supply current, thermal transient or transistor qualification.',
        'Fixed nominal dummy does not track unknown external loads. Not yet integrated with live calibration.'])
    (P/'evidence/connected-rf-dummy-load.json').write_text(json.dumps(report,indent=2)+'\n')
    print('nominal',nominal,'worst amplitude error',report['worst_calibration_amplitude_error'])

if __name__=='__main__':main()
