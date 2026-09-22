"""Analytical state, saturation recovery and invalid-setting checks for local tile."""
import json,math
from analog_tile import AnalogTile
from chip_model import P

def main():
    rows=[]
    for leakage in (0.,1e-7):
        for sign in (-1,1):
            a=AnalogTile(leakage=leakage);b=AnalogTile(leakage=leakage)
            for c in (a,b):
                c.configure(0,(sign,-sign*.5));c.drive(0,.2,.1)
            t=1e-6;current=sign*.15e-6
            expected=current*t/a.c if not leakage else current/leakage*(-math.expm1(-leakage*t/a.c))
            assert abs(a.advance(t)-expected)<1e-14
            for i in range(1,138):b.advance(t*i/137)
            assert abs(a.voltage-b.voltage)<1e-14
            a.advance(100e-6);assert a.voltage==sign*a.limit
            # Reverse drive must release a saturated capacitor immediately.
            a.drive(a.time,-sign*.2,0);before=a.voltage
            # Both weight and source sign matter: explicitly reverse current.
            a.configure(a.time,(1.,0.));a.advance(a.time+1e-6)
            assert abs(a.voltage)<abs(before)
            saved=a.voltage;a.configure(a.time,(0.,0.),False)
            assert a.voltage==saved
            old=(a.time,a.voltage,a.weights)
            try:a.configure(a.time+1,(2.,0.))
            except ValueError:pass
            else:raise AssertionError('Invalid weight accepted')
            assert old==(a.time,a.voltage,a.weights)
            a.discharge(a.time);assert a.voltage==0 and not a.comparator
            rows.append(dict(leakage_s=leakage,sign=sign,analytic_voltage_v=expected,subdivision_error_v=abs(b.voltage-expected)))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Standalone tile is not yet connected to diagnostic selection or converter ownership.',
        'Held inputs, hard voltage bounds and ideal current weights omit bandwidth, slew, noise and switch charge.',
        'Comparator reports endpoint state; asynchronous threshold-crossing event delivery remains open.'])
    (P/'evidence/connected-analog-tile.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed local tile integration, saturation recovery and state preservation')
if __name__=='__main__':main()
