"""Edge-driven ideal PFD/charge pump, passive filter and continuous VCO phase.

Ideal pump current is valid only inside the declared compliance envelope. The
solver stops at its first boundary instead of clipping capacitor charge or
extrapolating an unqualified transistor current model.
"""
import copy
import math
from autonomous_pll import AutonomousPLL
from charge_pump_filter import ChargePumpFilter
from oscillator_noise import FrequencyNoise


class EdgePumpPLL:
    FILTER_CLASS=ChargePumpFilter
    def __init__(self,rate_hz=1.25e9,reference_hz=10e6,free_offset=-.04,
                 bandwidth_hz=1e6,fast_fraction=.5,pump_current=100e-6,
                 initial_voltage=0.,initial_phase_cycles=0.,limit_v=1.,filter_kwargs=None):
        if not all(math.isfinite(x) and x>0 for x in (rate_hz,reference_hz)):
            raise ValueError('Positive finite clock frequencies required')
        ratio=rate_hz/reference_hz
        if not math.isfinite(ratio) or ratio<1 or ratio!=int(ratio):raise ValueError('Integer feedback ratio required')
        if not math.isfinite(initial_phase_cycles) or initial_phase_cycles>=ratio:
            raise ValueError('Initial phase must precede the first feedback edge')
        self.gains=AutonomousPLL(reference_hz=reference_hz,divider=ratio,
            free_hz=rate_hz*(1+free_offset),bandwidth_hz=bandwidth_hz,phase_cycles=0.)
        self.filter=self.FILTER_CLASS.from_gains(self.gains.kp,self.gains.ki,pump_current,
            fast_fraction,voltage=initial_voltage,limit_v=limit_v,**(filter_kwargs or {}))
        if not self.filter.compliant or self.gains.free_hz-self.gains.kvco*limit_v<=0:
            raise ValueError('Invalid initial voltage or positive-frequency envelope')
        self.rate=rate_hz;self.reference=reference_hz;self.divider=int(ratio)
        self.current_amplitude=pump_current;self.phase=initial_phase_cycles;self.time=0.
        self.reference_origin=0.
        self.present=True
        self.up=self.down=False;self.reference_index=1;self.next_reference=1/reference_hz
        self.feedback_target=float(self.divider);self.feedback_edges=0
        self.good=0;self.locked=False;self.first_lock=None;self.fault=None
        self.reference_history=[];self.transitions=[]
        self.frequency_noise=FrequencyNoise(())
        self.rail_amplitude_hz=0.;self.rail_epoch=0.;self.rail_tau=1.

    def feedback_interval(self):return self.divider

    def __copy__(self):
        clone=object.__new__(type(self));clone.__dict__=self.__dict__.copy()
        clone.filter=copy.copy(self.filter);clone.gains=copy.copy(self.gains)
        clone.reference_history=list(self.reference_history)
        clone.transitions=list(self.transitions)
        return clone

    @property
    def output_phase_cycles(self):return self.phase

    def edge_time(self,target_phase):
        """Forecast an actual PFD/pump/VCO phase crossing without consuming events."""
        if self.fault or not math.isfinite(target_phase) or target_phase<self.phase:
            raise ValueError('A healthy loop and finite future phase are required')
        if target_phase==self.phase:return self.time
        minimum=self.gains.free_hz-self.gains.kvco*self.filter.limit+min(0.,self.rail_frequency(self.time))-self.frequency_noise.bound_hz
        if minimum<=0:raise ValueError('Positive VCO envelope required')
        lo=self.time;hi=lo+(target_phase-self.phase)/minimum
        mid=min(hi,lo+(target_phase-self.phase)/self.frequency_hz)
        for _ in range(52):
            trial=copy.copy(self)
            if not trial.advance(mid):raise ValueError('Clock forecast reaches pump compliance fault')
            residual=trial.phase-target_phase
            if abs(residual)<1e-9:return mid
            if residual<0:lo=mid
            else:hi=mid
            if hi-lo<=max(2*math.ulp(mid),1e-21):return (lo+hi)/2
            candidate=mid-residual/trial.frequency_hz
            mid=candidate if lo<candidate<hi else (lo+hi)/2
        raise ArithmeticError('Pump-clock crossing did not converge')

    def set_reference(self,present,time):
        if not isinstance(present,bool) or not math.isfinite(time) or time<self.time:
            raise ValueError('Invalid reference transition')
        if not self.advance(time):raise ValueError('Faulted pump loop requires explicit recovery')
        if present==self.present:return
        old=self.current;self.present=present;self.up=self.down=False
        self.good=0;self.locked=False
        if present:
            self.reference_index=math.floor((time-self.reference_origin)*self.reference)+1
            self.next_reference=self.reference_origin+self.reference_index/self.reference
            while self.next_reference<=time:
                self.reference_index+=1;self.next_reference=self.reference_origin+self.reference_index/self.reference
        else:self.next_reference=math.inf
        if old!=self.current:self.transitions.append((time,self.current))

    @property
    def current(self):return self.current_amplitude*(int(self.up)-int(self.down)) if self.present else 0.

    def rail_frequency(self,time):
        return self.rail_amplitude_hz*math.exp(-(time-self.rail_epoch)/self.rail_tau)

    def rail_phase_integral(self,start,end):
        """Integrated supply-induced cycles; override with the same rail trajectory."""
        if not all(math.isfinite(x) for x in (start,end)) or end<start:
            raise ValueError('Invalid rail integration interval')
        return self.rail_frequency(start)*self.rail_tau*(-math.expm1(-(end-start)/self.rail_tau))

    def set_supply(self,time,delta_v,tau_s,hz_per_v):
        if not all(math.isfinite(v) for v in (time,delta_v,tau_s,hz_per_v)) or time<self.time or tau_s<=0:
            raise ValueError('Invalid pulse-loop rail forcing')
        amplitude=delta_v*hz_per_v
        if not math.isfinite(amplitude) or self.gains.free_hz-self.gains.kvco*self.filter.limit+min(0.,amplitude)-self.frequency_noise.bound_hz<=0:
            raise ValueError('Rail forcing exceeds positive-frequency envelope')
        if not self.advance(time):raise ValueError('Cannot disturb a faulted pulse loop')
        self.rail_amplitude_hz=amplitude;self.rail_epoch=time;self.rail_tau=tau_s

    def set_noise(self,time,source):
        if not isinstance(source,FrequencyNoise) or not math.isfinite(time) or time<self.time:
            raise ValueError('Finite future time and immutable noise source required')
        minimum=self.gains.free_hz-self.gains.kvco*self.filter.limit+min(0.,self.rail_frequency(time))-source.bound_hz
        if minimum<=0:raise ValueError('Noise exceeds positive VCO envelope')
        if not self.advance(time):raise ValueError('Cannot disturb a faulted pulse loop')
        self.frequency_noise=source

    @property
    def frequency_hz(self):return self.gains.free_hz+self.gains.kvco*self.filter.v+self.rail_frequency(self.time)+self.frequency_noise.frequency(self.time)

    def predict(self,time):
        trial=copy.copy(self.filter);previous=trial.voltage_integral
        trial.voltage_integral=0.;trial.advance(time,self.current)
        integral=trial.voltage_integral;trial.voltage_integral+=previous
        rail_phase=self.rail_phase_integral(self.time,time)
        phase=self.phase+self.gains.free_hz*(time-self.time)+self.gains.kvco*integral+rail_phase+self.frequency_noise.phase_integral(self.time,time)
        return trial,phase

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid pump-loop time')
        while self.time<time and self.fault is None:
            end=min(time,self.next_reference)
            trial,phase=self.predict(end);boundary=False
            if not trial.compliant:
                # Prefix extrema make this predicate monotonic even if voltage
                # subsequently re-enters its range within the interval.
                lo,hi=self.time,end
                for _ in range(52):
                    mid=(lo+hi)/2
                    if self.predict(mid)[0].compliant:lo=mid
                    else:hi=mid
                end=lo;trial,phase=self.predict(end);boundary=True
            feedback=phase>=self.feedback_target-1e-9
            if feedback and abs(phase-self.feedback_target)>1e-9:
                lo,hi=self.time,end
                for _ in range(52):
                    mid=(lo+hi)/2
                    if self.predict(mid)[1]<self.feedback_target:lo=mid
                    else:hi=mid
                end=(lo+hi)/2;trial,phase=self.predict(end);boundary=False
            old_current=self.current
            self.filter=trial;self.phase=phase;self.time=end
            reference=end==self.next_reference
            # Both edge flags are applied before the ideal asynchronous reset.
            if reference:self.up=True
            if feedback:
                self.down=self.present;self.feedback_edges+=1;self.feedback_target+=self.feedback_interval()
            if self.up and self.down:self.up=self.down=False
            # An edge may turn the pump off exactly at the boundary. In that
            # case passive redistribution returns the node into its range.
            if boundary and self.current==old_current:
                self.fault='charge-pump compliance boundary';self.locked=False;break
            if self.current!=old_current:
                self.transitions.append((end,self.current))
            if reference:
                fraction=self.phase/self.divider
                phase_error=(fraction-round(fraction))/self.reference
                frequency_error=self.frequency_hz/self.rate-1
                valid=abs(phase_error)<250e-12 and abs(frequency_error)<100e-6
                self.good=self.good+1 if valid else 0;self.locked=self.good>=8
                if self.locked and self.first_lock is None:self.first_lock=end
                self.reference_history.append((end,phase_error,frequency_error,self.filter.v,self.locked))
                self.reference_index+=1;self.next_reference=self.reference_origin+self.reference_index/self.reference
        return self.fault is None

    def metrics(self):
        return dict(time_s=self.time,reference_present=self.present,locked=self.locked,first_lock_s=self.first_lock,fault=self.fault,
            compliance_boundary_reached=self.fault is not None,
            minimum_compliance_margin_v=self.filter.limit-max(abs(self.filter.minimum),abs(self.filter.maximum)),
            feedback_edges=self.feedback_edges,reference_edges=len(self.reference_history),
            pump_transitions=len(self.transitions),filter=self.filter.metrics(),
            final_frequency_hz=self.frequency_hz,reference_tail=self.reference_history[-16:])
