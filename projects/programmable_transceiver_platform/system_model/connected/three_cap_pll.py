"""Experimental edge PLL adapter; separate pump compliance and VCO control."""
import numpy as np
from three_cap_filter import ThreeCapFilter
from fractional_rf_chip import ShapedRFClock

class ThreeCapPLLFilter(ThreeCapFilter):
    @property
    def v(self):
        # Legacy PLL interface calls the VCO control voltage `v`.
        return float(self.state[2])
    @property
    def w(self):return float(self.state[1])
    @property
    def voltage_integral(self):return float(self.state[3])
    @voltage_integral.setter
    def voltage_integral(self,value):self.state[3]=value
    @property
    def compliant(self):return bool(np.all(np.isfinite(self.state)) and np.max(abs(self.state[:3]))<self.limit)
    def metrics(self):
        return dict(pump_node_v=float(self.state[0]),slow_node_v=self.w,vco_node_v=self.v,
            source_work_j=float(self.state[5]),resistor_loss_j=float(self.state[6]),
            energy_j=float(self.energy),scope='Separate-node transient adapter; full PLL qualification pending')

class ThreeCapRFClock(ShapedRFClock):
    def __init__(self,filter_values,**kwargs):
        super().__init__(**kwargs)
        if self.time!=0:raise ValueError('Filter replacement requires initial state')
        self.filter=ThreeCapPLLFilter(**filter_values)
    @property
    def integral(self):
        """Physical capacitor charges, ordered pump / slow / VCO (not phase)."""
        f=self.filter
        return tuple(f.state[:3]*np.array([f.cf,f.cs,f.c3]))
    @integral.setter
    def integral(self,charge):
        f=self.filter
        if self.time or f.time or self.reference_history:
            raise ValueError('Charge transfer requires a fresh clock band')
        q=np.asarray(charge,dtype=float)
        if q.shape!=(3,) or not np.all(np.isfinite(q)):
            raise ValueError('Three capacitor charges are required')
        nodes=q/np.array([f.cf,f.cs,f.c3])
        if np.max(abs(nodes))>=f.limit:
            raise ValueError('Transferred charge exceeds filter envelope')
        f.state[:3]=nodes
    def metrics(self):
        return dict(time_s=self.time,locked=self.locked,frequency_hz=self.frequency_hz,
            fault=self.fault,filter=self.filter.metrics())
