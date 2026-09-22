"""Passive shunts to the fine-control center; no capacitor-voltage projection."""
import math
from compliant_pump_filter import CompliantPumpFilter
from coarse_vco_clock import CoarseVCOClock

class CenteringFilter(CompliantPumpFilter):
    def __init__(self,*args,center_tau_s=200e-9,**kwargs):
        super().__init__(*args,**kwargs)
        if not math.isfinite(center_tau_s) or center_tau_s<=0:raise ValueError('Invalid centering RC constant')
        self.center_tau=center_tau_s;self.center_enabled=False
        self.center_charge=0.;self.center_loss=0.
    def advance(self,time,current):
        if not self.center_enabled:return super().advance(time,current)
        if current or not math.isfinite(time) or time<self.time:raise ValueError('Centering requires a held pump and monotonic time')
        dt=time-self.time
        if dt==0:return
        q=self.cf*self.v+self.cs*self.w;delta=self.v-self.w;energy=self.energy
        lam=1/self.center_tau;fast=lam+self.pole
        def integ(rate):return -math.expm1(-rate*dt)/rate
        q1=q*math.exp(-lam*dt);d1=delta*math.exp(-fast*dt)
        v1=(q1+self.cs*d1)/self.total;w1=(q1-self.cf*d1)/self.total
        # v is a sum of two exponentials and can have one interior extremum.
        a=q/self.total;b=self.cs*delta/self.total
        extrema=[self.v,v1]
        if a and b and -fast*b/(lam*a)>0:
            t=math.log(-fast*b/(lam*a))/(fast-lam)
            if 0<t<dt:extrema.append(a*math.exp(-lam*t)+b*math.exp(-fast*t))
        self.voltage_integral+=a*integ(lam)+b*integ(fast)
        link_loss=delta*delta/self.r*integ(2*fast)
        self.v,self.w,self.time=v1,w1,time
        loss=energy-self.energy
        self.resistor_loss+=loss # Includes original link plus the two shunts.
        self.center_loss+=loss-link_loss;self.center_charge+=q1-q
        self.minimum=min(self.minimum,*extrema);self.maximum=max(self.maximum,*extrema)
    def metrics(self):
        r=super().metrics();r.update(center_charge_c=self.center_charge,center_shunt_loss_j=self.center_loss,
            center_resistance_fast_ohm=self.center_tau/self.cf,center_resistance_slow_ohm=self.center_tau/self.cs)
        return r

class RecenteringClock(CoarseVCOClock):
    FILTER_CLASS=CenteringFilter
    def start_center(self,time,tau_bound_s=400e-9):
        if self.filter.center_enabled:raise ValueError('Centering already active')
        if not math.isfinite(tau_bound_s) or tau_bound_s<self.filter.center_tau:raise ValueError('Centering time constant exceeds declared bound')
        self.set_reference(False,time)
        self.filter.center_enabled=True;self.coarse_initial_ready=False
        self.center_deadline=time+12*tau_bound_s
        self.center_voltage_bound=self.filter.limit*math.exp(-12)
        return self.center_deadline
    def finish_center(self,time):
        if not self.filter.center_enabled:raise ValueError('Centering is not active')
        if time<self.center_deadline:raise ValueError('Centering guard incomplete')
        self.advance(time);self.filter.center_enabled=False;self.coarse_initial_ready=True

    def cancel_center(self,time):
        if self.filter.center_enabled:
            self.advance(time)
            self.filter.center_enabled=False
            self.coarse_initial_ready=False

    def set_reference(self,present,time):
        if present and self.filter.center_enabled:
            raise ValueError('Fine pump cannot run during passive centering')
        return super().set_reference(present,time)
