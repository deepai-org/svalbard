"""Time-varying envelope forcing and independent numerical refinement checks."""
import copy,json
import numpy as np
from chip_model import P
from rf_driver_transient import CoupledDriver

def main():
    def drive(t):return .2*np.exp(2j*np.pi*3e6*t)+.1*np.exp(-2j*np.pi*7e6*t)
    c=CoupledDriver();c.network.configure(True,False)
    split=copy.deepcopy(c);fine=copy.deepcopy(c);held=copy.deepcopy(c)
    c.advance(200e-9,drive,max_step=1e-9)
    for end in (73e-9,131e-9,200e-9):split.advance(end,drive,max_step=1e-9)
    fine.advance(200e-9,drive,rtol=1e-10,atol=1e-13,max_step=.25e-9)
    held.advance(200e-9,drive(0),max_step=1e-9)
    subdivision=float(max(abs(c.network.voltage-split.network.voltage)))
    refinement=float(max(abs(c.network.voltage-fine.network.voltage)))
    rail_error=abs(c.rail_v-fine.rail_v)
    assert subdivision<1e-7 and refinement<1e-7 and rail_error<1e-7
    assert abs(c.network.voltage[1]-held.network.voltage[1])>.001
    # Exercise smooth waveform through switch event with retained charge/rail.
    state=c.network.voltage.copy();rail=c.rail_v
    c.network.configure(False,True)
    assert np.array_equal(state,c.network.voltage) and rail==c.rail_v
    c.advance(250e-9,drive,max_step=1e-9)
    assert c.network.time==c.time==250e-9
    report=dict(status='passed',subdivision_voltage_error_v=subdivision,
        refinement_voltage_error_v=refinement,refinement_rail_error_v=rail_error,
        final_rail_v=c.rail_v,final_pad_magnitude_v=abs(c.network.voltage[1]),
        limitations=['Two-tone envelope with numerical refinement; no whole-chip DAC/PLL/controller integration.',
            'Callbacks must be pure absolute-time functions, with discontinuities split by caller.',
            'Step bound must resolve forcing; this finite check is not a universal integration error bound.',
            'Driver law and rail parameters remain assumptions.'])
    (P/'evidence/connected-rf-driver-modulation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
