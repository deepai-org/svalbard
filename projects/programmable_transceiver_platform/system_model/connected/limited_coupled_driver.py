"""Finite-current integration candidate of the unified RF-envelope/rail ODE.

Extends the baseline driver with finite reference current and optional owned RX
filter states. All continuous states commit together after a successful solve.
Full-chip event ownership and PLL rail feedback remain integration work.
"""
import copy,math
import numpy as np
from scipy.integrate import solve_ivp
from rf_driver_supply import DriverSupplyLaw
from rf_switched_load import SwitchedLoad
from current_limited_reference import power as limited_power


class LimitedCoupledDriver:
    def __init__(self,network=None,law=None,rail_r=100.,rail_c=100e-12,minimum_rail_v=2.5,detector=None,reference=None,reference_bias_a=.0001,reference_efficiency=.5,source_limit_a=150e-6,sink_limit_a=150e-6,rx_bank=None,receive=None):
        self.network=copy.deepcopy(network) if network is not None else SwitchedLoad()
        self.law=law or DriverSupplyLaw()
        if not all(math.isfinite(x) and x>0 for x in (rail_r,rail_c,minimum_rail_v)) or minimum_rail_v>=self.law.nominal_v:raise ValueError('Invalid rail parameters')
        self.r=rail_r;self.c=rail_c;self.minimum_rail_v=minimum_rail_v
        self.rail_v=self.law.nominal_v;self.time=self.network.time
        self.source_limit=source_limit_a;self.sink_limit=sink_limit_a
        self.reference=reference;self.reference_bias=reference_bias_a;self.reference_efficiency=reference_efficiency
        if reference is not None:
            if reference.time!=self.time:raise ValueError('Reference clock mismatch')
            limited_power(reference.voltage,1.,reference.r,self.rail_v,self.source_limit,self.sink_limit,reference_bias_a,reference_efficiency)
        # Own the filter state: callers must not also advance an RX cascade.
        # receive(t, pad_envelope) supplies mixing/blockers in this carrier frame.
        self.rx_bank=copy.deepcopy(rx_bank)
        self.receive=receive or (lambda t,pad:pad)
        self.received=0j
        if self.rx_bank is not None:
            bank=self.rx_bank
            if not (len(bank['poles'])==len(bank['weights'])==len(bank['states'])>0):
                raise ValueError('Invalid RX bank dimensions')
            if not all(np.isfinite(x) for key in ('poles','weights','states') for x in bank[key]):
                raise ValueError('Nonfinite RX bank')
            if any(p.real<=0 for p in bank['poles']):raise ValueError('Unstable RX bank')
            self.received=sum(w*x for w,x in zip(bank['weights'],bank['states']))
        self.detector=detector
        if detector is not None and (detector.time!=self.time or not hasattr(detector,'readout_pole')):
            raise ValueError('Aligned two-pole detector required')
    def advance(self,time,command,rtol=1e-8,atol=1e-11,max_step=math.inf):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic time')
        if max_step<=0 or math.isnan(max_step):raise ValueError('Invalid integration step bound')
        drive=command if callable(command) else lambda t:command
        self.law.source(drive(self.time),self.rail_v)
        if time==self.time:return
        n=self.network;law=self.law
        B=np.linalg.solve(n.C,np.array([1/50,0,0,0],complex))
        ref_index=11 if self.detector is not None else 9
        rx_index=ref_index+(self.reference is not None)
        count=len(self.rx_bank['poles']) if self.rx_bank is not None else 0
        def rhs(t,y):
            v=y[:4]+1j*y[4:8];rail=y[8]
            source=law.source(drive(t),rail)
            dv=n.A@v+B*source
            power=float(np.real(source*np.conj((source-v[0])/50)))
            current=law.consumption(rail,power)['dc_current_a']
            dr=((law.nominal_v-rail)/self.r-current)/self.c
            result=np.r_[dv.real,dv.imag,dr]
            if self.detector is not None:
                d=self.detector
                result=np.r_[result,d.pole*(abs(v[2])**2-y[9]),d.readout_pole*(y[9]-y[10])]
            if self.reference is not None:
                r=self.reference;target=1+r.driver_sensitivity*(rail-r.driver_nominal)
                power=limited_power(y[ref_index],target,r.r,rail,self.source_limit,self.sink_limit,self.reference_bias,self.reference_efficiency)
                result[8]-=power['dc_current_a']/self.c
                result=np.r_[result,power['current_a']/r.c]
            if count:
                states=y[rx_index:rx_index+count]+1j*y[rx_index+count:rx_index+2*count]
                signal=self.receive(t,v[1])
                if not np.isfinite(signal):raise ValueError('Nonfinite RX input')
                change=np.asarray(self.rx_bank['poles'])*(signal-states)
                result=np.r_[result,change.real,change.imag]
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
        if count:
            states=np.asarray(self.rx_bank['states'],complex)
            y=np.r_[y,states.real,states.imag]
        sol=solve_ivp(rhs,(self.time,time),y,method='Radau',rtol=rtol,atol=atol,events=undervoltage,max_step=max_step)
        if not sol.success or sol.status==1:raise ValueError('Coupled driver left declared rail envelope or integration failed')
        # Transactional update: failed exploratory solves cannot corrupt live state.
        out=sol.y[:,-1]
        if self.reference is not None and out[ref_index]<=.1:raise ValueError('Reference outside model')
        if not np.all(np.isfinite(out)):raise ValueError('Nonfinite coupled state')
        if self.detector is not None:
            if min(out[9:11]) < -1e-10:raise ValueError('Invalid detector state')
            self.detector.value=max(0.,float(out[9]));self.detector.readout_value=max(0.,float(out[10]));self.detector.time=time
        if self.reference is not None:
            r=self.reference;r.voltage=float(out[ref_index]);r.time=time;r.minimum=min(r.minimum,r.voltage)
            r.driver_voltage=float(out[8]);r.driver_epoch=time;r.driver_slope=0.
        if count:
            states=out[rx_index:rx_index+count]+1j*out[rx_index+count:rx_index+2*count]
            self.rx_bank['states']=list(states)
            self.received=sum(w*x for w,x in zip(self.rx_bank['weights'],states))
        n.voltage=out[:4]+1j*out[4:8]
        self.rail_v=float(out[8]);self.time=time;n.time=time
