"""Coupled transient convergence, subdivision, load switching and rail limits."""
import copy,json
import numpy as np
from chip_model import P
from rf_driver_transient import CoupledDriver
from rf_driver_supply import DriverSupplyLaw

def main():
    c=CoupledDriver();split=copy.deepcopy(c);command=.3+.1j
    dc=c.law.operating_point(c.network,command,c.r)
    c.advance(500e-9,command)
    for t in (100e-9,300e-9,500e-9):split.advance(t,command)
    assert abs(c.rail_v-dc['rail_v'])<1e-8
    voltage_error=float(max(abs(c.network.voltage-split.network.voltage)))
    assert voltage_error<1e-8 and abs(c.rail_v-split.rail_v)<1e-8
    before=c.network.voltage.copy();rail=c.rail_v
    c.network.configure(True,True)
    assert np.array_equal(before,c.network.voltage) and c.rail_v==rail
    dc2=c.law.operating_point(c.network,command,c.r)
    c.advance(1e-6,command)
    assert abs(c.rail_v-dc2['rail_v'])<1e-8 and c.rail_v<rail
    failed=CoupledDriver(law=DriverSupplyLaw(bias_a=.02));initial=failed.network.voltage.copy()
    try:failed.advance(500e-9,command)
    except ValueError:pass
    else:raise AssertionError('Undervoltage admitted')
    assert failed.time==0 and failed.rail_v==3.3 and np.array_equal(initial,failed.network.voltage)
    report=dict(status='passed',initial_settled_rail_v=rail,after_load_switch_rail_v=c.rail_v,
        subdivision_voltage_error_v=voltage_error,final_dc_error_v=abs(c.rail_v-dc2['rail_v']),
        limitations=['Local coupled held-source transient, not connected to full-chip oscillator/reference/host events.',
            'Assumed nonregenerative current/swing law; fixed output resistance and no transistor/package qualification.',
            'Implicit stiff integration is a reference implementation, not yet a fast event-driven substitute.'])
    (P/'evidence/connected-rf-driver-transient.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
