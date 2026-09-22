"""DC energy conservation and load-dependent rail/swing controls."""
import json,copy
import numpy as np
from chip_model import P
from rf_switched_load import SwitchedLoad
from rf_driver_supply import DriverSupplyLaw

def main():
    law=DriverSupplyLaw();n=SwitchedLoad();before=copy.deepcopy(n.__dict__)
    zero=law.operating_point(n,0j,100)
    assert abs(zero['rail_v']-3.1)<1e-12
    ideal=law.operating_point(n,.3+0j,0)
    assert abs(ideal['rail_v']-3.3)<1e-12
    rows=[]
    for output,dummy in [(False,True),(True,False),(False,False),(True,True)]:
        n.configure(output,dummy)
        r=law.operating_point(n,.3+.1j,100)
        assert r['rail_v']<3.1 and abs(r['rail_residual_v'])<1e-11
        assert r['dc_power_w']>=r['rf_source_power_w']>=0
        rows.append(dict(output_on=output,dummy_on=dummy,**r))
    assert max(r['rail_v'] for r in rows)-min(r['rail_v'] for r in rows)>1e-4
    returned=law.consumption(3.3,-.0018)
    assert abs(returned['dc_current_a']-.002)<1e-15
    assert abs(returned['driver_dissipation_w']-.0084)<1e-15
    try:DriverSupplyLaw(bias_a=.02).operating_point(n,.3,100)
    except ValueError:pass
    else:raise AssertionError('Rail outside envelope admitted')
    assert np.array_equal(n.voltage,before['voltage']) and n.time==before['time']
    report=dict(status='passed',zero_signal=zero,zero_resistance=ideal,cases=rows,returned_energy=returned,
        limitations=['Assumed current/swing/efficiency law and DC fixed point, not GF180 validation.',
            'No transient supply feedback, current-limit dynamics, nonlinear output impedance or whole-chip integration.',
            'Returned energy dissipates in the chosen nonregenerative policy; other physical topologies may differ.'])
    (P/'evidence/connected-rf-driver-supply.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Rail range',min(r['rail_v'] for r in rows),max(r['rail_v'] for r in rows),flush=True)

if __name__=='__main__':main()
