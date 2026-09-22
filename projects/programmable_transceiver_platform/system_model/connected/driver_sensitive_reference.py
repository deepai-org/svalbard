"""Reference RC target follows a declared piecewise-linear driver rail.

Retains the existing ADC/DAC conversion charge laws. Supply sensitivity is an
assumption; this does not model amplifier dropout, current limiting or PSRR poles.
"""
import math
from causal_reference_lifecycle import Reference

class DriverSensitiveReference(Reference):
    def __init__(self,driver_v_per_v=.01,driver_nominal_v=3.3,**kwargs):
        super().__init__(**kwargs)
        if not math.isfinite(driver_v_per_v) or not math.isfinite(driver_nominal_v) or driver_nominal_v<=0:raise ValueError('Invalid reference supply sensitivity')
        self.driver_sensitivity=driver_v_per_v;self.driver_nominal=driver_nominal_v
        self.driver_voltage=driver_nominal_v;self.driver_slope=0.;self.driver_epoch=0.
    def set_driver_rail(self,time,voltage,slope_v_per_s=0.):
        if not all(math.isfinite(v) for v in (time,voltage,slope_v_per_s)) or voltage<=0 or time<self.time:raise ValueError('Invalid rail segment')
        if 1+self.driver_sensitivity*(voltage-self.driver_nominal)<=.1:raise ValueError('Reference target outside model')
        self.advance(time)
        self.driver_voltage=voltage;self.driver_slope=slope_v_per_s;self.driver_epoch=time
    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic reference time')
        dt=time-self.time;tau=self.r*self.c
        rail=self.driver_voltage+self.driver_slope*(self.time-self.driver_epoch)
        target=1+self.driver_sensitivity*(rail-self.driver_nominal)
        slope=self.driver_sensitivity*self.driver_slope
        if target<=.1 or target+slope*dt<=.1 or min(rail,rail+self.driver_slope*dt)<=0:raise ValueError('Reference rail/target outside model')
        decay=math.exp(-dt/tau)
        value=target+slope*(dt-tau)+(self.voltage-target+slope*tau)*decay
        self.voltage=value;self.time=time;self.minimum=min(self.minimum,value)
