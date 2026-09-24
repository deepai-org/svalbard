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


class PassiveSourceBudgetExceeded(ValueError):
    pass


class LimitedCoupledDriver:
    def __init__(self,network=None,law=None,rail_r=100.,rail_c=100e-12,minimum_rail_v=2.5,detector=None,reference=None,reference_bias_a=.0001,reference_efficiency=.5,source_limit_a=150e-6,sink_limit_a=150e-6,rx_bank=None,receive=None,domain_supply=None,domain_minimum_v=None,domain_load=None,host_bank=None):
        self.network=copy.deepcopy(network) if network is not None else SwitchedLoad()
        self.law=law or DriverSupplyLaw()
        if not all(math.isfinite(x) and x>0 for x in (rail_r,rail_c,minimum_rail_v)) or minimum_rail_v>=self.law.nominal_v:raise ValueError('Invalid rail parameters')
        self.r=rail_r;self.c=rail_c;self.minimum_rail_v=minimum_rail_v
        self.rail_v=self.law.nominal_v;self.time=self.network.time
        self.rail_trajectory=None
        self.driver_enabled=True
        self.extra_current=lambda time,rail:0.
        self.external_return_current=lambda time:0.
        self.external_return_guard=lambda time,ground:True
        self.source_energy_j=self.rail_resistor_energy_j=self.load_energy_j=0.
        self.extra_load_energy_j=0.;self.impulse_energy_j=0.
        self.source_limit=source_limit_a;self.sink_limit=sink_limit_a
        self.reference=reference;self.reference_bias=reference_bias_a;self.reference_efficiency=reference_efficiency
        if reference is not None:
            if reference.time!=self.time:raise ValueError('Reference clock mismatch')
            limited_power(reference.voltage,1.,reference.r,self.rail_v,self.source_limit,self.sink_limit,reference_bias_a,reference_efficiency)
        # Own the filter state: callers must not also advance an RX cascade.
        # receive(t, pad_envelope) supplies mixing/blockers in this carrier frame.
        self.rx_bank=copy.deepcopy(rx_bank)
        self.receive=receive or (lambda t,pad:pad)
        self.pad_branch=None  # Optional shared serial/USB two-node circuit, owned by this ODE.
        self.received=0j
        if self.rx_bank is not None:
            bank=self.rx_bank
            if not (len(bank['poles'])==len(bank['weights'])==len(bank['states'])>0):
                raise ValueError('Invalid RX bank dimensions')
            if not all(np.isfinite(x) for key in ('poles','weights','states') for x in bank[key]):
                raise ValueError('Nonfinite RX bank')
            if any(p.real<=0 for p in bank['poles']):raise ValueError('Unstable RX bank')
            self.received=sum(w*x for w,x in zip(bank['weights'],bank['states']))
        self.domains=copy.deepcopy(domain_supply)
        self.domain_load=domain_load
        self.domain_trajectories=None
        if self.domains is not None:
            d=self.domains
            if d.time!=self.time or not callable(domain_load):raise ValueError('Aligned domain supply and explicit load callback required')
            self.domain_floor=np.asarray(domain_minimum_v,float)
            if self.domain_floor.shape!=d.voltage.shape or not np.all(np.isfinite(self.domain_floor)) or np.any(self.domain_floor<=0) or np.any(d.voltage<=self.domain_floor):
                raise ValueError('Valid per-domain voltage envelope required')
            self.rf_domain=d.names.index('RF');self.reference_domain=d.names.index('PLL');self.wire_domain=d.names.index('WIRE_A')
            if d.nominal[self.rf_domain]!=self.law.nominal_v:raise ValueError('RF nominal voltage mismatch')
            self.rail_v=float(d.voltage[self.rf_domain])
        self.host_bank=copy.deepcopy(host_bank)
        if self.host_bank is not None:
            h=self.host_bank;d=self.domains
            if d is None or h.time!=self.time or h.n!=len(d.names):raise ValueError('Host bank requires aligned physical domains')
            for a,b in ((h.nominal,d.nominal),(h.feed_r,d.feed_r),(h.decap,d.c),(h.floor,self.domain_floor),(h.state[:h.n],d.voltage)):
                if not np.array_equal(a,b):raise ValueError('Host bank and domain circuit mismatch')
            if h.return_r!=d.common_return_r:raise ValueError('Host return mismatch')
            h.externally_owned=True
        self.detector=detector
        if detector is not None and (detector.time!=self.time or not hasattr(detector,'readout_pole')):
            raise ValueError('Aligned two-pole detector required')
    def forecast_passive(self,time,terms,*,source_error_limit_v,minimum_step_s=1e-13,
                         maximum_attempts=128,record_states=False):
        """Transactional adaptive held-source reduction on a private candidate.

        Only exponential command terms are supported. The budget constrains
        source mismatch at solver evaluations, not a continuous-time error bound.
        No discrete switch/host/converter event may occur inside this forecast.
        """
        from autonomous_pll import SupplyTrajectory
        if (not math.isfinite(time) or time<=self.time or not math.isfinite(minimum_step_s)
                or minimum_step_s<=0 or type(maximum_attempts) is not int or maximum_attempts<1
                or not math.isfinite(source_error_limit_v) or source_error_limit_v<=0):
            raise ValueError('Positive bounded passive forecast required')
        self.network.forecast_terms(0.,terms)
        local=copy.copy(self)
        for name in ('domains','host_bank','pad_branch','network','rx_bank'):
            setattr(local,name,copy.deepcopy(getattr(self,name)))
        for name in ('detector','reference'):
            setattr(local,name,copy.copy(getattr(self,name)))
        origin=self.time;pending=[time];accepted=[];attempts=0;traces={}
        def command(t):return sum(a*np.exp(r*(t-origin)) for a,r in terms)
        while pending:
            stop=pending.pop();start=local.time;attempts+=1
            if attempts>maximum_attempts:raise ValueError('Passive refinement attempt budget exhausted')
            coefficients=[(a*np.exp(r*(start-origin)),r) for a,r in terms]
            value=command(start)
            # Exact source scale at the interval start, including compression.
            scale=local.law.source(value,local.rail_v)/value if value!=0 else local.rail_v/local.law.nominal_v
            projected=[(a*scale if local.driver_enabled else 0j,r) for a,r in coefficients]
            initial_network=copy.deepcopy(local.network) if record_states else None
            try:
                local.advance(stop,command,solver_method='BDF',rtol=1e-10,atol=1e-13,
                    rail_trace_step_s=(stop-start)/4,passive_terms=projected,
                    source_error_limit_v=source_error_limit_v)
            except PassiveSourceBudgetExceeded:
                midpoint=(start+stop)/2
                if midpoint-start<minimum_step_s or midpoint==start or midpoint==stop:
                    raise ValueError('Passive source budget requires finer than allowed interval')
                pending.extend((stop,midpoint));continue
            row=dict(start_s=start,end_s=stop,source_error_v=local.passive_source_error_v)
            if record_states:
                row['pad_observations']=[(start+fraction*(stop-start),
                    initial_network.forecast_terms(fraction*(stop-start),projected)) for fraction in (.5,1.)]
                row['end_rails']=local.domains.voltage.copy() if local.domains is not None else np.array([local.rail_v])
            accepted.append(row)
            current={'rail':local.rail_trajectory,**(local.domain_trajectories or {})}
            for name,trace in current.items():
                times,values=traces.setdefault(name,([],[]));offset=1 if times else 0
                times.extend(trace.times[offset:]);values.extend(trace.deltas[offset:])
        local.rail_trajectory=SupplyTrajectory(*traces.pop('rail'))
        if local.domains is not None:
            local.domain_trajectories={name:SupplyTrajectory(*trace) for name,trace in traces.items()}
            local.domains.trajectories=local.domain_trajectories
        return local,dict(attempts=attempts,segments=accepted,continuous_error_bound=False)

    def advance(self,time,command,rtol=1e-8,atol=1e-11,max_step=math.inf,rail_trace_step_s=None,solver_method="Radau",passive_terms=None,source_error_limit_v=None):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic time')
        if max_step<=0 or math.isnan(max_step):raise ValueError('Invalid integration step bound')
        if rail_trace_step_s is not None and (not math.isfinite(rail_trace_step_s) or rail_trace_step_s<=0):
            raise ValueError('Positive finite rail trace step required')
        drive=command if callable(command) else lambda t:command
        self.law.source(drive(self.time),self.rail_v)
        if time==self.time:return
        n=self.network;law=self.law
        B=np.linalg.solve(n.C,np.array([1/50,0,0,0],complex))
        ref_index=11 if self.detector is not None else 9
        rx_index=ref_index+(self.reference is not None)
        count=len(self.rx_bank['poles']) if self.rx_bank is not None else 0
        energy_index=rx_index+2*count
        domain_index=energy_index+4
        domains=self.domains;host=self.host_bank
        domain_count=len(domains.names) if domains is not None else 0
        pad=self.pad_branch
        if pad is not None and (domains is None or pad.time!=self.time):
            raise ValueError('Shared pad requires aligned domain owner')
        host_end=domain_index+(len(host.state) if host is not None else domain_count)
        pad_index=host_end
        projected_source_error=0.
        if passive_terms is not None:
            if source_error_limit_v is None or not math.isfinite(source_error_limit_v) or source_error_limit_v<=0:
                raise ValueError('Passive reduction needs an explicit positive source-error budget')
            if not self.driver_enabled and any(a!=0 for a,_ in passive_terms):
                raise ValueError("Disabled driver cannot supply projected RF source")
            n.forecast_terms(0.,passive_terms)
        def rhs(t,y):
            nonlocal projected_source_error
            v=y[:4]+1j*y[4:8];rail=y[8]
            rails=y[domain_index:domain_index+domain_count] if domains is not None else None
            reference_rail=rails[self.reference_domain] if domains is not None else rail
            extra_rail=rails[self.wire_domain] if domains is not None else rail
            source=law.source(drive(t),rail) if self.driver_enabled else 0j
            if passive_terms is None:
                dv=n.A@v+B*source
            else:
                dt=t-self.time
                projected=sum(a*np.exp(rate*dt) for a,rate in passive_terms)
                projected_source_error=max(projected_source_error,abs(projected-source))
                v=n.forecast_terms(dt,passive_terms)
                source=projected
                dv=np.zeros(4,complex)
            power=float(np.real(source*np.conj((source-v[0])/50)))
            current=law.consumption(rail,power)['dc_current_a'] if self.driver_enabled else 0.
            driver_current=current
            reference_current=0.
            extra=self.extra_current(t,extra_rail)
            if not math.isfinite(extra) or extra<0:raise ValueError('Invalid additional rail load')
            current+=extra
            dr=((law.nominal_v-rail)/self.r-current)/self.c
            result=np.r_[dv.real,dv.imag,dr]
            if self.detector is not None:
                d=self.detector
                result=np.r_[result,d.pole*(abs(v[2])**2-y[9]),d.readout_pole*(y[9]-y[10])]
            if self.reference is not None:
                r=self.reference;target=1+r.driver_sensitivity*(reference_rail-r.driver_nominal)
                power=limited_power(y[ref_index],target,r.r,reference_rail,self.source_limit,self.sink_limit,self.reference_bias,self.reference_efficiency)
                result[8]-=power['dc_current_a']/self.c
                reference_current=power['dc_current_a']
                current+=reference_current
                result=np.r_[result,power['current_a']/r.c]
            if count:
                states=y[rx_index:rx_index+count]+1j*y[rx_index+count:rx_index+2*count]
                signal=self.receive(t,v[1])
                if not np.isfinite(signal):raise ValueError('Nonfinite RX input')
                change=np.asarray(self.rx_bank['poles'])*(signal-states)
                result=np.r_[result,change.real,change.imag]
            if domains is not None:
                # All physical rails and analog states share this one ODE.
                currents=domains.currents(self.domain_load(t,rails.copy())).copy()
                currents[self.rf_domain]+=driver_current
                currents[self.reference_domain]+=reference_current
                currents[self.wire_domain]+=extra
                pad_result=None
                if pad is not None:
                    pad_result=pad.electrical(y[pad_index:pad_index+2],extra_rail)
                    currents[self.wire_domain]+=pad_result[1]
                external_return=self.external_return_current(t)
                if not math.isfinite(external_return) or external_return<0:
                    raise ValueError('Invalid external ground current')
                if external_return and host is None:
                    raise ValueError('External current requires explicit return-node model')
                host_states=None;driver_loss=0.;external_ground_power=0.
                if host is not None:
                    host_states=y[domain_index:host_end]
                    currents+=host.internal_current(t)
                    ground,feed,up,down=(host.currents(host_states,host.drive,external_return_a=external_return)
                        if external_return else host.currents(host_states,host.drive))
                    if not self.external_return_guard(t,ground):
                        raise ValueError("External sink outside local-ground compliance")
                    external_ground_power=ground*external_return
                    # Reuse the already solved return-node currents. Calling
                    # host.derivative here would solve the identical KCL twice.
                    derivative=np.concatenate(((feed-currents-np.bincount(
                        host.output_domain,weights=up,minlength=domain_count))/host.decap,
                        (up-down)/host.load_cap))
                    outputs=host_states[domain_count:]
                    driver_loss=float(up@(rails[host.output_domain]+ground-outputs)+down@(outputs-ground))
                    feed_loss=float(domains.feed_r@(feed**2)+ground**2/host.return_r)
                else:
                    feed=domains.conductance@(domains.nominal-rails)
                    derivative=(feed-currents)/domains.c
                    feed_loss=float(feed@domains.resistance@feed)
                result[8]=derivative[self.rf_domain]
                out_rhs=np.r_[result,(domains.nominal@feed+external_ground_power)/self.c,
                    feed_loss/self.c,(rails@currents+driver_loss)/self.c,
                    extra_rail*extra/self.c,derivative]
                if pad_result is not None:
                    dp,ip,external,loss=pad_result
                    out_rhs=np.r_[out_rhs,dp,extra_rail*ip/self.c,external/self.c,loss/self.c]
                return out_rhs
            feed=(law.nominal_v-rail)/self.r
            # Scale energy states by C for comparable numerical tolerances.
            return np.r_[result,law.nominal_v*feed/self.c,feed*feed*self.r/self.c,
                         rail*current/self.c,rail*extra/self.c]
        def undervoltage(t,y):
            return float(np.min(y[domain_index:domain_index+domain_count]-self.domain_floor)) if domains is not None else y[8]-self.minimum_rail_v
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
        y=np.r_[y,0.,0.,0.,0.]
        if domains is not None:y=np.r_[y,domains.voltage]
        if host is not None:y=np.r_[y,host.state[domain_count:]]
        if pad is not None:y=np.r_[y,pad.voltage,0.,0.,0.]
        sol=solve_ivp(rhs,(self.time,time),y,method=solver_method,rtol=rtol,atol=atol,events=undervoltage,max_step=max_step,dense_output=rail_trace_step_s is not None)
        if not sol.success or sol.status==1:raise ValueError('Coupled driver left declared rail envelope or integration failed')
        trajectory=None;domain_trajectories=None
        if rail_trace_step_s is not None:
            from autonomous_pll import SupplyTrajectory
            times=np.linspace(self.time,time,max(1,math.ceil((time-self.time)/rail_trace_step_s))+1)
            samples=sol.sol(times)
            trajectory=SupplyTrajectory(tuple(times),tuple(samples[8]-law.nominal_v))
            if domains is not None:
                domain_trajectories={name:SupplyTrajectory(tuple(times),tuple(samples[domain_index+i]-domains.nominal[i]))
                    for i,name in enumerate(domains.names)}
        if passive_terms is not None and projected_source_error>source_error_limit_v:
            raise PassiveSourceBudgetExceeded('Passive source approximation exceeds declared error budget')
        # Transactional update: failed exploratory solves cannot corrupt live state.
        out=sol.y[:,-1].copy()
        if passive_terms is not None:
            endpoint=n.forecast_terms(time-self.time,passive_terms)
            out[:4]=endpoint.real;out[4:8]=endpoint.imag
        if self.reference is not None and out[ref_index]<=.1:raise ValueError('Reference outside model')
        if not np.all(np.isfinite(out)):raise ValueError('Nonfinite coupled state')
        if self.detector is not None:
            if min(out[9:11]) < -1e-10:raise ValueError('Invalid detector state')
            self.detector.value=max(0.,float(out[9]));self.detector.readout_value=max(0.,float(out[10]));self.detector.time=time
        if self.reference is not None:
            r=self.reference;r.voltage=float(out[ref_index]);r.time=time;r.minimum=min(r.minimum,r.voltage)
            r.driver_voltage=float(out[domain_index+self.reference_domain] if domains is not None else out[8]);r.driver_epoch=time;r.driver_slope=0.
        if count:
            states=out[rx_index:rx_index+count]+1j*out[rx_index+count:rx_index+2*count]
            self.rx_bank['states']=list(states)
            self.received=sum(w*x for w,x in zip(self.rx_bank['weights'],states))
        if pad is not None:
            pad.voltage=out[pad_index:pad_index+2].copy();pad.time=time
            pad.source_energy_j+=float(out[pad_index+2])*self.c
            pad.external_energy_j+=float(out[pad_index+3])*self.c
            pad.dissipated_j+=float(out[pad_index+4])*self.c
        n.voltage=out[:4]+1j*out[4:8]
        self.source_energy_j+=float(out[energy_index])*self.c
        self.rail_resistor_energy_j+=float(out[energy_index+1])*self.c
        self.load_energy_j+=float(out[energy_index+2])*self.c
        self.extra_load_energy_j+=float(out[energy_index+3])*self.c
        self.passive_source_error_v=projected_source_error if passive_terms is not None else None
        self.rail_v=float(out[8]);self.time=time;n.time=time
        self.rail_trajectory=trajectory
        self.domain_trajectories=domain_trajectories
        if domains is not None:
            domains.voltage=out[domain_index:domain_index+domain_count].copy();domains.time=time
            if host is not None:
                pending=host.pending_charge.copy()
                host.pending_charge=pending*np.exp(-(time-host.time)/host.switching_tau)
                host.consumed_charge+=pending-host.pending_charge
                host.state=out[domain_index:host_end].copy();host.time=time
            domains.source_energy_j+=float(out[energy_index])*self.c
            domains.feed_loss_j+=float(out[energy_index+1])*self.c
            domains.load_energy_j+=float(out[energy_index+2])*self.c
            domains.trajectories=domain_trajectories
