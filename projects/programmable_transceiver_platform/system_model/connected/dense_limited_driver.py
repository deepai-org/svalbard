"""Same guarded finite-current ODE with direct derivative-array assembly.

Temporary comparison candidate; no changed equations, tolerances or state order.
Consolidate into the selected solver after equivalence and speed evaluation.
"""
import math
import numpy as np
from scipy.integrate import solve_ivp
from current_limited_reference import power as limited_power
from limited_coupled_driver import LimitedCoupledDriver

class DenseLimitedDriver(LimitedCoupledDriver):
    def advance(self,time,command,rtol=1e-8,atol=1e-11,max_step=math.inf):
        if not math.isfinite(self.rail_v) or self.rail_v<=self.minimum_rail_v:
            raise ValueError('Initial driver rail outside declared model')
        if self.reference is not None and (not math.isfinite(self.reference.voltage) or self.reference.voltage<=.1):
            raise ValueError('Initial reference outside declared model')
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic time')
        if max_step<=0 or math.isnan(max_step):raise ValueError('Invalid integration step bound')
        drive=command if callable(command) else lambda t:command
        self.law.source(drive(self.time),self.rail_v)
        if time==self.time:return
        n=self.network;law=self.law
        B=np.linalg.solve(n.C,np.array([1/50,0,0,0],complex))
        ref_index=11 if self.detector is not None else 9
        def rhs(t,y):
            v=y[:4]+1j*y[4:8];rail=y[8]
            source=law.source(drive(t),rail)
            dv=n.A@v+B*source
            power=float(np.real(source*np.conj((source-v[0])/50)))
            current=law.consumption(rail,power)['dc_current_a']
            dr=((law.nominal_v-rail)/self.r-current)/self.c
            result=np.empty_like(y)
            result[:4]=dv.real;result[4:8]=dv.imag;result[8]=dr
            if self.detector is not None:
                d=self.detector
                result[9]=d.pole*(abs(v[2])**2-y[9])
                result[10]=d.readout_pole*(y[9]-y[10])
            if self.reference is not None:
                r=self.reference;target=1+r.driver_sensitivity*(rail-r.driver_nominal)
                power=limited_power(y[ref_index],target,r.r,rail,self.source_limit,self.sink_limit,self.reference_bias,self.reference_efficiency)
                result[8]-=power['dc_current_a']/self.c
                result[ref_index]=power['current_a']/r.c
            return result
        def undervoltage(t,y):return y[8]-self.minimum_rail_v
        undervoltage.terminal=True;undervoltage.direction=-1
        y=np.r_[n.voltage.real,n.voltage.imag,self.rail_v]
        if self.detector is not None:
            if self.detector.time!=self.time:raise ValueError('Detector clock mismatch')
            y=np.r_[y,self.detector.value,self.detector.readout_value]
        if self.reference is not None:
            if self.reference.time!=self.time:raise ValueError('Reference clock mismatch')
            y=np.r_[y,self.reference.voltage]
        sol=solve_ivp(rhs,(self.time,time),y,method='Radau',rtol=rtol,atol=atol,events=undervoltage,max_step=max_step)
        if not sol.success or sol.status==1:raise ValueError('Coupled driver left declared rail envelope or integration failed')
        # Transactional update: failed exploratory solves cannot corrupt live state.
        out=sol.y[:,-1]
        if self.reference is not None and out[ref_index]<=.1:raise ValueError('Reference outside model')
        if self.detector is not None:
            if min(out[9:11]) < -1e-10:raise ValueError('Invalid detector state')
            self.detector.value=max(0.,float(out[9]));self.detector.readout_value=max(0.,float(out[10]));self.detector.time=time
        if self.reference is not None:
            r=self.reference;r.voltage=float(out[ref_index]);r.time=time;r.minimum=min(r.minimum,r.voltage)
            r.driver_voltage=float(out[8]);r.driver_epoch=time;r.driver_slope=0.
        n.voltage=out[:4]+1j*out[4:8]
        self.rail_v=float(out[8]);self.time=time;n.time=time
