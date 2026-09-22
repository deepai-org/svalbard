"""Independent branch power balance, steady load split and energy return."""
import json,copy
import numpy as np
from chip_model import P
from rf_switched_load import SwitchedLoad
from rf_driver_power import account

def main():
    rows=[];maxerr=0.
    for output,dummy in [(False,True),(True,False),(False,False),(True,True)]:
        n=SwitchedLoad();n.configure(output,dummy)
        n.voltage=n.steady(.2+.1j);r=account(n,.2+.1j)
        assert abs(r['stored_energy_rate_w'])<1e-12 and r['source_power_w']>0
        assert abs(r['balance_error_w'])<1e-12
        rows.append(dict(output_on=output,dummy_on=dummy,**r))
        rng=np.random.default_rng(302)
        for _ in range(20):
            n.voltage=rng.normal(0,.2,4)+1j*rng.normal(0,.2,4)
            source=complex(*rng.normal(0,.2,2));r=account(n,source)
            maxerr=max(maxerr,abs(r['balance_error_w']))
            assert abs(r['balance_error_w'])<1e-12
            # Rotate all envelope coordinates: physical power cannot change.
            rotated=copy.deepcopy(n);rotated.reframe(2437e6,.43)
            other=account(rotated,source*np.exp(-.43j))
            assert abs(other['source_power_w']-r['source_power_w'])<1e-12
            assert abs(other['stored_energy_rate_w']-r['stored_energy_rate_w'])<1e-12
    n=SwitchedLoad();n.voltage=np.array([1.,0,0,0],complex)
    returned=account(n,.1)
    assert returned['source_power_w']<0 and returned['stored_energy_rate_w']<0
    report=dict(status='passed',steady_cases=rows,max_balance_error_w=maxerr,energy_return_case=returned,
        limitations=['Power accounting on existing linear RMS-envelope RC network; not active-driver/DC feedback.',
            'Ideal source can absorb transient energy; a physical output stage needs an explicit dissipation/return law.',
            'Resistance and capacitance assumptions are unchanged; no physical efficiency or power budget claim.'])
    (P/'evidence/connected-rf-driver-power.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Power balance max error',maxerr,'return power',returned['source_power_w'],flush=True)

if __name__=='__main__':main()
