"""Averaged phase/frequency detector, PI filter and bounded autonomous VCO.

Phase error is measured in reference cycles. The ideal divided VCO phase is
continuous; a fractional divider here specifies an average ratio, not its edge
pattern. Parameters are declared mathematical assumptions, not GF180 estimates.
"""
import math
import copy
from dataclasses import dataclass
from bisect import bisect_right
from oscillator_noise import FrequencyNoise


@dataclass(frozen=True)
class SupplyTrajectory:
    """Immutable piecewise-linear voltage history with a strict forecast horizon.

    Values are deltas from nominal. Interpolation accuracy belongs to the analog
    producer and must be checked by refinement; extrapolation is forbidden.
    """
    times: tuple
    deltas: tuple

    def __post_init__(self):
        object.__setattr__(self,'times',tuple(self.times))
        object.__setattr__(self,'deltas',tuple(self.deltas))
        if len(self.times)<1 or len(self.times)!=len(self.deltas):
            raise ValueError('Supply history needs aligned voltage/time samples')
        if not all(math.isfinite(v) for v in self.times+self.deltas):
            raise ValueError('Nonfinite supply history')
        if any(b<=a for a,b in zip(self.times,self.times[1:])):
            raise ValueError('Supply history must increase strictly')

    def voltage(self,time):
        if not math.isfinite(time) or not self.times[0]<=time<=self.times[-1]:
            raise ValueError('Supply forecast outside known analog history')
        if len(self.times)==1:return self.deltas[0]
        i=min(len(self.times)-2,max(0,bisect_right(self.times,time)-1))
        fraction=(time-self.times[i])/(self.times[i+1]-self.times[i])
        return self.deltas[i]+fraction*(self.deltas[i+1]-self.deltas[i])


