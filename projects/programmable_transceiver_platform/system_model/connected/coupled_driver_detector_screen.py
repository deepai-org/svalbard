"""Actual monitor-node power drives detector/readout in the coupled ODE."""
import json,math,copy
import numpy as np
from chip_model import P
from rf_driver_transient import CoupledDriver
from buffered_shared_detector import BufferedSharedDetector

def main():
    samples=[]
    def sample(value,time):samples.append(value);return value,False
    d=BufferedSharedDetector(sample,readout_tau_s=20e-9)
    c=CoupledDriver(detector=d);command=.2+.1j
    dc=c.law.operating_point(c.network,command,c.r);c.rail_v=dc['rail_v']
    c.network.voltage=c.network.steady(c.law.source(command,c.rail_v))
    power=abs(c.network.voltage[2])**2;split=copy.deepcopy(c)
    end=100e-9;a=d.pole;b=d.readout_pole
    expected=power*(1-(b*math.exp(-a*end)-a*math.exp(-b*end))/(b-a))
    c.advance(end,command);split.advance(end/2,command);split.advance(end,command)
    error=abs(d.readout_value-expected)
    assert error<1e-11 and abs(d.value-power*(1-math.exp(-a*end)))<1e-11
    assert abs(d.readout_value-split.detector.readout_value)<1e-11
    d.request();held=d.readout_value;deadline=d.pending[0]
    c.network.configure(True,False);c.advance(deadline,command)
    assert d.read()['power']==held and samples==[held]
    d.request();before=(d.value,d.readout_value,c.rail_v,c.network.voltage.copy())
    d.abort()
    assert d.pending is None and (d.value,d.readout_value,c.rail_v)==before[:3]
    assert np.array_equal(c.network.voltage,before[3])
    report=dict(status='passed',monitor_power=power,analytic_readout_error=error,sampled_power=held,
        limitations=['Local coupled driver/network/rail/detector/readout, with callback readout only.',
            'Full-chip shared ADC reference and autonomous clock coupling not yet integrated.',
            'Detector buffer is one-way; reverse mux loading and kickback absent.'])
    (P/'evidence/connected-coupled-driver-detector.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
