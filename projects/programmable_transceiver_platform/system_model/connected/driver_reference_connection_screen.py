"""Live rail trajectory, retained conversion impulses and interval refinement."""
import json
import numpy as np
from chip_model import P
from rf_driver_transient import CoupledDriver
from driver_sensitive_reference import DriverSensitiveReference
from driver_reference_connection import advance

def run(step,sensitivity):
    d=CoupledDriver();d.network.configure(True,False)
    r=DriverSensitiveReference(driver_v_per_v=sensitivity)
    def source(t):return .2*np.exp(2j*np.pi*3e6*t)+.08*np.exp(-2j*np.pi*7e6*t)
    samples=[]
    for i in range(1,9):
        end=i*25e-9;advance(d,r,end,source,step)
        samples.append(r.sample(end,.2+.1j))
        r.dac_update(end,.1+.03j,1e-12)
    assert d.time==r.time==200e-9 and r.samples==r.dac_updates==8
    return d,r,samples

def main():
    coarse=run(2e-9,.05);medium=run(1e-9,.05);fine=run(.25e-9,.05);zero=run(.25e-9,0.)
    errors=[abs(x[1].voltage-fine[1].voltage) for x in (coarse,medium)]
    assert errors[1]<errors[0] and errors[1]<1e-6
    assert fine[1].voltage<zero[1].voltage
    assert abs(fine[2][-1]-zero[2][-1])>1e-4
    report=dict(status='passed',reference_error_v=errors,final_reference_v=fine[1].voltage,
        uncoupled_reference_v=zero[1].voltage,final_driver_rail_v=fine[0].rail_v,
        adc_samples=fine[1].samples,dac_updates=fine[1].dac_updates,
        limitations=['Local driver-to-reference feedforward with real load impulses; no managed whole-chip integration.',
            'Reference draw does not yet load driver supply; interpolation convergence is finite-case evidence.',
            'Driver/reference laws and supply sensitivity remain assumptions.'])
    (P/'evidence/connected-driver-reference-connection.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
