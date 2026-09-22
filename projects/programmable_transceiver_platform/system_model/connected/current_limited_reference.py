"""Exploratory finite-current reference buffer with explicit rail energy demand.

The ideal target drives R followed by a bidirectional current limiter. The extra
voltage drop dissipates power; returned reservoir energy is dissipated locally.
This is an assumed constitutive law, not a selected transistor topology.
"""
import math
from scipy.integrate import solve_ivp
from reference_rail_feedback import ReferenceRail

def power(voltage,target,resistance,rail,source_limit,sink_limit,bias,efficiency):
    values=(voltage,target,resistance,rail,source_limit,sink_limit,bias,efficiency)
    if not all(math.isfinite(v) for v in values) or min(values[:6])<=0 or bias<0 or not 0<efficiency<=1:
        raise ValueError('Invalid finite-current reference parameters')
    current=max(-sink_limit,min(source_limit,(target-voltage)/resistance))
    source=target*current;stored=voltage*current
    resistor=current*current*resistance
    limiter=(target-voltage)*current-resistor
    dc=rail*bias+max(0.,source)/efficiency
    return dict(current_a=current,dc_current_a=dc/rail,source_w=source,stored_w=stored,
                resistor_w=resistor,limiter_w=limiter,buffer_dissipation_w=dc-source)

class CurrentLimitedReferenceRail(ReferenceRail):
    def __init__(self,reference,source_limit_a=.001,sink_limit_a=.001,**kwargs):
        super().__init__(reference,**kwargs)
        power(1.,1.,reference.r,self.rail_v,source_limit_a,sink_limit_a,self.bias,self.efficiency)
        self.source_limit=source_limit_a;self.sink_limit=sink_limit_a
    def advance(self,end,other_current_a=.002,rtol=1e-9,atol=1e-12):
        if not math.isfinite(end) or end<self.time or self.reference.time!=self.time or not math.isfinite(other_current_a) or other_current_a<0:
            raise ValueError('Invalid interval/current')
        if end==self.time:return
        r=self.reference
        def rhs(t,y):
            rail,voltage=y;target=1+r.driver_sensitivity*(rail-r.driver_nominal)
            p=power(voltage,target,r.r,rail,self.source_limit,self.sink_limit,self.bias,self.efficiency)
            return [((self.nominal-rail)/self.r-other_current_a-p['dc_current_a'])/self.c,p['current_a']/r.c]
        sol=solve_ivp(rhs,(self.time,end),[self.rail_v,r.voltage],method='Radau',rtol=rtol,atol=atol)
        if not sol.success or min(sol.y[0])<=2.5 or min(sol.y[1])<=.1:
            raise ValueError('Finite-current reference left local operating envelope')
        rail,voltage=map(float,sol.y[:,-1])
        self.rail_v=rail;self.time=end;r.voltage=voltage;r.time=end;r.minimum=min(r.minimum,float(min(sol.y[1])))
        r.driver_voltage=rail;r.driver_slope=0.;r.driver_epoch=end