class AutonomousPLL:
    def __init__(self, reference_hz=40e6, divider=60., free_hz=2.38e9,
                 kvco_hz_per_v=200e6, bandwidth_hz=1e6, damping=.707,
                 rail_v=1., phase_cycles=.2, max_step_s=1e-9,
                 lock_phase_cycles=.01,lock_frequency_hz=4000.):
        parameters=(reference_hz, divider, free_hz, kvco_hz_per_v,
                    bandwidth_hz, damping, rail_v, max_step_s,lock_phase_cycles,lock_frequency_hz)
        if not all(math.isfinite(x) and x>0 for x in parameters):
            raise ValueError('PLL parameters must be finite and positive')
        if not math.isfinite(phase_cycles):
            raise ValueError('Nonfinite initial phase')
        if free_hz<=kvco_hz_per_v*rail_v:
            raise ValueError('VCO frequency must remain positive across tuning range')
        self.lock_phase_cycles=lock_phase_cycles;self.lock_frequency_hz=lock_frequency_hz
        self.reference_hz=reference_hz; self.divider=divider
        self.free_hz=free_hz; self.kvco=kvco_hz_per_v; self.rail=rail_v
        omega=2*math.pi*bandwidth_hz
        self.kp=2*damping*omega/(kvco_hz_per_v/divider)
        self.ki=omega**2/(kvco_hz_per_v/divider)
        self.antiwindup_rate=omega
        self.error=phase_cycles; self.integral=0.; self.time=0.; self.phase_offset=0.
        self.max_step=max_step_s; self.present=True; self.hold_voltage=0.
        self.supply_shift_hz=0.; self.rail_amplitude_hz=0.; self.rail_epoch=0.; self.rail_tau=1.
        self.supply_trajectory=None;self.trajectory_hz_per_v=0.
        self.good=0; self.locked=False
        self.saturation_time=0.;self.frequency_noise=FrequencyNoise(())

    def initialize_reference(self,time,first_tick):
        # Continuous-detector baseline has no sampled state to reset.
        pass

    def clip(self,value):
        return max(-self.rail,min(self.rail,value))

    def control(self,error=None,integral=None):
        if not self.present:return self.hold_voltage
        e=self.error if error is None else error
        i=self.integral if integral is None else integral
        return self.clip(self.kp*max(-.5,min(.5,e))+i)

    def rail_frequency(self,time):
        if self.supply_trajectory is not None:
            # RK half-step sums can round a few ulps beyond an exact endpoint.
            # Public advance/edge horizons remain strict in validate_supply_horizon.
            lo,hi=self.supply_trajectory.times[0],self.supply_trajectory.times[-1]
            if time>hi and time-hi<=2*max(math.ulp(time),math.ulp(hi)):time=hi
            if time<lo and lo-time<=2*max(math.ulp(time),math.ulp(lo)):time=lo
            return self.trajectory_hz_per_v*self.supply_trajectory.voltage(time)
        return self.rail_amplitude_hz*math.exp(-(time-self.rail_epoch)/self.rail_tau)

    def validate_supply_horizon(self,time):
        if self.supply_trajectory is not None:
            self.supply_trajectory.voltage(time)

    def minimum_rail_frequency(self):
        if self.supply_trajectory is not None:
            return min(self.trajectory_hz_per_v*v for v in self.supply_trajectory.deltas)+self.minimum_extra_rail_frequency()
        return min(0.,self.rail_frequency(self.time))

    def minimum_extra_rail_frequency(self):
        return 0.

    def set_supply_trajectory(self,trajectory,hz_per_v):
        if not isinstance(trajectory,SupplyTrajectory) or not math.isfinite(hz_per_v):
            raise ValueError('Immutable supply trajectory and finite sensitivity required')
        if trajectory.times[0]!=self.time:raise ValueError('Supply trajectory must start at PLL time')
        shifts=tuple(hz_per_v*v for v in trajectory.deltas)
        if not all(math.isfinite(v) for v in shifts):raise ValueError('Nonfinite supply frequency shift')
        minimum=min(shifts)+self.minimum_extra_rail_frequency()
        if self.free_hz-self.kvco*self.rail+self.supply_shift_hz+minimum-self.frequency_noise.bound_hz<=0:
            raise ValueError('Supply trajectory can reverse oscillator phase')
        self.supply_trajectory=trajectory;self.trajectory_hz_per_v=hz_per_v

    @property
    def frequency_hz(self):
        return self.free_hz+self.kvco*self.control()+self.supply_shift_hz+self.rail_frequency(self.time)+self.frequency_noise.frequency(self.time)

    def derivative(self,error,integral,time=None):
        if time is None:time=self.time
        detector=max(-.5,min(.5,error))
        raw=self.kp*detector+integral
        control=self.control(error,integral)
        frequency=self.free_hz+self.kvco*control+self.supply_shift_hz+self.rail_frequency(time)+self.frequency_noise.frequency(time)
        if frequency<=0:raise ValueError('Disturbance reverses oscillator phase')
        # Continuous back-calculation pulls the filter state toward the
        # realizable tuning voltage without discontinuous integrator chatter.
        di=(self.ki*detector+self.antiwindup_rate*(control-raw)) if self.present else 0.
        return self.reference_hz-frequency/self.divider,di

    def rk_step(self,e,i,h,time):
        a,b=self.derivative(e,i,time)
        c,d=self.derivative(e+h*a/2,i+h*b/2,time+h/2)
        f,g=self.derivative(e+h*c/2,i+h*d/2,time+h/2)
        j,k=self.derivative(e+h*f,i+h*g,time+h)
        return e+h*(a+2*c+2*f+j)/6,i+h*(b+2*d+2*g+k)/6

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:
            raise ValueError('PLL time must be finite and monotonic')
        self.validate_supply_horizon(time)
        while self.time<time:
            h=min(self.max_step,time-self.time,self.frequency_noise.integration_step_s)
            if self.supply_trajectory is not None:
                knots=self.supply_trajectory.times
                next_knot=knots[bisect_right(knots,self.time)]
                h=min(h,next_knot-self.time)
            e,i=self.error,self.integral
            # Resolve switching at tuning/anti-windup boundaries instead of
            # allowing reference cadence to determine the acquisition result.
            while True:
                full=self.rk_step(e,i,h,self.time)
                half=self.rk_step(e,i,h/2,self.time)
                refined=self.rk_step(*half,h/2,self.time+h/2)
                if max(abs(a-b) for a,b in zip(full,refined))<=1e-10:break
                h/=2
                if h<1e-16:raise ArithmeticError('PLL integration did not converge')
            saturated=abs(self.control())>=self.rail
            self.error,self.integral=refined
            self.time=min(time,self.time+h)
            if saturated:self.saturation_time+=h

    @property
    def output_phase_cycles(self):
        return self.phase_offset+self.divider*(self.reference_hz*self.time-self.error)

    def edge_time(self,target_phase):
        """Predict a future phase crossing without advancing oscillator state.

        The caller must discard this prediction if a new disturbance arrives.
        Positivity over the tuning range guarantees a unique forward crossing.
        """
        phase=self.output_phase_cycles
        if not math.isfinite(target_phase) or target_phase<phase:
            raise ValueError('Clock edge must be a finite future phase crossing')
        if target_phase==phase:return self.time
        minimum=self.free_hz-self.kvco*self.rail+self.supply_shift_hz+self.minimum_rail_frequency()-self.frequency_noise.bound_hz
        lo=self.time;hi=lo+(target_phase-phase)/minimum
        if self.supply_trajectory is not None:
            hi=min(hi,self.supply_trajectory.times[-1])
            trial=copy.copy(self);trial.advance(hi)
            if trial.output_phase_cycles<target_phase-1e-10:
                raise ValueError('Clock edge exceeds supply forecast horizon')
        mid=min(hi,lo+(target_phase-phase)/self.frequency_hz)
        for _ in range(48):
            trial=copy.copy(self);trial.advance(mid)
            residual=trial.output_phase_cycles-target_phase
            if abs(residual)<1e-10:return mid
            if residual<0:lo=mid
            else:hi=mid
            if hi-lo<=max(2*math.ulp(mid),1e-21):return (lo+hi)/2
            candidate=mid-residual/trial.frequency_hz
            mid=candidate if lo<candidate<hi else (lo+hi)/2
        raise ArithmeticError('Oscillator phase crossing did not converge')

    def observe_lock(self):
        valid=(self.present and abs(self.error)<self.lock_phase_cycles and
               abs(self.frequency_hz/self.divider-self.reference_hz)<self.lock_frequency_hz)
        self.good=self.good+1 if valid else 0
        self.locked=self.good>=8
        return self.locked

    def set_reference(self,present,time):
        self.advance(time)
        if not present:self.hold_voltage=self.control()
        self.present=bool(present); self.good=0; self.locked=False

    def disturb(self,time,phase_cycles=0.,frequency_hz=0.):
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid disturbance time')
        if not all(math.isfinite(x) for x in (phase_cycles,frequency_hz)):
            raise ValueError('Nonfinite PLL disturbance')
        if self.free_hz-self.kvco*self.rail+frequency_hz+min(0.,self.rail_frequency(time))-self.frequency_noise.bound_hz<=0:
            raise ValueError('Disturbance can reverse oscillator phase')
        self.advance(time); self.error+=phase_cycles
        self.supply_shift_hz=frequency_hz

    def set_supply(self,time,delta_v,tau_s,hz_per_v):
        if not all(math.isfinite(v) for v in (time,delta_v,tau_s,hz_per_v)) or tau_s<=0:
            raise ValueError('Invalid oscillator supply response')
        amplitude=delta_v*hz_per_v
        if not math.isfinite(amplitude) or self.free_hz-self.kvco*self.rail+self.supply_shift_hz+min(0.,amplitude)-self.frequency_noise.bound_hz<=0:
            raise ValueError('Supply response exceeds positive oscillator envelope')
        self.advance(time)
        self.supply_trajectory=None
        self.rail_amplitude_hz=amplitude;self.rail_epoch=time;self.rail_tau=tau_s

    def set_noise(self,time,source):
        if not isinstance(source,FrequencyNoise):raise ValueError('Immutable spectral source required')
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid noise configuration time')
        lower=self.free_hz-self.kvco*self.rail+self.supply_shift_hz+min(0.,self.rail_frequency(time))-source.bound_hz
        if lower<=0:raise ValueError('Noise exceeds positive oscillator envelope')
        self.advance(time);self.frequency_noise=source
