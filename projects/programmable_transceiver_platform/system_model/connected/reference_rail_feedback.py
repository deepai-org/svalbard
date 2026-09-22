"""Local two-way reference-buffer/rail transient with retained conversion loads."""
import math
from scipy.integrate import solve_ivp
from reference_buffer_power import account

class ReferenceRail:
    def __init__(self,reference,nominal_v=3.3,rail_r=100.,rail_c=100e-12,buffer_bias_a=.0001,efficiency=.5):
        if not all(math.isfinite(v) and v>0 for v in (nominal_v,rail_r,rail_c)):raise ValueError('Invalid rail')
        account(1.,1.,reference.r,nominal_v,buffer_bias_a,efficiency)
        self.reference=reference;self.nominal=nominal_v;self.r=rail_r;self.c=rail_c
        self.bias=buffer_bias_a;self.efficiency=efficiency;self.rail_v=nominal_v;self.time=reference.time
    def advance(self,end,other_current_a=.002,rtol=1e-9,atol=1e-12):
        if not math.isfinite(end) or end<self.time or self.reference.time!=self.time or not math.isfinite(other_current_a) or other_current_a<0:raise ValueError('Invalid interval/current')
        if end==self.time:return
        r=self.reference
        def rhs(t,y):
            rail,voltage=y;target=1+r.driver_sensitivity*(rail-r.driver_nominal)
            p=account(voltage,target,r.r,rail,self.bias,self.efficiency)
            return [((self.nominal-rail)/self.r-other_current_a-p['dc_current_a'])/self.c,
                    p['output_current_a']/r.c]
        result=solve_ivp(rhs,(self.time,end),[self.rail_v,r.voltage],rtol=rtol,atol=atol,method='Radau')
        if not result.success:raise ValueError('Reference/rail integration failed')
        rail,voltage=map(float,result.y[:,-1])
        self.rail_v=rail;self.time=end;r.voltage=voltage;r.time=end;r.minimum=min(r.minimum,voltage)
        r.driver_voltage=rail;r.driver_slope=0.;r.driver_epoch=end
